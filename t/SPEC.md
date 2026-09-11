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
binary. Division and modulo are absent from v0; v1 has them as `div` and
`mod` (below), with one semantics stated for every column, since 2026-09-08.
Until then they were absent from v1 too, because the seven kernels split
three ways on negative operands (Euclidean, truncating, floor) and t refuses
to paper over a semantic difference with a syntax; the gate opened by
stating the semantics and measuring each column against it.

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
A parameter type from the start; since 2026-09-09 also a return and local
type ("Sequences as values" below). New type: `"bool"`, usable as a
return or local type.

### Division and modulo (v1)

`{"op": "div", "args": [x, y]}` and `{"op": "mod", "args": [x, y]}`, both
int × int → int, written `x / y` and `x % y` in the notation. The semantics
is Euclidean: for `y != 0`, `q = div(x, y)` and `r = mod(x, y)` are the
unique integers with `x == q * y + r` and `0 <= r < |y|`. So `-7 / 2 == -4`,
`-7 % 2 == 1`, `7 / -2 == -3`, `7 % -2 == 1`, `-7 / -2 == 4`, `-7 % -2 == 1`.
At `y == 0` both are undefined, a definedness obligation under the rules
below, exactly as `at` is undefined outside `[0, len)`.

Why Euclidean: it is the convention of SMT-LIB's `div`/`mod`, Dafny, Boogie,
Verus and Lean 4's `Int` division, F*'s `/` and `%` (all measured on the
pinned kernels, 2026-09-08), and therefore of every DafnyBench program, so
the lifter maps Dafny's `/` and `%` one to one with no domain restriction.
Where a kernel's native operator is not Euclidean (rocq 9.2's `Z.div` and
`Z.modulo` are floor; SPARK, C and ACSL truncate), its lowering defines
`div` and `mod` in the kernel's own terms (`mod(x, y) = x mod |y|` in the
kernel's floor or sign-of-divisor modulo with a positive divisor, then
`div(x, y) = (x - mod(x, y)) / y`, an exact division) and proves nothing
about the operator by name: the committed task `remainder` states the
Euclidean law as its `ensures` and a column that verifies it has shown its
lowering implements this semantics; the twin table shows the twin refuted.
No lowering may emit a kernel's native `/` or `%` where that kernel's
convention differs from this one.

### Definedness

v1 admits partial operators (`at`, `div` and `mod`, above), so definedness
is part of the semantics and is stated once: `and`, `or` evaluate left to right and the
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
probe (unwitnessed: the run's artifact was not kept, no committed probe
task, results table, or docstring states the count below independent of
this prose): six of the seven lowerings surface it and none of the six
verifies the probe. dafny (native well-formedness checking of contracts), verus
(one wf lemma per requires clause, each assuming the earlier clauses),
lean (one wf theorem per clause), rocq (one definedness lemma per clause),
spark (the `at` wrapper's own precondition, checked by the kernel inside
the contract) and fstar (the index refinement on `Seq.index`) all reject
the real lowering: dafny and fstar score the probe REFUTED through their
well-formedness and typing channels (unwitnessed per-column verdict),
verus, spark, lean and rocq score it
UNPROVED (unwitnessed per-column verdict). framac is the known gap and verified the probe: WP's
logic is total, an out-of-range `s[i]` denotes an unconstrained value, and
an undefined requires quietly becomes a constraint on that value.
lower_framac.py discharges definedness for executable positions and for
`ensures` clauses (the ensures side landed 2026-09-01, commit cb70ac47); its `requires`
side, and the same total-logic softness in invariant and spec_fun-body
positions, is recorded future work in that file's own docstring, not
silently claimed here.

**Invariants are checked in order (stated 2026-09-09, measured on the
sequences-as-values fuzz family).** A loop's invariants are a list, and
every kernel discharges the definedness of an invariant with only the
earlier invariants of the same list in context, exactly as `and` reads
left to right. So an invariant that reads `r[k]` for `k < i` must come
after the invariants that bound `len(r)` and `i`; written the other way
round, six columns read the task unproved on the invariant's own
definedness (Dafny: "index out of range" on the invariant itself) while
the interpreter, which only ever sees reachable states, saw nothing wrong.
The committed `reverse` task is written in the checkable order: length,
range, then the value invariant.

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
{"var": {"name": ID, "type": "int"|"bool"|"seq", "init": Expr}}    // local, initialized
{"return": [ID, Expr]}                                       // early exit: ID is the return name
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
probes UNPROVED, spark scored both TIMEOUT, and fstar scored both REFUTED
(unwitnessed as this specific verdict word: lower_fstar.py's own dated
note records fr_probe_ret/fr_probe_local as having "failed" the old
lowering, not the REFUTED classification by name),
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

### Early exit (v1)

`{"return": [ID, Expr]}`, written `return Expr;`. `ID` must be the task's
return name (the AST carries it, as `assign` does, so an interpreter runs
the statement without context). It evaluates `Expr`, assigns it to the
return variable, and ends the task: no statement of its own block may
follow it (well-formedness refuses an unreachable statement), and no later
statement of any enclosing block runs. A path may end in `return` instead
of an assignment. Inside a loop, a `return` leaves the loop without owing
the loop's invariant at that point; the task owes its `ensures` there as
at every exit. Definedness rules are unchanged: `Expr` is in the same
position as an assignment's right-hand side.

Stated 2026-09-08 (ROADMAP 12.7) from the measurement that early exit is
the top gap of MBPP's Python reference solutions (62 of 974) and appears
in 138 of the 785 DafnyBench programs. Lowering status (current, all seven
`lower_*.py`; ROADMAP 12.7 landed 2026-09-09): every column lowers it.
dafny, verus, spark and framac have a return statement; lean, rocq and
fstar encode a loop as a recursive function and return an outcome (exited
with a value, or the loop state) whose invariant shape differs on the two
paths. The committed corpus carries two tasks with `return`: `is_prime`
and `first_even` (t/tasks/is_prime.json, t/tasks/first_even.json).

### Sequences as values (v1)

Stated 2026-09-09 (ROADMAP 12.7, "arrays with mutation"). Measured first
on the 785 DafnyBench programs (unwitnessed: this breakdown's run
artifact was not kept; a rerun of coverage_census.py over the same
corpus finds an array-as-seq tag of 249 under the census's current
naming, not directly comparable to the 315/157/130/72/85 split below,
which no committed table restates): 315 use an array, 157 assign an
element, 130 only read one (the lifter already carries a read-only array
as a `seq`), 72 mutate a parameter in place under `modifies`, 85 allocate an
array and fill it. Every one of those shapes is a value computation once
the array is a sequence: an in-place update is a functional update, an
allocation is a filled sequence, and a method whose effect is its array is
a task whose return is a `seq`. So t takes arrays this way, with no heap,
no aliasing and no element-level frame: a `seq` local or return is a
variable like any other, the loop frame rule havocs it by name, and what
its elements preserve across an iteration is the invariant author's
statement, as it is in Dafny with `seq` and in every functional kernel.

New Expr forms:

```
{"op": "update", "args": [SeqExpr, IdxExpr, Expr]}   // s[i := v]; DEFINED IFF 0 <= i < len(s)
{"op": "fill",   "args": [IntExpr, Expr]}            // seq(n, v): n copies of v; DEFINED IFF n >= 0
```

`update` denotes the sequence equal to `s` at every index but `i`, where it
holds `v`; its length is `len(s)`. `fill` denotes the sequence of length
`n` whose every element is `v`. `==` and `!=` now also apply to two seqs,
extensionally: equal lengths and equal elements at every index. Types:
`seq` may be declared as a return (`returns (r: seq)`) and as a local
(`var a: seq := s;`), and assigned and returned like an int. `at`, `len`,
the bounded quantifiers and the definedness rules are unchanged. What is
still not in v1: nested seqs, seqs of bools (literals, concatenation and
slices are the next section).

The lifter's mapping (LIFTER-DECISIONS.md row 22): `a[i] := e` becomes
`a := a[i := e]`; `new int[n]` becomes `seq(n, 0)`; a method that
`modifies a` and speaks of `old(a[..])` and `a[..]` in its ensures becomes
a task with `a` as a `seq` parameter and a fresh `seq` return, `old(a[k])`
reading as `a[k]` and post-state `a[k]` as the return's element; `fresh(b)`
on a returned array is dropped. Each lowering's dated note records the
kernel's own sequence type, its update and construction forms, and what
extensional equality costs it.

### Sequences: literals, concatenation, slices (v1)

Stated 2026-09-09 (ROADMAP 12.7, the wave after "Sequences as values").
Measured first, twice. On the 785 DafnyBench programs, 50 of the 643
gradable are blocked by sequence operations alone (unwitnessed: the
breakdown's run artifact was not kept; no committed COVERAGE-dafnybench.md
row or census rerun states this per-shape split): 28 build a sequence by
appending a singleton (`r := r + [x]`), 27 start from `[]`, 30 slice, 10
prepend a singleton, 6 concatenate two slices. On the 24,748 nl/ problems
(`COVERAGE-nl.md`), a sequence literal is needed by 8,599, concatenation
by 6,030, a slice by 3,305, and a string, the top gap at 18,361, is a
sequence of characters that needs exactly these three operations before
the character type means anything (at the census split, current,
`COVERAGE-nl.md`: seq-slice 2,474; the string figure split into
string-lib, the gap, at 13,266, and string-as-seq, the burden, at
13,339). So t takes the three on sequences of ints now, values
throughout, and the character type is the wave after.

New Expr forms:

```
{"op": "seq",    "args": [Expr, ...]}                 // [e1, ..., en]; n >= 0; [] is the empty seq
{"op": "+",      "args": [SeqExpr, SeqExpr]}          // s + t: + on two seqs is concatenation; always defined
{"op": "slice",  "args": [SeqExpr, IntExpr, IntExpr]} // s[a..b]; DEFINED IFF 0 <= a <= b <= len(s)
```

`seq` denotes the sequence of length n whose k-th element is the k-th
argument, every argument an int; with no arguments it is the empty
sequence, and `len([]) == 0`. `+` on two seqs denotes the sequence of length
`len(s) + len(t)` whose element at `i` is `s[i]` for `i < len(s)` and
`t[i - len(s)]` otherwise: one operator name, polymorphic by the types of
its operands exactly as `==` already is (two ints, two bools, two seqs). `slice` denotes the sequence of length `b - a`
whose element at `k` is `s[a + k]`; it is undefined unless
`0 <= a <= b <= len(s)`, a definedness obligation under the rules above,
exactly as `at` outside `[0, len)`. The notation also writes `s[a..]` for
`s[a..len(s)]` and `s[..b]` for `s[0..b]`; both are sugar the parser
expands, the AST carries only the three-argument form. A `+` whose operands are one int and one seq is
ill-typed, as a `==` across types is. Every argument of a literal is evaluated, so a literal is
defined iff all its elements are; a concatenation is defined iff both arguments
are. Nothing else changes: `at`, `len`, `update`, `fill`, extensional `==`
and the bounded quantifiers apply to the new values as to any seq, the loop
frame rule havocs a seq variable by name, and the interpreter's length cap
(`interp.MAX_SEQ`) bounds a literal and a concatenation as it bounds
`fill`. What is still not in v1: nested seqs, seqs of bools, membership as
an operator (`x in s` stays the lifter's bounded `exists`, decision 2),
characters and strings.

Two committed tasks carry the construct: `tail` (loop-free: a slice and a
literal, `ensures len(r) == len(s) - 1` and every element) and
`filter_pos` (a loop that appends to a seq return, `r := r + [s[i]]`, with
`len(r) <= i` and a value invariant, the LLM-shaped append idiom the census
counts). The twin ladder needs no new operator: `off-by-one` reaches a
slice bound and an appended index, `wrong-var` swaps the sequence
concatenated, `collapse-if` drops the filter's test; the fuzz family
`v1seqops` measures which of them refute, per column. Each lowering's
dated note records the kernel's own literal, append and slice forms, what
the slice's definedness obligation costs it, and, for framac, which shapes
its buffer encoding refuses (a concatenation's length is data-dependent
in a loop; an output buffer needs a caller-pinned bound, so a
seq-returning task that appends must state `len(r) <= E` for an `E` over
the parameters, or framac abstains).

The lifter's mapping (LIFTER-DECISIONS.md rows 25 to 27): a Dafny
sequence display `[e1, ..., en]` is the literal, `[]` the empty one; `+`
on two seqs is the same `+`; `s[a..b]`, `s[a..]`, `s[..b]` are the slice and
its two sugars, and `a[..]` on an array parameter (the whole array, already
a seq by decision 1) is the parameter itself.

### Strings as sequences of code points (v1)

Stated 2026-09-09, the same night as the sequence trio, and measured
first: on the 24,748 nl/ problems the top gap is `string-char` at 18,361
(`COVERAGE-nl.md`, the sole blocker for 347 function-shaped problems); on
the 785 DafnyBench programs 94 use a string or a char, 7 as their sole
gap (the census was later split, current, `COVERAGE-nl.md` /
`COVERAGE-dafnybench.md`: nl/ carries the gap as string-lib, 13,266, sole
298, with the seq-of-code-points usage measured apart as the burden
string-as-seq, 13,339; DafnyBench carries string-as-seq as a burden at
94, with the gap split into string-lib, 6, sole 0, and nested-seq-string,
4, sole 2); 14 MBPP-DFY methods are refused for it first. t adds no type and no
operator for them. A character is its Unicode code point, an int in
`[0, 1114111]`; a string is a `seq` of code points. Everything a string
does in Dafny (`seq<char>`) or in a Python test, t already does on a seq:
`len`, indexing, `+`, a slice, extensional `==`, a comparison of two
characters as ints, a bounded quantifier over positions.

What the notation adds is two literal forms, both sugar the parser
expands and the printer never emits:

```
'a'          // a char literal: {"int": 97}, the code point; escapes '\n' '\t' '\'' '\\'
"abc"        // a string literal: {"op": "seq", "args": [{"int": 97}, {"int": 98}, {"int": 99}]}; "" is []
```

The AST carries ints and seqs only, so a lowering never sees a character
and every column's existing sequence lowering covers a string; the round
trip holds on the AST (`parse(print(t)) == t`) and the canonical text
prints code points as ints. What is given up, on purpose: the char/int
type distinction. Dafny refuses `'a' + 1`; t computes 98, and a task that
wants a character to stay one states it. Lexicographic order on strings is
not an operator: a task states it with quantifiers or a spec function, as
it states any order. Not in v1: the library a Python solution leans on
(`split`, `upper`, `strip`, `join`, `format`); those are functions a task
writes, or a later gate, and the census counts them apart from the seq
shapes (`string-as-seq` the burden, `string-lib` the gap).

The lifter's mapping (LIFTER-DECISIONS.md row 28): Dafny `string` is
`seq`, `char` is `int`, a char literal its code point, a string literal the
seq literal, `c as int` and `i as char` the identity, and a comparison of
chars an int comparison; a Dafny char is a UTF-16 code unit unless the
program is compiled with `--unicode-char`, so a literal outside the Basic
Multilingual Plane is refused rather than guessed. MBPP tests whose
arguments or results are Python strings enter the spec experiment's pool
as code-point sequences (`mbpp_dfy.parse_assertion`), which is the pool's
version 2.

### Pairs (v1)

Stated 2026-09-09 (commit 8ee34d5; ROADMAP 12.7, the wave after strings).
The construct landed the following day, 2026-09-10 (core commit 5991e8b,
all seven kernels commit 578a473, 2026-09-10 03:03Z). Measured first,
twice. On the 785 DafnyBench programs, `multi-return` heads the census's
greedy order once the sequence trio landed: 71 gradable programs carry it,
27 are blocked by it alone, and of the 73 multi-return methods among the
parsed files 66 return two values (46 `(int, int)`, 6 `(nat, nat)`, 3 the
`(bool, int)` flag-and-value idiom, 2 `(seq<int>, seq<int>)`), 43 carry a
loop, and 26 of the `(int, int)` methods compute both values in one loop
(unwitnessed: no committed census artifact, log, or commit message states
this int-int-single-loop sub-count independent of this prose),
so the two are one coupled result and not two tasks (the shape
measurement of 2026-09-09 that settled `zero-returns` and `multi-method`
as burdens). On the 24,748 nl/ problems, `tuple` is the third gap after
strings and the string library: 7,906 problems build or unpack a tuple, 53
are blocked by it alone, while a function returning several values is 43
(the census was later split, current, `COVERAGE-nl.md`: the two-element
case landed as the burden `tuple-pair`, 7,747, and the remaining gap
`tuple` -- three or more elements, a nested tuple, or a string component
-- is 3,872, sole 56). So t takes a pair as a value. One construct serves both corpora: the
Dafny method with two returns (the lifter turns two named outs into one
pair return) and the Python tuple (a value passed, returned, compared),
and a pair of two base types is the whole of v1.

New type: `{"pair": [T1, T2]}`, each of `T1`, `T2` one of `"int"`,
`"bool"`, `"seq"`; written `(int, int)`, `(bool, seq)`. A parameter,
return or local type. Not in v1: a pair of pairs, a seq of pairs, a pair
of three.

New Expr forms:

```
{"op": "pair", "args": [Expr, Expr]}   // (a, b); a pair value; defined iff both components are
{"op": "fst",  "args": [PairExpr]}      // p.0; always defined on a pair
{"op": "snd",  "args": [PairExpr]}      // p.1; always defined on a pair
```

`pair` denotes the pair whose first component is its first argument and
whose second is its second; `fst` and `snd` project, `fst((a, b)) == a`
and `snd((a, b)) == b`. `==` and `!=` on two pairs of one type are
componentwise, the polymorphic `==` again (two ints, two bools, two seqs,
two pairs); `< <= > >=` stay int-only, so a pair has no order. A `pair`
whose operands disagree with the declared type, a projection of anything
but a pair, and a `==` across pair types are ill-typed. Nothing else
changes: the loop frame rule havocs a pair variable by name, a bound
variable is still an int, and a component obeys its own type's rules
(`len` and `at` reach a seq component through `fst` or `snd`, with the
same definedness obligations). The notation writes `(e1, e2)` for the
pair (a parenthesised expression with a comma; `(e)` alone is still
grouping) and `p.0`, `p.1` for the projections; the AST carries `pair`,
`fst`, `snd` and nothing else.

Two committed tasks carry the construct: `divmod_pair` (loop-free:
`requires y > 0`, `r := (x div y, x mod y)`, `ensures r.0 * y + r.1 == x`,
`0 <= r.1`, `r.1 < y`; twin `wrong-var`, the components swapped, refuted
at `x = 1, y = 1`, the first point of the domain's shell order that breaks
`r.1 < y`) and `min_max` (a loop over a non-empty seq that keeps
both bounds in one pass and returns `(lo, hi)`, ensures every element
between `r.0` and `r.1` and each attained; the coupled `(int, int)` loop
shape the measurement counts 26 of (unwitnessed, the same unrestated
sub-count as above); twin `collapse-if`, the first guard
collapsed, refuted at `s = [0, 1]`: no invariant drop of this task is
witnessable by bounded execution, measured at fifteen times the state
cap, so the ladder falls through to the next rung). The twin
ladder gains one move: `wrong-var` swaps the two components of a `pair`
and swaps `fst` for `snd` in a projection; `off-by-one` reaches a
component as any int. The fuzz family `v1pairs` measures which twins
refute, per column.

Each lowering uses its kernel's own product and records it in a dated
note: dafny and verus tuples with `.0` and `.1`, lean `Int × Int` with
`.1` and `.2`, rocq `Z * Z` with `fst` and `snd`, fstar `int & int`, spark
a record type declared per pair type inside the task's package, framac a
struct returned by value with `\result.a` and `\result.b` in ACSL, or a
named refusal where the memory model or a seq component costs the
certificate. The lifter's mapping (LIFTER-DECISIONS.md row 29): a method
`returns (a: T1, b: T2)` lifts to one return `r: (T1, T2)`, `a` and `b`
become locals, every exit returns `(a, b)`, and `a`, `b` in `ensures`
become `r.0`, `r.1`; three or more returns stay refused, by name.

### Nested sequences (v1)

Stated 2026-09-10 (ROADMAP 12.7, the wave after pairs). Measured first,
twice, and the second measurement corrected the first: the censuses' tag
`nested-seq` fires on any `seq` whose element is not an int, so of the 17
DafnyBench programs it names as blocked by nesting alone, 12 hold a
sequence of sequences of ints, 2 hold `seq<char>` (a string, in the
fragment since row 28), 2 hold `seq<bool>` (its own gap), and 1 fails to
parse for an unrelated reason; of the 74 programs it tags, 16 nest at all,
12 with int rows, 2 with string rows, none with pair rows, none three
deep. On the 24,748 nl/ problems the tag names 3,948 (821 function-shaped,
3,127 stdin): 1,470 confirmed int or bool rows, 150 string rows, 5 pair
rows, 10 three or more deep, 2,313 unreadable by static reading (grid and
matrix problems whose row type a static pass cannot fix) (unwitnessed:
this sub-count breakdown appears nowhere except this prose). (The tag was
split again the same night into `nested-seq`, `seq-of-bool`,
`nested-seq-string`, `nested-seq-deep` and `nested-seq-other`, commit
b31d583: current, `COVERAGE-dafnybench.md`, the plain int/nat `nested-seq`
burden is 12 programs, 10 sole; current, `COVERAGE-nl.md`, `nested-seq`
narrowed to int/bool rows is 3,606, sole 154.) The shapes that
dominate, none restated in any committed table besides this prose
(unwitnessed): a local matrix built and indexed in a loop (3,008 locals,
12,321 row indexes, 9,416 element indexes), a parameter consumed row by
row under a single-binder `forall` with a `len(s[i])` fact (19 parameter
sites, 26 row-length uses, 10 such foralls on DafnyBench), and a nested
literal (3 and 299). Rows are ragged by default: no DafnyBench program
states a cross-row length equality, and 157 of the 3,948 carry any
rectangular signal (unwitnessed; the 3,948 denominator is itself the
superseded first-pass count, current committed `nested-seq` is 3,606,
`COVERAGE-nl.md`). Beside it, the string library, nl/'s top gap: 13,266
current gap count (`COVERAGE-nl.md`, string-lib), of which 8,784 are said
to call `split` or `join` and nothing else in the library (unwitnessed:
the 8,784 split/join-only subset appears nowhere in COVERAGE-nl.md,
nl_census.py, or any commit message), and both return a sequence of
sequences, so this construct is the library's substrate as the sequence
trio was the string's.

New type: `{"seq": "seq"}`, a finite sequence whose elements are seqs of
ints, written `seq<seq>`; the elementary `"seq"` is unchanged and still
means a seq of ints. A parameter, return or local type. Not in v1: three
levels, a seq of strings as a distinct type (a string row is a seq of
ints already, so a `seq<seq>` holds one; the lifter's row for
`seq<string>` and `seq<seq<char>>` is the wave after), a seq of pairs, a
seq of bools.

No new Expr forms. The existing operators are polymorphic by the static
type of their operands, exactly as `+` and `==` already are: `seq` (the
literal, `[[1, 2], [3]]`, every element a seq expression, `[]` the empty
nested seq where the declared type says so), `len(s)` (the number of
rows), `at(s, i)` written `s[i]` (a row, a seq value, DEFINED IFF
`0 <= i < len(s)`), `s[i][j]` (the notation's chained postfix, `at(at(s,
i), j)`, defined iff both indices are in range), `len(s[i])`, `s + t` on
two nested seqs (concatenation of rows; appending one row is `s + [r]`),
`s[a..b]` (a slice of rows), `update(s, i, r)` (row `i` replaced by the
seq `r`), `fill(n, r)` (`n` copies of the row `r`), and `==`/`!=`
(extensional and recursive: two nested seqs are equal iff same length
and equal rows). A `+`, `update`, `fill` or literal whose element is an
int where a row is expected, or a row where an int is expected, is
ill-typed. Definedness composes: a literal is defined iff every row is,
`s[i][j]` iff `0 <= i < len(s)` and `0 <= j < len(s[i])`. Quantifiers are
unchanged: a bound variable is an int, and a quantifier over the
elements of a row is the nested single-binder form `forall i in [0,
len(s)) :: forall j in [0, len(s[i])) :: ...`, the inner bound depending
on the outer, which the checker and every column already take. The loop
frame rule havocs a nested seq by name; the interpreter's length cap
bounds the outer length and each row.

Two committed tasks carry the construct: `swap_rows` (loop-free: `r :=
update(update(m, i, m[j]), j, m[i])` under `requires 0 <= i < len(m)`
and `0 <= j < len(m)`, ensures `len(r) == len(m)`, `r[i] == m[j]`,
`r[j] == m[i]`, every other row unchanged; twin `off-by-one`, refuted at
`m = [[]], i = 0, j = 0`, the shifted index running off the single row,
the ladder's first rung with a witness) and `row_max_len` (a loop over the rows keeping the
longest length, `requires len(m) > 0`, ensures every row's length at
most `r` and some row's length equal to it, the seq_max shape over row lengths;
twin an invariant drop, refuted by exit entailment at `m = [[], [0]]`,
the dropped upper bound letting the loop exit with `r = 0`). The twin ladder needs no new move:
`off-by-one` reaches an outer or an inner index, `wrong-var` swaps two
seq-typed names, `collapse-if` and the invariant drops as before. The
fuzz family `v1nested` measures which twins refute, per column.

Each lowering uses its kernel's own nested sequence and records it in a
dated note: dafny `seq<seq<int>>`, verus `Seq<Seq<int>>`, lean `List
(List Int)`, fstar `Seq.seq (Seq.seq int)`, rocq its own seq encoding
nested one level (or a named refusal where the fn-and-length form does
not compose), spark the generic sequence package instantiated over the
sequence type, framac a named refusal or a flat buffer with an offsets
array, measured first. The lifter's mapping (LIFTER-DECISIONS.md row 30):
Dafny `seq<seq<int>>` and `seq<seq<nat>>` in a parameter, return or
local are `seq<seq>`; `array2<int>` (a matrix with its own indexing) and
`seq<string>` stay refused, by name. The census's `nested-seq` detector
is split the same day: `seq<seq<int>>` one level deep a burden, `seq<bool>`,
`seq<string>` in a row, and depth three or more gaps under their own
names, so the 17 reads 12.

### The string library (v1)

Stated 2026-09-11 (ROADMAP 12.7, the wave after nested sequences),
measured first: COVERAGE-string-lib.md reads the nl/ census member by
member. Of the 24,748 problems, 13,266 need the Python string library and
3,103 need nothing else t lacks: 298 function-shaped (the census's sole
blockers) and 2,805 stdin-shaped, whose need is almost only `split()` on
the input, the stdin-signature construct's own business. Over the 298 the
greedy order is split, str(), join, count, strip, format, replace,
int(x, base), rstrip, find, lower, f-strings, upper, isdigit, isalpha;
twelve members reach 240 of 298. The corpus is Python and the model
writes what it knows, so the semantics are Python's, exactly, one member
at a time, with the reference interpreter transcribing each method over
tuples of ints (never calling Python's `str` or `chr`, so it stays total on
any int) and parity with Python's own `str` methods measured by
`test_strlib.py` on 2,000 sequences per member; the kernels are measured
against it.

A string is a `seq` of code points and a list of strings a `seq<seq>`
(the two sections above); the library adds no type. It adds polymorphic
operators, each total (Python's are; the library adds no undefined case),
each with the definedness of its arguments only:

- `split(s)` : seq -> seq<seq>, Python's `s.split()`: runs of whitespace
  separate, leading and trailing whitespace is dropped, no row is empty;
  `split("") == []`. Measured 2026-09-11 (`test_strlib.py`'s parity test):
  "whitespace" is the 10 ASCII code points Python's own `str.isspace()`
  holds for, 9-13 and 28-32 (FS/GS/RS/US alongside tab/LF/VT/FF/CR/space),
  not the 6-point guess an earlier draft of this line named; a `chr()`-
  free interpreter still has to enumerate them, since it never calls
  `str.isspace()` itself (interp.py's own note on why).
- `split(s, c)` : seq, int -> seq<seq>, Python's `s.split(chr(c))` on one
  code point: every occurrence separates, empty rows kept, so
  `len(split(s, c)) == count(s, [c]) + 1` and `join(split(s, c), [c]) == s`.
- `join(rows, sep)` : seq<seq>, seq -> seq, Python's `sep.join(rows)`.
- `tostr(n)` : int -> seq, Python's `str(n)`: decimal digits, `-` at 45
  for a negative n.
- `count(s, t)` : seq, seq -> int, Python's `s.count(t)`: non-overlapping
  occurrences left to right; `count(s, []) == len(s) + 1`.
- `find(s, t)` : seq, seq -> int, Python's `s.find(t)`: the least index
  where t occurs, `-1` when none, `find(s, []) == 0`.
- `strip(s)`, `lstrip(s)`, `rstrip(s)` : seq -> seq, whitespace as above
  removed at both ends, the left, the right.
- `replace(s, t, u)` : seq, seq, seq -> seq, Python's `s.replace(t, u)`:
  every non-overlapping occurrence left to right; `t == []` inserts `u`
  before every code point and at the end, as Python does.
- `lower(s)`, `upper(s)` : seq -> seq, the ASCII letters 65 to 90 and 97
  to 122 mapped, every other code point unchanged (the corpus is ASCII;
  the Unicode case tables are not in v1, by name).
- `isdigit(s)`, `isalpha(s)`, `isupper(s)`, `islower(s)` : seq -> bool,
  Python's on the ASCII classes: `isdigit` iff s is non-empty and every
  code point is 48 to 57; `isalpha` iff non-empty and every code point a
  letter; `isupper` iff at least one letter, every letter upper; `islower`
  likewise.
- `startswith(s, t)`, `endswith(s, t)` : seq, seq -> bool.

In the notation every member is written Python's way, `s.split()`,
`s.split(c)`, `sep.join(rows)`, `s.count(t)`, `s.find(t)`, `s.strip()`,
`s.replace(t, u)`, `s.lower()`, `s.isdigit()`, `s.startswith(t)`, and
`tostr(n)` as a function; the JSON op is the member's name with the
receiver first (`{"op": "split", "args": [s, c]}`), `s.split()` and
`s.split(c)` two arities of one op. A member in specification position is
the same function (its value in a quantified body or an ensures), so an
ensures may say `len(s.split(c)) == s.count([c]) + 1`. Twin operators
apply to a member's arguments as to any expression; no member-specific
twin exists in v1.

Not in v1, each by name and by the census: `format` and f-strings (a
desugaring to `tostr` and `+` is the lifter's, not the language's),
`int(x, base)` and string-to-int parsing (with the stdin-signature
construct), `strip(s, chars)` and the two one-sided chars forms,
`split(s, t)` on a multi-code-point separator, `splitlines`, the padding
members (`zfill`, `center`, `ljust`, `rjust`), the case members that need
word boundaries (`title`, `capitalize`, `swapcase`), `partition`, and
`encode`. Each kernel lowers a member to a definition in its prelude, a
recursive function with the lemmas its own proofs need, measured on the
committed tasks, the fuzz family `v1strlib`, and the spec experiment's
pool, which grows by the function-shaped problems whose only gap these
members close; the per-kernel notes record what each kernel proves about
a member and what stays an abstain, by name.

Tasks, twin and witness measured via `harness.twin_cached` (2026-09-11),
correcting the twins predicted when this section was first drafted:
`word_count` (`r := len(t2.split())` over `t2 := s[0..len(s)]`, a
full-length slice standing in for the loop-free body's own copy of `s`;
twin OFF-BY-ONE on the slice's `0` lower bound, witness `s = []`, real
`0`, twin undefined -- `slice bounds [1..0]`), `split_join` (the law
`[c].join(s.split(c)) == s` as an ensures, the body rebuilding `s` by the
law with a decoy `s.strip()` local also in scope; twin WRONG-VAR, `s`
becomes `trimmed` inside the rebuild, witness `s = [32]` (one space),
`c = 0`, real `[32]`, twin `[]`), and `count_vowels` (a loop over code
points, invariant `r == s[0..i].count([97]) + ... + s[0..i].count([117])`
against the five lowercase vowels; twin INVARIANT-DROP on that
invariant, witness `s = []`, exit state `i = 0, r = 1` violating the
now-unconstrained `ensures`).

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
shows was vacuous: no twin that was already distinct moved (unwitnessed:
no committed table, log, or commit message restates this 96-count
independent of this prose).

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

No unbounded quantifiers. No heap, no aliasing: `seq` is a value, and an
array with mutation is a `seq` updated functionally ("Sequences as
values"). No overflow semantics (mathematical integers; bounded backends
owe explicit range obligations). One return value. No mutual recursion,
no higher-order functions. A string is a seq of code points (stated
2026-09-09, sequence literals/concatenation/slices the same night); its
library (`split`, `join`, `tostr`, `count`, `find`, `strip`/`lstrip`/
`rstrip`, `replace`, `lower`/`upper`, `isdigit`/`isalpha`/`isupper`/
`islower`, `startswith`/`endswith`) landed 2026-09-11 -- not in it, each
by name: `format` and f-strings, `int(x, base)`, a multi-code-point
separator, `splitlines`, the padding members, `title`/`capitalize`/
`swapcase`, `partition`, `encode`. A pair is one value ("Pairs",
stated 2026-09-10): no pair of pairs, no seq of pairs, no triple. A nested seq is one
level deep ("Nested sequences", stated 2026-09-10): no third level, no seq
of bools, no seq of pairs.
These are gates to open with measurements, not omissions to apologize
for.
