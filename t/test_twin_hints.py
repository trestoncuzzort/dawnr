"""t/test_twin_hints.py -- the hint-stripping twin generator, without a kernel.

Every test here runs on the desktop: parse, strip, print, well-formedness,
the three gates, the layout, and the classification of a run_par table that
is written by hand. The kernel side is measured on the lab and reported in
t/TWIN-HINTS-2026-09-25.md, never asserted here.
"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import check_wf
import loop_filter
import surface
import twin_hints as th

HERE = Path(__file__).resolve().parent
TASKS = HERE / "tasks"
SEVEN = ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"]


def load(name: str) -> dict:
    return surface.parse((TASKS / f"{name}.t").read_text(encoding="utf-8"))


def source(name: str, text: str | None = None, problem=None, written_by="test") -> th.Source:
    task = load(name) if text is None else surface.parse(text)
    return th.Source(name=task["name"], problem=problem, written_by=written_by,
                     text=surface.print_task(task).strip(), verified_by=list(SEVEN))


def table_text(rows, cols=SEVEN) -> str:
    lines = ["# t cross-kernel agreement, 2026-09-25 00:00Z", "",
             "| task | " + " | ".join(cols) + " |", "|" + "---|" * (len(cols) + 1)]
    for name, cells in rows.items():
        lines.append("| " + name + " | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


class HintCensus(unittest.TestCase):
    def test_contains_has_two_invariants_and_its_loop_decreases_is_not_strippable(self):
        hints, unstrippable = th.hints(load("contains"))
        self.assertEqual([h["kind"] for h in hints], ["invariant", "invariant"])
        self.assertEqual([h["index"] for h in hints], [0, 1])
        self.assertEqual(hints[0]["text"], "r == (exists j in [0, i) . j < len(s) and s[j] == x)")
        self.assertEqual(unstrippable, {"loop-decreases": 1, "task-decreases": 0,
                                        "spec-fun-decreases": 0, "assert": 0})

    def test_factorial_task_decreases_and_spec_fun_decreases_are_not_strippable(self):
        hints, unstrippable = th.hints(load("factorial"))
        self.assertEqual([(h["kind"], h["text"]) for h in hints], [("requires", "n >= 0")])
        self.assertEqual(unstrippable["task-decreases"], 1)
        self.assertEqual(unstrippable["spec-fun-decreases"], 1)
        # And the reason: check_wf refuses the decreases-less variant (gate 3), so
        # stripping it would teach well-formedness, not proof.
        task = load("factorial")
        del task["decreases"]
        self.assertTrue(any("self-recursive body without a task decreases" in e
                            for e in check_wf.check_wf(task)))

    def test_loops_are_numbered_in_pre_order_across_branches(self):
        hints, unstrippable = th.hints(load("has_duplicate"))
        self.assertEqual(unstrippable["loop-decreases"], 2)
        self.assertEqual(sorted({h["loop"] for h in hints}), [0, 1])
        self.assertEqual(len(hints), 7)


class Strip(unittest.TestCase):
    def test_every_twin_removes_exactly_one_line_and_keeps_the_body(self):
        seen = 0
        for path in sorted(TASKS.glob("*.t")):
            task = surface.parse(path.read_text(encoding="utf-8"))
            program = surface.print_task(task).strip().splitlines()
            for tw in th.twins_of(task):
                seen += 1
                twin = tw["twin_text"].splitlines()
                self.assertEqual(len(program) - len(twin), 1, (path.name, tw["operator"]))
                missing = [l for l in program if l not in twin]
                self.assertEqual(len(missing), 1, (path.name, tw["operator"]))
                self.assertIn(tw["hint"]["text"], missing[0])
                self.assertEqual(th.executable_body(tw["twin"]["body"]), th.executable_body(task["body"]))
                self.assertEqual(tw["twin"]["ensures"], task["ensures"])
                if tw["hint"]["kind"] == "invariant":
                    self.assertNotEqual(tw["twin"]["body"], task["body"])   # the invariant is gone
                else:
                    self.assertEqual(tw["twin"]["body"], task["body"])
        self.assertGreater(seen, 40)

    def test_twins_round_trip_and_are_well_formed(self):
        for name in ("contains", "sum_upto", "has_duplicate", "min_max"):
            task = load(name)
            for tw in th.twins_of(task):
                self.assertEqual(surface.parse(tw["twin_text"] + "\n"), tw["twin"])
                self.assertEqual(check_wf.check_wf(tw["twin"]), [], (name, tw["operator"]))

    def test_operator_names_count_within_their_kind(self):
        ops = [tw["operator"] for tw in th.twins_of(load("sum_upto"))]
        self.assertEqual(ops, ["drop-requires", "drop-invariant", "drop-invariant#1"])

    def test_a_duplicated_clause_strips_one_copy_at_a_time(self):
        # A lifted DafnyBench task states one requires twice; the first emit
        # refused it because a set difference of the lines saw nothing removed.
        text = ("t 1\ntask twice(n: int) returns (r: int)\n  requires n >= 0\n  requires n >= 0\n"
                "  ensures r == n\n{\n  r := n;\n}\n")
        tws = th.twins_of(surface.parse(text))
        self.assertEqual([tw["operator"] for tw in tws], ["drop-requires", "drop-requires#1"])
        self.assertEqual(tws[0]["twin_text"], tws[1]["twin_text"])
        self.assertEqual(tws[0]["twin_text"].count("requires n >= 0"), 1)
        # At emit, the two hints are one twin: one file, and the fold is counted.
        with tempfile.TemporaryDirectory() as d:
            tasks = Path(d) / "tasks"
            tasks.mkdir()
            (tasks / "twice.t").write_text(text, encoding="utf-8")
            table = Path(d) / "table.md"
            table.write_text(table_text({"twice": ["verified / refuted"] * 7}), encoding="utf-8")
            split = Path(d) / "split.json"
            split.write_text(json.dumps({"eval_ids": []}), encoding="utf-8")
            report = th.emit(None, tasks, table, "t", split, Path(d) / "no-dev.json", Path(d) / "out")
            self.assertEqual((report["twins"], report["duplicates"], report["on_disk"]), (1, 1, 1))

    def test_a_task_with_no_hint_yields_no_twin(self):
        self.assertEqual(th.twins_of(load("abs")), [])

    def test_a_hint_that_is_not_there_is_refused_by_name(self):
        task = load("sum_upto")
        with self.assertRaises(th.TwinRefused):
            th.strip_hint(task, {"kind": "invariant", "loop": 7, "index": 0, "text": "x"})
        with self.assertRaises(th.TwinRefused):
            th.strip_hint(task, {"kind": "requires", "index": 3, "text": "x"})


class WitnessSentence(unittest.TestCase):
    def test_the_three_shapes_read_and_nothing_reads_for_none(self):
        self.assertEqual(th.real_witness_sentence(None), "")
        value = {"_ens": True, "_kind": "value", "_real": 0, "_twin": 0, "num": -2}
        self.assertEqual(th.real_witness_sentence(value),
                         "at num=-2, an input the stripped requires excluded, the program answers 0 "
                         "and `ensures` is false")
        undef = {"_kind": "undefined", "_real": "no value", "_twin": "div by zero", "_ens": True, "y": 0}
        self.assertIn("the body is undefined (div by zero)", th.real_witness_sentence(undef))
        measure = {"_kind": "measure", "_site": 0, "_caller_measure": 3, "_callee_measure": 3, "n": 3}
        self.assertIn("does not decrease (3 to 3)", th.real_witness_sentence(measure))


class Rename(unittest.TestCase):
    def test_renaming_a_recursive_task_renames_its_self_call(self):
        task = th.rename_task(load("factorial"), "factorial__h0")
        self.assertEqual(task["name"], "factorial__h0")
        self.assertEqual(check_wf.check_wf(task), [])
        self.assertIn("factorial__h0(n - 1)", surface.print_task(task))
        self.assertIn("fact(n)", surface.print_task(task))   # the spec fun keeps its name

    def test_grading_name_keeps_the_problem_id(self):
        name = th.grading_name("mbpp_10__small_nnum", "1ebef08bec149da7")
        self.assertEqual(loop_filter.problem_id(name), 10)
        self.assertEqual(loop_filter.problem_id(th.grading_name("apps_124__search", "ab")), 200124)


class Gate(unittest.TestCase):
    def setUp(self):
        self.policy = loop_filter.decontamination()

    def test_held_out_id_is_refused_under_an_alias(self):
        text = ("t 1\ntask mbpp_5__f(a: int) returns (r: int)\n  requires a >= 0\n"
                "  ensures r == a\n{\n  r := a;\n}\n")
        src = source("x", text, problem=5, written_by="t")
        refusal = th.gate(src, {5}, self.policy)
        self.assertIsNotNone(refusal)
        self.assertIn("mbpp_5", refusal)
        self.assertIsNone(th.gate(src, {6}, self.policy))

    def test_task_id_field_is_checked_even_when_the_name_is_plain(self):
        text = ("t 1\ntask plain(a: int) returns (r: int)\n  requires a >= 0\n"
                "  ensures r == a\n{\n  r := a;\n}\n")
        src = source("plain", text, problem=42, written_by="t")
        self.assertIsNotNone(th.gate(src, {42}, self.policy))

    def test_decontaminated_document_is_refused(self):
        self.assertIn("contains", self.policy.drop_document_names)
        refusal = th.gate(source("contains"), set(), self.policy)
        self.assertIsNotNone(refusal)
        self.assertIn("contains", refusal)

    def test_clean_committed_task_is_admitted(self):
        self.assertIsNone(th.gate(source("all_nonneg"), set(), self.policy))

    def test_held_out_ids_come_from_the_split_and_the_dev_file(self):
        with tempfile.TemporaryDirectory() as d:
            split = Path(d) / "split.json"
            split.write_text(json.dumps({"eval_ids": [1, 2], "train_ids": [3]}), encoding="utf-8")
            dev = Path(d) / "dev.json"
            dev.write_text(json.dumps({"dev_ids": [3], "inputs": {
                "split_sha256": hashlib.sha256(split.read_bytes()).hexdigest()}}), encoding="utf-8")
            self.assertEqual(th.held_out_ids(split, dev), {1, 2, 3})
            other = Path(d) / "other.json"
            other.write_text(json.dumps({"eval_ids": [9]}), encoding="utf-8")
            self.assertEqual(th.held_out_ids(other, dev), {9})   # dev ids belong to one split
            with self.assertRaises(SystemExit):
                th.held_out_ids(Path(d) / "missing.json", dev)


class TableReading(unittest.TestCase):
    def test_real_side_is_read_per_kernel(self):
        text = table_text({"a": ["verified / refuted"] * 6 + ["unproved / unproved (FLAKED)"]})
        rows = th.read_table(text)
        self.assertEqual(rows["a"]["dafny"], ("verified", False))
        self.assertEqual(rows["a"]["fstar"], ("unproved", True))

    def test_a_table_without_all_seven_columns_is_refused(self):
        with self.assertRaises(th.TwinRefused):
            th.read_table(table_text({"a": ["verified / refuted"] * 6}, cols=SEVEN[:6]))

    def test_all_seven_verified_programs_are_the_only_admitted_ones(self):
        text = table_text({"a": ["verified / refuted"] * 7,
                           "b": ["verified / refuted"] * 6 + ["timeout / refuted"],
                           "c": ["verified / decorative"] * 7,
                           "d": ["verified / refuted"] * 6 + ["verified / refuted (FLAKED)"]})
        self.assertEqual(th.verified_rows(th.read_table(text)), {"a", "c"})


class Classify(unittest.TestCase):
    def test_classes(self):
        v = {k: ("verified", False) for k in SEVEN}
        self.assertEqual(th.classify(v)["class"], "redundant")
        u = dict(v, lean=("unproved", False))
        c = th.classify(u)
        self.assertEqual(c["class"], "proof-breaking")
        self.assertEqual(c["breaks_in"], ["lean"])
        r = dict(u, dafny=("refuted", False))
        self.assertEqual(th.classify(r)["class"], "behavioural")
        self.assertEqual(th.classify(r)["twin_refuted_by"], ["dafny"])
        t = dict(v, rocq=("timeout", False))
        self.assertEqual(th.classify(t)["class"], "undecided")
        f = dict(v, spark=("verified", True))
        self.assertEqual(th.classify(f)["class"], "undecided")   # a flaked cell is not a verdict
        m = dict(v, framac=("malformed", False))
        self.assertEqual(th.classify(m)["class"], "undecided")
        self.assertIn("framac", th.classify(m)["unknown_in"])


class Emit(unittest.TestCase):
    def emit(self, d, **kw):
        split = Path(d) / "split.json"
        split.write_text(json.dumps({"eval_ids": [], "train_ids": []}), encoding="utf-8")
        args = dict(twins_dir=None, tasks_dir=TASKS, table=HERE / "AGREEMENT.md",
                    written_by="committed", split=split, dev_ids=Path(d) / "no-dev.json",
                    out=Path(d) / "out", max_programs=None, max_cells=None, skip_refused=True)
        args.update(kw)
        return th.emit(**args)

    def test_layout_matches_t_twins_and_the_grading_copies_are_distinct(self):
        with tempfile.TemporaryDirectory() as d:
            report = self.emit(d)
            out = Path(d) / "out"
            index = (out / "INDEX.tsv").read_text(encoding="utf-8").splitlines()
            self.assertTrue(index[0].startswith("task\tproblem\toperator\twritten by\tfile"))
            self.assertEqual(index[0].split("\t")[5:], ["hint", "class"])
            self.assertEqual(len(index) - 1, report["twins"])
            pairs = sorted((out / "pairs").glob("*.json"))
            self.assertEqual(len(pairs), report["twins"])
            one = json.loads(pairs[0].read_text(encoding="utf-8"))
            for key in ("id", "task", "problem", "operator", "written_by", "program", "twin",
                        "hint", "verified_by", "twin_refuted_by", "class", "witness", "witness_reads"):
                self.assertIn(key, one)
            self.assertEqual(one["class"], "ungraded")
            self.assertEqual(one["verified_by"], sorted(SEVEN))
            self.assertTrue((out / "README.md").exists())
            # The refusals are on record, by name, not dropped quietly.
            refused = (out / "REFUSED.tsv").read_text(encoding="utf-8").splitlines()
            self.assertIn("contains", "\n".join(refused))
            self.assertEqual(len(refused) - 1, report["refused"])
            # Grading copies: one .t per twin, distinct names, the problem id preserved.
            grade = sorted((out / "grade" / "tasks").glob("*.t"))
            self.assertEqual(len(grade), report["twins"])
            names = [surface.parse(p.read_text(encoding="utf-8"))["name"] for p in grade]
            self.assertEqual(len(set(names)), len(names))
            self.assertEqual([p.stem for p in grade], names)
            manifest = (out / "grade" / "MANIFEST.tsv").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(manifest) - 1, report["twins"])
            # A program with a `timeout` column is not verified in all seven, so it is not a source.
            self.assertNotIn("min_max", {l.split("\t")[0] for l in index[1:]})

    def test_refusal_is_loud_without_skip_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                self.emit(d, skip_refused=False)

    def test_sample_respects_both_budgets_and_covers_both_hint_kinds(self):
        with tempfile.TemporaryDirectory() as d:
            report = self.emit(d, max_programs=4, max_cells=42)
            self.assertLessEqual(report["programs"], 4)
            self.assertLessEqual(report["twins"] * 7, 42)
            index = (Path(d) / "out" / "INDEX.tsv").read_text(encoding="utf-8").splitlines()[1:]
            kinds = {l.split("\t")[2].split("#")[0] for l in index}
            self.assertEqual(kinds, {"drop-invariant", "drop-requires"})

    def test_emit_is_deterministic_and_rerunnable(self):
        with tempfile.TemporaryDirectory() as d:
            self.emit(d, max_programs=3, max_cells=200)
            first = (Path(d) / "out" / "INDEX.tsv").read_bytes()
            self.emit(d, max_programs=3, max_cells=200)
            self.assertEqual(first, (Path(d) / "out" / "INDEX.tsv").read_bytes())

    def test_classify_updates_pairs_index_and_readme(self):
        with tempfile.TemporaryDirectory() as d:
            self.emit(d, max_programs=2, max_cells=200)
            out = Path(d) / "out"
            manifest = [l.split("\t") for l in
                        (out / "grade" / "MANIFEST.tsv").read_text(encoding="utf-8").splitlines()[1:]]
            rows = {}
            for i, (row, _file) in enumerate(manifest):
                cells = ["verified / refuted"] * 7
                if i == 0:
                    cells[4] = "unproved / unproved"
                rows[row] = cells
            table = out / "table.md"
            table.write_text(table_text(rows), encoding="utf-8")
            counts = th.classify_dir(out, table)
            self.assertEqual(counts["proof-breaking"], 1)
            self.assertEqual(counts["redundant"], len(manifest) - 1)
            index = (out / "INDEX.tsv").read_text(encoding="utf-8").splitlines()[1:]
            self.assertEqual({l.split("\t")[6] for l in index}, {"proof-breaking", "redundant"})
            first = json.loads((out / manifest[0][1]).read_text(encoding="utf-8"))
            self.assertEqual(first["class"], "proof-breaking")
            self.assertEqual(first["breaks_in"], ["lean"])
            self.assertEqual(first["twin_outcomes"]["lean"], "unproved")
            readme = (out / "README.md").read_text(encoding="utf-8")
            self.assertIn("proof-breaking", readme)
            # A table naming a row the manifest does not know is refused.
            rows["nobody__hdeadbeef"] = ["verified / refuted"] * 7
            table.write_text(table_text(rows), encoding="utf-8")
            with self.assertRaises(th.TwinRefused):
                th.classify_dir(out, table)
            # A table missing a manifest row leaves that twin ungraded, and says so.
            del rows["nobody__hdeadbeef"]
            del rows[manifest[0][0]]
            table.write_text(table_text(rows), encoding="utf-8")
            counts = th.classify_dir(out, table)
            self.assertEqual(counts["ungraded"], 1)


if __name__ == "__main__":
    unittest.main()
