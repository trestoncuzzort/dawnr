"""A corpus must not contain a problem the model will be evaluated on.

Issue #30: the builder applied no split filter at all. `--sft` trusted its input
file and `--lifted` added MBPP-DFY-derived tasks unchecked, and MBPP-DFY comes
from the same MBPP the held-out split is drawn from, so nothing but luck kept an
evaluation problem out of training. Luck held when it was measured on
2026-09-20 (0 of 232 held-out ids across six corpora), which is exactly the
situation in which a guard gets left unwritten.

t/preflight.py catches a leak after the fact. These tests cover the point the
corpus is built, which is the last moment it can be caught before a model has
already read the problem.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import loop_locallm

HERE = Path(__file__).resolve().parent
SPLIT = HERE / "out" / "loop" / "split-v5.json"
PROGRAM = "task mbpp_{i}__f(a: int) returns (r: int)\n  ensures r == a\n{{\n  r := a;\n}}\n"


def build(base_text, extra):
    d = Path(tempfile.mkdtemp())
    base = d / "base.txt"
    base.write_text(base_text, encoding="utf-8")
    out = d / "corpus.txt"
    r = subprocess.run([sys.executable, str(HERE / "loop_locallm.py"), "corpus", "--pool", "v5",
                        "--base", str(base), "--out", str(out), *extra],
                       capture_output=True, text=True, cwd=HERE)
    if r.returncode:
        raise AssertionError(r.stderr)
    return out.read_text(encoding="utf-8"), r.stdout


class SplitFilterTests(unittest.TestCase):
    def setUp(self):
        if not SPLIT.exists():
            self.skipTest(f"{SPLIT} not present")
        evil = sorted(int(i) for i in json.loads(SPLIT.read_text())["eval_ids"])
        self.held = evil[0]
        self.safe = sorted(set(range(1, 2000)) - set(evil))[0]
        self.base = ("t 1\n" + PROGRAM.format(i=self.held) + "\n\n"
                     "t 1\n" + PROGRAM.format(i=self.safe) + "\n")

    def test_a_held_out_problem_never_reaches_the_corpus(self):
        text, said = build(self.base, ["--split", str(SPLIT)])
        self.assertNotIn(f"mbpp_{self.held}__", text, "a held-out problem reached the corpus")
        self.assertIn(f"mbpp_{self.safe}__", text, "the filter dropped a problem it should keep")
        self.assertIn("1 document(s) excluded", said)

    def test_without_a_split_nothing_is_filtered_and_it_says_so(self):
        """The old behaviour, unchanged, so no existing caller is silently altered."""
        text, said = build(self.base, [])
        self.assertIn(f"mbpp_{self.held}__", text)
        self.assertIn("NOT APPLIED", said)

    def test_the_id_reader_only_matches_real_task_names(self):
        self.assertEqual(loop_locallm.mbpp_id("mbpp_269__foo"), 269)
        self.assertEqual(loop_locallm.mbpp_id("mbpp_4__heap_queue_largest"), 4)
        self.assertIsNone(loop_locallm.mbpp_id("not_an_mbpp_task"))
        self.assertIsNone(loop_locallm.mbpp_id(""))
        self.assertIsNone(loop_locallm.mbpp_id(None))

    def test_an_unreadable_split_stops_the_build_instead_of_filtering_nothing(self):
        """Silently filtering nothing is how a leak gets built; fail loudly."""
        with self.assertRaises(SystemExit):
            loop_locallm.held_out(str(HERE / "out" / "loop" / "no-such-split.json"))


if __name__ == "__main__":
    unittest.main()
