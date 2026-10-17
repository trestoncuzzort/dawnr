#!/usr/bin/env python3
"""t/spec_strength.py: score how strongly each task's specification constrains wrong programs, and
emit a ranked worklist of the exact gaps to strengthen.

Built on t/audit.py (`audit_file` -> survivors with {op, change, witness}). A *survivor* is a
behaviour-changing one-edit mutant that the task's `ensures` still accepts: a concrete witness that
the specification is under-constrained there. This reports the mutation-based specification strength

    strength = killed / (killed + survivors)       # 1.0 = no behaviour-changing mutant slips the spec

over behaviour-changing mutants (equivalent / diverging / ill-formed mutants are excluded, exactly as
in audit), and ranks tasks weakest-first with each survivor's operator, changed line and separating
witness, so an under-constrained spec can be strengthened against those exact counterexamples.

This is the MEASUREMENT half of specification refinement: a surviving twin plus its witness is the
counterexample a strengthened `ensures` must exclude (the refiner, t/spec_refine.py, consumes the
--worklist this writes). The metric and the strengthen-against-the-surviving-mutant design follow the
specification-strength literature distilled in internal/research/spec-validation.md and
internal/research/vacuity-spec-strength-sweep-2026-09-20.md: mutation score AS specification strength
(MutDafny, arXiv:2511.15403; FormalBench, arXiv:2503.04779; FMCAD'24, arXiv:2406.09757), negative
examples as a reusable completeness signal (SpecRL, arXiv:2604.05820), and refinement by
variant discrimination / counterexample generalisation (SpecSyn, arXiv:2604.21570; ExVerus,
arXiv:2603.25810). It motivates E1's finding that the seven-kernel false-accept floor is a
specification gap, not a prover gap (internal/E1-FINDINGS-2026-10-14.md).

Usage:
    python3 t/spec_strength.py <FILE|DIR> [--jobs N] [--seconds S] [--kernel K]
                               [--json OUT.jsonl] [--worklist OUT.json]

Pure interpreter by default (no proof kernels). With --kernel it also confirms which survivors a
kernel actually proves (a true false-accept), reusing audit's kernel path.
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # t/ on path for audit/harness/interp
import audit  # noqa: E402


def score_one(path: str, kernel: str | None = None, seconds: int | None = None) -> dict:
    """Score a single task file. Returns strength, counts, and each survivor's {op, change,
    witness, kernel_proved}. strength is None when there is no behaviour-changing mutant (no
    evidence about the spec either way) or the task is not auditable."""
    r = audit.audit_file(path, kernel=kernel, seconds=seconds or audit.TASK_SECONDS)
    name = r.get("name", Path(path).stem)
    if r.get("status") != "ok":
        return {"name": name, "file": path, "status": r.get("status"), "strength": None,
                "changing": 0, "killed": 0, "survivors": [], "capped": False, "real_verdict": None}
    killed = r.get("killed", 0)
    survs = r.get("survivors", [])
    changing = killed + len(survs)
    strength = (killed / changing) if changing else None
    gaps = [{"op": s.get("op"), "change": s.get("change"), "witness": s.get("witness"),
             "kernel_proved": s.get("verdict") == "verified"} for s in survs]
    return {"name": name, "file": path, "status": "ok", "strength": strength,
            "changing": changing, "killed": killed, "survivors": gaps,
            "capped": r.get("capped", False),
            "real_verdict": r.get("real_verdict") if kernel else None}


def _star(args: tuple) -> dict:
    return score_one(*args)


def rank_weakest(rows: list[dict]) -> list[dict]:
    """ok tasks with >=1 survivor, weakest spec first (lowest strength, then most survivors)."""
    weak = [r for r in rows if r["status"] == "ok" and r["survivors"]]
    return sorted(weak, key=lambda r: ((r["strength"] if r["strength"] is not None else 1.0),
                                       -len(r["survivors"])))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="spec_strength.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("target", metavar="FILE|DIR")
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--seconds", type=int, default=audit.TASK_SECONDS, help="interpreter budget per task")
    ap.add_argument("--kernel", help="also confirm survivors in this kernel (a true false-accept)")
    ap.add_argument("--json", metavar="PATH", help="one JSON line per task")
    ap.add_argument("--worklist", metavar="PATH", help="ranked survivors (weakest specs first) as JSON")
    a = ap.parse_args(argv)
    if a.kernel and a.kernel not in audit.tlib._LOWER_MOD:
        print(f"spec_strength.py: unknown kernel {a.kernel!r}; known: {sorted(audit.tlib._LOWER_MOD)}",
              file=sys.stderr)
        return 2

    target = Path(a.target)
    files = ([str(p) for p in sorted(target.iterdir()) if p.suffix in (".t", ".json")]
             if target.is_dir() else [str(target)])
    if not files:
        print(f"spec_strength.py: no .t/.json tasks under {a.target}", file=sys.stderr)
        return 2
    run = [(f, a.kernel, a.seconds) for f in files]
    if a.jobs > 1:
        with ProcessPoolExecutor(max_workers=a.jobs) as ex:
            rows = list(ex.map(_star, run))
    else:
        rows = [score_one(*r) for r in run]

    ok = [r for r in rows if r["status"] == "ok"]
    changing = sum(r["changing"] for r in ok)
    killed = sum(r["killed"] for r in ok)
    corpus_strength = (killed / changing) if changing else None
    weak = rank_weakest(rows)

    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, sort_keys=True) + "\n")
    if a.worklist:
        wl = [{"name": r["name"], "file": r["file"], "strength": r["strength"],
               "survivors": r["survivors"]} for r in weak]
        with open(a.worklist, "w", encoding="utf-8") as f:
            json.dump(wl, f, indent=1)

    status_counts: dict[str, int] = {}
    for r in rows:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
    non_ok = ", ".join(f"{v} {k}" for k, v in sorted(status_counts.items()) if k != "ok")
    print(f"spec-strength: {len(ok)} tasks audited" + (f"; non-ok: {non_ok}" if non_ok else ""))
    cs = f"{corpus_strength * 100:.1f}%" if corpus_strength is not None else "n/a"
    print(f"corpus spec-strength (killed / behaviour-changing): {cs}  ({killed}/{changing})")
    print(f"under-constrained specs (>=1 survivor): {len(weak)} of {len(ok)}"
          + ("  [weakest first]" if weak else ""))
    for r in weak[:25]:
        st = f"{r['strength'] * 100:.0f}%" if r["strength"] is not None else " n/a"
        ex = r["survivors"][0]
        extra = " [kernel-proved]" if any(s["kernel_proved"] for s in r["survivors"]) else ""
        print(f"  {st:>4}  {r['name']}: {len(r['survivors'])} survivor(s){extra}; "
              f"e.g. {ex['op']}: {ex['change']} at {ex['witness']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
