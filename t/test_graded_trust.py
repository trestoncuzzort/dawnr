"""Graded-trust admission (AMBITION.md "t grows as dawnr does"): a lifted or
committed row that reads clean in six of the seven kernels can enter the
corpus with its gap recorded, not only a row clean in all seven. `--min-kernels`
(default 7, so a build that never asks for it is byte-for-byte the old
all-or-nothing gate) lowers the bar; a cell that actively contradicts the
program -- a real refutation, or a decorative twin the kernel could not tell
from the real thing -- excludes its row at any bar, because that is not a
kernel withholding evidence, it is a kernel standing against the program.

Style follows t/test_corpus_split.py (the split boundary is absolute) and
t/test_heads_from_sources.py's CorpusHeadsTests (a lifted directory, a
coverage table, cmd_corpus driven through argparse.Namespace and mock.patch).
"""
import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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
KERNELS = ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"]
CLEAN = loop_locallm.CLEAN                          # "verified / refuted"
TIMEOUT_CELL = "timeout / timeout"
DECORATIVE_CELL = "verified / decorative"
UNSOUND_CELL = "verified / unsound"
REFUTED_CELL = "refuted / refuted"
ABSTAIN_CELL = "abstain / abstain"
UNPROVED_CELL = "unproved / refuted"
MALFORMED_CELL = "malformed / malformed"


def make_table(path: Path, rows: dict[str, list[str]]) -> Path:
    """A `| task | dafny | ... | fstar |` table with each row's own seven
    cells, exactly the shape t/run_par.py writes (t/test_heads_from_sources.py
    Fixture.table, generalised to a per-row, per-column cell instead of
    seven CLEANs for every row)."""
    lines = ["| task | " + " | ".join(KERNELS) + " |", "|" + "---|" * 8]
    for name, cells in rows.items():
        assert len(cells) == 7, (name, cells)
        lines.append("| " + name + " | " + " | ".join(cells) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def row_of(clean=7, gap_kernel=None, gap_cell=TIMEOUT_CELL) -> list[str]:
    """Seven cells, `clean` of them CLEAN; if fewer than seven, the rest are
    `gap_cell` (default a timeout), all in `gap_kernel`'s column when given,
    otherwise spread from the end so the table stays readable."""
    cells = [CLEAN] * 7
    n_gap = 7 - clean
    idx = [KERNELS.index(gap_kernel)] if gap_kernel else list(range(7 - n_gap, 7))
    for i in idx[:n_gap] if gap_kernel is None else idx * n_gap:
        cells[i] = gap_cell
    return cells


class ContradictsProgramTests(unittest.TestCase):
    """The exact veto rule: a real refutation or a decorative twin excludes a
    row at every --min-kernels; every other non-clean cell only lowers the
    clean-kernel count."""

    def test_a_clean_cell_does_not_contradict(self):
        self.assertFalse(loop_locallm.contradicts_program(CLEAN))

    def test_withheld_evidence_does_not_contradict(self):
        for cell in (TIMEOUT_CELL, ABSTAIN_CELL, UNPROVED_CELL, MALFORMED_CELL,
                     "no-twin / no-twin", "lower-error / lower-error",
                     "verified / timeout", "verified / unproved", "verified / malformed",
                     "vacuous / refuted"):
            self.assertFalse(loop_locallm.contradicts_program(cell), cell)

    def test_a_decorative_twin_contradicts(self):
        self.assertTrue(loop_locallm.contradicts_program(DECORATIVE_CELL))
        self.assertTrue(loop_locallm.contradicts_program(UNSOUND_CELL))

    def test_a_real_refutation_contradicts(self):
        self.assertTrue(loop_locallm.contradicts_program(REFUTED_CELL))
        self.assertTrue(loop_locallm.contradicts_program("refuted / verified"))

    def test_a_flaked_clean_cell_is_not_clean_but_does_not_contradict(self):
        flaked = CLEAN + " (FLAKED)"
        self.assertNotEqual(flaked, CLEAN)
        self.assertFalse(loop_locallm.contradicts_program(flaked))

    def test_a_flaked_decorative_cell_still_contradicts(self):
        self.assertTrue(loop_locallm.contradicts_program(DECORATIVE_CELL + " (FLAKED)"))


class GradedRowsTests(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.dir = Path(d.name)

    def test_a_seven_clean_row_is_admitted_at_the_default(self):
        table = make_table(self.dir / "t.md", {"seven": row_of(7)})
        graded = loop_locallm.graded_rows(table)
        self.assertTrue(graded["seven"].admitted)
        self.assertEqual(graded["seven"].clean, 7)
        self.assertEqual(graded["seven"].gaps, {})
        self.assertEqual(loop_locallm.clean_rows(table), {"seven"})

    def test_a_six_clean_row_needs_min_kernels_six(self):
        table = make_table(self.dir / "t.md", {"six": row_of(6, gap_kernel="framac")})
        graded7 = loop_locallm.graded_rows(table, 7)
        self.assertFalse(graded7["six"].admitted)
        self.assertEqual(graded7["six"].clean, 6)
        self.assertEqual(graded7["six"].gaps, {"framac": TIMEOUT_CELL})
        graded6 = loop_locallm.graded_rows(table, 6)
        self.assertTrue(graded6["six"].admitted)
        self.assertEqual(loop_locallm.clean_rows(table, min_kernels=6), {"six"})
        self.assertEqual(loop_locallm.clean_rows(table, min_kernels=7), set())

    def test_a_decorative_twin_is_never_admitted(self):
        table = make_table(self.dir / "t.md", {"veto": row_of(6, gap_kernel="verus", gap_cell=DECORATIVE_CELL)})
        for n in (7, 6, 1):
            graded = loop_locallm.graded_rows(table, n)
            self.assertFalse(graded["veto"].admitted, n)
        self.assertEqual(graded["veto"].clean, 6)
        self.assertEqual(graded["veto"].gaps, {"verus": DECORATIVE_CELL})

    def test_a_refuted_real_program_is_never_admitted(self):
        table = make_table(self.dir / "t.md", {"veto": row_of(6, gap_kernel="rocq", gap_cell=REFUTED_CELL)})
        for n in (7, 6, 1):
            self.assertFalse(loop_locallm.graded_rows(table, n)["veto"].admitted, n)

    def test_table_kernels_reads_the_header_in_order(self):
        table = make_table(self.dir / "t.md", {"x": row_of(7)})
        self.assertEqual(loop_locallm.table_kernels(table), KERNELS)


class TempDirTestCase(unittest.TestCase):
    def tempdir(self) -> Path:
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        return Path(d.name)


class CorpusGradedTrustTests(TempDirTestCase):
    """`loop_locallm.py corpus --lifted --min-kernels N`: the sidecar, the
    printed counts, and the gates still applied to an admitted 6-clean row."""

    def setUp(self):
        self.lifted = self.tempdir()
        self.committed = self.tempdir()
        self.split = self.tempdir() / "split.json"
        self.split.write_text(json.dumps({"eval_ids": [269]}), encoding="utf-8")

    def lift(self, name: str) -> None:
        task = surface.parse(TASK.format(name=name))
        (self.lifted / f"{name}.json").write_text(json.dumps(task), encoding="utf-8")

    def build(self, rows: dict[str, list[str]], min_kernels=7, split=None):
        table = make_table(self.tempdir() / "COVERAGE.md", rows)
        agreement = make_table(self.tempdir() / "AGREEMENT.md", {})
        out = self.tempdir() / "corpus.txt"
        said = io.StringIO()
        with mock.patch.object(loop_locallm, "LIFTED_DIR", self.lifted), \
             mock.patch.object(loop_locallm, "LIFTED_TABLE", table), \
             mock.patch.object(loop_locallm, "COMMITTED_DIR", self.committed), \
             mock.patch.object(loop_locallm, "AGREEMENT", agreement), \
             contextlib.redirect_stdout(said):
            code = loop_locallm.cmd_corpus(argparse.Namespace(
                pool="v5", split=split or self.split, base="", sft=[], lifted=True, out=str(out),
                examples=False, heads=[], lifted_set=[], min_kernels=min_kernels))
        return code, said.getvalue(), out

    def trust_lines(self, out: Path) -> list[dict]:
        path = out.with_name(out.name + ".trust.jsonl")
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def test_a_six_clean_row_is_absent_by_default_and_present_at_min_kernels_six(self):
        self.lift("seven")
        self.lift("six_gap")
        rows = {"seven": row_of(7), "six_gap": row_of(6, gap_kernel="framac")}
        code, said, out = self.build(rows, min_kernels=7)
        self.assertEqual(code, 0, said)
        text = out.read_text(encoding="utf-8")
        self.assertIn("task seven(", text)
        self.assertNotIn("task six_gap(", text)
        self.assertIn("1 lifted", said)

        code, said, out = self.build(rows, min_kernels=6)
        self.assertEqual(code, 0, said)
        text = out.read_text(encoding="utf-8")
        self.assertIn("task seven(", text)
        self.assertIn("task six_gap(", text)
        self.assertIn("2 lifted", said)

    def test_a_decorative_twin_stays_out_even_at_min_kernels_one(self):
        self.lift("seven")
        self.lift("veto")
        rows = {"seven": row_of(7), "veto": row_of(6, gap_kernel="verus", gap_cell=DECORATIVE_CELL)}
        code, said, out = self.build(rows, min_kernels=1)
        self.assertEqual(code, 0, said)
        text = out.read_text(encoding="utf-8")
        self.assertIn("task seven(", text)
        self.assertNotIn("task veto(", text)
        self.assertIn("1 lifted", said)

    def test_the_sidecar_names_every_admitted_document_and_its_gap(self):
        self.lift("seven")
        self.lift("six_gap")
        rows = {"seven": row_of(7), "six_gap": row_of(6, gap_kernel="framac")}
        code, said, out = self.build(rows, min_kernels=6)
        self.assertEqual(code, 0, said)
        by_name = {r["document"]: r for r in self.trust_lines(out)}
        self.assertEqual(set(by_name), {"seven", "six_gap"})
        self.assertEqual(by_name["seven"], {"document": "seven", "clean_kernels": 7, "missing": {}})
        self.assertEqual(by_name["six_gap"],
                         {"document": "six_gap", "clean_kernels": 6, "missing": {"framac": TIMEOUT_CELL}})
        self.assertIn("2 document(s) recorded, 1 admitted with a gap", said)

    def test_no_sidecar_text_reaches_the_training_document_itself(self):
        self.lift("six_gap")
        rows = {"six_gap": row_of(6, gap_kernel="framac")}
        code, said, out = self.build(rows, min_kernels=6)
        self.assertEqual(code, 0, said)
        text = out.read_text(encoding="utf-8")
        self.assertNotIn("framac", text)
        self.assertNotIn("clean_kernels", text)
        self.assertNotIn("timeout", text)

    def test_a_seven_clean_only_build_still_records_trust_with_no_gap(self):
        # "every admitted document carries its trust" -- even one clean in all
        # seven gets a record, just with an empty `missing`, so a reader of the
        # sidecar never has to ask elsewhere whether a document was checked.
        self.lift("seven")
        rows = {"seven": row_of(7)}
        code, said, out = self.build(rows, min_kernels=7)
        self.assertEqual(code, 0, said)
        self.assertEqual(self.trust_lines(out), [{"document": "seven", "clean_kernels": 7, "missing": {}}])
        self.assertIn("1 document(s) recorded, 0 admitted with a gap", said)

    def test_no_lifted_documents_at_all_writes_no_sidecar(self):
        out = self.tempdir() / "corpus.txt"
        table = make_table(self.tempdir() / "COVERAGE.md", {})
        agreement = make_table(self.tempdir() / "AGREEMENT.md", {})
        with mock.patch.object(loop_locallm, "LIFTED_DIR", self.lifted), \
             mock.patch.object(loop_locallm, "LIFTED_TABLE", table), \
             mock.patch.object(loop_locallm, "COMMITTED_DIR", self.committed), \
             mock.patch.object(loop_locallm, "AGREEMENT", agreement), \
             self.assertRaises(SystemExit):
            # an empty --lifted directory is refused (0 lifted documents is
            # not the corpus --lifted names); the point here is only that no
            # sidecar is left behind by a build that never got to write one
            loop_locallm.cmd_corpus(argparse.Namespace(
                pool="v5", split=self.split, base="", sft=[], lifted=True, out=str(out),
                examples=False, heads=[], lifted_set=[], min_kernels=7))
        self.assertFalse(out.with_name(out.name + ".trust.jsonl").exists())

    def test_a_held_out_six_clean_row_is_still_refused(self):
        self.lift("dafny_synthesis_task_id_269__f")
        rows = {"dafny_synthesis_task_id_269__f": row_of(6, gap_kernel="framac")}
        code, said, out = self.build(rows, min_kernels=6)
        self.assertEqual(code, 0, said)
        text = out.read_text(encoding="utf-8")
        self.assertNotIn("dafny_synthesis_task_id_269__f", text)
        self.assertIn("1 document(s) excluded", said)
        self.assertEqual(self.trust_lines(out), [])

    def test_a_same_task_six_clean_row_is_still_refused(self):
        name = sorted(loop_filter.decontamination().drop_document_names)[0]
        self.lift(name)
        rows = {name: row_of(6, gap_kernel="framac")}
        code, said, out = self.build(rows, min_kernels=6)
        self.assertEqual(code, 0, said)
        text = out.read_text(encoding="utf-8")
        self.assertNotIn(f"task {name}(", text)
        self.assertIn("decontamination filter: 1 document(s) excluded", said)

    def test_a_dev_split_six_clean_row_is_still_refused(self):
        self.lift("dafny_synthesis_task_id_5__f")
        rows = {"dafny_synthesis_task_id_5__f": row_of(6, gap_kernel="framac")}
        with mock.patch.object(loop_filter, "r12_dev_ids", return_value=frozenset({5})):
            code, said, out = self.build(rows, min_kernels=6)
        self.assertEqual(code, 0, said)
        text = out.read_text(encoding="utf-8")
        self.assertNotIn("dafny_synthesis_task_id_5__f", text)
        self.assertIn("1 ids from t/r12-dev-ids.json refused", said)


if __name__ == "__main__":
    unittest.main()
