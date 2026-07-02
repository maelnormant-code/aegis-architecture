# sys-ai-builder — Air-Gapped Build Pipeline for llama-server

## Overview

The `sys-ai` inference VM has `NetVM: none` (fully air-gapped). It cannot
download source code or binaries from the internet. Instead, we use an
ephemeral, network-connected **`sys-ai-builder`** VM to:

1. Download a pinned llama.cpp source tarball
2. Verify its SHA256 hash
3. Compile `llama-server` with static linking
4. Transfer the binary to Dom0
5. Verify the binary's SHA256 in Dom0
6. Install the binary to the `sys-ai` template
7. Destroy `sys-ai-builder`

## Usage

From Dom0:

```bash
sudo /usr/libexec/qubes-aegis/orchestrate-build.sh [template-name]
```

Default template name is `sys-ai`.

## First-Time Setup

1. **Verify the source tarball hash:**
   - Download the tarball manually on a trusted machine
   - Compute: `sha256sum llama.cpp-b5000.tar.gz`
   - Update `EXPECTED_SOURCE_SHA256` in `build-llama-in-builder.sh`

2. **Run the first build:**
   - Execute `orchestrate-build.sh`
   - Record the output binary SHA256

3. **Update verification pins:**
   - Fill in `dom0/llama-build-pins.json`
   - Fill in `dom0/attestation-pins.json` (for vTPM Feature 3)
   - Update `EXPECTED_BINARY_SHA256` in `deploy-llama-to-template.sh`

## Security Model

- Source is verified via SHA256 before compilation
- Binary is verified via SHA256 before installation
- `sha256sum -c` is used (not bash string comparison) to avoid timing attacks
- Builder VM has `maxmem` cap and uses `sys-firewall` (not `sys-whonix`)
- Builder VM is destroyed even if the build fails (via bash `trap`)

## Files

| File | Runs In | Purpose |
|------|---------|--------|
| `build-llama-in-builder.sh` | sys-ai-builder | Downloads, verifies, compiles |
| `deploy-llama-to-template.sh` | Dom0 | Verifies binary, installs to template |
| `destroy-builder.sh` | Dom0 | Destroys the builder VM |
| `orchestrate-build.sh` | Dom0 | Master script that coordinates everything |
