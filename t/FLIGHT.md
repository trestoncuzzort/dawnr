# t cross-kernel agreement, 2026-10-07 23:29Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| px4_alpha_update | abstain / abstain | abstain / abstain | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| px4_constrain | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| px4_constrain_f | abstain / abstain | abstain / abstain | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| px4_hysteresis_holds | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | verified / refuted |
| px4_hysteresis_set | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| px4_hysteresis_switches | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | verified / refuted |
| px4_hysteresis_update | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| px4_interp_index | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| px4_interpolate | abstain / abstain | abstain / abstain | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| px4_is_in_range | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| px4_lerp | abstain / abstain | abstain / abstain | verified / refuted | timeout / timeout | abstain / abstain | abstain / abstain | abstain / abstain |
| px4_max | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| px4_max3 | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| px4_min | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| px4_min3 | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| px4_negate_i16 | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| px4_rb_pop_front | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| px4_rb_push_back | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| px4_rb_space_available | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| px4_sign | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| px4_sign_from_bool | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| px4_sign_no_zero | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| px4_slew_update | abstain / abstain | abstain / abstain | timeout / refuted | verified / refuted (FLAKED) | abstain / abstain | abstain / abstain | abstain / abstain |
| px4_sq | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| px4_wrap_bin | timeout / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| px4_wrap_bin_72 | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| px4_wrap_int | timeout / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | verified / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `px4_constrain.dfy` bcade8d84b47b4a3…, `px4_constrain.rs` 884cbeb1b9e257a1…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| rocq | 2 | 5 | px4_hysteresis_holds, px4_hysteresis_switches |
| dafny | 0 | 5 | (none) |
| verus | 0 | 5 | (none) |
| spark | 0 | 2 | (none) |
| framac | 0 | 3 | (none) |
| lean | 0 | 5 | (none) |
| fstar | 0 | 3 | (none) |

Of the 2 tasks in six, 2 are rocq alone.

## Per kernel

| kernel | carried | real verified | twin refuted where the real is verified | abstains by name |
|---|---|---|---|---|
| dafny | 22 | 20 | 20 of 20 (100%) | 5 |
| verus | 22 | 20 | 20 of 20 (100%) | 5 |
| spark | 27 | 23 | 23 of 23 (100%) | 0 |
| framac | 27 | 23 | 23 of 23 (100%) | 0 |
| lean | 22 | 20 | 20 of 20 (100%) | 5 |
| rocq | 22 | 18 | 18 of 18 (100%) | 5 |
| fstar | 22 | 22 | 22 of 22 (100%) | 5 |

Verified with the twin refuted in all seven columns: 18 of 27 tasks.
