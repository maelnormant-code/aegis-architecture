#!/bin/bash
# aegis-guest-llm-proxy.sh — Runs in guest AppVM.
# Listens on localhost:8080 and forwards to sys-copilot aegis.LLMProxyGuest via qrexec.

set -euo pipefail

# Mode: check if we are qubes-aware first
IDENTITY=$(qubesdb-read /qubes-features/ai-identity 2>/dev/null || echo "generic")

if [ "$IDENTITY" != "qubes-aware" ]; then
    echo "Aegis: guest is not configured as qubes-aware. Exiting."
    exit 0
fi

# Listen on localhost:8080 and execute qrexec client
exec socat \
    TCP-LISTEN:8080,bind=127.0.0.1,fork,reuseaddr \
    EXEC:"qrexec-client-vm sys-copilot aegis.LLMProxyGuest"
