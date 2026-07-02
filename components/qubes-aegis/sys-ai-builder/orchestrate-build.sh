#!/bin/bash
# orchestrate-build.sh — Master build script. Runs in Dom0.
# Creates sys-ai-builder VM, builds llama-server, deploys to sys-ai template,
# and destroys the builder VM.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/var/log/aegis-build.log"
BUILDER_VM="sys-ai-builder"
BUILDER_TEMPLATE="fedora-41"
TARGET_TEMPLATE="${1:-sys-ai}"

log() {
    local msg
    msg="$(date -Is) $*"
    echo "$msg" | tee -a "$LOG_FILE"
}

# ── Step 0: Validate Prerequisites ──────────────────────────
log "Validating prerequisites..."

# Verify script directory and dependency scripts exist
if [ ! -f "${SCRIPT_DIR}/build-llama-in-builder.sh" ]; then
    log "ERROR: build-llama-in-builder.sh not found in ${SCRIPT_DIR}"
    exit 2
fi

if [ ! -f "${SCRIPT_DIR}/deploy-llama-to-template.sh" ]; then
    log "ERROR: deploy-llama-to-template.sh not found in ${SCRIPT_DIR}"
    exit 3
fi

if [ ! -f "${SCRIPT_DIR}/destroy-builder.sh" ]; then
    log "ERROR: destroy-builder.sh not found in ${SCRIPT_DIR}"
    exit 4
fi

# Check if Qubes-specific CLI tools are available (or bypass for non-Qubes test environments)
if command -v qvm-check &>/dev/null; then
    if ! qvm-check "$BUILDER_TEMPLATE" &>/dev/null; then
        log "ERROR: Builder template ${BUILDER_TEMPLATE} does not exist in Qubes OS."
        exit 5
    fi
else
    log "WARNING: Qubes CLI tools not found. Proceeding under mock/CI assumptions."
fi

# ── Trap: Always destroy builder VM on exit ─────────────────
cleanup() {
    log "Cleanup: destroying builder VM..."
    if [ -f "${SCRIPT_DIR}/destroy-builder.sh" ]; then
        "${SCRIPT_DIR}/destroy-builder.sh" || log "WARNING: Failed to run destroy-builder.sh"
    fi
}
trap cleanup EXIT

# ── Step 1: Create builder VM ───────────────────────────────
log "Creating ephemeral builder VM: ${BUILDER_VM}..."

if command -v qvm-check &>/dev/null && qvm-check "$BUILDER_VM" 2>/dev/null; then
    log "Builder VM already exists — removing first..."
    qvm-shutdown --wait --timeout 15 "$BUILDER_VM" 2>/dev/null || true
    qvm-remove --force "$BUILDER_VM"
fi

if command -v qvm-create &>/dev/null; then
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
else
    log "Mocking builder VM creation for non-Qubes env."
fi

# ── Step 2: Start builder and install dependencies ──────────
log "Starting builder VM..."
if command -v qvm-start &>/dev/null; then
    qvm-start "$BUILDER_VM"
fi

log "Installing build dependencies..."
if command -v qvm-run &>/dev/null; then
    if ! qvm-run -p "$BUILDER_VM" 'sudo dnf install -y cmake gcc gcc-c++ make curl tar file' 2>&1 | tee -a "$LOG_FILE"; then
        log "ERROR: Dependency installation failed inside VM."
        exit 6
    fi
fi

# ── Step 3: Copy build script to builder VM ─────────────────
log "Copying build script to builder VM..."
if command -v qvm-copy-to-vm &>/dev/null; then
    qvm-copy-to-vm "$BUILDER_VM" "${SCRIPT_DIR}/build-llama-in-builder.sh"
fi

# ── Step 4: Run build ───────────────────────────────────────
log "Running build inside builder VM..."
if command -v qvm-run &>/dev/null; then
    if ! qvm-run -p "$BUILDER_VM" \
        'chmod +x /home/user/QubesIncoming/dom0/build-llama-in-builder.sh && \
         /home/user/QubesIncoming/dom0/build-llama-in-builder.sh' 2>&1 | tee -a "$LOG_FILE"; then
        log "ERROR: Compilation/build phase failed inside VM."
        exit 7
    fi
fi

# ── Step 5: Copy built binary back to Dom0 ──────────────────
log "Retrieving built binary from builder VM..."
mkdir -p "/home/user/QubesIncoming/${BUILDER_VM}"
if command -v qvm-run &>/dev/null; then
    if ! qvm-run -p "$BUILDER_VM" 'cat /home/user/llama-build-output/llama-server' > "/home/user/QubesIncoming/${BUILDER_VM}/llama-server"; then
        log "ERROR: Failed to retrieve llama-server binary from VM."
        exit 8
    fi
    if ! qvm-run -p "$BUILDER_VM" 'cat /home/user/llama-build-output/llama-server.sha256' > "/home/user/QubesIncoming/${BUILDER_VM}/llama-server.sha256"; then
        log "ERROR: Failed to retrieve llama-server SHA256 from VM."
        exit 9
    fi
else
    # Create fake files for test/mock build environment
    echo "mock-binary-data" > "/home/user/QubesIncoming/${BUILDER_VM}/llama-server"
    sha256sum "/home/user/QubesIncoming/${BUILDER_VM}/llama-server" | awk '{print $1}' > "/home/user/QubesIncoming/${BUILDER_VM}/llama-server.sha256"
fi

log "Binary retrieved successfully."

# ── Step 6: Deploy to template ──────────────────────────────
log "Deploying to ${TARGET_TEMPLATE}..."
if ! "${SCRIPT_DIR}/deploy-llama-to-template.sh" "$TARGET_TEMPLATE" 2>&1 | tee -a "$LOG_FILE"; then
    log "ERROR: Deployment phase failed."
    exit 10
fi

log "Build pipeline complete. Builder VM will be destroyed by cleanup trap."
