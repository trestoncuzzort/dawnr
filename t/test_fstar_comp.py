#!/usr/bin/env python3
"""test_fstar_comp.py: comprehensions in the F* lowering (PREDICT T16, 2026-10-06; SPEC.md "Comprehensions (v1)").
Text-level checks only, no kernel runs. Each map shape is one function `t_compK` in Dafny's prefix form, built by
`Seq.init` with one call of `Seq.init_index`, its postcondition stating the length and every element. The body's
definedness is its precondition: element-free conjuncts once, as `t_n > 0 ==> ...`, the rest as a quantifier
triggered on the element (`Seq.index t_s t_di`, or `t_ix t_di` over a range). A filter is a prefix-form recursion
(PREDICT T45). A comprehension inside a
spec_fun, method or lemma, refuse by name."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lower_framac  # noqa: E402
import lower_fstar  # noqa: E402
import surface  # noqa: E402
import tasks_io  # noqa: E402


def load(name: str) -> dict:
    return tasks_io.load_task(str(HERE / "tasks" / f"{name}.t"))


def fstar(name: str) -> str:
    task = load(name)
    return lower_fstar.lower(task, task["body"])


def refusal(task: dict, mod=lower_fstar) -> str:
    try:
        mod.lower(task, task["body"])
    except NotImplementedError as e:
        return str(e)
    return ""


def test_a_map_over_a_seq_is_seq_init_with_its_element_lemma():
    src = fstar("doubled")
    assert "let t_comp1 (t_s:Seq.seq int) (t_n:nat)" in src
    assert "Seq.init_index t_n t_f;\n  Seq.init t_n t_f" in src
    assert "Seq.index t_r t_i == (2 * (Seq.index t_s t_i))" in src
    assert "= (t_comp1 s (Seq.length s))" in src
    assert "t_ix" not in src, "a total body over a seq needs no precondition and no t_ix"


def test_a_range_map_counts_from_its_start():
    src = fstar("squares")
    assert "let t_comp1 (t_a:int) (t_n:int)" in src
    assert "Seq.length t_r == (if t_n < 0 then 0 else t_n)" in src
    assert "= (t_comp1 0 (n - 0))" in src


def test_partial_body_owes_definedness_per_element_and_once():
    src = fstar("diffs")
    assert "let t_ix (t_i:int) : int = t_i" in src
    assert "(forall (t_di:nat).{:pattern (t_ix t_di)} t_di < t_n ==>" in src
    src = fstar("odd_positions")
    assert "(t_n > 0 ==> ((1 <= (Seq.length s))" in src, "the slice's bound is stated once, outside the quantifier"


def test_filter():
    # PREDICT T45: Dafny's filter shape, a prefix-form recursion keeping the last element when the condition holds
    src = fstar("evens")
    assert "let rec t_comp1 (t_s:Seq.seq int) (t_n:nat)" in src and "(decreases t_n)" in src
    assert "(ensures (fun t_r -> Seq.length t_r <= t_n /\\ (forall (t_i:nat).{:pattern (Seq.index t_r t_i)}" in src
    assert ("if (((Seq.index t_s (t_n - 1)) % 2) = 0) then Seq.append t_p (Seq.create 1 (Seq.index t_s (t_n - 1))) "
            "else t_p") in src
    src = fstar("count_evens_skip")
    assert "(c == (Seq.length (t_comp1 s i)))" in src, "a count over a growing prefix, the step left to the definition"


def test_refusals_by_name():
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


def test_framac_refuses_a_filter_by_name():
    # SPARK and Frama-C carry maps since PREDICT T18, T19 (test_spark_comp.py, test_framac_comp.py)
    assert "filtered comprehension is not lowered yet" in refusal(load("evens"), lower_framac)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
