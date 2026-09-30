#!/usr/bin/env python3
"""t/stage_teacher_prompts.py -- the training-problem prompt ids for a teacher round.

    python3 t/stage_teacher_prompts.py --corpus t/out/loop/corpus-r12-headed.txt \\
        --out t/out/rl-2026-10-01/training-ids.txt [--apps 60] [--seed 2026]

t/EXPERT-ITERATION-2026-09-26.md section 1.2 staged the training-problem half of a teacher round
by hand: every id t/rl_reward.rl_prompt_ids allows (the split's train ids minus the held-out,
dev and decontamination exclusions), minus the problems whose answer is already in the policy's
fine-tuning corpus (named there, t/loop_filter.problem_ids_in) plus a seeded sample of the APPS
ids, which are non-corpus by construction. This writes that list to a file `spec_experiment.py
generate --ids-file` reads, one id per line, and prints the counts, so the staging is a command
that can be rerun rather than a paragraph. The loop it feeds is STaR's (arXiv:2203.14465) and
ReST-EM's (arXiv:2312.06585): sample, keep what an external check accepts, train on the kept set.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import loop_filter                                               # noqa: E402
import rl_reward                                                 # noqa: E402
import spec_experiment as se                                     # noqa: E402


def stage(corpus_text: str, ids: list[int], apps_base: int, apps: int, seed: int) -> dict:
    """The prompt ids: MBPP/HumanEval ids not named in the corpus, plus a seeded APPS sample."""
    named = set(loop_filter.problem_ids_in(corpus_text))
    mbpp_he = [i for i in ids if i < apps_base]
    apps_ids = [i for i in ids if i >= apps_base]
    out_corpus = [i for i in mbpp_he if i not in named]
    sample = sorted(random.Random(seed).sample(apps_ids, min(apps, len(apps_ids)))) if apps else []
    return {"mbpp_he_total": len(mbpp_he), "in_corpus": len(mbpp_he) - len(out_corpus),
            "out_corpus": len(out_corpus), "apps_available": len(apps_ids), "apps_sampled": len(sample),
            "ids": sorted(out_corpus + sample)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--corpus", type=Path, required=True, help="the policy's fine-tuning corpus text")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--split", type=Path, default=rl_reward.SPLIT)
    ap.add_argument("--apps", type=int, default=60, help="APPS ids to sample (0: none)")
    ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args(argv)
    pool = se.pool("v5")
    ids = rl_reward.rl_prompt_ids(a.split, pool=pool)
    r = stage(a.corpus.read_text(encoding="utf-8"), ids, se.APPS_BASE, a.apps, a.seed)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("".join(f"{i}\n" for i in r["ids"]), encoding="utf-8")
    a.out.with_suffix(".json").write_text(json.dumps({k: v for k, v in r.items() if k != "ids"} | {
        "corpus": str(a.corpus), "split": str(a.split), "seed": a.seed, "count": len(r["ids"])}, indent=1) + "\n")
    print(json.dumps({k: v for k, v in r.items() if k != "ids"} | {"count": len(r["ids"]), "out": str(a.out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
