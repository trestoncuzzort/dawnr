#!/bin/bash
# 8.76. Jinja2-3.1.6
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/jinja2.html
# TUP_TARBALL=jinja2-3.1.6.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch08/76-jinja2.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_aa95266758830642f968827e331290fd01ae6b54367e91a32cf7cc0f8bc44ef5'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
pip3 wheel -w dist --no-cache-dir --no-build-isolation --no-deps $PWD
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
pip3 install --no-index --find-links dist Jinja2
# TUP_BLOCK_END=002
TUP_UNSELECTED_aa95266758830642f968827e331290fd01ae6b54367e91a32cf7cc0f8bc44ef5
