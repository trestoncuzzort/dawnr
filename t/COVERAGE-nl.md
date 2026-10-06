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
- in t's fragment today: **1072** of 4239 function-shaped (25.3%)
- stdin-shaped, in fragment once a signature is extracted (all-int sample io, solution tags no gap): **5345** of 20509 (26.1%)
- function-shaped problems blocked by exactly one gap: 1663

## Gaps, by problems that need them

| gap | problems | sole blocker for (function-shaped) | meaning |
|---|---|---|---|
| unbounded-loop | 4403 | 53 | while True, or a break/continue (t has no while-true, no continue, and a break is only in the fragment as a tail-position return, decision 23 -- not distinguished here, see Method) |
| import | 3932 | 253 | an import other than math, sys or typing: an unmodeled library the solution's meaning depends on |
| real | 3517 | 297 | real numbers: a float literal, true division `/`, math.sqrt, float(), or a decimal-valued io token |
| map | 2463 | 110 | dict literal, dict(), defaultdict, Counter, or a dict-typed io value |
| closure | 2243 | 84 | a lambda, a nested def, or map/filter with a lambda |
| generator | 1686 | 257 | a generator expression or a generator function (yield): t has no lazy or deferred evaluation |
| class | 1641 | 262 | a class definition (t has no classes, no heap) |
| string-lib | 1288 | 109 | a Python string-library use that SPEC.md's 'The string library (v1)' does NOT cover (split into this gap and the burden `string-lib-v1` on 2026-09-11, the day that section landed; read the dated docstring note above): an f-string or `.format()`, a based `int(x, base)` conversion, `strip`/`lstrip`/`rstrip` given a `chars` argument, `split` on a literal longer than one code point or on a non-literal separator, `sorted()` on a string, or a call to capitalize/title/zfill/center/ljust/rjust/partition/splitlines/encode/swapcase -- none of which SPEC.md's v1 names |
| seq-slice-step | 852 | 72 | a slice with a step, s[a:b:c]: t's slice form takes two bounds only, no step |
| exception | 502 | 13 | try/except/raise |
| seq-slice-negative | 489 | 38 | a slice bound that is a negative literal, s[-1:] or s[:-1]: t's slice is defined only for 0 <= a <= b <= len(s), so a negative index is measured apart from the burden seq-slice |
| global | 316 | 0 | global or nonlocal: mutable state outside the function, which t's pure functions have no notion of |
| any-type | 141 | 83 | the interface's type could not be pinned to one of the other named types: a bare Any annotation, a call expression as a test argument, or an untyped io value |
| none-type | 99 | 26 | Optional[..] or an explicit None return/argument |
| io | 30 | 6 | input()/print()/sys.stdin used INSIDE a function-shaped solution (for a stdin-shaped problem, I/O is the shape itself, not a separate gap) |

## Greedy gate order, whole corpus (function-shaped population)

| step | gate | newly unlocked | cumulative in fragment | of function-shaped |
|---|---|---|---|---|
| 1 | real | 562 | 1634 | 38.5% |
| 2 | class | 297 | 1931 | 45.6% |
| 3 | generator | 312 | 2243 | 52.9% |
| 4 | import | 349 | 2592 | 61.1% |
| 5 | map | 326 | 2918 | 68.8% |
| 6 | closure | 255 | 3173 | 74.9% |
| 7 | string-lib | 262 | 3435 | 81.0% |
| 8 | seq-slice-step | 183 | 3618 | 85.4% |
| 9 | unbounded-loop | 191 | 3809 | 89.9% |
| 10 | any-type | 135 | 3944 | 93.0% |
| 11 | seq-slice-negative | 100 | 4044 | 95.4% |
| 12 | none-type | 82 | 4126 | 97.3% |
| 13 | exception | 82 | 4208 | 99.3% |
| 14 | io | 30 | 4238 | 100.0% |
| 15 | global | 1 | 4239 | 100.0% |

A step with 0 newly unlocked is a gate that unlocks nothing alone but
is the most frequent remaining gap; the programs it belongs to need
more than one gate.

### MBPP greedy gate order (974 function-shaped, 278 in fragment today)

| step | gate | newly unlocked | cumulative | of function-shaped |
|---|---|---|---|---|
| 1 | real | 362 | 640 | 65.7% |
| 2 | import | 102 | 742 | 76.2% |
| 3 | generator | 55 | 797 | 81.8% |
| 4 | map | 54 | 851 | 87.4% |
| 5 | closure | 52 | 903 | 92.7% |
| 6 | unbounded-loop | 29 | 932 | 95.7% |
| 7 | seq-slice-step | 10 | 942 | 96.7% |
| 8 | string-lib | 9 | 951 | 97.6% |
| 9 | seq-slice-negative | 8 | 959 | 98.5% |
| 10 | none-type | 6 | 965 | 99.1% |
| 11 | any-type | 3 | 968 | 99.4% |
| 12 | class | 4 | 972 | 99.8% |
| 13 | exception | 2 | 974 | 100.0% |

### HumanEval greedy gate order (164 function-shaped, 14 in fragment today)

| step | gate | newly unlocked | cumulative | of function-shaped |
|---|---|---|---|---|
| 1 | any-type | 83 | 97 | 59.1% |
| 2 | real | 16 | 113 | 68.9% |
| 3 | closure | 11 | 124 | 75.6% |
| 4 | generator | 10 | 134 | 81.7% |
| 5 | seq-slice-step | 6 | 140 | 85.4% |
| 6 | unbounded-loop | 5 | 145 | 88.4% |
| 7 | map | 4 | 149 | 90.9% |
| 8 | string-lib | 4 | 153 | 93.3% |
| 9 | none-type | 3 | 156 | 95.1% |
| 10 | seq-slice-negative | 3 | 159 | 97.0% |
| 11 | import | 3 | 162 | 98.8% |
| 12 | exception | 2 | 164 | 100.0% |

### APPS greedy gate order (3101 function-shaped, 780 in fragment today)

| step | gate | newly unlocked | cumulative | of function-shaped |
|---|---|---|---|---|
| 1 | class | 266 | 1046 | 33.7% |
| 2 | real | 226 | 1272 | 41.0% |
| 3 | generator | 257 | 1529 | 49.3% |
| 4 | import | 246 | 1775 | 57.2% |
| 5 | map | 270 | 2045 | 65.9% |
| 6 | string-lib | 221 | 2266 | 73.1% |
| 7 | closure | 231 | 2497 | 80.5% |
| 8 | seq-slice-step | 172 | 2669 | 86.1% |
| 9 | unbounded-loop | 161 | 2830 | 91.3% |
| 10 | seq-slice-negative | 89 | 2919 | 94.1% |
| 11 | none-type | 73 | 2992 | 96.5% |
| 12 | exception | 78 | 3070 | 99.0% |
| 13 | io | 30 | 3100 | 100.0% |
| 14 | global | 1 | 3101 | 100.0% |

### CodeContests: no function-shaped problems

## By source

| source | problems | function-shaped | stdin-shaped | in fragment | stdin in fragment once signature extracted |
|---|---|---|---|---|---|
| MBPP | 974 | 974 | 0 | 278 | 0 |
| HumanEval | 164 | 164 | 0 | 14 | 0 |
| APPS | 10000 | 3101 | 6899 | 780 | 2432 |
| CodeContests | 13610 | 0 | 13610 | 0 | 2913 |

## Burdens (expressible in t at a translation cost)

| burden | problems | meaning |
|---|---|---|
| stdin-to-signature | 20509 | a stdin-shaped problem carries no function signature; one has to be extracted from its input format before t can pose the problem at all |
| string-as-seq | 13339 | a string used only the way t's `seq` of code points already covers: a str literal, a str-typed io value, indexing/len/slicing/concatenation/comparison of strings, `ord`/`chr`, iterating over a string, or `in` on a string (a bounded exists) -- SPEC.md's 'Strings as sequences of code points' |
| string-lib-v1 | 11978 | a Python string-library use that IS one of SPEC.md's 'The string library (v1)' sixteen members, called in a v1 form: `split()` or `split(c)` on a one-code-point literal, `join`, `str()`, `count`/`find`/`replace`/`startswith`/`endswith` with any argument, `strip`/`lstrip`/`rstrip` with no argument, `lower`/`upper`, or one of the four predicates isdigit/isalpha/isupper/islower; tags only when EVERY string-library use in the solution reads this way -- one use outside v1 anywhere in the same solution tags the gap `string-lib` instead, not both. Split from `string-lib` 2026-09-11 the day SPEC.md's section landed |
| seq-literal | 8599 | a sequence literal [..] in an expression: t's v1 already has seq (SPEC.md 'Sequences: literals, concatenation, slices'), landed 2026-09-09, so this is expressible directly, not a gap |
| tuple-pair | 7747 | a tuple of exactly two values, each an int, bool or seq of ints, built, returned, passed, compared, or unpacked from such a pair: t's v1 already has {"pair": [T1, T2]} (SPEC.md 'Pairs (v1)'), landed 2026-09-10 |
| builtin-math | 6624 | min, max, sum or abs; t can express each but has no builtin for any of them |
| seq-append | 6030 | sequence concatenation `+` or .append()/.extend()/.insert(): t's v1 already has + on seqs (SPEC.md 'Sequences: literals, concatenation, slices'), landed as r + [x] or r + s |
| comprehension | 5920 | a list/set/dict comprehension over ints; t writes this as an explicit loop or a quantifier |
| tuple | 3872 | IN THE FRAGMENT since 2026-10-06 (SPEC.md Compositional types): a tuple of three or more elements, a nested tuple, a tuple with a string component (until strings-as-seq's seq-of-code-points model covers a pair component too), or a list of tuples (the separate gap `nested-seq-pair`, tagged where a list literal's own elements are inspected): SPEC.md's 'Pairs (v1)' covers only the two-element case, the burden tuple-pair |
| nested-seq | 3606 | IN THE FRAGMENT since 2026-10-06 (SPEC.md Compositional types): a seq of seq whose row type could not be read as string or tuple (an int/bool row, or a subscript of a subscript, or a grid a static read genuinely cannot classify): SPEC.md's 'Nested sequences (v1)' burden `seq<seq<int>>` and the unreadable fallback both land here |
| sort | 2908 | sorted() or .sort(); expressible in t but needs a spec, not a builtin |
| seq-slice | 2474 | slicing s[a:b], s[a:], s[:b] with non-negative bounds and no step: t's v1 already has slice (SPEC.md 'Sequences: literals, concatenation, slices'); a negative bound or a step is measured separately as the gaps seq-slice-negative / seq-slice-step |
| py2-unparseable | 2107 | the chosen Python solution does not parse under Python 3's ast (typically a Python 2 solution: print statement, raw_input, etc.); only its io-types are measured, its AST is not |
| set | 1604 | IN THE FRAGMENT since 2026-10-06 (SPEC.md Compositional types): set literal, set(), frozenset(), a set/dict comprehension's set form |
| recursion | 1496 | the solution's function calls itself; t supports this through spec functions (self-calls and calls to earlier functions), so it is a burden, not a gap |
| nested-seq-pair | 566 | IN THE FRAGMENT since 2026-10-06 (SPEC.md Compositional types): a seq of seq whose row reads as a tuple (a list of tuples, or a nested annotation through Tuple/tuple): SPEC.md v1 has no seq of pairs |
| nested-seq-string | 119 | IN THE FRAGMENT since 2026-10-06 (SPEC.md Compositional types): a seq of seq (or equivalent) whose row reads as a string: SPEC.md v1 has no seq<string> type |
| nested-seq-deep | 95 | IN THE FRAGMENT since 2026-10-06 (SPEC.md Compositional types): three or more levels of seq nesting: SPEC.md v1's nested seq is exactly one level deep |
| multi-return | 43 | IN THE FRAGMENT since 2026-10-06 (SPEC.md Compositional types): a function-shaped problem returning a tuple (several return values; t returns exactly one) |

## Method

Run time: 29.4s. Every source's first Python solution only; APPS and CodeContests carry many, all but the first are
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
else needs the burden `string-as-seq`. A lexical scan cannot show a
map, a set, a tuple or a nested sequence, so those four gaps are
never attempted for a stdin-shaped problem's io-types; only its
SOLUTION's AST can still tag them.

A stdin-shaped problem is never `in_fragment`: SYNTAX.md and the
brief for this file agree a signature has to exist before a
problem can be posed to t at all, which is the `stdin-to-signature`
burden every stdin-shaped problem carries. `would_be_in_fragment_with_signature` in the JSON (and the by-source table above) marks
the ones whose sample io has no decimal-valued (`real`) token and
whose solution tags no gap -- everything BUT the missing signature
already fits; a string token in the sample is no longer
disqualifying on its own, since `string-as-seq` is a burden, not a
gap. A problem with no Python solution, or whose chosen solution is
`py2-unparseable`, is never marked this way even when its sample io
has no `real` token: the solution side is unmeasured, not measured
clean.

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
  computed value: a step present on the slice tags `seq-slice-step`
  instead, and a bound written as a negative literal (`s[:-1]`,
  `ast`'s own `UnaryOp(USub, ..)` shape for a negative number) tags
  `seq-slice-negative` instead; a negative bound reached through a
  variable or an expression (`s[:n-1]`) is not recognized this way
  and reads as the plain (non-negative) burden, an undercount of
  the two gaps in the same direction every other syntactic detector
  here accepts;
- `unbounded-loop` fires on EVERY `break` and `continue`, not only
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
