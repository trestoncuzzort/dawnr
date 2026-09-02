# 8.73. Vim-9.1.1629
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/vim.html
# TUP_TARBALL=vim-9.1.1629.tar.gz

echo '#define SYS_VIMRC_FILE "/etc/vimrc"' >> src/feature.h

./configure --prefix=/usr

make

chown -R tester .
sed '/test_plugin_glvs/d' -i src/testdir/Make_all.mak

if tup_tests_enabled "vim"; then
su tester -c "TERM=xterm-256color LANG=en_US.UTF-8 make -j1 test" \
   &> vim-test.log
else tup_receipt_skip_tests "vim"; fi

make install

ln -sv vim /usr/bin/vi
for L in  /usr/share/man/{,*/}man1/vim.1; do
    ln -sv vim.1 $(dirname $L)/vi.1
done

ln -sv ../vim/vim91/doc /usr/share/doc/vim-9.1.1629

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

vim -c ':options'
