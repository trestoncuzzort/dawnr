#!/bin/bash
source /tup-layer/common.sh
# The whole-disk installer: tup/install/disk.py and the two boot modules it imports, under /usr/lib/tup-installer,
# and the wrapper /usr/sbin/tup-install that runs it. Nothing runs at boot and nothing is enabled; the owner runs
# it from the live system (tup/system/README.md, "Installing to a disk"). The page refuses a root that lacks any
# program the installer runs, so a missing mkfs.fat is found at build time and not on the owner's desktop.
#   tup/install/README.md describes the installer and what it refuses.
#   https://www.linuxfromscratch.org/blfs/view/13.1-systemd/postlfs/dosfstools.html   (mkfs.fat, fsck.fat)
#   https://www.linuxfromscratch.org/lfs/view/13.1-systemd/chapter08/grub.html          (GRUB; x86_64-efi modules)
#   python(1) of Python 3.14: -I isolates from the environment and user site, -B writes no bytecode
fail() { echo "04-installer: $*" >&2; exit 1; }

src=/tup-layer/tup
dest=/usr/lib/tup-installer
for file in install/disk.py boot/__init__.py boot/inputs.py; do
  [ -f "$src/$file" ] && [ ! -L "$src/$file" ] || fail "layer input $file is missing"
done
# The installer reads the enrollment input with the code that reads it at first boot (03-access.sh installs it).
[ -f /usr/lib/tup/remote/enroll.py ] || fail "/usr/lib/tup/remote/enroll.py is missing; 03-access.sh comes first"

# Every program disk.py runs (its TOOLS table), looked up on the installer's own PATH, plus blockdev and findmnt,
# which the owner's checks in the README use. partx is not used: the new partitions' nodes come from sysfs.
for tool in sfdisk lsblk blkid wipefs blockdev findmnt udevadm mount umount mkfs.ext4 e2fsck mkfs.fat fsck.fat \
            grub-mkstandalone grub-script-check cp sync python3; do
  path=$(PATH=/usr/sbin:/usr/bin:/sbin:/bin; command -v "$tool") && [ -x "$path" ] || fail "$tool is missing"
done
# grub-mkstandalone embeds the modules of the menu it is given (insmod part_gpt fat search linux smbios, and the
# serial command); all of them must be there for x86_64-efi.
[ -d /usr/lib/grub/x86_64-efi ] || fail "/usr/lib/grub/x86_64-efi is missing; the x86_64-efi GRUB platform was not built"
for module in part_gpt fat search linux smbios serial; do
  [ -f "/usr/lib/grub/x86_64-efi/$module.mod" ] || fail "GRUB module $module.mod is missing"
done
[ -f /usr/lib/grub/x86_64-efi/moddep.lst ] || fail "GRUB moddep.lst is missing"

install -v -d -m 0755 "$dest" "$dest/tup" "$dest/tup/install" "$dest/tup/boot"
install -v -m 0755 "$src/install/disk.py" "$dest/tup/install/disk.py"
install -v -m 0644 "$src/boot/__init__.py" "$src/boot/inputs.py" "$dest/tup/boot/"
# python3 -I ignores PYTHON* variables and the working directory; -B keeps bytecode out of the image. The path
# of the script is explicit, so nothing is found by searching.
rm -f /usr/sbin/tup-install
cat > /usr/sbin/tup-install << "EOF"
#!/bin/sh
# Plan and apply the installation of this live system onto one internal disk. tup-install plan --help
exec /usr/bin/python3 -I -B /usr/lib/tup-installer/tup/install/disk.py "$@"
EOF
chmod 0755 /usr/sbin/tup-install

# The installed copy, run by the target's own Python: it must import from /usr/lib/tup-installer, find every tool
# it runs, load the enrollment code from /usr/lib/tup/remote, and generate a menu that the target's own
# grub-script-check accepts. Nothing is written but a temporary directory.
python3 -I -B - << "EOF"
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, "/usr/lib/tup-installer")
from tup.install import disk

if Path(disk.__file__).resolve() != Path("/usr/lib/tup-installer/tup/install/disk.py"):
    raise SystemExit(f"04-installer: disk.py loaded from {disk.__file__}")
if Path(disk.inputs.__file__).resolve() != Path("/usr/lib/tup-installer/tup/boot/inputs.py"):
    raise SystemExit(f"04-installer: inputs.py loaded from {disk.inputs.__file__}")
host = disk.Host()
missing = [name for name in disk.TOOLS if not host.which(name)]
if missing:
    raise SystemExit(f"04-installer: the installer cannot find: {', '.join(missing)}")
module, enroll_path = disk.enroll_module()
if enroll_path != Path("/usr/lib/tup/remote/enroll.py"):
    raise SystemExit(f"04-installer: enrollment code loaded from {enroll_path}")
layout = disk.make_layout({"log_sec": 512, "size_bytes": 64 << 30}, 512, os.urandom)
text = disk.grub_cfg_text(layout, {"name": "vmlinuz-fixture"}, {"loaded": True}, "0" * 64)
with tempfile.TemporaryDirectory() as temporary:
    config = Path(temporary) / "grub.cfg"
    config.write_text(text)
    check = subprocess.run([host.which("grub-script-check"), str(config)], capture_output=True, text=True)
    if check.returncode:
        raise SystemExit("04-installer: grub-script-check refused the generated menu: " + check.stderr)
    # The exact command line of disk.py deploy(): the target's GRUB must be able to build the image.
    image = Path(temporary) / "BOOTX64.EFI"
    build = subprocess.run([host.which("grub-mkstandalone"), "-O", "x86_64-efi", "--fonts=", "--themes=", "--locales=",
                            "-o", str(image), f"boot/grub/grub.cfg={config}"], capture_output=True, text=True)
    if build.returncode or image.read_bytes()[:2] != b"MZ" or image.stat().st_size < (1 << 20):
        raise SystemExit("04-installer: grub-mkstandalone did not produce an EFI image: " + build.stderr)
EOF

# Final state of a generic image, as 03-access.sh left it: this page adds files under /usr only.
cmp -s "$src/install/disk.py" "$dest/tup/install/disk.py" || fail "the installed disk.py differs from the layer input"
[ -x /usr/sbin/tup-install ] && [ ! -L /usr/sbin/tup-install ] || fail "/usr/sbin/tup-install is not an executable file"
if [ -n "$(find "$dest" /usr/lib/tup /usr/sbin/tup-install \( -name __pycache__ -o -name '*.pyc' \) -print)" ]; then
  fail "bytecode was written beside the installer or the renderers"
fi
[ -z "$(find "$dest" ! -user root -print)" ] || fail "the installer tree must be owned by root"
[ ! -e /etc/tup/owner-enrolled.json ] && [ ! -e /etc/tup/enroll-input ] || fail "the image must not carry enrollment"
[ ! -s /etc/machine-id ] || fail "/etc/machine-id must stay empty"
if compgen -G '/etc/ssh/ssh_host_*' > /dev/null; then fail "the image must not contain SSH host keys"; fi
if [ -e /etc/fstab ] && grep -qEv '^[[:space:]]*(#|$)' /etc/fstab; then fail "/etc/fstab must be empty or comment-only"; fi
