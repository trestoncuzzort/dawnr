# Specification audit

Every one-edit mutant of each body, classed by the interpreter over the task's bounded domain (t/audit.py): **killed** (the spec rejects its result somewhere), **same** (computes the same everywhere), **diverges** (runs out of steps where the real body ends), **survivor** (computes something different, and the spec accepts it everywhere).

- tasks: 511; audited: 488; not audited: 21 no-input, 2 real-violates-spec
- behaviour-changing mutants the specs kill: 14357 of 15148 (94.8%)
- tasks whose spec admits a survivor: 54 of 488
- dafny: real body verified in 425 of 488; of those, a survivor proved too (a wrong program with a proof) in 39

| task | mutants | killed | same | diverges | survivors | proved by the kernel | a survivor: change at input |
|---|---|---|---|---|---|---|---|
| vericoding_da0000__solve | 58 | 43 | 7 | 8 | 0 | 0 |  |
| vericoding_da0001__solve | 221 | 198 | 23 | 0 | 0 | 0 |  |
| vericoding_da0003__solve | 83 | 0 | 31 | 0 | 52 | 1 | wrong-var: `var g1: int := gcd(a, b);` -> `var g1: int := gcd(n, b);` at n=1, a=2, b=2, p=2, q=2 -> real 2, twin 1 |
| vericoding_da0010__solve | 53 | 16 | 19 | 0 | 18 | 1 | collapse-if#1: `if n == 1 {` -> `result := 1;` at n=2, t_v=2 -> real 2, twin 1 |
| vericoding_da0014__solve | 25 | 14 | 8 | 0 | 3 | 1 | off-by-one#4: `numerator := 0;` -> `numerator := 1;` at t_v=1, w=1, b=1 -> real [0, 1], twin [1, 1] |
| vericoding_da0017__solve | 74 | 73 | 1 | 0 | 0 | 0 |  |
| vericoding_da0018__solve | 19 | 19 | 0 | 0 | 0 | 0 |  |
| vericoding_da0022__solve | 3 | 3 | 0 | 0 | 0 | 0 |  |
| vericoding_da0026__solve | 155 | 145 | 10 | 0 | 0 | 0 |  |
| vericoding_da0029__solve | 120 | 102 | 15 | 3 | 0 | 0 |  |
| vericoding_da0031__solve | 45 | 40 | 2 | 3 | 0 | 0 |  |
| vericoding_da0035__solve | 111 | 103 | 8 | 0 | 0 | (real timeout) |  |
| vericoding_da0036__solve | 21 | 21 | 0 | 0 | 0 | 0 |  |
| vericoding_da0038__solve | no-input | | | | | | |
| vericoding_da0043__solve | 78 | 74 | 4 | 0 | 0 | (real timeout) |  |
| vericoding_da0044__solve | no-input | | | | | | |
| vericoding_da0046__minimumMoves | 44 | 39 | 5 | 0 | 0 | 0 |  |
| vericoding_da0047__findOptimalT | 69 | 44 | 12 | 10 | 3 | (real unproved) | compare-flip#1: `if current_cost < min_cost {` -> `if current_cost <= min_cost {` at n=1, sticks=[1] -> real [1, 0], twin [2, 0] |
| vericoding_da0049__solve | 32 | 32 | 0 | 0 | 0 | 0 |  |
| vericoding_da0054__solve | 40 | 40 | 0 | 0 | 0 | 0 |  |
| vericoding_da0055__solve | 160 | 153 | 7 | 0 | 0 | 0 |  |
| vericoding_da0057__solve | 223 | 104 | 81 | 0 | 38 | 1 | collapse-if#5: `if fuel < a {` -> `refuels := refuels + 1;` at a=2, b=3, f=1, k=2 -> real 1, twin 2 |
| vericoding_da0059__solve | 28 | 28 | 0 | 0 | 0 | 0 |  |
| vericoding_da0060__computeDistanceToHouse | 27 | 27 | 0 | 0 | 0 | 0 |  |
| vericoding_da0062__solve | 78 | 36 | 21 | 21 | 0 | 0 |  |
| vericoding_da0063__shellGame | 102 | 3 | 0 | 0 | 99 | 1 | collapse-if: `if remainder == 0 {` -> `result := x;` at n=1, x=0 -> real 1, twin 0 |
| vericoding_da0071__solve | 40 | 23 | 14 | 3 | 0 | 0 |  |
| vericoding_da0072__solve | 24 | 24 | 0 | 0 | 0 | 0 |  |
| vericoding_da0078__solve | 31 | 30 | 1 | 0 | 0 | 0 |  |
| vericoding_da0080__solve | 31 | 28 | 3 | 0 | 0 | 0 |  |
| vericoding_da0084__solve | 28 | 27 | 1 | 0 | 0 | (real timeout) |  |
| vericoding_da0085__findMinimumTotalDistance | 83 | 68 | 15 | 0 | 0 | 0 |  |
| vericoding_da0086__solve | no-input | | | | | | |
| vericoding_da0090__solve | 75 | 16 | 59 | 0 | 0 | 0 |  |
| vericoding_da0101__solve | 37 | 34 | 1 | 2 | 0 | 0 |  |
| vericoding_da0105__solve | 37 | 37 | 0 | 0 | 0 | 0 |  |
| vericoding_da0108__solve | 43 | 41 | 0 | 2 | 0 | 0 |  |
| vericoding_da0110__solve | 87 | 87 | 0 | 0 | 0 | 0 |  |
| vericoding_da0113__solve | 39 | 39 | 0 | 0 | 0 | 0 |  |
| vericoding_da0119__solve | 54 | 45 | 9 | 0 | 0 | 0 |  |
| vericoding_da0120__solve | 112 | 68 | 44 | 0 | 0 | 0 |  |
| vericoding_da0121__solve | 205 | 196 | 9 | 0 | 0 | (real timeout) |  |
| vericoding_da0123__solve | 35 | 32 | 0 | 3 | 0 | 0 |  |
| vericoding_da0131__solve | 62 | 54 | 6 | 2 | 0 | (real unproved) |  |
| vericoding_da0133__solve | 4 | 4 | 0 | 0 | 0 | 0 |  |
| vericoding_da0140__minBacteria | 47 | 41 | 2 | 4 | 0 | 0 |  |
| vericoding_da0144__solve | 42 | 38 | 1 | 3 | 0 | 0 |  |
| vericoding_da0145__solve | 0 | 0 | 0 | 0 | 0 | (real unproved) |  |
| vericoding_da0148__solve | 18 | 18 | 0 | 0 | 0 | (real timeout) |  |
| vericoding_da0151__solve | 35 | 33 | 0 | 2 | 0 | 0 |  |
| vericoding_da0153__solve | 63 | 42 | 19 | 2 | 0 | 0 |  |
| vericoding_da0157__solve | 36 | 27 | 0 | 0 | 9 | (real timeout) | off-by-one: `var x_v: int := max(2 * n, a);` -> `var x_v: int := max(3 * n, a);` at n=1, a=1, b=1 -> real [6, 2, 3], twin [9, 3, 3] |
| vericoding_da0159__solve | no-input | | | | | | |
| vericoding_da0161__solve | 4 | 0 | 0 | 0 | 4 | 1 | off-by-one: `result := 0;` -> `result := 1;` at n=1, d=1, transactions=[0] -> real 0, twin 1 |
| vericoding_da0162__convertIntToString | 0 | 0 | 0 | 0 | 0 | 0 |  |
| vericoding_da0167__solve | 117 | 117 | 0 | 0 | 0 | 0 |  |
| vericoding_da0168__solve | 66 | 66 | 0 | 0 | 0 | 0 |  |
| vericoding_da0172__solve | 66 | 59 | 5 | 2 | 0 | (real unproved) |  |
| vericoding_da0173__solve | 46 | 35 | 5 | 6 | 0 | 0 |  |
| vericoding_da0174__solve | 66 | 55 | 3 | 8 | 0 | 0 |  |
| vericoding_da0176__solve | 64 | 51 | 13 | 0 | 0 | 0 |  |
| vericoding_da0178__solve | 60 | 52 | 1 | 7 | 0 | 0 |  |
| vericoding_da0180__solve | 72 | 65 | 7 | 0 | 0 | 0 |  |
| vericoding_da0183__solve | 237 | 176 | 61 | 0 | 0 | 0 |  |
| vericoding_da0187__solve | 41 | 40 | 1 | 0 | 0 | 0 |  |
| vericoding_da0188__solve | 76 | 73 | 3 | 0 | 0 | 0 |  |
| vericoding_da0190__solve | 11 | 10 | 1 | 0 | 0 | 0 |  |
| vericoding_da0200__solve | 4 | 2 | 0 | 0 | 2 | 1 | off-by-one: `cost := 0;` -> `cost := 1;` at n=1, k=1, requests=[1] -> real 0, twin 1 |
| vericoding_da0201__solve | no-input | | | | | | |
| vericoding_da0204__solve | 29 | 27 | 2 | 0 | 0 | 0 |  |
| vericoding_da0205__solve | 32 | 18 | 8 | 6 | 0 | (real timeout) |  |
| vericoding_da0210__solve | 39 | 39 | 0 | 0 | 0 | 0 |  |
| vericoding_da0211__solve | 27 | 27 | 0 | 0 | 0 | 0 |  |
| vericoding_da0212__gildCells | 98 | 87 | 0 | 11 | 0 | (real timeout) |  |
| vericoding_da0216__solve | 4 | 4 | 0 | 0 | 0 | 0 |  |
| vericoding_da0217__solve | 32 | 23 | 1 | 8 | 0 | (real unproved) |  |
| vericoding_da0224__solve | 44 | 35 | 1 | 8 | 0 | 0 |  |
| vericoding_da0229__solve | 31 | 24 | 0 | 7 | 0 | 0 |  |
| vericoding_da0230__solve | 99 | 90 | 9 | 0 | 0 | 0 |  |
| vericoding_da0233__solve | no-input | | | | | | |
| vericoding_da0234__solve | 12 | 12 | 0 | 0 | 0 | 0 |  |
| vericoding_da0239__solve | 17 | 17 | 0 | 0 | 0 | 0 |  |
| vericoding_da0246__solve | 54 | 12 | 42 | 0 | 0 | (real unproved) |  |
| vericoding_da0263__solve | 30 | 30 | 0 | 0 | 0 | 0 |  |
| vericoding_da0264__solve | 33 | 26 | 7 | 0 | 0 | 0 |  |
| vericoding_da0278__solve | 4 | 2 | 0 | 0 | 2 | 1 | off-by-one: `result := 0;` -> `result := 1;` at n=1 -> real 0, twin 1 |
| vericoding_da0282__solve | 163 | 150 | 13 | 0 | 0 | (real timeout) |  |
| vericoding_da0285__solve | 100 | 56 | 42 | 2 | 0 | 0 |  |
| vericoding_da0287__solve | 54 | 54 | 0 | 0 | 0 | (real timeout) |  |
| vericoding_da0292__canFormat | 8 | 5 | 3 | 0 | 0 | 0 |  |
| vericoding_da0292__checkFormattingHelper | 214 | 73 | 141 | 0 | 0 | 0 |  |
| vericoding_da0292__solve | 51 | 22 | 15 | 14 | 0 | (real unproved) |  |
| vericoding_da0296__solveGraph | 63 | 17 | 9 | 3 | 34 | 0 | wrong-var#4: `var sum: int := pathSum(i_v11, k, f, w);` -> `var sum: int := pathSum(n, k, f, w);` at n=1, k=1, f=[0], w=[1] -> real [[1], [1]], twin [[0], [1]] |
| vericoding_da0297__calculateDistances | 252 | 169 | 81 | 2 | 0 | 0 |  |
| vericoding_da0305__solve | 122 | 88 | 32 | 2 | 0 | (real unproved) |  |
| vericoding_da0308__solve | 11 | 11 | 0 | 0 | 0 | 0 |  |
| vericoding_da0326__solve | 97 | 83 | 10 | 4 | 0 | 0 |  |
| vericoding_da0328__solve | 85 | 54 | 29 | 2 | 0 | (real unproved) |  |
| vericoding_da0333__solve | 189 | 8 | 181 | 0 | 0 | 0 |  |
| vericoding_da0334__computeCombination | 125 | 109 | 12 | 0 | 4 | (real timeout) | wrong-var#30: `var den2: int := vericoding_da0334__computeFactorial(n - k, mod);` -> `var den2: int := vericoding_da0334__computeFactorial(n - k, n);` at n=4, k=1, mod=1000000 -> real 739584, twin 656256 |
| vericoding_da0334__computeModInverse | 7 | 7 | 0 | 0 | 0 | 0 |  |
| vericoding_da0334__solve | 77 | 4 | 68 | 5 | 0 | (real timeout) |  |
| vericoding_da0345__solve | 16 | 16 | 0 | 0 | 0 | (real unproved) |  |
| vericoding_da0347__solve | 41 | 33 | 8 | 0 | 0 | 0 |  |
| vericoding_da0353__intToString | 34 | 18 | 0 | 7 | 9 | 1 | collapse-if: `if n == 0 {` -> `s := [48];` at n=1 -> real [49], twin [48] |
| vericoding_da0360__solve | 155 | 33 | 121 | 1 | 0 | 0 |  |
| vericoding_da0366__solve | 4 | 4 | 0 | 0 | 0 | 0 |  |
| vericoding_da0367__solve | no-input | | | | | | |
| vericoding_da0368__solve | 52 | 52 | 0 | 0 | 0 | 0 |  |
| vericoding_da0375__solveCase | no-input | | | | | | |
| vericoding_da0377__solve | 56 | 46 | 5 | 5 | 0 | 0 |  |
| vericoding_da0386__solve | 65 | 45 | 18 | 2 | 0 | (real timeout) |  |
| vericoding_da0396__solve | 51 | 45 | 4 | 2 | 0 | (real unproved) |  |
| vericoding_da0399__solve | 10 | 10 | 0 | 0 | 0 | 0 |  |
| vericoding_da0405__solve | no-input | | | | | | |
| vericoding_da0409__solveRivalDistance | 93 | 87 | 6 | 0 | 0 | 0 |  |
| vericoding_da0417__solve | 377 | 23 | 339 | 10 | 5 | 1 | off-by-one#50: `var out: seq := [48];` -> `var out: seq := [49];` at input=[0] -> real [48], twin [49] |
| vericoding_da0422__determineWinner | 32 | 32 | 0 | 0 | 0 | 0 |  |
| vericoding_da0423__solve | 7 | 1 | 0 | 0 | 6 | 1 | wrong-var#1: `result := h + totalB;` -> `result := n + totalB;` at n=1, h=2, a=[1], b=[1] -> real 3, twin 2 |
| vericoding_da0426__solve | 16 | 9 | 0 | 3 | 4 | 0 | compare-flip: `while i_v2 < len(input)` -> `while i_v2 <= len(input)` at input=[0] -> real [1], twin [1, 2] |
| vericoding_da0429__solve | 59 | 55 | 4 | 0 | 0 | 0 |  |
| vericoding_da0453__solve | 26 | 20 | 4 | 2 | 0 | 0 |  |
| vericoding_da0466__solve | 134 | 122 | 7 | 2 | 3 | 1 | off-by-one#50: `next := result[i_v2 - 1] + 10;` -> `next := result[i_v2 - 1] + 11;` at k=11 -> real [1, 2, 3, 4, 5, 6, 7, 8, 9, 19, 29], twin [1, 2, 3, 4, 5, 6, 7, 8, 9, 19, 30] |
| vericoding_da0469__solve | 0 | 0 | 0 | 0 | 0 | (real vacuous) |  |
| vericoding_da0470__solve | 55 | 50 | 2 | 3 | 0 | (real unproved) |  |
| vericoding_da0472__solve | 48 | 12 | 36 | 0 | 0 | 0 |  |
| vericoding_da0475__solve | 95 | 85 | 10 | 0 | 0 | 0 |  |
| vericoding_da0476__solve | 30 | 17 | 5 | 6 | 2 | 0 | off-by-one#7: `current := current + current / 100;` -> `current := current + current / 99;` at x=1000000 -> real 983, twin 973 |
| vericoding_da0478__solve | 81 | 81 | 0 | 0 | 0 | 0 |  |
| vericoding_da0482__solve | 14 | 11 | 0 | 3 | 0 | 0 |  |
| vericoding_da0483__solve | 45 | 35 | 4 | 2 | 4 | 1 | off-by-one#16: `result := [78, 111];` -> `result := [79, 111];` at n=2, heights=[78, 1] -> real [78, 111], twin [79, 111] |
| vericoding_da0484__solve | 21 | 21 | 0 | 0 | 0 | 0 |  |
| vericoding_da0488__solve | 22 | 22 | 0 | 0 | 0 | 0 |  |
| vericoding_da0489__solve | 64 | 56 | 6 | 2 | 0 | (real unproved) |  |
| vericoding_da0493__solve | 24 | 23 | 1 | 0 | 0 | 0 |  |
| vericoding_da0496__solve | 16 | 16 | 0 | 0 | 0 | 0 |  |
| vericoding_da0497__solve | 0 | 0 | 0 | 0 | 0 | 0 |  |
| vericoding_da0499__solve | 1 | 0 | 1 | 0 | 0 | (real unproved) |  |
| vericoding_da0500__solve | 20 | 20 | 0 | 0 | 0 | 0 |  |
| vericoding_da0505__solve | 2 | 2 | 0 | 0 | 0 | 0 |  |
| vericoding_da0513__solve | real-violates-spec | | | | | | |
| vericoding_da0515__solve | 20 | 20 | 0 | 0 | 0 | 0 |  |
| vericoding_da0516__solve | 40 | 40 | 0 | 0 | 0 | 0 |  |
| vericoding_da0517__solve | 86 | 42 | 41 | 3 | 0 | 0 |  |
| vericoding_da0519__solve | no-input | | | | | | |
| vericoding_da0522__solve | 14 | 14 | 0 | 0 | 0 | 0 |  |
| vericoding_da0523__solve | 33 | 32 | 1 | 0 | 0 | 0 |  |
| vericoding_da0524__solve | 15 | 15 | 0 | 0 | 0 | 0 |  |
| vericoding_da0526__solve | 35 | 35 | 0 | 0 | 0 | 0 |  |
| vericoding_da0527__solve | 14 | 10 | 0 | 4 | 0 | 0 |  |
| vericoding_da0529__solve | 2 | 2 | 0 | 0 | 0 | 0 |  |
| vericoding_da0530__solve | 50 | 48 | 2 | 0 | 0 | 0 |  |
| vericoding_da0531__solve | 54 | 54 | 0 | 0 | 0 | 0 |  |
| vericoding_da0533__solve | 93 | 85 | 8 | 0 | 0 | 0 |  |
| vericoding_da0538__computeMaxGroups | 5 | 5 | 0 | 0 | 0 | 0 |  |
| vericoding_da0539__calculateMaxPies | 13 | 13 | 0 | 0 | 0 | 0 |  |
| vericoding_da0540__solve | 34 | 11 | 23 | 0 | 0 | 0 |  |
| vericoding_da0543__solve | 55 | 8 | 47 | 0 | 0 | 0 |  |
| vericoding_da0545__solve | 14 | 12 | 0 | 2 | 0 | 0 |  |
| vericoding_da0551__solve | 28 | 25 | 1 | 2 | 0 | 0 |  |
| vericoding_da0554__countEvenOddPairs | 23 | 23 | 0 | 0 | 0 | 0 |  |
| vericoding_da0556__solveCakeProblem | 26 | 26 | 0 | 0 | 0 | 0 |  |
| vericoding_da0558__solve | 14 | 14 | 0 | 0 | 0 | 0 |  |
| vericoding_da0561__solve | 18 | 18 | 0 | 0 | 0 | 0 |  |
| vericoding_da0562__solve | no-input | | | | | | |
| vericoding_da0564__solve | 36 | 36 | 0 | 0 | 0 | 0 |  |
| vericoding_da0565__solve | no-input | | | | | | |
| vericoding_da0569__solve | no-input | | | | | | |
| vericoding_da0576__intToStringMethod | 0 | 0 | 0 | 0 | 0 | 0 |  |
| vericoding_da0576__parseInput | 0 | 0 | 0 | 0 | 0 | 0 |  |
| vericoding_da0576__solve | 56 | 22 | 25 | 9 | 0 | 0 |  |
| vericoding_da0577__solve | 4 | 2 | 2 | 0 | 0 | (real vacuous) |  |
| vericoding_da0580__solve | 6 | 6 | 0 | 0 | 0 | 0 |  |
| vericoding_da0584__solve | 62 | 56 | 1 | 5 | 0 | (real unproved) |  |
| vericoding_da0585__solve | 14 | 14 | 0 | 0 | 0 | 0 |  |
| vericoding_da0586__solve | 15 | 15 | 0 | 0 | 0 | 0 |  |
| vericoding_da0588__solve | 10 | 10 | 0 | 0 | 0 | (real unproved) |  |
| vericoding_da0599__solve | no-input | | | | | | |
| vericoding_da0601__solve | 50 | 47 | 0 | 3 | 0 | 0 |  |
| vericoding_da0602__solve | 61 | 61 | 0 | 0 | 0 | 0 |  |
| vericoding_da0606__solve | no-input | | | | | | |
| vericoding_da0609__getRow | 67 | 53 | 6 | 8 | 0 | 0 |  |
| vericoding_da0612__solve | 34 | 34 | 0 | 0 | 0 | 0 |  |
| vericoding_da0615__calculateBlackSquares | 9 | 9 | 0 | 0 | 0 | 0 |  |
| vericoding_da0620__solve | no-input | | | | | | |
| vericoding_da0623__solve | 30 | 26 | 0 | 0 | 4 | 1 | off-by-one#6: `result := [78, 79];` -> `result := [79, 79];` at a=1, b=1, x=78 -> real [78, 79], twin [79, 79] |
| vericoding_da0624__solve | 19 | 19 | 0 | 0 | 0 | 0 |  |
| vericoding_da0627__solve | 6 | 2 | 4 | 0 | 0 | 0 |  |
| vericoding_da0629__solve | 67 | 61 | 2 | 4 | 0 | 0 |  |
| vericoding_da0633__solve | no-input | | | | | | |
| vericoding_da0642__solve | 59 | 46 | 2 | 11 | 0 | 0 |  |
| vericoding_da0644__solve | 16 | 16 | 0 | 0 | 0 | 0 |  |
| vericoding_da0648__solve | no-input | | | | | | |
| vericoding_da0654__solve | 4 | 2 | 0 | 0 | 2 | 1 | off-by-one: `result := 65;` -> `result := 66;` at a=[], b=[], c=[] -> real 65, twin 66 |
| vericoding_da0657__solve | 53 | 47 | 0 | 6 | 0 | (real unproved) |  |
| vericoding_da0658__solve | 50 | 49 | 1 | 0 | 0 | 0 |  |
| vericoding_da0659__solve | 6 | 6 | 0 | 0 | 0 | 0 |  |
| vericoding_da0662__solve | 3 | 1 | 0 | 0 | 2 | 1 | wrong-var: `result := n;` -> `result := k;` at n=1, k=2 -> real 1, twin 2 |
| vericoding_da0663__solve | 16 | 16 | 0 | 0 | 0 | 0 |  |
| vericoding_da0664__solve | 24 | 24 | 0 | 0 | 0 | 0 |  |
| vericoding_da0665__solve | no-input | | | | | | |
| vericoding_da0667__solve | 22 | 22 | 0 | 0 | 0 | 0 |  |
| vericoding_da0668__solve | 87 | 84 | 3 | 0 | 0 | 0 |  |
| vericoding_da0671__solve | 38 | 36 | 2 | 0 | 0 | 0 |  |
| vericoding_da0672__solve | 26 | 25 | 1 | 0 | 0 | 0 |  |
| vericoding_da0674__solve | 14 | 14 | 0 | 0 | 0 | 0 |  |
| vericoding_da0675__solve | 59 | 59 | 0 | 0 | 0 | 0 |  |
| vericoding_da0676__solve | 10 | 10 | 0 | 0 | 0 | 0 |  |
| vericoding_db0006__lexicographicCompare | 45 | 42 | 1 | 2 | 0 | 0 |  |
| vericoding_db0020__computeExp | 23 | 17 | 0 | 6 | 0 | 0 |  |
| vericoding_db0020__modExpPow2_int | 17 | 17 | 0 | 0 | 0 | 0 |  |
| vericoding_db0034__modPowExec | 60 | 47 | 7 | 6 | 0 | 0 |  |
| vericoding_db0052__modExp_int | 17 | 17 | 0 | 0 | 0 | 0 |  |
| vericoding_db0052__pow | 23 | 17 | 0 | 6 | 0 | 0 |  |
| vericoding_db0053__modExp_int | 12 | 12 | 0 | 0 | 0 | 0 |  |
| vericoding_dd0008__getInsertIndex | 68 | 46 | 14 | 8 | 0 | 0 |  |
| vericoding_dd0040__query | 40 | 31 | 7 | 2 | 0 | 0 |  |
| vericoding_dd0041__queryFast | 12 | 8 | 4 | 0 | 0 | 0 |  |
| vericoding_dd0045__concat | 51 | 44 | 2 | 5 | 0 | 0 |  |
| vericoding_dd0050__binarySearch | 53 | 43 | 3 | 7 | 0 | 0 |  |
| vericoding_dd0052__calDiv | 25 | 15 | 10 | 0 | 0 | 0 |  |
| vericoding_dd0053__sum | 22 | 17 | 2 | 3 | 0 | 0 |  |
| vericoding_dd0054__canyonSearch | 106 | 79 | 15 | 12 | 0 | (real timeout) |  |
| vericoding_dd0058__double_array_elements | 20 | 18 | 0 | 2 | 0 | 0 |  |
| vericoding_dd0059__doubleQuadruple | 29 | 21 | 8 | 0 | 0 | 0 |  |
| vericoding_dd0066__isPalindrome | 31 | 24 | 5 | 2 | 0 | 0 |  |
| vericoding_dd0068__linearSearch | 16 | 11 | 3 | 2 | 0 | 0 |  |
| vericoding_dd0069__longestCommonPrefix | 34 | 31 | 1 | 2 | 0 | 0 |  |
| vericoding_dd0070__match | 28 | 25 | 1 | 2 | 0 | 0 |  |
| vericoding_dd0071__maxArray | 24 | 19 | 3 | 2 | 0 | 0 |  |
| vericoding_dd0075__multipleReturns | 33 | 25 | 8 | 0 | 0 | 0 |  |
| vericoding_dd0077__quotient | 51 | 35 | 8 | 8 | 0 | 0 |  |
| vericoding_dd0079__replace | 27 | 24 | 0 | 3 | 0 | 0 |  |
| vericoding_dd0080__m | 4 | 4 | 0 | 0 | 0 | 0 |  |
| vericoding_dd0081__reverse | 47 | 45 | 2 | 0 | 0 | 0 |  |
| vericoding_dd0085__swap | 25 | 15 | 10 | 0 | 0 | 0 |  |
| vericoding_dd0086__swapArithmetic | 25 | 15 | 10 | 0 | 0 | 0 |  |
| vericoding_dd0088__swap | 17 | 13 | 4 | 0 | 0 | 0 |  |
| vericoding_dd0089__swapSimultaneous | 25 | 15 | 10 | 0 | 0 | 0 |  |
| vericoding_dd0090__testArrayElements | 4 | 4 | 0 | 0 | 0 | 0 |  |
| vericoding_dd0091__triple | 6 | 6 | 0 | 0 | 0 | 0 |  |
| vericoding_dd0092__triple | 6 | 6 | 0 | 0 | 0 | 0 |  |
| vericoding_dd0093__triple | 6 | 6 | 0 | 0 | 0 | 0 |  |
| vericoding_dd0094__triple | 6 | 6 | 0 | 0 | 0 | 0 |  |
| vericoding_dd0096__updateElements | no-input | | | | | | |
| vericoding_dd0100__binarySearch | 53 | 42 | 5 | 6 | 0 | 0 |  |
| vericoding_dd0102__fibonacci1 | 66 | 60 | 3 | 3 | 0 | 0 |  |
| vericoding_dd0105__mpositive | 20 | 18 | 0 | 2 | 0 | (real unproved) |  |
| vericoding_dd0124__mfirstNegative | 42 | 30 | 4 | 3 | 5 | 1 | off-by-one#14: `i := 0;` -> `i := 1;` at v=[] -> real [False, 0], twin [False, 1] |
| vericoding_dd0130__mCountMin | 116 | 108 | 3 | 5 | 0 | (real unproved) |  |
| vericoding_dd0131__mPeekSum | 38 | 35 | 0 | 3 | 0 | 0 |  |
| vericoding_dd0133__binarySearchRec | 67 | 29 | 27 | 11 | 0 | 0 |  |
| vericoding_dd0144__barrier | 96 | 71 | 17 | 8 | 0 | (real unproved) |  |
| vericoding_dd0155__invertArray | 47 | 45 | 2 | 0 | 0 | 0 |  |
| vericoding_dd0167__longestPrefix | 27 | 25 | 0 | 2 | 0 | 0 |  |
| vericoding_dd0187__findPositionOfElement | 86 | 36 | 17 | 3 | 30 | 1 | off-by-one#6: `count := 0;` -> `count := 1;` at a=[], element=0, n1=0, s1=[] -> real [-1, 0], twin [-1, 1] |
| vericoding_dd0225__computePower | 25 | 22 | 0 | 3 | 0 | 0 |  |
| vericoding_dd0256__max | 20 | 15 | 5 | 0 | 0 | 0 |  |
| vericoding_dd0271__incrementArray | 20 | 18 | 0 | 2 | 0 | 0 |  |
| vericoding_dd0275__lookForMin | 28 | 22 | 2 | 3 | 1 | 1 | compare-flip#1: `if a[j] < a[m] {` -> `if a[j] <= a[m] {` at a=[0, 0], i=0 -> real 0, twin 1 |
| vericoding_dd0342__calcR | 40 | 34 | 3 | 3 | 0 | 0 |  |
| vericoding_dd0355__mod2 | 146 | 115 | 6 | 25 | 0 | (real timeout) |  |
| vericoding_dd0356__mod | 62 | 52 | 0 | 10 | 0 | (real unproved) |  |
| vericoding_dd0454__getmini | 26 | 22 | 2 | 2 | 0 | 0 |  |
| vericoding_dd0464__counting_bits | 50 | 36 | 10 | 2 | 2 | (real unproved) | off-by-one#12: `result := result[0 := 0];` -> `result := result[0 := 1];` at n=0 -> real [0], twin [1] |
| vericoding_dd0493__queryFast | 12 | 8 | 4 | 0 | 0 | 0 |  |
| vericoding_dd0508__mergeSimple | 159 | 32 | 88 | 0 | 39 | 0 | collapse-if: `if len(a1) + len(a2) == 0 {` -> `return b_out;` at a1=[0], a2=[0], start=0, end=1, b=[1] -> real [0], twin [1] |
| vericoding_dd0517__prodAndCount | 66 | 55 | 8 | 3 | 0 | (real unproved) |  |
| vericoding_dd0518__findAddends | 113 | 80 | 26 | 7 | 0 | (real unproved) |  |
| vericoding_dd0533__euclid | 4 | 4 | 0 | 0 | 0 | 0 |  |
| vericoding_dd0534__intDiv | 33 | 25 | 8 | 0 | 0 | 0 |  |
| vericoding_dd0537__noDups | 28 | 24 | 2 | 2 | 0 | 0 |  |
| vericoding_dd0539__reverse | 26 | 22 | 2 | 2 | 0 | 0 |  |
| vericoding_dd0580__appendArray | 51 | 44 | 2 | 5 | 0 | 0 |  |
| vericoding_dd0586__getEven | 29 | 27 | 0 | 2 | 0 | 0 |  |
| vericoding_dd0587__getTriple | 42 | 35 | 5 | 2 | 0 | 0 |  |
| vericoding_dd0611__maximum | 24 | 19 | 3 | 2 | 0 | 0 |  |
| vericoding_dd0634__expt | 28 | 23 | 0 | 5 | 0 | 0 |  |
| vericoding_dd0635__factorial | 24 | 19 | 2 | 3 | 0 | 0 |  |
| vericoding_dd0643__sharedElements | 35 | 24 | 0 | 2 | 9 | 1 | off-by-one#3: `while i_v4 < h` -> `while i_v4 < h + -1` at a=[0], b=[0] -> real [0], twin [] |
| vericoding_dd0646__triangularPrismVolume | 15 | 15 | 0 | 0 | 0 | 0 |  |
| vericoding_dd0653__containsSequence | 16 | 14 | 0 | 2 | 0 | 0 |  |
| vericoding_dd0654__allSequencesEqualLength | 30 | 25 | 2 | 3 | 0 | 0 |  |
| vericoding_dd0663__smallestListLength | 28 | 23 | 3 | 2 | 0 | 0 |  |
| vericoding_dd0667__isInteger | 20 | 17 | 1 | 2 | 0 | 0 |  |
| vericoding_dd0668__sumOfCommonDivisors | 12 | 7 | 1 | 0 | 4 | (real unproved) | wrong-var#4: `sum := sumOfCommonDivisorsUpTo(a, b, minVal);` -> `sum := sumOfCommonDivisorsUpTo(b, b, minVal);` at a=2147483647, b=2 -> real 1, twin 3 |
| vericoding_dd0669__multiply | 6 | 6 | 0 | 0 | 0 | 0 |  |
| vericoding_dd0678__pentagonPerimeter | 6 | 6 | 0 | 0 | 0 | 0 |  |
| vericoding_dd0679__minOfThree | 36 | 33 | 3 | 0 | 0 | 0 |  |
| vericoding_dd0680__replaceBlanksWithChar | 25 | 22 | 0 | 3 | 0 | 0 |  |
| vericoding_dd0682__cubeVolume | 6 | 6 | 0 | 0 | 0 | 0 |  |
| vericoding_dd0684__replaceLastElement | 13 | 13 | 0 | 0 | 0 | 0 |  |
| vericoding_dd0687__insertBeforeEach | 14 | 12 | 0 | 2 | 0 | 0 |  |
| vericoding_dd0689__elementWiseDivision | 20 | 17 | 1 | 2 | 0 | 0 |  |
| vericoding_dd0690__splitArray | 21 | 21 | 0 | 0 | 0 | 0 |  |
| vericoding_dd0696__subtractSequences | 21 | 18 | 1 | 2 | 0 | 0 |  |
| vericoding_dd0701__maxLengthList | 24 | 19 | 2 | 2 | 1 | 1 | compare-flip#1: `if len(lists[i]) > len(maxList) {` -> `if len(lists[i]) >= len(maxList) {` at lists=[[0], [1]] -> real [0], twin [1] |
| vericoding_dd0703__elementAtIndexAfterRotation | 9 | 3 | 6 | 0 | 0 | 0 |  |
| vericoding_dd0714__removeOddNumbers | 18 | 16 | 0 | 2 | 0 | 0 |  |
| vericoding_dd0716__extractRearChars | 22 | 20 | 0 | 2 | 0 | 0 |  |
| vericoding_dd0717__filterOddNumbers | 18 | 16 | 0 | 2 | 0 | 0 |  |
| vericoding_dd0722__lastDigit | 5 | 5 | 0 | 0 | 0 | 0 |  |
| vericoding_dd0723__findNegativeNumbers | 18 | 16 | 0 | 2 | 0 | 0 |  |
| vericoding_dd0724__cubeSurfaceArea | 8 | 8 | 0 | 0 | 0 | 0 |  |
| vericoding_dd0727__calculateLoss | 16 | 15 | 1 | 0 | 0 | 0 |  |
| vericoding_dd0729__monthHas31Days | 14 | 14 | 0 | 0 | 0 | 0 |  |
| vericoding_dd0730__minLengthSublist | 24 | 19 | 2 | 2 | 1 | 1 | compare-flip#1: `if len(s[i]) < len(minSublist) {` -> `if len(s[i]) <= len(minSublist) {` at s=[[0], [1]] -> real [0], twin [1] |
| vericoding_dd0732__getFirstElements | 18 | 16 | 0 | 2 | 0 | 0 |  |
| vericoding_dd0736__replaceChars | 30 | 25 | 3 | 2 | 0 | 0 |  |
| vericoding_dd0738__toLowercase | 27 | 25 | 0 | 2 | 0 | 0 |  |
| vericoding_dd0739__findOddNumbers | 25 | 23 | 0 | 2 | 0 | 0 |  |
| vericoding_dd0740__differenceSumCubesAndSumNumbers | 40 | 40 | 0 | 0 | 0 | 0 |  |
| vericoding_dd0741__toggleCase | 46 | 39 | 5 | 2 | 0 | 0 |  |
| vericoding_dd0742__splitStringIntoChars | 0 | 0 | 0 | 0 | 0 | 0 |  |
| vericoding_dd0749__factorialOfLastDigit | 6 | 6 | 0 | 0 | 0 | 0 |  |
| vericoding_dd0750__interleave | 26 | 21 | 3 | 2 | 0 | 0 |  |
| vericoding_dd0752__squarePyramidSurfaceArea | 14 | 14 | 0 | 0 | 0 | 0 |  |
| vericoding_dd0758__isArmstrong | 72 | 6 | 66 | 0 | 0 | 0 |  |
| vericoding_dd0762__lucidNumbers | 24 | 9 | 2 | 6 | 7 | 1 | compare-flip: `while i_v3 <= n` -> `while i_v3 < n` at n=0 -> real [0], twin [] |
| vericoding_dd0765__removeElement | 49 | 42 | 2 | 5 | 0 | 0 |  |
| vericoding_dd0767__elementWiseDivide | 20 | 17 | 1 | 2 | 0 | 0 |  |
| vericoding_dd0769__powerOfListElements | 26 | 23 | 0 | 3 | 0 | 0 |  |
| vericoding_dd0771__swapFirstAndLast | 24 | 23 | 1 | 0 | 0 | 0 |  |
| vericoding_dd0772__areaOfLargestTriangleInSemicircle | 4 | 4 | 0 | 0 | 0 | 0 |  |
| vericoding_dd0777__isBreakEven | 2 | 2 | 0 | 0 | 0 | 0 |  |
| vericoding_dd0778__nthNonagonalNumber | 15 | 15 | 0 | 0 | 0 | 0 |  |
| vericoding_dd0782__replaceWithColon | 26 | 24 | 0 | 2 | 0 | 0 |  |
| vericoding_dd0784__allCharactersSame | 30 | 23 | 4 | 3 | 0 | 0 |  |
| vericoding_dd0785__rotateRight | 32 | 24 | 3 | 5 | 0 | 0 |  |
| vericoding_dd0789__isDecimalWithTwoPrecision | 28 | 17 | 9 | 2 | 0 | 0 |  |
| vericoding_dd0791__isMonthWith30Days | 8 | 8 | 0 | 0 | 0 | 0 |  |
| vericoding_dd0794__sumOfFourthPowerOfOddNumbers | 47 | 41 | 0 | 6 | 0 | 0 |  |
| vericoding_dd0797__firstEvenOddIndices | 86 | 65 | 17 | 4 | 0 | 0 |  |
| vericoding_dd0799__isEvenAtIndexEven | 18 | 13 | 3 | 2 | 0 | 0 |  |
| vericoding_dd0800__countLists | 2 | 2 | 0 | 0 | 0 | 0 |  |
| vericoding_dd0804__countEqualNumbers | 38 | 36 | 2 | 0 | 0 | 0 |  |
| vericoding_dd0809__isSmaller | 23 | 20 | 1 | 2 | 0 | 0 |  |
| vericoding_dd0826__climbStairs | 71 | 62 | 3 | 6 | 0 | 0 |  |
| vericoding_dd0830__iterativeFactorial | 24 | 16 | 2 | 6 | 0 | 0 |  |
| vericoding_dd0831__fibonacciIterative | 72 | 66 | 3 | 3 | 0 | 0 |  |
| vericoding_dd0839__findMin | 28 | 22 | 2 | 3 | 1 | 1 | compare-flip#1: `if a[i] < a[minIndex] {` -> `if a[i] <= a[minIndex] {` at a=[0, 0], start=0 -> real 0, twin 1 |
| vericoding_dd0847__divMod1 | 51 | 35 | 8 | 8 | 0 | 0 |  |
| vericoding_dd0848__hoareTripleReqEns | 12 | 12 | 0 | 0 | 0 | 0 |  |
| vericoding_dd0873__intersperse | 32 | 29 | 0 | 3 | 0 | 0 |  |
| vericoding_dd0875__rolling_max | 34 | 30 | 1 | 3 | 0 | 0 |  |
| vericoding_dd0897__find_min_index | 36 | 7 | 29 | 0 | 0 | 0 |  |
| vericoding_dd0923__longestZero | 163 | 128 | 28 | 6 | 1 | (real timeout) | compare-flip#1: `if cur > best {` -> `if cur >= best {` at a=[0, 1, 0] -> real [1, 0], twin [1, 2] |
| vericoding_dh0005__insertDelimiter | 31 | 27 | 2 | 2 | 0 | 0 |  |
| vericoding_dh0008__sum_product | 55 | 45 | 8 | 2 | 0 | (real unproved) |  |
| vericoding_dh0011__string_xor | 25 | 22 | 1 | 2 | 0 | 0 |  |
| vericoding_dh0021__largest_divisor | 4 | 4 | 0 | 0 | 0 | 0 |  |
| vericoding_dh0024__remove_duplicates | 26 | 24 | 0 | 2 | 0 | 0 |  |
| vericoding_dh0026__concatenate | 2 | 2 | 0 | 0 | 0 | 0 |  |
| vericoding_dh0035__findMaxElement | 0 | 0 | 0 | 0 | 0 | (real unproved) |  |
| vericoding_dh0040__decode_cyclic | 55 | 47 | 3 | 2 | 3 | 0 | collapse-if#2: `if i_v3 % 3 == 1 {` -> `res := res + [s[i_v3 - 1]];` at s=[0, 1, 0] -> real [0, 0, 0], twin [0, 0, 1] |
| vericoding_dh0043__car_race_collision | 4 | 4 | 0 | 0 | 0 | 0 |  |
| vericoding_dh0044__incr_list | 18 | 16 | 0 | 2 | 0 | 0 |  |
| vericoding_dh0048__fib4 | 76 | 52 | 0 | 24 | 0 | (real timeout) |  |
| vericoding_dh0051__modp | 137 | 75 | 41 | 21 | 0 | (real unproved) |  |
| vericoding_dh0052__decode_shift | 14 | 11 | 1 | 2 | 0 | 0 |  |
| vericoding_dh0053__encode_shift | 14 | 11 | 1 | 2 | 0 | 0 |  |
| vericoding_dh0055__checkBelowThreshold | 22 | 19 | 0 | 3 | 0 | 0 |  |
| vericoding_dh0056__add | 4 | 4 | 0 | 0 | 0 | 0 |  |
| vericoding_dh0058__fib | 71 | 62 | 3 | 6 | 0 | 0 |  |
| vericoding_dh0063__sum_to_n | 11 | 11 | 0 | 0 | 0 | 0 |  |
| vericoding_dh0064__derivative | 34 | 30 | 2 | 2 | 0 | 0 |  |
| vericoding_dh0065__fibfib | 52 | 35 | 0 | 17 | 0 | 0 |  |
| vericoding_dh0069__extract_numbers_from_string_imperative | 69 | 61 | 4 | 4 | 0 | 0 |  |
| vericoding_dh0069__fruit_distribution | 6 | 6 | 0 | 0 | 0 | 0 |  |
| vericoding_dh0073__will_it_fly | 2 | 2 | 0 | 0 | 0 | 0 |  |
| vericoding_dh0074__smallest_change | 22 | 8 | 11 | 3 | 0 | (real unproved) |  |
| vericoding_dh0078__cube_root | 16 | 10 | 2 | 4 | 0 | 0 |  |
| vericoding_dh0079__is_cube | 31 | 23 | 3 | 5 | 0 | (real timeout) |  |
| vericoding_dh0085__starts_one_ends | 4 | 4 | 0 | 0 | 0 | (real unproved) |  |
| vericoding_dh0091__encrypt | 106 | 96 | 6 | 4 | 0 | 0 |  |
| vericoding_dh0096__skjkasdkd | 41 | 28 | 10 | 3 | 0 | (real unproved) |  |
| vericoding_dh0101__make_a_pile | 23 | 20 | 0 | 3 | 0 | 0 |  |
| vericoding_dh0102__chooseNum | 48 | 41 | 3 | 4 | 0 | 0 |  |
| vericoding_dh0103__rounded_avg | 133 | 117 | 16 | 0 | 0 | 0 |  |
| vericoding_dh0108__f | 37 | 33 | 1 | 3 | 0 | 0 |  |
| vericoding_dh0110__digitSum | 136 | 112 | 7 | 17 | 0 | (real unproved) |  |
| vericoding_dh0112__exchange | 21 | 21 | 0 | 0 | 0 | 0 |  |
| vericoding_dh0122__maximum | 19 | 16 | 0 | 3 | 0 | 0 |  |
| vericoding_dh0123__solution | 27 | 26 | 0 | 1 | 0 | 0 |  |
| vericoding_dh0125__get_odd_collatz | 0 | 0 | 0 | 0 | 0 | (real unproved) |  |
| vericoding_dh0127__next_odd_collatz_iter | 34 | 26 | 2 | 6 | 0 | 0 |  |
| vericoding_dh0133__tribonacci | 16 | 10 | 0 | 6 | 0 | (real timeout) |  |
| vericoding_dh0141__factorial | 34 | 24 | 4 | 6 | 0 | 0 |  |
| vericoding_dh0141__special_factorial | 35 | 24 | 6 | 5 | 0 | 0 |  |
| vericoding_dh0143__sum_squares | 18 | 16 | 0 | 2 | 0 | 0 |  |
| vericoding_dh0152__x_or_y | 12 | 12 | 0 | 0 | 0 | 0 |  |
| vericoding_dh0154__compare | 21 | 18 | 1 | 2 | 0 | 0 |  |
| vericoding_dh0157__even_odd_count | 23 | 15 | 8 | 0 | 0 | (real unproved) |  |
| vericoding_dj0004__myfun | 55 | 28 | 9 | 2 | 16 | 1 | off-by-one#1: `var total: int := 0;` -> `var total: int := -1;` at a=[0], sum=[0], n=1 -> real [0], twin [-1] |
| vericoding_dj0010__chooseOdd | 27 | 7 | 6 | 2 | 12 | 0 | collapse-if: `if v[i] % 2 == 1 {` -> `odd_index := i;` at v=[0, 1] -> real 1, twin 0 |
| vericoding_dj0014__myfun | 63 | 59 | 0 | 2 | 2 | 1 | wrong-operator#2: `a_out := a_out[i := a_out[i] + 1];` -> `a_out := a_out[i := a_out[i] - 1];` at a=[0, 1], n=2 -> real [0, 2], twin [0, 0] |
| vericoding_dj0015__myfun | 34 | 25 | 4 | 3 | 2 | 1 | collapse-if: `if a_out[i] > n {` -> `a_out := a_out[i := n];` at a=[0], n=1, m=0 -> real [0], twin [1] |
| vericoding_dj0016__fibonacci | 33 | 31 | 0 | 2 | 0 | (real timeout) |  |
| vericoding_dj0020__findMax | 24 | 19 | 3 | 2 | 0 | 0 |  |
| vericoding_dj0026__myfun | 55 | 29 | 9 | 2 | 15 | 1 | off-by-one#1: `var total: int := 0;` -> `var total: int := -1;` at a=[0], sum=[0], n=1 -> real [0], twin [-1] |
| vericoding_dj0027__myfun | 55 | 28 | 9 | 2 | 16 | 1 | off-by-one#1: `var total: int := 0;` -> `var total: int := -1;` at a=[0], sum=[0], n=1 -> real [0], twin [-1] |
| vericoding_dj0028__myfun | 55 | 28 | 9 | 2 | 16 | 1 | off-by-one#1: `var total: int := 0;` -> `var total: int := -1;` at a=[0], sum=[0], n=1 -> real [0], twin [-1] |
| vericoding_dj0037__myfun | 35 | 26 | 6 | 3 | 0 | 0 |  |
| vericoding_dj0038__myfun | 9 | 8 | 1 | 0 | 0 | 0 |  |
| vericoding_dj0039__myfun | 9 | 8 | 1 | 0 | 0 | 0 |  |
| vericoding_dj0040__myfun | 9 | 8 | 1 | 0 | 0 | 0 |  |
| vericoding_dj0041__myfun | 9 | 8 | 1 | 0 | 0 | 0 |  |
| vericoding_dj0044__myfun | 9 | 8 | 1 | 0 | 0 | 0 |  |
| vericoding_dj0045__myfun | 35 | 26 | 6 | 3 | 0 | 0 |  |
| vericoding_dj0048__myfun | 9 | 8 | 1 | 0 | 0 | 0 |  |
| vericoding_dj0057__isNonPrime | 22 | 17 | 1 | 4 | 0 | (real unproved) |  |
| vericoding_dj0058__squareNums | 24 | 20 | 2 | 2 | 0 | 0 |  |
| vericoding_dj0068__countIdenticalPosition | 42 | 35 | 5 | 2 | 0 | (real unproved) |  |
| vericoding_dj0072__replaceBlanksWithChars | 25 | 22 | 0 | 3 | 0 | 0 |  |
| vericoding_dj0073__replaceLastElement | 63 | 56 | 2 | 5 | 0 | 0 |  |
| vericoding_dj0075__insertBeforeEach | 44 | 39 | 2 | 3 | 0 | 0 |  |
| vericoding_dj0076__elementWiseDivision | 27 | 21 | 4 | 2 | 0 | 0 |  |
| vericoding_dj0077__splitArray | 17 | 17 | 0 | 0 | 0 | 0 |  |
| vericoding_dj0078__elementWiseSubtract | 28 | 22 | 4 | 2 | 0 | 0 |  |
| vericoding_dj0079__elementWiseSubtract | 28 | 22 | 4 | 2 | 0 | 0 |  |
| vericoding_dj0080__allElementsEquals | 20 | 17 | 0 | 3 | 0 | 0 |  |
| vericoding_dj0088__isGreater | 22 | 19 | 0 | 3 | 0 | 0 |  |
| vericoding_dj0089__findNegativeNumbers | 22 | 20 | 0 | 2 | 0 | 0 |  |
| vericoding_dj0099__findOddNumbers | 23 | 21 | 0 | 2 | 0 | 0 |  |
| vericoding_dj0105__interleave | 62 | 47 | 13 | 2 | 0 | 0 |  |
| vericoding_dj0110__primeNum | 22 | 17 | 1 | 4 | 0 | (real unproved) |  |
| vericoding_dj0111__removeKthElement | 14 | 14 | 0 | 0 | 0 | 0 |  |
| vericoding_dj0113__elementWiseDivide | 27 | 21 | 4 | 2 | 0 | 0 |  |
| vericoding_dj0116__reverseToK | 0 | 0 | 0 | 0 | 0 | 0 |  |
| vericoding_dj0128__sum | 18 | 16 | 0 | 2 | 0 | (real unproved) |  |
| vericoding_dj0130__findFirstOdd | 25 | 21 | 0 | 2 | 2 | 1 | off-by-one#12: `index := -(1);` -> `index := -(2);` at arr=[] -> real -1, twin -2 |
| vericoding_dj0132__isSmaller | 28 | 23 | 3 | 2 | 0 | 0 |  |
| vericoding_dj0133__getElementCheckProperty | 2 | 2 | 0 | 0 | 0 | (real unproved) |  |
| vericoding_dj0135__arithmeticWeird | 4 | 2 | 0 | 0 | 2 | 1 | off-by-one#1: `result := 9;` -> `result := 8;` at  -> real 9, twin 8 |
| vericoding_dj0136__arrayAppend | 0 | 0 | 0 | 0 | 0 | 0 |  |
| vericoding_dj0137__arrayConcat | 2 | 2 | 0 | 0 | 0 | 0 |  |
| vericoding_dj0142__binarySearchRecursive | 54 | 23 | 19 | 12 | 0 | 0 |  |
| vericoding_dj0143__cubes | 29 | 23 | 4 | 2 | 0 | 0 |  |
| vericoding_dj0148__intersperse | 26 | 23 | 0 | 3 | 0 | 0 |  |
| vericoding_dj0156__removeElement | 14 | 14 | 0 | 0 | 0 | 0 |  |
| vericoding_dj0158__replace | 30 | 25 | 1 | 4 | 0 | 0 |  |
| vericoding_dj0160__reverse | 20 | 18 | 0 | 2 | 0 | 0 |  |
| vericoding_dj0161__rollingMax | 35 | 31 | 2 | 2 | 0 | 0 |  |
| vericoding_dj0170__binarySearchExists | 112 | 63 | 32 | 9 | 8 | 1 | off-by-one#14: `index := 0;` -> `index := 1;` at w=[], m=0, target=0 -> real [False, 0], twin [False, 1] |
| vericoding_ds0010__clip | 60 | 51 | 5 | 4 | 0 | 0 |  |
| vericoding_ds0015__cumProd | 36 | 32 | 2 | 2 | 0 | 0 |  |
| vericoding_ds0016__cumSum | 34 | 30 | 2 | 2 | 0 | 0 |  |
| vericoding_ds0020__floorDivide | 27 | 21 | 4 | 2 | 0 | 0 |  |
| vericoding_ds0026__invert | 31 | 26 | 2 | 3 | 0 | 0 |  |
| vericoding_ds0029__lcmInt | 4 | 4 | 0 | 0 | 0 | 0 |  |
| vericoding_ds0033__max | 24 | 19 | 3 | 2 | 0 | 0 |  |
| vericoding_ds0041__power | 26 | 20 | 4 | 2 | 0 | 0 |  |
| vericoding_ds0046__right_shift | 26 | 20 | 4 | 2 | 0 | 0 |  |
| vericoding_ds0049__sign | 42 | 38 | 2 | 2 | 0 | 0 |  |
| vericoding_ds0051__square | 24 | 20 | 2 | 2 | 0 | 0 |  |
| vericoding_ds0052__subtract | 28 | 22 | 4 | 2 | 0 | 0 |  |
| vericoding_ds0053__sumArray | 64 | 42 | 20 | 2 | 0 | 0 |  |
| vericoding_dt0088__leftShift | 32 | 22 | 8 | 2 | 0 | 0 |  |
| vericoding_dt0257__bitwiseNot | 24 | 22 | 0 | 2 | 0 | 0 |  |
| vericoding_dt0258__numpyBitwiseOr | real-violates-spec | | | | | | |
| vericoding_dt0555__insertSorted | 59 | 46 | 11 | 2 | 0 | 0 |  |
| vericoding_dt0630__stringsMod | 31 | 28 | 1 | 2 | 0 | 0 |  |
| vericoding_dt0631__multiply | 16 | 14 | 0 | 2 | 0 | (real unproved) |  |
| vericoding_dt0662__ntypes | 2 | 2 | 0 | 0 | 0 | 0 |  |
| vericoding_dv0008__countSumDivisibleBy | 32 | 11 | 0 | 5 | 16 | 1 | collapse-if: `if isSumDivisibleBy(i, d) {` -> `result := result + 1;` at n=1, d=2 -> real 0, twin 1 |
| vericoding_dv0015__insertionSort | 6 | 4 | 2 | 0 | 0 | 0 |  |
| vericoding_dv0017__isArmstrong | 6 | 6 | 0 | 0 | 0 | 0 |  |
| vericoding_dv0038__maxOfList | 24 | 19 | 3 | 2 | 0 | 0 |  |
| vericoding_dv0039__maxOfList | 24 | 19 | 3 | 2 | 0 | 0 |  |
| vericoding_dv0042__maxStrength | 24 | 9 | 3 | 2 | 10 | 1 | collapse-if: `if nums[i_v] > result {` -> `result := nums[i_v];` at nums=[1, 0] -> real 1, twin 0 |
| vericoding_dv0057__nthUglyNumber | 177 | 1 | 48 | 51 | 77 | 1 | collapse-if: `if candidate == 1 {` -> `count := count + 1;` at n=7 -> real 8, twin 7 |
| vericoding_dv0061__rain | 56 | 16 | 12 | 5 | 23 | 1 | negate-cond#1: `result := result + water;` -> `} else {` at heights=[1, 0, 1] -> real 1, twin 0 |
| vericoding_dv0062__removeDuplicates | 54 | 28 | 2 | 4 | 20 | 1 | collapse-if: `if len(nums) == 0 {` -> `result := 0;` at nums=[0] -> real 1, twin 0 |
| vericoding_dv0068__searchInsert | 53 | 42 | 5 | 6 | 0 | 0 |  |
| vericoding_dv0069__semiOrderedPermutation | 135 | 16 | 27 | 4 | 88 | 1 | collapse-if#1: `if nums[i] == 1 {` -> `pos1 := i;` at nums=[0, 0] -> real 0, twin 1 |
| vericoding_dv0073__solution | 27 | 9 | 0 | 2 | 16 | 0 | boundary-swap: `while i_v2 < len(nums)` -> `while len(nums) < i_v2` at nums=[1] -> real 1, twin 0 |
| vericoding_dv0076__trapRainWater | 68 | 10 | 18 | 5 | 35 | 0 | collapse-if: `if len(height) <= 2 {` -> `return result;` at height=[1, 0, 1] -> real 1, twin 0 |
| vericoding_dv0079__twoSum | 67 | 50 | 12 | 5 | 0 | 0 |  |
| vericoding_dv0084__kthElementImpl | 6 | 6 | 0 | 0 | 0 | 0 |  |
| vericoding_dv0085__multiply | 6 | 6 | 0 | 0 | 0 | 0 |  |
| vericoding_dv0086__minOfThree | 44 | 36 | 8 | 0 | 0 | 0 |  |
| vericoding_dv0090__isGreater | 22 | 19 | 0 | 3 | 0 | 0 |  |
| vericoding_dv0094__containsZ | 22 | 20 | 0 | 2 | 0 | 0 |  |
| vericoding_dv0097__toLowercase | 20 | 18 | 0 | 2 | 0 | 0 |  |
| vericoding_dv0104__firstEvenOddDifference | 78 | 68 | 6 | 4 | 0 | 0 |  |
| vericoding_dv0111__toUppercase | 34 | 31 | 0 | 3 | 0 | 0 |  |
| vericoding_dv0112__swapFirstAndLast | 24 | 24 | 0 | 0 | 0 | 0 |  |
| vericoding_dv0117__findFirstOccurrence | 79 | 56 | 10 | 11 | 2 | 0 | off-by-one#2: `result := -(1);` -> `result := -(2);` at arr=[], target=0 -> real -1, twin -2 |
| vericoding_dv0118__allCharactersSame | 24 | 18 | 4 | 2 | 0 | 0 |  |
| vericoding_dv0131__binarySearchLoop | 59 | 34 | 20 | 5 | 0 | 0 |  |
| vericoding_dv0135__compare | 2 | 2 | 0 | 0 | 0 | 0 |  |
| vericoding_dv0138__doubleArrayElements | 18 | 16 | 0 | 2 | 0 | 0 |  |
| vericoding_dv0139__doubleQuadruple | 9 | 9 | 0 | 0 | 0 | 0 |  |
| vericoding_dv0149__linearSearch | 16 | 10 | 4 | 2 | 0 | (real unproved) |  |
| vericoding_dv0152__append | 31 | 26 | 2 | 3 | 0 | 0 |  |
| vericoding_dv0153__matchStrings | 28 | 25 | 1 | 2 | 0 | 0 |  |
| vericoding_dv0158__multipleReturns | 9 | 9 | 0 | 0 | 0 | 0 |  |
| vericoding_dv0162__removeFront | 6 | 6 | 0 | 0 | 0 | 0 |  |
| vericoding_dv0163__concat | 2 | 2 | 0 | 0 | 0 | 0 |  |
| vericoding_dv0164__replace | 27 | 24 | 0 | 3 | 0 | 0 |  |
| vericoding_dv0165__reverse | 26 | 22 | 2 | 2 | 0 | 0 |  |
| vericoding_dv0171__swap | 3 | 3 | 0 | 0 | 0 | 0 |  |
| vericoding_dv0172__swapArithmetic | 42 | 36 | 6 | 0 | 0 | 0 |  |
| vericoding_dv0173__swapBitvectors | 3 | 3 | 0 | 0 | 0 | 0 |  |
| vericoding_dv0176__swapSimultaneous | 3 | 3 | 0 | 0 | 0 | 0 |  |
| vericoding_dv0177__testArrayElements | 16 | 16 | 0 | 0 | 0 | 0 |  |
| vericoding_dv0178__triple | 6 | 6 | 0 | 0 | 0 | 0 |  |
| vericoding_dv0179__triple | 6 | 6 | 0 | 0 | 0 | 0 |  |
| vericoding_dv0180__triple | 6 | 6 | 0 | 0 | 0 | 0 |  |
| vericoding_dv0181__triple | 6 | 6 | 0 | 0 | 0 | 0 |  |
| vericoding_dv0183__update_elements | no-input | | | | | | |
