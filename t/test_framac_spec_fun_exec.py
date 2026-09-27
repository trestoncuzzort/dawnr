"""Plain-python tests for framac-closure (2026-09-14): a spec_fun predicate
called from EXECUTABLE position (an `if`/assign inside a task's own loop,
not a `requires`/`ensures`/invariant) is lowered to a call on a mirrored C
function (`_spec_fun_c`, lower_framac.py) instead of an unconditional
abstain, for the all-int-parameter case (self-recursive ones too since
2026-09-26, with the spec_fun's `decreases` on the mirror); a seq-typed
spec_fun parameter, or a callee that is itself ineligible, still abstains
with the ORIGINAL, unchanged message. See lower_framac.py's own
module docstring, "FRAMAC-CLOSURE, 2026-09-14" section, for the full
argument and the sweep rows (dafny-synthesis 412/426/436/554/629) this
closes a layer of.

Run as: cd <repo>/t && python3 test_framac_spec_fun_exec.py
"""
from __future__ import annotations

import sys
import traceback

import lower_framac as lf

FAILURES = []


def check(name, cond, detail=""):
    if not cond:
        FAILURES.append(f"{name}: {detail}")


def _int_task_calling_isEven():
    task = {
        "name": "pickEvenOrOne",
        "params": [{"name": "n", "type": "int"}],
        "returns": [{"name": "r", "type": "int"}],
        "requires": [],
        "ensures": [
            {"op": "implies", "args": [
                {"call": {"fun": "isEven", "args": [{"var": "n"}]}},
                {"op": "==", "args": [{"var": "r"}, {"int": 1}]}]}
        ],
        "spec_funs": [
            {"name": "isEven", "params": [{"name": "n", "type": "int"}],
             "result": "bool", "decreases": {"int": 0},
             "body": {"op": "==", "args": [
                 {"op": "mod", "args": [{"var": "n"}, {"int": 2}]},
                 {"int": 0}]}}
        ],
    }
    body = [
        {"if": {
            "cond": {"call": {"fun": "isEven", "args": [{"var": "n"}]}},
            "then": [{"assign": ["r", {"int": 1}]}],
            "else": [{"assign": ["r", {"int": 0}]}],
        }}
    ]
    return task, body


def test_eligible_spec_fun_lowers_and_calls_mirror():
    task, body = _int_task_calling_isEven()
    c_src = lf.lower(task, body)
    check("mirror function emitted", "int isEven_c(int n)" in c_src, c_src)
    check("mirror contract states equality with the logic function",
          "<==> isEven(n)" in c_src, c_src)
    check("call site dispatches to the mirror, not the logic function",
          "isEven_c(n)" in c_src, c_src)
    # The ACSL side must stay on the plain logic function, unchanged: the
    # ensures clause names `isEven` (not `isEven_c`) exactly as
    # spec_fun_acsl already renders it.
    check("ACSL ensures still names the logic function",
          "isEven(n) == \\true" in c_src or "isEven(n)) ==>" in c_src, c_src)


def test_seq_param_spec_fun_still_abstains_with_original_message():
    task = {
        "name": "anyEven",
        "params": [{"name": "s", "type": "seq"}],
        "returns": [{"name": "r", "type": "bool"}],
        "requires": [], "ensures": [],
        "spec_funs": [
            {"name": "hasEven", "params": [{"name": "s", "type": "seq"}],
             "result": "bool", "decreases": {"int": 0},
             "body": {"bool": True}}
        ],
    }
    body = [
        {"assign": ["r",
                    {"call": {"fun": "hasEven", "args": [{"var": "s"}]}}]}
    ]
    try:
        lf.lower(task, body)
        check("seq-param spec_fun call raises", False,
              "expected NotImplementedError, lowering succeeded instead")
    except NotImplementedError as e:
        check("original abstain message unchanged",
              str(e) == "spec_fun call in executable position (ACSL logic "
                        "functions are not executable)", str(e))


def _fact_task():
    return {
        "name": "callsFact",
        "params": [{"name": "n", "type": "int"}],
        "returns": [{"name": "r", "type": "int"}],
        "requires": [], "ensures": [],
        "spec_funs": [
            {"name": "fact", "params": [{"name": "n", "type": "int"}],
             "result": "int", "decreases": {"var": "n"},
             "body": {"ite": {
                 "cond": {"op": "<=", "args": [{"var": "n"}, {"int": 0}]},
                 "then": {"int": 1},
                 "else": {"op": "*", "args": [
                     {"var": "n"},
                     {"call": {"fun": "fact", "args": [
                         {"op": "-", "args": [{"var": "n"}, {"int": 1}]}]}}]}}}}
        ],
    }


def test_self_recursive_spec_fun_lowers_to_a_recursive_mirror_with_decreases():
    """UPDATED 2026-09-26 (framac track, RECURSIVE MIRRORS in
    lower_framac.py): a self-recursive spec_fun with a `decreases` now gets
    a recursive C mirror carrying that measure, so WP checks the variant at
    the recursive call; it used to abstain. The kernel-level checks (the
    mirror verifies, a non-decreasing mirror and a wrong caller do not) are
    in test_framac_mirror.py."""
    task = _fact_task()
    body = [
        {"assign": ["r", {"call": {"fun": "fact", "args": [{"var": "n"}]}}]}
    ]
    c_src = lf.lower(task, body)
    check("recursive mirror emitted", "int fact_c(int n)" in c_src, c_src)
    check("mirror recurses through itself", "fact_c((n - 1))" in c_src, c_src)
    check("mirror carries the spec_fun's decreases", "decreases n;" in c_src,
          c_src)
    check("decreases precedes assigns (ACSL clause order)",
          c_src.index("decreases n;") < c_src.index("assigns \\nothing;"),
          c_src)
    check("call site dispatches to the mirror", "r = fact_c(n);" in c_src,
          c_src)


def test_uncalled_mirror_is_not_emitted():
    """2026-09-26: a spec_fun used only in the spec gets no C mirror (an
    uncalled mirror's own contract goal was the one unproved goal of
    da0069/da0641/da0658)."""
    task = _fact_task()
    task["ensures"] = [{"op": "==", "args": [
        {"var": "r"}, {"call": {"fun": "fact", "args": [{"int": 0}]}}]}]
    c_src = lf.lower(task, [{"assign": ["r", {"int": 1}]}])
    check("no mirror when no statement calls it", "fact_c" not in c_src, c_src)


def test_caller_of_ineligible_spec_fun_still_abstains():
    """A spec_fun whose callee is not an EARLIER eligible spec_fun (here
    declared after it) is itself ineligible, so its call site abstains with
    the original message rather than emitting a mirror that calls a C
    function not yet declared (and no mutual recursion can arise)."""
    task = {
        "name": "callsWrap",
        "params": [{"name": "n", "type": "int"}],
        "returns": [{"name": "r", "type": "bool"}],
        "requires": [], "ensures": [],
        "spec_funs": [
            {"name": "wrap", "params": [{"name": "n", "type": "int"}],
             "result": "bool", "decreases": {"int": 0},
             "body": {"call": {"fun": "isPos", "args": [{"var": "n"}]}}},
            {"name": "isPos", "params": [{"name": "m", "type": "int"}],
             "result": "bool", "decreases": {"int": 0},
             "body": {"op": ">", "args": [{"var": "m"}, {"int": 0}]}},
        ],
    }
    body = [{"assign": ["r", {"call": {"fun": "wrap", "args": [{"var": "n"}]}}]}]
    try:
        lf.lower(task, body)
        check("ineligible-callee call raises", False, "lowering succeeded")
    except NotImplementedError as e:
        check("original abstain message unchanged",
              str(e) == "spec_fun call in executable position (ACSL logic "
                        "functions are not executable)", str(e))


def main() -> int:
    tests = [test_eligible_spec_fun_lowers_and_calls_mirror,
             test_seq_param_spec_fun_still_abstains_with_original_message,
             test_self_recursive_spec_fun_lowers_to_a_recursive_mirror_with_decreases,
             test_uncalled_mirror_is_not_emitted,
             test_caller_of_ineligible_spec_fun_still_abstains]
    ran = 0
    for t in tests:
        ran += 1
        try:
            t()
        except Exception:                          # noqa: BLE001
            FAILURES.append(f"{t.__name__}: raised\n{traceback.format_exc()}")
    print(f"{ran} tests, {len(FAILURES)} failures")
    for f in FAILURES:
        print(f"FAIL: {f}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
