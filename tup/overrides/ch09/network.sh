#!/bin/bash
# OVERRIDE ch09/network: the book's page is placeholder-filled
# (<Your Domain Name>, <lfs>, 192.168.1.2). tup gets QEMU's user-mode network,
# which is a fixed, documented slirp: 10.0.2.15/24 via 10.0.2.2, DNS 10.0.2.3.
set -e
mkdir -p /etc/sysconfig
cat > /etc/sysconfig/ifconfig.eth0 << "IFEOF"
ONBOOT=yes
IFACE=eth0
SERVICE=ipv4-static
IP=10.0.2.15
GATEWAY=10.0.2.2
PREFIX=24
BROADCAST=10.0.2.255
IFEOF
cat > /etc/resolv.conf << "RESOLVEOF"
# Begin /etc/resolv.conf — QEMU user-mode DNS
nameserver 10.0.2.3
# End /etc/resolv.conf
RESOLVEOF
echo "tup" > /etc/hostname
cat > /etc/hosts << "HOSTSEOF"
# Begin /etc/hosts
127.0.0.1 localhost.localdomain localhost
127.0.1.1 tup.local tup
::1       localhost ip6-localhost ip6-loopback
ff02::1   ip6-allnodes
ff02::2   ip6-allrouters
# End /etc/hosts
HOSTSEOF
