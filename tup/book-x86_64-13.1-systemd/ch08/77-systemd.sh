#!/bin/bash
# 8.77. Systemd-261.2
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/systemd.html
# TUP_TARBALL=systemd-261.2.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch08/77-systemd.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_57d4ee0f02b3aeb0be6257f276b60708dbadea3162823fe3cd2cc8456f73bb3d'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
sed -e 's/GROUP="render"/GROUP="video"/' \
    -e 's/GROUP="sgx", //'               \
    -i rules.d/50-udev-default.rules.in
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
mkdir -p build
cd       build

meson setup ..                \
      --prefix=/usr           \
      --buildtype=release     \
      -D default-dnssec=no    \
      -D firstboot=false      \
      -D install-tests=false  \
      -D ldconfig=false       \
      -D sysusers=false       \
      -D rpmmacrosdir=no      \
      -D homed=disabled       \
      -D man=disabled         \
      -D mode=release         \
      -D pamconfdir=no        \
      -D dev-kvm-mode=0660    \
      -D nobody-group=nogroup \
      -D sysupdate=disabled   \
      -D ukify=disabled       \
      -D docdir=/usr/share/doc/systemd-261.2
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
ninja
# TUP_BLOCK_END=003

if tup_tests_enabled "systemd"; then
# TUP_BLOCK_BEGIN=004
echo 'NAME="Linux From Scratch"' > /etc/os-release
unshare -m ninja test
# TUP_BLOCK_END=004
else tup_receipt_skip_tests "ch08/77-systemd.sh:block-004"; fi

# TUP_BLOCK_BEGIN=005
ninja install
# TUP_BLOCK_END=005

# TUP_BLOCK_BEGIN=006
tar -xf ../../systemd-man-pages-261.2.tar.xz \
    --no-same-owner --strip-components=1     \
    -C /usr/share/man
# TUP_BLOCK_END=006

# TUP_BLOCK_BEGIN=007
systemd-machine-id-setup
# TUP_BLOCK_END=007

# TUP_BLOCK_BEGIN=008
systemctl preset-all
# TUP_BLOCK_END=008
TUP_UNSELECTED_57d4ee0f02b3aeb0be6257f276b60708dbadea3162823fe3cd2cc8456f73bb3d
