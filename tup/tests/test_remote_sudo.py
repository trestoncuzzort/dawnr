"""Sudo source record, five-source closure and target page; no network, build or install.

Run: python -m unittest discover -s tup/tests -p 'test_remote_sudo.py' -v
The retained publisher bytes are checked for real. Signature tests run the real
verifier when a gpg executable exists; the authenticated archive itself stays in
the external cache, so the positive signature check is evidence, not a unit test.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

TUP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TUP))
from remote import verify_layer_sources as layer
from remote import verify_sources as four
from sources import source_lock as verifier

REMOTE = TUP / "remote"
PAGE = REMOTE / "pages/05-sudo.sh"
BASH = os.environ.get("TUP_TEST_BASH") or shutil.which("bash")
GPG = shutil.which("gpg")
PIN = "4a38a1ab3adb1199257edc2a7c4a2bd714665eb605b04368843b06dada2cfcfb"


def verified(name, sha256="0" * 64):
    return {"name": name, "status": "verified", "sha256": sha256, "size": 1,
            "authentication": {"status": "verified", "trust_class": "publisher-openpgp"}}


class SudoRecordTests(unittest.TestCase):
    """Every check except GPG itself, against a mutable copy of the real record."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.remote = Path(temporary.name) / "remote"
        (self.remote / "evidence/netfilter").mkdir(parents=True)
        shutil.copytree(REMOTE / "evidence/sudo", self.remote / "evidence/sudo")
        shutil.copyfile(REMOTE / "evidence/netfilter/lfs-13.1-advisories.html",
                        self.remote / "evidence/netfilter/lfs-13.1-advisories.html")
        for name in ("sudo-source.json", "sudo-advisories.json"):
            shutil.copyfile(REMOTE / name, self.remote / name)
        self.cache = Path(temporary.name) / "cache"
        self.cache.mkdir()

    def edit(self, name, change):
        value = json.loads((self.remote / name).read_bytes())
        change(value)
        (self.remote / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")

    def check(self):
        with patch.object(verifier, "verify_record", return_value=verified(layer.SUDO, PIN)) as signature:
            report = layer.verify_sudo(self.cache, Path("gpg"), self.remote)
            signature.assert_called_once()
            record, cache, evidence, gpg = signature.call_args.args
            self.assertEqual((record["name"], cache, evidence), (layer.SUDO, self.cache, self.remote / "evidence/sudo"))
            return report

    def refused(self, pattern):
        with self.assertRaisesRegex(verifier.Refusal, pattern):
            self.check()

    def test_retained_record_passes_every_non_signature_check(self):
        report = self.check()
        self.assertEqual(report["status"], "verified")
        self.assertEqual([row["name"] for row in report["sources"]], [layer.SUDO])
        self.assertEqual(report["published_sha256_on_approval_page"], PIN)
        self.assertFalse(report["release_eligible"])

    def test_record_has_the_shape_the_existing_verifier_requires(self):
        record = json.loads((REMOTE / "sudo-source.json").read_bytes())["source"]
        auth = record["authentication"]
        self.assertEqual((record["sha256"], auth["method"], auth["primary_fingerprint"]),
                         (PIN, "openpgp", layer.SUDO_PRIMARY))
        self.assertTrue(auth["approval"]["reviewed_at"] and auth["approval"]["basis"])
        for item in (auth["key"], auth["signature"], auth["approval"]["material"]):
            verifier.material(REMOTE / "evidence/sudo", item)

    def test_unsigned_verifier_result_is_not_accepted(self):
        for result in (dict(verified(layer.SUDO, PIN), status="accepted-exception"),
                       dict(verified(layer.SUDO, PIN), authentication={"trust_class": "https-published-sha256"})):
            with self.subTest(result=result), patch.object(verifier, "verify_record", return_value=result), \
                    self.assertRaisesRegex(verifier.Refusal, "incomplete"):
                layer.verify_sudo(self.cache, Path("gpg"), self.remote)

    def test_changed_identity_key_or_signer_refuses_before_any_signature_check(self):
        changes = {
            "name": lambda value: value["source"].update(name="sudo-1.9.17p1.tar.gz"),
            "url": lambda value: value["source"].update(url="https://mirror.invalid/" + layer.SUDO),
            "omit": lambda value: value["source"].update(disposition="omit", reason="fixture"),
            "method": lambda value: value["source"]["authentication"].update(method="https-published-sha256"),
            "old-key": lambda value: value["source"]["authentication"].update(
                primary_fingerprint="CCB24BE9E9481B15D34159535A89DFA27EE470C4"),
            "any-signer": lambda value: value["source"]["authentication"].pop("signing_fingerprint"),
            "payload": lambda value: value["source"]["authentication"].update(payload="uncompressed-tar"),
        }
        for name, change in changes.items():
            with self.subTest(name=name):
                self.setUp()
                self.edit("sudo-source.json", change)
                with patch.object(verifier, "verify_record") as signature:
                    with self.assertRaisesRegex(verifier.Refusal, "changed without review"):
                        layer.verify_sudo(self.cache, Path("gpg"), self.remote)
                    signature.assert_not_called()

    def test_pin_must_equal_the_digest_on_the_retained_download_page(self):
        self.edit("sudo-source.json", lambda value: value["source"].update(sha256="f" * 64))
        self.refused("differs from the digest published")

    def test_changed_or_fingerprintless_approval_page_refuses(self):
        page = self.remote / "evidence/sudo/sudo-download.html"
        original = page.read_bytes()
        page.write_bytes(original + b"\n")
        self.refused("SHA256 mismatch")
        stripped = original.replace(b"59D1 E9CC BA2B 3767", b"0000 0000 0000 0000")
        page.write_bytes(stripped)
        self.edit("sudo-source.json", lambda value: value["source"]["authentication"]["approval"]["material"].update(
            sha256=verifier.digest(page)))
        self.refused("does not publish the approved signing fingerprint")

    def test_advisory_review_must_be_the_exact_reviewed_dispositions(self):
        changes = {
            "date": lambda value: value.update(reviewed_at="2026-11-06"),
            "request": lambda value: value["request"]["fields"].update(release="13.0"),
            "inventory": lambda value: value.update(inventory_sha256="0" * 64),
            "selected": lambda value: value.update(selected_advisories=[{"id": "sa-13.1-999"}]),
            "dropped": lambda value: value["dispositions"].pop(),
            "extra": lambda value: value["dispositions"].append(dict(value["dispositions"][0], id="upstream-sudo-new")),
            "not-fixed": lambda value: value["dispositions"][0].update(disposition="not-affected"),
            "other-source": lambda value: value["dispositions"][1].update(selected_sources=["sudo-1.9.17.tar.gz"]),
            "fix-release": lambda value: value["dispositions"][0].update(fixed_in="1.9.18"),
        }
        for name, change in changes.items():
            with self.subTest(name=name):
                self.setUp()
                self.edit("sudo-advisories.json", change)
                self.refused("requires new review|differs from the reviewed complete query")

    def test_a_sudo_record_in_the_lfs_inventory_requires_new_review(self):
        raw = (self.remote / "evidence/netfilter/lfs-13.1-advisories.html").read_bytes()
        inventory = verifier.advisory_inventory(raw)
        inventory[0] = dict(inventory[0], package="Sudo")
        self.edit("sudo-advisories.json", lambda value: value.update(
            inventory_sha256=hashlib.sha256(verifier.encoded(inventory)).hexdigest()))
        with patch.object(verifier, "advisory_inventory", return_value=inventory):
            self.refused("requires new review")

    def test_retained_advisory_pages_must_state_the_fix_and_stay_newest(self):
        page = self.remote / "evidence/sudo/sudo-advisory-chroot_bug.html"
        page.write_bytes(page.read_bytes().replace(b"1.9.17p1", b"1.9.18"))
        self.edit("sudo-advisories.json", lambda value: value["dispositions"][0]["evidence"].update(
            sha256=verifier.digest(page)))
        self.refused("does not state the reviewed fix release")
        self.setUp()
        index = self.remote / "evidence/sudo/sudo-advisories.html"
        index.write_bytes(index.read_bytes().replace(
            b'href="/security/advisories/chroot_bug/"', b'href="/security/advisories/newer_bug/"', 1))
        self.edit("sudo-advisories.json", lambda value: value["upstream_index"].update(sha256=verifier.digest(index)))
        self.refused("unreviewed newest record")

    @unittest.skipUnless(GPG, "gpg is required for the real signature controls")
    def test_real_gpg_refuses_other_bytes_and_a_key_that_did_not_sign(self):
        (self.cache / layer.SUDO).write_bytes(b"not the signed sudo release\n")
        with self.assertRaisesRegex(verifier.Refusal, "OpenPGP signature verification failed"):
            layer.verify_sudo(self.cache, Path(GPG), self.remote)
        # A key file that lacks the signing key: the retained OpenSSH release key.
        other = REMOTE / "evidence/openssh-10.6p1/RELEASE_KEY.asc"
        shutil.copyfile(other, self.remote / "evidence/sudo/PGPKEYS")
        self.edit("sudo-source.json", lambda value: value["source"]["authentication"]["key"].update(
            sha256=verifier.digest(other)))
        with self.assertRaisesRegex(verifier.Refusal, "OpenPGP signature verification failed"):
            layer.verify_sudo(self.cache, Path(GPG), self.remote)


class FiveSourceClosureTests(unittest.TestCase):
    def setUp(self):
        self.first = {"status": "verified", "catalogs": {"source.json": "a" * 64},
                      "sources": [verified(name) for name in sorted(four.NAMES)], "limitations": ["fixture"]}
        self.sudo = {"status": "verified", "catalogs": {"sudo-source.json": "b" * 64},
                     "sources": [verified(layer.SUDO, PIN)]}

    def verify(self):
        with patch.object(four, "verify", return_value=self.first) as first, \
                patch.object(layer, "verify_sudo", return_value=self.sudo) as sudo:
            report = layer.verify(Path("cache"), Path("gpg"))
            first.assert_called_once_with(Path("cache"), Path("gpg"), layer.HERE)
            sudo.assert_called_once_with(Path("cache"), Path("gpg"), layer.HERE)
            return report

    def test_one_call_returns_the_unchanged_four_plus_sudo(self):
        report = self.verify()
        self.assertEqual((report["status"], report["scope"]), ("verified", "five-remote-layer-sources"))
        self.assertEqual([row["name"] for row in report["sources"]], sorted(four.NAMES) + [layer.SUDO])
        self.assertIs(report["remote"], self.first)
        self.assertEqual(set(report["catalogs"]), {"source.json", "sudo-source.json"})
        self.assertFalse(report["release_eligible"])

    def test_missing_extra_duplicate_or_unverified_source_refuses(self):
        cases = {
            "missing": lambda: self.first["sources"].pop(),
            "extra": lambda: self.first["sources"].append(verified("extra-1.0.tar.gz")),
            "duplicate": lambda: self.first["sources"].__setitem__(0, verified(layer.SUDO)),
            "unverified": lambda: self.first["sources"][0].update(status="unresolved"),
            "four-not-verified": lambda: self.first.update(status="refused"),
            "no-sudo": lambda: self.sudo["sources"].clear(),
        }
        for name, change in cases.items():
            with self.subTest(name=name):
                self.setUp()
                change()
                with self.assertRaisesRegex(verifier.Refusal, "closure changed without review"):
                    self.verify()

    def test_existing_four_source_check_and_its_evidence_are_untouched(self):
        self.assertEqual(four.NAMES, {"openssh-10.6p1.tar.gz", "libmnl-1.0.5.tar.bz2",
                                      "libnftnl-1.3.2.tar.xz", "nftables-1.1.7.tar.xz"})
        receipt = json.loads((REMOTE / "evidence/source-verification.json").read_bytes())
        self.assertEqual(receipt["scope"], "four-remote-layer-sources")
        for name, expected in receipt["catalogs"].items():
            self.assertEqual(verifier.digest(REMOTE / name), expected, name)


class SudoPageTests(unittest.TestCase):
    def setUp(self):
        self.raw = PAGE.read_bytes()
        self.lines = self.raw.decode("ascii").split("\n")

    def test_layer_page_contract(self):
        self.assertNotIn(b"\r", self.raw)
        self.assertEqual(self.lines[:3], ["#!/bin/bash", "# TUP_TARBALL=" + layer.SUDO, "source /tup-layer/common.sh"])
        self.assertTrue(self.raw.endswith(b"\n"))
        text = "\n".join(self.lines)
        for required in ("--prefix=/usr", "--libexecdir=/usr/lib", "--with-secure-path", "--with-env-editor",
                         "--docdir=/usr/share/doc/sudo-1.9.17p2", "--with-passprompt='[sudo] password for %p: '",
                         "--without-pam", "--disable-openssl", 'make -j"$TUP_JOBS"',
                         "make -j1 check", "/sources/log/sudo-make-check.log", "/usr/sbin/visudo -c"):
            self.assertIn(required, text)
        # The generic page installs no rule, account, service or PAM file.
        for forbidden in ("systemctl", "> /etc/sudoers", "NOPASSWD", "useradd", "curl", "wget", "/etc/pam.d"):
            self.assertNotIn(forbidden, text)
        self.assertLess(self.lines.index("env LC_ALL=C make -j1 check > make-check.log 2>&1 || result=$?"),
                        self.lines.index("make -j1 install"))

    def block(self, first, last):
        start = next(index for index, line in enumerate(self.lines) if line.startswith(first))
        end = next(index for index in range(start, len(self.lines)) if self.lines[index] == last)
        return "\n".join(self.lines[start:end + 1]) + "\n"

    def run_bash(self, script, cwd):
        return subprocess.run([BASH, "-c", "set -euo pipefail\n" + script], cwd=cwd, capture_output=True,
                              text=True, timeout=60)

    @unittest.skipUnless(BASH, "Bash is required to execute page fragments")
    def test_page_is_valid_bash(self):
        result = subprocess.run([BASH, "-n"], input=self.raw, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(BASH, "Bash is required to execute page fragments")
    def test_check_log_gate_refuses_hidden_failures_and_missing_suites(self):
        gate = self.block("if grep -Eq 'FAIL$", "done")
        clean = "".join(f"{suite}: {count} tests run, 0 errors, 100% success rate\n" for suite, count in
                        (("check_addr", 9), ("sudoers", 174), ("testsudoers", 62), ("visudo", 20), ("cvtsudoers", 82)))
        cases = {
            "clean": (clean, 0),
            "error-count": (clean.replace("visudo: 20 tests run, 0 errors, 100%", "visudo: 20 tests run, 1 errors, 95%"), 1),
            "other-suite-error": (clean + "check_fill: 18 tests run, 2 errors, 88% success rate\n", 1),
            "harness-fail-line": (clean + "sudoers/test2 (parse): FAIL\n", 1),
            "suite-absent": (clean.replace("cvtsudoers: 82 tests run, 0 errors, 100% success rate\n", ""), 1),
            "suite-ran-nothing": (clean.replace("testsudoers: 62 tests", "testsudoers: 0 tests"), 1),
            "empty": ("", 1),
        }
        for name, (log, expected) in cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                Path(temporary, "make-check.log").write_text(log, encoding="ascii", newline="\n")
                result = self.run_bash(gate, temporary)
                self.assertEqual(result.returncode, expected, result.stderr)

    @unittest.skipUnless(BASH, "Bash is required to execute page fragments")
    def test_default_policy_edit_disables_only_the_upstream_root_rule(self):
        edit = next(line for line in self.lines if line.startswith("sed -i 's/^root ALL"))
        upstream = ('Defaults!/usr/sbin/visudo env_keep += "SUDO_EDITOR EDITOR VISUAL"\n'
                    'Defaults secure_path="/usr/sbin:/usr/bin"\n## User privilege specification\n##\n'
                    "root ALL=(ALL:ALL) ALL\n# %wheel ALL=(ALL:ALL) ALL\n@includedir /etc/sudoers.d\n")
        with tempfile.TemporaryDirectory() as temporary:
            Path(temporary, "sudoers").write_text(upstream, encoding="ascii", newline="\n")
            result = self.run_bash(edit.replace("/etc/sudoers", "sudoers"), temporary)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(Path(temporary, "sudoers").read_bytes().decode("ascii"),
                             upstream.replace("\nroot ALL", "\n# root ALL"))


if __name__ == "__main__":
    unittest.main()
