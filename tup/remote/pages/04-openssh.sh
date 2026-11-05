#!/bin/bash
# TUP_TARBALL=openssh-10.6p1.tar.gz
# BLFS 13.1 portable OpenSSH recipe, with upstream install-nokeys for an image.
# https://www.linuxfromscratch.org/blfs/view/13.1-systemd/postlfs/openssh.html
source /tup-layer/common.sh
for name in sshd sshtest; do
  if getent passwd "$name" || getent group "$name"; then
    echo 'unexpected pre-existing SSH build account' >&2; exit 1
  fi
done
for id in 50 51; do
  if getent passwd "$id" || getent group "$id"; then
    echo 'SSH build UID/GID is already allocated' >&2; exit 1
  fi
done
groupadd -g 50 sshd
useradd -M -u 50 -g sshd -d /var/lib/sshd -s /bin/false -c 'sshd PrivSep' sshd
install -d -o root -g sys -m 0700 /var/lib/sshd
./configure --prefix=/usr --sysconfdir=/etc/ssh --libexecdir=/usr/lib/openssh \
  --with-privsep-user=sshd --with-privsep-path=/var/lib/sshd \
  --with-default-path=/usr/bin --with-superuser-path=/usr/sbin:/usr/bin \
  --with-pid-dir=/run --without-pam --without-kerberos5
make -j"$TUP_JOBS"
# Programs that "make install-nokeys" copies; they must not change while the
# suite runs as another user inside this tree.
# Take the list from the generated Makefile's own TARGETS rather than restate it.
read -r -a programs <<< "$(sed -n 's/^TARGETS=//p' Makefile | sed -e 's/\$[({]EXEEXT[)}]//g')"
[ "${#programs[@]}" -ge 10 ] || { echo 'unexpected OpenSSH TARGETS list' >&2; exit 1; }
for program in "${programs[@]}"; do [ -x "$program" ] || { echo "expected built program is absent: $program" >&2; exit 1; }; done
sha256sum -- "${programs[@]}" > /sources/log/openssh-built-programs.sha256
# The image's root account remains locked. Run upstream tests as an ephemeral
# normal identity. Linux OpenSSH uses '!' for account lock; '*' cannot verify a
# password but permits the suite's explicit public keys (configure.ac/platform.c).
groupadd -g 51 sshtest
useradd -M -u 51 -g sshtest -d "$PWD/regress-home" -s /bin/bash -p '*' sshtest
install -d -o sshtest -g sshtest -m 0700 "$PWD/regress-home"
chown -R sshtest:sshtest .
result=0
# LFS disables util-linux runuser/setpriv; use the same Shadow su interface as
# the book's unprivileged package suites, without a login-shell directory change.
su sshtest -s /bin/bash -c 'make -j1 tests' || result=$?
logs=$(find regress -type f -name '*.log' -print)
[ -z "$logs" ] || find regress -type f -name '*.log' -print0 | tar --null -T - -cf /sources/log/openssh-test-logs.tar
[ "$result" -eq 0 ] || exit "$result"
# With Shadow's default USERGROUPS_ENAB, userdel also removes the user's group.
userdel sshtest
if getent group sshtest > /dev/null; then groupdel sshtest; fi
if getent passwd sshtest > /dev/null || getent group sshtest > /dev/null; then
  echo 'ephemeral SSH test identity was not removed' >&2; exit 1
fi
chown -R root:root .
sha256sum --check --strict --quiet /sources/log/openssh-built-programs.sha256
make install-nokeys
install -m 0755 contrib/ssh-copy-id /usr/bin/ssh-copy-id
install -m 0644 contrib/ssh-copy-id.1 /usr/share/man/man1/ssh-copy-id.1
# Enrollment replaces this refusal policy only after verifying the actual
# normal account, key material and matching firewall plan.
cat > /etc/ssh/sshd_config <<'CONFIG'
ListenAddress 127.0.0.1
RefuseConnection yes
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
AuthenticationMethods publickey
AuthorizedKeysFile none
CONFIG
chmod 0644 /etc/ssh/sshd_config
if compgen -G '/etc/ssh/ssh_host_*_key' > /dev/null; then
  echo 'generic target acquired a private host key' >&2; exit 1
fi
