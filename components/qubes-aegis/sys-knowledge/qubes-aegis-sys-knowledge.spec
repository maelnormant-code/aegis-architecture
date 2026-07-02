Name:           qubes-aegis-sys-knowledge
Version:        1.0.0
Release:        1%{?dist}
Summary:        Aegis Copilot — sys-knowledge RAG VM components

License:        GPLv2+
URL:            https://github.com/qubes-aegis/qubes-aegis

Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch
Requires:       python3 >= 3.10

%description
Components for the Aegis sys-knowledge air-gapped RAG VM.
Provides the aegis.KnowledgeQuery qrexec RPC handler that queries
a local SQLite FTS5 knowledge database and returns sanitised snippets.

The knowledge database is built offline by sys-knowledge-builder and
deployed via SHA256-verified qvm-copy from Dom0.

%install
# qrexec RPC handler
mkdir -p %{buildroot}/etc/qubes-rpc
install -m 0755 aegis.KnowledgeQuery %{buildroot}/etc/qubes-rpc/aegis.KnowledgeQuery

# qrexec RPC config to run under aegis-knowledge user
mkdir -p %{buildroot}/etc/qubes/rpc-config
echo "user=aegis-knowledge" > %{buildroot}/etc/qubes/rpc-config/aegis.KnowledgeQuery

# systemd unit
mkdir -p %{buildroot}/usr/lib/systemd/system
install -m 0644 aegis-knowledge-server.service %{buildroot}/usr/lib/systemd/system/aegis-knowledge-server.service

# Database directory
mkdir -p %{buildroot}/var/lib/aegis

%pre
# Create service account
getent group aegis-knowledge >/dev/null || groupadd -r aegis-knowledge
getent passwd aegis-knowledge >/dev/null || \
    useradd -r -g aegis-knowledge -d /nonexistent -s /usr/sbin/nologin \
    -c "Aegis Knowledge Service" aegis-knowledge

%post
systemctl daemon-reload
systemctl enable aegis-knowledge-server.service

%preun
if [ $1 -eq 0 ]; then
    systemctl stop aegis-knowledge-server.service || true
    systemctl disable aegis-knowledge-server.service || true
fi

%postun
systemctl daemon-reload

%files
%attr(0755, root, root) /etc/qubes-rpc/aegis.KnowledgeQuery
%attr(0644, root, root) /etc/qubes/rpc-config/aegis.KnowledgeQuery
%attr(0644, root, root) /usr/lib/systemd/system/aegis-knowledge-server.service
%dir %attr(0750, aegis-knowledge, aegis-knowledge) /var/lib/aegis

%changelog
* Sun Jun 29 2025 Aegis Maintainer <aegis@qubes-os.org> - 1.0.0-1
- Initial package: KnowledgeQuery RPC handler and systemd unit
