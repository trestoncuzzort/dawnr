# Dafny to t lifter, strategy: dafny-print-normalised

Design only (ROADMAP 12.4). The lifter replaces coverage_census.py's lexical
guess with a parse: a DafnyBench program is in t's fragment when it lifts into
a t task that passes fuzz_lower.check_wf, executes under interp.py, and is
graded by the seven kernels with its twin refuted. This document designs the
lifter whose input is not the raw .dfy text but the program as the Dafny
4.11.0 binary itself re-prints it after resolution. Everything stated about
Dafny below was run on this box (section 1 quotes the output; section 16
lists every command); everything stated about a corpus program quotes the
program.

Scope of the strategy in one sentence: run `dafny resolve FILE.dfy
--allow-warnings --rprint:OUT.dfy`, gate on exit code 0, discard the
`_System` preamble (it is one block comment), parse the user module with a
recursive-descent parser over a small Dafny subset, and lift that AST.

## 0. Verdict in brief

- Normalisation is worth it, and the resolved print (`--rprint`) is the one
  to parse, not the parsed print (`--print`): only the resolved print carries
  the decreases clauses Dafny inferred for loops and functions and the types
  it inferred for locals, and t requires both. 24 of the 41 loops and 25 of
  the 30 recursive functions inside the 77 in-fragment programs have no stated
  decreases (inventory.md, section 1); without rprint the lifter would have to
  invent measures.
- What it buys: one spelling per construct (comments, deprecated semicolons,
  redundant parentheses, `if (x)` parentheses and whitespace are gone;
  clauses print in a fixed order), resolution errors are caught before
  lifting (2 of 785 corpus programs), inferred decreases and local types are
  made explicit, and the parser downstream needs no error recovery because
  the input is machine-printed. It costs one dafny process per program,
  measured median 0.57 s (785 programs: 452 s of process time, 113.5 s wall
  with 4 workers), plus a dependency on the pinned Dafny 4.11.0, which
  verifiers/dafny.py already carries (it runs `--rprint` on every kernel
  call, for the certificate door), so this is not a new dependency.
- What normalisation does NOT do: it does not desugar. Chained comparisons,
  parallel assignments, multi-name `var`, `<==>`, `else if`, if without else,
  trailing `return`, nat types and quantifier ranges all survive verbatim, so
  the lifter's mapping rules are the same as for raw source. The parser is
  easier (no comments, canonical layout), the semantics are not.
- Expected: 74 of the 77 census in-fragment programs lift into tasks that pass
  check_wf under the default rules; the 3 refusals are `decreases-tuple`
  (SlowMax, and the two ex_06 gcd files). With the opt-in Dafny-checked
  candidate measure (section 7) all 77 lift; measured, Dafny accepts
  `decreases x` for SlowMax's loop and `decreases x + y` for gcd.
- Where it breaks: tuple decreases, `for` loops (rprint prints no measure),
  functions whose requires is not a nat guard (totalised, a recorded
  weakening), `x in s` and `values != []` (desugarings that are policy calls),
  arrays (refused by default even when read-only), and any construct the
  parser does not know, which it refuses by name rather than skipping.

## 1. What the Dafny binary does, measured

Binary: `/home/tmcuzzort/.local/dafny/dafny`, `dafny --version` prints
`4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2`. Scratch directory for
every file below: `scratchpad/lifter/design/dpn-exp/` (paths abbreviated).

### 1.1 `--print` on three corpus shapes

Straight-line, `Clover_abs.dfy` (source lines 2 and 3 are `ensures x>=0 ==>
x==y` and `ensures x<0 ==> x+y==0`):

    $ dafny resolve abs.dfy --print:abs.print.dfy    (elapsed 0.45s, exit 0)
    // abs.dfy

    method Abs(x: int) returns (y: int)
      ensures x >= 0 ==> x == y
      ensures x < 0 ==> x + y == 0
    {
      if x < 0 {
        return -x;
      } else {
        return x;
      }
    }

Loop without a stated decreases, `dafny_examples_..._climbing-stairs.dfy`
(elapsed 0.50 s, exit 0): the print keeps `var a, b := 1, 1;`, `var i := 1;`,
`a, b := b, a + b;` and `return b;` verbatim, drops the comment `// A simple
specification`, and adds NO decreases to `while i < n` and NO decreases to
`function Stairs(n: nat): nat`. The function body is re-laid-out as

    function Stairs(n: nat): nat
    {
      if n <= 1 then
        1
      else
        Stairs(n - 2) + Stairs(n - 1)
    }

Recursive function without a stated decreases, `Metodos_Formais_..._fatorial2.dfy`
(elapsed 0.48 s, exit 0): the trailing comment block (lines 22 to 28 of the
source, non-ASCII included) is gone; `Fat` gets no decreases; the loop's
clauses are reordered from the source's `decreases n-i` then two `invariant`
lines to

      while i <= n
        invariant 1 <= i <= n + 1
        invariant f == Fat(i - 1)
        decreases n - i

So `--print` is the PARSED program: comments dropped, spacing canonical,
clauses ordered invariant then decreases, nothing inferred.

### 1.2 `--rprint` on the same three: the preamble and the inferred clauses

`dafny resolve abs.dfy --rprint:abs.rprint.dfy` (elapsed 0.45 s, exit 0, 130
lines). Structure of the file, quoted:

    // abs.dfy

    /*
    module _System {
      /* CALL GRAPH for module _System:
       ...
      datatype /*_tuple#0*/ () = _#Make0
    }
    // bitvector types in use:
    */

    /* CALL GRAPH for module _module:
     * SCC at height 0:
     *   Abs
     */
    method Abs(x: int) returns (y: int)
      ensures x >= 0 ==> x == y
      ensures x < 0 ==> x + y == 0
      decreases x
    {

The whole `_System` preamble is ONE nested block comment (`/*` on line 3,
`*/` after `// bitvector types in use:`), so a lexer that handles nested
block comments drops it for free; no line-based stripping is needed. Note
the method-level `decreases x` that resolution added to a non-recursive
method: the lifter must drop it (check_wf: "task decreases without a
self-call").

climbing-stairs rprint (elapsed 0.47 s, exit 0), user module:

    function Stairs(n: nat): nat
      decreases n
    { ... }

    method ClimbStairs(n: nat) returns (r: nat)
      ensures r == Stairs(n)
      decreases n
    {
      var a: int, b: int := 1, 1;
      var i: int := 1;
      while i < n
        invariant i <= n || i == 1
        invariant a == Stairs(i - 1)
        invariant b == Stairs(i)
        decreases n - i
      {

fatorial2 rprint (elapsed 0.48 s, exit 0): `function Fat(n: nat): nat
decreases n`, `method Fatorial(n: nat) returns (f: nat) ... decreases n`,
`var i: int := 1;`, and the stated `decreases n - i` unchanged.

So `--rprint` exposes: the inferred decreases of a function, the inferred
decreases of a while loop, a default method-level decreases (to be dropped),
and the inferred type of every local (`var i: int := 1`). This is the fact
the strategy rests on.

### 1.3 The construct probe (`mix.dfy`)

A synthetic file with a leading `//` comment and a `/* */` comment, the old
syntax `function power(a: int, n: int): int requires 0 <= n; decreases n;`,
`function Half(n: nat): nat { n / 2 }`, a method with `requires n >= 0;`
(deprecated semicolon), `ensures r >= 0 <==> n >= 0`, `ensures (r == 1) <==>
(n == 1 || n == 2) && n != 3`, three quantifier spellings, a chained
`1 <= n+1 <= n+2`, `var a, b := 1, 2;`, `var i := 0;`, `var c: int;`,
`a, b := b, a + b;`, `if n > 5 { a := a + 1; }` with no else, an
`if (n > 7) ... else if (n > 6) ... else ...` chain, a loop with no
decreases, `assert i == n;`, and `return r;`.

Result without `--allow-warnings`: exit 2, three `Warning: deprecated style:
a semi-colon is not needed here` and `Compilation failed because warnings
were found and --allow-warnings is false`, yet the print file WAS written.
With `--allow-warnings`: exit 0, and `diff` shows the printed text is
byte-identical. The print:

    function power(a: int, n: int): int
      requires 0 <= n
      decreases n
    { ... }
    method Mix(n: nat, s: seq<int>) returns (r: int)
      requires n >= 0
      ensures r >= 0 <==> n >= 0
      ensures r == 1 <==> (n == 1 || n == 2) && n != 3
      ensures forall k :: 0 <= k < |s| ==> s[k] == s[k]
      ensures forall k | 0 <= k < |s| :: s[k] == s[k]
      ensures forall k :: k in s ==> k == k
      ensures 1 <= n + 1 <= n + 2
    {
      var a, b := 1, 2;
      var i := 0;
      var c: int;
      a, b := b, a + b;
      if n > 5 {
        a := a + 1;
      }
      if n > 7 {
        b := 1;
      } else if n > 6 {
        b := 2;
      } else {
        b := 3;
      }
      while i < n
        invariant 0 <= i <= n
      {
        i := i + 1;
      }
      assert i == n;
      r := a + b + i;
      return r;
    }

Observations that drive the parser: redundant parentheses are removed and
necessary ones kept by Dafny's precedence table (`(r == 1) <==> ...` lost
its parentheses, `(n == 1 || n == 2) && n != 3` kept them); `if (n > 7)`
became `if n > 7`; `else if` is preserved as a chain; chained comparisons
are preserved; every semicolon after a clause is gone; comments are gone;
nat stays nat; the trailing return stays. The rprint of the same file adds
`decreases n` to `Half` (non-recursive: the default measure is the parameter
tuple), `decreases n, s` to the method, `decreases n - i` to the loop, types
to the locals (`var a: int, b: int := 1, 2;`, `var i: int := 0;`) and
triggers plus binder types to the quantifiers:

      ensures forall k: int {:trigger s[k]} :: 0 <= k < |s| ==> s[k] == s[k]
      ensures forall k: int {:trigger s[k]} | 0 <= k < |s| :: s[k] == s[k]
      ensures forall k: int {:trigger k in s} :: k in s ==> k == k

The parser must therefore skip `{:attr ...}` groups wherever Dafny may
print one (after a binder's type, before a declaration name, on `case`).

### 1.4 Programs that do not parse or resolve

- `noparse.dfy` (`r := x +;`): `Error: invalid UnaryExpression`, `1 parse
  errors detected`, exit 2, and NO print file is written (`ls: cannot access
  'noparse.print.dfy'`).
- `noresolve.dfy` (`r := x + true;`): `Error: type of right argument to +
  (bool) must agree with the result type (int)`, exit 2, and the print file
  IS written, containing the ill-typed program. Same with `--rprint`.
- `undeclared.dfy` (`ensures r == y`): `Error: unresolved identifier: y`,
  exit 2, print file written.
- `--allow-warnings` does not change a real error's exit code (noresolve
  still exits 2).

Rule: gate on exit code 0 under `--allow-warnings`, never on the output
file's existence. The exit-2 stdout distinguishes `N parse errors detected`
from `N resolution/type errors detected`, so the refusal reason can name
which.

### 1.5 Inferred decreases by guard shape

`guards.dfy` (one method, eleven loops, plus `gcd` with a requires and
`Ack`), rprint user module, quoted per loop:

    while i <= n            decreases n - i
    while j > 0             decreases j - 0
    while k != n            decreases if k <= n then n - k else k - n
    while (r + 1) * (r + 1) <= N
                            decreases N - (r + 1) * (r + 1)
    while x != y            decreases if x <= y then y - x else x - y
    while z < x && z < y    decreases x - z, if z < x then y - z else 0 - 1
    while q >= 1            decreases q - 1
    while w > n             decreases w            (stated, kept)
    for t: int := 0 to n    (no decreases printed)
    while outer < n         decreases n - outer
      while inner < outer + 1   decreases outer + 1 - inner

and for the functions: `ghost function gcd(x: int, y: int): int requires x >
0 && y > 0 decreases x, y`, `function Ack(m: nat, n: nat): nat decreases m,
n`. The method got `decreases n, N, m`. `dafny verify guards.dfy`: `3
verified, 0 errors`, exit 0, so every inferred clause is one Dafny proves.

`guards2.dfy` (guards `!done`, `j < n || j < 3`, a bare bool `b`): rprint
prints NO decreases on any of the three loops, and `dafny verify` reports
`Error: cannot prove termination; try supplying a decreases clause for the
loop` at `while !done`, exit 4. So Dafny infers a measure for `<`, `<=`,
`>`, `>=`, `!=` and conjunctions of those (a tuple), and nothing for
disjunctions, negations or bool guards; a corpus program with such a loop
verifies only because it states its own measure, which rprint keeps.

Over the 77 in-fragment programs' rprints (script in section 16): 41 while
loops, 41 with a decreases line, 0 without. By guard: `<` 20 (measures like
`n - j`), `>` 10 (`y - 0`, `m - 0`, `e - 0`), `!=` 6 (`N - x`, `if i <= n
then n - i else i - n`), `<=` 3 (`N - (r + 1) * (r + 1)`), `>=` 1 (`k`), `&&`
1 (SlowMax, stated `x, y`). Exactly one loop measure is a tuple. 0 `for`
loops.

Functions in the 77 rprints: 31 function declarations; 30 recursive, of
which 24 print a single-variable `decreases` and 6 print a tuple of all
parameters (`Potencia(x, y)` twice, `pow(a, e)`, `Expt(b, n)`, `gcd(x, y)`
twice) plus `gcd'` with stated `decreases x + y, y`; the non-recursive `max(x,
y)` prints `decreases x, y`.

### 1.6 Spelling and parenthesisation (`forms.dfy`)

Under Dafny 4's default `--function-syntax:4`, `function method fm(...)` is
a PARSE error: `Error: the phrase 'function method' is not allowed when using
--function-syntax:4; to declare a compiled function, use just 'function'`.
(In the corpus, the only two files containing the phrase have it inside
comments; the census's one `function-method` file uses `by method`.) With
that line fixed, the print shows:

    requires a == b == c
    ensures r == -5 || r == -5 || r == 0 - 5          (from -5, -(5), 0 - 5)
    ensures !(a < b) && (a % 2 == 0 || a / 2 == 1)
    ensures a == b && b == c && c == a                (from three bracketings)
    ensures a <= b < c || a in s || a !in s
    ensures |s| >= 0 && (|s| > 0 ==> s[0] == s[0]) && s == s && s + s == s + s && s[0 .. 1] == s[..1]
    ensures forall i, j :: 0 <= i < j < |s| ==> s[i] <= s[j]
    ensures (if a > b then a else b) >= a
      r := -5;  var t := -5;  var u := 0 - 5;
      if { case a > 0 => r := 1; case a <= 0 => r := 2; }     (laid out on lines)
      L(a, 0);
      assert r == r by { }
      calc { r; == r; }                       (rprint: `calc == {`)
      assume r == r;
      ghost var g := 1;                       (rprint: `ghost var g: int := 1;`)
      r := if a > 0 then r else -r;
      var w := *;                             (resolution error: type underspecified)
      r :| r == 5 || true;
      if * { ... } else { ... }
      match a { case {:split false} 0 => ... case {:split false} _ /* _v0 */ => ... }
      r := r - a - b;                         (from (r - a) - b)
      r := r - (a - b);

So: `(a && b) && c` and `a && (b && c)` print identically (Dafny's AST is
binary but the printer elides same-precedence parentheses), `-5` and `-(5)`
print identically, and rprint can contain a comment (`/* _v0 */`) and
attributes inside `case`. The lexer strips comments; the parser skips
attributes; `match`, `:|`, `*`, `assume`, `ghost var`, `calc` are each
recognised and refused by name (section 9).

### 1.7 Cost and the exit-code census over the corpus

- 77 in-fragment programs, `dafny resolve ... --allow-warnings --rprint`,
  sequential: 77 exit 0, 38.0 s wall, 0.49 s per program.
- All 785 programs, 4 worker threads (`corpus785.py`): exit 0 for 783, exit
  2 for 2; both are resolution errors, not parse errors:
  `Program-Verification-Dataset_..._dafny4_ACL2-extractor.dfy(89,20): Error:
  type parameter (T) passed to function xtr must be nonempty` and
  `groupTheory_tmp_tmppmmxvu8h_assignment1.dfy(65,60): Error: can't use
  parenthesis when hiding or revealing`. Per-file seconds: min 0.45, median
  0.57, p90 0.63, max 1.63, sum 452.5; wall 113.5 s. 256 of 785 print at
  least one warning (deprecated semicolons and the like), all accepted under
  `--allow-warnings`. Files with spaces in their names (`M2_tmp_..._Software
  Verification_...`) resolve fine when passed as one argv element.
- Corpus files: 0 of 785 have CRLF line endings (`file` and a `\r` grep),
  so newline handling is not exercised by this corpus; the lifter still
  reads with `newline=None` and writes with `newline="\n"` per
  RUN-ON-WINDOWS.md.

### 1.8 Normalisation preserves verifiability on the 77

`verify77.py`: for each of the 77, `dafny verify --allow-warnings` on the
source, on its `--print` output, and on its full `--rprint` output (the
preamble comment left in). Result: `src exits Counter({0: 77})`, `print
exits Counter({0: 77})`, `rprint exits Counter({0: 77})`, `disagreements
0`, wall 73.0 s at 4 workers. So the rprint file is itself a valid Dafny
program that verifies, and every exposed inferred clause is one Dafny
accepts when stated.

### 1.9 End-to-end hand lifts through the real t pipeline

Six tasks were written by hand following the rules of sections 5 to 8 from
the rprint of five corpus programs, then run through `fuzz_lower.check_wf`,
`interp.Reference`, `harness.twin_for`, `lower_dafny.lower` and
`verifiers.dafny.verify` (files under `dpn-exp/lift/`):

| source program | rules exercised | check_wf | twin (witness) | dafny real | dafny twin |
|---|---|---|---|---|---|
| Invariantes_fatorial2 | nat param/return, nat function totalised, tail `return f`, added `f >= 0` invariant | OK | invariant-drop (preservation at n=0, i=0, f=0) | verified | unproved |
| IsEven_success_1 | function with `requires n >= 0` totalised, `<==>` to `==`, bool return | OK | invariant-drop (exit at n=0, i=1, r=False) | verified | refuted |
| climbing-stairs | multi-name var, parallel assign via temps, tail `return b`, inferred `n - i` | OK | compare-flip (n=1: real 1, twin 2) | verified | refuted |
| integer_square_root, no added invariant | inferred `N - (r + 1) * (r + 1)`, chained ensures | OK | invariant-drop (exit at N=0, r=1) | verified | refuted |
| integer_square_root, added `r >= 0` | same plus nat-return invariant | OK | invariant-drop (exit at N=0, r=1) | verified | refuted |
| AI_agent_verify_examples_Cube | `!=` guard with the ite measure `if i <= n then n - i else i - n`, 3-target parallel assign | OK | invariant-drop#1 (exit at n=0, i=0, k=1, m=6, c=1) | verified | refuted |

Five of six count in dafny; fatorial2's twin is a preservation witness, for
which lower_dafny emits no certificate (its docstring: "preservation,
undefined: not emitted; such a cell honestly reads unproved"). The inventory
predicted exactly this for the factorial-shaped programs.

### 1.10 Measures Dafny accepts in place of a tuple

- `reduce.dfy`: `function Expt(b: int, n: nat): int decreases n` (Dafny's
  inferred tuple was `b, n`) and its int-totalised form `if n < 0 then 0
  else if n == 0 then 1 else b * ExptT(b, n - 1)` with `decreases n`: `2
  verified, 0 errors`.
- `slowmax_decx.dfy` (SlowMax with `decreases x` in place of the stated
  `decreases x,y`): `1 verified, 0 errors`, exit 0.
- `gcd_sum.dfy` (ex06-solution with `decreases x + y` added to `gcd`): `4
  verified, 0 errors`, exit 0.

## 2. Judgement: easier or harder than raw source, and at what price

Easier, for the parser and for exactly these reasons: (a) no comments, no
string or char literals to mask inside the fragment (a program that carries
one is refused anyway), no deprecated semicolons, one whitespace and
parenthesis convention, so the recursive-descent parser has no error
recovery and no masking pass; (b) the input has already type-checked, so
`x + true` or an unresolved name never reaches the lifter, and the two such
corpus files are refused with Dafny's own message; (c) every local carries
its type (`var i: int := 1`), so the lifter never infers a type; (d) every
loop Dafny could bound carries its measure, and every recursive function
carries Dafny's measure or its default tuple, so "uninferable decreases"
becomes a fact the binary states (a loop with no decreases line) rather than
a guess; (e) `dafny resolve` accepts the exact input the kernel later
grades, so the census and the kernel share one front end.

Not easier semantically: normalisation performs no desugaring, so every
mapping rule in section 5 is needed with or without it, and a few things are
slightly harder: the rprint adds a method-level decreases that must be
dropped, `{:trigger}` attributes and binder types that must be skipped, and
in refused constructs (`match`) even a comment. `(a && b) && c` and `a && (b
&& c)` become indistinguishable, which is harmless because t's n-ary `and`
has the same left-to-right short-circuit meaning as both.

Price: one dafny process per program (0.57 s median, section 1.7), and a
version dependency: the lifter's parser is written against the printer of
Dafny 4.11.0. This is acceptable because dafny 4.11.0 is one of the seven
kernels, its version is the one AGREEMENT.md line 22 records (`dafny
4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2`), RUN-ON-WINDOWS.md pins
the same version for the Windows box, and verifiers/dafny.py already invokes
`--rprint` on every verification run and reads the printed declarations
back (its certificate door). A Dafny upgrade that changes the printer would
have to be measured against the round-trip tests of section 12 the same way
the verifier adapter is re-measured; the lifter records the version string
in every lift record so a table can never mix two printers.

## 3. Architecture

Modules (one file each under t/lifter/, stdlib only, Windows-safe: every
subprocess uses `--flag=value` or `--flag:value` forms as Dafny accepts them,
`--rprint:PATH` here; text is read with `encoding="utf-8", errors="replace"`
and written with `newline="\n"`):

1. `normalise.py`: runs `dafny resolve FILE --allow-warnings --rprint:OUT`
   under a wall timeout, returns (exit, stdout, text or None). MAY decide:
   nothing. It records exit code, the Dafny version string, and whether
   stdout says `parse errors detected` or `resolution/type errors detected`.
   Exit != 0 is a refusal (`dafny-parse-error` or `dafny-resolve-error`)
   carrying Dafny's first error line; the output file is not read.
2. `lex.py`: tokenizer for the rprint text: nested block comments and line
   comments dropped (this removes the `_System` preamble and the
   `// FILE.dfy` header), integers (decimal; a `0x` literal is a token the
   parser refuses), identifiers including `'` and `?`, and the fixed operator
   set (`<==>`, `==>`, `<==`, `&&`, `||`, `==`, `!=`, `<=`, `>=`, `<`, `>`,
   `+`, `-`, `*`, `/`, `%`, `!`, `:=`, `:|`, `::`, `..`, `|`, brackets,
   `,`, `;`, `:`, `.`). Attribute groups `{:` ... `}` are lexed as one
   token the parser skips. MAY decide: nothing.
3. `parse.py`: recursive descent over the grammar of section 4, producing a
   Dafny-side AST (section 4). Every token sequence outside the grammar is a
   refusal naming the construct (`match`, `set`, `map`, `array`, `real`,
   `..` slice, `[` display, `old(`, `*` havoc, `:|`, `for`, `break`,
   `return` not in tail position, `class`, `module`, `datatype`, `newtype`,
   `type`, `iterator`, `import`, `include`, `print`, `expect`, `bv`,
   `string`, `char`, `as`, `->`, `=>`). Dafny's own precedence table is
   implemented so `parse(print(P))` is Dafny's own AST shape. MAY decide:
   what is in the grammar; nothing about meaning.
4. `select.py`: from the AST picks the gradable methods (a `method` with at
   least one `ensures`, not named `Main`), drops lemmas, drops `Main` and
   methods without an ensures that nothing lifted calls, builds the
   function call graph, marks the functions transitively reachable from each
   gradable method's contract, invariants and body, and orders them
   topologically (t: a spec_fun calls itself and EARLIER spec_funs only; a
   cycle of length 2 or more is `mutual-recursion`). MAY decide: which
   declarations are part of a task; refuses `zero-returns`, `multi-return`,
   `method-call` (a lifted method calls a non-lemma method), `multi-method`
   only under the policy in section 15 (default: one task per gradable
   method).
5. `lift.py`: the mapping rules of section 5, including nat handling
   (section 6), decreases (section 7), name sanitising (section 8), producing
   the t task JSON and a LIFT RECORD: source file, Dafny version, method
   name, rename table, every rewrite applied with its rule name and count
   (`split-conjuncts`, `chain-desugared`, `nat-param-guard`,
   `nat-return-ensures`, `nat-invariant-added`, `spec-fun-totalised`,
   `decreases-inferred`, `decreases-tuple-reduced`, `parallel-assign-temps`,
   `tail-return`, `default-init`, `assert-dropped` with count,
   `lemma-call-dropped`, `function-ensures-dropped`, `unused-function-
   dropped`, `main-dropped`, `iff-to-eq`, `in-desugared`), and the loop and
   function decreases with their origin (`stated` or `inferred`). MAY decide:
   only what the rules say; a construct with no rule is a refusal, never a
   best effort.
6. `check.py`: runs `fuzz_lower.check_wf` (must be empty), `interp.Reference`
   (records `n_req` and the number of points with a value; `n_req == 0` is
   recorded as `interp-no-input`, points == 0 as `interp-real-undefined`,
   both are refusals of the TASK by the existing t rules, not of the lift),
   and `harness.twin_for` (records operator and witness, or the REFUSED
   reason). MAY decide: nothing new; it applies t's own instruments.
7. `census_compare.py`: joins the lift outcomes with census.json by file
   name and prints the disagreement table: census in_fragment vs lifter
   lifted; for every disagreement, the census gap list and the lifter's
   refusal reason or the rule that handled the construct, and a verdict
   column filled by reading the program (section 11 says how each class is
   decided).
8. `lift_corpus.py`: the driver over a directory; parallelism by thread pool
   of dafny processes (4 workers measured fine on the shared box); writes
   `out/lift/<file>.json` (task), `out/lift/<file>.record.json`, and the
   table.

Data flow: .dfy -> normalise (text) -> lex -> parse (Dafny AST) -> select
(per-method units) -> lift (t task + record) -> check (t instruments) ->
compare (table). A refusal at any stage is a record with `reason`, the
stage, and the Dafny line where available (rprint line numbers refer to the
rprint file, which is kept beside the record so the quote can be checked).

## 4. What the parser accepts

The grammar is the subset of Dafny 4.11.0's printer output that the lifter
can lift or must recognise to refuse by name. Everything not derivable here
is a `parse-refusal` naming the offending token.

```ebnf
Program    ::= { Decl }
Decl       ::= Function | Method | Lemma | Refused
Refused    ::= ("class" | "trait" | "datatype" | "codatatype" | "newtype" | "type"
              | "module" | "import" | "include" | "iterator" | "const" | "export"
              | "least" | "greatest" | "twostate" | "abstract") ...      (* named refusal *)
Function   ::= ["ghost"] ("function" | "predicate") {Attr} Id [TypeParams] "(" Params ")"
               [":" ResultType] {FunClause} ( "{" Expr "}" | (empty) )        (* (empty) = bodyless-function *)
ResultType ::= Type | "(" Id ":" Type ")"
FunClause  ::= "requires" Expr | "ensures" Expr | "reads" Frame | "decreases" ExprList
Method     ::= "method" {Attr} Id [TypeParams] "(" Params ")" ["returns" "(" Params ")"]
               {MethClause} ( Block | (empty) )                                (* (empty) = bodyless-method *)
MethClause ::= "requires" Expr | "ensures" Expr | "modifies" Frame | "decreases" ExprList
Lemma      ::= "lemma" {Attr} Id "(" Params ")" {MethClause} [Block]     (* dropped whole *)
Params     ::= [ Param { "," Param } ]
Param      ::= ["ghost"] Id ":" Type
Type       ::= "int" | "nat" | "bool" | "seq" "<" Type ">" | Other       (* Other: named refusal:
                 array, array2, set, iset, multiset, map, imap, string, char, real, bv*, ORDINAL,
                 a datatype or type-parameter name, "(" tuple, "->" *)
Block      ::= "{" { Stmt } "}"
Stmt       ::= Lhs { "," Lhs } ":=" Rhs { "," Rhs } ";"                  (* parallel assign *)
             | "var" VarDecl { "," VarDecl } [ ":=" Rhs { "," Rhs } ] ";"
             | "if" Expr Block [ "else" ( IfStmt | Block ) ]
             | "if" "{" ... "}" | "if" "*"                                (* nondet, refused *)
             | "while" Expr {LoopClause} Block
             | "while" "*" ...                                            (* nondet, refused *)
             | "for" ...                                                  (* for-loop, see 5 *)
             | "return" [ Expr { "," Expr } ] ";"
             | "assert" Expr ( ";" | "by" Block )                         (* dropped *)
             | "calc" ... "}"                                             (* dropped *)
             | "assume" Expr ";"                                          (* refused *)
             | "ghost" "var" ...                                          (* refused *)
             | Id "(" Args ")" ";"                                        (* lemma call: dropped;
                                                                             method call: refused *)
             | "break" | "continue" | "label" | "forall" | "match" | "print" | "expect"
             | "reveal" | ":|" | "modify" | "yield"                       (* refused by name *)
Lhs        ::= Id | Id "[" Expr "]" | Id "." Id                           (* index/field: refused *)
Rhs        ::= Expr | "*" | "new" ...                                     (* * and new: refused *)
VarDecl    ::= Id [ ":" Type ]                                            (* rprint always has : Type *)
LoopClause ::= "invariant" Expr | "decreases" ExprList | "modifies" Frame
ExprList   ::= Expr { "," Expr }                                          (* > 1 element: tuple *)
Expr       ::= Equiv
Equiv      ::= Implies { "<==>" Implies }                                 (* associative *)
Implies    ::= Or [ "==>" Implies ] | Or { "<==" Or }                     (* ==> right-assoc *)
Or         ::= And { "||" And }
And        ::= Rel { "&&" Rel }                                           (* && and || never mix
                                                                             without parens *)
Rel        ::= Add { RelOp Add }                                          (* chain: all of {==,<,<=}
                                                                             or all of {==,>,>=}; a
                                                                             lone != or in/!in *)
RelOp      ::= "==" | "!=" | "<" | "<=" | ">" | ">=" | "in" | "!in" | "!!"
Add        ::= Mul { ("+" | "-") Mul }
Mul        ::= Unary { ("*" | "/" | "%") Unary }
Unary      ::= "-" Unary | "!" Unary | Postfix
Postfix    ::= Primary { "[" Expr "]" | "[" [Expr] ".." [Expr] "]" | "(" Args ")"
                       | "." Id | "as" Type }                             (* slice, ., as: refused *)
Primary    ::= Int | "true" | "false" | Id | "(" Expr ")" | "|" Expr "|"
             | "if" Expr "then" Expr "else" Expr
             | ("forall" | "exists") Binders [ "|" Expr ] "::" Expr
             | "[" ... "]" | "{" ... "}" | "map" ... | "set" ... | "old" "(" ...
             | "*" | "fresh" | "unchanged" | "this" | Lambda            (* each a named refusal *)
Binders    ::= Binder { "," Binder }
Binder     ::= Id [ ":" Type ] {Attr}                                     (* rprint: Id ": int" and
                                                                             {:trigger ...} *)
Attr       ::= "{:" ... "}"                                               (* skipped everywhere *)
Id         ::= [A-Za-z_][A-Za-z0-9_'?]*                                   (* Dafny's; sanitised in 8 *)
```

Dafny-side AST produced (Python dicts, one tag per node):

- Program: functions [Function], methods [Method], lemmas [name], refused
  [(construct, line)].
- Function: name, ghost, params [(name, type)], result type, requires
  [Expr], ensures [Expr], reads present?, decreases [Expr] (list; length >
  1 is a tuple), body Expr or None, line.
- Method: name, params, returns [(name, type)], requires, ensures,
  decreases [Expr] (dropped unless self-recursive), body [Stmt] or None.
- Stmt: Assign(targets [Lhs], rhss [Expr]); VarDecl([(name, type, init or
  None)]); If(cond, then [Stmt], else [Stmt] or None); While(cond,
  invariants [Expr], decreases [Expr] or None, body); Return([Expr]);
  Assert; Calc; Call(name, args); Refused(kind, line).
- Expr: Int(n); Bool(b); Var(name); Neg(e); Not(e); Bin(op, a, b) with op
  in {+, -, *, /, %, ==, !=, <, <=, >, >=, in, !in}; Chain([ops],
  [operands]); And([...]); Or([...]); Implies(a, b); Iff(a, b); Ite(c, t,
  e); Card(e) for `|e|`; Index(s, i); Call(f, args); Quant(kind,
  binders [(name, type)], range Expr or None, body); Refused(kind, line).

## 5. Mapping rules (Dafny construct -> t construct)

Conventions: `int`-typed means the Dafny resolver typed it `int` or `nat`
(rprint shows the declared type; expression types follow from the leaves
since t has no other numeric type). "Split" means top-level `&&` in a
requires, ensures or invariant becomes several clauses in source order.
Every rule that rewrites records its name in the lift record.

| # | Dafny (as rprint prints it) | t | condition | meaning argument |
|---|---|---|---|---|
| 1 | `method M(p: T, ...) returns (r: T)` with >= 1 `ensures` | task `name: M'` (sanitised), params, one return | exactly one return of type int, nat or bool; params of type int, nat, bool, `seq<int>`, `seq<nat>` | t's task is one method with one return; the contract is the same theorem "requires implies ensures after body" that Dafny grades. |
| 2 | `function F(p: int/nat/seq<int>, ...): int/nat/bool` or `predicate P(...)`, `ghost` or not, with a body, no `reads`, reachable from the task | spec_fun with `result` int or bool, body lifted as an Expr | params int/nat/seq; result int/nat/bool; body in the Expr fragment; single decreases after section 7; no `reads`; no type parameters | A Dafny function is a pure total function of its parameters on its domain; a spec_fun denotes the unique solution of the same defining equation, and both kernels grade calls by the same equation. |
| 3 | function with `requires R` (a partial function) | totalised: body becomes `ite(not R, D, body)`, D = `0` for int, `false` for bool; record `spec-fun-totalised` | R lifts as an Expr over the params | On R's domain the lifted function equals the source function (the wrapper is the identity there); every call the SOURCE program makes is inside R (Dafny proved the requires at each call), so every value the spec talks about is unchanged. Outside R the source is undefined and the lift returns D: a weakening of definedness, recorded (section 6). |
| 4 | function with `ensures E` | dropped; record `function-ensures-dropped` | always | A function's ensures is a lemma about it, not part of its definition; the function's value is fixed by its body, so the task's theorem is unchanged and only proof help is lost (honest UNPROVED, never a wrong VERIFIED). |
| 5 | function unreachable from the task's contract, invariants and body | dropped; record `unused-function-dropped` | reachability computed on the AST | A definition nothing mentions cannot change what is proved. |
| 6 | `requires A && B` (top-level `&&`) | two requires clauses `A`, `B` in order; same for ensures and invariant | always | SPEC: clauses are conjoined and checked left to right each assuming the earlier ones; Dafny's `&&` is left-to-right short-circuit; both give the same truth value and the same definedness obligations. |
| 7 | chained comparison `a <= b < c` (or any chain Dafny accepts) | `and(a <= b, b < c)` (one `and` node; the middle operand duplicated) | operands are pure (they are: t has no side effects) | Dafny defines a chain as the conjunction of adjacent comparisons; duplicating a pure expression evaluates to the same value and the second copy's definedness follows from the first's. |
| 8 | `A ==> B` | `implies(A, B)` | always | Same operator, same short-circuit definedness (SPEC: q need only be defined when p holds). |
| 9 | `A <== B` | `implies(B, A)` | always | Dafny defines `<==` as reversed implication. |
| 10 | `A <==> B` | `==(A, B)` on two bools | both sides bool | Dafny's `<==>` is boolean equality; t's `==` on two bools is boolean equality; both sides are strict in both languages. |
| 11 | `A && B && C`, `A \|\| B \|\| C` in expression position | n-ary `and`/`or` (flattened) | always | Dafny's binary nesting and t's n-ary node both mean left-to-right short-circuit conjunction; the printer already hides the bracketing because it does not matter. |
| 12 | `!A` | `not(A)` | always | Same. |
| 13 | `-E` | `neg(E)`, except `-<digits>` which is the literal `{"int": -n}` | always | Dafny prints both `-5` and `-(5)` as `-5`; both denote the integer -5; interp evaluates `neg(5)` and `-5` identically, and surface.py reads `-5` as the literal. |
| 14 | `+ - *` on ints; `== != < <= > >=` on ints; `== !=` on bools | same op | operands int (for order ops) | Mathematical integers on both sides (SPEC integer semantics; Dafny's int is unbounded). |
| 15 | `/`, `%` | refuse `div-mod` | always | t has no division (SPEC). |
| 16 | `\|s\|` | `len(s)` | s is a seq | Same. |
| 17 | `s[i]` | `at(s, i)` | s is a seq param | Same partial operator; Dafny checks `0 <= i < \|s\|` as well-formedness, t makes it a definedness obligation every lowering discharges. |
| 18 | `s[a..b]`, `s[..b]`, `s[a..]`, `s + t`, `s == t`, `[..]` displays, `s[i := v]` | refuse `seq-slice`, `seq-concat`, `seq-equality`, `seq-literal`, `seq-update` | always | t has no seq-valued expressions except a parameter. Exception, policy (section 15): `s != []` and `s == []` where one side is the empty display may lift to `len(s) != 0` / `len(s) == 0`; default: refuse `seq-literal`. |
| 19 | `x in s`, `x !in s` (s a seq) | `exists j in [0, len(s)) . at(s, j) == x`, and `not` of it; j fresh | policy default ON (section 15) | Dafny defines seq membership as exactly this bounded existential; the bound variable is fresh so no capture. |
| 20 | `if c then a else b` (expression) | `ite(c, a, b)` | always | Same lazy conditional (SPEC: the taken branch only). |
| 21 | `forall k :: R ==> B`, `forall k \| R :: B`, `exists k :: R && B`, `exists k \| R :: B`, binder typed int or nat or untyped | `forall k in [lo, hi) . B'` / `exists k in [lo, hi) . B'` | R's top-level conjuncts (chains split) contain, on the bare variable k, one lower bound (`lo <= k`, `lo < k` gives `lo + 1`, `k == e` gives `[e, e+1)`) and one upper bound (`k < hi`, `k <= hi` gives `hi + 1`); a nat binder supplies `0 <= k`; lo and hi mention only names in scope outside the quantifier; leftover conjuncts L stay in the body as `implies(L, B)` (forall) or `and(L, B)` (exists) | The set of k satisfying the range conjuncts is exactly the half-open integer interval [lo, hi); the leftover conjuncts keep their position relative to B so the body is evaluated for a value of k exactly when Dafny would evaluate it, preserving definedness of `at` inside B. Two binders `forall i, j :: 0 <= i < j < \|s\| ==> B` become nested quantifiers with j's range `[i + 1, \|s\|)` and i's `[0, \|s\|)`; equivalence because `i < j < \|s\|` implies `i < \|s\|`, so no (i, j) pair is added or lost. Anything else: refuse `unbounded-quantifier`. |
| 22 | `requires`, `ensures` on the method | requires list, ensures list, split per rule 6, in source order, after the nat guards of section 6 | always | Order matters only for definedness (SPEC), and the nat guards come first because the source's clauses were well-formed under the nat typing they encode. |
| 23 | `old(E)`, `fresh`, `unchanged`, `modifies` | refuse `heap` (`old` recorded as its own reason `old-expression`) | always | No heap in t. |
| 24 | `while G invariant I1 ... decreases D { body }` | `while` with `cond`, invariants split per rule 6, decreases per section 7, body | G lifts as bool Expr; D lifts to one int Expr | Same partial-correctness-plus-termination package: Dafny checks invariants on entry, preservation, exit with negated guard, and decreases >= 0 and strictly decreasing, exactly SPEC gate 2. Frame: Dafny havocs the loop's assigned variables (its loop targets), which is SPEC's frame rule verbatim. |
| 25 | `while G` with an EMPTY invariant list | invariants `[]` | always | SPEC allows an empty list; meaning identical. |
| 26 | `for i := lo to hi invariant ... { body }` | `var i := lo; var h := hi; while i < h invariant lo <= i and i <= h, <stated>, decreases h - i { body; i := i + 1 }` with h fresh | body contains no `break`/`continue`/`return` and does not assign i; `to` form only (`downto` refused `for-downto`) | Dafny evaluates the bound once at entry (hence the snapshot h), forbids assignment to the index, iterates i over [lo, hi), and supplies `lo <= i <= hi` as an implicit invariant; the desugaring states exactly those facts. Not exercised by the 77 (0 for loops); the 5 for-loops in the refusal samples are the first test material. |
| 27 | `var x: T := e;` | `{"var": {"name": x, "type": int/bool, "init": e}}` | T int/nat/bool | Same scoped local with the same initial value; nat handled by section 6. |
| 28 | `var x: T;` (no initialiser) | init `0` (int) or `false` (bool); record `default-init` | always | Dafny's definite-assignment check guarantees the source reads x only after assigning it, so no execution observes the initial value; the lift picks one. |
| 29 | `var a: int, b: int := e1, e2;` | `var a := e1; var b := e2;` in order | the initialisers do not mention a or b (they cannot: not yet in scope) | Simultaneous evaluation of independent pure expressions equals sequential evaluation. |
| 30 | `a, b := e1, e2;` (parallel assignment) | if no RHS reads any target: sequential assigns in order; else `var t0 := e1; var t1 := e2; a := t0; b := t1;` with fresh t0, t1; record `parallel-assign-temps` | targets are distinct simple names (a repeated target is a Dafny error already) | Dafny evaluates all right-hand sides before any assignment; the temporaries realise exactly that order. |
| 31 | `x := e;` where x is the return or a local | `assign` | always | Same. |
| 32 | `if c { S } else { T }` | `if` with then/else lists | always | Same. |
| 33 | `if c { S }` (no else) | `if` with `else: []` | always | Dafny's missing else is the empty block; SPEC allows an empty else. |
| 34 | `if c1 { S } else if c2 { T } else { U }` | nested `if` in the else list | always | Dafny parses `else if` as an if statement in the else branch; the print keeps the chain, the AST is the nesting. |
| 35 | `if { case g1 => S1 case g2 => S2 }` (guarded alternatives) | refuse `nondet` | always | Dafny picks any alternative whose guard holds; when two hold the choice is nondeterministic and t has no nondeterminism. (Even when the guards are provably exclusive the lifter does not decide that; a kernel would have to.) |
| 36 | `return;` as the last statement of the method body or of a branch of an if that is itself last (recursively) | dropped | tail position, computed on the AST | Falling off the end returns the current value of the out-parameter; a tail `return;` does the same. |
| 37 | `return e;` in tail position | `assign(r, e)` | exactly one return value | Dafny's `return e` assigns e to the out-parameter and exits; at tail position nothing follows, so the assignment alone has the same effect. |
| 38 | `return` anywhere else, `break`, `continue`, labels | refuse `early-exit` | always | t has no early exit; a rewrite would restructure control flow, which is a body change the lifter must not make. |
| 39 | `assert E;`, `assert E by { ... }`, `calc { ... }` | dropped; record `assert-dropped` with count | always | SYNTAX.md: hints, not constructs; they do not change what the program computes or what its contract states, only what the kernel is told along the way. |
| 40 | `assume E;` | refuse `assume-in-body` | always | An assume is an axiom inside the proof; dropping it changes the theorem the kernel must prove, keeping it is unsound. |
| 41 | `L(args);` where L is a `lemma` declared in the file | dropped; record `lemma-call-dropped` | always | A lemma call has no effect on state; it is proof scaffolding (SYNTAX.md). |
| 42 | `M(args);` or `x := M(args);` where M is a `method` | refuse `method-call` | M is not the lifted method itself | t has no inter-method calls; the callee's contract would have to be trusted. |
| 43 | a call of the lifted method itself in the body | `call` of the task name; the task's `decreases` from the method's stated or inferred clause after section 7 | direct self-recursion only | SPEC gate 3: a self-call denotes a value about which exactly the contract is known, which is Dafny's modular treatment of a recursive method call; Dafny's method-level decreases is the same measure obligation. (0 of the 77 self-call.) |
| 44 | a function called both from `ensures` and from the body | one spec_fun, called in both places | always | SPEC allows spec_fun calls in bodies; Dafny lets compiled functions be called in code and ghost functions in ghost contexts, and in the corpus a function called in a body is compiled. |
| 45 | `ghost var`, `ghost` locals, `ghost` params | refuse `ghost-var` | always | A ghost local may feed the invariants; dropping it breaks them, keeping it makes it real. |
| 46 | `method Main` (no ensures) | dropped; record `main-dropped` | always | A harness computes nothing the gradable method's contract mentions. |
| 47 | other methods without an ensures, uncalled | dropped; record `method-dropped` | not called by any lifted method | Same as 46. |
| 48 | two or more gradable methods | one task per method (policy, section 15); program row counts only when every task counts | no method calls a method | Each method's theorem is independent of the others (calls are refused). |
| 49 | a method with no `returns` | refuse `zero-returns` | always | t has exactly one return. |
| 50 | `returns (a: int, b: int)` | refuse `multi-return` | always | Same. |
| 51 | `nat` in any position | section 6 | | |
| 52 | `E as int`, `E as nat` where E is int-typed | `E` | E int or nat typed | Identity conversion between int and its subset type. Any other `as`: refuse `as-cast`. |
| 53 | identifiers | section 8 (sanitised, rename recorded) | | alpha-renaming, injective per task |
| 54 | `type` parameters, `class`, `trait`, `datatype`, `match`, `set`, `map`, `array`, `real`, `string`, `char`, `bv`, `->`, `=>`, `module`, `import`, `include`, `iterator`, `newtype`, `type`, `print`, `expect`, `reveal`, `opaque`, bodyless function or method, `decreases *`, `least/greatest predicate`, `:|` | refuse with the census gap name (section 9) | always | Outside t. |

## 6. nat handling: which theorem the kernels should prove

A Dafny `nat` is the subset type `{x: int | 0 <= x}`. It acts in three ways:
as an ASSUMPTION wherever a nat-typed name is read (params on entry, locals
and returns at every program point after their assignment, function results
at every call), as an OBLIGATION wherever a nat-typed slot is written
(argument positions, assignments to nat locals and returns, function bodies
whose result is nat), and as a DOMAIN restriction on functions. t has no
subset types, so each role is rendered separately, and each rendering is
recorded in the lift record so the disagreement table can say `nat-...`.

The theorem wanted: for every int assignment to the parameters satisfying
the lifted requires (which includes `p >= 0` for each nat parameter), the
lifted body's result satisfies the lifted ensures (which includes `r >= 0`
for a nat return), where every spec_fun agrees with the source function on
the source function's domain. This is the source's partial-correctness
theorem on the source's own input domain, strengthened by the non-negativity
the source guaranteed by typing its return, and weakened by dropping the
intermediate typing obligations (a nat local or a nat argument momentarily
negative). The weakening is stated, not hidden: on the 785 ground-truth
programs every source verifies, so no intermediate obligation is violated by
a REAL body; the difference can only show on a TWIN, where a twin that
drives a nat below zero would be refuted by Dafny's typing in the source and
might verify in the lift if no ensures or invariant catches it. That is a
lifted spec weaker than the source, the direction section 11 watches for,
and the rules below add exactly the facts needed to close it where the
source's spec itself relied on them.

Rules:

- nat method parameter `p: nat` -> `p: int` and `requires p >= 0` PREPENDED
  before the source's requires, in parameter order. Record `nat-param-
  guard`. The guard comes first because the source's own requires were
  well-formed under the typing (`requires 1 <= n` followed by `Fat(n)` needs
  n >= 0 known first).
- nat method return `r: nat` -> `r: int` and `ensures r >= 0` PREPENDED
  before the source's ensures. Record `nat-return-ensures`. Prepending keeps
  the source clauses' definedness context (they could assume r >= 0).
- nat local `var x: nat := e` -> int local, plus, for every `while` whose
  body assigns x (transitively, per interp.assigned), the invariant `x >= 0`
  APPENDED to that loop's invariant list; the same for a nat return assigned
  in a loop. Record `nat-invariant-added`. Appending puts the source's own
  invariants at the earlier ladder sites, so INVARIANT-DROP site 0 is still
  a source invariant. Why add it at all: Dafny keeps `x >= 0` across the
  loop by typing, and the source's proof may need it (fatorial2's `f >= 0`
  after the loop is not derivable from `f == Fat(i - 1)` once Fat is an int
  function; measured, the lifted task verifies with the invariant). Where
  it is not needed it is harmless (integer_square_root verified with and
  without it, section 1.9). An unassigned nat local needs nothing: SPEC's
  frame rule preserves it.
- nat function parameter `F(n: nat)` -> int parameter, and the function body
  is totalised exactly as a `requires n >= 0` would be (rule 3): `ite(n < 0,
  D, body)`, D = 0 or false. Several nat params and a requires combine into
  one guard `not(n1 >= 0 and n2 >= 0 and R)`. Record `spec-fun-totalised`.
  Why not rewrite the base case (`n == 0` to `n <= 0`, as tasks/factorial.json
  does by hand): that is pattern-matching on the body; the wrapper is one
  rule for every shape and provably the identity on the domain. Termination
  under the wrapper: the source's recursive calls sit in branches where
  Dafny proved the arguments are nats smaller than the measure; the wrapper's
  else-branch is entered only for arguments in the domain, so the kernel
  re-proves `measure(args) >= 0 and < measure(params)` from the same path
  conditions (measured on `ExptT`, section 1.10, and on `fat`, `even`,
  `stairs`, section 1.9).
- nat function result `F(...): nat` -> `result: int`. The fact `F(x) >= 0`
  that Dafny gets from the signature is lost; nothing is added (t has no
  spec_fun ensures). Record `nat-result-fact-dropped`. A proof that needed
  it reads UNPROVED, never wrong.
- nat elements `seq<nat>` -> `seq` (elements are ints) and NO constraint is
  added: t has no way to state `forall j. s[j] >= 0` at the parameter, and
  adding a requires would be an invented clause. Refuse `nat-seq-elements`
  unless the parameter is read only through `len`; policy in section 15.
- nat in a quantifier binder `forall k: nat | k < hi` -> lower bound 0 (rule
  21).

Alternatives considered and why not default: refusing every nat program
(30 of the 77 carry a nat; the theorem above is exactly what those authors
meant); lifting nat params without the requires (would let the kernel see
inputs the source excluded, and every factorial-like task would then be
false: `Fat(-1)` versus a loop that never runs); adding the nat return
ensures LAST instead of first (only definedness order differs; no case in
the 77 depends on it).

## 7. decreases: stated, inferred, tuple, missing

t requires a `decreases` on every loop and every spec_fun, and on the task
iff its body self-calls. The lifter takes measures from the rprint only;
it never invents one:

1. A `decreases` line under a `while` or on a `function` in the rprint is
   the measure (stated by the author or inferred by Dafny; the lift record
   says which by comparing with the source text's `decreases` keyword at
   that declaration, or simply records `origin: rprint`). Single-element:
   lift the expression (it is an int expression over names in scope; the
   `!=` shape `if a <= b then b - a else a - b` lifts to an `ite`, which t
   has, measured verified on Cube). Applies to guards `<`, `<=`, `>`, `>=`,
   `!=` (section 1.5), and to any stated single expression.
2. Tuple (a comma at depth 0): reduce by dropping every component that is a
   bare parameter passed unchanged in the same position at every self-call
   (functions), or a bare variable the loop body never assigns (loops).
   Rationale: a lexicographic tuple whose component is constant across every
   step decreases iff the remaining components do, so the reduced tuple is
   an equivalent measure. If exactly one component remains, it is the
   measure; record `decreases-tuple-reduced`. Measured: Dafny accepts `n`
   for `Expt(b, n)` whose inferred tuple was `b, n` (section 1.10). Over the
   77 this reduces `Potencia(x, y)` to `y` (three files), `pow(a, e)` to `e`,
   `Expt(b, n)` to `n`, and fails for `gcd(x, y)` (calls `gcd(x - y, y)` and
   `gcd(x, y - x)`: no component fixed in both) and for SlowMax's loop
   `decreases x, y` (both assigned).
3. Otherwise refuse `decreases-tuple` (the tuple survived reduction) or
   `decreases-uninferable` (no decreases line: Dafny inferred nothing, which
   happens for `||`, `!b` and bool guards and for-loops; a verifying source
   then has a stated measure, so this reason fires only when the source
   relied on `decreases *` or the like). Neither occurs in the 77.
4. Non-recursive function: Dafny prints the parameter tuple as a default
   (`max(x, y)` gets `decreases x, y`). t still requires a measure, and with
   no self-call there is no obligation, so the lifter emits `{"int": 0}` and
   records `decreases-nonrecursive-zero`. Meaning: no self-call, no
   termination proof to change.
5. Method-level decreases: dropped unless the body self-calls (rule 43), in
   which case rule 2 applies to it; check_wf rejects a task decreases
   without a self-call.
6. Opt-in, off by default (section 15): `--candidate-measure`. When rule 2
   fails, try, in order, the first tuple component alone and the sum of all
   components; for each candidate rewrite the DAFNY SOURCE with that
   decreases and run `dafny verify`; accept the first candidate Dafny
   verifies and record `decreases-candidate-dafny-verified`. Measured: this
   lifts SlowMax (`decreases x`) and both gcd files (`decreases x + y`). It
   is off by default because the measure is then the lifter's, not the
   author's or Dafny's own inference, even though it changes no value the
   spec talks about.

## 8. Names: sanitising and the rename table

t names match `[A-Za-z][A-Za-z0-9_]*` and may not be surface.py keywords
(`t gate task returns requires ensures decreases spec fun var while invariant
if then else forall exists in len true false and or not int bool seq`);
lower_fstar refuses its RESERVED set and any name whose initial is not
lowercase; lower_rocq refuses its RESERVED set and any name ending in `_len`
or starting `sf_` or `t_`; lower_spark refuses, case-insensitively, `F Seq
Seqs Len Elem T_Range R_First R_Has R_Next Big_Integer Boolean
T_Refutation_Certificate`; lower_dafny refuses a task that mentions
`t_refutation_certificate`. Measured over the 77 rprints: 64 files have an
uppercase-initial name (methods `Abs`, `ClimbStairs`, functions `Fat`,
`Stairs`, params `N`), 5 have a name colliding case-insensitively with
spark's `F` (`function F` in appeal_20_p4, return `f` in fatorial2, p5, p6,
fibonacci), 2 have a primed name (`gcd'`), 0 collide with a keyword list;
68 of 77 need at least one rename.

Sanitiser, applied to every declared name in a task (task name, params,
return, locals, spec_funs and their params, bound variables), in
declaration order, deterministic:

1. replace each `'` by `_p` and each `?` by `_q`; drop a leading `_` by
   prefixing `v` (`_x` -> `v_x`);
2. lowercase the first character;
3. while the result is in the union of the reserved sets above
   (case-insensitively), or matches rocq's patterns, or equals a name
   already taken in the task, or equals a fresh-name shape the lifter
   itself uses (`t<digits>`, `j<digits>`, `h<digits>`): append `_1`, then
   `_2`, ...

The rename table (`source name -> t name`, per scope) goes into the lift
record; the disagreement table and every refusal quote source names, and
the task JSON carries a `"source": {"file": ..., "method": ..., "renames":
{...}}` block only in the record, never in the task (check_wf does not know
the key and the task must stay a plain t task). Fresh names for temporaries
(`t0`), membership binders (`j0`) and for-loop bounds (`h0`) are drawn from
a supply that avoids every string in the task (lower_dafny._collect_names
does the same), so no shadowing is possible (SPEC: a bound variable may not
collide with any name in scope; check_wf: a local may not shadow).

## 9. Refusal rules

Every refusal names one reason (the first, in reading order of the rprint:
declarations top to bottom, then clauses, then body) and quotes the rprint
line. Census gap names are reused where the construct is the same.

| reason | trigger | census equivalent |
|---|---|---|
| dafny-parse-error | `dafny resolve` exit 2 with `parse errors detected` (no output file) | none (the census tags text it cannot parse) |
| dafny-resolve-error | exit 2 with `resolution/type errors detected` | none |
| dafny-timeout | the resolve process hit the wall timeout | none |
| not-gradable | no `method` with an `ensures` (lemma-only, function-only, Main-only files) | method-with-ensures false |
| zero-returns | a gradable method without `returns` | zero-returns |
| multi-return | `returns (a, b)` | multi-return |
| multi-method | two or more gradable methods, only under the reversed policy of section 15 | multi-method |
| method-call | a lifted method calls a `method` (not a lemma) | multi-method (census's nearest) |
| array | `array<T>`, `.Length`, `new T[...]` | array |
| array-mutation | `a[i] := e` | array-mutation |
| div-mod | `/` or `%` in a lifted expression | div-mod |
| seq-slice | `s[a..b]` | seq-slice |
| seq-literal | `[...]` display (except the policy exception on `!= []`) | seq-literal |
| seq-concat | `s + t` on seqs | none (census reads `+` as int) |
| seq-equality | `s == t` on seqs | none |
| seq-update | `s[i := v]` | seq-update |
| seq-return | a seq-typed return or function result | seq-return |
| nested-seq | `seq<seq<..>>`, `seq<T>` with T not int/nat | nested-seq |
| nat-seq-elements | `seq<nat>` read other than through `len` (policy) | none (census: nat burden) |
| set / map / string-char / real / bitvector / datatype / heap / higher-order / generics / tuple / type-decl / io / iterator / module / function-method / bodyless-function / bodyless-method / extreme-predicate / decreases-star / char-arith / such-that-exec | the corresponding token or declaration | same name |
| old-expression | `old(...)` | heap (census: `old` hint) |
| nondet | `x := *`, `if *`, `while *`, `if { case ... }` | nondet |
| early-exit | `return` not in tail position, `break`, `continue`, a label | early-exit |
| for-downto | `for i := hi downto lo` | none (census: for-loop burden) |
| unbounded-quantifier | a binder without both bounds per rule 21, a non-int binder type, a `forall` statement | unbounded-quantifier |
| assume-in-body | `assume` in a lifted body | none (census: assume hint) |
| ghost-var | `ghost var` or a ghost parameter of a lifted method | none (census: ghost-var hint) |
| mutual-recursion | a call cycle of length >= 2 among reachable functions | mutual-recursion |
| function-reads | a reachable function with a non-empty `reads` | frame-clause (burden) |
| decreases-tuple | a tuple measure that section 7 cannot reduce | none |
| decreases-uninferable | a loop or recursive function with no decreases line in the rprint | while-no-decreases (burden) |
| as-cast | `as` to anything but int/nat from int/nat | as-cast (burden) |
| name-unsanitisable | a name the sanitiser cannot make legal (does not occur: the procedure always terminates) | none |
| parse-refusal | any token sequence outside section 4's grammar, with the token named | none |
| interp-no-input, interp-real-undefined, twin-no-operator, twin-no-witness, twin-candidate-budget | the task lifted and passed check_wf but t's own instruments refuse it (harness.REFUSALS) | none: these are t verdicts, reported in their own column, not lift refusals |

## 10. Expected lift of the 77 census in-fragment programs: 74

Grounded in the inventory (77 records) and the rprint survey (section 1.5):

- Refused under default rules, 3: `Dafny_tmp_tmpmvs2dmry_SlowMax.dfy`
  (`decreases x,y;` on the loop at source line 17, both assigned in the body:
  `x := x - 1; y := y - 1;`, section 7 rule 2 fails: `decreases-tuple`);
  `Programmverifikation-..._ex06-solution.dfy` (`ghost function gcd(x:int,
  y:int):int requires x > 0 && y > 0` with no stated decreases; rprint
  infers `decreases x, y`; calls `gcd(x-y,y)` and `gcd(x,y-x)` fix no
  component: `decreases-tuple`; `gcd'` is unused by `gcdI` and would be
  dropped); `..._ex_06_hoangkim.dfy` (same `gcd`; its `gcd'` has a stated
  single measure and is unused).
- Lifted, 74. Every other construct in the inventory's constructs_outside_t
  list has a rule above: nat (30 programs, section 6), loop without decreases
  (23, rule 1 of section 7: all 41 loops have a decreases line), chained
  comparison (23, rule 7), function without decreases (21, rules 1 and 2 of
  section 7: Potencia, pow, Expt reduce; the rest are single), untyped local
  (21, rprint types them), tail return (14, rules 36 and 37), text-level (12,
  gone in the print), function with requires (12, rule 3), uppercase or
  reserved names (68, section 8), assert (8 programs, 57 statements, rule
  39), parallel assignment (7, rule 30, measured on climbing-stairs and
  Cube), `<==>` (5, rule 10), multi-name var (4, rule 29), ghost functions
  (3, rule 2), Main (2, rule 46), else-if (2, rule 34), primes (2, section
  8), uninitialised local (2, rule 28), if without else (2, rule 33), nested
  loops (1, rule 24), function `ensures` (factorial.dfy, rule 4), lemma
  declarations (expt.dfy's bodyless `lemma distributive`, hoangkim: dropped
  whole; a bodyless LEMMA is a hint, not the bodyless-method gap).
- Of the 74, t's own instruments then refuse 2 as `no-operator`
  (`dafny-synthesis_task_id_234.dfy`: `volume := size * size * size`, and
  `_626.dfy`: `area := radius * radius`, straight-line bodies with no
  literal, no if, no loop and one param, so no ladder rung has a candidate),
  and the dafny column will read twin UNPROVED for the preservation-witness
  twins (fatorial2 measured, section 1.9; the inventory names factorial.dfy
  and introducao_ex4.dfy). Those are t verdicts on lifted tasks, not lift
  failures, and they are exactly what the coverage number must stop
  counting.
- With `--candidate-measure` on (section 7 rule 6) the 3 refusals lift
  (measured in Dafny, section 1.10), giving 77.

The count is a prediction from the rules and the inventory, not a
measurement; the implementer's first corpus run replaces it (section 12,
test 9).

## 11. Validation: catching a wrong lift before it corrupts a number

A wrong lift is a task whose theorem differs from the source's. Two
directions, and what each does to the twin discipline:

- Lifted spec WEAKER than the source (a dropped conjunct, a range widened, a
  nat guard omitted, a `<==>` turned into `==>`): the real lowering still
  verifies, and a twin that the source spec would refute may VERIFY, which
  the suite reads as "vacuous spec" and refuses; the program is then
  wrongly counted as out of fragment, or, worse, a weaker spec still refutes
  the chosen twin and the program is counted with a theorem nobody wrote.
- Lifted body DIFFERENT from the source (a parallel assignment sequenced in
  the wrong order, an `else if` misnested, a chain split wrongly, a `-5`
  misread): the real lowering FAILS (verification against the source's spec
  catches it) unless the spec is loose enough to admit the changed body, in
  which case the twin ladder measures a program nobody wrote.

Instruments, in the order they run:

1. Round trip against lower_dafny (the inverse on the fragment). For every
   committed task and every fuzz_lower.build_corpus task: `lift(rprint(
   lower_dafny.lower(task, task["body"]))) == task` as canonical JSON, after
   the two known differences are normalised: the method name (lower_dafny
   capitalises, the sanitiser lowercases the initial, so the round trip is
   the identity on names that start lowercase, which every committed name
   does) and hoisted self-calls (lower_dafny emits `var t0 := Method(args);`
   for a body self-call; the lift reads that back as a local initialised
   with a `call`, an equivalent body with one more local, so the recursive
   tasks are compared by interp on the domain rather than by JSON). What
   this catches: any asymmetry between reading and writing an operator,
   quantifier range, `ite`, n-ary and/or, negative literal, invariant order,
   decreases. What it cannot catch: anything both files get wrong the same
   way (they are written by the same people against the same SPEC), and
   rules with no lower_dafny counterpart (nat, chains, parallel assignment,
   tail return, totalisation), which are covered by the next instruments.
2. Verifiability preservation. For every lifted task, `dafny verify` on the
   task's lower_dafny output must be VERIFIED when the source verified (all
   785 ground-truth programs do, as their name says, and the 77 were
   re-measured). A lifted real that dafny does not verify is a lift the
   kernel rejects: either the body changed, or the spec strengthened, or a
   hint was load-bearing. Each such case is read by a person and classified
   (`hint-load-bearing` is honest UNPROVED; the other two are lifter bugs);
   until classified the program is not counted.
3. Differential execution. For every lifted task, compile the SOURCE method
   to an executable oracle without the lifter's help: `dafny run` is not
   available for every shape (ghost functions), so the oracle is the source
   program's own verified contract evaluated by interp on the lifted
   spec... which is circular. The non-circular oracle: `dafny test`-style
   harnesses are heavy; instead, for programs whose method and functions are
   compiled (non-ghost), emit a Dafny `Main` that prints the method's result
   on the interp domain points of the lifted task (the same `interp.domain`
   the twin uses), run `dafny run`, and compare with `interp.Reference`'s
   values point by point. A body difference shows as a value difference at
   some point; a spec difference does not show here, which is why 4 exists.
4. Spec equivalence spot check by Dafny itself. For each lifted task, emit a
   Dafny lemma per clause: `lemma c_k(params, r) requires <lifted requires>
   ensures <source ensures clause k> <==> <lifted ensures clause k>`, with
   the source's nat types replaced by ints plus the lifted guards, and the
   source's functions and the lifted spec_funs both present (renamed apart).
   Dafny proving the equivalence on the lifted domain is evidence the spec
   is unchanged; a failure is read by a person. This is the only instrument
   that catches a WEAKER spec directly; it is run over every lifted program
   and its verdicts go in the record.
5. Twin measurements: a twin that VERIFIES in dafny on a lifted task is
   investigated before the program's row is written, because on the 11
   committed tasks no dafny twin verifies (AGREEMENT.md) and the inventory
   predicts none in the 77; a verified twin is either a real vacuous spec
   (the source's own, worth a row) or a weakened one (a lifter bug).
6. The disagreement table itself. For every file where census in_fragment
   differs from lifter outcome, a verdict is written by READING THE PROGRAM
   and quoting the line: `census-right` (the lifter refused a construct the
   census also names, or the lifter's grammar is too small), `lifter-right`
   (the census's detector fired on a token in a comment, a lemma or an
   attribute, or missed a construct such as seq concatenation), or
   `policy` (both are right under their own definition; section 15 decides).
   Expected classes from the inventory's 49 refusal samples: 12 lift with a
   rewrite the census calls a gap (read-only array, `values != []`, `x in
   s`, for-loop, string seen only through `|s|`, top-level early return
   rewritable to if/else), 6 are policy, 30 refused with matching names, 9
   refused with a reason the census has no name for (function contracts,
   trait, class, not-gradable).

## 12. Test plan: what the implementer writes first

1. `test_normalise.py`: the three shapes of section 1.1 and 1.2 as fixtures
   (source text and expected rprint user module), exit-code gating (parse
   error -> no file, refusal; resolve error -> file present, refusal;
   warnings -> exit 0 under `--allow-warnings`), version string recorded.
2. `test_lex.py`: nested block comments (the `_System` preamble), `//`
   comments, `{:trigger s[k]}` and `{:split false}` as single tokens, primed
   identifiers, `0x` literal refused, every operator token.
3. `test_parse_precedence.py`: for each line of forms.dfy's rprint (section
   1.6), the AST expected; chained comparisons; `==>` right-associativity;
   `<==>` lowest; `&&`/`||` flattening; `if then else` and quantifier
   extent; `-5` versus `- x`.
4. `test_roundtrip_lower_dafny.py`: section 11 instrument 1 over
   `tasks/*.json` and `fuzz_lower.build_corpus` seeds 1 to 7 (1528 tasks per
   SYNTAX.md); exact JSON equality for non-recursive tasks, interp
   equivalence on the domain for recursive ones.
5. `test_rules.py`: one fixture per mapping rule (sections 5 to 8), each a
   Dafny snippet and the expected t fragment: chain split, top-level `&&`
   split, parallel assign (order-free, needs-temp, three targets),
   multi-name var, tail return (`return;`, `return e;`, inside an if in tail
   position, inside a loop = refusal), if without else, else-if nesting,
   `<==>`, `in`/`!in`, quantifier ranges (each bound shape, leftover
   conjuncts, two binders, no lower bound = refusal, nat binder), nat param
   guard order, nat return ensures order, nat local invariant placement,
   totalisation wrapper with several params and a requires, decreases
   tuple reduction (Potencia, Expt, gcd fails), `!=` ite measure,
   non-recursive zero, method-level dropped, self-call keeps it,
   sanitiser (uppercase, prime, spark `F`, keyword, collision after
   lowercasing `N` next to `n`).
6. `test_refusals.py`: one snippet per refusal reason in section 9,
   asserting the reason name and the quoted line.
7. `test_check.py`: every fixture task from 5 passes check_wf and has at
   least one interp domain point.
8. `test_hand_lifts.py`: the six tasks of section 1.9 regenerated by the
   lifter from the corpus files and compared to the hand-written JSON
   (modulo fresh-name choice), then run through twin_for; expected operators
   and witnesses as measured.
9. `test_corpus.py` (slow, opt-in): all 785; asserts 783 resolve, the two
   resolution errors are refused by name; every lifted task passes check_wf
   and interp; the census disagreement table is written; the count of lifts
   among the 77 is printed and compared to 74 (a difference is a finding,
   not a failure).
10. Windows: tests 1 to 8 run under `py -3.12` with `T_DAFNY` set, per
    RUN-ON-WINDOWS.md; the `--rprint:PATH` form is what Dafny accepts on
    both platforms (measured here on Linux only; the Windows run is the
    test).

## 13. Where it breaks

- Tuple measures. Dafny's inference defaults to the parameter tuple, and
  its `&&` inference to a tuple; t has one int measure. The reduction rule
  handles the common "one parameter is carried along" shape and nothing
  else; gcd-like functions and SlowMax-like loops are refused unless the
  Dafny-checked candidate is switched on, and even then only two candidate
  shapes are tried.
- Anything with no decreases line: `for` loops (desugared with an explicit
  measure, untested on this corpus), and loops whose guard is a disjunction,
  a negation or a bool, where a verifying source must carry a stated
  measure; `decreases *` is refused.
- Definedness weakening under totalisation and nat erasure (section 6): a
  twin can reach a function outside its source domain and get D instead of
  a well-formedness failure. This cannot be closed in v1 t (no partial
  spec_funs); it is recorded per task and section 11 instrument 4 is where
  a resulting spec weakening would show.
- Dropped hints. Asserts (57 in 8 of the 77), lemma calls and function
  ensures are gone; a kernel that needed them reads UNPROVED. Not wrong,
  but coverage measured this way is "provable without hints", a stricter
  bar than the source met.
- The parser is written against one printer. Dafny 4.11.0's print of a
  construct the corpus does not contain has not been seen (multi-dimensional
  arrays, `by method`, `expect`, labels, `modify`, iterators); those are all
  refusals, but a printer shape that is NOT in the refusal grammar either
  would surface as `parse-refusal` with the token named, never as a silent
  skip. A different Dafny version invalidates the round-trip tests until
  re-run.
- Names: the sanitiser knows the reserved lists the lowerings check. A name
  legal for t and refused by a kernel's own syntax that no lowering guards
  against (a Rust or Lean keyword such as `match`, `loop`, `mod`, `from`,
  `show`) surfaces as that column's LOWER-ERROR, a per-cell fact, not a
  wrong verdict.
- Multi-target parallel assignments and `var` inside loop bodies introduce
  locals declared inside a `while` body; SPEC allows them (frame rule
  excludes them) and lower_dafny verified them (climbing-stairs, Cube), but
  the other six lowerings' handling of a body-local inside a loop is only
  as tested as the fuzz corpus made it.
- Per-method splitting of multi-method files makes "program" ambiguous;
  section 15 makes the program row the conjunction of its tasks, and the
  table shows both counts.
- Seq membership, `!= []`, read-only arrays and strings observed only
  through `|s|` are exact desugarings the inventory identified, each a
  policy call (section 15); by default only `in` is taken.

## 14. Corpus evidence (quoted)

- `Metodos_Formais_tmp_tmpql2hwcsh_Invariantes_fatorial2.dfy` lines 1 to 4:
  `function Fat(n:nat):nat` / `{` / `if n == 0 then 1 else n*Fat(n-1)`: a
  nat-domain recursive function with no decreases; rprint adds `decreases
  n`; the base case relies on nat's lower bound, which is why totalisation
  (or a base-case rewrite) is required before an int-typed spec_fun is
  total.
- Same file, line 20: `return f;` after the loop, where `f` is the return:
  a tail `return` of the return variable, dropped (rule 36).
- `dafny_examples_tmp_tmp8qotd4ez_leetcode_0070-climbing-stairs.dfy` line 16:
  `a, b := b, a + b;`: a parallel assignment whose second right-hand side
  reads the first target, so sequential assignment in source order would be
  wrong (rule 30 uses temporaries); line 19: `return b;` a tail return of a
  local (rule 37).
- `Dafny_Verify_tmp_tmphq7j0row_dataset_error_data_real_error_IsEven_success_1.dfy`
  lines 1 to 2: `function even(n: int): bool` / `requires n >= 0`: a spec
  function with a requires (rule 3); line 9: `ensures r <==> even(n);` (rule
  10, and a deprecated semicolon the print removes).
- `Dafny_Verify_tmp_tmphq7j0row_AI_agent_verify_examples_Cube.dfy`: rprint
  shows `while i != n ... decreases if i <= n then n - i else i - n` and
  `c, k, m := c + k, k + m, m + 6;`: the `!=` ite measure and a three-target
  parallel assignment; both lifted and verified (section 1.9).
- `Dafny_tmp_tmpmvs2dmry_SlowMax.dfy` line 17: `decreases x,y;` on a loop
  whose body assigns both (`x := x - 1;`, `y := y - 1;`): the one tuple
  measure among the 77 loops; refused by default, lifted with `decreases x`
  under the candidate rule (Dafny verified, section 1.10).
- `Programmverifikation-und-synthese_..._ex06-solution.dfy` lines 1 to 7:
  `ghost function gcd(x:int,y:int):int requires x > 0 && y > 0 { if x==y
  then x else if x > y then gcd(x-y,y) else gcd(x,y-x) }`: rprint infers
  `decreases x, y`; no component is fixed in both calls; `decreases-tuple`.
  Lines 25 to 32 declare `gcd'` with `decreases x+y,y`, unused by `gcdI`.
- `dafny-synthesis_task_id_801.dfy` lines 2 to 5: `ensures count >= 0 &&
  count <= 3` and `ensures (count == 3) <==> (a == b && b == c)`: top-level
  `&&` split (rule 6) and `<==>` (rule 10); rprint prints the second as
  `count == 3 <==> a == b && b == c`, the parentheses gone by precedence;
  lines 8 to 16: three `if` statements without `else` (rule 33).
- `Dafny_Verify_tmp_tmphq7j0row_dataset_bql_exampls_Square.dfy` lines 5 to 6:
  `var x: int;` / `var i: int;`: uninitialised locals, assigned before use
  (rule 28).
- `dafny-language-server_tmp_tmpkir0kenl_Test_dafny2_TuringFactorial.dfy`
  lines 15 to 24: a nested `while (s < r + 1)` inside `while (r < n)`;
  rprint gives `decreases n - r` and `decreases r + 1 - s`; `var v, s := u,
  1;` inside the outer body (rules 24, 29).
- `cs245-verification_tmp_tmp0h_nxhqp_power.dfy` lines 5 to 7: `function
  power(a: int, n: int): int` / `requires 0 <= a && 0 <= n;` / `decreases
  n;{if (n == 0) then 1 else a * power(a, n - 1)}`: old-style semicolons
  and a stated single measure alongside a two-conjunct requires (rules 3 and
  6); the body carries 8 asserts inside `/* ... */` proof-outline comments,
  all dropped by the print and rule 39.
- `dafny-programs_tmp_tmpcwodh6qh_src_factorial.dfy` lines 1 to 2: `function
  fact(n: nat): nat` / `ensures fact(n) >= 1`: a function ensures (rule 4).
- `dafny-programs_tmp_tmpcwodh6qh_src_expt.dfy` line 1: `function Expt(b:
  int, n: nat): int requires n >= 0`; rprint infers `decreases b, n`; the
  only self-call is `Expt(b, n - 1)`, so `b` is fixed and the measure
  reduces to `n` (Dafny verified, section 1.10); lines 24 to 25: `lemma
  {:induction a} distributive(x: int, a: nat, b: nat) ensures ...` with no
  body, dropped as a lemma.
- `MIEIC_mfes_tmp_tmpq3ho7nve_exams_appeal_20_p4.dfy` line 1: `function
  F(n: nat): nat { if n <= 2 then n else F(n-1) + F(n-3)}` and line 12:
  `a, b, c := b, c, a + c;`: the name `F` collides case-insensitively with
  lower_spark's reserved `F` after lowercasing, so the sanitiser yields
  `f_1`; a three-target parallel assignment where the third RHS reads the
  first target.
- `dafny-workout_tmp_tmp0abkw6f8_starter_ex01.dfy` lines 12 to 26: `method
  Main()` with `print` and asserts: dropped whole (rule 46); the census's
  `strip_main` did the same lexically.
- `dafny-synthesis_task_id_234.dfy` line 6: `volume := size * size * size;`:
  no if, no literal, one parameter: harness.twin_for returns `no-operator`;
  lifts, cannot count.
- Out of fragment: `Clover_rotate.dfy` line 1 `returns (b: array<int> )` and
  line 12 `b[i]:=a[(i+offset)%a.Length];`: array, array-mutation, div-mod
  (all three named by the census; the lifter refuses at the first, `array`).
  `dafny-synthesis_task_id_414.dfy` lines 5 and 11: `for i := 0 to |seq1|`
  and `break;`: for-loop desugaring is blocked by `early-exit`.
  `dafny-language-server_..._Test_tutorial_maximum.dfy` line 9: `requires
  values != []` and line 10 `ensures max in values`: the two policy
  desugarings (rules 18 exception and 19). `Clover_swap_sim.dfy` line 1:
  `returns(x: int, y: int)`: multi-return. `dafny-synthesis_task_id_803.dfy`
  line 4: `forall a: int :: 0 < a*a < n ==> a*a != n`: the bound is on
  `a*a`, not `a`: unbounded-quantifier, matching the census.

## 15. Open decisions (Treston's, not the lifter's)

1. Read-only `array<int>` parameter -> `seq`. Default: refuse `array`. If
   reversed (an array parameter never assigned, never in a `modifies`, read
   only via `a[i]` and `a.Length`, lifts to a seq with `at` and `len`): the
   inventory's readers found the 36 array sole-blockers largely of this
   shape; the theorem changes type (heap reference to value) but not values;
   the twin discipline is unaffected; the census's `array` row would move to
   a `policy` verdict.
2. `x in s` on a seq -> bounded `exists`. Default: desugar (it is Dafny's own
   definition). If reversed: refuse `seq-membership`; 1 of the 49 refusal
   samples (`maximum.dfy`) and the `seq-membership` burden rows change.
3. `s != []` / `s == []` -> `len(s) != 0` / `len(s) == 0`. Default: refuse
   `seq-literal` (a display is a display). If reversed: exact desugaring of
   an emptiness test; `maximum.dfy` then lifts.
4. nat return -> add `ensures r >= 0`. Default: add (section 6). If
   reversed: the kernels prove a strictly weaker theorem than the source's
   typing states, and the added invariants of section 6 become unnecessary.
5. nat local -> append `x >= 0` invariants. Default: append to the loops
   that assign it. If reversed (refuse `nat-local`): 7 of the 77 are
   refused; or (no invariant): some reals read UNPROVED in kernels that do
   not re-derive it.
6. Function requires -> totalise with default D. Default: totalise, record.
   If reversed (refuse `function-requires`): 12 of the 77 (inventory:
   "spec function with requires / partial domain") are refused, including
   every nat-domain recursive function unless nat params are exempted, since
   a nat parameter IS a requires.
7. Candidate measure checked by Dafny (section 7 rule 6). Default: off. If
   on: SlowMax and the two gcd files lift; the measure is the lifter's.
8. Multi-method files -> one task per gradable method, program row = all
   tasks count. Default: split. If reversed (refuse `multi-method`): 212
   census programs stay out on packaging alone; the inventory counts 5
   gradable programs blocked by nothing else.
9. Top-level `&&` in clauses -> split into separate clauses. Default: split
   (matches the committed tasks and gives INVARIANT-DROP its sites). If
   reversed: one clause per source clause; the twin chosen changes on p6
   and mockExam2_p3 (single `&&` invariants), the theorem does not.
10. Uninitialised local -> default init 0/false. Default: yes. If reversed:
    refuse `uninitialised-local`, 2 of the 77.
11. `string` observed only through `|s|`, `seq<nat>` observed only through
    `len`: erase to `seq`. Default: refuse (`string-char`, `nat-seq-
    elements`). If reversed: exact on those programs (the inventory names
    `_242.dfy` and `_792.dfy`), but the rule needs a use-site analysis.
12. Top-level early `return` before any loop rewritten to if/else. Default:
    refuse `early-exit` (a body restructuring). If reversed: the inventory
    names `starter_ex09.dfy`; the rewrite is exact when nothing follows the
    if in the same block.
13. Program-level accounting when the lifter refuses a task t's instruments
    refuse (no-operator, preservation twin UNPROVED): report as "lifted, not
    counted" rows. Default: yes, in their own column, so coverage of the
    fragment (lifts) and coverage of the measurement (counts) are two
    numbers.

## 16. Experiments run (commands and results)

All under `PATH=/home/tmcuzzort/.local/dafny:$PATH`, cwd
`scratchpad/lifter/design/dpn-exp/`, each dafny call under `timeout 120`.

1. `dafny --version` -> `4.11.0+fcb2042d6d043a2634f0854338c08feeaaaf4ae2`.
2. `dafny resolve abs.dfy --print:abs.print.dfy` (0.45 s, exit 0); same for
   stairs (0.50 s) and fat (0.48 s): comments gone, canonical layout,
   clauses invariant-then-decreases, no inferred decreases (section 1.1).
3. `dafny resolve X.dfy --rprint:X.rprint.dfy` for the same three (0.45 s,
   0.47 s, 0.48 s; 130, 147, 146 lines): preamble is one block comment;
   `decreases n` on Stairs and Fat, `decreases n - i` on the stairs loop,
   `decreases x`/`n` on the methods, `var i: int := 1` (section 1.2).
4. `dafny resolve mix.dfy --print:mix.print.dfy`: exit 2 on deprecated
   semicolons with the file written; `--allow-warnings` gives exit 0 and
   `diff` identical; rprint adds `decreases n` to `Half`, `decreases n, s`
   to the method, `decreases n - i` to the loop, types to locals, `{:trigger}`
   to quantifiers (section 1.3).
5. `noparse.dfy`, `noresolve.dfy`, `undeclared.dfy` with `--print` and
   `--rprint`: parse error writes no file; resolution errors write the file;
   all exit 2 (section 1.4).
6. `dafny verify lemma_only.dfy` -> `2 verified, 0 errors`, exit 0 (a
   lemma with an empty body over a recursive function verifies; dropping it
   costs at most a hint).
7. `dafny verify guessdec.dfy` (loop with `decreases n - i`) and `nodec.dfy`
   (same loop, no decreases) -> both `2 verified`, exit 0.
8. `dafny verify` on abs/stairs/fat sources and on their `--print` outputs
   -> all exit 0.
9. `dafny resolve guards.dfy --rprint` and `dafny verify guards.dfy`: the
   inferred measures per guard shape of section 1.5; `3 verified`.
10. `dafny resolve guards2.dfy --rprint` and `dafny verify guards2.dfy`: no
    measure for `!done`, `||`, bool guards; `cannot prove termination`, exit 4.
11. `dafny resolve forms.dfy --print/--rprint`: `function method` is a parse
    error under Dafny 4 syntax; after the fix, the spellings of section 1.6;
    `var w := *` is a resolution error (`type ... underspecified`).
12. 77 in-fragment programs, sequential `dafny resolve --allow-warnings
    --rprint`: 77 exit 0, 38.0 s (0.49 s each). Survey script over the 77
    user modules: 41 loops, 41 with decreases, guard shapes and tuple counts
    of section 1.5; 31 functions with their measures and self-call
    arguments; identifier hazards 68 of 77 (section 8).
13. `python3 corpus785.py` (4 workers): 783 exit 0, 2 resolution errors
    (named in section 1.7), median 0.57 s, sum 452.5 s, wall 113.5 s, 256
    with warnings. (A sibling design's earlier 8-worker pass in
    `scratchpad/lifter/dpn/corpus_pass.json` shows the same 783/2.)
14. `python3 verify77.py` (4 workers): `dafny verify --allow-warnings` on
    source, `--print` and `--rprint` outputs of all 77: 77/77/77 exit 0, no
    disagreements, 73.0 s wall.
15. Hand lifts `lift/*.json` (fatorial, is_even, climb_stairs,
    square_root_noinv, square_root_inv, cube) through check_wf, interp,
    twin_for, lower_dafny and verifiers.dafny.verify: all check_wf OK, 41 or
    42 domain points each; verdicts in section 1.9 (5 count, fatorial's
    preservation twin unproved).
16. `dafny verify reduce.dfy` (Expt with `decreases n`, and ExptT int-total
    with `decreases n`): `2 verified`. `dafny verify slowmax_decx.dfy`
    (`decreases x`): `1 verified`. `dafny verify gcd_sum.dfy` (`decreases
    x + y` on gcd): `4 verified`.
17. Corpus checks: `grep -l "function method"` finds 2 files, both inside
    comments; 0 files with CRLF; census.json: 785 records, 102 gradable
    one-gap programs (array 36, div-mod 25, multi-return 14, multi-method 5,
    real 5, early-exit 4, string-char 3, set 2, nested-seq 2, generics,
    nondet, seq-literal, bitvector, unbounded-quantifier, module 1 each).
