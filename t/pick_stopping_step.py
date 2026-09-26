#!/usr/bin/env python3
"""t/pick_stopping_step.py -- the fine-tune's stopping step, chosen by tests passed on the
dev split, never by validation loss (2026-09-26, r12 plan section C).

    python3 t/pick_stopping_step.py --run t/out/locallm-r12-s1 \\
        [--split t/out/loop/split-v5.json] [--dev-ids t/r12-dev-ids.json | --ids-file IDS] \\
        [--tokens 1200] [--top-k 20] [--examples] [--use-cache] [--tag-prefix NAME] [--install]

Why. The fine-tune that makes every locallm arm memorizes its corpus: on r11 seed 1,
train / held-out nats per token went 0.77/0.88 at step 50, 0.40/0.73 at 100, 0.23/0.70
at 150 and 0.11/0.68 at 300; on r7 the held-out loss rose from 0.57 to 0.59 after step
150 while the train loss fell to 0.08. Validation loss stops moving by step 100-150 and
says nothing about what the model writes. LIMA (ar5iv.labs.arxiv.org/html/2305.11206)
kept a 50-prompt development set apart from its test prompts and picked its checkpoint
by what the model generated on it, because "perplexity does not correlate with
generation quality"; phi-1 (arxiv.org/html/2306.11644) kept the best of periodically
saved fine-tune checkpoints. This script does the same with the 100 train-side problems
of t/r12-dev-ids.json, which no corpus may contain (the builder and preflight refuse
them) and which are not the 232 held-out problems.

What it does. For every kept checkpoint of a continue_from_checkpoint.py run
(`--keep-every`, ckpt-step-N.pt beside the rolling checkpoint, listed in run.json
"kept"), it decodes the dev problems greedily with exactly the prompt
t/loop_locallm.py generate builds (it calls that command, into an answer set named
<run>-dev-step<N>), extracts each reply the way the grader does, and runs the
problems' own assertions in the t interpreter. No kernel runs, no held-out problem is
touched, no positive is spent.

The rule (t/DATA-r12.md section 4): the step with the most dev problems passing all
their assertions; assertions passed as the tie-break; the earliest step on a tie,
because an earlier step is cheaper to reproduce and later steps only memorize more.
selection.json beside the run records every step's numbers. `--install` copies the
chosen kept file over the run's ckpt.pt (the rolling final checkpoint is kept as
ckpt-final.pt) and records the step in run.json, so the generate commands that follow
need no change.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import harness                                                   # noqa: E402
import loop_filter                                               # noqa: E402
import loop_locallm                                              # noqa: E402
import spec_experiment as se                                     # noqa: E402

SCHEMA = 1
RULE = ("the earliest kept step with the most dev problems passing every assertion; "
        "assertions passed break a tie, and an earlier step wins an exact tie")
TESTS_ONLY = "tests only: the seven kernels never run on the dev split, and no held-out problem is decoded"


class Refusal(SystemExit):
    """A loud stop with the reason; exit status 3 like the rest of the r12 tools."""

    def __init__(self, reason: str):
        super().__init__(f"pick_stopping_step: refusing: {reason}")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_run(run: Path) -> dict:
    """The run record, refused unless it is a finished schema-2 continuation."""
    path = run / "run.json"
    if not path.is_file():
        raise Refusal(f"{run} has no run.json")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise Refusal(f"{path} is not readable JSON ({error})")
    if not isinstance(record, dict) or record.get("schema") != 2:
        raise Refusal(f"{path} is schema {record.get('schema') if isinstance(record, dict) else '?'}, "
                      f"not 2; only a continue_from_checkpoint.py run from the r12 build keeps steps")
    if record.get("status") != "complete":
        raise Refusal(f"{path} status is {record.get('status')!r}, not complete")
    return record


def kept_steps(run: Path, record: dict) -> list[dict]:
    """Every kept checkpoint run.json names, present on disk, ascending by step.
    A kept file on disk that run.json does not name is refused too: the record is
    the account of the run, and a stray file is a step the account cannot explain."""
    kept = record.get("kept") or []
    steps = []
    for entry in kept:
        try:
            step, name = int(entry["step"]), str(entry["file"])
        except (KeyError, TypeError, ValueError):
            raise Refusal(f"run.json kept entry is not {{step, file}}: {entry!r}")
        path = run / name
        if not path.is_file():
            raise Refusal(f"run.json names kept step {step} as {name}, and {path} is missing")
        steps.append({"step": step, "file": name})
    named = {s["file"] for s in steps}
    stray = sorted(p.name for p in run.glob("ckpt-step-*.pt") if p.name not in named)
    if stray:
        raise Refusal(f"{len(stray)} kept file(s) run.json does not name: {stray[:5]}")
    if not steps:
        raise Refusal(f"{run} kept no checkpoints (train with --keep-every N)")
    steps.sort(key=lambda s: s["step"])
    return steps


def read_split(split_path: Path) -> dict:
    try:
        split = json.loads(Path(split_path).read_text(encoding="utf-8"))
        return {"pool": split.get("pool", "v1"),
                "eval_ids": {int(i) for i in split["eval_ids"]},
                "train_ids": {int(i) for i in split.get("train_ids", [])}}
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise Refusal(f"cannot read the split {split_path} ({error})")


def dev_ids(split_path: Path, split: dict, dev_file: Path | None, ids_file: Path | None) -> list[int]:
    """The dev problems, and every reason they may not be decoded, checked before anything is."""
    if ids_file is not None:
        try:
            ids = sorted({int(x) for x in Path(ids_file).read_text(encoding="utf-8").split()})
        except (OSError, ValueError) as error:
            raise Refusal(f"cannot read --ids-file {ids_file} ({error})")
        source = str(ids_file)
    else:
        try:
            dev = json.loads(Path(dev_file).read_text(encoding="utf-8"))
            ids = sorted({int(x) for x in dev["dev_ids"]})
            recorded = dev["inputs"]["split_sha256"]
        except (OSError, KeyError, TypeError, ValueError) as error:
            raise Refusal(f"cannot read the dev split {dev_file} ({error})")
        actual = file_sha256(split_path)
        if recorded != actual:
            raise Refusal(f"{dev_file} was drawn from a split with digest {recorded[:12]}..., and {split_path} "
                          f"has {actual[:12]}...; regenerate it (bash t/r12_data_queue.sh dev-ids)")
        source = str(dev_file)
    if not ids:
        raise Refusal(f"{source} names no problem")
    held = sorted(set(ids) & split["eval_ids"])
    if held:
        raise Refusal(f"{len(held)} dev id(s) are held-out problems of the split: {held[:5]}; "
                      f"the stopping step must never be chosen on the test problems")
    policy = loop_filter.decontamination()
    listed = sorted(set(ids) & (set(policy.exclude_train_ids) | set(policy.overlap_eval_ids)))
    if listed:
        raise Refusal(f"{len(listed)} dev id(s) are on the decontamination list: {listed[:5]}")
    if split["train_ids"]:
        outside = sorted(set(ids) - split["train_ids"])
        if outside:
            raise Refusal(f"{len(outside)} dev id(s) are not train problems of the split: {outside[:5]}")
    return ids


def load_pool(version: str) -> dict:
    """The pool the split names; a seam so a test can supply its own problems."""
    return se.pool(version)


def decode_step(checkpoint: Path, tag: str, split_path: Path, ids_file: Path, args) -> int:
    """Answer the dev problems from one kept checkpoint through the one generator this
    project has, so the prompt, the stop rule, the seeding and the records are exactly
    those of a held-out run; resumable, because generate refuses to mix configurations."""
    argv = ["generate", "--model", str(checkpoint), "--tag", tag, "--split", str(split_path),
            "--ids-file", str(ids_file), "--temperature", "0", "--tokens", str(args.tokens),
            "--top-k", str(args.top_k), "--seed", str(args.seed)]
    if args.examples:
        argv.append("--examples")
    if args.use_cache:
        argv.append("--use-cache")
    return loop_locallm.main(argv)


def overall_verdict(verdicts: list[str]) -> str:
    """spec_experiment.cmd_tests's rule, so a dev problem is passed here exactly when
    the grader would count its tests as passed."""
    if all(v == "pass" for v in verdicts):
        return "pass"
    if any(v in ("arity", "type") for v in verdicts):
        return "signature"
    if any(v in ("fail", "crash") for v in verdicts):
        return "fail"
    if any(v == "requires-excluded" for v in verdicts):
        return "requires-excluded"
    return "undefined"


def score_tag(d: Path, ids: list[int], pool: dict) -> dict[int, dict]:
    """Extract the answer set the way the grader does and run each dev problem's own
    assertions; tests.json is written in cmd_tests's shape for the record."""
    rc = se.extract_tag(d)
    if rc != 0:
        raise Refusal(f"extraction of {d.name} failed (exit {rc}); see its messages above")
    extracted = json.loads((d / "extract.json").read_text(encoding="utf-8"))
    results, tests = {}, {}
    for tid in ids:
        entry = pool.get(tid) or pool.get(str(tid))
        if entry is None:
            raise Refusal(f"dev problem {tid} is not in the pool")
        points = entry["points"]
        row = extracted.get(str(tid)) or extracted.get(tid)
        if row is None:
            results[tid] = {"overall": "unanswered", "passed": 0, "total": len(points)}
            continue
        if row.get("stage") != "task":
            results[tid] = {"overall": row.get("stage"), "passed": 0, "total": len(points), "why": row.get("why")}
            continue
        task = harness.load(d / "tasks" / f"{row['name']}.json")
        verdicts = [se.run_point(task, point) for point in points]
        overall = overall_verdict([v["verdict"] for v in verdicts])
        passed = sum(v["verdict"] == "pass" for v in verdicts)
        results[tid] = {"name": row["name"], "overall": overall, "passed": passed, "total": len(points)}
        tests[tid] = {"name": row["name"], "overall": overall, "points": verdicts}
    (d / "tests.json").write_text(json.dumps(tests, indent=1), encoding="utf-8")
    return results


def summarize(step: dict, results: dict[int, dict]) -> dict:
    return {**step,
            "passed_problems": sum(r["overall"] == "pass" for r in results.values()),
            "passed_assertions": sum(r["passed"] for r in results.values()),
            "total_assertions": sum(r["total"] for r in results.values()),
            "extracted": sum(r["overall"] not in ("unanswered", "no-block", "parse", "wf") for r in results.values()),
            "problems": {str(tid): r for tid, r in sorted(results.items())}}


def choose(steps: list[dict]) -> dict:
    """The rule: most problems, then most assertions, then the earliest step. A strictly
    greater key replaces the choice, so an equal later step never displaces an earlier one."""
    if not steps:
        raise Refusal("no step to choose from")
    best = None
    for step in sorted(steps, key=lambda s: s["step"]):
        key = (step["passed_problems"], step["passed_assertions"])
        if best is None or key > (best["passed_problems"], best["passed_assertions"]):
            best = step
    return best


def install(run: Path, record: dict, chosen: dict) -> dict:
    """Make the chosen kept checkpoint the run's ckpt.pt, keeping the rolling final one."""
    already = record.get("installed")
    if already and already.get("step") != chosen["step"]:
        raise Refusal(f"{run / 'run.json'} already records step {already.get('step')} as installed; "
                      f"this selection chose {chosen['step']}. Restore ckpt-final.pt by hand first")
    source, target, final = run / chosen["file"], run / "ckpt.pt", run / "ckpt-final.pt"
    if target.is_file() and not final.is_file():
        shutil.copy2(target, final)
    shutil.copy2(source, target)
    record["installed"] = {"step": chosen["step"], "from": chosen["file"], "sha256": file_sha256(source),
                           "final_saved_as": final.name if final.is_file() else None,
                           "selection": "selection.json"}
    (run / "run.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record["installed"]


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", type=Path, required=True, help="a continue_from_checkpoint.py --out directory")
    ap.add_argument("--split", type=Path, default=HERE / "out" / "loop" / "split-v5.json")
    ap.add_argument("--dev-ids", type=Path, default=HERE / "r12-dev-ids.json",
                    help="the dev split file; its recorded split digest must match --split")
    ap.add_argument("--ids-file", type=Path, help="decode these ids instead of the dev split's")
    ap.add_argument("--tag-prefix", help="answer sets are named <prefix>-step<N>; default <run name>-dev")
    ap.add_argument("--tokens", type=int, default=1200)
    ap.add_argument("--top-k", type=int, default=20)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--examples", action="store_true", help="the problem's own assertions in the head, "
                    "as the corpus was built; must match how the held-out run will prompt")
    ap.add_argument("--use-cache", action="store_true")
    ap.add_argument("--install", action="store_true", help="copy the chosen step over the run's ckpt.pt")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run = args.run
    record = read_run(run)
    steps = kept_steps(run, record)
    split = read_split(args.split)
    ids = dev_ids(args.split, split, args.dev_ids, args.ids_file)
    pool = load_pool(split["pool"])
    ids_file = run / "dev-ids.txt"
    ids_file.write_text("\n".join(map(str, ids)) + "\n", encoding="utf-8")
    prefix = args.tag_prefix or f"{run.resolve().name}-dev"
    rows = []
    for step in steps:
        tag = f"{prefix}-step{step['step']}"
        checkpoint = run / step["file"]
        rc = decode_step(checkpoint, tag, args.split, ids_file, args)
        if rc != 0:
            raise Refusal(f"generate exited {rc} for step {step['step']} (tag {tag})")
        results = score_tag(se.outdir(tag), ids, pool)
        row = summarize({**step, "sha256": file_sha256(checkpoint), "tag": tag}, results)
        rows.append(row)
        print(f"step {row['step']:>5}: {row['passed_problems']} of {len(ids)} problems pass, "
              f"{row['passed_assertions']} of {row['total_assertions']} assertions, "
              f"{row['extracted']} extracted   ({tag})", flush=True)
    chosen = choose(rows)
    selection = {"schema": SCHEMA, "rule": RULE, "tests_only": TESTS_ONLY, "run": str(run),
                 "split": {"path": str(args.split), "sha256": file_sha256(args.split), "pool": split["pool"]},
                 "dev_ids": {"source": str(args.ids_file or args.dev_ids), "n": len(ids), "ids": ids},
                 "options": {"temperature": 0, "tokens": args.tokens, "top_k": args.top_k, "seed": args.seed,
                             "examples": args.examples},
                 "steps": [{k: v for k, v in row.items()} for row in rows],
                 "chosen": {"step": chosen["step"], "file": chosen["file"], "sha256": chosen["sha256"],
                            "passed_problems": chosen["passed_problems"],
                            "passed_assertions": chosen["passed_assertions"]},
                 "installed": None}
    if args.install:
        selection["installed"] = install(run, record, chosen)
    (run / "selection.json").write_text(json.dumps(selection, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"chosen: step {chosen['step']} ({chosen['file']}): {chosen['passed_problems']} problems, "
          f"{chosen['passed_assertions']} assertions" + (" -- installed as ckpt.pt" if args.install else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
