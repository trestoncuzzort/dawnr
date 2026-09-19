#!/usr/bin/env python3
"""t/constrained_compare.py -- what decoding against t's grammar bought (2026-09-18, WS-21).

    python3 t/constrained_compare.py [--control TAG] [--arm TAG] [--out PATH]

The arms and the rule were fixed before either arm existed, in `t/PREREG-2026-09-18-constrained.md`: the same
problems, model, prompt, temperature and seed, differing only in whether the request carried t's grammar. The
amendment of the same day, written before anything was graded, says two more things this obeys:

  * The sample is whatever prefix the constrained arm reached, and the comparison is over the problems it
    ATTEMPTED -- answered or timed out -- intersected with the problems the control answered. A problem the
    constraint could not finish counts against it rather than being dropped, since dropping it would select
    for the problems the constraint finds easy.
  * The primary outcome is answers that pass their own tests, not clean answers: the control produced 16 clean
    over 1,133 problems, and no rule can tell two arms apart on that at a few hundred.

Clean answers are reported beside it, and so is the number the whole experiment exists for: the test-pass rate
among answers that PARSE, which separates a model that wrote a good program in the wrong notation from a model
that wrote a bad program.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

SE = HERE / "out" / "spec-experiment"
KERNELS = ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"]


def load(tag: str) -> dict:
    d = SE / tag
    out = {"tag": tag, "dir": d, "extract": {}, "tests": {}, "clean": set(), "wall": {}}
    try:
        out["extract"] = json.loads((d / "extract.json").read_text())
    except (OSError, ValueError):
        pass
    try:
        out["tests"] = {str(k): v for k, v in json.loads((d / "tests.json").read_text()).items()}
    except (OSError, ValueError):
        pass
    if (d / "kernels.md").exists():
        import spec_experiment as se
        _cols, cells = se.parse_kernel_table(d / "kernels.md")
        passing = {v.get("name") for v in out["tests"].values() if v.get("overall") == "pass"}
        out["clean"] = {n for n, r in cells.items()
                        if n in passing and all(r.get(k, "").startswith("verified / refuted") for k in KERNELS)}
        out["graded"] = set(cells)
    else:
        out["graded"] = set()
    for tid in out["extract"]:
        p = d / "raw" / f"{tid}.json"
        if p.exists():
            try:
                out["wall"][tid] = json.loads(p.read_text()).get("wall_s", 0.0)
            except (OSError, ValueError):
                pass
    return out


def name_of(arm: dict, tid: str) -> str | None:
    e = arm["extract"].get(tid) or {}
    return e.get("name")


def counts(arm: dict, ids: set[str]) -> dict:
    """Over a fixed set of problem ids, how many got through each gate. A problem with no answer at all --
    the constraint timed out on it -- counts in the denominator and passes nothing."""
    parsed = wf = tests = clean = 0
    for tid in ids:
        e = arm["extract"].get(tid)
        if not e:
            continue                                            # attempted, nothing came back
        if e.get("stage") in ("task", "wf"):
            parsed += 1                                         # wf means it parsed and then failed a rule
        if e.get("stage") == "task":
            wf += 1
            if (arm["tests"].get(tid) or {}).get("overall") == "pass":
                tests += 1
            n = e.get("name")
            if n and n in arm["clean"]:
                clean += 1
    return {"problems": len(ids), "answered": sum(1 for t in ids if t in arm["extract"]),
            "parsed": parsed, "wf": wf, "tests": tests, "clean": clean}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--control", default="qwen3-coder-30b-apps-s1")
    ap.add_argument("--arm", default="qwen3-coder-30b-apps-g1")
    ap.add_argument("--timedout", type=Path, default=HERE / "out" / "loop" / "g1-timedout.txt")
    ap.add_argument("--out", type=Path, default=HERE / "out" / "CONSTRAINED-2026-09-18.md")
    a = ap.parse_args()

    ctl, arm = load(a.control), load(a.arm)
    timed_out = set()
    if a.timedout.exists():
        timed_out = {x.strip() for x in a.timedout.read_text().split() if x.strip()}
    attempted = set(arm["extract"]) | timed_out
    ids = sorted(attempted & set(ctl["extract"]), key=int)
    if not ids:
        print("the two arms share no problem; nothing to compare")
        return 1
    ids = set(ids)

    c, g = counts(ctl, ids), counts(arm, ids)
    pct = lambda n: f"{100 * n / len(ids):.0f}%"                 # noqa: E731
    ratio = (g["tests"] / c["tests"]) if c["tests"] else float("inf")

    rows = [("problems attempted by both", c["problems"], g["problems"]),
            ("an answer came back", c["answered"], g["answered"]),
            ("parses as t", c["parsed"], g["parsed"]),
            ("well formed", c["wf"], g["wf"]),
            ("passes the problem's own tests", c["tests"], g["tests"]),
            ("clean: tests, seven proofs, refuted twin", c["clean"], g["clean"])]

    lines = [f"# What the grammar bought, {a.arm} against {a.control}", "",
             "Preregistered in [`t/PREREG-2026-09-18-constrained.md`](PREREG-2026-09-18-constrained.md),",
             "with the sample and the primary outcome amended before anything was graded. Same model, prompt,",
             "temperature and seed; the only difference is that the constrained arm's request carried",
             f"[`t/t.gbnf`](t.gbnf). Over the {len(ids)} problems the constrained arm attempted and the control",
             f"answered, of which it could not finish {len(timed_out & ids)} inside half an hour each -- those",
             "count here as attempts that passed nothing.", "",
             "| | control | constrained |", "|---|---|---|"]
    for label, cv, gv in rows:
        lines.append(f"| {label} | {cv} ({pct(cv)}) | {gv} ({pct(gv)}) |")

    ctp = c["tests"] / c["parsed"] if c["parsed"] else 0
    gtp = g["tests"] / g["parsed"] if g["parsed"] else 0
    lines += ["", "## The number the experiment exists for", "",
              "| | control | constrained |", "|---|---|---|",
              f"| tests pass, among answers that parse | {c['tests']}/{c['parsed']} ({100*ctp:.0f}%) "
              f"| {g['tests']}/{g['parsed']} ({100*gtp:.0f}%) |", "",
              "A constrained model writes t by construction. If its answers pass the problems' own tests at",
              "the rate the control's parsing answers do, the notation was the only thing in the way. If they",
              "pass at a lower rate, the constraint is buying syntax with sense, which is what locallm looks",
              "like at 98 percent parsing and under 1 percent passing.", "",
              "## The rule, applied", ""]
    verdict = ("ADOPT: the constrained arm passes tests on at least 1.5 times the problems"
               if ratio >= 1.5 else
               "REJECT: the constrained arm passes tests on fewer problems than the control"
               if g["tests"] < c["tests"] else
               "INCONCLUSIVE, the more informative outcome: the parse wall is real and the gates below it "
               "absorb what passes, so the limit is semantic")
    lines += [f"Test-passing problems: control {c['tests']}, constrained {g['tests']} "
              f"({'x%.2f' % ratio if ratio != float('inf') else 'no control baseline'}).", "", f"**{verdict}.**", ""]

    secs = sum(arm["wall"].get(t, 0.0) for t in ids if t in arm["wall"])
    if g["tests"]:
        lines += [f"Cost: {secs/60:.0f} generation minutes for {g['tests']} test-passing answers, "
                  f"{secs/max(g['tests'],1):.0f} s each. The control's whole 1,133-problem run took about 19 "
                  f"minutes.", ""]
    text = "\n".join(lines) + "\n"
    a.out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
