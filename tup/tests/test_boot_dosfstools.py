"""dosfstools source record and target page; no network, build or install.

Run: python -m unittest discover -s tup/tests -p 'test_boot_dosfstools.py' -v
The retained publisher bytes are checked for real. The archive and the signed
Gentoo snapshot stay in the external cache, so the positive signature check is
evidence (tup/boot/evidence/dosfstools/source-verification.json), not a unit test.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

TUP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TUP))
from sources import source_lock as verifier

BOOT = TUP / "boot"
EVIDENCE = BOOT / "evidence"
PAGE = BOOT / "staged-pages/04-dosfstools.sh"
BASH = os.environ.get("TUP_TEST_BASH") or shutil.which("bash")
RECORD = json.loads((BOOT / "dosfstools-source.json").read_bytes())
CACHE_ONLY = {"gentoo-20261103.tar.xz"}


def materials(value):
    if isinstance(value, dict):
        if "path" in value and "sha256" in value:
            yield value
        for child in value.values():
            yield from materials(child)


class DosfstoolsRecordTests(unittest.TestCase):
    def test_record_is_the_blfs_release_with_a_detached_signature(self):
        auth = RECORD["authentication"]
        self.assertEqual((RECORD["version"], RECORD["name"], RECORD["disposition"], RECORD["release_eligible"]),
                         ("4.2", "dosfstools-4.2.tar.gz", "retain", False))
        self.assertEqual((auth["method"], auth["payload"]), ("openpgp", "archive"))
        self.assertEqual(auth["corroboration"]["method"], "distributor-openpgp-manifest")
        self.assertIn("13.1-systemd/postlfs/dosfstools.html", RECORD["selection"]["blfs_page"]["url"])
        self.assertTrue(auth["approval"]["basis"] and auth["approval"]["reviewed_at"])
        for item in (auth["key"], auth["signature"], auth["approval"]["material"]):
            verifier.material(EVIDENCE, item)

    def test_every_retained_material_matches_its_pinned_digest(self):
        seen = 0
        for item in materials(RECORD):
            if item["path"] in CACHE_ONLY:
                continue
            path = Path(item["path"])
            root = TUP.parent if path.parts[0] == "tup" else EVIDENCE
            self.assertEqual(hashlib.sha256((root / path).read_bytes()).hexdigest(), item["sha256"], item["path"])
            seen += 1
        self.assertGreaterEqual(seen, 12)

    def test_changed_retained_key_is_refused_by_the_existing_verifier(self):
        auth = RECORD["authentication"]
        with self.assertRaisesRegex(verifier.Refusal, "SHA256 mismatch"):
            verifier.material(EVIDENCE, dict(auth["key"], sha256="0" * 64))

    def test_retained_verification_and_controls_describe_this_record(self):
        report = json.loads((EVIDENCE / "dosfstools/source-verification.json").read_bytes())
        controls = json.loads((EVIDENCE / "dosfstools/source-negative-controls.json").read_bytes())
        self.assertEqual(report["status"], "verified")
        self.assertEqual(report["record_sha256"], hashlib.sha256((BOOT / "dosfstools-source.json").read_bytes()).hexdigest())
        self.assertEqual(report["sources"][0]["sha256"], RECORD["sha256"])
        self.assertEqual(controls["status"], "passed")
        self.assertTrue(controls["cases"] and all(row["status"] == "refused-as-required" for row in controls["cases"]))

    def test_rehearsal_names_this_page_and_claims_nothing_about_the_target(self):
        rehearsal = json.loads((EVIDENCE / "dosfstools/host-rehearsal.json").read_bytes())
        self.assertEqual(rehearsal["page_sha256"], hashlib.sha256(PAGE.read_bytes()).hexdigest())
        self.assertEqual(rehearsal["status"], "host-rehearsal-not-target-qualified")
        self.assertEqual(rehearsal["upstream_check"]["summary"]["PASS"], 39)
        self.assertNotIn("/srv/", json.dumps(rehearsal))


@unittest.skipUnless(BASH, "no bash")
class DosfstoolsPageTests(unittest.TestCase):
    def test_page_is_valid_bash_with_the_runner_header(self):
        subprocess.run([BASH, "-n", str(PAGE)], check=True)
        lines = PAGE.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[:3], ["#!/bin/bash", "# TUP_TARBALL=dosfstools-4.2.tar.gz",
                                     "source /tup-layer/common.sh"])
        self.assertNotIn(b"\r", PAGE.read_bytes())

    def test_page_keeps_the_book_options_and_a_bounded_serial_check(self):
        text = PAGE.read_text(encoding="utf-8")
        for needle in ("--prefix=/usr --enable-compat-symlinks", "--mandir=/usr/share/man",
                       "--docdir=/usr/share/doc/dosfstools-4.2", "make -j\"$TUP_JOBS\"", "make -j1 check",
                       "/sources/log/dosfstools-make-check.log", "'# SKIP:  0'", "make -j1 install"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
