"""The disagreement census must be able to find a disagreement.

It reports 0 contradictions over 3,321 graded programs. A zero from a detector
nobody tested is indistinguishable from a broken parser, and this project has
already published one zero that was a property of the search rather than of the
data (locallm/FINDINGS-completeness-2026-09-20.md). These feed it contradictions
it must catch and agreements it must not flag.
"""
import tempfile
import unittest
from pathlib import Path

import kernel_disagreement as kd

HEAD = ("| task | dafny | verus | spark | framac | lean | rocq | fstar |\n"
        "|---|---|---|---|---|---|---|---|\n")
OK = "verified / refuted"


def table(*rows):
    d = Path(tempfile.mkdtemp()) / "tag"
    d.mkdir()
    (d / "kernels.md").write_text(HEAD + "".join(rows), encoding="utf-8")
    return [d / "kernels.md"]


def row(name, *cells):
    return f"| {name} | " + " | ".join(cells) + " |\n"


class DetectorTests(unittest.TestCase):
    def test_it_catches_verified_against_refuted(self):
        t = table(row("mbpp_1__f", OK, OK, OK, OK, OK, OK, "refuted / refuted"))
        r = kd.scan(t)
        self.assertEqual(len(r["real_contradictions"]), 1)
        c = r["real_contradictions"][0]
        self.assertEqual(c["refuted"], ["fstar"])
        self.assertEqual(r["minority"]["fstar"], 1, "the lone dissenter is the one to audit")

    def test_it_catches_a_twin_that_verifies_where_others_refute(self):
        t = table(row("mbpp_2__g", OK, OK, OK, OK, OK, OK, "verified / verified"))
        r = kd.scan(t)
        self.assertEqual(len(r["twin_unsound"]), 1)
        self.assertEqual(r["twin_unsound"][0]["twin_verified"], ["fstar"])

    def test_full_agreement_is_not_flagged(self):
        r = kd.scan(table(row("mbpp_3__h", *[OK] * 7)))
        self.assertEqual(r["real_contradictions"], [])
        self.assertEqual(r["twin_unsound"], [])
        self.assertEqual(r["rows"], 1)

    def test_a_gap_is_not_a_contradiction(self):
        """unproved is not refuted: a prover that cannot decide has not disagreed."""
        t = table(row("mbpp_4__i", OK, OK, OK, OK, OK, OK, "unproved / refuted"))
        r = kd.scan(t)
        self.assertEqual(r["real_contradictions"], [], "unproved must not count as refuted")
        self.assertEqual(r["gap_majority"]["fstar"], 1)

    def test_a_flaked_suffix_does_not_hide_the_verdict(self):
        t = table(row("mbpp_5__j", OK, OK, OK, OK, OK, OK, "refuted (FLAKED) / refuted"))
        self.assertEqual(len(kd.scan(t)["real_contradictions"]), 1,
                         "a FLAKED suffix still carries its verdict word")

    def test_it_reads_the_real_tables_without_dropping_rows(self):
        """Guards the parser: a silent parse failure would also report zero."""
        from pathlib import Path as P
        tables = sorted((P(kd.__file__).parent / "out" / "spec-experiment").glob("*/kernels.md"))
        if not tables:
            self.skipTest("no graded sets present")
        r = kd.scan(tables)
        self.assertGreater(r["rows"], 1000, "the parser should see thousands of graded rows")
        self.assertGreater(sum(r["gap_majority"].values()), 0,
                           "some kernel somewhere failed to decide; zero means nothing parsed")


if __name__ == "__main__":
    unittest.main()
