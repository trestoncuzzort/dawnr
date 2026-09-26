#!/usr/bin/env python3
"""t/negatives_from_spec_disagreements.py -- preference pairs against the recited attractors (2026-09-25).

A clean answer that DISAGREES with its problem under the specification check
(t/spec_check.py: the model's `ensures` evaluated against the problem's own
reference solution on random draws; t/out/spec-disagree.json holds the verdicts
and the programs) is a program all seven kernels verified, with a sabotaged twin
refuted, that computes the wrong function for problem P. That is the failure
locallm makes 59 to 204 times a round (internal/RESEARCH-NEXT-2026-09-20.md),
and 34 to 57 percent of those are corpus programs recited for the wrong problem
(internal/research/r12-2026-09-21/data-growth-lit.md, recommendation 5).

This builds pairs for locallm's continuation trainer: for each disagreeing answer
whose problem P is on the training side, {task_id, prompt, chosen, rejected,
provenance} where prompt is the Problem/Signature head the corpus builder writes
for P (loop_locallm.problem_head, so the pair and the corpus document are the
same bytes for the positive), chosen is a verified, spec-AGREEING positive for P
from a pool file (an SFT jsonl built under loop_dataset.positive_rejection) and
rejected is the disagreeing program. The pair shape -- chosen passes the
checker, rejected is a plausible program that fails it, same prompt -- is
CodeDPO's (arXiv:2410.05605, arxiv.org/html/2410.05605) with the mutual
self-validation replaced by the project's own oracle, and Iterative RPO's
(arXiv:2404.19733), whose winners are judged by an external checker.

Every candidate goes through the r12 gates and a refusal is NAMED, never a
silent drop: a held-out id under any alias (loop_filter.problem_id), the
same-task exclusions (t/decontamination-2026-09-21.json), the dev split
(t/r12-dev-ids.json), a pool other than the split's, a program whose hash no
longer matches its verdict, a positive that no verdict row says agrees. A pool
file positive that a verdict row says DISAGREES is a contradiction between the
inputs and stops the build. Measured on 2026-09-25 against sft-r8 and the
spec-disagree.json of 2026-09-21: 81 disagreeing rows, 74 name held-out ids,
4 are pool v3, 3 pairs (t/NEGATIVES-2026-09-25.md).

    python3 t/negatives_from_spec_disagreements.py --split t/out/loop/split-v5.json \\
        --pool-file t/out/loop/sft-r8.jsonl --out t/out/loop/pairs-negatives-2026-09-25.jsonl \\
        --report t/out/loop/NEGATIVES-report-2026-09-25.md
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

T = Path(__file__).resolve().parent
sys.path.insert(0, str(T))

import loop_filter                                              # noqa: E402
import loop_locallm                                             # noqa: E402
import spec_check                                               # noqa: E402
import spec_experiment as se                                    # noqa: E402
import surface                                                  # noqa: E402

FENCE = re.compile(r"```t\n(.*?)```", re.S)
REFUSALS = ("pool-mismatch", "held-out", "dev-split", "same-task", "names-refused-id",
            "no-positive", "positive-not-spec-checked", "identical-programs")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def program_sha256(text: str) -> str | None:
    """spec_check's task hash of a program's text, or None when it does not parse."""
    try:
        return spec_check.task_sha256(surface.parse(text))
    except Exception:                                           # noqa: BLE001 -- surface raises many kinds
        return None


def load_split(path: Path) -> tuple[set[int], set[int], str]:
    try:
        split = json.loads(path.read_text(encoding="utf-8"))
        eval_ids = {int(i) for i in split["eval_ids"]}
        train_ids = {int(i) for i in split["train_ids"]}
        pool_name = split["pool"]
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot read the split {path} (eval_ids, train_ids and pool are required): {error}")
    if not isinstance(pool_name, str) or pool_name not in se.POOL_VERSIONS:
        raise SystemExit(f"{path} names pool {pool_name!r}, not one of {se.POOL_VERSIONS}")
    return eval_ids, train_ids, pool_name


def load_disagree(path: Path) -> tuple[dict, dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        results, programs = data["results"], data["programs"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot read the specification verdicts {path} (results and programs are required): {error}")
    if not isinstance(results, dict) or not isinstance(programs, dict):
        raise SystemExit(f"{path}: results and programs must be objects keyed by tag/name")
    return results, programs


def load_positives(paths: list[Path]) -> dict[int, list[dict]]:
    """task_id -> the pool files' positives, each with its raw block and hash.

    A row that is not an SFT row, or has no fenced t block, or whose block does
    not parse, is refused by file and line: the pool file is the evidence a pair
    stands on, and an unusable row in it is an input error, not a gap.
    """
    positives: dict[int, list[dict]] = {}
    for path in paths:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                task_id = row["task_id"]
                chosen = row["chosen"]
            except (KeyError, TypeError, json.JSONDecodeError) as error:
                raise SystemExit(f"{path}:{number}: not an SFT row with a task_id and a chosen answer: {error}")
            if isinstance(task_id, bool) or not isinstance(task_id, int):
                raise SystemExit(f"{path}:{number}: task_id {task_id!r} is not an integer")
            match = FENCE.search(chosen) if isinstance(chosen, str) else None
            if match is None:
                raise SystemExit(f"{path}:{number}: task_id={task_id} has no fenced t block")
            program = match.group(1).strip()
            sha = program_sha256(program)
            if sha is None:
                raise SystemExit(f"{path}:{number}: task_id={task_id}: the fenced block does not parse as a t task")
            name = row.get("task") if isinstance(row.get("task"), str) else None
            positives.setdefault(task_id, []).append(
                {"pool_file": path.name, "line": number, "task": name, "program": program, "task_sha256": sha})
    return positives


def spec_rows_for(results: dict, task_id: int, sha: str) -> dict[str, dict]:
    """Every verdict row for this exact program (by hash) and this problem."""
    return {key: row for key, row in results.items()
            if isinstance(row, dict) and row.get("task_sha256") == sha
            and type(row.get("task_id")) is int and row["task_id"] == task_id}


def build(args) -> tuple[list[dict], dict]:
    split_path = Path(args.split)
    eval_ids, train_ids, pool_name = load_split(split_path)
    dev_ids = loop_filter.r12_dev_ids(Path(args.dev_ids) if args.dev_ids else loop_filter.T / "r12-dev-ids.json",
                                      split_path=split_path)
    policy = (loop_filter.decontamination(Path(args.decontamination)) if args.decontamination
              else loop_filter.decontamination())
    refused_ids = eval_ids | dev_ids
    pool = se.pool(pool_name)
    disagree_path = Path(args.spec_disagree)
    results, programs = load_disagree(disagree_path)
    pool_files = [Path(p) for p in args.pool_file]
    positives = load_positives(pool_files)

    # A pool-file positive that a verdict says disagrees is a contradiction
    # between two inputs that were built under the same gate; stop, do not choose.
    for task_id, rows in positives.items():
        for pos in rows:
            for key, verdict in spec_rows_for(results, task_id, pos["task_sha256"]).items():
                if verdict.get("status") == "disagrees":
                    raise SystemExit(f"{pos['pool_file']}:{pos['line']}: the positive for task_id {task_id} is the "
                                     f"program {key} records as DISAGREEING with the problem; the pool file and "
                                     f"{disagree_path.name} contradict each other")

    counts: Counter = Counter()
    refused: dict[str, list[str]] = {reason: [] for reason in REFUSALS}
    by_tag: Counter = Counter()
    pairs: list[dict] = []
    seen: set[tuple] = set()
    for key in sorted(results):
        verdict = results[key]
        if not isinstance(verdict, dict) or verdict.get("status") != "disagrees":
            continue
        counts["disagreeing"] += 1
        tag, _, neg_name = key.partition("/")
        by_tag[tag] += 1
        task_id = verdict.get("task_id")
        if type(task_id) is not int:
            raise SystemExit(f"{disagree_path.name}: {key} disagrees but names no integer task_id")
        if verdict.get("pool") != pool_name:
            refused["pool-mismatch"].append(f"{key} (pool {verdict.get('pool')!r}, split is {pool_name})")
            continue
        if task_id in eval_ids:
            refused["held-out"].append(f"{key} (task_id {task_id})")
            continue
        if task_id in dev_ids:
            refused["dev-split"].append(f"{key} (task_id {task_id})")
            continue
        if task_id in policy.exclude_train_ids or neg_name in policy.drop_document_names:
            refused["same-task"].append(f"{key} (task_id {task_id})")
            continue
        if task_id not in train_ids:
            raise SystemExit(f"{key}: task_id {task_id} is neither held out nor on the training side of {split_path}")
        program = programs.get(key)
        if not isinstance(program, str) or not program.strip():
            raise SystemExit(f"{disagree_path.name}: {key} disagrees but its program is missing")
        program = program.strip()
        sha = program_sha256(program)
        if sha != verdict.get("task_sha256"):
            raise SystemExit(f"{disagree_path.name}: the program stored for {key} hashes to {sha}, not the "
                             f"{verdict.get('task_sha256')} its verdict was measured on; the file is stale")
        entry = pool.get(task_id)
        if entry is None:
            raise SystemExit(f"{key}: task_id {task_id} is not in pool {pool_name}")
        candidates = positives.get(task_id, [])
        if not candidates:
            refused["no-positive"].append(f"{key} (task_id {task_id})")
            continue
        head = loop_locallm.problem_head(entry, args.examples)
        emitted = 0
        for pos in candidates:
            agreeing = {k: v for k, v in spec_rows_for(results, task_id, pos["task_sha256"]).items()
                        if v.get("status") == "agrees" and type(v.get("draws")) is int and v["draws"] > 0
                        and v.get("pool") == pool_name}
            if not agreeing:
                refused["positive-not-spec-checked"].append(
                    f"{key} against {pos['pool_file']}:{pos['line']} (task_id {task_id}: no agreeing verdict "
                    f"for the positive's program under pool {pool_name})")
                continue
            if pos["task_sha256"] == sha or pos["program"] == program:
                refused["identical-programs"].append(f"{key} against {pos['pool_file']}:{pos['line']}")
                continue
            names = [pos["task"], neg_name] + loop_filter.task_names(head + pos["program"] + program)
            check = loop_filter.validate_training_data(head + pos["program"] + "\n" + program, refused_ids,
                                                       names=names, task_ids=[task_id], policy=policy)
            if not check.ok:
                detail = (loop_filter.held_out_detail(check.held_out) if check.held_out
                          else loop_filter.same_task_detail(check))
                refused["names-refused-id"].append(f"{key} against {pos['pool_file']}:{pos['line']} ({detail})")
                continue
            identity = (task_id, pos["program"], program)
            if identity in seen:
                continue
            seen.add(identity)
            agree_key = sorted(agreeing)[0]
            pairs.append(OrderedDict([
                ("task_id", task_id), ("prompt", head), ("chosen", pos["program"]), ("rejected", program),
                ("provenance", {
                    "positive": {"pool_file": pos["pool_file"], "line": pos["line"], "task": pos["task"],
                                 "task_sha256": pos["task_sha256"], "spec": agree_key,
                                 "spec_draws": agreeing[agree_key].get("draws")},
                    "negative": {"key": key, "tag": tag, "task": neg_name, "task_sha256": sha,
                                 "status": "disagrees", "args": verdict.get("args"),
                                 "reference_said": verdict.get("reference_said"),
                                 "ensures": verdict.get("ensures"), "draws": verdict.get("draws"),
                                 "attempts": verdict.get("attempts"), "seed": verdict.get("seed")},
                    "pool": pool_name, "split": str(split_path), "examples": bool(args.examples),
                    "spec_disagree_sha256": file_sha256(disagree_path)})]))
            emitted += 1
        counts["pairs"] += emitted
    for reason in REFUSALS:
        counts["refused:" + reason] = len(refused[reason])
    summary = {"pool": pool_name, "split": str(split_path), "split_sha256": file_sha256(split_path),
               "spec_disagree": str(disagree_path), "spec_disagree_sha256": file_sha256(disagree_path),
               "pool_files": {str(p): file_sha256(p) for p in pool_files},
               "positives": sum(len(v) for v in positives.values()),
               "eval_ids": len(eval_ids), "dev_ids": len(dev_ids), "examples": bool(args.examples),
               "counts": dict(counts), "disagreeing_by_tag": dict(sorted(by_tag.items())),
               "refused": refused, "pairs": [(p["task_id"], p["provenance"]["positive"]["pool_file"],
                                             p["provenance"]["positive"]["line"], p["provenance"]["negative"]["key"])
                                            for p in pairs]}
    return pairs, summary


def report_text(summary: dict) -> str:
    counts = summary["counts"]
    lines = ["# Negatives from specification disagreements",
             "",
             f"Pool `{summary['pool']}`, split `{summary['split']}` (sha256 {summary['split_sha256'][:12]}), "
             f"verdicts `{summary['spec_disagree']}` (sha256 {summary['spec_disagree_sha256'][:12]}), "
             f"{summary['positives']} positives from "
             + ", ".join(f"`{p}` ({s[:12]})" for p, s in summary["pool_files"].items())
             + f"; {summary['eval_ids']} held-out ids, {summary['dev_ids']} dev ids; examples in the head: "
             f"{'yes' if summary['examples'] else 'no'}.",
             "",
             "| count | |", "|---|---:|",
             f"| disagreeing verdict rows | {counts.get('disagreeing', 0)} |",
             f"| **pairs written** | **{counts.get('pairs', 0)}** |"]
    for reason in REFUSALS:
        lines.append(f"| refused: {reason} | {counts.get('refused:' + reason, 0)} |")
    lines += ["", "Disagreeing rows by tag: "
              + ", ".join(f"{tag} {n}" for tag, n in summary["disagreeing_by_tag"].items()) + ".", ""]
    if summary["pairs"]:
        lines += ["## Pairs", "", "| task_id | positive | negative |", "|---:|---|---|"]
        lines += [f"| {tid} | {pf}:{ln} | {key} |" for tid, pf, ln, key in summary["pairs"]]
        lines.append("")
    for reason in REFUSALS:
        rows = summary["refused"][reason]
        if rows:
            lines += [f"## Refused: {reason} ({len(rows)})", ""] + [f"- {row}" for row in rows] + [""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", required=True, help="the split that names the held-out ids and the pool")
    parser.add_argument("--pool-file", action="append", required=True,
                        help="an SFT jsonl of verified, spec-agreeing positives (repeatable)")
    parser.add_argument("--spec-disagree", default=str(T / "out" / "spec-disagree.json"))
    parser.add_argument("--out", required=True, help="the pairs jsonl to write")
    parser.add_argument("--report", required=True, help="the markdown report with the counts")
    parser.add_argument("--examples", action="store_true",
                        help="put the problem's own assertions in the head, as the corpus built with --examples has")
    parser.add_argument("--dev-ids", default=None, help="t/r12-dev-ids.json by default")
    parser.add_argument("--decontamination", default=None, help="t/decontamination-2026-09-21.json by default")
    args = parser.parse_args(argv)
    pairs, summary = build(args)
    eval_ids, _, _ = load_split(Path(args.split))
    dev_ids = loop_filter.r12_dev_ids(Path(args.dev_ids) if args.dev_ids else loop_filter.T / "r12-dev-ids.json",
                                      split_path=Path(args.split))
    whole = "\n\n".join(p["prompt"] + p["chosen"] + "\n\n" + p["rejected"] for p in pairs)
    final = loop_filter.validate_training_data(whole, eval_ids | dev_ids, task_ids=[p["task_id"] for p in pairs])
    if not final.ok:
        detail = (loop_filter.held_out_detail(final.held_out) if final.held_out
                  else loop_filter.same_task_detail(final))
        raise SystemExit(f"refusing to write unsafe pairs: {detail}")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in pairs), encoding="utf-8")
    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(report_text(summary), encoding="utf-8")
    counts = summary["counts"]
    print(f"pairs {out}: {counts.get('pairs', 0)} written from {counts.get('disagreeing', 0)} disagreeing rows; "
          + ", ".join(f"{reason} {counts.get('refused:' + reason, 0)}" for reason in REFUSALS)
          + f"; report {report}")
    for reason in REFUSALS:
        for row in summary["refused"][reason]:
            print(f"refused {reason}: {row}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
