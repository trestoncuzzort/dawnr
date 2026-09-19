# Dafny to t lifter: strategy two-stage-generic

Design only (ROADMAP.md 12.4). Nothing below is implemented. Every statement
about what Dafny 4.11.0 does was measured with the installed binary
(`$HOME/.local/dafny/dafny`), and the command and result are in
section 15. Every statement about a corpus program quotes the line it rests
on (section 14). Where a rule rests on a semantic choice that is Treston's
to make, the rule names its default and section 16 lists the reversal.

## 0. Summary

The lifter is three stages behind a Dafny front end that we do not write.

- Stage 0 runs `dafny resolve` twice on the source, once with `--print`
  (the parsed program, no inference) and once with `--rprint` (the resolved
  program: every local and binder typed, every loop and function carrying
  the decreases Dafny inferred), and `dafny verify --allow-warnings` once
  for the source's own verdict. All three are recorded.
- Stage 1 is a tokenizer and recursive-descent parser over Dafny's printed
  form into a GENERIC Dafny AST that represents what the corpus contains,
  including everything t lacks: arrays, div and mod, sets, maps, slices,
  literals, early return, multiple returns, parallel assignment, for
  loops, match, classes and modules as opaque declarations. The parser
  never decides fragment membership.
- Stage 2 selects the gradable method, types every node from the rprint
  annotations, and maps node by node to t. It refuses by AST NODE KIND with
  a named reason, applies exactly the rewrites listed in section 4 (each
  recorded by name in a provenance sidecar), infers a decreases clause only
  by a fixed candidate ladder checked against Dafny, and renames identifiers
  by one deterministic rule with the map recorded.
- Stage 3 is a differential check with two arms. Arm A: a small evaluator
  of the generic Dafny AST run over interp.py's own bounded domain for the
  lifted task, compared point by point with interp.py's reading of the
  lifted task on requires, on the return value and on ensures. Arm B:
  `dafny run --no-verify` of the SOURCE method on the same points, which is
  an evaluator nobody on this project wrote. A disagreement on any point
  rejects the lift with `differential-mismatch`.
- Stage 4 emits the task JSON, runs `fuzz_lower.check_wf`, builds
  `interp.Reference`, records the twin rung `harness.twin_for` selects, and
  joins the per-file provenance with `census.json` into the disagreement
  table with a verdict per row.

The one rule everything else follows: a rewrite is admitted only when the
lifted theorem is provably EQUAL to the source theorem on every input that
satisfies the lifted requires, or STRONGER. Weaker is never admitted, not
even recorded-weaker, because a weaker lift can count where the source
would not have, and that corrupts the number silently. A stronger lift
can only fail to verify, and a failed real cell is a visible row, not a
corrupted count.

## 1. What the lifter replaces and what it may not do

`coverage_census.py` decides membership with regular expressions and
records a gap SET per file. The lifter decides membership by producing a
task, and it records a refusal SET per file (every reason, never only the
first) so that the two instruments can be joined reason by reason. The
census's gap names are the vocabulary of that join; section 5 reuses them
wherever the construct is the same thing and adds lifter-specific names
where the census had no concept (a parse failure, an uninferable measure,
a function with a requires, a name that cannot be sanitised, a seq
concatenation the census cannot see).

The lifter may not: guess a construct from a token (every decision is on a
typed AST node), invent an annotation the source does not carry except the
ones that make an implicit Dafny fact explicit (section 7 says exactly
which), pick a decreases measure it has not checked, or emit a task whose
two evaluations disagree.

## 2. Architecture

```
source.dfy
   |
   |  Stage 0 (Dafny as front end; nothing decided here)
   |    dafny resolve --allow-warnings --print:P.dfy   source.dfy   -> exit, P
   |    dafny resolve --allow-warnings --rprint:R.dfy  source.dfy   -> exit, R
   |    dafny verify  --allow-warnings                 source.dfy   -> exit 0/4, verdict text
   v
tokens(P), tokens(R)
   |
   |  Stage 1 (parse; may decide only "is this Dafny I can read")
   |    GenericAST(P), GenericAST(R); the two are aligned declaration by
   |    declaration and statement by statement; R supplies types and the
   |    inferred clauses, P says what the author wrote
   v
GenericAST + inference marks
   |
   |  Stage 2 (select, type, map; decides membership, by node kind)
   |    2a select: the gradable method(s); drop Main, lemmas, unused functions
   |    2b type:   every expression node gets int|bool|seq|OTHER(kind)
   |    2c refuse: any OTHER-typed node, any statement kind outside 4.3
   |    2d rewrite: exactly the rows of section 4, each appended to `rewrites`
   |    2e decreases: stated, else the candidate ladder of section 6
   |    2f rename: section 8, map appended to `renames`
   v
task.json (candidate) + provenance.json
   |
   |  Stage 3 (check; may only REJECT, never repair)
   |    3a fuzz_lower.check_wf(task) == []
   |    3b interp.Reference(task): n_req > 0 and points non-empty, else tag
   |    3c Arm A: DafnyEval(GenericAST) vs interp.ev/exec_body on every point
   |    3d Arm B: dafny run --no-verify of a generated Main over the same points
   |    3e lower_X.lower(task, body) for every X in the seven, text only:
   |        a NotImplementedError naming an identifier -> rename and retry once;
   |        any other abstention is recorded as the lowering's, not the lifter's
   v
task.json (final) + provenance.json
   |
   |  Stage 4 (report)
   |    harness.twin_for(task) -> rung, witness or refusal, recorded
   |    join with census.json -> disagreement table, verdict per row
```

What each stage may and may not decide, stated once:

- Stage 0 decides nothing. It records three exit codes and three texts.
  Exit 2 from `resolve` WITH `--allow-warnings` is an error and the file is
  refused `dafny-resolve-error` (measured: without the flag, deprecated
  semicolons alone give exit 2, and the rprint file is still written on a
  type error, so an exit code must be read before an rprint is opened;
  section 15, E3 and E12).
- Stage 1 decides only whether the printed program is in the grammar of
  section 3. A construct outside the grammar is a `parse-failure` with the
  offending token and line; it is a lifter defect to be fixed, never a
  fragment verdict, and the test plan keeps it at zero over the 785.
- Stage 2 decides membership and nothing about truth. It never runs a
  kernel except through the decreases candidate ladder, where Dafny is asked
  to confirm a measure for a probe that is the SOURCE method plus one
  clause; a measure Dafny rejects is still emitted when it is the only
  candidate, tagged `decreases-unproved`, because a wrong measure makes the
  real cell fail visibly and a right one Dafny could not prove may be
  proved elsewhere.
- Stage 3 may only reject. It never patches a task to make the arms agree.
- Stage 4 reports. The twin rung is recorded because the inventory shows
  rewrites move it (hazard 3), and a coverage number that hides the rung
  hides the discipline.

Modules (Python 3.12 standard library only; every path a `pathlib.Path`;
every subprocess flag in `--flag=value` or `--flag value` form as the
harness already uses; text read with `encoding="utf-8"`, `newline=""` and
written with `newline="\n"`, per RUN-ON-WINDOWS.md):

```
t/lift/dfy_front.py    stage 0: the three dafny invocations, exit-code discipline
t/lift/dfy_lex.py      tokenizer over Dafny's printed form
t/lift/dfy_ast.py      the generic AST dataclasses (section 3)
t/lift/dfy_parse.py    recursive descent, precedence table, chain nodes
t/lift/dfy_types.py    type reconstruction from rprint annotations
t/lift/select.py       gradable method(s), Main, lemmas, unused functions
t/lift/rewrite.py      the section 4 rewrites, one function per row
t/lift/measure.py      section 6 decreases ladder and the dafny probe
t/lift/names.py        section 8 rename rule and the reserved union
t/lift/to_t.py         node-by-node mapping to task JSON
t/lift/dfy_eval.py     stage 3 arm A evaluator of the generic AST
t/lift/dfy_run.py      stage 3 arm B: generate Main, dafny run, parse output
t/lift/report.py       provenance sidecar and the census join
t/lift/lifter.py       driver: one file or the whole corpus
```

`dfy_eval.py` imports nothing from `interp.py`; it evaluates the Dafny AST.
The comparison code in `lifter.py` calls both. Section 9 says why the
independence is partial and what closes the gap.

## 3. What is parsed

The parser reads Dafny's own printed form (rprint and print), never the raw
source. Measured (E5, E9): rprint keeps every statement shape of the corpus
verbatim (if without else, else-if chains, bare `return`, `return e`,
`assert`, `assume`, `calc`, method-call statements, `x in s`, slices,
`old(r)`, functional update, parallel assignment, multi-name `var`, for
loops) and adds what a parser cannot know: types on every local (`var m:
int := x` where the author wrote `var m := x` with `x: nat`), types on
every binder (`forall i: int ::`), and the inferred `decreases` clauses.
Comments are gone, so the comment-aware masking the census needed is not
needed here. The user program begins at the first column-0 declaration
after the `module _System { ... }` preamble (measured: 125 lines on E9's
probe), which is the same walk `verifiers/dafny.py` already performs.

```ebnf
Program     ::= Decl*
Decl        ::= Method | Function | Lemma | Module | Opaque
Module      ::= "module" Id "{" Decl* "}"                       (* unwrapped in 4.6 when no Import *)
Opaque      ::= ("class"|"trait"|"datatype"|"codatatype"|"newtype"|"type"
                |"const"|"iterator"|"import"|"export"|"include") ... balanced ; (* kind + name kept, body skipped *)
Method      ::= Mods "method" Id TypeParams? Formals ("returns" Formals)? Spec* (Block | ";")
Lemma       ::= Mods ("lemma"|"twostate lemma"|"least lemma"|"greatest lemma") Id ... (Block | ";")
Function    ::= Mods ("function"|"predicate"|"twostate function"|"least predicate"|"greatest predicate")
                ("method")? Id TypeParams? Formals (":" Type)? Spec* ("{" Expr "}" ("by method" Block)? | ";")
Mods        ::= ("ghost"|"static"|"opaque"|"abstract"|Attribute)*
Attribute   ::= "{:" Id Expr* "}"
Formals     ::= "(" (Formal ("," Formal)*)? ")"
Formal      ::= ("ghost")? Id ":" Type
Spec        ::= "requires" Label? Expr | "ensures" Expr | "decreases" Expr ("," Expr)* | "decreases" "*"
              | "modifies" Expr ("," Expr)* | "reads" Expr ("," Expr)* | "invariant" Expr
Type        ::= "int" | "nat" | "bool" | "real" | "char" | "string" | "ORDINAL"
              | ("seq"|"set"|"iset"|"multiset") "<" Type ">" | ("map"|"imap") "<" Type "," Type ">"
              | "array" Digits? "<" Type ">" | "bv" Digits | "(" Type ("," Type)* ")"
              | Type ("->"|"-->"|"~>") Type | Id ("<" Type ("," Type)* ">")? | Type "?"
Block       ::= "{" Stmt* "}"
Stmt        ::= Lhs ("," Lhs)* ":=" Rhs ("," Rhs)* ";"                  (* parallel when >1 *)
              | Lhs ":|" ("assume")? Expr ";"                            (* such-that *)
              | "var" VarDecl ("," VarDecl)* (":=" Rhs ("," Rhs)*)? ";"  (* multi-name, optional init *)
              | "var" Pattern ":|" Expr ";"
              | "if" Guard Block ("else" (IfStmt | Block))?
              | "if" "{" ("case" Expr "=>" Stmt*)+ "}"                   (* guarded alternatives *)
              | "while" Guard Spec* Block?
              | "while" Spec* "{" ("case" Expr "=>" Stmt*)+ "}"
              | "for" Id (":" Type)? ":=" Expr ("to"|"downto") (Expr | "*") Spec* Block
              | "return" (Rhs ("," Rhs)*)? ";" | "yield" ... ";"
              | "break" (Id | "break"*)? ";" | "continue" Id? ";"
              | "assert" Attribute* Expr ("by" Block | ";") | "assume" Attribute* Expr ";"
              | "expect" Expr ("," Expr)? ";" | "print" Expr ("," Expr)* ";"
              | "reveal" Id ("," Id)* ";" | "calc" CalcOp? "{" (Expr ";" CalcOp? Block?)* "}"
              | "forall" Binders ("|" Expr)? Spec* Block?                (* forall statement *)
              | "match" Expr "{" ("case" Pattern "=>" Stmt*)* "}"
              | Label ":" Stmt | Block | Expr ";"                        (* method call statement *)
Guard       ::= Expr | "*" | "(" "*" ")"
Rhs         ::= Expr | "*" | "new" Type ("[" Expr ("," Expr)* "]")? ("(" Exprs? ")")? ("[" Exprs? "]")?
Lhs         ::= Id | Expr "[" Expr "]" | Expr "." Id
VarDecl     ::= ("ghost")? Id (":" Type)?

Expr        ::= Equiv
Equiv       ::= Implies ("<==>" Implies)*                                (* lowest; associative *)
Implies     ::= Or ("==>" Implies)? | Or ("<==" Or)*                     (* ==> right-assoc, <== left *)
Or          ::= And ("||" And)* ; And ::= Rel ("&&" Rel)*               (* no mixing without parens *)
Rel         ::= Add (RelOp Add)*                                          (* CHAIN node: all operands kept *)
RelOp       ::= "==" | "!=" | "<" | "<=" | ">" | ">=" | "in" | "!in" | "!!"
Add         ::= Mul (("+"|"-") Mul)* ; Mul ::= Unary (("*"|"/"|"%") Unary)*
Unary       ::= ("-"|"!") Unary | Postfix
Postfix     ::= Primary ( "[" Expr "]" | "[" Expr? ".." Expr? "]" | "[" Expr ":=" Expr "]"
                        | "(" Exprs? ")" | "." Id | "as" Type | "is" Type )*
Primary     ::= IntLit | RealLit | CharLit | StrLit | "true" | "false" | "null" | "this"
              | Id | "(" Expr ("," Expr)* ")" | "|" Expr "|"
              | "[" Exprs? "]" | "{" Exprs? "}" | "multiset" "{" Exprs? "}" | "map" "[" (Expr ":=" Expr)* "]"
              | "seq" "(" Expr "," Expr ")"
              | "if" Expr "then" Expr "else" Expr
              | ("forall"|"exists") Binders ("|" Expr)? "::" Expr
              | ("set"|"iset"|"map"|"imap") Binders ("|" Expr)? ("::" Expr)?
              | "var" Pattern ":=" Expr ";" Expr | "var" Pattern ":|" Expr ";" Expr
              | "match" Expr "{" ("case" Pattern "=>" Expr)* "}"
              | Binders "=>" Expr                                         (* lambda *)
              | "old" ("@" Id)? "(" Expr ")" | "fresh" "(" Expr ")" | "unchanged" "(" Exprs ")"
              | "assert" Expr ";" Expr | "calc" ... ";" Expr | "reveal" ... ";" Expr
Binders     ::= Id (":" Type)? ("," Id (":" Type)?)*
IntLit      ::= Digits ("_" Digits)* | "0x" Hex+
```

AST node kinds (the names stage 2 refuses by): `Method, Function, Lemma,
Module, Opaque(kind), Formal, TypeInt, TypeNat, TypeBool, TypeReal,
TypeChar, TypeString, TypeSeq, TypeSet, TypeMultiset, TypeMap, TypeArray,
TypeBv, TypeTuple, TypeArrow, TypeNamed, TypeNullable, Assign(lhs*, rhs*),
Havoc, SuchThat, VarDecl(names, types, inits?), If(guard|None, then,
else?), IfCases, While(guard|None, invs, decs, mods, body?), WhileCases,
For(var, lo, hi|None, down, invs, decs, body), Return(exprs), Yield, Break,
Continue, Assert(by?), Assume, Expect, Print, Reveal, Calc, ForallStmt,
MatchStmt, Label, Block, CallStmt, IntLit, RealLit, CharLit, StrLit,
BoolLit, Null, This, Var, Paren, Card, SeqDisplay, SetDisplay,
MultisetDisplay, MapDisplay, SeqComprehension, Ite, Quant(kind, binders,
range?, body), SetComprehension, MapComprehension, Let, MatchExpr, Lambda,
Old, Fresh, Unchanged, AssertExpr, Unary(op), Binary(op), Chain(operands,
ops), Index, Slice, Update, Call, Field, Cast, TypeTest`.

Two parser rules are load-bearing for meaning and are tested separately:

- A relational chain `0 <= i <= n` is ONE `Chain` node with three operands.
  A left-associative parse would type `(0 <= i) <= n` as bool <= int and
  the rprint reprints the chain unchanged (E1), so the parser must carry
  the chain and stage 2 splits it. 23 of the 77 have one (inventory).
- `==>` is right-associative and binds looser than `&&`/`||`; `<==>` is
  looser still. The test in section 11 (T2) uses Dafny's own printer as the
  oracle for this table: print our AST with every operator parenthesised,
  run `dafny resolve --print` on it, and require the text back equal to
  Dafny's print of the original; Dafny drops exactly the parentheses its
  own precedence makes redundant, so any misread association survives as
  a parenthesis and fails the comparison.

## 4. Mapping rules

Every row: Dafny construct, t construct, the condition under which the row
applies, and the meaning argument for why the kernels grade the same
theorem. "Recorded" means the rewrite name is appended to the provenance
sidecar for that task. Where a row is a policy default, section 16 has the
reversal.

### 4.1 Declarations

| Dafny | t | condition | meaning |
|---|---|---|---|
| `method M(params) returns (r: T) requires.. ensures.. { body }` | the task: `name`, `params`, `returns`, `requires`, `ensures`, `body` | exactly one return; T in {int, nat, bool}; every param int, nat, bool or (4.7) read-only seq/array; no `modifies` | one-to-one; the kernels grade the same contract over the same body |
| `method Main() {...}` | dropped | name is `Main` | a test harness states nothing a kernel grades about M; recorded `main-dropped` |
| a second method without ensures, never called | dropped | not called from any lifted body | its absence changes no theorem about M; recorded `extra-method-dropped` |
| a second method WITH ensures | its own task | the two do not call each other | each is one theorem; the file yields k tasks; the program is in fragment iff all k lift (default, 16.9) |
| `M2(...)` called in the body | refuse `method-call` | any CallStmt or call Rhs naming a method | t has no callee contract; the census names this `multi-method` |
| `lemma L(...) ... {...}` | dropped | always | a lemma is a proof hint (SYNTAX.md); recorded `lemma-dropped`, and a bodyless one is additionally recorded `axiom-dropped` because the source verdict rested on an assumption the kernels will not get |
| `L(args);` in the body | dropped | the callee is a lemma | no value flows; the theorem is unchanged and the proof is harder, which fails visibly; recorded `lemma-call-dropped` |
| `function f(p: int|nat|seq<int>): int|nat|bool [decreases..] { E }` | a spec_fun with int/seq params, int/bool result, `decreases` from section 6, body `E` lifted | f is reachable from M's contract, invariants or body; no `reads` except of a read-only array param (4.7); params typed as stated | the same recursive definition; the kernel discharges the same termination obligation |
| `ghost function`, `predicate`, `function method`, `function ... by method {..}` | as above | the `by method` block is dropped | ghost-ness and compilation strategy are not part of the function's meaning; recorded `by-method-dropped`; the census tags `function-method` as a gap, which the lifter disagrees with |
| a function not reachable from M | dropped | reachability over calls from M's requires, ensures, invariants, decreases, body | a spec_fun the theorem never mentions adds only obligations and lowering hazards (`gcd'` with its tuple decreases in ex06-solution); recorded `unused-function-dropped` |
| `function f(..) requires R { E }` | spec_fun with body `ite(R', E', default)` where R' is R's lift conjoined with `p >= 0` for each nat param, default `0` (int) or `false` (bool) | always (default totalize, 16.5) | f' equals f on Dom(f); every occurrence of f in the lifted task lies in Dom(f) because the source's well-formedness proof established it, so the theorem restricted to the requires-satisfying inputs is identical; the one loss is that call-site definedness obligations become vacuous, so a twin the source would have refuted through the WF channel must now be refuted through a value; recorded `function-requires-totalized`; measured E7, E10 |
| `function f(n: nat)` | spec_fun param `n: int`, body wrapped as above with `n >= 0` | always | measured E8: the naive lift fails `decreases expression must be bounded below by 0`; the wrap makes the wrapper guard the path condition at every self-call, which is exactly Dafny's knowledge there; recorded `nat-param-totalized` |
| `function f(..): nat` | result `int` | always | the source proved E >= 0 as a lemma; t has no place for it; recorded `function-result-nat-widened`; a kernel that needs it must re-derive it (visible) |
| `function f(..) ensures P` | ensures dropped | always | a function ensures is a lemma about f; recorded `function-ensures-dropped`; measured E8 (fact_a): its absence can make `ensures res >= 0` unprovable, which fails visibly |
| `function f(..) decreases a, b` (tuple) | section 6 candidate ladder | always | a single measure that Dafny confirms is a stronger termination statement, never weaker |
| functions calling each other in a cycle | refuse `mutual-recursion` | the call graph over reachable functions has a cycle of length > 1 | t admits self-calls and calls to EARLIER spec_funs only; otherwise topological order is emitted |
| `module X { decls }` with no `import`/`export`/`include` | unwrapped | one module, no imports | packaging around the same declarations; recorded `module-unwrapped` (census gap `module`, lifter disagrees) |
| `module` with imports, `include`, several modules | refuse `module` | | names cross files; nothing to grade in one task |
| `class`, `trait`, `this`, `new C(..)`, `fresh` | refuse `heap` | any Opaque(class/trait), This, Fresh, `new` of a class | |
| `datatype`, `match` | refuse `datatype` | | |
| `newtype`, `type` synonyms, subset types | refuse `type-decl` | | |
| `iterator` | refuse `iterator` | | |
| `print`, `expect` | refuse `io` | in a lifted body (inside Main they are dropped with Main) | |
| method or function generic `<T>` | refuse `generics` | | |
| bodyless method / bodyless function that is reachable | refuse `bodyless-method` / `bodyless-function` | | |
| `least predicate`, `greatest predicate` | refuse `extreme-predicate` | | |

### 4.2 Contracts

| Dafny | t | condition | meaning |
|---|---|---|---|
| `requires A && B` | two clauses `A`, `B` in order | top-level `&&` (after chain splitting) | Dafny checks clause k assuming clauses 1..k-1 and `&&` short-circuits left to right, so definedness and truth are identical; recorded `conjunct-split` (default split, 16.10) |
| `requires A` mentioning `f(..)` | clause with `call f` | f lifted | same function, same argument |
| `requires true` | `{"bool": true}` | | harmless; kept faithfully |
| `ensures A && B` | split as for requires | | same argument; the certificate lower_dafny builds is over the conjunction either way |
| nat param `p` | `requires p >= 0`, one clause per nat param, PREPENDED in parameter order before the author's requires | | Dafny knows the type fact before it reads the first requires, so a requires that is defined only under `p >= 0` stays defined; measured E13; recorded `nat-param-requires` (hazard 8: load-bearing, emit all) |
| nat return `r` | `ensures r >= 0` PREPENDED before the author's ensures | default (16.3) | Dafny establishes `r` is a nat at exit and every caller may rely on it; the first ensures is where that fact lives in t; measured E10, E13 with the type invariant of 4.4 |
| `old(e)` | `e` | e reads no heap (no array element, no field) | on values `old(e) == e`; recorded `old-erased`; with a heap read it is `heap` or `array-mutation` (110 programs carry `old`, the inventory found none among the 77) |
| `decreases` on a non-recursive method | dropped | body has no self-call | rprint stamps `decreases <params>` on every method (E1, E2, E4); check_wf rejects a task decreases without a self-call; recorded nothing (it is Dafny's, not the author's) |
| `decreases` on a self-recursive method | task `decreases` via section 6 | body self-calls | SPEC.md gate 3 requires it |

### 4.3 Statements

| Dafny | t | condition | meaning |
|---|---|---|---|
| `x := e;` | `{"assign": [x, e']}` | x is the return or a local | identical |
| `return e;` | `{"assign": [r, e']}` | the Return is in tail position: last statement of the body, or last statement of a branch of an `if` that is itself in tail position, recursively | nothing follows it on its path, so assigning and falling off the end is the same trace; Clover_abs.dfy lines 6 and 8 |
| `return r;` | dropped | tail position, the expression is the return variable itself | a no-op; FormalMethods Invariants_ex1 line 16 |
| `return;` | dropped | tail position | a no-op |
| `return e;` NOT in tail position, `break`, `continue`, labels | refuse `early-exit` | | t has no non-local exit; task_id_414 line 11 |
| `return e1, e2;`, `returns (a, b)` | refuse `multi-return` | | |
| `returns ()` | refuse `zero-returns` | | |
| `returns (s: seq<int>)` or any non-int/bool return | refuse `seq-return` (or the type's gap name) | | |
| `if c { S }` | `{"if": {"cond": c', "then": S', "else": []}}` | | identical |
| `if c1 {A} else if c2 {B} else {C}` | nested `if` in the else list | | Dafny's else-if IS a nested if |
| `if { case c1 => .. case c2 => .. }`, `if *`, `while *`, `x := *`, `x :| P` in compiled code | refuse `nondet` | | |
| `x :| P` on a ghost variable | refuse `ghost-such-that` | | the value is unconstrained and may flow into an invariant |
| `a, b := e1, e2;` | `var t0: T1 := e1'; var t1: T2 := e2'; a := t0; b := t1;` with fresh names | any parallel assignment whose right-hand sides read a target | Dafny evaluates all right-hand sides before any store; the temporaries reproduce that; measured E14 on Cube; recorded `parallel-assign-temporaries` |
| `a, b := e1, e2;` | `a := e1'; b := e2';` | no right-hand side reads any target (order-free) | stores commute when nothing reads them; recorded `parallel-assign-sequenced` |
| `var x := e;` (untyped) | `{"var": {"name": x, "type": T, "init": e'}}` with T from rprint | T is int or bool (nat -> int, 4.4) | rprint states the type Dafny inferred (`var m: int := x`, E2) |
| `var a, b, c := 0, 1, 2;` | three `var` statements in order | | Dafny binds left to right with no dependence between them |
| `var x: int;` (no initialiser) | `var x: int := 0` | x is definitely assigned before every read, which Dafny's own resolution already enforces for compiled locals | the 0 is unobservable on every path of the source; it is observable to a WRONG-VAR twin that reads x early, which is a twin-semantics shift, so recorded `uninit-local-zeroed`; Square.dfy lines 5 and 6 |
| `ghost var x ...` | an ordinary local | | t has no ghost; the value is the same; recorded `ghost-erased` |
| `while c invariant I* decreases D { S }` | `{"while": {"cond": c', "invariants": [I'*], "decreases": D', "body": S'}}` | D stated and int-typed | identical |
| `while c invariant I* { S }` (no decreases) | as above with D from section 6 | | t requires one; the inferred one is a stronger statement than "Dafny found some measure" only if it is the same measure, which the ladder checks |
| `invariant A && B` | ONE invariant clause | default (16.11) | the author's clause is the unit INVARIANT-DROP deletes; splitting would add rungs the author did not write |
| `for k := lo to hi invariant I* { S }` | `var k: int := lo'; while k < hi' invariant lo' <= k && k <= hi' invariant I'* decreases hi' - k { S'; k := k + 1 }` | body does not assign k (Dafny forbids) and no variable of `hi` is assigned in S; otherwise `hi` is first bound to a fresh local | Dafny evaluates `hi` once and knows `lo <= k <= hi` implicitly; measured E11: without the range invariant the desugared loop does not verify, with it it does; recorded `for-desugared` |
| `for k := hi downto lo` | mirror: `k := hi; while k > lo ... { k := k - 1; S }` | as above | the same reasoning; untested on the corpus (no in-fragment program has a for loop) |
| `for .. to *` | refuse `decreases-star` | | |
| `assert P;`, `assert P by {..}`, `calc {..}`, `reveal f;`, `forall x ... ensures ... {..}` statements | dropped | | proof hints; the theorem is unchanged; recorded `assert-dropped` etc. with a count; measured E10: Pow verifies without its seven asserts |
| `assume P;` | refuse `assume` | default (16.6) | an assumed fact makes the source's verdict not a verdict; dropping it would be sound-direction but the row belongs in the table as `assume`, not as a lift |
| `a[i] := e;`, `new int[n]`, `modifies a` with a write | refuse `array-mutation` | | |
| `match`, `yield`, `expect`, `print` | refuse `datatype`, `iterator`, `io` | | |
| a nested `while` | nested `while` | | t allows it (check_wf recurses); lean and rocq abstain, which is theirs to record (hazard 5) |
| `var` and `while` inside an `if` branch | as written | | check_wf scopes locals per branch; dafl fibonacci lines 28 to 43 |

### 4.4 Types

| Dafny | t | condition | meaning |
|---|---|---|---|
| `int` | `int` | | mathematical integers in both |
| `bool` | `bool` | return, local, expression; NOT a param of a spec_fun (t spec_fun params are int or seq) | a bool spec_fun param is refused `spec-fun-bool-param` |
| `nat` (param) | `int` + `requires p >= 0` | 4.2 | |
| `nat` (return) | `int` + `ensures r >= 0` + `invariant r >= 0` appended to every loop that assigns r | default (16.3, 16.4) | section 7 |
| `nat` (local) | `int` + `invariant v >= 0` appended to every loop that assigns v, unless an existing invariant conjunct is literally `0 <= v`, `v >= 0`, `0 < v`, `v > 0`, `1 <= v` or a chain beginning `0 <= v` | default (16.4) | section 7; measured E13 |
| `seq<int>` | `seq` | params of methods and functions only | SPEC.md gate 1 |
| `seq<nat>` | `seq` + `requires forall i in [0,len(s)). s[i] >= 0` | | the element type is a fact Dafny knew; recorded `nat-elements-requires` |
| `array<int>` param | `seq` | the method has no `modifies`, no element assignment, no `new`, no call passing the array; functions over it may `reads` it | a never-written array parameter is observationally the sequence of its elements; `a.Length` is `len(a)`, `a[i]` is `at(a, i)` with the same definedness; default lift (16.1); recorded `array-readonly-as-seq`; starter_ex12 and Clover_max_array |
| `array<nat>` param | as above + `nat-elements-requires` | as above | |
| `array<bool>`, `array<T>` otherwise, `array2`, local arrays | refuse `array` (or `nested-seq`) | | task_id_105 `array<bool>` |
| `seq<seq<int>>`, `seq<bool>`, `seq<T>` | refuse `nested-seq` | | |
| `string`, `char` | refuse `string-char` | default (16.13) | |
| `real` | refuse `real` | | |
| `set`, `iset`, `multiset` | refuse `set` | | task_id_142, task_id_455 |
| `map`, `imap` | refuse `map` | | |
| `bv*`, `&`, `^`, `<<` | refuse `bitvector` | | |
| tuples | refuse `tuple` | | |
| arrow types, lambdas | refuse `higher-order` | | |
| `x as int` where x is nat/int | `x` | | identity on values; recorded `cast-erased`; other casts refuse `as-cast` |

### 4.5 Expressions

| Dafny | t | condition | meaning |
|---|---|---|---|
| integer literal (decimal, `_`, `0x`) | `{"int": n}` | | |
| `-` applied to a literal | `{"int": -n}` | | lower_dafny prints `{"int": -1}` as `-1`; folding keeps the lifter the inverse of the lowering (linear_search.json) |
| `-e` otherwise | `neg` | | tasks/abs.json |
| `true`, `false` | `{"bool": ..}` | | |
| `x` | `{"var": x}` | x in scope after renaming | |
| `+ - *` | `+ - *` | int operands | |
| `/`, `%` | refuse `div-mod` | | SPEC.md refuses the syntax; kernels disagree on semantics |
| `== !=` | `== !=` | both int or both bool | |
| `== !=` on seqs | `len(s) == 0` / `len(s) != 0` when one side is `[]`; otherwise refuse `seq-equality` | | `s != []` is exactly `len(s) != 0`; tutorial_maximum line 9; recorded `empty-seq-comparison`; general seq equality has no t node (census has no name; lifter adds one) |
| `< <= > >=` | same | int operands | |
| `a <= b < c` (Chain) | `and(a <= b, b < c)` in operand order | | Dafny defines a chain as the conjunction; the middle operand is pure and its definedness is checked once by Dafny and twice with the same result by t's left-to-right `and`; recorded `chain-split` |
| `&&`, `\|\|` | n-ary `and`/`or`, a left-nested chain of the same operator flattened | | short-circuit left to right in both; recorded `nary-flattened` |
| `!` | `not` | | |
| `==>` | `implies` | | right-associative, section 3 |
| `<==` | `implies` with swapped arguments | | `a <== b` is `b ==> a` |
| `<==>` | `==` on bools | | SPEC.md: `==` applies to two bools; task_id_762 line 3 |
| `if c then a else b` | `ite` | branches of one type | |
| `\|s\|` | `len` | s a seq (or read-only array via `.Length`) | |
| `s[i]` | `at` | s a seq | defined iff `0 <= i < len(s)` in both |
| `a.Length`, `a[i]` on a read-only array | `len`, `at` | 4.4 | |
| `s[a..b]`, `s[..b]`, `s[a..]` | refuse `seq-slice` | | |
| `s[i := v]` | refuse `seq-update` | | |
| `s + t` on seqs | refuse `seq-concat` | typed seq operands | lifter-specific name: the census cannot see it (its report says so) |
| `[e, ..]` (non-empty display) | refuse `seq-literal` | | |
| `x in s`, `x !in s` (s a seq) | `exists j in [0, len(s)). s[j] == x` and its `not`, j fresh | default (16.2) | Dafny defines seq membership as existence of an index; recorded `membership-desugared`; tutorial_maximum line 10 |
| `in` on sets or maps | refuse `set` / `map` | | |
| `forall x: int :: R ==> B`, `forall x \| R :: B` | `forall x in [lo, hi). R'' implies B'` | R is a conjunction (chains split first) containing one conjunct of the form `lo <= x`, `x >= lo`, `lo < x` (lo+1), `x > lo` (lo+1) and one of `x < hi`, `hi > x`, `x <= hi` (hi+1), `hi >= x` (hi+1), each with x-free bounds; a `nat` binder supplies `0 <= x` when no other lower bound exists; R'' is the remaining conjuncts (absent when none) | the range is the same set of integers; the remaining conjuncts guard B exactly as in Dafny; recorded `quantifier-bounded`; task_id_803 line 3 gives `[0, n + 1)` |
| `exists x :: R && B` | `exists x in [lo, hi). R'' and B'` | same extraction | |
| `forall x, y :: R ==> B` | nested quantifiers, outer x, inner y | each variable's two bounds are found among conjuncts mentioning no LATER binder; a conjunct `x < y` becomes y's lower bound `x + 1` | the nesting is the same predicate; recorded `quantifier-nested` |
| quantifier with no such bounds, or a binder typed other than int/nat | refuse `unbounded-quantifier` | | task_id_803 line 4 ranges over `a*a`, not `a` |
| a binder name already in scope | renamed by section 8 | | SPEC.md: the bound variable may not shadow |
| `f(args)` where f is a lifted function | `call` | arity and types match | |
| `M(args)` self-call in a body assignment | `call` of the task's own name, task `decreases` from section 6 | strict position (not under ite branch, quantifier body, non-first and/or/implies argument) | SPEC.md gate 3; a lazy position is refused `self-call-lazy-position` |
| `var x := e; body` (let) | refuse `let-expression` | | rare; substitution is a later rewrite if wanted |
| `old(e)` | 4.2 | | |
| `fresh`, `unchanged`, `allocated`, `this`, `.field` | refuse `heap` | | |
| set/map displays and comprehensions, `multiset(..)` | refuse `set` / `map` | | |
| `seq(n, i => e)` | refuse `seq-comprehension` | | |
| real literal, `.` on numerics | refuse `real` | | |
| char and string literals | refuse `string-char` | | |
| `match` expression | refuse `datatype` | | |
| lambda | refuse `higher-order` | | |
| `assert P; e`, `calc ..; e`, `reveal ..; e` in expressions | `e` | | hints; recorded `assert-dropped` |

### 4.6 Whole-file rules

- Exactly the gradable methods are lifted; a file with none is
  `not-gradable` (the census's `method-with-ensures` false).
- A `module` wrapper with no imports is unwrapped (4.1).
- Deprecated semicolons, attributes on lemmas, and `{:induction}` are not
  constructs; they are absorbed by `--allow-warnings` and the attribute
  node is dropped with a count.
- The task's `"t"` is 0 iff every param and the return are int, and no
  bool literal, ite, quantifier, call, var or while appears; otherwise 1.
  `gate` is `recursion` when spec_funs or a self-call exist, else `loops`
  when a while exists, else `quantifiers` when a seq, quantifier or bool
  exists, else omitted.

## 5. Refusal rules

The lifter records EVERY reason that fires on a file, not the first, so
the join with `census.json` is set against set. Census names are reused
where the construct is the same thing; lifter-specific names are marked.

| reason | trigger (AST node kind or stage) | census equivalent |
|---|---|---|
| `dafny-resolve-error` | stage 0: `dafny resolve --allow-warnings` exit != 0 (parse or resolution error; the rprint file may exist and is not read) | none (the census read unresolvable files anyway) |
| `parse-failure` | stage 1: a token or production outside section 3; a lifter defect, held at zero by T1 | none |
| `not-gradable` | no method carries an ensures | `method-with-ensures` false |
| `array` | TypeArray anywhere except a read-only `array<int>`/`array<nat>` parameter (4.4) | `array` (the lifter disagrees on read-only params) |
| `array-mutation` | Assign with an Index lhs on an array; `new` of an array in a lifted body; `modifies` with a write | `array-mutation` |
| `div-mod` | Binary `/` or `%` | `div-mod` |
| `early-exit` | Return not in tail position; Break; Continue; Label | `early-exit` |
| `multi-return` | Method with > 1 return formal; Return with > 1 expression | `multi-return` |
| `zero-returns` | Method with no return formal | `zero-returns` |
| `method-call` | CallStmt or call Rhs whose callee is a method | `multi-method` (the census counts methods; the lifter refuses only calls) |
| `seq-slice`, `seq-update`, `seq-literal`, `seq-comprehension`, `nested-seq`, `seq-return` | Slice; Update; non-empty SeqDisplay (an `[]` compared for equality is rewritten, 4.5); SeqComprehension; TypeSeq of non-int; seq-typed return | same names |
| `seq-concat` (lifter-specific) | Binary `+` with seq-typed operands | none; the census report says it cannot see this |
| `seq-equality` (lifter-specific) | `==`/`!=` with seq operands other than against `[]` | none |
| `set`, `map`, `string-char`, `real`, `bitvector`, `tuple`, `higher-order`, `generics`, `type-decl`, `datatype`, `heap`, `module`, `iterator`, `io`, `nondet`, `such-that-exec`, `bodyless-method`, `bodyless-function`, `extreme-predicate`, `mutual-recursion`, `decreases-star`, `char-arith`, `as-cast` | the corresponding type or node kind (4.4, 4.5, 4.1) | same names |
| `unbounded-quantifier` | Quant whose range does not yield two x-free bounds per binder (4.5) | `unbounded-quantifier` |
| `spec-fun-bool-param` (lifter-specific) | Function with a bool formal, reachable | none |
| `let-expression` (lifter-specific) | Let in a lifted expression | none |
| `self-call-lazy-position` (lifter-specific) | self Call under ite branch, quantifier body, or non-first and/or/implies argument | none |
| `decreases-uninferable` (lifter-specific) | section 6 ladder produces no candidate (guard not a comparison, conjunction with no comparison conjunct, rprint gives a tuple with no usable component) | `while-no-decreases` is a burden, not a gap; the lifter must refuse when it cannot even guess |
| `assume` (lifter-specific refusal; census hint) | Assume in a lifted body | `assume` (hint) |
| `ghost-such-that` (lifter-specific) | SuchThat on a ghost local | `assign-such-that` (hint) |
| `name-unsanitisable` (lifter-specific) | section 8 cannot produce a distinct legal name in 100 attempts, or two source names collapse to the same sanitised name (case-insensitively, for SPARK) | none |
| `differential-mismatch` (lifter-specific) | stage 3: any domain point where arm A or arm B disagrees with interp on requires, value or ensures | none |
| `check-wf` (lifter-specific) | stage 3a: check_wf returns errors; a lifter defect, held at zero by T9 | none |

Not refusals, recorded as tags: `source-unverified` (stage 0 verify exit 4
or timeout; the task is still emitted), `no-input` / `real-undefined` /
`no-operator` / `no-witness` (harness refusals of the twin; the task lifted
and passes check_wf but cannot count), and every rewrite name of section 4.

## 6. Decreases inference

t requires a `decreases` on every loop and every spec_fun, and a task-level
one on a self-recursive body. 24 of the 41 loops and 25 of the 30 recursive
functions among the 77 state none (inventory). Dafny infers one and, since
4.11.0 prints it in `--rprint` (measured E1, E2, E4, E5):

| guard / declaration | rprint's inferred clause | source |
|---|---|---|
| `while j < n` | `decreases n - j` | Generated_Code_15 |
| `while (r+1)*(r+1) <= N` | `decreases N - (r + 1) * (r + 1)` | Clover_integer_square_root |
| `while m > 0` | `decreases m - 0` | Invariants_ex1 |
| `while i > 3` | `decreases i - 3` | probe |
| `while i >= 1` | `decreases i - 1` | probe |
| `while x != y` | `decreases if x <= y then y - x else x - y` | probe; Cube's `i != n` |
| `while z < x && z < y` | `decreases x - z, if z < x then y - z else 0 - 1` (a TUPLE) | probe (SlowMax states its own) |
| `function Fib(n: nat)` | `decreases n` | Invariantes_fibonacci |
| `function gcd(x, y)` | `decreases x, y` (a tuple) | ex06-solution |
| `for k := 0 to n` | none | task_id_267 |
| every method | `decreases <all params>` | every file |

Two measured facts shape the rule. First, the inferred clause is a GUESS
Dafny then checks: `dafny verify` on the `!=` probe fails `cannot prove
termination` on its own inferred `ite` (E5), so an rprint clause is not
evidence of termination. Second, an `ite`-shaped clause is legal t: it
passes check_wf, interp evaluates it, the twin ladder runs, and
lower_dafny prints it back (E15), and Cube verifies with it (E14).

The rule, applied in order, first candidate accepted wins:

1. A stated single int-typed clause: copied. A stated tuple: candidate
   list = each component in order, then the sum of the int-typed
   components.
2. Inferred single int-typed clause from rprint (present in R, absent in
   P): candidate.
3. Guard shape, for loops, when rprint gives a tuple or nothing: `a < b`
   and `a <= b` give `b - a`; `a > b` and `a >= b` give `a - b`; `a != b`
   gives `ite(a <= b, b - a, a - b)`; a conjunction gives the candidates of
   each comparison conjunct in order; a for loop gives `hi - k`.
4. For functions with a tuple: each component, then the sum of int params.
5. For a self-recursive method: the stated clause, else rprint's tuple
   handled as in 4.

Each candidate is CHECKED by a Dafny probe: the source file with the
candidate written as the loop's or function's `decreases` (replacing any
stated tuple), `dafny verify --allow-warnings`, exit 0 accepts. The probe
is the source, not the lift, so it measures only the measure. The first
accepted candidate is emitted and recorded `decreases-inferred:<text>`
with its provenance (stated-tuple-component, rprint, guard-shape). If no
candidate is accepted, the FIRST candidate is still emitted, recorded
`decreases-unproved`, because a wrong measure can only make the real cell
fail (visible), and a right one Dafny could not prove may be proved by
another kernel (the sqrt probe E6 verified two different measures, one of
them with no invariant supporting it, which is Z3's nonlinear luck, not a
rule). If there is no candidate at all, refuse `decreases-uninferable`.

Why a checked ladder and not "copy rprint": a tuple has no t form, `!=`
guards produce measures Dafny itself cannot always prove, and a for loop
gets nothing. Why never a weaker measure: there is no such thing; a
measure either proves termination of the same loop or fails.

## 7. nat

Every nat is an int with a fact Dafny knew at every program point. t has
three places for facts, and the lift puts the fact in each place where
Dafny used it, so that the kernels prove the same theorem, and it records
each placement:

- Method parameter `p: nat` becomes `p: int` with `requires p >= 0`
  prepended (4.2). The theorem: the same contract on the same domain
  (`n >= 0` is exactly the set of nat inputs). Measured E13, E14.
- Method return `r: nat` becomes `r: int` with `ensures r >= 0` prepended
  and `invariant r >= 0` appended to every loop that assigns r. The
  theorem: at exit, identical (Dafny's return type IS an ensures a caller
  may use); at loop heads, identical (Dafny's type IS an invariant it gets
  for free); between two assignments inside one iteration, t is weaker (a
  transiently negative value Dafny would reject at the assignment, t
  accepts) and that gap is unobservable to both the value witness and the
  proof witness, which read loop heads and exits only. Measured: fact_a
  (E8) shows the ensures alone is unprovable on a loop-assigned return,
  fact_c and pow_v (E8, E13) show it verifies with the invariant.
- Local `v: nat` becomes `v: int` with `invariant v >= 0` appended to every
  loop that assigns v, deduplicated against an author's invariant that
  already states it literally (4.4). Same argument as the return; hazard 7
  is exactly this loss and this recovery.
- Function parameter `n: nat`: the spec_fun body is wrapped
  `ite(n >= 0, E, default)` (4.1). Without it the lifted `fact` recurses
  below zero and the naive lift fails termination (E8, fact_d). tasks/
  factorial.json's committed `fact` uses the equivalent base-case widening
  `n <= 0`; the wrapper is chosen over widening because it is one rule for
  every body shape and does not require recognising the base case.
- Function result `nat`: widened to int, fact dropped (4.1).
- Quantifier binder `x: nat`: contributes the lower bound `0` (4.5).
- `seq<nat>` and `array<nat>` elements: `requires forall i in [0,
  len(s)). s[i] >= 0` (4.4).

Which theorem I want proved and why: the one Dafny proved, restated with
its implicit type facts made explicit where Dafny used them, so that a
kernel's failure on the lift is a kernel finding and a twin's verification
on the lift says the same thing it says on any t task. The alternative of
dropping `ensures r >= 0` (16.3) makes the lifted spec weaker than the
source's contract and is therefore excluded by the section 0 rule unless
Treston decides the return type is not part of the contract t grades. The
alternative of not adding the type invariants (16.4) keeps the author's
invariant list pristine for the twin ladder at the price of making
provable programs unprovable, which is visible under-counting and
acceptable if preferred; the inventory measured that the appended clause
would be redundant with an author's `0 <= k` in most loops, and the
deduplication rule keeps those lists unchanged.

## 8. Names

Identifiers in the task (task name, params, return, locals, spec_funs and
their params, bound variables, temporaries) must match
`[A-Za-z][A-Za-z0-9_]*`, must not be `surface.KEYWORDS` (t, gate, task,
returns, requires, ensures, decreases, spec, fun, var, while, invariant,
if, then, else, forall, exists, in, len, true, false, and, or, not, int,
bool, seq), must not be in any lowering's reserved set (lower_fstar
RESERVED plus its lowercase-initial rule, lower_rocq RESERVED plus its
`_len` suffix and `sf_` prefix rules, lower_spark RESERVED compared
case-insensitively), and must not be keywords of the seven kernel
languages, since lower_dafny and the others print names verbatim (a Dafny
function named `Function` lowers to `function`, a keyword). 68 of the 77
carry an uppercase initial (inventory hazard 1), two carry a prime
(`gcd'`).

The rule, deterministic and total:

1. Replace `'` with `_p`, `?` with `_q`; strip a leading `_` and prefix `v`.
2. Lowercase the first character.
3. While the result is in RESERVED (the union above, computed at start by
   importing each lowering module's RESERVED and adding a static keyword
   list for Dafny, Verus, SPARK, ACSL/C, Lean, Rocq, F*), or collides
   case-insensitively with another name already chosen in the same task,
   append `_v`.
4. Record `source -> lifted` in `renames`; the disagreement table prints
   source names by inverting the map.

Backstop, measured rather than listed: stage 3e runs every
`lower_X.lower(task, body)` as pure text generation; a NotImplementedError
or ValueError whose message names an identifier triggers one more round of
step 3 on that identifier and a retry. A second failure is
`name-unsanitisable`. The lowerings are the authority on their own
reserved words; the static list only makes the first attempt usually
right.

## 9. The differential check

### 9.1 What it is

Arm A, `dfy_eval.py`: an evaluator of the GENERIC Dafny AST restricted to
what stage 2 accepted, with Dafny's semantics for those nodes and no
knowledge of t: chains natively (`a <= b < c` evaluates b once), parallel
assignment natively (all right-hand sides, then all stores), `for` natively
(`hi` evaluated once, k not assignable), `<==>`, `==>` right-associative,
`in` natively, `return` natively (so a mis-classified tail position shows
up as a different value), nat types natively (a negative value stored into
a nat is a Violation), function preconditions natively (a call outside its
`requires` is Undefined, NOT the totalised default), array parameters as
immutable sequences, mathematical integers, `s[i]` Undefined outside
range, `&&`/`||`/`==>`/ite/quantifier short-circuit as Dafny's WF rules
say, and a source `assert` evaluated and checked (a failing assert on a
requires-satisfying point is an evaluator or parser fault, since the
source verified).

Domain: `interp.domain(task, params)` of the LIFTED task, so both readings
see the same content-derived ladders (the lifted task's literals include
the source's). For every point: (i) source requires under arm A vs lifted
requires under `interp.ev`, type-tagged; (ii) when both true, source body
under arm A vs `interp.exec_body`, return value type-tagged, Undefined vs
Undef aligned; (iii) source ensures under arm A at the source value vs
lifted ensures under `interp.ev` at the lifted value; (iv) at every
arrival at a loop head in the source run, the source invariants under arm
A (must all hold; a failure is an arm A fault) and at the corresponding
arrival in the lifted run the lifted invariants under `interp.ev` (must
all hold; a failure is a lift fault in an invariant rewrite, most likely a
chain split or a nat clause). Budget: `interp`'s caps; a point over budget
on either side decides nothing.

Arm B, `dfy_run.py`: a generated file containing the source declarations
plus a `method Main()` that calls the gradable method once per domain
point that satisfied the requires under arm A (points are written as
Dafny literals; seqs as `[..]`) and prints the result, run with `dafny run
--no-verify --allow-warnings` (measured E16: 3.3 s for a five-point Main,
one process per file). Its printed values are compared type-tagged with
arm A's and with interp's. Arm B cannot report definedness (a compiled
program either prints or crashes) and cannot run a method whose body calls
a ghost function, so it is skipped with tag `arm-b-unavailable` when the
generated file does not compile, and the check then rests on arm A alone.

### 9.2 Is it worth its cost

Cost: `dfy_eval.py` is a second interpreter, on the order of interp.py's
674 lines, plus `dfy_run.py` and a few seconds of dafny per file. Against
that:

- What it catches that a straight translator cannot see. The translator is
  syntax-directed; every rewrite in section 4 is a place where meaning can
  change while syntax stays well-typed: the parallel assignment order
  (Cube's `c, k, m := c + k, k + m, m + 6` sequenced in source order gives
  the right values only by accident of which targets each right-hand side
  reads; `x, y := y, x + y` sequenced gives `y := 2y`), a chain split that
  keeps the wrong operand (`and(0 <= i, 0 <= n)` for `0 <= i <= n` is
  type-correct and wrong), a quantifier bound off by one (`x <= n` lifted
  to `hi = n` instead of `n + 1`), `<==` with arguments in source order, a
  right-associative `==>` read left-associatively, `a - b - c` read
  right-associatively, a `return e` inside an `if` that is NOT the last
  statement being treated as tail so the statements after it vanish, a
  for-loop desugaring whose `hi` reads a variable the body assigns, a
  membership desugaring over the wrong sequence. check_wf sees none of
  these; the kernels would see them only as a real cell that fails or a
  twin that verifies, both attributed to t rather than to the lift. The
  census needed three repair rounds and 185 confirmed detector faults for
  a much simpler instrument; a translator with thirty rewrites will have
  faults, and the check is the only place they are caught before a number
  is corrupted.
- Where two evaluators by one author share a blind spot. `interp.py`'s
  docstring records the measured hazard: "fuzz_lower.ev is a CLONE of `ev`
  below, not an independent reading of SPEC.md ... Agreement between the
  two is therefore evidence of faithful copying and NOT evidence against a
  shared misconception". Arm A and the translator are written by the same
  person against the same reading of Dafny; a misreading of Dafny's
  semantics (say, believing `for k := 0 to n` visits n, or that `%` is
  Euclidean, or that `==>` is left-associative, or that a chain `a < b == c`
  is legal) lands identically in `rewrite.py` and `dfy_eval.py`, the two
  agree, and the check passes a wrong lift. That is exactly why arm B
  exists: `dafny run` is Dafny's own reading of the source, written by
  nobody here, and it disagrees with a shared misconception on the first
  domain point where the misconception changes a value. The residual blind
  spot is properties arm B cannot observe: definedness (Dafny's compiled
  code does not check `nat` or preconditions at run time) and anything
  about invariants. For those, the only independent oracle is `dafny
  verify` of the source, which stage 0 already records, plus T7's
  mutation test of the checker itself.
- Verdict: worth it, on the condition that arm B is built and that the
  checker is mutation-tested (T7). Arm A alone is a regression net for
  implementation slips; arm A plus arm B is a measurement.

## 10. Validation plan: how a wrong lift is caught before it corrupts a number

A wrong lift is one of two things, and the twin discipline reacts to each
differently:

- A lifted SPEC weaker than the source (an ensures lost, a chain conjunct
  dropped, a nat fact dropped, a quantifier range widened): the real cell
  still verifies, and the twin may now VERIFY too, since the spec no
  longer excludes the twin's value. In harness terms this is `twin-verifies:
  vacuous spec`, attributed to t's spec, when the fault is the lift's.
  Worse, if the twin still refutes, the task COUNTS for a theorem weaker
  than the source's.
- A lifted BODY different from the source (a rewrite that changes a
  value): the real cell FAILS on a true program, attributed to a kernel or
  to t, when the fault is the lift's; or, if the spec is loose enough, the
  real still verifies and a different program is counted.

The layers, in the order they run, each stopping the task from reaching
the next:

1. `check_wf(task) == []` (types, scopes, arities, decreases presence,
   bound-variable freshness). Zero tolerance: a failure is a lifter bug.
2. `interp.Reference(task)` has `n_req > 0` and at least one point with a
   value; otherwise the task is tagged `no-input` or `real-undefined` and
   still emitted (they are honest refusals of the twin, not of the lift).
3. The differential check (section 9), both arms where arm B compiles.
   Any mismatch rejects the lift.
4. Round trip to Dafny: `lower_dafny.lower(task, task["body"])` verified
   with the harness's own `verifiers/dafny.py`. When the source verified
   (stage 0) and the lift does not, the row is `real-unproved-after-lift`
   and the sidecar lists every dropped hint (asserts, lemma calls,
   function ensures) and every added obligation (nat ensures, nat
   invariants, inferred decreases) so the cause can be read off. This is
   the cheap first kernel; the seven-kernel sweep is ROADMAP 12.5.
5. Twin cells read against the source: a `twin-verifies` on a lifted task
   whose sidecar shows a dropped or narrowed spec element is flagged
   `lift-suspect-weak-spec` for hand review before it is filed as t's
   vacuity. The sidecar makes that grep possible; without it the two
   causes are indistinguishable.
6. Checker mutation test (T7): the differential checker is run against
   deliberately broken lifters and must catch every seeded fault, so that
   "0 mismatches over 785" is a measurement and not silence.
7. The inverse test (T3, T4): every committed and generated t task lowered
   by lower_dafny and lifted back must return the same task. Where it does
   not, the difference is either a lifter fault or a documented asymmetry
   (the two known ones: `and`/`or` arity flattening of nested binary
   nodes, and lower_dafny's `.capitalize()` of the task name, which the
   rename rule inverts).
8. The census join (stage 4): every disagreement row carries a verdict
   with a quoted line, and rows where the lifter is the one that is wrong
   are lifter bugs to fix, not table entries to keep.

## 11. Test plan: what the implementer writes first

- T1 tokenizer and parser coverage: `dfy_parse.parse(rprint(f))` for all
  785 rprint outputs of stage 0 (the background sweep of section 15 is
  producing them) parses or raises `parse-failure` with a location; the
  count of parse failures is printed and the target is zero.
- T2 precedence oracle: for every parsed file, print the AST fully
  parenthesised, `dafny resolve --print` it, and compare the text with
  Dafny's print of the original token for token. Any difference is a
  precedence or associativity misread in the parser.
- T3 committed inverse: for the 11 tasks in `t/tasks/`, `lift(lower_dafny.
  lower(task, body))` equals the task as canonical JSON (after inverting
  the rename of the capitalised method name). Zero tolerance.
- T4 generated inverse: the same over `fuzz_lower.build_corpus` seeds 1 to
  7 (1528 tasks after check_wf), compared modulo the documented arity
  flattening. Every remaining difference is a lifter fault.
- T5 one test per row of section 4 and one per row of section 5: a
  minimal Dafny program, the expected task JSON or the expected refusal
  set. The corpus programs quoted in section 14 are the first inputs.
- T6 decreases ladder: probes for `<`, `<=`, `>`, `>=`, `!=`, `&&`, tuple,
  for-loop, recursive function with and without nat params; each asserts
  the emitted clause and the recorded provenance, and the `!=` probe
  asserts `decreases-unproved` when Dafny rejects the ite.
- T7 checker mutation test: a switch in `rewrite.py` seeds one of
  {parallel assignment sequenced in source order, chain split keeping the
  first operand twice, quantifier `<=` bound without the `+1`, `<==` in
  source order, `==>` left-associative, tail-return classification that
  accepts any last-in-branch return, for-loop `hi` unbound, membership
  over the first seq parameter, nat requires omitted, `ensures r >= 0`
  omitted}; each must be caught by arm A or arm B on the corpus programs
  where it applies, and the table of which arm caught which is kept.
- T8 renames: every name in every RESERVED set, `Abs`, `gcd'`, `_x`,
  `result`, `x` and `X` in one task, a param named `len`; each yields a
  legal, distinct name and a recorded map; every lowering's `lower()`
  accepts the result as text.
- T9 the 77: every file lifts, check_wf is empty, `Reference` has points,
  the twin rung is recorded, and the per-file rewrite set equals the
  inventory's `constructs_outside_t` reading (differences are read by
  hand once).
- T10 the 785: the refusal-set distribution, the join with census.json,
  and the disagreement table; the count of rows verdicted "lifter wrong"
  must be zero before the wave closes.

## 12. Expected lift of the 77

Expected: 77 of 77 lift into a task that passes check_wf.

Grounds. A token scan of the 77 sources for every construct stage 2
refuses (`assume`, `:|`, `:= *`, `decreases *`, `break`, `match`, `reads`,
`old(`, `ghost var`, `modifies`, `%`, `/`, `if {`, `predicate`, `forall`,
`exists`, `seq<`, `in`) found nothing in any of them (section 15, E17); the
inventory's readers reached the same conclusion (all 77 lift, 17 verbatim,
60 with a named rewrite). Every construct the inventory lists under
`constructs_outside_t` has a row in section 4: nat (30 programs), missing
loop decreases (23) and function decreases (21), chained comparisons (23),
untyped locals (21), tail returns (14), function requires (12, totalised),
uppercase and primed names (8, renamed), asserts (8, dropped), parallel
assignment (7, temporaries), `<==>` (5), multi-name var (4), else-if (2),
uninitialised locals (2), tuple decreases (2: SlowMax's stated `x, y`
whose first component verifies, E10; `gcd'` in ex06-solution is unused
and dropped), one nested loop, one `requires true`.

Programs I expect to REFUSE under this design: none. Programs I expect to
lift but NOT count, from the inventory's readings: task_id_234 and
task_id_626 (straight-line `volume := size * size * size` with no literal,
comparison, if or loop: harness `no-operator`); and programs whose real
cell is at risk in one or more kernels for reasons that are the
lowering's or the kernel's, not the lift's: the two preservation-witness
twins the inventory names (dafny-programs factorial, t1_MF ex4: lower_dafny
emits no certificate for preservation), TuringFactorial's nested loop
(lean and rocq abstain), dafl fibonacci's loop under an `if` (fstar
abstains), and any program whose `ensures r >= 0` needs an induction the
kernel will not do unaided (the type invariant of section 7 discharged
that on factorial and Pow in dafny, E8 and E13, and is untested in the
other six).

The number is a reading, not a measurement; T9 measures it.

## 13. Where it breaks

- The lifter depends on Dafny 4.11.0's printer. A Dafny upgrade that
  changes `--rprint` layout, stops printing inferred decreases, or changes
  the `_System` preamble breaks stage 0 and stage 1 together. Pin the
  version, as the harness does, and keep T1 running.
- Parsing the printed form loses source line numbers. Refusal rows quote
  the rprint line; mapping back to the source is by declaration name and
  statement index, not by line. Hazards that live in comments (`// Do not
  change this postcondition`) are invisible, by design.
- Totalisation of partial functions changes WHAT a twin refutation is
  evidence of: a refutation the source would have produced through Dafny's
  well-formedness channel (a call outside the function's requires after an
  invariant is dropped) becomes, in the lift, a refutation through a
  value, or no refutation at all if the totalised default happens to
  satisfy the spec. This is recorded per task and section 16.5 offers the
  strict alternative (refuse), which costs 12 of the 77.
- Type invariants for nat (section 7) add rungs to INVARIANT-DROP even with
  deduplication. Two lifts of the same program with and without the rule
  can select different twins. The rung is recorded; the rule is a flag.
- The decreases ladder uses Dafny as a checker. A measure that is right but
  only provable in another kernel is emitted `decreases-unproved`; one that
  is wrong is emitted with the same tag. The two are told apart only by
  the seven-kernel sweep.
- Arm B cannot see definedness or invariants, and cannot run bodies that
  call ghost functions. Where arm B is unavailable, the check is one
  author's evaluator against the same author's translator, and the shared
  blind spot of section 9.2 is open there.
- Read-only array parameters lifted to seq (default on) rely on the
  absence of `modifies`, element assignment, `new` and method calls in the
  lifted method; a `modifies a` clause with no write is accepted, which is
  a judgment (the frame permits a write that never happens).
- Membership `x in s` desugared to an existential adds a bound variable
  and a quantifier the author did not write; a kernel that struggles with
  existentials (lower_dafny's docstring records Z3 not instantiating one
  unprompted) may fail the real cell.
- A file with several gradable methods yields several tasks; the census
  counted programs. The join must say which unit each count uses.
- Programs that Dafny 4.11.0 does not resolve (older syntax, missing
  includes) are refused `dafny-resolve-error` whatever their constructs;
  the census read them anyway, so the join will show rows where the census
  says in fragment and the lifter says it cannot read the file. The
  background sweep of section 15 counts them.
- The `for ... downto` mirror and the `seq<nat>` element requires are
  designed, not exercised by any in-fragment program, and are untested
  until T5.
- Stage 3 runs on interp.py's bounded domain. A rewrite wrong only outside
  the domain (huge values, long sequences) passes the check. The kernels
  are the only instrument for that, and their failure is visible.

## 14. Corpus evidence

| file | quote | shows |
|---|---|---|
| Clover_abs.dfy | line 6 `return -x;`, line 8 `return x;` | tail return of an expression in both branches of a final if; `-x` is `neg` of a variable, not a negative literal; method name `Abs` needs the lowercase rename |
| Clover_integer_square_root.dfy | line 2 `ensures r*r <= N < (r+1)*(r+1)`; line 5 `while (r+1)*(r+1)<=N` with no decreases; line 1 `(N:nat) returns (r:nat)` | chain split; `<=` guard whose rprint measure is `N - (r + 1) * (r + 1)`; nat param and nat return rules together |
| Dafny_Verify_tmp_tmphq7j0row_Generated_Code_15.dfy | line 2 `requires n > 0;` | deprecated semicolons give exit 2 without `--allow-warnings` (E2); rprint infers `decreases n - j` |
| Dafny_tmp_tmpmvs2dmry_SlowMax.dfy | line 17 `decreases x,y;`; lines 24 and 25 `if (x <= y) { return b; } else { return a;}`; line 12 `while (z < x && z < y)` | tuple decreases whose first component verifies alone (E10); tail returns of parameters; conjunction guard |
| MIEIC_mfes_tmp_tmpq3ho7nve_exams_appeal_20_p4.dfy | line 6 `var a, b, c := 0, 1, 2;`; line 13 `a, b, c := b, c, a + c;`; line 1 `function F(n: nat): nat { if n <= 2 then n else F(n-1) + F(n-3)}` | multi-name var; parallel assignment needing temporaries (`a + c` reads a target assigned earlier in the list); nat function without decreases |
| Programmverifikation-und-synthese_..._ex06-solution.dfy | lines 1 and 2 `ghost function gcd(x:int,y:int):int requires x > 0 && y > 0`; line 25 `ghost function gcd'(x:int,y:int):int`; line 27 `decreases x+y,y` | a partial function used in the method's ensures and invariant (totalised, E10); a primed name; a tuple decreases on an UNUSED function (dropped) |
| Programmverifikation-und-synthese_..._ex_06_hoangkim.dfy | line 16 `var x: int;`; line 14 `ensures d == gcd(m, n);` | uninitialised local zeroed; function requires totalised |
| dafny-language-server_..._TuringFactorial.dfy | line 19 `var v, s := u, 1;`; lines 15 and 20 nested `while` without decreases | multi-name var with initialisers; nested loops (rprint infers `n - r` and `r + 1 - s`, E5 probe Nested) |
| dafny-synthesis_task_id_762.dfy | line 3 `ensures result <==> month == 4 \|\| month == 6 \|\| month == 9 \|\| month == 11`; line 2 `requires 1 <= month <= 12` | `<==>` to `==` on bools; 4-ary `or` flattening; chain split |
| dafny-synthesis_task_id_801.dfy | line 8 `if (a == b) {` with no else | if without else becomes `"else": []` |
| dafny_examples_..._leetcode_0070-climbing-stairs.dfy | line 16 `a, b := b, a + b;`; line 19 `return b;`; line 12 `invariant i <= n \|\| i == 1` | parallel assignment that sequencing breaks (`b := a + b` after `a := b` doubles b); tail return of a local |
| Dafny_Verify_..._bql_exampls_Square.dfy | lines 5 and 6 `var x: int;` `var i: int;` | uninitialised locals, assigned on lines 8 to 10 before any read |
| dafny-programs_tmp_tmpcwodh6qh_src_factorial.dfy | line 2 `ensures fact(n) >= 1`; line 7 `returns (res: nat)` | a function ensures (dropped) that the nat-return ensures would otherwise need (E8) |
| dafny-programs_tmp_tmpcwodh6qh_src_expt.dfy | lines 22 and 23 `lemma {:induction a} distributive(x: int, a: nat, b: nat) ensures ...` with no body | a bodyless lemma: warning, exit 2 without `--allow-warnings` (E7); dropped as `axiom-dropped` |
| Dafny_Verify_..._AI_agent_verify_examples_Cube.dfy | line 8 `while i != n`; line 14 `c, k, m := c + k, k + m, m + 6;` | `!=` guard: rprint's ite measure verifies here (E14); order-dependent parallel assignment |
| Prog-Fun-Solutions_tmp_tmp7_gmnz5f_extra_pow.dfy | lines 9 and 10 `var x:nat := 1; var k:nat := 0;`; lines 16 to 27 seven `assert` statements | nat locals and the type-invariant rule (E13); asserts dropped without loss in dafny |
| dafny-workout_tmp_tmp0abkw6f8_starter_ex12.dfy | line 2 `method FindMax(a: array<int>) returns (max_idx: nat)`; line 26 `new int[][1, 1, 25, 7, 2, -2, 3, 3, 20]` inside Main only; no `modifies`, no `a[..] :=` | the read-only array case the census tags `array`; the lifter's disagreement row |
| dafny-synthesis_task_id_803.dfy | line 3 `exists i: int :: 0 <= i <= n && i * i == n`; line 4 `forall a: int :: 0 < a*a < n ==> a*a != n` | a bounded existential with an inclusive upper bound (`[0, n + 1)`) beside an unbounded universal (the range is on `a*a`) |
| dafny-language-server_..._Test_tutorial_maximum.dfy | line 9 `requires values != []`; line 10 `ensures max in values`; line 11 `forall i \| 0 <= i < \|values\| :: values[i] <= max` | `!= []` to `len != 0`; membership desugaring; the `\|` range form |
| dafny-synthesis_task_id_414.dfy | line 11 `break;`; line 9 `if seq1[i] in seq2` | early exit inside a for loop; membership as a body condition |
| dafny-synthesis_task_id_105.dfy | line 1 `function countTo( a:array<bool>, n:int ) : int`; line 5 `reads a;`; line 15 `for i := 0 to a.Length` | `array<bool>` refused `array` even read-only; `reads` on a read-only array; a for loop |
| dafny-synthesis_task_id_234.dfy | line 5 `volume := size * size * size;` | lifts and passes check_wf; harness `no-operator` |

## 15. Experiments run

All with `PATH=$HOME/.local/dafny:$PATH`, every dafny call under
`timeout 120`, probe files under the scratchpad `lifter/exp/`.

- E1 `dafny resolve sqrt.dfy --print:sqrt.print.dfy` (Clover_integer_square_root): exit 0; the print keeps `nat`, the chain `r * r <= N < (r + 1) * (r + 1)`, and has NO decreases. `dafny resolve sqrt.dfy --rprint:sqrt.rprint.dfy`: exit 0; the method gets `decreases N` and the loop `decreases N - (r + 1) * (r + 1)`.
- E2 `dafny resolve gc15.dfy --rprint:...` (Generated_Code_15): exit 2 with five `deprecated style: a semi-colon is not needed here` warnings, and the rprint IS written, showing `decreases n, k` on the method and `decreases n - j` on the loop. `dafny resolve mult.dfy --rprint:...` (Invariants_ex1): exit 0; `var m: int := x` for the untyped local of a nat, `decreases m - 0` for `while m > 0`, `return r;` kept.
- E3 `dafny resolve bad.dfy --rprint:bad.rprint.dfy` (body `r := x + true`): exit 2, `1 resolution/type errors detected`, and the rprint file is STILL written (2329 bytes). `dafny resolve parse_err.dfy --rprint:...` (`r := x +;`): exit 2, `1 parse errors detected`, no file written. `dafny resolve gc15.dfy --allow-warnings --rprint:...`: exit 0.
- E4 `dafny resolve fib.dfy --rprint:...` (Invariantes_fibonacci): `function Fib(n: nat): nat decreases n`, loop keeps its stated `decreases n - i`, parallel `x, y := y, x + y;` kept. `dafny resolve gcd.dfy --rprint:...` (ex06-solution): `ghost function gcd ... requires x > 0 && y > 0 decreases x, y` (inferred tuple), `var x: int, y: int := m, n;`, `gcd'` kept with its stated `decreases x + y, y`.
- E5 `dafny resolve guards.dfy --rprint:...` (five probe loops without decreases): `x != y` gives `decreases if x <= y then y - x else x - y`; `i > 3` gives `i - 3`; `i >= 1` gives `i - 1`; `z < x && z < y` gives the tuple `x - z, if z < x then y - z else 0 - 1`; nested loops give `n - r` and `r + 1 - s`. `dafny verify guards.dfy`: exit 4, `cannot prove termination; try supplying a decreases clause for the loop` on the `!=` loop; 4 verified, 1 error.
- E6 `dafny verify sqrt.dfy`: exit 0. `dafny verify sqrt_int.dfy` (nat to int, `requires N >= 0`, chain split, `decreases N - r * r`): exit 0. `dafny verify sqrt_int2.dfy` (same with `decreases N - r` and no invariant on r's sign): exit 0.
- E7 `dafny verify expt.dfy`: `Warning: This ensures clause is part of a bodyless method`, `4 verified, 0 errors`, then `Compilation failed because warnings were found`, exit 2. With `--allow-warnings`: exit 0.
- E8 factorial lifts. fact_a (spec_fun wrapped `if n >= 0 then (...) else 0`, `ensures res >= 0` first, no type invariant): exit 4, `a postcondition could not be proved` on `res >= 0`. fact_b (no `ensures res >= 0`): exit 0. fact_c (base case widened `n <= 0`, `ensures res >= 0`, `invariant res >= 0`): exit 0. fact_d (naive nat to int, base case `n == 0`): exit 4, `decreases expression must be bounded below by 0`.
- E9 `dafny resolve shapes.dfy --allow-warnings --rprint:...` (a probe with every statement shape): exit 2 on an unrelated ghost-use error I introduced, but the rprint shows every shape preserved (`if x > 0 {`, `} else if x > 0 {`, `var t: int := Helper(r);`, `assert`, `assume` with `Warning: assume statement has no {:axiom} annotation`, `L(n);`, `calc == {`, `s[0 .. x]`, `s + s`, `if s == u then 1 else 0`, `ghost var w: int := old(r);`, `s[x := 5]`, `return;`, `return r;`), binders typed (`forall i: int ::`, `forall i: int | 0 <= i < |s| ::`, `forall i: int, j: int ::`), the user program starting at line 126 after `module _System {` (line 4).
- E10 `dafny verify iseven_t.dfy` (function requires totalised, `<==>` as `==`): exit 0. `dafny verify slowmax_t.dfy` (tuple decreases to `x`, nat to int, returns to assignments, non-recursive function `decreases 0`): exit 0. `dafny verify pow_t.dfy` (nat locals to int, asserts dropped, `ensures y >= 0`, no type invariant): exit 4 on `y >= 0`. `dafny verify pow_u.dfy` (without that ensures): exit 0. `dafny verify gcd_t.dfy` (gcd totalised with `decreases x + y`, `var x,y := m,n` split): exit 0.
- E11 `dafny verify for_t.dfy`: the for loop verifies; its while desugaring with `invariant 0 <= k && k <= n` and `decreases n - k` verifies; the desugaring WITHOUT the range invariant fails `a postcondition could not be proved`; 2 verified, 1 error, exit 4.
- E12 `dafny resolve gc15.dfy --allow-warnings --rprint:gc15b.rprint.dfy`: exit 0 (warnings only, with the flag).
- E13 `dafny verify pow_v.dfy` (`ensures y >= 0` first, `invariant x >= 0` appended, k's invariant not duplicated because `0 <= k` is stated): exit 0.
- E14 `dafny verify cube_t.dfy` (`while i != n` with rprint's `decreases if i <= n then n - i else i - n`, three temporaries for the parallel assignment, `requires n >= 0`, `ensures c >= 0` first, `invariant c >= 0` appended): exit 0.
- E15 `python3` in `t/`: a hand-built task with `"decreases": {"ite": ...}` on the loop: `fuzz_lower.check_wf` returns `[]`; `interp.Reference` yields 403 points (529 satisfying requires); `harness.twin_for` returns `wrong-var+nonrefuting` with a witness; `lower_dafny.lower` prints `decreases (if (x <= y) then (y - x) else (x - y))`.
- E16 `dafny run run_mult.dfy --allow-warnings` (Invariants_ex1 plus a Main printing `Mult` at five inputs): exit 0, prints `0 0 6 15 3000000`, 4.1 s; with `--no-verify`: 3.3 s, same output.
- E17 `grep -nE` over the 77 in-fragment sources for `assume|:\||:= *\*|decreases +\*|break|match|reads|old\(|ghost var|modifies|%|/ (not //)|if *\{|function method|predicate|forall|exists|seq<|\bin\b`: no hit in any program (one hit inside a comment of dafl fibonacci).
- E18 `python3` over census.json: 643 gradable; sole-gap counts array 36, div-mod 25, multi-return 14, multi-method 5, real 5, early-exit 4, string-char 3, set 2, nested-seq 2, generics/nondet/seq-literal/bitvector/unbounded-quantifier/module 1 each; 0 of the 77 carry a quantifier; the 36 sole-gap `array` files all lack `array-mutation`.
- E19 background sweep started (`sweep.sh`): `dafny verify --allow-warnings` over the 77 sources into `verify77.tsv`, then `dafny resolve --allow-warnings --rprint` over all 785 into `resolve785.tsv` and `rprint/`. Results are appended to this section when it finishes (see the addendum at the end of this file if present).

## 16. Open decisions (Treston's, not the lifter's)

1. Read-only `array<int>` parameters as `seq`. Default: lift, recorded
   `array-readonly-as-seq`. Reversed: refuse `array`; 36 gradable programs
   whose sole census gap is `array` stay refused and the disagreement table
   loses its largest class of "census right" rows.
2. `x in s` on a seq as a bounded existential. Default: lift, recorded
   `membership-desugared`. Reversed: refuse `seq-membership` (a new name);
   tutorial_maximum and task_id_414-shaped programs stay out; the twin
   ladder never sees a lifter-introduced bound variable.
3. `ensures r >= 0` for a nat return. Default: add, first in the list.
   Reversed: omit; the lifted contract is weaker than the source's return
   type, which section 0 otherwise forbids; some real cells that needed an
   induction now verify.
4. Type invariants `v >= 0` for nat locals and returns assigned in a loop.
   Default: add, appended, deduplicated. Reversed: omit; the author's
   invariant list is the twin's exact instrument, and programs like Pow and
   factorial lose their real cell in dafny (E8, E10).
5. Functions with a `requires` or nat params. Default: totalise with an
   ite wrapper, recorded. Reversed: refuse `function-precondition`; 12 of
   the 77 (inventory) are refused, and every twin refutation keeps its
   source channel.
6. `assume` in a lifted body. Default: refuse `assume`. Reversed: drop and
   record `assume-dropped` (sound direction; the source verdict was not a
   verdict).
7. Unused functions and lemmas. Default: drop, recorded. Reversed: lift
   every function that qualifies; `gcd'`-shaped tuple decreases and name
   hazards then land in tasks that never mention them.
8. Files where Dafny does not verify the source. Default: lift and tag
   `source-unverified`. Reversed: refuse; the corpus is "ground truth" by
   name, and a source that fails 4.11.0 may be a Dafny-version artefact.
9. Files with several gradable methods. Default: one task per method; the
   program counts as in fragment iff all lift. Reversed: refuse
   `multi-method` as the census does, or count per method.
10. Top-level `&&` in requires and ensures. Default: split into clauses.
    Reversed: keep as one clause; identical theorem, different JSON shape.
11. Top-level `&&` in an invariant. Default: keep as one clause (the
    author's rung). Reversed: split; INVARIANT-DROP gains sites.
12. A decreases candidate Dafny cannot prove. Default: emit with
    `decreases-unproved`. Reversed: refuse `decreases-uninferable`; the row
    moves from "real UNPROVED, reason recorded" to "refused".
13. `string` observed only through `|s|`. Default: refuse `string-char`.
    Reversed: abstract to seq when no character is read (task_id_242).
14. `modifies a` with no write to `a`. Default: accept as read-only.
    Reversed: refuse `array-mutation` on the frame alone.
15. For loops. Default: desugar with the implicit range invariant and
    `hi - k`. Reversed: refuse `for-loop` (a new name); no in-fragment
    program has one, so the 77 are unaffected.
16. `module` wrappers with no imports. Default: unwrap. Reversed: refuse
    `module` as the census does.
17. `ghost var` locals. Default: ordinary locals. Reversed: refuse
    `ghost-local`; the value never reaches compiled code, but it can reach
    an invariant.
18. `function ... by method`. Default: drop the method body, lift the
    function. Reversed: refuse `function-method` as the census does.
19. Arm B unavailable (the generated Main does not compile). Default: run
    arm A alone and tag `arm-b-unavailable`. Reversed: refuse the lift;
    fewer tasks, no single-author check anywhere in the counted set.

## Addendum: the background sweep (E19), measured

- `dafny verify --allow-warnings` over the 77 in-fragment sources: 77 of 77
  exit 0 (`verify77.tsv`). Every in-fragment source verifies under 4.11.0
  once warnings are allowed, so `source-unverified` fires on none of them.
- `dafny resolve --allow-warnings --rprint` over all 785: 783 exit 0, 2
  exit 2 (`resolve785.tsv`, rprint files under `exp/rprint/`). The two
  refused `dafny-resolve-error`: `groupTheory_tmp_tmppmmxvu8h_assignment1.dfy`
  (`(65,60): Error: can't use parenthesis when hiding or revealing`) and
  `Program-Verification-Dataset_..._dafny4_ACL2-extractor.dfy` (`(89,20):
  Error: type parameter (T) passed to function xtr must be nonempty`).
  Neither is gradable under the census, so `dafny-resolve-error` costs no
  gradable program and the join has no "census in, lifter cannot read" row.
- No timeouts at 120 s in either pass.
- The 785 rprint files are the input to T1 and T2; the parser is measured
  against them, not against raw source.
