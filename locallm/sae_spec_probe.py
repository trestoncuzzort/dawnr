"""sae_spec_probe.py: does a published sparse autoencoder find a feature in the student that tracks whether a
specification is right? (2026-10-01)

    python3 locallm/sae_spec_probe.py --model DIR --sae layer12.sae.pt --layer 12 --answers answers.jsonl --out report.json

Qwen-Scope (huggingface.co/Qwen/SAE-Res-Qwen3.5-2B-Base-W32K-L0_50; arXiv:2605.11887): TopK sparse autoencoders,
k = 50 of 32,768 features, on the residual stream after each of Qwen3.5-2B-Base's 24 layers (the output of
`model.model.layers[i]`, not normalised): pre = x W_enc^T + b_enc, keep the top 50, x_hat = a W_dec^T + b_dec.
Kissane, Krzyzanowski, Conmy and Nanda ("SAEs (usually) Transfer Between Base and Chat Models", 2024) found
middle-layer base-model SAEs reconstruct the fine-tuned model's activations about as well, except for the rare
outlier-norm positions, so the transfer is measured here first: the fraction of variance the SAE explains on the
fine-tuned student's own residual stream while it reads answers (positions after the first).

Then, on answers labelled by the instruments (right: the reference check agrees and the specification is
complete; wrong or weak otherwise), each answer is the mean of the SAE's activations over the tokens of its
`ensures` lines; the problems are split in two by a fixed hash (two thirds to choose, one third to test), the
single feature whose activation best separates right from not-right on the chosen problems is picked, and its
AUROC on the other problems is reported. Nothing here is trained.

answers.jsonl rows: {"task_id", "question" (the student prompt's messages), "answer" (the fenced t text), "right"}.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "t"))


def auroc(scores, labels) -> float | None:
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg:
        return None
    import bisect
    neg_sorted = sorted(neg)
    wins = 0.0
    for p in pos:
        lo = bisect.bisect_left(neg_sorted, p)
        hi = bisect.bisect_right(neg_sorted, p)
        wins += lo + 0.5 * (hi - lo)
    return wins / (len(pos) * len(neg))


def split_of(task_id: int) -> str:
    """Two thirds 'choose', one third 'test', by problem, fixed: the same problem never sits on both sides."""
    return "test" if int(hashlib.sha256(str(task_id).encode()).hexdigest(), 16) % 3 == 0 else "choose"


def ensures_spans(text: str) -> list[tuple[int, int]]:
    """Character spans of the `ensures` lines in an answer's text."""
    spans, pos = [], 0
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("ensures "):
            spans.append((pos, pos + len(line.rstrip("\n"))))
        pos += len(line)
    return spans


class TopKSAE:
    def __init__(self, path: Path, k: int = 50):
        import torch
        d = torch.load(path, map_location="cpu")
        self.W_enc, self.b_enc = d["W_enc"].float(), d["b_enc"].float()
        self.W_dec, self.b_dec = d["W_dec"].float(), d["b_dec"].float()
        self.k = k

    def encode(self, x):
        import torch
        pre = x @ self.W_enc.T + self.b_enc
        vals, idx = pre.topk(self.k, dim=-1)
        acts = torch.zeros_like(pre)
        acts.scatter_(-1, idx, vals)
        return acts

    def decode(self, a):
        return a @ self.W_dec.T + self.b_dec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--sae", type=Path, required=True)
    ap.add_argument("--layer", type=int, required=True)
    ap.add_argument("--answers", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--threads", type=int, default=12)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--feature", type=int, default=None,
                    help="also score this one feature within quartiles of answer length on the test problems")
    a = ap.parse_args(argv)
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    torch.set_num_threads(a.threads)
    tok = AutoTokenizer.from_pretrained(a.model)
    model = AutoModelForCausalLM.from_pretrained(a.model, torch_dtype=torch.float32)
    model.eval()
    sae = TopKSAE(a.sae)
    rows = [json.loads(l) for l in a.answers.read_text(encoding="utf-8").splitlines() if l.strip()]
    if a.limit:
        rows = rows[:a.limit]
    captured = {}
    layer = model.model.layers[a.layer]
    handle = layer.register_forward_hook(lambda m, i, o: captured.__setitem__("x", (o[0] if isinstance(o, tuple) else o).detach()))
    resid_ss = recon_ss = 0.0
    n_pos = 0
    total = None
    feats, labels, splits, ids, rows_kept = [], [], [], [], []
    started = time.monotonic()
    with torch.no_grad():
        for k, r in enumerate(rows):
            prefix = tok.apply_chat_template(r["question"], tokenize=False, add_generation_prompt=True, enable_thinking=False)
            text = prefix + r["answer"]
            enc = tok(text, return_offsets_mapping=True, return_tensors="pt")
            model(input_ids=enc["input_ids"])
            x = captured["x"][0]                                # (seq, d)
            offsets = enc["offset_mapping"][0].tolist()
            start = len(prefix)
            ans_pos = [i for i, (s, e) in enumerate(offsets) if s >= start and i > 0]
            ens = []
            for (s0, e0) in ensures_spans(r["answer"]):
                ens += [i for i, (s, e) in enumerate(offsets) if s >= start + s0 and e <= start + e0 and e > s]
            if not ans_pos or not ens:
                continue
            xa = x[ans_pos]
            acts = sae.encode(xa)
            xhat = sae.decode(acts)
            resid_ss += float(((xa - xhat) ** 2).sum())
            total = xa if total is None else torch.cat([total[-4096:], xa])  # a running sample for the variance
            recon_ss += float(((xa - xa.mean(0)) ** 2).sum())
            n_pos += len(ans_pos)
            pos_in_ans = [ans_pos.index(i) for i in ens if i in ans_pos]
            feats.append(acts[pos_in_ans].mean(0).to_sparse())
            rows_kept.append(r)
            labels.append(bool(r["right"]))
            splits.append(split_of(int(r["task_id"])))
            ids.append(int(r["task_id"]))
            if (k + 1) % 50 == 0:
                print(f"sae_spec_probe: {k + 1}/{len(rows)} ({time.monotonic() - started:.0f} s)", flush=True)
    handle.remove()
    fve = 1 - resid_ss / recon_ss if recon_ss else None
    dense = torch.stack([f.to_dense() for f in feats]) if feats else None
    choose = [i for i, s in enumerate(splits) if s == "choose"]
    test = [i for i, s in enumerate(splits) if s == "test"]
    best = None
    if dense is not None and choose and test:
        y_c = [labels[i] for i in choose]
        active = (dense[choose] != 0).sum(0)
        candidates = [int(j) for j in torch.nonzero(active >= 5).flatten()]
        scored = []
        for j in candidates:
            s = auroc(dense[choose, j].tolist(), y_c)
            if s is not None:
                scored.append((abs(s - 0.5), s, j))
        scored.sort(reverse=True)
        if scored:
            _gap, s_c, j = scored[0]
            sign = 1 if s_c >= 0.5 else -1
            s_t = auroc([sign * v for v in dense[test, j].tolist()], [labels[i] for i in test])
            best = {"feature": j, "direction": "higher means right" if sign > 0 else "higher means not right",
                    "auroc on the choosing problems": round(max(s_c, 1 - s_c), 4), "auroc on the test problems": round(s_t, 4) if s_t is not None else None,
                    "features considered": len(scored)}
    controlled = None
    if a.feature is not None and dense is not None and test:
        # the feature's AUROC within each quartile of answer length on the test problems, pooled by pairs:
        # whatever the feature adds beyond how long the answer is
        lengths = [len(rows_kept[i]["answer"]) for i in range(len(rows_kept))]
        t_sorted = sorted(test, key=lambda i: lengths[i])
        quarters = [t_sorted[q * len(t_sorted) // 4:(q + 1) * len(t_sorted) // 4] for q in range(4)]
        num = den = 0.0
        per = []
        for qs in quarters:
            ys = [labels[i] for i in qs]
            pos, neg = sum(ys), len(ys) - sum(ys)
            s_q = auroc([float(dense[i, a.feature]) for i in qs], ys)
            per.append({"answers": len(qs), "right": pos, "auroc": round(s_q, 4) if s_q is not None else None})
            if s_q is not None:
                num += s_q * pos * neg
                den += pos * neg
        controlled = {"feature": a.feature, "auroc within length quartiles (pair-weighted)": round(num / den, 4) if den else None,
                      "quartiles": per,
                      "auroc on the test problems, all": round(auroc([float(dense[i, a.feature]) for i in test],
                                                                     [labels[i] for i in test]), 4)}
    report = {"model": str(a.model), "sae": str(a.sae), "layer": a.layer, "answers read": len(feats),
              "positions": n_pos, "fraction of variance explained": round(fve, 4) if fve is not None else None,
              "right": sum(labels), "choose answers": len(choose), "test answers": len(test),
              "test problems": len({ids[i] for i in test}), "best feature": best, "length-controlled": controlled,
              "seconds": round(time.monotonic() - started)}
    a.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
