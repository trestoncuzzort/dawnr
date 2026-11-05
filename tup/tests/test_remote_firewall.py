"""Input refusals for the renderer; real network tests use probe_firewall.py."""
import contextlib
import hashlib
import importlib.util
import io
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("remote_firewall", Path(__file__).resolve().parents[1] / "remote/firewall.py")
firewall = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(firewall)
PRIVATE, UNENROLLED = firewall.PRIVATE, firewall.UNENROLLED


def chain(rules: bytes, name: str) -> list[str]:
    body = rules.decode().split(f"    chain {name} {{\n", 1)[1].split("\n    }\n", 1)[0]
    return [line.strip() for line in body.splitlines()]


class RemoteFirewallTests(unittest.TestCase):
    def test_public_wildcard_mapped_and_injected_peers_refuse(self):
        for peer in ("0.0.0.0", "::", "8.8.8.8", "::ffff:10.0.0.2", "10.0.0.2\nflush ruleset", "10.0.0.0/8"):
            with self.subTest(peer=peer), self.assertRaises(firewall.Refusal):
                firewall.render(["10.0.0.1"], [peer])

    def test_missing_mismatched_and_duplicate_peers_refuse(self):
        for peers in ([], ["fd00::2"], ["10.0.0.2", "10.0.0.2"]):
            with self.subTest(peers=peers), self.assertRaises(firewall.Refusal):
                firewall.render(["10.0.0.1"], peers)

    def test_stop_never_flushes_rules_and_missing_policy_cannot_skip_firewall(self):
        unit = firewall.render(["10.0.0.1"], ["10.0.0.2"])["tup-firewall.service"]
        self.assertNotIn(b"ExecStop=", unit)
        self.assertNotIn(b"ConditionPathExists=", unit)
        self.assertIn(b"Before=network-pre.target tup-sshd.service shutdown.target", unit)

    def test_invalid_ports_refuse(self):
        for port in (True, 0, 65536, "22"):
            with self.assertRaises(firewall.Refusal):
                firewall.render(["10.0.0.1"], ["10.0.0.2"], port)

    def test_exact_scope_output_is_byte_identical_to_the_reviewed_renderer(self):
        # SHA256 of every output of the renderer as it stood before the other
        # scopes existed (commit 52a20d8e), for this fixture.
        expected = {
            "FIREWALL-PLAN.json": "3a724f64fc4e19584aad7424e8966cd601b59d0b79166464daae904e5526eef3",
            "firewall.nft": "40c08e35974eabacd057c755b41710090c6b44100e3e4f13dc5a096d9f19516b",
            "tup-firewall.service": "8d50dfb6068a65730b073e0bf71816948c0f283765df2ab288528ef1ba6fbe58",
        }
        for files in (firewall.render(["10.0.0.1", "fd00::1"], ["10.0.0.2", "fd00::2"]),
                      firewall.render(["10.0.0.1", "fd00::1"], ["10.0.0.2", "fd00::2"], 22, firewall.EXACT)):
            self.assertEqual({name: hashlib.sha256(data).hexdigest() for name, data in files.items()}, expected)
        self.assertNotIn(b"5353", files["firewall.nft"])

    def test_private_networks_scope_admits_ssh_only_from_private_sources(self):
        files = firewall.render(None, None, scope=PRIVATE)
        rules = files["firewall.nft"]
        self.assertEqual(chain(rules, "owner_ssh"), [
            "ip saddr { 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 100.64.0.0/10 } ct state { new, established } counter accept",
            "ip6 saddr { fc00::/7, fe80::/10 } ct state { new, established } counter accept",
            "counter drop"])
        inbound = chain(rules, "input")
        self.assertEqual(inbound[0], "type filter hook input priority filter; policy drop;")
        self.assertEqual(inbound[-1], "counter drop")
        # SSH is decided in its own chain before established traffic is accepted,
        # and no rule of the input chain itself mentions the SSH port again.
        self.assertLess(inbound.index("tcp dport 22 jump owner_ssh"), inbound.index("ct state established,related accept"))
        self.assertEqual([line for line in inbound if "22" in line], ["tcp dport 22 jump owner_ssh"])
        self.assertEqual(inbound[-3:-1], [
            "ip saddr { 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 100.64.0.0/10 } udp dport 5353 accept",
            "ip6 saddr { fc00::/7, fe80::/10 } udp dport 5353 accept"])
        # Every source prefix in the table is a private one; none is a default route, loopback or public.
        allowed = {str(network) for network in firewall.PRIVATE_SOURCES}
        for members in re.findall(r"saddr \{ ([^}]*) \}", rules.decode()):
            for member in members.split(", "):
                self.assertIn(member, allowed)
                self.assertFalse(ipaddress.ip_network(member).is_global or ipaddress.ip_network(member).is_loopback)
        self.assertNotIn(b"daddr", rules)
        self.assertEqual(chain(rules, "forward"), ["type filter hook forward priority filter; policy drop;"])
        self.assertEqual(firewall.render(None, None, 2222, PRIVATE)["firewall.nft"], rules.replace(b"tcp dport 22 ", b"tcp dport 2222 "))
        plan = json.loads(files["FIREWALL-PLAN.json"])
        self.assertEqual((plan["scope"], plan["listen_addresses"], plan["owner_peer_addresses"]), ("private-networks", [], []))
        self.assertEqual(plan["source_networks"], [str(network) for network in firewall.PRIVATE_SOURCES])
        for name, expected in plan["files"].items():
            self.assertEqual(hashlib.sha256(files[name]).hexdigest(), expected)

    def test_unenrolled_table_is_the_private_table_without_any_ssh_accept(self):
        private = firewall.render(None, None, scope=PRIVATE)["firewall.nft"]
        files = firewall.render(None, None, scope=UNENROLLED)
        rules = files["firewall.nft"]
        self.assertEqual(chain(rules, "owner_ssh"), ["counter drop"])
        self.assertNotIn(b"ct state { new, established }", rules)
        self.assertEqual(chain(rules, "input"), chain(private, "input"))
        accepted = [line for line in private.splitlines() if line not in rules.splitlines()]
        self.assertEqual(len(accepted), 2)
        self.assertTrue(all(line.endswith(b"ct state { new, established } counter accept") for line in accepted))
        self.assertEqual(json.loads(files["FIREWALL-PLAN.json"])["scope"], "unenrolled")

    def test_firewall_unit_is_the_same_in_every_scope(self):
        exact = firewall.render(["10.0.0.1"], ["10.0.0.2"])["tup-firewall.service"]
        for scope in (PRIVATE, UNENROLLED):
            self.assertEqual(firewall.render(None, None, scope=scope)["tup-firewall.service"], exact)

    def test_scope_is_explicit_and_only_the_exact_scope_takes_addresses(self):
        for addresses, peers, scope in ((["10.0.0.1"], ["10.0.0.2"], PRIVATE), (["10.0.0.1"], None, PRIVATE),
                                        (None, ["10.0.0.2"], PRIVATE), (None, ["0.0.0.0"], UNENROLLED),
                                        (["10.0.0.1"], ["10.0.0.2"], UNENROLLED), (None, None, firewall.EXACT),
                                        ([], [], firewall.EXACT), (None, None, "public"), (None, None, None),
                                        (["10.0.0.1"], ["10.0.0.2"], "any"), (None, None, "private")):
            with self.subTest(addresses=addresses, peers=peers, scope=scope), self.assertRaises(firewall.Refusal):
                firewall.render(addresses, peers, 22, scope)
        for scope in (PRIVATE, UNENROLLED):
            for port in (True, 0, 65536, "22"):
                with self.assertRaises(firewall.Refusal):
                    firewall.render(None, None, port, scope)

    def test_command_line_scope_flags_are_mutually_exclusive_with_listen_and_peer(self):
        for arguments in (["--private-networks", "--listen", "10.0.0.1", "--peer", "10.0.0.2"],
                          ["--private-networks", "--peer", "10.0.0.2"], ["--unenrolled", "--peer", "10.0.0.2"],
                          ["--unenrolled", "--listen", "10.0.0.1"], ["--private-networks", "--unenrolled"],
                          ["--listen", "10.0.0.1"], ["--peer", "10.0.0.2"], []):
            with self.subTest(arguments=arguments), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as refused:
                    firewall.main([*arguments, "--output", "unused"])
                self.assertEqual(refused.exception.code, 2)

    @unittest.skipUnless(os.name == "posix", "requires Linux ownership and modes")
    def test_command_line_renders_each_scope(self):
        with tempfile.TemporaryDirectory() as temporary:
            for flags, expected in ((["--private-networks"], firewall.render(None, None, scope=PRIVATE)),
                                    (["--unenrolled"], firewall.render(None, None, scope=UNENROLLED)),
                                    (["--listen", "10.0.0.1", "--peer", "10.0.0.2"], firewall.render(["10.0.0.1"], ["10.0.0.2"]))):
                output = Path(temporary) / flags[0].strip("-")
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(firewall.main([*flags, "--output", str(output)]), 0)
                self.assertEqual({path.name: path.read_bytes() for path in output.iterdir()}, expected)

    @unittest.skipUnless(os.environ.get("TUP_TEST_NFT"), "set TUP_TEST_NFT to an nft binary (and run as root) for a check-mode parse")
    def test_real_nft_accepts_every_scope_in_check_mode_and_rejects_a_broken_table(self):
        # `nft -c` validates through the kernel and commits nothing; it never loads rules.
        tables = {"exact": firewall.render(["10.0.2.15", "fd00::15"], ["10.0.2.2", "fd00::2"])["firewall.nft"],
                  "private": firewall.render(None, None, scope=PRIVATE)["firewall.nft"],
                  "unenrolled": firewall.render(None, None, scope=UNENROLLED)["firewall.nft"]}
        tables["broken"] = tables["private"].replace(b"udp dport 5353 accept", b"udp dport 5353 acept")
        with tempfile.TemporaryDirectory() as temporary:
            for name, rules in tables.items():
                path = Path(temporary) / (name + ".nft")
                path.write_bytes(rules)
                done = subprocess.run([os.environ["TUP_TEST_NFT"], "-c", "-f", str(path)], capture_output=True, check=False)
                with self.subTest(name=name):
                    self.assertEqual(done.returncode == 0, name != "broken", done.stderr)


if __name__ == "__main__":
    unittest.main()
