#!/usr/bin/env python3
"""Plan and apply the installation of the TUP live root onto one whole disk.

Run as root from the booted TUP live system. Nothing here is interactive, uses
the network or writes firmware variables.

plan   reads the target disk, the running system and the live root's read-only
       lower root, refuses unsafe targets, and writes PLAN.json. It runs only
       read-only commands and opens the target only to read its first and last
       MiB. It writes nothing to the target. The summary it prints ends with
       the confirmation token. A disk that looks like Windows (NTFS, BitLocker,
       ReFS, exFAT, LDM or Storage Spaces, or a Microsoft partition type) is
       refused outright: no flag overrides that.
apply  re-reads all of it, refuses on any difference from the plan, records its
       intent, then partitions (one sfdisk script), formats the two planned
       partitions, copies the lower root with cp -a, writes fstab, the
       optional enrollment input and a GRUB image plus kernel and AMD
       microcode on the ESP, verifies the result and only then writes a
       receipt. It never resumes: a state directory that exists, or a disk
       that no longer matches the plan, means a new plan. The disk is checked
       against the plan once more immediately before the first write.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import posixpath
import re
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tup.boot import inputs
from tup.boot.inputs import Refusal, canonical, check_kernel, check_offline_root, digest, file_hash, inventory, load_json

MIB = 1 << 20
PATH = "/usr/sbin:/usr/bin:/sbin:/bin"
ESP_TYPE = "C12A7328-F81F-11D2-BA4B-00A0C93EC93B"
ROOT_TYPE = "4F68BCE3-E8CD-4DB1-96E7-FBCAF984B709"
PLAN_SCHEMA = "tup.install-disk-plan.v1"
INTENT_SCHEMA = "tup.install-intent.v1"
RECEIPT_SCHEMA = "tup.install-receipt.v1"
ESP_LABEL, ROOT_LABEL = "TUP-ESP", "TUP-ROOT"
# systemd.gpt_auto=0: with the root and the ESP named in fstab, systemd-gpt-auto-generator must not mount the ESP
# a second time (systemd.kernel-command-line(7), systemd-gpt-auto-generator(8)).
CMDLINE = "rootwait ro systemd.gpt_auto=0"
# Same console policy as tup/boot/assemble.py grub_config(): the last console= is /dev/console.
SCREEN_CONSOLES = "console=ttyS0,115200n8 console=tty0"
SERIAL_CONSOLES = "console=tty0 console=ttyS0,115200n8 systemd.log_target=console"
MICROCODE = "usr/lib/firmware/amd-ucode/microcode_amd_fam19h.bin"
# The files tup/remote/enroll.py plan() reads, with its size limits.
ENROLL_FILES = {"authorized_keys": 16384, "owner": 256, "listen": 4096, "peer": 4096, "clock": 64}
# macOS adds these beside the owner's files; enroll.py never reads them. Every other name is refused.
ENROLL_IGNORED = re.compile(r"\.DS_Store|\._.*")
ENROLL_TARGET = "etc/tup/enroll-input"
SOURCE_FILESYSTEMS = {"squashfs", "erofs"}
# Anonymous (major 0) mounts that cannot hold a disk. Any other major-0 row without a /dev source is a refusal.
PSEUDO_FILESYSTEMS = {"tmpfs", "ramfs", "rootfs", "proc", "sysfs", "devtmpfs", "devpts", "overlay", "cgroup", "cgroup2",
                      "securityfs", "debugfs", "tracefs", "configfs", "fusectl", "mqueue", "hugetlbfs", "pstore", "bpf",
                      "binfmt_misc", "autofs", "efivarfs", "selinuxfs", "nsfs", "rpc_pipefs"}
VOLATILE_FILESYSTEMS = {"tmpfs", "ramfs", "rootfs"}
# util-linux 2.42.4 include/pt-gpt-partnames.h and include/pt-mbr-partnames.h (the tables fdisk and sfdisk print).
WINDOWS_GPT = {"EBD0A0A2-B9E5-4433-87C0-68B6B72699C7": "Microsoft basic data",
               "E3C9E316-0B5C-4DB8-817D-F92DF00215AE": "Microsoft reserved",
               "DE94BBA4-06D1-4D40-A16A-BFD50179D6AC": "Windows recovery environment",
               "5808C8AA-7E8F-42E0-85D2-E1E90434CFB3": "Microsoft LDM metadata",
               "AF9B60A0-1431-4F62-BC68-3311714A69AD": "Microsoft LDM data",
               "E75CAF8F-F680-4CEE-AFA3-B001E56EFC2D": "Microsoft Storage Spaces"}
WINDOWS_MBR = {0x07: "HPFS/NTFS/exFAT", 0x27: "Hidden NTFS WinRE", 0x42: "SFS (Windows dynamic disk, LDM)"}
# libblkid 2.42.4 superblock names (ntfs.c, bitlocker.c, refs.c, exfat.c); wipefs and blkid print them.
WINDOWS_SIGNATURES = {"ntfs", "bitlocker", "refs", "exfat"}
# Fewest sectors for which mkfs.fat 4.2 -F 32 -S SECTOR does not print "Number of clusters for 32 bit FAT is less then
# suggested minimum" (65525 clusters; below it the command still succeeds). Found by bisection on regular files:
# 65695 sectors warn and 65696 do not at 4096 bytes; 66591 warn and 66592 do not at 512 bytes. The tests redo it.
FAT32_FLOOR = {512: 66592, 4096: 65696}
# Name patterns of devices that are never a whole physical disk.
NOT_A_DISK = re.compile(r"(loop|dm-|md|zram|ram|nbd|sr|fd)\d*$")
GUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
LSBLK_COLUMNS = ("NAME,KNAME,PATH,MAJ:MIN,TYPE,MODEL,SERIAL,WWN,SIZE,LOG-SEC,PHY-SEC,TRAN,RM,HOTPLUG,RO,PTTYPE,"
                 "PTUUID,FSTYPE,UUID,PARTUUID,PARTTYPE,PARTLABEL,LABEL,MOUNTPOINTS,VENDOR,REV")
# Each tool and the arguments that make it print its version without acting.
TOOLS = {"lsblk": ["--version"], "sfdisk": ["--version"], "blkid": ["--version"], "wipefs": ["--version"],
         "udevadm": ["--version"], "mkfs.fat": ["--help"], "fsck.fat": ["--help"], "mkfs.ext4": ["-V"],
         "e2fsck": ["-V"], "mount": ["--version"], "umount": ["--version"], "cp": ["--version"],
         "sync": ["--version"], "grub-mkstandalone": ["--version"], "grub-script-check": ["--version"]}


class Interrupted(KeyboardInterrupt):
    pass


class Host:
    """Every command and every /sys, /proc or device observation goes through here."""

    def run(self, argv, stdin=None, timeout=900, detached=False):
        """detached: the child gets its own session, so a Ctrl-C or hangup aimed at the installer does not reach
        it. If the installer is signalled meanwhile it waits for the child instead of killing it half way
        through a write; a repeated signal does not abandon the wait."""
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL if stdin is None else subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=detached,
                                   env={"PATH": PATH, "LC_ALL": "C"})
        try:
            out, err = process.communicate(stdin, timeout)
        except BaseException as error:
            if detached and isinstance(error, KeyboardInterrupt):
                while True:
                    try:
                        process.communicate()
                        break
                    except KeyboardInterrupt:
                        continue
            else:
                process.kill()
                process.communicate()
            raise
        return process.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")

    def read_block(self, path, offset, length):
        """Read-only sample of a device or file: opened O_RDONLY, never through a tool that can write."""
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_CLOEXEC", 0))
        try:
            data = b""
            while len(data) < length:
                chunk = os.pread(fd, length - len(data), offset + len(data))
                if not chunk:
                    break
                data += chunk
            return data
        finally:
            os.close(fd)

    def read(self, path):
        return Path(path).read_text(encoding="utf-8", errors="replace")

    def listdir(self, path):
        return sorted(os.listdir(path))

    def realpath(self, path):
        return os.path.realpath(path)

    def exists(self, path):
        return os.path.exists(path)

    def is_block(self, path):
        return stat.S_ISBLK(os.stat(path).st_mode)

    def fs_devno(self, path):
        device = os.stat(path).st_dev
        return f"{os.major(device)}:{os.minor(device)}"

    def block_devno(self, path):
        device = os.stat(path).st_rdev
        return f"{os.major(device)}:{os.minor(device)}"

    def which(self, name):
        return shutil.which(name, path=PATH)

    def sha256(self, path):
        return file_hash(os.path.realpath(path))  # mkfs.ext4 is a symbolic link to mke2fs

    def now(self):
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def sleep(self, seconds):
        time.sleep(seconds)

    def random(self, count):
        return secrets.token_bytes(count)


def read_only_command(argv):
    """The only shapes plan may run. A new shape must be added here on purpose."""
    name, args = posixpath.basename(argv[0]), argv[1:]
    if args in (["--version"], ["--help"], ["-V"]):
        return name in TOOLS
    if name == "lsblk":
        return args[:3] == ["--json", "--bytes", "-o"] and len(args) == 5
    if name == "sfdisk":
        return len(args) == 2 and args[0] in ("--dump", "--json")
    if name == "blkid":
        return len(args) == 4 and args[:3] == ["-p", "-o", "export"]
    if name == "wipefs":
        return len(args) == 3 and args[:2] == ["--no-act", "--json"]
    return False


class Planning:
    """plan's view of the host: refuses any command that could write."""

    def __init__(self, host):
        self.host = host

    def run(self, argv, stdin=None, timeout=900):
        if not read_only_command(argv):
            raise Refusal("plan refused to run a command that is not read-only: " + " ".join(argv))
        return self.host.run(argv, stdin, timeout)

    def __getattr__(self, name):
        return getattr(self.host, name)


def check_platform():
    if sys.platform != "linux" or not hasattr(os, "geteuid"):
        raise Refusal("the disk installer runs on the TUP Linux live system")


def short(value):
    return value if len(value) <= 4000 else value[:4000] + "...[truncated]"


# --- observation ---------------------------------------------------------------------------

def measure_tools(host, expected=None):
    """Absolute path, SHA256 and reported version of every tool. With expected, refuse any change."""
    found = {}
    for name, version in TOOLS.items():
        path = expected[name]["path"] if expected else host.which(name)
        if not path:
            raise Refusal(f"required tool not found: {name}")
        code, out, err = host.run([path, *version], timeout=60)
        text = [line.strip() for line in (out + "\n" + err).splitlines()
                if re.search(r"\d", line) and not line.lstrip().startswith("Usage")]
        found[name] = {"path": path, "sha256": host.sha256(path), "version": text[0] if text else "unreported"}
        if expected and found[name] != expected[name]:
            raise Refusal(f"tool changed since the plan: {name}")
    return found


def run_json(host, tools, name, *args):
    code, out, err = host.run([tools[name]["path"], *args])
    if code:
        raise Refusal(f"{name} {' '.join(args)} failed ({code}): {err.strip()}")
    try:
        return json.loads(out)
    except ValueError as error:
        raise Refusal(f"{name} produced unreadable JSON") from error


def text(value):
    return value.strip() if isinstance(value, str) else value


def flag(value):
    return value in (True, 1, "1", "true")


def block_entry(node):
    keys = ("kname", "path", "maj:min", "type", "fstype", "uuid", "partuuid", "parttype", "partlabel", "label",
            "pttype", "ptuuid")
    entry = {key.replace(":", "_"): text(node.get(key)) for key in keys}
    entry["size_bytes"] = int(node["size"])
    entry["children"] = [block_entry(child) for child in node.get("children", [])]
    return entry


def descendants(entry):
    for child in entry["children"]:
        yield child
        yield from descendants(child)


def mountpoints(node):
    found = [mp for mp in node.get("mountpoints") or [] if mp]
    for child in node.get("children", []):
        found += mountpoints(child)
    return found


def read_identity(host, tools, target):
    """Whole-disk identity from lsblk. Mount points are returned apart: they are state, not identity."""
    devices = run_json(host, tools, "lsblk", "--json", "--bytes", "-o", LSBLK_COLUMNS, target)["blockdevices"]
    if len(devices) != 1 or text(devices[0].get("path")) != target:
        raise Refusal(f"lsblk did not describe exactly {target}")
    node = devices[0]
    identity = block_entry(node)
    identity.update(model=text(node.get("model")), serial=text(node.get("serial")), wwn=text(node.get("wwn")),
                    vendor=text(node.get("vendor")), rev=text(node.get("rev")), tran=text(node.get("tran")),
                    log_sec=int(node["log-sec"]), phy_sec=int(node["phy-sec"]), removable=flag(node.get("rm")),
                    hotplug=flag(node.get("hotplug")), read_only=flag(node.get("ro")))
    return identity, mountpoints(node)


def read_state(host, tools, identity):
    """The partition table dump and every signature of the disk and of each partition on it."""
    nodes = [identity["path"]] + [child["path"] for child in descendants(identity)]
    code, out, err = host.run([tools["sfdisk"]["path"], "--dump", identity["path"]])
    dump, unreadable = (out, None) if code == 0 else (None, None)
    if code and not (code == 1 and "does not contain a recognized partition table" in err):
        unreadable = f"sfdisk --dump failed ({code}): {err.strip()}"  # a damaged table is still data
    wipefs, blkid = {}, {}
    for node in nodes:
        found = run_json(host, tools, "wipefs", "--no-act", "--json", node)["signatures"]
        wipefs[node] = [{key: item.get(key) for key in ("offset", "type", "uuid", "label")} for item in found]
        code, out, err = host.run([tools["blkid"]["path"], "-p", "-o", "export", node])
        if code not in (0, 2):
            raise Refusal(f"blkid -p failed on {node} ({code}): {err.strip()}")
        blkid[node] = dict(line.split("=", 1) for line in out.splitlines() if "=" in line) if code == 0 else {}
    return {"sfdisk_dump": dump, "sfdisk_unreadable": unreadable, "wipefs": wipefs, "blkid": blkid,
            "sample": read_sample(host, identity)}


def read_sample(host, identity):
    """First and last MiB of the disk, read-only: where its offset, first non-zero byte and digest are recorded.
    A disk with no table and no signature is blank only if both are all zero."""
    path, size, regions = identity["path"], identity["size_bytes"], {}
    for name, offset in (("head", 0), ("tail", max(0, size - MIB))):
        length = min(MIB, size - offset)
        try:
            data = host.read_block(path, offset, length)
        except OSError as error:
            raise Refusal(f"cannot read the {name} of {path} to see whether it is empty: {error}") from error
        if len(data) != length:
            raise Refusal(f"short read of the {name} of {path}: {len(data)} of {length} bytes")
        regions[name] = {"offset": offset, "length": length, "sha256": digest(data),
                         "first_nonzero": offset + len(data) - len(data.lstrip(b"\0")) if data.strip(b"\0") else None}
    return regions


def windows_evidence(identity, state):
    """Everything in the read state that says Windows owns this disk. Types are util-linux's own tables."""
    found = []

    def signature(kind, where):
        if str(kind).lower() in WINDOWS_SIGNATURES or "ldm" in str(kind).lower():
            found.append(f"{kind} signature on {where}")

    def partition_type(value, label, where):
        value = str(value or "").strip()
        if label == "dos" or re.fullmatch(r"0[xX][0-9a-fA-F]+", value):
            kind = WINDOWS_MBR.get(int(value, 16)) if re.fullmatch(r"(0[xX])?[0-9a-fA-F]{1,2}", value) else None
        else:
            kind = WINDOWS_GPT.get(value.upper())
        if kind:
            found.append(f"partition type {value} ({kind}) on {where}")

    for node, items in state["wipefs"].items():
        for item in items:
            signature(item["type"], node)
    for node, values in state["blkid"].items():
        signature(values.get("TYPE"), node)
        signature(values.get("PTTYPE"), node)
    for entry in [identity, *descendants(identity)]:
        signature(entry["fstype"], entry["path"])
        partition_type(entry["parttype"], identity["pttype"], entry["path"])
    rows = (state["sfdisk_dump"] or "").splitlines()
    label = next((row.split(":", 1)[1].strip() for row in rows if row.startswith("label:")), None)
    for row in rows:
        match = re.match(r"(/dev/\S+)\s*:.*\btype=([0-9A-Fa-f-]+)", row)
        if match:
            partition_type(match[2], label, match[1])
    return found


def refuse_windows(identity, state):
    found = windows_evidence(identity, state)
    if found:
        raise Refusal(f"{identity['path']} looks like a Windows disk and this installer never erases a disk that looks "
                      "like Windows, with or without --allow-existing. A disk like this must be cleared by the owner "
                      "by other means first. Found:\n  " + "\n  ".join(dict.fromkeys(found)))


def existing_lines(identity, state):
    """What a write would destroy, in words."""
    lines = []
    if state["sfdisk_unreadable"]:
        lines.append("a partition table that sfdisk cannot read: " + state["sfdisk_unreadable"])
    if state["sfdisk_dump"]:
        rows = state["sfdisk_dump"].splitlines()
        header = {k: v.strip() for k, _, v in (row.partition(":") for row in rows if row[:1].isalpha() and ": " in row)}
        entries = [row.split(":", 1)[1].strip() for row in rows if row.startswith("/dev/")]
        lines.append(f"partition table {header.get('label', '?')}, identifier {header.get('label-id', 'none')}, "
                     f"{len(entries)} partition(s): " + "; ".join(entries))
    for child in descendants(identity):
        lines.append(f"partition {child['path']}: {child['size_bytes']} bytes, type {child['parttype']}, "
                     f"label {child['partlabel']}, filesystem {child['fstype']} {child['label'] or ''} {child['uuid'] or ''}")
    for node, items in state["wipefs"].items():
        for item in items:
            lines.append(f"signature {item['type']} at offset {item['offset']} on {node} "
                         f"(uuid {item['uuid']}, label {item['label']})")
    for node, values in state["blkid"].items():
        if values:
            lines.append(f"blkid on {node}: " + " ".join(f"{k}={v}" for k, v in sorted(values.items())))
    # lsblk reads the udev database, the other tools read the device: a disagreement must not pass as blank.
    facts = {key: identity[key] for key in ("pttype", "ptuuid", "fstype", "uuid", "partuuid", "label") if identity[key]}
    if facts:
        lines.append(f"lsblk on {identity['path']}: " + " ".join(f"{k}={v}" for k, v in sorted(facts.items())))
    if not lines:
        for name, region in state["sample"].items():
            if region["first_nonzero"] is not None:
                lines.append(f"unrecognised non-zero data in the {name} of the disk ({region['length']} bytes read from "
                             f"offset {region['offset']}): first non-zero byte at offset {region['first_nonzero']}; "
                             "no partition table or signature names it")
    return lines


# --- what already uses which disk ------------------------------------------------------------

def unescape(value):
    return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), value)


def mount_table(host):
    rows = []
    for line in host.read("/proc/self/mountinfo").splitlines():
        left, _, right = line.partition(" - ")
        fields, rest = left.split(), right.split(" ", 2)
        rows.append({"majmin": fields[2], "mountpoint": unescape(fields[4]), "options": fields[5].split(","),
                     "fstype": rest[0], "source": rest[1], "super": rest[2] if len(rest) > 2 else ""})
    return rows


def disks_for_row(host, row, seen):
    """Disks behind one mount-table row. A major-0 device number is anonymous, but not always harmless: a btrfs
    or FUSE (ntfs-3g, exfat) mount has one and names its block device as the source. Those are resolved through
    that device node; a pseudo filesystem holds no disk; anything else is a refusal, never a guess."""
    if row["majmin"].split(":")[0] != "0":
        return disks_for_devno(host, row["majmin"], seen)
    if row["source"].startswith("/dev/"):
        return disks_for_devno(host, host.block_devno(row["source"]), seen)
    if row["fstype"] in PSEUDO_FILESYSTEMS:
        return set()
    raise Refusal(f"{row['fstype']} mounted at {row['mountpoint']} has an anonymous device number and the source "
                  f"{row['source']!r} is not a /dev path; cannot tell which disk holds it")


def disks_for_devno(host, majmin, seen):
    if majmin.split(":")[0] == "0":  # st_dev of a file on an anonymous mount: ask the mount table which one
        rows = [row for row in mount_table(host) if row["majmin"] == majmin]
        if not rows:
            raise Refusal(f"device {majmin} is not in the mount table; cannot tell which disk holds it")
        found = set()
        for row in rows:
            found |= disks_for_row(host, row, seen)
        return found
    name = posixpath.basename(host.realpath("/sys/dev/block/" + majmin))
    return disks_behind(host, name, seen)


def disks_behind(host, name, seen):
    """Whole disks that physically hold block device `name`, through partitions, dm/md and loop files."""
    if name in seen:
        return set()
    seen.add(name)
    base = host.realpath("/sys/class/block/" + name)
    if not host.exists(base):
        raise Refusal(f"/sys/class/block/{name} does not exist; cannot tell which disk it is on")
    if host.exists(base + "/partition"):
        return disks_behind(host, posixpath.basename(posixpath.dirname(base)), seen)
    found = set()
    slaves = host.listdir(base + "/slaves") if host.exists(base + "/slaves") else []
    for slave in slaves:
        found |= disks_behind(host, slave, seen)
    if host.exists(base + "/loop/backing_file"):
        backing = host.read(base + "/loop/backing_file").strip()
        try:
            # A loop device over a block special file (losetup /dev/loopN /dev/sdX): st_dev of such a node is the
            # devtmpfs, the disk is its st_rdev.
            devno = host.block_devno(backing) if host.is_block(backing) else host.fs_devno(backing)
            found |= disks_for_devno(host, devno, seen)
        except OSError as error:
            raise Refusal(f"cannot resolve the backing file {backing} of {name} to a disk: {error}") from error
    elif not slaves:
        found.add(name)
    return found


def disks_in_use(host, paths):
    """{disk: [reasons]} for every mount, swap area and given path (the live root's source, the state)."""
    use = {}

    def note(label, resolve):
        try:
            disks = resolve()
        except OSError as error:
            raise Refusal(f"cannot tell which disk holds {label}: {error}") from error
        for disk in disks:
            use.setdefault(disk, []).append(label)

    for row in mount_table(host):
        label = f"{row['fstype']} mounted at {row['mountpoint']}"
        note(label, lambda row=row: disks_for_row(host, row, set()))
        if row["fstype"] == "overlay":
            for option in row["super"].split(","):
                key, _, value = option.partition("=")
                if key in ("lowerdir", "upperdir", "workdir"):
                    for part in value.split(":"):
                        note(f"{key} {part} of the overlay at {row['mountpoint']}",
                             lambda part=part: disks_for_devno(host, host.fs_devno(part), set()))
    for line in host.read("/proc/swaps").splitlines()[1:]:
        area = unescape(line.split()[0]) if line.split() else None
        if area:
            devno = host.block_devno if area.startswith("/dev/") else host.fs_devno
            note(f"swap area {area}", lambda area=area, devno=devno: disks_for_devno(host, devno(area), set()))
    for label, path in paths.items():
        note(f"{label} {path}", lambda path=path: disks_for_devno(host, host.fs_devno(path), set()))
    return use


def holders_of(host, identity):
    base = host.realpath("/sys/class/block/" + identity["kname"])
    found = []
    for path, name in [(base, identity["kname"])] + [(f"{base}/{c['kname']}", c["kname"]) for c in descendants(identity)]:
        if host.exists(path + "/holders"):
            found += [f"{name} held by {holder}" for holder in host.listdir(path + "/holders")]
    return found


def check_device_path(host, target):
    if not re.fullmatch(r"/dev/[A-Za-z0-9][A-Za-z0-9._-]*", target) or host.realpath(target) != target:
        raise Refusal("--target must be a kernel device name such as /dev/nvme0n1, not a symbolic link or by-id path")
    if not host.is_block(target):
        raise Refusal(f"{target} is not a block device")


def check_target(host, identity, mounted, use):
    target, name = identity["path"], identity["kname"]
    base = host.realpath("/sys/class/block/" + name)
    if identity["type"] != "disk" or NOT_A_DISK.match(name) or any(
            host.exists(f"{base}/{part}") for part in ("partition", "loop", "dm", "md")):
        raise Refusal(f"{target} is not a whole physical disk (type {identity['type']}); partitions, loop, "
                      "device-mapper, md, zram and optical devices are refused")
    if identity["read_only"] or (host.exists(base + "/ro") and host.read(base + "/ro").strip() == "1"):
        raise Refusal(f"{target} is read-only")
    if mounted:
        raise Refusal(f"{target} has mounted partitions: {', '.join(sorted(mounted))}")
    if name in use:
        raise Refusal(f"{target} is in use by this system: {'; '.join(use[name])}")
    if holders_of(host, identity):
        raise Refusal(f"{target} is held by device-mapper or md: {', '.join(holders_of(host, identity))}")


def confirmation_token(identity, plan_sha):
    """Disk serial (WWN without one) and the plan digest: it cannot be typed for another disk or plan."""
    name = identity["serial"] or identity["wwn"]
    if not name:
        raise Refusal(f"{identity['path']} reports neither a serial nor a WWN, so it cannot be named in a confirmation")
    return re.sub(r"[^A-Za-z0-9._-]", "_", name) + "-" + plan_sha[:8]


# --- layout and generated files ----------------------------------------------------------

def make_layout(identity, esp_mib, random):
    """Everything that names the new disk, fixed before any write. Sectors are logical sectors."""
    sector, size = identity["log_sec"], identity["size_bytes"]
    if sector not in (512, 4096) or size % sector:
        raise Refusal(f"unsupported logical sector size {sector}")
    align, total = MIB // sector, size // sector
    last_usable = total - -(-16384 // sector) - 2  # primary header, 128 entries, backup header
    esp_start, esp_size = align, esp_mib * MIB // sector
    if esp_size < FAT32_FLOOR[sector]:
        raise Refusal(f"an ESP of {esp_mib} MiB on {sector}-byte sectors has fewer than 65525 FAT32 clusters, so "
                      f"mkfs.fat would not make a FAT32 volume; use --esp-mib {-(-FAT32_FLOOR[sector] * sector // MIB)} "
                      "or more")
    root_start = esp_start + esp_size
    root_size = (last_usable + 1) // align * align - root_start

    def guid():
        return str(uuid.UUID(bytes=random(16), version=4))

    volume = int.from_bytes(random(4), "big") or 1
    return {
        "sector_size": sector, "disk_guid": guid(),
        "partitions": [
            {"number": 1, "name": ESP_LABEL, "type": ESP_TYPE, "guid": guid(), "start": esp_start, "size": esp_size},
            {"number": 2, "name": ROOT_LABEL, "type": ROOT_TYPE, "guid": guid(), "start": root_start, "size": root_size}],
        "esp": {"label": ESP_LABEL, "volume_id": f"{volume:08X}", "uuid": f"{volume >> 16:04X}-{volume & 0xFFFF:04X}"},
        "root": {"label": ROOT_LABEL, "uuid": guid()}}


def sfdisk_script(layout):
    rows = [f'start={p["start"]}, size={p["size"]}, type={p["type"]}, uuid={p["guid"]}, name="{p["name"]}"'
            for p in layout["partitions"]]
    return "\n".join(["label: gpt", "label-id: " + layout["disk_guid"], "unit: sectors",
                      f"sector-size: {layout['sector_size']}", "", *rows]) + "\n"


def fstab_text(layout, basis):
    return (f"# /etc/fstab, written by tup/install/disk.py for plan {basis[:12]}\n"
            "# file system   mount-point  type  options  dump  fsck\n"
            f"UUID={layout['root']['uuid']}  /  ext4  defaults,errors=remount-ro  0  1\n"
            f"UUID={layout['esp']['uuid']}  /boot/efi  vfat  "
            "umask=0077,rw,relatime,codepage=437,iocharset=iso8859-1,nofail,x-systemd.device-timeout=10s  0  2\n")


def grub_cfg_text(layout, kernel, microcode, basis):
    """GRUB reads only the ESP. The menu follows tup/boot/assemble.py grub_config(): output on the screen and the
    serial port, input from the local console only (noise on an absent UART could stop the countdown of a headless
    boot), the screen entry by default and the serial-diagnostics entry when the SMBIOS manufacturer is QEMU
    (GRUB manual, "smbios"). There is no rescue.target entry: root is locked, so sulogin would refuse to open a
    shell and could hang a headless machine."""
    command = f"/tup/{kernel['name']} root=PARTUUID={layout['partitions'][1]['guid']} {CMDLINE}"
    initrd = ["    initrd /tup/amd-ucode.img"] if microcode["loaded"] else []
    entries = []
    for title, ident, consoles in (("TUP (boot messages on the screen)", "tup", SCREEN_CONSOLES),
                                   ("TUP (diagnostics on the serial port)", "tup-serial", SERIAL_CONSOLES)):
        entries += [f"menuentry '{title}' --id {ident} " + "{", f"    linux {command} {consoles}", *initrd, "}"]
    return "\n".join([f"# TUP boot menu, written by tup/install/disk.py for plan {basis[:12]}",
                      "set default=tup", "set timeout=3",
                      "serial --unit=0 --speed=115200 --word=8 --parity=no --stop=1",
                      "terminal_input console", "terminal_output console serial",
                      "insmod part_gpt", "insmod fat", "insmod search", "insmod linux",
                      f"search --no-floppy --fs-uuid --set=root {layout['esp']['uuid'].lower()}",
                      "insmod smbios", "smbios --type 1 --get-string 4 --set tup_system_manufacturer",
                      'if [ "$tup_system_manufacturer" = "QEMU" ]; then', "    set default=tup-serial", "fi",
                      *entries]) + "\n"


def microcode_cpio(blob):
    """Uncompressed newc archive holding kernel/x86/microcode/AuthenticAMD.bin: the kernel's early loader
    reads it from the start of the initrd (docs.kernel.org/arch/x86/microcode.html)."""
    out = bytearray()

    def member(number, name, mode, data, links):
        raw = name.encode() + b"\0"
        out.extend(("070701" + "".join(f"{value:08X}" for value in (
            number, mode, 0, 0, links, 0, len(data), 0, 0, 0, 0, len(raw), 0))).encode() + raw)
        out.extend(b"\0" * (-len(out) % 4) + data)
        out.extend(b"\0" * (-len(out) % 4))

    for number, name in enumerate(("kernel", "kernel/x86", "kernel/x86/microcode"), 1):
        member(number, name, 0o040755, b"", 2)
    member(4, "kernel/x86/microcode/AuthenticAMD.bin", 0o100644, blob, 1)
    member(0, "TRAILER!!!", 0, b"", 1)
    return bytes(out)


def parse_microcode_cpio(raw):
    """Minimal newc reader used to verify what was built: {name: (mode, data)}."""
    found, offset = {}, 0
    while True:
        if raw[offset:offset + 6] != b"070701":
            raise Refusal("microcode archive is not newc")
        fields = [int(raw[offset + 6 + 8 * i:offset + 14 + 8 * i], 16) for i in range(13)]
        start = offset + 110
        name = raw[start:start + fields[11] - 1].decode()
        data_at = start + fields[11] + (-(start + fields[11]) % 4)
        if name == "TRAILER!!!":
            return found
        found[name] = (fields[1], raw[data_at:data_at + fields[6]])
        offset = data_at + fields[6] + (-(data_at + fields[6]) % 4)


# --- source, enrollment input, plan -------------------------------------------------------

def check_source(host, source):
    if not os.path.isabs(source) or host.realpath(source) != source:
        raise Refusal("--source must be an absolute path without symbolic links")
    rows = [row for row in mount_table(host) if row["mountpoint"] == source]
    if not rows or rows[-1]["fstype"] not in SOURCE_FILESYSTEMS or "ro" not in rows[-1]["options"]:
        raise Refusal(f"{source} is not a read-only {'/'.join(sorted(SOURCE_FILESYSTEMS))} mount: only the live "
                      "system's read-only lower root may be copied (the running / carries enrollment state)")
    return {"fstype": rows[-1]["fstype"], "source": rows[-1]["source"]}


def read_source(source):
    """Validate the lower root and return (inventory, its summary, kernel, microcode)."""
    check_offline_root(source)
    if os.path.lexists(os.path.join(source, "etc/tup/owner-enrolled.json")):
        raise Refusal("the source already carries owner enrollment state")
    tup_dir = Path(source, "etc/tup")
    if os.path.lexists(tup_dir):
        info = tup_dir.lstat()
        # (the installer runs only on Linux, see check_platform; the unit tests of plan also run elsewhere)
        if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o022 or (
                hasattr(os, "geteuid") and info.st_uid != os.geteuid()):
            raise Refusal("/etc/tup in the source is not a real directory owned by the installer and closed to group "
                          "and other writers; enroll.py would refuse to enroll below it")
    leftover = Path(source, ENROLL_TARGET)
    if os.path.lexists(leftover) and (leftover.is_symlink() or not leftover.is_dir() or any(leftover.iterdir())):
        raise Refusal(f"the source carries enrollment input at /{ENROLL_TARGET}; only --enroll-input may supply it")
    images = sorted(Path(source, "boot").glob("vmlinuz-*"))
    if len(images) != 1:
        raise Refusal("the source must hold exactly one /boot/vmlinuz-RELEASE")
    release = images[0].name.removeprefix("vmlinuz-")
    kernel = check_kernel(source, release)
    tree = inventory(source)
    sizes = [row["size"] for name, row in tree.items() if row["type"] == "file" and row.get("hardlink", name) == name]
    blob = Path(source, MICROCODE)
    if blob.is_file() and not blob.is_symlink():
        raw = blob.read_bytes()
        if raw[:4] != b"DMA\0":
            raise Refusal("the AMD microcode container lacks its DMA signature")
        microcode = {"loaded": True, "source": MICROCODE, "sha256": digest(raw), "cpio_sha256": digest(microcode_cpio(raw))}
    else:
        microcode = {"loaded": False, "reason": f"{MICROCODE} is absent from the source; AMD microcode is NOT loaded"}
    summary = {"inventory_sha256": digest(canonical(tree)), "entries": len(tree), "file_bytes": sum(sizes)}
    return tree, summary, {"release": release, "name": "vmlinuz-" + release,
                           "image_sha256": kernel["image_sha256"]}, microcode


def enroll_module():
    """tup/remote/enroll.py, the code that reads this input on the installed system's first boot: the repository's
    copy when run from a checkout, else the one the image installs. Loaded, not reimplemented."""
    for candidate in (Path(__file__).resolve().parents[1] / "remote/enroll.py", Path("/usr/lib/tup/remote/enroll.py")):
        if candidate.is_file():
            spec = importlib.util.spec_from_file_location("tup_installer_enroll", candidate)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module, candidate
    raise Refusal("remote/enroll.py is not available, so the enrollment input cannot be checked")


def read_enroll(directory):
    """Validate the input with enroll.py's own plan() (an input it would refuse at first boot leaves a headless
    machine unreachable), and bind the exact bytes by digest."""
    if directory is None:
        return None
    path = Path(directory)
    if path.is_symlink() or not path.is_dir():
        raise Refusal("--enroll-input must be a real directory")
    names = sorted(entry.name for entry in path.iterdir())
    ignored = [name for name in names if ENROLL_IGNORED.fullmatch(name)]
    names = [name for name in names if name not in ignored]
    if "authorized_keys" not in names or set(names) - set(ENROLL_FILES):
        raise Refusal(f"--enroll-input must hold authorized_keys and only {sorted(ENROLL_FILES)} (macOS metadata "
                      f".DS_Store and ._* is ignored); other names found: {sorted(set(names) - set(ENROLL_FILES))}")
    files = {}
    for name in names:
        info = (path / name).lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > ENROLL_FILES[name]:
            raise Refusal(f"enrollment input {name} must be a regular file of at most {ENROLL_FILES[name]} bytes")
        files[name] = file_hash(path / name)
    module, _ = enroll_module()
    try:
        accepted = module.plan(path)
    except ValueError as error:  # enroll.py's and policy.py's Refusal are ValueErrors
        raise Refusal(f"the installed system would refuse this enrollment input at its first boot: {error}") from error
    return {"path": str(path), "files": files, "ignored": ignored,
            "accepted": {"owner": accepted["owner"], "scope": accepted["scope"], "fingerprints": accepted["fingerprints"],
                         "clock": accepted["clock"]}}


def texts_for(plan):
    layout, basis = plan["layout"], plan["basis"]
    return {"sfdisk_script": sfdisk_script(layout), "fstab": fstab_text(layout, basis),
            "grub_cfg": grub_cfg_text(layout, plan["kernel"], plan["microcode"], basis)}


def installer_digests():
    return {"disk_py_sha256": file_hash(__file__), "inputs_py_sha256": file_hash(inputs.__file__),
            "enroll_py_sha256": file_hash(enroll_module()[1])}


def state_directory_facts(host, state):
    """Where the journal will live, if the operator already says: RAM does not survive a power cut."""
    if state is None:
        return None
    if not str(state).startswith("/"):
        raise Refusal("--state must be an absolute path")
    filesystem, volatile = state_storage(host, posixpath.dirname(str(state)))
    return {"path": str(state), "filesystem": filesystem, "volatile": volatile}


def plan_digest(plan):
    return digest(canonical({key: value for key, value in plan.items() if key != "digest"}))


def basis_digest(plan):
    return digest(canonical({key: value for key, value in plan.items() if key not in ("digest", "basis", "texts")}))


def state_storage(host, path, depth=0):
    """(filesystem type, volatile) of the filesystem that holds `path`; an overlay is followed to its upper layer."""
    path = host.realpath(path)
    best = None
    for row in mount_table(host):
        mountpoint = row["mountpoint"].rstrip("/")
        if (path == row["mountpoint"] or path.startswith(mountpoint + "/")) and (
                best is None or len(row["mountpoint"]) >= len(best["mountpoint"])):
            best = row
    if best is None:
        raise Refusal(f"{path} is not below any mount in the mount table")
    if best["fstype"] == "overlay":
        upper = dict(option.partition("=")[::2] for option in best["super"].split(",")).get("upperdir")
        if upper and depth < 4:
            return state_storage(host, upper, depth + 1)
        return "overlay", True
    return best["fstype"], best["fstype"] in VOLATILE_FILESYSTEMS


def make_plan(host, *, target, source, esp_mib=512, enroll_input=None, allow_existing=False, state=None):
    """Build the plan. `host` is wrapped so that nothing but read-only commands can run."""
    host = Planning(host)
    if not isinstance(esp_mib, int) or not 64 <= esp_mib <= 8192:
        raise Refusal("--esp-mib must be 64 to 8192")
    check_device_path(host, target)
    tools = measure_tools(host)
    identity, mounted = read_identity(host, tools, target)
    mount = check_source(host, source)
    use = disks_in_use(host, {"source": source})
    check_target(host, identity, mounted, use)
    state_read = read_state(host, tools, identity)
    refuse_windows(identity, state_read)  # no flag overrides this
    existing = existing_lines(identity, state_read)
    if existing and not allow_existing:
        raise Refusal(f"{target} already holds data and --allow-existing was not given. A Windows RAW report proves "
                      "nothing about emptiness. Found:\n  " + "\n  ".join(existing))
    tree, summary, kernel, microcode = read_source(source)
    enroll = read_enroll(enroll_input)
    needed = int(summary["file_bytes"] * 1.15) + (512 << 20)
    layout = make_layout(identity, esp_mib, host.random)
    root_bytes = layout["partitions"][1]["size"] * layout["sector_size"]
    if layout["partitions"][1]["size"] <= 0 or root_bytes < needed:
        raise Refusal(f"{target} is too small: the root partition would be {root_bytes} bytes, the live root needs "
                      f"at least {needed}")
    plan = {"schema": PLAN_SCHEMA, "created_at": host.now(), "allow_existing": allow_existing,
            "target": {"path": target, "identity": identity, "state": state_read, "disks_in_use": sorted(use),
                       "snapshot_sha256": digest(canonical({"identity": identity, "state": state_read}))},
            "destroys": existing or ["nothing: the disk has no partition table and no signature"],
            "source": {"path": source, "mount": mount, **summary}, "kernel": kernel, "microcode": microcode,
            "enroll_input": enroll, "layout": layout, "tools": tools,
            "installer": installer_digests(), "state_directory": state_directory_facts(host, state),
            "root_bytes_needed": needed, "confirmation_basis": "serial" if identity["serial"] else "wwn"}
    plan["basis"] = basis_digest(plan)
    plan["texts"] = texts_for(plan)
    plan["digest"] = plan_digest(plan)
    confirmation_token(identity, plan["digest"])  # refuses a disk that cannot be named
    return plan


def summary_text(plan):
    identity, layout = plan["target"]["identity"], plan["layout"]
    rows = [f"TUP disk install plan {plan['digest']}",
            f"  target      {identity['path']}  {identity['vendor'] or ''} {identity['model'] or ''}".rstrip(),
            f"              serial {identity['serial']}  wwn {identity['wwn']}  {identity['size_bytes']} bytes, "
            f"sectors {identity['log_sec']}/{identity['phy_sec']}, transport {identity['tran']}, "
            f"removable {identity['removable']}, hotplug {identity['hotplug']}",
            f"  layout      GPT {layout['disk_guid']}"]
    for part in layout["partitions"]:
        rows.append(f"              {part['number']}: {part['name']} start {part['start']} size {part['size']} sectors "
                    f"type {part['type']} guid {part['guid']}")
    rows += [f"  filesystems FAT32 {layout['esp']['label']} volume id {layout['esp']['volume_id']}; "
             f"ext4 {layout['root']['label']} uuid {layout['root']['uuid']}",
             f"  source      {plan['source']['path']} ({plan['source']['mount']['fstype']}), "
             f"inventory {plan['source']['inventory_sha256']}",
             f"  kernel      {plan['kernel']['name']}",
             "  microcode   " + ("AMD early microcode cpio" if plan["microcode"]["loaded"] else plan["microcode"]["reason"]),
             "  enrollment  " + ("input " + ", ".join(plan["enroll_input"]["files"]) if plan["enroll_input"]
                                 else "none: the installed system will not enroll an owner")]
    enroll = plan["enroll_input"]
    if enroll:
        rows.append(f"              owner {enroll['accepted']['owner']}, scope {enroll['accepted']['scope']}, "
                    f"hardware clock {enroll['accepted']['clock']}, key(s) " + ", ".join(enroll["accepted"]["fingerprints"]))
        if enroll["ignored"]:
            rows.append("              ignored, not copied (macOS metadata): " + ", ".join(enroll["ignored"]))
    kept = plan["state_directory"]
    if kept is None:
        rows.append("  state       not given to plan (--state DIR); the live system keeps /root, /tmp and /run in RAM, so "
                    "pass apply a --state on persistent storage if the journal must survive a power cut")
    elif kept["volatile"]:
        rows.append(f"  state       {kept['path']} is on VOLATILE storage ({kept['filesystem']}): the intent record and "
                    "journal are lost at power-off or reboot; after a power cut only the disk itself shows that a write "
                    "started, and a rerun of this plan is refused because the disk changed")
    else:
        rows.append(f"  state       {kept['path']} is on {kept['filesystem']}, which is not RAM")
    rows += ["  this will ERASE:"] + ["    " + line for line in plan["destroys"]]
    rows += [f"  disks in use by this system (never written): {', '.join(plan['target']['disks_in_use']) or 'none'}",
             f"Confirmation token: {confirmation_token(identity, plan['digest'])}"]
    return "\n".join(rows) + "\n"


# --- apply -----------------------------------------------------------------------------------

def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_atomic(path, data, mode=0o600):
    """Durable replace. mode None leaves permissions to the filesystem (FAT has none)."""
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode or 0o600)
    with os.fdopen(fd, "wb") as stream:
        if mode is not None:
            os.fchmod(stream.fileno(), mode)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    sync_dir(path.parent)


def load_plan(path):
    plan = load_json(path)
    if (plan.get("schema") != PLAN_SCHEMA or plan.get("digest") != plan_digest(plan)
            or plan.get("basis") != basis_digest(plan)):
        raise Refusal("not a TUP disk install plan, or it was edited after it was written")
    if plan["texts"] != texts_for(plan):
        raise Refusal("the plan's sfdisk script, fstab or grub.cfg differ from what its fields generate")
    return plan


def describe_difference(plan, identity, state):
    old = plan["target"]["identity"]
    changed = sorted(key for key in old if old[key] != identity.get(key))
    if plan["target"]["state"]["sfdisk_dump"] != state["sfdisk_dump"]:
        changed.append("partition table")
    if plan["target"]["state"]["wipefs"] != state["wipefs"] or plan["target"]["state"]["blkid"] != state["blkid"]:
        changed.append("filesystem signatures")
    if plan["target"]["state"]["sample"] != state["sample"]:
        changed.append("data in the first or last MiB")
    return ", ".join(changed) or "state"


def changed_paths(before, after):
    return sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))


def writes_target(name, stdin):
    """The commands that change the disk or a filesystem on it: the partitioning script and the formatters and copy.
    They get their own session (see Host.run)."""
    return name in ("mkfs.fat", "mkfs.ext4", "cp") or (name == "sfdisk" and stdin is not None)


class Run:
    """One apply: the journal, the command log, the mounts it made, and the checks after each step."""

    def __init__(self, host, plan, state, recheck):
        self.host, self.plan, self.state, self.recheck = host, plan, Path(state), recheck
        self.tools, self.mounted, self.step_name, self.commands = plan["tools"], [], "start", 0
        self.partitions = {}

    def journal(self, step, status="begin"):
        self.step_name = step
        line = json.dumps({"t": self.host.now(), "step": step, "status": status}) + "\n"
        fd = os.open(self.state / "PROGRESS.jsonl", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a") as stream:
            stream.write(line)
            stream.flush()
            os.fsync(stream.fileno())

    def tool(self, name, *args, stdin=None, timeout=3600):
        argv = [self.tools[name]["path"], *map(str, args)]
        code, out, err = self.host.run(argv, stdin, timeout, detached=writes_target(name, stdin))
        self.commands += 1
        entry = {"t": self.host.now(), "step": self.step_name, "argv": argv, "rc": code,
                 "stdout": short(out), "stderr": short(err)}
        with open(self.state / "COMMANDS.jsonl", "a") as stream:
            stream.write(json.dumps(entry) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        if code:
            raise Refusal(f"{' '.join(argv)} failed ({code}): {err.strip() or out.strip()}")
        return out

    def new_nodes(self, name):
        """Device nodes of the new partitions, from sysfs: never the disk name plus a digit."""
        host, scale = self.host, self.plan["layout"]["sector_size"] // 512
        base = host.realpath("/sys/class/block/" + name)
        wanted = {p["number"]: (p["start"] * scale, p["size"] * scale) for p in self.plan["layout"]["partitions"]}
        for _ in range(30):
            found = {}
            for entry in host.listdir(base):
                if host.exists(f"{base}/{entry}/partition"):
                    found[int(host.read(f"{base}/{entry}/partition"))] = (
                        entry, (int(host.read(f"{base}/{entry}/start")), int(host.read(f"{base}/{entry}/size"))))
            if set(found) == set(wanted) and all(host.exists("/dev/" + found[n][0]) for n in found):
                if {n: found[n][1] for n in found} != wanted:
                    raise Refusal(f"the kernel's partitions of {name} differ from the plan")
                self.partitions = {n: (f"{base}/{found[n][0]}", "/dev/" + found[n][0], wanted[n]) for n in found}
                for number in found:
                    self.confirm_node(number)
                return {n: "/dev/" + found[n][0] for n in found}
            host.sleep(1)
        raise Refusal(f"the kernel did not show exactly the two planned partitions of {name}")

    def confirm_node(self, number):
        """Immediately before a mkfs: the node is a block device whose number is the one sysfs gives this
        partition, sysfs reaches it from that number, and its start and size are still the planned ones."""
        host = self.host
        sysfs, node, geometry = self.partitions[number]
        try:
            wanted = host.read(sysfs + "/dev").strip()
            actual = (int(host.read(sysfs + "/start")), int(host.read(sysfs + "/size")))
            ok = (host.is_block(node) and host.block_devno(node) == wanted
                  and host.realpath("/sys/dev/block/" + wanted) == sysfs and actual == geometry)
        except (OSError, ValueError) as error:
            raise Refusal(f"cannot confirm {node} as partition {number} of the new table: {error}") from error
        if not ok:
            raise Refusal(f"{node} is not the block device {wanted} that sysfs lists as partition {number} of the "
                          "new table, or its extent changed; nothing was formatted")

    def read_table(self, disk):
        table = json.loads(self.tool("sfdisk", "--json", disk))["partitiontable"]
        layout = self.plan["layout"]
        got = [(p["start"], p["size"], p["type"].upper(), p["uuid"].lower(), p.get("name")) for p in table["partitions"]]
        want = [(p["start"], p["size"], p["type"].upper(), p["guid"], p["name"]) for p in layout["partitions"]]
        if (table["label"], table["id"].lower(), table["sectorsize"], got) != (
                "gpt", layout["disk_guid"], layout["sector_size"], want):
            raise Refusal("the partition table on disk is not the planned one")
        return table

    def check_filesystem(self, node, expected):
        values = dict(line.split("=", 1) for line in self.tool("blkid", "-p", "-o", "export", node).splitlines()
                      if "=" in line)
        if {key: values.get(key) for key in expected} != expected:
            raise Refusal(f"{node} does not carry the planned filesystem identity {expected}: got {values}")

    def mount(self, node, kind, options, name):
        point = self.state / "mnt" / name
        point.mkdir(parents=True, mode=0o700)
        self.mounted.append(point)  # recorded first: a signal after mount(2) but before mount returns must still unmount it
        self.tool("mount", "-t", kind, "-o", options, node, point)
        row = [r for r in mount_table(self.host) if r["mountpoint"] == str(point)]
        if len(row) != 1 or row[0]["majmin"] != self.host.block_devno(node) or row[0]["fstype"] != kind:
            raise Refusal(f"{point} is not the freshly formatted {node}")
        return point

    def unmount_all(self):
        """Every mount below the state directory, latest first, each attempted even if one fails or was never
        recorded. The mount table decides what is mounted; the points recorded before each mount call are the
        fallback if the table cannot be read."""
        problems, prefix = [], str(self.state) + "/"

        def below():
            return [r["mountpoint"] for r in mount_table(self.host) if r["mountpoint"].startswith(prefix)]
        try:
            points = list(reversed(below()))
        except OSError:
            points = [str(point) for point in reversed(self.mounted)]
        for point in points:
            try:
                self.tool("umount", point)
            except BaseException as error:
                problems.append(f"{point}: {error}")
        self.mounted = []
        left = below()
        if problems or left:
            raise Refusal("could not unmount everything this run mounted; unmount these by hand before anything "
                          "else: " + "; ".join(problems + left))


def refuse_existing_state(state):
    detail = ""
    if (state / "INTENT.json").is_file():
        try:
            record = json.loads((state / "INTENT.json").read_text())
            progress = state / "PROGRESS.jsonl"
            lines = progress.read_text().splitlines() if progress.is_file() else []
            detail = (f" It recorded intent for plan {record.get('plan_sha256')} on {record.get('target')}, started "
                      f"{record.get('started_at')}; last journal entry: {lines[-1] if lines else 'none'}.")
        except (OSError, ValueError, AttributeError):
            detail = " Its INTENT.json is unreadable."
    raise Refusal(f"state directory {state} already exists: apply never resumes and never reuses a state directory."
                  f"{detail} The disk may be half-written. Make a NEW plan with --allow-existing and a new --state.")


def recheck(host, plan, tools, confirm, state_parent):
    """Is this still exactly the planned disk, and still safe to write? Reads only, and fast: apply asks it once
    before it creates anything and once more immediately before the first write, with nothing slow in between.
    Returns the identity it just read."""
    target, source = plan["target"]["path"], plan["source"]["path"]
    check_device_path(host, target)
    identity, mounted = read_identity(host, tools, target)
    current = read_state(host, tools, identity)
    if (identity, current) != (plan["target"]["identity"], plan["target"]["state"]):
        raise Refusal(f"{target} differs from the plan ({describe_difference(plan, identity, current)}). A disk "
                      "that changed, or a previous attempt that wrote to it, needs a new plan with --allow-existing.")
    if host.block_devno(target) != identity["maj_min"]:
        raise Refusal(f"{target} is now device {host.block_devno(target)}, not the planned {identity['maj_min']}")
    refuse_windows(identity, current)  # the same refusal as plan, from this fresh read
    if not hmac.compare_digest(confirmation_token(identity, plan["digest"]).encode(), str(confirm).encode("utf-8", "replace")):
        raise Refusal("the confirmation token does not belong to this disk and plan; it is printed with the plan summary")
    use = disks_in_use(host, {"source": source})
    if sorted(use) != plan["target"]["disks_in_use"]:
        raise Refusal(f"the disks in use changed since the plan: {sorted(use)} instead of {plan['target']['disks_in_use']}")
    check_target(host, identity, mounted, disks_in_use(host, {"source": source, "state parent": str(state_parent)}))
    if check_source(host, source) != plan["source"]["mount"]:
        raise Refusal("the source mount changed since the plan")
    return identity


@contextlib.contextmanager
def ignoring_signals():
    """Cleanup must finish: a second SIGINT, SIGTERM or SIGHUP is dropped while mounts are released."""
    previous = {number: signal.signal(number, signal.SIG_IGN) for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    try:
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


def apply(host, plan_path, confirm, state):
    """Returns the receipt. Raises Refusal before any write unless the plan still matches everything."""
    plan = load_plan(plan_path)
    state, source, target = Path(state), plan["source"]["path"], plan["target"]["path"]
    if os.path.lexists(state):
        refuse_existing_state(state)
    if not state.is_absolute() or os.path.realpath(state.parent) != str(state.parent) or not state.parent.is_dir():
        raise Refusal("--state must be a new directory below an existing directory, without symbolic links")
    check_device_path(host, target)
    tools = measure_tools(host, plan["tools"])
    # Everything slow comes first: the disk is compared with the plan only after it.
    tree, summary, kernel, microcode = read_source(source)
    if ({k: plan["source"][k] for k in summary}, plan["kernel"], plan["microcode"]) != (summary, kernel, microcode):
        raise Refusal("the source tree, kernel or microcode changed since the plan")
    if read_enroll(plan["enroll_input"]["path"] if plan["enroll_input"] else None) != plan["enroll_input"]:
        raise Refusal("the enrollment input changed since the plan")
    if plan["installer"] != installer_digests():
        raise Refusal("the installer changed since the plan")
    storage = state_directory_facts(host, state)
    identity = recheck(host, plan, tools, confirm, state.parent)

    os.mkdir(state, 0o700)
    started = host.now()
    run = Run(host, plan, state, lambda: recheck(host, plan, tools, confirm, state.parent))
    write_atomic(state / "INTENT.json", json.dumps({
        "schema": INTENT_SCHEMA, "plan_sha256": plan["digest"], "target": target, "started_at": started,
        "identity": identity, "layout": plan["layout"], "state_directory": storage,
        "will_write": "partition table, FAT32 ESP, ext4 root"}, indent=2).encode())
    failure = None
    try:
        return deploy(run, plan, tree, identity, started, storage)
    except BaseException as error:
        failure = error
        try:
            write_atomic(state / "FAILED.json", json.dumps({"step": run.step_name, "error": str(error)}, indent=2).encode())
        except OSError:
            pass
        raise
    finally:
        with ignoring_signals():
            try:
                run.unmount_all()
            except BaseException as error:
                if failure is None:
                    raise
                print(f"WARNING: {error}", file=sys.stderr)


def deploy(run, plan, tree, identity, started, storage):
    host, state, layout = run.host, run.state, plan["layout"]
    disk, esp, root_uuid = identity["path"], layout["esp"], layout["root"]["uuid"]
    source, kernel = Path(plan["source"]["path"]), plan["kernel"]["name"]
    boot = state / "boot"
    boot.mkdir(mode=0o700)

    run.journal("prepare-boot-files")
    (boot / "grub.cfg").write_text(plan["texts"]["grub_cfg"])
    run.tool("grub-script-check", boot / "grub.cfg")
    run.tool("grub-mkstandalone", "-O", "x86_64-efi", "--fonts=", "--themes=", "--locales=",
             "-o", boot / "BOOTX64.EFI", f"boot/grub/grub.cfg={boot / 'grub.cfg'}")
    efi_image = (boot / "BOOTX64.EFI").read_bytes()
    if efi_image[:2] != b"MZ":
        raise Refusal("grub-mkstandalone did not produce an EFI executable")
    boot_files = {"EFI/BOOT/BOOTX64.EFI": efi_image, f"tup/{kernel}": (source / "boot" / kernel).read_bytes()}
    if digest(boot_files[f"tup/{kernel}"]) != plan["kernel"]["image_sha256"]:
        raise Refusal("the kernel image changed since the plan")
    if plan["microcode"]["loaded"]:
        blob = (source / MICROCODE).read_bytes()
        boot_files["tup/amd-ucode.img"] = microcode_cpio(blob)
        if parse_microcode_cpio(boot_files["tup/amd-ucode.img"])["kernel/x86/microcode/AuthenticAMD.bin"][1] != blob:
            raise Refusal("the microcode archive does not hold the container")

    run.journal("write-partition-table")
    run.recheck()  # the last thing before the first write: nothing slow, nothing else, between this and sfdisk
    run.tool("sfdisk", "--lock", "--wipe", "always", "--wipe-partitions", "always", disk,
             stdin=plan["texts"]["sfdisk_script"].encode())
    run.tool("udevadm", "settle", "--timeout=60")
    nodes = run.new_nodes(identity["kname"])
    table = run.read_table(disk)

    run.journal("format")
    run.confirm_node(1)
    run.tool("mkfs.fat", "-F", "32", "-i", esp["volume_id"], "-n", esp["label"], nodes[1])
    run.confirm_node(2)
    run.tool("mkfs.ext4", "-F", "-q", "-U", root_uuid, "-L", layout["root"]["label"], nodes[2])
    run.tool("udevadm", "settle", "--timeout=60")
    identities = {1: {"TYPE": "vfat", "UUID": esp["uuid"], "LABEL": esp["label"]},
                  2: {"TYPE": "ext4", "UUID": root_uuid, "LABEL": layout["root"]["label"]}}
    for number, expected in identities.items():
        run.check_filesystem(nodes[number], expected)

    run.journal("mount")
    root = run.mount(nodes[2], "ext4", "rw", "root")
    efi = run.mount(nodes[1], "vfat", "rw,umask=0077,codepage=437,iocharset=iso8859-1", "esp")

    run.journal("copy-root")
    run.tool("cp", "-a", "--one-file-system", f"{source}/.", f"{root}/", timeout=None)
    run.journal("verify-copy")
    copied = inventory(root)
    if changed_paths(tree, copied) != ["lost+found"]:
        raise Refusal("the copy differs from the source inventory at: " + ", ".join(changed_paths(tree, copied)[:20]))

    run.journal("configure-root")
    # Every path the installer itself touches is allowed to differ from the source whether or not it existed there:
    # a directory that already exists changes its mtime when a file is created in it.
    allowed = {"lost+found", "etc", "etc/fstab", "boot", "boot/efi"}
    write_atomic(root / "etc/fstab", plan["texts"]["fstab"].encode(), 0o644)
    if not (root / "boot/efi").is_dir():
        (root / "boot/efi").mkdir(mode=0o755)
    for relative in ("etc/machine-id", "var/lib/dbus/machine-id"):
        if os.path.lexists(root / relative) and (root / relative).read_bytes().strip():
            raise Refusal(f"the copied root carries a machine identity: {relative}")
    if (root / "etc/ssh").is_dir() and list((root / "etc/ssh").glob("ssh_host_*_key")):
        raise Refusal("the copied root carries SSH host keys")
    if plan["enroll_input"]:
        allowed |= {"etc/tup", ENROLL_TARGET}
        for directory in ("etc/tup", ENROLL_TARGET):
            path = root / directory
            if path.is_symlink() or (os.path.lexists(path) and not path.is_dir()):
                raise Refusal(f"/{directory} in the copied root is not a real directory")
            if not path.exists():
                path.mkdir()
                os.chmod(path, 0o755)
        os.chmod(root / ENROLL_TARGET, 0o700)  # enroll.py reads owner keys from here
        expected = {"etc/tup": None, ENROLL_TARGET: 0o700}
        for name, sha in plan["enroll_input"]["files"].items():
            data = Path(plan["enroll_input"]["path"], name).read_bytes()
            if digest(data) != sha:
                raise Refusal(f"enrollment input {name} changed during the install")
            write_atomic(root / ENROLL_TARGET / name, data, 0o600)
            allowed.add(f"{ENROLL_TARGET}/{name}")
            expected[f"{ENROLL_TARGET}/{name}"] = 0o600
        for relative, mode in expected.items():  # owner and mode, read back; root:root because main() requires root
            info = os.lstat(root / relative)
            if (info.st_uid, info.st_gid) != (os.geteuid(), os.getegid()) or (
                    mode is None and info.st_mode & 0o022) or (mode is not None and stat.S_IMODE(info.st_mode) != mode):
                raise Refusal(f"/{relative} has owner {info.st_uid}:{info.st_gid} mode {stat.S_IMODE(info.st_mode):o}, "
                              "not the planned root-owned mode")

    run.journal("install-boot-files")
    for relative, data in boot_files.items():
        (efi / relative).parent.mkdir(parents=True, exist_ok=True)
        write_atomic(efi / relative, data, None)

    run.journal("verify-final")
    final = inventory(root)
    if set(changed_paths(tree, final)) - allowed:
        raise Refusal("the deployed root differs from the source beyond the planned changes at: "
                      + ", ".join(sorted(set(changed_paths(tree, final)) - allowed)[:20]))
    if (root / "etc/fstab").read_bytes() != plan["texts"]["fstab"].encode():
        raise Refusal("fstab on disk is not the planned fstab")
    for relative, data in boot_files.items():
        if (efi / relative).read_bytes() != data:
            raise Refusal(f"{relative} on the ESP differs from what was written")
    run.tool("sync")
    run.unmount_all()

    run.journal("fsck")
    run.tool("e2fsck", "-f", "-n", nodes[2])
    run.tool("fsck.fat", "-n", nodes[1])
    for number, expected in identities.items():
        run.check_filesystem(nodes[number], expected)
    if run.read_table(disk) != table:
        raise Refusal("the partition table changed during the install")
    run.tool("sync")

    run.journal("receipt")
    receipt = {
        "schema": RECEIPT_SCHEMA, "status": "installed-unbooted", "plan_sha256": plan["digest"],
        "target": {"path": disk, "serial": identity["serial"], "wwn": identity["wwn"], "model": identity["model"],
                   "size_bytes": identity["size_bytes"], "snapshot_sha256": plan["target"]["snapshot_sha256"]},
        "created": {"disk_guid": layout["disk_guid"], "esp_uuid": esp["uuid"], "esp_volume_id": esp["volume_id"],
                    "root_uuid": root_uuid, "partitions": [
                        {"number": p["number"], "node": nodes[p["number"]], "guid": p["guid"], "start": p["start"],
                         "size": p["size"]} for p in layout["partitions"]]},
        "source_inventory_sha256": plan["source"]["inventory_sha256"],
        "copy_inventory_sha256": digest(canonical(copied)), "deployed_inventory_sha256": digest(canonical(final)),
        "planned_changes": sorted(allowed),
        "state_directory": storage,
        "bootloader": {relative: digest(data) for relative, data in boot_files.items()}
                      | {"grub.cfg": digest(plan["texts"]["grub_cfg"].encode())},
        "microcode": plan["microcode"], "tools": plan["tools"], "commands_run": run.commands,
        "started_at": started, "finished_at": host.now(), "boot_tested": False, "release_eligible": False}
    write_atomic(state / "RECEIPT.json", json.dumps(receipt, indent=2, sort_keys=True).encode())
    run.journal("done", "complete")
    return receipt


def terminate(signum, frame):
    raise Interrupted(f"signal {signum}")


def main(argv=None, host=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="action", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--target", required=True)
    plan.add_argument("--source", required=True)
    plan.add_argument("--output", type=Path, required=True)
    plan.add_argument("--esp-mib", type=int, default=512)
    plan.add_argument("--enroll-input", type=Path)
    plan.add_argument("--allow-existing", action="store_true",
                      help="plan over a disk that holds data; never overrides the refusal of a Windows-looking disk")
    plan.add_argument("--state", type=Path, help="the --state apply will get; the summary says whether it is in RAM")
    apply_parser = sub.add_parser("apply")
    apply_parser.add_argument("--plan", type=Path, required=True)
    apply_parser.add_argument("--confirm", required=True)
    apply_parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args(argv)
    host = host or Host()
    try:
        check_platform()
        if os.geteuid() != 0:
            raise Refusal("run as root")
        if args.action == "plan":
            made = make_plan(host, target=args.target, source=args.source, esp_mib=args.esp_mib,
                             enroll_input=args.enroll_input, allow_existing=args.allow_existing,
                             state=args.state)
            fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as stream:
                json.dump(made, stream, indent=2, sort_keys=True)
                stream.write("\n")
            print(summary_text(made), end="")
        else:
            previous = {number: signal.signal(number, terminate) for number in (signal.SIGTERM, signal.SIGHUP)}
            try:
                receipt = apply(host, args.plan, args.confirm, args.state)
            finally:
                for number, handler in previous.items():
                    signal.signal(number, handler)
            print(f"installed {receipt['target']['path']}: receipt {args.state / 'RECEIPT.json'}")
    except Refusal as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"FAILED: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt as error:
        print(f"INTERRUPTED ({error or 'SIGINT'}): mounts were released, the disk may be half-written; "
              "make a new plan with --allow-existing", file=sys.stderr)
        return 143 if isinstance(error, Interrupted) else 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
