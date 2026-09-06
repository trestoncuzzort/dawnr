# t: task format

A task is one JSON object. Every field is required unless marked optional.
Two format versions exist. `"t": 0` is frozen: everything in the v0 section
is unchanged and every v0 task remains valid byte-for-byte. `"t": 1` is a
strict superset that opens three expressiveness gates: quantifiers over
sequences, loops with invariants, recursion with termination measures. A v1
task may use any v0 construct; a v0 task may use nothing from v1.

Integer semantics in both versions: **mathematical integers**, unbounded, no
overflow. Backends whose native integers are bounded must add explicit range
obligations or abstain; t does not paper over a semantic difference with a
syntax.

## v0 (`"t": 0`)

```
{
  "t": 0,                          // format version, integer
  "name": "abs",                   // [A-Za-z][A-Za-z0-9_]*
  "params":  [{"name": "x", "type": "int"}],
  "returns": [{"name": "r", "type": "int"}],   // exactly one in v0 and v1
  "requires": [ Expr, ... ],       // conjoined; empty list = true
  "ensures":  [ Expr, ... ],       // conjoined; must be non-empty
  "body": [ Stmt, ... ]            // straight-line + if; must end every path in assign
}
```

### Expr (v0)

```
{"int": n}                                   // integer literal
{"var": "x"}                                 // parameter or return name
{"op": OP, "args": [Expr, ...]}
```

`OP` ∈ arithmetic `+ - * neg` (neg is unary), comparison `== != < <= > >=`,
logic `and or not implies`. `and`/`or` are n-ary; `not`/`neg` unary; the rest
binary. Division and modulo are deliberately absent from v0 AND v1 (their
semantics differ across the WS-7 backends, Euclidean against truncating, and t
refuses to paper over a semantic difference with a syntax).

### Stmt (v0)

```
{"assign": ["r", Expr]}
{"if": {"cond": Expr, "then": [Stmt, ...], "else": [Stmt, ...]}}
```

## v1 (`"t": 1`): the three gates

New top-level fields, all optional unless a gate below requires them:

```
"gate": "quantifiers" | "loops" | "recursion"   // which gate the task exercises; informational
"spec_funs": [ SpecFun, ... ]                   // pure recursive definitions usable in specs
"decreases": Expr                               // termination measure for a self-recursive body
```

New type: `"seq"`, a finite immutable sequence of mathematical integers.
Usable as a parameter type only (not a return type in v1). New type:
`"bool"`, usable as a return or local type.

### Definedness

v1 admits one partial operator (`at`, below), so definedness is part of the
semantics and is stated once: `and`, `or` evaluate left to right and the
k-th argument need only be defined when no earlier argument decided the
result (`and`: all earlier args true; `or`: all earlier args false).
`implies p q`: q need only be defined when p is true. `ite`: the taken
branch only. `forall`/`exists`: `lo` and `hi` must be defined; the body must
be defined for every value of the bound variable in `[lo, hi)`. `requires`
clauses are checked left to right, each assuming the earlier ones; each
`ensures` clause may assume `requires` and all earlier `ensures`; each loop
invariant may assume earlier invariants in its list. Every lowering must
either discharge these definedness obligations in its kernel (Dafny-style
well-formedness) or abstain; a lowering that silently totalizes `at` is
wrong.

**Undefined `requires` (normative).** The `requires` clauses themselves
owe definedness, and they owe it unconditionally: clause k must be defined
at every type-correct input at which clauses 1 through k-1 are defined and
true, because nothing else is in scope to guard it. A task whose
`requires` is undefined at such an input (`requires at(s, 0) == 0` with
nothing establishing `len(s) > 0`, undefined at the type-correct input
`s = []`) is DEFECTIVE, the task author's error. It does not mean "inputs
where the requires is undefined are excluded"; a lowering that can detect
the defect must surface it, so that the real lowering fails and the task
cannot count, rather than quietly narrowing the domain to wherever the
clause happens to evaluate. What is, measured 2026-09-02 on exactly that
probe: six of the seven lowerings surface it and none of the six verifies
the probe. dafny (native well-formedness checking of contracts), verus
(one wf lemma per requires clause, each assuming the earlier clauses),
lean (one wf theorem per clause), rocq (one definedness lemma per clause),
spark (the `at` wrapper's own precondition, checked by the kernel inside
the contract) and fstar (the index refinement on `Seq.index`) all reject
the real lowering: dafny and fstar score the probe REFUTED through their
well-formedness and typing channels, verus, spark, lean and rocq score it
UNPROVED. framac is the known gap and verified the probe: WP's
logic is total, an out-of-range `s[i]` denotes an unconstrained value, and
an undefined requires quietly becomes a constraint on that value.
lower_framac.py discharges definedness for executable positions and for
`ensures` clauses (the ensures side landed 2026-09-02); its `requires`
side, and the same total-logic softness in invariant and spec_fun-body
positions, is recorded future work in that file's own docstring, not
silently claimed here.

### Gate 1: quantifiers + sequences

Semantics: a `seq` value s has a length `len(s) >= 0` and elements
`s[0] … s[len(s)-1]`, each a mathematical integer. Sequences are values:
no aliasing, no mutation, no heap.

New Expr forms:

```
{"bool": true|false}                             // boolean literal
{"op": "len", "args": [Expr]}                    // length of a seq; int >= 0
{"op": "at",  "args": [SeqExpr, IdxExpr]}        // s[i]; DEFINED IFF 0 <= i < len(s)
{"forall": {"var": ID, "lo": Expr, "hi": Expr, "body": Expr}}
{"exists": {"var": ID, "lo": Expr, "hi": Expr, "body": Expr}}
{"ite": {"cond": Expr, "then": Expr, "else": Expr}}   // conditional expression
```

`forall` means: for every integer i with `lo <= i < hi`, body holds. `exists`
means: for some such i. The range is half-open `[lo, hi)`; `hi <= lo` gives
the empty range (forall = true, exists = false). Quantification is bounded by
design, because every kernel on the WS-7 list can express a bounded integer
quantifier; unbounded quantification is a later gate, not a notational
convenience to smuggle in. The bound variable is a fresh name scoped to
`body` and must not collide with any name already in scope at that point
(params, returns, locals, enclosing bound variables). `==`/`!=` apply to two
ints or two bools; `< <= > >=` are int-only. `at` outside `[0, len)` is
undefined, and the definedness rules above say who must guard it.

Scope rule (v0 had it implicitly): `requires` sees params; `ensures` sees
params and returns; body expressions see params, returns, and locals declared
above them; invariants see all of those.

### Gate 2: loops + invariants

New Stmt forms:

```
{"var": {"name": ID, "type": "int"|"bool", "init": Expr}}    // local, initialized
{"while": {"cond": Expr,
           "invariants": [Expr, ...],       // conjoined; may be empty
           "decreases": Expr,               // required on every loop
           "body": [Stmt, ...]}}
```

`assign` now targets any return or local name in scope. Loop semantics are
the standard partial-correctness-plus-termination package: every invariant
must hold on entry and be preserved by one iteration (assuming the guard);
after the loop, invariants hold and the guard is false. `decreases` is an
int-valued expression that is `>= 0` whenever the guard holds and strictly
decreases across every iteration; it is required, not optional: a t task
never states a loop it cannot bound. The kernel discharges all of it; t
checks nothing itself.

**The frame rule (normative).** A `while` loop havocs exactly the
variables assigned in its body: the syntactic assigned set, computed from
the body AST (an `assign` target anywhere in the body counts, including
under an `if` or inside a nested `while`), intersected with the names in
scope at the loop (a local declared inside the body does not outlive the
body and is excluded). Every other variable in scope is preserved across
the loop, and no invariant is needed to say so; invariants carry
information only about the havocked variables and the values readable from
them. This sentence exists because "the standard package" underdetermines
it: a lowering that havocs every mutable name and one that havocs only the
assigned set prove DIFFERENT theorems, and a task whose `ensures` depends
on a variable the loop never assigns is provable under one and not the
other with neither lowering looking wrong. Measured 2026-09-02 with two
probes on the training box (a return assigned before the loop and never
inside it; a prefix local never assigned in the loop and read after it):
dafny, verus and framac already implemented this rule (native loop
targets, read-only helper parameters, and `loop assigns` from the assigned
set, respectively) and verified both probes, while the fstar, lean, rocq
and spark lowerings threaded every in-scope mutable name through their
loop encodings under a contract stating only invariants plus the negated
guard, which is the havoc-everything theorem: lean and rocq scored both
probes UNPROVED, spark scored both TIMEOUT, and fstar scored both REFUTED,
its solver rejecting the havoc-everything obligation the old lowering had
emitted in place of the task's theorem. All four were fixed the same day
(each loop helper now threads exactly the assigned set, or carries one
frame equality per preserved variable); with the fixes all seven kernels
verify both probes, flake-checked, and the artifacts emitted
for every committed task are byte-identical to before the fix, because
every committed loop assigns every variable in scope. A loop whose body
assigns nothing in scope havocs nothing; such a loop cannot satisfy its
own `decreases` obligation whenever the guard can hold, so no provable t
task contains one, and a lowering may refuse the shape outright (an
ABSTAIN, never a verdict).

### Gate 3: recursion + termination

A SpecFun is a pure total function defined by well-founded recursion,
usable in `requires`, `ensures`, `invariants`, and bodies:

```
{"name": ID,
 "params": [{"name": ID, "type": "int"|"seq"}, ...],
 "result": "int"|"bool",
 "decreases": Expr,          // int-valued over the params
 "body": Expr}               // may call itself and earlier spec_funs
```

New Expr form:

```
{"call": {"fun": ID, "args": [Expr, ...]}}
```

`fun` is a spec_fun name, or, inside the task's own body only, the task's
own name (direct self-recursion; no mutual recursion in v1). Semantics:

- A spec_fun call denotes the unique function satisfying its defining
  equation; well-definedness is exactly the termination obligation: at every
  self-call (and every call to an earlier spec_fun there is nothing to
  check), the callee's `decreases` measure evaluated at the call's arguments
  is `>= 0` and strictly less than the caller's measure at its own
  parameters. The kernel discharges this.
- A self-call of the task denotes a value about which exactly the task's
  contract is known (modular reasoning: callee `requires` must hold at the
  call site; callee `ensures` may be assumed of the result). A body that
  self-calls MUST carry a task-level `"decreases"` measure with the same
  obligation as above. Lowerings may hoist expression-position self-calls
  into call statements; the meaning is call-by-value, evaluated left to
  right, and (in v1) self-calls appear only in contexts where evaluation
  order is unobservable: specs and assignments.

The spec side of a recursive task is anchored by a spec_fun (`ensures r ==
fact(n)`), never by the task's own name: an `ensures` that referenced the
task itself would be redefined by the twin along with the body, and the flip
would measure nothing.

## The twins

A ladder of mutation operators. None is optional or configurable; the choice
is derived from the body by one deterministic rule, applied identically to
every task, so "the twin failed" always means the same thing. The twin never
touches `requires`, `ensures`, `spec_funs`, or the task/loop `decreases`
clauses that survive in the mutated body. The spec is the fixed instrument;
the body and its annotations are what gets broken.

**Every twin must carry a witness.** This is the whole point and it is a
measurement, not an assumption. Measured over the 1395 generated tasks (7 seeds x
200 from `fuzz_lower.py`, less the 5 its own well-formedness check rejects)
that the fuzzer measures, 129 of them, 9.2%, and 13 to 22 per seed, had a
twin that computes an IDENTICAL value to the real program on every input
tested. On those tasks the "measured flip" measures nothing: there is no
behavioural difference for a kernel to detect, so a REFUTED verdict is luck
and a VERIFIED twin cannot be told apart from a vacuous spec. So a mutation is
accepted only when `t/interp.py` produces one of:

- a value witness, an input satisfying `requires` on which the real body and
  the twin return different values, or on which the twin is undefined where
  the real body has a value (the value-changing operators); or
- a proof witness, a loop state satisfying `requires` and the SURVIVING
  invariants that either falsifies `ensures` with the guard false (exit
  entailment) or breaks a surviving invariant in one iteration (preservation).
  INVARIANT-DROP's twin computes the same value by construction, so this is
  the only thing there is to measure about it.

The operators, tried in this fixed order, with sites inside an operator
enumerated in pre-order (statement, then into `if` branches and `while`
bodies), first candidate with a witness winning:

1. **INVARIANT-DROP** (v1): one invariant of one loop is deleted. An
   annotation mutation. Twin REFUTED means that invariant is load-bearing:
   the kernel cannot re-derive it, so the stated proof outline is real work.
2. **COLLAPSE-IF** (v0): one `if` is replaced by its then-branch.
3. **NEGATE-COND**: one `if`'s branches are swapped, which is `not cond`
   with no new syntax for a lowering to reject.
4. **COMPARE-FLIP**: `<` <-> `<=`, `>` <-> `>=` at one comparison.
5. **BOUNDARY-SWAP**: the operands of one order comparison are exchanged.
6. **OFF-BY-ONE**: +/-1 on one integer literal, `at` index, or loop bound.
7. **WRONG-VAR**: one variable occurrence is replaced by another of the same
   type in scope (never the return: reading it before its first assignment is
   ill-formed rather than wrong, and a lowering rejects it instead of
   refuting it).
8. **DROP-GUARD**: one conjunct of an `if`/`while` condition is dropped.

Rungs 1 and 2 at site 0 are exactly the v1 rule, so a task whose v1 twin was
already load-bearing keeps that twin unchanged; measured over the same 1395
tasks, 96 twins changed and every one of them was a twin the interpreter
shows was vacuous: no twin that was already distinct moved.

No witness on any rung and the task is REFUSED, with the reason named:
`no-witness` (every mutation computes what the real body computes),
`no-input` (nothing in the bounded domain satisfies `requires`, a vacuous
precondition), `real-undefined` (the real body returns no value), or
`no-operator` (nothing to mutate). An unmeasurable twin is reported as such,
never passed off as a flip.

A task counts ONLY when the real lowering is VERIFIED and the twin is REFUTED
by the actual kernel, both measured and never predicted. Twin VERIFIED now says
one specific thing, because the twin is known to be broken: the spec is
vacuous, or the dropped invariant's obligation is one the kernel re-derives.

## What v1 does not claim

No unbounded quantifiers. No arrays-with-mutation, no heap, no aliasing:
`seq` is a value. No division or modulo. No overflow semantics (mathematical
integers; bounded backends owe explicit range obligations). One return
value. No mutual recursion, no higher-order functions, no seq-valued
returns or seq literals. These are gates to open with measurements, not
omissions to apologize for.
