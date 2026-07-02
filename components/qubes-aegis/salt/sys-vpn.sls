# Qubes Aegis — sys-vpn Salt Formula
# Provisions the server-side VPN peer AppVM, configures network gateway capabilities,
# and tags it with 'aegis-guest' to authorize qrexec RPC communication.

sys-vpn:
  qvm.present:
    - template: debian-12-minimal
    - label: green
    - class: AppVM

sys-vpn-prefs:
  qvm.prefs:
    - name: sys-vpn
    - autostart: True
    - netvm: sys-firewall
    - provides_network: True   # Allows sys-vpn to act as a NetVM/Gateway for other AppVMs
    - maxmem: 2048

sys-vpn-install-rpm:
  pkg.installed:
    - name: qubes-aegis-sys-vpn
    - require:
      - qvm: sys-vpn

# Tag the VPN gateway VM so it is permitted to call aegis.HeimdallChat.
# Only explicitly tagged VMs may use the HeimdallChat RPC channel.
sys-vpn-aegis-tag:
  qvm.tags:
    - name: sys-vpn
    - enable:
      - aegis-guest
