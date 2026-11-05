#!/bin/bash
# 8.46. Perl-5.44.0
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/perl.html
# TUP_TARBALL=perl-5.44.0.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review,book-alternatives-or-judgment
printf '%s\n' 'ch08/46-perl.sh: named override required: native-policy-review, book-alternatives-or-judgment' >&2
exit 97
: <<'TUP_UNSELECTED_88e191b389c95e7f30c5b1a5163cd666c571a1dfacc3a87d2155648e8e43aec6'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
export BUILD_ZLIB=False
export BUILD_BZIP2=0
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
sh Configure -des                                          \
             -D prefix=/usr                                \
             -D vendorprefix=/usr                          \
             -D privlib=/usr/lib/perl5/5.44/core_perl      \
             -D archlib=/usr/lib/perl5/5.44/core_perl      \
             -D sitelib=/usr/lib/perl5/5.44/site_perl      \
             -D sitearch=/usr/lib/perl5/5.44/site_perl     \
             -D vendorlib=/usr/lib/perl5/5.44/vendor_perl  \
             -D vendorarch=/usr/lib/perl5/5.44/vendor_perl \
             -D man1dir=/usr/share/man/man1                \
             -D man3dir=/usr/share/man/man3                \
             -D pager="/usr/bin/less -isR"                 \
             -D useshrplib                                 \
             -D usethreads
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make
# TUP_BLOCK_END=003

if tup_tests_enabled "perl"; then
# TUP_BLOCK_BEGIN=004
TEST_JOBS=$(nproc) make test_harness
# TUP_BLOCK_END=004
else tup_receipt_skip_tests "ch08/46-perl.sh:block-004"; fi

# TUP_BLOCK_BEGIN=005
make install
unset BUILD_ZLIB BUILD_BZIP2
# TUP_BLOCK_END=005
TUP_UNSELECTED_88e191b389c95e7f30c5b1a5163cd666c571a1dfacc3a87d2155648e8e43aec6
