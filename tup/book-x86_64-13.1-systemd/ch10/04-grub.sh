#!/bin/bash
# 10.4. Using GRUB to Set Up the Boot Process
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter10/grub.html
# TUP_ACTION_PAGE
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment,replaceable-parameter
printf '%s\n' 'ch10/04-grub.sh: named override required: native-policy-review, book-alternatives-or-judgment, replaceable-parameter' >&2
exit 97
: <<'TUP_UNSELECTED_c107b64627135bbf0afc15a8fc7d9db98770cdd280bcd0f3c246915bcde3c0e0'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
cd /tmp
grub-mkrescue --output=grub-img.iso
xorriso -as cdrecord -v dev=/dev/cdrw blank=as_needed grub-img.iso
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
grub-install /dev/sda --target=i386-pc
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
grub-install --target=x86_64-efi --removable
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
mountpoint /sys/firmware/efi/efivars ||
  mount -v -t efivarfs efivarfs /sys/firmware/efi/efivars
# TUP_BLOCK_END=004

# TUP_BLOCK_BEGIN=005
efibootmgr -c -d /dev/sd<x> \
  -p <y> -L "LFS" -l '\EFI\BOOT\BOOT<X64>.EFI'
# TUP_BLOCK_END=005

# TUP_BLOCK_BEGIN=006
umount -v /sys/firmware/efi/efivars
# TUP_BLOCK_END=006

# TUP_BLOCK_BEGIN=007
cat > /boot/grub/grub.cfg << "EOF"
# Begin /boot/grub/grub.cfg
set default=0
set timeout=5

insmod part_gpt
insmod ext2

set root=(hd0,2)
set gfxpayload=1024x768x32

menuentry "GNU/Linux, Linux 7.1.8-lfs-13.1-systemd" {
        linux   /boot/vmlinuz-7.1.8-lfs-13.1-systemd root=/dev/sda2 ro
}
EOF
# TUP_BLOCK_END=007
TUP_UNSELECTED_c107b64627135bbf0afc15a8fc7d9db98770cdd280bcd0f3c246915bcde3c0e0
