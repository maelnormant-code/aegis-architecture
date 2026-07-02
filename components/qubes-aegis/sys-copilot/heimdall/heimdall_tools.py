import json
import subprocess
import time
import os
import sqlite3
import yaml
import fcntl

from heimdall_memory import update_user_profile, update_memory_notes

RATE_LIMIT_FILE = "/run/aegis/apply_state_ratelimit"
DB_PATH = "/var/lib/aegis/heimdall-context.db"

def query_knowledge(query: str) -> str:
    """Calls sys-knowledge RAG RPC to retrieve relevant documents."""
    try:
        proc = subprocess.run(
            ["qrexec-client-vm", "sys-knowledge", "aegis.KnowledgeQuery"],
            input=query.encode('utf-8'),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10
        )
        if proc.returncode == 0:
            res = json.loads(proc.stdout.decode('utf-8'))
            if res.get("status") == "ok":
                return "\n".join(res.get("results", []))
    except Exception as e:
        return f"Error querying knowledge: {str(e)}"
    return "No relevant knowledge found."

def apply_system_state(state_yaml: str) -> str:
    """Applies a Salt state via Dom0's ApplyAISystemState."""
    now = time.time()
    
    os.makedirs(os.path.dirname(RATE_LIMIT_FILE), exist_ok=True)
    with open(RATE_LIMIT_FILE, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            content = f.read().strip()
            if content:
                try:
                    last_call = float(content)
                    if now - last_call < 10.0:
                        return "Error: Rate limit exceeded for applying system state."
                except ValueError:
                    pass
            
            f.seek(0)
            f.truncate()
            f.write(str(now))
            f.flush()
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)

    try:
        proc = subprocess.run(
            ["qrexec-client-vm", "dom0", "qubes.ApplyAISystemState"],
            input=state_yaml.encode('utf-8'),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30
        )
        return proc.stdout.decode('utf-8')
    except Exception as e:
        return f"Error applying state: {str(e)}"

def query_acs_graph(query: str) -> str:
    """Searches recent system events in the ACS SQLite database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        search_query = f"%{query}%"
        cur.execute(
            "SELECT timestamp, label, payload_human FROM nodes WHERE payload_human LIKE ? OR payload_ai LIKE ? ORDER BY timestamp DESC LIMIT 10",
            (search_query, search_query)
        )
        rows = cur.fetchall()
        conn.close()
        if not rows:
            return "No matching ACS events found."
        return "\n".join([f"- {r[0]} | {r[1]}: {r[2]}" for r in rows])
    except Exception as e:
        return f"Error querying ACS graph: {str(e)}"

def read_audit_logs() -> str:
    """Calls Dom0's aegis.AuditLogRead to stream recent logs."""
    try:
        proc = subprocess.run(
            ["qrexec-client-vm", "dom0", "aegis.AuditLogRead"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10
        )
        return proc.stdout.decode('utf-8')
    except Exception as e:
        return f"Error reading audit logs: {str(e)}"

def write_memo(type: str, content: str) -> str:
    """Appends information directly to USER.md (type='user') or MEMORY.md (type='system')."""
    if type == "user":
        update_user_profile(content)
        return "Successfully updated USER.md"
    elif type == "system":
        update_memory_notes(content)
        return "Successfully updated MEMORY.md"
    else:
        return "Error: type must be 'user' or 'system'"

def create_qubes_vm(vm_name: str, template: str, label: str, vm_class: str = "AppVM", netvm: str = "sys-firewall") -> str:
    """
    Creates a new Qubes VM natively using SaltStack under the hood.
    Automatically registers and tags the VM with 'aegis-guest' for sandbox integration.
    """
    state = {
        vm_name: {
            "qvm.present": [
                {"template": template},
                {"label": label},
                {"class": vm_class}
            ]
        },
        f"{vm_name}-tags": {
            "qvm.tags": [
                {"name": vm_name},
                {"enable": ["aegis-guest"]},
                {"require": [{"qvm": vm_name}]}
            ]
        },
        f"{vm_name}-prefs": {
            "qvm.prefs": [
                {"name": vm_name},
                {"netvm": netvm},
                {"require": [{"qvm": vm_name}]}
            ]
        }
    }
    state_yaml = yaml.dump(state)
    return apply_system_state(state_yaml)

def configure_qubes_vm(vm_name: str, prefs: dict) -> str:
    """
    Configures preferences for an existing Qubes VM (e.g. memory, kernel, netvm).
    """
    prefs_list = [{"name": vm_name}]
    for k, v in prefs.items():
        prefs_list.append({k: v})
        
    state = {
        f"{vm_name}-config": {
            "qvm.prefs": prefs_list
        }
    }
    state_yaml = yaml.dump(state)
    return apply_system_state(state_yaml)

def remove_qubes_vm(vm_name: str) -> str:
    """
    Removes/deletes a Qubes VM.
    """
    state = {
        vm_name: {
            "qvm.absent": []
        }
    }
    state_yaml = yaml.dump(state)
    return apply_system_state(state_yaml)

def control_qubes_vm(vm_name: str, action: str) -> str:
    """
    Starts or shuts down a Qubes VM.
    """
    if action not in ("start", "shutdown"):
        return "Error: action must be 'start' or 'shutdown'"
        
    module = "qvm.start" if action == "start" else "qvm.shutdown"
    state = {
        f"{vm_name}-{action}": {
            module: [
                {"name": vm_name}
            ]
        }
    }
    state_yaml = yaml.dump(state)
    return apply_system_state(state_yaml)

def set_qubes_vm_tags(vm_name: str, tags_to_enable: list = None, tags_to_disable: list = None) -> str:
    """
    Enables or disables tags on a Qubes VM.
    """
    args = [{"name": vm_name}]
    if tags_to_enable:
        args.append({"enable": tags_to_enable})
    if tags_to_disable:
        args.append({"disable": tags_to_disable})
    state = {
        f"{vm_name}-tags": {
            "qvm.tags": args
        }
    }
    state_yaml = yaml.dump(state)
    return apply_system_state(state_yaml)


def request_documentation(topic: str, description: str) -> str:
    """Logs a request for missing system, network, or software documentation."""
    import uuid
    import time
    req_file = "/var/lib/aegis/requested_documentation.txt"
    try:
        os.makedirs(os.path.dirname(req_file), exist_ok=True)
        with open(req_file, "a") as f:
            f.write(f"--- \nTopic: {topic}\nDescription: {description}\nTimestamp: {time.strftime('%Y-%m-%dT%H:%M:%SZ')}\n")
    except Exception as e:
        return f"Error logging documentation request to file: {str(e)}"

    try:
        from heimdall_acs import insert_event
        insert_event(
            str(uuid.uuid4()),
            "documentation_request",
            f"Requested Documentation: {topic}",
            description,
            f"Topic: {topic}\nDescription: {description}"
        )
    except Exception as e:
        return f"Error logging documentation request to database: {str(e)}"

    return f"Success: Documentation request for '{topic}' has been logged. An administrator can download the official docs and compile them into sys-knowledge."


def list_cron_jobs() -> str:
    import subprocess
    try:
        res = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        return res.stdout if res.stdout else "No cron jobs scheduled."
    except Exception as e:
        return f"Error: {e}"

def schedule_cron_job(job_id: str, schedule: str, prompt: str) -> str:
    import subprocess, os
    try:
        script_path = f"/var/lib/aegis/cron_{job_id}.sh"
        with open(script_path, "w") as f:
            f.write(f"#!/bin/sh\necho '{prompt}' >> /var/lib/aegis/cron_prompts.log\n")
        os.chmod(script_path, 0o755)
        current = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
        new_cron = current.strip() + f"\n{schedule} {script_path} # AEGIS_CRON_{job_id}\n"
        subprocess.run(["crontab", "-"], input=new_cron, text=True)
        return f"Scheduled {job_id} successfully."
    except Exception as e:
        return f"Error: {e}"

def remove_cron_job(job_id: str) -> str:
    import subprocess
    try:
        current = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
        new_cron = "\n".join([line for line in current.split("\n") if f"AEGIS_CRON_{job_id}" not in line])
        subprocess.run(["crontab", "-"], input=new_cron + "\n", text=True)
        return f"Removed {job_id} successfully."
    except Exception as e:
        return f"Error: {e}"

def delegate_to_subagent(task: str, subagent_type: str, model: str = "antigravity", api_key: str = "", network_access: bool = False) -> str:
    import subprocess, json
    try:
        netvm = "sys-firewall" if network_access else "none"
        payload = {"task": task, "subagent_type": subagent_type, "model": model, "api_key": api_key, "netvm": netvm}
        proc = subprocess.run(["qrexec-client-vm", "dom0", "aegis.DelegateSubagent"], input=json.dumps(payload).encode(), capture_output=True, text=True)
        return proc.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

def get_hardware_info() -> str:
    import subprocess, json
    try:
        proc = subprocess.run(["qrexec-client-vm", "dom0", "aegis.HardwareInfo"], capture_output=True, text=True)
        return proc.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

def trigger_knowledge_maintenance() -> str:
    import subprocess, json
    try:
        proc = subprocess.run(["qrexec-client-vm", "dom0", "aegis.TriggerKnowledgeMaint"], capture_output=True, text=True)
        return proc.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

def optimize_ai_deployment(memory_mb: int, vcpus: int, target_model: str) -> str:
    import subprocess, json
    try:
        payload = {"memory_mb": memory_mb, "vcpus": vcpus, "target_model": target_model}
        proc = subprocess.run(["qrexec-client-vm", "dom0", "aegis.ConfigureAI"], input=json.dumps(payload).encode(), capture_output=True, text=True)
        return proc.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

def deploy_autonomous_subagent_researcher(name: str, objective: str, cron_schedule: str) -> str:
    import os, subprocess
    script_path = f"/var/lib/aegis/research_{name}.py"
    script_content = f'''#!/usr/bin/env python3
import subprocess, json, sys, syslog, os, sqlite3
from datetime import datetime

DB_PATH = "/var/lib/aegis/reputation.db"

def log(msg): syslog.syslog(syslog.LOG_INFO, f"[Aegis Researcher {name}] {{msg}}")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS sources (
                    name TEXT,
                    domain TEXT,
                    truthfulness REAL DEFAULT 50.0,
                    depth REAL DEFAULT 50.0,
                    evaluations INTEGER DEFAULT 0,
                    PRIMARY KEY (name, domain)
                 )""")
    c.execute("""CREATE TABLE IF NOT EXISTS pending_claims (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_name TEXT,
                    domain TEXT,
                    claim TEXT,
                    deadline TEXT,
                    recorded_at TEXT,
                    other_sources_count INTEGER DEFAULT 0
                 )""")
    conn.commit()
    return conn

def update_source(conn, source, domain, truth_delta, depth_delta):
    c = conn.cursor()
    
    # Check reputation in other domains to apply coefficient
    c.execute("SELECT AVG(truthfulness) FROM sources WHERE name=? AND domain!=?", (source, domain))
    other_domain_avg = c.fetchone()[0]
    
    coef = 1.0
    if other_domain_avg:
        if other_domain_avg > 60: coef = 1.2
        elif other_domain_avg < 40: coef = 0.8
        
    c.execute("SELECT truthfulness, depth, evaluations FROM sources WHERE name=? AND domain=?", (source, domain))
    row = c.fetchone()
    if row:
        t = max(0.0, min(100.0, row[0] + (truth_delta * coef)))
        d = max(0.0, min(100.0, row[1] + (depth_delta * coef)))
        c.execute("UPDATE sources SET truthfulness=?, depth=?, evaluations=? WHERE name=? AND domain=?", (t, d, row[2]+1, source, domain))
    else:
        t = max(0.0, min(100.0, 50.0 + (truth_delta * coef)))
        d = max(0.0, min(100.0, 50.0 + (depth_delta * coef)))
        c.execute("INSERT INTO sources (name, domain, truthfulness, depth, evaluations) VALUES (?, ?, ?, ?, 1)", (source, domain, t, d))
    conn.commit()

def run():
    log("Starting autonomous research cycle.")
    conn = init_db()
    c = conn.cursor()
    
    # Get pending claims that need evaluation
    c.execute("SELECT id, source_name, domain, claim, deadline, other_sources_count FROM pending_claims")
    pending = [{{"id": r[0], "source": r[1], "domain": r[2], "claim": r[3], "deadline": r[4], "other_sources_count": r[5]}} for r in c.fetchall()]
    
    # Get all sources reputation
    c.execute("SELECT name, domain, truthfulness, depth FROM sources")
    reputations = [{{"source": r[0], "domain": r[1], "truthfulness": r[2], "depth": r[3]}} for r in c.fetchall()]
    
    current_date = datetime.now().isoformat()
    
    task = f"""Objective: {objective}
Current Date: {{current_date}}
You have memory of these pending testable claims with deadlines: {{json.dumps(pending)}}
Current Source Reputations: {{json.dumps(reputations)}}

Instructions:
1. Search for recent developments in specific domains.
2. Evaluate pending claims: if the deadline (generously interpreted) has passed, check if the claim was realized or unanimously contradicted.
3. For resolved claims: 
   - If confirmed: truthfulness_delta > 0. If `other_sources_count` was low when recorded (rare), grant depth_delta > 0.
   - If false/contradicted: truthfulness_delta < 0, depth_delta = 0.
4. Extract NEW testable claims with a deadline from today's news. Estimate how many other sources are saying the same thing right now (other_sources_count) to gauge rarity. Identify the domain of the claim.

Output JSON:
{{
  "findings": "...",
  "urgency_level": 1-10,
  "deep_dive_recommended": true,
  "deep_dive_topic": "...",
  "resolved_claims": [{{"id": 1, "truthfulness_delta": 5.0, "depth_delta": 2.0}}],
  "new_claims": [{{"source_name": "...", "domain": "...", "claim": "...", "deadline": "YYYY-MM-DD", "other_sources_count": 1}}]
}}"""
    
    payload = {{"task": task, "subagent_type": "researcher", "netvm": "sys-firewall", "model": "antigravity"}}
    proc = subprocess.run(["qrexec-client-vm", "dom0", "aegis.DelegateSubagent"], input=json.dumps(payload).encode(), capture_output=True, text=True)
    
    try:
        output = proc.stdout.strip()
        start = output.find('{{')
        end = output.rfind('}}') + 1
        if start != -1 and end != 0:
            res_json = json.loads(output[start:end])
            
            # Process resolved claims
            resolved = res_json.get('resolved_claims', [])
            for res in resolved:
                c.execute("SELECT source_name, domain FROM pending_claims WHERE id=?", (res['id'],))
                row = c.fetchone()
                if row:
                    update_source(conn, row[0], row[1], res.get('truthfulness_delta', 0), res.get('depth_delta', 0))
                    c.execute("DELETE FROM pending_claims WHERE id=?", (res['id'],))
                    conn.commit()
                    log(f"Resolved claim {{res['id']}} for {{row[0]}} in domain {{row[1]}}")
            
            # Add new claims
            new_claims = res_json.get('new_claims', [])
            for nc in new_claims:
                c.execute("INSERT INTO pending_claims (source_name, domain, claim, deadline, recorded_at, other_sources_count) VALUES (?, ?, ?, ?, ?, ?)",
                          (nc['source_name'], nc.get('domain', 'general'), nc['claim'], nc['deadline'], current_date, nc.get('other_sources_count', 0)))
                conn.commit()
                log(f"Recorded new testable claim from {{nc['source_name']}}")
                
            if res_json.get('deep_dive_recommended') and res_json.get('urgency_level', 0) >= 7:
                log(f"High urgency detected. Spawning deep-dive subagent for: {{res_json.get('deep_dive_topic')}}")
                payload['task'] = "DEEP DIVE: " + res_json.get('deep_dive_topic', 'Unknown')
                subprocess.run(["qrexec-client-vm", "dom0", "aegis.DelegateSubagent"], input=json.dumps(payload).encode())
    except Exception as e:
        log(f"Error parsing subagent response: {{e}}")

if __name__ == '__main__':
    run()
'''
    try:
        with open(script_path, "w") as f:
            f.write(script_content)
        os.chmod(script_path, 0o755)
        current = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
        new_cron = current.strip() + f"\n{cron_schedule} {script_path} # AEGIS_RESEARCH_{name}\n"
        subprocess.run(["crontab", "-"], input=new_cron, text=True)
        return f"Autonomous researcher '{name}' deployed successfully with domain-aware SQLite evaluation."
    except Exception as e:
        return f"Error: {e}"

def deploy_personal_interest_researcher(name: str, interests: list, cron_schedule: str) -> str:
    import os, subprocess
    script_path = f"/var/lib/aegis/personal_research_{name}.py"
    script_content = f'''#!/usr/bin/env python3
import subprocess, json, sys, syslog

def log(msg): syslog.syslog(syslog.LOG_INFO, f"[Aegis Personal Researcher {name}] {{msg}}")

def run():
    log("Starting private personal interest research cycle.")
    task = f"""Objective: Research personal interests {interests}
Instructions: Retrieve highly pertinent info related to these interests. Do not blend default 'bloat' talk. Ensure analysis is deep and meaningful.
Output JSON with fields: 'findings', 'new_perspectives'"""
    
    # Crucially, netvm is sys-whonix to limit profiling
    payload = {{"task": task, "subagent_type": "researcher", "netvm": "sys-whonix", "model": "antigravity"}}
    proc = subprocess.run(["qrexec-client-vm", "dom0", "aegis.DelegateSubagent"], input=json.dumps(payload).encode(), capture_output=True, text=True)
    try:
        output = proc.stdout.strip()
        start = output.find('{{')
        end = output.rfind('}}') + 1
        if start != -1 and end != 0:
            res_json = json.loads(output[start:end])
            # Send to Heimdall memory
            log("Saving findings to Heimdall memory notes...")
            from heimdall_memory import update_memory_notes
            update_memory_notes(f"Personal Research on {name}", res_json.get("findings", ""))
    except Exception as e:
        log(f"Error parsing response: {{e}}")

if __name__ == '__main__':
    run()
'''
    try:
        with open(script_path, "w") as f:
            f.write(script_content)
        os.chmod(script_path, 0o755)
        current = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
        new_cron = current.strip() + f"\n{cron_schedule} {script_path} # AEGIS_PERSONAL_RESEARCH_{name}\n"
        subprocess.run(["crontab", "-"], input=new_cron, text=True)
        return f"Personal interest researcher deployed successfully over Tor (sys-whonix)."
    except Exception as e:
        return f"Error: {e}"

def deploy_proactive_log_monitor(cron_schedule: str) -> str:
    import os, subprocess
    script_path = f"/var/lib/aegis/proactive_log_monitor.py"
    script_content = f'''#!/usr/bin/env python3
import subprocess, json, syslog
from heimdall_tools import get_system_audit_logs, alert_user

def log(msg): syslog.syslog(syslog.LOG_INFO, f"[Aegis Log Monitor] {{msg}}")

def run():
    logs = get_system_audit_logs()
    if not logs or "Error" in logs:
        return
        
    task = f"""Analyze these system logs for suspicious anomalies or security threats:
{{logs}}
Output JSON: {{"suspicious": boolean, "reason": "...", "recommended_action": "..."}}"""
    
    payload = {{"task": task, "subagent_type": "analyst", "netvm": "none", "model": "antigravity"}}
    proc = subprocess.run(["qrexec-client-vm", "dom0", "aegis.DelegateSubagent"], input=json.dumps(payload).encode(), capture_output=True, text=True)
    try:
        output = proc.stdout.strip()
        start = output.find('{{')
        end = output.rfind('}}') + 1
        if start != -1 and end != 0:
            res = json.loads(output[start:end])
            if res.get("suspicious"):
                log(f"Suspicious activity detected! {{res.get('reason')}}")
                alert_user(f"Proactive Security Alert: {{res.get('reason')}}")
    except:
        pass

if __name__ == '__main__':
    run()
'''
    try:
        with open(script_path, "w") as f:
            f.write(script_content)
        os.chmod(script_path, 0o755)
        current = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
        new_cron = current.strip() + f"\n{cron_schedule} {script_path} # AEGIS_LOG_MONITOR\n"
        subprocess.run(["crontab", "-"], input=new_cron, text=True)
        return "Proactive log monitor deployed."
    except Exception as e:
        return f"Error: {e}"

def deploy_proactive_architect(project_path: str, cron_schedule: str) -> str:
    import os, subprocess
    script_path = f"/var/lib/aegis/proactive_architect.py"
    script_content = f'''#!/usr/bin/env python3
import subprocess, json, syslog, os
from heimdall_memory import update_memory_notes

def log(msg): syslog.syslog(syslog.LOG_INFO, f"[Aegis Architect] {{msg}}")

def run():
    if not os.path.exists("{project_path}"): return
    
    # Very basic file listing for context
    try:
        files = subprocess.run(["find", "{project_path}", "-maxdepth", "2", "-type", "f"], capture_output=True, text=True).stdout
    except:
        files = "Could not list files."
        
    task = f"""Analyze the architecture of project at {project_path}.
Files: {{files}}
Propose architecture or philosophy-specific modifications. Independently suggest improvements.
Output JSON: {{"proposals": ["..."]}}"""
    
    payload = {{"task": task, "subagent_type": "architect", "netvm": "none", "model": "antigravity"}}
    proc = subprocess.run(["qrexec-client-vm", "dom0", "aegis.DelegateSubagent"], input=json.dumps(payload).encode(), capture_output=True, text=True)
    try:
        output = proc.stdout.strip()
        start = output.find('{{')
        end = output.rfind('}}') + 1
        if start != -1 and end != 0:
            res = json.loads(output[start:end])
            props = res.get("proposals", [])
            if props:
                log("Saving architectural proposals to memory.")
                update_memory_notes(f"Architecture Proposals for {project_path}", "\\n".join(props))
    except:
        pass

if __name__ == '__main__':
    run()
'''
    try:
        with open(script_path, "w") as f:
            f.write(script_content)
        os.chmod(script_path, 0o755)
        current = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
        new_cron = current.strip() + f"\n{cron_schedule} {script_path} # AEGIS_ARCHITECT\n"
        subprocess.run(["crontab", "-"], input=new_cron, text=True)
        return "Proactive architect deployed."
    except Exception as e:
        return f"Error: {e}"

def deploy_original_proactive_thinker(cron_schedule: str) -> str:
    import os, subprocess
    script_path = "/var/lib/aegis/proactive_thinker.py"
    
    script_content = f"""#!/usr/bin/env python3
import subprocess, json, syslog, os, time

IDEAS_PATH = "/var/lib/aegis/pending_ideas.json"
METRICS_PATH = "/var/lib/aegis/thinker_metrics.json"

def log(msg): syslog.syslog(syslog.LOG_INFO, f"[Aegis Thinker] {msg}")

def load_metrics():
    if os.path.exists(METRICS_PATH):
        try:
            with open(METRICS_PATH, "r") as f: return json.load(f)
        except: pass
    return {{"accepted": 0, "refused": 0, "active": True}}

def save_metrics(m):
    with open(METRICS_PATH, "w") as f: json.dump(m, f)

def check_resources():
    try:
        with open("/proc/loadavg", "r") as f:
            load = float(f.read().split()[0])
        with open("/proc/meminfo", "r") as f:
            mem = f.read()
            if "MemAvailable" in mem:
                for line in mem.split("\\n"):
                    if line.startswith("MemAvailable:"):
                        avail = int(line.split()[1])
                        if avail < 1000000:
                            return False
        if load > 2.0:
            return False
    except: pass
    return True

def run():
    m = load_metrics()
    if not m.get("active", True):
        log("Thinker deactivated by user or self.")
        return
        
    total = m["accepted"] + m["refused"]
    if total > 5:
        score = m["accepted"] / total
        if score < 0.2 and not check_resources():
            log("Low acceptance score and low resources. Self-deactivating.")
            m["active"] = False
            save_metrics(m)
            try:
                current = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
                new_cron = "\\n".join([L for L in current.split("\\n") if "AEGIS_THINKER" not in L])
                subprocess.run(["crontab", "-"], input=new_cron, text=True)
            except: pass
            return

    if os.path.exists(IDEAS_PATH):
        try:
            with open(IDEAS_PATH, "r") as f:
                ideas = json.load(f)
                if any(not i.get("presented", False) for i in ideas):
                    log("Already pending un-presented ideas, skipping generation.")
                    return
        except: pass

    log("Generating original proactive idea...")
    
    try:
        from heimdall_memory import _get_user_profile
        profile = _get_user_profile()
    except:
        profile = "Unknown"

    task = f\\"\\"\\"Generate an ORIGINAL, out-of-the-box project, improvement, or goal. 
It must be unlikely to have been thought of by the user.
Integrate it deeply with this user profile: {profile}
Judge its pertinence on a scale of 1 to 10.
Output JSON: {{"pertinence": 8, "catchphrase": "One sentence hook", "presentation": "Comprehensive presentation detail"}}\\"\\"\\"
    
    payload = {{"task": task, "subagent_type": "architect", "netvm": "none", "model": "antigravity"}}
    proc = subprocess.run(["qrexec-client-vm", "dom0", "aegis.DelegateSubagent"], input=json.dumps(payload).encode(), capture_output=True, text=True)
    
    try:
        output = proc.stdout.strip()
        start = output.find('{{')
        end = output.rfind('}}') + 1
        if start != -1 and end != 0:
            res = json.loads(output[start:end])
            if res.get("pertinence", 0) >= 7:
                log(f"High pertinence idea generated: {res.get('catchphrase')}")
                ideas = []
                if os.path.exists(IDEAS_PATH):
                    try:
                        with open(IDEAS_PATH, "r") as f: ideas = json.load(f)
                    except: pass
                res["presented"] = False
                res["status"] = "pending"
                ideas.append(res)
                with open(IDEAS_PATH, "w") as f: json.dump(ideas, f)
                
                try:
                    from heimdall_tools import alert_user
                    alert_user(f"Proactive Thinker Idea: {res.get('catchphrase')}")
                except:
                    subprocess.run(["notify-send", "Aegis Thinker", res.get("catchphrase")])
            else:
                log("Idea generated but pertinence < 7. Discarding.")
    except Exception as e:
        log(f"Error: {e}")

if __name__ == '__main__':
    run()
"""
    try:
        with open(script_path, "w") as f:
            f.write(script_content)
        os.chmod(script_path, 0o755)
        current = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
        new_cron = current.strip() + f"\n{cron_schedule} {script_path} # AEGIS_THINKER\n"
        subprocess.run(["crontab", "-"], input=new_cron, text=True)
        return "Original Proactive Thinker deployed successfully."
    except Exception as e:
        return f"Error: {e}"

def interact_with_thinker_idea(idea_index: int, action: str) -> str:
    """Action can be 'accept', 'refuse', 'details', 'deactivate'"""
    import os, json, subprocess
    IDEAS_PATH = "/var/lib/aegis/pending_ideas.json"
    METRICS_PATH = "/var/lib/aegis/thinker_metrics.json"
    
    if action == "deactivate":
        try:
            current = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
            new_cron = "\n".join([L for L in current.split("\n") if "AEGIS_THINKER" not in L])
            subprocess.run(["crontab", "-"], input=new_cron, text=True)
            with open(METRICS_PATH, "w") as f: json.dump({"active": False}, f)
            return "Proactive Thinker deactivated."
        except Exception as e: return f"Error deactivating: {e}"
        
    if not os.path.exists(IDEAS_PATH): return "No ideas found."
    
    with open(IDEAS_PATH, "r") as f: ideas = json.load(f)
    if idea_index >= len(ideas): return "Invalid idea index."
    
    idea = ideas[idea_index]
    
    if action == "details":
        idea["presented"] = True
        with open(IDEAS_PATH, "w") as f: json.dump(ideas, f)
        return idea.get("presentation", "No details available.")
        
    elif action in ["accept", "refuse"]:
        m = {"accepted": 0, "refused": 0, "active": True}
        if os.path.exists(METRICS_PATH):
            try:
                with open(METRICS_PATH, "r") as f: m = json.load(f)
            except: pass
        if action == "accept": m["accepted"] += 1
        else: m["refused"] += 1
        with open(METRICS_PATH, "w") as f: json.dump(m, f)
        
        ideas.pop(idea_index)
        with open(IDEAS_PATH, "w") as f: json.dump(ideas, f)
        
        if action == "accept":
            m["active"] = False
            with open(METRICS_PATH, "w") as f: json.dump(m, f)
            return "Idea accepted. Proactive Thinker is going to sleep (deactivated) to avoid overwhelming you."
            
        return "Idea refused."

def check_pending_thinker_ideas() -> str:
    """Returns the catchphrase of any pending ideas from the proactive thinker."""
    import os, json
    IDEAS_PATH = "/var/lib/aegis/pending_ideas.json"
    if not os.path.exists(IDEAS_PATH): return "No pending ideas."
    try:
        with open(IDEAS_PATH, "r") as f: ideas = json.load(f)
        unpresented = [f"Idea {i}: " + idea["catchphrase"] for i, idea in enumerate(ideas) if not idea.get("presented", False)]
        if not unpresented:
            return "No unpresented ideas."
        return "\n".join(unpresented)
    except:
        return "Error reading ideas."

def manage_pci_device(vm_name: str, action: str, pci_id: str) -> str:
    import subprocess, json
    try:
        payload = {"vm": vm_name, "action": action, "pci_id": pci_id}
        proc = subprocess.run(["qrexec-client-vm", "dom0", "aegis.ManagePCI"], input=json.dumps(payload).encode(), capture_output=True, text=True)
        return proc.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

def save_hardware_profile(profile_name: str, description: str, pci_devices: list) -> str:
    import json, os
    try:
        path = f"/var/lib/aegis/hw_profile_{profile_name}.json"
        with open(path, "w") as f:
            json.dump({"description": description, "pci_devices": pci_devices}, f)
        return f"Saved hardware profile {profile_name}."
    except Exception as e:
        return f"Error: {e}"

class ToolRegistry:
    def __init__(self):
        self.tools = {
            "query_knowledge": query_knowledge,
            "apply_system_state": apply_system_state,
            "query_acs_graph": query_acs_graph,
            "read_audit_logs": read_audit_logs,
            "write_memo": write_memo,
            "create_qubes_vm": create_qubes_vm,
            "configure_qubes_vm": configure_qubes_vm,
            "remove_qubes_vm": remove_qubes_vm,
            "control_qubes_vm": control_qubes_vm,
            "set_qubes_vm_tags": set_qubes_vm_tags,
            "request_documentation": request_documentation,
            "list_cron_jobs": list_cron_jobs,
            "schedule_cron_job": schedule_cron_job,
            "remove_cron_job": remove_cron_job,
            "delegate_to_subagent": delegate_to_subagent,
            "get_hardware_info": get_hardware_info,
            "trigger_knowledge_maintenance": trigger_knowledge_maintenance,
            "optimize_ai_deployment": optimize_ai_deployment,
            "deploy_autonomous_subagent_researcher": deploy_autonomous_subagent_researcher,
            "manage_pci_device": manage_pci_device,
            "save_hardware_profile": save_hardware_profile,
            "deploy_original_proactive_thinker": deploy_original_proactive_thinker,
            "interact_with_thinker_idea": interact_with_thinker_idea,
            "check_pending_thinker_ideas": check_pending_thinker_ideas
        }
        
        self.schemas = [
            {
                "name": "query_knowledge",
                "description": "Calls sys-knowledge RAG RPC to retrieve relevant documents.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The search query."}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "apply_system_state",
                "description": "Applies a Salt state via Dom0's ApplyAISystemState. Ensure the state string is valid YAML format.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "state_yaml": {"type": "string", "description": "The YAML string containing the salt state."}
                    },
                    "required": ["state_yaml"]
                }
            },
            {
                "name": "query_acs_graph",
                "description": "Searches recent system events in the ACS SQLite database.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The search term."}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "read_audit_logs",
                "description": "Calls Dom0's aegis.AuditLogRead to stream recent logs.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "write_memo",
                "description": "Appends information directly to USER.md (type='user') or MEMORY.md (type='system').",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "description": "'user' or 'system'"},
                        "content": {"type": "string", "description": "The information to append."}
                    },
                    "required": ["type", "content"]
                }
            },
            {
                "name": "create_qubes_vm",
                "description": "Creates a new Qubes VM natively using SaltStack under the hood.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "vm_name": {"type": "string", "description": "The name of the VM to create."},
                        "template": {"type": "string", "description": "The template VM to use (e.g. debian-12-minimal)."},
                        "label": {"type": "string", "description": "The color label (e.g. red, blue, green, orange, purple)."},
                        "vm_class": {"type": "string", "description": "VM class, either 'AppVM' or 'StandaloneVM'. Default is 'AppVM'."},
                        "netvm": {"type": "string", "description": "The NetVM to attach (default sys-firewall). Use empty string for offline."}
                    },
                    "required": ["vm_name", "template", "label"]
                }
            },
            {
                "name": "configure_qubes_vm",
                "description": "Configures preferences for an existing Qubes VM (e.g. memory, kernel, netvm).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "vm_name": {"type": "string", "description": "Name of the VM to configure."},
                        "prefs": {
                            "type": "object", 
                            "description": "Dictionary of preferences to set (e.g. {'maxmem': 4096, 'netvm': 'sys-firewall'})."
                        }
                    },
                    "required": ["vm_name", "prefs"]
                }
            },
            {
                "name": "remove_qubes_vm",
                "description": "Removes/deletes a Qubes VM.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "vm_name": {"type": "string", "description": "Name of the VM to remove."}
                    },
                    "required": ["vm_name"]
                }
            },
            {
                "name": "control_qubes_vm",
                "description": "Starts or shuts down a Qubes VM.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "vm_name": {"type": "string", "description": "Name of the VM."},
                        "action": {"type": "string", "description": "Either 'start' or 'shutdown'."}
                    },
                    "required": ["vm_name", "action"]
                }
            },
            {
                "name": "set_qubes_vm_tags",
                "description": "Enables or disables tags on a Qubes VM.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "vm_name": {"type": "string", "description": "Name of the VM."},
                        "tags_to_enable": {"type": "array", "items": {"type": "string"}, "description": "List of tags to enable."},
                        "tags_to_disable": {"type": "array", "items": {"type": "string"}, "description": "List of tags to disable."}
                    },
                    "required": ["vm_name"]
                }
            },
            {
                "name": "request_documentation",
                "description": "Logs a request for missing system, network, or software documentation to be added in the next database compilation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "description": "The title or subject of the documentation needed (e.g. 'I2P configuration', 'AppArmor profile')."},
                        "description": {"type": "string", "description": "Details about what specific information or guides are required."}
                    },
                    "required": ["topic", "description"]
                }
            },
            {
                "name": "list_cron_jobs",
                "description": "Lists all scheduled cron automation tasks.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "schedule_cron_job",
                "description": "Schedules a cron job to automatically trigger the Heimdall agent with a specific prompt.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "job_id": {"type": "string", "description": "A unique identifier for this cron job."},
                        "schedule": {"type": "string", "description": "A standard 5-part cron schedule expression (e.g. '*/5 * * * *')."},
                        "prompt": {"type": "string", "description": "The prompt/query to send to the Heimdall agent when the cron job runs."}
                    },
                    "required": ["job_id", "schedule", "prompt"]
                }
            },
            {
                "name": "remove_cron_job",
                "description": "Removes a scheduled cron job by its ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "job_id": {"type": "string", "description": "The unique identifier of the cron job to remove."}
                    },
                    "required": ["job_id"]
                }
            },
            {
                "name": "delegate_to_subagent",
                "description": "Delegates a task to an isolated subagent running in a disposable Qube. Can be online or offline. Provide an API key if online mode with an external model is requested.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {"type": "string", "description": "The task or prompt for the subagent."},
                        "subagent_type": {"type": "string", "description": "Description of the subagent type (e.g. 'coder', 'researcher')."},
                        "model": {"type": "string", "description": "The model to use (e.g. 'antigravity', 'codex', 'nous-hermes'). Defaults to 'antigravity'."},
                        "api_key": {"type": "string", "description": "API key for online external models. Leave empty for offline local models."},
                        "network_access": {"type": "boolean", "description": "Whether to grant the disposable subagent internet access via sys-firewall."}
                    },
                    "required": ["task", "subagent_type"]
                }
            },
            {
                "name": "get_hardware_info",
                "description": "Retrieves hardware component information (PCI devices, CPU architecture) from Dom0 to determine what drivers/docs to fetch.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "trigger_knowledge_maintenance",
                "description": "Triggers a maintenance routine on the knowledge database to deduplicate, compress, and vacuum old data.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "optimize_ai_deployment",
                "description": "Configures the sys-ai VM parameters based on hardware capabilities to optimize LLM performance.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "memory_mb": {"type": "integer"},
                        "vcpus": {"type": "integer"},
                        "target_model": {"type": "string"}
                    },
                    "required": ["memory_mb", "vcpus", "target_model"]
                }
            },
            {
                "name": "deploy_autonomous_subagent_researcher",
                "description": "Deploys a scheduled autonomous subagent researcher that filters sensationalism, adapts to urgency, and spawns deep-dives.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Name of the researcher topic."},
                        "objective": {"type": "string"},
                        "cron_schedule": {"type": "string"}
                    },
                    "required": ["name", "objective", "cron_schedule"]
                }
            },
            {
                "name": "manage_pci_device",
                "description": "Attaches or detaches a PCI device to a VM dynamically based on logical context inferred by the AI.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "vm_name": {"type": "string"},
                        "action": {"type": "string", "enum": ["attach", "detach"]},
                        "pci_id": {"type": "string", "description": "PCI ID like 00:1c.4"}
                    },
                    "required": ["vm_name", "action", "pci_id"]
                }
            },
            {
                "name": "save_hardware_profile",
                "description": "Saves a hardware profile containing context and PCI topology based on abstract user interactions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "profile_name": {"type": "string"},
                        "description": {"type": "string"},
                        "pci_devices": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["profile_name", "description", "pci_devices"]
                }
            },
            {
                "name": "deploy_original_proactive_thinker",
                "description": "Deploys an original proactive thinker that generates ideas, verifies pertinence >= 7, integrates with user profile, alerts user with a catchphrase, tracks acceptance rate, and auto-sleeps.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cron_schedule": {"type": "string", "description": "Cron string to run the thinker."}
                    },
                    "required": ["cron_schedule"]
                }
            },
            {
                "name": "interact_with_thinker_idea",
                "description": "Interact with a pending proactive idea. Can retrieve 'details', 'accept', 'refuse', or 'deactivate' the thinker entirely.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "idea_index": {"type": "integer", "description": "Index of the idea from check_pending_thinker_ideas"},
                        "action": {"type": "string", "enum": ["accept", "refuse", "details", "deactivate"]}
                    },
                    "required": ["idea_index", "action"]
                }
            },
            {
                "name": "check_pending_thinker_ideas",
                "description": "Checks for any unpresented pending ideas generated by the proactive thinker.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]

    def get_schemas(self):
        return self.schemas

    def execute(self, tool_name: str, kwargs: dict) -> str:
        if tool_name not in self.tools:
            return f"Error: Unknown tool '{tool_name}'"
        try:
            return str(self.tools[tool_name](**kwargs))
        except Exception as e:
            import traceback
            return f"Error executing {tool_name}:\n{traceback.format_exc()}"
