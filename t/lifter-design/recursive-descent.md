# Dafny to t lifter, recursive-descent design

Design wave for ROADMAP.md 12.4. Strategy: a hand-written tokenizer and
recursive-descent parser for the t-expressible Dafny subset, Python 3.12
standard library only, emitting the t JSON AST directly for expressions and
a five-node statement pre-form that one deterministic desugaring turns into
t statements. Program-level structure is scanned first so that a foreign
declaration is refused BY KIND with a named reason; inside a method or a
function the parser is exact and any production outside the subset is a
refusal naming the construct. Dafny 4.11.0 is used twice, as an oracle and
as a cross-check, never as the parser: `dafny resolve --rprint` supplies the
inferred loop and function `decreases` clauses and the inferred types of
untyped locals, and `dafny resolve --print` supplies a second rendering of
the same program that the same parser must read to the same tree.

Everything below that says "measured" was run on this box on 2026-09-05
with dafny 4.11.0 (`$HOME/.local/dafny/dafny`) and the checked-in
`t/` modules; the commands are listed in section 17 and the files are under
`<scratch>/lifter/design/rd/`.
Meaning preservation is the design's only priority: a refusal costs one
row, a wrong lift corrupts every number downstream, so every rule below
comes with the argument for why the kernels grade the same theorem, and
every place where that argument is only "the same on the source's domain"
says so.

## 1. Headline

- Parse, do not pattern-match: a lexer that strips nested comments and
  string literals, a declaration scanner over the token stream with
  bracket-balanced extents, and a recursive-descent parser with Dafny's
  operator precedence and chaining rules.
- One program yields at most one task: the unique method carrying an
  `ensures` (excluding `Main`). Two such methods is `multi-method`, none is
  `no-gradable-method`.
- Functions and predicates reachable from that method become `spec_funs`,
  topologically ordered; unreachable ones are dropped. A function with a
  `nat` parameter or a `requires` is WIDENED to a total function that
  agrees with the source on the source's domain and is 0 (or false)
  outside it. Measured: the widened function agrees with the source on
  every point of the source's domain by a Dafny lemma the kernel proves
  unaided (section 17, E8).
- `nat` becomes `int` plus the explicit non-negativity the type carried:
  a `requires p >= 0` per nat parameter, an `ensures r >= 0` per nat
  return, and an invariant `v >= 0` on every loop that assigns a nat
  local or a nat return. Measured: without the invariant the lifted
  `Pot` (Invariantes_potencia) is UNPROVED in dafny; with it, VERIFIED and
  its twin REFUTED (E7).
- `decreases` is taken from the source when stated as one int expression,
  from `--rprint` when Dafny inferred one, from the head of a stated tuple
  when that head strictly decreases syntactically, and refused otherwise.
  A wrong measure can only lose a row, never mint one, because it adds an
  obligation.
- Expected: all 77 lexically in-fragment programs lift into tasks that
  pass `check_wf`; two of them (`dafny-synthesis_task_id_234`, `_626`)
  cannot count because the twin ladder has no operator. Eight hand-lifts
  under these rules were run end to end (check_wf, interp, twin ladder,
  lower_dafny, dafny): 7 of 8 VERIFIED with the twin REFUTED, the eighth
  (`fatorial`) VERIFIED with a preservation-witness twin that
  lower_dafny cannot certify (UNPROVED, a known kernel-side gap).

## 2. Architecture

Six stages. Each stage may decide exactly what its row says and nothing
else; a stage that cannot decide refuses with a named reason and the run
records the reason against the file.

| stage | input | may decide | may not decide |
|---|---|---|---|
| S0 read | file bytes | UTF-8 decoding (strict, else `encoding-error`), newline normalisation, tab expansion for column numbers only | anything about content |
| S1 lex | text | token stream; comments (nested `/* */`, `//`) removed; string and char literals kept as single tokens; `'` and `?` allowed inside identifiers per Dafny | meaning of any token |
| S2 scan | tokens | the list of top-level declarations with (kind, name, modifiers, extent); refusal by kind (`module`, `class`, `datatype`, ...) with the census gap name; selection of THE gradable method; the set of functions reachable from it | anything inside a body |
| S3 parse | one declaration's tokens | the t expression AST directly; a statement pre-form (t statements plus `Return`, `Assert`, `ParAssign`, `VarDecl`, `Call`); refusal naming the construct | types, decreases, names |
| S4 oracle | `dafny resolve --print` and `--rprint` outputs | for each loop and function without a stated decreases, the clause Dafny inferred; for each untyped local, the type Dafny inferred (`int`, `nat`, `bool`, other); a `parser-disagreement` refusal when S3 reads the `--print` text to a different tree | anything the source does not say and rprint does not print |
| S5 normalise | pre-form + oracle facts | the desugarings of section 7 (return, parallel assign, uninitialised local, multi-name var, chained comparison, `<==>`, nat), renames of section 9, spec_fun widening and ordering, the task JSON, and the provenance record | whether the task is TRUE (kernels only) |
| S6 check | task JSON | `fuzz_lower.check_wf` must return no errors; `interp.Reference` must find at least one point; else refuse `check-wf-error` / `no-input` with the messages | verdicts |

Data flow: S0 to S3 run on the ORIGINAL source. S4 runs dafny twice with
`timeout` and captures stdout (dafny prints warnings on stdout and still
writes both files at exit 2: measured, 257 of 785 corpus files exit 2 from
`resolve` and all 257 wrote their `--print` and `--rprint` output; 255 of
those carry only warnings, mostly "deprecated style", and 2 carry a real
`Error:` line). An `Error:` line in the resolve output is
`dafny-resolve-error`; warnings are recorded and ignored. S4 parses the
`--rprint` text with the SAME S1 to S3 machinery, skipping the leading
`module _System { ... }` block by kind, so the oracle is read by a parser,
not by a regex.

Provenance: every task carries a sidecar `<name>.lift.json` with the source
file, the method name, one entry per rewrite rule applied (rule id, source
line, before, after), the rename map, the list of dropped declarations and
statements, the decreases provenance per loop and per spec_fun (`stated`,
`rprint`, `tuple-head`), and the warnings dafny printed. The disagreement
table reads this sidecar, so a row can say "census: nat; lifter: lifted,
rules nat-param, nat-local-invariant(e)".

## 3. What is parsed: lexer and grammar

### 3.1 Lexer

Token kinds: `id`, `int` (decimal, `0x` hex, `_` separators removed),
`real-literal` (refused later as `real`), `string`, `char`, `sym`, `kw`.
Keywords are Dafny's reserved words (the lexer needs them only to stop an
identifier from being read as one). Identifier syntax per the Dafny manual:
`[A-Za-z_?'][A-Za-z0-9_?']*` with the restriction that a bare `_` is the
wildcard and `?` only appears as a suffix in datatype tests. Comments:
`//` to end of line and `/* ... */` NESTED (Dafny nests them; measured 0
nested block comments in the 785 files, the lexer nests anyway). Strings:
`"..."` with escapes and verbatim `@"..."`. Symbols, longest match first:
`<==>`, `==>`, `<==`, `:=`, `:|`, `::`, `..`, `==`, `!=`, `<=`, `>=`,
`&&`, `||`, `!in`, `->`, `=>`, then single characters including `|`, `<`,
`>`, `!`, `.`, `,`, `;`, `:`, `(`, `)`, `[`, `]`, `{`, `}`, `+`, `-`,
`*`, `/`, `%`, `&`, `^`, `@`, `#`, `` ` ``.

Two lexical traps, resolved by the lexer alone: (a) `{:` opens an
attribute, not a block; the lexer emits a distinct `attr-open` token so
the scanner never counts it as a body brace; (b) `'` inside an identifier
versus a char literal: a `'` directly after an identifier character
continues the identifier, otherwise it opens a char literal. Measured: 178
of 785 files contain a primed identifier; 7 of the 77 contain non-ASCII
bytes, all inside comments (S0 decodes strictly and S1 drops them).

### 3.2 Declaration scanner (S2)

At depth 0 the scanner reads a declaration head: modifiers
(`ghost`, `static`, `twostate`, `least`, `greatest`, `abstract`,
`opaque`), one kind keyword, optional attributes, a name, and then skips to
the end of the declaration: the matching `}` of the first body brace at
depth 0, or the next depth-0 kind keyword when the declaration has no body
(a bodyless lemma or function, an `import`, a `type` synonym, a `const`).
Extents are bracket-balanced over `()`, `[]`, `{}` with attributes
excluded. Kinds and their fate:

| kind keyword(s) | fate | reason name (census name where the same) |
|---|---|---|
| `method` (non-`Main`, with `ensures`) | candidate task; two or more: refuse | `multi-method` |
| `method Main` | dropped; recorded `main-harness` | none (burden) |
| `method` without `ensures`, not called | dropped; recorded `dropped-uncalled-method` | none; the census calls the file `multi-method`, a disagreement to expect |
| `method` without `ensures`, called from the task body | refuse | `method-call` (new) |
| `function`, `predicate`, `function method`, `predicate method`, with `ghost` or not | spec_fun candidate if reachable, else dropped `dropped-unused-function` | see 3.4 for what refuses inside |
| `lemma` (any modifiers), `twostate lemma` | dropped; recorded `dropped-lemma` | none (hint) |
| `least predicate`, `greatest predicate`, `copredicate`, `inductive predicate` | refuse | `extreme-predicate` |
| `class`, `trait` | refuse | `heap` |
| `datatype`, `codatatype` | refuse | `datatype` |
| `newtype`, `type` | refuse | `type-decl` |
| `module`, `import`, `include`, `export`, `abstract module` | refuse | `module` |
| `iterator` | refuse | `iterator` |
| `const` | refuse | `const-decl` (new; could be inlined later) |
| anything else at depth 0 | refuse | `parse-error` |

Ordering: refusals by kind are reported before any body is parsed, so a
file with a `class` and a method is one `heap` row even if the method body
would also have failed.

### 3.3 EBNF of the accepted method and function subset

```ebnf
Method    ::= "method" Name "(" Params ")" "returns" "(" Param ")" Spec* Body
Params    ::= [ Param { "," Param } ]
Param     ::= Name ":" Type
Type      ::= "int" | "nat" | "bool" | "seq" "<" ("int"|"nat") ">"
Spec      ::= ( "requires" | "ensures" ) Expr [";"]
            | "decreases" Expr { "," Expr } [";"]            (* method-level: dropped unless self-recursive *)
            | "modifies" ... | "reads" ...                   (* refuse: frame-clause / heap *)
Body      ::= "{" Stmt* "}"
Stmt      ::= "var" VarItem { "," VarItem } [ ":=" Expr { "," Expr } ] ";"
            | Lhs { "," Lhs } ":=" Expr { "," Expr } ";"      (* Lhs must be a Name; a[i] or x.f refuses *)
            | "if" Expr Block [ "else" ( Block | IfStmt ) ]  (* if (*) / if { case } refuse: nondet *)
            | "while" Expr LoopSpec* Block                  (* while * refuses: nondet *)
            | "for" Name [":" Type] ":=" Expr ("to"|"downto") Expr LoopSpec* Block   (* desugared, 7.9 *)
            | "return" [ Expr ] ";"                         (* tail only, 7.1 *)
            | "assert" [ Attr ] Expr [ "by" Block ] ";"      (* dropped *)
            | "calc" ... "}"                                 (* dropped *)
            | "assume" ... ";"                               (* refuse: assume-in-body *)
            | "ghost" "var" ...                              (* dropped iff every use is in a dropped hint *)
            | Name "(" Args ")" ";"                          (* lemma call: dropped; method call: refuse *)
            | Block                                          (* flattened iff it declares no local *)
            | "label" Name ":" Stmt                          (* refuse: labelled-statement *)
            | ("break" | "continue") ...                     (* refuse: early-exit *)
            | "print" ... | "expect" ...                     (* refuse: io *)
            | Lhs ":|" ...                                   (* refuse: such-that-exec *)
            | "match" ...                                    (* refuse: datatype *)
            | "forall" ... Block                             (* refuse: forall-statement *)
LoopSpec  ::= "invariant" Expr [";"] | "decreases" Expr { "," Expr } [";"] | "modifies" ...   (* modifies refuses *)
VarItem   ::= Name [ ":" Type ]
Function  ::= ["ghost"] ("function"|"predicate") ["method"] Name "(" Params ")" [":" Type] FSpec* "{" Expr "}"
FSpec     ::= "requires" Expr [";"] | "ensures" Expr [";"] | "decreases" Expr {"," Expr} [";"]
            | "reads" ...                                    (* refuse: heap *)

Expr      ::= Equiv
Equiv     ::= Implies { "<==>" Implies }                    (* left-assoc chain; lowered as == on bools *)
Implies   ::= Or [ "==>" Implies ]                          (* right-assoc; "<==" is rewritten to ==> with swapped operands *)
Or        ::= And { "||" And }                               (* n-ary or *)
And       ::= Rel { "&&" Rel }                               (* n-ary and *)
Rel       ::= Add [ RelOp Add { RelOp Add } ]                (* chain rules of the Dafny manual: all of {<,<=,==} or all of {>,>=,==}; a lone != or a lone in/!in; anything else is parse-error *)
RelOp     ::= "==" | "!=" | "<" | "<=" | ">" | ">=" | "in" | "!in"
Add       ::= Mul { ("+"|"-") Mul }
Mul       ::= Unary { ("*"|"/"|"%") Unary }                 (* "/" and "%" refuse: div-mod *)
Unary     ::= "-" Unary | "!" Unary | Postfix
Postfix   ::= Primary { "[" Expr "]" | "[" Expr ".." [Expr] "]" | "[" Expr ":=" Expr "]" | "." Name | "(" Args ")" }
Primary   ::= IntLit | "true" | "false" | Name | "(" Expr ")" | "|" Expr "|"
            | "if" Expr "then" Expr "else" Expr
            | ("forall"|"exists") Binder { "," Binder } [ "|" Expr ] "::" Expr
            | "[" ... "]" | "{" ... "}" | "map" ... | "old" "(" ... ")" | Name "(" ... ")" ... (* see 3.4 *)
Binder    ::= Name [ ":" Type ] [ Attr ]                    (* {:trigger} attributes from rprint are skipped *)
```

`|` is both the cardinality bracket and (in Dafny) bitwise or; the parser
reads `|` in Primary position as a cardinality opener and in binary
position as `bitvector` (refuse). Dafny's own grammar has the same
ambiguity and resolves it the same way.

### 3.4 Expression productions: accepted, rewritten, refused

| Dafny expression | t | note |
|---|---|---|
| decimal or hex integer literal | `{"int": n}` | `-` applied to a literal folds into a negative literal, matching `tasks/linear_search.json`'s `{"int": -1}` |
| `true`, `false` | `{"bool": b}` | |
| identifier in scope | `{"var": name}` after rename (9) | an identifier that is a function name used without a call: refuse `higher-order` |
| `-e`, `!e` | `neg`, `not` | |
| `a + b`, `a - b`, `a * b` | `+ - *` | on ints only; on seqs `+` refuses `seq-concat` (new) |
| `a / b`, `a % b` | refuse | `div-mod` |
| `a == b`, `a != b` | `==`, `!=` | ints or bools; on seqs refuse `seq-equality` (new); on anything else the type refusal of the operand wins |
| `a < b` etc. | order op | ints only |
| `a <= b < c` (chain) | `and` of the adjacent pairs | 7.6 |
| `a && b && c`, `a \|\| b \|\| c` | one n-ary node | the parser builds one node per maximal run, so `a && b && c` is 3-ary and `(a && b) && c` is nested, the same distinction surface.py keeps |
| `a ==> b` | `implies` | right-assoc |
| `a <== b` | `implies(b, a)` | |
| `a <==> b` | `==` on two bools | check_wf admits `==` on bools; measured VERIFIED/REFUTED on IsEven |
| `if c then a else b` | `ite` | |
| `f(args)` where f is a reachable function | `call` | arity checked; a call to a method inside an expression cannot occur in Dafny |
| `\|s\|` | `len` | s must be a seq param |
| `s[i]` | `at` | |
| `s[a..b]`, `s[..b]`, `s[a..]` | refuse | `seq-slice` |
| `s[i := v]` | refuse | `seq-update` |
| `x in s`, `x !in s` with s a seq | `exists k in [0, len s) . s[k] == x` (negated for `!in`) with a fresh k | open decision 19.2; default ON |
| `x in S` with S a set, map, multiset | refuse | `set` / `map` |
| `[a, b]`, `[]` | refuse | `seq-literal` |
| `{a, b}`, `set x \| ...`, `multiset` | refuse | `set` |
| `map[...]`, `map x \| ...` | refuse | `map` |
| `old(e)`, `old@L(e)`, `unchanged`, `fresh` | refuse | `old` / `heap` |
| `a.Length`, `a[i, j]`, `new` | refuse | `array` |
| `e.f`, `e.Ctor?`, `Ctor(...)`, `match` | refuse | `heap` / `datatype` |
| `(a, b)`, `e.0` | refuse | `tuple` |
| `x => e`, `f(g)` with a function argument | refuse | `higher-order` |
| `e as int` where e is int-typed | identity | `e as nat` refuses `as-cast` (a checked cast t cannot state) |
| `1.5`, `real` | refuse | `real` |
| `'c'`, `"s"`, `string`, `char` | refuse | `string-char` |
| `&`, `\|` (binary), `^`, `<<`, `>>`, `bv8` | refuse | `bitvector` |
| `var x := e; body` (let expression) | refuse | `let-expr` (new) |
| `forall`/`exists` | see 7.10 | |

## 4. Selecting the task and its functions

1. Gradable methods = methods with at least one `ensures`, excluding
   `Main`. 0: refuse `no-gradable-method`. 2 or more: refuse
   `multi-method` (open decision 19.1).
2. Returns: exactly one, of type `int`, `nat` or `bool`. 0: `zero-returns`.
   2 or more: `multi-return`. A `seq<int>` return: `seq-return`. Anything
   else: the type's refusal (`array`, `real`, ...).
3. Parameters: `int`, `nat`, `bool`, `seq<int>`, `seq<nat>`. `seq<nat>` is
   lifted as `seq` with a `requires forall k in [0, len s) . s[k] >= 0`
   prepended (the typing constraint made explicit, same principle as nat).
   `array<int>`: `array`. Anything else: its refusal.
4. Reachable functions: transitive closure of call sites in the method's
   requires, ensures, body, invariants and decreases, and in reached
   functions' bodies, requires and decreases. Order: callees before
   callers; a cycle of length 2 or more: `mutual-recursion`. Unreachable
   functions are dropped with `dropped-unused-function` (ex06-solution's
   `gcd'` and hoangkim's `gcd'`, both unused by the method).
5. Lemmas are dropped whole (`dropped-lemma`). A lemma CALL statement in
   the method body is dropped (`dropped-lemma-call`); a lemma was proven,
   so removing the call removes a derivable fact and can only make the
   kernel's job harder. A bodyless lemma is an axiom in the source
   (dafny warns and exits 2 without `--allow-warnings`, measured on
   `dafny-programs_tmp_tmpcwodh6qh_src_expt.dfy`); dropping its call
   removes an ASSUMPTION, which makes the lifted theorem stronger than the
   source's, never weaker; recorded as `dropped-axiom-call` so the
   disagreement table can show it.

## 5. Mapping rules: contract

| Dafny | condition | t | meaning argument |
|---|---|---|---|
| `requires P` (one clause) | P lifts | one `requires` entry, in source order | the conjunction is unchanged; Dafny checks clause k assuming earlier clauses, exactly SPEC.md's rule, so definedness obligations are the same |
| `requires P && Q` | | ONE entry `and(P, Q)`, not split | semantically identical either way; keeping the clause granularity 1:1 with the source lets the disagreement table point at a source line; splitting is offered as an option and changes nothing the kernels prove |
| `requires true` | | dropped, `dropped-trivial-requires` | `true` adds nothing; keeping it would force `"t": 1` on an otherwise v0 task (bool literals are v1) |
| `ensures Q` | Q lifts | one `ensures` entry in source order | same as requires; `ensures` sees params and the return, exactly t's scope rule |
| `ensures Q && R` | | one entry, not split | same as above |
| a clause mentioning `f(args)` | f reachable, lifted to spec_fun `f'` | `call f'` | f' agrees with f on f's domain (section 6); Dafny discharged `args` in f's domain as a well-formedness obligation of the clause, so the call sites the kernels see are exactly where f' = f |
| `ensures r <==> P` | | `==(r, P)` | bool equality is iff |
| method-level `decreases` (stated or rprint's) | body has no self-call | dropped | `check_wf` rejects "task decreases without a self-call"; rprint prints one for EVERY method (measured: `decreases n`, `decreases x, y`, `decreases a, b, c`), so the drop is unconditional unless the body self-calls |
| method-level `decreases` | body self-calls | task `decreases` by the rules of section 8 | gate 3 requires it |
| `modifies`, `reads` on the method | | refuse `frame-clause` | t has no heap |

## 6. Mapping rules: functions to spec_funs

Qualifying function: `function` or `predicate`, ghost or compiled, with
parameters of type `int`, `nat`, `seq<int>`, result `int`, `nat` or `bool`
(predicate = bool), an expression body in the t subset, no `reads`, and no
call to anything but itself and earlier qualifying functions.

| Dafny | condition | t | meaning argument |
|---|---|---|---|
| `function f(p: int, ...): int { E }` | no nat params, no requires | `{"name": f, "params": int/seq, "result": int, "decreases": D, "body": E}` | the defining equation is the same, so the unique solution is the same; D from section 8 |
| `predicate P(...)` | | result `bool` | |
| `function f(n: nat, ...): T requires R { E }` | any nat param or any requires | body `ite(G, E, default)` where G = conjunction of `p >= 0` per nat param, then the requires conjuncts in order; default 0 for int result, false for bool | f' is total and f' = f wherever G holds; every call site the kernels grade is under Dafny's well-formedness obligation that G holds (a source that violated it would not have verified), so the kernels prove the same theorem about the same values. Measured E8: `lemma potencia_agree(x: nat, y: nat) ensures Potencia(x,y) == potencia(x,y)` verifies unaided; a widening with default 1 verifies equally, confirming the default is invisible on the domain |
| `function f(...): nat` | result nat | result `int`; the fact `f(...) >= 0` is LOST | t spec_funs have no ensures; the fact is derivable by induction, so no wrong theorem is proved, but a source proof that leaned on it may become unprovable; recorded `nat-result-fact-dropped` |
| `function f(...) ensures Q { E }` | | `ensures` dropped, `dropped-function-ensures` | Q was proven from E in the source; the kernels must re-derive it; provability may drop, meaning does not (`dafny-programs_..._factorial.dfy`: `function fact(n: nat): nat ensures fact(n) >= 1`) |
| `function f(...) requires R` where R mentions a later function | | refuse `partial-spec-fun-order` | the widening guard would call a function not yet defined |
| `ghost function` | | same as function | spec_funs are spec-only in every kernel; lower_dafny emits a compiled `function` and Dafny 4 allows calling it from a method body, so a compiled source function called in the body lifts too |
| `function method` (Dafny 3 spelling) | | same | the census tags `function-method` as a gap; the lifter lifts it and the table will show the disagreement |
| function with a `reads` clause | | refuse `heap` | |
| function with a seq return, a seq literal, a slice | | `seq-return`, `seq-literal`, `seq-slice` | |
| function called both from `ensures` and from the body | | one spec_fun, called from both | t allows it (SPEC gate 3); `Power` in ComputePower is called from an invariant and an ensures only, the body computes it, so no program in the 77 exercises the body call; `tasks/count_matches.json` does |
| a function the method's body calls that Dafny would call in a ghost context only | cannot occur | | Dafny rejects a ghost call in compiled code at resolution, and the corpus resolved |

## 7. Mapping rules: statements

| Dafny | condition | t | meaning argument |
|---|---|---|---|
| `x := e` | x is the return or a local | `assign` | identical |
| `x := e` | x is a parameter | refuse `param-assign` (new) | Dafny forbids it; unreachable in a resolved file, kept for the fuzz tests |
| 7.1 `return;` | last statement of the body, or last statement of a branch whose `if` is itself in tail position (recursively) | dropped | no statement follows on any path, so the flow is unchanged |
| `return e;` | tail position as above | `assign(ret, e)` | Dafny's `return e` assigns the out-parameter then exits; in tail position the exit is a no-op (`Clover_abs.dfy`: `if x < 0 { return -x; } else { return x; }`) |
| `return` anywhere else (inside a loop, followed by statements) | | refuse `early-exit` | t has no exit |
| `break`, `continue`, `break L` | | refuse `early-exit` | |
| 7.2 `if c { S } else { T }` | | `if` | identical |
| `if c { S }` | | `if` with `"else": []` | SPEC allows an empty else |
| `if c { S } else if d { T } else { U }` | | nested `if` in the else list | Dafny's else-if IS a nested if (`--print` keeps the spelling, `--rprint` too) |
| `if (*)`, `if { case g => S }`, `if c { } case-alternatives` | | refuse `nondet` | census name |
| 7.3 `while g invariant I decreases D { S }` | D one int expr | `while` with invariants in source order | identical; SPEC's frame rule matches Dafny's loop targets (measured in SPEC.md) |
| `while g invariant I { S }` (no decreases) | | decreases per section 8 | see 8 |
| `while (g)` | | parentheses dropped | `--print` drops them too |
| `while *`, `decreases *` | | refuse `nondet`, `decreases-star` | |
| `while g modifies M` | | refuse `frame-clause` | |
| `invariant A && B` | | ONE invariant `and(A, B)`, never split | splitting would add INVARIANT-DROP sites the author did not write and change which twin is chosen; the theorem is the same, the instrument would not be |
| loop inside an if branch, loop inside a loop | | nested as written | t allows both (`uiowa_fibonacci`, `TuringFactorial`); lower_lean and lower_fstar currently refuse these shapes, a kernel-side fact the lifter records, not a lift failure |
| 7.4 `var x: T := e;` | T in int/nat/bool | `var` with type int or bool | nat: int plus the invariant rule of section 10 |
| `var x := e;` (untyped) | rprint prints `var x: T := e` | type T from rprint | Dafny's inference is non-local: measured `var m: int := x` in Aula_2_ex1 (m only used in arithmetic) versus `var e: nat := y` in Invariantes_potencia (e is passed to a nat parameter), both with a nat initialiser; the lifter must not re-implement this. Cross-check: the lifter's own t-typing of `e` must agree with rprint on int-vs-bool, else `type-oracle-disagreement` |
| `var x: T;` (no initialiser) | the first assignment to x is a later statement of the SAME block, before any read of x, any branch or any loop | that assignment becomes `var x: T := e` at its own position, the declaration is dropped | Dafny's definite-assignment rule forbids reading x before it; declaring x where it is first assigned changes no reachable value; `Square` (`var x: int; var i: int; r := 0; i := 0; x := 1;`) and hoangkim (`var x: int; d := m; x := n;`) |
| `var x: T;` otherwise | | refuse `uninitialized-local` (new) | |
| 7.5 `var a, b := e1, e2;` | | `var a := e1; var b := e2;` in order | the declared names are not in scope in the initialisers (Dafny), so order is immaterial and left-to-right is the source's evaluation order |
| `var a, b: T;` | | as 7.4 per name | |
| `x, y := e1, e2;` (parallel) | for every j, RHS_j reads no target_i with i < j | sequential assigns in source order | each RHS still reads old values (`Cube`: `c, k, m := c + k, k + m, m + 6`, ComputePower: `x, y := x + 1, y + y`) |
| `x, y := e1, e2;` | some RHS_j reads an earlier target | `var t0 := e1; var t1 := e2; x := t0; y := t1;` with fresh names | call-by-value snapshot: every RHS is evaluated on the old state, then assigned; the temporaries are locals of the enclosing block and, inside a loop body, do not outlive it, so the frame rule is untouched (`a, b := b, a + b` in climbing-stairs, fibonacci, exercise9, appeal_20_p4, mockExam2_p6) |
| `x, y := *, *`, `x := *` | | refuse `nondet` | |
| `a[i] := e` | | refuse `array-mutation` | |
| `x.f := e` | | refuse `heap` | |
| 7.6 `a <= b < c` (in any expression) | ops all in {<,<=,==} or all in {>,>=,==} | `and(a <= b, b < c)` (adjacent pairs) | Dafny defines a chain as the conjunction of adjacent comparisons; the middle operand is evaluated once in both, and t expressions are pure so duplicating the subterm `b` changes no value; definedness: `and` is left-to-right and each pair's operands were all defined in the source's single evaluation |
| 7.7 `assert P;`, `assert P by { ... }`, `assert {:attr} P;`, `calc { ... }`, `reveal f();` | | dropped, counted in provenance | a checked assertion is a proof hint: removing it removes an obligation the source discharged and a fact that was derivable from what precedes it, so the theorem is unchanged; provability may fall (measured: `problem5` with its 11 asserts dropped is VERIFIED in dafny and its twin REFUTED) |
| `assume P;` | | refuse `assume-in-body` (new; the census tags `assume` as a hint) | the source's proof rests on an unproven assumption; dropping it changes what is graded from "P assumed" to "P not available", which is a stronger theorem than the source proved and is not a lift of the source; default refuse, open decision 19.5 |
| `ghost var g := e;` and assignments to g | every use of g is inside a dropped hint | dropped | ghost state cannot flow into compiled code (Dafny), so with its hint uses gone it is dead |
| `ghost var` used in an invariant or a decreases | | refuse `ghost-state` (new) | |
| lemma call `L(args);` | L is a lemma | dropped `dropped-lemma-call` | section 4.5 |
| method call `x := M(args);` or `M(args);` | M is a method | refuse `method-call` (new) | t has one method per task; the callee's contract would have to be inlined as an assumption |
| 7.8 `label L: S` | | refuse `labelled-statement` (new) | labels exist for `break L` and `old@L`, both refused; measured `--print` renders `label L:` on its own line |
| `{ S }` bare block | declares no local | flattened | pure sequencing |
| `{ var x ... }` bare block | | refuse `block-scope` (new) | t has no block scoping below if/while |
| 7.9 `for i := lo to hi invariant I { S }` | S assigns neither i nor any variable free in hi | `var i := lo; var hi_snap := hi; while i < hi_snap invariant lo <= i, i <= hi_snap, I decreases hi_snap - i { S; i := i + 1 }` | Dafny evaluates the bound once and forbids assigning i; snapshotting hi reproduces that; the two range invariants are Dafny's built-in ones; a `break` in S is `early-exit` (414, 809) |
| `for i := hi downto lo` | | symmetric with `i := i - 1` after S and body first `i := i - 1`... | Dafny's downto body sees i already decremented; the desugaring is `while lo < i { i := i - 1; S }` |
| 7.10 quantifiers | see the table below | | |
| `print`, `expect` | | refuse `io` | |
| `x :\| P` | | refuse `such-that-exec` | |
| `forall i \| R { S }` statement | | refuse `forall-statement` | |
| `match` | | refuse `datatype` | |
| `yield` | | refuse `iterator` | |

### 7.10 Quantifiers

Accepted shapes, with `k` the bound variable, `lo`, `hi` int expressions
not mentioning `k`:

| Dafny | t | argument |
|---|---|---|
| `forall k :: lo <= k < hi ==> P`, `forall k :: lo <= k && k < hi ==> P` | `forall k in [lo, hi) . P` | the same set of k |
| `forall k :: lo < k < hi ==> P` | `[lo + 1, hi)` | integers |
| `forall k :: lo <= k <= hi ==> P` | `[lo, hi + 1)` | |
| `forall k :: k < hi && lo <= k ==> P` (any order of the two bounds, chained or conjoined, in either direction `hi > k`) | as above | commutativity of `and` and of reading a comparison backwards |
| `forall k \| lo <= k < hi :: P` | as above | the range form is Dafny sugar for the implication |
| `forall k: nat \| k < hi :: P`, `forall k: nat :: k < hi ==> P` | `[0, hi)` | nat supplies the lower bound |
| `exists k :: lo <= k < hi && P`, `exists k \| lo <= k < hi :: P` | `exists k in [lo, hi) . P` | |
| `forall i, j :: 0 <= i < j < n ==> P` (two binders) | `forall i in [0, n) . forall j in [i + 1, n) . P` | each binder's range is read from the conjuncts mentioning only earlier binders and params; an i with no valid j is vacuously true in both readings; a binder without both bounds refuses |
| `forall k :: k in s ==> P` with s a seq | refuse `unbounded-quantifier` by default | the range is over VALUES of s, not indices; the faithful rewrite is `forall idx in [0, len s) . P[k := s[idx]]`, which substitutes into P; open decision 19.3 |
| `forall k :: P` with no range, `forall k :: P(k) ==> Q` with a non-range antecedent, `forall k \| f(k) :: Q` | refuse `unbounded-quantifier` | census name |
| `forall k: T` with T not int or nat | refuse `unbounded-quantifier` (or the type's own gap) | |
| a binder whose name is in scope at that point (params, return, locals, enclosing binders) | renamed `k_q`, `k_q2`, ... and recorded | t forbids shadowing; alpha-renaming a bound variable changes no meaning |
| `{:trigger e}` on a binder (rprint adds them) | skipped | a trigger is a solver hint, not semantics |

## 8. Decreases inference

t requires a `decreases` on every loop and every spec_fun and Dafny does
not, so the lifter must supply one where the source is silent. The one
property that makes this safe: a `decreases` ADDS an obligation. A wrong
measure makes the real lowering fail (the row is lost and the provenance
says which rule guessed), and can never make a false program verify or a
twin refute for a reason other than its own defect, because the twin
carries the same measure as the real body. So the rules below are ordered
by trust and the first applicable wins; there is no search over the
kernels.

Loops:

| tier | condition | measure | provenance |
|---|---|---|---|
| L0 | `decreases E` stated, E one int expression | E verbatim | `stated` |
| L1 | `decreases E1, E2, ...` stated | E1, if E1 strictly decreases syntactically: every path through the body assigns each variable of E1 at most once, and E1 after the body's assignments minus E1 before is a negative literal (the body of `slow_max` assigns `x := x - 1`, so `x` from `decreases x, y` qualifies; measured VERIFIED/REFUTED) | `tuple-head` |
| L1 fails | | refuse `lexicographic-decreases` (new) | |
| L2 | no decreases stated, rprint prints `decreases E` with one component | E verbatim, including `e - 0` (rprint's rendering of a `> 0` guard) and `if i <= n then n - i else i - n` (its rendering of a `!=` guard, an `ite`, which t has) | `rprint` |
| L3 | rprint prints a tuple (a `&&` guard yields one component per conjunct, measured: `n - r, if r < n then ... else 0 - 1`) | first component if it passes the L1 syntactic check, else refuse `uninferable-decreases` (new) | `rprint-head` |
| L4 | rprint unavailable (no dafny) | the guard-shape table Dafny itself uses, measured on 4.11.0: `a < b`, `a <= b` give `b - a`; `a > b`, `a >= b` give `a - b`; `a != b` gives `if a <= b then b - a else a - b`; anything else refuses `uninferable-decreases` | `guard-shape` |

Measured shapes rprint printed for the loops of the 77 (stated and
inferred together, variables and literals normalised): `v - v` 21 times,
`v - k` 7, a single variable 4, `v + k - v` 3, the `!=` ite 2, `v + v` 2,
`N - (r + 1) * (r + 1)` 1, the tuple `x, y` 1. Every one but the tuple is
a single int expression t can carry, and the tuple resolves by L1.

Functions:

| tier | condition | measure | provenance |
|---|---|---|---|
| F0 | `decreases E` stated, one int expression | E | `stated` |
| F1 | stated tuple | first component passing F3's check, else `lexicographic-decreases` | `tuple-head` |
| F2 | no decreases, rprint prints one component (always the sole parameter: `decreases n` 21 times in the 77) | that parameter | `rprint` |
| F3 | rprint prints all parameters as a tuple (`decreases x, y` 6 times, `b, n`, `a, e`) | the component p such that at EVERY self-call the argument in p's position is `p - k` with k a positive literal and, for a widened function, the call sits under the widening guard; `Potencia(x, y - 1)` gives y, `pow(a, e - 1)` gives e | `syntactic` |
| F4 | F3 finds no single component (`gcd(x - y, y)` and `gcd(x, y - x)`) | the sum of the parameters that carry a positivity guard in the function's requires (`x > 0 && y > 0` gives `x + y`), accepted only if at every self-call the sum's change is the negation of a guarded-positive term under the enclosing branch condition (`x - y + y - (x + y) = -y` with `y > 0`; `x + y - x - (x + y) = -x` with `x > 0`); measured VERIFIED/REFUTED on gcdI | `sum-of-guarded` |
| F5 | none applies | refuse `uninferable-decreases` | |
| non-recursive function | | `{"int": 0}` | no self-call, so the obligation is vacuous; `max` in SlowMax, measured |

Two honest caveats. First, SPEC.md's gate 3 obligation is that the
CALLEE's measure is `>= 0` at every self-call, while Dafny's is that the
caller's is bounded below; `f(n) = if n < 0 then 0 else 3 * f(n - 5) + n`
(mockExam2_p5) has `decreases n` in rprint and the self-call at n = 3 has
callee measure -2. lower_dafny renders `decreases n` and Dafny accepts it
(measured VERIFIED); a kernel that encodes SPEC.md's rule literally may
reject it. The lifter emits what Dafny inferred and records the tier; the
disagreement is the kernels' to show, not the lifter's to hide. Second,
the inferred measure for `!=` is an `ite` that every kernel must lower in
`decreases` position; dafny does (measured on Cube).

## 9. Names

t names match `[A-Za-z][A-Za-z0-9_]*` and must avoid surface.py's
KEYWORDS (`t gate task returns requires ensures decreases spec fun var
while invariant if then else forall exists in len true false and or not
int bool seq`), lower_fstar's RESERVED plus its lowercase-initial rule,
lower_rocq's RESERVED plus its `_len`, `sf_`, `t_` namespaces, and
lower_spark's RESERVED compared case-insensitively (`F`, `Seq`, `Seqs`,
`Len`, `Elem`, `T_Range`, `R_First`, `R_Has`, `R_Next`, `Big_Integer`,
`Boolean`, `T_Refutation_Certificate`). A lifted task that any lowering
refuses for a spelling reason loses a column for nothing, and the
inventory counts an uppercase initial in 68 of the 77 files and the name
`f` in several (`returns (f: nat)` in fatorial2 and uiowa_fibonacci,
`ghost function f` in mockExam2_p5 and p6).

Deterministic rename, applied to the method, every parameter, return,
local, function and binder, in declaration order:

1. `'` becomes `_p` (`gcd'` to `gcd_p`); a leading `_` gets `v` prefixed;
   `?` cannot occur on a t-liftable name.
2. An uppercase initial is lowercased (`Cube` to `cube`, `N` to `n`).
3. If the result is in the union of the reserved sets above, or ends in
   `_len`, or starts with `sf_` or `t_`, append `_v` (`f` to `f_v`, `in`
   to `in_v`).
4. If the result collides with a name already taken in the same scope
   (Dafny is case-sensitive, so a file may have both `max` and `Max`),
   append `_2`, `_3`, ... until free.
5. The task name additionally must differ from every spec_fun and
   parameter name (lower_dafny capitalises it for the method).

The full map `{source_name: t_name}` is in the provenance sidecar, and
every table the lifter prints uses source names with the t name in
parentheses when they differ. Measured: `fatorial` with `f` renamed
`f_v` VERIFIED in dafny.

## 10. nat handling

The theorem the kernels should prove is the source's theorem: a method
contract in which every `nat` has become `int` constrained by the fact the
type carried at that point, no more and no less. Three places, three
rules, one measurement each way.

| position | t | why this and not the alternatives |
|---|---|---|
| method parameter `p: nat` | `p: int`; `requires p >= 0` PREPENDED before the source's requires, in parameter order | Dafny's typing constrains the caller before any clause is read, so later requires may assume it (SPEC.md: clause k assumes earlier clauses); prepending reproduces that order. Dropping it would widen the domain to negative inputs the source never promised anything about, which is a different, usually false, theorem |
| method return `r: nat` | `r: int`; `ensures r >= 0` APPENDED after the source's ensures | the source's callers know `r >= 0`; a lifted contract without it is WEAKER than the source and a twin returning a negative value could pass it. Appended, not prepended: the source's ensures did not assume it (they were checked under the type, but t has no way to state "the type" except this clause, and putting it first would let a definedness obligation in the source's first ensures lean on it) |
| `nat` local or return assigned inside a loop | invariant `v >= 0` appended to that loop's invariants, one per such name, in declaration order | Dafny checks `v >= 0` at every assignment and therefore knows it at every loop header for free; t's kernels know only the stated invariants. Measured: `Pot` (Invariantes_potencia, `var e := y` with rprint type nat, `while e > 0 invariant Potencia(b, e) * r == Potencia(x, y)`) is UNPROVED without the invariant and VERIFIED with it, twin REFUTED. Appended last so the author's invariants keep their INVARIANT-DROP positions; the synthesized one is a legitimate drop site (it states the typing the source relied on) and its provenance says so |
| `nat` local not assigned in any loop | `int`, nothing added | the frame rule preserves it across loops; between straight-line assignments Dafny's per-assignment check is a proof obligation the lifted task no longer has, but the value is the same on every path (the source verified, so no assignment produced a negative) |
| `nat` local declared inside a loop body | `int`, nothing added | re-initialised each iteration; its nat-ness is a fact about the initialiser the kernel re-derives or not |
| function parameter `n: nat` | widening guard `n >= 0` (section 6) | totality is needed for the kernels' definitional semantics; agreement on the domain measured |
| function result `nat` | `int`, fact lost | section 6 |
| `seq<nat>` parameter | `seq` plus `requires forall k in [0, len s) . s[k] >= 0` | the same principle; not exercised in the 77 |

Alternatives considered and rejected: (a) lift `nat` to `int` with
nothing added: weaker theorem, measured to lose `Pot`; (b) refuse every
program with `nat`: loses 30 of the 77 for a burden, not a gap; (c) a
`nat` gate in t: a language change outside this wave.

## 11. Refusal rules

Refusals by kind at S2 come first, then by construct at S3, then the
semantic refusals at S5, then S6's mechanical ones. Names reuse the
census's gap names where the construct is the same; new names are marked.

| reason | trigger | census equivalent |
|---|---|---|
| `array` | `array<T>`, `.Length`, `new T[...]`, `a[i, j]` | array |
| `array-mutation` | `a[i] := e` | array-mutation |
| `div-mod` | `/`, `%` | div-mod |
| `early-exit` | `return` not in tail position, `break`, `continue` | early-exit |
| `multi-return` | 2+ out-parameters | multi-return |
| `zero-returns` | no out-parameter | zero-returns |
| `multi-method` | 2+ methods with an ensures (Main excluded) | multi-method |
| `method-call` (new) | the task body calls a method | multi-method (the census cannot tell a helper from a second theorem) |
| `no-gradable-method` (new) | no method with an ensures | not gradable in the census (method-with-ensures false) |
| `seq-slice`, `seq-literal`, `seq-update`, `seq-return`, `seq-comprehension`, `nested-seq` | as named | same |
| `seq-concat` (new), `seq-equality` (new) | `s + t`, `s == t` on seqs | no census name (its `seq-return`/`seq-literal` catch some) |
| `set`, `map`, `string-char`, `real`, `bitvector`, `tuple`, `datatype`, `heap`, `generics`, `module`, `type-decl`, `io`, `iterator`, `higher-order`, `nondet`, `such-that-exec`, `decreases-star`, `extreme-predicate`, `char-arith`, `bodyless-method`, `bodyless-function`, `mutual-recursion`, `old`, `unbounded-quantifier`, `forall-statement` | as named in sections 3 to 7 | same names |
| `frame-clause` (new as a refusal) | `modifies`/`reads` on a method or loop | frame-clause (census: burden) |
| `as-cast` (new as a refusal) | `e as nat` | as-cast (census: burden) |
| `const-decl`, `let-expr`, `labelled-statement`, `block-scope`, `param-assign` (all new) | as named | none |
| `assume-in-body` (new) | `assume` inside the task's body | assume (census: hint) |
| `ghost-state` (new) | a ghost local read outside dropped hints | ghost-var (census: hint) |
| `uninitialized-local` (new) | `var x: T;` not folded by 7.4 | untyped-var / none |
| `lexicographic-decreases` (new) | a tuple whose head fails the syntactic check | none |
| `uninferable-decreases` (new) | no tier of section 8 applies | while-no-decreases (census: burden) |
| `partial-spec-fun-order` (new) | a widening guard needs a later function | none |
| `bad-name` (new) | a name the rename of section 9 cannot make legal (cannot happen for Dafny identifiers; kept for completeness) | none |
| `parse-error` (new) | the parser rejects the token stream inside a selected declaration: an unknown production, an illegal comparison chain, an unbalanced bracket | none |
| `dafny-resolve-error` (new) | `dafny resolve` prints an `Error:` line | none (2 of 785 measured) |
| `parser-disagreement` (new) | the tree read from `--print` differs from the tree read from the source after S5's own normalisations | none; a lifter bug, never silently resolved |
| `type-oracle-disagreement` (new) | rprint's type for a local is not int/nat/bool, or disagrees with the lifter's t-typing of the initialiser on int-versus-bool | none |
| `check-wf-error` (new) | `fuzz_lower.check_wf` returns errors on the emitted task | none; a lifter bug |
| `no-input` | `interp.Reference` finds no point satisfying requires | none (SPEC's twin refusal name) |
| `encoding-error` (new) | the file is not UTF-8 | none |

Not refused, only recorded (burdens the lifter carries): `nat`,
`for-loop`, `iff`, `seq-membership`, `parallel-assign`, `untyped-var`,
`trailing-return`, `main-harness`, `if-no-else`, `while-no-decreases`
(when a tier applies), `function-or-predicate`, `spec-only-quantifier`,
`assert`, `lemma`, `ghost`, `calc`, `reveal-opaque`, `attribute`,
`assert-by`, `function-method`.

## 12. Dafny grammar traps and how each is met

| trap | where it bites a regex | how the parser meets it |
|---|---|---|
| comments containing braces, quotes or keywords (`// RUN: %dafny /compile:0 /dprint:"%t.dprint"` in TuringFactorial; block comments with `{` in the cs245 files) | brace balancing and keyword search | S1 removes comments before anything else; nested `/* */` handled by depth |
| strings containing anything | same | S1 keeps a string as one token |
| `{:attribute}` with braces and colons (`lemma {:induction a}`, rprint's `{:trigger s[i]}`) | brace balancing, `::` search | `attr-open` token; attributes skipped as units |
| semicolon-free `assert P by { ... }` | statement splitting on `;` | `assert` production consumes an optional `by` block |
| guarded alternatives `if { case g => S }` and `case` in `match` | `case` looks like a datatype | the `if` production sees `{` where it expects a condition and refuses `nondet`; `match` refuses `datatype` |
| generics `<T>` versus `<` comparison | `<` after a name | S2 reads a type-parameter list only in a declaration head (`method Compare<T(==)>`), refuses `generics`; inside expressions `<` is always a comparison because t admits no generic call |
| `seq<int>` versus `x < y` | same | `seq` is a type keyword; a type is only parsed after `:` or in `returns (...)` |
| `function` versus `method`, `function method`, `predicate method`, `ghost function`, `twostate function` | keyword proximity | S2 reads the full modifier list before the kind |
| `else if` chains | nesting | parsed as a nested if, printed by Dafny the same way |
| deprecated `;` after clauses (`requires n > 0;`) | clause splitting | optional `;` accepted in every clause production |
| `while (g)` and `if(a - 1 == 0)` | `(` glued to the keyword | the condition is an Expr; a parenthesised one is fine |
| chained comparisons `0 <= i <= n`, `r*r <= N < (r+1)*(r+1)` | binary-operator regexes | Rel production with the manual's chain rule; `--print` keeps chains (measured), so both readings go through the same code |
| `<==>` versus `<==` versus `==>` versus `==` | longest match | lexer, longest match first |
| `\|s\|` versus bitwise `\|` | | Primary versus binary position |
| `-` on a literal versus binary minus (`x := -r+1`) | | Unary production; `-r + 1` parses as `(neg r) + 1`, which is Dafny's reading |
| a `label L:` line | looks like a type annotation | `label` keyword production |
| `var x: int;` with no initialiser | `:=` search | VarItem without `:=` |
| primed identifiers `gcd'` and `f'` | `'` read as a char literal opener | lexer rule 3.1(b) |
| `!in` versus `! in` | | lexer emits `!in` as one symbol; `!` followed by space then `in` is also `!in` in Dafny, and the parser accepts both |
| `..` in slices versus `.` field access | | longest match |
| `nat` versus `int` in a `var` with no annotation | invisible in the source | S4 oracle (rprint), never guessed |
| a method named `main` (lowercase) versus `Main` | case | exact match on `Main` only, `main` is an ordinary method (Generated_Code_15, C_convert_examples_15) |
| `returns` on the line after the parameter list (rprint's layout) | line-based scanning | tokens, not lines |

## 13. Cross-checks the lifter runs on itself

1. Print differential: S3 parses the `--print` text of every file and the
   two trees of the selected method and of every reachable function must
   be equal after S5's normalisations (the printer drops parentheses,
   reorders `invariant` before `decreases`, drops deprecated semicolons
   and comments, none of which reaches the AST). Any difference is
   `parser-disagreement`. This runs on all 785 files, including the ones
   refused later, and costs one `dafny resolve` per file (measured: 785
   files at 8-way parallelism finished in well under the 120 s per-file
   timeout, no timeouts).
2. Oracle consistency: for every loop and function where a syntactic tier
   (L4, F3, F4) produced a measure AND rprint printed one, the two must be
   equal or the row is refused `decreases-oracle-disagreement`; this
   keeps the syntactic tiers honest against Dafny's own inference.
3. Round trip through lower_dafny: `lower_dafny.lower(task, body)` is the
   inverse of the lifter on the fragment. The rendered Dafny is verified
   with the adapter (`verifiers.dafny.verify`), and the source is verified
   with `dafny verify --allow-warnings` (measured: 748 of 785 exit 0, 34
   exit 4, 2 exit 2, 1 exit 134; all 77 in-fragment exit 0). A source at
   exit 0 whose lift is not VERIFIED is a `lift-lost-row` for the
   disagreement table with the kernel's message attached; it is never
   counted as in-fragment.

## 14. Validation plan: how a wrong lift is caught

A wrong lift has two shapes and the twin discipline reacts differently to
each:

- A lifted SPEC weaker than the source's (a dropped `ensures r >= 0`, an
  `<==>` read as `==>`, a widened function with the wrong default reached
  on the domain, a requires clause lost). The real lowering verifies MORE
  easily, and the twin, being graded against the weaker spec, may VERIFY
  where the source's spec would have refuted it. Twin VERIFIED on a lifted
  task is therefore a wrong-lift alarm first and a vacuous-spec finding
  second.
- A lifted BODY different from the source's (a parallel assignment
  sequenced wrongly, a for-loop bound not snapshotted, an uninitialised
  local folded past a read). A TRUE program's lift fails to verify, or its
  interp values differ from the source's. Real UNPROVED on a source that
  verifies is the alarm.

Instruments, in the order they run:

1. Spec-equivalence certificate (per task, Dafny). The lifter emits one
   Dafny file holding the source's reachable functions verbatim, the
   lifted spec_funs as lower_dafny renders them, and lemmas: per spec_fun
   `lemma f_agree(params typed as in the source) ensures f_src(args) ==
   f_lift(args)` (the widening guard is exactly the source's domain, so
   the lemma is on nat/requires-constrained inputs); `lemma req_equiv(params
   as int) ensures (typing conjuncts && source requires) <==> (lifted
   requires conjunction)`; `lemma ens_equiv(params, r as int) requires
   lifted requires ensures (typing of r && source ensures) <==> (lifted
   ensures conjunction) { f_agree calls }`. Measured E8: on Pot, all three
   verify, and a deliberately wrong lift (`<==>` read as `==>`) fails its
   lemma; a widening with a different default passes `f_agree`, confirming
   the default is invisible on the domain. A task whose certificate fails
   is refused `spec-equivalence-failed` and never enters the count.
2. Body oracle (per task, Dafny run). The lifter appends a `Main` to the
   SOURCE that calls the method on interp.py's domain points (the same
   `interp.domain` enumeration, nat inputs filtered by the requires) and
   prints the results; `dafny run --no-verify` executes it (measured 3 s
   on Cube; 7 of 7 values equal to `interp.exec_body` on the lifted
   task). A value difference is `body-disagreement` and a refusal. Ghost
   functions do not block this: methods are compiled. Programs whose
   source cannot be compiled (a ghost method) skip this instrument and
   say so.
3. check_wf and interp on every emitted task (S6), so a task that reaches
   the kernels is well-formed and has at least one admissible input.
4. The twin ladder itself: after 1 to 3, a twin VERIFIED cell is reported
   as `twin-verified` with the witness, and the disagreement table lists
   these rows separately from the vacuous-spec rows of committed tasks,
   because on a lifted task the first suspect is the lift.
5. Cross-kernel agreement: a lifted task is in-fragment only when all
   seven kernels verify the real and refute the twin; a kernel that
   abstains (fstar on a loop under an if, lean on nested loops) is
   recorded as an abstention, not as a failed lift.

What a wrong lift means for the twin discipline, stated once: the twin
never touches the spec, so a lifted spec that is weaker than the source's
weakens every twin verdict on that task in the same direction (towards
VERIFIED), and a lifted body that is wrong breaks the real cell (towards
UNPROVED); neither can produce a false "counts" (real VERIFIED and twin
REFUTED) unless BOTH the spec is wrong in a way that still refutes the
twin and the body is wrong in a way that still verifies, which
instruments 1 and 2 test independently.

## 15. Test plan: what the implementer writes first

1. Lexer tests: nested comments, strings with `//` and braces inside,
   `{:attr}` versus `{`, `gcd'` and `'c'`, `!in`, `<==>`/`<==`/`==>`,
   hex literals, a non-UTF-8 byte (refusal), CRLF input (measured 0 in
   the corpus, tested anyway for Windows).
2. Parser golden tests on the 8 hand-lifted programs of E7: the JSON in
   `design/rd/handlift/out/*.json` is the expected output byte for byte
   (canonical JSON), and these already pass check_wf, interp and dafny.
3. Precedence and chaining: `count == 3 <==> a == b && b == c` (801),
   `result <==> month == 4 || month == 6 || ...` (762), `0 <= i <= n`,
   `r*r <= N < (r+1)*(r+1)`, `a != b != c` (parse-error), `x < y > z`
   (parse-error), `-r+1`, `!even(n-1)`.
4. Print differential on all 785 files: zero `parser-disagreement`.
5. Desugaring unit tests: each parallel-assignment class (`Cube` in
   order, `a, b := b, a + b` with temporaries, `x, y := x + 1, y + y`
   order-free); `var x: int;` folded (Square, hoangkim) and refused (a read
   before the assignment, an assignment inside a branch); tail return in
   both branches (Clover_abs) and a return inside a loop (early-exit);
   `for` snapshot (a body that assigns a variable of the bound).
6. Decreases tiers: one program per tier (`Cube` L2 ite, `mult` L2 `y -
   0`, `slow_max` L1, gcd F4, `Potencia` F3, `f` in p5 F2, `max` non-
   recursive), and an oracle-disagreement fixture where the syntactic
   tier and a doctored rprint differ.
7. nat rules: `Pot` with and without the synthesized invariant (UNPROVED
   versus VERIFIED, already measured) as a regression test that the rule
   is load-bearing; a nat return not assigned in a loop (`Pow`, extra_pow)
   gets the ensures and no invariant.
8. Renames: `f` to `f_v`, `Cube` to `cube`, `N` to `n`, a file with both
   `max` and `Max`, a binder shadowing a local.
9. Refusal fixtures, one per reason name in section 11, each a 5-line
   Dafny file, asserting the reason and that S2 refusals fire before S3.
10. Spec-equivalence certificate and body oracle on the 8 hand-lifts (all
   pass), plus the deliberately wrong `<==>` lift (fails).
11. The full run: 785 files, a JSON row per file with `verdict`
   (lifted / refused), `reason`, `provenance`, `census_in_fragment`,
   `census_gaps`, and the disagreement table grouped by (census, lifter)
   pairs.

## 16. Expected lift of the 77

77 of 77 lift into tasks that pass `check_wf`. The rules above were
written from the 77 sources and the inventory's 220 construct entries,
and every construct class present is covered: nat in 30 files (section
10), 24 loops without a decreases (L2, all single-component in rprint
except SlowMax's stated tuple, L1), 23 chained comparisons (7.6), 21
functions without a decreases (F2 for the 21 single-parameter ones, F3
for `Potencia`, `pow`, `Expt`, F4 for `gcd`), 21 untyped locals (rprint),
14 tail returns (7.1), 8 files with asserts (dropped; measured on p5 that
dafny still verifies), 7 parallel assignments (7.5, both classes
measured), 5 `<==>`, 4 multi-name declarations, 2 uninitialised locals
(both fold), 2 if-without-else, 1 lemma (expt, dropped), 2 primed
identifiers (both on unused functions, dropped), 1 nested loop, 1 loop
inside a branch, 8 functions with a requires (widened), 1 with an ensures
(`fact` in dafny-programs factorial, dropped; the inventory's count of 2
included expt's bodyless lemma, which the reader listed among functions),
68 files needing a rename.

Named exceptions, none a lifter refusal:

- `dafny-synthesis_task_id_234.dfy` (`volume := size * size * size`) and
  `dafny-synthesis_task_id_626.dfy` (`area := radius * radius`): lifted,
  then REFUSED by the twin ladder with `no-operator` (no literal, no
  comparison, no if, no variable of another name of the same type to
  swap: `size` is the only int param). These cannot count in any design.
- `dafny-programs_tmp_tmpcwodh6qh_src_factorial.dfy` and
  `t1_MF_tmp_tmpi_sqie4j_exemplos_introducao_ex4.dfy` (and `fatorial2`,
  measured): the twin is an INVARIANT-DROP with a preservation witness,
  which lower_dafny does not certify, so the dafny column reads UNPROVED
  on the twin. A kernel-side gap the inventory already records.
- The 8 assert-heavy files: dafny verified `problem5` with all asserts
  gone; the other seven were not run and may lose the row in one or
  more kernels. That is a row lost, not a wrong lift.
- `mockExam2_p5` and `p6`: `f`'s inferred `decreases n` meets Dafny's
  rule and may not meet SPEC.md's callee-nonnegative rule in a kernel
  that encodes it literally (section 8).

Confidence: 8 of the 77 were lifted by hand under exactly these rules
and run end to end (section 17, E7); the remaining 69 are covered by the
same rules by inspection of their source. The number that will COUNT
(seven kernels, real VERIFIED, twin REFUTED) is not predicted here; it is
what the implementation wave measures.

## 17. Experiments run

All with `PATH=$HOME/.local/dafny:$PATH`, dafny 4.11.0, under
`timeout 120` per dafny invocation. Files under `design/rd/`.

- E1 `dafny resolve X.dfy --print:X.print.dfy` on cube, stairs, s801,
  iseven, slowmax, s397, gcd06, expt. Result: comments gone, canonical
  layout, `invariant` before `decreases`, deprecated `;` gone,
  parentheses dropped where precedence allows (`ensures count == 3 <==> a
  == b && b == c`), chained comparisons KEPT (`0 <= i <= n`), `<==>` kept,
  `a, b := b, a + b` kept, `var a, b := 1, 1` kept, `return b;` kept,
  if-without-else kept, `decreases x, y` kept, `else if` kept, `ghost
  function` kept. Exit 2 on iseven, slowmax, expt (warnings) with the file
  written.
- E2 `dafny resolve X.dfy --rprint:X.rprint.dfy` on cube, mult, rosetta,
  sqrt, potencia, gcd06, extrapow, slowmax, turing, uiowa, iseven, s801,
  aula1, s414, p5. Result: inferred loop decreases exposed (`while i !=
  n` gives `decreases if i <= n then n - i else i - n`; `y > 0` gives `y -
  0`; `i <= n` gives `n - i`; `(r + 1) * (r + 1) <= N` gives `N - (r + 1) *
  (r + 1)`); function decreases exposed as the tuple of all parameters
  (`Potencia`: `x, y`; `pow`: `a, e`; single-param: `n`); a method-level
  `decreases` of all parameters printed on EVERY method; untyped locals
  typed (`var i: int := 0`, `var e: nat := y` in potencia but `var m: int
  := x` in aula1); `for` loops printed without a decreases; quantifiers
  gain `{:trigger ...}`.
- E3 `dafny verify expt_v.dfy` (source with a bodyless attributed
  lemma): "4 verified, 0 errors", then "Compilation failed because
  warnings were found and --allow-warnings is false", exit 2.
- E4 `dafny verify lemma_only.dfy`: "1 verified", exit 0. A lemma is a
  verification unit for dafny; the lifter drops lemmas.
- E5 `dafny resolve guards.dfy --rprint` and `dafny verify guards.dfy`:
  five probe loops. `!=` gives the ite measure; a `&&` guard gives a
  TUPLE (`n - r, if r < n then ... else 0 - 1`); `r <= n - 1` gives `n -
  1 - r`; the gcd-shaped `while a != b` with the inferred ite fails to
  verify ("cannot prove termination"), exit 4, the reason the ex06
  sources state `decreases x + y` by hand.
- E6 `dafny resolve traps.dfy --print` and `--rprint`: `assert x <= y by
  { ... }` printed with a block; `label L:` on its own line; `ghost var g:
  int := r;`; bare `return;`; `predicate P(a: int, b: int)` gets
  `decreases a, b` in rprint; `if r > 3 then r else 3` kept.
- E7 `python3 design/rd/handlift/drive.py` (tasks in `tasks.py`, outputs
  in `handlift/out/`): eight hand-lifts through `fuzz_lower.check_wf`,
  `interp.Reference`, `harness.twin_for`, `lower_dafny.lower`,
  `verifiers.dafny.verify`. pot_noinv: check_wf ok, real UNPROVED, twin
  REFUTED. pot_natinv: VERIFIED / REFUTED (invariant-drop, exit witness).
  cube: VERIFIED / REFUTED (invariant-drop#1). is_even: VERIFIED /
  REFUTED. gcdI: VERIFIED / REFUTED. slow_max: VERIFIED / REFUTED.
  abs_clover (v0): VERIFIED / REFUTED (collapse-if, x=1). problem5 (11
  asserts dropped): VERIFIED / REFUTED (boundary-swap, n=1). fatorial (`f`
  renamed `f_v`): VERIFIED / twin UNPROVED (preservation witness, no
  certificate).
- E8 `dafny verify design/rd/equiv/pot_equiv.dfy`: `potencia_agree`
  verifies unaided; `pot_requires_equiv` verifies; `pot_ensures_equiv`
  verifies once its body calls `potencia_agree(x, y)` (fails without the
  call: the agreement is inductive and Dafny does not invoke it
  unprompted); `bad_agree` (default 1 outside the domain) verifies;
  `wrong_ensures` (`<==>` versus `==>`) fails. "8 verified, 1 error".
- E9 `dafny run --no-verify design/rd/run/cube_run.dfy` (the source plus a
  generated `Main` printing `Cube(0..6)`): 0 1 8 27 64 125 216 in 3.0 s
  wall; `interp.exec_body` on the lifted cube task gives the same seven
  values.
- E10 `design/rd/all785/one.sh` over all 785 files, 8-way `xargs -P 8`:
  `resolve --print` exit 0 on 528, exit 2 on 257 (all 257 wrote the
  file; 255 warnings only, chiefly "deprecated style", 2 with an
  `Error:` line: "type parameter" and "can't use parenthesis when hiding
  or revealing"); `resolve --rprint` identical counts; `verify
  --allow-warnings` exit 0 on 748, 4 on 34, 2 on 2, 134 on 1, no
  timeouts; all 77 in-fragment files verify at exit 0, and 13 of the 77
  exit 2 from `resolve` (warnings only, file written).
- E11 corpus lexical scan (grep/python): 0 CRLF files, 0 BOMs, 0 nested
  block comments, 178 files with a primed identifier, 7 of the 77 with
  non-ASCII bytes (comments only), 7 of the 77 with tabs, 2 of the 77
  with braces or quotes inside comments.

## 18. Where it breaks

- Dafny's type inference for untyped locals is non-local (E2: `m: int`
  versus `e: nat` from the same-shaped initialiser). The design makes
  rprint the authority. Without a working dafny the lifter cannot decide
  nat-ness of an untyped local and must either refuse those 21 files or
  lift them as int without the synthesized invariant, which measured as a
  lost row on Pot. The lifter therefore requires dafny 4.11.0, the same
  binary the dafny column already requires.
- The parser is exact only for the subset; Dafny's full grammar (type
  parameters with characteristics, `abstract module`, `export`, refinement
  `...`, `opaque`, `by method` bodies, `reveal`, `expect`, string
  interpolation, `static`, `@`-annotations in newer versions) is refused
  by kind or as `parse-error`. A `parse-error` on a file that dafny
  resolves is a lifter defect by definition and the print differential
  will surface it; the 785-file run is the acceptance test.
- The decreases tiers are syntactic. F4 (sum of guarded parameters)
  proves nothing itself; it accepts a candidate only when a local check
  passes, and the kernels grade it. A source whose function needs a
  measure outside `p`, `p ± literal`, or a sum of guarded parameters is
  refused `uninferable-decreases`; none of the 77 does, some of the 643
  will.
- SPEC.md's callee-nonnegative decreases rule versus Dafny's (section 8,
  p5 and p6). The lifter cannot fix this without inventing a measure the
  source does not have; it records the tier and lets the kernels
  disagree in the open.
- Widened functions: the argument that the default is invisible rests on
  the source having VERIFIED (every call site under Dafny's
  well-formedness obligation). For a source at exit 4 the lift is still
  emitted, still well-formed, and its spec_funs still agree on the
  domain; but if the source called a function outside its domain the
  lifted task grades a total function where the source was ill-formed.
  The disagreement table therefore carries the source's own verify exit
  code (E10) beside every row.
- Dropping asserts, calcs and lemma calls can lose rows in kernels that
  needed the hint; measured not to on p5 in dafny, unmeasured elsewhere.
- `x in s` desugared to an `exists` introduces a fresh binder and a t
  quantifier where the source had a membership test; the kernels'
  treatment of the two differs (Dafny's `in` on seqs is a built-in with
  its own axioms). Meaning is identical; provability may differ; the
  rewrite is an open decision.
- Multi-method files: 212 of 785 carry the census's `multi-method` gap,
  many with a Main or an uncalled helper. The design lifts the helper-only
  cases and refuses two-theorem files; a per-method lift would change the
  unit of counting from program to method and is not the lifter's call.
- Windows: the lifter shells out to dafny with the two-argument form
  (`--rprint`, path) as verifiers/dafny.py does, decodes stdout as UTF-8
  with replacement, and writes JSON with `\n`; `dafny run` for the body
  oracle compiles to C# on both platforms, untested here on Windows.

## 19. Open decisions for the project owner

1. Multi-method files. Default: refuse `multi-method` when two methods
   carry an ensures; drop uncalled ensures-free helpers and Main. If
   reversed (one task per gradable method): the unit becomes the method,
   the disagreement table needs a per-method row, and `Programmverifikation
   ..._ex_05_Hoangkim.dfy` (three independent method+function pairs)
   yields three tasks.
2. `x in s` on a `seq<int>`. Default: desugar to a bounded `exists` with a
   fresh binder. If reversed (refuse `seq-membership`): 414, 809-style
   files lose a row they would otherwise have; the census would then agree
   with the lifter more often on those files.
3. `forall k :: k in s ==> P` (quantification over values). Default:
   refuse `unbounded-quantifier`. If reversed: rewrite to an index
   quantifier with substitution `P[k := s[idx]]`, meaning-preserving but a
   body rewrite inside the spec.
4. `nat` return. Default: `ensures r >= 0` appended AND `invariant r >= 0`
   on loops assigning r. If reversed (no ensures): the lifted contract is
   weaker than the source's typing and a twin returning a negative value
   can pass; section 14 treats twin VERIFIED as a lift alarm, which this
   choice would blunt.
5. `assume` in a method body. Default: refuse `assume-in-body`. If
   reversed (drop with provenance): the lifted theorem is stronger than
   the one the source proved, and a lost row would be a finding about the
   source, not about t.
6. Function `ensures`. Default: dropped. If reversed (refuse
   `function-ensures`): 1 of the 77 is lost (`fact` in dafny-programs
   factorial, `ensures fact(n) >= 1`) for a hint.
7. Widening default value. Default: 0 / false. Any constant is
   equivalent on the domain (E8); a different constant only moves where a
   twin's off-domain call lands. No reason to change.
8. Clause granularity. Default: one Dafny clause is one t clause, `&&`
   not split, for requires, ensures and invariants alike. If reversed for
   requires/ensures only: identical theorem, finer certificate conjuncts;
   invariants must never be split (twin sites).
9. Placement of synthesized nat invariants. Default: appended after the
   author's. If reversed (prepended): the author's INVARIANT-DROP site
   indices shift and the twin may change; definedness of an author
   invariant could lean on `v >= 0` (it never does in the 77).
10. Array-only-read programs (36 sole-blocker `array` files). Default:
   refuse `array`. If reversed (lift `array<int>` read-only parameters to
   `seq` with `.Length` as `len`): a heap type becomes a value type; every
   `modifies`-free method reading `a[i]` is then in reach, and the
   argument is that a method with no `modifies` clause cannot write the
   array, so the value view is exact. Not implemented in this design; it
   is the single largest coverage lever and a semantic call.
11. `assert`/`calc` dropping versus refusing. Default: drop with a count.
   If reversed: 8 of the 77 refused for a hint.

## 20. Corpus evidence

Quoted from the ground_truth files (paths relative to
`$HOME/tup/t-corpora/DafnyBench/DafnyBench/dataset/ground_truth/`):

- `Clover_abs.dfy`: `if x < 0 {\n    return -x;\n  } else {\n    return x;\n  }` : tail returns in both branches of a tail if (7.1).
- `Dafny_Verify_tmp_tmphq7j0row_AI_agent_verify_examples_Cube.dfy`: `while i != n` with no decreases, `c, k, m := c + k, k + m, m + 6;` : `!=` guard (L2 ite) and an order-safe parallel assignment.
- `Metodos_Formais_tmp_tmpql2hwcsh_Invariantes_potencia.dfy`: `var e := y; //expoente` and `while e > 0 \n    invariant  Potencia(b,e)*r == Potencia(x,y)` : untyped local that rprint types `nat`, no range invariant; the source leans on the type (section 10, measured).
- `Metodos_Formais_tmp_tmpbez22nnn_Aula_2_ex1.dfy`: `var m := x;` with `while m > 0 invariant m >= 0` : rprint types m `int`; the author wrote the range invariant.
- `Programmverifikation-und-synthese_..._ex06-solution.dfy`: `ghost function gcd(x:int,y:int):int\n  requires x > 0 && y > 0` and `while x != y\n    decreases             x+y` : a partial function (widened, F4 `x + y`) and a stated loop measure.
- `Dafny_Verify_..._IsEven_success_1.dfy`: `function even(n: int): bool\n  requires n >= 0` and `ensures r <==> even(n);` : requires on a function, `<==>`, deprecated semicolons.
- `Dafny_tmp_tmpmvs2dmry_SlowMax.dfy`: `decreases x,y;` on the loop and `function max(x:nat, y:nat) : nat` non-recursive : L1 tuple head, non-recursive spec_fun with `decreases 0`.
- `dafny_examples_..._0070-climbing-stairs.dfy`: `var a, b := 1, 1;` and `a, b := b, a + b;` and `return b;` : multi-name declaration, temporaries needed, tail return of a local.
- `dafny-language-server_..._TuringFactorial.dfy`: `// RUN: %dafny /compile:0 /dprint:"%t.dprint" "%s" > "%t"` and a nested `while (s < r + 1)` : comment with quotes, nested loops.
- `Dafny_Verify_..._bql_exampls_Square.dfy`: `var x: int;\n\tvar i: int;\n\n\tr := 0;\n\ti := 0;\n\tx := 1;` : uninitialised locals folded at their first assignment.
- `dafny-programs_tmp_tmpcwodh6qh_src_expt.dfy`: `lemma {:induction a} distributive(x: int, a: nat, b: nat) \n  ensures ...` with no body : attribute with braces, bodyless lemma (dafny exit 2 without `--allow-warnings`).
- `Prog-Fun-Solutions_tmp_tmp7_gmnz5f_mockExam2_p5.dfy`: `ghost function f(n: int): int {\n  if n < 0 then 0 else 3*f(n-5) + n\n}` and 11 `assert` lines : F2 `decreases n` with a callee measure that can be negative; asserts dropped and measured harmless in dafny.
- `dafny-synthesis_task_id_801.dfy`: `ensures (count == 3) <==> (a == b && b == c)` and three `if` statements without `else` : `<==>` and if-no-else.
- `dafny-synthesis_task_id_762.dfy`: `requires 1 <= month <= 12` and `ensures result <==> month == 4 || month == 6 || month == 9 || month == 11` : chain and precedence of `<==>` under a 4-ary `||`.
- `cs245-verification_tmp_tmp0h_nxhqp_A8_Q2.dfy`: `requires true;` and a `/* (| ... |) */` comment on nearly every line : trivial requires dropped, comments with braces.
- `dafny-synthesis_task_id_414.dfy` (out of fragment): `for i := 0 to |seq1|` with `break;` and `seq1[i] in seq2` : for-loop desugaring blocked by early-exit; `in` on a seq.
- `dafny-synthesis_task_id_803.dfy` (out): `ensures result == false ==> (forall a: int :: 0 < a*a < n ==> a*a != n)` : a typed binder whose range is on `a*a`, not on `a`; `unbounded-quantifier`.
- `cs357_tmp_tmpn4fsvwzs_lab7_question5.dfy` (out): `decreases x < 0, x` and `r:= M1(-x, y);` and `r:= A1(r, y);` : a bool component in a tuple measure, a self-call and a method call in the body (`method-call`).
- `Clover_compare.dfy` (out): `method Compare<T(==)>(a: T, b: T)` : type parameter with a characteristic, `generics` at S2.
- `dafny-language-server_..._Test_tutorial_maximum.dfy` (out): `requires values != []` and `ensures max in values` and `forall i | 0 <= i < |values| :: values[i] <= max` : seq literal, membership, range-form quantifier.
