"""Negative controls for private SSH enrollment; no daemon is started here."""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import struct
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("remote_policy", Path(__file__).resolve().parents[1] / "remote/policy.py")
policy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(policy)
BLOB = struct.pack(">I", 11) + b"ssh-ed25519" + struct.pack(">I", 32) + bytes(range(1, 33))
KEY = b"ssh-ed25519 " + base64.b64encode(BLOB) + b" fixture-only\n"


class RemotePolicyTests(unittest.TestCase):
    @staticmethod
    def effective_fixture():
        config = policy.render("owner", ["127.0.0.1", "::1"], KEY)["sshd_config"]
        return b"\n".join(line for line in config.splitlines() if not line.startswith(b"#")).replace(
            b"ListenAddress 127.0.0.1\n", b"ListenAddress 127.0.0.1:22\n").replace(
            b"ListenAddress ::1\n", b"ListenAddress [::1]:22\n") + b"\n"

    def test_effective_policy_keywords_are_case_insensitive(self):
        raw = self.effective_fixture()
        policy.check_effective(raw, "owner", ["127.0.0.1", "::1"])
        lower_keywords = b"\n".join(line.split(b" ", 1)[0].lower() + b" " + line.split(b" ", 1)[1] for line in raw.splitlines())
        policy.check_effective(lower_keywords, "owner", ["127.0.0.1", "::1"])

    def test_effective_password_root_ca_and_owner_drift_refuse(self):
        original = self.effective_fixture()
        for before, after in ((b"PasswordAuthentication no", b"PasswordAuthentication yes"),
                              (b"PermitRootLogin no", b"PermitRootLogin prohibit-password"),
                              (b"TrustedUserCAKeys none", b"TrustedUserCAKeys /tmp/ca"),
                              (b"AllowUsers owner", b"AllowUsers owner other"),
                              (b"UsePAM no", b"UsePAM yes")):
            with self.subTest(before=before), self.assertRaises(policy.Refusal):
                policy.check_effective(original.replace(before, after), "owner", ["127.0.0.1", "::1"])

    def test_effective_missing_duplicate_or_wildcard_listeners_refuse(self):
        original = self.effective_fixture()
        variants = (original.replace(b"ListenAddress 127.0.0.1:22\n", b""),
                    original.replace(b"ListenAddress 127.0.0.1:22", b"ListenAddress 0.0.0.0:22"),
                    original + b"ListenAddress 127.0.0.1:22\n",
                    original + b"PasswordAuthentication no\n", b"", b"malformed\n")
        for raw in variants:
            with self.assertRaises(policy.Refusal):
                policy.check_effective(raw, "owner", ["127.0.0.1", "::1"])

    def test_complete_policy_is_owner_only_and_bound_to_exact_files(self):
        files = policy.render("owner", ["127.0.0.1", "::1"], KEY)
        config = files["sshd_config"].decode()
        self.assertIn("AllowUsers owner\n", config)
        self.assertIn("AuthenticationMethods publickey\n", config)
        for directive in ("PermitRootLogin", "PasswordAuthentication", "KbdInteractiveAuthentication", "PermitEmptyPasswords"):
            self.assertIn(directive + " no\n", config)
        self.assertNotIn("Include ", config)
        self.assertIn(b"Requires=tup-firewall.service", files["tup-sshd.service"])
        plan = json.loads(files["ENROLLMENT-PLAN.json"])
        self.assertEqual(plan["status"], "rendered-not-applied")
        self.assertFalse(plan["release_eligible"])
        for name, expected in plan["files"].items():
            self.assertEqual(hashlib.sha256(files[name]).hexdigest(), expected)

    def test_owner_injection_system_accounts_and_globs_refuse(self):
        for owner in ("root", "sshd", "lfs", "systemd-network", "owner\nMatch all", "*", "owner@host", "-owner", "OWNER", "0"):
            with self.subTest(owner=owner), self.assertRaises(policy.Refusal):
                policy.render(owner, ["127.0.0.1"], KEY)

    def test_wildcard_public_multicast_scoped_mapped_and_injected_listeners_refuse(self):
        for address in ("0.0.0.0", "::", "8.8.8.8", "224.0.0.1", "fe80::1%eth0", "::ffff:127.0.0.1", "localhost", "127.0.0.1\nPasswordAuthentication yes"):
            with self.subTest(address=address), self.assertRaises(policy.Refusal):
                policy.render("owner", [address], KEY)

    def test_private_overlay_and_lan_addresses_are_explicit(self):
        self.assertEqual(policy.listen_addresses(["10.0.0.5", "100.64.0.5", "fd00::5"]), ["10.0.0.5", "100.64.0.5", "fd00::5"])
        for addresses in ([], ["::1", "0:0:0:0:0:0:0:1"], ["127.0.0.1"] * 9):
            with self.assertRaises(policy.Refusal):
                policy.listen_addresses(addresses)

    def test_private_key_and_authorized_keys_options_refuse(self):
        for key in (b"-----BEGIN OPENSSH PRIVATE KEY-----\n", b'command="sh" ' + KEY, b"ssh-rsa AAAA\n", b"", b"# only comment\n", b"\xff", b"x" * 16385):
            with self.subTest(key=key[:30]), self.assertRaises(policy.Refusal):
                policy.public_keys(key)

    def test_malformed_wire_lengths_and_trailing_payload_refuse(self):
        bad_blobs = (BLOB[:-1], BLOB + b"x", BLOB[:15] + struct.pack(">I", 31) + BLOB[19:], BLOB[:19] + bytes(32), b"ssh-ed25519")
        for blob in bad_blobs:
            with self.assertRaises(policy.Refusal):
                policy.public_keys(b"ssh-ed25519 " + base64.b64encode(blob))
        with self.assertRaises(policy.Refusal):
            policy.public_keys(b"ssh-ed25519 !!invalid!!")

    def test_comments_are_discarded_duplicates_and_extra_directives_refuse(self):
        key, fingerprints = policy.public_keys(KEY)
        self.assertNotIn(b"fixture", key)
        self.assertEqual(len(fingerprints), 1)
        for value in (KEY + KEY, KEY + b"PasswordAuthentication yes\n", KEY * 9):
            with self.assertRaises(policy.Refusal):
                policy.public_keys(value)

    def test_invalid_ports_refuse(self):
        for port in (0, 65536, -1, "22", True):
            with self.assertRaises(policy.Refusal):
                policy.render("owner", ["127.0.0.1"], KEY, port)

    @unittest.skipUnless(os.name == "posix", "requires Linux ownership and modes")
    def test_private_creation_refuses_overwrite_and_world_writable_parent(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            target = parent / "enrollment"
            outputs = policy.render("owner", ["127.0.0.1"], KEY)
            policy.write_private_directory(target, outputs)
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o700)
            for name in outputs:
                self.assertEqual(stat.S_IMODE((target / name).stat().st_mode), 0o600)
            with self.assertRaises(FileExistsError):
                policy.write_private_directory(target, outputs)
            parent.chmod(0o777)
            try:
                with self.assertRaises(policy.Refusal):
                    policy.write_private_directory(parent / "second", outputs)
            finally:
                parent.chmod(0o700)

    @unittest.skipUnless(os.name == "posix", "requires Linux symlinks")
    def test_symlink_parent_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            real = parent / "real"
            real.mkdir(mode=0o700)
            link = parent / "alias"
            link.symlink_to(real, target_is_directory=True)
            with self.assertRaises(policy.Refusal):
                policy.write_private_directory(link / "enrollment", policy.render("owner", ["127.0.0.1"], KEY))


if __name__ == "__main__":
    unittest.main()
