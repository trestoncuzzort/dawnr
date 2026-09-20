# This answer set is UNGRADED, not scored zero

Its `kernels.md` was quarantined on 2026-09-20 as
`kernels.md.INVALID-verus-never-ran`.

Every row read `verus | malformed / malformed`, and the table's own footer said
so: *"Of the 68 tasks in six, 68 are verus alone."* Verus did not disagree with
anything. It never started. Verus needs rustup on `PATH`, a non-login shell
does not provide it, and the harness records a kernel that cannot start as
`malformed`, which is indistinguishable from a lowering that really is
malformed.

Scored as it stood, this set read **0 clean**, which would have been reported as
the recipe failing to reproduce its headline across seeds. It is not a result.

**To grade it properly:** run from the desktop with `bash t/grade_lab.sh heldout locallm-r9-seed7`,
which invokes the driver as `bash -lc` for exactly this reason, and wait for the
lab's load average to come down first (it was 178 on a 120-core box when this was
found, and Lean flakes under contention: `t/RECHECK-lean-2026-09-19.md`).

Predictions for these arms are registered in `t/PREDICT-2026-09-20-seeds.md` and
remain **unmeasured**.
