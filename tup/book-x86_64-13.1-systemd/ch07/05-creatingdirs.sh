#!/bin/bash
# 7.5. Creating Directories
# https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter07/creatingdirs.html
# TUP_ACTION_PAGE
# TUP_REQUIRES_OVERRIDE=native-policy-review
printf '%s\n' 'ch07/05-creatingdirs.sh: named override required: native-policy-review' >&2
exit 97
: <<'TUP_UNSELECTED_88ba0fe23f1c8b0c9560375ffb427aa9bbc99602f05c4f94f6726756daf0882f'
# TUP_BOOK_COMMANDS_BEGIN

# TUP_BLOCK_BEGIN=001
mkdir -pv /{boot,home,mnt,opt,srv}
# TUP_BLOCK_END=001

# TUP_BLOCK_BEGIN=002
mkdir -pv /etc/{opt,sysconfig}
mkdir -pv /lib/firmware
mkdir -pv /media/{floppy,cdrom}
mkdir -pv /usr/{,local/}{include,src}
mkdir -pv /usr/lib/locale
mkdir -pv /usr/local/{bin,lib,sbin}
mkdir -pv /usr/{,local/}share/{color,dict,doc,info,locale,man}
mkdir -pv /usr/{,local/}share/{misc,terminfo,zoneinfo}
mkdir -pv /usr/{,local/}share/man/man{1..8}
mkdir -pv /var/{cache,local,log,mail,opt,spool}
mkdir -pv /var/lib/{color,misc,locate}

ln -sfv /run /var/run
ln -sfv /run/lock /var/lock

install -dv -m 0750 /root
install -dv -m 1777 /tmp /var/tmp
# TUP_BLOCK_END=002
TUP_UNSELECTED_88ba0fe23f1c8b0c9560375ffb427aa9bbc99602f05c4f94f6726756daf0882f
