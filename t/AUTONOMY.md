# t cross-kernel agreement, 2026-10-07 14:25Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| aabb_overlap | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| all_in_range | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| arm_check | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| battery_level | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| clamp_cmd | abstain / abstain | abstain / abstain | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| crosstrack_side | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| debounce | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| first_fault | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| geofence_box | abstain / abstain | abstain / abstain | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| grid_cell | timeout / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| heading_diff | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| low_pass_step | timeout / refuted | unproved / refuted | verified / refuted | timeout / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| mode_transition | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| nearest_index | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| peak_reading | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| pid_step | abstain / abstain | abstain / abstain | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| readings_in_band | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | verified / refuted | abstain / abstain | verified / refuted |
| sample_push | verified / refuted | unproved / unproved | timeout / refuted | verified / refuted | unproved / refuted | unproved / unproved | unproved / unproved |
| saturate_all | verified / refuted | unproved / unproved | timeout / refuted | verified / refuted | unproved / refuted | unproved / unproved | unproved / unproved |
| stop_distance_ok | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| throttle_limit | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| ttc_alert | abstain / abstain | abstain / abstain | abstain / abstain | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| vote3 | abstain / abstain | abstain / abstain | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| waypoint_advance | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| zero_fill | verified / refuted | verified / unproved | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / unproved |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `aabb_overlap.dfy` 05bec2f762c3002b…, `aabb_overlap.rs` 178270c336965990…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| lean | 1 | 8 | crosstrack_side |
| dafny | 0 | 6 | (none) |
| verus | 0 | 10 | (none) |
| spark | 0 | 4 | (none) |
| framac | 0 | 3 | (none) |
| rocq | 0 | 10 | (none) |
| fstar | 0 | 7 | (none) |

Of the 1 tasks in six, 1 is lean alone.

## Per kernel

| kernel | carried | real verified | twin refuted where the real is verified | abstains by name |
|---|---|---|---|---|
| dafny | 20 | 18 | 18 of 18 (100%) | 5 |
| verus | 20 | 16 | 14 of 16 (87%) | 5 |
| spark | 24 | 20 | 20 of 20 (100%) | 1 |
| framac | 24 | 21 | 21 of 21 (100%) | 1 |
| lean | 20 | 15 | 15 of 15 (100%) | 5 |
| rocq | 19 | 15 | 14 of 15 (93%) | 6 |
| fstar | 20 | 18 | 17 of 18 (94%) | 5 |

Verified with the twin refuted in all seven columns: 13 of 25 tasks.
