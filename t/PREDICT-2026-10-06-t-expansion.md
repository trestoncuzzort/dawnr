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

## T2 read (2026-10-06 10:45Z, after G2 and two corrections to the instrument)

| | after G1 (T1 read) | after G2 alone | after G2 and the reader correction | bar | |
|---|---:|---:|---:|---:|---|
| function-shaped in fragment | 1,072 | 1,302 | **1,601** (37.8%; 275 of them carry a real) | ≥ 1,320 | met on the corrected instrument; G2 alone missed by 18 |
| MBPP | 278 | 319 | **618** (86 carry a real) | ≥ 600 | met on the corrected instrument; G2 alone missed by 281 |
| HumanEval | 14 | 18 | 18 | — | |

Two faults in `t/nl_census.py` were found while reading, both fixed today and both stated here because they
move the numbers more than the landing did:

1. **The MBPP io reader was the pool's v1 reader** (ints, bools, seq<int>): every assertion with a string, a
   tuple, a nested row or a decimal argument was a refusal, and one refused assertion put the problem out of the
   fragment whatever its gaps. So G1's shapes were never counted into MBPP's fragment at the T1 read (278), and
   305 MBPP problems sat out of the fragment with no gap named. The reader now reads strings, tuples, nested rows
   and nested ints (the 2026-10-05 wider reader) and a decimal as `real`; a refusal the reader maps to a burden
   or gap by name no longer disqualifies the problem, a structural refusal (not `f(...) == v`) still does.
2. **The greedy table credited a problem with no gap to whichever gate opened first.** That is where "real
   +362" came from in the T1 read: 305 no-gap MBPP problems were counted under the first gate. The sole-blocker
   column was right (real: 297 across the corpus). The greedy order now runs over gap-blocked problems only and
   the report counts the no-gap problems apart (6 today).

The landing's own effect, by the instrument as it stands: function-shaped 1,072 → 1,302 (+230 against 297 sole
blockers; the rest needed a second gate), MBPP 278 → 319 (+41), HumanEval 14 → 18. `sqrt` is split out of
`real` as its own gap (192 problems, 23 sole blockers): a root is specified in t (`r * r == x`), not computed,
and `isqrt` is G3's library. The kernels: Dafny verifies all four committed tasks with the twin refuted
(`average`, `half_way`, `floor_ceil`, `safe_ratio`; the last through the definedness obligation, the collapse-if
twin dividing by `b` unguarded); SPARK (`Big_Reals`) and F* (`FStar.Real`, Ghost effect) each verify three
with the twin refuted and abstain by name on `floor_ceil` (neither library has a floor); Verus, Frama-C, Lean
and Rocq abstain by name. T8 and T9
hold: every old task keeps its twin rung (checked against the 09:15Z matrix), `surface.py --check` round-trips
1,937 of 1,937 and the grammar check on the lab agrees on every program (8,975 canonical, 7,150 as written, 490
refused).

Sole blockers after G2 (the restated bars stand as written above): generator 295, class 294, import 273, map
128, string-lib 125, closure 99, any-type 96, seq-slice-step 77, unbounded-loop 62, seq-slice-negative 41,
none-type 35, sqrt 23, exception 20, io 7.

## T3a registered (2026-10-06 13:05Z, before any run): the library, SPEC "The library (v1)"

G3 is split: G3a is the integer and sequence library (`min`, `max`, `abs`, `sum`, `gcd`, `pow`, `isqrt`, `x in s`
on a seq, `rev`) and the negative-literal index/bound sugar; G3b is `for` as sugar over `while`, seq comprehensions,
`sorted` and the slice step. Bars for G3a, read by the census and the matrix:

| | bar | from |
|---|---|---|
| function-shaped in fragment | ≥ 1,601 + 35 = 1,636 | `seq-slice-negative`: 41 sole blockers, less those whose negative bound is not a literal |
| `builtin-math` | stays a burden, re-tagged IN THE FRAGMENT (the count is the same by construction; what changes is that the writer has the word) | the detector |
| `sqrt` | the `math.isqrt` / `int(math.sqrt(..))` forms leave the gap (≥ 5 of its 23 sole blockers); `math.sqrt` as a real stays a gap | the detector, split |
| kernels | Dafny, Verus, SPARK and F* verify the real and refute the twin on every committed task of the landing, or abstain by name on a function they cannot carry (named); Lean, Rocq, Frama-C abstain by name; no old task's cell changes | T8 |
| notation | `surface.py --check` round-trips every example; the grammar is unchanged (calls were already in it), so the lab check holds as it stands | T9 |

What would falsify the design: a kernel that verifies a wrong twin through a library definition that differs from
the interpreter's (the interpreter is the reference; a disagreement is a lowering bug, reported as such), or a
committed task whose proof needs a lemma about the library (`isqrt`'s uniqueness, `sum` over a slice) that no
kernel discharges without help: then the task is restated or the function abstains by name, and the result says
which.

### T3a read (2026-10-06 13:50Z, the library's core and Dafny landed; the census with the detectors moved)

| | before | after | bar | |
|---|---:|---:|---:|---|
| function-shaped in fragment | 1,601 | **1,642** (38.7%) | ≥ 1,636 | met (+41: the 41 `seq-slice-negative` sole blockers, all of them literal bounds) |
| MBPP | 618 | 625 | — | +7 |
| HumanEval | 18 | 19 | — | +1 |
| `builtin-math` | 6,624 burden | 6,686, re-tagged IN THE FRAGMENT (now also `math.gcd`, `math.isqrt`) | re-tagged | as stated |
| `sqrt` sole blockers | 23 | 23 | ≥ 5 leave | **missed**: the detector had never tagged `math.isqrt` under `sqrt` (it reads `.sqrt` only), so nothing could leave by moving `isqrt`; the 23 are `math.sqrt` on a real, which stays a gap by design |

The kernels at this read: Dafny verifies all nine committed tasks with the twin refuted. `sum`'s first task,
`sum_two` (`r == sum([a, b])`), read UNPROVED: the two-element display is not unfolded at Dafny's default fuel
(`t_pow(x, 3)` is), a `{:fuel 3, 4}` attribute proved it but the adapter bans every attribute (its audit rule),
so the committed tasks are `sum_tail` (`r == sum(s + [x])`, one unfolding, which Dafny proves and SPARK (timeout)
and F* (gave up) do not: both need the slice lemma Dafny's sequence axioms supply) and `sum_one` (`r == sum([x])`,
which all three prove). SPARK and F* carry the library (9 of 10 tasks each, `sum_tail` the exception); Verus
carries it on 7 of 10 (`sum_tail` the same lemma; `cube` and `root_floor` need nonlinear arithmetic Verus does not
try unhinted); Lean, Rocq and Frama-C abstain by name on every library function and on membership in a seq. The
three unproved cells are measured kernel limits, kept in the matrix as they read, not false verdicts. `last` is `last_of`
(SPARK's package already has a `Last`). The `gcd` task was restated once: its
first form asked `gcd(b, a) == gcd(a, b)`, a theorem about Euclid that no kernel proves from the definition, and
a committed task is a use of the library, not a lemma about it.

## T3b-1 registered (2026-10-06 15:00Z, before any run): `for` as sugar, SPEC "Loops as sugar (v1)"

The three `for` forms expand to the `while` the AST has, with the bound invariants and the `decreases` supplied.
Bars: the census does not move (a Python `for` was never a gap: `while` already carried it); the three committed
tasks read as `while` tasks do in every kernel (the kernel half of T8: Dafny, Verus, SPARK, F*, Lean, Rocq,
Frama-C each verify the real and refute the twin wherever that kernel counts the existing while-loop tasks, or
read the same limit by name); `surface.py --check` round-trips 1,939 of 1,939 and the lab's grammar check agrees
with the new `for` rule (T9). What would falsify the design: a kernel that counts `while` tasks and not these
(then the expansion is wrong, not the kernel).

### T3b-1 read (2026-10-06 15:40Z): the three `for` tasks parse to their `while`, round-trip through it, and Dafny
verifies each with the twin refuted (`count_pos_for` compare-flip, `zeros_for` compare-flip, `any_neg_for`
collapse-if); the other six columns are read from the clean-clone matrix that follows the commit. The census did
not move, as registered. `surface.py --check` round-trips 1,943 of 1,943; the lab's grammar check agrees on every
program with the `for` rule and the optional `else` (an `if` without `else` is the `if` with an empty `else`, a
notation change made the same day because every `for` body in the committed tasks wanted one).

## T3b-2 registered (2026-10-06 15:50Z, before any run): `sort(s)`, SPEC "Sorting (v1)"

Bars: the `sort` burden (2,908 problems) is re-tagged IN THE FRAGMENT (its count is the same by construction);
the census does not otherwise move. Kernels: Dafny and Verus verify the two committed tasks with the twin refuted,
or read a limit by name; F*, SPARK, Lean, Rocq and Frama-C abstain by name. T9 as before (the grammar is unchanged:
a call). What would falsify the design: Dafny failing to prove its own insertion sort's postconditions (then the
Std's merge sort shape is taken instead, and the result says so).

### T3b-2 read (2026-10-06 16:30Z): `sort(s)` landed. Dafny carries it as Std.Collections.Seq's merge sort specialised
to the element type, with the Std's own lemma and asserts (its first form, an insertion sort, did not prove its
own postconditions; the Std's shape did, and `t_sorted` is a `function ... : bool`, since the adapter's shape rule
admits no `predicate`); Verus as one wrapper over vstd's `sort_by` with one named comparison closure shared by the
wrapper and the lemma (two closure literals are two functions to the solver) and the lemma stated beside every use,
in the clause well-formedness lemmas and in a certificate that sorts. Both committed tasks (`sort_it`,
`first_sorted`) verified with the twin refuted in both kernels; F*, SPARK, Lean, Rocq and Frama-C abstain by name.
The `sort` burden is IN THE FRAGMENT (2,908 problems; the census count unchanged by construction, 1,642 in
fragment). `sort_it` was given a local (`var u := sort(s); r := u`) so the ladder has a mutation to make: a body
`r := sort(s)` alone has no twin, and a task without a twin cannot count.
