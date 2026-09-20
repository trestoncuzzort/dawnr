# Handoff, written 2026-09-19 23:50 for whoever picks this up next

Claude access ends at midnight. This is the live state, what is running, what is
half-finished, and the traps. Everything below was measured today unless it says
otherwise. Read `AGENTS.md` first, then this.

## The headline, and exactly how far it is supported

**locallm, 92M parameters, drew level with Phi-4-mini, 3.8B, at 3 clean answers
of 232 held-out problems.** Table: `t/out/score-r8.md`. The winning arm is
`locallm-r7b-headed2`: 91 well formed, 3 tests passing, 3 clean, and all 3
survived `spec_check.py`, where one of Phi's 3 cannot be checked at all.

The Phi baseline was regraded the same day by the same evaluator
(`phi4-mini-eval2-2026-09-19`) and reproduced its historical row exactly: 12
well formed, 6 tests passing, 3 clean. `t/out/evaluator-state-2026-09-19.json`
records both machines' HEAD, dirty files and per-file hashes before and after,
with `evaluator_stable: true`.

**Three attacks on that claim, all fair, none yet answered:**

1. **3 of 232 is 1.3%.** Both models fail ~99% of the time. A tie at the floor
   is a tie in noise. Fixing this means raising the absolute number, which
   means more training data.
2. **Phi has never seen t**, so 220 of its 232 answers do not parse. The arm
   that answers this is `phi4-mini-g`, Phi decoding against `t/t.gbnf`, which
   cannot emit unparseable output. **It is 56 of 232 generated and was never
   graded.** Finishing it is the single highest-value experiment available.
3. **No seeds.** Three arms exist to fix this and are described below.

The README states all three caveats next to the number. Do not remove them
without the measurement that retires them.

## What is running: one job, and it finishes on its own

`/tmp/finish_tables.sh` is running detached on the lab, assembling the three
seed arms' `kernels.md` from their cached cells. It touches
`~/tup/t/out/tables.done` when finished and logs to `t/out/finish-tables.log`.
It is re-running the SPARK cells it has to, so expect tens of minutes. **When it
is done, that is attack 3 answered**: copy each
`/dev/shm/tup-grade/<tag>/kernels.md` to
`t/out/spec-experiment/<tag>/kernels.md` on the desktop, then spec-check and
score as described below. If `/dev/shm` was cleared by a reboot, the 232 answers
per arm still exist and `bash t/grade_lab.sh heldout <tag>` regrades them.

## What else was running: nothing. The long runs were stopped deliberately

Killed at 23:45 at the operator's request, with their partial output kept:

- `prover-train2`: **450 of 2,354** training problems answered by
  DeepSeek-Prover-V2-7B, prompt v4, pool v5. Resumable: a problem with a record
  on disk is never re-asked. Restart with `/tmp/gen_prover2.sh` on the lab, or
  the command inside it. **These 450 are ungraded and are the fastest path to a
  bigger pool**: its predecessor `prover-train` converted 31 of 88 graded cells
  into clean answers.
- `phi4-mini-g`: 56 of 232, same resumability, `/tmp/gen_phig.sh`.

## Half-finished, and the exact state

**Three seed arms are fully generated and partly graded.** `locallm-r9` (heads
on the specification-checked pool), `locallm-r9-seed7` and `locallm-r9-seed42`
(same recipe from the other two pretrained cores) each have 232 of 232 answers
in `t/out/spec-experiment/<tag>/raw` on the lab.

Their kernel cells were computed into `/dev/shm/tup-grade/<tag>/kernels/` but
**`kernels.md` was never assembled**, because the ssh session carrying
`grade_lab.sh` timed out when I overloaded the box. The cells are cached, so
re-running the driver over the same directory assembles the table without
redoing the proofs:

```bash
cd ~/tup && python3 t/run_par.py --jobs 24 \
  --tasks /dev/shm/tup-grade/locallm-r9/tasks \
  --out   /dev/shm/tup-grade/locallm-r9/kernels \
  --table /dev/shm/tup-grade/locallm-r9/kernels.md
```

Then copy each `kernels.md` to `t/out/spec-experiment/<tag>/kernels.md` on the
desktop, run `python3 t/spec_check.py <tags> --pool v5 --n 100 --only clean`,
and `python3 t/score_heldout.py ...`. **/dev/shm does not survive a reboot.**
If it is gone, the answers still exist and `bash t/grade_lab.sh heldout <tag>`
regrades from scratch.

Predictions for these arms are registered in
`t/PREDICT-2026-09-19-round8.md`; the seed arms themselves were launched to
answer attack 3 and have no separate registration, which someone should write
before reading their numbers.

## What worked today, in order of how much it mattered

1. **The header.** Giving every training document the signature its own program
   declares took signature failures from 40.8% to 12.1% and turned 2 clean into
   3. `t/head_align_corpus.py`, `t/out/loop/corpus-r8-headed.txt`.
2. **Greedy decoding.** Temperature 0 instead of 0.5, same checkpoint: well
   formed 136 to 149, clean 1 to 2, free.
3. **The specification check nobody had run.** The training gate was refusing
   246 answers that had passed their tests and all seven verifiers because
   `spec_check.py` had never been run on them. Running it over 34 tags took
   minutes and took the pool from 87 preference pairs to **733**.
   `t/SPEC-CHECK-2026-09-19.md`.
4. **Sharded generation, roughly 12x.** One problem at a time on one card
   leaves a 48 GB card 97% idle. Split the held-out list into four chunks
   (`t/out/loop/eval-chunk{0..3}.txt`) and run a worker per chunk per card;
   workers skip answers already on disk, so no coordination is needed. Three
   arms generated in about ten minutes.

## What did not work, so nobody repeats it

- **A cleaner pool did not help.** `locallm-r8` trained on 79 examples that are
  verified, twin-refuted and confirmed to specify the right problem, replacing
  a pool containing 28 that disagree, and scored exactly what the same recipe
  scored before.
- **A shorter training schedule is worse.** `locallm-r7b-step150`: 92 well
  formed, 0 clean.
- **The synthetic composition curriculum is a dead end at this scale.** Three
  seeds scored 0, 2 and 0 of 323 held-out tasks, and 0 of 203 three-stage tasks
  at every seed. `locallm/FINDINGS-learnability-2026-09-19.md`.
- **The latent/execution factorial produced no synthesis gain**, and its own
  instrument was wrong: 38 of 38 correct answers sat on tasks a shorter program
  already passed. `t/audit_collapsible.py` is the check;
  `locallm/FINDINGS-factorial-2026-09-19.md` is the write-up.

## Engine fixes made after the runs stopped, 2026-09-19 late

Five silent failures, each of which had already cost a round. All committed,
all verifiable without a GPU.

| file | what was silently wrong |
|---|---|
| `t/spec_check.py` | crashed on its last line when `--out` was relative, **after** writing the report: work done, exit code nonzero |
| `t/loop_locallm.py` | the corpus splitter knew `Problem:` heads and bare programs, not `Signature:` heads, so a headed corpus passed as `--base` merges documents |
| `t/loop_filter.py` | same splitter gap, plus a head stripper that removed only `Problem:`/`Signature:` lines, so an `Example:` line made `surface.parse` fail and the document vanish from the copy check inside `except Exception: pass` |
| `.gitignore` | `t/out/` hid the scoreboard tables, so `git add t/out/score-r8.md` failed silently and three findings cited files the repo did not contain. Negations added for `score-*.md`, `evaluator-state-*.json`, `capacity-*.json` |
| `t/grade_lab.sh` | `git pull --ff-only \|\| true` is how the grading machine ran 19 commits behind with 109 dirty entries while every log line looked normal. It now prints the HEAD and dirty count it is actually grading with |

`t/test_head_handling.py` fails if a new head line is added without teaching
the stripper, both splitters and the aligner. That mistake has been made three
times; the test is there so it is made zero more.

## Optimizations made after the runs stopped

| change | what it buys |
|---|---|
| `t/gen_fleet.sh` | the measured **12x** on generation, permanently: shards the held-out list stride-wise, a worker per shard per card, no coordination because answers already on disk are skipped, sentinel written **only on success** |
| `t/loop_locallm.py --use-cache` | the KV cache this project built and verified correct was unreachable from the pipeline; every generation has been decoding 1200 tokens an answer without it. Off by default, **unmeasured on this path**, prediction to register in the help text |
| `t/preflight.py` | reads the grading machine's HEAD and dirty count and says when it is not this tree. It found the drift on its first run |
| `t/grade_lab.sh` | reads load, cores and our own running workers before choosing cell count, instead of always taking 32. A SPARK cell averages 3.4 cores, so cells are the budget |
| four `t/steps.json` entries | the fleet, both recovery scripts and the examples corpus, drivable from t Lab |

**`t/spec_check.py` was considered for parallelism and deliberately left
serial.** One `random.Random(seed)` is threaded through every task in order, so
task N's arguments depend on tasks 1..N-1. That is what makes a seed reproduce a
report, and it means any concurrency changes the verdicts. Its output is cited
evidence, including the figure in the README and the file the training gate
reads. The safe route is per-task seeding from the task's own hash, which is a
change to the instrument and needs every report regenerated and the change
registered. The reasoning is written at the line someone would edit.

## The CPU-side optimization scan

`internal/OPTIMIZATION-SCAN-2026-09-20.md` has the full version with a paper
cited for every issue. The short form:

- **Fixed.** The corpus was re-tokenized at every training start: 104.6 s for
  48.8M tokens of frozen text, about 9% of each arm's wall clock, paid again on
  every resume. `locallm/data.py:cached_encode` makes it **1.6 s** with
  identical ids, keyed on the text hash and the tokenizer fingerprint together.
  Set `LOCALLM_TOKEN_CACHE=~/.cache/locallm-tokens` to turn it on; it is off by
  default so no existing command changes by upgrading.
- **Do not bother with a SPARK prover portfolio.** `spark.py:350-365` already
  proved with `strace` that the prover is not the cost: 93 obligations at "max
  0.0 seconds" against 111 serially-launched processes. The `-j` fix landed
  2026-09-19 and is the right one.
- **Do not bother parallelizing extract and tests.** Measured at 1.2 s and
  1.06 s for a 232-answer set.
- **Worth doing, with CPU hours:** deploy the verdict cache to the grading
  machine, which has never had it (`grep -c "import cache"` returns 0 there),
  after its three-table bar passes. And replace wall-clock backstops with
  CPU-time limits, after re-measuring the affected column cell for cell.

**Standing rule from the operator, 2026-09-20:** search for a paper before
fixing anything, cite it in the code and the commit, and say so plainly when no
paper exists rather than implying one does.

## PICK UP HERE: dead workflows, dead agents, and live files

### Research agents, and the lesson from one that died badly

Five literature agents were run. **One finished, returned a 30-paper report, and
never wrote its file**, because the instruction to save incrementally reached it
too late. Its report was recovered by hand into
`internal/research/nl-to-spec.md`. Every later agent was told to append to disk
after each item, which is the rule to keep: **an agent's return value is not a
deliverable; a file is.**

Files in `internal/research/`, each standing on its own:

| file | lane | state |
|---|---|---|
| `nl-to-spec.md` | generating a spec from intent | complete, 30+ papers, recovered by hand |
| `intent-from-examples.md` | pinning intent with examples and tests | agent was still appending when the session ended |
| `repos-verification.md` | open-source repos and benchmarks | agent was still appending |
| `verifier-feedback-training.md` | RL/filtering from verifier signal | agent was still appending |
| `spec-validation.md` | validating and repairing specs | **may not exist**: that agent had not written anything yet |

If a file is short or missing, that agent died before finishing. Nothing is
lost that was written; re-run the same lane if you want more.

### The five papers to act on first

From `nl-to-spec.md`, ranked for this repo:

1. **VeriMed** ([arXiv:2605.13817](https://arxiv.org/html/2605.13817v1)) — sample
   k specs, check pairwise equivalence, treat disagreement as ambiguity with a
   concrete witness. Their repair ladder is 55.4% → 80.0% → **98.5%** as feedback
   goes from none to textual to counterexample. We have seven provers to do the
   pairwise check with.
2. **SpecRL** ([arXiv:2604.05820](https://arxiv.org/abs/2604.05820)) — spectests:
   negatives built from *implementation-impossible* outputs. +26.46% relative
   completeness. Our `spec_check.mutations` is the same primitive already built.
3. **SpecBench** ([arXiv:2605.21384](https://arxiv.org/abs/2605.21384)) — split
   the problem's own assertions into visible and held-out and report the gap.
   **This must be done before the examples arm runs**, or that arm cannot be
   distinguished from gaming: the gap grows 28 points per 10x code size.
4. **CLEVER** ([arXiv:2505.13938](https://arxiv.org/abs/2505.13938)) — spec
   compile 71-87% against spec prove 0.62-1.86%; the sharpest "compiles is not
   correct" datum there is.
5. **Clover** ([arXiv:2310.17807](https://arxiv.org/abs/2310.17807),
   [repo](https://github.com/ChuyueSun/Clover)) — already applied, see below.

### Work stopped mid-flight, and how to resume each

| what | where it stopped | how to pick it up |
|---|---|---|
| **three seed arms** | 232/232 generated, kernel cells computed, `kernels.md` never assembled | `bash t/finish_seeds.sh`; if `/dev/shm` was cleared, `bash t/grade_lab.sh heldout <tag>` regrades from the answers, which survive |
| **prover-train2** | **450 of 2,354** training problems answered, ungraded | `bash t/grow_pool.sh prover-train2`; resume generation with `/tmp/gen_prover2.sh` on the lab, which skips answered problems |
| **phi4-mini-g** | 56 of 232 generated, never graded | `/tmp/gen_phig.sh` on the lab, then grade. **This retires the strongest objection to the tie**: Phi decoding against our grammar cannot emit unparseable output |
| **the examples arm** | implemented and corpus built, never trained | `t/out/loop/corpus-ex-headed.txt` exists; the four commands are at the end of `internal/RESEARCH-NEXT-2026-09-20.md`. Do SpecBench's visible/held-out split first |
| **`/tmp/finish_tables.sh`** | was assembling seed tables when the session ended | check `~/tup/t/out/tables.done` on the lab; `finish_seeds.sh` waits for exactly that |

Scripts in `/tmp` do not survive a reboot. The two that matter are committed:
`t/finish_seeds.sh` and `t/grow_pool.sh`.

### What was applied from the literature, and what it measured

**Clover's third consistency edge** ([arXiv:2310.17807](https://arxiv.org/abs/2310.17807),
[ChuyueSun/Clover](https://github.com/ChuyueSun/Clover)) reduces correctness to
consistency between code, docstring and annotation. This repo had two of the
three edges; `t/spec_check.check_points` adds the missing one by evaluating the
model's `ensures` at the problem's own assertions. It catches **62%, 27% and 88%**
of the proven-but-wrong population in three arms and **fired on none of the
eleven clean answers across four sets**.

And the hypothesis it replaced was falsified first: across 388 proved answers
there is **not one weak specification**. The failure is specs that are flatly
false at the problem's own solution — a predicate problem specified as
`r == x + 1`. `locallm/FINDINGS-completeness-2026-09-20.md` has it.

## Traps that cost time today

1. **`t/out` is gitignored.** `git add t/out/score-r8.md` fails silently unless
   you pass `-f`. Three findings documents cited tables that were not in the
   repository until this was caught.
2. **`grade_lab.sh` runs `git pull --ff-only || true` on the lab and it is
   failing.** The lab tree is 19 commits behind origin with 109 dirty entries
   and untracked files that would be overwritten. Grading therefore runs on an
   **older evaluator than this desktop's tree**, which is why every comparison
   regrades a baseline beside the new model. Do not force-reset it; the dirty
   files are other agents' unverified work.
3. **The grading machine has no verdict cache.** Its `run_par.py` is at
   `17d7aaf` and does not import `t/cache.py`; the cache is uncommitted desktop
   work. `--no-cache` is not a flag it accepts.
4. **Do not overlap GPU generation with grading.** Ten generation workers plus
   a 7B model plus 32 grading cells put the load average at 80 and killed the
   ssh carrying the grading.
5. **`pkill -f <pattern>` matches your own command line.** It killed my ssh
   sessions twice. Use a bracket, `pkill -f "name[.]sh"`.
6. **A sentinel file that a wrapper touches after `wait` means "the process
   exited", not "the work finished".** Killing a generator let its wrapper
   touch the sentinel and two chains scored partial answer sets.

## Two commands that do the first two steps for you

    bash t/finish_seeds.sh        # the three seed arms, mid-grade, to a scoreboard
    bash t/grow_pool.sh prover-train2   # grade 450 prover answers, rebuild the pool

Both are committed, both are safe to re-run, and `grow_pool.sh` prints the four
commands that turn the new pool into a scored model with the recipe that tied
Phi. Read them before running them; they are short.

## What to do next, in the order I would do it

1. **Assemble the three seed tables** as above and score them. This answers
   attack 3 and costs minutes.
2. **Grade `prover-train2`'s 450 answers** and rebuild the pool with them:
   `python3 t/spec_experiment.py extract/tests --model prover-train2 --pool v5`,
   then `grade_lab.sh`, then `spec_check.py`, then `loop_dataset.py
   --from-samples <all training tags> prover-train prover-train2 --out-suffix
   r10`. This is the only lever measured to move the absolute number.
3. **Finish `phi4-mini-g`** and grade it. This retires attack 2.
4. **Train the r10 corpus headed**, greedy decode, score. `t/head_align_corpus.py`
   then `locallm/continue_from_checkpoint.py --init
   t/out/source-pretraining-longer-2026-09-19/gpt-seed1337`.
5. **A size curve.** 3.2M and 92M exist; 312M trains at 7,396 tokens a second
   on one shared card (`locallm/FINDINGS-capacity-2026-09-19.md`). Three points
   on the same recipe and evaluator turn a tie into a trend, which is the
   strongest available version of this project's claim.

## Where everything is

| what | where |
|---|---|
| the plan and its finish lines | `ROADMAP.md`, WS-22 |
| today's findings | `locallm/FINDINGS-*-2026-09-19.md` |
| registered predictions | `t/PREDICT-2026-09-19-round7.md`, `-round7b.md`, `-round8.md`, `locallm/PREREG-*` |
| scoreboard tables | `t/out/score-r7.md`, `-r7b.md`, `-r8.md` |
| evaluator provenance | `t/out/evaluator-state-2026-09-19.json` |
| the other agent's channel | `~/.local/state/tup-channel/`, private, `channel.py read --since 0` |
| the overnight watcher | `~/.local/state/tup-overnight/`, `enabled: false` with its reason inside |

The channel holds a review request covering commits `20d5ec6..e1ded69` that was
never answered. Nothing in that range has been reviewed by anyone. The open
doubts are listed in message 7 and they are still open.
