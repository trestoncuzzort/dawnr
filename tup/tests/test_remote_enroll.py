"""Boot-time owner enrollment against a temporary root and injected tools.

No real account, key, firewall or daemon is touched: every command enroll.py
would run on the target is answered by the Tools fixture below.
"""
import base64
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import struct
import sys
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("remote_enroll", Path(__file__).resolve().parents[1] / "remote/enroll.py")
enroll = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(enroll)
policy, firewall, Refusal = enroll.policy, enroll.firewall, enroll.Refusal


def public_key(seed: int, comment: bytes = b"") -> bytes:
    blob = struct.pack(">I", 11) + b"ssh-ed25519" + struct.pack(">I", 32) + bytes(range(seed, seed + 32))
    return b"ssh-ed25519 " + base64.b64encode(blob) + comment + b"\n"


KEY, OTHER_KEY, HOST_KEY = public_key(1, b" owner@laptop"), public_key(2), public_key(100, b" root@fixture")
HOST_FINGERPRINT = policy.public_keys(HOST_KEY)[1][0]
DEFAULT_FIREWALL = firewall.render(None, None, scope=firewall.UNENROLLED)["firewall.nft"]
LABEL, VENTOY, ISOSCAN, LIVE, INSTALLED = enroll.INPUT_DIRECTORIES
POSIX = unittest.skipUnless(os.name == "posix", "enrollment needs Linux ownership, modes and symlinks")


def effective(config: bytes) -> bytes:
    """What `sshd -T` prints for a rendered configuration, as far as policy.py checks it."""
    lines = []
    for line in config.decode().splitlines():
        if line.startswith("#"):
            continue
        keyword, value = line.split(" ", 1)
        if keyword == "ListenAddress":
            value = f"[{value}]:22" if ":" in value else f"{value}:22"
        lines.append(f"{keyword} {value}")
    return ("\n".join(lines) + "\n").encode()


class Tools:
    """Injected command runner: records argv and imitates each tool's effect."""

    def __init__(self, root, fail=(), drift=lambda raw: raw, password=None, uid=1000):
        self.root, self.fail, self.drift, self.password, self.uid = root, set(fail), drift, password, uid
        self.calls, self.marker_seen = [], []

    def names(self):
        return [Path(argv[0]).name + (" " + argv[1] if Path(argv[0]).name in ("nft", "ssh-keygen") else "")
                for argv in self.calls]

    def __call__(self, argv):
        self.calls.append(list(argv))
        self.marker_seen.append(os.path.lexists(self.root / enroll.MARKER))
        name = self.names()[-1]
        if name in self.fail:
            return 1, b""
        if name == "ssh-keygen -A":
            for kind in ("rsa", "ecdsa", "ed25519"):
                (self.root / f"etc/ssh/ssh_host_{kind}_key").write_bytes(b"fixture, not a key\n")
            (self.root / enroll.HOST_KEY).write_bytes(HOST_KEY)
        elif name == "ssh-keygen -l":
            return 0, f"256 {HOST_FINGERPRINT} root@fixture (ED25519)\n".encode()
        elif name == "sshd":
            assert argv[1:3] == ["-T", "-f"], argv
            return 0, self.drift(effective(Path(argv[3]).read_bytes()))
        elif name == "useradd":
            owner = argv[-1]
            password = argv[argv.index("--password") + 1] if self.password is None else self.password
            with open(self.root / "etc/passwd", "a") as stream:
                stream.write(f"{owner}:x:{self.uid}:{self.uid}:TUP owner:/home/{owner}:{argv[argv.index('--shell') + 1]}\n")
            with open(self.root / "etc/shadow", "a") as stream:
                stream.write(f"{owner}:{password}:20000:0:99999:7:::\n")
            with open(self.root / "etc/group", "a") as stream:
                stream.write(f"{owner}:x:{self.uid}:\n")
            (self.root / "home" / owner).mkdir()
        return 0, b""


def snapshot(root):
    """Every path below root with its type, mode and content."""
    result = {}
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        content = os.readlink(path) if stat.S_ISLNK(info.st_mode) else path.read_bytes() if stat.S_ISREG(info.st_mode) else None
        result[path.relative_to(root).as_posix()] = (stat.S_IFMT(info.st_mode), stat.S_IMODE(info.st_mode), content)
    return result


class Fixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.outside = Path(temporary.name) / "outside"
        self.outside.mkdir()
        self.root = Path(temporary.name) / "root"
        for directory in ("etc/ssh", "etc/tup", "etc/systemd/system", "home", "run", "usr/bin", "usr/sbin"):
            (self.root / directory).mkdir(parents=True)
        (self.root / "etc/passwd").write_text("root:x:0:0:root:/root:/bin/bash\nsshd:x:50:50:sshd PrivSep:/var/lib/sshd:/bin/false\n")
        (self.root / "etc/shadow").write_text("root:!:20000:0:99999:7:::\nsshd:!:20000::::::\n")
        (self.root / "etc/group").write_text("root:x:0:\nsshd:x:50:\nusers:x:999:\n")
        (self.root / "etc/gshadow").write_text("root:::\nsshd:!::\n")
        (self.root / enroll.FIREWALL).write_bytes(DEFAULT_FIREWALL)
        for relative in enroll.TOOLS.values():
            (self.root / relative).write_bytes(b"")
        for path in (self.root, *self.root.rglob("*")):  # Independent of the caller's umask.
            path.chmod(0o755 if path.is_dir() else 0o644)

    def sudo(self):
        for relative in enroll.SUDO.values():
            (self.root / relative).write_bytes(b"")

    def give(self, location=ISOSCAN, **files):
        directory = self.root / location
        directory.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            (directory / name).write_bytes(data)
        return directory

    def refused(self, tools=None, pattern=""):
        """A refusal that must leave no marker and, with no tool run, no change at all."""
        tools = tools or Tools(self.root)
        before = snapshot(self.root)
        with self.assertRaisesRegex(Refusal, pattern):
            enroll.apply(self.root, tools)
        self.assertFalse(os.path.lexists(self.root / enroll.MARKER))
        if not tools.calls:
            self.assertEqual(snapshot(self.root), before)
        self.assertEqual([name for name in snapshot(self.root) if name.endswith(".tup-new")], [])
        return tools


@POSIX
class EnrollmentTests(Fixture):
    def test_private_networks_enrollment_installs_checked_files_and_writes_the_marker_last(self):
        self.sudo()
        self.give(authorized_keys=KEY)
        tools = Tools(self.root)
        result = enroll.apply(self.root, tools)
        self.assertEqual(result["state"], "enrolled")
        # The firewall is committed from the staged file before the account exists.
        self.assertEqual(tools.names(), ["ssh-keygen -A", "sshd", "visudo", "nft -c", "nft -f", "useradd"])
        self.assertFalse(any(tools.marker_seen), "the marker must not exist while any tool still runs")
        staged = [argv[-1] for argv in tools.calls[1:5]]
        self.assertTrue(all(Path(path).name.endswith(".tup-new") for path in staged), staged)
        self.assertEqual(tools.calls[4][1:], ["-f", str(self.root / "etc/tup/.firewall.nft.tup-new")])
        useradd = tools.calls[5]
        self.assertEqual(useradd[1:], ["--create-home", "--home-dir", "/home/owner", "--shell", "/bin/bash",
                                       "--user-group", "--password", "*", "--comment", "TUP owner", "owner"])
        expected = {
            "etc/tup/authorized_keys/owner": (policy.public_keys(KEY)[0], 0o644),
            enroll.SSHD_CONFIG: (policy.render("owner", None, KEY, scope=policy.PRIVATE)["sshd_config"], 0o600),
            enroll.FIREWALL: (firewall.render(None, None, scope=policy.PRIVATE)["firewall.nft"], 0o600),
            enroll.SUDOERS: (b"owner ALL=(ALL:ALL) NOPASSWD: ALL\n", 0o440),
            enroll.MARKER: (policy.canonical(result["record"]), 0o644),
        }
        record = json.loads((self.root / enroll.MARKER).read_bytes())
        for relative, (data, mode) in expected.items():
            path = self.root / relative
            self.assertEqual(path.read_bytes(), data, relative)
            self.assertEqual(stat.S_IMODE(path.lstat().st_mode), mode, relative)
            if relative != enroll.MARKER:
                self.assertEqual(record["files"]["/" + relative], hashlib.sha256(data).hexdigest())
        self.assertNotIn(b"laptop", (self.root / "etc/tup/authorized_keys/owner").read_bytes())
        self.assertEqual(sorted(record["files"]), sorted("/" + name for name in expected if name != enroll.MARKER))
        self.assertEqual(record["schema"], "tup-owner-enrolled-v1")
        self.assertEqual((record["owner"], record["scope"], record["sudo"]), ("owner", "private-networks", "passwordless-all"))
        self.assertEqual(record["listen_addresses"], ["0.0.0.0", "::"])
        self.assertEqual(record["input"], "/run/initramfs/isoscan/tup-enroll")
        self.assertEqual(record["hardware_clock"], "untouched")
        self.assertFalse(os.path.lexists(self.root / enroll.CLOCK))
        self.assertEqual(record["input_files"], {"authorized_keys": hashlib.sha256(KEY).hexdigest()})
        self.assertEqual(record["owner_key_fingerprints"], policy.public_keys(KEY)[1])
        self.assertEqual(record["host_key_fingerprints"], {"ssh_host_ed25519_key.pub": HOST_FINGERPRINT})
        self.assertEqual(record["account"], {"uid": 1000, "gid": 1000, "home": "/home/owner", "shell": "/bin/bash"})
        self.assertFalse((self.root / "etc/systemd/system/tup-sshd.service").exists())
        self.assertEqual([name for name in snapshot(self.root) if name.endswith(".tup-new")], [])
        # StrictModes: the key file and every directory above it, up to the root.
        path = self.root / "etc/tup/authorized_keys/owner"
        while path != self.root.parent:
            self.assertFalse(path.lstat().st_mode & 0o022, path)
            path = path.parent

    def test_listen_and_peer_files_select_the_exact_scope_and_sudo_absence_is_recorded(self):
        self.give(authorized_keys=KEY, owner=b"alice\r\n", listen=b"10.0.2.15\nfd00::15\n", peer=b"10.0.2.2\n\nfd00::2\n")
        tools = Tools(self.root)
        record = enroll.apply(self.root, tools)["record"]
        self.assertEqual(tools.names(), ["ssh-keygen -A", "sshd", "nft -c", "nft -f", "useradd"])
        self.assertEqual((record["owner"], record["scope"], record["sudo"]), ("alice", "exact", "absent"))
        self.assertEqual(record["listen_addresses"], ["10.0.2.15", "fd00::15"])
        self.assertEqual(record["owner_peer_addresses"], ["10.0.2.2", "fd00::2"])
        self.assertFalse((self.root / "etc/sudoers.d").exists())
        exact = policy.render("alice", ["10.0.2.15", "fd00::15"], KEY)
        self.assertEqual((self.root / enroll.SSHD_CONFIG).read_bytes(), exact["sshd_config"])
        self.assertEqual((self.root / "etc/systemd/system/tup-sshd.service").read_bytes(), exact["tup-sshd.service"])
        self.assertEqual((self.root / enroll.FIREWALL).read_bytes(),
                         firewall.render(["10.0.2.15", "fd00::15"], ["10.0.2.2", "fd00::2"])["firewall.nft"])
        self.assertTrue((self.root / "etc/tup/authorized_keys/alice").is_file())
        self.assertEqual(sorted(record["input_files"]), ["authorized_keys", "listen", "owner", "peer"])

    def test_a_second_run_changes_nothing_even_with_new_input(self):
        self.sudo()
        directory = self.give(authorized_keys=KEY)
        enroll.apply(self.root, Tools(self.root))
        (directory / "authorized_keys").write_bytes(OTHER_KEY)
        (directory / "owner").write_bytes(b"mallory\n")
        before = snapshot(self.root)
        tools = Tools(self.root)
        self.assertEqual(enroll.apply(self.root, tools), {"state": "already-enrolled"})
        self.assertEqual(tools.calls, [])
        self.assertEqual(snapshot(self.root), before)
        status, output, _ = self.main(tools)
        self.assertEqual((status, output), (0, "TUP enrollment: already enrolled; nothing changed\n"))
        self.assertEqual((tools.calls, snapshot(self.root)), ([], before))

    def test_no_input_is_not_an_error_and_changes_nothing(self):
        (self.root / LIVE).mkdir(parents=True)
        (self.root / LIVE / "authorized_keys.pub").write_bytes(KEY)  # A misnamed file is not enrollment.
        before = snapshot(self.root)
        tools = Tools(self.root)
        self.assertEqual(enroll.apply(self.root, tools), {"state": "no-input", "without_keys": ["/" + LIVE]})
        self.assertEqual((tools.calls, snapshot(self.root)), ([], before))

    def test_search_order_is_label_then_boot_media_then_the_installed_copy(self):
        self.assertEqual(enroll.INPUT_DIRECTORIES, (
            "run/tup-enroll/tup-enroll", "run/initramfs/tup-ventoy/media/tup-enroll",
            "run/initramfs/isoscan/tup-enroll", "run/initramfs/live/tup-enroll", "etc/tup/enroll-input"))
        self.give(INSTALLED, authorized_keys=OTHER_KEY)
        self.assertEqual(enroll.locate(self.root), (INSTALLED, []))
        self.give(LIVE, authorized_keys=OTHER_KEY)
        self.assertEqual(enroll.locate(self.root), (LIVE, []))
        self.give(ISOSCAN, authorized_keys=KEY)
        self.assertEqual(enroll.locate(self.root), (ISOSCAN, []))
        # Where boot/ventoy-live.sh leaves the stick's data partition mounted.
        self.give(VENTOY, authorized_keys=KEY, owner=b"ventoy\n")
        self.assertEqual(enroll.locate(self.root), (VENTOY, []))
        self.give(LABEL, authorized_keys=OTHER_KEY, owner=b"labelled\n")
        record = enroll.apply(self.root, Tools(self.root))["record"]
        self.assertEqual((record["input"], record["owner"]), ("/run/tup-enroll/tup-enroll", "labelled"))
        self.assertEqual(record["owner_key_fingerprints"], policy.public_keys(OTHER_KEY)[1])

    def test_the_ventoy_data_partition_and_the_installed_copy_enroll(self):
        for location, expected in ((VENTOY, "/run/initramfs/tup-ventoy/media/tup-enroll"), (INSTALLED, "/etc/tup/enroll-input")):
            with self.subTest(location=location):
                self.setUp()
                self.give(location, authorized_keys=KEY)
                record = enroll.apply(self.root, Tools(self.root))["record"]
                self.assertEqual((record["input"], record["owner"]), (expected, "owner"))

    def test_time_synchronization_needs_the_owners_word_that_the_hardware_clock_is_utc(self):
        self.give(authorized_keys=KEY, clock=b"utc\r\n")
        record = enroll.apply(self.root, Tools(self.root))["record"]
        self.assertEqual(record["hardware_clock"], "utc")
        self.assertEqual((self.root / enroll.CLOCK).read_bytes(), b"utc\n")
        self.assertEqual(stat.S_IMODE((self.root / enroll.CLOCK).lstat().st_mode), 0o644)
        self.assertEqual(record["files"]["/" + enroll.CLOCK], hashlib.sha256(b"utc\n").hexdigest())
        for content in (b"", b"UTC\n", b"local\n", b"utc\nutc\n", b"America/Los_Angeles\n", b"\xff"):
            with self.subTest(content=content):
                self.setUp()
                self.give(authorized_keys=KEY, clock=content)
                self.assertEqual(self.refused().calls, [])
                self.assertFalse(os.path.lexists(self.root / enroll.CLOCK))

    def test_invalid_input_applies_nothing(self):
        rsa = b"ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC7 owner@laptop\n"
        cases = [
            dict(authorized_keys=rsa), dict(authorized_keys=b'command="/bin/sh" ' + KEY),
            dict(authorized_keys=b"-----BEGIN OPENSSH PRIVATE KEY-----\n"), dict(authorized_keys=b""),
            dict(authorized_keys=KEY + KEY), dict(authorized_keys=b"\xff\xfe"), dict(authorized_keys=b"x" * 16385),
            dict(authorized_keys=KEY, owner=b"root\n"), dict(authorized_keys=KEY, owner=b"sshd"),
            dict(authorized_keys=KEY, owner=b"owner\nextra\n"), dict(authorized_keys=KEY, owner=b"Owner\n"),
            dict(authorized_keys=KEY, owner=b"\n"), dict(authorized_keys=KEY, owner=b"\xff"),
            dict(authorized_keys=KEY, owner=b"owner ALL=(ALL) NOPASSWD: ALL\n"), dict(authorized_keys=KEY, owner=b"o" * 257),
            dict(authorized_keys=KEY, listen=b"10.0.2.15\n"), dict(authorized_keys=KEY, peer=b"10.0.2.2\n"),
            dict(authorized_keys=KEY, listen=b"", peer=b"10.0.2.2\n"),
            dict(authorized_keys=KEY, listen=b"203.0.113.7\n", peer=b"10.0.2.2\n"),
            dict(authorized_keys=KEY, listen=b"10.0.2.15\n", peer=b"198.51.100.9\n"),
            dict(authorized_keys=KEY, listen=b"0.0.0.0\n", peer=b"10.0.2.2\n"),
            dict(authorized_keys=KEY, listen=b"10.0.2.15\n", peer=b"10.0.0.0/8\n"),
            dict(authorized_keys=KEY, listen=b"10.0.2.15\n", peer=b"fd00::2\n"),
            dict(authorized_keys=KEY, listen=b"10.0.2.15\nPasswordAuthentication yes\n", peer=b"10.0.2.2\n"),
        ]
        for files in cases:
            with self.subTest(files={name: data[:40] for name, data in files.items()}):
                directory = self.give(**files)
                self.assertEqual(self.refused().calls, [])
                for name in files:
                    (directory / name).unlink()
        directory = self.give()
        (directory / "authorized_keys").mkdir()
        self.assertEqual(self.refused(pattern="regular file").calls, [])

    def test_existing_account_group_or_home_is_never_adopted(self):
        self.give(authorized_keys=KEY)
        for relative, line in (("etc/passwd", "owner:x:1000:1000::/home/owner:/bin/bash\n"), ("etc/shadow", "owner:*:20000::::::\n"),
                               ("etc/group", "owner:x:1000:\n"), ("etc/gshadow", "owner:!::\n")):
            with self.subTest(relative=relative):
                original = (self.root / relative).read_text()
                (self.root / relative).write_text(original + line)
                self.assertEqual(self.refused(pattern="already exists").calls, [])
                (self.root / relative).write_text(original)
        (self.root / "home/owner").mkdir()
        self.assertEqual(self.refused(pattern="/home/owner already exists").calls, [])

    def test_missing_remote_tools_refuse_before_any_change(self):
        self.give(authorized_keys=KEY)
        for relative in enroll.TOOLS.values():
            with self.subTest(relative=relative):
                (self.root / relative).unlink()
                self.assertEqual(self.refused(pattern="remote layer").calls, [])
                (self.root / relative).write_bytes(b"")

    def test_failed_checks_leave_no_marker_no_account_and_the_default_firewall(self):
        self.sudo()
        self.give(authorized_keys=KEY)
        password = lambda raw: raw.replace(b"PasswordAuthentication no", b"PasswordAuthentication yes")
        listener = lambda raw: raw.replace(b"ListenAddress [::]:22\n", b"")
        other = lambda raw: raw.replace(b"AllowUsers owner", b"AllowUsers owner root")
        for tools in (Tools(self.root, fail={"sshd"}), Tools(self.root, fail={"visudo"}), Tools(self.root, fail={"nft -c"}),
                      Tools(self.root, drift=password), Tools(self.root, drift=listener), Tools(self.root, drift=other),
                      Tools(self.root, drift=lambda raw: b"")):
            with self.subTest(calls=tools.fail):
                self.refused(tools)
                self.assertNotIn("useradd", tools.names())
                self.assertNotIn("nft -f", tools.names())
                self.assertEqual((self.root / enroll.FIREWALL).read_bytes(), DEFAULT_FIREWALL)
                for relative in (enroll.SSHD_CONFIG, enroll.SUDOERS, "etc/tup/authorized_keys", "etc/sudoers.d", "home/owner"):
                    self.assertFalse(os.path.lexists(self.root / relative), relative)
                self.assertNotIn("owner", (self.root / "etc/passwd").read_text())
        tools = self.refused(Tools(self.root, fail={"ssh-keygen -A"}))
        self.assertEqual(tools.names(), ["ssh-keygen -A"])

    def test_account_or_firewall_load_failure_leaves_no_marker(self):
        self.give(authorized_keys=KEY)
        tools = self.refused(Tools(self.root, fail={"useradd"}), "useradd failed")
        self.assertEqual((self.root / enroll.FIREWALL).read_bytes(), DEFAULT_FIREWALL)
        self.assertFalse(os.path.lexists(self.root / enroll.SSHD_CONFIG))
        for unexpected in (dict(password="!"), dict(password=""), dict(password="!*"), dict(uid=0), dict(uid=999)):
            with self.subTest(unexpected=unexpected):
                self.setUp()
                self.give(authorized_keys=KEY)
                tools = self.refused(Tools(self.root, **unexpected), "expected unprivileged account")
                self.assertFalse(os.path.lexists(self.root / enroll.SSHD_CONFIG))
        # A firewall the kernel will not commit stops enrollment before the
        # account exists, so the next attempt is not refused for adopting one.
        self.setUp()
        self.give(authorized_keys=KEY)
        tools = self.refused(Tools(self.root, fail={"nft -f"}), "could not load")
        self.assertEqual(tools.names()[-2:], ["nft -c", "nft -f"])
        self.assertNotIn("owner", (self.root / "etc/passwd").read_text())
        self.assertEqual((self.root / enroll.FIREWALL).read_bytes(), DEFAULT_FIREWALL)
        for relative in (enroll.SSHD_CONFIG, "etc/tup/authorized_keys", "home/owner"):
            self.assertFalse(os.path.lexists(self.root / relative), relative)

    def test_symlinks_are_never_followed_out_of_the_root(self):
        traps = {
            "etc/tup": lambda path: (path.joinpath("firewall.nft").unlink(), path.rmdir(), path.symlink_to(self.outside)),
            "etc/tup/authorized_keys": lambda path: path.symlink_to(self.outside),
            "etc/ssh": lambda path: (path.rmdir(), path.symlink_to(self.outside)),
            "etc/passwd": lambda path: (path.rename(self.outside / "passwd"), path.symlink_to(self.outside / "passwd")),
            "etc/sudoers.d": lambda path: path.symlink_to(self.outside),
            enroll.SSHD_CONFIG: lambda path: path.symlink_to(self.outside / "valid/authorized_keys"),
            "home/owner": lambda path: path.symlink_to(self.outside),
            ISOSCAN: lambda path: (path.parent.mkdir(parents=True), path.symlink_to(self.outside / "valid")),
            ISOSCAN + "/authorized_keys": lambda path: (path.parent.mkdir(parents=True),
                                                        path.symlink_to(self.outside / "valid/authorized_keys")),
            ISOSCAN + "/owner": lambda path: (self.give(authorized_keys=KEY), path.symlink_to(self.outside / "valid/authorized_keys")),
        }
        for relative, trap in traps.items():
            with self.subTest(relative=relative):
                self.setUp()
                self.sudo()
                (self.outside / "valid").mkdir()
                (self.outside / "valid/authorized_keys").write_bytes(KEY)  # A valid key behind every link.
                if not relative.startswith("run/"):
                    self.give(authorized_keys=KEY)
                trap(self.root / relative)
                outside = snapshot(self.outside)
                self.assertEqual(self.refused().calls, [])
                self.assertEqual(snapshot(self.outside), outside)
        for target in (self.outside / "absent", self.outside / "valid/authorized_keys"):
            self.setUp()
            (self.outside / "valid").mkdir()
            (self.outside / "valid/authorized_keys").write_bytes(KEY)
            self.give(authorized_keys=KEY)
            (self.root / enroll.MARKER).symlink_to(target)  # Neither "enrolled" nor a place to write.
            before, tools = snapshot(self.root), Tools(self.root)
            with self.assertRaisesRegex(Refusal, "symbolic link"):
                enroll.apply(self.root, tools)
            self.assertEqual((tools.calls, snapshot(self.root)), ([], before))
        link = self.outside / "root-link"
        link.symlink_to(self.root)
        with self.assertRaisesRegex(Refusal, "symbolic link"):
            enroll.apply(link, Tools(self.root))

    def test_existing_links_at_destinations_are_replaced_not_written_through(self):
        self.give(authorized_keys=KEY)
        victim = self.outside / "victim"
        victim.write_bytes(b"untouched\n")
        (self.root / enroll.SSHD_CONFIG).symlink_to(victim)
        (self.root / "etc/tup/.firewall.nft.tup-new").symlink_to(victim)
        with self.assertRaisesRegex(Refusal, "symbolic link"):
            enroll.apply(self.root, Tools(self.root))  # A linked destination is refused outright.
        (self.root / enroll.SSHD_CONFIG).unlink()
        enroll.apply(self.root, Tools(self.root))  # A stale staging name is unlinked, never opened.
        self.assertEqual(victim.read_bytes(), b"untouched\n")
        self.assertFalse((self.root / enroll.FIREWALL).is_symlink())
        self.assertEqual((self.root / enroll.FIREWALL).read_bytes(), firewall.render(None, None, scope=policy.PRIVATE)["firewall.nft"])

    def test_directories_others_can_write_refuse(self):
        self.give(authorized_keys=KEY)
        for relative in ("", "etc", "etc/tup", "etc/ssh"):
            with self.subTest(relative=relative):
                path = self.root / relative
                mode = stat.S_IMODE(path.stat().st_mode)
                for unsafe in (mode | 0o020, mode | 0o002):
                    path.chmod(unsafe)
                    try:
                        self.assertEqual(self.refused(pattern="not writable by group or others").calls, [])
                    finally:
                        path.chmod(mode)

    def test_real_commands_are_refused_for_any_root_but_slash(self):
        self.give(authorized_keys=KEY)
        with self.assertRaisesRegex(Refusal, "injected command runner"):
            enroll.apply(self.root)

    def test_default_runner_reports_status_and_output(self):
        self.assertEqual(enroll.run_command([sys.executable, "-c", "print('ok')"]), (0, b"ok\n"))
        self.assertEqual(enroll.run_command([sys.executable, "-c", "raise SystemExit(3)"])[0], 3)

    def main(self, tools, *arguments):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            status = enroll.main(list(arguments), root=self.root, run=tools)
        return status, output.getvalue(), errors.getvalue()

    def test_main_reports_and_records_only_what_the_console_needs(self):
        tools = Tools(self.root)
        status, output, errors = self.main(tools)  # No input is a normal boot, not a failure.
        self.assertEqual((status, errors), (0, ""))
        self.assertIn("no enrollment input; SSH stays off", output)
        self.assertFalse((self.root / enroll.RESULT).exists())
        directory = self.give(authorized_keys=b"ssh-rsa AAAA\n")
        status, output, errors = self.main(tools)
        self.assertEqual((status, output), (1, ""))
        self.assertIn("REFUSED: only plain ssh-ed25519 public keys", errors)
        self.assertEqual((self.root / enroll.RESULT).read_bytes(),
                         b"REFUSED: only plain ssh-ed25519 public keys are currently supported\n")
        self.assertEqual(tools.calls, [])
        self.assertFalse(os.path.lexists(self.root / enroll.MARKER))
        (directory / "authorized_keys").write_bytes(KEY)
        status, output, errors = self.main(tools)
        self.assertEqual((status, errors), (0, ""))
        self.assertIn(f"enrolled owner from /{ISOSCAN} (scope private-networks); host key {HOST_FINGERPRINT}", output)
        self.assertTrue((self.root / enroll.MARKER).is_file())
        self.assertEqual(self.main(tools, "--console-status"), (0, "", ""))
        self.assertIn(b"ENROLLED. Account owner", (self.root / enroll.ISSUE).read_bytes())
        (self.root / enroll.MARKER).unlink()
        (self.root / enroll.MARKER).symlink_to(self.outside)
        status, _, errors = self.main(tools, "--console-status")
        self.assertEqual(status, 1)
        self.assertIn("TUP console status: REFUSED", errors)


class ConsoleStatusTests(Fixture):
    def status(self, **options):
        tools = Tools(self.root, **options)
        text = enroll.console_status(self.root, tools)
        self.assertEqual((self.root / enroll.ISSUE).read_bytes(), text)
        text.decode("ascii")
        return text.decode(), tools

    def test_unenrolled_console_says_how_to_enroll_and_why_the_last_attempt_failed(self):
        text, tools = self.status()
        self.assertIn("NOT ENROLLED", text)
        self.assertIn("tup-enroll/authorized_keys", text)
        self.assertNotIn("fingerprint", text)
        self.assertEqual(tools.calls, [])
        (self.root / enroll.RESULT).write_bytes("REFUSED: bad \\4 \\S{x} \x1b[2J café\n".encode())
        text, _ = self.status()
        self.assertIn("Last attempt: REFUSED: bad ?4 ?S{x} ?[2J caf?\n", text)
        self.assertNotIn("\\", text)

    def test_enrolled_console_shows_how_to_connect_and_the_host_key_fingerprint(self):
        record = {"owner": "owner", "scope": "private-networks", "listen_addresses": ["0.0.0.0", "::"]}
        (self.root / enroll.MARKER).write_bytes(policy.canonical(record))
        (self.root / enroll.HOST_KEY).write_bytes(HOST_KEY)
        text, tools = self.status()
        self.assertIn("ENROLLED. Account owner, scope private-networks.", text)
        self.assertIn("ssh owner@\\n.local\n", text)  # agetty expands \n to the host name.
        self.assertIn(f"ED25519 host key fingerprint:  {HOST_FINGERPRINT}\n", text)
        self.assertEqual(tools.calls, [[str(self.root / "usr/bin/ssh-keygen"), "-l", "-f", str(self.root / enroll.HOST_KEY)]])
        self.assertTrue(enroll.ISSUE.startswith("run/issue.d/") and enroll.ISSUE.endswith(".issue"))
        (self.root / enroll.MARKER).write_bytes(policy.canonical({**record, "scope": "exact", "listen_addresses": ["10.0.2.15"]}))
        self.assertIn("ssh owner@10.0.2.15\n", self.status()[0])

    def test_unreadable_marker_or_fingerprint_is_said_plainly(self):
        (self.root / enroll.HOST_KEY).write_bytes(HOST_KEY)
        for marker in (b"not json", b"[]", policy.canonical({"owner": "root", "scope": "exact", "listen_addresses": ["10.0.2.15"]}),
                       policy.canonical({"owner": "owner", "scope": "anywhere"}),
                       policy.canonical({"owner": "owner", "scope": "exact", "listen_addresses": ["\\4"]})):
            with self.subTest(marker=marker[:30]):
                (self.root / enroll.MARKER).write_bytes(marker)
                text, _ = self.status(fail={"ssh-keygen -l"})
                self.assertIn("the enrollment marker is unreadable", text)
                self.assertIn("fingerprint could not be read", text)
                self.assertNotIn("ssh ", text)


if __name__ == "__main__":
    unittest.main()
