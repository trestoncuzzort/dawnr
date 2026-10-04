# A teacher round on our own cards: the prompted Qwen3.5-27B over every training prompt; registered before any sample

Registered 2026-10-04 17:17Z. Section 3's curve measured the prompted Qwen3.5-27B (Apache-2.0) on the clean 200 at 43
problems proved by at least one kernel and 29 by all seven with 17 answers a problem (`t/PREDICT-2026-10-04-size-curve.md`):
the strongest model measured on our own hardware, served by vLLM 0.29 on one of the lab's 48 GB cards (fp8 weights)
at about 60 answers a minute. Every document the student has learned from so far that a teacher wrote came through
Amazon Bedrock. This round asks the same prompts of the 27B on our own cards, at no cost, as the stage sweep's first
item asked of a 27B teacher before any card could run one (`internal/RESEARCH-2026-09-30-stage-sweep.md`).

## The run

The lab's GPUs 1 to 3 as the teacher3 student round frees them, one vLLM server a card (the size curve's settings:
fp8, `--max-num-seqs 128`, the model's own sampling turned off for vLLM's, thinking off), the Bedrock rounds'
settings exactly: k = 8 (seeds 1 to 8), temperature 0.7, budgets 6,144 tokens for a problem and 4,096 for a
specification prompt, `spec_experiment generate --pool v5 --prompt v5` on the 2,521 training-side ids rounds 1 to 3
asked (356 MBPP and HumanEval, 2,165 APPS) and `rl_teacher_expert_iter.py sample-spec` on the 442 specification
prompts. Scored as the Bedrock rounds were (`rl_feasibility.py score`, `score-spec`), and the top-tier answers
assembled in all seven kernels (on the lab this time), admitting six or seven.

## Predictions

The 27B proved 21.5% of the clean 200 at one kernel with 17 answers; DeepSeek-V3.2 reached the top tier on 20% of the
356 MBPP and HumanEval training problems and 11% of the 2,165 APPS problems at k = 8.

- **B1.** At least 150 of the 2,521 training problems reach the top tier (tests, the specification check, a Dafny proof).
- **B2.** At least 70 training documents are admitted in six or seven kernels.
- **B3.** At least 120 of the 441 distinct specification prompts are proved (Qwen3-235B 174, DeepSeek-V3.2 206).

If B2 holds, the admitted documents join the pool for the next registered student round, beside every earlier
round's.
