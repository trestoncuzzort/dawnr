"""Plain-python tests for framac-closure (2026-09-14): a spec_fun predicate
called from EXECUTABLE position (an `if`/assign inside a task's own loop,
not a `requires`/`ensures`/invariant) is lowered to a call on a mirrored C
function (`_spec_fun_c`, lower_framac.py) instead of an unconditional
abstain, for the non-recursive, all-int-parameter case; every other case
(a seq-typed spec_fun parameter, or a self-recursive spec_fun) still
abstains with the ORIGINAL, unchanged message. See lower_framac.py's own
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


def test_self_recursive_spec_fun_still_abstains_with_original_message():
    task = {
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
    body = [
        {"assign": ["r", {"call": {"fun": "fact", "args": [{"var": "n"}]}}]}
    ]
    try:
        lf.lower(task, body)
        check("self-recursive spec_fun call raises", False,
              "expected NotImplementedError, lowering succeeded instead")
    except NotImplementedError as e:
        check("original abstain message unchanged",
              str(e) == "spec_fun call in executable position (ACSL logic "
                        "functions are not executable)", str(e))


def main() -> int:
    tests = [test_eligible_spec_fun_lowers_and_calls_mirror,
             test_seq_param_spec_fun_still_abstains_with_original_message,
             test_self_recursive_spec_fun_still_abstains_with_original_message]
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
