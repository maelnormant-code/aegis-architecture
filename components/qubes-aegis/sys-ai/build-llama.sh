#!/bin/bash
# This directory previously contained a live git-clone script for llama.cpp.
# In accordance with spec §12, this is now built in an ephemeral,
# network-connected sys-ai-builder VM and pushed securely via qvm-copy
# to the offline sys-ai template.
#
# See sys-ai-builder/ for the new secure supply chain scripts.

echo "This script is deprecated. Use sys-ai-builder/orchestrate-build.sh to build llama-server."
exit 1
