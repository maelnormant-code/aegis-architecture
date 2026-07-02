# AUDIT FIXES (2026-06-29):
#   - HIGH-PRIV-1:  Replaced cmd.run with qvm.features (declarative).
#                   The spec §2 explicitly forbids cmd.run in Salt states.
#   - MEDIUM-REQ-6: Corrected QubesDB key name from 'qubes-ai-mode' to
#                   'qubes-ai-identity' to match spec §3, line 96.

include:
  - aegis.sys-ai
  - aegis.sys-copilot
  - aegis.sys-vpn

# Set the default AI identity for template VMs.
# This writes a QubesDB feature that guest init scripts read at boot.
# Key must match: spec §3 'qvm-features <vm-name> ai-identity qubes-aware'
aegis_qubesdb_features:
  qvm.features:
    - name: default-template
    - set:
        ai-identity: qubes-aware
