# The specifications are not weak. They are wrong.

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
| r4 (3.2M) | clean | 2 | 1 | 0 | 1 | **0** |
| r4 (3.2M) | proven but wrong | 205 | 2 | **43** | 2 | **0** |
| r8 headed2 | clean | 3 | 3 | 0 | 3 | **0** |
| r8 headed2 | proven but wrong | 59 | 3 | **44** | 3 | **0** |

**Not one weak specification anywhere.** Not in the clean answers, not in the
proven-but-wrong ones, across three arms and 388 proved answers.

## The predictions

1. **Proven-but-wrong answers are weak at least three times as often as clean
   ones: falsified.** Both populations are at zero.
2. **Mean completeness is lower for proven-but-wrong in every set:
   unscoreable.** There is no variation to compare.
3. **At least 20% of proven-but-wrong answers are weak: falsified**, at 0%.

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
