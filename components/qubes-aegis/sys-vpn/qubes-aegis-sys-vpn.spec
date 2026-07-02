Name:           qubes-aegis-sys-vpn
Version:        1.0.0
Release:        1%{?dist}
Summary:        Sys-VPN components for Qubes Aegis AI Fork
License:        MIT
BuildArch:      noarch

Requires:       wireguard-tools
Requires:       syncthing
Requires:       python3 >= 3.10

%description
Provides the server-side peer components for Aegis Tunnel App integration in sys-vpn:
  - aegis-tunnel-proxy.py: REST API server mapping wireguard-tunnel requests to secure qrexec
  - aegis-tunnel-proxy.service: systemd service running the proxy
  - wg0.conf: WireGuard gateway configuration template

%install
mkdir -p %{buildroot}/usr/libexec/qubes-aegis/
install -m 0755 aegis-tunnel-proxy.py %{buildroot}/usr/libexec/qubes-aegis/

mkdir -p %{buildroot}/usr/lib/systemd/system/
install -m 0644 aegis-tunnel-proxy.service %{buildroot}/usr/lib/systemd/system/

mkdir -p %{buildroot}/etc/wireguard/
install -m 0600 wg0.conf %{buildroot}/etc/wireguard/

%post
systemctl daemon-reload
systemctl enable aegis-tunnel-proxy.service

%preun
if [ $1 -eq 0 ]; then
    systemctl stop aegis-tunnel-proxy.service || true
    systemctl disable aegis-tunnel-proxy.service || true
fi

%postun
systemctl daemon-reload

%files
%attr(0755, root, root) /usr/libexec/qubes-aegis/aegis-tunnel-proxy.py
%attr(0644, root, root) /usr/lib/systemd/system/aegis-tunnel-proxy.service
%config(noreplace) %attr(0600, root, root) /etc/wireguard/wg0.conf
