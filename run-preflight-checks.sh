#!/bin/bash
# run-preflight-checks.sh — Hardened Preflight Validator for Aegis Architecture.
# Asserts correct file names, shell scripts syntax, Python compilability, and patch idempotency.

set -euo pipefail

log() {
    echo "[$(date -Is)] $*"
}

log "Starting Aegis Build preflight verification..."

# 1. Verify File Naming Alignment
log "Verifying python memory filename alignment..."
MEMORY_PY="components/qubes-aegis/sys-copilot/heimdall/heimdall_memory.py"
LEGACY_MEMORY_PY="components/qubes-aegis/sys-copilot/heimdall/heimdall-memory.py"

if [ -f "$LEGACY_MEMORY_PY" ]; then
    log "ERROR: Legacy file $LEGACY_MEMORY_PY still exists! It must be deleted/renamed."
    exit 1
fi

if [ ! -f "$MEMORY_PY" ]; then
    log "ERROR: Target file $MEMORY_PY does not exist!"
    exit 1
fi
log "  [OK] Valid python file name $MEMORY_PY found."

# 2. Syntax validation of critical shell scripts
log "Validating shell scripts syntax..."
for sh_script in \
    components/qubes-aegis/sys-ai-builder/orchestrate-build.sh \
    components/qubes-aegis/sys-ai-builder/build-llama-in-builder.sh \
    components/qubes-aegis/sys-ai-builder/deploy-llama-to-template.sh \
    components/qubes-aegis/sys-ai-builder/destroy-builder.sh; do
    if [ ! -f "$sh_script" ]; then
        log "ERROR: Missing shell script $sh_script"
        exit 1
    fi
    bash -n "$sh_script"
    log "  [OK] Syntax clean for $sh_script"
done

# 3. Compilability of patch script and core python files
log "Validating compilability of Python components..."
python3 -m py_compile patch_final.py
python3 -m py_compile "$MEMORY_PY"

# 4. Patch Idempotency and Non-corruption Test
log "Testing patch script idempotency..."
# Backup original tools file
TOOLS_PY="components/qubes-aegis/sys-copilot/heimdall/heimdall_tools.py"
BACKUP_TOOLS_PY="/tmp/heimdall_tools_backup.py"
cp "$TOOLS_PY" "$BACKUP_TOOLS_PY"

cleanup_test() {
    mv "$BACKUP_TOOLS_PY" "$TOOLS_PY"
}
trap cleanup_test EXIT

# Clean state check: ensure no patch is applied initially
git checkout "$TOOLS_PY"

# Run patch first time (should succeed and apply changes)
log "  Running first patch..."
python3 patch_final.py

# Check first run compilation
python3 -m py_compile "$TOOLS_PY"

# Capture patched file contents
FIRST_PATCH_HASH=$(sha256sum "$TOOLS_PY" | awk '{print $1}')

# Run patch second time (should say already patched, and NOT modify content or corrupt)
log "  Running second patch (asserting idempotency)..."
SECOND_PATCH_OUT=$(python3 patch_final.py)

if [[ "$SECOND_PATCH_OUT" != *"heimdall_tools.py is already patched. Skipping."* ]]; then
    log "ERROR: Idempotency check failed! Script did not detect existing patch."
    exit 1
fi

SECOND_PATCH_HASH=$(sha256sum "$TOOLS_PY" | awk '{print $1}')

if [ "$FIRST_PATCH_HASH" != "$SECOND_PATCH_HASH" ]; then
    log "ERROR: Idempotency failure! Patch script modified the file on the second run."
    exit 1
fi

log "  [OK] Patch script is fully idempotent."

# 5. Clean up backup via exit trap
log "[SUCCESS] All preflight checks passed successfully!"
exit 0
