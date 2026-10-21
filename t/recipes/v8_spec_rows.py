#!/usr/bin/env python3
"""v8 rows: the base snapshot plus specification rows self-distilled from the student's own reference-checked
candidates on training problems (t/PREDICT-2026-10-21-v8-spec-rows.md).

    python3 t/recipes/v8_spec_rows.py --base ROWS.jsonl --kept t/out/spec-experiment/TAG/kept-specs.jsonl \\
        --out out/v8/v8-rows.jsonl --report out/v8/rows.json [--pool v5] [--keep-covered]

`--kept` is what `t/spec_first.py --reference-python --specs-only` writes for training problems: candidates kept
by the problem's own tests AND by the reference check (spec_first.reference_keeps: agreement with the problem's
solution on drawn inputs, 60% of mutated outputs rejected). Rows are built by spec_first_rows.build_from_specs in
the route's own words; problems that already have a specification row in the base are skipped unless
--keep-covered. STaR (arXiv:2203.14465) and V-STaR (arXiv:2402.06457) keep a model's own correct samples as
training data; here the correctness check is the reference check, never a model's judgement.

Sources: t/spec_first_rows.py (build_from_specs), t/recipes/v7_decomposed_rows.py (the snapshot and report shape),
STaR arXiv:2203.14465, V-STaR arXiv:2402.06457, SAFE arXiv:2410.15756.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import spec_experiment as se                                    # noqa: E402
import spec_first_rows                                          # noqa: E402


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=Path, required=True, help="the base training rows (jsonl)")
    ap.add_argument("--kept", type=Path, required=True, help="kept-specs.jsonl of a --reference-python stage-1 run")
    ap.add_argument("--pool", default="v5")
    ap.add_argument("--keep-covered", action="store_true", help="also add rows for problems the base already covers")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    a = ap.parse_args(argv)
    base = [json.loads(l) for l in a.base.read_text(encoding="utf-8").splitlines() if l.strip()]
    covered = {int(r["task_id"]) for r in base if r.get("source") == "spec" and r.get("task_id") is not None}
    kept = [json.loads(l) for l in a.kept.read_text(encoding="utf-8").splitlines() if l.strip()]
    pool = se.pool(a.pool)
    skip = set() if a.keep_covered else covered
    new, counts = spec_first_rows.build_from_specs(kept, pool, skip)
    for r in new:
        r["tag"] = "self-distilled-specs"
    seen = {json.dumps((r.get("prompt"), r.get("chosen")), sort_keys=True) for r in base}
    added = []
    for r in new:
        key = json.dumps((r.get("prompt"), r.get("chosen")), sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        added.append(r)
    rows = base + added
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    by_source = Counter(r.get("source") for r in added)
    report = {"base": {"path": str(a.base), "rows": len(base), "sha256": sha256(a.base),
                       "problems with a spec row": len(covered)},
              "kept": {"path": str(a.kept), "problems": len(kept), "sha256": sha256(a.kept)},
              "built": counts, "added": {"rows": len(added), "by source": dict(by_source),
                                         "problems": len({r["task_id"] for r in added})},
              "output": {"path": str(a.out), "rows": len(rows), "sha256": sha256(a.out)}}
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report["added"]), "->", report["output"]["rows"], "rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
