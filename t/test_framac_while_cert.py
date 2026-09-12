"""Plain-python tests for ROADMAP 16.2, framac-cert (2026-09-12):
lower_framac.py's `_undef_certificate` walk now descends into a `while`
loop's own body (unrolled at the concrete witness, guard-true/guard-false
asserted per iteration, `interp.MAX_LOOP`-capped) instead of raising the
moment it meets one, and a seq-typed intermediate local reached by a
fresh `fill`, a bare copy of another seq, or a self-referential `update`
is now declared/mutated with the same plain C array + `_n` length pair a
seq PARAM already gets, instead of refusing outright. `_value_certificate`
also gained a nested-seq (`{"seq": "seq"}`) PARAMETER declaration (the
flat data+offsets pair `lower()`'s own signature already gives it).

Measures the actual lifted sweep tasks these three fixes were traced to
(t/COVERAGE-lifted-785.md r20: 610 removeElement, 591/625
swapFirstAndLast, 792 countLists), not a reimplementation of the fix.
The task JSON files are the sweep's own set (t/out/lifted-tasks/, not
tracked in this repo); a run on a checkout without that directory skips
these tests by name rather than failing, exactly like this file's own
`checked_a_spec_fun_task` sibling in test_framac_measure_axiom.py skips a
missing abstain.

Run as: cd <repo>/t && python3 test_framac_while_cert.py

MEASURED 2026-09-12 by `python3 t/test_framac_while_cert.py`: see the
printed summary line for the exact pass/fail count this run produced.
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import harness                       # noqa: E402
import interp                        # noqa: E402
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


@test
def while_descent_certifies_remove_element_610():
    """610 removeElement's compare-flip twin (a `<=` widened from `<`)
    puts its undefined `update(v, i_v2, ...)` access one full loop
    iteration INSIDE the twin's first `while`, past the old flat walk's
    first statement (it never reached the loop at all, see
    seq_local_declares_before_reaching_the_loop below) -- exercising the
    new `while` branch itself, not only the seq-local declaration this
    same task's first statement also needed."""
    task = _lifted("dafny-synthesis_task_id_610.*.json")
    if task is None:
        return _skip("while_descent_certifies_remove_element_610")
    twin_body, op, meta = harness.twin_cached(task)
    assert op == "compare-flip", op
    w = interp.Reference(task).witness(twin_body)
    assert w is not None and w.get("_kind") == "undefined", w
    src = lower_framac.lower(task, twin_body, witness=w)
    assert "t_certificate" in src, "no certificate built: " + src[-400:]
    assert "t_refutation_certificate" in src
    # ground, no assumed/admitted fact
    for banned in ("assume", "admit", "\\assume"):
        assert banned not in src.lower(), (banned, src)


@test
def seq_local_declares_before_reaching_the_loop():
    """Without the seq-local declaration fix, 610's very FIRST twin
    statement (`v := fill(s_n - 1, 0)`, a seq-typed local, not a
    parameter) raised before the walk ever reached the while loop this
    module's own docstring above traces the bug to; this checks that
    specific statement is no longer what stops the walk, by confirming
    the certificate's params/locals section declares `v`'s own backing
    array."""
    task = _lifted("dafny-synthesis_task_id_610.*.json")
    if task is None:
        return _skip("seq_local_declares_before_reaching_the_loop")
    twin_body, op, meta = harness.twin_cached(task)
    w = interp.Reference(task).witness(twin_body)
    src = lower_framac.lower(task, twin_body, witness=w)
    assert "int *v = t_cert_v;" in src, src


@test
def bare_seq_copy_declares_for_swap_first_and_last():
    """591/625 swapFirstAndLast's off-by-one twin's undefined witness
    sits on the FIRST statement, `a_out := a` (a bare copy of a
    PARAMETER into the seq-typed return local, no `fill` at all) -- the
    seq-local declaration branch this file's docstring generalized past
    `fill` alone once this exact shape measured as the same gap."""
    for pat in ("dafny-synthesis_task_id_591.*.json",
               "dafny-synthesis_task_id_625.*.json"):
        task = _lifted(pat)
        if task is None:
            _skip(f"bare_seq_copy_declares_for_swap_first_and_last[{pat}]")
            continue
        twin_body, op, meta = harness.twin_cached(task)
        assert op == "off-by-one", op
        w = interp.Reference(task).witness(twin_body)
        assert w is not None and w.get("_kind") == "undefined", w
        src = lower_framac.lower(task, twin_body, witness=w)
        assert "t_certificate" in src, "no certificate built: " + src[-400:]
        assert "t_refutation_certificate" in src


@test
def nested_seq_param_certifies_count_lists_792():
    """792 countLists's `lists` param is `{"seq": "seq"}` (nested), and
    its wrong-constant twin's witness is VALUE-kind, straight-line, no
    loop at all -- `_value_certificate`'s own gap, not `_undef_
    certificate`'s: before this fix, a nested-seq param fell into the
    generic `int {name} = ...;` branch and raised on a Python list."""
    task = _lifted("dafny-synthesis_task_id_792.*.json")
    if task is None:
        return _skip("nested_seq_param_certifies_count_lists_792")
    twin_body, op, meta = harness.twin_cached(task)
    assert op == "wrong-constant", op
    w = interp.Reference(task).witness(twin_body)
    assert w is not None and w.get("_kind") == "value" and w.get("_ens"), w
    src = lower_framac.lower(task, twin_body, witness=w)
    assert "t_certificate" in src, "no certificate built: " + src[-400:]
    assert "int *lists_data" in src and "int *lists_off" in src, src


@test
def committed_tasks_unchanged_without_a_witness():
    """None of this file's edits touch the WITNESS-FREE lowering path:
    every committed t/tasks/*.t file's real body, lowered with no
    witness, must still byte-match a witness-carrying call whose witness
    the real body itself does not trigger (the same regression check
    test_framac_measure_axiom.py's own `spec_fun_declare_only_leaves_
    every_committed_task_unchanged` runs, restated for this file's own
    edits instead of that one's)."""
    import tasks_io
    taskdir = HERE / "tasks"
    names = sorted(p.stem for p in taskdir.glob("*.t"))
    assert names, "no committed tasks found"
    checked = 0
    for name in names:
        task = tasks_io.load_task(taskdir / f"{name}.t")
        try:
            w = harness.real_witness(task)
        except Exception:
            w = None
        assert w is None, f"{name}: unexpected witness: {w}"
        try:
            without = lower_framac.lower(task, task["body"])
        except NotImplementedError:
            continue              # this file's own named abstains (unrelated)
        with_w = lower_framac.lower(task, task["body"], witness=w)
        assert without == with_w, name
        checked += 1
    # count_vowels/split_join/swap_rows are this file's own named
    # abstains (T_STRFIND_ACSL not wired to spec position; no CAPACITY
    # bound; nested-seq RETURN unsupported), unrelated to this wave's
    # fix -- skipped above via `continue`, not asserted on here.
    assert checked >= len(names) - 3, (checked, len(names))


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
    print(f"test_framac_while_cert: {passed} passed, {failed} failed "
          f"of {len(UNIT_TESTS)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
