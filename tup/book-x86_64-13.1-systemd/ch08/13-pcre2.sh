#!/bin/bash
# 8.13. Pcre2-10.47
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/pcre2.html
# TUP_TARBALL=pcre2-10.47.tar.bz2
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/13-pcre2.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_7f027a58c68a53bfd07eef8508992eb9ca0ecdeff787f52127d9092d98ce43d6'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr                       \
            --docdir=/usr/share/doc/pcre2-10.47 \
            --enable-unicode                    \
            --enable-jit                        \
            --enable-pcre2-16                   \
            --enable-pcre2-32                   \
            --enable-pcre2grep-libz             \
            --enable-pcre2grep-libbz2           \
            --enable-pcre2test-libreadline      \
            --disable-static
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

if tup_tests_enabled "pcre2"; then
# TUP_BLOCK_BEGIN=003
make check
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/13-pcre2.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004
TUP_UNSELECTED_7f027a58c68a53bfd07eef8508992eb9ca0ecdeff787f52127d9092d98ce43d6
