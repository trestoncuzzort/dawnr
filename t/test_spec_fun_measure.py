"""A spec_fun's decreases is the measure of a self-recursive definition and nothing else (2026-10-13): a definition
that never calls itself parses, prints, checks and lowers without one, and one that calls itself without one is
refused by name. Dafny asks a measure of possibly recursive functions only (dafny.org/latest/OnlineTutorial/Termination)."""
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import surface  # noqa: E402
import tlib  # noqa: E402

PLAIN = """t 1
task total(x: int) returns (r: int)
  requires x >= 0
  ensures r >= 0
spec fun g(n: int): int
= if n < 0 then 0 else n
{
  r := g(x)
}
"""
RECURSIVE = PLAIN.replace("= if n < 0 then 0 else n", "  decreases n\n= if n <= 0 then 0 else g(n - 1)")


def test_a_definition_that_never_calls_itself_needs_no_measure(tmp_path):
    task = surface.parse(PLAIN)
    assert "decreases" not in task["spec_funs"][0]
    printed = surface.print_task(task)
    assert "decreases" not in printed and "spec fun g(n: int): int" in printed
    again = surface.parse(printed)
    assert again["spec_funs"][0]["body"] == task["spec_funs"][0]["body"]
    path = tmp_path / "plain.t"
    path.write_text(PLAIN, encoding="utf-8")
    assert surface.check_file(str(path)) == []


def test_a_measure_is_kept_when_written():
    task = surface.parse(RECURSIVE)
    assert task["spec_funs"][0]["decreases"] == {"var": "n"} or "var" in task["spec_funs"][0]["decreases"]
    assert "  decreases n" in surface.print_task(task)


def test_a_self_calling_definition_without_a_measure_is_refused_by_name(tmp_path):
    path = tmp_path / "rec.t"
    path.write_text(RECURSIVE.replace("  decreases n\n", ""), encoding="utf-8")
    errs = surface.check_file(str(path))
    assert any("spec-fun-decreases-selfcall" in (getattr(e, "rule", "") or str(e)) for e in errs), errs


def test_every_lowering_takes_a_measureless_definition():
    task = surface.parse(PLAIN)
    for kernel, (lmod, _suffix) in sorted(tlib._LOWER_MOD.items()):
        src = importlib.import_module(lmod).lower(task, task["body"])
        assert "g" in src, kernel
