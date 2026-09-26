"""t/negatives_from_spec_disagreements.py: pairs through the r12 gates, refusals by name.

Runs without torch or the real pools: the pool is a five-entry stand-in patched
over spec_experiment.pool; the split, verdicts, positives, dev ids and
decontamination policy are written into a temporary directory.
"""
import argparse
import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import loop_filter                                              # noqa: E402
import negatives_from_spec_disagreements as neg                 # noqa: E402
import spec_check                                               # noqa: E402
import surface                                                  # noqa: E402

TRAIN_ID, HELD_ID, DEV_ID, EXCLUDED_ID, LONELY_ID = 8, 122, 17, 35, 52


def program(name: str, expr: str, param: str = "n") -> str:
    return (f"t 0\ntask {name}({param}: int) returns (r: int)\n"
            f"  ensures r == {expr}\n{{\n  r := {expr};\n}}")


def sha(text: str) -> str:
    return spec_check.task_sha256(surface.parse(text))


def entry(task_id: int, text: str, fn: str) -> dict:
    # one parsed assertion, the shape spec_experiment.pool() gives: loop_locallm.signature reads points[0]
    return {"rec": {"task_id": task_id, "text": text, "test_list": [f"assert {fn}(3) == 6"]},
            "points": [{"ok": True, "fn": fn, "args": [("int", 3)], "expected": ("int", 6)}], "fn": fn}


POOL = {TRAIN_ID: entry(TRAIN_ID, "Write a function to double a number.", "double"),
        HELD_ID: entry(HELD_ID, "Write a function to find the nth smart number.", "smartNumber"),
        DEV_ID: entry(DEV_ID, "Write a function to find the perimeter of a square.", "square_perimeter"),
        EXCLUDED_ID: entry(EXCLUDED_ID, "Write a function to find the n-th rectangular number.", "find_rect_num"),
        LONELY_ID: entry(LONELY_ID, "Write a function to triple a number.", "triple")}

POSITIVE = program(f"mbpp_{TRAIN_ID}__double", "2 * n")
NEGATIVE = program(f"mbpp_{TRAIN_ID}__double", "n + n + 1")
HELD_NEGATIVE = program(f"mbpp_{HELD_ID}__smartNumber", "n * (3 * n - 2)")
DEV_NEGATIVE = program(f"mbpp_{DEV_ID}__square_perimeter", "5 * n")
EXCLUDED_NEGATIVE = program(f"mbpp_{EXCLUDED_ID}__find_rect_num", "n * n")
LONELY_NEGATIVE = program(f"mbpp_{LONELY_ID}__triple", "4 * n")


def verdict(task_id: int, text: str, status: str, pool: str = "v5") -> dict:
    return {"status": status, "task_id": task_id, "task_sha256": sha(text), "pool": pool, "draws": 100,
            "seed": 1, "attempts": 100, "args": [3], "reference_said": 6, "ensures": 7}


def sft_row(task_id: int, name: str, text: str) -> str:
    return json.dumps({"task_id": task_id, "task": name, "chosen": f"```t\n{text}\n```",
                       "prompt": [], "source": "samples"}) + "\n"


class Fixture:
    def __init__(self, root: Path):
        self.root = root
        self.split = root / "split.json"
        self.split.write_text(json.dumps({"pool": "v5", "eval_ids": [HELD_ID],
                                          "train_ids": [TRAIN_ID, DEV_ID, EXCLUDED_ID, LONELY_ID]}))
        self.dev = root / "dev.json"
        self.dev.write_text(json.dumps({"dev_ids": [DEV_ID], "inputs": {
            "split_sha256": hashlib.sha256(self.split.read_bytes()).hexdigest()}}))
        self.decon = root / "decon.json"
        self.decon.write_text(json.dumps({"drop_documents": {"lift:clover_x__y": "reason"},
                                          "exclude_future_train_ids": [EXCLUDED_ID], "overlap_ids": [HELD_ID]}))
        self.pool_file = root / "sft.jsonl"
        self.pool_file.write_text(sft_row(TRAIN_ID, f"mbpp_{TRAIN_ID}__double", POSITIVE))
        self.disagree = root / "spec-disagree.json"
        self.results = {
            "teacher/mbpp_8__double": verdict(TRAIN_ID, POSITIVE, "agrees"),
            "student/mbpp_8__double": verdict(TRAIN_ID, NEGATIVE, "disagrees"),
            "student/mbpp_122__smartNumber": verdict(HELD_ID, HELD_NEGATIVE, "disagrees"),
            "student/mbpp_17__square_perimeter": verdict(DEV_ID, DEV_NEGATIVE, "disagrees"),
            "student/mbpp_35__find_rect_num": verdict(EXCLUDED_ID, EXCLUDED_NEGATIVE, "disagrees"),
            "student/mbpp_52__triple": verdict(LONELY_ID, LONELY_NEGATIVE, "disagrees"),
            "old/mbpp_8__double": verdict(TRAIN_ID, NEGATIVE, "disagrees", pool="v3"),
        }
        self.programs = {"student/mbpp_8__double": NEGATIVE, "student/mbpp_122__smartNumber": HELD_NEGATIVE,
                         "student/mbpp_17__square_perimeter": DEV_NEGATIVE,
                         "student/mbpp_35__find_rect_num": EXCLUDED_NEGATIVE,
                         "student/mbpp_52__triple": LONELY_NEGATIVE, "old/mbpp_8__double": NEGATIVE}
        self.write_disagree()
        self.out = root / "pairs.jsonl"
        self.report = root / "report.md"

    def write_disagree(self):
        self.disagree.write_text(json.dumps({"results": self.results, "programs": self.programs}))

    def argv(self, *extra):
        return ["--split", str(self.split), "--pool-file", str(self.pool_file), "--spec-disagree", str(self.disagree),
                "--out", str(self.out), "--report", str(self.report), "--dev-ids", str(self.dev),
                "--decontamination", str(self.decon), *extra]


def build_args(fx: Fixture, examples: bool = False) -> argparse.Namespace:
    """The namespace neg.build reads, as neg.main's parser would fill it from fx.argv()."""
    return argparse.Namespace(split=str(fx.split), pool_file=[str(fx.pool_file)], spec_disagree=str(fx.disagree),
                              out=str(fx.out), report=str(fx.report), examples=examples,
                              dev_ids=str(fx.dev), decontamination=str(fx.decon))


class NegativesTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.fx = Fixture(Path(directory.name))
        patcher = mock.patch.object(neg.se, "pool", lambda version="v1": dict(POOL))
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_main(self, *extra) -> str:
        stream = io.StringIO()
        with redirect_stdout(stream):
            code = neg.main(self.fx.argv(*extra))
        self.assertEqual(code, 0)
        return stream.getvalue()

    def pairs(self) -> list[dict]:
        return [json.loads(line) for line in self.fx.out.read_text().splitlines()]

    def test_one_pair_for_the_train_side_problem_with_the_corpus_head_as_prompt(self):
        out = self.run_main()
        pairs = self.pairs()
        self.assertEqual([p["task_id"] for p in pairs], [TRAIN_ID])
        pair = pairs[0]
        self.assertEqual(pair["prompt"], "Problem: Write a function to double a number.\nSignature: double(int) -> int\n")
        self.assertEqual(pair["chosen"], POSITIVE)
        self.assertEqual(pair["rejected"], NEGATIVE)
        self.assertEqual(pair["provenance"]["negative"]["key"], "student/mbpp_8__double")
        self.assertEqual(pair["provenance"]["positive"]["spec"], "teacher/mbpp_8__double")
        self.assertEqual(pair["provenance"]["negative"]["status"], "disagrees")
        self.assertEqual(pair["provenance"]["pool"], "v5")
        self.assertIn("pairs written** | **1**", self.fx.report.read_text())
        self.assertIn("1 written from 6 disagreeing rows", out)

    def test_the_held_out_dev_and_same_task_ids_are_refused_by_name_not_dropped(self):
        out = self.run_main()
        report = self.fx.report.read_text()
        for reason, key in (("held-out", "student/mbpp_122__smartNumber"),
                            ("dev-split", "student/mbpp_17__square_perimeter"),
                            ("same-task", "student/mbpp_35__find_rect_num"),
                            ("pool-mismatch", "old/mbpp_8__double"),
                            ("no-positive", "student/mbpp_52__triple")):
            self.assertIn(f"refused {reason}: {key}", out)
            self.assertIn(f"## Refused: {reason} (1)", report)
        self.assertNotIn(HELD_ID, [p["task_id"] for p in self.pairs()])
        text = "".join(p["prompt"] + p["chosen"] + p["rejected"] for p in self.pairs())
        self.assertTrue(loop_filter.validate_training_data(text, {HELD_ID, DEV_ID}).ok)

    def test_a_positive_without_an_agreeing_verdict_is_refused(self):
        del self.fx.results["teacher/mbpp_8__double"]
        self.fx.write_disagree()
        out = self.run_main()
        self.assertEqual(self.pairs(), [])
        self.assertIn("refused positive-not-spec-checked: student/mbpp_8__double against sft.jsonl:1", out)

    def test_a_pool_file_positive_that_a_verdict_says_disagrees_stops_the_build(self):
        self.fx.results["teacher/mbpp_8__double"]["status"] = "disagrees"
        self.fx.write_disagree()
        with self.assertRaises(SystemExit) as caught:
            neg.main(self.fx.argv())
        self.assertIn("contradict", str(caught.exception))
        self.assertFalse(self.fx.out.exists())

    def test_a_stale_program_hash_stops_the_build(self):
        self.fx.programs["student/mbpp_8__double"] = program("mbpp_8__double", "n + n + 2")
        self.fx.write_disagree()
        with self.assertRaises(SystemExit) as caught:
            neg.main(self.fx.argv())
        self.assertIn("stale", str(caught.exception))

    def test_a_split_without_a_pool_is_refused(self):
        self.fx.split.write_text(json.dumps({"eval_ids": [HELD_ID], "train_ids": [TRAIN_ID]}))
        with self.assertRaises(SystemExit) as caught:
            neg.main(self.fx.argv())
        self.assertIn("pool", str(caught.exception))

    def test_the_same_pair_under_a_second_tag_is_refused_as_a_duplicate_by_name(self):
        # the same disagreeing program graded again under another tag (as
        # qwen235-heldout and qwen235-heldout-p5 both carry mbpp_355)
        self.fx.results["student2/mbpp_8__double"] = verdict(TRAIN_ID, NEGATIVE, "disagrees")
        self.fx.programs["student2/mbpp_8__double"] = NEGATIVE
        self.fx.write_disagree()
        out = self.run_main()
        pairs = self.pairs()
        self.assertEqual([p["task_id"] for p in pairs], [TRAIN_ID])
        self.assertEqual(pairs[0]["provenance"]["negative"]["key"], "student/mbpp_8__double")
        self.assertIn("refused duplicate: student2/mbpp_8__double against sft.jsonl:1 "
                      "(the same pair was written from student/mbpp_8__double)", out)
        self.assertIn("1 written from 7 disagreeing rows", out)
        self.assertIn("duplicate 1", out)
        report = self.fx.report.read_text()
        self.assertIn("| refused: duplicate | 1 |", report)
        self.assertIn("## Refused: duplicate (1)", report)
        # every disagreeing row is a pair or a named refusal
        counts = neg.build(build_args(self.fx))[1]["counts"]
        self.assertEqual(counts["disagreeing"],
                         counts["pairs"] + sum(counts["refused:" + reason] for reason in neg.REFUSALS))

    def test_examples_go_into_the_head_when_asked(self):
        self.run_main("--examples")
        pair = self.pairs()[0]
        self.assertTrue(pair["prompt"].endswith("Signature: double(int) -> int\nExample: double(3) == 6\n"))
        self.assertTrue(pair["provenance"]["examples"])


if __name__ == "__main__":
    unittest.main()
