#!/bin/bash
source /tup-layer/common.sh
# System identity and the book's shell defaults. Nothing here is specific to
# one machine: no machine-id, host key, account or address is created.
#   https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter11/theend.html      (os-release format)
#   https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter09/network.html     (9.2.4 hostname)
#   https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter09/locale.html      (locale.conf, profile)
#   https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter09/inputrc.html
#   https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter09/etcshells.html
#   https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter09/systemd-custom.html (9.10.2)
# The core keeps /etc/hosts at localhost only; nss-myhostname resolves the host name.

# Each file is created new, never written through an existing symlink.
rm -f /etc/os-release /etc/hostname /etc/locale.conf /etc/profile /etc/inputrc /etc/shells

# A regular file with one ID=tup and one VERSION_ID line: boot/inputs.py
# check_offline_root() refuses anything else.
cat > /etc/os-release << "EOF"
NAME="TUP"
ID=tup
VERSION_ID=13.1
VERSION="13.1-systemd"
PRETTY_NAME="TUP 13.1 (Linux From Scratch 13.1-systemd)"
EOF

# The Multicast DNS name is this host name plus .local (see 02-network.sh).
echo "tup" > /etc/hostname

# Glibc always provides C.UTF-8; no locale has to be generated for it.
cat > /etc/locale.conf << "EOF"
LANG=C.UTF-8
EOF

cat > /etc/profile << "EOF"
# Begin /etc/profile

for i in $(locale); do
  unset ${i%=*}
done

if [[ "$TERM" = linux ]]; then
  export LANG=C.UTF-8
else
  source /etc/locale.conf

  for i in $(locale); do
    key=${i%=*}
    if [[ -v $key ]]; then
      export $key
    fi
  done
fi

# End /etc/profile
EOF

cat > /etc/inputrc << "EOF"
# Begin /etc/inputrc
# Modified by Chris Lynn <roryo@roryo.dynup.net>

# Allow the command prompt to wrap to the next line
set horizontal-scroll-mode Off

# Enable 8-bit input
set meta-flag On
set input-meta On

# Turns off 8th bit stripping
set convert-meta Off

# Keep the 8th bit for display
set output-meta On

# none, visible or audible
set bell-style none

# All of the following map the escape sequence of the value
# contained in the 1st argument to the readline specific functions
"\eOd": backward-word
"\eOc": forward-word

# for linux console
"\e[1~": beginning-of-line
"\e[4~": end-of-line
"\e[5~": beginning-of-history
"\e[6~": end-of-history
"\e[3~": delete-char
"\e[2~": quoted-insert

# for xterm
"\eOH": beginning-of-line
"\eOF": end-of-line

# for Konsole
"\e[H": beginning-of-line
"\e[F": end-of-line

# uncomment for history search mode with up/down
# "\e[A": history-search-backward
# "\e[B": history-search-forward

# End /etc/inputrc
EOF

cat > /etc/shells << "EOF"
# Begin /etc/shells

/bin/sh
/bin/bash

# End /etc/shells
EOF

# Keep boot and enrollment messages on tty1 instead of clearing them: a
# headless machine has no other local record of why SSH is on or off.
mkdir -pv /etc/systemd/system/getty@tty1.service.d

cat > /etc/systemd/system/getty@tty1.service.d/noclear.conf << EOF
[Service]
TTYVTDisallocate=no
EOF

# The kernel builds amdgpu as a module, and the boot chapter stages none of its
# firmware yet. When it binds, it takes the device away from the firmware's own
# framebuffer partway through initialization (Linux 6.18.60 amdgpu_device.c,
# aperture_remove_conflicting_pci_devices after early init), so a later failure
# could leave the integrated graphics without a console. Until the firmware is
# staged with it, udev must not load it on its own; the firmware framebuffer
# keeps driving the screen, and "modprobe amdgpu" by hand still works.
#   modprobe.d(5): "blacklist" stops loading through a module's aliases only.
mkdir -pv /etc/modprobe.d
rm -f /etc/modprobe.d/tup-graphics.conf
cat > /etc/modprobe.d/tup-graphics.conf << "EOF"
blacklist amdgpu
EOF

for file in /etc/os-release /etc/hostname /etc/locale.conf /etc/profile /etc/inputrc /etc/shells \
            /etc/modprobe.d/tup-graphics.conf; do
  [ -f "$file" ] && [ ! -L "$file" ] && [ -s "$file" ] || { echo "01-identity: $file was not written as a regular file" >&2; exit 1; }
done
