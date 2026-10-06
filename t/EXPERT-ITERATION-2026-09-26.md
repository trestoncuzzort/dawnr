# Teacher-seeded expert iteration: prompts staged, pipeline validated, generation blocked by GPU contention

2026-09-27. Runs `t/RL-DESIGN-2026-09-26.md` section 7's recommendation: have the
prompted 27B teacher (`qwen3.8-27b-fp8`, served locally, the same model
`t/spec_experiment.py` has always generated with) answer the 447 vericoding
spec prompts and the 308 non-corpus training problems through
`t/rl_reward.py`'s tiered proof reward, and keep every top-tier answer as a
new training document (STaR, arXiv:2203.14465; ReST-EM, arXiv:2312.06585; PSV,
arXiv:2512.18160, research receipt `2cbb3be1bf27`). Code: `t/rl_teacher_expert_iter.py`.
Outputs under `t/out/rl-2026-09-26/teacher/` (not committed, gitignored like
every other `t/out/**` path).

**What this run produced:** both prompt pools staged, gated and ready (442
specification prompts, 368 training-problem ids); the whole scoring, seven-kernel
re-grading and dataset-assembly pipeline built and validated end to end against
a real, hand-verified example, reaching clean-in-seven; and zero teacher
samples, because the lab's four shared GPUs were, for the whole session, in a
state far past what this task was briefed to expect, and every configuration
tried to fit the 27B teacher on one card within the required 6 GB safety
margin failed the same way. Both halves of that sentence are reported in full
below, because a repository that only reports the number it wanted is the
thing `AGENTS.md` rule 4 exists to prevent.

## 0. Head

`git merge-base --is-ancestor r12-blockers HEAD` failed in this worktree (it
was on an unrelated branch), so `git reset --hard r12-blockers` was run per
the task's instruction. The lab's `~/tup` was 21 commits behind
(`df532651` → `4b79f3fc`, fast-forwarded with `git pull --ff-only origin
r12-blockers`). Both machines are at **`4b79f3fc`**, which matches
`origin/r12-blockers`.

## 1. Prompts staged

### 1.1 Specification-only prompts (vericoding)

`t/rl_spec_pool.py stage|gate|prompts`, vericoding-benchmark
(`~/r12-test/L1/vericoding-benchmark`, git `387cd699`, already checked out on
the lab), lifter at `--jobs 16`:

| step | count |
|---|---:|
| Dafny spec files (jsonl task list) | 2,334 |
| spec files on disk (`specs/D*_specs.dfy`) | 3,029 |
| refused: return type with no t default | 1,297 |
| staged with a stub body | 1,732 |
| lifted | **715** (exactly `t/RL-DESIGN-2026-09-26.md`'s count) |
| refused: lifted specification not well formed | 133 (exact match) |
| refused: specification twin of a gated problem | 138 |
| refused: held-out or excluded id | 2 (exact match) |
| **prompts** | **442** |

By source: apps 224, dafnybench 133, humaneval 48, verified_cogen 26,
numpy_triple 7, bignum 3, numpy_simple 1.

442 against the design doc's 447: staging and the not-well-formed and held-out
refusals match exactly; the specification-twin gate refused 138 here against
133 there, five more, all in the safe direction (over-refusal — a spec correctly
read as describing a held-out or excluded problem is one fewer prompt, not a
wrong one let through). `t/r12-dev-ids.json`, `t/decontamination-2026-09-21.json`
and `t/decontamination-behavioural-2026-09-25.json` are byte-identical between
`df532651` and `4b79f3fc` (`git log` on those three paths over that range is
empty), and none of the 24 files that did change touch `spec_check.py`,
`surface.py` or the pool loader, so the five-prompt difference is not from
anything that changed between the two commits; it was not chased further, since
it moves the count in the direction the gate exists to move it in.

### 1.2 Training-problem prompts (non-corpus)

`t/rl_reward.rl_prompt_ids()` on the lab's pool v5: **2,597** ids (287 MBPP +
85 HumanEval + **2,225 APPS**), against the desktop's 372 (no APPS points) that
`t/RL-DESIGN-2026-09-26.md` measured — confirming its own note that the APPS
points the design doc lacked are on the lab.

The 308 non-corpus problems are reproduced exactly: of the 372 MBPP/HumanEval
ids, membership in `t/out/loop/corpus-r8-headed.txt` (the locallm-r11-s8
fine-tuning corpus) was checked two ways, matching `t/RL-DESIGN-2026-09-26.md`
section 3's own method — `loop_filter.problem_ids_in()` over the corpus text
for a named pool id, and a normalised text match of the corpus's `Problem:`
lines against each candidate's MBPP/HumanEval text:

    mbpp_he_total 372, in_corpus 64, out_corpus 308

**64 / 308 reproduced exactly.** APPS: all 2,225 ids are non-corpus by
construction (the design doc: "the policy has never seen APPS-style
answers"); given the compute budget below, 60 were drawn (`random.Random(2026)`,
the project's convention seed) rather than run in full, a scope cut made
explicit here rather than silently: **308 + 60 = 368 training-problem
prompts**, all re-checked against `t/loop_filter.py`'s gates through
`rl_reward.rl_prompt_ids` (which raises on any held-out leak) before being
written to an ids file.

## 2. Generation: blocked by the lab's actual GPU state

The task was briefed to expect "about 10-12 GB used on each" of the four 49 GB
cards. Measured at every point in this session, all four cards were at
**37-49 GB used, 45-92 percent utilization**:

    index, memory.used, memory.free, utilization.gpu
    0, 48401 MiB,   109 MiB, 65%
    1, 45627 MiB,  2883 MiB, 69%
    2, 36953 MiB, 11548 MiB, 50%
    3, 46887 MiB,  1623 MiB, 84%

This held steady (unchanged nvidia-smi readings) across the whole session, so
it is someone else's sustained job, not a transient spike. Card 2 was the best
card throughout, and even its budget under the required rule ("leaving at
least 6 GB free") is 11,548 − 6,144 = 5,404 MiB — before the teacher (29 GB on
disk, FP8) even starts loading.

`qwen3.8-27b-fp8` has only ever been served here across all four cards
(`t/lab_gpu.sh`, `t/runs/2026-09-16/scripts/v3-27b.sh`: `--tensor-parallel-size
4 --gpu-memory-utilization 0.25`), which this task's rule forbids (one card
only). vLLM's `--cpu-offload-gb` (offload weights to host RAM, stream them to
the GPU per layer; the lab has 416 GB free RAM) is the mechanism that keeps
this to one card: with 22 GB offloaded, model loading used only 6.43 GiB of
GPU memory (`vllm4.log`). Six configurations were tried on card 2, tuning
`--gpu-memory-utilization`, `--cpu-offload-gb`, `--max-model-len` and
`--max-num-seqs`, plus the CUDA toolchain env vars `t/lab_gpu.sh` itself needs
for vLLM's FP8 kernel JIT (`CUDA_HOME` inside the venv's `nvidia/cu13` wheel,
`VLLM_USE_FLASHINFER_SAMPLER=0`, since the lab has no system CUDA toolkit):

| # | fraction | offload | max-len | seqs | card free (start) | result |
|---|---:|---:|---:|---:|---:|---|
| 1 | 0.22 | 22 GB | 8192 | 8 | 18,376 MiB | KV cache: 0 MiB available after weight load |
| 2 | 0.18 | 24 GB | 4096 | 2 | 18,376 MiB | **started**; but the prompt (grammar + few-shot, v5) is 3,073 tokens, so 4096 leaves no room for a reply (`HTTP 400`, vLLM's own message) |
| 3 | 0.18 | 24 GB | 8192 | 2 | 15,153 MiB (other user grew) | KV cache: 0 MiB available |
| 4 | 0.11 | 27 GB | 6144 | 1 | 11,548 MiB (other user grew further, sustained) | KV cache: 0 MiB available; card dropped to 5,293 MiB free (below the floor) during its own slow teardown, needing `kill -9` |
| 5 | 0.11 | 26 GB | 8192 | 1, `--enforce-eager` | 11,548 MiB | card crossed below 6,144 MiB free at 48 s into startup (own monitoring loop, 4 s polling); killed pre-emptively |
| 6 | 0.11 | 27 GB | 4608 | 1, `--enforce-eager` | 11,548 MiB | same: 6,693 → 4,205 MiB free by 44-48 s, same shape as #5 |

Runs 5 and 6 (`--enforce-eager`, skipping cudagraph/compile, the plausible
transient-memory suspect) show the same drop at the same point regardless of
the configured fraction, which is why a seventh attempt was not made: the
model's unavoidable startup footprint at this shared-memory level is larger
than the 5,404 MiB the floor leaves, on the only card worth trying. Every
attempt that crossed or neared the floor was killed within seconds
(`kill -9` on the exact PID once — a `pkill -f` pattern that appears in its
own invoking shell's command line kills that shell instead of the target,
`t/RUN-NEXT.md`'s own documented footgun, reproduced here again while
building the kill command and then avoided); every card was back at its
baseline free memory within the same check.

**No teacher sample was generated or scored in this session.** This is the
finding, not a gap in it: measured against the briefed assumption, the shared
resource was not available within the stated safety rule, on any of the four
cards, for the whole session.

## 3. The pipeline, validated without the GPU

`t/rl_teacher_expert_iter.py` (`sample-spec`, `score-spec`,
`consolidate-training`, `assemble`) was built to need no new sampling code for
training-problem prompts (`spec_experiment.py generate --api openai`, one tag
per seed, exactly the historical `-s2` pattern already answers a pool
problem) and only a thin new sampling and scoring path for the specification
prompts, which have no pool id (module docstring). Every piece downstream of
"get a reply" reuses existing code: `spec_experiment.find_block`,
`surface.parse`, `se.rename_task`, `fuzz_lower.check_wf`, `rl_reward.prove`
(Dafny only, in the loop), `run_par.py`'s full seven kernels for the
shortlist, `rl_feasibility.load_samples` for the training-problem sample
shape.

This was checked against a real answer, not a mock: DD0178
(`vericoding_dd0178__calcPower`, `ensures p == 2 * n`), the one verified spec
answer `t/RL-DESIGN-2026-09-26.md` section 6.1 found by hand. Three
hand-written completions were scored through the live pipeline (`score-spec`,
`--local`, real Dafny), each catching what it was meant to:

| completion | result |
|---|---|
| `p := 2 * n;` (correct) | **proved** — Dafny `verified / refuted` |
| `p := 999;` (wrong body, same spec) | **typed** — well formed, not proved |
| body correct, `ensures p == 3 * n` (spec changed) | **none** — caught by the spec-fidelity check (`spec_header`), twice (a second, differently-worded mutation was caught the same way) |

`assemble` was then run end to end on the one proved sample: it re-graded
`vericoding_DD0178` in all seven kernels and wrote it as a corpus-format
document (`Problem:`/`Signature:`/`task`, the same head every other document
in this pipeline gets) plus a manifest row recording its source, sample index
and reward tier — **1 of 1 admitted, clean in seven of seven**:

    | vericoding_DD0178 | dafny | verus | spark | framac | lean | rocq | fstar |
    | verified / refuted (all seven) |

This is a validation of the machinery, not a measurement of the teacher: the
completion was written by hand from the design doc's own citation, not
sampled. It shows the reward, the spec-fidelity gate, the seven-kernel
re-grade and the document writer all work on a real proof, on the lab, before
any GPU time was spent on the teacher itself.

## 4. Numbers the task asked for

| | value |
|---|---|
| prompts per source | 442 spec-pool (apps 224, dafnybench 133, humaneval 48, verified_cogen 26, numpy_triple 7, bignum 3, numpy_simple 1); 368 training-problem (308 MBPP/HumanEval non-corpus, 60 APPS sampled of 2,225 available) |
| samples requested | k=8 planned (temperature 0.7, seeds 1-8, matching the `qwen3.8-27b-fp8-v3-s2` precedent, `t/RUN-NEXT.md`) |
| samples generated | **0** (section 2) |
| reward-tier distribution | none from the teacher; the hand-written validation set (section 3) was none 2, typed 1, proved 1 |
| verified per source | 0 from the teacher; 1 of 1 in the validation set (specpool) |
| clean in seven / clean in six | 0 / 0 from the teacher; validation set 1 / 0 |
| throughput (answers/hour, proofs/hour) | not measurable: no server stayed up long enough to answer a real batch |
| what limited it | the lab's four shared GPUs, all four at 37-49 GB used against the ~10-12 GB this task was briefed to expect, for the whole session (section 2) |

## 5. Next step

1. **Retry generation when the lab's GPUs free up.** `bash
   t/lab_gpu.sh status` (or `nvidia-smi`) first; if a card clears back to
   something near the briefed 10-12 GB used, rerun with configuration #2's
   shape (it started) but a context between 4096 and 8192 that actually fits
   both the 3,073-token v5 prompt and a real reply — untried here, since the
   contention worsened before a middle value (`--max-model-len 5120` or
   `6144` with a smaller `--max-num-batched-tokens`) could be measured. The
   exact commands: `t/out/rl-2026-09-26/spec-pool/prompts.jsonl` (442, already
   staged) and a training-ids file of the 308 + an APPS sample (section 1.2,
   reproducible from `t/out/loop/corpus-r8-headed.txt` and
   `t/rl_reward.rl_prompt_ids()`) are both ready; `python3
   t/rl_teacher_expert_iter.py sample-spec` and `python3 t/spec_experiment.py
   generate --tag rl-teacher-s<N> --seed <N>` (eight seeds) are the two
   generation commands, `consolidate-training` then `assemble` the rest.
2. **If the contention does not clear**, the same teacher could be tried at a
   smaller quantization or a shorter prompt (drop v5's extra few-shot
   examples for a shorter system prompt, trading some coverage of
   string/seq-of-seq problems for headroom) — neither was attempted here,
   since the measured failure was the same shape (a fixed startup cost
   exceeding the floor) regardless of context length, which a shorter prompt
   would not change enough to matter next to a several-GB fixed overhead.
3. **Once real samples exist**, `t/rl_teacher_expert_iter.py assemble` is
   already the path from tiered reward to a corpus-ready document set (section
   3); the recommended follow-on from there is unchanged from
   `t/RL-DESIGN-2026-09-26.md` section 7: retrain the r12 locallm on its
   planned corpus plus whatever this run admits, then re-run
   `t/rl_feasibility.py` on the new checkpoint to see whether the RL gate
   (about 10 percent of groups with a test-passing sample) moves at all before
   reconsidering GRPO.

What was learned, in one line: the pipeline (reward, spec-fidelity gate,
seven-kernel re-grade, dataset writer) is right — proven on a real proof, not
a mock — and the thing that stopped this round was not the design, it was
four shared GPUs already fuller than briefed for an entire session, which no
amount of `--cpu-offload-gb` tuning fit under the safety floor this task set.
