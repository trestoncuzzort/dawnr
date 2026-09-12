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
    """FIXED this pass: `fz_p_nest_eq`'s own `ensures` (`\\forall k; ...
    at(m, k) == at(n, k)`) used to crash `pred()` outright
    (`NotImplementedError: seq position holds non-variable {'op': 'at',
    ...}`) because the old code called `seq_var` on the `at(...)` operand
    directly. Confirms the fix by checking the exception it now raises is
    NOT that one -- the `ensures` itself renders, the task still abstains
    for a different, later reason (the next test)."""
    try:
        _lower("fz_p_nest_eq")()
    except NotImplementedError as ex:
        assert "seq position holds non-variable" not in str(ex), str(ex)
    else:
        raise AssertionError("fz_p_nest_eq lowered with no exception at all")


@test
def nest_eq_still_abstains_on_the_executable_equality():
    """The crash moved, the outcome did not: `fz_p_nest_eq`'s BODY computes
    `r := (m == n)` in EXECUTABLE position, `cexpr`'s own pre-existing named
    refusal (unchanged by this pass -- no C loop is built)."""
    try:
        _lower("fz_p_nest_eq")()
    except NotImplementedError as ex:
        assert "executable position" in str(ex), str(ex)
        assert "no C VALUE rendering" in str(ex), str(ex)
    else:
        raise AssertionError("fz_p_nest_eq: expected an executable-equality "
                              "NotImplementedError, none raised")


@test
def the_other_five_seq_cells_are_unmoved():
    """The five cells this pass does not touch each still raise their own
    pre-existing exact message (byte-identical to FRAMAC-SEQ2/3's own
    notes): a fresh design (a second CAPACITY dimension, nested locals, an
    executable length bound, a pair-with-seq encoding), never a
    rendering-site patch this pass's four owned sites could close alone."""
    expected_substrings = {
        "fz_p_nest_empty": "nested seq (seq<seq>) RETURN: building a "
                            "fresh row set has no encoding",
        "fz_p_str_splitempty": "nested seq (seq<seq>) RETURN: building a "
                                "fresh row set has no encoding",
        "fz_p_str_tab": "nested seq (seq<seq>) local variables are not "
                        "supported",
        "fz_p_str_lowernonletter": "length is not statically determinable",
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


@test
def committed_tasks_are_unaffected():
    """The 34 committed tasks under t/tasks: none declares a nested seq at
    all, so none reaches `pred()`'s seq `==` branch on a row-extracted
    (non-bare-variable) operand -- this pass's edit is a no-op for every
    one of them, confirmed by lowering each and counting exactly the same
    31 lower cleanly / 3 abstain split t/AGREEMENT.md's own framac column
    (31 `verified/refuted`, 3 `abstain/abstain`: count_vowels, split_join,
    swap_rows) already records."""
    taskdir = HERE / "tasks"
    names = sorted(p.stem for p in taskdir.glob("*.t"))
    assert len(names) == 34, len(names)
    lowered, abstained = 0, 0
    for name in names:
        task = tasks_io.load_task(taskdir / f"{name}.t")
        try:
            lower_framac.lower(task, task["body"])
        except NotImplementedError:
            abstained += 1
        else:
            lowered += 1
    assert (lowered, abstained) == (31, 3), (lowered, abstained)


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
