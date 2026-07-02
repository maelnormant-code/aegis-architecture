# Aegis Malformed Test ISO - Kickstart Configuration (Unsigned 2)
# This file must fail validation because the packages section has no %end tag

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

repo --name="qubes-aegis-repo" --baseurl="https://github.com/maelnormant-code/aegis-architecture" --gpgkey="https://github.com/maelnormant-code/aegis-architecture/raw/main/keys/RPM-GPG-KEY-qubes-aegis"

%packages
@core
qubes-aegis-sys-copilot
# DELIBERATE ERROR: Missing %end tag here
