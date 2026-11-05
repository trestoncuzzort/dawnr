"""Negative controls for private SSH enrollment; no daemon is started here."""
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

    def test_effective_host_identity_and_connection_limit_drift_refuse(self):
        original = self.effective_fixture()
        for before, after in (
            (b"HostKey /etc/ssh/ssh_host_ed25519_key", b"HostKey /tmp/shared_host_key"),
            (b"MaxAuthTries 3", b"MaxAuthTries 100"),
            (b"MaxStartups 10:30:30", b"MaxStartups 1000:30:1000"),
            (b"PerSourceMaxStartups 3", b"PerSourceMaxStartups none"),
            (b"LoginGraceTime 30", b"LoginGraceTime 0"),
            (b"LogLevel VERBOSE", b"LogLevel QUIET"),
            (b"Subsystem sftp internal-sftp", b"Subsystem sftp /tmp/other-server"),
        ):
            for changed in (original.replace(before, after), original.replace(before + b"\n", b"")):
                with self.subTest(before=before, missing=before not in changed), self.assertRaises(policy.Refusal):
                    policy.check_effective(changed, "owner", ["127.0.0.1", "::1"])

    def test_service_stop_cleans_session_cgroup(self):
        service = policy.render("owner", ["127.0.0.1"], KEY)["tup-sshd.service"]
        self.assertIn(b"KillMode=control-group\n", service)
        self.assertIn(b"TimeoutStopSec=30\n", service)

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

    @staticmethod
    def private_effective():
        config = policy.render("owner", None, KEY, scope=policy.PRIVATE)["sshd_config"]
        return b"\n".join(line for line in config.splitlines() if not line.startswith(b"#")).replace(
            b"ListenAddress 0.0.0.0\n", b"ListenAddress 0.0.0.0:22\n").replace(
            b"ListenAddress ::\n", b"ListenAddress [::]:22\n") + b"\n"

    def test_exact_scope_output_is_byte_identical_to_the_reviewed_renderer(self):
        # SHA256 of every output of the renderer as it stood before the second
        # scope existed (commit 52a20d8e), for this fixture.
        expected = {
            "ENROLLMENT-PLAN.json": "0e4a339d2c160bcc548e3d9cda75363e49721f1239b7b14ea14b7c4fe4ba619c",
            "authorized_keys": "d5badbd683f6bc900ef7732ee2b5ffd6c693d81fcf96f423e9643d7263f55810",
            "sshd_config": "706e0af10b215caccb67bcc0c230d79fc6088f7e2f2a5bc3923395b0336cb3f1",
            "tup-sshd.service": "766779a1c44a6419a93f169d39915aa0b85b109b871d233c5df6a9a54e99a9c5",
        }
        for files in (policy.render("owner", ["127.0.0.1", "::1"], KEY),
                      policy.render("owner", ["127.0.0.1", "::1"], KEY, 22, policy.EXACT)):
            self.assertEqual({name: hashlib.sha256(data).hexdigest() for name, data in files.items()}, expected)
        self.assertIn(b"After=network-online.target tup-firewall.service\n", files["tup-sshd.service"])

    def test_private_networks_scope_binds_both_wildcards_and_never_waits_for_an_address(self):
        files = policy.render("owner", None, KEY, scope=policy.PRIVATE)
        exact = policy.render("owner", ["127.0.0.1"], KEY)
        self.assertIn(b"AddressFamily any\nListenAddress 0.0.0.0\nListenAddress ::\nHostKey ", files["sshd_config"])
        self.assertEqual(files["sshd_config"].count(b"ListenAddress "), 2)
        unit = files["tup-sshd.service"]
        self.assertNotIn(b"network-online.target", unit)
        self.assertIn(b"\nAfter=network.target tup-firewall.service\nRequires=tup-firewall.service\n"
                      b"ConditionPathExists=/etc/tup/owner-enrolled.json\n", unit)
        # Only the listeners and the unit's ordering depend on the scope.
        self.assertEqual(unit.split(b"Requires=", 1)[1], exact["tup-sshd.service"].split(b"Requires=", 1)[1])
        strip = lambda config: [line for line in config.splitlines() if not line.startswith(b"ListenAddress ")]
        self.assertEqual(strip(files["sshd_config"]), strip(exact["sshd_config"]))
        self.assertEqual(files["authorized_keys"], exact["authorized_keys"])
        plan = json.loads(files["ENROLLMENT-PLAN.json"])
        self.assertEqual((plan["scope"], plan["listen_addresses"]), ("private-networks", ["0.0.0.0", "::"]))
        for name, expected in plan["files"].items():
            self.assertEqual(hashlib.sha256(files[name]).hexdigest(), expected)

    def test_private_networks_effective_check_requires_exactly_both_wildcards(self):
        raw = self.private_effective()
        policy.check_effective(raw, "owner", None, 22, policy.PRIVATE)
        policy.check_effective(raw, "owner", [], scope=policy.PRIVATE)
        variants = (raw.replace(b"ListenAddress [::]:22\n", b""), raw.replace(b"ListenAddress 0.0.0.0:22\n", b""),
                    raw.replace(b"ListenAddress 0.0.0.0:22", b"ListenAddress 127.0.0.1:22"),
                    raw.replace(b"ListenAddress [::]:22", b"ListenAddress [::]:2222"),
                    raw + b"ListenAddress 10.0.0.5:22\n", raw + b"ListenAddress 0.0.0.0:22\n",
                    raw.replace(b"PasswordAuthentication no", b"PasswordAuthentication yes"),
                    raw.replace(b"AllowUsers owner", b"AllowUsers owner root"), self.effective_fixture())
        for changed in variants:
            with self.assertRaises(policy.Refusal):
                policy.check_effective(changed, "owner", None, 22, policy.PRIVATE)
        # The scopes never accept each other's listeners.
        with self.assertRaises(policy.Refusal):
            policy.check_effective(raw, "owner", ["127.0.0.1", "::1"])
        with self.assertRaises(policy.Refusal):
            policy.check_effective(raw, "owner", ["127.0.0.1", "::1"], 22, policy.EXACT)

    def test_scope_is_explicit_and_excludes_listen_addresses(self):
        for addresses, scope in ((["127.0.0.1"], policy.PRIVATE), (["0.0.0.0"], policy.PRIVATE), (None, policy.EXACT),
                                 ([], policy.EXACT), (["0.0.0.0", "::"], policy.EXACT), (None, "public"),
                                 (["127.0.0.1"], "any"), (None, None), (None, ""), (["127.0.0.1"], "PRIVATE-NETWORKS")):
            with self.subTest(addresses=addresses, scope=scope):
                with self.assertRaises(policy.Refusal):
                    policy.render("owner", addresses, KEY, 22, scope)
                with self.assertRaises(policy.Refusal):
                    policy.check_effective(self.private_effective(), "owner", addresses, 22, scope)
        for owner, port in (("root", 22), ("owner", 0)):
            with self.assertRaises(policy.Refusal):
                policy.render(owner, None, KEY, port, policy.PRIVATE)
        with self.assertRaises(policy.Refusal):
            policy.render("owner", None, b"ssh-rsa AAAA\n", scope=policy.PRIVATE)

    def test_private_sources_are_private_networks_without_loopback_plus_link_local(self):
        self.assertEqual([str(network) for network in policy.PRIVATE_SOURCES],
                         ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10", "fc00::/7", "fe80::/10"])
        for network in policy.PRIVATE_SOURCES:
            self.assertFalse(network.is_loopback or network.is_multicast or network.is_unspecified)
            self.assertFalse(network.is_global, network)
            self.assertGreater(network.prefixlen, 0)

    def test_command_line_scope_flags_are_mutually_exclusive(self):
        for arguments in (["--listen", "127.0.0.1", "--private-networks"], []):
            with self.subTest(arguments=arguments), contextlib.redirect_stderr(io.StringIO()) as errors:
                with self.assertRaises(SystemExit) as refused:
                    policy.main(["--owner", "owner", "--public-keys", "unused", "--output", "unused", *arguments])
                self.assertEqual(refused.exception.code, 2)
                self.assertIn("--private-networks", errors.getvalue())

    @unittest.skipUnless(os.name == "posix", "requires Linux ownership and modes")
    def test_command_line_renders_the_private_networks_scope(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            (parent / "key.pub").write_bytes(KEY)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(policy.main(["--owner", "owner", "--private-networks", "--public-keys",
                                              str(parent / "key.pub"), "--output", str(parent / "out")]), 0)
            expected = policy.render("owner", None, KEY, scope=policy.PRIVATE)
            self.assertEqual({path.name: path.read_bytes() for path in (parent / "out").iterdir()}, expected)

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
