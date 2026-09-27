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

## The order from here

Ranked by documents unlocked per unit of effort, where documents unlocked is
the sole-blocker count (a floor: files the parser refuses are not in it) and
effort is the lowering work across seven kernels plus the lifter.

| # | feature | unlocks (sole) | effort | why here |
|---|---|---:|---|---|
| 2 | **Lemmas: declared, proved, called** | the 55 checked lemma-dropped tasks, of which only 6 are clean in six or seven today | a zero-return method whose body the kernels prove; the call rule is already built | Dropping lemma calls (decision 8) keeps the program but loses the proof: Dafny itself re-proves only 32 of the 55 without them. The method feature already has the call rule; a lemma is a ghost method with no return. |
| 3 | seq `decreases` on spec_funs (lifter only) | 32 of 108 in the re-lift, 32 of 373 in the lift, at the check stage | lifter only | no kernel cost |
| 4 | arrays read by functions (`function f(a: array<int>) reads a`) | 43 | lifter only: decision 1 already lifts a read-only array parameter to a seq value; extend it to functions that read one | no kernel cost |
| 5 | quantifier bounds through predicates and one-sided ranges | part of 57 | lifter first (infer the range from a predicate's body or a one-sided guard); truly unbounded quantifiers stay refused | the interpreter cannot evaluate an unbounded quantifier, so no twin witness; bounds are what makes a twin measurable |
| 6 | multi-return calls (`a, b := M(x)`) | 4 | pairs exist; destructuring is surface plus lifter | small |
| 7 | finite sets | 32 | all seven kernels, a new type | large |
| 8 | datatypes | 11 + 56 files | all seven kernels, a new declaration form | large |
| 9 | higher-order functions | 1 + 91 files | all seven kernels | largest |

## The features ahead: designs and costs

### 2. Lemmas

Candidates: Dafny `lemma` (a ghost method: requires/ensures, a proof body, a call
adds the ensures as a fact); Why3 `lemma`/`let lemma`; Lean/Rocq `theorem`
applied by name; F* `Lemma` effect; Verus `proof fn`; SPARK ghost procedures
(`Ghost` aspect) with a `Post`; ACSL `lemma` (global, not called) or a ghost
function with a contract. Chosen shape: Dafny's, as a t `lemma` declaration with
params, requires, ensures and no return, called as a statement; the kernel
proves the lemma with its own automation (the Dafny proof body is a hint, not
lowered), and a caller gets its ensures at the arguments. It fits because it
is the method call rule with the return removed. Costs: Dafny, Verus, F*,
SPARK native (a call statement of a ghost/proof subprogram); Frama-C a ghost
function with a contract; Lean and Rocq a theorem per lemma and an `have` at
the call, the same machinery methods use. The hard part is not the call but the
lemma's own proof in Lean and Rocq, which have no SMT; where their automation
cannot prove the statement, those two read unproved, graded, and the other five
still count.

### 3. Sequence decreases on spec_funs (lifter)

Dafny's default and explicit `decreases s` for a function over a sequence is
compared in Dafny's built-in well-founded order; t requires an int. The lifter
rewrites it to `|s|` where every recursive call's argument is a strictly
shorter sequence (a slice `s[1..]`, `s[..|s|-1]`), which the check stage's
equivalence lemmas then verify rather than trust.

### 4. Arrays read by functions (lifter)

Decision 1 lifts a read-only `array<int>` method parameter to a `seq` value.
Many corpora functions take the same array (`function sum(a: array<int>, i:
int): int reads a`). Candidates: keep arrays as a heap type (Dafny, SPARK,
Frama-C natively; Lean/Rocq/F* would need a heap model, far too costly), or
Dafny's own `a[..]` view: a function reading an array is a function of its
sequence view. Chosen: the view, which is what decision 1 already does for
methods; no t construct changes.

### 5. Quantifier bounds

t's quantifiers are bounded so the interpreter can evaluate them and a twin can
carry a witness. Candidates: Dafny/Why3/SPARK unbounded quantifiers (fine for
SMT kernels, not evaluable); Isabelle/Lean bounded `∀ x ∈ Finset.range n`;
Python's `all(... for i in range(n))`. Chosen: keep t bounded, and make the
lifter find the bound where Dafny left it implicit (inside a called predicate,
or a one-sided guard paired with a type bound such as `nat`). A quantifier with
no finite range stays refused by name.

### 6. Multi-return calls

Dafny `a, b := M(x)`, Rust/Python tuple destructuring `let (a, b) = m(x)`.
t has pairs, so a two-return callee lifts to a pair return and the call to
`var p: (T1, T2) := m(x); a := p.0; b := p.1`, a lifter rewrite with no kernel
cost, or a surface destructuring sugar printed back as that expansion.

### 7. Finite sets

Candidates: Dafny `set<int>` with comprehension and `|s|`; SPARK
`Ada.Containers.Functional_Sets`; Why3 `fset`; Lean `Finset`; Rocq
`MSets`/lists modulo permutation; F* `FStar.FiniteSet`; Frama-C/ACSL has
logic sets only in specifications. Chosen when it opens: Dafny's
set-of-int with the bounded comprehension `set i | lo <= i < hi && P(i)`, the
common corpus shape, which every kernel can express as a bounded filter. Cost:
a new value type in all seven lowerings, the interpreter, twin ladder moves.

### 8. Datatypes

Candidates: Dafny `datatype`, Rust `enum`, OCaml/Haskell variants, Lean
`inductive`, SPARK discriminated records, C tagged unions. Chosen when it opens:
non-recursive, then recursive, algebraic datatypes with `match`, Dafny's
syntax. Cost: a declaration form in all seven kernels (Frama-C and SPARK
through records with discriminants), twin moves over constructors.

### 9. Higher-order functions

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
