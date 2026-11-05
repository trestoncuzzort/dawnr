#!/bin/bash
# Named LFS deviation: explicit target-root, sequential checked stages,
# bounded jobs, clean environment, private mount namespace for chroot.
set -euo pipefail
[[ "$#" -eq 6 || ( "$#" -eq 7 && "${7:-}" = --validate ) ]] || {
  echo 'run-stage: expected stage, root, user, home, jobs, profile, optional --validate' >&2; exit 2;
}
stage=$1 root=$2 build_user=$3 build_home=$4 jobs=$5 profile=$6
validate=0
[ "${7:-}" != --validate ] || validate=1
[[ "$root" = /* && "$root" != / && "$jobs" =~ ^[1-9][0-9]*$ ]] || exit 2
[ "$(readlink -f -- "$root")" = "$root" ] || { echo 'noncanonical root' >&2; exit 2; }
[ "$(readlink -f -- "$build_home")" = "$build_home" ] || { echo 'noncanonical build home' >&2; exit 2; }
[[ "$build_user" =~ ^[A-Za-z0-9][A-Za-z0-9._+-]*$ && "$build_user" != root ]] || exit 2
[ "$(id -u)" = 0 ] || { echo 'run-stage: root required' >&2; exit 2; }
staged=$root/tup-build
for path in "$root" "$build_home" "$staged" "$root/sources" "$root/sources/log"; do
  [ -d "$path" ] && [ ! -L "$path" ] && [ "$(readlink -f -- "$path")" = "$path" ] || exit 2
done
for path in "$staged/BUILD-INPUTS.json" "$staged/driver.sh"; do
  [ -s "$path" ] && [ ! -L "$path" ] || exit 2
done
for name in usr var etc lib64; do
  [ -d "$root/$name" ] && [ ! -L "$root/$name" ] || exit 2
done
for name in bin lib sbin; do
  [ -L "$root/$name" ] && [ "$(readlink "$root/$name")" = "usr/$name" ] || exit 2
done
case "$profile" in
  lfs-12.4-sysv) runtime_profile=native-x86_64-core; tests='glibc gcc binutils' ;;
  lfs-13.1-systemd) runtime_profile=native-x86_64-lfs-13.1-systemd-core; tests='glibc gcc binutils gmp mpfr expect coreutils Python tar kbd bzip2 tcl sqlite' ;;
  *) echo 'unsupported native profile' >&2; exit 2 ;;
esac
test_jobs=$jobs
[ "$test_jobs" -le 4 ] || test_jobs=4
common=(TUP_ARCH=x86_64 TUP_PROFILE="$runtime_profile" TUP_TESTS="$tests"
        TUP_JOBS="$jobs" TUP_TEST_JOBS="$test_jobs" NINJAJOBS="$jobs"
        MAKEFLAGS="-j$jobs" TESTSUITEFLAGS="-j$test_jobs" CMAKE_BUILD_PARALLEL_LEVEL="$jobs"
        PIP_NO_INDEX=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONHASHSEED=0
        LC_ALL=POSIX LANG=POSIX TZ=UTC TUP_VALIDATE_ONLY="$validate")
case "$stage" in
  ch05|ch06)
    prefix=(runuser -u "$build_user" --)
    # Root owns the ledger after ch06. Validation executes no package commands.
    [ "$validate" = 0 ] || prefix=()
    exec "${prefix[@]}" env -i \
      HOME="$build_home" TERM=dumb "${common[@]}" TUP_NATIVE_CHROOT=0 \
      LFS="$root" LFS_TGT=x86_64-lfs-linux-gnu \
      PATH="$root/tools/bin:/usr/bin:/bin" CONFIG_SITE="$root/usr/share/config.site" \
      TUP_OVERRIDES="$staged/overrides" TUP_BUILD_INPUTS="$staged/BUILD-INPUTS.json" \
      /bin/bash --noprofile --norc -c 'set +h; umask 022; exec /bin/bash "$1" "$2"' \
      bash "$staged/driver.sh" "$staged/book/$stage"
    ;;
  ownership)
    [ "$validate" = 0 ] || exit 2
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
    # The book enters the chroot from a root login, whose supplementary groups
    # include group 0. A service unit starts with an empty list, and coreutils'
    # chroot-credentials root test then sees "101" where it expects "101 0".
    # "+0" is numeric, so no group database is consulted on either side.
    exec chroot --groups=+0 "$root" /usr/bin/env -i HOME=/root TERM=dumb "${common[@]}" \
      PATH=/usr/bin:/usr/sbin LFS= TUP_NATIVE_CHROOT=1 \
      TUP_OVERRIDES=/tup-build/overrides TUP_BUILD_INPUTS=/tup-build/BUILD-INPUTS.json \
      /bin/bash --noprofile --norc /tup-build/driver.sh "/tup-build/book/$stage"
    ;;
  *) echo "unsupported stage: $stage" >&2; exit 2 ;;
esac
