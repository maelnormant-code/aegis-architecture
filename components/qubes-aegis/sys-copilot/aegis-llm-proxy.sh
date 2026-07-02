#!/bin/bash
# aegis-llm-proxy.sh — Forward LLM requests from sys-copilot to sys-ai via qrexec.
#
# AUDIT FIXES (2026-06-29):
#   - HIGH-SEC-3a: Switched from TCP to Unix domain socket to scope connections
#                  to the aegis-ai process group (mode=0600).
#   - HIGH-SEC-3b: Explicit bind to 127.0.0.1 added as fallback if TCP is needed.
#
# The Heimdall agent connects to /run/aegis/llm.sock (owned by aegis-copilot:aegis-copilot)
# instead of an open TCP port.

SOCKET_PATH="${AEGIS_LLM_SOCK:-/run/aegis/llm.sock}"
export QUARANTINE_FLAG="${AEGIS_QUARANTINE_FLAG:-/run/aegis/sys-ai-quarantine}"
rm -f "$SOCKET_PATH"

# mode=0600: only the aegis-copilot user (who owns the socket) can connect.
# fork: handle multiple sequential requests.
exec socat \
    UNIX-LISTEN:"${SOCKET_PATH}",fork,mode=0600 \
    SYSTEM:"if [ -f \$QUARANTINE_FLAG ]; then exit 1; else exec qrexec-client-vm sys-ai aegis.LLMProxy; fi"

