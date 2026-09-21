#!/usr/bin/env python3
"""locallm/soup.py -- average the weights of fine-tunes that share one pretrained core.

    python3 locallm/soup.py --out t/out/locallm-r11-soup \
        t/out/locallm-r11-rerun t/out/locallm-r11-s1 t/out/locallm-r11-s2 ...

A uniform model soup (Wortsman et al., "Model soups: averaging weights of
multiple fine-tuned models improves accuracy without increasing inference
time", arXiv:2203.05482; code github.com/mlfoundations/model-soups): theta =
mean(theta_i) over models fine-tuned from the SAME pretrained initialization.
It works because such fine-tunes sit in one low-error basin (Neyshabur et al.
2020, cited there), and it fails when an ingredient left the basin, which the
paper sees with high learning rates. locallm's fine-tunes move very little:
300 steps at lr 3e-5 from `gpt-seed1337`, and two of them differ by at most
0.0016 in any weight (measured 2026-09-21). The soup costs no inference time:
it is one model of the same size as each ingredient.

Why it is here. Dodge et al. (arXiv:2002.06305) measured that fine-tuning with
only the seed varied spreads out-of-sample scores widely, and locallm-r9 against
locallm-r10 (1 against 4 written clean answers, from a 1% corpus difference)
looks like exactly that. A soup attacks the spread rather than picking a lucky
seed, and picking a seed by its score on the 232 held-out problems would be
selecting on the test set. So this is the UNIFORM soup only: no ingredient is
chosen or weighted by any evaluation. The paper's greedy soup needs a held-out
validation signal, and the only one here is the eval set.

Refuses, rather than averages, ingredients that disagree on the config, the
tokenizer fingerprint, the pretrained core they started from, or the set of
tensor names: an average across two different models is not a soup of either.
Non-floating buffers must be identical in every ingredient and are copied.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import torch


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def init_of(d: Path) -> str | None:
    """The pretrained checkpoint an ingredient was fine-tuned from, per its run.json."""
    try:
        return json.loads((d / "run.json").read_text(encoding="utf-8"))["identities"]["init_ckpt_sha256"]
    except (OSError, ValueError, KeyError):
        return None


def average(checkpoints: list[dict]) -> dict:
    """The uniform soup of loaded ckpt.pt dicts: same keys out, model weights averaged."""
    first = checkpoints[0]
    for i, ck in enumerate(checkpoints[1:], 1):
        if ck["config"] != first["config"]:
            raise ValueError(f"ingredient {i} has a different config: {ck['config']} vs {first['config']}")
        if ck.get("tokenizer_fingerprint") != first.get("tokenizer_fingerprint"):
            raise ValueError(f"ingredient {i} has a different tokenizer fingerprint")
        if set(ck["model"]) != set(first["model"]):
            raise ValueError(f"ingredient {i} has different tensor names: "
                             f"{sorted(set(ck['model']) ^ set(first['model']))[:5]}")
    soup = {}
    for name, t0 in first["model"].items():
        if t0.is_floating_point():
            acc = torch.zeros_like(t0, dtype=torch.float32)
            for ck in checkpoints:
                acc += ck["model"][name].float()
            soup[name] = (acc / len(checkpoints)).to(t0.dtype)
        else:
            for i, ck in enumerate(checkpoints[1:], 1):
                if not torch.equal(ck["model"][name], t0):
                    raise ValueError(f"non-floating tensor {name} differs in ingredient {i}")
            soup[name] = t0.clone()
    out = {k: v for k, v in first.items() if k not in ("model", "optimizer")}
    out["model"] = soup
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("ingredients", nargs="+", type=Path)
    a = ap.parse_args()
    if len(a.ingredients) < 2:
        ap.error("a soup needs at least two ingredients")
    inits = {init_of(d) for d in a.ingredients}
    if len(inits) != 1 or None in inits:
        raise SystemExit(f"ingredients do not share one recorded pretrained core: {inits}")
    toks = {sha256(d / "tokenizer.json") for d in a.ingredients}
    if len(toks) != 1:
        raise SystemExit("ingredients carry different tokenizer.json files")
    cks = [torch.load(d / "ckpt.pt", map_location="cpu", weights_only=True) for d in a.ingredients]
    soup = average(cks)
    a.out.mkdir(parents=True, exist_ok=True)
    torch.save(soup, a.out / "ckpt.pt")
    shutil.copyfile(a.ingredients[0] / "tokenizer.json", a.out / "tokenizer.json")
    record = {"schema": 1, "kind": "uniform soup", "method": "arXiv:2203.05482",
              "init_ckpt_sha256": inits.pop(),
              "ingredients": [{"dir": str(d), "ckpt_sha256": sha256(d / "ckpt.pt")} for d in a.ingredients],
              "ckpt_sha256": sha256(a.out / "ckpt.pt")}
    (a.out / "soup.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    print(f"soup of {len(cks)} -> {a.out}/ckpt.pt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
