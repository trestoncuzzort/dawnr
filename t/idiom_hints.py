#!/usr/bin/env python3
"""t/idiom_hints.py -- what to say when an answer does not parse because it reached for a construct t
spells another way (2026-10-01).

The fine-tuned 4B's unparseable dev answers fall into a few classes by what is written on the
line the parser stops at (t/PREDICT-2026-10-01-several-answers.md): a comprehension or an
aggregate over one, a quantifier with no range, a quantifier over elements, a nested type under
the prompt's old word for it, operators and loops from other languages. The parser's message for
all of them is "expected X, found Y", which says where and not what to write.

AutoVerus (arXiv:2409.13082) routes each verifier error to a repair agent for its type, whose
prompt carries "the instruction about how to fix errors of [that] type"; over 657 repair
iterations those agents succeed 57.4% of the time, and its debugging phase proves 37 more of 150
tasks. Here the instruction is one sentence that names the `t` idiom, appended to the parser's
own message in t/debug_rows.message_for, so the debugging rows and the repair loop say the same
words. Every example in a hint is checked by the tests to be valid `t`.
"""
from __future__ import annotations

import re

# The example is the form the provers accept. With it and the loop invariant `r == count_neg(s, i)`
# a counting loop is proved by all seven kernels with its twin refuted (run 2026-10-01). Without
# the `n > len(s)` guard the function indexes outside the seq for some arguments, and only two of
# the seven prove the same loop.
COUNT_EXAMPLE = ("spec fun count_neg(s: seq, n: int): int\n"
                 "  decreases n\n"
                 "= if n <= 0 or n > len(s) then 0 else count_neg(s, n - 1) + (if s[n - 1] < 0 then 1 else 0)")

# (class, a pattern on the offending line, the hint). First match wins.
_CLASSES = [
    ("nested type",
     re.compile(r"seq\s+of\s+seq|seq-of-seq"),
     "The nested type is written seq<seq>."),
    ("comprehension",
     re.compile(r"\[[^\]]*\b(in|for)\b[^\]]*\]|\b(sum|count|max|min)\s*\([^)]*\bfor\b"),
     # since SPEC.md "Comprehensions (v1)" and "The library (v1)" (2026-10-06) the forms exist; the hint names them
     "A comprehension is written [x for x in s if x < 0] (or [e for i in [a, b) if p]); a count of the elements "
     "is len([x for x in s if x < 0]); sum(s), min(a, b), max(a, b) and abs(x) are the library's. A quantity "
     "can also be a recursive spec fun over a prefix length, placed after the ensures, for example\n" + COUNT_EXAMPLE +
     "\nwith count_neg(s, len(s)) in the ensures and count_neg(s, i) in the loop invariant."),
    ("unbounded quantifier",
     re.compile(r"\b(forall|exists)\s+\w+(\s*,\s*\w+|\s+\w+)*\s*(:\s*(int|nat|bool)\b|such\s+that|>=|<=|<|>|\|)"),
     "A quantifier ranges over a half-open interval of integers: exists k in [lo, hi) . P. "
     "Give the interval the problem implies."),
    ("element quantifier",
     # since SPEC.md "Quantifiers over a collection" (2026-10-07) `forall x in s . P` exists; a range with a postfix
     # (an index, a slice, a field) still does not parse, since the `.` after the range is the quantifier's own
     re.compile(r"\b(forall|exists)\s+\w+\s+in\s+(?!\[|\()\w+\s*[\[.]\s*\w"),
     "A quantifier over a collection takes a name, a call or a parenthesized range: forall x in (s[1..]) . x >= 0; "
     "over indices it is forall i in [0, len(s)) . s[i] >= 0."),
    ("power",
     re.compile(r"\*\*|\^"),
     "There is no power operator: multiply, or define the power with a recursive spec fun."),
    ("for loop",
     re.compile(r"^\s*for\b"),
     # since SPEC.md "Loops as sugar (v1)" (2026-10-06) a for loop exists; a Python colon or range() does not parse
     "A for loop is `for i in [a, b) invariant ... { ... }` or `for x in s invariant ... { ... }`: no colon, no "
     "range(), the body in braces; the loop supplies its bound invariants and decreases."),
    ("boolean operators",
     re.compile(r"&&|\|\|"),
     "The boolean operators are written and, or, not."),
    ("python slice",
     re.compile(r"\[[^\]\[]*:[^\]\[]*\]"),
     "A slice is written s[lo..hi]."),
]
_WHERE = re.compile(r"<string>:(\d+):(\d+):")


def offending_line(block: str, why: str | None) -> str | None:
    m = _WHERE.search(why or "")
    lines = (block or "").splitlines()
    if not m or not 1 <= int(m.group(1)) <= len(lines):
        return None
    return lines[int(m.group(1)) - 1]


def classify(block: str, why: str | None) -> tuple[str, str] | None:
    """(class, hint) for a block the parser refused with message `why`, or None."""
    line = offending_line(block, why)
    if line is None:
        return None
    for name, pattern, hint in _CLASSES:
        if pattern.search(line):
            return name, hint
    return None


def hint(block: str, why: str | None) -> str | None:
    found = classify(block, why)
    return found[1] if found else None
