#!/bin/bash
# 8.56. Packaging-26.3
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/packaging.html
# TUP_TARBALL=packaging-26.3.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/56-packaging.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_d8d9c366fb463ffb388e37d048f5f9c9bb74c192f1b442e7939d5042994e9364'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
pip3 wheel -w dist --no-cache-dir --no-build-isolation --no-deps $PWD
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
pip3 install --no-index --find-links dist packaging
# TUP_BLOCK_END=002
TUP_UNSELECTED_d8d9c366fb463ffb388e37d048f5f9c9bb74c192f1b442e7939d5042994e9364
