# The remaining APPS training problems through DeepSeek-V3.2 on Bedrock: registered before any sample

The two Bedrock rounds asked every specification the lifter expresses today and 356 training problems
(`t/PREDICT-2026-10-03-teacher-round-bedrock.md`, `t/PREDICT-2026-10-04-teacher-round2-deepseek.md`). The training
side the RL prompt rule allows holds 2,597 problems: the 356 asked, 76 MBPP/HumanEval ones the staging left out
because the corpus already answers them, and **2,165 APPS problems never asked**. On the 60 APPS problems the rounds
did ask, DeepSeek-V3.2 reached the top tier on 5 and Qwen3-235B on 1, and DeepSeek admitted 28 of its 70 top-tier
training answers in six or seven kernels. "More proved data each round" is a goal of its own (AMBITION.md), so this
round runs whatever the student round on round 1's documents shows.

## The run

DeepSeek-V3.2 (MIT), the round-2 settings exactly (k = 8, temperature 0.7, seeds 1 to 8, budget 6144, `spec_experiment
generate --pool v5 --prompt v5`), on the 2,165 ids (`~/scratch/bedrock/round3-apps-ids.txt`: `rl_reward.rl_prompt_ids`
minus the 356, APPS only), through the same capped proxy on the flex tier. Bedrock allows this model 100 requests a
minute, so the round takes about three hours. Scored with `rl_feasibility.py score` proving on the lab, and the
top-tier answers assembled in all seven kernels as before. The proxy's cap stays $60 for all Bedrock rounds ($13.16
spent before this one).

## Predictions

The 60 asked are a small sample (5 of 60 is 3% to 18% at 95%), so the bars sit near its lower end.

- **A1.** At least 90 of the 2,165 reach the top tier (tests, the specification check, a Dafny proof).
- **A2.** At least 35 are admitted in six or seven kernels.
- **A3.** The round spends at most $30 by the ledger.

If A2 holds, the admitted documents join the pool for the next registered student round, beside rounds 1 and 2's and
the specification round's.
