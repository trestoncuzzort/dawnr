#!/usr/bin/env python3
"""test_spark_seq_carry.py: a seq local that a loop does not assign is carried into the loop function's precondition
by the qualified `Seqs."="`, never the infix "=" (2026-10-06, PREDICT T13's read). The infix equality of the
instantiated private Sequence type is not directly visible without a use clause, and gnatprove refused the whole file
("operator for private type Sequence ... is not directly visible") on AlgoVeri's string_search_naive and
solve_longest_common_subsequence. Text-level check, no kernel run."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lower_spark  # noqa: E402
import surface  # noqa: E402

SRC = """t 1
task count_up(s: seq) returns (r: int)
  ensures r >= 0
{
  var u: seq := s;
  r := 0;
  var i: int := 0;
  while i < len(u)
    invariant 0 <= i and i <= len(u)
    invariant r >= 0
    decreases len(u) - i
  {
    r := r + 1;
    i := i + 1;
  }
}
"""


def test_a_carried_seq_local_uses_the_qualified_equality():
    task = surface.parse(SRC)
    out = lower_spark.lower(task, task["body"])
    assert 'Seqs."=" (U, (S))' in out, "the carried seq local is compared by Seqs.\"=\""
    assert "U = (S)" not in out


if __name__ == "__main__":
    test_a_carried_seq_local_uses_the_qualified_equality()
    print("ok")
