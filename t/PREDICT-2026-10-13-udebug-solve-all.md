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

**Pilot read, 06:06Z (six wrong-answer problems, DeepSeek-V3.2 on dawnr-core-2026, repair prompt, 6,144-token
replies):** 1 of 6 accepted (UVa 116). Of the five refused: two replies ran to the token limit while deliberating
(one of them with no fence at all); three answered with a different wrong program, two of them failing at a
later case or line than before and one at an earlier case that the previous program had passed. The feedback is
read, not ignored, and deliberation is the cost: repair rounds now ask for reasoning under 300 words and allow
16,384 reply tokens. Six is too few to read X2; the rounds read it.

**Infrastructure read, 05:56Z:** the school-account credential behind the cs-project endpoints stopped
refreshing (`invalid_grant`, `invalid_rapt`) and both scale lanes on it crashed. All lanes moved to
dawnr-core-2026 with the jonhh credential, which also carries Qwen3-Next. Also found: 36% of Qwen3-Next replies
and 17% of DeepSeek replies were cut at 4,096 tokens before their fence (the "no fence" refusals); the lanes were
relaunched with 8,192, and the no-fence problems are prompted afresh by the rounds rather than repaired.

**X1 and X4 read, 06:44Z (first confirmation pass, `udebug-export-1`):** 965 of 965 accepted programs reproduce
every stored case again under both seeds: X1 holds at 100%. 870 of 965 (90.2%) run every stored case under 2 s:
X4 holds, barely. 95 are slower, 46 of them over 10 s (the slowest 116 s): correct by the judge, refused for time
by any online judge. A speed round hands each slow solution back for a faster one (`--slow-index`, `speed_text`);
the export keeps the fastest confirmed sample per problem.

**Speed round read, 07:12Z (Qwen3-Next, 95 slow solutions, 12,288-token replies):** 60 of 95 rewrites still
reproduce every stored case; 48 of those are faster than the program on record and 27 now run every case within
2 s. The export now sorts a problem's accepted samples fastest first and re-confirms a solved problem whenever a
faster accepted sample appears, so the bundle keeps the fastest confirmed program. 68 remain over 2 s for a
DeepSeek speed round later.

**Early repair read, 07:50Z (Qwen3-Next, first 83 of round 1):** 9 accepted (10.8%; 11.5% of the 78 with a
fence), 50 wrong answer, 12 crash, 7 timeout, 5 no fence. Consistent with X3 (Qwen3-Next at least 10 points under
DeepSeek) only if DeepSeek's round lands above 21%; X2's read waits for the DeepSeek drivers. Scheduling note: the
Qwen sweep and the Qwen repair lane shared one request limit and both collapsed under backoff; the repair driver
now waits for the sweep.

**OpenAI read, 10:44Z (repair prompts over the 934 problems every open-weight lane had refused; priority tier):**
gpt-6-astra 35 of 48 accepted, gpt-6.1-sol 33 of 47, gpt-5.5 19 of 31, gpt-5.4 15 of 36, gpt-6-luna 12 of 48,
against the open-weight repair rounds on the same set (DeepSeek 42 of 272 across its shards, Qwen3-Coder 18 of
267, GLM-5 7 of 93, Qwen3-Next 109 of 589). X2 (DeepSeek repair 25 to 45% on wrong answers) reads BELOW its floor
at 15%; the frontier models clear it by a wide margin. Spend per problem: Astra about $0.48, Sol $0.08, gpt-5.5
$1.10, gpt-5.4 $0.53, Luna under $0.01; gpt-5.5 and gpt-5.4 were stopped as dominated. Bundle 1,622 solved.
