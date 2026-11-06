# Native gate: a `complete` verdict checked by a proof checker, 2026-11-05

`LIMITS.md` and `t/NATIVE-CASES.md` say the SAT solver is trusted. A counterexample already has a check
that does not trust the solver: it is replayed natively. A `complete` verdict has none. This adds
one: the formula CBMC would give to its solver is exported, a solver writes an LRAT proof that the
formula has no solution, and a small separate program checks that proof.

Found by the research list of this date: `marijnheule/drat-trim` (`lrat-check.c`, MIT) and
`arminbiere/cadical` (`--lrat`, MIT), with arXiv:2607.00815 and arXiv:2609.20873 on what such certificates
cost and mean. Both tools are built from pinned commits by `t/build_certify_tools.sh`, and neither is
copied into this repository.

## What it does and does not establish

It removes the trust in the SAT solver for the checking stage. It does not remove the trust in CBMC's
translation of C to that formula, which is where a wrong result is more likely to come from, or in the
checker. The coverage stage, which shows the assumptions and the end of the harness can be reached, is
not certified by this. It is not a proof in any of the seven kernels. Their agreement counts are unchanged.

## What was measured before this file was written

A prototype on 5 published cases, with CaDiCaL 3.0.1 at c6073042 and `lrat-check` at 2e3b2dc0:

| case | formula | solve | proof | check | `fixed` | `original` |
|---|---|---|---|---|---|---|
| libuv-utf8-decode1 | 0.4 MB | 0.0 s | 1.2 MB | 0.0 s | `c VERIFIED` | satisfiable |
| betaflight-uvarint-encode | 0.3 MB | 0.1 s | 1.1 MB | 0.0 s | `c VERIFIED` | satisfiable |
| libevent-servname-port-range | 4.8 MB | 10.9 s | 366.0 MB | 2.8 s | `c VERIFIED` | satisfiable |
| msgpack-c-print-buffer-empty-bin | 52.3 MB | 20.4 s | 293.2 MB | 2.8 s | `c VERIFIED` | satisfiable |
| libcoap-opt-parse-delta | 78.3 MB | 16.8 s | 201.9 MB | 2.2 s | `c VERIFIED` | satisfiable |

Betaflight at `--unwind 1` is satisfiable, so the formula carries the unwinding assertions. On the libuv proof,
a flipped literal printed `c FAILED`, a hint to a clause that does not exist crashed the checker (exit 139), a
truncated proof exited 1, and a proof of another formula printed `c FAILED`. None printed `c VERIFIED`.

Read in `lrat-check.c` at that commit: `c VERIFIED` needs the empty clause derived and no error. On failure it
prints `c NOT VERIFIED`, so a search for the word would accept a failure, and some of its error paths exit 0, so
the exit status alone is not enough. The gate requires the exact line and exit 0, and anything else is not verified.

## Predictions, written before the gate had this stage

| # | prediction | falsified by |
|---|---|---|
| C1 | `--cadical` and `--lrat-check` on all 8 published `fixed` variants and the PX4 case: every one `verified` | any other status that is not a stated resource limit |
| C2 | Five bad proofs of one formula are all refused: flipped literal, hint to a missing clause, truncated, empty, proof of another formula | one accepted |
| C3 | The exported formula of each published `original` is satisfiable, so it does carry the failing property | one that is proved unsatisfiable |
| C4 | Export, solve and check together take under 3 times the CaDiCaL checking stage on each case, and checking takes less time than solving on each case above 1 s of solving | a case above either |
| C5 | Proofs stay under 20 GB on every published case | one above |

## Results

From `native_fixture_check.py --cadical --lrat-check --solver cadical --memory-limit-mb 6144`, on commit 6a9f331.
Receipt: [`evidence/native-gate-2026-11-05/fixture-check-certified.json`](evidence/native-gate-2026-11-05/fixture-check-certified.json).

| # | outcome | measured |
|---|---|---|
| C1 | holds | all 8 published `fixed` variants and PX4: `verified`, with no certificate problem |
| C2 | holds | the five bad proofs are refused in `test_native_case.py`. The hint to a missing clause crashes the checker (exit 139), and a crash is a refusal |
| C3 | holds | the formula of each `original` has a solution, so it carries the failing property |
| C4 | holds | export, solve and check together take 0.72 to 1.59 times the checking stage, and checking is faster than solving on each case above 1 s of solving |
| C5 | holds | largest proof 2.9 GB, against 20 GB |

| case | formula MB | SAT variables | solve s | proof MB | check s | checking stage s | status |
|---|---:|---:|---:|---:|---:|---:|---|
| flac-metaflac-parse-uint32 | 1.9 | 24,844 | 3.61 | 83.7 | 0.69 | 6.18 | `verified` |
| libcoap-opt-parse-delta | 78.3 | 228,326 | 13.00 | 201.9 | 2.24 | 11.01 | `verified` |
| libevent-servname-port-range | 4.8 | 55,727 | 11.61 | 366.0 | 3.36 | 10.53 | `verified` |
| msgpack-c-print-buffer-empty-bin | 52.3 | 601,159 | 17.45 | 293.2 | 3.05 | 14.71 | `verified` |
| open62541-datetime-parse-year | 19.6 | 208,935 | 130.05 | 2,948.5 | 20.91 | 95.48 | `verified` |
| betaflight, INAV, libuv, PX4 | under 0.5 | under 8,000 | under 0.1 | under 2 | under 0.1 | under 0.1 | `verified` |

The same run on GitHub's machines, run 42175532805 of dawnr's `native.yml`: 29 rows, none moved, no certificate problem, and each proof
the same size to 0.1 MB, so the formula and the proof do not depend on the machine.

arXiv:2609.20873 reports checking at 1.9 times solving for its DRAT proofs. These LRAT checks took 0.13 to 0.29 of solving, since an LRAT
proof names the clauses each step uses. They are different proofs of different problems, so this is not a comparison of the two.

## What this bought

The solver is no longer trusted for the checking stage on these cases. Every `complete` behind the 8 pull requests opened upstream has a
proof that a 500-line program checked. What is left is the part that was always the likelier place for a mistake, CBMC's translation of
C to a formula, and nothing here touches it. The proofs themselves are not kept, only their hashes, so to see one again it has to be
made again. A second checker (`krobelus/rate`, MIT, on the research list) and checking in Lean through arXiv:2607.00815 are the
next steps for this limit, if the checker itself becomes the concern.
