import re

with open('/components/qubes-aegis/sys-copilot/heimdall/heimdall_tools.py', 'r') as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if line.startswith('def deploy_darknet_scout'):
        skip = True
    if skip and line.startswith('def query_knowledge'):
        skip = False
    if not skip:
        new_lines.append(line)

content = "".join(new_lines)

new_functions = '''def deploy_darknet_scout(name: str, network: str, objective: str, cron_schedule: str) -> str:
    """Deploys an anti-censorship autonomous subagent that routes exclusively through darknets."""
    import os, subprocess
    script_path = f"/var/lib/aegis/darknet_scout_{name}.py"
    
    netvm = "sys-whonix"
    if network.lower() == "i2p":
        netvm = "sys-i2p"
        
    script_content = f"""#!/usr/bin/env python3
import subprocess, json, sys, syslog

def log(msg): syslog.syslog(syslog.LOG_INFO, f"[Aegis Darknet Scout {name}] {{msg}}")

def run():
    log(f"Starting darknet ({network}) scout cycle.")
    task = f\\"\\"\\"Objective: {objective}
Instructions: You are operating in a highly policed/liberticide environment. You must use anti-censorship protocols to find free software, uncensored information, or restricted data. 
Be highly stealthy and rely exclusively on onion/hidden services or darknet equivalents if possible. 
Output JSON: {{"findings": "...", "threats_evaded": "..."}}\\"\\"\\"
    
    payload = {{"task": task, "subagent_type": "researcher", "netvm": "{netvm}", "model": "antigravity"}}
    proc = subprocess.run(["qrexec-client-vm", "dom0", "aegis.DelegateSubagent"], input=json.dumps(payload).encode(), capture_output=True, text=True)
    try:
        output = proc.stdout.strip()
        start = output.find('{{')
        end = output.rfind('}}') + 1
        if start != -1 and end != 0:
            res_json = json.loads(output[start:end])
            log("Saving findings to Heimdall memory...")
            from heimdall_memory import update_memory_notes
            update_memory_notes(f"Darknet Scout [{name}] Findings", res_json.get("findings", ""))
    except Exception as e:
        log(f"Error parsing response: {{e}}")

if __name__ == '__main__':
    run()
"""
    try:
        with open(script_path, "w") as f:
            f.write(script_content)
        os.chmod(script_path, 0o755)
        current = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
        new_cron = current.strip() + f"\\n{cron_schedule} {script_path} # AEGIS_DARKNET_{name}\\n"
        subprocess.run(["crontab", "-"], input=new_cron, text=True)
        return f"Darknet scout '{name}' deployed over {netvm} ({network})."
    except Exception as e:
        return f"Error: {e}"

def introspect_self() -> str:
    """Reads Heimdall's own source code to provide self-awareness of its capabilities, limitations, and internal structure."""
    import os
    files = [
        "/components/qubes-aegis/sys-copilot/heimdall/heimdall.py", 
        "/components/qubes-aegis/sys-copilot/heimdall/heimdall_tools.py", 
        "/components/qubes-aegis/sys-copilot/heimdall/heimdall_memory.py"
    ]
    
    knowledge = "Heimdall Self-Awareness Data:\\n"
    for path in files:
        if os.path.exists(path):
            with open(path, "r") as f:
                content = f.read()
                knowledge += f"\\n--- {os.path.basename(path)} ---\\n"
                knowledge += content
    return knowledge

'''

content = content.replace('def query_knowledge', new_functions + 'def query_knowledge')

with open('/components/qubes-aegis/sys-copilot/heimdall/heimdall_tools.py', 'w') as f:
    f.write(content)
