# salt/sys-knowledge.sls — Create and configure the sys-knowledge RAG VM
# This VM holds an air-gapped SQLite FTS5 knowledge base.
# Root filesystem uses squashfs overlay for read-only protection.
# Updated knowledge indexes are deployed via qvm-copy from Dom0
# after SHA256 verification (see sys-knowledge-builder/).

sys-knowledge:
  qvm.present:
    - template: debian-12-minimal
    - label: orange
    - class: AppVM

sys-knowledge-prefs:
  qvm.prefs:
    - name: sys-knowledge
    - netvm: ""          # CRITICAL: Air-gapped — no network access ever
    - autostart: true
    - maxmem: 2048
    - kernel: pvgrub2     # Use pvgrub2 to enable squashfs read-only root overlay
    - require:
      - qvm: sys-knowledge

# Ensure the knowledge database directory exists in the template
sys-knowledge-db-dir:
  file.directory:
    - name: /var/lib/aegis
    - user: aegis-knowledge
    - group: aegis-knowledge
    - mode: 0750

# Install the RPM inside the template
sys-knowledge-install-rpm:
  pkg.installed:
    - name: qubes-aegis-sys-knowledge
    - require:
      - qvm: sys-knowledge

# Enable the query handler service
sys-knowledge-enable-service:
  service.enabled:
    - name: aegis-knowledge-server
    - require:
      - pkg: sys-knowledge-install-rpm
