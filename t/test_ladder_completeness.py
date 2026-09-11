"""Plain-python tests for t/ladder_completeness.py and the
`harness.ladder_rungs` enumerator it is built on (ROADMAP WS-19 move 6,
2026-09-11).

Checked once by hand and pinned here as regression tests: on `t/tasks/abs.json`
(a top-level `if`, no loop) `ladder_rungs` returns the operators harness.py's
own module docstring names as reachable from that shape -- collapse-if,
negate-cond, compare-flip, boundary-swap, off-by-one (two literal
directions), and wrong-constant (two directions on each of the `if`'s two
branches: `neg(x)` and the bare `var x`, both proved int-rooted) -- 10 rungs
total, 8 refuted (fraction 8/10). On `t/tasks/sum_upto.json` (one `while`
with two invariants) it returns invariant-drop (one rung per invariant) plus
the extensional operators reachable inside the loop body and its condition,
plus wrong-constant (the `int` literals: `r := 0`, `i`'s `0` initialiser)
and wrong-operator (the `+` nodes in `i := i + 1` and `r := r + i`, each
tried against its two ARITH_ALT alternates) -- 24 rungs total, 19 refuted
(fraction 19/24). No `if` in sum_upto's body, so collapse-if and negate-cond
contribute nothing there, and `wrong-var` has no candidate in abs (only one
int-typed name, `x`, in scope; no other name of the same type to
substitute). Twin-ladder wave, 2026-09-11 (ROADMAP 16.2): the twins
committed under t/tasks are unaffected -- wrong-constant and wrong-operator
sit below every rung above, so a task whose twin was already found earlier
keeps that exact twin, byte-identical (measured directly, all 34 tasks'
twin bodies dumped before and after, zero diffs).

No corpus, no network, no model, no kernel. Standard library plus t's own
modules.

Run as: cd <repo>/t && python3 test_ladder_completeness.py
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

import harness
import ladder_completeness as lc
import tasks_io

HERE = Path(__file__).resolve().parent

UNIT_TESTS = []


def test(fn):
    UNIT_TESTS.append(fn)
    return fn


def _rungs(name: str):
    task = harness.load(tasks_io.find(HERE / "tasks", name))
    return task, harness.ladder_rungs(task)


# --------------------------------------------------------------- abs.json --

@test
def test_abs_rung_count_and_operators():
    _task, rungs = _rungs("abs")
    assert len(rungs) == 10, rungs
    ops = [tag for tag, _twin, _w in rungs]
    # docstring-named operators reachable from a lone top-level `if`,
    # no loop: no invariant-drop, no drop-guard (the `if` has no `and`),
    # no wrong-var (only one int name, `x`, in scope), no wrong-operator
    # (neither branch has a `+`/`-`/`*`/`div`/`mod` node: `neg(x)` is
    # unary, and the else-branch is a bare `var`). wrong-constant fires on
    # both branches' whole right-hand side (`neg(x)`, then the bare `x`),
    # +1 then -1 each.
    assert ops == ["collapse-if", "negate-cond", "compare-flip",
                    "boundary-swap", "off-by-one", "off-by-one#1",
                    "wrong-constant", "wrong-constant#1",
                    "wrong-constant#2", "wrong-constant#3"], ops


@test
def test_abs_refuted_fraction():
    _task, rungs = _rungs("abs")
    total = len(rungs)
    refuted = sum(1 for _tag, _twin, w in rungs if w is not None)
    assert (total, refuted) == (10, 8), (total, refuted)
    assert abs(refuted / total - 8 / 10) < 1e-9


@test
def test_abs_every_rung_has_its_operator_and_twin_body():
    task, rungs = _rungs("abs")
    for tag, twin, _w in rungs:
        assert isinstance(tag, str) and tag
        assert isinstance(twin, list)
        assert twin != task["body"]        # a mutation, not a copy


# ----------------------------------------------------------- sum_upto.json --

@test
def test_sum_upto_rung_count():
    _task, rungs = _rungs("sum_upto")
    assert len(rungs) == 24, rungs


@test
def test_sum_upto_operators_present():
    _task, rungs = _rungs("sum_upto")
    ops = {tag.split("#")[0] for tag, _twin, _w in rungs}
    # invariant-drop (one rung per invariant, two invariants) plus the
    # extensional operators the while-loop's condition and body reach:
    # compare-flip, boundary-swap, off-by-one, wrong-var, plus the
    # twin-ladder wave's two new rungs: wrong-constant (the `int` literals
    # `r := 0` and `i`'s `0` initialiser) and wrong-operator (the `+` in
    # `i := i + 1` and `r := r + i`). No collapse-if or negate-cond (no
    # `if` anywhere in the body) and no drop-guard (no `and`-conjunct
    # condition).
    assert ops == {"invariant-drop", "compare-flip", "boundary-swap",
                   "off-by-one", "wrong-var", "wrong-constant",
                   "wrong-operator"}, ops
    n_inv = sum(1 for tag, _t, _w in rungs if tag.startswith("invariant-drop"))
    assert n_inv == 2, n_inv         # sum_upto's while states two invariants


@test
def test_sum_upto_refuted_fraction():
    _task, rungs = _rungs("sum_upto")
    total = len(rungs)
    refuted = sum(1 for _tag, _twin, w in rungs if w is not None)
    assert (total, refuted) == (24, 19), (total, refuted)
    assert abs(refuted / total - 19 / 24) < 1e-9


@test
def test_sum_upto_invariant_drop_witnesses_are_forcing():
    # invariant_witness only ever returns a witness that forces a sound
    # kernel to refute (exit entailment or preservation), by construction
    # (interp.invariant_witness's own docstring); both of sum_upto's
    # invariant-drop rungs should therefore come back refuted.
    _task, rungs = _rungs("sum_upto")
    inv = [(tag, w) for tag, _twin, w in rungs if tag.startswith("invariant-drop")]
    assert len(inv) == 2, inv
    for tag, w in inv:
        assert w is not None, (tag, "expected a forcing witness")
        assert w.get("_kind") in ("exit", "preservation"), (tag, w)


# --------------------------------------------------- twin-ladder wave, 16.2 --
# The no-twin rows named in ROADMAP 16.2 (dafny_synthesis 234 cubeVolume, 242
# countCharacters, 269 asciiValue, 626 areaOfLargestTriangleInSemicircle, 792
# countLists) are all one shape: a single int param, a single `assign`
# computing an arithmetic expression with no literal, no `at`/`update`/
# `fill`/`slice`, and no `if`/loop -- rungs 1-8 have nothing to mutate.
# CUBE_SHAPED reproduces that shape directly rather than depending on the
# lifted corpus files under /tmp, so this test needs no external fixture.
CUBE_SHAPED = {
    "name": "cube_shaped",
    "params": [{"name": "size", "type": "int"}],
    "returns": [{"name": "volume", "type": "int"}],
    "requires": [{"op": ">", "args": [{"var": "size"}, {"int": 0}]}],
    "ensures": [{"op": "==", "args": [{"var": "volume"},
                {"op": "*", "args": [{"op": "*", "args": [{"var": "size"},
                {"var": "size"}]}, {"var": "size"}]}]}],
    "body": [{"assign": ["volume", {"op": "*", "args": [
        {"op": "*", "args": [{"var": "size"}, {"var": "size"}]},
        {"var": "size"}]}]}],
}


@test
def test_straight_line_arithmetic_had_no_operator_before_wrong_constant():
    # Without rungs 9-10, this exact body has no `if`, no loop, no literal,
    # and no `at`/`update`/`fill`/`slice`: every one of rungs 1-8 yields
    # zero candidates, which is what made this shape a no-twin row.
    for op_name, gen in harness.EXTENSIONAL:
        if op_name in ("wrong-constant", "wrong-operator"):
            continue
        assert list(gen(CUBE_SHAPED["body"], harness._scope(CUBE_SHAPED))) == [], op_name


@test
def test_straight_line_arithmetic_gets_a_grounded_twin():
    rungs = harness.ladder_rungs(CUBE_SHAPED)
    assert rungs, "wrong-constant should give this shape at least one rung"
    tags = [tag for tag, _twin, _w in rungs]
    # wrong-constant fires once on the whole `size*size*size` (+1, -1);
    # wrong-operator fires on each of the two `*` nodes (2 alternates each).
    assert tags == ["wrong-constant", "wrong-constant#1", "wrong-operator",
                    "wrong-operator#1", "wrong-operator#2",
                    "wrong-operator#3"], tags
    # `ensures volume == size*size*size` is a plain equality, so `+- 1`
    # falsifies it at every size the ladder tries: both directions refute.
    wc = [w for tag, _t, w in rungs if tag.startswith("wrong-constant")]
    assert all(w is not None for w in wc), wc

    twin, op, w = harness.twin_for(CUBE_SHAPED)
    assert op == "wrong-constant", op
    assert twin is not None and w is not None and w.get("_ens") is True, w


# A medianOfThree-shaped task: its `ensures` only pins the result to be ONE
# OF the three params (both disjuncts hold by reflexivity for whichever
# param comes out), so every rung that merely picks a DIFFERENT param
# (collapse-if, wrong-var) produces a value that still satisfies `ensures`
# -- a "+nonrefuting" fallback, never a forcing witness -- until
# wrong-constant offsets the result to a value equal to none of the three.
MEDIAN_SHAPED = {
    "name": "median_shaped",
    "params": [{"name": "a", "type": "int"}, {"name": "b", "type": "int"},
               {"name": "c", "type": "int"}],
    "returns": [{"name": "median", "type": "int"}],
    "requires": [],
    "ensures": [{"op": "or", "args": [
        {"op": "==", "args": [{"var": "median"}, {"var": "a"}]},
        {"op": "or", "args": [
            {"op": "==", "args": [{"var": "median"}, {"var": "b"}]},
            {"op": "==", "args": [{"var": "median"}, {"var": "c"}]}]}]}],
    "body": [{"assign": ["median", {"var": "b"}]}],
}


@test
def test_loose_membership_ensures_only_broken_by_wrong_constant():
    twin, op, w = harness.twin_for(MEDIAN_SHAPED)
    assert twin is not None and w is not None
    assert op == "wrong-constant", (
        "every earlier rung on this body only swaps which param comes "
        f"out, which this ensures cannot tell apart: got {op}")
    assert w.get("_ens") is True, w

    rungs = harness.ladder_rungs(MEDIAN_SHAPED)
    wrong_var = [w for tag, _t, w in rungs if tag.startswith("wrong-var")]
    assert wrong_var and all(w is None for w in wrong_var), (
        "wrong-var swaps a/b/c, which this ensures accepts either way", wrong_var)


# ------------------------------------------------------- module-level glue --

@test
def test_is_restate_body_true_shape():
    task = {
        "returns": [{"name": "r", "type": "int"}],
        "ensures": [{"op": "==", "args": [{"var": "r"}, {"var": "x"}]}],
        "body": [{"assign": ["r", {"var": "x"}]}],
    }
    assert lc.is_restate_body(task) is True


@test
def test_is_restate_body_false_when_body_computes_something_else():
    task = {
        "returns": [{"name": "r", "type": "int"}],
        "ensures": [{"op": "==", "args": [{"var": "r"}, {"var": "x"}]}],
        "body": [{"assign": ["r", {"op": "neg", "args": [{"var": "x"}]}]}],
    }
    assert lc.is_restate_body(task) is False


@test
def test_is_restate_body_false_on_abs_and_sum_upto():
    # abs's ensures is a disjunction, not a single `==`; sum_upto's is an
    # equation between two products, not `ret == body-expression`.
    for name in ("abs", "sum_upto"):
        task = harness.load(tasks_io.find(HERE / "tasks", name))
        assert lc.is_restate_body(task) is False, name


@test
def test_fraction_and_kernel_buckets():
    assert lc.fraction_bucket(4, 6) == "some"
    assert lc.fraction_bucket(6, 6) == "all"
    assert lc.fraction_bucket(0, 6) == "none"
    assert lc.fraction_bucket(0, 0) == "none"
    assert lc.kernel_bucket(7, 7) == "all seven"
    assert lc.kernel_bucket(3, 7) == "some column"
    assert lc.kernel_bucket(0, 7) == "none"


def run() -> None:
    failures = 0
    for fn in UNIT_TESTS:
        try:
            fn()
            print(f"{fn.__name__}: pass")
        except AssertionError as e:
            failures += 1
            print(f"{fn.__name__}: FAILED: {e}")
        except Exception as e:                                  # noqa: BLE001
            failures += 1
            traceback.print_exc()
            print(f"{fn.__name__}: FAILED (exception): {e}")
    if failures:
        raise AssertionError(f"{failures} of {len(UNIT_TESTS)} test(s) failed")
    print(f"test_ladder_completeness: all {len(UNIT_TESTS)} checks passed")


if __name__ == "__main__":
    try:
        run()
    except AssertionError as e:
        print(f"FAILED: {e}")
        sys.exit(1)
    sys.exit(0)
