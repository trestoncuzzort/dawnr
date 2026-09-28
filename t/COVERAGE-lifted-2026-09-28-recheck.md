# t cross-kernel agreement, 2026-09-28 23:52Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| vericoding_da0292__canFormat | verified / unproved | verified / unproved | abstain / abstain | verified / timeout | abstain / abstain | unproved / unproved | unproved / unproved |
| vericoding_da0292__solve | unproved / refuted | unproved / refuted | abstain / abstain | timeout / timeout | abstain / abstain | unproved / malformed | abstain / abstain |
| vericoding_dd0750__interleave | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / refuted |
| vericoding_dj0068__countIdenticalPosition | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / unproved | verified / refuted |
| vericoding_dj0105__interleave | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_dj0158__replace | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `vericoding_da0292__canFormat.dfy` 5c65f1715fb75269…, `vericoding_da0292__canFormat.rs` 9aba438272445296…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| lean | 2 | 1 | vericoding_dd0750__interleave, vericoding_dj0105__interleave |
| dafny | 0 | 1 | (none) |
| verus | 0 | 1 | (none) |
| spark | 0 | 1 | (none) |
| framac | 0 | 1 | (none) |
| rocq | 0 | 1 | (none) |
| fstar | 0 | 0 | (none) |

Of the 2 tasks in six, 2 are lean alone.
