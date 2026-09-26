# Hint-stripped twins: one twin per hint, graded before it is called anything

Written 2026-09-25 for the r12 data build (track W6; `internal/RESEARCH-NEXT-2026-09-20.md`
"four more" item 4, `internal/ROADMAP-LOG.md` WS-19). The tool is `t/twin_hints.py`, its tests
`t/test_twin_hints.py`. Every number below names the command that produced it. No home paths,
hosts or addresses: the lab is `T_LAB` in the gitignored `t/lab-workstation.conf`.

## 1. The idea, and what it is not

`t/twins/` is 426 pairs over 213 programs: each twin is one change to the **body** (off-by-one,
collapse-if, negate-cond, ...), chosen by a measured witness, refuted by all seven kernels. Every
program contributes one family. The idea from the retired `forge/dafny_pairs.py` (git `a736d82`)
is the other family: leave the body alone and remove one **hint**. A verified program with N
hints then yields N twins, each one line away from the program, each naming the line that went,
with the seven kernels as the oracle for both halves. Nothing here needs a teacher model.

What a hint is in t, read off `t/surface.py`'s grammar and `t/check_wf.py`'s gates:

| hint | strippable | why |
|---|---|---|
| a loop's `invariant` | yes | zero or more are allowed by the grammar |
| the task's `requires` | yes | zero or more are allowed; stripping one **widens the precondition**, so this twin can change what the specification says about inputs the program never had to handle |
| a loop's `decreases` | no | `while Expr invariant* decreases Expr` requires it; its absence is a parse error |
| the task's `decreases` | no | check_wf gate 3 (`decreases-selfcall`): a self-recursive body without one is ill-formed |
| a spec fun's `decreases` | no | required by the grammar |
| `assert` | no | t has no assert statement |

The unstrippable ones are counted per program and never emitted: a twin that fails to parse or to
type teaches syntax, not proof (the retired generator found 63 of 782 DafnyBench single strips broke
the parse, and discarded them for the same reason). A stripped twin keeps its body and its `ensures`
byte for byte (asserted per twin over the executable body, the invariants erased), so the program's
tests pass by construction; only the proof side can move.

## 2. Why no twin is a twin until the kernels say so

DafnyBench (arXiv:2406.08467, fetched 2026-09-25 from `ar5iv.labs.arxiv.org/html/2406.08467`,
repository `github.com/sun-wendy/DafnyBench`) removes every hint from a verified file at once and
still finds 113 of its 556 GitHub programs verify with no hints at all; `forge/dafny_pairs.py`
measured single-hint strips on the same benchmark and 210 of 782 (26.9 percent) still verified.
"Hint removed, so the proof fails" is false often enough that assuming it would mint negatives
pointing the wrong way. AlphaVerus (arXiv:2412.06176, fetched 2026-09-25 from
`ar5iv.labs.arxiv.org/html/2412.06176`, repository `github.com/cmu-l3/alphaverus`) keeps only what
the real verifier accepts and adds a filter against specifications weakened to pass, which is
exactly what a stripped `requires` is.

So `twin_hints.py emit` writes every twin with `class: ungraded`, and `classify` reads each twin's
class off its own seven-column row in a `run_par.py` table over the `grade/tasks/` directory it
wrote (the twin's real side; run_par's own ladder twin of the twin is graded alongside and ignored):

| class | rule | what it is |
|---|---|---|
| `redundant` | verified in all seven | not a twin; the hint was decorative for every kernel: data about the lowerings |
| `proof-breaking` | some kernel `unproved`, none `refuted` | the negative the project wants; `breaks_in` names the kernels that needed the hint |
| `behavioural` | some kernel `refuted` | only a `requires` strip can do this: the widened precondition admits an input where the body violates `ensures` or is undefined; `harness.real_witness` finds it at emit time (`witness`), the lowerings put it in the certificate, and the certificate is the only door to REFUTED in every adapter |
| `undecided` | a `timeout`, `tool_error`, `malformed`, `vacuous`, `abstain`, `lower-error` or flaked column and nothing above | not a verdict; re-run before it is anything |

The class is what the kernels say, not what the interpreter predicts: a `requires` strip whose
counterexample lies outside the interpreter's bounded domain reads `proof-breaking` (unproved, no
certificate) even though it is semantically behavioural. The witness is recorded so the two can be
compared.

## 3. The gates

Every source program goes through the same gates the r12 build installed (`t/RUN-NEXT-locallm-r12.md`
A1, A2): held-out ids under every alias (`loop_filter.problem_id` over the task name, the text and the
recorded problem id), the same-task exclusions (`t/decontamination-2026-09-21.json`), and the dev split
(`t/r12-dev-ids.json`, valid for the one split it was drawn from). A source that names any of them is
**refused by name**, printed, and written to `REFUSED.tsv`; without `--skip-refused` a refusal stops
the run. `--split` is required, as it is for the corpus builder: no unscoped twin corpus.

## 4. The census (desktop, 2026-09-25)

    python3 t/twin_hints.py emit --twins t/twins --tasks t/tasks --table t/AGREEMENT.md \
        --split t/out/loop/split-v5.json --out <dir> --skip-refused

| count | |
|---|---:|
| sources: distinct programs verified in all seven (213 from `t/twins`, 31 committed rows of `t/AGREEMENT.md` with `verified` in every column) | 244 |
| refused by the gates (10 `t/twins` programs under same-task exclusions: `apps_124__search`, `apps_2465__divisorGame`, three `mbpp_404__minimum`, `mbpp_451`, `mbpp_498`, `mbpp_504`, two `mbpp_728`; the 4 decontaminated committed tasks `contains`, `digit_sum`, `gcd`, `remainder`) | 14 |
| admitted | 230 |
| admitted programs with at least one strippable hint | 140 |
| twins: one per hint | **358** |
| of which `drop-invariant` | 196 |
| of which `drop-requires` | 162 |
| `drop-requires` twins with an interpreter witness already (predicted behavioural) | 23 |
| cells to grade (seven per twin) | 2,506 |
| unstrippable, counted: loop `decreases` / task `decreases` / spec fun `decreases` / `assert` | 59 / 6 / 9 / 0 |

Against the 426 body twins over the same programs, one hint family adds 358 twins from 140 programs,
2.6 twins per program with a hint (the retired generator's DafnyBench figure was 1.53 pairs per
verified file, after its own verifier filter; this count is before the kernels). The 90 admitted
programs with no hint at all are straight-line tasks; they have body twins already and nothing to
strip.

The same command over the other sources the scope names, read-only from the main tree's `t/out`:

| source | rows verified in all seven | past the gates | with a hint | twins (invariant / requires) | note |
|---|---:|---:|---:|---|---|
| lifted DafnyBench (`t/out/lifted-tasks`, `t/COVERAGE-lifted-785.md`) | 199 | 174 | 128 | 387 (217 / 170) | 25 refused (same-task exclusions; `dafny_synthesis_task_id_269` and `_626` are also held out); one task states a `requires` twice, so its two hints are one twin, counted and said |
| `qwen235-train` (`tasks/` + `kernels.md`) | 59 | 57 | 22 | 56 (35 / 21) | 2 refused |
| `locallm-r8` (`tasks/` + `kernels.md`) | 108 | 0 | - | 0 | every program refused: that set is the held-out evaluation, and every id is an eval id |

So about 800 hint twins are available today from programs already verified in all seven, before any
answer set the queue is still grading.

## 5. The kernel sample (lab, CPU only, `--jobs 4`)

Selection (`--max-programs 20 --max-cells 196`, deterministic): two queues sorted by twins-per-program,
programs with an invariant and programs with only `requires`, taken alternately so both kinds are
in the sample; 17 programs, 28 twins, 196 cells (the 20-program cap was not reached because the
cell cap was). 18 `drop-invariant`, 10 `drop-requires`; 2 of the 10 carry an interpreter witness
(`apps_2930__summation` at `num=-2`, `divmod_pair` at `x=0, y=-1`).

    python3 t/twin_hints.py emit --twins t/twins --tasks t/tasks --table t/AGREEMENT.md \
        --split t/out/loop/split-v5.json --out <scratch>/sample --max-programs 20 --max-cells 196 --skip-refused
    # on the lab, in this track's own checkout, after t/stall_check.py printed clean and the
    # 1-minute load was under 84:
    CUDA_VISIBLE_DEVICES= nice -n 19 python3 run_par.py --tasks <scratch>/sample/grade/tasks \
        --out <scratch>/sample/grade/out --table <scratch>/sample/grade/table.md --jobs 4 --no-cache
    python3 t/twin_hints.py classify --out <scratch>/sample --table <scratch>/sample/grade/table.md

**Not run on 2026-09-25.** The precondition was a clean `t/stall_check.py` and a 1-minute load under
84 on the lab. The load was 15 to 31 all evening; `stall_check` was never clean: the six orphaned z3
solvers of section 7 were alive from 20:06 through 20:50, and this track kills nothing on the shared
machine (the remedy is one line for whoever owns the lab session: the six pids `stall_check` prints).
Everything else is in place: the sample directory (28 twins, 196 cells, the renamed `grade/tasks/`,
the manifest) is emitted and synced to this track's own lab checkout with the tests passing there,
all seven kernels answer `run_par.probe_backends()` from that checkout (dafny 4.11.0, verus
0.2026.08.30, gnatprove FSF 16.1.0, frama-c 33.0, Lean 4.33.1, Rocq 9.2, F\* 2026.08.30), and the
run is the three commands above followed by `classify`. The per-class and per-kernel counts the
sample was to produce are therefore not in this report; the README `classify` writes carries both
tables (`## Classes`, `## Per kernel`) the moment the table exists, as the synthetic-table test
`test_classify_updates_pairs_index_and_readme` and the CLI check on a copy of the sample show.

What the sample will answer, registered before the run: (1) the redundant share among the 18
invariant strips (the retired generator's DafnyBench figure was 26.9 percent of single strips still
verifying, in one kernel; seven kernels can only lower it, since one unproved column is enough);
(2) whether the 2 requires strips with an interpreter witness (`apps_2930__summation`, `divmod_pair`)
read `behavioural` in all seven, which is the certificate path working on a real witness; (3) whether
the recursive `factorial` and `fib` requires strips read `proof-breaking` through the termination
obligation (`decreases n` with `n` unconstrained) rather than `behavioural` (the interpreter's search
hit `RecursionError` there and recorded no witness); (4) which kernel needs hints most, per
`breaks_in`.

## 6. The full run is a queue step

Not run here (2,506 cells). The exact commands, in this order, on the lab through the r12 data
queue's own admission gate (`bash t/r12_data_queue.sh gate --grading`), never through `grade_lab.sh`:

    python3 t/twin_hints.py emit --twins t/twins --tasks t/tasks --table t/AGREEMENT.md \
        --split t/out/loop/split-v5.json --out t/out/twins-hints --skip-refused
    CUDA_VISIBLE_DEVICES= nice -n 19 python3 t/run_par.py --tasks t/out/twins-hints/grade/tasks \
        --out t/out/twins-hints/grade/out --table t/out/twins-hints/grade/table.md --jobs 4 --no-cache
    python3 t/twin_hints.py classify --out t/out/twins-hints --table t/out/twins-hints/grade/table.md

`--no-cache` for the reason `t/DATA-r12.md` gives: run_par caches UNPROVED, and a load-induced
UNPROVED would be kept for good; the class of a twin rests on UNPROVED, so every cell is measured.
The sample's rate is not measured (section 5); at the committed matrix's rate on the lab (242 cells in
the A3 regrade), 2,506 cells at `--jobs 4` is a few hours. The same three commands over a graded answer
set (`--tasks <set>/tasks --table <set>/kernels.md --written-by <tag>`) or the lifted sweep
(`--tasks t/out/lifted-tasks --table t/COVERAGE-lifted-785.md --written-by lifted`) extend the corpus;
`emit` into the same `--out` adds to the pairs on disk and regenerates the index.

## 7. What the lab looked like, and a finding about A5

Before the sample could run, `t/stall_check.py` in the lab's own checkout reported six ORPHAN z3
processes (`z3 rlimit 16450000 -smt2 ...`), all started within one second at 20:06:36 in six
different `/tmp/t-spark-*/gnatprove` work directories, since deleted: one SPARK cell of a task named
`apps_190_x_findlength` (three flake runs of the real and three of its twin, `verifiers.cell_pair`'s
six concurrent calls), whose gnatprove was killed by the wall backstop while its solvers were not.
Each z3 is its own process-group leader (`PGID = PID`, inside the gnatprove session's `SID`): why3
puts every prover in a process group of its own, so the r12 blocker A5 fix, which kills the prover's
process group on every exit path, does not reach a z3 under gnatprove. A kill of the whole session
(every process whose `SID` is the cell's), or of the provers `stall_check` itself lists, would. Until
then every gate that reads `stall_check` (the r12 data queue's own admission, this track's precondition)
is refused by solvers nobody is waiting for. Nothing was killed here; the state is reported.

## 8. What this does not claim

- A twin's class is a statement about seven lowerings and seven kernels at their default budgets on
  the day, not about the hint's mathematical necessity. `redundant` means no kernel needed it, which
  is about the lowerings' own preludes as much as about the hint.
- The `behavioural` witness search is bounded (`interp.MAX_POINTS`); its absence is not evidence that
  a stripped `requires` is harmless.
- Nothing here is training data yet. `loop_dataset.py` reads the loop's pair files, not this layout;
  turning `proof-breaking` and `behavioural` twins into `pairs-*.jsonl` rows is a separate change
  (callers_to_update in the track's result), and `redundant` twins must never become negatives.
