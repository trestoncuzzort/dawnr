# Counterexample-guided repair, measured: +3 cells of 182, and a metric that hid it

Forty answers from `qwen235-heldout` that pass their problem's own tests but are
not clean in all seven kernels, repaired once by Qwen3-235B-A22B with the
concrete witness in the prompt, then regraded.

    python3 t/repair.py t/out/spec-experiment/qwen235-heldout \
        --api openai --host 127.0.0.1:8077 --model <the 235B> --pool v3 --jobs 8

## What came back

40 replies, 26 parsed into valid tasks, **26 of 26 passed their problem's own
tests**, **0 dropped for illegally changing the specification**, and **0 clean in
all seven kernels**.

The last number is the one to be careful with, because on its own it is
uninformative. The same 26 answers, before and after, per kernel, counting only
`verified` with the twin `refuted`:

| kernel | before | after | delta |
|---|---:|---:|---:|
| dafny | 12/26 | 12/26 | 0 |
| verus | 11/26 | 11/26 | 0 |
| spark | 11/26 | 10/26 | **−1** |
| framac | 9/26 | 11/26 | **+2** |
| lean | 6/26 | 7/26 | +1 |
| rocq | 7/26 | 8/26 | +1 |
| fstar | 10/26 | 10/26 | 0 |
| **cells** | **66** | **69** | **+3** of 182 |

Four answers gained at least one kernel, **two lost at least one**, twenty were
unchanged. So the loop did something, it was small, and the conjunctive gate
reported it as exactly zero.

## The gate, priced

Per-prover conversion on the parent arm, 67 graded answers: dafny 47.8%, verus
46.3%, fstar 46.3%, spark 44.8%, framac 41.8%, lean 34.3%, rocq 34.3%. If the
seven were independent, the product of those rates predicts **0.15 clean answers
of 67**. The arm scored **11**. So the kernels agree about 70 times more often
than independence would give, which is what you expect when five of the seven
discharge through SMT and often literally through Z3, and SPARK is itself a
three-prover portfolio tried until one succeeds.

On the repaired set the independence prediction is **0.03 of 26**. Observing 0 is
therefore consistent with a loop that works and a gate that is brutal, and
equally consistent with a loop that does nothing. **A seven-way AND at n=26
cannot tell those apart**, which is why the per-kernel table above is the result
and the clean count is not.

## Against the right baselines

The run was designed against VeriMed ([arXiv:2605.13817](https://arxiv.org/abs/2605.13817)),
whose ladder is 55.4% with no feedback to **98.5%** with a concrete
counterexample. That comparison is void, on five counts read out of the paper:
its artifact is a JSON answer constrained to a schema, not a program with a
proof; the formal model it is checked against is hand-built and fixed; it runs
six attempts, not one; its oracle is one Z3 with no anti-vacuity gate; and its
CEGR arm began at **46.2% first-attempt accuracy** where ours began at 0. Its
97.1% is a repair rate over answers already 46% right. We should not have
quoted it as a target and do not quote it again.

What this run should be read against instead:

- **VerifyThisBench** ([arXiv:2505.19271](https://arxiv.org/html/2505.19271v2)),
  seven tools including five of ours, scored **per tool**: o3-mini 3.62%
  zero-shot to **9.37%** after four refinement rounds. +5.75 points over four
  rounds for a frontier reasoning model. On 26 answers, one round predicts about
  0.4 conversions before any multi-prover gate.
- **AlgoVeri** ([arXiv:2602.09464](https://arxiv.org/html/2602.09464v2)), which
  measured our exact model: Qwen3-235B-A22B at 15 repair rounds reaches 25.3%
  Dafny, 9.5% Verus, 3.8% Lean, per prover. Its conclusion is the relevant one:
  "the repair curves fail to significantly outperform the pure sampling
  baseline, and repair often degrades performance... compute is better scaled
  with width rather than depth." We observed two regressions in 26, which is
  that effect.

Against those, +3 cells in one round is unremarkable rather than broken.

## Why one round was the right test after all

The plan had been to blame the budget and iterate. The literature says not to.
*Is Three the Magic Number?* ([arXiv:2607.05197](https://arxiv.org/html/2607.05197v1))
measures mean relative improvement per repair step across six tool-dataset
combinations: the largest gain is always at step 1, and by step 3 marginal gains
are under a few percent. AxDafny's twenty-iteration Dafny loop agrees that gains
are "heavily concentrated within the first 5 iterations", and its
iteration-friendly case still started from 11.6%, not 0. So a near-zero first
round is a signal about the feedback, not a warm-up artifact.

## What the feedback was missing

The prompt contained the violated obligations in prose and a concrete witness.
That is the shape a controlled ablation calls **LocObs**, failure location plus
observed value, and it measures as barely better than saying "wrong":
28% to 36% for one model, 16% to 18% for another. Adding **admissible
alternatives** to the same message takes it to 70% and 58%, a gain of 36 and 40
points ([arXiv:2607.14167](https://arxiv.org/html/2607.14167v1)). Prose versus
JSON made no difference; the missing ingredient is a candidate repair, not a
better format.

Two mechanisms explain the 26-pass-tests-but-0-verify signature:

- Models patch the pointed-at error without fixing global correctness. In graph
  colouring they "fixed" 94% of errors that were **deliberately fabricated**
  (arXiv:2310.12397), applying local edits "without regard for overall
  correctness". Killing one witness does not discharge a universally quantified
  obligation, and our two regressions are that.
- Handing over a counterexample in prose buys nothing by itself. ExVerus
  ([arXiv:2603.25810](https://arxiv.org/html/2603.25810v1)) measures prose
  counterexamples at or below plain error messages, and gets its gain from
  mutating candidates and **mechanically checking that the candidate blocks the
  witness**: candidates that block at least one counterexample verify 70.78% of
  the time against 24.84% for those that do not.

## What is worth keeping from this run

**26 of 26 repaired answers still pass their tests and none changed the
specification illegally.** Every large study of this task reports models
reaching for `ensures true`, `assume(false)` or `sorry` when the reward permits
it; Vericoding measures roughly 9% of specs as too weak, ExVerus discarded 426
candidate tasks down to 67 for reward hacking. Ours did not cheat once, which is
the gate doing its job.

And 480 candidate repairs are now banked across twelve draws at temperature 0.7,
which is the pool the next step needs: Houdini
([Flanagan and Leino, FME 2001](https://users.soe.ucsc.edu/~cormac/papers/fme01.pdf))
filters a candidate set by deleting whatever the prover refutes until quiescence
and the survivors are the unique maximal valid subset. That needs no model, only
the seven provers we already run.

## What not to claim

No published system attempts a conjunctive seven-prover gate with a mutation
kill, so there is no basis for expecting a repair loop to produce a high clean
count under ours. The nearest precedent reaches 14 of 18 dual-prover and 3 of 18
triple-prover agreement with sixteen backends and human orchestration. If the
headline is a clean count, the gate is the binding constraint, not the loop. If
the headline is the criterion itself, then a low clean count is the finding, and
VeriEquivBench is the precedent for publishing it that way: Claude-4-sonnet
scores 75.81% on CloverBench and **4.83%** once specification strength is
required.
