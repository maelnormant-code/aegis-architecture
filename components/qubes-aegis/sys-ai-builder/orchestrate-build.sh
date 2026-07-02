#!/bin/bash
# orchestrate-build.sh — Master build script. Runs in Dom0.
# Creates sys-ai-builder VM, builds llama-server, deploys to sys-ai template,
# and destroys the builder VM.
#
# Security:
#   - Builder VM is destroyed on exit (success or failure) via trap
#   - All SHA256 verification happens in Dom0
#   - Builder VM has maxmem cap and uses sys-firewall (auditable)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/var/log/aegis-build.log"
BUILDER_VM="sys-ai-builder"
BUILDER_TEMPLATE="fedora-41"
TARGET_TEMPLATE="${1:-sys-ai}"

log() {
    local msg="$(date -Is) $*"
    echo "$msg" | tee -a "$LOG_FILE"
}

# ── Trap: Always destroy builder VM on exit ─────────────────
cleanup() {
    log "Cleanup: destroying builder VM..."
    "${SCRIPT_DIR}/destroy-builder.sh" || true
}
trap cleanup EXIT

# ── Step 1: Create builder VM ───────────────────────────────
log "Creating ephemeral builder VM: ${BUILDER_VM}..."

if qvm-check "$BUILDER_VM" 2>/dev/null; then
    log "Builder VM already exists — removing first..."
    qvm-shutdown --wait --timeout 15 "$BUILDER_VM" 2>/dev/null || true
    qvm-remove --force "$BUILDER_VM"
fi

qvm-create --class AppVM \
    --template "$BUILDER_TEMPLATE" \
    --label red \
    "$BUILDER_VM"

# Configure builder VM
qvm-prefs "$BUILDER_VM" netvm sys-firewall  # NOT sys-whonix — keep auditable
qvm-prefs "$BUILDER_VM" maxmem 8192
qvm-prefs "$BUILDER_VM" memory 4096
qvm-prefs "$BUILDER_VM" vcpus 4

log "Builder VM created and configured."

# ── Step 2: Start builder and install dependencies ──────────
log "Starting builder VM..."
qvm-start "$BUILDER_VM"

log "Installing build dependencies..."
qvm-run -p "$BUILDER_VM" \
    'sudo dnf install -y cmake gcc gcc-c++ make curl tar' 2>&1 | tail -5

# ── Step 3: Copy build script to builder VM ─────────────────
log "Copying build script to builder VM..."
qvm-copy-to-vm "$BUILDER_VM" "${SCRIPT_DIR}/build-llama-in-builder.sh"

# ── Step 4: Run build ───────────────────────────────────────
log "Running build inside builder VM..."
qvm-run -p "$BUILDER_VM" \
    'chmod +x /home/user/QubesIncoming/dom0/build-llama-in-builder.sh && \
     /home/user/QubesIncoming/dom0/build-llama-in-builder.sh'

# ── Step 5: Copy built binary back to Dom0 ──────────────────
log "Retrieving built binary from builder VM..."
mkdir -p "/home/user/QubesIncoming/${BUILDER_VM}"
qvm-run -p "$BUILDER_VM" \
    'cat /home/user/llama-build-output/llama-server' \
    > "/home/user/QubesIncoming/${BUILDER_VM}/llama-server"

qvm-run -p "$BUILDER_VM" \
    'cat /home/user/llama-build-output/llama-server.sha256' \
    > "/home/user/QubesIncoming/${BUILDER_VM}/llama-server.sha256"

log "Binary retrieved."

# ── Step 6: Deploy to template ──────────────────────────────
log "Deploying to ${TARGET_TEMPLATE}..."
"${SCRIPT_DIR}/deploy-llama-to-template.sh" "$TARGET_TEMPLATE"

log "Build pipeline complete. Builder VM will be destroyed by cleanup trap."
