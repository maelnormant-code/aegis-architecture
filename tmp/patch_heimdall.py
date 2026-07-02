import re

with open("/components/qubes-aegis/sys-copilot/heimdall/heimdall_tools.py", "r") as f:
    content = f.read()

funcs = """
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
            f.write(f"#!/bin/sh\\necho '{prompt}' >> /var/lib/aegis/cron_prompts.log\\n")
        os.chmod(script_path, 0o755)
        current = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
        new_cron = current.strip() + f"\\n{schedule} {script_path} # AEGIS_CRON_{job_id}\\n"
        subprocess.run(["crontab", "-"], input=new_cron, text=True)
        return f"Scheduled {job_id} successfully."
    except Exception as e:
        return f"Error: {e}"

def remove_cron_job(job_id: str) -> str:
    import subprocess
    try:
        current = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
        new_cron = "\\n".join([line for line in current.split("\\n") if f"AEGIS_CRON_{job_id}" not in line])
        subprocess.run(["crontab", "-"], input=new_cron + "\\n", text=True)
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
import subprocess, json, sys, syslog

def log(msg): syslog.syslog(syslog.LOG_INFO, f"[Aegis Researcher {name}] {{msg}}")

def run():
    log("Starting autonomous research cycle.")
    task = """Objective: {objective}
Instructions: Search for recent developments. STRICTLY filter out sensationalist sources, hearsay, and propaganda. Use independent analytical judgment. Output JSON with fields: 'findings', 'urgency_level' (1-10), 'deep_dive_recommended' (boolean), 'deep_dive_topic'."""
    
    payload = {{"task": task, "subagent_type": "researcher", "netvm": "sys-firewall", "model": "antigravity"}}
    proc = subprocess.run(["qrexec-client-vm", "dom0", "aegis.DelegateSubagent"], input=json.dumps(payload).encode(), capture_output=True, text=True)
    
    try:
        output = proc.stdout.strip()
        start = output.find('{{')
        end = output.rfind('}}') + 1
        if start != -1 and end != 0:
            res_json = json.loads(output[start:end])
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
        new_cron = current.strip() + f"\\n{cron_schedule} {script_path} # AEGIS_RESEARCH_{name}\\n"
        subprocess.run(["crontab", "-"], input=new_cron, text=True)
        return f"Autonomous researcher '{name}' deployed successfully."
    except Exception as e:
        return f"Error: {e}"

"""

content = content.replace("class ToolRegistry:", funcs + "\\nclass ToolRegistry:")

with open("/components/qubes-aegis/sys-copilot/heimdall/heimdall_tools.py", "w") as f:
    f.write(content)
