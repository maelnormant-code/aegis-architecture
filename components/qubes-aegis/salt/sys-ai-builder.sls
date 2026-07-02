# salt/sys-ai-builder.sls — Ephemeral builder VM for llama-server.

sys-ai-builder:
  qvm.present:
    - template: debian-12-minimal  # Needs to have build-essential installed in template
    - label: red
    - class: AppVM

sys-ai-builder-prefs:
  qvm.prefs:
    - name: sys-ai-builder
    - netvm: sys-firewall  # Network connected for downloading
    - maxmem: 8192         # Needs memory for compilation
    - require:
      - qvm: sys-ai-builder

# Run the build script on start
sys-ai-builder-run-build:
  cmd.script:
    - name: salt://aegis/build-llama-in-builder.sh
    - runas: user
    - require:
      - qvm: sys-ai-builder
