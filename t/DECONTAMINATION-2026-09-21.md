# Held-out problems with a same-task source in training, 2026-09-21

The list `t/RUN-NEXT-locallm-r12.md` (blocker A2) decontaminates against. 32 of
the 232 held-out problems (`t/out/loop/split-v3.json` eval ids) have a training
document or train-split problem that asks for the same function. Every hit of
four detectors was read by hand; 66 template siblings (largest/smallest,
odd/even) were flagged by the thresholds and kept apart, because they are
different functions.

The detectors, each on prior art fetched that day:
- reference solutions equal with every local name erased (Riddell et al.,
  https://arxiv.org/html/2403.04811);
- token and statement edit similarity above 0.8
  (https://ar5iv.labs.arxiv.org/html/2107.06499);
- execution: every corpus document run on the held-out problem's own
  assertions (https://arxiv.org/html/2508.01357v1);
- answer overlap: `loop_filter.key`, as in `t/score_heldout.py --corpus`
  (Lewis et al., arXiv:2008.02637).

The execution check has 3 assertions per problem to work with, so some
contamination may remain undetected. 18 held-out problems have tests weak
enough that unrelated documents pass them (listed at the end).

## The 32, by reason

- **problem-level same task (names-erased reference equal)**: 366, 527, 699, 719, 775, 800, 842, 161
- **problem-level same task (near-identical text/reference, read)**: 10, 208, 347, 402, 411, 604, 813, 928, 970
- **same function, found by running train/corpus docs on the eval problem's own assertions (read)**: 138, 358, 443, 492, 502, 518, 566, 682, 687, 729, 887, 931
- **eval problem itself lifted into the corpus (MBPP-DFY)**: 269, 626
- **degenerate in t (identity), recited by locallm-r5**: 565

Two of these are not near-duplicates but the held-out problem itself:
`dafny_synthesis_task_id_269__asciiValue` and
`dafny_synthesis_task_id_626__areaOfLargestTriangleInSemicircle` are MBPP-DFY
lifts of MBPP 269 and 626 and have been in every locallm corpus since r7,
because the held-out filter matched only `mbpp_N` names. Neither produced a
clean answer.

## What it changes

Of locallm's 23 clean answers across rounds 4 to 10, 22 are on these 32; the
23rd (r9 seed 42, `check_abundant`) disagrees with its problem under
`t/spec_check.py`. On the other 200, locallm has passed a problem's tests once
in ten arms. Phi-4-mini passes 5 there, the untrained 1.5B 10, the 235B 44.

## Documents to drop from any corpus (37), with the held-out ids each duplicates

| document | held-out ids |
|---|---|
| `committed:contains` | 492 |
| `committed:digit_sum` | 566 |
| `committed:gcd` | 687 |
| `committed:remainder` | 502 |
| `lifted:clover_array_product__arrayProduct` | 682 |
| `lifted:clover_array_sum__arraySum` | 729 |
| `lifted:clover_is_even__computeIsEven` | 138 |
| `lifted:clover_min_array__minArray` | 443 |
| `lifted:clover_min_of_two__min` | 970 |
| `lifted:dafny_exercises_tmp_tmpjm75muf__session2exercises_exercisesquare_root__mroot1` | 518 |
| `lifted:dafny_synthesis_task_id_242__countCharacters` | 813 |
| `lifted:dafny_synthesis_task_id_269__asciiValue` | 269 |
| `lifted:dafny_synthesis_task_id_404__min` | 970 |
| `lifted:dafny_synthesis_task_id_406__isOdd` | 887 |
| `lifted:dafny_synthesis_task_id_445__multiplyElements` | 682 |
| `lifted:dafny_synthesis_task_id_600__isEven` | 138 |
| `lifted:dafny_synthesis_task_id_616__elementWiseModulo` | 358 |
| `lifted:dafny_synthesis_task_id_626__areaOfLargestTriangleInSemicircle` | 626 |
| `lifted:dafny_synthesis_task_id_62__findSmallest` | 443 |
| `lifted:dafny_synthesis_task_id_728__addLists` | 729 |
| `lifted:dafny_tmp_tmpv_d3qi10_2_min__minArray` | 443 |
| `lifted:dafny_tmp_tmpv_d3qi10_2_min__minMethod` | 970 |
| `lifted:dafny_verify_tmp_tmphq7j0row_generated_code_minimum__minimum` | 443 |
| `lifted:dafny_verify_tmp_tmphq7j0row_test_cases_index__min` | 970 |
| `lifted:dafnyexercises_tmp_tmpd6qyevja_part1_q1__addArrays` | 729 |
| `lifted:programmverifikation_und_synthese_tmp_tmppurk6ime_pvs_assignment_ex_05_hoangkim_ex_05_hoangkim__gcdI` | 687 |
| `lifted:programmverifikation_und_synthese_tmp_tmppurk6ime_pvs_assignment_ex_06_hoangkim_ex06_solution__gcdI` | 687 |
| `lifted:programmverifikation_und_synthese_tmp_tmppurk6ime_pvs_assignment_ex_06_hoangkim_ex_06_hoangkim__gcdI` | 687 |
| `lifted:stunning_palm_tree_tmp_tmpr84c2iwh_ch1__min` | 970 |
| `positive:apps_124__search` | 492 |
| `positive:apps_2465__divisorGame` | 138 |
| `positive:mbpp_242__count_charac` | 813 |
| `positive:mbpp_404__minimum` | 970 |
| `positive:mbpp_451__remove_whitespaces` | 800 |
| `positive:mbpp_498__gcd` | 687 |
| `positive:mbpp_504__sum_Of_Series` | 931 |
| `positive:mbpp_728__sum_list` | 729 |

## Train ids to exclude from every future build (21)

These train-split problems are the same task as a held-out problem; two of them
(427 and 790) already have passing teacher answers waiting to be graded, which
the positive gate would otherwise admit.

496, 759, 76, 952, 102, 767, 595, 930, 790, 29, 427, 204462, 203929, 242, 404, 451, 498, 504, 728, 200124, 202465

## Held-out problems whose tests are weak (18)

Unrelated documents pass these problems' own assertions, so a clean answer on
one of them is weaker evidence than elsewhere:

20, 45, 68, 72, 179, 201, 269, 355, 362, 541, 565, 605, 683, 711, 741, 768, 804, 866

Kept deliberately: five documents that pass a held-out problem's tests but are
a different task (`committed:is_prime`, `positive:mbpp_173__remove_splchar`, `positive:mbpp_455__check_monthnumb_number`, `positive:mbpp_676__remove_extra_char`, `positive:mbpp_732__replace_specialchar`).
