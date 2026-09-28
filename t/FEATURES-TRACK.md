# The t features track

t has to grow as the ambition grows (`AMBITION.md`): locallm learns from what t
can say, and the released verified corpora are refused wherever t cannot say it.
This file is the track's plan and stays current: what each missing feature would
unlock, how established languages already do it, what it costs in each of the
seven lowerings, and the order.

**The design rule** (the operator, 2026-09-26). t is not novel for its own sake.
Where an established language already has the construct, copy its design and its
semantics, and cite it. Dafny comes first because the lifted corpora are Dafny,
but any language or data source may be borrowed from (Rust, Python, Haskell,
OCaml, Ada/SPARK, Lean, Why3, Whiley, TLA+, Liquid Haskell, ...) where its
design fits t better. t differs only where its purpose makes the difference
better: every construct must be checkable in all seven kernels (Dafny, Verus,
SPARK, Frama-C, Lean, Rocq, F*), and learnable by a small model (one spelling
per meaning, local reasoning, short programs). Every feature below names the
candidate designs and why the chosen one fits.

## What the corpora say is missing

The 2026-09-26 lift (`t/LIFT-2026-09-26.md`, 1886 staged Dafny files from
HumanEval-Dafny and vericoding) refuses a method at its FIRST blocker, so its
refusal counts overstate what one feature unlocks. The column that matters is
**sole blocker**: methods whose ONLY classify-stage refusal is this feature. It
comes from a census that records every blocker of every method, run 2026-09-26
on the grading machine over the same 1886 files with the lemma-name fix below
applied (the census script is a monkeypatch of `lift_classify._first`; the
numbers are in the table, the script is not committed). 849 methods lift at
classify on that tree. Files the parser refuses have one reason each:
higher-order 91, datatype 56, let-pattern 14, bitvector 12,
stmt-in-expression 10.

| reason | first blocker (lift) | any blocker | **sole blocker** |
|---|---:|---:|---:|
| unbounded-quantifier | 88 | 166 | **57** |
| array | 91 | 146 | **43** |
| calls-other-method (after the lemma fix) | 44 | 92 | **39** |
| set | 89 | 116 | **32** |
| real | 37 | 69 | **17** |
| nested-seq-string | 81 | 119 | **15** |
| nested-seq-other | 150 | 279 | **13** |
| datatype | 73 | 142 | **11** (+56 files the parser refuses) |
| seq-typing | 51 | 312 | 9 |
| seq-update | 13 | 37 | 9 |
| ghost-local | 10 | 39 | 8 |
| seq-slice | 16 | 85 | 7 |
| nat-seq-elements | 11 | 13 | 6 |
| as-cast | 19 | 64 | 5 |
| early-exit | 5 | 10 | 5 |
| string-lib | 10 | 14 | 4 |
| higher-order | 4 | 6 | 1 (+91 files the parser refuses) |
| return-not-assigned-on-all-paths | 67 | 79 | 2 (59 pair with `assume`: specification stubs with no body, not liftable) |
| seq-return | 12 | 215 | 0 (29 pair with nested-seq-other) |

A second measurement matters as much as the refusal counts: **what survives the
check stage and the kernels**. The lifter's check stage refused 32 of the 108
re-lifted tasks below on well-formedness alone, nearly all `spec_fun ... decreases
is not int`: a Dafny function over a sequence whose decreases is the sequence
itself (Dafny's default), which t requires as an int. The same reason cost 32 of
the main lift's 373. That is a lifter-only fix (`decreases s` to `decreases |s|`
where the function's recursive calls shrink the length), costs no kernel work,
and is the next item in the order.

## Done

### 1. Calls to other methods (2026-09-26)

**Refused: 139 methods.** The survey found two problems under one name.

- **113 were lemma calls, refused by a lifter bug.** `lift_parse` never kept a
  lemma's name, so `_closure` never found the lemma, and decision 8 (a lemma
  call is a proof hint, dropped and counted, `LIFTER-DECISIONS.md`) never
  fired. A one-line fix (commit 9fa34ca1). Cheapest per document on this page,
  so it went first.
- **26 were calls of real methods** (28 once the fix let two more files reach
  classify). These needed the language feature.

**The feature: methods with contracts, verified modularly** (SPEC.md "Methods
(v1)", commit 64bed5f7). Candidate designs:

| design | where | verdict for t |
|---|---|---|
| methods with requires/ensures; a caller knows only the callee's contract; each method verified on its own | Dafny (reference manual 6.3, 8.5.2, "Dafny works modularly"), SPARK subprogram contracts, Verus exec fns, ACSL function contracts, Why3 `val`/`let`, Whiley | **chosen.** The corpora's own semantics, and every kernel already has it natively (a call statement with a contract) or already used it for t's self-recursion (Lean's spec theorems, Rocq's contract lemmas, F*'s Pure types). It is also what a small model can learn: a call is understood from its few lines of contract, never from the callee's body, so programs stay local. |
| inlining: a call means the callee's body | C macros; t's own `inline fun` (surface only) | rejected for methods: not what the corpora mean (a Dafny caller cannot see a method body), proofs grow with every call, recursion cannot inline. t keeps `inline fun` for expression templates, where substitution is the meaning. |
| transparent functions: the caller sees the body, bounded by fuel | Dafny `function`, Lean `def`, F* `let` | already in t as `spec fun` (pure, total, recursive), where Dafny functions lift to. |
| refinement-typed functions | Liquid Haskell, F* | the same power as contracts; the contract spelling reads the same in all seven lowerings and matches the source text. |

Differences from Dafny, each for t's purpose: one return (pairs cover two); a
call only as the whole right-hand side of `:=` with call-free arguments (Dafny's
own rule for method calls, kept strict so no kernel has to hoist); methods call
only earlier methods (no mutual recursion, as for spec_funs); the twin never
mutates a method.

**Per kernel.** Fixtures `t/methods/*.t` (max3, clamp_sum, count_pos,
rev_twice) and the modularity probe `t/methods_probe/opaque_callee.t`, whose
ensures holds of the callee's body but not of its contract: a kernel that
verifies it is not reasoning modularly.

Graded together on the grading machine (run_par, flake 3, `--no-cache`),
cell = real / twin; opaque_callee has no twin (nothing to mutate), so its real
was measured on its own, per kernel, on the desktop:

| | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| max3 | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| clamp_sum | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| count_pos | verified / unproved | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| rev_twice | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | timeout / refuted | verified / refuted |
| opaque_callee, real | unproved | unproved | unproved | not proved (the task's ensures, stepout) | unproved | unproved | unproved |

count_pos's twin is an undefined-index witness, for which Dafny emits no
certificate (as for every such twin before methods). rev_twice's Rocq real
times out chaining two per-index sequence facts, the same proof-search limit
that holds outside methods.

| kernel | encoding | the body hidden from callers by | abstains by name on |
|---|---|---|---|
| dafny | a Dafny method | Dafny's own call rule | a method named like the task's lowered method |
| verus | a `proof fn` per method, its loops its own helpers | Verus's own call rule | a method self-calling inside a loop (its helper and the method would be mutually recursive; Verus could not prove termination on a correct probe) |
| spark | an expression function with Pre/Post (Subprogram_Variant when recursive) | `Annotate (GNATprove, Hide_Info, "Expression_Function_Body")`; without it opaque_callee read VERIFIED | a call in a body with an early return; pair-typed methods; a divisor-bound method loop |
| framac | a C function with an ACSL contract; a seq local set by a call lives in a caller-provided buffer whose length is asserted, never assumed | WP's own call rule | a seq local set by a call inside a loop or reassigned; a buffer size not fixed by the parameters; pair or nested-seq method types |
| lean | a def and a spec theorem through the task's own shape dispatch | `attribute [irreducible]` plus `grind_pattern` on the spec theorem | a call of a method whose def takes its requires as a proof argument (self-recursive with requires, domain-guarded loops); parameterless methods |
| rocq | a Definition and a proved contract lemma | the caller's theorem quantifies over the callee as a function variable with a contract hypothesis, closed afterwards with the real method (`Opaque` only affects tactics, so it was rejected) | pair or nested-seq method types; parameterless methods; recursion combined with calls; requires capture |
| fstar | a Pure `let` (`let rec` with its decreases) | `[@@"opaque_to_smt"]`; without it a probe proved `inc x == x + 1` from the body | a call whose result is never read; pair-typed methods; a body that both loops and self-calls |

Tests (no prover): `t/test_methods.py` 8, and one `t/test_lower_<kernel>_methods.py`
per kernel: verus 10, spark 10, framac 13, lean 10, rocq 9, fstar 11. Every
committed task in `t/tasks/` lowers byte-identically in all seven kernels, real
and twin, so `t/AGREEMENT.md` stands unchanged.

What the kernels taught: modularity is not free everywhere. F* shows a caller
the body of a plain `let` even under a Pure contract, and SPARK treats a visible
expression function's body as a postcondition; both verified opaque_callee until
the body was hidden (`opaque_to_smt`; `Hide_Info`). SPARK's and F*'s lowerings
substitute values, which would have skipped the requires of a call whose result
is unused; SPARK now owes it where the call executes, F* abstains. And a twin's
refutation certificate is about what the twin executes, so Frama-C and SPARK
let the certificate (never the real proof) see callee bodies.

**The lifter** (commit 091c9e29, `LIFTER-DECISIONS.md` row 37) lifts a call
`x := M(a)` / `var x := M(a)` of a one-return method whose body itself lifts,
into a `methods` entry; each callee is checked on its own (its own equivalence
lemmas and differential run) before the caller.

**Measured** (the re-lift, `t/lift_corpora.py --only-stems` over the 136 files
the lift refused as calls-other-method; check stage and seven-kernel grading on
the grading machine, run_par, flake 3):

| | files | lifted (classify) | accepted by the corpus gates | new (the lift had refused the method) | kept by the check stage | clean in 7 | clean in exactly 6 |
|---|---:|---:|---:|---:|---:|---:|---:|
| lemma calls dropped (decision 8, fixed) | 136 | 121 | 108 | 96 | 55 new (67 in all) | **3** | **3** (rocq 2, lean 1) |
| method calls lifted to `methods` | the same 136 | 10 more | 9 | 9 | 6 | **0** | **0** (2 clean in five: ModExp_int and ModExpPow2_int, lean abstaining on the recursive Pow and rocq unproved) |

Clean in 7: `vericoding_DA0308 solve`, `vericoding_DA0484 solve`,
`vericoding_DA0531 solve`. Per kernel, of the 55 new lemma-dropped tasks the
check stage kept: dafny 32, fstar 30, spark 28, verus 20, lean 12, framac 11,
rocq 5 verified with the twin refuted. The grading machine was shared and
loaded (load average near 100 of 120 cores) during the run, so some timeouts
may be load, not proof; these are one run's numbers.

**What this bought, and what it did not.** The feature is built and correct in
seven kernels (the fixtures), but the corpus yield is small: 3 new documents
clean in all seven. The measurement says why. Dropping a lemma call keeps the
program and loses its proof: Dafny itself re-proves only 32 of the 55 without
their lemma calls. The lemma is the missing half of the call rule, which is why
lemmas are next. And the method-call tasks fail inside their callees (a
recursive `Pow` Lean abstains on, loops Rocq's proof search cannot close), not
at the call.

### 2. Lemmas: declared, proved, called (2026-09-27)

**The feature** (SPEC.md "Lemmas (v1)"). Candidates: Dafny `lemma` (a ghost
method: requires/ensures, a proof body, a call adds the ensures as a fact);
Why3 `lemma`/`let lemma`; Lean/Rocq `theorem` applied by name; F* `Lemma`;
Verus `proof fn`; SPARK lemma subprograms with a `Post`; ACSL `lemma`
(global, not called) or a ghost function with a contract. Chosen: Dafny's
(reference manual 6.3.3), because it is the method call rule with the return
removed and the corpora's own semantics. A t `lemma` has params, requires,
ensures, a `decreases` when it calls itself, and a proof body of `if`,
`assert` and lemma calls (Dafny's case split, intermediate facts and
induction step); `L(a, b);` is a statement anywhere a statement may stand. It
is a no-op in the interpreter and in every certificate replay; the twin never
touches it. check_wf: `lemma-body`, `lemma-call`, `lemma-decreases`,
`lemma-name`, `lemma-order`.

The plan above said the Dafny proof body would be "a hint, not lowered". The
measurement reversed that: proofs in these corpora are mostly asserts
(1349 asserts in 112 of the 136 files), and a lemma lifted without them is
often unprovable where its source was proved. So t keeps the proof skeleton,
and a kernel that states a step must prove it.

**Per kernel** (a lemma is never assumed: a kernel either proves it in the
file or does not state it):

| kernel | a lemma is | a call is | an `assert` step |
|---|---|---|---|
| dafny | a `lemma`, always with a body (a body-less one is an axiom) | the call statement | `assert` |
| verus | a `proof fn`; recursive spec fns revealed to fuel 2 | a proof-fn call | `assert`; a nonlinear one `by (nonlinear_arith)` over the requires, guards and earlier steps on its path |
| spark | a Boolean function, Pre/Post the lemma, body hidden | an obligation in the value-neutral wrapper where it executes (left out in a body with an early return) | left out (an expression function cannot cut) |
| framac | a ghost C function with an ACSL contract | a ghost call statement | a ghost-code assertion |
| fstar | a `Lemma` (`let rec` with `decreases` for an induction) with a conjunctive `SMTPat` over the spec_fun calls in its ensures | nothing: the pattern hands the proved fact to Z3 | `assert` |
| lean | a theorem, the skeleton as `by_cases`/`have`, closed by grind, well-founded recursion for an induction, `#print axioms` audited | nothing: `grind_pattern` hands it to grind | `have .. := by grind` |
| rocq (2026-09-27, `lower_rocq.py`'s LEMMAS section; before it: not stated, the call removed) | a `Theorem tl_<l>` proved from the skeleton by the file's own automation, a recursive one by induction on a nat fuel bounding its `decreases` (the encoding every spec_fun and self-recursive task already has); the spec_fun applications its ensures names are unfolded once each first (Dafny's fuel of one) | `pose proof (tl_l args) as H; t_feed H` in the proof whose goal covers the call (the theorem; the loop lemma for a loop-body call), each premise discharged where `t_dis` proves it and left as an implication otherwise; a body with no site (self-recursion, nested or multiple loops) states none of the lemmas, as before | `assert (..) by t_dis`, a proved cut |

Fixtures `t/lemmas/*.t` and seeded-fault probes `t/lemmas_probe/*.t`, one
kernel at a time on the desktop (real / twin):

| | dafny | verus | spark | framac | lean | rocq | fstar |
|---|---|---|---|---|---|---|---|
| pow2_pos (induction over a recursive spec_fun) | verified / refuted | verified / refuted | verified / refuted | abstain (a spec_fun in executable position) | verified / refuted | verified / refuted (unproved / refuted before 2026-09-27's LEMMAS section) | verified / refuted |
| sq_bound (a nonlinear fact) | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted |
| sum_loop (an induction step used in a loop) | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted | verified / refuted (unproved / refuted before) | verified / refuted |
| false_lemma (false at its base case) | unproved | unproved | timeout | abstain | unproved | unproved | unproved |
| false_arith (a false nonlinear fact) | unproved | unproved | refuted | timeout | unproved | unproved | unproved |
| circular (`k == k + 1` by calling itself) | unproved | unproved | malformed | timeout | unproved | unproved | unproved |
| false_assert (a false step, correct program) | unproved | unproved | verified | timeout | unproved | unproved (verified before, the step unstated) | unproved |
| false_nonlinear_step (the same, nonlinear, under a guard) | unproved | unproved | verified | timeout | unproved | unproved (verified before, the step unstated) | unproved |

No kernel verifies a program through a false lemma. The two `verified` cells
on the last two rows are SPARK's: correct programs whose false step an
expression function cannot state (Rocq's two read the same until its lemmas
were stated, below). Every committed task, the methods fixtures, 98 lifted tasks and
the 66 conformance items lower byte-identically, real and twin, in all seven
kernels; `t/conformance.py` on the grading machine: 2 FAIL cells before and
after (the same two Frama-C timeouts). Tests (no prover): `t/test_lemmas.py`
16, `t/test_lift_lemmas.py` 4.

**The lifter** (LIFTER-DECISIONS row 38). A lemma the method (or a lemma it
calls) calls lifts when its parameters are t types, it is not generic and has
no out-parameters, its contract lifts and it adds no well-formedness error;
its proof keeps `if`, `assert` and calls of lifted lemmas, with the proof's
own locals substituted in; `calc` and `forall` statements are dropped. A
lemma that does not lift is dropped with its calls as before: lemmas never
make a method refuse. The check stage verifies the lifted lemmas with Dafny's
automatic induction off (Dafny alone of the seven inducts on its own) and
drops any it cannot prove, with their calls.

**Measured** (the 136 files the 2026-09-26 lift refused for calls, through
`t/lift_corpora.py --only-stems`, the check stage and seven-kernel grading on
the grading machine, `run_par --jobs 6` with serial cells; tables
`t/COVERAGE-lifted-2026-09-27-lemmas.md` and, for the same 48 tasks with
their lemmas removed, `t/COVERAGE-lifted-2026-09-27-lemmas-removed.md`):
187 lemmas lifted and 25 not, 179 lemma calls kept and 26 dropped; 117
accepted by the corpus gates (as before); 74 kept by the check stage (73
before), 48 of them carrying lemmas after the check stage dropped an unproved
lemma in 14.

Verified with the twin refuted, per kernel, on the 48 lemma-carrying tasks:

| kernel | lemmas removed | with lemmas | gained | lost |
|---|---:|---:|---:|---:|
| dafny | 28 | 36 | 8 | 0 |
| verus | 16 | 25 | 9 | 0 |
| spark | 25 | 29 | 5 | 1 |
| framac | 9 | 12 | 3 | 0 |
| lean | 8 | 10 | 2 | 0 |
| rocq | 3 | 3 | 0 | 0 |
| fstar | 25 | 30 | 6 | 1 |

Clean documents on those 48: **1 clean in all seven with lemmas, 1 without**
(vericoding_DA0484 both ways); **4 clean in exactly six with lemmas, 3
without** (the new one vericoding_DA0123; the other three are DA0399, missing
lean, and DA0538 and DA0659, missing rocq). Over the whole relift (74 tasks):
3 clean in seven (DA0308, DA0484, DA0531) and 6 in exactly six (3 missing
lean, 3 missing rocq), against 3 and 3 in the 2026-09-26 relift. The two
losses: spark cannot prove DA0524's lemma, whose ensures it proves at the
task without it; fstar's twin of DH0079 times out with the lemma's pattern in
play.

**What this bought, and what it did not.** 33 kernel cells gained against 2
lost, and every kernel but Rocq gains, most of all Dafny and Verus (the
kernels closest to the source's own proof). But one new clean-in-six document
and no new clean-in-seven, because the binding kernels are not the ones
lemmas help: of the 10 lemma-carrying tasks clean in exactly five, 9 miss
Rocq (6 miss Rocq and Lean together). Rocq states no lemma in v1, and its
proof search fails even on straight-line tasks whose lemma is a one-line
bound (DA0659: `result := 48 - m` against a three-function ensures). Lemmas
in Rocq, as proved cuts its automation can use (a `try assert` of each call's
conclusion, then the lemma as a theorem proved by fuel induction), are the
next lever for clean-in-seven on this set; Lean's grind closing the lemma
proofs is the second.

**Rocq lemmas (2026-09-27, later the same day; `lower_rocq.py`'s LEMMAS
section).** Done as described, with one difference from the sketch above:
an `assert` step is a proved cut (`assert (..) by t_dis`), never a `try`,
so a false step fails the file as it does in Dafny, Verus, Lean and F*
(SPARK alone leaves it out, because an expression function cannot cut).
A lemma is `Theorem tl_<l>`, proved from its skeleton by the file's own
automation; a recursive one by induction on a nat fuel bounding its
`decreases` (the encoding every spec_fun and self-recursive task already
has); the spec_fun applications its ensures names are unfolded once each
first (Dafny's fuel of one). A call in the task body poses the instance
where the proof needs it and `t_feed` discharges the premises t_dis can
prove. The refutation certificate is untouched, still built from the
stripped body; a body with no site for an instance (self-recursion,
nested or multiple loops) states none of the lemmas, as before. Fixtures:
pow2_pos and sum_loop now verified / refuted (unproved before); the five
probes all unproved (false_assert and false_nonlinear_step read verified
before, their false step unstated). On the 181 lemma-carrying tasks of the
2026-09-26 lift: 90 state their lemmas (69 abstain on a quantifier in
computational position and 9 on a loop under a conditional, both
pre-existing Rocq refusals; 7 strip; 5 raise on a pre-existing spec_fun
typing gap). Verified with rocq 9.2 without and with their lemmas: 26 and
30; 7 gained (DA0101, DA0113, DA0123, DA0157, DA0368, DA0585, DJ0118),
3 lost (DA0429 times out at 180 s with the instances posed, 25 s without;
DA0472 and DA0476 have a step Rocq's automation cannot close, a division
monotonicity fact, so the whole file reads unproved as SPEC.md says it
must), 23 verified either way. The full table is in
`t/FEATURES-CLOUD-2026-09-27.md`.

### 3. Sequence decreases on spec_funs (2026-09-27, lifter)

**Refused: 93 methods** of the 2026-09-26 lift passed classify and failed
check_wf on `spec_fun .. decreases is not int` (29 of them one `str2Int`).
Dafny orders a `decreases s` over a sequence by its built-in rank (reference
manual 7.1.3); t requires an int. The lifter now lifts such a component as
`len(s)` (LIFTER-DECISIONS row 39) and the check stage verifies the order
rather than trusting it: `L_dec` compares the source's `|s|` with the lifted
`len`, `L_fun`'s strong-induction hint orders by length, and a function whose
body has a one-sided slice gets proved bridges between `s[1..]` and
`s[1..|s|]` (without them `L_fun_sum` read unproved under every induction
hint tried). No kernel changes. **Measured** (the 88 staged files, re-lifted
with the check stage): 24 checked, 47 lift-check-failed, 18 check-wf-failed
(string-returning helpers, since refused `function-result`), 3 differential
timeouts (the arm needs dotnet, absent on the measuring machine), 1 error.
Tests: `t/test_lift_seq_decreases.py`.

### 4. Arrays read by functions (2026-09-27, lifter)

**Refused: 88 methods `array`** (91 first blocker, 43 sole). Decision 1's
read-only array parameter escaped the moment it was passed to a lemma or to
another method. Both are no escape (row 42): a lemma cannot write the heap
(reference manual 6.3.3), a callee whose own parameter is read-only by the
same condition writes nothing through it; a lemma with an array parameter
lifts with a seq parameter. **Measured**: 21 of 88 pass, 14 lift, 12 of those
pass the check stage. The 67 still refused are arrays of char/real/bool/bv32/
a type parameter/arrays, array results, and the in-place sorts (`aliased`: a
mutated array passed to a predicate; 9 of the 11 also need `multiset`).
Later the same day (the in-place writes feature's first shape): a mutated
array passed to a closure PREDICATE is no alias either (a function reads
the value at the point of evaluation, the threaded seq), so `insertionSort`
and `sorting`, the two sorts without `multiset`, lift; both then fail the
check stage on the predicate's equivalence over the mutated array
(`L_inv_0`, `L_fun_insertionSorted` unproved). A fixture for that shape
caught a check-stage bug: it re-derived decision 22's shape without the
module, so a lemma call still counted as an alias there and the
synthesised return was typed `int`; the alias checks read lemma names from
the closure too now. Tests: `t/test_lift_array_functions.py`.

### 5. Quantifier bounds (2026-09-27, lifter)

**Refused: 88 methods `unbounded-quantifier`** (166 any, 57 sole). The
lifter now finds the bound where Dafny left it implicit (row 40): inside a
called predicate's body, in a `<`/`<=` chain over several binders, in a
`nat` binder's implicit lower bound, or eliminates a binder an equality pins
(the one-point rule, Gries and Schneider (8.14)); a quantifier with no finite
range stays refused, since the interpreter cannot evaluate it and a twin has
no witness. **Measured**: 50 of 88 pass the gate, 24 lift, 10 pass the check
stage (11 equivalence lemmas unproved, in two of them after the source's own
sum lemma was dropped `lemma-dropped-unproved`; 3 check-wf-failed).
Tests: `t/test_lift_quant_bounds.py`.

### 6. Multi-return calls (2026-09-27, lifter)

**Refused: 5 methods `method-call-multi-return`** and 12
`multi-return-nested`. `a, b := M(x);` binds the callee's pair return to a
fresh local and the two names to its projections (row 41). **Measured**: all
5 pass the call rule; none lifts, each callee refused on its own terms
(`seq-typing`, `return-not-assigned-on-all-paths`, `seq-update`). The 12
`multi-return-nested` are two out-parameters with a component t's pair does
not carry (array, real, char, a datatype) and are unchanged. Tests:
`t/test_lift_multi_return_calls.py`.

### 7. Nested string sequences, and strings for the Lean front end (2026-09-27, lifter)

**Refused: 79 methods `nested-seq-string`** (Dafny) and 119 Lean files
`string`/`char`. `seq<string>` and `seq<seq<char>>` lift as t's nested seq
with code-point rows (row 43: row 28 per row, as row 30 lifts int rows); a
nested name's rows are seq-kinded, so `xs[i][..k]` resolves; the checker
views such a name row by row and the differential harness prints nested
points (row 30's own residual). **Measured**: 37 of 79 lift at the rewrite
stage; through the check stage 3 checked, 25 refused `function-result`, 5
lift-check-failed, 3 check-wf-failed, 1 differential timeout. The binding
gap is a helper FUNCTION returning a string (or any seq): a t spec_fun's
result is int or bool (SPEC.md), so such a function cannot lift, and it now
refuses by name, `function-result`, where before it was lifted with an int
result and failed check_wf a stage later (135 methods of the 2026-09-26
lift). Seq-returning spec_funs in t, across the seven kernels, is the next
lever for every string program with a helper.

The Lean front end (`t/lift_lean.py`) reads `String` as Dafny's `string` and
`Char` as `char`, each String/Char operation by its Lean core definition
(`.length`, `.data`/`.toList`/`String.mk`, `++`/`.push`, `.take`/`.drop`/
`.dropRight`/`.takeRight` as slices, `.startsWith`/`.endsWith` as slice
equality, `.contains`, `Char.toNat`, the ASCII class tests as core's
ranges), and refuses by name what has no Dafny expression: `string-pos` (a
`String.Pos` is a UTF-8 byte position), `string-lib` (`splitOn`, `trim`,
`toNat?`, ...), `char-case`. The equivalence harness views a String as
`s.toList.map (fun c => (c.toNat : Int))`. **Measured** on the 119 files:
33 render, 18 lift (10 `function-result`, 5 `unbounded-quantifier`), and
the Lean harness proves none: `grind` stops on the code-point range clause
`string-elements-requires` adds to the lifted requires. A standalone probe
proved the char bound (`c.toNat <= 1114111` from `Char.valid`) and the
length half (`String.length_toList`, `List.length_map`) but not the clause
over the mapped list's `!` index; teaching the fixed cascade that one fact,
or letting the Lean track drop the clause it never needs (no `dafny run`
there), is what stands between these 18 and a proved equivalence. Tests:
`t/test_lift_nested_strings.py`, `t/test_lift_lean.py`.

### 8. Tuples (2026-09-27, lifter)

**Refused: 27 methods `tuple`.** A two-component Dafny tuple (reference
manual 5.6.3) is t's pair under the source's own name (row 44): the return
type `(int, int)`, a parameter or local, the literal `(a, b)`, `p.0`/`p.1`;
a `nat` component keeps its guard or ensures on the projection; `tuple-arity`
and `tuple-component` name what t's pair cannot carry. **Measured**: 10 of 27
lift, 7 pass the check stage; 8 of the other 17 refuse `function-result`
(a tuple-returning helper). Tests: `t/test_lift_tuples.py`.

### 9. Nested sequences named by their element (2026-09-27, lifter)

**Refused: 113 methods `nested-seq-other`** on the 1886 staged files of the
2026-09-26 lift (the round-2 census, merged lifter). The name hid what they
were: 84 hold `seq<real>` or `seq<seq<real>>` (the numpy-shaped vericoding
files), 20 `seq<T>` under a type parameter or a datatype, 5 `seq<bv32>`, one
`seq<(int, int)>`, one `seq<seq<bool>>`, one `[i % 3 == 0]`, one
`[('0' as int + digit) as char]`. Each now refuses under its element's own
name (row 46: `seq-of-real`, `seq-of-datatype`, `seq-of-bitvector`,
`seq-of-pair`, `seq-of-bool`, `seq-of-set`, `seq-of-map`), so the census
ranks them with `real`, `datatype` and `bitvector`; a cast to char or int
inside a display is an int element, so `[c as char]` lifts when the cast is
safe and refuses `char-cast-unbounded` when it is not. **Measured**: 0 of
the 113 lift, because none is a t value (reals, bitvectors and datatypes
have no t type; a seq of pairs or of bools is "Not in v1", SPEC.md "Nested
sequences"); 84 read seq-of-real, 20 seq-of-datatype, 5 seq-of-bitvector, 2
seq-of-bool, 1 seq-of-pair, and one is
the `[.. as char]` display whose cast bound the syntactic rule cannot see, and 113 of 113 read as one of the seven names or `char-cast-unbounded`.
The lever this leaves is a range analysis for `(lit + e) as char` under a
`requires` on `e`, which is what the int-to-string helpers need. Tests:
`t/test_lift_seq_elements.py`.

### 10. Zero-return methods named by what they are (2026-09-27, lifter)

**Refused: 39 methods `zero-returns`** on the 1886 staged files. SPEC.md
already decides what t makes of a method with no out-parameter: a task
whose return is its mutated array (decision 22, "a method whose effect is
its array is a task whose return is a seq"), or nothing. So the bare name
is retired and the refusal says why the shape did not apply (row 47): a
mutation issue `find_array_mutation` had already named stands alone (the
method-line `zero-returns` used to hide it by line order); a `modifies`
whose writes are all a callee's refuses `array-mutation`
(`modifies-via-call`), one with no write `modifies-no-index-assign`; a
method with neither return nor `modifies` is a lemma about its parameters
(SPEC.md "Lemmas (v1)") and refuses `lemma-shaped`. **Measured**: of the
39, 34 read `array-mutation` (23 of them the vericoding DJ family, which
writes two arrays, `a[i] := 0` and `sum[0] := total`), 4 `lemma-shaped`, 1
`array`; 0 lift. The lever is a task returning a pair of seqs for the
two-array methods (t's pair holds two seqs already); not built here. Tests:
`t/test_lift_zero_returns.py`.
### 11. Finite sets (2026-09-27, SPEC.md "Finite sets (v1)", six lowerings touched)

**Refused: 77 methods `set`** on the 1886 staged files (round-2 census): 39
the cardinality of a bounded comprehension used as a count, 30 a display
(`s[i] in {'G', 'T', '.', '#'}`), 8 a `set<int>` parameter or return. t now
has the type `set` (a finite set of ints) with six total operations, the
display `{e1, ..., en}`, `x in s`, `card(s)`, `union`, `inter`, `setminus`
(spelled `diff` at first, respelled the same day -- see below), written by
name, `==` extensional (SPEC.md "Finite sets (v1)", SYNTAX.md);
`surface.py` parses and prints it (26 of 26 written examples, 1846 of 1846
corpus tasks and 3000 fuzzed ASTs round-trip), `check_wf` types it,
`interp` runs it on a frozenset with its own domain ladder, and
`fuzz_lower` carries nine probes `fz_p_set_*` (duplicates collapse,
inclusion-exclusion, difference against intersection, extensional equality,
an adversarial union count and duplicate count, membership through an
intersection, the empty display, a set-collecting loop) plus two committed
tasks, `tasks/set_toggle.t` (add or remove one element, four cardinality and
membership ensures; twin `collapse-if`) and `tasks/set_collect.t` (a loop
collecting a seq into a set; twin `compare-flip`). The comprehension is not
in v1 (its predicate needs a binder every kernel would close over; SPEC.md
says how it will be stated), and the lifter's mapping of Dafny's `set<int>`
onto the type is not built, so no corpus method lifts yet: the 38
display-and-typed-name methods are what that mapping would reach.

Per kernel, measured on this machine (the nine probes as expected with
twins refuted, the two tasks verified with twins refuted, unless noted):

| kernel | representation | probes | tasks | note |
|---|---|---|---|---|
| dafny | `set<int>`; `{..}`, `in`, `\|s\|`, `+ * -`; the empty display let-bound to a typed name | 9 of 9 | 2 of 2 | `\|{}\|` is underspecified and a false-ranged comprehension is rejected as not finite, measured; hence the let |
| verus | `vstd::set::Set<int>`; `set![..]`, `contains`, `len`, `insert`/`remove` for a singleton union/difference, `union`/`intersect`/`difference`; vstd's three broadcast groups plus one prelude lemma (empty difference is inclusion) in its own module; `==` bridged to `=~=` | 9 of 9 | 2 of 2 | the ground certificate over sets is closed by the SMT arm, `compute_only` cannot evaluate a cardinality (measured) |
| fstar | `FStar.FiniteSet.Base` with `FStar.FiniteSet.Ambient`; a task that uses sets is lowered in the Ghost effect (`cardinality` is GTot, equality the ghost decision of `equal`) | 9 of 9 | 2 of 2 | `union` with a singleton is spelled `insert`, the one law the ambient facts do not close otherwise |
| rocq | Stdlib 9.2 `MSetList.Make Z_as_OT` with `MSetProperties`; prelude lemmas and `t_inv1` arms for membership, negative membership, the four cardinality laws and set equality | 9 of 9 real; 9 of 9 twins refuted (`fz_p_set_eq`'s twin ran to the wall until the certificate computed its closed set atoms, `t_set_ground`) | set_collect and set_toggle both verified and both twins refuted: a set-valued twin result is certified by `S.Equal` (MSetList values carry a sortedness proof, so two computations of one set are not Leibniz-equal), pushed under `S.cardinal` by `P.Equal_cardinal` and into `S.In` at its element, and the closed set atoms that remain are decided by `vm_compute` (`t_set_ground`) | |
| lean | none: core Lean 4, no Mathlib, no finite set | abstain by name | abstain | a sorted duplicate-free `List Int` is the encoding to build and measure |
| framac | none: C has no set value | abstain by name | abstain | a sorted-array encoding with WP proofs is the encoding to build |
| spark | none yet: `SPARK.Containers.Functional.Sets` exists but has no difference function and its cardinality laws are unmeasured here | abstain by name | abstain | the instantiation is the next step |

Byte identity: every set-free committed task lowers byte for byte as before
in all seven kernels (48 fixture tasks, real and twin, `sha256` before and
after). No twin-generator, grader or check-filter change: the ladder's
existing moves (`wrong-var` over two set names, `off-by-one` on an int,
`collapse-if`, `compare-flip`) found a refuting twin for every probe that
has one.

**Regression, found and fixed the same day: `diff` collided with a common
identifier.** `set`, `card`, `union`, `inter` and `diff` all became
keywords when this landed. `diff` is a common variable and return name:
4 documents of the proved corpus (dafny_synthesis_task_id_145__maxDifference,
vericoding_dd0675__maxDifference, vericoding_dd0740__differenceSumCubesAnd
SumNumbers, vericoding_da0528__solve) and lifted task files across
`t/out/lifted-tasks/`, `-2026-09-26/`, `-2026-09-26-rechecked/` and
`-2026-09-26-recovered/` named a return or local `diff`, and every one
stopped parsing (`expected 'id', found 'diff'`) or stopped printing (`'diff'
is a keyword ... and has no notation as a name`). Nothing caught it: the
corpus builder (`t/loop_locallm.py cmd_corpus`) kept writing the 4 documents
unchecked, `locallm/chat_data.py`'s broad exception handler silently
dropped them from training, and `t_tool` would have rejected any model
answer that named a variable `diff`. `set`, `card`, `union` and `inter`
collide with nothing in the corpus and keep the named-operation style (as
`len` and `tostr` do); only `diff` is respelled, to `setminus` (the AST op
tag stays `"diff"`, so no lowering, `check_wf` or `interp` changed -- see
SPEC.md's "Set difference is spelled `setminus`" paragraph for the full
account). `t/loop_locallm.py` gained the guard that was missing: it now
refuses, by name and with the parse error, any document about to be
written that does not parse with the current surface, and two tests
(`t/test_set_keyword_surface.py`, `t/test_corpus_parse_gate.py`) hold both
the fix and the guard in place. Byte identity: unaffected -- the two
committed set tasks' surface changed (`tasks/set_toggle.t`'s `diff(a, {x})`
is now `setminus(a, {x})`), their AST and lowering did not (`sha256`
checked across all seven kernels, real and twin, against `r12-blockers`).

### 12. A return unassigned on a path opens with its default (2026-09-27, lifter)

**Refused: 69 methods `return-not-assigned-on-all-paths`** on the 1886
staged files. The refusal rested on a reading of Dafny that was wrong both
ways (row 45): Dafny checks definite assignment of an out-parameter as a
verification obligation, so a method the syntactic walk refuses (`while
true { .. r := i; return; }`, an if-case, a `break` then a guarded
assignment) verifies, and one that truly leaves the return unassigned does
not. The body now opens with the return type's default and the check stage
keeps the task only when `dafny verify --filter-symbol M` accepts the source
method (`verify-source`), refusing `return-default-unverified` otherwise;
`char` returns refuse `return-default-char`. **Measured**: 61 of the 69 are
`assume` stubs (the table above foresaw them), 4 lift (all four sources
accepted by dafny), 1 of the 4 passes the check stage, 3 fail it on
unrelated lemmas; 4 refuse elsewhere. Tests:
`t/test_lift_return_default.py` (6, plus 2 slow: one accepted source, one
refused `return-default-unverified` with dafny's own message).
### 13. Seq-valued spec_funs (2026-09-27, language and lifter)

**Refused: 135 methods `function-result`** of the 2026-09-26 lift (a helper
function returning `string` or `seq<int>`); **305 methods** in the
2026-09-27 baseline re-lift of the 1,886 staged files without the check
stage, this feature's own run (`t/FEATURES-SEQFUN-2026-09-27.md`: 86
`string`, 66 `bool`, 58 `real`, 31 `seq<string>`, 25 `seq<int>`, 5
`seq<char>`, 2 `seq<nat>`, the rest sets, tuples, bitvectors, type
synonyms). A spec_fun's result may now be a seq of ints (SPEC.md
"Seq-valued spec_funs (v1)"; `"result": "seq"` in SYNTAX.md, `spec fun
f(..): seq` in the notation): a call is a seq expression wherever an int
call is an int expression, indexed, measured, sliced, concatenated and
compared as any seq. The lifter lifts a function returning `string`,
`seq<char>`, `seq<int>` or `seq<nat>` to one (LIFTER-DECISIONS row 49),
with the empty seq as the totalising default, and a `function F(..): bool`
as the bool spec_fun a `predicate` already was (row 50: the 66 `bool`
tokens were an omission of the 2026-09-27 check, not a language gap). All seven
kernels lower the seq result in their own sequence type since 2026-09-27
(`feat/framac-seq-fun`): Frama-C states it as a recursive `\list<integer>`
logic function, bridged to a buffer-typed seq value at `==`/`len`/`at`
through ACSL's own built-in `\length`/`\nth` (t/FEATURES-SEQFUN-2026-09-27.md
"Frama-C, the `\list` route" has the numbers; what the route does not
reach still abstains by name). Fixtures: the committed task
`t/tasks/double_all.t`, four probes `fz_p_sf_seq_*` in `t/fuzz_lower.py`.
**Measured** (same run, same files): `function-result` 305 to 139
methods, lifted 850 to 955, 104 methods in 101 files newly lift at the
rewrite stage (72 by the seq result, 32 by the bool one); the check stage
on the desktop: 55 checked (35 with a seq-valued spec_fun), 47
`lift-check-failed` (the helper's own `L_fun` lemma, mostly), 2
`check-wf-failed`; the seven-kernel grading of the 55: none clean in
seven, 2 clean in six with Frama-C's abstain the missing column (dafny
29, spark 27, verus 26, lean 18, fstar 18, rocq 5 verified/refuted; 12
with no twin). The fixtures read verified/refuted in six kernels and
abstain in Frama-C. Runs, per-kernel tables and what still refuses are
in `t/FEATURES-SEQFUN-2026-09-27.md`. Tests: `t/test_seq_spec_fun.py`,
`t/test_lift_seq_fun.py`. The 2026-09-27 review seeded faults into the
spec_fun's own body and found dafny and F* reading two of three
unproved; the fix (the same file, "The review and the seeded faults")
ladders every seq-valued call and the ground seq operators around it in
those two certificates, and moved 6 corpus twin cells from unproved to
refuted (dafny 29 to 30, F* 18 to 22 of the 55 checked tasks).

### 14. Source-axiom, source-assume: refusing sources dafny accepted unchecked (2026-09-27, lifter)

**Refused: 74 methods across 80 staged files carrying `{:axiom}`/`{:verify false}`/`assume`**
(69 with `{:axiom}`, 68 with a raw `assume` token, of the 1,886 staged files) -- 61
`source-assume` directly, 10 `callee-refused:source-assume` (a lemma the method calls
hides the assume in its own proof), 3 `source-axiom`. Dafny's `{:axiom}` (Reference
Manual 11.2.4) means a lemma's/function's/method's ensures "may be assumed to be true
without proof," and `{:verify false}` (11.2.22) skips even well-formedness; neither
checks the declaration's body against what it claims. vericoding's DT0258
`NumpyBitwiseOr` (t/LIFT-2026-09-26.md's last section) names the failure mode: its
`BitwiseOr` is a placeholder returning 0, and its only stated properties are
`lemma {:axiom}` facts false for that body (`BitwiseOr(x, 0) == x` only when x == 0);
dafny accepts the source anyway, so it "verifies" without dafny ever checking the one
thing the lift would grade. `lift_classify.py` now reads, per source file, every
`{:axiom}` attribute (on lemmas -- kept only in `LemmaDecl.text`, since `attrs` is not a
stored field for a lemma the way it is for a function or method -- functions and
methods), every `{:verify false}`, and every `assume` statement (attributed or not),
then refuses `source-axiom` when the method's spec, body, invariants or the closure of
functions and lemmas it uses references a declaration that is axiomatised or a function
whose only stated properties come from axiom lemmas (`_axiom_only_functions`), and
`source-assume` when an assume lies in the method's own body or in a lemma/callee it
uses. An axiom the method's closure never touches still lifts, noted `axiom-in-file` in
the sidecar (LIFTER-DECISIONS row 51). **Measured** (`t/lifter.py --list` over the union
of the two staged sets, `--skip-check --jobs 4`, `~/scratch/axiom/out`): DT0258 reads
`source-axiom` (token `BitwiseOr`, the placeholder function at its declaration); of the 69 `{:axiom}` files, 3 have a
method refused `source-axiom` directly (`DT0258`, `DT0333`, `DT0360`; most of the rest
also carry an `assume` in the graded method's own body and are caught there first); of
the 68 `assume`-token files, 35 have a method refused `source-assume`. Of the 74 newly
refused methods, only 1 (DT0258's `NumpyBitwiseOr`) had ever lifted before across any
`t/out/lifted-tasks-*` run, and it is in neither the 552-document nor the
454-document corpus (`~/scratch/corpus-2026-09-27-6.txt`, `-7.txt`): the twin/kernel
gate had already excluded it, so this rule's corpus effect today is 0 documents -- its
value is catching the defect at classify, before seven kernels are spent proving a spec
that is false of the very body they would grade. One limitation found and left as is, by
the letter of the decision: `assume{:axiom} false;` inside an unrelated, no-ensures
sibling method (`vericoding_DD0311`, `DD0520`, `DD0521`, `DD0598`: a common boilerplate
"Testing'" stub) sits in neither the graded method's body nor a callee it uses, so it is
not refused and gets no note -- the decision names an axiom DECLARATION outside the
closure for the note, not a stray assume in a method the graded one never calls. Tests:
`t/test_lift_source_axiom.py`.

**Review round (2026-09-27)** found the closure walk this check used (`_closure`,
function/lemma callees only) dropped an axiom-attributed callee METHOD entirely instead
of checking it: `method {:axiom} DoubleIt(...) ensures r==2*x { r := 0; }` called by
`UsesDoubleIt` (same `ensures`) lifted clean through the real pipeline, carrying
`DoubleIt`'s false ensures into the task as ground truth -- DT0258's own hazard through a
method instead of a function+lemma pair. Fixed with `_closure_incl_methods`, a
`MethodDecl`-inclusive walk used only by this check (`_closure` itself stays
function/lemma-only for its other three callers, which assume a side-effect-free,
provable-body closure). `UsesDoubleIt` now refuses `source-axiom`; a sibling method that
never calls the axiom method still lifts, noted `axiom-in-file`. Also fixed in this
round: the token `classify` named for DT0258 varied between runs (two issues on one line, the
tie broken by a set's iteration order); the closure walk now follows the source order of calls and an
axiom-only function is recorded at its own declaration, so the witness is `BitwiseOr` on every run. See LIFT-2026-09-26.md's review-round section for the
reproduction and the one item raised that was not a row-51 gap (`{:verify false}` on a
method's own declaration never reaches `classify`; `lift_resolve.py` refuses it first, a
pre-existing narrowing outside this diff).

### 15. Finite sets, the lifter's own mapping (2026-09-27, lifter only)

Done 11 (above) built the type and its six operations in four kernels, abstaining by
name in SPARK, Frama-C and Lean, but left the lifter's own mapping of Dafny's
`set<int>` onto the type unbuilt: "the 38 display and typed-name methods are what it
would reach" (t/FEATURES-CLOUD-2026-09-27-r2.md's own count, 30 display + 8 typed
name, of the 77 methods the round-2 census refused `set`; the other 39 are set
comprehensions, out of scope by SPEC.md's own note and still refused, now under the
sharper name `set-comprehension`). `lift_classify.py` now admits a `set<int>`
parameter, return or local (declared or inferred from an untyped local's own
initialiser); a display `{e1, ..., en}`/`{}` whose every element is int-typed; `in`/
`!in` to t's own `in` operator (kept as decision 2's bounded-exists desugaring for a
seq); `|s|` to `card` rather than `len`; and Dafny's `+`/`*`/`-` between two sets
(Dafny Reference Manual 5.5.1: the same three symbols overload set union,
difference and intersection) to t's own `union`/`diff`/`inter`, checked ahead of the
existing seq/int reading of the same symbols. Refused by name, precisely at the
boundary SPEC.md draws: a set comprehension (`set-comprehension`); `set<T>` for T
not int (`set-of-bool`/`set-of-real`/.../`nat-set-elements` kept distinct, the same
reading a `seq<nat>` already gets); a bare `set` with no `<T>` (`set-generic`);
`iset` and `multiset` (a `multiset{...}` display reuses the `SetDisplay` AST node,
so `lift_ast.SetDisplay` grew a `multiset` field to keep the two apart now that a
genuine set literal can lift); a subset/superset comparison (`set-subset`) and
disjointness (`set-disjoint`, Dafny's `!!`); a set used as a quantifier's own range
(`unbounded-quantifier` -- SPEC.md: "Not in v1: ... a set as a quantifier's range";
decision 2's own membership-binding rule was never type-aware before this row, and
would otherwise have tried to desugar `forall x :: x in c ==> P(x)` for a set `c`
into a nonexistent index range); and a set-typed spec_fun parameter
(`set-spec-fun-param`, a gate that did not exist anywhere before this row). The
check stage's equivalence lemmas print the six ops back to Dafny (`_t_expr`), the
differential harness compares set-typed points order-free (Dafny's own printed set
element order is unspecified, measured on dafny 4.11.0), and the membership-bridge/
pointwise proof helpers skip a set-typed collection rather than hand it the
seq-shaped `|R|`/`R[j]` bridge those build for a genuine seq.

**Measured** (`t/lifter.py --list --skip-check --jobs 4` over the 1,886 staged
files of the 2026-09-26 lift, diffed method by method against `t/out/lifted-tasks-
2026-09-27-features2.meta/lift`): of the 83 methods this baseline refused `set`,
**7 now lift** -- every one a display shape (`x in {..}`, `{..} + {x}`), none a
typed-name method: the realistic typed-name spec, `forall x :: x in c ==> P(x)`,
turns out to need exactly the one thing SPEC.md excludes from v1 (a set as a
quantifier's own range), which is why the yield is 7, well under the 30-display-
plus-8-typed-name upper bound `t/FEATURES-CLOUD-2026-09-27-r2.md` estimated before
this row was built. The other 76 refuse by a sharper name than before: 46
`set-comprehension` (unchanged in substance, SPEC's own "wave after"), 11
`set-of-seq` (a `set<string>` display), 6 `unbounded-quantifier` (the set-as-range
shape above), 3 `set-spec-fun-param`, 2 `function-contract`, 2 `function-result`,
1 each of `such-that-exec`/`set-of-char`/`seq-update`/`nat-set-elements`/
`tuple-projection`/`as-cast`. 972 of 1,886 files' methods lift in total, up from
966 (net +6: +7 gained, -1 -- `vericoding_DT0258`'s `NumpyBitwiseOr`, now
`source-axiom`, row 51, already on `r12-blockers` before this branch and dated
ahead of the baseline snapshot; checked against every one of the 1,886 files'
methods for an unexpected transition into a refusal this row touches, and found
none, so this is the one pre-existing, unrelated difference between the baseline's
timestamp and this branch's, not a regression). Of the 7, the full check stage
(`t/lifter.py --list --jobs 4`) checked 3 (`vericoding_DA0038`/`DA0633`'s `solve`,
`vericoding_DD0729`'s `MonthHas31Days`) and left 4 `lift-check-failed` on an
unproved `L_fun_*`/`L_inv_0` lemma unrelated to the set machinery (each method's
own character/string logic; not investigated further). Graded in all seven kernels
(`t/run_par.py --jobs 2`, `systemd-run --user --scope -p MemoryMax=9G`,
`T_SPARK_JOBS=1`): `DA0038`/`DA0633` are vacuous (no input in the bounded probe
domain satisfies their own `requires`; nothing measured, an existing harness
category, not a set-specific gap). `DD0729` (`month in {1, 3, 5, 7, 8, 10, 12}`)
is verified/refuted (clean) in dafny, verus and f\*, an honest abstain in
SPARK/Frama-C/Lean exactly as Done 11's own table states, and **unproved/unproved
in rocq** -- a real proof gap, not a documented abstention, so **0 of the 7 newly-
lifted methods reach graded-trust admissible today**; the yield of this row is the
sound type-and-operator mapping and an honest corpus count, not a clean-in-four
document -- reported plainly rather than rounded up. Tests: `t/test_lift_sets.py`;
a full CI
run (`t/ unit tests that need neither provers nor torch`) found and this change
fixed two tests asserting the old refusal (`test_lift_rules.py::
test_set_refused_before_rewrite`, `test_function_reads_own_array_param_dropped` --
the second a real regression, not a stale assertion: moving `SetDisplay`'s refusal
out of the generic per-node scan the way rows 25-27 already moved `SeqDisplay`
dropped the `accepted_ids` exemption `_dropped_function_decreases_set_ids` needs
for dafny's own inferred `decreases {a}, a, x` on a `reads`-bearing, non-self-
calling closure function; restored, with the exemption checked first in the new
dedicated pass too).
### 17. Datatype refusals named by what they touch (2026-09-27, lifter)

**Refused: 78 methods `datatype` and 56 files `parse:datatype`** on the 1886
staged files. Read at the source, 42 of the 78 touched no datatype: `.0`/`.1`
on an element of a `seq<(int, int)>`, `Length0`/`Length1` on an `array2`,
`.Floor` on a real, `type` synonyms, members of imported modules. Row 48
names each by what it is and names a real datatype use by the shape of the
file's declarations, read from the skipped declaration's tokens:
`datatype-enum`, `-record`, `-sum`, `-real`, `-generic`, `-recursive`; the
parser splits `match` by its first case pattern into `match-literal` and
`datatype`. **Measured** (re-lift of the 78): 18 `seq-of-pair`, 17
`datatype-real`, 9 `function-result`, 8 `type-decl`, 8 `datatype-record`, 5
`tuple-projection`, 4 `datatype-generic`, 3 `array2`, 2 `datatype-sum`, 1
each `datatype-enum`, `set`, `opaque-type`, `real`; 0 lift. Of the 56 files,
41 match on constructors and 15 on literals (12 int, 2 char, 1 string). The
reach of a non-recursive datatype without reals or type parameters is
therefore 11 methods and at most 8 files, against a declaration form in
seven kernels and twin moves over constructors ("The features ahead: 10.
Datatypes"); it was not built this round, and the numbers say what to build
first instead: `match-literal` as an if-chain (Done 18: built, 1 file
lifts, the rest match on chars or lack a default) and a record of ints as
an n-ary pair (8 methods). Tests: `t/test_lift_datatypes.py`.

### 18. A `match` on int literals with a default lifts as an if-chain (2026-09-27, lifter)

**Refused: 15 files `match-literal`** after Done 17's split of the parser's
`match` refusal. Dafny tries a match's cases in order, takes the first that
matches, and `_` matches everything, so over int literals with a `_` default
the construct is exactly an if-chain over `==`. The parser builds that chain
(row 54) as the IfStmt/IfExpr nodes every later stage already handles,
statement and expression form, and the classifier logs
`match-literal-if-chain`; a char or string literal keeps `match-literal`
(t compares neither yet), a missing `_` refuses `match-no-default` (an
if-chain needs an else and exhaustiveness would rest on the precondition).
**Measured**: 1 of the 15 files lifts (vericoding DD0831, FibonacciIterative
through its spec_fun Fibonacci) and passes the check stage with every
checker lemma verified; 9 still refuse `match-literal` (a match on a char or
string in the same file), 5 `match-no-default`. Tests:
`t/test_lift_datatypes.py` (8, plus 2 slow: dafny proves both if-chains
against the source clauses).

## The order from here

Ranked by documents unlocked per unit of effort, where documents unlocked is
the sole-blocker count (a floor: files the parser refuses are not in it) and
effort is the lowering work across seven kernels plus the lifter.

| # | feature | unlocks (sole) | effort | why here |
|---|---|---:|---|---|
| 3 | seq `decreases` on spec_funs (lifter only) | 32 of 108 in the re-lift, 32 of 373 in the lift, at the check stage | lifter only | no kernel cost |
| 4 | arrays read by functions (`function f(a: array<int>) reads a`) | 43 | lifter only: decision 1 already lifts a read-only array parameter to a seq value; extend it to functions that read one | no kernel cost |
| 5 | quantifier bounds through predicates and one-sided ranges | part of 57 | lifter first (infer the range from a predicate's body or a one-sided guard); truly unbounded quantifiers stay refused | the interpreter cannot evaluate an unbounded quantifier, so no twin witness; bounds are what makes a twin measurable |
| 6 | multi-return calls (`a, b := M(x)`) | 4 | pairs exist; destructuring is surface plus lifter | small |
| 9 | finite sets | 32 | all seven kernels, a new type | large |
| 10 | datatypes | 11 + 56 files | all seven kernels, a new declaration form | large |
| 11 | higher-order functions | 1 + 91 files | all seven kernels | largest |

Rows 3 to 6 landed 2026-09-27 (Done, above), with nested string sequences,
Lean strings and tuples beside them; the measured yield of each is in its
entry. The seq-valued spec_fun (the binding refusal for string programs,
`function-result`) landed 2026-09-27 as entry 13. Finite sets landed as
entry 11/15; datatypes landed its first wave (enumerations) as entry 16,
below, records and non-recursive sums still ahead of it; higher-order
functions remain, and one gap the measurements named ranks with them: the
in-place sorts' `multiset` permutation specs. A Frama-C lowering of the
seq-valued spec_fun (ACSL `\list`) is the one open kernel column of entry
13.

### 16. Datatypes: enumerations (2026-09-27, SPEC.md "Datatypes (v1)", three lowerings touched)

**Refused: 73 methods `datatype` at classify, plus 56 files the parser
refuses on `match`** (the 2026-09-27 round-2 census, t/FEATURES-CLOUD-
2026-09-27-r2.md, which also named the shapes: `datatype-enum`, `-record`,
`-sum`, `-real`, `-generic`, `-recursive`, and the parser's own
`match-literal`). This wave states the first and simplest of those shapes
end to end: **enumerations**, a datatype whose constructors carry no
fields (SPEC.md "Datatypes (v1)"). t now has a per-task `datatype D = C1 |
C2 | ...` declaration, the type `{"datatype": D}`, a constructor value
`D.C`, structural `==`/`!=`, and a total `match` (surface keyword `case`,
not Dafny's own `match`: `tasks/probe_names_fstar.t`/`probe_names_lean.t`
deliberately use `match` as an ordinary t parameter name, proving F*'s and
Lean's own reserved words do not leak into t, so reserving it would have
broken that exact probe -- the same reasoning `setminus` was chosen over
`diff` for). `check_wf` types `ctor`/`match` (four new rule names,
`match-coverage` proving the arm-to-constructor bijection); `interp`
evaluates them on a new `Ctor` dataclass value and gives every declared
datatype its own domain ladder (the whole, small, finite list of its
constructors); `surface.py` parses and prints the notation (2 of 2 new
written examples, 1919 of 1919 corpus tasks still round-trip); the twin
ladder gains `SWAP-CTOR` (`harness.py` `_c_swap_ctor`: two of a match's
arms trade bodies), and the ladder's generic expression walk was extended
to descend into `ctor`/`match` nodes, so every EXISTING move also now
reaches a match arm's body for free. Four probes state the construct's
laws (`fz_p_dt_match_total`/`_bad`, `fz_p_dt_eq`, `fz_p_dt_match_eq`) and
one committed task, `tasks/color_code.t` (a three-constructor enum read
back as its own int code; twin found by the pre-existing `off-by-one` move
alone, one arm's literal bumped). Records (one constructor, int/bool/seq
fields) and non-recursive sums are FEATURES-TRACK's own next two waves;
recursive datatypes stay out of v1, permanently for now (no termination
measure built for a recursive constructor). The lifter's own admission of
Dafny's `datatype`/`match` source syntax is NOT built this wave
(LIFTER-DECISIONS.md row 53): `lift_classify`/`lift_parse` still refuse
every one of the 73 + 56 files the census counted, unchanged, so no corpus
method lifts through this construct yet.

Per kernel, measured on this machine (`fz_p_dt_match_total`/`color_code`,
real verified, twin as noted):

| kernel | representation | note |
|---|---|---|
| dafny | native `datatype`/`match`, the source construct itself | real verified (`dafny verify`, 1/0); the twin's own postcondition genuinely fails (0 verified, 1 error) and its ground certificate proves ALONE under `--filter-symbol` (1/0), but `verifiers/dafny.py`'s certificate shape check (`_HONEST_KINDS`, untouched) refuses a file that also declares a `datatype`, so the grader's own cell reads `verified / unproved`, not `refuted` -- a structural gap in the certificate's vocabulary, not a soundness gap |
| verus | Rust `enum` + `#[derive(PartialEq, Eq)]`, `use Dtype::*;` so `match` arms print bare | real verified, twin's certificate accepted -- `verified / refuted` |
| lean | `inductive ... deriving DecidableEq`, `match ... with \| .C => ...` (Lean 4's own anonymous-constructor dot notation) | real's `grind`-closed spec theorem prints a clean axiom list; the twin's own spec theorem depends on `sorryAx` while its hand-built certificate depends on no axioms -- `verified / refuted` |
| spark | none yet: an Ada enumeration type is the design, unmeasured against gnatprove's own `case` exhaustiveness and equality obligations here | abstain by name |
| rocq | none yet: `Inductive` is the design, at the same measured-cost posture entry 11's finite-set wave logged for its own prelude machinery | abstain by name |
| fstar | none yet: `type D = \| C1 \| C2 \| ...` is the design, unmeasured against fstar.exe here | abstain by name |
| framac | none: C's `enum` is an unchecked int with no WP support of its own for a `match`-shaped case split; a tagged struct with an ACSL exhaustiveness predicate is the design | abstain by name |

Byte identity: every task/lemma/nested file committed before this landing
carries no `"datatypes"` field and lowers byte for byte as before in all
seven kernels (588 = 42 files x 7 kernels x 2 sides, `sha256` before and
after, against `r12-blockers`). No twin-generator move, grader or
check-filter change beyond the new `SWAP-CTOR` rung and the generic
expression-walk extension every existing rung now shares.

## The features ahead: designs and costs

### 9. Finite sets

Landed 2026-09-27 as Done 11 above (the type and six operations in four
kernels, three abstaining by name; the comprehension and the lifter's mapping
remain). The plan as it stood:

Candidates: Dafny `set<int>` with comprehension and `|s|`; SPARK
`Ada.Containers.Functional_Sets`; Why3 `fset`; Lean `Finset`; Rocq
`MSets`/lists modulo permutation; F* `FStar.FiniteSet`; Frama-C/ACSL has
logic sets only in specifications. Chosen when it opens: Dafny's
set-of-int with the bounded comprehension `set i | lo <= i < hi && P(i)`, the
common corpus shape, which every kernel can express as a bounded filter. Cost:
a new value type in all seven lowerings, the interpreter, twin ladder moves.

### 10. Datatypes

Candidates: Dafny `datatype`, Rust `enum`, OCaml/Haskell variants, Lean
`inductive`, SPARK discriminated records, C tagged unions. Chosen when it opens:
non-recursive, then recursive, algebraic datatypes with `match`, Dafny's
syntax. Cost: a declaration form in all seven kernels (Frama-C and SPARK
through records with discriminants), twin moves over constructors.
Measured reach (Done 17, 2026-09-27): a non-recursive datatype without
reals or type parameters unlocks 11 methods and at most 8 files of the
staged corpora; 17 of the datatype methods carry a real field and 4 a type
parameter, so those two gaps come first.

### 11. Higher-order functions

Candidates: Dafny arrow types and lambdas, Python lambdas, Haskell. Most corpus
uses are `seq(n, i => f(i))` comprehensions and `forall` over a function
parameter. Chosen when it opens: the comprehension first (as a bounded seq
constructor, an expression form every kernel has), general function values
last: Frama-C and SPARK cannot pass closures without a defunctionalization the
model would have to learn as noise.

## Decision: SPARK's `Hide_Info` annotation (2026-09-26)

The operator approved keeping `pragma Annotate (GNATprove, Hide_Info, "Expression_Function_Body")`
in the SPARK lowering of methods. The earlier rule against `Annotate` covers justifications, which
suppress a failed check and can make a proof pass. `Hide_Info` only removes facts from the prover's
context (a callee's body), so it can make a proof fail but never pass; it is what makes SPARK reason
about a call through the callee's contract alone, as the other six kernels do. Twin files unhide the
body for the refutation check only. Any other use of `Annotate` stays banned.
