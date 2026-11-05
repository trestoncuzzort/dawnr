"""Boot refusal/orchestration fixtures. No real build tool or mount is executed."""
from __future__ import annotations

import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tup.boot import assemble as boot
from tup.boot import inputs


class BootFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        if os.name == "nt":
            # Production refuses Windows. Fixture-only adapter; Linux runs the
            # actual directory fsync and supplies the durability evidence.
            for name in ("sync_directory", "sync_tree"):
                patcher = mock.patch.object(boot, name)
                patcher.start()
                self.addCleanup(patcher.stop)
        self.base = Path(self.temp.name)
        self.root = self.base / "export"
        self.root.mkdir()
        self.release = "6.18.60-tup-test"
        elf = b"\x7fELF\x02\x01" + bytes(12) + b"\x3e\x00"
        for name in ("usr/bin/bash", "usr/lib/systemd/systemd", "usr/sbin/dmsetup"):
            self.write(self.root / name, elf)
        self.write(self.root / "etc/shadow", b"root:!:0:0:99999:7:::\n")
        self.write(self.root / "etc/os-release", b'ID=tup\nNAME="TUP"\nVERSION_ID="fixture"\n')
        self.write(self.root / "etc/machine-id", b"")
        config = "".join(f"CONFIG_{name}=y\n" for name in inputs.BUILTIN + inputs.AVAILABLE)
        self.write(self.root / "boot" / ("config-" + self.release), config.encode())
        image = bytearray(1024)
        image[0x202:0x206] = b"HdrS"
        struct.pack_into("<H", image, 0x206, 0x20C)
        struct.pack_into("<H", image, 0x236, 1)
        struct.pack_into("<H", image, 0x20E, 0x80)
        text = (self.release + " fixture\0").encode()
        image[0x280:0x280 + len(text)] = text
        self.write(self.root / "boot" / ("vmlinuz-" + self.release), image)
        for name in ("modules.dep", "modules.alias", "modules.builtin", "modules.builtin.modinfo", "modules.order"):
            self.write(self.root / "usr/lib/modules" / self.release / name, b"")
        self.workspace = self.base / "native"
        native_inputs = self.workspace / "root/tup-build/BUILD-INPUTS.json"
        self.write(native_inputs, b'{"schema":"fixture-native-inputs"}\n')
        self.core_script = self.base / "core-validator.py"
        self.write(self.core_script, b"raise SystemExit('fixture must not execute')\n")
        self.core_spec = self.base / "core-validator.json"
        self.core = {"schema": "tup.boot-core-validator.v1", "script": str(self.core_script),
                     "script_sha256": inputs.file_hash(self.core_script),
                     "inputs_sha256": inputs.file_hash(native_inputs),
                     "args": ["validate", "--workspace", str(self.workspace), "--through", "ch08",
                              "--profile", "lfs-13.1-systemd",
                              "--source-cache", str(self.base / "cache"), "--source-lock", str(self.base / "sources.json"),
                              "--lock-sha256", "0" * 64]}
        self.write_json(self.core_spec, self.core)
        prefix = self.base / "host-tools"
        binary = prefix / "bin"
        self.tools = {"schema": "tup.boot-tools.v1", "versions": {"dracut": "112", "grub": "2.14"},
                      "commands": {}, "path": [str(binary)], "support_trees": [],
                      "provenance": "fixture only; no source authentication or executable tools"}
        for name in boot.TOOLS:
            path = binary / name
            self.write(path, b"fixture not executable\n")
            self.tools["commands"][name] = {"path": str(path), "sha256": inputs.file_hash(path)}
        grub = prefix / "lib/grub/x86_64-efi"
        for name in ("modinfo.sh", "normal.mod", "linux.mod", "iso9660.mod", "search_label.mod"):
            self.write(grub / name, b"fixture\n")
        self.tools["support_trees"] = [{"path": str(grub), "sha256": inputs.tree_hash(grub)}]
        self.tools["grub_modules"] = str(grub)
        dracut = prefix / "lib/dracut"
        for name in ("dracut-functions.sh", "dracut-logger.sh", "dracut-install", "modules.d/70dmsquash-live/module-setup.sh"):
            self.write(dracut / name, b"fixture\n")
        self.tools["support_trees"].append({"path": str(dracut), "sha256": inputs.tree_hash(dracut)})
        self.tools["dracut_base"] = str(dracut)
        self.tools_path = self.base / "tools.json"
        self.write_json(self.tools_path, self.tools)
        self.tools_hash = inputs.file_hash(self.tools_path)
        self.layer_path = self.base / "layer.json"
        self.layer = {"schema": "tup.boot-layer.v1", "architecture": "x86_64", "status": "complete",
                      "core_inputs_sha256": self.core["inputs_sha256"], "source_lock_sha256": "1" * 64,
                      "recipe_sha256": "2" * 64, "root_tree_sha256": inputs.tree_hash(self.root)}
        self.write_json(self.layer_path, self.layer)
        self.expected = self.base / "expected.json"
        self.seal()
        self.output = self.base / "artifacts"
        self.commands = []

    def write(self, path, raw):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)

    def write_json(self, path, value):
        self.write(path, inputs.canonical(value))

    def seal(self):
        self.write_json(self.expected, boot.describe(self.root, self.release, self.core_spec, self.layer_path,
                                                    self.tools_path, self.tools_hash))

    def runner(self, command, *, cwd, env, log):
        command = [str(x) for x in command]
        self.commands.append(command)
        with open(log, "ab") as stream:
            stream.write(inputs.canonical(command))
        name = Path(command[0]).name
        if len(command) > 2 and command[1] == str(self.core_script):
            st = (self.workspace / "root").stat()
            core = {"schema": "tup-native-core-completion-v1", "scope": "ch05-ch08-core-only",
                    "profile": "lfs-13.1-systemd", "inputs_sha256": self.core["inputs_sha256"],
                    "stages": {name: {"receipt_sha256": "3" * 64, "log_sha256": "4" * 64}
                               for name in ("ch05", "ch06", "ownership", "ch07-inner", "ch08")},
                    "root_identity": {"device": st.st_dev, "inode": st.st_ino},
                    "source_lock_sha256": "0" * 64, "source_lock_purpose": "disposable-build-test",
                    "source_release_eligible": False, "release_eligible": False,
                    "release_gates": ["H55 fixture gate"], "advisory_review_sha256": "7" * 64,
                    "driver_receipts_sha256": "5" * 64, "driver_state_sha256": "6" * 64}
            self.write_json(self.workspace / "state/CORE-COMPLETION.json", core)
        elif name == "mksquashfs":
            Path(command[2]).write_bytes(b"hsqs fixture squashfs")
        elif name == "dracut":
            Path(command[-1]).write_bytes(b"fixture initramfs")
        elif name == "lsinitrd":
            if "-m" in command:
                return "dracut modules:\nbash\nsystemd\ndmsquash-live\noverlayfs\n"
            if command[2].endswith("01-tup-live-verify.sh"):
                return (boot.HERE / "verify-live.sh").read_text()
            return (cwd / "overlay/etc/tup-live/root.sha256").read_text()
        elif name == "grub-mkrescue":
            path = next(x.split("=", 1)[1] for x in command if x.startswith("--output="))
            Path(path).write_bytes(b"fixture ISO")
        elif name == "xorriso":
            return "El Torito boot img : 1 UEFI y none 0x0000 0x00 2880 123\n"
        return ""

    def build(self, runner=None):
        with mock.patch.object(boot.platform, "system", return_value="Linux"), \
             mock.patch.object(boot.platform, "machine", return_value="x86_64"), \
             mock.patch.object(boot, "check_unmounted"):
            return boot.assemble(self.root, self.expected, self.core_spec, self.layer_path,
                                 self.tools_path, self.tools_hash, self.output, runner=runner or self.runner)


class InputRefusalTests(BootFixture):
    def test_wrong_kernel_release_or_architecture_refuses(self):
        kernel = self.root / "boot" / ("vmlinuz-" + self.release)
        data = bytearray(kernel.read_bytes())
        struct.pack_into("<H", data, 0x236, 0)
        kernel.write_bytes(data)
        with self.assertRaisesRegex(inputs.Refusal, "bzImage"):
            inputs.check_kernel(self.root, self.release)

    def test_kernel_version_must_match_module_directory(self):
        kernel = self.root / "boot" / ("vmlinuz-" + self.release)
        kernel.write_bytes(kernel.read_bytes().replace(b"6.18.60", b"6.18.59"))
        with self.assertRaisesRegex(inputs.Refusal, "header release"):
            inputs.check_kernel(self.root, self.release)

    def test_missing_storage_option_refuses(self):
        config = self.root / "boot" / ("config-" + self.release)
        config.write_text(config.read_text().replace("CONFIG_BLK_DEV_NVME=y", "# CONFIG_BLK_DEV_NVME is not set"))
        with self.assertRaisesRegex(inputs.Refusal, "BLK_DEV_NVME"):
            inputs.check_kernel(self.root, self.release)

    def test_missing_modules_metadata_refuses(self):
        (self.root / "usr/lib/modules" / self.release / "modules.dep").unlink()
        with self.assertRaises(OSError):
            inputs.check_kernel(self.root, self.release)

    def test_changed_root_refuses_before_invoking_any_tool(self):
        self.write(self.root / "usr/bin/new", b"unreceipted file")
        with self.assertRaisesRegex(inputs.Refusal, "receipt"):
            self.build()
        self.assertEqual(self.commands, [])
        self.assertFalse(self.output.exists())

    def test_host_key_cloned_identity_and_default_password_refuse(self):
        for relative, value, diagnostic in (("etc/machine-id", b"cloned", "identity"),
                ("etc/ssh/ssh_host_ed25519_key", b"private fixture", "private SSH"),
                ("etc/shadow", b"root::0:0:99999:7:::\n", "locked")):
            with self.subTest(relative=relative):
                path = self.root / relative
                previous = path.read_bytes() if path.exists() else None
                self.write(path, value)
                with self.assertRaisesRegex(inputs.Refusal, diagnostic):
                    inputs.check_offline_root(self.root)
                if previous is None:
                    path.unlink()
                else:
                    path.write_bytes(previous)

    def test_populated_runtime_directory_is_not_silently_excluded(self):
        self.write(self.root / "proc/cpuinfo", b"unwanted mounted content")
        with self.assertRaisesRegex(inputs.Refusal, "proc"):
            inputs.check_offline_root(self.root)

    def test_live_fstab_rejects_historical_fixed_disk(self):
        self.write(self.root / "etc/fstab", b"/dev/vda1 / ext4 defaults 0 1\n")
        with self.assertRaisesRegex(inputs.Refusal, "fstab"):
            inputs.check_offline_root(self.root)

    def test_tool_or_support_tree_tamper_refuses(self):
        path = Path(self.tools["commands"]["dracut"]["path"])
        original = path.read_bytes()
        path.write_bytes(b"tampered")
        with self.assertRaisesRegex(inputs.Refusal, "digest mismatch"):
            self.build()
        self.assertEqual(self.commands, [])
        path.write_bytes(original)
        (Path(self.tools["grub_modules"]) / "normal.mod").write_bytes(b"tampered EFI module")
        with self.assertRaisesRegex(inputs.Refusal, "support-tree"):
            self.build()
        self.assertEqual(self.commands, [])

    def test_changed_mode_is_not_hidden_by_identical_file_bytes(self):
        path = self.root / "usr/bin/bash"
        previous = inputs.file_hash(path)
        path.chmod(0o444)
        self.assertEqual(inputs.file_hash(path), previous)
        with self.assertRaisesRegex(inputs.Refusal, "receipt"):
            self.build()

    @unittest.skipUnless(hasattr(os, "setxattr"), "Linux xattr fixture")
    def test_changed_xattr_is_not_hidden_by_identical_file_bytes(self):
        path = self.root / "usr/bin/bash"
        os.setxattr(path, "user.tup.fixture", b"changed")
        with self.assertRaisesRegex(inputs.Refusal, "receipt"):
            self.build()

    def test_core_validator_cannot_run_build_help_or_duplicate_partial_stage(self):
        original = self.core["args"]
        for args in (["build", *original[1:]], [*original, "--help", "x"], [*original, "--through", "ch06"]):
            self.core["args"] = args
            self.write_json(self.core_spec, self.core)
            with self.assertRaisesRegex(inputs.Refusal, "complete ch08"):
                boot.check_core_spec(self.core_spec)

    def test_different_native_core_is_not_authorized_by_receipt(self):
        self.layer["core_inputs_sha256"] = "9" * 64
        self.write_json(self.layer_path, self.layer)
        with self.assertRaisesRegex(inputs.Refusal, "different native core"):
            self.seal()

    def test_duplicate_json_keys_refuse(self):
        path = self.base / "duplicate.json"
        path.write_text('{"status":"failed","status":"complete"}')
        with self.assertRaisesRegex(inputs.Refusal, "duplicate"):
            inputs.load_json(path)

    def test_nested_mount_is_refused_without_touching_it(self):
        nested = self.root / "proc"
        mountinfo = f"42 1 0:7 / {nested} rw - tmpfs tmpfs rw\n"
        with mock.patch.object(Path, "read_text", return_value=mountinfo):
            with self.assertRaisesRegex(inputs.Refusal, "unmounted offline"):
                boot.check_unmounted(self.root)

    def test_critical_symlink_never_reads_host_binary(self):
        path = self.root / "usr/sbin/dmsetup"
        path.unlink()
        try:
            path.symlink_to(self.core_script)
        except OSError:
            self.skipTest("host cannot create symlink; Linux fixture required")
        with self.assertRaisesRegex(inputs.Refusal, "symbolic link"):
            inputs.check_offline_root(self.root)


class PackagingTests(BootFixture):
    def test_real_failed_child_keeps_output_and_propagates_status(self):
        log = self.base / "child.log"
        with self.assertRaisesRegex(inputs.Refusal, r"failed \(7\)"):
            boot.execute([sys.executable, "-c", "print('fixture failure evidence'); raise SystemExit(7)"],
                         cwd=self.base, env=os.environ.copy(), log=log)
        self.assertIn(b"fixture failure evidence", log.read_bytes())
        result = boot.execute([sys.executable, "-c", "print('fresh output')"],
                              cwd=self.base, env=os.environ.copy(), log=log)
        self.assertEqual(result.strip(), "fresh output")

    def test_pipeline_packages_but_never_claims_boot_success(self):
        receipt = self.build()
        self.assertEqual(receipt["status"], "packaged-unbooted")
        self.assertFalse(receipt["boot_tested"])
        self.assertFalse(receipt["ventoy_tested"])
        self.assertFalse(receipt["release_eligible"])
        self.assertIn("H55 fixture gate", receipt["release_gates"])
        self.assertFalse(receipt["core_source_policy"]["source_release_eligible"])
        self.assertEqual(inputs.load_json(self.output / "ARTIFACT.json"), receipt)
        self.assertFalse((self.output / "iso/ventoy.dat").exists())
        commands = "\n".join(" ".join(cmd) for cmd in self.commands)
        self.assertNotIn("grub-install", commands)
        self.assertNotIn("efibootmgr", commands)
        self.assertEqual(self.commands[0][2], "validate")
        grub = (self.output / "iso/boot/grub/grub.cfg").read_text()
        self.assertIn("root=live:LABEL=TUP_", grub)
        self.assertIn("console=ttyS0,115200n8", grub)
        self.assertNotRegex(grub, r"/dev/(?:sda|sr0|vda)")

    def test_failed_native_validation_stops_before_image_tools(self):
        def fail(*args, **kwargs):
            raise inputs.Refusal("fixture native validation failed")
        with self.assertRaisesRegex(inputs.Refusal, "native validation"):
            self.build(fail)
        self.assertFalse(self.output.exists())
        self.assertEqual(len(list(self.base.glob(".tup-boot-*/FAILED.txt"))), 1)
        self.assertEqual(list(self.base.glob(".tup-boot-*/ARTIFACT.json")), [])

    def test_zero_exit_with_no_new_completion_receipt_refuses(self):
        # A stale marker plus a no-op validator cannot authorize packaging.
        self.runner(["python", str(self.core_script), "validate"], cwd=self.base, env={}, log=self.base / "test.log")
        def stale(command, **kwargs):
            if len(command) > 2 and str(command[1]) == str(self.core_script):
                return ""
            return self.runner(command, **kwargs)
        with self.assertRaisesRegex(inputs.Refusal, "did not rewrite"):
            self.build(stale)
        self.assertFalse(self.output.exists())

    def test_each_failed_packaging_stage_prevents_publication(self):
        for tool in ("mksquashfs", "dracut", "grub-mkrescue", "xorriso"):
            with self.subTest(tool=tool):
                def fail(command, **kwargs):
                    if Path(command[0]).name == tool:
                        raise inputs.Refusal("fixture " + tool + " failed")
                    return self.runner(command, **kwargs)
                with self.assertRaisesRegex(inputs.Refusal, "failed"):
                    self.build(fail)
                self.assertFalse(self.output.exists())

    def test_missing_initramfs_live_module_or_digest_refuses(self):
        for option, response in (("-m", "systemd\n"), ("-f", "wrong digest\n")):
            with self.subTest(option=option):
                def incorrect(command, **kwargs):
                    if Path(command[0]).name == "lsinitrd" and option in command:
                        return response
                    return self.runner(command, **kwargs)
                with self.assertRaisesRegex(inputs.Refusal, "initramfs"):
                    self.build(incorrect)
                self.assertFalse(self.output.exists())

    def test_bios_only_iso_does_not_pass_uefi_inspection(self):
        def bios(command, **kwargs):
            if Path(command[0]).name == "xorriso":
                return "El Torito boot img : 1 BIOS y none\n"
            return self.runner(command, **kwargs)
        with self.assertRaisesRegex(inputs.Refusal, "UEFI"):
            self.build(bios)
        self.assertFalse(self.output.exists())

    def test_input_mutation_during_build_prevents_publication(self):
        def mutate(command, **kwargs):
            result = self.runner(command, **kwargs)
            if Path(command[0]).name == "grub-mkrescue":
                self.write(self.root / "usr/bin/new", b"late mutation")
            return result
        with self.assertRaisesRegex(inputs.Refusal, "receipt"):
            self.build(mutate)
        self.assertFalse(self.output.exists())

    def test_existing_or_nested_output_is_refused(self):
        self.output.mkdir()
        with self.assertRaisesRegex(inputs.Refusal, "new directory"):
            self.build()
        self.output = self.root / "bad-output"
        with self.assertRaisesRegex(inputs.Refusal, "disjoint"):
            self.build()
        self.assertEqual(self.commands, [])

    def test_failed_durability_does_not_publish_a_completion_receipt(self):
        with mock.patch.object(boot, "sync_tree", side_effect=OSError("fixture fsync failed")):
            with self.assertRaisesRegex(OSError, "fsync"):
                self.build()
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.base.glob(".tup-boot-*/ARTIFACT.json")), [])
        self.assertEqual(len(list(self.base.glob(".tup-boot-*/ARTIFACT.uncertain.json"))), 1)

    def test_failed_publish_directory_fsync_marks_output_uncertain(self):
        original = boot.sync_directory
        def fail_parent(path):
            if Path(path) == self.base:
                raise OSError("fixture parent fsync failed")
            return original(path)
        with mock.patch.object(boot, "sync_directory", side_effect=fail_parent):
            with self.assertRaisesRegex(OSError, "parent fsync"):
                self.build()
        self.assertTrue((self.output / "FAILED.txt").exists())
        self.assertFalse((self.output / "ARTIFACT.json").exists())
        self.assertTrue((self.output / "ARTIFACT.uncertain.json").exists())

    @unittest.skipUnless(os.name == "posix", "Linux shell hook fixture")
    def test_bad_live_digest_cannot_reach_switch_root_even_if_die_returns(self):
        code = '''sha256sum() { return 1; }
die() { printf 'refused\\n'; return 0; }
info() { printf 'incorrectly accepted\\n'; }
. "$1"
printf 'incorrectly continued\\n'
'''
        result = subprocess.run(["/bin/sh", "-c", code, "fixture", str(boot.HERE / "verify-live.sh")],
                                capture_output=True, text=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "refused\n")

    def test_host_environment_injection_is_not_inherited(self):
        with mock.patch.dict(os.environ, {"DRACUT_EXTRA_ARGS": "--hostonly", "LD_PRELOAD": "/tmp/evil.so"}):
            env = boot.environment(self.tools, self.base)
        self.assertNotIn("DRACUT_EXTRA_ARGS", env)
        self.assertNotIn("LD_PRELOAD", env)


if __name__ == "__main__":
    unittest.main()
