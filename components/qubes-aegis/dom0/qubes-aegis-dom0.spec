Name:           qubes-aegis-dom0
Version:        1.0.0
Release:        1%{?dist}
Summary:        Dom0 components for Qubes Aegis AI Fork
License:        GPLv2+
BuildArch:      noarch

# AUDIT FIXES (2026-06-29) - MEDIUM-PRIV-3:
#   - Added Requires: for all runtime dependencies
#   - Moved scripts from /usr/bin to /usr/libexec (not publicly accessible)
#   - Added new qrexec handler files (qubes.ApplyAISystemState, aegis.AuditLogRead)
#   - Added %post hook to create required directories and aegis-ai system user
#   - Tightened file permissions (0700 for Dom0-only scripts, not 0755)

Requires:       python3 >= 3.10
Requires:       python3-pyyaml
Requires:       zenity
Requires:       audit
# python3-pam is required for grave-risk PAM verification
Requires:       python3-pam

%description
Provides qrexec policies, confirmation scripts, SaltStack formulas, and
qrexec service handlers for the Qubes Aegis AI Fork.

Includes:
  - 30-aegis.policy: qrexec access control rules for the aegis.* namespace
  - aegis-confirm.py: Dom0 GUI confirmation dialogs with PAM verification
  - qubes.ApplyAISystemState: SaltStack state validation pipeline (spec §2)
  - aegis.AuditLogRead: Sanitized audit log streaming service (spec §7)
  - Salt formulas: Declarative VM provisioning states

%install
# ── qrexec Policy ───────────────────────────────────────────────────────────
mkdir -p %{buildroot}/etc/qubes/policy.d/
install -m 0644 30-aegis.policy %{buildroot}/etc/qubes/policy.d/

# ── Dom0 Scripts (libexec — not in $PATH for regular users) ─────────────────
mkdir -p %{buildroot}/usr/libexec/qubes-aegis/
install -m 0700 aegis-confirm.py %{buildroot}/usr/libexec/qubes-aegis/
install -m 0700 aegis-audit-export.sh %{buildroot}/usr/libexec/qubes-aegis/
install -m 0700 ../sys-ai-builder/deploy-llama-to-template.sh %{buildroot}/usr/libexec/qubes-aegis/
install -m 0700 ../sys-ai-builder/destroy-builder.sh %{buildroot}/usr/libexec/qubes-aegis/

# ── qrexec Service Handlers ─────────────────────────────────────────────────
mkdir -p %{buildroot}/etc/qubes-rpc/
install -m 0755 qubes.ApplyAISystemState %{buildroot}/etc/qubes-rpc/
install -m 0755 aegis.AuditLogRead %{buildroot}/etc/qubes-rpc/
install -m 0755 aegis.DelegateSubagent %{buildroot}/etc/qubes-rpc/

# Documentation rebuild RPC handler
install -m 0755 aegis.RequestDocBuild %{buildroot}/etc/qubes-rpc/
install -m 0755 deploy-subagent-template.sh %{buildroot}/usr/libexec/qubes-aegis/
install -m 0755 aegis.SetNetVM %{buildroot}/etc/qubes-rpc/
install -m 0755 aegis.ModifyTemplate %{buildroot}/etc/qubes-rpc/
install -m 0755 aegis.RunDispVMScript %{buildroot}/etc/qubes-rpc/
install -m 0755 aegis.HardwareInfo %{buildroot}/etc/qubes-rpc/
install -m 0755 aegis.TriggerKnowledgeMaint %{buildroot}/etc/qubes-rpc/
install -m 0755 aegis.ConfigureAI %{buildroot}/etc/qubes-rpc/
install -m 0755 aegis.ManagePCI %{buildroot}/etc/qubes-rpc/

mkdir -p %{buildroot}/usr/libexec/qubes-aegis/
install -m 0755 aegis-first-boot.py %{buildroot}/usr/libexec/qubes-aegis/

mkdir -p %{buildroot}/etc/qubes/rpc-config/
echo "user=root" > %{buildroot}/etc/qubes/rpc-config/aegis.RequestDocBuild


# ── Salt Formulas ────────────────────────────────────────────────────────────
mkdir -p %{buildroot}/srv/salt/aegis/
mkdir -p %{buildroot}/srv/salt/_tops/
install -m 0644 ../salt/aegis-setup.top %{buildroot}/srv/salt/_tops/
install -m 0644 ../salt/init.sls %{buildroot}/srv/salt/aegis/
install -m 0644 ../salt/sys-ai.sls %{buildroot}/srv/salt/aegis/
install -m 0644 ../salt/sys-copilot.sls %{buildroot}/srv/salt/aegis/
install -m 0644 ../salt/sys-knowledge.sls %{buildroot}/srv/salt/aegis/
install -m 0644 ../salt/sys-ai-builder.sls %{buildroot}/srv/salt/aegis/
install -m 0755 ../sys-ai-builder/build-llama-in-builder.sh %{buildroot}/srv/salt/aegis/

# ── Log directory ────────────────────────────────────────────────────────────
mkdir -p %{buildroot}/var/log/qubes-aegis/

# ── DNF Plugin ────────────────────────────────────────────────────────────────
mkdir -p %{buildroot}%{python3_sitelib}/dnf-plugins/
install -m 0644 aegis_prevent_suppression.py %{buildroot}%{python3_sitelib}/dnf-plugins/

%post
# Create runtime directory for qrexec state files
install -d -m 0750 -o root -g qubes /var/run/qubes-aegis || true
install -d -m 0750 -o root -g root /var/log/qubes-aegis || true

# Create dedicated service account for llama-server (used by sys-ai template)
# This user has no shell and no home directory
getent group aegis-ai > /dev/null 2>&1 || groupadd --system aegis-ai
getent passwd aegis-ai > /dev/null 2>&1 || \
    useradd --system --no-create-home --shell /sbin/nologin \
            --gid aegis-ai --comment "Aegis AI Inference Service" aegis-ai

mkdir -p /var/lib/aegis-builds

%preun
# Nothing to undo — policy files are managed by the package manager

%files
%attr(0644, root, root) /etc/qubes/policy.d/30-aegis.policy
%attr(0700, root, root) /usr/libexec/qubes-aegis/aegis-confirm.py
%attr(0700, root, root) /usr/libexec/qubes-aegis/aegis-audit-export.sh
%attr(0700, root, root) /usr/libexec/qubes-aegis/deploy-llama-to-template.sh
%attr(0700, root, root) /usr/libexec/qubes-aegis/destroy-builder.sh
%attr(0755, root, root) /etc/qubes-rpc/qubes.ApplyAISystemState
%attr(0755, root, root) /etc/qubes-rpc/aegis.DelegateSubagent
%attr(0755, root, root) /etc/qubes-rpc/aegis.RequestDocBuild
%attr(0755, root, root) /usr/libexec/qubes-aegis/deploy-subagent-template.sh
%attr(0755, root, root) /etc/qubes-rpc/aegis.SetNetVM
%attr(0755, root, root) /etc/qubes-rpc/aegis.ModifyTemplate
%attr(0755, root, root) /etc/qubes-rpc/aegis.RunDispVMScript
%attr(0755, root, root) /etc/qubes-rpc/aegis.HardwareInfo
%attr(0755, root, root) /etc/qubes-rpc/aegis.TriggerKnowledgeMaint
%attr(0755, root, root) /etc/qubes-rpc/aegis.ConfigureAI
%attr(0755, root, root) /etc/qubes-rpc/aegis.ManagePCI
%attr(0755, root, root) /usr/libexec/qubes-aegis/aegis-first-boot.py
%attr(0644, root, root) /etc/qubes/rpc-config/aegis.RequestDocBuild

%attr(0755, root, root) /etc/qubes-rpc/aegis.AuditLogRead
%attr(0644, root, root) /srv/salt/_tops/aegis-setup.top
%attr(0644, root, root) /srv/salt/aegis/init.sls
%attr(0644, root, root) /srv/salt/aegis/sys-ai.sls
%attr(0644, root, root) /srv/salt/aegis/sys-copilot.sls
%attr(0644, root, root) /srv/salt/aegis/sys-knowledge.sls
%attr(0644, root, root) /srv/salt/aegis/sys-ai-builder.sls
%attr(0755, root, root) /srv/salt/aegis/build-llama-in-builder.sh
%{python3_sitelib}/dnf-plugins/aegis_prevent_suppression.py
%dir %attr(0750, root, qubes) /var/run/qubes-aegis
%dir %attr(0750, root, root) /var/log/qubes-aegis

