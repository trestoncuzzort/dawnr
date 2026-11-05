#!/bin/bash
# Named LFS 12.4 deviation: explicit target-root, sequential checked stages,
# bounded jobs, clean environment, private mount namespace for chroot.
set -euo pipefail
[[ "$#" -eq 5 || ( "$#" -eq 6 && "${6:-}" = --validate ) ]] || {
  echo 'run-stage: expected stage, root, user, home, jobs, optional --validate' >&2; exit 2;
}
stage=$1 root=$2 build_user=$3 build_home=$4 jobs=$5
validate=0
[ "${6:-}" != --validate ] || validate=1
[[ "$root" = /* && "$root" != / && "$jobs" =~ ^[1-9][0-9]*$ ]] || exit 2
[ "$(readlink -f -- "$root")" = "$root" ] || { echo 'noncanonical root' >&2; exit 2; }
[ "$(id -u)" = 0 ] || { echo 'run-stage: root required' >&2; exit 2; }
staged=$root/tup-build
[ -s "$staged/BUILD-INPUTS.json" ] || exit 2
case "$stage" in
  ch05|ch06)
    prefix=(runuser -u "$build_user" --)
    # Root owns the ledger after ch06. Validation executes no package commands.
    [ "$validate" = 0 ] || prefix=()
    exec "${prefix[@]}" env -i \
      HOME="$build_home" TERM=dumb LC_ALL=POSIX \
      LFS="$root" LFS_TGT=x86_64-lfs-linux-gnu \
      PATH="$root/tools/bin:/usr/bin:/bin" CONFIG_SITE="$root/usr/share/config.site" \
      MAKEFLAGS="-j$jobs" TESTSUITEFLAGS="-j$jobs" \
      TUP_ARCH=x86_64 TUP_PROFILE=native-x86_64-core TUP_TESTS='glibc gcc binutils' \
      TUP_VALIDATE_ONLY="$validate" \
      TUP_OVERRIDES="$staged/overrides" TUP_BUILD_INPUTS="$staged/BUILD-INPUTS.json" \
      /bin/bash --noprofile --norc -c 'set +h; umask 022; exec /bin/bash "$1" "$2"' \
      bash "$staged/driver.sh" "$staged/book/$stage"
    ;;
  ownership)
    # Never invoke the old chain's hardcoded /mnt/lfs or host disk operations.
    for name in usr var etc tools lib64 sources/log; do
      [ -d "$root/$name" ] && [ ! -L "$root/$name" ] || exit 2
      chown -R root:root "$root/$name"
    done
    ;;
  ch07-inner|ch08)
    # Called only through unshare by build.py. Refuse direct host-namespace use.
    [ "$(readlink /proc/self/ns/mnt)" != "$(readlink /proc/1/ns/mnt)" ] || {
      echo 'run-stage: private mount namespace required' >&2; exit 2;
    }
    mount --make-rprivate /
    for name in dev proc sys run; do
      [ ! -L "$root/$name" ] || exit 2
      mkdir -p "$root/$name"
      mountpoint -q "$root/$name" && { echo "unexpected mount: $name" >&2; exit 2; }
    done
    mount --bind /dev "$root/dev"
    mount -t devpts devpts -o gid=5,mode=0620 "$root/dev/pts"
    mount -t proc proc "$root/proc"
    mount -t sysfs sysfs "$root/sys"
    mount -t tmpfs tmpfs "$root/run"
    if [ -h "$root/dev/shm" ]; then
      shm_target=$(readlink "$root/dev/shm")
      [ "$shm_target" = /run/shm ] || { echo 'unexpected /dev/shm symlink' >&2; exit 2; }
      install -d -m 1777 "$root/run/shm"
    else
      mount -t tmpfs -o nosuid,nodev tmpfs "$root/dev/shm"
    fi
    exec chroot "$root" /usr/bin/env -i HOME=/root TERM=dumb LC_ALL=POSIX \
      PATH=/usr/bin:/usr/sbin MAKEFLAGS="-j$jobs" TESTSUITEFLAGS="-j$jobs" \
      LFS= TUP_ARCH=x86_64 TUP_PROFILE=native-x86_64-core TUP_TESTS='glibc gcc binutils' \
      TUP_VALIDATE_ONLY="$validate" \
      TUP_OVERRIDES=/tup-build/overrides TUP_BUILD_INPUTS=/tup-build/BUILD-INPUTS.json \
      /bin/bash --noprofile --norc /tup-build/driver.sh "/tup-build/book/$stage"
    ;;
  *) echo "unsupported stage: $stage" >&2; exit 2 ;;
esac
