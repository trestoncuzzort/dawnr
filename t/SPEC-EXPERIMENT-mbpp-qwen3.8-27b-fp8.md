# The spec experiment on MBPP: qwen3.8-27b-fp8

ROADMAP 12.6. One reply per problem, temperature 0, fixed seed; the
prompt is `spec_experiment.build_prompt` (grammar, five committed tasks
as examples, the problem text and its three assertions). Every stage
is a count, every refusal is named, and the two failures 12.6 keeps
apart are kept apart here: a task that VERIFIES with a REFUTED twin,
and a task that passes the problem's own tests.

## Stages

| stage | count |
|---|---:|
| MBPP problems whose tests are in t's fragment (the pool) | 368 |
| replies recorded | 368 |
| replies with a t block | 331 |
| blocks that parse | 208 |
| tasks that are well-formed (graded below) | 143 |

Refusals, by named reason:

- 17 x `parse: <string>:N:N: expected 't', found 'spec' [Task]`
- 12 x `parse: <string>:N:N: expected ')', found 'ensures' [Expr]`
- 10 x `wf: bool literal in a vN task [SPEC: the bool literal is a vN construct (G`
- 9 x `parse: <string>:N:N: 'var' does not start an expression [Expr]`
- 9 x `parse: <string>:N:N: expected ')', found '{' [Expr]`
- 8 x `parse: <string>:N:N: unexpected character '^' [Id]`
- 6 x `parse: <string>:N:N: expected ')', found 'of' [Expr]`
- 6 x `wf: == wants two ints, two bools, two seqs, two nested seqs, or two pairs `
- 5 x `parse: <string>:N:N: 'end of input' does not start an expression [Expr]`
- 5 x `wf: vN expression form in a vN task [SPEC: ite/forall/exists/call are vN e`
- 4 x `wf: task decreases without a self-call [SPEC: a task decreases requires a `
- 4 x `parse: <string>:N:N: expected ')', found 'else' [Expr]`
- 4 x `wf: vN has int only [SPEC: vN has int only]`
- 4 x `wf: implies over non-bool [SPEC: and/or/not/implies are bool-only]`
- 3 x `parse: <string>:N:N: expected 'in', found ':' [Expr]`
- 3 x `wf: quantifier body is not bool [SPEC: a quantifier's body must be bool (G`
- 3 x `wf: operator 'div' not in vN [SPEC: an operator must be in the declared ve`
- 3 x `parse: <string>:N:N: expected ']', found ':' [Expr]`
- 3 x `parse: RecursionError: maximum recursion depth exceeded`
- 3 x `parse: <string>:N:N: unterminated literal [Strings as sequences of code point`
- 2 x `parse: <string>:N:N: 'exists' does not start an expression [Expr]`
- 2 x `parse: <string>:N:N: expected 't', found 'var' [Task]`
- 2 x `wf: * over non-int [SPEC: + - * neg div mod are int-only]`
- 2 x `parse: <string>:N:N: '..' does not start an expression [Expr]`
- 2 x `parse: <string>:N:N: expected 't', found 'assert' [Task]`

## The problem's own tests (interp on the MBPP assertions)

| outcome | tasks |
|---|---:|
| pass | 116 |
| fail | 22 |
| requires-excluded | 2 |
| undefined | 3 |

## The seven kernels (real / twin), over the well-formed tasks

| kernel | verified / refuted | of tasks |
|---|---:|---:|
| dafny | 62 | 143 |
| verus | 59 | 143 |
| spark | 55 | 143 |
| framac | 59 | 143 |
| lean | 58 | 143 |
| rocq | 56 | 143 |
| fstar | 58 | 143 |

| columns counting | 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0 |
|---|---|---|---|---|---|---|---|---|
| tasks | 47 | 7 | 3 | 3 | 2 | 1 | 1 | 79 |

Tasks with no twin at all (every mutation on the ladder computes what the real body computes, or no input satisfies requires): 0.

## 12.6's table: verifies with a refuted twin, against passes its tests

| verifies with refuted twin in | tests pass | tests fail | requires-excluded | undefined | signature |
|---|---:|---:|---:|---:|---:|
| all seven | 44 | 2 | 1 | 0 | 0 |
| some column | 13 | 4 | 0 | 0 | 0 |
| none | 59 | 16 | 1 | 3 | 0 |

**44 of 368 problems** got a task that verifies with a refuted twin in all seven columns and passes its tests; 57 in at least one column. Verified-with-twin but failing its tests, the class 12.6 warns about: 2 in all seven, 4 in some column.

MBPP-DFY subset: 67 pool problems are MBPP-DFY problems (ROADMAP 16.2's family); 37 of them reached the kernels and 18 verify in all seven and pass their tests.

## Every task

| task_id | task | columns counting | tests | dafny | verus | spark | framac | lean | rocq | fstar |
|---:|---|---:|---|---|---|---|---|---|---|---|
| 5 | mbpp_5__count_ways | 0 | fail | unproved / unproved | unproved / refuted | unproved / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 14 | mbpp_14__find_Volume | 0 | pass | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 17 | mbpp_17__square_perimeter | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 19 | mbpp_19__test_duplicate | 0 | pass | unproved / refuted | unproved / refuted | unproved / timeout | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 22 | mbpp_22__find_first_duplicate | 0 | pass | unproved / refuted | unproved / refuted | unproved / unproved | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 28 | mbpp_28__binomial_Coeff | 0 | pass | unproved / unproved | unproved / refuted | timeout / refuted | timeout / unproved | unproved / unproved | unproved / unproved | unproved / refuted |
| 34 | mbpp_34__find_missing | 0 | requires-excluded | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 35 | mbpp_35__find_rect_num | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 36 | mbpp_36__find_Nth_Digit | 0 | undefined | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 46 | mbpp_46__test_distinct | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 47 | mbpp_47__compute_Last_Digit | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 52 | mbpp_52__parallelogram_area | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 55 | mbpp_55__tn_gp | 0 | pass | unproved / unproved | unproved / refuted | timeout / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 59 | mbpp_59__is_octagonal | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 68 | mbpp_68__is_Monotonic | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | timeout / timeout | unproved / refuted |
| 69 | mbpp_69__is_sublist | 0 | pass | unproved / unproved | malformed / malformed | timeout / timeout | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 86 | mbpp_86__centered_hexagonal_number | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 89 | mbpp_89__closest_num | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 93 | mbpp_93__power | 0 | pass | unproved / unproved | unproved / refuted | unproved / refuted | malformed / malformed | unproved / unproved | unproved / unproved | unproved / refuted |
| 103 | mbpp_103__eulerian_num | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / timeout |
| 112 | mbpp_112__perimeter | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 119 | mbpp_119__search | 0 | fail | unproved / refuted | unproved / refuted | timeout / timeout | refuted / refuted | unproved / refuted | refuted / refuted | unproved / refuted |
| 127 | mbpp_127__multiply_int | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 135 | mbpp_135__hexagonal_num | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 138 | mbpp_138__is_Sum_Of_Powers_Of_Two | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 151 | mbpp_151__is_coprime | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 167 | mbpp_167__next_Power_Of_2 | 0 | pass | unproved / unproved | refuted / refuted | refuted / refuted | refuted / refuted | unproved / unproved | unproved / unproved | refuted / refuted |
| 169 | mbpp_169__get_pell | 0 | pass | unproved / unproved | unproved / refuted | unproved / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 171 | mbpp_171__perimeter_pentagon | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 176 | mbpp_176__perimeter_triangle | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 184 | mbpp_184__greater_specificnum | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | malformed / refuted | unproved / refuted |
| 194 | mbpp_194__octal_To_Decimal | 0 | undefined | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 195 | mbpp_195__first | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 199 | mbpp_199__highest_Power_of_2 | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 221 | mbpp_221__first_even | 0 | pass | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 224 | mbpp_224__count_Set_Bits | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted |
| 227 | mbpp_227__min_of_three | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 234 | mbpp_234__volume_cube | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 236 | mbpp_236__No_of_Triangle | 1 | pass | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 244 | mbpp_244__next_Perfect_Square | 0 | pass | unproved / unproved | unproved / refuted | unproved / refuted | refuted / refuted | unproved / unproved | unproved / refuted | unproved / refuted |
| 245 | mbpp_245__max_sum | 0 | fail | unproved / unproved | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 264 | mbpp_264__dog_age | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 266 | mbpp_266__lateralsurface_cube | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 267 | mbpp_267__square_Sum | 0 | pass | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 268 | mbpp_268__find_star_num | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 279 | mbpp_279__is_num_decagonal | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 281 | mbpp_281__all_unique | 0 | pass | unproved / refuted | unproved / refuted | timeout / timeout | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 287 | mbpp_287__square_Sum | 6 | pass | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 289 | mbpp_289__odd_Days | 0 | pass | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 291 | mbpp_291__count_no_of_ways | 0 | pass | unproved / unproved | unproved / refuted | timeout / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 292 | mbpp_292__find | 6 | pass | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 309 | mbpp_309__maximum | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 316 | mbpp_316__find_last_occurrence | 0 | pass | unproved / refuted | unproved / refuted | unproved / refuted | refuted / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 320 | mbpp_320__sum_difference | 4 | pass | timeout / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / timeout |
| 335 | mbpp_335__ap_sum | 5 | pass | verified / refuted | verified / refuted | timeout / refuted | timeout / refuted | verified / refuted | verified / refuted | verified / refuted |
| 340 | mbpp_340__sum_three_smallest_nums | 0 | pass | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 346 | mbpp_346__zigzag | 0 | fail | unproved / unproved | unproved / refuted | timeout / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 354 | mbpp_354__tn_ap | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 356 | mbpp_356__find_angle | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 369 | mbpp_369__lateralsurface_cuboid | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 371 | mbpp_371__smallest_missing | 0 | fail | unproved / unproved | malformed / malformed | timeout / refuted | timeout / refuted | unproved / refuted | timeout / refuted | unproved / unproved |
| 373 | mbpp_373__volume_cuboid | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 379 | mbpp_379__surfacearea_cuboid | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 385 | mbpp_385__get_perrin | 0 | pass | unproved / unproved | unproved / refuted | unproved / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 388 | mbpp_388__highest_Power_of_2 | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 389 | mbpp_389__find_lucas | 0 | pass | unproved / unproved | unproved / refuted | unproved / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 392 | mbpp_392__get_max_sum | 4 | fail | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | unproved / unproved | verified / timeout |
| 404 | mbpp_404__minimum | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 414 | mbpp_414__overlapping | 0 | pass | unproved / refuted | unproved / refuted | timeout / timeout | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 420 | mbpp_420__cube_Sum | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 441 | mbpp_441__surfacearea_cube | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 443 | mbpp_443__largest_neg | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 448 | mbpp_448__cal_sum | 0 | fail | unproved / unproved | refuted / refuted | refuted / timeout | vacuous / vacuous | unproved / unproved | unproved / unproved | refuted / refuted |
| 458 | mbpp_458__rectangle_area | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 466 | mbpp_466__find_peak | 0 | pass | refuted / refuted | refuted / refuted | unproved / unproved | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 472 | mbpp_472__check_Consecutive | 4 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 479 | mbpp_479__first_Digit | 0 | fail | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 481 | mbpp_481__is_subset_sum | 0 | pass | abstain / abstain | malformed / refuted | timeout / refuted | abstain / abstain | unproved / unproved | unproved / unproved | unproved / refuted |
| 492 | mbpp_492__binary_search | 0 | pass | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | unproved / refuted | refuted / refuted |
| 498 | mbpp_498__gcd | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 499 | mbpp_499__diameter_circle | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 501 | mbpp_501__num_comm_div | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 504 | mbpp_504__sum_Of_Series | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 517 | mbpp_517__largest_pos | 0 | pass | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | timeout / refuted | unproved / refuted |
| 518 | mbpp_518__sqrt_root | 0 | pass | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | unproved / unproved | refuted / refuted | refuted / refuted |
| 529 | mbpp_529__jacobsthal_lucas | 0 | pass | unproved / unproved | unproved / refuted | unproved / refuted | vacuous / vacuous | abstain / abstain | abstain / abstain | abstain / abstain |
| 540 | mbpp_540__find_Diff | 0 | fail | unproved / unproved | unproved / refuted | unproved / refuted | abstain / abstain | unproved / unproved | abstain / abstain | malformed / malformed |
| 555 | mbpp_555__difference | 5 | pass | verified / refuted | verified / refuted | timeout / refuted | timeout / refuted (FLAKED) | verified / refuted | verified / refuted | verified / refuted |
| 564 | mbpp_564__count_Pairs | 0 | pass | unproved / unproved | refuted / refuted | timeout / timeout | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 566 | mbpp_566__sum_digits | 0 | pass | timeout / unproved | unproved / refuted | timeout / refuted | refuted / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 567 | mbpp_567__issort_list | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | timeout / refuted | unproved / refuted |
| 571 | mbpp_571__max_sum_pair_diff_lessthan_K | 3 | fail | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | malformed / malformed |
| 576 | mbpp_576__is_Sub_Array | 0 | pass | unproved / unproved | malformed / malformed | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 577 | mbpp_577__last_Digit_Factorial | 0 | pass | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 581 | mbpp_581__surface_Area | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 597 | mbpp_597__find_kth | 0 | pass | unproved / unproved | malformed / malformed | timeout / refuted | refuted / unproved | unproved / refuted | unproved / unproved | unproved / refuted |
| 605 | mbpp_605__prime_num | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 627 | mbpp_627__find_First_Missing | 0 | fail | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / unproved | refuted / refuted | refuted / refuted |
| 650 | mbpp_650__are_Equal | 2 | fail | verified / refuted | unproved / refuted | unproved / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 654 | mbpp_654__rectangle_perimeter | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 655 | mbpp_655__fifth_Power_Sum | 3 | pass | timeout / refuted | unproved / refuted | timeout / refuted | timeout / refuted | verified / refuted | verified / refuted | verified / refuted |
| 670 | mbpp_670__decreasing_trend | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | timeout / refuted | unproved / refuted |
| 672 | mbpp_672__max_of_three | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 673 | mbpp_673__convert | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / unproved | timeout / timeout |
| 677 | mbpp_677__validity_triangle | 5 | pass | verified / refuted | malformed / malformed | verified / refuted | verified / refuted | verified / refuted | malformed / malformed | verified / refuted |
| 680 | mbpp_680__increasing_trend | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | timeout / refuted | unproved / refuted |
| 683 | mbpp_683__sum_Square | 0 | pass | timeout / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 687 | mbpp_687__recur_gcd | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 692 | mbpp_692__last_Two_Digits | 0 | pass | unproved / unproved | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 706 | mbpp_706__is_subset | 0 | pass | unproved / refuted | unproved / refuted | timeout / timeout | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 714 | mbpp_714__count_Fac | 0 | pass | unproved / unproved | unproved / refuted | timeout / refuted | refuted / unproved | unproved / unproved | unproved / unproved | unproved / refuted |
| 716 | mbpp_716__rombus_perimeter | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 723 | mbpp_723__count_same_pair | 0 | pass | unproved / unproved | unproved / refuted | unproved / refuted | refuted / vacuous | malformed / refuted | unproved / unproved | unproved / refuted |
| 733 | mbpp_733__find_first_occurrence | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 736 | mbpp_736__left_insertion | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / unproved | verified / refuted | verified / refuted |
| 739 | mbpp_739__find_Index | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | refuted / refuted | abstain / abstain | abstain / abstain | unproved / refuted |
| 752 | mbpp_752__jacobsthal_num | 0 | pass | unproved / unproved | unproved / refuted | unproved / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 770 | mbpp_770__odd_Num_Sum | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 777 | mbpp_777__find_Sum | 0 | pass | unproved / unproved | unproved / unproved | timeout / refuted | abstain / abstain | unproved / unproved | abstain / abstain | unproved / refuted |
| 786 | mbpp_786__right_insertion | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | verified / refuted |
| 789 | mbpp_789__perimeter_polygon | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 793 | mbpp_793__last | 7 | requires-excluded | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 799 | mbpp_799__left_Rotate | 0 | pass | unproved / unproved | unproved / refuted | unproved / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 803 | mbpp_803__is_Perfect_Square | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / unproved | unproved / refuted |
| 807 | mbpp_807__first_odd | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 814 | mbpp_814__rombus_area | 0 | pass | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 837 | mbpp_837__cube_Sum | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 845 | mbpp_845__find_Digits | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | refuted / refuted | abstain / abstain | abstain / abstain | unproved / refuted |
| 873 | mbpp_873__fibonacci | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 876 | mbpp_876__lcm | 0 | fail | refuted / refuted | refuted / refuted | refuted / refuted | timeout / refuted | refuted / unproved (FLAKED) | refuted / refuted | refuted / refuted |
| 882 | mbpp_882__parallelogram_perimeter | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 890 | mbpp_890__find_Extra | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / refuted |
| 891 | mbpp_891__same_Length | 0 | fail | refuted / refuted | refuted / refuted | timeout / timeout | vacuous / vacuous | abstain / abstain | abstain / abstain | refuted / refuted |
| 901 | mbpp_901__smallest_multiple | 0 | undefined | timeout / unproved | unproved / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| 908 | mbpp_908__find_fixed_point | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 911 | mbpp_911__maximum_product | 0 | fail | unproved / unproved | refuted / refuted | refuted / refuted | abstain / abstain | refuted / refuted | refuted / refuted | timeout / timeout |
| 924 | mbpp_924__max_of_two | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 926 | mbpp_926__rencontres_number | 0 | fail | unproved / unproved | unproved / refuted | timeout / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 931 | mbpp_931__sum_series | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 935 | mbpp_935__series_sum | 6 | pass | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 960 | mbpp_960__get_noOfways | 0 | fail | unproved / unproved | unproved / refuted | unproved / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 962 | mbpp_962__sum_Even | 0 | fail | malformed / malformed | malformed / malformed | malformed / malformed | malformed / malformed | refuted / refuted | refuted / refuted | malformed / malformed |
| 970 | mbpp_970__min_of_two | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |

## Problems that produced no graded task

| task_id | fn | stage | why |
|---:|---|---|---|
| 3 | is_not_prime | parse | <string>:5:26: 'exists' does not start an expression [Expr] |
| 6 | differ_At_One_Bit_Pos | parse | <string>:1:1: expected 't', found 'spec' [Task] |
| 20 | is_woodall | parse | <string>:4:28: 'exists' does not start an expression [Expr] |
| 24 | binary_to_decimal | parse | <string>:1:1: expected 't', found 'spec' [Task] |
| 25 | find_Product | parse | <string>:5:2118: 'end of input' does not start an expression [Expr] |
| 29 | get_Odd_Occurrence | parse | <string>:6:3: expected ')', found 'ensures' [Expr] |
| 32 | max_Prime_Factors | parse | <string>:21:24: expected 'decreases', found '{' [Stmt] |
| 33 | decimal_To_Binary | wf | task decreases without a self-call [SPEC: a task decreases requires a self-recursive body, and vice versa (Gate 3)] |
| 38 | div_even_odd | parse | <string>:1:1: expected 't', found 'spec' [Task] |
| 42 | find_Sum | parse | <string>:5:17: 'var' does not start an expression [Expr] |
| 45 | get_gcd | parse | <string>:8:20: expected 'in', found ':' [Expr] |
| 48 | odd_bit_set_number | no-block |  |
| 51 | check_equilateral | wf | bool literal in a v0 task [SPEC: the bool literal is a v1 construct (Gate 1)]; bool literal in a v0 task [SPEC: the bool |
| 56 | check | parse | <string>:1:1: expected 't', found 'spec' [Task] |
| 57 | find_Max_Num | wf | call of unknown fun max_digit [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; + over non-int [SP |
| 58 | opposite_Signs | wf | bool literal in a v0 task [SPEC: the bool literal is a v1 construct (Gate 1)]; bool literal in a v0 task [SPEC: the bool |
| 60 | max_len_sub | no-block |  |
| 62 | smallest_num | parse | <string>:7:3: expected ')', found 'ensures' [Expr] |
| 66 | pos_count | wf | or over non-bool [SPEC: and/or/not/implies are bool-only]; == wants two ints, two bools, two seqs, two nested seqs, or t |
| 67 | bell_number | wf | call of unknown fun bell_sum [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; ite branches differ |
| 72 | dif_Square | parse | <string>:3:30: expected 'in', found ':' [Expr] |
| 76 | count_Squares | parse | <string>:6:17: 'var' does not start an expression [Expr] |
| 77 | is_Diff | parse | <string>:15:3: expected 'else', found 'if' [Stmt] |
| 78 | count_With_Odd_SetBits | parse | <string>:1:1: expected 't', found 'var' [Task] |
| 84 | sequence | wf | task decreases without a self-call [SPEC: a task decreases requires a self-recursive body, and vice versa (Gate 3)] |
| 96 | divisor | parse | <string>:5:106: expected ')', found 'else' [Expr] |
| 100 | next_smallest_palindrome | parse | <string>:11:40: unexpected character '^' [Id] |
| 101 | kth_element | wf | v0 has int only [SPEC: v0 has int only]; operator 'len' not in v0 [SPEC: an operator must be in the declared version's o |
| 107 | count_Hexadecimal | wf | call of unknown fun has_hex_letter [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; implies over  |
| 121 | check_triplet | parse | <string>:5:1: expected ')', found '{' [Expr] |
| 122 | smartNumber | no-block |  |
| 123 | amicable_numbers_sum | wf | * over non-int [SPEC: + - * neg div mod are int-only]; * over non-int [SPEC: + - * neg div mod are int-only]; call of un |
| 126 | sum | parse | <string>:12:1312: expected '{', found ')' [Stmt] |
| 133 | sum_negativenum | parse | <string>:4:17: 'var' does not start an expression [Expr] |
| 142 | count_samepair | parse | <string>:6:81: expected ')', found 'else' [Expr] |
| 144 | sum_Pairs | wf | quantifier body is not bool [SPEC: a quantifier's body must be bool (Gate 1)]; + over non-int [SPEC: + - * neg div mod a |
| 148 | sum_digits_twoparts | no-block |  |
| 149 | longest_subseq_with_diff_one | wf | call of unknown fun abs_diff [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; == wants two ints,  |
| 150 | does_Contain_B | no-block |  |
| 155 | even_bit_toggle_number | no-block |  |
| 158 | min_Ops | parse | <string>:7:90: expected ')', found 'of' [Expr] |
| 162 | sum_series | wf | task decreases without a self-call [SPEC: a task decreases requires a self-recursive body, and vice versa (Gate 3)] |
| 164 | areEquivalent | no-block |  |
| 166 | find_even_Pair | parse | <string>:6:1: expected ')', found '{' [Expr] |
| 168 | frequency | wf | implies over non-bool [SPEC: and/or/not/implies are bool-only]; == wants two ints, two bools, two seqs, two nested seqs, |
| 170 | sum_range_list | wf | == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type [SPEC: == and != apply to two int |
| 179 | is_num_keith | parse | <string>:9:3: '..' does not start an expression [Expr] |
| 183 | count_pairs | parse | <string>:1:1: expected 't', found 'assert' [Task] |
| 188 | prod_Square | no-block |  |
| 189 | first_Missing_Positive | parse | <string>:7:3: expected ')', found 'ensures' [Expr] |
| 190 | count_Intgral_Points | wf | v1 expression form in a v0 task [SPEC: ite/forall/exists/call are v1 expression forms (v1: the three gates)]; v1 express |
| 203 | hamming_Distance | parse | <string>:1:1: expected 't', found 'spec' [Task] |
| 211 | count_Num | no-block |  |
| 212 | fourth_Power_Sum | wf | == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type [SPEC: == and != apply to two int |
| 218 | min_Operations | no-block |  |
| 223 | is_majority | parse | <string>:6:3032: 'end of input' does not start an expression [Expr] |
| 225 | find_Min | parse | <string>:8:78: expected ')', found ']' [Expr] |
| 228 | all_Bits_Set_In_The_Given_Range | parse | <string>:6:57: unexpected character '^' [Id] |
| 235 | even_bit_set_number | wf | and over non-bool [SPEC: and/or/not/implies are bool-only]; == wants two ints, two bools, two seqs, two nested seqs, or  |
| 239 | get_total_number_of_sequences | no-block |  |
| 256 | count_Primes_nums | parse | <string>:1:1: expected 't', found 'spec' [Task] |
| 258 | count_odd | parse | <string>:5:3: expected ')', found 'ensures' [Expr] |
| 260 | newman_prime | no-block |  |
| 270 | sum_even_and_even_index | parse | <string>:6:17: 'var' does not start an expression [Expr] |
| 271 | even_Power_Sum | wf | quantifier body is not bool [SPEC: a quantifier's body must be bool (Gate 1)]; * over non-int [SPEC: + - * neg div mod a |
| 274 | even_binomial_Coeff_Sum | parse | <string>:5:18: unexpected character '^' [Id] |
| 275 | get_Position | wf | v0 has int only [SPEC: v0 has int only]; operator 'len' not in v0 [SPEC: an operator must be in the declared version's o |
| 283 | validate | parse | <string>:1:1: expected 't', found 'spec' [Task] |
| 286 | max_sub_array_sum_repeated | wf | call of unknown fun max_sub_array_sum_single [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; ite |
| 288 | modular_inverse | parse | <string>:5:75: '..' does not start an expression [Expr] |
| 295 | sum_div | parse | <string>:5:21: expected ')', found 'of' [Expr] |
| 296 | get_Inv_Count | parse | <string>:44:58: 'end of input' does not start an expression [Expr] |
| 302 | set_Bit_Number | no-block |  |
| 303 | solve | no-block |  |
| 306 | max_sum_increasing_subseq | parse | <string>:1:1: expected 't', found 'r' [Task] |
| 311 | set_left_most_unset_bit | no-block |  |
| 313 | pos_nos | parse | <string>:6:3: expected ')', found 'ensures' [Expr] |
| 318 | max_volume | parse | <string>:10:3: '/' does not start a statement [Stmt] |
| 325 | get_Min_Squares | parse | <string>:7:3545: 'end of input' does not start an expression [Expr] |
| 327 | check_isosceles | wf | bool literal in a v0 task [SPEC: the bool literal is a v1 construct (Gate 1)]; bool literal in a v0 task [SPEC: the bool |
| 329 | neg_count | wf | implies over non-bool [SPEC: and/or/not/implies are bool-only]; == wants two ints, two bools, two seqs, two nested seqs, |
| 331 | count_unset_bits | parse | <string>:1:1: expected 't', found 'spec' [Task] |
| 334 | check_Validity | wf | bool literal in a v0 task [SPEC: the bool literal is a v1 construct (Gate 1)]; bool literal in a v0 task [SPEC: the bool |
| 339 | find_Divisor | no-block |  |
| 344 | count_Odd_Squares | wf | == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type [SPEC: == and != apply to two int |
| 347 | count_Squares | parse | <string>:6:17: 'var' does not start an expression [Expr] |
| 348 | find_ways | wf | call of unknown fun cat_sum [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; ite branches differ: |
| 351 | first_Element | parse | <string>:7:1: expected ')', found '{' [Expr] |
| 355 | count_Rectangles | no-block |  |
| 360 | get_carol | no-block |  |
| 362 | max_occurrences | parse | <string>:5:13: expected '{', found 'in' [Stmt] |
| 365 | count_Digit | parse | <string>:6:14: unexpected character '^' [Id] |
| 366 | adjacent_num_product | wf | == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type [SPEC: == and != apply to two int |
| 375 | round_num | parse | <string>:13:7: expected '{', found 'q' [Stmt] |
| 382 | find_rotation_count | parse | <string>:6:3: expected ')', found 'requires' [Expr] |
| 383 | even_bit_toggle_number | parse | <string>:16:11: unexpected character '&' [Id] |
| 384 | frequency_Of_Smallest | wf | == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type [SPEC: == and != apply to two int |
| 402 | ncr_modp | no-block |  |
| 407 | rearrange_bigger | parse | <string>:6:1: expected ')', found '{' [Expr] |
| 416 | breakSum | no-block |  |
| 430 | parabola_directrix | no-block |  |
| 435 | last_Digit | wf | operator 'div' not in v0 [SPEC: an operator must be in the declared version's operator set]; * over non-int [SPEC: + - * |
| 436 | neg_nos | parse | <string>:6:3: expected ')', found 'ensures' [Expr] |
| 439 | multiple_to_single | parse | <string>:3:49: unexpected character '^' [Id] |
| 453 | sumofFactors | parse | <string>:5:21: expected ')', found 'of' [Expr] |
| 455 | check_monthnumb_number | wf | bool literal in a v0 task [SPEC: the bool literal is a v1 construct (Gate 1)]; bool literal in a v0 task [SPEC: the bool |
| 463 | max_subarray_product | parse | <string>:5:4811: expected 'else', found 'end of input' [Expr] |
| 467 | decimal_to_Octal | parse | <string>:7:597: expected 'id', found 't' [Expr] |
| 468 | max_product | no-block |  |
| 469 | max_profit | parse | <string>:1:1: expected 't', found 'mp' [Task] |
| 471 | find_remainder | wf | call of unknown fun prod_mod [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; == wants two ints,  |
| 476 | big_sum | parse | <string>:6:1: expected ')', found '{' [Expr] |
| 483 | first_Factorial_Divisible_Number | parse | <string>:1:1: expected 't', found 'spec' [Task] |
| 485 | largest_palindrome | parse | <string>:1:1: expected 't', found 'spec' [Task] |
| 489 | frequency_Of_Largest | parse | <string>:29:118: expected ')', found 'end of input' [Expr] |
| 491 | sum_gp | parse | <string>:8:32: unexpected character '^' [Id] |
| 502 | find | parse | <string>:7:19: expected 'in', found ':' [Expr] |
| 506 | permutation_coefficient | wf | task decreases without a self-call [SPEC: a task decreases requires a self-recursive body, and vice versa (Gate 3)] |
| 509 | average_Odd | no-block |  |
| 510 | no_of_subsequences | parse | <string>:8:46: expected ']', found ':' [Expr] |
| 511 | find_Min_Sum | parse | <string>:1:1: expected 't', found 'sum' [Task] |
| 515 | modular_sum | wf | call of unknown fun sum_subset [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; mod over non-int  |
| 520 | get_lcm | parse | <string>:10:1: expected 'decreases', found '=' [SpecFun] |
| 521 | check_isosceles | wf | bool literal in a v0 task [SPEC: the bool literal is a v1 construct (Gate 1)]; bool literal in a v0 task [SPEC: the bool |
| 522 | lbs | parse | <string>:83:43: expected 'id', found 't' [Stmt] |
| 524 | max_sum_increasing_subsequence | wf | call of unknown fun best_inc_ending_at [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; + over no |
| 525 | parallel_lines | wf | v0 has int only [SPEC: v0 has int only]; operator 'len' not in v0 [SPEC: an operator must be in the declared version's o |
| 527 | get_pairs_count | parse | <string>:6:17: 'var' does not start an expression [Expr] |
| 531 | min_coins | parse | <string>:10:105: expected ')', found 'over' [Expr] |
| 541 | check_abundant | parse | <string>:14:25: expected ')', found 'of' [Expr] |
| 543 | count_digits | parse | RecursionError: maximum recursion depth exceeded |
| 545 | toggle_F_and_L_bits | parse | <string>:5:31: expected ')', found 'if' [Expr] |
| 547 | Total_Hamming_Distance | no-block |  |
| 548 | longest_increasing_subsequence | parse | <string>:1:1: expected 't', found 'spec' [Task] |
| 549 | odd_Num_Sum | parse | <string>:5:44: expected ')', found 'k' [Expr] |
| 550 | find_Max | parse | <string>:7:36: expected ')', found ']' [Expr] |
| 556 | find_Odd_Pair | wf | * over non-int [SPEC: + - * neg div mod are int-only]; * over non-int [SPEC: + - * neg div mod are int-only] |
| 558 | digit_distance_nums | parse | <string>:22:61: expected 'decreases', found 'is' [Stmt] |
| 559 | max_sub_array_sum | wf | == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type [SPEC: == and != apply to two int |
| 573 | unique_product | parse | <string>:7:98: expected ']', found ':' [Expr] |
| 575 | count_no | no-block |  |
| 583 | catalan_number | wf | unbound var i [SPEC: a name must be bound before use (v0 and Gate 1 scope rule)]; argument type mismatch calling catalan |
| 588 | big_diff | parse | <string>:7:3: expected ')', found 'ensures' [Expr] |
| 592 | sum_Of_product | wf | call of unknown fun sumprod2 [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; + over non-int [SPE |
| 594 | diff_even_odd | wf | call of unknown fun tail [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; argument type mismatch  |
| 598 | armstrong_number | wf | call of unknown fun sum_digits_pow [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; == wants two  |
| 600 | is_Even | wf | operator 'div' not in v0 [SPEC: an operator must be in the declared version's operator set]; * over non-int [SPEC: + - * |
| 608 | bell_Number | wf | call of unknown fun bell_row [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; ite branches differ |
| 609 | floor_Min | no-block |  |
| 620 | largest_subset | parse | <string>:8:1: expected ')', found '{' [Expr] |
| 626 | triangle_area | wf | v1 expression form in a v0 task [SPEC: ite/forall/exists/call are v1 expression forms (v1: the three gates)] |
| 633 | pair_OR_Sum | parse | <string>:1:1: expected 't', found 'spec' [Task] |
| 634 | even_Power_Sum | parse | <string>:5:101: expected ')', found 'else' [Expr] |
| 637 | noprofit_noloss | wf | bool literal in a v0 task [SPEC: the bool literal is a v1 construct (Gate 1)]; bool literal in a v0 task [SPEC: the bool |
| 638 | wind_chill | no-block |  |
| 641 | is_nonagonal | parse | <string>:10:5: '..' does not start a statement [Stmt] |
| 646 | No_of_cubes | wf | v1 expression form in a v0 task [SPEC: ite/forall/exists/call are v1 expression forms (v1: the three gates)]; local in a |
| 649 | sum_Range_list | parse | <string>:7:17: 'var' does not start an expression [Expr] |
| 656 | find_Min_Sum | parse | <string>:1:1: expected 't', found 'find_Min_Sum' [Task] |
| 657 | first_Digit | parse | <string>:6:17: unexpected character '^' [Id] |
| 658 | max_occurrences | parse | RecursionError: maximum recursion depth exceeded |
| 661 | max_sum_of_three_consecutive | wf | call of unknown fun max_sum_helper [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; ite branches  |
| 663 | find_max_val | parse | <string>:9:43: unterminated literal [Strings as sequences of code points (v1)] |
| 664 | average_Even | parse | <string>:5:38: unterminated literal [Strings as sequences of code points (v1)] |
| 671 | set_Right_most_Unset_Bit | no-block |  |
| 675 | sum_nums | wf | v1 expression form in a v0 task [SPEC: ite/forall/exists/call are v1 expression forms (v1: the three gates)] |
| 681 | smallest_Divisor | parse | <string>:1:1: expected 't', found 'spec' [Task] |
| 685 | sum_Of_Primes | wf | call of unknown fun is_prime_odd [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; ite branches di |
| 689 | min_jumps | parse | <string>:1:1: expected 't', found 'spec' [Task] |
| 697 | count_even | parse | <string>:5:3: expected ')', found 'ensures' [Expr] |
| 701 | equilibrium_index | wf | quantifier body is not bool [SPEC: a quantifier's body must be bool (Gate 1)]; + over non-int [SPEC: + - * neg div mod a |
| 702 | removals | no-block |  |
| 707 | count_Set_Bits | no-block |  |
| 711 | product_Equal | parse | <string>:1:1: expected 't', found 'var' [Task] |
| 724 | power_base_sum | parse | <string>:1:1: expected 't', found 'spec' [Task] |
| 734 | sum_Of_Subarray_Prod | parse | <string>:1:1: expected 't', found 'spec' [Task] |
| 735 | toggle_middle_bits | no-block |  |
| 751 | check_min_heap | wf | implies over non-bool [SPEC: and/or/not/implies are bool-only] |
| 762 | check_monthnumber_number | wf | bool literal in a v0 task [SPEC: the bool literal is a v1 construct (Gate 1)]; bool literal in a v0 task [SPEC: the bool |
| 765 | is_polite | parse | <string>:3:78: unterminated literal [Strings as sequences of code points (v1)] |
| 767 | get_Pairs_Count | parse | <string>:8:3: expected ')', found 'ensures' [Expr] |
| 768 | check_Odd_Parity | wf | operator 'mod' not in v0 [SPEC: an operator must be in the declared version's operator set]; == wants two ints, two bool |
| 775 | odd_position | parse | <string>:5:1: expected ')', found '{' [Expr] |
| 782 | Odd_Length_Sum | parse | <string>:18:25: expected ')', found 'of' [Expr] |
| 784 | mul_even_odd | parse | <string>:7:119: expected ')', found 'i0' [Expr] |
| 790 | even_position | parse | <string>:5:1: expected ')', found '{' [Expr] |
| 797 | sum_in_Range | wf | implies over non-bool [SPEC: and/or/not/implies are bool-only]; implies over non-bool [SPEC: and/or/not/implies are bool |
| 798 | _sum | parse | <string>:3:6: unexpected character '_' [Id] |
| 801 | test_three_equal | wf | v1 expression form in a v0 task [SPEC: ite/forall/exists/call are v1 expression forms (v1: the three gates)]; v1 express |
| 802 | count_Rotation | parse | <string>:48:35: expected ')', found 'end of input' [Expr] |
| 804 | is_Product_Even | wf | v0 has int only [SPEC: v0 has int only]; operator 'len' not in v0 [SPEC: an operator must be in the declared version's o |
| 820 | check_monthnum_number | wf | bool literal in a v0 task [SPEC: the bool literal is a v1 construct (Gate 1)]; bool literal in a v0 task [SPEC: the bool |
| 831 | count_Pairs | parse | <string>:6:21: expected ')', found 'over' [Expr] |
| 836 | max_sub_array_sum | parse | <string>:10:3: expected ')', found 'ensures' [Expr] |
| 841 | get_inv_count | parse | <string>:38:32: 'end of input' does not start an expression [Expr] |
| 842 | get_odd_occurence | parse | <string>:6:3: expected ')', found 'ensures' [Expr] |
| 843 | nth_super_ugly_number | wf | call of unknown fun next_super_ugly [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; ite branches |
| 844 | get_Number | no-block |  |
| 846 | find_platform | wf | call of unknown fun overlap_at [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; >= is int-only (S |
| 848 | area_trapezium | wf | operator 'div' not in v0 [SPEC: an operator must be in the declared version's operator set]; assign r: None into int [SP |
| 849 | Sum | wf | call of unknown fun is_prime [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; ite condition is no |
| 850 | is_triangleexists | wf | bool literal in a v0 task [SPEC: the bool literal is a v1 construct (Gate 1)]; bool literal in a v0 task [SPEC: the bool |
| 853 | sum_of_odd_Factors | parse | <string>:5:21: expected ')', found 'of' [Expr] |
| 855 | check_Even_Parity | no-block |  |
| 856 | find_Min_Swaps | parse | <string>:6:17: 'var' does not start an expression [Expr] |
| 863 | find_longest_conseq_subseq | parse | RecursionError: maximum recursion depth exceeded |
| 867 | min_Num | no-block |  |
| 870 | sum_positivenum | parse | <string>:4:17: 'var' does not start an expression [Expr] |
| 881 | sum_even_odd | parse | <string>:5:70: expected ')', found 'i0' [Expr] |
| 884 | all_Bits_Set_In_The_Given_Range | no-block |  |
| 887 | is_odd | wf | operator 'mod' not in v0 [SPEC: an operator must be in the declared version's operator set]; != wants two ints, two bool |
| 895 | max_sum_subseq | parse | <string>:7:98: expected ']', found ':' [Expr] |
| 899 | check | no-block |  |
| 903 | count_Unset_Bits | parse | <string>:3:42: unexpected character '^' [Id] |
| 905 | sum_of_square | wf | call of unknown fun sum_sq_rest [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; + over non-int [ |
| 909 | previous_palindrome | parse | <string>:14:8: expected ')', found 'd' [Expr] |
| 918 | coin_change | parse | <string>:1:1: expected 't', found 'assert' [Task] |
| 919 | multiply_list | parse | <string>:5:1: expected ')', found '{' [Expr] |
| 934 | dealnnoy_num | parse | <string>:22:25: expected ')', found 'i' [Expr] |
| 952 | nCr_mod_p | no-block |  |
| 953 | subset | parse | <string>:7:3: expected ')', found 'ensures' [Expr] |
| 955 | is_abundant | parse | <string>:11:84: expected ')', found 'else' [Expr] |
| 957 | get_First_Set_Bit_Pos | parse | <string>:1:1: expected 't', found 'spec' [Task] |
| 968 | floor_Max | parse | <string>:1:1: expected 't', found 'result' [Task] |
| 971 | maximum_segments | parse | <string>:12:3: '..' does not start a statement [Stmt] |

