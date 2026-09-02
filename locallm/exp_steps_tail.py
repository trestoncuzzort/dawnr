"""exp_steps_tail.py — go past 10,000 steps and look for the turn-up.

Executes prereg_steps_tail.json. Read that first; this file only runs it.

TRACKS THE GAP, NOT JUST THE LOSS. Past ~5k steps every additional step re-reads
text the model has already seen, so the failure worth catching is not "stops
improving" but "improves on memorised text while getting worse on unseen text".
That shows up as val minus train widening, and it shows up BEFORE val itself
turns up. Reporting only val would find the damage a doubling or two late.

WRITES AFTER EVERY ARM. The 160k arm alone is ~15 minutes per seed; a crash at
the end of a 90-minute run that lost the first 75 would be its own small
tragedy. Partial results are a real artifact, not a consolation prize.
"""
from __future__ import annotations

import contextlib
import json
import math
import time
from pathlib import Path

import torch

import baselines
import runlog
from data import CharTokenizer, Corpus
from model import GPT, GPTConfig
from train import (auto_lr, cosine_lr, enable_fast_math, estimate_loss,
                   make_optimizer, pick_device, wants_bf16)

HERE = Path(__file__).resolve().parent
PREREG = json.loads((HERE / "prereg_steps_tail.json").read_text(encoding="utf-8"))
OUT = HERE / "exp_steps_tail_result.json"

STEPS_ARMS = PREREG["arms"]["steps"]
SEEDS = PREREG["arms"]["seeds"]
ARCH = dict(n_layer=4, n_head=4, n_embd=256, block_size=128)
BATCH, DROPOUT = 32, 0.1
CHARS_PER_STEP = BATCH * ARCH["block_size"]

# WHAT THIS EXPERIMENT MEASURED, as opposed to what it CONCLUDED. The same
# declaration exp_steps_vs_quality.py carries and for the same reason: every
# leaf of the payload not named here is a claim built on the holdout, and
# baselines.withhold_claims nulls it when the holdout cannot carry one. A field
# added below and never declared is withheld by default.
#
# The per-arm train/val readings stay on an ineligible run -- including the
# gap, which is one model's val loss minus its own train loss and is measured,
# not argued. What goes is every comparison BETWEEN arms (val_change,
# gap_growth and the two booleans read off them), the verdict, and
# closed_fraction. corpus_crossings is arithmetic on the step count and the
# corpus length and does not touch the holdout at all.
PAYLOAD_DATA = frozenset({
    "prereg", "device", "partial", "wall_s",
    "baseline.*.nats_per_char", "baseline.*.bits_per_char", "baseline.*.choices",
    "arms.*.seeds_val", "arms.*.seeds_train", "arms.*.seeds_gap",
    "arms.*.mean_val", "arms.*.spread_val", "arms.*.mean_train",
    "arms.*.mean_gap", "arms.*.spread_gap", "arms.*.choices",
    "arms.*.corpus_crossings", "arms.*.closed_fraction_reason",
})
RECORD_DATA = frozenset({"wall_s"})


def train_one(corpus, tok, device, steps: int, seed: int) -> dict:
    """One run, mirroring train.py's loop exactly. Returns train and val."""
    torch.manual_seed(seed)
    cfg = GPTConfig(vocab_size=tok.vocab_size, dropout=DROPOUT, **ARCH)
    model = GPT(cfg).to(device)
    lr = auto_lr(ARCH["n_embd"])
    opt = make_optimizer(model, lr)
    use_bf16 = wants_bf16(device)
    amp = (lambda: torch.autocast(device, dtype=torch.bfloat16)) if use_bf16 \
        else (lambda: contextlib.nullcontext())
    warmup = max(10, steps // 20)

    model.train()
    for step in range(steps):
        for g in opt.param_groups:
            g["lr"] = cosine_lr(step, warmup, steps, lr, lr / 10)
        xb, yb = corpus.get_batch("train", BATCH, ARCH["block_size"])
        with amp():
            _, loss = model(xb, yb)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()

    final = estimate_loss(model, corpus, BATCH, ARCH["block_size"])
    del model, opt
    if device == "cuda":
        torch.cuda.empty_cache()
    elif device == "mps":
        torch.mps.empty_cache()
    return {"train": float(final["train"]), "val": float(final["val"])}


def summarise(rows: list[dict], steps: int, corpus_chars: int,
              ngram_choices: float, ineligible: str | None = None) -> dict:
    vals = [r["val"] for r in rows]
    trains = [r["train"] for r in rows]
    gaps = [r["val"] - r["train"] for r in rows]
    mean_val = sum(vals) / len(vals)
    # baselines.closed_fraction, not the division spelled out here: this used to
    # divide by (ngram_choices - 1.0) unguarded and publish the result whatever
    # the holdout was worth. See baselines.holdout_eligibility.
    closed, why = baselines.closed_fraction(ngram_choices, math.exp(mean_val),
                                            ineligible)
    return {
        "seeds_val": vals, "seeds_train": trains, "seeds_gap": gaps,
        "mean_val": mean_val, "spread_val": max(vals) - min(vals),
        "mean_train": sum(trains) / len(trains),
        "mean_gap": sum(gaps) / len(gaps), "spread_gap": max(gaps) - min(gaps),
        "choices": math.exp(mean_val),
        "closed_fraction": closed, "closed_fraction_reason": why,
        "corpus_crossings": steps * CHARS_PER_STEP / corpus_chars,
    }


def compare_arms(summary: dict, arms: list[str]) -> list[dict]:
    """Consecutive arms, on val and on the train/val gap. All claims."""
    out = []
    for a, b in zip(arms, arms[1:]):
        gap = summary[a]["mean_val"] - summary[b]["mean_val"]   # +ve = b better
        noise = max(summary[a]["spread_val"], summary[b]["spread_val"])
        gap_growth = summary[b]["mean_gap"] - summary[a]["mean_gap"]
        gap_noise = max(summary[a]["spread_gap"], summary[b]["spread_gap"])
        out.append({
            "from_steps": int(a), "to_steps": int(b),
            "val_change": gap, "val_noise": noise,
            "still_improving": bool(gap > noise),
            "turned_up": bool(-gap > noise),
            "gap_growth": gap_growth, "gap_noise": gap_noise,
            "memorising": bool(gap_growth > gap_noise),
        })
    return out


def verdict_of(comparisons: list[dict]) -> str:
    if any(c["turned_up"] for c in comparisons):
        return "TAIL FOUND — more training measurably made it worse on unseen text"
    if any(c["memorising"] for c in comparisons):
        return ("no turn-up yet, but the train/val gap is widening beyond noise — "
                "memorising is detectable before it is costly")
    if all(c["still_improving"] for c in comparisons):
        return "still improving at every arm — no tail within the range tested"
    return "flattened — gains fell inside seed noise, but nothing got worse"


def payload_of(base: dict, summary: dict, device: str, wall_s: float,
               ineligible: str | None, *, partial: bool,
               comparisons: list[dict] | None = None,
               verdict: str | None = None) -> dict:
    """The result file, with every claim in it gated on the holdout.

    Both the after-every-arm write and the final one come through here, so a
    partial file cannot carry a claim the final one would have withheld. The
    partial one simply has no comparisons and no verdict yet: those keys are
    absent rather than null, because "not computed yet" and "withheld" are
    different facts and the reader of a partial file deserves the first one.

    Every claim surface of this experiment reads the returned object -- the
    file, the run log record and the terminal -- so none of them can print what
    another withheld. Before this, an ineligible holdout nulled closed_fraction
    and left the verdict, the val comparisons and the memorising call standing.
    """
    payload = {"prereg": PREREG["experiment"], "device": device,
               "partial": partial, "baseline": base, "arms": summary,
               "wall_s": wall_s}
    if not partial:
        payload["comparisons"] = comparisons
        payload["verdict"] = verdict
    return baselines.withhold_claims(payload, ineligible, PAYLOAD_DATA)


def main() -> None:
    enable_fast_math()
    device = pick_device()
    text = (HERE / "corpus.txt").read_text(encoding="utf-8")
    tok = CharTokenizer.from_text(text)
    corpus = Corpus(text, tok, device)
    print(f"corpus {len(text):,} chars | vocab {tok.vocab_size} | device {device}",
          flush=True)
    print(f"one crossing of this corpus = {len(text)/CHARS_PER_STEP:,.0f} steps\n",
          flush=True)

    base = baselines.compare(corpus.train_text or "", corpus.val_text or "",
                             tok.vocab_size)
    ngram_choices = base[f"ngram_{baselines.NGRAM_ORDER}"]["choices"]

    # Is this holdout worth comparing anything against? Asked once, before the
    # arms run, and carried into every arm's row. Without it this file printed a
    # "vs table" percentage for corpora with no usable holdout at all.
    # doc_aligned comes from the Corpus that produced the split, not from a
    # default: grouped=True splits between whole documents, so document counts
    # mean something; the positional path's do not.
    ineligible = baselines.holdout_eligibility(text, corpus.train_text,
                                               corpus.val_text,
                                               corpus.val_frac, corpus.seed,
                                               doc_aligned=corpus.grouped)
    if ineligible:
        print(f"  NOT ELIGIBLE for a baseline comparison: {ineligible}\n"
              f"  Every claim this run would make rests on that holdout, so the "
              f"verdict, the arm-to-arm comparisons and closed_fraction will all "
              f"be withheld. The train/val readings below are readings, and they "
              f"stay.\n", flush=True)

    summary: dict[str, dict] = {}
    wall0 = time.time()
    for steps in STEPS_ARMS:
        rows = []
        for seed in SEEDS:
            t = time.time()
            r = train_one(corpus, tok, device, steps, seed)
            rows.append(r)
            print(f"  steps={steps:<7} seed={seed}  train={r['train']:.4f}  "
                  f"val={r['val']:.4f}  gap={r['val']-r['train']:+.4f}  "
                  f"({time.time()-t:.0f}s)", flush=True)
        s = summarise(rows, steps, len(text), ngram_choices, ineligible)
        summary[str(steps)] = s
        print(f"  -> {steps}: val {s['mean_val']:.4f} (spread {s['spread_val']:.4f})  "
              f"gap {s['mean_gap']:+.4f}  crossings {s['corpus_crossings']:.1f}\n",
              flush=True)
        # Written after every arm, not at the end. See module docstring.
        OUT.write_text(json.dumps(
            payload_of(base, summary, device, time.time() - wall0, ineligible,
                       partial=True), indent=2), encoding="utf-8")

    arms = [str(s) for s in STEPS_ARMS]
    comparisons = compare_arms(summary, arms)
    payload = payload_of(base, summary, device, time.time() - wall0, ineligible,
                         partial=False, comparisons=comparisons,
                         verdict=verdict_of(comparisons))
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    # Every arm here is scored on the SAME holdout and the verdict is a
    # comparison of val losses, so which holdout it was is part of the result,
    # not decoration; and every arm's timing is a device number. Both fields
    # are read off the Corpus that actually trained, never re-derived.
    #
    # The metrics dict goes through the same gate as the payload: a run log row
    # that carried the verdict of a run whose result file withheld it would be
    # the same claim, published somewhere the reader trusts more.
    runlog.record("experiment", kind_detail="steps_tail", device=device,
                  data_device=corpus.data_device,
                  corpus=runlog.corpus_fingerprint(text),
                  split_fingerprint=runlog.split_fingerprint(
                      corpus.val_frac, corpus.seed, corpus.val_text),
                  metrics=baselines.withhold_claims(
                      {"verdict": payload["verdict"],
                       "wall_s": payload["wall_s"]},
                      ineligible, RECORD_DATA))

    # PRINTED FROM THE GATED PAYLOAD, never from the local variables above, so
    # the terminal cannot state what the file withheld.
    print("=" * 78)
    print(f"{'steps':>8} {'crossings':>10} {'train':>8} {'val':>8} {'gap':>8} "
          f"{'spread':>8} {'vs table':>9}")
    for k in arms:
        s = payload["arms"][k]
        vs = (f"{s['closed_fraction']*100:>8.0f}%"
              if s["closed_fraction"] is not None else f"{'n/a':>9}")
        print(f"{k:>8} {s['corpus_crossings']:>9.1f}x {s['mean_train']:>8.4f} "
              f"{s['mean_val']:>8.4f} {s['mean_gap']:>+8.4f} {s['spread_val']:>8.4f} "
              f"{vs}")
    if ineligible:
        print(f"  vs table: n/a -- {ineligible}")
    print()
    for c in payload["comparisons"] or []:
        if c["turned_up"]:
            mark = "WORSE — tail found"
        elif c["still_improving"]:
            mark = "still improving"
        else:
            mark = "inside noise"
        print(f"  {c['from_steps']:>6} -> {c['to_steps']:<7} val {c['val_change']:+.4f} "
              f"(noise {c['val_noise']:.4f})   gap {c['gap_growth']:+.4f} "
              f"(noise {c['gap_noise']:.4f})   {mark}"
              f"{'  MEMORISING' if c['memorising'] else ''}")
    if payload["verdict"] is None:
        print(f"\nVERDICT WITHHELD: {payload['ineligible_reason']}")
        print(f"  {len(payload['claims_withheld'])} claim-bearing field(s) "
              f"withheld: {', '.join(payload['claims_withheld'])}")
        print("  The table above is what this run measured. Nothing in this "
              "result says what it means.")
    else:
        print(f"\nVERDICT: {payload['verdict']}")
    print(f"wall {payload['wall_s']/60:.1f} min -> {OUT.name}")


if __name__ == "__main__":
    main()
