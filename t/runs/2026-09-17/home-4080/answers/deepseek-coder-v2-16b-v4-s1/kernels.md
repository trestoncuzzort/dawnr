# t cross-kernel agreement, 2026-09-18 01:31Z

Cell = real outcome / twin outcome. Agreement means `verified / refuted` in every present column. A real-VERIFIED, twin-VERIFIED cell reads `verified / decorative` (the spec cannot tell real and twin apart) or `verified / unsound` (the twin's own measured witness says a sound kernel must refute it, and this one did not); neither counts as agreement.

| task | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| mbpp_112__perimeter | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_118__string_to_list | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| mbpp_135__hexagonal_num | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_162__sum_series | unproved / refuted | unproved / refuted | timeout / refuted | vacuous / vacuous | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_171__perimeter_pentagon | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_173__remove_splchar | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_17__square_perimeter | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_227__min_of_three | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_234__volume_cube | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_238__number_of_substrings | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_266__lateralsurface_cube | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_268__find_star_num | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_279__is_num_decagonal | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_345__diff_consecutivenums | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_356__find_angle | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_404__minimum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_441__surfacearea_cube | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_447__cube_nums | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| mbpp_454__text_match_wordz | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_458__rectangle_area | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_503__add_consecutive_nums | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_504__sum_Of_Series | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_586__split_Arr | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| mbpp_643__text_match_wordz_middle | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_654__rectangle_perimeter | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_672__max_of_three | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_676__remove_extra_char | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / refuted |
| mbpp_690__mul_consecutive_nums | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_708__Convert | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| mbpp_727__remove_char | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | timeout / refuted | unproved / refuted |
| mbpp_739__find_Index | refuted / refuted | refuted / refuted | malformed / malformed | abstain / abstain | unproved / unproved | refuted / refuted | abstain / abstain |
| mbpp_789__perimeter_polygon | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| mbpp_790__even_position | refuted / refuted | refuted / refuted | refuted / refuted | timeout / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_823__check_substring | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | timeout / unproved | abstain / abstain |
| mbpp_89__closest_num | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| mbpp_908__find_fixed_point | refuted / refuted | refuted / refuted | unproved / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |

Kernels present: 7 of 7 (dafny, verus, spark, framac, lean, rocq, fstar)

Backends:
- dafny: dafny 4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2
- verus: verus 0.2026.08.30.b432e82
- spark: gnatprove FSF 16.1.0 / Why3 for gnatprove version 1.8.2+git
- framac: frama-c 33.0 (Arsenic) / alt-ergo 2.4.3-free
- lean: Lean (version 4.33.1
- rocq: The Rocq Prover, version 9.2
- fstar: F* 2026.08.30 / platform=Linux_x86_64 / system=Unix / compiler=OCaml 5.3.0 / date=2026-08-30 16:26:18 +0000 / commit=2b82aefeff37f78509c876844954b07fcb8813ff

Verdict basis: every source file hashed; e.g. `mbpp_112__perimeter.dfy` 9fa768b7c6e39746…, `mbpp_112__perimeter.rs` 9083b8626d1abc08…

## Sole blockers

| kernel | sole blocker of | co-blocker of | tasks it alone keeps out of all seven |
|---|---|---|---|
| framac | 1 | 1 | mbpp_586__split_Arr |
| rocq | 1 | 1 | mbpp_676__remove_extra_char |
| dafny | 0 | 0 | (none) |
| verus | 0 | 0 | (none) |
| spark | 0 | 0 | (none) |
| lean | 0 | 0 | (none) |
| fstar | 0 | 1 | (none) |

Of the 2 tasks in six, 1 is framac alone, 1 is rocq alone.
