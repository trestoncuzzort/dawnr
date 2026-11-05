"""Ventoy live-root hook fixtures: synthetic handoff bytes, a fake sysfs and command stubs.

The real shell functions run, but nothing is mounted and no device is opened.
They do not show that Ventoy, the kernel or dracut behave as assumed.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import unittest

from tup.boot.inputs import Refusal
from tup.boot import ventoy

HOOK = Path(ventoy.__file__).with_name("ventoy-live.sh")
# The target's /bin/sh is bash; the builder's is dash, which keeps the hook POSIX.
SHELLS = [name for name in ("bash", "sh") if os.name == "posix" and shutil.which(name)]
GUID, DISK_SIGNATURE = bytes(range(1, 17)), b"TUP!"

PARSE = '''. "$1"
if vl_parse "$2"; then
    printf '%s\\n' "$VL_GUID" "$VL_DISKSIG" "$VL_PARTITION" "$VL_FSTYPE" "$VL_SIZE" "$VL_PATH"
else
    printf '%s\\n' "$VL_ERROR"
    exit 3
fi
'''

# Stubs stand in for dracut-lib.sh and for every command that would touch a device.
RUN = '''T=$1
hookdir=$T/hooks
log() { printf '%s\\n' "$*" >> "$T/calls"; }
warn() { log "warn $*"; }
info() { log "info $*"; }
ismounted() { [ -e "$T/efivarfs-is-mounted" ]; }
udevadm() {
    case $1 in
        info) cat "$T/udev/${3##*/}" 2> /dev/null ;;
        *) log "udevadm $*" ;;
    esac
}
mount() {
    log "mount $*"
    [ ! -e "$T/mount-fails" ] || return 32
    eval "point=\\${$#} source=\\${$(($# - 1))}"
    cp -R "$T/content/${source##*/}/." "$point"
}
umount() {
    log "umount $*"
    rm -rf "${1:?}"/*
}
losetup() {
    log "losetup $*"
    [ ! -e "$T/losetup-fails" ] || return 1
    echo /dev/loop7
}
od() {
    eval "file=\\${$#}"
    case $file in "$T/dev/"*) log "read ${file##*/}" ;; esac
    command od "$@"
}
rm() { [ -e "$T/job-cannot-leave" ] || command rm "$@"; }
# dracut-initqueue.sh:42-46 and init.sh:197-201: every pass sources each queued job.
for pass in 1 2 3; do
    for job in "$T"/hooks/initqueue/settled/*.sh; do
        [ -e "$job" ] || continue
        job=$job . "$job"
    done
done
'''


def handoff(path="/images/tup test.iso", *, filesystem=0, partition=1, size=4096, guid=GUID):
    raw = bytearray(512)
    raw[:16] = ventoy.SIGNATURE
    raw[17:33] = guid
    struct.pack_into("<QHH", raw, 33, 32 * 1024**3, partition, filesystem)
    encoded = path if isinstance(path, bytes) else path.encode()
    raw[45:45 + len(encoded)] = encoded
    struct.pack_into("<Q", raw, 429, size)
    raw[481:485] = DISK_SIGNATURE
    raw[16] = (-sum(raw)) & 255
    return b"\x07\0\0\0" + bytes(raw)


def per_shell(cls):
    """One concrete TestCase per available shell, or one skipped placeholder."""
    for shell in SHELLS:
        name = f"{cls.__name__}_{shell}"
        globals()[name] = type(name, (cls, unittest.TestCase), {"shell": shell})
    if not SHELLS:
        globals()[cls.__name__ + "_skipped"] = unittest.skip("Linux shell hook fixture")(
            type(cls.__name__ + "_skipped", (unittest.TestCase,), {"test_needs_a_posix_shell": lambda self: None}))
    return cls


@per_shell
class HandoffParsing:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.blob = Path(self.temp.name) / "VentoyOsParam"

    def check(self, raw, message=None):
        """The shell parser must agree with ventoy.py, field for field and refusal for refusal."""
        try:
            parsed = ventoy.parse_handoff(raw, efivarfs=True)
            expected = (0, [parsed["disk_guid"], parsed["disk_signature"], str(parsed["partition"]),
                            parsed["filesystem"], str(parsed["iso_size"]), parsed["iso_path"]])
        except Refusal as error:
            expected = (3, [str(error)])
        if message is not None:
            expected = (3, [message])
        self.blob.write_bytes(raw)
        result = subprocess.run([self.shell, "-c", PARSE, "fixture", str(HOOK), str(self.blob)],
                                capture_output=True, check=False)
        self.assertEqual((result.returncode, result.stdout.decode().splitlines()), expected, result.stderr.decode())
        return expected

    def test_valid_handoffs_yield_the_fields_ventoy_py_yields(self):
        for path in ("/tup.iso", "/images/tup test.iso", "/a b/c d/e f.ISO", "/images/测试.iso",
                     "/é/\U0001f4bf.iso", "/" + "d" * 370 + ".iso"):
            for filesystem in range(6):
                with self.subTest(path=path, filesystem=filesystem):
                    status, lines = self.check(handoff(path, filesystem=filesystem, partition=128, size=2**47 + 5))
                    self.assertEqual((status, lines[-1]), (0, path))

    def test_length_signature_and_checksum_refuse(self):
        raw = handoff()
        for damaged in (raw[:-1], raw + b"x", raw[4:], raw[:4] + b"x" + raw[5:], raw[:90] + b"X" + raw[91:], b""):
            with self.subTest(length=len(damaged)):
                self.assertEqual(self.check(damaged)[0], 3)

    def test_identity_fields_refuse(self):
        for fields in ({"guid": bytes(16)}, {"partition": 0}, {"partition": 129}, {"filesystem": 6},
                       {"filesystem": 65535}, {"size": 0}):
            with self.subTest(fields=fields):
                self.assertEqual(self.check(handoff(**fields)),
                                 (3, ["invalid Ventoy disk/partition/filesystem/image identity"]))

    def test_shell_arithmetic_never_sees_an_impossible_image_size(self):
        # ventoy.py accepts any nonzero size; signed shell arithmetic must not wrap.
        for size in (2**48, 2**63, 2**64 - 1):
            with self.subTest(size=size):
                self.check(handoff(size=size), "invalid Ventoy disk/partition/filesystem/image identity")

    def test_unsafe_paths_refuse(self):
        for path in ("/../root.iso", "/images/../../root.iso", "/images//root.iso", "relative.iso", "",
                     "/images/./root.iso", "/images\\root.iso", "/image\nroot.iso", "/image\x7froot.iso",
                     "/not-an-iso", "/", "/tup.iso/", "/..", "/x.iso/.."):
            with self.subTest(path=path):
                self.assertEqual(self.check(handoff(path)), (3, ["unsafe Ventoy ISO path"]))

    def test_malformed_utf8_refuses(self):
        for encoded in (b"/\xff.iso", b"/\xc0\xaf.iso", b"/\xe0\x80\xaf.iso", b"/\xed\xa0\x80.iso",
                        b"/\xf4\x90\x80\x80.iso", b"/\xf8\x88\x80\x80\x80.iso", b"/\xe6\xb5.iso", b"/x.iso\xe6"):
            with self.subTest(encoded=encoded):
                self.assertEqual(self.check(handoff(encoded)), (3, ["invalid UTF-8 Ventoy ISO path"]))

    def test_path_field_must_be_terminated_and_zero_padded(self):
        raw = bytearray(handoff("/tup.iso"))
        raw[4 + 45 + 20] = ord("x")
        raw[4 + 16] = 0
        raw[4 + 16] = (-sum(raw[4:])) & 255
        self.assertEqual(self.check(bytes(raw)), (3, ["nonzero bytes after Ventoy path terminator"]))
        self.assertEqual(self.check(handoff("/" + "d" * 379 + ".iso")), (3, ["unterminated Ventoy path"]))


@per_shell
class Discovery:
    """Queue passes over a fake sysfs. The image is /images/tup test.iso on sdb1."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(os.path.realpath(self.temp.name))
        for name in ("sys/class/block", "sys/firmware/efi/efivars", "dev", "udev", "hooks/emergency",
                     "hooks/initqueue/settled", "content"):
            (self.base / name).mkdir(parents=True)
        # The hook exactly as packaged, except that its three fixed locations point into the fixture.
        self.job = self.base / "hooks/initqueue/settled/20-tup-ventoy-live.sh"
        self.hook = HOOK.read_text(encoding="ascii")
        for name, target in (("SYS", "sys"), ("DEV", "dev"), ("DIR", "run")):
            self.hook, count = re.subn(rf"(?m)^VL_{name}=/.*$", f"VL_{name}={self.base}/{target}", self.hook)
            self.assertEqual(count, 1)
        self.image = b"fixture ISO bytes"
        self.variable = self.base / "sys/firmware/efi/efivars" / ventoy.EFI_VARIABLE
        self.variable.write_bytes(handoff(size=len(self.image)))
        (self.base / "efivarfs-is-mounted").touch()
        # An unrelated internal disk sorts first; run() fails on any read of it.
        self.disk("nvme0n1", None, {1: ("vfat", "EFI"), 2: ("ext4", "root")}, separator="p")
        self.disk("sdb", GUID + DISK_SIGNATURE, {1: ("exfat", "Ventoy"), 2: ("vfat", "VTOYEFI")})
        self.put("sdb1", "images/tup test.iso", self.image)

    def disk(self, name, identity, partitions, *, separator=""):
        directory = self.base / "sys/devices/fixture/block" / name
        directory.mkdir(parents=True)
        (self.base / "sys/class/block" / name).symlink_to(directory)
        sector = bytearray(512)
        if identity:
            sector[384:400], sector[440:444] = identity[:16], identity[16:]
        (self.base / "dev" / name).write_bytes(sector)
        for number, (filesystem, label) in partitions.items():
            part = name + separator + str(number)
            (directory / part).mkdir()
            (directory / part / "partition").write_text(f"{number}\n")
            (self.base / "sys/class/block" / part).symlink_to(directory / part)
            (self.base / "udev" / part).write_text(f"ID_FS_TYPE={filesystem}\nID_FS_LABEL={label}\n")
            (self.base / "dev" / part).touch()

    def put(self, partition, relative, raw):
        path = self.base / "content" / partition / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)

    def run_hook(self):
        """A fresh boot: returns the logged calls; self.reads names the disks whose sector 0 was read."""
        for name in ("run", "calls", "hooks/emergency/79-tup-ventoy-live.sh"):
            path = self.base / name
            shutil.rmtree(path) if path.is_dir() else path.unlink(missing_ok=True)
        self.job.write_text(self.hook, encoding="ascii", newline="\n")
        result = subprocess.run([self.shell, "-c", RUN, "fixture", str(self.base)],
                                capture_output=True, text=True, check=False)
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        lines = (self.base / "calls").read_text().splitlines() if (self.base / "calls").exists() else []
        self.reads = sorted({line for line in lines if line.startswith("read ")})
        self.assertNotIn("read nvme0n1", self.reads)
        return [line for line in lines if not line.startswith("read ")]

    def commands(self, calls, name):
        return [line for line in calls if line.startswith(name + " ")]

    def test_selected_partition_is_mounted_read_only_and_the_image_attached_read_only(self):
        media = f"{self.base}/run/media"
        calls = self.run_hook()
        self.assertEqual(self.commands(calls, "mount"),
                         [f"mount -n -t exfat -o ro,nosuid,nodev,noexec {self.base}/dev/sdb1 {media}"])
        self.assertEqual(self.commands(calls, "losetup"), [f"losetup -r -f --show -- {media}/images/tup test.iso"])
        self.assertEqual(self.commands(calls, "udevadm"), ["udevadm trigger --action=change --name-match=/dev/loop7"])
        self.assertEqual(self.commands(calls, "umount") + self.commands(calls, "warn"), [])
        self.assertIn("attached /dev/loop7 read-only to /images/tup test.iso", calls[-1])
        self.assertFalse(self.job.exists())
        self.assertEqual(self.reads, ["read sdb"])
        self.assertEqual((self.base / "run/VentoyOsParam").read_bytes(), self.variable.read_bytes())

    def test_job_that_cannot_leave_the_queue_never_mounts_or_attaches_twice(self):
        (self.base / "job-cannot-leave").touch()
        calls = self.run_hook()
        self.assertEqual((len(self.commands(calls, "mount")), len(self.commands(calls, "losetup"))), (1, 1))
        self.variable.write_bytes(b"not a handoff")
        self.assertEqual(len(self.run_hook()), 1)

    def test_without_the_variable_the_hook_leaves_and_touches_nothing(self):
        self.variable.unlink()
        self.assertEqual(self.run_hook(), [])
        self.assertFalse(self.job.exists() or (self.base / "run").exists())
        # A non-UEFI boot has no /sys/firmware/efi at all.
        shutil.rmtree(self.base / "sys/firmware")
        self.assertEqual(self.run_hook(), [])
        self.assertFalse(self.job.exists() or (self.base / "run").exists())

    def test_unmounted_efivarfs_is_read_at_a_private_read_only_mount_and_released(self):
        # dracut's own init does not mount efivarfs; the stub "mounts" these bytes.
        (self.base / "efivarfs-is-mounted").unlink()
        (self.base / "content/efivarfs").mkdir()
        staged = self.base / "content/efivarfs" / ventoy.EFI_VARIABLE
        self.variable.rename(staged)
        private = f"{self.base}/run/efivars"
        calls = self.run_hook()
        self.assertEqual(calls[:2], [f"mount -n -t efivarfs -o ro,nosuid,nodev,noexec efivarfs {private}",
                                     f"umount {private}"])
        self.assertEqual(len(self.commands(calls, "losetup")), 1)
        self.assertFalse(Path(private).exists())
        staged.unlink()
        self.assertEqual(len(self.run_hook()), 2)
        self.assertFalse(self.job.exists() or (self.base / "run").exists())
        (self.base / "mount-fails").touch()
        calls = self.run_hook()
        self.assertEqual(len(calls), 2)
        self.assertIn("efivarfs cannot be read", calls[1])
        self.assertFalse(self.job.exists() or (self.base / "run").exists())

    def test_malformed_handoff_is_reported_and_nothing_is_mounted(self):
        self.variable.write_bytes(handoff("/images/../tup.iso", size=len(self.image)))
        calls = self.run_hook()
        self.assertEqual(len(calls), 1)
        self.assertIn("malformed VentoyOsParam: unsafe Ventoy ISO path", calls[0])
        self.assertFalse(self.job.exists())
        self.assertIn("unsafe Ventoy ISO path", (self.base / "run/status").read_text())
        self.assertIn(f"{self.base}/run/status", (self.base / "hooks/emergency/79-tup-ventoy-live.sh").read_text())

    def test_filesystems_without_a_kernel_driver_refuse_before_any_mount(self):
        for filesystem, name in ((1, "ntfs"), (3, "xfs"), (4, "udf")):
            with self.subTest(filesystem=name):
                self.variable.write_bytes(handoff(filesystem=filesystem, size=len(self.image)))
                calls = self.run_hook()
                self.assertEqual(len(calls), 1)
                self.assertIn(f"is {name}, which this kernel cannot mount", calls[0])
                self.assertFalse(self.job.exists())

    def test_ext_is_mounted_without_journal_replay_and_fat_with_utf8_names(self):
        for code, probed, expected in ((2, "ext4", "-t ext4 -o ro,noload,nosuid,nodev,noexec"),
                                       (2, "ext2", "-t ext4 -o ro,noload,nosuid,nodev,noexec"),
                                       (5, "vfat", "-t vfat -o ro,utf8,nosuid,nodev,noexec")):
            with self.subTest(probed=probed):
                self.variable.write_bytes(handoff(filesystem=code, size=len(self.image)))
                (self.base / "udev/sdb1").write_text(f"ID_FS_TYPE={probed}\nID_FS_LABEL=Ventoy\n")
                calls = self.run_hook()
                self.assertEqual(self.commands(calls, "mount"),
                                 [f"mount -n {expected} {self.base}/dev/sdb1 {self.base}/run/media"])
                self.assertEqual(len(self.commands(calls, "losetup")), 1)

    def test_absent_media_keeps_waiting_quietly_without_reading_other_disks(self):
        sector = (self.base / "dev/sdb").read_bytes()
        cases = {"no marker": lambda: (self.base / "udev/sdb2").write_text("ID_FS_TYPE=vfat\nID_FS_LABEL=OTHER\n"),
                 "other disk GUID": lambda: (self.base / "dev/sdb").write_bytes(sector[:384] + bytes(16) + sector[400:]),
                 "other disk signature": lambda: (self.base / "dev/sdb").write_bytes(sector[:440] + b"ELSE" + sector[444:]),
                 "other filesystem": lambda: (self.base / "udev/sdb1").write_text("ID_FS_TYPE=ntfs\n"),
                 "other partition": lambda: self.variable.write_bytes(handoff(partition=3, size=len(self.image)))}
        for name, damage in cases.items():
            with self.subTest(case=name):
                original = {path: path.read_bytes() for path in (
                    self.base / "udev/sdb1", self.base / "udev/sdb2", self.base / "dev/sdb", self.variable)}
                damage()
                calls = self.run_hook()
                # Three passes, one notice: the job stays queued until rd.retry expires.
                self.assertEqual([line.split()[0] for line in calls], ["info", "warn"])
                self.assertIn("retrying until rd.retry expires", calls[1])
                self.assertTrue(self.job.exists())
                self.assertEqual(self.reads, [] if name == "no marker" else ["read sdb"])
                for path, raw in original.items():
                    path.write_bytes(raw)

    def test_duplicate_ventoy_media_refuse_rather_than_guess(self):
        self.disk("sdc", GUID + DISK_SIGNATURE, {1: ("exfat", "Ventoy"), 2: ("vfat", "VTOYEFI")})
        self.put("sdc1", "images/tup test.iso", self.image)
        calls = self.run_hook()
        self.assertEqual(self.commands(calls, "mount") + self.commands(calls, "losetup"), [])
        self.assertIn("more than one partition matches", calls[-1])
        self.assertFalse(self.job.exists())

    def test_reordered_second_ventoy_stick_with_another_identity_is_ignored(self):
        self.disk("sda", bytes(16) + b"ELSE", {1: ("exfat", "Ventoy"), 2: ("vfat", "VTOYEFI")})
        self.put("sda1", "images/tup test.iso", self.image)
        calls = self.run_hook()
        self.assertEqual(len(self.commands(calls, "mount")), 1)
        self.assertIn(f"{self.base}/dev/sdb1 ", self.commands(calls, "mount")[0])
        self.assertEqual(self.reads, ["read sda", "read sdb"])

    def test_missing_wrong_size_linked_or_unattachable_image_is_unmounted_and_refused(self):
        target = self.base / "content/sdb1/images/tup test.iso"

        def linked():
            target.rename(target.with_name("real.iso"))
            target.symlink_to("real.iso")
        cases = {"no regular file": target.unlink, "symbolic links are not followed": linked,
                 "is not the 17 bytes Ventoy recorded": lambda: target.write_bytes(self.image + b"x"),
                 "cannot attach": (self.base / "losetup-fails").touch}
        for message, damage in cases.items():
            with self.subTest(case=message):
                shutil.rmtree(self.base / "content/sdb1")
                self.put("sdb1", "images/tup test.iso", self.image)
                damage()
                calls = self.run_hook()
                self.assertEqual(self.commands(calls, "umount"), [f"umount {self.base}/run/media"])
                self.assertEqual(len(self.commands(calls, "losetup")), int(message == "cannot attach"))
                self.assertIn(message, calls[-1])
                self.assertFalse(self.job.exists())
                self.assertEqual(list((self.base / "run/media").iterdir()), [])

    def test_failed_mount_is_refused_without_looking_for_the_image(self):
        (self.base / "mount-fails").touch()
        calls = self.run_hook()
        self.assertIn("cannot mount", calls[-1])
        self.assertEqual(self.commands(calls, "losetup") + self.commands(calls, "umount"), [])
        self.assertFalse(self.job.exists())


class HookSourceTests(unittest.TestCase):
    def test_hook_is_lf_only_and_never_asks_for_a_writable_mount_or_loop(self):
        raw = HOOK.read_bytes()
        self.assertNotIn(b"\r", raw)
        text = raw.decode("ascii")
        self.assertTrue(text.startswith("#!/bin/sh\n"))
        code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
        self.assertNotRegex(code, r"\brw\b|remount|mkfs|\bdd\b[^\n]*\bof=|blockdev|fsck")
        self.assertEqual(code.count("losetup"), 1)
        self.assertIn("losetup -r -f --show", code)
        for line in (line for line in code.splitlines() if "mount -n" in line):
            self.assertRegex(line, r"-o (ro,|\"\$opts,)")
        self.assertEqual({value.split(",")[0] for value in re.findall(r"\bopts=(\S+)", code)}, {"ro"})
        self.assertIn(ventoy.EFI_VARIABLE, code)
        self.assertIn(ventoy.SIGNATURE.hex(), code)


if __name__ == "__main__":
    unittest.main()
