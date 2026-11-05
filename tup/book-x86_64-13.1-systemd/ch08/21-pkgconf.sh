#!/bin/bash
# 8.21. Pkgconf-3.0.5
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/pkgconf.html
# TUP_TARBALL=pkgconf-3.0.5.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/21-pkgconf.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_cc2e35e1dedb3b41a5676f991b0020e5a3754d53b122090cbfff9f9d4830895a'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
tar -xf ../meson-1.12.0.tar.gz
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
mkdir build
cd    build

python3 ../meson-1.12.0/meson.py setup --prefix=/usr --buildtype=release ..
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
ninja
# TUP_BLOCK_END=003

if tup_tests_enabled "pkgconf"; then
# TUP_BLOCK_BEGIN=004
ninja test
# TUP_BLOCK_END=004
else tup_receipt_skip_tests "ch08/21-pkgconf.sh:block-004"; fi

# TUP_BLOCK_BEGIN=005
ninja install
mv /usr/share/doc/pkgconf{,-3.0.5}
# TUP_BLOCK_END=005

# TUP_BLOCK_BEGIN=006
ln -sv pkgconf   /usr/bin/pkg-config
ln -sv pkgconf.1 /usr/share/man/man1/pkg-config.1
# TUP_BLOCK_END=006
TUP_UNSELECTED_cc2e35e1dedb3b41a5676f991b0020e5a3754d53b122090cbfff9f9d4830895a
