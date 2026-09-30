# Stage sweep, 2026-09-30: what the shelf already holds, what the outside adds, and the queue

Written while r12's core was between its two stages (stage 1 complete, English validation 2.180;
stage 2 running). The operator asked for everything we need at this stage or can use, found the
fetch-before-fix way (AGENTS rule 5): this repository's own record first, the web second, nothing
counted as prior art unless it was fetched and read. Two read-only sweeps covered the shelf
(`internal/`, the PREDICT and FINDINGS files, the `DAWNR-*.md` plans, `t/RUN-NEXT-*`, the mirrored
library, the skills, the receipts) and the code's current facts; 35 pages were then fetched. The
receipts are listed at the end.

## The headline

The sweep did not find a new idea. It found that **the shelf holds sixteen plans that were written
and never run**, that the largest of them (the teacher and expert iteration) has been waiting for a
30 GB card since 2026-09-26, and that **the free-compute routes that would feed them had never been
looked up**: the record said only "or a grant". The outside literature, read against the list,
says the same thing the unrun plans say: the proved corpus is one to two orders too small, and the
way up is candidates from a stronger model filtered by the provers and by specification checks.

## 1. Written and never run

| plan | where | why it stopped | what unblocks it |
|---|---|---|---|
| Teacher generation and expert iteration: 442 specification prompts and 368 problem ids staged, scoring and seven-prover regrading validated end to end, zero teacher samples | `t/EXPERT-ITERATION-2026-09-26.md:11-22,144-147,203-233`; `t/rl_teacher_expert_iter.py` | the 27B teacher never fit beside other users on the shared cards | any 30 GB card: one rented H100 within the monthly free credit, or an academic allocation (section 5) |
| k specifications per problem, kept when `spec_check` agrees with the reference (lever 1) | `internal/RESEARCH-NEXT-2026-09-20.md:59-63`; receipt 94d9718666d3 (adopt, k about 10) | needs the teacher | the row above |
| Specification documents in the corpus (lever 2: problem to `ensures`) | `corpus --spec-docs` is built (`t/RUN-NEXT-locallm-r12.md:260`); the registered r12 corpus has 0 `Spec:` lines | left out of the r12 registration | the next corpus registration |
| Relabel rows: 118 programs for 40 problems | `t/RELABEL-2026-09-25.md`; left out at `t/RUN-NEXT-locallm-r12.md:293-297` | same | same |
| Sampling with the verifier as the filter | `t/RUN-NEXT-locallm-r12.md:151-161` (a 2-id smoke only) | never scheduled | a GPU slot after r12's round |
| Hint-stripped twins (about 800 ready; lever 4) | `t/TWIN-HINTS-2026-09-25.md:122-160` | "Not run" | lab CPU (a 2,506-cell grade) |
| Examples-in-prompt arm | `internal/RESEARCH-NEXT-2026-09-20.md:110-157`; "corpus built, never trained" (`internal/HANDOFF-2026-09-20-antigravity.md:117`) | superseded in part by the chat pipeline, which shows examples and a tool | decide: run or retire |
| Preference training on mined negatives (lever 3) | `t/NEGATIVES-2026-09-25.md:85-118,216-247` | 3 usable pairs; the trainer is built and off until 30 pairs over 15 problems | more disagreeing answers on training problems (the teacher supplies them) |
| Dense reward for RL (fraction of drawn inputs matched) | registered as the consequence of `locallm/PREDICT-2026-09-29-dawnr-drawn-verdicts.md:85-93`; absent from `t/rl_reward.py` | not built | build before RL restarts |
| RL restart with a difficulty band | `t/RL-DESIGN-2026-09-26.md:369-402` | 2 of 308 problems outside the corpus pass (0.6%); the bar is about 10% | distillation first, in the design's own order |
| Unlifted sources: Dafny standard library (MIT, low effort), Ironclad, verified-storage, EverParse/HACL*, Compfiles, F* algorithms | `~/resources/sweep/SYNTHESIS.md:337`; `~/resources/sweep/verified.md:104-127`; `~/resources/VERIFIED-CORPORA.md:57-79` | not scheduled | lab CPU |
| The 312M core on 15.6B tokens | `t/PREDICT-2026-09-30-dawnr-r12-core.md:14-41` | about $150, over the free limit | an allocation (section 5) |
| torch.compile measurement | `~/resources/LOCALLM-USES.md:446-474` ("no compile measurement exists at locallm sizes") | never run | ten minutes of an idle card |
| Decay-phase mixing arm | `internal/PRETRAIN-R12-2026-09-25.md:226-287` | "Not run" | with the next pretraining registration |
| Verdict-cache bar (grade twice, then without the cache) | `internal/OPTIMIZATION-SCAN-2026-09-20.md:73-91` | never run | lab CPU |
| Token shards for the code corpus ("pretraining input must be token shards, never text") | the lesson is in the 2026-09-29 overnight log; English has shards (`locallm/token_shards.py`), code has none | not built | section 4 |

`README.md` said expert iteration was "running with a local teacher model". It was staged and has
not run; the row is corrected with this file.

## 2. Run, and negative (do not rerun)

Drawn verdicts as training data (0 of 600, `locallm/PREDICT-2026-09-29-dawnr-drawn-verdicts.md`);
the chat pipeline on the held-out set (2/0/5 raw, 0 after the specification check,
`t/PREDICT-2026-09-29-dawnr-chat-heldout.md`); English before code (0 in all three arms,
`t/PREDICT-2026-09-29-dawnr-english-pilot.md`); repair conversations (+1.2 of 133,
`DAWNR-PIPELINE.md:343-364`); the composition curriculum (0/2/0 of 323, answers on collapsible
tasks, `locallm/FINDINGS-factorial-2026-09-19.md`); plain preference pairs on twins (tests 5 to 3);
preference pairs at the proof gate (27 to 33%, count unchanged); constrained decoding (1.23x); a
cleaner pool alone, a bigger model alone, pretraining alone (`internal/HANDOFF-2026-09-19.md:279-289`);
the "modern" architecture at untuned lr (6 to 7% worse at 4,000 updates and 1.9x slower,
`locallm/FINDINGS-source-longer-2026-09-19.md:35`); weight decay 0.1 at lr 6e-4 or above (three
divergences). Datasets rejected for contamination one hop from the held-out set: AutoVerus and
Verus-Bench, SAFE's data, AlphaVerus, VeriContest, CodeSpecBench, VeriEquivBench, MBPP-DFY
(`~/resources/VERIFIED-CORPORA.md:87-102`). Vericoding (Dafny, Verus, Lean) is already lifted.

## 3. What the fetched work adds

| source | what it reports | what it means here |
|---|---|---|
| SAFE, arXiv:2410.15756 | 45,395 Rust functions to 19,017 specifications to 9,706 verified proofs and 10,486 self-debugging pairs; accuracy 32.4, 42.5, 43.2% over three rounds; specifications kept at 80% correctness on tests and 60% of mutated tests rejected; self-debugging 59.7 to 70.5% at 100 samples | our 531 documents are one to two orders short; the loop is our unrun rows 1 and 2; its two thresholds are the comparison point for `spec_check` |
| AlphaVerus, arXiv:2412.06176 | translation from a richer language, tree search on verifier feedback, three filters; an exploit model writes a trivial program and a specification it satisfies is discarded; "without filtering ... the model learns to exploit verification" | add the exploit check beside `spec_check` and the twins when row 2 runs |
| DeepSeek-Prover, arXiv:2405.14333 | 8M synthetic statements with proofs; 46.3% against 23.0% | scale with filtering is the lever, as `RESEARCH-NEXT` argued |
| STP, arXiv:2502.00212; Polu et al., arXiv:2202.01344 | expert iteration plateaus on sparse reward; training on statements "barely provable" doubles the proved share (28.5% against 13.2%); a spread of difficulties gives a curriculum | RL's difficulty band needs a supply of easier problems near the frontier; the selection rule is usable, the scale is not |
| Teaching Arithmetic to Small Transformers, arXiv:2307.03381; TinyStories, arXiv:2305.07759 | for small models trained from scratch, the data format (worked intermediate steps) and a distribution matched to capacity decide learning against memorising | bears on the specification documents' format (row 3) |
| LintSeq, arXiv:2410.02749 | synthetic edit sequences help small code models | supports the pipeline's "repairs as edits" stage |
| nl2postcond, arXiv:2310.01831; Clover, arXiv:2310.17807 | a specification is judged by correctness on the reference and by discriminating mutants; consistency across description, specification and code | the same two scores SAFE thresholds; ours is the agreement check on drawn inputs |
| Vericoding, arXiv:2509.22908 | 12,504 specifications, MIT | already lifted; nothing new |
| nanochat `gpt.py`; modded-nanogpt README; Muon is Scalable, arXiv:2502.16982; nanoGPT README | rotary positions, RMSNorm, QK norm, ReLU squared, untied embeddings, logit cap; Muon on block matrices (about 1.5x to 2x the efficiency of AdamW); the speedrun's target in about 330M tokens against 10B; torch.compile 250 to 135 ms per iteration; uint16 memmap token files | section 4; recipe changes only in a new registration |

The difference from every one of these: they fine-tune pretrained models of 33B to 70B parameters.
Ours is 93M from random weights, so a teacher supplies candidates and the provers decide; the
capability has to come from the corpus.

## 4. The code today, and the speed it leaves on the table

- **Architecture and optimizer.** `gpt` = learned positions, LayerNorm, GELU, biases, tied
  embeddings, fused attention (`locallm/model.py:123-127,144-153,173,199-208`); AdamW, fused, betas
  (0.9, 0.95), decay on matrices only (`locallm/train.py:83-135`); warmup then cosine to a tenth
  (`train.py:190-196`). No QK-norm, no Muon, no torch.compile anywhere in the tree.
- **Continuation startup.** A `--data` text is read whole, scanned by the held-out gate, split and
  encoded on every launch (`locallm/data.py:630-660`; `locallm/continue_from_checkpoint.py:570`).
  For the 153 MB code corpus that is about 24 minutes and about 22 GB of working set under an 8 GiB
  cap, the card idle throughout. `cached_encode` (`data.py:559-602`) would make the encode 1.6 s
  warm, but the default `--data` path does not call it and the launchers do not set
  `LOCALLM_TOKEN_CACHE`. `train_distributed.py` reads memmap shards (`--data-tokens`); the
  continuation has no such flag and the only shard writer is English-specific.
- **Evaluation in the continuation** runs in fp32 outside autocast without TF32
  (`continue_from_checkpoint.py:772-781`); at the default cadence it was 42% of wall clock.
- **Held-out generation** is one row at a time, the key-value cache off on CUDA by default, fp32,
  and the stop rule decodes the whole text at every token (`t/loop_locallm.py:855,955`;
  `locallm/checkpoint.py:89-118`). `sample_many` exists (`model.py:360-431`).
- **Where one r12 seed's hour goes** (measured on seed 1 of the round on the new core, from
  `t/out/r12-run/run.log`, 2026-09-30 19:18Z on): the fine-tune itself is 45 seconds (300 steps);
  the dev-chosen stopping step is 52 minutes (seven kept checkpoints x 100 dev problems, greedy,
  one row at a time, about 4.5 s a problem); the held-out generation is about 23 minutes (232
  problems, about 6 s each); then the lab grades. About 75 GPU-minutes of every seed is batch-1
  greedy decoding of a 93M model, which is per-token overhead, not arithmetic: the cache finding
  (`locallm/FINDINGS-kv-cache-2026-09-19.md`) already showed the key-value cache does not shorten
  it at these prefixes. The lever is batching the dev problems (and the held-out ones) through
  `sample_many`-style decoding, eight or sixteen rows at a time, behind an identity test (batched
  greedy output equal to the one-row output on every dev problem of one checkpoint) and a
  registered speed prediction. Not touched while the round runs from the working tree.
- **Activation checkpointing** is inherited from the init checkpoint by the continuation. A core
  trained on an 80 GB card with it off ran out of memory at batch 16 x 2048 on the 16 GB card
  (2026-09-30 05:55Z). Fixed the same morning: `--gradient-checkpointing` (commit eee3c9c6, the
  loss and every gradient tested equal).
- **Launchers** under `~/scratch` marked a lane done after a failed stage; the r12 core launcher
  now stops on the first failure.
- **Grading.** The verdict cache keys on source, kernel, version, budget and adapter
  (`t/cache.py:31-52`); timeouts and tool errors are never cached, UNPROVED is, so queue grades run
  `--no-cache`. Cells run three real and three twin runs concurrently.
- **Generators.** The fuzz families (`t/fuzz_lower.py`, `t/truth_fuzz.py`, `t/metamorphic.py`) emit
  tasks with verdicts known by construction and no English or tests; they test the lowerings and
  are not training data. The one generated training set was the composition curriculum (negative).

## 5. Free compute

The free-limit rule (2026-09-29) makes this the largest speed lever. Found, with the institution
left out of this public file (the URLs are on receipt 9fddcb991f51):

| route | what it gives | who acts |
|---|---|---|
| the rented platform's monthly credit | $30 again each month; one H100-hour is about $4; the staged teacher generation is a few dollars | nobody |
| the same platform's academic program | up to $10k of credits over a year, by application | the operator |
| the university's cluster | 10 GPUs including 80 GB cards, a 24-hour GPU queue | a faculty sponsor who holds an account |
| the state's supercomputer authority | no cost to enrolled students of the state's public universities | the operator, with the advisor's details on the form |
| NSF ACCESS, Explore | 400,000 credits on an abstract; "Undergraduate students are not eligible to be PIs" | a faculty PI, the operator as a member |
| NAIRR pilot | 12-month allocation, monthly decisions, a 3-page proposal | faculty, or a graduate student with a letter |
| Kaggle notebooks | about 30 GPU-hours a week on T4 or P100 | the operator |

One message to the advisor covers four of the rows. Trials at the large clouds exclude GPUs, as
our own attempts found.

## 6. The desktop card

Four drops off the PCIe bus (Xid 79, then Xid 154 "Node Reboot Required"), each within about 40
minutes of a fresh training start; the power cap and the runtime power-management changes did not
stop the third and fourth. The driver is the open kernel module 595 on kernel 7.0, the board an
X670E. Fetched: the vendor's Xid catalog (79 is a PCIe link failure, typically hardware, sometimes
the driver); a report of the same GPU family on the same chipset stable only with the slot forced
to Gen 3, called "a well known issue"; a thread on the same pairing where disabling ASPM and
swapping drivers did not help; a thread where Xid 79 began with kernel 7.0 and the open 595 module.
Nothing confirms a software fix. Test order, cheapest first: the slot at Gen 3 in the firmware
setup (training does not need link bandwidth); the proprietary module or the previous driver
branch; reseat the card and its power connector; the supply. The first three were named here on
2026-09-27 and never tried.

## 7. The queue

Each item is its own registration or receipt; none changes the run in flight.

**Added the same day, after the core was judged** (well formed 45 of 100, `spec_agrees` 0:
`t/PREDICT-2026-09-30-dawnr-r12-core.md`) **and its base rate sampled** (6,400 draws, no correct
answer: `t/PREDICT-2026-09-30-dawnr-base-rate.md`): item 0 is now the specification check itself.
It calls a string problem's reference with a list of integers, and on 3 of the 232 held-out
problems the reference then computes another function (`t/audit_reference_types.py`, `LIMITS.md`).
Repair it (type-faithful reference calls, EvalPlus's rule) and re-score before any reward,
selector or new held-out number rests on it. The base rate confirms the rest of this queue: RL and
self-sampling have nothing to work with on this core, so the teacher items come first.

1. **The operator, any time:** the advisor message and the academic-credit application; the
   firmware slot setting at the next reboot.
2. **After the r12 core is judged, before r12's round:** token shards for the code corpus and
   `--data-tokens` in the continuation, with a token-identity test; a profile of where one r12
   seed's hour goes before any change to generation. The profile is in section 4 now (2026-09-30
   20:40Z): 75 of a seed's minutes are batch-1 greedy decoding; batched decoding behind an
   identity test is the registration to write once the round is off the working tree.
3. **With the next month's free credit:** the staged teacher generation on one rented H100 (row 1),
   then k specifications per problem through `spec_check` plus the exploit check (row 2), then a
   corpus registration that includes the specification documents and the relabel rows (rows 3, 4).
4. **When an allocation lands:** the 312M core, with QK-norm and Muon as one registered arm against
   the weight-decay-0.8 baseline; RL when the base rate clears its bar, with the dense reward and
   the difficulty band.
5. **Lab CPU, any time it is free:** the hint-stripped twins grade; the Dafny standard library
   lift; the verdict-cache bar. Checked 2026-09-30 20:45Z: the standard library is not a lab job
   yet. Its files are modules of generic functions, predicates and lemmas
   (`Std/Collections/Seq.dfy`: 18 opaque functions, 6 ghost predicates, lemmas, every one inside
   `module Std.Collections.Seq` and most over a type parameter); the lifter lifts a *method with
   an ensures* and skips module bodies by design (`t/LIFTER-DESIGN.md` section 3: `module` is a
   census gap, and the type grammar has no type parameters). Lifting it means a lifter extension
   (modules, functions as tasks, monomorphising `T` to `int`), a design registration, not a run.
   The twins grade ran 2026-09-30 20:00Z on; the cache bar is queued behind it.

## 8. Not taken, and why

- Another core-side experiment before the data moves: the registration's own reading is that if
  this core reads 0 the corpus is the lever.
- The speedrun's structure-imposing tricks: its authors say they may not scale.
- A conjecturer model (STP): 51.3B generated tokens is far past the free limit.
- The rejected datasets: contamination one hop from the held-out set.
- Any recipe change to the run in flight.

## Receipts

9fddcb991f51 (free compute), e75435991395 (Xid 79), ee391d924aec (verified-data synthesis and
specification filters), bea53fe22289 (sparse verifier reward), 8fc282443bc0 (training efficiency),
ad5c3171aba9 (activation checkpointing in the continuation).
