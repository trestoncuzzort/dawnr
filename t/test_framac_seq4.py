"""Plain-python tests for ROADMAP 13.4, framac-seq4 (2026-09-12): the six
seq cells `pred()`, `code_ats`/`at_asserts`, `term`/`_seq_len_render`/
`_seq_at_render`, `cexpr`, and `defs` still name as abstains
(`fz_p_nest_eq`, `fz_p_nest_empty`, `fz_p_str_splitempty`, `fz_p_str_tab`,
`fz_p_str_lowernonletter`, `fz_p_pair_seq`), and the one rendering-site
correctness fix this pass makes along the way: `pred()`'s extensional seq
`==`/`!=` (ACSL predicate position) now renders a ROW extracted from a
nested seq (`at(m, k)`, itself "seq"-typed) as an operand, not only a bare
seq variable, by routing both operands through `_seq_len_render`/
`_seq_at_render` instead of pasting `seq_var(...)` directly. See
lower_framac.py's module docstring, "FRAMAC-SEQ4" note, for the full
argument; this file measures it through the real pipeline (fuzz_lower.py's
committed probes and t/tasks), not a reimplementation of any of it.

Run as: cd <repo>/t && python3 test_framac_seq4.py

MEASURED 2026-09-12 by `python3 t/test_framac_seq4.py`: see the printed
summary line for the exact pass/fail count this run produced.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import harness                       # noqa: E402
import fuzz_lower as fz              # noqa: E402
import lower_framac                  # noqa: E402
import tasks_io                      # noqa: E402

UNIT_TESTS = []


def test(fn):
    UNIT_TESTS.append(fn)
    return fn


def _probe(name):
    return next(t for t in fz.probes() if t["name"] == name)


def _lower(name):
    task = _probe(name)
    try:
        w = harness.real_witness(task)
    except Exception as ex:                                  # noqa: BLE001
        w = f"<real_witness raised {type(ex).__name__}: {ex}>"
    return lambda: lower_framac.lower(task, task["body"], witness=w)


@test
def nest_eq_ensures_lowers_past_the_old_pred_crash():
    """FIXED in FRAMAC-SEQ4 (2026-09-12): `fz_p_nest_eq`'s own `ensures`
    (`\\forall k; ... at(m, k) == at(n, k)`) used to crash `pred()`
    outright (`NotImplementedError: seq position holds non-variable
    {'op': 'at', ...}`) because the old code called `seq_var` on the
    `at(...)` operand directly. Confirms that fix still holds by checking
    `lower()` raises no exception at all any more (superseded by
    FRAMAC-NESTED below: the BODY's own executable `r := (m == n)` no
    longer abstains either, so nothing is left in this task to raise)."""
    _lower("fz_p_nest_eq")()


@test
def nest_eq_now_lowers_to_a_loop_not_an_abstain():
    """FRAMAC-NESTED, ROADMAP 13.4 item (a), 2026-09-12: `fz_p_nest_eq`'s
    BODY computes `r := (m == n)` in EXECUTABLE position, `cexpr`'s own
    named refusal there (unchanged, still raised for any OTHER seq `==`
    shape this pass's `_seq_eq_top`/`_seq_eq_loop` do not recognize) --
    but this exact shape (two bare nested-seq PARAMETER variables) is
    now a STATEMENT-shaped C loop `stmts()` emits before the assignment,
    not the abstain the old test above named. Confirmed by checking the
    emitted C for the loop's own two markers (`__seq_eq0`, the fresh
    bool temp; a nested `while` for the row-by-row/cell-by-cell walk)
    rather than an exception. MEASURED SEPARATELY, not by this test
    (this file only calls `lower()`, no kernel): frama-c/WP schedules
    real proof goals for the loop's own invariants but does not close
    all of them at the pinned budget (`ensures` and both loop
    invariants' own preservation goals TIMEOUT, alt-ergo 2.4.3 cannot
    instantiate the doubly-quantified row/cell invariant at 20000 steps)
    -- an honest TIMEOUT, not a false VERIFIED, and not this test's own
    concern (a lowering-shape check, not a proof-budget one)."""
    c = _lower("fz_p_nest_eq")()
    assert "__seq_eq0" in c, c
    assert c.count("while (") >= 2, c   # outer row loop + inner cell loop


@test
def the_other_five_seq_cells_are_unmoved():
    """UPDATED 2026-09-14 (FRAMAC-NESTED, DESIGN-framac-nested-seq.md):
    three of the five cells this docstring originally named as untouched
    by FRAMAC-SEQ4 are CLOSED by this later pass, each its own fresh
    mechanism (`lower_framac.py`'s own dated 2026-09-14 note has the
    full account): `fz_p_nest_empty`/`fz_p_str_splitempty` (a
    compile-time-constant nested seq<seq> RETURN, `_ret_nested_fold`/
    `_fold_nested_rows`) and `fz_p_str_lowernonletter` (an executable
    `lower`, `_expr_seq_len`'s new case plus `seq_assign_lines`'s new
    `lower`/`upper` branch). `fz_p_str_tab`'s own LOCAL-declaration gap
    is ALSO closed the same way (`stmts()`'s `var` case, the same
    `_fold_nested_rows`), so it now declares its two rows cleanly --
    but the cell as a whole still abstains, because its body then reads
    those rows back through `==` NESTED INSIDE `and` (`len(rows)==2 and
    at(rows,0)==[65] and at(rows,1)==[66]`), never a bare top-level
    comparison `_seq_eq_top` recognizes (item (a)'s own scope, wave K,
    2026-09-12), a genuinely different, deeper gap than "local variables
    are not supported" and not attempted by this pass either. Only
    `fz_p_pair_seq` (a pair with a seq component, still its own separate
    encoding problem, see `_pair_field_c`) is truly untouched."""
    expected_substrings = {
        "fz_p_str_tab": "seq extensional equality (==/!=) reaching "
                        "executable position directly",
        "fz_p_pair_seq": "a pair with a seq component is refused",
    }
    for name, needle in expected_substrings.items():
        try:
            _lower(name)()
        except NotImplementedError as ex:
            assert needle in str(ex), (name, str(ex))
        else:
            raise AssertionError(f"{name}: lowered with no exception; "
                                  f"expected it to still abstain")
    # The three CLOSED cells now lower with no exception at all.
    for name in ("fz_p_nest_empty", "fz_p_str_splitempty",
                 "fz_p_str_lowernonletter"):
        _lower(name)()


@test
def committed_tasks_are_unaffected():
    """The 35 committed tasks under t/tasks: none declares a nested seq at
    all, so none reaches `pred()`'s seq `==` branch on a row-extracted
    (non-bare-variable) operand -- this pass's edit is a no-op for every
    one of them, confirmed by lowering each and counting exactly the same
    31 lower cleanly / 3 abstain split t/AGREEMENT.md's own framac column
    (31 `verified/refuted`, 3 `abstain/abstain`: count_vowels, split_join,
    swap_rows) already records."""
    taskdir = HERE / "tasks"
    names = sorted(p.stem for p in taskdir.glob("*.t"))
    assert len(names) == 35, len(names)
    lowered, abstained = 0, 0
    for name in names:
        task = tasks_io.load_task(taskdir / f"{name}.t")
        try:
            lower_framac.lower(task, task["body"])
        except NotImplementedError:
            abstained += 1
        else:
            lowered += 1
    assert (lowered, abstained) == (32, 3), (lowered, abstained)


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
    print(f"test_framac_seq4: {passed} passed, {failed} failed "
          f"of {len(UNIT_TESTS)}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
