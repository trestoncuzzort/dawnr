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
  t/out/loop/split-v5.json`, built from the main checkout (read-only): 302
  documents, 108,477 characters, 46,173 tokens under the
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

## Result (written after the runs, below this line, without editing anything above it)

All nine 300-step runs and all nine 900-step runs completed on the desktop's
RTX 4080, one at a time under `systemd-run --user --scope -p MemoryMax=8G`,
about 105-110 s each at 900 steps. Every loss is nats per token (BPE);
`best val` is the lowest validation loss over every `metrics.jsonl` row
(`--eval-every 20 --log-every 20`, so every row is a fresh evaluation).

### The 300-step runs (kept, not the scored ones -- see "why this step budget")

| arm | seed | best val | at step | final val | final train | gap |
|---|---|---|---|---|---|---|
| whole rows | 1337 | 0.6320 | 300 | 0.6320 | 0.2776 | 0.3543 |
| whole rows | 7 | 0.6301 | 300 | 0.6301 | 0.2746 | 0.3554 |
| whole rows | 42 | 0.6320 | 300 | 0.6320 | 0.2809 | 0.3511 |
| windows | 1337 | 0.6584 | 300 | 0.6584 | 0.2056 | 0.4528 |
| windows | 7 | 0.6559 | 300 | 0.6559 | 0.2095 | 0.4464 |
| windows | 42 | 0.6779 | 300 | 0.6779 | 0.2103 | 0.4676 |
| FIM 0.5 | 1337 | 0.6609 | 300 | 0.6609 | 0.3522 | 0.3088 |
| FIM 0.5 | 7 | 0.6716 | 300 | 0.6716 | 0.3518 | 0.3198 |
| FIM 0.5 | 42 | 0.6642 | 300 | 0.6642 | 0.3517 | 0.3124 |

Every one of the nine best-val steps equals the final step: nothing had
turned over yet at 300 steps, on any arm, at any seed. Read only as an
early-training snapshot (not the scored comparison): whole rows already sit
below windows and FIM on held-out loss well before anything overfits, which
foreshadows the 900-step result below.

### The scored runs, at the revised 900-step budget

| arm | seed | best val | at step | best train | final val | final train | gap |
|---|---|---|---|---|---|---|---|
| whole rows | 1337 | 0.5905 | 440 | 0.0877 | 0.6415 | 0.0491 | 0.5924 |
| whole rows | 7 | 0.5887 | 320 | 0.1450 | 0.6371 | 0.0491 | 0.5880 |
| whole rows | 42 | 0.5924 | 340 | 0.1350 | 0.6463 | 0.0500 | 0.5962 |
| **whole rows, mean (range)** | | **0.5905 (0.0038)** | | | 0.6416 (0.0092) | 0.0494 (0.0010) | **0.5922 (0.0082)** |
| windows | 1337 | 0.6621 | 220 | 0.1676 | 0.7924 | 0.0332 | 0.7591 |
| windows | 7 | 0.6545 | 200 | 0.2014 | 0.7795 | 0.0330 | 0.7465 |
| windows | 42 | 0.6757 | 300 | 0.1007 | 0.7931 | 0.0325 | 0.7606 |
| **windows, mean (range)** | | **0.6641 (0.0213)** | | | 0.7883 (0.0137) | 0.0329 (0.0007) | **0.7554 (0.0142)** |
| FIM 0.5 | 1337 | 0.5718 | 440 | 0.1279 | 0.5974 | 0.0691 | 0.5282 |
| FIM 0.5 | 7 | 0.5920 | 520 | 0.1042 | 0.6077 | 0.0686 | 0.5391 |
| FIM 0.5 | 42 | 0.5768 | 480 | 0.1140 | 0.6003 | 0.0694 | 0.5309 |
| **FIM 0.5, mean (range)** | | **0.5802 (0.0202)** | | | 0.6018 (0.0103) | 0.0690 (0.0007) | **0.5327 (0.0108)** |

Noise (the larger of the two arms' seed ranges compared, matching the
denoising note's definition):

- whole rows vs. windows: best-val noise 0.0213, gap noise 0.0142.
- whole rows vs. FIM: best-val noise 0.0202, gap noise 0.0108.
- windows vs. FIM: best-val noise 0.0213, gap noise 0.0142.

### Applying the decision rule

**Rule 1 (windows reduce the gap) fails, in the wrong direction.** The
windows arm's mean gap (0.7554) is *higher* than whole rows' (0.5922) by
0.1632, itself many times the 0.0142 noise, and every windows seed's gap
(0.7465-0.7606) is above every whole-rows seed's (0.5880-0.5962). Windows do
not narrow the gap on this path; they widen it.

**Rule 2 (windows generalise better) fails for the same reason and does not
need rule 1 to fail first.** The windows arm's mean best val (0.6641) is
*worse* than whole rows' (0.5905) by 0.0736, against a noise of 0.0213, with
no overlap between the two arms' seeds (worst whole-rows seed 0.5924, best
windows seed 0.6545). By rule 4, this is windows *hurting*, not helping.

**Rule 3 (FIM adds beyond windows): passes, clearly.** FIM's mean best val
(0.5802) is below windows' (0.6641) by 0.0839 against a noise of 0.0213, no
overlap (worst FIM seed 0.5920, best windows seed 0.6545). FIM is
unambiguously better than windows here, exactly as the denoising note found.

**FIM against whole rows (not in the pre-registered rules, checked because
the numbers are close): no clear win.** FIM's mean best val (0.5802) is
below whole rows' (0.5905) by only 0.0103, *inside* the 0.0202 noise, and the
two arms' seed ranges overlap (FIM 0.5718-0.5920, whole rows 0.5887-0.5924).
FIM's gap is far narrower than whole rows' (0.5327 against 0.5922, a
difference of 0.0595 against a noise of 0.0108, no overlap) -- but by the
denoising note's own rule 2 language, applied here to FIM against whole
rows instead of windows against whole rows: a narrower gap with a best val
inside the noise is **"FIM slows memorisation but does not make the model
generalise better,"** which is a no.

**Rule 5: the finding does not hold on the r12 path, and the miss is not
narrow.** The denoising note's central claim -- that whole-document rows
anchored on the head drive most of the memorisation, and random windows
remove most of it -- predicted windows would land close to FIM's numbers.
Instead windows are the *worst* arm on every measure: worse best val than
whole rows, worse gap than whole rows, and both worse than FIM. Whole-document
rows, r12's current choice, are not the memorisation problem on this path;
if anything they are the best-generalising arm measured, tied with FIM
within noise.

### Why the prediction was wrong

The prediction (see above) explicitly named the mechanism at risk: a
pretrained core, unlike a random init, does not have to learn the shape of
text from these 302 documents, so head-keying might not dominate its
memorisation the way it dominated the from-scratch model's. The result is
consistent with a stronger version of that risk: windows do not merely fail
to help, they actively hurt, plausibly because the windows path draws its
512-token slices from the *joined* corpus (`Corpus.get_batch`, the same
windows machinery pretraining itself uses) rather than from documents with
their `Problem:`/`Signature:` structure intact. A window can start mid
document or straddle two documents; whole-document rows always hand the
model a complete, correctly-headed unit. A model that already knows how to
read source text and English (the pretrained core) may get more usable
signal per token from 270 complete, well-formed 150-token-average documents
than from 512-token slices that are frequently incomplete or structurally
broken -- the opposite of the from-scratch case, where the model had nothing
to key on *except* the head, and randomising the cut point was pure
regularisation. This is a plausible mechanism, not a re-measurement; it was
not tested directly (that would mean comparing windows cut only at document
boundaries against windows cut anywhere, which this note did not run).

### Recommendation for r12's row layout

**Keep `--doc-batches`.** It is not only unrefuted on the real path, it
measures as the best or tied-best arm on held-out loss. Switching to random
windows, which is what the denoising note's from-scratch result would have
recommended, would make r12's fine-tune worse by every measure here. FIM at
rate 0.5 on top of `--doc-batches` is not shown to generalise better than
plain whole-document rows beyond noise (best val ties, at 900 steps), but it
does cut the train/held-out gap substantially and is the only arm that
matches whole rows' held-out loss while training on a harder, denoised
objective; it is a reasonable candidate for a future arm judged by clean
answers on the held-out 232 (`internal/PRETRAIN-R12-2026-09-25.md`'s own
standard: "not loss... run the section-C fine-tune... and count tests
passed"), not a required change for r12 to train.

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
