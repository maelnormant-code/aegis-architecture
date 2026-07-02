# Aegis Unsigned Test ISO - Kickstart Configuration
# This file must fail validation because the Aegis repository is unsigned (missing gpgkey)

auth --enableshadow --passalgo=sha512
text
keyboard --vckeymap=us --xlayouts='us'
lang en_US.UTF-8
network --bootproto=dhcp --device=link --activate
rootpw --plaintext aegis_root_pass_temp
timezone UTC --isUtc
bootloader --location=mbr
clearpart --all --initlabel
autopart --type=thinpool

# Malformed/unsigned repo - missing --gpgkey parameter, should be rejected by qubes-builder validation checks
repo --name="qubes-aegis-repo" --baseurl="https://github.com/maelnormant-code/aegis-architecture"

%packages
@core
qubes-aegis-sys-copilot
%end
