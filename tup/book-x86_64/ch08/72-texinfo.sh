# 8.72. Texinfo-7.2
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/texinfo.html
# TUP_TARBALL=texinfo-7.2.tar.xz

sed 's/! $output_file eq/$output_file ne/' -i tp/Texinfo/Convert/*.pm

./configure --prefix=/usr

make

if tup_tests_enabled "texinfo"; then
make check
else tup_receipt_skip_tests "texinfo"; fi

make install

make TEXMF=/usr/share/texmf install-tex

pushd /usr/share/info
  rm -v dir
  for f in *
    do install-info $f dir 2>/dev/null
  done
popd
