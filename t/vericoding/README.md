# Vericoding tasks in t (D8)

These tasks restate verified solutions from the [vericoding benchmark](https://github.com/Beneficial-AI-Foundation/vericoding)
(arXiv 2509.22908): 66 from its Verus track (`verus/`) and 16 from its Lean track (`lean/`). It is licensed under the
MIT License; a copy is in `LICENSE-vericoding`. dawnr's lifter (github.com/trestoncuzzort/dawnr,
`t/lift_vericoding.py`) translated each solution whose constructs t states, in September 2026. The commit read was
not recorded; the branch head on 2026-10-07 is b265a3b2bce31e09d264306f419e810d02f98f44. File names keep vericoding's
task ids: `va`/`vd`/`vt` prefixes name the source collection the benchmark translated from.

The selection is biased toward programs over integers, booleans and sequences; numbers measured here describe these
tasks, not the benchmark.

`t/audit.py --kernel verus` (and `--kernel lean`) measures each specification. A vericoding task is solved by any
program the kernel verifies against its specification, so a survivor the kernel proves is a wrong program that would
count as a solution. The tables are `t/AUDIT-VERICODING-VERUS.md` and `t/AUDIT-VERICODING-LEAN.md` (PREDICT T56).
