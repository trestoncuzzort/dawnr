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
        config = "".join(f"CONFIG_{name}=y\n" for name in inputs.BUILTIN + inputs.AVAILABLE + ["MICROCODE", "CPU_SUP_AMD"])
        self.write(self.root / "boot" / ("config-" + self.release), config.encode())
        self.microcode = b"DMA\0fixture family 19h container"
        self.write(self.root / boot.MICROCODE, self.microcode)
        # What the fake lsinitrd finds in the fake initramfs.
        self.early = {"early_cpio": b"1\n", boot.EARLY_MICROCODE: self.microcode}
        self.listing = "".join(f"-rwxr-xr-x   1 root     root            1 Jan  1  1970 {name}\n" for name in (
            "init", "usr/bin/od", "usr/bin/sha256sum", "var/lib/dracut/hooks/cmdline/30-parse-dmsquash-live.sh",
            "var/lib/dracut/hooks/mount/01-mount-overlayfs.sh", "var/lib/dracut/hooks/pre-mount/01-prepare-overlayfs.sh",
            "var/lib/dracut/hooks/pre-udev/30-dmsquash-live-genrules.sh",
            # Programs dracut's init, dmsquash-live and the two hooks run.
            "usr/bin/cat", "usr/bin/dd", "usr/bin/mount", "usr/bin/readlink", "usr/bin/rmdir", "usr/bin/stat",
            "usr/bin/udevadm", "usr/bin/umount", "usr/sbin/blkid", "usr/sbin/losetup", "usr/sbin/switch_root"))
        self.listing += "lrwxrwxrwx   1 root     root           16 Jan  1  1970 usr/lib/systemd/systemd-udevd -> ../../bin/udevadm\n"
        self.modules = "dracut modules:\nbash\ndm\ndmsquash-live\noverlayfs\nrootfs-block\ninitqueue\nbase\n"
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
        for name in ("dracut-functions.sh", "dracut-logger.sh", "dracut-install", "skipcpio",
                     "modules.d/70dmsquash-live/module-setup.sh"):
            self.write(dracut / name, b"fixture\n")
        self.tools["support_trees"].append({"path": str(dracut), "sha256": inputs.tree_hash(dracut)})
        self.tools["dracut_base"] = str(dracut)
        font = prefix / "share/grub/themes/starfield/dejavu_12.pf2"
        self.write(font, b"fixture label font\n")
        self.tools["grub_label_font"] = {"path": str(font), "sha256": inputs.file_hash(font)}
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
        self.commands, self.environments = [], []

    def reseal(self):
        """The layer receipt and sealed inputs follow a deliberate change of the fixture root."""
        self.layer["root_tree_sha256"] = inputs.tree_hash(self.root)
        self.write_json(self.layer_path, self.layer)
        self.seal()

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
        self.environments.append(env)
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
                return self.modules
            if "--unpackearly" in command:
                for relative, raw in self.early.items():
                    self.write(Path(cwd) / relative, raw)
                return self.listing
            return (Path(cwd) / "overlay" / command[2]).read_text()
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

    def test_only_the_books_dbus_link_to_the_one_machine_identity_is_accepted(self):
        legacy = self.root / "var/lib/dbus/machine-id"
        self.write(legacy, b"")
        inputs.check_offline_root(self.root)  # An empty regular file carries no identity.
        legacy.write_bytes(b"0123456789abcdef0123456789abcdef\n")
        with self.assertRaisesRegex(inputs.Refusal, "identity"):
            inputs.check_offline_root(self.root)
        legacy.unlink()
        if os.name != "posix":
            self.skipTest("the link cases need Linux symlinks")
        # ch08 D-Bus: ln -sfv /etc/machine-id /var/lib/dbus
        legacy.symlink_to("/etc/machine-id")
        inputs.check_offline_root(self.root)
        for target in ("/etc/hostname", "../../../etc/machine-id", "/etc/machine-id/", "machine-id"):
            with self.subTest(target=target):
                legacy.unlink()
                legacy.symlink_to(target)
                with self.assertRaisesRegex(inputs.Refusal, "identity link"):
                    inputs.check_offline_root(self.root)
        legacy.unlink()
        # The identity file itself and the directory above the link stay link-free.
        (self.root / "etc/machine-id").unlink()
        (self.root / "etc/machine-id").symlink_to("/run/machine-id")
        with self.assertRaisesRegex(inputs.Refusal, "symbolic link"):
            inputs.check_offline_root(self.root)

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

    def test_missing_or_tampered_efi_label_font_refuses_before_tools(self):
        font = Path(self.tools["grub_label_font"]["path"])
        font.write_bytes(b"unreviewed font")
        with self.assertRaisesRegex(inputs.Refusal, "digest mismatch"):
            self.build()
        font.unlink()
        with self.assertRaises(FileNotFoundError):
            self.build()
        self.assertEqual(self.commands, [])

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
    def test_headless_grub_accepts_a_host_without_optional_fonts(self):
        # GRUB 2.14 always renders an EFI/Mac media label, even with --fonts=.
        # Use its authenticated bundled DejaVu font, not an implicit Unifont.
        def no_graphical_assets(command, **kwargs):
            if Path(command[0]).name == "grub-mkrescue":
                if "--fonts=" not in command:
                    raise inputs.Refusal("cannot open unicode.pf2")
                self.assertIn("--themes=", command)
                self.assertIn("--locales=", command)
                self.assertTrue(any(str(arg).startswith("--label-font=") for arg in command))
            return self.runner(command, **kwargs)
        self.build(no_graphical_assets)

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
        # The marker stops Ventoy's own hook injection; it is not evidence of a Ventoy boot.
        self.assertEqual((self.output / "iso/ventoy.dat").read_bytes(), boot.VENTOY_MARKER)
        self.assertEqual(receipt["artifacts"][os.path.join("iso", "ventoy.dat")], inputs.digest(boot.VENTOY_MARKER))
        self.assertIn("ventoy-unqualified", receipt["release_gates"])
        self.assertEqual(receipt["inputs"]["policy"]["ventoy"], "marker-and-efi-handoff-loop-hook-unbooted")
        self.assertEqual(receipt["inputs"]["microcode"], {"path": boot.MICROCODE, "sha256": inputs.digest(self.microcode)})
        self.assertEqual(receipt["early_microcode"], {boot.EARLY_MICROCODE: inputs.digest(self.microcode)})
        commands = "\n".join(" ".join(cmd) for cmd in self.commands)
        self.assertNotIn("grub-install", commands)
        self.assertNotIn("efibootmgr", commands)
        self.assertEqual(self.commands[0][2], "validate")
        grub = (self.output / "iso/boot/grub/grub.cfg").read_text()
        self.assertIn("root=live:LABEL=TUP_", grub)
        self.assertIn("console=ttyS0,115200n8", grub)
        self.assertNotRegex(grub, r"/dev/(?:sda|sr0|vda)")

    def test_live_command_line_uses_the_spellings_dracut_112_implements(self):
        label = "TUP_" + "A" * 24
        entries = [line.split() for line in boot.grub_config(label).splitlines() if line.lstrip().startswith("linux ")]
        self.assertEqual(len(entries), 2)
        for words in entries:
            for word in ("root=live:LABEL=" + label, "ro", "rd.live.image", "rd.live.dir=LiveOS", "rd.live.squashimg=squashfs.img",
                         "rd.overlay=tmpfs:size=512M,nr_inodes=100000", "rd.live.ram=0", "rd.retry=90", "rd.shell"):
                self.assertIn(word, words)
            # dmsquash-live-root.sh reads "tmpfs" as a device to search for a persistent
            # overlay, finds none and then waits for Enter; a headless boot would hang there.
            self.assertIn("rd.live.overlay.nouserconfirmprompt", words)
            self.assertEqual([word for word in words if word.startswith(("rd.overlay", "rd.live.overlay"))],
                             ["rd.overlay=tmpfs:size=512M,nr_inodes=100000", "rd.live.overlay.nouserconfirmprompt"])
            self.assertFalse({word.split("=")[0] for word in words} & {"rd.live.overlay", "rd.live.overlay.overlayfs",
                                                                       "rd.live.overlay.size", "iso-scan/filename"})

    def test_a_desktop_boots_to_its_screen_and_a_qemu_test_machine_to_its_serial_port(self):
        grub = boot.grub_config("TUP_" + "A" * 24)
        screen, serial = [line.split() for line in grub.splitlines() if line.lstrip().startswith("linux ")]
        # The last console= is /dev/console, where systemd and the emergency shell write.
        self.assertEqual([word for word in screen if word.startswith("console=")], ["console=ttyS0,115200n8", "console=tty0"])
        self.assertEqual([word for word in serial if word.startswith("console=")], ["console=tty0", "console=ttyS0,115200n8"])
        # Shell tracing at 115200 baud would slow a desktop boot; only the test entry has it.
        self.assertNotIn("rd.debug", screen)
        self.assertNotIn("systemd.log_target=console", screen)
        self.assertIn("rd.debug", serial)
        lines = [line.strip() for line in grub.splitlines()]
        self.assertEqual(lines[:2], ["set default=0", "set timeout=3"])
        # Noise on an absent UART must never reach GRUB as a key press.
        self.assertIn("terminal_input console", lines)
        self.assertNotIn("serial", " ".join(line for line in lines if line.startswith("terminal_input")))
        self.assertIn("terminal_output console serial", lines)
        selection = lines[lines.index("insmod smbios"):lines.index("fi") + 1]
        self.assertEqual(selection, ["insmod smbios", "smbios --type 1 --get-string 4 --set tup_system_manufacturer",
                                     'if [ "$tup_system_manufacturer" = "QEMU" ]; then', "set default=1", "fi"])
        self.assertLess(lines.index("fi"), next(i for i, line in enumerate(lines) if line.startswith("menuentry")))
        self.assertEqual(sum(line.startswith("menuentry ") for line in lines), 2)

    def test_dracut_runs_its_own_init_with_host_files_spelled_through_the_sysroot(self):
        self.build()
        dracut = next(command for command in self.commands if Path(command[0]).name == "dracut")
        option = lambda name: dracut[dracut.index(name) + 1]
        root = str(self.root.resolve())
        self.assertEqual((option("--sysroot"), option("--modules")), (root, boot.MODULES))
        # LFS builds systemd without systemd-sysusers, which dracut 112's systemd-journald module requires.
        self.assertNotIn("systemd", option("--modules"))
        self.assertEqual(option("--install").split(), ["/usr/bin/sha256sum", "/usr/bin/od"])
        self.assertIn("--early-microcode", dracut)
        self.assertNotIn("--no-early-microcode", dracut)
        self.assertEqual(option("--fwdir"), os.path.join(root, "usr", "lib", "firmware"))
        # Found by the first packaging of a real root: without --kmoddir dracut 112
        # asks the builder's own /lib/modules whether "overlay" exists and refuses.
        # The directory is the one check_kernel() inventories, and its last two
        # parents must read lib/modules (dracut.sh checks the text).
        self.assertEqual(option("--kmoddir"), os.path.join(root, "usr", "lib", "modules", self.release))
        self.assertEqual(Path(option("--kmoddir")).parts[-3:-1], ("lib", "modules"))
        includes = {dracut[index + 2]: dracut[index + 1] for index, arg in enumerate(dracut) if arg == "--include"}
        self.assertEqual(set(includes), {"/etc/tup-live/root.sha256", *("/" + target for target in boot.HOOKS.values())})
        for target, source in includes.items():
            # Dracut 112 would look up any other spelling of a host file below the sysroot.
            self.assertTrue(source.startswith(root + os.sep))
            self.assertTrue(os.path.normpath(source).endswith(os.path.normpath("overlay" + target)))
            self.assertFalse(os.path.normpath(source).startswith(root + os.sep))
        for index, command in enumerate(self.commands):
            if Path(command[0]).name in {"dracut", "lsinitrd"}:
                base = self.environments[index]["dracutbasedir"]
                self.assertTrue(base.startswith(root + os.sep))
                self.assertEqual(os.path.normpath(base), os.path.normpath(self.tools["dracut_base"]))
        for name, target in boot.HOOKS.items():
            self.assertEqual((self.output / "overlay" / target).read_bytes(), (boot.HERE / name).read_bytes())

    def test_export_without_exactly_the_family_19h_microcode_refuses_before_any_tool(self):
        path = self.root / boot.MICROCODE
        config = self.root / "boot" / ("config-" + self.release)
        cases = {"missing": path.unlink,
                 "second container": lambda: self.write(path.with_name("microcode_amd_fam17h.bin"), self.microcode),
                 "intel": lambda: self.write(self.root / "usr/lib/firmware/intel-ucode/06-55-04", b"fixture"),
                 "not a container": lambda: path.write_bytes(b"fixture"),
                 "kernel": lambda: config.write_text(config.read_text().replace("CONFIG_MICROCODE=y\n", ""))}
        original = config.read_bytes()
        for name, damage in cases.items():
            with self.subTest(case=name):
                damage()
                self.layer["root_tree_sha256"] = inputs.tree_hash(self.root)
                self.write_json(self.layer_path, self.layer)
                for attempt in (self.seal, self.build):
                    with self.assertRaisesRegex(inputs.Refusal, "(?i)microcode"):
                        attempt()
                self.assertEqual(self.commands, [])
                self.assertFalse(self.output.exists())
                for extra in (path.parent.parent / "intel-ucode", path.parent):
                    if extra.exists():
                        for child in extra.iterdir():
                            child.unlink()
                        extra.rmdir()
                self.write(path, self.microcode)
                config.write_bytes(original)

    def test_initramfs_without_exactly_the_staged_early_microcode_refuses(self):
        # Dracut drops early microcode with a warning when it disagrees about the kernel configuration.
        for name, early in (("no early cpio", {}), ("marker only", {"early_cpio": b"1\n"}),
                            ("other bytes", {"early_cpio": b"1\n", boot.EARLY_MICROCODE: b"DMA\0other"}),
                            ("intel as well", {**self.early, "kernel/x86/microcode/GenuineIntel.bin": b"fixture"})):
            with self.subTest(case=name):
                self.early = early
                with self.assertRaisesRegex(inputs.Refusal, "early microcode"):
                    self.build()
                self.assertFalse(self.output.exists())

    def test_initramfs_without_the_ventoy_hook_or_dracuts_own_scripts_refuses(self):
        def unhooked(command, **kwargs):
            if Path(command[0]).name == "lsinitrd" and boot.HOOKS["ventoy-live.sh"] in command:
                return "# some other hook\n"
            return self.runner(command, **kwargs)
        with self.assertRaisesRegex(inputs.Refusal, "ventoy-live.sh"):
            self.build(unhooked)
        # Dracut 112 exits 0 after "dracut-install: ERROR: installing" its own framework scripts.
        complete = self.listing
        for line in complete.splitlines(keepends=True):
            with self.subTest(missing=line.split(" 1970 ")[1].strip()):
                self.listing = complete.replace(line, "")
                with self.assertRaisesRegex(inputs.Refusal, "live scripts"):
                    self.build()
        self.listing = complete.replace(" init\n", " init -> usr/lib/systemd/systemd\n")
        with self.assertRaisesRegex(inputs.Refusal, "live scripts"):
            self.build()
        # The udev daemon may be systemd's link to udevadm or a plain file, never a link elsewhere.
        self.listing = complete.replace("systemd-udevd -> ../../bin/udevadm\n", "systemd-udevd\n")
        self.build()
        self.listing = complete.replace("systemd-udevd -> ../../bin/udevadm\n", "systemd-udevd -> ../../bin/true\n")
        self.output = self.output.with_name("refused-link")
        with self.assertRaisesRegex(inputs.Refusal, "systemd-udevd"):
            self.build()
        self.assertFalse(self.output.exists())

    def test_dracut_install_errors_refuse_although_dracut_exits_zero(self):
        # Measured with dracut 112: a failed dracut-install of a script, program
        # or library is logged and the run still exits 0.
        option = lambda command, name: command[command.index(name) + 1]
        cases = {"output": ("dracut[E]: FAILED: /x/dracut-install -D /x/initramfs -a stat\n", None),
                 "install": ("dracut-install: ERROR: installing '/usr/bin/stat'\n", None),
                 "log": ("", "I: *** Including module: base ***\nE: FAILED: /x/dracut-install -D /x/initramfs -a stat\n")}
        for name, (printed, logged) in cases.items():
            with self.subTest(where=name):
                def noisy(command, **kwargs):
                    result = self.runner(command, **kwargs)
                    if Path(command[0]).name != "dracut":
                        return result
                    if logged is not None:
                        Path(option([str(x) for x in command], "--logfile")).write_text(logged, encoding="utf-8")
                    return printed
                self.output = self.output.with_name("dracut-error-" + name)
                with self.assertRaisesRegex(inputs.Refusal, "install error"):
                    self.build(noisy)
                self.assertFalse((self.output / "ARTIFACT.json").exists())
        # Informational lines that only mention the words do not refuse.
        def quiet(command, **kwargs):
            result = self.runner(command, **kwargs)
            if Path(command[0]).name == "dracut":
                Path(option([str(x) for x in command], "--logfile")).write_text(
                    "I: *** Including module: base ***\nW: no error here: E: is not at a line start\n", encoding="utf-8")
            return result
        self.output = self.output.with_name("dracut-quiet")
        self.build(quiet)

    def test_systemd_initramfs_without_the_dracut_hook_runner_refuses(self):
        # Measured with dracut 112: "systemd systemd-initrd" alone installs the hooks but nothing that sources them.
        self.modules += "systemd\nsystemd-initrd\n"
        with self.assertRaisesRegex(inputs.Refusal, "live modules"):
            self.build()
        self.assertFalse(self.output.exists())
        self.modules += "dracut-systemd\n"
        self.build()

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
