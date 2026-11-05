#!/bin/bash
# 8.34. Sed-4.10
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/sed.html
# TUP_TARBALL=sed-4.10.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/34-sed.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_7718779864e053f0bb37f7140badd6630ab138b3f5ace64b12e2ab0615bc803f'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
make html
# TUP_BLOCK_END=002

if tup_tests_enabled "sed"; then
# TUP_BLOCK_BEGIN=003
chown -R tester .
su tester -c "PATH=$PATH make check"
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/34-sed.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
install -vDm644 doc/sed.html -t /usr/share/doc/sed-4.10
# TUP_BLOCK_END=004
TUP_UNSELECTED_7718779864e053f0bb37f7140badd6630ab138b3f5ace64b12e2ab0615bc803f
