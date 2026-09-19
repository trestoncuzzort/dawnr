# Round 7: a pretrained core through the pipeline, and it scored 1

The first time a pretrained locallm has answered the 232 held-out problems.
Predictions were registered in
[t/PREDICT-2026-09-19-round7.md](../t/PREDICT-2026-09-19-round7.md) while the
kernels were still running and before either `kernels.md` existed.

## The table

`t/out/score-r7.md`, produced by `t/score_heldout.py`.

| model | well formed | tests pass | **clean** | converts | clean, spec checked | wrong but proven |
|---|---:|---:|---:|---|---:|---:|
| phi4-mini-v3 (historical) | 12 | 6 | **3** | 3/6 (50%) | 0, 3 unchecked | 1 |
| phi4-mini-eval2 (regraded today) | 12 | 6 | **3** | 3/6 (50%) | 2, 1 unchecked | 1 |
| qwen15b-base-v3 | 39 | 13 | **3** | 3/13 (23%) | 0, 3 unchecked | 8 |
| locallm-r4 (3.2M) | 209 | 2 | **2** | 2/2 | 0, 2 unchecked | 204 |
| locallm-r5 (3.2M) | 198 | 2 | **2** | 2/2 | 0, 2 unchecked | 196 |
| **locallm-r7-92m** | **136** | **1** | **1** | 1/1 | **1, 0 unchecked** | 91 |

**The pretrained 92M core scored 1 clean of 232.** That is below the 3.2M
character models it was meant to improve on, and below Phi-4-mini. It also
wrote *fewer* well-formed answers than they did, 136 against 209 and 198.

## The predictions

1. **Tests passing at least 3 and fewer than 20: falsified, low, at 1.** This
   is the failure I said in the registration I expected: "if 92M and
   real-source pretraining buy nothing at all here, tests passing lands at 1 or
   2 and prediction 1 fails low."
2. **Clean fewer than 3, i.e. it does not beat Phi: held**, at 1.
3. **Conversion below 50%: unscoreable**, exactly as registered -- the
   denominator is 1, below the 5 the prediction required. It reads 100% and
   that number means nothing.
4. **The fresh Phi baseline reproduces the historical row within one answer per
   column: held, exactly.** 12 well formed, 6 tests passing, 3 clean, in both.
   The only column that moves is the specification check, and it moves because
   the new tag was actually checked while the historical one never was.
5. **At least one specification disagreement among the clean answers:
   falsified.** The single clean answer was checked and agrees with its
   problem.

Two held, two falsified, one unscoreable.

## The instrument held, which is why the rest can be read

`t/out/evaluator-state-2026-09-19.json`: `evaluator_stable: true`. No hash moved
across the whole evaluation -- not on the desktop, where extraction, tests and
the specification check ran with inherited modifications to `interp.py`,
`cache.py` and `run_par.py`, and not on the lab, where the seven kernels ran at
`17d7aaf` with 109 dirty entries. The lab HEAD did not move either.

The grading machine has **no verdict cache at all**: its `run_par.py` does not
import `t/cache.py`, which is uncommitted desktop work. Every cell in this
session ran its kernel by absence of the feature rather than by a flag.

And the baseline reproducing itself to the answer is what licenses the
comparison. Without it, a 1 against a 3 could have been lowering drift.

## What the 136 answers actually are

- **55 of 136 fail on the signature**: the model writes a task whose parameter
  or return types do not match the signature the prompt handed it. Two in five
  of its well-formed answers are disqualified before a test runs.
- **80 fail their tests** on values.
- **91 are proven but wrong**: all seven verify the program against the
  specification the model wrote, and all seven refute its twin, and the tests
  still fail. The model writes internally consistent specifications of the
  wrong function.
- **1 passes**, `mbpp_682__mul_list`, and it is clean and spec-checked.

That is the same disease the 3.2M models had -- notation without the problem --
and pretraining on 46M tokens of real source did not cure it. If anything the
larger model is better at producing confident, self-consistent, wrong
specifications: 91 proven-but-wrong out of 136 well formed is a higher rate
than the 3.2M rows' 204 of 209 only because their denominator is bigger.

## What this does not establish, stated before anyone asks

- The comparison moves **size, tokenizer, pretraining corpus and training
  recipe at once** against the 3.2M rows. It shows the pipeline's number did
  not improve; it cannot say which of the four is responsible.
- **The exported checkpoint is the end of the schedule, step 300**, whose
  validation loss on the specialization corpus (0.5927) is worse than step
  150's (0.5738). I chose the end of the schedule to avoid selecting a
  checkpoint, and that choice is now a live candidate explanation for the
  result. It is cheap to test and has not been tested.
- The specialization corpus is **39,191 training tokens**, seen many times over
  4000 updates at batch 8. Whatever this measures, it is not a data-rich
  fine-tune.
- Sampling was temperature 0.5, top-k 20, one answer per problem, as the
  earlier locallm rows used. Nothing here is a claim about the model's best
  achievable answer.
- None of the instruments behind this round were reviewed by anyone but their
  own tests and me. The second agent's review was requested and did not arrive.

## What it buys

The measurement that was missing has been made, and it says the obvious cheap
version of "use a pretrained core" does not move this pipeline. The next
questions are ordered by cost: rerun from the step-150 checkpoint, which is
half an hour; fix the signature failure, which is 55 answers thrown away for a
reason the prompt already contains; and only then argue about size.
