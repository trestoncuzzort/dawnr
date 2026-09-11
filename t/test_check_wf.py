#!/usr/bin/env python3
r"""test_check_wf.py: standard-library tests for check_wf.py.

Added 2026-09-11 (ROADMAP 14.3, "The checker as a module"). Run as
`python3 t/test_check_wf.py` from anywhere (it inserts its own directory
onto sys.path); exits nonzero on any failure, prints "OK" and the number
of checks run on success.

Three things are checked:

1. `test_committed_tasks_well_formed`: every task committed under
   t/tasks/*.t passes `check_wf(task) == []`. This is the module's own
   regression gate: any task the corpus already agreed was well-formed
   must still be well-formed after the move.
2. `test_malformed_examples`: one hand-built malformed task per rule, for
   eight rules covering the six most common construct classes a
   generated task's `check_wf` error touches (unbound names, polymorphic
   `==`, arithmetic typing, comparison typing, declared types, and
   quantifier scope) plus two more (a missing loop `decreases`, a
   misnamed early-exit return) -- each example's `check_wf` output must
   contain an error string naming that rule's RULES text.
3. `test_no_cycle`: check_wf.py's own top-level imports never name
   fuzz_lower, so surface.py and the command can import check_wf without
   pulling in the fuzzer (the module boundary ROADMAP 14.3 asks for).

Measured 2026-09-11 with `python3 -c 'import fuzz_lower as f; \
c=f.build_corpus(400,1); from collections import Counter; import re; \
cnt=Counter(); [cnt.update(re.findall(r"\[SPEC: ([^]]+)\]", e)) for t in c \
for e in f.check_wf(t)]; print(cnt.most_common(10))'` (seed 1, 400 draws):
the generated corpus's own well-formedness errors are rare (`check_wf`
mostly rejects candidates before they are added to the corpus, per
fuzz_lower.py's build_corpus), so on this run only 4 distinct rules fired
at all, each 1-3 times: eq-types (3), arith-int (2), op-unknown (2),
assign-type (1) and return-unreachable (1). The eight rules below are
chosen for construct diversity, not corpus frequency; eq-types and
arith-int, the two rules the corpus run above did trigger most, are
covered.
"""

from __future__ import annotations

import ast
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_wf  # noqa: E402


def _v0_base():
    """A minimal well-formed v0 task, to be mutated per test."""
    return {
        "t": 0,
        "name": "abs2",
        "params": [{"name": "x", "type": "int"}],
        "returns": [{"name": "r", "type": "int"}],
        "requires": [],
        "ensures": [{"op": ">=", "args": [{"var": "r"}, {"int": 0}]}],
        "body": [{"assign": ["r", {"var": "x"}]}],
    }


def _v1_loop_base():
    """A minimal well-formed v1 task with a loop, to be mutated."""
    return {
        "t": 1,
        "name": "count_up",
        "params": [{"name": "n", "type": "int"}],
        "returns": [{"name": "r", "type": "int"}],
        "requires": [{"op": ">=", "args": [{"var": "n"}, {"int": 0}]}],
        "ensures": [{"op": "==", "args": [{"var": "r"}, {"var": "n"}]}],
        "body": [
            {"var": {"name": "i", "type": "int", "init": {"int": 0}}},
            {"assign": ["r", {"int": 0}]},
            {"while": {
                "cond": {"op": "<", "args": [{"var": "i"}, {"var": "n"}]},
                "invariants": [{"op": "<=", "args": [{"var": "i"}, {"var": "n"}]}],
                "decreases": {"op": "-", "args": [{"var": "n"}, {"var": "i"}]},
                "body": [
                    {"assign": ["r", {"op": "+", "args": [{"var": "r"}, {"int": 1}]}]},
                    {"assign": ["i", {"op": "+", "args": [{"var": "i"}, {"int": 1}]}]},
                ],
            }},
        ],
    }


def _errs_text(task):
    return check_wf.check_wf(task)


def test_committed_tasks_well_formed():
    n = 0
    tasks_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks")
    import tasks_io
    for path in sorted(glob.glob(os.path.join(tasks_dir, "*.t"))):
        task = tasks_io.load_task(path)
        errs = check_wf.check_wf(task)
        assert errs == [], f"{os.path.basename(path)}: check_wf found {errs}"
        n += 1
    assert n > 0, f"no tasks found under {tasks_dir}"
    return n


def test_malformed_examples():
    cases = []

    # 1. unbound: an ensures clause reads a name never bound.
    t = _v0_base()
    t["ensures"] = [{"op": ">=", "args": [{"var": "zzz"}, {"int": 0}]}]
    cases.append(("unbound", t))

    # 2. eq-types: == across an int and a seq.
    t = _v0_base()
    t["params"] = [{"name": "x", "type": "int"}]
    t["ensures"] = [{"op": "==", "args": [{"var": "x"}, {"op": "seq", "args": []}]}]
    cases.append(("eq-types", t))

    # 3. arith-int: + over a bool operand (v1, so bool exists as a type).
    t = _v1_loop_base()
    t["ensures"] = [{"op": "==", "args": [
        {"var": "r"},
        {"op": "+", "args": [{"bool": True}, {"int": 1}]}]}]
    cases.append(("arith-int", t))

    # 4. cmp-int: < between two bools.
    t = _v1_loop_base()
    t["ensures"] = [{"op": "<", "args": [{"bool": True}, {"bool": False}]}]
    cases.append(("cmp-int", t))

    # 5. valid-type: a param declares an unknown type.
    t = _v0_base()
    t["params"] = [{"name": "x", "type": "float"}]
    cases.append(("valid-type", t))

    # 6. quant-shadow: a forall's bound variable shadows a param.
    t = _v1_loop_base()
    t["ensures"] = [{"forall": {"var": "n", "lo": {"int": 0}, "hi": {"var": "n"},
                                "body": {"op": ">=", "args": [{"var": "n"}, {"int": 0}]}}}]
    cases.append(("quant-shadow", t))

    # 7. loop-decreases: a while with no decreases.
    t = _v1_loop_base()
    del t["body"][2]["while"]["decreases"]
    cases.append(("loop-decreases", t))

    # 8. return-name: an early exit names a variable that is not the
    # task's return.
    t = _v1_loop_base()
    t["body"].append({"var": {"name": "junk", "type": "int", "init": {"int": 0}}})
    t["body"].append({"return": ["junk", {"int": 0}]})
    cases.append(("return-name", t))

    n = 0
    for rule, task in cases:
        errs = check_wf.check_wf(task)
        assert errs, f"rule {rule!r}: expected check_wf to find an error, found none"
        rule_text = check_wf.RULES[rule]
        assert any(rule_text in e for e in errs), (
            f"rule {rule!r}: expected an error naming {rule_text!r}, got {errs}")
        n += 1
    return n


def test_no_cycle():
    """check_wf.py imports nothing from fuzz_lower, so it has no cycle
    with the module that imports it."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "check_wf.py")
    with open(path) as f:
        tree = ast.parse(f.read(), filename=path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "fuzz_lower", (
                    "check_wf.py imports fuzz_lower: that is the cycle "
                    "ROADMAP 14.3 asks this module not to have")
        elif isinstance(node, ast.ImportFrom):
            assert node.module != "fuzz_lower", (
                "check_wf.py imports from fuzz_lower: that is the cycle "
                "ROADMAP 14.3 asks this module not to have")
    return 1


def main():
    checks = [test_committed_tasks_well_formed, test_malformed_examples, test_no_cycle]
    total = 0
    for check in checks:
        n = check()
        print(f"{check.__name__}: ok ({n})")
        total += n
    print(f"OK: {total} checks across {len(checks)} tests")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"FAIL: {e}")
        sys.exit(1)
