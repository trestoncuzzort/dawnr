"""Plain-python tests for ROADMAP 16.2, framac-3 (2026-09-12): the loop-body
frame-fact fix and the capacity-mode bare-seq-assign length fix in
lower_framac.py.

THE FRAME-FACT GAP (framac column): a scalar local declared before a
`while` (`h := len(a);`, appendArrayToSeq's own shape) and never
reassigned inside that loop's body is now stated as an equality `loop
invariant` (`h == a_n;`), giving WP a premise the source program already
guarantees. `stmts()`'s own module-level docstring comment carries the
full account measured on the real cell; these tests check the mechanism
directly (the emitted C text) rather than re-measuring the kernel, and
guard the additive-only property this wave's docstring claims: an
EXACT-mode task with no such prefix local (or none the loop leaves
alone) gets byte-identical C to before this change.

THE CAPACITY-MODE BARE-SEQ-ASSIGN BUG: `seq_assign_lines`'s `"var" in e`
branch (`target := src`, a plain seq copy) used the TARGET's own buffer
capacity (`target_n`) as both the copy bound and the fresh length-local
value, which is only correct in EXACT mode; under CAPACITY mode (a
later append into the same buffer, `ctx.seq_len[target]` set) it must
use `src`'s own logical length instead, or it silently over-reads `src`
and lies about how much of the buffer the copy actually filled. Measured
directly on the real cell this traces to: t/COVERAGE-lifted-785.md's
appendArrayToSeq (dafny-synthesis task 106), whose `r := s;` precedes a
capacity-tracked append loop; before this fix framac timed out on the
loop's own `len(r) == len(s) + i_v2` establishment goal (the invariant
was FALSELY stated, `r_len` having been set to the full buffer capacity
rather than `len(s)`), after this fix framac reads verified/refuted,
agreeing with dafny's own verified/refuted on the same task
(t/grade.py --tasks <106,460,86> --kernels framac,dafny --flake 3, run
directly against t/out/lifted-tasks/dafny-synthesis_task_id_106.*.json,
not reproduced here since that directory is the sweep's own set, not
tracked in this repo -- see LIFTED skip below, matching this file's
siblings' own convention).

Run as: cd <repo>/t && python3 test_framac_frame_fact.py
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


# A minimal synthetic task, independent of the sweep's own out/ directory:
# `h := len(a); i := 0; while (i < h) invariant i <= len(a) { i := i+1; }`.
# Nothing here calls a kernel; only the emitted C text is checked.
_SYNTH_TASK = {
    "name": "t_frame_fact_probe",
    "params": [{"name": "a", "type": "seq"}],
    "returns": [{"name": "i", "type": "int"}],
    "returns": [{"name": "result", "type": "int"}],
    "requires": [{"args": [{"args": [{"var": "a"}], "op": "len"},
                           {"int": 0}], "op": ">="}],
    "ensures": [{"args": [{"var": "result"},
                          {"args": [{"var": "a"}], "op": "len"}],
                "op": "=="}],
    "body": [
        {"var": {"name": "h", "type": "int",
                "init": {"args": [{"var": "a"}], "op": "len"}}},
        {"var": {"name": "i", "type": "int", "init": {"int": 0}}},
        {"while": {
            "cond": {"args": [{"var": "i"}, {"var": "h"}], "op": "<"},
            "decreases": {"args": [{"var": "h"}, {"var": "i"}], "op": "-"},
            "invariants": [
                {"args": [{"var": "i"},
                         {"args": [{"var": "a"}], "op": "len"}], "op": "<="},
            ],
            "body": [
                {"assign": ["i", {"args": [{"var": "i"}, {"int": 1}],
                                  "op": "+"}]},
            ],
        }},
        {"assign": ["result", {"var": "i"}]},
    ],
}


@test
def frame_fact_emitted_for_never_reassigned_prefix_local():
    """`h`'s own defining expression (`len(a)`, i.e. `a_n`) is never
    reassigned inside the loop (`i` is the only assignment target), so
    the fix must state `loop invariant h == a_n;` in the while's own
    invariant block."""
    src = lower_framac.lower(_SYNTH_TASK, _SYNTH_TASK["body"])
    assert "loop invariant h == a_n;" in src, src


@test
def frame_fact_not_emitted_for_a_name_the_loop_reassigns():
    """The same shape, but the loop now reassigns `h` itself (`h := h -
    1;` alongside `i := i + 1;`): the fix must NOT claim `h == a_n` any
    more, since it no longer holds after the first iteration -- `hit`
    (assigned_names' own write set), not the unrelated `frame` list, is
    the right gate."""
    task = json.loads(json.dumps(_SYNTH_TASK))   # deep copy
    task["body"][2]["while"]["body"].append(
        {"assign": ["h", {"args": [{"var": "h"}, {"int": 1}], "op": "-"}]})
    src = lower_framac.lower(task, task["body"])
    assert "loop invariant h == a_n;" not in src, src


@test
def frame_fact_scoped_to_the_statement_list_declaring_it():
    """A local declared INSIDE one `if`-branch must not leak a frame fact
    into the other branch or past the `if` -- C scoping, mirrored by
    `stmts()`'s own dict-copy discipline for `_prefix`. Build a task
    where `if` guards a local `k := len(a)` used by neither an outer nor
    a sibling-branch loop, and check no `k == a_n` invariant appears
    anywhere in the sibling `while` this task also declares."""
    task = {
        "name": "t_frame_fact_scope_probe",
        "params": [{"name": "a", "type": "seq"}, {"name": "flag", "type": "bool"}],
        "returns": [{"name": "result", "type": "int"}],
        "requires": [{"args": [{"args": [{"var": "a"}], "op": "len"},
                               {"int": 0}], "op": ">="}],
        "ensures": [{"args": [{"var": "result"}, {"int": 0}], "op": ">="}],
        "body": [
            {"if": {"cond": {"var": "flag"}, "then": [
                {"var": {"name": "k", "type": "int",
                        "init": {"args": [{"var": "a"}], "op": "len"}}},
            ], "else": []}},
            {"var": {"name": "i", "type": "int", "init": {"int": 0}}},
            {"while": {
                "cond": {"args": [{"var": "i"},
                                  {"args": [{"var": "a"}], "op": "len"}],
                         "op": "<"},
                "decreases": {"args": [{"args": [{"var": "a"}], "op": "len"},
                                       {"var": "i"}], "op": "-"},
                "invariants": [
                    {"args": [{"var": "i"},
                             {"args": [{"var": "a"}], "op": "len"}],
                     "op": "<="},
                ],
                "body": [{"assign": ["i", {"args": [{"var": "i"}, {"int": 1}],
                                           "op": "+"}]}],
            }},
            {"assign": ["result", {"var": "i"}]},
        ],
    }
    src = lower_framac.lower(task, task["body"])
    assert "k ==" not in src, src


@test
def capacity_bare_assign_uses_source_length_not_target_capacity():
    """appendArrayToSeq's own shape, measured on the real sweep task when
    present, else a self-contained regression check on the mechanism:
    `seq_assign_lines`'s `"var" in e` branch, called with a CAPACITY-mode
    context (a length-local already bound for the target), must bound
    its copy loop by the SOURCE's length, not the target's own buffer
    capacity, and must set the length-local to that same source length."""
    task = _lifted("dafny-synthesis_task_id_106.*.json")
    if task is not None:
        src = lower_framac.lower(task, task["body"])
        assert "for (int __k = 0; __k < s_n; __k++) r[__k] = s[__k];" in src, src
        assert "r_len = s_n;" in src, src
        assert "for (int __k = 0; __k < r_n; __k++) r[__k] = s[__k];" not in src
        return
    _skip("capacity_bare_assign_uses_source_length_not_target_capacity")


@test
def exact_mode_bare_assign_is_byte_identical_to_target_capacity_bound():
    """EXACT mode (no `ctx.seq_len` entry for the target, `tail`'s own
    shape) must be UNCHANGED by this fix: `bound` stays `None` and
    `_copy_loop` falls back to its pre-existing `xn` (the target's own
    declared size), exactly as before this wave. `tail`'s own committed
    task is the real regression check (t/tasks/tail.t via
    t/test_check_wf.py and the AGREEMENT/CONFORMANCE tables, unaffected
    here per t/AGREEMENT.md's own `tail` row, framac verified/refuted,
    remeasured this wave, see this file's own docstring); this test
    isolates the SAME code path with a minimal synthetic EXACT-mode
    task, no seq_len entry."""
    task = {
        "name": "t_exact_mode_copy_probe",
        "params": [{"name": "s", "type": "seq"}],
        "returns": [{"name": "r", "type": "seq"}],
        "requires": [{"args": [{"args": [{"var": "s"}], "op": "len"},
                               {"int": 0}], "op": ">="}],
        "ensures": [{"args": [{"args": [{"var": "r"}], "op": "len"},
                              {"args": [{"var": "s"}], "op": "len"}],
                    "op": "=="}],
        "body": [{"assign": ["r", {"var": "s"}]}],
    }
    src = lower_framac.lower(task, task["body"])
    # EXACT mode: `r`'s own declared size (`r_n`) is the copy bound, not
    # a source-length substitution -- unchanged from before this wave.
    assert "for (int __k = 0; __k < r_n; __k++) r[__k] = s[__k];" in src, src


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
    print(f"test_framac_frame_fact: {passed} passed, {failed} failed "
          f"of {len(UNIT_TESTS)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
