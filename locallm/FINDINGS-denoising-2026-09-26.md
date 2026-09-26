# Denoising (fill-in-the-middle) against memorisation, 2026-09-26

## Why

locallm memorises its fine-tune corpus: 0.11 nats/token on training text
against 0.68 held out. The north star (`AMBITION.md`) asks for a model that
learned rather than memorised. Denoising is the standard way to make one
document teach several prediction problems instead of one; for a decoder-only
model the form is fill-in-the-middle (Bavarian et al., arXiv:2207.14255),
implemented in `fim.py` and wired as `--fim-rate` into `train.py` and
`continue_from_checkpoint.py`. Each epoch, each training document is re-cut
with probability 0.5 into `<PRE> prefix <SUF> suffix <MID> middle <EOT>` (half
of those in the paper's SPM order), character-level cuts, loss on every token.

## Set-up (fixed before the runs)

- Corpus: the proved corpus in r12's form, `t/loop_locallm.py corpus --lifted
  --lifted-set t/out/lifted-tasks-2026-09-26=t/COVERAGE-lifted-2026-09-26.md
  --split t/out/loop/split-v5.json`: 302 documents, 108,477 bytes.
- Trainer: `continue_from_checkpoint.py --doc-batches` from a random init (one
  whole document per row, hash split at split seed 1337: 32 validation
  documents, 10.9% of the characters). Driver: `exp_fim_denoising.py`.
- Model: the studio's Medium width and depth (4 layers, 4 heads, width 256,
  3.5M parameters) with a 1,280-character context so no document is cut;
  character tokenizer with the four FIM sentinels in every arm.
- 3,000 steps, batch 16 (about 176 epochs), lr 3e-3 cosine to 3e-4, warmup
  100, dropout 0, early stopping off, evaluation every 50 steps.
- Arms: `--fim-rate 0` and `--fim-rate 0.5`, seeds 1, 2, 3. A seed fixes the
  init (shared by both arms) and the batch order.
- Every loss is on untransformed left-to-right text: the token-weighted mean
  over every training or validation document once.
- A secondary arm, `--fim-rate 0.5 --fim-span t` (whole t clauses and
  statements as the middle half the time), is run the same way and judged by
  the same rule, as exploration.

The budget was chosen from one pilot, rate 0 at seed 99 (not one of the
experiment's seeds): validation bottomed at 1.24 near step 300 and climbed to
1.80 by step 3,000 while training loss fell to 0.016. The budget is therefore
deep into memorisation, which is the regime in question.

## Metrics

- **gap**: final validation loss minus final training loss, at step 3,000.
- **best val**: the lowest validation loss at any evaluation, and its step.
- **noise**: for each metric, the larger of the two arms' seed ranges
  (max minus min over the 3 seeds).

## Decision rule

1. **FIM reduces the gap** if the FIM arm's mean gap is below the rate-0 arm's
   by more than the noise, and no FIM seed's gap is as high as any rate-0
   seed's.
2. **FIM helps** (the claim that matters: the model learned more, not just
   memorised less) only if, in addition, the FIM arm's mean best val is below
   the rate-0 arm's by more than the noise with no overlap between seeds.
   A narrower gap with a best val inside the noise is reported as "FIM slows
   memorisation but does not make the model generalise better", which is a no.
3. A FIM arm whose best val is worse than rate 0's by more than the noise is
   reported as FIM hurting.

## Prediction

- Rate 0: best val about 1.24 near step 300, final val about 1.8, final train
  about 0.02, gap about 1.78 (the pilot).
- Rate 0.5: the gap narrows by 20-40% (to about 1.1-1.4), because the model
  sees each document left to right only about half the time and cannot fit
  the transformed rows as tightly. Best val improves by 0.02-0.08 nats (to
  about 1.16-1.22) and bottoms later (steps 400-600).
- So the operator expects rule 1 to pass and rule 2 to be close; if rule 2 fails, the gain
  is a slower route to the same memorisation, not learning.
- Infilling on held-out documents: the rate-0.5 model closes with `<EOT>` on
  most probes (over 80%); exact whole-clause infills rare but present
  (10-30%); exact random character spans rarer.

## Result

(written after the runs, below this line, without editing anything above it)

Run 2026-09-26 on the desktop's graphics card, one run at a time, about 80
seconds each. Numbers from `python exp_fim_denoising.py summarize`; every
loss is nats per character on untransformed text. The rate-0 and rate-0.5
final validation losses were recomputed through a separate path (load the
final checkpoint, score each validation document alone) and matched to four
decimals. No validation document is a copy of a training document; the mean
best line overlap of a validation document with any one training document is
0.61 (maximum 0.94), the same for every arm.

### The pre-registered arms

| arm | seed | best val | at step | final val | final train | gap |
|---|---|---|---|---|---|---|
| rate 0 | 1 | 1.2158 | 350 | 1.8752 | 0.0162 | 1.8591 |
| rate 0 | 2 | 1.2528 | 350 | 1.8593 | 0.0162 | 1.8431 |
| rate 0 | 3 | 1.1936 | 400 | 1.8367 | 0.0162 | 1.8205 |
| **rate 0, mean (range)** | | **1.2207 (0.059)** | 367 | 1.8571 (0.039) | 0.0162 | **1.8409 (0.039)** |
| rate 0.5 | 1 | 0.5756 | 1150 | 0.6390 | 0.0172 | 0.6218 |
| rate 0.5 | 2 | 0.5788 | 900 | 0.6711 | 0.0176 | 0.6535 |
| rate 0.5 | 3 | 0.5573 | 1150 | 0.6403 | 0.0176 | 0.6227 |
| **rate 0.5, mean (range)** | | **0.5706 (0.021)** | 1067 | 0.6502 (0.032) | 0.0175 | **0.6327 (0.032)** |

**Rule 1 passes.** The gap falls from 1.841 to 0.633, by 1.21 nats against a
noise of 0.039, and the highest FIM gap (0.654) is far below the lowest
rate-0 gap (1.821).

**Rule 2 passes.** Best validation loss falls from 1.221 to 0.571, by 0.65
nats against a noise of 0.059, with no overlap (worst FIM seed 0.579, best
rate-0 seed 1.194). Final validation loss falls from 1.857 to 0.650.
**FIM helps**, under the rule written before the runs.

**The prediction was wrong, in the direction of the effect being much
larger.** Predicted: the gap narrows 20-40% and best val improves 0.02-0.08
nats. Measured: the gap narrows 66% and best val improves 0.65 nats (53%).
Predicted best step 400-600; measured 900-1150.

What did not change: the training text is memorised just as hard. Final
train loss is 0.0175 with FIM against 0.0162 without. The gap closes from the
held-out side: the FIM model fits every training document almost exactly and
still predicts unseen documents at a third of the loss.

### Controls added after the result (not pre-registered)

A gain ten times the prediction needed a check that it was FIM and not any
change to how the rows look. Two controls, same seeds, same inits, same
budget, judged by the same rule, run after the table above was known:

| arm | best val, mean (range) | at step | final val | final train | gap, mean (range) |
|---|---|---|---|---|---|
| rate 0, dropout 0.1 | 0.9570 (0.051) | 650 | 1.2851 | 0.0163 | 1.2688 (0.101) |
| rate 0, random windows | 0.6940 (0.028) | 550 | 0.8878 | 0.0368 | 0.8510 (0.065) |
| rate 0.5, whole rows (above) | 0.5706 (0.021) | 1067 | 0.6502 | 0.0175 | 0.6327 (0.032) |

- `rate 0, random windows` is left-to-right training on 1,280-character
  windows cut at random offsets from the joined corpus (the windows path, no
  `--doc-batches`); its kept checkpoints every 50 steps were re-scored with
  the same document loss.
- A standard regulariser buys a third of FIM's gain (1.22 to 0.96).
- **Most of the gain is available without FIM at all.** Random windows alone
  take best val from 1.22 to 0.69. With `--doc-batches` every row starts at
  its document's head and the model can key each document on its first
  characters; windows, like FIM, take that anchor away. This matters for r12,
  which adopted whole-document rows (Ding et al., arXiv:2404.10830) to keep
  heads intact: from scratch, on this corpus, whole-document rows memorise
  far worse than windows do. That has not been measured on the r12 recipe
  (a pretrained core, BPE), and should be before r12 trains.
- **FIM still beats windows beyond the noise**: 0.571 against 0.694, a
  difference of 0.12 against a noise of 0.028, no overlap (worst FIM seed
  0.579, best windows seed 0.679). Gap 0.633 against 0.851, noise 0.065, no
  overlap.

### The t-aware arm

`--fim-span t` was run twice. The first version took one whole clause,
invariant or statement line for half the FIM documents. The version kept in
`fim.py` follows AST-FIM (arXiv:2506.00204): units are clauses, invariants,
statements, expressions and `{ }` blocks, one chosen with probability
proportional to its size for 90% of FIM documents, and a random character
span for the other 10%.

| arm | best val, mean (range) | at step | final val | gap, mean (range) |
|---|---|---|---|---|
| rate 0.5, char | 0.5706 (0.021) | 1067 | 0.6502 | 0.6327 (0.032) |
| rate 0.5, t, first version (50% line units) | 0.5729 (0.018) | 1000 | 0.6612 | 0.6438 (0.018) |
| rate 0.5, t, AST-FIM taxonomy (90% units) | 0.5924 (0.014) | 817 | 0.6858 | 0.6686 (0.020) |

Syntax-aware spans do not help left-to-right held-out loss here. The first
version is level with character spans. The AST-FIM version is worse by 0.022
against a noise of 0.021, with no overlap between seeds, so at this scale
more syntactic middles give slightly less of the regularising effect. AST-FIM
claims its gain on infilling benchmarks, not on left-to-right loss (its
section 7), which is consistent.

### Can the model infill?

`exp_fim_denoising.py infill`: 32 validation documents, two probes each (one
whole unit from `fim.t_units`, one random character span), greedy decoding,
PSM prompt, per seed.

| arm | exact middles | closed with `<EOT>` |
|---|---|---|
| rate 0.5, char | 0, 0, 0 of 64 | 29, 44, 39 of 64 |
| rate 0.5, t (AST-FIM) | 1, 1, 0 of 64 | 51, 46, 53 of 64 |
| rate 0 | 0 of 64 each | 0 of 64 each |

The infill prediction was also wrong: `<EOT>` closure is 45-69% for character
spans (predicted over 80%), and exact whole-unit infills are about 1%
(predicted 10-30%). Read by hand (seed 1, t arm), the middles are well-formed
t: a real invariant, a real requires clause, a loop body. But they are
attached badly. After a prefix ending `requires ` it writes `requires 1 <= mo`,
repeating the keyword. Asked for `i_v2 + 1` after `i_v2 := `, it writes a
different whole statement. It has learned the shape of a unit and when to
stop, not how to join a prefix to a suffix. This model is 3.5M parameters,
trained on 270 documents.

### What was learned

- Denoising works on this memorisation problem, and by far more than
  predicted: held-out loss halves at the same training-text fit. Measured on
  a 3.5M model trained from scratch, not yet on the r12 fine-tune.
- The biggest single cause of the memorisation in this setup is the row
  layout, not the objective: whole-document rows that always start at the
  head. Random windows remove most of it, and FIM removes more.
- Syntax-aware spans are not a lever for left-to-right loss at this scale.
- The infilling this produces is shallow: well-formed units that do not join.

### Next

1. Run the same three arms (rate 0 whole rows, rate 0 windows, rate 0.5) on
   the actual r12 path, a pretrained core with its BPE tokenizer through
   `continue_from_checkpoint.py` (sentinels are added with mean-initialised
   rows), and re-measure the 0.11 / 0.68 gap there. The whole-rows against
   windows result bears directly on r12's `--doc-batches` decision.
2. FIM rate 0.5 against 0.7 and 0.9 (the paper recommends 0.5-0.9), and FIM
   on the windows path, which combines both effects.
3. Judge by clean answers on the held-out 232, not by loss: lower held-out
   loss is necessary, not sufficient.
4. Score infilling by middle-only perplexity, as AST-FIM's Real-FIM-Eval
   does, which separates "cannot join" from "cannot write the unit".
