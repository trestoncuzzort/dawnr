# 8.44. XML::Parser-2.47
# https://www.linuxfromscratch.org/lfs/view/12.4/chapter08/xml-parser.html
# TUP_TARBALL=XML-Parser-2.47.tar.gz

perl Makefile.PL

make

if tup_tests_enabled "xml-parser"; then
make test
else tup_receipt_skip_tests "xml-parser"; fi

make install
