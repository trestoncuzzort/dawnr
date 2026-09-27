# t cross-kernel agreement, 2026-09-27 07:29Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| vericoding_va0074__min_repunit_sum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_va0079__solve | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| vericoding_va0080__solve | vacuous / refuted | verified / refuted | verified / refuted | abstain / abstain | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_va0085__find_minimum_total_distance | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_va0100__solve | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | verified / refuted |
| vericoding_va0123__solve | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| vericoding_va0216__solve | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | verified / refuted |
| vericoding_va0237__solve | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | verified / refuted |
| vericoding_va0253__solve | verified / refuted | verified / unproved | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| vericoding_va0290__solve | verified / unproved | verified / unproved | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | verified / refuted |
| vericoding_va0351__solve | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_va0353__solve | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_va0363__capitalize_first_letter | verified / unproved | verified / unproved | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | verified / refuted |
| vericoding_va0399__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_va0405__solve | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_va0410__solve | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | verified / refuted |
| vericoding_va0429__solve | vacuous / refuted | verified / refuted | verified / refuted | abstain / abstain | unproved / refuted | verified / refuted | verified / refuted |
| vericoding_va0445__solve | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | unproved / refuted |
| vericoding_va0476__solve | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| vericoding_va0482__solve | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | verified / refuted |
| vericoding_va0530__solve | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_va0550__solve | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_va0582__solve_core | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | verified / refuted |
| vericoding_va0654__solve | verified / refuted | verified / unproved | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | verified / refuted |
| vericoding_va0659__solve | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_vd0056__copy | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / timeout | verified / refuted | timeout / refuted |
| vericoding_vd0087__swap_bitvectors | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_vd0287__reverse | verified / refuted | verified / refuted | verified / refuted | verified / timeout | timeout / timeout | verified / refuted | verified / refuted |
| vericoding_vd0367__yarra | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | timeout / timeout | abstain / abstain | malformed / malformed |
| vericoding_vd0432__find_min | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_vd0483__maxArrayReverse | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_vd0509__max | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_vd0588__reverse | verified / refuted | verified / refuted | verified / refuted | verified / timeout | timeout / timeout | unproved / refuted | verified / refuted |
| vericoding_vd0674__count_arrays | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_vd0700__all_elements_equal | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted |
| vericoding_vd0721__is_greater | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / timeout | verified / refuted | unproved / refuted |
| vericoding_vd0729__month_has_31_days | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_vh0107__reverse | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_vj0058__square_nums | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_vj0162__smallest_list_length | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted | unproved / refuted | abstain / abstain | unproved / refuted |
| vericoding_vj0164__string_xor | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| vericoding_vt0014__frombuffer | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / timeout | verified / refuted | verified / refuted |
| vericoding_vt0025__logspace | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_vt0029__ones | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_vt0095__npy_2_pi | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_vt0099__npy_loge10 | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_vt0106__true_ | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_vt0165__argmax | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| vericoding_vt0166__argmin | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| vericoding_vt0233__matrix_power | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| vericoding_vt0297__numpy_cos | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_vt0329__log | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / refuted |
| vericoding_vt0357__sign | verified / refuted | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / refuted | verified / refuted |
| vericoding_vt0360__sinc | verified / refuted | unproved / refuted | verified / refuted | abstain / abstain | verified / refuted | timeout / refuted | verified / refuted |
| vericoding_vt0362__spacing | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_vt0496__legmul | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / refuted |
| vericoding_vt0557__numpy_argmin | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| vericoding_vt0567__nanargmax | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_vt0568__nanargmin | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_vt0580__numpy_cov | verified / refuted | verified / refuted | malformed / malformed | abstain / abstain | abstain / abstain | verified / unproved | verified / refuted |
| vericoding_vt0590__nanmax | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_vt0594__nanpercentile | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_vv0064__reverse_string | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / timeout | verified / refuted | verified / refuted |
| vericoding_vv0171__swap | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_vv0173__swap_bitvectors | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| vericoding_vv0176__swap_simultaneous | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `vericoding_va0074__min_repunit_sum.dfy` 3a835ce0976278a4…, `vericoding_va0074__min_repunit_sum.rs` d341da04c61f3bb9…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| framac | 2 | 19 | vericoding_vj0164__string_xor, vericoding_vt0357__sign |
| lean | 2 | 24 | vericoding_vt0014__frombuffer, vericoding_vv0064__reverse_string |
| rocq | 2 | 20 | vericoding_vt0329__log, vericoding_vt0496__legmul |
| verus | 1 | 16 | vericoding_vt0297__numpy_cos |
| spark | 1 | 6 | vericoding_va0659__solve |
| fstar | 1 | 10 | vericoding_vd0700__all_elements_equal |
| dafny | 0 | 4 | (none) |

Of the 9 tasks in six, 2 are framac alone, 2 are lean alone, 2 are rocq alone, 1 is verus alone, 1 is spark alone, 1 is fstar alone.
