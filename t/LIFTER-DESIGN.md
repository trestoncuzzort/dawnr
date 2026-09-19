# The Dafny-to-t lifter: design

Provenance. The text below the rule is `t/lifter-design/verified-lift.md`,
one of four independent designs written by the design workflow
`wf_75f9712b-7db` on 2026-09-05, unchanged. The workflow's judge, synthesis
and critique phases never ran (five-hour rate cap, overage disabled); Treston
chose this design as the base on 2026-09-05 after a two-section comparison,
and the reconciliation the panel would have done is `t/LIFTER-DECISIONS.md`,
one row per open question with each design's default and the chosen one.
Where this text and the decisions file disagree, the decisions file wins. Two
of this design's own defaults are reversed there: read-only `array<int>`
parameters LIFT to seq (decision 1, section 15 item 1 argues the other way),
and a top-level `&&` in a requires or ensures is SPLIT, never in an invariant
(decision 10, section 15 item 5). Section 18, appended after the design,
grafts what the other three designs had that this one lacks.

Audit status. No critic has read this document. Its audit is measurement:
the 77 census in-fragment programs first, then all 785, then the seven
kernels over the lifted tasks. Every "expected" number in section 13 is a
prediction the corpus run replaces.

Implementer map (flat `t/lift_*.py`, Python 3.12 standard library only, runs
on Windows per RUN-ON-WINDOWS.md):

| module | reads sections | plus |
|---|---|---|
| `lift_ast.py` (interfaces first) | 2, 3 | SPEC.md, SYNTAX.md |
| `lift_resolve.py`, `lift_parse.py` and its printer | 1, 3, 10(b), 18.1 | verifiers/dafny.py for the dafny invocation style |
| `lift_classify.py`, `lift_rewrite.py` | 4, 5, 6, 7, 18.2, 18.6, LIFTER-DECISIONS.md | fuzz_lower.check_wf, SYNTAX.md reserved words |
| `lift_check.py` | 9, 10, 11, 18.3, 18.4, 18.5 | fuzz_lower.check_wf, interp.Reference, interp.domain, harness.twin_for, lower_dafny.lower, verifiers/dafny.py |
| `lift_census.py`, `lifter.py` | 2, 8, 12, 13, 18.2, decisions 9 and 17 | t/coverage_census.py output (census.json) |

---

# Verified lift: a Dafny to t lifter whose lift is checked by Dafny

Strategy: verified-lift. Design wave for ROADMAP.md 12.4; a later wave
implements. Every number below is a measurement made on this box on
2026-09-05 with Dafny 4.11.0 at $HOME/.local/dafny, and every
command is listed in section 16. Where a rule rests on a reading of a
program, the file and line are quoted. No schedule anywhere in this
document, only per-step costs that were timed.

Experiment files: <scratch>/lifter/design/vl/
(hand-lifted tasks fatorial.json and cube.json, the lemma files eq_*.dfy,
the negative controls neg*.dfy, the probes, and rp/ holding the resolver's
print of all 785 corpus files).

## 0. The idea in one paragraph

The lifter reads Dafny's OWN resolved print of a program (`dafny resolve
FILE --rprint:OUT`), never the raw source, so types of untyped locals and
the decreases clauses Dafny inferred arrive already decided by Dafny. It
lifts one method with an ensures into one t task by a closed list of
rewrite rules (section 4) and refuses everything else with a named reason
(section 5). Then it does not trust itself: for every lifted program it
emits one Dafny checker file holding the original declarations
(alpha-renamed), the lifted task lowered back to Dafny by the repo's own
lower_dafny.py, and one lemma per spec function (`f_src(x) == f_lift(x)` on
the source's domain), one lemma for the requires, one for the ensures, one
per loop for its invariant conjunction and one for its decreases, each an
`<==>` or `==` between the source clause and the lifted clause under the
same names. Dafny verifies the checker file; a failed lemma is a refused
lift, reason `lift-check-failed`, with the lemma named. The body, which
Dafny cannot compare as an object, is checked by a bounded differential run
of source and lift compiled together (`dafny run`, 3.9 to 4.5 s per
program, measured) plus expression-level lemmas where the body's
expressions are total; the seven-kernel grade of the lifted body against
the proven-equivalent contract is what the coverage table counts, and it is
NOT a body-fidelity check (section 10 says why). Measured end to end on
three real programs (fatorial2, IsEven, Cube): every equivalence lemma
verifies, and five deliberately wrong lifts each fail exactly the lemma
that guards the corrupted clause (section 9).

## 1. Front end: the resolver's print, and why

Three candidates were on the table: a hand-written parser over the raw
source, a parser over `dafny resolve --print`, and a parser over `dafny
resolve --rprint`. The third wins on four measured facts:

1. rprint carries the INFERRED decreases of loops and functions, which
   `--print` does not (FACTS-for-review.md; re-measured here: fat.rp.dfy has
   `decreases n` on `Fat`, cube.rp.dfy has `decreases if i <= n then n - i
   else i - n` on `while i != n`, mult.rp.dfy has `decreases m - 0` on
   `while m > 0`, sqrt.rp.dfy has `decreases N - (r + 1) * (r + 1)` on
   `while (r + 1) * (r + 1) <= N`). Over all 785 corpus rprints, 656 while
   loops occur and 656 carry a decreases line (63 of them the ite shape
   from a `!=` guard). t requires a decreases on every loop and every
   spec_fun; rprint is the only place Dafny states the one it used.
2. rprint carries the INFERRED types of untyped locals: `var i: int := 1`
   in fat.rp.dfy (source line 10 `var i := 1;`), `var b: nat := x;` in
   potencia.rp.dfy (source line 18 `var b := x;`, typed nat because x is
   nat). 14 nat-typed locals appear in the 77 in-fragment rprints, only
   some of them typed nat in the source (extra_sum.dfy lines 12 to 14 `var
   x:nat := 0;`); the others are inferences the lifter could not have made
   without reimplementing Dafny's type inference.
3. rprint is canonical and comment-free, and it is a fixpoint: rprint of
   fat.rp.dfy's declarations reproduces them byte for byte (measured, `diff`
   empty). A print-and-compare round trip is therefore well defined.
4. It costs 0.5 s per file (timed on seven files: 0.48 to 0.53 s), and it
   ran over all 785 corpus files: 783 exit 0, 2 exit 2 (resolution errors
   in groupTheory_tmp_tmppmmxvu8h_assignment1.dfy, "can't use parenthesis
   when hiding or revealing", and Program-Verification-Dataset ...
   ACL2-extractor.dfy, a nonempty type parameter error). Those two are
   refused `resolve-failure` before any construct question.

What rprint costs the lifter, each measured and each handled:

- a `module _System { ... }` preamble (lines 4 to 112 of every rprint here),
  a `// bitvector types in use:` line, a closing `*/`, and a `/* CALL GRAPH
  for module _module: ... */` comment before the declarations. The parser
  skips to the end of the CALL GRAPH comment; the call graph is also
  useful (section 4, closure rule).
- `{:trigger ...}` attributes on every quantifier (`forall i: int {:trigger
  values[i]} | 0 <= i < |values| :: values[i] <= max`, maximum.rp.dfy). 473
  of the 785 rprints carry one. The parser accepts and discards them; they
  are the resolver's, not the program's.
- a method-level `decreases` on EVERY method (`decreases n` on Cube,
  `decreases a, b, c` on CountEqualNumbers, `decreases values` on Maximum):
  73 of the 77 in-fragment rprints have one. It is dropped when the body
  has no self-call, because fuzz_lower.check_wf rejects "task decreases
  without a self-call".
- deprecated-semicolon warnings end `dafny resolve` at exit 2 unless
  `--allow-warnings` is passed, and the rprint is written either way
  (iseven.rp.dfy, 2698 bytes, exists after the exit-2 run). The lifter
  passes `--allow-warnings` and reads the exit code only to separate
  resolution errors from warnings.
- rprint normalises the association of `*`: `(x * y) * z == x * (y * z)`
  prints as `x * y * z == x * y * z` (prec.rp.dfy). Mathematical integers
  make this harmless for meaning; it is noted because it means the lifter
  sees a left-associated tree wherever the source had a right one.
- `-(-x)` prints as `--x`; the lexer must read that as two unary minuses.

Windows (RUN-ON-WINDOWS.md): the resolver is invoked as an argument list
through subprocess (no shell; corpus file names contain spaces and one
contains non-ASCII), `--rprint:PATH` is one argument, output files are read
as UTF-8 and written with `newline="\n"`.

## 2. Architecture

Modules, Python 3.12 standard library only, one file each:

| module | input | output | may decide | may not decide |
|---|---|---|---|---|
| `lift_resolve.py` | a .dfy path | rprint text, exit code, stderr | `resolve-failure`, `parse-failure` (unknown token) | nothing about constructs |
| `lift_parse.py` | rprint text | a Dafny AST of the fragment in section 3, or a parse error naming the token | which declaration is the gradable method (a `method` with >= 1 ensures) | whether a construct is liftable |
| `lift_classify.py` | Dafny AST | per method: the refusal reason (section 5) or a "liftable" mark with the rewrite list | the refusal reason from the census vocabulary plus section 5's additions | any rewrite |
| `lift_rewrite.py` | liftable method AST plus the call-graph closure | the t task JSON, the rename map, the rewrite log, the added-clause log | only the rewrites in section 4, deterministically | to add, drop or reorder any source clause except by a rule in section 4 |
| `lift_check.py` | task JSON, source AST | the checker .dfy (section 9), the differential harness .dfy (section 10), their verdicts | `lift-check-failed` (lemma named), `lift-diff-failed` (input named) | to repair a failed lift |
| `lift_census.py` | all of the above for 785 files, census.json | the disagreement table, per-file rows | agreement / disagreement / undecided per row | the policy calls in section 15 |

Data flow per file: resolve -> parse -> classify (refuse or continue) ->
rewrite -> `fuzz_lower.check_wf` (must be `[]`) -> `interp.Reference` (must
execute: >= 1 point, else `interp-no-point` recorded, not a refusal) ->
`harness.twin_for` (rung recorded, or twin refusal recorded) -> checker
file verified by dafny -> differential run -> row.

The row is per gradable METHOD, not per file: a file with two gradable
methods yields two candidates, each with its own fate (aula2.dfy has
seven methods, three of them liftable as written). The census counts
files; the table reports both granularities and says which.

Provenance sidecar `<task>.lift.json` beside every emitted task: source
path, method name, rprint sha256, rename map (source name -> t name, with
the reason), rewrites applied (rule id, source line), clauses added (rule
id, text), clauses dropped (asserts, function ensures, unreachable
declarations, method-level decreases), decreases origin per loop and
spec_fun (`stated`, `rprint-inferred`, `projected`, `guess:sum`), twin rung
and witness, checker verdicts per lemma, differential verdict. The
disagreement table is read against the source through this file.

## 3. What is parsed

The parser recognises MORE than t accepts: it must read the whole method to
name the refusal, so it parses the general shapes below and the classifier
refuses on them. Anything outside this grammar is `parse-failure` with the
offending token and line; a parse failure is a refusal, never a guess.

```ebnf
RPrint     ::= Preamble Decl*
Preamble   ::= "module" "_System" "{" ... "}" "// bitvector types in use:" ... "*/"
               "/* CALL GRAPH for module _module:" CallGraph "*/"
CallGraph  ::= ("* SCC at height" Int ":" ("*" Id)+ )*

Decl       ::= Function | Method | Lemma | Skipped
Function   ::= ["ghost"] ("function" | "predicate") Id [TypeParams] "(" Params ")" [":" Type]
               FSpec* ( "{" Expr "}" | )                     (* bodyless: refuse *)
Method     ::= "method" Id [TypeParams] "(" Params ")" ["returns" "(" Params ")"]
               MSpec* ( Block | )                            (* bodyless: refuse *)
Lemma      ::= ("lemma" | "least lemma" | "greatest lemma" | "twostate lemma") ... Block
               (* brace-matched and dropped; a lemma is a hint *)
Skipped    ::= ("datatype" | "codatatype" | "class" | "trait" | "type" | "newtype" | "const"
               | "iterator" | "module" | "import" | "export" | "least predicate"
               | "greatest predicate" | "twostate function" | "twostate predicate") ...
               (* recorded under the census gap name, method not lifted *)

Params     ::= [ Param ("," Param)* ]
Param      ::= ["ghost"] Id ":" Type
Type       ::= "int" | "nat" | "bool" | "seq" "<" Type ">" | "array" ["?"] "<" Type ">"
             | "set" "<" Type ">" | "map" "<" Type "," Type ">" | "string" | "char" | "real"
             | "bv" Int | "(" Type ("," Type)* ")" | Type "->" Type | Id [ "<" Type ("," Type)* ">" ]
FSpec      ::= "requires" Expr | "ensures" Expr | "reads" ExprList | "decreases" ExprList
MSpec      ::= "requires" Expr | "ensures" Expr | "modifies" ExprList | "decreases" ExprList
ExprList   ::= Expr ("," Expr)* | "*"

Block      ::= "{" Stmt* "}"
Stmt       ::= Lhs ("," Lhs)* ":=" Rhs ("," Rhs)* ";"
             | "var" ["ghost"] VarDecl ("," VarDecl)* [":=" Rhs ("," Rhs)*] ";"
             | "var" VarDecl ("," VarDecl)* ":|" Expr ";"
             | "if" (Expr | "*") Block ["else" (Block | IfStmt)]
             | "if" "{" ("case" Expr "=>" Stmt*)+ "}"
             | "while" (Expr | "*") LoopSpec* Block
             | "while" "{" ("case" Expr "=>" Stmt*)+ "}"
             | "for" Id [":" Type] ":=" Expr ("to" | "downto") Expr LoopSpec* Block
             | "return" [Expr ("," Expr)*] ";" | "break" ";" | "continue" ";"
             | "assert" Expr ";" | "assert" Expr "by" Block | "assume" Expr ";"
             | "calc" ... | "forall" ... Block | "print" ExprList ";" | "expect" Expr ";"
             | "reveal" ... ";" | "label" Id ":" Stmt | Id "(" [ExprList] ")" ";"   (* method call *)
             | Block
Lhs        ::= Id | Expr "[" Expr "]" | Expr "." Id
Rhs        ::= Expr | "*" | "new" ...
VarDecl    ::= Id [":" Type]
LoopSpec   ::= "invariant" Expr | "decreases" ExprList | "modifies" ExprList

Expr       ::= Equiv
Equiv      ::= Implies ("<==>" Implies)*                          (* lowest *)
Implies    ::= OrAnd ["==>" Implies] | OrAnd ("<==" OrAnd)*      (* ==> right-assoc *)
OrAnd      ::= Not ("&&" Not)* | Not ("||" Not)*                 (* mixing needs parens; rprint parenthesises *)
Not        ::= "!" Not | Rel
Rel        ::= Add (RelOp Add)*                                    (* chains: 0 <= i < n, a == b == c *)
RelOp      ::= "==" | "!=" | "<" | "<=" | ">" | ">=" | "in" | "!in"
Add        ::= Mul (("+" | "-") Mul)*
Mul        ::= Unary (("*" | "/" | "%") Unary)*
Unary      ::= "-" Unary | Primary                                (* "--x" is two minuses *)
Primary    ::= Atom ( "(" [ExprList] ")" | "[" Expr "]" | "[" [Expr] ".." [Expr] "]"
                    | "[" Expr ":=" Expr "]" | "." Id | "as" Type | "is" Type )*
Atom       ::= Int | "true" | "false" | Id | "(" Expr ("," Expr)* ")" | "|" Expr "|"
             | "[" [ExprList] "]" | "{" [ExprList] "}" | "old" "(" Expr ")" | "fresh" "(" Expr ")"
             | "if" Expr "then" Expr "else" Expr
             | ("forall" | "exists") Binders [Attr*] ["|" Expr] "::" Expr
             | "set" Binders ... | "map" Binders ... | "seq" "(" ... | Real | Char | String
Binders    ::= Id [":" Type] ("," Id [":" Type])*
Attr       ::= "{:" Id ExprList "}"                              (* {:trigger ...}: discarded *)
```

The precedence table was pinned by what rprint keeps parenthesised
(prec.rp.dfy, section 16): `a ==> b ==> c` and `a <==> b ==> c` print
without parentheses, `(a ==> b) ==> c` and `(a <==> b) ==> c` keep them;
`a && b ==> c` and `a ==> b || c` print bare; `-x * y` is `(-x) * y`; `x -
(y - z)` keeps its parentheses; `x == y == z` and `0 <= x < y <= z` are
chains; `x in s && b` puts `in` at the comparison level.

The Dafny AST the parser produces is a plain Python tree (tuples of kind
and children with a line number from rprint). The t AST is SYNTAX.md's
JSON, produced only by `lift_rewrite.py`.

## 4. Mapping rules

One row per construct. "Condition" is when the row applies; when no row
applies the construct is refused (section 5). The meaning column says why
the lift preserves what the kernels grade: the theorem `requires ==>
(body terminates and ensures)` under SPEC.md semantics, and the twin's
instrument (the spec, fixed) plus the mutable body.

### 4.1 Declarations

| Dafny | t | condition | meaning argument |
|---|---|---|---|
| `method M(params) returns (r: T) requires.. ensures.. { body }` | the task: `name`, `params`, `returns: [r]`, `requires`, `ensures`, `body`, `"t": 1`, `gate` by content (recursion if a spec_fun or self-call exists, else loops if a while exists, else quantifiers if a forall/exists/seq exists, else omitted) | exactly one gradable method per candidate; >= 1 ensures; exactly one return; every param type in {int, nat, bool, seq<int>}; return type in {int, nat, bool}; no modifies | one task = one method; `"t": 1` is a superset of v0 byte for byte (SPEC.md), so no v0 task is lost and lower_verus/lower_rocq's v0-only refusals are avoided |
| `function F(params): T { e }`, `ghost function`, `predicate`, `ghost predicate` | a spec_fun with `result` int or bool, body `e` lifted, `decreases` per section 6, domain guard per 4.6 | params in {int, nat, seq<int>}, result in {int, nat, bool}; no `reads`; body present; F in the call-graph closure of the method; not in a recursive SCC with another function | Dafny functions are pure and total on their declared domain, exactly t's spec_fun; ghost-ness is irrelevant because spec_funs are spec-only in every lowering |
| `function F(...) requires P { e }` | spec_fun with body `ite(P, e, default)` (default 0 for int, false for bool); the equivalence lemma carries `requires P` | P lifts as an Expr | t has no partial spec_fun; the guard makes the lift total and agrees with F wherever F is defined, which is the only place the source's proof (Dafny well-formedness) ever reads F; outside the domain the source has no value and the lifted requires/type clauses exclude the input (section 4.6). Measured: IsEven's `even(n: int): bool requires n >= 0` lifts this way and `L_fun_even` verifies |
| `function F(...) ensures Q { e }` | as above; Q dropped and logged `function-ensures-dropped` | | Q is a theorem about F that Dafny proved and then used as a hint; t has no place for it; dropping it cannot change F's value and can only make a kernel's proof harder (an honest UNPROVED, attributable through the sidecar) |
| `lemma L(...) ensures ... { }` (with or without body) | dropped, logged `lemma-dropped` | not called from the method body (a lemma CALL in a body is refused, 4.5) | lemmas are hints (SYNTAX.md); a bodyless lemma is an axiom the source assumed, and an uncalled one does not enter the method's proof (expt.dfy line 22, `lemma {:induction a} distributive(...)` with no body, unreachable from `expt`) |
| `method Main() { ... }`, any method with zero ensures | skipped, never lifted (`main-harness` logged when named Main) | | no ensures means nothing to grade; the decision is by ensures count, never by name (a method named Main with an ensures would be a candidate) |
| declarations outside the method's call-graph closure | dropped, logged `unreachable-dropped` | the CALL GRAPH comment gives the SCCs; closure = the method's SCC and everything below it that its spec or body names, transitively | the method's theorem depends only on what it names (ex06-solution.dfy line 25 `ghost function gcd'(x:int,y:int):int` is not named by `gcdI` and is dropped; its `decreases x+y,y` never becomes a lifter problem) |
| `function F(a: array<int>)` or any `reads` | refuse `array` / `frame-clause` | | policy question (section 15, read-only arrays) |

### 4.2 Types

| Dafny | t | condition | meaning argument |
|---|---|---|---|
| `int` | `int` | | identical: mathematical integers in both |
| `bool` | `bool` (param, return or local) | | identical; SPEC.md v1 admits bool params, returns and locals |
| `nat` on a param `p` | `int`, plus `requires p >= 0` inserted BEFORE the source requires | | Dafny's nat is the subset type `int` with `>= 0` assumed on entry; putting it first lets every later clause assume it, which is the order Dafny checks well-formedness in (section 7) |
| `nat` on the return `r` | `int`, plus `ensures r >= 0` inserted BEFORE the source ensures | | the caller of the source sees `returns (r: nat)`; the theorem the kernels prove must include it (section 7 and open decision 15.3) |
| `nat` on a local `v` (stated or rprint-inferred) | `int` local; for every loop whose body assigns `v` and in whose scope `v` is, `invariant v >= 0` inserted FIRST in that loop's list; logged `nat-local-invariant` | | Dafny checks `>= 0` at every assignment to `v` and assumes it at every loop head; the invariant is the same obligation at the end of the body and the same assumption at the head (section 7). Measured: Fatorial's `f: nat` return assigned in the loop lifts with `invariant (f >= 0)` and verifies |
| `nat` result of a function | `int` result; logged `nat-result-fact-dropped` | | the function's value is unchanged; only the free fact `F(x) >= 0` is lost to the kernels (section 7 measures what that costs) |
| `seq<int>` param | `seq` | | t's seq is a value sequence of mathematical integers, Dafny's too |
| `seq<int>` local, return, or function result | refuse `seq-return` / `seq-local` | | t v1 has seq params only |
| `real`, `char`, `string`, `set`, `map`, `bv..`, tuples, `array`, class types, datatypes, generics | refuse with the census gap name | | no t type; no integer encoding preserves reals or chars (hazard 33) |

### 4.3 Contract clauses

| Dafny | t | condition | meaning argument |
|---|---|---|---|
| `requires P` (one clause) | one requires Expr | | one Dafny clause = one t clause; the list order is preserved because each clause may assume the earlier ones in both (SPEC.md definedness) |
| `requires P && Q` in one clause | one `and` node, NOT split | | splitting is meaning-preserving but is a policy the source did not choose; the twin does not touch requires, so this only changes clause counts (open decision 15.5) |
| `requires true` | `[{"bool": true}]` | | mirrors the source (A8_Q2.dfy line 5 `requires true;`); `[]` would also be true but drops a clause the author wrote |
| `ensures Q` | one ensures Expr; the return-type clause of 4.2 goes first | | as for requires; `ensures` sees params and the return in both |
| `ensures A && B` (801.dfy line 2 `ensures count >= 0 && count <= 3`) | one n-ary `and` | | mirror; the certificate negates the conjunction of all ensures, which is the same formula either way |
| `A <==> B` | `{"op": "==", "args": [A, B]}` with both sides bool | both sides typecheck as bool | `<==>` on booleans is equality on booleans; the lifted `==` on two bools is what SPEC.md gate 1 allows; the contract lemma re-proves it per program (IsEven `ensures r <==> even(n);`, line 9: `L_ens` verified) |
| `A ==> B` | `implies` | | identical definedness rule (B defined when A true) |
| `A && B && C`, `A \|\| B \|\| C` | one n-ary `and` / `or` in source order | | Dafny's chain is left-to-right short-circuit; t's n-ary node is the same evaluation (762.dfy line 3 becomes one 4-ary `or`) |
| `!A` | `not` | | identical |
| `a <= b < c` (chain) | `and(a <= b, b < c)` | every link an order or equality operator | Dafny defines the chain as the conjunction with the middle operand evaluated once; t expressions are pure so double evaluation is unobservable, and definedness of `b` is checked in both conjuncts (23 in-fragment files, e.g. fatorial2.dfy line 13 `invariant 1 <= i <= n+1`) |
| `a == b == c` | `and(a == b, b == c)` | | same |
| `x in s`, `x !in s` with `s: seq<int>` | `exists k in [0, len(s)) . s[k] == x` / `not` of it, `k` fresh | | Dafny's seq membership is exactly that existential; it is a REWRITE the contract lemma verifies per program, never trusted (maximum.dfy line 10 `ensures max in values`) |
| `s == []`, `s != []` | `len(s) == 0`, `len(s) != 0` | the literal is empty | a seq equals the empty seq iff its length is 0; verified by the contract lemma (maximum.dfy line 9 `requires values != []`); any other seq literal is refuse `seq-literal` |
| `\|s\|` | `len(s)` | | identical |
| `s[i]` | `at(s, i)` | | identical, including definedness: Dafny checks `0 <= i < \|s\|` as well-formedness, t leaves `at` undefined outside it and every lowering discharges or abstains |
| `s[a..b]`, `s[i := v]`, `s + t`, `s <= t`, `seq(n, f)` | refuse `seq-slice`, `seq-update`, `seq-concat`, `seq-prefix`, `seq-comprehension` | | no t node; a slice-parameterised spec_fun would be a spec re-expression, not a lift (hazard 27) |
| `old(e)`, `fresh`, `unchanged`, `@L` labels | refuse `old` | | two-state; t has no heap and no pre-state |
| `x / y`, `x % y` | refuse `div-mod` | | SPEC.md refuses the operator by design |

### 4.4 Quantifiers

Ranges arrive in three spellings and rprint keeps them
(`forall i: int {:trigger values[i]} | 0 <= i < |values| :: ...` in
maximum.rp.dfy; `exists i: int {:trigger seq1[i]} :: 0 <= i < |seq1| &&
seq1[i] in seq2` in s414.rp.dfy). Every row below produces t's half-open
`[lo, hi)` and is verified by the contract lemma; the bound variable is
renamed fresh if it collides with anything in scope (Dafny accepts a bound
variable shadowing a parameter, measured in shadow.dfy; t forbids it).

| Dafny | t | condition | meaning argument |
|---|---|---|---|
| `forall k :: lo <= k < hi ==> P` | `forall k in [lo, hi) . P` | `k` int-typed (declared or inferred), lo and hi free of k | definitionally t's forall |
| `forall k \| lo <= k < hi :: P` | same | same | Dafny's range syntax is the antecedent form |
| `exists k :: lo <= k < hi && P` | `exists k in [lo, hi) . P` | | definitionally t's exists |
| `forall k :: lo <= k <= hi ==> P` | `[lo, hi + 1)` | | integers; verified by the lemma |
| `forall k :: lo < k < hi ==> P`, `lo < k <= hi` | `[lo + 1, hi)`, `[lo + 1, hi + 1)` | | integers; verified by the lemma; the `+ 1` literals sit in spec position, which the twin never mutates |
| `forall k :: lo <= k < hi && Q ==> P` | `forall k in [lo, hi) . implies(Q, P)` | Q free of further range constraints on k | `(R && Q) ==> P` equals `R ==> (Q ==> P)` |
| `forall k :: k in s ==> P` with s a seq | `forall j in [0, len(s)) . P[k := s[j]]` | P has no other range on k | membership over a seq value is a bounded range over its indices; the lemma verifies the instance |
| two binders `forall i, j :: R(i) && R(j) ==> P` | nested foralls, each with its own range | each binder has its own `lo <= v < hi` conjunct | nesting is the meaning of a multi-binder quantifier |
| no range, a range not of the form above (803.dfy line 4 `forall a: int :: 0 < a*a < n ==> a*a != n`), a non-int binder, `k in S` with S a set or map | refuse `unbounded-quantifier` (or `set` / `map`) | | t quantifies over an integer interval only (SPEC.md gate 1) |

### 4.5 Statements

| Dafny | t | condition | meaning argument |
|---|---|---|---|
| `x := e;` | `{"assign": [x, e]}` | x is the return or a local | identical |
| `var x: T := e;` | `{"var": {"name": x, "type": T, "init": e}}` with T from rprint | T int or bool (nat per 4.2); x does not shadow (else renamed, 4.8) | identical; the type is Dafny's own inference |
| `var x, y := a, b;` | two `var` statements in order | | the right-hand sides cannot name x or y (they are being declared), so sequencing is exact (stairs.dfy line 9 `var a, b := 1, 1;`) |
| `var x: T;` (no initialiser) | the declaration moves to the first assignment `x := e` and becomes `var x: T := e` | the first assignment is at the same block level, and no read of x precedes it (Dafny's definite-assignment rule guarantees the second) | the value of x is undefined until that assignment in Dafny too; moving the declaration shrinks scope only over statements that could not mention x (Square.dfy lines 5 to 10; hoangkim.dfy lines 16 to 18) |
| `var x: T;` first assigned inside a branch or a loop | refuse `uninitialized-local` | | inventing an initialiser adds a literal the OFF-BY-ONE rung can target and a value the source never had |
| `x, y := e1, e2;` | `var t0 := e1; var t1 := e2; x := t0; y := t1;` with fresh `t*` names | every target is a return or local (not `a[i]`, not `*`) | Dafny's simultaneous assignment evaluates every right-hand side before any write; the temporaries do exactly that, so no dependency analysis is needed and no case is mis-ordered (Cube.dfy line 14 `c, k, m := c + k, k + m, m + 6;` measured: the lift verifies and the differential run agrees on 41 points) |
| `x := *;`, `x, y := *, *;` | refuse `nondet` | | a havoc is not an assignment (product_details.dfy line 8) |
| `if c { A } else { B }` | `if` with then/else lists | | identical |
| `if c { A }` | `if` with `"else": []` | every path still assigns the return (4.7) | identical; SPEC.md allows an empty else |
| `if c1 { A } else if c2 { B } else { C }` | nested `if` in the else list | | identical (227.dfy lines 5 to 11) |
| `if { case .. }`, `if * ..`, `while * ..` | refuse `nondet` | | |
| `while g invariant I.. decreases d { B }` | `while` with the invariant list in source order, decreases per section 6 | g lifts as bool Expr | the loop rule is SPEC.md's; the frame rule matches (Dafny havocs the assigned set; SPEC.md too, normative) |
| `for i := lo to hi invariant I.. { B }` | `var h := hi; var i := lo; while i < h invariant lo <= i, invariant i <= h, I.. decreases h - i { B; i := i + 1 }` (`downto`: `var i := hi; while i > lo ... decreases i - lo { i := i - 1; B }`) | B has no `break`/`continue`, no assignment to i; `h` fresh | Dafny evaluates the bound once and gives the loop the implicit invariant `lo <= i <= hi` and the implicit measure; the desugaring states exactly those (forloop.rp.dfy shows rprint keeps `for` and prints no decreases, so the measure is the lifter's and the kernel checks it). Zero of the 77 have a `for`; 101 corpus files do |
| `return;` as the last statement | dropped | tail position | no effect: the return variable already holds the value |
| `return r;` where r is the return variable, tail | dropped | tail position | identical (Invariants_ex1.dfy line 16 `return r;`) |
| `return e;` in tail position | `r := e` | tail position: last statement of the body, or last statement of a branch of an `if` that is itself in tail position, recursively | the value assigned to r is what the method returns (Clover_abs.dfy lines 6 and 8 `return -x;` / `return x;` inside the final if; se2011 ex4 line 14 `return z;` of a local) |
| any other `return`, `break`, `continue` | refuse `early-exit` | | a t body has no exits (strings1.dfy line 11 `{return false;}` before the loop, 414.dfy line 11 `break;`) |
| `assert P;`, `assert P by {..}`, `calc {..}`, `reveal`, `forall` statement | dropped, logged `assert-dropped` with count | | obligations, not assumptions: removing them cannot change the value (they have none) and cannot weaken the theorem; it can lose a proof hint (kernels that do not unfold recursion unaided), which is an honest UNPROVED attributed through the sidecar (extra_sum.dfy lines 20 to 34, eleven asserts) |
| `assume P;` | refuse `assume` (executable code) | | an assumption gives the body a meaning the kernel did not prove; every t adapter bans it (verifiers/dafny.py ban regex) |
| `L(args);` lemma call | refuse `lemma-call` | | the lemma's ensures becomes an assumption at that point; t has no statement for it |
| `x := M(args);` another method | refuse `calls-other-method` | | t has no encoding of a callee contract other than the task's own (aula2.dfy line 45 `var aux2 := mystery1(m,aux);`) |
| `r := M(args);` where M is the method itself | `{"call": {"fun": task, "args": ..}}` in the assignment, task-level `decreases` from the method's stated or rprint decreases (section 6) | the method has a decreases (stated or rprint) that projects to one int Expr; the self-call is in an assignment or a spec position, not under a lazily evaluated operator | SPEC.md gate 3 modular reasoning is Dafny's too (lab7_question5.dfy line 8 `r:= M1(-x, y);` would qualify were line 12 `r:= A1(r, y);` not a call of another method) |
| `ghost var`, `ghost` statements | refuse `ghost-var` if the variable is read by an executable statement, else dropped and logged | | a ghost local exists for asserts only |
| `print`, `expect` | refuse `io` | | |
| `a[i] := e`, `new`, `this`, `modifies` | refuse `array-mutation`, `heap`, `frame-clause` | | |

### 4.6 Spec functions: totalisation

A Dafny function is defined only on inputs where its parameters have their
types and its `requires` hold. t's spec_fun is total. The lift of `function
F(p1: T1, ..., pk: Tk) requires P { e }` is

    body_lift = ite(D, e_lift, default)
    D = and(p_i >= 0 for each nat p_i, in order, then P_lift if present)

with `default` 0 for int results and false for bool results, and `e_lift`
the lifted body. Reasons, each measured:

- Without the guard the lift is REJECTED by Dafny on termination: the
  int-typed `fat(n) = if n == 0 then 1 else n * fat(n - 1)` with `decreases
  n` fails with "decreases expression must be bounded below by 0" (exit
  4, noguard.dfy). With the guard it verifies (guard.dfy). Every kernel has
  the same obligation (SPEC.md gate 3), so the guard is not a Dafny
  accommodation.
- On the source's domain the two functions agree, and that is a theorem
  Dafny proves by auto-induction for every case tried: `L_fun_fat(n: int)
  requires n >= 0 ensures Fat_src(n) == fat(n)`, `L_fun_even(n) requires n
  >= 0`, `L_fun_gcd(x, y) requires x > 0 && y > 0`, `L_fun_potencia(x, y)
  requires x >= 0 && y >= 0`: all verified, 0 errors.
- Outside the domain the source has no value. The only positions that
  could observe the default are (a) the task's inputs, excluded by the
  lifted requires which carries every type and requires clause; (b) spec
  positions inside the task (ensures, invariants), which the source's
  well-formedness proof shows are only evaluated where the earlier clauses
  put the argument in the domain, and t's clause-list definedness rule
  gives the lifted clause the same earlier clauses; (c) the twin's mutated
  body, where a value the source lacked can appear: that changes which
  twins refute, never the real task's theorem (section 11).

The alternative, rewriting the base case `n == 0` to `n <= 0` (as
tasks/factorial.json does by hand), is NOT used: it edits the body's
literal structure per function and is decidable only by inspecting every
self-call; the guard is one uniform rule with one uniform lemma.

### 4.7 Definite assignment

t requires every path to end in an assignment of the return (SYNTAX.md).
The lifter checks it on the t body (an `if` without else on the last path,
aula2.dfy m1 lines 55 to 57 `if (x > 0 && y > 0 && y > x) { z := x-1; }`,
leaves z unassigned) and refuses `return-not-assigned-on-all-paths`. Dafny
accepts such a method with an unspecified return value; t has no havoc
value, so this is a refusal and not a rewrite.

### 4.8 Names

Every name is checked against: SYNTAX.md's `Id` regex; surface.py
`KEYWORDS` (t, gate, task, returns, requires, ensures, decreases, spec,
fun, var, while, invariant, if, then, else, forall, exists, in, len, true,
false, and, or, not, int, bool, seq); lower_fstar.py RESERVED and its
lowercase-initial rule; lower_rocq.py RESERVED plus its `_len` suffix and
`sf_` / `t_` prefixes; lower_spark.py RESERVED compared case-insensitively
(F, Seq, Seqs, Len, Elem, T_Range, R_First, R_Has, R_Next, Big_Integer,
Boolean, T_Refutation_Certificate); `main` (lower_verus appends `fn main`,
lower_framac emits a C entry point); and `t_refutation_certificate`.

Rename rule, deterministic: (1) `'` becomes `_p` (gcd' -> gcd_p); (2) an
uppercase initial is lowercased (Fat -> fat, N -> n); (3) if the result is
unusable or collides case-insensitively with another name in the task,
append `_v`, then `_v2`, `_v3` ... A return named `f` is renamed `f_v`
because spark's `F` catches it (fatorial2.dfy line 6 `returns (f:nat)`,
mockExam2_p6.dfy line 6 `ghost function f(n: int)`). A local that shadows
a parameter or an earlier local (Dafny accepts `var n := 5;` under a
parameter `n`, shadow.dfy, resolved with no warning) is renamed in its
scope, `n_v`. A quantifier's bound variable that shadows anything in scope
is renamed likewise.

Task name: the source file stem lowercased with every character outside
`[A-Za-z0-9_]` replaced by `_`, then `__`, then the method name after rule
(2). File stems are unique case-insensitively across the 785 (measured: no
duplicates after lowercasing), so task names are unique case-insensitively,
which lower_dafny's `.capitalize()` and spark's case folding need.

Every rename is recorded in the sidecar as `{"from": "Fat", "to": "fat",
"why": "uppercase-initial (fstar)", "line": 1}` so the disagreement table
and the checker file read against the source. The checker file uses the
SOURCE names with `_src` appended, so a lemma reads `Fat_src(n) == fat(n)`.

## 5. Refusal rules

The reason is the census gap name where the construct is the same; the
lifter never invents a reason for a construct the census names. Each row
records the rprint line of the first offending token.

| reason | trigger | census equivalent |
|---|---|---|
| `resolve-failure` | `dafny resolve` exits 2 with an Error line (not a warning) | none (2 of 785 files) |
| `parse-failure` | a token outside section 3's grammar | none |
| `no-method` | no `method` declaration | has-method = false |
| `no-ensures` | no method carries an ensures | method-with-ensures = false (gradable) |
| `zero-returns` | the gradable method has no `returns` | zero-returns |
| `multi-return` | two or more return values | multi-return |
| `multi-method` | never a refusal here: each gradable method is its own candidate; a file-level row reports `split-per-method` | multi-method (the census's file-level gap) |
| `array` | `array<T>` anywhere in the method's closure (read or written) | array (policy 15.1 could turn read-only params into seq) |
| `array-mutation` | `a[i] := e` or `modifies` | array-mutation |
| `div-mod` | `/` or `%` on integers | div-mod |
| `real` | `real` type or literal | real |
| `string-char` | `string`, `char`, `seq<char>` | string-char |
| `set`, `map`, `tuple`, `datatype`, `heap`, `generics`, `module`, `higher-order`, `bitvector`, `iterator`, `type-decl`, `nested-seq`, `seq-return`, `seq-literal`, `seq-slice`, `seq-update`, `seq-comprehension`, `char-arith`, `extreme-predicate`, `decreases-star`, `bodyless-function`, `bodyless-method`, `function-method`, `such-that-exec`, `io`, `nondet`, `old`, `unbounded-quantifier`, `mutual-recursion`, `early-exit` | the construct named, as detected on the AST (not lexically) | the same name |
| `seq-concat`, `seq-prefix`, `seq-local`, `seq-equality` | `s + t`, `s <= t`, a seq-typed local or function result, `s == t` with t not `[]` | none (the census folds these into seq-literal / seq-slice or misses `+`) |
| `assume` | `assume` in executable code | assume was a hint in the census; here a refusal |
| `lemma-call` | a lemma called from the method body | none (lemma was a hint) |
| `calls-other-method` | a call of a method other than itself | none (folded into multi-method by the census) |
| `self-call-lazy` | a self-call under a lazily evaluated operator or a quantifier body | none (lower_dafny abstains on it) |
| `uninitialized-local` | `var x: T;` first assigned inside a branch or loop | none |
| `return-not-assigned-on-all-paths` | section 4.7 | none |
| `ghost-var` | a ghost local read by executable code | ghost-var was a hint |
| `function-contract` | a function `reads` clause | frame-clause (burden) |
| `uninferable-decreases` | a loop with no decreases line in rprint, or a spec_fun/self-recursive task whose decreases candidates (section 6) are all rejected by the kernel-side check | while-no-decreases (burden) |
| `lexicographic-decreases` | a tuple decreases that neither projects nor sums (section 6) | none |
| `name-unsanitisable` | a name that rule 4.8 cannot make legal (non-ASCII letters, since t's Id is ASCII) | none |
| `lift-check-failed` | a checker lemma fails or times out (section 9), lemma named | none; this is the new instrument |
| `lift-diff-failed` | the differential run disagrees on an input (section 10), input named | none |
| `check-wf-failed` | fuzz_lower.check_wf returns errors on the emitted task (a lifter bug by construction; reported, never silently fixed) | none |

Not refusals, recorded as separate columns because the census had no such
concept: `twin-refused` (harness.twin_for returns no-operator, no-witness,
no-input, real-undefined, candidate-budget), `kernel-abstain` per kernel
(a NotImplementedError from a lowering: lean's boolean operator in
computational position and empty else path, fstar/rocq's loop under a
conditional, nested loops, more than one loop), and the per-kernel
verdict. A program that lifts and is refused at the twin (234.dfy, 626.dfy,
measured by the readers) is "in the fragment, cannot count", which is a
different row from "out of the fragment".

## 6. decreases inference

t requires a decreases on every loop and every spec_fun (and on the task
when the body self-calls). The measure never changes what a function or
loop COMPUTES (SPEC.md: a spec_fun denotes the unique function satisfying
its equation; the measure is the well-definedness obligation), so a wrong
guess is caught by the kernels as an unproved termination obligation and
can never corrupt a value or a spec. That is why a small deterministic
ladder is acceptable here and nowhere else in this design.

Loops:

1. A stated single expression: verbatim.
2. No stated clause: the rprint line, verbatim, as a t Expr. Measured shapes
   over the 656 corpus loops: `n - i` for `<`/`<=` guards, `m - 0` for `m
   > 0` (kept as `m - 0`, no simplification; the literal 0 is in spec
   position and the twin does not mutate decreases), `if i <= n then n - i
   else i - n` for `!=` guards (63 loops; lifts as `ite`, which check_wf
   types int; Cube measured VERIFIED with it), `N - (r + 1) * (r + 1)` for
   a compound guard. rprint prints a decreases for 656 of 656 corpus
   loops; a loop with none is a loop Dafny could not bound (noguess.dfy:
   "cannot prove termination; try supplying a decreases clause", and its
   rprint has no loop decreases), which cannot occur in a verified file and
   is refused `uninferable-decreases` if it does.
3. A tuple `d1, ..., dk` (stated, SlowMax.dfy line 17 `decreases x,y;`):
   project by dropping every component whose free variables the loop body
   never assigns; if one component remains, use it; if several remain and
   all are int, use their sum (`x + y` for SlowMax: both assigned); else
   refuse `lexicographic-decreases`. The sum is a guess the kernel checks.
4. `decreases *`: refuse `decreases-star`.

Spec functions (and a self-recursive task):

1. A stated single expression: verbatim (power.dfy line 7 `decreases n;`).
2. Otherwise rprint's tuple, which for a function without a clause is its
   parameters in order (`decreases x, y` on Potencia and on gcd, measured).
   Project: drop each component that is passed through unchanged at every
   self-call (Potencia(x, y-1): x unchanged, so `y` remains and is used;
   measured VERIFIED with the domain guard). If one remains, use it. If
   several remain and all are int, use the sum (gcd(x-y, y) and gcd(x,
   y-x): neither fixed, `x + y` used; measured VERIFIED with `L_fun_gcd`).
   Else refuse `lexicographic-decreases`.
3. Method-level decreases printed by rprint when the body has NO self-call:
   dropped (73 of 77 in-fragment rprints; check_wf rejects it otherwise).
   With a self-call: the same projection as for functions (lab7_question5
   `decreases x < 0, x` has a bool component and no int projection; it is
   refused for `calls-other-method` first anyway).

Every choice is recorded (`stated`, `rprint-inferred`, `projected:<i>`,
`guess:sum`). The kernel-side check for guesses is the checker file itself:
the lowered spec_fun's termination is one of the obligations `dafny verify`
discharges there, so a rejected guess reads `lift-check-failed:
termination` and the row says so.

## 7. nat handling

Dafny's `nat` is the subset type `{x: int | 0 <= x}`. Three facts about it
decide the rules: on entry Dafny ASSUMES it of params; at every assignment
to a nat variable Dafny PROVES it; at every loop head and method exit Dafny
ASSUMES it again of nat variables (as the type invariant). t has no
subset types, so the lifter reproduces those three uses as clauses, at
exactly the program points where Dafny assumes them, and drops the
per-assignment proofs in favour of the equivalent loop-head proof:

- param `p: nat` -> `requires p >= 0`, first. The clause is load-bearing
  even where the proof does not need it: it fixes the domain, and with it
  the twin's witness set (interp enumerates only inputs satisfying
  requires).
- return `r: nat` -> `ensures r >= 0`, first.
- local or return `v: nat` (stated, or inferred by rprint) assigned inside a
  loop -> `invariant v >= 0`, first in that loop's list. A nat variable not
  assigned in the loop needs nothing: the frame rule preserves it and the
  code before the loop fixed its value (potencia's `var b: nat := x` is
  covered by `requires x >= 0`).
- function result `F(...): nat` -> nothing (no place in t); logged.

The theorem this produces, and why it is the one to prove: the source's
contract as a caller sees it is `requires (types of params) && P ensures
(type of r) && Q`. The lifted contract is exactly that with the types
spelled out, and the checker lemmas (section 9) prove `requires_lift <==>
(types && P)` and `ensures_lift <==> (type(r) && Q)` per program. Dropping
`r >= 0` would make the lifted theorem weaker than the source's, which is
the corruption section 11 is built to catch; adding an `ensures` the
source did not state would make it stronger and is never done.

What it costs, measured and estimated: the added invariant carries the
proof for every nat variable whose new value is computed from nat
variables by `+`, `*` with a non-negative factor, or a guarded `-`
(Fatorial `f := f * i` under `1 <= i`, Cube `c := c + k`, calcR `r := r -
i` under `r > i`, all provable by the kernel from the invariants). It
does NOT carry the proof where the source got `>= 0` from a nat FUNCTION
result: ClimbStairs (`return b` with `b == Stairs(i)`), ComputeFib in
Metodos_Formais and in uiowa (`x, y := y, x + y` with `y == Fib(i+1)`),
calcF (`res := a` with `a == F(i)`). There the lifted `ensures r >= 0` (or
the added invariant) needs `F(n) >= 0`, a fact the int-typed spec_fun does
not carry and no kernel derives without an induction lemma. Those four
lift, pass check_wf, and are expected to read UNPROVED on the real cell in
every kernel, attributable to `nat-result-fact-dropped` in the sidecar.
Open decision 15.3 states the alternative and what it buys.

## 8. Provenance and the disagreement table

Row per file (785) and per gradable method. Columns: census in_fragment
and gaps; resolve exit; lifter verdict (`lifted` or `refused:<reason>` with
rprint line); rewrites and renames applied; check_wf; interp points and
first value; twin rung or refusal; checker verdicts per lemma; differential
verdict; per-kernel outcome (once the seven run); the disagreement verdict.

Disagreement verdict rule (mechanical, no judgment):

- census in, lifter refused with reason R at line L: `lifter` if R names a
  construct present at L (the row quotes the rprint line), `census` never
  (the census cannot be right that a program is in the fragment when a
  construct outside t is quoted), `undecided` if R is a policy reason
  (section 15) or `lift-check-failed` (then the LIFTER is suspect and the
  row is a bug report against it).
- census out with gap G, lifter lifted and checked: `lifter` when G's
  construct is absent (a detector fault, e.g. the whole-file `if-no-else`
  rule) or is one of the verified rewrites (`seq-membership`, `s != []`);
  `undecided` when G is a policy gap (read-only array).
- both refuse with different reasons: `gap-name`, the lifter's reason
  stands because it quotes a line; the census's tag is a detector fault
  when its construct is absent.
- both agree: `agree`.

## 9. The check: equivalence lemmas, verified by Dafny

For each lifted program one checker file `<task>.check.dfy`:

1. The source's call-graph closure, alpha-renamed by appending `_src` to
   every declaration name (functions and the method; params and locals
   keep their names), verbatim from rprint. Renaming a declaration is
   textual on the rprint, where every identifier is unambiguous.
2. The lifted task lowered by `lower_dafny.lower(task, task["body"])`,
   unmodified (its method is `Name.capitalize()`, its spec_funs keep their
   t names; no collision with `*_src`).
3. One lemma per spec_fun F with source params `p_i: T_i` and requires P:

       lemma L_fun_F(p_1: int, ..., p_k: int)
         requires <p_i >= 0 for each nat p_i> requires P_src
         ensures F_src(p_1, ..., p_k) == f_lift(p_1, ..., p_k)
       { }

   Dafny's auto-induction on int parameters proved every instance tried
   (fat, even, gcd, potencia). Params of type seq<int> are passed as
   seq<int>.
4. The requires lemma, over int-typed params with no requires of its own:

       lemma L_req(params: int...)
         ensures (<lifted requires conjunction>) <==> (<type clauses> && <source requires conjunction>)

   Well-formedness of the source side holds because the type clauses come
   first in the conjunction and Dafny checks `&&` left to right.
5. The ensures lemma, under the lifted requires:

       lemma L_ens(params: int..., r: int|bool)
         requires <lifted requires>
         ensures (<type clause of r> && <source ensures conjunction>) <==> (<lifted ensures conjunction>)
       { forall k: int | D_F(k) ensures F_src(k) == f_lift(k) { L_fun_F(k); }  // one per spec_fun named }

   The forall statement is REQUIRED: without it `L_ens` and `L_inv` for
   Fatorial fail ("a postcondition could not be proved", 10 verified 2
   errors, eq_fat.dfy) because Dafny does not apply `L_fun_fat` unprompted;
   with it 12 verified 0 errors (eq_fat2.dfy). For IsEven the lemmas
   verified without the hint (13 verified), so the hint is emitted always
   and costs nothing when unneeded.
6. Per loop, in pre-order, the invariant lemma over params, the return and
   every local in scope at the loop, all int-typed (bool for bool locals),
   under the lifted requires:

       lemma L_inv_<k>(...)
         requires <lifted requires>
         ensures (<nat clauses of the loop's variables> && <source invariants conjunction>) <==> (<lifted invariants conjunction>)

   and the decreases lemma `ensures <source or rprint decreases> == <lifted
   decreases>` (trivially true when the lift is verbatim; it exists so that
   a projected or summed measure is compared against what was projected,
   and so that a tuple measure is visibly NOT equal to the lift: the lemma
   is emitted only for single-expression measures and the sidecar says
   `guess` otherwise).
7. Verified with `dafny verify <file>`; the finish line must read `N
   verified, 0 errors` with N >= the number of lemmas plus lowered
   declarations, and every lemma's `Results for` block Correct. Cost
   measured: 1.08 to 1.16 s per file on fatorial2, IsEven, Cube, gcd and
   Potencia together.

What a failure means: the lifted clause is not equivalent to the source
clause on the source's domain, or Dafny could not prove that it is. The
two are not separated by the tool (exit 4 is could-not-prove, verifiers/
dafny.py's finding). The refusal is `lift-check-failed:<lemma>`, and it is
a refusal of the LIFT, recorded as such: the program is not counted in
either direction and the row is a work item for the lifter. A timeout is
the same refusal with `timeout` in place of the lemma's error.

Measured, positive: fatorial2 (12 verified, 0 errors), IsEven (13, 0),
Cube (7, 0), gcd and Potencia function lemmas (8, 0).

Measured, negative controls (each a wrong lift of fatorial2, each must and
does fail exactly its lemma, "a postcondition could not be proved"):
neg1 spec_fun base case returns 0 (L_fun_fat fails); neg2 ensures weakened
to `f >= 0` alone (L_ens fails); neg3 invariant `i <= n` for `i <= n + 1`
(L_inv_0 fails); neg4 requires dropped (L_req fails: `true <==> n >= 0 &&
true` is not a theorem); neg5 spec_fun recurses on `n - 2` (L_fun_fat
fails). A checker that could not fail would prove nothing; this one fails
where it should.

What the checker does NOT see: the body's statements (section 10), the
default branch of a totalised spec_fun (outside the domain, by design),
and hints (asserts, lemmas, function ensures), whose loss shows up as a
kernel UNPROVED, not as a lift error.

## 10. The body

Three candidates were named. Which is sound, which is theatre, and costs
on 785 programs (of which about 80 lift; nothing below runs on a refused
program):

(a) Differential execution. A `method Main()` is appended to the checker
file that calls `<Method>_src` and the lowered `<Method>` on every input of
`interp.domain(task)` that satisfies the lifted requires (the same points
interp's witness search uses, so the twin's domain and the fidelity
domain coincide), compares the results, and prints `points=N bad=M`;
`dafny run FILE --no-verify` compiles and runs it. Measured: 3.9 to 4.5 s
per program (Fatorial 41 points bad=0, Cube 41 points bad=0). Sound as a
bounded test: a disagreement is a proof that the lifted body is not the
source body (refuse `lift-diff-failed` with the input); agreement on the
domain is not a proof of identity, and the report says "agrees on N
points". It sees values only: invariants, decreases and asserts are ghost
and never execute, so a lift that damaged an annotation passes it (those
are covered by section 9's lemmas). It is the only check of the five
skeleton rewrites (return, parallel assignment, multi-name var, moved
declaration, for-desugaring) per program. Cost: ~80 x 4.5 s. Seq-typed
params are emitted as Dafny seq literals in the harness.

(b) Print-and-compare. The claim "the body lift is statement-for-statement
syntactic" is TRUE for 17 of the 77 (the readers' `lifts` verdict:
verbatim bodies) and FALSE for the 60 with a named rewrite, so a plain
round trip is not available as the body check. What print-and-compare
soundly checks is the PARSER: rprint(print(parse(rprint(src)))) ==
rprint(src), where print is the lifter's Dafny printer of its own AST.
rprint is a fixpoint (measured), so any deviation is a parse or print
error. That check costs 0.5 s per file and runs on all 785, and it is
what turns "parse, do not pattern-match" into a measurement. Beyond the
parser, the body's EXPRESSIONS are pure and get the lemma treatment: for
each assignment right-hand side, initialiser, if-condition and loop guard
whose source form is total on the type-correct states (no `s[i]`, no call
of a spec_fun with a domain), emit `lemma B_k(<scope>) requires <lifted
requires> ensures e_src == e_lift`; skip the others and log
`body-expr-unchecked` with the position. The rewrites that touch
expressions (chains, `<==>`, negative literals, the ite measure) are then
verified per program, and the five skeleton rewrites are argued once each
(section 4.5) and tested per program by (a). So (b) is sound for the
parser and for expressions, and honest about the rest; it is theatre only
if presented as a whole-body identity check.

(c) The kernel argument: "body faithfulness is covered because the seven
kernels grade the lifted body against the proven-equivalent contract".
This is the correct statement of what the COVERAGE claim needs: a program
is in t's fragment when its spec lifts to an equivalent t spec and some
body proves it with the twin refuted; the body is a witness that the spec
is satisfiable and non-vacuous, and the kernels are exactly the instrument
for that. It is THEATRE as a body-fidelity check: a lifted body that
computes something else but still meets the contract verifies; the twin
ladder then mutates a body the source never had, and "DafnyBench program
X verifies in seven kernels" would be a claim about the lifter's program.
Cost: nothing extra, the kernels run anyway.

Decision: (a) and (b) both run; (c) is what the table counts and is
labelled as a claim about the SPEC. A row reads "spec equivalent (lemmas),
body agrees on N points (diff), expressions equivalent (k lemmas, m
unchecked), kernels: ...". Nothing in the row says "the body is the
source's body" without those qualifiers.

## 11. Validation plan: how a wrong lift is caught before it corrupts a number

The two corruptions the wave statement names, and what catches each:

- A lifted spec WEAKER than the source (a dropped requires makes the
  domain larger and the real may fail honestly, which is loss not
  corruption; a dropped or weakened ensures makes the real easier and the
  TWIN easier to verify, so twin-VERIFIED rows, which the flip rule reads
  as "vacuous spec", would be manufactured by the lifter). Caught by L_req
  and L_ens: an `<==>` fails in the weakened direction (neg2, neg4
  measured). A weaker invariant makes the real harder, not the twin
  easier, and is caught by L_inv (neg3).
- A lifted body DIFFERENT from the source makes a true program fail
  (loss, misfiled as "the kernel could not prove X") or, worse, makes a
  body that meets the spec by a different route (the twin is of the wrong
  program). Caught by the differential run on the interp domain (values)
  and by the expression lemmas; the skeleton rewrites are five, each
  argued in 4.5 and each exercised by (a) on every program that uses it.
- A lifted spec STRONGER than the source (an added clause the source did
  not state): caught by L_ens/L_req in the other direction. The only added
  clauses are the type clauses of section 7, and the lemmas state them on
  the source side so the equivalence holds exactly.
- A wrong decreases: cannot corrupt (section 6); shows as a termination
  error in the checker file, `lift-check-failed: termination`.
- A wrong parse: caught by the print-and-compare fixpoint on all 785.
- A wrong rename: the checker file would not resolve (a name mismatch
  between `_src` and lifted sides is a resolution error, exit 2), and
  check_wf/surface.py reject keywords.

The flip discipline under a lift that passed every check: the twin is
derived from the LIFTED body by harness.twin_for, deterministically, and
the rung is recorded. The rewrite of a parallel assignment adds locals and
therefore WRONG-VAR candidates, the added `v >= 0` invariants add
INVARIANT-DROP sites, and the totalised spec_fun gives a twin a value
where the source's twin had none; each moves WHICH twin is chosen, none
changes what "COUNTS" means (real VERIFIED, twin REFUTED, witness
measured). The table therefore reports the rung per task and the
comparison to a hand-written task is by rung, not by "the twin".

What remains unverified after all checks, stated: identity of the body's
statement skeleton beyond the interp domain; the value of a totalised
spec_fun outside its domain (by design never compared); hints dropped
(asserts, function ensures, lemmas) whose absence is a kernel UNPROVED and
is logged per drop so it can be attributed; and Dafny's own soundness in
the checker (the same trust the dafny column already extends).

## 12. Test plan: what the implementer writes first

In this order, each a `unittest` module under t/ with stdlib only, each
runnable on Windows (paths through pathlib, subprocess argument lists,
UTF-8 explicit):

1. `test_lift_parse.py`: the fixpoint test rprint(print(parse(rprint(f))))
   == rprint(f) on the 77 in-fragment files and on the 49 refusal samples
   (parse must succeed on all 126, printing the refused constructs too);
   then on all 785 (783 resolve). A precedence table test that parses
   prec.rp.dfy's clauses and reprints them identically.
2. `test_lift_refuse.py`: one fixture per refusal reason in section 5, each
   a five-line Dafny program, asserting the reason and the line; the census
   gap names as the expected strings.
3. `test_lift_rewrite.py`: one fixture per row of section 4 whose t output
   is written by hand in the test (fatorial.json and cube.json from this
   design are the first two, byte-compared as canonical JSON to the
   lifter's output), plus check_wf == [] on every emitted task and
   interp.Reference having >= 1 point.
4. `test_lift_check.py`: the checker file for fatorial2 verifies (12
   verified, 0 errors); the five negative controls each fail exactly one
   lemma; the differential harness reports bad=0 on Fatorial and Cube and
   bad>0 on a body with `i := i + 2`.
5. `test_lift_names.py`: every name in surface.KEYWORDS and every
   lowering's RESERVED set is renamed; `f` becomes `f_v`; `gcd'` becomes
   `gcd_p`; shadowed locals and bound variables are renamed; task names
   across the 785 stems are unique case-insensitively.
6. `test_lift_census.py`: the disagreement verdict rule on the 44
   disagreements the readers recorded (inventory.md section 3), asserting
   the verdict column.
7. Only then the corpus run, whose output is the table, checked against
   the numbers in section 13 and the readers' inventory.

## 13. Expected lift of the 77

Expected to pass check_wf: 77 of 77. Grounds: the readers' inventory
records a `lifts` or `lifts-with-rewrite` verdict for all 77 with the
rewrite named per file, and every named rewrite is a row of section 4;
two were lifted end to end here (fatorial2, Cube) and the readers' lift3/
and lifts/ directories hold ten more hand lifts that pass check_wf. No
program among the 77 triggers a refusal row of section 5: zero returns 0,
multi-return 0, quantifiers 0, seqs 0, arrays 0, div/mod 0, early exits 0
(18 returns, all tail), assumes 0, lemma calls 0, other-method calls 0,
uninitialised locals 2 (Square.dfy, hoangkim.dfy, both first assigned at
the same block level), loops without decreases 24 (all with an rprint
measure), tuple measures 2 (SlowMax loop `x, y` and the Potencia-shaped
function defaults, all projectable or summable), functions with requires
8 (totalised), `'` names 2 (both in unreachable declarations).

Expected NOT to count, though lifted, with the reason and the file:

- twin refused `no-operator` (measured by the readers): 234.dfy (`volume
  := size * size * size;`), 626.dfy.
- twin UNPROVED in dafny because the witness is a preservation witness and
  lower_dafny emits no certificate for that kind (lower_dafny.py section
  comment): dafny-programs factorial.dfy, t1_MF ex4.dfy (readers,
  measured), and fatorial2 here (twin `invariant-drop#1`, preservation at
  n=0, i=0, f=0, dafny UNPROVED, measured). This is a kernel-adapter gap,
  not a lifter one, and is a distinct column.
- real expected UNPROVED in every kernel for the nat-return clause
  (section 7): climbing-stairs.dfy, Invariantes_fibonacci.dfy, uiowa
  fibonacci.dfy, appeal_20_p4.dfy. Not measured; the expectation is
  from reading the proof dependency (the return's value equals a nat
  function's value) and is the first thing the corpus run will confirm or
  refute.
- kernel abstentions on valid t (not lifter refusals): fstar/rocq on
  uiowa fibonacci (loop under a conditional) and TuringFactorial (nested
  loops); lean on the 4 bool-returning tasks and on the 2 else-less ifs
  (A8_Q2, 801) per its NotImplementedError messages.
- dafny-only proofs (readers, measured): Generated_Code_Mult.dfy and
  A8_Q1.dfy verify in dafny through Boogie's interval inference and its
  free `decreases <= decreases at entry` invariant, facts no other kernel
  has; expected VERIFIED in dafny and UNPROVED elsewhere.

Expected to refuse among the 77: none. If the corpus run refuses one, the
refusal reason and line are the finding, and it is checked against this
list.

## 14. Where it breaks

- The checker is Dafny. A lemma Dafny cannot prove (nonlinear arithmetic
  in an invariant, a spec_fun equivalence that needs a lemma beyond
  auto-induction) is a REFUSED lift even when the lift is right. Section 9
  measured four function lemmas and three programs' contract lemmas
  proved unaided; the corpus will find the ones that are not, and each
  such row is `lift-check-failed` and costs one row, never a wrong count.
  A hand-written hint is not allowed in the checker (it would be a proof
  the lifter wrote about itself); the row stays refused.
- Body fidelity is bounded and partial (section 10). A body that differs
  only outside interp's domain, or only in a ghost annotation the lemmas
  do not cover (a decreases guess), passes.
- The totalised spec_fun differs from the source outside the domain, and a
  TWIN can reach there. The twin then has a value where the source's twin
  had none; which twins refute can differ from a hand-written task's. The
  rung is recorded; the meaning of COUNTS is unchanged.
- nat results of functions are lost (section 7), so about four of the 77
  are expected to lift and not verify anywhere. Open decision 15.3.
- Every hint is dropped (asserts, function ensures, lemmas). Kernels that
  needed them read UNPROVED; the sidecar attributes it, the count does not
  recover it.
- Reads of `--rprint` depend on Dafny 4.11.0's printer. A Dafny upgrade
  can change the print (attribute spelling, clause order, the ite measure
  shape); the fixpoint test and the pinned binary are the guard, and the
  design is not portable to another verifier's front end.
- For-loops, read-only arrays, `x in s`, two-binder quantifiers and
  inclusive ranges are rows of section 4 that zero of the 77 exercise; on
  the 102 sole-gap programs and the rest of the 643 they matter, and their
  meaning arguments are checked by the lemmas per program, but none was
  measured here.
- The lifter's parser is the largest new trusted component. The fixpoint
  test bounds it (a misparse that reprints identically is the residual
  risk), and the refusal-on-unknown-token rule means the parser fails
  closed.

## 15. Open decisions (Treston's, not the lifter's)

1. Read-only `array<int>` params -> `seq`? Default: NO (refuse `array`),
   because `a.Length`/`a[i]` reads are meaning-equivalent to `len`/`at`
   but the type is not, and the readers count 10 such programs (36 are
   sole-gap `array`). If reversed: a rewrite row `array-param-readonly`
   with the condition "no `modifies`, no element assignment, no `new` in
   the method's closure", verified by the contract lemma through a seq
   view; the census's 77 becomes larger and the row must carry the label.
2. `x in s` desugared to a bounded exists? Default: YES (a rewrite verified
   per program by the lemma). If reversed: refuse `seq-membership`; 0 of
   the 77 and 6 of the 49 samples are affected.
3. nat return adds `ensures r >= 0`? Default: YES (the source's theorem).
   If reversed: the lifted theorem is weaker than the source's on every
   nat-returning method (25 of the 77), the four programs in section 13
   likely verify, and the table must label every nat-return row "type
   clause dropped".
4. nat local adds `invariant v >= 0`? Default: YES (it is the obligation
   Dafny proved, relocated). If reversed: the lifts of potencia-shaped
   loops fail in every kernel (the exit case `e <= 0` does not give `e ==
   0`), so the reversal is a coverage decision, not a meaning one.
5. Split a top-level `&&` in one clause into several clauses? Default: NO
   (mirror the source; one Dafny clause = one t clause). If reversed:
   INVARIANT-DROP gains sites (mockExam2_p6's single four-conjunct
   invariant becomes four), which changes the selected twin on 27
   programs; meaning is unchanged.
6. `requires true` -> `[{"bool": true}]` or `[]`? Default: the literal
   (mirror). Reversal changes nothing measurable.
7. Emit `"t": 1` always, or `"t": 0` when the task fits v0? Default: always
   1 (a superset; lower_verus/lower_rocq refuse some v0 bodies). Reversal
   makes the v0 tasks byte-comparable to the committed ones.
8. A measure guess (sum of tuple components) for spec_funs and loops?
   Default: YES, because a wrong measure cannot corrupt and the kernel
   checks it; recorded as `guess:sum`. If reversed: refuse
   `lexicographic-decreases`, losing SlowMax and the two gcd programs.
9. Drop asserts silently or refuse `assert-in-body`? Default: drop and log
   (SYNTAX.md calls them hints). If reversed: 8 of the 77 are refused.
10. Multi-method files: one candidate per gradable method (default) or
    refuse `multi-method` like the census? The default reports both
    granularities; reversal collapses to the census's file count.
11. The differential run's domain: interp's (default, so twin and
    fidelity share it) or a larger sampled one. Cost scales linearly with
    points at ~0.1 ms each after the 4 s compile.
12. Whether a `lift-check-failed` row may be retried with a bounded set of
    mechanical hints (calling every `L_fun_*` lemma, `{:induction}` on the
    lemma). Default: NO; the checker never argues for the lifter.

## 16. Experiments run (commands and results)

All in <scratch>/lifter/design/vl/, with `export PATH=$HOME/.local/dafny:$PATH`, every dafny call under `timeout 120`.

1. `dafny resolve X.dfy --rprint:X.rp.dfy` on cube, sqrt, maximum, mult,
   potencia, iseven, fat: 0.48 to 0.53 s each; iseven exits 2
   ("Compilation failed because warnings were found and --allow-warnings
   is false", four deprecated semicolons) and still writes the rprint;
   with `--allow-warnings` exit 0. Findings: inferred loop measures `n -
   i`, `m - 0`, `if i <= n then n - i else i - n`, `N - (r + 1) * (r +
   1)`, `|values| - idx`; inferred function measures `decreases n`,
   `decreases x, y`; method-level `decreases` on every method; `var i:
   int`, `var b: nat` typed locals; `{:trigger ...}` on quantifiers; the
   range syntax `| 0 <= i < |values| ::` preserved; `for` preserved with no
   decreases; `break` preserved; parallel assignment preserved; `return`
   preserved; chains preserved.
2. rprint fixpoint: the declarations of fat.rp.dfy written as fat.body1.dfy,
   resolved with --rprint, declarations extracted again: `diff` empty.
3. prec.dfy resolved with --rprint: the precedence table of section 3.
4. noguard.dfy `dafny verify`: "decreases expression must be bounded below
   by 0", exit 4. guard.dfy: "1 verified, 0 errors".
5. `python3 drive.py fatorial.json fatorial`: check_wf ok; interp 41
   points (values 1, 1, 2, 6, 24, 120, 720, 5040 at n = 0..7); twin
   invariant-drop#1, preservation at n=0, i=0, f=0; verifiers.dafny: real
   VERIFIED, twin UNPROVED.
6. `dafny verify eq_fat.dfy`: 10 verified, 2 errors (L_ens, L_inv_0).
   `dafny verify eq_fat2.dfy` (forall-statement hint added to those two
   lemmas): 12 verified, 0 errors, 1.16 s.
7. `dafny verify neg1..neg5.dfy`: each "a postcondition could not be
   proved on this return path" on its one lemma; 3 verified 1 error (neg1,
   neg2, neg3, neg5), 1 verified 1 error (neg4).
8. `dafny verify eq_even.dfy`: 13 verified, 0 errors, 1.15 s (function
   with requires, `<==>` ensures and invariant, `!r` body).
9. `dafny verify eq_gcdpot.dfy`: 8 verified, 0 errors, 1.08 s (gcd with
   guard and `decreases (x + y)`, Potencia with guard and `decreases y`,
   both equivalence lemmas). `dafny resolve gcd.dfy --rprint`: `decreases
   x, y` inferred on gcd, method-level `decreases m, n`.
10. `python3 drive.py cube.json cube`: check_wf ok; 41 points; twin
    invariant-drop#2, exit at n=0, i=0, k=1, m=6, c=1; real VERIFIED,
    twin REFUTED (certificate accepted). `dafny verify eq_cube.dfy`: 7
    verified, 0 errors, 1.08 s. `dafny run eq_cube.dfy --no-verify`:
    points=41 bad=0, 3.9 s.
11. `dafny run runprobe.dfy` and `diff_fat.dfy --no-verify`: bad=0, 2.8 to
    4.5 s (compile plus run).
12. noguess.dfy (`while b`): "cannot prove termination; try supplying a
    decreases clause for the loop"; its rprint has no loop decreases.
    forloop.dfy: verifies; rprint keeps `for i: int := 0 to n`, no
    decreases.
13. shadow.dfy: `var n := 5;` under parameter `n` resolves (the only error
    is the postcondition); a bound variable `i` under parameter `i`
    resolves.
14. rp_all.sh: `dafny resolve F --allow-warnings --rprint:...` over all
    785 corpus files, 4 in parallel: 783 exit 0, 2 exit 2 (groupTheory
    assignment1: "can't use parenthesis when hiding or revealing";
    ACL2-extractor: "type parameter (T) passed to function xtr must be
    nonempty"). Over the 785 rprints: 656 while loops, 656 with a
    decreases line, 63 ite-shaped; 473 files with `{:trigger`; 101 with
    `for`; among the 77 in-fragment: 41 loops, 14 nat-typed locals, 73
    method-level decreases, 0 for-loops, 0 triggers.
15. Corpus stems: `ls | tr A-Z a-z | sort | uniq -d` empty; 93 file names
    contain a space; one contains non-ASCII.
16. census.json over the 77: nat 30, iff 5, parallel-assign 9, assert 8,
    main-harness 2, if-no-else 1 (a known detector fault: A8_Q2 and 801
    both have one), while-no-decreases 23, function-or-predicate 28,
    untyped-var 33, trailing-return 14, no-if-no-loop 24, ghost 6.

## 17. Corpus lines this design rests on

- Clover_abs.dfy 6, 8: `return -x;` / `return x;` (tail returns in the final if).
- Cube.dfy 8: `while i != n` (no decreases; rprint gives the ite); 14: `c, k, m := c + k, k + m, m + 6;`.
- Invariantes_fatorial2.dfy 1: `function Fat(n:nat):nat`; 13: `invariant 1 <= i <= n+1`; 19: `return f;`.
- IsEven_success_1.dfy 1-2: `function even(n: int): bool requires n >= 0`; 9: `ensures r <==> even(n);`; 18: `r := !r;`.
- Invariantes_potencia.dfy 6-11: `function Potencia(x:nat, y:nat):nat` with no decreases (rprint: `decreases x, y`); 18: `var b := x;` (rprint: `var b: nat := x;`).
- ex06-solution.dfy 1-2: `ghost function gcd(x:int,y:int):int requires x > 0 && y > 0`; 17: `decreases x+y`; 25-27: `gcd'` with `decreases x+y,y`, unreachable.
- SlowMax.dfy 12: `while (z < x && z < y)`; 17: `decreases x,y;`.
- Generated_Code_15.dfy 1: `method main(n: int, k: int) returns (k_out: int)`.
- Square.dfy 5-6: `var x: int; var i: int;`.
- ex_06_hoangkim.dfy 16: `var x: int;`; 43: `else gcd(y, x)` (gcd' calls gcd; not mutual).
- climbing-stairs.dfy 9: `var a, b := 1, 1;`; 16: `a, b := b, a + b;`; 12: `invariant i <= n || i == 1`.
- tutorial_maximum.dfy 9: `requires values != []`; 10: `ensures max in values`; 11: `forall i | 0 <= i < |values| :: values[i] <= max`.
- task_id_414.dfy 5: `for i := 0 to |seq1|`; 11: `break;`.
- task_id_803.dfy 4: `forall a: int :: 0 < a*a < n ==> a*a != n`.
- strings1.dfy 1: `predicate isPrefixPredicate(pre: string, str:string)`; 11: `{return false;}`.
- aula2.dfy 32: `var aux := mystery1 (n-1,m);`; 45: `var aux2 := mystery1(m,aux);`; 55-57: `if (x > 0 && y > 0 && y > x) { z := x-1; }`.
- product_details.dfy 8: `m1, res := *, *;`; 9: `assume res == (m-m1)*n;`.
- lab7_question5.dfy 3: `decreases x < 0, x`; 12: `r:= A1(r, y);`.
- extra_sum.dfy 12-14: `var x:nat := 0;` etc.; 20-34: asserts.
- task_id_801.dfy 2: `ensures count >= 0 && count <= 3`; 8-10: `if (a == b) { count := count + 1; }`.
- task_id_762.dfy 3: `ensures result <==> month == 4 || month == 6 || month == 9 || month == 11`.
- A8_Q2.dfy 5: `requires true;`; 27: `if (x<y){ m := x; }`.
- mockExam2_p6.dfy 6: `ghost function f(n: int): int`; 24: one invariant with four conjuncts.
- se2011 ass1_ex4.dfy 14: `return z;` (a local).
- cs245 power.dfy 5-7: `function power(a: int, n: int): int requires 0 <= a && 0 <= n; decreases n;`.
- expt.dfy 22: `lemma {:induction a} distributive(x: int, a: nat, b: nat)` bodyless, unreachable.

## 18. Grafts from the other three designs

Each item names the design it comes from (`t/lifter-design/`). They add to
the sections above; none replaces a rule.

### 18.1 Exit-code discipline for the Dafny front end (two-stage-generic, stage 0)

Every file gets three invocations, each under a wall timeout, each recording
its exit code and stdout: `dafny resolve FILE --allow-warnings --rprint:OUT`,
`dafny resolve FILE --allow-warnings --print:OUT2` (kept beside the record so
a row can quote what the author wrote), and `dafny verify FILE
--allow-warnings` for the source verdict (exit 0 or 4, decision 12). Measured
by two of the designs: without `--allow-warnings`, 257 of 785 files exit 2 on
warnings alone (255 deprecated-style, 2 real errors); with it, exit 2 is an
error. The rprint file is still written on a type error, so the exit code is
read BEFORE the rprint is opened, and a nonzero exit is `dafny-resolve-error`
carrying Dafny's first `Error:` line; the rprint is never parsed. Warnings
are recorded in the sidecar and ignored.

### 18.2 The rewrite vocabulary and the expected disagreement classes (dafny-print-normalised)

The sidecar's rewrite list uses one name per rule, so the disagreement table
and the decisions file can be joined by name. The names, with the decision
row that governs each where one exists: `split-conjuncts` (10),
`chain-desugared`, `iff-to-eq`, `in-desugared` (2), `nat-param-guard`,
`nat-return-ensures` (4), `nat-invariant-added` (5), `spec-fun-totalised`
(6), `decreases-inferred`, `decreases-tuple-reduced` and `guess:sum` (11),
`parallel-assign-temps`, `tail-return`, `default-init` (13),
`for-desugared` (15), `array-readonly-as-seq` (1), `assert-dropped` with a
count, `lemma-call-dropped`, `function-ensures-dropped`,
`unused-function-dropped`, `main-dropped` (8), `source-unverified` (12).
Decreases origin per loop and spec_fun stays as section 8 has it: `stated`,
`rprint-inferred`, `projected`, `guess:sum`.

The verdict rule of section 8 is kept as written (`lifter`, `census`,
`undecided`, `gap-name`, `agree`). The inventory's 49 refusal samples give
the classes to expect, and the first 785 run checks this prediction: 12 lift
with a rewrite the census calls a gap (read-only array, `values != []`, `x
in s`, for-loop, string seen only through `|s|`, early return rewritable to
if/else; under the decisions file the first, third and fourth lift, the
others refuse), 6 are policy rows, 30 refuse with the census's own name, 9
refuse with a reason the census has no name for (function contracts, trait,
class, not gradable).

### 18.3 The checker mutation test (two-stage-generic, T7)

Section 9 measured that three deliberately wrong lifts fail their lemmas
(neg2, neg3, neg4). That becomes a standing test: `test_lifter.py` carries a
list of seeded lifter faults, each a small function that corrupts a correct
task in one way (an `<==>` read as `==>`, a parallel assignment sequenced,
an ensures conjunct dropped, a quantifier bound widened by one, a negative
literal read as positive, a totalisation default reached on the domain, a
loop guard negated, an invariant dropped), and asserts that section 9's
lemmas or section 10's differential run catch every one. The count caught
over the count seeded is printed with the corpus numbers, so that "0 wrong
lifts over 785" is a measurement of the checker, not silence.

### 18.4 The inverse test against lower_dafny (dafny-print-normalised 11.1, two-stage-generic T3 and T4)

For the 11 committed tasks in `t/tasks/` and a fuzz corpus from
`fuzz_lower.build_corpus` (fuzz_lower.py): `lift(rprint(lower_dafny.lower(
task, task["body"])))` must equal `task` as canonical JSON after three
documented asymmetries are normalised, and any other difference is a lifter
fault. The asymmetries: lower_dafny capitalises the method name and the
sanitiser lowercases the initial, so names that start lowercase round-trip
exactly; lower_dafny hoists a body self-call into `var t0 := Method(args);`,
which lifts back as a local initialised with a call, so the recursive tasks
are compared by interp on the domain rather than by JSON; and nested binary
`and`/`or` nodes flatten to one n-ary node. What the test catches: any
asymmetry between reading and writing an operator, a quantifier range, an
`ite`, an n-ary connective, a negative literal, an invariant order, a
decreases. What it cannot catch: what both files get wrong the same way, and
rules with no lower_dafny counterpart (nat, chains, parallel assignment,
tail return, totalisation), which sections 9 and 10 cover.

### 18.5 The reference interpreter as an independent third arm (recursive-descent 14.2, two-stage-generic 9)

Section 10(a) runs the source and the lowered lift side by side under
`dafny run` and compares values. Both arms are Dafny; neither exercises
`interp.py`, which is the interpreter the twin's witness search and the
`ground_truth` fuzz use. So the same Main also prints the source's value at
every point, and `lift_check.py` compares those to `interp.Reference` on the
lifted task point by point (measured by recursive-descent on Cube: 3 s, 7 of
7 equal). A mismatch here with 10(a) passing points at interp or at the
lowering, not at the lift, and is reported as `interp-disagreement` with the
input, never folded into `lift-diff-failed`. Programs whose source cannot be
compiled (a ghost method) skip this arm and the sidecar says
`arm-unavailable`.

### 18.6 The read-only array row, switched on (two-stage-generic section 4)

Decision 1 turns section 15 item 1 on. The row, as two-stage-generic states
it: an `array<int>` parameter lifts to `seq` when the method has no
`modifies` clause, no element assignment, no `new`, and no call that passes
the array, anywhere in the method's closure; functions over it may `reads`
it. `a.Length` is `len(a)`, `a[i]` is `at(a, i)` with the same definedness. A
never-written array parameter is observationally the sequence of its
elements, so the value view is exact; the type is not, and the sidecar
records `array-readonly-as-seq` so the row carries the label. `array<nat>`
adds the `nat-elements-requires` clause; `array<bool>`, `array<T>` otherwise,
`array2` and local arrays stay refused `array`. The refusal table of
section 5 narrows accordingly: `array` fires only when the condition fails,
and `array-mutation` on `a[i] := e`, `new` or a `modifies` naming the array.
None of the 77 exercises this row; the 36 sole-gap programs of the 785 do,
and the contract lemma of section 9 verifies the rewrite on each.
