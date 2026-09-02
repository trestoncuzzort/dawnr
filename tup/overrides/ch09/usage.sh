#!/bin/bash
# OVERRIDE ch09/usage: the book's bootscript config, byte for byte, plus
# ONE addition tup needs: an agetty on the serial console. tup boots under
# QEMU with console= pointing at that port, so without this line the system
# comes up correctly and offers a login prompt on virtual consoles nobody can
# see. The boot witness is a login prompt on the serial console; this is the
# line that produces it. The port is the one fact that differs per arch:
# ttyAMA0 (PL011) on the arm64 virt machine, ttyS0 (8250) on x86 q35.
set -e
PAGE="$TUP_PAGE"
[ -s "$PAGE" ] || { echo "override: cannot find the usage page"; exit 1; }
case "${TUP_ARCH:?TUP_ARCH must be set by the driver}" in
  arm64)  TTY=ttyAMA0 ;;
  x86_64) TTY=ttyS0 ;;
  *) echo "override: no serial console known for arch $TUP_ARCH"; exit 1 ;;
esac
sed "s|^1:2345:respawn:/sbin/agetty --noclear tty1 9600\$|S0:2345:respawn:/sbin/agetty --noclear $TTY 115200 vt100\n1:2345:respawn:/sbin/agetty --noclear tty1 9600|" \
  "$PAGE" > /tmp/usage-serial.sh
grep -q "agetty --noclear $TTY" /tmp/usage-serial.sh || { echo "override: agetty substitution missed"; exit 1; }
bash -e /tmp/usage-serial.sh
