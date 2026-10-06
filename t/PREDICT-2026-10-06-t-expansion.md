# Registered before the work: the expansion of t (2026-10-06 08:20Z)

The plan is `internal/RESEARCH-2026-10-06-t-expansion.md`. The instrument is `t/nl_census.py` with its detectors
updated at each landing (a construct in the fragment is no longer a gap), read as the count of function-shaped
problems in fragment; the other instrument is `t/AGREEMENT.md`, every present kernel verifying the real task and
refuting its twin on the landing's committed tasks. Today: 772 of 4,239 function-shaped problems, 263 of 974 MBPP,
12 of 164 HumanEval; 39 committed tasks, 31 agreed by all seven.

| | after | bar | why that number |
|---|---|---|---|
| T1 | G1 compositional types | MBPP in fragment ≥ 380 (from 263); all function-shaped ≥ 1,150 (from 772) | the census says tuple + nested-seq + nested-seq-pair/string/deep + multi-return unlock about 130 MBPP and 400 corpus problems when opened together; some need other gates too |
| T2 | G2 exact rationals | MBPP ≥ 600; all function-shaped ≥ 1,500 | real alone unlocks 240 MBPP and 395 corpus problems first; after G1 more of them have only this gap left |
| T3 | G3 builtins and notation | the burdens `builtin-math`, `comprehension`, `sort` fall by at least half on the function-shaped MBPP problems in fragment; MBPP in fragment ≥ 640 | the burdens are what the writer stumbles on (the syntax gate), measured by the same census |
| T4 | G4 break and continue | MBPP ≥ 670; the `unbounded-loop` gap's sole-blocker count falls from 32 toward 0 | 29 MBPP problems have it as the only remaining gap after the gates above |
| T5 | G5 maps | MBPP ≥ 720; all function-shaped ≥ 1,900 | map unlocks 49 MBPP and 246 corpus problems in the greedy order |
| T6 | G6 records and options | `none-type`, `multi-return` and `exception` stop appearing as sole blockers | 17 + 3 + 11 problems today |
| T7 | G7 the string library's missing members | `string-lib` falls below 20 as a sole blocker (from 92) | the members are named in SPEC "What v1 does not claim" |
| T8 | every landing | every present kernel verifies the real and refutes the twin on at least two committed tasks per construct, or abstains by name; no kernel's abstain count on the 39 existing tasks rises | AGENTS rule 2; the matrix is regenerated from a clean clone |
| T9 | every landing | `surface.py --check` round-trips every SYNTAX example and 100,000 random ASTs; `grammar_check.py` accepts all parser-accepted programs | the notation stays the AST |

What would falsify the direction: a landing whose census bar is met while the kernels abstain on most of its tasks
(the construct is in the language and in no proof), or a bar missed because the unlocked problems need a gate that
is out of scope by design (classes, I/O). Both are reported as the result, not softened.

## T1 read (2026-10-06 08:55Z, the census with the type detectors moved to burdens)

| | before | after G1 | bar | |
|---|---:|---:|---:|---|
| function-shaped in fragment | 772 | **1,072** (25.3%) | ≥ 1,150 | **missed by 78** |
| MBPP | 263 | **278** | ≥ 380 | **missed by 102** |
| HumanEval | 12 | 14 | — | |
| APPS (function-shaped) | 497 | 780 | — | |
| stdin-shaped, in fragment once a signature is extracted | 3,750 | 5,345 | — | |

The bar was set from the census's greedy table, whose "newly unlocked" counts are CUMULATIVE after the gates above
them in the order (`real` and `import` first), not what each gate opens on its own. The column that answers the
question asked was the sole-blocker column: tuple 71 + nested-seq 177 + nested-seq-pair/string/deep 0 + 18 + 16 +
set 54 + multi-return 3 = 339 function-shaped problems with one of these as the only gap, and the landing opened
300 (some needed two of them, some are now blocked by another gap that the greedy order had counted as already
open). MBPP's problems that need tuples or nested seqs almost all need `real` or an `import` too, so the MBPP count
moved 15. The bars for the landings below are restated from the sole-blocker column of the census as it stands
after G1 (its table "Gaps, by problems that need them"), not from the greedy table, and each is read the same way.

The kernels: Dafny verifies all six committed tasks with the twin refuted (sort3, zip_pairs, signs, words_seen,
swap_ends, grid_row_sums); Verus, SPARK, Frama-C, Lean, Rocq and F* abstain by name (T8 holds on its own terms:
no false verdict; T1's kernel half is open until each is written).

### The bars restated from the sole-blocker column after G1 (2026-10-06 09:00Z, before G2 runs)

Function-shaped problems with exactly one gap left, after G1: real 297, class 262, generator 257, import 253, map 110,
string-lib 109, closure 84, any-type 83, seq-slice-step 72, unbounded-loop 53, seq-slice-negative 38, none-type 26,
exception 13, io 6. MBPP's own greedy order now opens with `real` at +362 (278 → 640, 65.7%).

| | after | bar (restated) | from |
|---|---|---|---|
| T2 | G2 exact rationals | all function-shaped ≥ 1,072 + 250 = 1,320; MBPP ≥ 600 | real: 297 sole blockers; +362 first in MBPP's order |
| T3 | G3 builtins and notation | ≥ +90 function-shaped (slice step 72 + negative slice 38 sole, less overlap); the burdens `builtin-math`, `comprehension`, `sort` down by half on MBPP's in-fragment problems | the two slice gaps and the burden table |
| T4 | G4 break and continue | ≥ +40 | unbounded-loop: 53 sole |
| T5 | G5 maps | ≥ +90 | map: 110 sole |
| T6 | G6 records and options | ≥ +30 | none-type 26 + exception 13 sole |
| T7 | G7 the string library's missing members | ≥ +80 | string-lib: 109 sole |

`class`, `generator`, `import` and `closure` stay as they are: the first is out of scope by design, the other three
are met in part by G3's builtins and comprehensions (the census will say how much, by the same column).
