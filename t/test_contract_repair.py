#!/usr/bin/env python3
"""test_repair.py: t/contract_repair.py (programme R1), proved specification repair. A weak max gains the clause that names
its result; a subset-only filter gains its converse and, for its loop, the invariant that carries it; every chosen
clause holds for the real program on the whole domain; a strong spec gets nothing. Standard library only, no
kernel runs."""
from __future__ import annotations

import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import audit  # noqa: E402
import cli  # noqa: E402
import harness  # noqa: E402
import interp  # noqa: E402
import contract_repair as repair  # noqa: E402
import surface  # noqa: E402

MAX = """t 1
task max2(a: int, b: int) returns (c: int)
  ensures c >= a
  ensures c >= b
{
  if a < b {
    c := b;
  } else {
    c := a;
  }
}
"""

FILTER = """t 1
task keep_pos(s: seq) returns (r: seq)
  ensures forall k in [0, len(r)) . r[k] > 0
{
  var acc: seq := [];
  var i: int := 0;
  while i < len(s)
    invariant 0 <= i and i <= len(s)
    invariant forall k in [0, len(acc)) . acc[k] > 0
    decreases len(s) - i
  {
    if s[i] > 0 {
      acc := acc + [s[i]];
    }
    i := i + 1;
  }
  r := acc;
}
"""


def _texts(res):
    return [repair._show(c) for c in res["clauses"]]


def test_a_weak_max_gains_the_clause_naming_its_result():
    res = repair.repair_task(surface.parse(MAX))
    assert res["before"] >= 1 and res["after"] == 0, res
    assert "c == a or c == b" in _texts(res), _texts(res)


def test_every_chosen_clause_holds_for_the_real_program():
    task = surface.parse(FILTER)
    res = repair.repair_task(task)
    assert res["before"] >= 1 and res["after"] == 0, res
    harness._set_ctx(task)
    ref = interp.Reference(task)
    for c in res["clauses"]:
        assert all(repair._holds(ref, c, env0, real) for env0, real in ref.points), repair._show(c)
    assert any("==>" in t and "exists" in t for t in _texts(res)), _texts(res)


def test_the_loop_gains_the_invariant_that_carries_the_converse():
    task = surface.parse(FILTER)
    res = repair.repair_task(task)
    stronger, added = repair.strengthen_loops(res["task"], res["clauses"])
    shown = [repair._show(c) for _k, c in added]
    assert any("[0, i)" in t and "acc[" in t for t in shown), shown
    assert all("acc" in t or "i" in t for t in shown), shown
    assert audit.classify(stronger)["survivors"] == [], "the stronger task still kills every mutant"


def test_a_strong_spec_gets_nothing():
    strong = MAX.replace("  ensures c >= b\n", "  ensures c >= b\n  ensures c == a or c == b\n")
    res = repair.repair_task(surface.parse(strong))
    assert res["before"] == 0 and res["clauses"] == [], res


def test_a_program_that_ignores_its_inputs_is_not_repaired_to():
    blind = "t 1\ntask k(x: int) returns (r: int)\n  ensures r >= 0\n{\n  r := 0;\n}\n"
    res = repair.repair_task(surface.parse(blind))
    assert res["status"].startswith("refused") and res["clauses"] == [], res


def test_cli_writes_the_repaired_task():
    with tempfile.TemporaryDirectory() as d:
        Path(d, "max2.t").write_text(MAX, encoding="utf-8")
        out = io.StringIO()
        with redirect_stdout(out):
            rc = cli.main(["repair", str(Path(d, "max2.t")), "--json", "--write", str(Path(d, "fixed"))])
        rows = [json.loads(x) for x in out.getvalue().splitlines()]
        assert rc == 0 and rows[0]["after"] == 0, rows
        fixed = json.loads(Path(d, "fixed", "max2.json").read_text())
        assert len(fixed["ensures"]) == 3, fixed["ensures"]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
