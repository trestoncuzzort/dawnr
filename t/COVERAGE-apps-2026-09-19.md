# t coverage: APPS (2266 problems in pool v5)

Written by `t/coverage_corpus.py` on 2026-09-19 08:02Z, from the
answer sets already on disk. No kernel ran and nothing was generated. ROADMAP 16.3 asks for a
second coverage table over a second corpus; this is the pipeline's own question, since
`coverage_census.py` reads Dafny source and this corpus is Python.

## How far the corpus got

| stage | problems | share |
|---|---|---|
| in the pool (their own examples read as t values) | 2266 | 100% |
| a model answered | 2263 | 99.9% |
| the answer was well-formed t | 422 | 18.6% |
| it passed the problem's own tests | 257 | 11.3% |
| **all seven verified it with the twin refuted** | **29** | 1.3% |

351 answers reached the checkers.

## What stopped the ones the checkers saw

One row per kernel and outcome, counted over every graded answer that was not clean. An
answer usually appears in several rows: it is counted once for each kernel that did not
verify it.

| kernel | outcome | answers |
|---|---|---|
| `dafny` | unproved | 201 |
| `spark` | timeout | 196 |
| `verus` | unproved | 164 |
| `lean` | unproved | 150 |
| `framac` | abstain | 141 |
| `verus` | refuted | 138 |
| `fstar` | abstain | 134 |
| `rocq` | unproved | 123 |
| `fstar` | unproved | 123 |
| `dafny` | refuted | 116 |
| `lean` | abstain | 113 |
| `rocq` | abstain | 113 |
| `framac` | timeout | 108 |
| `framac` | refuted | 85 |
| `rocq` | refuted | 80 |
| `spark` | refuted | 79 |
| `fstar` | refuted | 78 |
| `lean` | refuted | 61 |

## Sole blockers

Answers where six kernels verified and one did not: the cheapest possible gains, since
everything else about them is already on the record.

| kernel | answers it alone kept out |
|---|---|
| `dafny` | 0 |
| `verus` | 0 |
| `spark` | 6 |
| `framac` | 3 |
| `lean` | 2 |
| `rocq` | 0 |
| `fstar` | 0 |

