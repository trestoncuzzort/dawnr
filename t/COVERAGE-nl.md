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
- in t's fragment today: **1777** of 4239 function-shaped (41.9%)
- stdin-shaped, in fragment once a signature is extracted (all-int sample io, solution tags no gap): **8140** of 20509 (39.7%)
- function-shaped problems blocked by exactly one gap: 1574
- function-shaped, out of the fragment with no gap named: 6 (no gate opens them: an assertion form or io shape the reader refuses, or no reference solution; counted apart from the greedy order since 2026-10-06)

## Gaps, by problems that need them

| gap | problems | sole blocker for (function-shaped) | meaning |
|---|---|---|---|
| import | 3932 | 289 | an import other than math, sys or typing: an unmodeled library the solution's meaning depends on |
| map | 2464 | 136 | dict literal, dict(), defaultdict, Counter, or a dict-typed io value |
| closure | 2243 | 105 | a lambda, a nested def, or map/filter with a lambda |
| generator | 1686 | 321 | a generator expression or a generator function (yield): t has no lazy or deferred evaluation |
| class | 1641 | 370 | a class definition (t has no classes, no heap) |
| string-lib | 1288 | 141 | a Python string-library use that SPEC.md's 'The string library (v1)' does NOT cover (split into this gap and the burden `string-lib-v1` on 2026-09-11, the day that section landed; read the dated docstring note above): an f-string or `.format()`, a based `int(x, base)` conversion, `strip`/`lstrip`/`rstrip` given a `chars` argument, `split` on a literal longer than one code point or on a non-literal separator, `sorted()` on a string, or a call to capitalize/title/zfill/center/ljust/rjust/partition/splitlines/encode/swapcase -- none of which SPEC.md's v1 names |
| exception | 502 | 21 | try/except/raise |
| global | 316 | 0 | global or nonlocal: mutable state outside the function, which t's pure functions have no notion of |
| sqrt | 192 | 23 | math.sqrt: a real root is specified in t (`r * r == x`), not computed; `math.isqrt` is in t since 2026-10-06 (SPEC.md The library) and is tagged builtin-math, not here |
| any-type | 142 | 106 | the interface's type could not be pinned to one of the other named types: a bare Any annotation, a call expression as a test argument, or an untyped io value |
| seq-slice-step-other | 108 | 13 | a slice whose step is not a positive literal: a variable step (written as the comprehension by hand, not posed by the notation) or a negative step with a bound |
| none-type | 105 | 41 | Optional[..] or an explicit None return/argument |
| loop-else | 61 | 1 | a loop's else clause (for/while ... else, run when no break fired): t has no such clause; written by hand with a flag |
| io | 30 | 7 | input()/print()/sys.stdin used INSIDE a function-shaped solution (for a stdin-shaped problem, I/O is the shape itself, not a separate gap) |

## Greedy gate order, whole corpus (function-shaped population)

| step | gate | newly unlocked | cumulative in fragment | of function-shaped |
|---|---|---|---|---|
| 1 | class | 370 | 2147 | 50.6% |
| 2 | generator | 341 | 2488 | 58.7% |
| 3 | import | 378 | 2866 | 67.6% |
| 4 | map | 365 | 3231 | 76.2% |
| 5 | closure | 295 | 3526 | 83.2% |
| 6 | string-lib | 304 | 3830 | 90.4% |
| 7 | any-type | 136 | 3966 | 93.6% |
| 8 | none-type | 87 | 4053 | 95.6% |
| 9 | exception | 80 | 4133 | 97.5% |
| 10 | sqrt | 34 | 4167 | 98.3% |
| 11 | seq-slice-step-other | 34 | 4201 | 99.1% |
| 12 | io | 30 | 4231 | 99.8% |
| 13 | loop-else | 1 | 4232 | 99.8% |
| 14 | global | 1 | 4233 | 99.9% |

A step with 0 newly unlocked is a gate that unlocks nothing alone but
is the most frequent remaining gap; the programs it belongs to need
more than one gate.

### MBPP greedy gate order (974 function-shaped, 657 in fragment today)

| step | gate | newly unlocked | cumulative | of function-shaped |
|---|---|---|---|---|
| 1 | import | 104 | 761 | 78.1% |
| 2 | generator | 53 | 814 | 83.6% |
| 3 | map | 54 | 868 | 89.1% |
| 4 | closure | 51 | 919 | 94.4% |
| 5 | sqrt | 16 | 935 | 96.0% |
| 6 | none-type | 12 | 947 | 97.2% |
| 7 | string-lib | 10 | 957 | 98.3% |
| 8 | seq-slice-step-other | 5 | 962 | 98.8% |
| 9 | any-type | 4 | 966 | 99.2% |
| 10 | class | 4 | 970 | 99.6% |
| 11 | exception | 2 | 972 | 99.8% |

### HumanEval greedy gate order (164 function-shaped, 20 in fragment today)

| step | gate | newly unlocked | cumulative | of function-shaped |
|---|---|---|---|---|
| 1 | any-type | 103 | 123 | 75.0% |
| 2 | closure | 13 | 136 | 82.9% |
| 3 | generator | 10 | 146 | 89.0% |
| 4 | map | 4 | 150 | 91.5% |
| 5 | string-lib | 3 | 153 | 93.3% |
| 6 | none-type | 3 | 156 | 95.1% |
| 7 | import | 3 | 159 | 97.0% |
| 8 | sqrt | 2 | 161 | 98.2% |
| 9 | exception | 2 | 163 | 99.4% |
| 10 | seq-slice-step-other | 1 | 164 | 100.0% |

### APPS greedy gate order (3101 function-shaped, 1100 in fragment today)

| step | gate | newly unlocked | cumulative | of function-shaped |
|---|---|---|---|---|
| 1 | class | 370 | 1470 | 47.4% |
| 2 | generator | 288 | 1758 | 56.7% |
| 3 | import | 272 | 2030 | 65.5% |
| 4 | map | 309 | 2339 | 75.4% |
| 5 | string-lib | 259 | 2598 | 83.8% |
| 6 | closure | 275 | 2873 | 92.6% |
| 7 | none-type | 72 | 2945 | 95.0% |
| 8 | exception | 76 | 3021 | 97.4% |
| 9 | io | 29 | 3050 | 98.4% |
| 10 | seq-slice-step-other | 28 | 3078 | 99.3% |
| 11 | sqrt | 17 | 3095 | 99.8% |
| 12 | loop-else | 1 | 3096 | 99.8% |
| 13 | global | 1 | 3097 | 99.9% |

### CodeContests: no function-shaped problems

## By source

| source | problems | function-shaped | stdin-shaped | in fragment | stdin in fragment once signature extracted |
|---|---|---|---|---|---|
| MBPP | 974 | 974 | 0 | 657 | 0 |
| HumanEval | 164 | 164 | 0 | 20 | 0 |
| APPS | 10000 | 3101 | 6899 | 1100 | 3515 |
| CodeContests | 13610 | 0 | 13610 | 0 | 4625 |

## Burdens (expressible in t at a translation cost)

| burden | problems | meaning |
|---|---|---|
| stdin-to-signature | 20509 | a stdin-shaped problem carries no function signature; one has to be extracted from its input format before t can pose the problem at all |
| string-as-seq | 13229 | a string used only the way t's `seq` of code points already covers: a str literal, a str-typed io value, indexing/len/slicing/concatenation/comparison of strings, `ord`/`chr`, iterating over a string, or `in` on a string (a bounded exists) -- SPEC.md's 'Strings as sequences of code points' |
| string-lib-v1 | 11978 | a Python string-library use that IS one of SPEC.md's 'The string library (v1)' sixteen members, called in a v1 form: `split()` or `split(c)` on a one-code-point literal, `join`, `str()`, `count`/`find`/`replace`/`startswith`/`endswith` with any argument, `strip`/`lstrip`/`rstrip` with no argument, `lower`/`upper`, or one of the four predicates isdigit/isalpha/isupper/islower; tags only when EVERY string-library use in the solution reads this way -- one use outside v1 anywhere in the same solution tags the gap `string-lib` instead, not both. Split from `string-lib` 2026-09-11 the day SPEC.md's section landed |
| seq-literal | 8599 | a sequence literal [..] in an expression: t's v1 already has seq (SPEC.md 'Sequences: literals, concatenation, slices'), landed 2026-09-09, so this is expressible directly, not a gap |
| tuple-pair | 7738 | a tuple of exactly two values, each an int, bool or seq of ints, built, returned, passed, compared, or unpacked from such a pair: t's v1 already has {"pair": [T1, T2]} (SPEC.md 'Pairs (v1)'), landed 2026-09-10 |
| builtin-math | 6686 | IN THE FRAGMENT since 2026-10-06 (SPEC.md The library): min, max, sum, abs, math.gcd, math.isqrt, ** -- library functions of t; before that day t could express each but has no builtin for any of them |
| seq-append | 6030 | sequence concatenation `+` or .append()/.extend()/.insert(): t's v1 already has + on seqs (SPEC.md 'Sequences: literals, concatenation, slices'), landed as r + [x] or r + s |
| comprehension | 5920 | IN THE FRAGMENT since 2026-10-06 (SPEC.md Comprehensions): a list comprehension over a seq or a range is t's [body for x in s if cond]; before that day t writes this as an explicit loop or a quantifier |
| unbounded-loop | 4403 | IN THE FRAGMENT since 2026-10-06 (SPEC.md Early exits): while True, break and continue are t's own statements now (a while true needs a break of its own or a return, which every terminating Python loop has) |
| tuple | 3749 | IN THE FRAGMENT since 2026-10-06 (SPEC.md Compositional types): a tuple of three or more elements, a nested tuple, a tuple with a string component (until strings-as-seq's seq-of-code-points model covers a pair component too), or a list of tuples (the separate gap `nested-seq-pair`, tagged where a list literal's own elements are inspected): SPEC.md's 'Pairs (v1)' covers only the two-element case, the burden tuple-pair |
| nested-seq | 3625 | IN THE FRAGMENT since 2026-10-06 (SPEC.md Compositional types): a seq of seq whose row type could not be read as string or tuple (an int/bool row, or a subscript of a subscript, or a grid a static read genuinely cannot classify): SPEC.md's 'Nested sequences (v1)' burden `seq<seq<int>>` and the unreadable fallback both land here |
| real | 3445 | IN THE FRAGMENT since 2026-10-06 (SPEC.md Exact rationals): a float literal, true division `/`, float(), or a decimal-valued io token -- t's `real` is the exact rational, so a problem whose answer depends on float rounding is still not posed (undercounted here) |
| sort | 2908 | IN THE FRAGMENT since 2026-10-06 (SPEC.md Sorting): sorted() or .sort() is t's sort(s); before that day it was expressible in t but needed a spec, not a builtin |
| seq-slice | 2474 | slicing s[a:b], s[a:], s[:b] with non-negative bounds and no step: t's v1 already has slice (SPEC.md 'Sequences: literals, concatenation, slices'); a negative bound or a step is measured separately as seq-slice-negative / seq-slice-step (burdens since 2026-10-06) and the gap seq-slice-step-other |
| py2-unparseable | 2107 | the chosen Python solution does not parse under Python 3's ast (typically a Python 2 solution: print statement, raw_input, etc.); only its io-types are measured, its AST is not |
| set | 1604 | IN THE FRAGMENT since 2026-10-06 (SPEC.md Compositional types): set literal, set(), frozenset(), a set/dict comprehension's set form |
| recursion | 1493 | the solution's function calls itself; t supports this through spec functions (self-calls and calls to earlier functions), so it is a burden, not a gap |
| seq-slice-reverse | 662 | IN THE FRAGMENT since 2026-10-06 (SPEC.md The library): s[::-1] with no bounds, the reversal, the library's rev(s) |
| nested-seq-pair | 566 | IN THE FRAGMENT since 2026-10-06 (SPEC.md Compositional types): a seq of seq whose row reads as a tuple (a list of tuples, or a nested annotation through Tuple/tuple): SPEC.md v1 has no seq of pairs |
| seq-slice-negative | 489 | IN THE FRAGMENT since 2026-10-06 (SPEC.md The library): a slice bound that is a negative literal, s[-1:] or s[:-1], read as len(s) - k by the notation (a non-literal negative bound is still not posed, undercounted here) |
| nested-seq-string | 119 | IN THE FRAGMENT since 2026-10-06 (SPEC.md Compositional types): a seq of seq (or equivalent) whose row reads as a string: SPEC.md v1 has no seq<string> type |
| seq-slice-step | 99 | IN THE FRAGMENT since 2026-10-06 (SPEC.md Stepped slices): a slice whose step is a positive literal, s[a:b:k], the notation's s[a..b..k] (sugar for a range comprehension) |
| nested-seq-deep | 95 | IN THE FRAGMENT since 2026-10-06 (SPEC.md Compositional types): three or more levels of seq nesting: SPEC.md v1's nested seq is exactly one level deep |
| multi-return | 70 | IN THE FRAGMENT since 2026-10-06 (SPEC.md Compositional types): a function-shaped problem returning a tuple (several return values; t returns exactly one) |

## Method

Run time: 29.1s. Every source's first Python solution only; APPS and CodeContests carry many, all but the first are
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
token that parses as `float` but not `int` needs `real` (a burden
since 2026-10-06: exact rationals are in the fragment), anything
else needs the burden `string-as-seq`. A lexical scan cannot show a
map, a set, a tuple or a nested sequence, so those four gaps are
never attempted for a stdin-shaped problem's io-types; only its
SOLUTION's AST can still tag them.

A stdin-shaped problem is never `in_fragment`: SYNTAX.md and the
brief for this file agree a signature has to exist before a
problem can be posed to t at all, which is the `stdin-to-signature`
burden every stdin-shaped problem carries. `would_be_in_fragment_with_signature` in the JSON (and the by-source table above) marks
the ones whose solution tags no gap -- everything BUT the missing signature
already fits; a string token in the sample is no longer
disqualifying on its own, since `string-as-seq` is a burden, not a
gap, and since 2026-10-06 neither is a decimal-valued token (`real`).
A problem with no Python solution, or whose chosen solution is
`py2-unparseable`, is never marked this way: the solution side is
unmeasured, not measured clean.

Solution-construct detection walks the parsed `ast` once per
solution; each DETECTORS entry below is either a node-type check
(a `try`/`raise` is `exception`, a `ClassDef` is `class`) or a
narrower check on a `Call`, `Attribute`, `Subscript` or `Tuple`
node. It is approximate in both directions, and the approximations
are named rather than hidden:

- `seq-append` (a burden since SPEC.md's 'Sequences: literals,
  concatenation, slices' landed) only fires on
  `.append`/`.extend`/`.insert` or a `+` where at least one operand
  is a literal list; a `+` between two names typed as lists earlier
  in the function is not traced and is undercounted here, the same
  undercounting coverage_census.py notes for `+` on Dafny
  sequences;
- `seq-slice` (a burden, same landing) fires on `s[a:b]`, `s[a:]`,
  `s[:b]` read off the AST `Slice` node's own shape, not a
  computed value: a positive literal step tags `seq-slice-step`, a bare
  `s[::-1]` tags `seq-slice-reverse`, any other step tags
  `seq-slice-step-other` (since 2026-10-06), and a bound written as a
  negative literal (`s[:-1]`,
  `ast`'s own `UnaryOp(USub, ..)` shape for a negative number) tags
  `seq-slice-negative` instead; a negative bound reached through a
  variable or an expression (`s[:n-1]`) is not recognized this way
  and reads as the plain (non-negative) burden, an undercount of
  the two gaps in the same direction every other syntactic detector
  here accepts;
- `unbounded-loop` (a burden since 2026-10-06, SPEC.md Early exits)
  fires on EVERY `break` and `continue`, not only
  the ones outside coverage_census.py's tail-position exception
  (LIFTER-DECISIONS.md row 23: a break whose loop is the tail of the
  function, with a straight-line continuation, lifts to a return);
  replicating that exception needs the same control-flow reach
  coverage_census.py's `_break_as_return` scanner has, which this
  file does not build, so `unbounded-loop` OVER-counts relative to
  that finer rule;
- `tuple` and `tuple-pair` (SPEC.md's 'Pairs (v1)' split, landed
  2026-09-10) fire on EVERY `ast.Tuple` node found anywhere in the
  solution, built, returned, passed, compared, or the target or
  value of an unpacking assignment: exactly two elements, neither a
  nested tuple nor syntactically a string, is `tuple-pair`; three
  or more elements, a nested tuple, or a string element is `tuple`
  (a list of tuples is the separate gap `nested-seq-pair`, tagged
  where a list literal's own elements are inspected); a parallel
  assignment whose right-hand side is a tuple literal of the same
  length as its target (`a, b = b, a`, `a, b = 1, 2`) is excluded
  from both, the same exception the detector has always made,
  since t writes it as two plain assignments, no pair value ever
  built; neither check resolves a bare variable's element type, so
  a tuple carrying a string held in a variable, not a literal, is
  undercounted into `tuple-pair` here. MBPP's channel is different:
  `mbpp_dfy.parse_assertion`'s own refusal for a tuple argument or
  expected value names no arity (`_Unsupported("tuple")` whatever
  the tuple's shape), so this file re-parses that SAME assert line
  a second time with its own `ast` (`_mbpp_assert_tuple_kind`,
  mbpp_dfy.py untouched) to recover the literal tuple and apply the
  same pair/arity rule; an assert whose shape that second parse
  cannot read (not a plain `f(...) == expected`, or no literal
  tuple on the named side) falls back to the gap `tuple`, not the
  burden, the same conservative default the io-types side takes
  elsewhere in this file. HumanEval's typed `Tuple[T1, T2]`
  annotation takes the exact recursive read instead: two
  components, each itself annotated with no gap or burden of its
  own, is `tuple-pair`; anything else is `tuple`; a `Tuple[..]`
  RETURN annotation is `multi-return` regardless, unchanged from
  before the split, since a tuple-typed return means several
  return values, not a tuple-shaped value in the data;
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
  (`STRING_METHODS` in nl_census.py) are string-LIBRARY uses, not
  the seq-of-code-points model SPEC.md's 'Strings as sequences of
  code points' covers (that burden is `string-as-seq`, tagged only
  for a bare str/f-string-free/char literal); since 2026-09-11
  (SPEC.md's 'The string library (v1)') a string-library use tags
  the burden `string-lib-v1` when it is one of the sixteen named
  members called in a v1 form (`split()`/`split(c)` on one code
  point, `join`, `str()`, `count`/`find`/`replace`/`startswith`/
  `endswith` with any argument, no-argument `strip`/`lstrip`/
  `rstrip`, `lower`/`upper`, the four is-predicates) and ONLY when
  EVERY string-library use in the same solution reads that way; one
  use outside v1 anywhere in the solution (an f-string, `.format()`,
  `int(x, base)`, `strip(chars)`, `split` on a longer or
  non-literal separator, `sorted()` on a string, or a member SPEC.md
  does not name) tags the narrower gap `string-lib` for the whole
  solution instead, never both;
- `count` is in `STRING_METHODS` even though `list.count(..)` uses
  the same attribute name; a solution counting occurrences in a
  list, not a string, is over-counted into `string-lib`/
  `string-lib-v1` here, the same name-only approximation `.sort`
  already accepts elsewhere;
- `ord`/`chr` calls tag `string-as-seq` (a burden: t already has
  the code point, this is only the name Python gives it);
- `str(..)` is tagged the burden `string-lib-v1` unconditionally
  (SPEC.md's `tostr` is defined for an int, but any argument reads
  as v1 here, undercounting nothing), the same treatment `float(..)`
  already gets for `real`; `int(..)` is tagged the gap `string-lib`
  only when called with an explicit base (`int(x, 16)`), unambiguous
  string parsing -- a bare `int(x)` is NOT tagged even when x is a
  string, since the common `int(input())` idiom would otherwise
  swamp `string-lib` on nearly every stdin-shaped solution with
  input-parsing boilerplate a signature-extraction step would
  remove, not the algorithmic core; this undercounts genuine
  string-to-int parsing written without a base argument;
- `sorted(..)` always tags the `sort` burden, and additionally tags
  the gap `string-lib` (sorted() is not one of SPEC.md's sixteen v1
  members, in any form) when its argument is SYNTACTICALLY a string
  (a literal, an f-string, a `str(..)` call, or a chained string-
  method call) -- `sorted(a_variable)` is not resolved to a type
  and is undercounted when the variable holds a string;
- a bare `Attribute` naming a STRING_METHODS member with no `Call`
  wrapped around it (a method passed by reference, `f = s.strip`)
  has no argument list to read a v1 form from and tags the gap
  `string-lib`, the same conservative default every other
  unreadable shape in this file takes;
- iterating over a string, and `in` on a string, are not detected
  as their own AST shape (both look identical to the same
  operation on a list without type inference); a solution doing
  only this and nothing else stringy is invisible to
  `string-as-seq`, an undercount left as-is rather than built out;
- a `SyntaxError` on `ast.parse` (most often Python 2: a `print`
  statement, `raw_input`, an octal literal) is recorded as the
  `py2-unparseable` burden and stops solution-construct detection
  for that problem; its io-types are still measured from the tests
  or samples, which do not require parsing Python.

Every problem's full tag set, including MBPP's raw parse_assertion
refusals and the split each record came from, is in the JSON beside
this report when `--json` is given, so any row can be checked
against the source it came from.
