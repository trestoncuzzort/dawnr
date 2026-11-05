#!/bin/bash
# 8.19. DejaGNU-1.6.3
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/dejagnu.html
# TUP_TARBALL=dejagnu-1.6.3.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/19-dejagnu.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_eed9fb540fe7165a1e8349fc092acbcfb62b361242cf5d356fb8f3ccfb9e441a'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
mkdir -v build
cd       build
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
../configure --prefix=/usr
makeinfo --html --no-split -o doc/dejagnu.html ../doc/dejagnu.texi
makeinfo --plaintext       -o doc/dejagnu.txt  ../doc/dejagnu.texi
# TUP_BLOCK_END=002

if tup_tests_enabled "dejagnu"; then
# TUP_BLOCK_BEGIN=003
make check
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/19-dejagnu.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
install -v -dm755  /usr/share/doc/dejagnu-1.6.3
install -v -m644   doc/dejagnu.{html,txt} /usr/share/doc/dejagnu-1.6.3
# TUP_BLOCK_END=004
TUP_UNSELECTED_eed9fb540fe7165a1e8349fc092acbcfb62b361242cf5d356fb8f3ccfb9e441a
