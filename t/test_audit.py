#!/usr/bin/env python3
"""test_audit.py: t/audit.py (NORTH-STAR.md target 3, D8), the specification audit. Every mutant lands in one class;
a weak spec admits a survivor with a witness, the same routine under a strong spec admits none, a mutant that loops
forever is classed apart from the spec, and the table and the CLI agree. Standard library only, no kernel runs."""
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
import surface  # noqa: E402

WEAK = """t 1
task next_up(x: int) returns (r: int)
  requires x >= 0
  ensures r > x
{
  r := x + 1;
}
"""
STRONG = WEAK.replace("ensures r > x", "ensures r == x + 1")
LOOP = """t 1
task count_to(n: int) returns (r: int)
  requires n >= 0
  ensures r == n
{
  r := 0;
  while r < n
    invariant 0 <= r and r <= n
    decreases n - r
  {
    r := r + 1;
  }
}
"""


def _classes_add_up(res: dict) -> bool:
    return res["mutants"] == res["killed"] + res["same"] + res["diverges"] + len(res["survivors"])


def test_weak_spec_admits_a_survivor():
    res = audit.classify(surface.parse(WEAK))
    assert res["status"] == "ok" and _classes_add_up(res), res
    assert res["survivors"], f"r > x admits x + 2: {res}"
    w = res["survivors"][0]["witness"]
    assert w["_kind"] == "value" and w.get("_ens") is not True, w


def test_strong_spec_kills_every_changing_mutant():
    res = audit.classify(surface.parse(STRONG))
    assert res["status"] == "ok" and _classes_add_up(res), res
    assert not res["survivors"] and res["killed"] >= 1, res


def test_a_mutant_that_never_ends_is_not_a_spec_finding():
    res = audit.classify(surface.parse(LOOP))
    assert res["status"] == "ok" and _classes_add_up(res), res
    assert res["diverges"] >= 1 and not res["survivors"], res


def test_a_real_body_that_breaks_its_spec_is_not_audited():
    res = audit.classify(surface.parse(WEAK.replace("r := x + 1;", "r := x;")))
    assert res["status"] == "real-violates-spec", res


def test_file_table_and_cli():
    with tempfile.TemporaryDirectory() as d:
        for name, text in (("weak.t", WEAK), ("strong.t", STRONG)):
            Path(d, name).write_text(text, encoding="utf-8")
        rows = [audit.audit_file(str(Path(d, n))) for n in ("strong.t", "weak.t")]
        assert all(r["status"] == "ok" for r in rows), rows
        weak = rows[1]
        s = weak["survivors"][0]
        assert "body" not in s and s["change"].startswith("`r := x + 1;` -> ") and " -> real " in s["witness"], s
        text = audit.table(rows, None)
        assert "tasks whose spec admits a survivor: 1 of 2" in text, text
        out = io.StringIO()
        with redirect_stdout(out):
            rc = cli.main(["audit", d, "--json", "--table", str(Path(d, "AUDIT.md"))])
        lines = [json.loads(x) for x in out.getvalue().splitlines()]
        assert rc == 0 and [r["name"] for r in lines] == ["next_up", "next_up"], lines
        assert Path(d, "AUDIT.md").read_text(encoding="utf-8") == audit.table(lines, None)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"{name}: ok")
