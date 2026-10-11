#!/usr/bin/env python3
"""Remove every known problem view when an audit refuses one training row.

Extends spec_panel.draw's document grouping to explicit problem identities:
https://github.com/trestoncuzzort/dawnr/blob/1994e06a/t/spec_panel.py
Problem identifiers use loop_filter.problem_id; unnamed rows stay independent.
This consumes findings on the SAME input bytes, before either audit filters rows.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import graded_pool
import loop_filter
import mbpp_dfy
import spec_experiment
import spec_panel


def identity(row):
    explicit = row.get("task_id")
    if explicit is not None:
        if type(explicit) is not int and not (isinstance(explicit, str) and explicit.isdecimal()):
            raise ValueError("invalid task_id")
        explicit = int(explicit)
        if explicit < 0:
            raise ValueError("negative task_id")
    inferred = loop_filter.problem_id(row.get("name"))
    if explicit is not None and inferred is not None and explicit != inferred:
        raise ValueError("task_id and qualified name disagree")
    tid = explicit if explicit is not None else inferred
    if tid is not None:
        return ("problem", tid)
    key = spec_panel.document_key(row)
    return ("document", key) if key != "n:" else None


def close(rows, rejected, allowed):
    """Return removals and a receipt; input indices are zero based and validated."""
    direct = set()
    for index in rejected:
        if type(index) is not int or not 0 <= index < len(rows):
            raise ValueError("finding has an invalid row index")
        direct.add(index)
    keys = [identity(row) for row in rows]
    split = {i for i, key in enumerate(keys)
             if key is not None and key[0] == "problem" and key[1] not in allowed}
    seeds = direct | split
    refused = {keys[i] for i in seeds if keys[i] is not None}
    gone = seeds | {i for i, key in enumerate(keys) if key is not None and key in refused}
    return gone, {"input_rows": len(rows), "audit_rows": sorted(direct),
                  "split_rows": sorted(split), "family_only_rows": sorted(gone - seeds),
                  "removed_rows": sorted(gone), "kept_rows": len(rows) - len(gone),
                  "refused_families": sorted(refused),
                  "anonymous_rows": sum(key is None for key in keys)}


def kind(row):
    return row.get("kind") or row.get("source") or "unknown"


def require_pool_coverage(rows, pool, required_ids=None):
    known = {key[1] for row in rows if (key := identity(row)) is not None and key[0] == "problem"}
    if required_ids is not None:
        known &= required_ids
    missing = sorted(known - set(pool))
    if missing:
        raise ValueError(f"reference pool is missing {len(missing)} identified training problems: {missing[:12]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rows", type=Path, required=True)
    ap.add_argument("--findings", type=Path, nargs="+", required=True)
    ap.add_argument("--input-sha256", required=True)
    ap.add_argument("--split", type=Path, required=True)
    ap.add_argument("--pool", default="v7")
    ap.add_argument("--nl-data", type=Path, help="isolated recovered reference data; leaves other evaluations unchanged")
    ap.add_argument("--keep", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    a = ap.parse_args()
    data = a.rows.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != a.input_sha256:
        raise SystemExit("row input differs from the audited input")
    lines = [line for line in data.splitlines(keepends=True) if line.strip()]
    rows = [json.loads(line) for line in lines]
    reports = [json.loads(p.read_text()) for p in a.findings]
    for report in reports:
        if "rows" in report and report["rows"] != len(rows):
            raise SystemExit("audit row count differs from input")
    indices = [finding["row"] for report in reports for finding in report["findings"]]
    if a.nl_data is not None:
        mbpp_dfy.NL_DATA = a.nl_data
    pool = spec_experiment.pool(a.pool)
    declared = {int(i): None for i in json.loads(a.split.read_text())["train_ids"]}
    allowed = graded_pool.training_ids(a.split, declared)
    require_pool_coverage(rows, pool, allowed)
    gone, record = close(rows, indices, allowed)
    kept = b"".join(line for i, line in enumerate(lines) if i not in gone)
    a.keep.write_bytes(kept)
    record.update(input_sha256=digest, output_sha256=hashlib.sha256(kept).hexdigest(),
                  input_kinds=dict(Counter(kind(r) for r in rows)),
                  kept_kinds=dict(Counter(kind(r) for i, r in enumerate(rows) if i not in gone)),
                  reference_pool_problems=len(pool),
                  reference_data_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                         for p in mbpp_dfy.NL_DATA.glob("*.jsonl.gz")},
                  findings_sha256={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in a.findings})
    a.report.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({k: record[k] for k in ("input_rows", "kept_rows", "kept_kinds", "output_sha256")}))


if __name__ == "__main__":
    main()
