# A second teacher on the same prompts (DeepSeek-V3.2 on Bedrock): registered before any sample

Registered 2026-10-04 01:35Z. The first Bedrock round (`t/PREDICT-2026-10-03-teacher-round-bedrock.md`) asked
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
