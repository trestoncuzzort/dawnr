"""exp_steps_vs_quality.py — does training longer actually help, or is it luck?

Runs the arms declared in prereg_steps_vs_quality.json and answers against the
success bar written there BEFORE any run happened. Read that file first; this
one only executes it.

WHY IT LOADS THE CORPUS ONCE. Shelling out to train.py twenty times would re-read
and re-tokenise 20MB and rebuild the same trigram table twenty times, which is
about six minutes of pure repetition on a run that is otherwise ~12. It would
also make the split a per-process accident rather than one fixed object. One
Corpus, one baseline, twenty models.

WHY THE BASELINE IS COMPUTED ONCE. Every arm is scored on the identical holdout,
so the lookup table's score is a property of the text, not of the run. Computing
it per-run would produce twenty identical numbers and invite someone to average
them as if they were measurements.
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
PREREG = json.loads((HERE / "prereg_steps_vs_quality.json").read_text(encoding="utf-8"))
OUT = HERE / "exp_steps_vs_quality_result.json"

STEPS_ARMS = PREREG["arms"]["steps"]
SEEDS = PREREG["arms"]["seeds"]
ARCH = dict(n_layer=4, n_head=4, n_embd=256, block_size=128)
BATCH, DROPOUT = 32, 0.1

# WHAT THIS EXPERIMENT MEASURED, as opposed to what it CONCLUDED. Every leaf of
# the payload that is not declared here is treated as a claim built on the
# holdout and is nulled when the holdout cannot carry one -- including a field
# added below next year and never declared, which is the direction that fails
# safe. baselines.withhold_claims derives the claim set by walking the payload;
# this is the only half of it written by hand.
#
# The readings stay on an ineligible run because they are what happened: a
# per-seed val loss is the number the model scored on the text that was held
# back, `choices` is exp() of it, and the baseline table is a lookup table
# scored on the same text. What goes is everything that says what they MEAN --
# the arm-to-arm gaps, the comparison against seed noise, the verdict, and
# closed_fraction, which was already nulled by baselines.closed_fraction and is
# now nulled by the gate as well.
PAYLOAD_DATA = frozenset({
    "prereg", "success_bar", "device", "wall_s",
    "baseline.*.nats_per_char", "baseline.*.bits_per_char", "baseline.*.choices",
    "arms.*.seeds", "arms.*.mean", "arms.*.min", "arms.*.max", "arms.*.spread",
    "arms.*.choices", "arms.*.closed_fraction_reason",
})
# The run log's metrics dict is the same surface in miniature: a wall clock is a
# device number, and the verdict is the claim.
RECORD_DATA = frozenset({"wall_s"})


def train_one(corpus, tok, device, steps: int, seed: int) -> float:
    """One run. Returns final validation loss on the fixed holdout.

    This loop mirrors train.py's exactly — same warmup rule, same cosine
    schedule and min_lr, same grad clip, same bf16 autocast when the card
    supports it. An experiment that trains a LOOKALIKE of the product measures
    the lookalike; every line here that differs from train.py:164-181 would be a
    silent confound in the result.
    """
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
    return float(final["val"])


def summarise(row: list[float], ngram_choices: float,
              ineligible: str | None) -> dict:
    """One arm's readings. Nothing here compares anything to anything."""
    mean = sum(row) / len(row)
    closed, why = baselines.closed_fraction(ngram_choices, math.exp(mean),
                                            ineligible)
    return {
        "seeds": row, "mean": mean, "min": min(row), "max": max(row),
        "spread": max(row) - min(row),
        "choices": math.exp(mean),
        "closed_fraction": closed, "closed_fraction_reason": why,
    }


def compare_arms(summary: dict, arms: list[str]) -> list[dict]:
    """Consecutive arms against seed noise. Every field here is a claim."""
    out = []
    for a, b in zip(arms, arms[1:]):
        gap = summary[a]["mean"] - summary[b]["mean"]          # positive = b better
        noise = max(summary[a]["spread"], summary[b]["spread"])
        out.append({
            "from_steps": int(a), "to_steps": int(b),
            "gap_in_val_loss": gap, "wider_seed_spread": noise,
            "beats_noise": bool(gap > noise),
        })
    return out


def verdict_of(comparisons: list[dict]) -> str:
    return ("longer training measurably helps"
            if all(c["beats_noise"] for c in comparisons)
            else "some step increases are NOT distinguishable from seed luck")


def payload_of(base: dict, summary: dict, comparisons: list[dict], verdict: str,
               device: str, wall_s: float, ineligible: str | None) -> dict:
    """The result file, with every claim in it gated on the holdout.

    ONE OBJECT FEEDS ALL THREE SURFACES. The file, the run log record and the
    terminal all read this payload, so the terminal cannot print a verdict the
    file withheld -- which is exactly what it did: it printed NOT ELIGIBLE and
    then the ordinary val-loss verdict eleven lines later. What counts as a
    claim is declared once, in PAYLOAD_DATA, by naming what was MEASURED.

    Measured before this existed: the terminal printed "NOT ELIGIBLE for a
    baseline comparison" at the top of the run and "VERDICT: longer training
    measurably helps" at the bottom of the same one.
    """
    return baselines.withhold_claims({
        "prereg": PREREG["experiment"],
        "success_bar": PREREG["success_bar"]["primary"],
        "device": device,
        "wall_s": wall_s,
        "baseline": base,
        "arms": summary,
        "comparisons": comparisons,
        "verdict": verdict,
    }, ineligible, PAYLOAD_DATA)


def main() -> None:
    enable_fast_math()
    device = pick_device()
    text = (HERE / "corpus.txt").read_text(encoding="utf-8")
    tok = CharTokenizer.from_text(text)
    corpus = Corpus(text, tok, device)
    print(f"corpus {len(text):,} chars | vocab {tok.vocab_size} | device {device}", flush=True)

    print("scoring the lookup table once (same holdout for every arm)...", flush=True)
    t0 = time.time()
    base = baselines.compare(corpus.train_text or "", corpus.val_text or "",
                             tok.vocab_size)
    ngram_choices = base[f"ngram_{baselines.NGRAM_ORDER}"]["choices"]
    print(f"  trigram: {base[f'ngram_{baselines.NGRAM_ORDER}']['bits_per_char']:.3f} "
          f"bits/char, {ngram_choices:.2f} choices  ({time.time()-t0:.1f}s)\n", flush=True)

    # A baseline is only worth reporting on a holdout that is worth reporting.
    # baselines.py has said so in prose since it was written and studio.py has
    # enforced it since; this file published closed_fraction for any corpus at
    # all, including ones with no holdout to speak of.
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
              f"be withheld. The val losses below are readings, and they stay.\n",
              flush=True)

    results: dict[str, list[float]] = {}
    wall0 = time.time()
    for steps in STEPS_ARMS:
        row = []
        for seed in SEEDS:
            t = time.time()
            val = train_one(corpus, tok, device, steps, seed)
            row.append(val)
            print(f"  steps={steps:<6} seed={seed}  val={val:.4f}  "
                  f"({time.time()-t:.1f}s)", flush=True)
        results[str(steps)] = row
        lo, hi = min(row), max(row)
        print(f"  -> steps={steps}: mean {sum(row)/len(row):.4f}  "
              f"spread {hi-lo:.4f}\n", flush=True)

    # ---- analysis, against the bar declared before any of this ran -----------
    arms = [str(s) for s in STEPS_ARMS]
    summary = {steps: summarise(row, ngram_choices, ineligible)
               for steps, row in results.items()}
    comparisons = compare_arms(summary, arms)
    payload = payload_of(base, summary, comparisons, verdict_of(comparisons),
                         device, time.time() - wall0, ineligible)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    # The verdict is "longer training measurably helps", read off val losses
    # from one holdout. Which holdout is therefore part of the claim, and the
    # wall clock is a device number. Both read off the Corpus that trained.
    #
    # The metrics dict goes through the same gate as the payload, so a run log
    # row cannot carry a verdict the result file withheld. It used to: with the
    # holdout ineligible, runs.jsonl recorded the verdict string and no
    # eligibility field at all, and the digest printed it beside the trustworthy
    # ones.
    runlog.record("experiment", kind_detail="steps_vs_quality", device=device,
                  data_device=corpus.data_device,
                  corpus=runlog.corpus_fingerprint(text),
                  split_fingerprint=runlog.split_fingerprint(
                      corpus.val_frac, corpus.seed, corpus.val_text),
                  metrics=baselines.withhold_claims(
                      {"verdict": payload["verdict"],
                       "wall_s": payload["wall_s"]},
                      ineligible, RECORD_DATA))

    # PRINTED FROM THE GATED PAYLOAD, never from the local variables above. The
    # terminal is a claim surface like the file and the log, and reading the
    # same object is the only arrangement in which it cannot disagree with them.
    print("=" * 70)
    print(f"{'steps':>7} {'mean val':>10} {'spread':>8} {'choices':>9} {'vs table':>9}")
    for steps in arms:
        s = payload["arms"][steps]
        vs = (f"{s['closed_fraction']*100:>8.0f}%"
              if s["closed_fraction"] is not None else f"{'n/a':>9}")
        print(f"{steps:>7} {s['mean']:>10.4f} {s['spread']:>8.4f} "
              f"{s['choices']:>9.2f} {vs}")
    if ineligible:
        print(f"  vs table: n/a -- {ineligible}")
    print()
    for c in payload["comparisons"] or []:
        mark = "REAL" if c["beats_noise"] else "inside noise"
        print(f"  {c['from_steps']:>5} -> {c['to_steps']:<6} improved {c['gap_in_val_loss']:.4f}"
              f"   seed luck moves it {c['wider_seed_spread']:.4f}   {mark}")
    if payload["verdict"] is None:
        print(f"\nVERDICT WITHHELD: {payload['ineligible_reason']}")
        print(f"  {len(payload['claims_withheld'])} claim-bearing field(s) "
              f"withheld: {', '.join(payload['claims_withheld'])}")
        print("  The table above is what this run measured. Nothing in this "
              "result says what it means.")
    else:
        print(f"\nVERDICT: {payload['verdict']}")
    print(f"written to {OUT.name}")


if __name__ == "__main__":
    main()
