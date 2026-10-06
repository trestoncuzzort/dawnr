#!/usr/bin/env python3
"""test_verus_nested_index_trigger.py: PREDICT T15 (2026-10-06). A quantifier whose bound variable is read only inside a
nested quantifier, in its bounds or under a base that is not a plain variable, gets an explicit trigger on that
index term. Verus does not look inside a nested quantifier for the outer one's trigger and refused outright ("Could
not automatically infer triggers"): AlgoVeri's matrix_multiplication (`A[i]` only in `A[i].len()` and `A[i][j]`),
kmp (`fail[q]` only in an inner bound) and merge_sort (`(m + seq![e])[i]`). Each minimal program below verifies in
Verus with the trigger (measured 2026-10-06, 2 verified, 0 errors each). Text-level checks, no kernel runs."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lower_verus  # noqa: E402
import surface  # noqa: E402

CASES = {
    "an index read only in an inner bound and an inner body": ("""t 1
task rows_ok(A: seq<seq>) returns (r: int)
  requires forall i in [0, len(A)) . forall j in [0, len(A[i])) . A[i][j] >= 0
  ensures r == len(A)
{
  r := len(A);
}
""", "(forall|i: int| #![trigger A[i]] "),
    "an index read only in an inner lower bound": ("""t 1
task lo_ok(f: seq) returns (r: int)
  requires forall q in [0, len(f)) . forall k in [f[q], q) . k >= 0
  ensures r == len(f)
{
  r := len(f);
}
""", "(forall|q: int| #![trigger f[q]] "),
    "an index into an expression": ("""t 1
task app_sorted(m: seq, e: int) returns (r: int)
  requires forall i in [0, len(m + [e])) . forall j in [i + 1, len(m + [e])) . (m + [e])[i] <= (m + [e])[j]
  ensures r == e
{
  r := e;
}
""", "(forall|i: int| #![trigger (m + seq![e])[i]] "),
}


def test_outer_quantifier_gets_the_nested_index_trigger():
    for what, (src, want) in CASES.items():
        task = surface.parse(src)
        out = lower_verus.lower(task, task["body"])
        assert want in out, f"{what}: {want!r} not in the lowering"


def test_a_term_with_an_inner_variable_is_never_the_trigger():
    task = surface.parse(CASES["an index read only in an inner bound and an inner body"][0])
    out = lower_verus.lower(task, task["body"])
    assert "#![trigger A[i][j]]" not in out


if __name__ == "__main__":
    test_outer_quantifier_gets_the_nested_index_trigger()
    test_a_term_with_an_inner_variable_is_never_the_trigger()
    print("ok")
