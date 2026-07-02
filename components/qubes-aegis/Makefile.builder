# AUDIT FIX (2026-06-29):
#   - HIGH-ARCH-1: Added salt/ to DEBIAN_BUILD_DIRS and defined SALT_FORMULAS_DIR.
#                  Previously the Salt states were never installed on the target system.

RPM_SPEC_FILES := dom0/qubes-aegis-dom0.spec
RPM_SPEC_FILES += sys-ai/qubes-aegis-sys-ai.spec
RPM_SPEC_FILES += sys-copilot/qubes-aegis-sys-copilot.spec
RPM_SPEC_FILES += guest/qubes-aegis-guest.spec
RPM_SPEC_FILES += sys-knowledge/qubes-aegis-sys-knowledge.spec
RPM_SPEC_FILES += sys-vpn/qubes-aegis-sys-vpn.spec

# Include salt directory in Debian build layout
DEBIAN_BUILD_DIRS := dom0 sys-ai sys-copilot guest sys-knowledge sys-vpn salt

# Qubes Builder Salt formula integration
# Salt files are installed to /srv/salt/aegis/ on Dom0
SALT_FORMULAS_DIR := salt
