# Aegis Test ISO - Kickstart Configuration (Online Testing)
# Designed for automated ISO generation and verification.

# System Authorization
auth --enableshadow --passalgo=sha512
# Use graphical or text install
text
# Keyboard layouts
keyboard --vckeymap=us --xlayouts='us'
# System language
lang en_US.UTF-8

# Network information
network --bootproto=dhcp --device=link --activate

# Root password
rootpw --plaintext aegis_root_pass_temp

# System timezone
timezone UTC --isUtc

# Disk partitioning / bootloader
bootloader --location=mbr
clearpart --all --initlabel
autopart --type=thinpool

# Setup repository sources for Aegis
repo --name="qubes-aegis-repo" --baseurl="https://github.com/maelnormant-code/aegis-architecture" --gpgkey="https://github.com/maelnormant-code/aegis-architecture/raw/main/keys/RPM-GPG-KEY-qubes-aegis"

# Aegis specific templates and components installation
%packages
@core
chrony
# Aegis Core Components
qubes-aegis-sys-copilot
qubes-aegis-sys-ai
qubes-aegis-sys-ai-builder
%end

%post --log=/root/aegis-post-install.log
echo "Configuring Aegis Qubes templates..."
%end
