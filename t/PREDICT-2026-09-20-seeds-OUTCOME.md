# Outcome: the three seed arms, measured 2026-09-20

Predictions registered in `t/PREDICT-2026-09-20-seeds.md` before any table was
read. Graded from the desktop with `bash t/grade_lab.sh heldout` at
`T_LAB_JOBS=12`, all seven kernels, twin refuted, on the same 232 held-out
problems as every other arm.

| arm | core seed | well formed | tests pass | clean | after the spec check |
|---|---|---:|---:|---:|---:|
| `locallm-r9` | 1337 | 114 | 2 | **2** | 2 |
| `locallm-r9-seed7` | 7 | 106 | 2 | **1** | 1 |
| `locallm-r9-seed42` | 42 | 101 | 3 | **3** | **2** |
| `locallm-r7b-headed2`, for reference | 1337 | 91 | 3 | 3 | 3 |

Spread of clean: **2** (3 down to 1). Mean 2.0. After the specification check:
2, 1, 2, spread 1, mean 1.67.

## Against each registered prediction

**1. At least one arm scores 3 or more clean. HELD.** `seed42` scored 3. The
recipe can reproduce its own headline, once in three tries.

**2. Not all three score 3 or more. HELD.** 2, 1, 3.

**3. The spread is at most 2 clean answers, falsified at 3 or more. HELD, at the
boundary.** Best 3, worst 1, spread exactly 2. This was named in advance as "the
prediction that actually matters", with the pre-committed consequence that a
spread of 3 or more would mean rewriting `README.md` into a mean and a range.
The spread is 2, so that rewrite is not triggered, and the claim stands as
written with the seed evidence it previously lacked. It stands with a thinner
margin than "2, 3, 3" would have given: one of the three arms produced a single
clean answer.

**4. Every clean answer survives `spec_check.py`. FALSIFIED.** Six clean answers
across the three arms, 100 random draws each against the problem's own reference
solution: **5 agree, 1 disagrees.**

    DISAGREES locallm-r9-seed42/mbpp_541__check_abundant:
    ensures[0] is false at args=[2], the problem's solution answers False

The prediction said this was "the one column where this project is ahead, and a
regression there costs more than a clean answer". It is a regression, and it
costs `seed42` its third answer. Every locallm arm measured before today was
100% on this column; that is no longer a property of the method, it is a
property of the arms that happened to be measured.

**5. Well-formed counts land between 80 and 160 for all three. HELD.** 114, 106,
101. No splitter or head regression.

Four held, one falsified, and the falsified one is the column the project was
proudest of.

## What this does and does not settle

It answers attack 3 as it was posed: the tie does not rest on a single lucky
draw, because two of three seeds reach 2 or more clean and one reaches 3. It
does not show the recipe is stable at 3; the honest range across greedy seeds is
**1 to 3 clean, 2.0 mean, 1.67 after the specification check**.

**The seeds measure a different recipe from the headline.** Noted in the
prediction file before grading and repeated here: all three r9 arms decode
greedily at `temperature 0.0`, and `locallm-r7b-headed2` decodes at
`temperature 0.5` because `t/gen_fleet.sh` dropped the `--temperature 0` it was
handed (`CORRECTIONS.md`). So this is seed variance of the greedy recipe, and
the headline arm's own variance is still unmeasured. Measuring it needs three
more arms at temperature 0.5 and three different seeds, which nothing has run.

Both quarantined tables from 2026-09-19, which read 0 clean because Verus never
started, are superseded by this run. `kernels.md.INVALID-verus-never-ran` and
the `WHY-NO-TABLE.md` beside them stay where they are as the record of that
failure.
