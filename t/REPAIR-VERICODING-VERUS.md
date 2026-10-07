# Specification repair

For each task whose spec admits a survivor (`t/audit.py`), the clauses `t/contract_repair.py` adds: each holds for the real program at every domain point, and together they kill every survivor they can. **after** is the repaired task's own audit, from scratch.

- tasks with survivors: 20; repaired to zero survivors: 4
- refused because the real body never reads its parameters: 6
- verus: repaired contract proved for the real body, twin refuted: 3 of 4

| task | survivors before | after | verus real / twin | clauses added |
|---|---|---|---|---|
| vericoding_va0074__min_repunit_sum | 2 | 0 | verified / refuted | `result <= 1` |
| vericoding_va0079__solve | 1 | 1 |  /  | (none found) |
| vericoding_va0216__solve | 2 | 2 |  /  | (none found) |
| vericoding_va0237__solve | 4 | 4 |  /  | (none found) |
| vericoding_va0290__solve | 1 | 1 |  /  | (none found) |
| vericoding_va0445__solve | 2 | 2 |  /  | (none found) |
| vericoding_va0476__solve | 3 | 3 | unproved / refuted | `years < x` |
| vericoding_va0582__solve_core | 4 | 4 |  /  | (none found) |
| vericoding_va0654__solve | 2 | 2 |  /  | (none found) |
| vericoding_vd0432__find_min | 2 | 2 |  /  | (none found) |
| vericoding_vd0509__max | 1 | 0 | verified / refuted | `exists j in [0, len(a)) . a[j] == result` |
| vericoding_vt0025__logspace | 1 | 0 | unproved / refuted | `result == [1] or result == [1, 1]` |
| vericoding_vt0099__npy_loge10 | 2 | 0 | verified / refuted | `result == 2` |
| vericoding_vt0297__numpy_cos | 2 | 2 |  /  | (none found) |
| vericoding_vt0329__log | 3 | 3 |  /  | (none found) |
| vericoding_vt0360__sinc | 2 | 2 |  /  | (none found) |
| vericoding_vt0362__spacing | 1 | 1 |  /  | (none found) |
| vericoding_vt0496__legmul | 4 | 4 |  /  | (none found) |
| vericoding_vt0580__numpy_cov | 1 | 1 |  /  | (none found) |
| vericoding_vt0594__nanpercentile | 5 | 5 |  /  | (none found) |
