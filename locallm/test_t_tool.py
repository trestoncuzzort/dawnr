"""test_t_tool.py: the t tool keeps the prompt's specification, not only its examples.

FINDINGS-repair-2026-09-26.md ("The t tool has a hole on specification
prompts"): 101 of 285 fold drafts that passed every example were not the
proved program because they had rewritten the declaration, requires or
ensures the prompt gave them -- `run()` only executes the body against the
example's value, so a narrowed `requires` that excludes none of the (usually
one or two) given examples, or a dropped or reweakened `ensures` conjunct,
was invisible to it. t_tool.spec_changed closes that hole; this file is its
contract: what must still be ALLOWED (renaming every declared name
consistently -- the task's own, its parameters, its return, a spec fun's own
parameters, a quantifier's bound variable -- and reordering the requires
list and, separately, the ensures list, since each is a set of conditions,
not a sequence) and what must be CAUGHT (anything else: a dropped, added or
reworded clause, a different arity or type, a spec fun added, removed,
renamed or redefined).

No torch: t_tool.py and chat_data.py are both standard-library-only, and
this file only needs them and dawnr_harness.checker.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "t"))

import chat_data  # noqa: E402
import t_tool  # noqa: E402
import surface  # noqa: E402
from dawnr_harness import checker  # noqa: E402

ABS = """t 1
task abs_val(x: int) returns (y: int)
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

SEARCH = """t 1
gate loops
task first_ge(a: seq, e: int) returns (n: int)
  ensures 0 <= n
  ensures n <= len(a)
  ensures n == len(a) or a[n] == e
  ensures forall i in [0, n) . e != a[i]
{
  n := 0;
  while n < len(a)
    invariant 0 <= n and n <= len(a)
    invariant forall j in [0, n) . e != a[j]
    decreases len(a) - n
  {
    if a[n] == e {
      return n;
    } else {
    }
    n := n + 1;
  }
}
"""

POWER = """t 1
task compute_power(n: int) returns (y: int)
  requires n >= 0
  ensures y >= 0
  ensures y == power(n)
spec fun power(n_v: int): int
  decreases n_v
= if n_v >= 0 then if n_v == 0 then 1 else 2 * power(n_v - 1) else 0
{
  y := 1;
}
"""


def spec_context(program: str, *examples: str) -> str:
    """The context chat_data.conversation builds for a "spec" prompt: its own
    SPEC_PROMPT and spec_text, real production code, so a test that passes
    here is a test of the actual prompt shape, not a hand-rolled guess at
    it."""
    return "\n".join([chat_data.SPEC_PROMPT, chat_data.spec_text(program), *examples])


def task_of(program: str) -> dict:
    return surface.parse(program)


class SpecHeaderFromContext(unittest.TestCase):
    def test_reads_back_exactly_the_declaration_requires_ensures(self):
        ctx = spec_context(ABS, "Example: abs_val(3) == 3")
        header = t_tool.spec_header_from_context(ctx)
        self.assertIsNotNone(header)
        self.assertEqual(header, chat_data.spec_text(ABS))
        # the header never carries a body; parsing it back gives the same task with an empty one
        self.assertEqual(t_tool.parse_spec_header(header), {**task_of(ABS), "body": []})

    def test_none_without_a_t_head_line(self):
        for ctx in ("", None, "Example: abs_val(3) == 3",
                    "Problem: absolute value\nSignature: abs_val(int) -> int\nExample: abs_val(3) == 3"):
            self.assertIsNone(t_tool.spec_header_from_context(ctx))

    def test_stops_before_the_example_lines_not_at_end_of_context(self):
        ctx = spec_context(ABS, "Example: abs_val(3) == 3", "Example: abs_val(-3) == 3")
        header = t_tool.spec_header_from_context(ctx)
        self.assertNotIn("Example:", header)

    def test_unparseable_header_is_none_not_a_crash(self):
        ctx = "t 1\nthis is not a task at all\nExample: f(1) == 1"
        self.assertIsNone(t_tool.parse_spec_header(t_tool.spec_header_from_context(ctx)))


class SpecChangedAllowedVariation(unittest.TestCase):
    """What FINDINGS-repair-2026-09-26.md's own "next" line asked for: renamed
    consistently, and reordered clauses, must not be reported as a change."""

    def test_identical_is_unchanged(self):
        self.assertIsNone(t_tool.spec_changed(task_of(ABS), task_of(ABS)))

    def test_renamed_parameter_and_return_consistently(self):
        renamed = ABS.replace("x", "n").replace("y", "r")
        self.assertIsNone(t_tool.spec_changed(task_of(ABS), task_of(renamed)))

    def test_reordered_ensures_clauses(self):
        lines = chat_data.spec_text(ABS).split("\n")
        ensures = [ln for ln in lines if ln.strip().startswith("ensures")]
        self.assertEqual(len(ensures), 2)
        reordered_body = ABS.replace(ensures[0] + "\n" + ensures[1], ensures[1] + "\n" + ensures[0])
        self.assertNotEqual(reordered_body, ABS)
        self.assertIsNone(t_tool.spec_changed(task_of(ABS), task_of(reordered_body)))

    def test_reordered_requires_clauses(self):
        two_requires = POWER.replace("requires n >= 0", "requires n >= 0\n  requires n < 1000000")
        reordered = two_requires.replace("requires n >= 0\n  requires n < 1000000",
                                         "requires n < 1000000\n  requires n >= 0")
        self.assertIsNone(t_tool.spec_changed(task_of(two_requires), task_of(reordered)))

    def test_renamed_quantifier_bound_variable(self):
        renamed = SEARCH.replace("forall i in", "forall k in").replace("e != a[i]", "e != a[k]")
        self.assertNotEqual(renamed, SEARCH)
        self.assertIsNone(t_tool.spec_changed(task_of(SEARCH), task_of(renamed)))

    def test_spec_funs_own_parameter_renamed(self):
        renamed = (POWER.replace("power(n_v: int)", "power(m: int)")
                        .replace("decreases n_v", "decreases m")
                        .replace("if n_v >= 0 then if n_v == 0 then 1 else 2 * power(n_v - 1) else 0",
                                 "if m >= 0 then if m == 0 then 1 else 2 * power(m - 1) else 0"))
        self.assertIsNone(t_tool.spec_changed(task_of(POWER), task_of(renamed)))


class SpecChangedCaughtChanges(unittest.TestCase):
    def assertChanged(self, prompt_program: str, draft_program: str, *substrings: str):
        reason = t_tool.spec_changed(task_of(prompt_program), task_of(draft_program))
        self.assertIsNotNone(reason, "expected a spec change to be reported")
        for s in substrings:
            self.assertIn(s, reason)

    def test_dropped_ensures_clause(self):
        dropped = ABS.replace("  ensures x >= 0 ==> x == y\n", "")
        self.assertChanged(ABS, dropped, "ensures")

    def test_added_narrowing_requires(self):
        narrowed = ABS.replace("task abs_val(x: int) returns (y: int)\n",
                               "task abs_val(x: int) returns (y: int)\n  requires x != 999999999\n")
        self.assertChanged(ABS, narrowed, "requires")

    def test_reworded_ensures_same_clause_count(self):
        weakened = ABS.replace("x >= 0 ==> x == y", "x >= 0 ==> x <= y")
        self.assertChanged(ABS, weakened, "ensures")

    def test_parameter_count_differs(self):
        extra_param = ABS.replace("abs_val(x: int)", "abs_val(x: int, unused: int)")
        self.assertChanged(ABS, extra_param, "parameter")

    def test_parameter_type_differs(self):
        retyped = ABS.replace("abs_val(x: int)", "abs_val(x: bool)").replace(
            "ensures x >= 0 ==> x == y", "ensures true").replace("ensures x < 0 ==> x + y == 0", "ensures true")
        self.assertChanged(ABS, retyped, "parameter 1")

    def test_return_type_differs(self):
        retyped = ABS.replace("returns (y: int)", "returns (y: bool)").replace(
            "ensures x >= 0 ==> x == y", "ensures true").replace("ensures x < 0 ==> x + y == 0", "ensures true")
        self.assertChanged(ABS, retyped, "returns")

    def test_dropped_forall_ensures_is_caught_not_hidden_by_renaming(self):
        dropped = SEARCH.replace("  ensures forall i in [0, n) . e != a[i]\n", "")
        self.assertChanged(SEARCH, dropped, "ensures")

    def test_spec_fun_renamed_is_not_allowed(self):
        renamed = POWER.replace("power(n)", "pw(n)").replace("spec fun power", "spec fun pw").replace(
            "2 * power(n_v - 1)", "2 * pw(n_v - 1)")
        self.assertChanged(POWER, renamed, "power")

    def test_spec_fun_definition_changed(self):
        changed = POWER.replace("2 * power(n_v - 1)", "3 * power(n_v - 1)")
        self.assertChanged(POWER, changed, "power")

    def test_spec_fun_decreases_changed(self):
        changed = POWER.replace("decreases n_v", "decreases n_v + 1")
        self.assertChanged(POWER, changed, "power")

    def test_spec_fun_removed(self):
        # the ensures that uses it must go too, or this would (correctly) also be caught as an ensures
        # change; dropping both isolates the spec-fun-removal reason on its own
        removed = POWER.replace("  ensures y == power(n)\n", "").replace(
            "spec fun power(n_v: int): int\n  decreases n_v\n"
            "= if n_v >= 0 then if n_v == 0 then 1 else 2 * power(n_v - 1) else 0\n", "")
        self.assertChanged(POWER, removed, "power")


class EndToEnd(unittest.TestCase):
    """t_tool.call itself: silent when there is nothing to compare against or
    nothing changed, reporting and stopping before the examples otherwise."""

    def test_no_formal_specification_in_context_is_unaffected(self):
        # a "Problem:"-style prompt states no formal specification at all
        out = t_tool.call(ABS, "Problem: absolute value\nSignature: abs_val(int) -> int\n"
                                "Example: abs_val(3) == 3\nExample: abs_val(-3) == 3")
        self.assertNotIn("specification", out)
        self.assertEqual(out, "parses: yes\nwell formed: yes\nexample 1: pass\nexample 2: pass")

    def test_faithful_draft_reports_no_specification_line(self):
        renamed = ABS.replace("x", "n").replace("y", "r")
        ctx = spec_context(ABS, "Example: abs_val(3) == 3")
        out = t_tool.call(renamed, ctx)
        self.assertNotIn("specification", out)
        self.assertIn("example 1: pass", out)

    def test_changed_specification_reported_and_examples_not_run(self):
        dropped = ABS.replace("  ensures x >= 0 ==> x == y\n", "")
        ctx = spec_context(ABS, "Example: abs_val(3) == 3")
        out = t_tool.call(dropped, ctx)
        self.assertIn("specification: spec changed: ensures", out)
        self.assertNotIn("example ", out)                 # the (still passing) example is not misleadingly shown

    def test_checker_failing_treats_it_as_a_failure(self):
        dropped = ABS.replace("  ensures x >= 0 ==> x == y\n", "")
        ctx = spec_context(ABS, "Example: abs_val(3) == 3")
        out = t_tool.call(dropped, ctx)
        self.assertTrue(checker.failing(out))
        ok, _ = checker.check(dropped, ctx)
        self.assertFalse(ok)

    def test_redacted_verdict_reports_the_class_never_the_reason(self):
        # redacted_verdict is what the checker hook uses for a program found in another tool's input or
        # output (or the final answer) -- text the harness does not trust -- so its note must never quote
        # the program's or the specification's own words (checker.py's redacted_verdict docstring); only
        # the fixed tag "class=spec-changed" may say a change was found.
        dropped = ABS.replace("  ensures x >= 0 ==> x == y\n", "")
        ctx = spec_context(ABS, "Example: abs_val(3) == 3")
        ok, verdict = checker.redacted_verdict(dropped, ctx)
        self.assertFalse(ok)
        self.assertIn("class=spec-changed", verdict)
        self.assertNotIn("ensures", verdict)
        self.assertNotIn("abs_val", verdict)


if __name__ == "__main__":
    unittest.main()
