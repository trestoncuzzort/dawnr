#!/usr/bin/env python3
"""t/dawnr_token_budget.py -- token budgets for dawnr's general-English layer (2026-09-26).

Two data:model ratios from the literature, applied to two locallm sizes:

- Chinchilla (Hoffmann et al. 2022, arXiv:2203.15556): compute-optimal training
  scales tokens and parameters together; the paper's own recommended operating
  point is close to 20 tokens per parameter, the number every later paper
  (including the one below) calls "the Chinchilla-optimal heuristic."
- MiniCPM (Hu et al. 2024, arXiv:2404.06395): "model wind tunnel" scaling-law
  experiments on small proxy models fit a compute-optimal data:model ratio of
  about 192:1, "nearly 10x more data per parameter than Chinchilla's 20:1,"
  i.e. a small model safely absorbs far more data relative to its size than
  the Chinchilla heuristic suggests.

dawnr is not compute constrained on tokens the way Chinchilla's regime
assumes -- AMBITION.md's framing is that data is the limit, not compute -- so
both ratios are reported as a range: Chinchilla as the conservative floor,
MiniCPM as the data-rich ceiling a small model can still absorb safely.

The two sizes are locallm's own measured points
(locallm/FINDINGS-capacity-2026-09-19.md): the r12 core actually in use
(92,920,320 parameters, internal/PRETRAIN-R12-2026-09-25.md) and the 312M
step already measured to train on one shared card (311,224,320 parameters).
"""
import argparse
import json

CHINCHILLA_RATIO = 20
MINICPM_RATIO = 192

SIZES = {
    "core-92.9M": 92_920_320,   # internal/PRETRAIN-R12-2026-09-25.md
    "312M": 311_224_320,        # locallm/FINDINGS-capacity-2026-09-19.md
}

# The core's actual pretraining corpus today, for the "how far below the floor
# are we" number (locallm/FINDINGS-capacity-2026-09-19.md: "153 MB of training
# text, about 46M BPE tokens"; the exact count from the study's own record,
# internal/PRETRAIN-R12-2026-09-25.md, is used here).
CURRENT_CORPUS_TOKENS = 48_798_892


def budgets() -> list[dict]:
    rows = []
    for name, params in SIZES.items():
        chinchilla = params * CHINCHILLA_RATIO
        minicpm = params * MINICPM_RATIO
        rows.append({
            "model": name,
            "parameters": params,
            "chinchilla_20to1_tokens": chinchilla,
            "minicpm_192to1_tokens": minicpm,
            "current_code_corpus_ratio": round(CURRENT_CORPUS_TOKENS / params, 4),
        })
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    a = ap.parse_args()
    rows = budgets()
    if a.json:
        print(json.dumps(rows, indent=1))
        return
    print(f"{'model':<12} {'params':>13} {'chinchilla 20:1':>18} {'minicpm 192:1':>18} {'current corpus ratio':>22}")
    for r in rows:
        print(f"{r['model']:<12} {r['parameters']:>13,} "
              f"{r['chinchilla_20to1_tokens']:>15,} tok "
              f"{r['minicpm_192to1_tokens']:>15,} tok "
              f"{r['current_code_corpus_ratio']:>21}:1")


if __name__ == "__main__":
    main()
