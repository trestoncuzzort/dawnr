# Nested loops, the shape the corpus cannot hold yet

`has_duplicate.t` is a correct nested-loop task written by hand, with invariants on both loops, kept here rather
than in `t/tasks/` because it does not yet read `verified / refuted` in all seven: promoting it would change the
committed matrix's headline before the work is done. It exists to make WS-20's first move measurable.

Where it stands, graded on 2026-09-18 (`python3 t/run_par.py --tasks t/nested`):

| kernel | real | twin | what is in the way |
|---|---|---|---|
| dafny | verified | refuted | nothing |
| verus | verified | refuted | nothing, since the fix of 2026-09-18 below |
| spark | verified | unproved | the twin's certificate does not reach through two loops |
| framac | timeout | refuted | the real side times out |
| lean | abstain | abstain | nested loops are not lowered |
| rocq | abstain | abstain | nested loops are not lowered |
| fstar | abstain | abstain | more than one loop per body is not lowered |

The Verus fix: a local that the inner loop never assigns was treated as a constant, so its initializer's fact
(`i == 0`) went into the loop helper's `requires` and was false on every outer iteration after the first. Verus
reported a failed precondition and the cell read `malformed`. `_ro_defining_facts` now drops any name the task
body assigns anywhere. The committed 34-task matrix is unchanged by it.

Why this task and not one from the corpus: of 113 graded answers that contain a nested or second loop, Lean and
Rocq abstain on every one, F\* on 106, and of the four kernels that do accept them only 3 answers verified in
Dafny. Generated nested-loop code passes its tests (94 of the 113) and carries no inner-loop invariant, so a
hand-written correct example was needed to tell a lowering gap from a missing invariant.
