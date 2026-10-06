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
