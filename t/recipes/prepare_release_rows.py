#!/usr/bin/env python3
"""Build private release-candidate rows from pinned inputs and strictly checked teacher outputs.

Apply sources in manifest order using v8_spec_rows' existing rule: skip problems already covered by
the base or an earlier source. Preserve each source's explicit tag. A completed receipt requires the
whole resulting dataset to pass heldout_audit --panels --refuse-gpl; this script never trains a model.
Sources may provide pinned kept/report files, or raw_kept to run the existing strict check first.

Sources: v8_spec_rows.py; v9_strict_specs.py; t/heldout_audit.py;
https://docs.cohere.com/reference/chat (the teacher named in the row provenance).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import v8_spec_rows
from v9_strict_specs import strict_keeps

REPO = Path(__file__).resolve().parents[2]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def checked_file(root: Path, entry: dict) -> Path:
    relative = Path(entry["path"])
    path = (root / relative).resolve()
    if relative.is_absolute() or not path.is_relative_to(root.resolve()):
        raise ValueError("input paths must stay within the private input directory")
    if digest(path) != entry["sha256"]:
        raise ValueError(f"input digest differs: {relative}")
    return path


def validate_strict(kept: Path, report_path: Path) -> None:
    report = json.loads(report_path.read_text())
    rows = read_rows(kept)
    if report["pool"] != "v5" or report["draws"] < 1000 or report["floor"] < 0.9:
        raise ValueError("teacher source was not checked at the registered strict floor")
    if report["problems_kept"] != len(rows) or report["candidates_kept"] != sum(len(row["tasks"]) for row in rows):
        raise ValueError("teacher output differs from its strict report")
    for row in rows:
        if not row["tasks"] or len(row.get("reference", [])) != len(row["tasks"]) or not all(
                strict_keeps(reference, 0.9) for reference in row["reference"]):
            raise ValueError("every teacher candidate must carry passing strict evidence")


def validate_inputs(manifest_path: Path) -> tuple[dict, Path, list[tuple]]:
    manifest = json.loads(manifest_path.read_text())
    root = manifest_path.parent
    base = checked_file(root, manifest["base"])
    if len(read_rows(base)) != manifest["base"]["rows"]:
        raise ValueError("base row count differs from the manifest")
    if not manifest["sources"]:
        raise ValueError("no teacher sources supplied")
    sources = []
    for source in manifest["sources"]:
        if not isinstance(source.get("tag"), str) or not source["tag"].strip():
            raise ValueError("each teacher source needs an explicit provenance tag")
        if "raw_kept" in source:
            if "kept" in source or "report" in source:
                raise ValueError("supply either raw candidates or checked candidates, not both")
            raw = checked_file(root, source["raw_kept"])
            sources.append((source, raw))
            continue
        kept = checked_file(root, source["kept"])
        report_path = checked_file(root, source["report"])
        validate_strict(kept, report_path)
        sources.append((source, kept))
    return manifest, base, sources


def build(manifest_path: Path, output: Path, jobs: int) -> dict:
    manifest, base, sources = validate_inputs(manifest_path)
    if output.exists():
        raise ValueError("use a fresh output directory; keep previous build evidence")
    if jobs < 1:
        raise ValueError("jobs must be positive")
    output.mkdir(parents=True)
    current, additions = base, []
    for index, (source, kept) in enumerate(sources):
        if "raw_kept" in source:
            import graded_pool
            allowed = graded_pool.training_ids(REPO / "t/out/loop/split-v5.json", v8_spec_rows.se.pool("v5"))
            if any(int(row["task_id"]) not in allowed for row in read_rows(kept)):
                raise ValueError("raw teacher candidates must be on the permitted training side")
            strict = output / f"source-{index}-strict-kept.jsonl"
            strict_report = output / f"source-{index}-strict.json"
            command = [sys.executable, str(REPO / "t/recipes/v9_strict_specs.py"), "--kept", str(kept),
                       "--pool", "v5", "--draws", "1000", "--floor", "0.9", "--jobs", str(jobs),
                       "--out", str(strict), "--report", str(strict_report),
                       "--dropped", str(output / f"source-{index}-strict-dropped.jsonl")]
            with (output / f"source-{index}-strict.log").open("w") as log:
                subprocess.run(command, cwd=REPO, stdout=log, stderr=subprocess.STDOUT, check=True)
            validate_strict(strict, strict_report)
            kept = strict
        stage = output / f"stage-{index}.jsonl"
        report_path = output / f"stage-{index}.json"
        v8_spec_rows.main(["--base", str(current), "--kept", str(kept), "--pool", "v5",
                          "--tag", source["tag"], "--out", str(stage), "--report", str(report_path)])
        report = json.loads(report_path.read_text())
        additions.append({"tag": source["tag"], "kept_sha256": digest(kept),
                          **({"model_identity": source["model_identity"]} if "model_identity" in source else {}),
                          **({"raw_kept_sha256": source["raw_kept"]["sha256"]} if "raw_kept" in source else {}),
                          **report["added"]})
        current = stage
    final = output / "training-rows.jsonl"
    shutil.copyfile(current, final)
    audit_path = output / "audit.json"
    command = [sys.executable, str(REPO / "t/heldout_audit.py"), "--rows", str(final), "--panels",
               "--refuse-gpl", "--jobs", str(jobs), "--json", str(audit_path)]
    with (output / "audit.log").open("w") as log:
        subprocess.run(command, cwd=REPO, stdout=log, stderr=subprocess.STDOUT, check=True)
    audit = json.loads(audit_path.read_text())
    rows = read_rows(final)
    if audit["flagged"] or audit["findings"] or audit["rows"] != len(rows):
        raise ValueError("final training-row audit did not pass completely")
    record = {"label": manifest["label"], "purpose": manifest.get("purpose", "candidate-data-preparation"),
              "input_manifest_sha256": digest(manifest_path),
              "base": manifest["base"], "sources": additions,
              "output": {"filename": final.name, "rows": len(rows), "sha256": digest(final)},
              "audit": {"rows": audit["rows"], "flagged": 0, "unparsed": audit["unparsed"],
                        "sha256": digest(audit_path), "panels": True, "refuse_gpl": True},
              "code_sha256": {name: digest(REPO / name) for name in
                              ("t/recipes/prepare_release_rows.py", "t/recipes/v8_spec_rows.py",
                               "t/recipes/v9_strict_specs.py", "t/spec_first_rows.py", "t/heldout_audit.py")}}
    (output / "rows-manifest.json").write_text(json.dumps(record, indent=2) + "\n")
    (output / "COMPLETE").write_text(record["output"]["sha256"] + "\n")
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args(argv)
    record = build(args.manifest.resolve(), args.out.resolve(), args.jobs)
    print(json.dumps({"output": record["output"], "audit": record["audit"], "sources": record["sources"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
