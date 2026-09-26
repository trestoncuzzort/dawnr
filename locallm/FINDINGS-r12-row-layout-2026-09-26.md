# Does the row-layout finding hold on the real r12 path? 2026-09-26

## Why

`FINDINGS-denoising-2026-09-26.md` measured, on a 3.5M model trained from
scratch with a character tokenizer on the r12 corpus, that whole-document rows
starting at each document's head drive most of the fine-tune's memorisation:
best held-out loss 1.221 nats/char for whole rows, 0.694 for random windows,
0.571 for fill-in-the-middle at rate 0.5. r12's own fine-tune recipe uses
whole-document rows (`--doc-batches`, `t/RUN-NEXT-locallm-r12.md` section C),
chosen to keep document heads intact (Ding et al., arXiv:2404.10830). That
note's own "Next" section says plainly this has not been checked "on the
actual r12 path, a pretrained core with its BPE tokenizer... before r12
trains." This is that check.

Two things differ from the denoising setup and could change the answer:

- **A pretrained core, not a random init.** The model already has priors over
  code- and English-shaped text before it sees a single r12 document; whether
  head-keying still dominates memorisation when the model did not have to
  learn the alphabet from these 302 documents is exactly the open question.
- **A BPE tokenizer, not characters.** The corpus is 46,173 tokens at the
  core's frozen vocabulary against 108,477 characters: coarser units could
  make head-keying cheaper (fewer tokens to memorise a document's identity)
  or costlier (each token carries more information, so getting the first one
  right constrains less).

## Set-up (fixed before the runs)

- **Core**: the lab's `wd0.8-lr1e-3-seed1337` pretraining arm
  (`internal/PRETRAIN-R12-2026-09-25.md`, "Results"), copied by `scp` from the
  lab workstation into a scratch directory outside this repository. **This is
  the step-11,200 state, not the best one** (best was step 7,400, validation
  1.166, and was overwritten before this note was written; see the checkpoint
  fix earlier in this session). The core's own overfit does not change which
  row layout memorises the r12 corpus faster, which is what this note asks,
  but it means the core going into every arm here is not the best available
  core, and whoever reads these numbers should not read them as r12's final
  fine-tune result.
- **Corpus**: `t/loop_locallm.py corpus --lifted --lifted-set
  t/out/lifted-tasks-2026-09-26=t/COVERAGE-lifted-2026-09-26.md --split
  t/out/loop/split-v5.json`, built from the main checkout (`/home/t/tup`,
  read-only): 302 documents, 108,477 characters, 46,173 tokens under the
  core's frozen BPE tokenizer (8,192 entries) -- the same corpus, by
  construction, as the denoising note's.
- **Trainer**: `locallm/continue_from_checkpoint.py --init <core>`, hash split
  at `--split-seed 1337` (32 validation documents at the character level in
  the denoising note; the hash split is over document text, so the same 32
  documents are held out here). `--steps 300 --lr 3e-5 --block-size 512
  --batch-size 8 --dropout 0.1 --deterministic`, the section-C recipe
  `t/RUN-NEXT-locallm-r12.md` already runs (chosen because it is the recipe
  that produced the anchor number below, not a new budget invented for this
  note).
- **Arms**, one flag changed at a time from that command:
  1. **whole rows**: `--doc-batches` (r12's current choice).
  2. **random windows**: no `--doc-batches` (the windows path).
  3. **FIM**: `--doc-batches --fim-rate 0.5` (r12's row layout plus the
     denoising note's rate).
- **Seeds**: 1337, 7, 42 (the pretraining sweep's `SEEDS`), same three for
  every arm. `--seed` varies; `--split-seed 1337` is fixed across every run,
  so every arm and seed is scored on the same 32 held-out documents.
- **Early stopping**: off (`continue_from_checkpoint.py` has no early-stopping
  option to turn off; the fixed `--steps 300` is the whole budget, as it is
  for every other run of this recipe).
- **Validation**: on untransformed text in every arm, including FIM ("Validation
  and the reported train loss stay left to right", `continue_from_checkpoint.py`
  module docstring). Loss units: nats per token (BPE), not nats per character
  (the denoising note's char-tokenizer numbers do not compare directly to
  these; only the *ordering* of the three arms is the thing being checked
  against the denoising result, not the absolute numbers).

### Why this step budget

The task instruction for this note anchors the budget on an existing
measurement: r12's whole-document fine-tune at these exact hyperparameters
(steps 300, lr 3e-5, block 512, batch 8, `--doc-batches`, dropout 0.1) has
already been run at least three times (r7, r9, r11) and lands at **0.08-0.11
nats/token training loss against 0.6-1.1 held out**
(`internal/PRETRAIN-R12-2026-09-25.md`, "Replay in the r12 fine-tune"; the
same range as the denoising note's from-scratch pilot, 0.11 train / 0.68 held
out, though that pilot used a different model and tokenizer). This was
expected to already be the "whole-row arm clearly overfits" regime the task
asks for, at the recipe r12 already runs, so no new budget was planned before
the first run.

**It was not.** All nine 300-step runs (below, kept rather than discarded)
finished with their lowest validation loss AT the last step -- every arm, every
seed, still improving at step 300, not yet overfit. The whole-rows arm's train
loss at step 300 was 0.28, well above the 0.08-0.11 anchor. r7/r9/r11 evidently
overfit faster than this run does at the same step count; the likely reason is
that the anchor runs continued a different (and, per the checkpoint-keeping fix
earlier in this session, in one case now-lost) core, not the wd0.8-lr1e-3
step-11,200 core copied for this note -- a fresher core generalises longer
before it starts reciting these 302 documents. Rather than force a false "the
budget already overfits" claim, a single-seed probe (whole rows, seed 1337,
1,500 steps, otherwise identical) was run to find where this core's fine-tune
actually turns over:

| step | train | val |
|---:|---:|---:|
| 300 | 0.155 | 0.606 |
| 350 (best) | 0.125 | 0.599 |
| 600 | 0.062 | 0.655 |
| **900** | **0.045** | **0.696** |
| 1,200 | 0.041 | 0.728 |
| 1,500 | 0.040 | 0.741 |

**The step budget is revised to 900** (train loss well below the anchor's
0.11, held-out loss risen 16% off its own minimum, train down 64% from the
best step's own 0.125): unambiguous overfitting, at a budget still cheap
enough (three arms, three seeds, ~70 s each on the desktop's RTX 4080) to run
before r12 trains. Every arm and seed below uses `--steps 900` with the same
lr, validation split and every other setting already fixed above; the
300-step numbers are reported too, since they were run and are informative in
their own right (nothing at 300 steps had reached its held-out minimum, in
any arm), but the decision rule below is applied to the 900-step numbers.

## Metrics

- **best val**: the lowest validation loss (nats/token) at any of the
  `metrics.jsonl` evaluation rows, and its step. `--eval-every 20 --log-every
  20` (equal, so every logged row is a fresh evaluation rather than a stale
  value between less-frequent logging and more-frequent evaluation, which is
  how the script's defaults, 50 and 25, would otherwise interleave).
- **final val / final train**: the last step's validation and training loss.
- **gap**: final val minus final train.
- **noise**: for each metric, the larger of the three seeds' ranges (max
  minus min) within an arm.

## Decision rule (the same shape as the denoising note's)

1. **Windows reduce the gap** if the windows arm's mean gap is below the
   whole-rows arm's mean gap by more than the noise, and no windows seed's gap
   is as high as any whole-rows seed's.
2. **Windows generalise better** (the claim that matters, not just "memorises
   slower") only if, in addition, the windows arm's mean best val is below the
   whole-rows arm's by more than the noise, with no overlap between the two
   arms' seed values. A narrower gap with best val inside the noise is
   reported as "windows slow memorisation but do not generalise better" --
   a no.
3. **FIM adds beyond windows** if FIM's mean best val is below the windows
   arm's by more than the noise, no overlap. If FIM's best val sits inside the
   windows arm's noise band, FIM is reported as "no better than windows alone
   on this path" -- which is what the denoising note's "most of the gain is
   available without FIM at all" would predict if it transfers.
4. Any arm whose best val is *worse* than the whole-rows arm's by more than
   the noise is reported as that arm hurting, not helping.
5. **The finding holds** on the r12 path only if rule 2 passes (windows beat
   whole rows on held-out loss, not just on the gap). If rule 2 fails --
   whole rows and windows land inside each other's noise, or whole rows
   actually generalise better with a pretrained core and BPE tokens -- the
   finding is reported as not transferring, plainly, the way the denoising
   note reported its own prediction being wrong.

## Prediction

- **Arm 1 (whole rows)**: reproduces the historical range: best/final val
  0.6-1.1 nats/token, final train 0.08-0.11.
- **Arm 2 (windows)**: the denoising note's ratio (best val 0.694 / 1.221 =
  0.57 of the whole-rows number) transfers approximately: best val around
  0.35-0.65, i.e. noticeably below arm 1, and a smaller gap. This is the
  operator's best guess, not a re-derivation from this setup -- the denoising
  note's own prediction for its from-scratch rate-0.5 arm was wrong by 10x in
  the size of the effect, so this prediction is held loosely.
- **Arm 3 (FIM 0.5)**: at least as good as windows, plausibly a further
  incremental improvement (denoising note: FIM's best val 0.571 against
  windows' 0.694, beyond noise), but the two effects (dropping the
  whole-row-at-head anchor; denoising) may not add the same way with a
  pretrained core, so no numeric range is committed beyond "no worse than
  windows beyond noise."
- **What would falsify "the finding holds"**: arm 1 and arm 2's best-val
  ranges overlapping, or arm 1 beating arm 2. A pretrained core already knows
  how to write plausible code and English before seeing any r12 document; if
  its held-out loss is dominated by *task content* it has never seen rather
  than by *which of these 302 documents this is*, head-keying may matter far
  less here than it did for a model that learned the alphabet from these same
  302 documents, and the finding would not transfer.

## What this note does not settle

- Loss ordering, not clean-answer counts. As `internal/PRETRAIN-R12-2026-09-25.md`
  says of the pretraining sweep, "not loss: validation loss has twice failed to
  predict behaviour here" for the thing that actually matters (tests passed on
  the dev/held-out split). This note's verdict is about which row layout
  memorises the corpus fastest at the fixed step budget, which is a necessary
  input to r12's row-layout choice, not the whole of it.
- The core used is the step-11,200, not the step-7,400, state of its
  pretraining arm (see above); a rerun once the corrected core exists would
  use the actually-best core, though the row-layout ordering is not expected
  to depend on which step of the same pretraining run was used.
