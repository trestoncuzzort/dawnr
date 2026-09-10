# t coverage census: MBPP-DFY (dafny-synthesis) (164 programs)

What this corpus needs that t does not have, program by program, and
which gate opens the most programs. Lexical census, no kernel run; the
in-fragment count says a program's constructs fit SYNTAX.md, not that
seven kernels verify its t rendering. Method and detectors at the end.

## Headline

- programs: 164; with a method carrying its own ensures (gradable): 164
- in t's fragment today: **131** of 164 gradable (79.9%)
- gradable programs blocked by exactly one gap: 27

## Gaps, by programs that need them

| gap | programs | sole blocker for (gradable) | meaning |
|---|---|---|---|
| real | 10 | 9 | real numbers |
| set | 7 | 6 | set, iset, multiset, set comprehension or set literal |
| char-arith | 3 | 3 | char arithmetic |
| array | 2 | 1 | array2/array3, array?<..> (nullable), or a non-int/non-nat element type |
| nested-seq-string | 2 | 2 | seq<string>, or seq<seq<char>> -- a row that is itself string-shaped, since a Dafny string is a seq of chars; a bare seq<char> is not this gap, it is the burden string-as-seq |
| bitvector | 2 | 1 | bit vectors or bitwise operators |
| multi-return-arity | 2 | 1 | a method with more than one return value that t cannot map to one pair return -- three or more return values, or exactly two whose component types this lifter does not carry (array, bitvector, real, map, multiset, a nested Dafny tuple, a bare char) -- see the burden multi-return-pair |
| early-exit | 2 | 1 | a continue, a labeled break, or a break whose loop is not the tail of the method body (a break inside a nested loop, or followed by another loop) |
| multi-method | 2 | 0 | more than one graded method (Main excluded) where some method's body calls ANOTHER declared method by name -- decision 9 lifts one task per method, so independent methods (no cross-call) are the burden multi-method-independent, not this gap |
| zero-returns | 2 | 1 | a method with no return value (t returns exactly one) that is not row 22's own modifies-param shape -- see the burden zero-returns-array |
| seq-of-bool | 1 | 0 | seq<bool>, one level, bool element -- its own gap, split out of the old nested-seq row 2026-09-09 |
| nested-seq-other | 1 | 0 | a nested seq/array this file doesn't give its own name: seq<real>, seq<T> for a datatype or identifier, or a 2-level nesting whose innermost type is not int/nat/char |
| higher-order | 1 | 0 | lambdas or function types |
| seq-comprehension | 1 | 0 | seq(n, i => e) -- t's fill is constant-valued, this is not (v1 gap, unlike rows 25-27) |
| array-mutation | 1 | 0 | array mutation decision 22 does not map: more than one mutated array, multiset over a mutated array's slice, or a modifies clause naming anything but the one array |
| tuple | 1 | 1 | tuples |
| unbounded-quantifier | 1 | 1 | quantifier without an int range |

## Greedy gate order (open the gate that unlocks the most programs)

| step | gate | newly unlocked | cumulative in fragment | of gradable |
|---|---|---|---|---|
| 1 | real | 9 | 140 | 85.4% |
| 2 | set | 6 | 146 | 89.0% |
| 3 | char-arith | 3 | 149 | 90.9% |
| 4 | multi-return-arity | 2 | 151 | 92.1% |
| 5 | nested-seq-string | 2 | 153 | 93.3% |
| 6 | array | 1 | 154 | 93.9% |
| 7 | zero-returns | 1 | 155 | 94.5% |
| 8 | early-exit | 1 | 156 | 95.1% |
| 9 | multi-method | 1 | 157 | 95.7% |
| 10 | array-mutation | 1 | 158 | 96.3% |
| 11 | seq-of-bool | 1 | 159 | 97.0% |
| 12 | unbounded-quantifier | 1 | 160 | 97.6% |
| 13 | bitvector | 1 | 161 | 98.2% |
| 14 | nested-seq-other | 1 | 162 | 98.8% |
| 15 | tuple | 1 | 163 | 99.4% |
| 16 | higher-order | 0 | 163 | 99.4% |
| 17 | seq-comprehension | 1 | 164 | 100.0% |


### The same order on the MBPP-DFY family alone (164 gradable, the LLM-shaped subset)

| step | gate | newly unlocked | cumulative | of gradable |
|---|---|---|---|---|
| 1 | real | 9 | 140 | 85.4% |
| 2 | set | 6 | 146 | 89.0% |
| 3 | char-arith | 3 | 149 | 90.9% |
| 4 | multi-return-arity | 2 | 151 | 92.1% |
| 5 | nested-seq-string | 2 | 153 | 93.3% |
| 6 | array | 1 | 154 | 93.9% |
| 7 | zero-returns | 1 | 155 | 94.5% |
| 8 | early-exit | 1 | 156 | 95.1% |
| 9 | multi-method | 1 | 157 | 95.7% |
| 10 | array-mutation | 1 | 158 | 96.3% |
| 11 | seq-of-bool | 1 | 159 | 97.0% |
| 12 | unbounded-quantifier | 1 | 160 | 97.6% |
| 13 | bitvector | 1 | 161 | 98.2% |
| 14 | nested-seq-other | 1 | 162 | 98.8% |
| 15 | tuple | 1 | 163 | 99.4% |
| 16 | higher-order | 0 | 163 | 99.4% |
| 17 | seq-comprehension | 1 | 164 | 100.0% |

A step with 0 newly unlocked is a gate that unlocks nothing alone but
is the most frequent remaining gap; the programs it belongs to need
more than one gate.

## By family

| family | programs | gradable | in fragment |
|---|---|---|---|
| MBPP-DFY (dafny-synthesis) | 164 | 164 | 131 |

## Burdens (expressible at a translation cost)

| burden | programs | meaning |
|---|---|---|
| spec-only-quantifier | 91 | quantifiers (bounded ones are in t) |
| no-if-no-loop | 79 | straight-line body: the twin ladder has only its extensional operators to try |
| for-loop | 77 | for loop (a while with a bound) |
| array-as-seq | 48 | array<int>/array<nat> (one dimension): read-only, mutated in place under modifies, or allocated and filled -- lifts to seq (decision 1, decision 22) |
| if-no-else | 48 | if without else |
| seq-concat | 42 | + on two seqs (concatenation) -- lifts to t's own + (LIFTER-DECISIONS.md row 26); lexical and approximate, UNDER-counts (see comment above) |
| untyped-var | 42 | var without a type (t declares every type) |
| seq-literal | 40 | sequence literal [..] in an expression -- lifts to t's seq literal (LIFTER-DECISIONS.md row 25) |
| seq-return | 37 | sequence-valued return of a method or a function -- lifts as a seq return (LIFTER-DECISIONS.md rows 22/25-27) |
| function-or-predicate | 36 | pure functions, as spec_funs when first-order over int and seq |
| iff | 30 | <==> (== on bools) |
| string-as-seq | 25 | a string or char used only the way t's seq of code points already covers: literals, |s|, indexing, +, a slice, ==/!=, char comparisons (<,<=,>,>=), as int -- SPEC.md 'Strings as sequences of code points', LIFTER-DECISIONS.md row 28 |
| break-as-return | 24 | an unlabeled break whose innermost loop is the tail of the method body, with at most a straight-line continuation after it (lifts to t's early-exit `return` of the method's own result, LIFTER-DECISIONS.md row 23) |
| seq-membership | 21 | in / !in (a bounded exists over a seq; set and map membership are their own gaps) |
| while-no-decreases | 19 | a loop without its decreases (t requires one) |
| seq-slice | 18 | slicing s[a..b], s[a..], s[..b] -- lifts to t's slice, sugars expanded (LIFTER-DECISIONS.md row 27) |
| frame-clause | 12 | modifies / reads (array frames when no class is present) |
| trailing-return | 12 | a return as the last statement (assign the result instead) |
| nested-seq | 10 | seq<seq<int>>/seq<seq<nat>> (array\d* variants included: array<seq<..>>, seq<array<..>>), one level of nesting, int/nat innermost -- or a nested seq literal display with no type at all, [[1,2],[3]] -- lifts to t's {'seq': 'seq'} (LIFTER-DECISIONS.md row 30) |
| as-cast | 8 | as int / as nat casts |
| early-return | 6 | a return that is not in tail position of a method body (lifts to t's early-exit `return` statement) |
| multi-return-pair | 3 | exactly two return values, both int/nat/bool/seq<int|nat|char>/string -- lifts to one pair-typed return (LIFTER-DECISIONS.md row 29) |
| nat | 3 | nat, as int with a >= 0 clause |
| zero-returns-array | 3 | a method with no return whose effect is its one array, lifted as a seq return by row 22 (LIFTER-DECISIONS.md row 22's modifies-param shape) |
| multi-method-independent | 1 | more than one graded method, none calling another by name -- decision 9 lifts one task per method, so no packaging decision is needed |
| parallel-assign | 1 | x, y := a, b (sequenced through a temporary) |

## Hints (proof scaffolding a kernel may need; t has none)

| hint | programs | meaning |
|---|---|---|
| assert | 7 | assert statements |
| old | 6 | old() / old@L() (two-state; heap or array frames) |
| ghost | 3 | ghost code |
| lemma | 2 | lemmas |
| ghost-var | 2 | ghost variables |
| calc | 1 | calc proofs |
| assign-such-that | 1 | assign-such-that in a lemma, a function or on a ghost variable (the executable one is the such-that-exec gap) |

## In fragment today

- dafny-synthesis_task_id_101.dfy
- dafny-synthesis_task_id_106.dfy
- dafny-synthesis_task_id_113.dfy
- dafny-synthesis_task_id_126.dfy
- dafny-synthesis_task_id_127.dfy
- dafny-synthesis_task_id_133.dfy
- dafny-synthesis_task_id_135.dfy
- dafny-synthesis_task_id_14.dfy
- dafny-synthesis_task_id_143.dfy
- dafny-synthesis_task_id_145.dfy
- dafny-synthesis_task_id_161.dfy
- dafny-synthesis_task_id_17.dfy
- dafny-synthesis_task_id_170.dfy
- dafny-synthesis_task_id_171.dfy
- dafny-synthesis_task_id_18.dfy
- dafny-synthesis_task_id_2.dfy
- dafny-synthesis_task_id_227.dfy
- dafny-synthesis_task_id_230.dfy
- dafny-synthesis_task_id_234.dfy
- dafny-synthesis_task_id_238.dfy
- dafny-synthesis_task_id_240.dfy
- dafny-synthesis_task_id_242.dfy
- dafny-synthesis_task_id_249.dfy
- dafny-synthesis_task_id_257.dfy
- dafny-synthesis_task_id_261.dfy
- dafny-synthesis_task_id_262.dfy
- dafny-synthesis_task_id_264.dfy
- dafny-synthesis_task_id_266.dfy
- dafny-synthesis_task_id_267.dfy
- dafny-synthesis_task_id_268.dfy
- dafny-synthesis_task_id_269.dfy
- dafny-synthesis_task_id_273.dfy
- dafny-synthesis_task_id_279.dfy
- dafny-synthesis_task_id_282.dfy
- dafny-synthesis_task_id_284.dfy
- dafny-synthesis_task_id_290.dfy
- dafny-synthesis_task_id_292.dfy
- dafny-synthesis_task_id_3.dfy
- dafny-synthesis_task_id_304.dfy
- dafny-synthesis_task_id_307.dfy
- dafny-synthesis_task_id_309.dfy
- dafny-synthesis_task_id_396.dfy
- dafny-synthesis_task_id_397.dfy
- dafny-synthesis_task_id_401.dfy
- dafny-synthesis_task_id_404.dfy
- dafny-synthesis_task_id_406.dfy
- dafny-synthesis_task_id_412.dfy
- dafny-synthesis_task_id_414.dfy
- dafny-synthesis_task_id_426.dfy
- dafny-synthesis_task_id_431.dfy
- dafny-synthesis_task_id_432.dfy
- dafny-synthesis_task_id_433.dfy
- dafny-synthesis_task_id_435.dfy
- dafny-synthesis_task_id_436.dfy
- dafny-synthesis_task_id_441.dfy
- dafny-synthesis_task_id_445.dfy
- dafny-synthesis_task_id_447.dfy
- dafny-synthesis_task_id_452.dfy
- dafny-synthesis_task_id_454.dfy
- dafny-synthesis_task_id_457.dfy
- dafny-synthesis_task_id_458.dfy
- dafny-synthesis_task_id_460.dfy
- dafny-synthesis_task_id_470.dfy
- dafny-synthesis_task_id_472.dfy
- dafny-synthesis_task_id_474.dfy
- dafny-synthesis_task_id_476.dfy
- dafny-synthesis_task_id_554.dfy
- dafny-synthesis_task_id_555.dfy
- dafny-synthesis_task_id_565.dfy
- dafny-synthesis_task_id_567.dfy
- dafny-synthesis_task_id_572.dfy
- dafny-synthesis_task_id_576.dfy
- dafny-synthesis_task_id_577.dfy
- dafny-synthesis_task_id_578.dfy
- dafny-synthesis_task_id_579.dfy
- dafny-synthesis_task_id_58.dfy
- dafny-synthesis_task_id_581.dfy
- dafny-synthesis_task_id_586.dfy
- dafny-synthesis_task_id_587.dfy
- dafny-synthesis_task_id_588.dfy
- dafny-synthesis_task_id_59.dfy
- dafny-synthesis_task_id_591.dfy
- dafny-synthesis_task_id_594.dfy
- dafny-synthesis_task_id_598.dfy
- dafny-synthesis_task_id_600.dfy
- dafny-synthesis_task_id_603.dfy
- dafny-synthesis_task_id_605.dfy
- dafny-synthesis_task_id_610.dfy
- dafny-synthesis_task_id_616.dfy
- dafny-synthesis_task_id_618.dfy
- dafny-synthesis_task_id_62.dfy
- dafny-synthesis_task_id_622.dfy
- dafny-synthesis_task_id_623.dfy
- dafny-synthesis_task_id_625.dfy
- dafny-synthesis_task_id_626.dfy
- dafny-synthesis_task_id_627.dfy
- dafny-synthesis_task_id_629.dfy
- dafny-synthesis_task_id_637.dfy
- dafny-synthesis_task_id_641.dfy
- dafny-synthesis_task_id_69.dfy
- dafny-synthesis_task_id_70.dfy
- dafny-synthesis_task_id_728.dfy
- dafny-synthesis_task_id_732.dfy
- dafny-synthesis_task_id_733.dfy
- dafny-synthesis_task_id_741.dfy
- dafny-synthesis_task_id_743.dfy
- dafny-synthesis_task_id_751.dfy
- dafny-synthesis_task_id_755.dfy
- dafny-synthesis_task_id_759.dfy
- dafny-synthesis_task_id_760.dfy
- dafny-synthesis_task_id_762.dfy
- dafny-synthesis_task_id_769.dfy
- dafny-synthesis_task_id_77.dfy
- dafny-synthesis_task_id_770.dfy
- dafny-synthesis_task_id_775.dfy
- dafny-synthesis_task_id_79.dfy
- dafny-synthesis_task_id_790.dfy
- dafny-synthesis_task_id_792.dfy
- dafny-synthesis_task_id_793.dfy
- dafny-synthesis_task_id_798.dfy
- dafny-synthesis_task_id_8.dfy
- dafny-synthesis_task_id_80.dfy
- dafny-synthesis_task_id_801.dfy
- dafny-synthesis_task_id_804.dfy
- dafny-synthesis_task_id_807.dfy
- dafny-synthesis_task_id_808.dfy
- dafny-synthesis_task_id_809.dfy
- dafny-synthesis_task_id_86.dfy
- dafny-synthesis_task_id_89.dfy
- dafny-synthesis_task_id_94.dfy
- dafny-synthesis_task_id_95.dfy

## Method

Source is masked (comments, string and char literals blanked, their
presence recorded outside `{:attribute}` arguments and outside the
`method Main` harness, which is blanked in the ORIGINAL source so that
a literal elsewhere in the file is still recorded) and each detector is
a regular expression or a small scanner over the masked text;
`coverage_census.py` lists every one.

Lexical detection is approximate in both directions: `+` on sequences
is not distinguished from `+` on integers (concatenation is not tagged,
so seq needs are under-counted) and `nat` is a burden not a gap. Where
one token means two things, the detector reads its context:

- proof scaffolding is blanked before any gap or burden is read: whole
  lemma declarations, and `assert`, `assume` and `calc` statements.
  SYNTAX.md makes these hints, which never put a program outside the
  fragment, so a construct appearing only inside one is not counted;
  the hint rows below are counted on the unblanked text;
- a quantifier is unbounded when a bound variable carries a non-int
  declared type, or carries no int range on the variable itself (a bare
  `v`, not `v*v`) in the guard; membership `v in e` counts as a range,
  `v !in e` does not, and an equality `v == e` counts only when this
  file types `e` as an integer, by declaring the function it calls or
  the collection it indexes to return int or nat;
- `a[i] := e` is an element assignment only when the left-hand side
  starts a statement, so the `:=` inside a functional update
  `m[k := v]` is not one, and the index is bracket-balanced;
- `s[i := v]` is a sequence update only when its receiver is a slice,
  or is not named as a map, imap or multiset in a file that holds a
  sequence somewhere;
- a `[` opens a sequence display only when what precedes it is not an
  identifier, `]` or `)`, or is one of a fixed list of keywords
  (`then [0]`, `else []`, `return [];`);
- a brace group holding only identifiers or integers is a set display
  only in expression position: `predicate P() { false }` is a body;
- `case` alone does not prove a datatype, since a match always carries
  its `match` keyword; `if { case .. }` is the guarded-alternative
  statement and is tagged as nondeterminism instead;
- a return is early only when it is not in tail position of a `method`
  body; a return in a lemma, a function or a predicate is not an exit;
- `:|` is nondeterministic choice (a gap) in a non-ghost method or
  constructor and proof scaffolding (a hint) in a lemma, a function, a
  ghost declaration or the ghost-only `:| assume P` form;
- a program is gradable when a METHOD carries an ensures of its own:
  an ensures on a function, a lemma, a constructor or an iterator
  states nothing a kernel would grade about the method;
- a comma inside `(int, int)` or `map<K, V>` is part of one type, not a
  second return value, and such a group is a tuple only when no call,
  index, arrow type, datatype update or binder head claims it first;
- a real literal is a digit run, a dot and a digit run, never glued to
  an identifier or another dot, so `x.1.1` is a tuple projection;
- an arrow type is `->`, `-->` or `~>` with or without spaces, and a
  declaration is generic even when an attribute stands between the
  keyword and the name.

A declaration with no body (an uninterpreted function, a method
signature), a method with no return value, a least or greatest
predicate, and spec functions in a call cycle are gaps of their own.
Every file's tag set is in the JSON beside this report when `--json` is
given, so any row can be checked against its source.
