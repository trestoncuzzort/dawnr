# t coverage census: nl/ stdin-to-signature instrument

COVERAGE-nl.md found 20509 of nl/'s 24748 problems are
stdin-shaped (APPS and CodeContests) and that 361 of them would be
in t's fragment once a signature is extracted: their sample inputs
and outputs are all-integer and their reference solution tags no
gap. This file builds that missing instrument: a SIGNATURE (an
ordered list of typed parameters) and a parser from sample input
text to argument values and sample output text to an expected
result, inferred by a small grammar over the samples alone, and
validated against every sample the problem carries. Method at the
end names exactly what was parsed and every decision made about
edge cases.

## Headline

### nl/ stdin-shaped problems, all sources

- stdin-shaped problems: 20509
- accepted (a signature was extracted and every sample fit it): 3058 (14.9%)
- **in the pool** (accepted AND the reference solution tags no gap): **271** (1.3%)

accepted signatures by grammar rule:

| rule | problems |
|---|---|
| b | 948 |
| a(k=1) | 615 |
| a(k=2) | 543 |
| d | 378 |
| a(k=3) | 264 |
| a(k=4) | 122 |
| c | 72 |
| a(k=5) | 36 |
| e:b | 31 |
| e:d | 16 |
| a(k=6) | 16 |
| a(k=8) | 4 |
| a(k=7) | 4 |
| a(k=14) | 3 |
| a(k=9) | 3 |
| e:c | 1 |
| a(k=18) | 1 |
| a(k=70) | 1 |

refusals by reason:

| reason | problems |
|---|---|
| multi-case | 6291 |
| unknown-format | 4914 |
| non-integer-token | 2226 |
| multi-value-output | 1811 |
| ragged | 1545 |
| non-integer-output | 664 |

## By source

### APPS

- stdin-shaped problems: 6899
- accepted (a signature was extracted and every sample fit it): 1268 (18.4%)
- **in the pool** (accepted AND the reference solution tags no gap): **121** (1.8%)

accepted signatures by grammar rule:

| rule | problems |
|---|---|
| b | 376 |
| a(k=1) | 248 |
| a(k=2) | 213 |
| d | 191 |
| a(k=3) | 98 |
| a(k=4) | 45 |
| c | 26 |
| e:b | 26 |
| a(k=5) | 17 |
| e:d | 16 |
| a(k=6) | 3 |
| a(k=14) | 2 |
| a(k=8) | 2 |
| a(k=9) | 2 |
| e:c | 1 |
| a(k=18) | 1 |
| a(k=7) | 1 |

refusals by reason:

| reason | problems |
|---|---|
| multi-case | 1801 |
| unknown-format | 1541 |
| non-integer-token | 825 |
| multi-value-output | 737 |
| ragged | 447 |
| non-integer-output | 280 |

### CodeContests

- stdin-shaped problems: 13610
- accepted (a signature was extracted and every sample fit it): 1790 (13.2%)
- **in the pool** (accepted AND the reference solution tags no gap): **150** (1.1%)

accepted signatures by grammar rule:

| rule | problems |
|---|---|
| b | 572 |
| a(k=1) | 367 |
| a(k=2) | 330 |
| d | 187 |
| a(k=3) | 166 |
| a(k=4) | 77 |
| c | 46 |
| a(k=5) | 19 |
| a(k=6) | 13 |
| e:b | 5 |
| a(k=7) | 3 |
| a(k=8) | 2 |
| a(k=9) | 1 |
| a(k=14) | 1 |
| a(k=70) | 1 |

refusals by reason:

| reason | problems |
|---|---|
| multi-case | 4490 |
| unknown-format | 3373 |
| non-integer-token | 1401 |
| ragged | 1098 |
| multi-value-output | 1074 |
| non-integer-output | 384 |

## Ten most common accepted signatures

| signature | problems |
|---|---|
| `b: n:int, a:seq` | 948 |
| `a(k=1): x1:int` | 615 |
| `a(k=2): x1:int, x2:int` | 543 |
| `d: n:int, m:int, a:seq` | 378 |
| `a(k=3): x1:int, x2:int, x3:int` | 264 |
| `a(k=4): x1:int, x2:int, x3:int, x4:int` | 122 |
| `c: n:int, a:seq` | 72 |
| `a(k=5): x1:int, x2:int, x3:int, x4:int, x5:int` | 36 |
| `e:b: n:int, a:seq` | 31 |
| `e:d: n:int, m:int, a:seq` | 16 |

## Five worked examples

Chosen from the pool (accepted, gap-free), shortest sample input
first, so the input/signature/points line up legibly on the page.

### 1. APPS `apps_raw_train:1235`

grammar rule: `a(k=1)`  
signature: `(x1: int)`

sample input:
```
2
```
sample output: `25`

points:

- `(2) == 25`

### 2. APPS `apps_raw_train:1290`

grammar rule: `a(k=1)`  
signature: `(x1: int)`

sample input:
```
9
```
sample output: `1`

points:

- `(9) == 1`

### 3. APPS `apps_raw_train:2570`

grammar rule: `a(k=1)`  
signature: `(x1: int)`

sample input:
```
3
```
sample output: `123`

points:

- `(3) == 123`

### 4. APPS `apps_raw_train:532`

grammar rule: `a(k=1)`  
signature: `(x1: int)`

sample input:
```
4
```
sample output: `5`

points:

- `(4) == 5`

### 5. APPS `apps_raw_train:656`

grammar rule: `a(k=1)`  
signature: `(x1: int)`

sample input:
```
5
```
sample output: `4`

points:

- `(5) == 4`

## Method

Run time: 182.0s. Streams every APPS and CodeContests
.jsonl.gz split with nl_census._stream (gzip text mode, one JSON
object per line; nothing is decompressed to disk). A problem is
stdin-shaped under the same split nl_census.py uses: an APPS record
whose `input_output` carries no `fn_name`, or any CodeContests
record. For APPS, every `input_output.inputs`/`outputs` pair is a
sample (not the first 3, unlike nl_census's lexical io-type scan);
an entry that is itself a list of per-line strings, rather than one
string with embedded newlines (measured on apps_raw_train id 514),
is joined with a NEWLINE per element so line structure survives.
For CodeContests, every `public_tests` + `private_tests` +
`generated_tests` pair is a sample (`generated_tests` alone runs to
hundreds per problem on this corpus).

A signature is inferred by classifying each sample's input text
independently against the grammar in this file's docstring
(rules a-e, tried in that priority; anything left over is rule f,
a named refusal) and requiring every sample of the problem to
classify under the identical rule (and the identical k, for rule
a). One sample that does not is a whole-problem refusal, never a
partial signature: the pool over-approximates nothing, a problem
is in it only if every sample it carries parsed. When samples
disagree with each other, or a single sample fails in more than
one way across the corpus, the reported reason follows a fixed
priority -- multi-case, then non-integer-token, then ragged, then
unknown-format on the input side; multi-value-output then
non-integer-output on the output side -- rather than an arbitrary
first-seen reason.

Decisions on edge cases not fully pinned down by the grammar's
prose:

- Windows line endings (`\r\n`, bare `\r`) are normalized to `\n`
  before any line is split, on both the input and output side.
- Every TRAILING blank line is dropped before matching, including
  the empty element a final `\n` produces ("3\n" is one line,
  not two). An INTERIOR blank line is kept as a zero-token line,
  which fails every rule's per-line token-count check and reliably
  refuses the sample (`ragged` or `unknown-format`) rather than
  being skipped or silently reinterpreted.
- The output side is tokenized over the WHOLE normalized text with
  a plain `str.split()`, ignoring which line a token falls on, so
  the ONLY question is how many whitespace-separated tokens exist
  in total: more than one is `multi-value-output` regardless of
  formatting, exactly one is checked with `int()`.
- Rule e's test-count wrapper is only unwrapped when its count is
  1 in EVERY sample of the problem (the constant "1" line is then
  dropped and contributes no parameter); a count that is ever >1,
  or ever fails to parse as an int, refuses the whole problem
  (`multi-case` or `non-integer-token`) rather than being read as
  a genuine, unsupported batch -- t has no notion of batching a
  task over several independent input blocks.
- A problem with zero samples (an empty or unparseable
  `input_output`, or no test dicts under any of CodeContests's
  three categories) is refused `unknown-format` rather than given
  a reason of its own: there is nothing to classify.
- Rule b and rule c overlap exactly when n=1 (a two-line input,
  header "1", one data line): rule b's precondition (exactly two
  lines, one-token header) is checked first per the stated
  priority and always claims this case, so rule c's own two-line
  case never fires; it only matches n_lines == n+1 for n >= 2.
- The first Python solution (APPS: the first entry of the decoded
  `solutions` list, no language field to filter on; CodeContests:
  the first entry whose `language` is `PYTHON3` or `PYTHON`) is
  decoded and AST-tagged with `nl_census.solution_tags` ONLY for a
  problem that already passed both the input-signature and the
  output checks -- the ~95% of stdin-shaped problems that refuse
  before that point never pay for JSON-decoding or parsing a
  solution. `in_pool` requires a solution that exists, parses
  under Python 3's `ast` (not `py2-unparseable`), and tags none of
  `nl_census.GAPS` -- the identical detectors, and the identical
  `py2-unparseable` exception, COVERAGE-nl.md's solution-construct
  census uses, imported from nl_census.py rather than
  reimplemented.

The JSON beside this report carries one record per stdin-shaped
problem: source, id, split, n_samples, verdict, in_pool, and for
an accepted problem also grammar_rule, signature, has_solution,
solution_gaps and the full points list (every sample, not a
selection) -- one `{"args": [[type, value], ...], "expected":
["int", value]}` per sample, in signature order, the same
(kind, value) shape mbpp_dfy.parse_assertion and spec_experiment's
pool() use for MBPP's points.
