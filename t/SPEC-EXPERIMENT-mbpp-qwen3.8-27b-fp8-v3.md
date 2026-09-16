# The spec experiment on MBPP: qwen3.8-27b-fp8-v3

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
| replies with a t block | 641 |
| blocks that parse | 483 |
| tasks that are well-formed (graded below) | 323 |

Refusals, by named reason:

- 22 x `wf: vN has int only [SPEC: vN has int only]`
- 18 x `parse: <string>:N:N: expected ')', found 'ensures' [Expr]`
- 17 x `parse: <string>:N:N: expected ')', found '{' [Expr]`
- 15 x `wf: == wants two ints, two bools, two seqs, two nested seqs, or two pairs `
- 14 x `parse: <string>:N:N: comparisons do not chain`
- 13 x `wf: task decreases without a self-call [SPEC: a task decreases requires a `
- 11 x `wf: len of a non-seq [SPEC: len is defined on a seq (Gate N)]`
- 10 x `parse: <string>:N:N: unexpected character '^' [Id]`
- 10 x `wf: bool literal in a vN task [SPEC: the bool literal is a vN construct (G`
- 8 x `wf: implies over non-bool [SPEC: and/or/not/implies are bool-only]`
- 7 x `parse: <string>:N:N: 'exists' does not start an expression [Expr]`
- 7 x `parse: <string>:N:N: expected ')', found 'end of input' [Expr]`
- 7 x `wf: operator 'div' not in vN [SPEC: an operator must be in the declared ve`
- 6 x `parse: <string>:N:N: expected 'id', found 't' [Task]`
- 6 x `wf: operator 'seq' not in vN [SPEC: an operator must be in the declared ve`
- 5 x `parse: <string>:N:N: 'var' does not start an expression [Expr]`
- 5 x `wf: bound var i shadows a name in scope [SPEC: a bound variable must not c`
- 5 x `parse: <string>:N:N: expected ']', found 'for' [Expr]`
- 4 x `parse: <string>:N:N: expected ',', found 'end of input' [Expr]`
- 4 x `parse: <string>:N:N: expected ')', found 'else' [Expr]`
- 4 x `wf: call of unknown fun maxN [SPEC: call names a declared spec_fun or the `
- 4 x `parse: <string>:N:N: expected '{', found 'in' [Stmt]`
- 4 x `wf: operator 'mod' not in vN [SPEC: an operator must be in the declared ve`
- 3 x `parse: <string>:N:N: expected 'in', found ':' [Expr]`
- 3 x `wf: find wants (seq, seq) [SPEC: each string-library member's argument typ`

## The problem's own tests (interp on the MBPP assertions)

| outcome | tasks |
|---|---:|
| pass | 237 |
| fail | 77 |
| requires-excluded | 5 |
| undefined | 1 |
| signature | 3 |

## The seven kernels (real / twin), over the well-formed tasks

| kernel | verified / refuted | of tasks |
|---|---:|---:|
| dafny | 134 | 323 |
| verus | 115 | 323 |
| spark | 125 | 323 |
| framac | 100 | 323 |
| lean | 91 | 323 |
| rocq | 97 | 323 |
| fstar | 110 | 323 |

| columns counting | 7 | 6 | 5 | 4 | 3 | 2 | 1 | 0 |
|---|---|---|---|---|---|---|---|---|
| tasks | 69 | 18 | 9 | 15 | 16 | 10 | 8 | 178 |

Tasks with no twin at all (every mutation on the ladder computes what the real body computes, or no input satisfies requires): 10.

## 12.6's table: verifies with a refuted twin, against passes its tests

| verifies with refuted twin in | tests pass | tests fail | requires-excluded | undefined | signature |
|---|---:|---:|---:|---:|---:|
| all seven | 57 | 11 | 1 | 0 | 0 |
| some column | 60 | 14 | 0 | 0 | 2 |
| none | 120 | 52 | 4 | 1 | 1 |

**57 of 649 problems** got a task that verifies with a refuted twin in all seven columns and passes its tests; 117 in at least one column. Verified-with-twin but failing its tests, the class 12.6 warns about: 11 in all seven, 14 in some column.

MBPP-DFY subset: 117 pool problems are MBPP-DFY problems (ROADMAP 16.2's family); 74 of them reached the kernels and 27 verify in all seven and pass their tests.

## Every task

| task_id | task | columns counting | tests | dafny | verus | spark | framac | lean | rocq | fstar |
|---:|---|---:|---|---|---|---|---|---|---|---|
| 4 | mbpp_4__heap_queue_largest | 0 | fail | refuted / refuted | refuted / refuted | timeout / timeout | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 5 | mbpp_5__count_ways | 0 | fail | unproved / unproved | unproved / refuted | unproved / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 8 | mbpp_8__square_nums | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 9 | mbpp_9__find_Rotations | 0 | fail | refuted / unproved | refuted / refuted | refuted / refuted | abstain / abstain | timeout / timeout | timeout / refuted | refuted / unproved |
| 10 | mbpp_10__small_nnum | 0 | fail | refuted / refuted | refuted / refuted | malformed / malformed | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| 11 | mbpp_11__remove_Occ | 0 | fail | unproved / refuted | refuted / refuted | refuted / refuted | abstain / abstain | refuted / unproved | unproved / refuted | unproved / refuted |
| 14 | mbpp_14__find_Volume | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 16 | mbpp_16__text_lowercase_underscore | 0 | pass | unproved / refuted | unproved / refuted | malformed / malformed | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| 17 | mbpp_17__square_perimeter | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 18 | mbpp_18__remove_dirty_chars | 2 | pass | verified / refuted | unproved / refuted | verified / refuted | abstain / abstain | timeout / timeout | abstain / abstain | timeout / refuted |
| 19 | mbpp_19__test_duplicate | 3 | pass | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| 21 | mbpp_21__multiples_of_num | 6 | pass | verified / refuted | malformed / malformed | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 22 | mbpp_22__find_first_duplicate | 0 | pass | unproved / refuted | unproved / refuted | timeout / unproved | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 28 | mbpp_28__binomial_Coeff | 0 | pass | unproved / unproved | unproved / refuted | timeout / refuted | timeout / unproved | unproved / unproved | unproved / unproved | unproved / refuted |
| 34 | mbpp_34__find_missing | 0 | requires-excluded | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 35 | mbpp_35__find_rect_num | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 41 | mbpp_41__filter_evennumbers | 2 | pass | verified / refuted | unproved / refuted | verified / refuted | timeout / refuted | timeout / timeout | timeout / refuted | timeout / timeout |
| 43 | mbpp_43__text_match | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | timeout / unproved | unproved / refuted |
| 44 | mbpp_44__text_match_string | 4 | pass | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / unproved | verified / refuted | unproved / refuted |
| 46 | mbpp_46__test_distinct | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 47 | mbpp_47__compute_Last_Digit | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | vacuous / vacuous | abstain / abstain | abstain / abstain | abstain / abstain |
| 52 | mbpp_52__parallelogram_area | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 55 | mbpp_55__tn_gp | 0 | pass | unproved / unproved | unproved / refuted | unproved / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 59 | mbpp_59__is_octagonal | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 62 | mbpp_62__smallest_num | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / refuted | verified / refuted |
| 68 | mbpp_68__is_Monotonic | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | timeout / timeout | unproved / refuted |
| 69 | mbpp_69__is_sublist | 0 | pass | unproved / unproved | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 72 | mbpp_72__dif_Square | 5 | fail | verified / refuted | malformed / malformed | verified / refuted | verified / refuted | verified / refuted | malformed / malformed | verified / refuted |
| 74 | mbpp_74__is_samepatterns | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 77 | mbpp_77__is_Diff | 0 | fail | timeout / timeout | unproved / refuted | timeout / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 86 | mbpp_86__centered_hexagonal_number | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 89 | mbpp_89__closest_num | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 92 | mbpp_92__is_undulating | 0 | pass | unproved / unproved | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 93 | mbpp_93__power | 0 | pass | unproved / unproved | unproved / refuted | unproved / refuted | malformed / malformed | unproved / unproved | unproved / unproved | unproved / refuted |
| 102 | mbpp_102__snake_to_camel | 0 | pass | unproved / unproved | unproved / refuted | timeout / malformed | abstain / abstain | unproved / unproved | timeout / refuted | unproved / refuted |
| 103 | mbpp_103__eulerian_num | 0 | fail | unproved / unproved | unproved / refuted | timeout / refuted | timeout / unproved | unproved / unproved | unproved / unproved | unproved / refuted |
| 107 | mbpp_107__count_Hexadecimal | 0 | pass | unproved / refuted | unproved / refuted | unproved / refuted | abstain / abstain | unproved / unproved | unproved / unproved | unproved / refuted |
| 108 | mbpp_108__merge_sorted_list | 0 | pass | refuted / refuted | refuted / refuted | malformed / malformed | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| 109 | mbpp_109__odd_Equivalent | 0 | requires-excluded | unproved / unproved | unproved / refuted | unproved / refuted | timeout / unproved | unproved / unproved | unproved / unproved | unproved / refuted |
| 112 | mbpp_112__perimeter | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 121 | mbpp_121__check_triplet | 0 | fail | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 122 | mbpp_122__smartNumber | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 123 | mbpp_123__amicable_numbers_sum | 0 | pass | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 127 | mbpp_127__multiply_int | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 135 | mbpp_135__hexagonal_num | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 138 | mbpp_138__is_Sum_Of_Powers_Of_Two | 0 | fail | unproved / unproved | unproved / unproved | timeout / refuted | unproved / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 150 | mbpp_150__does_Contain_B | 3 | pass | verified / refuted | unproved / refuted | verified / refuted | abstain / abstain | verified / refuted | unproved / refuted | unproved / refuted |
| 151 | mbpp_151__is_coprime | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 162 | mbpp_162__sum_series | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | vacuous / vacuous | unproved / refuted | unproved / refuted | unproved / refuted |
| 168 | mbpp_168__frequency | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | unproved / refuted | abstain / abstain |
| 169 | mbpp_169__get_pell | 0 | pass | unproved / unproved | unproved / refuted | unproved / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 171 | mbpp_171__perimeter_pentagon | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 172 | mbpp_172__count_occurance | 0 | pass | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 173 | mbpp_173__remove_splchar | 4 | pass | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | timeout / timeout | timeout / refuted | verified / refuted |
| 175 | mbpp_175__is_valid_parenthese | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | unproved / unproved | unproved / refuted |
| 176 | mbpp_176__perimeter_triangle | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 179 | mbpp_179__is_num_keith | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 184 | mbpp_184__greater_specificnum | 4 | fail | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | verified / refuted |
| 188 | mbpp_188__prod_Square | 0 | fail | unproved / unproved | unproved / unproved | refuted / timeout | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 189 | mbpp_189__first_Missing_Positive | 0 | pass | unproved / unproved | malformed / malformed | refuted / timeout | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 190 | mbpp_190__count_Intgral_Points | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 194 | mbpp_194__octal_To_Decimal | 0 | fail | unproved / unproved | unproved / unproved | malformed / malformed | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| 195 | mbpp_195__first | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 199 | mbpp_199__highest_Power_of_2 | 0 | pass | refuted / refuted | refuted / refuted | unproved / refuted | unproved / refuted | refuted / refuted | unproved / refuted | refuted / refuted |
| 201 | mbpp_201__chkList | 4 | pass | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | verified / refuted |
| 202 | mbpp_202__remove_even | 0 | pass | unproved / refuted | unproved / refuted | timeout / timeout | timeout / refuted | unproved / refuted | timeout / refuted | unproved / refuted |
| 204 | mbpp_204__count | 1 | pass | verified / unproved | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | verified / refuted | timeout / refuted |
| 207 | mbpp_207__find_longest_repeating_subseq | 0 | fail | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 208 | mbpp_208__is_decimal | 0 | fail | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 210 | mbpp_210__is_allowed_specific_char | 4 | pass | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | verified / refuted |
| 212 | mbpp_212__fourth_Power_Sum | 3 | pass | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | verified / refuted | verified / refuted | verified / timeout |
| 217 | mbpp_217__first_Repeated_Char | 0 | pass | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 218 | mbpp_218__min_Operations | 0 | pass | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 221 | mbpp_221__first_even | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 223 | mbpp_223__is_majority | 0 | pass | refuted / unproved | refuted / refuted | refuted / refuted | abstain / abstain | unproved / refuted | unproved / refuted | refuted / refuted |
| 225 | mbpp_225__find_Min | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / unproved | timeout / refuted | unproved / refuted |
| 226 | mbpp_226__odd_values_string | 4 | pass | verified / refuted | verified / refuted | verified / timeout | verified / refuted | unproved / refuted | timeout / refuted | verified / refuted |
| 227 | mbpp_227__min_of_three | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 230 | mbpp_230__replace_blank | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 234 | mbpp_234__volume_cube | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 235 | mbpp_235__even_bit_set_number | 0 | fail | refuted / refuted | malformed / malformed | timeout / timeout | timeout / timeout | timeout / timeout | timeout / timeout | refuted / refuted |
| 239 | mbpp_239__get_total_number_of_sequences | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 244 | mbpp_244__next_Perfect_Square | 0 | pass | unproved / unproved | unproved / refuted | unproved / refuted | refuted / refuted | unproved / unproved | unproved / refuted | unproved / refuted |
| 251 | mbpp_251__insert_element | 4 | signature | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | unproved / refuted | timeout / refuted | verified / refuted |
| 260 | mbpp_260__newman_prime | 6 | pass | verified / refuted | malformed / malformed | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 264 | mbpp_264__dog_age | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 266 | mbpp_266__lateralsurface_cube | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 267 | mbpp_267__square_Sum | 0 | pass | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 268 | mbpp_268__find_star_num | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 269 | mbpp_269__ascii_value | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 270 | mbpp_270__sum_even_and_even_index | 2 | pass | unproved / unproved | verified / refuted | timeout / refuted | verified / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 271 | mbpp_271__even_Power_Sum | 0 | pass | refuted / refuted | refuted / refuted | timeout / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 279 | mbpp_279__is_num_decagonal | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 281 | mbpp_281__all_unique | 3 | pass | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| 282 | mbpp_282__sub_list | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 283 | mbpp_283__validate | 0 | pass | unproved / unproved | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | unproved / unproved | unproved / refuted |
| 285 | mbpp_285__text_match_two_three | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / timeout | timeout / unproved | unproved / refuted |
| 287 | mbpp_287__square_Sum | 6 | pass | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 291 | mbpp_291__count_no_of_ways | 0 | fail | unproved / unproved | unproved / refuted | timeout / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 292 | mbpp_292__find | 6 | pass | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 302 | mbpp_302__set_Bit_Number | 0 | pass | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 306 | mbpp_306__max_sum_increasing_subseq | 0 | fail | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 308 | mbpp_308__large_product | 0 | fail | refuted / refuted | refuted / refuted | malformed / malformed | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 309 | mbpp_309__maximum | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 313 | mbpp_313__pos_nos | 0 | fail | refuted / unproved | refuted / refuted | refuted / timeout | refuted / refuted | unproved / refuted | refuted / unproved | refuted / refuted |
| 316 | mbpp_316__find_last_occurrence | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 318 | mbpp_318__max_volume | 0 | pass | unproved / unproved | unproved / refuted | timeout / timeout | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 323 | mbpp_323__re_arrange | 0 | undefined | refuted / refuted | refuted / refuted | malformed / malformed | abstain / abstain | abstain / abstain | abstain / abstain | refuted / refuted |
| 328 | mbpp_328__rotate_left | 0 | fail | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | refuted / refuted | refuted / refuted | refuted / refuted |
| 337 | mbpp_337__text_match_word | 3 | fail | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| 345 | mbpp_345__diff_consecutivenums | 0 | pass | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 348 | mbpp_348__find_ways | 0 | fail | unproved / unproved | unproved / refuted | timeout / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 349 | mbpp_349__check | 3 | pass | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / unproved | timeout / unproved | unproved / refuted |
| 352 | mbpp_352__unique_Characters | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 354 | mbpp_354__tn_ap | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 355 | mbpp_355__count_Rectangles | 0 | fail | unproved / unproved | unproved / refuted | unproved / refuted | refuted / vacuous | abstain / abstain | abstain / abstain | abstain / abstain |
| 356 | mbpp_356__find_angle | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 358 | mbpp_358__moddiv_list | 0 | pass | refuted / refuted | refuted / refuted | malformed / malformed | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 360 | mbpp_360__get_carol | 0 | fail | unproved / unproved | unproved / refuted | unproved / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 362 | mbpp_362__max_occurrences | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | refuted / refuted | unproved / refuted |
| 365 | mbpp_365__count_Digit | 3 | pass | verified / unproved | verified / refuted | malformed / malformed | abstain / abstain | verified / refuted | verified / refuted | abstain / abstain |
| 369 | mbpp_369__lateralsurface_cuboid | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 371 | mbpp_371__smallest_missing | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 372 | mbpp_372__heap_assending | 0 | fail | unproved / unproved | malformed / malformed | malformed / malformed | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| 373 | mbpp_373__volume_cuboid | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 377 | mbpp_377__remove_Char | 1 | fail | verified / refuted | unproved / refuted | timeout / refuted | abstain / abstain | timeout / timeout | timeout / refuted | unproved / refuted |
| 379 | mbpp_379__surfacearea_cuboid | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 382 | mbpp_382__find_rotation_count | 0 | pass | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | unproved / unproved | timeout / refuted | refuted / refuted |
| 385 | mbpp_385__get_perrin | 0 | pass | unproved / unproved | unproved / refuted | unproved / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 387 | mbpp_387__even_or_odd | 0 | pass | refuted / refuted | refuted / refuted | timeout / timeout | abstain / abstain | unproved / unproved | refuted / refuted | refuted / refuted |
| 388 | mbpp_388__highest_Power_of_2 | 0 | pass | refuted / refuted | refuted / refuted | unproved / refuted | unproved / refuted | refuted / refuted | unproved / refuted | refuted / refuted |
| 389 | mbpp_389__find_lucas | 0 | pass | unproved / unproved | unproved / refuted | unproved / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 392 | mbpp_392__get_max_sum | 0 | fail | unproved / unproved | unproved / refuted | timeout / timeout | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 403 | mbpp_403__is_valid_URL | 0 | pass | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 404 | mbpp_404__minimum | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 411 | mbpp_411__snake_to_camel | 0 | pass | unproved / unproved | unproved / refuted | timeout / malformed | abstain / abstain | unproved / unproved | refuted / refuted | unproved / refuted |
| 412 | mbpp_412__remove_odd | 3 | pass | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | timeout / timeout | timeout / refuted | timeout / refuted |
| 414 | mbpp_414__overlapping | 0 | pass | unproved / refuted | unproved / refuted | timeout / timeout | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 420 | mbpp_420__cube_Sum | 0 | pass | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 426 | mbpp_426__filter_oddnumbers | 2 | pass | verified / refuted | unproved / refuted | verified / refuted | timeout / refuted | timeout / timeout | timeout / refuted | timeout / timeout |
| 427 | mbpp_427__change_date_format | 0 | fail | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 428 | mbpp_428__shell_sort | 0 | pass | unproved / refuted | timeout / refuted | malformed / malformed | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| 433 | mbpp_433__check_greater | 3 | pass | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | unproved / refuted | abstain / abstain | verified / unproved |
| 434 | mbpp_434__text_match_one | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | unproved / unproved | unproved / refuted |
| 436 | mbpp_436__neg_nos | 0 | fail | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 437 | mbpp_437__remove_odd | 0 | pass | refuted / refuted | refuted / refuted | refuted / timeout | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 441 | mbpp_441__surfacearea_cube | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 443 | mbpp_443__largest_neg | 0 | fail | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 447 | mbpp_447__cube_nums | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 448 | mbpp_448__cal_sum | 0 | pass | unproved / unproved | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | unproved / unproved | unproved / refuted |
| 451 | mbpp_451__remove_whitespaces | 4 | pass | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | timeout / timeout | timeout / refuted | verified / refuted |
| 453 | mbpp_453__sumofFactors | 0 | pass | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 454 | mbpp_454__text_match_wordz | 3 | pass | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / unproved | timeout / unproved | unproved / refuted |
| 458 | mbpp_458__rectangle_area | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 459 | mbpp_459__remove_uppercase | 4 | pass | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | timeout / timeout | timeout / refuted | verified / refuted |
| 466 | mbpp_466__find_peak | 0 | pass | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 472 | mbpp_472__check_Consecutive | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 474 | mbpp_474__replace_char | 6 | pass | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 477 | mbpp_477__is_lower | 0 | pass | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 478 | mbpp_478__remove_lowercase | 2 | pass | unproved / refuted | unproved / refuted | verified / refuted | verified / refuted | unproved / refuted | timeout / refuted | timeout / timeout |
| 481 | mbpp_481__is_subset_sum | 0 | pass | unproved / unproved | unproved / refuted | unproved / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 482 | mbpp_482__match | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | timeout / unproved | unproved / refuted |
| 492 | mbpp_492__binary_search | 0 | pass | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | unproved / refuted | refuted / refuted |
| 498 | mbpp_498__gcd | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 499 | mbpp_499__diameter_circle | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 501 | mbpp_501__num_comm_div | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 502 | mbpp_502__find | 0 | pass | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 503 | mbpp_503__add_consecutive_nums | 0 | pass | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 504 | mbpp_504__sum_Of_Series | 0 | pass | timeout / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 507 | mbpp_507__remove_words | 0 | pass | unproved / refuted | unproved / refuted | malformed / malformed | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 509 | mbpp_509__average_Odd | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 511 | mbpp_511__find_Min_Sum | 0 | fail | timeout / refuted | malformed / malformed | refuted / refuted | unproved / unproved | unproved / unproved | timeout / timeout | refuted / refuted |
| 515 | mbpp_515__modular_sum | 0 | requires-excluded | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 517 | mbpp_517__largest_pos | 0 | pass | unproved / refuted | unproved / refuted | unproved / refuted | timeout / refuted | unproved / refuted | timeout / refuted | unproved / refuted |
| 518 | mbpp_518__sqrt_root | 0 | pass | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | unproved / unproved | refuted / refuted | refuted / refuted |
| 520 | mbpp_520__get_lcm | 0 | pass | unproved / unproved | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | unproved / unproved | unproved / refuted |
| 521 | mbpp_521__check_isosceles | 5 | pass | verified / refuted | malformed / malformed | verified / refuted | verified / refuted | verified / refuted | malformed / malformed | verified / refuted |
| 525 | mbpp_525__parallel_lines | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| 526 | mbpp_526__capitalize_first_last_letters | 0 | pass | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 529 | mbpp_529__jacobsthal_lucas | 0 | pass | unproved / unproved | unproved / refuted | unproved / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 531 | mbpp_531__min_coins | 0 | pass | unproved / unproved | unproved / refuted | timeout / refuted | refuted / unproved | unproved / unproved | unproved / unproved | unproved / refuted |
| 536 | mbpp_536__nth_items | 1 | pass | timeout / refuted | malformed / refuted | timeout / timeout | timeout / refuted | unproved / refuted | unproved / refuted | verified / refuted |
| 539 | mbpp_539__basesnum_coresspondingnum | 4 | pass | verified / unproved | verified / refuted | verified / refuted | abstain / abstain | unproved / refuted | verified / refuted | verified / refuted |
| 542 | mbpp_542__fill_spaces | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 543 | mbpp_543__count_digits | 3 | pass | verified / unproved | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / timeout | abstain / abstain |
| 550 | mbpp_550__find_Max | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 554 | mbpp_554__Split | 2 | pass | verified / refuted | unproved / refuted | verified / refuted | timeout / refuted | timeout / timeout | timeout / refuted | timeout / timeout |
| 555 | mbpp_555__difference | 1 | pass | timeout / refuted | verified / refuted | timeout / refuted | timeout / refuted | unproved / unproved | unproved / refuted | timeout / refuted |
| 556 | mbpp_556__find_Odd_Pair | 0 | pass | unproved / unproved | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / refuted | unproved / refuted |
| 557 | mbpp_557__toggle_string | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| 565 | mbpp_565__split | 0 | pass | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 567 | mbpp_567__issort_list | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | timeout / refuted | unproved / refuted |
| 571 | mbpp_571__max_sum_pair_diff_lessthan_K | 4 | fail | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | unproved / refuted | verified / refuted | verified / refuted |
| 576 | mbpp_576__is_Sub_Array | 0 | pass | unproved / unproved | malformed / malformed | timeout / timeout | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 577 | mbpp_577__last_Digit_Factorial | 0 | pass | timeout / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 578 | mbpp_578__interleave_lists | 5 | pass | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | timeout / timeout | verified / refuted | verified / refuted |
| 581 | mbpp_581__surface_Area | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 584 | mbpp_584__find_adverbs | 0 | fail | tool_error / tool_error | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | timeout / refuted | abstain / abstain |
| 586 | mbpp_586__split_Arr | 6 | pass | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| 591 | mbpp_591__swap_List | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 593 | mbpp_593__removezero_ip | 0 | pass | refuted / refuted | refuted / refuted | refuted / timeout | abstain / abstain | refuted / refuted | refuted / refuted | abstain / abstain |
| 597 | mbpp_597__find_kth | 0 | pass | unproved / unproved | malformed / malformed | refuted / refuted | abstain / abstain | timeout / timeout | unproved / unproved | refuted / refuted |
| 598 | mbpp_598__armstrong_number | 0 | fail | refuted / refuted | refuted / refuted | abstain / abstain | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 602 | mbpp_602__first_repeated_char | 0 | fail | unproved / refuted | unproved / refuted | unproved / unproved | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 605 | mbpp_605__prime_num | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 609 | mbpp_609__floor_Min | 0 | pass | refuted / refuted | refuted / refuted | refuted / refuted | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 610 | mbpp_610__remove_kth_element | 6 | fail | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| 620 | mbpp_620__largest_subset | 0 | fail | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 623 | mbpp_623__nth_nums | 0 | pass | unproved / unproved | unproved / refuted | unproved / refuted | abstain / abstain | unproved / refuted | unproved / unproved | unproved / refuted |
| 624 | mbpp_624__is_upper | 0 | pass | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 625 | mbpp_625__swap_List | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 626 | mbpp_626__triangle_area | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 628 | mbpp_628__replace_spaces | 4 | pass | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / unproved | abstain / abstain |
| 629 | mbpp_629__Split | 2 | pass | verified / refuted | unproved / refuted | verified / refuted | timeout / refuted | timeout / timeout | timeout / refuted | timeout / timeout |
| 631 | mbpp_631__replace_spaces | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 634 | mbpp_634__even_Power_Sum | 0 | pass | refuted / refuted | refuted / refuted | timeout / timeout | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 635 | mbpp_635__heap_sort | 0 | fail | unproved / refuted | unproved / refuted | malformed / malformed | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 640 | mbpp_640__remove_parenthesis | 0 | fail | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 641 | mbpp_641__is_nonagonal | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| 644 | mbpp_644__reverse_Array_Upto_K | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 649 | mbpp_649__sum_Range_list | 0 | fail | unproved / unproved | unproved / refuted | timeout / refuted | vacuous / vacuous | unproved / refuted | unproved / unproved | unproved / refuted |
| 654 | mbpp_654__rectangle_perimeter | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 655 | mbpp_655__fifth_Power_Sum | 0 | pass | refuted / refuted | refuted / refuted | timeout / timeout | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 664 | mbpp_664__average_Even | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 666 | mbpp_666__count_char | 0 | pass | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 668 | mbpp_668__replace | 0 | pass | refuted / refuted | refuted / refuted | timeout / timeout | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 670 | mbpp_670__decreasing_trend | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | timeout / timeout | unproved / refuted |
| 672 | mbpp_672__max_of_three | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 673 | mbpp_673__convert | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / unproved | unproved / refuted |
| 676 | mbpp_676__remove_extra_char | 4 | pass | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | timeout / timeout | timeout / refuted | verified / refuted |
| 677 | mbpp_677__validity_triangle | 5 | fail | verified / refuted | malformed / malformed | verified / refuted | verified / refuted | verified / refuted | malformed / malformed | verified / refuted |
| 678 | mbpp_678__remove_spaces | 2 | pass | verified / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | verified / refuted | unproved / refuted |
| 680 | mbpp_680__increasing_trend | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | timeout / refuted | unproved / refuted |
| 681 | mbpp_681__smallest_Divisor | 0 | pass | timeout / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / unproved | unproved / refuted | unproved / refuted |
| 682 | mbpp_682__mul_list | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 683 | mbpp_683__sum_Square | 0 | pass | unproved / refuted | unproved / refuted | timeout / timeout | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 684 | mbpp_684__count_Char | 6 | fail | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| 687 | mbpp_687__recur_gcd | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 690 | mbpp_690__mul_consecutive_nums | 0 | pass | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 692 | mbpp_692__last_Two_Digits | 0 | pass | unproved / unproved | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 701 | mbpp_701__equilibrium_index | 0 | fail | unproved / unproved | unproved / refuted | unproved / refuted | abstain / abstain | unproved / refuted | unproved / refuted | unproved / refuted |
| 702 | mbpp_702__removals | 0 | fail | unproved / unproved | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 706 | mbpp_706__is_subset | 0 | pass | unproved / refuted | unproved / refuted | timeout / timeout | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 711 | mbpp_711__product_Equal | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | timeout / timeout |
| 716 | mbpp_716__rombus_perimeter | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 718 | mbpp_718__alternate_elements | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| 727 | mbpp_727__remove_char | 4 | pass | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | timeout / timeout | timeout / refuted | verified / refuted |
| 728 | mbpp_728__sum_list | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 729 | mbpp_729__add_list | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 732 | mbpp_732__replace_specialchar | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 733 | mbpp_733__find_first_occurrence | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 736 | mbpp_736__left_insertion | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted |
| 741 | mbpp_741__all_Characters_Same | 4 | pass | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | abstain / abstain | abstain / abstain | verified / refuted |
| 743 | mbpp_743__rotate_right | 6 | pass | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | verified / refuted | verified / refuted |
| 748 | mbpp_748__capital_words_spaces | 0 | fail | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 749 | mbpp_749__sort_numeric_strings | 0 | fail | refuted / refuted | refuted / refuted | malformed / malformed | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| 751 | mbpp_751__check_min_heap | 0 | pass | unproved / refuted | timeout / refuted | timeout / refuted | timeout / refuted | unproved / refuted | timeout / refuted | unproved / timeout |
| 752 | mbpp_752__jacobsthal_num | 0 | pass | unproved / unproved | unproved / refuted | unproved / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 754 | mbpp_754__extract_index_list | 1 | pass | unproved / refuted | unproved / refuted | verified / refuted | timeout / refuted | timeout / timeout | timeout / unproved | timeout / timeout |
| 756 | mbpp_756__text_match_zero_one | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | unproved / unproved | unproved / refuted |
| 759 | mbpp_759__is_decimal | 6 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| 760 | mbpp_760__unique_Element | 0 | pass | unproved / refuted | unproved / refuted | malformed / refuted | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |
| 764 | mbpp_764__number_ctr | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | timeout / refuted | abstain / abstain |
| 771 | mbpp_771__check_expression | 0 | pass | unproved / refuted | unproved / malformed | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain | malformed / malformed |
| 781 | mbpp_781__count_Divisors | 0 | pass | refuted / unproved | refuted / unproved | refuted / refuted | abstain / abstain | unproved / unproved | unproved / unproved | refuted / unproved |
| 786 | mbpp_786__right_insertion | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | verified / refuted |
| 787 | mbpp_787__text_match_three | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | timeout / unproved | unproved / refuted |
| 789 | mbpp_789__perimeter_polygon | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 793 | mbpp_793__last | 7 | requires-excluded | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 794 | mbpp_794__text_starta_endb | 2 | pass | verified / refuted | verified / refuted | verified / malformed | abstain / abstain | unproved / refuted | abstain / abstain | verified / malformed |
| 797 | mbpp_797__sum_in_Range | 0 | pass | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 800 | mbpp_800__remove_all_spaces | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / refuted | unproved / refuted |
| 803 | mbpp_803__is_Perfect_Square | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / unproved | unproved / unproved | unproved / refuted |
| 804 | mbpp_804__is_Product_Even | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / timeout | verified / refuted | verified / refuted |
| 807 | mbpp_807__first_odd | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 812 | mbpp_812__road_rd | 0 | pass | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 823 | mbpp_823__check_substring | 3 | pass | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / unproved | timeout / refuted | abstain / abstain |
| 824 | mbpp_824__remove_even | 3 | pass | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | timeout / timeout | timeout / refuted | timeout / refuted |
| 825 | mbpp_825__access_elements | 6 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| 838 | mbpp_838__min_Swaps | 1 | fail | verified / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 844 | mbpp_844__get_Number | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / unproved | unproved / refuted | unproved / refuted |
| 852 | mbpp_852__remove_negs | 3 | pass | verified / refuted | unproved / refuted | verified / refuted | verified / refuted | timeout / timeout | timeout / refuted | timeout / refuted |
| 853 | mbpp_853__sum_of_odd_Factors | 0 | pass | unproved / unproved | refuted / refuted | refuted / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | refuted / refuted |
| 856 | mbpp_856__find_Min_Swaps | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / unproved | unproved / refuted |
| 860 | mbpp_860__check_alphanumeric | 3 | pass | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | unproved / unproved | abstain / abstain | unproved / refuted |
| 865 | mbpp_865__ntimes_list | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 873 | mbpp_873__fibonacci | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 876 | mbpp_876__lcm | 0 | fail | refuted / unproved | refuted / refuted | refuted / refuted | timeout / timeout | unproved / unproved | refuted / refuted | refuted / refuted |
| 877 | mbpp_877__sort_String | 0 | pass | unproved / unproved | malformed / malformed | malformed / malformed | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 881 | mbpp_881__sum_even_odd | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | timeout / timeout | unproved / unproved | timeout / refuted |
| 882 | mbpp_882__parallelogram_perimeter | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 890 | mbpp_890__find_Extra | 0 | requires-excluded | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 891 | mbpp_891__same_Length | 3 | pass | verified / unproved | verified / refuted | malformed / malformed | abstain / abstain | verified / refuted | verified / refuted | abstain / abstain |
| 895 | mbpp_895__max_sum_subseq | 0 | fail | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | refuted / refuted | unproved / unproved | refuted / refuted |
| 898 | mbpp_898__extract_elements | 0 | fail | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 899 | mbpp_899__check | 0 | fail | unproved / unproved | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 900 | mbpp_900__match_num | 7 | fail | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 905 | mbpp_905__sum_of_square | 5 | fail | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | unproved / refuted | verified / refuted |
| 907 | mbpp_907__lucky_num | 5 | pass | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | timeout / refuted | verified / refuted | verified / refuted |
| 908 | mbpp_908__find_fixed_point | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 910 | mbpp_910__check_date | 5 | signature | verified / refuted | verified / refuted | verified / refuted | verified / unproved | verified / refuted | unproved / refuted | verified / refuted |
| 917 | mbpp_917__text_uppercase_lowercase | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / unproved | timeout / unproved | unproved / refuted |
| 918 | mbpp_918__coin_change | 0 | fail | unproved / unproved | refuted / refuted | refuted / refuted | unproved / unproved | refuted / unproved | unproved / unproved | refuted / refuted |
| 919 | mbpp_919__multiply_list | 0 | pass | unproved / refuted | unproved / refuted | timeout / refuted | abstain / abstain | unproved / refuted | unproved / unproved | timeout / refuted |
| 923 | mbpp_923__super_seq | 0 | pass | unproved / unproved | unproved / refuted | timeout / refuted | timeout / unproved | unproved / unproved | unproved / unproved | unproved / refuted |
| 924 | mbpp_924__max_of_two | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 926 | mbpp_926__rencontres_number | 0 | fail | unproved / unproved | unproved / refuted | timeout / refuted | refuted / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 928 | mbpp_928__change_date_format | 0 | pass | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin | no-twin / no-twin |
| 931 | mbpp_931__sum_series | 0 | pass | timeout / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 932 | mbpp_932__remove_duplic_list | 1 | pass | verified / refuted | unproved / refuted | malformed / malformed | timeout / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 933 | mbpp_933__camel_to_snake | 0 | pass | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 934 | mbpp_934__dealnnoy_num | 0 | pass | unproved / unproved | unproved / refuted | unproved / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 935 | mbpp_935__series_sum | 5 | pass | verified / refuted | verified / refuted | timeout / refuted | verified / refuted | unproved / refuted | verified / refuted | verified / refuted |
| 937 | mbpp_937__max_char | 5 | fail | verified / refuted | verified / refuted | verified / refuted | abstain / abstain | verified / refuted | timeout / refuted | verified / refuted |
| 944 | mbpp_944__num_position | 1 | pass | unproved / refuted | unproved / refuted | unproved / refuted | verified / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 955 | mbpp_955__is_abundant | 0 | fail | unproved / refuted | unproved / refuted | timeout / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| 960 | mbpp_960__get_noOfways | 0 | fail | unproved / unproved | unproved / refuted | unproved / refuted | vacuous / vacuous | unproved / unproved | unproved / unproved | unproved / refuted |
| 961 | mbpp_961__roman_to_int | 0 | signature | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted |
| 962 | mbpp_962__sum_Even | 0 | fail | malformed / malformed | malformed / malformed | malformed / malformed | malformed / malformed | unproved / unproved | unproved / unproved | unproved / unproved |
| 967 | mbpp_967__check | 2 | fail | verified / refuted | verified / refuted | timeout / refuted (FLAKED) | abstain / abstain | verified / unproved | timeout / unproved | unproved / refuted |
| 970 | mbpp_970__min_of_two | 7 | pass | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| 971 | mbpp_971__maximum_segments | 0 | pass | refuted / refuted | refuted / refuted | refuted / refuted | refuted / refuted | abstain / abstain | abstain / abstain | abstain / abstain |
| 973 | mbpp_973__left_rotate | 0 | pass | unproved / refuted | unproved / refuted | timeout / unproved | abstain / abstain | abstain / abstain | abstain / abstain | abstain / abstain |

## Problems that produced no graded task

| task_id | fn | stage | why |
|---:|---|---|---|
| 3 | is_not_prime | parse | <string>:5:26: 'exists' does not start an expression [Expr] |
| 6 | differ_At_One_Bit_Pos | wf | local in a v0 task [SPEC: locals are a v1 construct (Gate 2)]; bool literal in a v0 task [SPEC: the bool literal is a v1 |
| 7 | find_char_long | wf | len of a non-seq [SPEC: len is defined on a seq (Gate 1)]; == wants two ints, two bools, two seqs, two nested seqs, or t |
| 15 | split_lowerstring | wf | unbound var c [SPEC: a name must be bound before use (v0 and Gate 1 scope rule)]; seq literal elements must be all int o |
| 20 | is_woodall | parse | <string>:4:46: unexpected character '^' [Id] |
| 24 | binary_to_decimal | wf | task decreases without a self-call [SPEC: a task decreases requires a self-recursive body, and vice versa (Gate 3)] |
| 25 | find_Product | wf | call of unknown fun count_in [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; == wants two ints,  |
| 27 | remove | wf | len of a non-seq [SPEC: len is defined on a seq (Gate 1)]; len of a non-seq [SPEC: len is defined on a seq (Gate 1)]; le |
| 29 | get_Odd_Occurrence | parse | <string>:16:5: expected ')', found 'decreases' [Expr] |
| 30 | count_Substring_With_Equal_Ends | parse | <string>:5:1: expected ')', found '{' [Expr] |
| 32 | max_Prime_Factors | parse | <string>:8:28: expected ')', found ']' [Expr] |
| 33 | decimal_To_Binary | parse | <string>:45:69: expected ')', found 'end of input' [Expr] |
| 36 | find_Nth_Digit | parse | <string>:8:30: unexpected character '^' [Id] |
| 38 | div_even_odd | parse | <string>:19:22: comparisons do not chain; parenthesise [What the notation refuses] |
| 39 | rearange_string | parse | <string>:7:5638: expected ',', found 'end of input' [Expr] |
| 42 | find_Sum | parse | <string>:6:17: 'var' does not start an expression [Expr] |
| 45 | get_gcd | parse | <string>:9:20: expected 'in', found ':' [Expr] |
| 48 | odd_bit_set_number | parse | <string>:83:54: expected ':=', found 'end of input' [Stmt] |
| 51 | check_equilateral | wf | bool literal in a v0 task [SPEC: the bool literal is a v1 construct (Gate 1)]; bool literal in a v0 task [SPEC: the bool |
| 53 | check_Equality | wf | v0 has int only [SPEC: v0 has int only]; operator 'len' not in v0 [SPEC: an operator must be in the declared version's o |
| 54 | counting_sort | wf | == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type [SPEC: == and != apply to two int |
| 56 | check | wf | call of unknown fun last_digit [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; - over non-int [S |
| 57 | find_Max_Num | wf | call of unknown fun max_digit [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; + over non-int [SP |
| 58 | opposite_Signs | wf | bool literal in a v0 task [SPEC: the bool literal is a v1 construct (Gate 1)]; bool literal in a v0 task [SPEC: the bool |
| 60 | max_len_sub | parse | <string>:8:1: expected ')', found '{' [Expr] |
| 61 | count_Substrings | parse | <string>:41:20: expected ',', found 'end of input' [Expr] |
| 66 | pos_count | wf | implies over non-bool [SPEC: and/or/not/implies are bool-only]; implies over non-bool [SPEC: and/or/not/implies are bool |
| 67 | bell_number | wf | call of unknown fun bell_sum [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; ite branches differ |
| 71 | comb_sort | wf | bound var i shadows a name in scope [SPEC: a bound variable must not collide with a name already in scope (Gate 1 scope  |
| 76 | count_Squares | wf | operator 'div' not in v0 [SPEC: an operator must be in the declared version's operator set]; == wants two ints, two bool |
| 78 | count_With_Odd_SetBits | wf | call of unknown fun popcount_odd [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; ite condition i |
| 79 | word_len | wf | v0 has int only [SPEC: v0 has int only]; operator 'mod' not in v0 [SPEC: an operator must be in the declared version's o |
| 83 | get_Char | parse | <string>:3:3765: expected ')', found 'end of input' [Expr] |
| 84 | sequence | wf | task decreases without a self-call [SPEC: a task decreases requires a self-recursive body, and vice versa (Gate 3)] |
| 90 | len_log | wf | len of a non-seq [SPEC: len is defined on a seq (Gate 1)]; len of a non-seq [SPEC: len is defined on a seq (Gate 1)]; ta |
| 91 | find_substring | wf | find wants (seq, seq) [SPEC: each string-library member's argument types must match its signature (The string library)]; |
| 96 | divisor | parse | <string>:5:67: expected ')', found 'else' [Expr] |
| 99 | decimal_to_binary | parse | <string>:12:66: unexpected character '^' [Id] |
| 100 | next_smallest_palindrome | parse | <string>:12:23: 'seq' is not one of int bool [Type] |
| 101 | kth_element | wf | v0 has int only [SPEC: v0 has int only]; operator 'len' not in v0 [SPEC: an operator must be in the declared version's o |
| 113 | check_integer | parse | <string>:4:83: 'forall' does not start an expression [Expr] |
| 118 | string_to_list | wf | == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type [SPEC: == and != apply to two int |
| 119 | search | parse | <string>:25:5: expected 'else', found 'if' [Stmt] |
| 125 | find_length | wf | call of unknown fun max_diff_helper [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; ite branches |
| 126 | sum | wf | call of unknown fun sum_common_divs_upto [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; == want |
| 128 | long_words | wf | len of a non-seq [SPEC: len is defined on a seq (Gate 1)]; == wants two ints, two bools, two seqs, two nested seqs, or t |
| 131 | reverse_vowels | parse | <string>:7:3: expected ')', found 'ensures' [Expr] |
| 133 | sum_negativenum | parse | <string>:4:17: 'var' does not start an expression [Expr] |
| 134 | check_last | wf | v0 has int only [SPEC: v0 has int only]; operator 'len' not in v0 [SPEC: an operator must be in the declared version's o |
| 141 | pancake_sort | wf | bound var k shadows a name in scope [SPEC: a bound variable must not collide with a name already in scope (Gate 1 scope  |
| 142 | count_samepair | wf | implies over non-bool [SPEC: and/or/not/implies are bool-only]; implies over non-bool [SPEC: and/or/not/implies are bool |
| 144 | sum_Pairs | wf | call of unknown fun sum_prefix [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; - over non-int [S |
| 146 | ascii_value_string | wf | v0 has int only [SPEC: v0 has int only]; operator 'len' not in v0 [SPEC: an operator must be in the declared version's o |
| 148 | sum_digits_twoparts | no-block |  |
| 149 | longest_subseq_with_diff_one | parse | <string>:9:1: expected ')', found '{' [Expr] |
| 152 | merge_sort | parse | <string>:7:19: expected 'in', found ':' [Expr] |
| 155 | even_bit_toggle_number | parse | <string>:5:40: unexpected character '&' [Id] |
| 158 | min_Ops | parse | <string>:70:32: unexpected character '/' [Id] |
| 159 | month_season | wf | v0 has int only [SPEC: v0 has int only]; operator 'seq' not in v0 [SPEC: an operator must be in the declared version's o |
| 161 | remove_elements | parse | <string>:3:30: expected 'id', found 't' [Task] |
| 164 | areEquivalent | wf | call of unknown fun sum_divs_rest [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; + over non-int |
| 165 | count_char_position | parse | <string>:4:152: expected ')', found 'else' [Expr] |
| 166 | find_even_Pair | wf | == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type [SPEC: == and != apply to two int |
| 167 | next_Power_Of_2 | parse | <string>:34:66: expected ')', found 'end of input' [Expr] |
| 170 | sum_range_list | wf | task decreases without a self-call [SPEC: a task decreases requires a self-recursive body, and vice versa (Gate 3)] |
| 178 | string_literals | wf | find wants (seq, seq) [SPEC: each string-library member's argument types must match its signature (The string library)]; |
| 181 | common_prefix | wf | slice wants (seq or seq<seq>, int, int) [SPEC: slice wants (seq or seq<seq>, int, int) (Sequences: literals, concatenati |
| 183 | count_pairs | parse | <string>:23:7: expected 'else', found 'if' [Stmt] |
| 186 | check_literals | wf | find wants (seq, seq) [SPEC: each string-library member's argument types must match its signature (The string library)]; |
| 187 | longest_common_subsequence | parse | <string>:3:41: expected 'id', found 't' [Task] |
| 191 | check_monthnumber | wf | v0 has int only [SPEC: v0 has int only]; operator 'seq' not in v0 [SPEC: an operator must be in the declared version's o |
| 192 | check_String | parse | <string>:4:106: 'exists' does not start an expression [Expr] |
| 200 | position_max | wf | bound var i shadows a name in scope [SPEC: a bound variable must not collide with a name already in scope (Gate 1 scope  |
| 203 | hamming_Distance | wf | task decreases without a self-call [SPEC: a task decreases requires a self-recursive body, and vice versa (Gate 3)] |
| 209 | heap_replace | parse | <string>:76:18: 'end of input' does not start an expression [Expr] |
| 211 | count_Num | wf | and over non-bool [SPEC: and/or/not/implies are bool-only]; == wants two ints, two bools, two seqs, two nested seqs, or  |
| 220 | replace_max_specialchar | parse | <string>:9:3: expected ')', found 'ensures' [Expr] |
| 224 | count_Set_Bits | wf | task decreases without a self-call [SPEC: a task decreases requires a self-recursive body, and vice versa (Gate 3)] |
| 228 | all_Bits_Set_In_The_Given_Range | parse | <string>:5:28: '<' does not start an expression [Expr] |
| 229 | re_arrange_array | parse | <string>:48:26: expected ',', found 'end of input' [Expr] |
| 232 | larg_nnum | wf | assign to s, not a return or local [SPEC: assign targets a return or a local in scope (Gate 2)] |
| 236 | No_of_Triangle | wf | operator 'div' not in v0 [SPEC: an operator must be in the declared version's operator set]; v1 expression form in a v0  |
| 238 | number_of_substrings | wf | v0 has int only [SPEC: v0 has int only]; operator 'div' not in v0 [SPEC: an operator must be in the declared version's o |
| 240 | replace_list | parse | <string>:3:27: expected 'id', found 't' [Task] |
| 242 | count_charac | wf | v0 has int only [SPEC: v0 has int only]; operator 'len' not in v0 [SPEC: an operator must be in the declared version's o |
| 245 | max_sum | parse | <string>:27:14: expected ':=', found '[' [Stmt] |
| 247 | lps | wf | call of unknown fun max2 [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; ite branches differ: in |
| 249 | intersection_array | parse | <string>:6:42: expected '{', found 'in' [Stmt] |
| 254 | words_ae | wf | len of a non-seq [SPEC: len is defined on a seq (Gate 1)]; at wants (seq or seq<seq>, int) [SPEC: at wants (seq or seq<s |
| 256 | count_Primes_nums | parse | <string>:5:23: expected ']', found 'for' [Expr] |
| 258 | count_odd | wf | implies over non-bool [SPEC: and/or/not/implies are bool-only]; implies over non-bool [SPEC: and/or/not/implies are bool |
| 274 | even_binomial_Coeff_Sum | parse | <string>:5:24: '*' does not start an expression [Expr] |
| 275 | get_Position | wf | v0 has int only [SPEC: v0 has int only]; v1 expression form in a v0 task [SPEC: ite/forall/exists/call are v1 expression |
| 284 | check_element | wf | == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type [SPEC: == and != apply to two int |
| 286 | max_sub_array_sum_repeated | wf | call of unknown fun max_sub_array_sum_spec [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; ite b |
| 288 | modular_inverse | parse | <string>:5:59: expected 'in', found '.' [Expr] |
| 289 | odd_Days | parse | <string>:11:22: comparisons do not chain; parenthesise [What the notation refuses] |
| 295 | sum_div | wf | task decreases without a self-call [SPEC: a task decreases requires a self-recursive body, and vice versa (Gate 3)]; imp |
| 296 | get_Inv_Count | wf | + over non-int [SPEC: + - * neg div mod are int-only]; == wants two ints, two bools, two seqs, two nested seqs, or two p |
| 303 | solve | wf | implies over non-bool [SPEC: and/or/not/implies are bool-only]; == wants two ints, two bools, two seqs, two nested seqs, |
| 311 | set_left_most_unset_bit | parse | <string>:6:54: unexpected character '^' [Id] |
| 315 | find_Max_Len_Even | parse | <string>:4:3629: expected '.', found 'end of input' [Expr] |
| 319 | find_long_word | parse | <string>:8:1: expected ')', found '{' [Expr] |
| 320 | sum_difference | wf | operator 'div' not in v0 [SPEC: an operator must be in the declared version's operator set]; operator 'div' not in v0 [S |
| 321 | find_demlo | wf | == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type [SPEC: == and != apply to two int |
| 322 | position_min | wf | bound var i shadows a name in scope [SPEC: a bound variable must not collide with a name already in scope (Gate 1 scope  |
| 325 | get_Min_Squares | parse | <string>:279:129: unterminated block [Stmt] |
| 326 | most_occurrences | parse | <string>:53:100: 'end of input' does not start an expression [Expr] |
| 327 | check_isosceles | wf | bool literal in a v0 task [SPEC: the bool literal is a v1 construct (Gate 1)]; bool literal in a v0 task [SPEC: the bool |
| 329 | neg_count | wf | implies over non-bool [SPEC: and/or/not/implies are bool-only]; implies over non-bool [SPEC: and/or/not/implies are bool |
| 330 | find_char | parse | <string>:4:28: expected ']', found 'for' [Expr] |
| 331 | count_unset_bits | parse | <string>:16:27: unexpected character '^' [Id] |
| 334 | check_Validity | wf | bool literal in a v0 task [SPEC: the bool literal is a v1 construct (Gate 1)]; bool literal in a v0 task [SPEC: the bool |
| 335 | ap_sum | parse | <string>:11:22: comparisons do not chain; parenthesise [What the notation refuses] |
| 336 | check_monthnum | wf | v0 has int only [SPEC: v0 has int only]; operator 'seq' not in v0 [SPEC: an operator must be in the declared version's o |
| 338 | count_Substring_With_Equal_Ends | parse | <string>:5:1: expected ')', found '{' [Expr] |
| 339 | find_Divisor | no-block |  |
| 340 | sum_three_smallest_nums | wf | unbound var i [SPEC: a name must be bound before use (v0 and Gate 1 scope rule)]; != wants two ints, two bools, two seqs |
| 344 | count_Odd_Squares | parse | <string>:5:34: expected ')', found ']' [Expr] |
| 346 | zigzag | wf | v1 expression form in a v0 task [SPEC: ite/forall/exists/call are v1 expression forms (v1: the three gates)] |
| 347 | count_Squares | wf | operator 'div' not in v0 [SPEC: an operator must be in the declared version's operator set]; == wants two ints, two bool |
| 350 | minimum_Length | parse | <string>:5:3: expected ')', found 'ensures' [Expr] |
| 351 | first_Element | parse | <string>:7:3: expected ')', found 'ensures' [Expr] |
| 359 | Check_Solution | parse | <string>:4:22: comparisons do not chain; parenthesise [What the notation refuses] |
| 364 | min_flip_to_make_string_alternate | wf | call of unknown fun min_flips2 [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; ite branches diff |
| 366 | adjacent_num_product | wf | == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type [SPEC: == and != apply to two int |
| 374 | permute_string | wf | len of a non-seq [SPEC: len is defined on a seq (Gate 1)]; at wants (seq or seq<seq>, int) [SPEC: at wants (seq or seq<s |
| 375 | round_num | wf | call of unknown fun abs [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; <= is int-only (SPEC.md  |
| 378 | move_first | wf | v0 has int only [SPEC: v0 has int only]; operator 'len' not in v0 [SPEC: an operator must be in the declared version's o |
| 383 | even_bit_toggle_number | parse | <string>:4:18: expected '{', found 'xor_mask' [Stmt] |
| 384 | frequency_Of_Smallest | parse | <string>:8:1: expected ')', found '{' [Expr] |
| 386 | swap_count | parse | RecursionError: maximum recursion depth exceeded |
| 396 | check_char | wf | v0 has int only [SPEC: v0 has int only]; operator 'len' not in v0 [SPEC: an operator must be in the declared version's o |
| 402 | ncr_modp | parse | <string>:1:1: expected 't', found 'result' [Task] |
| 406 | find_Parity | wf | operator 'seq' not in v0 [SPEC: an operator must be in the declared version's operator set]; == wants two ints, two bool |
| 407 | rearrange_bigger | parse | <string>:8:3: expected ')', found 'ensures' [Expr] |
| 416 | breakSum | no-block |  |
| 430 | parabola_directrix | no-block |  |
| 435 | last_Digit | wf | operator 'mod' not in v0 [SPEC: an operator must be in the declared version's operator set]; - over non-int [SPEC: + - * |
| 439 | multiple_to_single | wf | call of unknown fun parse_concat_helper [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; ite bran |
| 449 | check_Triangle | wf | operator 'seq' not in v0 [SPEC: an operator must be in the declared version's operator set]; == wants two ints, two bool |
| 450 | extract_string | wf | len of a non-seq [SPEC: len is defined on a seq (Gate 1)]; len of a non-seq [SPEC: len is defined on a seq (Gate 1)]; le |
| 455 | check_monthnumb_number | wf | bool literal in a v0 task [SPEC: the bool literal is a v1 construct (Gate 1)]; bool literal in a v0 task [SPEC: the bool |
| 456 | reverse_string_list | wf | len of a non-seq [SPEC: len is defined on a seq (Gate 1)]; len of a non-seq [SPEC: len is defined on a seq (Gate 1)]; le |
| 461 | upper_ctr | wf | implies over non-bool [SPEC: and/or/not/implies are bool-only]; implies over non-bool [SPEC: and/or/not/implies are bool |
| 463 | max_subarray_product | wf | call of unknown fun max3 [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; ite branches differ: in |
| 467 | decimal_to_Octal | parse | <string>:7:1015: expected 'id', found 't' [Expr] |
| 468 | max_product | wf | task decreases without a self-call [SPEC: a task decreases requires a self-recursive body, and vice versa (Gate 3)] |
| 469 | max_profit | wf | call of unknown fun max_profit_all [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; call of unkno |
| 471 | find_remainder | wf | == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type [SPEC: == and != apply to two int |
| 476 | big_sum | wf | + over non-int [SPEC: + - * neg div mod are int-only]; + over non-int [SPEC: + - * neg div mod are int-only]; + over non |
| 479 | first_Digit | wf | operator 'div' not in v0 [SPEC: an operator must be in the declared version's operator set]; - over non-int [SPEC: + - * |
| 480 | get_max_occuring_char | wf | == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type [SPEC: == and != apply to two int |
| 483 | first_Factorial_Divisible_Number | parse | <string>:8:3: expected ')', found 'ensures' [Expr] |
| 485 | largest_palindrome | parse | <string>:11:26: 'seq' is not one of int bool [Type] |
| 489 | frequency_Of_Largest | wf | == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type [SPEC: == and != apply to two int |
| 491 | sum_gp | parse | <string>:8:32: unexpected character '^' [Id] |
| 495 | remove_lowercase | wf | == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type [SPEC: == and != apply to two int |
| 496 | heap_queue_smallest | parse | <string>:9:74: 'exists' does not start an expression [Expr] |
| 500 | concatenate_elements | parse | <string>:5:3: expected ')', found 'ensures' [Expr] |
| 505 | re_order | parse | <string>:6:3: expected ')', found 'ensures' [Expr] |
| 506 | permutation_coefficient | wf | task decreases without a self-call [SPEC: a task decreases requires a self-recursive body, and vice versa (Gate 3)] |
| 508 | same_order | parse | <string>:5:1: expected ')', found '{' [Expr] |
| 510 | no_of_subsequences | wf | call of unknown fun count_subseq_with_first [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; + ov |
| 516 | radix_sort | parse | <string>:49:12: expected ':=', found '[' [Stmt] |
| 522 | lbs | wf | call of unknown fun max2 [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; ite branches differ: in |
| 523 | check_string | wf | == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type [SPEC: == and != apply to two int |
| 524 | max_sum_increasing_subsequence | wf | call of unknown fun best_before [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; + over non-int [ |
| 527 | get_pairs_count | parse | <string>:5:3: expected ')', found 'ensures' [Expr] |
| 532 | check_permutation | parse | <string>:4:99: comparisons do not chain; parenthesise [What the notation refuses] |
| 537 | first_repeated_word | parse | <string>:5:1: expected ')', found '{' [Expr] |
| 540 | find_Diff | wf | call of unknown fun max_freq_helper [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; == wants two |
| 541 | check_abundant | parse | <string>:19:29: expected ')', found 'of' [Expr] |
| 545 | toggle_F_and_L_bits | parse | <string>:5:56: '*' does not start an expression [Expr] |
| 547 | Total_Hamming_Distance | wf | call of unknown fun hamming_dist [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; + over non-int  |
| 548 | longest_increasing_subsequence | parse | <string>:7:3: expected ')', found 'ensures' [Expr] |
| 549 | odd_Num_Sum | parse | <string>:5:2965: expected 'then', found 'end of input' [Expr] |
| 552 | Seq_Linear | parse | <string>:5:51: comparisons do not chain; parenthesise [What the notation refuses] |
| 558 | digit_distance_nums | parse | <string>:1:1: expected 't', found 'spec' [Task] |
| 559 | max_sub_array_sum | wf | task decreases without a self-call [SPEC: a task decreases requires a self-recursive body, and vice versa (Gate 3)]; cal |
| 563 | extract_values | wf | == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type [SPEC: == and != apply to two int |
| 564 | count_Pairs | wf | * over non-int [SPEC: + - * neg div mod are int-only]; * over non-int [SPEC: + - * neg div mod are int-only]; * over non |
| 566 | sum_digits | parse | <string>:22:9: expected 'id', found 't' [Stmt] |
| 570 | remove_words | wf | replace wants (seq, seq, seq) [SPEC: each string-library member's argument types must match its signature (The string li |
| 572 | two_unique_nums | parse | <string>:26:65: expected ')', found 'else' [Expr] |
| 573 | unique_product | wf | task decreases without a self-call [SPEC: a task decreases requires a self-recursive body, and vice versa (Gate 3)] |
| 575 | count_no | no-block |  |
| 583 | catalan_number | wf | unbound var k [SPEC: a name must be bound before use (v0 and Gate 1 scope rule)]; argument type mismatch calling catalan |
| 588 | big_diff | wf | == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type [SPEC: == and != apply to two int |
| 589 | perfect_squares | parse | <string>:6:65: 'exists' does not start an expression [Expr] |
| 592 | sum_Of_product | wf | task decreases without a self-call [SPEC: a task decreases requires a self-recursive body, and vice versa (Gate 3)] |
| 594 | diff_even_odd | parse | <string>:6:216: expected ')', found 'then' [Expr] |
| 595 | min_Swaps | parse | <string>:16:22: comparisons do not chain; parenthesise [What the notation refuses] |
| 600 | is_Even | parse | <string>:376:60: unterminated block [Stmt] |
| 603 | get_ludic | parse | <string>:9:29: 'seq' is not one of int bool [Type] |
| 604 | reverse_words | wf | local words init type mismatch [SPEC: assign's expression type must match the target's declared type]; join wants (seq<s |
| 608 | bell_Number | wf | call of unknown fun bell_row [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; ite branches differ |
| 619 | move_num | parse | <string>:6:3: expected ')', found 'ensures' [Expr] |
| 621 | increment_numerics | wf | isdigit wants a seq [SPEC: each string-library member's argument types must match its signature (The string library)]; a |
| 627 | find_First_Missing | parse | <string>:8:29: expected '{', found 'in' [Stmt] |
| 632 | move_zero | parse | <string>:6:3: expected ')', found 'ensures' [Expr] |
| 633 | pair_OR_Sum | parse | <string>:5:79: 'var' does not start an expression [Expr] |
| 636 | Check_Solution | wf | operator 'seq' not in v0 [SPEC: an operator must be in the declared version's operator set]; == wants two ints, two bool |
| 637 | noprofit_noloss | wf | bool literal in a v0 task [SPEC: the bool literal is a v1 construct (Gate 1)]; bool literal in a v0 task [SPEC: the bool |
| 638 | wind_chill | no-block |  |
| 639 | sample_nam | wf | at wants (seq or seq<seq>, int) [SPEC: at wants (seq or seq<seq>, int) (Gate 1; Nested sequences)]; >= is int-only (SPEC |
| 643 | text_match_wordz_middle | parse | <string>:7:1: expected ')', found '{' [Expr] |
| 646 | No_of_cubes | wf | local in a v0 task [SPEC: locals are a v1 construct (Gate 2)] |
| 647 | split_upperstring | wf | len of a non-seq [SPEC: len is defined on a seq (Gate 1)]; at wants (seq or seq<seq>, int) [SPEC: at wants (seq or seq<s |
| 648 | exchange_elements | parse | <string>:5:60: 'if' does not start an expression [Expr] |
| 650 | are_Equal | wf | v0 has int only [SPEC: v0 has int only]; operator 'len' not in v0 [SPEC: an operator must be in the declared version's o |
| 656 | find_Min_Sum | wf | call of unknown fun abs_diff [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; + over non-int [SPE |
| 657 | first_Digit | parse | <string>:24:7: expected 'id', found 't' [Stmt] |
| 658 | max_occurrences | parse | <string>:7:1: expected ')', found '{' [Expr] |
| 659 | Repeat | parse | <string>:9:1: expected ')', found '{' [Expr] |
| 661 | max_sum_of_three_consecutive | parse | <string>:9:4408: expected 'else', found 'end of input' [Expr] |
| 663 | find_max_val | wf | operator 'mod' not in v0 [SPEC: an operator must be in the declared version's operator set]; - over non-int [SPEC: + - * |
| 665 | move_last | wf | v0 has int only [SPEC: v0 has int only]; operator 'len' not in v0 [SPEC: an operator must be in the declared version's o |
| 667 | Check_Vow | parse | <string>:7:3: expected ')', found 'ensures' [Expr] |
| 669 | check_IP | parse | <string>:8:11: expected ')', found 'part' [Expr] |
| 671 | set_Right_most_Unset_Bit | parse | <string>:6:83: unexpected character '^' [Id] |
| 674 | remove_duplicate | parse | <string>:7:42: expected '{', found 'in' [Stmt] |
| 675 | sum_nums | parse | <string>:3:16: 'if' does not start an expression [Expr] |
| 685 | sum_Of_Primes | wf | call of unknown fun is_prime_helper [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; ite branches |
| 689 | min_jumps | parse | <string>:10:1: expected ')', found '{' [Expr] |
| 693 | remove_multiple_spaces | parse | <string>:9:52: 'exists' does not start an expression [Expr] |
| 697 | count_even | parse | <string>:4:23: expected ']', found 'for' [Expr] |
| 699 | min_Swaps | parse | <string>:15:22: comparisons do not chain; parenthesise [What the notation refuses] |
| 700 | count_range_in_list | wf | implies over non-bool [SPEC: and/or/not/implies are bool-only]; implies over non-bool [SPEC: and/or/not/implies are bool |
| 707 | count_Set_Bits | wf | call of unknown fun popcount [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; + over non-int [SPE |
| 708 | Convert | wf | == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type [SPEC: == and != apply to two int |
| 714 | count_Fac | parse | <string>:25:3: expected 'else', found 'r' [Stmt] |
| 719 | text_match | parse | <string>:7:1: expected ')', found '{' [Expr] |
| 723 | count_same_pair | parse | <string>:12:3: expected 'else', found 'while' [Stmt] |
| 724 | power_base_sum | parse | <string>:6:31: unexpected character '^' [Id] |
| 725 | extract_quotation | wf | == wants two ints, two bools, two seqs, two nested seqs, or two pairs of the same type [SPEC: == and != apply to two int |
| 730 | consecutive_duplicates | wf | < is int-only (SPEC.md gate 1) [SPEC: < <= > >= are int-only (Gate 1)] |
| 734 | sum_Of_Subarray_Prod | wf | call of unknown fun sum_of_products_ending_at [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; +  |
| 735 | toggle_middle_bits | parse | <string>:12:1: expected '{', found 'end of input' [Stmt] |
| 737 | check_str | wf | v0 has int only [SPEC: v0 has int only]; operator 'len' not in v0 [SPEC: an operator must be in the declared version's o |
| 739 | find_Index | parse | <string>:6:19: unexpected character '^' [Id] |
| 745 | divisible_by_digits | parse | <string>:6:28: expected ']', found 'for' [Expr] |
| 747 | lcs_of_three | wf | call of unknown fun max3 [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; ite branches differ: in |
| 757 | count_reverse_pairs | wf | local wi init type mismatch [SPEC: assign's expression type must match the target's declared type]; local wj init type m |
| 762 | check_monthnumber_number | wf | bool literal in a v0 task [SPEC: the bool literal is a v1 construct (Gate 1)]; bool literal in a v0 task [SPEC: the bool |
| 765 | is_polite | parse | <string>:7:3: expected ')', found 'ensures' [Expr] |
| 767 | get_Pairs_Count | parse | <string>:5:3: expected ')', found 'ensures' [Expr] |
| 768 | check_Odd_Parity | wf | operator 'mod' not in v0 [SPEC: an operator must be in the declared version's operator set]; == wants two ints, two bool |
| 769 | Diff | parse | <string>:4:59: a dot must be followed by .0, .1, or a string-library member [Op] |
| 770 | odd_Num_Sum | parse | <string>:5:2545: expected 'then', found 'end of input' [Expr] |
| 772 | remove_length | parse | <string>:41:48: expected '{', found 'end of input' [Stmt] |
| 774 | check_email | parse | <string>:6:3: expected ')', found 'ensures' [Expr] |
| 775 | odd_position | parse | <string>:5:1: expected ')', found '{' [Expr] |
| 776 | count_vowels | parse | <string>:4:123: expected ')', found 'else' [Expr] |
| 777 | find_Sum | parse | <string>:6:17: 'var' does not start an expression [Expr] |
| 782 | Odd_Length_Sum | parse | <string>:55:8: expected 'then', found 'end of input' [Expr] |
| 784 | mul_even_odd | parse | <string>:6:215: expected ')', found 'then' [Expr] |
| 790 | even_position | parse | <string>:5:1: expected ')', found '{' [Expr] |
| 798 | _sum | parse | <string>:3:6: unexpected character '_' [Id] |
| 799 | left_Rotate | parse | <string>:4:23: unexpected character '^' [Id] |
| 801 | test_three_equal | wf | v1 expression form in a v0 task [SPEC: ite/forall/exists/call are v1 expression forms (v1: the three gates)]; v1 express |
| 802 | count_Rotation | parse | <string>:45:34: expected ')', found 'end of input' [Expr] |
| 806 | max_run_uppercase | parse | <string>:8:3: expected ')', found 'ensures' [Expr] |
| 810 | count_variable | wf | bound var i shadows a name in scope [SPEC: a bound variable must not collide with a name already in scope (Gate 1 scope  |
| 813 | string_length | wf | v0 has int only [SPEC: v0 has int only]; operator 'len' not in v0 [SPEC: an operator must be in the declared version's o |
| 814 | rombus_area | wf | operator 'div' not in v0 [SPEC: an operator must be in the declared version's operator set]; == wants two ints, two bool |
| 815 | sort_by_dnf | parse | <string>:26:34: expected ')', found 'end of input' [Expr] |
| 817 | div_of_nums | parse | <string>:10:28: expected ']', found 'for' [Expr] |
| 818 | lower_ctr | wf | implies over non-bool [SPEC: and/or/not/implies are bool-only]; implies over non-bool [SPEC: and/or/not/implies are bool |
| 820 | check_monthnum_number | wf | bool literal in a v0 task [SPEC: the bool literal is a v1 construct (Gate 1)]; bool literal in a v0 task [SPEC: the bool |
| 822 | pass_validity | parse | <string>:4:34: 'exists' does not start an expression [Expr] |
| 826 | check_Type_Of_Triangle | wf | operator 'seq' not in v0 [SPEC: an operator must be in the declared version's operator set]; == wants two ints, two bool |
| 829 | second_frequent | parse | <string>:19:22: comparisons do not chain; parenthesise [What the notation refuses] |
| 831 | count_Pairs | wf | call of unknown fun count_eq [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; + over non-int [SPE |
| 832 | extract_max | parse | <string>:19:22: comparisons do not chain; parenthesise [What the notation refuses] |
| 836 | max_sub_array_sum | parse | <string>:10:1: expected ')', found '{' [Expr] |
| 837 | cube_Sum | parse | <string>:11:22: comparisons do not chain; parenthesise [What the notation refuses] |
| 840 | Check_Solution | wf | operator 'seq' not in v0 [SPEC: an operator must be in the declared version's operator set]; == wants two ints, two bool |
| 841 | get_inv_count | parse | <string>:34:53: expected ',', found 'end of input' [Expr] |
| 842 | get_odd_occurence | parse | <string>:5:19: expected 'in', found ':' [Expr] |
| 843 | nth_super_ugly_number | parse | <string>:41:24: expected 'id', found 't' [Expr] |
| 845 | find_Digits | wf | task decreases without a self-call [SPEC: a task decreases requires a self-recursive body, and vice versa (Gate 3)] |
| 846 | find_platform | parse | <string>:19:22: comparisons do not chain; parenthesise [What the notation refuses] |
| 847 | lcopy | wf | v0 has int only [SPEC: v0 has int only] |
| 848 | area_trapezium | wf | operator 'div' not in v0 [SPEC: an operator must be in the declared version's operator set]; assign r: None into int [SP |
| 849 | Sum | wf | call of unknown fun is_prime [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; ite condition is no |
| 850 | is_triangleexists | wf | bool literal in a v0 task [SPEC: the bool literal is a v1 construct (Gate 1)]; bool literal in a v0 task [SPEC: the bool |
| 854 | raw_heap | parse | <string>:6:3: expected ')', found 'ensures' [Expr] |
| 855 | check_Even_Parity | wf | bool literal in a v0 task [SPEC: the bool literal is a v1 construct (Gate 1)]; bool literal in a v0 task [SPEC: the bool |
| 861 | anagram_lambda | wf | len of a non-seq [SPEC: len is defined on a seq (Gate 1)]; at wants (seq or seq<seq>, int) [SPEC: at wants (seq or seq<s |
| 863 | find_longest_conseq_subseq | wf | task decreases without a self-call [SPEC: a task decreases requires a self-recursive body, and vice versa (Gate 3)] |
| 864 | palindrome_lambda | wf | argument type mismatch calling is_pal [SPEC: a call's argument types must match the callee's params (Gate 3)]; argument  |
| 866 | check_monthnumb | wf | v0 has int only [SPEC: v0 has int only]; operator 'seq' not in v0 [SPEC: an operator must be in the declared version's o |
| 867 | min_Num | wf | v0 has int only [SPEC: v0 has int only]; v1 expression form in a v0 task [SPEC: ite/forall/exists/call are v1 expression |
| 868 | length_Of_Last_Word | wf | local words init type mismatch [SPEC: assign's expression type must match the target's declared type]; len of a non-seq  |
| 870 | sum_positivenum | parse | <string>:4:17: 'var' does not start an expression [Expr] |
| 871 | are_Rotations | parse | <string>:3:28: expected 'id', found 't' [Task] |
| 874 | check_Concat | parse | <string>:3:27: expected 'id', found 't' [Task] |
| 879 | text_match | parse | <string>:5:79: 'exists' does not start an expression [Expr] |
| 880 | Check_Solution | wf | operator 'seq' not in v0 [SPEC: an operator must be in the declared version's operator set]; == wants two ints, two bool |
| 883 | div_of_nums | parse | <string>:7:42: expected '{', found 'in' [Stmt] |
| 884 | all_Bits_Set_In_The_Given_Range | no-block |  |
| 885 | is_Isomorphic | parse | <string>:3:28: expected 'id', found 't' [Task] |
| 887 | is_odd | wf | operator 'mod' not in v0 [SPEC: an operator must be in the declared version's operator set]; != wants two ints, two bool |
| 892 | remove_spaces | parse | <string>:16:22: comparisons do not chain; parenthesise [What the notation refuses] |
| 897 | is_Word_Present | parse | <string>:4:22: expected ')', found 'in' [Expr] |
| 901 | smallest_multiple | wf | call of unknown fun gcd [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; div over non-int [SPEC:  |
| 903 | count_Unset_Bits | wf | call of unknown fun unset_bits [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; + over non-int [S |
| 909 | previous_palindrome | wf | at wants (seq or seq<seq>, int) [SPEC: at wants (seq or seq<seq>, int) (Gate 1; Nested sequences)]; at wants (seq or seq |
| 911 | maximum_product | parse | <string>:253:9: expected 'id', found 'if' [Stmt] |
| 913 | end_num | wf | v0 has int only [SPEC: v0 has int only]; operator 'len' not in v0 [SPEC: an operator must be in the declared version's o |
| 914 | is_Two_Alter | parse | <string>:4:50: 'forall' does not start an expression [Expr] |
| 915 | rearrange_numbs | wf | unbound var i [SPEC: a name must be bound before use (v0 and Gate 1 scope rule)]; quantifier hi is not int [SPEC: a quan |
| 930 | text_match | parse | <string>:7:1: expected ')', found '{' [Expr] |
| 940 | heap_sort | wf | bound var i shadows a name in scope [SPEC: a bound variable must not collide with a name already in scope (Gate 1 scope  |
| 943 | combine_lists | parse | <string>:24:87: 'end of input' does not start an expression [Expr] |
| 947 | len_log | wf | len of a non-seq [SPEC: len is defined on a seq (Gate 1)]; == wants two ints, two bools, two seqs, two nested seqs, or t |
| 950 | chinese_zodiac | parse | <string>:3:16: 'if' does not start an expression [Expr] |
| 952 | nCr_mod_p | parse | <string>:5:19: comparisons do not chain; parenthesise [What the notation refuses] |
| 953 | subset | wf | call of unknown fun count_in [SPEC: call names a declared spec_fun or the task's own name (Gate 3)]; > is int-only (SPEC |
| 956 | split_list | parse | <string>:34:60: expected ')', found 'end of input' [Expr] |
| 957 | get_First_Set_Bit_Pos | parse | <string>:6:15: '<' does not start an expression [Expr] |
| 958 | int_to_roman | parse | <string>:7:20: a dot must be followed by .0, .1, or a string-library member [Op] |
| 964 | word_len | wf | v0 has int only [SPEC: v0 has int only]; operator 'mod' not in v0 [SPEC: an operator must be in the declared version's o |
| 965 | camel_to_snake | parse | <string>:4:2965: expected ')', found 'end of input' [Expr] |
| 968 | floor_Max | no-block |  |

