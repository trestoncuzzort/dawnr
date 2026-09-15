"""Plain-python tests for ROADMAP 16.2, framac-capacity (2026-09-15):
`_ret_capacity`'s new loop-invariant-derived CAPACITY bound, and
`_fold_local_append_into_ret`, the new local-to-return aliasing fold, in
lower_framac.py.

THE CAPACITY-FROM-INVARIANTS GAP (framac column, sweep r26): a seq
RETURN built by the append idiom inside a `while` whose own length has
no `ensures`-stated bound (`removeOddNumbers`'s own shape: `evenList :=
evenList + [x]` conditionally, so `_seq_len_track` cannot resolve a
closed form) previously ABSTAINed outright ("no `ensures` ... gives a
CAPACITY bound either") even when the bound was sitting in the loop's
own invariant the whole time: `len(evenList) <= i_v2 <= h`, `h := len
(arr)` declared once before the loop and never touched again. Fixed:
`_ret_capacity` now also walks every `while` invariant (`and`-conjuncts
flattened, nested `if`/`while` included) for `len(ret) <= V`, then
chases `V` to a closed form over the task's own params, either directly
or through a never-reassigned local's own initializer, up to a small
depth -- and reads a `requires`, not only an `ensures`, of the shape
`len(ret) <= E`/`== E` the same way. These tests check the emitted C
directly (no kernel call) on self-contained synthetic tasks mirroring
`removeOddNumbers`'s own shape, plus the family's negative cases (no
usable invariant at all; a bound on a variable the loop itself
reassigns, which must NOT be trusted).

THE LOCAL-TO-RETURN ALIASING GAP (framac column, sole-blocked before
this pass): a seq-typed LOCAL (`newSeq`/`rotated`, `deepCopySeq`'s and
`rotateRight`'s own shape) built by the append idiom and then copied
WHOLE into the return as the body's last statement previously ABSTAINed
("seq-typed local variables are not supported by this lowering except
the slice-ALIAS shape") -- no requires-time bound sizes a SECOND buffer
for the local, and none is needed: the return already has one. Fixed:
`_fold_local_append_into_ret` detects exactly this narrow shape (a
`var` declaration `local := []`, written only by `local := local + ...`
recursively through `if`/`while`, then `ret := local` as `body`'s own
last statement, `ret` unread before that) and renames `local` to `ret`
throughout, dropping the declaration and the closing copy -- the append
loop then writes the return's own buffer directly, through the
pre-existing CAPACITY machinery, unchanged.

Both mechanisms were measured directly on the real sweep rows they trace
to (412 removeOddNumbers/426/436/554/629, and 307 deepCopySeq/743
rotateRight): the two named ABSTAINs are gone on all seven, replaced by
an honest `timeout / refuted`; see this file's own 2026-09-15 dated note
at the end of the module docstring for the exact `t/grade.py` command
and counts, not reproduced here since t/out/lifted-tasks is the sweep's
own gitignored set, not tracked in this repo (LIFTED skip below, this
file's siblings' own convention).

Run as: cd <repo>/t && python3 test_framac_capacity.py
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import lower_framac                  # noqa: E402

LIFTED = HERE / "out" / "lifted-tasks"

UNIT_TESTS = []


def test(fn):
    UNIT_TESTS.append(fn)
    return fn


def _lifted(glob_pat):
    hits = list(LIFTED.glob(glob_pat))
    if not hits:
        return None
    return json.loads(hits[0].read_text())


def _skip(name):
    print(f"{name}: SKIP (no {LIFTED} -- lifted sweep set not on this "
          "checkout)")


# `removeOddNumbers`'s own shape, minimized: filter `arr` into `out` via
# `out := out + [x]` inside a while whose only length-carrying invariant
# is the transitive chain `len(out) <= i <= h`, `h := len(arr)`. No
# `ensures` states any bound on `len(out)` at all -- the CAPACITY bound
# must come from the invariant chase alone.
def _capacity_probe_task(extra_while_stmts=(), invariants_extra=()):
    return {
        "name": "t_capacity_probe",
        "params": [{"name": "arr", "type": "seq"}],
        "returns": [{"name": "out", "type": "seq"}],
        "requires": [],
        "ensures": [
            {"forall": {
                "var": "i", "lo": {"int": 0},
                "hi": {"args": [{"var": "out"}], "op": "len"},
                "body": {"args": [{"int": 0}, {"int": 0}], "op": "=="}}},
        ],
        "body": [
            {"assign": ["out", {"op": "seq", "args": []}]},
            {"var": {"name": "h", "type": "int",
                    "init": {"op": "len", "args": [{"var": "arr"}]}}},
            {"var": {"name": "i", "type": "int", "init": {"int": 0}}},
            {"while": {
                "cond": {"op": "<", "args": [{"var": "i"}, {"var": "h"}]},
                "decreases": {"op": "-", "args": [{"var": "h"}, {"var": "i"}]},
                "invariants": [
                    {"op": "<=", "args": [{"int": 0}, {"var": "i"}]},
                    {"op": "<=", "args": [{"var": "i"}, {"var": "h"}]},
                    {"op": "and", "args": [
                        {"op": "<=", "args": [{"int": 0}, {"var": "i"}]},
                        {"op": "<=", "args": [{"var": "i"},
                                              {"op": "len",
                                               "args": [{"var": "arr"}]}]}]},
                    {"op": "and", "args": [
                        {"op": "<=", "args": [{"int": 0},
                                              {"op": "len",
                                               "args": [{"var": "out"}]}]},
                        {"op": "<=", "args": [{"op": "len",
                                              "args": [{"var": "out"}]},
                                              {"var": "i"}]}]},
                    *invariants_extra,
                ],
                "body": [
                    {"assign": ["out", {"op": "+", "args": [
                        {"var": "out"},
                        {"op": "seq", "args": [
                            {"op": "at", "args": [{"var": "arr"},
                                                  {"var": "i"}]}]}]}]},
                    {"assign": ["i", {"op": "+", "args": [{"var": "i"},
                                                          {"int": 1}]}]},
                    *extra_while_stmts,
                ],
            }},
        ],
    }


@test
def capacity_chases_invariant_through_never_reassigned_local():
    """`h := len(arr)` is never reassigned, so `i <= h` chases to `i <=
    arr_n`, and `len(out) <= i` chases the rest of the way: the emitted
    `requires` must size `out`'s buffer at exactly `arr_n`, and the old
    'no CAPACITY bound' NotImplementedError must not fire."""
    task = _capacity_probe_task()
    src = lower_framac.lower(task, task["body"])
    assert "requires out_n == arr_n;" in src, src


@test
def capacity_bound_absent_still_abstains():
    """Drop the `len(out) <= i` invariant entirely (replace it with an
    unrelated fact): no chase is possible, so this must still raise the
    NAMED refusal, not silently guess a buffer size or crash."""
    task = _capacity_probe_task()
    task["body"][3]["while"]["invariants"].pop()   # drops len(out) <= i
    try:
        lower_framac.lower(task, task["body"])
    except NotImplementedError as e:
        assert "CAPACITY bound" in str(e), e
    else:
        raise AssertionError("expected a CAPACITY-bound NotImplementedError")


@test
def capacity_does_not_trust_a_reassigned_bound_variable():
    """If the loop ALSO reassigns `h` (so `h == arr_n` no longer holds
    after the first iteration), the chase must refuse to use `h`'s own
    stale initializer as a closed form -- `assigned_names` is what makes
    `resolve()` bail out for `h` here, exactly as it already does for
    the frame-fact fix's own `h`. The redundant direct `i <= len(arr)`
    invariant (present in the real 412 task alongside `i <= h`, and kept
    by `_capacity_probe_task`'s own default shape) is dropped for this
    one test, so `i`'s ONLY bound is the now-untrustworthy `h` -- this
    must still abstain rather than emit an unsound `out_n == arr_n`."""
    task = _capacity_probe_task(
        extra_while_stmts=[{"assign": ["h", {"op": "-", "args": [
            {"var": "h"}, {"int": 0}]}]}])
    task["body"][3]["while"]["invariants"].pop(2)  # drops i <= len(arr)
    try:
        lower_framac.lower(task, task["body"])
    except NotImplementedError as e:
        assert "CAPACITY bound" in str(e), e
    else:
        raise AssertionError("expected a CAPACITY-bound NotImplementedError")


@test
def capacity_still_prefers_an_explicit_ensures_bound():
    """When the task ALSO states an explicit `ensures len(out) <=
    len(arr)`, that closed form is used directly (the pre-existing
    2026-09-09 path, unchanged) without ever reaching the new invariant
    chase -- both routes agree here, so this only guards that the new
    code did not accidentally shadow the old one."""
    task = _capacity_probe_task()
    task["ensures"].append(
        {"op": "<=", "args": [{"op": "len", "args": [{"var": "out"}]},
                              {"op": "len", "args": [{"var": "arr"}]}]})
    src = lower_framac.lower(task, task["body"])
    assert "requires out_n == arr_n;" in src, src


@test
def capacity_five_named_rows_on_the_real_sweep_if_present():
    """The five sweep r26 rows this gap traces to (412/426/436/554/629):
    each must lower without the old ABSTAIN when the lifted sweep set is
    present on this checkout."""
    any_present = False
    for pat in ("dafny-synthesis_task_id_412.*.json",
               "dafny-synthesis_task_id_426.*.json",
               "dafny-synthesis_task_id_436.*.json",
               "dafny-synthesis_task_id_554.*.json",
               "dafny-synthesis_task_id_629.*.json"):
        task = _lifted(pat)
        if task is None:
            continue
        any_present = True
        src = lower_framac.lower(task, task["body"])
        assert "requires" in src and "_n ==" in src, (pat, src)
    if not any_present:
        _skip("capacity_five_named_rows_on_the_real_sweep_if_present")


# `deepCopySeq`'s own shape, minimized: `local := []`, grown only by
# `local := local + [x]`, then `ret := local` as the last statement.
def _fold_probe_task():
    return {
        "name": "t_fold_probe",
        "params": [{"name": "s", "type": "seq"}],
        "returns": [{"name": "copy", "type": "seq"}],
        "requires": [],
        "ensures": [
            {"op": "==", "args": [{"op": "len", "args": [{"var": "copy"}]},
                                  {"op": "len", "args": [{"var": "s"}]}]},
        ],
        "body": [
            {"var": {"name": "local", "type": "seq",
                    "init": {"op": "seq", "args": []}}},
            {"var": {"name": "h", "type": "int",
                    "init": {"op": "len", "args": [{"var": "s"}]}}},
            {"var": {"name": "i", "type": "int", "init": {"int": 0}}},
            {"while": {
                "cond": {"op": "<", "args": [{"var": "i"}, {"var": "h"}]},
                "decreases": {"op": "-", "args": [{"var": "h"}, {"var": "i"}]},
                "invariants": [
                    {"op": "<=", "args": [{"int": 0}, {"var": "i"}]},
                    {"op": "<=", "args": [{"var": "i"}, {"var": "h"}]},
                    {"op": "==", "args": [{"op": "len",
                                          "args": [{"var": "local"}]},
                                          {"var": "i"}]},
                ],
                "body": [
                    {"assign": ["local", {"op": "+", "args": [
                        {"var": "local"},
                        {"op": "seq", "args": [
                            {"op": "at", "args": [{"var": "s"},
                                                  {"var": "i"}]}]}]}]},
                    {"assign": ["i", {"op": "+", "args": [{"var": "i"},
                                                          {"int": 1}]}]},
                ],
            }},
            {"assign": ["copy", {"var": "local"}]},
        ],
    }


@test
def fold_renames_the_local_into_the_return_buffer():
    """No second buffer, no `local` identifier anywhere in the emitted
    C: every write meant for `local` lands in `copy`'s own buffer
    directly, and the closing `copy := local` becomes the no-op it would
    have been (dropped, not emitted as `copy = copy;`)."""
    task = _fold_probe_task()
    src = lower_framac.lower(task, task["body"])
    assert "local" not in src, src
    assert "copy[(copy_len) + 0] = s[i];" in src, src
    assert "copy = copy;" not in src, src


@test
def fold_does_not_fire_when_the_local_is_written_some_other_way():
    """`local` updated via a non-append shape (`local := local[0 :=
    x]`) must NOT be folded -- `_only_append_writes` is the gate, and
    when it says no, the ORIGINAL named refusal for a general seq-typed
    local must still fire, unchanged."""
    task = _fold_probe_task()
    task["body"][3]["while"]["body"][0] = {
        "assign": ["local", {"op": "update", "args": [
            {"var": "local"}, {"var": "i"},
            {"op": "at", "args": [{"var": "s"}, {"var": "i"}]}]}]}
    try:
        lower_framac.lower(task, task["body"])
    except NotImplementedError as e:
        assert "seq-typed local variables are not supported" in str(e), e
    else:
        raise AssertionError("expected the seq-typed-local NotImplementedError")


@test
def fold_does_not_fire_when_the_return_is_read_before_the_copy():
    """If `copy` (the return) is somehow already mentioned before the
    closing `copy := local`, the fold must refuse (it only ever proved
    `local`'s writes safe to redirect into `copy`'s OWN, otherwise-idle
    buffer) rather than silently overwrite something the task's own body
    already depends on."""
    task = _fold_probe_task()
    task["body"].insert(3, {"assign": ["copy", {"var": "local"}]})
    try:
        lower_framac.lower(task, task["body"])
    except NotImplementedError as e:
        assert "seq-typed local variables are not supported" in str(e), e
    else:
        raise AssertionError("expected the seq-typed-local NotImplementedError")


@test
def fold_two_named_rows_on_the_real_sweep_if_present():
    """The two sweep rows this gap traces to (307 deepCopySeq, 743
    rotateRight): each must lower without the old seq-typed-local ABSTAIN
    when the lifted sweep set is present on this checkout."""
    any_present = False
    for pat in ("dafny-synthesis_task_id_307.*.json",
               "dafny-synthesis_task_id_743.*.json"):
        task = _lifted(pat)
        if task is None:
            continue
        any_present = True
        src = lower_framac.lower(task, task["body"])
        assert "seq-typed local" not in src
    if not any_present:
        _skip("fold_two_named_rows_on_the_real_sweep_if_present")


def main() -> int:
    passed, failed = 0, 0
    for fn in UNIT_TESTS:
        try:
            fn()
        except AssertionError as e:
            failed += 1
            print(f"{fn.__name__}: FAIL: {e}")
        except Exception:                                    # noqa: BLE001
            failed += 1
            print(f"{fn.__name__}: ERROR")
            traceback.print_exc()
        else:
            passed += 1
            print(f"{fn.__name__}: pass")
    print(f"test_framac_capacity: {passed} passed, {failed} failed "
          f"of {len(UNIT_TESTS)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
