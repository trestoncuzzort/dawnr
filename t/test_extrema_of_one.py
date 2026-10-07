#!/usr/bin/env python3
"""test_extrema_of_one.py: max(s)/min(s) of one argument in SPARK and F* (PREDICT T21, 2026-10-07; SPEC.md
"Reductions (v1)"). Text-level checks only, no kernel runs. Both kernels take the prefix form the comprehensions use:
the extremum of the first n elements, recursive on n, with the two facts the SPEC states (the result is a member of
the seq, and it bounds every element). SPARK states them as the Post of T_Maxs/T_Mins, the existential written the
way T_Contains writes membership, the recursion guarded by R_Has; F* states them in one SMT-patterned lemma per
function, the existential over an index, which FStar.Seq.Properties' seq_mem_k carries to `Seq.mem`. The call's
precondition (`Len (S) > 0`, F*'s `0 < n` refinement) is the definedness obligation."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lower_fstar  # noqa: E402
import lower_spark  # noqa: E402
import surface  # noqa: E402
import tasks_io  # noqa: E402

LOWEST = """t 1
task lowest(s: seq) returns (r: int)
  requires len(s) > 0
  ensures r in s
  ensures forall i in [0, len(s)) . r <= s[i]
{
  r := min(s);
}
"""


def lower(mod, task):
    return mod.lower(task, task["body"])


def test_spark_prefix_form_with_the_two_facts():
    src = lower(lower_spark, tasks_io.load_task(str(HERE / "tasks" / "largest.t")))
    assert "function T_Maxs (S : Seq; N : Big_Integer) return Big_Integer" in src
    assert "Pre  => N > Big_Integer'(0) and then N <= Len (S)" in src
    assert "(for some I in T_Range'(Big_Integer'(0), N) => Elem (S, I) = T_Maxs'Result)" in src
    assert "(T_Maxs (S, Len (S)))" in src
    assert "T_Mins (S, Len (S))" in lower(lower_spark, surface.parse(LOWEST))


def test_fstar_prefix_form_with_a_patterned_lemma():
    src = lower(lower_fstar, tasks_io.load_task(str(HERE / "tasks" / "largest.t")))
    assert "let rec t_maxs (s:Seq.seq int) (n:nat{0 < n /\\ n <= Seq.length s}) : Tot int (decreases n)" in src
    assert "[SMTPat (t_maxs s n)]" in src
    assert "(exists (k:nat). k < n /\\ Seq.index s k == t_maxs s n)" in src
    assert "(t_mins s (Seq.length s))" in lower(lower_fstar, surface.parse(LOWEST))


if __name__ == "__main__":
    test_spark_prefix_form_with_the_two_facts()
    test_fstar_prefix_form_with_a_patterned_lemma()
    print("ok")
