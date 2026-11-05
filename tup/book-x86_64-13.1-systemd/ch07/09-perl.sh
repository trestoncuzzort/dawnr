#!/bin/bash
# 7.9. Perl-5.44.0
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter07/perl.html
# TUP_TARBALL=perl-5.44.0.tar.xz
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch07/09-perl.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_f475f60c6e67642f2303c4241a795a88f0803924666f8973e350ab358b4fc416'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
sh Configure -des                                         \
             -D prefix=/usr                               \
             -D vendorprefix=/usr                         \
             -D useshrplib                                \
             -D privlib=/usr/lib/perl5/5.44/core_perl     \
             -D archlib=/usr/lib/perl5/5.44/core_perl     \
             -D sitelib=/usr/lib/perl5/5.44/site_perl     \
             -D sitearch=/usr/lib/perl5/5.44/site_perl    \
             -D vendorlib=/usr/lib/perl5/5.44/vendor_perl \
             -D vendorarch=/usr/lib/perl5/5.44/vendor_perl
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
make
# TUP_BLOCK_END=002

# TUP_BLOCK_BEGIN=003
make install
# TUP_BLOCK_END=003
TUP_UNSELECTED_f475f60c6e67642f2303c4241a795a88f0803924666f8973e350ab358b4fc416
