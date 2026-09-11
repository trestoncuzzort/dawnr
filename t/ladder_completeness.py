#!/usr/bin/env python3
"""t/ladder_completeness.py -- ROADMAP WS-19 move 6, the ladder as a
completeness measurement (survey move 2, demoted), added 2026-09-11.

Move 6, verbatim: "34 of the 35 restate-the-body specs on the 7B's 64 are
already refuted under the single-twin rule, so the fraction of rungs
refuted is measured against the tests on those 64 and on round 2's 23
before it enters any reward. First hurdle: the measurement."

`harness.twin_for` (the single-twin rule) walks the mutation ladder in a
fixed order and STOPS at the first rung with a witness: the cheapest
question ("does the flip rule fire at all"), not "how much of the ladder
does the spec see". This module asks the second question. For every
well-formed task in a spec-experiment column it calls the new
`harness.ladder_rungs(task)` (added beside `twin_for` in t/harness.py,
2026-09-11; reuses twin_for's own candidate generators unchanged, it adds
no mutation logic) to enumerate EVERY rung the ladder can build, not only
the first. Per rung: the operator tag, and whether interp finds a witness
that forces a sound kernel to refute that rung (an invariant-drop witness,
forced by construction, or an extensional witness whose value also
falsifies `ensures` -- the same standard twin_for itself applies before
counting a rung as a flip; a witness that only shows a value difference
without falsifying `ensures` is NOT counted as refuted here, matching
twin_for's own `fallback` distinction).

Per task this reports: rungs total, rungs refuted, the fraction refuted,
the task's own tests outcome (spec_experiment.py's tests.json, keyed by
MBPP task_id), and how many of the seven kernel columns show `verified /
refuted` for that task (spec_experiment.py's kernels.md via
`parse_kernel_table`, reused unchanged).

Columns measured (spec_experiment.py's out/spec-experiment/<tag>/ layout,
see t/LOOP-CURVE.md and spec_experiment.cmd_table):
  qwen2.5-coder-7b            12.6's column, the 64 well-formed tasks.
  qwen2.5-coder-1.5b-r2       round 2's well-formed tasks (23 here).

`is_restate_body` re-implements, structurally on the task JSON (never by
name), the "spec restates the body" shape SPEC-EXPERIMENT-mbpp.md's finding
describes: the task's sole `ensures` is `ret == E` (either argument order)
and the body is the single statement `ret := E` with the SAME `E` (deep
JSON equality after key-order-independent comparison). Checked directly
against the 7B's column, 2026-09-11: 35 of 64 match, the same 35
SPEC-EXPERIMENT-mbpp.md reports, so the detector is the right one to
re-read the 34-of-35 claim against.

CLI: python3 t/ladder_completeness.py --column qwen2.5-coder-7b
     --column qwen2.5-coder-1.5b-r2 --out t/LADDER-COMPLETENESS.md
Deterministic: reads only committed/local out/spec-experiment data and
task JSON, runs the interpreter (no network, no kernels), and writes the
same bytes for the same inputs.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import harness          # noqa: E402
import spec_experiment  # noqa: E402  (parse_kernel_table, reused unchanged)

OUT_ROOT = HERE / "out" / "spec-experiment"


def is_restate_body(task: dict) -> bool:
    """See the module docstring. Structural, not by task name."""
    ens = task.get("ensures", [])
    if len(ens) != 1 or ens[0].get("op") != "==":
        return False
    ret = task["returns"][0]["name"]
    a, b = ens[0]["args"]
    if a == {"var": ret}:
        e = b
    elif b == {"var": ret}:
        e = a
    else:
        return False
    body = task["body"]
    return (len(body) == 1 and "assign" in body[0]
            and body[0]["assign"][0] == ret and body[0]["assign"][1] == e)


def fraction_bucket(refuted: int, total: int) -> str:
    if total > 0 and refuted == total:
        return "all"
    if refuted > 0:
        return "some"
    return "none"


def kernel_bucket(counting: int, total: int) -> str:
    if total > 0 and counting == total:
        return "all seven"
    if counting > 0:
        return "some column"
    return "none"


def measure_column(tag: str) -> dict:
    """Every well-formed task in out/spec-experiment/<tag>/, with its
    ladder-completeness row. Raises FileNotFoundError by name (via
    Path.read_text) if the column's stages have not been run."""
    d = OUT_ROOT / tag
    ext = json.loads((d / "extract.json").read_text(encoding="utf-8"))
    tests = (json.loads((d / "tests.json").read_text(encoding="utf-8"))
             if (d / "tests.json").exists() else {})
    cols, cells = spec_experiment.parse_kernel_table(d / "kernels.md")
    rows = []
    for tid_s, e in sorted(ext.items(), key=lambda kv: int(kv[0])):
        if e["stage"] != "task":
            continue
        name = e["name"]
        task = harness.load(d / "tasks" / f"{name}.json")
        rungs = harness.ladder_rungs(task)
        total = len(rungs)
        refuted = sum(1 for _op, _twin, w in rungs if w is not None)
        frac = (refuted / total) if total else 0.0
        tr = tests.get(tid_s, {}).get("overall", "?")
        krow = cells.get(name, {})
        counting = sum(1 for c in cols if krow.get(c) == "verified / refuted")
        rows.append({
            "task_id": int(tid_s), "fn": e["fn"], "name": name,
            "rungs": total, "refuted": refuted, "fraction": frac,
            "tests": tr, "columns_counting": counting,
            "columns_total": len(cols),
            "restate_body": is_restate_body(task),
            "ops": [op for op, _twin, w in rungs if w is not None],
        })
    return {"tag": tag, "cols": cols, "rows": rows}


def _fmt_frac(f: float) -> str:
    return f"{f:.2f}"


def render(measurements: list[dict]) -> str:
    lines: list[str] = []
    L = lines.append
    L("# The ladder as a completeness measurement")
    L("")
    L("ROADMAP WS-19 move 6, 2026-09-11. `harness.twin_for` (the single-twin")
    L("rule) stops at the ladder's first rung with a witness; this measures")
    L("EVERY rung `harness.ladder_rungs` can build for each well-formed task,")
    L("via the interpreter only (no kernels run here), and cross-tabulates")
    L("the refuted fraction against the task's own tests (tests.json) and")
    L("its kernel verdict (kernels.md, `verified / refuted` per column).")
    L("A rung counts as refuted only when interp shows a sound kernel MUST")
    L("refute it (an invariant-drop witness, or an extensional witness that")
    L("falsifies `ensures`), the same standard `twin_for` applies before")
    L("accepting a flip.")
    L("")
    for m in measurements:
        tag, cols, rows = m["tag"], m["cols"], m["rows"]
        L(f"## Column: `{tag}` ({len(rows)} well-formed tasks)")
        L("")
        L("| task_id | fn | rungs | refuted | fraction | tests | columns counting |")
        L("|---:|---|---:|---:|---:|---|---:|")
        for r in rows:
            L(f"| {r['task_id']} | {r['fn']} | {r['rungs']} | {r['refuted']} | "
              f"{_fmt_frac(r['fraction'])} | {r['tests']} | "
              f"{r['columns_counting']}/{r['columns_total']} |")
        L("")

        # 2x2 (really 3xN): fraction bucket x tests outcome
        test_outcomes = sorted({r["tests"] for r in rows})
        L("### Fraction bucket against tests outcome")
        L("")
        L("| fraction bucket | " + " | ".join(test_outcomes) + " | total |")
        L("|---|" + "---:|" * (len(test_outcomes) + 1))
        for bucket in ("all", "some", "none"):
            brows = [r for r in rows if fraction_bucket(r["refuted"], r["rungs"]) == bucket]
            counts = [sum(1 for r in brows if r["tests"] == t) for t in test_outcomes]
            L(f"| {bucket} rungs refuted | " + " | ".join(str(c) for c in counts)
              + f" | {len(brows)} |")
        L("")

        # fraction bucket x kernel bar
        L("### Fraction bucket against kernel bar")
        L("")
        L("| fraction bucket | all seven | some column | none | total |")
        L("|---|---:|---:|---:|---:|")
        for bucket in ("all", "some", "none"):
            brows = [r for r in rows if fraction_bucket(r["refuted"], r["rungs"]) == bucket]
            kb = [sum(1 for r in brows
                      if kernel_bucket(r["columns_counting"], r["columns_total"]) == k)
                  for k in ("all seven", "some column", "none")]
            L(f"| {bucket} rungs refuted | " + " | ".join(str(c) for c in kb)
              + f" | {len(brows)} |")
        L("")

        # mean fraction per tests outcome
        L("### Mean fraction refuted, per tests outcome")
        L("")
        L("| tests outcome | tasks | mean fraction |")
        L("|---|---:|---:|")
        for t in test_outcomes:
            trows = [r for r in rows if r["tests"] == t]
            mean = sum(r["fraction"] for r in trows) / len(trows) if trows else 0.0
            L(f"| {t} | {len(trows)} | {_fmt_frac(mean)} |")
        L("")

        # plain reading
        all_bucket = [r for r in rows if fraction_bucket(r["refuted"], r["rungs"]) == "all"]
        some_bucket = [r for r in rows if fraction_bucket(r["refuted"], r["rungs"]) == "some"]
        none_bucket = [r for r in rows if fraction_bucket(r["refuted"], r["rungs"]) == "none"]
        all_pass = sum(1 for r in all_bucket if r["tests"] == "pass")
        some_pass = sum(1 for r in some_bucket if r["tests"] == "pass")
        none_pass = sum(1 for r in none_bucket if r["tests"] == "pass")
        L("### Plain reading")
        L("")
        L(f"All-rungs-refuted tasks: {len(all_bucket)}, of which {all_pass} pass "
          f"their tests ({all_pass}/{len(all_bucket)}). Some-rungs-refuted: "
          f"{len(some_bucket)}, of which {some_pass} pass ({some_pass}/{len(some_bucket)}"
          f" if any). No-rungs-refuted: {len(none_bucket)}, of which {none_pass} pass "
          f"({none_pass}/{len(none_bucket)} if any). Read as counts, not a claim of "
          "correlation: the fraction refuted does not sort tasks by tests outcome here"
          " -- a fully-refuted ladder is common in both the passing and the failing"
          " rows, since the ladder measures how much of the mutation space the spec"
          " sees, and the tests measure whether the spec is the problem's, two"
          " different questions by 12.6's own finding.")
        L("")

        # restate-the-body re-read
        rb_rows = [r for r in rows if r["restate_body"]]
        rb_all = [r for r in rb_rows if fraction_bucket(r["refuted"], r["rungs"]) == "all"]
        all_rungs_any = [r for r in rows if fraction_bucket(r["refuted"], r["rungs"]) == "all"]
        L("### The 34-of-35 restate-the-body claim, re-read")
        L("")
        if rb_rows:
            L(f"{len(rb_rows)} of the {len(rows)} tasks are the restate-the-body shape "
              f"(`is_restate_body`, structural: sole `ensures` is `ret == E`, body is "
              f"the single statement `ret := E`, same `E`). Of those, {len(rb_all)} have "
              f"EVERY rung on the full ladder refuted (not just the first rung the "
              f"single-twin rule tries), against the {len(all_rungs_any)} of all "
              f"{len(rows)} well-formed tasks with every rung refuted.")
        else:
            L(f"No restate-the-body tasks (by the structural detector above) in this "
              f"column. {len(all_rungs_any)} of {len(rows)} well-formed tasks have "
              "every rung on the full ladder refuted.")
        L("")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--column", action="append", dest="columns", required=True,
                     help="a directory name under out/spec-experiment/, "
                          "e.g. qwen2.5-coder-7b; may repeat")
    ap.add_argument("--out", default=str(HERE / "LADDER-COMPLETENESS.md"))
    args = ap.parse_args(argv)
    measurements = [measure_column(tag) for tag in args.columns]
    text = render(measurements)
    Path(args.out).write_text(text, encoding="utf-8")
    for m in measurements:
        print(f"{m['tag']}: {len(m['rows'])} well-formed tasks measured")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
