# r12's core: the 312M model pretrained on 15.6B tokens of English, then code, registered before the run (2026-09-30)

**Written 2026-09-29 22:10Z, before any training.** The general-English pilot
(`t/PREDICT-2026-09-29-dawnr-english-pilot.md`, outcome) found that English before code beats code
alone at matched tokens and that every core so far leaves the specification column at zero; the plan's
own budget (`internal/PRETRAIN-DAWNR-GENERAL.md` section 2) puts the core's range at 1.9 to 17.8B
tokens and the 312M model's Chinchilla floor at 6.2B. The operator's decision on 2026-09-29: r12 is
the big run, more cards and a bigger batch. This registers it. Receipts: f3d8ea9162ef (the recipe:
nanoGPT's config/train_gpt2.py and GPT-3, arXiv:2005.14165, for the 0.5M-token-step regime),
345447b88143 (the shard reader), 821a29fb4e76 (the rented-GPU launcher).

## The run

**Stage 1, English, from random weights.** `locallm/train_distributed.py` under torchrun on eight
rented H100s (`locallm/cloud_train.py`, Modal volume `dawnr-data`), model `core-large`
(24 layers, 16 heads, 1,024 wide, block 2,048, vocabulary 8,192 with the sweep's tokenizer;
311,224,320 parameters, `locallm/FINDINGS-capacity-2026-09-19.md`). Data: the 14 FineWeb-Edu
sample-10BT files tokenized and decontaminated on 2026-09-29 (section 7.3 tool, widened protected
set of 7.1), `english/file-0*/english-*.bin` in file order, **15.55B tokens**; TinyStories is left
out of this run on purpose (model-written text; the core trains on human-written web text and our
own code). The validation split is the last 1,000,000 tokens of the used range (inside file 013).
Recipe: 8 ranks x micro-batch 16 x block 2,048 x gradient accumulation 2 = **524,288 tokens per
step**, one pass = **29,660 steps**; AdamW lr 6e-4, warmup 2,000 steps, cosine to 6e-5 over the
run, weight decay 0.1 (single pass: no memorisation to fight), gradient clip 1.0, bf16, no gradient
checkpointing, dropout 0, seed 1337, deterministic; checkpoint every 500 steps, validation every
500 steps over 20 batches; `best.pt` is the lowest-validation state. Run directory
`runs/r12-core-english` on the volume.

**Stage 2, code, continued from stage 1's checkpoint.** `locallm/continue_from_checkpoint.py` on
one rented H100 over the code corpus (`t/out/source-corpus-2026-09-19-v2/train.txt`, 48.8M tokens,
split `split-v5.json`), in the sweep's regime: weight decay 0.8, lr 1e-3, warmup 560, batch 16 x
2,048, dropout 0, seed 1337, deterministic, **15,000 steps (about 10 passes, where the sweep saw its
best validation)**, validation every 500 steps, `--keep-every 1000`; **the core is the kept copy with
the lowest validation loss**, never the final state (the pilot's lesson). Run directory
`runs/r12-core-code`.

**Judgement, on the desktop after `modal volume get`.** (a) The pipeline's judgement, as for every
pilot arm: `dawnr_pipeline` mid stage on the 531-document r12 corpus at seed 1337, the registered
dev evaluation with `spec_agrees`, the base held-out loss on the 46 proved validation documents.
(b) r12's fine-tune round on this core, exactly as `t/PREDICT-r12.md` registers it, with the held-out
232 exported and graded through `t/grade_lab.sh heldout` and scored on the clean 200, spec checked.

## Predictions

1. **Stage 1's English validation loss ends below 2.10 nats per token** (the pilot's 93M core at
   300M tokens: 2.525). Falsified at or above 2.10.
2. **Stage 2's best validation loss on the code split is below 1.15** (the pilot's arm B, the same
   split and trainer, ended at 1.214 after 15 passes). Falsified at or above 1.15.
3. **Well formed on the 100 dev problems is at least 50** (A: 49, B: 29, C: 23). Falsified below 50.
4. **`spec_agrees` is at least 1 on the 100 dev problems**: for the first time a core yields an
   answer that agrees with the problem's own solution on drawn inputs. This is the prediction the run
   exists for, held with about one chance in three. Falsified at 0; then the base rate is measured by
   sampling (64 draws per problem through the checker) before any reward is built, and the proved
   corpus, not the core, becomes the next lever.
5. **The base held-out loss on the proved validation documents is below 3.60** (A 3.7154, B 3.6425,
   C 3.6686). Falsified at or above 3.60.
6. **r12's round on this core scores at least 1 clean, spec checked, on the 200 for at least one
   seed** (every arm so far: 0). Held with low confidence; falsified at 0 on every seed.

## Cost and time, from the calibration of 2026-09-29

Thirty steps of the stage-1 recipe on Modal H100:8 (app ap-ol83QRbT0Rs1vPRvDaiecg, run directory
`runs/calib-312m-h100x8`, the first 2B English tokens): **0.478 s per optimizer step of 524,288
tokens, 1.09 to 1.10 million tokens per second** (about 26% of the eight cards' bf16 peak; the
pilot's 93M core on one H100 ran 235k tokens/s at 16k tokens per step). At that rate:

| stage | steps | time | price |
|---|---:|---:|---:|
| 1, English, H100:8 at $31.60/h | 29,660 | about 4.0 h of steps, 4.3 h with validation and checkpoints | about $135 |
| 2, code continuation, one H100 at $3.95/h | 15,000 | about 2.5 h (312M at 16 x 2,048 per step) | about $10 |
| calibrations so far (93M x1, 312M x8) | | | about $3 |

Total about $150, of which the month's remaining free credit covers about $20; the rest is billed
to the card on file. The eight-GPU container took about ten minutes to be scheduled. Launch, once
the operator has said so:

    DAWNR_GPU=H100:8 DAWNR_MEMORY_MB=65536 modal run --detach locallm/cloud_train.py --nproc 8 \
      --data "english/file-0*/english-*.bin" --steps 29660 --save-every 500 --out runs/r12-core-english \
      --recipe "--tokenizer-file /data/tokenizer.json --architecture gpt --preset core-large --vocab-size 8192 \
        --block-size 2048 --n-layer 24 --n-head 16 --n-embd 1024 --no-gradient-checkpointing --batch-size 16 \
        --grad-accum 2 --dropout 0.0 --lr 0.0006 --weight-decay 0.1 --warmup-steps 2000 --seed 1337 \
        --deterministic --bf16 --data-tokens-val 1000000 --eval-every 500 --eval-iters 20 --log-every 10"

Stage 2 follows from stage 1's `ckpt.pt` with `continue_from_checkpoint.py` on one H100 (the
launcher gains a `--stage2` path for it before then), and both run directories come back with
`modal volume get` for the judgement.

Nothing here touches the held-out 232 or the dev 100: the English set was decontaminated against
them (7.1) and the code corpus is the one every earlier arm trained on. One look per decision: the
numbers land in `locallm/dawnr-r12-core-results-2026-09-30.json` and this file's outcome section.

## Amendment, 2026-09-29 21:50Z, before any training: the budget is the free limit

The operator set the budget to the free compute available (Modal's month credit, about $20 left of
$30, and the desktop). The run above does not fit ($150), so it is re-registered at the size the
free compute allows, with everything downstream unchanged (the 93M `core-medium` is what every
pipeline stage, r12's recipe and the held-out export already take):

**Stage 1, English, from random weights, on the desktop (free).** `core-medium` (12 layers, 12
heads, 768 wide, block 2,048, vocabulary 8,192, 92,920,320 parameters), the first **3.7B tokens**
of the same FineWeb-Edu set in file order (files 000 to 003, twice the plan's Chinchilla point for
this size, `--data-tokens-limit 3700000000`), validation the last 1,000,000 tokens of the used range.
Recipe: micro-batch 8 x block 2,048 x gradient accumulation 4 = **65,536 tokens per step** (the
sweep's batch), **56,457 steps** (one pass), lr 6e-4 with warmup 2,000 and cosine to a tenth, weight
decay 0.1, gradient clip 1.0, bf16, gradient checkpointing (the 16 GB card), dropout 0, seed 1337,
deterministic; checkpoint and validation every 500 steps. About 17 hours at the pilot's measured
rate (65k tokens/s). Run directory `t/out/dawnr-r12-core-2026-09-30/stage1-english`.

**Stage 2, code, on the desktop**, as registered above but at micro-batch 16 x 2,048 for the 93M
model (15,000 steps, wd 0.8, lr 1e-3, `--keep-every 1000`, the kept copy with the lowest validation
loss is the core). Run directory `t/out/dawnr-r12-core-2026-09-30/stage2-code`.

**Predictions**, restated for the size: 1. stage 1's English validation loss ends **below 2.30**
(the pilot's 300M-token stage: 2.525); 2. stage 2's best code validation loss is **below 1.20**
(arm B: 1.214); 3 to 6 unchanged (well formed at least 50; `spec_agrees` at least 1, the reason
for the run, held with about one chance in four at this size; held-out loss below 3.60; r12's round
at least 1 clean, spec checked, on some seed). The 312M run stays registered above for the day a
free allocation covers it (the Google Cloud credit once its GPU quota is granted, or a grant).

**Addendum, 2026-09-30 00:25Z, stage 1 still training:** at the operator's word, the same stage 1
also runs on one rented H100 within Modal's remaining month credit (micro-batch 32 with no
gradient accumulation and no gradient checkpointing, the same 65,536 tokens per step, data, steps,
optimizer and seed; a hard cap of 4.5 hours on the container bounds the spend at about $18). The
first of the two stage-1 runs to complete is the one continued into stage 2 and judged; the other
is kept as a replicate and not judged. The predictions are unchanged.

**Amendment, 2026-09-30 01:50Z, before the relaunch: the single-pass recipe diverged; stage 1 reruns at the sweep's recipe.** Both stage-1 runs at weight decay 0.1 and lr 6e-4 (the published single-epoch values, receipt f3d8ea9162ef) diverged past step 10,000 at lr about 5.7e-4: validation fell to 2.444 (desktop, step 10,000) and 2.373 (rented H100, step 15,500), then recurrent loss spikes (desktop 2.97 at 11,000 and 2.62 at 13,500; H100 4.87 at 19,000 and 5.40 at 25,500, training loss back to 3 to 7). This is the third divergence of this model at weight decay 0.1 (the sweep's control, the pilot's first stage 2, now this), against a stable record at weight decay 0.8 with lr 1e-3 at the same batch (the sweep, 11,200 steps) and on English (the pilot's stage 1, 18,311 steps); Wortsman et al. (arXiv:2309.14322) place these small-model instabilities at high learning rate and name weight decay among the interventions that tame them (receipt 8a65930c39ea). Stage 1 therefore reruns with **weight decay 0.8 and lr 1e-3**, warmup 2,000 and cosine to a tenth, everything else unchanged (data, 65,536 tokens per step, 56,457 steps, seed), again on one rented H100 within the free credit (about $11, a 3-hour cap) with the desktop as the replicate; the diverged runs are kept as `stage1-english-wd0.1-diverged` (desktop) and `runs/r12-core-english` (volume) and are not arms. Predictions unchanged; prediction 1 (English validation below 2.30) now carries the note that the diverged runs reached 2.37 to 2.44 before spiking.

**Amendment, 2026-09-30 06:41Z, before stage 2 trains a step: stage 1 is complete; stage 2 on the desktop runs with activation checkpointing on.** Stage 1 (weight decay 0.8, lr 1e-3) finished its 56,457 steps on the rented H100 without a spike: English validation 2.1797 nats per token at the end, 2.1795 at its best (step 56,000). Prediction 1 (below 2.30) holds at the stage-1 level. The run was landed on the desktop at 05:18Z. The first start of stage 2 there failed before any step: the continuation inherits the init checkpoint's configuration, the H100 run had activation checkpointing off, and batch 16 x 2048 needed more than the 16 GB card has (CUDA out of memory at 14.98 GiB, 05:55Z; the launcher then marked the lane done with no judgement, which is corrected: a failed stage now stops it). Stage 2 reruns from the same stage-1 checkpoint with `--gradient-checkpointing`: each block's activations are recomputed in the backward pass (torch.utils.checkpoint, docs.pytorch.org/docs/stable/checkpoint.html; Chen et al., arXiv:1604.06174), which changes memory and step time and not the gradients (`locallm/test_continue_gradient_checkpointing.py` checks the loss and every gradient for equality). Nothing in the recipe changes: batch 16 x 2048, lr 1e-3, weight decay 0.8, warmup 560, 15,000 steps, seed 1337, a kept copy every 1,000 steps, the core = the kept copy with the lowest validation loss. The failed attempt is kept as `stage2-code-oom-batch16` and is not an arm. Predictions unchanged.
