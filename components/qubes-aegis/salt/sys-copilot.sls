# AUDIT FIXES (2026-06-29):
#   - MEDIUM-ISO-2: Added netvm: "" to enforce NetVM: none (spec §1 mandates this)
#   - MEDIUM-SEC-4: Added qvm.tags to explicitly tag app-chat as aegis-guest
#                   (required for 30-aegis.policy @tag:aegis-guest matching)

sys-copilot:
  qvm.present:
    - template: debian-12-minimal
    - label: purple
    - class: AppVM

sys-copilot-prefs:
  qvm.prefs:
    - name: sys-copilot
    - autostart: True
    - netvm: ""    # CRITICAL: Enforces NetVM: none per spec §1
    - maxmem: 4096

sys-copilot-install-rpm:
  pkg.installed:
    - name: qubes-aegis-sys-copilot
    - require:
      - qvm: sys-copilot

sys-copilot-enable-heimdall:
  service.enabled:
    - name: aegis-heimdall
    - require:
      - pkg: sys-copilot-install-rpm
# Tag the user-facing chat VM so it is permitted to call aegis.GetContext.
# Only explicitly tagged VMs may use the GetContext RPC channel.
# To revoke access: qvm-tags <vm> del aegis-guest
app-chat-aegis-tag:
  qvm.tags:
    - name: app-chat
    - enable:
      - aegis-guest
