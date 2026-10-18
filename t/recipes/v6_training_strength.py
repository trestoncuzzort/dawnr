"""Audit a fixed sample of the preserved v6 training programs for specification gaps.

Uses the existing spec_strength scorer and student_rows textual normalization.
Prior art: https://github.com/trestoncuzzort/dawnr/blob/main/t/spec_strength.py
This is a bounded interpreter diagnostic, not a formal-proof or reference-correctness score.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import resource
import sys

ENGINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE))
import spec_experiment as se
import spec_strength
import student_rows
import surface

ROWS_SHA256 = "e14f766f06299d589d9a6e3293f6bf3e3f06ffac026433e2fdeff1c04294af80"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def memory_bound():
    cap = 1536 * 1024**2
    resource.setrlimit(resource.RLIMIT_AS, (cap, cap))


def measure(path, seconds):
    try:
        return spec_strength.score_one(path, seconds=seconds)
    except Exception as error:
        return {"file": path, "name": Path(path).stem,
                "status": "error:" + type(error).__name__, "detail": str(error)[:300],
                "strength": None, "changing": 0, "killed": 0, "survivors": [],
                "capped": False, "real_verdict": None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=128)
    parser.add_argument("--seconds", type=int, default=15)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--full", action="store_true", help="audit all unique training programs")
    parser.add_argument("--reuse", type=Path, help="reuse a complete diagnostic with identical scoring inputs")
    args = parser.parse_args(argv)
    assert (args.limit, args.seconds, args.jobs) == (128, 15, 2), "use the registered diagnostic settings"
    assert digest(args.rows) == ROWS_SHA256
    rows = [json.loads(line) for line in args.rows.read_text().splitlines() if line.strip()]
    assert len(rows) == 4189
    if args.out.exists():
        parser.error("use a fresh output directory; preserve previous diagnostics")
    args.out.mkdir(parents=True)
    tasks = args.out / "tasks"
    tasks.mkdir()
    programs, categories, parse_failures = {}, Counter(), []
    for index, row in enumerate(rows):
        block = se.find_block(row["chosen"])
        if not block:
            categories["no_t_block"] += 1
            continue
        try:
            task = surface.parse(block)
        except Exception as error:
            categories["parse_failure"] += 1
            parse_failures.append({"row": index, "error": type(error).__name__})
            continue
        if not task.get("body"):
            categories["empty_body"] += 1
            continue
        categories["program_row"] += 1
        key = hashlib.sha256(student_rows._normalised(task, body=True).encode()).hexdigest()
        entry = programs.setdefault(key, {"task": task, "rows": []})
        entry["rows"].append(index)
    selected = sorted(programs) if args.full else sorted(programs)[:args.limit]
    sources = sorted(ENGINE.glob("*.py")) + [Path(__file__)]
    protocol = {"dataset_sha256": ROWS_SHA256, "rows": len(rows), "categories": dict(categories),
                "parse_failures": parse_failures, "unique_programs": len(programs),
                "selection": ("all SHA-256 keys" if args.full else "first 128 SHA-256 keys")
                             + " after student_rows._normalised(task, body=True)",
                "seconds_per_task": args.seconds, "jobs": args.jobs, "worker_memory_mib": 1536,
                "selected": {}, "sources": {str(p.relative_to(ENGINE.parent)): digest(p) for p in sources}}
    for key in selected:
        path = tasks / (key + ".json")
        path.write_text(json.dumps(programs[key]["task"], sort_keys=True) + "\n")
        protocol["selected"][key] = {"name": programs[key]["task"]["name"],
                                     "source_rows": programs[key]["rows"], "task_sha256": digest(path)}
    reused = {}
    if args.reuse:
        old = json.loads((args.reuse / "protocol.json").read_text())
        old_summary = json.loads((args.reuse / "summary.json").read_text())
        assert digest(args.reuse / "protocol.json") == old_summary["protocol_sha256"]
        assert digest(args.reuse / "results.jsonl") == old_summary["results_sha256"]
        for key in ("dataset_sha256", "seconds_per_task", "jobs", "worker_memory_mib"):
            assert old[key] == protocol[key], "cached diagnostic settings differ"
        scorer_sources = lambda p: {k:v for k,v in p["sources"].items()
                                    if k != "t/recipes/v6_training_strength.py"}
        assert scorer_sources(old) == scorer_sources(protocol), "cached scoring code differs"
        previous = [json.loads(line) for line in (args.reuse / "results.jsonl").read_text().splitlines()]
        assert old_summary["completed"] == old_summary["selected"] == len(old["selected"]) == len(previous)
        assert {r["program_sha256"] for r in previous} == set(old["selected"])
        for result in previous:
            key = result["program_sha256"]
            if key not in protocol["selected"]:
                continue
            assert old["selected"][key] == protocol["selected"][key], "cached task differs"
            assert result["source_rows"] == programs[key]["rows"]
            reused[key] = {**result, "file": str(tasks / (key + ".json"))}
        protocol["reused_results"] = {"count": len(reused),
                                      "protocol_sha256": old_summary["protocol_sha256"],
                                      "results_sha256": old_summary["results_sha256"]}
    (args.out / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
    print(json.dumps({"unique_programs": len(programs), "selected": len(selected),
                      "categories": dict(categories)}), flush=True)
    results = list(reused.values())
    with (args.out / "results.jsonl").open("w") as stream, ProcessPoolExecutor(
            max_workers=args.jobs, initializer=memory_bound) as pool:
        for result in results:
            stream.write(json.dumps(result, sort_keys=True) + "\n")
        stream.flush()
        pending = {pool.submit(measure, str(tasks / (key + ".json")), args.seconds): key
                   for key in selected if key not in reused}
        for future in as_completed(pending):
            key = pending[future]
            result = future.result()
            result["program_sha256"] = key
            result["source_rows"] = programs[key]["rows"]
            stream.write(json.dumps(result, sort_keys=True) + "\n")
            stream.flush()
            results.append(result)
            print(f"{len(results)}/{len(selected)} {key[:12]} {result['status']} "
                  f"survivors={len(result['survivors'])}", flush=True)
    assert len(results) == len(selected)
    ok = [r for r in results if r["status"] == "ok"]
    weak = spec_strength.rank_weakest(results)
    summary = {"selected": len(selected), "completed": len(results),
               "statuses": dict(Counter(r["status"] for r in results)),
               "capped": sum(r["capped"] for r in results),
               "known_strength": sum(r["strength"] is not None for r in results),
               "programs_with_survivors": len(weak), "survivors": sum(len(r["survivors"]) for r in ok),
               "reused_programs": len(reused), "newly_measured_programs": len(results) - len(reused),
               "prediction_S1": bool(weak), "protocol_sha256": digest(args.out / "protocol.json"),
               "results_sha256": digest(args.out / "results.jsonl"),
               "scope": "Bounded interpreter diagnostic on training programs. Survivors require review; unknowns are not passes."}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (args.out / "worklist.json").write_text(json.dumps(weak, indent=2) + "\n")
    print(json.dumps(summary), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
