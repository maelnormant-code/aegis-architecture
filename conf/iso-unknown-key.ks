# Aegis Unknown Key Test ISO - Kickstart Configuration
# This file must fail validation because it references an unknown, invalid, or non-existent GPG key

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

# Uses an unknown/non-existent key file path which should trigger validation failure
repo --name="qubes-aegis-repo" --baseurl="https://github.com/maelnormant-code/aegis-architecture" --gpgkey="file:///etc/pki/rpm-gpg/RPM-GPG-KEY-UNKNOWN-NONEXISTENT"

%packages
@core
qubes-aegis-sys-copilot
%end
