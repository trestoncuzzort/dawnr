#!/usr/bin/env python3
"""t/rl_feasibility.py -- can GRPO start from this policy? (2026-09-26)

    ~/.venv-locallm/bin/python t/rl_feasibility.py sample --model DIR --out OUT --k 16 --temperature 0.8
    python3 t/rl_feasibility.py score  --out OUT            # CPU here, Dafny on the lab
    python3 t/rl_feasibility.py report --out OUT [--json]

GRPO (arXiv:2402.03300 section 4.1.2) normalises each reward by its group's
mean and standard deviation, so a group whose G answers all score the same has
zero advantage everywhere and teaches nothing. Before any training this measures,
on the RL prompt set (training problems only, t/rl_reward.rl_prompt_ids), how
often a group of k samples has any spread at each tier of t/rl_reward.py.

The prompt, the stop and the reply extraction are cmd_generate's
(t/loop_locallm.py problem_head, reply_stop; t/pilot_sampling.extract_reply),
and the k rows of a problem are decoded together by locallm/checkpoint.sample_batch
seeded from (seed, task id) as pilot_sampling.derive_seed does.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import rl_reward                                                # noqa: E402
import spec_experiment as se                                    # noqa: E402

ORDER = rl_reward.ORDER


def reply_record(head: str, text: str) -> str:
    """The reply exactly as cmd_generate stores it, fenced."""
    import pilot_sampling
    return "```t\n" + pilot_sampling.extract_reply(head, text) + "\n```"


def cmd_sample(a) -> int:
    import torch
    sys.path.insert(0, str(HERE.parent / "locallm"))
    import checkpoint
    import loop_locallm
    import pilot_sampling
    split = json.loads(Path(a.split).read_text(encoding="utf-8"))
    pool = se.pool(split.get("pool", "v1"))
    ids = rl_reward.rl_prompt_ids(Path(a.split), pool)
    if a.limit:
        ids = ids[: a.limit]
    out = Path(a.out) / "samples"
    out.mkdir(parents=True, exist_ok=True)
    model, tok, _cfg = checkpoint.load_checkpoint(a.model)
    options = {"k": a.k, "temperature": a.temperature, "top_k": a.top_k, "tokens": a.tokens, "seed": a.seed}
    for n, tid in enumerate(ids):
        path = out / f"{tid}.jsonl"
        if path.exists():
            continue
        head = loop_locallm.problem_head(pool[tid])
        g = torch.Generator(device=next(model.parameters()).device)
        g.manual_seed(pilot_sampling.derive_seed(a.seed, tid, a.temperature))
        rows = checkpoint.sample_batch(model, tok, head, a.k, tokens=a.tokens, temperature=a.temperature,
                                       top_k=a.top_k, stop=loop_locallm.reply_stop(head), generator=g)
        lines = [json.dumps({"task_id": tid, "i": i, "reply": reply_record(head, r["text"]),
                             "stopped": r["stopped"], "new_tokens": r["new_tokens"],
                             "mean_logprob": r["mean_logprob"], "options": options}) for i, r in enumerate(rows)]
        tmp = path.with_suffix(".tmp")
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.replace(tmp, path)
        if (n + 1) % 20 == 0:
            print(f"sample: {n + 1} of {len(ids)}", flush=True)
    print(f"sample: {len(ids)} problems x {a.k} into {out}")
    return 0


def load_samples(out: Path) -> dict[int, list[dict]]:
    groups: dict[int, list[dict]] = {}
    for p in sorted((out / "samples").glob("*.jsonl"), key=lambda p: int(p.stem)):
        groups[int(p.stem)] = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    return groups


def cmd_score(a) -> int:
    out = Path(a.out)
    split = json.loads(Path(a.split).read_text(encoding="utf-8"))
    pool = se.pool(split.get("pool", "v1"))
    allowed = set(rl_reward.rl_prompt_ids(Path(a.split), pool))
    groups = load_samples(out)
    bad = set(groups) - allowed
    if bad:
        raise SystemExit(f"score: samples for ids outside the RL prompt set: {sorted(bad)[:5]}")
    cache = rl_reward.RewardCache(out / "rewards.jsonl")
    items = [(tid, s["reply"]) for tid, rows in groups.items() for s in rows]
    host = "local" if a.local else None
    chunk = a.chunk
    for start in range(0, len(items), chunk):
        rl_reward.score_many(items[start:start + chunk], pool, cache, jobs=a.jobs, host=host,
                             batch=f"feas-{start}")
        print(f"score: {min(start + chunk, len(items))} of {len(items)}", flush=True)
    return 0


def report(out: Path) -> dict:
    groups = load_samples(out)
    cache = rl_reward.RewardCache(out / "rewards.jsonl")
    per = {}
    for tid, rows in groups.items():
        tiers = []
        for s in rows:
            row = cache.get(rl_reward.answer_key(tid, s["reply"]))
            if row is None:
                raise SystemExit(f"report: {tid} has an unscored sample; run score first")
            tiers.append(rl_reward.tier(row["signals"], row["proof"]))
        per[tid] = tiers
    n = len(per)
    k = max((len(t) for t in per.values()), default=0)
    res = {"problems": n, "k": k, "samples": sum(len(t) for t in per.values()), "tiers": {}}
    counts = collections.Counter(t for ts in per.values() for t in ts)
    res["sample_tier_counts"] = {t: counts.get(t, 0) for t in ORDER}
    for level in ORDER[1:]:
        at = ORDER.index(level)
        reach = [sum(ORDER.index(t) >= at for t in ts) for ts in per.values()]
        any_ = sum(r > 0 for r in reach)
        mixed = sum(0 < r < len(ts) for r, ts in zip(reach, per.values()))
        res["tiers"][level] = {"problems_any": any_, "frac_any": round(any_ / n, 4) if n else 0,
                               "groups_mixed": mixed, "frac_mixed": round(mixed / n, 4) if n else 0,
                               "sample_rate": round(sum(reach) / max(1, res["samples"]), 4)}
    nonzero = sum(len(set(rl_reward.TIERS[t] for t in ts)) > 1 for ts in per.values())
    res["composite_nonzero_variance"] = {"groups": nonzero, "frac": round(nonzero / n, 4) if n else 0}
    res["by_family"] = {}
    for fam, pred in (("mbpp", lambda i: i < se.HUMANEVAL_BASE),
                      ("humaneval", lambda i: se.HUMANEVAL_BASE <= i < se.APPS_BASE)):
        sub = {t: ts for t, ts in per.items() if pred(t)}
        res["by_family"][fam] = {"problems": len(sub),
                                 "any_tests": sum(any(ORDER.index(x) >= 3 for x in ts) for ts in sub.values()),
                                 "any_proved": sum(any(ORDER.index(x) >= 4 for x in ts) for ts in sub.values())}
    return res


def cmd_report(a) -> int:
    res = report(Path(a.out))
    if a.json:
        print(json.dumps(res, indent=1))
        return 0
    print(f"{res['problems']} problems x {res['k']} samples = {res['samples']} answers")
    print("sample tiers: " + ", ".join(f"{t} {c}" for t, c in res["sample_tier_counts"].items()))
    print("| tier (or better) | problems with any | fraction | groups with mixed outcomes | fraction | sample rate |")
    print("|---|---:|---:|---:|---:|---:|")
    for level, r in res["tiers"].items():
        print(f"| {level} | {r['problems_any']} | {r['frac_any']:.3f} | {r['groups_mixed']} | "
              f"{r['frac_mixed']:.3f} | {r['sample_rate']:.4f} |")
    c = res["composite_nonzero_variance"]
    print(f"composite reward: {c['groups']} of {res['problems']} groups have nonzero variance ({c['frac']:.3f})")
    print(f"by family: {res['by_family']}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("sample")
    p.add_argument("--model", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--split", default=str(rl_reward.SPLIT))
    p.add_argument("--k", type=int, default=16)
    p.add_argument("--temperature", type=float, required=True)
    p.add_argument("--top-k", type=int, default=20)
    p.add_argument("--tokens", type=int, default=1200)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--limit", type=int, default=0)
    p = sub.add_parser("score")
    p.add_argument("--out", required=True)
    p.add_argument("--split", default=str(rl_reward.SPLIT))
    p.add_argument("--jobs", type=int, default=2)
    p.add_argument("--chunk", type=int, default=2000)
    p.add_argument("--local", action="store_true", help="prove on this machine instead of the lab")
    p = sub.add_parser("report")
    p.add_argument("--out", required=True)
    p.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    return {"sample": cmd_sample, "score": cmd_score, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
