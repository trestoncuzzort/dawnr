"""r12 blockers A3 (the table the builder reads), A4 and A6 (what a generate run may resume into).

Each test builds the failure its guard exists for:
  - a table with rows for fewer tasks than t/tasks holds, read without a word (A3);
  - an SFT row that reaches no document, dropped with exit 0;
  - a requested id the pool lacks, skipped with exit 0 (A4);
  - a resume into raw records made with other options or another model (A6);
  - a generate run with no --temperature, which used to mean a silent 0.5.
The desktop has no torch, so cmd_generate runs against a fake torch and a fake
checkpoint module; the code under test is the bookkeeping around them.
"""
import argparse
import contextlib
import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import loop_locallm
import preflight
import surface

HERE = Path(__file__).resolve().parent
TASK = ("t 1\n"
        "task {name}(a: int) returns (r: int)\n"
        "  ensures r == a\n"
        "{{\n"
        "  r := a;\n"
        "}}\n")


def entry(fn: str, text: str) -> dict:
    return {"fn": fn, "rec": {"text": text},
            "points": [{"args": [["int", 1]], "expected": ["int", 2]},
                       {"args": [["int", 5]], "expected": ["int", 6]},
                       {"args": [["int", 0]], "expected": ["int", 1]}]}


class TempDirTestCase(unittest.TestCase):
    def tempdir(self) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        return Path(directory.name)


class ParserTests(unittest.TestCase):
    def test_generate_refuses_to_run_without_a_temperature(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            loop_locallm.build_parser().parse_args(["generate", "--tag", "x"])

    def test_generate_takes_an_explicit_temperature(self):
        a = loop_locallm.build_parser().parse_args(["generate", "--tag", "x", "--temperature", "0"])
        self.assertEqual(a.temperature, 0.0)

    def test_reply_boundary_is_one_constant(self):
        cut = loop_locallm.REPLY_BOUNDARY.split("t 1\ntask f() {}\n\nProblem: next\nt 1\n", maxsplit=1)[0]
        self.assertEqual(cut, "t 1\ntask f() {}")


class ResumeConflictTests(unittest.TestCase):
    def setUp(self):
        self.expected = {"model": "locallm:t/out/m", "checkpoint_sha256": "abc", "pool_version": "v5",
                         "prompt": "Problem: p\nSignature: f(int) -> int\n",
                         "options": {"temperature": 0.0, "top_k": 20, "max_new_tokens": 1200,
                                     "tokenizer": "Tok", "seed": 1}}
        self.record = {"model": "locallm:t/out/m", "checkpoint_sha256": "abc", "pool_version": "v5",
                       "messages": [{"role": "user", "content": self.expected["prompt"]}],
                       "options": dict(self.expected["options"])}

    def test_an_identical_record_has_no_conflict(self):
        self.assertEqual(loop_locallm.resume_conflicts(self.record, self.expected), [])

    def test_every_difference_is_named(self):
        self.record["options"]["temperature"] = 0.5
        self.record["checkpoint_sha256"] = "def"
        self.record["messages"][0]["content"] = "Problem: other\n"
        found = loop_locallm.resume_conflicts(self.record, self.expected)
        self.assertEqual(len(found), 3, found)
        self.assertIn("options.temperature: 0.5 -> 0.0", found)
        self.assertIn("checkpoint_sha256: 'def' -> 'abc'", found)
        self.assertTrue(any(c.startswith("prompt:") for c in found))

    def test_a_record_without_a_checkpoint_hash_is_a_difference(self):
        del self.record["checkpoint_sha256"]
        found = loop_locallm.resume_conflicts(self.record, self.expected)
        self.assertEqual(found, ["checkpoint_sha256: None -> 'abc'"])

    def test_two_spellings_of_one_model_directory_agree(self):
        with tempfile.TemporaryDirectory() as temp:
            d = Path(temp)
            self.assertTrue(loop_locallm._same_model_path(f"locallm:{d}", f"locallm:{d}/./"))
        self.assertFalse(loop_locallm._same_model_path("locallm:/a", "ollama:/a"))


class GenerateTests(TempDirTestCase):
    """cmd_generate with a fake torch and a fake checkpoint module."""

    def setUp(self):
        self.d = self.tempdir()
        self.model_dir = self.d / "model"
        self.model_dir.mkdir()
        (self.model_dir / "ckpt.pt").write_bytes(b"weights")
        self.split = self.d / "split.json"
        self.split.write_text(json.dumps({"pool": "v5", "eval_ids": [1, 2]}), encoding="utf-8")
        self.out = self.d / "tag"
        (self.out / "raw").mkdir(parents=True)
        self.pool = {1: entry("f", "add one"), 2: entry("g", "add one again")}

        sample = lambda model, tok, head, tokens, **kw: head + TASK.format(name="mbpp_1__f") + "\n\nProblem: x\n"
        fake_checkpoint = types.SimpleNamespace(
            load_checkpoint=lambda path: (FakeModel(), FakeTok(), None), sample=sample)
        fake_torch = types.SimpleNamespace(manual_seed=lambda seed: None)
        self.enterContext(mock.patch.dict(sys.modules, {"torch": fake_torch, "checkpoint": fake_checkpoint}))
        self.enterContext(mock.patch.object(loop_locallm.se, "pool", lambda version: self.pool))
        self.enterContext(mock.patch.object(loop_locallm.se, "outdir", lambda tag: self.out))

    def args(self, **over):
        base = dict(model=str(self.model_dir), tag="tag", ids_file="", train=False, split=str(self.split),
                    tokens=1200, temperature=0.0, top_k=20, seed=1, examples=False, use_cache=False)
        base.update(over)
        return argparse.Namespace(**base)

    def run_generate(self, a):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = loop_locallm.cmd_generate(a)
        return code, out.getvalue(), err.getvalue()

    def raw(self, tid: int) -> dict:
        return json.loads((self.out / "raw" / f"{tid}.json").read_text(encoding="utf-8"))

    def test_a_fresh_run_answers_every_id_and_records_the_checkpoint(self):
        code, out, _ = self.run_generate(self.args())
        self.assertEqual(code, 0)
        self.assertIn("2 answered now, 0 resumed", out)
        record = self.raw(1)
        self.assertEqual(record["options"]["temperature"], 0.0)
        self.assertEqual(len(record["checkpoint_sha256"]), 64)
        self.assertEqual(record["reply"], "```t\n" + TASK.format(name="mbpp_1__f").strip() + "\n```",
                         "the reply is cut at the next head")

    def test_an_id_the_pool_lacks_is_refused_before_anything_is_generated(self):
        ids = self.d / "ids.txt"
        ids.write_text("1\n2\n3\n", encoding="utf-8")
        code, _, err = self.run_generate(self.args(ids_file=str(ids)))
        self.assertEqual(code, 1)
        self.assertIn("[3]", err)
        self.assertEqual(sorted(p.name for p in (self.out / "raw").iterdir()), [])

    def test_a_resume_with_identical_options_writes_nothing_new(self):
        self.run_generate(self.args())
        before = {p.name: p.read_bytes() for p in (self.out / "raw").iterdir()}
        code, out, _ = self.run_generate(self.args())
        self.assertEqual(code, 0)
        self.assertIn("0 answered now, 2 resumed", out)
        self.assertEqual({p.name: p.read_bytes() for p in (self.out / "raw").iterdir()}, before)

    def test_a_resume_with_another_temperature_is_refused_and_writes_nothing(self):
        self.run_generate(self.args())
        (self.out / "raw" / "2.json").unlink()
        before = (self.out / "raw" / "1.json").read_bytes()
        code, _, err = self.run_generate(self.args(temperature=0.5))
        self.assertEqual(code, 2)
        self.assertIn("1: options.temperature: 0.0 -> 0.5", err)
        self.assertFalse((self.out / "raw" / "2.json").exists(), "refused before generating the missing id")
        self.assertEqual((self.out / "raw" / "1.json").read_bytes(), before)

    def test_a_resume_into_another_checkpoint_at_the_same_path_is_refused(self):
        self.run_generate(self.args())
        (self.model_dir / "ckpt.pt").write_bytes(b"retrained in place")
        code, _, err = self.run_generate(self.args())
        self.assertEqual(code, 2)
        self.assertIn("checkpoint_sha256", err)

    def test_a_truncated_raw_record_is_refused_by_name(self):
        self.run_generate(self.args())
        (self.out / "raw" / "2.json").write_text('{"task_id": 2, "opt', encoding="utf-8")
        code, _, err = self.run_generate(self.args())
        self.assertEqual(code, 2)
        self.assertIn("2: raw record unreadable", err)


class FakeModel:
    def parameters(self):
        return [types.SimpleNamespace(numel=lambda: 7)]


class FakeTok:
    pass


class AgreementCoverageTests(TempDirTestCase):
    def tasks_dir(self, names) -> Path:
        d = self.tempdir()
        for name in names:
            (d / f"{name}.t").write_text(TASK.format(name=name), encoding="utf-8")
        return d

    def table(self, names) -> Path:
        d = self.tempdir()
        cells = " | ".join([loop_locallm.CLEAN] * 7)
        rows = "\n".join(f"| {name} | {cells} |" for name in names)
        path = d / "AGREEMENT.md"
        path.write_text("| task | dafny | verus | spark | framac | lean | rocq | fstar |\n"
                        "|---|---|---|---|---|---|---|---|\n" + rows + "\n"
                        "\n| kernel | version |\n|---|---|\n| dafny | 4.11.0 |\n", encoding="utf-8")
        return path

    def test_a_table_short_of_its_tasks_names_the_missing_ones(self):
        rows, missing = loop_locallm.agreement_gap(self.table(["a"]), self.tasks_dir(["a", "b", "c"]))
        self.assertEqual(sorted(rows), ["a"])
        self.assertEqual(missing, ["b", "c"])

    def test_a_covering_table_has_no_gap(self):
        rows, missing = loop_locallm.agreement_gap(self.table(["a", "b"]), self.tasks_dir(["a", "b"]))
        self.assertEqual(missing, [])
        self.assertEqual(rows["a"], [loop_locallm.CLEAN] * 7)

    def test_an_unparseable_committed_task_is_a_refusal_by_name(self):
        d = self.tasks_dir(["a"])
        (d / "broken.t").write_text("t 1\ntask (\n", encoding="utf-8")
        with self.assertRaises(SystemExit) as caught:
            loop_locallm.committed_task_names(d)
        self.assertIn("broken.t", str(caught.exception))

    def test_preflight_fails_on_a_short_table_and_passes_on_a_covering_one(self):
        tasks = self.tasks_dir(["a", "b"])
        for table, expected in ((self.table(["a"]), False), (self.table(["a", "b"]), True)):
            with mock.patch.object(loop_locallm, "AGREEMENT", table), \
                 mock.patch.object(loop_locallm, "COMMITTED_DIR", tasks):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    self.assertIs(preflight.check_agreement_covers_tasks(), expected)
                if not expected:
                    self.assertIn("no row for ['b']", out.getvalue())

    def test_the_committed_table_in_this_checkout_is_measured_not_assumed(self):
        rows, missing = loop_locallm.agreement_gap()
        total = len(rows) + len(missing)
        self.assertEqual(total, len(list(loop_locallm.COMMITTED_DIR.glob("*.t"))))


class BuilderRefusalTests(TempDirTestCase):
    def build(self, **over):
        d = self.tempdir()
        split = d / "split.json"
        split.write_text(json.dumps({"eval_ids": [269]}), encoding="utf-8")
        base = dict(pool="v5", split=split, base="", sft=[], lifted=False, out=str(d / "corpus.txt"),
                    examples=False)
        base.update(over)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = loop_locallm.cmd_corpus(argparse.Namespace(**base))
        return code, out.getvalue(), Path(base["out"])

    def sft_row(self, task_id, chosen) -> Path:
        d = self.tempdir()
        path = d / "sft.jsonl"
        path.write_text(json.dumps({"task_id": task_id, "task": "x", "chosen": chosen}) + "\n", encoding="utf-8")
        return path

    def test_an_sft_row_outside_the_pool_is_named_not_dropped(self):
        row = self.sft_row(999999999, "```t\n" + TASK.format(name="mbpp_5__f") + "```")
        with self.assertRaises(SystemExit) as caught:
            self.build(sft=[str(row)])
        self.assertIn("task_id=999999999 is not in pool v5", str(caught.exception))

    def test_an_sft_row_without_a_fenced_block_is_named_not_dropped(self):
        pool = loop_locallm.se.pool("v5")
        task_id = sorted(int(k) for k in pool if int(k) != 269)[0]
        row = self.sft_row(task_id, "no program here")
        with self.assertRaises(SystemExit) as caught:
            self.build(sft=[str(row)])
        self.assertIn(f"task_id={task_id} has no fenced t block", str(caught.exception))

    def test_a_usable_sft_row_still_builds(self):
        pool = loop_locallm.se.pool("v5")
        task_id = sorted(int(k) for k in pool if int(k) != 269)[0]
        row = self.sft_row(task_id, "```t\n" + TASK.format(name=f"mbpp_{task_id}__f") + "```")
        code, said, out = self.build(sft=[str(row)])
        self.assertEqual(code, 0)
        self.assertIn("1 problem answers", said)
        self.assertIn(f"mbpp_{task_id}__f", out.read_text(encoding="utf-8"))

    def test_lifted_refuses_an_empty_lifted_directory(self):
        with mock.patch.object(loop_locallm, "LIFTED_DIR", self.tempdir()):
            with self.assertRaises(SystemExit) as caught:
                self.build(lifted=True)
        self.assertIn("holds none", str(caught.exception))

    def test_lifted_refuses_a_table_that_does_not_cover_the_committed_tasks(self):
        lifted = self.tempdir()
        task = surface.parse_file(str(self.write_task(lifted, "lifted_one")))
        (lifted / "lifted_one.json").write_text(json.dumps(task), encoding="utf-8")
        lifted_table = AgreementCoverageTests.table(self, ["lifted_one"])
        committed = AgreementCoverageTests.tasks_dir(self, ["c_one", "c_two"])
        short = AgreementCoverageTests.table(self, ["c_one"])
        with mock.patch.object(loop_locallm, "LIFTED_DIR", lifted), \
             mock.patch.object(loop_locallm, "LIFTED_TABLE", lifted_table), \
             mock.patch.object(loop_locallm, "COMMITTED_DIR", committed), \
             mock.patch.object(loop_locallm, "AGREEMENT", short):
            with self.assertRaises(SystemExit) as caught:
                self.build(lifted=True)
        self.assertIn("no row for ['c_two']", str(caught.exception))

    def write_task(self, directory: Path, name: str) -> Path:
        path = directory / f"{name}.t"
        path.write_text(TASK.format(name=name), encoding="utf-8")
        return path


if __name__ == "__main__":
    unittest.main()
