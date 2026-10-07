#!/usr/bin/env python3
"""test_spark_comp.py: comprehensions in the SPARK lowering (PREDICT T18, 2026-10-07; SPEC.md "Comprehensions (v1)").
Text-level checks only, no kernel runs. Each map shape is one recursive expression function `T_CompK` in T_Slice's
own shape: a Pre (the source's bound, the count nonnegative, the body's definedness), a Post stating the length and
every element over T_Range, a Subprogram_Variant, and `Seqs.Add` of the last element. Over a range the index is
written through the identity `T_Ix` and the count is clamped at the call site; the recursion is guarded by
`R_Has (T_Range'(0, T_N), T_N - 1)`, the Has_Element term through which a T_Range quantifier is instantiated
(measured on diffs: without it, the Pre's instance at T_N - 1 was out of reach at five times the step budget). A
filter, and a comprehension inside a spec_fun, method or lemma, refuse by name."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lower_spark  # noqa: E402
import surface  # noqa: E402
import tasks_io  # noqa: E402


def load(name: str) -> dict:
    return tasks_io.load_task(str(HERE / "tasks" / f"{name}.t"))


def spark(name: str) -> str:
    task = load(name)
    return lower_spark.lower(task, task["body"])


def refusal(task: dict) -> str:
    try:
        lower_spark.lower(task, task["body"])
    except NotImplementedError as e:
        return str(e)
    return ""


def test_a_map_over_a_seq_is_a_recursive_expression_function():
    src = spark("doubled")
    assert "function T_Comp1 (T_S : Seq; T_N : Big_Integer) return Seq" in src
    assert "Subprogram_Variant => (Decreases => T_N)" in src
    assert "Seqs.Add (T_Comp1 (T_S, T_N - Big_Integer'(1))" in src
    assert "(T_Comp1 (S, Len (S)))" in src
    assert "T_Ix" not in src


def test_a_range_map_clamps_its_count_and_indexes_through_t_ix():
    src = spark("squares")
    assert "function T_Ix (K : Big_Integer) return Big_Integer is (K);" in src
    assert "(T_A + T_Ix (T_K))" in src
    assert "T_Comp1 (Big_Integer'(0), (if (N - Big_Integer'(0)) < Big_Integer'(0) then Big_Integer'(0) else (N - Big_Integer'(0))))" in src


def test_the_recursion_is_guarded_by_the_has_element_term():
    src = spark("diffs")
    assert "(if not R_Has (T_Range'(Big_Integer'(0), T_N), T_N - Big_Integer'(1)) then Seqs.Empty_Sequence" in src
    assert "(for all T_K in T_Range'(Big_Integer'(0), T_N) =>" in src


def test_refusals_by_name():
    assert "filtered comprehension is not lowered yet" in refusal(load("evens"))
    assert "not lowered yet" in refusal(load("count_evens_skip"))
    task = surface.parse("""t 1
task twice_len(s: seq) returns (r: int)
  ensures r == dbl(s)
spec fun dbl(q: seq): int
  decreases 0
= len([2 * x for x in q])
{
  r := len(s);
}
""")
    assert "comprehension inside a spec_fun, method or lemma" in refusal(task)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
