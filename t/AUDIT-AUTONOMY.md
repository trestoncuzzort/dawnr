# Specification audit

Every one-edit mutant of each body, classed by the interpreter over the task's bounded domain (t/audit.py): **killed** (the spec rejects its result somewhere), **same** (computes the same everywhere), **diverges** (runs out of steps where the real body ends), **survivor** (computes something different, and the spec accepts it everywhere).

- tasks: 25; audited: 25; not audited: none
- behaviour-changing mutants the specs kill: 812 of 813 (99.9%)
- tasks whose spec admits a survivor: 1 of 25
- dafny: real body verified in 18 of 25; of those, a survivor proved too (a wrong program with a proof) in 1

| task | mutants | killed | same | diverges | survivors | proved by the kernel | a survivor: change at input |
|---|---|---|---|---|---|---|---|
| aabb_overlap | 100 | 100 | 0 | 0 | 0 | 0 |  |
| all_in_range | 34 | 29 | 1 | 4 | 0 | 0 |  |
| arm_check | 18 | 18 | 0 | 0 | 0 | 0 |  |
| battery_level | 34 | 34 | 0 | 0 | 0 | 0 |  |
| clamp_cmd | 22 | 20 | 2 | 0 | 0 | (real abstain) |  |
| crosstrack_side | 92 | 92 | 0 | 0 | 0 | 0 |  |
| debounce | 15 | 15 | 0 | 0 | 0 | 0 |  |
| first_fault | 25 | 23 | 0 | 2 | 0 | 0 |  |
| geofence_box | 56 | 56 | 0 | 0 | 0 | (real abstain) |  |
| grid_cell | 26 | 26 | 0 | 0 | 0 | (real timeout) |  |
| heading_diff | 21 | 21 | 0 | 0 | 0 | 0 |  |
| low_pass_step | 22 | 22 | 0 | 0 | 0 | (real timeout) |  |
| mode_transition | 30 | 28 | 2 | 0 | 0 | 0 |  |
| nearest_index | 26 | 21 | 2 | 2 | 1 | 1 | compare-flip#1: `if d[i] < d[k] {` -> `if d[i] <= d[k] {` at d=[0, 0] -> real 0, twin 1 |
| peak_reading | 24 | 19 | 3 | 2 | 0 | 0 |  |
| pid_step | 76 | 74 | 2 | 0 | 0 | (real abstain) |  |
| readings_in_band | 49 | 43 | 1 | 5 | 0 | 0 |  |
| sample_push | 17 | 14 | 3 | 0 | 0 | 0 |  |
| saturate_all | 12 | 12 | 0 | 0 | 0 | 0 |  |
| stop_distance_ok | 18 | 18 | 0 | 0 | 0 | 0 |  |
| throttle_limit | 18 | 18 | 0 | 0 | 0 | 0 |  |
| ttc_alert | 20 | 20 | 0 | 0 | 0 | (real abstain) |  |
| vote3 | 52 | 47 | 5 | 0 | 0 | (real abstain) |  |
| waypoint_advance | 36 | 36 | 0 | 0 | 0 | 0 |  |
| zero_fill | 6 | 6 | 0 | 0 | 0 | 0 |  |
