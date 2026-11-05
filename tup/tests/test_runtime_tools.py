"""External VM test tooling: refusals, and the SSH verdict rules against a scripted client.

No VM, loop device, mount or network listener is used here. The scripted client
stands in for ssh and sftp so that every pass/fail rule is exercised, including
the ones a healthy guest never triggers. It is not evidence about a real guest.
"""
import ast
import base64
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import unittest

RUNTIME = Path(__file__).resolve().parents[1] / "boot/tests-runtime"
sys.path.insert(0, str(RUNTIME))  # ventoy-image.py imports its sibling loop_guard.


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, RUNTIME / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


remote_check = load("runtime_remote_check", "remote_check.py")
loop_guard = load("loop_guard", "loop_guard.py")
ventoy_image = load("runtime_ventoy_image", "ventoy-image.py")
Refusal = remote_check.Refusal
BASH = os.environ.get("TUP_TEST_BASH") or shutil.which("bash")
LINUX = platform.system() == "Linux"
REAL_TOOLS = LINUX and all(os.access(path, os.X_OK) for path in remote_check.TOOLS.values())
PORT = 22022


# Not QEMU and not a guest: it prints a login prompt on the serial file and
# answers the QMP power button, so uefi.sh's control flow can run end to end.
STAND_IN_EMULATOR = r'''#!/usr/bin/python3
import json, os, socket, sys
serial = next(arg for arg in sys.argv if arg.startswith("file:"))[5:]
qmp = sys.argv[sys.argv.index("-qmp") + 1][5:].split(",")[0]
with open(serial, "a") as log:
    log.write("Welcome to the stand-in\ntup login: ")
server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
server.bind(qmp)
server.listen(1)
while True:
    link, _ = server.accept()
    with link, link.makefile("rwb") as stream:
        stream.write(b'{"QMP": {"version": {}, "capabilities": []}}\r\n')
        stream.flush()
        for line in stream:
            command = json.loads(line)["execute"]
            stream.write(b'{"return": {}}\r\n')
            stream.flush()
            if command == "system_powerdown":
                with open(serial, "a") as log:
                    log.write("\n[  OK  ] Reached target Power-Off.\n[   99.0] reboot: Power down\n")
                if os.environ.get("TUP_STAND_IN_TAMPER"):  # The media is rebuilt in place while the guest runs.
                    with open(os.environ["TUP_STAND_IN_TAMPER"], "ab") as media:
                        media.write(b"x")
                sys.exit(0)
'''


def shell_path(path):
    text = Path(path).resolve().as_posix()
    return "/" + text[0].lower() + text[2:] if os.name == "nt" else text


def key_blob(seed):
    return base64.b64encode(struct.pack(">I", 11) + b"ssh-ed25519" + struct.pack(">I", 32) + bytes([seed]) * 32).decode()


class Guest:
    """A scripted ssh/sftp pair: the client and server behaviour the verdict rules depend on."""

    def __init__(self, remote, now):
        self.remote, self.now, self.calls = remote, now, []
        self.down_for, self.sudo, self.sudo_denied, self.state = 0, True, False, "running"
        self.methods, self.root_allowed, self.root_reset, self.any_key = "publickey", False, False, False
        self.host_blob, self.ignore_host_key, self.corrupt, self.timeout_on = key_blob(7), False, False, None
        self.address = "10.0.2.15"
        self.cmdline = "BOOT_IMAGE=/boot/vmlinuz root=live:LABEL=TUP quiet console=ttyS0,115200n8"

    def __call__(self, argv, timeout, env=None):
        self.calls.append(argv)
        self.now[0] += 1

        def result(code, out=b"", err=b"", late=False):
            return {"returncode": code, "stdout": out, "stderr": err, "timed_out": late, "seconds": 1.0}
        options = dict(argv[index + 1].split("=", 1) for index, part in enumerate(argv) if part == "-o")
        if self.down_for > 0:
            self.down_for -= 1
            return result(255, err=b"kex_exchange_identification: Connection closed by remote host\n")
        known = Path(options["UserKnownHostsFile"])
        entry = f"[127.0.0.1]:{options['Port']} ssh-ed25519 {self.host_blob}\n".encode()
        if not known.exists():
            if options["StrictHostKeyChecking"] != "accept-new":
                return result(255, err=b"Host key verification failed.\n")
            known.write_bytes(entry)
        elif known.read_bytes() != entry and not self.ignore_host_key:
            return result(255, err=b"Host key verification failed.\n")
        if Path(argv[0]).name == "sftp":
            quoted = re.findall(r'"([^"]+)"', Path(argv[argv.index("-b") + 1]).read_text())
            data = Path(quoted[0]).read_bytes()
            Path(quoted[3]).write_bytes(data[:-1] + bytes([data[-1] ^ 1]) if self.corrupt else data)
            return result(0)
        user, key = argv[argv.index("-l") + 1], Path(argv[argv.index("-i") + 1]).name
        refused = result(255, err=f"{user}@127.0.0.1: Permission denied ({self.methods}).\n".encode())
        if options["PreferredAuthentications"].startswith("password"):
            if "password" in self.methods:  # A real client would now run the askpass program.
                (self.remote / "askpass.asked").write_bytes(b"")
            return refused
        if user == "root":
            if self.root_reset:
                return result(255, err=b"Connection reset by 127.0.0.1 port 22022\n")
            if not self.root_allowed:
                return refused
        elif user != "owner" or (key != "owner_key" and not self.any_key):
            return refused
        command = argv[-1].removeprefix(remote_check.GUEST_PATH)
        if command == self.timeout_on:
            return result(None, late=True)
        sudo = (1, b"", b"sudo: a password is required\n") if self.sudo_denied else None
        replies = {
            "echo TUP-SSH-OK": (0, b"TUP-SSH-OK\n"),
            "uname -a": (0, b"Linux tup 6.18.60-tup #1 SMP PREEMPT_DYNAMIC x86_64 GNU/Linux\n"),
            "id": (0, b"uid=1000(owner) gid=1000(owner) groups=1000(owner)\n"),
            "cat /etc/os-release": (0, b'NAME="TUP"\nID=tup\nVERSION_ID="13.1"\n'),
            "ip -brief address": (0, f"lo UNKNOWN 127.0.0.1/8\neth0 UP {self.address}/24\n".encode()),
            "cat /proc/cmdline": (0, self.cmdline.encode() + b"\n"),
            "systemctl is-system-running --wait": (0 if self.state == "running" else 1, self.state.encode() + b"\n"),
            "systemctl list-units --failed --no-legend --no-pager; systemctl list-jobs --no-pager":
                (0, b"example.service loaded failed failed\n"),
            "command -v sudo": (0, b"/usr/bin/sudo\n") if self.sudo else (1, b""),
            "sudo -n /usr/sbin/nft list ruleset": sudo or (0, b"table inet tup_owner {\n}\n"),
            "sudo -n systemctl poweroff": sudo or (0, b""),
        }
        return result(*replies[command])


class ScriptedRun(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="tup-runtime-")
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name) / "run"
        self.remote = self.output / "remote"
        self.remote.mkdir(parents=True)
        for name, seed in (("owner_key", 1), ("unenrolled_key", 2)):
            (self.remote / name).write_bytes(b"fixture private half\n")
            (self.remote / (name + ".pub")).write_bytes(f"ssh-ed25519 {key_blob(seed)}\n".encode())
        self.now = [0.0]
        self.guest = Guest(self.remote, self.now)
        self.powerdowns = []

    def verify(self, wait=60):
        def sleep(seconds):
            self.now[0] += seconds
        report = remote_check.verify(self.output, PORT, "owner", wait, run=self.guest, clock=lambda: self.now[0],
                                     sleep=sleep, powerdown=self.powerdowns.append)
        return report, {item["name"]: item for item in report["checks"]}

    def conclude(self, verdict="BOOTED", verify_ran=1, powered_off=1, logged=1, qemu_exit=0, inputs=1,
                 kind="tup-iso-ssh"):
        return remote_check.conclude(self.output, kind, "0" * 64, 2048, 2, PORT, verdict, verify_ran,
                                     powered_off, logged, qemu_exit, 9, 180, inputs)

    def failed(self, checks):
        return sorted(name for name, item in checks.items() if item["status"] == "fail")


class RemoteVerdictTests(ScriptedRun):
    def test_healthy_guest_with_sudo_passes_every_named_check(self):
        report, checks = self.verify()
        self.assertEqual(self.failed(checks), [])
        self.assertEqual([item["name"] for item in report["checks"]], list(remote_check.SSH_CHECKS))
        self.assertEqual(report["poweroff_method"], "owner-systemctl-poweroff")
        self.assertEqual(self.powerdowns, [])
        self.assertEqual(report["host_key"]["type"], "ssh-ed25519")
        self.assertTrue((self.output / checks["guest_uname"]["stdout_file"]).read_bytes().startswith(b"Linux tup"))
        result = self.conclude()
        self.assertTrue(result["passed"])
        self.assertEqual(result, json.loads((self.output / "RESULT.json").read_bytes()))
        scope = result["scope"]
        self.assertEqual((scope["accelerator"], scope["kvm"], scope["hardware_tested"], scope["physical_boot_tested"],
                          scope["release_eligible"], scope["remote_access_tested"]),
                         ("tcg", False, False, False, False, True))
        self.assertFalse((self.remote / "owner_key").exists() or (self.remote / "unenrolled_key").exists())
        self.assertTrue((self.remote / "owner_key.pub").exists())

    def test_every_client_call_is_strict_and_self_contained(self):
        self.verify()
        for argv in self.guest.calls:
            joined = " ".join(argv)
            self.assertEqual(argv[1:3], ["-F", "none"])
            for required in ("IdentitiesOnly=yes", "IdentityAgent=none", "GlobalKnownHostsFile=/dev/null",
                             "UpdateHostKeys=no", "ControlMaster=no", "ForwardAgent=no", f"Port={PORT}"):
                self.assertIn(required, joined)
            self.assertNotIn("StrictHostKeyChecking=no", joined)
        first = " ".join(self.guest.calls[0])
        self.assertIn("StrictHostKeyChecking=accept-new", first)
        self.assertTrue(all("StrictHostKeyChecking=yes" in " ".join(argv) for argv in self.guest.calls[1:]))

    def test_guest_without_sudo_is_powered_down_through_qmp_and_says_what_was_not_inspected(self):
        self.guest.sudo = False
        report, checks = self.verify()
        self.assertEqual(self.failed(checks), [])
        self.assertEqual(checks["nft_ruleset_as_root"]["status"], "not-applicable")
        self.assertIn("not inspected", checks["nft_ruleset_as_root"]["detail"])
        self.assertEqual((report["poweroff_method"], self.powerdowns), ("qmp-system_powerdown", [self.output / "qmp.sock"]))
        self.assertTrue(self.conclude()["passed"])

    def test_late_guest_is_waited_for_and_the_attempts_are_counted(self):
        self.guest.down_for = 3
        _, checks = self.verify()
        self.assertEqual(self.failed(checks), [])
        self.assertIn("4 attempt(s)", checks["owner_key_login"]["detail"])

    def test_guest_that_never_answers_fails_every_check_and_skips_none(self):
        self.guest.down_for = 10**6
        report, checks = self.verify(wait=30)
        self.assertEqual(self.failed(checks), sorted(remote_check.SSH_CHECKS[:-1]))
        self.assertIn("not attempted", checks["sftp_round_trip_sha256"]["detail"])
        self.assertEqual(report["poweroff_method"], "qmp-system_powerdown")
        self.assertLessEqual(self.now[0], 30 + 60)
        result = self.conclude()
        self.assertFalse(result["passed"])
        self.assertIn("root_login_refused", result["failed_checks"])

    def test_each_weakened_guest_fails_its_own_check(self):
        cases = (
            ({"root_allowed": True}, "root_login_refused"),
            ({"root_reset": True}, "root_login_refused"),  # A dropped connection is not a denial.
            ({"methods": "publickey,password"}, "password_authentication_refused"),
            ({"methods": "publickey,keyboard-interactive"}, "password_authentication_refused"),
            ({"any_key": True}, "unenrolled_key_refused"),
            ({"corrupt": True}, "sftp_round_trip_sha256"),
            ({"state": "degraded"}, "guest_system_running"),
            ({"timeout_on": "uname -a"}, "guest_uname"),
            ({"address": "192.0.2.15"}, "guest_ip_address"),
            ({"ignore_host_key": True}, "changed_host_key_refused"),
            ({"sudo_denied": True}, "nft_ruleset_as_root"),
            ({"cmdline": "BOOT_IMAGE=/boot/vmlinuz rdinit=/vtoy/vtoy quiet"}, "guest_kernel_cmdline"),
            ({"cmdline": ""}, "guest_kernel_cmdline"),
        )
        for change, expected in cases:
            with self.subTest(change=change):
                self.setUp()
                for name, value in change.items():
                    setattr(self.guest, name, value)
                _, checks = self.verify()
                self.assertIn(expected, self.failed(checks))
                result = self.conclude()
                self.assertFalse(result["passed"])
                self.assertIn(expected, result["verdict"])

    def test_the_booted_command_line_is_recorded_and_a_ventoy_fallback_boot_never_passes(self):
        _, checks = self.verify()
        self.assertIn("console=ttyS0", checks["guest_kernel_cmdline"]["detail"])
        self.assertEqual(checks["guest_kernel_cmdline"]["status"], "pass")
        saved = (self.output / checks["guest_kernel_cmdline"]["stdout_file"]).read_bytes()
        self.assertIn(b"root=live:LABEL=TUP", saved)
        self.setUp()
        self.guest.cmdline = "BOOT_IMAGE=/boot/vmlinuz rdinit=/vtoy/vtoy quiet"
        _, checks = self.verify()
        self.assertEqual(self.failed(checks), ["guest_kernel_cmdline"])
        self.assertIn("rdinit=/vtoy/vtoy quiet", checks["guest_kernel_cmdline"]["detail"])  # The evidence stays.
        for kind in ("tup-iso-ssh", "ventoy-tup-ssh"):
            with self.subTest(kind=kind):
                (self.output / "RESULT.json").unlink(missing_ok=True)
                result = self.conclude(kind=kind)
                self.assertEqual(result["failed_checks"], ["guest_kernel_cmdline"])

    def test_result_cannot_say_verified_when_the_wrapper_rejects_the_run_inputs(self):
        self.verify()
        result = self.conclude(inputs=0)
        self.assertEqual((result["passed"], result["failed_checks"]), (False, ["host_inputs_unchanged"]))
        self.assertTrue(result["verdict"].startswith("TUP REMOTE ACCESS FAILED"))
        self.assertNotIn("VERIFIED", (self.output / "RESULT.json").read_text())
        checks = {item["name"]: item for item in result["checks"]}
        self.assertIn("host-recheck.txt", checks["host_inputs_unchanged"]["detail"])
        (self.output / "RESULT.json").unlink()
        self.assertTrue(self.conclude(inputs=1)["passed"])

    def test_scope_names_what_each_kind_does_not_establish_about_its_enrollment(self):
        self.verify()
        direct = self.conclude()["scope"]
        (self.output / "RESULT.json").unlink()
        ventoy = self.conclude(kind="ventoy-tup-ssh")["scope"]
        self.assertIn("whole-device FAT filesystem without a partition table", " ".join(direct["not_established"]))
        self.assertIn("MBR, one FAT32 partition", direct["enrollment"])
        self.assertNotIn("whole-device", " ".join(ventoy["not_established"]))
        self.assertIn("Ventoy data partition", ventoy["enrollment"])
        self.assertIn("Ventoy2Disk.exe", " ".join(ventoy["not_established"]))

    def test_degraded_state_keeps_the_failed_unit_listing(self):
        self.guest.state = "degraded"
        _, checks = self.verify()
        self.assertIn("degraded", checks["guest_system_running"]["detail"])
        listing = re.search(r"unit detail in (\S+)", checks["guest_system_running"]["detail"]).group(1)
        self.assertIn(b"example.service", (self.output / listing).read_bytes())

    def test_sudo_refusing_poweroff_is_not_a_poweroff_request(self):
        self.guest.sudo_denied = True
        report, checks = self.verify()
        self.assertFalse(report["poweroff_requested"])
        self.assertEqual(checks["poweroff_request"]["status"], "fail")

    def test_host_key_change_between_connections_stops_the_client(self):
        original = self.guest.__call__

        def changing(argv, timeout, env=None):
            if len(self.guest.calls) == 3:
                self.guest.host_blob = key_blob(9)
            return original(argv, timeout, env)
        report = remote_check.verify(self.output, PORT, "owner", 60, run=changing, clock=lambda: self.now[0],
                                     sleep=lambda seconds: None, powerdown=self.powerdowns.append)
        failed = [item["name"] for item in report["checks"] if item["status"] == "fail"]
        self.assertIn("second_connection_same_known_hosts", failed)
        self.assertIn("sftp_round_trip_sha256", failed)

    def test_conclusion_requires_the_serial_verdict_the_power_off_and_every_check(self):
        self.verify()
        for change, expected in (({"verdict": "TIMEOUT (600s, no login prompt)"}, "serial_boot_verdict"),
                                 ({"powered_off": 0}, "guest_powered_off"),
                                 ({"logged": 0}, "guest_powered_off"),  # A reset also ends QEMU under -no-reboot.
                                 ({"qemu_exit": 1}, "guest_powered_off")):
            with self.subTest(change=change):
                (self.output / "RESULT.json").unlink(missing_ok=True)
                result = self.conclude(**change)
                self.assertEqual(result["failed_checks"], [expected])
        (self.output / "RESULT.json").unlink()
        report = json.loads((self.remote / "CHECKS.json").read_bytes())
        report["checks"] = [item for item in report["checks"] if item["name"] != "unenrolled_key_refused"]
        report["checks"].append({"name": "invented_check", "status": "pass", "detail": ""})
        (self.remote / "CHECKS.json").write_bytes(remote_check.canonical(report))
        self.assertEqual(self.conclude()["failed_checks"], ["invented_check", "unenrolled_key_refused"])

    def test_conclusion_without_a_verification_fails_all_and_never_overwrites(self):
        result = self.conclude(verify_ran=0, powered_off=0, logged=0, qemu_exit=-1)
        self.assertEqual(result["failed_checks"], sorted(remote_check.REQUIRED[1:-1]))
        self.assertFalse(result["scope"]["remote_access_tested"])
        with self.assertRaisesRegex(Refusal, "never replaced"):
            self.conclude()
        self.assertEqual(json.loads((self.output / "RESULT.json").read_bytes()), result)

    def test_second_verification_in_one_run_and_bad_bounds_refuse(self):
        self.verify()
        with self.assertRaises(FileExistsError):
            self.verify()
        for port, owner, wait in ((22, "owner", 60), (PORT, "root", 60), (PORT, "owner", 5), (PORT, "owner", "60")):
            with self.subTest(port=port, owner=owner, wait=wait), self.assertRaises(ValueError):
                remote_check.verify(self.output, port, owner, wait, run=self.guest)

    def test_command_line_reports_refusal_and_failure_separately(self):
        self.verify()
        common = ["conclude", "--output", str(self.output), "--port", str(PORT), "--kind", "tup-iso-ssh",
                  "--media-sha256", "0" * 64, "--memory-mib", "2048", "--cpus", "2", "--boot-verdict", "BOOTED",
                  "--verify-ran", "1", "--power-down-logged", "1", "--poweroff-seconds", "9", "--poweroff-budget", "180", "--inputs-unchanged", "1"]
        script = [sys.executable, str(RUNTIME / "remote_check.py")]
        done = subprocess.run(script + common + ["--powered-off", "0", "--qemu-exit=-1"], capture_output=True, text=True)
        self.assertEqual((done.returncode, done.stdout.strip()),
                         (1, "TUP REMOTE ACCESS FAILED (external VM, TCG): guest_powered_off"))
        done = subprocess.run(script + common + ["--powered-off", "1", "--qemu-exit=0"], capture_output=True, text=True)
        self.assertEqual(done.returncode, 2)  # RESULT.json exists; a result is never replaced.
        self.assertIn("remote check refused", done.stderr)


class EnrollmentTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="tup-runtime-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name).resolve()
        self.output = self.directory / "run"
        self.output.mkdir(mode=0o700)

    def test_account_port_and_missing_tool_refuse_before_anything_is_written(self):
        absent = {name: str(self.directory / "absent" / name) for name in remote_check.TOOLS}
        for owner, port, tools in (("root", PORT, None), ("Owner", PORT, None), ("a b", PORT, None), ("sshd", PORT, None),
                                   ("owner", 22, None), ("owner", 65536, None), ("owner", "2222", None),
                                   ("owner", PORT, absent), ("owner", PORT, {"ssh": "ssh"})):
            with self.subTest(owner=owner, port=port, tools=tools), self.assertRaises(ValueError):
                remote_check.prepare(self.output, owner, port, tools or remote_check.TOOLS)
        self.assertEqual(list(self.output.iterdir()), [])

    def read_back(self, image, path):
        """Read through the partition's byte offset, a route that does not use the drive definition prepare() wrote."""
        return remote_check.execute([remote_check.TOOLS["mtools"], "-c", "mtype", "-i",
                                     f"{image}@@{remote_check.PART_START * 512}", "::" + path], 30,
                                    remote_check.host_environment())

    def ventoy_keys(self, image_sha256, owner=None):
        """What ventoy-image.py --generate-test-key leaves beside an image, made with the real ssh-keygen."""
        folder = self.directory / "enroll-keys"
        folder.mkdir(mode=0o700)
        keys, fingerprints = remote_check.generate_key(remote_check.TOOLS, remote_check.execute, folder / "owner_key")
        (folder / "ENROLL.json").write_bytes(remote_check.canonical({
            "schema": "tup.runtime-ventoy-enroll.v1", "image_sha256": image_sha256, "owner": owner,
            "authorized_keys_sha256": remote_check.digest(keys), "owner_key_fingerprint": fingerprints[0]}))
        return folder, fingerprints[0]

    @unittest.skipUnless(REAL_TOOLS, "needs the Linux test host's ssh-keygen and mtools")
    def test_ventoy_run_takes_the_owner_key_from_the_image_and_builds_no_enrollment_volume(self):
        folder, fingerprint = self.ventoy_keys("a" * 64)
        summary = remote_check.prepare(self.output, None, PORT, keys_from=folder, media_sha256="a" * 64)
        remote = self.output / "remote"
        self.assertEqual(summary["owner_key_fingerprint"], fingerprint)
        self.assertNotEqual(summary["unenrolled_key_fingerprint"], fingerprint)
        self.assertFalse((remote / "enroll.img").exists())
        self.assertNotIn("image_sha256", summary)
        self.assertIn("Ventoy data partition", summary["enrollment"])
        self.assertEqual((remote / "owner_key").stat().st_mode & 0o777, 0o600)
        self.assertEqual((remote / "owner_key").read_bytes(), (folder / "owner_key").read_bytes())

    @unittest.skipUnless(REAL_TOOLS, "needs the Linux test host's ssh-keygen and mtools")
    def test_ventoy_keys_for_another_image_owner_or_key_refuse_and_nothing_is_adopted(self):
        folder, _ = self.ventoy_keys("a" * 64, owner="mac-owner")
        record = (folder / "ENROLL.json").read_bytes()
        cases = (("b" * 64, "mac-owner", "not made for this Ventoy image"),
                 ("a" * 64, None, "enrolls owner 'mac-owner'"),
                 ("a" * 64, "someone", "enrolls owner 'mac-owner'"))
        for sha, owner, message in cases:
            with self.subTest(sha=sha[:1], owner=owner), self.assertRaisesRegex(Refusal, message):
                remote_check.prepare(self.output, owner, PORT, keys_from=folder, media_sha256=sha)
            shutil.rmtree(self.output / "remote", ignore_errors=True)
        (folder / "ENROLL.json").write_bytes(record.replace(b'"authorized_keys_sha256":"', b'"authorized_keys_sha256":"0'))
        with self.assertRaisesRegex(Refusal, "differs from the one written"):
            remote_check.prepare(self.output, "mac-owner", PORT, keys_from=folder, media_sha256="a" * 64)
        shutil.rmtree(self.output / "remote", ignore_errors=True)
        (folder / "ENROLL.json").write_bytes(record)
        (folder / "owner_key").chmod(0o640)
        with self.assertRaisesRegex(Refusal, "not a private regular file"):
            remote_check.prepare(self.output, "mac-owner", PORT, keys_from=folder, media_sha256="a" * 64)
        shutil.rmtree(self.output / "remote", ignore_errors=True)
        (folder / "owner_key").chmod(0o600)
        folder.chmod(0o755)
        with self.assertRaisesRegex(Refusal, "private, real directory"):
            remote_check.prepare(self.output, "mac-owner", PORT, keys_from=folder, media_sha256="a" * 64)

    def test_enrollment_image_must_be_one_mbr_partition_of_labelled_fat32(self):
        start = remote_check.PART_START
        sector = bytearray(512)
        sector[11:13], sector[36:40] = (512).to_bytes(2, "little"), (1000).to_bytes(4, "little")
        sector[71:82], sector[82:90], sector[510:512] = b"TUP-ENROLL ", b"FAT32   ", b"\x55\xaa"
        mbr = bytearray(512)
        mbr[446 + 4] = remote_check.FAT32_LBA
        mbr[446 + 8:446 + 12] = start.to_bytes(4, "little")
        mbr[446 + 12:446 + 16] = (remote_check.DISK_SECTORS - start).to_bytes(4, "little")
        mbr[510:512] = b"\x55\xaa"
        image = self.directory / "image"

        def write(first, second):
            image.write_bytes(bytes(first) + bytes(start * 512 - 512) + bytes(second))
        write(mbr, sector)
        remote_check.check_enrollment_image(image)
        second_entry = bytearray(mbr)
        second_entry[446 + 16 + 4] = 0x83
        for name, first, second in (
                ("whole-device FAT without a partition table", sector, bytes(512)),
                ("FAT12 label as the old fixture had it", mbr, bytes(sector[:54]) + b"TUP-ENROLL FAT12   " + bytes(sector[73:])),
                ("a different label", mbr, bytes(sector[:71]) + b"OTHER      " + bytes(sector[82:])),
                ("FAT16", mbr, bytes(sector[:82]) + b"FAT16   " + bytes(sector[90:])),
                ("not FAT32 LBA", bytes(mbr[:450]) + b"\x83" + bytes(mbr[451:]), sector),
                ("a second partition", second_entry, sector),
                ("starting elsewhere", bytes(mbr[:454]) + (63).to_bytes(4, "little") + bytes(mbr[458:]), sector),
                ("no MBR signature", bytes(mbr[:510]) + b"\0\0", sector),
                ("no boot-sector signature", mbr, bytes(sector[:510]) + b"\0\0")):
            with self.subTest(name), self.assertRaises(Refusal):
                write(first, second)
                remote_check.check_enrollment_image(image)

    @unittest.skipUnless(REAL_TOOLS, "needs the Linux test host's ssh-keygen and mtools")
    def test_unsafe_output_arguments_refuse(self):
        spaced = self.directory / "with space"
        spaced.mkdir(mode=0o700)
        shared = self.directory / "shared"
        shared.mkdir(mode=0o755)
        shared.chmod(0o755)
        regular = self.directory / "file"
        regular.write_bytes(b"")
        link = self.directory / "link"
        link.symlink_to(self.output)
        taken = self.directory / "taken"
        (taken / "remote").mkdir(parents=True, mode=0o700)
        taken.chmod(0o700)
        for output in (spaced, shared, regular, link, taken, Path("/dev/null"), Path("/dev/loop0"),
                       self.directory / "absent", Path("relative"), self.directory / ("x" * 90)):
            with self.subTest(output=output), self.assertRaises((Refusal, OSError)):
                remote_check.prepare(output, None, PORT)
        self.assertEqual(sorted(path.name for path in taken.iterdir()), ["remote"])
        self.assertEqual(list((taken / "remote").iterdir()), [])

    @unittest.skipUnless(REAL_TOOLS, "needs the Linux test host's ssh-keygen and mtools")
    def test_real_tools_build_a_read_only_labelled_image_the_guest_can_read(self):
        summary = remote_check.prepare(self.output, None, PORT)
        remote = self.output / "remote"
        image = remote / "enroll.img"
        self.assertEqual((summary["owner"], summary["owner_file_written"], summary["files"]),
                         ("owner", False, ["tup-enroll/authorized_keys"]))
        self.assertEqual(image.stat().st_mode & 0o777, 0o400)
        self.assertEqual(image.stat().st_size, remote_check.DISK_SECTORS * 512)  # 128 MiB: FAT32 needs the clusters.
        self.assertEqual((remote / "owner_key").stat().st_mode & 0o777, 0o600)
        remote_check.check_enrollment_image(image)
        listed = self.read_back(image, "tup-enroll/authorized_keys")
        key = (remote / "owner_key.pub").read_bytes().split()
        self.assertEqual(listed["stdout"], b" ".join(key[:2]) + b"\n")
        self.assertNotEqual(summary["owner_key_fingerprint"], summary["unenrolled_key_fingerprint"])
        self.assertEqual(json.loads((remote / "PREPARED.json").read_bytes()), summary)
        with self.assertRaisesRegex(Refusal, "already holds"):
            remote_check.prepare(self.output, None, PORT)

    @unittest.skipUnless(REAL_TOOLS, "needs the Linux test host's ssh-keygen and mtools")
    def test_named_owner_is_written_and_a_busy_port_refuses(self):
        summary = remote_check.prepare(self.output, "mac-owner", PORT)
        self.assertEqual(summary["files"], ["tup-enroll/authorized_keys", "tup-enroll/owner"])
        self.assertEqual(self.read_back(self.output / "remote/enroll.img", "tup-enroll/owner")["stdout"], b"mac-owner\n")
        second = self.directory / "second"
        second.mkdir(mode=0o700)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as held:  # Bound only; nothing listens.
            held.bind(("127.0.0.1", 0))
            with self.assertRaisesRegex(Refusal, "not free"):
                remote_check.prepare(second, None, held.getsockname()[1])

    @unittest.skipUnless(LINUX and hasattr(socket, "AF_UNIX"), "QMP uses a Unix socket")
    def test_qmp_is_used_for_one_powerdown_and_an_error_reply_refuses(self):
        for reply in ({"return": {}}, {"error": {"class": "GenericError", "desc": "fixture"}}):
            path = self.directory / ("qmp-%d.sock" % ("error" in reply))
            received = []
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.addCleanup(server.close)
            server.bind(str(path))
            server.listen(1)

            def serve():
                link, _ = server.accept()
                with link, link.makefile("rwb") as stream:
                    stream.write(b'{"QMP": {"version": {}, "capabilities": []}}\r\n')
                    stream.flush()
                    for answer in ({"return": {}}, reply):
                        line = stream.readline()
                        if not line:
                            return
                        received.append(json.loads(line)["execute"])
                        stream.write(b'{"event": "FIXTURE", "timestamp": {}}\r\n' + json.dumps(answer).encode() + b"\r\n")
                        stream.flush()
            thread = threading.Thread(target=serve, daemon=True)
            thread.start()
            with self.subTest(reply=reply):
                if "error" in reply:
                    with self.assertRaisesRegex(Refusal, "refused system_powerdown"):
                        remote_check.qmp_powerdown(path, timeout=5)
                else:
                    remote_check.qmp_powerdown(path, timeout=5)
                thread.join(5)
                self.assertEqual(received, ["qmp_capabilities", "system_powerdown"])
        with self.assertRaises(OSError):
            remote_check.qmp_powerdown(self.directory / "absent.sock", timeout=1)


class VentoyFixtureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="tup-runtime-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name).resolve()
        self.iso = self.directory / "probe.iso"
        self.iso.write_bytes(b"not an image; only its identity is read\n")
        self.digest = remote_check.file_hash(self.iso)

    def build(self, **change):
        values = {"cache": self.directory / "cache", "iso": self.iso, "expected": self.digest,
                  "output": self.directory / "image", "prefix": self.directory / "prefix", "size_gib": 1,
                  "workspace": self.directory}
        values.update(change)
        return ventoy_image.build(**values)

    def test_unsafe_arguments_refuse_before_any_privileged_step(self):
        existing = self.directory / "existing"
        existing.mkdir()
        cases = [({"size_gib": 0}, "1-16 GiB"), ({"size_gib": 17}, "1-16 GiB"), ({"size_gib": "1"}, "1-16 GiB"),
                 ({"output": existing}, "new directory"), ({"iso": self.directory}, "regular file"),
                 ({"expected": "0" * 64}, "digest mismatch"), ({"expected": "sha256"}, "SHA256")]
        if os.name != "nt":
            link = self.directory / "link.iso"
            link.symlink_to(self.iso)
            cases += [({"iso": Path("/dev/null")}, "regular file"), ({"iso": link}, "regular file")]
        for change, message in cases:
            with self.subTest(change=change), self.assertRaisesRegex(ventoy_image.Refusal, message):
                self.build(**change)
        self.assertFalse((self.directory / "image").exists())
        self.assertEqual(list(existing.iterdir()), [])

    @unittest.skipUnless(LINUX and hasattr(os, "geteuid") and os.geteuid() == 0, "needs Linux root for ownership rules")
    def test_workspace_must_be_named_private_and_contain_the_output(self):
        self.directory.chmod(0o755)
        self.assertEqual(loop_guard.workspace_root(self.directory), self.directory)
        loose = self.directory / "loose"
        loose.mkdir()
        loose.chmod(0o777)
        link = self.directory / "link"
        link.symlink_to(self.directory)
        for workspace in ("relative", "/", loose, link, self.directory / "absent", self.iso):
            with self.subTest(workspace=workspace), self.assertRaises((ValueError, OSError)):
                loop_guard.workspace_root(workspace)
        elsewhere = tempfile.TemporaryDirectory(prefix="tup-runtime-")
        self.addCleanup(elsewhere.cleanup)
        with self.assertRaisesRegex(ventoy_image.Refusal, "under the named workspace"):
            self.build(output=Path(elsewhere.name).resolve() / "image")
        self.assertFalse((Path(elsewhere.name) / "image").exists())

    def test_loop_guard_accepts_only_a_whole_loop_device_name(self):
        for device in ("/dev/sda", "/dev/nvme0n1", "/dev/loop0p1", "/dev/loop", "loop0", "/dev/loop0/../sda"):
            with self.subTest(device=device), self.assertRaisesRegex(ValueError, "whole loop device"):
                loop_guard.check(device, self.iso, [0, 0, 0], self.directory)

    def test_enrollment_and_name_arguments_refuse_before_any_privileged_step(self):
        keys = self.directory / "keys.pub"
        keys.write_bytes(f"ssh-ed25519 {key_blob(3)}\n".encode())
        bad = self.directory / "bad name.iso"
        bad.write_bytes(self.iso.read_bytes())
        for change, message in (({"authorized_keys": keys, "generate_key": True}, "not both"),
                                ({"owner": "mac-owner"}, "only written together"),
                                ({"iso": bad}, "file name must be")):
            with self.subTest(change=change), self.assertRaisesRegex(ventoy_image.Refusal, message):
                self.build(**change)
        keys.write_bytes(b"ssh-rsa AAAA\n")
        with self.assertRaises(ValueError):
            self.build(authorized_keys=keys)
        keys.write_bytes(f"ssh-ed25519 {key_blob(3)}\n".encode())
        with self.assertRaises(ValueError):
            self.build(authorized_keys=keys, owner="root")
        self.assertFalse((self.directory / "image").exists())

    def test_only_the_one_mount_the_program_made_is_tolerated_on_the_loop(self):
        mounts = ("/dev/loop7p1 /run/x/mnt exfat rw 0 0\n/dev/loop70p1 /mnt/other ext4 rw 0 0\n"
                  "/dev/sda1 /boot ext4 rw 0 0\n/dev/loop3p1 /mnt/else ext4 rw 0 0\n")
        ours = ("/dev/loop7p1", "/run/x/mnt")
        self.assertEqual(len(loop_guard.foreign_mounts("/dev/loop7", mounts)), 2)  # No mount is expected yet.
        self.assertEqual(loop_guard.foreign_mounts("/dev/loop7", mounts, ours), ["/dev/loop70p1 /mnt/other ext4 rw 0 0"])
        self.assertEqual(loop_guard.foreign_mounts("/dev/loop7", "/dev/loop7p1 /elsewhere exfat rw 0 0\n", ours),
                         ["/dev/loop7p1 /elsewhere exfat rw 0 0"])  # Same device, other mountpoint.
        self.assertEqual(loop_guard.foreign_mounts("/dev/loop3", mounts, ours), ["/dev/loop3p1 /mnt/else ext4 rw 0 0"])

    def test_extents_are_runs_of_consecutive_physical_blocks_and_holes_are_counted(self):
        for blocks, expected in (([5, 6, 7], (1, 0)), ([5, 6, 0, 7], (2, 1)), ([5, 7], (2, 0)),
                                 ([0, 0], (0, 2)), ([], (0, 0)), ([9, 10, 0, 0, 20, 21], (2, 2))):
            with self.subTest(blocks=blocks):
                self.assertEqual(ventoy_image.extents(blocks), expected)

    def test_the_stick_carries_the_key_at_the_enrollment_path_and_the_iso_at_the_top_level(self):
        keys = f"ssh-ed25519 {key_blob(5)}\n".encode()
        self.assertEqual(sorted(ventoy_image.stick_files("tup.iso")), ["ventoy/ventoy.json"])
        files = ventoy_image.stick_files("tup.iso", keys)
        self.assertEqual(sorted(files), ["tup-enroll/authorized_keys", "ventoy/ventoy.json"])
        self.assertEqual(files["tup-enroll/authorized_keys"], keys)
        files = ventoy_image.stick_files("tup.iso", keys, "mac-owner")
        self.assertEqual(sorted(files), ["tup-enroll/authorized_keys", "tup-enroll/owner", "ventoy/ventoy.json"])
        self.assertEqual(files["tup-enroll/owner"], b"mac-owner\n")
        self.assertNotIn("tup.iso", files)  # The ISO is copied by populate() to the top level, never into this map.
        control = json.loads(files["ventoy/ventoy.json"])["control"]
        self.assertIn({"VTOY_DEFAULT_IMAGE": "/tup.iso"}, control)  # The leading slash is the top level.
        self.assertIn({"VTOY_MENU_TIMEOUT": "2"}, control)
        self.assertEqual(json.loads(ventoy_image.stick_files("a-b.iso")["ventoy/ventoy.json"])["control"][0],
                         {"VTOY_DEFAULT_IMAGE": "/a-b.iso"})

    def test_the_iso_is_copied_to_the_top_level_under_its_own_name(self):
        calls = []

        def run(argv, **keywords):
            calls.append(argv)
            if argv[0] == "/usr/bin/cp":
                shutil.copyfile(argv[-2], argv[-1])
            return ""
        self.populate(run, lambda path: (512, [1]), [])
        copied = next(argv for argv in calls if argv[0] == "/usr/bin/cp")
        self.assertEqual(Path(copied[-1]), self.directory / "mnt" / "probe.iso")

    def test_a_block_map_with_a_hole_or_no_extent_is_refused(self):
        for blocks in ([30, 0, 32], [0, 31, 32], [30, 31, 0], [0], []):
            with self.subTest(blocks=blocks), self.assertRaisesRegex(Refusal, r"holes \(block map: \d+ extents, \d+ holes\)"):
                ventoy_image.require_whole_file(*ventoy_image.extents(blocks))
        with self.assertRaisesRegex(Refusal, r"block map: 2 extents, 1 holes"):
            ventoy_image.require_whole_file(*ventoy_image.extents([30, 0, 32]))
        for blocks in ([30, 31, 32], [30], [30, 31, 40, 41]):  # Fragments are slow for GRUB but not holes.
            with self.subTest(blocks=blocks):
                ventoy_image.require_whole_file(*ventoy_image.extents(blocks))

    def test_build_calls_the_pure_functions_the_tests_above_cover(self):
        # build() needs root, a loop device and Ventoy's installer, so no unit test runs it past its
        # argument refusals. This only proves it still goes through the tested functions.
        tree = ast.parse((RUNTIME / "ventoy-image.py").read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "build")
        called = {node.func.id for node in ast.walk(function) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        self.assertLessEqual({"stick_files", "enroll_record", "require_whole_file", "populate"}, called)

    def test_a_hole_found_by_populate_reaches_the_refusal_build_applies(self):
        def run(argv, **keywords):
            if argv[0] == "/usr/bin/cp":
                shutil.copyfile(argv[-2], argv[-1])
            return ""
        *_, (block, count, holes) = self.populate(run, lambda path: (512, [30, 0, 32]), [])
        self.assertEqual((count, holes), (2, 1))
        with self.assertRaises(Refusal):
            ventoy_image.require_whole_file(count, holes)

    def ventoy_enrollment(self, owner=None, sha="c" * 64):
        """The writer's ENROLL.json beside the key pair, as build() leaves them (the private half is a stand-in)."""
        keys, fingerprints = remote_check.public_keys(f"ssh-ed25519 {key_blob(6)}\n".encode())
        folder = self.directory / "enroll-keys"
        folder.mkdir(mode=0o700)
        (folder / "owner_key.pub").write_bytes(keys)
        (folder / "owner_key").write_bytes(b"stand-in private key\n")
        (folder / "owner_key").chmod(0o600)
        record = ventoy_image.enroll_record(sha, owner, keys, fingerprints[0])
        (folder / "ENROLL.json").write_bytes(remote_check.canonical(record))
        remote = self.directory / "remote"
        remote.mkdir(exist_ok=True)
        return folder, remote, keys, fingerprints[0], record

    @unittest.skipUnless(hasattr(os, "geteuid"), "enrollment keys are read on the Linux test host")
    def test_the_enrollment_record_the_writer_makes_is_accepted_by_the_reader(self):
        for owner, explicit in ((None, False), ("mac-owner", True)):
            with self.subTest(owner=owner):
                folder, remote, keys, fingerprint, record = self.ventoy_enrollment(owner)
                self.assertEqual(sorted(record), ["authorized_keys_sha256", "image_sha256", "owner",
                                                  "owner_key_fingerprint", "schema"])
                adopted = remote_check.adopt_ventoy_keys(folder, remote, "c" * 64, owner, explicit)
                self.assertEqual(adopted, (keys, [fingerprint]))
                self.assertEqual((remote / "owner_key").read_bytes(), b"stand-in private key\n")
                self.assertEqual(remote_check.digest(ventoy_image.stick_files("t.iso", keys, owner)["tup-enroll/authorized_keys"]),
                                 record["authorized_keys_sha256"])  # What the stick holds is what the record names.
                shutil.rmtree(folder)
                shutil.rmtree(remote)

    @unittest.skipUnless(hasattr(os, "geteuid"), "enrollment keys are read on the Linux test host")
    def test_a_changed_image_digest_owner_or_key_fingerprint_is_refused_by_the_reader(self):
        folder, remote, keys, fingerprint, record = self.ventoy_enrollment("mac-owner")
        for sha, owner, explicit, message in (("d" * 64, "mac-owner", True, "not made for this Ventoy image"),
                                              ("c" * 64, "other", True, "enrolls owner 'mac-owner'"),
                                              ("c" * 64, None, False, "enrolls owner 'mac-owner'")):
            with self.subTest(sha=sha[:1], owner=owner), self.assertRaisesRegex(Refusal, message):
                remote_check.adopt_ventoy_keys(folder, remote, sha, owner, explicit)
        for change, message in (({"owner_key_fingerprint": "SHA256:" + "A" * 43}, "differs from the one written"),
                                ({"authorized_keys_sha256": "0" * 64}, "differs from the one written"),
                                ({"image_sha256": "d" * 64}, "not made for this Ventoy image"),
                                ({"owner": None}, "enrolls owner None")):
            (folder / "ENROLL.json").write_bytes(remote_check.canonical({**record, **change}))
            with self.subTest(change=change), self.assertRaisesRegex(Refusal, message):
                remote_check.adopt_ventoy_keys(folder, remote, "c" * 64, "mac-owner", True)
        self.assertEqual(list(remote.iterdir()), [])  # Nothing was adopted.

    def populate(self, run, block_map, calls):
        mountpoint = self.directory / "mnt"
        mountpoint.mkdir(exist_ok=True)
        return ventoy_image.populate("/dev/loop7p1", mountpoint, self.iso, "probe.iso",
                                     {"ventoy/ventoy.json": b"{}\n", "tup-enroll/authorized_keys": b"key\n"},
                                     lambda mounted: calls.append(("guard", mounted)), run, block_map)

    def test_population_checks_the_loop_before_every_write_copies_without_holes_and_reads_back(self):
        calls = []

        def run(argv, **keywords):
            calls.append(("run", argv))
            if argv[0] == "/usr/bin/cp":
                shutil.copyfile(argv[-2], argv[-1])
            return "1 extent found\n" if argv[0].endswith("filefrag") else ""
        report, back, steps, layout = self.populate(run, lambda path: (512, [30, 31, 32]), calls)
        self.assertEqual(layout, (512, 1, 0))
        self.assertEqual(back, {"probe.iso": self.digest, "ventoy/ventoy.json": remote_check.digest(b"{}\n"),
                                "tup-enroll/authorized_keys": remote_check.digest(b"key\n")})
        mount = str(self.directory / "mnt")
        programs = [argv[0].rsplit("/", 1)[1] for kind, argv in calls if kind == "run"]
        self.assertEqual(programs, ["mount", "cp", "sync", "filefrag", "umount", "mount", "umount"])
        self.assertEqual([argv[4] for kind, argv in calls if kind == "run" and argv[0].endswith("/mount")], ["rw,nosuid,nodev,noexec", "ro,nosuid,nodev,noexec"])
        copy = next(argv for kind, argv in calls if kind == "run" and argv[0].endswith("/cp"))
        self.assertEqual(copy[:3], ["/usr/bin/cp", "--sparse=never", "--"])
        for index, (kind, argv) in enumerate(calls):
            if kind == "run" and argv[0].rsplit("/", 1)[1] in ("mount", "cp", "sync", "umount"):
                self.assertEqual(calls[index - 1][0], "guard", argv)  # Proven to be the loop, just before.
            if kind == "run":
                self.assertTrue(all(not arg.startswith("/dev/") or arg == "/dev/loop7p1" for arg in argv), argv)
                self.assertNotIn(argv[0], ("/usr/bin/rm", "/usr/sbin/mkfs.ext4", "/usr/sbin/debugfs"))
        self.assertEqual(calls[-1], ("guard", None))
        self.assertTrue(all(m in (None, ("/dev/loop7p1", mount)) for kind, m in calls if kind == "guard"))

    def test_a_failed_copy_still_unmounts_and_a_failed_guard_stops_before_the_write(self):
        calls = []

        def broken(argv, **keywords):
            calls.append(("run", argv))
            if argv[0] == "/usr/bin/cp":
                raise subprocess.CalledProcessError(1, argv)
            return ""
        with self.assertRaises(subprocess.CalledProcessError):
            self.populate(broken, lambda path: (512, []), calls)
        self.assertEqual([argv[0].rsplit("/", 1)[1] for kind, argv in calls if kind == "run"], ["mount", "cp", "umount"])
        calls.clear()

        def changed(mounted):
            calls.append(("guard", mounted))
            raise ValueError("backing-file identity changed")
        ran = []
        with self.assertRaisesRegex(ValueError, "identity changed"):
            ventoy_image.populate("/dev/loop7p1", self.directory / "mnt", self.iso, "probe.iso", {}, changed,
                                  lambda argv, **kw: ran.append(argv), lambda path: (512, []))
        self.assertEqual(ran, [])  # The very first mount never ran.


class ShellTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="tup-runtime-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name).resolve()
        self.media = self.directory / "media.iso"
        self.media.write_bytes(b"fixture media\n")
        self.digest = remote_check.file_hash(self.media)

    def uefi(self, *arguments):
        return subprocess.run([BASH, shell_path(RUNTIME / "uefi.sh"), *arguments], capture_output=True, text=True,
                              timeout=60, stdin=subprocess.DEVNULL)

    @unittest.skipUnless(BASH, "bash is required")
    def test_shell_scripts_parse_and_have_unix_line_endings(self):
        for script in (RUNTIME / "uefi.sh", RUNTIME.parents[1] / "boot_verdict.sh"):
            with self.subTest(script=script.name):
                self.assertNotIn(b"\r", script.read_bytes())
                done = subprocess.run([BASH, "-n", shell_path(script)], capture_output=True, text=True)
                self.assertEqual((done.returncode, done.stderr), (0, ""))

    @unittest.skipUnless(BASH, "bash is required")
    def test_uefi_refuses_unsafe_arguments_before_any_tool_runs(self):
        media, fresh = shell_path(self.media), shell_path(self.directory) + "/fresh"
        existing = self.directory / "existing"
        existing.mkdir()
        wrong = "0" * 64
        cases = [
            (("tup-iso-ssh", media, self.digest), "usage: uefi.sh"),
            (("tup-usb", media, self.digest, fresh), "unknown test kind"),
            (("tup-iso-ssh", media, "sha256", fresh), "SHA256 is required"),
            (("tup-iso-ssh", "/dev/null", self.digest, fresh), "never a device"),
            (("ventoy-tup-ssh", "/dev/sda", self.digest, fresh), "never a device"),
            (("tup-iso-ssh", shell_path(self.directory), self.digest, fresh), "never a device"),
            (("tup-iso-ssh", media, self.digest, shell_path(existing)), "must be a new directory"),
            (("ventoy-tup", media, self.digest, shell_path(existing)), "must be a new directory"),
            (("tup-iso-ssh", media, wrong, fresh), "media digest mismatch"),
            (("tup-iso-ssh", media, self.digest, fresh, "--memory-mib", "8192"), "from 512 to 4096"),
            (("tup-iso-ssh", media, self.digest, fresh, "--memory-mib", "2g"), "from 512 to 4096"),
            (("tup-iso-ssh", media, self.digest, fresh, "--cpus", "0"), "from 1 to 4"),
            (("tup-iso-ssh", media, self.digest, fresh, "--cpus"), "needs a value"),
            (("tup-iso-ssh", media, self.digest, fresh, "--ssh-port", "22"), "from 1024 to 65535"),
            (("tup-iso-ssh", media, self.digest, fresh, "--ssh-wait", "5"), "from 30 to 1800"),
            (("tup-iso-ssh", media, self.digest, fresh, "--poweroff-budget", "5000"), "from 30 to 900"),
            (("tup-iso-ssh", media, self.digest, fresh, "--accel", "kvm"), "unknown option"),
            (("tup-iso", media, self.digest, fresh, "--ssh-port", "2222"), "unknown option"),
            (("ventoy-tup", media, self.digest, fresh, "--owner", "owner"), "unknown option"),
            (("tup-iso-ssh", media, self.digest, fresh, "--enroll-keys", "keys"), "unknown option"),
            (("ventoy-tup", media, self.digest, fresh, "--enroll-keys", "keys"), "unknown option"),
            (("host-smoke", media, self.digest, fresh, "--cpus", "2"), "take no options"),
        ]
        if os.name != "nt":
            link = self.directory / "link.iso"
            link.symlink_to(self.media)
            cases.append((("tup-iso-ssh", str(link), self.digest, fresh), "never a device"))
            dangling = self.directory / "dangling"
            dangling.symlink_to(self.directory / "nowhere")
            cases.append((("tup-iso-ssh", media, self.digest, str(dangling)), "must be a new directory"))
        for arguments, message in cases:
            with self.subTest(arguments=arguments[:1] + arguments[4:], message=message):
                done = self.uefi(*arguments)
                self.assertEqual(done.returncode, 1, done.stderr)
                self.assertIn(message, done.stderr)
                self.assertEqual(done.stdout, "")
        self.assertFalse((self.directory / "fresh").exists())
        self.assertEqual(list(existing.iterdir()), [])

    def stand_in_tree(self):
        """A copy of the tooling whose uefi.sh starts the stand-in emulator; returns the tests-runtime copy."""
        tree = self.directory / "tree/tup"
        shutil.copytree(RUNTIME, tree / "boot/tests-runtime", ignore=shutil.ignore_patterns("evidence", "__pycache__"))
        for name in ("boot_verdict.sh", "boot/inputs.py", "boot/__init__.py", "remote/policy.py"):
            (tree / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RUNTIME.parents[1] / name, tree / name)
        emulator = self.directory / "emulator.py"
        emulator.write_text(STAND_IN_EMULATOR)
        emulator.chmod(0o700)
        firmware = self.directory / "vars.fd"
        firmware.write_bytes(b"fixture variables\n")
        copy = tree / "boot/tests-runtime"
        script = (copy / "uefi.sh").read_text()
        for real, fake in (("/usr/bin/qemu-system-x86_64", str(emulator)), ("/usr/share/OVMF/OVMF_VARS_4M.fd", str(firmware))):
            self.assertIn(real, script)
            script = script.replace(real, fake)
        (copy / "uefi.sh").write_text(script)
        (copy / "host-tools.sha256").write_text("".join(
            f"{remote_check.file_hash(path)}  {path}\n" for path in (emulator, firmware)))
        return copy

    def stand_in_run(self, copy, kind, media, digest, name, *options, tamper=None):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        output = self.directory / name
        env = dict(os.environ, TUP_STAND_IN_TAMPER=str(tamper)) if tamper else None
        done = subprocess.run([BASH, str(copy / "uefi.sh"), kind, str(media), digest, str(output),
                               "--ssh-port", str(port), "--ssh-wait", "30", "--poweroff-budget", "30", *options],
                              capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL, env=env)
        return done, output, port

    @unittest.skipUnless(BASH and REAL_TOOLS and hasattr(socket, "AF_UNIX"), "needs the Linux test host's tools")
    def test_whole_remote_run_against_a_stand_in_emulator_fails_honestly_and_ends_cleanly(self):
        """Control flow only: the stand-in prints a prompt and answers QMP; nothing listens for SSH.

        The run must record a booted serial verdict, fail every SSH check without
        skipping one, power the stand-in down through QMP and still say FAILED.
        """
        done, output, port = self.stand_in_run(self.stand_in_tree(), "tup-iso-ssh", self.media, self.digest, "run")
        self.assertEqual(done.returncode, 1, done.stderr)
        verdict = done.stdout.strip().splitlines()[-1]
        self.assertTrue(verdict.startswith("TUP REMOTE ACCESS FAILED (external VM, TCG): "), done.stdout)
        result = json.loads((output / "RESULT.json").read_bytes())
        status = {item["name"]: item["status"] for item in result["checks"]}
        self.assertEqual(sorted(status), sorted(remote_check.REQUIRED))
        self.assertEqual({name for name, value in status.items() if value == "pass"},
                         {"serial_boot_verdict", "poweroff_request", "guest_powered_off", "host_inputs_unchanged"})
        self.assertNotIn("not-applicable", status.values())
        self.assertEqual((result["passed"], result["verdict"], result["poweroff_method"], result["boot_verdict"]),
                         (False, verdict, "qmp-system_powerdown", "BOOTED"))
        text = (output / "RESULT.txt").read_text()
        for line in ("verdict: " + verdict, "serial_boot_verdict: BOOTED", "accelerator: tcg", "hardware_tested: false",
                     "scope: tup-iso-ssh", "remote_access_tested: true", "physical_boot_tested: false",
                     "release_eligible: false"):
            self.assertIn(line + "\n", text)
        inputs = (output / "INPUTS.txt").read_text()
        self.assertIn(f"hostfwd=tcp:127.0.0.1:{port}-10.0.2.15:22", inputs)
        self.assertIn("virtio-blk-pci\\,drive=enroll", inputs)
        self.assertIn(b"reboot: Power down", (output / "serial.log").read_bytes())
        self.assertFalse((output / "remote/owner_key").exists() or (output / "remote/unenrolled_key").exists())
        self.assertEqual((output / "remote/enroll.img").stat().st_mode & 0o777, 0o400)
        self.assertEqual(output.stat().st_mode & 0o777, 0o700)
        remote_check.check_enrollment_image(output / "remote/enroll.img")
        self.assertIn("media: unchanged\n", (output / "host-recheck.txt").read_text())

    @unittest.skipUnless(BASH and REAL_TOOLS and hasattr(socket, "AF_UNIX"), "needs the Linux test host's tools")
    def test_media_rebuilt_during_the_run_is_in_the_machine_readable_result_not_only_in_the_exit_status(self):
        copy = self.stand_in_tree()
        done, output, _ = self.stand_in_run(copy, "tup-iso-ssh", self.media, self.digest, "tampered", tamper=self.media)
        self.assertEqual(done.returncode, 1, done.stderr)
        self.assertIn("changed during the test", done.stderr)
        result = json.loads((output / "RESULT.json").read_bytes())
        self.assertIn("host_inputs_unchanged", result["failed_checks"])
        self.assertFalse(result["passed"])
        self.assertTrue(done.stdout.strip().splitlines()[-1].startswith("TUP REMOTE ACCESS FAILED"))
        self.assertIn("media: CHANGED", (output / "host-recheck.txt").read_text())
        self.assertTrue((output / "RESULT.txt").is_file())  # The wrapper reports it; it does not vanish.

    @unittest.skipUnless(BASH and REAL_TOOLS and hasattr(socket, "AF_UNIX"), "needs the Linux test host's tools")
    def test_ventoy_run_uses_the_one_stick_with_no_second_enrollment_disk(self):
        copy = self.stand_in_tree()
        stick = self.directory / "stick"
        stick.mkdir(mode=0o700)
        image = stick / "ventoy.raw"
        image.write_bytes(b"fixture ventoy image\n")
        digest = remote_check.file_hash(image)
        folder = stick / "enroll-keys"
        folder.mkdir(mode=0o700)
        keys, fingerprints = remote_check.generate_key(remote_check.TOOLS, remote_check.execute, folder / "owner_key")
        (folder / "ENROLL.json").write_bytes(remote_check.canonical({
            "schema": "tup.runtime-ventoy-enroll.v1", "image_sha256": digest, "owner": None,
            "authorized_keys_sha256": remote_check.digest(keys), "owner_key_fingerprint": fingerprints[0]}))
        done, output, _ = self.stand_in_run(copy, "ventoy-tup-ssh", image, digest, "ventoy")
        self.assertEqual(done.returncode, 1, done.stderr)  # No SSH server answers; the stand-in is not a guest.
        inputs = (output / "INPUTS.txt").read_text()
        self.assertEqual(inputs.count("usb-storage"), 1)
        self.assertNotIn("id=enroll", inputs)
        self.assertNotIn("virtio-blk", inputs)
        self.assertFalse((output / "remote/enroll.img").exists())
        prepared = json.loads((output / "remote/PREPARED.json").read_bytes())
        self.assertEqual(prepared["owner_key_fingerprint"], fingerprints[0])
        self.assertIn("Ventoy data partition", prepared["enrollment"])
        result = json.loads((output / "RESULT.json").read_bytes())
        self.assertEqual(result["kind"], "ventoy-tup-ssh")
        self.assertIn("Ventoy data partition", result["scope"]["enrollment"])
        self.assertEqual((output / "remote/owner_key.pub").read_bytes(), (folder / "owner_key.pub").read_bytes())
        self.assertFalse((output / "remote/owner_key").exists())  # The run's copy is deleted; the image's stays.
        self.assertTrue((folder / "owner_key").exists())
        # Keys made for another image, or a missing directory, refuse before QEMU starts.
        (folder / "ENROLL.json").write_bytes((folder / "ENROLL.json").read_bytes().replace(digest.encode(), b"0" * 64))
        done, output, _ = self.stand_in_run(copy, "ventoy-tup-ssh", image, digest, "ventoy-wrong")
        self.assertEqual(done.returncode, 1)
        self.assertIn("not made for this Ventoy image", done.stderr)
        self.assertFalse((output / "qemu.stdout").exists() or (output / "RESULT.json").exists())
        done, output, _ = self.stand_in_run(copy, "ventoy-tup-ssh", image, digest, "ventoy-elsewhere",
                                            "--enroll-keys", str(self.directory / "absent"))
        self.assertEqual(done.returncode, 1)
        self.assertIn("enrollment media refused", done.stderr)

    def test_remote_kinds_keep_tcg_one_loopback_forward_and_a_read_only_enrollment_drive(self):
        script = (RUNTIME / "uefi.sh").read_text(encoding="utf-8")
        self.assertIn("accel=tcg", script)
        self.assertNotIn("kvm", script.lower().replace("kvm was actually probed", ""))
        self.assertEqual(script.count("hostfwd="), 1)
        self.assertIn("restrict=on,hostfwd=tcp:127.0.0.1:$port-10.0.2.15:22", script)
        self.assertIn("id=enroll,format=raw,readonly=on", script)
        self.assertIn(". \"$TUP/boot_verdict.sh\"", script)
        self.assertEqual(script.count("tup_boot_verdict "), 1)  # One verdict rule, sourced, never copied.
        for path in re.findall(r"^[0-9a-f]{64}  (\S+)$", (RUNTIME / "remote-tools.sha256").read_text(), re.M):
            self.assertIn(path, remote_check.TOOLS.values())
        self.assertEqual(len(re.findall(r"^[0-9a-f]{64}  /\S+$", (RUNTIME / "remote-tools.sha256").read_text(), re.M)),
                         len(remote_check.TOOLS))


if __name__ == "__main__":
    unittest.main()
