"""t/pilot_sampling.py without torch: the ids it picks, the boundary it stops at,
the prompt it builds, and the files it writes and refuses."""
import inspect
import json
import random
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import loop_filter  # noqa: E402
import loop_locallm  # noqa: E402
import pilot_sampling as ps  # noqa: E402

PINNED = [3, 39, 74, 126, 179, 224, 275, 322, 362, 436, 482, 531, 575, 633, 670, 734, 782, 837, 876, 914]


class IdTests(unittest.TestCase):
    def test_the_clean_200_and_the_20_pinned_pilot_ids(self):
        if not ps.SPLIT.exists():
            self.skipTest(f"{ps.SPLIT} absent")
        clean = ps.clean_ids()
        self.assertEqual(len(clean), 200)
        self.assertEqual(ps.pilot_ids(clean), PINNED)
        self.assertEqual(sorted(set(PINNED) & ps.weak_test_ids()), [179, 362])

    def test_seeds_differ_per_problem_temperature_and_batch(self):
        seeds = {ps.derive_seed(1, tid, t, b) for tid in (3, 39) for t in (0.4, 0.8) for b in (0, 1)}
        self.assertEqual(len(seeds), 8)
        self.assertEqual(ps.derive_seed(1, 3, 0.4), ps.derive_seed(1, 3, 0.4, 0))


class BoundaryTests(unittest.TestCase):
    def test_the_boundary_is_the_one_cmd_generate_cuts_at(self):
        exported = getattr(loop_locallm, "REPLY_BOUNDARY", None)
        if exported is not None:
            self.assertEqual(exported.pattern, ps.REPLY_BOUNDARY.pattern)
        else:
            source = inspect.getsource(loop_locallm.cmd_generate)
            self.assertIn(repr(ps.BOUNDARY_PATTERN)[1:-1].replace("\\\\", "\\"), source.replace("\\\\", "\\"))

    def test_stopping_at_the_first_prefix_that_matches_extracts_the_same_reply(self):
        """A prefix that contains a boundary match yields the same extracted reply as the
        full text, so a stop at the first such prefix is exact. 3,000 random texts over
        pieces that include every head this project writes and long whitespace runs."""
        pieces = ["t 1\n", "task f(x: int) returns (r: int)\n", "{\n", "  r := x;\n", "}\n", "\n", "\n\n",
                  "   \n", " ", "Problem: x\n", "Signature: f(int) -> int\n", "Example: f(1) == 2\n", "t 2\n",
                  "\t\n", "abc", "\n \n \n"]
        rng = random.Random(1039)
        head = "Problem: p\nSignature: f(int) -> int\n"
        stops, misses = 0, 0
        for _ in range(3000):
            body = "".join(rng.choice(pieces) for _ in range(rng.randint(1, 14)))
            text = head + body
            # tokens of random length, as a tokenizer would cut them
            cuts, at = [], 0
            while at < len(text):
                at = min(len(text), at + rng.randint(1, 6))
                cuts.append(at)
            first = next((c for c in cuts if ps.reply_cut(head, text[:c]) is not None), None)
            if first is None:
                self.assertIsNone(ps.reply_cut(head, text))
                misses += 1
                continue
            stops += 1
            self.assertEqual(ps.extract_reply(head, text[:first]), ps.extract_reply(head, text))
            # and the cut index is the same one the full text reports
            self.assertEqual(ps.reply_cut(head, text[:first]), ps.reply_cut(head, text))
        self.assertGreater(stops, 500)
        self.assertGreater(misses, 100)

    def test_a_boundary_inside_the_head_does_not_count(self):
        head = "Problem: p\n\nSignature: f(int) -> int\n"
        self.assertIsNone(ps.reply_cut(head, head + "t 1\ntask f"))
        self.assertEqual(ps.reply_cut(head, head + "t 1\n}\n\nProblem: q"), len(head) + len("t 1\n}"))

    def test_extract_reply_is_cmd_generates(self):
        head = "Problem: p\nSignature: f(int) -> int\n"
        text = head + "Example: f(1) == 1\nt 1\ntask f(x: int) returns (r: int)\n{\n  r := x;\n}\n\n\nt 1\ntask g"
        self.assertEqual(ps.extract_reply(head, text), "t 1\ntask f(x: int) returns (r: int)\n{\n  r := x;\n}")
        self.assertEqual(loop_filter.strip_head("Example: f(1) == 1\nt 1\n"), "t 1\n")


class PromptTests(unittest.TestCase):
    def test_the_prompt_is_problem_head(self):
        entry = {"fn": "f", "rec": {"text": "Add  one\nto x."},
                 "points": [{"args": [["int", 1]], "expected": ["int", 2]}, {"args": [["int", 5]], "expected": ["int", 6]}]}
        self.assertEqual(loop_locallm.problem_head(entry, False), "Problem: Add one to x.\nSignature: f(int) -> int\n")
        self.assertTrue(loop_locallm.problem_head(entry, True).startswith(loop_locallm.problem_head(entry, False)))


def fake_pool():
    entry = {"fn": "f", "rec": {"text": "p"}, "points": [{"args": [["int", 1]], "expected": ["int", 2]}]}
    return {3: dict(entry), 39: dict(entry), 20: dict(entry)}


def fake_sample_rows(model, tok, head, k, *, tokens, temperature, top_k, seed, task_id, rows_per_batch, device):
    return [{"text": head + f"t 1\ntask f{n}\n\nProblem: next", "new_tokens": 9, "stopped": True, "reply_tokens": 7,
             "logprob_sum": -3.5, "mean_logprob": -0.5, "mean_logprob_all": -0.6} for n in range(k)]


class FakeModel:
    def parameters(self):
        import types
        return iter([types.SimpleNamespace(device=types.SimpleNamespace(type="cpu"))])


class WritingTests(unittest.TestCase):
    """main() end to end with the sampler and the checkpoint loader replaced: no torch."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        (root / "model").mkdir()
        (root / "model" / "ckpt.pt").write_bytes(b"not a checkpoint")
        split = {"pool": "v5", "eval_ids": [3, 39, 20, 45], "train_ids": []}
        (root / "split.json").write_text(json.dumps(split))
        (root / "decontam.json").write_text(json.dumps({"overlap_ids": [20, 45], "weak_test_eval_ids": [39]}))
        self.root = root
        fake_checkpoint = mock.MagicMock()
        fake_checkpoint.load_checkpoint.return_value = (FakeModel(), object(), None)
        self.patches = [mock.patch.object(ps.se, "pool", lambda version: fake_pool()),
                        mock.patch.object(ps, "sample_rows", fake_sample_rows),
                        mock.patch.dict(sys.modules, {"torch": mock.MagicMock(), "checkpoint": fake_checkpoint})]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def run_main(self, *extra):
        return ps.main(["--model", str(self.root / "model"), "--out", str(self.root / "out"),
                        "--split", str(self.root / "split.json"), "--decontam", str(self.root / "decontam.json"),
                        "--k", "2", "--temperatures", "0.4", "0.8", "--top-k", "20", "--tokens", "50", *extra])

    def test_writes_one_file_per_problem_and_temperature_with_identical_options(self):
        self.assertEqual(self.run_main("--ids", "3", "39"), 0)
        for temperature in ("0.4", "0.8"):
            for tid in (3, 39):
                path = self.root / "out" / f"temperature-{temperature}" / "candidates" / f"{tid}.jsonl"
                lines = [json.loads(line) for line in path.read_text().splitlines()]
                self.assertEqual(len(lines), 2)
                self.assertEqual([line["sample"] for line in lines], [0, 1])
                self.assertEqual(len({json.dumps(line["options"], sort_keys=True) for line in lines}), 1)
                self.assertEqual(lines[0]["options"]["temperature"], float(temperature))
                self.assertEqual(lines[0]["options"]["stop"], "reply-boundary")
                self.assertEqual(lines[0]["weak_test"], tid == 39)
                self.assertEqual(lines[0]["reply_tokens"], 7)
                self.assertNotIn(str(self.root), json.dumps(lines[0]))    # no workstation paths in a record
        # the same run again skips every existing file
        self.assertEqual(self.run_main("--ids", "3", "39"), 0)

    def test_different_options_are_refused(self):
        self.run_main("--ids", "3")
        with self.assertRaises(SystemExit) as caught:
            self.run_main("--ids", "3", "--seed", "2")
        self.assertIn("different options", str(caught.exception))

    def test_refusals(self):
        with self.assertRaises(SystemExit):
            ps.main(["--model", str(self.root / "model"), "--out", str(self.root / "out"), "--k", "4",
                     "--temperatures", "0", "--top-k", "20", "--split", str(self.root / "split.json"),
                     "--decontam", str(self.root / "decontam.json")])            # T=0 with k>1
        with self.assertRaises(SystemExit) as caught:
            self.run_main("--ids", "20")                                             # an overlap id
        self.assertIn("same-task", str(caught.exception))
        self.assertEqual(self.run_main("--ids", "20", "--allow-contaminated"), 0)
        with self.assertRaises(SystemExit) as caught:
            self.run_main("--ids", "999")                                            # not in the pool
        self.assertIn("not in pool", str(caught.exception))
        with self.assertRaises(SystemExit):
            ps.main(["--model", "m", "--out", "o", "--k", "2", "--top-k", "20"])   # no --temperatures

    def test_default_ids_are_every_tenth_clean_id_of_the_split(self):
        self.assertEqual(self.run_main(), 0)
        written = sorted(int(p.stem) for p in (self.root / "out" / "temperature-0.4" / "candidates").glob("*.jsonl"))
        self.assertEqual(written, ps.pilot_ids([3, 39]))
        self.assertEqual(written, [3])                       # never an overlap id (20, 45) by default


if __name__ == "__main__":
    unittest.main()
