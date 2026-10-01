"""A test value is read at the declared parameter type (2026-10-01; arXiv:2208.08227 III-C.2)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fuzz_lower                                               # noqa: E402
import spec_experiment as se                                    # noqa: E402
import surface                                                  # noqa: E402

TOTAL_LEN = """t 1
gate loops
task f(rows: %s) returns (r: int)
  ensures r >= 0
{
  r := 0;
  var i: int := 0;
  while i < len(rows)
    invariant 0 <= i and i <= len(rows)
    invariant r >= 0
    decreases len(rows) - i
  {
    r := r + %s;
    i := i + 1;
  }
}
"""


def _task(ptype, step):
    task = surface.parse(TOTAL_LEN % (ptype, step))
    assert fuzz_lower.check_wf(task) == []
    return task


def _point(kind, val, expected):
    return {"ok": True, "fn": "f", "args": [[kind, val]], "expected": ["int", expected]}


def test_a_nested_value_passes_under_a_parameter_declared_nested():
    out = se.run_point(_task("seq<seq>", "len(rows[i])"), _point("seq-of-seq", [[1, 2], [3]], 3))
    assert out["verdict"] == "pass", out


def test_an_empty_list_is_a_value_of_the_nested_type():
    out = se.run_point(_task("seq<seq>", "len(rows[i])"), _point("seq", [], 0))
    assert out["verdict"] == "pass", out


def test_a_flat_list_of_ints_is_not_a_nested_value():
    out = se.run_point(_task("seq<seq>", "len(rows[i])"), _point("seq", [1, 2], 0))
    assert out["verdict"] == "type"


def test_a_nested_value_under_a_plain_seq_parameter_is_still_accepted():
    out = se.run_point(_task("seq", "1"), _point("seq-of-seq", [[1, 2], [3]], 2))
    assert out["verdict"] == "pass", out


def test_other_mismatches_are_still_refused():
    assert se.run_point(_task("seq", "1"), _point("int", 3, 0))["verdict"] == "type"
    assert not se.kind_fits("int", 3, "seq") and not se.kind_fits("seq", [1], "int")
    assert se.kind_fits("int", 3, "int") and se.kind_fits("seq", [1], "seq")
