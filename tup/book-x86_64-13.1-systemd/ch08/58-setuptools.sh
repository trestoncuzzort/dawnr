#!/bin/bash
# 8.58. Setuptools-84.0.0
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/setuptools.html
# TUP_TARBALL=setuptools-84.0.0.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/58-setuptools.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_8a79edbba8112c32a2adb72130a58d519cbf0929b843bf90a44195b748984937'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
pip3 wheel -w dist --no-cache-dir --no-build-isolation --no-deps $PWD
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
pip3 install --no-index --find-links dist setuptools
# TUP_BLOCK_END=002
TUP_UNSELECTED_8a79edbba8112c32a2adb72130a58d519cbf0929b843bf90a44195b748984937
