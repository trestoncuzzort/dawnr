# Tools

Scripts behind the waves and sweeps of 2026-09-14 to 2026-09-16, kept here because their working copies lived in temporary folders. Paths inside are the lab workstation's; adjust them on another machine.

- `wave-gate.sh <name>`: after merging a wave, the full conformance run, the matrix diff against the committed `t/AGREEMENT.md`, and `t/reproduce.sh --tests`. Writes its before and after files to `$T_SCRATCH` (default `~/.cache/t-gate`).
- `sweep-r27.sh`: the last sweep of the lifted corpus (326 run-ready tasks, 16 jobs, alone on the machine), then the blocker and census tables. Copy it with the next round number and date.
- `lowerprobe.py <task.json>`: runs the twin search and all seven lowerings on one task without any kernel, with time and peak memory. Run it under a memory limit in a subshell, never around the gate or a sweep.
- `sweepdiff.py <old table> <new table>`: cell by cell comparison of two sweep tables.
- `repin-census.py <lifted> <rows> <a7> <a7in>`: moves the pinned numbers in `t/test_mbpp_lifter_census.py` after a sweep.
- `install26.py`: the one-off install of the relift behind sweep r26, kept as a record.
- `workflows/`: the multi-agent scripts of waves Q and R and the design workflow. Wave R was stopped minutes in; the design workflow wrote 152 designs and 40 reviews (in `~/workflows-2026-09-16.zip` on the lab workstation) and no plan.
