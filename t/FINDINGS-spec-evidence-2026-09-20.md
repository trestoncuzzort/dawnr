# The headline's specification check had no evidence in the tree, 2026-09-20

`README.md`, `SCOREBOARD.md` and `locallm/ACHIEVEMENTS.md` all report "3 against
2 after the specification check". Until today `t/out/spec-disagree.json` held 496
result rows and **not one** for `locallm-r7b-headed2`, `locallm-r8` or
`phi4-mini-eval2-2026-09-19` — the three arms that column is about. The claim was
not reproducible from the repository.

It is now, and it holds exactly as published.

## Why the evidence was missing

Two runs on 2026-09-20 at 03:47 did name all three tags. Both used `--pool v5`.
All three arms are graded on the 232 held-out problems of `split-v3.json`, so
every answer was outside the pool and was skipped. The tell was in the file the
whole time: those runs recorded **the same counts** as the 37-tag run before them,
`{agrees: 288, disagrees: 5, other: 28}`, so the five tags they added contributed
nothing. The tags were still written into the cumulative `tags` list, which is
the list a reader uses to tell "checked, nothing disagreed" from "never checked".

This is the failure in `CORRECTIONS.md`'s first entry happening a second time in
a second place. There it was `score_heldout.py` treating absence from the
disagreement list as a pass. Here it is `spec_check.py` recording a tag as
checked when it checked none of its answers.

## The measurement

    python3 t/spec_check.py locallm-r7b-headed2 locallm-r8 \
        phi4-mini-eval2-2026-09-19 --pool v3 --n 100 --only clean --seed 1
    python3 t/spec_check.py locallm-r4 locallm-r5 locallm-r7-92m phi4-mini-v3 \
        --pool v3 --n 100 --only clean --seed 1

Then `python3 t/score_heldout.py <tags>`, which computes the column from those
rows rather than from absence:

| tag | clean | spec checked | spec unchecked | disagrees |
|---|---:|---:|---:|---:|
| locallm-r4 | 2 | **1** | 1 | 0 |
| locallm-r5 | 2 | **1** | 1 | 0 |
| locallm-r7-92m | 1 | 1 | 0 | 0 |
| locallm-r7b-greedy | 2 | 2 | 0 | 0 |
| **locallm-r7b-headed2** | **3** | **3** | 0 | 0 |
| locallm-r8 | 2 | 2 | 0 | 0 |
| locallm-r9 | 2 | 2 | 0 | 0 |
| locallm-r9-seed7 | 1 | 1 | 0 | 0 |
| locallm-r9-seed42 | 3 | 2 | 0 | 1 |
| phi4-mini-v3 | 3 | 1 | 1 | **1** |
| **phi4-mini-eval2-2026-09-19** | **3** | **2** | 1 | 0 |

**The headline is confirmed.** `locallm-r7b-headed2` is 3 of 3 agreeing on every
draw: `mbpp_682__mul_list` on 12 draws, `mbpp_729__add_list` on 10, and
`mbpp_970__min_of_two` on 100. Phi's regraded arm is 2, with
`mbpp_269__ascii_value` uncheckable because the reference solution never ran on
the drawn shapes. 3 against 2, as written.

All eight of those answers also pass the examples check: `points_held = 3`,
`points_failed = 0` for every one, so none of them contradicts an input/output
pair its own problem states.

## What did not hold: two earlier rows were overcounted

`SCOREBOARD.md` gave rounds 4 and 5 a 2 in that column. Each has 2 clean answers,
and in each arm only one is checkable. Both arms' second clean answer is
`mbpp_800__remove_all_spaces`, which returns `no valid draws`: it is a string
problem, `t` has no string type, and the drawn argument shapes never fit the
reference solution. By the scoreboard's own stated convention — "one of Phi's
three cannot be checked at all, so on that column it reads 3 against 2" — an
unchecked answer does not count. So those cells are **1 and 1**, corrected today.

`locallm/FINDINGS-round7-2026-09-19.md` and `FINDINGS-round8-2026-09-19.md` are
left as written. They reported "0, 2 unchecked" for both arms, which was true
when they were written; the scoreboard, not the findings, read unchecked as
passing. Dated records that were accurate are not rewritten here.

Phi's historical arm `phi4-mini-v3` is worse than its regrade: of 3 clean, one
agrees, one is uncheckable, and one **disagrees** —
`mbpp_20__is_woodall`, whose `ensures` is false at `n = 63` where the problem's
own solution answers `True`. The regraded `phi4-mini-eval2` arm has no
disagreement, which is why the README compares against the regrade.

## The fix, so silence stops meaning "checked"

`t/spec_check.py` now excludes from the cumulative `tags` list any tag that
produced no rows, prints

    NOT CHECKED, no answer of theirs was in pool <pool>: <tags>

and records `checked_nothing` in the run entry. A tag the checker skipped
entirely can no longer be mistaken for a tag that passed.

Thirty tags in the file still claim a check with no row and no recorded
disagreement behind it, among them `locallm-r4-train`, `student-r4-train` and
twenty-odd sampling arms. They are train-split and side arms that no public table
quotes, they are left in place rather than silently rewritten, and the list is
recoverable by comparing `tags` against the keys of `results` and `disagree`.
Every tag any public claim rests on is now measured above.
