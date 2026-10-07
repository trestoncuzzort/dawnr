# The 14 Verus-proved survivors, read by hand

In `t/AUDIT-VERICODING-VERUS.md`, Verus proves the real solution and a one-edit program that computes something different at a ground input, against the same specification, in 14 tasks. In a vericoding benchmark a task is solved by any program the kernel verifies, so each survivor is a wrong solution that counts. Each was read against the task's name and solution (2026-10-07):

- **gap** (13): the specification admits a result that is wrong for the task;
- **latitude** (1): the specification deliberately allows several answers.

The APPS-derived tasks (`va`) state only that the output is well formed. Two of them, va0216 and va0654, are solved by a constant. The NumPy-derived ones (`vt`) state mostly the output's length.

| class | task | why | the proved survivor: change at input |
|---|---|---|---|
| gap | vericoding_va0074__min_repunit_sum | valid_output says only that n > 0 gives a positive result: 2 passes where 1 is the answer | off-by-one#4: `result := 1;` -> `result := 2;` at n=1 -> real 1, twin 2 |
| gap | vericoding_va0216__solve | any of R, P, S passes (valid_rps_char): a constant program solves it | off-by-one: `result := 82;` -> `result := 83;` at n=1, k=0, s=[82] -> real 82, twin 83 |
| gap | vericoding_va0237__solve | result >= 0 only | off-by-one: `var r: int := 0;` -> `var r: int := 1;` at n=1, lights=[1, 1] -> real 0, twin 1 |
| gap | vericoding_va0290__solve | any non-empty string of digits passes (valid_output) | off-by-one: `result_1 := result_1 + [48];` -> `result_1 := result_1 + [49];` at stdin_input=[10] -> real [48], twin [49] |
| gap | vericoding_va0582__solve_core | 0 <= result <= n only | off-by-one: `var res: int := 0;` -> `var res: int := 1;` at n=1, a=1, b=1, k=0, h=[1] -> real 0, twin 1 |
| gap | vericoding_va0654__solve | any of A, B, C passes (valid_winner): a constant program solves it | off-by-one: `result := 65;` -> `result := 66;` at a=[], b=[], c=[] -> real 65, twin 66 |
| gap | vericoding_vd0509__max | result >= every element; the maximum is not required | wrong-constant#2: `result := max_val;` -> `result := max_val + 1;` at a=[0] -> real 0, twin 1 |
| gap | vericoding_vt0025__logspace | length and positivity only; the values are free | off-by-one#2: `v := v + [1];` -> `v := v + [2];` at start=0, stop=0, endpoint=False, base=2, num=1 -> real [1], twin [2] |
| gap | vericoding_vt0099__npy_loge10 | brackets the constant between 2 and 3; either passes | off-by-one: `result := 2;` -> `result := 3;` at  -> real 2, twin 3 |
| gap | vericoding_vt0329__log | length only | off-by-one#4: `r := r + [0];` -> `r := r + [1];` at x=[1] -> real [0], twin [1] |
| gap | vericoding_vt0362__spacing | length and positivity only | off-by-one#2: `y := y + [1];` -> `y := y + [2];` at x=[0] -> real [1], twin [2] |
| gap | vericoding_vt0496__legmul | length only | off-by-one#4: `res := res + [0];` -> `res := res + [1];` at c1=[0], c2=[0] -> real [0], twin [1] |
| gap | vericoding_vt0594__nanpercentile | any value comparable with each element passes (a tautology) unless the sequence has one element | collapse-if#1: `if len(a) == 1 {` -> `result := a[0];` at a=[1, 0], q=0 -> real 0, twin 1 |
| latitude | vericoding_vd0432__find_min | ties: any index of a minimum | compare-flip#1: `if a[i] < a[min_idx] {` -> `if a[i] <= a[min_idx] {` at a=[0, 0], lo=0 -> real 0, twin 1 |
