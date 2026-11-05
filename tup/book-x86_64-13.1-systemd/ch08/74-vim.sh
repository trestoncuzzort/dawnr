#!/bin/bash
# 8.74. Vim-9.2.1025
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/vim.html
# TUP_TARBALL=vim-9.2.1025.tar.gz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch08/74-vim.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_33ab9ba3d6014eec2c3015608a3909fea39e73ea7578c483e1402a6fef47e022'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
echo '#define SYS_VIMRC_FILE "/etc/vimrc"' >> src/feature.h
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
./configure --prefix=/usr
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make
# TUP_BLOCK_END=003

# TUP_BLOCK_BEGIN=004
chown -R tester .
sed '/test_plugin_glvs/d' -i src/testdir/Make_all.mak
# TUP_BLOCK_END=004

if tup_tests_enabled "vim"; then
# TUP_BLOCK_BEGIN=005
su tester -c "TERM=xterm-256color LANG=en_US.UTF-8 make -j1 test" \
   &> vim-test.log
# TUP_BLOCK_END=005
else tup_receipt_skip_tests "ch08/74-vim.sh:block-005"; fi

# TUP_BLOCK_BEGIN=006
make install
# TUP_BLOCK_END=006

# TUP_BLOCK_BEGIN=007
ln -sv vim /usr/bin/vi
for L in  /usr/share/man/{,*/}man1/vim.1; do
    ln -sv vim.1 $(dirname $L)/vi.1
done
# TUP_BLOCK_END=007

# TUP_BLOCK_BEGIN=008
ln -sv ../vim/vim92/doc /usr/share/doc/vim-9.2.1025
# TUP_BLOCK_END=008

# TUP_BLOCK_BEGIN=009
cat > /etc/vimrc << "EOF"
" Begin /etc/vimrc

" Ensure defaults are set before customizing settings, not after
source $VIMRUNTIME/defaults.vim
let skip_defaults_vim=1

set nocompatible
set backspace=2
set mouse=
syntax on
if (&term == "xterm") || (&term == "putty")
  set background=dark
endif

" End /etc/vimrc
EOF
# TUP_BLOCK_END=009

# TUP_BLOCK_BEGIN=010
vim -c ':options'
# TUP_BLOCK_END=010
TUP_UNSELECTED_33ab9ba3d6014eec2c3015608a3909fea39e73ea7578c483e1402a6fef47e022
