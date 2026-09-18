# t cross-kernel agreement, 2026-09-18 00:10Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| he_30__get_positive | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | timeout / timeout | timeout / refuted | verified / refuted |
| he_42__incr_list | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| he_48__is_palindrome | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| he_51__remove_vowels | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / timeout | abstain / abstain |
| he_60__sum_to_n | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| he_62__derivative | refuted / refuted | malformed / malformed | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `he_30__get_positive.dfy` 59c49f5a346d3c54…, `he_30__get_positive.rs` 70749d0d96de0ba0…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| spark | 1 | 0 | he_60__sum_to_n |
| dafny | 0 | 0 | (none) |
| verus | 0 | 1 | (none) |
| framac | 0 | 1 | (none) |
| lean | 0 | 1 | (none) |
| rocq | 0 | 2 | (none) |
| fstar | 0 | 1 | (none) |

Of the 1 tasks in six, 1 is spark alone.
