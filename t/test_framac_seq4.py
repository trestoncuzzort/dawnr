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
    """UPDATED TWICE. 2026-09-14 (FRAMAC-NESTED, DESIGN-framac-nested-
    seq.md) closed three of the five cells this docstring originally
    named as untouched by FRAMAC-SEQ4, each its own fresh mechanism
    (`lower_framac.py`'s own dated 2026-09-14 note has the full
    account): `fz_p_nest_empty`/`fz_p_str_splitempty` (a compile-time-
    constant nested seq<seq> RETURN, `_ret_nested_fold`/
    `_fold_nested_rows`) and `fz_p_str_lowernonletter` (an executable
    `lower`).

    2026-09-19 (ROADMAP 13.4) closes the last two, so this test now pins
    the opposite fact for every one of the five: all five LOWER, none
    abstains. `fz_p_str_tab` reads its constant-folded rows back through
    a seq `==` NESTED INSIDE an `and`, which `_seq_eq_hoist` now lifts
    into the loops `_seq_eq_loop` already builds, with the literal
    operand declared as a local array; `fz_p_pair_seq` is a pair with a
    seq component, which `_pair_flat` now FLATTENS into separate C
    parameters rather than asking `_pair_field_c` for a struct field it
    still, correctly, refuses to name. The named refusals both of them
    used to reach are still live for the shapes that have no encoding --
    a pair with a seq component as a RETURN or a LOCAL, and a pair of
    two seqs -- and those are checked in `pair_seq_refusals_are_still_
    named` below, so nothing here is traded for a silent guess."""
    for name in ("fz_p_nest_empty", "fz_p_str_splitempty",
                 "fz_p_str_lowernonletter", "fz_p_str_tab",
                 "fz_p_pair_seq"):
        _lower(name)()


@test
def str_tab_hoists_its_two_row_comparisons_into_loops():
    """`fz_p_str_tab`'s emitted C, checked directly rather than through
    the kernel: the constant-folded seq<seq> local's own three
    declarations, one declared local array per seq LITERAL operand, one
    `while` per comparison, and the two temps the rewritten `and` reads
    instead of the comparisons it replaced."""
    c = _lower("fz_p_str_tab")()
    assert "int rows_data[2] = {65, 66};" in c, c
    assert "int rows_off[3] = {0, 1, 2};" in c, c
    assert "int rows_n = 2;" in c, c
    assert "int __seq_eq0_lit0[1] = {65};" in c, c
    assert "int __seq_eq1_lit0[1] = {66};" in c, c
    # Two comparison loops, counted by their own flag rather than by the
    # bare keyword: the emitted header carries a `while` of its own (the
    # string library's ACSL block, pulled in by `split`).
    assert c.count("while (__seq_eq") == 2, c
    assert "int __seq_eq0_v = __seq_eq0;" in c, c
    assert "int __seq_eq1_v = __seq_eq1;" in c, c
    assert "r = ((rows_n == 2) && __seq_eq0_v && __seq_eq1_v);" in c, c


@test
def pair_seq_flattens_the_parameter_and_keeps_its_obligations():
    """`fz_p_pair_seq`'s emitted C: the pair PARAMETER is three C
    parameters, not a struct, and the seq half carries exactly the
    `requires` a bare seq parameter would. No `struct t_pair_` is
    declared anywhere, which is the point -- `_pair_field_c`'s refusal
    of a seq struct FIELD is not weakened, it is never reached."""
    c = _lower("fz_p_pair_seq")()
    assert "int fz_p_pair_seq_t(int *p_fst, int p_fst_n, int p_snd)" in c, c
    assert "struct t_pair_" not in c, c
    assert "requires p_fst_n >= 0;" in c, c
    assert "requires \\valid_read(p_fst + (0 .. p_fst_n - 1));" in c, c
    assert "r = p_fst[p_snd];" in c, c


@test
def pair_seq_refusals_are_still_named():
    """The three shapes `lower()` refuses BY NAME around the flattened
    parameter, each built here rather than taken from a probe because no
    probe has one: a pair-with-a-seq RETURN, a pair-with-a-seq LOCAL,
    and a pair of two seqs. Each must raise NotImplementedError (the
    harness's abstain), never lower."""
    seq_int = {"pair": ["seq", "int"]}
    cases = [
        ("return", {
            "t": 1, "name": "t_pair_seq_ret",
            "params": [{"name": "s", "type": "seq"}],
            "returns": [{"name": "r", "type": seq_int}],
            "requires": [], "ensures": [],
            "body": [{"assign": ["r", {"op": "pair", "args": [
                {"var": "s"}, {"int": 0}]}]}]},
         "pair RETURN with a seq component"),
        ("local", {
            "t": 1, "name": "t_pair_seq_local",
            "params": [{"name": "s", "type": "seq"}],
            "returns": [{"name": "r", "type": "int"}],
            "requires": [], "ensures": [],
            "body": [{"var": {"name": "q", "type": seq_int,
                              "init": {"op": "pair", "args": [
                                  {"var": "s"}, {"int": 0}]}}},
                     {"assign": ["r", {"int": 0}]}]},
         "pair LOCAL with a seq component"),
        ("two-seqs", {
            "t": 1, "name": "t_pair_two_seqs",
            "params": [{"name": "p", "type": {"pair": ["seq", "seq"]}}],
            "returns": [{"name": "r", "type": "int"}],
            "requires": [], "ensures": [],
            "body": [{"assign": ["r", {"op": "len",
                                       "args": [{"op": "fst", "args": [
                                           {"var": "p"}]}]}]}]},
         "two seq components"),
    ]
    for label, task, needle in cases:
        try:
            lower_framac.lower(task, task["body"])
        except NotImplementedError as ex:
            assert needle in str(ex), (label, str(ex))
        else:
            raise AssertionError(f"{label}: lowered with no exception; "
                                 f"expected a named refusal")


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
