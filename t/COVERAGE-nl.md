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
- in t's fragment today: **599** of 4239 function-shaped (14.1%)
- stdin-shaped, in fragment once a signature is extracted (all-int sample io, solution tags no gap): **1022** of 20509 (5.0%)
- function-shaped problems blocked by exactly one gap: 1438

## Gaps, by problems that need them

| gap | problems | sole blocker for (function-shaped) | meaning |
|---|---|---|---|
| string-lib | 13266 | 298 | the Python string LIBRARY, not the seq-of-code-points model SPEC.md's v1 covers: any str method call (upper/lower/split/join/strip/replace/startswith/endswith/find/count/isdigit/...), an f-string or `.format()`, `str()` or a based `int(x, base)` conversion of a string, or `sorted()` on a string |
| unbounded-loop | 4403 | 28 | while True, or a break/continue (t has no while-true, no continue, and a break is only in the fragment as a tail-position return, decision 23 -- not distinguished here, see Method) |
| import | 3932 | 160 | an import other than math, sys or typing: an unmodeled library the solution's meaning depends on |
| tuple | 3872 | 56 | a tuple of three or more elements, a nested tuple, a tuple with a string component (until strings-as-seq's seq-of-code-points model covers a pair component too), or a list of tuples (the separate gap `nested-seq-pair`, tagged where a list literal's own elements are inspected): SPEC.md's 'Pairs (v1)' covers only the two-element case, the burden tuple-pair |
| nested-seq | 3606 | 154 | a seq of seq whose row type could not be read as string or tuple (an int/bool row, or a subscript of a subscript, or a grid a static read genuinely cannot classify): SPEC.md's 'Nested sequences (v1)' burden `seq<seq<int>>` and the unreadable fallback both land here |
| real | 3517 | 226 | real numbers: a float literal, true division `/`, math.sqrt, float(), or a decimal-valued io token |
| map | 2463 | 52 | dict literal, dict(), defaultdict, Counter, or a dict-typed io value |
| closure | 2243 | 31 | a lambda, a nested def, or map/filter with a lambda |
| generator | 1686 | 83 | a generator expression or a generator function (yield): t has no lazy or deferred evaluation |
| class | 1641 | 177 | a class definition (t has no classes, no heap) |
| set | 1604 | 34 | set literal, set(), frozenset(), a set/dict comprehension's set form |
| seq-slice-step | 852 | 16 | a slice with a step, s[a:b:c]: t's slice form takes two bounds only, no step |
| nested-seq-pair | 566 | 0 | a seq of seq whose row reads as a tuple (a list of tuples, or a nested annotation through Tuple/tuple): SPEC.md v1 has no seq of pairs |
| exception | 502 | 9 | try/except/raise |
| seq-slice-negative | 489 | 16 | a slice bound that is a negative literal, s[-1:] or s[:-1]: t's slice is defined only for 0 <= a <= b <= len(s), so a negative index is measured apart from the burden seq-slice |
| global | 316 | 0 | global or nonlocal: mutable state outside the function, which t's pure functions have no notion of |
| any-type | 141 | 55 | the interface's type could not be pinned to one of the other named types: a bare Any annotation, a call expression as a test argument, or an untyped io value |
| nested-seq-string | 119 | 8 | a seq of seq (or equivalent) whose row reads as a string: SPEC.md v1 has no seq<string> type |
| none-type | 99 | 15 | Optional[..] or an explicit None return/argument |
| nested-seq-deep | 95 | 15 | three or more levels of seq nesting: SPEC.md v1's nested seq is exactly one level deep |
| multi-return | 43 | 3 | a function-shaped problem returning a tuple (several return values; t returns exactly one) |
| io | 30 | 2 | input()/print()/sys.stdin used INSIDE a function-shaped solution (for a stdin-shaped problem, I/O is the shape itself, not a separate gap) |

## Greedy gate order, whole corpus (function-shaped population)

| step | gate | newly unlocked | cumulative in fragment | of function-shaped |
|---|---|---|---|---|
| 1 | string-lib | 415 | 1014 | 23.9% |
| 2 | real | 258 | 1272 | 30.0% |
| 3 | class | 249 | 1521 | 35.9% |
| 4 | import | 231 | 1752 | 41.3% |
| 5 | generator | 270 | 2022 | 47.7% |
| 6 | nested-seq | 305 | 2327 | 54.9% |
| 7 | map | 269 | 2596 | 61.2% |
| 8 | closure | 202 | 2798 | 66.0% |
| 9 | tuple | 214 | 3012 | 71.1% |
| 10 | set | 206 | 3218 | 75.9% |
| 11 | seq-slice-step | 169 | 3387 | 79.9% |
| 12 | unbounded-loop | 176 | 3563 | 84.1% |
| 13 | any-type | 129 | 3692 | 87.1% |
| 14 | nested-seq-string | 91 | 3783 | 89.2% |
| 15 | seq-slice-negative | 92 | 3875 | 91.4% |
| 16 | nested-seq-deep | 80 | 3955 | 93.3% |
| 17 | none-type | 81 | 4036 | 95.2% |
| 18 | exception | 82 | 4118 | 97.1% |
| 19 | nested-seq-pair | 49 | 4167 | 98.3% |
| 20 | multi-return | 41 | 4208 | 99.3% |
| 21 | io | 30 | 4238 | 100.0% |
| 22 | global | 1 | 4239 | 100.0% |

A step with 0 newly unlocked is a gate that unlocks nothing alone but
is the most frequent remaining gap; the programs it belongs to need
more than one gate.

### MBPP greedy gate order (974 function-shaped, 256 in fragment today)

| step | gate | newly unlocked | cumulative | of function-shaped |
|---|---|---|---|---|
| 1 | real | 206 | 462 | 47.4% |
| 2 | import | 86 | 548 | 56.3% |
| 3 | tuple | 62 | 610 | 62.6% |
| 4 | string-lib | 59 | 669 | 68.7% |
| 5 | nested-seq | 52 | 721 | 74.0% |
| 6 | generator | 56 | 777 | 79.8% |
| 7 | map | 49 | 826 | 84.8% |
| 8 | closure | 51 | 877 | 90.0% |
| 9 | set | 33 | 910 | 93.4% |
| 10 | unbounded-loop | 29 | 939 | 96.4% |
| 11 | seq-slice-step | 10 | 949 | 97.4% |
| 12 | seq-slice-negative | 8 | 957 | 98.3% |
| 13 | none-type | 6 | 963 | 98.9% |
| 14 | any-type | 3 | 966 | 99.2% |
| 15 | class | 4 | 970 | 99.6% |
| 16 | nested-seq-pair | 2 | 972 | 99.8% |
| 17 | exception | 2 | 974 | 100.0% |

### HumanEval greedy gate order (164 function-shaped, 8 in fragment today)

| step | gate | newly unlocked | cumulative | of function-shaped |
|---|---|---|---|---|
| 1 | any-type | 55 | 63 | 38.4% |
| 2 | string-lib | 22 | 85 | 51.8% |
| 3 | real | 15 | 100 | 61.0% |
| 4 | closure | 8 | 108 | 65.9% |
| 5 | generator | 10 | 118 | 72.0% |
| 6 | set | 7 | 125 | 76.2% |
| 7 | map | 5 | 130 | 79.3% |
| 8 | unbounded-loop | 5 | 135 | 82.3% |
| 9 | multi-return | 4 | 139 | 84.8% |
| 10 | seq-slice-step | 6 | 145 | 88.4% |
| 11 | nested-seq | 4 | 149 | 90.9% |
| 12 | tuple | 3 | 152 | 92.7% |
| 13 | none-type | 3 | 155 | 94.5% |
| 14 | seq-slice-negative | 3 | 158 | 96.3% |
| 15 | import | 3 | 161 | 98.2% |
| 16 | exception | 2 | 163 | 99.4% |
| 17 | nested-seq-pair | 1 | 164 | 100.0% |

### APPS greedy gate order (3101 function-shaped, 335 in fragment today)

| step | gate | newly unlocked | cumulative | of function-shaped |
|---|---|---|---|---|
| 1 | string-lib | 251 | 586 | 18.9% |
| 2 | class | 218 | 804 | 25.9% |
| 3 | real | 193 | 997 | 32.2% |
| 4 | generator | 207 | 1204 | 38.8% |
| 5 | nested-seq | 215 | 1419 | 45.8% |
| 6 | import | 213 | 1632 | 52.6% |
| 7 | map | 229 | 1861 | 60.0% |
| 8 | closure | 160 | 2021 | 65.2% |
| 9 | set | 166 | 2187 | 70.5% |
| 10 | seq-slice-step | 152 | 2339 | 75.4% |
| 11 | unbounded-loop | 137 | 2476 | 79.8% |
| 12 | tuple | 112 | 2588 | 83.5% |
| 13 | nested-seq-string | 91 | 2679 | 86.4% |
| 14 | seq-slice-negative | 81 | 2760 | 89.0% |
| 15 | nested-seq-deep | 80 | 2840 | 91.6% |
| 16 | none-type | 72 | 2912 | 93.9% |
| 17 | exception | 78 | 2990 | 96.4% |
| 18 | nested-seq-pair | 46 | 3036 | 97.9% |
| 19 | multi-return | 34 | 3070 | 99.0% |
| 20 | io | 30 | 3100 | 100.0% |
| 21 | global | 1 | 3101 | 100.0% |

### CodeContests: no function-shaped problems

## By source

| source | problems | function-shaped | stdin-shaped | in fragment | stdin in fragment once signature extracted |
|---|---|---|---|---|---|
| MBPP | 974 | 974 | 0 | 256 | 0 |
| HumanEval | 164 | 164 | 0 | 8 | 0 |
| APPS | 10000 | 3101 | 6899 | 335 | 464 |
| CodeContests | 13610 | 0 | 13610 | 0 | 558 |

## Burdens (expressible in t at a translation cost)

| burden | problems | meaning |
|---|---|---|
| stdin-to-signature | 20509 | a stdin-shaped problem carries no function signature; one has to be extracted from its input format before t can pose the problem at all |
| string-as-seq | 13339 | a string used only the way t's `seq` of code points already covers: a str literal, a str-typed io value, indexing/len/slicing/concatenation/comparison of strings, `ord`/`chr`, iterating over a string, or `in` on a string (a bounded exists) -- SPEC.md's 'Strings as sequences of code points' |
| seq-literal | 8599 | a sequence literal [..] in an expression: t's v1 already has seq (SPEC.md 'Sequences: literals, concatenation, slices'), landed 2026-09-09, so this is expressible directly, not a gap |
| tuple-pair | 7747 | a tuple of exactly two values, each an int, bool or seq of ints, built, returned, passed, compared, or unpacked from such a pair: t's v1 already has {"pair": [T1, T2]} (SPEC.md 'Pairs (v1)'), landed 2026-09-10 |
| builtin-math | 6624 | min, max, sum or abs; t can express each but has no builtin for any of them |
| seq-append | 6030 | sequence concatenation `+` or .append()/.extend()/.insert(): t's v1 already has + on seqs (SPEC.md 'Sequences: literals, concatenation, slices'), landed as r + [x] or r + s |
| comprehension | 5920 | a list/set/dict comprehension over ints; t writes this as an explicit loop or a quantifier |
| sort | 2908 | sorted() or .sort(); expressible in t but needs a spec, not a builtin |
| seq-slice | 2474 | slicing s[a:b], s[a:], s[:b] with non-negative bounds and no step: t's v1 already has slice (SPEC.md 'Sequences: literals, concatenation, slices'); a negative bound or a step is measured separately as the gaps seq-slice-negative / seq-slice-step |
| py2-unparseable | 2107 | the chosen Python solution does not parse under Python 3's ast (typically a Python 2 solution: print statement, raw_input, etc.); only its io-types are measured, its AST is not |
| recursion | 1496 | the solution's function calls itself; t supports this through spec functions (self-calls and calls to earlier functions), so it is a burden, not a gap |

## Method

Run time: 43.4s. Every source's first Python solution only; APPS and CodeContests carry many, all but the first are
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
  (`STRING_METHODS` in nl_census.py) all tag the single `string-lib`
  gap rather than each having a name of their own, since all three
  need the Python string LIBRARY, not just the seq-of-code-points
  model SPEC.md's v1 covers; a bare str/f-string/char literal, by
  contrast, tags only the burden `string-as-seq`;
- `count` is in `STRING_METHODS` even though `list.count(..)` uses
  the same attribute name; a solution counting occurrences in a
  list, not a string, is over-counted into `string-lib` here, the
  same name-only approximation `.sort` already accepts elsewhere;
- `ord`/`chr` calls tag `string-as-seq` (a burden: t already has
  the code point, this is only the name Python gives it);
- `str(..)` is tagged `string-lib` unconditionally, the same
  treatment `float(..)` already gets; `int(..)` is tagged only when
  called with an explicit base (`int(x, 16)`), unambiguous string
  parsing -- a bare `int(x)` is NOT tagged even when x is a string,
  since the common `int(input())` idiom would otherwise swamp
  `string-lib` on nearly every stdin-shaped solution with input-
  parsing boilerplate a signature-extraction step would remove, not
  the algorithmic core; this undercounts genuine string-to-int
  parsing written without a base argument;
- `sorted(..)` always tags the `sort` burden, and additionally tags
  `string-lib` only when its argument is SYNTACTICALLY a string (a
  literal, an f-string, a `str(..)` call, or a chained string-
  method call) -- `sorted(a_variable)` is not resolved to a type
  and is undercounted when the variable holds a string;
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
