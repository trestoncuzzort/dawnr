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


# Named by the GPT-6 Astra review of 2026-10-13 and reproduced here before the fix: two task files whose stems
# sanitize to the same name wrote the same kernel source path, so a parallel audit with a shared --out could read
# the other task's verdict.

def test_kernel_source_paths_do_not_collide(tmp_path):
    from unittest.mock import patch
    text = "t 1\ntask next_up(x: int) returns (r: int)\n  requires x >= 0\n  ensures r > x\n{\n  r := x + 1;\n}\n"
    paths = []

    def verdict(task, body, kernel, path):
        paths.append(path)
        return "abstain"
    with patch.object(audit, "_kernel_verdict", side_effect=verdict):
        for name in ("a-b.t", "a_b.t"):
            (tmp_path / name).write_text(text, encoding="utf-8")
            audit.audit_file(str(tmp_path / name), kernel="dafny", out_dir=str(tmp_path / "out"))
    assert len(paths) == 2 and len(set(paths)) == 2, paths


# Two more from the same review: a capped search is disclosed as incomplete; a lowering refusal keeps the construct name.


def test_table_discloses_capped_search():
    import audit

    result = {
        'name': 'f', 'status': 'ok', 'mutants': 1,
        'same': 0, 'killed': 1, 'diverges': 0,
        'survivors': [], 'ill_formed': 0,
        'capped': True, 'proved_survivors': 0,
    }
    report = audit.table([result], None).lower()
    assert any(word in report for word in ('capped', 'truncat', 'incomplete', 'partial')), report


def test_lowering_refusal_preserves_construct_name():
    from pathlib import Path
    from types import SimpleNamespace
    from unittest.mock import patch
    import audit

    def lower(task, body):
        raise NotImplementedError('unsupported construct: choice_expression')

    with patch.dict(audit.tlib._LOWER_MOD, {'audit_test': ('audit_test_lower', 'txt')}), patch.object(audit.importlib, 'import_module', return_value=SimpleNamespace(lower=lower)):
        result = audit._kernel_verdict({'body': []}, [], 'audit_test', Path('unused.txt'))
    assert 'choice_expression' in str(result), result
