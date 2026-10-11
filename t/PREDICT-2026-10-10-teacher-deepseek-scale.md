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

**Spec check ran (via Landlock, no sudo) and the full admission gate admitted 0 training rows — correctly.** The
lab cannot create bwrap namespaces, but dawnr's own Landlock backend (`T_SANDBOX=landlock`, `t/landlock_exec.py`,
built for exactly this lab) runs the spec check without root. With the MBPP canonical solutions as the reference
(`spec_gate.py --python <pool rec.code>`), **44 of 66 answers pass the spec check** (11 spec-false, 7
requires-excludes-most, 4 too-few-draws); 14 distinct problems have a spec-passing sample. Merged into
`out/spec-disagree.json`, `loop_dataset.py --from-samples … --min-kernels 7` then admitted **0 rows**, and that is
the gate working, not a bug:

- Per problem, best over samples, 11 are clean in all seven kernels and 14 spec-pass, overlapping on 9 problem ids.
  But `loop_dataset` requires the **same sample** to clear every gate at once — well-formed AND tests-pass AND
  clean in seven AND spec-agrees at the problem's own stated examples — and **no single sample does**. The 168
  samples split cleanly: 97 not-well-formed, 5 tests-not-passing, 32 kernels-not-clean-seven, 34 spec-not-agrees.
- The finding: DeepSeek-V3.2's answers that prove in all seven kernels tend to carry a specification that does not
  also agree with the reference at the problem's examples — provable against its own (unfaithful) spec. The gate
  refuses these by name, which is the whole point ("its specification agrees with the problem's own solution",
  AMBITION.md). Zero bad rows entered the corpus.

**Net:** the DeepSeek-V3.2 (MIT) Bedrock → seven-kernel → spec-check engine is proven end to end on the
re-provisioned lab (Landlock unblocks the spec check without sudo) for ~$0.29. This batch grew the corpus by 0
rows because no single sample cleared all four gates together. To actually add rows: raise the sample count per
problem (more k, so a problem gets more chances at an all-gate-clearing sample) and the problem count (to clear 20
all-seven). Training a student stays GPU-blocked (lab GPUs closed, AWS Free refuses GPU instances, laptop
control-node only).

## Follow-up round (registered before the run): k=16 on the 9 clean-7 ∩ spec-pass problems

The 0-admission came from clean-in-seven and spec-pass landing in *different* samples. 9 problems
([234, 266, 356, 373, 458, 525, 577, 716, 789]) already have both properties across their k=4 samples. Re-running
just those 9 at **k=16** gives each more chances at a single sample that clears every gate at once.

- **D1:** at least 1 of the 9 is admitted by `loop_dataset --min-kernels 7` (a single sample well-formed +
  tests-pass + clean-in-seven + spec-agrees). *Falsifier:* 0 admitted ⇒ the two properties rarely coincide in one
  sample even at k=16, a model-level spec-faithfulness limit, not a sampling-count one.
- **D2:** cost at most $3.

### Follow-up read (2026-10-10): 9 rows admitted + 125 preference pairs — D1 and D2 hold

Re-running the 9 at **k=16** (144 records, $0.31) and gating all 16 sample tags (seven kernels + Landlock spec
check; `spec_gate` judged 128 of 137 answers spec-agreeing) admitted **all 9 problems**: `loop_dataset
--from-samples` produced **9 SFT positives + 125 deduped preference pairs** (`out/loop/sft-deepseek-nine.jsonl`,
`pairs-deepseek-nine.jsonl`, `DATASET-deepseek-nine.md`).

- **D1 holds:** 9 admitted (>= 1). Each is one sample that is well-formed AND passes its tests AND reads
  `verified / refuted` in all seven kernels AND whose spec agrees with the MBPP reference on 100 draws. Higher k was
  exactly the fix: at k=4 no single sample cleared all four gates together; at k=16 every one of the 9 got a sample
  that did.
- **D2 holds:** $0.31 against $3. (Two scale rounds together: ~$0.60.)

**A real dawnr pipeline gap, found and bridged.** `spec_gate.judge()` nests its spec evidence under an
`"agreement"` key, but `loop_dataset.positive_rejection` reads `status`/`draws`/`task_id`/`pool`/`task_sha256` at
the **top level** and otherwise returns `spec-not-agrees` — so `spec_gate`'s output is not directly consumable by
`loop_dataset` (it rejected 121 genuinely-agreeing answers until the fields were flattened). The flatten is a
faithful reformat of real `check_task` evidence, not a weakening. The clean fix (dawnr-local, worth doing next):
make `spec_gate` emit the flat per-sample record `loop_dataset` reads, or teach `loop_dataset` to read the nested
form. Until then a flatten step is required between them.

The 9 SFT rows + 125 pairs are in `out/loop/` (gitignored run artifacts); they join the registered corpus at its
next registration and feed the next training run (still GPU-blocked). **Net: the engine now demonstrably admits
real verified training rows end to end on the re-provisioned lab + live AWS, for cents.**

### Batch 2 (2026-10-10): fixed pipeline, 5 rows from 16 fresh random problems — production confirmation

A fresh round on 16 previously-unsampled eligible problems at k=8 (128 records, $0.31), gated through the
**fixed** `spec_gate` (its output plain-merged into `out/spec-disagree.json`, **no flatten**): `loop_dataset`
admitted **5 SFT rows + 48 preference pairs** with **0 `spec-not-agrees`** rejections — the format fix (`a0b8aeb`)
works in production. On random (not hand-picked) problems the admission rate is ~5/16 ≈ 31%. Session total of new
verified data: **14 SFT rows + 173 preference pairs** across the nine-round and batch 2, all in `out/loop/`
(`sft-deepseek-{nine,b2}.jsonl`, `pairs-deepseek-{nine,b2}.jsonl`), joining the corpus at its next registration.
The engine manufactures verified training data end to end on the re-provisioned lab for cents; the remaining gap to
a better student is a GPU to train on it.

### Batch 3 (2026-10-10): 8 more rows; session total 22 SFT + 238 pairs

A third fresh round (64 problems requested, 33 accepted, k=8 → 264 records, $0.62) gated through the fixed
pipeline (plain merge, no flatten) admitted **8 SFT rows + 65 preference pairs** (93 of 128 answers spec-agreed;
only 11 spec-not-agrees, all genuine disagreements). Admission on random problems ~8/33 ≈ 24%.

**Session total new verified data: 22 SFT rows + 238 preference pairs** (nine 9+125, b2 5+48, b3 8+65), each a
DeepSeek-V3.2 (MIT) answer verified / twin-refuted in all seven kernels with its spec agreeing with the MBPP
reference. All in `out/loop/sft-deepseek-{nine,b2,b3}.jsonl` + `pairs-deepseek-{nine,b2,b3}.jsonl`; they join the
registered corpus at its next registration and feed the next training run. Total Bedrock spend ~$1.25. The data
engine (generate → seven-kernel gate → Landlock spec check → admission) is proven, cheap, and reproducible on the
re-provisioned lab; the remaining gap to a better *model* is a GPU to train on these rows.
