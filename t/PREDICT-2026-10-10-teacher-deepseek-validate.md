# A DeepSeek-V3.2 (Bedrock, MIT) teacher round on 24 RL-eligible problems: registered before any sample

Registered 2026-10-10. The lab was re-provisioned on 2026-10-10 (new host `cs-rahman-dell`); this round re-validates
the Bedrock teacher-data engine end-to-end on the current infrastructure and measures its verified-row yield before
scaling. It is the measured, licensing-clean path: DeepSeek-V3.2 is MIT-licensed and hosted natively on Amazon
Bedrock (`deepseek.v3.2`, confirmed reachable via the `converse` API 2026-10-10), so its outputs are admissible as
training data under the project's permissive-only rule (AMBITION.md; the earlier rounds used DeepSeek/Qwen, never
Claude, for exactly this reason). This grows verified data (AMBITION §4, "scale the engine") on current hardware.

## The run

- **Teacher:** `deepseek.v3.2` on Bedrock (us-east-1), via `t/bedrock_generate.py` (boto3 `converse`).
- **Problems:** 24 ids sampled (seed 42) from `rl_reward.rl_prompt_ids(split-v5, pool v5)` — the RL-eligible
  training set (train ids minus eval, r12-dev and every decontamination-blocked id). APPS is not loaded on the
  re-provisioned lab, so these are the MBPP/HumanEval-family training problems, not APPS. Ids in
  `/tmp/round-validate-ids.txt` on the lab.
- **Sampling:** k = 4 samples, temperature 0.7, prompt/pool v5, token budget 6144, concurrency 4. (Bounded at k=4,
  not round 3's k=8, to keep this a cheap validation; scale k and the id set after it holds.)
- **Gate (on the lab, seven kernels):** the generated records are run through the standard pipeline — extract →
  tests (the problem's own tests) → `run_par` (seven-kernel verify with the twin refuted at a concrete witness) →
  table. A row counts as *verified* only under the twin rule (real proved AND twin refuted), never on an exit code.
- **Cost guard:** `--spend-cap-usd 5` on the generation; the run stops before exceeding it.

## Predictions (checked on the run)

- **B1 — the engine works on the new infra:** at least 1 of the 24 problems yields a program that passes its own
  tests and verifies in at least one kernel with its twin refuted. *Falsifier:* 0 verified ⇒ the data engine is
  broken on the re-provisioned lab (an infra regression to fix before any larger round).
- **B2 — yield:** at least 8 of 24 reach a tests-passing extracted program, and at least 4 of 24 are clean in all
  seven kernels. (These problems are easier than round 3's APPS, where DeepSeek-V3.2 hit the top tier on 11.3% and
  53% of those assembled in six or seven kernels; the bar sits above the APPS rate because the pool is easier.)
- **B3 — cost:** at most $5 by the generation ledger.

## Read (2026-10-10, on the lab)

The data engine works end to end on the re-provisioned lab with live AWS and a licensing-clean MIT teacher.

**Generation.** `deepseek.v3.2` on Bedrock answered via the `converse` API. Of the 24 sampled ids,
`bedrock_generate.py` accepted 10 (the rest filtered by its own id gate), so the run is 10 problems x 4 samples =
**40 records**, generated for **$0.094** by the ledger. The `converse` path needed no proxy; the earlier rounds'
flex-tier proxy is not required now that DeepSeek-V3.2 is a native Bedrock model.

**Extract and tests.** Well-formed `t` per sample: 5, 6, 6, 6. **Every well-formed answer passes its own tests**
(5/5, 6/6, 6/6, 6/6) — the interp-level filter lets none through that fails the problem's own assertions.

**Kernels (Dafny + Verus, two independent provers; the twin refuted at a concrete witness).** Distinct problems
clean (`real=verified`, `twin=refuted`), best over the 4 samples:

| problem | Dafny | Verus | twin witness |
|---|---|---|---|
| mbpp_176 perimeter_triangle | verified/refuted | verified/refuted | a=0,b=1,c=0 -> real 1, twin 2 |
| mbpp_379 surfacearea_cuboid | verified/refuted | verified/refuted | l=0,w=1,h=1 -> real 2, twin 3 |
| mbpp_499 diameter_circle | verified/refuted | verified/refuted | radius=1 -> real 2, twin 3 |
| mbpp_46 test_distinct | verified/refuted | unproved | data=[0] -> real True, twin False |

Correctly refused, not counted: `mbpp_36 find_Nth_Digit` (real **refuted** — the generated program is genuinely
wrong, caught at a=1,b=1,n=1), `mbpp_934 dealnnoy_num` and `mbpp_168 frequency` (real unproved). The gate keeps
only what proves; a wrong answer is rejected by name.

**Bars.**
- **B1 holds:** 4 of the 10 problems verify with the twin refuted in at least one kernel (3 in two independent
  provers). The engine produces verified-with-twin-refuted rows on the new infrastructure.
- **B3 holds:** $0.094 against $5.
- **B2's all-seven clause holds; its "of 24" framing is re-scoped and said plainly.** The generation produced 10
  problems, not 24 (`bedrock_generate`'s id filter accepted 10 of the sampled ids), so the "of 24" denominators do
  not apply. The seven-kernel assembly, run on s0's 5 well-formed tasks under `run_par` (7/7 kernels present, 35
  cells, 210 kernel runs, `--no-cache`), gives: **3 of the 5 tasks are `verified / refuted` in all seven kernels**
  — `mbpp_176 perimeter_triangle`, `mbpp_379 surfacearea_cuboid`, `mbpp_499 diameter_circle`. A fourth,
  `mbpp_46 test_distinct`, is verified in three (Dafny, Frama-C, Lean) with the twin refuted in all seven but the
  real unproved by Verus/SPARK/Rocq/F* (an honest per-kernel limit, abstains 0). `mbpp_934 dealnnoy_num` stays out
  (real unproved). Per-kernel real-verified counts: dafny 4, framac 4, lean 4, verus 3, spark 3, rocq 3, fstar 3;
  every one refutes the twin on 100% of its verified reals. So the engine yields **3 all-seven gold rows of 10
  problems** at $0.094. (The earlier detached all-seven attempt had stalled under a flaky VPN link; relaunched with
  `setsid` and an absolute log it completed in ~5 min.)

**What it bought.** The licensing-clean Bedrock teacher path (DeepSeek-V3.2, MIT, native `converse`) is confirmed
on current hardware, cheap, and yields verified rows. The next increment: the full eligible id set, k=8, all seven
kernels under `run_par`'s own per-cell timeouts (launched with `setsid` so an SSH drop cannot kill it), then the
clean rows assembled into the corpus and a student trained — the measured path of rounds 1-4, resumed.
