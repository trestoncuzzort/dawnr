#!/bin/bash
# OVERRIDE ch11/01-theend: the release files, saying the true thing — this
# system is tup 0.1, built from LFS arm64-r12.4 by the witnessed pipeline.
# HOME_URL named the repo's old name (srlm-forge) in the 0.1 image; found by a
# reader of /etc/os-release inside a booted guest, 2026-09-02. Fixed here for
# the next image: it is a byte-changing edit to one file, so it rides with a
# rebuild and that build's INVENTORY, not with a patch to a shipped disk.
set -e
echo "tup 0.1 (built on LFS arm64-r12.4-42)" > /etc/lfs-release
cat > /etc/lsb-release << "LSBEOF"
DISTRIB_ID="tup"
DISTRIB_RELEASE="0.1"
DISTRIB_CODENAME="witness"
DISTRIB_DESCRIPTION="tup 0.1"
LSBEOF
cat > /etc/os-release << "OSEOF"
NAME="tup"
VERSION="0.1 (witness)"
ID=tup
PRETTY_NAME="tup 0.1"
VERSION_CODENAME="witness"
HOME_URL="https://github.com/jonhhjackson-a11y/tup"
OSEOF
