#!/usr/bin/env python3
"""t/rl_student.py: GRPO on the pretrained student, the gate's tiers as the reward (2026-10-01).

    python3 t/rl_student.py band  --model DIR --out OUT [--n 800 --k 4 --seed 1]
    python3 t/rl_student.py train --model DIR --out OUT [--epochs 2]
    python3 t/rl_student.py report --out OUT

Registered in t/PREDICT-2026-10-01-rl-on-the-student.md; the design is t/RL-DESIGN-2026-09-26.md (sections 7
and 9). The update is GRPO (DeepSeekMath, arXiv:2402.03300, 4.1.2) with Dr. GRPO's mean-only advantage and
constant normaliser (arXiv:2503.20783), run by TRL's GRPOTrainer (`loss_type="dr_grpo"`, `scale_rewards="none"`,
huggingface.co/docs/trl/grpo_trainer), a LoRA adapter on the merged student, the frozen student as the KL
reference (TRL disables the adapter for it). The reward is t/rl_reward.py version 3, the answer extracted as
every student answer is (header promotion), Dafny on the lab for the answers that can reach the top tiers.

`band` picks the problems: n training problems drawn by a fixed seed from rl_reward.rl_prompt_ids, minus the
ones whose function shares a name with a held-out specification-given question and the ones in the
student's own rows; k samples each through t/student_generate.py (temperature 0.7, top-p 0.95, prompt s2);
the difficulty band of STP and PSV is the problems with one or two of k passing the tests tier, widened to
three of k if that leaves fewer than 40, and the run stops if it still does.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import rl_reward                                                # noqa: E402
import spec_experiment as se                                    # noqa: E402

HELD_QUESTIONS = Path.home() / "scratch/pool-levels/spec-given-heldout.jsonl"
MIN_BAND = 40


def held_question_fns(path: Path = HELD_QUESTIONS) -> set[str]:
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return {r["name"].split("__", 1)[-1] for r in rows}


def candidate_ids(pool: dict, rows_file: Path, held_fns: set[str]) -> dict[str, list[int]]:
    """The RL prompt set split: problems in the student's rows (`rows`) and the rest (`other`), with every
    problem whose function shares a held-out question's name left out of both."""
    in_rows = {int(json.loads(l)["task_id"]) for l in rows_file.read_text().splitlines()
               if l.strip() and json.loads(l).get("task_id") is not None}
    ids = [i for i in rl_reward.rl_prompt_ids(pool=pool) if pool[i]["fn"] not in held_fns]
    return {"rows": [i for i in ids if i in in_rows], "other": [i for i in ids if i not in in_rows]}


def band_of(passes: dict[int, int], k: int, min_band: int = MIN_BAND) -> tuple[list[int], str]:
    """STP/PSV's difficulty band: problems that pass sometimes but seldom."""
    narrow = sorted(i for i, n in passes.items() if 1 <= n <= 2)
    if len(narrow) >= min_band:
        return narrow, f"1 or 2 of {k}"
    wide = sorted(i for i, n in passes.items() if 1 <= n <= min(3, k - 1))
    if len(wide) >= min_band:
        return wide, f"1 to 3 of {k}"
    return [], f"fewer than {min_band} problems pass 1 to 3 of {k}: {len(wide)}"


def cmd_band(a) -> int:
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    P = se.pool("v5")
    cands = candidate_ids(P, Path(a.rows), held_question_fns())
    rnd = random.Random(a.seed)
    drawn = sorted(rnd.sample(cands["other"], min(a.n, len(cands["other"]))))
    (out / "band-ids.txt").write_text("\n".join(map(str, drawn)) + "\n")
    prefix = f"rlband-{Path(a.model).name}"
    cmd = [sys.executable, str(HERE / "student_generate.py"), "--model", a.model, "--tag-prefix", prefix,
           "--seeds", *map(str, range(1, a.k + 1)), "--pool", "v5", "--prompt", "s2", "--ids-file",
           str(out / "band-ids.txt"), "--temperature", "0.7", "--top-p", "0.95", "--batch", str(a.batch)]
    if not a.skip_generate:
        subprocess.run(cmd, check=True)
    passes: dict[int, int] = {i: 0 for i in drawn}
    tiers: dict[str, int] = {}
    for s in range(1, a.k + 1):
        raw = HERE / "out" / "spec-experiment" / f"{prefix}-s{s}" / "raw"
        for f in raw.glob("*.json"):
            rec = json.loads(f.read_text(encoding="utf-8"))
            tid = int(rec["task_id"])
            if tid not in passes:
                continue
            sig = rl_reward.local_signals(tid, rec["reply"], P[tid], promote_header=True)
            t = "tests" if rl_reward.tests_ok(sig) else rl_reward.tier(sig)
            tiers[t] = tiers.get(t, 0) + 1
            passes[tid] += t == "tests"
    ids, rule = band_of(passes, a.k)
    rep = {"model": a.model, "drawn": len(drawn), "k": a.k, "seed": a.seed, "candidates": {k: len(v) for k, v in cands.items()},
           "sample tiers": tiers, "problems with a pass": sum(1 for n in passes.values() if n),
           "pass counts": {str(n): sum(1 for v in passes.values() if v == n) for n in range(a.k + 1)},
           "rule": rule, "band": ids}
    (out / "band.json").write_text(json.dumps(rep, indent=1) + "\n")
    print(json.dumps({k: v for k, v in rep.items() if k != "band"}), flush=True)
    return 0 if ids else 3


def cmd_train(a) -> int:
    import torch
    from datasets import Dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import GRPOConfig, GRPOTrainer
    out = Path(a.out)
    P = se.pool("v5")
    band = json.loads((out / "band.json").read_text())["band"]
    ds = Dataset.from_list([{"prompt": se.build_prompt(P[i], "s2"), "task_id": i} for i in band])
    cache = rl_reward.RewardCache(out / "rewards-cache.jsonl")
    log_path = out / "rewards.jsonl"
    state = {"call": 0}

    def gate_reward(prompts, completions, task_id, **kw):
        state["call"] += 1
        replies = [c[-1]["content"] if isinstance(c, list) else c for c in completions]
        rows = rl_reward.score_many(list(zip((int(t) for t in task_id), replies)), P, cache, promote_header=True,
                                    jobs=a.prove_jobs, batch=f"rl-{os.getpid()}-{state['call']}")
        with log_path.open("a", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps({"call": state["call"], "time": time.time(), "task_id": r["task_id"],
                                    "tier": r["tier"], "reward": r["reward"]}) + "\n")
        return [r["reward"] for r in rows]

    tok = AutoTokenizer.from_pretrained(a.model)
    model = AutoModelForCausalLM.from_pretrained(a.model, dtype=torch.bfloat16, device_map={"": 0})
    cfg = GRPOConfig(
        output_dir=str(out / "trainer"), learning_rate=a.lr, beta=a.beta, loss_type="dr_grpo", scale_rewards="none",
        num_generations=a.group, max_completion_length=a.max_new, temperature=0.7, top_p=0.95,
        per_device_train_batch_size=a.micro, gradient_accumulation_steps=a.group * a.prompts_per_step // a.micro,
        num_train_epochs=a.epochs, gradient_checkpointing=True, bf16=True, logging_steps=1, save_strategy="steps",
        save_steps=a.save_steps, save_total_limit=2, report_to=[], seed=a.seed, mask_truncated_completions=True,
        chat_template_kwargs={"enable_thinking": False}, log_completions=False)
    peft = LoraConfig(r=a.rank, lora_alpha=a.alpha, lora_dropout=0.0, bias="none", target_modules="all-linear",
                      task_type="CAUSAL_LM")
    trainer = GRPOTrainer(model=model, reward_funcs=gate_reward, args=cfg, train_dataset=ds,
                          processing_class=tok, peft_config=peft)
    resume = any((out / "trainer").glob("checkpoint-*"))
    trainer.train(resume_from_checkpoint=resume or None)
    trainer.save_model(str(out / "adapter"))
    tok.save_pretrained(str(out / "adapter"))
    (out / "train-log.json").write_text(json.dumps(trainer.state.log_history, indent=1) + "\n")
    return 0


def cmd_report(a) -> int:
    out = Path(a.out)
    band = json.loads((out / "band.json").read_text())
    rows = [json.loads(l) for l in (out / "rewards.jsonl").read_text().splitlines() if l.strip()]
    calls = sorted({r["call"] for r in rows})
    half = len(calls) // 2
    first = [r for r in rows if r["call"] in set(calls[:half])]
    second = [r for r in rows if r["call"] in set(calls[half:])]
    mean = lambda rs: sum(r["reward"] for r in rs) / len(rs) if rs else 0.0
    tiers = lambda rs: {t: sum(1 for r in rs if r["tier"] == t) for t in rl_reward.ORDER}
    rep = {"band": len(band["band"]), "rule": band["rule"], "calls": len(calls), "answers": len(rows),
           "first pass mean reward": round(mean(first), 4), "second pass mean reward": round(mean(second), 4),
           "first pass tiers": tiers(first), "second pass tiers": tiers(second)}
    print(json.dumps(rep, indent=1))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("band")
    b.add_argument("--model", required=True); b.add_argument("--out", required=True)
    b.add_argument("--rows", required=True, help="the student's training rows (jsonl with task_id)")
    b.add_argument("--n", type=int, default=800); b.add_argument("--k", type=int, default=4)
    b.add_argument("--seed", type=int, default=1); b.add_argument("--batch", type=int, default=16)
    b.add_argument("--skip-generate", action="store_true")
    t = sub.add_parser("train")
    t.add_argument("--model", required=True); t.add_argument("--out", required=True)
    t.add_argument("--epochs", type=float, default=2); t.add_argument("--lr", type=float, default=5e-6)
    t.add_argument("--beta", type=float, default=0.04); t.add_argument("--group", type=int, default=8)
    t.add_argument("--prompts-per-step", type=int, default=2); t.add_argument("--micro", type=int, default=2)
    t.add_argument("--max-new", type=int, default=1024); t.add_argument("--rank", type=int, default=64)
    t.add_argument("--alpha", type=int, default=16); t.add_argument("--save-steps", type=int, default=10)
    t.add_argument("--prove-jobs", type=int, default=2); t.add_argument("--seed", type=int, default=1)
    r = sub.add_parser("report"); r.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    return {"band": cmd_band, "train": cmd_train, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
