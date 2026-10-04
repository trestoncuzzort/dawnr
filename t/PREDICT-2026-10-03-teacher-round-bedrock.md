# The teacher round on Amazon Bedrock: registered before any sample is drawn

Registered 2026-10-03 23:25Z (commit dce1e288; the pilot's first sample 23:26:05Z). `t/PREDICT-2026-10-01-dawnr-teacher-round.md` staged this round for a
27B teacher on a rented GPU and was stopped before it measured anything; its stop note says a round
elsewhere is a new registration with its own predictions. This is that registration. The reason is
unchanged and sharper: the student is proved correct on 15 to 18 of the clean 200, Section 1 of
AMBITION.md is not met, and every measurement since 2026-09-30 says the proved corpus, not the
recipe, is what limits it. A teacher supplies candidates; the seven provers decide what is kept.

## Where it runs and what it may spend

- **Account.** The operator's AWS account is on the Free plan with $200.00 of credit
  (`aws freetier get-account-plan-state`, read 2026-10-03 23:10Z). Usage draws on the credit and
  no card is charged; at $0 the account is suspended (AWS Free Tier FAQ). The round may spend at
  most **$60**, pilot included. `locallm/bedrock_proxy.py` enforces it: every request passes through
  it, it prices each reply from the token counts Bedrock returns and the AWS Price List's flex-tier
  rates, refuses any request that could carry the total past the cap, and writes a ledger. The
  credit balance AWS reports is read before and after; that figure, not the ledger, is the result.
- **Endpoint.** Bedrock's OpenAI-compatible `bedrock-mantle` chat completions, flex service tier
  (half the standard rate, measured to answer for every candidate below). Short-term Bedrock API
  keys minted from the operator's login by the proxy; the key never leaves this machine. The
  pipeline's own client (`t/spec_experiment.py chat`, `--api openai`) talks to the proxy unchanged.

## The teachers, and how one is chosen

Five open-weight models that answered on 2026-10-03, each under a licence that lets their output
train an Apache-2.0 model (read from each model card): `openai.gpt-oss-120b` (Apache-2.0),
`qwen.qwen3-235b-a22b-2507` (Apache-2.0), `qwen.qwen3-coder-next` (Apache-2.0), `deepseek.v3.2`
(MIT), `zai.glm-5` (MIT). Not candidates: closed models (their terms forbid training on their
output), Llama and Gemma (licences that restrict it), Qwen3-Coder-480B (did not answer in two tries).

**Pilot.** 40 of the 356 training ids and 40 of the 442 gated specification prompts (the first 40
of each after `random.Random(2026).shuffle`), one sample each, temperature 0.7, seed 1. Token
budgets 6144 for training prompts and 4096 for specification prompts, above the 27B round's 3072
and 1024 because three candidates reason before they answer and the budget covers both. Scored
exactly as the round is: training answers by `rl_teacher_expert_iter.py consolidate-training` and
`rl_feasibility.py score`, specification answers by `rl_teacher_expert_iter.py score-spec`; the top
tier is `proved` in both.

**Rule, fixed now.** Count the pilot items (of 80) with a `proved` sample. Among the candidates whose
count is at least 80% of the best count, the lowest dollars per proved item (the proxy's ledger)
is the teacher; a tie goes to the higher count. If no candidate proves anything, the round stops
and is reported, not re-tried with another prompt.

## The round

The chosen teacher, k samples at temperature 0.7 (seeds 1 to k) on all 356 training ids
(`spec_experiment.py generate --pool v5 --prompt v5`) and all 442 gated specification prompts
(`rl_teacher_expert_iter.py sample-spec`), the pilot's token budgets. k = 8, unless the pilot's
measured cost per item projects the round past $55; then the largest k that fits. Then
`rl_teacher_expert_iter.py assemble`: every top-tier answer is re-graded in all seven kernels with
the twin gate and the corrected specification check, and what passes becomes candidate documents
(`t/out/spec-experiment/rl-teacher-verified`) and enters the student's graded pool at its level.

## Predictions

No measurement of these teachers on t exists; the numbers are the 27B round's (100, 60, 40, 50)
raised by about half for a stronger teacher, so they can fail.

- **T1.** At least 150 of the 356 training problems get a sample that passes the problem's own
  tests. Falsified below 150.
- **T2.** At least 80 of the 356 get a sample at the top tier (tests, the specification check and
  a Dafny proof). Falsified below 80.
- **T3.** At least 60 of the 442 specification prompts get a sample at the top tier (Dafny proves
  it against the given specification, unchanged). Falsified below 60.
- **T4.** The assembled set adds at least 80 documents clean in all seven kernels. Falsified
  below 80.
- **T5.** The round spends at most $55 by the ledger, and the credit AWS reports afterwards is at
  least $140. Falsified otherwise.

## What each outcome decides

- T2 and T4 hold: the new documents join the student's pool, and a student round on it is
  registered separately and measured on the clean 200 with the Section 1 instrument.
- T1 holds and T4 fails: the teacher solves problems but a gate rejects its specifications; the
  loss is reported gate by gate before anything else is tried.
- T1 fails: the prompt or the grammar is the problem, not the teacher; inspected before any second
  round.

## What it cannot show

The teachers have read the public MBPP and HumanEval, so some answers are recall. The held-out 232
are never prompted (the ids come from `rl_reward.rl_prompt_ids` with the held-out, dev and
decontamination exclusions), the clean-200 gate stays where it is, and a document is admitted for
being proved, not for being novel. The 27B round's 74 specification sample files on the lab are a
different teacher's and are not mixed into this round.

## Pilot outcome, 2026-10-03 23:38Z (commit 0f1b1d89; the rule applied, the round not yet run)

One sample each on the 40 training ids and 40 specification prompts; spend by the proxy's ledger.

| teacher | training: tests | training: proved | spec: proved | proved of 80 | spend | per proved |
|---|---|---|---|---|---|---|
| openai.gpt-oss-120b | 13 | 3 | 6 | 9 | $0.071 | $0.0079 |
| qwen.qwen3-235b-a22b-2507 | 11 | 2 | 10 | 12 | $0.044 | $0.0037 |
| qwen.qwen3-coder-next | 9 | 0 | 9 | 9 | $0.092 | $0.0102 |
| deepseek.v3.2 | 13 | 1 | 14 | 15 | $0.115 | $0.0077 |
| zai.glm-5 | 14 | 4 | 7 | 11 | $0.188 | $0.0170 |

The best count is 15 (DeepSeek-V3.2); within 80% of it are DeepSeek-V3.2 and Qwen3-235B-A22B-2507, and the
lower cost per proved item is Qwen3-235B's: **the teacher is `qwen.qwen3-235b-a22b-2507`**. Its measured cost,
about $0.00055 a sample, projects the round (798 prompts, k = 8) to about $3.50, so k = 8 as registered.

gpt-oss-120b spent its whole budget reasoning on 3 of 80 replies and Bedrock returned no content; the client
handed on None and the scorers stopped (fixed in 0116e4b0: an absent answer is an empty one), and those three were
scored as empty answers. Every teacher proves far more given a specification (6 to 14 of 40) than from a problem
statement alone (0 to 4 of 40), where the specification check and the proof both have to come out right.

## Outcome, 2026-10-04 03:18Z (`~/scratch/bedrock/round/assemble-report.json`, `~/scratch/bedrock/log`)

Qwen3-235B-A22B-2507, k = 8, 6,384 requests through the proxy, every one answered on the flex tier: $3.47 by the
ledger (22.4M tokens in, 2.3M out). The staged specification file holds 442 lines but 441 distinct prompts (DH0141
twice), so the specification pool is 441.

| | asked | tests pass | top tier | graded in seven kernels | clean in all seven | clean in six | admitted |
|---|---:|---:|---:|---:|---:|---:|---:|
| training problems | 356 | 151 | 40 | 40 | 10 | 11 | 21 |
| specification prompts | 441 | | 174 | 174 | 79 | 23 | 102 |

- **T1 holds:** 151 of 356, at the line (150).
- **T2 falsified:** 40 of 356, not at least 80.
- **T3 holds:** 174 of 441, almost three times the 60.
- **T4 holds:** 89 documents clean in all seven (10 and 79), against 80.
- **T5:** the ledger reads $3.47, inside $55; the credit AWS reports is read again once its billing catches up
  (it still reads $200.00 at 03:18Z), and the second half is judged on that figure.

**Reading.** Given a specification the teacher proves 39% of prompts and most of those proofs hold in every
kernel (79 of 174); from a problem statement it reaches the top tier on 11%, and four of five of those fail some
other kernel. Writing the specification, not the proof, is where answers from a statement die, as it is for the
student. 123 documents were admitted (six or seven kernels) and go to the registered student round
(`t/PREDICT-2026-10-04-teacher1-student.md`).

**Two things that went wrong on the way, both fixed.** The reward scorer stopped on 7 problems whose own test
points mix output kinds (146c38ff). The first seven-kernel assembly ran eight cells at once (about 48 provers on a
15 GB machine), was killed whole under memory pressure with nothing logged, and ran again with three; the prover
cache kept the finished cells, including any timeout recorded while the machine was overloaded. A timeout never
admits a document, so the error can only have kept out documents, not let any in; the documents near the line
are re-graded without the cache after the student's rows are built, and any that change are reported.
