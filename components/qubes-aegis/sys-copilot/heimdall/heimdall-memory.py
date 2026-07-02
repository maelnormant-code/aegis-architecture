#!/usr/bin/env python3
"""heimdall-memory.py — Procedural & Episodic Memory Manager for Aegis Copilot.

Implements the Nous Research Heimdall Agent memory model:
  - USER.md: User preferences, style, expectations.
  - MEMORY.md: Environment facts, learned conventions, project contexts.
  - skills/ directory: On-demand Markdown files (SKILL.md) with YAML frontmatter.
  - Semantic/keyword matching for dynamic skill injection.
  - Autonomous skill creation & reflection update loops.
"""

import os
import re
import yaml
import sqlite3
import time
import shutil
import json
from llm_client import call_llm

AEGIS_DIR = "/var/lib/aegis"
USER_FILE = os.path.join(AEGIS_DIR, "USER.md")
MEMORY_FILE = os.path.join(AEGIS_DIR, "MEMORY.md")
SKILLS_DIR = os.path.join(AEGIS_DIR, "skills")
CONVERSATIONS_DB = os.path.join(AEGIS_DIR, "conversations.db")

DEFAULT_USER = """# User Profile
- Name: Aegis OS Operator
- Preferred Style: Concise, direct, technical, security-focused.
- Permissions: Dom0 access, hardware management, template configuration.
"""

DEFAULT_MEMORY = """# Personal Notes & Memory
- System identity: Aegis Copilot (Network-isolated AI helper for Aegis OS).
- Environment: Hardened Qubes OS fork.
- Core constraint: Running in sys-copilot AppVM (NetVM: none).
- Inference node: sys-ai VM (GPU-accelerated, air-gapped).
- RAG node: sys-knowledge VM (air-gapped SQLite FTS5 database).
"""

def init_db():
    """Initialize the filesystem-based memory structures."""
    os.makedirs(AEGIS_DIR, exist_ok=True)
    os.makedirs(SKILLS_DIR, exist_ok=True)

    if not os.path.exists(USER_FILE):
        with open(USER_FILE, "w", encoding="utf-8") as f:
            f.write(DEFAULT_USER)

    if not os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            f.write(DEFAULT_MEMORY)
            
    # Initialize conversations DB
    conn = sqlite3.connect(CONVERSATIONS_DB)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            session_id TEXT PRIMARY KEY,
            user_query TEXT,
            agent_response TEXT,
            timestamp REAL
        )
    ''')
    cur.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS conversations_fts USING fts5(
            user_query,
            agent_response,
            content='conversations',
            content_rowid='rowid'
        )
    ''')
    # Trigger to keep fts in sync
    cur.execute('''
        CREATE TRIGGER IF NOT EXISTS conversations_ai AFTER INSERT ON conversations BEGIN
            INSERT INTO conversations_fts(rowid, user_query, agent_response)
            VALUES (new.rowid, new.user_query, new.agent_response);
        END;
    ''')
    cur.execute('''
        CREATE TRIGGER IF NOT EXISTS conversations_au AFTER UPDATE ON conversations BEGIN
            INSERT INTO conversations_fts(conversations_fts, rowid, user_query, agent_response)
            VALUES('delete', old.rowid, old.user_query, old.agent_response);
            INSERT INTO conversations_fts(rowid, user_query, agent_response)
            VALUES (new.rowid, new.user_query, new.agent_response);
        END;
    ''')
    cur.execute('''
        CREATE TRIGGER IF NOT EXISTS conversations_ad AFTER DELETE ON conversations BEGIN
            INSERT INTO conversations_fts(conversations_fts, rowid, user_query, agent_response)
            VALUES('delete', old.rowid, old.user_query, old.agent_response);
        END;
    ''')
    conn.commit()
    conn.close()

def get_user_profile() -> str:
    try:
        with open(USER_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return DEFAULT_USER.strip()

def get_memory_notes() -> str:
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return DEFAULT_MEMORY.strip()

def update_user_profile(new_info: str):
    """Safely append or merge new user insights into USER.md."""
    if not new_info or new_info.strip() == "":
        return
    try:
        content = get_user_profile()
        # Clean new info lines
        lines = [l.strip() for l in new_info.strip().split("\n") if l.strip()]
        formatted_lines = []
        for line in lines:
            if not line.startswith("-"):
                line = f"- {line}"
            if line not in content:
                formatted_lines.append(line)
        
        if formatted_lines:
            with open(USER_FILE, "a", encoding="utf-8") as f:
                f.write("\n" + "\n".join(formatted_lines))
    except Exception:
        pass

def update_memory_notes(new_info: str):
    """Safely append or merge new environmental facts into MEMORY.md."""
    if not new_info or new_info.strip() == "":
        return
    try:
        content = get_memory_notes()
        lines = [l.strip() for l in new_info.strip().split("\n") if l.strip()]
        formatted_lines = []
        for line in lines:
            if not line.startswith("-"):
                line = f"- {line}"
            if line not in content:
                formatted_lines.append(line)
        
        if formatted_lines:
            with open(MEMORY_FILE, "a", encoding="utf-8") as f:
                f.write("\n" + "\n".join(formatted_lines))
    except Exception:
        pass

def parse_frontmatter(file_path: str) -> tuple[dict, str]:
    """Parse Jekyll-style YAML frontmatter from a Markdown file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Match frontmatter using regex
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        if m:
            frontmatter_text = m.group(1)
            body_text = m.group(2)
            meta = yaml.safe_load(frontmatter_text)
            if isinstance(meta, dict):
                return meta, body_text
        return {}, content
    except Exception:
        return {}, ""

def find_matching_skills(query: str) -> list[str]:
    """Scan the skills/ directory, parse metadata, and retrieve relevant skills."""
    if not os.path.exists(SKILLS_DIR):
        return []
    
    matching_skills = []
    query_tokens = set(re.findall(r"\w+", query.lower()))

    # Walk skills directory
    for root, dirs, files in os.walk(SKILLS_DIR):
        for fname in files:
            if fname == "SKILL.md":
                fpath = os.path.join(root, fname)
                meta, body = parse_frontmatter(fpath)
                
                # Check for keyword matches in skill metadata or title
                name = meta.get("name", "").lower()
                description = meta.get("description", "").lower()
                triggers = meta.get("triggers", [])
                if not isinstance(triggers, list):
                    triggers = [triggers]
                
                name_tokens = set(re.findall(r"\w+", name))
                desc_tokens = set(re.findall(r"\w+", description))
                
                trigger_matched = False
                for trig in triggers:
                    trig_tokens = set(re.findall(r"\w+", str(trig).lower()))
                    if query_tokens & trig_tokens:
                        trigger_matched = True
                        break
                
                if (query_tokens & name_tokens) or (query_tokens & desc_tokens) or trigger_matched:
                    # Include the skill content (both frontmatter and body)
                    with open(fpath, "r", encoding="utf-8") as f:
                        matching_skills.append(f.read().strip())
                        
    return matching_skills

def save_autonomous_skill(name: str, description: str, steps: str) -> bool:
    """Create a new skill folder and SKILL.md file autonomously or merge with existing."""
    if not name or not steps:
        return False
        
    query_tokens = set(re.findall(r"\w+", f"{name} {description}".lower()))
    similar_skill_path = None
    similar_skill_content = ""
    
    # Check for existing similar skills
    if os.path.exists(SKILLS_DIR):
        for root, dirs, files in os.walk(SKILLS_DIR):
            for fname in files:
                if fname == "SKILL.md":
                    fpath = os.path.join(root, fname)
                    meta, body = parse_frontmatter(fpath)
                    existing_name = meta.get("name", "").lower()
                    existing_desc = meta.get("description", "").lower()
                    
                    name_tokens = set(re.findall(r"\w+", existing_name))
                    desc_tokens = set(re.findall(r"\w+", existing_desc))
                    
                    if (query_tokens & name_tokens) or (query_tokens & desc_tokens):
                        similar_skill_path = fpath
                        with open(fpath, "r", encoding="utf-8") as f:
                            similar_skill_content = f.read()
                        break
            if similar_skill_path:
                break

    if similar_skill_path:
        # Merge using LLM
        prompt = f"""[System Skill Merger]
You are a skill optimizer. Merge the new skill steps into the existing skill, removing duplicates and ensuring a coherent combined SKILL.md format.

Existing Skill Content:
{similar_skill_content}

New Skill to Merge:
Name: {name}
Description: {description}
Steps:
{steps}

Output ONLY the merged markdown file content. It MUST contain YAML frontmatter with "name" and "description". Do not output any markdown block formatting like ```markdown. Just the raw text."""
        
        merged_content = ""
        success = False
        
        for attempt in range(3):
            merged_content = call_llm(prompt)
            # Clean potential markdown wrapping
            if merged_content.startswith("```markdown"):
                merged_content = merged_content[11:]
            elif merged_content.startswith("```"):
                merged_content = merged_content[3:]
            if merged_content.endswith("```"):
                merged_content = merged_content[:-3]
            merged_content = merged_content.strip()
            
            # YAML Validation Gate
            m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", merged_content, re.DOTALL)
            validation_error = ""
            if not m:
                validation_error = "Error: Missing YAML frontmatter enclosed in '---'."
            else:
                try:
                    meta = yaml.safe_load(m.group(1))
                    if not isinstance(meta, dict):
                        validation_error = "Error: YAML frontmatter must be a dictionary."
                    elif "name" not in meta or "description" not in meta:
                        validation_error = "Error: Frontmatter missing 'name' or 'description' key."
                except Exception as e:
                    validation_error = f"Error parsing YAML: {str(e)}"
            
            if not validation_error:
                success = True
                break
            else:
                prompt += f"\n\nPrevious attempt failed validation: {validation_error}\nPlease fix the YAML frontmatter and output the full merged markdown again."
                
        if not success:
            merged_content = similar_skill_content + f"\n\n# Unmerged Steps ({name})\n{steps}\n"
            
        # Anti-Truncation (Diff-Check)
        orig_len = len(similar_skill_content.splitlines())
        new_len = len(merged_content.splitlines())
        if new_len < orig_len * 0.5:
            merged_content += f"\n\n## Legacy Unmerged Steps\n{similar_skill_content}\n"
        
        try:
            with open(similar_skill_path, "w", encoding="utf-8") as f:
                f.write(merged_content)
            return True
        except Exception:
            return False
    else:
        # Generate clean name slug
        slug = re.sub(r"[^a-zA-Z0-9_-]", "_", name.strip().lower())
        skill_folder = os.path.join(SKILLS_DIR, slug)
        os.makedirs(skill_folder, exist_ok=True)
        
        skill_file = os.path.join(skill_folder, "SKILL.md")
        
        frontmatter = {
            "name": name.strip(),
            "description": description.strip()
        }
        
        try:
            yaml_text = yaml.dump(frontmatter, default_flow_style=False).strip()
            skill_content = f"---\n{yaml_text}\n---\n\n# {name.strip()}\n\n{steps.strip()}\n"
            with open(skill_file, "w", encoding="utf-8") as f:
                f.write(skill_content)
            return True
        except Exception:
            return False

def save_session(session_id: str, user_query: str, agent_response: str):
    conn = sqlite3.connect(CONVERSATIONS_DB)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO conversations (session_id, user_query, agent_response, timestamp) VALUES (?, ?, ?, ?)",
        (session_id, user_query, agent_response, time.time())
    )
    conn.commit()
    conn.close()

def retrieve_past_experiences(query: str, limit: int = 3) -> list[str]:
    conn = sqlite3.connect(CONVERSATIONS_DB)
    cur = conn.cursor()
    
    stop_words = {"a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "if", "in", "into", "is", "it", "no", "not", "of", "on", "or", "such", "that", "the", "their", "then", "there", "these", "they", "this", "to", "was", "will", "with"}
    
    # Simple tokenization for fts MATCH
    tokens = [t for t in re.findall(r"\w+", query.lower()) if t not in stop_words]
    if not tokens:
        return []
        
    search_query = " OR ".join(f"{t}*" for t in tokens)
    try:
        cur.execute(
            "SELECT user_query, agent_response FROM conversations_fts WHERE conversations_fts MATCH ? LIMIT ?",
            (search_query, limit)
        )
        rows = cur.fetchall()
        experiences = []
        for q, r in rows:
            experiences.append(f"Past Query: {q}\nPast Response: {r}")
        conn.close()
        return experiences
    except Exception:
        conn.close()
        return []

if __name__ == "__main__":
    init_db()
