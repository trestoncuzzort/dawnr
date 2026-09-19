# Preregistration: latent and execution supervision, four cells, three seeds

Registered before any arm of this experiment was trained and before any scored
output existed. The design it implements is
[DESIGN-latent-execution-2026-09-19.md](DESIGN-latent-execution-2026-09-19.md);
this file fixes the identities, the schedule and the numbers that would
falsify the claims.

## Question

Does token-conditioned latent prediction (NextLat-style) combine with concrete
execution-state supervision to improve the owned core's *unaided* program
synthesis on held-out compositions? A combined gain and a positive interaction
are separate claims and are reported separately.

## The four cells

| arm | NextLat auxiliary loss | intermediate execution-token loss |
|---|---|---|
| baseline | off | off |
| latent | on | off |
| execution | off | on |
| combined | on | on |

Every arm reads the same examples in the same order within a seed, including
both synthesis and execution examples; the example order hash is written into
each arm's `run.json` and must agree across the four arms of a block.
Intermediate execution tokens are in every arm's input; only their loss mask
differs. Synthesis completions and final execution outputs are supervised in
every arm. Execution loss is normalized separately with weight 1.0, so a longer
trace cannot dilute the synthesis loss.

## Frozen inputs

Dataset `t/out/composition-2026-09-19-v2`, built by
`t/build_composition_dataset.py --inputs 17 --max-events 36`:

- `train.jsonl` `ca73a1b2872ec77c466ebcdca178d572b03a3d85ba7f0a254a84be0baf41a95e`
- `eval_synthesis.jsonl` `548e82f8b5f197b324bbfc747bcadb1e641e3663c84a570558c632f66e810368`
- `eval_execution.jsonl` `ad143718ec899ba14337f23bc2079427ae2078bfd1d24127ad7fab2a0422a356`
- `traces.jsonl` `df386b21d83ef0d3129c76205d9d5bbfa609c8743bd451005516284befffb106`

81 training tasks over 15 patterns (1094 execution and 81 synthesis examples);
102 held-out tasks over 17 patterns that appear in training under no parameter
assignment: 5 whole two-stage compositions (30 tasks) and 12 three-stage
programs longer than anything trained (72 tasks). Numerical extrapolation is a
separate stratum *within* those tasks: every held-out task is tested at 8
in-range inputs and 8 inputs of untrained magnitude (|x| ≥ 18), 1632 tests in
all. Every label is bounded concrete execution agreed by `interp` and by
`t/composition_reference.py`, which never sees the AST; every generated
postcondition is checked true at every generated input, which is not a proof.
10,800 deliberate corruptions of state values, AST locations and event
sequences were rejected during generation.

Initialization: the modern 4000-step checkpoints of
`t/out/source-pretraining-longer-2026-09-19`, `ckpt.pt` SHA-256 beginning
`c6fa9977` (1337), `5627ec4b` (7), `82b44108` (42). The four arms of a block
share one backbone byte for byte and reset optimizers identically. That study
measured this core as 5.9–7.4% *worse* than its GPT control at this budget
([FINDINGS-source-longer-2026-09-19.md](FINDINGS-source-longer-2026-09-19.md));
the design named this initialization before that result, the paired contrasts
here are unaffected by it, and no absolute number from this experiment is a
statement about the best available core.

Tokenizer: the frozen `source-tokenizer-2026-09-19-v2` byte-BPE carried by the
initialization checkpoints. `locallm/audit_example_masks.py` was run over the
whole training file at block size 512 before launch: 1175 examples encode, 0
exceed the context, every arm receives identical input IDs and identical answer
targets, 214,304 input tokens, 10,638 answer-supervised tokens and 78,649
tokens supervised only by the execution arms.

## Schedule and budget

1000 updates at batch 32 was the design's budget and it does not survive this
machine: the four cards are shared with another user, and a batch-32 arm peaked
at 12.86 GB and was killed by `torch.OutOfMemoryError` when that user's
processes grew during the first attempt, on a card that had measured 17 GiB
free seconds earlier. **Amended before any arm produced a scored output, and
recorded here rather than silently:** 4000 updates per arm at batch 8, which is
the same 32,000 examples per arm as the design's 32 × 1000, with warmup kept at
5% of the horizon (200 updates). Measured on the real dataset and
initialization: batch 32 peaks at 12.86 GB, batch 16 at 7.24 GB, batch 8 at
4.51 GB and 0.068 s per update, about four and a half minutes of training per
arm. Every arm uses the same amended setting, so no contrast in this experiment
is affected; the absolute scores are those of a smaller-batch schedule.

Context 512, AdamW at lr 3e-4 with cosine decay to lr/10, gradient clip 1.0,
dropout 0, bf16 autocast, `expandable_segments` allocation, one card per arm,
arms run sequentially. A card is chosen by measured free memory at the moment
an arm starts and must show at least 10 GiB free. Arm order inside each seed
block was randomized with seed 20260919 before launch and is:

- seed 1337: execution, combined, latent, baseline
- seed 7: baseline, combined, latent, execution
- seed 42: execution, latent, combined, baseline

An arm killed by memory pressure is resumed from its own saved optimizer, RNG
and step state, never restarted from another arm's state, and both attempts are
kept in the ledger.

## Response and scoring

Primary: one greedy program per held-out task, 200 new tokens, no retries, no
repair, no reranking, no search, cut after the first closing brace on its own
line. The prompt supplies the whole contract and the scorer reassembles the
frozen header with the candidate body, so no candidate can alter the contract,
the tests or the expected values; expected values come from the closed-form
oracle. Malformed, ill-formed, contract-altering, undefined, over-budget,
over-time and over-length answers are failures and are counted separately
(`t/score_synthesis.py`, 11 tests covering each outcome).

Secondary and descriptive only: per-stratum test pass rates, execution-token
losses, source loss, wall time, peak memory, supervised-token counts.

## Predictions, with what falsifies them

1. **Combined beats baseline by at least 5 percentage points of held-out tasks
   solved, with a positive paired difference in every one of the three seeds.**
   Any seed with a combined-minus-baseline difference below 5 points falsifies
   the threshold claim; any negative seed falsifies the weaker directional
   claim, which is reported separately.
2. **The interaction `combined − latent − execution + baseline` is positive in
   every seed.** A negative or zero interaction falsifies it, and is reported
   with the cell scores rather than replaced by the additive result.
3. Every arm completes 1000 updates with finite losses.

Additive improvement without synergy is a real outcome and is reported as one:
prediction 1 can hold while prediction 2 fails. All twelve arms are reported,
failed attempts are retained, no arm is dropped for a bad score, and no
checkpoint or learning rate is selected using held-out task scores.

## What this experiment cannot show

It scores generated compositional tasks with an interpreter. It is not a
seven-verifier result, not a twin refutation, not a specification-agreement
result and not a Phi comparison; a gain here must still survive the project's
original acceptance evaluation before it is an improvement in this project's
terms. Training-seed and held-out family are the replication levels: 102 tasks
over 17 patterns are not 102 independent families.
