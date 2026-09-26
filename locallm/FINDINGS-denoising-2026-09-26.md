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
