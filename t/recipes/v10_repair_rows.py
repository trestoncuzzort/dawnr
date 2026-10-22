#!/usr/bin/env python3
"""v10 rows, the repair traces: (a failed specification, the checker's witness, the specification that was kept).

The route's repair turn (t/spec_first.py --repair) was falsified three ways this week: the 4B student rewrites but
does not fix (1 of 32 asks accepted). The literature says that is a blind spot of the training data, not of the
prompt: fine-tuning on 5,306 error-correction traces cut the self-correction blind spot by 76.0%
(arXiv:2507.02778), and small code models trained to refine gain up to 63.5% relative (CYCLE, arXiv:2403.18746).
This builds the traces from our own records, in the route's own repair question (spec_first.repair_question), so
the skill trained is the turn the route asks for:

  * a candidate the problem's tests dropped (scored-specs.jsonl, verdict "dropped"), its witnesses from
    spec_quality.witnesses (the first test the specification rejects, or the first wrong result it accepts);
  * a candidate the tests kept but the strict reference check dropped (v9_strict_specs.py --dropped), its witness
    phrased from the reference record (the drawn input, what the problem's solution answers, what the
    specification also accepts, or that the ensures is false of the right answer);

each paired with the first strictly kept specification of the same problem as the answer. At most
--max-per-problem traces a problem, duplicates dropped. Rows have the shape of t/spec_first_rows.build_from_specs.

    python3 t/recipes/v10_repair_rows.py --scored SCORED.jsonl --strict-kept KEPT.jsonl --strict-dropped DROPPED.jsonl \\
        --pool v5 --out out/v10/repair-rows.jsonl --report out/v10/repair-rows.json

Sources: t/spec_first.py (repair_question, REPAIR_ASK), t/spec_quality.py (witnesses), t/spec_first_rows.py
(build_from_specs), t/spec_check.py (the reference record's fields); arXiv:2507.02778; arXiv:2403.18746.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import loop_dataset                                             # noqa: E402
import spec_experiment as se                                    # noqa: E402
import spec_first                                               # noqa: E402
import spec_first_rows                                          # noqa: E402
import spec_quality                                             # noqa: E402
import surface                                                  # noqa: E402


def reference_witness(r: dict) -> list[str]:
    """One plain sentence from a strict reference record, in the words of spec_check's own report lines."""
    status = r.get("status")
    if status == "disagrees":
        return [f"on the input {r.get('args')!r} the problem's solution answers {r.get('reference_said')!r}, "
                f"and an ensures clause is false of that answer"[:240]]
    w = r.get("weak_witness") or r.get("cross_witness")
    if isinstance(w, dict) and "also_accepts" in w:
        return [f"on the input {w.get('args')!r} the problem's solution answers {w.get('reference_said')!r}, "
                f"and the specification also accepts the wrong result {w.get('also_accepts')!r}"[:240]]
    c = r.get("completeness")
    if isinstance(c, (int, float)):
        return [f"the specification accepts {round(100 * (1 - c))}% of wrong results drawn near the right one"]
    return [f"the specification does not pin the answer down ({status})"]


def fenced(task: dict, fn: str) -> str:
    spec = se.rename_task(spec_first_rows.specification_of(json.loads(json.dumps(task))), fn)
    return loop_dataset.fence(surface.print_task(spec).strip())


def build(scored: list[dict], kept: list[dict], dropped: list[dict], pool: dict, max_per_problem: int = 3) -> tuple[list[dict], dict]:
    rows, counts = [], Counter()
    kept_by = {int(k["task_id"]): k for k in kept}
    test_dropped: dict[int, list[dict]] = {}
    for r in scored:
        if r.get("verdict") == "dropped":
            test_dropped.setdefault(int(r["task_id"]), []).append(r)
    ref_dropped: dict[int, list[dict]] = {}
    for d in dropped:
        ref_dropped.setdefault(int(d["task_id"]), []).append(d)
    for tid, k in kept_by.items():
        entry = pool.get(tid)
        if entry is None:
            counts["not in the pool"] += 1
            continue
        code = (entry["rec"].get("code") or "").strip("\n")
        if not code.strip():
            counts["no python solution"] += 1
            continue
        answer = fenced(k["tasks"][0], entry["fn"])
        seen, n = {answer}, 0
        candidates = []
        for r in test_dropped.get(tid, []):
            try:
                task = surface.parse(r["spec"])
            except Exception:                                   # noqa: BLE001
                counts["unparsed test-dropped"] += 1
                continue
            candidates.append(("tests", task, None))
        for d in ref_dropped.get(tid, []):
            candidates.append(("reference", d["task"], d["reference"]))
        for kind, task, ref in candidates:
            if n >= max_per_problem:
                break
            failed = fenced(task, entry["fn"])
            if failed in seen:
                counts["duplicate"] += 1
                continue
            seen.add(failed)
            if kind == "tests":
                witnesses = spec_quality.witnesses(spec_first_rows.specification_of(task), entry)
            else:
                witnesses = reference_witness(ref)
            if not witnesses:
                counts["no witness"] += 1
                continue
            rows.append({"task_id": tid, "tag": "repair-trace", "name": None, "kernels_verified": 0, "undecided": [],
                         "source": f"spec-repair-{kind}", "prompt": spec_first.repair_question(entry, code, failed, witnesses),
                         "chosen": answer})
            counts[f"traces from {kind}"] += 1
            n += 1
        if n:
            counts["problems"] += 1
    return rows, dict(counts)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scored", type=Path, required=True)
    ap.add_argument("--strict-kept", type=Path, required=True)
    ap.add_argument("--strict-dropped", type=Path, required=True)
    ap.add_argument("--pool", choices=se.POOL_VERSIONS, default="v5")
    ap.add_argument("--max-per-problem", type=int, default=3)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    a = ap.parse_args(argv)
    load = lambda p: [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]  # noqa: E731
    rows, report = build(load(a.scored), load(a.strict_kept), load(a.strict_dropped), se.pool(a.pool), a.max_per_problem)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    report.update(rows=len(rows), output=str(a.out))
    a.report.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
