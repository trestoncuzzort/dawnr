# PREDICT 2026-10-13: solve every uDebug problem for submission

Registered 2026-10-13T05:54Z, before the first repair call and before the export's first confirmation run.
Receipt `dawnr-udebug-solve-all` (arXiv:2304.05128; docs.python.org PYTHONHASHSEED).

## The goal, stated so it can be met or missed

A problem is **solved** when one program reproduces the judge's stored accepted output on every stored input
(trailing blank lines and trailing spaces ignored) on three runs: the lane's grading run and two confirmation runs
under fixed hash seeds 0 and 4242. That is the whole claim. It is not a proof against the statement, and an online
judge's hidden cases and time limit stay beyond a local check; `max_case_s` in the evidence is the number to hold
against a time limit.

The bank: 7,682 problems. UVa 3,407, all with statements, 3,401 with a stored output (train 3,008, held-out 378;
2,793 with inputs <= 200 KB). The other judges hold 4,275 problems, of which only FBHC 86, GCJ 233, LOJ 414 and
Toph 73 carry a statement; URI 1,851, LA 880, SPOJ 312, DS 274 and CATS 43 carry none, so nothing can be written
for them until their statements are collected. The first target is every UVa problem with a stored output.

State at registration (05:30Z): 946 UVa problems hold an accepted sample across the lanes (2,457 tried: the train
problems with inputs <= 200 KB). Lanes running: DeepSeek-V3.2 at k = 1 over the 1,516 train problems Qwen3-235B
missed, Qwen3-Next over all 2,421. Best status among the tried-and-unsolved: 909 wrong answer, 266 crash,
162 timeout, 174 no fence.

## Instruments

- `t/udebug_export.py`: re-judges every accepted program under two seeds with per-case timing, writes
  `t/out/udebug-solutions/<judge>/<id>.py` + `.json`, `INDEX.jsonl`, `SOLVED.md`, `UNSOLVED.md`.
- `t/udebug_teacher.py --repair-from DIRS`: prompts only the problems refused in those lanes and accepted in none,
  with the judge's refusal (case, first difference, the input head, the expected output around the difference) and
  the refused program quoted.
- `t/udebug_gate.py`: unchanged judgement; now records `max_case_s` and accepts an environment.

## Predictions

- **X1 (confirmation).** Of the accepted samples, at least 98% reproduce every case again under both seeds. The
  ones that do not are programs whose output depends on set/dict order of strings, or whose running time sits at
  the per-case budget. Fewer than 98%: the lanes' grading run was not the deterministic reading it was taken for.
- **X2 (repair, DeepSeek).** One repair round with DeepSeek-V3.2 over problems refused by every lane accepts
  between 25% and 45% of the wrong-answer refusals, between 15% and 35% of the crashes, and under 20% of the
  timeouts. Below 25% on wrong answers: the quoted feedback is not the lever Chen et al. measured on this kind of
  problem, and the next lever is more samples at temperature, not more rounds.
- **X3 (repair, Qwen3-Next).** The same round with Qwen3-Next lands at least 10 points below DeepSeek on the same
  problems.
- **X4 (time limit).** At least 90% of confirmed solutions run every stored case under 2 s on this laptop; the ones
  above are the candidates for a faster rewrite before submission.
- **X5 (coverage after two repair rounds and the running lanes).** At least 60% of the 3,401 UVa problems with a
  stored output are solved by 2026-10-16. Below 50%: the remaining problems need a different teacher or hand work,
  and the plan says so instead of a third round.

## Reads

(appended as they land)
