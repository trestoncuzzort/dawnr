# The specifications are almost never weak. They are wrong.

> **Corrected the same day.** The first version of this document said "not one
> weak specification" across 388 answers. Widening the search found one, and
> the correction is at the end. The substance holds and the headline number
> did not: weakness is rare and wrongness dominates, but it is not zero.

Predictions registered in
[`t/PREDICT-2026-09-20-completeness.md`](../t/PREDICT-2026-09-20-completeness.md)
before the measurement. **Two of three are falsified and the third is
unscoreable**, and the falsification is worth more than the hypothesis was.

## What was measured

Every answer in three arms that all seven verifiers proved with its twin
refuted, split into the two populations that matter, and each specification put
through both halves of the check: does it hold at the problem's own reference
solution (soundness), and does it reject a mutated output (completeness)?

| arm | population | n | agrees | **disagrees** | scored for weakness | **weak** |
|---|---|---:|---:|---:|---:|---:|
| r7b greedy | clean | 2 | 2 | 0 | 2 | **0** |
| r7b greedy | proven but wrong | 117 | 3 | **52** | 3 | **0** |
| r4 (10.9M) | clean | 2 | 1 | 0 | 1 | **0** |
| r4 (10.9M) | proven but wrong | 205 | 2 | **43** | 2 | **0** |
| r8 headed2 | clean | 3 | 3 | 0 | 3 | **0** |
| r8 headed2 | proven but wrong | 59 | 3 | **44** | 3 | **0** |

**Not one weak specification anywhere.** Not in the clean answers, not in the
proven-but-wrong ones, across three arms and 388 proved answers.

> **This paragraph is the claim that was corrected**, and it is left standing
> because the reasoning that follows it was built on it. A wider search found
> one weak specification; see "Correction: the search was too narrow, and it
> hid one" at the end before quoting anything above it.

## The predictions

1. **Proven-but-wrong answers are weak at least three times as often as clean
   ones: falsified.** Both populations are at zero.
2. **Mean completeness is lower for proven-but-wrong in every set:
   unscoreable.** There is no variation to compare.
3. **At least 20% of proven-but-wrong answers are weak: falsified**, at 0% by
   this search and at 1 of 14 specifications once the search was widened.
   Falsified either way, and by a wide margin.

## What is actually happening

The proven-but-wrong population is dominated by `disagrees`: the specification
is **false at the problem's own reference solution**. 52 of 117, 43 of 205, 44
of 59.

Two of them, verbatim:

> *"Write a function to find n'th smart number."*
> The model wrote `ensures r == n * (3 * n - 2)`.
> False at `n = 0`, where the problem's own solution answers `2996`.

> *"Write a python function to check whether the given number can be
> represented as sum of non-zero powers of 2."*
> The model wrote `ensures r == x + 1`.
> False at `x = 4`, where the problem's own solution answers `True`.

The second is the clearest statement of the failure this project has: the
problem asks for a predicate and the model specified arithmetic. It then wrote a
program satisfying that specification, and **all seven proof systems correctly
proved the pairing, and all seven correctly refuted its twin.** The verifiers
did their job perfectly. The specification was a specification of a different
function.

So the model is not lazy. It is confident and wrong. A gate that rejects weak
specifications would have rejected nothing here, and the 3.6x filtering result
that motivated it does not apply to this failure.

## What this changes

**Do not build the completeness gate.** The prediction file said so in advance:
*"If 3 fails, the population is strong specifications of the wrong function —
the model understood the problem incorrectly rather than specified it lazily —
and the fix is the prompt-example arm."*

That arm is already implemented and unrun. The reasoning behind it now has
direct evidence: giving every training document the signature its own program
declares took signature failures from 40.8% to 12.1% and turned 2 clean answers
into 3, because it pinned the **types** the model was inventing. These
measurements say the model is still inventing the **semantics**, which is what
the problem's own assertions pin. `t/loop_locallm.py --examples` puts them in
the head; `internal/RESEARCH-NEXT-2026-09-20.md` carries the run and the rule
that Phi must be regraded with the same prompt before any comparison is quoted.

## What the check is still worth

The completeness half stays in `t/spec_check.py`. It costs nothing, it is
covered by nine tests, and it answers a question that had never been asked. Its
answer here is **negative and clean**: whatever is wrong with these
specifications, weakness is not it. A measurement that rules out a whole class
of explanation in one afternoon is worth keeping even when it finds nothing,
and this one also gives the pipeline a defence it did not have against a failure
mode that would otherwise be invisible.

One caveat on the method. The cross-tabulation above draws arguments with a
generator seeded per task, so the tasks are independent of each other; the
shipped report threads one generator through every task in order, which is why
it is reproducible but not parallelizable. The two agree on every verdict
reported here, and the per-task seeding is the honest choice for a comparison
between populations.

---

# The fix already existed: Clover's third consistency edge

Under the operator's rule — search for an existing fix before writing one — the
failure above has prior art with a repository.
**[Clover: Closed-Loop Verifiable Code Generation](https://arxiv.org/abs/2310.17807)**
([POPL/Dafny 2024](https://popl24.sigplan.org/details/dafny-2024-papers/1/CLOVER-Closed-Loop-Verifiable-Code-Generation),
code at [ChuyueSun/Clover](https://github.com/ChuyueSun/Clover)) reduces
correctness to **consistency between three artifacts** — code, docstring and
formal annotation — by checking every pair. It reports up to **87% acceptance on
correct instances with no false positives** on CloverBench.

This project had two of those three edges and never noticed the third was
missing:

| edge | how this repo checks it |
|---|---|
| code ↔ annotation | the seven verifiers, plus the twin refutation |
| code ↔ problem | the problem's own unit tests |
| **annotation ↔ problem** | **only via a reference solution, when one runs** |

`spec_check.check_task` runs the problem's reference solution and draws random
arguments. When the reference will not run, the drawn shapes do not fit, or the
arity differs, it gives up: **78 of 149 answers in one arm**.

## The edge, added

`t/spec_check.check_points` evaluates the model's `ensures` at the problem's
**own assertions** — the ground-truth input/output pairs shipped with every
problem. No reference solution, no random draws, no language model, no verifier
call.

| arm | population | n | caught | no opinion |
|---|---|---:|---:|---:|
| r7b greedy | proven but wrong | 117 | **72 (62%)** | 45 |
| r7b greedy | clean | 2 | **0** | 0 |
| r4 (10.9M) | proven but wrong | 205 | **56 (27%)** | 148 |
| r4 (10.9M) | clean | 2 | **0** | 0 |
| r8 headed2 | proven but wrong | 59 | **52 (88%)** | 5 |
| r8 headed2 | clean | 3 | **0** | 0 |
| Phi-4-mini | proven but wrong | 1 | **1 (100%)** | 0 |
| Phi-4-mini | clean | 3 | **0** | 0 |

**Zero false positives across every clean answer in four answer sets**, which is
the property Clover reports and the only property that makes a gate safe to
build on. On the best arm it explains 88% of the proven-but-wrong population by
itself.

A test caught a real defect while this was being written: `zip()` silently
truncates, so a point carrying more arguments than the task has parameters was
being checked against a truncated environment instead of skipped — a verdict
about nothing. The guard now compares lengths before zipping.

## What it is worth

It is cheap, it never fires on a right answer, and it reaches exactly the
population the reference-based check cannot. That makes it the first candidate
for a training-data gate that would actually remove something: the
completeness gate was refused above because it would have rejected nothing,
and this one would reject between a quarter and seven-eighths of the
proven-but-wrong answers, depending on the arm.

It stays a measurement until someone runs a round with it as a gate and reports
what the pool lost, because adding a gate changes what the pool contains and the
pool's contents are cited evidence.


---

# Correction: the search was too narrow, and it hid one

The completeness check tested four wrong answers per draw: `o+1`, `o-1`, `0`,
`-o`. **CLEVER** ([arXiv:2505.13938](https://arxiv.org/abs/2505.13938)) and
**VeriEquivBench** ([arXiv:2510.06296](https://arxiv.org/abs/2510.06296)) both
state the strong form of this as a proof obligation: *no* output other than the
right one may satisfy the specification, and a spec that is merely sound scores
zero. We cannot discharge that against a Python reference, so the honest
substitute is to search harder and report how hard the search was.

The neighbourhood is now twelve candidates for an integer and seven for a
sequence, including dropping the first element and swapping the first two.
Re-measured over the same three arms, **1,295 wrong answers tested instead of
about 300**:

| arm | specifications scored | weak | wrong answers tested |
|---|---:|---:|---:|
| r7b greedy | 5 | 0 | 333 |
| r4 (10.9M) | 3 | 0 | 249 |
| r8 headed2 | 6 | **1** | 713 |

**One weak specification exists**, and it is the textbook case:

> *"Write a function to find maximum of three numbers."*
> ```
> ensures r >= a
> ensures r >= b
> ensures r == a or r == b or r == c
> ```

It forgot `r >= c`. At `a=15, b=28, c=30` the right answer is 30, and the
specification also accepts **28**: 28 ≥ 15, 28 ≥ 28, and 28 is one of the three.
All seven proof systems proved a program meeting it, and the twin was refuted.
It rejected **345 of 350** wrong answers, which is why four mutations missed it:
it is nearly tight, and the miss is in the one direction that matters.

## What changes and what does not

- The headline claim becomes **1 of 14 scored specifications**, not 0 of 14. The
  dominant failure is still `disagrees` — a specification false at the problem's
  own solution — by two orders of magnitude.
- **The decision not to build a completeness gate stands.** A gate that fires on
  1 of 14 answers, none of which was clean, removes nothing worth removing.
- The instrument is better and the claim is smaller. That is the right direction
  for both. The next strengthening is the one the two papers actually specify:
  prove `∀y. spec(x,y) → y = ref(x)` with the seven provers rather than
  searching for a counterexample by hand.

The lesson is about the first version of this document rather than about the
model: **a negative result is only as strong as the search that failed to find
anything**, and reporting the size of that search is not optional.
