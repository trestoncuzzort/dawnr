# Specifications against the problems' own solutions, 2026-09-18

`python3 t/spec_check.py --pool v5 --n 1000 --only all`, seed 1. Each task's
`ensures` is evaluated with the problem's reference solution supplying the result, on random
arguments of the shapes the problem's own assertions use. A disagreement is a specification the
seven proof systems proved and the twin rule accepted that does not say what the problem asked.

- checked: 99
- agree on every draw: 34
- disagree: 64
- could not be checked: 1

- `gcp-student-20261011-greedy/mbpp_122__smartNumber`: ensures[0] false at `[438]`, the problem's solution answers `1353`
- `gcp-student-20261011-greedy/mbpp_149__longest_subseq_with_diff_one`: ensures[0] false at `[[8, 0, 0, 5, 3, 7], 4]`, the problem's solution answers `1`
- `gcp-student-20261011-greedy/mbpp_175__is_valid_parenthese`: ensures[0] false at `[[88]]`, the problem's solution answers `False`
- `gcp-student-20261011-greedy/mbpp_184__greater_specificnum`: ensures[0] false at `[[], 6]`, the problem's solution answers `True`
- `gcp-student-20261011-greedy/mbpp_194__octal_To_Decimal`: ensures[0] false at `[17]`, the problem's solution answers `15`
- `gcp-student-20261011-greedy/mbpp_203__hamming_Distance`: ensures[0] false at `[1, 4]`, the problem's solution answers `2`
- `gcp-student-20261011-greedy/mbpp_20__is_woodall`: ensures[0] false at `[1]`, the problem's solution answers `True`
- `gcp-student-20261011-greedy/mbpp_228__all_Bits_Set_In_The_Given_Range`: ensures[0] false at `[19, 4, 4]`, the problem's solution answers `True`
- `gcp-student-20261011-greedy/mbpp_271__even_Power_Sum`: ensures[0] false at `[1]`, the problem's solution answers `32`
- `gcp-student-20261011-greedy/mbpp_275__get_Position`: ensures[1] false at `[[1, 1, 2, 3, 3], 0, 1]`, the problem's solution answers `0`
- `gcp-student-20261011-greedy/mbpp_289__odd_Days`: ensures[0] false at `[147]`, the problem's solution answers `0`
- `gcp-student-20261011-greedy/mbpp_313__pos_nos`: ensures[0] false at `[[-5, -3, 2, 3, -1]]`, the problem's solution answers `2`
- `gcp-student-20261011-greedy/mbpp_318__max_volume`: ensures[1] false at `[15]`, the problem's solution answers `125`
- `gcp-student-20261011-greedy/mbpp_322__position_min`: ensures[2] false at `[[-1, 0, 0, 1, 1, 1, 1, 2, 3, 4, 4, 7]]`, the problem's solution answers `[0]`
- `gcp-student-20261011-greedy/mbpp_32__max_Prime_Factors`: ensures[3] false at `[21]`, the problem's solution answers `7`
- `gcp-student-20261011-greedy/mbpp_344__count_Odd_Squares`: ensures[0] false at `[1, 8]`, the problem's solution answers `2`
- `gcp-student-20261011-greedy/mbpp_347__count_Squares`: ensures[0] false at `[2, 4]`, the problem's solution answers `10`
- `gcp-student-20261011-greedy/mbpp_351__first_Element`: ensures[0] false at `[[5, 0, 1, 0, -1, 6, 4], 3, 3]`, the problem's solution answers `-1`
- `gcp-student-20261011-greedy/mbpp_375__round_num`: ensures[1] false at `[4303, 13]`, the problem's solution answers `4303`
- `gcp-student-20261011-greedy/mbpp_38__div_even_odd`: ensures[0] false at `[[0, 1, 3, 4, 8, 12]]`, the problem's solution answers `0.0`
- `gcp-student-20261011-greedy/mbpp_411__snake_to_camel`: ensures[1] false at `[[112, 116, 104, 118, 122, 117, 103, 95]]`, the problem's solution answers `'Pthvzug_'`
- `gcp-student-20261011-greedy/mbpp_420__cube_Sum`: ensures[0] false at `[1]`, the problem's solution answers `8`
- `gcp-student-20261011-greedy/mbpp_443__largest_neg`: ensures[0] false at `[[-7, 1, -2, -3, -4, -6, -6]]`, the problem's solution answers `-7`
- `gcp-student-20261011-greedy/mbpp_472__check_Consecutive`: ensures[1] false at `[[1, 7]]`, the problem's solution answers `False`
- `gcp-student-20261011-greedy/mbpp_479__first_Digit`: ensures[0] false at `[736]`, the problem's solution answers `7`
- `gcp-student-20261011-greedy/mbpp_483__first_Factorial_Divisible_Number`: ensures[1] false at `[30]`, the problem's solution answers `5`
- `gcp-student-20261011-greedy/mbpp_502__find`: ensures[0] false at `[18, 6]`, the problem's solution answers `0`
- `gcp-student-20261011-greedy/mbpp_515__modular_sum`: ensures[0] false at `[[8, 5, 2, -1, 4, 5], 8, 11]`, the problem's solution answers `True`
- `gcp-student-20261011-greedy/mbpp_521__check_isosceles`: ensures[0] false at `[10, 15, 6]`, the problem's solution answers `True`
- `gcp-student-20261011-greedy/mbpp_527__get_pairs_count`: ensures[0] false at `[[3, 7, -3, 0], 4, 1]`, the problem's solution answers `0`
- `gcp-student-20261011-greedy/mbpp_536__nth_items`: ensures[0] false at `[[0, 1, 2, 4, 4, 7, 9, 11], 4]`, the problem's solution answers `[0, 4]`
- `gcp-student-20261011-greedy/mbpp_550__find_Max`: ensures[0] false at `[[6, 5, 0, 3, 2, 0, -1], 0, 4]`, the problem's solution answers `5`
- `gcp-student-20261011-greedy/mbpp_556__find_Odd_Pair`: ensures[0] false at `[[2, 2, 2, 2, 4, -1, 7], 7]`, the problem's solution answers `10`
- `gcp-student-20261011-greedy/mbpp_575__count_no`: ensures[0] false at `[5, 11, 4, 28]`, the problem's solution answers `17`
- `gcp-student-20261011-greedy/mbpp_593__removezero_ip`: ensures[1] false at `[[58, 59, 59, 48, 49, 51, 55, 50, 44]]`, the problem's solution answers `':;;01372,'`
- `gcp-student-20261011-greedy/mbpp_597__find_kth`: ensures[0] false at `[[0, 1, 2, 4, 4, 8], [-1, 0, 6, 10], 4, 4, 0]`, the problem's solution answers `10`
- `gcp-student-20261011-greedy/mbpp_604__reverse_words`: ensures[1] false at `[[105, 30, 111, 40, 45, 30, 108, 38, 61, 54]]`, the problem's solution answers `'l&=6 o(- i'`
- `gcp-student-20261011-greedy/mbpp_609__floor_Min`: ensures[0] false at `[9, 10, 15]`, the problem's solution answers `13`
- `gcp-student-20261011-greedy/mbpp_626__triangle_area`: ensures[2] false at `[1]`, the problem's solution answers `1`
- `gcp-student-20261011-greedy/mbpp_629__Split`: ensures[2] false at `[[8, 9, 12, 16, 19, 20]]`, the problem's solution answers `[8, 12, 16, 20]`
- `gcp-student-20261011-greedy/mbpp_633__pair_OR_Sum`: ensures[0] false at `[[6, 3, 8, 9], 3]`, the problem's solution answers `30`
- `gcp-student-20261011-greedy/mbpp_644__reverse_Array_Upto_K`: ensures[0] false at `[[8, 3, 9, 9], 0]`, the problem's solution answers `[9, 9, 3, 8, 8, 3, 9, 9]`
- `gcp-student-20261011-greedy/mbpp_665__move_last`: ensures[1] false at `[[1, 1, 2, 3, 5, 5]]`, the problem's solution answers `[2, 3, 5, 5, 1, 1]`
- `gcp-student-20261011-greedy/mbpp_670__decreasing_trend`: ensures[0] false at `[[3, 0]]`, the problem's solution answers `False`
- `gcp-student-20261011-greedy/mbpp_675__sum_nums`: ensures[1] false at `[6, 27, 6, 19]`, the problem's solution answers `33`
- `gcp-student-20261011-greedy/mbpp_680__increasing_trend`: ensures[0] false at `[[3, 3, 7, 11]]`, the problem's solution answers `True`
- `gcp-student-20261011-greedy/mbpp_723__count_same_pair`: ensures[0] false at `[[16, 13, 13, -10, 1], [0, 4, 2, 9, 4, 5, 2, -4, 1]]`, the problem's solution answers `0`
- `gcp-student-20261011-greedy/mbpp_72__dif_Square`: ensures[0] false at `[7]`, the problem's solution answers `True`
- `gcp-student-20261011-greedy/mbpp_748__capital_words_spaces`: ensures[0] false at `[[102, 78, 92, 100, 89, 90, 122]]`, the problem's solution answers `'f N\\d YZz'`
- `gcp-student-20261011-greedy/mbpp_765__is_polite`: ensures[0] false at `[8]`, the problem's solution answers `12`
- `gcp-student-20261011-greedy/mbpp_768__check_Odd_Parity`: ensures[0] false at `[8]`, the problem's solution answers `True`
- `gcp-student-20261011-greedy/mbpp_793__last`: ensures[1] false at `[[6, 0, 8, 6, 3, 1, 5, 1, 10], 5, 7]`, the problem's solution answers `-1`
- `gcp-student-20261011-greedy/mbpp_800__remove_all_spaces`: ensures[1] false at `[[34, 54, 37, 111, 41, 65, 49, 60]]`, the problem's solution answers `'"6%o)A1<'`
- `gcp-student-20261011-greedy/mbpp_814__rombus_area`: ensures[0] false at `[4, 4]`, the problem's solution answers `8.0`
- `gcp-student-20261011-greedy/mbpp_831__count_Pairs`: ensures[0] false at `[[7, -1, 8, 1], 3]`, the problem's solution answers `0`
- `gcp-student-20261011-greedy/mbpp_837__cube_Sum`: ensures[0] false at `[2]`, the problem's solution answers `28`
- `gcp-student-20261011-greedy/mbpp_844__get_Number`: ensures[0] false at `[11, 4]`, the problem's solution answers `7`
- `gcp-student-20261011-greedy/mbpp_882__parallelogram_perimeter`: ensures[0] false at `[14, 11]`, the problem's solution answers `308`
- `gcp-student-20261011-greedy/mbpp_891__same_Length`: ensures[0] false at `[2, 1]`, the problem's solution answers `True`
- `gcp-student-20261011-greedy/mbpp_899__check`: ensures[0] false at `[[2, 1, -1, 1, 1], 5]`, the problem's solution answers `True`
- `gcp-student-20261011-greedy/mbpp_900__match_num`: ensures[0] false at `[[53, 46, 55, 50, 47, 52]]`, the problem's solution answers `True`
- `gcp-student-20261011-greedy/mbpp_908__find_fixed_point`: ensures[0] false at `[[0, 4, 7, 13, 13], 1]`, the problem's solution answers `0`
- `gcp-student-20261011-greedy/mbpp_931__sum_series`: ensures[0] false at `[3]`, the problem's solution answers `36.0`
- `gcp-student-20261011-greedy/mbpp_961__roman_to_int`: ensures[12] false at `[[77]]`, the problem's solution answers `1000`
