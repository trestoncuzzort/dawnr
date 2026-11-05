#!/bin/bash
source /tup-layer/common.sh
# Owner access: the renderers and the boot-time enrollment step, their units,
# the default-deny firewall and the console banner. The image stays generic:
# no host key, no account, no owner key and no enrollment marker. Units are
# enabled offline (symlinks only); nothing is started in this chroot.
#   tup/remote/README.md and tup/system/README.md describe the design.
#   agetty(8) of util-linux 2.42.4: /etc/issue, /run/issue.d and the \4 \6 escapes
#   systemctl(1) of systemd 261.2: --root= operates on files, as the core's preset-all does
#   https://www.linuxfromscratch.org/blfs/view/stable-systemd/postlfs/openssh.html
fail() { echo "03-access: $*" >&2; exit 1; }

src=/tup-layer/tup
units="tup-enroll.service tup-firewall.service tup-sshd.service tup-console-status.service"
for file in remote/policy.py remote/firewall.py remote/enroll.py system/firewall.nft system/issue; do
  [ -f "$src/$file" ] && [ ! -L "$src/$file" ] || fail "layer input $file is missing"
done
for unit in $units; do
  [ -f "$src/system/units/$unit" ] && [ ! -L "$src/system/units/$unit" ] || fail "layer input system/units/$unit is missing"
done
# Every program the units and enroll.py execute; the remote chapter comes first.
for tool in /usr/bin/python3 /usr/sbin/sshd /usr/bin/ssh-keygen /usr/sbin/nft /usr/sbin/useradd \
            /usr/bin/udevadm /usr/bin/mount /usr/bin/umount /usr/bin/kill /usr/sbin/agetty; do
  [ -x "$tool" ] || fail "$tool is missing"
done
# nft resolves "ipv6-icmp" in the table through getprotobyname(): without the
# iana-etc database the firewall unit fails and nothing is filtered.
[ -s /etc/protocols ] || fail "/etc/protocols is missing; nft cannot load the firewall table without it"
# Enrollment grants the owner sudo through /etc/sudoers.d. Where sudo is
# already installed, a sudoers file that does not read that directory would
# leave the owner without any route to root, since root itself is locked.
if [ -x /usr/bin/sudo ] && [ -e /etc/sudoers ]; then
  grep -Eq '^[@#]includedir[[:space:]]+/etc/sudoers\.d[[:space:]]*$' /etc/sudoers \
    || fail "/etc/sudoers does not include /etc/sudoers.d"
fi

install -v -d -m 0755 /usr/lib/tup /usr/lib/tup/remote /etc/tup /etc/tup/authorized_keys
install -v -m 0644 "$src/remote/policy.py" "$src/remote/firewall.py" /usr/lib/tup/remote/
install -v -m 0755 "$src/remote/enroll.py" /usr/lib/tup/remote/
for unit in $units; do
  install -v -m 0644 "$src/system/units/$unit" /usr/lib/systemd/system/
done
# Loaded before the network on every boot. Enrollment replaces it atomically.
install -v -m 0600 "$src/system/firewall.nft" /etc/tup/firewall.nft
rm -f /etc/issue
install -v -m 0644 "$src/system/issue" /etc/issue

# The installed renderers, run by the target's own Python, must reproduce the
# installed static files: a unit or default table that drifted from policy.py
# and firewall.py is refused here, not discovered at first boot.
python3 -I -B - << "EOF"
import base64, struct, sys
from pathlib import Path
sys.path.insert(0, "/usr/lib/tup")
from remote import enroll, firewall, policy

blob = struct.pack(">I", 11) + b"ssh-ed25519" + struct.pack(">I", 32) + bytes(range(1, 33))
access = policy.render("owner", None, b"ssh-ed25519 " + base64.b64encode(blob) + b"\n", scope=policy.PRIVATE)
wall = firewall.render(None, None, scope=policy.PRIVATE)
default = firewall.render(None, None, scope=firewall.UNENROLLED)
expected = {"/usr/lib/systemd/system/tup-sshd.service": access["tup-sshd.service"],
            "/usr/lib/systemd/system/tup-firewall.service": wall["tup-firewall.service"],
            "/etc/tup/firewall.nft": default["firewall.nft"]}
for path, data in expected.items():
    if Path(path).read_bytes() != data:
        raise SystemExit(f"03-access: {path} differs from what the installed renderer emits")
if b"new, established } counter accept" in default["firewall.nft"]:
    raise SystemExit("03-access: the unenrolled firewall admits SSH")
if Path(enroll.__file__).resolve().parent != Path("/usr/lib/tup/remote"):
    raise SystemExit("03-access: enroll.py did not load from /usr/lib/tup/remote")
EOF

systemctl --root=/ enable systemd-networkd.service systemd-resolved.service systemd-timesyncd.service $units
for unit in systemd-networkd.service systemd-resolved.service systemd-timesyncd.service $units; do
  [ "$(systemctl --root=/ is-enabled "$unit")" = enabled ] || fail "$unit is not enabled"
done

# Final state of a generic image: boot/inputs.py check_offline_root() and the
# layer contract. /dev, /run and /tmp are the runner's own mounts in here and
# are checked by the packager, not by this page.
[ ! -L /etc/machine-id ] && [ ! -s /etc/machine-id ] || fail "/etc/machine-id must be empty"
if compgen -G '/etc/ssh/ssh_host_*' > /dev/null; then fail "the image must not contain SSH host keys"; fi
root_hash=$(awk -F: '$1 == "root" { print $2; n++ } END { if (n != 1) exit 1 }' /etc/shadow) \
  || fail "/etc/shadow must have exactly one root entry"
case "$root_hash" in '!'*|'*'*) ;; *) fail "root must stay locked; there is no default password" ;; esac
[ -f /etc/os-release ] && [ ! -L /etc/os-release ] || fail "/etc/os-release must be a regular file"
[ "$(grep -cE '^ID=(tup|"tup")$' /etc/os-release)" = 1 ] || fail "/etc/os-release needs exactly one ID=tup"
[ "$(grep -cE '^VERSION_ID="?[A-Za-z0-9._+-]+"?$' /etc/os-release)" = 1 ] || fail "/etc/os-release needs exactly one VERSION_ID"
if [ -e /etc/fstab ] && grep -qEv '^[[:space:]]*(#|$)' /etc/fstab; then fail "/etc/fstab must be empty or comment-only"; fi
[ ! -e /etc/tup/owner-enrolled.json ] || fail "the image must not be enrolled"
[ -z "$(ls -A /etc/tup/authorized_keys)" ] || fail "the image must not contain owner keys"
[ ! -e /etc/sudoers.d/10-tup-owner ] || fail "the image must not contain an owner sudo rule"
if awk -F: '$3 >= 1000 && $3 != 65534 { found = 1 } END { exit !found }' /etc/passwd; then
  fail "the image must not contain a login account"
fi
[ ! -e /usr/lib/tup/remote/__pycache__ ] || fail "bytecode was written beside the renderers"
