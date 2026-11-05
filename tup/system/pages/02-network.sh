#!/bin/bash
source /tup-layer/common.sh
# Wired DHCP with systemd-networkd, DNS and Multicast DNS with
# systemd-resolved, bounded journal and a bounded wait for "online".
# Configuration files only: 03-access.sh enables the services, and nothing is
# ever started in this chroot. No address, MAC or device name is written.
#   https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter09/network.html
#     (9.2.1 networkd and the wait-online note, 9.2.3 resolv.conf)
#   systemd 261.2 network/89-ethernet.network.example, systemd.network(5),
#     resolved.conf(5), journald.conf(5), systemd-networkd-wait-online.service(8)
fail() { echo "02-network: $*" >&2; exit 1; }

for unit in systemd-networkd.service systemd-resolved.service systemd-networkd-wait-online.service \
            systemd-timesyncd.service systemd-journald.service; do
  [ -f "/usr/lib/systemd/system/$unit" ] || fail "$unit is not installed"
done
[ -x /usr/lib/systemd/systemd-networkd-wait-online ] || fail "systemd-networkd-wait-online is not where its unit expects it"

mkdir -pv /etc/systemd/network /etc/systemd/resolved.conf.d /etc/systemd/journald.conf.d \
          /etc/systemd/system/systemd-networkd-wait-online.service.d \
          /etc/systemd/system/systemd-timesyncd.service.d

# The match is upstream's example for "all physical ethernet links"; Wi-Fi
# links have type wlan and virtual links have a kind, so neither matches.
# ClientIdentifier=mac: the image ships an empty machine-id and a live boot
# generates a new one every time, which would change a DUID-based identifier
# and with it the DHCP lease. The MAC keeps the same address across boots.
cat > /etc/systemd/network/20-wired.network << "EOF"
[Match]
Kind=!*
Type=ether

[Network]
DHCP=yes
MulticastDNS=yes
LLMNR=no

[DHCPv4]
ClientIdentifier=mac
EOF

# Multicast DNS is on for a link only when both this global switch and the
# per-link one above are on. The responder answers for <hostname>.local.
cat > /etc/systemd/resolved.conf.d/10-tup.conf << "EOF"
[Resolve]
MulticastDNS=yes
LLMNR=no
EOF

# The book lets systemd-resolved create this link when the file is absent;
# create the same link here so the image does not depend on first-boot tmpfiles.
ln -sfnv ../run/systemd/resolve/stub-resolv.conf /etc/resolv.conf

# A live boot keeps /var in memory; an installed system has a real disk.
cat > /etc/systemd/journald.conf.d/10-tup-size.conf << "EOF"
[Journal]
SystemMaxUse=256M
RuntimeMaxUse=64M
EOF

# network-online.target is wanted only by the exact-address SSH scope. Without
# a cable the default waits 120 seconds for every link; one configured link
# and 30 seconds are enough, and a timeout never blocks the rest of the boot.
cat > /etc/systemd/system/systemd-networkd-wait-online.service.d/10-tup-bounded.conf << "EOF"
[Service]
ExecStart=
ExecStart=/usr/lib/systemd/systemd-networkd-wait-online --any --timeout=30
EOF

# Once the system clock is synchronized, Linux on x86 copies it to the hardware
# clock about every eleven minutes, as UTC (kernel/time/ntp.c sync_hw_clock;
# arch/x86/Kconfig selects GENERIC_CMOS_UPDATE, so no option turns it off). A
# desktop that also boots Windows keeps local time in that clock, and Windows
# would then be wrong by its UTC offset. systemd-timesyncd therefore starts
# only once the owner has said the hardware clock is in UTC: enrollment input
# "clock" containing "utc" creates this file, as does creating it by hand.
cat > /etc/systemd/system/systemd-timesyncd.service.d/10-tup-hardware-clock.conf << "EOF"
[Unit]
ConditionPathExists=/etc/tup/hardware-clock-utc
EOF

[ "$(readlink /etc/resolv.conf)" = ../run/systemd/resolve/stub-resolv.conf ] || fail "/etc/resolv.conf is not the resolved stub link"
for file in /etc/systemd/network/20-wired.network /etc/systemd/resolved.conf.d/10-tup.conf \
            /etc/systemd/journald.conf.d/10-tup-size.conf \
            /etc/systemd/system/systemd-timesyncd.service.d/10-tup-hardware-clock.conf \
            /etc/systemd/system/systemd-networkd-wait-online.service.d/10-tup-bounded.conf; do
  [ -f "$file" ] && [ ! -L "$file" ] && [ -s "$file" ] || fail "$file was not written as a regular file"
done
