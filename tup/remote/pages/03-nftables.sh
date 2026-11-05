#!/bin/bash
# TUP_TARBALL=nftables-1.1.7.tar.xz
# Upstream INSTALL/configure.ac; use the authenticated core's GMP.
source /tup-layer/common.sh
./configure --prefix=/usr --sbindir=/usr/sbin --disable-static \
  --without-cli --without-json --without-xtables --disable-man-doc --without-unitdir
make -j"$TUP_JOBS"
make install
/usr/sbin/nft --version
# Full upstream kernel coverage needs the booted target kernel. This bounded
# real traffic test runs in further private network/PID/mount namespaces.
python3 /tup-layer/tup/remote/probe_firewall.py --nft /usr/sbin/nft \
  > /sources/log/firewall-probe.json
printf '%s\n' 'nftables: bounded dual-stack probe passed; full upstream kernel suite deferred to disposable boot'
