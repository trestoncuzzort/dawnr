"""Refusal and real regular-file installation tests; never mount or touch disks."""
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import unittest
from unittest import mock

from tup.install import image
from tup.boot.inputs import Refusal, canonical, digest, file_hash, inventory, load_json


class CommandPolicyTests(unittest.TestCase):
    def test_observed_repart_dry_run_hazards_are_absent(self):
        plan = {"tools": {"files": {"repart": {"path": "/usr/bin/systemd-repart"}}},
                "source": "/private/source", "seed": "361bc694-54e1-4f3c-98aa-054d0747376c"}
        for apply in (False, True):
            command = image.command(plan, Path("/private/state"), 7, apply=apply)
            self.assertIn("--empty=require", command)
            self.assertIn("--split=no", command)
            self.assertIn("--offline=yes", command)
            self.assertIn("--dry-run=" + ("no" if apply else "yes"), command)
            self.assertEqual(command[-1], "/proc/self/fd/7")
            self.assertFalse(any(arg.startswith(("--size", "--image", "--root")) for arg in command))
            self.assertNotIn("--empty=create", command)

    def test_source_target_state_exclusion(self):
        for paths in (("/x/source", "/x/source/root/image", "/state"),
                      ("/image", "/source", "/source/state"), ("/x", "/x", "/state")):
            with self.assertRaisesRegex(Refusal, "disjoint"):
                image.disjoint(*map(Path, paths))

    def test_no_arbitrary_definition_strings(self):
        for sizes in (("64\nCopyBlocks=/dev/sda", 128), (True, 128), (1, 128), (64, 1)):
            with self.assertRaises(Refusal):
                image.definitions(*sizes)

    def test_same_filesystem_bind_mount_is_not_an_offline_source(self):
        line = "1 2 3:4 / /offline/source\\040tree rw - ext4 /dev/fixture rw\n"
        with mock.patch.object(Path, "read_text", return_value=line):
            with self.assertRaisesRegex(Refusal, "mounted"):
                image.unmounted(Path("/offline/source tree"))


@unittest.skipUnless(platform.system() == "Linux" and hasattr(os, "geteuid") and os.geteuid() == 0,
                     "real repart tests require the disposable Linux root builder")
class RealImageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            image.tool_identity()
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            raise unittest.SkipTest(str(error))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="tup-install-test-", dir=os.environ.get("TUP_INSTALL_TEST_ROOT"))
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / "source"
        (self.source / "root/etc").mkdir(parents=True)
        (self.source / "root/etc/payload").write_bytes(b"original\n")
        (self.source / "esp/EFI/BOOT").mkdir(parents=True)
        (self.source / "esp/EFI/BOOT/BOOTX64.EFI").write_bytes(b"explicit nonbootable fixture\n")
        self.target = self.base / "target.raw"
        self.blank(self.target)
        self.state = self.base / "state"

    @staticmethod
    def blank(path):
        with path.open("xb") as stream:
            stream.truncate(200 * image.MIB)

    def plan(self):
        result = image.plan_image(self.target, self.source, digest(canonical(inventory(self.source))), self.state)
        self.plan_hash = digest(canonical(result))
        return result

    def apply(self):
        return image.apply_image(self.state, self.plan_hash, "APPLY-IMAGE " + self.plan_hash)

    def test_real_plan_and_apply_then_replay_refusal(self):
        before = file_hash(self.target)
        self.plan()
        self.assertEqual(file_hash(self.target), before)
        receipt = self.apply()
        self.assertTrue(receipt["gpt_checked"])
        self.assertFalse(receipt["boot_tested"])
        self.assertFalse(receipt["root_contents_attested"])
        self.assertFalse(receipt["release_eligible"])
        after = file_hash(self.target)
        self.assertNotEqual(after, before)
        with self.assertRaisesRegex(Refusal, "replayed"):
            self.apply()
        self.assertEqual(file_hash(self.target), after)

    def test_declined_confirmation_has_zero_target_writes(self):
        self.plan()
        before = file_hash(self.target)
        with self.assertRaisesRegex(Refusal, "confirmation"):
            image.apply_image(self.state, self.plan_hash, "no")
        self.assertEqual(file_hash(self.target), before)
        self.assertFalse((self.state / "APPLYING.json").exists())

    def test_identical_bytes_on_replaced_inode_refuse(self):
        self.plan()
        self.target.rename(self.base / "old.raw")
        self.blank(self.target)
        with self.assertRaisesRegex(Refusal, "identity changed"):
            self.apply()
        self.assertFalse((self.state / "APPLYING.json").exists())

    def test_changed_target_bytes_refuse_before_writes(self):
        self.plan()
        with self.target.open("r+b") as stream:
            stream.seek(1024 * 1024)
            stream.write(b"changed")
        before = file_hash(self.target)
        with self.assertRaisesRegex(Refusal, "all-zero"):
            self.apply()
        self.assertEqual(file_hash(self.target), before)

    def test_changed_payload_with_restored_timestamp_refuses(self):
        self.plan()
        path = self.source / "root/etc/payload"
        old = path.stat()
        path.write_bytes(b"modified\n")
        os.utime(path, ns=(old.st_atime_ns, old.st_mtime_ns))
        with self.assertRaisesRegex(Refusal, "source changed"):
            self.apply()
        self.assertFalse((self.state / "APPLYING.json").exists())

    def test_wrong_reviewed_source_digest_refuses(self):
        with self.assertRaisesRegex(Refusal, "reviewed digest"):
            image.plan_image(self.target, self.source, "0" * 64, self.state)
        self.assertFalse(self.state.exists())

    def test_changed_plan_refuses(self):
        self.plan()
        with (self.state / "PLAN.json").open("ab") as stream:
            stream.write(b" ")
        with self.assertRaisesRegex(Refusal, "digest mismatch"):
            self.apply()

    def test_extra_drop_in_definitions_refuse(self):
        self.plan()
        (self.state / "definitions/10-esp.conf.d").mkdir()
        with self.assertRaisesRegex(Refusal, "definition paths"):
            self.apply()

    def test_even_resealed_plan_cannot_add_custom_copy_directives(self):
        self.plan()
        plan = load_json(self.state / "PLAN.json")
        plan["definitions"]["20-root.conf"] += "CopyFiles=/etc:/unexpected-host-copy\n"
        (self.state / "PLAN.json").write_bytes(canonical(plan))
        self.plan_hash = digest(canonical(plan))
        with self.assertRaisesRegex(Refusal, "unsupported partition directives"):
            self.apply()
        self.assertFalse((self.state / "APPLYING.json").exists())

    def test_changed_tools_refuse(self):
        self.plan()
        changed = image.tool_identity()
        changed["files"]["repart"]["sha256"] = "0" * 64
        with mock.patch.object(image, "tool_identity", return_value=changed):
            with self.assertRaisesRegex(Refusal, "tools changed"):
                self.apply()

    def test_concurrent_invocation_lock_refuses(self):
        self.plan()
        lock = self.target.with_name("." + self.target.name + ".tup-install.lock")
        lock.write_bytes(b"another installer")
        with self.assertRaises(FileExistsError):
            self.apply()
        self.assertEqual(lock.read_bytes(), b"another installer")
        self.assertFalse((self.state / "APPLYING.json").exists())

    def test_partial_write_and_interruption_cannot_resume(self):
        self.plan()
        def interrupt(command, state, name, fd):
            os.lseek(fd, 0, os.SEEK_SET)
            os.write(fd, b"interrupted fixture")
            raise KeyboardInterrupt("injected interruption after target mutation")
        with mock.patch.object(image, "execute", side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.apply()
        self.assertTrue((self.state / "APPLYING.json").exists())
        self.assertTrue((self.state / "FAILED.txt").exists())
        self.assertFalse((self.state / "RECEIPT.json").exists())
        before = file_hash(self.target)
        with self.assertRaisesRegex(Refusal, "replayed"):
            self.apply()
        self.assertEqual(file_hash(self.target), before)

    def test_ledger_full_before_apply_prevents_target_writes(self):
        self.plan()
        before = file_hash(self.target)
        with mock.patch.object(image, "write_json", side_effect=OSError("injected ENOSPC")):
            with mock.patch.object(image, "execute") as execute:
                with self.assertRaises(OSError):
                    self.apply()
                execute.assert_not_called()
        self.assertEqual(file_hash(self.target), before)
        self.assertFalse((self.state / "RECEIPT.json").exists())

    def test_completion_durability_failure_withdraws_receipt(self):
        self.plan()
        original = image.write_json
        def fail_receipt(path, value):
            original(path, value)
            if path.name == "RECEIPT.json":
                raise OSError("injected completion persistence failure")
        with mock.patch.object(image, "write_json", side_effect=fail_receipt):
            with self.assertRaises(OSError):
                self.apply()
        self.assertFalse((self.state / "RECEIPT.json").exists())
        self.assertTrue((self.state / "RECEIPT.uncertain.json").exists())
        self.assertTrue((self.state / "FAILED.txt").exists())

    def test_hardlinked_target_refuses(self):
        os.link(self.target, self.base / "alias.raw")
        with self.assertRaisesRegex(Refusal, "without hardlinks"):
            self.plan()

    def test_attached_loop_target_is_refused_without_attaching_devices(self):
        backing = self.base / "backing_file"
        backing.write_text(str(self.target))
        with image.target_file(self.target) as fd:
            with mock.patch.object(Path, "glob", return_value=[backing]):
                with self.assertRaisesRegex(Refusal, "loop device"):
                    image.target_identity(self.target, fd, blank=True)

    def test_nonregular_target_refuses_without_opening_it(self):
        fifo = self.base / "fifo"
        os.mkfifo(fifo)
        with self.assertRaisesRegex(Refusal, "non-regular"):
            with image.target_file(fifo):
                self.fail("a FIFO must not be opened")

    def test_symlink_input_path_refuses(self):
        link = self.base / "source-link"
        link.symlink_to(self.source)
        with self.assertRaisesRegex(Refusal, "symbolic links"):
            image.plan_image(self.target, link, "0" * 64, self.state)

    def test_fat_symlink_would_silently_disappear_so_refuse(self):
        (self.source / "esp/link").symlink_to("EFI/BOOT/BOOTX64.EFI")
        with self.assertRaisesRegex(Refusal, "unsupported type"):
            self.plan()

    def test_fat_case_collision_refuses(self):
        (self.source / "esp/efi").mkdir()
        with self.assertRaisesRegex(Refusal, "collision"):
            self.plan()


if __name__ == "__main__":
    unittest.main()
