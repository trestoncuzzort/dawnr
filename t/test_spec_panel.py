#!/usr/bin/env python3
"""t/spec_panel.py: a held-out specification question is a function the rows hold nowhere else (2026-10-05).

The case it exists for is the one the audit met: `clover_abs__abs` held out by name while three other `abs`
stayed in training. Differential testing on generated inputs decides, not names (EvalPlus, arXiv:2305.01210;
arXiv:2311.04850 on why a string match does not).
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import spec_panel as sp  # noqa: E402
import surface  # noqa: E402


def fenced(program: str) -> str:
    return "```t\n" + program.strip() + "\n```"


def task(name: str, body: str, ensures: str = "true", params: str = "x: int", ret: str = "r: int") -> str:
    return f"t 0\ntask {name}({params}) returns ({ret})\n  ensures {ensures}\n{{\n{body}\n}}\n"


ABS_A = task("clover_abs__abs", "  if x < 0 {\n    r := 0 - x;\n  } else {\n    r := x;\n  }", "r >= 0")
ABS_B = task("dafny_workout_ex02__abs", "  r := x;\n  if r < 0 {\n    r := 0 - r;\n  } else {\n  }", "r >= 0")
TRIPLE = task("triple_it", "  r := 3 * x;", "r == 3 * x")
SQUARE_PLUS = task("vericoding_DA0056", "  r := x * x + 7;", "r == x * x + 7")
NEGATE = task("negate", "  r := 0 - x;", "r == 0 - x")


def given(program: str, name: str | None = None, kind: str = "spec-given") -> dict:
    parsed = surface.parse(program)
    question = surface.print_task(dict(parsed, body=[])).strip()
    return {"name": name or parsed["name"], "kind": kind,
            "prompt": [{"role": "user", "content": "Complete this t task.\n\n" + fenced(question)}],
            "chosen": fenced(program)}


def repair(wrong: str, fixed: str) -> dict:
    return {"name": None, "kind": "debug", "prompt": [{"role": "user", "content": "This fails:\n\n" + fenced(wrong)}],
            "chosen": fenced(fixed)}


class BehaviourTests(unittest.TestCase):
    def test_two_abs_under_two_names_are_the_same_function(self):
        ins = sp.inputs(surface.parse(ABS_A))
        self.assertGreaterEqual(len(ins), sp.MIN_BOTH)
        self.assertTrue(sp.same(*sp.compare(ins, surface.parse(ABS_B))))

    def test_abs_and_negate_are_not(self):
        ins = sp.inputs(surface.parse(ABS_A))
        both, agree = sp.compare(ins, surface.parse(NEGATE))
        self.assertGreaterEqual(both, sp.MIN_BOTH)
        self.assertFalse(sp.same(both, agree))

    def test_too_few_shared_inputs_decides_nothing(self):
        self.assertFalse(sp.same(sp.MIN_BOTH - 1, sp.MIN_BOTH - 1))
        self.assertTrue(sp.same(100, 91))
        self.assertFalse(sp.same(100, 90))

    def test_a_program_silent_on_an_input_is_not_compared_there(self):
        partial = task("abs_pos", "  r := x;", "r == x").replace("  ensures", "  requires x >= 0\n  ensures")
        ins = sp.inputs(surface.parse(ABS_A))
        both, agree = sp.compare(ins, surface.parse(partial))
        self.assertLess(both, len(ins))
        self.assertEqual(both, agree)


class DocumentTests(unittest.TestCase):
    def test_a_vericoding_task_is_one_document_whatever_the_spelling(self):
        self.assertEqual(sp.document_key({"name": "vericoding_DA0056"}), "v:da0056")
        self.assertEqual(sp.document_key({"name": "vericoding_da0056__squarePlus"}), "v:da0056")
        self.assertEqual(sp.document_key({"name": "clover_abs__abs"}), "n:clover_abs__abs")

    def test_a_row_with_no_name_belongs_to_the_task_it_mentions_or_to_nothing(self):
        self.assertEqual(sp.document_key(repair(SQUARE_PLUS, SQUARE_PLUS)), "v:da0056")
        self.assertEqual(sp.document_key(repair(TRIPLE, TRIPLE)), "n:")


class DrawTests(unittest.TestCase):
    def rows(self):
        # abs three times over (two documents and a pool answer), triple_it with a repair row, DA0056 alone
        return [given(ABS_A), given(ABS_B), given(TRIPLE), repair(NEGATE, TRIPLE), given(SQUARE_PLUS),
                {"name": "mbpp_1__x", "kind": None, "chosen": fenced(ABS_B.replace("dafny_workout_ex02__abs", "magnitude"))}]

    def test_a_function_the_rows_hold_elsewhere_is_not_drawn(self):
        panel, removed, report = sp.draw(self.rows(), k=2, seed="s", max_remove=2, jobs=1)
        names = {q["name"] for q in panel}
        self.assertEqual(names, {"triple_it", "vericoding_DA0056"})                  # neither abs: three rows hold it
        self.assertEqual(report["eligible"], 2)
        self.assertEqual(report["documents_with_a_specification_given_row"], 4)

    def test_every_row_holding_the_function_leaves_with_it(self):
        panel, removed, _ = sp.draw(self.rows(), k=2, seed="s", max_remove=2, jobs=1)
        # triple_it's own row and the repair whose answer is the same program; DA0056's own row
        self.assertEqual(removed, [2, 3, 4])
        self.assertEqual({q["name"]: q["rows_removed"] for q in panel}, {"triple_it": 2, "vericoding_DA0056": 1})

    def test_a_removal_set_over_the_cap_is_not_a_candidate(self):
        panel, _removed, report = sp.draw(self.rows(), k=1, seed="s", max_remove=1, jobs=1)
        self.assertEqual([q["name"] for q in panel], ["vericoding_DA0056"])
        self.assertEqual(report["eligible"], 1)

    def test_the_order_is_the_seeds_and_not_the_files(self):
        a, _, _ = sp.draw(self.rows(), k=1, seed="seed-a", max_remove=2, jobs=1)
        b, _, _ = sp.draw(list(reversed(self.rows())), k=1, seed="seed-a", max_remove=2, jobs=1)
        self.assertEqual(a[0]["name"], b[0]["name"])
        firsts = {sp.draw(self.rows(), k=1, seed=f"seed-{i}", max_remove=2, jobs=1)[0][0]["name"] for i in range(12)}
        self.assertEqual(firsts, {"triple_it", "vericoding_DA0056"})                 # both come first under some seed

    def test_only_names_restricts_the_candidates(self):
        panel, _, report = sp.draw(self.rows(), k=1, seed="s", only_names={"triple_it"}, max_remove=2, jobs=1)
        self.assertEqual([q["name"] for q in panel], ["triple_it"])
        self.assertEqual(report["documents_with_a_specification_given_row"], 1)

    def test_a_document_of_gpl_lineage_is_never_drawn(self):
        rows = [given(TRIPLE.replace("triple_it", "vericoding_dd0736__replaceChars"))]
        self.assertEqual(sp.candidates(rows), {})


class CheckTests(unittest.TestCase):
    def test_a_row_is_flagged_by_document_and_by_behaviour(self):
        panel = [dict(given(TRIPLE), document="n:triple_it", heldout=True)]
        rows = [given(ABS_A),                                                        # unrelated
                given(TRIPLE.replace("triple_it", "times_three")),                   # the same function, another name
                given(NEGATE, name="triple_it")]                                     # the document's name
        found = {(f["row"], f["why"]) for f in sp.check(rows, panel, jobs=1)}
        self.assertEqual(found, {(1, "behaviour"), (2, "document")})

    def test_the_gate_of_a_row_build(self):
        with tempfile.TemporaryDirectory() as d:
            rows, panel, kept = Path(d) / "rows.jsonl", Path(d) / "panel.jsonl", Path(d) / "kept.jsonl"
            panel.write_text(json.dumps(dict(given(TRIPLE), document="n:triple_it")) + "\n")
            rows.write_text(json.dumps(given(ABS_A)) + "\n" + json.dumps(given(TRIPLE.replace("triple_it", "x3"))) + "\n")
            self.assertEqual(sp.main(["check", "--rows", str(rows), "--panel", str(panel), "--keep", str(kept), "--jobs", "1"]), 1)
            self.assertEqual([json.loads(line)["name"] for line in kept.read_text().splitlines()], ["clover_abs__abs"])
            self.assertEqual(sp.main(["check", "--rows", str(kept), "--panel", str(panel), "--jobs", "1"]), 0)

    def test_draw_writes_a_panel_and_the_rows_that_stay(self):
        with tempfile.TemporaryDirectory() as d:
            rows, panel, kept = Path(d) / "rows.jsonl", Path(d) / "panel.jsonl", Path(d) / "kept.jsonl"
            rows.write_text("".join(json.dumps(r) + "\n" for r in DrawTests().rows()))
            self.assertEqual(sp.main(["draw", "--rows", str(rows), "--k", "2", "--seed", "s", "--max-remove", "2",
                                      "--panel", str(panel), "--keep", str(kept), "--jobs", "1"]), 0)
            self.assertEqual(len(panel.read_text().splitlines()), 2)
            self.assertEqual(len(kept.read_text().splitlines()), 3)
            # what stays holds no question of the panel
            self.assertEqual(sp.main(["check", "--rows", str(kept), "--panel", str(panel), "--jobs", "1"]), 0)
            with self.assertRaises(SystemExit):
                sp.main(["draw", "--rows", str(rows), "--k", "5", "--seed", "s", "--panel", str(panel), "--keep", str(kept), "--jobs", "1"])


if __name__ == "__main__":
    unittest.main()
