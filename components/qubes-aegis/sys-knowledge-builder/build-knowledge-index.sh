#!/bin/bash
# build-knowledge-index.sh — Runs in the networked sys-knowledge-builder VM.
# Downloads source documentation, builds a SQLite FTS5 index, and packages
# it as a SHA256-signed tarball for deployment to air-gapped sys-knowledge.
#
# Usage: ./build-knowledge-index.sh
# Output: /home/user/knowledge-index-output/knowledge-index.tar.gz
#         /home/user/knowledge-index-output/knowledge-index.sha256

set -euo pipefail

OUTPUT_DIR="/home/user/knowledge-index-output"
export DB_FILE="${OUTPUT_DIR}/knowledge.db"
TARBALL="${OUTPUT_DIR}/knowledge-index.tar.gz"
CHECKSUM_FILE="${OUTPUT_DIR}/knowledge-index.sha256"
export DOC_DIR="/tmp/aegis-knowledge-docs"

# ── Setup ────────────────────────────────────────────────
rm -rf "$OUTPUT_DIR" "$DOC_DIR"
mkdir -p "$OUTPUT_DIR" "$DOC_DIR"

echo "[*] Downloading Qubes OS documentation..."
# Download Qubes OS documentation pages
curl -fsSL "https://www.qubes-os.org/doc/" -o "${DOC_DIR}/qubes-doc-index.html" || true

# Download key Qubes OS documentation pages (20 pages)
for page in getting-started how-to-install-software how-to-update \
            backup-restore firewall disposablevm split-gpg \
            salt dom0-tools qrexec device-handling vpn whonix \
            templates security usb-devices pci-devices admin-api \
            windows-tools gui; do
    curl -fsSL "https://www.qubes-os.org/doc/${page}/" \
        -o "${DOC_DIR}/qubes-${page}.html" 2>/dev/null || true
    sleep 1  # Rate limiting
done

echo "[*] Downloading Linux Kernel documentation..."
curl -fsSL "https://www.kernel.org/doc/html/latest/admin-guide/sysctl/net.html" -o "${DOC_DIR}/linux-sysctl-net.html" || true
curl -fsSL "https://www.kernel.org/doc/html/latest/admin-guide/sysctl/vm.html" -o "${DOC_DIR}/linux-sysctl-vm.html" || true
curl -fsSL "https://www.kernel.org/doc/html/latest/admin-guide/sysctl/kernel.html" -o "${DOC_DIR}/linux-sysctl-kernel.html" || true
curl -fsSL "https://www.kernel.org/doc/html/latest/security/lsm.html" -o "${DOC_DIR}/linux-lsm.html" || true
curl -fsSL "https://www.kernel.org/doc/html/latest/networking/filter.html" -o "${DOC_DIR}/linux-ebpf-filter.html" || true
curl -fsSL "https://www.kernel.org/doc/html/latest/admin-guide/index.html" -o "${DOC_DIR}/linux-kernel-admin.html" || true
curl -fsSL "https://www.kernel.org/doc/html/latest/security/index.html" -o "${DOC_DIR}/linux-kernel-security.html" || true

echo "[*] Downloading Networking documentation..."
curl -fsSL "https://gitlab.torproject.org/tpo/core/torspec/-/raw/main/spec/tor-spec/cell-packet-format.md" -o "${DOC_DIR}/tor-cell-format.md" || true
curl -fsSL "https://gitlab.torproject.org/tpo/core/torspec/-/raw/main/spec/tor-spec/relay-cells.md" -o "${DOC_DIR}/tor-relay-cells.md" || true
curl -fsSL "https://gitlab.torproject.org/tpo/core/torspec/-/raw/main/spec/tor-spec/index.md" -o "${DOC_DIR}/tor-spec-index.md" || true
curl -fsSL "https://www.wireguard.com/quickstart/" -o "${DOC_DIR}/wireguard-quickstart.html" || true
curl -fsSL "https://raw.githubusercontent.com/OpenVPN/openvpn/master/doc/man-sections/generic-options.rst" -o "${DOC_DIR}/openvpn-options.rst" || true
curl -fsSL "https://www.kernel.org/doc/html/latest/networking/ip-sysctl.html" -o "${DOC_DIR}/linux-ip-sysctl.html" || true
curl -fsSL "https://raw.githubusercontent.com/i2p/i2p.i2p/master/README.md" -o "${DOC_DIR}/i2p-readme.md" || true

echo "[*] Downloading Coding and Configuration documentation..."
curl -fsSL "https://www.sqlite.org/fts5.html" -o "${DOC_DIR}/sqlite-fts5.html" || true
curl -fsSL "https://docs.saltproject.io/en/latest/ref/states/all/index.html" -o "${DOC_DIR}/salt-all-states.html" || true
curl -fsSL "https://raw.githubusercontent.com/python/cpython/main/Doc/library/sqlite3.rst" -o "${DOC_DIR}/python-sqlite3.rst" || true
curl -fsSL "https://docs.saltproject.io/en/latest/topics/states/index.html" -o "${DOC_DIR}/salt-states.html" 2>/dev/null || true

echo "[*] Gathering man pages..."
# Extract key man pages as plain text
for cmd in qvm-run qvm-copy qvm-prefs qvm-features qvm-firewall \
           qvm-start qvm-shutdown qvm-create qvm-remove qvm-ls \
           qubesctl salt-call; do
    if command -v "$cmd" &>/dev/null; then
        man -P cat "$cmd" > "${DOC_DIR}/man-${cmd}.txt" 2>/dev/null || true
    fi
done

echo "[*] Downloading Xen hypervisor documentation..."
curl -fsSL "https://downloads.xenproject.org/release/xen/4.18.0/xen-4.18.0.tar.gz" -o "${DOC_DIR}/xen-docs.tar.gz" || true
tar -xzf "${DOC_DIR}/xen-docs.tar.gz" -C "${DOC_DIR}" --wildcards "*/docs/*.txt" "*/docs/*.md" --strip-components=2 2>/dev/null || true
rm -f "${DOC_DIR}/xen-docs.tar.gz"

echo "[*] Creating Aegis Coding Conventions..."
cat << 'EOF' > "${DOC_DIR}/aegis-coding-conventions.md"
# Qubes Aegis Coding Conventions

Aegis enforces strict compartmentalization and security boundaries.

## Rules
- **No Direct Internet**: Execution VMs must not connect to the internet directly. Use `sys-knowledge` for retrieval.
- **Sanitization**: All input across qrexec boundaries must be rigorously sanitized. Rely on allowlists, not denylists.
- **Least Privilege**: Only request the exact qrexec policies required. Avoid wildcard `*` policies in `/etc/qubes-rpc/policy/`.
- **Python**: Use `#!/usr/bin/env python3`. Enforce strict type hints and avoid `eval` or `exec`.
- **Bash**: Start scripts with `set -euo pipefail`.
EOF

echo "[*] Processing supplemental documentation requests..."
# Auto-fetch topics requested by Heimdall via request_documentation().
# SECURITY: Only URLs from the hardcoded ALLOWED_URLS set may be fetched.
#           The allowlist here mirrors the TOPIC_URL_MAP in aegis.RequestDocBuild (Dom0).
#           Even if supplement.json is tampered with, no unlisted URL can be fetched.
SUPPLEMENT_FILE="/home/user/knowledge-supplement.json"
if [ -f "$SUPPLEMENT_FILE" ]; then
    python3 << 'SUPPLEMENT_PY'
import json, os, re, urllib.request, html

DOC_DIR = os.environ.get("DOC_DIR", "/tmp/aegis-knowledge-docs")
SUPPLEMENT_PATH = "/home/user/knowledge-supplement.json"

# ── Hardcoded URL allowlist (must stay in sync with aegis.RequestDocBuild) ──
ALLOWED_URLS = {
    "https://gitlab.com/apparmor/apparmor/-/raw/master/README.md",
    "https://raw.githubusercontent.com/torvalds/linux/master/Documentation/admin-guide/LSM/apparmor.rst",
    "https://raw.githubusercontent.com/SELinuxProject/selinux-notebook/main/src/selinux_overview.md",
    "https://www.kernel.org/doc/html/latest/admin-guide/LSM/SELinux.html",
    "https://www.netfilter.org/projects/nftables/manpage.html",
    "https://raw.githubusercontent.com/torvalds/linux/master/Documentation/networking/nf_conntrack-sysctl.rst",
    "https://www.netfilter.org/documentation/HOWTO/packet-filtering-HOWTO.txt",
    "https://raw.githubusercontent.com/systemd/systemd/main/README",
    "https://raw.githubusercontent.com/systemd/systemd/main/docs/SANDBOX.md",
    "https://www.qubes-os.org/doc/qrexec/",
    "https://www.qubes-os.org/doc/qrexec-internals/",
    "https://www.whonix.org/wiki/Documentation",
    "https://raw.githubusercontent.com/DNSCrypt/dnscrypt-proxy/master/README.md",
    "https://raw.githubusercontent.com/netblue30/firejail/master/README.md",
    "https://raw.githubusercontent.com/containers/bubblewrap/main/README.md",
    "https://www.kernel.org/doc/html/latest/userspace-api/seccomp_filter.html",
    "https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html",
    "https://www.kernel.org/doc/html/latest/admin-guide/namespaces/index.html",
    "https://raw.githubusercontent.com/torvalds/linux/master/Documentation/userspace-api/unshare.rst",
    "https://www.kernel.org/doc/html/latest/bpf/index.html",
    "https://www.kernel.org/doc/html/latest/bpf/instruction-set.html",
    "https://gitlab.com/cryptsetup/cryptsetup/-/raw/main/README.md",
    "https://raw.githubusercontent.com/tpm2-software/tpm2-tools/master/README.md",
    "https://raw.githubusercontent.com/VirusTotal/yara/master/README.md",
    "https://raw.githubusercontent.com/OISF/suricata/master/README.md",
    "https://raw.githubusercontent.com/zeek/zeek/master/README",
    "https://raw.githubusercontent.com/openssl/openssl/master/README.md",
    "https://raw.githubusercontent.com/openssl/openssl/master/doc/man7/ossl-guide-introduction.pod",
    "https://raw.githubusercontent.com/openssh/openssh-portable/master/README",
    "https://raw.githubusercontent.com/gpg/gnupg/master/README",
    "https://raw.githubusercontent.com/fail2ban/fail2ban/master/README.md",
    "https://www.kernel.org/doc/html/latest/userspace-api/audit/index.html",
    "https://raw.githubusercontent.com/xen-project/xen/master/README",
    "https://www.kernel.org/doc/html/latest/virt/kvm/index.html",
    "https://raw.githubusercontent.com/libvirt/libvirt/master/README.rst",
    "https://raw.githubusercontent.com/containers/podman/main/README.md",
    "https://raw.githubusercontent.com/ansible/ansible/devel/README.rst",
    "https://raw.githubusercontent.com/python/cpython/main/Doc/library/subprocess.rst",
    "https://raw.githubusercontent.com/python/cpython/main/Doc/library/os.rst",
    "https://www.gnu.org/software/bash/manual/bash.txt",
}

def strip_html(text):
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html.unescape(text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

try:
    with open(SUPPLEMENT_PATH, 'r') as f:
        entries = json.load(f)
    if not isinstance(entries, list):
        raise ValueError("supplement.json must be a JSON array")
except Exception as e:
    print(f'[!] Could not read supplement file: {e}')
    entries = []

fetched = 0
blocked = 0
for entry in entries:
    topic = str(entry.get('topic', 'unknown'))[:100]
    urls = entry.get('urls', [])
    for url in urls:
        # ── SECURITY: re-validate against allowlist ──────────────────
        if url not in ALLOWED_URLS:
            print(f'[BLOCKED] URL not in allowlist, skipping: {url!r}')
            blocked += 1
            continue
        # ── Safe to fetch ─────────────────────────────────────────────
        slug = re.sub(r'[^a-zA-Z0-9._-]', '_', url.split('/')[-1] or topic)
        out_path = os.path.join(DOC_DIR, f'supplement-{topic}-{slug}')
        try:
            req = urllib.request.Request(
                url, headers={'User-Agent': 'aegis-knowledge-builder/1.0'}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read().decode('utf-8', errors='replace')
            ct = resp.headers.get('content-type', '')
            if url.endswith('.html') or 'text/html' in ct:
                content = strip_html(content)
            with open(out_path, 'w') as f:
                f.write(content)
            print(f'[+] Supplement fetched: topic={topic!r} <- {url}')
            fetched += 1
        except Exception as e:
            print(f'[!] Failed to fetch {url}: {e}')

print(f'[*] Supplement: {fetched} fetched, {blocked} blocked (not in allowlist)')

# Archive processed supplement (prevents re-fetching on next run)
os.rename(SUPPLEMENT_PATH, SUPPLEMENT_PATH + '.done')
SUPPLEMENT_PY
fi

echo "[*] Building SQLite FTS5 knowledge database..."
# Create the SQLite database with FTS5 index
python3 << 'PYEOF'
import os
import sqlite3
import html
import re

DB_PATH = os.environ.get("DB_FILE", "/home/user/knowledge-index-output/knowledge.db")
DOC_DIR = os.environ.get("DOC_DIR", "/tmp/aegis-knowledge-docs")

def strip_html(text):
    """Remove HTML tags and decode entities."""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html.unescape(text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_sections(text, source):
    """Split text into topic-content pairs."""
    sections = []
    # Split on heading-like patterns
    parts = re.split(r'\n(?=#{1,3}\s|[A-Z][A-Z ]{5,})', text)
    for part in parts:
        part = part.strip()
        if len(part) < 20:
            continue
        lines = part.split('\n', 1)
        topic = lines[0].strip('#').strip()[:200]
        content = lines[1].strip() if len(lines) > 1 else part
        content = content[:2048]
        if topic and content:
            sections.append((topic, content, source))
    if not sections and len(text) > 20:
        sections.append((source, text[:2048], source))
    return sections

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute('''CREATE TABLE IF NOT EXISTS knowledge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT NOT NULL
)''')

cur.execute('''CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts
    USING fts5(topic, content, source, content=knowledge, content_rowid=id)''')

cur.execute('''CREATE TRIGGER IF NOT EXISTS knowledge_ai AFTER INSERT ON knowledge BEGIN
    INSERT INTO knowledge_fts(rowid, topic, content, source)
    VALUES (new.id, new.topic, new.content, new.source);
END''')

count = 0
for root, dirs, files in os.walk(DOC_DIR):
    for fname in sorted(files):
        fpath = os.path.join(root, fname)
        if not os.path.isfile(fpath):
            continue
        try:
            with open(fpath, 'r', errors='replace') as f:
                raw = f.read()
        except Exception:
            continue

        if fname.endswith('.html'):
            raw = strip_html(raw)

        source = os.path.relpath(fpath, DOC_DIR)
        sections = extract_sections(raw, source)
        for topic, content, src in sections:
            cur.execute(
                'INSERT INTO knowledge (topic, content, source) VALUES (?, ?, ?)',
                (topic, content, src)
            )
            count += 1

conn.commit()
conn.close()
print(f'[+] Indexed {count} sections into {DB_PATH}')
PYEOF

echo "[*] Packaging tarball..."
cd "$OUTPUT_DIR"
tar czf "$TARBALL" knowledge.db

echo "[*] Computing SHA256 checksum..."
sha256sum "knowledge-index.tar.gz" > "$CHECKSUM_FILE"

echo "[+] Knowledge index build complete."
echo "    Tarball:  $TARBALL"
echo "    Checksum: $(cat "$CHECKSUM_FILE")"
echo ""
echo "Next steps:"
echo "  1. Copy $CHECKSUM_FILE to Dom0"
echo "  2. Update the expected hash in verify-and-deploy-knowledge.sh"
echo "  3. Run verify-and-deploy-knowledge.sh in Dom0 to push to sys-knowledge"
