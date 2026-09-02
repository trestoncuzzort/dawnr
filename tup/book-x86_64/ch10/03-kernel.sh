# 10.3. Linux-6.16.1
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter10/kernel.html
# TUP_TARBALL=linux-6.16.1.tar.xz

make mrproper

make menuconfig

make

make modules_install

mount /boot

cp -iv arch/x86/boot/bzImage /boot/vmlinuz-6.16.1-lfs-12.4

cp -iv System.map /boot/System.map-6.16.1

cp -iv .config /boot/config-6.16.1

cp -r Documentation -T /usr/share/doc/linux-6.16.1

install -v -m755 -d /etc/modprobe.d
cat > /etc/modprobe.d/usb.conf << "EOF"
# Begin /etc/modprobe.d/usb.conf

install ohci_hcd /sbin/modprobe ehci_hcd ; /sbin/modprobe -i ohci_hcd ; true
install uhci_hcd /sbin/modprobe ehci_hcd ; /sbin/modprobe -i uhci_hcd ; true

# End /etc/modprobe.d/usb.conf
EOF
