# The general-English pilot, registered before the arms train (2026-09-29)

**Written 2026-09-29 10:00Z, before any arm trains.** The plan is
`internal/PRETRAIN-DAWNR-GENERAL.md`, sections 6 and 7.4 (written 2026-09-26 and 2026-09-27,
never run: the lab's GPUs were full and this card was busy with rounds whose answer the notes
already gave). The question is the one section 6 fixes: does an English pretraining layer under
the code change the core's own measures at all, before the full 1.86B-17.84B-token budget is
spent on it. `internal/RESEARCH-NEXT-2026-09-20.md` names the project's failure as the step
from an English problem to a formal specification; a core that has never read English is the
first suspect.

**Arms** (same architecture as the core: gpt, vocab 8,192, block 2,048, 12 layers, 12 heads,
768 embedding; the core's frozen tokenizer; single RTX 4080 under the GPU lock; every command
exactly as section 7.4 wrote it, `~/scratch/dawnr-english-pilot/run.sh`):

| arm | pretraining | tokens | steps (8 x 2,048 per step) |
|---|---|---:|---:|
| A | the current core, `best.pt` of the r12 sweep (code only, 48.8M tokens) | 0 more | none |
| B | stage 1: decontaminated FineWeb-Edu (`pilot-english.txt`, 1.17B tokens available), from random weights; stage 2: the code corpus continued from stage 1's checkpoint with the r12 sweep's recipe | 300,015,104 + 734,003,200 | 18,311 + 44,800 |
| C | the code corpus alone, from random weights, for B's total | 1,034,018,304 | 63,111 |

**How each arm is judged**, the way every pipeline arm is: the chat pipeline's mid stage on the
531-document r12 corpus from that arm's core (400 steps, 1e-4, tool rate 0.5, harness tokens,
seed 1337), then the registered dev evaluation (greedy, 800 tokens, grammar on, two calls,
best-verdict, 100 dev problems) with `spec_agrees`, plus the pipeline's own held-out loss on
the proved corpus's validation documents. One seed per arm in this pilot; more seeds only if
the direction is worth them.

**Calibration, measured 2026-09-29 10:16Z** (20 steps of arm B's stage 1 on the token shards,
`t/out/dawnr-english-pilot-2026-09-27/calibration/`): batch 8 x 2,048 with gradient
checkpointing and bf16 fits the card; **65,600 tokens/s at the optimizer step** (39,900
tokens/s over the whole 54-second run, evaluations and startup included). At that rate: stage 1
about 76 minutes, arm B's stage 2 about 3.1 hours, arm C about 4.4 hours, before evaluations.
The first calibration on the 3.4 GB text died in data loading (the text corpus becomes a
Python list of 1.17B ints on a 14 GB machine); the trainer now reads the uint16 shards
section 7.3 wrote (`data.TokenShards`, 5a6ce99e). The written-time above says 10:00Z; the
arms start after this line is committed.

**Predictions.**

1. **Arm B's held-out loss on the proved corpus's validation documents is below arm A's.** An
   English layer under the same code recipe should not make the code side worse, and the
   proved documents carry English heads. Falsified if B's loss is above A's.
2. **Arm B is well formed on more dev problems than arm A (51 at seed 1337).** Falsified at 51
   or fewer.
3. **Arm B passes all examples on more dev problems than both A (0) and C.** This is the
   claim the pilot exists to test: English, not merely more tokens. Falsified if B is at or
   below either.
4. **`spec_agrees` stays at 0 for every arm.** 300M tokens of English at 16% of the Chinchilla
   floor should move form and examples, not the specification step; that step needs the
   spec-signal levers (the drawn-verdicts run, then RL through the engine). Falsified if any
   arm reads 1 or more, which would be the best news of the day and would be reported as such.

Nothing here touches the held-out 232. Results and the calibration's measured throughput are
recorded below when they land; run directories under `t/out/dawnr-english-pilot-2026-09-27/`
and `~/scratch/dawnr-english-pilot/`.

## Amendment, 2026-09-29 15:45Z, before any arm is judged: arm B's stage 2 reran at the registered decay

Stage 2 as first launched ran at weight decay 0.1, not the sweep recipe's 0.8 this registration
names: `continue_from_checkpoint.py` had no decay flag and took `train.make_optimizer`'s
fine-tune default. At lr 1e-3 over 44,800 steps (15 passes over the 48.8M-token code corpus) it
showed the sweep control's signature (`internal/PRETRAIN-R12-2026-09-25.md`, results): validation
1.52 nats per token at step 8,000, a spike to 3.59 at 10,000, then 2.3 to 3.3 through step
28,000 with the fixed training windows the same, instability rather than memorisation. That run
is kept as `arm-b-stage2-code-wd0.1-diverged` and is not an arm. Stage 2 restarts from stage 1's
checkpoint with `--weight-decay 0.8` (the flag added for it) and `--eval-every 2000` (the default
50 spent 42% of the wall clock on validation; evaluation draws from its own generator, so the
cadence does not touch the training stream). The arms, the tokens, the judgement and the four
predictions above are unchanged; no arm has been evaluated. Two trainer defects found on the way
are fixed in the repository: a CUDA resume moved the generator state to the GPU and refused it
(74fc41e6), and the decay above.
