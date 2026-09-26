"""English heads from sources that exist (t/heads_from_sources.py) and their
application by `loop_locallm.py corpus --heads` (r12 data build, plan B.2).

Every test builds its fixtures in a temporary directory: a lifted-task
directory in the lifter's <stem>.<method>.json layout, a seven-kernel table
whose clean rows are the documents, a pool with test points, a Clover dataset
directory and a DafnyBench ground-truth directory. Nothing here reads the real
pools or corpora; the real extraction runs on the lab (t/HEADS-2026-09-25.md).
"""
import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import heads_from_sources as H
import loop_filter
import loop_locallm
import surface

HERE = Path(__file__).resolve().parent
TASK = ("t 1\n"
        "task {name}(a: int) returns (r: int)\n"
        "  ensures r == a\n"
        "{{\n"
        "  r := a;\n"
        "}}\n")
POINTS = [{"ok": True, "fn": "f", "args": [["int", 3]], "expected": ["int", 3]},
          {"ok": True, "fn": "f", "args": [["int", 7]], "expected": ["int", 7]}]
WRONG_POINTS = [{"ok": True, "fn": "f", "args": [["int", 3]], "expected": ["int", 4]}]
DFY = """// Return the value that was given, unchanged.
method Bar(a: int) returns (r: int)
  ensures r == a
{
  r := a;
}

// A description that a blank line separates from its method.

method Sep(a: int) returns (r: int)
  ensures r == a
{
  r := a;
}

// Invariante significa que o valor não muda desde a pré-condição
method Pt(a: int) returns (r: int)
  ensures r == a
{
  r := a;
}

method Bare(a: int) returns (r: int)
  ensures r == a
{
  r := a;
}

method Doc(a: int) returns (r: int)
  // Returns the argument as the result of the method.
  ensures r == a
{
  r := a;
}

// n>=1 ==> 1 + 3 + 5 + ... + (2*n-1) = n*n
method Formula(a: int) returns (r: int)
  ensures r == a
{
  r := a;
}
"""


def pool_entry(text, points):
    return {"rec": {"text": text}, "points": points, "fn": "f"}


class Fixture(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.dir = Path(d.name)
        self.lifted = self.dir / "lifted"
        self.lifted.mkdir()
        self.clover = self.dir / "clover"
        self.gt = self.dir / "gt"
        self.gt.mkdir()
        self.split = self.dir / "split.json"
        self.split.write_text(json.dumps({"eval_ids": [269]}), encoding="utf-8")
        self.pool = {5: pool_entry("Write a function that returns its input.", POINTS),
                     6: pool_entry("Write a function that adds one.", WRONG_POINTS),
                     269: pool_entry("A held-out problem.", POINTS)}
        self.names = []

    def lift(self, stem, method, name):
        task = surface.parse(TASK.format(name=name))
        (self.lifted / f"{stem}.{method}.json").write_text(json.dumps(task), encoding="utf-8")
        self.names.append(name)
        return task

    def table(self, names=None) -> Path:
        names = self.names if names is None else names
        cells = " | ".join([loop_locallm.CLEAN] * 7)
        path = self.dir / "COVERAGE.md"
        path.write_text("| task | dafny | verus | spark | framac | lean | rocq | fstar |\n"
                        "|---|---|---|---|---|---|---|---|\n"
                        + "".join(f"| {n} | {cells} |\n" for n in names), encoding="utf-8")
        return path

    def spec(self, directory, text):
        (self.clover / directory).mkdir(parents=True, exist_ok=True)
        (self.clover / directory / f"{directory}_spec.txt").write_text(text, encoding="utf-8")

    def build(self, table=None):
        return H.build(self.lifted, table or self.table(), self.split, self.pool, self.clover, self.gt)


class EnglishTests(unittest.TestCase):
    def test_english_prose_passes_and_the_reason_counts_function_words(self):
        ok, why = H.english_verdict("Return the value of the minimum element in a non-empty array.")
        self.assertTrue(ok, why)
        self.assertIn("function word", why)

    def test_the_rules_refuse_what_is_not_english_prose(self):
        cases = {
            "Invariante significa que o valor não muda": "non-ascii letter",
            "PROGRAMA VERIFICADOR DE WHILE": "no English function word",
            "n>=1 ==> 1 + 3 + 5 + ... + (2*n-1) = n*n": "code operator",
            "}": "code operator",
            "...": "0 word(s)",
            "this file.": "2 word(s)",
            "RUN: %dafny /compile:0 \"%s\"": "administrative line",
            "": "empty",
        }
        for text, reason in cases.items():
            ok, why = H.english_verdict(text)
            self.assertFalse(ok, text)
            self.assertEqual(why, reason, text)


class DescriptionTests(unittest.TestCase):
    def test_english_that_addresses_the_exercise_is_meta_commentary(self):
        cases = {
            "Annotate this method with pre- and postconditions that ensure it behaves as described.": "annotate",
            "Exercise 1. Write a test method that calls your Max method.": "exercise",
            "Indicates returned object is newly created in method body": "newly created",
            "use this instead of line 3,4": "instead of",
            "do not change do not change": "do not change",
            "Simple Assignment Example based on the code used in the course overheads": "assignment",
        }
        for text, word in cases.items():
            ok, why = H.description_verdict(text)
            self.assertFalse(ok, text)
            self.assertEqual(why, f"meta-commentary ({word})", text)

    def test_a_description_of_the_method_passes_both_tests(self):
        ok, why = H.description_verdict("Return a minimum of a.")
        self.assertTrue(ok, why)
        ok, why = H.description_verdict("Invariante significa que o valor não muda")
        self.assertFalse(ok)
        self.assertEqual(why, "non-ascii letter")


class DafnyCommentTests(unittest.TestCase):
    def test_a_block_ending_right_above_the_header_is_taken(self):
        text, reason = H.dafnybench_comment(DFY, "Bar")
        self.assertEqual(text, "Return the value that was given, unchanged.")
        self.assertEqual(reason, "block above")

    def test_a_blank_line_breaks_the_attachment(self):
        text, reason = H.dafnybench_comment(DFY, "Sep")
        self.assertIsNone(text)
        self.assertEqual(reason, "comment separated by a blank line")

    def test_a_comment_between_header_and_body_is_the_dafny_doc_comment(self):
        text, reason = H.dafnybench_comment(DFY, "Doc")
        self.assertEqual(text, "Returns the argument as the result of the method.")
        self.assertEqual(reason, "between header and body")

    def test_no_comment_and_no_method_are_told_apart(self):
        self.assertEqual(H.dafnybench_comment(DFY, "Bare"), (None, "no comment"))
        self.assertEqual(H.dafnybench_comment(DFY, "Missing"), (None, "method not found"))

    def test_block_comment_markers_are_stripped_the_way_dafny_strips_them(self):
        src = "/** Swaps the two values.\n *  Nothing else changes. */\nmethod Swap(a: int) returns (r: int)\n{\n}\n"
        self.assertEqual(H.dafnybench_comment(src, "Swap"), ("Swaps the two values. Nothing else changes.", "block above"))


class BuildTests(Fixture):
    def test_an_mbpp_lift_gets_the_problem_english_and_examples_only_when_its_points_pass(self):
        self.lift("dafny-synthesis_task_id_5", "F", "dafny_synthesis_task_id_5__f")
        self.lift("dafny-synthesis_task_id_6", "F", "dafny_synthesis_task_id_6__f")
        rows, log = self.build()
        self.assertEqual([r["name"] for r in rows], ["dafny_synthesis_task_id_5__f"])
        row = rows[0]
        self.assertEqual(row["problem"], "Write a function that returns its input.")
        self.assertEqual(row["examples"], ["dafny_synthesis_task_id_5__f(3) == 3", "dafny_synthesis_task_id_5__f(7) == 7"])
        self.assertEqual(row["source"], H.SOURCE_MBPP)
        self.assertIn("run_point", row["curation"])
        mbpp = log["sources"][H.SOURCE_MBPP]
        self.assertEqual((mbpp["tasks"], mbpp["documents"], mbpp["heads"]), (2, 2, 1))
        self.assertEqual(mbpp["refused"], ["dafny_synthesis_task_id_6__f: tests: fail"])

    def test_a_held_out_id_is_refused_by_the_gate_and_named(self):
        self.lift("dafny-synthesis_task_id_269", "F", "dafny_synthesis_task_id_269__f")
        rows, log = self.build()
        self.assertEqual(rows, [])
        self.assertEqual(log["gated"], ["dafny_synthesis_task_id_269__f"])
        self.assertEqual(len(log["held"]), 1)
        self.assertIn("269", log["held"][0])

    def test_a_registered_same_task_source_is_refused_by_the_gate(self):
        name = sorted(loop_filter.decontamination().drop_document_names)[0]
        self.lift("Clover_zzz", "Zzz", name)
        self.spec("zzz", "A docstring.")
        rows, log = self.build()
        self.assertEqual(rows, [])
        self.assertEqual(log["gated"], [name])
        self.assertEqual(len(log["decontaminated"]), 1)

    def test_a_clover_lift_takes_the_dataset_docstring_as_written(self):
        self.lift("Clover_zzz", "Zzz", "clover_zzz__zzz")
        self.spec("zzz", "Return the input\n unchanged.\n")
        rows, log = self.build()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["problem"], "Return the input unchanged.")
        self.assertEqual(rows[0]["examples"], [])
        self.assertEqual(rows[0]["source"], H.SOURCE_CLOVER)
        self.assertIn("curated by construction", rows[0]["curation"])

    def test_a_clover_lift_without_its_spec_file_is_an_error_not_a_headless_task(self):
        self.lift("Clover_zzz", "Zzz", "clover_zzz__zzz")
        self.clover.mkdir()
        with self.assertRaises(SystemExit) as caught:
            self.build()
        self.assertIn("zzz_spec.txt", str(caught.exception))

    def test_dafnybench_lifts_take_only_an_english_comment_directly_on_the_method(self):
        (self.gt / "Course_x.dfy").write_text(DFY, encoding="utf-8")
        for method in ("Bar", "Sep", "Pt", "Bare", "Doc", "Formula"):
            self.lift("Course_x", method, f"course_x__{method.lower()}")
        rows, log = self.build()
        self.assertEqual({r["name"]: r["problem"] for r in rows},
                         {"course_x__bar": "Return the value that was given, unchanged.",
                          "course_x__doc": "Returns the argument as the result of the method."})
        entry = log["sources"][H.SOURCE_DAFNYBENCH]
        self.assertEqual((entry["tasks"], entry["documents"], entry["heads"]), (6, 6, 2))
        self.assertEqual(sorted(entry["refused"]), [
            "course_x__bare: no comment",
            "course_x__formula: block above, not a description (code operator)",
            "course_x__pt: block above, not a description (non-ascii letter)",
            "course_x__sep: comment separated by a blank line",
        ])

    def test_a_dafnybench_lift_without_its_source_file_is_an_error(self):
        self.lift("Course_missing", "Bar", "course_missing__bar")
        with self.assertRaises(SystemExit) as caught:
            self.build()
        self.assertIn("Course_missing.dfy", str(caught.exception))

    def test_a_task_whose_row_is_not_clean_is_not_a_document_and_gets_no_row(self):
        self.lift("dafny-synthesis_task_id_5", "F", "dafny_synthesis_task_id_5__f")
        rows, log = self.build(table=self.table([]))
        self.assertEqual(rows, [])
        self.assertEqual(log["not_a_document"][H.SOURCE_MBPP], 1)
        self.assertEqual(log["sources"][H.SOURCE_MBPP]["documents"], 0)

    def test_an_empty_lifted_directory_is_refused(self):
        with self.assertRaises(SystemExit):
            self.build()

    def test_main_writes_the_rows_and_the_report_with_counts_per_source(self):
        self.lift("dafny-synthesis_task_id_5", "F", "dafny_synthesis_task_id_5__f")
        self.lift("Clover_zzz", "Zzz", "clover_zzz__zzz")
        self.spec("zzz", "Return the input.")
        (self.gt / "Course_x.dfy").write_text(DFY, encoding="utf-8")
        self.lift("Course_x", "Bar", "course_x__bar")
        self.lift("Course_x", "Bare", "course_x__bare")
        out, report = self.dir / "heads.jsonl", self.dir / "HEADS.md"
        said = io.StringIO()
        with mock.patch.object(H.se, "pool", lambda version: self.pool), contextlib.redirect_stdout(said):
            code = H.main(["--lifted-dir", str(self.lifted), "--table", str(self.table()), "--split", str(self.split),
                           "--clover-dir", str(self.clover), "--dafnybench", str(self.gt),
                           "--out", str(out), "--report", str(report)])
        self.assertEqual(code, 0)
        rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([r["name"] for r in rows], ["dafny_synthesis_task_id_5__f", "clover_zzz__zzz", "course_x__bar"])
        text = report.read_text(encoding="utf-8")
        self.assertIn("| mbpp-dfy | 1 | 1 | 1 | 0 |", text)
        self.assertIn("| clover | 1 | 1 | 1 | 0 |", text)
        self.assertIn("| dafnybench | 2 | 2 | 1 | 1 |", text)
        self.assertIn("course_x__bare: no comment", text)
        self.assertIn("Example: dafny_synthesis_task_id_5__f(3) == 3", text)
        self.assertIn("heads ", said.getvalue())


class CorpusHeadsTests(Fixture):
    """`loop_locallm.py corpus --lifted --heads`: the heads reach the documents
    through the same gates, and a head with no document is an error."""

    def setUp(self):
        super().setUp()
        self.committed = self.dir / "tasks"
        self.committed.mkdir()
        (self.committed / "c_one.t").write_text(TASK.format(name="c_one"), encoding="utf-8")
        self.agreement = self.dir / "AGREEMENT.md"
        cells = " | ".join([loop_locallm.CLEAN] * 7)
        self.agreement.write_text("| task | dafny | verus | spark | framac | lean | rocq | fstar |\n"
                                  "|---|---|---|---|---|---|---|---|\n"
                                  f"| c_one | {cells} |\n", encoding="utf-8")

    def heads_file(self, rows) -> Path:
        path = self.dir / "heads.jsonl"
        path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        return path

    def corpus(self, heads="", lifted=True, examples=False):
        out = self.dir / "corpus.txt"
        said = io.StringIO()
        with mock.patch.object(loop_locallm, "LIFTED_DIR", self.lifted), \
             mock.patch.object(loop_locallm, "LIFTED_TABLE", self.table()), \
             mock.patch.object(loop_locallm, "COMMITTED_DIR", self.committed), \
             mock.patch.object(loop_locallm, "AGREEMENT", self.agreement), \
             mock.patch.object(loop_locallm.se, "pool", lambda version: self.pool), \
             contextlib.redirect_stdout(said):
            code = loop_locallm.cmd_corpus(argparse.Namespace(
                pool="v5", split=self.split, base="", sft=[], lifted=lifted, out=str(out), examples=examples,
                heads=str(heads) if heads else ""))
        return code, said.getvalue(), out.read_text(encoding="utf-8") if out.exists() else ""

    def row(self, name, problem="Return the input.", examples=(), source="clover"):
        return {"name": name, "problem": problem, "examples": list(examples), "source": source, "curation": "fixture"}

    def test_a_head_prefixes_its_document_the_way_problem_head_would(self):
        self.lift("Clover_zzz", "Zzz", "clover_zzz__zzz")
        self.lift("Course_x", "Bare", "course_x__bare")
        heads = self.heads_file([self.row("clover_zzz__zzz"), self.row("c_one", "A committed task.", source="fixture")])
        code, said, text = self.corpus(heads=heads)
        self.assertEqual(code, 0, said)
        self.assertIn("Problem: Return the input.\nSignature: clover_zzz__zzz(int) -> int\nt 1\ntask clover_zzz__zzz(", text)
        self.assertIn("Problem: A committed task.\nSignature: c_one(int) -> int\nt 1\ntask c_one(", text)
        self.assertIn("\n\nt 1\ntask course_x__bare(", text)
        self.assertIn("heads: 2 document(s) prefixed", said)
        self.assertIn("clover 1, fixture 1", said)
        documents = loop_locallm.REPLY_BOUNDARY.split(text)
        self.assertEqual(len([d for d in documents if d.strip()]), 3)

    def test_example_lines_follow_the_corpus_examples_flag_like_every_other_head(self):
        self.lift("dafny-synthesis_task_id_5", "F", "dafny_synthesis_task_id_5__f")
        heads = self.heads_file([self.row("dafny_synthesis_task_id_5__f", "Return the input.",
                                          ["dafny_synthesis_task_id_5__f(3) == 3"], source="mbpp-dfy")])
        _code, _said, without = self.corpus(heads=heads)
        self.assertNotIn("Example:", without)
        _code, _said, with_examples = self.corpus(heads=heads, examples=True)
        self.assertIn("Signature: dafny_synthesis_task_id_5__f(int) -> int\nExample: dafny_synthesis_task_id_5__f(3) == 3\nt 1\n",
                      with_examples)

    def test_a_head_that_matches_no_document_is_an_error(self):
        self.lift("Clover_zzz", "Zzz", "clover_zzz__zzz")
        heads = self.heads_file([self.row("clover_zzz__zzz"), self.row("nobody")])
        with self.assertRaises(SystemExit) as caught:
            self.corpus(heads=heads)
        self.assertIn("1 head(s) in", str(caught.exception))
        self.assertIn("['nobody']", str(caught.exception))

    def test_a_head_for_a_held_out_document_is_refused_not_dropped(self):
        self.lift("dafny-synthesis_task_id_269", "F", "dafny_synthesis_task_id_269__f")
        heads = self.heads_file([self.row("dafny_synthesis_task_id_269__f", source="mbpp-dfy")])
        with self.assertRaises(SystemExit) as caught:
            self.corpus(heads=heads)
        self.assertIn("dafny_synthesis_task_id_269__f", str(caught.exception))

    def test_heads_without_lifted_documents_is_an_error(self):
        self.lift("Clover_zzz", "Zzz", "clover_zzz__zzz")
        heads = self.heads_file([self.row("clover_zzz__zzz")])
        with self.assertRaises(SystemExit) as caught:
            self.corpus(heads=heads, lifted=False)
        self.assertIn("--lifted was not given", str(caught.exception))

    def test_a_malformed_or_duplicated_head_row_is_refused_by_line(self):
        self.lift("Clover_zzz", "Zzz", "clover_zzz__zzz")
        bad = self.dir / "bad.jsonl"
        bad.write_text(json.dumps({"name": "clover_zzz__zzz", "problem": ""}) + "\n", encoding="utf-8")
        with self.assertRaises(SystemExit) as caught:
            self.corpus(heads=bad)
        self.assertIn("bad.jsonl:1", str(caught.exception))
        twice = self.heads_file([self.row("clover_zzz__zzz"), self.row("clover_zzz__zzz")])
        with self.assertRaises(SystemExit) as caught:
            self.corpus(heads=twice)
        self.assertIn("heads.jsonl:2: a second head", str(caught.exception))
        empty = self.dir / "empty.jsonl"
        empty.write_text("\n", encoding="utf-8")
        with self.assertRaises(SystemExit) as caught:
            self.corpus(heads=empty)
        self.assertIn("holds no head", str(caught.exception))

    def test_without_heads_the_builder_is_unchanged(self):
        self.lift("Clover_zzz", "Zzz", "clover_zzz__zzz")
        code, said, text = self.corpus()
        self.assertEqual(code, 0, said)
        self.assertNotIn("Problem:", text)
        self.assertNotIn("heads:", said)


if __name__ == "__main__":
    unittest.main()


class CorpusLiftedSetsTests(CorpusHeadsTests):
    """`corpus --lifted --lifted-set DIR=TABLE --heads A --heads B` (2026-09-26): a
    second lift joins the corpus through its own table and the same gates, and each
    lift brings its own heads file."""

    def second_set(self, names):
        """A second lifted directory and its table, as t/lift_corpora.py and the
        queue's grading step leave them."""
        directory = self.dir / "lifted-2"
        directory.mkdir(exist_ok=True)
        for name in names:
            task = surface.parse(TASK.format(name=name))
            (directory / f"{name}.json").write_text(json.dumps(task), encoding="utf-8")
        cells = " | ".join([loop_locallm.CLEAN] * 7)
        table = self.dir / "COVERAGE-2.md"
        table.write_text("| task | dafny | verus | spark | framac | lean | rocq | fstar |\n"
                         "|---|---|---|---|---|---|---|---|\n"
                         + "".join(f"| {n} | {cells} |\n" for n in names[:1]), encoding="utf-8")
        return directory, table

    def corpus_sets(self, sets, heads=()):
        out = self.dir / "corpus.txt"
        said = io.StringIO()
        with mock.patch.object(loop_locallm, "LIFTED_DIR", self.lifted), \
             mock.patch.object(loop_locallm, "LIFTED_TABLE", self.table()), \
             mock.patch.object(loop_locallm, "COMMITTED_DIR", self.committed), \
             mock.patch.object(loop_locallm, "AGREEMENT", self.agreement), \
             mock.patch.object(loop_locallm.se, "pool", lambda version: self.pool), \
             contextlib.redirect_stdout(said):
            code = loop_locallm.cmd_corpus(argparse.Namespace(
                pool="v5", split=self.split, base="", sft=[], lifted=True, out=str(out), examples=False,
                heads=[str(h) for h in heads], lifted_set=list(sets)))
        return code, said.getvalue(), out.read_text(encoding="utf-8") if out.exists() else ""

    def test_a_second_set_adds_its_clean_rows_only(self):
        self.lift("Clover_zzz", "Zzz", "clover_zzz__zzz")
        directory, table = self.second_set(["vericoding_one__f", "vericoding_two__g"])
        code, said, text = self.corpus_sets([f"{directory}={table}"])
        self.assertEqual(code, 0, said)
        self.assertIn("task clover_zzz__zzz(", text)
        self.assertIn("task vericoding_one__f(", text)          # clean in its own table
        self.assertNotIn("task vericoding_two__g(", text)       # not in its table: not clean
        self.assertIn("lifted, per set: 1 from lifted (COVERAGE.md), 1 from lifted-2 (COVERAGE-2.md)", said)

    def test_each_lift_brings_its_own_heads_file(self):
        self.lift("Clover_zzz", "Zzz", "clover_zzz__zzz")
        directory, table = self.second_set(["vericoding_one__f"])
        first = self.dir / "heads-1.jsonl"
        first.write_text(json.dumps(self.row("clover_zzz__zzz")) + "\n", encoding="utf-8")
        second = self.dir / "heads-2.jsonl"
        second.write_text(json.dumps(self.row("vericoding_one__f", "Return the input, verbatim.",
                                              source="vericoding/apps")) + "\n", encoding="utf-8")
        code, said, text = self.corpus_sets([f"{directory}={table}"], heads=[first, second])
        self.assertEqual(code, 0, said)
        self.assertIn("Problem: Return the input.\nSignature: clover_zzz__zzz(int) -> int\n", text)
        self.assertIn("Problem: Return the input, verbatim.\nSignature: vericoding_one__f(int) -> int\n", text)
        self.assertIn("heads: 2 document(s) prefixed from", said)

    def test_a_name_headed_in_two_files_is_refused(self):
        self.lift("Clover_zzz", "Zzz", "clover_zzz__zzz")
        first = self.dir / "heads-1.jsonl"
        first.write_text(json.dumps(self.row("clover_zzz__zzz")) + "\n", encoding="utf-8")
        second = self.dir / "heads-2.jsonl"
        second.write_text(json.dumps(self.row("clover_zzz__zzz", "Another statement.")) + "\n", encoding="utf-8")
        with self.assertRaises(SystemExit) as caught:
            self.corpus_sets([], heads=[first, second])
        self.assertIn("already gave", str(caught.exception))

    def test_a_bad_set_is_refused_by_name(self):
        self.lift("Clover_zzz", "Zzz", "clover_zzz__zzz")
        directory, table = self.second_set(["vericoding_one__f"])
        for spec, phrase in ((str(directory), "expected DIR=TABLE"),
                             (f"{self.dir / 'absent'}={table}", "no directory"),
                             (f"{directory}={self.dir / 'absent.md'}", "no table")):
            with self.subTest(spec=spec):
                with self.assertRaises(SystemExit) as caught:
                    self.corpus_sets([spec])
                self.assertIn(phrase, str(caught.exception))

    def test_the_command_line_repeats_both_options(self):
        a = loop_locallm.build_parser().parse_args(
            ["corpus", "--split", "s.json", "--lifted", "--lifted-set", "a=b", "--lifted-set", "c=d",
             "--heads", "h1.jsonl", "--heads", "h2.jsonl"])
        self.assertEqual(a.lifted_set, ["a=b", "c=d"])
        self.assertEqual(a.heads, ["h1.jsonl", "h2.jsonl"])
