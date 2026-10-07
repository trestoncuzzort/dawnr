# Specification audit

Every one-edit mutant of each body, classed by the interpreter over the task's bounded domain (t/audit.py): **killed** (the spec rejects its result somewhere), **same** (computes the same everywhere), **diverges** (runs out of steps where the real body ends), **survivor** (computes something different, and the spec accepts it everywhere).

- tasks: 16; audited: 16; not audited: none
- behaviour-changing mutants the specs kill: 213 of 213 (100.0%)
- tasks whose spec admits a survivor: 0 of 16
- lean: real body verified in 12 of 16; of those, a survivor proved too (a wrong program with a proof) in 0

| task | mutants | killed | same | diverges | survivors | proved by the kernel | a survivor: change at input |
|---|---|---|---|---|---|---|---|
| vericoding_la0018__solve | 2 | 2 | 0 | 0 | 0 | (real unproved) |  |
| vericoding_la0026__solve | 20 | 20 | 0 | 0 | 0 | 0 |  |
| vericoding_la0046__solve | 2 | 2 | 0 | 0 | 0 | 0 |  |
| vericoding_la0099__solve | 104 | 102 | 2 | 0 | 0 | 0 |  |
| vericoding_la0110__solve | 6 | 6 | 0 | 0 | 0 | 0 |  |
| vericoding_la0113__solve | 2 | 2 | 0 | 0 | 0 | (real unproved) |  |
| vericoding_la0308__solve | 0 | 0 | 0 | 0 | 0 | 0 |  |
| vericoding_la0368__solve | 2 | 2 | 0 | 0 | 0 | (real unproved) |  |
| vericoding_la0484__solve | 0 | 0 | 0 | 0 | 0 | 0 |  |
| vericoding_la0585__solve | 2 | 2 | 0 | 0 | 0 | (real unproved) |  |
| vericoding_ld0178__calcPower | 6 | 6 | 0 | 0 | 0 | 0 |  |
| vericoding_ld0794__sumOfFourthPowerOfOddNumbers | 43 | 43 | 0 | 0 | 0 | 0 |  |
| vericoding_lj0000__chooseOdd | 4 | 4 | 0 | 0 | 0 | 0 |  |
| vericoding_lv0091__lastDigit | 5 | 5 | 0 | 0 | 0 | 0 |  |
| vericoding_lv0092__cubeSurfaceArea | 8 | 8 | 0 | 0 | 0 | 0 |  |
| vericoding_lv0187__computeAvg | 9 | 9 | 0 | 0 | 0 | 0 |  |
