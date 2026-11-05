#!/bin/bash
# 9.2. General Network Configuration
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter09/network.html
# TUP_ACTION_PAGE
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment,replaceable-parameter
printf '%s\n' 'ch09/02-network.sh: named override required: native-policy-review, book-alternatives-or-judgment, replaceable-parameter' >&2
exit 97
: <<'TUP_UNSELECTED_f1b27e4b689a7a47f6a777b8d5307dd0a613df3a2d2e48061e4b88ee2b8e524e'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
systemctl disable systemd-networkd-wait-online
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
ln -s /dev/null /etc/systemd/network/99-default.link
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
cat > /etc/systemd/network/10-ether0.link << "EOF"
[Match]
# Change the MAC address as appropriate for your network device
MACAddress=12:34:45:78:90:AB

[Link]
Name=ether0
EOF
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
cat > /etc/systemd/network/10-eth-static.network << "EOF"
[Match]
Name=<network-device-name>

[Network]
Address=192.168.0.2/24
Gateway=192.168.0.1
DNS=192.168.0.1
Domains=<Your Domain Name>
EOF
# TUP_BLOCK_END=004

# TUP_BLOCK_BEGIN=005
cat > /etc/systemd/network/10-eth-dhcp.network << "EOF"
[Match]
Name=<network-device-name>

[Network]
DHCP=ipv4

[DHCPv4]
UseDomains=true
EOF
# TUP_BLOCK_END=005

# TUP_BLOCK_BEGIN=006
systemctl disable systemd-resolved
# TUP_BLOCK_END=006

# TUP_BLOCK_BEGIN=007
cat > /etc/resolv.conf << "EOF"
# Begin /etc/resolv.conf

domain <Your Domain Name>
nameserver <IP address of your primary nameserver>
nameserver <IP address of your secondary nameserver>

# End /etc/resolv.conf
EOF
# TUP_BLOCK_END=007

# TUP_BLOCK_BEGIN=008
echo "<lfs>" > /etc/hostname
# TUP_BLOCK_END=008

# TUP_BLOCK_BEGIN=009
cat > /etc/hosts << "EOF"
# Begin /etc/hosts

<192.168.0.2> <FQDN> [alias1] [alias2] ...
::1       ip6-localhost ip6-loopback
ff02::1   ip6-allnodes
ff02::2   ip6-allrouters

# End /etc/hosts
EOF
# TUP_BLOCK_END=009
TUP_UNSELECTED_f1b27e4b689a7a47f6a777b8d5307dd0a613df3a2d2e48061e4b88ee2b8e524e
