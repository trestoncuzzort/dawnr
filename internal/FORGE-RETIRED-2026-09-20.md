# forge, retired 2026-09-20: the parked items from the line that was closed

`forge/` was this repository's first training pipeline, aimed at a different
task (DPO on an 8B base over an SQL/AceCode task bank, graded by the twins it
refutes). Its last real commit is 2026-09-01; nothing outside it ever imported
it, and the locallm and t lines superseded it. The directory was removed from
the working tree on 2026-09-20 and is in git history at `a736d82` if it is ever
needed.

This file is its OPEN-ITEMS list, kept because the traps it names are
methodology rather than forge trivia, and this project keeps hitting them:
a saturated ruler, a noise floor assumed instead of measured, a variance term
with nowhere to live, and acceptance evidence aimed at a path production never
takes. The specific file paths below point into the deleted tree and are left
as written; they resolve in git history.

The one piece of forge that is still load-bearing was inlined into
`t/loop_train.py` before deletion: why a LoRA merge must happen in bf16 against
the full-precision base and never the 4-bit one.

---

# OPEN ITEMS

One line per parked thing: **why** it is parked and **where** the details live.
Parked is not done. Prune entries when they close.

## Track A (DPO pipeline)

- ~~**Zero gradient steps.**~~ CLOSED 2026-07-28 — the path was exercised end to end on
  `Qwen/Qwen2.5-0.5B-Instruct` (10 steps, real adapter + `run_meta.json` written,
  DPO+NLL confirmed live).

- **No run on the real base; no efficacy result.** Nothing has run on the real 8B
  base, no held-out evaluation has been scored, and no prereg is signed. A smoke
  test is not a result.
  *Where:* `data/smoke_rpo_alpha_result.json`, README "Track A" status paragraph.

- ~~**The ruler is saturated, and its noise floor was understated.**~~ REPLACED
  2026-07-29 (§69–§72). The old 10-task bank is spent (§64: pass@20 == pass@3 ==
  0.9000, 7 at ceiling / 1 at floor). A 31-task replacement was screened from
  AceCode `oss`, confirmed at n=60, and FROZEN — `data/ruler_frozen.json`, set
  sha256 `74560a4c…`, with a disjoint 43-tid training pool declared in the same act.
  Its noise floor is now MEASURED, not assumed: run-level pass@1 sd **0.0283** over
  10 null replicates under the pinned verifier.
  *Where:* `data/ruler_frozen.json`, `screen_tasks.NOISE_FLOOR`, §71/§72.

- **`se_diff = sqrt(2)*run_sd` has no slot for TRAINING-SEED variance**, and that is
  bigger than the homoscedasticity question it was raised as. The null arm is one
  checkpoint, so it has **zero** training variance by construction; the trained arm's
  seed / data-order / init variance has nowhere to live in the formula. One
  checkpoint cannot support a claim about DPO at any k (council #17, citing Dodge
  et al. 2020, Bouthillier et al. 2021). **Fix costs zero extra generations:** spend
  the same trained budget across 2–3 seeds, never pool (Welch from each arm's own
  sd), pair by task, and re-estimate variance mid-run rather than pre-sizing — but
  re-size on the variance, never stop on the effect.
  **MEASURED 2026-08-31** from the banked hc-seed campaign (11 seeds × 40 replicates,
  frozen ruler, pinned verifier): sigma_seed ≈ 0.0019 vs within-seed 0.0323; the
  observed sd of seed means (0.0054) sits barely above the replicate-noise
  prediction (0.0051); the missing slot underestimates se_diff by ~6% at this
  recipe; 2/55 pairwise Welch rejections at alpha .05 (empirical rate .036). The
  campaign was unpreregistered, so this SIZES Run 2 — it does not close the item;
  the confirmatory multi-seed design still belongs to Run 2's prereg.
  *Where:* `analyze_seed_variance.py`, `council/seed_variance_decomposition.txt`,
  §76 (council), `council/ruler_noise_analysis_n40.txt`.

- **The measured sd was compared against the wrong null, and the "independence
  holds" reading is WITHDRAWN.** Observed 0.0381 vs the 0.0376 the sizing rows
  assume is 1.01×, but that null lets all 5 draws vary and the greedy draw is
  constant on 31/31 tasks. Against the correct null (0.0326) the observed sd is
  **1.17× — excess variance, not agreement**; the 1.01× was the constant greedy draw
  (0.894×) cancelling excess between-task covariance. The ratio's CI contains 1.0, so
  the excess is a direction, not a fact. **§70's sizing rows are unaffected and stand
  as published** — the generation counts were derived from 0.0376 and that is what
  was observed. Corrected in §77.
  *Where:* `screen_tasks.NOISE_FLOOR` (both nulls recorded), §75 F1, §76 C2/C4, §77.

- ~~**`data/ruler_frozen.json` records n=10 eval-instrument rates.**~~ CLOSED
  2026-07-30 (§77). Sample-dependent figures are no longer frozen at all — a frozen
  file should hold only what is frozen. `eval_instrument_rate` and
  `eval_instrument_out_of_band` are stripped; measured rates live in
  `council/ruler_noise_analysis_*.txt`, dated and re-derivable. Set sha256 unchanged
  at `74560a4c…` because it never covered the rates.

- ~~**The freeze has no gate.**~~ CLOSED 2026-07-30 (§77, council #17 F2).
  `freeze` wrote `ruler_set_sha256` and nothing read it, so the freeze was a comment.
  `build_ruler.verify_frozen()` now re-hashes every task from its stored screen
  payload and `ruler_noise` obtains the ruler only through it. Red witness both ways:
  a corrupted task hash and a corrupted set hash are each refused; clean passes.

- **Four frozen ruler tasks sit outside [0.2, 0.8] under the eval instrument.** At
  n=40: `ace_oss_16070` (0.880), `ace_oss_19459` (0.855), `ace_oss_2454` (0.180),
  `ace_oss_24748` (0.145). Frozen and flagged rather than dropped, because dropping
  them selects on the very measurement being reported and each drop-and-remeasure
  round biases the next. So the ruler is **27 clearly-live channels plus 4 weak
  ones**, and 0 dead channels across 40 runs. All four are pushed out by the greedy
  anchor (each has greedy pinned at 1.00 or 0.00).
  *Where:* `data/ruler_frozen.json` → `eval_instrument_out_of_band`, §73.

- **The greedy anchor is 20% of every eval score and it is a deterministic
  constant.** `eval.py` samples 1 draw at temp 0.0 + 4 at 0.8, and the resulting
  rate is exactly `0.2*greedy + 0.8*temp0.8` (verified to 0.000000 over 31 tasks).
  Greedy was constant on 31/31 tasks across **40** runs. **CORRECTED (§77):** it is
  NOT the reason tasks fall out of band — it accounts for **1 of 4**
  (`ace_oss_2454`); the other three are outside on their temp-0.8 rates alone. My
  earlier "all four" was an inference from "each has greedy pinned at 1.00 or 0.00"
  and does not follow. The real case against it is **estimator validity**: Chen et
  al.'s unbiased pass@k assumes n i.i.d. draws and this is a 20/80 policy blend, so
  0.894× is bias at a changed estimand, not variance reduction. Two decisions are
  open and both go to the proprietor: adopt greedy-free pass@1 as the metric
  (**already measured at zero cost** — mean 0.4905, sd 0.0476, MDE 2.98pp at 40
  replicates/arm, since `sampled` is recorded separately), and **drop 3 from `KS`** —
  a [0.2,0.8] pass@1 band maps to [0.488,0.992] at k=3, so 20/31 tasks are outside
  the band at k=3 by construction. Level shift is 2.45pp, which is why it is a
  decision and not a cleanup. Re-baselining cost is **zero**: all 68 existing
  `eval_history` rows already lack the verifier key and the greedy/sampled split.
  *Where:* §76 Q1, §77, `ruler_noise.py` CAUSE 1.

- **The pin created a training confound nobody has checked.** Under the pinned 3.11,
  omitting `from typing import List` FAILS — and the AceCode `oss` prompts carry
  annotated signatures that invite exactly that omission. Pairs drawn from the 43-tid
  training pool may therefore have `rejected` rejected for a missing import, so DPO
  would learn import hygiene and the ruler would reward it: **true positive on the
  instrument, false positive on the thesis.** Cheap pre-check, NOT yet run: count
  `rejected` completions failing with a `NameError` naming a typing generic.
  *Where:* §76 Q3, §77.

- ~~**`export_adapter.py` does not exist.**~~ CLOSED 2026-07-28. Built and verified
  end to end on the smoke adapter: conversion exit 0 with tensor count 336 = 336,
  both the adapted model and the null baseline created, coherent spot check, and
  the adapter-is-live control passed (lora_B × 50,000 → output similarity 0.0238
  vs null, i.e. the ADAPTER directive is genuinely applied, not silently ignored).
  Requires llama.cpp's converter — set `SRLM_LLAMA_CPP` if it is not at
  `C:\Users\t\llama.cpp`. *Where:* `export_adapter.py`, `data/export_acceptance_result.json`.
  STILL OPEN: only exercised against a 0.5B stand-in; the real 8B base is untested
  on this path.

- **No Track A prereg.** The only prereg files are `localllm/prereg_lr_width{,_fast}.json`,
  both Track B. §14/§18 specify N + sha256 + recipe must be recorded before run 1.
  *Where:* `build_training_set.py` closing print; `instructions.txt` §14.

## Data

- **`data/dpo_pairs_capped.jsonl` is CRLF on disk; the builder now writes LF.**
  Deliberately NOT regenerated: the 918 pairs are byte-identical in content, only line
  endings differ, and the file is pinned by council §12/§14 rulings. Consequence —
  rebuilding it changes its sha256, which invalidates the receipt and makes training
  refuse until `verify_dataset.py` is re-run. That is the gate working, not a fault.
  *Where:* `build_training_set.py` (the `newline=""` comment), `dataset_gate.py`.

- **3 pairs appear in both `dpo_pairs.jsonl` and `repair_pairs.jsonl`**
  (`dpo_pairs:13 / repair:2`, `dpo_pairs:435 / repair:35`, `dpo_pairs:1016 / repair:21`).
  They are verified once, but would be seen twice per epoch under `--include-repair`.
  Not deduplicated because that changes a council-pinned dataset. Default run-1 config
  (capped only) is unaffected.
  *Where:* `verify_dataset.py` (`signature()` dedup), README Track A section.

## Guard scope

- **Cross-version verifier divergence beyond the annotation case is unenumerated.**
  §71 found `forge.verify()` launching `[sys.executable, …]`, so ground truth was
  inherited from the caller: guarded scripts (`screen_tasks.py`, `build_ruler.py`)
  re-exec under `.venv-train`/3.11, unguarded ones (`eval.py`, `forge.py`) ran under
  3.14. Red witness: 310 identical completions scored **172/310 on 3.14 vs 154/310
  on 3.11**, all 18 disagreements one way, cause PEP 649 deferred annotations. Now
  pinned in one place (`dataset_gate.verify_py`) and recorded in the receipt
  (schema 4). `tests/test_verifier_pin.py` is a fixed probe for that one mechanism
  plus a structural check that the interpreter is no longer inherited — **a
  flashlight, not a fence.** Other 3.11↔3.14 semantic differences are not swept, and
  the fingerprint covers the interpreter version but not its installed packages, the
  OS, or CPU-dependent behaviour.
  *Where:* `forge.py` pin block, `dataset_gate.py` VERIFIER_FILES block, §71.

- **The dataset receipt is unsigned.** It defends against drift and accident, not
  against someone editing the receipt itself. Stated deliberately rather than implied.
  *Where:* `dataset_gate.py` module docstring, "WHO MAY ISSUE A RECEIPT".

## Third-party datasets (imported 2026-07-28, for building the second instrument)

- **KodCode-V1 is CC BY-NC 4.0 and must never be redistributed from this repo.**
  487,432 triplets, pytest-style tests. Downloaded for LOCAL screening only -
  downloading is not redistributing, but publishing its rows from an MIT repo
  would make this repo's own licence untrue. If a task derived from it ever needs
  to ship, it must be re-derived independently or the licence renegotiated.
  *Where:* `.gitignore` third-party block, verified on the HF dataset card.

- **AceCode-89K is MIT and may be redistributed with attribution.** 87,149 rows,
  bare `assert` test cases (~16 per question) - structurally the same shape
  `forge.py` already runs, which is why it is the import candidate rather than
  KodCode. Attribution must accompany any published subset.
  *Where:* `.gitignore` third-party block; TIGER-Lab/AceCode-89K on HuggingFace.

- **The second instrument is costed but not built.** To detect a +3% effect at 80%
  power needs ~30 movable tasks at k=5 seeds per side (~50 at k=3, ~150 at k=1);
  +5% needs ~11 at k=5. A paired before/after design does NOT help here - measured
  1.0x, because the aggregate is already a per-task average and the residual noise
  is per-task binomial sampling, which pairing cannot cancel. The current ruler has
  4 movable tasks; the other 6 are pinned at 1.000 and carry no signal.
  *Where:* `data/eval_history.jsonl` (57 runs), README Track A status paragraph.
