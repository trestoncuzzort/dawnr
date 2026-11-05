#!/bin/bash
# 8.20. Ninja-1.13.2
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/ninja.html
# TUP_TARBALL=ninja-1.13.2.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch08/20-ninja.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_a2fb25d754d5d7e2d3061f5baa2f68d32b23c535283b18d0a563eb07b923e7b6'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
sed -i '/int Guess/a \
  int   j = 0;\
  char* jobs = getenv( "NINJAJOBS" );\
  if ( jobs != NULL ) j = atoi( jobs );\
  if ( j > 0 ) return j;\
' src/ninja.cc
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
python3 configure.py --bootstrap --verbose
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
install -vm755 ninja /usr/bin/
install -vDm644 misc/bash-completion /usr/share/bash-completion/completions/ninja
install -vDm644 misc/zsh-completion  /usr/share/zsh/site-functions/_ninja
# TUP_BLOCK_END=003
TUP_UNSELECTED_a2fb25d754d5d7e2d3061f5baa2f68d32b23c535283b18d0a563eb07b923e7b6
