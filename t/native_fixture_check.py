#!/usr/bin/env python3
"""Rerun the control suite of every published native case and compare it with what was published.

    python3 t/native_fixture_check.py --fixtures t/native_fixtures --cbmc /path/to/cbmc --out /tmp/fixtures

A change to the gate must not move a published result. For each directory holding a case.json,
the newest suite-*.json beside it is the published result: verdict, unit hash, property count
and confirmed witnesses of every row have to come back the same. A case with no published
suite is run and reported, and counts as neither a pass nor a failure. Exit 0 only when
nothing moved and at least one published row was compared.

Sources: the expected verdict per control is local precedent (native_case.suite). Keeping a
result beside the task it came from follows sv-comp.sosy-lab.org/2025/rules.php.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_case as cases
import native_sample as sampler

FIELDS = ("variant", "unwind", "verdict", "unit_sha256", "properties", "confirmed_witnesses")


def compare(published: dict, summary: dict, same_solver: bool = True) -> list[str]:
    """Every difference between a published suite and a new run of it, in words. Another solver can find
    other witnesses for the same property, so then a confirmed witness only has to exist in both or neither."""
    before, after = published.get("rows", []), summary.get("rows", [])
    moved = []
    if len(before) != len(after):
        moved.append(f"{len(before)} published rows, {len(after)} now")
    for index, (old, new) in enumerate(zip(before, after)):
        for field in FIELDS:
            first, second = old.get(field), new.get(field)
            if field == "confirmed_witnesses" and not same_solver:
                first, second = bool(first), bool(second)
            if first != second:
                moved.append(f"row {index} {old.get('variant')}: {field} was {old.get(field)!r}, now {new.get(field)!r}")
    return moved


def model_size(root: Path, out: Path, cbmc: str, unwind: int, bounds: dict, timeout: float, memory_limit_mb: int, solver: str) -> dict:
    """SAT variables and clauses of the fixed variant under the given bounds, and how long it took."""
    case = cases.load(root)
    unit, _, _ = cases.build_unit(case, "fixed", root)
    out.mkdir(parents=True, exist_ok=False)
    (out / "unit.c").write_text(unit)
    stops, defines = cases.stops_unit(case.get("allowed_stops", []), unit)
    (out / cases.STOP_FILE).write_text(stops)
    args = ["unit.c", cases.STOP_FILE, *defines, "--function", "harness", cases.MACHINES[case["machine"]][0], "--little-endian",
            *cases.native.KEEP_SELF_LOOPS, "--sat-solver", solver, "--unwind", str(unwind), *(["--unwindset", cases.render_bounds(bounds)] if bounds else []),
            "--json-ui", "--verbosity", "8",
            *cases.CHECKS, *case.get("checks", []), "--unwinding-assertions"]
    run = cases.native.run_process([cbmc, *args], out, timeout, memory_limit_mb)
    sizes = re.findall(r"(\d+) variables, (\d+) clauses", run["stdout"])
    return {"state": run["state"], "exit": run["exit"], "seconds": run["seconds"],
            "variables": max((int(pair[0]) for pair in sizes), default=None), "clauses": max((int(pair[1]) for pair in sizes), default=None)}


def tune(root: Path, out: Path, args) -> dict:
    """Find per-loop bounds, compare the model with the published global bound, and run the suite with them in a copy."""
    published = cases.load(root)
    found = cases.find_bounds(root, out / "bounds", args.cbmc, args.timeout, args.memory_limit_mb, solver=args.solver)
    entry = {"case": root.name, "published_unwind": published.get("unwind", 4), "published_loops": published["loops"], "found": found["found"],
             "reason": found.get("reason"), "attempts": len(found["attempts"]), "search_seconds": round(sum(item["seconds"] for item in found["attempts"]), 2),
             "unwindset": found.get("unwindset"), "other_failures": found.get("other_failures")}
    if not found["found"]:
        return entry
    entry["largest_bound"] = max([found["unwind"], *found["unwindset"].values()])
    entry["model_published"] = model_size(root, out / "size-published", args.cbmc, published.get("unwind", 4), {}, args.timeout, args.memory_limit_mb, args.solver)
    entry["model_found"] = model_size(root, out / "size-found", args.cbmc, found["unwind"], found["unwindset"], args.timeout, args.memory_limit_mb, args.solver)
    copy = out / "case"
    shutil.copytree(root, copy)
    case = json.loads((copy / "case.json").read_text())
    # A loop the search no longer sees cannot be demanded, and the control still needs one when the case had one.
    case.update(unwind=found["unwind"], unwindset=found["unwindset"], loops=min(published["loops"], found["loops"]))
    (copy / "case.json").write_text(json.dumps(case, indent=2) + "\n")
    summary = cases.suite(copy, out / "suite", args.cbmc, args.timeout, args.compiler, args.memory_limit_mb, args.solver)
    entry["suite_ok"] = summary["ok"]
    entry["rows"] = [{key: row.get(key) for key in ("variant", "unwind", "verdict", "properties", "confirmed_witnesses", "seconds")} for row in summary["rows"]]
    return entry


def original_formula(root: Path, out: Path, args) -> dict:
    """What a solver says about the formula of the original. It has to have a solution: if it were proved to have
    none, the exported formula would not carry the failing property, and no certificate of it would mean anything."""
    case = cases.load(root)
    unit, _, _ = cases.build_unit(case, "original", root)
    out.mkdir(parents=True, exist_ok=False)
    (out / "unit.c").write_text(unit)
    stops, defines = cases.stops_unit(case.get("allowed_stops", []), unit)
    (out / cases.STOP_FILE).write_text(stops)
    formula = ["unit.c", cases.STOP_FILE, *defines, "--function", "harness", cases.MACHINES[case["machine"]][0], "--little-endian", *cases.native.KEEP_SELF_LOOPS,
               "--unwind", str(case.get("unwind", 4)), *(["--unwindset", cases.render_bounds(case["unwindset"])] if case.get("unwindset") else []),
               *cases.CHECKS, *case.get("checks", []), "--unwinding-assertions"]
    report = cases.certify(args.cbmc, formula, out, args.cadical, args.lrat_check, args.timeout, args.memory_limit_mb)
    for name in ("formula.cnf", "proof.lrat"):  # up to gigabytes, and nothing to read once the status is known
        (out / name).unlink(missing_ok=True)
    return {key: report.get(key) for key in ("status", "variables", "clauses")} | {"solve_seconds": report.get("solve", {}).get("seconds")}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fixtures", type=Path, default=Path(__file__).resolve().parent / "native_fixtures")
    parser.add_argument("--out", type=Path, required=True, help="new artifact directory; existing directories are refused")
    parser.add_argument("--cbmc", default="cbmc")
    parser.add_argument("--compiler", default="gcc")
    parser.add_argument("--timeout", type=float, default=3000)
    parser.add_argument("--memory-limit-mb", type=int, default=cases.DEFAULT_MEMORY_MB)
    parser.add_argument("--case", action="append", default=[], help="only this case directory name; may be repeated")
    parser.add_argument("--tune", action="store_true", help="search per-loop bounds for each case and run its suite with them, in a copy")
    parser.add_argument("--solver", choices=cases.SOLVERS, default=cases.DEFAULT_SOLVER, help="the published suites used minisat2")
    parser.add_argument("--cadical", help="with --lrat-check: certify each complete verdict, and check the formula of each original")
    parser.add_argument("--lrat-check", dest="lrat_check")
    parser.add_argument("--sample", type=int, default=0, help="also run each fixed variant natively over this many draws (native_sample.py)")
    args = parser.parse_args(argv)
    if bool(args.cadical) != bool(args.lrat_check):
        parser.error("--cadical and --lrat-check go together")
    certify_with = (args.cadical, args.lrat_check) if args.cadical else None
    args.out.mkdir(parents=True, exist_ok=False)
    report = []
    if args.tune:
        for root in sorted(path for path in args.fixtures.iterdir() if (path / "case.json").exists()):
            if args.case and root.name not in args.case:
                continue
            (args.out / root.name).mkdir()
            entry = tune(root, args.out / root.name, args)
            report.append(entry)
            print(json.dumps({key: value for key, value in entry.items() if key != "rows"}), flush=True)
        (args.out / "tune.json").write_text(json.dumps({"format": cases.FORMAT + "-tune", "report": report}, indent=2, sort_keys=True) + "\n")
        return 0 if report and all(entry.get("suite_ok") for entry in report) else 1
    for root in sorted(path for path in args.fixtures.iterdir() if (path / "case.json").exists()):
        if args.case and root.name not in args.case:
            continue
        published = sorted(root.glob("suite-*.json"))
        start = time.monotonic()
        try:
            summary = cases.suite(root, args.out / root.name, args.cbmc, args.timeout, args.compiler, args.memory_limit_mb, args.solver, certify_with)
        except (OSError, ValueError, KeyError, TypeError) as error:
            summary = {"rows": [], "ok": False, "error": str(error)}
        entry = {"case": root.name, "seconds": round(time.monotonic() - start, 1), "ok": summary.get("ok"), "error": summary.get("error"),
                 "rows": [{key: row.get(key) for key in (*FIELDS, "seconds", "certificate") if key in row} for row in summary["rows"]],
                 "peak_rss_mb": summary.get("peak_rss_mb"), "published": published[-1].name if published else None}
        entry["moved"] = compare(json.loads(published[-1].read_text()), summary, args.solver == "minisat2") if published else []
        if certify_with:
            entry["original_formula"] = original_formula(root, args.out / root.name / "original-formula", args)
            entry["certificates"] = [row["certificate"]["status"] for row in entry["rows"] if "certificate" in row]
        if args.sample:
            result = sampler.sample(root, "fixed", args.out / root.name / "native-sample", args.sample, compiler=args.compiler, timeout=args.timeout)
            entry["sample"] = {key: result.get(key) for key in ("status", "draws", "reached_the_end", "rejected", "failed_assertions", "failed_properties", "seconds", "report")}
        report.append(entry)
        print(json.dumps({key: entry[key] for key in ("case", "seconds", "ok", "published", "moved", "error", "peak_rss_mb", "certificates", "original_formula", "sample") if key in entry}), flush=True)
    compared = sum(len(entry["rows"]) for entry in report if entry["published"])
    moved = sum(len(entry["moved"]) for entry in report)
    failed = sum(not entry["ok"] for entry in report)
    result = {"format": cases.FORMAT + "-fixture-check", "cases": len(report), "rows_compared": compared, "moved": moved, "suites_failed": failed,
              "memory_limit_mb": args.memory_limit_mb, "solver": args.solver, "report": report}
    unproved = 0
    if certify_with:
        # Every original has to have a solution, and every fix a checked proof or no formula at all.
        unproved = (sum(entry["original_formula"]["status"] != "refuted" for entry in report)
                    + sum(status not in ("verified", "no_formula") for entry in report for status in entry["certificates"]))
        result["certificate_problems"] = unproved
    disagreements = 0
    if args.sample:
        # A fix the model calls complete, and the real code does not agree with: a defect in a model, or in the case.
        disagreements = sum(entry["sample"]["status"] != "no_failure" for entry in report)
        result["sample_problems"] = disagreements
    (args.out / "fixture-check.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in ("cases", "rows_compared", "moved", "suites_failed", "certificate_problems", "sample_problems") if key in result}))
    return 0 if compared and not moved and not failed and not unproved and not disagreements else 1


if __name__ == "__main__":
    raise SystemExit(main())
