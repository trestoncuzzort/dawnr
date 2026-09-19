# t: the complete syntax

Everything a t task can say, in one place. [`SPEC.md`](SPEC.md) is normative:
it carries the semantics, the definedness rules, and the twin selection. This
page is the grammar with examples, for writing a task by hand.

A t program **is** its JSON abstract syntax tree, and since 2026-09-04 that
tree also has a surface syntax: [`surface.py`](surface.py) parses the
`written:` notation below into the AST and prints the AST back out. The
absence was deliberate while it lasted, and it ended on the terms it was
stated on. A surface syntax needs a verified parse-print round trip before
its proofs mean anything, because a parser and a printer that disagree prove
things about a program nobody wrote. Measured by `python3 t/surface.py
--check`:

- `parse(print(t)) == t` on **1783 of 1783** tasks, compared as canonical
  JSON. The corpus is the 35 committed tasks in `tasks/` plus
  `fuzz_lower.build_corpus` over seeds 1 through 7, less the 23 that
  `check_wf` rejects for carrying constructs t does not have, 1806 seen in
  all. 1469 of the 1783 are distinct; the repeats are the hand-built probes,
  which recur once per seed.
- `print(parse(text)) == text` on all 1783, so every task has exactly one
  normal form in the notation.
- The **22 examples on the `written:` lines of this page parse, unedited**,
  to the JSON they sit beside (some lines carry more than one, separated by
  `·`). That is what makes this grammar the documented notation rather than
  a new one that resembles it.
- **100000 of 100000** random ASTs drawn from the grammar itself round trip
  (`--fuzz 20000`, seeds 1 through 5). That instrument samples the grammar
  instead of t's semantics, so it reaches shapes no corpus generator emits,
  and it is what found the only real defect this syntax had: `neg` of an `at`
  whose base is a literal printed as `-18[false]`, which reparses as `at` of
  the literal `-18`. A corpus cannot contain what its generators cannot
  build, so that instrument stays.

The notation is sugar and nothing more. It adds, removes and reinterprets no
construct; there is nothing it can say that the JSON cannot already say, and
nothing the JSON says that it drops. The full surface grammar is in
`surface.py`'s module docstring, beside the two places where the obvious
notation would have lost information: a negative literal `-5` against `neg`
of a literal `-(5)`, and the n-ary arity of `and`/`or`, where `a and b and c`
is the 3-ary node and `(a and b) and c` is not.

## The whole grammar

```ebnf
Task     ::= { "t": 0|1, "name": Id,
               "params":  [ {"name": Id, "type": Type}* ],
               "returns": [ {"name": Id, "type": Type} ],          (* exactly one *)
               "requires": [ Expr* ],           (* conjoined; [] = true *)
               "ensures":  [ Expr+ ],           (* conjoined; non-empty *)
               "gate"?: "quantifiers"|"loops"|"recursion",
               "spec_funs"?: [ SpecFun* ],      (* v1 *)
               "decreases"?: Expr,              (* v1; required iff body self-calls *)
               "body": [ Stmt+ ] }              (* every path ends in assign *)

Type     ::= "int" | "bool" | "seq"             (* seq: v1; a return and local type since 2026-09-09 *)
           | {"pair": [Type, Type]}             (* v1, since 2026-09-10; written (T1, T2); T1, T2 int/bool/seq, no pair of pairs *)
           | {"seq": "seq"}                     (* v1, since 2026-09-10; written seq<seq>; one level only, rows are seqs of int *)

Expr     ::= {"int": integer}                   (* mathematical integer *)
           | {"bool": true|false}                                        (* v1 *)
           | {"var": Id}
           | {"op": Op, "args": [Expr+]}
           | {"ite":    {"cond": Expr, "then": Expr, "else": Expr}}      (* v1 *)
           | {"forall": {"var": Id, "lo": Expr, "hi": Expr, "body": Expr}}  (* v1 *)
           | {"exists": {"var": Id, "lo": Expr, "hi": Expr, "body": Expr}}  (* v1 *)
           | {"call":   {"fun": Id, "args": [Expr*]}}                    (* v1 *)

Op       ::= "+" | "-" | "*" | "neg"            (* neg unary *)
           | "div" | "mod"                     (* v1; written / and %; Euclidean *)
           | "==" | "!=" | "<" | "<=" | ">" | ">="
           | "and" | "or" | "not" | "implies"   (* and/or n-ary, short-circuit *)
           | "len" | "at"                       (* v1, seq only *)
           | "update" | "fill"                  (* v1; written s[i := v] and seq(n, v) *)
           | "seq" | "slice"                    (* v1; written [a, b] (any arity, [] empty) and s[a..b];
                                                   "+" on two seqs is concatenation *)
           | "pair" | "fst" | "snd"             (* v1, since 2026-09-10; written (e1, e2), p.0, p.1 *)
           | "split"                            (* v1, since 2026-09-11; seq -> seq<seq>, arity 1 or 2;
                                                   written s.split() and s.split(c) *)
           | "join" | "tostr" | "count" | "find"
           | "strip" | "lstrip" | "rstrip" | "replace"
           | "lower" | "upper"
           | "isdigit" | "isalpha" | "isupper" | "islower"
           | "startswith" | "endswith"          (* v1, since 2026-09-11: the string library
                                                   (SPEC.md "The string library"); written
                                                   sep.join(rows), tostr(n), s.count(t), s.find(t),
                                                   s.strip()/s.lstrip()/s.rstrip(), s.replace(t, u),
                                                   s.lower(), s.upper(), s.isdigit(), s.isalpha(),
                                                   s.isupper(), s.islower(), s.startswith(t),
                                                   s.endswith(t) *)

Stmt     ::= {"assign": [Id, Expr]}
           | {"if":    {"cond": Expr, "then": [Stmt*], "else": [Stmt*]}}
           | {"var":   {"name": Id, "type": Type, "init": Expr}}            (* v1 *)
           | {"return": [Id, Expr]}                 (* v1; written `return Expr;`; ends the task *)
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
that backend abstains. Division and modulo are `div` and `mod` since 2026-09-08, Euclidean and undefined at a zero divisor (SPEC.md "Division and modulo"); a column whose native operator differs defines them in its own terms.

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
`seq` is a value: no aliasing, no mutation, no heap. Since 2026-09-09
(SPEC.md "Sequences as values") a `seq` is also a return and local type,
`s[i := v]` is the functional update (`{"op": "update", "args": [s, i, v]}`,
defined only for `0 <= i < len(s)`), `seq(n, v)` builds `n` copies of `v`
(`{"op": "fill", "args": [n, v]}`, defined only for `n >= 0`), and `==` on
two seqs is extensional. `tasks/swap.json` and `tasks/reverse.json` are
the committed examples: `r := s[i := s[j]]; r := r[j := tmp];` and
`r := seq(len(s), 0); ... r := r[i := s[len(s) - 1 - i]];`.

Since the same evening (SPEC.md "Sequences: literals, concatenation,
slices"):

```json
{"op": "seq",   "args": [{"int": 3}, {"var": "x"}]}
{"op": "seq",   "args": []}
{"op": "+",     "args": [{"var": "s"}, {"op": "seq", "args": [{"var": "x"}]}]}
{"op": "slice", "args": [{"var": "s"}, {"int": 1}, {"op": "len", "args": [{"var": "s"}]}]}
```
written: `[3, x]` · `[]` · `s + [x]` · `s[1..len(s)]`, also `s[1..]`

A literal takes any number of int elements, `[]` being the empty seq. `+`
on two seqs is concatenation, the same operator name as on ints, chosen by
the types of its operands exactly as `==` is; a `+` across the two types
is ill-formed. `s[a..b]` is the slice with elements `a` to `b - 1`,
**defined only for `0 <= a <= b <= len(s)`**; the notation also accepts
`s[a..]` for `s[a..len(s)]` and `s[..b]` for `s[0..b]`, and prints the
three-argument form back. `tasks/tail.json` (`r := s[1..];`) and
`tasks/filter_pos.json` (`r := r + [s[i]];` inside a loop) are the
committed examples.

Since 2026-09-09 (SPEC.md "Strings as sequences of code points (v1)"), two
more literal forms are sugar the parser expands and the printer never
emits:

```json
{"int": 97}
{"op": "seq", "args": [{"int": 97}, {"int": 98}, {"int": 99}]}
```
written: `'a'` · `"abc"`

A character is its Unicode code point, an int in `[0, 1114111]`; a string
is a `seq` of code points, `""` being the empty seq. Both forms accept the
escapes `\n` `\t` `\r` `\0` `\'` `\\`, a string also `\"`, and either can
spell a code point by its hex value as `\u{H...H}`, 1 to 6 hex digits. The
printer always emits ints and seq literals, never quotes, so `'a'` prints
as `97` and `"abc"` as `[97, 98, 99]`.

### Pairs (v1)

```json
{"op": "pair", "args": [{"var": "a"}, {"var": "b"}]}
{"op": "fst",  "args": [{"var": "p"}]}
{"op": "snd",  "args": [{"var": "p"}]}
{"var": {"name": "r", "type": {"pair": ["int", "int"]},
         "init": {"op": "pair", "args": [{"var": "x"}, {"var": "y"}]}}}
```
written: `(a, b)` · `p.0` · `p.1` · `var r: (int, int) := (x, y);`

Since 2026-09-10 (SPEC.md "Pairs (v1)"), a pair is a value: `{"pair": [T1,
T2]}`, each of `T1`, `T2` one of `int`, `bool`, `seq`, written `(int,
int)` or `(bool, seq)`, usable as a param, return or local type. `(e1,
e2)` builds one; `p.0` and `p.1` project, both always defined on a pair.
`==` and `!=` on two pairs of the same type are componentwise, the same
polymorphic operator as on two ints, two bools or two seqs; a `==` across
two DIFFERENT pair types is ill-formed, as is any of `< <= > >=` on a
pair, since a pair has no order. `(e)` alone, no comma, is still grouping,
never a pair. Not in v1: a pair of pairs, a seq of pairs, a pair of three.
`tasks/divmod_pair.json` (`r := (x div y, x mod y);`, loop-free) and
`tasks/min_max.json` (a loop keeping both bounds in one pass, `r :=
(lo, hi);` after it exits) are the committed examples. The twin ladder's
WRONG-VAR rung gained one move for this construct: it also swaps a
`pair`'s two components, and swaps `fst` for `snd` in a projection.

### Nested sequences (v1)

```json
{"var": {"name": "m", "type": {"seq": "seq"},
         "init": {"op": "seq", "args": [
             {"op": "seq", "args": [{"int": 1}, {"int": 2}]},
             {"op": "seq", "args": [{"int": 3}]}]}}}
{"op": "at", "args": [{"op": "at", "args": [{"var": "s"}, {"var": "i"}]}, {"var": "j"}]}
```
written: `var m: seq<seq> := [[1, 2], [3]];` · `s[i][j]` · `var m: seq<seq> := [];`

Since 2026-09-10 (SPEC.md "Nested sequences (v1)"), a nested seq is a
value: `{"seq": "seq"}`, written `seq<seq>`, a finite seq whose elements
are seqs of ints (the elementary `seq` is unchanged). One level only: not
in v1 are three levels, a seq of pairs, or a seq of bools/strings as a
distinct type (a string row is already a `seq`, so a `seq<seq>` holds one
directly). No new Expr forms: every existing seq operator is polymorphic
by the static type of its operands, exactly as `+` and `==` already are.
`seq` (the literal, every element a seq expression; `[]` is the empty
nested seq where the declared type says so), `len(s)` (the row count),
`at(s, i)` written `s[i]` (a row), and the chained postfix `s[i][j]` (`at`
of `at`, needing no new grammar: `Postfix` already loops over `[...]`),
`s + t` (row concatenation), `s[a..b]` (a slice of rows), `update(s, i,
r)` (row `i` replaced by the seq `r`), `fill(n, r)` (`n` copies of the row
`r`), and `==`/`!=` (extensional and recursive: same length, equal rows)
all carry over. A `+`, `update`, `fill` or literal whose element is an int
where a row is expected, or the reverse, is ill-typed. Rows are ragged by
default: t states no cross-row length equality on its own.
`tasks/swap_rows.json` (loop-free: `r := update(update(m, i, m[j]), j,
m[i])`, swapping two rows) and `tasks/row_max_len.json` (a loop keeping
the longest row length seen) are the committed examples. The twin ladder
needs no new move: OFF-BY-ONE already reaches an outer or an inner index,
WRONG-VAR already swaps two seq-typed names (nested or not, since the
comparison is on the declared type, dict equality included), and
COLLAPSE-IF and an invariant drop apply as before.

### The string library (v1)

```json
{"op": "split", "args": [{"var": "s"}]}
{"op": "split", "args": [{"var": "s"}, {"var": "c"}]}
{"op": "join",  "args": [{"var": "rows"}, {"var": "sep"}]}
{"op": "tostr", "args": [{"var": "n"}]}
{"op": "count", "args": [{"var": "s"}, {"var": "u"}]}
{"op": "replace", "args": [{"var": "s"}, {"var": "u"}, {"var": "v"}]}
{"op": "at", "args": [{"op": "split", "args": [{"var": "s"}]}, {"int": 0}]}
```
written: `s.split()` · `s.split(c)` · `sep.join(rows)` · `tostr(n)` ·
`s.count(u)` · `s.replace(u, v)` · `s.split()[0]`

Since 2026-09-11 (SPEC.md "The string library (v1)"), 17 polymorphic seq
operators over `seq` and `seq<seq>`, each total (no new definedness
obligation beyond its own arguments'), each Python's own str-method
semantics: `split(s)` (whitespace runs; `seq -> seq<seq>`), `split(s, c)`
(one code point, empty rows kept; `seq, int -> seq<seq>`, two arities of
one op), `join(rows, sep)` (`seq<seq>, seq -> seq`), `tostr(n)` (`int ->
seq`, decimal digits and `-`), `count(s, t)`/`find(s, t)` (`seq, seq ->
int`), `strip`/`lstrip`/`rstrip` (`seq -> seq`), `replace(s, t, u)`
(`seq, seq, seq -> seq`), `lower`/`upper` (`seq -> seq`, ASCII only),
`isdigit`/`isalpha`/`isupper`/`islower` (`seq -> bool`, ASCII classes),
`startswith(s, t)`/`endswith(s, t)` (`seq, seq -> bool`). The notation
writes every member Python's way, a postfix `.name(...)` on its first
(receiver) argument except `tostr`, a plain function like `len`, and
`join`, whose AST order is `(rows, sep)` (the receiver is `sep`, second),
so `sep.join(rows)` prints and parses with its two arguments swapped
back; postfix chains with indexing and slicing exactly as `.0`/`.1` do
(`s.split()[0]`, `s.strip().lower()`). `tasks/word_count.json` (`r :=
len(t2.split())` over a full-length slice of `s`, twin OFF-BY-ONE on the
slice's `0` bound), `tasks/split_join.json` (the round-trip law
`[c].join(s.split(c)) == s` as an ensures on a body that rebuilds `s` by
the law, twin WRONG-VAR: `split(s, c)` becomes `split(trimmed, c)`, a
decoy `s.strip()` local) and `tasks/count_vowels.json` (a loop counting
code points against `s.count([97]) + ... + s.count([117])`, the five
lowercase vowels, twin INVARIANT-DROP) are the committed examples. No new
twin move: OFF-BY-ONE, WRONG-VAR, COLLAPSE-IF and an invariant drop reach
these bodies exactly as they reach any seq-typed one.

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

### Typed inline helpers (surface, v1; 2026-09-19)

After the task's clauses and before its body, declarations may mix existing
`spec fun` definitions and the following expression helpers:

```ebnf
InlineFun ::= "inline" "fun" Id "(" Params ")" ":" Type "=" Expr ";"?
```

```
t 1 task adjacent(x: int) returns (r: (int, seq))
  ensures r.0 == x + 1
  ensures r.1 == [x, x + 1]
inline fun inc(a: int): int = a + 1
inline fun singleton(a: int): seq = [a]
inline fun adjacentPair(a: int): (int, seq) =
  (inc(a), singleton(a) + singleton(inc(a)))
{ r := adjacentPair(x); }
```

Parameters and results admit every current type, including `seq`, pairs and
`seq<seq>`. Definitions see only their parameters and earlier inline helpers;
they cannot call themselves, later helpers, spec functions, or the task.
All definitions and call arguments are type-checked, including unused ones.
Task expressions and spec-function definitions can use all declared helpers.
Helper names are unique and distinct from the task and spec-function names.
`inline` is contextual: an existing variable or task named `inline` stays valid.

These are **expression templates with substitution semantics**. For example,
`inline fun keep(a: int): int = 7` makes `keep(1 / 0)` equal to `7`, because
the argument does not occur in the expanded expression. `keep(true)` still
fails typing. `inline fun safe(ok: bool, a: int): int = if ok then a else 0`
makes `safe(x > 0, 1 / x)` defined at zero. A used, unguarded partial expression
retains its definedness obligation. Quantifier binders are renamed freshly so
caller variables cannot be captured; no `requires` is added or weakened.

`surface.parse` returns the expanded, well-formed core AST. The printer emits
that expanded program, not the declarations: `parse(print(parse(source))) ==
parse(source)`. As with string literal sugar, source spelling is not retained.
The constrained grammar admits the structure; binding, typing and acyclicity
are checked during elaboration. Unsupported expanded shapes remain unsupported
by the same backends. See [the normative rules](SPEC.md#typed-inline-helpers-surface-v1)
and [the preregistered probes](PREREG-inline-helpers-2026-09-19.md).

### Core scope

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

## What the notation refuses

The surface syntax is allowed to say exactly what the AST says, so these are
rejected rather than given a meaning. Each is a case where accepting would
have made the notation a second, undocumented language; `surface.py --check`
exercises all six.

| refused | why |
|---|---|
| `div`, `mod` | written `/` and `%` at the `*` precedence, left associative; v1 only |
| a chained comparison, `a == b == c` | there is no AST node for it, and reading it as a conjunction would invent one |
| `and`/`or` at arity 1 | the AST admits it and `a and` is not a sentence; it occurs 0 times in the 1628 tasks, and `print` raises rather than emit text that reads as a different tree |
| a keyword as a name | `len` cannot be both an operator and a spec_fun |
| **comments** | a comment has no AST node, so it cannot survive `print(parse(text)) == text`; admitting one would make the round trip conditional, and the round trip is the only reason the syntax exists |

## Errors with a position

Since 2026-09-11 (ROADMAP 14.2 "Errors with a position", parse side), every
error `surface.py` raises while lexing or parsing text is a `SurfaceError`
carrying the offending token's `file`, `line` and `col`, and the
`production` above being parsed (SYNTAX.md's own EBNF names -- `Task`,
`Type`, `SpecFun`, `Stmt`, `Expr`, `Op`, `Id` -- or, for the two rules this
page names no production for, the heading above the rule: a char/string
literal error is filed under "Strings as sequences of code points (v1)",
and the chained-comparison refusal under "What the notation refuses").
`str(err)` reads `file:line:col: message [production]`; `surface.parse_file
(path)` reports `path` as `file`. Measured by `python3
t/test_surface_errors.py` against the committed corpus of malformed `.t`
files in `t/malformed/` (one per production, named after it) and its
manifest `t/malformed/EXPECTED.tsv`. `surface.parse(text, positions=None)`
also, when given a dict, fills it with `id(node) -> (line, col)` for every
AST dict it builds, for the well-formedness side (`check_wf`, not yet its
own module) to reuse the same positions once it exists.

## What does not exist (on purpose)

No unbounded quantifiers. No
mutation of sequences in place (a seq is a value, updated functionally), no
arrays, no heap, no aliasing. No mutual recursion, no higher-order
functions. A character and a string are sugar over `int` and `seq`, not
their own types; a pair is one value, no pair of pairs, no seq of pairs,
no triple; a nested seq is one level only, no seq of seq of seq, no seq
of pairs, no seq of bools or strings as its own type. One return value.
Gates open with measurements, not intentions; see `AGREEMENT.md` for what
each kernel has actually verified.
