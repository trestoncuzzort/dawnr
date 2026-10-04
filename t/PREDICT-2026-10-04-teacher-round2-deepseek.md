# A second teacher on the same prompts (DeepSeek-V3.2 on Bedrock): registered before any sample

Registered 2026-10-04 01:27Z (commit 64a5fe9e; its first sample 01:27:22Z). The first Bedrock round (`t/PREDICT-2026-10-03-teacher-round-bedrock.md`) asked
Qwen3-235B-A22B-2507, the pilot rule's choice on cost per proved item; DeepSeek-V3.2 proved the most pilot items
(15 of 80 against 12). Given a specification, the first round proved 174 of the 441 distinct prompts; from a problem
statement alone, 40 of 356. Every specification the lifter can express today has now been asked, and the APPS
problems left prove at about 2% (1 of 60), so the cheapest way to more documents with today's t is a second
teacher on the same prompts: different models fail on different problems. This round measures that.

## The run

The same proxy, cap and flex tier (the $60 cap covers both rounds; $3.98 spent before this one), the same prompts
(the 356 training ids, the 441 distinct specification prompts of the lab's staged file), the same settings
(k = 8, temperature 0.7, seeds 1 to 8, token budgets 6144 and 4096), teacher `deepseek.v3.2` (MIT). Scored and
assembled exactly as the first round, after it, on this machine.

## Predictions

- **U1.** DeepSeek-V3.2 proves at least 150 of the 441 specification prompts (one sample at the top tier).
- **U2.** The two teachers together prove at least 210 of the 441 (the first round's 174 plus at least 36).
- **U3.** From problem statements, the two together reach the top tier on at least 55 of the 356 (40 plus 15).
- **U4.** The round spends at most $12 by the ledger.

If the two teachers' admitted documents together exceed the first round's by at least 50, a student round on the
union is registered separately; otherwise the first round's documents stand alone.

## U1 to U4, 2026-10-04 04:08Z (`~/scratch/bedrock/round2/`, the score caches of both rounds)

DeepSeek-V3.2, k = 8, 6,384 requests on the flex tier, $9.18 by the ledger.

| | Qwen3-235B (round 1) | DeepSeek-V3.2 (round 2) | the two together | new from DeepSeek |
|---|---:|---:|---:|---:|
| specification prompts proved (441) | 174 | 206 | 215 | 41 |
| training problems at the top tier (356) | 40 | 70 | 79 | 39 |
| training problems passing their tests (356) | 151 | 173 | | |

- **U1 holds:** 206 against 150.
- **U2 holds:** 215 against 210; the two teachers prove mostly the same specifications (165 in common).
- **U3 holds:** 79 against 55; from a problem statement DeepSeek reaches the top tier on nearly twice as many as Qwen.
- **U4 holds:** $9.18 against $12.

The decision rule (a student round on the union if the admitted documents grow by at least 50) waits for round 2's
seven-kernel assembly.

## The decision, 2026-10-04 06:25Z (`~/scratch/bedrock/round2/union.json`, `assemble-report.json`)

Round 2's seven-kernel assembly (three cells in flight): training, 70 top-tier answers graded, 19 clean in all
seven and 9 in six, 28 admitted; specifications, 113 admitted.

| admitted (six or seven kernels) | round 1 | round 2 | the two, by problem or prompt | new from round 2 |
|---|---:|---:|---:|---:|
| specification documents | 102 | 113 | 119 | 17 |
| training documents | 21 | 28 | 35 | 14 |
| all | 123 | 141 | 154 | 31 |

Counted by problem or prompt, as U2 and U3 count the union, the two rounds together admit 31 more than round 1, not
the 50 the rule asks: **no student round on the union is registered by this rule**, and round 1's documents stand
alone in `t/PREDICT-2026-10-04-teacher1-student.md`. Counted as distinct programs instead (two teachers' different
proofs of one prompt are two documents), the two rounds hold about 225 (180 specification documents), which would
have passed; the rule was written beside unions by problem, so that reading is taken, and the larger count is
recorded rather than used. Whether more documents of this kind are worth a round is left to the student round's
result.
