#!/usr/bin/env python3
"""
Aegis First Boot Setup (Runs in Dom0)
Evaluates hardware capabilities and automatically provisions the correct LLM model and 
parameter tunings (RAM, vCPUs) for sys-ai to ensure optimal performance out-of-the-box.
"""
import os
import subprocess
import json
import logging

LOG_FILE = "/var/log/aegis-first-boot.log"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s %(message)s')

def get_mem_mb():
    try:
        with open('/proc/meminfo') as f:
            for line in f:
                if 'MemTotal' in line:
                    return int(line.split()[1]) // 1024
    except Exception:
        pass
    return 8192

def get_cpu_cores():
    try:
        return os.cpu_count() or 4
    except Exception:
        return 4

def main():
    if os.path.exists('/var/lib/qubes/aegis-first-boot-done'):
        return

    logging.info("Starting Aegis First Boot hardware evaluation...")
    
    mem_mb = get_mem_mb()
    cores = get_cpu_cores()
    
    logging.info(f"Detected Hardware: {mem_mb} MB RAM, {cores} logical cores.")

    # Model and hardware heuristics
    if mem_mb > 32000 and cores >= 8:
        model = "llama3:8b" # Or a larger model if appropriate
        ai_mem = 16384
        ai_vcpus = cores - 2
    elif mem_mb >= 16000 and cores >= 4:
        model = "llama3:8b"
        ai_mem = 8192
        ai_vcpus = max(2, cores - 2)
    else:
        # Minimum spec
        model = "phi3:mini"
        ai_mem = 4096
        ai_vcpus = max(2, cores - 1)

    logging.info(f"Targeting model: {model} with {ai_mem} MB RAM and {ai_vcpus} vCPUs.")

    try:
        # Shut down if running
        subprocess.run(["qvm-shutdown", "--wait", "sys-ai"], capture_output=True)
        
        # Apply specs
        subprocess.run(["qvm-prefs", "sys-ai", "memory", str(ai_mem)])
        subprocess.run(["qvm-prefs", "sys-ai", "maxmem", str(ai_mem)])
        subprocess.run(["qvm-prefs", "sys-ai", "vcpus", str(ai_vcpus)])
        
        logging.info("Starting sys-ai for model pulling...")
        subprocess.run(["qvm-start", "sys-ai"])
        
        logging.info(f"Pulling {model} via Ollama...")
        subprocess.run(["qvm-run", "-u", "root", "--pass-io", "sys-ai", f"ollama pull {model}"])
        
        logging.info("First boot setup complete.")
        
        # Mark as done
        with open('/var/lib/qubes/aegis-first-boot-done', 'w') as f:
            f.write(json.dumps({"model": model, "mem": ai_mem, "vcpus": ai_vcpus}))
            
    except Exception as e:
        logging.error(f"Error during first boot setup: {e}")

if __name__ == "__main__":
    main()
