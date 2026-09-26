# Behavioural decontamination of the train split, 2026-09-25

The second decontamination list `t/loop_filter.decontamination()` merges, beside
`t/DECONTAMINATION-2026-09-21.md` (the same-task list read by hand). This one is
computed: a train problem whose reference solution computes the same function
as a held-out problem's, on both problems' own assertion inputs and on 100
drawn inputs, teaches the held-out answer whatever its English says, so it
leaves every future corpus. Written by `t/behavioural_decontam.py`.

## The rule

- a train problem is a behavioural duplicate of a held-out problem of the same signature kinds when both references run and return equal values (as t reads them) on every one of both problems' own assertion inputs and on every drawn input that both answered, with at least MIN_DRAWS_AGREED of the pair's 100 draws (50 per problem, spec_check.draw shaped like the problem's first example) answered alike (equal values, or both references raising the same exception) and at least MIN_DRAWS_VALUED of them equal values; an input where exactly one reference raises is a difference; an input a reference did not answer in time says nothing; a reference that does not run is reported by name and never counted as agreeing.
- Draws: 50 per problem with `spec_check.draw()` shaped like the problem's
  first example, seeded `behavioural-decontam-2026-09-25:<id>`, so a pair sees 100 draws; a duplicate
  needs at least 50 of them answered alike (equal values, or both references
  raising the same exception on that input) and at least 10 equal values.
- Signature kinds: the argument kinds and the result kind of the first assertion.
- Outputs are compared as t reads them: a string is its code points, a
  one-character string is that character, `true` is not `1`.
- A pair that agrees on every own input and differs on a drawn one is a
  MINIMAL PAIR, kept, and listed below; a pair that differs on an own input is
  simply different and is not listed.
- A reference that does not load, does not finish, or raises on every input is
  reported by name and is never counted as agreeing.

Prior art (fetched 2026-09-25): https://ar5iv.labs.arxiv.org/html/2403.04811; https://arxiv.org/html/2602.12413v1; https://arxiv.org/html/2311.04850v2; https://arxiv.org/html/2508.01357v1.

What the rule cannot see: draws follow the example's shape, so two problems
that differ only outside it (negative inputs, an unsorted sequence) count as
duplicates here. That is the right side to err on for a corpus: the train
problem's program passes the held-out problem's tests.

## Counts

| pool | split | held-out | train | pairs | duplicate | minimal pair | different | insufficient | not run or no reference | cannot draw | references not run |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v5 | `split-v5.json` `49103716b2ed` | 232 | 2771 | 48734 | 71 | 70 | 47939 | 11 | 643 | 0 | 32 |
| v6 | `split-v6.json` `aac8f8eb8226` | 232 | 3803 | 66891 | 78 | 74 | 65641 | 14 | 1084 | 0 | 63 |

**72 train ids are excluded** from every future build: 29, 41, 62, 71, 102, 152, 199, 242, 372, 388, 404, 427, 451, 496, 504, 567, 595, 600, 635, 756, 759, 767, 790, 930, 940, 955, 100013, 100023, 100057, 200178, 200201, 200343, 202415, 202457, 202465, 202493, 202504, 202525, 202542, 202551, 202658, 202849, 202860, 202893, 202914, 203008, 203031, 203336, 203383, 203632, 203736, 203778, 203920, 203929, 203985, 204152, 204154, 204157, 204207, 204444, 204455, 204462, 204498, 204695, 204735, 300281, 300683, 300709, 301606, 5973913, 8141530, 9333067.

- Rediscovered from the 21 same-task exclusions of 2026-09-21: 16 (29, 102, 242, 404, 427, 451, 496, 504, 595, 759, 767, 790, 930, 202465, 203929, 204462).
- New: 56 (41, 62, 71, 152, 199, 372, 388, 567, 600, 635, 756, 940, 955, 100013, 100023, 100057, 200178, 200201, 200343, 202415, 202457, 202493, 202504, 202525, 202542, 202551, 202658, 202849, 202860, 202893, 202914, 203008, 203031, 203336, 203383, 203632, 203736, 203778, 203920, 203985, 204152, 204154, 204157, 204207, 204444, 204455, 204498, 204695, 204735, 300281, 300683, 300709, 301606, 5973913, 8141530, 9333067).
- Held-out problems with a behavioural twin in training: 47 (10, 47, 68, 138, 141, 161, 175, 203, 208, 224, 269, 302, 325, 334, 339, 366, 411, 428, 443, 502, 527, 541, 548, 566, 583, 604, 629, 670, 680, 687, 699, 701, 719, 736, 775, 782, 800, 813, 842, 877, 885, 911, 928, 931, 935, 961, 970). The 32 overlap ids of
  2026-09-21 stay frozen; `score_heldout.py` can report these separately.

## Ten duplicates

1. train `mbpp_29__get_Odd_Occurrence` (29): Write a python function to find the element occurring odd number of times.
   held-out `mbpp_842__get_odd_occurence` (842): Write a function to find the number which occurs for odd number of times in the given array.
   agreed on 49 inputs (4 own, 45 of 100 draws), pool v5
2. train `mbpp_41__filter_evennumbers` (41): Write a function to filter even numbers using lambda function.
   held-out `mbpp_629__Split` (629): Write a python function to find even numbers from a mixed list.
   agreed on 106 inputs (6 own, 100 of 100 draws), pool v5
3. train `mbpp_62__smallest_num` (62): Write a python function to find smallest number in a list.
   held-out `mbpp_443__largest_neg` (443): Write a python function to find the largest negative number from the given list.
   agreed on 90 inputs (6 own, 84 of 100 draws), pool v5
4. train `mbpp_71__comb_sort` (71): Write a function to sort a list of elements using comb sort.
   held-out `mbpp_428__shell_sort` (428): Write a function to sort the given array by using shell sort.
   agreed on 106 inputs (6 own, 100 of 100 draws), pool v5
5. train `mbpp_102__snake_to_camel` (102): Write a function to convert snake case string to camel case string.
   held-out `mbpp_411__snake_to_camel` (411): Write a function to convert the given snake case string to camel case string by using regex.
   agreed on 106 inputs (6 own, 100 of 100 draws), pool v5
6. train `mbpp_152__merge_sort` (152): Write a function to sort the given array by using merge sort.
   held-out `mbpp_141__pancake_sort` (141): Write a function to sort a list of elements using pancake sort.
   agreed on 106 inputs (6 own, 100 of 100 draws), pool v5
7. train `mbpp_152__merge_sort` (152): Write a function to sort the given array by using merge sort.
   held-out `mbpp_428__shell_sort` (428): Write a function to sort the given array by using shell sort.
   agreed on 106 inputs (6 own, 100 of 100 draws), pool v5
8. train `mbpp_199__highest_Power_of_2` (199): Write a python function to find highest power of 2 less than or equal to given number.
   held-out `mbpp_302__set_Bit_Number` (302): Write a python function to find the most significant bit number which is also a set bit.
   agreed on 105 inputs (5 own, 100 of 100 draws), pool v5
9. train `mbpp_242__count_charac` (242): Write a function to count total characters in a string.
   held-out `mbpp_813__string_length` (813): Write a function to find length of the string.
   agreed on 105 inputs (5 own, 100 of 100 draws), pool v5
10. train `mbpp_372__heap_assending` (372): Write a function to sort a given list of elements in ascending order using heap queue algorithm.
   held-out `mbpp_141__pancake_sort` (141): Write a function to sort a list of elements using pancake sort.
   agreed on 106 inputs (6 own, 100 of 100 draws), pool v5

Distinct over the pools (pool v6 holds every v5 pair again): 78 duplicate pairs, 74 minimal pairs, 14 pairs with insufficient evidence, 63 references that did not run.

## Minimal pairs (kept)

74 distinct pairs agree on every own input and differ on a drawn one (144 rows in the JSON, per pool). The first ten:

- train 29 `mbpp_29__get_Odd_Occurrence` vs held-out 119 `mbpp_119__search`: agreed 16, then on input `[[1, 0, 4, 3, 2, 5], 5]` train said `1`, held-out said `4` (disagree)
- train 54 `mbpp_54__counting_sort` vs held-out 141 `mbpp_141__pancake_sort`: agreed 101, then on input `[[-1, 24]]` train said `[24, 24]`, held-out said `[-1, 24]` (disagree)
- train 54 `mbpp_54__counting_sort` vs held-out 428 `mbpp_428__shell_sort`: agreed 101, then on input `[[-1, 24]]` train said `[24, 24]`, held-out said `[-1, 24]` (disagree)
- train 54 `mbpp_54__counting_sort` vs held-out 516 `mbpp_516__radix_sort`: agreed 89, then on input `[[]]` train said `[]`, held-out said `"raised"` (one raised)
- train 54 `mbpp_54__counting_sort` vs held-out 877 `mbpp_877__sort_String`: agreed 87, then on input `[[21]]` train said `[21]`, held-out said `21` (disagree)
- train 71 `mbpp_71__comb_sort` vs held-out 141 `mbpp_141__pancake_sort`: agreed 105, then on input `[[50, 36, 39, 50, 42, 77, 17]]` train said `[17, 39, 36, 42, 50, 50, 77]`, held-out said `[17, 36, 39, 42, 50, 50, 77]` (disagree)
- train 71 `mbpp_71__comb_sort` vs held-out 516 `mbpp_516__radix_sort`: agreed 97, then on input `[[]]` train said `[]`, held-out said `"raised"` (one raised)
- train 71 `mbpp_71__comb_sort` vs held-out 877 `mbpp_877__sort_String`: agreed 91, then on input `[[47]]` train said `[47]`, held-out said `47` (disagree)
- train 76 `mbpp_76__count_Squares` vs held-out 347 `mbpp_347__count_Squares`: agreed 29, then on input `[6, 0]` train said `0`, held-out said `-35` (disagree)
- train 152 `mbpp_152__merge_sort` vs held-out 516 `mbpp_516__radix_sort`: agreed 84, then on input `[[5, 8, 8, 10, 0, 4, 9, 0]]` train said `[0, 0, 4, 5, 8, 8, 9, 10]`, held-out said `[10, 0, 0, 4, 5, 8, 8, 9]` (disagree)

## The 2026-09-21 exclusions this rule did not rediscover

- 76: verdicts ['different', 'minimal pair']; closest held-out 347 (minimal pair, 29 agreed)
- 498: verdicts ['different', 'minimal pair']; closest held-out 687 (minimal pair, 103 agreed)
- 728: verdicts ['different', 'minimal pair']; closest held-out 729 (minimal pair, 67 agreed)
- 952: verdicts ['different', 'minimal pair']; closest held-out 402 (minimal pair, 89 agreed)
- 200124: verdicts ['different', 'minimal pair']; closest held-out 492 (minimal pair, 99 agreed)

## References that did not run

63 references produced no value on any input they were given, so every pair with them is 'not run', never a duplicate (each listed once, from the first pool that ran it):

- v5 200179 `apps_179__getLengthOfOptimalCompression`: reference raised on every input it was given
- v5 200215 `apps_215__isGoodArray`: reference raised on every input it was given
- v5 200229 `apps_229__canReorderDoubled`: reference raised on every input it was given
- v5 200242 `apps_242__maxEqualFreq`: reference raised on every input it was given
- v5 200259 `apps_259__smallestDivisor`: reference does not load (no code, an import or syntax error, or the function is missing)
- v5 200278 `apps_278__largestMultipleOfThree`: reference raised on every input it was given
- v5 200297 `apps_297__numTilePossibilities`: reference raised on every input it was given
- v5 200300 `apps_300__leastOpsExpressTarget`: reference raised on every input it was given
- v5 200365 `apps_365__uniqueLetterString`: reference raised on every input it was given
- v5 200426 `apps_426__reorderedPowerOf2`: reference raised on every input it was given
- v5 201642 `apps_1642__multiply`: reference does not load (no code, an import or syntax error, or the function is missing)
- v5 201643 `apps_1643__almost_everywhere_zero`: reference does not load (no code, an import or syntax error, or the function is missing)
- v5 201666 `apps_1666__solution`: reference does not load (no code, an import or syntax error, or the function is missing)
- v5 201669 `apps_1669__isNStraightHand`: reference raised on every input it was given
- v5 202414 `apps_2414__countGoodTriplets`: reference raised on every input it was given
- v5 202443 `apps_2443__maxNumberOfBalloons`: reference raised on every input it was given
- v5 202785 `apps_2785__parameter`: reference does not load (no code, an import or syntax error, or the function is missing)
- v5 202803 `apps_2803__DPC_sequence`: reference does not load (no code, an import or syntax error, or the function is missing)
- v5 202924 `apps_2924__are_coprime`: reference does not load (no code, an import or syntax error, or the function is missing)
- v5 203314 `apps_3314__solve`: reference raised on every input it was given
- v5 203401 `apps_3401__eq_dice`: reference does not load (no code, an import or syntax error, or the function is missing)
- v5 203454 `apps_3454__candies_to_buy`: reference does not load (no code, an import or syntax error, or the function is missing)
- v5 203687 `apps_3687__mn_lcm`: reference does not load (no code, an import or syntax error, or the function is missing)
- v5 203844 `apps_3844__poly_from_roots`: reference does not load (no code, an import or syntax error, or the function is missing)
- v5 203863 `apps_3863__final_attack_value`: reference does not load (no code, an import or syntax error, or the function is missing)
- v5 203916 `apps_3916__mean_vs_median`: reference does not load (no code, an import or syntax error, or the function is missing)
- v5 204012 `apps_4012__encrypt`: reference does not load (no code, an import or syntax error, or the function is missing)
- v5 204061 `apps_4061__count_ones`: reference does not load (no code, an import or syntax error, or the function is missing)
- v5 204169 `apps_4169__para_to_rect`: reference does not load (no code, an import or syntax error, or the function is missing)
- v5 204384 `apps_4384__fraction`: reference does not load (no code, an import or syntax error, or the function is missing)
- v5 204439 `apps_4439__div_num`: reference does not load (no code, an import or syntax error, or the function is missing)
- v5 204752 `apps_4752__has_subpattern`: reference does not load (no code, an import or syntax error, or the function is missing)
- v6 300070 `apps_100070__apps_stdin_70`: reference raised on every input it was given
- v6 300081 `apps_100081__apps_stdin_81`: reference raised on every input it was given
- v6 300313 `apps_100313__apps_stdin_313`: reference raised on every input it was given
- v6 300377 `apps_100377__apps_stdin_377`: reference raised on every input it was given
- v6 300397 `apps_100397__apps_stdin_397`: reference raised on every input it was given
- v6 301113 `apps_101113__apps_stdin_1113`: reference raised on every input it was given
- v6 301470 `apps_101470__apps_stdin_1470`: reference raised on every input it was given
- v6 301625 `apps_101625__apps_stdin_1625`: reference raised on every input it was given
- v6 301846 `apps_101846__apps_stdin_1846`: reference raised on every input it was given
- v6 301930 `apps_101930__apps_stdin_1930`: reference raised on every input it was given
- v6 302509 `apps_102509__apps_stdin_2509`: reference raised on every input it was given
- v6 303714 `apps_103714__apps_stdin_3714`: reference raised on every input it was given
- v6 303774 `apps_103774__apps_stdin_3774`: reference raised on every input it was given
- v6 304070 `apps_104070__apps_stdin_4070`: reference raised on every input it was given
- v6 304309 `apps_104309__apps_stdin_4309`: reference raised on every input it was given
- v6 304402 `apps_104402__apps_stdin_4402`: reference raised on every input it was given
- v6 304442 `apps_104442__apps_stdin_4442`: reference raised on every input it was given
- v6 304484 `apps_104484__apps_stdin_4484`: reference raised on every input it was given
- v6 304559 `apps_104559__apps_stdin_4559`: reference raised on every input it was given
- v6 304593 `apps_104593__apps_stdin_4593`: reference raised on every input it was given
- v6 304683 `apps_104683__apps_stdin_4683`: reference raised on every input it was given
- v6 2059334 `apps_1859334__cc_stdin_taand`: reference raised on every input it was given
- v6 3453886 `apps_3253886__cc_stdin_p03659_AtCoder_Beginner_Contest_067___Splitting_Pile`: reference raised on every input it was given
- v6 4806287 `apps_4606287__cc_stdin_p02603_M_SOLUTIONS_Programming_Contest_2020___Road_to_Millionaire`: reference raised on every input it was given
- v6 5046167 `apps_4846167__cc_stdin_341_C__Iahub_and_Permutations`: reference raised on every input it was given
- v6 5455213 `apps_5255213__cc_stdin_tree`: reference raised on every input it was given
- v6 7855165 `apps_7655165__cc_stdin_cdva1501`: reference raised on every input it was given
- v6 7922531 `apps_7722531__cc_stdin_p02642_AtCoder_Beginner_Contest_170___Not_Divisible`: reference raised on every input it was given
- v6 8836270 `apps_8636270__cc_stdin_340_E__Iahub_and_Permutations`: reference raised on every input it was given
- v6 9092507 `apps_8892507__cc_stdin_chefeq`: reference raised on every input it was given
- v6 9105357 `apps_8905357__cc_stdin_p03064_Tenka1_Programmer_Contest_2019___Three_Colors`: reference raised on every input it was given

## Insufficient evidence

14 distinct pairs never differed but fell short of the bar (50 draws answered alike, 10 with values, every own input agreed); they are listed in the JSON and not excluded.

## Weak tests

The 18 held-out problems with weak tests (`t/decontamination-2026-09-21.json` weak_test_eval_ids) are 20, 45, 68, 72, 179, 201, 269, 355, 362, 541, 565, 605, 683, 711, 741, 768, 804, 866; a duplicate verdict there rests on the draws, which is why the draws are required.

## Reading of the results

Written by hand from the pairs above (passed to `write --notes`; the sections before this one
are generated).

**What the rule found that the reading missed.** The 2026-09-21 list was read
by hand from text and AST similarity plus the held-out problems' own three
assertions. The behavioural rule adds sorting, in force: five sort problems
(`comb_sort` 71, `merge_sort` 152, `heap_assending` 372, `apps_3008__sort_array`,
and the counting sort 54 as a minimal pair) compute the function held-out
`pancake_sort` 141, `shell_sort` 428 and `sort_String` 877 ask for. In t there is
no algorithm to name, only the function, so a training document for merge
sort is the held-out answer for shell sort. The same holds for
`highest_Power_of_2` 199 against `set_Bit_Number` 302, `snake_to_camel` 102
against 411, three HumanEval problems (`greatest_common_divisor`, `strlen`,
`monotonic`) and 36 APPS problems whose LeetCode or Codewars statements ask
for hamming distance, the equilibrium index, the digit sum, `is_even`, the
minimum of a list, or the longest increasing subsequence under other words.

**Pool v6** adds the 1,032 stdin-shaped problems and seven exclusions with
them, each a whole competition script that is one held-out function: the last
digit of a product (held-out 47), a character's code point (269, one of the
two problems that had been lifted into every corpus since r7), the set bits
of an integer (224), the number of divisors (339), a digit sum (566), a gcd
(687) and a remainder (502). The 31 further references that did not run under
v6 are stdin scripts that raised on every input they were given (a script
that prints more than one token, or one whose input the draws cannot be
written into); each is named in the JSON.

**What the reading found that the rule keeps.** Five of the 21 exclusions of
2026-09-21 are minimal pairs here, each with its differing input in the JSON:
76 against 347 (the same English, two formulas that part at `(6, 0)`: 0
against -35), 498 against 687 (`gcd(11, 0)`: one recurses on zero, one
returns 11), 728 against 729 (`zip` against indexing on lists of unequal
length), 952 against 402 (a division by zero on `(0, 2, 9)`), and
`apps_124__search` against 492 (binary search against a linear one on an
unsorted list). They stay excluded because the merged policy keeps the
2026-09-21 list whole; the rule alone would keep them, and says so.

**The three corrections made while measuring**, each caught by a pair the
first run got wrong: (1) an integral float reads as its int, because MBPP 76
returns `20.0` where 347 returns `20` and the problem's own assertion accepts
both; (2) both references raising the same exception on an input counts as
answering alike, because train 595 and held-out 699 are the same code and
refuse the same 52 of their 100 draws; (3) a draw that repeats weighs as many
times as it was drawn, because an example of 2 draws from 0..4 and
`divisorGame` (n even) against `is_Sum_Of_Powers_Of_Two` (n even) was
"insufficient" on 16 distinct draws that all agreed.

**Dev split.** Three excluded ids, 199, 372 and 955, are in `t/r12-dev-ids.json`.
A dev problem is never trained on either way, but a dev problem that is a
behavioural twin of a held-out one measures the held-out problem in the
stopping rule. The dev list is drawn by `t/r12_data_queue.sh dev-ids` from the
2026-09-21 list only; it should draw from the merged policy too.

**Reproducibility.** Pool v5 ran twice under the same seeds (691.7 s and
667.6 s on four lab CPUs at nice 19) and gave the same pairs; the verdicts are
re-derived from the recorded counts by `verdict_of`, so a changed threshold
needs no new run. The 32 references that never ran are APPS records whose
first solution does not define the named function or expects an argument
shape t cannot write; each is named in the JSON and none was counted as
agreeing.

