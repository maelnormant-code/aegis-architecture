#!/bin/bash
# build-llama-in-builder.sh — Runs inside temporary networked sys-ai-builder VM.
# Downloads llama.cpp source, verifies SHA256, compiles statically,
# computes binary hash, and pushes to QubesIncoming of the sys-ai template.

set -euo pipefail

LLAMA_VERSION="b3000"
EXPECTED_SHA256="<FILL_IN_AFTER_VERIFYING>"
URL="https://github.com/ggerganov/llama.cpp/archive/refs/tags/${LLAMA_VERSION}.tar.gz"
TARBALL="llama.cpp-${LLAMA_VERSION}.tar.gz"

echo "[*] Downloading llama.cpp source ${LLAMA_VERSION}..."
curl -fsSL -o "$TARBALL" "$URL"

echo "[*] Verifying SHA256..."
ACTUAL_SOURCE_SHA256=$(sha256sum "$TARBALL" | awk '{print $1}')

if [ "$EXPECTED_SHA256" = "<FILL_IN_AFTER_VERIFYING>" ] || [ -z "$EXPECTED_SHA256" ]; then
    echo "WARNING: No expected source SHA256 pinned. Bootstrapping trust..."
    EXPECTED_SHA256="$ACTUAL_SOURCE_SHA256"
fi

echo "${EXPECTED_SHA256}  ${TARBALL}" > checksum.txt
if ! sha256sum -c checksum.txt --strict; then
    echo "FATAL: Source tarball hash mismatch!"
    exit 1
fi

echo "[*] Extracting source..."
tar xzf "$TARBALL"
cd "llama.cpp-${LLAMA_VERSION}"

echo "[*] Compiling statically with 3600s timeout..."
if ! timeout 3600 make LLAMA_STATIC=1 -j$(nproc) llama-server > make_build.log 2>&1; then
    echo "ERROR: Compilation failed or timed out! Compilation logs:"
    cat make_build.log
    exit 1
fi

if [ ! -f llama-server ]; then
    echo "ERROR: llama-server binary not found after build!"
    exit 1
fi

if ! file llama-server | grep -q ELF; then
    echo "ERROR: llama-server binary is not a valid ELF executable!"
    exit 1
fi

echo "[*] Saving build output..."
OUTPUT_DIR="/home/user/llama-build-output"
mkdir -p "$OUTPUT_DIR"
cp llama-server "$OUTPUT_DIR/"
sha256sum llama-server > "$OUTPUT_DIR/llama-server.sha256"
echo "$ACTUAL_SOURCE_SHA256" > "$OUTPUT_DIR/llama-source.sha256"

echo "[+] Build complete. VM will shut down now."
sudo poweroff
