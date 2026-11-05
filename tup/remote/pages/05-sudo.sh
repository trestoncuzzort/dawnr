#!/bin/bash
# TUP_TARBALL=sudo-1.9.17p2.tar.gz
source /tup-layer/common.sh
# BLFS 13.1-systemd sudo recipe (postlfs/sudo.html) for a target without PAM.
# Differences from the book, each deliberate:
#   --without-pam      the target has no Linux-PAM: refuse autodetection and
#                      use sudo's shadow password backend (configure.ac).
#   --disable-openssl  OpenSSL only adds TLS for sudo_logsrvd/sudo_sendlog,
#                      unused here; sudo then uses its bundled SHA-2. The
#                      book's OpenSSL 4 sed on lib/iolog/hostcheck.c is
#                      therefore not applied: that code is HAVE_OPENSSL only.
#   --with-secure-path=/usr/sbin:/usr/bin  the value the book sets afterwards
#                      in /etc/sudoers.d/00-sudo; the generic image keeps
#                      /etc/sudoers.d empty, so it is configured here.
#   --enable-tmpfiles.d  stated, not autodetected from the build environment.
#   make -j1 install   serialized; the book's plain make inherits MAKEFLAGS.
./configure --prefix=/usr --libexecdir=/usr/lib \
  --with-secure-path=/usr/sbin:/usr/bin --with-env-editor \
  --docdir=/usr/share/doc/sudo-1.9.17p2 \
  --with-passprompt='[sudo] password for %p: ' \
  --without-pam --disable-openssl --enable-tmpfiles.d=/usr/lib/tmpfiles.d
if grep -Eq '^#define (HAVE_PAM|HAVE_OPENSSL)\b' config.h; then
  echo 'sudo configured PAM or OpenSSL despite the explicit refusal' >&2; exit 1
fi
grep -q '^#define HAVE_GETSPNAM 1$' config.h || {
  echo 'sudo did not select shadow password lookup' >&2; exit 1;
}
make -j"$TUP_JOBS"
result=0
env LC_ALL=C make -j1 check > make-check.log 2>&1 || result=$?
cp make-check.log /sources/log/sudo-make-check.log
grep -E 'tests run|FAIL$' make-check.log || true
[ "$result" -eq 0 ] || { tail -n 40 make-check.log >&2; exit "$result"; }
# Each suite prints "N tests run, M errors"; refuse a failure the exit status
# hid, and refuse a log in which the policy suites did not run at all.
if grep -Eq 'FAIL$|, [1-9][0-9]* errors?,' make-check.log; then
  echo 'sudo upstream check reported failures' >&2; exit 1
fi
for suite in sudoers testsudoers visudo cvtsudoers; do
  grep -Eq "^$suite: [1-9][0-9]* tests run, 0 errors, 100% success rate\$" make-check.log || {
    echo "sudo upstream suite did not run cleanly: $suite" >&2; exit 1;
  }
done
if [ -e /etc/sudoers ] || [ -e /etc/sudoers.d ]; then
  echo 'unexpected pre-existing sudoers policy' >&2; exit 1
fi
make -j1 install
# Upstream's install also creates /run/sudo. The layer runner mounts a tmpfs on
# /run, so that directory never reaches the image; the installed tmpfiles.d
# entry recreates it at every boot.
# Restrictive default: upstream's installed sudoers keeps its Defaults and
# "@includedir /etc/sudoers.d", but its one active rule (root) is disabled.
# Root is locked; the owner rule is written only at enrollment, as
# /etc/sudoers.d/10-tup-owner. /etc/sudoers.dist stays as installed, unread.
sed -i 's/^root ALL=(ALL:ALL) ALL$/# &/' /etc/sudoers
if ! grep -qx '# root ALL=(ALL:ALL) ALL' /etc/sudoers ||
    ! grep -qx '@includedir /etc/sudoers.d' /etc/sudoers; then
  echo 'installed sudoers is not the reviewed upstream default' >&2; exit 1
fi
if [ "$(stat -c '%a %U %G' /etc/sudoers)" != '440 root root' ] ||
    [ "$(stat -c '%a %U %G' /etc/sudoers.d)" != '750 root root' ] ||
    [ -n "$(ls -A /etc/sudoers.d)" ] ||
    [ "$(stat -c '%a %U %G' /usr/bin/sudo)" != '4755 root root' ]; then
  echo 'sudo policy files or the setuid front end have unexpected ownership, mode or content' >&2; exit 1
fi
/usr/sbin/visudo -c
# Upstream's own parser must find no user specification at all.
/usr/bin/cvtsudoers -f json -o sudoers-policy.json /etc/sudoers
python3 - <<'EOF'
import json
policy = json.load(open("sudoers-policy.json"))
if "User_Specs" in policy or not policy.get("Defaults"):
    raise SystemExit("generic sudoers grants a rule or lost its upstream defaults")
EOF
# Installed-binary controls: the front end must load its policy plugin, and
# the generic policy must refuse even root, who is never asked for a password.
/usr/bin/sudo -V > sudo-version.txt
grep -qx 'Sudo version 1.9.17p2' sudo-version.txt || {
  echo 'installed sudo does not report the selected version' >&2; exit 1;
}
denied=0
/usr/bin/sudo -n /usr/bin/true > sudo-denial.txt 2>&1 || denied=$?
cat sudo-denial.txt
if [ "$denied" -ne 1 ] || ! grep -q 'root is not in the sudoers file' sudo-denial.txt; then
  echo 'generic sudo policy did not refuse root by rule' >&2; exit 1
fi
printf '%s\n' 'sudo: installed without PAM/OpenSSL; no rule granted; owner rule is an enrollment step'
