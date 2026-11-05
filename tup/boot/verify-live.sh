#!/bin/sh
# Dracut pre-pivot hook. This is media integrity, not authenticated boot.
command -v die >/dev/null 2>&1 || . /lib/dracut-lib.sh
if ! sha256sum --status --check /etc/tup-live/root.sha256; then
    die "TUP live payload digest mismatch or missing media; refusing switch-root. See /run/initramfs/rdsosreport.txt"
    exit 1
fi
info "TUP live payload verified against the digest embedded in this initramfs"
