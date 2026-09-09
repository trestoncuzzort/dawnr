# t coverage census: nl (24748 problems)

What the nl/ corpus needs that t does not have, problem by problem,
and which gate opens the most problems. Lexical and AST census of
reference solutions, no lifter and no kernel run: a solution's
constructs over-approximate what a t answer would need, since a t
answer can be written differently from the reference. nl/FIDELITY.md's
gate on corpus numbers is untouched by this file. Method and
detectors at the end.

## Headline

- problems: 24748
  - MBPP: 974
  - HumanEval: 164
  - APPS: 10000
  - CodeContests: 13610
- function-shaped: 4239; stdin-shaped: 20509
- in t's fragment today: **449** of 4239 function-shaped (10.6%)
- stdin-shaped, in fragment once a signature is extracted (all-int sample io, solution tags no gap): **361** of 20509 (1.8%)
- function-shaped problems blocked by exactly one gap: 982

## Gaps, by problems that need them

| gap | problems | sole blocker for (function-shaped) | meaning |
|---|---|---|---|
| string-char | 18361 | 347 | string or char type: a str literal, an f-string, a str method (upper/lower/split/join/strip/replace/startswith/endswith/format), or a str-typed io value |
| seq-literal | 8599 | 35 | a sequence literal [..] in an expression (the next wave; t builds sequences with seq(n, v) and functional update today) |
| tuple | 7906 | 53 | tuple unpacking beyond a same-length parallel assignment, a tuple parameter, or a tuple-typed io value |
| seq-append | 6030 | 3 | sequence concatenation `+` or .append()/.extend() (the next wave after v1's functional update and seq(n, v); not yet in the fragment) |
| unbounded-loop | 4403 | 16 | while True, or a break/continue (t has no while-true, no continue, and a break is only in the fragment as a tail-position return, decision 23 -- not distinguished here, see Method) |
| import | 3932 | 38 | an import other than math, sys or typing: an unmodeled library the solution's meaning depends on |
| nested-seq | 3704 | 81 | a seq of seq, or a subscript of a subscript: list of lists in the solution or in a sample io value |
| real | 3517 | 180 | real numbers: a float literal, true division `/`, math.sqrt, float(), or a decimal-valued io token |
| seq-slice | 3305 | 45 | slicing s[a:b] (the next wave) |
| map | 2463 | 16 | dict literal, dict(), defaultdict, Counter, or a dict-typed io value |
| closure | 2243 | 25 | a lambda, a nested def, or map/filter with a lambda |
| generator | 1686 | 51 | a generator expression or a generator function (yield): t has no lazy or deferred evaluation |
| class | 1641 | 55 | a class definition (t has no classes, no heap) |
| set | 1604 | 18 | set literal, set(), frozenset(), a set/dict comprehension's set form |
| exception | 502 | 4 | try/except/raise |
| global | 316 | 0 | global or nonlocal: mutable state outside the function, which t's pure functions have no notion of |
| any-type | 141 | 0 | the interface's type could not be pinned to one of the other named types: a bare Any annotation, a call expression as a test argument, or an untyped io value |
| none-type | 99 | 12 | Optional[..] or an explicit None return/argument |
| multi-return | 43 | 2 | a function-shaped problem returning a tuple (several return values; t returns exactly one) |
| io | 30 | 1 | input()/print()/sys.stdin used INSIDE a function-shaped solution (for a stdin-shaped problem, I/O is the shape itself, not a separate gap) |

## Greedy gate order, whole corpus (function-shaped population)

| step | gate | newly unlocked | cumulative in fragment | of function-shaped |
|---|---|---|---|---|
| 1 | string-char | 370 | 819 | 19.3% |
| 2 | real | 231 | 1050 | 24.8% |
| 3 | import | 195 | 1245 | 29.4% |
| 4 | generator | 205 | 1450 | 34.2% |
| 5 | nested-seq | 202 | 1652 | 39.0% |
| 6 | seq-slice | 247 | 1899 | 44.8% |
| 7 | class | 222 | 2121 | 50.0% |
| 8 | seq-literal | 253 | 2374 | 56.0% |
| 9 | map | 251 | 2625 | 61.9% |
| 10 | seq-append | 280 | 2905 | 68.5% |
| 11 | tuple | 249 | 3154 | 74.4% |
| 12 | closure | 276 | 3430 | 80.9% |
| 13 | set | 249 | 3679 | 86.8% |
| 14 | unbounded-loop | 192 | 3871 | 91.3% |
| 15 | any-type | 132 | 4003 | 94.4% |
| 16 | none-type | 82 | 4085 | 96.4% |
| 17 | exception | 82 | 4167 | 98.3% |
| 18 | multi-return | 41 | 4208 | 99.3% |
| 19 | io | 30 | 4238 | 100.0% |
| 20 | global | 1 | 4239 | 100.0% |

A step with 0 newly unlocked is a gate that unlocks nothing alone but
is the most frequent remaining gap; the programs it belongs to need
more than one gate.

### MBPP greedy gate order (974 function-shaped, 239 in fragment today)

| step | gate | newly unlocked | cumulative | of function-shaped |
|---|---|---|---|---|
| 1 | string-char | 116 | 355 | 36.4% |
| 2 | import | 86 | 441 | 45.3% |
| 3 | real | 89 | 530 | 54.4% |
| 4 | tuple | 64 | 594 | 61.0% |
| 5 | nested-seq | 45 | 639 | 65.6% |
| 6 | generator | 52 | 691 | 70.9% |
| 7 | seq-slice | 37 | 728 | 74.7% |
| 8 | map | 37 | 765 | 78.5% |
| 9 | closure | 46 | 811 | 83.3% |
| 10 | set | 29 | 840 | 86.2% |
| 11 | seq-literal | 29 | 869 | 89.2% |
| 12 | seq-append | 61 | 930 | 95.5% |
| 13 | unbounded-loop | 29 | 959 | 98.5% |
| 14 | none-type | 6 | 965 | 99.1% |
| 15 | any-type | 3 | 968 | 99.4% |
| 16 | class | 4 | 972 | 99.8% |
| 17 | exception | 2 | 974 | 100.0% |

### HumanEval greedy gate order (164 function-shaped, 0 in fragment today)

| step | gate | newly unlocked | cumulative | of function-shaped |
|---|---|---|---|---|
| 1 | string-char | 9 | 9 | 5.5% |
| 2 | any-type | 52 | 61 | 37.2% |
| 3 | real | 10 | 71 | 43.3% |
| 4 | seq-slice | 10 | 81 | 49.4% |
| 5 | seq-literal | 9 | 90 | 54.9% |
| 6 | seq-append | 19 | 109 | 66.5% |
| 7 | closure | 8 | 117 | 71.3% |
| 8 | generator | 10 | 127 | 77.4% |
| 9 | set | 7 | 134 | 81.7% |
| 10 | multi-return | 7 | 141 | 86.0% |
| 11 | map | 5 | 146 | 89.0% |
| 12 | unbounded-loop | 5 | 151 | 92.1% |
| 13 | nested-seq | 4 | 155 | 94.5% |
| 14 | none-type | 3 | 158 | 96.3% |
| 15 | import | 3 | 161 | 98.2% |
| 16 | tuple | 1 | 162 | 98.8% |
| 17 | exception | 2 | 164 | 100.0% |

### APPS greedy gate order (3101 function-shaped, 210 in fragment today)

| step | gate | newly unlocked | cumulative | of function-shaped |
|---|---|---|---|---|
| 1 | string-char | 245 | 455 | 14.7% |
| 2 | real | 143 | 598 | 19.3% |
| 3 | class | 161 | 759 | 24.5% |
| 4 | generator | 159 | 918 | 29.6% |
| 5 | seq-slice | 191 | 1109 | 35.8% |
| 6 | nested-seq | 176 | 1285 | 41.4% |
| 7 | seq-literal | 195 | 1480 | 47.7% |
| 8 | import | 220 | 1700 | 54.8% |
| 9 | map | 218 | 1918 | 61.9% |
| 10 | seq-append | 241 | 2159 | 69.6% |
| 11 | closure | 202 | 2361 | 76.1% |
| 12 | set | 201 | 2562 | 82.6% |
| 13 | tuple | 161 | 2723 | 87.8% |
| 14 | unbounded-loop | 162 | 2885 | 93.0% |
| 15 | none-type | 73 | 2958 | 95.4% |
| 16 | exception | 78 | 3036 | 97.9% |
| 17 | multi-return | 34 | 3070 | 99.0% |
| 18 | io | 30 | 3100 | 100.0% |
| 19 | global | 1 | 3101 | 100.0% |

### CodeContests: no function-shaped problems

## By source

| source | problems | function-shaped | stdin-shaped | in fragment | stdin in fragment once signature extracted |
|---|---|---|---|---|---|
| MBPP | 974 | 974 | 0 | 239 | 0 |
| HumanEval | 164 | 164 | 0 | 0 | 0 |
| APPS | 10000 | 3101 | 6899 | 210 | 181 |
| CodeContests | 13610 | 0 | 13610 | 0 | 180 |

## Burdens (expressible in t at a translation cost)

| burden | problems | meaning |
|---|---|---|
| stdin-to-signature | 20509 | a stdin-shaped problem carries no function signature; one has to be extracted from its input format before t can pose the problem at all |
| builtin-math | 6624 | min, max, sum or abs; t can express each but has no builtin for any of them |
| comprehension | 5920 | a list/set/dict comprehension over ints; t writes this as an explicit loop or a quantifier |
| sort | 2908 | sorted() or .sort(); expressible in t but needs a spec, not a builtin |
| py2-unparseable | 2107 | the chosen Python solution does not parse under Python 3's ast (typically a Python 2 solution: print statement, raw_input, etc.); only its io-types are measured, its AST is not |
| recursion | 1496 | the solution's function calls itself; t supports this through spec functions (self-calls and calls to earlier functions), so it is a burden, not a gap |

## Method

Run time: 43.8s. Every source's first Python solution only; APPS and CodeContests carry many, all but the first are
unread. `mbpp_dfy.parse_assertion` is reused for every MBPP
assertion (spec_experiment.py's `pool()` uses the same function to
decide the same question, whether a problem's tests fit t's
fragment); its refusal reasons are recorded verbatim in the JSON
beside this report and mapped to a gap name only where the reason
names a type (`arg:str`, `expected:float`, ...); a structural
refusal (a comparison other than `==`, an unparseable assertion
shape, a keyword argument) names no type and contributes no gap,
though it is still counted toward `all_ok` and can keep a problem
out of fragment on its own.

HumanEval's io-types come from `ast`-parsing the typed `def` line in
`prompt` (always present, always parses: measured 164 of 164).
APPS problems whose `input_output` carries a `fn_name` are
LeetCode-style function calls (`class Solution: def f(self, ...)`)
with typed JSON arguments and a typed JSON return in the SAME field
that other APPS problems use for raw stdin text; these are counted
as `function`-shaped, like MBPP and HumanEval, and their io-types
are read directly off the decoded JSON values of up to 5 sample
input rows and 5 sample outputs, not lexically. Every other APPS
problem, and every CodeContests problem, is `stdin`-shaped: its
io-types come from a lexical scan of up to 3 sample `input`/`output`
blocks (`public_tests` for CodeContests), token by token on
whitespace -- every token that parses as `int` needs nothing, a
token that parses as `float` but not `int` needs `real`, anything
else needs `string-char`. A lexical scan cannot show a map, a set, a
tuple or a nested sequence, so those four gaps are never attempted
for a stdin-shaped problem's io-types; only its SOLUTION's AST can
still tag them.

A stdin-shaped problem is never `in_fragment`: SYNTAX.md and the
brief for this file agree a signature has to exist before a
problem can be posed to t at all, which is the `stdin-to-signature`
burden every stdin-shaped problem carries. `would_be_in_fragment_with_signature` in the JSON (and the by-source table above) marks
the ones whose sample io is all-integer and whose solution tags no
gap -- everything BUT the missing signature already fits. A problem
with no Python solution, or whose chosen solution is
`py2-unparseable`, is never marked this way even when its sample io
is all-integer: the solution side is unmeasured, not measured clean.

Solution-construct detection walks the parsed `ast` once per
solution; each DETECTORS entry below is either a node-type check
(a `try`/`raise` is `exception`, a `ClassDef` is `class`) or a
narrower check on a `Call`, `Attribute` or `Assign` node. It is
approximate in both directions, and the approximations are named
rather than hidden:

- `seq-append` only fires on `.append`/`.extend`/`.insert` or a `+`
  where at least one operand is a literal list; a `+` between two
  names typed as lists earlier in the function is not traced and is
  undercounted here, the same undercounting coverage_census.py notes
  for `+` on Dafny sequences;
- `unbounded-loop` fires on EVERY `break` and `continue`, not only
  the ones outside coverage_census.py's tail-position exception
  (LIFTER-DECISIONS.md row 23: a break whose loop is the tail of the
  function, with a straight-line continuation, lifts to a return);
  replicating that exception needs the same control-flow reach
  coverage_census.py's `_break_as_return` scanner has, which this
  file does not build, so `unbounded-loop` OVER-counts relative to
  that finer rule;
- `tuple` fires on a tuple-target assignment unless the right-hand
  side is a tuple literal of the same length (`a, b = b, a` reads as
  a parallel assignment, not a gap); a tuple unpacking a call's
  return or an arbitrary iterable IS tagged;
- `recursion` and `multi-return` are read off the entry-point
  function specifically for a function-shaped problem (matching it
  by name), and off any self-recursive top-level `def` for a
  stdin-shaped one, where there is no single entry point;
- `io` is tagged for `print`/`input` only in a function-shaped
  solution; a stdin-shaped solution's I/O calls are the shape, not a
  separate gap, so they are never tagged there;
- Python's own `int` is unbounded, like t's, so no `bigint` detector
  exists and no problem is ever blocked on integer width;
- an f-string, `.format()`, and every string method in a fixed list
  (`STRING_METHODS` in nl_census.py) all tag the single `string-char`
  gap rather than each having a name of their own, since all three
  mean the same thing for t: the value in play is not an int, a
  bool, or a seq of int;
- a `SyntaxError` on `ast.parse` (most often Python 2: a `print`
  statement, `raw_input`, an octal literal) is recorded as the
  `py2-unparseable` burden and stops solution-construct detection
  for that problem; its io-types are still measured from the tests
  or samples, which do not require parsing Python.

Every problem's full tag set, including MBPP's raw parse_assertion
refusals and the split each record came from, is in the JSON beside
this report when `--json` is given, so any row can be checked
against the source it came from.
