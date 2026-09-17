#!/usr/bin/env python3
"""t/yield.py -- what one verified example costs (2026-09-17).

    python3 t/yield.py [--events ~/.cache/t-watch/events.jsonl] [tag ...]

The filter accepts an answer only when its tests pass, seven independent proof systems verify it, and all seven
refute a deliberately broken copy of it at a concrete input. Nothing here is a model's opinion of a model. This
script says what that costs: how many generations, how many seconds of generation and how many seconds of proof
per accepted example, per answer set and over all of them.

Generation seconds come from each reply's own `wall_s` in raw/<id>.json. Proof seconds come from the check
events run_par.py writes (T_WATCH), summed over the cells of that answer set's tasks, so a set graded on another
machine counts too as long as its events reached this one. A set graded before the event file existed reports
its proof seconds as unknown rather than zero.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import spec_experiment as se                                    # noqa: E402

KERNELS = ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"]


def kernel_rows(path: Path) -> tuple[list[str], dict]:
    cols, rows = [], {}
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return cols, rows
    for line in lines:
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells[0] == "task":
            cols = cells[1:]
        elif cols and len(cells) == len(cols) + 1 and set(cells[0]) - {"-"}:
            rows[cells[0]] = dict(zip(cols, cells[1:]))
    return cols, rows


def proof_seconds(events: Path) -> dict[str, float]:
    """Seconds of proof per task name, from the start and end events of its cells."""
    out: dict[str, float] = {}
    open_at: dict[tuple, float] = {}
    try:
        for line in events.read_text(errors="replace").splitlines():
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            key = (ev.get("task"), ev.get("kernel"))
            if ev.get("ev") == "start":
                open_at[key] = ev.get("t", 0)
            elif ev.get("ev") == "end" and key in open_at:
                out[key[0]] = out.get(key[0], 0.0) + max(0.0, ev.get("t", 0) - open_at.pop(key))
    except OSError:
        pass
    return out


def one(tag: str, secs: dict[str, float]) -> dict | None:
    d = se.outdir(tag)
    if not (d / "raw").is_dir():
        return None
    asked = gen_s = 0
    for f in (d / "raw").glob("*.json"):
        asked += 1
        try:
            gen_s += float(json.loads(f.read_text(errors="replace")).get("wall_s") or 0)
        except (OSError, ValueError):
            pass
    try:
        ext = json.loads((d / "extract.json").read_text(errors="replace"))
        wf = sum(1 for e in ext.values() if e.get("stage") == "task")
    except (OSError, ValueError):
        wf = 0
    passing = set()
    try:
        for v in json.loads((d / "tests.json").read_text(errors="replace")).values():
            if v.get("overall") == "pass":
                passing.add(v.get("name"))
    except (OSError, ValueError):
        pass
    cols, rows = kernel_rows(d / "kernels.md")
    clean = [n for n, r in rows.items()
             if n in passing and all(r.get(k, "").startswith("verified / refuted") for k in KERNELS)]
    proof_s = sum(secs.get(n, 0.0) for n in rows)
    return {"tag": tag, "asked": asked, "wellformed": wf, "tests_pass": len(passing), "graded": len(rows),
            "clean": len(clean), "gen_s": gen_s, "proof_s": proof_s,
            "problems": {n.split("__")[0] for n in clean}}


def fmt(x: float) -> str:
    return "-" if not x else (f"{x:.0f}" if x < 1000 else f"{x / 60:.0f} min")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("tags", nargs="*")
    ap.add_argument("--events", type=Path,
                    default=Path(os.environ.get("T_WATCH", Path.home() / ".cache/t-watch/events.jsonl")))
    a = ap.parse_args()
    secs = proof_seconds(a.events)
    tags = a.tags or sorted(p.name for p in (HERE / "out" / "spec-experiment").glob("*") if p.is_dir())
    rows = [r for r in (one(t, secs) for t in tags) if r and r["asked"]]
    if not rows:
        print("no answer sets found")
        return 1
    print(f"{'answer set':40s} {'asked':>6} {'wf':>5} {'tests':>6} {'graded':>7} {'clean':>6} "
          f"{'asked/clean':>12} {'gen s/clean':>12} {'proof s/clean':>14}")
    tot = {k: 0 for k in ("asked", "wellformed", "tests_pass", "graded", "clean")}
    tot_gen = tot_proof = 0.0
    problems: set[str] = set()
    for r in sorted(rows, key=lambda r: -r["clean"]):
        c = r["clean"]
        print(f"{r['tag'][:40]:40s} {r['asked']:6d} {r['wellformed']:5d} {r['tests_pass']:6d} {r['graded']:7d} "
              f"{c:6d} {(r['asked'] / c if c else 0):12.1f} {(r['gen_s'] / c if c else 0):12.1f} "
              f"{(r['proof_s'] / c if c else 0):14.1f}")
        for k in tot:
            tot[k] += r[k]
        tot_gen += r["gen_s"]
        tot_proof += r["proof_s"]
        problems |= r["problems"]
    c = tot["clean"] or 1
    print(f"\n{tot['asked']} generations, {tot['wellformed']} well formed, {tot['tests_pass']} passing their "
          f"tests, {tot['graded']} graded, {tot['clean']} clean over {len(problems)} distinct problems.")
    print(f"Per accepted example: {tot['asked'] / c:.1f} generations, {tot_gen / c:.0f} s of generation, "
          f"{tot_proof / c:.0f} s of proof ({fmt(tot_proof / c)}).")
    print(f"Generation is {tot_gen / 3600:.1f} h and proof {tot_proof / 3600:.1f} h in total, as measured; "
          f"proof seconds are wall time per cell, and cells run in parallel, so the clock time is lower.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
