"""exp_lr_width.py — experiment 1: is a hardcoded lr=3e-4 wrong for this width?

Two preregistered profiles, and they are DIFFERENT EXPERIMENTS, not two speeds
of one:
  canonical  prereg_lr_width.json       2000 steps, 7-LR grid  (~2.5 min)
  fast       prereg_lr_width_fast.json   800 steps, 4-LR grid  (~1 min)
The effect size decays roughly 9x from 400 to 2000 steps, so the fast profile
reports a LARGER gap for the same phenomenon and licenses only the weaker claim
"reaches lower train loss faster". Each run writes its profile, step count, grid
size and claim into its own verdict string, so the two cannot be quietly
conflated later.

Each profile runs:
  stage 1  sweep LR at fixed width, single seed, to select the treatment arm
  stage 2  control (3e-4) vs treatment, 5 seeds each, train-loss endpoint

Endpoint is TRAIN loss on purpose: a positional train/val split can duplicate
training text into validation, so a val endpoint is not yet trustworthy here.
Eval batches come from a dedicated torch.Generator, never the global RNG, so
every arm sees identical batches and evaluation cannot perturb training.

    python exp_lr_width.py                     # canonical, ~2.5 min
    python exp_lr_width.py --profile fast      # separate experiment, ~1 min
    python exp_lr_width.py --quick             # 400-step sanity pass, not a result
"""
from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import re
import sys
import time
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from model import GPT, GPTConfig          # noqa: E402
from data import CharTokenizer, Corpus    # noqa: E402
import runlog                            # noqa: E402
from train import cosine_lr, enable_fast_math, make_optimizer, pick_device, wants_bf16  # noqa: E402

EVAL_SEED = 12345
EVAL_BATCHES = 40
# Measured, and the measurement reversed itself, which is why the number is
# recorded here rather than reasoned about: running ONE arm at a time, fp32 beats
# bf16 autocast (6.00 vs 8.36 ms/step) because the casts cost more than the
# arithmetic they save on a 3M-parameter model. Running four arms concurrently,
# which is the shipped default, bf16 wins by a wide margin end to end (163s vs
# 215s). Benchmark the configuration you actually run.
USE_AMP = True


# THE BAR IS A COMPLETE NUMERIC TOKEN, and the pattern says so at both ends.
# The previous one, r">=\s*([0-9]*\.?[0-9]+)", was a PREFIX match: it read the
# longest plain decimal it could and ignored whatever followed, so it could not
# tell 0.020 from 0.020junk and read the exponent of 5e-1 as if it were not
# there. Measured, before: "gap >= 5e-1" -> 5.0 (a bar 10x too high),
# "gap >= 2E2" -> 2.0, "gap >= 0.020junk" -> 0.020, "gap >= -0.020" -> refused
# outright, "gap >= 0x10" -> 0.0, "gap >= 1_000" -> 1.0, "gap >= 0.02e" ->
# 0.020, "gap >= 2e400" -> 2.0.
#
#   [+-]?                     an explicit sign, PARSED rather than dropped
#   digits with an optional fraction, or a leading-dot fraction
#   an optional exponent, WITH its digits
#   (?![0-9A-Za-z_]|\.[0-9])  and nothing may follow that could have belonged
#                             to the number. A sentence-ending "." is fine: a
#                             period not followed by a digit is punctuation.
_BAR = re.compile(
    r">=\s*([+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)"
    r"(?![0-9A-Za-z_]|\.[0-9])")

# EVERY ">=" IN THE SENTENCE IS A COMPARISON THIS HAS TO ACCOUNT FOR. The bar
# above is a good pattern applied with findall, which reports the comparisons it
# COULD read and says nothing about the ones it could not, so a sentence
# carrying one readable comparison and one malformed one came back with a
# number. Measured, three of three sentences tried in this shape:
#
#     "n >= 5 seeds and gap >= 0.020junk"   -> 5.0
#     "gap >= 0.020 and gap >= 5e-1x"       -> 0.02
#     "gap >= 0x10 and gap >= 0.020"        -> 0.02
#
# Each is a bar the preregistration never set, printed as if it had.
#
# A parser that validates only its own matches cannot refuse anything it failed
# to match, which is the whole failure class. So the occurrences are enumerated
# FIRST and each one is then required to parse, rather than the parse being
# allowed to define the occurrences.
_GE = re.compile(r">=")


def success_bar(prereg: dict) -> float:
    """The numeric bar, READ FROM THE PREREGISTRATION that declared it.

    This file printed prereg['success_bar']['primary'] and then decided against
    a literal 0.020 in three places. Change the preregistration and the
    experiment goes on answering the old question while printing the new one:
    measured with the bar raised to 0.500 and a stubbed gap of 0.0500, it
    printed "gap >= ... >= 0.500" and then "bar = 0.020" and PASS.

    The bar lives in prose because the prose is what a reader checks the run
    against, so it is parsed out rather than duplicated into a numeric field --
    a second field would be a second place for the two to disagree. If it
    cannot be read, the experiment stops: a confirmatory run that does not know
    its own bar has nothing to confirm.

    PARSING PROSE MEANS REFUSING PROSE IT CANNOT READ. The failure this guards
    is not an exception, it is a WRONG NUMBER THAT RUNS: the previous pattern
    read "gap >= 5e-1" as 5.0 and "gap >= 0.020junk" as 0.020, and either would
    have printed "bar = ..." and a PASS/FAIL verdict against a bar the
    preregistration never set. So the token must be a complete numeric literal
    with nothing of the number left over, and anything else raises.

    ONE bar, too. If the prose carries two different ">= <number>" tokens --
    "n >= 5 seeds and gap >= 0.020" -- the old pattern took the first and read
    the bar as 5.0. There is no rule that makes one of them the right one, so
    this refuses and says which two it found. Repeats of the SAME number are
    fine: they cannot be ambiguous.

    AND EVERY COMPARISON COUNTS, not only the ones that parsed. The refusal
    above was implemented with findall, which returns successes: it could refuse
    "gap >= 0.020junk" alone, because then there was nothing to return, but
    "n >= 5 seeds and gap >= 0.020junk" returned 5.0 -- the bar of the readable
    half, silently standing in for a sentence half of which is unreadable. So
    the ">=" occurrences are enumerated first and each is required to parse as a
    complete comparison; one that does not is named and raises. See _GE.
    """
    primary = prereg["success_bar"]["primary"]
    found = []
    for m in _GE.finditer(primary):
        bar_at = _BAR.match(primary, m.start())
        if bar_at is None:
            raise ValueError(
                f"this preregistration's success_bar.primary contains a "
                f"comparison whose bar is not a number this can read: "
                f"{primary[m.start():m.start() + 20]!r} at character "
                f"{m.start()} of {primary!r}. Every '>=' in the sentence must "
                f"be followed by a complete decimal literal (5, 0.020, .5, "
                f"-0.02, 5e-1) with nothing attached to it.")
        found.append(bar_at.group(1))
    if not found:
        raise ValueError(
            f"cannot read a numeric bar out of this preregistration's "
            f"success_bar.primary: {primary!r}. It must contain '>= <number>' "
            f"where <number> is a complete decimal literal (5, 0.020, .5, "
            f"-0.02, 5e-1) with nothing attached to it.")
    values = sorted({float(f) for f in found})
    if len(values) > 1:
        raise ValueError(
            f"this preregistration's success_bar.primary names more than one "
            f"bar ({', '.join(repr(v) for v in values)}): {primary!r}. Nothing "
            f"here decides which is THE bar, so it must say one.")
    bar = values[0]
    if not math.isfinite(bar):
        raise ValueError(
            f"this preregistration's success_bar.primary reads as {bar}, which "
            f"is not a number an experiment can be judged against: {primary!r}")
    return bar


def fixed_eval_batches(corpus: Corpus, batch_size: int, block_size: int, n: int):
    """Identical batches for every arm, drawn from our own Generator rather than
    the global RNG, so evaluating can never disturb the training stream."""
    dev = corpus.train.device
    g = torch.Generator(device=dev.type).manual_seed(EVAL_SEED)
    return [corpus.get_batch("train", batch_size, block_size, generator=g)
            for _ in range(n)]


@torch.no_grad()
def eval_train_loss(model, batches):
    model.eval()
    tot = 0.0
    for x, y in batches:
        _, loss = model(x, y)
        tot += loss.item()
    model.train()
    return tot / len(batches)


_W = {}


def _init_worker(cfg_d, device, corpus_path):
    enable_fast_math()
    """Each worker builds the corpus once and reuses it for every arm it runs.

    Arms are independent training runs, and this rig is launch-bound rather than
    compute-bound: a 3M-parameter step leaves the GPU idle while Python queues
    the next one. Running several arms in separate processes fills that idle
    time. Results are unchanged, because nothing is shared between arms except
    the read-only corpus, and each arm seeds its own RNG.
    """
    text = Path(corpus_path).read_text(encoding="utf-8", errors="ignore")
    tok = CharTokenizer.from_text(text)
    corpus = Corpus(text, tok, device)
    # The fingerprint of the file THIS worker read, kept rather than the text:
    # it is the fallback identity for a split that has no train TEXT to hash,
    # and holding another copy of a 20MB corpus per worker to get it would be
    # paying in memory for twelve characters.
    _W.update(tok=tok, corpus=corpus, device=device, cfg=cfg_d,
              corpus_fp=runlog.corpus_fingerprint(text),
              batches=fixed_eval_batches(corpus, cfg_d["batch_size"],
                                         cfg_d["block_size"], EVAL_BATCHES))


def _provenance() -> dict:
    """What this arm actually trained on, read off the Corpus in this worker.

    Every arm runs in a separate process and builds its own Corpus, so there is
    no single object in the parent to ask. Re-deriving it in main() by calling
    group_split() again would agree only for as long as every caller happens to
    pass the same val_frac and seed, which is the trap data.Corpus keeps
    train_text/val_text to close. So the arm reports what it used and main()
    reconciles the reports.

    THE ENDPOINT HERE IS TRAIN LOSS, SO THE TRAINING TEXT IS THE FINGERPRINT
    THAT HAS TO BE RECONCILED. This reported the VALIDATION fingerprint alone,
    which is the half of the split the endpoint never touches. Measured on a
    24-document corpus with one TRAINING document rewritten to the same length
    (4 characters changed): train text different, val text byte-identical, both
    arms reporting val_sha1 16aba70b30cb, and provenance_of joining them into
    one split_fingerprint with no warning -- provenance reporting agreement
    between two arms that trained on different text. Any same-length edit does
    it, because group_split assigns by position in a seed-shuffled list and the
    document LENGTHS decide what fits.

    A LIMIT THIS DOES NOT FIX: main() records corpus_fingerprint(text) from its
    OWN read of the file and nothing compares that with what the workers read.
    If the file changes between the parent's read and a worker's, the arms can
    agree with each other and all disagree with the corpus named on the row.
    The train fingerprint makes that visible to a reader who compares two runs
    of the "same" corpus; nothing here raises it.
    """
    c = _W["corpus"]
    # The text this arm's optimiser actually saw. On the positional path there
    # is no train TEXT to hash -- data.Corpus splits tokens there and keeps
    # None -- so the fallback is the corpus this worker read, labelled as such:
    # "the whole corpus" and "the training half of it" are different facts, and
    # a reconciliation that could not tell them apart would be the val-only
    # mistake again in another costume.
    trained_on = (runlog.corpus_fingerprint(c.train_text)
                  if c.train_text is not None
                  else dict(_W["corpus_fp"], whole_corpus=True))
    return {"data_device": c.data_device,
            "train_fingerprint": trained_on,
            "split_fingerprint": runlog.split_fingerprint(
                c.val_frac, c.seed, c.val_text)}


def _run_arm(job):
    label, lr, seed = job
    loss, secs, _ = run_one(_W["corpus"], _W["tok"], lr, seed, _W["cfg"],
                            _W["device"], _W["batches"])
    return label, lr, seed, loss, secs, _provenance()


def provenance_of(results: list) -> dict:
    """One provenance for the whole run, or the disagreement left visible.

    Arms build their corpus independently from the same file with the same
    defaults, so they normally agree exactly and this returns their one answer.
    They can disagree for a real reason -- one worker's corpus fell back to
    host memory while another's fitted, or the corpus file changed between the
    two stages -- and that is a fact about the run, not a detail to average
    away. So the distinct values are joined rather than reduced to the first
    one seen, and a run whose arms did not agree on the training text or on the
    holdout does not get to name one.
    """
    devices = sorted({r[5]["data_device"] for r in results})
    out = {"data_device": devices[0] if len(devices) == 1 else "+".join(devices)}

    # BOTH HALVES OF THE SPLIT, reconciled the same way. The train fingerprint
    # is the one this experiment's endpoint is measured on; the split
    # fingerprint identifies the holdout the prereg says every arm shares.
    # Reporting only the second was reporting agreement about the text nobody
    # scored: see _provenance.
    for field, warning in (
            ("train_fingerprint",
             "\nWARNING: the arms did not train on the same TEXT, so the gap "
             "printed above is between arms trained on different corpora and "
             "cannot be attributed to the learning rate. Recorded as a "
             "disagreement rather than as one training set."),
            ("split_fingerprint",
             "\nWARNING: the arms did not train on the same holdout, so the "
             "comparison printed above is between arms scored on different "
             "validation text and the prereg assumes they are identical. "
             "Recorded as a disagreement rather than as one split.")):
        seen = {json.dumps(r[5][field], sort_keys=True) for r in results}
        if len(seen) == 1:
            out[field] = json.loads(seen.pop())
        else:
            out[field] = {"arms_disagreed":
                          [json.loads(s) for s in sorted(seen)]}
            print(warning)
    if len(devices) > 1:
        print(f"\nWARNING: arms kept the corpus on different devices "
              f"({', '.join(devices)}); their ms/step are not comparable with "
              f"each other.")
    return out


def _run_jobs(jobs, cfg_d, device, workers, corpus_path):
    """Run arms across processes, or in-process when workers == 1."""
    if workers <= 1:
        _init_worker(cfg_d, device, corpus_path)
        return [_run_arm(j) for j in jobs]
    ctx = mp.get_context("spawn")          # required on Windows, and CUDA-safe
    with ctx.Pool(processes=workers, initializer=_init_worker,
                  initargs=(cfg_d, device, corpus_path)) as pool:
        return pool.map(_run_arm, jobs)


def run_one(corpus, tok, lr, seed, cfg_d, device, eval_batches=None):
    """One training run. The corpus and tokenizer are built ONCE by the caller
    and reused: re-tokenising half a million characters per arm cost more than
    some of the arms did."""
    torch.manual_seed(seed)
    if eval_batches is None:
        eval_batches = fixed_eval_batches(corpus, cfg_d["batch_size"],
                                          cfg_d["block_size"], EVAL_BATCHES)

    cfg = GPTConfig(vocab_size=tok.vocab_size, block_size=cfg_d["block_size"],
                    n_layer=cfg_d["n_layer"], n_head=cfg_d["n_head"],
                    n_embd=cfg_d["n_embd"], dropout=0.0)
    model = GPT(cfg).to(device)
    opt = make_optimizer(model, lr)
    use_bf16 = USE_AMP and wants_bf16(device)

    steps = cfg_d["steps"]
    warmup = max(10, steps // 20)
    t0 = time.time()
    for step in range(steps):
        for g in opt.param_groups:
            g["lr"] = cosine_lr(step, warmup, steps, lr, lr / 10)
        x, y = corpus.get_batch("train", cfg_d["batch_size"], cfg_d["block_size"])
        if use_bf16:
            with torch.autocast(device, dtype=torch.bfloat16):
                _, loss = model(x, y)
        else:
            _, loss = model(x, y)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        if not torch.isfinite(loss):
            return float("nan"), time.time() - t0, eval_batches

    return eval_train_loss(model, eval_batches), time.time() - t0, eval_batches


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", choices=["canonical", "fast"], default="canonical",
                    help="canonical = prereg_lr_width.json (2000 steps, 7 LRs). "
                         "fast = prereg_lr_width_fast.json (800 steps, 4 LRs), a "
                         "SEPARATE experiment licensing a different claim, not a "
                         "cheaper version of the canonical one.")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--workers", type=int, default=4,
                    help="arms to run concurrently (1 = serial). The GPU is "
                         "launch-bound at this model size, so concurrency is "
                         "close to free.")
    args = ap.parse_args()

    pf = "prereg_lr_width_fast.json" if args.profile == "fast" else "prereg_lr_width.json"
    prereg = json.loads((HERE / pf).read_text(encoding="utf-8"))
    C = dict(prereg["fixed_config"])
    C = {k: C[k] for k in ("n_layer", "n_head", "n_embd", "block_size",
                           "batch_size", "steps")}
    if args.quick:
        C["steps"] = 400

    device = pick_device()
    corpus_path = HERE / "corpus.txt"
    text = corpus_path.read_text(encoding="utf-8", errors="ignore")
    print(f"device {device} | corpus {len(text):,} chars | workers {args.workers} "
          f"| config {C}")
    bar = success_bar(prereg)
    print(f"prereg bar: {prereg['success_bar']['primary']}")
    print(f"            read as: gap >= {bar}\n")

    t_all = time.time()

    # ---------------- stage 1: sweep
    sweep_lrs = prereg["stage_1_sweep"]["lrs"]
    sweep_seed = prereg["stage_1_sweep"]["seed"]
    print("=== STAGE 1: LR sweep (seed %d, selects treatment arm) ===" % sweep_seed)
    t_stage = time.time()
    res = _run_jobs([("sweep", lr, sweep_seed) for lr in sweep_lrs],
                    C, device, args.workers, str(corpus_path))
    sweep_res = res
    sweep = {lr: loss for _, lr, _, loss, _, _ in res}
    for _, lr, _, loss, secs, _p in sorted(res, key=lambda r: r[1]):
        print(f"  lr {lr:<8.1e}  train loss {loss:.4f}   ({secs:.0f}s)")
    print(f"  stage 1 wall clock: {time.time() - t_stage:.0f}s")
    finite = {k: v for k, v in sweep.items() if v == v}
    if not finite:
        print("\nAll sweep arms diverged (NaN). Stopping — nothing to confirm.")
        return
    treatment_lr = min(finite, key=finite.get)
    control_lr = prereg["stage_2_confirm"]["control_lr"]
    print(f"\n  -> treatment selected by rule (lowest loss): lr = {treatment_lr:.1e}")
    if treatment_lr == control_lr:
        print("  -> treatment == control; the shipped default already wins this sweep.")

    # ---------------- stage 2: confirm
    seeds = prereg["stage_2_confirm"]["seeds"]
    print(f"\n=== STAGE 2: control {control_lr:.1e} vs treatment {treatment_lr:.1e}, "
          f"seeds {seeds} ===")
    t_stage = time.time()
    jobs = ([("control", control_lr, sd) for sd in seeds]
            + [("treatment", treatment_lr, sd) for sd in seeds])
    res = _run_jobs(jobs, C, device, args.workers, str(corpus_path))
    arms = {"control": [], "treatment": []}
    for label, lr, sd, loss, secs, _p in sorted(res, key=lambda r: (r[0], r[2])):
        arms[label].append(loss)
        print(f"  {label:<10} seed {sd}  train loss {loss:.4f}   ({secs:.0f}s)")
    print(f"  stage 2 wall clock: {time.time() - t_stage:.0f}s")

    c, t = arms["control"], arms["treatment"]
    mc, mt = sum(c) / len(c), sum(t) / len(t)
    gap = mc - mt
    overlap = not (max(t) < min(c) or max(c) < min(t))

    print("\n" + "=" * 62)
    print(f"control   lr {control_lr:.1e}  mean {mc:.4f}  range [{min(c):.4f}, {max(c):.4f}]")
    print(f"treatment lr {treatment_lr:.1e}  mean {mt:.4f}  range [{min(t):.4f}, {max(t):.4f}]")
    print(f"gap (control - treatment) = {gap:+.4f}   bar = {bar}")
    print(f"ranges overlap = {overlap}   (bar requires NO overlap)")
    passed = (gap >= bar) and (not overlap)
    # The verdict carries its own provenance. A label kept only in a filename or
    # a person's memory gets conflated with the canonical result eventually; one
    # written into the string itself travels with the number wherever it is
    # pasted.
    verdict = (f"{'PASS' if passed else 'FAIL / NULL'} "
               f"[{'QUICK SANITY RUN, not a result. ' if args.quick else ''}"
               f"{args.profile} profile: {C['steps']} steps, "
               f"{len(sweep_lrs)}-LR grid, {len(seeds)} seeds]")
    if args.profile == "fast":
        verdict += (" - claim: reaches lower train loss FASTER; "
                    "NOT the canonical effect size")
    print(f"\nPREREGISTERED VERDICT: {verdict}")
    if gap < 0 and abs(gap) >= bar:
        print("NOTE: control WON — the hypothesis is falsified on this rig.")
    print("=" * 62)

    # A sanity run must never overwrite a preregistered result file.
    if args.quick:
        out = HERE / "exp_lr_width_result_quick.json"
    elif args.profile == "fast":
        out = HERE / "exp_lr_width_result_fast.json"
    else:
        out = HERE / "exp_lr_width_result.json"
    out.write_text(json.dumps({
        "profile": args.profile, "prereg_file": pf, "success_bar": bar,
        "verdict_string": verdict,
        "claim": prereg.get("claim_this_licenses", ""),
        "config": C, "device": device, "quick": args.quick,
        "sweep": {str(k): v for k, v in sweep.items()},
        "control_lr": control_lr, "treatment_lr": treatment_lr,
        "seeds": seeds, "control_losses": c, "treatment_losses": t,
        "mean_control": mc, "mean_treatment": mt, "gap": gap,
        "ranges_overlap": overlap, "passed": passed,
    }, indent=2), encoding="utf-8")
    # The endpoint here is TRAIN loss, so the training text is on the row: a
    # gap between two arms means nothing if they were not reading the same
    # documents. The split is on it too -- every arm still trains on the train
    # side of one -- and the timings are device numbers. All three are reported
    # by the arms themselves, because the corpus is built inside the workers.
    prov = provenance_of(sweep_res + res)
    runlog.record("experiment", name=f"lr_vs_width[{args.profile}]",
                  device=device, data_device=prov["data_device"],
                  corpus=runlog.corpus_fingerprint(text),
                  train_fingerprint=prov["train_fingerprint"],
                  split_fingerprint=prov["split_fingerprint"],
                  config=C,
                  metrics={"verdict": verdict, "gap": gap,
                           "mean_control": mc, "mean_treatment": mt,
                           "wall_s": time.time() - t_all})
    print(f"wrote {out.name}   total wall clock {time.time() - t_all:.0f}s")
    print(f"recorded to {runlog.LOG.name}")


if __name__ == "__main__":
    main()
