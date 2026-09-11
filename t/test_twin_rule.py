"""Plain-python tests for the twin-rule (SPEC.md "The twins", 2026-09-11
paragraph, ROADMAP 13.3): a real-VERIFIED, twin-VERIFIED column is a named
REFUSAL, "decorative" or "unsound", never a bare pass-through and never
folded into fuzz_lower.py's `no_flip`.

Two things are measured here, both through the real pipeline (harness.py's
`twin_cached`/`decorative_kind` and run_par.py's `lower_and_dispatch`/
`format_table`, not a reimplementation of either):

  1. A hand-built task, `decorative_probe`, whose `ensures` is the
     decorative literal `true`: no mutation on the ladder can ever falsify
     it, so the interpreter's own witness (`w["_ens"]`) is never `True` for
     ANY candidate, and the grounded ladder falls back to a "+nonrefuting"
     twin. Run through dafny (the fast kernel named in the task), both real
     and twin VERIFY (there is nothing in `ensures true` for either to
     fail), so the cell must read `verified / decorative` in the table
     run_par.format_table builds, and `harness.decorative_kind` must say
     "decorative" directly.
  2. The committed `abs` task must still read `verified / refuted` (a real
     flip, unaffected by this change): the twin (COLLAPSE-IF, `r = -x`
     unconditionally) is falsified by any negative `x`, e.g. `x = -1`
     gives real `r = 1` but twin `r = 1` too... no: collapse-if picks the
     THEN branch unconditionally (`r = -x`), so for `x = 1`, real `r = 1`,
     twin `r = -1`, which breaks `ensures r >= 0`. dafny should REFUTE it,
     and `decorative_kind` must return None (the pairing is not
     VERIFIED/VERIFIED at all).

Requires dafny on PATH (the same binary run_par.py/grade.py use). No
network. Run as: cd <repo>/t && python3 test_twin_rule.py

MEASURED 2026-09-11 by `python3 t/test_twin_rule.py`: see the printed
summary line for the exact pass/fail count this run produced.
"""
from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import harness                       # noqa: E402
import tasks_io
import lower_dafny                   # noqa: E402
import run_par                       # noqa: E402
from verifiers import Outcome        # noqa: E402
from verifiers import dafny as dafny_backend  # noqa: E402

UNIT_TESTS = []


def test(fn):
    UNIT_TESTS.append(fn)
    return fn


# A decorative ensures: literally `true`, so no mutation on the ladder can
# ever falsify it (the interpreter's `_breaks_ensures` evaluates `ensures`
# on the twin's own output, and `true` accepts any output). The body is
# abs.json's own (an `if`/`else` assigning `r`), reused so the only
# variable between this task and the committed `abs` task is the spec.
DECORATIVE_PROBE = {
    "t": 0,
    "name": "decorative_probe",
    "params": [{"name": "x", "type": "int"}],
    "returns": [{"name": "r", "type": "int"}],
    "requires": [],
    "ensures": [{"bool": True}],
    "body": [
        {"if": {
            "cond": {"op": "<", "args": [{"var": "x"}, {"int": 0}]},
            "then": [{"assign": ["r", {"op": "neg", "args": [{"var": "x"}]}]}],
            "else": [{"assign": ["r", {"var": "x"}]}]
        }}
    ]
}


def _dafny_available() -> bool:
    try:
        dafny_backend.version()
        return True
    except (Exception, SystemExit):                          # noqa: BLE001
        return False


def _run_one(task: dict, outdir: Path):
    """Lower + verify `task`'s real and twin through dafny alone, via
    run_par.lower_and_dispatch/format_table (the SAME functions run_par.py's
    own main() and grade.py call), never a hand-rolled call to
    verifiers.dafny.verify. Returns (rows, wits, table_text)."""
    tpath = outdir / f"{task['name']}.json"
    tpath.write_text(__import__("json").dumps(task, indent=1), encoding="utf-8")
    prior_out = harness.OUT
    harness.OUT = outdir / "out"
    harness.OUT.mkdir(parents=True, exist_ok=True)
    try:
        present = [("dafny", lower_dafny.lower, "dfy")]
        rows, wits, _all_ok = run_par.lower_and_dispatch(
            [tpath], present, jobs_arg=1, flake_n=1)
        cols = [("dafny", dafny_backend.version())]
        text = run_par.format_table(cols, rows, [tpath], harness.OUT, wits)
    finally:
        harness.OUT = prior_out
    return rows, wits, text


@test
def test_decorative_ensures_true_reads_decorative():
    if not _dafny_available():
        print("  (dafny not on PATH, skipping test_decorative_ensures_true_reads_decorative)")
        return
    with tempfile.TemporaryDirectory(prefix="t-twin-rule-") as td:
        outdir = Path(td)
        twin_body, op, w = harness.twin_cached(DECORATIVE_PROBE)
        assert twin_body is not None, "the ladder must find a witnessed twin"
        # The grounded ladder cannot falsify `ensures true` on any
        # candidate, so the witness it settles for is never a refuting one:
        # kind "value" (never "exit"/"preservation", there is no loop) and
        # `_ens` not True.
        assert w.get("_kind") == "value", w
        assert w.get("_ens") is not True, w

        rows, wits, text = _run_one(DECORATIVE_PROBE, outdir)
        real, twin, agreed = rows["decorative_probe"]["dafny"]
        assert agreed, rows
        assert real == Outcome.VERIFIED, f"real should VERIFY: {real}"
        assert twin == Outcome.VERIFIED, (
            f"twin should ALSO verify ({op}, `ensures true` cannot refute "
            f"it): {twin}")

        kind = harness.decorative_kind(real, twin, w)
        assert kind == "decorative", (kind, w)

        assert "verified / decorative" in text, text
        assert "verified / verified" not in text, text


@test
def test_abs_still_reads_verified_refuted():
    if not _dafny_available():
        print("  (dafny not on PATH, skipping test_abs_still_reads_verified_refuted)")
        return
    abs_task = harness.load(tasks_io.find(HERE / "tasks", "abs"))
    with tempfile.TemporaryDirectory(prefix="t-twin-rule-abs-") as td:
        outdir = Path(td)
        rows, wits, text = _run_one(abs_task, outdir)
        real, twin, agreed = rows["abs"]["dafny"]
        assert agreed, rows
        assert real == Outcome.VERIFIED, f"abs real should VERIFY: {real}"
        assert twin == Outcome.REFUTED, (
            f"abs twin (COLLAPSE-IF, `r = -x` unconditionally) should be "
            f"REFUTED by x=1 breaking `ensures r >= 0`: {twin}")
        assert harness.decorative_kind(real, twin, wits.get("abs")) is None
        row_line = next(l for l in text.splitlines() if l.startswith("| abs "))
        assert row_line == "| abs | verified / refuted |", row_line


@test
def test_decorative_kind_pure_function():
    """No kernel, no dafny: harness.decorative_kind's own contract, so this
    check runs even where dafny is absent."""
    assert harness.decorative_kind(Outcome.VERIFIED, Outcome.REFUTED, None) is None
    assert harness.decorative_kind(Outcome.VERIFIED, Outcome.TIMEOUT, None) is None
    assert harness.decorative_kind(Outcome.VERIFIED, Outcome.VERIFIED, None) == "decorative"
    assert harness.decorative_kind(
        Outcome.VERIFIED, Outcome.VERIFIED, {"_ens": False, "_kind": "value"}
    ) == "decorative"
    assert harness.decorative_kind(
        Outcome.VERIFIED, Outcome.VERIFIED, {"_ens": True, "_kind": "value"}
    ) == "unsound"
    assert harness.decorative_kind(
        Outcome.VERIFIED, Outcome.VERIFIED, {"_kind": "exit"}
    ) == "unsound"
    assert harness.decorative_kind(
        Outcome.VERIFIED, Outcome.VERIFIED, {"_kind": "preservation"}
    ) == "unsound"


def run() -> None:
    failures = 0
    for fn in UNIT_TESTS:
        try:
            fn()
            print(f"{fn.__name__}: pass")
        except AssertionError as e:
            failures += 1
            print(f"{fn.__name__}: FAILED: {e}")
        except Exception as e:                                  # noqa: BLE001
            failures += 1
            traceback.print_exc()
            print(f"{fn.__name__}: FAILED (exception): {e}")
    if failures:
        raise AssertionError(f"{failures} of {len(UNIT_TESTS)} test(s) failed")
    print(f"test_twin_rule: all {len(UNIT_TESTS)} checks passed")


if __name__ == "__main__":
    try:
        run()
    except AssertionError as e:
        print(f"FAILED: {e}")
        sys.exit(1)
    sys.exit(0)
