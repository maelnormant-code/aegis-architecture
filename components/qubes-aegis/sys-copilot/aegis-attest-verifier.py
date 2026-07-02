#!/usr/bin/env python3
"""aegis-attest-verifier.py — Called by Heimdall before each inference session."""

import json
import subprocess
import syslog
import os
import sys

PINS_FILE = os.getenv("AEGIS_PINS_FILE", "/etc/qubes-aegis/attestation-pins.json")
QUARANTINE_FLAG = os.getenv("AEGIS_QUARANTINE_FLAG", "/run/aegis/sys-ai-quarantine")

def verify_attestation():
    try:
        proc = subprocess.run(
            ["qrexec-client-vm", "sys-ai", "aegis.AttestAI"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30
        )
        if proc.returncode != 0:
            syslog.syslog(syslog.LOG_CRIT, "Aegis Attestation: Failed to call aegis.AttestAI.")
            quarantine()
            return False

        attest_data = json.loads(proc.stdout.decode('utf-8'))
        
        with open(PINS_FILE, 'r') as f:
            pins = json.load(f)

        expected_llama = pins.get("llama_sha256")
        expected_model = pins.get("model_sha256")
        expected_pcr10 = pins.get("pcr10")

        if attest_data.get("llama_sha256") != expected_llama:
            syslog.syslog(syslog.LOG_CRIT, f"Aegis Attestation: llama-server hash mismatch! Expected {expected_llama}, got {attest_data.get('llama_sha256')}")
            quarantine()
            return False

        # Trust On First Use (TOFU) for the model GGUF file
        if expected_model == "<PENDING_MODEL_DEPLOYS>" or not expected_model:
            syslog.syslog(syslog.LOG_INFO, f"Aegis Attestation: Pinning model hash dynamically: {attest_data.get('model_sha256')}")
            pins["model_sha256"] = attest_data.get("model_sha256")
            try:
                with open(PINS_FILE, 'w') as f:
                    json.dump(pins, f, indent=2)
            except Exception as e:
                syslog.syslog(syslog.LOG_ERR, f"Aegis Attestation: Failed to write model pin to config file: {str(e)}")
            expected_model = attest_data.get("model_sha256")

        if attest_data.get("model_sha256") != expected_model:
            syslog.syslog(syslog.LOG_CRIT, f"Aegis Attestation: model.gguf hash mismatch! Expected {expected_model}, got {attest_data.get('model_sha256')}")
            quarantine()
            return False

        if expected_pcr10 is not None:
            if attest_data.get("pcr10") != expected_pcr10:
                syslog.syslog(syslog.LOG_CRIT, f"Aegis Attestation: PCR10 mismatch! Expected {expected_pcr10}, got {attest_data.get('pcr10')}")
                quarantine()
                return False

        # If we reach here, attestation passed. Clear quarantine if it exists.
        if os.path.exists(QUARANTINE_FLAG):
            try:
                os.remove(QUARANTINE_FLAG)
            except OSError:
                pass
        return True

    except Exception as e:
        syslog.syslog(syslog.LOG_CRIT, f"Aegis Attestation: Verification error: {str(e)}")
        quarantine()
        return False

def quarantine():
    try:
        with open(QUARANTINE_FLAG, 'w') as f:
            f.write("QUARANTINED\n")
    except OSError:
        pass

if __name__ == "__main__":
    syslog.openlog("aegis-attest-verifier", syslog.LOG_PID, syslog.LOG_AUTH)
    if verify_attestation():
        sys.exit(0)
    else:
        sys.exit(1)
