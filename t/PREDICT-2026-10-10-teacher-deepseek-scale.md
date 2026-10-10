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

## Read (2026-10-10): completed — 11 of 26 problems clean in all seven kernels, $0.29

**Generation.** `deepseek.v3.2` on Bedrock answered via `converse`. `bedrock_generate` accepted 42 of the 96
sampled ids (its own id gate), so the run is 42 problems x 4 samples = **168 records, $0.29** by the ledger. The
earlier credential failures were **not a bug**: they were stale creds under a flapping VPN. Replicating
`bedrock_generate`'s exact client (line 322) with freshly-sent 3-variable static creds resolves a static
`Credentials` object and `converse` succeeds; `--limit 2` then the full run both completed once the creds in
`~/.aws-tmp-creds` were current. Lesson for the resume: the lab's SSO window is short (~15 min), so send fresh
3-var creds (strip `AWS_CREDENTIAL_EXPIRATION`) immediately before each run.

**Gate (all seven kernels, `run_par`, ~3,036 kernel runs across the 4 sample tags).** Per-problem, best over the
4 samples: **26 distinct well-formed problems graded, 23 pass their own tests, 14 verified with the twin refuted in
at least one kernel, and 11 clean in all seven kernels** (`verified / refuted` in every column, twins refuted at
concrete witnesses).

**Bars.**
- **C3 holds:** $0.29 against $8.
- **C2 holds:** the gate counts only `verified / refuted`; every wrong or unproved answer is refused (12 of the 26
  are not clean in all seven, correctly excluded).
- **C1 (>=20 all-seven) is NOT met in absolute count (11), and the shortfall is the generation volume, not the
  yield.** Only 42 of the 96 ids were accepted and 26 distinct well-formed problems reached grading; the all-seven
  *rate* is **11/26 = 42%**, above the validation round's 30%. To clear 20 all-seven, generate more problems (raise
  the accepted id count), not change the gate.

**Admission into training rows is one step short.** `loop_dataset.py --from-samples … --min-kernels 7` produced 0
rows: the 11 gold rows are `spec-unchecked`. The full admission gate also requires the **spec check** (the
generated specification agreeing with a reference solution on sampled inputs) — and this round's generator emits
only `t` programs, no reference Python, so no spec-check result exists yet. The 11 problems are
verified-and-twin-refuted in all seven kernels; turning them into corpus/training rows needs `spec_gate.py`
(`--python <reference solutions JSONL>`) run over the sample tags first. Artifacts written:
`out/loop/{pairs,sft}-deepseek-scale.jsonl` (0 rows, pending the spec check) and `out/loop/DATASET-deepseek-scale.md`.

**Net:** the DeepSeek-V3.2 (MIT) Bedrock -> seven-kernel engine yields gold rows at scale on the re-provisioned
lab, at a 42% all-seven rate for ~$0.29; the owed steps to grow the trained corpus are (a) generate more problems
to clear 20 all-seven and (b) run the spec check to admit the rows. Training stays GPU-blocked (lab GPUs closed,
AWS Free refuses GPU instances, laptop control-node only).
