#!/bin/bash
# prepare-host.sh: the book's chapters 2, 3 and 4, scripted, inside the
# build VM. Run as root: `sudo bash /home/tup/tup/buildvm/prepare-host.sh`.
#
# These chapters were never extracted for the arm64 leg; they were typed
# into a Lima VM and nothing in the repository says what was typed. That is
# the class of gap this project exists to close, so the x86_64 leg records
# them here the way chain7.sh records the chroot crossing: the book's own
# blocks where they can run unattended, and a NAMED deviation everywhere a
# block wanted a human (a partitioning program, a password prompt, a
# placeholder). Re-runnable: every step checks whether it is already done.
#
# Deviations from the book's bytes, all of them:
#   2.2  packages come from apt (the scaffold is Ubuntu 24.04); /bin/sh is
#        relinked to bash, which the book requires and Ubuntu does not do.
#   2.4  `cfdisk`/`fdisk` are interactive: sfdisk writes ONE partition on
#        an MBR label (the BIOS-GRUB ruling; see X86-FEASIBILITY.md).
#   2.5  /dev/<xxx> is /dev/vdb1; no swap partition.
#   2.7  /dev/<xxx> is /dev/vdb1.
#   3    md5sums mismatches STOP the run, except the lfs-bootscripts case the
#        arm64 leg already documented (upstream regenerated the tarball after
#        the book was cut); that one is recorded with its actual hash.
#   4.3  `passwd lfs` is skipped: root switches to lfs without one.
#   4.4  the lfs user's files are written by root via runuser instead of
#        from an interactive lfs shell.
set -eu
export LFS=/mnt/lfs
SRC=${TUP_SRC:-/home/tup/tup}
BOOKDIR=${TUP_BOOK:-$SRC/book-x86_64}
BASE=$(sed -n 's/^base=//p' "$BOOKDIR/BOOK-SOURCE")
DISK=${TUP_LFS_DEV:-/dev/vdb}
PART=${DISK}1
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
[ "$(id -u)" = 0 ] || { echo "run as root"; exit 1; }
[ -n "$BASE" ] || { echo "no BOOK-SOURCE in $BOOKDIR; run extract_book.py --arch x86_64"; exit 1; }
say() { echo; echo "=== $*"; }

say "2.2 host requirements (apt; the scaffold is disposable)"
export DEBIAN_FRONTEND=noninteractive
apt-get -qq update
apt-get -qq install -y build-essential bison gawk texinfo m4 patch perl python3 \
  xz-utils wget bc rsync file > /tmp/apt.log 2>&1 || { tail -20 /tmp/apt.log; exit 1; }
# the book: "/bin/sh should be a symbolic or hard link to bash"
[ "$(readlink -f /bin/sh)" = "$(readlink -f /bin/bash)" ] || ln -sfv bash /bin/sh
# the book: "/usr/bin/yacc should be a link to bison"; "/usr/bin/awk should be a link to gawk"
command -v yacc >/dev/null || ln -sfv bison /usr/bin/yacc
[ "$(readlink -f /usr/bin/awk)" = "$(readlink -f /usr/bin/gawk)" ] || ln -sfv gawk /usr/bin/awk
# the book's version-check.sh, verbatim from the page, judged by its own ERROR
# lines. The page's block WRITES version-check.sh into the cwd and then runs
# it, so the page itself must not be that file: the first run of this script
# saved the block as /tmp/version-check.sh, ran it from /tmp, and the block
# overwrote the script bash was reading. The check printed nothing and the
# ERROR grep passed on silence. Now the page lives elsewhere, runs in its own
# directory, and an empty report is a failure, not a pass.
mkdir -p /tmp/hostreqs
python3 - "$BOOKDIR" > /tmp/hostreqs-page.sh <<'PY'
import re, sys, html, urllib.request, pathlib
base = [l.split('=',1)[1] for l in pathlib.Path(sys.argv[1] + '/BOOK-SOURCE').read_text().split('\n') if l.startswith('base=')][0]
h = urllib.request.urlopen(base + 'chapter02/hostreqs.html', timeout=60).read().decode()
b = re.findall(r'<pre class="userinput">(.*?)</pre>', h, re.S)[0]
print(html.unescape(re.sub(r'<[^>]+>', '', b)))
PY
( cd /tmp/hostreqs && bash /tmp/hostreqs-page.sh ) > /tmp/version-check.out 2>&1 || true
cat /tmp/version-check.out
grep -q '^OK:' /tmp/version-check.out || { echo "!!! the version check produced no verdicts; refusing to treat silence as a pass"; exit 1; }
grep -q '^ERROR' /tmp/version-check.out && { echo "!!! host requirements not met"; exit 1; }

say "2.4 / 2.5 partition and file system on $DISK (one MBR partition, no swap)"
[ -b "$DISK" ] || { echo "no $DISK"; exit 1; }
if [ ! -b "$PART" ]; then
  echo 'label: dos' | sfdisk -q "$DISK"
  echo ',,L,*' | sfdisk -q "$DISK"
  partprobe "$DISK" 2>/dev/null || true; sleep 1
fi
[ -b "$PART" ] || { echo "no $PART after partitioning"; exit 1; }
if [ "$(blkid -o value -s TYPE "$PART" 2>/dev/null)" != ext4 ]; then
  mkfs -v -t ext4 "$PART"
fi

say "2.6 / 2.7 \$LFS and the mount"
export LFS=/mnt/lfs
umask 022
mkdir -pv $LFS
mountpoint -q $LFS || mount -v -t ext4 "$PART" $LFS
chown root:root $LFS
chmod 755 $LFS
echo $LFS

say "3 packages and patches"
mkdir -pv $LFS/sources
chmod -v a+wt $LFS/sources
cd $LFS/sources
[ -s wget-list-sysv ] || wget -q "${BASE}wget-list-sysv"
[ -s md5sums ]        || wget -q "${BASE}md5sums"
# ftp.gnu.org stalled at 0 B/s for gcc on 2026-09-02, measured from the
# guest and from the host alike, so a mirror may be named: every basename in
# the book's list is fetched from it first, and the book's own wget line then
# runs unchanged to fill anything the mirror lacks. The md5 gate below does
# not care where the bytes came from; PREPARED.txt records that it happened.
if [ -n "${TUP_SOURCE_MIRROR:-}" ]; then
  sed "s|.*/|${TUP_SOURCE_MIRROR%/}/|" wget-list-sysv > wget-list-mirror
  wget --input-file=wget-list-mirror --continue --directory-prefix=$LFS/sources -nv 2>&1 | grep -vc '^$' | sed 's/$/ mirror lines/'
fi
wget --input-file=wget-list-sysv --continue --directory-prefix=$LFS/sources -nv 2>&1 | tail -3
pushd $LFS/sources > /dev/null
  set +e; md5sum -c md5sums > md5.out 2>&1; rc=$?; set -e
popd > /dev/null
if [ $rc -ne 0 ]; then
  bad=$(grep -v ': OK$' md5.out | sed 's/: FAILED.*//' | grep -v '^md5sum' || true)
  for f in $bad; do
    case "$f" in
      lfs-bootscripts-*.tar.xz)
        top=$(tar tf "$f" 2>/dev/null | head -1 | cut -d/ -f1)
        [ "$top" = "${f%.tar.xz}" ] || { echo "!!! $f: bad tarball"; exit 1; }
        want=$(grep " $f$" md5sums | cut -d' ' -f1)
        mkdir -p log
        cat > log/PROVENANCE-NOTE-bootscripts.txt <<NOTE
$f: book md5 $want does NOT match. Downloaded $(date -u +%F) from $(grep "$f" wget-list-sysv): valid xz,
correct content tree ($top/). Upstream regenerated the tarball after the x86 12.4 md5sums was cut (the
arm64 leg hit the same case on 2026-08-31). Our binding hash:
$(sha256sum "$f")
NOTE
        echo "note: $f md5 mismatch recorded (see log/PROVENANCE-NOTE-bootscripts.txt)" ;;
      *) echo "!!! md5 mismatch on $f; not continuing"; exit 1 ;;
    esac
  done
fi
chown root:root $LFS/sources/*
mkdir -p $LFS/sources/log
sha256sum $(ls *.tar.* *.patch *.tgz 2>/dev/null) > "$LFS/sources/SHA256-MANIFEST-$STAMP.txt"
echo "manifest: $(wc -l < "$LFS/sources/SHA256-MANIFEST-$STAMP.txt") tarballs hashed"

say "4.2 limited directory layout"
mkdir -pv $LFS/{etc,var} $LFS/usr/{bin,lib,sbin}
for i in bin lib sbin; do
  [ -L $LFS/$i ] || ln -sv usr/$i $LFS/$i
done
case $(uname -m) in
  x86_64) mkdir -pv $LFS/lib64 ;;
esac
mkdir -pv $LFS/tools

say "4.3 the lfs user"
getent group lfs >/dev/null || groupadd lfs
id lfs >/dev/null 2>&1 || useradd -s /bin/bash -g lfs -m -k /dev/null lfs
chown -v lfs $LFS/{usr{,/*},var,etc,tools}
case $(uname -m) in
  x86_64) chown -v lfs $LFS/lib64 ;;
esac

say "4.4 the lfs user's environment (the book's two files, plus MAKEFLAGS as the book suggests)"
# Written by root and handed to lfs; the bytes are the page's. The book has
# lfs type them in an interactive shell, which is the deviation named above.
cat > /home/lfs/.bash_profile << "EOF"
exec env -i HOME=$HOME TERM=$TERM PS1='\u:\w\$ ' /bin/bash
EOF
cat > /home/lfs/.bashrc << "EOF"
set +h
umask 022
LFS=/mnt/lfs
LC_ALL=POSIX
LFS_TGT=$(uname -m)-lfs-linux-gnu
PATH=/usr/bin
if [ ! -L /bin ]; then PATH=/bin:$PATH; fi
PATH=$LFS/tools/bin:$PATH
CONFIG_SITE=$LFS/usr/share/config.site
export LFS LC_ALL LFS_TGT PATH CONFIG_SITE
EOF
cat >> /home/lfs/.bashrc << "EOF"
export MAKEFLAGS=-j$(nproc)
EOF
chown lfs:lfs /home/lfs/.bash_profile /home/lfs/.bashrc
[ ! -e /etc/bash.bashrc ] || mv -v /etc/bash.bashrc /etc/bash.bashrc.NOUSE

say "staging the build system under /home/lfs (the paths chain*.sh expect)"
rm -rf /home/lfs/book /home/lfs/overrides
cp -r "$BOOKDIR" /home/lfs/book
cp -r "$SRC/overrides" /home/lfs/overrides
cp "$SRC/driver.sh" "$SRC/chain7.sh" "$SRC/chain8.sh" "$SRC/chain-home.sh" \
   "$SRC/buildvm/chain56.sh" "$SRC/buildvm/build-all.sh" /home/lfs/
chown -R lfs:lfs /home/lfs
chown lfs:lfs $LFS/sources/log
{
  echo "prepared $STAMP"
  echo "book: $(tr '\n' ' ' < "$BOOKDIR/BOOK-SOURCE")"
  echo "host: $(lsb_release -ds 2>/dev/null) $(uname -r) nproc=$(nproc)"
  echo "disk: $PART $(blkid -o value -s UUID "$PART")"
  echo "sources: ${TUP_SOURCE_MIRROR:+mirror $TUP_SOURCE_MIRROR first, then }the book's wget-list-sysv; md5sums checked"
} > $LFS/sources/log/PREPARED.txt
cat $LFS/sources/log/PREPARED.txt
echo; echo "host prepared. next: sudo bash /home/lfs/build-all.sh"
