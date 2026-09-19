#!/usr/bin/env python3
"""t/recheck_near.py -- the answers one kernel away from clean, re-run alone (2026-09-19).

    python3 t/recheck_near.py [--only timeout] [--kernels spark,framac,lean] [--limit N] [--flake 3]

87 answers across this repository pass their own tests and are verified by six of the seven with the twin
refuted, and stopped at one kernel. 35 of those stopped on a *timeout*, which `t/lower_spark.py`'s own notes
call provisional rather than a verdict: a cell graded at 32 concurrent cells is competing with 31 others for
its wall clock, and the same cell run alone often proves. A timeout is also the one outcome `t/preflight.py`
refuses to let a clean answer rest on.

So this re-runs the blocking kernel by itself, at flake 3, on whatever machine it is given, and reports which
cells change their mind. A cell that now reads verified with its twin refuted turns its answer clean and
belongs in the pool; one that times out again alone is a real cost, not a scheduling artifact, and is worth
knowing as such.

Anything that flips is written to `t/out/recheck.json` in the form preflight.py already reads, so the change
is auditable rather than a hand-edited table. Nothing edits a kernels.md: the tables stay as the sweep wrote
them and the re-check is a record beside them.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness                                                  # noqa: E402
import spec_experiment as se                                    # noqa: E402
import tlib                                                     # noqa: E402

SE = HERE / "out" / "spec-experiment"
KERNELS = ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"]


def near_misses() -> list[dict]:
    """Every test-passing answer that six kernels verified with the twin refuted and one did not."""
    out = []
    for d in sorted(SE.glob("*")):
        if not (d / "kernels.md").exists():
            continue
        try:
            tests = {v.get("name"): v.get("overall")
                     for v in json.loads((d / "tests.json").read_text()).values()}
        except (OSError, ValueError):
            tests = {}
        _cols, cells = se.parse_kernel_table(d / "kernels.md")
        for name, row in cells.items():
            if tests.get(name) != "pass":
                continue
            bad = [k for k in KERNELS if not row.get(k, "").startswith("verified / refuted")]
            if len(bad) != 1:
                continue
            cell = row.get(bad[0], "").replace(" (FLAKED)", "")
            real, _, twin = cell.partition(" / ")
            out.append({"tag": d.name, "task": name, "kernel": bad[0],
                        "was": f"{real.strip()} / {twin.strip()}"})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", default="timeout", help="'timeout', 'abstain', 'unproved' or 'all'")
    ap.add_argument("--kernels", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--flake", type=int, default=3)
    ap.add_argument("--out", type=Path, default=HERE / f"RECHECK-{time.strftime('%Y-%m-%d')}.md")
    a = ap.parse_args()

    rows = near_misses()
    if a.only != "all":
        rows = [r for r in rows if a.only in r["was"]]
    if a.kernels:
        want = set(a.kernels.split(","))
        rows = [r for r in rows if r["kernel"] in want]
    if a.limit:
        rows = rows[:a.limit]
    if not rows:
        print("nothing matches")
        return 1
    print(f"{len(rows)} cells to re-run alone, flake {a.flake}", flush=True)

    flipped, held, failed = [], [], []
    for i, r in enumerate(rows, 1):
        path = SE / r["tag"] / "tasks" / f"{r['task']}.json"
        if not path.exists():
            failed.append({**r, "now": "the task file is not on this machine"})
            continue
        task = harness.load(path)
        t0 = time.monotonic()
        try:
            got = tlib.verify(task, [r["kernel"]], flake=a.flake)[r["kernel"]]
        except Exception as e:                                  # noqa: BLE001
            failed.append({**r, "now": f"{type(e).__name__}: {e}"[:80]})
            continue
        now = f"{got.get('real')} / {got.get('twin')}"
        secs = time.monotonic() - t0
        rec = {**r, "now": now, "seconds": round(secs, 1), "provisional": bool(got.get("provisional"))}
        (flipped if now == "verified / refuted" and not got.get("provisional") else held).append(rec)
        print(f"  [{i}/{len(rows)}] {r['kernel']:7s} {r['task'][:34]:34s} {r['was']:22s} -> {now:22s} "
              f"{secs:6.1f} s", flush=True)

    if flipped:
        p = HERE / "out" / "recheck.json"
        try:
            prev = json.loads(p.read_text())
        except (OSError, ValueError):
            prev = {"rechecked": []}
        for r in flipped:
            prev["rechecked"].append({
                "tag": r["tag"], "task": r["task"], "kernel": r["kernel"],
                "was": r["was"] + " under the sweep", "alone": "verified / refuted",
                "agrees_with": "the other six kernels on the same answer",
                "how": f"python3 t/recheck_near.py --only {a.only} --flake {a.flake}",
                "when": time.strftime("%F"), "seconds": r["seconds"],
                "why": "a cell graded at 32 concurrent cells competes for its wall clock; "
                       "lower_spark.py's own notes call such a cell provisional until re-run alone"})
        p.write_text(json.dumps(prev, indent=1) + "\n", encoding="utf-8")

    lines = [f"# The answers one kernel from clean, re-run alone, {time.strftime('%Y-%m-%d %H:%MZ', time.gmtime())}",
             "", f"`t/recheck_near.py --only {a.only} --flake {a.flake}`. {len(rows)} cells, each the single",
             "kernel that kept an otherwise-clean answer out, re-run by itself instead of beside 31 others.", "",
             f"- **changed their mind: {len(flipped)}** (now verified with the twin refuted)",
             f"- held their verdict: {len(held)}", f"- could not be run here: {len(failed)}", ""]
    if flipped:
        lines += ["## Changed their mind", "", "| kernel | answer set | task | was | seconds alone |",
                  "|---|---|---|---|---|"]
        lines += [f"| `{r['kernel']}` | {r['tag']} | `{r['task']}` | {r['was']} | {r['seconds']} |"
                  for r in flipped]
        lines += ["", f"These {len(flipped)} answers are clean: their tests pass and all seven now verify them",
                  "with the twin refuted. The flip is recorded in `t/out/recheck.json`, which `t/preflight.py`",
                  "reads; no kernels.md was edited.", ""]
    if held:
        lines += ["## Held their verdict", "", "| kernel | task | was | now | seconds |", "|---|---|---|---|---|"]
        lines += [f"| `{r['kernel']}` | `{r['task']}` | {r['was']} | {r['now']} | {r.get('seconds', '')} |"
                  for r in held]
        lines += ["", "For these the outcome is a real cost, not a scheduling artifact.", ""]
    a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n{len(flipped)} flipped, {len(held)} held, {len(failed)} could not run; "
          f"written to {a.out.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
