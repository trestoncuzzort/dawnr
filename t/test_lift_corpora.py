"""t/lift_corpora.py: released verified corpora lifted into t with their own English, gated.

The fixtures are two one-method Dafny files in the two corpora's layouts; the pool
is a fake with one held-out problem, so the behavioural twin gate can be shown to fire
and to stay quiet. The lifter runs for real (checks skipped: no dafny is needed).
"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lift_corpora                                              # noqa: E402
import spec_experiment as se                                     # noqa: E402

ABS = """method Abs(x: int) returns (y: int)
  ensures x >= 0 ==> x == y
  ensures x < 0 ==> x + y == 0
{
  if x < 0 {
    y := -x;
  } else {
    y := x;
  }
}
"""
LEMMA_USER = """lemma Helper(n: int)
  ensures n + 0 == n
{
}
method Same(x: int) returns (y: int)
  ensures y == x
{
  Helper(x);
  y := x;
}
"""


def point(x: int, expected: int) -> dict:
    return {"args": [("int", x)], "expected": ("int", expected)}


def fake_pool(held_out_points: list[dict]) -> dict:
    return {1: {"fn": "abs", "points": held_out_points, "rec": {"text": "Write a function to return the absolute value."}},
            2: {"fn": "plus", "points": [point(1, 2)], "rec": {"text": "Add one."}}}


class LiftCorporaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        v = self.tmp / "vericoding"
        (v / "vericoded").mkdir(parents=True)
        (v / "jsonl").mkdir()
        (v / "vericoded" / "DX0001_vericoded.dfy").write_text(ABS)
        (v / "vericoded" / "DX0002_vericoded.dfy").write_text(LEMMA_USER)
        (v / "jsonl" / "dafny_tasks.jsonl").write_text(
            json.dumps({"id": "DX0001", "source": "apps", "source-id": "apps_test_9",
                        "vc-description": "Return the absolute\nvalue of x."}) + "\n"
            + json.dumps({"id": "DX0002", "source": "apps", "source-id": "apps_test_10", "vc-description": "Same."}) + "\n")
        h = self.tmp / "HumanEval-Dafny"
        (h / "text-descriptions").mkdir(parents=True)
        (h / "999-absolute.dfy").write_text(ABS)
        (h / "text-descriptions" / "999-absolute.txt").write_text(
            "You have to write 1 function in dafny, using the given helper functions\n"
            "The description is as follows:\nfunction `Abs`: Return the absolute value of the argument.\n")
        self.split = self.tmp / "split.json"
        self.split.write_text(json.dumps({"eval_ids": [1], "train_ids": [2]}))

    def run_build(self, pool: dict, eval_ids=(1,)):
        self.split.write_text(json.dumps({"eval_ids": list(eval_ids), "train_ids": [2]}))
        out = self.tmp / "out"
        args = SimpleNamespace(vericoding=str(self.tmp / "vericoding"), humaneval_dafny=str(self.tmp / "HumanEval-Dafny"),
                               out=str(out), split=str(self.split), pool="v5", jobs=1, with_check=False, resume=False)
        with mock.patch.object(se, "pool", lambda name: pool), contextlib.redirect_stdout(io.StringIO()):
            census = lift_corpora.build(args)
        return out, census

    def test_the_lifted_tasks_carry_their_source_english_and_the_lemma_user_is_refused_by_name(self):
        out, census = self.run_build(fake_pool([point(5, 6), point(-3, -2)]))       # Abs fails these: no twin
        meta = out.with_name(out.name + ".meta")
        tasks = sorted(p.name for p in out.glob("*.json"))
        self.assertEqual(len(tasks), 2, tasks)
        self.assertTrue(all((meta / "sidecars" / (t[:-5] + ".lift.json")).exists() for t in tasks))
        heads = [json.loads(line) for line in (meta / "heads.jsonl").read_text().splitlines()]
        self.assertEqual(len(heads), 2)
        by_source = {h["source"]: h for h in heads}
        self.assertEqual(by_source["vericoding"]["problem"], "Return the absolute value of x.")
        self.assertEqual(by_source["vericoding"]["curation"], "source-statement")
        self.assertEqual(by_source["humaneval-dafny"]["problem"], "Return the absolute value of the argument.")
        self.assertEqual(set(heads[0]), {"name", "problem", "examples", "source", "curation", "origin"})
        self.assertEqual(census["accepted"], 2)
        self.assertEqual(census["refused"], 0)
        self.assertIn("classify:calls-other-method", census["lifter_refusals"])
        self.assertFalse(census["lifter_checks_run"])

    def test_a_program_that_passes_every_point_of_a_held_out_problem_is_refused_as_its_twin(self):
        out, census = self.run_build(fake_pool([point(5, 5), point(-3, 3), point(0, 0)]))   # Abs passes: twin of 1
        meta = out.with_name(out.name + ".meta")
        self.assertEqual([p.name for p in out.glob("*.json")], [])
        refused = [json.loads(line) for line in (meta / "refused.jsonl").read_text().splitlines()]
        self.assertEqual(len(refused), 2)
        self.assertTrue(all("gated problem 1 (held-out)" in r["reason"] for r in refused), refused)
        self.assertEqual((meta / "heads.jsonl").read_text(), "")
        self.assertEqual(census["accepted"], 0)

    def test_a_humaneval_index_that_names_a_gated_problem_is_refused_before_anything_else(self):
        pool = fake_pool([point(5, 6)])
        pool[se.HUMANEVAL_BASE + 999] = {"fn": "abs", "points": [point(5, 5)], "rec": {"text": "abs"}}
        out, census = self.run_build(pool, eval_ids=(1, se.HUMANEVAL_BASE + 999))
        refused = {r["source"]: r for r in (json.loads(line) for line in (out.with_name(out.name + ".meta") / "refused.jsonl").read_text().splitlines())}
        # the HumanEval-Dafny task is refused by the index its name carries, before any run;
        # the vericoding task has no such index and is caught by behaviour instead: it passes
        # the gated problem's point, so it is that problem's twin
        self.assertIn("names HumanEval 999, a held-out id", refused["humaneval-dafny"]["reason"])
        self.assertIn(f"gated problem {se.HUMANEVAL_BASE + 999} (held-out)", refused["vericoding"]["reason"])
        self.assertEqual(census["accepted"], 0)

    def test_a_humaneval_task_whose_pool_problem_it_passes_is_curated_by_test(self):
        pool = fake_pool([point(5, 6)])
        pool[se.HUMANEVAL_BASE + 999] = {"fn": "abs", "points": [point(5, 5), point(-2, 2)], "rec": {"text": "abs"}}
        out, census = self.run_build(pool)
        heads = {h["source"]: h for h in (json.loads(line) for line in (out.with_name(out.name + ".meta") / "heads.jsonl").read_text().splitlines())}
        self.assertEqual(heads["humaneval-dafny"]["curation"], "test")
        self.assertEqual(len(heads["humaneval-dafny"]["examples"]), 2)

    def test_the_report_is_written_from_the_meta_files(self):
        out, _census = self.run_build(fake_pool([point(5, 6)]))
        with mock.patch.object(lift_corpora, "HERE", self.tmp):
            path = lift_corpora.write_report(out)
        text = path.read_text()
        self.assertTrue(path.name.startswith("LIFT-20"), path.name)
        self.assertIn("| vericoding/apps | MIT", text)
        self.assertIn("| humaneval-dafny | Apache-2.0", text)
        self.assertIn("classify:calls-other-method", text)
        self.assertIn("NO: the machine that lifted has no dafny", text)
        self.assertIn("bash t/r12_data_queue.sh lift-2026-09-26", text)

    def test_description_parsing(self):
        self.assertEqual(lift_corpora.humaneval_description("x\nfunction `f`: Do the\n thing.\n"), "Do the thing.")
        self.assertIsNone(lift_corpora.humaneval_description("no marker here"))


if __name__ == "__main__":
    unittest.main()


class TypeKeyTests(unittest.TestCase):
    """The lifter's compound types key the gated-problem index (2026-09-26: a
    {"seq": "seq"} parameter made the signature unhashable and stopped the lift)."""

    def test_the_lifters_types_fold_like_problem_kinds(self):
        import relabel
        self.assertEqual(relabel.type_key("int"), "int")
        self.assertEqual(relabel.type_key({"seq": "seq"}), "seq")
        self.assertEqual(relabel.type_key({"pair": ["int", "int"]}), "pair(int,int)")
        task = {"params": [{"type": {"seq": "seq"}}, {"type": "int"}], "returns": [{"type": {"pair": ["bool", "int"]}}]}
        signature = relabel.task_signature(task)
        self.assertEqual(signature, (("seq", "int"), "pair(bool,int)"))
        self.assertEqual(hash(signature), hash((("seq", "int"), "pair(bool,int)")))
