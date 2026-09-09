# The spec experiment's pool, version 2: strings

2026-09-10. No model was run for this: there is no free GPU memory right
now, and this file is a measurement of the pool and the prompt only, taken
with `python3 spec_experiment.py pool [--pool v1|v2]` and direct calls into
`mbpp_dfy.parse_assertion`, `spec_experiment.build_prompt`,
`surface.parse`, `fuzz_lower.check_wf`, and `interp` through
`spec_experiment.run_point`. Version 1 of the pool and the prompt are
unchanged: both are new options with `v1` as the default, and `pool()` and
`build_prompt()` called with no arguments (as `loop_dataset.py` and
`loop_generate.py` already do) return exactly what they always returned.

## What changed

`mbpp_dfy.parse_assertion(src, strings=False)` and its helper
`mbpp_dfy._literal(node, strings=False)` gained a `strings` parameter,
default off. With `strings=True` (SPEC.md "Strings as sequences of code
points"), a Python string literal argument or expected value is no longer
refused as `arg:str` / `expected:str`. Its code points come from `ord(c)`
over the string Python's own `ast.parse` already decoded, so an escape (a
newline, a tab, a Python unicode escape, or a literal non-ASCII character
typed directly into the source) is resolved before this function ever
sees it, and a code point outside the ASCII range is a code point, not a
byte. A length-1 string becomes a t CHARACTER,
`("int", codepoint)`, exactly as the notation's `'a'` is sugar for
`{"int": 97}`; any other length, including 0, becomes a t STRING, a `seq`
of code points, exactly as `"abc"` is sugar for the seq literal `[97, 98,
99]` and `""` for `[]`. This is the one place t itself draws no line
between a one-character string and a character (SPEC.md says so directly),
so the parser draws none either. Every other literal kind (`int`, `bool`,
negative int, a list of int, a tuple, a dict, a set, a call, a bare name) is
untouched; `strings=False` is byte-for-byte what `parse_assertion` and
`_literal` always did, checked directly (see "Regression" below).

`spec_experiment.py` gained `--pool {v1,v2}` (default `v1`) on all five
subcommands, and `pool()`/`pool_report()` take the same argument, plus
`--prompt {v1,v2}` (default `v1`) on `generate`, threaded into
`build_prompt()`/`fewshot_text()`. `v2`'s grammar (`GRAMMAR_V2`, a separate
constant, not a patch to `GRAMMAR`) adds the sequence literal, `+`
concatenation, and slice, and the char/string sugar; its few-shot list
(`FEWSHOT_V2_EXTRA`) adds two tasks that use them, described below.

## Pool size

| | problems | in the pool |
|---|---:|---:|
| v1 | 974 | **368** |
| v2 | 974 | **606** |

v2 adds **238** problems (+64.7% over v1's 368; +24.4% of the full 974).
v1's 368 ids are a subset of v2's 606 (verified: `set(pool("v1")) <=
set(pool("v2"))`, and `pool_report("v1")` before and after the code change
returns the identical `{"problems": 974, "in_pool": 368, "refused": {...}}`
object, byte-for-byte, matched against a copy taken before any edit).

Of the 238 added, **164 needed a string to be admitted at all**: 148 were
blocked by a string somewhere in an argument (`arg:str` under v1's
parsing), 16 by a string result (`expected:str`). The remaining **74 carry
no string literal anywhere** (checked directly against the raw assertion
text, not inferred): their arguments and result were already fully inside
t's v1 fragment, and the only thing excluding them from v1's pool was that
`seq` was not an admitted return type. `seq` has been a legal t return
type since 2026-09-09 ("Sequences as values"), one day after the pool was
frozen at 368, and admitting a string result requires admitting `seq` as a
return type at all (a string result *is* a seq once parsed); t draws no
line between a string-shaped seq and any other seq, so the same widening
that lets in a string result also lets in a plain list-of-int result. This
is named here so the +238 figure is not mistaken for "+238 problems that
need strings": it is 164 that do, plus 74 that were waiting on a different,
already-landed gate. Every added problem was blocked by exactly one of
these three conditions; none needed more than one (148 + 16 + 74 = 238
exactly, no overlap).

## Why the rest still refuse

368 problems remain refused under v2. Per problem (not per assertion; a
problem needs every assertion to parse and its result type admitted), 359
are refused for exactly one reason and 9 for two. Reason names are the
ones `parse_assertion`/`pool_report` already use (`arg:X` / `expected:X`,
`X` from `_Unsupported`'s existing vocabulary); none invented:

| reason | problems | what it is | example |
|---|---:|---|---|
| `arg:tuple` | 129 | a tuple argument | `similar_elements((3,4,5,6),(5,7,4,10))==(4,5)` (tid 2) |
| `arg:seq-of-seq` | 94 | a nested list argument: a list of lists, or now, a list of multi-character strings | `min_cost([[1,2,3],[4,8,2],[1,5,3]],2,2)==8` (tid 1) |
| `expected:float` | 42 | a float result | `tetrahedral_number(5)==35.0` (tid 80) |
| `expected:tuple` | 37 | a tuple result | `max_occurrences([...])==(2,5)` (tid 130) |
| `expected:seq-of-seq` | 25 | a nested list result, often the words of a split string | `find_char_long('Please move back to stream')==['Please','move','back','stream']` (tid 7): the string argument now parses, the list-of-words result does not, both a nested seq and SPEC.md's separately named `string-lib` gap (`split`) |
| `arg:dict` | 22 | a dict argument | `merge_dictionaries_three({...},{...},{...})==...` (tid 87) |
| `expected:NoneType` | 8 | the result is Python's `None` | `first_non_repeating_character("abcabc")==None` (tid 395): the string argument parses fine now, t has no value for "no answer" |
| `arg:float` | 7 | a float argument | `encode_list([1,1,2,3,4,4.3,5,1])==[...]` (tid 157) |
| `expected:dict` | 3 | a dict result | `freq_count([...])==({10: 4, ...})` (tid 88) |
| `arg:set` | 3 | a set argument (bare, or nested in a list) | `empty_dit([{1,2},{},{}])==False` (tid 115) |
| `arg:Name` | 2 | a bare identifier as an argument, not a literal at all | `is_tree_balanced(root)==False` (tid 367): `root` is built earlier in the test file; `parse_assertion` sees one line and cannot resolve it |
| `arg:call` | 2 | a function call embedded as an argument, library-shaped | `max_chain_length([Pair(5,24),...],4)==3` (tid 601) |
| `arg:seq-of-bool` | 1 | a list of booleans (t's seq holds int, not bool) | `count([True,False,True])==2` (tid 105) |
| `arg:complex` | 1 | a Python complex literal | `angle_complex(0,1j)==1.5707963267948966` (tid 124) |
| `arg:BinOp` | 1 | an arithmetic expression written as an argument instead of a literal | `binomial_probability(10,5,1.0/3)==0.13656454808718185` (tid 486) |

(9 problems carry two reasons at once, mostly `arg:float` or
`expected:NoneType` paired with a second unrelated reason; none of the 368
is blocked by anything to do with strings any more.)

## Of the 238 added: test coverage and string positions

All 238 have exactly 3 test assertions, and, by construction of pool
inclusion, all 3 parse for all 238 (**238 of 238**, 100%; the experiment
needs every test, and every added problem has it).

String argument positions (0-indexed; a problem can use more than one):

| position | problems |
|---:|---:|
| 0 | 148 |
| 1 | 24 |
| 2 | 4 |

Distinct string-argument positions per problem: 0 (no string argument,
string only in the result, or no string at all) in 90, 1 position in 124,
2 positions in 20, 3 positions in 4 (90+124+20+4 = 238).

Result: **102 of 238** have a string-typed (`seq`) expected result; 136
return int or bool. Cross-tabulated against having a string argument:

| | string result | int/bool result |
|---|---:|---:|
| no string argument | 16 | 74 |
| has a string argument | 86 | 62 |

(74 is the "no string anywhere" group from above; 62 is, for example, a
character predicate: a string or character argument with a bool result.)

Among the string positions, read from each problem's first test point:
15 argument occurrences and 9 result occurrences resolve to a bare
character (`int`, a length-1 literal); 161 argument occurrences and 93
results resolve to a multi-character string (`seq`). Most of what v2 adds
is genuine multi-character text, not single characters.

## The two few-shot examples added to the v2 prompt

Both are hand-written surface text kept verbatim in
`spec_experiment.FEWSHOT_V2_EXTRA` (not round-tripped through a committed
`tasks/*.json` and `surface.print_task`, because the printer never emits
`'a'`/`"abc"`; it only ever prints the plain int/seq literals they expand
to, which would teach the model nothing about the sugar). Each was checked
with `surface.parse` then `fuzz_lower.check_wf` (zero errors, both), and
each round-trips (`surface.parse(surface.print_task(t)) == t`). Their own
tests were run through `interp` via `spec_experiment.run_point` on
hand-built points; all pass.

```t
t 1
gate quantifiers
task greet(name: seq) returns (r: seq)
  ensures len(r) == len(name) + 7
  ensures r[0..7] == "Hello, "
  ensures r[7..len(r)] == name
{
  r := "Hello, " + name;
}
```

Verified: `greet([87,111,114,108,100])` ("World") returns `[72,101,108,
108,111,44,32,87,111,114,108,100]` ("Hello, World"), pass; `greet([])`
("") returns `[72,101,108,108,111,44,32]` ("Hello, "), pass. Uses the
string literal, concatenation, and two slices.

```t
t 1
gate loops
task extract_digits(s: seq) returns (r: seq)
  ensures len(r) <= len(s)
  ensures forall k in [0, len(r)) . r[k] >= '0' and r[k] <= '9'
{
  r := [];
  var i: int := 0;
  while i < len(s)
    invariant 0 <= i
    invariant i <= len(s)
    invariant len(r) <= i
    invariant forall k in [0, len(r)) . r[k] >= '0' and r[k] <= '9'
    decreases len(s) - i
  {
    if s[i] >= '0' and s[i] <= '9' {
      r := r + [s[i]];
    } else {
    }
    i := i + 1;
  }
}
```

Verified on four points: `"ab12cd3"` -> `"123"`, `""` -> `""`,
`"nodigitshere"` -> `""`, `"007"` -> `"007"`; all pass. Uses the char
literal (in two ranges), the empty seq literal, the one-element seq
literal, and concatenation, inside the loop-and-append idiom
`tasks/filter_pos.json` already established for plain integers.

## A bug found and fixed along the way

`spec_experiment.run_point` compared the interpreter's returned value
against the test's expected value with plain `==`. `interp` represents a
`seq` value as a Python tuple (and `run_point` itself already converts a
`seq` argument to a tuple before handing it to the interpreter, on the way
in); `mbpp_dfy.parse_assertion`'s expected value is a plain list. A tuple
never equals a list in Python even with identical elements, so every
`seq`-expected test point would have misreported "fail" on a genuinely
correct answer. This was unreachable under the v1 pool, which never admits
a `seq` expected value, so it never fired before; it is live the moment
`--pool v2` is used with the `tests` stage, which is exactly what pool v2
is for. Fixed by normalizing the expected value to a tuple before the
comparison when its kind is `seq`; confirmed with the `greet` and
`extract_digits` points above (they failed before the fix, pass after),
and confirmed inert for v1 (`abs`, `int`/`bool` points, before and after,
identical).

## Regression: v1 unchanged

- `pool_report()` (no arguments) and `pool_report("v1")` return the
  identical object, byte-for-byte, to what `pool_report()` returned before
  this change: `{"problems": 974, "in_pool": 368, "refused": {...18
  reasons...}}`, checked by diffing the two outputs directly.
- `pool()` (no arguments) returns the same 368 ids as before the change.
- `fewshot_text()` and `fewshot_text("v1")` return the identical string
  (1840 characters); `build_prompt(entry)` and `build_prompt(entry, "v1")`
  return identical message lists, checked by equality, not inspection.
- `loop_dataset.py` and `loop_generate.py` needed no change: both call
  `spec_experiment.pool()` and `spec_experiment.build_prompt(entry)` with
  no arguments, so the new defaults keep them on v1. Confirmed by
  importing both modules and calling their pool()/build_prompt() paths
  directly: `loop_dataset.spec_experiment.pool()` and
  `loop_generate.se.pool()` both return 368, and
  `loop_dataset.spec_experiment.build_prompt(entry) ==
  spec_experiment.build_prompt(entry)`.
- `test_mbpp_dfy.py` (new, 17 checks) exercises `strings=False` against
  every literal kind `_literal` already handled (int, bool, negative int,
  seq of int, tuple, dict, set, call, bare name) and asserts each is
  byte-for-byte the old result; `strings=True` against a single character,
  a multi-character string, the empty string, two escape cases, a
  precomposed non-ASCII character (code point 233, not its two UTF-8
  bytes), an astral code point (U+1F600, one Python character, one t int,
  not a UTF-16 surrogate pair), a list of single-character strings (a
  plain seq of int, since each element is itself a t character), a list of
  multi-character strings and a mixed-length list (both refused as
  `arg:seq-of-seq`, t's existing nested-seq name), a tuple of strings
  (still refused as `arg:tuple`, unaffected by `strings`), and a batch of
  kinds strings never touches (float, dict, set, call), plus a direct
  regression guard that `pool_report("v1")["in_pool"] == 368`. All 17
  pass (`python3 test_mbpp_dfy.py`).

## Named residual: the negated-string edge case

`_literal`'s negation branch (`-x`) does not special-case a character: a
length-1 string under `strings=True` parses as `("int", codepoint)`, so
`-"a"` parses to `("int", -97)`, matching SPEC.md's own stance that t does
not distinguish a character from an int once it exists ("Dafny refuses
'a' + 1; t computes 98"). Checked directly against the full MBPP corpus:
**zero** assertions contain a negated string literal, so this is a
theoretical corner, not a measured one, and it changes nothing about the
238 added or the 368 still refused.

## What remains for the run (not done here, on purpose)

- **No model was run.** `--pool v2` and `--prompt v2` are built and
  measured in isolation (pool composition, prompt text, the two new
  few-shot tasks); `generate`/`extract`/`tests`/`table` were not run
  end-to-end against a live model under either flag.
- **The control column must be re-measured under the v2 prompt before any
  round is compared under it.** LOOP-CURVE.md's comparisons hold the
  prompt fixed across rounds; switching to `--prompt v2` changes the
  system message every round sees (a longer grammar, two more few-shot
  tasks), so a round graded under v2 is not comparable to round 0's
  numbers, which were measured under v1's prompt. A fresh round 0
  (`generate --prompt v2 --pool v2`, or against whichever pool the
  comparison needs) has to be run and graded before v2-prompt rounds mean
  anything relative to it. This file states that; it does not run it.
- `loop_dataset.py` and `loop_generate.py` were not touched and gained no
  v2 option; they keep reading `pool()`/`build_prompt()` at their v1
  defaults (confirmed above), which is what "unaffected" was asked for,
  not "extended."
- The 74-of-238 "no string, admitted by the return-type widening alone"
  group is named above so it is measured rather than folded silently into
  a "+238 strings" headline.
