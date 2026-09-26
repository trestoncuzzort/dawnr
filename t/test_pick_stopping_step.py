"""t/pick_stopping_step.py: the stopping step by dev tests, on a fixture run.

No torch: the decoder is replaced by a fake that writes the raw records a kept
checkpoint would have produced, and the pool by three small problems. Extraction
and the assertions run for real through spec_experiment and the t interpreter,
so what is tested is the selection path the real run takes after decoding.
"""
import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loop_filter                                               # noqa: E402
import pick_stopping_step as pick                                # noqa: E402
import spec_experiment as se                                     # noqa: E402

GOOD = "t 1\ntask f(a: int) returns (r: int)\n  ensures r == a + 1\n{\n  r := a + 1;\n}\n"
WRONG = "t 1\ntask f(a: int) returns (r: int)\n  ensures r == a + 2\n{\n  r := a + 2;\n}\n"
# a second problem with a different function, so a right answer to one is wrong for another
GOOD_G = "t 1\ntask g(a: int) returns (r: int)\n  ensures r == a * 2\n{\n  r := a * 2;\n}\n"
IDS = [5, 7, 11]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fake_pool():
    def problem(fn, points):
        return {"fn": fn, "rec": {"text": f"Write a function {fn}."},
                "points": [{"ok": True, "fn": fn, "args": [["int", a]], "expected": ["int", e]} for a, e in points]}
    return {5: problem("f", [(2, 3), (5, 6), (0, 1)]),
            7: problem("f", [(1, 2), (9, 10), (3, 4)]),
            11: problem("g", [(2, 4), (5, 10), (0, 0)])}


class Fixture:
    """A finished schema-2 run with three kept steps whose fake replies pass 1, 3, 3 problems."""

    def __init__(self, root: Path, replies=None, kept=(50, 100, 150)):
        self.root = root
        self.run = root / "locallm-fixture-s1"
        self.run.mkdir()
        self.split = root / "split.json"
        self.split.write_text(json.dumps({"pool": "v4", "eval_ids": [999001, 999002],
                                          "train_ids": IDS + [13]}), encoding="utf-8")
        self.dev = root / "dev-ids.json"
        self.dev.write_text(json.dumps({"schema": 1, "dev_ids": IDS,
                                        "inputs": {"split_sha256": sha(self.split)}}), encoding="utf-8")
        for step in kept:
            (self.run / f"ckpt-step-{step}.pt").write_bytes(f"weights of step {step}".encode())
        (self.run / "ckpt.pt").write_bytes(b"the rolling final checkpoint")
        (self.run / "run.json").write_text(json.dumps(
            {"schema": 2, "status": "complete", "identities": {"split_seed": 1337},
             "kept": [{"step": s, "file": f"ckpt-step-{s}.pt"} for s in kept]}), encoding="utf-8")
        # step -> {tid: reply text}; step 50 gets one problem right, the others all three
        self.replies = replies or {50: {5: GOOD, 7: WRONG, 11: WRONG},
                                   100: {5: GOOD, 7: GOOD, 11: GOOD_G},
                                   150: {5: GOOD, 7: GOOD, 11: GOOD_G}}
        self.decoded = []

    def decode(self, checkpoint: Path, tag: str, split_path: Path, ids_file: Path, args) -> int:
        step = int(checkpoint.name.split("-")[-1].split(".")[0])
        ids = [int(x) for x in ids_file.read_text().split()]
        self.decoded.append((step, tag, ids))
        d = se.outdir(tag)
        for tid in ids:
            reply = self.replies[step][tid]
            (d / "raw" / f"{tid}.json").write_text(json.dumps(
                {"task_id": tid, "fn": fake_pool()[tid]["fn"], "model": f"locallm:{checkpoint}",
                 "reply": "```t\n" + reply + "```", "done_reason": "stop"}), encoding="utf-8")
        return 0

    def argv(self, *extra):
        return ["--run", str(self.run), "--split", str(self.split), "--dev-ids", str(self.dev), *extra]


class PickStoppingStepTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.fx = Fixture(self.root)
        patches = [mock.patch.object(se, "OUT_ROOT", self.root / "spec-experiment"),
                   mock.patch.object(pick, "load_pool", lambda version: fake_pool()),
                   mock.patch.object(pick, "decode_step", self.fx.decode)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def run_main(self, *extra):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = pick.main(self.fx.argv(*extra))
        return rc, out.getvalue()

    def test_the_earliest_best_step_is_chosen_and_recorded(self):
        rc, out = self.run_main()
        self.assertEqual(rc, 0, out)
        selection = json.loads((self.fx.run / "selection.json").read_text())
        by_step = {s["step"]: s for s in selection["steps"]}
        self.assertEqual([by_step[s]["passed_problems"] for s in (50, 100, 150)], [1, 3, 3])
        # step 50: problem 5's three points, none of problem 7's (a+2 never equals a+1), and one
        # of problem 11's (a+2 == a*2 at a=2): a wrong program can still pass a point, which is
        # why problems passed is the first key and assertions only the tie-break
        self.assertEqual([by_step[s]["passed_assertions"] for s in (50, 100, 150)], [4, 9, 9])
        self.assertEqual(selection["chosen"]["step"], 100, "steps 100 and 150 tie; the earlier one wins")
        self.assertEqual(selection["chosen"]["file"], "ckpt-step-100.pt")
        self.assertIsNone(selection["installed"])
        self.assertEqual([d[0] for d in self.fx.decoded], [50, 100, 150])
        self.assertTrue(all(d[2] == IDS for d in self.fx.decoded))
        self.assertIn("chosen: step 100", out)
        # the rolling checkpoint is untouched without --install
        self.assertEqual((self.fx.run / "ckpt.pt").read_bytes(), b"the rolling final checkpoint")
        # tests.json in the grader's shape, for the record
        tests = json.loads((self.root / "spec-experiment" / "locallm-fixture-s1-dev-step50" / "tests.json").read_text())
        self.assertEqual(tests["5"]["overall"], "pass")
        self.assertEqual(tests["7"]["overall"], "fail")

    def test_install_makes_the_chosen_step_the_checkpoint_and_keeps_the_final_one(self):
        rc, _ = self.run_main("--install")
        self.assertEqual(rc, 0)
        self.assertEqual((self.fx.run / "ckpt.pt").read_bytes(), b"weights of step 100")
        self.assertEqual((self.fx.run / "ckpt-final.pt").read_bytes(), b"the rolling final checkpoint")
        record = json.loads((self.fx.run / "run.json").read_text())
        self.assertEqual(record["installed"]["step"], 100)
        self.assertEqual(record["installed"]["from"], "ckpt-step-100.pt")
        self.assertEqual(record["installed"]["final_saved_as"], "ckpt-final.pt")
        # the same choice installs again; a different one is refused
        rc, _ = self.run_main("--install")
        self.assertEqual(rc, 0)
        record["installed"]["step"] = 150
        (self.fx.run / "run.json").write_text(json.dumps(record))
        with self.assertRaises(SystemExit) as caught:
            self.run_main("--install")
        self.assertIn("already records step 150", str(caught.exception))

    def test_the_rule_on_bare_numbers(self):
        rows = [{"step": 50, "passed_problems": 1, "passed_assertions": 3},
                {"step": 100, "passed_problems": 3, "passed_assertions": 9},
                {"step": 150, "passed_problems": 3, "passed_assertions": 9}]
        self.assertEqual(pick.choose(rows)["step"], 100)
        rows[2]["passed_assertions"] = 10                        # more assertions at equal problems
        self.assertEqual(pick.choose(rows)["step"], 150)
        rows[0]["passed_problems"] = 3                           # the earliest of three equal steps
        rows[0]["passed_assertions"] = 10
        self.assertEqual(pick.choose(rows)["step"], 50)
        with self.assertRaises(SystemExit):
            pick.choose([])

    def test_a_run_that_is_not_a_finished_schema_2_continuation_is_refused(self):
        record = json.loads((self.fx.run / "run.json").read_text())
        record["schema"] = 1
        (self.fx.run / "run.json").write_text(json.dumps(record))
        with self.assertRaises(SystemExit) as caught:
            self.run_main()
        self.assertIn("schema 1", str(caught.exception))
        record["schema"], record["status"] = 2, "running"
        (self.fx.run / "run.json").write_text(json.dumps(record))
        with self.assertRaises(SystemExit) as caught:
            self.run_main()
        self.assertIn("not complete", str(caught.exception))

    def test_no_kept_step_and_a_stray_kept_file_are_refused(self):
        record = json.loads((self.fx.run / "run.json").read_text())
        record["kept"] = []
        (self.fx.run / "run.json").write_text(json.dumps(record))
        with self.assertRaises(SystemExit) as caught:
            self.run_main()
        self.assertIn("does not name", str(caught.exception))    # the files on disk are unaccounted for
        for p in self.fx.run.glob("ckpt-step-*.pt"):
            p.unlink()
        with self.assertRaises(SystemExit) as caught:
            self.run_main()
        self.assertIn("kept no checkpoints", str(caught.exception))

    def test_a_held_out_listed_or_foreign_dev_id_is_refused_before_any_decoding(self):
        listed = sorted(loop_filter.decontamination().exclude_train_ids)[0]
        for bad, phrase in ((999001, "held-out"), (listed, "decontamination list"), (13000, "not train problems")):
            split = json.loads(self.fx.split.read_text())
            split["train_ids"] = IDS + ([listed] if bad == listed else [])
            self.fx.split.write_text(json.dumps(split))
            self.fx.dev.write_text(json.dumps({"schema": 1, "dev_ids": IDS + [bad],
                                               "inputs": {"split_sha256": sha(self.fx.split)}}))
            with self.subTest(bad=bad):
                with self.assertRaises(SystemExit) as caught:
                    self.run_main()
                self.assertIn(phrase, str(caught.exception))
                self.assertEqual(self.fx.decoded, [])

    def test_a_dev_split_drawn_from_another_split_is_refused(self):
        self.fx.dev.write_text(json.dumps({"schema": 1, "dev_ids": IDS, "inputs": {"split_sha256": "0" * 64}}))
        with self.assertRaises(SystemExit) as caught:
            self.run_main()
        self.assertIn("digest", str(caught.exception))
        self.assertEqual(self.fx.decoded, [])

    def test_an_ids_file_replaces_the_dev_split_and_is_gated_the_same_way(self):
        ids = self.root / "ids.txt"
        ids.write_text("5\n7\n")
        rc, _ = self.run_main("--ids-file", str(ids))
        self.assertEqual(rc, 0)
        self.assertEqual(self.fx.decoded[0][2], [5, 7])
        ids.write_text("5\n999002\n")
        self.fx.decoded.clear()
        with self.assertRaises(SystemExit):
            self.run_main("--ids-file", str(ids))
        self.assertEqual(self.fx.decoded, [])

    def test_a_generate_failure_stops_the_selection(self):
        with mock.patch.object(pick, "decode_step", lambda *a, **k: 1):
            with self.assertRaises(SystemExit) as caught:
                self.run_main()
        self.assertIn("generate exited 1", str(caught.exception))
        self.assertFalse((self.fx.run / "selection.json").exists())


if __name__ == "__main__":
    unittest.main()
