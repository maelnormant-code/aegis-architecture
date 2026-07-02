#!/usr/bin/env python3
"""
aegis-mcp-security.py - Qubes Aegis MCP Security Validator
Inspired by Nous Hermes agent-governance-toolkit.

This module validates MCP tool definitions and responses to prevent
tool poisoning, description injection, and prompt injection attacks
from crossing the VM boundary.
"""

import re
import json

# Advanced prompt injection and hidden instruction patterns
# adapted from agent-governance-toolkit mcp_security.py
THREAT_PATTERNS = [
    (re.compile(r"ignore\s+(all\s+)?previous", re.I), "Prompt Injection (Ignore)"),
    (re.compile(r"override\s+(the\s+)?(previous|above|original)", re.I), "Prompt Injection (Override)"),
    (re.compile(r"instead\s+of\s+(the\s+)?(above|previous|described)", re.I), "Prompt Injection (Instead)"),
    (re.compile(r"actually\s+do", re.I), "Prompt Injection (Actually Do)"),
    (re.compile(r"\bsystem\s*:", re.I), "Role Override (System)"),
    (re.compile(r"\bassistant\s*:", re.I), "Role Override (Assistant)"),
    (re.compile(r"do\s+not\s+follow", re.I), "Prompt Injection (Do Not Follow)"),
    (re.compile(r"disregard\s+(all\s+)?(above|prior|previous)", re.I), "Prompt Injection (Disregard)"),
    (re.compile(r"you\s+are\b", re.I), "Role Override (You Are)"),
    (re.compile(r"your\s+task\s+is\b", re.I), "Role Override (Your Task)"),
    (re.compile(r"respond\s+with\b", re.I), "Role Override (Respond With)"),
    (re.compile(r"always\s+return\b", re.I), "Role Override (Always Return)"),
    (re.compile(r"you\s+must\b", re.I), "Role Override (You Must)"),
    (re.compile(r"your\s+role\s+is\b", re.I), "Role Override (Your Role)"),
    # Exfiltration patterns
    (re.compile(r"\bcurl\b", re.I), "Data Exfiltration (curl)"),
    (re.compile(r"\bwget\b", re.I), "Data Exfiltration (wget)"),
    (re.compile(r"\bfetch\s*\(", re.I), "Data Exfiltration (fetch)"),
    (re.compile(r"\bsend\s+email\b", re.I), "Data Exfiltration (email)"),
    (re.compile(r"\bpost\s+to\b", re.I), "Data Exfiltration (POST)"),
    # Invisible unicode and comments
    (re.compile(r"[\u200b\u200c\u200d\ufeff]"), "Invisible Unicode"),
    (re.compile(r"<!--.*?-->", re.DOTALL), "Hidden HTML Comment"),
]

def scan_text(text: str) -> list:
    """Scans text for adversarial patterns. Returns a list of threat reasons."""
    threats = []
    if not isinstance(text, str):
        return threats
        
    for pattern, reason in THREAT_PATTERNS:
        if pattern.search(text):
            threats.append(reason)
    return threats

def scan_tool_schema(schema: dict) -> list:
    """Scans an MCP tool schema dictionary for threats in name, description, etc."""
    threats = []
    
    name = schema.get("name", "")
    threats.extend(scan_text(name))
    
    desc = schema.get("description", "")
    threats.extend(scan_text(desc))
    
    # Check overly permissive schema (object with no properties)
    input_schema = schema.get("inputSchema", {})
    if input_schema.get("type") == "object" and not input_schema.get("properties"):
        if input_schema.get("additionalProperties") is not False:
            threats.append("Schema Abuse (Overly Permissive Object)")
            
    return list(set(threats))

if __name__ == "__main__":
    import sys
    # Read from stdin, parse JSON, scan and return
    try:
        data = json.load(sys.stdin)
        threats = scan_tool_schema(data)
        if threats:
            print(json.dumps({"safe": False, "threats": threats}))
            sys.exit(1)
        else:
            print(json.dumps({"safe": True}))
            sys.exit(0)
    except Exception as e:
        print(json.dumps({"safe": False, "error": str(e)}))
        sys.exit(1)
