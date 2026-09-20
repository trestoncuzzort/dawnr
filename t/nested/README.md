# Nested loops: the shape the corpus could not hold, now closed

`has_duplicate.t` is a correct nested-loop task written by hand, with invariants on both loops. It
was kept out of `t/tasks/` while it could not read `verified / refuted` in all seven, so that
promoting it would not move the committed matrix's headline before the work was done. It exists to
make WS-20's first move measurable.

**All seven now agree**, measured 2026-09-20 (`python3 t/run_par.py --tasks t/nested --jobs 7`,
no cache, 42 kernel runs, every verdict taken here):

| kernel | real | twin |
|---|---|---|
| dafny | verified | refuted |
| verus | verified | refuted |
| spark | verified | refuted |
| framac | verified | refuted |
| lean | verified | refuted |
| rocq | verified | refuted |
| fstar | verified | refuted |

Twin operator `collapse-if`, separating witness `s=[0, 1]`: the real program answers False, the twin
answers True. `FULL AGREEMENT`.

For the record, this is where it stood on 2026-09-18, because the distance is the point: SPARK's
twin certificate did not reach through two loops, Frama-C's real side timed out, and Lean, Rocq and
F\* did not lower nested loops at all, so they abstained on both sides. Two of those turned out to
be honesty defects rather than lowering gaps: Lean could leave a goal unsolved that `sorryAx` then
discharged, so a lowering that proved nothing could read as verified, and Frama-C was not slow at
all, its lowering was emitting an invariant of its own that is false.

The Verus fix of 2026-09-18: a local that the inner loop never assigns was treated as a constant, so
its initializer's fact (`i == 0`) went into the loop helper's `requires` and was false on every
outer iteration after the first. Verus reported a failed precondition and the cell read `malformed`.
`_ro_defining_facts` now drops any name the task body assigns anywhere. The committed matrix was
unchanged by it.

## A trap, if you grade this by hand

**Run it through a login shell.** `t/grade_lab.sh` invokes the driver as `bash -lc '...'` for a
reason: Verus needs rustup on `PATH`, and a plain non-interactive `ssh host 'python3 t/run_par.py
...'` does not source the profile that puts it there. Verus then cannot start and the cell reads
**`malformed`**, which is indistinguishable at a glance from a lowering that really is malformed.
Measured both ways on 2026-09-20: without the login shell this task reads `verus malformed/malformed`
and the run reports DISAGREEMENT; with it, all seven agree. `t/preflight.py` catches the same
condition before a round by refusing a checker whose version cannot be read.

## Why a hand-written task and not one from the corpus

Of 113 graded answers that contain a nested or second loop, Lean and Rocq abstained on every one,
F\* on 106, and of the four kernels that did accept them only 3 answers verified in Dafny. Generated
nested-loop code passes its tests (94 of the 113) and carries no inner-loop invariant, so a
hand-written correct example was needed to tell a lowering gap from a missing invariant.
