# locallm: the technical record

The version of [the README's achievements section](../README.md) with the
settings, the identities and the caveats. Every row of this page is a number a
script in this repository produced; where a measurement has a confound or a
narrow scope, it says so in the same paragraph rather than in a footnote.

Nothing here has been reviewed by a second party. A review of the 2026-09-19
work was requested from another agent and did not arrive; the instruments
behind the newer numbers carry their own tests and nothing more.

## 1. Well-formedness from random initialization

**209 of 232** held-out answers parse and pass `check_wf` (`locallm-r4`, 10.9M
parameters, character tokenizer, trained from random weights on a 77 KB
corpus); 198 of 232 for `locallm-r5`. The matched Phi-4-mini row is 12 of 232
and the prompted Qwen3.8-27B-FP8 row is 116.

Scored by [`t/score_heldout.py`](../t/score_heldout.py) over
`t/out/loop/split-v3.json`'s 232 held-out problems; full table
[`t/out/score-r6.md`](../t/out/score-r6.md).

**Caveats.** Phi has never seen t, so its 12 measures unfamiliarity as much as
capability; that applies equally to every prompted row and the README says so.
Well-formedness is a parse and a type check, not correctness: 204 of those 209
answers are *proven but wrong*, meaning all seven verifiers agreed the program
meets the specification the model wrote, and the problem's own tests still
failed.

## 2. Conversion from correct to proved

Every locallm answer that passed its problem's tests also verified in all seven
systems with its twin refuted: **2 of 2** (r4, r5), **1 of 1** (r7), **2 of 2**
(r7b greedy, r8) and **3 of 3** (r7b headed2, the arm that ties Phi). The
comparable rates are Phi 3 of 6, the untrained 1.5B 3 of 13, the prompted 27B
12 of 81, DeepSeek-Prover-V2-7B 6 of 10. Every rate here is a column of
[`../t/out/score-r8.md`](../t/out/score-r8.md).

**Caveats.** The denominators are 1 and 2. This is not evidence of a high
conversion rate; it is the absence of any observed failure to convert, on a
sample far too small to distinguish 100% from 60%. It is reported because the
failures, when they come, will be informative.

## 3. Deterministic resume

`locallm/train_factorial.py` saves wrapper weights, optimizer state, step and
RNG state, and re-enters the same epoch at the same offset on resume.
`locallm/test_train_factorial.py::test_resume_reproduces_an_uninterrupted_run`
asserts every tensor of a four-update run equals the corresponding tensor of a
two-update run resumed for two more, and the accounting agrees.

**Caveats.** Verified on CPU with dropout 0. It has **not** been verified on
CUDA, where non-deterministic kernels can break bitwise equality, and no claim
is made there. The four-GPU pretraining path
([`DISTRIBUTED-2026-09-19.md`](DISTRIBUTED-2026-09-19.md)) has its own
deterministic-resume work, measured separately.

## 4. Trainable size on this hardware

`locallm/measure_capacity.py`, five real optimizer steps per size on random
token data, GPT architecture, gradient checkpointing on, block 512, vocabulary
8,192, bf16, one RTX 6000 Ada with **16.4 GiB free** of 47.4 GiB because
another user held the rest:

| parameters | batch | result | peak reserved | tokens/s |
|---:|---:|---|---:|---:|
| 91,740,672 | 2 | trains | 1,664 MiB | 23,539 |
| 210,454,528 | 2 | trains | 3,444 MiB | 10,991 |
| 311,224,320 | 2 | trains | 5,026 MiB | 7,677 |
| 483,402,240 | 2 | trains | 7,728 MiB | 4,697 |
| **874,672,000** | 2 | **trains** | 13,790 MiB | 2,693 |
| 1,629,294,592 | 2 | out of memory | — | — |

**Caveats.** This establishes that optimizer steps of that size fit and how
fast they run. It does **not** establish that size is why earlier work stalled,
and no large model has been trained to a score. The out-of-memory boundary was
measured against another user's fluctuating allocation, so it is a floor on the
machine's capacity at that moment. The ~2.5B figure for a free card in
[`FINDINGS-capacity-2026-09-19.md`](FINDINGS-capacity-2026-09-19.md) is
arithmetic from AdamW's sixteen bytes per parameter, not a measurement. Four
cards do not raise the ceiling: `train_distributed.py` uses DDP, which
replicates model and optimizer per rank.

## 5. Corpus-built byte-BPE

A byte-level BPE learned from the project's own corpus, 8,192 entries, reduces
that corpus's token count by about **60%** against the character tokenizer it
replaced. Every window used in training was round-trip audited
(`locallm/test_tokenizer_integrity.py`, `locallm/audit_source_corpus.py`), and
the frozen tokenizer's file hash and fingerprint are recorded in every
checkpoint that uses it.

**Caveats.** Fewer tokens for the same text is a compression result and
explicitly **not** a learned-quality result; the project has said so since
[`PREDICT-tokenizer-2026-09-19.md`](PREDICT-tokenizer-2026-09-19.md). Loss in
BPE-token units is not comparable to the earlier character-model numbers.

## 6. Opt-in KV cache

Cached decoding is implemented, and verified to produce output identical to the
uncached path. It is **off by default** because the registered speed prediction
failed: see [`FINDINGS-kv-cache-2026-09-19.md`](FINDINGS-kv-cache-2026-09-19.md)
and its preregistration.

## 7. The architecture comparison, and its reversal

Six arms, three seeds (1337, 7, 42), 4000 updates each, 65,536 tokens per
update, identical frozen corpus and tokenizer, modern then GPT within each
seed. Registered in
[`PREREG-source-longer-2026-09-19.md`](PREREG-source-longer-2026-09-19.md).

| seed | modern val | GPT val | modern is |
|---|---:|---:|---|
| 1337 | 1.3611 | 1.2676 | 7.38% worse |
| 7 | 1.3388 | 1.2641 | 5.91% worse |
| 42 | 1.3691 | 1.2824 | 6.76% worse |

At 1000 updates the modern core led by 24.6%, 26.6% and 28.7%. Two registered
predictions held (all updates finite; each modern seed improved on its own
1000-step endpoint by 43.7-45.8%) and the third, that modern would keep a 3%
advantage, was falsified at every seed, in the opposite direction. Modern
also took 1,141 s against 961 s per arm and reserved 11.02 GiB against 8.27.

**Caveats.** One corpus, one tokenizer, one optimizer setting, one budget. A
learning rate or schedule tuned per architecture was not explored, and the
comparison holds those fixed by design. Token loss on a fixed validation window
is all that was measured: completions from all six arms remain repetitive.

## 8. Research instruments built for the 2026-09-19 experiments

Not achievements of the model, but of the apparatus, and they are what the
newer numbers rest on.

- [`t/composition_reference.py`](../t/composition_reference.py): a closed-form
  oracle that never imports the interpreter and never walks an AST, so
  agreement with a traced run is a cross-check between implementations.
- [`t/score_synthesis.py`](../t/score_synthesis.py): scores a candidate by
  reassembling the frozen task header with the model's body, so no answer can
  alter the contract it is scored against; counts malformed, ill-formed,
  undefined, over-budget, timed-out and over-length answers as failures. 11
  tests, one per outcome.
- [`t/audit_collapsible.py`](../t/audit_collapsible.py): asks whether a
  proper sub-sequence of a held-out task's own stages already passes its tests.
  This found that **38 of 38** correct answers across a twelve-arm study sat on
  such tasks, which reinterpreted that study's entire result.
- [`locallm/audit_example_masks.py`](audit_example_masks.py): proves on real
  tokens that every arm of a factorial sees identical input IDs and identical
  answer targets, differing only in which intermediate tokens carry loss.
- `t/out/evaluator-state-2026-09-19.json`: records both machines' HEAD, dirty
  files and per-file hashes before and after an evaluation, and computes
  whether anything moved. Round 7 was graded with `evaluator_stable: true`.

**Caveat that applies to all five.** They carry their own tests and my reading.
No second party has reviewed them.

## What is not on this page

No locallm model has beaten Phi-4-mini. The best is **3** clean answers of 232
against Phi's 3 ([`../t/out/score-r8.md`](../t/out/score-r8.md)), which is a tie
and not a win, and the plan to change that is WS-22 in
[`ROADMAP.md`](../ROADMAP.md). This page said "the best is 2" until 2026-09-20,
two rounds after it stopped being true.
