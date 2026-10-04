#!/usr/bin/env python3
"""t/rl_teacher_expert_iter.py -- teacher-seeded expert iteration (2026-09-26).

t/RL-DESIGN-2026-09-26.md section 7 found the policy (locallm-r11-s8) solves
almost nothing outside its own training corpus (0.6 percent of 308 MBPP/
HumanEval train problems, 1 of 120 vericoding specs) and recommended: have the
prompted 27B teacher this pipeline already uses (t/spec_experiment.py's
qwen3.8-27b-fp8) answer the same two prompt pools through the same tiered
reward (t/rl_reward.py), and keep every answer that reaches the reward's top
tier as a new training document. STaR (arXiv:2203.14465) and ReST-EM
(arXiv:2312.06585) are exactly this loop -- sample, keep what an external
check accepts, train on the kept set, repeat -- and PSV (arXiv:2512.18160,
the design doc's reference) plays the proposer's role here with the fixed
lifted vericoding pool and the training split, not a learned model (research
receipt 2cbb3be1bf27).

Training-problem prompts (MBPP, HumanEval, APPS train ids the policy was not
fine-tuned on) need no new sampling code: `t/spec_experiment.py generate
--api openai` already prompts a served model with the pool's few-shot t
grammar (build_prompt) and writes one raw record per id per tag, so k samples
are k tags (`--seed`, `--tag`), exactly as the historical `-s2` arm did. This
file adds only what that pipeline does not already have:

  consolidate-training  fold several spec_experiment tag directories (one
                         per sample) into the per-problem sample files
                         t/rl_feasibility.py's own score/report commands
                         already read, so scoring a teacher sample set is
                         `python3 t/rl_feasibility.py score/report`
                         unchanged (rl_feasibility.load_samples, rl_reward.
                         score_many): no new scoring code for this half.

Specification-only prompts (t/rl_spec_pool.py's 447 lifted vericoding specs)
have no pool() entry to run spec_experiment.py's build_prompt against, so
they need a sampling step of their own (sample-spec, below) -- but the same
teacher call (spec_experiment.chat, api openai) as every other reply in this
pipeline, not a new client. t/rl_spec_pool.py's own scoring
(score_spec_answers) assumes a *continuation* completion (valid for the
locally-sampled 92M checkpoint's raw next-token output, which cannot restate
the prompt); a chat-tuned model asked to write the whole task can restate the
declaration in its own formatting, or -- unrewarded here but not
structurally prevented the way a bare continuation prevents it -- change it,
which would make a proof of a rewritten specification look like a proof of
the given one. score-spec below therefore parses the model's whole reply and
checks a spec-fidelity invariant (spec_header) before scoring it, which
substitutes for the continuation trick rather than adding a new tier.

The rest is bookkeeping: assemble builds a shortlist at the reward's top
Dafny-only tier from both pools, re-grades the shortlist in all seven
kernels (t/run_par.py, the cost this project always defers past the cheap
proxy: t/rl_reward.py's own docstring measures Dafny-alone agrees with all
seven 97.8 percent of the time), and writes what is admitted (clean in
seven, or six with the gap named, AMBITION.md's rule) as a new corpus in the
pipeline's existing formats: a spec_experiment tag directory (raw/, tasks/,
kernels.md) for the training-problem answers, so t/loop_dataset.py
--from-samples can take it unchanged, and a corpus-format document file
(Problem:/Signature:/task, t/loop_locallm.py's own head convention) for the
specification answers, which have no pool id to key a tag directory on.

    python3 t/rl_teacher_expert_iter.py sample-spec --out OUT --prompts P.jsonl \\
        --host H:PORT --model qwen3.8-27b-fp8 --k 8 --temperature 0.7 --jobs 8

    python3 t/rl_teacher_expert_iter.py score-spec --out OUT --gated GATED.jsonl \\
        [--jobs 2] [--local]

    python3 t/rl_teacher_expert_iter.py consolidate-training --out OUT --tags TAG0 TAG1 ...

    python3 t/rl_teacher_expert_iter.py assemble --spec-out SOUT --gated GATED.jsonl \\
        --training-out TOUT --pool v5 --dest-tag rl-teacher-verified \\
        --dest-specpool-dir DEST [--jobs 2] [--local]
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import rl_reward                                                 # noqa: E402
import run_par                                                   # noqa: E402
import spec_experiment as se                                     # noqa: E402
import surface                                                   # noqa: E402

SPEC_TIERS = {"none": 0.0, "parses": 0.05, "typed": 0.10, "proved": 1.0}


def teacher_reply(host: str, model: str, messages: list[dict], *, temperature: float, seed: int,
                  max_tokens: int, timeout: float) -> str:
    """One chat completion from the served teacher: spec_experiment.chat's own
    OpenAI-shaped call (api="openai"), reused rather than re-implemented,
    since every other reply this pipeline has ever graded went through it."""
    options = {"temperature": temperature, "seed": seed, "num_predict": max_tokens}
    resp = se.chat(host, model, messages, options, timeout, api="openai")
    return resp.get("message", {}).get("content", "")


# ------------------------------------------------------------- spec prompts --

def spec_messages(prompt: str) -> list[dict]:
    """A chat prompt for one vericoding spec: build_prompt's own grammar and
    few-shot t examples (v5), so the teacher sees the same language once, plus
    the spec prompt (t/rl_spec_pool.spec_prompt: Problem/Signature/declaration
    up to the body's opening brace) and an instruction to leave the clauses
    alone. score_spec_sample below checks that instruction held; it is not
    trusted on its own (module docstring)."""
    system = se.GRAMMAR_V5 + "\nExamples of complete t tasks:\n\n" + se.fewshot_text("v5")
    user = (prompt + "\n\nThe text above ends at the task's opening brace. Reply with the "
            "COMPLETE task, from `task` to its final closing brace, in one ```t code fence. "
            "Keep every `requires` and `ensures` clause exactly as given and write only the "
            "body statements that belong between them and the closing brace.")
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


_T_HEADER = re.compile(r"(?m)^t [01]\b")


def with_t_header(block: str, original: dict) -> str:
    """surface.parse needs the leading `t 0`/`t 1` version line; the spec
    prompt's instruction (spec_messages) asks the model to reply starting at
    `task`, not at that line (which duplicates the version already carried
    in the prompt's own last line before the model ever speaks), so it is
    restored from the given spec rather than trusted from the reply -- one
    more thing this pipeline does not let the model choose for itself."""
    return block if _T_HEADER.search(block) else f"t {original['t']}\n{block}"


def spec_header(task: dict) -> str:
    """The canonical form of a task's declaration and clauses alone, name and
    body erased (se.rename_task, surface.canon; loop_filter.key erases the
    same way for corpus deduplication, a different purpose). Two tasks compare
    equal here exactly when their interface and specification match, whatever
    their body or original name."""
    t = se.rename_task(copy.deepcopy(task), "x")
    t["body"] = []
    t.pop("gate", None)
    return surface.canon(t)


def cmd_sample_spec(a) -> int:
    prompts = [json.loads(l) for l in Path(a.prompts).read_text(encoding="utf-8").splitlines() if l.strip()]
    out = Path(a.out) / "samples"
    out.mkdir(parents=True, exist_ok=True)
    pending = [p for p in prompts if not (out / f"{p['stem']}.jsonl").exists()]
    print(f"sample-spec: {len(prompts) - len(pending)} of {len(prompts)} stems already sampled "
          f"({len(pending)} to go), k={a.k}", flush=True)
    if not pending:
        return 0
    work = [(p, i) for p in pending for i in range(a.k)]
    results = {p["stem"]: [None] * a.k for p in pending}
    remaining = {p["stem"]: a.k for p in pending}
    lock = threading.Lock()
    t0 = time.monotonic()
    state = {"done": 0}

    def one(p, i):
        seed = a.seed_base + i
        try:
            content = teacher_reply(a.host, a.model, spec_messages(p["prompt"]), temperature=a.temperature,
                                    seed=seed, max_tokens=a.tokens, timeout=a.timeout)
        except (urllib.error.URLError, OSError) as e:
            return p, i, None, str(e)
        return p, i, content, None

    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        futs = [ex.submit(one, p, i) for p, i in work]
        for fut in as_completed(futs):
            p, i, content, err = fut.result()
            stem = p["stem"]
            with lock:
                if err is None:
                    results[stem][i] = {"stem": stem, "name": p["name"], "source": p.get("source"),
                                        "i": i, "reply": content}
                else:
                    print(f"sample-spec: {stem} seed {a.seed_base + i}: {err}", file=sys.stderr)
                remaining[stem] -= 1
                if remaining[stem] == 0:
                    rows = [r for r in results[stem] if r is not None]
                    if rows:
                        path = out / f"{stem}.jsonl"
                        tmp = path.with_suffix(".tmp")
                        tmp.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
                        os.replace(tmp, path)
                state["done"] += 1
                if state["done"] % 20 == 0 or state["done"] == len(work):
                    el = time.monotonic() - t0
                    print(f"sample-spec: {state['done']} of {len(work)} replies "
                          f"({el:.0f}s, {el / state['done']:.1f}s each)", flush=True)
    return 0


def cmd_score_spec(a) -> int:
    out = Path(a.out)
    gated = {}
    for line in Path(a.gated).read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            gated[row["stem"]] = row
    cache = rl_reward.RewardCache(out / "rewards.jsonl")
    items = []
    for f in sorted((out / "samples").glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                items.append(json.loads(line))
    fresh: dict[str, tuple[dict, dict | None]] = {}
    keys = []
    for it in items:
        stem = it["stem"]
        key = hashlib.sha256(f"specrl:{stem}:{it['i']}:{it['reply']}".encode("utf-8")).hexdigest()
        keys.append(key)
        if cache.get(key) is not None or key in fresh:
            continue
        row = gated.get(stem)
        if row is None:
            fresh[key] = ({"stem": stem, "stage": "no-gate-row"}, None)
            continue
        original = json.loads(Path(row["task_file"]).read_text(encoding="utf-8"))
        block = se.find_block(it["reply"])
        if block is None:
            fresh[key] = ({"stem": stem, "stage": "no-block"}, None)
            continue
        block = with_t_header(block, original)
        try:
            task = surface.parse(block)
        except Exception as e:                                   # noqa: BLE001
            fresh[key] = ({"stem": stem, "stage": "parse", "why": str(e)[:200]}, None)
            continue
        task = se.rename_task(task, f"{it['name']}__rlt{key[:10]}")
        if spec_header(task) != spec_header(original):
            fresh[key] = ({"stem": stem, "stage": "spec-changed"}, None)
            continue
        try:
            errs = se.fuzz_lower.check_wf(task)
        except Exception as e:                                   # noqa: BLE001
            errs = [f"check_wf raised {type(e).__name__}: {e}"[:200]]
        if errs:
            fresh[key] = ({"stem": stem, "stage": "wf", "why": "; ".join(errs)[:300]}, None)
            continue
        fresh[key] = ({"stem": stem, "stage": "task"}, task)
    tasks = {t["name"]: t for (_s, t) in fresh.values() if t is not None}
    host = "local" if a.local else None
    cells = rl_reward.prove(tasks, jobs=a.jobs, host=host, batch="spec-teacher") if tasks else {}
    for key, (sig, task) in fresh.items():
        cache.put(key, sig, cells.get(task["name"]) if task is not None else None)
    tiers = {}
    for key in keys:
        row = cache.get(key)
        sig, proof = row["signals"], row["proof"]
        stage = sig["stage"]
        tier = ("none" if stage in ("no-block", "parse", "spec-changed", "no-gate-row")
                else "parses" if stage == "wf"
                else "proved" if proof == rl_reward.CLEAN else "typed")
        tiers[tier] = tiers.get(tier, 0) + 1
    print(json.dumps({"samples": len(items), "tiers": tiers}))
    return 0


# --------------------------------------------------------- training prompts --

def cmd_consolidate_training(a) -> int:
    """Fold spec_experiment.py generate's per-tag raw/<id>.json (one sample
    set per tag: k samples of one prompt pool means k tags, one --seed and
    --tag each, exactly as the historical qwen3.8-27b-fp8-v3-s2 arm was
    produced) into the per-problem files t/rl_feasibility.py's own sample/
    score/report commands read (out/samples/<id>.jsonl, k rows), so scoring a
    teacher sample set needs no new code: `python3 t/rl_feasibility.py score
    --out OUT --local` and `... report --json` read this directly."""
    out = Path(a.out) / "samples"
    out.mkdir(parents=True, exist_ok=True)
    per_tid: dict[int, list[dict]] = {}
    for tag in a.tags:
        raw_dir = HERE / "out" / "spec-experiment" / tag / "raw"
        if not raw_dir.is_dir():
            print(f"consolidate-training: no raw/ under tag {tag}, skipping", file=sys.stderr)
            continue
        for f in sorted(raw_dir.glob("*.json")):
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
            except ValueError:
                continue
            tid = int(rec["task_id"])
            i = len(per_tid.setdefault(tid, []))
            per_tid[tid].append({"task_id": tid, "i": i, "reply": rec["reply"], "tag": tag,
                                 "options": rec.get("options")})
    for tid, rows in per_tid.items():
        path = out / f"{tid}.jsonl"
        tmp = path.with_suffix(".tmp")
        tmp.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        os.replace(tmp, path)
    print(f"consolidate-training: {len(per_tid)} problems from {len(a.tags)} tag(s) -> {out}")
    return 0


# ------------------------------------------------------------- full 7 grade --

def full_kernel_grade(tasks: dict[str, dict], out: Path, *, jobs: int, host: str | None) -> dict[str, dict[str, str]]:
    """All seven kernels (run_par.py's own default set, not the Dafny-only
    subset t/rl_reward.py asks in the loop) for a shortlist that already
    reached the reward's top Dafny-only tier. Writes tasks/ and kernels.md
    straight into ``out``, so ``out`` can be the final tag directory
    t/loop_dataset.py --from-samples reads. host="local" runs run_par.py in
    this checkout (we are already on the grading machine); no other host is
    implemented here because this project's proof grading only ever runs on
    the lab or the desktop it is invoked from (AGENTS.md)."""
    if not tasks:
        return {}
    tdir = out / "tasks"
    tdir.mkdir(parents=True, exist_ok=True)
    for name, task in tasks.items():
        (tdir / f"{name}.json").write_text(json.dumps(task, indent=1), encoding="utf-8")
    table = out / "kernels.md"
    run = (f"T_MIN_KERNELS=1 T_SPARK_JOBS=1 python3 t/run_par.py --jobs {int(jobs)} "
           f"--tasks {tdir} --out {out / 'kernels'} --table {table}")
    if (host or "local") != "local":
        raise NotImplementedError("full_kernel_grade: only host='local' is used by this task")
    r = subprocess.run(["bash", "-lc", run], cwd=HERE.parent, capture_output=True, text=True)
    if r.returncode not in (0, 1):
        raise RuntimeError(f"full_kernel_grade: run_par exited {r.returncode}: {(r.stdout + r.stderr)[-800:]}")
    _cols, rows = se.parse_kernel_table(table)
    return {name: {k: rows.get(name, {}).get(k, "missing") for k in run_par.ALL_KERNELS} for name in tasks}


def clean_count(row: dict[str, str]) -> int:
    return sum(1 for v in row.values() if v == rl_reward.CLEAN)


def gap_kernels(row: dict[str, str]) -> list[str]:
    return sorted(k for k, v in row.items() if v != rl_reward.CLEAN)


# ---------------------------------------------------------------- assemble --

def cmd_assemble(a) -> int:
    import rl_feasibility

    dest_root = Path(a.dest_root)
    dest_root.mkdir(parents=True, exist_ok=True)
    host = "local" if a.local else None
    report: dict = {"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    # -- training-problem prompts: rl_feasibility's own sample shape + rl_reward's cache --
    tout = Path(a.training_out)
    groups = rl_feasibility.load_samples(tout) if (tout / "samples").is_dir() else {}
    pool = se.pool(a.pool) if groups else {}
    cache = rl_reward.RewardCache(tout / "rewards.jsonl")
    tier_counts: dict[str, int] = {}
    # One winner per problem id: the lowest-seed sample that reaches "proved".
    # A later seed of the same id that also proves is real evidence (recorded
    # in the tier counts above) but would only duplicate the corpus document
    # the first one already earns, at the cost of a second seven-kernel grade.
    shortlist_training: dict[str, tuple[dict, dict]] = {}   # name -> (task, provenance)
    for tid, rows in groups.items():
        winner = None
        for s in sorted(rows, key=lambda r: r.get("i", 0)):
            key = rl_reward.answer_key(tid, s["reply"])
            row = cache.get(key)
            if row is None:
                continue
            t = rl_reward.tier(row["signals"], row["proof"])
            tier_counts[t] = tier_counts.get(t, 0) + 1
            if t == "proved" and winner is None:
                winner = s
        if winner is not None:
            sig = rl_reward.local_signals(tid, winner["reply"], pool[int(tid)])
            task = sig.get("task")
            if task is not None:
                fam = ("apps" if int(tid) >= se.APPS_BASE else
                       "humaneval" if int(tid) >= se.HUMANEVAL_BASE else "mbpp")
                shortlist_training[task["name"]] = (task, {"task_id": int(tid), "source": fam,
                                                           "sample_tag": winner.get("tag"),
                                                           "sample_index": winner.get("i"),
                                                           "reward_tier": "proved", "reward": rl_reward.TIERS["proved"]})
    report["training"] = {"prompts": len(groups), "samples": sum(len(v) for v in groups.values()),
                          "tiers": tier_counts, "top_tier_answers": len(shortlist_training)}

    # -- spec-only prompts: this file's own score-spec cache --
    sout = Path(a.spec_out)
    scache = rl_reward.RewardCache(sout / "rewards.jsonl")
    stier_counts: dict[str, int] = {}
    shortlist_spec: dict[str, tuple[dict, dict]] = {}
    n_spec_samples = n_spec_prompts = 0
    gated_rows = {}
    for line in Path(a.gated).read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            gated_rows[row["stem"]] = row
    if (sout / "samples").is_dir():
        by_stem: dict[str, list[dict]] = {}
        for f in sorted((sout / "samples").glob("*.jsonl")):
            rows = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
            by_stem[f.stem] = rows
        n_spec_prompts = len(by_stem)
        for stem, rows in by_stem.items():
            n_spec_samples += len(rows)
            winner = None
            for s in sorted(rows, key=lambda r: r.get("i", 0)):
                key = hashlib.sha256(f"specrl:{stem}:{s['i']}:{s['reply']}".encode("utf-8")).hexdigest()
                row = scache.get(key)
                if row is None:
                    continue
                sig, proof = row["signals"], row["proof"]
                stage = sig["stage"]
                t = ("none" if stage in ("no-block", "parse", "spec-changed", "no-gate-row")
                     else "parses" if stage == "wf"
                     else "proved" if proof == rl_reward.CLEAN else "typed")
                stier_counts[t] = stier_counts.get(t, 0) + 1
                if t == "proved" and winner is None:
                    winner = s
            if winner is not None:
                original = json.loads(Path(gated_rows[stem]["task_file"]).read_text(encoding="utf-8"))
                block = with_t_header(se.find_block(winner["reply"]), original)
                # A clean, stable name for the final corpus document (not the
                # hash-suffixed working name score-spec used to keep concurrent
                # candidates for the same stem distinct while proving).
                task = se.rename_task(surface.parse(block), f"vericoding_{stem}")
                shortlist_spec[task["name"]] = (task, {"stem": stem, "source": winner.get("source"),
                                                       "sample_index": winner["i"], "reward_tier": "proved",
                                                       "reward": SPEC_TIERS["proved"]})
    report["specpool"] = {"prompts": n_spec_prompts, "samples": n_spec_samples, "tiers": stier_counts,
                          "top_tier_answers": len(shortlist_spec)}

    # -- second stage: all seven kernels on the shortlist alone --
    training_tasks = {name: t for name, (t, _p) in shortlist_training.items()}
    spec_tasks = {name: t for name, (t, _p) in shortlist_spec.items()}
    training_dest = dest_root / a.dest_tag
    spec_dest = Path(a.dest_specpool_dir)
    training_rows = full_kernel_grade(training_tasks, training_dest, jobs=a.jobs, host=host)
    spec_rows = full_kernel_grade(spec_tasks, spec_dest, jobs=a.jobs, host=host)

    def admit(rows: dict[str, dict[str, str]]) -> dict[str, dict]:
        out = {}
        for name, row in rows.items():
            n = clean_count(row)
            if n >= 6:
                out[name] = {"clean": n, "gap": gap_kernels(row) if n == 6 else []}
        return out

    training_admitted = admit(training_rows)
    spec_admitted = admit(spec_rows)
    report["training"]["kernels7"] = {"graded": len(training_rows),
                                      "clean7": sum(1 for r in training_rows.values() if clean_count(r) == 7),
                                      "clean6": sum(1 for r in training_rows.values() if clean_count(r) == 6),
                                      "admitted": len(training_admitted)}
    report["specpool"]["kernels7"] = {"graded": len(spec_rows),
                                      "clean7": sum(1 for r in spec_rows.values() if clean_count(r) == 7),
                                      "clean6": sum(1 for r in spec_rows.values() if clean_count(r) == 6),
                                      "admitted": len(spec_admitted)}

    # -- write the admitted training-problem answers as spec_experiment's own raw/ shape --
    (training_dest / "raw").mkdir(parents=True, exist_ok=True)
    for name in training_admitted:
        task, prov = shortlist_training[name]
        tag = prov.get("sample_tag")
        tid = prov["task_id"]
        src = HERE / "out" / "spec-experiment" / str(tag) / "raw" / f"{tid}.json"
        rec = json.loads(src.read_text(encoding="utf-8")) if src.exists() else {"task_id": tid, "reply": ""}
        rec["expert_iteration"] = {**prov, "clean_kernels": training_admitted[name]["clean"],
                                   "gap": training_admitted[name]["gap"]}
        (training_dest / "raw" / f"{tid}.json").write_text(json.dumps(rec, indent=1), encoding="utf-8")
    for name in list(training_rows):
        if name not in training_admitted:
            (training_dest / "tasks" / f"{name}.json").unlink(missing_ok=True)

    # -- write the admitted spec-pool answers as corpus-format documents, the
    # same head (Problem:/Signature:) t/rl_spec_pool.spec_prompt gives every
    # spec prompt, so these read like any other corpus document --
    import head_align_corpus
    manifest = []
    doc_lines = []
    for name in spec_admitted:
        task, prov = shortlist_spec[name]
        stem = prov["stem"]
        description = gated_rows.get(stem, {}).get("description", "")
        doc = surface.print_task(task)
        head = f"Problem: {' '.join(description.split())}\n" + head_align_corpus.head_for(task)
        text = head + doc
        doc_lines.append(text)
        manifest.append({"name": name, **prov, "clean_kernels": spec_admitted[name]["clean"],
                         "gap": spec_admitted[name]["gap"]})
    # full_kernel_grade returns early for an empty shortlist and creates nothing, so a round with no
    # specification prompts (Bedrock round 3, 2026-10-04) reached this write with no directory and
    # lost its report after grading every training answer.
    spec_dest.mkdir(parents=True, exist_ok=True)
    (spec_dest / "documents.txt").write_text("\n\n".join(doc_lines) + ("\n" if doc_lines else ""),
                                             encoding="utf-8")
    (spec_dest / "manifest.jsonl").write_text("".join(json.dumps(m) + "\n" for m in manifest), encoding="utf-8")

    report_path = Path(a.report)
    report_path.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report, indent=1))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("sample-spec")
    p.add_argument("--out", required=True)
    p.add_argument("--prompts", required=True)
    p.add_argument("--host", required=True)
    p.add_argument("--model", default="qwen3.8-27b-fp8")
    p.add_argument("--k", type=int, default=8)
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--seed-base", type=int, default=1)
    p.add_argument("--tokens", type=int, default=1024)
    p.add_argument("--timeout", type=float, default=1800.0)
    p.add_argument("--jobs", type=int, default=8)

    p = sub.add_parser("score-spec")
    p.add_argument("--out", required=True)
    p.add_argument("--gated", required=True)
    p.add_argument("--jobs", type=int, default=2)
    p.add_argument("--local", action="store_true")

    p = sub.add_parser("consolidate-training")
    p.add_argument("--out", required=True)
    p.add_argument("--tags", nargs="+", required=True)

    p = sub.add_parser("assemble")
    p.add_argument("--spec-out", required=True)
    p.add_argument("--gated", required=True)
    p.add_argument("--training-out", required=True)
    p.add_argument("--pool", default="v5")
    p.add_argument("--dest-root", default=str(HERE / "out" / "spec-experiment"))
    p.add_argument("--dest-tag", default="rl-teacher-verified")
    p.add_argument("--dest-specpool-dir", required=True)
    p.add_argument("--report", default=str(HERE / "out" / "rl-2026-09-26" / "teacher" / "assemble-report.json"))
    p.add_argument("--jobs", type=int, default=2)
    p.add_argument("--local", action="store_true")

    a = ap.parse_args(argv)
    return {"sample-spec": cmd_sample_spec, "score-spec": cmd_score_spec,
            "consolidate-training": cmd_consolidate_training, "assemble": cmd_assemble}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
