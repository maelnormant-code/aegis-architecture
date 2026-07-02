# AUDIT FIXES (2026-06-29):
#   - MEDIUM-ISO-1: Added netvm: "" to enforce NetVM: none (spec §1 mandates this)
#   - LOW-PRIV-4:   PCIe address must be set via Salt Pillar, NOT hardcoded here.
#                   Replace the pcidevs placeholder before applying this state.

sys-ai:
  qvm.present:
    - template: debian-12-minimal
    - label: black
    - class: AppVM

sys-ai-prefs:
  qvm.prefs:
    - name: sys-ai
    - virt_mode: hvm
    - netvm: ""          # CRITICAL: Enforces NetVM: none per spec §1
    - maxmem: 16384
    - pcidevs:
      # WARNING: Replace this with the actual GPU PCI address for this machine.
      # Use 'lspci' in Dom0 to find the correct address.
      # This MUST be set via a Salt Pillar value, not hardcoded here.
      # See: /srv/pillar/aegis/hardware.sls
      - {{ salt['pillar.get']('aegis:gpu_pci_address', '00:00.0') }}
