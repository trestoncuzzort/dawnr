# Specification audit

Every one-edit mutant of each body, classed by the interpreter over the task's bounded domain (t/audit.py): **killed** (the spec rejects its result somewhere), **same** (computes the same everywhere), **diverges** (runs out of steps where the real body ends), **survivor** (computes something different, and the spec accepts it everywhere).

- tasks: 66; audited: 63; not audited: 3 no-input
- behaviour-changing mutants the specs kill: 1369 of 1414 (96.8%)
- tasks whose spec admits a survivor: 20 of 63
- verus: real body verified in 55 of 63; of those, a survivor proved too (a wrong program with a proof) in 14

| task | mutants | killed | same | diverges | survivors | proved by the kernel | a survivor: change at input |
|---|---|---|---|---|---|---|---|
| vericoding_va0074__min_repunit_sum | 12 | 10 | 0 | 0 | 2 | 1 | off-by-one#4: `result := 1;` -> `result := 2;` at n=1 -> real 1, twin 2 |
| vericoding_va0079__solve | 14 | 13 | 0 | 0 | 1 | 0 | wrong-var#3: `result := r;` -> `result := s;` at s=[0, 0] -> real [0], twin [0, 0] |
| vericoding_va0080__solve | 45 | 21 | 24 | 0 | 0 | 0 |  |
| vericoding_va0085__find_minimum_total_distance | 90 | 75 | 15 | 0 | 0 | 0 |  |
| vericoding_va0100__solve | 4 | 4 | 0 | 0 | 0 | 0 |  |
| vericoding_va0123__solve | 37 | 17 | 20 | 0 | 0 | (real unproved) |  |
| vericoding_va0216__solve | 4 | 2 | 0 | 0 | 2 | 1 | off-by-one: `result := 82;` -> `result := 83;` at n=1, k=0, s=[82] -> real 82, twin 83 |
| vericoding_va0237__solve | 7 | 3 | 0 | 0 | 4 | 1 | off-by-one: `var r: int := 0;` -> `var r: int := 1;` at n=1, lights=[1, 1] -> real 0, twin 1 |
| vericoding_va0253__solve | 56 | 19 | 37 | 0 | 0 | 0 |  |
| vericoding_va0290__solve | 4 | 3 | 0 | 0 | 1 | 1 | off-by-one: `result_1 := result_1 + [48];` -> `result_1 := result_1 + [49];` at stdin_input=[10] -> real [48], twin [49] |
| vericoding_va0351__solve | no-input | | | | | | |
| vericoding_va0353__solve | 1 | 0 | 1 | 0 | 0 | 0 |  |
| vericoding_va0363__capitalize_first_letter | 48 | 36 | 12 | 0 | 0 | 0 |  |
| vericoding_va0399__solve | 62 | 14 | 48 | 0 | 0 | 0 |  |
| vericoding_va0405__solve | no-input | | | | | | |
| vericoding_va0410__solve | 11 | 5 | 6 | 0 | 0 | 0 |  |
| vericoding_va0429__solve | 119 | 66 | 53 | 0 | 0 | 0 |  |
| vericoding_va0445__solve | 4 | 2 | 0 | 0 | 2 | 0 | off-by-one: `result := 0;` -> `result := 1;` at n=1, p=2, s=[48] -> real 0, twin 1 |
| vericoding_va0476__solve | 9 | 6 | 0 | 0 | 3 | (real unproved) | wrong-var: `years := years_out;` -> `years := x;` at x=101 -> real 1, twin 101 |
| vericoding_va0482__solve | 23 | 18 | 2 | 3 | 0 | 0 |  |
| vericoding_va0530__solve | 73 | 69 | 4 | 0 | 0 | 0 |  |
| vericoding_va0550__solve | no-input | | | | | | |
| vericoding_va0582__solve_core | 10 | 6 | 0 | 0 | 4 | 1 | off-by-one: `var res: int := 0;` -> `var res: int := 1;` at n=1, a=1, b=1, k=0, h=[1] -> real 0, twin 1 |
| vericoding_va0654__solve | 4 | 2 | 0 | 0 | 2 | 1 | off-by-one: `result := 65;` -> `result := 66;` at a=[], b=[], c=[] -> real 65, twin 66 |
| vericoding_va0659__solve | 30 | 25 | 0 | 5 | 0 | 0 |  |
| vericoding_vd0056__copy | 87 | 57 | 28 | 2 | 0 | 0 |  |
| vericoding_vd0087__swap_bitvectors | 25 | 15 | 10 | 0 | 0 | 0 |  |
| vericoding_vd0287__reverse | 25 | 23 | 0 | 2 | 0 | 0 |  |
| vericoding_vd0367__yarra | 30 | 28 | 0 | 2 | 0 | 0 |  |
| vericoding_vd0432__find_min | 39 | 30 | 3 | 4 | 2 | 1 | compare-flip#1: `if a[i] < a[min_idx] {` -> `if a[i] <= a[min_idx] {` at a=[0, 0], lo=0 -> real 0, twin 1 |
| vericoding_vd0483__maxArrayReverse | 32 | 26 | 3 | 3 | 0 | 0 |  |
| vericoding_vd0509__max | 32 | 25 | 3 | 3 | 1 | 1 | wrong-constant#2: `result := max_val;` -> `result := max_val + 1;` at a=[0] -> real 0, twin 1 |
| vericoding_vd0588__reverse | 29 | 27 | 0 | 2 | 0 | 0 |  |
| vericoding_vd0674__count_arrays | 2 | 2 | 0 | 0 | 0 | 0 |  |
| vericoding_vd0700__all_elements_equal | 20 | 17 | 0 | 3 | 0 | 0 |  |
| vericoding_vd0721__is_greater | 22 | 19 | 0 | 3 | 0 | 0 |  |
| vericoding_vd0729__month_has_31_days | 14 | 14 | 0 | 0 | 0 | 0 |  |
| vericoding_vh0107__reverse | 35 | 33 | 0 | 2 | 0 | 0 |  |
| vericoding_vj0058__square_nums | 23 | 20 | 0 | 3 | 0 | 0 |  |
| vericoding_vj0162__smallest_list_length | 70 | 55 | 10 | 5 | 0 | (real unproved) |  |
| vericoding_vj0164__string_xor | 53 | 47 | 4 | 2 | 0 | 0 |  |
| vericoding_vt0014__frombuffer | 29 | 20 | 7 | 2 | 0 | 0 |  |
| vericoding_vt0025__logspace | 9 | 8 | 0 | 0 | 1 | 1 | off-by-one#2: `v := v + [1];` -> `v := v + [2];` at start=0, stop=0, endpoint=False, base=2, num=1 -> real [1], twin [2] |
| vericoding_vt0029__ones | 17 | 14 | 0 | 3 | 0 | 0 |  |
| vericoding_vt0095__npy_2_pi | 4 | 4 | 0 | 0 | 0 | 0 |  |
| vericoding_vt0099__npy_loge10 | 4 | 2 | 0 | 0 | 2 | 1 | off-by-one: `result := 2;` -> `result := 3;` at  -> real 2, twin 3 |
| vericoding_vt0106__true_ | 0 | 0 | 0 | 0 | 0 | 0 |  |
| vericoding_vt0165__argmax | 34 | 29 | 2 | 3 | 0 | (real unproved) |  |
| vericoding_vt0166__argmin | 34 | 29 | 2 | 3 | 0 | (real unproved) |  |
| vericoding_vt0233__matrix_power | 0 | 0 | 0 | 0 | 0 | 0 |  |
| vericoding_vt0297__numpy_cos | 29 | 24 | 0 | 3 | 2 | (real unproved) | off-by-one#10: `var y: int := if xi == 0 then 1 else 0;` -> `var y: int := if xi == 0 then 1 else 1;` at x=[1] -> real [0], twin [1] |
| vericoding_vt0329__log | 17 | 11 | 0 | 3 | 3 | 1 | off-by-one#4: `r := r + [0];` -> `r := r + [1];` at x=[1] -> real [0], twin [1] |
| vericoding_vt0357__sign | 36 | 32 | 0 | 4 | 0 | 0 |  |
| vericoding_vt0360__sinc | 28 | 23 | 1 | 2 | 2 | (real unproved) | off-by-one#10: `var val: int := if x[i_v] == 0 then 1 else 0;` -> `var val: int := if x[i_v] == 0 then 1 else 1;` at x=[1] -> real [0], twin [1] |
| vericoding_vt0362__spacing | 10 | 9 | 0 | 0 | 1 | 1 | off-by-one#2: `y := y + [1];` -> `y := y + [2];` at x=[0] -> real [1], twin [2] |
| vericoding_vt0496__legmul | 50 | 40 | 0 | 6 | 4 | 1 | off-by-one#4: `res := res + [0];` -> `res := res + [1];` at c1=[0], c2=[0] -> real [0], twin [1] |
| vericoding_vt0557__numpy_argmin | 84 | 60 | 19 | 5 | 0 | (real unproved) |  |
| vericoding_vt0567__nanargmax | 34 | 29 | 2 | 3 | 0 | 0 |  |
| vericoding_vt0568__nanargmin | 34 | 29 | 2 | 3 | 0 | 0 |  |
| vericoding_vt0580__numpy_cov | 40 | 31 | 0 | 8 | 1 | 0 | off-by-one#8: `row := row + [0];` -> `row := row + [1];` at m=[[0]] -> real [[0]], twin [[1]] |
| vericoding_vt0590__nanmax | 32 | 26 | 3 | 3 | 0 | 0 |  |
| vericoding_vt0594__nanpercentile | 20 | 14 | 1 | 0 | 5 | 1 | collapse-if#1: `if len(a) == 1 {` -> `result := a[0];` at a=[1, 0], q=0 -> real 0, twin 1 |
| vericoding_vv0064__reverse_string | 39 | 36 | 0 | 3 | 0 | 0 |  |
| vericoding_vv0171__swap | 25 | 15 | 10 | 0 | 0 | 0 |  |
| vericoding_vv0173__swap_bitvectors | 25 | 15 | 10 | 0 | 0 | 0 |  |
| vericoding_vv0176__swap_simultaneous | 25 | 15 | 10 | 0 | 0 | 0 |  |
