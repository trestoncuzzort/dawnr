"""Read-only boot input identities. Inventory observations do not authenticate sources."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct


class Refusal(ValueError):
    pass


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")) + "\n").encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def load_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise Refusal(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique)


def file_hash(path):
    path = Path(path)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise Refusal(f"expected a regular file: {path}")
    result = hashlib.sha256()
    # O_NOFOLLOW prevents substitution of the final component on Linux.
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as stream:
        opened = os.fstat(stream.fileno())
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise Refusal(f"input changed while opening: {path}")
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
        after = os.fstat(stream.fileno())
    # Compare each API with itself: Windows Python exposes different ctime
    # meanings through lstat and fstat. Linux still checks both observations.
    named_after = path.lstat()
    fields = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
    if fields(opened) != fields(after) or fields(before) != fields(named_after):
        raise Refusal(f"input changed while hashing: {path}")
    return result.hexdigest()


def checked_file(path, expected):
    if not isinstance(expected, str) or not re.fullmatch("[0-9a-f]{64}", expected):
        raise Refusal("missing/invalid expected SHA256")
    if file_hash(path) != expected:
        raise Refusal(f"input digest mismatch: {path}")


def inventory(directory):
    """Never follow links; include mode, ownership, xattrs and hardlink grouping.

    Only regular files, directories and links are accepted. Prepare an offline
    export first: this function cannot safely inventory mounted /dev or /proc.
    """
    directory = Path(directory).absolute()
    if directory.is_symlink() or not directory.is_dir():
        raise Refusal("inventory root must be a real directory")
    result, hardlinks = {}, {}
    device = directory.stat().st_dev

    def walk(path):
        relative = path.relative_to(directory).as_posix()
        info = path.lstat()
        if info.st_dev != device:
            raise Refusal(f"nested filesystem in input tree: {relative}")
        entry = {"mode": stat.S_IMODE(info.st_mode), "uid": info.st_uid, "gid": info.st_gid,
                 "mtime_ns": info.st_mtime_ns}
        if hasattr(os, "listxattr"):
            entry["xattrs"] = {name: os.getxattr(path, name, follow_symlinks=False).hex()
                               for name in sorted(os.listxattr(path, follow_symlinks=False))}
        if stat.S_ISLNK(info.st_mode):
            entry.update(type="symlink", target=os.readlink(path))
        elif stat.S_ISREG(info.st_mode):
            entry.update(type="file", size=info.st_size, sha256=file_hash(path))
            if info.st_nlink > 1:
                entry["hardlink"] = hardlinks.setdefault((info.st_dev, info.st_ino), relative)
        elif stat.S_ISDIR(info.st_mode):
            entry["type"] = "directory"
        else:
            raise Refusal(f"special file in offline input: {relative}")
        result[relative] = entry
        if entry["type"] == "directory":
            for child in sorted(path.iterdir(), key=lambda p: p.name):
                walk(child)
    walk(directory)
    return result


def tree_hash(directory):
    return digest(canonical(inventory(directory)))


def root_path(root, relative):
    """Critical input paths never follow a symlink out of the supplied root."""
    path = Path(root)
    parts = Path(relative).parts
    if Path(relative).is_absolute() or ".." in parts:
        raise Refusal("unsafe relative root path")
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise Refusal(f"critical root input has a symbolic link: {relative}")
    return path


SYSTEMD = "CGROUPS MEMCG FHANDLE INOTIFY_USER SIGNALFD TIMERFD EPOLL UNIX DMIID BLK_DEV_BSG NET_NS USER_NS IPV6 AUTOFS_FS SECCOMP SECCOMP_FILTER TMPFS_POSIX_ACL TMPFS_XATTR".split()
# SQUASHFS_XATTR: the live root keeps file capabilities and ACLs that mksquashfs stores.
BUILTIN = "64BIT X86_64 EFI EFI_STUB EFI_PARTITION BLK_DEV_INITRD RD_GZIP DEVTMPFS DEVTMPFS_MOUNT TMPFS PROC_FS SYSFS BINFMT_ELF BINFMT_SCRIPT SERIAL_8250 SERIAL_8250_CONSOLE MODULES SQUASHFS_ZSTD SQUASHFS_XATTR".split() + SYSTEMD
# EROFS_FS: dracut 112's dmsquash-live installkernel() requests squashfs, loop,
# iso9660 and erofs without marking any of them optional.
AVAILABLE = "BLK_DEV_LOOP SQUASHFS OVERLAY_FS ISO9660_FS EROFS_FS EXT4_FS VFAT_FS EXFAT_FS EFIVAR_FS SCSI BLK_DEV_SD BLK_DEV_SR SATA_AHCI BLK_DEV_NVME USB_XHCI_HCD USB_XHCI_PCI USB_STORAGE USB_UAS VIRTIO_PCI VIRTIO_BLK VIRTIO_NET BLK_DEV_DM".split()


def check_config(config):
    values = {}
    for line in Path(config).read_text(encoding="utf-8").splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key, value = line.split("=", 1)
            if key in values:
                raise Refusal(f"duplicate kernel configuration: {key}")
            values[key] = value
    missing = [key for key in BUILTIN if values.get("CONFIG_" + key) != "y"]
    missing += [key for key in AVAILABLE if values.get("CONFIG_" + key) not in {"y", "m"}]
    if missing:
        raise Refusal("kernel lacks required native/live options: " + ", ".join(missing))
    return values


def check_kernel(root, release):
    if not re.fullmatch(r"[0-9][A-Za-z0-9._+-]{1,95}", release):
        raise Refusal("invalid kernel release")
    root = Path(root)
    image = root_path(root, "boot/vmlinuz-" + release)
    config = root_path(root, "boot/config-" + release)
    for path in (image, config):
        file_hash(path)
    check_config(config)
    raw = image.read_bytes()
    if (len(raw) < 0x260 or raw[0x202:0x206] != b"HdrS"
            or struct.unpack_from("<H", raw, 0x206)[0] < 0x20C
            or not struct.unpack_from("<H", raw, 0x236)[0] & 1):
        raise Refusal("kernel is not a supported x86_64 bzImage")
    offset = 0x200 + struct.unpack_from("<H", raw, 0x20E)[0]
    version = raw[offset:offset + 256].split(b"\0", 1)[0].decode("ascii", errors="strict")
    if not version.startswith(release + " "):
        raise Refusal("kernel header release differs from modules release")
    modules = root_path(root, "usr/lib/modules/" + release)
    for name in ("modules.dep", "modules.alias", "modules.builtin", "modules.builtin.modinfo", "modules.order"):
        file_hash(modules / name)
    return {"release": release, "image_sha256": file_hash(image), "config_sha256": file_hash(config),
            "modules_sha256": tree_hash(modules)}


def check_offline_root(root):
    if Path(root).is_symlink():
        raise Refusal("source root must not be a symbolic link")
    root = Path(root).resolve()
    if root == Path(root.anchor) or not root.is_dir():
        raise Refusal("supply an explicit offline TUP root")
    # These are not silently excluded from the payload. An export must be
    # consciously prepared before this layer packages it.
    for name in ("dev", "proc", "sys", "run", "tmp", "sources", "tools", "tup-build"):
        path = root_path(root, name)
        if path.is_symlink() or (path.exists() and (not path.is_dir() or any(path.iterdir()))):
            raise Refusal(f"offline root must have empty/absent {name}")
    identity = root_path(root, "etc/machine-id")
    if identity.exists() and identity.read_bytes().strip():
        raise Refusal("live template must not contain a cloned machine identity")
    # The LFS D-Bus page links /var/lib/dbus/machine-id to /etc/machine-id, so
    # both names are the one file checked above. Any other link, or a file
    # with content, would be a second identity.
    legacy = root_path(root, "var/lib/dbus") / "machine-id"
    if legacy.is_symlink():
        if os.readlink(legacy) != "/etc/machine-id":
            raise Refusal("live template has a machine identity link that is not the book's /etc/machine-id")
    elif legacy.exists() and legacy.read_bytes().strip():
        raise Refusal("live template must not contain a cloned machine identity")
    ssh = root_path(root, "etc/ssh")
    if ssh.exists() and list(ssh.glob("ssh_host_*_key")):
        raise Refusal("live template contains private SSH host keys")
    shadow = root_path(root, "etc/shadow")
    file_hash(shadow)
    accounts = [line.split(":") for line in shadow.read_text().splitlines()]
    roots = [row for row in accounts if row[0] == "root"]
    if len(roots) != 1 or len(roots[0]) < 2 or not roots[0][1].startswith(("!", "*")):
        raise Refusal("live root account must be locked; no default password")
    os_release = root_path(root, "etc/os-release")
    file_hash(os_release)
    release_text = os_release.read_text(encoding="utf-8")
    if (len(re.findall(r'^ID=(?:tup|"tup")$', release_text, re.M)) != 1
            or len(re.findall(r'^VERSION_ID="?[A-Za-z0-9._+-]+"?$', release_text, re.M)) != 1):
        raise Refusal("explicit TUP os-release ID/version required for the live export")
    for name in ("usr/lib/systemd/systemd", "usr/bin/bash", "usr/sbin/dmsetup"):
        path = root_path(root, name)
        file_hash(path)
        raw = path.read_bytes()[:20]
        if len(raw) != 20 or raw[:6] != b"\x7fELF\x02\x01" or raw[18:20] != b"\x3e\x00":
            raise Refusal(f"expected x86_64 ELF target binary: {name}")
    # fstab must not mount the preparation host or an installed root at boot.
    fstab = root_path(root, "etc/fstab")
    if fstab.exists() and any(line.strip() and not line.lstrip().startswith("#")
                             for line in fstab.read_text().splitlines()):
        raise Refusal("live root requires an empty/comment-only fstab")
    return root
