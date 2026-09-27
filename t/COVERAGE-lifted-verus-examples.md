# t cross-kernel agreement, 2026-09-26 23:39Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| verus_examples_guide_const_add_one__add_one | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| verus_examples_guide_modes_compute_min3__compute_min3 | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| verus_examples_guide_overflow_compute_sum_limited__compute_sum_limited | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| verus_examples_guide_requires_ensures_edit_octuple__octuple | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| verus_examples_integers_test0__test0 | verified / decorative | verified / decorative | verified / decorative | verified / decorative | verified / decorative | verified / decorative | verified / decorative |
| verus_examples_nevd_script_fibo_impl__fibo_impl | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | unproved / unproved | unproved / refuted |
| verus_examples_nevd_script_max__max | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
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

Verdict basis: every source file hashed; e.g. `verus_examples_guide_const_add_one__add_one.dfy` dec98c8d91f39896…, `verus_examples_guide_const_add_one__add_one.rs` 3d05cf40df37e3a1…

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
