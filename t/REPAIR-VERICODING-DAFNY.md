# Specification repair

For each task whose spec admits a survivor (`t/audit.py`), the clauses `t/contract_repair.py` adds: each holds for the real program at every domain point, and together they kill every survivor they can. **after** is the repaired task's own audit, from scratch.

- tasks with survivors: 54; repaired to zero survivors: 12
- refused because the real body never reads its parameters: 5
- dafny: repaired contract proved for the real body, twin refuted: 9 of 12

| task | survivors before | after | dafny real / twin | clauses added |
|---|---|---|---|---|
| vericoding_da0003__solve | 52 | 52 | refuted / refuted | `n <= result`; `(result == 1 or result == 2) or result == 4` |
| vericoding_da0010__solve | 18 | 10 | verified / refuted | `result <= t_v` |
| vericoding_da0014__solve | 3 | 3 |  /  | (none found) |
| vericoding_da0047__findOptimalT | 3 | 3 |  /  | (none found) |
| vericoding_da0057__solve | 38 | 22 | verified / refuted | `result <= 1` |
| vericoding_da0063__shellGame | 99 | 99 |  /  | (none found) |
| vericoding_da0157__solve | 9 | 9 |  /  | (none found) |
| vericoding_da0161__solve | 4 | 4 |  /  | (none found) |
| vericoding_da0200__solve | 2 | 2 |  /  | (none found) |
| vericoding_da0278__solve | 2 | 2 |  /  | (none found) |
| vericoding_da0296__solveGraph | 34 | 34 |  /  | (none found) |
| vericoding_da0334__computeCombination | 4 | 4 |  /  | (none found) |
| vericoding_da0353__intToString | 9 | 9 |  /  | (none found) |
| vericoding_da0417__solve | 5 | 0 | unproved / refuted | `result == [48]` |
| vericoding_da0423__solve | 6 | 1 | unproved / refuted | `forall t_rk in [0, len(b)) . b[t_rk] <= result`; `h <= result` |
| vericoding_da0426__solve | 4 | 0 | verified / refuted | `len(result) == len(input)` |
| vericoding_da0466__solve | 3 | 3 |  /  | (none found) |
| vericoding_da0476__solve | 2 | 2 |  /  | (none found) |
| vericoding_da0483__solve | 4 | 0 | verified / refuted | `result == [89, 101, 115] or result == [78, 111]` |
| vericoding_da0623__solve | 4 | 0 | verified / refuted | `result == [89, 69, 83] or result == [78, 79]` |
| vericoding_da0654__solve | 2 | 2 |  /  | (none found) |
| vericoding_da0662__solve | 2 | 0 | verified / refuted | `result == n` |
| vericoding_dd0124__mfirstNegative | 5 | 0 | unproved / refuted | `(r.1 == 0 or r.1 == 1) or r.1 == 2`; `r.1 <= len(v)` |
| vericoding_dd0187__findPositionOfElement | 30 | 20 | unproved / refuted | `r.1 <= 1`; `r.0 <= 1` |
| vericoding_dd0275__lookForMin | 1 | 1 |  /  | (none found) |
| vericoding_dd0464__counting_bits | 2 | 2 |  /  | (none found) |
| vericoding_dd0508__mergeSimple | 39 | 39 |  /  | (none found) |
| vericoding_dd0643__sharedElements | 9 | 0 | verified / refuted | `forall t_rj in [0, len(a)) . inArray(a, a[t_rj]) and inArray(b, a[t_rj]) ==> (exists t_rm in [0, len(result)) . result[t_rm] == a[t_rj])` |
| vericoding_dd0668__sumOfCommonDivisors | 4 | 4 |  /  | (none found) |
| vericoding_dd0701__maxLengthList | 1 | 1 |  /  | (none found) |
| vericoding_dd0730__minLengthSublist | 1 | 1 |  /  | (none found) |
| vericoding_dd0762__lucidNumbers | 7 | 7 |  /  | (none found) |
| vericoding_dd0839__findMin | 1 | 1 |  /  | (none found) |
| vericoding_dd0923__longestZero | 1 | 1 |  /  | (none found) |
| vericoding_dh0040__decode_cyclic | 3 | 3 |  /  | (none found) |
| vericoding_dj0004__myfun | 16 | 16 |  /  | (none found) |
| vericoding_dj0010__chooseOdd | 12 | 12 |  /  | (none found) |
| vericoding_dj0014__myfun | 2 | 2 |  /  | (none found) |
| vericoding_dj0015__myfun | 2 | 2 |  /  | (none found) |
| vericoding_dj0026__myfun | 15 | 15 |  /  | (none found) |
| vericoding_dj0027__myfun | 16 | 16 |  /  | (none found) |
| vericoding_dj0028__myfun | 16 | 16 |  /  | (none found) |
| vericoding_dj0130__findFirstOdd | 2 | 0 | verified / refuted | `-1 <= index` |
| vericoding_dj0135__arithmeticWeird | 2 | 0 | verified / refuted | `result == 9` |
| vericoding_dj0170__binarySearchExists | 8 | 0 | unproved / refuted | `r.1 == 0` |
| vericoding_dv0008__countSumDivisibleBy | 16 | 16 |  /  | (none found) |
| vericoding_dv0042__maxStrength | 10 | 0 | verified / refuted | `forall t_rk in [0, len(nums)) . nums[t_rk] <= result` |
| vericoding_dv0057__nthUglyNumber | 77 | 44 | unproved / refuted | `n <= result` |
| vericoding_dv0061__rain | 23 | 14 | unproved / unproved | `(result == 0 or result == 1) or result == 2` |
| vericoding_dv0062__removeDuplicates | 20 | 20 |  /  | (none found) |
| vericoding_dv0069__semiOrderedPermutation | 88 | 88 |  /  | (none found) |
| vericoding_dv0073__solution | 16 | 3 | verified / refuted | `forall t_rk in [0, len(nums)) . nums[t_rk] <= result` |
| vericoding_dv0076__trapRainWater | 35 | 31 | unproved / refuted | `(result == 0 or result == 1) or result == 2` |
| vericoding_dv0117__findFirstOccurrence | 2 | 0 | verified / refuted | `-1 <= result` |
