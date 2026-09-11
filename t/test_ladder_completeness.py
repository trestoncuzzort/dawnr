"""Plain-python tests for t/ladder_completeness.py and the
`harness.ladder_rungs` enumerator it is built on (ROADMAP WS-19 move 6,
2026-09-11).

Checked once by hand and pinned here as regression tests: on `t/tasks/abs.json`
(a top-level `if`, no loop) `ladder_rungs` returns the operators harness.py's
own module docstring names as reachable from that shape -- collapse-if,
negate-cond, compare-flip, boundary-swap, off-by-one (two literal directions)
-- 6 rungs total, 4 refuted (fraction 4/6). On `t/tasks/sum_upto.json` (one
`while` with two invariants) it returns invariant-drop (one rung per
invariant) plus the extensional operators reachable inside the loop body and
its condition -- 16 rungs total, 14 refuted (fraction 14/16). No `if` in
sum_upto's body, so collapse-if and negate-cond contribute nothing there,
and `wrong-var` has no candidate in abs (only one int-typed name, `x`, in
scope; no other name of the same type to substitute).

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
    assert len(rungs) == 6, rungs
    ops = [tag for tag, _twin, _w in rungs]
    # docstring-named operators reachable from a lone top-level `if`,
    # no loop: no invariant-drop, no drop-guard (the `if` has no `and`),
    # no wrong-var (only one int name, `x`, in scope).
    assert ops == ["collapse-if", "negate-cond", "compare-flip",
                    "boundary-swap", "off-by-one", "off-by-one#1"], ops


@test
def test_abs_refuted_fraction():
    _task, rungs = _rungs("abs")
    total = len(rungs)
    refuted = sum(1 for _tag, _twin, w in rungs if w is not None)
    assert (total, refuted) == (6, 4), (total, refuted)
    assert abs(refuted / total - 4 / 6) < 1e-9


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
    assert len(rungs) == 16, rungs


@test
def test_sum_upto_operators_present():
    _task, rungs = _rungs("sum_upto")
    ops = {tag.split("#")[0] for tag, _twin, _w in rungs}
    # invariant-drop (one rung per invariant, two invariants) plus the
    # extensional operators the while-loop's condition and body reach:
    # compare-flip, boundary-swap, off-by-one, wrong-var. No collapse-if or
    # negate-cond (no `if` anywhere in the body) and no drop-guard (no
    # `and`-conjunct condition).
    assert ops == {"invariant-drop", "compare-flip", "boundary-swap",
                   "off-by-one", "wrong-var"}, ops
    n_inv = sum(1 for tag, _t, _w in rungs if tag.startswith("invariant-drop"))
    assert n_inv == 2, n_inv         # sum_upto's while states two invariants


@test
def test_sum_upto_refuted_fraction():
    _task, rungs = _rungs("sum_upto")
    total = len(rungs)
    refuted = sum(1 for _tag, _twin, w in rungs if w is not None)
    assert (total, refuted) == (16, 14), (total, refuted)
    assert abs(refuted / total - 14 / 16) < 1e-9


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
