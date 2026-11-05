"""Whole-disk installer tests. Every external command is a recorded fake; /sys and /proc are dictionaries.

The real-tool tests at the end run sfdisk, mkfs and cpio only on regular files in a temporary directory.
Run: python -m unittest discover -s tup/tests -p 'test_install_disk.py' -v
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest

from tup.boot import inputs
from tup.boot.inputs import Refusal
from tup.install import disk

POSIX = os.name == "posix" and hasattr(os, "geteuid")
SOURCE_DEV = "7:1"
RELEASE = "6.18.60-tup-test"
MICROCODE = b"DMA\0" + bytes(range(60))
SERIALS = {"nvme0n1": "S5GXNX0R123456A", "sda": "WD-WX11A2345678", "vda": "virtio-0001", "sdc": "USB0001", "sdb": "VENTOY0001"}
PCI = {"nvme0n1": "pci0000:00/0000:00:01.1/0000:01:00.0/nvme/nvme0", "sda": "pci0000:00/0000:00:17.0/ata1/host0/target0:0:0/0:0:0:0",
       "vda": "pci0000:00/0000:00:04.0/virtio1", "sdb": "pci0000:00/0000:00:14.0/usb1/1-1/1-1:1.0/host6/target6:0:0/6:0:0:0",
       "sdc": "pci0000:00/0000:00:14.0/usb1/1-2/1-2:1.0/host7/target7:0:0/7:0:0:0"}


def part_name(disk_name, number):
    return f"{disk_name}p{number}" if disk_name[-1].isdigit() else f"{disk_name}{number}"


def node_json(name, majmin, size, *, kind="disk", model=None, serial=None, wwn=None, tran=None, ro=False, rm=False,
              hotplug=False, log=512, phy=512, pttype=None, ptuuid=None, fstype=None, children=(), mounts=(None,),
              uuid=None, label=None, parttype=None, partuuid=None, partlabel=None):
    return {"name": name, "kname": name, "path": "/dev/" + name, "maj:min": majmin, "type": kind, "model": model,
            "serial": serial, "wwn": wwn, "size": size, "log-sec": log, "phy-sec": phy, "tran": tran, "rm": rm,
            "hotplug": hotplug, "ro": ro, "pttype": pttype, "ptuuid": ptuuid, "fstype": fstype, "uuid": uuid,
            "partuuid": partuuid, "parttype": parttype, "partlabel": partlabel, "label": label,
            "mountpoints": list(mounts), "vendor": "ATA     " if tran == "sata" else None, "rev": "1.0",
            **({"children": list(children)} if children else {})}


class FakeHost(disk.Host):
    """The machine: sysfs, mountinfo, device nodes and a dispatcher for every tool."""

    def __init__(self, source=None, state_parent=None):
        self.commands, self.files, self.dirs, self.links = [], {}, {}, {}
        self.devnos, self.nodes, self.dev_links = {}, set(), {}
        self.lsblk, self.dump, self.signatures, self.blkid_out = {}, {}, {}, {}
        self.mounts, self.swaps, self.written, self.counter, self.hook = [], [], [], 0, None
        self.table_json = {}
        self.source, self.state_parent = source, state_parent
        self.fail, self.sfdisk_error = None, {}
        self.add_disk("sdb", "8:16", 64 << 30)  # the Ventoy stick that booted this system
        self.files["/sys/class/block/sdb"] = None
        for number, (start, size) in enumerate(((2048, 100 << 11), (2048 + (100 << 11), 32768)), 1):
            self.add_partition("sdb", number, start, size)
        self.add_loop("loop0", "7:0", "/run/initramfs/tup-ventoy/media/tup.iso")
        self.add_loop("loop1", "7:1", "/run/initramfs/live/LiveOS/squashfs.img")
        self.devnos.update({"/run/initramfs/tup-ventoy/media/tup.iso": "8:17", "/run/initramfs/live/LiveOS/squashfs.img": "7:0",
                            "/run/rootfsbase": "7:1", "/run/overlayfs": "0:25", "/run/ovlwork": "0:25"})
        self.mount_rows = [
            "20 1 0:40 / / rw - overlay LiveOS_rootfs rw,lowerdir=/run/rootfsbase,upperdir=/run/overlayfs,workdir=/run/ovlwork",
            "21 20 0:25 / /run rw - tmpfs tmpfs rw,mode=755",
            "22 20 7:0 / /run/initramfs/live ro - iso9660 /dev/loop0 ro",
            "23 20 7:1 / /run/rootfsbase ro - squashfs /dev/loop1 ro",
            "24 20 8:17 / /run/initramfs/tup-ventoy/media ro - exfat /dev/sdb1 ro"]
        if source:
            self.devnos[str(source)] = SOURCE_DEV
            self.mount_rows.append(f"25 20 {SOURCE_DEV} / {source} ro - squashfs /dev/loop1 ro")
        if state_parent:
            self.devnos[str(state_parent)] = "0:25"

    # --- sysfs construction
    def add_disk(self, name, majmin, size, bus=None):
        base = f"/sys/devices/{PCI.get(name, 'virtual/x/' + name)}/block/{name}"
        self.links[f"/sys/class/block/{name}"] = base
        self.links[f"/sys/dev/block/{majmin}"] = base
        self.dirs[base] = []
        self.files[base + "/ro"] = "0\n"
        self.devnos["/dev/" + name] = majmin
        self.nodes.add("/dev/" + name)

    def add_partition(self, disk_name, number, start, size):
        name = part_name(disk_name, number)
        base = self.links[f"/sys/class/block/{disk_name}"]
        major = int(self.devnos["/dev/" + disk_name].split(":")[0])
        minor = int(self.devnos["/dev/" + disk_name].split(":")[1]) + number
        path = f"{base}/{name}"
        self.dirs[base].append(name)
        self.dirs[path] = []
        self.files.update({path + "/partition": f"{number}\n", path + "/start": f"{start}\n", path + "/size": f"{size}\n"})
        self.links[f"/sys/class/block/{name}"] = path
        self.links[f"/sys/dev/block/{major}:{minor}"] = path
        self.devnos["/dev/" + name] = f"{major}:{minor}"
        self.nodes.add("/dev/" + name)
        return name

    def add_loop(self, name, majmin, backing):
        base = f"/sys/devices/virtual/block/{name}"
        self.links[f"/sys/class/block/{name}"] = base
        self.links[f"/sys/dev/block/{majmin}"] = base
        self.dirs[base] = ["loop"]
        self.dirs[base + "/loop"] = []
        self.files[base + "/loop/backing_file"] = backing + "\n"
        self.files[base + "/ro"] = "1\n"
        self.nodes.add("/dev/" + name)
        self.devnos["/dev/" + name] = majmin

    def add_target(self, name, majmin, size, **kwargs):
        self.add_disk(name, majmin, size)
        self.lsblk["/dev/" + name] = node_json(name, majmin, size, serial=SERIALS.get(name), **kwargs)
        self.dump["/dev/" + name] = None
        self.signatures["/dev/" + name] = []
        self.blkid_out["/dev/" + name] = {}

    # --- Host interface
    def realpath(self, path):
        path = str(path)
        return self.links.get(path) or self.dev_links.get(path) or path

    def exists(self, path):
        path = self.realpath(str(path))
        return path in self.files or path in self.dirs or path in self.links.values() or path in self.nodes

    def listdir(self, path):
        return list(self.dirs[self.realpath(str(path))])

    def read(self, path):
        path = str(path)
        if path == "/proc/self/mountinfo":
            return "\n".join(self.mount_rows) + "\n"
        if path == "/proc/swaps":
            return "Filename Type Size Used Priority\n" + "".join(f"{s} partition 1024 0 -2\n" for s in self.swaps)
        return self.files[self.realpath(path)]

    def is_block(self, path):
        return str(path) in self.nodes

    def fs_devno(self, path):
        try:
            return self.devnos[str(path)]
        except KeyError:
            raise FileNotFoundError(str(path)) from None

    def block_devno(self, path):
        return self.devnos[str(path)]

    def which(self, name):
        return "/usr/sbin/" + name

    def sha256(self, path):
        return hashlib.sha256(path.encode()).hexdigest()

    def now(self):
        self.counter += 1
        return f"2026-11-05T12:00:{self.counter % 60:02d}Z"

    def sleep(self, seconds):
        pass

    def random(self, count):
        self.counter += 1
        return hashlib.sha256(b"seed%d" % self.counter).digest()[:count] if count <= 32 else b""

    # --- tools
    def run(self, argv, stdin=None, timeout=900):
        argv = [str(a) for a in argv]
        self.commands.append((argv, stdin))
        if self.hook:
            self.hook(self, argv)
        name, args = Path(argv[0]).name, argv[1:]
        if args in (["--version"], ["--help"], ["-V"]):
            return 0, f"{name} 1.0 (fixture)\n", ""
        return getattr(self, "tool_" + name.replace(".", "_").replace("-", "_"))(args, stdin)

    def tool_lsblk(self, args, stdin):
        return 0, json.dumps({"blockdevices": [self.lsblk[args[-1]]]}), ""

    def tool_sfdisk(self, args, stdin):
        node = args[-1]
        if "--dump" in args and node in self.sfdisk_error:
            return self.sfdisk_error[node]
        if "--dump" in args:
            if self.dump.get(node) is None:
                return 1, "", f"sfdisk: {node}: does not contain a recognized partition table\n"
            return 0, self.dump[node], ""
        if "--json" in args:
            return 0, json.dumps({"partitiontable": self.table_json[node]}), ""
        script = stdin.decode()
        self.written.append((node, script))
        import re
        header = dict(line.split(": ", 1) for line in script.splitlines() if ": " in line)
        parts = [m.groups() for m in re.finditer(r'start=(\d+), size=(\d+), type=(\S+), uuid=(\S+), name="([^"]+)"', script)]
        name = node[5:]
        self.table_json[node] = {"label": header["label"], "id": header["label-id"].upper(), "device": node,
                                 "unit": "sectors", "sectorsize": int(header["sector-size"]), "partitions": [
                                     {"node": node + str(i), "start": int(a), "size": int(b), "type": c.upper(),
                                      "uuid": d.upper(), "name": e} for i, (a, b, c, d, e) in enumerate(parts, 1)]}
        scale = int(header["sector-size"]) // 512
        for i, (a, b, c, d, e) in enumerate(parts, 1):
            self.add_partition(name, i, int(a) * scale, int(b) * scale)
            self.blkid_out["/dev/" + part_name(name, i)] = {}
        self.dump[node] = "label: gpt\n"
        return 0, "", ""

    def tool_blkid(self, args, stdin):
        values = self.blkid_out.get(args[-1], {})
        return (0, "".join(f"{k}={v}\n" for k, v in values.items()), "") if values else (2, "", "")

    def tool_wipefs(self, args, stdin):
        return 0, json.dumps({"signatures": [dict(device=args[-1], **s) for s in self.signatures.get(args[-1], [])]}), ""

    def tool_udevadm(self, args, stdin):
        return 0, "", ""

    tool_sync = tool_udevadm
    tool_e2fsck = tool_udevadm
    tool_fsck_fat = tool_udevadm
    tool_grub_script_check = tool_udevadm

    def tool_mkfs_fat(self, args, stdin):
        volume = args[args.index("-i") + 1]
        self.blkid_out[args[-1]] = {"TYPE": "vfat", "UUID": f"{volume[:4]}-{volume[4:]}", "LABEL": args[args.index("-n") + 1]}
        return 0, "", ""

    def tool_mkfs_ext4(self, args, stdin):
        self.blkid_out[args[-1]] = {"TYPE": "ext4", "UUID": args[args.index("-U") + 1], "LABEL": args[args.index("-L") + 1]}
        return 0, "", ""

    def tool_mount(self, args, stdin):
        node, point, kind = args[-2], args[-1], args[args.index("-t") + 1]
        self.mount_rows.append(f"90 20 {self.devnos[node]} / {point} rw - {kind} {node} rw")
        if kind == "ext4":
            os.makedirs(os.path.join(point, "lost+found"), mode=0o700, exist_ok=True)
        return 0, "", ""

    def tool_umount(self, args, stdin):
        self.mount_rows = [row for row in self.mount_rows if f" {args[-1]} " not in row]
        return 0, "", ""

    def tool_cp(self, args, stdin):
        done = subprocess.run(["cp", *args], capture_output=True, text=True)
        return done.returncode, done.stdout, done.stderr

    def tool_grub_mkstandalone(self, args, stdin):
        Path(args[args.index("-o") + 1]).write_bytes(b"MZ fixture efi application")
        return 0, "", ""

    # --- helpers for assertions
    def mutating(self):
        return [argv for argv, _ in self.commands if not disk.read_only_command(argv)]


def build_source(base):
    """A root that passes check_offline_root and check_kernel, with the AMD microcode container."""
    root = Path(base) / "lower"
    elf = b"\x7fELF\x02\x01" + bytes(12) + b"\x3e\x00"
    files = {"usr/bin/bash": elf, "usr/lib/systemd/systemd": elf, "usr/sbin/dmsetup": elf,
             "etc/shadow": b"root:!:0:0:99999:7:::\n", "etc/os-release": b'ID=tup\nNAME="TUP"\nVERSION_ID="fixture"\n',
             "etc/machine-id": b"", "etc/fstab": b"# live root: nothing to mount\n",
             "boot/config-" + RELEASE: "".join(f"CONFIG_{n}=y\n" for n in inputs.BUILTIN + inputs.AVAILABLE).encode(),
             disk.MICROCODE: MICROCODE, "etc/hostname": b"tup\n"}
    image = bytearray(1024)
    image[0x202:0x206] = b"HdrS"
    struct.pack_into("<H", image, 0x206, 0x20C)
    struct.pack_into("<H", image, 0x236, 1)
    struct.pack_into("<H", image, 0x20E, 0x80)
    text = (RELEASE + " fixture\0").encode()
    image[0x280:0x280 + len(text)] = text
    files["boot/vmlinuz-" + RELEASE] = bytes(image)
    for name in ("modules.dep", "modules.alias", "modules.builtin", "modules.builtin.modinfo", "modules.order"):
        files["usr/lib/modules/" + RELEASE + "/" + name] = b""
    for relative, raw in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    os.chmod(root / "etc/shadow", 0o640) if POSIX else None
    return root


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = build_source(self.base)
        self.host = FakeHost(self.source, self.base)
        self.host.add_target("nvme0n1", "259:0", 64 << 30, model="Fixture NVMe", tran="nvme", wwn="eui.0025385b71234567")
        self.host.add_target("sda", "8:0", 64 << 30, model="Fixture SATA", tran="sata", wwn="0x5002538d41234567")
        self.host.add_target("vda", "254:0", 64 << 30, model="", tran="virtio")
        self.host.add_target("sdc", "8:32", 64 << 30, model="Fixture USB", tran="usb", rm=True, hotplug=True)

    def plan(self, target="/dev/nvme0n1", **kwargs):
        return disk.make_plan(self.host, target=target, source=str(self.source), **kwargs)

    def assert_read_only(self):
        self.assertEqual(self.host.mutating(), [])
        for argv, stdin in self.host.commands:
            self.assertIsNone(stdin)

    def refused(self, pattern, target="/dev/nvme0n1", **kwargs):
        with self.assertRaisesRegex(Refusal, pattern):
            self.plan(target, **kwargs)
        self.assert_read_only()

    def windows_ntfs(self, name):
        """What Windows leaves behind: a GPT with an ESP, MSR and an NTFS partition."""
        node = "/dev/" + name
        self.host.lsblk[node]["children"] = [
            node_json(part_name(name, 1), "8:1", 100 << 20, kind="part", fstype="vfat", partlabel="EFI system partition"),
            node_json(part_name(name, 2), "8:2", 60 << 30, kind="part", fstype="ntfs", partlabel="Basic data partition",
                      label="Windows")]
        self.host.lsblk[node]["pttype"] = "gpt"
        self.host.dump[node] = (f"label: gpt\nlabel-id: 1111\ndevice: {node}\nunit: sectors\n\n"
                                f"{node}1 : start=2048, size=204800, type=C12A7328\n{node}2 : start=206848, size=125000000, type=EBD0A0A2\n")
        self.host.signatures[node] = [{"offset": "0x200", "type": "gpt", "uuid": None, "label": None}]
        self.host.signatures[node + "p2" if name[-1].isdigit() else node + "2"] = [
            {"offset": "0x3", "type": "ntfs", "uuid": "AA", "label": "Windows"}]


class PlanTests(Base):
    def test_blank_nvme_plan_is_complete_and_wrote_nothing(self):
        plan = self.plan()
        self.assert_read_only()
        target, layout = plan["target"], plan["layout"]
        self.assertEqual((target["identity"]["serial"], target["identity"]["wwn"], target["identity"]["tran"]),
                         ("S5GXNX0R123456A", "eui.0025385b71234567", "nvme"))
        self.assertEqual(target["disks_in_use"], ["sdb"])
        self.assertEqual(plan["destroys"], ["nothing: the disk has no partition table and no signature"])
        self.assertEqual(target["snapshot_sha256"], inputs.digest(inputs.canonical(
            {"identity": target["identity"], "state": target["state"]})))
        esp, root = layout["partitions"]
        self.assertEqual((esp["start"], esp["size"], esp["type"]), (2048, 512 * 2048, disk.ESP_TYPE))
        self.assertEqual((root["start"], root["type"]), (2048 + 512 * 2048, disk.ROOT_TYPE))
        # 64 GiB = 134217728 sectors; backup GPT takes the last 33; root ends on a 1 MiB boundary.
        self.assertEqual(root["start"] + root["size"], (134217728 - 34 + 1) // 2048 * 2048)
        for value in (layout["disk_guid"], esp["guid"], root["guid"], layout["root"]["uuid"]):
            self.assertRegex(value, disk.GUID)
        self.assertEqual(len({layout["disk_guid"], esp["guid"], root["guid"], layout["root"]["uuid"]}), 4)
        self.assertRegex(layout["esp"]["volume_id"], r"^[0-9A-F]{8}$")
        self.assertEqual(layout["esp"]["uuid"], layout["esp"]["volume_id"][:4] + "-" + layout["esp"]["volume_id"][4:])
        self.assertEqual(plan["digest"], disk.plan_digest(plan))
        self.assertEqual(plan["texts"], disk.texts_for(plan))
        summary = disk.summary_text(plan)
        self.assertTrue(summary.endswith(f"Confirmation token: S5GXNX0R123456A-{plan['digest'][:8]}\n"))
        self.assertNotIn("S5GXNX0R123456A-", json.dumps(plan))

    def test_generated_bytes(self):
        plan = self.plan()
        layout, texts = plan["layout"], plan["texts"]
        esp, root = layout["partitions"]
        self.assertEqual(texts["sfdisk_script"], (
            f"label: gpt\nlabel-id: {layout['disk_guid']}\nunit: sectors\nsector-size: 512\n\n"
            f'start=2048, size=1048576, type=C12A7328-F81F-11D2-BA4B-00A0C93EC93B, uuid={esp["guid"]}, name="TUP-ESP"\n'
            f'start=1050624, size={root["size"]}, type=4F68BCE3-E8CD-4DB1-96E7-FBCAF984B709, uuid={root["guid"]}, name="TUP-ROOT"\n'))
        self.assertEqual(texts["fstab"], (
            f"# /etc/fstab, written by tup/install/disk.py for plan {plan['basis'][:12]}\n"
            "# file system   mount-point  type  options  dump  fsck\n"
            f"UUID={layout['root']['uuid']}  /  ext4  defaults,errors=remount-ro  0  1\n"
            f"UUID={layout['esp']['uuid']}  /boot/efi  vfat  "
            "umask=0077,rw,relatime,codepage=437,iocharset=iso8859-1,nofail,x-systemd.device-timeout=10s  0  2\n"))
        self.assertEqual(texts["grub_cfg"], (
            f"# TUP boot menu, written by tup/install/disk.py for plan {plan['basis'][:12]}\n"
            "set timeout=3\nset default=tup\ninsmod part_gpt\ninsmod fat\ninsmod search\ninsmod linux\n"
            f"search --no-floppy --fs-uuid --set=root {layout['esp']['uuid'].lower()}\n"
            "menuentry 'TUP' --id tup {\n"
            f"    linux /tup/vmlinuz-{RELEASE} root=PARTUUID={root['guid']} rootwait ro console=tty0 console=ttyS0,115200n8\n"
            "    initrd /tup/amd-ucode.img\n}\n"
            "menuentry 'TUP rescue target' --id tup-rescue {\n"
            f"    linux /tup/vmlinuz-{RELEASE} root=PARTUUID={root['guid']} rootwait ro console=tty0 console=ttyS0,115200n8"
            " systemd.unit=rescue.target\n    initrd /tup/amd-ucode.img\n}\n"))
        for forbidden in ("serial", "terminal_input", "terminal_output", "usb_keyboard"):
            self.assertNotIn(forbidden, texts["grub_cfg"])

    def test_every_transport_plans_without_writes(self):
        for name, tran in (("nvme0n1", "nvme"), ("sda", "sata"), ("vda", "virtio"), ("sdc", "usb")):
            with self.subTest(name=name):
                self.host.commands.clear()
                if name == "vda":
                    self.host.lsblk["/dev/vda"]["serial"] = "virtio-0001"
                plan = disk.make_plan(self.host, target="/dev/" + name, source=str(self.source))
                self.assertEqual(plan["target"]["identity"]["tran"], tran)
                self.assert_read_only()

    def test_4096_byte_sectors_are_laid_out_in_sectors(self):
        self.host.lsblk["/dev/nvme0n1"].update({"log-sec": 4096, "phy-sec": 4096})
        layout = self.plan()["layout"]
        self.assertEqual(layout["sector_size"], 4096)
        esp, root = layout["partitions"]
        self.assertEqual((esp["start"], esp["size"]), (256, 512 * 256))
        self.assertEqual((root["start"] + root["size"]) % 256, 0)
        self.assertLessEqual((root["start"] + root["size"]) * 4096, (64 << 30) - 4096 * 6)

    def test_refuses_what_is_not_a_whole_disk(self):
        self.host.nodes.update({"/dev/nvme0n1p1", "/dev/loop5", "/dev/dm-0", "/dev/md0", "/dev/zram0", "/dev/sr0"})
        for name, kind in (("nvme0n1p1", "part"), ("loop5", "loop"), ("dm-0", "lvm"), ("md0", "raid1"),
                           ("zram0", "disk"), ("sr0", "rom")):
            with self.subTest(name=name):
                self.host.add_disk(name, "9:9", 1 << 40)
                self.host.lsblk["/dev/" + name] = node_json(name, "9:9", 1 << 40, kind=kind, serial="X")
                self.host.dump["/dev/" + name] = None
                self.host.commands.clear()
                if name == "nvme0n1p1":
                    self.host.files[self.host.links["/sys/class/block/nvme0n1p1"] + "/partition"] = "1\n"
                self.refused("not a whole physical disk", "/dev/" + name)

    def test_refuses_read_only_and_symlinked_and_unknown_targets(self):
        self.host.lsblk["/dev/nvme0n1"]["ro"] = True
        self.refused("read-only")
        self.host.lsblk["/dev/nvme0n1"]["ro"] = False
        self.host.files[self.host.links["/sys/class/block/nvme0n1"] + "/ro"] = "1\n"
        self.refused("read-only")
        self.host.files[self.host.links["/sys/class/block/nvme0n1"] + "/ro"] = "0\n"
        self.host.dev_links["/dev/disk/by-id/nvme-Fixture_S5GXNX0R123456A"] = "/dev/nvme0n1"
        self.refused("symbolic link or by-id", "/dev/disk/by-id/nvme-Fixture_S5GXNX0R123456A")
        self.refused("symbolic link or by-id", "nvme0n1")
        self.refused("not a block device", "/dev/nvme9n1")
        self.refused("--esp-mib", esp_mib=8)

    def test_refuses_the_boot_medium_the_running_system_and_the_iso_file(self):
        self.host.lsblk["/dev/sdb"] = node_json("sdb", "8:16", 64 << 30, serial="VENTOY0001", tran="usb", rm=True)
        self.host.dump["/dev/sdb"], self.host.signatures["/dev/sdb"], self.host.blkid_out["/dev/sdb"] = None, [], {}
        with self.assertRaisesRegex(Refusal, r"in use by this system: .*tup-ventoy/media"):
            self.plan("/dev/sdb", allow_existing=True)
        self.assert_read_only()
        # An installed system whose root lives on sda2 protects sda, and the squashfs chain protects the stick.
        self.host.mount_rows.append("30 20 8:2 / /var rw - ext4 /dev/sda2 rw")
        self.host.add_partition("sda", 2, 4096, 4096)
        self.refused(r"in use by this system: ext4 mounted at /var", "/dev/sda", allow_existing=True)
        self.assertEqual(self.plan()["target"]["disks_in_use"], ["sda", "sdb"])

    def test_resolves_loop_chains_device_mapper_and_swap_to_disks(self):
        host = self.host
        self.assertEqual(disk.disks_behind(host, "loop1", set()), {"sdb"})
        host.add_disk("dm-0", "253:0", 1 << 30)
        base = host.links["/sys/class/block/dm-0"]
        host.dirs[base] += ["slaves"]
        host.dirs[base + "/slaves"] = ["nvme0n1p1"]
        host.add_partition("nvme0n1", 1, 2048, 2048)
        self.assertEqual(disk.disks_behind(host, "dm-0", set()), {"nvme0n1"})
        host.swaps.append("/dev/nvme0n1p1")
        self.refused("swap area /dev/nvme0n1p1")
        host.swaps.clear()
        host.devnos["/swapfile"] = "259:1"
        host.swaps.append("/swapfile")
        self.refused("swap area /swapfile")

    def test_refuses_mounted_partitions_holders_and_unresolvable_backing_files(self):
        node = self.host.lsblk["/dev/nvme0n1"]
        node["children"] = [node_json("nvme0n1p1", "259:1", 1 << 20, kind="part", mounts=("/mnt/data",))]
        self.refused("mounted partitions: /mnt/data")
        node.pop("children")
        base = self.host.links["/sys/class/block/nvme0n1"]
        self.host.dirs[base + "/holders"] = ["dm-3"]
        self.refused("held by device-mapper or md: nvme0n1 held by dm-3")
        del self.host.dirs[base + "/holders"]
        del self.host.devnos["/run/initramfs/live/LiveOS/squashfs.img"]
        self.refused("cannot resolve the backing file")

    def test_refuses_a_source_that_is_not_the_read_only_lower_root(self):
        self.host.mount_rows[:] = [row for row in self.host.mount_rows if f" {self.source} " not in row]
        self.refused("not a read-only erofs/squashfs mount")
        self.host.mount_rows.append(f"25 20 {SOURCE_DEV} / {self.source} rw - squashfs /dev/loop1 rw")
        self.refused("not a read-only erofs/squashfs mount")
        with self.assertRaisesRegex(Refusal, "absolute path without symbolic links"):
            disk.make_plan(self.host, target="/dev/nvme0n1", source="relative/path")

    def test_refuses_a_source_that_carries_secrets_or_enrollment(self):
        (self.source / "etc/ssh").mkdir()
        (self.source / "etc/ssh/ssh_host_ed25519_key").write_text("x")
        self.refused("private SSH host keys")
        (self.source / "etc/ssh/ssh_host_ed25519_key").unlink()
        (self.source / "etc/machine-id").write_text("0123456789abcdef0123456789abcdef\n")
        self.refused("cloned machine identity")
        (self.source / "etc/machine-id").write_text("")
        (self.source / "etc/tup").mkdir()
        (self.source / "etc/tup/owner-enrolled.json").write_text("{}")
        self.refused("already carries owner enrollment state")

    def test_existing_data_needs_allow_existing_and_is_described(self):
        self.windows_ntfs("sda")
        with self.assertRaises(Refusal) as caught:
            self.plan("/dev/sda")
        message = str(caught.exception)
        for fragment in ("--allow-existing", "RAW report proves nothing", "partition table gpt", "ntfs", "Windows"):
            self.assertIn(fragment, message)
        self.assert_read_only()
        plan = self.plan("/dev/sda", allow_existing=True)
        self.assertTrue(plan["allow_existing"])
        self.assertTrue(any("ntfs" in line for line in plan["destroys"]))
        self.assertIn("this will ERASE", disk.summary_text(plan))
        self.assert_read_only()

    def test_any_single_signature_counts_as_data(self):
        for node, sigs, blk in (("/dev/vda", [{"offset": "0x438", "type": "ext4", "uuid": "U", "label": None}], {}),
                                ("/dev/vda", [], {"TYPE": "crypto_LUKS"})):
            self.host.signatures[node], self.host.blkid_out[node] = sigs, blk
            self.host.lsblk["/dev/vda"]["serial"] = "virtio-0001"
            self.refused("already holds data", "/dev/vda")

    def test_a_damaged_partition_table_is_data_not_an_error_and_not_blank(self):
        self.host.sfdisk_error["/dev/nvme0n1"] = (1, "", "sfdisk: /dev/nvme0n1: failed to read the GPT: bad CRC\n")
        self.refused("cannot read: sfdisk --dump failed")
        plan = self.plan(allow_existing=True)
        self.assertIn("a partition table that sfdisk cannot read", plan["destroys"][0])
        self.assert_read_only()

    def test_a_disk_without_serial_or_wwn_cannot_be_named(self):
        self.host.lsblk["/dev/vda"]["serial"] = None
        self.refused("neither a serial nor a WWN", "/dev/vda")
        self.host.lsblk["/dev/vda"]["wwn"] = "0xabc"
        plan = self.plan("/dev/vda")
        self.assertEqual(plan["confirmation_basis"], "wwn")
        self.assertTrue(disk.summary_text(plan).endswith("Confirmation token: 0xabc-" + plan["digest"][:8] + "\n"))

    def test_refuses_a_disk_that_is_too_small(self):
        self.host.lsblk["/dev/nvme0n1"]["size"] = 600 << 20
        self.refused("too small")

    def test_plan_cannot_run_a_write_capable_command(self):
        planning = disk.Planning(self.host)
        for argv in (["/usr/sbin/sfdisk", "/dev/sda"], ["/usr/sbin/wipefs", "-a", "/dev/sda"],
                     ["/usr/sbin/wipefs", "--json", "/dev/sda"], ["/usr/sbin/mkfs.ext4", "/dev/sda"],
                     ["/usr/sbin/blkid", "/dev/sda"], ["/usr/bin/cp", "-a", "a", "b"]):
            with self.subTest(argv=argv), self.assertRaisesRegex(Refusal, "not read-only"):
                planning.run(argv)
        self.assertEqual(self.host.commands, [])

    def test_enroll_input_is_validated_and_hashed(self):
        keys = self.base / "enroll"
        keys.mkdir()
        (keys / "authorized_keys").write_bytes(b"ssh-ed25519 AAAA example\n")
        (keys / "owner").write_bytes(b"alex\n")
        plan = self.plan(enroll_input=keys)
        self.assertEqual(plan["enroll_input"]["files"]["owner"], inputs.digest(b"alex\n"))
        (keys / "id_rsa").write_text("private")
        self.refused("only", enroll_input=keys)
        (keys / "id_rsa").unlink()
        (keys / "authorized_keys").unlink()
        self.refused("authorized_keys", enroll_input=keys)


@unittest.skipUnless(POSIX, "apply needs POSIX directory sync and modes")
class ApplyTests(Base):
    def setUp(self):
        super().setUp()
        self.plan_file = self.base / "PLAN.json"
        self.state = self.base / "state"
        self.enroll = self.base / "enroll"
        self.enroll.mkdir()
        (self.enroll / "authorized_keys").write_bytes(b"ssh-ed25519 AAAA example\n")
        self.make_plan()

    def make_plan(self, target="/dev/nvme0n1", **kwargs):
        made = self.plan(target, enroll_input=self.enroll, **kwargs)
        self.plan_file.write_text(json.dumps(made, indent=2, sort_keys=True))
        self.made = made
        self.token = disk.confirmation_token(made["target"]["identity"], made["digest"])
        self.host.commands.clear()

    def apply(self, token=None, state=None):
        return disk.apply(self.host, self.plan_file, self.token if token is None else token, state or self.state)

    def refused_apply(self, pattern, **kwargs):
        with self.assertRaisesRegex(Refusal, pattern):
            self.apply(**kwargs)
        self.assertEqual(self.host.mutating(), [])
        self.assertFalse(os.path.lexists(self.state))
        self.assertEqual(self.host.written, [])

    def test_successful_apply_runs_exactly_these_commands_in_order(self):
        receipt = self.apply()
        layout = self.made["layout"]
        mnt = self.state / "mnt"
        sfdisk = self.made["tools"]["sfdisk"]["path"]
        tool = lambda name: self.made["tools"][name]["path"]
        mutating = [(a[0], *a[1:]) for a, _ in self.host.commands if a[1:2] != ["--version"] and a[1:2] not in (["--help"], ["-V"])]
        # Reads that precede the first write are not in this list's head; the writes and checks from there are.
        start = next(i for i, a in enumerate(mutating) if a[0] == tool("grub-script-check"))
        self.assertEqual(mutating[start:], [
            (tool("grub-script-check"), str(self.state / "boot/grub.cfg")),
            (tool("grub-mkstandalone"), "-O", "x86_64-efi", "--fonts=", "--themes=", "--locales=", "-o",
             str(self.state / "boot/BOOTX64.EFI"), f"boot/grub/grub.cfg={self.state / 'boot/grub.cfg'}"),
            (sfdisk, "--lock", "--wipe", "always", "--wipe-partitions", "always", "/dev/nvme0n1"),
            (tool("udevadm"), "settle", "--timeout=60"),
            (sfdisk, "--json", "/dev/nvme0n1"),
            (tool("mkfs.fat"), "-F", "32", "-i", layout["esp"]["volume_id"], "-n", "TUP-ESP", "/dev/nvme0n1p1"),
            (tool("mkfs.ext4"), "-F", "-q", "-U", layout["root"]["uuid"], "-L", "TUP-ROOT", "/dev/nvme0n1p2"),
            (tool("udevadm"), "settle", "--timeout=60"),
            (tool("blkid"), "-p", "-o", "export", "/dev/nvme0n1p1"),
            (tool("blkid"), "-p", "-o", "export", "/dev/nvme0n1p2"),
            (tool("mount"), "-t", "ext4", "-o", "rw", "/dev/nvme0n1p2", str(mnt / "root")),
            (tool("mount"), "-t", "vfat", "-o", "rw,umask=0077,codepage=437,iocharset=iso8859-1", "/dev/nvme0n1p1", str(mnt / "esp")),
            (tool("cp"), "-a", "--one-file-system", f"{self.source}/.", f"{mnt / 'root'}/"),
            (tool("sync"),),
            (tool("umount"), str(mnt / "esp")),
            (tool("umount"), str(mnt / "root")),
            (tool("e2fsck"), "-f", "-n", "/dev/nvme0n1p2"),
            (tool("fsck.fat"), "-n", "/dev/nvme0n1p1"),
            (tool("blkid"), "-p", "-o", "export", "/dev/nvme0n1p1"),
            (tool("blkid"), "-p", "-o", "export", "/dev/nvme0n1p2"),
            (sfdisk, "--json", "/dev/nvme0n1"),
            (tool("sync"),)])
        self.assertEqual(self.host.written, [("/dev/nvme0n1", self.made["texts"]["sfdisk_script"])])
        self.assertEqual(self.host.mount_rows, [r for r in self.host.mount_rows if str(self.state) not in r])
        self.assertEqual(receipt, json.loads((self.state / "RECEIPT.json").read_text()))

    def test_deployed_files_receipt_and_modes(self):
        receipt = self.apply()
        root, esp = self.state / "mnt/root", self.state / "mnt/esp"
        self.assertEqual((root / "etc/fstab").read_text(), self.made["texts"]["fstab"])
        self.assertEqual((root / "etc/machine-id").read_bytes(), b"")
        self.assertEqual(list((root / "etc").glob("ssh/ssh_host_*")), [])
        self.assertTrue((root / "boot/efi").is_dir())
        self.assertEqual(oct((root / disk.ENROLL_TARGET).stat().st_mode & 0o777), "0o700")
        self.assertEqual(oct((root / disk.ENROLL_TARGET / "authorized_keys").stat().st_mode & 0o777), "0o600")
        self.assertEqual((root / disk.ENROLL_TARGET / "authorized_keys").read_text(), "ssh-ed25519 AAAA example\n")
        self.assertEqual((esp / f"tup/vmlinuz-{RELEASE}").read_bytes(), (self.source / f"boot/vmlinuz-{RELEASE}").read_bytes())
        self.assertEqual(disk.parse_microcode_cpio((esp / "tup/amd-ucode.img").read_bytes())
                         ["kernel/x86/microcode/AuthenticAMD.bin"], (0o100644, MICROCODE))
        self.assertTrue((esp / "EFI/BOOT/BOOTX64.EFI").read_bytes().startswith(b"MZ"))
        self.assertEqual(receipt["schema"], "tup.install-receipt.v1")
        self.assertEqual(receipt["plan_sha256"], self.made["digest"])
        self.assertEqual(receipt["source_inventory_sha256"], self.made["source"]["inventory_sha256"])
        self.assertNotEqual(receipt["copy_inventory_sha256"], receipt["source_inventory_sha256"])  # lost+found
        self.assertNotEqual(receipt["deployed_inventory_sha256"], receipt["copy_inventory_sha256"])  # fstab, enrollment
        self.assertEqual(receipt["planned_changes"], ["boot", "boot/efi", "etc", "etc/fstab", "etc/tup", "etc/tup/enroll-input",
                                                      "etc/tup/enroll-input/authorized_keys", "lost+found"])
        self.assertEqual([p["node"] for p in receipt["created"]["partitions"]], ["/dev/nvme0n1p1", "/dev/nvme0n1p2"])
        self.assertEqual(set(receipt["bootloader"]), {"EFI/BOOT/BOOTX64.EFI", f"tup/vmlinuz-{RELEASE}", "tup/amd-ucode.img", "grub.cfg"})
        self.assertFalse(receipt["boot_tested"])
        self.assertEqual(set(receipt["tools"]), set(disk.TOOLS))
        journal = [json.loads(line)["step"] for line in (self.state / "PROGRESS.jsonl").read_text().splitlines()]
        self.assertEqual(journal[0], "prepare-boot-files")
        self.assertEqual(journal[-1], "done")
        self.assertTrue((self.state / "INTENT.json").is_file())
        intent = json.loads((self.state / "INTENT.json").read_text())
        self.assertEqual((intent["plan_sha256"], intent["schema"]), (self.made["digest"], "tup.install-intent.v1"))

    def test_apply_without_microcode_loads_no_initrd(self):
        (self.source / disk.MICROCODE).unlink()
        self.make_plan()
        self.assertFalse(self.made["microcode"]["loaded"])
        self.assertNotIn("initrd", self.made["texts"]["grub_cfg"])
        self.assertIn("NOT loaded", disk.summary_text(self.made))
        self.apply()
        self.assertFalse((self.state / "mnt/esp/tup/amd-ucode.img").exists())

    def test_the_token_is_bound_to_this_disk_and_plan(self):
        wrong = [self.token[:-1] + ("0" if self.token[-1] != "0" else "1"), "WD-WX11A2345678-" + self.made["digest"][:8],
                 "", "S5GXNX0R123456A", self.token.lower(), "S5GXNX0R123456A-éééééééé"]
        for token in wrong:
            with self.subTest(token=token):
                self.refused_apply("confirmation token", token=token)

    def test_any_drift_between_plan_and_apply_refuses_before_a_write(self):
        node = "/dev/nvme0n1"
        base = self.host.links["/sys/class/block/nvme0n1"]

        def serial():
            self.host.lsblk[node]["serial"] = "OTHERSERIAL"

        def size():
            self.host.lsblk[node]["size"] += 512

        def table():
            self.host.dump[node] = "label: gpt\nlabel-id: 1\n"

        def signature():
            self.host.signatures[node] = [{"offset": "0x438", "type": "ext4", "uuid": "U", "label": None}]

        def probe():
            self.host.blkid_out[node] = {"TYPE": "ext4"}

        def mounted_partition():
            self.host.lsblk[node]["children"] = [node_json("nvme0n1p1", "259:1", 1 << 20, kind="part", mounts=("/mnt",))]

        def new_mount():
            self.host.add_partition("nvme0n1", 1, 2048, 2048)
            self.host.mount_rows.append("40 20 259:1 / /mnt rw - ext4 /dev/nvme0n1p1 rw")

        def holder():
            self.host.dirs[base + "/holders"] = ["dm-0"]

        def other_disk_in_use():
            self.host.mount_rows.append("41 20 8:48 / /mnt2 rw - ext4 /dev/sdd1 rw")
            self.host.add_disk("sdd", "8:48", 1 << 30)
            self.host.add_partition("sdd", 1, 2048, 2048)

        def source_file():
            (self.source / "etc/hostname").write_text("changed\n")

        def kernel():
            (self.source / f"boot/vmlinuz-{RELEASE}").write_bytes(b"x")

        def enroll_input():
            (self.enroll / "authorized_keys").write_bytes(b"ssh-ed25519 BBBB other\n")

        def tool():
            self.host.sha256 = lambda path: "0" * 64

        for change in (serial, size, table, signature, probe, mounted_partition, new_mount, holder, other_disk_in_use,
                       source_file, kernel, enroll_input, tool):
            with self.subTest(change=change.__name__):
                self.setUp()
                change()
                with self.assertRaises(Refusal):
                    self.apply()
                self.assertEqual(self.host.mutating(), [])
                self.assertFalse(os.path.lexists(self.state))

    def test_edited_plan_is_refused(self):
        raw = json.loads(self.plan_file.read_text())
        raw["layout"]["partitions"][1]["start"] += 1
        self.plan_file.write_text(json.dumps(raw))
        self.refused_apply("edited after it was written")
        raw = json.loads(self.plan_file.read_text())
        raw["texts"]["fstab"] += "/dev/sda1 /mnt ext4 defaults 0 0\n"
        raw["digest"] = disk.plan_digest(raw)
        self.plan_file.write_text(json.dumps(raw))
        self.refused_apply("edited after it was written|differ from what its fields generate")

    def test_plan_for_one_disk_is_refused_when_another_answers_to_that_name(self):
        other = self.host.lsblk["/dev/sda"]
        self.host.lsblk["/dev/nvme0n1"] = dict(other, path="/dev/nvme0n1", name="nvme0n1", kname="nvme0n1")
        self.refused_apply("differs from the plan")

    def kill_during_copy(self):
        def hook(host, argv):
            if Path(argv[0]).name == "cp" and argv[1] == "-a":
                raise disk.Interrupted("signal 15")
        self.host.hook = hook
        with self.assertRaises(disk.Interrupted):
            self.apply()
        self.host.hook = None
        self.host.commands.clear()

    def test_rerun_with_the_same_state_directory_reports_the_recorded_intent(self):
        self.kill_during_copy()
        with self.assertRaisesRegex(Refusal, r"already exists.*recorded intent for plan " + self.made["digest"]
                                    + r".*last journal entry.*copy-root.*NEW plan with --allow-existing"):
            self.apply()

    def test_rerun_with_a_new_state_on_a_half_written_disk_refuses_as_drift(self):
        self.kill_during_copy()
        # The interrupted run wrote a table; the same plan must now be refused although the token is right.
        self.host.lsblk["/dev/nvme0n1"]["children"] = [node_json("nvme0n1p1", "259:1", 1 << 29, kind="part", fstype="vfat")]
        self.host.dump["/dev/nvme0n1"] = "label: gpt\n"
        with self.assertRaisesRegex(Refusal, r"differs from the plan .*partition table.*new plan with --allow-existing"):
            self.apply(state=self.base / "state-2")
        self.assertEqual(self.host.mutating(), [])

    def test_failure_or_interrupt_at_every_command_unmounts_everything(self):
        self.apply()
        total = len(self.host.commands)
        self.assertGreater(total, 30)
        for fault in ("fail", "interrupt"):
            for index in range(total):
                with self.subTest(fault=fault, index=index):
                    self.setUp()
                    original, seen = self.host.run, []

                    def run(argv, stdin=None, timeout=900, original=original, seen=seen, index=index, fault=fault):
                        seen.append(argv)
                        if len(seen) - 1 == index:
                            if fault == "interrupt":
                                raise disk.Interrupted("signal 15")
                            return 1, "", "injected failure"
                        return original(argv, stdin, timeout)
                    self.host.run = run
                    with self.assertRaises((Refusal, KeyboardInterrupt)):
                        self.apply()
                    left = [row for row in self.host.mount_rows if str(self.state) in row]
                    if Path(seen[index][0]).name == "umount" and seen[index][1].startswith("/"):
                        self.assertTrue(left)  # the unmount itself failed: reported, not hidden
                    else:
                        self.assertEqual(left, [])
                    if self.state.exists():
                        self.assertTrue((self.state / "FAILED.json").exists())
                    if not any(Path(a[0]).name == "sfdisk" and not disk.read_only_command(a) for a in seen[:index + 1]):
                        self.assertEqual(self.host.written, [])

    def test_unmount_failure_is_reported_loudly(self):
        self.host.tool_umount = lambda args, stdin: (32, "", "target is busy")
        with self.assertRaisesRegex(Refusal, "could not unmount everything"):
            self.apply()

    def test_a_state_directory_with_unreadable_intent_is_still_refused(self):
        self.state.mkdir()
        (self.state / "INTENT.json").write_text("{not json")
        with self.assertRaisesRegex(Refusal, "INTENT.json is unreadable"):
            self.apply()

    def test_apply_refuses_any_existing_state_directory_without_touching_the_disk(self):
        self.state.mkdir()
        with self.assertRaisesRegex(Refusal, "already exists.*NEW plan"):
            self.apply()
        self.assertEqual(self.host.mutating(), [])

    def test_state_must_be_new_below_a_real_directory(self):
        with self.assertRaisesRegex(Refusal, "new directory below an existing directory"):
            self.apply(state=self.base / "missing" / "state")
        self.assertEqual(self.host.mutating(), [])


@unittest.skipUnless(POSIX, "main needs POSIX")
class CommandLineTests(Base):
    def run_main(self, *argv):
        import contextlib
        import io
        from unittest import mock
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(os, "geteuid", return_value=0), mock.patch.object(disk, "check_platform"), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = disk.main(list(argv), host=self.host)
        return code, out.getvalue(), err.getvalue()

    def test_plan_then_apply_through_the_command_line(self):
        plan = self.base / "p.json"
        code, out, err = self.run_main("plan", "--target", "/dev/nvme0n1", "--source", str(self.source), "--output", str(plan))
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(oct(plan.stat().st_mode & 0o777), "0o600")
        token = out.splitlines()[-1].removeprefix("Confirmation token: ")
        self.assertRegex(token, r"^S5GXNX0R123456A-[0-9a-f]{8}$")
        self.assertTrue(disk.load_plan(plan)["digest"].startswith(token.split("-")[-1]))
        code, out, err = self.run_main("plan", "--target", "/dev/nvme0n1", "--source", str(self.source), "--output", str(plan))
        self.assertEqual(code, 1)  # an existing output file is never overwritten
        self.assertIn("FAILED", err)
        code, out, err = self.run_main("apply", "--plan", str(plan), "--confirm", "nope", "--state", str(self.base / "st"))
        self.assertEqual((code, out), (2, ""))
        self.assertIn("REFUSED: the confirmation token", err)
        code, out, err = self.run_main("apply", "--plan", str(plan), "--confirm", token, "--state", str(self.base / "st"))
        self.assertEqual((code, err), (0, ""))
        self.assertIn("receipt", out)

    def test_refusal_exits_2_and_a_signal_exits_143_with_a_message(self):
        self.host.lsblk["/dev/sdb"] = node_json("sdb", "8:16", 64 << 30, serial="VENTOY0001", tran="usb", rm=True)
        self.host.dump["/dev/sdb"], self.host.signatures["/dev/sdb"], self.host.blkid_out["/dev/sdb"] = None, [], {}
        code, out, err = self.run_main("plan", "--target", "/dev/sdb", "--source", str(self.source), "--output", str(self.base / "x.json"))
        self.assertEqual(code, 2)
        self.assertIn("tup-ventoy/media", err)
        self.assertFalse((self.base / "x.json").exists())

        def hook(host, argv):
            if disk.Path(argv[0]).name == "sfdisk" and "--lock" in argv:
                raise disk.Interrupted("signal 15")
        plan = self.base / "p.json"
        self.run_main("plan", "--target", "/dev/nvme0n1", "--source", str(self.source), "--output", str(plan))
        token = disk.confirmation_token(json.loads(plan.read_text())["target"]["identity"], json.loads(plan.read_text())["digest"])
        self.host.hook = hook
        code, out, err = self.run_main("apply", "--plan", str(plan), "--confirm", token, "--state", str(self.base / "st"))
        self.assertEqual(code, 143)
        self.assertIn("INTERRUPTED (signal 15)", err)
        self.assertEqual(self.host.written, [])

    def test_requires_root(self):
        from unittest import mock
        with mock.patch.object(os, "geteuid", return_value=1000), mock.patch.object(disk, "check_platform"):
            self.assertEqual(disk.main(["plan", "--target", "/dev/sda", "--source", "/x", "--output", "/x"], host=self.host), 2)


class GeneratedFileTests(unittest.TestCase):
    def test_microcode_archive_round_trips_and_is_newc(self):
        raw = disk.microcode_cpio(MICROCODE)
        self.assertEqual(len(raw) % 4, 0)
        found = disk.parse_microcode_cpio(raw)
        self.assertEqual(list(found), ["kernel", "kernel/x86", "kernel/x86/microcode", "kernel/x86/microcode/AuthenticAMD.bin"])
        self.assertEqual(found["kernel/x86/microcode/AuthenticAMD.bin"], (0o100644, MICROCODE))
        self.assertEqual(found["kernel"][0], 0o040755)

    @unittest.skipUnless(shutil.which("cpio") and POSIX, "needs GNU cpio")
    def test_microcode_archive_is_read_by_the_real_cpio(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "ucode.img"
            archive.write_bytes(disk.microcode_cpio(MICROCODE))
            listing = subprocess.run(["cpio", "-it"], input=archive.read_bytes(), capture_output=True, check=True)
            self.assertEqual(listing.stdout.decode().split(), ["kernel", "kernel/x86", "kernel/x86/microcode",
                                                               "kernel/x86/microcode/AuthenticAMD.bin"])
            out = Path(temp) / "out"
            out.mkdir()
            subprocess.run(["cpio", "-id", "--quiet"], input=archive.read_bytes(), cwd=out, check=True)
            self.assertEqual((out / "kernel/x86/microcode/AuthenticAMD.bin").read_bytes(), MICROCODE)

    @unittest.skipUnless(POSIX, "symbolic links")
    def test_a_tool_that_is_a_symbolic_link_is_hashed_by_its_target(self):
        with tempfile.TemporaryDirectory() as temp:
            real, link = Path(temp) / "mke2fs", Path(temp) / "mkfs.ext4"
            real.write_bytes(b"tool")
            link.symlink_to(real)
            self.assertEqual(disk.Host().sha256(str(link)), inputs.digest(b"tool"))

    def test_layout_for_the_sizes_it_will_meet(self):
        for size, sector in ((500107862016, 512), (1000204886016, 4096), (64 << 30, 512)):
            with self.subTest(size=size, sector=sector):
                counter = iter(range(100))
                layout = disk.make_layout({"log_sec": sector, "size_bytes": size}, 512,
                                          lambda n: hashlib.sha256(bytes([next(counter)])).digest()[:n])
                esp, root = layout["partitions"]
                align = (1 << 20) // sector
                self.assertEqual((esp["start"] % align, root["start"] % align, (root["start"] + root["size"]) % align), (0, 0, 0))
                self.assertEqual(esp["start"] + esp["size"], root["start"])
                table = -(-16384 // sector)
                self.assertLessEqual(root["start"] + root["size"] - 1, size // sector - table - 2)
                self.assertGreater(root["start"] + root["size"], size // sector - table - 2 - align)


@unittest.skipUnless(POSIX and shutil.which("sfdisk") and shutil.which("blkid"), "needs util-linux")
class RealToolTests(unittest.TestCase):
    """sfdisk, mkfs and blkid on regular files only. Nothing here opens a /dev path."""

    def layout(self, size, sector=512):
        counter = iter(range(100))
        return disk.make_layout({"log_sec": sector, "size_bytes": size}, 64,
                                lambda n: hashlib.sha256(bytes([next(counter)])).digest()[:n])

    def test_sfdisk_script_produces_the_planned_guids_and_offsets(self):
        with tempfile.TemporaryDirectory() as temp:
            image = Path(temp) / "disk.img"
            with open(image, "wb") as stream:
                stream.truncate(2 << 30)
            layout = self.layout(2 << 30)
            done = subprocess.run(["sfdisk", "--wipe", "always", "--wipe-partitions", "always", str(image)],
                                  input=disk.sfdisk_script(layout).encode(), capture_output=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            table = json.loads(subprocess.run(["sfdisk", "--json", str(image)], capture_output=True, check=True).stdout)["partitiontable"]
            self.assertEqual(table["id"].lower(), layout["disk_guid"])
            self.assertEqual([(p["start"], p["size"], p["type"], p["uuid"].lower(), p["name"]) for p in table["partitions"]],
                             [(p["start"], p["size"], p["type"], p["guid"], p["name"]) for p in layout["partitions"]])
            self.assertLessEqual(table["partitions"][1]["start"] + table["partitions"][1]["size"] - 1, table["lastlba"])
            self.assertGreater(table["partitions"][1]["start"] + table["partitions"][1]["size"], table["lastlba"] - 2048)

    def test_mkfs_options_set_the_planned_identifiers(self):
        if not shutil.which("mkfs.ext4"):
            self.skipTest("no mkfs.ext4")
        layout = self.layout(2 << 30)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "root.img"
            with open(root, "wb") as stream:
                stream.truncate(64 << 20)
            subprocess.run(["mkfs.ext4", "-F", "-q", "-U", layout["root"]["uuid"], "-L", "TUP-ROOT", str(root)], check=True)
            found = dict(line.split("=", 1) for line in subprocess.run(
                ["blkid", "-p", "-o", "export", str(root)], capture_output=True, text=True, check=True).stdout.splitlines())
            self.assertEqual((found["TYPE"], found["UUID"], found["LABEL"]), ("ext4", layout["root"]["uuid"], "TUP-ROOT"))
            if shutil.which("mkfs.fat"):
                esp = Path(temp) / "esp.img"
                with open(esp, "wb") as stream:
                    stream.truncate(64 << 20)
                subprocess.run(["mkfs.fat", "-F", "32", "-i", layout["esp"]["volume_id"], "-n", "TUP-ESP", str(esp)],
                               check=True, capture_output=True)
                found = dict(line.split("=", 1) for line in subprocess.run(
                    ["blkid", "-p", "-o", "export", str(esp)], capture_output=True, text=True, check=True).stdout.splitlines())
                self.assertEqual((found["TYPE"], found["UUID"], found["LABEL"]), ("vfat", layout["esp"]["uuid"], "TUP-ESP"))

    @unittest.skipUnless(shutil.which("grub-script-check"), "needs GRUB's grub-script-check")
    def test_grub_cfg_passes_grub_script_check(self):
        layout = self.layout(2 << 30)
        text = disk.grub_cfg_text(layout, {"name": "vmlinuz-" + RELEASE}, {"loaded": True}, "a" * 64)
        with tempfile.TemporaryDirectory() as temp:
            cfg = Path(temp) / "grub.cfg"
            cfg.write_text(text)
            done = subprocess.run(["grub-script-check", str(cfg)], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)


if __name__ == "__main__":
    unittest.main()
