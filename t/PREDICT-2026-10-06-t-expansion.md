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

## T2 read (2026-10-06 10:07Z, after G2 and two corrections to the instrument)

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

## T3a registered (2026-10-06 10:54Z, before any run): the library, SPEC "The library (v1)"

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

### T3a read (2026-10-06 11:13Z, the library's core and Dafny landed; the census with the detectors moved)

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

## T3b-1 registered (2026-10-06 11:48Z, before any run): `for` as sugar, SPEC "Loops as sugar (v1)"

The three `for` forms expand to the `while` the AST has, with the bound invariants and the `decreases` supplied.
Bars: the census does not move (a Python `for` was never a gap: `while` already carried it); the three committed
tasks read as `while` tasks do in every kernel (the kernel half of T8: Dafny, Verus, SPARK, F*, Lean, Rocq,
Frama-C each verify the real and refute the twin wherever that kernel counts the existing while-loop tasks, or
read the same limit by name); `surface.py --check` round-trips 1,939 of 1,939 and the lab's grammar check agrees
with the new `for` rule (T9). What would falsify the design: a kernel that counts `while` tasks and not these
(then the expansion is wrong, not the kernel).

### T3b-1 read (2026-10-06 11:57Z): the three `for` tasks parse to their `while`, round-trip through it, and Dafny
verifies each with the twin refuted (`count_pos_for` compare-flip, `zeros_for` compare-flip, `any_neg_for`
collapse-if); the other six columns are read from the clean-clone matrix that follows the commit. The census did
not move, as registered. `surface.py --check` round-trips 1,943 of 1,943; the lab's grammar check agrees on every
program with the `for` rule and the optional `else` (an `if` without `else` is the `if` with an empty `else`, a
notation change made the same day because every `for` body in the committed tasks wanted one).

## T3b-2 registered (2026-10-06 11:58Z, before any run): `sort(s)`, SPEC "Sorting (v1)"

Bars: the `sort` burden (2,908 problems) is re-tagged IN THE FRAGMENT (its count is the same by construction);
the census does not otherwise move. Kernels: Dafny and Verus verify the two committed tasks with the twin refuted,
or read a limit by name; F*, SPARK, Lean, Rocq and Frama-C abstain by name. T9 as before (the grammar is unchanged:
a call). What would falsify the design: Dafny failing to prove its own insertion sort's postconditions (then the
Std's merge sort shape is taken instead, and the result says so).

### T3b-2 read (2026-10-06 12:25Z): `sort(s)` landed. Dafny carries it as Std.Collections.Seq's merge sort specialised
to the element type, with the Std's own lemma and asserts (its first form, an insertion sort, did not prove its
own postconditions; the Std's shape did, and `t_sorted` is a `function ... : bool`, since the adapter's shape rule
admits no `predicate`); Verus as one wrapper over vstd's `sort_by` with one named comparison closure shared by the
wrapper and the lemma (two closure literals are two functions to the solver) and the lemma stated beside every use,
in the clause well-formedness lemmas and in a certificate that sorts. Both committed tasks (`sort_it`,
`first_sorted`) verified with the twin refuted in both kernels; F*, SPARK, Lean, Rocq and Frama-C abstain by name.
The `sort` burden is IN THE FRAGMENT (2,908 problems; the census count unchanged by construction, 1,642 in
fragment). `sort_it` was given a local (`var u := sort(s); r := u`) so the ladder has a mutation to make: a body
`r := sort(s)` alone has no twin, and a task without a twin cannot count.

## T3b-3 registered (2026-10-06 12:33Z, before any run): comprehensions, SPEC "Comprehensions (v1)"

Bars: the `comprehension` burden (5,920 problems) is re-tagged IN THE FRAGMENT for list comprehensions whose
source is a sequence or a range; set and dict comprehensions stay a burden by name (`set-comprehension`,
`dict-comprehension`) until maps land, so the count will split, not vanish. Kernels: Dafny and Verus verify the
three committed tasks with the twin refuted, or read a limit by name; the other five abstain by name. T9: the
round trip over the new form (`surface.py --check`, which fuzzes it) and the lab's grammar check with the new
rule. What would falsify the design: a filter or map ensures Dafny does not prove by induction from the
recursive definition (then the Std's opaque-plus-lemma shape is taken and the result says so).

### T3b-3 read (2026-10-06 12:56Z): comprehensions landed. The form `[body for x in s if cond]` (and over `[lo, hi)`)
parses, prints and fuzzes (`surface.py --check` 1,948 of 1,948; the lab's grammar check agrees with the new rule);
the checker types the bound variable from the source, the interpreter evaluates it, the twins reach its bounds and
condition. Dafny carries it as one recursive function per comprehension with the ensures its shape admits (filter:
every element satisfies the condition, the length does not grow; map: the length and the image at every index;
range map: `hi - lo` and the image at `lo + k`), proved by induction from the definition as the Std's Filter and
Map are, and a ground comprehension in a certificate is unrolled into the display it denotes, one `(if cond then
[body] else [])` per element, so no recursive function is unfolded there; Verus carries it as a `spec fn` with a
broadcast lemma of the same ensures, revealed with fuel inside the proof fn (its nonlinear-arithmetic bridge
steps aside for a return built from a comprehension, since that block sees no outside fact). All three committed
tasks (`evens`, `doubled`, `squares`) verified with the twin refuted in both kernels; F*, SPARK, Lean, Rocq and
Frama-C abstain by name. The census: `comprehension` (5,920 problems) is IN THE FRAGMENT for list comprehensions;
set and dict comprehensions are the new burden `set-dict-comprehension`; the in-fragment count is unchanged by
construction (1,642).

## T3c registered (2026-10-06 13:26Z, before any run): stepped slices, SPEC "Stepped slices (v1)", and the
definedness of a comprehension's body in Dafny

Found while reading the comprehension landing's Dafny text for the next form: the recursive function it emits per
comprehension has no `requires`, so a body with a partial operator over a free variable (`[s[i + 1] - s[i] for i in
[0, len(s) - 1)]`, the differences, a shape MBPP writes constantly) fails Dafny's own well-formedness check inside
the function and the task reads `unproved` for the real and the twin alike (measured on a scratch task `diffs`
before this registration: Verus `verified / refuted`, Dafny `unproved / unproved`, the FINDING line of the matrix).
Bars: (1) `_comp_defs` gives the function the precondition the SPEC's definedness rule states, over the index as the
Std's `Map` does (`requires forall i :: 0 <= i < |xs| ==> f.requires(xs[i])`), emitted only when the formula is not
`true`, so the three committed comprehension tasks' Dafny text is unchanged; `diffs` committed and Dafny `verified /
refuted`. (2) `s[a..b..k]`, the stepped slice, as SUGAR the parser expands to the range comprehension `[s[a..b][k * i]
for i in [0, (len(s[a..b]) + k - 1) / k)]` (the bound variable fresh in the task, never printed as sugar): Python's
meaning on positive steps with the two-bound slice's definedness, `k` a positive literal (a step of 0 or a negative
step is refused by name; a reversal is `rev(s)`; a variable step is written as the comprehension). Two committed
tasks, `every_other` (`s[0..len(s)..2]`) and `odd_positions` (`s[1..len(s)..2]`), Dafny and Verus `verified /
refuted` through the range-map ensures; the other five abstain by name as for every comprehension. (3) The census:
`seq-slice-step` (852 problems) splits: a positive literal step is IN THE FRAGMENT; `s[::-1]` with no bounds is the
library's `rev` and in the fragment; any other step (a variable, a negative one with bounds) stays a gap by name.
(4) `surface.py --check` round-trips every corpus file and the lab's grammar check agrees with the new `post` rule.
What would falsify the design: Dafny's trigger selection on a range comprehension's precondition (its body is
arithmetic over the bound index, no indexing term to match on) leaves the function's own well-formedness unproved;
then the precondition is restated through a term Dafny can match (the Std's `f.requires(xs[i])` shape, or an
identity function on the index) and the read says which.

### T3c read (2026-10-06 13:47Z): stepped slices landed; the comprehension precondition in Dafny repaired.
(1) Dafny: `_comp_defs` passes a range as the index sequence `t_range(a, b)` and gives every comprehension function
the SPEC's definedness formula as a precondition over the element `t_s[t_di]` (the Std `Map`'s shape), the conjuncts
without the element once under `|t_s| > 0`. The falsifier fired first: a precondition over a bare range index left
the function's own well-formedness unproved (`index out of range` inside the function, 19:40Z), as registered; the
element form proved all five probe shapes (an indexed map over a range, the stepped slice, a gather `s2[x]` over a
sequence, a total body, a divisor with no mention of the element), and then `odd_positions` failed its ensures'
well-formedness (`lower bound out of range`: `1 <= |s|` reachable only through the element's instance) until the
element-free conjuncts were stated once. `diffs` committed: Dafny `verified / refuted` (was `unproved / unproved`).
The three earlier comprehension tasks unchanged in outcome (`evens`, `doubled`, `squares`: `verified / refuted` in
both kernels; their Dafny text now has the one sequence shape). (2) `s[a..b..k]` parses to the registered
comprehension, prints as it and round-trips (`surface.py --check`: 1,951 of 1,951 well-formed corpus tasks, 5
literal probes, 14 refusals); the bound variable is the first of i, j, k, i2, ... absent from the program;
`every_other` and `odd_positions` committed, Dafny and Verus `verified / refuted` (the twin: off-by-one on the
slice's lower bound). (3) The census: `seq-slice-step` split into `seq-slice-step` (a positive literal step, 99
problems, in the fragment), `seq-slice-reverse` (`s[::-1]`, 662, in the fragment as `rev`) and the gap
`seq-slice-step-other` (108; the sole blocker for 11); in the fragment 1,642 -> 1,713 of 4,239 function-shaped
(38.7% -> 40.4%). (4) The lab's grammar check: the grammar and the parser agree on every program tested (8,996
canonical, 7,150 as written, 450 refused). Unit tests: `t/test_slice_step.py` (7) and `test_comprehensions.py`
updated for the index sequence. Not touched: a variable step (written as the comprehension by hand), clamping
(t's slice is undefined out of range, Python's clamps).

## T3d registered and read in one sitting (2026-10-06 14:05Z): the three library proofs the kernels did not reach
alone (the roadmap's item after the stepped slices)

Registered before the fix runs, from the kernels' own messages on the lowered files (`cube`, `root_floor`, `sum_tail`;
receipt 458fc843896b): Verus `cube` — `r == t_pow(x, 3)` unproved, since fuel unfolds `t_pow(x, 3)` to `x * (x *
(x * 1))` and the body's `x * x * x` is the same number only to the nonlinear solver; Verus `root_floor` — the
library's own `t_isqrt_spec` lemma failed its postcondition `n < (t_isqrt(n) + 1) * (t_isqrt(n) + 1)`, the step
`(r + 1)^2 < (r + 2)^2` being nonlinear; Verus and F* `sum_tail` — `sum(s + [x]) == sum(s) + x` needs an induction
the definition does not give; SPARK `sum_tail` — timeout on the same induction. Bars: each kernel's `verified /
refuted` on its task without a regression on the other tasks that use `sum`, `pow` or `isqrt` (`digit_sum`,
`sum_one`).

Read: **Verus** — `t_sum_add` (`t_sum(s + t) == t_sum(s) + t_sum(t)`, induction on `t` with one extensional step,
vstd's `lemma_fold_left_split` shape) and `t_sum_prefix` (`t_sum(s.subrange(0, j))` one step) as broadcast lemmas
brought in inside the proof fn; the isqrt lemma's nonlinear step stated to the nonlinear solver with `r >= 0` as
its one fact; a bridge for every `pow(e, k)` with a literal `k` in the spec over the parameters: `t_pow(e, k) ==
e * ... * e` by `reveal_with_fuel` plus the nested-to-flat identity by `nonlinear_arith` alone. `cube`,
`root_floor`, `sum_tail` `verified / refuted`; `digit_sum`, `sum_one` unchanged (`verified / refuted`). **F*** —
`lemma_t_sum_append` by induction with `Seq.lemma_eq_intro` and an SMT pattern; the pattern alone left `sum_tail`
unproved while an explicit call proved it (a `t_sum (Seq.create 1 x)` that a lemma instance introduces is not
unfolded by the encoding's fuel), so `lemma_t_sum_create1` with its own pattern states that one fact; `sum_tail`
verified (`All verification conditions discharged`). **SPARK** — not fixed, recorded: the lowering emits a package
spec of expression functions only (its own design note: "statement lists are compiled" into one expression), so no
lemma procedure can be called from a task, and a congruence over two sequences cannot be stated as a `Post` (no
quantification over the sequence type); `T_Concat`'s `Post` gives the lengths and the elements, and the step
`T_Sum_To (S & [X], Len S) = T_Sum_To (S, Len S)` is an induction gnatprove times out on. The repair is a design
item (a ghost lemma per `sum(a + b)` shape stated as an extra `Post` conjunct of a helper the task calls, or a
statement body with a lemma call), its own registration. Column counts after this item: Verus `sum`/`pow`/`isqrt`
tasks 5 of 5; F* `sum_tail` joins; SPARK `sum_tail` stays `timeout / refuted`.

## T4 registered (2026-10-06 14:21Z, before any run): early exits, SPEC "Early exits (v1)": `break`, `continue`,
`while true`

The census: `unbounded-loop` is a gap on 4,403 problems (every `while True`, `break` and `continue`), the largest
single gap left; the greedy order unlocks 194 function-shaped problems with it. Read first (receipt d8d236f078af):
Dafny reference 8.14 (break and continue, labelled and not), the Verus guide's loops page, Python's compound
statements; and a Dafny probe (21:40Z): an invariant false at a `break` is accepted and the exit path keeps what
held there (`i % 2 == 0` with `i := i + 1; break;` verified `r == 1`), the invariant is checked at `continue`, and
`while true` verifies with its `decreases`. Bars: (1) the two statements and the `while true` guard parse, print,
round-trip (`surface.py --check`) and the lab's grammar check agrees; the checker refuses an exit outside a loop,
a statement after one, and a `while true` with no exit of its own; (2) the interpreter unwinds `break`/`continue`
to the innermost loop and the `for` sugar's `continue` takes the step; (3) a new twin move DROP-EXIT; (4) Dafny
carries all three natively; the other six abstain by name (`tshape.has_exit`); three committed tasks (`index_of`,
`find_zero`, `count_evens_skip`) Dafny `verified / refuted`; (5) the census re-tags `unbounded-loop` IN THE
FRAGMENT and names the loop `else` clause as its own gap. Also in this landing, found while writing
`count_evens_skip`: a comprehension over a prefix `s[0..i]` (the invariant) and over `s` (the ensures) were two
Dafny functions of one shape, which no kernel can equate; the comprehension key becomes the shape (bound variable,
condition, body, source type), one function per shape, so `t_comp1(s[0..|s|])` and `t_comp1(s)` meet by the
slice axiom. What would falsify the design: Dafny not proving the prefix step of the counting invariant through the
comprehension function's one unfolding (`s[0..i+1][..i] == s[0..i]`); then the task states its count by a spec
function and the comprehension stays in the ensures, and the read says so.

### T4 read (2026-10-06 14:34Z): early exits landed; the comprehension functions in Dafny now in prefix form.
(1) `break;`, `continue;` and `while true` parse, print and round-trip (`surface.py --check`: 1,954 of 1,954
well-formed corpus tasks); the lab's grammar check agrees with the parser on every program tested (the two new
keywords, the two statement rules). The checker's three rules fire where registered (`exit-outside-loop`,
`exit-unreachable`, `loop-exit`; fixtures in t/malformed) and a `break` inside a nested loop does not count as the
outer `while true`'s exit. (2) The interpreter unwinds both exits to the innermost loop; the `for` sugar's
`continue` takes the step (`i := i + 1; continue;`), measured by `count_evens_skip` against Python's own count and
by a nested while whose `continue` stays its own. (3) DROP-EXIT added to the ladder (the twin that found
`index_of` was NEGATE-COND; `find_zero`'s and `count_evens_skip`'s too). (4) Dafny carries all three natively,
its rule t's (the 21:40Z probe); the three tasks `verified / refuted`; the other six kernels abstain by name.
The falsifier fired on `count_evens_skip`: its invariant `c == len([y for y in s[0..i] if y % 2 == 0])` was not
maintained while the prefix and the whole were calls on two sequences (`s[0..i+1][..i]` and `s[0..i]`), which
Dafny does not equate unprompted. Taken instead of a spec function: the comprehension functions in PREFIX form,
`t_compK(t_s, t_n)` over the first `t_n` elements (a source `s[0..e]` is `t_compK(s, e)`, any other source
`t_compK(s, |s|)`), and `t_compK(t_a, t_n)` for a range with its index written `t_a + t_ix(t_di)` through the
identity function `t_ix` (the term Dafny matches the precondition on, replacing the index sequence `t_range` of
T3c); `count_evens_skip` then verifies by one unfolding, and the six earlier comprehension tasks (`evens`,
`doubled`, `squares`, `diffs`, `every_other`, `odd_positions`) stay `verified / refuted` in Dafny and in Verus
(whose spec fns are unchanged). A ground-true conjunct of the precondition (`2 != 0`) is no longer stated. (5) The
census: `unbounded-loop` (4,403 problems) IN THE FRAGMENT; the loop `else` clause is the gap `loop-else` (61; the
sole blocker for 1); in the fragment 1,713 -> 1,777 of 4,239 function-shaped (40.4% -> 41.9%). Not done, by
name: Verus (a loop is a recursive proof fn there; `continue` is a recursive call and `break` an exit the
function's contract does not describe), F*, SPARK, Lean, Rocq and Frama-C on bodies with an exit.

## T5 registered (2026-10-06 14:52Z, before any run): maps, SPEC "Maps (v1)"

The census: `map` is a gap on 2,464 problems (a dict literal, `dict()`, `Counter`, `defaultdict`, a dict-typed io
value; the sole blocker for 129), the fourth-largest. Read first (receipt 85a79b86b0ce): Dafny's `map<T, U>` with
`map[k := v]` displays, `m[k]`, `m[k := v]`, `k in m`, `|m|`, `m.Keys` and `m - s`; vstd's `Map<K, V>` with `dom()`,
`index`, `insert`, `remove`, `len` and its broadcast lemmas; Python's `dict`. Bars: (1) the type `map<K, V>`, the
display `map[k1 := v1, ...]` (`map[]` empty; the rightmost of two equal keys wins, as in Python), `m[k]` (defined iff
`k in m`), `m[k := v]`, `k in m`, `len(m)`, `keys(m)` (a set) and `remove(m, k)` parse, print and round-trip
(`surface.py --check`); the lab's grammar check agrees; the checker's `map-types` and `map-lit-types` fire. (2) The
interpreter agrees with Python's dict on lookup, update, membership, size, keys and removal; the witness ladder
reaches small maps. (3) Dafny and Verus carry maps natively (`map<K, V>` / `Map<K, V>`); the other five abstain by
name (the type shape). Three committed tasks: `lookup_or` (lookup with a default), `put_key` (one update: the key is
in, its value, the size does not shrink, the rest unchanged by `remove`), `index_map` (a loop building a map from a
sequence: every element is a key, the size is at most the length), each `verified / refuted` in both. (4) The census
re-tags `map` IN THE FRAGMENT and names iteration over a dict (`.items()`, `.values()`) as the gap `map-iteration`.
What would falsify the design: Verus's `==` on two maps needs the same `=~=` bridge nested seqs and sets needed
(then `_nested_eq_bridges` takes `Map<` too, and the read says so); Dafny not proving `|m[k := v]| <= |m| + 1` from
its own map axioms (then the size ensures of `index_map` is dropped and the read says so).

### T5 read (2026-10-06 15:04Z): maps landed.
(1) `map<K, V>`, `map[k := v, ...]`, `m[k]`, `m[k := v]`, `k in m`, `len(m)`, `keys(m)` and `remove(m, k)` parse, print
and round-trip (`surface.py --check`: 1,957 of 1,957 well-formed corpus tasks); the lab's grammar check agrees with
the parser on every program tested (the `map` keyword, the type rule, the display rule); `map-types` and
`map-lit-types` fire with fixtures. (2) The interpreter's `MapV` agrees with Python's dict on lookup, update (insert
and overwrite), membership, size, keys, removal (total on an absent key), the rightmost duplicate key, and
extensional `==`; a map is never a seq of pairs to `_tv`; the ladder starts at the empty map. (3) Dafny and Verus
carry the type natively; the three tasks `lookup_or`, `put_key`, `index_map` are `verified / refuted` in both (the
twins: an off-by-one key, an off-by-one key in the update, a flipped loop guard). Both registered falsifiers held
their ground without firing: Dafny proved `|m[k := v]| <= |m| + 1` and `(m[k := v] - {k}) == (m - {k})` from its own
axioms, and Verus proved `put_key`'s map equality with the `=~=` bridge extended to `Map<` as registered. Two
things the registration did not foresee, both repaired and measured: Verus's loop helper renames its state to the
result tuple's components (`t_res.0`, `t_res.1`), so a map state's `k in m` was written as a seq's `.contains` until
the components were aliased to their t types for the typer (`index_map`: `no method named contains` before, 5
verified after); and the Verus certificate path rebuilt a map witness as a plain list, so `lookup_or`'s off-by-one
twin replayed `k in m` as false, hid the undefined lookup behind the `else`, and built no certificate (`twin =
unproved`) until `_to_py` learnt maps and a ground formula over a map took the SMT arm as a set's does (`twin =
refuted` after). F*, SPARK, Lean, Rocq and Frama-C abstain by name on the type shape (`map<int, int> is not lowered
yet`). (4) The census: `map` (2,464 problems) IN THE FRAGMENT; iteration over a dict is the gap `map-iteration`
(535; the sole blocker for 21; a bare `for k in d` is not recognised, undercounted); in the fragment 1,777 ->
1,892 of 4,239 function-shaped (41.9% -> 44.6%). Not done, by name: iteration over a map, `values(m)`, a map
comprehension, and the other five kernels.

## T6 registered (2026-10-06 15:24Z, before any run): reductions over a sequence, SPEC "Reductions (v1)", and three
census corrections measured first

Measured on the corpus's first solutions before designing (01:00Z): of 1,047 solutions with a generator expression,
the consumers are `sum` 405, `join` 293, `all` 114, `max` 65, `any` 65, `sorted` 55, `tuple` 53, `min` 50, `next`
47, `set` 23, `reduce` 21, `list` 18; of 950 solutions with a class, 638 are a bare method wrapper (`class
Solution` whose methods never read `self`), 66 methods calling each other through `self`, 173 stateful, 17
records; the imports beyond math/sys/typing are `collections` 638, `itertools` 313, `re` 292, `bisect` 236, `heapq`
160, `functools` 141, `numpy` 103, `fractions` 96. So the language takes the reductions the generators feed and the
census stops counting what is already t: (1) library ops `any(s)` and `all(s)` on a `seq<bool>` (total; `any([])`
is false, `all([])` true), `max(s)` and `min(s)` of one argument on a non-empty seq of ints or reals (DEFINED IFF
`len(s) > 0`; the two-argument forms stay), `toset(s)` the set of a seq's elements (total); Dafny carries them as
functions (the Std's `Max`/`Min` shape with their ensures, `ToSet` as the set comprehension), Verus as spec fns and
vstd's own `max`/`min`/`to_set` with `max_ensures`/`min_ensures` stated at every use over the parameters; the
other five abstain by name. Four committed tasks (`all_positive`, `has_negative`, `largest`, `members_upto`)
`verified / refuted` in both. (2) The census: a generator expression consumed by sum, join, any, all, max, min,
sorted, tuple, list, set, len or next is the burden `generator-consumed` (a comprehension under a library op), a
`yield` or any other generator stays the gap; a class whose methods never read `self` beyond calling each other is
the burden `class-wrapper` (its method is the function), a dataclass, NamedTuple or init-only class is the gap
`record` by name, a stateful class stays `class`; an import of collections, bisect, fractions, copy, string, array,
queue, decimal, or functools's lru_cache/cache alone is the burden `import-modelled` (maps, slices, reals, values,
literals), any other module stays the gap `import`. Bars: `surface.py --check`, the lab's grammar check (no new
rule: library names are identifiers), the in-fragment count and the gap table before and after, both printed in
the read. What would falsify the design: Dafny not proving `t_maxs(s) in s` without the Std's opaque-plus-lemma
shape, or Verus's `max_ensures` not reaching a `max(s)` inside a loop helper (then the read says which).

### T6 read (2026-10-06 15:33Z): reductions landed; the census corrected.
(1) `any(s)`, `all(s)`, `max(s)`, `min(s)` and `toset(s)` parse, type and round-trip (`surface.py --check`: 1,961 of
1,961 well-formed corpus tasks; no grammar rule changed, a library name being an identifier, so the lab's check
of 00:55Z stands); the checker refuses `any` of a seq of ints, `max` of a seq<bool> and `max` of one int by the
`lib-types` rule. (2) The interpreter agrees with Python's own `any`, `all`, `max`, `min` and `frozenset`; `max([])`
is undefined. (3) Dafny carries the five as functions in the Std's shapes (`t_maxs(s) in s` proved from the Std's
own `assert s == [s[0]] + s[1..]`, no opaque-plus-lemma needed: the first registered falsifier did not fire).
Verus: `largest` through vstd's `max()` and `max_ensures()` stated for the parameter; `all_positive` and
`has_negative` through the comprehension's spec fn and `t_all`/`t_any` were UNPROVED (Z3 had no term to
instantiate the two quantifiers on), repaired by writing a comprehension under `any`/`all` as the Verus quantifier
itself over the source's index; `members_upto` through the bare `to_set()` was UNPROVED (the membership needed the
witness index), repaired by two broadcast lemmas whose triggers are the goals a task states (`s.to_set().contains(
s[i])` and the slice form), then read TOOL_ERROR because the adapter's vacuity probe cannot copy a GENERIC lemma's
parameter list (the second falsifier's cousin, not foreseen), repaired by stating them over `Seq<int>`. All four
tasks `verified / refuted` in both kernels (the twins: a flipped comparison in the comprehension twice, a wrong
constant, an off-by-one slice bound); SPARK and F* abstain by name on the one-argument extrema and on any/all/toset.
(4) The census, measured before and after: in the fragment 1,892 -> 2,745 of 4,239 function-shaped (44.6% ->
64.8%); `generator-consumed` 1,444 (in), `class-wrapper` 719 (in), `import-modelled` 2,426 (in); the gaps left:
`import` 2,446 (itertools, re, heapq, functools.reduce, numpy, random, ...; the sole blocker for 310), `closure`
2,243 (201), `string-lib` 1,288 (203), `class` 902 stateful (27), `map-iteration` 535 (68), `exception` 502 (37),
`generator` 460 (24), `record` 390 (3; a class with fields and no behaviour, many of them linked-list nodes),
`none-type` 105 (61), `any-type` 142 (115). Of these the language items are the string library's missing members
(`split(sep)` with a longer or variable separator, `strip(chars)`, `index`, `rfind`, `zfill`, `center`/`ljust`/
`rjust`, `capitalize`, `swapcase`, `title`, `isspace`, `isalnum`, `splitlines`, `partition`; `format` and
`translate` stay out), records and options (constructors with fields), map iteration and closures as nested
helpers; the rest is the instrument's honesty about what no verifier should carry.

## T7 registered (2026-10-06 15:47Z, before any run): the string library's second wave, SPEC "The string library
(v2)"

The census after T6: `string-lib` is a gap on 1,288 problems (the sole blocker for 203), the largest language item
left; measured on the corpus's first solutions (01:00Z), the members used beyond v1 are, in order, `split(sep)` with
a longer or variable separator (part of 6,637 `split` calls), `index` 226, `format` 220, `rstrip`/`strip` with a
character set (part of 816), `translate`/`maketrans` 80, `capitalize` 21, `swapcase` 20, `center` 17, `rfind` 15,
`zfill` 14, `rjust` 13, `ljust` 10, `splitlines` 8, `isspace` 7, `isalnum` 6, `title` 6, `partition` 5. Read first
(receipt 608b2fa22b76): Python's str methods (the semantics of record, transcribed over tuples of code points as
the first wave was); Dafny's Std Strings module (number conversion only, nothing to borrow for these). The wave
takes fifteen members, each Python's exactly: `split(s, t)` on a sequence separator (owes `len(t) > 0`),
`strip/lstrip/rstrip(s, t)` with a character set, `index(s, t)` (owes `find(s, t) >= 0`), `rfind`, `zfill`,
`center/ljust/rjust(s, w[, f])`, `capitalize`, `swapcase`, `title`, `isspace`, `isalnum`, `splitlines`,
`partition(s, t)` (a 3-tuple; owes `len(t) > 0`), and two library names `isint(s)` and `toint(s)` (owes
`isint(s)`), the inverse of `tostr`. `format`, f-strings, `translate`, `encode` stay out by name. Bars: (1) parity
with Python's own methods on 2,000 random ASCII sequences per member (`test_strlib.py`), the notation round trip
for every form, the lab's grammar check with the new `strmember` names; (2) Dafny and Verus carry all fifteen in
their preludes with the ensures the committed tasks need (lengths and bounds), the other five abstain by name on
the second wave; four committed tasks (`pad_right_len`, `swap_prefix`, `last_pos`, `strip_dots`) `verified /
refuted` in both; (3) the census re-reads the v1 rule as v1 plus v2 and the `string-lib` gap shrinks by the
members' share, printed in the read. What would falsify the design: a Dafny prelude function whose ensures do not
verify on their own (then that member is stated without ensures and the task that needed them says so); Verus
needing an induction lemma for a bound the task states (then the lemma is added and the read says which).

### T7 read (2026-10-06 18:42Z): the string library's second wave landed, with three repairs found on the way.
(1) Fifteen members and two library names (`split` on a sequence separator, `strip/lstrip/rstrip` with a set,
`index`, `rfind`, `zfill`, `center/ljust/rjust` with an optional fill, `capitalize`, `swapcase`, `title`,
`isspace`, `isalnum`, `splitlines`, `partition`, `isint`, `toint`): parity with Python's own methods on 2,000 random
ASCII sequences per member (`test_strlib.py`), undefinedness where Python raises (`split`/`partition` on an empty
separator, `index` of an absent part, `toint` of a non-integer); the notation round trip 1,965 of 1,965.
(2) Dafny and Verus carry every member; `pad_right_len`, `swap_prefix`, `last_pos`, `strip_dots` are `verified /
refuted` in both. The second registered falsifier fired in Verus: `rfind`'s bounds needed a lemma (with `-1 <= i`
in its precondition), and the stripped length under a one-code-point set its own lemma form; Dafny's preludes
verified on their own (the first falsifier did not fire). The other five kernels abstain by name on the wave.
(3) Repairs: the padding members built a sequence as long as the width the twin search tried (the int ladder
reaches 2**31) and twice OOM-killed the session; they now stop at MAX_SEQ as `fill` and `join` do. The grammar
check, run on the desktop for the first time (its 22,569 raw replies against the lab's 7,150), found two
disagreements older than this wave: a simple statement with no terminator let `x := gap := [5]` read as `x := g`
then `ap := [5]`, and every string member took any argument list; both repaired (a simple statement ends with `;`,
whitespace or the block's `}`; members split by arity), 472 of 472 refusals now agree with acceptance unchanged.
Adding `index` to the census's string list read the field `self.index` of a heap node as a string use and dropped
MBPP 342 from the frozen wider panel (145 -> 144); the frozen pools keep the first wave's reading exactly
(`solution_tags(strlib_wave=1)`), the census reads both waves and ignores plain field accesses for the new names.
(4) Census: `string-lib` 1,288 -> 1,095 problems (sole blocker 203 -> 175); in the fragment 2,745 -> 2,773 of
4,239 function-shaped (65.4%). The lift report's exact counts were re-measured once the lab-only corpus came home:
all 77 programs lift and agree (was 76 of 77).

## T8 registered (2026-10-06 20:28Z, before any run): higher-order calls with lambdas, SPEC "Higher-order calls (v1)"

Measured first on the corpus's first solutions (21:00Z): of the uses behind the `closure` gap (2,243 problems), 419
are lambdas bound to a name (mostly stdin helpers such as `I = lambda: map(int, input().split())`) and 347 nested
defs of which 336 do not use `nonlocal`: local functions t already states as top-level helpers (a nested def
lifted with its read-only captures as parameters). The higher-order uses are sort keys 185 (`sorted` 107, `.sort`
78), `map` 68 and `filter` 26 (both already t's comprehensions), `max`/`min` keys 35 and `reduce` 24. Read first
(receipt b27338128981): Python's `functools.reduce` (left to right, the initial value first), `sorted` (stable),
`max`/`min` (the first maximal or minimal item). Bars: (1) a lambda `x => e` or `(a, x) => e`, allowed only as the
function argument of four library calls: `fold(f, init, s)` (a left fold), `sort_by(s, key)` (stable, by an int or
real key), `max_by(s, key)` and `min_by(s, key)` (the first extreme item; DEFINED IFF `len(s) > 0`); the notation
round trip, the grammar check, the checker's `lambda-position` and `hof-types`; (2) the interpreter is Python's own
on all four; the twins reach a lambda's body; (3) Dafny carries all four as per-instance recursive functions in
prefix form (fold and the extrema with their ensures proved by induction; `sort_by` as a stable insertion sort
with the length, the occurrence counts and the key order as ensures); Verus carries `fold`, `max_by` and
`min_by` and abstains on `sort_by` by name unless its sortedness lemma closes; the other five abstain by name.
Committed tasks: `longest_row` (max_by), `cheapest` (min_by over pairs), `by_second` (sort_by over pairs),
`weighted_sum` (a loop whose invariant is the fold over the prefix). (4) The census: lambdas under sort keys,
`max`/`min` keys, `map`, `filter` and `reduce`, a lambda bound to a name and a nested def without `nonlocal` are
in the fragment; `nonlocal` and other lambda positions stay the gap. What would falsify the design: Dafny not
proving the stable insertion sort's key order without an explicit lemma (then the lemma is written and the read
says so), or Verus's spec closures not reaching the per-instance definitions (then Verus abstains on all four).

### T8 read (2026-10-06 21:09Z): higher-order calls landed; Verus carries all four, `sort_by` included.
(1) The notation: `x => e` and `(a, x) => e`, only as the function argument of `fold(f, init, s)`,
`sort_by(s, key)`, `max_by(s, key)` and `min_by(s, key)`; the checker's `lambda-position` and `hof-types` (each with
its malformed file in `t/malformed/`); the round trip 1,969 of 1,969; the desktop grammar check 25,894 of 25,894
canonical forms and 22,569 of 22,569 raw replies accepted, 472 of 472 refusals agreed. (2) The interpreter is
Python's own on all four (`test_hof.py`, 915 checks: 300 random inputs, stability and the first extreme included;
`max_by`/`min_by` undefined on an empty sequence); the ladder reaches a lambda's body and swaps `max_by` and
`min_by`. (3) Dafny: all four, `verified / refuted` on `longest_row`, `cheapest`, `by_second` and `weighted_sum`.
The first registered falsifier fired, as the registration allowed for: the insertion sort's key order needed the two
explicit lemmas (a bound on an insertion's keys, order preservation) called inside the sort function. Two repairs on
the way. An invariant's `(a, y) => ...` and the ensures' `(a, x) => ...` were two functions, and `weighted_sum` read
unproved until the shape key renamed the lambda's parameters. `longest_row`'s twin had no certificate because the
ground evaluator read `r in rows` over a seq of seqs by hashing the rows; it now scans. Verus: the second falsifier
did not fire. Verus carries all four; the registration expected `sort_by` to abstain unless its sortedness lemma
closed, and it closed. A hand probe came first (14 verified, 0 errors), then the generator. `max_by`/`min_by` go
through the index of the chosen element. `sort_by` is the same insertion sort with three lemmas and vstd's
`to_multiset_ensures`, because vstd's own sort lemma requires an antisymmetric order, which a key comparison is
not. One repair older than the landing: Verus's ground evaluator did not read the length of a display of compound
elements, so every Verus certificate quantifying over a `seq<(int, int)>` parameter was refused. `cheapest`'s and
`by_second`'s twins read UNPROVED until it did, and the matrix shows whether older pair tasks move. SPARK, Frama-C,
Lean, Rocq and F* abstain by name. (4) Census: in the fragment 2,773 -> 2,959 of 4,239 function-shaped problems
(69.8%); stdin-shaped 9,839 -> 10,618 of 20,509; the gap `closure` 2,243 -> 707 problems; `functools.reduce` a
modelled import (the gap `import` 2,446 -> 2,372). The rule as run is stricter than registered. A nested def or a
lambda that mutates a name it captured (an append, a subscript or attribute store) stays the gap, because t's values
are immutable and lifting such a def does not keep its meaning. Measured by running the census without that clause:
the registered rule would have read 2,980 and 10,677, so the clause keeps out 21 function-shaped and 59 stdin-shaped
problems.

Time labels corrected in this file and in `internal/ROADMAP-LOG.md` (2026-10-06 21:09Z). The labels written from T2's
read onward were not read from a clock: they ran ahead of the real time by up to eleven hours, and four said 10-07.
Each is now the time the entry was written, taken from the session's own log, and each matrix entry carries its
table's own UTC stamp. Every "2026-10-07" in the repository (74 dating notes on Reductions and the string library's
second wave) is now 2026-10-06. The order of every registration before its runs is unchanged. A clock is read from
now on (`date -u`).

## T9 registered (2026-10-06 21:23Z, before any run): the library in Lean, the first landing of the depth programme

`internal/RESEARCH-2026-10-06-landscape.md` decision D1: the five kernels carry what the language already has, before
more breadth. Lean refuses 18 of the 84 committed tasks for "The library (v1)" (and Rocq and Frama-C the same 18), the
largest single block of refusals in the matrix. Read first (receipt 14c792546549): core Lean 4.33's `List.mergeSort`
("a stable merge sort") with `mergeSort_perm`, `length_mergeSort`, `mem_mergeSort` and `pairwise_mergeSort`
(sorted under a total, transitive comparison); `List.sum_append`, `List.getElem_reverse`, `List.foldl_append`;
`Int.gcd` (a Nat); the reference's `grind` chapter (linear integer arithmetic, a commutative ring solver,
E-matching over `@[grind]`-annotated library lemmas). No Mathlib: this column is core Lean only. Bars: (1) Lean
verifies the real and refutes the twin on at least 12 of the 18 tasks, with every theorem's `#print axioms` free
of `sorryAx`; (2) the rest are refused by name with the reason stated: `members_upto` (finite sets, not in core
Lean), `pad_right_len` (the string library's second wave), and any other op that does not close, named; (3) no
Lean cell that agreed before changes, measured by the clean-clone matrix; (4) the definitions are Python's (and t's
interpreter's) semantics: `sort` and `sort_by` are `mergeSort` itself, not merely a sorted permutation, since a
stable sort is unique. What would falsify the design: `grind` not closing the sorted-output ensures from
`pairwise_mergeSort` without an explicit instance (then the lowering states the instance, and the read says so);
a ground certificate over `mergeSort` not reducing by `decide` (then that certificate is refused by name and the
twin reads UNPROVED, a cell the read counts against bar 1).

### T9 read (2026-10-06 21:53Z): the library in Lean, 16 of the 18 tasks verified with the twin refuted.
(1) Bar 1 held: Lean verifies the real and refutes the twin on 16 of the 18 tasks it refused for the library:
`clamp`, `cube`, `distance`, `gcd_of`, `has_elem`, `largest`, `palindrome`, `root_floor`, `sum_one`,
`sum_tail`, `first_sorted`, `sort_it`, `all_positive`, `has_negative`, `weighted_sum` (a fold in a loop
invariant) and `longest_row` (`max_by`). Every theorem's audit is free of `sorryAx`. (2) Bar 2 held: the other
two refuse by name, `members_upto` (`toset`: core Lean has no finite set) and `pad_right_len` (the string
library's second wave); `sort_by` is refused by name too. (3) Bar 3 held: the whole Lean column was re-run over
the 88 tasks. Only those 16 cells moved, from refusal to verified with the twin refuted; the two older non-agreeing
cells (`count_vowels`, `grid_row_sums`) are unchanged. Lean goes from 40 to 56 and its refusals from 46 to 30.
(4) The second registered falsifier fired on the hand probe, before the generator was written: a well-founded
definition does not reduce under `decide`. That covers core's `List.mergeSort`, `isqrt` and `pow` by
`termination_by`, and `native_decide` is banned. Every library function is therefore structurally recursive, and
`sort` is our own stable insertion sort, the list Python's `sorted` gives, with its own permutation, order,
length and membership lemmas. The first falsifier never came into play, since `mergeSort` was not used. Three more
findings on the way. `grind` did not instantiate `isqrt`'s bound lemma, neither as a conjunction nor as three
single facts; a `grind_pattern` on `t_isqrt n` did. Handing grind the append lemma for `sum` on a goal with no
concatenation unfolded `[x]` against `?s ++ ?t` until the heartbeat budget ran out (`sum_one`'s twin read
TIMEOUT), so the lemma is handed over only where a sequence `+` occurs. A primed lemma name (`t_maxs_mem'`)
broke the adapter's audit pattern, which reads names between single quotes, and the real read UNPROVED.
`any`/`all` over a comprehension are core's `List.all`/`List.any` over a predicate, carried to the index
quantifier by two bridge lemmas; the shared comprehension rule now lets a kernel say it carries a comprehension
directly under them (`tshape.has_comprehension(under_reduction_ok=)`).

## T10 registered (2026-10-06 21:57Z, after one hand probe and before the generator): the library in Rocq

D1's second landing (`internal/RESEARCH-2026-10-06-landscape.md`). Rocq refuses the same 18 tasks as Lean did for
the library. Stated plainly: a hand probe ran before this registration (scratch `p1.v`, seven shapes: clamp,
distance, gcd_of, cube, root_floor, has_elem, sum_tail, written over the file's own sequence encoding, a function
`Z -> Z` with a length). All seven compiled closed under the global context, with ground values by
`reflexivity`. The bars below are about the generated lowering, which has not run. Read first: the stdlib's
`Z.sqrt_spec`, `Z.gcd_nonneg`, `Z.abs_nonneg`, `Z.pow_succ_r`, `Permutation` and `Sorted` (all present in
the installed stdlib, checked with `Check`); `lia`'s preprocessing of `Z.min`/`Z.max`/`Z.abs`. Design: `min`,
`max`, `abs`, `gcd`, `pow`, `isqrt` are the stdlib's own `Z` functions with their lemmas stated at the use.
`sum`, membership, `max`/`min` of one argument, `any`/`all`, `fold`, `max_by`/`min_by` are fuel
`Fixpoint`s over `Z.to_nat` of the length (the file's own idiom), recursing from the end, so a prefix's value is
one unfolding from the next. `rev` is `fun k => f (n - 1 - k)` and `sort` a stable insertion sort over the
listed elements. Bars: (1) Rocq verifies the real and refutes the twin on at least 12 of the 18; (2) the rest refuse
by name, with `members_upto` (sets in this column are `MSetList`, not reached by `toset` yet) and
`pad_right_len` (strings v2) expected among them; (3) no Rocq cell that agreed before changes (the whole column is
re-run); (4) every theorem closed under the global context. What would falsify the design: the file's proof engine
(`t_sweep`/`t_base`) not reaching a library lemma stated at the use (then a `pose proof` line names it, and the
read says which); a ground certificate over a fuel `Fixpoint` not reducing by `reflexivity` (then that twin reads
UNPROVED, counted against bar 1).

### T10 read (2026-10-06 22:18Z): the library in Rocq, 14 of the 18 tasks verified with the twin refuted.
(1) Bar 1 held: Rocq verifies the real program and refutes the twin on 14 of the 18 tasks it refused for the library:
`clamp`, `distance`, `gcd_of`, `cube`, `root_floor`, `has_elem`, `sum_one`, `sum_tail`, `largest`,
`palindrome`, `first_sorted`, `sort_it`, `all_positive`, `has_negative`. (2) Bar 2 held: `members_upto`
(`toset`), `pad_right_len` (strings v2), `weighted_sum` (`fold`) and `longest_row` (`max_by`) refuse by name;
the higher-order calls are this column's next item. (3) Bar 3 held: the whole Rocq column was re-run over the 88 tasks,
and exactly those 14 cells moved. Rocq goes from 43 to 57 verified with the twin refuted, its refusals from 45 to 31.
(4) Every theorem is closed under the global context. The first registered falsifier fired, as allowed: the proof
engine did not reach a library fact on its own, so each fact is posed at its use before `t_dis`, as a `pose proof`
line built from the call's own arguments (gcd's sign, isqrt's bounds, the extremum's facts, the sort's order, a sum
over a concatenation). Membership needed more. The engine does not case-split an arbitrary bool-valued call, so the
membership bridge is rewritten into the goal, the bool destructed, and the first branch closed in place. `any`'s
bool predicate needed a pointwise bool/Prop bridge rewritten under the binder (`setoid_rewrite`). The second
falsifier did not fire: ground values reduce by computation. One repair older than the landing: the certificate
builder handed the interpreter a witness sequence as a JSON list, so an ensures with a concatenation raised and was
skipped, and `sum_tail`'s twin had no certificate; witness sequences now enter as the interpreter's tuples. Membership
in a seq left Rocq's set detector, as it left Lean's.

## T11 registered (2026-10-06 22:20Z, after two hand probes and before the generator): the library in Frama-C

D1's third landing. After T9 and T10, ten committed tasks are kept from all-seven agreement by Frama-C alone; eight of
them are library tasks (`clamp`, `cube`, `distance`, `gcd_of`, `has_elem`, `palindrome`, `root_floor`,
`sum_one`). Stated plainly: two hand probes ran before this registration (scratch `p1.c`, `p2.c`, under the
adapter's own WP flags without `-wp-rte`: the integer pieces 64 of 65 goals, the one open goal an overflow check
the adapter does not ask for; the sequence pieces 42 of 42). The bars are about the generated lowering, which has not
run. Design: the library as ACSL `logic` definitions (recursive ones with the termination lemma this file already
emits for a recursive spec function, proved by WP, never assumed), and in executable position small C helper
functions whose loops mirror the logic recursion one step per iteration, each with its own contract proved once and
called from the task's body, the pattern the string library already uses (`t_count_c`). Membership in a seq in
ACSL is the existential over indices. `sum` of a display is its definitional unfolding (`sum([x])` is `0 + x`);
a sum over a concatenation is not rewritten by a law. Bars: (1) Frama-C verifies the real and refutes the twin on
at least 6 of the 8, and the all-seven count rises by the same number; (2) the rest refuse by name; (3) no Frama-C
cell that agreed before changes (the whole column is re-run); (4) no ACSL `axiom` is emitted. What would falsify the
design: WP not closing a helper's contract inside the adapter's step budget (then that helper is refused by name), or
a twin's certificate not reaching a library call (then that twin reads UNPROVED, counted against bar 1).

### T11 read (2026-10-06 22:31Z): the library in Frama-C, 8 tasks verified with the twin refuted, 7 of them reaching all seven.
(1) Bar 1 held: Frama-C verifies the real program and refutes its twin on 7 of the 8 tasks registered (`clamp`,
`cube`, `distance`, `gcd_of`, `has_elem`, `root_floor`, `sum_one`) and on `largest` besides. Those seven were
blocked by Frama-C alone, so the all-seven count should rise from 36 to 43; the clean-clone matrix measures it. (2) Bar 2
held: `palindrome` refuses by name (`rev`, a sequence value built in code), as do `sort`, `any`/`all`, `toset`
and a sum over a concatenation. (3) Bar 3 held: the whole Frama-C column was re-run over the 88 tasks; only those 8
cells moved, Frama-C from 36 to 44 verified with the twin refuted, its refusals from 51 to 43. (4) Bar 4 held: no ACSL
axiom; every recursive logic definition carries its termination lemma, proved by WP (the prelude alone proves 105 of
105 goals). Neither registered falsifier fired. What did fire was the adapter's structural backstop: one recursive
definition without its own termination lemma (`t_mins`, which shared `t_maxs`'s) read the whole task vacuous, and each
now has its own. Two certificate repairs belong to this landing. The replay's ground evaluator gained the library's
operators; it had refused every twin that called one. min, max and abs are replayed as their `ite`, resolved
branch-free: a live `?:` arm at ground values is dead code to the smoke tests, which read `clamp`'s and `distance`'s
twins UNPROVED. Membership in a seq left Frama-C's set detector, as in Lean and Rocq.

Measured (2026-10-06 22:49Z, the matrix regenerated from a clean clone at 3c9d721b, 88 tasks, 7 kernels): all seven
went from 36 to 43, the count this read predicted. Exactly the 22 cells T10 and T11 named moved (14 Rocq, 8 Frama-C)
and no other cell in any column; every kernel still refutes the twin of every real it verifies (100%). Frama-C is now
the only kernel keeping a task in six columns out of all seven: `double_all`, `palindrome` and `swap_rows`.

## T12 registered (2026-10-06 22:32Z, before any run): comprehensions in Lean

D1's fourth landing. Seven committed tasks state a comprehension (`doubled`, `squares`, `evens`, `diffs`,
`every_other`, `odd_positions`, `count_evens_skip`) and all five of SPARK, Frama-C, Lean, Rocq and F* refuse
them by name. Lean first, because its higher-order calls (T9) already have the shape a comprehension needs. Design:
each comprehension shape (variable, filter, body, and whether the source is a seq or an int range) becomes one
function in prefix form by structural recursion over `Nat`, appending the element's image when the filter holds,
so a prefix's value is one unfolding from the next and ground values evaluate under `decide`. A seq source `s`
is `(s, s.length)`, a prefix `s[0..e]` is `(s, e.toNat)`, a range `[lo, hi)` is `(lo, (hi - lo).toNat)`. The
lemmas each shape needs are generated with it and proved by induction: a map's length and element, a filter's length
bound and that every element satisfies the filter, all stated at an int index, the form the ensures use. A partial
body (`diffs`'s `s[i + 1] - s[i]`) is lowered only when its definedness holds at every index of the source, as
Dafny's comprehension precondition does. Bars: (1) Lean verifies the real and refutes the twin on at least 5 of the
7, with `count_evens_skip` expected among the refusals (it needs early exits, which Lean refuses by name);
(2) the rest refuse by name; (3) no Lean cell that agreed before changes, measured by re-running the whole column.
What would falsify the design: grind not reaching the element lemma through an append at an int index (then the
lemma is stated at the exact index shape the ensures use, and the read says so); a filter's element property not
following by induction without a permutation fact (then `evens` refuses by name).

### T12 read (2026-10-06 22:48Z): comprehensions in Lean, 5 of the 7 tasks verified with the twin refuted.
(1) Bar 1 held: Lean verifies the real and refutes the twin on `doubled`, `squares`, `evens`, `diffs` and
`every_other`. (2) Bar 2 is partly missed. `count_evens_skip` refuses by name (early exits), as registered, but
`odd_positions` does not refuse: it reads UNPROVED with its twin refuted. Its ensures read `s[(2 * k + 1).toNat]!`,
the slice lemma gives `s[(1 + 2 * k).toNat]!`, and a commuted form of the lemma did not close it either. It is an
honest UNPROVED, not a false verdict, and it is left open. (3) The whole Lean column was re-run over the 88 tasks:
the five cells above moved from refusal to verified with the twin refuted, and `odd_positions` from refusal to
UNPROVED. One more cell moved, `sum_tail`, from verified/refuted to verified/timeout: the run shared the machine
with a clean-clone matrix. Its twin takes 5 min 22 s alone and does refute, and its lowering is now byte-identical
to the committed one, because the commuted slice lemma is emitted only beside a comprehension. Lean: 56 -> 61
verified with the twin refuted, 30 -> 24 refusals. (4) The second registered falsifier did not fire: the filter's
property follows by induction. The first did, in a different place than predicted. grind reached the element lemma
through the append, but not through `0 + i` under `toNat`, so a range from 0 gets its own corollary with
`0 + i` simplified, which closed `diffs`.

Measured (2026-10-06 23:23Z, the matrix regenerated from a clean clone of t-proof-engine at 1dfc4f9f, the first one run
from the engine's own repository): exactly the six Lean cells this read names moved, and no other cell in any column.
`sum_tail`'s twin, which had timed out once under load in the column re-run, refutes. Lean: 61 verified with the twin
refuted, 3 carried and not proved, 24 refusals by name. All seven stays 43: SPARK, Frama-C, Rocq and F* still refuse
the comprehension tasks.

## T13 registered (2026-10-06 23:12Z, after a lowering-only pass and before any kernel run): AlgoVeri's contracts in seven kernels

D2 of `internal/RESEARCH-2026-10-06-landscape.md`. AlgoVeri states 77 classical algorithms with identical contracts in
Dafny, Verus and Lean (github.com/haoyuzhao123/algoveri at 8e313b0e, Apache License 2.0). Of the 77, 22 use only
what t states: 17 as written, and 5 with the permutation stated as equal length and equal occurrence counts. 21 of the
22 are now written in t under `t/algoveri/`, each with a program that meets its contract. Each was verified in Dafny,
with its twin refuted, while it was written. The 22nd, `k_smallest`, is not stated: its `ensures` is an existential
over a sequence, which t's bounded quantifiers cannot say as written. `sort(v)[k] == res` would be an equivalent
statement, and it is left for a registration of its own. `t/algoveri/MAPPING.md` gives every clause beside its t form
and names each departure from the letter of the Dafny text.

**Measured before any kernel ran.** A lowering-only pass, which gives no verdict, shows the tasks each kernel carries.
The rest are refused by name.

| kernel | carried |
|---|---|
| Dafny | 21 |
| Verus | 21 |
| SPARK | 14 |
| F* | 14 |
| Lean | 8 |
| Rocq | 3 |
| Frama-C | 2 |

Only `fast_exponential` and `integer_exponential` are carried by all seven. The pass found one unnamed failure: F*'s
spec functions over a `seq<seq>` raised TypeError. It was fixed before this registration (c31b5ca).

**Bars.**
(1) Dafny verifies the real program and refutes the twin on all 21.
(2) In every kernel, the twin of every real program it verifies is refuted (100%).
(3) No cell is an unnamed failure (MALFORMED, or a lowering error); every refusal is by name.
(4) Of the carried tasks, these are verified with the twin refuted:

| kernel | predicted |
|---|---|
| Verus | 10 to 18 of 21 |
| SPARK | 5 to 11 of 14 |
| F* | 5 to 11 of 14 |
| Lean | 3 to 7 of 8 |
| Rocq | 1 to 3 of 3 |
| Frama-C | 1 to 2 of 2 |

(5) All seven: 0 to 2.

**Why the ranges are wide.** These proofs were written for Dafny, with lemmas and loop splits tuned to its resource
limit, and they are carried mechanically into six other kernels. No proof this size has gone through the other
lowerings before.

**Not comparable with AlgoVeri's results.** Its best model reached 40.3% in Dafny, 24.7% in Verus and 7.8% in Lean.
Those numbers measure a model writing a verified program. These programs were written with iteration against
Dafny, and the comparison here is between kernels on one statement.

**What would falsify the design:**
- a kernel that verifies a real program and does not refute its twin (a decorative or unsound cell);
- Dafny failing to re-verify a program it verified while it was written (a proof too close to its resource limit to
  be stable).

### T13 read (2026-10-06 23:51Z): AlgoVeri in seven kernels. Dafny 21 of 21; the other kernels far below their ranges, and 13 unnamed failures.

The table is `t/ALGOVERI.md`, from a clean clone at bc60bb4. A first run was stopped before it finished, because both
polynomial tasks declared the name `poly_multiply`, which keys a table row and the lowered files. `cli.py verify` now
refuses that before anything is lowered, and the tasks are `poly_multiply_naive` and `poly_multiply_karatsuba`.

(1) **Bar 1 held:** Dafny verifies the real program and refutes the twin on all 21.

(2) **Bar 2 missed in Verus.** `trial_division_naive` verifies with its twin UNPROVED. The twin's certificate did not
close, so it is neither refuted nor decorative. Every other kernel refutes the twin of every real it verifies.

(3) **Bar 3 missed: 13 cells are MALFORMED.** Each comes from a lowering defect that 88 small tasks never reached, and
each is now named:

- **Verus, 5 cells.** Four are "Could not automatically infer triggers", where a bound variable is read only inside a
  nested quantifier: `kmp`, `matrix_multiply`, `merge_sort` and `quick_sort`. T15 is this repair; under it,
  `quick_sort` verifies (37 verified, 0 errors at the adapter's budget). The fifth, `poly_multiply_naive`, is a shape
  T15 does not cover: an index into an `update` expression at the top level.
- **SPARK, 2 cells** (`solve_longest_common_subsequence`, `string_search_naive`). An operator on the functional
  `Sequence` type is used without a `use type` clause: "operator for private type Sequence ... is not directly
  visible".
- **F*, 6 cells.** In three, a nested quantifier inside a spec function's body renders the inner variable out of scope
  (Error 72, "Identifier not found"): `binary_search`, `linear_search`, `longest_palindromic_substring`. In the other
  three, a `Tot bool` spec function calls a ghost quantifier helper (Error 34, "GTot is not compatible with Tot"):
  `bubble_sort`, `insertion_sort`, `kmp`.

(4) **The counts, against the predicted ranges**, as tasks verified with the twin refuted:

| kernel | measured | predicted | |
|---|---|---|---|
| Verus | 5 (6 reals proved) | 10 to 18 | missed |
| SPARK | 3 | 5 to 11 | missed |
| F* | 3 | 5 to 11 | missed |
| Lean | 0 | 3 to 7 | missed |
| Rocq | 1 | 1 to 3 | held |
| Frama-C | 2 | 1 to 2 | held |

The rest of the carried cells read UNPROVED or TIMEOUT.

(5) **Held:** all seven is 0. `integer_exponential` is verified with the twin refuted in six kernels, and Lean leaves
its real UNPROVED.

**What it bought.** The prediction was wrong because these are proofs written for Dafny: lemmas, loop splits and
helper methods tuned to its resource limit, carried mechanically into six kernels that each need their own
instantiation hints. The ranges assumed the 88 small tasks' rates would carry over, and they did not. The useful half
is the defect list. AlgoVeri found 13 malformed cells in four lowerings, under six distinct causes, none of which the
committed tasks reach. Each is now a named repair, the first of them (T15) already registered. The registered
falsifier about Dafny's stability did not fire: all 21 re-verified from a clean clone.

## T14 registered (2026-10-06 23:19Z, after the generator and before any kernel run): comprehensions in Rocq

D1's fifth landing. Seven committed tasks state a comprehension, and Rocq refuses all seven by name: `doubled`,
`squares`, `evens`, `diffs`, `every_other`, `odd_positions` and `count_evens_skip`.

**Design.** Rocq's sequences in this lowering are a function from `Z` with a length, so a map needs no construction:

- over a seq, `(fun k => body[x := s k], len s)`;
- over a range, `(fun k => body[i := lo + k], Z.max 0 (hi - lo))`, with the index alone when `lo` is the literal 0.

The body owes its definedness at every element of the source, so `diffs` owes `0 <= i + 1 < len(s)` on its range.
A filter needs a construction that this landing does not build: a fuel Fixpoint appending at the end, with its length
bound and element lemma, the shape of the stdlib's `filter` (receipt f42c30edd14b). So `evens` refuses by name (a
filter), and so does `count_evens_skip` (early exits, before its filter is reached). The generator is written. All
88 Rocq lowerings were compared before and after: exactly those seven changed, five from a refusal to a lowering and
two to a narrower refusal.

**Bars.**
(1) Rocq verifies the real program and refutes the twin on at least 4 of the 5 maps (`doubled`, `squares`, `diffs`,
`every_other`, `odd_positions`).
(2) `evens` and `count_evens_skip` refuse by name.
(3) No Rocq cell that agreed before changes; the whole column is re-run.
(4) The all-seven count does not move with this landing: SPARK, Frama-C and F* still refuse every comprehension
task.

**What would falsify the design:**
- `t_dis` not closing a goal that holds a beta-redex under the unfolded definitions (then the definitions are
  reduced with `cbv beta` first, and the read says so);
- a twin's certificate not evaluating the function at its witness (then that twin reads UNPROVED, counted against
  bar 1).

### T14 read (2026-10-06 23:30Z): comprehensions in Rocq, all 5 maps verified with the twin refuted.

(1) Bar 1 held, at 5 of 5: Rocq verifies the real program and refutes its twin on `doubled`, `squares`, `diffs`,
`every_other` and `odd_positions`. `odd_positions` is among them; Lean leaves it UNPROVED, because the index sum sits
under `toNat` in Lean and is plain `Z` here.
(2) Bar 2 held: `evens` refuses as a filter, and `count_evens_skip` for its early exit.
(3) Bar 3 held: the whole Rocq column was re-run over the 88 tasks, and only those five cells moved. Rocq goes from 57
to 62 verified with the twin refuted, and its refusals from 31 to 26.
(4) Bar 4 held as registered: all seven stays 43, since SPARK, Frama-C and F* still refuse every comprehension task.

Neither registered falsifier fired. `t_dis` closed every goal with a beta-redex under the unfolded definitions, and
each twin's certificate evaluated the function at its witness.

One operational finding, not a verdict: a Rocq-only column at three cells in flight runs about five `rocqworker`
processes per cell at about 420 MB each. Its first launch under a 5 GB cap was OOM-killed in ten seconds, and the
rerun under 8 GB peaked at 7.4 to 7.8 GB. A Rocq column runs at two cells per 5 GB, or at three under 8 GB.

## T15 registered (2026-10-06 23:39Z, after hand probes and before the kernel run): Verus triggers for an index read only inside a nested quantifier

**Found by T13's first, stopped run.** Verus read three AlgoVeri cells MALFORMED, all from one cause: "Could not
automatically infer triggers". In each, a quantifier's bound variable is read only inside a nested quantifier:

- `matrix_multiplication`: `A[i]` appears only in the inner bound `A[i].len()` and in `A[i][j]`.
- `kmp`: `fail[q]` appears only in an inner lower bound.
- `merge_sort`: the index is into an expression, `(m + seq![e])[i]`.

Verus does not look inside a nested quantifier for the outer one's trigger. The existing nested-quantifier branch
collects only indexes of a plain variable in the inner body, and only when no top-level root exists.

**Design** (Verus guide, "forall and triggers", receipt ed77e77a7f2c). When the body has no indexable term outside
nested quantifiers, the outer quantifier gets an explicit `#![trigger X[v]]` for each such index term found inside
them. That covers terms in their bounds or their bodies, with any base `X` that mentions no inner bound variable.

**Measured before this registration, stated plainly:**
- The Verus lowerings of all 88 committed tasks are byte-identical.
- Three minimal programs of the three shapes each verify in Verus (2 verified, 0 errors).
- The three AlgoVeri files now compile. At rlimit 50, above the adapter's 10, Verus reads postconditions or
  assertions not proved in all three.

**Bars.**
(1) None of the three AlgoVeri Verus cells is MALFORMED; each reads a named outcome.
(2) No Verus cell over the 88 committed tasks changes; their lowerings are identical.
(3) **Prediction:** 0 of the 3 verify at the adapter's budget. These are Dafny-tuned proofs, and the probes at a
higher budget did not close.

**What would falsify the design:** a trigger the guide's rules reject (Verus refuses it), or one of the three still
MALFORMED for another reason.

### T15 read (2026-10-06 23:53Z): Verus triggers for an index read only inside a nested quantifier. No MALFORMED left among them; `quick_sort` verifies.

The Verus column was re-run over the 21 AlgoVeri tasks at ef68ff5. Against T13's table, exactly four cells moved:

| task | T13 | T15 |
|---|---|---|
| `kmp` | malformed / malformed | unproved / refuted |
| `merge_sort` | malformed / malformed | unproved / refuted |
| `matrix_multiply` | malformed / malformed | unproved / unproved |
| `quick_sort` | malformed / malformed | verified / refuted |

(1) **Bar 1 held:** none of the three registered cells is MALFORMED, and each reads a named outcome.
(2) **Bar 2 held:** the Verus lowerings of all 88 committed tasks are byte-identical.
(3) **The prediction held:** 0 of the 3 registered cells verify. `quick_sort`, the fourth of the same class, not named
in the registration because the first run was stopped before reaching it, verifies with its twin refuted.

Verus on AlgoVeri goes from 5 to 6 verified with the twin refuted. `poly_multiply_naive` stays MALFORMED. It is the
shape T15 does not cover, an index into an `update` expression at the top level, for which Verus also infers no
trigger. That is the next Verus repair. `trial_division_naive`'s twin certificate remains unproved.

## T16 registered (2026-10-06 23:46Z, after hand probes and before the column run): comprehensions in F*

D1's sixth landing, the comprehension tasks' next kernel after Lean (T12) and Rocq (T14). F* refuses all seven by name.

**Design** (receipt d2d097513c74, FStar.Seq.Base). Each map shape is one function `t_compK` in Dafny's prefix form:
over a seq `(t_s, t_n)`, over a range `(t_a, t_n)`, then the body's free variables. It is built by `Seq.init`, with one
call of `Seq.init_index`, which Base gives no SMT pattern, so the function's own postcondition carries the length and
every element to each call site.

The body's definedness is the function's precondition, split as Dafny's lowering splits it:
- conjuncts that do not mention the element are stated once, as `t_n > 0 ==> ...`;
- the rest form a quantifier triggered on the element, `Seq.index t_s t_di`, or over a range `t_ix t_di` through an
  identity function, since F* runs Z3 without MBQI.

A filter, and a comprehension inside a spec_fun, method or lemma, refuse by name, so `evens` and `count_evens_skip`
(early exits) refuse.

**Measured before this registration, stated plainly.** Hand probes under the adapter's own Z3 version, seed and
budget: all five maps' real files verify (`doubled`, `squares`, `diffs`, `every_other`, `odd_positions`). The first
probe of `odd_positions` failed. Its slice's bound mentions no element, so nothing triggered the quantifier before
the slice was typed. That is Dafny's measured case, and the split above repaired it. The F* lowerings of the other
81 committed tasks are byte-identical.

**Bars.**
(1) F* verifies the real program and refutes the twin on at least 4 of the 5 maps.
(2) `evens` and `count_evens_skip` refuse by name.
(3) No F* cell that agreed before changes; the whole F* column is re-run.
(4) All seven stays 43: SPARK and Frama-C still refuse every comprehension task.

**What would falsify the design:** a twin whose certificate does not reach the comprehension's value (then that twin
reads UNPROVED, counted against bar 1), or a quantifier pattern that fires in the probe and not in the adapter's run.

### T16 read (2026-10-06 23:52Z): comprehensions in F*, all 5 maps verified with the twin refuted.

(1) **Bar 1 held, at 5 of 5:** F* verifies the real program and refutes its twin on `doubled`, `squares`, `diffs`,
`every_other` and `odd_positions`.
(2) **Bar 2 held:** `evens` refuses as a filter, and `count_evens_skip` for its early exit.
(3) **Bar 3 held:** the whole F* column was re-run over the 88 tasks, and only those five cells moved. F* goes from 53
to 58 verified with the twin refuted, and its refusals from 33 to 28.
(4) **Bar 4 held as registered:** all seven stays 43. The five maps are now verified with the twin refuted in Dafny,
Verus, Rocq and F*, and in Lean for four of them. SPARK and Frama-C are the two kernels between them and all seven.

Neither falsifier fired. Each twin's certificate states the measured value of the twin's comprehension, and the
quantifier patterns fired under the adapter's own run as they did in the probes.

## T17 registered (2026-10-07 00:07Z, after hand probes and before the column runs): T13's SPARK and F* repairs

T13's read named eight MALFORMED cells in SPARK and F*. Four repairs, each the smallest change that makes the cause
go, are written. Each is measured byte-identical on the 88 committed tasks except where named.

**SPARK** (4051116, receipt 43cfb88d4b64). A seq local carried into a loop function's precondition is compared by
the qualified `Seqs."="`, so gnatprove no longer refuses the file. All 88 SPARK lowerings are identical.

**F*, three repairs.**
- A computational-position quantifier's helper no longer takes domain obligations that mention a nested
  quantifier's variable, and its logical binder is fresh when the body already uses `j`. This fixes the out-of-scope
  `j` (Error 72) in `binary_search` and `linear_search`.
- `in` left F*'s set detector, as it left Lean's, Rocq's and Frama-C's. A task with seq membership is no longer put
  in the Ghost effect, where its `Tot` spec functions could not call their helpers (Error 34). Of the 88, only
  `has_elem`'s lowering changes, and it still verifies with its twin refuted (measured, one-file run).
- A lemma's SMT pattern takes only calls over its own parameters, never a call under its ensures' quantifier.

**Hand probes, stated plainly** (the adapter's Z3 version, seed and budget, real side):
- verified: `binary_search`, `linear_search`;
- compile, with proof obligations unproved (Error 19): `bubble_sort`, `insertion_sort`, `kmp`;
- still Error 72, an index that is a function of the helper's own bound variable (`s[len(s) - 1 - i]`, which needs
  an endpoint argument not written here): `longest_palindromic_substring`.

The two SPARK files compile under gnatprove with unproved checks.

**Bars.**
(1) Of the eight cells, at most one stays MALFORMED (`longest_palindromic_substring` in F*).
(2) **Prediction:** F* verifies `binary_search` and `linear_search` with the twin refuted. SPARK verifies neither of
its two.
(3) No F* cell over the 88 moves except, possibly, `has_elem`, and that one stays verified with the twin refuted. The
whole F* column is re-run.

### T17 read (2026-10-07 00:24Z): T13's SPARK and F* repairs. 7 of the 8 cells leave MALFORMED; F* on AlgoVeri goes from 3 to 5.

The SPARK and F* columns were re-run over the 21 AlgoVeri tasks at a93accd, and the F* column over the 88.

(1) **Bar 1 held:** of the eight cells, only `longest_palindromic_substring` in F* stays MALFORMED, as registered.
SPARK's two read timeout with the twin refuted. F*'s `bubble_sort` and `insertion_sort` read timeout, and `kmp`
unproved, each with the twin refuted.
(2) **The prediction held:** F* verifies `binary_search` and `linear_search` with the twin refuted, and SPARK verifies
neither of its two. F* also now carries `merge_sort` (unproved, twin refuted), which its set detector had refused
for seq membership.
(3) **Bar 3 held:** in the whole F* column over the 88, no cell moved beyond T16's five, and `has_elem` stays verified
with its twin refuted.

On AlgoVeri, F* goes from 3 to 5 verified with the twin refuted (carried 16 -> 17), SPARK stays at 3, and Verus is
at 6 after T15. MALFORMED cells across AlgoVeri go from T13's 13 to 2: Verus's `poly_multiply_naive`, an index into an
update expression, and F*'s `longest_palindromic_substring`, an index that is a function of a computational
quantifier's own bound variable. Both are named and queued.

## T18 registered (2026-10-07 00:41Z, after hand probes and before the column run): comprehensions in SPARK

D1's seventh landing. After T16, only SPARK and Frama-C stand between the five map tasks and all seven.

**Design** (receipt a749e5e14241). Each map shape is one recursive expression function `T_CompK`, in the shape of
the file's own `T_Slice`:
- the Pre states the source's bound, a nonnegative count, and the body's definedness, split as in Dafny and F*;
- the Post states the length and every element over `T_Range`;
- a `Subprogram_Variant` on the count;
- the body is `Seqs.Add` of the last element onto the function at `T_N - 1`.

Two measured adaptations, both from the hand probes:
- Over a range, the count is clamped at the call site, because the variant on a possibly negative count failed its
  range check (`squares`). The index is written through an identity `T_Ix`.
- The recursion is guarded by `R_Has (T_Range'(0, T_N), T_N - 1)` instead of `T_N = 0`. A quantifier over T_Range
  is instantiated through its Has_Element term, and without that guard `diffs`' Pre was out of reach at `T_N - 1`
  even at five times the step budget.

A filter, and a comprehension inside a spec_fun, method or lemma, refuse by name.

**Measured before this registration.** All five maps' real files verify under the adapter's own `verify`. The SPARK
lowerings of the other 81 committed tasks are byte-identical, and the whole suite passes (691).

**Bars.**
(1) SPARK verifies the real program and refutes the twin on at least 4 of the 5 maps.
(2) `evens` and `count_evens_skip` refuse by name.
(3) No SPARK cell that agreed before changes; the whole SPARK column is re-run.
(4) All seven stays 43, because Frama-C still refuses every comprehension task.

**What would falsify the design:** a twin certificate that does not reach the comprehension's value (counted
against bar 1), or a verdict that depends on the step budget (a TIMEOUT where the probe verified).

### T18 read (2026-10-07 00:52Z): comprehensions in SPARK. 3 of 5 at the registered commit, 5 of 5 after a certificate repair.

(1) **Bar 1 missed at 48c59e3.** The whole SPARK column was re-run over the 88 tasks. SPARK verifies all five maps'
real programs, but refutes the twin on only three (`doubled`, `every_other`, `odd_positions`). The twins of `squares`
and `diffs` read TIMEOUT, because their files carried no refutation certificate.

The witness is undefined at the ensures: the twin's result is shorter, so `r[k]` falls past it. The certificate
builder's ensures-level branch could not render an obligation that names the return value, and it failed closed, as
its own note says it would. The repair binds the return to `F (inputs)`, as the "value" kind already does, when the
witness values every parameter. That `F` is an expression function whose value comes through the helper's proved
Post. Measured after the repair: both cells read verified with the twin refuted, from single-file runs. Only those
two tasks' SPARK files change; the other 86 are byte-identical.

(2) **Bar 2 held:** `evens` refuses as a filter, and `count_evens_skip` for its early exit.
(3) **Bar 3 held:** in the column, only the five comprehension cells moved. SPARK goes from 50 to 55 verified with the
twin refuted, counting the repaired two.
(4) **Bar 4 held:** all seven stays 43 for now. Frama-C is the last kernel that refuses the maps (T19, next).

## T19 registered (2026-10-07 00:52Z, after hand probes and before the column run): comprehensions in Frama-C

D1's eighth landing, and the last kernel between the four map tasks Lean verifies (`doubled`, `squares`, `diffs`,
`every_other`) and all seven.

**Design.** A map that is the whole right-hand side of an assignment to a seq is one write loop over the buffer, the
copy loop a slice already uses with the body's value in place of the source's element:
- the count is asserted equal to the buffer's length, as an ACSL term;
- each step asserts the body's definedness at its element;
- the invariant states every element written so far;
- the return's length is the map's closed form (the source's length, or `hi - lo`), so the buffer is EXACT;
- in the body, `s[a..b][i]` is read as `s[a + i]`, with the slice's definedness asserted, since Frama-C indexes only a
  buffer by name.

A filter, and a comprehension anywhere but an assignment's right-hand side, refuse by name.

**Measured before this registration.** All five maps' real files verify under the adapter's own `verify`. The first
probe found the count rendered by `cexpr`, whose branch-free division Frama-C rejects inside an annotation. It is
now an ACSL term. The Frama-C lowerings of the other 81 committed tasks are byte-identical, and the whole suite
passes (695).

**Bars.**
(1) Frama-C verifies the real program and refutes the twin on at least 4 of the 5 maps.
(2) `evens` and `count_evens_skip` refuse by name.
(3) No Frama-C cell that agreed before changes; the whole Frama-C column is re-run.
(4) **The headline:** all seven goes from 43 to 47 (`doubled`, `squares`, `diffs`, `every_other`), with
`odd_positions` held out by Lean's UNPROVED. The installed table moves only with a clean-clone matrix, which follows.

**What would falsify the design:** a twin whose certificate does not reach the buffer's written value (counted
against bar 1), or a verdict that differs between the probe and the adapter's run.

### T19 read (2026-10-07 01:16Z): comprehensions in Frama-C, 5 of 5. All seven goes from 43 to 47, measured from a clean clone.

(1) **Bar 1 held, at 5 of 5:** Frama-C verifies the real program and refutes its twin on all five maps.
(2) **Bar 2 held:** `evens` refuses as a filter, and `count_evens_skip` for its early exit.
(3) **Bar 3 held:** in the whole Frama-C column, only those five cells moved. Frama-C goes from 44 to 49.
(4) **Bar 4 held:** the matrix was regenerated from a clean clone of t-proof-engine at 1da32b3 (`t/AGREEMENT.md`).
All seven goes from 43 to 47: `doubled`, `squares`, `diffs` and `every_other` are verified with the twin refuted in
every kernel. `odd_positions` is held out by Lean's UNPROVED, as registered.

Against the previous installed table, exactly 20 cells moved: the five maps in Rocq (T14), F* (T16), SPARK (T18) and
Frama-C (T19). No other cell moved, and every kernel still refutes the twin of every real it verifies (100%).

| kernel | verified with the twin refuted |
|---|---|
| Dafny | 88 |
| Verus | 80 |
| Rocq | 62 |
| Lean | 61 |
| F* | 58 |
| SPARK | 55 |
| Frama-C | 49 |

**Next by all-seven gain.** Four tasks are one kernel short of all seven:
- `palindrome` (Frama-C: `rev` in a seq local needs a buffer);
- `swap_rows` (Frama-C: a nested-seq return);
- `double_all` (Frama-C: a timeout);
- `odd_positions` (Lean: UNPROVED).

Three tasks are two kernels short: `largest` (SPARK, F*: max of one argument, T21 next), `sum_tail` and
`grid_row_sums`.

## T21 registered (2026-10-07 01:20Z, after hand probes and before the clean-clone matrix): max/min of one argument in SPARK and F*

`largest` is two kernels short of all seven: SPARK and F* refuse `max(s)` by name.

**Design** (receipt dfe96e13d0c5). Both kernels take the prefix form the comprehensions use: the extremum of the
first n elements, recursive on n, with the two facts SPEC.md states (a member of the seq, and a bound on every
element).
- **SPARK:** the facts are T_Maxs's Post, the existential written the way T_Contains writes membership, and the
  recursion is guarded by R_Has.
- **F*:** one SMT-patterned induction lemma states them, the existential over an index, which FStar.Seq.Properties'
  patterned `seq_mem_k` carries to `Seq.mem`.

The call's precondition is the definedness obligation.

**Measured before this registration.**
- `largest` COUNTS in F*: verified, wrong-constant twin refuted.
- In SPARK the twin `max(s) + 1` first did not compile. `_ty` had read `max(s)` as a seq, making the `+` a
  concatenation. Read as an element, `largest` COUNTS in SPARK too.
- Of the 88 committed tasks, only `largest`'s SPARK and F* files change, and the whole suite passes (697).

**Bars.**
(1) The clean-clone matrix that follows reads `largest` verified with the twin refuted in SPARK and F*.
(2) No other cell moves.
(3) All seven goes from 47 to 48.

### T21 read (2026-10-07 01:38Z): max/min of one argument in SPARK and F*. All seven goes from 47 to 48.

The matrix was regenerated from a clean clone of t-proof-engine at 25e3491 (`t/AGREEMENT.md`).
(1) **Bar 1 held:** `largest` reads verified with the twin refuted in SPARK and in F*.
(2) **Bar 2 held:** no other cell moved; exactly these two moved against the installed table.
(3) **Bar 3 held:** all seven goes from 47 to 48.

Per kernel: Dafny 88, Verus 80, Rocq 62, Lean 61, F* 59, SPARK 56, Frama-C 49. Every kernel still refutes the twin
of every real it verifies (100%).

## T22 registered (2026-10-07 01:47Z, before any run): the common-mode audit, SPARK's half (D6)

Four of the seven legs run on Z3: Dafny through Boogie, Verus, F*, and SPARK as this engine pins it
(`--prover=z3`), although gnatprove's own default is CVC5 (receipt add8ff238c99). A solver-specific false proof
would then show up in four columns at once. This audit measures how much of SPARK's column depends on Z3. The
same files are re-run under gnatprove's bundled CVC5 and Alt-Ergo, through a new `T_SPARK_PROVER` switch. Its
default stays Z3, so the matrix of record is unchanged, and a non-default prover is named in the backend version.

**Bars.** Against SPARK's 56 cells verified with the twin refuted under Z3:
(1) Under CVC5, at least 50 of the 56 stay verified with the twin refuted.
(2) Under Alt-Ergo, at least 35 of the 56 do.
(3) No real program verified under Z3 is REFUTED under another prover. That would be a disagreement in kind, and
the first thing read. A TIMEOUT or UNPROVED under another prover is a budget or strength difference, since gnatprove's
`--steps` is prover-specific.
(4) Every twin refuted under Z3 is refuted under the other two. A certificate is one ground goal, which any of the
three should discharge.

**What would falsify the design of the audit:** gnatprove refusing a prover for these files (a tool error, not a
verdict), which would make that column unmeasurable rather than disagreeing.

T22's Frama-C half, registered 2026-10-07 01:49Z before its runs. WP's goals go to Alt-Ergo (pinned) and, through Why3 1.8.2,
to Z3 4.16.0 and CVC5 1.3.2 (registered with `why3 config detect`; Why3 does not recognize either exact version, so
its nearest drivers are used, which the read will say). A new `T_FRAMAC_PROVER` switch selects one; its default stays
Alt-Ergo. One-task check: `clamp` verifies with its twin refuted under all three.

**Bars**, against Frama-C's 49 cells verified with the twin refuted under Alt-Ergo:
(5) Under Z3, at least 40 stay verified with the twin refuted; under CVC5, at least 40.
(6) No real program verified under Alt-Ergo is REFUTED under Z3 or CVC5.

T22's Dafny half, registered 2026-10-07 01:50Z before its run. Boogie's CVC5 route (`--solver-path` to gnatprove's bundled CVC5
1.3.2, `/proverOpt:SOLVER=CVC5`, which Boogie marks experimental), selected by a new `T_DAFNY_SOLVER` switch whose
default stays Z3.

**One-task check, stated plainly:** `clamp`'s real verifies under CVC5, but its twin's certificate, a ground goal Z3
discharges, is UNPROVED: CVC5 gave up without exhausting its budget. So certificate acceptance itself can depend on
the solver, and the run measures how often.

**Bars**, against Dafny's 88:
(7) Under CVC5, at least 75 reals stay verified; the count with the twin also refuted is read as measured, not
predicted.
(8) No real verified under Z3 is REFUTED under CVC5.

Verus and F* run on Z3 alone and have no second solver here.


### T22 read (2026-10-07 02:12Z): the common-mode audit. No verified real is refuted under a second solver; three of the five count bars are missed.

Five alternate-solver columns ran over the 88 tasks (`/home/t/scratch/t-matrix/AGREEMENT-{spark-cvc5,spark-altergo,
framac-z3,framac-cvc5,dafny-cvc5}.md`). Each cell was compared with the installed table (clean18).

| leg | default | second solver | counted under default | still counted | real re-verified | real REFUTED |
|---|---|---|---|---|---|---|
| SPARK | Z3 | CVC5 1.3.2 | 56 | 48 | 48 | 0 |
| SPARK | Z3 | Alt-Ergo | 56 | 53 | 53 | 0 |
| Frama-C | Alt-Ergo | Z3 4.16.0 | 49 | 18 | 18 | 0 |
| Frama-C | Alt-Ergo | CVC5 1.3.2 | 49 | 33 | 33 | 0 |
| Dafny | Z3 | CVC5 1.3.2 | 88 | 0 (twin side unmeasurable, below) | 86 | 0 |

(1) **Missed:** under CVC5, 48 of SPARK's 56 stay counted (bar: 50). The eight lost reals are 6 UNPROVED and 2
TIMEOUT: diffs, every_other, has_duplicate, odd_positions, palindrome, reverse, squares, tail.
(2) **Held:** under Alt-Ergo, 53 of 56 (bar: 35). The three lost are UNPROVED: average, half_way, safe_ratio, the
tasks with reals and division.
(3) **Held:** no real verified under Z3 is REFUTED under CVC5 or Alt-Ergo.
(4) **Missed by one cell:** under Alt-Ergo, every twin is refuted. Under CVC5, `diffs`'s twin certificate times
out. That certificate unfolds the comprehension's recursive expression function at the witness, which is not one
flat ground goal.
(5) **Missed in both:** Frama-C under Z3 keeps 18 of 49 and under CVC5 33 of 49 (bar: 40 each).
   - The Z3 losses are 31 genuine timeouts. Rerun by hand with WP's cache off, `all_nonneg`'s loop-invariant and
     ensures goals are still open at 60 s, where Alt-Ergo proves them.
   - Under Z3, 8 twin certificates are also UNPROVED: count_matches, digit_sum, double_all, gcd_of, largest,
     min_max, row_max_len, seq_max. Each needs an ACSL recursive logic function evaluated at the witness.
   - Under CVC5, 9 reals are UNPROVED and 7 TIMEOUT, and every twin is refuted.
(6) **Held:** no real verified under Alt-Ergo is REFUTED under Z3 or CVC5.
(7) **Held:** under CVC5, 86 of Dafny's 88 reals verify (bar: 75). `first_sorted` and `sort_it` time out.
(8) **Held:** no real verified under Z3 is REFUTED under CVC5.

**Dafny's twin side under CVC5 is unmeasurable.** This is the registered falsifier, a tool error rather than a
verdict (receipt 04b99488c420).
- Every twin's main run is a failing proof, so Boogie asks the solver for a counterexample model.
- Boogie's model converter has no case for a Real value, and CVC5's model carries `0.0`, so Boogie throws
  `BadExprFromProver` before reporting any verdict.
- The certificates themselves verify under CVC5 when run alone. The adapter still refuses every one, correctly,
  because the main run printed no result.
- Dafny 4.11 sets `EnhancedErrorMessages = 1` whenever its counterexample option binding runs, so
  `/enhancedErrorMessages:0` is overridden. CVC5 refuses `produce-models=false` after initialization.
- No engine code changed. Accepting a crashed main run would weaken the certificate door.

**What it measures.** Over five columns and 298 cells that verify under the default solver, no second solver refuted
a verified real: a solver-specific false proof would have shown here, and none did. Re-verification by a second
solver:
- **SPARK:** all 56 of its counted reals are re-verified by CVC5 or Alt-Ergo, and their losses do not overlap.
- **Dafny:** 86 of 88.
- **Frama-C:** 33 of 49. The other 16 rest on Alt-Ergo alone: all_nonneg, any_neg_for, contains, diffs, every_other,
  first_even, has_duplicate, has_elem, largest, linear_search, min_max, remainder, reverse, root_floor,
  row_max_len, seq_max.

**Proof strength.** It is solver-specific, and much more so in Frama-C than registered. WP's encoding suits
Alt-Ergo, and Z3 loses 31 of 49 there.

**Twin certificates.** They are solver-robust when the certificate is one flat ground goal. They depend on the
solver when they must unfold a recursive function at the witness (1 cell in SPARK under CVC5, 8 in Frama-C under
Z3).

**Still open.** Verus and F* run on Z3 alone. Lean's cells have no independent re-check here (lean4checker is not
installed). Rocq's are re-checked by `coqchk`.

## T23 registered (2026-10-07 02:32Z, after hand probes and before the clean-clone matrix): datatypes with fields in Dafny, Verus and Lean (G9, first wave)

SPEC.md "Datatypes (v2): fields". Constructors carry int, bool or seq fields, which gives records and non-recursive
sums: `D.C(a, ...)`, `case` arms binding fields, `e.f`. Six tasks are added, making 94:
- `shape_area`: a three-constructor sum matched in requires, ensures and body;
- `manhattan`: a record;
- `rect_area`: field access under a discriminating requires;
- `some_negative`: an option built in a loop under a quantified invariant;
- `bag_size`: a bool and a seq field;
- `checked_tail`: a seq field, compared by structural equality.

Receipts: f28afa1d8db8 (Dafny), 2d503d12f07a (Verus), 134d11c182fc (Lean).

**Measured before this registration, stated plainly.**
- **Hand probes:** all six COUNT in Dafny, Verus and Lean on scratch runs (18 cells). `bag_size` was measured with
  its bool field named `open`, renamed `active` since, so that no committed task needs a keyword rename (`test_names`);
  its re-run under the committed name (finished 02:32Z) COUNTS in all three.
- **Defects the probes found and fixed:**
  - a witness showed a bool field as Python's `False`, which the parser cannot read back;
  - Verus read the datatype declarations before renaming a keyword-named field;
  - Verus derived `PartialEq` on an enum with a `Seq` field, which does not compile;
  - Lean's sign lemmas named match binders outside their scope;
  - Lean's preservation step `split` the contract's own Prop-valued match.
- **Byte identity:** every lowering of the 88 previous tasks and the 21 AlgoVeri tasks is unchanged: real and twin,
  all seven kernels, with the witness. The other four kernels refuse all six by name.
- **Suite:** the whole suite passes (686).

**Bars**, for the clean-clone matrix that follows:
(1) The six read verified with the twin refuted in Dafny, Verus and Lean: 18 cells.
(2) Rocq, F*, SPARK and Frama-C refuse all six by name: 24 cells.
(3) No cell of the 88 moves against the installed table.
(4) Per kernel: Dafny 94, Verus 86, Lean 67; the other four unchanged. All seven stays 48, now of 94.

## T24 registered (2026-10-07 02:49Z, after hand probes and before the clean-clone runs): AlgoVeri's discrete_logarithm, and five engine defects it found

`discrete_logarithm` is the first AlgoVeri contract that datatypes with fields make stateable. Its result is
`Option<int>`, and its helpers are `spec_pow_mod`, recursive on an int, and `is_discrete_log`. It is the 22nd
AlgoVeri program (`t/algoveri/MAPPING.md` names its two departures: a monomorphic `Option`, and total helpers).
Of the other 36 datatype contracts, `linearsys_gf2` needs a quantifier over all sequences. The remaining 35 need
recursive datatypes, set-valued helpers or graphs.

**Five defects, found while writing it and fixed:**
1. Lean's prelude declares `Option`: a datatype of that name was "already declared". A datatype named like an
   uppercase entry of `names.KEYWORDS["lean"]` is now emitted as `t_<name>` in Lean text.
2. Verus's `use Option::*` was ambiguous with Rust's prelude (E0659). For a prelude type name the import is now
   qualified `self::`. A datatype named `Seq`, `Set`, `Map` or `Multiset` is refused by name, since it would
   shadow the vstd type the lowering names.
3. Dafny's undefined-kind replay (`_ev_undef`) had no constructor, field or match case, so a twin undefined inside
   a constructor argument had no certificate.
4. Dafny's certificate unroller walked a ground match's arms with their binders unbound. It now reduces a match on a
   ground constructor to the chosen arm, recording `scrutinee == literal` as an equation the kernel re-proves when
   they differ.
5. Lean's `simp only` closer cited a recursive spec_fun's equation, which never stops rewriting (maxRecDepth, which
   `first` does not catch). Recursive spec_funs are now grind hints only.

**Measured before this registration, stated plainly.**
- `discrete_logarithm`: Dafny COUNTS, Verus COUNTS. In Lean the real verifies, and the twin is unproved: the
  certificate's `simp` loops on `spec_pow_mod` at ground arguments. This is named, not fixed: it needs guarded
  unfolding lemmas or a Nat-fuel definition the kernel can evaluate.
- A probe with `datatype Option` COUNTS in Dafny, Verus and Lean.
- Of the 94 tasks' lowerings, changed:
  - the Dafny twins of `rect_area`, `shape_area` and `some_negative` (their certificates reduce the match); all three
    re-verified, still refuted;
  - `grid_row_sums` in Lean (fix 5): it now COUNTS in Lean, where it was a near miss.
- Of the AlgoVeri lowerings, changed: Lean real and twin of bubble_sort, insertion_sort, matrix_multiply,
  quick_sort and solve_longest_common_subsequence. Probed, all keep their T13 verdicts (unproved, or timeout).
- The whole suite passes (686).

**Bars**, for the clean-clone matrix of the 94 and a clean-clone regeneration of `t/ALGOVERI.md` (22 programs):
(1) `grid_row_sums` reads verified with the twin refuted in Lean. No other cell moves against T23's matrix.
(2) Lean goes from 67 to 68. All seven stays 48: `grid_row_sums` still needs Frama-C.
(3) `discrete_log_naive` reads verified with the twin refuted in Dafny and Verus, verified with the twin unproved in
Lean, and abstains elsewhere. Dafny is 22 of 22.
(4) No AlgoVeri cell reads differently from T13's table with T15's and T17's measured repairs applied, except as
follows. The five Lean rows above keep their verdicts. T16, T18, T19 and T21 landed after those AlgoVeri runs and
were never measured on AlgoVeri, so the F*, SPARK and Frama-C counts are read as measured.

### T23 read (2026-10-07 02:53Z): datatypes with fields in Dafny, Verus and Lean. All four bars held.

The matrix was regenerated from a clean clone of t-proof-engine at 0d091f5 (`t/AGREEMENT.md`) and compared cell by
cell with the installed table.
(1) **Held:** the six new tasks read verified with the twin refuted in Dafny, Verus and Lean (18 cells).
(2) **Held:** Rocq, F*, SPARK and Frama-C abstain by name on all six (24 cells).
(3) **Held:** no cell of the 88 moved. Only the six new rows differ.
(4) **Held:** per kernel, Dafny 94, Verus 86, Lean 67, Rocq 62, F* 59, SPARK 56, Frama-C 49. All seven stays 48, now
of 94. Every kernel still refutes the twin of every real it verifies (100%).

## T25 registered (2026-10-07 03:09Z, after hand probes and before the clean-clone matrix): recursive datatypes in Dafny, Verus and Lean (G10)

SPEC.md "Datatypes (v3): recursion". A field may have its own datatype's type, or the type of one declared before
it, and spec functions, lemmas and self-recursive tasks may take a datatype value as their measure. Five tasks are
added, making 99:
- `tree_sum` and `tree_count`: an int fold, the second with a nonnegativity clause the induction must carry;
- `tree_mirror`: a tree result, stated as `m == mirror(tr)`;
- `tree_insert`: BST-order insertion, a self-call under an `if` inside a match arm;
- `tree_height`: `max` of the two recursive results.

Receipt fb16ecad608c (Verus decreases-to; Box probe). The Lean design reuses 134d11c182fc (TPIL ch. 7, the
recursor), with the tree probe measured.

**Measured before this registration, stated plainly.**
- **Hand probes:** all five COUNT in Dafny, Verus and Lean on scratch runs (15 cells). `tree_insert` was re-run
  under its committed name: its spec function was renamed from `has`, which is a Verus keyword.
- **Two defects in a first statement, fixed before committing:**
  - `tree_mirror` was first stated by its total and size alone, which the identity function also meets. The twin
    harness rightly found no refutable twin, so the contract was strengthened to `m == mirror(tr)`.
  - `tree_height` failed in Verus, because a proof fn self-call cannot be an argument of a spec function, and in Lean,
    because grind was not given `t_max`. Both are fixed: the calls are bound by `let`s first, and the library
    functions are grind hints.
- **Byte identity:** every lowering of the 94 committed tasks and the 22 AlgoVeri programs is unchanged, real and
  twin, all seven kernels, with the witness. The twin harness's new binder move picks no earlier task's twin.
- **Suite:** the whole suite passes (694). The grammar and the parser agree on all 99 canonical forms; the printer
  now spells a spec function's datatype result by name.

**Bars**, for the clean-clone matrix of the 99 that follows:
(1) The five read verified with the twin refuted in Dafny, Verus and Lean: 15 cells.
(2) Rocq, F*, SPARK and Frama-C refuse all five by name: 20 cells.
(3) No other cell moves against T24's matrix.
(4) Per kernel: Dafny 99, Verus 91, and Lean five more than T24's matrix reads. All seven stays 48, now of 99.

### T24 read (2026-10-07 03:27Z): AlgoVeri's discrete_logarithm and five engine defects. All four bars held.

Both tables were regenerated from a clean clone at fbce7d9: the matrix of 94 (`t/AGREEMENT.md`) and the 22 AlgoVeri
programs (`t/ALGOVERI.md`, the first AlgoVeri table of record since T13's).
(1) **Held:** `grid_row_sums` reads verified with the twin refuted in Lean. It is the only cell of the 94 that moved.
(2) **Held:** Lean goes from 67 to 68, and all seven stays 48. `grid_row_sums` still needs Frama-C.
(3) **Held:** `discrete_log_naive` reads verified with the twin refuted in Dafny and Verus, verified with the twin
unproved in Lean, and abstains elsewhere. Dafny is 22 of 22.
(4) **Held:** no Lean AlgoVeri row changed. Every other change against T13's table is a T15 or T17 repair, now in the
table of record:
- Verus: quick_sort verified/refuted; kmp and merge_sort unproved with the twin refuted; matrix_multiply unproved.
- F*: binary_search and linear_search verified/refuted; kmp unproved/refuted; bubble_sort and insertion_sort
  timeout.
- SPARK: longest_common_subsequence and string_search_naive timeout with the twin refuted.

F*'s merge_sort also moved, from abstain to unproved/refuted: T16's comprehensions, read as measured. The AlgoVeri
counts are Dafny 22, Verus 7, F* 5, SPARK 3, Frama-C 2, Rocq 1, Lean 0. Two MALFORMED cells remain, the two T13
named: Verus poly_multiply_naive and F* longest_palindromic_substring.

Receipts behind T24's fixes, which its commit message miscited: 134d11c182fc (Lean) and 2d503d12f07a (Verus).

## T26 registered (2026-10-07 03:28Z, after hand probes and before the clean-clone matrix): quantifiers over a collection (G11)

SPEC.md "Quantifiers over a collection": `forall x in S . P` over the elements of a set or a seq, the form AlgoVeri's
BST contracts state.
- **A seq range** is exact sugar for the index form. `tshape.desugar_seq_quants` rewrites it at the top of every
  lowering, typed by check_wf, so all seven kernels state it.
- **A set range** is stated natively in Dafny (membership) and Verus (`contains`, as range and trigger). The other
  five refuse it by name.

Two tasks are added, making 101: `none_neg` (a seq range in the contract, an index invariant in the loop) and
`all_pos_set` (a set range). Receipt aad9cbc9ffae (Dafny reference: quantifier expressions; Verus guide: forall
and triggers).

**Measured before this registration, stated plainly.**
- **Hand probes:** `none_neg` COUNTS in all seven kernels. `all_pos_set` COUNTS in Dafny and Verus, and the other five
  abstain by name.
- **A first statement of `none_neg`, with membership left as membership:** Dafny and Verus could not prove it. An
  invariant in membership form over a slice was unproved in Dafny and Verus and timed out in Lean and Rocq. That
  measurement is why a seq range is desugared to indices.
- **A G9 defect, fixed:** check_wf collected a field's types in a Python set, which a datatype-typed field (a dict)
  cannot enter. It was found by AlgoVeri's BST contracts, written in scratch and not part of this registration.
- **Byte identity:** every lowering of the 99 tasks and the 22 AlgoVeri programs is unchanged.
- **Suite and grammar:** the whole suite passes (699). The grammar and the parser agree on all 101 canonical forms.

**Bars**, for the clean-clone matrix of the 101 that follows (after T25's):
(1) `none_neg` reads verified with the twin refuted in all seven kernels, so all seven goes from 48 to 49.
(2) `all_pos_set` reads verified with the twin refuted in Dafny and Verus, and abstains by name in the other five.
(3) No other cell moves against T25's matrix.
(4) Dafny and Verus gain two each. Lean, Rocq, F*, SPARK and Frama-C gain one each.

### T25 read (2026-10-07 03:45Z): recursive datatypes in Dafny, Verus and Lean. All four bars held.

The matrix was regenerated from a clean clone at 947c37c (`t/AGREEMENT.md`) and compared cell by cell with T24's.
(1) **Held:** the five tree tasks read verified with the twin refuted in Dafny, Verus and Lean (15 cells).
(2) **Held:** Rocq, F*, SPARK and Frama-C abstain by name on all five (20 cells).
(3) **Held:** no other cell moved.
(4) **Held:** Dafny 99, Verus 91, Lean 73; the other four unchanged. All seven stays 48, now of 99. Every kernel still
refutes the twin of every real it verifies (100%).

## T27 registered (2026-10-07 04:01Z, after hand probes and before the clean-clone runs): AlgoVeri's BST family, first five (G12)

`bst_search`, `bst_insert`, `bst_zig`, `bst_zigzag` and `bst_zigzig` are stated in t, making 27 AlgoVeri programs.
`t/algoveri/MAPPING.md` gives them clause by clause. They stand on recursive datatypes (T25) and set-ranged
quantifiers (T26), letter for letter, apart from three spellings with Dafny's meaning: `e.Node?` as a `case`, `+` on
sets as `union`, and `{v}` as t's set display. The rotations carry proof lemmas: zig one, zig_zag and zig_zig four
each.

**Engine changes, each found while writing these:**
- **Labelled shapes in the witness ladder:** every shape of up to five nodes, int fields labelled in order, so that
  BST requires have inputs. zig_zag had none before.
- **Dafny:** a certificate prints a ground set it states as a set display.
- **Verus, set certificates:** recursive spec fns revealed to the witness's depth, and the set-valued spec fns'
  memberships stated at each constructor literal. search's and insert's twins were unproved before.
- **Verus, well-definedness lemmas:** structural recursion revealed one level past the default.

**Measured before this registration, stated plainly.**
- **Dafny:** all five COUNT.
- **Verus:** search and insert COUNT. zig, zig_zag and zig_zig are unproved, the reason named in SPEC.md and MAPPING.md:
  `res.val`'s definedness from `view(res) == view(tree)`.
- **Byte identity:** every lowering of the 101 tasks and the 22 earlier AlgoVeri programs is unchanged, real and twin,
  all seven kernels, with the witness.
- **Suite:** the whole suite passes (701).

**Bars**, for the clean-clone matrix of the 101 and the AlgoVeri table of 27:
(1) No cell of the 101 moves against T26's matrix.
(2) The five read verified with the twin refuted in Dafny. In Verus, search and insert read verified/refuted, and the
three rotations do not. Lean, Rocq, F*, SPARK and Frama-C abstain by name on all five.
(3) The 22 earlier AlgoVeri programs read as in T24's table.
(4) AlgoVeri Dafny 27 of 27, Verus 9.

### T26 read (2026-10-07 04:03Z): quantifiers over a collection. All four bars held; all seven goes from 48 to 49.

The matrix was regenerated from a clean clone at c48c57f (`t/AGREEMENT.md`) and compared cell by cell with T25's.
(1) **Held:** `none_neg`, its contract written as `forall x in s . x >= 0`, reads verified with the twin refuted in all
seven kernels. All seven goes from 48 to 49.
(2) **Held:** `all_pos_set` reads verified with the twin refuted in Dafny and Verus, and abstains by name in Lean, Rocq,
F*, SPARK and Frama-C.
(3) **Held:** no other cell moved.
(4) **Held:** Dafny 101, Verus 93, Lean 74, Rocq 63, F* 60, SPARK 57, Frama-C 50. Every kernel still refutes the twin of
every real it verifies (100%).

## T28 registered (2026-10-07 04:09Z, after hand probes and before the clean-clone runs): the sign bridge for a product inside a lemma's definitions (Lean)

AlgoVeri's `integer_exponential` verifies with the twin refuted in six kernels. Lean alone kept it from all seven,
and not for its loop: the helper lemma `pow_nonneg` failed. From `spec_pow(b, e - 1) >= 0` and `b >= 0`, grind's
linear arithmetic does not derive `b * spec_pow(b, e - 1) >= 0`. That product sits inside the definition the lemma's
ensures calls. The lemma closer's existing sign bridge covers only products of int parameters in the ensures.

**Design.** `Lower._definition_signs`: for each spec_fun call in a lemma's ensures, every product in that function's
body whose factors mention only its own parameters is instantiated at the call's arguments. Its sign is stated as
`try have _mpd<k> : (0:Int) <= A * B := Int.mul_nonneg (by omega) (by omega)` before each closer, after the inductive
hypothesis, so omega sees it. There are at most eight such facts, and `try` keeps a fact that does not hold out of the
proof.

**Measured before this registration, stated plainly.**
- **Hand probe:** with the one fact added to the emitted file, pow_nonneg_l, the loop lemma and the contract verify.
- **Lean, `cli verify`:** integer_exponential COUNTS. fast_exponential is still unproved: its loop's preservation needs
  `pow_square`'s fact, which Lean's loop helper does not receive. That is named and not part of this registration.
- **Byte identity:** of the 101 tasks and 27 AlgoVeri programs, exactly four lowerings change: Lean's real and twin of
  fast_exponential and integer_exponential.
- **Suite:** the whole suite passes (703).

**Bars**, for the clean-clone matrix of the 101 and the AlgoVeri table of 27, after T27's:
(1) No cell of the 101 moves against T27's matrix.
(2) AlgoVeri integer_exponential reads verified with the twin refuted in Lean, so it is verified/refuted in all seven:
AlgoVeri's first all-seven contract.
(3) fast_exponential's Lean cell keeps T27's verdict. No other AlgoVeri cell moves.

## T29 registered (2026-10-07 04:21Z, after hand probes and before the clean-clone runs): finite sets in Lean (G13)

SPEC.md "Finite sets", the Lean note of 2026-10-07. Lean refused every set, on the ground that core Lean has no
finite-set type. Lean 4.33's own Std ships `Std.ExtTreeSet`, extensional and decidable. A set of ints is
`Std.ExtTreeSet Int compare`:
- the operations are `∪`, `∩` and `\`, with `insert`/`erase` for a singleton second operand;
- `card` is size, membership is `∈`/`contains`, `toset` is `ofList`, and `==` is Lean's `=`;
- grind gets the membership and size lemmas core leaves untagged, plus one proved fact, `t_set_size_pos`;
- certificates close by `decide`.

**The Lean adapter's ban list allows exactly one import line**, `import Std.Data.ExtTreeSet`, a toolchain module.
Every other import stays banned, and the axiom audit is unchanged. Receipt 76156bbbd011 (the ExtTreeSet API page,
and the lemma file of the toolchain itself).

**Measured before this registration, stated plainly.**
- **Lean, `cli verify`:**
  - set_toggle and set_collect COUNT.
  - members_upto is unproved: membership in a slice, `s[i] ∈ s[0..n]`, is not derived.
  - all_pos_set (a set-ranged quantifier) and words_seen (`set<seq>`) are refused by name.
- **Byte identity:** of the 101 tasks and 27 AlgoVeri programs, exactly six lowerings change, all from a refusal to
  a lowering: Lean's real and twin of members_upto, set_collect and set_toggle.
- **Suite:** the whole suite passes (707). `test_lean_lib`'s "toset stays refused" became "toset is lowered", as this
  registration intends.

**Bars**, read from the clean-clone matrix of the 101 that follows T27's. The same run reads T28, whose cells are
disjoint from these:
(1) set_toggle and set_collect read verified with the twin refuted in Lean. With Dafny and Verus, and Rocq and F*,
which already verify both, each is then verified/refuted in five kernels.
(2) members_upto's Lean cell moves from abstain to unproved. all_pos_set and words_seen keep their Lean refusals.
(3) No other cell of the 101 moves against T27's matrix. Lean gains 2.

### T27 read (2026-10-07 04:37Z): AlgoVeri's BST family, first five. All four bars held.

Both tables were regenerated from a clean clone at f047482: the matrix of 101 (`t/AGREEMENT.md`) and the AlgoVeri table
of 27 (`t/ALGOVERI.md`).
(1) **Held:** no cell of the 101 moved against T26's matrix.
(2) **Held:** the five read verified with the twin refuted in Dafny. In Verus, search and insert are verified/refuted and
the three rotations unproved, for the named `res.val` definedness. Lean, Rocq, F*, SPARK and Frama-C abstain by name.
(3) **Held:** the 22 earlier programs read as in T24's table. One cell, F*'s insertion_sort, kept its verdict
(timeout/timeout) but is marked FLAKED: its reruns disagreed on the way to the same verdict, so the cell is
provisional, as before.
(4) **Held:** AlgoVeri Dafny 27 of 27, Verus 9, the rest unchanged (F* 5, SPARK 3, Frama-C 2, Rocq 1, Lean 0).

### T28 and T29 read (2026-10-07 05:18Z): every bar held.

Both tables were regenerated from a clean clone at d8188c8, which carries T28 and T29 and not T30: the matrix of 101
(`t/AGREEMENT.md`) and the AlgoVeri table of 27 (`t/ALGOVERI.md`).

**T28**, the sign bridge for a product inside a lemma's definitions:
(1) **Held:** no cell of the 101 moved for T28. The only cells that moved are T29's three, below.
(2) **Held:** AlgoVeri's integer_exponential reads verified with the twin refuted in Lean. It is now verified/refuted
in all seven, AlgoVeri's first such contract.
(3) **Held:** fast_exponential's Lean cell kept its verdict. No other AlgoVeri cell moved. F*'s insertion_sort kept
timeout/timeout, and this run's reruns agreed, so the FLAKED mark is gone.

**T29**, finite sets in Lean:
(1) **Held:** set_toggle and set_collect read verified with the twin refuted in Lean.
(2) **Held:** members_upto's Lean cell moved from abstain to unproved/refuted. all_pos_set and words_seen kept their
Lean refusals; at d8188c8, T30 had not yet landed.
(3) **Held:** no other cell of the 101 moved. Lean went from 74 to 76, and all seven stayed at 49.

AlgoVeri: Dafny 27, Verus 9, F* 5, SPARK 3, Frama-C 2, Lean 1, Rocq 1; all seven 1.

## T30 registered (2026-10-07 04:43Z, after hand probes and before the clean-clone runs): set-ranged quantifiers in Lean

Lean refused a quantifier over a set's members. On T29's tree sets it now states one in both positions:
- **In a Prop:** `∀ x, x ∈ S → P` (`∃ x, x ∈ S ∧ P`).
- **Computed as a Bool:** `S.toList.all (fun x => P)` (`any`). A connective whose operands include one is computed as a
  Bool too (`&&`, `||`, `!`), because `decide` over the Prop form has no Decidable instance (measured on is_bst).
- **Closers:** a task with a set range first simps the spec funs and `List.all_eq_true`, `List.any_eq_true`,
  `ExtTreeSet.mem_toList` and `decide_eq_true_eq` before grind. grind does not use an `all = true` hypothesis
  through the iff unless simp first states it as the quantifier (measured).
- **Inhabited:** a datatype that is a field's type derives `Inhabited` when the task reads fields, which the default
  arm of a field read needs. Measured on AlgoVeri's zig: `tree.left`.

**Measured before this registration, stated plainly.**
- all_pos_set COUNTS in Lean.
- AlgoVeri's zig, zig_zag and zig_zig lower in Lean. Their twins are refuted, by kernel-checked certificates over trees
  and sets. Their reals are unproved: the lemmas' steps reason through the Bool is_bst, and grind does not close
  them.
- search and insert stay refused by name: a structurally recursive task with requires (T25).
- **Byte identity:** exactly these change, all_pos_set's Lean pair and the five BST programs' Lean pairs.
- **Suite:** the whole suite passes (708).

**Bars**, for the clean-clone runs after T28's and T29's:
(1) all_pos_set reads verified with the twin refuted in Lean, making three kernels.
(2) AlgoVeri zig, zig_zag and zig_zig read unproved with the twin refuted in Lean, where they abstained. search and
insert abstain.
(3) No other cell moves against T28's and T29's tables.

## T31 registered (2026-10-07 05:08Z, after hand probes and before the clean-clone runs): seq locals in Frama-C

Frama-C refused every seq local except a slice alias, and `rev` everywhere. palindrome was one of four tasks Frama-C
alone kept out of all seven. Frama-C now gives such a local the workspace a method call's local already had: SPEC.md
"The library (v1)", the Frama-C note of 2026-10-07. Receipt 74ec03028a6f: ACSL by Example's reverse_copy, whose
contract for its destination buffer is the one emitted here.
- **`rev`** (the shelved T20 patch): in a specification, the element rewrite `rev(s)[k] == s[len(s) - 1 - k]`; in
  code, T19's write loop.
- **The workspace** (`_local_scratch`). A seq local qualifies when:
  - its initializer can be written: a copy, `seq(n, v)`, `s[i := v]`, a literal, `rev` of a variable, or a map;
  - its length is a function of the params;
  - it is written once, outside any loop.

  It becomes a caller-provided `int *u, int u_n`: `\valid`, separated from every other buffer,
  `requires u_n == <length>`, and in the `assigns`. Every other seq local keeps the refusal by name.
- **The certificate** (`_cert_seq_cells`). It replays such a local cell by cell at the witness, and asserts each
  ground length and index as a goal first. A seq equality assigned to a bool is decided the way a branch is.
- **Three tasks:**
  - `rev_equal`: `r == (b == rev(a))` through a local `rev(a)`;
  - `doubled_head`: a map into a local;
  - `set_first`: an update into a local.

**Measured before this registration, stated plainly.**
- **Frama-C, `cli verify`:** palindrome COUNTS. Six probes of a seq local (a copy, a fill, an update, a literal, a
  map, and `rev` compared to a parameter) read verified with the twin refuted.
- **All seven, `cli verify`:**
  - palindrome and set_first read verified/refuted in every kernel.
  - rev_equal is verified/refuted in six kernels; Rocq's real is unproved.
  - doubled_head is verified/refuted in six kernels; Lean's real is unproved.
- **A named gap outside this registration's tasks.** The rev probe with `requires len(s) == len(t2)` drew the witness
  `s=[0], t2=[1]`. There, Dafny's and F*'s twins read unproved: refuting needs `[1] != rev([0])`. Rocq's real read
  unproved there too. rev_equal's witness is `a=[], b=[0]`, decided by length alone.
- **Byte identity:** of the 101 tasks and 27 AlgoVeri programs, exactly two lowerings change: Frama-C's real and twin
  of palindrome, both from a refusal to a lowering.
- **Suite:** the whole suite passes (713). `test_framac_lib`'s "palindrome refuses rev" became "rev is lowered", as
  this registration intends.

**Bars**, for the clean-clone matrix of 104 that follows T30's registration. The same run reads T30, whose cells are
disjoint from these:
(1) palindrome reads verified with the twin refuted in Frama-C, so all seven reach 50 of the 101.
(2) set_first reads verified/refuted in all seven. rev_equal reads the same in six, with Rocq's real unproved.
doubled_head reads the same in six, with Lean's real unproved.
(3) No other cell moves against T29's and T30's tables. Frama-C gains 4 (palindrome and the three).

## T32 registered (2026-10-07 05:17Z, after hand probes and before the clean-clone runs): a map's element at a Nat index (Lean)

T31's hand probe left doubled_head unproved in Lean alone. Its spec needs `t_comp1_get` at index 0, and the lemma's
pattern is `(t_comp1 t_s t_n)[t_i.toNat]!`. grind normalizes the goal's `(0 : Int).toNat` to `0`, so the pattern never
matches. With the instance stated by hand, the file verifies. Receipt 4ba739e6c40b: the Lean reference's E-matching
chapter, where patterns match modulo congruence and nothing equates a literal with `?t_i.toNat`.

**Design.** Each map comprehension also gets `t_compK_getn`: the element at a Nat index, `∀ (t_i : Nat), t_i < t_n →
(t_compK t_s t_n)[t_i]! = body[t_s[t_i]!]` (over a range, `t_a + (t_i : Int)`). It is proved from `_get` at
`(t_i : Int)` by `simpa only [Int.toNat_natCast]`, which rewrites only the cast, and it is handed to grind beside the
others. A filter gets nothing new.

**Measured before this registration, stated plainly.**
- **Lean, `cli verify`, the eight tasks whose Lean text changes:**
  - doubled_head reads verified/refuted.
  - all_positive, diffs, doubled, every_other, has_negative and squares stay verified/refuted.
  - odd_positions stays unproved/refuted.
- **odd_positions is a named gap, the same mismatch one step further.** Its strided slice is a range map over
  `s[1..len(s)]`. grind normalizes the slice to `List.take (len + -1).toNat (List.drop 1 s)`, which
  `t_seq_slice_get`'s pattern (`drop a.toNat`, `take (b - a).toNat`) does not match. A Nat-indexed slice lemma was
  probed: grind registers its pattern but never instantiates it, because the element sits in an implication whose
  antecedents grind does not discharge. More E-matching rounds did not change that. It is not part of this
  registration.
- **Byte identity:** of the 104 tasks and 27 AlgoVeri programs, exactly 16 lowerings change, the Lean pairs of those
  eight tasks.
- **Suite:** the whole suite passes (713).

**Bars**, for the clean-clone matrix of 104 that reads T30 and T31 too. This replaces T31 bar (2)'s Lean clause for
doubled_head:
(1) doubled_head reads verified/refuted in Lean, so with T31 it is verified/refuted in all seven.
(2) The other seven tasks keep their Lean verdicts.
(3) No other cell moves for this change.

### T30, T31 and T32 read (2026-10-07 05:53Z): every bar held.

Both tables were regenerated from a clean clone at 9095774, which carries T30, T31 and T32 and not T33 or T34: the
matrix of 104 (`t/AGREEMENT.md`) and the AlgoVeri table of 27 (`t/ALGOVERI.md`).

**T30**, set-ranged quantifiers in Lean:
(1) **Held:** all_pos_set reads verified with the twin refuted in Lean, making three kernels.
(2) **Held:** AlgoVeri's zig, zig_zag and zig_zig read unproved/refuted in Lean, where they abstained. search and
insert abstain.
(3) **Held:** no other cell moved.

**T31**, seq locals in Frama-C:
(1) **Held:** palindrome reads verified/refuted in Frama-C. All seven reach 50 on the 101.
(2) **Held**, as T32 amended:
- set_first reads verified/refuted in all seven.
- rev_equal does in six, with Rocq's real unproved.
- doubled_head does in all seven: its Lean clause was replaced by T32's bar (1) before the run.

(3) **Held:** no other cell moved, and Frama-C gained 4 (50 to 54).

**T32**, a map's element at a Nat index in Lean:
(1) **Held:** doubled_head reads verified/refuted in Lean.
(2) **Held:** the other seven tasks kept their Lean verdicts, odd_positions still unproved/refuted.
(3) **Held:** no other cell moved.

**The matrix of 104, by kernel (verified with the twin refuted):**

| kernel | count |
|---|---|
| Dafny | 104 |
| Verus | 96 |
| Lean | 80 |
| Rocq | 65 |
| F* | 63 |
| SPARK | 60 |
| Frama-C | 54 |

All seven: 52 (49 of the 101, plus palindrome, set_first and doubled_head). AlgoVeri is unchanged at Dafny 27,
Verus 9, F* 5, SPARK 3, Frama-C 2, Lean 1, Rocq 1, with all seven 1.

## T33 registered (2026-10-07 05:24Z, after hand probes and before the clean-clone run that follows clean25): one orientation for a seq equality (Rocq)

T31's rev_equal is verified/refuted in six kernels; Rocq's real is unproved. The code tests `u == b` with `u = rev(a)`
and the contract states `b == rev(a)`. Rocq renders each operand in its own place:
- code: `(a_len =? b_len) && t_seq_eqb a_len (t_rev a a_len) b`
- contract: `b_len = a_len /\ forall k < b_len, b k = t_rev a a_len k`

The closer ends the false branch by `congruence` between the contract's forall and the code's negated fact. Those are
two different terms here, so nothing closes it. Receipt d051845f7561: Rocq's congruence is congruence closure, which
closes a hypothesis against the negation of another only when they are the same term.

**Design.** `_seq_eq_order`: in all three places Rocq states a seq `==` (code, contract, certificate arm), the operand
whose rendered function sorts first leads, with its own length as the bound.

**Measured before this registration, stated plainly.**
- **Hand probes:** a hand proof compiles. So does the closer once the flipped facts are added and the lengths
  substituted.
- **Rocq, `cli verify`:** rev_equal COUNTS. double_all, palindrome and swap_rows, whose Rocq text changes, stay
  verified/refuted.
- **Byte identity:** of the 104 tasks and 27 AlgoVeri programs, exactly six lowerings change:
  - Rocq's real and twin of palindrome and rev_equal;
  - the real of double_all and swap_rows.
- **Suite:** the whole suite passes (714).

**Bars**, for the clean-clone matrix that follows clean25 (which runs at 9095774, without this change):
(1) rev_equal reads verified/refuted in Rocq. With T31's six, it is then verified/refuted in all seven.
(2) double_all, palindrome and swap_rows keep their Rocq verdicts.
(3) No other cell moves against clean25's table.

## T34 registered (2026-10-07 05:49Z, after hand probes and before the clean-clone runs): datatypes in Rocq

The zoom-out's decision 5 (internal/RESEARCH-2026-10-07-zoom-out.md), first half. Rocq refused every datatype.
Receipt 3366ce62013e: the Rocq reference on inductive types and on reasoning with them. SPEC.md "Datatypes" v1, v2
and v3 carry the Rocq notes.

**Design.**
- **Types.** A t datatype is Rocq's own `Inductive`: `dt_<D>` is the type and `dt_<D>_<C>` a constructor. A field is
  the constructor's argument, of type int, bool or a datatype.
- **Equality.** `==` is Leibniz equality in a Prop. In a bool it is a decider built by `decide equality`.
- **Expressions.** `case` is Rocq's `match`. `e.f` is a projection, and its definedness obligation (the constructor
  declares `f`) is a lemma proved by cases.
- **Proofs.** A straight-line proof first destructs each matched variable and each decided equality (`t_dt_cases`),
  then runs the usual search.
- **Recursion.** A spec fun or task whose measure is a datatype parameter is a structural `Fixpoint`, so the guard
  checker is the termination proof. Its contract is proved by induction:
  - each case is unfolded one step;
  - an `if` the unfolding cannot pass is destructed;
  - the inductive hypotheses' conjuncts are split, and their `= true` facts rewritten in.
- **Certificates.** A certificate grounds a constructor witness as its term.
- **Refused by name:** a seq, set or pair field.

**Measured before this registration, stated plainly.**
- **Rocq, `cli verify`, the 12 datatype tasks:**
  - Nine COUNT: color_code, shape_area, manhattan, rect_area, tree_sum, tree_count, tree_height, tree_mirror and
    tree_insert.
  - bag_size and checked_tail abstain by name (a seq field).
  - some_negative, a loop over an Opt state, lowers and reads unproved/unproved.
- **AlgoVeri, the six datatype programs:**
  - The five BST programs still abstain by name, on the set-ranged quantifier.
  - discrete_log_naive (a loop with an Option return) lowers and reads unproved/unproved.
  - None is malformed.
- **Byte identity:** of the 104 tasks and 27 AlgoVeri programs, exactly 26 lowerings change:
  - the Rocq real and twin of the 12 datatype tasks (bag_size and checked_tail only in their refusal text);
  - discrete_log_naive's Rocq real and twin.
- **Suite:** the whole suite passes (719). The two tests that pinned "Rocq refuses datatypes" now pin the three
  kernels that still do, as this registration intends.

**Bars**, for the clean-clone matrix and AlgoVeri table that follow T33's registration:
(1) The nine read verified/refuted in Rocq; Rocq gains 9.
(2) Each of the nine is then verified/refuted in Dafny, Verus, Lean and Rocq, four kernels, where it was three.
(3) bag_size and checked_tail abstain in Rocq. some_negative reads unproved in Rocq, and AlgoVeri's
discrete_log_naive reads unproved there. No other cell moves for this change.

### T33 and T34 read (2026-10-07 06:29Z): every predicted cell held; one unrelated cell moved under load I caused.

Both tables were regenerated from a clean clone at 1da07b8, which carries T33 and T34 and not T35 or later: the
matrix of 104 and the AlgoVeri table of 27.

**T33**, one orientation for a seq equality in Rocq:
(1) **Held:** rev_equal reads verified with the twin refuted in Rocq, so it is in all seven. All seven: 53.
(2) **Held:** double_all, palindrome and swap_rows kept their Rocq verdicts.
(3) **Did not hold as measured.** sum_tail's Lean twin read timeout, where it was refuted.
- Nothing in T33 or T34 touches Lean. The cause is mine: I was running SPARK and F* proofs beside the clean-clone
  run.
- Rerun alone at 06:15Z, sum_tail's Lean twin is refuted, as before.
- The table is installed as measured, and the next clean-clone run, with nothing beside it, re-measures the cell.
- In the AlgoVeri table, F*'s insertion_sort, the known flaky cell, read timeout/refuted, marked FLAKED.

**T34**, datatypes in Rocq:
(1) **Held:** the nine read verified/refuted in Rocq. Rocq went from 65 to 75: those nine, plus T33's rev_equal.
(2) **Held:** each of the nine is verified/refuted in four kernels: Dafny, Verus, Lean and Rocq.
(3) **Held for this change:** bag_size and checked_tail abstain in Rocq. some_negative and AlgoVeri's
discrete_log_naive read unproved/unproved there. The cells that moved besides are not Rocq's, as T33's (3) records.

**The matrix of 104, by kernel (verified with the twin refuted):**

| kernel | count |
|---|---|
| Dafny | 104 |
| Verus | 96 |
| Lean | 79 (80 with sum_tail's re-measured twin) |
| Rocq | 75 |
| F* | 63 |
| SPARK | 60 |
| Frama-C | 54 |

All seven: 53.

## T35 registered (2026-10-07 06:04Z, after hand probes and before the clean-clone run that follows clean26): datatypes in F*

The zoom-out's decision 5, second half. F* refused every datatype. Receipt fc51eb6283ec: the F* book's chapter
"Inductive types and pattern matching". SPEC.md "Datatypes" v1, v2 and v3 carry the F* notes.

**Design.**
- **Types.** A t datatype is F*'s own inductive type: `dt_<D>` the type, `Dt_<D>_<C>` a constructor, `f_<f>` a field.
- **Equality.** The type is an eqtype, so `==` is `=` in a bool and `==` in a Prop.
- **Expressions.** `case` is F*'s `match`, which F* checks exhaustive. `e.f` is a function whose argument is refined
  to the constructors that declare `f`, so F* proves the read's definedness wherever it occurs.
- **Recursion.** Recursion on a datatype parameter is `(decreases q)`, F*'s subterm ordering.
- **Certificates.** A certificate's formula is built from the original task, as before, and for a datatype task its
  calls are renamed to the file's own names. tree_sum's `total` is an F* keyword, so the file says `t_total`; a
  certificate naming `total` read MALFORMED, measured before this fix.
- **Refused by name:** a seq, set or pair field.

**Measured before this registration, stated plainly.**
- **F*, `cli verify`, the 12 datatype tasks:**
  - Ten COUNT: color_code, shape_area, manhattan, rect_area, some_negative, tree_sum, tree_count, tree_height,
    tree_mirror and tree_insert. some_negative is a loop over an Opt state, which Rocq leaves unproved.
  - bag_size and checked_tail abstain by name (a seq field).
- **AlgoVeri:**
  - The five BST programs abstain by name, on the set-ranged quantifier.
  - discrete_log_naive's real times out and its twin is refuted.
- **Byte identity:** of the 104 tasks and 27 AlgoVeri programs, exactly 26 lowerings change: the F* real and twin of
  the 12 datatype tasks, and of discrete_log_naive.
- **Suite:** the whole suite passes (724). Three tests changed, as this registration intends:
  - the two refusal tests now pin SPARK and Frama-C;
  - the F* shape tests skip datatype tasks, which test_fstar_datatypes.py covers;
  - test_names allows a rename only of the kernel's own keywords.

**Bars**, for the clean-clone matrix and AlgoVeri table that follow clean26 (which runs at 1da07b8, without this
change):
(1) The ten read verified/refuted in F*; F* gains 10.
(2) With T34's Rocq cells, the nine Rocq carries are verified/refuted in five kernels (Dafny, Verus, Lean, Rocq, F*).
some_negative is in four: Dafny, Verus, Lean and F*.
(3) bag_size and checked_tail abstain in F*, and AlgoVeri's discrete_log_naive reads timeout/refuted in F*. No other
cell moves for this change.

## T36 registered (2026-10-07 06:13Z, after hand probes and before the clean-clone run that follows clean26): datatypes in SPARK

SPARK refused every datatype. Receipt f33fe37e88f8: learn.adacore.com, "More about records", on variant records.
SPEC.md "Datatypes" v1, v2 and v3 carry the SPARK notes.

**Design.**
- **Types.** A t datatype is an Ada discriminated record. The discriminant is an enumeration of the constructors,
  `Dt_<D>_Tag`, with a default, so the type is definite. A constructor's field is the component `F_<C>_<f>`, since
  Ada forbids one component name twice in a record.
- **Field reads.** A read is the component selection, and its discriminant check, which gnatprove proves, is the
  read's definedness. A field several constructors declare is a function over the tag, whose `Pre` names them.
- **Expressions.** `case` is an Ada case expression on the tag, `==` the record's predefined equality, and a
  constructor a qualified aggregate.
- **Certificates.** A certificate binds a datatype parameter by name in a declare expression. A static aggregate
  selected under another variant's alternative is a compile-time error (measured: shape_area's twin read MALFORMED).
- **Definedness formula.** `defined()` states a field read's and a match's obligations as a t match.
  some_negative's crash (KeyError) is fixed by this.
- **Refused by name:** a recursive datatype (an Ada record cannot hold itself without access types), and a seq, set
  or pair field.

**Measured before this registration, stated plainly.**
- **SPARK, `cli verify`:**
  - color_code, shape_area, manhattan, rect_area and some_negative COUNT.
  - The five recursive tree tasks, bag_size and checked_tail refuse by name.
  - AlgoVeri's discrete_log_naive COUNTS.
- **Byte identity:** of the 104 tasks and 27 AlgoVeri programs, exactly 26 lowerings change:
  - the SPARK real and twin of the 12 datatype tasks (seven of them only in their refusal text);
  - discrete_log_naive's SPARK pair.
- **Suite:** the whole suite passes (728). The fields refusal test now pins Frama-C alone; the recursion test accepts
  SPARK's refusal by name.

**Bars**, for the clean-clone matrix and AlgoVeri table that follow clean26 (which runs at 1da07b8, without T35 or
this change). The same run reads T35:
(1) The five read verified/refuted in SPARK; SPARK gains 5.
(2) color_code, shape_area, manhattan and rect_area are then verified/refuted in six kernels, all but Frama-C.
some_negative is in five: all but Rocq and Frama-C.
(3) AlgoVeri's discrete_log_naive reads verified/refuted in SPARK (AlgoVeri SPARK 3 to 4). No other cell moves for
this change.

## T37 registered (2026-10-07 06:32Z, after hand probes and before the clean-clone run that reads T35-T37): datatypes in Frama-C

Frama-C was the last kernel refusing every datatype, and for color_code, shape_area, manhattan and rect_area it was
the only kernel left once T34-T36 landed. Receipt 030f8d5520b2: the ACSL language source, on `\let` and on struct
terms. SPEC.md "Datatypes" v1 and v2 carry the Frama-C notes.

**Design.**
- **Values.** A t datatype is a C struct passed by value, the encoding the pairs already use: `int tag` (an enum
  constant per constructor) and every variant's fields `f_<C>_<f>`. A constructor is a C99 compound literal.
- **Equality.** ACSL needs no struct literal: `x == C(a, b)` is `x.tag == C` and the fields. Other equality is the
  tag-aware predicate `dt_<D>_eq`.
- **Matches.** A match is a conditional on the tag. Its binders are bound by `\let` in ACSL and replaced by their
  field in C.
- **Definedness.** A field read owes its constructor: `defs()` states it in a specification, and an assert states
  it before the statement in code.
- **Parameters.** Each datatype parameter `requires dt_<D>_ok(p)`, its tag one of its constructors'.
- **Certificates.** A certificate declares a datatype witness as its compound literal. It decides each match, and
  each nested min, max or abs, at the ground state, asserted. manhattan's twin carried a live `?:` for a nested abs
  before that last step.
- **This landing takes datatype parameters.** A datatype return or local, `==` on datatypes in executable position,
  a recursive datatype and a seq, set or pair field refuse by name.

**Measured before this registration, stated plainly.**
- **Frama-C, `cli verify`:** color_code, shape_area, manhattan and rect_area COUNT. some_negative and
  discrete_log_naive (a datatype return), the five trees (recursive), and bag_size and checked_tail (seq fields)
  refuse by name.
- **Byte identity:** of the 104 tasks and 27 AlgoVeri programs, exactly 26 lowerings change: the Frama-C pairs of
  the 12 datatype tasks and of discrete_log_naive. No other task's certificate changed for the nested-conditional
  step.
- **Suite:** the whole suite passes (732). The fields test that pinned "Frama-C refuses" now checks that all seven
  lower shape_area.

**Bars**, for the clean-clone matrix and AlgoVeri table at this registration's commit, which read T35, T36 and T37
together, with no proof run beside them:
(1) The four read verified/refuted in Frama-C; Frama-C gains 4.
(2) With T34-T36, color_code, shape_area, manhattan and rect_area are verified/refuted in all seven, so all seven
gains 4 (53 to 57). The fifth reaches 58 only if sum_tail's Lean twin is no longer the unrelated timeout T33's read
recorded, and sum_tail is not all-seven anyway: SPARK and Frama-C keep it out.
(3) No other cell moves for T35-T37 beyond their own bars. sum_tail's Lean twin reads refuted again, unloaded.

### T35, T36 and T37 read (2026-10-07 07:23Z): every bar held. Datatypes are verified/refuted in all seven kernels.

Both tables were regenerated from a clean clone at 3e67882, which carries T35, T36 and T37, with no proof run
beside it: the matrix of 104 (`t/AGREEMENT.md`) and the AlgoVeri table of 27 (`t/ALGOVERI.md`).
- The AlgoVeri half was OOM-killed at the unit's 8 GB cap (peak 8 GB plus 5.3 GB swap), near the end of its Lean
  column. It was re-run alone at the same commit with 2 jobs under 11 GB.
- With less load, two F* twins of AlgoVeri moved from timeout to refuted: bubble_sort and max_subarray_sum. Neither
  touches a datatype, and both reals still time out, so no count of verified-with-twin-refuted moves.
- insertion_sort's F* cell kept its verdict, and is no longer marked FLAKED.

**T35**, datatypes in F*:
(1) **Held:** the ten read verified/refuted in F*. F* went from 63 to 73.
(2) **Held:** the nine Rocq carries are verified/refuted in five kernels. some_negative is in four: Dafny, Verus,
Lean and F*.
(3) **Held:** bag_size and checked_tail abstain in F*. AlgoVeri's discrete_log_naive reads timeout/refuted in F*.

**T36**, datatypes in SPARK:
(1) **Held:** color_code, shape_area, manhattan, rect_area and some_negative read verified/refuted in SPARK. SPARK
went from 60 to 65.
(2) **Held:** the four are in six kernels, all but Frama-C. some_negative is in five, all but Rocq and Frama-C.
(3) **Held:** AlgoVeri's discrete_log_naive reads verified/refuted in SPARK, so AlgoVeri SPARK went from 3 to 4.

**T37**, datatypes in Frama-C:
(1) **Held:** the four read verified/refuted in Frama-C. Frama-C went from 54 to 58.
(2) **Held:** color_code, shape_area, manhattan and rect_area are verified/refuted in all seven. All seven went from
53 to 57.
(3) **Held:** no other cell moved for T35-T37. sum_tail's Lean twin, unloaded, is refuted again, as T33's read said
it would be. Lean is back at 80.

**The matrix of 104, by kernel (verified with the twin refuted):**

| kernel | count |
|---|---|
| Dafny | 104 |
| Verus | 96 |
| Lean | 80 |
| Rocq | 75 |
| F* | 73 |
| SPARK | 65 |
| Frama-C | 58 |

All seven: 57. Frama-C alone keeps double_all, grid_row_sums and swap_rows out of all seven; Lean alone keeps
odd_positions out.

## T38, T39 and T40 registered (2026-10-07 07:26Z, after hand probes and before the clean-clone runs)

Three disjoint changes, read from one clean-clone matrix and one AlgoVeri table. The AlgoVeri half runs alone at 2
jobs under 11 GB, as clean27's re-run did.

**T38: AlgoVeri's left-leaning red-black tree, three contracts.** `llrbt_rotateleft`, `llrbt_rotateright` and
`llrbt_flipcolor` are stated (MAPPING.md, README.md).
- **Encoding.** t's datatypes are monomorphic and not mutually recursive, so `Node` with `Option<Node>` children is
  one `Tree` whose `Nil` is the source's `None`. Each member function is a spec fun agreeing with the source on
  every `Node`.
- **Proofs.** The two rotations carry an order lemma, as bst_zig does.
- **Witness ladder.** The ladder found no input satisfying their `requires`, because every labelled shape held each
  bool field at its first value, so every node was black. Receipt 7d3153ed1847 (SmallCheck's small-scope
  enumeration): for a recursive datatype with a bool field only, each labelled shape now also enters with one
  node's bools flipped and with all of them flipped, appended and capped (SPEC.md "Datatypes (v3)").

**T39: a slice read in a Lean comprehension body is the base's read** (receipt 4ba739e6c40b, the grind E-matching
chapter, as T32). odd_positions' stepped slice desugars to a map whose body reads `s[1..len(s)][2*i]`. grind
normalizes that nested `drop`/`take` past every lemma pattern, so T32's read left it unproved. The helper's body now
reads `s[1 + 2*i]`, which is equal wherever the slice is defined. The definedness theorems still state the slice's
bounds from the task's own AST, and a slice from the literal 0 reads the bare index. With a `0 + ` left in,
every_other's `_get0` read MALFORMED in the first probe; fixed before this registration.

**T40: datatype returns and locals in Frama-C** (receipt 030f8d5520b2, as T37). A datatype return or local is the
struct by value, as a pair's is. The loop frame havocs it by name. The certificate declares and compares constructor
values by their t text. `==` on datatypes in executable position still refuses by name.

**Measured before this registration, stated plainly.**
- **T38, `cli verify`, all seven on the three:**
  - Dafny verifies each with the twin refuted.
  - Lean: unproved/refuted. Verus: unproved/unproved.
  - Rocq, F*, SPARK and Frama-C abstain by name on the set-ranged quantifier in `is_bst`.
- **T39, Lean:** odd_positions and every_other read verified/refuted.
- **T40, Frama-C:** some_negative reads verified/refuted. AlgoVeri's discrete_log_naive refuses by name, on its
  executable `==` on an Option.
- **Byte identity:** of the 104 tasks and 27 AlgoVeri programs, exactly eight lowerings change, and three programs
  are new:
  - the Lean pairs of every_other and odd_positions;
  - the Frama-C pairs of some_negative and discrete_log_naive.

  No earlier witness changed for the ladder's bool variants.
- **Suite:** the whole suite passes (734).

**Bars**, for the clean-clone matrix of 104 and the AlgoVeri table of 30 at this registration's commit:
(1) odd_positions reads verified/refuted in Lean, so it is in all seven: all seven go from 57 to 58, and Lean from 80
to 81. every_other keeps verified/refuted.
(2) some_negative reads verified/refuted in Frama-C, so it is in six (all but Rocq): Frama-C goes from 58 to 59.
(3) AlgoVeri grows to 30 programs. The three LLRB programs are verified/refuted in Dafny (30 of 30), unproved
otherwise or abstaining as measured above. discrete_log_naive's Frama-C cell stays an abstention, with its new reason.
No other cell moves.

### T38, T39 and T40 read (2026-10-07 08:06Z): every bar held.

Both tables were regenerated from a clean clone at 7a5f9f8, with no proof run beside it: the matrix of 104 (3 jobs),
then the AlgoVeri table of 30 (2 jobs), in one unit under 11 GB, with no OOM.
(1) **Held:** odd_positions reads verified/refuted in Lean, so it is in all seven: all seven went from 57 to 58, and
Lean from 80 to 81. every_other kept verified/refuted.
(2) **Held:** some_negative reads verified/refuted in Frama-C (59), so it is in six. Rocq alone keeps it out.
(3) **Held:** AlgoVeri has 30 programs.
- The three LLRB programs are verified/refuted in Dafny (30 of 30), unproved/refuted in Lean and unproved/unproved
  in Verus. Rocq, F*, SPARK and Frama-C abstain, on the set-ranged quantifier.
- discrete_log_naive's Frama-C cell stayed an abstention, with its new reason.
- No other cell moved, in either table.

Single-kernel blockers now: Frama-C keeps double_all, grid_row_sums and swap_rows from all seven, and Rocq keeps
some_negative.

## T41 and T42 registered (2026-10-07 08:11Z, after hand probes and before the clean-clone runs)

**T41: Rocq, a loop over a datatype state.** some_negative was Rocq's only gap to all seven: its loop invariant is a
`match` on the `Opt` state, which the generic search never splits. Receipt 3366ce62013e (Rocq's reasoning with
inductives, as T34).
- For a datatype task, `t_dis` and `t_side` each gain a LAST alternative, `solve [ t_dt_cases; t_vc0 ]`. It is tried
  only when every earlier one fails, so no goal an earlier one closed changes how it closes.
- The value certificate missed the twin's computed value: `_fv` did not see a return used as a `match` scrutinee.
  `_fv` now walks constructors, field reads and matches.

**T42: seq fields in Rocq, F* and SPARK.**
- **Rocq:** a seq field is one `((Z -> Z) * Z)` value, read through `fst` and `snd`. A datatype holding one gets no
  decider, and `==` on it refuses by name, since Leibniz equality on a function is not t's extensional seq
  equality. `t_dt_cases` also splits a variable read through a field's projection, then reduces the projections.
  Before that, bag_size's `dt_Bag_f_active b` was no `match` on `b`, so nothing split it.
- **F\*:** a seq field is `Seq.seq int`. The type is then no eqtype, so `==` is propositional only, and a computed
  `==` refuses by name.
- **SPARK:** a seq field is a `Seq` component, and the seq preamble is emitted for it.

Receipts fc51eb6283ec and f33fe37e88f8, as T35 and T36.

**Measured before this registration, stated plainly.**
- **Rocq, the 12 datatype tasks:**
  - some_negative and bag_size now COUNT, beside the nine.
  - checked_tail refuses by name: `==` on a datatype holding a seq.
  - AlgoVeri's discrete_log_naive moves from unproved/unproved to unproved/refuted.
- **F\* and SPARK:** bag_size and checked_tail COUNT in both.
- **Byte identity:**
  - Every datatype task's Rocq lowering changes (the alternative and the case tactic), and so does
    discrete_log_naive's. The nine earlier tasks were re-verified: unchanged.
  - The F* and SPARK pairs of bag_size and checked_tail change, from refusals.
- **Suite:** the whole suite passes (737).

**Bars**, for the clean-clone matrix and AlgoVeri table at this registration's commit:
(1) some_negative reads verified/refuted in Rocq, so it is in all seven: all seven go from 58 to 59, and Rocq from 75
to 77 with bag_size.
(2) bag_size reads verified/refuted in Rocq, F* and SPARK, so it is in six (all but Frama-C). checked_tail reads it in
F* and SPARK, so it is in five (Rocq and Frama-C refuse by name). F* goes from 73 to 75, and SPARK from 65 to 67.
(3) discrete_log_naive's Rocq cell reads unproved/refuted. No other cell moves.

### T41 and T42 read (2026-10-07 08:52Z): every bar held.

Both tables were regenerated from a clean clone at fb3e1f8, with no proof run beside it: the matrix of 104 (3 jobs),
then the AlgoVeri table of 30 (2 jobs), in one unit under 11 GB, with no OOM.
(1) **Held:** some_negative reads verified/refuted in Rocq, so it is in all seven: all seven went from 58 to 59. Rocq
went from 75 to 77 with bag_size.
(2) **Held:** bag_size reads verified/refuted in Rocq, F* and SPARK, so it is in six; Frama-C alone keeps it out.
checked_tail reads verified/refuted in F* and SPARK, so it is in five; Rocq and Frama-C refuse it by name. F* went
from 73 to 75, and SPARK from 65 to 67.
(3) **Held:** discrete_log_naive's Rocq cell reads unproved/refuted. AlgoVeri stays at 30 programs: Dafny 30,
Verus 9, F* 5, SPARK 4, Frama-C 2, Lean 1, Rocq 1; all seven 1.
- No other cell moved, in either table.

## T43, T44 and T45 registered (2026-10-07 09:03Z, after hand probes and before the clean-clone runs)

**T43: a datatype with a seq field, flattened in Frama-C.** bag_size (`datatype Bag = Bag(items: seq, active:
bool)`) was Frama-C's only gap on it. A C struct field cannot hold a seq buffer. Receipt 7210be66f2c9: ACSL by
Example's Stack keeps (pointer, capacity, size) in a struct passed by pointer and moves the buffer's obligations into
predicates over the struct. t's datatypes are passed by value, so the backend's existing answer for a pair with a seq
component is taken instead (`_pair_flat`, DESIGN-framac-nested-seq.md section 5).
- **The flattening:** a datatype with one constructor whose fields are int, bool and seq is a FLATTENED parameter,
  each field its own C parameter (`int *b_items, int b_items_n, int b_active`). `b.items` is the bare name
  `b_items`, so every reader of a seq (`len`, `at`, definedness) takes it unchanged, and the seq field joins the seq
  parameters' `_n >= 0`, `\valid_read` and pairwise `\separated` clauses.
- **The certificate:** declares the witness field by field.
- **Refused by name:** any other use of such a datatype (a return, local, constructor, match, equality, call
  argument, spec-function parameter), and a seq field in a datatype of several constructors (checked_tail, whose
  refusal is reworded).

**T44: early exits in Verus, Lean, Rocq, F*, SPARK and Frama-C.** Receipt 28d3ddecb054. One rewrite,
`tshape.desugar_exits`, not six lowerings: every one of the six already carries `return` inside a loop (SPEC "Early
exit (v1)"), which owes the task's `ensures` and not the invariant.
- **`continue`:** the statements after it on its path move into the other branch of each `if` on that path. The
  iteration ends in the same state, where the invariants and `decreases` are owed exactly as at the `continue`.
- **`break`:** becomes the loop's continuation (the rest of the task body) followed by `return`. When the
  continuation ends in an assignment to the return name, that assignment becomes the `return`.
- **Refused by name:** a `break` of a loop nested in another loop's body, unless the rest of that body ends in
  `return` and holds no `continue`; a `break` or `continue` in a method body; a `break` in a task with several returns.
- **`while true`** is left as written.
- **Checked against the interpreter** (`test_exits_desugar.py`): on every input of a small domain (seqs over
  {-1, 0, 1, 2} up to length 3, ints -2..3) the rewrite computes what the original computes. Covered: the three
  tasks, their twins, and five programs written to reach each case (nested `if`s, two loops in a row, a loop inside
  an `if`, a nested loop followed by `return`, `continue` beside `return`).

**Measured before this registration, stated plainly.**
- **T43:** bag_size COUNTS in Frama-C (verified, its collapse-if twin refuted).
- **T44 and T45, the four tasks in the six kernels** (`cli.py verify`, 3 jobs): every carried cell reads
  verified/refuted. That is index_of and find_zero in all six, count_evens_skip in Verus, Lean, F* and SPARK, and evens
  in F* and SPARK (and still in Lean). Rocq and Frama-C refuse count_evens_skip and evens by name (filters).
- **What the first probe found, and what fixed it:**
  - SPARK emitted the comprehension's function after the loop function whose contract calls it (malformed): the
    comprehensions now come first.
  - Verus left count_evens_skip unproved: its comprehension recursion is `drop_last` over the whole source, so a
    prefix `s[0..i + 1]` needs subrange extensionality at every step. Two broadcast lemmas (`t_compK_prefix`,
    `t_compK_whole`) state it once, and a loop's proof function now uses them.
  - Lean left it unproved: grind did not unfold the filter through `(i + 1).toNat`, so `t_compK_step` states the
    length one step on.
  - Frama-C left find_zero unproved on one smoke goal: the dead code after `while (1)`. The rewrite now drops
    statements after a `while true` that has no `break` left, and Frama-C emits no trailing `return` there.
- **Byte identity:** every lowering of the 104 tasks and the 30 AlgoVeri programs, real and twin, in all seven
  kernels, with the witness (1,560 and 450 entries), was compared with fb3e1f8. Only bag_size and checked_tail
  (Frama-C), the three early-exit tasks (the six kernels) and evens (F*, SPARK, and Lean's new step lemma) change;
  no AlgoVeri lowering changes.
- **Suite:** the whole suite passes (746, with test_exits_desugar.py's 51 checks).

**Bars**, for the clean-clone matrix and AlgoVeri table at this registration's commit:
(1) bag_size reads verified/refuted in Frama-C, and index_of and find_zero in Verus, Lean, Rocq, F*, SPARK and
Frama-C, so all three are in all seven: all seven go from 59 to 62.
(2) count_evens_skip reads verified/refuted in Verus, Lean, F* and SPARK (five kernels with Dafny), and evens in F* and
SPARK (five); Rocq and Frama-C refuse both by name. evens keeps verified/refuted in Lean.
(3) Per kernel: Verus 96 to 99, Lean 81 to 84, Rocq 77 to 79, F* 75 to 79, SPARK 67 to 71, Frama-C 59 to 62; Dafny 104.
checked_tail keeps its Frama-C refusal, reworded. No other cell moves.
(4) The AlgoVeri table does not move (no lowering of it changed).

**T45: filtered comprehensions in F* and SPARK.** Receipt 0e4e244fa954 (F*'s fuel-instrumented equation for a `let
rec`, fetched). Dafny's own shape: a prefix-form recursion keeping the last element when the condition holds, its
contract the length bound and, for a pure filter, the condition at every element; the definedness is the condition at
every element and the body where it holds. SPARK's definedness formula gains the comprehension case
lower_verus.defined already has (count_evens_skip's ensures holds one).

### T43, T44 and T45 read (2026-10-07 09:45Z): every bar held.

Both tables were regenerated from a clean clone at 0ddcce3, with no proof run beside it: the matrix of 104 (3 jobs),
then the AlgoVeri table of 30 (2 jobs), in one unit under 11 GB, with no OOM.
(1) **Held:** bag_size reads verified/refuted in Frama-C, and index_of and find_zero in Verus, Lean, Rocq, F*, SPARK
and Frama-C, so all three are in all seven: all seven went from 59 to 62.
(2) **Held:** count_evens_skip reads verified/refuted in Verus, Lean, F* and SPARK, and evens in F* and SPARK; Rocq
and Frama-C refuse both by name. evens kept verified/refuted in Lean.
(3) **Held:** Verus 99, Lean 84, Rocq 79, F* 79, SPARK 71, Frama-C 62, Dafny 104. checked_tail kept its Frama-C
refusal. No other cell moved.
(4) **Held:** the AlgoVeri table did not move.

## T46, T47, T48 and T49 registered (2026-10-07 09:50Z, after hand probes and before the clean-clone runs)

The operator, 2026-10-07 09:00Z: add the heap, floats and concurrency to t, under a new north star
(`NORTH-STAR.md`, "write it once, prove it everywhere it ships"), whose first target they are. Each is in SPEC.md
with its own section, SYNTAX.md, t.gbnf (`grammar_check.py`: 114 of 114 committed programs accepted), the checker
(rules with a `malformed/` example each), the interpreter, the twins and the Python hand-back.

**T46: Heap (v1), arrays by reference.** Receipt 76b38f46f235 (Ada RM 6.2: by copy and by reference agree when nothing
is aliased; Dafny's `array<T>`).
- **The form:** an `array` task parameter, `modifies a`, `a[i] := e`, and `old(e)` in an ensures or a loop
  invariant. No aliasing; an array is nothing but a task parameter.
- **The observable result** is the return value and the modified arrays' final contents. Witnesses record both
  (`_real_heap`, `_twin_heap`), and the real-witness scan reads them.
- **Dafny** lowers it natively. The other six refuse it by name (`tshape.has_heap`).
- **Four tasks:** reverse_in_place, swap_at, clamp_all, ring_push.

**T47: Concurrency (v1), parallel loops.** Receipt 1338b1d7d06d (rayon's par_iter_mut; Dafny's forall statement).
- **The form:** `parallel for i in [lo, hi)`, whose iterations run in any interleaving.
- **Race freedom is checked by rule** (`par-race`, `par-exit`): an iteration writes only its own element, reads a
  written array only there, assigns only its own locals and has fixed bounds. So every schedule equals the
  sequential loop, which each kernel verifies (`tshape.desugar_par`).
- **The interpreter** runs the iterations in reverse, a second schedule; `test_concurrency.py` checks it against
  the sequential rewrite on every domain point. The hand-back runs them on a thread pool.
- **Three tasks:** scale_all, offset_all, relu_all.

**T48: Floats (v1), IEEE-754 binary64.** Receipt 18db794aff2e (the SPARK UG's semantics of floating point).
- **The form:** `float`, `float(x)`, `sqrt`, `real(f)`. Arithmetic rounds to nearest even and is defined only when
  finite; a float never mixes with an int or a real.
- **The interpreter and the hand-back** compute in Python's float, with a finiteness check after each operation.
- **T49, SPARK:** `Long_Float`, literals as the exact decimal value of their double. `sqrt`, `real(f)` and a run-time
  `float(n)` refuse by name. The other six refuse floats by name.
- **Three tasks:** sat_scale, deadband, rate_limit (autonomy shapes: saturation, deadband, rate limiter).

**Measured before this registration, stated plainly.**
- **Dafny, the seven heap and parallel tasks:** every one verified, with its twin refuted. scale_all's twin
  differs from the real body only in the array, and its certificate grounds the twin's final contents.
  reverse_in_place first timed out reading `a[..][k]`; with `a[k]` and `a.Length` read on the array itself (the
  terms Dafny's array axioms trigger on) it verified, and the other six re-verified.
- **SPARK, the three float tasks:** sat_scale and deadband verified with the twin refuted. rate_limit's real body
  TIMES OUT: its ensures `r >= prev - step` where `r = prev + step` needs the monotonicity of rounding, which Z3 (the
  pinned prover) did not find within the budget.
- **Every other cell** of the ten tasks is a refusal by name (heap, or floats).
- **Byte identity:** no lowering of the 104 matrix tasks or the 30 AlgoVeri programs changes (the 10 tasks are new).
- **Suite:** the whole suite passes, including test_heap.py, test_concurrency.py and test_floats.py.

**Bars**, for the clean-clone matrix and AlgoVeri table at this registration's commit:
(1) The matrix has 114 tasks. Dafny reads verified/refuted on all of them except the three float tasks, which it
refuses by name: 111.
(2) SPARK reads verified/refuted on sat_scale and deadband (73), and timeout/refuted on rate_limit.
(3) Every other new cell is abstain/abstain, and no cell of the 104 moves. All seven stays 62 of 114.
(4) The AlgoVeri table does not move.

### T46, T47, T48 and T49 read (2026-10-07 10:35Z): every bar held.

Both tables were regenerated from a clean clone at 4ed6dd6, with no proof run beside it, in one unit under 11 GB, with
no OOM.
(1) **Held:** the matrix has 114 tasks. Dafny reads verified/refuted on all of them but the three float tasks, which
it refuses by name: 111.
(2) **Held:** SPARK reads verified/refuted on sat_scale and deadband (73), and timeout/refuted on rate_limit.
(3) **Held:** every other new cell is abstain/abstain, and no cell of the 104 moved. All seven stays 62 (of 114).
(4) **Held:** the AlgoVeri table did not move.

## T50 registered (2026-10-07 10:35Z, after hand probes and before the clean-clone runs): the heap in Frama-C

The first industry kernel for the heap (NORTH-STAR.md target 1). Receipt 76b38f46f235 (T46's).
- **Arrays are C pointers.** `int *a, int a_n`: `\\valid` when written, `\\valid_read` otherwise,
  `assigns a[0 .. a_n - 1]`, and the array in a loop's frame. A write is `a[i] = e;`, after an assert of the index's
  range.
- **`old(a)[i]`** is `\\let t = i; \\at(a[t], Pre)`: the index bound in the current state, the element read at Pre.
  `len(old(a))` is `a_n`.
- **A certificate** replays the writes on its ground arrays (both the value walk and the undefined walk) and reads
  old(...) at its own entry label `t_entry`.
- **Refused by name:** a whole array in old(...), as reverse_in_place's `a == rev(old(a))`.

**Measured before this registration, stated plainly.**
- **Frama-C:** swap_at, clamp_all, ring_push, scale_all, offset_all and relu_all are each verified with the twin
  refuted. Three of them (scale_all, offset_all, relu_all) are parallel loops (T47).
- **Byte identity:** only the seven heap tasks' Frama-C lowerings change (from refusals); nothing else in the 114,
  and nothing in AlgoVeri.
- **Suite:** the whole suite passes (765), and every module compiles under Python 3.10.

**Bars**, for the clean-clone matrix and AlgoVeri table at this registration's commit:
(1) Frama-C reads verified/refuted on those six (68), and refuses reverse_in_place by name.
(2) No other cell moves. All seven stays 62.
(3) The AlgoVeri table does not move.

### T50 read (2026-10-07 11:34Z): every bar held.

Both tables were regenerated from a clean clone at 905e457, with no proof run beside it, with no OOM.
(1) **Held:** Frama-C reads verified/refuted on swap_at, clamp_all, ring_push, scale_all, offset_all and relu_all
(68), and refuses reverse_in_place by name.
(2) **Held:** no other cell moved. All seven stays 62 of 114.
(3) **Held:** the AlgoVeri table did not move.

## T51 and T52 registered (2026-10-07 11:34Z, after hand probes and before the clean-clone runs)

**T51: floats in Frama-C.** Receipt 68e1c50d765a (ACSL's manual: annotation arithmetic is exact on reals, a
`(double)` cast rounds to nearest even, `\\is_finite`).
- **Types:** a t float is a C `double`, and each float parameter is `requires \\is_finite(p)`.
- **In a specification,** every float operation is written with its rounding made explicit, `((double)(a op b))`.
- **In code,** the operation is C's own, preceded by `\\is_finite` of the rounded value (and a nonzero divisor).
- **Literals** are exact decimal values (`1.000e3`). WP warned "Unexpected constant literal" on a hexadecimal one and
  proved nothing about it (measured).
- **Certificates** declare float witnesses the same way and replay with the interpreter's float arithmetic.
- **sat_scale** now writes `-lim` (an exact negation) where it wrote `float(0) - lim`, a rounded subtraction the
  provers did not see through. SPARK re-verified it.

**T52: the autonomy suite** (`t/autonomy/`, NORTH-STAR.md target 2). 25 routines of a navigation, guidance and
control stack (`t/autonomy/README.md`), with their own table, `t/AUTONOMY.md`. Each is well-formed, has a twin whose
witness falsifies its ensures, and hands back to Python agreeing with t (`test_autonomy.py`). Four fixes came from its
first run:
- **Rocq's keyword list** (receipt a991b51f25db, the reference manual's lists): `by` (a box's y coordinate) made
  aabb_overlap and crosstrack_side MALFORMED. The list gains by, is, of, where, using, exists2, SProp, Axiom,
  CoFixpoint, Hypothesis, Parameter and Variable.
- **Rocq, bool parameters** (receipt bd2ed2ab30c9): `t_dis` gains a last alternative, only for a task with a bool
  parameter, that destructs every bool and searches again. arm_check and debounce were unproved.
- **Comprehension shapes up to the bound variable's name,** in Dafny, Verus, F* and SPARK, as Lean's already were. An
  ensures `[x for x in s if p(x)]` and an invariant `[y for y in s[0..i] if p(y)]` were two functions, and Dafny could
  not equate them (readings_in_band).
- **Verus:** a certificate whose comprehension has a free variable the witness grounds has no spec fn, and is now
  refused by name instead of raising KeyError. The twin stands without a certificate.

**Measured before this registration, stated plainly.**
- **Frama-C floats:** deadband verified with its twin refuted. sat_scale and rate_limit time out. sat_scale proves
  8 of 8 goals with no step limit, but Alt-Ergo steps out at the matrix's 20000 steps.
- **The autonomy suite, all 25 in all seven kernels** (`cli.py verify t/autonomy`, 3 jobs), verified with the twin
  refuted:

| kernel | Frama-C | SPARK | Dafny | F* | Verus | Lean | Rocq |
|---|---|---|---|---|---|---|---|
| routines | 21 | 19 | 18 | 17 | 14 | 14 | 14 |

  13 of the 25 are in all seven. Every routine a kernel proves has its twin refuted, except readings_in_band's in
  Verus (no certificate). The routines kept out:
  - grid_cell and low_pass_step: nonlinear integer division, proved by F* alone;
  - pid_step: floats, timing out in SPARK and Frama-C;
  - crosstrack_side: a product, unproved in Lean;
  - the float and array routines, wherever a kernel refuses floats or the heap.
- **Byte identity:** in the 114 tasks only the float tasks' Frama-C lowerings change (and sat_scale's SPARK one, from
  its edit). Nothing in AlgoVeri changes.
- **Suite:** passes; every module compiles under Python 3.10.

**Bars**, for the clean-clone tables at this registration's commit:
(1) The matrix: Frama-C reads verified/refuted on deadband (69), timeout on sat_scale and rate_limit. SPARK keeps
sat_scale verified/refuted (73). No other cell moves; all seven stays 62.
(2) `t/AUTONOMY.md`: Frama-C 21, SPARK 19, Dafny 18, F* 17, Verus 14, Lean 14, Rocq 14; all seven 13 of 25.
(3) The AlgoVeri table does not move.

### T51 and T52 read (2026-10-07 12:27Z): every registered bar held; one unregistered cell moved, under my load.

The three tables were regenerated from a clean clone at d4d87d1, with no OOM.
(1) **Held:** Frama-C reads verified/refuted on deadband (69), and timeout on sat_scale and rate_limit. SPARK kept
sat_scale verified/refuted (73).
(2) **Held:** `t/AUTONOMY.md` reads Frama-C 21, SPARK 19, Dafny 18, F* 17, Verus 14, Lean 14 and Rocq 14; 13 of 25 in
all seven, exactly the hand probes.
(3) **Held:** the AlgoVeri table did not move.
- **Not registered, and caused by me:** sum_tail's Lean twin read timeout (verified/refuted before). I ran the lowering
  snapshot, four Python processes, beside the matrix half. This is the same borderline cell that timed out under load
  on clean26. Re-run alone on the clean clone afterwards, it is refuted again. The installed table keeps the measured
  timeout (Lean 83), and the next clean run re-measures it. A clean run's matrix half now gets an idle machine, with no
  snapshot and no suite beside it.


## T53 registered (2026-10-07 12:40Z, after hand probes and before the clean-clone run): the heap in five more kernels

**The change.** `tshape.desugar_heap` rewrites an in-place routine as copy-in/copy-out, which Ada RM 6.2 makes the
same program when there is no aliasing (t's heap v1 forbids it). The array parameter becomes a sequence; the body
works on a local copy `t_cur_<m>`; `a[i] := e` becomes an `update`; `return e` becomes `return pair(e, t_cur_<m>)`.
The ensures reads `fst(t_out)` for the result, `snd(t_out)` for the array, and `old(e)` as `e`. The witness becomes
`[value, final array]`. Verus, Lean, Rocq, F* and SPARK lower through it in place of refusing the heap by name;
Dafny and Frama-C keep their native lowerings. Two written arrays, or a result type with no default, still refuse by
name. Rocq's `default_term` gains the sequence slot, `((fun _ : Z => 0), 0)`, that the pair needs.

**Measured before this registration, stated plainly.** Hand probes of the seven heap tasks and the three autonomy
array routines in the five kernels (`cli.py verify`, after the Rocq default fix):

| task | verus | spark | lean | rocq | fstar |
|---|---|---|---|---|---|
| clamp_all | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| offset_all | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| swap_at | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| scale_all | verified / unproved | verified / refuted | verified / refuted | verified / unproved | verified / unproved |
| relu_all | verified / unproved | verified / timeout | verified / refuted | verified / unproved | verified / unproved |
| ring_push | unproved / refuted | verified / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| reverse_in_place | unproved / refuted | timeout / refuted | unproved / refuted | unproved / refuted | unproved / refuted |
| zero_fill (autonomy) | verified / unproved | verified / refuted | verified / refuted | verified / unproved | verified / unproved |
| sample_push (autonomy) | unproved / unproved | timeout / refuted | unproved / refuted | unproved / unproved | unproved / unproved |
| saturate_all (autonomy) | unproved / unproved | timeout / refuted | unproved / refuted | unproved / unproved | unproved / unproved |

- **Twins unrefuted in Verus, F* and Rocq:** where a twin differs from the real program only in the array, those three
  have no value certificate for a `(value, sequence)` pair yet. These cells read verified/unproved, never
  verified/refuted, and are not counted.
- **Unproved reals:** the mod arithmetic of ring_push and sample_push, and reverse_in_place's index reflection.
- **Byte identity:** in the 114 tasks only the seven heap tasks' lowerings change, in exactly these five kernels.
  Nothing in AlgoVeri changes.
- **Suite:** passes; every module compiles under Python 3.10. The names test allows Rocq's rename of `t_cur_<m>` and
  `t_out`, since lower_rocq reserves the whole `t_` prefix.

**Bars**, for the clean-clone tables at this registration's commit:
(1) The matrix, verified/refuted: Verus 102 (+3), SPARK 78 (+5), Lean 89 (+5, and sum_tail's twin refuted again on an
idle machine), Rocq 82 (+3), F* 82 (+3). Dafny 111 and Frama-C 69 do not move.
(2) swap_at, clamp_all and offset_all enter all seven: 65 of 114.
(3) `t/AUTONOMY.md`: SPARK 20 and Lean 15 (zero_fill); the other five rows do not move; all seven stays 13 of 25.
(4) The AlgoVeri table does not move.

### T53 read (2026-10-07 13:33Z): every registered bar held.

The three tables were regenerated from a clean clone at 94fb961 on an idle machine, and are installed.
(1) **Held:** Verus 102, SPARK 78, Lean 89 (sum_tail's twin refuted again), Rocq 82, F* 82; Dafny 111 and Frama-C 69
unchanged.
(2) **Held:** swap_at, clamp_all and offset_all are in all seven: 65 of 114.
(3) **Held:** `t/AUTONOMY.md` reads SPARK 20 and Lean 15 (zero_fill); Frama-C 21, Dafny 18, F* 17, Verus 14 and Rocq
14 unchanged; all seven 13 of 25.
(4) **Held:** the AlgoVeri table is byte-identical below its date line.
- **One uncounted cell differs from the probe:** scale_all's Rocq twin reads timeout (unproved in the probe). It
  counts in neither reading.

## T54 registered (2026-10-07 13:34Z, after hand probes and before the full run): D8, the specification audit

**The tool.** `t/audit.py` (`cli.py audit`) runs every one-edit mutant the twin ladder can build, not only the first,
over the task's bounded domain. Each mutant is **killed** (its result falsifies `ensures` at some point, or has no
value), **same** (the same result everywhere), **diverges** (runs out of steps where the real body ends; a kernel
rejects it on termination) or a **survivor** (a different result somewhere, and `ensures` holds everywhere). With
`--kernel`, the real body and up to three survivors are verified in that kernel. A survivor the kernel proves is a
wrong program with a proof.

**Prior art, read** (receipt 0139ee2dd35d): MutDafny (arXiv 2511.15403) mutates 794 Dafny programs (743 from
DafnyBench) and calls a mutant alive when Dafny verifies it. Of 118,458 mutants, 30,459 were alive; a manual triage of
284 found 157 equivalent, 77 pointing at weak specs and 50 inconclusive. Five weak specs were named: bst4copy and
dafny-synthesis task_id 2, 126, 161 and 249. Here equivalence is decided by execution before any kernel runs, and a
survivor is a postcondition finding that does not depend on the loop invariants. The cost is the bounded domain: a
difference outside it is not seen.

**Measured before this registration, stated plainly.**
- **MutDafny's four dafny-synthesis weak specs** (all four are in dawnr's 326 lifted DafnyBench tasks): each has
  survivors (126: 13, 161: 11, 2: 11, 249: 11). Dafny verifies each real body **and proves a survivor in all four**.
  126 (`sum >= every common divisor`) admits summing every i. 2, 161 and 249 (each `result` within the intended set,
  never the converse) admit a loop that stops one element early: `a=[0], b=[0]` gives `[]` where the real gives
  `[0]`. These are the weaknesses MutDafny's authors found by hand, found here mechanically with a witness. 4 s for
  the four, kernel included.
- **t's own suites, interpreter only:**
  - the 114 tasks: 1,541 of 1,570 behaviour-changing mutants killed (98.2%); 6 tasks admit a survivor;
  - the 25 autonomy routines: 810 of 813 killed (99.6%); 2 admit a survivor;
  - read by hand, seven are gaps:
    - count_pos_for, evens, filter_pos and index_map: bounds or membership only;
    - rate_limit: the direction of a limited step is unstated;
    - pid_step: which limit a saturated command takes is unstated;
    - tree_insert: the search-tree order is unstated;
  - nearest_index's survivor is a tie, intended latitude;
  - every one of these specs passes the twin rule; the audit asks more of a spec than one refuted twin.

**Bars**, for the full run over the 326 lifted tasks with `--kernel dafny` (guesses where marked):
(1) At least 300 of the 326 are audited (the ladder pilot reached 317).
(2) Dafny verifies the real body in at least 90% of the audited tasks (the sources were verified before lifting).
(3) A guess: between 25% and 60% of the audited tasks admit a survivor.
(4) A guess: where the real body is verified and a survivor exists, Dafny proves a survivor in at least half.
(5) The four tasks above read as measured.

### T54 read (2026-10-07 13:42Z): four bars held, and the one guess about how many specs are weak missed low.

Read from a clean clone at 62fa15e (`t/AUDIT-DAFNYBENCH.md`, `t/AUDIT-TASKS.md`, `t/AUDIT-AUTONOMY.md`), the same
numbers as the hand run.
(1) **Held:** 320 of the 326 are audited. 4 have no input inside the bounded domain that meets `requires`; in 2 the
real body breaks its own `ensures` inside the domain.
(2) **Held:** Dafny verifies the real body in 316 of the 320 (98.8%). Three read vacuous and one timeout.
(3) **Missed, low:** 53 of the 320 (16.6%) admit a survivor, below the guessed 25% to 60%. Over all 9,145 mutants,
6,829 are killed, 896 compute the same, 1,002 diverge and 418 survive: the specs kill 94.2% of the mutants that change
behaviour.
(4) **Held:** where the real body is verified and a survivor exists (50 tasks), Dafny proves a survivor in 44 (88%).
Each is a wrong program with a proof.
(5) **Held:** MutDafny's four read as measured.
- **The 44, read by hand** (`t/dafnybench/CLASSIFIED.md`):
  - 23 are gaps: the spec admits a result that is wrong for what the routine evidently computes. Three `max`
    routines admit a value above both inputs; a Euclidean division admits remainder 1 for 1 / 1; a median of three
    admits a non-median; an `==>` precedence slip makes one contract a tautology; plus MutDafny's four.
  - 3 have no spec (`ensures true`).
  - 3 are test cases that are bounds by design.
  - 15 are intended latitude: ties, either order, any negative sentinel, VSComp 2010's stated property.
- **t's own suites,** with Dafny: of the 6 tasks with survivors, Dafny proves one in 5. rate_limit is a float task,
  which Dafny refuses. Of the autonomy suite's 2, Dafny proves nearest_index's tie (pid_step is a float routine). The
  seven gaps named at registration stand.

## T55 registered (2026-10-07 13:54Z, after hand probes and before the clean-clone run): t's own weak specs, strengthened

**The change.** T54's self-audit named seven of t's specs that admit a different program. Six are rewritten so that
they pin the result down; the bodies are unchanged:
- **count_pos_for:** `r == npos(s, len(s))`, a recursive count in count_matches' shape.
- **filter_pos:** `r == pos(s, len(s))`, a recursive filter in double_all's shape, keeping `len(r) <= len(s)`
  (Frama-C sizes the output buffer from it).
- **evens:** `r == [x for x in s if x % 2 == 0]`.
- **index_map:** every element maps to an index holding it, at or after every occurrence (so the last one), within
  the sequence.
- **rate_limit and pid_step:** the limit a saturated step or command takes.

tree_insert's search-tree order needs an induction lemma over insertion that the kernels do not find unaided, so it
stays a named gap. Frama-C's sequence display now casts an element read from a C array to `integer`. Without the cast,
`\Cons(s[i], \Nil)` is a `\list<int>` and does not unify with `\list<integer>` (ACSL's implicit coercions do not
reach inside a list).

**Measured before this registration, stated plainly.**
- **The audit (interpreter):** all six read 0 survivors. count_pos_for kills 35 of 35 behaviour-changing mutants,
  filter_pos 20 of 20, evens 6 of 6, index_map 16 of 16, pid_step 74 of 74 and rate_limit 32 of 32.
- **The kernels (hand probe, all seven):**
  - count_pos_for stays verified/refuted in all seven, and evens and index_map keep their cells.
  - rate_limit and pid_step stay timeouts in SPARK and Frama-C.
  - filter_pos stays verified/refuted in six. In Frama-C its real body now steps out (31 of 32 goals; the loop
    invariant's preservation fails even at 1,000,000 steps): WP lacks the frame fact that the recursive logic
    function's value is unchanged by a write to the output buffer. This is the gap that keeps double_all at timeout.
- **Byte identity:** only the six tasks' lowerings move. The twin changes for count_pos_for and evens. evens'
  refusal in Frama-C and Rocq now names the comprehension in its spec. AlgoVeri does not move. Suite passes, Python
  3.10 compiles.

**Bars**, for the clean-clone tables at this registration's commit:
(1) Frama-C 68 (filter_pos timeout); every other kernel's count unchanged; all seven 64 of 114.
(2) `t/AUTONOMY.md` unchanged (pid_step stays a timeout in SPARK and Frama-C).
(3) `t/AUDIT-TASKS.md`: 1 of 114 tasks admits a survivor (tree_insert). `t/AUDIT-AUTONOMY.md`: 1 of 25
(nearest_index, a tie).

### T55 read (2026-10-07 14:25Z): every registered bar held.

The tables were regenerated from a clean clone at 1bc4dc6 on an idle machine, and are installed.
(1) **Held:** Frama-C 68 (filter_pos now timeout/refuted); every other kernel unchanged (Dafny 111, Verus 102, Lean
89, Rocq 82, F* 82, SPARK 78); all seven 64 of 114. No other cell moved.
(2) **Held:** `t/AUTONOMY.md` unchanged.
(3) **Held:** `t/AUDIT-TASKS.md` reads 1 of 114 (tree_insert, the named gap), with 1,568 of 1,570 behaviour-changing
mutants killed. `t/AUDIT-AUTONOMY.md` reads 1 of 25 (nearest_index's tie), 812 of 813 killed.
- **What it cost:** one all-seven cell. A stronger contract is harder to prove, and Frama-C's missing frame fact for
  recursive logic functions over memory now blocks two tasks (double_all and filter_pos) instead of one.

## T56 registered (2026-10-07 14:29Z, after hand probes and before the clean-clone run): D8 v2, three more corpora in their own kernels

**The change.** Three more lifted corpora are committed, each with its license and provenance, and audited in the
kernel its source was verified in:
- `t/acslbyexample/`: 16 functions from ACSL by Example (Fraunhofer FOKUS, MIT), in Frama-C;
- `t/vericoding/verus/` (66) and `t/vericoding/lean/` (16): verified solutions from the vericoding benchmark (MIT;
  arXiv 2509.22908), in Verus and Lean.

**Prior art, read** (receipt ceb1bc69583b): the vericoding paper estimates by manual inspection that "conditioned on
vericoding success, roughly 9% of the specs were too weak and another 15% had poor translations". It found them with
an LLM-as-judge, a quality score and sampling, and it keeps incomplete specs deliberately. No execution- or
kernel-based measure is reported.

**Measured before this registration, stated plainly** (hand runs of `t/audit.py --kernel K`):
- **ACSL by Example, Frama-C:** 16 audited; 457 of 457 behaviour-changing mutants killed; **0 survivors**. Frama-C
  verifies 13 real bodies (find3, find_if_not and is_sorted_until time out).
- **Vericoding Verus:** 63 of 66 audited (3 have no input in the domain); 1,369 of 1,414 killed (96.8%); 20 tasks
  admit a survivor. Verus verifies 55 real bodies and **proves a survivor in 14**. By hand
  (`t/vericoding/CLASSIFIED.md`), 13 are gaps and 1 is a tie. The six APPS-derived ones state only that the output is
  well formed; two are satisfied by a constant. The NumPy-derived ones state mostly the output's length.
- **Vericoding Lean:** 16 audited; 213 of 213 killed; **0 survivors**. Lean verifies 12 real bodies.
- The contrast is the finding. The expert-written library and the Lean track pin their results down, including the
  first maximum on ties (ACSL by Example's max_element). In the Verus track, where a solution verified against the
  spec counts as solved, 13 of the 55 verified tasks are solved by a one-edit wrong program as well.

**Bars**, for the clean-clone tables at this registration's commit:
(1) The interpreter's columns (mutants, killed, same, diverge, survivors) reproduce exactly in all three.
(2) The kernel columns reproduce within one task in each corpus: Frama-C 13 real bodies verified, Verus 55 and 14,
Lean 12.

### T56 read (2026-10-07 14:31Z): both bars held, exactly.

All three tables were regenerated from a clean clone at 5e3abec and are installed (`t/AUDIT-ACSLBYEXAMPLE.md`,
`t/AUDIT-VERICODING-VERUS.md`, `t/AUDIT-VERICODING-LEAN.md`). Every row matches the hand runs, kernel columns included.
The D8 picture across four corpora and three kernels:

| corpus | kernel | audited | mutants killed | specs with a survivor | real verified | a survivor proved too | gaps by hand |
|---|---|---|---|---|---|---|---|
| DafnyBench (t can state) | Dafny | 320 | 94.2% | 53 | 316 | 44 | 23 (+3 `ensures true`) |
| vericoding, Verus track | Verus | 63 | 96.8% | 20 | 55 | 14 | 13 |
| vericoding, Lean track | Lean | 16 | 100% | 0 | 12 | 0 | 0 |
| ACSL by Example | Frama-C | 16 | 100% | 0 | 13 | 0 | 0 |
