# Scale the DeepSeek-V3.2 (Bedrock, MIT) teacher round to 96 problems: registered before any sample

Registered 2026-10-10, after the validation round
([PREDICT-2026-10-10-teacher-deepseek-validate.md](PREDICT-2026-10-10-teacher-deepseek-validate.md)) confirmed the
engine end to end (3 of 10 problems clean in all seven kernels, $0.094). This round scales the generator to measure
real yield at size and add the clean rows to the verified corpus (AMBITION.md §4, "scale the engine"; §1, "data is
the limit"). Training a student on the result is deferred: no GPU is available to this session (the lab's GPUs are
closed to the account, the AWS Free plan refuses GPU instances, and the laptop is control-node only), so the
deliverable here is verified rows, not a new student.

## The run

- **Teacher:** `deepseek.v3.2` on Bedrock (us-east-1), MIT, via `t/bedrock_generate.py` (boto3 `converse`).
- **Problems:** the first 96 of `rl_reward.rl_prompt_ids(split-v5, pool v5)` (the RL-eligible training set, each
  decontamination-safe), seed-42 shuffled; ids in `/tmp/scale-ids.txt` on the lab.
- **Sampling:** k = 4, temperature 0.7, prompt/pool v5, 6144-token budget, concurrency 4, `--spend-cap-usd 10`.
- **Gate (seven kernels, on the lab):** extract → tests → `run_par` (all seven, twin refuted at a concrete
  witness), launched under `setsid` with `run_par`'s per-cell timeouts. A row counts only as `verified / refuted`.
- **Assembly:** problems clean in all seven kernels (and, recorded separately, in six with the gap named) are the
  rows this round adds.

## Predictions (checked on the run)

- **C1 — yield at size:** at least 20 of the 96 problems produce a program that is `verified / refuted` in all
  seven kernels (the validation hit 3 of 10 = 30% on an easier-looking subset; the bar sits below that at ~21% to
  allow for harder problems in the larger set). *Falsifier:* fewer than 20 all-seven ⇒ the easy-subset yield did
  not carry to size, reported plainly.
- **C2 — the gate is honest:** every problem whose generated program is wrong is refused by name (real refuted or
  unproved), never counted; no `verified / unsound` or `verified / decorative` cell is counted as agreement.
- **C3 — cost:** at most $8 by the generation ledger.

## Read (2026-10-10): not completed this session — infra blocker, reported plainly

The scale generation did **not** produce records. Two compounding blockers, neither in the engine:

1. **The lab VPN link degraded badly mid-session** and began dropping almost every multi-second SSH (exit 255),
   so each `setsid`-detached launch was cut before it could produce records, and progress could not be confirmed.
2. **`bedrock_generate.py` raised a botocore credential error** — `Credentials were refreshed, but the refreshed
   credentials are still expired` — even though an *identical* inline `converse` call, with the same static
   3-variable creds sourced the same way (`set -a; . ~/.aws-tmp-creds; set +a`), **succeeded repeatedly in the
   same minutes** (`OK 14`). So the SSO creds and the boto3 client are fine; the failure is specific to the script's
   run. `bedrock_generate.py` has no credential handling of its own (line 322 is a plain
   `boto3.client("bedrock-runtime", region_name=...)`), and the lab has no competing credential source (no AWS env
   vars, no `~/.aws`). The most likely cause, to check first on the retry: its `ThreadPoolExecutor` (concurrency 4)
   sharing one client, or the `spec_experiment` import/pool-build delaying the first call — not the creds.

**What it bought.** The data engine itself is already proven on this exact infrastructure by the validation round
([the sibling PREDICT](PREDICT-2026-10-10-teacher-deepseek-validate.md), committed): DeepSeek-V3.2 (Bedrock, MIT) →
seven-kernel gate → 3 of 10 problems clean in all seven kernels, $0.094. This scale round is deferred, not
abandoned, and resumes in one step on a stable link with fresh SSO creds:

- id set: the first 96 of `rl_reward.rl_prompt_ids(split-v5, pool v5)`, seed-42 shuffled (rebuild on the lab);
- command: `bedrock_generate.py --tag deepseek-v3.2-scale --model deepseek.v3.2 --ids-file <ids> --samples 4
  --temperature 0.7 --prompt v5 --max-tokens 6144 --concurrency 4 --spend-cap-usd 10` (try `--concurrency 1`
  first to isolate the threaded-client credential question);
- gate: `run_par` all seven under `setsid`, then assemble the clean rows.

Training a student on the result stays GPU-blocked (lab GPUs closed, AWS Free refuses GPU instances, laptop is
control-node only), so the scale round's deliverable when it runs is verified corpus rows, not a new student.
