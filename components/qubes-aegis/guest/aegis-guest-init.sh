#!/bin/bash
# aegis-guest-init.sh — Read QubesDB AI identity and configure agent mode.
#
# AUDIT FIX (2026-06-29):
#   - MEDIUM-REQ-6: Key changed from /qubes-ai-mode to /qubes-ai-identity
#                   to match spec §3, line 96.
#
# This script is run by the aegis-guest-init.service systemd unit at boot.
# It reads the QubesDB key set by Dom0 and starts the appropriate agent mode.

# Read the identity feature written by Dom0 via qvm-features
IDENTITY=$(qubesdb-read /qubes-features/ai-identity 2>/dev/null || echo "generic")

if [ "$IDENTITY" = "qubes-aware" ]; then
    # Start the MCP server daemon (aegis-mcp.service must exist)
    systemctl start aegis-mcp.service
    echo "Goose initialized in Qubes-aware mode."
else
    # Generic offline Linux mode — no Qubes-specific agent behavior
    exit 0
fi
