#!/usr/bin/env python3
"""Rebuild the registered full mixture before its row audits.

Reuse student_rows, graded_pool and spec_first_rows, as the recovered v5 pool
builders did. Source: https://github.com/trestoncuzzort/dawnr/blob/1994e06a/t/spec_first_rows.py
The historical input stays byte-for-byte at the start; added views are deduplicated.
The saved 33-question panel is fixed independently of this build.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, "t")
import graded_pool
import loop_dataset
import mbpp_dfy
import spec_experiment as se
import spec_first_rows
import student_rows
import surface
import student_row_families

ROOT = Path("t/out/v5-full-20261011")
ORIGINAL = Path("t/out/desktop-recovery-20261011/sft-student-teacher3.jsonl")
EXPECTED = "848fca29d9399ef91fcb867006e4ff42f60b53e9e2e084e4f1e93dae37811110"
PANEL = Path("t/out/v5-matched-20261011/v5/spec-heldout.jsonl")
PANEL_SHA = "effc2f4e586e0c4f7638a5a9a2b75515aaf7019de03ca819d46e5aa3d593ab24"


def read(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def key(row):
    return json.dumps([row["prompt"], row["chosen"]], sort_keys=True)


def kind(row):
    return row.get("kind") or row.get("source") or "unknown"


def write(path, rows):
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    if (ROOT / "raw-rows.jsonl").exists():
        raise SystemExit("refusing to overwrite assembled input")
    original = ORIGINAL.read_bytes()
    assert hashlib.sha256(original).hexdigest() == EXPECTED
    assert original.endswith(b"\n")
    assert hashlib.sha256(PANEL.read_bytes()).hexdigest() == PANEL_SHA
    base = read(ORIGINAL)
    assert len(base) == 5095
    paths = [Path("t/out/loop/sft-deepseek-" + name + ".jsonl") for name in ("nine", "b2", "b3")]
    fresh = [row for path in paths for row in read(path)]
    assert len(fresh) == 22
    mbpp_dfy.NL_DATA = ROOT / "reference-data"
    assert (mbpp_dfy.NL_DATA / "apps_raw_train.jsonl.gz").is_file(), "restore the APPS reference data first"
    pool = se.pool("v7")
    student_row_families.require_pool_coverage(base + fresh, pool)
    english = []
    for row in fresh:
        tid = int(row["task_id"])
        task = surface.parse(se.find_block(row["chosen"]))
        english.append({**row, "name": row.get("name", task["name"]),
                        "prompt": se.build_prompt(pool[tid], "s2"),
                        "chosen": loop_dataset.fence(graded_pool.answer_text(task, pool[tid]["fn"])),
                        "prompt_version": "s2"})
    write(ROOT / "new-english.jsonl", english)
    first, first_report = spec_first_rows.build(english, pool)
    write(ROOT / "new-spec-first.jsonl", first)
    given, generated_panel, given_report = student_rows.build(
        Path("t/out/loop/corpus-r12-headed.txt"), Path("t/out/loop/split-v5.json"),
        1338, [ORIGINAL, ROOT / "new-english.jsonl"])
    write(ROOT / "corpus-spec-rows.jsonl", given)
    # This is only a build diagnostic, never a replacement evaluation panel.
    write(ROOT / "generated-panel-diagnostic.jsonl", generated_panel)
    (ROOT / "spec-heldout.jsonl").write_bytes(PANEL.read_bytes())
    seen = {key(row) for row in base}
    contributions, appended, origins = {}, [], []
    for label, rows in (("corpus-spec", given), ("new-english", english), ("new-spec-first", first)):
        added, duplicates = [], []
        for row in rows:
            digest = key(row)
            if digest in seen:
                duplicates.append({"task_id": row.get("task_id"), "name": row.get("name"), "kind": kind(row)})
                continue
            seen.add(digest)
            origins.append({"row": len(base) + len(appended), "source": label,
                            "task_id": row.get("task_id"), "kind": kind(row)})
            appended.append(row)
            added.append(row)
        contributions[label] = {"input": len(rows), "added": len(added), "duplicates": duplicates,
                                "added_kinds": dict(Counter(kind(r) for r in added))}
    data = original + "".join(json.dumps(row, sort_keys=True) + "\n" for row in appended).encode()
    (ROOT / "raw-rows.jsonl").write_bytes(data)
    sources = [ORIGINAL, PANEL, *paths, Path("t/out/loop/corpus-r12-headed.txt"), Path("t/out/loop/split-v5.json"),
               *sorted(mbpp_dfy.NL_DATA.glob("*.jsonl.gz"))]
    record = {"sources": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
              "original_rows": len(base), "original_kinds": dict(Counter(kind(r) for r in base)),
              "original_distinct_prompt_answer_pairs": len({key(r) for r in base}),
              "raw_rows": len(base) + len(appended), "raw_sha256": hashlib.sha256(data).hexdigest(),
              "contributions": contributions, "appended_origins": origins,
              "student_rows_report": given_report, "spec_first_report": first_report,
              "fixed_panel_questions": len(read(PANEL)), "generated_panel_is_diagnostic_only": True}
    (ROOT / "build-inputs.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({k: record[k] for k in ("original_rows", "original_kinds", "raw_rows", "raw_sha256", "contributions")}))


if __name__ == "__main__":
    main()
