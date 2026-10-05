"""t/invariant_repair.py: a proof that fails on its loop invariants, repaired by rule. Reordering and dropping
invariants (Houdini; DafnyPro, arXiv:2601.05385) never touches the program, and the repaired text is a new
candidate that still has to be proved."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import invariant_repair as ir                                   # noqa: E402
import surface                                                  # noqa: E402
from verifiers import dafny as dafny_adapter                    # noqa: E402

needs_dafny = pytest.mark.skipif(not dafny_adapter.DAFNY, reason="Dafny is not installed here")

LARGEST = """t 1
gate loops
task largest(xs: seq) returns (r: int)
  requires len(xs) > 0
  ensures exists i in [0, len(xs)) . r == xs[i]
  ensures forall j in [0, len(xs)) . r >= xs[j]
{
  r := xs[0];
  var i: int := 1;
  while i < len(xs)
INVARIANTS
    decreases len(xs) - i
  {
    if xs[i] > r {
      r := xs[i];
    } else {
    }
    i := i + 1;
  }
}
"""
BOUND = "    invariant i >= 0 and i <= len(xs)"
ALL = "    invariant forall j in [0, i) . r >= xs[j]"
SOME = "    invariant exists k in [0, i) . r == xs[k]"
WRONG = "    invariant r > i"


def task(*invariants):
    return surface.parse(LARGEST.replace("INVARIANTS", "\n".join(invariants)))


def texts(t):
    return [surface.pexpr(i) for w in ir.loops(t) for i in w["invariants"]]


def test_the_invariants_over_plain_numbers_go_first_and_the_rest_keep_their_order():
    moved = ir.reordered(task(ALL, SOME, BOUND))
    assert texts(moved) == ["i >= 0 and i <= len(xs)", "forall j in [0, i) . r >= xs[j]", "exists k in [0, i) . r == xs[k]"]
    assert ir.reordered(task(BOUND, ALL, SOME)) is None                               # already in a checkable order
    assert ir.plain(task(BOUND)["body"][2]["while"]["invariants"][0]) and not ir.plain(task(ALL)["body"][2]["while"]["invariants"][0])


def test_nothing_but_invariants_may_differ_between_a_program_and_its_repair():
    a = task(ALL, SOME, BOUND)
    assert ir.same_program(a, ir.reordered(a)) and ir.same_program(a, ir.without(a, [(0, 0)]))
    other = surface.parse(LARGEST.replace("INVARIANTS", BOUND).replace("if xs[i] > r", "if xs[i] >= r"))
    assert not ir.same_program(task(BOUND), other)
    weaker = surface.parse(LARGEST.replace("INVARIANTS", BOUND).replace("  ensures forall j in [0, len(xs)) . r >= xs[j]\n", ""))
    assert not ir.same_program(task(BOUND), weaker)                                    # a specification is not an annotation


def scripted(*verdicts):
    queue, seen = list(verdicts), []

    def diagnose(t):
        seen.append(texts(t))
        return dict({"verified": False, "undefined": [], "failing": [], "other": 0}, **queue.pop(0))
    diagnose.seen = seen
    return diagnose


def test_an_undefined_invariant_is_met_by_reordering_and_a_failing_one_by_dropping_it():
    d = scripted({"undefined": [(0, 0), (0, 1)]}, {"failing": [(0, 3)]}, {"verified": True})
    r = ir.repair(task(ALL, SOME, WRONG, BOUND), d)
    assert r["verified"] and not r["as written"] and len(r["steps"]) == 2
    assert texts(r["task"]) == ["r > i", "i >= 0 and i <= len(xs)", "forall j in [0, i) . r >= xs[j]"] or \
        texts(r["task"]) == ["i >= 0 and i <= len(xs)", "r > i", "forall j in [0, i) . r >= xs[j]"]
    assert d.seen[1][:2] == ["r > i", "i >= 0 and i <= len(xs)"]                         # both are plain, in their written order


def test_what_cannot_be_repaired_by_rule_is_left_alone():
    assert ir.repair(task(BOUND, ALL, SOME), scripted({"verified": True})) == {"verified": True, "task": None, "steps": [], "as written": True}
    # Dafny's complaint is about the postcondition: no invariant is named, nothing is done
    r = ir.repair(task(BOUND, ALL), scripted({"other": 1}))
    assert r == {"verified": False, "task": None, "steps": [], "as written": False}
    # every round names another invariant and none ends in a proof: it stops, and hands back no task
    forever = scripted(*[{"failing": [(0, 0)]}] * (ir.ROUNDS + 1))
    r = ir.repair(task(BOUND, ALL, SOME, WRONG, WRONG.replace(">", ">=")), forever)
    assert r["verified"] is False and r["task"] is None and len(r["steps"]) == ir.ROUNDS


@needs_dafny
def test_the_35b_writers_largest_is_unproved_as_written_and_proved_with_the_bound_first():
    written = task(ALL, SOME, BOUND)
    d = ir.diagnose(written)
    assert d["verified"] is False and d["undefined"] == [(0, 0), (0, 1)] and not d["failing"]
    r = ir.repair(written)
    assert r["verified"] and r["steps"] == ["the invariants over plain numbers moved before those that index or quantify"]
    assert texts(r["task"])[0] == "i >= 0 and i <= len(xs)" and ir.same_program(written, r["task"])


@needs_dafny
def test_a_surplus_invariant_that_is_not_inductive_is_dropped_and_a_wrong_program_stays_unproved():
    r = ir.repair(task(BOUND, ALL, SOME, WRONG))
    assert r["verified"] and "r > i" not in texts(r["task"]) and len(texts(r["task"])) == 3
    assert r["steps"] == ["1 invariant dropped that Dafny could not prove on entry or maintained"]
    wrong = surface.parse(LARGEST.replace("INVARIANTS", "\n".join([ALL, SOME, BOUND])).replace("if xs[i] > r", "if xs[i] < r"))
    r = ir.repair(wrong)
    assert r["verified"] is False and r["task"] is None                                # the smallest is not the largest, however the invariants are arranged
