# t cross-kernel agreement, 2026-09-27 07:23Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| acsl_accumulate__accumulate | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| acsl_adjacent_find__adjacent_find | verified / refuted | verified / refuted | verified / timeout | verified / refuted | unproved / unproved | unproved / unproved | verified / refuted |
| acsl_clamp__clamp | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| acsl_count__count | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| acsl_find__find | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| acsl_find2__find2 | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| acsl_find3__find3 | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / unproved | unproved / refuted |
| acsl_find_if_not__find_if_not | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / unproved | unproved / refuted |
| acsl_find_last__find_last | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / refuted |
| acsl_inner_product__inner_product | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| acsl_is_heap_until__is_heap_until | unproved / refuted | timeout / refuted | timeout / refuted | verified / refuted | unproved / unproved | unproved / timeout | unproved / refuted |
| acsl_is_sorted_until__is_sorted_until | unproved / refuted | timeout / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / unproved | unproved / refuted |
| acsl_max_element__max_element | verified / refuted | verified / refuted | verified / unproved | verified / refuted | malformed / unproved | unproved / unproved | verified / refuted |
| acsl_max_element2__max_element2 | verified / refuted | verified / refuted | verified / unproved | verified / refuted | malformed / unproved | unproved / unproved | verified / refuted |
| acsl_min_element__min_element | verified / refuted | verified / refuted | verified / timeout | verified / refuted | malformed / unproved | unproved / unproved | verified / refuted |
| acsl_mismatch__mismatch | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `acsl_accumulate__accumulate.dfy` f1ace29e4f38306e…, `acsl_accumulate__accumulate.rs` be7209899d450a57…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| lean | 1 | 6 | acsl_accumulate__accumulate |
| rocq | 1 | 5 | acsl_find_last__find_last |
| dafny | 0 | 1 | (none) |
| verus | 0 | 2 | (none) |
| spark | 0 | 5 | (none) |
| framac | 0 | 0 | (none) |
| fstar | 0 | 1 | (none) |

Of the 2 tasks in six, 1 is lean alone, 1 is rocq alone.
