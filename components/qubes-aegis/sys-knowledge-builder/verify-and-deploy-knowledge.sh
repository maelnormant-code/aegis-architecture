#!/bin/bash
# verify-and-deploy-knowledge.sh — Runs in Dom0.
# Verifies SHA256 of the knowledge index blob, then deploys to sys-knowledge.
#
# Usage: ./verify-and-deploy-knowledge.sh /path/to/knowledge-index.tar.gz

set -euo pipefail

LOG_FILE="/var/log/aegis-knowledge-deploy.log"
TARGET_VM="sys-knowledge"
TARGET_DIR="/var/lib/aegis"

# Configuration file for knowledge index pins in Dom0
PINS_FILE="/etc/qubes-aegis/knowledge-pins.json"

log() { echo "$(date -Is) $*" | tee -a "$LOG_FILE"; }

if [ $# -lt 1 ]; then
    echo "Usage: $0 <path-to-knowledge-index.tar.gz>"
    exit 1
fi

TARBALL="$1"

if [ ! -f "$TARBALL" ]; then
    log "ERROR: Tarball not found: $TARBALL"
    exit 1
fi

# ── Retrieve/Generate expected knowledge hash in Dom0 ────────
log "Verifying SHA256 of $TARBALL..."

ACTUAL_SHA256=$(sha256sum "$TARBALL" | awk '{print $1}')
EXPECTED_SHA256=""

# Create pins directory if missing
mkdir -p "/etc/qubes-aegis"

if [ -f "$PINS_FILE" ]; then
    EXPECTED_SHA256=$(python3 -c "import json; print(json.load(open('$PINS_FILE')).get('knowledge_sha256', ''))" 2>/dev/null || echo "")
fi

if [ -z "$EXPECTED_SHA256" ] || [ "$EXPECTED_SHA256" = "<FILL_IN_AFTER_FIRST_VERIFIED_BUILD>" ]; then
    # Trigger zenity popup in Dom0 to approve and pin this knowledge database
    PROMPT_TEXT="No pinned knowledge index hash found. A new index has been compiled.\n\n"
    PROMPT_TEXT+="Tarball Path: $TARBALL\n"
    PROMPT_TEXT+="Computed SHA256: $ACTUAL_SHA256\n\n"
    PROMPT_TEXT+="Do you want to trust this knowledge database and pin this hash in Dom0 configuration?"

    if zenity --question --title="Aegis: Bootstrap Knowledge Trust" --width=600 --text="$PROMPT_TEXT"; then
        echo "{\"knowledge_sha256\": \"$ACTUAL_SHA256\"}" > "$PINS_FILE"
        chmod 600 "$PINS_FILE"
        EXPECTED_SHA256="$ACTUAL_SHA256"
        log "[+] Successfully pinned knowledge hash: $EXPECTED_SHA256"
    else
        log "FATAL: User rejected the knowledge database hash."
        exit 1
    fi
fi

# Format check expected hash
if [[ ! "$EXPECTED_SHA256" =~ ^[0-9a-fA-F]{64}$ ]]; then
    log "FATAL: Invalid EXPECTED_SHA256 format."
    exit 1
fi

# Reject path if it contains newlines or backslashes
if [[ "$TARBALL" =~ [$'\n\r\\'] ]]; then
    log "ERROR: Tarball path contains invalid characters (newline or backslash)."
    exit 1
fi

# Create a secure temporary directory for verification
TMP_VERIFY_DIR=$(mktemp -d /tmp/aegis-knowledge-verify.XXXXXX)
trap 'rm -rf "$TMP_VERIFY_DIR"' EXIT

# Link to target.tar.gz to prevent space/whitespace injection vulnerabilities
SAFE_TARBALL="${TMP_VERIFY_DIR}/target.tar.gz"
ln -s "$(realpath "$TARBALL")" "$SAFE_TARBALL"

CHECKSUM_FILE="${TMP_VERIFY_DIR}/checksum.txt"
printf "%s  %s\n" "$EXPECTED_SHA256" "$SAFE_TARBALL" > "$CHECKSUM_FILE"

if ! sha256sum -c "$CHECKSUM_FILE" --strict; then
    log "FATAL: SHA256 verification FAILED for $TARBALL"
    log "       Expected: ${EXPECTED_SHA256}"
    log "       Got:      $(sha256sum "$TARBALL" | awk '{print $1}')"
    exit 1
fi

log "SHA256 verified successfully."

# ── Extract and deploy ──────────────────────────────────────
TMP_EXTRACT=$(mktemp -d /tmp/aegis-knowledge-deploy.XXXXXX)
# Update trap to clean up both temp directories
trap 'rm -rf "$TMP_VERIFY_DIR" "$TMP_EXTRACT"' EXIT

tar xzf "$TARBALL" -C "$TMP_EXTRACT"

if [ ! -f "${TMP_EXTRACT}/knowledge.db" ]; then
    log "ERROR: knowledge.db not found in tarball"
    exit 1
fi

log "Deploying knowledge.db to ${TARGET_VM}:${TARGET_DIR}..."

# Ensure target directory exists and stream file directly to the VM
qvm-run -p "$TARGET_VM" "sudo mkdir -p ${TARGET_DIR}"
qvm-run -p "$TARGET_VM" "sudo dd of=${TARGET_DIR}/knowledge.db bs=1M" < "${TMP_EXTRACT}/knowledge.db"
qvm-run -p "$TARGET_VM" "sudo chown aegis-knowledge:aegis-knowledge ${TARGET_DIR}/knowledge.db && sudo chmod 0640 ${TARGET_DIR}/knowledge.db"

log "Knowledge index deployed successfully to ${TARGET_VM}."
