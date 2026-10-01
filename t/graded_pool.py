#!/usr/bin/env python3
"""t/graded_pool.py -- the student's training pool at a stated trust level (2026-10-01).

    python3 t/graded_pool.py --from-samples TAG [TAG ...] --split t/out/loop/split-v5.json \\
        --verdicts PATH --min-kernels K --out PATH [--report PATH]

t/loop_dataset.py admits a model-written answer only when all seven kernels verify it. That bar is
kept there, and every corpus registered under it is untouched. This file builds a second pool for
fine-tuning a pretrained student, at a trust level the caller names and every row records:

  an answer is admitted when it is well formed, passes its problem's own tests, at least K of the
  seven named kernels read `verified / refuted` (the program proved, its sabotaged twin refuted),
  NO kernel refutes the program, and its specification agrees with the problem's reference on
  drawn inputs (a current, hash-bound verdict) without contradicting a stated example.

Why a lower K is sound enough to train on. SAFE (arXiv:2410.15756) fine-tunes on proofs one
verifier accepted, with specifications filtered by tests and mutants, and reaches 21.6% from 1.4%
on a 1.3B backbone; one sound verifier is the published filter. Our own record
(t/kernel_disagreement.py, 2026-10-01): 4,700 programs through seven kernels, no kernel ever
verified what another refuted, so a kernel that could not decide has never been evidence against
a proof. The specification check and the tests are applied at every level, because a proof of the
wrong thing is still wrong (of 63 held-out problems proved by some kernel, 18 fell to that check).

Only training problems are read: an id in the split's eval half, the dev split, or the
decontamination policy's exclusions stops the build by name, as t/rl_reward.rl_prompt_ids does.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import loop_dataset                                             # noqa: E402
import loop_filter                                              # noqa: E402
import spec_check                                               # noqa: E402
import spec_experiment                                          # noqa: E402
import surface                                                  # noqa: E402

VERIFIED = "verified / refuted"
# INVENTED (no outside source gives the number): an `agrees` needs one agreeing draw, and since
# 2026-10-01 the specification check skips draws the reference cannot answer, so an `agrees` can
# rest on very few (9 training answers under 10, one on a single draw). SAFE's table 3
# (arXiv:2410.15756) is the reason to be strict here: wrong specifications in the training data
# cost its model 26 points. A row is trained on only when at least this many draws agreed.
MIN_AGREEING_DRAWS = 10
# SAFE keeps a specification for training only when it rejects at least 60% of mutated test cases
# (arXiv:2410.15756, 3.2). The reference check has always measured the same thing on its drawn
# inputs (`completeness`: the share of mutated outputs the ensures rejects) and only reported it.
# On 2026-10-01, 40 of the pool's 693 rows sat below 0.6 (an `ensures` true of the right answer
# and of most wrong ones, e.g. "every character of r is alphanumeric" for a function that removes
# the others). A row is trained on only at this completeness or above; a verdict that tried no
# mutant is let through, as before.
MIN_COMPLETENESS = 0.6


def kernel_level(sample: dict) -> tuple[int, list[str], list[str]]:
    """(kernels that proved it and refuted its twin, kernels that refuted the program, the rest)."""
    row = sample.get("kernel_row", {})
    proved = [k for k in spec_check.KERNELS if row.get(k) == VERIFIED]
    refuted = [k for k in spec_check.KERNELS if str(row.get(k, "")).split(" / ")[0] == "refuted"]
    undecided = [k for k in spec_check.KERNELS if k not in proved and k not in refuted]
    return len(proved), refuted, undecided


def rejection(sample: dict, results: dict, pool_name: str, min_kernels: int) -> str | None:
    """First failed gate, or None. The order is the cheap evidence first."""
    if not sample["wellformed"]:
        return "not-wellformed"
    if not sample["tests_pass"]:
        return "tests-not-passing"
    columns = sample.get("kernel_columns", [])
    if len(columns) != loop_dataset.ALL_KERNELS or set(columns) != set(spec_check.KERNELS):
        return "kernel-names-not-exact-seven"
    proved, refuted, _undecided = kernel_level(sample)
    if refuted:
        return "a-kernel-refutes-the-program"
    if proved < min_kernels:
        return f"proved-by-fewer-than-{min_kernels}"
    result = results.get(f"{sample['tag']}/{sample['name']}")
    if not isinstance(result, dict):
        return "spec-unchecked"
    if result.get("status") != "agrees":
        return "spec-not-agrees"
    if type(result.get("draws")) is not int or result["draws"] <= 0:
        return "spec-no-valid-draws"
    if result["draws"] < MIN_AGREEING_DRAWS:
        return "spec-agrees-on-too-few-draws"
    if spec_check.complete(result, MIN_COMPLETENESS) is False:     # either mutant family (spec_check.complete)
        return "spec-too-weak"
    if type(result.get("task_id")) is not int or result["task_id"] != sample["task_id"]:
        return "spec-problem-mismatch"
    if result.get("pool") != pool_name:
        return "spec-pool-mismatch"
    try:
        current = spec_check.task_sha256(sample["task"])
    except surface.SurfaceError:
        return "task-no-longer-prints"
    if result.get("task_sha256") != current:
        return "spec-hash-missing-or-stale"
    if type(result.get("points_failed")) is int and result["points_failed"] > 0:
        return "spec-contradicts-example"
    return None


def answer_text(task: dict, asked_name: str) -> str:
    """The answer as the student should write it: the task named as the prompt asks.

    The graded task carries the pipeline's own name, `mbpp_<id>__<fn>`, which extract assigns;
    the prompt asks for `<fn>` and never states the id. Printed under the internal name, all 527
    rows of the first pool contradicted their own instruction, and a student trained on them wrote
    an `mbpp_<number>__` prefix on 99 of 100 dev answers with the real id in none (2026-10-01).
    The target must be a function of the prompt. A copy is renamed, self-calls with it
    (spec_experiment.rename_task); the graded task and its evidence hash are not touched, and
    extract gives every answer the internal name again before grading. A name the surface syntax
    cannot print (a keyword) keeps the internal one."""
    import copy
    try:
        return surface.print_task(spec_experiment.rename_task(copy.deepcopy(task), asked_name)).strip()
    except surface.SurfaceError:
        return surface.print_task(task).strip()


def training_ids(split_path: Path, pool: dict) -> set[int]:
    """Train ids minus everything held out: the eval half, the dev split, the policy's exclusions."""
    split = json.loads(split_path.read_text(encoding="utf-8"))
    eval_ids = {int(i) for i in split["eval_ids"]}
    policy = loop_filter.decontamination()
    blocked = (eval_ids | set(loop_filter.r12_dev_ids(HERE / "r12-dev-ids.json"))
               | set(policy.exclude_train_ids) | set(policy.overlap_eval_ids))
    ids = {int(i) for i in split["train_ids"] if int(i) in pool} - blocked
    leak = ids & blocked
    if leak:
        raise SystemExit(f"graded_pool: held-out ids in the pool: {sorted(leak)[:5]}")
    return ids


def build(tags: list[str], split_path: Path, verdicts_path: Path, min_kernels: int,
          prompt_version: str = "v5") -> tuple[list[dict], dict]:
    if not 1 <= min_kernels <= loop_dataset.ALL_KERNELS:
        raise SystemExit("graded_pool: --min-kernels is 1 to 7")
    split = json.loads(split_path.read_text(encoding="utf-8"))
    pool_name = split.get("pool", "v1")
    pool = spec_experiment.pool(pool_name)
    ids = training_ids(split_path, pool)
    results = json.loads(verdicts_path.read_text(encoding="utf-8")).get("results", {})
    tag_dirs = [loop_dataset.load_tag_dir(t) for t in tags]
    rows, reasons, seen = [], Counter(), {}
    problems_with_samples = 0
    for tid in sorted(ids):
        samples = []
        for k, tagdata in enumerate(tag_dirs):                  # loop_dataset.gather_samples, one tag at a time
            try:
                sample = loop_dataset.grade_sample(tagdata, k, tid)
            except surface.SurfaceError:
                # an answer from before a word became a keyword (`card`): it does not print in
                # today's syntax, so it is not a program the student should be taught
                reasons["task-no-longer-prints"] += 1
                continue
            if sample is not None:
                samples.append(sample)
        if samples:
            problems_with_samples += 1
        for sample in samples:
            why = rejection(sample, results, pool_name, min_kernels)
            if why:
                reasons[why] += 1
                continue
            text = answer_text(sample["task"], pool[tid]["fn"])
            proved, _refuted, undecided = kernel_level(sample)
            key = (tid, text)
            if key in seen:                                     # the same program twice: keep the stronger evidence
                if proved > seen[key]["kernels_verified"]:
                    seen[key].update(kernels_verified=proved, undecided=undecided, tag=sample["tag"], name=sample["name"])
                reasons["duplicate-program"] += 1
                continue
            # t/loop_train.py's row: the recorded system+user messages and the fenced answer. The
            # prompt is rebuilt at ONE version for every row (the answers were asked under five),
            # so the student is trained and later asked under the same words; the answer is the
            # printer's canonical text, which is today's syntax whatever the model typed.
            row = {"task_id": tid, "tag": sample["tag"], "name": sample["name"],
                   "prompt": spec_experiment.build_prompt(pool[tid], prompt_version),
                   "chosen": loop_dataset.fence(text),
                   "kernels_verified": proved, "undecided": undecided, "source": "graded"}
            seen[key] = row
            rows.append(row)
    report = {"min_kernels": min_kernels, "pool": pool_name, "prompt": prompt_version, "tags": len(tags),
              "train_ids": len(ids),
              "problems_with_samples": problems_with_samples, "rows": len(rows),
              "problems": len({r["task_id"] for r in rows}),
              "by_level": dict(sorted(Counter(r["kernels_verified"] for r in rows).items())),
              "rejections": dict(reasons.most_common())}
    return rows, report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from-samples", nargs="+", required=True, metavar="TAG")
    ap.add_argument("--split", type=Path, required=True)
    ap.add_argument("--verdicts", type=Path, required=True,
                    help="a spec_check verdict file covering every candidate answer (--only all)")
    ap.add_argument("--min-kernels", type=int, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--report", type=Path)
    ap.add_argument("--prompt", choices=spec_experiment.PROMPT_VERSIONS, default="v5",
                    help="the prompt version every row is rebuilt under (default v5)")
    a = ap.parse_args(argv)
    rows, report = build(a.from_samples, a.split, a.verdicts, a.min_kernels, a.prompt)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
    if a.report:
        a.report.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report))
    return 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
