#!/bin/bash
# destroy-builder.sh — Runs in Dom0 to tear down sys-ai-builder.

set -euo pipefail

BUILDER_VM="sys-ai-builder"

if qvm-check "$BUILDER_VM" &>/dev/null; then
    echo "[*] Destroying ephemeral builder VM $BUILDER_VM..."
    qvm-kill "$BUILDER_VM" || true
    qvm-remove --force "$BUILDER_VM"
    echo "[+] Destroyed."
else
    echo "VM $BUILDER_VM does not exist."
fi
