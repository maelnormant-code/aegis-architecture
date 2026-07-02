Name:           qubes-aegis-guest
Version:        1.0.0
Release:        1%{?dist}
Summary:        Guest AppVM components for Qubes Aegis AI Fork
License:        MIT
BuildArch:      noarch

# AUDIT FIXES (2026-06-29) - MEDIUM-PRIV-3 / LOW-ARCH-4:
#   - Added Requires: python3
#   - Added missing aegis-mcp.service unit file (LOW-ARCH-4: was absent,
#     causing 'systemctl start aegis-mcp.service' to fail silently at boot)
#   - Added %post hook to enable aegis-guest-init.service
#   - Added aegis-guest-init.service unit for the init script

Requires:       python3 >= 3.10
Requires:       qubes-core-agent

%description
Provides MCP server and QubesDB identity initialization scripts for
AppVMs that participate in the Qubes Aegis AI system.

Components:
  - aegis-mcp-server.py: Model Context Protocol server stub
  - aegis-mcp.service: systemd unit for the MCP server
  - aegis-guest-init.sh: Reads QubesDB /qubes-ai-identity and starts MCP
  - aegis-guest-init.service: systemd unit for the init script

%install
mkdir -p %{buildroot}/usr/libexec/qubes-aegis/
install -m 0755 aegis-mcp-server.py %{buildroot}/usr/libexec/qubes-aegis/
install -m 0644 aegis_mcp_security.py %{buildroot}/usr/libexec/qubes-aegis/
install -m 0644 aegis_fs_safe.py %{buildroot}/usr/libexec/qubes-aegis/
install -m 0755 aegis-guest-init.sh %{buildroot}/usr/libexec/qubes-aegis/
install -m 0755 aegis-guest-llm-proxy.sh %{buildroot}/usr/libexec/qubes-aegis/

mkdir -p %{buildroot}/usr/lib/systemd/system/
install -m 0644 aegis-mcp.service %{buildroot}/usr/lib/systemd/system/
install -m 0644 aegis-guest-llm-proxy.service %{buildroot}/usr/lib/systemd/system/

# Write the init service unit inline
cat > %{buildroot}/usr/lib/systemd/system/aegis-guest-init.service << 'EOF'
[Unit]
Description=Aegis Guest Identity Initialization
After=qubes-sysinit.service

[Service]
Type=oneshot
ExecStart=/usr/libexec/qubes-aegis/aegis-guest-init.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

%post
systemctl daemon-reload
systemctl enable aegis-guest-init.service
systemctl enable aegis-mcp.service
systemctl enable aegis-guest-llm-proxy.service

%preun
systemctl disable aegis-guest-init.service || true
systemctl disable aegis-mcp.service || true
systemctl disable aegis-guest-llm-proxy.service || true

%postun
systemctl daemon-reload

%files
%attr(0755, root, root) /usr/libexec/qubes-aegis/aegis-mcp-server.py
%attr(0644, root, root) /usr/libexec/qubes-aegis/aegis_mcp_security.py
%attr(0644, root, root) /usr/libexec/qubes-aegis/aegis_fs_safe.py
%attr(0755, root, root) /usr/libexec/qubes-aegis/aegis-guest-init.sh
%attr(0755, root, root) /usr/libexec/qubes-aegis/aegis-guest-llm-proxy.sh
%attr(0644, root, root) /usr/lib/systemd/system/aegis-mcp.service
%attr(0644, root, root) /usr/lib/systemd/system/aegis-guest-init.service
%attr(0644, root, root) /usr/lib/systemd/system/aegis-guest-llm-proxy.service
