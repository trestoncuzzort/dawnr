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

2026-09-12 (ROADMAP 16.2, "twin-order"): the wrong-constant/wrong-operator
claim above ("the twins committed under t/tasks are unaffected") was true
of THAT wave; it is not true of this one. `twin_for` and `ladder_rungs`
now try the EXTENSIONAL rungs (collapse-if through wrong-operator) FIRST,
in their existing order, and the invariant-drop candidates LAST, reversing
the prior order -- SPEC.md's dated paragraph in "The twins" gives the
reason (an INVARIANT-DROP twin is not a wrong program; a value witness
that falsifies `ensures` is preferred whenever the body has one). Measured
directly: of the 34 committed tasks, the 13 whose twin was previously
invariant-drop all get a NEW twin (a behavioral rung the ladder already
had, just tried later before): `all_nonneg`, `contains`, `count_matches`,
`count_vowels`, `digit_sum`, `filter_pos`, `first_even`, `is_prime`,
`linear_search`, `reverse`, `row_max_len`, `seq_max`, `sum_upto`; the other
21, whose twin was already extensional, keep the exact same twin body
(the ordering only ever changes a rung that used to lose to
invariant-drop). `sum_upto`'s own rung/refuted-fraction counts above are
UNCHANGED (24 rungs, 19 refuted): `ladder_rungs` enumerates every rung
regardless of order, so reordering `twin_for`'s SELECTION changes which
rung wins, never the set `ladder_rungs` returns or their witnesses.

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


# ------------------------------------------------- twin-order wave, 16.2 --
# 2026-09-12: EXTENSIONAL rungs now win over invariant-drop whenever a body
# has a behavioral one. `first_even` (a committed task, t/tasks/first_even.t)
# is one of the 13 committed twins this reorder changes -- a loop with an
# early `return i;` inside its body -- so it doubles as the fixture for the
# early-return regression in interp.invariant_witness below (measured
# directly: `dafny_synthesis_task_id_414__anyValueExists`, reproduced here
# as ANY_VALUE_EXISTS_SHAPED, is the exact JSON body ROADMAP 16.2 names as
# minting a spurious "preservation" witness before the fix).

@test
def test_loop_task_now_gets_a_behavioral_twin_first():
    task = harness.load(tasks_io.find(HERE / "tasks", "first_even"))
    twin, op, w = harness.twin_for(task)
    assert twin is not None and w is not None
    assert not op.startswith("invariant-drop"), (
        "first_even has a behavioral rung (collapse-if on its early-return "
        f"`if`), which twin-order now tries before invariant-drop: got {op}")
    assert w.get("_ens") is True, w
    # ladder_rungs still enumerates the invariant-drop candidate; it comes
    # LAST in the list now, and this task's own two invariants (i's bounds,
    # the "no even seen yet" search invariant) are both still refuted when
    # tried -- so the reorder changes WHICH rung wins, not whether
    # invariant-drop remains a rung at all.
    rungs = harness.ladder_rungs(task)
    inv_positions = [i for i, (tag, _t, _w) in enumerate(rungs)
                     if tag.startswith("invariant-drop")]
    assert inv_positions, "first_even states invariants; some rung must be invariant-drop"
    assert min(inv_positions) > 0, (
        "invariant-drop must not be the first rung under twin-order", rungs[0])


# `dafny_synthesis_task_id_414__anyValueExists`'s own JSON (ROADMAP 16.2's
# seven named rows), reproduced verbatim rather than read from the lifted
# corpus (which sits outside this repo, under t/out/lifted-tasks, not a
# fixture this test can depend on). Its loop's `if` returns as soon as it
# finds a match (`result := true; return result;`), WITHOUT incrementing
# `i_v` first -- the exact shape that makes dropping the loop's own
# "not found yet" invariant (its 4th, `result == exists k in [0, i_v) ...`)
# look, to a preservation check that ignores the return, like it broke:
# `i_v` is unchanged (still short of the range the survivor asks about)
# but `result` is now True.
ANY_VALUE_EXISTS_SHAPED = {'body': [{'assign': ['result', {'bool': False}]}, {'var': {'init': {'args': [{'var': 'seq1'}], 'op': 'len'}, 'name': 'h', 'type': 'int'}}, {'var': {'init': {'int': 0}, 'name': 'i_v', 'type': 'int'}}, {'while': {'body': [{'if': {'cond': {'exists': {'body': {'args': [{'args': [{'var': 'seq2'}, {'var': 'k_v3'}], 'op': 'at'}, {'args': [{'var': 'seq1'}, {'var': 'i_v'}], 'op': 'at'}], 'op': '=='}, 'hi': {'args': [{'var': 'seq2'}], 'op': 'len'}, 'lo': {'int': 0}, 'var': 'k_v3'}}, 'else': [], 'then': [{'assign': ['result', {'bool': True}]}, {'return': ['result', {'var': 'result'}]}]}}, {'assign': ['i_v', {'args': [{'var': 'i_v'}, {'int': 1}], 'op': '+'}]}], 'cond': {'args': [{'var': 'i_v'}, {'var': 'h'}], 'op': '<'}, 'decreases': {'args': [{'var': 'h'}, {'var': 'i_v'}], 'op': '-'}, 'invariants': [{'args': [{'int': 0}, {'var': 'i_v'}], 'op': '<='}, {'args': [{'var': 'i_v'}, {'var': 'h'}], 'op': '<='}, {'args': [{'args': [{'int': 0}, {'var': 'i_v'}], 'op': '<='}, {'args': [{'var': 'i_v'}, {'args': [{'var': 'seq1'}], 'op': 'len'}], 'op': '<='}], 'op': 'and'}, {'args': [{'var': 'result'}, {'exists': {'body': {'exists': {'body': {'args': [{'args': [{'var': 'seq2'}, {'var': 'k_v2'}], 'op': 'at'}, {'args': [{'var': 'seq1'}, {'var': 'k_v'}], 'op': 'at'}], 'op': '=='}, 'hi': {'args': [{'var': 'seq2'}], 'op': 'len'}, 'lo': {'int': 0}, 'var': 'k_v2'}}, 'hi': {'var': 'i_v'}, 'lo': {'int': 0}, 'var': 'k_v'}}], 'op': '=='}]}}], 'ensures': [{'args': [{'var': 'result'}, {'exists': {'body': {'exists': {'body': {'args': [{'args': [{'var': 'seq2'}, {'var': 'k'}], 'op': 'at'}, {'args': [{'var': 'seq1'}, {'var': 'i'}], 'op': 'at'}], 'op': '=='}, 'hi': {'args': [{'var': 'seq2'}], 'op': 'len'}, 'lo': {'int': 0}, 'var': 'k'}}, 'hi': {'args': [{'var': 'seq1'}], 'op': 'len'}, 'lo': {'int': 0}, 'var': 'i'}}], 'op': '=='}], 'gate': 'loops', 'name': 'dafny_synthesis_task_id_414__anyValueExists', 'params': [{'name': 'seq1', 'type': 'seq'}, {'name': 'seq2', 'type': 'seq'}], 'requires': [], 'returns': [{'name': 'result', 'type': 'bool'}], 't': 1}


@test
def test_early_return_is_not_a_spurious_preservation_witness():
    rungs = harness.ladder_rungs(ANY_VALUE_EXISTS_SHAPED)
    inv = [(tag, w) for tag, _t, w in rungs if tag.startswith("invariant-drop")]
    assert len(inv) == 4, inv     # one rung per invariant, four invariants
    # Before the fix, dropping the 1ST invariant ("0 <= i_v") produced a
    # "preservation" witness at seq1=[0], seq2=[0], h=1, i_v=0, result=False
    # (measured directly, t/interp.py before this change): the loop's one
    # iteration takes the early-return branch (result := true; return), so
    # `i_v` is never incremented, and a preservation check that re-checks
    # `kept` at that post-body state (rather than `ensures`) sees the 4th,
    # SURVIVING invariant ("result == exists k in [0, i_v) ...") go from
    # vacuously true to false while `result` is now True -- a state the
    # loop NEVER revisits (the method returns from inside the `if`), so it
    # was never a preservation obligation. `ensures` (`result == exists i
    # in [0, len(seq1)) ...`) DOES hold there (seq1[0] is exactly why the
    # branch matched), so the fixed interpreter finds no witness on this
    # rung any more.
    tag0, w0 = inv[0]
    assert tag0 == "invariant-drop", tag0
    assert w0 is None, (
        "dropping the 1st invariant must not mint a preservation witness "
        "out of an early return the loop never revisits", w0)
    # Rung #3 (dropping the 4th invariant, the search-tracking one itself)
    # still legitimately returns a witness -- an EXIT witness, at a state
    # h=0 (seq1 empty) that the standard partial-correctness while rule
    # (SPEC.md gate 2: modified variables are HAVOCKED, not simulated) does
    # not rule out even though real execution never reaches it with
    # result=True: nothing to do with the early-return fix, a genuine
    # finding that this invariant is load-bearing for THAT rung.
    tag3, w3 = inv[3]
    assert tag3 == "invariant-drop#3", tag3
    assert w3 is not None and w3.get("_kind") == "exit", w3
    # And twin_for's own selection for this task is a behavioral rung
    # anyway (collapse-if, tried before invariant-drop under twin-order),
    # so rung #3's genuine finding never becomes this task's twin.
    twin, op, w = harness.twin_for(ANY_VALUE_EXISTS_SHAPED)
    assert twin is not None and w is not None
    assert not op.startswith("invariant-drop"), op
    assert w.get("_ens") is True, w


@test
def test_decorative_kind_re_derived_label():
    """harness.decorative_kind's INVARIANT-DROP branch reads "re-derived",
    not "unsound" (SPEC.md "The twins", 2026-09-12 paragraph): a kernel
    that verifies both real and twin when the twin's own witness is an
    invariant-drop proof witness (kind "exit" or "preservation") re-derived
    the dropped annotation, which is not a soundness finding the way a
    VALUE witness (`_ens is True`) is."""
    from verifiers import Outcome
    assert harness.decorative_kind(
        Outcome.VERIFIED, Outcome.VERIFIED, {"_kind": "exit"}) == "re-derived"
    assert harness.decorative_kind(
        Outcome.VERIFIED, Outcome.VERIFIED, {"_kind": "preservation"}) == "re-derived"
    assert harness.decorative_kind(
        Outcome.VERIFIED, Outcome.VERIFIED, {"_ens": True, "_kind": "value"}) == "unsound"


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
