# t: the complete syntax

Everything a t task can say, in one place. [`SPEC.md`](SPEC.md) is normative:
it carries the semantics, the definedness rules, and the twin selection. This
page is the grammar with examples, for writing a task by hand.

A t program **is** its JSON abstract syntax tree. There is no parser and no
concrete surface syntax yet. That is a deliberate absence, not an oversight:
a surface syntax would need its own verified parse-print round-trip before its
proofs meant anything. The `written:` lines below are **documentation
notation only**; nothing parses them.

## The whole grammar

```ebnf
Task     ::= { "t": 0|1, "name": Id,
               "params":  [ {"name": Id, "type": Type}* ],
               "returns": [ {"name": Id, "type": "int"|"bool"} ],   (* exactly one *)
               "requires": [ Expr* ],           (* conjoined; [] = true *)
               "ensures":  [ Expr+ ],           (* conjoined; non-empty *)
               "gate"?: "quantifiers"|"loops"|"recursion",
               "spec_funs"?: [ SpecFun* ],      (* v1 *)
               "decreases"?: Expr,              (* v1; required iff body self-calls *)
               "body": [ Stmt+ ] }              (* every path ends in assign *)

Type     ::= "int" | "bool" | "seq"             (* seq: v1, params only *)

Expr     ::= {"int": integer}                   (* mathematical integer *)
           | {"bool": true|false}                                        (* v1 *)
           | {"var": Id}
           | {"op": Op, "args": [Expr+]}
           | {"ite":    {"cond": Expr, "then": Expr, "else": Expr}}      (* v1 *)
           | {"forall": {"var": Id, "lo": Expr, "hi": Expr, "body": Expr}}  (* v1 *)
           | {"exists": {"var": Id, "lo": Expr, "hi": Expr, "body": Expr}}  (* v1 *)
           | {"call":   {"fun": Id, "args": [Expr*]}}                    (* v1 *)

Op       ::= "+" | "-" | "*" | "neg"            (* neg unary; NO div, NO mod *)
           | "==" | "!=" | "<" | "<=" | ">" | ">="
           | "and" | "or" | "not" | "implies"   (* and/or n-ary, short-circuit *)
           | "len" | "at"                       (* v1, seq only *)

Stmt     ::= {"assign": [Id, Expr]}
           | {"if":    {"cond": Expr, "then": [Stmt*], "else": [Stmt*]}}
           | {"var":   {"name": Id, "type": "int"|"bool", "init": Expr}}    (* v1 *)
           | {"while": {"cond": Expr,
                        "invariants": [Expr*],
                        "decreases": Expr,      (* required on every loop *)
                        "body": [Stmt+]}}                                   (* v1 *)

SpecFun  ::= {"name": Id,
              "params": [ {"name": Id, "type": "int"|"seq"}* ],
              "result": "int"|"bool",
              "decreases": Expr,                (* int-valued, over the params *)
              "body": Expr}                     (* may call itself and EARLIER spec_funs *)

Id       ::= [A-Za-z][A-Za-z0-9_]*
```

`"t": 0` restricts this to: int type only, the v0 `Expr`/`Stmt` rows (no
bool/ite/forall/exists/call, no var/while), no `gate`/`spec_funs`/`decreases`.
Every v0 task is valid v1, byte for byte.

## Each construct, by example

### Literals, variables, operators (v0)

```json
{"op": "implies", "args": [{"op": "<", "args": [{"var": "x"}, {"int": 0}]},
                           {"op": "==", "args": [{"var": "r"}, {"op": "neg", "args": [{"var": "x"}]}]}]}
```
written: `x < 0 ==> r == -x`

Integers are **mathematical**: unbounded, no overflow, in every backend or
that backend abstains. Division and modulo do not exist in t; the WS-7
kernels disagree on their semantics (Euclidean vs truncating), and t refuses
to paper over a semantic difference with a syntax.

### Assignment and if (v0)

```json
{"if": {"cond": {"op": ">=", "args": [{"var": "x"}, {"int": 0}]},
        "then": [{"assign": ["r", {"var": "x"}]}],
        "else": [{"assign": ["r", {"op": "neg", "args": [{"var": "x"}]}]}]}}
```
written: `if x >= 0 { r := x } else { r := -x }`

### Sequences and quantifiers (gate 1)

```json
{"op": "len", "args": [{"var": "s"}]}
{"op": "at",  "args": [{"var": "s"}, {"var": "i"}]}
{"forall": {"var": "i", "lo": {"int": 0}, "hi": {"op": "len", "args": [{"var": "s"}]},
            "body": {"op": ">=", "args": [{"var": "r"},
                     {"op": "at", "args": [{"var": "s"}, {"var": "i"}]}]}}}
```
written: `len(s)` · `s[i]` · `forall i in [0, len(s)) . r >= s[i]`

Ranges are half-open `[lo, hi)`; an empty range makes `forall` true and
`exists` false. `s[i]` is **defined only for `0 <= i < len(s)`**, and the
definedness rules in SPEC.md say whose job it is to guard it. A lowering
that silently totalizes `at` is wrong. Quantifiers are bounded by design.
`seq` is a value: no aliasing, no mutation, no heap.

### Locals and loops (gate 2)

```json
{"var": {"name": "i", "type": "int", "init": {"int": 1}}}
{"while": {"cond": {"op": "<", "args": [{"var": "i"}, {"op": "len", "args": [{"var": "s"}]}]},
           "invariants": [ ...Expr... ],
           "decreases": {"op": "-", "args": [{"op": "len", "args": [{"var": "s"}]}, {"var": "i"}]},
           "body": [ ...Stmt... ]}}
```
written: `var i: int := 1; while i < len(s) invariant … decreases len(s) - i { … }`

`decreases` is **required on every loop**: a t task never states a loop it
cannot bound. It must be `>= 0` while the guard holds and strictly decrease
each iteration. Invariants are conjoined, hold on entry, are preserved, and
survive the loop together with the negated guard. The kernel discharges all
of it; t checks nothing itself.

A loop havocs **exactly the variables its body assigns**, intersected with the
names in scope at the loop. Every other variable is preserved across it, and
no invariant is needed to say so. That sentence is normative in SPEC.md rather
than a detail of one lowering: havocking every mutable name proves a different
theorem, and a task whose `ensures` rests on a variable the loop never assigns
is provable under one reading and not the other.

### Spec functions and recursion (gate 3)

```json
{"call": {"fun": "gcds", "args": [{"var": "a"}, {"var": "b"}]}}
```
written: `gcds(a, b)`

A `spec_fun` is a pure total function defined by well-founded recursion
(`ite`-expression body, its own `decreases`), usable anywhere an Expr is. A
task body may call **itself** (direct recursion only) if the task carries a
top-level `decreases`; the contract at the call site is the task's own
`requires`/`ensures`, which is modular reasoning with no unrolling. The spec
of a recursive task is anchored by a spec_fun (`ensures r == fact(n)`), never
by the task's own name, because a self-referential ensures would be mutated
along with the body and the flip would measure nothing.

## Scope

`requires` sees params. `ensures` sees params + returns. A body expression
sees params, returns, and locals declared above it. Invariants see all of
those. A quantifier's bound variable is fresh, scoped to its body, and may
not shadow anything.

## The twins (what makes a task count)

One deterministic rule, no configuration. A ladder of mutation operators is
tried in a fixed order, with sites inside an operator enumerated in pre-order
(statement, then into `if` branches and `while` bodies), and the first
candidate that carries a witness wins.

| rung | operator | what it breaks |
|---|---|---|
| 1 | **INVARIANT-DROP** (v1) | one invariant of one loop is deleted |
| 2 | **COLLAPSE-IF** (v0) | one `if` is replaced by its then-branch |
| 3 | **NEGATE-COND** | one `if`'s branches are swapped |
| 4 | **COMPARE-FLIP** | `<` becomes `<=`, `>` becomes `>=`, and back |
| 5 | **BOUNDARY-SWAP** | the operands of one order comparison are exchanged |
| 6 | **OFF-BY-ONE** | plus or minus 1 on one literal, `at` index, or loop bound |
| 7 | **WRONG-VAR** | one variable occurrence becomes another of the same type in scope |
| 8 | **DROP-GUARD** | one conjunct of an `if` or `while` condition is dropped |

**Every twin must carry a witness**, and that is what the ladder exists for. A
mutation is accepted only when `t/interp.py` produces one of:

- a **value witness**, an input satisfying `requires` on which the real body
  and the twin return different values, or on which the twin is undefined
  where the real body has a value; or
- a **proof witness**, a loop state satisfying `requires` and the surviving
  invariants that either falsifies `ensures` with the guard false, or breaks
  a surviving invariant in one iteration. INVARIANT-DROP's twin computes the
  same value by construction, so this is the only thing there is to measure
  about it.

No witness on any rung and the task is REFUSED, with the reason named:
`no-witness` (every mutation computes what the real body computes),
`no-input` (nothing in the bounded domain satisfies `requires`, a vacuous
precondition), `real-undefined` (the real body returns no value), or
`no-operator` (nothing to mutate). An unmeasurable twin is reported as such,
never passed off as a flip.

A task counts only when the real lowering is VERIFIED **and** the twin is
REFUTED by the actual kernel, both measured, never predicted. A twin that
verifies now says one specific thing, because the twin is known to be broken:
the spec is vacuous, or the dropped invariant's obligation is one the kernel
re-derives. The twin never touches `requires`, `ensures`, `spec_funs`, or the
`decreases` clauses that survive in the mutated body. The spec is the fixed
instrument; the body is what gets broken.

## What does not exist (on purpose)

No surface syntax, no parser. No div/mod. No unbounded quantifiers. No
mutation of sequences, no arrays, no heap, no aliasing. No mutual recursion,
no higher-order functions, no seq returns, no seq literals. One return value.
Gates open with measurements, not intentions; see `AGREEMENT.md` for what
each kernel has actually verified.
