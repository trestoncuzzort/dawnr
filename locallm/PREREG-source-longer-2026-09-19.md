# Longer-training follow-up

The completed three-seed pilot gave modern-core held-out losses of 2.5105,
2.4570 and 2.4315, versus GPT's 3.3274, 3.3477 and 3.4103. These are token-loss
results, not executable correctness. The modern models consumed only 65,536,000
tokens each, under one token per parameter. The next intervention is more
training, with the same architecture, corpus and tokenizer.

Before launch: fix the horizon at 4000 updates (262,144,000 tokens per arm),
warmup 200 updates (the same 5% fraction), otherwise identical settings. Run
modern then GPT for each of seeds 1337, 7, 42, all from random initialization.
This is a fresh cosine schedule, not a retroactive extension of a checkpoint's
completed schedule. Keep all six old endpoints and all six new results.
Use `run_pretraining_study.py --steps 4000`; the reporter takes the same flag.
The new output directory is `t/out/source-pretraining-longer-2026-09-19`.

Predictions: all updates remain finite; each modern endpoint improves held-out
loss by at least 10% relative to its own 1000-step seed; modern retains at least
a 3% relative loss advantage over the matched 4000-step GPT control for every
seed. Failure of any seed is reported rather than replaced with a best seed.
Report extra time/tokens and any widening train/validation gap. Existing fixed
validation windows are used for model development; a later sealed executable
evaluation is still necessary before a task-quality or Phi claim.

The initial pilot also requires descriptive source-category completions. The
fixed prompts chosen after the first loss results are explicitly post hoc;
reuse them for the longer endpoints, without treating their appearance as a
registered pass rate. Use greedy decoding and 96 new tokens, without retries.

Monitoring uses the native queue of the already-open conversation, not a second
writer resuming its session. Completion/failure/stall wakes diagnosis; a healthy
run uses no model calls. Independent evidence checks run every 200 seconds.
Publish results and tested changes after a terminal event, before the next run.
