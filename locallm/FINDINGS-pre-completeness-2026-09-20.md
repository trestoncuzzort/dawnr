# The fourth quadrant is measurable after all, and it finds almost nothing

`t/spec_scorecard.py` has printed **"pre-completeness NOT MEASURED"** since it
was written, with the reason: it needs inputs the problem should reject, and
this corpus ships none. That reason was wrong, and so was my first attempt to
fix it. Both are below, because the second mistake is the more instructive one.

## What the quadrant is

vACT / Spec-Harness (arXiv:2604.00280) scores a specification as a two-sided
classifier over four quadrants. Three were already instrumented here:

| quadrant | question | instrument |
|---|---|---|
| post-correctness | does the `ensures` hold at the right answer? | `check_points`, `check_task` |
| post-completeness | does it reject wrong answers? | `mutations`, `exploit` |
| pre-correctness | does the `requires` admit the problem's own examples? | `check_points.points_excluded` |
| **pre-completeness** | **does the `requires` reject inputs the problem does not define?** | **missing** |

## The corpus does not need to ship negatives

The problem's own reference solution is already the oracle for the problem's
**outputs**. It is equally the oracle for the problem's **domain**: an input the
reference refuses to compute is an input the problem does not define, and a
`requires` that still admits it is claiming ground the problem never gave it.

This is the admissibility leg of the admissibility / soundness / uniqueness
triad that property-based specification validation uses (VERINA
arXiv:2505.23135, CLEVER arXiv:2505.13938), where the same three cheap random
checks found underspecification in about 10% of specifications.

The signal was already being drawn and discarded. `check_task` had:

    except Exception:
        continue            # the reference refuses this input; not a finding

It was a finding. Four lines now ask, at that exact point, whether the
specification refuses the input too.

## The first version was wrong, and it looked like a result

Measured over three answer sets, the first implementation reported:

| set | population | pre-completeness |
|---|---|---:|
| phi4-mini | clean | **0.000** |
| qwen3.8-27B | clean | 0.455 |
| qwen3.8-27B | proven but wrong | 0.667 |

"Phi's clean answers are pre-incomplete at 0.000 while a 27B scores 0.455" is a
publishable-sounding differentiator, and it is an artifact.

The witnesses said so. `mbpp_102__snake_to_camel` produced **40 domain probes
out of 40 draws**, with witness `[[111, 120, 118, 117]]`: t represents a string
as a sequence of ints, the corpus's Python solution wants a `str`, and every
call raises `TypeError`. The reference was not declining a domain boundary. It
could not accept the value shape at all.

Counted across the 27B set: **97 answers produced domain probes, and 54 of them
came from a reference that never succeeded on a single draw.** More than half
the signal was the harness failing to talk to the problem, scored as a confident
0.000 against the specification.

The probes are now reported only when the reference is known to run on that
problem (`reference_ran > 0`). Where it never ran, the result says
`pre_completeness_unmeasurable: reference never ran` rather than scoring it.

## What it says once it is honest

    tag                          population            n  post-corr  post-comp  pre-corr pre-comp/n
    locallm-r8                   clean                 2      1.000      1.000     1.000       n/a
    locallm-r8                   proven_but_wrong    105      0.000      0.924     1.000   0.000/1
    phi4-mini-eval2-2026-09-19   clean                 3      1.000      1.000     1.000       n/a
    phi4-mini-eval2-2026-09-19   proven_but_wrong      1      0.000      1.000     1.000       n/a
    qwen3.8-27b-fp8-v3           clean                57      1.000      1.000     1.000   0.833/6
    qwen3.8-27b-fp8-v3           proven_but_wrong     12      0.083      0.833     0.917   1.000/2

**Nine answers out of 180 have a measurable domain boundary.** Every rate is
printed with the count it rests on, because `0.000/1` is one answer and reads
nothing like a population result.

So: the quadrant is instrumented, and **this corpus has almost no signal in
it**. MBPP problems over the inputs t can represent are very nearly total, so a
missing precondition rarely has anything to be wrong about. That is a fact about
the corpus, not a pass mark for the specifications, and it is the honest reason
the column was empty rather than the one the file used to give.

## What would make it bite

The instrument is ready and the corpus is the limit. Problems with real
preconditions (division, indexing, non-empty inputs, sorted inputs) would give
it something to measure. `nl/` has APPS and CodeContests, whose problems carry
explicit input constraints in their statements, and those are already on disk
and unused by the spec pipeline.

## Claims this does not support

- Not that specifications here have good preconditions. Nine measured answers
  cannot support that, and 105 of locallm-r8's proven-but-wrong answers had no
  measurable boundary at all.
- Not that pre-completeness distinguishes models. The one comparison that looked
  like it did was the artifact above.
- Not that a refusing reference always marks a domain boundary. It can be a bug
  in the reference. The result carries its witness so a human can tell.
