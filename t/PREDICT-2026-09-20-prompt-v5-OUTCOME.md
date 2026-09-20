# Outcome: prompt v5's grammar-guidance block, measured 2026-09-20

Predictions registered in `t/PREDICT-2026-09-20-prompt-v5.md` before the arm ran.
Same 232 held-out problems, same model, pool v3, temperature 0, seed 1, 8192
tokens. Only the prompt differs.

| stage | control `qwen235-heldout` (v3) | `qwen235-heldout-p5` (v5) |
|---|---:|---:|
| parse failures | 140 | **134** |
| well-formedness failures | 25 | **19** |
| well formed | 67 | **79** |
| tests pass | 53 | **62** |
| **clean, all seven with the twin refuted** | **11** | **11** |
| conversion | 11/53, 21% | 11/62, **18%** |
| after the specification check | 8 | **7** |

## Against each prediction

**1. Parse failures fall below 120, from 140. FALSIFIED.** 134, a fall of six.
The block names the three shapes that cost the most replies and the parser barely
noticed. Whatever the parse wall is, it is not the model not knowing what t looks
like.

**2. Well-formed lands between 75 and 130. HELD, at the low end.** 79.

**3. Clean answers do not fall below 11. HELD, and this is the result.** Exactly
11, the same eleven the control found. The prereg adopted 2026-09-18's rule that
"the number that decides this is clean answers, not parse rate", and by that rule
the block bought nothing.

**4. Conversion does not improve. HELD, and it fell**, 21% to 18%, because the
denominator grew by nine and the numerator did not move at all.

**5. Tests passing rises by at least 5. HELD.** 53 to 62, +9.

Four held, one falsified.

## What it actually did, and why that is not what WS-21 assumed

The gain landed one gate later than intended. Parse failures moved 6; well-formedness
failures moved 6 and well-formed answers 12; test-passing answers 9. So the block did
not teach the model to write text the parser accepts. It taught it to write text that
is correctly **typed and structured** once parsed, and to compute the right value
more often.

And none of that reached the proof gate. Nine more answers pass their problems' own
tests and not one of them verifies in all seven with its twin refuted.

**It also cost an answer on the column this project cares most about.** After
`spec_check.py`, the control reads 8 and p5 reads 7: of p5's 11 clean answers, 7
agree with their problem on 100 draws, 3 cannot be checked, and one disagrees,
`mbpp_355__count_Rectangles`, whose `ensures` is false at `n=4` where the problem's
own solution answers 41. That is the same problem and the same wrong specification
the control arm produced, so the block did not introduce the defect and did not
remove it either.

## What this closes

**WS-21 move 2 is closed as measured rather than implemented.** The move reads
"prompt fixes that need no grammar", and the measurement is that a prompt fix moves
the first two gates and stops there. Read together with move 1, which is now running
on the guidance backend, the workstream's own framing needs correcting: the parse
wall was never the binding constraint on clean answers. It is the largest *loss* by
count, which is what `t/funnel.py` measured and what made it look binding, and
removing six percent of it changed the clean count by zero.

The prediction that was falsified is the useful one. It was falsified because it
assumed the wall is ignorance of the notation, and PostcondBench's 0.629 to 0.814 on
Corr@1 was measured on a model writing JML into an existing method, where the
notation is the whole task. Here the notation is the easy part, which locallm has
been saying all along: it parses 98% and passes 2 tests in 464 answers.

## Kept

v5 is left in `spec_experiment.py` beside v1 through v4, which are untouched, so
every existing column stays comparable. It is not promoted to the default: 12.7's
standing rule says no round is compared across prompts until the control moves too,
and there is nothing here worth moving a control for.
