# The base rate by sampling on r12's core

> **Correction, 2026-10-05:** counts on the clean 200 in this file include 18 problems that an audit of the training rows
> later took out of the panel. Every published row is restated on the clean 182 in
> [DECONTAMINATION-2026-10-05.md](DECONTAMINATION-2026-10-05.md).

Registered 2026-09-30 09:29Z, before any draw. `t/PREDICT-2026-09-30-dawnr-r12-core.md` prediction
4 read 0 (`spec_agrees` on the 100 dev problems, greedy), and its registered consequence is this
measurement: "the base rate is measured by sampling (64 draws per problem through the checker)
before any reward is built". A greedy 0 does not say whether the model never writes an agreeing
answer or only fails to rank one first. The difference decides three things on the shelf: RL
through the engine (`t/RL-DESIGN-2026-09-26.md`: start when about 10% of groups outside the corpus
hold a passing sample), sampling with a selector (`t/RUN-NEXT-locallm-r12.md` section D), and
mined negatives (`t/NEGATIVES-2026-09-25.md`: 3 usable pairs, 30 needed).

## The measurement

The model is the one the core's judgement scored: the pipeline's mid-trained checkpoint on r12's
core (`ckpt.pt` sha256 `d74ee05a7f9d9790…`, from the core whose `ckpt.pt` is `704f4824b69ed645…`).
The problems are the same 100 dev problems (`t/r12-dev-ids.json`: MBPP train-side problems no
training document names); no held-out evaluation problem is asked.

    ~/.venv-locallm/bin/python locallm/chat_eval.py --model <4-mid/model> --out <base-rate.json> \
        --dev 100 --max-tokens 800 --grammar --max-calls 2 --answer best-verdict \
        --samples 64 --temperature 0.8 --top-k 20 --sample-batch 32 --seed 1

64 draws per problem in two batches of 32, temperature 0.8 and top-k 20 (the sampler RL-DESIGN
section 3 measured with), the judgement's prompt, grammar, two-call budget and best-verdict answer
rule, each batch seeded by `t/pilot_sampling.derive_seed`. Every draw is graded like a greedy
answer: well formed, passes every shown example, the tests tier (the problem's assertions and 50
drawn inputs against its reference), and agreement with the specification check on 200 drawn
inputs for a draw that passes its examples. pass@k is human-eval's unbiased estimate
(arXiv:2107.03374; receipt 30e7f15a9ba5). A 2-problem, 4-draw smoke of the tool runs first and is
discarded.

## Predictions

1. **At least 3 of the 100 problems have a draw that passes every shown example** (greedy: 0; two
   examples are a loose gate). Falsified below 3.
2. **At least 1 problem has a draw that passes its examples and agrees with the specification
   check.** Held at about even odds. Falsified at 0.
3. **RL's bar stays unmet: pass@16 is below 0.10 both for the tests tier and for specification
   agreement** (the document-format policy of 2026-09-26 had a test-passing sample on 0.6% of
   problems outside its corpus at 16 draws). Falsified at or above 0.10 on either.

## What each outcome decides

- Prediction 2 falsified (no agreeing draw on any problem): on this core there is nothing for a
  reward to reinforce or a selector to select; RL through the engine and the sampling pilot stay
  off, and only a teacher can supply agreeing answers. The corpus queue
  (`internal/RESEARCH-2026-09-30-stage-sweep.md` section 7) is the whole plan.
- Some problems hold an agreeing draw and pass@16 stays below 0.10: selection has something to
  select on those problems, and the draws that pass their examples and disagree with the
  specification are the negatives lever 3 lacked (their count is reported); RL stays off.
- Prediction 3 falsified: RL through the engine may be registered, with the dense reward and the
  difficulty band (the problems whose rate lies in (0, 1/4] are reported).

## What it cannot show

One checkpoint, one seed of draws, 100 problems from one source (MBPP's train side). The dev set
is not the held-out set: a rate here bounds what training on these problems could use, and says
nothing about the clean 200, which stays unseen.

## Outcome (written 2026-09-30, after all 6,400 draws were graded)

100 problems, 64 draws each, 19 minutes of generation on the desktop card. Numbers and every
problem's counts: `locallm/dawnr-base-rate-results-2026-09-30.json`.

| measure | problems with any such draw | draws of 6,400 | pass@1 | pass@16 | pass@64 |
|---|---:|---:|---:|---:|---:|
| well formed | 98 | 1,750 | 0.273 | 0.905 | 0.980 |
| passes every shown example | 4 | 28 | 0.0044 | 0.031 | 0.040 |
| tests tier | 2 | 6 | 0.0009 | 0.012 | 0.020 |
| agrees with the specification check | 1 | 3 | 0.0005 | 0.006 | 0.010 |
| passes its examples, disagrees with the check | 3 | 22 | | | |

1. **At least 3 problems pass their shown examples: holds** (4: MBPP 92, 188, 459, 771).
2. **At least 1 problem agrees with the specification check: holds as counted, and the count is
   an artifact.** The one problem is MBPP 771, "check if the given expression is balanced". Its
   three agreeing draws say `r == (len(s) % 2 == 0)`. The check calls the problem's Python
   solution with a list of integers, because t represents a string as a sequence of integers; no
   integer equals a bracket character, so the solution fed integers computes exactly "the length
   is even" (on the check's own draws it differs from the solution fed the string on 13% of
   inputs). The model's answer matches the check's degenerate reference, not the problem.
   **Read by hand, no draw on any problem is a correct answer.**
3. **pass@16 below 0.10 for the tests tier and for agreement: holds** (0.012 and 0.006). The
   document-format policy of 2026-09-26 stood at 0.6% of problems outside its corpus; a larger
   English stage, the chat format and the tool have not moved it.

**What it decides.** By the counted numbers the second branch applies (something to select, RL
off); by inspection the first does: on this core there is nothing for a reward to reinforce or a
selector to select, and only a teacher can supply agreeing answers. RL through the engine and the
sampling pilot stay off. The 22 draws that pass their examples and disagree with the check sit on
3 problems; the preference trainer needs 15.

**What it found about the instrument.** The artifact is a class. `t/audit_reference_types.py`
calls each reference both ways on the check's own draws: of the 100 dev problems 35 take a string;
for 15 the reference raises on every integer list (known since 2026-09-18: the check counts
nothing), for 18 it behaves the same, and for **2 it runs and silently computes another function**
(MBPP 315 and 771). Of the 232 held-out problems 41 take a string: 18 raise, 20 are the same, and
**3 silently differ (MBPP 125, 387 and 776, all on the clean 200)**. On those problems the check
can call a wrong answer agreeing and a right answer disagreeing, and it has: the 27B teacher's
second seed answers MBPP 387 (is the hexadecimal number even or odd) with its tests passing, the
check as it stands says its specification disagrees (the reference fed integers always answers
"Odd"), and with the reference fed the string it agrees on 174 draws. Of the 126 graded arms on
the desktop no locallm arm passes its tests on any of the three problems, so the published
locallm zeros stand; four teacher arms pass them on 387, so the teachers' specification-checked
counts can be one short. Recorded in `LIMITS.md`.

**Repaired the same day** (receipt ad806d032e1a; EvalPlus keeps a str a str when it grows inputs,
arXiv:2305.01210): `spec_check` now calls the reference with the types its own assertions use and
reads outputs the way the pool reads assertion values. Under the repaired check the 3 "agreeing"
draws on 771 disagree, the 3 tests-tier draws on 459 (which the old call could not check) disagree,
and every other verdict stands: **0 problems, 0 draws agree**. The judgement's dev block is
unchanged (10 answers move from "no valid draws" to a real verdict, none of them agreeing).
Re-scoring all 89 fully graded held-out answer sets on this machine changed no published count.

