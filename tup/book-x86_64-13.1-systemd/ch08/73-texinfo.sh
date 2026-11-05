#!/bin/bash
# 8.73. Texinfo-7.3
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/texinfo.html
# TUP_TARBALL=texinfo-7.3.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch08/73-texinfo.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_c6317cadb78a54dedd8f087d34544029a75111b4260d60fb5b5d6f5ab0a86dcb'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
./configure --prefix=/usr
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

if tup_tests_enabled "texinfo"; then
# TUP_BLOCK_BEGIN=003
make check
# TUP_BLOCK_END=003
else tup_receipt_skip_tests "ch08/73-texinfo.sh:block-003"; fi

# TUP_BLOCK_BEGIN=004
make install
# TUP_BLOCK_END=004

# TUP_BLOCK_BEGIN=005
make TEXMF=/usr/share/texmf install-tex
# TUP_BLOCK_END=005

# TUP_BLOCK_BEGIN=006
pushd /usr/share/info
  rm -v dir
  for f in *
    do install-info $f dir 2>/dev/null
  done
popd
# TUP_BLOCK_END=006
TUP_UNSELECTED_c6317cadb78a54dedd8f087d34544029a75111b4260d60fb5b5d6f5ab0a86dcb
