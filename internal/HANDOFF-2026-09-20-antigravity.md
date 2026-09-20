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

## What is running: nothing. All long runs were stopped deliberately

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
