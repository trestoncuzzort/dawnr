#!/usr/bin/env python3
"""t/rl_grpo.py -- Group Relative Policy Optimization for locallm, with the proof engine as the reward (2026-09-26).

    T_LAB=user@host ~/.venv-locallm/bin/python t/rl_grpo.py --model DIR --out OUT --ids-file IDS.json \
        --steps 24 --prompts-per-step 8 --group 16 --lr 2e-6 --beta 0.04 --clip 0.2

GRPO as DeepSeekMath defines it (arXiv:2402.03300, section 4.1, equations 3 and 4,
outcome supervision 4.1.2), in locallm's own model code because TRL and vLLM do
not load a custom GPT:

  * for each prompt, G answers are sampled from the current policy (pi_old);
  * each answer's reward comes from t/rl_reward.py, run in a SUBPROCESS so no
    interpreter or reference solution runs inside the GPU process, with Dafny on
    the lab;
  * every token of answer i gets the advantage (r_i - mean(r)) / std(r) over its
    group; a group whose G rewards are equal has no signal and is skipped (the
    dynamic-sampling filter of DAPO, arXiv:2503.14476);
  * the objective is the clipped ratio pi_theta / pi_old times the advantage,
    minus beta times the per-token KL to the frozen starting policy, estimated
    with the unbiased k3 estimator  pi_ref/pi_theta - log(pi_ref/pi_theta) - 1
    (Schulman 2020, eq. 4), averaged over an answer's tokens and then over answers.

The paper's DeepSeekMath-RL setting was lr 1e-6, KL coefficient 0.04, 64 samples,
one policy update per exploration stage (mu = 1); the defaults follow it except G.

Sequences are capped at the context the policy was fine-tuned on (512 tokens:
its run.json block_size), so the answer budget is 512 minus the prompt.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

import torch
import torch.nn.functional as F

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "locallm"))

import rl_reward                                                # noqa: E402
import spec_experiment as se                                    # noqa: E402


# ----------------------------------------------------------------- the loss --

def group_advantages(rewards: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    """(r - mean) / std within each row of a (groups, G) reward tensor; a row
    whose rewards are all equal gets advantage 0 everywhere (not a division by 0)."""
    mean = rewards.mean(dim=1, keepdim=True)
    std = rewards.std(dim=1, keepdim=True)
    adv = (rewards - mean) / (std + eps)
    return torch.where(std > 0, adv, torch.zeros_like(adv))


def grpo_loss(logp: torch.Tensor, old_logp: torch.Tensor, ref_logp: torch.Tensor,
              adv: torch.Tensor, mask: torch.Tensor, *, clip: float, beta: float):
    """Negative GRPO objective (eq. 3) for N answers padded to T tokens.

    logp, old_logp, ref_logp, mask: (N, T); adv: (N,). Each answer's token terms
    are averaged over its own tokens (1/|o_i|), then over answers (1/G per group,
    with every group the same size). Returns (loss, stats)."""
    mask = mask.to(logp.dtype)
    ratio = torch.exp(logp - old_logp)
    a = adv[:, None]
    surrogate = torch.minimum(ratio * a, torch.clamp(ratio, 1 - clip, 1 + clip) * a)
    log_ref_over = ref_logp - logp
    kl = torch.exp(log_ref_over) - log_ref_over - 1
    per_token = surrogate - beta * kl
    lengths = mask.sum(dim=1).clamp(min=1)
    per_answer = (per_token * mask).sum(dim=1) / lengths
    loss = -per_answer.mean()
    with torch.no_grad():
        kl_mean = ((kl * mask).sum(dim=1) / lengths).mean()
        clipped = (((ratio - 1).abs() > clip).to(logp.dtype) * mask).sum() / mask.sum().clamp(min=1)
    return loss, {"kl": float(kl_mean), "clip_frac": float(clipped)}


def token_logprobs(model, seqs: torch.Tensor, starts: list[int], ends: list[int]):
    """log p(token_t | tokens_<t) at every position t in [start, end) of each row
    of a right-padded (N, L) id tensor; returns (logp, mask), both (N, L-1),
    aligned so column j scores token j+1."""
    logits, _ = model(seqs)
    logp = torch.log_softmax(logits[:, :-1].float(), dim=-1).gather(2, seqs[:, 1:, None])[..., 0]
    pos = torch.arange(1, seqs.size(1), device=seqs.device)[None, :]
    s = torch.tensor(starts, device=seqs.device)[:, None]
    e = torch.tensor(ends, device=seqs.device)[:, None]
    mask = (pos >= s) & (pos < e)
    return logp, mask


# ------------------------------------------------------------------- driver --

def save_policy(model, src_dir: Path, dst: Path) -> None:
    """A checkpoint locallm/checkpoint.load_checkpoint reads: the source's dict
    with the weights replaced and no optimizer state, plus its tokenizer."""
    dst.mkdir(parents=True, exist_ok=True)
    ck = torch.load(src_dir / "ckpt.pt", map_location="cpu", weights_only=True)
    ck.pop("optimizer", None)
    ck["model"] = {k: v.detach().cpu() for k, v in model.state_dict().items()}
    torch.save(ck, dst / "ckpt.pt")
    shutil.copy(src_dir / "tokenizer.json", dst / "tokenizer.json")


def score(out: Path, step: int, items: list[dict], jobs: int) -> list[dict]:
    """t/rl_reward.py in a subprocess; one result per item, in order."""
    d = out / "steps"
    d.mkdir(parents=True, exist_ok=True)
    src, dst = d / f"{step:04d}-items.jsonl", d / f"{step:04d}-rewards.jsonl"
    src.write_text("".join(json.dumps(i) + "\n" for i in items), encoding="utf-8")
    subprocess.run([sys.executable, str(HERE / "rl_reward.py"), str(src), str(dst), "--cache",
                    str(out / "rewards-cache.jsonl"), "--jobs", str(jobs), "--batch", f"grpo-{step}"], check=True)
    return [json.loads(line) for line in dst.read_text(encoding="utf-8").splitlines() if line.strip()]


def main(argv=None) -> int:
    import checkpoint
    import loop_locallm
    import pilot_sampling
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--ids-file", required=True, type=Path, help="JSON list of RL prompt ids (training problems)")
    ap.add_argument("--split", type=Path, default=rl_reward.SPLIT)
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--prompts-per-step", type=int, default=8)
    ap.add_argument("--group", type=int, default=16)
    ap.add_argument("--temperature", type=float, default=0.8)
    ap.add_argument("--top-k", type=int, default=20)
    ap.add_argument("--context", type=int, default=512)
    ap.add_argument("--lr", type=float, default=2e-6)
    ap.add_argument("--beta", type=float, default=0.04)
    ap.add_argument("--clip", type=float, default=0.2)
    ap.add_argument("--mu", type=int, default=1, help="policy updates per sampled batch")
    ap.add_argument("--micro", type=int, default=16, help="answers per forward/backward")
    ap.add_argument("--jobs", type=int, default=2, help="run_par cells in flight on the lab")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--save-every", type=int, default=0)
    a = ap.parse_args(argv)

    split = json.loads(a.split.read_text(encoding="utf-8"))
    pool = se.pool(split.get("pool", "v1"))
    allowed = set(rl_reward.rl_prompt_ids(a.split, pool))
    ids = [int(i) for i in json.loads(a.ids_file.read_text(encoding="utf-8"))]
    if set(ids) - allowed:
        raise SystemExit(f"rl_grpo: ids outside the RL prompt set: {sorted(set(ids) - allowed)[:5]}")
    a.out.mkdir(parents=True, exist_ok=True)
    torch.manual_seed(a.seed)
    policy, tok, _cfg = checkpoint.load_checkpoint(a.model)
    ref, _tok, _ = checkpoint.load_checkpoint(a.model)
    for p in ref.parameters():
        p.requires_grad_(False)
    ref.eval()
    device = next(policy.parameters()).device
    opt = torch.optim.AdamW(policy.parameters(), lr=a.lr, betas=(0.9, 0.95), weight_decay=0.0)
    (a.out / "config.json").write_text(json.dumps({**{k: str(v) for k, v in vars(a).items()},
                                                    "prompts": len(ids)}, indent=1), encoding="utf-8")
    log = open(a.out / "log.jsonl", "a", encoding="utf-8")
    order = random.Random(a.seed)
    queue: list[int] = []
    for step in range(1, a.steps + 1):
        t0 = time.time()
        batch = []
        while len(batch) < a.prompts_per_step:
            if not queue:
                queue = ids[:]
                order.shuffle(queue)
            batch.append(queue.pop())
        # ---- explore: G answers per prompt from pi_old
        policy.eval()
        groups = []
        for tid in batch:
            head = loop_locallm.problem_head(pool[tid])
            prompt_ids = tok.encode(head)
            budget = a.context - len(prompt_ids)
            g = torch.Generator(device=device)
            g.manual_seed(pilot_sampling.derive_seed(a.seed * 100003 + step, tid, a.temperature))
            rows = checkpoint.sample_batch(policy, tok, head, a.group, tokens=budget, temperature=a.temperature,
                                           top_k=a.top_k, stop=loop_locallm.reply_stop(head), generator=g)
            groups.append((tid, head, prompt_ids, rows))
        t_sample = time.time() - t0
        items = [{"task_id": tid, "reply": "```t\n" + pilot_sampling.extract_reply(head, r["text"]) + "\n```"}
                 for tid, head, _p, rows in groups for r in rows]
        results = score(a.out, step, items, a.jobs)
        t_score = time.time() - t0 - t_sample
        rewards = torch.tensor([r["reward"] for r in results], dtype=torch.float32).view(len(groups), a.group)
        adv = group_advantages(rewards)
        live = [gi for gi in range(len(groups)) if rewards[gi].std() > 0]
        tiers = {}
        for r in results:
            tiers[r["tier"]] = tiers.get(r["tier"], 0) + 1
        stats = {"step": step, "reward_mean": float(rewards.mean()), "tiers": tiers,
                 "groups_live": len(live), "groups": len(groups), "prompts": batch,
                 "tests_or_better": sum(r["tier"] in ("tests", "proved") for r in results),
                 "proved": sum(r["tier"] == "proved" for r in results),
                 "mean_new_tokens": sum(len(r["tokens"]) for *_x, rows in groups for r in rows) / len(items)}
        # ---- learn: the clipped surrogate minus beta KL, over the live groups only
        seqs, starts, ends, advs = [], [], [], []
        for gi in live:
            _tid, _head, prompt_ids, rows = groups[gi]
            for j, r in enumerate(rows):
                full = (prompt_ids + r["tokens"])[: a.context]
                seqs.append(full)
                starts.append(len(prompt_ids))
                ends.append(len(full))
                advs.append(float(adv[gi, j]))
        kl_sum = clip_sum = loss_sum = 0.0
        n_micro = 0
        if seqs:
            policy.train()
            old_cache = {}                     # pi_old: the policy that sampled, fixed across the mu updates
            for _it in range(a.mu):
                order_idx = list(range(len(seqs)))
                opt.zero_grad(set_to_none=True)
                for m in range(0, len(seqs), a.micro):
                    idx = order_idx[m:m + a.micro]
                    width = max(len(seqs[i]) for i in idx)
                    x = torch.zeros(len(idx), width, dtype=torch.long, device=device)
                    for row, i in enumerate(idx):
                        x[row, :len(seqs[i])] = torch.tensor(seqs[i], device=device)
                    st = [starts[i] for i in idx]
                    en = [ends[i] for i in idx]
                    with torch.no_grad():
                        ref_logp, _ = token_logprobs(ref, x, st, en)
                        if m not in old_cache:
                            policy.eval()
                            old_cache[m], _ = token_logprobs(policy, x, st, en)
                            policy.train()
                    logp, mask = token_logprobs(policy, x, st, en)
                    loss, s = grpo_loss(logp, old_cache[m], ref_logp,
                                        torch.tensor([advs[i] for i in idx], device=device), mask,
                                        clip=a.clip, beta=a.beta)
                    (loss * len(idx) / len(seqs)).backward()
                    kl_sum += s["kl"] * len(idx)
                    clip_sum += s["clip_frac"] * len(idx)
                    loss_sum += float(loss) * len(idx)
                    n_micro += len(idx)
                torch.nn.utils.clip_grad_norm_(policy.parameters(), 1.0)
                opt.step()
        stats.update(kl=kl_sum / n_micro if n_micro else None, clip_frac=clip_sum / n_micro if n_micro else None,
                     loss=loss_sum / n_micro if n_micro else None, answers_trained=len(seqs),
                     seconds={"sample": round(t_sample, 1), "score": round(t_score, 1),
                              "total": round(time.time() - t0, 1)})
        log.write(json.dumps(stats) + "\n")
        log.flush()
        print(f"step {step}: reward {stats['reward_mean']:.3f} tests+ {stats['tests_or_better']} "
              f"proved {stats['proved']} live {len(live)}/{len(groups)} kl {stats['kl']} "
              f"({stats['seconds']['total']} s)", flush=True)
        if a.save_every and step % a.save_every == 0:
            save_policy(policy, a.model, a.out / f"policy-step-{step}")
    save_policy(policy, a.model, a.out / "policy-final")
    log.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
