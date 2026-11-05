"""Input refusals for the renderer; real network tests use probe_firewall.py."""
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("remote_firewall", Path(__file__).resolve().parents[1] / "remote/firewall.py")
firewall = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(firewall)


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


if __name__ == "__main__":
    unittest.main()
