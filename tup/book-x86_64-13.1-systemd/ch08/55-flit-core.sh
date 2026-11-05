#!/bin/bash
# 8.55. Flit-Core-4.0.2
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/flit-core.html
# TUP_TARBALL=flit_core-4.0.2.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/55-flit-core.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_029f205d3258aadd533a344148b8bf95956f8c9bd1c47f824532b4593200632f'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
pip3 wheel -w dist --no-cache-dir --no-build-isolation --no-deps $PWD
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
pip3 install --no-index --find-links dist flit_core
# TUP_BLOCK_END=002
TUP_UNSELECTED_029f205d3258aadd533a344148b8bf95956f8c9bd1c47f824532b4593200632f
