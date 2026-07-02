Name:           qubes-aegis-sys-ai
Version:        1.0.0
Release:        1%{?dist}
Summary:        Sys-AI components for Qubes Aegis AI Fork
License:        MIT
BuildArch:      x86_64
Requires:       socat

# AUDIT FIXES (2026-06-29) - MEDIUM-PRIV-3:
#   - Added %pre hook to create aegis-ai system user in the template
#   - Added %post hook to enable systemd service
#   - Noted that llama-server binary must be pre-built by sys-ai-builder
#   - Updated service file reference to match audit-fixed unit file

%description
Provides the statically compiled llama-server binary and the hardened systemd
service unit for the sys-ai inference qube.

NOTE: The llama-server binary must be compiled in a separate sys-ai-builder VM
(as described in spec §12) and copied here before RPM build. This package does
NOT fetch it from the internet.

%pre
# Create the service account for running llama-server
# This user is also created by the dom0 package, but we need it in the template
getent group aegis-ai > /dev/null 2>&1 || groupadd --system aegis-ai
getent passwd aegis-ai > /dev/null 2>&1 || \
    useradd --system --no-create-home --shell /sbin/nologin \
            --gid aegis-ai --comment "Aegis AI Inference" aegis-ai

%install
mkdir -p %{buildroot}/usr/bin/
install -m 0755 llama-server %{buildroot}/usr/bin/
install -m 0755 aegis-gemini-proxy.py %{buildroot}/usr/bin/aegis-gemini-proxy
install -m 0755 aegis-dev-toggle-llm %{buildroot}/usr/bin/aegis-dev-toggle-llm

mkdir -p %{buildroot}/usr/lib/systemd/system/
install -m 0644 aegis-llama.service %{buildroot}/usr/lib/systemd/system/
install -m 0644 aegis-gemini.service %{buildroot}/usr/lib/systemd/system/

# Mount point for the LVM block device (spec §10C)
mkdir -p %{buildroot}/mnt/llm-weights/

mkdir -p %{buildroot}/etc/qubes-rpc/
install -m 0755 aegis.AttestAI %{buildroot}/etc/qubes-rpc/
install -m 0755 aegis.LLMProxy %{buildroot}/etc/qubes-rpc/

%post
systemctl daemon-reload
systemctl enable aegis-llama.service

%preun
systemctl disable aegis-llama.service || true
systemctl disable aegis-gemini.service || true

%postun
systemctl daemon-reload

%files
%attr(0755, root, root) /usr/bin/llama-server
%attr(0755, root, root) /usr/bin/aegis-gemini-proxy
%attr(0755, root, root) /usr/bin/aegis-dev-toggle-llm
%attr(0644, root, root) /usr/lib/systemd/system/aegis-llama.service
%attr(0644, root, root) /usr/lib/systemd/system/aegis-gemini.service
%attr(0755, root, root) /etc/qubes-rpc/aegis.AttestAI
%attr(0755, root, root) /etc/qubes-rpc/aegis.LLMProxy
%dir %attr(0755, root, root) /mnt/llm-weights
