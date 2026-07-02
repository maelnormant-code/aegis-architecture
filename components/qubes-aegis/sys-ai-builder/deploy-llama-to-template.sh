#!/bin/bash
# deploy-llama-to-template.sh — Runs in Dom0.
# Verifies the retrieved binary's SHA256 in Dom0 against the expected pin,
# and installs it directly to the sys-ai-template VM.

set -euo pipefail

TEMPLATE_VM="${1:-sys-ai-template}"
BUILDER_VM="sys-ai-builder"
DOM0_INCOMING_DIR="/home/user/QubesIncoming/${BUILDER_VM}"
LOCAL_BIN="${DOM0_INCOMING_DIR}/llama-server"

# Configuration directory and files for pins in Dom0
PINS_FILE="/etc/qubes-aegis/llama-build-pins.json"
ATTESTATION_PINS_FILE="/etc/qubes-aegis/attestation-pins.json"

if [ ! -f "$LOCAL_BIN" ]; then
    echo "ERROR: Local binary not found at $LOCAL_BIN"
    exit 1
fi

if ! qvm-check "$TEMPLATE_VM" &>/dev/null; then
    echo "ERROR: Template $TEMPLATE_VM does not exist."
    exit 1
fi

# ── Retrieve/Generate expected binary hash in Dom0 ───────────
echo "[*] Verifying binary hash in Dom0..."

ACTUAL_SHA256=$(sha256sum "$LOCAL_BIN" | awk '{print $1}')
EXPECTED_BIN_SHA256=""

# Create pins directory if missing
mkdir -p "/etc/qubes-aegis"

if [ -f "$PINS_FILE" ]; then
    EXPECTED_BIN_SHA256=$(python3 -c "import json; print(json.load(open('$PINS_FILE')).get('llama_sha256', ''))" 2>/dev/null || echo "")
fi

if [ -z "$EXPECTED_BIN_SHA256" ] || [ "$EXPECTED_BIN_SHA256" = "<FILL_IN_AFTER_FIRST_BUILD>" ]; then
    SOURCE_SHA256=""
    if [ -f "${DOM0_INCOMING_DIR}/llama-source.sha256" ]; then
        SOURCE_SHA256=$(cat "${DOM0_INCOMING_DIR}/llama-source.sha256" | awk '{print $1}')
    fi

    # Trigger zenity popup in Dom0 to approve and pin this binary
    PROMPT_TEXT="No pinned binary hash found. A new binary has been built.\n\n"
    PROMPT_TEXT+="Binary Path: $LOCAL_BIN\n"
    PROMPT_TEXT+="Computed SHA256: $ACTUAL_SHA256\n"
    if [ -n "$SOURCE_SHA256" ]; then
        PROMPT_TEXT+="Source Tarball SHA256: $SOURCE_SHA256\n"
    fi
    PROMPT_TEXT+="\nDo you want to trust this build and pin these hashes in Dom0 configuration?"

    if zenity --question --title="Aegis: Bootstrap Binary Trust" --width=600 --text="$PROMPT_TEXT"; then
        echo "{\"llama_sha256\": \"$ACTUAL_SHA256\"}" > "$PINS_FILE"
        chmod 600 "$PINS_FILE"
        
        # Also initialize attestation pins
        echo "{\"llama_sha256\": \"$ACTUAL_SHA256\", \"model_sha256\": \"<PENDING_MODEL_DEPLOYS>\", \"pcr10\": null}" > "$ATTESTATION_PINS_FILE"
        chmod 600 "$ATTESTATION_PINS_FILE"
        
        EXPECTED_BIN_SHA256="$ACTUAL_SHA256"
        echo "[+] Successfully pinned binary hash: $EXPECTED_BIN_SHA256"
    else
        echo "FATAL: User rejected the binary hash."
        exit 1
    fi
fi

# Format check expected hash
if [[ ! "$EXPECTED_BIN_SHA256" =~ ^[0-9a-fA-F]{64}$ ]]; then
    echo "FATAL: Invalid EXPECTED_BIN_SHA256 format."
    exit 1
fi

if [ "$ACTUAL_SHA256" != "$EXPECTED_BIN_SHA256" ]; then
    echo "FATAL: Binary hash mismatch!"
    echo "       Expected: ${EXPECTED_BIN_SHA256}"
    echo "       Got:      ${ACTUAL_SHA256}"
    exit 1
fi

echo "[*] Hash verified successfully."

# ── Deploy directly to template VM ──────────────────────────
echo "[*] Installing binary to $TEMPLATE_VM..."

# Ensure target directory exists in template
qvm-run -p "$TEMPLATE_VM" -u root "mkdir -p /usr/bin"

# Stream the binary directly into /usr/bin/llama-server
qvm-run -p "$TEMPLATE_VM" -u root "dd of=/usr/bin/llama-server bs=1M" < "$LOCAL_BIN"

# Set correct permissions
qvm-run -p "$TEMPLATE_VM" -u root "chmod 0755 /usr/bin/llama-server"

echo "[+] Deployment successful."
