# Specification audit

Every one-edit mutant of each body, classed by the interpreter over the task's bounded domain (t/audit.py): **killed** (the spec rejects its result somewhere), **same** (computes the same everywhere), **diverges** (runs out of steps where the real body ends), **survivor** (computes something different, and the spec accepts it everywhere).

- tasks: 16; audited: 16; not audited: none
- behaviour-changing mutants the specs kill: 457 of 457 (100.0%)
- tasks whose spec admits a survivor: 0 of 16
- framac: real body verified in 13 of 16; of those, a survivor proved too (a wrong program with a proof) in 0

| task | mutants | killed | same | diverges | survivors | proved by the kernel | a survivor: change at input |
|---|---|---|---|---|---|---|---|
| acsl_accumulate__accumulate | 30 | 26 | 0 | 4 | 0 | 0 |  |
| acsl_adjacent_find__adjacent_find | 38 | 34 | 2 | 2 | 0 | 0 |  |
| acsl_clamp__clamp | 18 | 16 | 2 | 0 | 0 | 0 |  |
| acsl_count__count | 38 | 35 | 0 | 3 | 0 | 0 |  |
| acsl_find2__find2 | 25 | 22 | 0 | 3 | 0 | 0 |  |
| acsl_find3__find3 | 25 | 22 | 0 | 3 | 0 | (real timeout) |  |
| acsl_find__find | 25 | 22 | 0 | 3 | 0 | 0 |  |
| acsl_find_if_not__find_if_not | 25 | 22 | 0 | 3 | 0 | (real timeout) |  |
| acsl_find_last__find_last | 34 | 30 | 0 | 4 | 0 | 0 |  |
| acsl_inner_product__inner_product | 39 | 32 | 3 | 4 | 0 | 0 |  |
| acsl_is_heap_until__is_heap_until | 46 | 43 | 0 | 3 | 0 | 0 |  |
| acsl_is_sorted_until__is_sorted_until | 28 | 26 | 0 | 2 | 0 | (real timeout) |  |
| acsl_max_element2__max_element2 | 42 | 35 | 4 | 3 | 0 | 0 |  |
| acsl_max_element__max_element | 42 | 35 | 4 | 3 | 0 | 0 |  |
| acsl_min_element__min_element | 42 | 35 | 4 | 3 | 0 | 0 |  |
| acsl_mismatch__mismatch | 26 | 22 | 2 | 2 | 0 | 0 |  |
