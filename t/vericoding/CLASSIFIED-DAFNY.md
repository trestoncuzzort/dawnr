# The 39 Dafny-proved survivors in vericoding's Dafny track, read by hand

In `t/AUDIT-VERICODING-DAFNY.md`, Dafny proves the real solution and a one-edit program that computes something different at a ground input, against the same specification, in 39 tasks. A vericoding task is solved by any program the kernel verifies, so each gap below is a wrong solution that counts (2026-10-07):

- **gap** (31): the specification admits a result that is wrong for the task;
- **no spec** (1): the contract is a tautology;
- **latitude** (7): the specification deliberately allows several answers (ties, a sentinel, a value that does not matter).

| class | task | why | the proved survivor: change at input |
|---|---|---|---|
| gap | vericoding_da0003__solve | `result >= 0` only | wrong-var: `var g1: int := gcd(a, b);` -> `var g1: int := gcd(n, b);` at n=1, a=2, b=2, p=2, q=2 -> real 2, twin 1 |
| gap | vericoding_da0010__solve | the edge cases are pinned, the general case only bounded | collapse-if#1: `if n == 1 {` -> `result := 1;` at n=2, t_v=2 -> real 2, twin 1 |
| gap | vericoding_da0014__solve | any irreducible fraction in [0, 1] passes: 1/1 where 0/1 is the answer | off-by-one#4: `numerator := 0;` -> `numerator := 1;` at t_v=1, w=1, b=1 -> real [0, 1], twin [1, 1] |
| gap | vericoding_da0057__solve | feasibility conditions only; the refuel count is free within them | collapse-if#5: `if fuel < a {` -> `refuels := refuels + 1;` at a=2, b=3, f=1, k=2 -> real 1, twin 2 |
| gap | vericoding_da0063__shellGame | any position 0..2 passes (validPosition) | collapse-if: `if remainder == 0 {` -> `result := x;` at n=1, x=0 -> real 1, twin 0 |
| gap | vericoding_da0161__solve | `result == -1 or result >= 0` only | off-by-one: `result := 0;` -> `result := 1;` at n=1, d=1, transactions=[0] -> real 0, twin 1 |
| gap | vericoding_da0200__solve | `0 <= cost <= n` only | off-by-one: `cost := 0;` -> `cost := 1;` at n=1, k=1, requests=[1] -> real 0, twin 1 |
| gap | vericoding_da0278__solve | `result >= 0` only | off-by-one: `result := 0;` -> `result := 1;` at n=1 -> real 0, twin 1 |
| gap | vericoding_da0353__intToString | any non-empty digit string passes: "0" for 1 | collapse-if: `if n == 0 {` -> `s := [48];` at n=1 -> real [49], twin [48] |
| gap | vericoding_da0423__solve | `result > 0` only | wrong-var#1: `result := h + totalB;` -> `result := n + totalB;` at n=1, h=2, a=[1], b=[1] -> real 3, twin 2 |
| gap | vericoding_da0466__solve | increasing positive values with the first pinned; the rest are free | off-by-one#50: `next := result[i_v2 - 1] + 10;` -> `next := result[i_v2 - 1] + 11;` at k=11 -> real [1, 2, 3, 4, 5, 6, 7, 8, 9, 19, 29], twin [1, 2, 3, 4, 5, 6, 7, 8, 9, 19, 30] |
| gap | vericoding_da0483__solve | only the YES answer is pinned; the NO branch may return any string | off-by-one#16: `result := [78, 111];` -> `result := [79, 111];` at n=2, heights=[78, 1] -> real [78, 111], twin [79, 111] |
| gap | vericoding_da0623__solve | only the YES answer is pinned; the NO branch may return any string | off-by-one#6: `result := [78, 79];` -> `result := [79, 79];` at a=1, b=1, x=78 -> real [78, 79], twin [79, 79] |
| gap | vericoding_da0654__solve | any of A, B, C passes: a constant solves it (as in the Verus track) | off-by-one: `result := 65;` -> `result := 66;` at a=[], b=[], c=[] -> real 65, twin 66 |
| gap | vericoding_da0662__solve | `result >= 1` only | wrong-var: `result := n;` -> `result := k;` at n=1, k=2 -> real 1, twin 2 |
| gap | vericoding_dd0187__findPositionOfElement | the count is only `>= 0`: 1 for an empty sequence | off-by-one#6: `count := 0;` -> `count := 1;` at a=[], element=0, n1=0, s1=[] -> real [-1, 0], twin [-1, 1] |
| gap | vericoding_dd0643__sharedElements | only `result within a and b`, never the converse (MutDafny's weak spec) | off-by-one#3: `while i_v4 < h` -> `while i_v4 < h + -1` at a=[0], b=[0] -> real [0], twin [] |
| gap | vericoding_dd0762__lucidNumbers | multiples of 3 up to n, increasing; nothing requires them all | compare-flip: `while i_v3 <= n` -> `while i_v3 < n` at n=0 -> real [0], twin [] |
| gap | vericoding_dj0004__myfun | an upper bound on the first element only | off-by-one#1: `var total: int := 0;` -> `var total: int := -1;` at a=[0], sum=[0], n=1 -> real [0], twin [-1] |
| gap | vericoding_dj0014__myfun | parity only | wrong-operator#2: `a_out := a_out[i := a_out[i] + 1];` -> `a_out := a_out[i := a_out[i] - 1];` at a=[0, 1], n=2 -> real [0, 2], twin [0, 0] |
| gap | vericoding_dj0015__myfun | an upper bound only | collapse-if: `if a_out[i] > n {` -> `a_out := a_out[i := n];` at a=[0], n=1, m=0 -> real [0], twin [1] |
| gap | vericoding_dj0026__myfun | an upper bound on the first element only | off-by-one#1: `var total: int := 0;` -> `var total: int := -1;` at a=[0], sum=[0], n=1 -> real [0], twin [-1] |
| gap | vericoding_dj0027__myfun | an upper bound on the first element only | off-by-one#1: `var total: int := 0;` -> `var total: int := -1;` at a=[0], sum=[0], n=1 -> real [0], twin [-1] |
| gap | vericoding_dj0028__myfun | an upper bound on the first element only | off-by-one#1: `var total: int := 0;` -> `var total: int := -1;` at a=[0], sum=[0], n=1 -> real [0], twin [-1] |
| gap | vericoding_dj0135__arithmeticWeird | `result < 10` for a constant computation: 8 passes where 9 is computed | off-by-one#1: `result := 9;` -> `result := 8;` at  -> real 9, twin 8 |
| gap | vericoding_dv0008__countSumDivisibleBy | `0 <= result <= n` only | collapse-if: `if isSumDivisibleBy(i, d) {` -> `result := result + 1;` at n=1, d=2 -> real 0, twin 1 |
| gap | vericoding_dv0042__maxStrength | `result >= some element`; the maximum is not required | collapse-if: `if nums[i_v] > result {` -> `result := nums[i_v];` at nums=[1, 0] -> real 1, twin 0 |
| gap | vericoding_dv0057__nthUglyNumber | `result > 0` only | collapse-if: `if candidate == 1 {` -> `count := count + 1;` at n=7 -> real 8, twin 7 |
| gap | vericoding_dv0061__rain | `result >= 0` (and 0 for short inputs) only | negate-cond#1: `result := result + water;` -> `} else {` at heights=[1, 0, 1] -> real 1, twin 0 |
| gap | vericoding_dv0062__removeDuplicates | `0 <= result <= len(nums)` only | collapse-if: `if len(nums) == 0 {` -> `result := 0;` at nums=[0] -> real 1, twin 0 |
| gap | vericoding_dv0069__semiOrderedPermutation | `result >= 0` only | collapse-if#1: `if nums[i] == 1 {` -> `pos1 := i;` at nums=[0, 0] -> real 0, twin 1 |
| no spec | vericoding_da0417__solve | `len(result) >= 0`, a tautology | off-by-one#50: `var out: seq := [48];` -> `var out: seq := [49];` at input=[0] -> real [48], twin [49] |
| latitude | vericoding_dd0124__mfirstNegative | the index is free when no negative exists | off-by-one#14: `i := 0;` -> `i := 1;` at v=[] -> real [False, 0], twin [False, 1] |
| latitude | vericoding_dd0275__lookForMin | ties: any index of a minimum | compare-flip#1: `if a[j] < a[m] {` -> `if a[j] <= a[m] {` at a=[0, 0], i=0 -> real 0, twin 1 |
| latitude | vericoding_dd0701__maxLengthList | ties: any longest list | compare-flip#1: `if len(lists[i]) > len(maxList) {` -> `if len(lists[i]) >= len(maxList) {` at lists=[[0], [1]] -> real [0], twin [1] |
| latitude | vericoding_dd0730__minLengthSublist | ties: any shortest list | compare-flip#1: `if len(s[i]) < len(minSublist) {` -> `if len(s[i]) <= len(minSublist) {` at s=[[0], [1]] -> real [0], twin [1] |
| latitude | vericoding_dd0839__findMin | ties: any index of a minimum | compare-flip#1: `if a[i] < a[minIndex] {` -> `if a[i] <= a[minIndex] {` at a=[0, 0], start=0 -> real 0, twin 1 |
| latitude | vericoding_dj0130__findFirstOdd | any negative index means none | off-by-one#12: `index := -(1);` -> `index := -(2);` at arr=[] -> real -1, twin -2 |
| latitude | vericoding_dj0170__binarySearchExists | the index is free when the target is absent | off-by-one#14: `index := 0;` -> `index := 1;` at w=[], m=0, target=0 -> real [False, 0], twin [False, 1] |
