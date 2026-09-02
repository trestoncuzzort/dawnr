# 10.4. Using GRUB to Set Up the Boot Process
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter10/grub.html
# TUP_ACTION_PAGE

cd /tmp
grub-mkrescue --output=grub-img.iso
xorriso -as cdrecord -v dev=/dev/cdrw blank=as_needed grub-img.iso

grub-install /dev/sda

cat > /boot/grub/grub.cfg << "EOF"
# Begin /boot/grub/grub.cfg
set default=0
set timeout=5

insmod part_gpt
insmod ext2
set root=(hd0,2)
set gfxpayload=1024x768x32

menuentry "GNU/Linux, Linux 6.16.1-lfs-12.4" {
        linux   /boot/vmlinuz-6.16.1-lfs-12.4 root=/dev/sda2 ro
}
EOF
