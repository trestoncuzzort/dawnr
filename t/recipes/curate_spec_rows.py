#!/usr/bin/env python3
"""Statically check only the additions to a frozen training baseline, then audit the whole result.

Sources: prepare_release_rows.py (pinned inputs and whole-dataset audit),
spec_first.py:accept (checked header promotion), and spec_contract.py.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from prepare_release_rows import checked_file, digest, read_rows
from spec_contract import checked_contract

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "t"))
import loop_dataset
import spec_experiment as se
import surface


def row_hash(row: dict) -> str:
    return hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()


def filter_additions(base: list[dict], candidate: list[dict]) -> tuple[list[dict], dict]:
    if len(candidate) < len(base) or candidate[:len(base)] != base:
        raise ValueError("candidate does not preserve the frozen baseline")
    kept, actions, counts, tags = list(base), [], Counter(), {}
    row_key = lambda row: json.dumps((row.get("prompt"), row.get("chosen")), sort_keys=True)
    seen = {row_key(row) for row in base}
    for index, row in enumerate(candidate[len(base):], len(base)):
        if row.get("source") not in ("spec", "python"):
            raise ValueError("an added row has no recognized specification/reference source")
        counts["input_additions"] += 1
        tag = row.get("tag")
        if not isinstance(tag, str) or not tag:
            raise ValueError("an added row has no provenance tag")
        source = tags.setdefault(tag, Counter())
        source["input"] += 1
        record = {"input_index": index, "task_id": row.get("task_id"), "tag": tag,
                  "original_row_sha256": row_hash(row)}
        if row["source"] == "python":
            if row_key(row) in seen:
                raise ValueError("the archived reference addition was already in the frozen prefix")
            seen.add(row_key(row))
            kept.append(row)
            counts["reference_rows_retained"] += 1
            source["retained"] += 1
            continue
        try:
            block = se.find_block(row["chosen"])
            if block is None:
                raise ValueError("specification row has no t block")
            task = surface.parse(block)
            checked, promoted = checked_contract(task)
        except (ValueError, KeyError, TypeError, RecursionError, surface.SurfaceError) as error:
            counts["invalid_specifications_dropped"] += 1
            source["dropped"] += 1
            actions.append({**record, "action": "dropped", "reason": str(error)})
            continue
        result = row
        if promoted:
            result = deepcopy(row)
            result["chosen"] = loop_dataset.fence(surface.print_task(checked).strip())
            counts["header_promotion_candidates"] += 1
        if row_key(result) in seen:
            counts["duplicates_dropped"] += 1
            source["duplicate"] += 1
            actions.append({**record, "action": "duplicate_after_normalization"})
            continue
        seen.add(row_key(result))
        if promoted:
            counts["headers_promoted"] += 1
            source["promoted"] += 1
            actions.append({**record, "action": "promoted_header", "new_row_sha256": row_hash(result)})
        else:
            counts["specifications_retained_unchanged"] += 1
        kept.append(result)
        counts["specifications_retained"] += 1
        source["retained"] += 1
    # Recheck the serialized answers that will actually train, including promoted headers.
    for row in kept[len(base):]:
        if row["source"] == "spec":
            _task, promoted = checked_contract(surface.parse(se.find_block(row["chosen"])))
            if promoted:
                raise ValueError("the output still needs a header promotion")
    return kept, {"counts": dict(counts), "sources": [{"tag": k, **dict(v)} for k, v in tags.items()],
                  "row_actions": actions}


def curate(manifest_path: Path, output: Path, jobs: int) -> dict:
    manifest = json.loads(manifest_path.read_text())
    root = manifest_path.parent
    base_path = checked_file(root, manifest["base"])
    candidate_path = checked_file(root, manifest["candidate"])
    base, candidate = read_rows(base_path), read_rows(candidate_path)
    if len(base) != manifest["base"]["rows"] or len(candidate) != manifest["candidate"]["rows"]:
        raise ValueError("pinned row count changed")
    if output.exists() or jobs < 1:
        raise ValueError("use a fresh output directory and positive job count")
    rows, static = filter_additions(base, candidate)
    output.mkdir(parents=True)
    final = output / "training-rows.jsonl"
    final.write_text("".join(json.dumps(row) + "\n" for row in rows))
    static_path = output / "static-check.json"
    static_path.write_text(json.dumps(static, indent=2) + "\n")
    audit_path = output / "audit.json"
    with (output / "audit.log").open("w") as log:
        subprocess.run([sys.executable, str(REPO / "t/heldout_audit.py"), "--rows", str(final), "--panels",
                        "--refuse-gpl", "--jobs", str(jobs), "--json", str(audit_path)],
                       cwd=REPO, stdout=log, stderr=subprocess.STDOUT, check=True)
    audit = json.loads(audit_path.read_text())
    if audit["flagged"] or audit["findings"] or audit["rows"] != len(rows):
        raise ValueError("the full resulting dataset did not pass its audit")
    record = {"label": manifest["label"], "purpose": "static curation of additions to the frozen baseline",
              "input_manifest_sha256": digest(manifest_path), "base": manifest["base"],
              "candidate": manifest["candidate"], "sources": static["sources"],
              "static": {"counts": static["counts"], "sha256": digest(static_path),
                         "all_retained_added_specifications_valid": True, "baseline_checked_statically": False},
              "output": {"filename": final.name, "rows": len(rows), "sha256": digest(final)},
              "audit": {"rows": audit["rows"], "flagged": 0, "unparsed": audit["unparsed"],
                        "sha256": digest(audit_path), "panels": True, "refuse_gpl": True},
              "code_sha256": {name: digest(REPO / name) for name in
                              ("t/recipes/curate_spec_rows.py", "t/recipes/spec_contract.py",
                               "t/recipes/prepare_release_rows.py", "t/check_wf.py", "t/surface.py",
                               "t/loop_dataset.py", "t/spec_experiment.py", "t/heldout_audit.py")}}
    (output / "rows-manifest.json").write_text(json.dumps(record, indent=2) + "\n")
    (output / "COMPLETE").write_text(record["output"]["sha256"] + "\n")
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args(argv)
    record = curate(args.manifest.resolve(), args.out.resolve(), args.jobs)
    print(json.dumps({"output": record["output"], "audit": record["audit"], "static": record["static"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
