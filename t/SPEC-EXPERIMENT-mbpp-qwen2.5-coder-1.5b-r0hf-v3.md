# The spec experiment on MBPP: qwen2.5-coder-1.5b-r0hf-v3

ROADMAP 12.6. One reply per problem, temperature 0, fixed seed; the
prompt is `spec_experiment.build_prompt` (grammar, five committed tasks
as examples, the problem text and its three assertions). Every stage
is a count, every refusal is named, and the two failures 12.6 keeps
apart are kept apart here: a task that VERIFIES with a REFUTED twin,
and a task that passes the problem's own tests.

## Stages

| stage | count |
|---|---:|
| MBPP problems whose tests are in t's fragment (the pool) | 649 |
| replies recorded | 649 |
| replies with a t block | 649 |
| blocks that parse | 215 |
| tasks that are well-formed (graded below) | 121 |

Refusals, by named reason:

- 41 x `parse: line N: expected ']', found 'for'`
- 38 x `parse: line N: unexpected character '&'`
- 33 x `parse: line N: a dot must be followed by .N, .N, or a string-library member`
- 30 x `parse: line N: expected ')', found 'for'`
- 29 x `parse: line N: a char literal holds exactly one code point, found N`
- 28 x `parse: line N: unexpected character '^'`
- 25 x `parse: line N: '/' does not start an expression`
- 21 x `parse: line N: comparisons do not chain`
- 18 x `parse: line N: expected ')', found '-'`
- 16 x `parse: line N: expected '{', found 'if'`
- 15 x `wf: task decreases without a self-call`
- 14 x `wf: unbound var True`
- 12 x `parse: line N: unexpected character '|'`
- 12 x `parse: line N: '*' does not start an expression`
- 11 x `parse: line N: expected ')', found 'in'`
- 9 x `parse: line N: expected ']', found ':'`
- 8 x `parse: line N: expected 'id', found 'seq'`
- 7 x `parse: line N: 'seq' is not one of int bool`
- 6 x `wf: vN has int only`
- 6 x `parse: line N: unexpected character '!'`
- 6 x `parse: line N: ':' does not start an expression`
- 6 x `wf: call of unknown fun sum`
- 6 x `parse: line N: expected 'else', found 'i'`
- 6 x `wf: vN expression form in a vN task`
- 5 x `parse: line N: expected 'eof', found 'spec'`

## The problem's own tests (interp on the MBPP assertions)

| outcome | tasks |
|---|---:|
| pass | 42 |
| fail | 70 |
| undefined | 8 |
| signature | 1 |

## The seven kernels (real / twin), over the well-formed tasks

| kernel | verified / refuted | of tasks |
|---|---:|---:|
| dafny | 53 | 121 |
| verus | 53 | 121 |
| spark | 46 | 121 |
| framac | 42 | 121 |
| lean | 53 | 121 |
| rocq | 46 | 121 |
| fstar | 44 | 121 |

| columns counting | 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0 |
|---|---|---|---|---|---|---|---|---|
| tasks | 41 | 3 | 0 | 5 | 4 | 0 | 0 | 68 |

Tasks with no twin at all (every mutation on the ladder computes what the real body computes, or no input satisfies requires): 13.

## 12.6's table: verifies with a refuted twin, against passes its tests

| verifies with refuted twin in | tests pass | tests fail | requires-excluded | undefined | signature |
|---|---:|---:|---:|---:|---:|
| all seven | 21 | 20 | 0 | 0 | 0 |
| some column | 4 | 8 | 0 | 0 | 0 |
| none | 17 | 42 | 0 | 8 | 1 |

**21 of 649 problems** got a task that verifies with a refuted twin in all seven columns and passes its tests; 25 in at least one column. Verified-with-twin but failing its tests, the class 12.6 warns about: 20 in all seven, 8 in some column.

MBPP-DFY subset: 117 pool problems are MBPP-DFY problems (ROADMAP 16.2's family); 26 of them reached the kernels and 6 verify in all seven and pass their tests.

## Every task

| task_id | task | columns counting | tests | dafny | verus | spark | framac | lean | rocq | fstar |
|---:|---|---:|---|---|---|---|---|---|---|---|
| 10 | mbpp_10__small_nnum | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 11 | mbpp_11__remove_Occ | 4 | fail | verified / refuted | verified / refuted | timeout / refuted | abstain / abstain | verified / refuted | verified / refuted | unproved / refuted |
| 14 | mbpp_14__find_Volume | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 15 | mbpp_15__split_lowerstring | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / refuted | unproved / refuted |
| 17 | mbpp_17__square_perimeter | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 22 | mbpp_22__find_first_duplicate | 0 | fail | unproved / unproved | malformed / malformed | timeout / unproved | abstain / abstain | unproved / refuted | unproved / refuted | unproved / unproved |
| 24 | mbpp_24__binary_to_decimal | 0 | fail | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 30 | mbpp_30__count_Substring_With_Equal_Ends | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / refuted | unproved / refuted |
| 33 | mbpp_33__decimal_To_Binary | 0 | fail | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 35 | mbpp_35__find_rect_num | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 47 | mbpp_47__compute_Last_Digit | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 52 | mbpp_52__parallelogram_area | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 58 | mbpp_58__opposite_Signs | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 59 | mbpp_59__is_octagonal | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 76 | mbpp_76__count_Squares | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 86 | mbpp_86__centered_hexagonal_number | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 89 | mbpp_89__closest_num | 0 | pass | unproved / refuted | unproved / refuted | refuted / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 109 | mbpp_109__odd_Equivalent | 0 | undefined | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 112 | mbpp_112__perimeter | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 127 | mbpp_127__multiply_int | 0 | pass | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 134 | mbpp_134__check_last | 4 | fail | verified / refuted | verified / refuted | timeout / refuted | abstain / abstain | verified / refuted | verified / refuted | timeout / refuted |
| 135 | mbpp_135__hexagonal_num | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 158 | mbpp_158__min_Ops | 0 | fail | unproved / unproved | unproved / unproved | unproved / unproved | timeout / timeout | unproved / refuted | unproved / refuted | unproved / unproved |
| 162 | mbpp_162__sum_series | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 176 | mbpp_176__perimeter_triangle | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 190 | mbpp_190__count_Intgral_Points | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 202 | mbpp_202__remove_even | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / refuted | unproved / refuted |
| 209 | mbpp_209__heap_replace | 0 | undefined | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 220 | mbpp_220__replace_max_specialchar | 0 | undefined | unproved / refuted | unproved / refuted | abstain / abstain | abstain / abstain | abstain / abstain | unproved / refuted | unproved / refuted |
| 228 | mbpp_228__all_Bits_Set_In_The_Given_Range | 0 | fail | unproved / refuted | unproved / refuted | malformed / malformed | timeout / refuted | malformed / unproved | abstain / abstain | unproved / refuted |
| 230 | mbpp_230__replace_blank | 3 | fail | verified / refuted | verified / refuted | timeout / refuted | abstain / abstain | verified / refuted | verified / unproved | unproved / timeout |
| 232 | mbpp_232__larg_nnum | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 264 | mbpp_264__dog_age | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 268 | mbpp_268__find_star_num | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 289 | mbpp_289__odd_Days | 0 | fail | unproved / refuted | unproved / refuted | unproved / refuted | abstain / abstain | unproved / refuted | unproved / refuted | unproved / refuted |
| 313 | mbpp_313__pos_nos | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 319 | mbpp_319__find_long_word | 0 | fail | unproved / unproved | unproved / unproved | timeout / timeout | abstain / abstain | unproved / unproved | unproved / unproved | timeout / timeout |
| 320 | mbpp_320__sum_difference | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 321 | mbpp_321__find_demlo | 3 | fail | verified / refuted | verified / refuted | timeout / refuted | abstain / abstain | verified / refuted | verified / unproved | timeout / timeout |
| 335 | mbpp_335__ap_sum | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 336 | mbpp_336__check_monthnum | 0 | pass | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 337 | mbpp_337__text_match_word | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | unproved / unproved | unproved / refuted |
| 345 | mbpp_345__diff_consecutivenums | 0 | pass | unproved / unproved | unproved / unproved | timeout / timeout | timeout / timeout | lower-error / lower-error | timeout / refuted | unproved / unproved |
| 346 | mbpp_346__zigzag | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 347 | mbpp_347__count_Squares | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 350 | mbpp_350__minimum_Length | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted (FLAKED) | abstain / abstain | unproved / refuted | unproved / refuted | timeout / refuted |
| 351 | mbpp_351__first_Element | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 354 | mbpp_354__tn_ap | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 355 | mbpp_355__count_Rectangles | 0 | undefined | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 356 | mbpp_356__find_angle | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 358 | mbpp_358__moddiv_list | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 369 | mbpp_369__lateralsurface_cuboid | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 373 | mbpp_373__volume_cuboid | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 379 | mbpp_379__surfacearea_cuboid | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 396 | mbpp_396__check_char | 0 | signature | unproved / refuted | unproved / refuted | unproved / unproved | abstain / abstain | unproved / refuted | unproved / refuted | unproved / refuted |
| 403 | mbpp_403__is_valid_URL | 0 | fail | unproved / refuted | unproved / refuted | timeout / timeout | abstain / abstain | unproved / refuted | unproved / refuted | unproved / refuted |
| 437 | mbpp_437__remove_odd | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / refuted | unproved / refuted |
| 443 | mbpp_443__largest_neg | 0 | pass | unproved / unproved | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | timeout / refuted | unproved / refuted |
| 451 | mbpp_451__remove_whitespaces | 3 | pass | verified / refuted | verified / refuted | timeout / refuted (FLAKED) | abstain / abstain | verified / refuted | verified / unproved | abstain / abstain |
| 458 | mbpp_458__rectangle_area | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 467 | mbpp_467__decimal_to_Octal | 0 | fail | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 472 | mbpp_472__check_Consecutive | 0 | pass | unproved / unproved | malformed / malformed | timeout / timeout | timeout / timeout | unproved / refuted | unproved / refuted | unproved / unproved |
| 477 | mbpp_477__is_lower | 0 | pass | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 496 | mbpp_496__heap_queue_smallest | 0 | fail | unproved / refuted | unproved / refuted | timeout / timeout | abstain / abstain | abstain / abstain | unproved / unproved | unproved / refuted |
| 499 | mbpp_499__diameter_circle | 6 | pass | verified / refuted | verified / refuted | verified / refuted (FLAKED) | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 503 | mbpp_503__add_consecutive_nums | 0 | undefined | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / refuted | unproved / refuted |
| 536 | mbpp_536__nth_items | 6 | fail | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| 542 | mbpp_542__fill_spaces | 4 | pass | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / unproved | abstain / abstain |
| 555 | mbpp_555__difference | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 563 | mbpp_563__extract_values | 0 | fail | unproved / refuted | unproved / refuted | timeout / timeout | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| 565 | mbpp_565__split | 0 | pass | unproved / refuted | unproved / refuted | timeout / timeout | abstain / abstain | unproved / refuted | unproved / refuted | timeout / timeout |
| 566 | mbpp_566__sum_digits | 0 | fail | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 572 | mbpp_572__two_unique_nums | 0 | undefined | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 577 | mbpp_577__last_Digit_Factorial | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 619 | mbpp_619__move_num | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / unproved | unproved / refuted (FLAKED) |
| 624 | mbpp_624__is_upper | 0 | pass | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 629 | mbpp_629__Split | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 631 | mbpp_631__replace_spaces | 0 | pass | unproved / refuted | unproved / refuted | timeout / timeout (FLAKED) | abstain / abstain | unproved / refuted | unproved / unproved | abstain / abstain |
| 637 | mbpp_637__noprofit_noloss | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 647 | mbpp_647__split_upperstring | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / refuted | unproved / refuted |
| 648 | mbpp_648__exchange_elements | 0 | fail | unproved / refuted | unproved / refuted | timeout / timeout | abstain / abstain | abstain / abstain | timeout / unproved | unproved / refuted |
| 654 | mbpp_654__rectangle_perimeter | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 659 | mbpp_659__Repeat | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 663 | mbpp_663__find_max_val | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 668 | mbpp_668__replace | 3 | fail | verified / refuted | verified / refuted | timeout / refuted | abstain / abstain | verified / refuted | verified / unproved | unproved / timeout |
| 670 | mbpp_670__decreasing_trend | 0 | fail | unproved / unproved | malformed / malformed | unproved / unproved | timeout / timeout | unproved / refuted | unproved / refuted | unproved / unproved |
| 674 | mbpp_674__remove_duplicate | 6 | fail | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| 675 | mbpp_675__sum_nums | 0 | fail | unproved / refuted | unproved / refuted | refuted / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 680 | mbpp_680__increasing_trend | 0 | pass | unproved / unproved | malformed / malformed | timeout / timeout | timeout / timeout | unproved / refuted | unproved / refuted | unproved / unproved |
| 690 | mbpp_690__mul_consecutive_nums | 0 | undefined | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / refuted | unproved / refuted |
| 693 | mbpp_693__remove_multiple_spaces | 4 | fail | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / unproved | abstain / abstain |
| 702 | mbpp_702__removals | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 708 | mbpp_708__Convert | 0 | fail | unproved / refuted | unproved / refuted | timeout / timeout | abstain / abstain | unproved / refuted | unproved / refuted | timeout / refuted |
| 716 | mbpp_716__rombus_perimeter | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 732 | mbpp_732__replace_specialchar | 4 | pass | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / unproved | abstain / abstain |
| 754 | mbpp_754__extract_index_list | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / refuted | unproved / refuted |
| 762 | mbpp_762__check_monthnumber_number | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 768 | mbpp_768__check_Odd_Parity | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 769 | mbpp_769__Diff | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 771 | mbpp_771__check_expression | 0 | fail | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 789 | mbpp_789__perimeter_polygon | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 794 | mbpp_794__text_starta_endb | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | unproved / unproved | unproved / refuted |
| 814 | mbpp_814__rombus_area | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 820 | mbpp_820__check_monthnum_number | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 847 | mbpp_847__lcopy | 0 | pass | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 855 | mbpp_855__check_Even_Parity | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 865 | mbpp_865__ntimes_list | 0 | fail | timeout / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | timeout / refuted | timeout / refuted |
| 868 | mbpp_868__length_Of_Last_Word | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | timeout / refuted |
| 879 | mbpp_879__text_match | 0 | pass | unproved / refuted | unproved / refuted | timeout / timeout | abstain / abstain | unproved / refuted | unproved / refuted | unproved / refuted |
| 882 | mbpp_882__parallelogram_perimeter | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 892 | mbpp_892__remove_spaces | 0 | fail | unproved / unproved | unproved / unproved | timeout / timeout | timeout / timeout | lower-error / lower-error | unproved / refuted | unproved / unproved |
| 899 | mbpp_899__check | 0 | pass | unproved / refuted | unproved / refuted | unproved / unproved | timeout / timeout | unproved / unproved | unproved / unproved | unproved / refuted |
| 900 | mbpp_900__match_num | 0 | fail | unproved / refuted | unproved / refuted | unproved / refuted | abstain / abstain | unproved / refuted | unproved / refuted | unproved / refuted |
| 901 | mbpp_901__smallest_multiple | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 909 | mbpp_909__previous_palindrome | 0 | fail | unproved / refuted | unproved / refuted | abstain / abstain | timeout / refuted | unproved / unproved | unproved / refuted | unproved / refuted |
| 915 | mbpp_915__rearrange_numbs | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 931 | mbpp_931__sum_series | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 935 | mbpp_935__series_sum | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 953 | mbpp_953__subset | 0 | undefined | unproved / unproved | malformed / malformed | timeout / timeout | timeout / timeout | unproved / refuted | unproved / refuted | timeout / unproved |
| 957 | mbpp_957__get_First_Set_Bit_Pos | 0 | fail | unproved / refuted | unproved / refuted | refuted / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 964 | mbpp_964__word_len | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |

## Problems that produced no graded task

| task_id | fn | stage | why |
|---:|---|---|---|
| 3 | is_not_prime | wf | unbound var True; == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type; call of unknow |
| 4 | heap_queue_largest | parse | line 24: expected 'else', found '}' |
| 5 | count_ways | wf | call of unknown fun mbpp_5__count_ways; call of unknown fun mbpp_5__count_ways; + over non-int; ensures references the t |
| 6 | differ_At_One_Bit_Pos | parse | line 4: unexpected character '^' |
| 7 | find_char_long | parse | line 4: expected ']', found 'for' |
| 8 | square_nums | parse | line 3: expected ']', found 'for' |
| 9 | find_Rotations | wf | + over non-int; local rotated init type mismatch |
| 16 | text_lowercase_underscore | parse | line 4: expected ']', found 'for' |
| 18 | remove_dirty_chars | parse | line 4: unexpected character '/' |
| 19 | test_duplicate | parse | line 6: expected 'kw', found 'set' |
| 20 | is_woodall | parse | line 3: '/' does not start an expression |
| 21 | multiples_of_num | parse | line 6: expected ']', found 'for' |
| 25 | find_Product | parse | line 11: expected ':=', found 'i' |
| 27 | remove | parse | line 3: expected ')', found '-' |
| 28 | binomial_Coeff | parse | line 14: expected '{', found 'if' |
| 29 | get_Odd_Occurrence | parse | line 16: expected '{', found 'if' |
| 32 | max_Prime_Factors | wf | task decreases without a self-call |
| 34 | find_missing | parse | line 4: a dot must be followed by .0, .1, or a string-library member |
| 36 | find_Nth_Digit | parse | line 10: expected 'eof', found 'spec' |
| 38 | div_even_odd | parse | line 5: '/' does not start an expression |
| 39 | rearange_string | parse | line 10: comparisons do not chain; parenthesise |
| 41 | filter_evennumbers | parse | line 4: expected ']', found 'for' |
| 42 | find_Sum | parse | line 4: a dot must be followed by .0, .1, or a string-library member |
| 43 | text_match | parse | line 5: expected ']', found 'for' |
| 44 | text_match_string | parse | line 3: a char literal holds exactly one code point, found 14 |
| 45 | get_gcd | parse | line 4: a dot must be followed by .0, .1, or a string-library member |
| 46 | test_distinct | parse | line 3: comparisons do not chain; parenthesise |
| 48 | odd_bit_set_number | parse | line 3: unexpected character '/' |
| 51 | check_equilateral | wf | unbound var True; assign r: None into bool; unbound var False; assign r: None into bool |
| 53 | check_Equality | wf | v0 has int only; operator 'seq' not in v0; == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the  |
| 54 | counting_sort | parse | line 6: a dot must be followed by .0, .1, or a string-library member |
| 55 | tn_gp | parse | line 3: unexpected character '^' |
| 56 | check | parse | line 5: comparisons do not chain; parenthesise |
| 57 | find_Max_Num | parse | line 7: expected 'id', found 'seq' |
| 60 | max_len_sub | parse | line 4: a dot must be followed by .0, .1, or a string-library member |
| 61 | count_Substrings | parse | line 5: 'int' does not start an expression |
| 62 | smallest_num | wf | v0 has int only; v1 expression form in a v0 task; call of unknown fun min; == wants two ints, two bools, two seqs, two n |
| 66 | pos_count | parse | line 3: expected ']', found 'for' |
| 67 | bell_number | parse | line 9: expected ')', found 'for' |
| 68 | is_Monotonic | parse | line 3: expected ')', found 'for' |
| 69 | is_sublist | parse | line 3: expected ')', found 'in' |
| 71 | comb_sort | parse | line 7: 'seq' is not one of int bool |
| 72 | dif_Square | wf | call of unknown fun sqrt; mod over non-int; call of unknown fun sqrt; mod over non-int |
| 74 | is_samepatterns | parse | line 3: expected ')', found '-' |
| 77 | is_Diff | parse | line 3: comparisons do not chain; parenthesise |
| 78 | count_With_Odd_SetBits | parse | line 9: unexpected character '&' |
| 79 | word_len | parse | line 3: comparisons do not chain; parenthesise |
| 83 | get_Char | wf | call of unknown fun ord; == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type; call of |
| 84 | sequence | parse | line 9: expected 'else', found 'end of input' |
| 90 | len_log | parse | line 3: expected ')', found '-' |
| 91 | find_substring | parse | line 9: unexpected character '!' |
| 92 | is_undulating | parse | line 4: expected ')', found 'in' |
| 93 | power | parse | line 3: unexpected character '^' |
| 96 | divisor | parse | line 3: expected ')', found 'x' |
| 99 | decimal_to_binary | parse | line 3: a char literal holds exactly one code point, found 4 |
| 100 | next_smallest_palindrome | parse | line 10: expected 'kw', found 'str' |
| 101 | kth_element | parse | line 3: a dot must be followed by .0, .1, or a string-library member |
| 102 | snake_to_camel | wf | call of unknown fun chr; seq literal elements must be all int or all seq (no mixing, no pair or nested-seq rows) |
| 103 | eulerian_num | parse | line 5: expected ')', found 'for' |
| 107 | count_Hexadecimal | parse | line 6: expected ']', found 'for' |
| 108 | merge_sorted_list | parse | line 4: '..' does not start an expression |
| 113 | check_integer | wf | unbound var True; == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type; unbound var Fa |
| 118 | string_to_list | wf | == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type; assign r: {'seq': 'seq'} into se |
| 119 | search | parse | line 4: a dot must be followed by .0, .1, or a string-library member |
| 121 | check_triplet | parse | line 9: comparisons do not chain; parenthesise |
| 122 | smartNumber | parse | line 5: '/' does not start an expression |
| 123 | amicable_numbers_sum | parse | line 10: expected '{', found 'where' |
| 125 | find_length | parse | line 5: expected ')', found 'for' |
| 126 | sum | wf | task decreases without a self-call |
| 128 | long_words | wf | len of a non-seq; len of a non-seq; len of a non-seq |
| 131 | reverse_vowels | parse | line 25: unexpected character '&' |
| 133 | sum_negativenum | parse | line 3: expected ')', found 'for' |
| 138 | is_Sum_Of_Powers_Of_Two | parse | line 3: unexpected character '&' |
| 141 | pancake_sort | parse | line 10: ':' does not start an expression |
| 142 | count_samepair | parse | line 4: unexpected character '&' |
| 144 | sum_Pairs | parse | line 5: expected ')', found 'for' |
| 146 | ascii_value_string | parse | line 3: expected ')', found 'for' |
| 148 | sum_digits_twoparts | wf | call of unknown fun sum; == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type |
| 149 | longest_subseq_with_diff_one | parse | line 8: 'seq' is not one of int bool |
| 150 | does_Contain_B | parse | line 4: expected ')', found 'in' |
| 151 | is_coprime | parse | line 31: expected 'eof', found 'spec' |
| 152 | merge_sort | parse | line 20: unexpected character '&' |
| 155 | even_bit_toggle_number | parse | line 3: unexpected character '^' |
| 159 | month_season | parse | line 4: a char literal holds exactly one code point, found 3 |
| 161 | remove_elements | parse | line 3: expected 'id', found 't' |
| 164 | areEquivalent | parse | line 18: expected 'else', found 'i' |
| 165 | count_char_position | parse | line 19: expected '{', found 'if' |
| 166 | find_even_Pair | parse | line 14: unexpected character '^' |
| 167 | next_Power_Of_2 | parse | line 3: '*' does not start an expression |
| 168 | frequency | parse | line 6: a dot must be followed by .0, .1, or a string-library member |
| 169 | get_pell | wf | task decreases without a self-call |
| 170 | sum_range_list | parse | line 10: comparisons do not chain; parenthesise |
| 171 | perimeter_pentagon | wf | local perimeter shadows a name in scope |
| 172 | count_occurance | parse | line 4: expected ']', found 'for' |
| 173 | remove_splchar | parse | line 4: expected ']', found 'for' |
| 175 | is_valid_parenthese | parse | line 17: expected '{', found 'if' |
| 178 | string_literals | parse | line 4: a char literal holds exactly one code point, found 8 |
| 179 | is_num_keith | parse | line 9: expected 'then', found 'end of input' |
| 181 | common_prefix | parse | line 19: unexpected character '&' |
| 183 | count_pairs | parse | line 4: a dot must be followed by .0, .1, or a string-library member |
| 184 | greater_specificnum | parse | line 9: unexpected character '!' |
| 186 | check_literals | parse | line 4: a char literal holds exactly one code point, found 8 |
| 187 | longest_common_subsequence | parse | line 6: 'seq' is not one of int bool |
| 188 | prod_Square | parse | line 3: a dot must be followed by .0, .1, or a string-library member |
| 189 | first_Missing_Positive | parse | line 88: expected ')', found 'end of input' |
| 191 | check_monthnumber | wf | unbound var True; assign result: None into bool; unbound var False; assign result: None into bool |
| 192 | check_String | wf | unbound var True; == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type; unbound var Fa |
| 194 | octal_To_Decimal | parse | line 3: 'int' does not start an expression |
| 195 | first | wf | unbound var null; != wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type |
| 199 | highest_Power_of_2 | parse | line 3: unexpected character '^' |
| 200 | position_max | parse | line 22: expected 'else', found 'i' |
| 201 | chkList | parse | line 2: expected ')', found '-' |
| 203 | hamming_Distance | parse | line 4: unexpected character '&' |
| 204 | count | wf | count wants (seq, seq); count wants (seq, seq) |
| 207 | find_longest_repeating_subseq | wf | call of unknown fun longest_common_subsequence; len of a non-seq; call of unknown fun reverse; local reversed_s init typ |
| 208 | is_decimal | parse | line 3: unexpected character '~' |
| 210 | is_allowed_specific_char | parse | line 13: unexpected character '!' |
| 211 | count_Num | parse | line 5: unexpected character '&' |
| 212 | fourth_Power_Sum | parse | line 5: '*' does not start an expression |
| 217 | first_Repeated_Char | parse | line 6: expected 'kw', found 'set' |
| 218 | min_Operations | wf | v1 expression form in a v0 task; call of unknown fun abs; == wants two ints, two bools, two seqs, two nested seqs, or tw |
| 221 | first_even | parse | line 16: expected ':=', found ';' |
| 223 | is_majority | parse | line 4: a dot must be followed by .0, .1, or a string-library member |
| 224 | count_Set_Bits | parse | line 3: unexpected character '&' |
| 225 | find_Min | parse | line 46: 'end of input' does not start an expression |
| 226 | odd_values_string | parse | line 3: expected ']', found 'for' |
| 227 | min_of_three | parse | line 5: unexpected character '&' |
| 229 | re_arrange_array | parse | line 10: expected ':=', found ';' |
| 234 | volume_cube | parse | line 3: unexpected character '^' |
| 235 | even_bit_set_number | parse | line 3: unexpected character '/' |
| 236 | No_of_Triangle | parse | line 7: '/' does not start an expression |
| 238 | number_of_substrings | parse | line 3: '/' does not start an expression |
| 239 | get_total_number_of_sequences | parse | line 6: expected ')', found 'for' |
| 240 | replace_list | parse | line 3: expected 'id', found 't' |
| 242 | count_charac | wf | v0 has int only; operator 'len' not in v0; == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the  |
| 244 | next_Perfect_Square | parse | line 9: expected 'else', found '}' |
| 245 | max_sum | parse | line 10: expected '{', found 'mid' |
| 247 | lps | parse | line 6: 'seq' is not one of int bool |
| 249 | intersection_array | parse | line 4: a dot must be followed by .0, .1, or a string-library member |
| 251 | insert_element | parse | line 3: expected ')', found '-' |
| 254 | words_ae | parse | line 4: expected ']', found 'for' |
| 256 | count_Primes_nums | parse | line 17: expected 'else', found 'i' |
| 258 | count_odd | parse | line 3: expected ')', found 'x' |
| 260 | newman_prime | parse | line 23: expected 'eof', found 'spec' |
| 266 | lateralsurface_cube | parse | line 3: unexpected character '^' |
| 267 | square_Sum | parse | line 3: '/' does not start an expression |
| 269 | ascii_value | wf | v1 expression form in a v0 task; call of unknown fun ord; == wants two ints, two bools, two seqs, two nested seqs, or tw |
| 270 | sum_even_and_even_index | parse | line 5: expected ']', found 'for' |
| 271 | even_Power_Sum | parse | line 5: '*' does not start an expression |
| 274 | even_binomial_Coeff_Sum | parse | line 5: expected ')', found 'for' |
| 275 | get_Position | wf | unbound var null; != wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type |
| 279 | is_num_decagonal | parse | line 3: 'end of input' does not start an expression |
| 281 | all_unique | parse | line 57: expected ')', found 'end of input' |
| 282 | sub_list | parse | line 3: expected ']', found 'for' |
| 283 | validate | parse | line 3: expected ')', found 'd' |
| 284 | check_element | parse | line 2: expected ')', found '-' |
| 285 | text_match_two_three | parse | line 3: a char literal holds exactly one code point, found 14 |
| 286 | max_sub_array_sum_repeated | parse | line 4: unexpected character '&' |
| 287 | square_Sum | parse | line 3: '/' does not start an expression |
| 288 | modular_inverse | parse | line 8: unexpected character '&' |
| 291 | count_no_of_ways | parse | line 8: 'spec' does not start a statement |
| 292 | find | parse | line 3: '/' does not start an expression |
| 295 | sum_div | parse | line 5: expected ']', found 'for' |
| 296 | get_Inv_Count | parse | line 5: expected ')', found 'for' |
| 302 | set_Bit_Number | parse | line 4: unexpected character '^' |
| 303 | solve | parse | line 5: expected ')', found 'for' |
| 306 | max_sum_increasing_subseq | parse | line 4: comparisons do not chain; parenthesise |
| 308 | large_product | wf | call of unknown fun max; == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type; call of |
| 309 | maximum | wf | v1 expression form in a v0 task; call of unknown fun max; == wants two ints, two bools, two seqs, two nested seqs, or tw |
| 311 | set_left_most_unset_bit | parse | line 3: unexpected character '/' |
| 315 | find_Max_Len_Even | parse | line 94: 'end of input' does not start an expression |
| 316 | find_last_occurrence | parse | line 4: a dot must be followed by .0, .1, or a string-library member |
| 318 | max_volume | parse | line 6: '/' does not start an expression |
| 322 | position_min | parse | line 23: expected 'else', found 'i' |
| 323 | re_arrange | parse | line 5: a dot must be followed by .0, .1, or a string-library member |
| 325 | get_Min_Squares | parse | line 82: expected '{', found 'end of input' |
| 326 | most_occurrences | parse | line 3: expected ')', found '-' |
| 327 | check_isosceles | wf | unbound var True; assign r: None into bool; unbound var True; assign r: None into bool; unbound var True; assign r: None |
| 328 | rotate_left | parse | line 4: comparisons do not chain; parenthesise |
| 329 | neg_count | parse | line 3: expected ']', found 'for' |
| 330 | find_char | parse | line 4: expected ']', found 'for' |
| 331 | count_unset_bits | parse | line 3: expected ']', found ':' |
| 334 | check_Validity | wf | unbound var False; assign r: None into bool; unbound var True; assign r: None into bool |
| 338 | count_Substring_With_Equal_Ends | parse | line 4: '/' does not start an expression |
| 339 | find_Divisor | wf | unbound var max_divisor; == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type; task de |
| 340 | sum_three_smallest_nums | parse | line 5: ':' does not start an expression |
| 344 | count_Odd_Squares | parse | line 6: expected ']', found 'for' |
| 348 | find_ways | parse | line 5: expected ']', found 'for' |
| 349 | check | parse | line 3: expected '{', found 'if' |
| 352 | unique_Characters | parse | line 3: expected ')', found 'char' |
| 359 | Check_Solution | parse | line 7: unexpected character '^' |
| 360 | get_carol | wf | task decreases without a self-call |
| 362 | max_occurrences | parse | line 24: expected 'else', found 'count' |
| 364 | min_flip_to_make_string_alternate | parse | line 5: comparisons do not chain; parenthesise |
| 365 | count_Digit | wf | call of unknown fun str; len of a non-seq; call of unknown fun str; len of a non-seq |
| 366 | adjacent_num_product | parse | line 3: expected ')', found 'for' |
| 371 | smallest_missing | wf | self-recursive body without a task decreases |
| 372 | heap_assending | parse | line 12: a char literal holds exactly one code point, found 48 |
| 374 | permute_string | parse | line 11: expected 'kw', found 'char' |
| 375 | round_num | wf | operator 'mod' not in v0; == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type; local  |
| 377 | remove_Char | parse | line 3: expected '{', found 'without' |
| 378 | move_first | parse | line 3: ':' does not start an expression |
| 382 | find_rotation_count | parse | line 19: '/' does not start an expression |
| 383 | even_bit_toggle_number | parse | line 3: unexpected character '^' |
| 384 | frequency_Of_Smallest | parse | line 6: expected ']', found 'for' |
| 385 | get_perrin | wf | call of unknown fun mbpp_385__get_perrin; call of unknown fun mbpp_385__get_perrin; + over non-int; call of unknown fun  |
| 386 | swap_count | parse | line 4: expected '{', found 'contains' |
| 387 | even_or_odd | parse | line 5: expected '{', found 'then' |
| 388 | highest_Power_of_2 | parse | line 3: unexpected character '^' |
| 389 | find_lucas | wf | call of unknown fun mbpp_389__find_lucas; call of unknown fun mbpp_389__find_lucas; + over non-int; ensures references t |
| 392 | get_max_sum | wf | call of unknown fun max; == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type; ensures |
| 402 | ncr_modp | wf | task decreases without a self-call |
| 404 | minimum | wf | v1 expression form in a v0 task; call of unknown fun min; == wants two ints, two bools, two seqs, two nested seqs, or tw |
| 406 | find_Parity | parse | line 3: expected '{', found 'if' |
| 407 | rearrange_bigger | parse | line 47: a char literal holds exactly one code point, found 0 |
| 411 | snake_to_camel | wf | unbound var c; split wants (seq, int); unbound var c; seq literal elements must be all int or all seq (no mixing, no pai |
| 412 | remove_odd | parse | line 3: expected ']', found 'for' |
| 414 | overlapping | parse | line 3: comparisons do not chain; parenthesise |
| 416 | breakSum | parse | line 5: '/' does not start an expression |
| 420 | cube_Sum | parse | line 4: '/' does not start an expression |
| 426 | filter_oddnumbers | parse | line 4: expected ']', found 'for' |
| 427 | change_date_format | parse | line 4: expected ')', found 'in' |
| 428 | shell_sort | parse | line 7: expected 'id', found 'seq' |
| 430 | parabola_directrix | parse | line 5: '*' does not start an expression |
| 433 | check_greater | parse | line 4: a char literal holds exactly one code point, found 50 |
| 434 | text_match_one | parse | line 3: a char literal holds exactly one code point, found 14 |
| 435 | last_Digit | wf | operator 'mod' not in v0; == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type; operat |
| 436 | neg_nos | parse | line 13: expected ':=', found ';' |
| 439 | multiple_to_single | parse | line 3: expected '(', found ',' |
| 441 | surfacearea_cube | parse | line 4: unexpected character '^' |
| 447 | cube_nums | parse | line 7: expected ')', found 'x' |
| 448 | cal_sum | wf | task decreases without a self-call |
| 449 | check_Triangle | parse | line 5: a char literal holds exactly one code point, found 3 |
| 450 | extract_string | parse | line 3: expected ')', found '-' |
| 453 | sumofFactors | parse | line 3: expected ')', found 'for' |
| 454 | text_match_wordz | parse | line 3: a char literal holds exactly one code point, found 14 |
| 455 | check_monthnumb_number | wf | unbound var True; assign r: None into bool; unbound var False; assign r: None into bool |
| 456 | reverse_string_list | parse | line 3: expected ')', found '-' |
| 459 | remove_uppercase | parse | line 5: unexpected character '^' |
| 461 | upper_ctr | parse | line 3: expected ']', found 'for' |
| 463 | max_subarray_product | wf | call of unknown fun sum; spec_fun max_product decreases is not int; call of unknown fun sum; <= is int-only (SPEC.md gat |
| 466 | find_peak | parse | line 21: unexpected character '&' |
| 468 | max_product | parse | line 7: a dot must be followed by .0, .1, or a string-library member |
| 469 | max_profit | parse | line 4: a dot must be followed by .0, .1, or a string-library member |
| 471 | find_remainder | parse | line 4: a dot must be followed by .0, .1, or a string-library member |
| 474 | replace_char | parse | line 3: expected ']', found 'if' |
| 476 | big_sum | wf | v0 has int only; v1 expression form in a v0 task; call of unknown fun max; v1 expression form in a v0 task; call of unkn |
| 478 | remove_lowercase | parse | line 3: expected '{', found 'without' |
| 479 | first_Digit | parse | line 3: '/' does not start an expression |
| 480 | get_max_occuring_char | parse | line 9: expected ':=', found 'i' |
| 481 | is_subset_sum | parse | line 6: unexpected character '/' |
| 482 | match | parse | line 4: a char literal holds exactly one code point, found 3 |
| 483 | first_Factorial_Divisible_Number | parse | line 51: expected '{', found 'end of input' |
| 485 | largest_palindrome | parse | line 5: expected ')', found 'for' |
| 489 | frequency_Of_Largest | parse | line 7: expected 'id', found 'seq' |
| 491 | sum_gp | parse | line 7: unexpected character '^' |
| 492 | binary_search | parse | line 5: expected ')', found 'in' |
| 495 | remove_lowercase | wf | split wants (seq, int); split wants (seq, int) |
| 498 | gcd | wf | task decreases without a self-call |
| 500 | concatenate_elements | parse | line 2: expected ')', found '-' |
| 501 | num_comm_div | wf | task decreases without a self-call |
| 502 | find | wf | operator 'mod' not in v0; == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type; operat |
| 504 | sum_Of_Series | parse | line 3: '/' does not start an expression |
| 505 | re_order | parse | line 28: expected 'else', found '}' |
| 506 | permutation_coefficient | wf | task decreases without a self-call |
| 507 | remove_words | parse | line 4: unexpected character '&' |
| 508 | same_order | parse | line 4: unexpected character '&' |
| 509 | average_Odd | parse | line 4: '/' does not start an expression |
| 510 | no_of_subsequences | parse | line 4: a dot must be followed by .0, .1, or a string-library member |
| 511 | find_Min_Sum | wf | task decreases without a self-call |
| 515 | modular_sum | wf | call of unknown fun sum; mod over non-int; call of unknown fun sum; == wants two ints, two bools, two seqs, two nested s |
| 516 | radix_sort | parse | line 32: unexpected character '&' |
| 517 | largest_pos | parse | line 9: ':' does not start an expression |
| 518 | sqrt_root | parse | line 9: expected ')', found 'div' |
| 520 | get_lcm | parse | line 5: expected ')', found 'x' |
| 521 | check_isosceles | wf | unbound var True; assign r: None into bool; unbound var True; assign r: None into bool; unbound var True; assign r: None |
| 522 | lbs | parse | line 6: 'seq' is not one of int bool |
| 523 | check_string | parse | line 5: a char literal holds exactly one code point, found 40 |
| 524 | max_sum_increasing_subsequence | parse | line 10: expected ':=', found 'i' |
| 525 | parallel_lines | parse | line 4: comparisons do not chain; parenthesise |
| 526 | capitalize_first_last_letters | parse | line 18: unexpected character '/' |
| 527 | get_pairs_count | parse | line 4: expected 'returns', found 'requires' |
| 529 | jacobsthal_lucas | wf | call of unknown fun mbpp_529__jacobsthal_lucas; call of unknown fun mbpp_529__jacobsthal_lucas; + over non-int; call of  |
| 531 | min_coins | parse | line 4: unexpected character '&' |
| 532 | check_permutation | parse | line 3: ':' does not start an expression |
| 537 | first_repeated_word | parse | line 7: expected 'kw', found 'set' |
| 539 | basesnum_coresspondingnum | parse | line 6: unexpected character '^' |
| 540 | find_Diff | parse | line 37: expected 'else', found 'if' |
| 541 | check_abundant | parse | line 5: expected ')', found 'for' |
| 543 | count_digits | wf | call of unknown fun str; len of a non-seq; call of unknown fun str; len of a non-seq |
| 545 | toggle_F_and_L_bits | parse | line 3: unexpected character '^' |
| 547 | Total_Hamming_Distance | parse | line 5: unexpected character '^' |
| 548 | longest_increasing_subsequence | parse | line 6: expected 'id', found 'seq' |
| 549 | odd_Num_Sum | parse | line 5: '*' does not start an expression |
| 550 | find_Max | parse | line 10: unexpected character '/' |
| 552 | Seq_Linear | parse | line 12: unexpected character '&' |
| 554 | Split | parse | line 4: '/' does not start an expression |
| 556 | find_Odd_Pair | parse | line 14: unexpected character '^' |
| 557 | toggle_string | wf | unbound var c; split wants (seq, int); unbound var c; seq literal elements must be all int or all seq (no mixing, no pai |
| 558 | digit_distance_nums | wf | call of unknown fun abs; == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type; call of |
| 559 | max_sub_array_sum | parse | line 8: expected ':', found '=' |
| 564 | count_Pairs | parse | line 11: comparisons do not chain; parenthesise |
| 567 | issort_list | wf | unbound var True; == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type; unbound var Fa |
| 570 | remove_words | parse | line 4: unexpected character '&' |
| 571 | max_sum_pair_diff_lessthan_K | parse | line 4: a dot must be followed by .0, .1, or a string-library member |
| 573 | unique_product | parse | line 8: expected 'kw', found 'set' |
| 575 | count_no | wf | task decreases without a self-call |
| 576 | is_Sub_Array | parse | line 5: unexpected character '&' |
| 578 | interleave_lists | parse | line 4: comparisons do not chain; parenthesise |
| 581 | surface_Area | parse | line 6: a pair projection is .0 or .1, found .5 |
| 583 | catalan_number | wf | task decreases without a self-call |
| 584 | find_adverbs | parse | line 55: expected '{', found 'end of input' |
| 586 | split_Arr | parse | line 6: expected ']', found ':' |
| 588 | big_diff | wf | v0 has int only; v1 expression form in a v0 task; call of unknown fun max; v1 expression form in a v0 task; call of unkn |
| 589 | perfect_squares | parse | line 6: expected ']', found 'for' |
| 591 | swap_List | parse | line 3: expected ']', found ':' |
| 592 | sum_Of_product | parse | line 5: expected ')', found 'for' |
| 593 | removezero_ip | parse | line 5: expected ')', found 'in' |
| 594 | diff_even_odd | parse | line 5: a dot must be followed by .0, .1, or a string-library member |
| 595 | min_Swaps | parse | line 13: expected '{', found 'if' |
| 597 | find_kth | parse | line 4: unexpected character '&' |
| 598 | armstrong_number | parse | line 3: expected '{', found 'if' |
| 600 | is_Even | parse | line 3: unexpected character '&' |
| 602 | first_repeated_char | parse | line 3: expected '{', found 'in' |
| 603 | get_ludic | parse | line 5: expected ']', found 'for' |
| 604 | reverse_words | parse | line 4: a dot must be followed by .0, .1, or a string-library member |
| 605 | prime_num | parse | line 3: expected '{', found 'if' |
| 608 | bell_Number | parse | line 9: expected ')', found 'for' |
| 609 | floor_Min | parse | line 15: expected '{', found 'if' |
| 610 | remove_kth_element | parse | line 4: comparisons do not chain; parenthesise |
| 620 | largest_subset | parse | line 7: 'seq' is not one of int bool |
| 621 | increment_numerics | parse | line 25: unexpected character '&' |
| 623 | nth_nums | parse | line 4: '*' does not start an expression |
| 625 | swap_List | parse | line 3: expected ']', found ':' |
| 626 | triangle_area | parse | line 5: '*' does not start an expression |
| 627 | find_First_Missing | wf | unbound var null; != wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type; self-recursive |
| 628 | replace_spaces | parse | line 4: a char literal holds exactly one code point, found 47 |
| 632 | move_zero | parse | line 26: unexpected character '&' |
| 633 | pair_OR_Sum | parse | line 9: unexpected character '^' |
| 634 | even_Power_Sum | parse | line 5: '*' does not start an expression |
| 635 | heap_sort | parse | line 10: unterminated literal |
| 636 | Check_Solution | parse | line 7: unexpected character '^' |
| 638 | wind_chill | parse | line 6: unexpected character '^' |
| 639 | sample_nam | parse | line 3: expected ')', found '-' |
| 640 | remove_parenthesis | parse | line 2: expected ')', found '-' |
| 641 | is_nonagonal | parse | line 3: '/' does not start an expression |
| 643 | text_match_wordz_middle | parse | line 3: a char literal holds exactly one code point, found 14 |
| 644 | reverse_Array_Upto_K | parse | line 4: comparisons do not chain; parenthesise |
| 646 | No_of_cubes | parse | line 6: unexpected character '^' |
| 649 | sum_Range_list | parse | line 10: comparisons do not chain; parenthesise |
| 650 | are_Equal | parse | line 17: expected 'else', found 'i' |
| 655 | fifth_Power_Sum | parse | line 5: '*' does not start an expression |
| 656 | find_Min_Sum | parse | line 5: expected ')', found 'for' |
| 657 | first_Digit | parse | line 10: unexpected character '!' |
| 658 | max_occurrences | parse | line 25: expected 'else', found 'count' |
| 661 | max_sum_of_three_consecutive | parse | line 5: expected ']', found ':' |
| 664 | average_Even | parse | line 4: '/' does not start an expression |
| 665 | move_last | parse | line 3: expected ']', found ':' |
| 666 | count_char | wf | count wants (seq, seq); count wants (seq, seq) |
| 667 | Check_Vow | parse | line 2: expected 'id', found 't' |
| 669 | check_IP | parse | line 4: a char literal holds exactly one code point, found 16 |
| 671 | set_Right_most_Unset_Bit | parse | line 3: unexpected character '/' |
| 672 | max_of_three | parse | line 5: unexpected character '&' |
| 673 | convert | parse | line 2: expected 'id', found 'seq' |
| 676 | remove_extra_char | parse | line 4: expected ']', found 'for' |
| 677 | validity_triangle | wf | unbound var True; assign r: None into bool; unbound var False; assign r: None into bool |
| 678 | remove_spaces | parse | line 3: a char literal holds exactly one code point, found 0 |
| 681 | smallest_Divisor | parse | line 14: expected ':=', found ';' |
| 682 | mul_list | parse | line 4: a dot must be followed by .0, .1, or a string-library member |
| 683 | sum_Square | parse | line 5: 'int' does not start an expression |
| 684 | count_Char | wf | len of a non-seq; count wants (seq, seq); count wants (seq, seq) |
| 685 | sum_Of_Primes | parse | line 5: expected ')', found 'for' |
| 687 | recur_gcd | wf | task decreases without a self-call |
| 689 | min_jumps | parse | line 4: a dot must be followed by .0, .1, or a string-library member |
| 692 | last_Two_Digits | parse | line 13: unexpected character '!' |
| 697 | count_even | parse | line 3: expected ')', found 'x' |
| 699 | min_Swaps | parse | line 13: expected '{', found 'if' |
| 700 | count_range_in_list | parse | line 5: expected ']', found 'for' |
| 701 | equilibrium_index | wf | call of unknown fun sum; call of unknown fun sum; call of unknown fun sum; local right_sum init type mismatch; call of u |
| 706 | is_subset | parse | line 5: unexpected character '/' |
| 707 | count_Set_Bits | parse | line 5: a dot must be followed by .0, .1, or a string-library member |
| 711 | product_Equal | parse | line 3: 'int' does not start an expression |
| 714 | count_Fac | parse | line 10: expected 'eof', found 'spec' |
| 718 | alternate_elements | parse | line 3: expected ')', found '-' |
| 719 | text_match | parse | line 3: a char literal holds exactly one code point, found 14 |
| 723 | count_same_pair | parse | line 5: expected ']', found 'for' |
| 724 | power_base_sum | parse | line 6: unexpected character '^' |
| 725 | extract_quotation | parse | line 4: a char literal holds exactly one code point, found 9 |
| 727 | remove_char | parse | line 4: expected ']', found 'for' |
| 728 | sum_list | parse | line 3: expected ']', found 'for' |
| 729 | add_list | parse | line 3: expected ']', found 'for' |
| 730 | consecutive_duplicates | parse | line 5: expected ']', found 'for' |
| 733 | find_first_occurrence | parse | line 4: a dot must be followed by .0, .1, or a string-library member |
| 734 | sum_Of_Subarray_Prod | parse | line 5: expected ']', found 'for' |
| 735 | toggle_middle_bits | parse | line 3: unexpected character '^' |
| 736 | left_insertion | parse | line 6: unexpected character '&' |
| 737 | check_str | parse | line 4: a char literal holds exactly one code point, found 5 |
| 739 | find_Index | wf | call of unknown fun str; len of a non-seq; call of unknown fun sum; == wants two ints, two bools, two seqs, two nested s |
| 741 | all_Characters_Same | parse | line 3: expected ')', found 'for' |
| 743 | rotate_right | parse | line 4: comparisons do not chain; parenthesise |
| 745 | divisible_by_digits | parse | line 6: expected ']', found 'for' |
| 747 | lcs_of_three | wf | call of unknown fun max; ite branches differ: int vs None; task decreases without a self-call; call of unknown fun max;  |
| 748 | capital_words_spaces | parse | line 5: unexpected character '^' |
| 749 | sort_numeric_strings | parse | line 3: expected ')', found '-' |
| 751 | check_min_heap | parse | line 10: unexpected character '&' |
| 752 | jacobsthal_num | parse | line 17: expected 'eof', found 'spec' |
| 756 | text_match_zero_one | parse | line 3: a char literal holds exactly one code point, found 14 |
| 757 | count_reverse_pairs | parse | line 3: expected ')', found '-' |
| 759 | is_decimal | wf | unbound var True; == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type; unbound var Fa |
| 760 | unique_Element | parse | line 5: a char literal holds exactly one code point, found 3 |
| 764 | number_ctr | parse | line 3: expected ']', found 'for' |
| 765 | is_polite | parse | line 18: expected 'else', found 'i' |
| 767 | get_Pairs_Count | parse | line 12: comparisons do not chain; parenthesise |
| 770 | odd_Num_Sum | parse | line 5: '*' does not start an expression |
| 772 | remove_length | wf | unbound var null; != wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type; unbound var nu |
| 774 | check_email | parse | line 4: a char literal holds exactly one code point, found 11 |
| 775 | odd_position | parse | line 5: expected ')', found 'for' |
| 776 | count_vowels | parse | line 5: expected ']', found 'for' |
| 777 | find_Sum | parse | line 4: a dot must be followed by .0, .1, or a string-library member |
| 781 | count_Divisors | parse | line 3: expected ']', found 'if' |
| 782 | Odd_Length_Sum | parse | line 5: expected ']', found ':' |
| 784 | mul_even_odd | parse | line 112: expected 'decreases', found 'end of input' |
| 786 | right_insertion | parse | line 3: comparisons do not chain; parenthesise |
| 787 | text_match_three | parse | line 3: a char literal holds exactly one code point, found 14 |
| 790 | even_position | parse | line 3: expected ')', found 'for' |
| 793 | last | wf | unbound var e; == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type; unbound var e; != |
| 797 | sum_in_Range | parse | line 3: expected ')', found 'for' |
| 798 | _sum | parse | line 2: unexpected character '_' |
| 799 | left_Rotate | parse | line 5: unexpected character '/' |
| 800 | remove_all_spaces | parse | line 3: expected '{', found 'without' |
| 801 | test_three_equal | parse | line 5: unexpected character '&' |
| 802 | count_Rotation | parse | line 13: unexpected character '&' |
| 803 | is_Perfect_Square | wf | call of unknown fun sqrt; call of unknown fun sqrt; * over non-int; call of unknown fun sqrt; call of unknown fun sqrt;  |
| 804 | is_Product_Even | parse | line 2: expected 'id', found 'seq' |
| 806 | max_run_uppercase | parse | line 5: expected ')', found 'for' |
| 807 | first_odd | parse | line 3: expected '{', found 'if' |
| 810 | count_variable | parse | line 12: a dot must be followed by .0, .1, or a string-library member |
| 812 | road_rd | wf | split wants (seq, int); join wants (seq<seq>, seq); split wants (seq, int); join wants (seq<seq>, seq) |
| 813 | string_length | wf | v0 has int only; operator 'len' not in v0; == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the  |
| 815 | sort_by_dnf | parse | line 6: expected ')', found 'in' |
| 817 | div_of_nums | parse | line 4: unexpected character '&' |
| 818 | lower_ctr | parse | line 3: expected ']', found 'for' |
| 822 | pass_validity | parse | line 38: unexpected character '&' |
| 823 | check_substring | parse | line 4: a char literal holds exactly one code point, found 38 |
| 824 | remove_even | parse | line 3: expected ']', found 'for' |
| 825 | access_elements | wf | local result shadows a name in scope |
| 826 | check_Type_Of_Triangle | parse | line 7: '*' does not start an expression |
| 829 | second_frequent | parse | line 25: unexpected character '/' |
| 831 | count_Pairs | parse | line 3: '/' does not start an expression |
| 832 | extract_max | parse | line 4: bad escape \d |
| 836 | max_sub_array_sum | parse | line 5: expected ')', found ':' |
| 837 | cube_Sum | parse | line 4: '*' does not start an expression |
| 838 | min_Swaps | parse | line 13: expected '{', found 'if' |
| 840 | Check_Solution | parse | line 7: unexpected character '^' |
| 841 | get_inv_count | parse | line 5: unexpected character '&' |
| 842 | get_odd_occurence | parse | line 5: '{' does not start an expression |
| 843 | nth_super_ugly_number | parse | line 57: unexpected character '!' |
| 844 | get_Number | parse | line 6: '/' does not start an expression |
| 845 | find_Digits | parse | line 7: unexpected character '_' |
| 846 | find_platform | parse | line 4: a dot must be followed by .0, .1, or a string-library member |
| 848 | area_trapezium | wf | operator 'div' not in v0; == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type; operat |
| 849 | Sum | parse | line 9: '/' does not start an expression |
| 850 | is_triangleexists | wf | unbound var True; assign r: None into bool; unbound var False; assign r: None into bool |
| 852 | remove_negs | parse | line 3: expected ']', found 'for' |
| 853 | sum_of_odd_Factors | parse | line 5: expected ')', found 'for' |
| 854 | raw_heap | parse | line 7: expected 'id', found 'seq' |
| 856 | find_Min_Swaps | wf | unbound var n; spec_fun count_swaps decreases is not int; unbound var n; == wants two ints, two bools, two seqs, two nes |
| 860 | check_alphanumeric | parse | line 3: expected '{', found 'if' |
| 861 | anagram_lambda | parse | line 4: unexpected character '&' |
| 863 | find_longest_conseq_subseq | parse | line 3: expected 'id', found 'seq' |
| 864 | palindrome_lambda | parse | line 3: expected ')', found '-' |
| 866 | check_monthnumb | wf | unbound var True; assign result: None into bool; unbound var False; assign result: None into bool |
| 867 | min_Num | wf | call of unknown fun sum; + over non-int; call of unknown fun sum; + over non-int |
| 870 | sum_positivenum | parse | line 3: expected ')', found 'for' |
| 871 | are_Rotations | parse | line 4: expected ']', found ':' |
| 873 | fibonacci | wf | call of unknown fun mbpp_873__fibonacci; call of unknown fun mbpp_873__fibonacci; + over non-int; call of unknown fun mb |
| 874 | check_Concat | parse | line 4: comparisons do not chain; parenthesise |
| 876 | lcm | parse | line 6: '/' does not start an expression |
| 877 | sort_String | wf | call of unknown fun sorted; == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type; call |
| 880 | Check_Solution | parse | line 6: unexpected character '^' |
| 881 | sum_even_odd | wf | call of unknown fun sum; call of unknown fun sum; + over non-int; call of unknown fun sum; == wants two ints, two bools, |
| 883 | div_of_nums | parse | line 4: unexpected character '&' |
| 884 | all_Bits_Set_In_The_Given_Range | parse | line 9: unexpected character '&' |
| 885 | is_Isomorphic | parse | line 4: expected ')', found 'in' |
| 887 | is_odd | parse | line 3: unexpected character '&' |
| 890 | find_Extra | parse | line 4: a dot must be followed by .0, .1, or a string-library member |
| 891 | same_Length | wf | call of unknown fun str; len of a non-seq; call of unknown fun str; len of a non-seq; call of unknown fun str; len of a  |
| 895 | max_sum_subseq | parse | line 5: expected ')', found 'for' |
| 897 | is_Word_Present | parse | line 3: expected ')', found 'in' |
| 898 | extract_elements | parse | line 6: expected ')', found ']' |
| 903 | count_Unset_Bits | parse | line 3: expected ')', found 'for' |
| 905 | sum_of_square | parse | line 5: expected ')', found 'for' |
| 907 | lucky_num | parse | line 5: expected ']', found 'for' |
| 908 | find_fixed_point | parse | line 4: a dot must be followed by .0, .1, or a string-library member |
| 910 | check_date | wf | unbound var True; == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type; unbound var Fa |
| 911 | maximum_product | parse | line 4: a dot must be followed by .0, .1, or a string-library member |
| 913 | end_num | parse | line 3: expected '{', found 'if' |
| 914 | is_Two_Alter | parse | line 15: unexpected character '&' |
| 917 | text_uppercase_lowercase | parse | line 3: a char literal holds exactly one code point, found 14 |
| 918 | coin_change | parse | line 4: unexpected character '&' |
| 919 | multiply_list | parse | line 8: ':' does not start an expression |
| 923 | super_seq | parse | line 7: unexpected character '_' |
| 924 | max_of_two | wf | v1 expression form in a v0 task; call of unknown fun max; == wants two ints, two bools, two seqs, two nested seqs, or tw |
| 926 | rencontres_number | wf | task decreases without a self-call |
| 928 | change_date_format | wf | + over non-int; + over non-int; == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type;  |
| 930 | text_match | parse | line 3: a char literal holds exactly one code point, found 14 |
| 932 | remove_duplic_list | parse | line 3: expected ')', found '-' |
| 933 | camel_to_snake | parse | line 32: bad escape \f |
| 934 | dealnnoy_num | wf | task decreases without a self-call |
| 937 | max_char | parse | line 15: expected ')', found 'in' |
| 940 | heap_sort | parse | line 6: a dot must be followed by .0, .1, or a string-library member |
| 943 | combine_lists | parse | line 4: a dot must be followed by .0, .1, or a string-library member |
| 944 | num_position | parse | line 7: 'seq' is not one of int bool |
| 947 | len_log | parse | line 2: expected ')', found '-' |
| 950 | chinese_zodiac | parse | line 5: a char literal holds exactly one code point, found 2 |
| 952 | nCr_mod_p | wf | unbound var p; mod over non-int; task decreases without a self-call |
| 955 | is_abundant | parse | line 5: expected ')', found 'for' |
| 956 | split_list | parse | line 4: unexpected character '/' |
| 958 | int_to_roman | parse | line 5: '/' does not start an expression |
| 960 | get_noOfways | wf | call of unknown fun get_noOfWays; call of unknown fun get_noOfWays; + over non-int; call of unknown fun get_noOfWays; ca |
| 961 | roman_to_int | parse | line 17: unexpected character '_' |
| 962 | sum_Even | parse | line 3: expected ']', found 'for' |
| 965 | camel_to_snake | parse | line 5: expected ')', found 'in' |
| 967 | check | parse | line 14: expected 'decreases', found 'in' |
| 968 | floor_Max | parse | line 15: expected '{', found 'if' |
| 970 | min_of_two | wf | v1 expression form in a v0 task; call of unknown fun min; == wants two ints, two bools, two seqs, two nested seqs, or tw |
| 971 | maximum_segments | parse | line 5: '/' does not start an expression |
| 973 | left_rotate | parse | line 5: expected ']', found ':' |

