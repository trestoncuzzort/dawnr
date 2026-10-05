#!/usr/bin/env python3
"""t/heldout_audit.py: the rows are read for a held-out problem under another name (2026-10-05).

Each test is a case the audit of 2026-10-05 met: a row whose only tie to MBPP 474 is the benchmark's source-id;
a program whose `requires` excludes the one test point that would have parted it from MBPP 605; a problem that
passes its array's length and a program that does not take it; a failing program shown in a prompt. Yang et al.
(arXiv:2311.04850) is why none of them is a string match.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import heldout_audit as ha  # noqa: E402
import spec_experiment as se  # noqa: E402
import surface  # noqa: E402


def fenced(program: str) -> str:
    return "```t\n" + program.strip() + "\n```"


IS_PRIME = """
t 1
gate loops
task vericoding_dd0763__isPrime(n: int) returns (result: bool)
  requires n >= 2
  ensures result == (forall k in [2, n) . n % k != 0)
{
  result := true;
  var i: int := 2;
  while i < n
    invariant 2 <= i and i <= n
    invariant result == (forall k_v in [2, i) . n % k_v != 0)
    decreases n - i
  {
    if n % i == 0 {
      result := false;
      return result;
    } else {
    }
    i := i + 1;
  }
}
"""

CUBES = """
t 1
gate loops
task cubes(nums: seq) returns (cubed: seq)
  ensures len(cubed) == len(nums)
  ensures forall i in [0, len(nums)) . cubed[i] == nums[i] * nums[i] * nums[i]
{
  cubed := seq(len(nums), 0);
  var i_v: int := 0;
  while i_v < len(nums)
    invariant 0 <= i_v and i_v <= len(nums)
    invariant len(cubed) == len(nums)
    invariant forall j in [0, i_v) . cubed[j] == nums[j] * nums[j] * nums[j]
    decreases len(nums) - i_v
  {
    cubed := cubed[i_v := nums[i_v] * nums[i_v] * nums[i_v]];
    i_v := i_v + 1;
  }
}
"""

ANY_EVEN = """
t 1
task any_even(a: seq) returns (r: bool)
  ensures r == (exists i in [0, len(a)) . a[i] % 2 == 0)
{
  r := exists i in [0, len(a)) . a[i] % 2 == 0;
}
"""

DOUBLE = """
t 0
task double_it(n: int) returns (r: int)
  ensures r == 2 * n
{
  r := 2 * n;
}
"""


def point(args, expected, fn="f"):
    return {"ok": True, "fn": fn, "args": args, "expected": expected}


class LineageTests(unittest.TestCase):
    def setUp(self):
        self.table = ha.lineage()

    def test_a_vericoding_name_is_read_through_the_benchmarks_own_source_id(self):
        row = {"name": "vericoding_dd0736__replaceChars", "kind": "spec-given", "chosen": "..."}
        self.assertEqual(set(ha.named_mbpp(row, self.table)), {474})
        self.assertIn("dafny-synthesis_task_id_474", ha.named_mbpp(row, self.table)[474])

    def test_the_verus_bench_translation_names_the_same_problem(self):
        # Verus-Bench's MBPP set is "Translated from MBPP-DFY-153" (its README); vericoding carries it as DJ
        self.assertEqual(set(ha.named_mbpp({"name": "vericoding_DJ0129"}, self.table)), {804})
        self.assertEqual(set(ha.named_mbpp({"name": "vericoding_dj0091__cubeElement"}, self.table)), {447})

    def test_the_name_is_found_anywhere_in_the_row(self):
        row = {"name": None, "kind": "memory",
               "prompt": [{"role": "user", "content": "recall task vericoding_dd0735__containsConsecutiveNumbers"}]}
        self.assertEqual(set(ha.named_mbpp(row, self.table)), {472})

    def test_a_direct_mbpp_dfy_name_and_a_task_with_no_lineage(self):
        self.assertEqual(set(ha.named_mbpp({"name": "dafny_synthesis_task_id_95__smallestListLength"}, self.table)), {95})
        self.assertEqual(ha.named_mbpp({"name": "vericoding_da0140__minBacteria"}, self.table), {})
        self.assertEqual(ha.named_mbpp({"name": "mbpp_509__average_Odd"}, self.table), {})

    def test_gpl_origin_is_either_route(self):
        self.assertIsNotNone(ha.gpl_origin({"name": "vericoding_dj0091__cubeElement"}, self.table))
        self.assertIsNotNone(ha.gpl_origin({"name": "dafny_synthesis_task_id_95__smallestListLength"}, self.table))
        self.assertIsNone(ha.gpl_origin({"name": "clover_abs__abs"}, self.table))

    def test_an_empty_table_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "lineage.json"
            path.write_text(json.dumps({"schema": 1, "ids": {}}))
            with self.assertRaises(ValueError):
                ha.lineage(path)


class RowReadingTests(unittest.TestCase):
    def test_programs_are_read_from_the_answer_and_from_the_prompt(self):
        row = {"prompt": [{"role": "system", "content": "fix it"},
                          {"role": "user", "content": "This fails:\n\n" + fenced(DOUBLE)}],
               "chosen": fenced(CUBES)}
        got = ha.blocks(row)
        self.assertEqual(len(got), 2)
        self.assertTrue(any("double_it" in b for b in got) and any("cubes" in b for b in got))

    def test_the_same_program_twice_is_one_program(self):
        self.assertEqual(len(ha.blocks({"prompt": fenced(DOUBLE), "chosen": fenced(DOUBLE)})), 1)


class CandidateTests(unittest.TestCase):
    def test_a_point_the_requires_excludes_is_not_a_failure(self):
        # MBPP 605's points: 13, 7 and -1010; the lift's gate asked for every point passed and never met the pair
        entry = {"points": [point([("int", 13)], ("bool", True)), point([("int", 7)], ("bool", True)),
                            point([("int", -1010)], ("bool", False))]}
        task = surface.parse(IS_PRIME.strip() + "\n")
        self.assertEqual(ha.quiet(task, entry["points"]), ["pass", "pass", "requires-excluded"])
        got = ha.candidates(task, {605: (entry, "held-out")})
        self.assertEqual([(c["problem"], c["dropped"]) for c in got], [(605, None)])

    def test_a_failed_point_or_no_passed_point_is_not_a_candidate(self):
        task = surface.parse(IS_PRIME.strip() + "\n")
        self.assertIsNone(ha.quiet(task, [point([("int", 13)], ("bool", False))]))
        self.assertIsNone(ha.quiet(task, [point([("int", -1)], ("bool", False))]))          # excluded only
        self.assertIsNone(ha.quiet(task, [point([("int", 13), ("int", 2)], ("bool", True))]))  # arity

    def test_a_length_argument_is_found_and_left_out(self):
        # MBPP 804: is_Product_Even(arr, n)
        entry = {"points": [point([("seq", [1, 2, 3]), ("int", 3)], ("bool", True)),
                            point([("seq", [1, 2, 1, 4]), ("int", 4)], ("bool", True)),
                            point([("seq", [1, 1]), ("int", 2)], ("bool", False))]}
        self.assertEqual(ha.length_arguments(entry), [(1, 0)])
        task = surface.parse(ANY_EVEN.strip() + "\n")
        self.assertIsNone(ha.quiet(task, entry["points"]))
        got = ha.candidates(task, {804: (entry, "held-out")})
        self.assertEqual([(c["problem"], c["dropped"]) for c in got], [(804, [1, 0])])

    def test_an_int_that_is_not_always_the_length_is_not_a_length_argument(self):
        entry = {"points": [point([("seq", [1, 2, 3]), ("int", 3)], ("int", 0)),
                            point([("seq", [1, 2, 3]), ("int", 2)], ("int", 0))]}
        self.assertEqual(ha.length_arguments(entry), [])


@unittest.skipUnless(ha.SPLIT.exists() and ha.POLICY.exists() and ha.WIDER_POLICY.exists(), "the split or a policy is absent")
class PolicyTests(unittest.TestCase):
    def test_the_panels_are_182_and_95(self):
        eval_ids = {int(i) for i in json.loads(ha.SPLIT.read_text())["eval_ids"]}
        clean = ha.clean_182(eval_ids)
        self.assertEqual(len(clean), 182)
        self.assertEqual(len(ha.dev_95()), 95)
        for tid in (447, 472, 474, 605, 644, 804):                 # the six that are the problem's own formalisation
            self.assertNotIn(tid, clean)
        self.assertTrue(clean <= eval_ids)

    def test_the_wider_panel_is_the_new_problems_the_rows_never_matched(self):
        wider = set(se.wider_pool())
        clean = ha.wider_clean()
        self.assertEqual((len(wider), len(clean)), (145, 114))
        self.assertTrue(clean <= wider and not clean & {int(i) for i in json.loads(ha.SPLIT.read_text())["eval_ids"]})
        self.assertIn(95, wider - clean)                           # MBPP-DFY's smallestListLength is in the rows
        self.assertIn(616, clean)                                  # its elementWiseModulo left the corpus on 2026-09-21
        self.assertTrue(ha.wider_flagged() <= ha.removed_ids())

    def test_a_policy_that_removes_nothing_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "policy.json"
            path.write_text(json.dumps({"schema": 1, "overlap_eval_ids": [], "dev_overlap_ids": []}))
            with self.assertRaises(ValueError):
                ha.policy(path)


def _pool_here() -> bool:
    try:
        pool = se.pool("v5")
    except BaseException:                                           # noqa: BLE001 -- a worktree without the data
        return False
    return 447 in pool and 605 in pool and bool(pool[447].get("points"))


@unittest.skipUnless(ha.SPLIT.exists() and _pool_here(), "pool v5 is not on this machine")
class AuditTests(unittest.TestCase):
    """The audit itself, on the pool: three rows it must flag for the reasons it met, one it must not."""

    def audit(self, rows, **kw):
        return ha.audit([("rows.jsonl", k, r) for k, r in enumerate(rows)], jobs=1, **kw)

    def test_lineage_and_twin(self):
        rows = [
            {"name": "vericoding_dd0763__isPrime", "kind": "spec-given", "chosen": fenced(IS_PRIME)},     # 605 by lineage
            {"name": "some_cubes", "kind": "spec-given", "chosen": fenced(CUBES)},                         # 447 by behaviour
            {"name": None, "kind": "debug", "prompt": [{"role": "user", "content": fenced(ANY_EVEN)}],     # 804, in a prompt,
             "chosen": fenced(DOUBLE)},                                                                    # without its length
        ]
        result = self.audit(rows)
        table = ha.by_problem(result["findings"])
        self.assertEqual(table[("held-out", 605)]["why"], ["lineage"])
        self.assertIn("twin", table[("held-out", 447)]["why"])
        self.assertIn("twin", table[("held-out", 804)]["why"])
        self.assertEqual({line for _f, line in result["flagged"]}, {0, 1, 2})
        twin = next(f for f in result["findings"] if f["problem"] == 804 and f["why"] == "twin")
        self.assertEqual(twin["detail"]["without_argument"], 1)

    def test_a_row_no_gated_problem_claims_passes(self):
        result = self.audit([{"name": "double_it", "kind": "spec-given", "chosen": fenced(DOUBLE)}])
        held = [f for f in result["findings"] if f["gate"] == "held-out" and f["problem"] in ha.clean_182(
            {int(i) for i in json.loads(ha.SPLIT.read_text())["eval_ids"]})]
        self.assertEqual(held, [])

    def test_refuse_gpl_flags_the_lineage_whatever_the_problem(self):
        row = {"name": "dafny_synthesis_task_id_95__smallestListLength", "kind": "spec-given", "chosen": fenced(DOUBLE)}
        self.assertEqual([f["why"] for f in self.audit([row], refuse_gpl=True)["findings"] if f["why"] == "gpl"], ["gpl"])
        self.assertEqual([f for f in self.audit([row])["findings"] if f["why"] == "gpl"], [])

    def test_a_row_that_answers_a_wider_problem_is_flagged_for_the_wider_panel(self):
        # MBPP 616, read only by the wider reader: tuple_modulo((10, 4, 5, 6), (5, 6, 7, 5)) == (0, 4, 5, 1)
        modulo = """
t 1
gate loops
task element_wise_modulo(a: seq, b: seq) returns (r: seq)
  requires len(a) == len(b)
  requires forall i in [0, len(b)) . b[i] != 0
  ensures len(r) == len(a)
  ensures forall i in [0, len(r)) . r[i] == a[i] % b[i]
{
  r := [];
  var i: int := 0;
  while i < len(a)
    invariant 0 <= i and i <= len(a)
    invariant len(r) == i
    invariant forall k in [0, i) . r[k] == a[k] % b[k]
    decreases len(a) - i
  {
    r := r + [a[i] % b[i]];
    i := i + 1;
  }
}
"""
        result = self.audit([{"name": "some_modulo", "kind": "spec-given", "chosen": fenced(modulo)}])
        self.assertIn(("wider", 616), ha.by_problem(result["findings"]))

    def test_the_gate_of_a_row_build(self):
        with tempfile.TemporaryDirectory() as d:
            rows = Path(d) / "rows.jsonl"
            rows.write_text(json.dumps({"name": "some_cubes", "chosen": fenced(CUBES)}) + "\n"
                            + json.dumps({"name": "double_it", "chosen": fenced(DOUBLE)}) + "\n")
            kept = Path(d) / "kept.jsonl"
            self.assertEqual(ha.main(["--rows", str(rows), "--jobs", "1", "--keep", str(kept)]), 1)
            self.assertEqual([json.loads(line)["name"] for line in kept.read_text().splitlines()], ["double_it"])
            # MBPP 447 left the panel on 2026-10-05: a row that matches it costs no measurement and is not refused
            self.assertEqual(ha.main(["--rows", str(rows), "--jobs", "1", "--panels"]), 0)


if __name__ == "__main__":
    unittest.main()
