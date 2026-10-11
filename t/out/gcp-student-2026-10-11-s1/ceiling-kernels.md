# t cross-kernel agreement, 2026-10-11 06:04Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| acsl_count__count | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| all_nonneg | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| clover_abs__abs | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| clover_find__find | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| cs245_verification_tmp_tmp0h_nxhqp_a8_q2__a8Q1 | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| cs357_tmp_tmpn4fsvwzs_lab7_question2__two | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_programs_tmp_tmpcwodh6qh_src_max__max | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| dafny_tmp_tmpmvs2dmry_examples1__abs | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| divmod_pair | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| fib | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| final_project_dafny_tmp_tmpmcywuqox_final_project_3__nonZeroReturn | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| humaneval_dafny_041_car_race_collision__car_race_collision | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| humaneval_dafny_049_modp__modp | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0001__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0075__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0152__computeMinimalSteps | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0399__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0455__solveCookieDistribution | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0484__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0580__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_da0662__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0052__calDiv | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0061__find | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0077__quotient | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0680__replaceBlanksWithChar | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0684__replaceLastElement | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dd0752__squarePyramidSurfaceArea | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dj0048__myfun | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dj0113__elementWiseDivide | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0008__countSumDivisibleBy | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_dv0138__doubleArrayElements | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_la0099__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| verus_examples_recursion_compute_arith_sum__compute_arith_sum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `acsl_count__count.dfy` 9beb5654e7956133…, `acsl_count__count.rs` 21919f36bd11f5fa…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| dafny | 0 | 0 | (none) |
| verus | 0 | 0 | (none) |
| spark | 0 | 0 | (none) |
| framac | 0 | 0 | (none) |
| lean | 0 | 0 | (none) |
| rocq | 0 | 0 | (none) |
| fstar | 0 | 0 | (none) |

Of the 0 tasks in six, none are blocked alone.

## Per kernel

| kernel | carried | real verified | twin refuted where the real is verified | abstains by name |
|---|---|---|---|---|
| dafny | 33 | 33 | 33 of 33 (100%) | 0 |
| verus | 33 | 33 | 33 of 33 (100%) | 0 |
| spark | 33 | 33 | 33 of 33 (100%) | 0 |
| framac | 33 | 33 | 33 of 33 (100%) | 0 |
| lean | 33 | 33 | 33 of 33 (100%) | 0 |
| rocq | 33 | 33 | 33 of 33 (100%) | 0 |
| fstar | 33 | 33 | 33 of 33 (100%) | 0 |

Verified with the twin refuted in all seven columns: 33 of 33 tasks.
