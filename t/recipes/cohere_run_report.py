#!/usr/bin/env python3
"""Collect a downloaded teacher run for training and a further pass over unsolved problems.

Run after teacher_outputs.sh has opened the completed run's artifacts. Read only the strict-kept
files, reconcile their counts with the strict-check reports, and keep the resulting rows private.
The report distinguishes problems the route accounted for from ones a budget stop never reached.
Prior ledgers are explicit so the desktop pilots and GitHub jobs share one grant total.

    python3 t/recipes/cohere_run_report.py --run out/r61/teacher-runs/RUN --expected-jobs 10 \\
        --ids out/r61/cohere-a-ids-0.txt [--ids ...] --prior-ledger PILOT-LEDGER.jsonl \\
        --out out/r61/pass-one

Sources: teacher_outputs.sh (artifact layout); v9_strict_specs.py (strict reports and kept rows);
https://docs.cohere.com/reference/chat (billed units, recorded by cohere_proxy.py).
"""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from v9_strict_specs import strict_keeps


def jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def collect(run: Path, ids: list[str], expected_jobs: int, prior_ledgers: list[Path],
            ceiling: Decimal = Decimal("950")) -> tuple[dict, list[dict], list[str]]:
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("the planned problem lists must be nonempty and disjoint")
    planned = set(ids)
    ledgers = sorted(run.glob("teacher-*/out/r61/*-ledger.jsonl"))
    if expected_jobs < 1 or len(ledgers) != expected_jobs:
        raise ValueError(f"expected {expected_jobs} job ledgers, found {len(ledgers)}; fetch all completed jobs first")
    all_ledgers = prior_ledgers + ledgers
    if len({p.resolve() for p in all_ledgers}) != len(all_ledgers):
        raise ValueError("the same ledger was supplied twice")
    spent, prior_spent, calls = Decimal(0), Decimal(0), 0
    ledger_receipts = []
    for path in all_ledgers:
        records = jsonl(path)
        costs = [Decimal(str(row["usd"])) for row in records]
        if any(not value.is_finite() or value < 0 for value in costs):
            raise ValueError(f"invalid charge in {path}")
        total = sum(costs, Decimal(0))
        if path in prior_ledgers:
            prior_spent += total
        else:
            spent += total
            calls += len(records)
        ledger_receipts.append({"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                "calls": len(records), "usd": str(total)})

    kept, accounted, errors = {}, set(), Counter()
    for ledger in ledgers:
        series = ledger.name.removesuffix("-ledger.jsonl")
        directory = ledger.parent
        raw = directory / f"{series}-kept.jsonl"
        report_path = directory / f"{series}-strict.json"
        strict = directory / f"{series}-strict-kept.jsonl"
        if not raw.is_file():
            raise ValueError(f"missing route collection for {series}; do not treat a failed job as zero yield")
        rows = []
        if report_path.is_file():
            report = json.loads(report_path.read_text())
            if report["pool"] != "v5" or report["draws"] < 1000 or report["floor"] < 0.9:
                raise ValueError(f"{series} was not checked at the registered strict floor")
            rows = jsonl(strict)
            if report["problems_kept"] != len(rows) or report["candidates_kept"] != sum(len(r["tasks"]) for r in rows):
                raise ValueError(f"strict output counts differ from the report for {series}")
        elif raw.stat().st_size:
            raise ValueError(f"strict check missing for {series}")
        for row in rows:
            tid = str(row["task_id"])
            if tid not in planned:
                raise ValueError(f"strict output contains unplanned problem {tid}")
            if tid in kept:
                raise ValueError(f"problem {tid} occurs in more than one job; the planned lists must be disjoint")
            if not row["tasks"] or len(row.get("reference", [])) != len(row["tasks"]) or not all(
                    strict_keeps(ref, 0.9) for ref in row["reference"]):
                raise ValueError(f"problem {tid} lacks strict evidence for every kept candidate")
            kept[tid] = row
        artifact = ledger.parents[2]
        for summary in artifact.glob(f"t/out/spec-experiment/{series}-tc*/spec_first.json"):
            data = json.loads(summary.read_text())
            chunk_ids = set(data["per_problem"])
            if data["problems"] != len(chunk_ids) or not chunk_ids <= planned or accounted & chunk_ids:
                raise ValueError(f"inconsistent problem accounting in {summary}")
            accounted.update(chunk_ids)
        proxy = directory / series / "proxy.jsonl"
        if proxy.is_file():
            for record in jsonl(proxy):
                if not record.get("ok"):
                    error = record.get("error", "unknown")
                    kind = "ceiling" if error == "ceiling" else "other"
                    if error.startswith("HTTP "):
                        kind = "HTTP " + error.split()[1].rstrip(":")
                    errors[kind] += 1
    if not set(kept) <= accounted:
        raise ValueError("kept outputs lack the route's problem accounting")
    remaining = [tid for tid in ids if tid not in kept]
    total = prior_spent + spent
    summary = {"planned_problems": len(ids), "accounted_problems": len(accounted),
               "not_accounted_problems": len(planned - accounted), "strict_kept_problems": len(kept),
               "strict_kept_candidates": sum(len(row["tasks"]) for row in kept.values()),
               "remaining_problems": len(remaining), "calls": calls, "run_usd": str(spent),
               "prior_usd": str(prior_spent), "total_usd": str(total), "grant_stop_usd": str(ceiling),
               "unallocated_usd": str(max(Decimal(0), ceiling - total)), "proxy_errors": dict(errors),
               "strict_kept_problems_per_100_usd": round(len(kept) * 100 / float(spent), 2) if spent else None,
               "ledgers": ledger_receipts}
    return summary, [kept[tid] for tid in ids if tid in kept], remaining


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--ids", type=Path, action="append", required=True)
    parser.add_argument("--expected-jobs", type=int, required=True)
    parser.add_argument("--prior-ledger", type=Path, action="append", default=[])
    parser.add_argument("--ceiling", type=Decimal, default=Decimal("950"))
    parser.add_argument("--out", type=Path, required=True, help="private output directory, outside tracked data")
    args = parser.parse_args(argv)
    if not args.ceiling.is_finite() or args.ceiling <= 0:
        parser.error("ceiling must be finite and positive")
    ids = [tid for path in args.ids for tid in path.read_text().split()]
    summary, rows, remaining = collect(args.run, ids, args.expected_jobs, args.prior_ledger, args.ceiling)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (args.out / "strict-kept.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    (args.out / "remaining.txt").write_text("".join(tid + "\n" for tid in remaining))
    print(json.dumps({key: value for key, value in summary.items() if key != "ledgers"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
