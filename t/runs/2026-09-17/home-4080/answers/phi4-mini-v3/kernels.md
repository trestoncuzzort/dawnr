# t cross-kernel agreement, 2026-09-17 20:20Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| mbpp_208__is_decimal | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| mbpp_20__is_woodall | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_269__ascii_value | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_334__check_Validity | refuted / refuted | malformed / malformed | refuted / refuted | refuted / refuted | refuted / refuted | malformed / malformed | refuted / refuted |
| mbpp_345__diff_consecutivenums | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_355__count_Rectangles | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| mbpp_51__check_equilateral | verified / refuted | malformed / malformed | verified / refuted | verified / refuted | verified / refuted | malformed / malformed | verified / refuted |
| mbpp_626__triangle_area | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| mbpp_719__text_match | unproved / refuted | unproved / refuted | unproved / refuted | verified / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_86__centered_hexagonal_number | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_882__parallelogram_perimeter | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_900__match_num | unproved / refuted | unproved / refuted | unproved / refuted | verified / refuted | unproved / refuted | unproved / refuted | unproved / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `mbpp_20__is_woodall.dfy` 0ba5d1a42e637eb3…, `mbpp_20__is_woodall.rs` 8dd1a5c0f88b85bb…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| dafny | 0 | 2 | (none) |
| verus | 0 | 4 | (none) |
| spark | 0 | 2 | (none) |
| framac | 0 | 0 | (none) |
| lean | 0 | 2 | (none) |
| rocq | 0 | 4 | (none) |
| fstar | 0 | 2 | (none) |

Of the 0 tasks in six, none are blocked alone.
