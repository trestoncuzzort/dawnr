# The next run, step by step

> **For a locallm training run, read `t/RUN-NEXT-locallm-r12.md` instead.** This page is the recipe for a
> teacher-generation run (2026-09-19) and still holds for one.

Written 2026-09-19 from the day's measurements, for whoever runs the pipeline next. Follow it top to bottom.
Every number here names the file it came from; nothing is estimated. Where two files in this repository
disagree, the last section says so rather than picking a winner.

Background, if you want it, is `internal/HANDOFF-2026-09-19.md` (the state) and `internal/ROADMAP-LOG.md`
(the roadmap of record). This page is only the recipe.

---

## The short version

| decision | do this | because |
|---|---|---|
| generator | `deepseek-ai/DeepSeek-Prover-V2-7B`, prompted, no adapter | 6 clean of 232, conversion 6/10 (60%), 0 spec disagreements — `t/out/score-r6.md` |
| prompt | `--prompt v4` | clean 3 -> 5 and conversion 23% -> 45% on the untrained 1.5B — `t/PREDICT-2026-09-18-round6.md` |
| grading | start at `--jobs 32`, **watch the load for a minute, lower it if you pass 120** | 64 cells drew 216 of 120 cores (`t/grade_lab.sh` lines 18-26); but a cell is not a fixed number of cores — 12 was right for the prover's answers — handoff §6 trap 7 |
| token budget | `--max-new 3072` when comparing against Phi | the 1,024-token constrained run lost 42 of its 44 parse failures to truncation — `internal/HANDOFF-2026-09-19.md` §2 |
| before anything | `python3 t/preflight.py --split t/out/loop/split-v5.json` with the kernels on PATH | it exists to catch `verus ?` — §4 of the handoff |

**The one caveat that matters:** the generator result and the prompt result were measured on different models
and have never been measured together. See step 2.

---

## Step 0. Do not start on top of someone else

Four agents were launched on 2026-09-19 with uncommitted work in this tree
(`internal/HANDOFF-2026-09-19.md` §2a): `t/lower_lean.py`, `t/lower_framac.py` + `t/verifiers/framac.py`,
`t/lower_spark.py` + `t/verifiers/spark.py`, and the lifter (`t/lift_*.py`, `t/lifter.py`).

    git status --short

At the time this page was written that printed nine modified files and four new ones, and the list grew
between the start and the end of writing it — `t/lower_lean.py`, `t/lower_framac.py`, `t/lift_check.py`,
`t/preflight.py`, `t/run_par.py`, `t/cache.py`, two Frama-C tests and `t/out/recheck.json`, plus new
`t/RECHECK-lean-scratch.md` and `t/test_lower_lean_append1.py`. **Treat every number on this page as a snapshot
of 2026-09-19 and re-read `git status` yourself.**

**A lowering that changed since the last grading invalidates every comparison against a table graded before
it.** If an agent's report contradicts its regression bar, believe the bar: two of that day's agents produced
work that looked right and had a real defect underneath — a Lean tactic chain that could succeed without closing a goal, and a Frama-C
lowering emitting an invariant that is false — and both were caught by re-running the kernel's column, not by
reading the diff (handoff §2a).

The bars, if you need to check their work yourself:

| files | bar |
|---|---|
| `t/lower_lean.py` | `mbpp_557__toggle_string` verifies; the lean column of `t/AGREEMENT.md` unchanged |
| `t/lower_framac.py`, `t/verifiers/framac.py` | the conformance suite stays at or above 454 of 462; framac column unchanged |
| `t/lower_spark.py`, `t/verifiers/spark.py` | verdicts identical; a timeout may not be bought by shrinking the question |
| `t/lift_*.py`, `t/lifter.py` | every program that lifted before still lifts; the checker is not weakened |

`t/AGREEMENT.md` is the reference table: 7 kernels, 35 committed tasks, and its sole-blocker list at the foot
reads spark 1 (`linear_search`), framac 1 (`swap_rows`), rocq 1 (`min_max`), the other four 0.

---

## Step 1. Preflight, with the kernels on PATH

    export PATH=$HOME/.cargo/bin:$HOME/.opam/default/bin:$HOME/.elan/bin:$HOME/.local/fstar/fstar/bin:$HOME/.local/gnatprove/gnatprove-x86_64-linux-16.1.0-1/bin:$HOME/.local/verus/verus-x86-linux:$PATH
    python3 t/preflight.py --split t/out/loop/split-v5.json

(One line. Six entries, in that order.)

The PATH list is `lab.KERNEL_PATH` (`t/lab.py` lines 57-59), which `t/lab.py` and `t/overnight.py` set for
themselves. **Run preflight without it and it fails on `verus ?`, which is the trap it exists for**
(handoff §4 and §6 trap 2: a non-login shell with no Rust toolchain made every Verus cell read MALFORMED on
2026-09-17).

Pass `--split t/out/loop/split-v5.json` explicitly. Preflight's default is `split-v3.json`, which **is not
tracked by git**, so on a fresh lab clone the default fails at "split readable". `split-v5.json` is tracked and
its `eval_ids` are byte-identical to `split-v3.json`'s — both are the same 232 MBPP ids, verified by comparing
the two files. The train side differs (417 against 2,771) and the eval side does not, which is the whole point
of the split.

### What each preflight failure means

Checks and their reasons are in `t/preflight.py`'s own docstring; the readings below are from its code.

| check | reads FAIL when | what it means and what to do |
|---|---|---|
| `<kernel> present` | the adapter import or `version()` raised | the kernel is not installed on this machine. Nothing downstream is gradeable. |
| `<kernel> version readable` | the version string contains `?` or is blank | **PATH, almost always.** The binary answers and its toolchain is missing. Run the `export PATH` line above and try again. |
| `<kernel> <version>` with a note | the version differs from `t/AGREEMENT.md`'s | your numbers are not comparable to the committed matrix. Pin the version or re-measure AGREEMENT. |
| `sft-*.jsonl holds no held-out problem` | an `mbpp_<id>` in a pool file is in `eval_ids` | a leak: a held-out problem is in training data and every held-out number is void. This check globs, so it cannot fall behind a round again (it did for round 6, handoff §7.2). |
| `no clean answer rests on a flaked cell` | a clean row has `FLAKED` and no re-check | grade under load disagreed with itself. Re-run that cell alone with `t/recheck_near.py`; a flip is written to `t/out/recheck.json`, which preflight reads. Never hand-edit a `kernels.md`. |
| `no clean answer rests on a timeout` | a clean row has `timeout` in any cell | **a timeout is not a verdict.** Usually oversubscription (step 4). Re-run alone. |
| `no answer in the pool disagrees with its problem` | `spec_check.py` found a disagreeing program whose text is in the pool | it would be trained on. Drop it. If the check says "run python3 t/spec_check.py", `t/out/spec-disagree.json` does not exist yet — run it first. |
| `copy-check keys unique` | duplicates in `t/out/pool-keys.txt` | one answer entered the pool twice under two tags. |
| `this machine has N GB free` / `the grading machine has N GB free` | under 20 GB, or ssh failed | `T_LAB` comes from `t/lab-workstation.conf`, which git ignores. |

**Known gap, worth knowing before you trust a green preflight:** the leak check (`check_split`) globs every
`sft-*.jsonl` and `pairs-*.jsonl`, but the specification-agreement check (`check_spec_agreement`) reads a
hard-coded list — `sft-r4.jsonl`, `pairs-r4.jsonl`, `sft-r5.jsonl`, `pairs-r5.jsonl`. An r6 or r7 pool is not
covered by that second check. Until it globs too, read its result as "r4 and r5 are clean", not "the pool is
clean".

### The other thing the lab clone will not have

**The lab's clone only has what git tracks** (handoff §3). Tracked under `t/out/loop/` right now:
`eval-ids.txt`, `train-ids.txt`, `split-v5.json`, `sft-r6.jsonl`, `pairs-r6.jsonl`. Not tracked:
`split-v3.json`, `split-v4.json`, every adapter, `apps-ids.txt`. **A run that dies instantly with
`FileNotFoundError` is almost always this** — rsync what the step needs before starting it.

---

## Step 2. Pick the generator and the prompt, and know what you are picking

### The generator: the prover base

`t/out/score-r6.md`, all ten rows on the same 232 held-out problems:

| tag | well formed | tests pass | clean | converts | spec disagrees | clean after the check |
|---|---|---|---|---|---|---|
| `qwen3.8-27b-fp8-v3` | 116 | 81 | 12 | 12/81 (15%) | 1 | 11 |
| `prover-v2-7b` | 39 | 10 | **6** | **6/10 (60%)** | **0** | **6** |
| `phi4-mini-v3` | 12 | 6 | 3 | 3/6 (50%) | 1 | 2 |
| `qwen15b-base-v3` | 39 | 13 | 3 | 3/13 (23%) | 1 | 2 |
| `student-r4-v3` | 37 | 12 | 3 | 3/12 (25%) | 1 | 2 |
| `student-r5-v3` | 42 | 11 | 3 | 3/11 (27%) | 1 | 2 |
| `student-r6-v3` | 36 | 9 | 3 | 3/9 (33%) | 1 | 2 |
| `student-r6-g` | 58 | 14 | 4 | 4/14 (29%) | 1 | 3 |
| `locallm-r4` | 209 | 2 | 2 | 2/2 (100%) | 0 | 2 |
| `locallm-r5` | 198 | 2 | 2 | 2/2 (100%) | 0 | 2 |

**Steer by `converts`** — the share of test-passing answers the seven can prove. It is the gate three rounds
of data work could not move, and it is now a column in the table rather than a hand calculation (handoff §7.4).
Read down it: 27B 15%, untrained 1.5B 23%, our rounds 25/27/33, Phi 50%, the prover 60%.

`prover-v2-7b` is `deepseek-ai/DeepSeek-Prover-V2-7B`, **prompted and never fine-tuned here**, pool v3, prompt
v3, greedy, seed 1, `max_new 2048` (read from its own `raw/*.json` records). It is the only row where no
specification disagreed with its problem. Phi loses one of three to that check.

If what you want is **pool material rather than conversion**, `qwen3.8-27b-fp8-v3` produced 12 clean of 232,
twice the prover's count, at a quarter of its conversion rate. Both facts are in the same table.

Two limits stated in `README.md`'s limits section and handoff §7, which belong next to the number every time
it is quoted: the prover's 6 is **three answers wide** and needs seeds before it is a claim, and it is 7B
against Phi-4-mini's 3.8B, so it is not a per-parameter claim.

### The prompt: v4

`t/PREDICT-2026-09-18-round6.md`, predictions written before the run, result after it. Untrained
Qwen2.5-Coder-1.5B-Instruct, same 232 problems, same decoding, prompt the only difference:

| | v3 | v4 |
|---|---|---|
| well formed | 39 | **34** |
| test-passing | 13 | **11** |
| clean | 3 | **5** |
| converts | 3/13 (23%) | **5/11 (45%)** |
| clean after the spec check | 2 | 4 |

The model wrote **fewer** answers and **more provable** ones. That is the first change measured in this
project that moves conversion at all, and it moved it with no training.

Why v4 differs from v3 (`t/spec_experiment.py`, the `prompt v4` block): v1, v2 and v3 all told the model t has
"no division, no modulo" and listed `/` and `%` among operators that do not exist. **They have existed since
2026-09-08**, and 163 of 785 census programs need them (`t/LIFTER-DECISIONS.md` decision 20). v4 corrects that
and names the three commonest refusals — a spec function goes before the body, comparisons do not chain, there
are no comments. It is built from v3's own text by string replacement with an assertion on each, so the two
cannot drift; v3 is untouched.

### The caveat: these two results have never been combined

Every `prover-v2-7b` number above was generated under **prompt v3**. Every prompt-v4 number was generated on
the **untrained 1.5B** (`t/out/spec-experiment/qwen15b-base-v4`, `prompt_version: v4`, pool v3, greedy, seed 1,
`max_new 1024`). Prover + v4 is unmeasured. Run it as the first thing, not as an assumption, and expect the
1.5B's direction (fewer answers, better conversion) to be a hypothesis about the prover rather than a fact.

Also still open and written down but not run (handoff §8.1): **v4 with the division sentence alone against v4
with the refusal rules alone**, same base, same 232. Two readings of the v4 result survive this sample — either
telling the model it has division lets it write specifications it can satisfy, or naming the refusals pushes it
to attempt fewer and simpler problems — and the difference is 2 answers out of 232. Until that split runs,
neither reading is a claim.

---

## Step 3. Generate

    ~/.venv-vllm/bin/python t/loop_generate.py --adapter none \
        --base deepseek-ai/DeepSeek-Prover-V2-7B --tag <tag> \
        --pool v3 --prompt v4 --ids-file t/out/loop/eval-ids.txt --max-new 2048

`~/.venv-vllm/bin/python` is the interpreter with torch, transformers, xgrammar, peft, bitsandbytes and vLLM
(handoff §3). `eval-ids.txt` is the 232 held-out ids and is tracked.

`--max-new 2048` is what the existing `prover-v2-7b` row was generated with, so it is the right budget for a
seed of that row. Raise it to 3,072 only if the comparison you are making is against `phi4-mini-v3`, which used
3,072 — and then raise it for both.

**Held-out sets are graded whole.** Do not run `t/pool_pick.py` on them; that filter is for training sets, and
grading a held-out set whole is the point of a held-out set (handoff §4).

Four things that have cost time here:

1. **`--max-new` is not cosmetic.** The first constrained student run used 1,024 tokens and **42 of its 44
   parse failures were simply cut off** — the run was rigged against itself (handoff §2). Phi's own held-out
   run used 3,072. Match the budget across any arms you intend to compare.
2. **Seeds need `--samples`, not `--seed`.** At `--samples 1` the seed is recorded in the digest and
   generation stays greedy (`t/loop_generate.py --seed` help text), so re-running with `--seed 2` reproduces
   the identical answers. For the two or three prover seeds handoff §8.3 asks for, use `--samples 3
   --temperature <non-zero>`; each sample lands in its own `<tag>-s<k>` directory.
3. **A flag can reach three call sites and miss the one that runs.** `--grammar` was wired into
   `generate_samples` while every held-out run took the single-sample fast path straight to `model.generate`.
   The tell was 158 parse failures against the unconstrained run's 159 (handoff §6 trap 3). Check any claim
   against a number that would move if it were true.
4. **DeepSeek-Prover-V2's tokenizer drops every space** under transformers 5.17 — it loads as LlamaTokenizer
   and turns sound answers into `t1tasksmall_nnum(...)`. `loop_generate` now round-trips a line of t before
   trusting it. Keep that check (handoff §6 trap 4).

A problem that already has a record on disk is not re-asked (`t/spec_experiment.py` docstring), so a
half-finished tag resumes rather than restarting.

### If you are finishing the constrained comparison instead

`phi4-mini-g`, `student-r6-g3k` and `qwen3-14b-think` were generating on 2026-09-19 (handoff §2). Check one
with:

    ssh $T_LAB "ls ~/tup/t/out/spec-experiment/<tag>/raw | wc -l"

The preregistration (`t/PREREG-2026-09-18-constrained.md`) requires **both arms graded at the same cell count**,
and WS-21's DONE WHEN in `internal/ROADMAP-LOG.md` says 32. The waiting chain that was left running
(`scratchpad/finish.sh`, copied nowhere permanent) grades at `--jobs 24`. Both arms at 24 is still the same
number on both sides; 24 against 32 is not. Grade the pair the same way or regrade one of them.

Note the collision with step 4's correction: **24 cells plus four generation jobs is what took the machine to
a load of 138** (handoff §6 trap 7). If that chain is still grading while these three are still generating, it
is over the line, and SPARK timeouts in those tables are scheduling artifacts rather than verdicts. Check the
load before you believe either arm.

---

## Step 4. Extract, test, grade — and pick `--jobs` by watching, not by memory

    python3 t/spec_experiment.py extract --model <tag> --pool v3
    python3 t/spec_experiment.py tests   --model <tag> --pool v3
    python3 t/run_par.py --jobs 32 --tasks t/out/spec-experiment/<tag>/tasks \
        --out /dev/shm/tup-grade/<tag>/kernels --table t/out/spec-experiment/<tag>/kernels.md
    # then, a minute in:
    uptime            # if the load average is past 120, stop and lower --jobs

### Why 32 is the starting point, not the answer

From `t/grade_lab.sh` lines 18-26, measured on the APPS sets on 2026-09-18:

- The lab workstation has **120 threads**, and its CPUs are ours; only its GPUs are shared.
- **64 cells drew 216 of those 120 cores** and the load average sat at **2.1x the core count**, because a
  SPARK cell is not one core: gnatprove keeps a gnatwhy3 tree alive, and on loop-heavy sets a cell averages
  **3.4 cores**. Frama-C spawns 4 provers per cell of its own.
- Oversubscription is not merely slow. **The wall-clock backstop in `t/verifiers/spark.py` then fires on cells
  that would prove alone**, and a timeout is not a verdict — `t/preflight.py` refuses any clean answer resting
  on one, so an oversubscribed grading silently destroys results rather than delaying them.
- **32 cells is about 110 cores**, which also leaves the other users of a shared machine a little room.

Each cell makes six concurrent kernel calls (`t/run_par.py --jobs` help text).

**Corrected the next day, and this is the rule to follow** (handoff §6 trap 7, committed 2026-09-19): **a
grading cell is not a fixed number of cores, so a fixed `--jobs` is the wrong control.** 3.4 cores a cell was
measured on the APPS sets. The **proof-trained model's answer set drew about 7 cores a cell** — 24 cells plus
four generation jobs took the 120-core machine to a **load of 138** — because the shape of the answers decides
how much parallel prover work each cell spawns. **12 was right for that set while generation was also
running.**

So: start at 32 on a quiet machine, **read the load a minute in, and lower `--jobs` if it is past the core
count.** If you are generating on the same box at the same time, start far lower. The number to steer by is the
measured load, not a number someone remembered — which is exactly why this correction exists.

**Whatever number you pick, a cell can still flake, and the flips are not rare.** The documented shape is in
`t/out/recheck.json`: `qwen3-coder-30b-apps-s2 / apps_3271__arr / spark`, FLAKED under the sweep,
`verified / refuted` when re-run alone, because "gnatprove under 32 concurrent cells starves its own wall
clock". The rule is in `t/lower_spark.py`'s own notes: a sweep-load SPARK cell is provisional until re-verified
alone. And `t/RECHECK-lean-scratch.md` (2026-09-19 09:20Z) re-ran 26 Lean cells alone and **16 changed their
mind** — see "Which kernel is worth fixing" below, including the caveat about what caused those sixteen.

Read `t/out/recheck.json` rather than trusting a count from any page, this one included: it was carrying 17
entries at one point on 2026-09-19 and 1 entry an hour later, while agents were working in this tree.

So **budget a re-check pass after every grading**, not just when something looks odd:

    python3 t/recheck_near.py --only unproved --flake 3
    python3 t/recheck_near.py --only timeout  --flake 3

It re-runs the single blocking kernel by itself and writes any flip to `t/out/recheck.json` in the form
`t/preflight.py` already reads. **Nothing edits a `kernels.md`** — the tables stay as the sweep wrote them and
the re-check is a record beside them, carrying how it was run. That is the only way a changed verdict stays
arguable.

Grading on the lab from another machine is `bash t/grade_lab.sh heldout` or `... tags T1 T2`, which reads
`T_LAB` from `t/lab-workstation.conf`, defaults to `T_LAB_JOBS=32`, four answer sets at once, and works in
`/dev/shm/tup-grade` because the whole working set fits in RAM and only `kernels.md` comes back.

---

## Step 5. Check the specifications, then score

    python3 t/spec_check.py --pool v3 --only clean <tag>
    python3 t/score_heldout.py <tags...>

**Do not skip `spec_check.py`.** Until 2026-09-19 `score_heldout.py` credited an answer as
specification-checked whenever it was *absent* from the disagreement list, so a set nobody had ever checked
scored full marks — and that produced a false claim in this project's own reporting: round 5's student was
called "one ahead" of Phi, 3 clean surviving the check against 2. Checked properly it is **2 against 2, a
tie** (handoff §7.1, `README.md`'s corrections section). `spec_check.py` now records which tags it ran over and
`score_heldout.py` prints `not checked` for anything else.

What that check has found over everything (`internal/ROADMAP-LOG.md`, WS-20 move 3, and
`t/SPEC-CHECK-2026-09-18.md`): all 36 graded answer sets, 650 clean answers, 200 random draws each inside the
task's own precondition — **13 disagree**. About 2 percent of clean answers are false accepts that seven
provers and a refuted twin both missed. All 13 are held-out answers; none is in the training pool. Across the
ten held-out rows specifically: 86 clean answers, 67 agree, 8 disagree, 11 uncheckable (handoff §7.1).

A partial grading now says so: a table graded with `--kernels lean` alone prints `(only N kernels)` when N < 7,
instead of reporting "clean" for agreement among one column (handoff §7.3).

If you are building a round rather than scoring one, the rest of the pipeline is unchanged:

    python3 t/pool_pick.py t/out/spec-experiment/<tag> --control 40    # TRAINING sets only
    python3 t/loop_dataset.py --from-samples <tags...> --split t/out/loop/split-v5.json \
        --min-kernels 7 --out-suffix r7
    PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True ~/.venv-vllm/bin/python t/loop_train.py \
        --sft t/out/loop/sft-r7.jsonl --pairs t/out/loop/pairs-r7.jsonl --sft-first --max-len 3072 \
        --out t/out/loop/adapter-r7

`--max-len 3072` is not a preference. trl 1.13 removed `use_logits_to_keep`, so the DPO policy forward builds
full-window logits: **3,072 is the window that fits a 1.5B on 16 GB and keeps 482 of 489 pairs; 2,560 silently
keeps 45** (handoff §6 trap 8 — it was trap 7 until the grading-cell correction was inserted above it on
2026-09-19, so an older reference to "trap 7" means this one).

---

## What is cheap and what is not

### Proof, per task per kernel

`t/BUDGETS-2026-09-19.md`, measured by `t/budgets.py` over the 35 committed tasks, one verification of the real
program per task per kernel, verdict cache bypassed. The twin is not timed.

| kernel | median | slowest | under 1 s | under 3 s | under 10 s |
|---|---|---|---|---|---|
| `lean` | 0.50 s | 3.7 s | 30 of 35 | 34 of 35 | 35 of 35 |
| `fstar` | 0.92 s | 14.4 s | 19 of 35 | 31 of 35 | 34 of 35 |
| `verus` | 1.12 s | 1.6 s | 11 of 35 | 35 of 35 | 35 of 35 |
| `dafny` | 1.23 s | 1.8 s | 0 of 35 | 35 of 35 | 35 of 35 |
| `framac` | 3.73 s | 24.2 s | 0 of 32 | 15 of 32 | 28 of 32 |
| `rocq` | 4.23 s | **180.1 s** | 0 of 35 | 10 of 35 | 27 of 35 |
| `spark` | **21.88 s** | 63.4 s | 0 of 35 | 0 of 35 | 17 of 35 |

- **Free while someone types:** lean, fstar.
- **Affordable on a pause or a save:** verus, dafny, framac, rocq.
- **Only when asked for:** spark — 21.88 s median against the next-slowest 4.23, more than five times any
  other kernel. Note that `framac`'s row counts 32 of 35 tasks, not 35.
- Two slowest columns matter more than they look: rocq's median is cheap and its tail is 180 s, so rocq is the
  kernel that turns a long sweep into an overnight one.
- **The flake rule costs three runs, not one**, so a verdict anywhere a table reads from costs three times
  every number above (`t/BUDGETS-2026-09-19.md`, last paragraph).

### Generation, per answer

From handoff §2, the 2026-09-19 runs:

| run | rate |
|---|---|
| the student under the grammar at 3,072 tokens | 23 s an answer |
| `qwen3-14b-think`, unconstrained | 23 s an answer |
| `prover-train` (417 training problems) | 23 s an answer, about 2.5 hours for the set |
| `phi4-mini-g`, Phi under the grammar | **~124 s an answer** |

And the one that should stop you: constrained generation of the 30B on APPS cost **3,269 generation minutes
for 43 test-passing answers — 4,561 s each**, where the unconstrained control's whole 1,133-problem run took
about **19 minutes** (`t/out/CONSTRAINED-2026-09-18.md`). Constrained decoding on a large model is not a step
you add casually to a round.

### Which kernel is worth fixing

Two different populations, and they are easy to confuse:

- **The 87 near-misses across this repository** (`t/recheck_near.py`, triaged in `internal/ROADMAP-LOG.md`):
  answers that pass their tests and that six of seven verified with the twin refuted. This is the largest
  reserve in the project: the whole clean pool is also 87 examples, and handoff §8.0 puts the size of the
  prize concretely — **Lean's 26 and SPARK's 13 near-misses alone would grow the training pool by nearly
  half.**
- **The APPS corpus alone** (`t/COVERAGE-apps-2026-09-19.md`): of 2,266 problems, 2,263 answered, 422 well
  formed, 257 test-passing, **29 clean (1.3%)**. Its sole blockers are spark 6, framac 3, lean 2, and the other
  four kernels 0. Its biggest single stop is `dafny unproved` 201, with `spark timeout` 196 right behind.

What was measured about the 87 on 2026-09-19, and it changes where a session is worth spending:

- **Frama-C's twelve timeouts are a prover limit, not a budget.** On `mbpp_503__add_consecutive_nums` the goal
  ends in `[Stepout]`, the step limit, not `[Timeout]` — the opposite knob from the one `verifiers/framac.py`
  discusses. Raising it buys nothing: **20,000, 200,000 and 1,000,000 steps all give 26 of 28 goals**, in 3, 15
  and 35 seconds; swapping alt-ergo for z3 is worse at 23 of 28. Re-running them alone confirms it at 6 to 8
  seconds each, verdict unchanged. **Do not spend a session here.**
- **Lean's were called one named tactic gap, and most of them were not.** The triage said: of the answers only
  Lean could not prove, 21 have a `while`, 20 a `forall` invariant, 16 return a `seq`, and **none** has a nested
  loop, a slice, a spec function or a string-library call; the failing goal is invariant preservation after
  `r := r ++ [x]` where the invariant body is a nested if-then-else; the next move is case analysis on the
  if-then-else *inside the invariant* before the append rewrite. Then `t/RECHECK-lean-scratch.md`
  (2026-09-19 09:20Z, `t/recheck_near.py --only unproved --flake 3`) re-ran the 26 cells alone:
  **16 changed their mind and 10 held.** Sixteen answers are now clean — tests pass, all seven verify with the
  twin refuted — and the flips are in `t/out/recheck.json`. Five of the sixteen are `mbpp_557__toggle_string`.
  The ten that held are a real cost: `mbpp_913__end_num` (four sets), `apps_2415__searchInsert`,
  `mbpp_736__left_insertion`, `mbpp_890__find_Extra`, `mbpp_641__is_nonagonal`, `mbpp_718__alternate_elements`.
  **Read this before planning a Lean session:** the prize just shrank from 26 to 10, and see the caveat below
  about what actually caused the flips.
- **A timeout that is really load exists and is rarer than hoped.** Re-running the timeout-shaped cells alone at
  flake 3 flipped **one** in the first fifteen (`he_42__incr_list`, lean, `verified / timeout` to
  `verified / refuted` in 2.0 s). Everything Frama-C held.

**Caveat on those sixteen, and it is not settled.** `mbpp_557__toggle_string` is the named regression target of
the agent that is editing `t/lower_lean.py` right now (handoff §2a), and `t/lower_lean.py` is modified in the
working tree. So two explanations fit the flips equally well from this side: the cells were starved by
concurrency and prove fine alone, or the agent's lowering change made them provable. The scratch report
describes the run as "re-run by itself instead of beside 31 others" and does not say which `lower_lean.py` was
in effect. **Before quoting "16 flipped" anywhere, establish which it was** — re-run one of the sixteen at the
committed `lower_lean.py`. Attributing a lowering's win to scheduling, or the reverse, is exactly the kind of
mistake §7 of the handoff exists to catch.

---

## What NOT to try

Seven ideas, each closed by a measurement. The table is `README.md`'s "What has been ruled out, and what it
cost to find out"; handoff §5 carries the same seven. **Do not spend a night re-testing these.**

| Idea | What was measured | Where |
|---|---|---|
| More problems | the corpus is exhausted at about 3,000. APPS's *test* split yields 37 more usable problems (the rest are stdin/stdout, not named functions), and widening the value kinds t admits would buy at most 353, mostly floats and dicts | `t/funnel.py`, `internal/ROADMAP-LOG.md` WS-20 |
| More answers per problem | rounds 4 and 5 grew the pool from 60 to 87 rows and moved the clean count by **0** | `t/out/score-r6.md` |
| Let the model repair its own unproven answers | 110 repaired answers, **2 clean** — 1.8% against 21% for fresh samples. A 14B handed seven verdicts writes worse proofs more often than better ones | `t/runs/2026-09-17/NOTES-home.md` |
| A more tolerant reader (comments, `&&`, `\|\|`) | rescues **119 of 6,603** refused replies, 2%, and a second layer adds 3. The refusals are structural: `let x := e in`, list comprehensions, `?:`, `^` | `t/FUNNEL-2026-09-18.md` |
| Growing t's syntax | the commonest refusal is a spec function written after the task — 18.5% of refused replies — and moving them where t wants them rescues **1.6%**. Comments are 2%. Dict and set literals, the two things t genuinely lacks, appear in **none** of them | the same file |
| Decoding against t's grammar (30B, APPS) | parsing doubled (32% to 63%) and test-passing rose **1.23x**, below the 1.5x the preregistration required. INCONCLUSIVE, and the cost was 4,561 s an answer | `t/out/CONSTRAINED-2026-09-18.md` |
| Preference pairs aimed at the proof gate | conversion 27% to 33%, clean count **unchanged** at 3 | `t/PREDICT-2026-09-18-round6.md` |

The shape underneath all seven, from `t/FUNNEL-2026-09-18.md`: over 14,130 replies, a prompted stock model
writes something t's parser accepts **38%** of the time, well formed 23%, test-passing 17%. **The syntax gate
loses more answers than every other gate together.** And yet — locallm, trained on t from random weights,
parses **98%** and passes tests in **2 of 464** answers: it has the notation and not the problem. The
fine-tuned student parses 32%, exactly where the untrained 1.5B already sat. Fixing notation is not the same as
fixing answers, and every ruled-out idea above is a way of learning that again.

Note that the grammar row is ruled out **as a way to buy clean answers**, not as a mechanism: under the grammar
the round 6 student's parse failures fell 159 to 44, well formed rose 36 to 58, test-passing 9 to 14, and clean
3 to 4 (handoff §1). A constraint applied to one side only is two experiments, which is why the Phi arm exists.

---

## How to stop safely on a shared machine

**The lab's GPUs are lent, not owned. Stop when asked** (handoff §9). The four 48 GB cards are shared with
another user whose tensor-parallel job sits on all four.

    bash t/lab_gpu.sh stop

That clears every process of ours off the cards in seconds. It exists as one command for a reason
(`t/lab_gpu.sh` lines 62-68):

**`pkill -f <pattern>` matches the shell running it.** A plain `pkill -f 'vllm serve'` over ssh matches the
shell carrying the pattern in its own command line and kills the stop command halfway through — on 2026-09-18
that left the server and all four workers alive while printing "stopped", and a vLLM server held four shared
cards for an hour and three quarters. `lab_gpu.sh stop` uses bracketed patterns (`[v]llm serve`, `[V]LLM::`,
`[s]pec_experiment.py generate`), kills, waits, and kills again with `-9`. If you write your own, bracket the
pattern **and** put the kill in its own ssh call, because the launch half of a compound command carries the
pattern too (handoff §6 trap 1).

Two more rules for a shared machine:

- **Grade at 32, not 64.** Step 4. 110 cores of 120 leaves the other users room; 216 of 120 does not.
- **Do not press a Run button.** `python3 t/lab.py` opens the window and it **watches only** — the Run buttons
  were removed on purpose, because a button that starts a second copy of a running step loses a night's work
  (handoff §4). Steps are driven from a terminal.

### Why every answer is its own file

`t/spec_experiment.py`'s own docstring: `raw/<task_id>.json` keeps the prompt, the reply, token counts,
timings and the model digest, one file per problem, and **a problem with a record on disk is not re-asked**.

That is what makes stopping cheap. Because every answer is its own file, `lab_gpu.sh stop` can fire the moment
the cards' other user asks and **nothing in flight is lost** (handoff §3) — the next run picks up at the
problem that has no record yet. It is also what makes a run auditable: the digest on each record is how this
page could state that `prover-v2-7b` ran under prompt v3 at `max_new 2048` and `qwen15b-base-v4` under prompt
v4 at 1,024, without trusting anyone's memory.

The same principle governs verdicts. A re-check writes to `t/out/recheck.json` rather than editing a
`kernels.md`, so a changed verdict carries how it was run and can be argued with.

---

## Where the sources disagree

Four places. None is resolved here; each is flagged so the next run does not quietly pick one.

1. **Lean's share of the 87 near-misses: 23 or 26.** `internal/ROADMAP-LOG.md`'s counted triage block reads
   `23 lean unproved` and separately `3 lean twin unproved`; its own prose two paragraphs later says "Lean's 26
   `unproved` rows" and "of the 26 answers only Lean could not prove"; `internal/HANDOFF-2026-09-19.md` §1a
   carries "lean 26 `unproved`". 23 + 3 = 26, so the likeliest reading is that the prose merges `unproved` with
   `twin unproved` — but no file says so, and the triage rows are what `t/recheck_near.py` would print.
   `t/RECHECK-lean-scratch.md` then re-ran "**26** cells", which favours the 26 reading without stating it.
2. **The near-miss total: 86 or 87.** Every source says **87**, and the triage rows in
   `internal/ROADMAP-LOG.md` sum to **86** (23+18+8+3+2 and 13+12+3+2+2). One answer is unaccounted for in the
   breakdown.
3. **Timeout-shaped cells: 35 or 41.** `t/recheck_near.py`'s docstring says "35 of those stopped on a
   *timeout*", which is what the triage rows sum to (spark 13, framac 12, lean 8, rocq 2).
   `internal/ROADMAP-LOG.md` says "re-running the **41** timeout-shaped cells alone at flake 3".
4. **APPS problems answered: 2,262 or 2,263.** `t/COVERAGE-apps-2026-09-19.md` says 2,263 of 2,266 (99.9%);
   `internal/ROADMAP-LOG.md`'s WS-20 move 2 says "2,262 of 2,266 have an answer". One problem apart, and the
   coverage table is the later and more specific of the two.

One more that is not a disagreement but reads like one: `t/COVERAGE-apps-2026-09-19.md`'s sole blockers
(spark 6, framac 3, lean 2) are over the **APPS** graded sets; `t/AGREEMENT.md`'s sole blockers
(spark 1, framac 1, rocq 1) are over the **35 committed tasks**; the 87 near-misses are over **every answer set
in the repository**. Three populations, three tables, and no number crosses between them.

---

## How the operator wants the result reported

From handoff §9, because it changes what you write down before you start:

- **Say the honest number first, unhedged, and end with what was gained** — the hypothesis closed, the bug
  exposed, the capability that now exists. Failures are the instrument here, not something to soften.
- **Write predictions before a run**, with the number that would falsify them
  (`t/PREDICT-2026-09-18-round6.md` is the model), and **preregister an experiment's rule before either arm
  exists** (`t/PREREG-2026-09-18-constrained.md`).
- Plan in `internal/ROADMAP-LOG.md`; move things to `ROADMAP.md` as they finish, not when they are proposed.
- No assistant attribution anywhere — commits, docs, code comments.
- Do not ask the operator to paste output; tell them how they will know it is done.
- **`t/out/` is gitignored.** Any result a reader is pointed at has to be `git add -f`ed, or a clone can read
  the claim and not the data behind it (handoff §6 trap 6, §7.6).
