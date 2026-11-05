#!/bin/bash
# 8.57. Wheel-0.48.0
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/wheel.html
# TUP_TARBALL=wheel-0.48.0.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/57-wheel.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_a86f46b50b695981c99a72124187951fe57a3a6614db3196b6da6b8e7f385287'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
pip3 wheel -w dist --no-cache-dir --no-build-isolation --no-deps $PWD
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
pip3 install --no-index --find-links dist wheel
# TUP_BLOCK_END=002
TUP_UNSELECTED_a86f46b50b695981c99a72124187951fe57a3a6614db3196b6da6b8e7f385287
