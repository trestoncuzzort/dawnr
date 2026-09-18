#!/usr/bin/env python3
"""t/ablation.py -- what the seven checkers and the twin rule buy (2026-09-17).

    python3 t/ablation.py [--events ~/.cache/t-watch/events.jsonl] [--out t/ABLATION-2026-09-17.md]

The gates, the metrics and the decision rule were fixed before this ran, in `t/PREREG-2026-09-17-ablation.md`.
Each gate is applied to the answers already graded in this repository, so nothing is regenerated or regraded:
one prover or seven, with the deliberately broken twin required or ignored. The tests decide what is wrong, and
they are in no gate, so an answer a gate admits whose tests fail is a false accept.

Standard library only. The table it prints is the table it writes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

KERNELS = ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"]
HELD_OUT_TAGS = {"phi4-mini-v3", "qwen15b-base-v3", "student-r4-v3", "student-r5-v3",
                 "locallm-r0", "locallm-r4", "locallm-r5"}

GATES = {
    "dafny": lambda v: v["dafny"][0] == "verified",
    "dafny+twin": lambda v: v["dafny"] == ("verified", "refuted"),
    "any1": lambda v: any(v[k][0] == "verified" for k in KERNELS),
    "four+twin": lambda v: sum(1 for k in KERNELS if v[k] == ("verified", "refuted")) >= 4,
    "seven": lambda v: all(v[k][0] == "verified" for k in KERNELS),
    "seven+twin": lambda v: all(v[k] == ("verified", "refuted") for k in KERNELS),
}


def cells(path: Path) -> dict:
    """task name -> {kernel: (real, twin)} from a kernels.md table."""
    cols, rows = [], {}
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return rows
    for line in lines:
        if not line.startswith("|"):
            continue
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if c[0] == "task":
            cols = c[1:]
        elif cols and len(c) == len(cols) + 1 and set(c[0]) - {"-"}:
            v = {}
            for k, cell in zip(cols, c[1:]):
                real, _, twin = cell.replace("(FLAKED)", "").partition(" / ")
                v[k] = (real.strip(), twin.strip())
            if all(k in v for k in KERNELS):
                rows[c[0]] = v
    return rows


def prover_seconds(events: Path) -> dict:
    out, open_at = {}, {}
    try:
        for line in events.read_text(errors="replace").splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            key = (e.get("task"), e.get("kernel"))
            if e.get("ev") == "start":
                open_at[key] = e.get("t", 0)
            elif e.get("ev") == "end" and key in open_at:
                out[key[0]] = out.get(key[0], 0.0) + max(0.0, e.get("t", 0) - open_at.pop(key))
    except OSError:
        pass
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--events", type=Path,
                    default=Path(os.environ.get("T_WATCH", Path.home() / ".cache/t-watch/events.jsonl")))
    ap.add_argument("--out", type=Path, default=HERE / "ABLATION-2026-09-17.md")
    ap.add_argument("--dir", type=Path, default=HERE / "out" / "spec-experiment")
    a = ap.parse_args()
    secs = prover_seconds(a.events)

    groups = {"training-problem answer sets": [], "held-out answer sets": []}
    for d in sorted(p for p in a.dir.glob("*") if p.is_dir()):
        rows = cells(d / "kernels.md")
        if not rows:
            continue
        try:
            tests = {v.get("name"): v.get("overall") for v in json.loads((d / "tests.json").read_text()).values()}
        except (OSError, ValueError):
            continue
        which = "held-out answer sets" if d.name in HELD_OUT_TAGS else "training-problem answer sets"
        for name, v in rows.items():
            groups[which].append((name, v, tests.get(name) == "pass", secs.get(name, 0.0)))

    lines = ["# What the seven checkers and the twin rule buy, 2026-09-17", "",
             "Measured by `t/ablation.py` over every answer already graded here, under the gates and the decision",
             "rule fixed beforehand in [`t/PREREG-2026-09-17-ablation.md`](PREREG-2026-09-17-ablation.md). The tests",
             "are in no gate, so an admitted answer whose tests fail is a false accept.", ""]
    for group, data in groups.items():
        if not data:
            continue
        lines += [f"## {group} ({len(data)} graded answers)", "",
                  "| gate | accepted | false accepts | false-accept rate | problems covered | prover s per accepted |",
                  "|---|---|---|---|---|---|"]
        print(f"\n{group}: {len(data)} graded answers")
        for gate, ok in GATES.items():
            acc = [(n, v, passed, s) for n, v, passed, s in data if ok(v)]
            bad = [x for x in acc if not x[2]]
            probs = {n.split("__")[0] for n, _v, _p, _s in acc}
            rate = f"{100 * len(bad) / len(acc):.1f}%" if acc else "-"
            per = f"{sum(s for *_x, s in acc) / len(acc):.0f}" if acc else "-"
            lines.append(f"| `{gate}` | {len(acc)} | {len(bad)} | {rate} | {len(probs)} | {per} |")
            print(f"  {gate:12s} accepted {len(acc):5d}  false {len(bad):4d}  rate {rate:>6s}  "
                  f"problems {len(probs):4d}  prover s/accepted {per:>5s}")
        lines.append("")
    a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nwritten to {a.out.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
