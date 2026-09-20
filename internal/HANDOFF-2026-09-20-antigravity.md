# Handoff for whoever picks this up next

Written 2026-09-19 23:50, rewritten as the final version 2026-09-20. Read
`AGENTS.md` first, then this. Everything here was measured unless it says
otherwise, and where a number was wrong it says that too.

**State of the tree:** desktop and lab are both at the same commit, and the
whole lab runs end to end: corpus, head alignment, training from the pretrained
core, sharded generation on four cards, extract, tests, all seven kernels,
`spec_check`, `spec_scorecard`, `preflight`. Verified 2026-09-20 on 24 problems.
Suite is 418 tests with four known failures listed under "Known-failing".

---

## START HERE: the five things worth doing, in order

1. **Finish `phi4-mini-g` and grade it.** 56 of 232 generated, never graded.
   `/tmp/gen_phig.sh` on the lab, then `bash t/grade_lab.sh heldout phi4-mini-g`.
   This is the single highest-value experiment available because it retires the
   strongest objection to the headline: Phi decoding against `t/t.gbnf` cannot
   emit unparseable output, so it answers "Phi has never seen t".
2. **Grade `prover-train2`'s 450 answers and rebuild the pool.**
   `bash t/grow_pool.sh prover-train2`. This is the only lever measured to move
   the absolute number: its predecessor converted 31 of 88 graded cells into
   clean answers.
3. **Assemble the three seed arms' tables.** `bash t/finish_seeds.sh`. Answers
   attack 3 (no seeds) and costs minutes, not GPU time.
4. **Train the examples arm** — but run `t/example_holdout.py` first or the
   result does not count. See "The examples arm" below.
5. **A size curve.** 3.2M and 92M exist; 312M trains at 7,396 tokens a second on
   one shared card. Three points on one recipe and one evaluator turn a tie into
   a trend, which is the strongest available version of this project's claim.

---

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

**Three fair attacks on that claim. None is answered yet.**

1. **3 of 232 is 1.3%.** Both models fail about 99% of the time, and a tie at
   the floor is a tie in noise. Fixing it means raising the absolute number,
   which means more training data. That is item 2 above.
2. **Phi has never seen t**, so 220 of its 232 answers do not parse. `phi4-mini-g`
   answers this and is 56 of 232 generated, never graded. Item 1 above.
3. **No seeds.** Three arms exist to fix this and are fully generated. Item 3.

`README.md` states all three next to the number. **Do not remove them without
the measurement that retires them.**

---

## Traps. Read this section even if you read nothing else

Each one cost real time or silently corrupted a result.

1. **`t/out` is gitignored.** `git add t/out/score-r8.md` fails silently without
   `-f`. Three findings documents cited tables that were not in the repository
   until this was caught.
2. **`run_par.py` needs a LOGIN shell on the lab, or Verus silently reads
   `malformed`.** `grade_lab.sh` uses `bash -lc '...'` for exactly this: Verus
   needs rustup on `PATH` and a plain `ssh host 'python3 t/run_par.py ...'` does
   not source the profile. The cell then reads `malformed`, indistinguishable
   from a lowering that really is malformed. Measured both ways on `t/nested`:
   without the login shell, `verus malformed/malformed` and DISAGREEMENT; with
   it, all seven agree.
3. **`set --` in a shell script replaces the positional parameters**, and it bit
   twice in one day. `t/gen_fleet.sh` threw away the caller's decoding flags
   until `75a43fa`, so any fleet set older than that was decoded with defaults
   whatever its log says. `t/grade_lab.sh` overwrote its own mode argument until
   `042e35c`, so every `grade_lab.sh <mode>` call after `a6acacb` **exited 0
   having graded nothing**. Use `read -r`.
4. **Adding a head to a training document breaks a reader that does not know
   it.** Three times now, costing 216, then an unknown number, then 24 answers.
   Put the head in `loop_filter.HEAD_LINE` and nowhere else, and make every
   reader call `loop_filter.strip_head`. `t/test_head_handling.py` enforces it.
5. **Do not overlap GPU generation with grading.** Ten generation workers plus a
   7B model plus 32 grading cells put the load average at 80 on a 120-core box
   shared with another user, and the ssh carrying the grading died.
6. **`pkill -f <pattern>` matches your own command line.** It killed my ssh
   sessions twice. Use a bracket: `pkill -f "name[.]sh"`.
7. **A sentinel a wrapper touches after `wait` means "the process exited", not
   "the work finished".** Killing a generator let its wrapper touch the
   sentinel, and two chains scored partial answer sets.
8. **Lean flakes under contention.** `t/RECHECK-lean-2026-09-19.md`: 26 cells
   re-run alone, **17 changed their mind**, and every one of the 26 is Lean. It
   reports `unproved` on answers it proves in 0.0 to 16.6 seconds by itself.
   This is why `preflight.py` refuses a clean answer resting on a flaked cell
   and why `grade_lab.sh` sizes its cells to the machine.
9. **`grade_lab.sh` runs FROM the desktop and ssh's in.** Running it on the lab
   gives `T_LAB: set T_LAB=user@host`, which looks like missing config. It is
   not; you are on the wrong machine.
10. **A tool that cannot run reports something that looks like a verdict.** Two
    instances in one day: Verus above, and the pre-completeness metric below
    scoring a confident `0.000` on answers where the reference never ran.
    Demand a concrete witness before believing an aggregate.

---

## Work stopped mid-flight, and how to resume each

| what | where it stopped | how to pick it up |
|---|---|---|
| **`phi4-mini-g`** | 56 of 232 generated, never graded | `/tmp/gen_phig.sh` on the lab (skips answered problems), then grade. Retires attack 2 |
| **`prover-train2`** | **450 of 2,354** answered, ungraded | `bash t/grow_pool.sh prover-train2`; resume generation with `/tmp/gen_prover2.sh` |
| **three seed arms** | 232/232 generated, cells computed, `kernels.md` never assembled | `bash t/finish_seeds.sh`. If `/dev/shm` was cleared by a reboot, the answers survive and `bash t/grade_lab.sh heldout <tag>` regrades |
| **the examples arm** | implemented, corpus built, never trained | `t/out/loop/corpus-ex-headed.txt` exists; commands at the end of `internal/RESEARCH-NEXT-2026-09-20.md`. Run the holdout split first |

The seed arms' cells are cached, so re-running the driver over the same
directory assembles the table without redoing the proofs:

```bash
cd ~/tup && bash -lc 'python3 t/run_par.py --jobs 24 \
  --tasks /dev/shm/tup-grade/locallm-r9/tasks \
  --out   /dev/shm/tup-grade/locallm-r9/kernels \
  --table /dev/shm/tup-grade/locallm-r9/kernels.md'
```

Then copy each `kernels.md` to `t/out/spec-experiment/<tag>/kernels.md` on the
desktop, run `python3 t/spec_check.py <tags> --pool v5 --n 100 --only clean`,
then `t/score_heldout.py`. Predictions for round 8 are in
`t/PREDICT-2026-09-19-round8.md`; **the seed arms have no registration, and
someone should write one before reading their numbers.**

Scripts in `/tmp` do not survive a reboot. The two that matter are committed:
`t/finish_seeds.sh` and `t/grow_pool.sh`.

### The examples arm has a blocker

`t/example_holdout.py` implements SpecBench's visible/held-out split
([arXiv:2605.21384](https://arxiv.org/abs/2605.21384)) and its null distribution
is measured at −1.65 to +0.00 points. **Run it on the examples arm or that arm's
result cannot be distinguished from gaming**, because the gap grows 28 points
per 10× code size. Anything a model is given, every model it is compared against
must also be given: a held-out comparison run with examples has to regrade its
baselines with examples.

---

## The specification scorecard

    python3 t/spec_scorecard.py --tag <answer-set> [--tag ...]

Prints Spec-Harness / vACT's four quadrants
([arXiv:2604.00280](https://arxiv.org/abs/2604.00280)). Measured on four graded
arms:

| population | post-correctness | post-completeness | pre-correctness |
|---|---:|---:|---:|
| clean | **1.000** everywhere | 1.000, except r4 at **0.500** | 1.000 |
| proven but wrong | **0.000–0.034** | **0.712–0.932** | 0.980–1.000 |

Read it as: the specifications behind proven-but-wrong answers are mostly
*complete* (they reject wrong answers) and almost never *correct* (they do not
hold at the problem's own examples). **Wrong, not weak.** Over-constraint is
essentially absent. The one clean answer at 0.500 post-completeness is the
whitespace specification that returning nothing satisfies.

**pre-completeness is measured as of 2026-09-20** and the reason it was not
turned out to be wrong. It needs no shipped negatives: the problem's own
reference solution is the oracle for the problem's DOMAIN exactly as it already
is for its outputs, so an input the reference refuses to compute is one the
problem does not define. The signal was being drawn in `check_task` and thrown
away by a line reading "the reference refuses this input; not a finding".

**Read `locallm/FINDINGS-pre-completeness-2026-09-20.md` before quoting that
column.** Its first version reported Phi's clean answers at 0.000 against a
27B's 0.455 — a differentiator, and an artifact. t represents a string as a
sequence of ints, the corpus's Python solutions want a `str`, and 54 of 97
measurements came from a reference that never ran. Probes now count only where
the reference is known to run. Honest result: **nine answers of 180 have a
measurable domain boundary**, so this corpus has almost no signal in this
quadrant. Rates print with the count under them; `0.000/1` is one answer.

**Where that quadrant would bite:** APPS and CodeContests carry explicit input
constraints in their statements, are already on disk in `nl/data/`, and the spec
pipeline does not use them.

---

## What to apply from the literature

About 4,000 lines and 287 references across five files in `internal/research/`,
plus 77 repositories catalogued. Reading them all is not the point; this table
is. Everything is CPU-only unless noted.

| apply this | from | to this repo |
|---|---|---|
| **k-sample agreement as an ambiguity detector** | VeriMed, [arXiv:2605.13817](https://arxiv.org/html/2605.13817v1) | sample k specs for one problem, check them against each other with the seven provers, treat disagreement as a located ambiguity with a witness. Their repair ladder is 55.4% → 80.0% → **98.5%** as feedback goes none → textual → counterexample: the strongest argument in the corpus for feeding witnesses back rather than prose |
| **visible vs held-out gap** | SpecBench, [arXiv:2605.21384](https://arxiv.org/abs/2605.21384) | built as `t/example_holdout.py`. **Blocker on the examples arm** |
| **bidirectional equivalence against the reference** | CLEVER [arXiv:2505.13938](https://arxiv.org/abs/2505.13938), VeriEquivBench [arXiv:2510.06296](https://arxiv.org/abs/2510.06296) | **not built.** Prove both `spec(x, ref(x))` and `∀y. spec(x,y) → y = ref(x)` with each of the seven. The second half is the tightness check we lack |
| **verifier feedback into a knowledge base, not weights** | KBSpec, [arXiv:2606.21339](https://arxiv.org/abs/2606.21339) | **not built, and the right shape for us**: t is out-of-distribution for every model, and this reports **14–32%** better verification pass rates with no fine-tuning |
| **mutate the candidate spec, keep variants that still verify** | SpecGen, [arXiv:2401.08807](https://arxiv.org/abs/2401.08807) | **not built.** A repair loop rather than a gate: when a spec fails `check_points`, mutate and retry instead of discarding. 279/385 verifiable vs 247 for the best prior method |
| **provers as each other's reference** | verifier fuzzing, [arXiv:2606.01066](https://arxiv.org/abs/2606.01066) | **not built**, and we are unusually well placed: seven independent provers, so any disagreement is a spec defect or a prover defect. The disagreement rate is a free integrity metric |
| **checkpoint specs at internal program points** | SpecCoder, [arXiv:2607.04232](https://arxiv.org/abs/2607.04232) | **not built.** Our interpreter already emits per-statement states, so intermediate assertions cost nothing. Reported +55.8% spec correctness, +358.1% completeness |
| **isomorphic perturbation** | [arXiv:2604.15149](https://arxiv.org/abs/2604.15149) | **not built.** Rename every identifier and regenerate: a spec that only works under the original naming was keyed to surface cues. Needs generation, so GPU |
| **spectests: implementation-impossible negatives** | SpecRL, [arXiv:2604.05820](https://arxiv.org/abs/2604.05820) | primitive built as `spec_check.mutations`. Their +26.46% came from **rewarding rejection rate during training**, the step not taken |
| **discriminative example choice** | TiCoder, [arXiv:2208.05950](https://arxiv.org/abs/2208.05950) | built as `loop_locallm.discriminative` |
| **third consistency edge** | Clover, [arXiv:2310.17807](https://arxiv.org/abs/2310.17807), [repo](https://github.com/ChuyueSun/Clover) | built as `spec_check.check_points` |
| **exploit model** | AlphaVerus, [arXiv:2412.06176](https://arxiv.org/abs/2412.06176) | built as `spec_check.exploit` |
| **admissibility leg** | VERINA [arXiv:2505.23135](https://arxiv.org/abs/2505.23135), CLEVER | built 2026-09-20 as `check_task`'s pre-completeness |
| **RLVR at small scale and its failure modes** | `internal/research/verifier-feedback-training.md` | **read before any RL.** It collects the wins *and* the papers reporting verifier-filtered training did not help, plus the work showing a noisy verifier makes RL worse than none |

**Order I would take them in:** SpecBench's gap check (already a blocker), then
CLEVER/VeriEquivBench tightness (upgrades a check that already earns its keep),
then KBSpec (the only item addressing out-of-distribution without a training
run). Everything else waits on a GPU.

Repositories worth reading first, from `internal/research/repos-verification.md`:
**Vericoding** ([Beneficial-AI-Foundation/vericoding](https://github.com/Beneficial-AI-Foundation/vericoding),
flagged as the single most relevant repo found), **Clover**, **DafnyBench**,
**dafny-synthesis** ([Mondego/dafny-synthesis](https://github.com/Mondego/dafny-synthesis),
the MBPP-DFY source this project lifts from), and **AutoVerus**
([microsoft/verus-proof-synthesis](https://github.com/microsoft/verus-proof-synthesis)).

**The rule about research agents:** one finished, returned a 30-paper report and
**never wrote its file**; it was recovered by hand. Every later agent was told to
append to disk after each item. **An agent's return value is not a deliverable;
a file is.**

---

## What was measured and did not work, so nobody repeats it

- **A cleaner pool did not help.** `locallm-r8` trained on 79 examples that are
  verified, twin-refuted and confirmed to specify the right problem, replacing a
  pool containing 28 that disagree, and scored exactly what the same recipe
  scored before.
- **A shorter training schedule is worse.** `locallm-r7b-step150`: 92 well
  formed, 0 clean.
- **The synthetic composition curriculum is a dead end at this scale.** Three
  seeds scored 0, 2 and 0 of 323 held-out tasks, and 0 of 203 three-stage tasks
  at every seed.
- **The latent/execution factorial produced no synthesis gain**, and its own
  instrument was wrong: 38 of 38 correct answers sat on tasks a shorter program
  already passed. `t/audit_collapsible.py` is the check.
- **The modern architecture lost at 4000 updates** at every one of three seeds,
  while also being 18.8% slower and reserving 33% more memory, after leading by
  about a quarter at 1000.
- **Pretraining the core did not help this pipeline.** 1 clean of 232, fewer
  well-formed answers than the 3.2M models.

What worked, in order: the signature header (40.8% → 12.1% signature failures,
2 clean → 3), greedy decoding (well formed 136 → 149, clean 1 → 2, free), the
specification check nobody had run (pool 87 → **733** preference pairs), and
sharded generation (about 12×).

---

## What changed 2026-09-20

**Three bugs found by running the lab end to end, all of which reported success
while doing nothing.** `gen_fleet.sh` discarding the caller's flags (`75a43fa`);
the generator not stripping a head off the model's own reply, losing all 24
answers (`f191fab`); `grade_lab.sh` exiting 0 without grading (`042e35c`).
Details in traps 3 and 4.

**Four accepted issues applied** (`2db2a9e`): #44 `signal.SIGHUP` at import
breaking Windows collection; #24 `"${@:-a b c d}"` expanding to one word so
`grade_lab.sh heldout` with no tags looped once against a tag that cannot exist;
#30 the corpus builder applying **no split filter**, now a `--split` flag over
all four entry paths. #27 needed no change. Two deliberate choices in #30:
without `--split` nothing is filtered and it says `NOT APPLIED`, so no existing
caller changes silently; and an unreadable split stops the build, because
filtering nothing while reporting success is how the leak gets built.

**`preflight.py` stopped crying wolf** (`43ace6e`): it counted untracked files
as evaluator drift and printed "not this tree: it grades at 07ab406 … this tree
is at 07ab406". Tracked and untracked are now counted apart.

**Nested loops confirmed closed**: `t/nested` re-run with no cache, 42 kernel
runs, **FULL AGREEMENT**, all seven verified with the twin refuted. The table in
`t/nested/README.md` had been stale since 2026-09-18.

**forge retired** (`e0bace7`), 191 files. Last real commit 2026-09-01, nothing
outside it imported it. What was load-bearing was kept: the bf16-merge rationale
inlined into `t/loop_train.py`, and its OPEN-ITEMS as
`internal/FORGE-RETIRED-2026-09-20.md`.

**Documentation restructured.** `README.md` 357 → 148 lines, the result stated
once, with `SCOREBOARD.md`, `LIMITS.md` and `CORRECTIONS.md` carrying what moved
out. `t/README.md` had claimed only Dafny was live and described an int-only
language with no loops. `locallm/README.md` listed BPE, resume and multi-GPU as
missing when all three exist and are tested.

**`nl/data/` is self-contained.** The five large corpora were symlinks into a
sibling `nl-problems` checkout; they are now real files, verified 50/50 against
`manifest.json` on **both** the desktop and the lab. APPS has no rebuild script,
so those bytes are the working copy of record.

**One git identity.** Four author emails were in the history landing in four
different buckets, including 229 commits credited to no account at all. Both
machines now commit as `trestoncuzzort` via the account's noreply address.

---

## Known-failing before any of this, so do not go hunting

- `t/test_lower_spark_loop_cert.py::test_two_loops_falls_back_to_plain_f_call`
  fails identically with the day's changes stashed.
- On the desktop's `python3`, `t/test_loop_train.py` errors on a missing
  `datasets`, and all of `locallm/` errors on a missing `torch`. Use
  `~/.venv-vllm/bin/python` on the lab.
- `python3 -m unittest discover` additionally picks up `t/test_lab_gui.py`,
  whose tkinter teardown **crashes the whole run and hides the tally**. Exclude
  it when you want a number:
  `ls test_*.py | grep -v test_lab_gui | sed 's/\.py$//' | xargs python3 -m unittest`

---

## Where everything is

| what | where |
|---|---|
| the plan and its finish lines | `ROADMAP.md` WS-22, `internal/ROADMAP-LOG.md` (the roadmap of record) |
| the public claim, short | `README.md`, 148 lines |
| every model's numbers | `SCOREBOARD.md` |
| every caveat | `LIMITS.md` |
| claims that turned out wrong | `CORRECTIONS.md` |
| findings | `locallm/FINDINGS-*.md` |
| registered predictions | `t/PREDICT-*.md`, `locallm/PREREG-*.md` |
| scoreboard tables | `t/out/score-r7.md`, `-r7b.md`, `-r8.md` |
| evaluator provenance | `t/out/evaluator-state-2026-09-19.json` |
| the literature | `internal/research/`, five files |
| machine setup and git identity | `internal/MACHINES.md` |
| the retired pipeline | `internal/FORGE-RETIRED-2026-09-20.md` |
| the other agent's channel | `~/.local/state/tup-channel/`, private local state, never the public repo |

**One thing nobody has done:** the channel holds a review request covering
commits `20d5ec6..e1ded69` that was never answered. Nothing in that range has
been reviewed by anyone, and the open doubts are listed in its message 7.
