# The spec experiment on MBPP: qwen2.5-coder:7b

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
| replies with a t block | 368 |
| blocks that parse | 114 |
| tasks that are well-formed (graded below) | 64 |

Refusals, by named reason:

- 68 x `parse: line N: unexpected character '%'`
- 34 x `parse: line N: unexpected character '/'`
- 18 x `parse: line N: expected 'else', found 'i'`
- 17 x `parse: line N: unexpected character '&'`
- 17 x `parse: line N: expected ']', found '.'`
- 16 x `parse: line N: unexpected character '^'`
- 11 x `parse: line N: expected 'else', found 'j'`
- 10 x `wf: vN expression form in a vN task`
- 10 x `parse: line N: expected '{', found 'if'`
- 9 x `wf: bool literal in a vN task`
- 7 x `wf: task decreases without a self-call`
- 7 x `parse: line N: 'seq' is not one of int bool`
- 7 x `parse: line N: expected ')', found 'for'`
- 6 x `wf: vN has int only`
- 5 x `parse: line N: expected ']', found ':'`
- 4 x `parse: line N: expected ':=', found ';'`
- 4 x `parse: line N: expected 'decreases', found '{'`
- 4 x `parse: line N: unexpected character '|'`
- 4 x `wf: vN field in a vN task`
- 3 x `wf: call of unknown fun max`
- 3 x `parse: line N: expected 'else', found 'if'`
- 2 x `parse: line N: unexpected character "'"`
- 2 x `parse: line N: expected 'else', found '}'`
- 2 x `parse: line N: expected 'eof', found 'spec'`
- 2 x `parse: line N: 'int' does not start an expression`

## The problem's own tests (interp on the MBPP assertions)

| outcome | tasks |
|---|---:|
| pass | 41 |
| fail | 22 |
| requires-excluded | 1 |

## The seven kernels (real / twin), over the well-formed tasks

| kernel | verified / refuted | of tasks |
|---|---:|---:|
| dafny | 43 | 64 |
| verus | 40 | 64 |
| spark | 43 | 64 |
| framac | 37 | 64 |
| lean | 40 | 64 |
| rocq | 38 | 64 |
| fstar | 11 | 64 |

| columns counting | 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0 |
|---|---|---|---|---|---|---|---|---|
| tasks | 4 | 34 | 2 | 1 | 2 | 0 | 0 | 21 |

Tasks with no twin at all (every mutation on the ladder computes what the real body computes, or no input satisfies requires): 1.

## 12.6's table: verifies with a refuted twin, against passes its tests

| verifies with refuted twin in | tests pass | tests fail | requires-excluded | undefined | signature |
|---|---:|---:|---:|---:|---:|
| all seven | 4 | 0 | 0 | 0 | 0 |
| some column | 29 | 10 | 0 | 0 | 0 |
| none | 8 | 12 | 1 | 0 | 0 |

**4 of 368 problems** got a task that verifies with a refuted twin in all seven columns and passes its tests; 33 in at least one column. Verified-with-twin but failing its tests, the class 12.6 warns about: 0 in all seven, 10 in some column.

MBPP-DFY subset: 67 pool problems are MBPP-DFY problems (ROADMAP 16.2's family); 22 of them reached the kernels and 1 verify in all seven and pass their tests. (Recomputed 2026-09-10 by joining out/spec-experiment/qwen2.5-coder-7b/extract.json against mbpp_dfy.dfy_task_ids(): 67, 22, 1, all confirmed.)

## Every task

| task_id | task | columns counting | tests | dafny | verus | spark | framac | lean | rocq | fstar |
|---:|---|---:|---|---|---|---|---|---|---|---|
| 5 | mbpp_5__count_ways | 0 | fail | unproved / unproved | unproved / refuted | unproved / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 17 | mbpp_17__square_perimeter | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 34 | mbpp_34__find_missing | 0 | requires-excluded | unproved / unproved | unproved / unproved | timeout / timeout | timeout / timeout | unproved / refuted | unproved / refuted | unproved / unproved |
| 35 | mbpp_35__find_rect_num | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 52 | mbpp_52__parallelogram_area | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 58 | mbpp_58__opposite_Signs | 3 | pass | verified / refuted | malformed / malformed | verified / refuted | verified / refuted | abstain / abstain | malformed / malformed | malformed / refuted |
| 59 | mbpp_59__is_octagonal | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 84 | mbpp_84__sequence | 0 | pass | unproved / unproved | malformed / refuted | timeout / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 86 | mbpp_86__centered_hexagonal_number | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 89 | mbpp_89__closest_num | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 112 | mbpp_112__perimeter | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 119 | mbpp_119__search | 0 | fail | unproved / refuted | malformed / malformed | timeout / refuted | abstain / abstain | unproved / refuted | unproved / refuted | unproved / refuted |
| 122 | mbpp_122__smartNumber | 0 | fail | unproved / unproved | unproved / refuted | unproved / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 127 | mbpp_127__multiply_int | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / refuted | verified / refuted |
| 135 | mbpp_135__hexagonal_num | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 162 | mbpp_162__sum_series | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | vacuous / vacuous | unproved / refuted | unproved / refuted | unproved / refuted |
| 169 | mbpp_169__get_pell | 0 | pass | unproved / unproved | unproved / refuted | unproved / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 171 | mbpp_171__perimeter_pentagon | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 176 | mbpp_176__perimeter_triangle | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 189 | mbpp_189__first_Missing_Positive | 0 | fail | unproved / unproved | abstain / abstain | timeout / timeout | abstain / abstain | unproved / unproved | abstain / abstain | abstain / abstain |
| 190 | mbpp_190__count_Intgral_Points | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 195 | mbpp_195__first | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / refuted | verified / refuted |
| 234 | mbpp_234__volume_cube | 0 | pass | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 264 | mbpp_264__dog_age | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 266 | mbpp_266__lateralsurface_cube | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 279 | mbpp_279__is_num_decagonal | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 295 | mbpp_295__sum_div | 0 | fail | unproved / unproved | unproved / unproved | timeout / unproved | vacuous / vacuous | unproved / refuted | unproved / unproved | unproved / unproved |
| 309 | mbpp_309__maximum | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 354 | mbpp_354__tn_ap | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 356 | mbpp_356__find_angle | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 369 | mbpp_369__lateralsurface_cuboid | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 373 | mbpp_373__volume_cuboid | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 379 | mbpp_379__surfacearea_cuboid | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 385 | mbpp_385__get_perrin | 0 | pass | unproved / unproved | unproved / refuted | unproved / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 389 | mbpp_389__find_lucas | 0 | pass | unproved / unproved | unproved / refuted | unproved / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 420 | mbpp_420__cube_Sum | 5 | fail | verified / refuted | verified / refuted | verified / refuted | verified / timeout | verified / refuted | unproved / refuted | verified / refuted |
| 430 | mbpp_430__parabola_directrix | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 441 | mbpp_441__surfacearea_cube | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 458 | mbpp_458__rectangle_area | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 468 | mbpp_468__max_product | 0 | fail | timeout / unproved | unproved / refuted | timeout / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 498 | mbpp_498__gcd | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 499 | mbpp_499__diameter_circle | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 549 | mbpp_549__odd_Num_Sum | 0 | fail | unproved / unproved | unproved / unproved | timeout / unproved | timeout / timeout | unproved / refuted | unproved / refuted | unproved / unproved |
| 555 | mbpp_555__difference | 0 | fail | unproved / unproved | unproved / unproved | timeout / unproved | timeout / timeout | unproved / refuted | unproved / refuted | unproved / unproved |
| 581 | mbpp_581__surface_Area | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 627 | mbpp_627__find_First_Missing | 0 | fail | unproved / unproved | unproved / unproved | timeout / timeout | abstain / abstain | unproved / unproved | timeout / refuted | unproved / unproved |
| 637 | mbpp_637__noprofit_noloss | 4 | pass | verified / refuted | malformed / malformed | verified / refuted | verified / refuted | abstain / abstain | malformed / malformed | verified / refuted |
| 646 | mbpp_646__No_of_cubes | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 654 | mbpp_654__rectangle_perimeter | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 677 | mbpp_677__validity_triangle | 3 | pass | verified / refuted | malformed / malformed | verified / refuted | verified / unproved | abstain / abstain | malformed / malformed | verified / refuted |
| 716 | mbpp_716__rombus_perimeter | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 733 | mbpp_733__find_first_occurrence | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / refuted | verified / refuted |
| 770 | mbpp_770__odd_Num_Sum | 0 | fail | unproved / unproved | unproved / unproved | timeout / unproved | timeout / timeout | unproved / refuted | unproved / refuted | unproved / unproved |
| 789 | mbpp_789__perimeter_polygon | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 814 | mbpp_814__rombus_area | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 837 | mbpp_837__cube_Sum | 5 | fail | verified / refuted | verified / refuted | verified / refuted | verified / timeout | verified / refuted | unproved / refuted | verified / refuted |
| 844 | mbpp_844__get_Number | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 873 | mbpp_873__fibonacci | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 882 | mbpp_882__parallelogram_perimeter | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | malformed / refuted |
| 908 | mbpp_908__find_fixed_point | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / timeout | unproved / refuted | unproved / refuted | unproved / refuted |
| 924 | mbpp_924__max_of_two | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 926 | mbpp_926__rencontres_number | 0 | fail | unproved / unproved | unproved / refuted | timeout / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 931 | mbpp_931__sum_series | 0 | pass | unproved / unproved | unproved / unproved | timeout / unproved | timeout / timeout | unproved / refuted | unproved / refuted | unproved / unproved |
| 960 | mbpp_960__get_noOfways | 0 | fail | unproved / unproved | unproved / refuted | unproved / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |

## Problems that produced no graded task

| task_id | fn | stage | why |
|---:|---|---|---|
| 3 | is_not_prime | parse | line 4: unexpected character '/' |
| 6 | differ_At_One_Bit_Pos | parse | line 3: unexpected character '^' |
| 14 | find_Volume | parse | line 3: unexpected character '/' |
| 19 | test_duplicate | parse | line 22: expected 'else', found 'j' |
| 20 | is_woodall | parse | line 3: unexpected character '&' |
| 22 | find_first_duplicate | parse | line 23: expected ':=', found ';' |
| 24 | binary_to_decimal | parse | line 8: unexpected character '/' |
| 25 | find_Product | parse | line 8: expected ']', found '.' |
| 28 | binomial_Coeff | wf | task decreases without a self-call |
| 29 | get_Odd_Occurrence | parse | line 4: unexpected character '%' |
| 32 | max_Prime_Factors | parse | line 16: unexpected character '%' |
| 33 | decimal_To_Binary | parse | line 6: unexpected character "'" |
| 36 | find_Nth_Digit | parse | line 6: unexpected character '%' |
| 38 | div_even_odd | parse | line 5: unexpected character '%' |
| 42 | find_Sum | parse | line 8: expected ']', found '.' |
| 45 | get_gcd | wf | unbound var a; == wants two ints or two bools; unbound var b; assign r: None into int; unbound var b; == wants two ints  |
| 46 | test_distinct | parse | line 10: expected 'decreases', found '{' |
| 47 | compute_Last_Digit | parse | line 13: unexpected character '%' |
| 48 | odd_bit_set_number | parse | line 3: unexpected character '/' |
| 51 | check_equilateral | wf | bool literal in a v0 task; bool literal in a v0 task |
| 55 | tn_gp | wf | v1 expression form in a v0 task; call of unknown fun pow; * over non-int; v1 expression form in a v0 task; call of unkno |
| 56 | check | parse | line 6: unexpected character '/' |
| 57 | find_Max_Num | parse | line 5: unexpected character "'" |
| 60 | max_len_sub | wf | call of unknown fun max_len_sub_helper; ite branches differ: int vs None; call of unknown fun abs; == wants two ints or  |
| 62 | smallest_num | parse | line 10: expected ']', found '.' |
| 66 | pos_count | parse | line 16: expected 'else', found 'i' |
| 67 | bell_number | parse | line 10: 'seq' is not one of int bool |
| 68 | is_Monotonic | parse | line 18: expected 'else', found '}' |
| 69 | is_sublist | parse | line 22: expected 'else', found 'j' |
| 72 | dif_Square | parse | line 3: unexpected character '%' |
| 76 | count_Squares | wf | v1 field in a v0 task; v1 expression form in a v0 task; v1 expression form in a v0 task; v1 expression form in a v0 task |
| 77 | is_Diff | parse | line 3: unexpected character '%' |
| 78 | count_With_Odd_SetBits | parse | line 6: unexpected character '%' |
| 93 | power | parse | line 6: '*' does not start an expression |
| 96 | divisor | parse | line 5: unexpected character '%' |
| 100 | next_smallest_palindrome | parse | line 19: unexpected character '/' |
| 101 | kth_element | wf | v0 has int only; operator 'at' not in v0; == wants two ints or two bools; operator 'at' not in v0; assign r: None into i |
| 103 | eulerian_num | parse | line 12: unexpected character '&' |
| 107 | count_Hexadecimal | parse | line 17: expected 'else', found 'i' |
| 121 | check_triplet | parse | line 31: expected 'else', found 'k' |
| 123 | amicable_numbers_sum | parse | line 26: unexpected character '/' |
| 126 | sum | parse | line 19: unexpected character '%' |
| 133 | sum_negativenum | parse | line 6: expected ']', found '.' |
| 138 | is_Sum_Of_Powers_Of_Two | parse | line 3: unexpected character '&' |
| 142 | count_samepair | parse | line 8: expected ']', found ':' |
| 144 | sum_Pairs | parse | line 5: expected ')', found 'for' |
| 148 | sum_digits_twoparts | parse | line 17: unexpected character '%' |
| 149 | longest_subseq_with_diff_one | wf | call of unknown fun max; ite branches differ: int vs None; call of unknown fun max; assign r: None into int |
| 150 | does_Contain_B | wf | bool literal in a v0 task; bool literal in a v0 task |
| 151 | is_coprime | wf | assign r: int into bool; assign r: int into bool; assign r: int into bool; assign r: int into bool; assign r: int into b |
| 155 | even_bit_toggle_number | parse | line 3: unexpected character '^' |
| 158 | min_Ops | parse | line 21: expected ':=', found ';' |
| 164 | areEquivalent | parse | line 21: unexpected character '/' |
| 166 | find_even_Pair | parse | line 20: unexpected character '^' |
| 167 | next_Power_Of_2 | parse | line 6: unexpected character '&' |
| 168 | frequency | parse | line 15: expected 'else', found 'i' |
| 170 | sum_range_list | parse | line 6: expected ')', found 'for' |
| 179 | is_num_keith | parse | line 51: unexpected character '%' |
| 183 | count_pairs | parse | line 22: expected 'else', found 'j' |
| 184 | greater_specificnum | parse | line 15: expected 'else', found 'i' |
| 188 | prod_Square | parse | line 21: expected 'else', found 'j' |
| 194 | octal_To_Decimal | parse | line 6: unexpected character '/' |
| 199 | highest_Power_of_2 | parse | line 5: unexpected character '^' |
| 203 | hamming_Distance | parse | line 4: unexpected character '^' |
| 211 | count_Num | wf | v1 field in a v0 task; v1 expression form in a v0 task; v1 expression form in a v0 task; v1 expression form in a v0 task |
| 212 | fourth_Power_Sum | parse | line 5: unexpected character '^' |
| 218 | min_Operations | wf | v1 expression form in a v0 task; call of unknown fun abs; == wants two ints or two bools |
| 221 | first_even | parse | line 4: unexpected character '%' |
| 223 | is_majority | parse | line 4: unexpected character '/' |
| 224 | count_Set_Bits | parse | line 12: unexpected character '&' |
| 225 | find_Min | parse | line 7: expected ']', found '.' |
| 227 | min_of_three | parse | line 7: expected '{', found 'if' |
| 228 | all_Bits_Set_In_The_Given_Range | parse | line 4: unexpected character '&' |
| 235 | even_bit_set_number | parse | line 3: unexpected character '/' |
| 236 | No_of_Triangle | parse | line 6: unexpected character '/' |
| 239 | get_total_number_of_sequences | parse | line 22: expected 'eof', found 'spec' |
| 244 | next_Perfect_Square | parse | line 6: 'int' does not start an expression |
| 245 | max_sum | wf | call of unknown fun max; ite branches differ: int vs None; call of unknown fun max; assign r: None into int |
| 256 | count_Primes_nums | parse | line 11: unexpected character '%' |
| 258 | count_odd | parse | line 3: unexpected character '%' |
| 260 | newman_prime | parse | line 8: 'end of input' does not start an expression |
| 267 | square_Sum | parse | line 5: expected ')', found 'for' |
| 268 | find_star_num | parse | line 4: unexpected character '/' |
| 270 | sum_even_and_even_index | parse | line 7: unexpected character '%' |
| 271 | even_Power_Sum | parse | line 5: unexpected character '^' |
| 274 | even_binomial_Coeff_Sum | parse | line 4: expected ')', found 'for' |
| 275 | get_Position | parse | line 6: unexpected character '%' |
| 281 | all_unique | parse | line 10: expected 'decreases', found '{' |
| 283 | validate | parse | line 11: unexpected character '%' |
| 286 | max_sub_array_sum_repeated | parse | line 7: expected ':', found 'returns' |
| 287 | square_Sum | parse | line 5: unexpected character '%' |
| 288 | modular_inverse | parse | line 14: unexpected character '%' |
| 289 | odd_Days | parse | line 3: unexpected character '%' |
| 291 | count_no_of_ways | wf | call of unknown fun count; call of unknown fun count; + over non-int |
| 292 | find | wf | v1 expression form in a v0 task; local in a v0 task; while in a v0 task |
| 296 | get_Inv_Count | parse | line 8: expected ')', found 'in' |
| 302 | set_Bit_Number | parse | line 4: unexpected character '&' |
| 303 | solve | parse | line 12: unexpected character '/' |
| 306 | max_sum_increasing_subseq | parse | line 5: comparisons do not chain; parenthesise |
| 311 | set_left_most_unset_bit | parse | line 4: unexpected character '&' |
| 313 | pos_nos | parse | line 3: '[' does not start an expression |
| 316 | find_last_occurrence | parse | line 19: expected 'else', found 'i' |
| 318 | max_volume | parse | line 24: expected 'else', found 'r' |
| 320 | sum_difference | parse | line 4: unexpected character '/' |
| 325 | get_Min_Squares | wf | task decreases without a self-call |
| 327 | check_isosceles | wf | bool literal in a v0 task; bool literal in a v0 task |
| 329 | neg_count | parse | line 15: expected 'else', found 'i' |
| 331 | count_unset_bits | parse | line 7: unexpected character '%' |
| 334 | check_Validity | wf | bool literal in a v0 task; bool literal in a v0 task |
| 335 | ap_sum | parse | line 4: unexpected character '/' |
| 339 | find_Divisor | parse | line 7: unexpected character '%' |
| 340 | sum_three_smallest_nums | parse | line 18: expected ':=', found '[' |
| 344 | count_Odd_Squares | parse | line 8: unexpected character '%' |
| 346 | zigzag | wf | v1 expression form in a v0 task; call of unknown fun mbpp_346__zigzag; == wants two ints or two bools; ensures reference |
| 347 | count_Squares | wf | v1 field in a v0 task; v1 expression form in a v0 task; v1 expression form in a v0 task; v1 expression form in a v0 task |
| 348 | find_ways | wf | self-recursive body without a task decreases |
| 351 | first_Element | parse | line 26: expected 'eof', found 'spec' |
| 355 | count_Rectangles | wf | v1 expression form in a v0 task; call of unknown fun count_rectangles; == wants two ints or two bools |
| 360 | get_carol | parse | line 4: unexpected character '^' |
| 362 | max_occurrences | parse | line 26: expected 'else', found 'j' |
| 365 | count_Digit | parse | line 13: unexpected character '/' |
| 366 | adjacent_num_product | parse | line 11: expected 'decreases', found '{' |
| 371 | smallest_missing | parse | line 17: unexpected character '/' |
| 375 | round_num | parse | line 4: unexpected character '%' |
| 382 | find_rotation_count | parse | line 8: expected ']', found '.' |
| 383 | even_bit_toggle_number | parse | line 3: unexpected character '^' |
| 384 | frequency_Of_Smallest | parse | line 8: expected ']', found '.' |
| 388 | highest_Power_of_2 | parse | line 5: unexpected character '^' |
| 392 | get_max_sum | parse | line 9: unexpected character '/' |
| 402 | ncr_modp | parse | line 7: unexpected character '%' |
| 404 | minimum | wf | v1 expression form in a v0 task; call of unknown fun min; == wants two ints or two bools |
| 407 | rearrange_bigger | parse | line 13: unexpected character '^' |
| 414 | overlapping | parse | line 23: expected 'else', found 'j' |
| 416 | breakSum | parse | line 8: unexpected character '/' |
| 435 | last_Digit | parse | line 3: unexpected character '%' |
| 436 | neg_nos | parse | line 16: expected 'else', found 'i' |
| 439 | multiple_to_single | parse | line 4: '+' does not start an expression |
| 443 | largest_neg | parse | line 11: expected ']', found '.' |
| 448 | cal_sum | parse | line 8: expected '{', found 'if' |
| 453 | sumofFactors | parse | line 14: unexpected character '%' |
| 455 | check_monthnumb_number | wf | bool literal in a v0 task; bool literal in a v0 task |
| 463 | max_subarray_product | parse | line 8: expected ']', found '.' |
| 466 | find_peak | parse | line 20: expected 'else', found 'i' |
| 467 | decimal_to_Octal | parse | line 7: unexpected character '/' |
| 469 | max_profit | parse | line 10: expected ']', found '.' |
| 471 | find_remainder | parse | line 5: unexpected character '%' |
| 472 | check_Consecutive | parse | line 15: expected 'else', found 'i' |
| 476 | big_sum | parse | line 10: expected ']', found '.' |
| 479 | first_Digit | parse | line 10: unexpected character '/' |
| 481 | is_subset_sum | wf | task decreases without a self-call |
| 483 | first_Factorial_Divisible_Number | parse | line 6: unexpected character '%' |
| 485 | largest_palindrome | parse | line 26: unexpected character '%' |
| 489 | frequency_Of_Largest | parse | line 20: expected '{', found 'if' |
| 491 | sum_gp | parse | line 7: unexpected character '/' |
| 492 | binary_search | parse | line 15: unexpected character '/' |
| 501 | num_comm_div | wf | task decreases without a self-call; call of unknown fun gcd; assign r: None into int; call of unknown fun gcd; assign r: |
| 502 | find | parse | line 4: unexpected character '%' |
| 504 | sum_Of_Series | parse | line 4: unexpected character '/' |
| 506 | permutation_coefficient | parse | line 5: unexpected character '!' |
| 509 | average_Odd | parse | line 4: unexpected character '%' |
| 510 | no_of_subsequences | parse | line 8: expected ']', found ':' |
| 511 | find_Min_Sum | parse | line 11: unexpected character '%' |
| 515 | modular_sum | parse | line 6: unexpected character '%' |
| 517 | largest_pos | parse | line 17: expected 'else', found 'i' |
| 518 | sqrt_root | parse | line 16: expected 'else', found '}' |
| 520 | get_lcm | parse | line 8: unexpected character '/' |
| 521 | check_isosceles | wf | bool literal in a v0 task; bool literal in a v0 task |
| 522 | lbs | wf | call of unknown fun lbs_helper; ite branches differ: int vs None; call of unknown fun max; ite branches differ: int vs N |
| 524 | max_sum_increasing_subsequence | wf | call of unknown fun max_sum_increasing_subseq_helper; ite branches differ: int vs None; call of unknown fun max; ite bra |
| 525 | parallel_lines | wf | v0 has int only; operator 'len' not in v0; == wants two ints or two bools; operator 'len' not in v0; == wants two ints o |
| 527 | get_pairs_count | parse | line 8: expected ']', found ':' |
| 529 | jacobsthal_lucas | wf | call of unknown fun mbpp_529__jacobsthal_lucas; * over non-int; call of unknown fun mbpp_529__jacobsthal_lucas; + over n |
| 531 | min_coins | parse | line 10: 'seq' is not one of int bool |
| 540 | find_Diff | parse | line 6: 'seq' is not one of int bool |
| 541 | check_abundant | parse | line 13: unexpected character '%' |
| 543 | count_digits | wf | operator 'len' not in v0; == wants two ints or two bools; operator 'len' not in v0; assign r: None into int |
| 545 | toggle_F_and_L_bits | parse | line 3: unexpected character '^' |
| 547 | Total_Hamming_Distance | parse | line 30: unexpected character '%' |
| 548 | longest_increasing_subsequence | parse | line 13: 'seq' is not one of int bool |
| 550 | find_Max | parse | line 7: expected ']', found '.' |
| 556 | find_Odd_Pair | parse | line 20: unexpected character '^' |
| 558 | digit_distance_nums | wf | v1 expression form in a v0 task; call of unknown fun abs; == wants two ints or two bools |
| 559 | max_sub_array_sum | parse | line 23: expected 'else', found 'if' |
| 564 | count_Pairs | parse | line 9: expected ']', found '.' |
| 566 | sum_digits | parse | line 13: unexpected character '%' |
| 567 | issort_list | parse | line 15: expected 'else', found 'i' |
| 571 | max_sum_pair_diff_lessthan_K | parse | line 9: expected '{', found 'if' |
| 573 | unique_product | parse | line 8: 'seq' is not one of int bool |
| 575 | count_no | parse | line 17: unexpected character '%' |
| 576 | is_Sub_Array | parse | line 24: expected 'else', found 'i' |
| 577 | last_Digit_Factorial | wf | v1 expression form in a v0 task; call of unknown fun last_digit_factorial; == wants two ints or two bools |
| 583 | catalan_number | parse | line 9: '>' does not start an expression |
| 588 | big_diff | parse | line 19: expected 'else', found 'if' |
| 592 | sum_Of_product | wf | v1 field in a v0 task; v1 expression form in a v0 task; v1 expression form in a v0 task; v1 expression form in a v0 task |
| 594 | diff_even_odd | parse | line 8: unexpected character '%' |
| 597 | find_kth | parse | line 11: expected ']', found '.' |
| 598 | armstrong_number | parse | line 3: expected ')', found 'd' |
| 600 | is_Even | parse | line 3: unexpected character '&' |
| 605 | prime_num | parse | line 3: unexpected character '%' |
| 608 | bell_Number | parse | line 8: expected ')', found 'in' |
| 609 | floor_Min | parse | line 7: expected '{', found 'if' |
| 620 | largest_subset | parse | line 9: unexpected character '%' |
| 626 | triangle_area | parse | line 8: expected '{', found 'if' |
| 633 | pair_OR_Sum | parse | line 8: unexpected character '/' |
| 634 | even_Power_Sum | parse | line 5: unexpected character '^' |
| 638 | wind_chill | parse | line 5: unexpected character '^' |
| 641 | is_nonagonal | parse | line 4: unexpected character '/' |
| 649 | sum_Range_list | parse | line 6: expected ')', found 'for' |
| 650 | are_Equal | parse | line 18: expected ':=', found ';' |
| 655 | fifth_Power_Sum | parse | line 5: unexpected character '^' |
| 656 | find_Min_Sum | parse | line 12: expected ')', found 'for' |
| 657 | first_Digit | parse | line 19: unexpected character '/' |
| 658 | max_occurrences | parse | line 27: expected 'else', found 'j' |
| 661 | max_sum_of_three_consecutive | wf | call of unknown fun max; ite branches differ: int vs None; call of unknown fun max; assign r: None into int |
| 663 | find_max_val | parse | line 5: unexpected character '%' |
| 664 | average_Even | parse | line 4: unexpected character '%' |
| 670 | decreasing_trend | parse | line 15: expected 'else', found 'i' |
| 671 | set_Right_most_Unset_Bit | parse | line 3: unexpected character '&' |
| 672 | max_of_three | wf | v1 expression form in a v0 task; call of unknown fun max; == wants two ints or two bools |
| 673 | convert | parse | line 5: 'int' does not start an expression |
| 675 | sum_nums | parse | line 4: expected '{', found 'if' |
| 680 | increasing_trend | parse | line 15: expected 'else', found 'i' |
| 681 | smallest_Divisor | parse | line 5: unexpected character '%' |
| 683 | sum_Square | parse | line 21: expected 'else', found 'j' |
| 685 | sum_Of_Primes | parse | line 14: unexpected character '%' |
| 687 | recur_gcd | wf | task decreases without a self-call; call of unknown fun gcd; assign r: None into int; call of unknown fun gcd; assign r: |
| 689 | min_jumps | parse | line 10: 'seq' is not one of int bool |
| 692 | last_Two_Digits | parse | line 9: unexpected character '%' |
| 697 | count_even | parse | line 3: unexpected character '%' |
| 701 | equilibrium_index | parse | line 16: expected 'else', found 'i' |
| 702 | removals | parse | line 10: expected ']', found ':' |
| 706 | is_subset | parse | line 22: expected 'else', found 'j' |
| 707 | count_Set_Bits | parse | line 8: unexpected character '&' |
| 711 | product_Equal | parse | line 13: unexpected character '%' |
| 714 | count_Fac | parse | line 14: unexpected character '%' |
| 723 | count_same_pair | parse | line 5: expected 'decreases', found '=' |
| 724 | power_base_sum | parse | line 13: unexpected character '%' |
| 734 | sum_Of_Subarray_Prod | wf | call of unknown fun mbpp_734__sum_Of_Subarray_Prod; == wants two ints or two bools; ensures references the task name (SP |
| 735 | toggle_middle_bits | parse | line 5: unexpected character '&' |
| 736 | left_insertion | wf | v0 has int only; operator 'len' not in v0; < is int-only (SPEC.md gate 1); v1 expression form in a v0 task; operator 'le |
| 739 | find_Index | parse | line 5: unexpected character '/' |
| 751 | check_min_heap | parse | line 15: expected 'else', found 'j' |
| 752 | jacobsthal_num | wf | task decreases without a self-call |
| 762 | check_monthnumber_number | wf | bool literal in a v0 task; bool literal in a v0 task |
| 765 | is_polite | parse | line 22: unexpected character '/' |
| 767 | get_Pairs_Count | parse | line 10: expected 'decreases', found '{' |
| 768 | check_Odd_Parity | parse | line 3: unexpected character '%' |
| 775 | odd_position | parse | line 3: unexpected character '%' |
| 777 | find_Sum | parse | line 8: expected ']', found ':' |
| 782 | Odd_Length_Sum | parse | line 28: unexpected character '%' |
| 784 | mul_even_odd | parse | line 7: unexpected character '%' |
| 786 | right_insertion | wf | v0 has int only; operator 'len' not in v0; < is int-only (SPEC.md gate 1); v1 expression form in a v0 task; operator 'le |
| 790 | even_position | parse | line 3: unexpected character '%' |
| 793 | last | parse | line 20: expected 'else', found 'i' |
| 797 | sum_in_Range | parse | line 8: unexpected character '%' |
| 798 | _sum | parse | line 3: unexpected character '_' |
| 799 | left_Rotate | parse | line 5: unexpected character '%' |
| 801 | test_three_equal | parse | line 10: expected '{', found 'if' |
| 802 | count_Rotation | parse | line 16: expected ':=', found ';' |
| 803 | is_Perfect_Square | parse | line 15: expected 'else', found 'i' |
| 804 | is_Product_Even | parse | line 3: unexpected character '%' |
| 807 | first_odd | parse | line 3: unexpected character '%' |
| 820 | check_monthnum_number | wf | bool literal in a v0 task; bool literal in a v0 task |
| 831 | count_Pairs | parse | line 23: expected 'else', found 'j' |
| 836 | max_sub_array_sum | parse | line 24: expected 'else', found 'if' |
| 841 | get_inv_count | parse | line 8: expected '{', found 'i' |
| 842 | get_odd_occurence | parse | line 4: unexpected character '%' |
| 843 | nth_super_ugly_number | parse | line 9: '[' does not start an expression |
| 845 | find_Digits | parse | line 11: unexpected character '/' |
| 846 | find_platform | parse | line 11: expected ']', found '.' |
| 848 | area_trapezium | parse | line 6: unexpected character '/' |
| 849 | Sum | parse | line 17: unexpected character '%' |
| 850 | is_triangleexists | wf | bool literal in a v0 task; bool literal in a v0 task |
| 853 | sum_of_odd_Factors | parse | line 8: unexpected character '%' |
| 855 | check_Even_Parity | parse | line 3: unexpected character '&' |
| 856 | find_Min_Swaps | parse | line 10: expected '{', found 'var' |
| 863 | find_longest_conseq_subseq | parse | line 31: expected 'else', found 'i' |
| 867 | min_Num | parse | line 4: unexpected character '%' |
| 870 | sum_positivenum | parse | line 5: expected 'decreases', found '=' |
| 876 | lcm | parse | line 6: unexpected character '/' |
| 881 | sum_even_odd | parse | line 5: unexpected character '/' |
| 884 | all_Bits_Set_In_The_Given_Range | parse | line 4: unexpected character '&' |
| 887 | is_odd | parse | line 3: unexpected character '&' |
| 890 | find_Extra | wf | v0 has int only; operator 'len' not in v0; == wants two ints or two bools; operator 'len' not in v0; == wants two ints o |
| 891 | same_Length | wf | operator 'len' not in v0; operator 'len' not in v0; operator 'len' not in v0; operator 'len' not in v0 |
| 895 | max_sum_subseq | parse | line 7: expected ']', found '.' |
| 899 | check | parse | line 6: 'seq' is not one of int bool |
| 901 | smallest_multiple | parse | line 11: unexpected character '/' |
| 903 | count_Unset_Bits | parse | line 8: unexpected character '&' |
| 905 | sum_of_square | parse | line 4: expected ')', found 'for' |
| 909 | previous_palindrome | parse | line 27: unexpected character '%' |
| 911 | maximum_product | parse | line 23: expected '{', found 'if' |
| 918 | coin_change | parse | line 11: expected '{', found 'min_val' |
| 919 | multiply_list | parse | line 8: expected ']', found '.' |
| 934 | dealnnoy_num | wf | task decreases without a self-call |
| 935 | series_sum | parse | line 5: unexpected character '/' |
| 952 | nCr_mod_p | parse | line 10: unexpected character '%' |
| 953 | subset | wf | v0 has int only |
| 955 | is_abundant | parse | line 13: unexpected character '%' |
| 957 | get_First_Set_Bit_Pos | parse | line 4: unexpected character '&' |
| 962 | sum_Even | parse | line 9: unexpected character '%' |
| 968 | floor_Max | parse | line 7: expected '{', found 'if' |
| 970 | min_of_two | wf | v1 expression form in a v0 task; call of unknown fun min; == wants two ints or two bools |
| 971 | maximum_segments | parse | line 11: unexpected character '/' |


## Reading, written after the run (2026-09-08)

The machine: the lab workstation, four RTX 6000 Ada GPUs (this run pinned to
GPU 0 via ollama.log) with about 6 GB free beside a colleague's resident
models, qwen2.5-coder:7b through ollama
0.32.15 (family qwen2, 7.6B parameters, Q4_K_M), 8192 context, temperature
0, seed 1, one reply per problem, 1.5 s per reply over 368 problems. The
server was started for the run and killed as its last step. The seven
kernels are the pinned ones AGREEMENT.md names; 48 jobs, 744 s, 0 flaked
cells (unwitnessed: spec-gen.log and spec-kernels.log do not state a job
count or a flake count, so this figure has no kept artifact behind it).

**The numbers 12.6 asked for.** Of 368 problems, 64 became a well-formed t
task. Of those 64, 43 verify with a refuted twin in at least one column
and 4 in all seven. Of the 43, 33 pass the problem's own three assertions
and 10 fail them. Of the 4, all 4 pass. Per 368 problems: 1.1% reach the
seven-column bar and pass their tests, 9.0% verify somewhere and pass,
11.1% pass their tests at all, 17.4% are well-formed t.

**Where the 304 losses are.** 254 replies do not parse and 50 parse but
are not well-formed. The parse refusals sort into four classes: 102 use
division or modulo (`/` 34, `%` 68), which t does not have (ROADMAP 12.7
ranks div-mod third in the construct census); 37 use bitwise operators
(`& ^ |`), which t does not have and the census does not name; 46 write
an `if` with no `else`, which the notation refuses; 69 slip on notation
(Python `for`, slicing, attribute access, quotes, a seq-typed local,
`else if` chains). The 50 well-formedness refusals: 16 are only the
version header (the task reads `t 0` and uses a v1 form; with `t 1` it
is well-formed), 21 call functions t does not have (max, min, abs, pow,
a helper the model invented), 7 carry a task `decreases` without a
self-call, 3 self-call without one, 3 are type errors. The two truncated
replies (num_predict 1024) are in the parse count. So the largest single
loss is the language, not the model: 139 of 368 replies reach for an
operator t lacks, and every one of those problems is out of reach until
the construct exists.

**The finding: a spec that restates the body.** 35 of the 64 tasks have
an `ensures` that is the body's expression verbatim (`ensures r == E`,
body `r := E`). 34 of them verify with a refuted twin somewhere, 27 pass
their tests, and 8 of the 10 verified-but-wrong tasks are of this shape.
dog_age says `ensures r == human_years * 7`; the problem's answer for 12
is 61. rombus_area says `ensures r == p1 * p2`; the answer for (10, 20) is
100, half of it, and half needs division. The kernels prove such a task
in a step, the twin (a mutated body) fails the copied spec and is refuted
on its witness, and the cell counts. Nothing in the twin discipline asks
whether the spec is the problem's; that is what the tests are for, and
12.6's warning that "a vacuous specification verifies trivially" has a
sharper form here: a spec that is the body is not vacuous, it is
verified, refuted-twin and all, and it is still not a specification. For
the training thesis this is the number that matters: rewarded on
"verifies with a refuted twin" alone, 34 of the 43 rewarded tasks are
body copies and 8 of the 43 are wrong programs. The tests are not an
optional second check; they are the arm that makes the reward mean the
problem.

fstar sees the same thing from the other side. Its 32 malformed reals are
exactly the 32 body copies it was handed: F* discharges `r == E` for a
body `E` by unfolding, sends the solver nothing, and the adapter's rule
that zero logged obligations is not a proof (13.2 named this class on
the lifted corpus at 19) reads MALFORMED. On this corpus the rule is a
detector of specs that carry no obligation, and its 11 verified/refuted
cells are the tasks whose spec said something the body had to earn.

**The four that reach seven columns** are maximum, max_of_two, gcd and
fibonacci: two near-copies of the `max` example the prompt shows, a
near-copy of the `gcd` example, and a fibonacci in the shape of the
committed `fib`. A 7B model at temperature 0 reproduces the examples it
was given and fails outside them; the seven-column count says nothing
about t beyond that until a model that can write a loop invariant is
run, and that needs more than 6 GB.

**The 21 tasks no column counts**: 16 have a real the kernels cannot
prove (recursive spec funs and closed forms, `sum_series`, `get_pell`,
`find_lucas`, `get_perrin`: honest incompleteness without hints, the same
class as the lifted corpus's verus and rocq columns), of which 7 pass
their tests; 1 has no twin at all (`volume_cube`, a body with no `if` and
no loop, which the ladder has no operator for); the rest are malformed in
one lowering or timeouts. `find_missing`'s requires excludes every test
input, the one requires-excluded row: a precondition the model wrote that
the problem does not have.

**What this run does not measure**: more than one sample per problem, any
temperature above 0, any model larger than 7B, HumanEval (16.3), and
whether a header-only repair (`t 0` to `t 1`) or an `else { }` insertion
would be fair game for the extract stage; both are recorded as refusal
classes here and left unrepaired, so the table is what the model wrote.

## Addendum, 2026-09-08 evening: the same 368 replies under a t with division

t gained `div` and `mod` later the same day (SPEC.md "Division and
modulo", ROADMAP 12.7). The 368 replies above were re-parsed unchanged
under the new grammar, no model call, and the well-formed tasks re-run
through the seven kernels (`out/spec-experiment/qwen2.5-coder-7b-divmod/`,
same instrument, `--model qwen2.5-coder:7b-divmod`):

| stage | before | with div and mod |
|---|---:|---:|
| blocks that parse | 114 | 155 |
| well-formed tasks | 64 | 70 |
| pass their tests | 41 | 44 |
| verify with a refuted twin, at least one column | 43 | 45 |
| of those, pass their tests | 33 | 34 |
| verify with a refuted twin, all seven | 4 | 4 |

Of the 102 replies that had reached for `/` or `%`, 41 moved: 6 straight
to well-formed tasks and 35 to a well-formedness refusal, almost all the
model writing `t 0` over an operator that is v1 (`v1 expression form in a
v0 task`, `v0 has int only`). The four seven-column tasks are the same
four. So division was the largest single parse loss and not the largest
loss: the `if` with no `else` (56 replies) and the notation slips remain,
and a 7B model at temperature 0 does not become a t writer because the
language gained an operator it kept asking for.
