#!/bin/bash
# Export recent audit logs to a temporary sanitized file for Copilot ingestion

DUMP_DIR="/var/run/qubes-aegis"
mkdir -p "$DUMP_DIR"
chown root:qubes "$DUMP_DIR"
chmod 750 "$DUMP_DIR"

OUTPUT_FILE="$DUMP_DIR/audit_export.json"

# Just a simulated fetch of Qubes OS events or ausearch output
ausearch -ts recent --format json > "$OUTPUT_FILE" 2>/dev/null

# Make it readable by the qrexec service
chmod 640 "$OUTPUT_FILE"
