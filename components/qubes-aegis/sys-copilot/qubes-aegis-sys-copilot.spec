Name:           qubes-aegis-sys-copilot
Version:        1.0.0
Release:        1%{?dist}
Summary:        Sys-Copilot components for Qubes Aegis AI Fork
License:        MIT
BuildArch:      noarch

# AUDIT FIXES (2026-06-29) - MEDIUM-PRIV-3:
#   - Added Requires: for socat and sqlite3
#   - Added %post to enable/start aegis-llm-proxy service
#   - Fixed installation of aegis.GetContext to /etc/qubes-rpc/ (correct)

Requires:       socat
Requires:       cron
Requires:       python3 >= 3.10
Requires:       python3-pyyaml

%description
Provides the Heimdall Copilot agent interface components for sys-copilot:
  - aegis-llm-proxy.sh: Forwards inference requests to sys-ai via Unix socket
  - aegis.GetContext: qrexec RPC handler for guest context queries

%install
# LLM proxy (runs as a service — installed to /usr/libexec for isolation)
mkdir -p %{buildroot}/usr/libexec/qubes-aegis/
install -m 0750 aegis-llm-proxy.sh %{buildroot}/usr/libexec/qubes-aegis/

# qrexec RPC handler (must be in /etc/qubes-rpc/ for qrexec daemon discovery)
mkdir -p %{buildroot}/etc/qubes-rpc/
install -m 0755 aegis.GetContext %{buildroot}/etc/qubes-rpc/
install -m 0755 aegis.VerifyPackages %{buildroot}/etc/qubes-rpc/
install -m 0755 aegis.HeimdallChat %{buildroot}/etc/qubes-rpc/

# qrexec RPC config to run under aegis-copilot user
mkdir -p %{buildroot}/etc/qubes/rpc-config
echo "user=aegis-copilot" > %{buildroot}/etc/qubes/rpc-config/aegis.GetContext
echo "user=aegis-copilot" > %{buildroot}/etc/qubes/rpc-config/aegis.VerifyPackages
echo "user=aegis-copilot" > %{buildroot}/etc/qubes/rpc-config/aegis.HeimdallChat

# Heimdall agent
mkdir -p %{buildroot}/usr/libexec/qubes-aegis/heimdall/
install -m 0755 heimdall/heimdall-agent.py %{buildroot}/usr/libexec/qubes-aegis/heimdall/
install -m 0644 heimdall/heimdall-acs.py %{buildroot}/usr/libexec/qubes-aegis/heimdall/
install -m 0644 heimdall/heimdall_memory.py %{buildroot}/usr/libexec/qubes-aegis/heimdall/
install -m 0644 heimdall/heimdall_tools.py %{buildroot}/usr/libexec/qubes-aegis/heimdall/
install -m 0644 heimdall/llm_client.py %{buildroot}/usr/libexec/qubes-aegis/heimdall/

mkdir -p %{buildroot}/usr/lib/systemd/system/
install -m 0644 heimdall/aegis-heimdall.service %{buildroot}/usr/lib/systemd/system/
install -m 0644 aegis-llm-proxy.service %{buildroot}/usr/lib/systemd/system/

install -m 0755 aegis-attest-verifier.py %{buildroot}/usr/libexec/qubes-aegis/
mkdir -p %{buildroot}/etc/qubes-aegis/
install -m 0600 ../dom0/attestation-pins.json %{buildroot}/etc/qubes-aegis/

# Documentation request forwarder daemon
install -m 0755 aegis-doc-forwarder.py %{buildroot}/usr/libexec/qubes-aegis/
install -m 0644 aegis-doc-forwarder.service %{buildroot}/usr/lib/systemd/system/

# Runtime socket directory
mkdir -p %{buildroot}/run/aegis/

# Heimdall Skills
mkdir -p %{buildroot}/var/lib/aegis/
cp -a skills %{buildroot}/var/lib/aegis/

%pre
getent group aegis-copilot >/dev/null || groupadd -r aegis-copilot
getent passwd aegis-copilot >/dev/null || \
    useradd -r -g aegis-copilot -d /nonexistent -s /usr/sbin/nologin \
    -c "Aegis Copilot Service" aegis-copilot

%post
systemctl daemon-reload
systemctl enable aegis-heimdall.service
systemctl enable aegis-llm-proxy.service
systemctl enable aegis-doc-forwarder.service

# Create runtime directory for Unix domain socket
install -d -m 0750 -o root -g aegis-copilot /run/aegis || true
install -d -m 0750 -o aegis-copilot -g aegis-copilot /var/lib/aegis || true

%preun
if [ $1 -eq 0 ]; then
    systemctl stop aegis-heimdall.service || true
    systemctl disable aegis-heimdall.service || true
    systemctl stop aegis-llm-proxy.service || true
    systemctl disable aegis-llm-proxy.service || true
    systemctl stop aegis-doc-forwarder.service || true
    systemctl disable aegis-doc-forwarder.service || true
fi

%postun
systemctl daemon-reload

%files
%attr(0750, root, root) /usr/libexec/qubes-aegis/aegis-llm-proxy.sh
%attr(0755, root, root) /etc/qubes-rpc/aegis.GetContext
%attr(0644, root, root) /etc/qubes/rpc-config/aegis.GetContext
%attr(0755, root, root) /etc/qubes-rpc/aegis.VerifyPackages
%attr(0644, root, root) /etc/qubes/rpc-config/aegis.VerifyPackages
%attr(0755, root, root) /etc/qubes-rpc/aegis.HeimdallChat
%attr(0644, root, root) /etc/qubes/rpc-config/aegis.HeimdallChat
%attr(0755, root, root) /usr/libexec/qubes-aegis/heimdall/heimdall-agent.py
%attr(0644, root, root) /usr/libexec/qubes-aegis/heimdall/heimdall-acs.py
%attr(0644, root, root) /usr/libexec/qubes-aegis/heimdall/heimdall_memory.py
%attr(0644, root, root) /usr/libexec/qubes-aegis/heimdall/heimdall_tools.py
%attr(0644, root, root) /usr/libexec/qubes-aegis/heimdall/llm_client.py
%attr(0644, root, root) /usr/lib/systemd/system/aegis-heimdall.service
%attr(0644, root, root) /usr/lib/systemd/system/aegis-llm-proxy.service
%attr(0755, root, root) /usr/libexec/qubes-aegis/aegis-attest-verifier.py
%attr(0600, aegis-copilot, aegis-copilot) /etc/qubes-aegis/attestation-pins.json
%dir %attr(0750, root, aegis-copilot) /run/aegis
%dir %attr(0750, aegis-copilot, aegis-copilot) /var/lib/aegis
%attr(-, aegis-copilot, aegis-copilot) /var/lib/aegis/skills
%attr(0755, root, root) /usr/libexec/qubes-aegis/aegis-doc-forwarder.py
%attr(0644, root, root) /usr/lib/systemd/system/aegis-doc-forwarder.service
