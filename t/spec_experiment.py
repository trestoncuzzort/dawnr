#!/usr/bin/env python3
"""spec_experiment.py -- ROADMAP 12.6, the spec experiment.

The training thesis in one sentence: a model can write a t task, specification
included, from a natural-language problem, and seven kernels grading it give
a signal worth training on. This measures that once, on MBPP, with a local
model. Two failures are different and both matter, so they are reported
apart and never added: a task can VERIFY with a REFUTED twin and still not
be the program the problem asked for (a spec the kernels accept about the
wrong function), and a task can pass the problem's own tests and not verify
(a program the kernels cannot prove, or a spec they cannot prove of it).

Stages, each idempotent, records under out/spec-experiment/<model-tag>/:

  pool      the MBPP problems whose every test assertion is in t's fragment
            (int, bool, seq of int arguments; mbpp_dfy.parse_assertion) and
            whose expected result is int or bool, t's only return types.
            368 of 974 on 2026-09-08; 67 of them are MBPP-DFY problems.
  generate  one reply per problem from a local model through ollama's chat
            API, temperature 0 and a fixed seed, so the table is
            reproducible from the recorded prompt. raw/<task_id>.json keeps
            the prompt, the reply, token counts, timings and the model
            digest. A problem with a record on disk is not re-asked.
  extract   the reply's fenced t block -> surface.parse -> a task named
            mbpp_<task_id>__<fn> -> fuzz_lower.check_wf -> tasks/<name>.json.
            Every refusal is named (no-block, parse:<message>, wf:<messages>)
            and counted; nothing is dropped silently.
  tests     interp runs each task on the problem's own assertion points,
            mapped positionally onto the task's parameters. Per point: pass,
            fail (with the values), requires-excluded (the model's
            precondition rejects a test input), undefined, budget, or a
            signature mismatch. A problem passes when every point passes.
  table     joins the above with the kernel table run_par.py wrote over
            tasks/ (--tasks --out --table) into one markdown report: counts
            per stage, per-kernel verified/refuted counts, the seven-column
            count, and the cross-tabulation of "verifies with a refuted
            twin" against "passes its tests", which is 12.6's DONE WHEN.

Usage, in order:

    python3 spec_experiment.py generate --model qwen2.5-coder:7b [--limit N]
    python3 spec_experiment.py extract  --model qwen2.5-coder:7b
    python3 spec_experiment.py tests    --model qwen2.5-coder:7b
    python3 run_par.py --tasks out/spec-experiment/qwen2.5-coder-7b/tasks \\
        --out out/spec-experiment/qwen2.5-coder-7b/kernels \\
        --table out/spec-experiment/qwen2.5-coder-7b/kernels.md
    python3 spec_experiment.py table    --model qwen2.5-coder:7b \\
        --out SPEC-EXPERIMENT-mbpp.md

The server is the caller's: `ollama serve` bound to one GPU, started for
the run and killed at its end (the standing rule on this box). This file
never starts one; generate refuses with the connection error when none
answers. Standard library only, plus t's own modules.

2026-09-11: `--pool v3` (SPEC-EXPERIMENT-pool-v2.md's sequel, unwritten as
a separate file; see this docstring and pool_report's own reasons for the
measurement). v3 = v2's pool, unioned with every problem v2 still refuses
whose test assertions parse once `mbpp_dfy.parse_assertion`'s new
`nested_strings` flag is on too (a `seq-of-seq` argument or expected value
built only from Python string literals, SPEC.md's "Nested sequences"
applied to a list of words) AND whose reference solution's own
string-library use, if any, is entirely SPEC.md's "The string library
(v1)" sixteen members in v1 forms (`mbpp_dfy.string_lib_v1_only`, a thin
wrap of `nl_census.solution_tags`). `--prompt v3` adds the string
library's notation (GRAMMAR_V3) and two more few-shot tasks,
`word_count` and `split_join` from `tasks/`, printed by `surface.py`
(unlike v2's two hand-written extras, these use no char/string sugar
`surface.print_task` cannot round-trip, so the committed tasks themselves
serve directly). v1 and v2's `pool()`/`pool_report()`/`fewshot_text()`/
`build_prompt()` outputs are unchanged (v3 is additive, reached only
through the new branch of `_pool_settings`/`pool`/`pool_report`, and the
new `PROMPT_VERSIONS` member).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import concurrent.futures
import threading
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import fuzz_lower      # noqa: E402  (check_wf)
import harness         # noqa: E402
import interp          # noqa: E402
import mbpp_dfy        # noqa: E402
import surface         # noqa: E402
import tasks_io        # noqa: E402

OUT_ROOT = HERE / "out" / "spec-experiment"
FEWSHOT = ["abs", "max", "sum_upto", "linear_search", "gcd"]
BACKENDS = ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"]


def model_tag(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", model)


def outdir(model: str) -> Path:
    d = OUT_ROOT / model_tag(model)
    for sub in ("raw", "tasks"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    return d


# ------------------------------------------------------------------ pool --

POOL_VERSIONS = ("v1", "v2", "v3")


def _pool_settings(version: str) -> tuple[bool, tuple[str, ...]]:
    """(strings, allowed-expected-kinds) for a pool version.

    v1 (default): `mbpp_dfy.parse_assertion`'s own default, `strings=False`;
    a test carrying a Python string anywhere is refused (`arg:str` /
    `expected:str`), and the only return types are int and bool, t's only
    return types when this pool was measured (2026-09-08). Byte-for-byte
    what `pool()` always did.

    v2: `strings=True` (SPEC.md "Strings as sequences of code points"), so a
    Python string literal parses into a t character or a t `seq` of code
    points instead of being refused; the expected value may now also be a
    `seq` (a string result), since `seq` has been a legal t return type
    since 2026-09-09 ("Sequences as values").

    v3: v2's settings, plus `seq-of-seq` as an allowed kind (a list of
    strings, `mbpp_dfy.parse_assertion`'s `nested_strings=True` reading,
    SPEC.md "Nested sequences" applied to strings). `pool()`'s v3 branch
    also runs `mbpp_dfy.string_lib_v1_only` against the reference
    solution, which this tuple alone cannot express, so `pool()`/
    `pool_report()` read `version == "v3"` directly for that half rather
    than folding it in here."""
    if version == "v3":
        return True, ("int", "bool", "seq", "seq-of-seq")
    if version == "v2":
        return True, ("int", "bool", "seq")
    if version == "v1":
        return False, ("int", "bool")
    raise ValueError("pool version must be v1, v2 or v3, got %r" % version)


def pool(version: str = "v1") -> dict[int, dict]:
    """task_id -> {"rec": mbpp record, "points": parsed assertions, "fn": name}.

    v1 (default, unchanged since 2026-09-08): every assertion parses into
    t's int/bool/seq<int> argument fragment and every expected value is an
    int or a bool. v2: strings are admitted (arguments and results), typed
    as seq (mbpp_dfy.parse_assertion(strings=True)), and a seq expected
    value is admitted too. v3 (2026-09-11): v2's reading, plus a list of
    strings (`nested_strings=True`, kind `seq-of-seq`) as an argument or
    expected value, admitted only when the reference solution's own
    string-library use, if any, is entirely SPEC.md's v1 members in v1
    forms (`mbpp_dfy.string_lib_v1_only`); a problem already admitted
    under v2's own reading needs no solution check; only NEW v3 admissions
    (`seq-of-seq` used) go through it. Either way a problem with even one
    refused assertion is out, and the refusal reasons are counted in
    `pool_report`."""
    strings, allowed = _pool_settings(version)
    nested = version == "v3"
    recs = mbpp_dfy.mbpp_records()
    out = {}
    for tid, r in sorted(recs.items()):
        pts = [mbpp_dfy.parse_assertion(a, strings=strings, nested_strings=nested)
               for a in r["test_list"]]
        if not pts or not all(p["ok"] for p in pts):
            continue
        if not all(p["expected"][0] in allowed for p in pts):
            continue
        fns = {p["fn"] for p in pts}
        if len(fns) != 1:
            continue
        fn = fns.pop()
        if nested and any(p["expected"][0] == "seq-of-seq" or
                           any(a[0] == "seq-of-seq" for a in p["args"]) for p in pts):
            if not mbpp_dfy.string_lib_v1_only(r.get("code", ""), fn):
                continue
        out[tid] = {"rec": r, "points": pts, "fn": fn}
    return out


def pool_report(version: str = "v1") -> dict:
    strings, allowed = _pool_settings(version)
    nested = version == "v3"
    recs = mbpp_dfy.mbpp_records()
    why: dict[str, int] = {}
    n_ok = 0
    for tid, r in recs.items():
        pts = [mbpp_dfy.parse_assertion(a, strings=strings, nested_strings=nested)
               for a in r["test_list"]]
        bad = [p["why"] for p in pts if not p["ok"]]
        ok = not bad and pts and all(p["expected"][0] in allowed for p in pts)
        if ok and nested:
            fns = {p["fn"] for p in pts}
            fn = fns.pop() if len(fns) == 1 else None
            needs_check = any(p["expected"][0] == "seq-of-seq" or
                               any(a[0] == "seq-of-seq" for a in p["args"]) for p in pts)
            if needs_check and (fn is None or not mbpp_dfy.string_lib_v1_only(r.get("code", ""), fn)):
                ok = False
                bad = ["solution:string-lib"]
        if ok:
            n_ok += 1
            continue
        for w in bad or ["expected:%s" % ",".join(sorted({p["expected"][0] for p in pts if p["ok"]}))]:
            key = w.split(":")[0] + ":" + w.split(":")[1].split("(")[0] if ":" in w else w
            why[key] = why.get(key, 0) + 1
    return {"problems": len(recs), "in_pool": n_ok, "refused": why}


# ---------------------------------------------------------------- prompt --

GRAMMAR = """\
t is a tiny verified language. A t task is written like this:

    t 0                            (t 1 when the task uses locals, loops,
                                    seq, quantifiers, spec funs or recursion)
    gate loops                     (t 1 only: loops | recursion | quantifiers)
    task NAME(p1: int, p2: seq) returns (r: int)
      requires EXPR                (zero or more; conjoined)
      ensures EXPR                 (one or more; conjoined; the contract)
      decreases EXPR               (only when the task calls itself)
    spec fun F(a: int): int         (optional helper for the spec, t 1 only)
      decreases a
    = EXPR
    {
      STATEMENTS
    }

Types: int (unbounded mathematical integer), bool, seq (a read-only sequence
of ints, parameters only). Exactly one return, int or bool. Every path
through the body must assign the return variable.

Statements:  r := EXPR;    var i: int := EXPR;    if EXPR { ... } else { ... }
             while EXPR invariant EXPR ... decreases EXPR { ... }
Every while needs invariants strong enough to prove the ensures at exit and
one decreases expression that is >= 0 and strictly decreases. `else { }` may
be empty but must be present.

Expressions: integer literals, true, false, names, ( ), + - * (no division,
no modulo, no shifts), unary -, == != < <= > >=, not, and, or, ==> (implies),
if C then A else B, len(s), s[i], forall i in [lo, hi) . BODY,
exists i in [lo, hi) . BODY, F(args) for a spec fun.

RULES THE PARSER ENFORCES. These operators and names DO NOT EXIST in t and
make the task unparseable: / % ** ^ & | << >> bin abs min max pow sum
range. There are no strings, floats, tuples, arrays, dictionaries, sets or
comments. Quantifier ranges are half-open: `forall i in [lo, hi) . P` means
lo <= i < hi. Every `if` has both branches: `if C { ... } else { ... }`,
with `else { }` when there is nothing to do. A task that calls itself
needs `gate recursion` and a `decreases EXPR` line after its ensures, and
its ensures may not mention the task's own name (use a spec fun). A
condition is a bool expression: write `r := (a == b);`, never `r := a == b
? ...`. Loop variables are declared with `var i: int := 0;`.

Division and modulo are not in the language. If the problem needs them,
compute the quantity with a loop of repeated subtraction, or define it with
a recursive spec fun; never write / or %.

The ensures must say what the result IS, not merely that it exists; a spec
the tests would disagree with is wrong, and `ensures true` is worthless.
requires must admit every input the tests use. Encode a list as a seq of
ints and a yes/no answer as bool.

Reply with exactly one t task inside a ```t fenced block and nothing else.
"""

PROMPT_VERSIONS = ("v1", "v2", "v3")

# GRAMMAR_V2 is GRAMMAR plus the sequence trio (literal, concatenation,
# slice) and the string sugar (SPEC.md "Sequences: literals, concatenation,
# slices" and "Strings as sequences of code points"), both stated 2026-09-09,
# after this file's v1 GRAMMAR was written. It is a separate constant, not a
# patch to GRAMMAR, so that --prompt v1 (the default) stays byte-for-byte
# what it always was.
GRAMMAR_V2 = """\
t is a tiny verified language. A t task is written like this:

    t 0                            (t 1 when the task uses locals, loops,
                                    seq, quantifiers, spec funs or recursion)
    gate loops                     (t 1 only: loops | recursion | quantifiers)
    task NAME(p1: int, p2: seq) returns (r: int)
      requires EXPR                (zero or more; conjoined)
      ensures EXPR                 (one or more; conjoined; the contract)
      decreases EXPR               (only when the task calls itself)
    spec fun F(a: int): int         (optional helper for the spec, t 1 only)
      decreases a
    = EXPR
    {
      STATEMENTS
    }

Types: int (unbounded mathematical integer), bool, seq (a sequence of ints;
usable as a parameter, a return, or a local, t 1 only). Exactly one return,
int, bool, or seq. Every path through the body must assign the return
variable.

Statements:  r := EXPR;    var i: int := EXPR;    var a: seq := EXPR;
             if EXPR { ... } else { ... }
             while EXPR invariant EXPR ... decreases EXPR { ... }
Every while needs invariants strong enough to prove the ensures at exit and
one decreases expression that is >= 0 and strictly decreases. `else { }` may
be empty but must be present.

Expressions: integer literals, true, false, names, ( ), + - * (no division,
no modulo, no shifts), unary -, == != < <= > >=, not, and, or, ==> (implies),
if C then A else B, len(s), s[i], forall i in [lo, hi) . BODY,
exists i in [lo, hi) . BODY, F(args) for a spec fun.

SEQUENCES: [e1, ..., en] is a sequence literal, any number of int elements,
[] the empty sequence. s + t concatenates two sequences (the same + used on
numbers; t picks the meaning from the types on either side, an int-and-seq
+ is ill-typed). s[a..b] is the slice from position a up to but not
including b, defined only when 0 <= a <= b <= len(s); s[a..] means
s[a..len(s)] and s[..b] means s[0..b]. s[i := v] is s with position i
replaced by v (same range rule); seq(n, v) is n copies of v. Two sequences
are == when they have the same length and the same element at every
position.

STRINGS: t has no string type and no string operator. A character is its
Unicode code point, a plain int; a string is a seq of those ints. 'a' is a
character literal, its code point (so 'a' is 97), and "abc" is a string
literal, the sequence [97, 98, 99]; "" is the empty string, the same value
as []. Escapes \\n \\t \\r \\0 \\' \\\\, and inside "..." also \\", spell the
usual control characters and the quote marks. Everything above (len, s[i],
+, a slice, ==) already works on a string because a string is a seq; there
is no split, upper, strip, or join in the language.

RULES THE PARSER ENFORCES. These operators and names DO NOT EXIST in t and
make the task unparseable: / % ** ^ & | << >> bin abs min max pow sum
range. There are no floats, tuples, arrays, dictionaries, sets, comments, or
string library (split, upper, strip, join): write what a string's method
would have done with the sequence operations above, a loop, or a spec fun.
Quantifier ranges are half-open: `forall i in [lo, hi) . P` means
lo <= i < hi. Every `if` has both branches: `if C { ... } else { ... }`,
with `else { }` when there is nothing to do. A task that calls itself
needs `gate recursion` and a `decreases EXPR` line after its ensures, and
its ensures may not mention the task's own name (use a spec fun). A
condition is a bool expression: write `r := (a == b);`, never `r := a == b
? ...`. Loop variables are declared with `var i: int := 0;` and sequence
locals with `var a: seq := EXPR;`.

Division and modulo are not in the language. If the problem needs them,
compute the quantity with a loop of repeated subtraction, or define it with
a recursive spec fun; never write / or %.

The ensures must say what the result IS, not merely that it exists; a spec
the tests would disagree with is wrong, and `ensures true` is worthless.
requires must admit every input the tests use. Encode a list or a string as
a seq of ints (the notation's "..." and 'x' are sugar for exactly that) and
a yes/no answer as bool.

Reply with exactly one t task inside a ```t fenced block and nothing else.
"""

# Two extra few-shot examples for --prompt v2, using the construct v1's
# five (FEWSHOT, above) never touch: a sequence literal, concatenation, a
# slice, and the char/string sugar. Kept as hand-written SURFACE TEXT, not
# round-tripped through a committed tasks/*.json and surface.print_task
# (fewshot_text's v1 path, below): the printer never emits 'a'/"abc" (SPEC.md
# "Strings as sequences of code points"; surface.py prints only the plain
# int/seq literals they expand to), so a canonical print of these two tasks
# would show the model [72, 101, ...] instead of "Hello, " and teach nothing
# about the sugar the pool's v2 strings need. Each is verified well-formed
# (surface.parse then fuzz_lower.check_wf) and its own tests run through
# interp in test_mbpp_dfy.py; neither is committed under tasks/.
FEWSHOT_V2_EXTRA = [
    ("greet", """\
t 1
gate quantifiers
task greet(name: seq) returns (r: seq)
  ensures len(r) == len(name) + 7
  ensures r[0..7] == "Hello, "
  ensures r[7..len(r)] == name
{
  r := "Hello, " + name;
}
"""),
    ("extract_digits", """\
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
"""),
]

# GRAMMAR_V3 is GRAMMAR_V2 plus SPEC.md "The string library (v1)" (stated
# 2026-09-11): the sixteen v1 members, written Python's own method
# syntax, and the RULES paragraph's blanket "no string library" line
# replaced by the precise not-in-v1 list (so the model is told what DOES
# exist, not only what does not). A separate constant, not a patch to
# GRAMMAR_V2, so --prompt v1 and v2 stay byte-for-byte what they always
# were.
GRAMMAR_V3 = """\
t is a tiny verified language. A t task is written like this:

    t 0                            (t 1 when the task uses locals, loops,
                                    seq, quantifiers, spec funs or recursion)
    gate loops                     (t 1 only: loops | recursion | quantifiers)
    task NAME(p1: int, p2: seq) returns (r: int)
      requires EXPR                (zero or more; conjoined)
      ensures EXPR                 (one or more; conjoined; the contract)
      decreases EXPR               (only when the task calls itself)
    spec fun F(a: int): int         (optional helper for the spec, t 1 only)
      decreases a
    = EXPR
    {
      STATEMENTS
    }

Types: int (unbounded mathematical integer), bool, seq (a sequence of ints;
usable as a parameter, a return, or a local, t 1 only). Exactly one return,
int, bool, or seq. Every path through the body must assign the return
variable.

Statements:  r := EXPR;    var i: int := EXPR;    var a: seq := EXPR;
             if EXPR { ... } else { ... }
             while EXPR invariant EXPR ... decreases EXPR { ... }
Every while needs invariants strong enough to prove the ensures at exit and
one decreases expression that is >= 0 and strictly decreases. `else { }` may
be empty but must be present.

Expressions: integer literals, true, false, names, ( ), + - * (no division,
no modulo, no shifts), unary -, == != < <= > >=, not, and, or, ==> (implies),
if C then A else B, len(s), s[i], forall i in [lo, hi) . BODY,
exists i in [lo, hi) . BODY, F(args) for a spec fun.

SEQUENCES: [e1, ..., en] is a sequence literal, any number of int elements,
[] the empty sequence. s + t concatenates two sequences (the same + used on
numbers; t picks the meaning from the types on either side, an int-and-seq
+ is ill-typed). s[a..b] is the slice from position a up to but not
including b, defined only when 0 <= a <= b <= len(s); s[a..] means
s[a..len(s)] and s[..b] means s[0..b]. s[i := v] is s with position i
replaced by v (same range rule); seq(n, v) is n copies of v. Two sequences
are == when they have the same length and the same element at every
position.

STRINGS: t has no string type; a string is a seq of Unicode code points.
'a' is a character literal, its code point (so 'a' is 97), and "abc" is a
string literal, the sequence [97, 98, 99]; "" is the empty string, the same
value as []. Escapes \\n \\t \\r \\0 \\' \\\\, and inside "..." also \\", spell
the usual control characters and the quote marks. len, s[i], +, a slice,
and == already work on a string because a string is a seq.

THE STRING LIBRARY (v1): written Python's own method syntax, every member
total (defined for every input):
    s.split()            seq -> seq<seq>: runs of whitespace separate,
                          leading/trailing whitespace dropped, no row
                          empty; split("") == [].
    s.split(c)            seq, int -> seq<seq>: split on one code point c,
                          every occurrence separates, empty rows kept.
    sep.join(rows)        seq<seq>, seq -> seq: sep between consecutive
                          rows of `rows`.
    tostr(n)              int -> seq: decimal digits, '-' for negative n.
    s.count(t)             seq, seq -> int: non-overlapping occurrences of
                          t in s, left to right.
    s.find(t)              seq, seq -> int: least index where t occurs in
                          s, -1 when it does not.
    s.strip() / s.lstrip() / s.rstrip()   seq -> seq: whitespace trimmed
                          at both ends / the left / the right.
    s.replace(t, u)         seq, seq, seq -> seq: every occurrence of t
                          replaced by u, left to right.
    s.lower() / s.upper()   seq -> seq: ASCII letters cased, every other
                          code point unchanged.
    s.isdigit() / s.isalpha() / s.isupper() / s.islower()   seq -> bool.
    s.startswith(t) / s.endswith(t)   seq, seq -> bool.
A library member in specification position (an ensures, a requires, a spec
fun body) is the same function: `ensures len(s.split(c)) == s.count([c]) +
1` is valid.

RULES THE PARSER ENFORCES. These operators and names DO NOT EXIST in t and
make the task unparseable: / % ** ^ & | << >> bin abs min max pow sum
range. There are no floats, tuples, arrays, dictionaries, sets, or
comments. Outside the sixteen string-library members above, in the forms
shown, nothing else from Python's string library exists in t: no format,
no f-strings, no int(x, base), no strip/lstrip/rstrip with a `chars`
argument, no split on a separator longer than one code point, no
splitlines, no zfill/center/ljust/rjust, no title/capitalize/swapcase, no
partition, no encode -- write what it would have done with the members
above, the sequence operations, a loop, or a spec fun.
Quantifier ranges are half-open: `forall i in [lo, hi) . P` means
lo <= i < hi. Every `if` has both branches: `if C { ... } else { ... }`,
with `else { }` when there is nothing to do. A task that calls itself
needs `gate recursion` and a `decreases EXPR` line after its ensures, and
its ensures may not mention the task's own name (use a spec fun). A
condition is a bool expression: write `r := (a == b);`, never `r := a == b
? ...`. Loop variables are declared with `var i: int := 0;` and sequence
locals with `var a: seq := EXPR;`.

Division and modulo are not in the language. If the problem needs them,
compute the quantity with a loop of repeated subtraction, or define it with
a recursive spec fun; never write / or %.

The ensures must say what the result IS, not merely that it exists; a spec
the tests would disagree with is wrong, and `ensures true` is worthless.
requires must admit every input the tests use. Encode a list or a string as
a seq of ints (the notation's "..." and 'x' are sugar for exactly that) and
a yes/no answer as bool.

Reply with exactly one t task inside a ```t fenced block and nothing else.
"""

# Two more few-shot tasks for --prompt v3, using the string library
# GRAMMAR_V3 adds. Unlike FEWSHOT_V2_EXTRA (hand-written text: v2's two
# examples use the char/string SUGAR surface.print_task never emits),
# these use only the library's Python-method notation, which
# surface.print_task prints exactly as written, so they are read straight
# from the committed, verified tasks (SPEC.md "The string library (v1)":
# measured via harness.twin_cached, both real/twin-witnessed), the same
# way FEWSHOT's five are.
FEWSHOT_V3_EXTRA = ["word_count", "split_join"]


def fewshot_text(version: str = "v1") -> str:
    if version not in PROMPT_VERSIONS:
        raise ValueError("prompt version must be v1, v2 or v3, got %r" % version)
    parts = []
    for name in FEWSHOT:
        task = harness.load(tasks_io.find(HERE / "tasks", name))
        parts.append("```t\n" + surface.print_task(task).rstrip() + "\n```")
    if version in ("v2", "v3"):
        for _, text in FEWSHOT_V2_EXTRA:
            parts.append("```t\n" + text.rstrip() + "\n```")
    if version == "v3":
        for name in FEWSHOT_V3_EXTRA:
            task = harness.load(tasks_io.find(HERE / "tasks", name))
            parts.append("```t\n" + surface.print_task(task).rstrip() + "\n```")
    return "\n\n".join(parts)


def build_prompt(entry: dict, version: str = "v1") -> list[dict]:
    if version not in PROMPT_VERSIONS:
        raise ValueError("prompt version must be v1, v2 or v3, got %r" % version)
    r = entry["rec"]
    tests = "\n".join(r["test_list"])
    arity = len(entry["points"][0]["args"])
    kinds = ", ".join(a[0] for a in entry["points"][0]["args"])
    ret = entry["points"][0]["expected"][0]
    user = (f"Problem: {r['text'].strip()}\n\nTests:\n{tests}\n\n"
            f"Write the t task named `{entry['fn']}` with {arity} parameter(s) "
            f"of type(s) {kinds}, in the order the tests pass them, returning "
            f"{ret}. The tests must pass and the ensures must specify the "
            f"result.")
    grammar = GRAMMAR_V3 if version == "v3" else (GRAMMAR_V2 if version == "v2" else GRAMMAR)
    return [{"role": "system", "content": grammar + "\nExamples of complete t tasks:\n\n" + fewshot_text(version)},
            {"role": "user", "content": user}]


# -------------------------------------------------------------- generate --

def chat(host: str, model: str, messages: list[dict], options: dict, timeout: float) -> dict:
    body = {"model": model, "stream": False, "messages": messages, "options": options}
    req = urllib.request.Request(f"http://{host}/api/chat", data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def model_digest(host: str, model: str) -> str:
    try:
        req = urllib.request.Request(f"http://{host}/api/show", data=json.dumps({"model": model}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            d = json.loads(resp.read().decode("utf-8"))
        det = d.get("details", {})
        return json.dumps({k: det.get(k) for k in ("family", "parameter_size", "quantization_level")},
                          sort_keys=True) + " sha256:" + hashlib.sha256(json.dumps(d.get("modelfile", ""), sort_keys=True).encode()).hexdigest()[:16]
    except (urllib.error.URLError, OSError, ValueError):
        return "unknown"


# 2026-09-15: --jobs N asks N problems at once (a vLLM server batches them;
# ollama would serialize them). Records are per problem, written whole, and
# identical in shape to a sequential run; temperature 0 with a fixed seed.
def cmd_generate(args) -> int:
    d = outdir(args.model)
    P = pool(args.pool)
    ids = sorted(P)
    if args.limit:
        ids = ids[:args.limit]
    options = {"temperature": 0, "seed": args.seed, "num_ctx": args.num_ctx,
               "num_predict": args.num_predict}
    digest = model_digest(args.host, args.model)
    todo = [tid for tid in ids if not (d / "raw" / f"{tid}.json").exists()]
    state = {"asked": 0, "done": len(ids) - len(todo), "failed": []}
    t_start = time.monotonic()
    lock = threading.Lock()

    def one(tid: str) -> None:
        messages = build_prompt(P[tid], args.prompt)
        t0 = time.monotonic()
        try:
            resp = chat(args.host, args.model, messages, options, args.timeout)
        except (urllib.error.URLError, OSError) as e:
            print(f"generate: task {tid}: no answer from {args.host}: {e}", file=sys.stderr)
            with lock:
                state["failed"].append(tid)
            return
        wall = time.monotonic() - t0
        record = {"task_id": tid, "fn": P[tid]["fn"], "model": args.model, "digest": digest,
                  "pool_version": args.pool, "prompt_version": args.prompt,
                  "options": options, "messages": messages,
                  "reply": resp.get("message", {}).get("content", ""),
                  "prompt_tokens": resp.get("prompt_eval_count"),
                  "reply_tokens": resp.get("eval_count"),
                  "eval_s": round((resp.get("eval_duration") or 0) / 1e9, 3),
                  "wall_s": round(wall, 3), "done_reason": resp.get("done_reason")}
        (d / "raw" / f"{tid}.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
        with lock:
            state["asked"] += 1
            state["done"] += 1
            asked = state["asked"]
            if asked % 10 == 0 or asked == 1:
                el = time.monotonic() - t_start
                print(f"generate: {state['done']}/{len(ids)} ({asked} asked this run, {el:.0f} s, "
                      f"{el / asked:.1f} s each)", flush=True)

    jobs = max(1, getattr(args, "jobs", 1) or 1)
    if jobs == 1:
        for tid in todo:
            one(tid)
            if state["failed"]:
                return 2
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
            list(ex.map(one, todo))
    print(f"generate: {state['done']} of {len(ids)} problems have a reply on disk")
    return 2 if state["failed"] else 0


# --------------------------------------------------------------- extract --

FENCE = re.compile(r"```(?:t|text)?\s*\n(.*?)```", re.S)
HEAD = re.compile(r"(?m)^t [01]\b")


def find_block(reply: str) -> str | None:
    m = FENCE.search(reply)
    if m:
        return m.group(1)
    m = HEAD.search(reply)
    if m:
        return reply[m.start():]
    return None


def rename_task(task: dict, new: str) -> dict:
    """Rename the task and every self-call in its body and spec."""
    old = task["name"]

    def walk(node):
        if isinstance(node, dict):
            if "call" in node and node["call"].get("fun") == old:
                node["call"]["fun"] = new
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(task["body"])
    walk(task.get("ensures", []))
    walk(task.get("requires", []))
    walk(task.get("spec_funs", []))
    task["name"] = new
    return task


def cmd_extract(args) -> int:
    d = outdir(args.model)
    P = pool(args.pool)
    results = {}
    for rec_path in sorted((d / "raw").glob("*.json"), key=lambda p: int(p.stem)):
        rec = json.loads(rec_path.read_text(encoding="utf-8"))
        tid = rec["task_id"]
        entry = {"task_id": tid, "fn": rec["fn"], "reply_tokens": rec.get("reply_tokens"),
                 "done_reason": rec.get("done_reason")}
        block = find_block(rec["reply"])
        if block is None:
            entry["stage"] = "no-block"
            results[tid] = entry
            continue
        entry["block_sha256"] = hashlib.sha256(block.encode("utf-8")).hexdigest()[:16]
        try:
            task = surface.parse(block)
        except surface.SurfaceError as e:
            entry["stage"] = "parse"
            entry["why"] = str(e)[:200]
            results[tid] = entry
            continue
        except Exception as e:                                  # noqa: BLE001
            entry["stage"] = "parse"
            entry["why"] = f"{type(e).__name__}: {e}"[:200]
            results[tid] = entry
            continue
        entry["model_name"] = task.get("name")
        name = f"mbpp_{tid}__{rec['fn']}"
        if not fuzz_lower.NAME_RE.match(name):
            name = f"mbpp_{tid}"
        task = rename_task(task, name)
        try:
            errs = fuzz_lower.check_wf(task)
        except Exception as e:                                  # noqa: BLE001
            errs = [f"check_wf raised {type(e).__name__}: {e}"[:200]]
        if errs:
            entry["stage"] = "wf"
            entry["why"] = "; ".join(errs)[:300]
            results[tid] = entry
            continue
        entry["stage"] = "task"
        entry["name"] = name
        entry["t"] = task["t"]
        entry["gate"] = task.get("gate")
        entry["params"] = [p["type"] for p in task["params"]]
        entry["returns"] = task["returns"][0]["type"]
        entry["loops"] = _count(task["body"], "while")
        entry["selfcall"] = fuzz_lower._self_calls(task["body"], name)
        (d / "tasks" / f"{name}.json").write_text(json.dumps(task, indent=1), encoding="utf-8")
        results[tid] = entry
    (d / "extract.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    stages = {}
    for e in results.values():
        stages[e["stage"]] = stages.get(e["stage"], 0) + 1
    print(f"extract: {len(results)} replies; " + ", ".join(f"{k} {v}" for k, v in sorted(stages.items())))
    return 0


def _count(body, key) -> int:
    n = 0
    for s in body:
        if key in s:
            n += 1
        if "while" in s:
            n += _count(s["while"]["body"], key)
        elif "if" in s:
            n += _count(s["if"]["then"], key) + _count(s["if"]["else"], key)
    return n


# ----------------------------------------------------------------- tests --

def _as_interp_value(kind: str, val):
    """A parsed point's (kind, val) as the tuple-shaped value interp.py
    itself uses: a plain seq is a tuple (unchanged since the v2 fix
    below), and a seq-of-seq (SPEC.md "Nested sequences", pool v3:
    mbpp_dfy.parse_assertion's nested_strings reading) is a tuple of
    tuples, one per row -- interp.py's own nested-seq representation
    (`_nested_seq_ladder`'s `rows: tuple`), not the plain list of lists
    mbpp_dfy.parse_assertion hands back. int, bool and negative-int kinds
    pass through unchanged."""
    if kind == "seq-of-seq":
        return tuple(tuple(row) for row in val)
    if kind == "seq":
        return tuple(val)
    return val


def run_point(task: dict, point: dict) -> dict:
    """One assertion against the task: {"verdict": pass|fail|requires-excluded|
    undefined|budget|arity|type, ...}. Arguments map positionally."""
    params = task["params"]
    args = point["args"]
    if len(args) != len(params):
        return {"verdict": "arity", "why": f"{len(args)} args for {len(params)} params"}
    env = {}
    for p, (kind, val) in zip(params, args):
        # A seq-of-seq argument is still a t `seq` PARAMETER: t's type
        # name carries no nesting depth, only the runtime value does
        # (2026-09-11, pool v3), so it is accepted wherever the task
        # declares "seq", the same as a plain seq argument always was.
        decl_ok = kind == p["type"] or (kind == "seq-of-seq" and p["type"] == "seq")
        if not decl_ok:
            return {"verdict": "type", "why": f"{p['name']} is {p['type']}, test passes {kind}"}
        env[p["name"]] = _as_interp_value(kind, val)
    ret = task["returns"][0]["name"]
    funs = interp.funs_of(task, task["body"])
    st = interp.St()
    try:
        if not all(interp.ev(c, env, funs, st) for c in task.get("requires", [])):
            return {"verdict": "requires-excluded"}
        env2 = dict(env)
        env2[ret] = None
        interp.exec_body(task["body"], env2, funs, st)
        got = env2[ret]
    except interp.Undef as u:
        return {"verdict": "undefined", "why": str(u)[:120]}
    except (interp.Budget, RecursionError) as b:
        return {"verdict": "budget", "why": str(b)[:120]}
    ekind, eval_ = point["expected"]
    if got is None:
        return {"verdict": "undefined", "why": "no path assigned the return"}
    # interp represents a seq value as a tuple, and a nested seq as a
    # tuple of tuples (env setup above does the same on the way in);
    # mbpp_dfy.parse_assertion's expected value is a plain list (or list
    # of lists), so a seq/seq-of-seq comparison needs the same
    # normalization the arguments already get, or a correct answer
    # compares unequal to itself (tuple != list) and every such point
    # misreports "fail". Unreachable under the v1 pool, which never
    # admits a seq expected value; live once --pool v2 (seq) or --pool v3
    # (seq-of-seq, added 2026-09-11) does.
    eval_cmp = _as_interp_value(ekind, eval_)
    ok = (isinstance(got, bool) == (ekind == "bool")) and got == eval_cmp
    return {"verdict": "pass" if ok else "fail", "got": interp._j(got), "expected": eval_}


def cmd_tests(args) -> int:
    d = outdir(args.model)
    P = pool(args.pool)
    ext = json.loads((d / "extract.json").read_text(encoding="utf-8"))
    results = {}
    for tid_s, e in ext.items():
        if e["stage"] != "task":
            continue
        tid = int(tid_s)
        task = harness.load(d / "tasks" / f"{e['name']}.json")
        pts = [run_point(task, p) for p in P[tid]["points"]]
        verdicts = [p["verdict"] for p in pts]
        if all(v == "pass" for v in verdicts):
            overall = "pass"
        elif any(v in ("arity", "type") for v in verdicts):
            overall = "signature"
        elif any(v == "fail" for v in verdicts):
            overall = "fail"
        elif any(v == "requires-excluded" for v in verdicts):
            overall = "requires-excluded"
        else:
            overall = "undefined"
        results[tid] = {"name": e["name"], "overall": overall, "points": pts}
    (d / "tests.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    tally = {}
    for r in results.values():
        tally[r["overall"]] = tally.get(r["overall"], 0) + 1
    print(f"tests: {len(results)} tasks; " + ", ".join(f"{k} {v}" for k, v in sorted(tally.items())))
    return 0


# ----------------------------------------------------------------- table --

def parse_kernel_table(path: Path) -> tuple[list[str], dict[str, dict[str, str]]]:
    cols, rows = [], {}
    if not path.exists():
        return cols, rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells[0] == "task":
            cols = cells[1:]
            continue
        if not cols or len(cells) != len(cols) + 1 or set(cells[0]) <= {"-"}:
            continue
        rows[cells[0]] = dict(zip(cols, cells[1:]))
    return cols, rows


def cmd_table(args) -> int:
    d = outdir(args.model)
    P = pool(args.pool)
    ext = json.loads((d / "extract.json").read_text(encoding="utf-8"))
    tests = json.loads((d / "tests.json").read_text(encoding="utf-8")) if (d / "tests.json").exists() else {}
    cols, cells = parse_kernel_table(d / "kernels.md")
    raw_n = len(list((d / "raw").glob("*.json")))
    dfy_ids = set()
    try:
        import corpora
        if corpora.available(corpora.CORPUS_DIR):
            dfy_ids = set(mbpp_dfy.dfy_task_ids(corpora.CORPUS_DIR))
    except Exception:                                           # noqa: BLE001
        pass

    def counts_in(row: dict) -> int:
        return sum(1 for c in cols if row.get(c) == "verified / refuted")

    lines = []
    L = lines.append
    L(f"# The spec experiment on MBPP: {args.model}")
    L("")
    L("ROADMAP 12.6. One reply per problem, temperature 0, fixed seed; the")
    L("prompt is `spec_experiment.build_prompt` (grammar, five committed tasks")
    L("as examples, the problem text and its three assertions). Every stage")
    L("is a count, every refusal is named, and the two failures 12.6 keeps")
    L("apart are kept apart here: a task that VERIFIES with a REFUTED twin,")
    L("and a task that passes the problem's own tests.")
    L("")
    # stage counts
    stages = {}
    for e in ext.values():
        stages[e["stage"]] = stages.get(e["stage"], 0) + 1
    n_tasks = stages.get("task", 0)
    L("## Stages")
    L("")
    L("| stage | count |")
    L("|---|---:|")
    L(f"| MBPP problems whose tests are in t's fragment (the pool) | {len(P)} |")
    L(f"| replies recorded | {raw_n} |")
    L(f"| replies with a t block | {raw_n - stages.get('no-block', 0)} |")
    L(f"| blocks that parse | {n_tasks + stages.get('wf', 0)} |")
    L(f"| tasks that are well-formed (graded below) | {n_tasks} |")
    L("")
    if stages.get("parse") or stages.get("wf"):
        L("Refusals, by named reason:")
        L("")
        why = {}
        for e in ext.values():
            if e["stage"] in ("parse", "wf"):
                key = e["stage"] + ": " + re.sub(r"\d+", "N", e.get("why", "")).split(";")[0][:70]
                why[key] = why.get(key, 0) + 1
        for k, v in sorted(why.items(), key=lambda kv: -kv[1])[:25]:
            L(f"- {v} x `{k}`")
        L("")
    # tests
    tally = {}
    for r in tests.values():
        tally[r["overall"]] = tally.get(r["overall"], 0) + 1
    L("## The problem's own tests (interp on the MBPP assertions)")
    L("")
    L("| outcome | tasks |")
    L("|---|---:|")
    for k in ("pass", "fail", "requires-excluded", "undefined", "signature"):
        if tally.get(k):
            L(f"| {k} | {tally[k]} |")
    L("")
    # kernels
    L("## The seven kernels (real / twin), over the well-formed tasks")
    L("")
    if cells:
        per = {c: sum(1 for r in cells.values() if r.get(c) == "verified / refuted") for c in cols}
        L("| kernel | verified / refuted | of tasks |")
        L("|---|---:|---:|")
        for c in cols:
            L(f"| {c} | {per[c]} | {len(cells)} |")
        L("")
        hist = {}
        for r in cells.values():
            k = counts_in(r)
            hist[k] = hist.get(k, 0) + 1
        L("| columns counting | " + " | ".join(str(k) for k in range(len(cols), -1, -1)) + " |")
        L("|---|" + "---|" * (len(cols) + 1))
        L("| tasks | " + " | ".join(str(hist.get(k, 0)) for k in range(len(cols), -1, -1)) + " |")
        L("")
        twin_refused = sum(1 for r in cells.values() if all(v == "no-twin / no-twin" for v in r.values()))
        L(f"Tasks with no twin at all (every mutation on the ladder computes what the real body computes, or no input satisfies requires): {twin_refused}.")
        L("")
    else:
        L("(no kernel table yet: run run_par.py over tasks/ and re-run table)")
        L("")
    # cross-tab
    L("## 12.6's table: verifies with a refuted twin, against passes its tests")
    L("")
    name_to_tid = {e["name"]: int(t) for t, e in ext.items() if e["stage"] == "task"}
    if cells and tests:
        buckets = {}
        rows_out = []
        for name, row in cells.items():
            tid = name_to_tid.get(name)
            tr = tests.get(str(tid), {}).get("overall", "?")
            k = counts_in(row)
            seven = k == len(cols)
            any_ = k >= 1
            key = ("all seven" if seven else ("some column" if any_ else "none"), "tests pass" if tr == "pass" else f"tests {tr}")
            buckets[key] = buckets.get(key, 0) + 1
            rows_out.append((tid, name, k, tr, row))
        L("| verifies with refuted twin in | tests pass | tests fail | requires-excluded | undefined | signature |")
        L("|---|---:|---:|---:|---:|---:|")
        for band in ("all seven", "some column", "none"):
            vals = [buckets.get((band, f"tests {t}"), 0) for t in ("pass", "fail", "requires-excluded", "undefined", "signature")]
            L(f"| {band} | " + " | ".join(str(v) for v in vals) + " |")
        L("")
        both7 = buckets.get(("all seven", "tests pass"), 0)
        both1 = both7 + buckets.get(("some column", "tests pass"), 0)
        L(f"**{both7} of {len(P)} problems** got a task that verifies with a refuted twin in all seven columns and passes its tests; "
          f"{both1} in at least one column. Verified-with-twin but failing its tests, the class 12.6 warns about: "
          f"{buckets.get(('all seven', 'tests fail'), 0)} in all seven, {buckets.get(('some column', 'tests fail'), 0)} in some column.")
        L("")
        if dfy_ids:
            sub = [r for r in rows_out if r[0] in dfy_ids]
            s7 = sum(1 for r in sub if r[2] == len(cols) and r[3] == "pass")
            n_dfy_pool = len(set(P) & dfy_ids)
            L(f"MBPP-DFY subset: {n_dfy_pool} pool problems are MBPP-DFY problems (ROADMAP 16.2's family); "
              f"{len(sub)} of them reached the kernels and {s7} verify in all seven and pass their tests.")
            L("")
        L("## Every task")
        L("")
        L("| task_id | task | columns counting | tests | " + " | ".join(cols) + " |")
        L("|---:|---|---:|---|" + "---|" * len(cols))
        for tid, name, k, tr, row in sorted(rows_out):
            L(f"| {tid} | {name} | {k} | {tr} | " + " | ".join(row.get(c, "") for c in cols) + " |")
        L("")
    else:
        L("(needs both tests.json and kernels.md)")
        L("")
    # refusals detail
    L("## Problems that produced no graded task")
    L("")
    L("| task_id | fn | stage | why |")
    L("|---:|---|---|---|")
    for tid_s, e in sorted(ext.items(), key=lambda kv: int(kv[0])):
        if e["stage"] != "task":
            L(f"| {tid_s} | {e['fn']} | {e['stage']} | {e.get('why', '')[:120].replace('|', '/')} |")
    L("")
    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"table: wrote {args.out}")
    return 0


# ------------------------------------------------------------------ main --

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("pool", "generate", "extract", "tests", "table"):
        p = sub.add_parser(name)
        p.add_argument("--model", default="qwen2.5-coder:7b")
        p.add_argument("--pool", choices=POOL_VERSIONS, default="v1",
                        help="v1 (default, frozen 2026-09-08: int/bool "
                             "arguments and results only), v2 (admits "
                             "MBPP tests whose arguments or results are "
                             "Python strings, typed as seq), or v3 "
                             "(v2 plus a list-of-strings argument or "
                             "result, seq-of-seq, when the reference "
                             "solution's string-library use is all v1 "
                             "members in v1 forms)")
        if name == "generate":
            p.add_argument("--prompt", choices=PROMPT_VERSIONS, default="v1",
                            help="v1 (default, frozen), v2 (grammar and "
                                 "few-shots add the sequence literal/"
                                 "concat/slice trio and the char/string "
                                 "sugar), or v3 (v2 plus the string "
                                 "library's notation and two more "
                                 "few-shot tasks)")
            p.add_argument("--host", default="127.0.0.1:11434")
            p.add_argument("--limit", type=int, default=0)
            p.add_argument("--seed", type=int, default=1)
            p.add_argument("--num-ctx", type=int, default=8192)
            p.add_argument("--num-predict", type=int, default=1024)
            p.add_argument("--timeout", type=float, default=600.0)
            p.add_argument("--jobs", type=int, default=1)
        if name == "table":
            p.add_argument("--out", default=str(HERE / "SPEC-EXPERIMENT-mbpp.md"))
    args = ap.parse_args(argv)
    if args.cmd == "pool":
        rep = pool_report(args.pool)
        print(json.dumps(rep, indent=1))
        return 0
    return {"generate": cmd_generate, "extract": cmd_extract,
            "tests": cmd_tests, "table": cmd_table}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
