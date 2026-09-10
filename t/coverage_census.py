#!/usr/bin/env python3
"""coverage_census.py: which constructs a verification corpus needs that t
does not have, program by program, and which gate opens the most programs.

    python3 t/coverage_census.py <dir of .dfy files> [--out t/COVERAGE-<name>.md]
                                 [--json <per-file tags>]

The corpus is read as Dafny source (DafnyBench ground_truth, 785 programs,
Apache-2.0, is the first one; ROADMAP 10.4). Each program is tagged with the
GAPS it needs, constructs outside t's fragment (SYNTAX.md), with the BURDENS
it carries, things t can express another way at some translation cost, and
with the HINTS it uses, proof scaffolding a kernel might or might not need
(t has no assert statement and no lemma). A program is IN FRAGMENT when its
gap set is empty and it carries at least one method with an ensures OF ITS
OWN, a function's or a lemma's does not count; a gap set, not a verdict,
because nothing here runs a kernel. The greedy curve at the end answers the
question this file exists for: opening which gate next unlocks the most
programs, given the gates already open.

Detection is lexical, on source with comments and string/char literals
masked (their presence is recorded first, outside `{:attribute}` arguments
and outside `method Main`). Lexical means approximate, so the report names
every detector and the census is checked by sampling (see the Method section
of the report) rather than trusted. Where a detector cannot tell two things
apart (a `+` on sequences from a `+` on integers) it says so and tags the
cheaper reading, so the census can UNDER-count a gap but the detectors that
fire are real. Several detectors are scanners rather than one regex, because
the receiver, the enclosing declaration or the bracket nesting decides what a
token means: an element assignment is a statement and not the `:=` inside
`m[k := v]`, an update bracket belongs to a map as often as to a sequence, a
`:|` is nondeterministic choice in a method and proof scaffolding in a lemma,
a return is early only when it is not in tail position of a method body, and
a brace holding one identifier is a set display only in expression position.

Proof scaffolding is blanked before any gap or burden is read: whole lemma
declarations, and `assert`, `assume` and `calc` statements. SYNTAX.md is
explicit that these are hints which never put a program outside the fragment,
and t has no lemmas at all, so a set, a quantifier or a nondeterministic
choice that appears ONLY inside one is not a construct the program needs. The
hint detectors themselves read the unblanked text, since a lemma has to be
visible to be counted as one.

Stdlib only, like every instrument in t/.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# -------------------------------------------------------------- masking
_STR = re.compile(r'@"(?:[^"]|"")*"|"(?:[^"\\\n]|\\.)*"')
_CHR = re.compile(r"'(?:[^'\\\n]|\\.)'")
_ATTR = re.compile(r"\{:\s*[A-Za-z_]")


def blank(s: str) -> str:
    """Every character but the newlines replaced by a space, so offsets and
    line numbers survive."""
    return "".join(c if c == "\n" else " " for c in s)


def mask(src: str) -> tuple[str, dict]:
    """Comments and literals blanked (newlines kept); returns the masked text
    and what was seen: string literals, char literals.

    A literal inside a `{:name ...}` attribute is blanked like any other but
    is NOT recorded: attributes are hints, so `{:extern "Foo"}` must not make
    the program need strings."""
    seen = {"string_lit": False, "char_lit": False}
    out = []
    attr = 0  # brace depth inside a `{:` attribute, 0 when outside one
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if c == "{":
            attr = attr + 1 if attr else (1 if _ATTR.match(src, i) else 0)
        elif c == "}" and attr:
            attr -= 1
        if c == "/" and nxt == "/":
            j = src.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
        elif c == "/" and nxt == "*":
            depth, j = 1, i + 2
            while j < n and depth:
                if src.startswith("/*", j):
                    depth, j = depth + 1, j + 2
                elif src.startswith("*/", j):
                    depth, j = depth - 1, j + 2
                else:
                    j += 1
            out.append("".join(ch if ch == "\n" else " " for ch in src[i:j]))
            i = j
        elif c == '"' or (c == "@" and nxt == '"'):
            m = _STR.match(src, i)
            if m:
                seen["string_lit"] = seen["string_lit"] or not attr
                out.append(" " * (m.end() - i))
                i = m.end()
            else:
                out.append(c)
                i += 1
        elif c == "'":
            m = _CHR.match(src, i)
            if m:
                seen["char_lit"] = seen["char_lit"] or not attr
                out.append(" " * (m.end() - i))
                i = m.end()
            else:
                out.append(c)
                i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out), seen


# -------------------------------------------------------------- detectors
# Each entry: name -> (kind, regex or callable, one-line meaning).
# kind: "gap" (outside t), "burden" (expressible at a cost), "hint" (proof
# scaffolding), "shape" (structural facts used by the in-fragment rule).
IDENT = r"[A-Za-z_][A-Za-z0-9_']*"

def _has(rx: str, flags=re.M):
    r = re.compile(rx, flags)
    return lambda s: r.search(s) is not None


# Keywords an expression may follow, so a `[` after one of them opens a
# sequence display and indexes nothing: `then [0]`, `return [];`, `x in [1]`.
# Every one is reserved in Dafny, so no identifier ends in one as a token.
SEQ_LIT_KEYWORDS = frozenset(
    "then else return in case assert assume requires ensures invariant "
    "decreases yield print var calc reads modifies".split())


def _seq_literal(s: str) -> bool:
    # `[` preceded by an identifier char, an apostrophe, `]` or `)` (those
    # are indexing or slicing: `a[i]`, `m'[j]`, `f(x)[0]`, and an `[i]` that
    # a line break put under its `arr`), and not the empty `[]` of a type;
    # `[1, 2]`, `[x]`, `[]`.
    # Whitespace is NOT collapsed: `new int [n]` still indexes, but a `[`
    # whose previous token is one of SEQ_LIT_KEYWORDS opens a literal.
    for m in re.finditer(r"\[", s):
        head = s[:m.start()].rstrip()
        if re.search(r"[A-Za-z0-9_'\]\)>]$", head):
            word = re.search(IDENT + r"$", head)
            if not (word and word.group(0) in SEQ_LIT_KEYWORDS):
                continue
        j = s.find("]", m.end())
        if j < 0:
            continue
        inner = s[m.end():j]
        if ".." in inner:
            continue
        if inner.strip() == "" or re.search(r"[A-Za-z0-9_]", inner):
            # exclude attribute-ish and declaration contexts
            if re.search(r"(?:array\d*|(?<!:):)$", head):
                continue
            return True
    return False


# A brace group holding nothing but identifiers and integers is a set display
# only in expression position. Every other `{` of that shape opens a
# declaration body or a block, so the token in front of it decides.
_SET_CTX = re.compile(
    r"(?:[-+*(,\[]|:=|:\||<==>|==>|<=|>=|==|!=|<-|=>|::|&&|\|\||"
    r"\b(?:in|then|else|return|i?set|multiset))\s*$")
_SET_DISPLAY = re.compile(
    r"\{\s*(?:-?\d+|" + IDENT + r")(?:\s*,\s*(?:-?\d+|" + IDENT + r"))*\s*\}")
_SET_KIND = re.compile(r"\bi?set<|\bmultiset\b|\bset\s+" + IDENT + r"\s*(?::|\|)")


def _set(s: str) -> bool:
    """set / iset / multiset type, a set comprehension, or a set display.
    A display counts only when the text before its `{` ends in an operator,
    `(`, `,`, `[`, or one of in / then / else / return / set / iset /
    multiset. A `{` that follows `)`, a type or result name, an identifier
    or a closing cardinality bar opens a body, not a set: `predicate P()
    { false }`, `function f(x: int): int { x }`, `function Size(): nat
    ensures Size() == |Elements| { size }`, `reads this { sense }`."""
    if _SET_KIND.search(s):
        return True
    return any(_SET_CTX.search(s[:m.start()]) for m in _SET_DISPLAY.finditer(s))


_UPDATE = re.compile(r"\[[^\]]+:=[^\]]+\]")
_MAPPISH = ("map", "imap", "multiset", "set", "iset")
_SLICE_RECV = object()   # a slice or a sequence literal: a sequence for sure
_NO_RECV = object()      # nothing before the bracket: a literal, not an update


def _map_names(s: str) -> set:
    """Identifiers this file declares with a map, imap or multiset type: a
    typed declaration `x: map<..>` (field, parameter, datatype component) or
    an initialiser `var x := map[..]` / `var x := multiset{..}`."""
    names = set()
    for m in re.finditer(r"(" + IDENT + r")\s*:\s*(?:i?map|multiset)\s*[<\[{]", s):
        names.add(m.group(1))
    for m in re.finditer(r"\bvar\s+(" + IDENT + r")\s*:=\s*(?:i?map|multiset)\s*[<\[{(]", s):
        names.add(m.group(1))
    return names


def _match_back(s: str, i: int, close: str, open_: str) -> int:
    """Index of the bracket that opens the closer at i, or -1."""
    depth = 0
    while i >= 0:
        if s[i] == close:
            depth += 1
        elif s[i] == open_:
            depth -= 1
            if depth == 0:
                return i
        i -= 1
    return -1


def _update_receiver(s: str, end: int):
    """What owns an update bracket whose receiver expression ends at index
    `end`: the name of the variable, field or callee, _SLICE_RECV when the
    receiver is a slice or a sequence literal, _NO_RECV when there is no
    receiver at all (the bracket opens a literal), or None when the receiver
    is an expression no name can be read off."""
    while end >= 0 and s[end] in " \t\r\n":
        end -= 1
    if end < 0:
        return _NO_RECV
    if s[end] == ")":
        op = _match_back(s, end, ")", "(")
        if op < 0:
            return None
        j = op - 1
        while j >= 0 and s[j] in " \t\r\n":
            j -= 1
        k = j
        while k >= 0 and (s[k].isalnum() or s[k] in "_'@"):
            k -= 1
        name = s[k + 1:j + 1].split("@")[0]
        if name == "old":
            return _update_receiver(s, end - 1)
        return name or None
    if s[end] == "]":
        op = _match_back(s, end, "]", "[")
        if op < 0:
            return None
        if ".." in s[op + 1:end]:
            return _SLICE_RECV
        r = _update_receiver(s, op - 1)
        # `[..][i := v]` and `[a, b][i := v]`: a bracket with nothing before
        # it is a sequence literal, since a map literal carries its keyword.
        return _SLICE_RECV if r is _NO_RECV else r
    if s[end].isalnum() or s[end] in "_'":
        k = end
        while k >= 0 and (s[k].isalnum() or s[k] in "_'"):
            k -= 1
        return s[k + 1:end + 1]
    return _NO_RECV


def _seq_evidence(s: str) -> bool:
    """Whether the file holds a sequence at all: a seq or string type, a
    slice, or a sequence literal. With none of those, `[k := v]` cannot be
    a sequence update."""
    if re.search(r"\bseq\b|\bstring\b|\[[^\]]*\.\.", s):
        return True
    return _seq_literal(s)


def _seq_update(s: str) -> bool:
    # `[k := v]` updates a map, an imap or a multiset exactly as often as it
    # updates a sequence, and those carry their own gaps, so the receiver
    # decides. A slice receiver is a sequence outright; a receiver named as
    # a map, imap or multiset is not, and no receiver at all means the
    # bracket opens a literal; anything else counts only when the file holds
    # a sequence somewhere. A call receiver is read as unknown, so a
    # map-returning call in a file that also has sequences still tags.
    names = _map_names(s)
    evidence = None
    for m in _UPDATE.finditer(s):
        r = _update_receiver(s, m.start() - 1)
        if r is _SLICE_RECV:
            return True
        if r is _NO_RECV or r in _MAPPISH or r in names:
            continue
        if evidence is None:
            evidence = _seq_evidence(s)
        if evidence:
            return True
    return False


# The head of a quantifier: `::` ends it, a single `:` (a type annotation)
# does not, and `;` or a brace ends the search, so a `forall` STATEMENT with
# no `::` cannot run on into the next clause and match its `::`.
_QUANT_HEAD = re.compile(r"\b(forall|exists)\b((?:[^:;{}]|:(?!:))*?)::")
# `{:trigger ...}` and friends: hints, and they carry a colon, so they are
# blanked before the head is read.
_ATTRIBUTE = re.compile(r"\{:(?:[^{}]|\{[^{}]*\})*\}")
_CMP = re.compile(r"(<=|<|>=|>|==|&&|\|\|)")


def _word(n: str) -> str:
    r"""`n` as a whole Dafny identifier. A prime is part of a name, so `\b`
    will not do: `j'` and `j` are different variables."""
    return r"(?<![A-Za-z0-9_'])" + re.escape(n) + r"(?![A-Za-z0-9_'])"


def _binders(decl: str) -> list[tuple[str, str]]:
    """(name, declared type) for each binder of a quantifier; the type is ""
    when it is omitted. Commas inside `<...>` do not separate binders."""
    items, depth, cur = [], 0, []
    for ch in decl:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            items.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    items.append("".join(cur))
    out = []
    for it in items:
        m = re.match(r"\s*(" + IDENT + r")\s*(?::\s*(.*\S))?\s*$", it, re.S)
        if m:
            out.append((m.group(1), (m.group(2) or "").strip()))
    return out


_INT_ATOM = r"(?:\|[^|]*\||\d+|" + IDENT + r"(?:\s*[\[(][^\[\]()]*[\])])?)"
_INT_SHAPED = re.compile(r"^[\s(]*[-+]?" + _INT_ATOM +
                         r"(?:\s*[-+*]\s*[-+]?" + _INT_ATOM + r")*[\s)]*$")
_INT_RESULT = re.compile(r"\b(?:function|predicate)\s+(?:method\s+)?(" + IDENT +
                         r")\s*(?:<[^>]*>)?\s*\([^)]*\)\s*:\s*(?:int|nat)\b")
_INT_COLL = re.compile(r"\b(" + IDENT + r")\s*:\s*(?:array\d*|seq)<\s*(?:int|nat)\s*>")


def _int_names(s: str) -> set:
    """Names the file itself declares to denote an integer: functions and
    predicates whose result type is int or nat, and arrays and sequences of
    them. Read off the source rather than assumed, so a call or an index is
    only integer shaped when this file says it is."""
    return {m.group(1) for m in _INT_RESULT.finditer(s)} | \
           {m.group(1) for m in _INT_COLL.finditer(s)}


def _int_shaped(e: str, names: set = frozenset()) -> bool:
    """True when `e` could denote an integer position: a literal, a name, a
    cardinality, a call or an index the file types as int, or arithmetic over
    those. A field access, or a call this file does not type, is not, so
    `tx == txQueues[pid][state.currentTx]` does not pin tx to a range while
    `p == Count(b.Length, a[..])` does when Count is declared to return int."""
    e = e.strip()
    if "." in re.sub(r"\.\.", "", e):
        return False
    head = re.match(r"^[\s(]*[-+]?\s*(" + IDENT + r")\s*[\[(]", e)
    if head and head.group(1) not in names:
        return False
    return _INT_SHAPED.match(e) is not None


def _range_bounds(n: str, head: str, names: set = frozenset()) -> tuple[bool, bool]:
    """(lower, upper) for `n` in a quantifier head. The operand has to be a
    BARE `n` (or `n + k`): in `0 < a*a < n` the comparisons bound the
    product, not `a`, and t's forall wants `lo <= a < hi` on `a` itself.
    `n == e` pins `n` to a range of one, so it counts as both."""
    bare = re.compile(r"^[(\s]*" + re.escape(n) + r"\s*(?:[-+]\s*\d+\s*)?[)\s]*$")
    lo = hi = False
    toks = _CMP.split(head)
    for k in range(1, len(toks) - 1, 2):
        op = toks[k]
        if op in ("&&", "||"):
            continue
        left = bare.match(toks[k - 1]) is not None
        right = bare.match(toks[k + 1]) is not None
        if op == "==":
            other = toks[k + 1] if left else toks[k - 1]
            if ((left and not re.search(_word(n), toks[k + 1])) or
                    (right and not re.search(_word(n), toks[k - 1]))) \
                    and _int_shaped(other, names):
                lo = hi = True
        elif op in ("<", "<="):
            lo, hi = lo or right, hi or left
        else:
            lo, hi = lo or left, hi or right
    return lo, hi


_HINT_KW = re.compile(r"\b(?:assert|assume|calc)\b")
_LEMMA_KW = re.compile(r"\b(?:(?:least|greatest|twostate|inductive)\s+)*lemma\b")
_DECL_KW = re.compile(r"\b(?:method|function|predicate|lemma|class|trait|datatype|"
                      r"codatatype|module|import|include|iterator|newtype|type|const|"
                      r"least|greatest|twostate|inductive|ghost|static|abstract)\b")


def _hint_end(s: str, start: int) -> int:
    """End of the assert, assume or calc statement beginning at `start`. A
    plain `assert P;` ends at its semicolon; `assert P by { .. }` and
    `calc { .. }` end when their block closes, and neither carries a
    semicolon, so a scanner that only looks for one eats the rest of the
    enclosing body."""
    depth, j = 0, start
    while j < len(s):
        c = s[j]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            if depth == 0:
                return j
            depth -= 1
            if depth == 0 and c == "}":
                return j + 1
        elif c == ";" and depth == 0:
            return j + 1
        j += 1
    return len(s)


def _lemma_end(s: str, start: int) -> int:
    """End of the lemma declaration beginning at `start`: its signature, its
    spec clauses and its body if it has one. A bodyless lemma ends where the
    next declaration begins."""
    depth, j = 0, start
    while j < len(s):
        c = s[j]
        if c in "([":
            depth += 1
        elif c in ")]":
            depth = max(0, depth - 1)
        elif c == "{" and depth == 0:
            k, d = j, 0
            while k < len(s):
                if s[k] == "{":
                    d += 1
                elif s[k] == "}":
                    d -= 1
                    if d == 0:
                        return k + 1
                k += 1
            return len(s)
        elif c == "}" and depth == 0:
            return j
        elif depth == 0:
            m = _DECL_KW.match(s, j)
            if m and j > start:
                return j
        j += 1
    return len(s)


def _mask_hints(s: str) -> str:
    """Blank the proof scaffolding, newlines kept: assert, assume and calc
    statements, and whole lemma declarations. SYNTAX.md is explicit that these
    are hints and never put a program outside t's fragment, so a set literal,
    a quantifier or a nondeterministic choice that appears ONLY inside one is
    not a construct the program needs. t has no lemmas at all: a lowering
    drops them."""
    out = list(s)
    spans = [(m.start(), _lemma_end(s, m.end())) for m in _LEMMA_KW.finditer(s)]
    spans += [(m.start(), _hint_end(s, m.end())) for m in _HINT_KW.finditer(s)]
    for i, j in spans:
        for k in range(i, min(j, len(s))):
            if out[k] != "\n":
                out[k] = " "
    return "".join(out)


def _mask_assertions(s: str) -> str:
    """Kept as the quantifier scan's own entry point; see _mask_hints."""
    out = list(s)
    for m in _HINT_KW.finditer(s):
        depth, j = 0, m.end()
        while j < len(s):
            c = s[j]
            if c in "([{":
                depth += 1
            elif c in ")]}":
                if depth == 0:
                    break
                depth -= 1
            elif c == ";" and depth == 0:
                j += 1
                break
            j += 1
        for k in range(m.start(), min(j, len(s))):
            if out[k] != "\n":
                out[k] = " "
    return "".join(out)


def _unbounded_quantifier(s: str) -> bool:
    # A quantifier whose bound variables are not all int-typed-with-a-range:
    # a non-int declared type, or no int range [lo, hi) on the variable
    # itself in the guard after `|` (and, for a forall, in the body before
    # the `==>` that starts it). Membership `v in e` still counts as a
    # range (a bounded exists over a seq, a burden); `v !in e` does not,
    # since it names everything the collection leaves out.
    names = _int_names(s)
    s = _mask_hints(_ATTRIBUTE.sub(" ", s))
    for m in _QUANT_HEAD.finditer(s):
        pipe = m.group(2).split("|", 1)
        body = s[m.end():m.end() + 200]
        if m.group(1) == "forall":
            body = re.split(r"(?<!<)==>", body, 1)[0]
        head = (pipe[1] if len(pipe) > 1 else "") + " && " + body
        head = re.sub(r"<==>|<==|==>", " && ", head)
        for n, typ in _binders(pipe[0]):
            if re.search(_word(n) + r"\s+in\b", head):
                continue
            if typ and not re.match(r"(?:int|nat)\s*$", typ):
                return True
            lo, hi = _range_bounds(n, head, names)
            if typ == "nat":
                lo = True
            if not (lo and hi):
                return True
    return False


def main_span(s: str) -> tuple[int, int] | None:
    """(start, end) of `method Main` and its body, or None when there is no
    Main or it has no body; end is exclusive."""
    m = re.search(r"\bmethod\s+Main\b", s)
    if not m:
        return None
    i = s.find("{", m.end())
    if i < 0:
        return None
    depth, j = 0, i
    while j < len(s):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                break
        j += 1
    return m.start(), min(j + 1, len(s))


def strip_main(s: str) -> str:
    """Blank the body of `method Main` (a test harness, not the program) so
    its prints, arrays and calls do not tag the program."""
    span = main_span(s)
    if span is None:
        return s
    i, j = span
    return s[:i] + blank(s[i:j]) + s[j:]


_RET_DECL = re.compile(r"\b(?:method|lemma|function|predicate|constructor|iterator"
                       r"|class|trait|(?:co)?datatype|module)\b")
_ELSE = re.compile(r"\s*else\b")
_IF = re.compile(r"\s*if\b")
_LABELLED = re.compile(r"^label\s+" + IDENT + r"\s*:\s*")


def _brace_close(s: str, i: int) -> int:
    """Index just past the `}` that matches the `{` at i."""
    depth, j, n = 0, i, len(s)
    while j < n:
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    return n


def _method_bodies(s: str) -> list[tuple[int, int]]:
    """The brace span of every `method` body. A header carries `{:attr}`
    groups and its clauses carry set literals, so the body is the LAST
    top-level group between the keyword and the next declaration or the close
    of the enclosing scope. `function method` / `predicate method` are
    functions; `method Main` is already blanked."""
    spans = []
    for m in re.finditer(r"\bmethod\b", s):
        if re.search(r"\b(?:function|predicate)\s+$", s[max(0, m.start() - 24):m.start()]):
            continue
        i, n, groups = m.end(), len(s), []
        while i < n:
            c = s[i]
            if c == "}":
                break
            if c == "{":
                j = _brace_close(s, i)
                if not s.startswith("{:", i):
                    groups.append((i, j))
                i = j
                continue
            if (c.isalpha() or c == "_") and _RET_DECL.match(s, i):
                break
            i += 1
        if groups:
            spans.append(groups[-1])
    return spans


def _intro(s: str, brace: int, lo: int) -> str:
    """What introduces the block opening at `brace`: the text back to the
    previous `;`, `{` or `}`, with parenthesised parts dropped."""
    j = brace - 1
    while j > lo and s[j] not in ";{}":
        j -= 1
    txt, prev = s[j + 1:brace], None
    while prev != txt:
        prev, txt = txt, re.sub(r"\([^()]*\)", " ", txt)
    return _LABELLED.sub("", " ".join(txt.split()))


def _kind(intro: str) -> str:
    """if (a then/else branch), match, case (a match arm), loop, or other."""
    if re.match(r"(?:else\s+)?if\b", intro) or intro == "else":
        return "if"
    if re.match(r"match\b", intro):
        return "match"
    if re.match(r"(?:while|for|forall)\b", intro):
        return "loop"
    if intro.startswith("case") or re.search(r"(?<![=<>!])=>$", intro):
        return "case"
    return "other"


def _chain_end(s: str, close: int, limit: int) -> int:
    """End of the if / else-if / else chain whose first branch closes at
    `close`; a branch is a block or a single statement ending in `;`."""
    pos = close
    while True:
        m = _ELSE.match(s, pos)
        if not m or m.end() > limit:
            return pos
        k = m.end()
        m2 = _IF.match(s, k)
        if m2:                      # else if <cond> ...: skip the condition
            k, depth = m2.end(), 0
            while k < limit and not (depth == 0 and s[k] in "{;"):
                depth += (s[k] == "(") - (s[k] == ")")
                k += 1
        else:
            while k < limit and s[k].isspace():
                k += 1
        if k < limit and s[k] == "{":
            pos = _brace_close(s, k)
            continue
        j = s.find(";", k)
        if j < 0 or j >= limit:
            return limit
        pos = j + 1


def _tail(s: str, bstart: int, bend: int, kw: int, after: int) -> bool:
    """True when the return at `kw` is in tail position of the method body
    spanning [bstart, bend): last in its own block, and every block between
    it and the body is an if/else branch or a match arm whose construct is
    itself last. A return inside a loop is never in tail position."""
    semi = s.find(";", after)
    if semi < 0 or semi >= bend:
        return False
    stack, j = [], bstart
    while j < kw:
        if s[j] == "{":
            stack.append(j)
        elif s[j] == "}" and stack:
            stack.pop()
        j += 1
    if not stack:
        return False
    rest = s[semi + 1:_brace_close(s, stack[-1]) - 1].lstrip()
    if rest and not rest.startswith("case"):    # a further match arm is not a
        return False                            # statement after the return
    for k in range(len(stack) - 1, 0, -1):
        parent_end = _brace_close(s, stack[k - 1]) - 1
        kind = _kind(_intro(s, stack[k], stack[k - 1]))
        if kind == "case":          # arms are alternatives; the match block
            continue                # itself is checked on the next round
        if kind not in ("if", "match"):
            return False
        end = _brace_close(s, stack[k])
        if kind == "if":
            end = _chain_end(s, end, parent_end)
        if s[end:parent_end].strip():
            return False
    return True


def _returns(s: str) -> tuple[bool, bool]:
    """(early, trailing): control that leaves a method other than by falling
    off the end of its body, RETURN statements only (`_break_continue`
    below is the separate signal for break/continue). Only `method` bodies
    are scanned: a return in a lemma, function or predicate is proof
    scaffolding, never a program exit. A return in TAIL position (last in
    the body, or last in an if/else branch or match arm that is itself
    last) is the trailing-return burden; every other return is early. A
    bare `label` is not an exit, it anchors old@L.

    Both are in-fragment burdens as of SPEC.md's "Early exit (v1)"
    (2026-09-08, LIFTER-DECISIONS.md row 21): a tail return lifts by
    dropping (already the `trailing-return` burden), and a non-tail
    return now lifts to t's `{"return": [ret, e]}` statement (the
    `early-return` burden below), so neither counts as an `early-exit`
    gap any more. As of 2026-09-09 (LIFTER-DECISIONS.md row 23) a break
    whose loop is in tail position of the method body is in the same
    position: it lifts to that same `return`, the `break-as-return`
    burden (see `_break_continue` below), so `early-exit` now names only
    a continue, a labeled break, or a break whose loop is not tail."""
    early = trailing = False
    for bstart, bend in _method_bodies(s):
        for m in re.finditer(r"\breturn\b", s[bstart:bend]):
            if _tail(s, bstart, bend, bstart + m.start(), bstart + m.end()):
                trailing = True
            else:
                early = True
    return early, trailing


_LOOP_KW = re.compile(r"\bwhile\b|\bfor\b")


def _loop_groups(s: str, bstart: int, bend: int) -> list[tuple[int, int]]:
    """(open, close) of the body brace group of every `while`/`for` loop
    header found in [bstart, bend): the first `{` after the header that is
    not `{:` (an invariant or decreases clause may itself carry an
    attribute), closed by `_brace_close`. Groups nest the way the source
    nests, so the innermost group containing a position is the one with the
    largest open index among those that contain it."""
    groups = []
    for m in _LOOP_KW.finditer(s, bstart, bend):
        i = m.end()
        while i < bend and s[i] != "{":
            i += 1
        if i >= bend:
            continue
        if s.startswith("{:", i):
            # an attribute on the header itself (rare); skip past it and
            # keep looking for the real body brace.
            j = _brace_close(s, i)
            while j < bend and s[j] != "{":
                j += 1
            if j >= bend:
                continue
            i = j
        groups.append((i, _brace_close(s, i)))
    return groups


def _break_continuation_refused(cont: str) -> bool:
    """True when the text after a break's innermost loop closes, up to (but
    not including) the method body's own closing brace, rules out a
    straight-line fall-through: another loop, a break or continue, or a
    return that is not the body's last statement. Pragmatic on the return
    check: a return is tail only when nothing but whitespace follows its
    `;` to the end of `cont` (which itself stops right before the body's
    closing brace)."""
    if _LOOP_KW.search(cont):
        return True
    if re.search(r"\bbreak\b|\bcontinue\b", cont):
        return True
    for m in re.finditer(r"\breturn\b", cont):
        semi = cont.find(";", m.end())
        if semi < 0 or cont[semi + 1:].strip():
            return True
    return False


def _breaks(s: str, bstart: int, bend: int, loops: list[tuple[int, int]]):
    """Yield (position, labeled, depth, continuation_refused) for every
    `break` in the body span, `labeled` true for `break <ident>` (not the
    bare `break;`). `depth` is the number of loop groups enclosing the
    break (0 if none, which should not happen in well-formed source);
    `continuation_refused` is only meaningful when depth == 1."""
    for m in re.finditer(r"\bbreak\b", s[bstart:bend]):
        p = bstart + m.start()
        rest = s[bstart + m.end():bend]
        labeled = re.match(r"\s*(" + IDENT + r")\b", rest) is not None
        containing = [g for g in loops if g[0] <= p < g[1]]
        depth = len(containing)
        refused = True
        if depth == 1:
            close = containing[0][1]
            refused = _break_continuation_refused(s[close:bend - 1])
        yield p, labeled, depth, refused


def _break_continue(s: str) -> bool:
    """A `continue`, a labeled break, or a break whose loop is not the tail
    of the method body (a break inside a nested loop, or followed by
    another loop): still outside t's fragment. An unlabeled break whose
    innermost loop IS the tail of the method body, with at most a
    straight-line continuation after it, lifts instead to t's early-exit
    `return` (the `break-as-return` burden below) -- LIFTER-DECISIONS.md
    row 23, 2026-09-09. `early-exit` (the gap) now names only the refused
    shapes."""
    for bstart, bend in _method_bodies(s):
        if re.search(r"\bcontinue\b", s[bstart:bend]):
            return True
        loops = _loop_groups(s, bstart, bend)
        for _p, labeled, depth, refused in _breaks(s, bstart, bend, loops):
            accepted = (not labeled) and depth == 1 and not refused
            if not accepted:
                return True
    return False


def _break_as_return(s: str) -> bool:
    """An unlabeled break whose innermost loop is the tail of the method
    body, with at most a straight-line continuation after it: lifts to t's
    early-exit `return` of the method's own result (LIFTER-DECISIONS.md
    row 23, 2026-09-09)."""
    for bstart, bend in _method_bodies(s):
        loops = _loop_groups(s, bstart, bend)
        for _p, labeled, depth, refused in _breaks(s, bstart, bend, loops):
            if not labeled and depth == 1 and not refused:
                return True
    return False


# An element assignment is a STATEMENT; the `:=` inside a functional update
# `m[k := v]` is not one. So anchor the left-hand side at the start of a
# statement, allow a dotted path and one or more bracket groups (`a[i]`,
# `arr[i][j]`), balance the brackets so an inner `s[hi]` cannot be taken for
# the end of the index, and allow the parallel form `a[i], a[j] := b, c`.
_BAL = r"(?:[^\[\]]|\[[^\[\]]*\])*"
_PATH = IDENT + r"(?:\s*\.\s*" + IDENT + r")*"
_IDX = r"(?:\[" + _BAL + r"\]\s*)"
_ARRAY_MUT = (r"(?:^|[;{}])\s*"
              r"(?:" + _PATH + r"\s*" + _IDX + r"*,\s*)*"
              + _PATH + r"\s*" + _IDX + r"+"
              r"(?:,\s*" + _PATH + r"\s*" + _IDX + r"*)*"
              r":=(?!=)")

# Decision 22 (LIFTER-DECISIONS.md row 22, SPEC.md "Sequences as values
# (v1)"): the base identifier of an element-assignment target (the same
# statement `_ARRAY_MUT` recognises, captured this time instead of just
# matched), used to count how many DISTINCT arrays a method mutates --
# more than one is refused (row 22: "more than one mutated array per
# method").
_ARRAY_MUT_TARGET = re.compile(
    r"(?:^|[;{}])\s*(" + IDENT + r")(?:\s*\.\s*" + IDENT + r")*\s*" + _IDX + r"+:=(?!=)", re.M)

# A declared `array<..>`/`array2<..>`/`array3<..>` type, one dimension
# marker (`2`/`3`/none), one nullability marker (`?`/none), one element
# type. `new int[n]`/`new nat[n]` never spells the type this way (no
# `<..>` at all -- element type and dimension are read off the `new`
# expression instead, `_NEW_ARRAY_RE` below), so this alone under-counts
# a bare `var b := new int[n];` local; `_array_shapes` folds both in.
_ARRAY_TYPE_RE = re.compile(r"\barray(2|3)?(\?)?\s*<\s*([^<>]*)\s*>")
# `new int[n]` / `new nat[n]`: one dimension (no `,` inside the bracket),
# not immediately followed by a second `[..]` (Dafny's jagged-array
# syntax, `new int[n][m]`, two allocations chained, not decision 22's
# shape either).
_NEW_ARRAY_RE = re.compile(r"\bnew\s+(" + IDENT + r")\s*\[([^\[\]]*)\](\s*\[)?")


def _array_shapes(s: str) -> tuple:
    """`(any_good, any_bad)`: whether SOME array-typed construct in `s`
    is decision 22's mapped shape (1D, `int` or `nat` elements, non
    -nullable -- read-only per decision 1, or mutated/allocated per
    decision 22) and whether some OTHER one is not (`array2`/`array3`,
    `array?<..>`, a non-int/non-nat element type, or a jagged/2D `new`).
    Approximate like every detector here: a type SYNTAX match, not a
    per-declaration usage analysis, so a file mixing a good and a bad
    array sets both flags (each independently true of ITS OWN
    declaration, never merged into one verdict)."""
    any_good = any_bad = False
    for m in _ARRAY_TYPE_RE.finditer(s):
        dims, nullable, inner = m.group(1), m.group(2), m.group(3).strip()
        if dims or nullable or inner not in ("int", "nat"):
            any_bad = True
        else:
            any_good = True
    for m in _NEW_ARRAY_RE.finditer(s):
        elem, inner, jagged = m.group(1), m.group(2), m.group(3)
        if elem not in ("int", "nat") or "," in inner or jagged:
            any_bad = True
        else:
            any_good = True
    return any_good, any_bad


def _array_mutation_refused(s: str) -> bool:
    """Decision 22's own refusal shapes, approximated: no element
    assignment at all means this gap has nothing to say (row 1's
    read-only condition is `array-as-seq`'s business, below, not this
    one's); otherwise refused when MORE THAN ONE distinct array is
    mutated in the method (`_ARRAY_MUT_TARGET`'s distinct base
    identifiers), when a `multiset` wraps a whole-array slice (row 22:
    "multiset ... stay refused", Clover_bubble_sort's own
    `multiset(a[..])==multiset(old(a[..]))`), or when a `modifies`
    clause names anything but exactly one bare identifier (`modifies
    this`, `modifies a, b`, `modifies obj.arr` -- row 22: "any modifies
    clause naming something other than the one array")."""
    if not re.search(_ARRAY_MUT, s, re.M):
        return False
    if _has(r"\bmultiset\s*\(")(s) and re.search(r"\[\s*\.\.\s*\]", s):
        return True
    names = {m.group(1) for m in _ARRAY_MUT_TARGET.finditer(s)}
    if len(names) > 1:
        return True
    for m in re.finditer(r"\bmodifies\b([^\n{;]*)", s):
        clause = re.split(r"\b(?:requires|ensures|invariant|decreases|modifies|reads)\b",
                          m.group(1))[0]
        parts = [p.strip() for p in clause.split(",") if p.strip()]
        if len(parts) != 1 or not re.fullmatch(IDENT, parts[0]):
            return True
    return False


def _lambda(s: str) -> bool:
    for m in re.finditer(r"(?<![=<>!])=>", s):
        line = s[s.rfind("\n", 0, m.start()) + 1:m.start()]
        if not re.search(r"\bcase\b", line):
            return True
    # Dafny's arrow types `->`, `-->`, `~>`, with or without spaces around
    # them (`nat->nat` is one). No other token in masked Dafny source has a
    # `-` or `~` immediately followed by `>`: a subtraction spells its `>`
    # after an operand.
    return re.search(r"-+>|~>", s) is not None


def _method_count(s: str) -> int:
    return len(re.findall(r"\bmethod\b(?!\s+Main\b)", s))


def _multi_method_shapes(s: str) -> tuple:
    """(any_burden, any_gap): measured (a read-only pass over the
    census-gradable 643, 2026-09-09), 27 of 34 AST-analysed
    multi-method files (79 percent) have methods that never call each
    other, and the lifter already lifts one task per gradable method
    (decision 9) -- so more than one graded method (`Main` excluded) is
    the burden `multi-method-independent` UNLESS some method's own body
    calls ANOTHER declared method by name (an identifier immediately
    followed by `(` matching a DECLARED `method` name other than its
    own; a function or lemma call is not this row's business, an
    ordinary spec_fun/lemma application every single-method file
    already has), which keeps `multi-method` the gap it always was --
    a call across methods is a real packaging question (which one is
    "the" task, and what a cross-call even means once each is lifted
    separately) decision 9 never answered. Approximate like
    `_mutual_recursion`'s own per-declaration body scan: one graded
    method calling itself (self-recursion) is not "another" method and
    is excluded from the call set."""
    names = [nm for kw, nm, j in _declarations(s) if kw == "method" and nm != "Main"]
    if len(names) <= 1:
        return False, False
    name_set = set(names)
    calls_other = False
    for kw, nm, j in _declarations(s):
        if kw != "method" or nm == "Main":
            continue
        b = _OPEN_BRACE.search(s, j)
        if b is None:
            continue
        e = _delim_close(s, b.start(), "{", "}")
        body = s[b.start():e if e > 0 else len(s)]
        others = name_set - {nm}
        if any(re.search(r"\b" + re.escape(o) + r"\s*\(", body) for o in others):
            calls_other = True
            break
    return (not calls_other), calls_other


def _split_top_level_commas(text: str) -> list:
    """`text` split at its own top-level commas, `(..)`/`<..>` nesting
    (a tuple type, a generic type argument list) tracked as one combined
    depth so neither can end the other's group early -- unlike
    `_multi_return`'s own fixed-point `(..)`/`<..>` STRIP (which answers
    only "is there a top-level comma at all" and, doing so, also erases
    everything a type argument list carries, `seq<int>` down to `seq`),
    this keeps every character, so a caller can read each slot's own
    type text back out whole."""
    parts, depth, cur = [], 0, []
    for ch in text:
        if ch in "(<":
            depth += 1
        elif ch in ")>":
            depth -= 1
        if ch == "," and depth <= 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return parts


def _pair_component_supported(ty: str) -> bool:
    """Row 29 (2026-09-09, SPEC.md "Pairs (v1)"): the lexical read of
    `lift_classify._pair_component_issue`'s accepted set -- int, nat,
    bool, string, or seq<int|nat|char> -- read off the text after a
    `returns(...)` slot's own LAST top-level ':' (`name: Type`; a slot's
    own Type never itself contains a top-level ':', so this is exact,
    not approximate, GIVEN the type text `_split_top_level_commas`
    handed back is well-formed Dafny). A bare `char`, an `array<..>`, a
    bitvector, `real`, `map`/`multiset`, a nested Dafny tuple, or an
    unrecognised spelling (a generic type parameter, a type synonym) all
    read as unsupported -- an UNDER-count of the burden in that last
    case, the same direction `_zero_return_shapes`/`_array_shapes`
    already accept elsewhere."""
    ty = ty.strip()
    if re.fullmatch(r"int|nat|bool|string", ty):
        return True
    if re.fullmatch(r"seq\s*<\s*(?:int|nat|char)\s*>", ty):
        return True
    return False


def _multi_return_shapes(s: str) -> tuple:
    """(any_pair_burden, any_arity_gap): LIFTER-DECISIONS.md row 29
    (2026-09-09) lifts a method with EXACTLY two return values, both
    components one of the types `_pair_component_supported` accepts, to
    one pair-typed return -- the burden `multi-return-pair`. Three or
    more return values, or a two-return method with an unsupported
    component (array, bitvector, real, map, multiset, a nested Dafny
    tuple, a bare char), stays the gap `multi-return-arity` (the same
    token `lift_classify`'s own arity refusal uses; an unsupported
    COMPONENT reads `multi-return-nested` there, but this census key
    only ever draws the one line the row 29 task's own instructions
    named: pair-of-two-supported is the burden, everything else about a
    `multi-return` shape stays this one gap). Per `returns(...)`
    occurrence in the file, `_multi_return`'s own scanning shape,
    unaffected by which method it belongs to (approximate, per-file, the
    same reading every OTHER detector here that does not re-derive
    `_declarations` gives)."""
    any_burden = any_gap = False
    for m in re.finditer(r"\breturns\s*\(", s):
        depth, j = 1, m.end()
        while j < len(s) and depth:
            if s[j] == "(":
                depth += 1
            elif s[j] == ")":
                depth -= 1
            j += 1
        if depth:
            continue
        inner = s[m.end():j - 1]
        parts = [p for p in _split_top_level_commas(inner) if p.strip()]
        if len(parts) <= 1:
            continue
        if len(parts) >= 3:
            any_gap = True
            continue
        ok = True
        for part in parts:
            colon = part.rfind(":")
            ty = part[colon + 1:] if colon >= 0 else ""
            if not _pair_component_supported(ty):
                ok = False
                break
        if ok:
            any_burden = True
        else:
            any_gap = True
    return any_burden, any_gap


_SEQ_SYNONYM = re.compile(r"^[^\S\n]*type\s+(" + IDENT + r")\s*(?:<[^<>\n]*>)?\s*=\s*seq\s*<", re.M)
_FUN_HEAD = re.compile(r"\b(?:function|predicate)\b(?:\s+method\b)?\s*(?:\{:[^{}]*\}\s*)*"
                       + IDENT + r"\s*(?:<[^<>\n]*>)?\s*\(")


def _expand_seq_synonyms(s: str) -> str:
    """`type intStack = seq<int>` spells a sequence under another name; rewrite
    each such name to a plain seq type so the seq detectors can see it."""
    for name in _SEQ_SYNONYM.findall(s):
        s = re.sub(r"\b" + re.escape(name) + r"\b", "seq<int>", s)
    return s


def _close_paren(s: str, i: int) -> int:
    """Index of the `)` matching the `(` at i, or -1 when it is unmatched."""
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "(":
            depth += 1
        elif s[j] == ")":
            depth -= 1
            if depth == 0:
                return j
    return -1


def _seq_return(s: str) -> bool:
    # A method `returns (r: seq<..>)` or a function whose result type is a
    # sequence, written `f(..): seq<int>` or `f(..): (r: seq<int>)`; both
    # after `type NAME = seq<..>` synonyms are expanded.
    s = _expand_seq_synonyms(s)
    if re.search(r"\breturns\s*\([^)]*:\s*seq\b", s):
        return True
    if re.search(r"\)\s*:\s*seq\s*<", s):
        return True
    result = re.compile(r"\s*:\s*(?:\(\s*" + IDENT + r"\s*:\s*)?seq\b")
    for m in _FUN_HEAD.finditer(s):
        j = _close_paren(s, m.end() - 1)
        if j >= 0 and result.match(s, j + 1):
            return True
    return False


_ENS_DECL_KW = re.compile(r"\b(?:method|function|predicate|lemma|constructor"
                          r"|iterator|class|trait|module|(?:co)?datatype"
                          r"|newtype|type|const)\b")


def _paren_end(s: str, i: int) -> int:
    """Index just past the `)` that closes the `(` at i, or -1."""
    depth = 0
    while i < len(s):
        if s[i] == "(":
            depth += 1
        elif s[i] == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


def _brace_end(s: str, i: int) -> int:
    """Index just past the `}` that closes the `{` at i, or -1."""
    depth = 0
    while i < len(s):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


# A `{` that follows one of these is an operand, so a set or map literal in a
# spec clause, not the start of a body. `*` and `|` are left out on purpose:
# `decreases *` and `decreases |s|` are clause ends followed by a real body.
_LITERAL_LEAD = re.compile(r"(?:[=!<+\-,(:&]|\bin)\s*$")


def _body_brace(s: str, i: int) -> int:
    """Index of the `{` that opens a body, scanning from i, or -1. Skips a
    `{:attr}` and a set or map literal written inside a spec clause (a brace
    group that follows an operator and holds no statement separator)."""
    while True:
        j = s.find("{", i)
        if j < 0:
            return -1
        if s[j:j + 2] == "{:":
            i = j + 1
            continue
        k = _brace_end(s, j)
        if (k > 0 and ";" not in s[j:k]
                and _LITERAL_LEAD.search(s[max(0, j - 60):j])):
            i = k
            continue
        return j


def _method_with_ensures(s: str) -> bool:
    """A non-Main method whose OWN spec carries an ensures. The spec is the
    text between the signature (the parameter list, and `returns (..)` when
    there is one) and the body `{`, cut short at the next declaration
    keyword so a body-less method cannot borrow the clauses of whatever
    follows it. An ensures on a function or on a lemma does not make a
    program gradable: what a kernel grades is the method's postcondition,
    and a method with no ensures of its own states nothing to verify.

    A set or map literal written in a spec clause is stepped over, so a
    `requires x in {1, 2}` does not hide the `ensures` behind it."""
    for m in re.finditer(r"\bmethod\b", s):
        if re.search(r"\b(?:function|predicate)\s+$", s[max(0, m.start() - 12):m.start()]):
            continue  # `function method` / `predicate method`, not a method
        head = re.match(r"\s*(?:\{:[^}]*\}\s*)*(" + IDENT + r")", s[m.end():])
        if head is not None and head.group(1) == "Main":
            continue
        i = s.find("(", m.end())
        if i < 0:
            continue
        i = _paren_end(s, i)
        if i < 0:
            continue
        r = re.match(r"\s*returns\s*\(", s[i:])
        if r:
            i = _paren_end(s, i + r.end() - 1)
            if i < 0:
                continue
        end = len(s)
        body = _body_brace(s, i)
        if body >= 0:
            end = body
        nxt = _ENS_DECL_KW.search(s, i)
        if nxt and nxt.start() < end:
            end = nxt.start()
        if re.search(r"\bensures\b", s[i:end]):
            return True
    return False


# Nondeterministic choice t cannot express: havoc `x := *`, a nondeterministic
# guard `if *` / `while *` / `if (*)`, and the guarded-alternative statement
# `if { case g => s }` / `if case g => s` (whose `case` used to be read as a
# datatype match).
_NONDET = re.compile(r":=\s*\*|\b(?:if|while)\s*(?:\{\s*)?case\b"
                     r"|\b(?:if|while)\s*\(?\s*\*")

_SUCH_DECL_KW = re.compile(r"\b(method|constructor|lemma|function|predicate|iterator)\b")
_SUCH_THAT = re.compile(r"(?<!:):\|")


def _such_that_sites(s: str) -> list[bool]:
    """One flag per assign-such-that `:|`: True when it is EXECUTABLE, that
    is nondeterministic choice in compiled code (its enclosing declaration
    is a non-ghost method or constructor and its statement is neither a
    `ghost var` nor the ghost-only `:| assume P` form), False when it is
    proof scaffolding (a lemma, a let-such-that in a function, a ghost
    declaration, a ghost variable, `:| assume`). A `::` followed by a
    cardinality bar (`forall i :: |s| > 0`) is not an assign-such-that and
    is skipped."""
    decls = []
    for m in _SUCH_DECL_KW.finditer(s):
        pre = s[max(0, m.start() - 24):m.start()]
        ghost = re.search(r"\bghost\s+$", pre) is not None
        # `function method` / `predicate method` declares a function, so its
        # `method` keyword must not be read as a method declaration.
        fn_method = re.search(r"\b(?:function|predicate)\s+$", pre) is not None
        decls.append((m.start(), m.group(1), ghost, fn_method))
    sites = []
    for m in _SUCH_THAT.finditer(s):
        prev = [d for d in decls if d[0] < m.start()]
        if not prev:
            sites.append(False)
            continue
        _, kw, ghost_decl, fn_method = prev[-1]
        cut = max(s.rfind(c, 0, m.start()) for c in ";{}")
        stmt = s[cut + 1:m.start()]
        sites.append(kw in ("method", "constructor") and not ghost_decl
                     and not fn_method
                     and re.search(r"\bghost\b", stmt) is None
                     and re.match(r"\s*assume\b", s[m.end():]) is None)
    return sites


def _skip_ws(s: str, j: int) -> int:
    """Past whitespace and {:attribute} groups, from j."""
    while j < len(s):
        if s[j] in " \t\r\n":
            j += 1
        elif s.startswith("{:", j):
            k = s.find("}", j)
            if k < 0:
                return j
            j = k + 1
        else:
            break
    return j


def _delim_close(s: str, i: int, op: str = "(", cl: str = ")") -> int:
    """The index just past the delimiter matching the one at i, or -1."""
    depth = 0
    while i < len(s):
        if s[i] == op:
            depth += 1
        elif s[i] == cl:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


_BODY_DECL_KW = re.compile(r"\b(?:method|function|predicate|lemma|constructor|datatype"
                           r"|codatatype|class|trait|module|import|include|iterator"
                           r"|newtype|type|const|ghost|least|greatest|twostate"
                           r"|inductive|export)\b")
_OPEN_BRACE = re.compile(r"\{(?!:)")


def _declarations(s: str) -> list:
    """(keyword, name, header end) for every method, function and predicate
    declaration; the header end is just past the parameter list, so what
    follows is the result type, the specification clauses and the body."""
    out = []
    for m in re.finditer(r"\b(method|function|predicate)\b", s):
        kw = m.group(1)
        pre = re.search(r"(" + IDENT + r")\s*$", s[:m.start()])
        if kw == "method" and pre and pre.group(1) in ("function", "predicate", "by"):
            continue                              # function method, by method
        j = _skip_ws(s, m.end())
        if kw != "method" and re.match(r"method\b", s[j:]):
            j = _skip_ws(s, j + len("method"))     # function method f(..)
        name = re.match(IDENT, s[j:])
        if not name:
            continue
        j = _skip_ws(s, j + name.end())
        if j < len(s) and s[j] == "<":             # type parameters
            k = s.find(">", j)
            if k < 0:
                continue
            j = _skip_ws(s, k + 1)
        if j < len(s) and s[j] == "(":
            j = _delim_close(s, j)
            if j < 0:
                continue
        out.append((kw, name.group(0), j))
    return out


def _has_body(s: str, j: int) -> bool:
    """A declaration whose header ends at j has a body when its `{` comes
    before the next declaration keyword; in between are the result type and
    the requires / ensures / reads / modifies / decreases clauses."""
    r = re.match(r"\s*returns\s*\(", s[j:])
    if r:                                  # returns (ghost m: int, p: int)
        k = _delim_close(s, j + r.end() - 1)
        if k > 0:
            j = k
    b = _OPEN_BRACE.search(s, j)
    if b is None:
        return False
    k = _BODY_DECL_KW.search(s, j)
    return k is None or b.start() < k.start()


def _bodyless(s: str, want_method: bool) -> bool:
    return any(not _has_body(s, j) for kw, _, j in _declarations(s)
               if (kw == "method") == want_method)


def _zero_return_shapes(s: str) -> tuple:
    """(any_burden, any_gap): measured (a read-only pass over the
    census-gradable 643, 2026-09-09), every one of `zero-returns`'
    25 sole-blocker files is a method with no return that mutates
    exactly one array parameter under `modifies` -- LIFTER-DECISIONS.md
    row 22's "modifies-param" shape, which already lifts (a fresh seq
    return). So a zero-return, non-Main method whose OWN `modifies`
    names exactly one array parameter (one clause, one bare identifier)
    and whose OWN body mutates only that one name is the burden
    `zero-returns-array`, "a method with no return whose effect is its
    one array, lifted as a seq return by row 22"; every OTHER
    zero-return method (no array effect at all, a lemma written as a
    method, one that only prints) keeps `zero-returns` a gap.
    Approximate and per-declaration, `_array_shapes`'s own pattern: a
    DIFFERENT method in the same file may be the one whose modifies
    clause or mutation shape fails this row's own conditions
    (`_array_mutation_refused`'s per-file reading, narrowed here to
    the one zero-return method's own header and body)."""
    any_burden = any_gap = False
    for kw, nm, j in _declarations(s):
        if kw != "method" or nm == "Main":
            continue
        if re.match(r"\s*returns\b", s[j:]):
            continue
        b = _OPEN_BRACE.search(s, j)
        if b is None or not _has_body(s, j):
            any_gap = True
            continue
        header = s[j:b.start()]
        e = _delim_close(s, b.start(), "{", "}")
        body = s[b.start():e if e > 0 else len(s)]
        mods = re.findall(r"\bmodifies\b([^\n{;]*)", header)
        if len(mods) != 1:
            any_gap = True
            continue
        clause = re.split(r"\b(?:requires|ensures|invariant|decreases|modifies|reads)\b",
                           mods[0])[0]
        parts = [p.strip() for p in clause.split(",") if p.strip()]
        if len(parts) != 1 or not re.fullmatch(IDENT, parts[0]):
            any_gap = True
            continue
        target = parts[0]
        mut_names = {m.group(1) for m in _ARRAY_MUT_TARGET.finditer(body)}
        bad_multiset = _has(r"\bmultiset\s*\(")(body) and re.search(r"\[\s*\.\.\s*\]", body)
        if mut_names and mut_names == {target} and not bad_multiset:
            any_burden = True
        else:
            any_gap = True
    return any_burden, any_gap


def _mutual_recursion(s: str) -> bool:
    """Two spec functions that call each other, directly or around a chain.
    A t spec_fun may call itself and EARLIER spec_funs only, so a cycle of
    length two or more has no rendering; a plain forward call is only a
    declaration order to undo, and is not tagged."""
    bodies = []
    for kw, name, j in _declarations(s):
        if kw == "method" or not _has_body(s, j):
            continue
        b = _OPEN_BRACE.search(s, j)
        e = _delim_close(s, b.start(), "{", "}")
        bodies.append((name, s[b.start():e if e > 0 else len(s)]))
    names = [n for n, _ in bodies]
    calls = {n: set() for n in names}
    for n, body in bodies:
        for other in names:
            if other != n and re.search(r"\b" + re.escape(other) + r"\s*\(", body):
                calls[n].add(other)
    for start in calls:
        seen, front = set(), list(calls[start])
        while front:
            u = front.pop()
            if u == start:
                return True
            if u not in seen:
                seen.add(u)
                front.extend(calls.get(u, ()))
    return False


_COMPREHENSION = ("forall", "exists", "set", "iset", "multiset", "map",
                  "imap", "case")

# A generic argument list `<T, seq<U>>`: only type-shaped characters, so that
# a `<` that is a less-than (`i < n && n > 0`) does not open one. Its commas
# belong to the type, not to any tuple around it.
_GENERIC = re.compile(r"<[A-Za-z0-9_'?!=,.\s()\[\]<>]*>")

# The head of a quantifier or a comprehension, `forall i, j ::` or
# `set x, y | .. ::`: those commas separate bound variables, so they belong to
# the binder and not to any parenthesis around it.
_BINDER = re.compile(r"\b(?:forall|exists|set|iset|multiset|imap|map)\s+"
                     + IDENT + r"[^;{}]*?::")


def _numeric_destructors(s: str) -> set:
    """Field names a datatype constructor declares as plain numbers, as in
    `C3(3: int, 0: int, 1: int, c3: int)`. For such a file `k.3` is a
    destructor call, not a tuple projection."""
    names = set()
    for m in re.finditer(r"\b(?:co)?datatype\b", s):
        decl = re.split(r"\n\s*\n|\b(?:method|function|predicate|lemma|class"
                        r"|trait|module|newtype|iterator)\b", s[m.end():], 1)[0]
        names |= set(re.findall(r"[(,|]\s*(\d+)\s*:(?!=)", decl))
    return names


def _tuple(s: str) -> bool:
    """A tuple pattern `var (a, b) :=`, a tuple type or literal (a
    parenthesised group holding a comma of its own, one nested in no other
    bracket), or a `.0` projection. Not a tuple: a group after an
    identifier, `]` or `)` (a call or an index, so every parameter and
    argument list), a group after a `.` (the datatype update
    `x.(f := e, g := e)`), a group followed by `->` or `~>` (the argument
    list of a function type), the head of a comprehension or a quantifier,
    the bound variables of a quantifier or a comprehension anywhere inside
    it, and a `.0` whose number is a datatype field name."""
    if re.search(r"\bvar\s*\([^()]*,", s):
        return True
    bound = set()
    for m in _BINDER.finditer(s):
        bound.update(k for k in range(m.start(), m.end()) if s[k] == ",")
    close = {")": "(", "]": "[", "}": "{"}
    stack = []
    for i, ch in enumerate(s):
        if ch in "([{":
            stack.append([ch, i, False])
        elif ch == "<" and i and (s[i - 1].isalnum() or s[i - 1] in "_'") \
                and _GENERIC.match(s, i):
            stack.append(["<", i, False])
        elif ch == ">" and stack and stack[-1][0] == "<":
            stack.pop()
        elif ch == "," and stack and i not in bound:
            stack[-1][2] = True
        elif ch in close:
            group = None
            while stack:
                top = stack.pop()
                if top[0] == close[ch]:
                    group = top
                    break
            if group is None or ch != ")" or not group[2]:
                continue
            j = group[1]
            pre = s[:j].rstrip()
            if not pre.endswith(("=>", "->", "~>")):
                if pre and (pre[-1].isalnum() or pre[-1] in "_'>)]."):
                    continue
            head = re.match(r"\s*(" + IDENT + r")", s[j + 1:i])
            if head and head.group(1) in _COMPREHENSION:
                continue
            if re.match(r"\s*(?:->|~>|=>)", s[i + 1:]):
                continue
            return True
    numeric = _numeric_destructors(s)
    for m in re.finditer(r"(?<=[A-Za-z_)\]])\.(\d)\b", s):
        if m.group(1) not in numeric:
            return True
    return False


# ---------------------------------------------------------------- row 28
# LIFTER-DECISIONS.md row 28 (2026-09-09, SPEC.md "Strings as sequences of
# code points (v1)"): a Dafny `char` is a t int, a `string` a t `seq` of
# them, so the single `string-char` gap this file used to raise on any
# `string`/`char`/`seq<char>` type or literal splits the way
# `t/nl_census.py` already splits its own string gap -- `string-as-seq`
# (a BURDEN: literals, `|s|`, indexing, `+`, a slice, `==`/`!=`,
# `<`/`<=`/`>`/`>=` between two chars, `as int`, all already in t's
# fragment via the seq machinery rows 25-27 landed) versus `string-lib`
# (a GAP: what still needs a string library or char arithmetic t does not
# have). `string-lib`'s own two lexical signals: an order comparison
# adjacent to a string LITERAL (measured on dafny 4.11.0, t6.dfy/t6run.dfy
# in the task's own scratch notes: `<`/`<=`/`>`/`>=` on `string`/`seq<char>`
# is PROPER-PREFIX semantics, not lexicographic as a first guess -- and a
# first guess this file's own author also made, per
# AssertivePrograming_tmp_tmpwf43uz0e_Find_Substring.dfy's own comment,
# "`<=` on sequences is the prefix relation" -- but still not an operator
# t has on seqs either way, SPEC.md: "Lexicographic order on strings is
# not an operator"), and multiset/set of char. Lexical and approximate
# like every detector here, and UNDER-counts on purpose in the same
# direction `seq-concat` already does: an order comparison between two
# BARE string-typed NAMES with no literal on either side (`s1 < s2`) is
# invisible to it, since telling `s1`/`s2` are string-typed at all needs
# the lifter's own type knowledge (`lift_classify.expr_kind`), not a
# lexical scan. `s in t` (a substring test) needs no detector: measured
# directly (t7.dfy) NOT to type-check in Dafny at all when both sides are
# string ("expecting element type to be assignable to char (got
# string)"), so it cannot occur in a verified corpus program. A nested
# string (`seq<string>`, `seq<seq<char>>`) is already the EXISTING
# `nested-seq` gap's own territory (its regex already matches `seq<` not
# followed by `int`/`nat`), unchanged by this row. `char-arith` (the
# actual `c + 1`-shaped construct, decision-vocabulary's own name) is
# unaffected: its regex predates this row and is not part of this split.
_STRING_ORDER_CMP = re.compile(r'"[^"]*"\s*(?:<=|>=|<|>)|(?:<=|>=|<|>)\s*"[^"]*"')
_STRING_SET_KIND = re.compile(r"\b(?:multiset|set|iset)\s*<\s*char\s*>")


def _string_lib(s: str) -> bool:
    return bool(_STRING_ORDER_CMP.search(s)) or bool(_STRING_SET_KIND.search(s))


DETECTORS: dict[str, tuple[str, object, str]] = {
    # gaps: outside t's fragment
    # Decision 22 (LIFTER-DECISIONS.md row 22, 2026-09-09): an
    # `array<int>`/`array<nat>` (one dimension, non-nullable) is now
    # in-fragment -- read-only per decision 1, mutated in place under
    # `modifies`, or allocated and filled -- so `array` narrows to the
    # shapes that still are not: `array2`/`array3`, `array?<..>`, and
    # non-int/non-nat element types. `array-mutation` narrows the same
    # way, to the mutation shapes decision 22 does not map (more than
    # one mutated array, `multiset` over a mutated array's slice, a
    # `modifies` clause naming anything but the one array); the mapped
    # ones (single mutated array, single `modifies` target, or an
    # allocate-and-fill) are `array-as-seq`, a burden now, like decision
    # 1's read-only row always should have been but never had a name for.
    "array": ("gap", lambda s: _array_shapes(s)[1], "array2/array3, array?<..> (nullable), or a non-int/non-nat element type"),
    "array-mutation": ("gap", _array_mutation_refused, "array mutation decision 22 does not map: more than one mutated array, multiset over a mutated array's slice, or a modifies clause naming anything but the one array"),
    # div-mod (`/`, `%` on int) is in t's fragment since SPEC.md's
    # "Division and modulo (v1)" (2026-09-08): Dafny's own `/` and `%`
    # are Euclidean too, measured, so the lifter maps them one to one
    # with no domain restriction. Like the other in-fragment binary
    # operators (`+`, `-`, `*`, ...), it carries no detector here.
    "string-lib": ("gap", _string_lib, "the string LIBRARY t's v1 seq-of-code-points model does not cover: an order comparison (<, <=, >, >=) adjacent to a string literal (measured proper-prefix, not lexicographic, but still not a t operator on seqs either way), or multiset/set of char -- lexical and approximate, UNDER-counts an order comparison between two bare string-typed names with no literal on either side (see the comment above _string_lib)"),
    "set": ("gap", _set, "set, iset, multiset, set comprehension or set literal"),
    "map": ("gap", _has(r"\bi?map<|\bmap\s+" + IDENT + r"\s*(?::|\|)|\bmap\s*\["), "map, imap, map comprehension or map literal"),
    "heap": ("gap", _has(r"\bclass\b|\btrait\b|\bfresh\b|\bthis\b|\bnew\s+" + IDENT + r"\s*[(;]"), "classes, object allocation, this"),
    "datatype": ("gap", _has(r"\b(?:co)?datatype\b|\bmatch\b"), "algebraic datatypes and match"),
    "nondet": ("gap", lambda s: _NONDET.search(s) is not None, "nondeterministic choice: havoc x := *, if *, while *, guarded alternatives if { case }"),
    "multi-method": ("gap", lambda s: _multi_method_shapes(s)[1], "more than one graded method (Main excluded) where some method's body calls ANOTHER declared method by name -- decision 9 lifts one task per method, so independent methods (no cross-call) are the burden multi-method-independent, not this gap"),
    # Row 29 (2026-09-09, SPEC.md "Pairs (v1)"): a `multi-return` shape
    # of exactly two, both components int/nat/bool/seq<int|nat|char>/
    # string, is now in-fragment -- LIFTER-DECISIONS.md row 29 lifts it
    # to one pair-typed return -- so `multi-return` narrows to
    # `multi-return-arity`, the SAME token that row's own classifier
    # refusal uses for three or more returns (an unsupported COMPONENT
    # at arity two also stays this gap here; the census draws only the
    # one line row 29's own task named, see `_multi_return_shapes`'s
    # docstring for the finer `multi-return-nested` reading the real
    # lifter gives that case). Key renamed to match; see the burden
    # `multi-return-pair`.
    "multi-return-arity": ("gap", lambda s: _multi_return_shapes(s)[1], "a method with more than one return value that t cannot map to one pair return -- three or more return values, or exactly two whose component types this lifter does not carry (array, bitvector, real, map, multiset, a nested Dafny tuple, a bare char) -- see the burden multi-return-pair"),
    "zero-returns": ("gap", lambda s: _zero_return_shapes(s)[1], "a method with no return value (t returns exactly one) that is not row 22's own modifies-param shape -- see the burden zero-returns-array"),
    "early-exit": ("gap", _break_continue, "a continue, a labeled break, or a break whose loop is not the tail of the method body (a break inside a nested loop, or followed by another loop)"),
    "seq-comprehension": ("gap", _has(r"\bseq\s*\("), "seq(n, i => e) -- t's fill is constant-valued, this is not (v1 gap, unlike rows 25-27)"),
    "nested-seq": ("gap", _has(r"\b(?:seq|array\d*)<\s*(?:seq|array\d*)<|\bseq<\s*(?!int\b|nat\b)" + IDENT), "a nested seq or array, or a seq of non-int elements"),
    "unbounded-quantifier": ("gap", _unbounded_quantifier, "quantifier without an int range"),
    "real": ("gap", _has(r"\breal\b|(?<![\w.])\d+\.\d+(?![\w.])"), "real numbers"),
    "bitvector": ("gap", _has(r"\bbv\d+\b|\bas\s+bv\d|(?<!&)&(?!&)|\^|<<"), "bit vectors or bitwise operators"),
    "higher-order": ("gap", _lambda, "lambdas or function types"),
    "generics": ("gap", _has(r"\b(?:method|function|predicate|lemma|(?:co)?datatype|class|trait|iterator)\s+(?:method\s+)?(?:\{:[^}]*\}\s*)*" + IDENT + r"\s*<"), "type parameters"),
    "tuple": ("gap", _tuple, "tuples"),
    "type-decl": ("gap", _has(r"^\s*(?:newtype|type)\s+" + IDENT), "newtype, type synonyms, subset types"),
    "io": ("gap", _has(r"\bprint\b|\bexpect\b"), "print or expect"),
    "iterator": ("gap", _has(r"\biterator\b"), "iterators"),
    "module": ("gap", _has(r"\bmodule\b|\bimport\b|\binclude\b"), "modules and imports"),
    "function-method": ("gap", _has(r"\bfunction\s+method\b|\bby\s+method\b|\bpredicate\s+method\b"), "compiled functions"),
    "bodyless-method": ("gap", lambda s: _bodyless(s, True), "a method declared without a body"),
    "bodyless-function": ("gap", lambda s: _bodyless(s, False), "an uninterpreted function or predicate: a declaration with no body, constrained only by axioms"),
    "extreme-predicate": ("gap", _has(r"\b(?:least|greatest)\s+predicate\b|\bcopredicate\b|\binductive\s+predicate\b"), "least / greatest predicate: an inductive or coinductive definition, not a well-founded recursion (least and greatest LEMMAS stay hints)"),
    "mutual-recursion": ("gap", _mutual_recursion, "spec functions that call each other (t allows self-calls and calls to earlier functions)"),
    "decreases-star": ("gap", _has(r"\bdecreases\s+\*"), "decreases * (a loop or call allowed not to terminate)"),
    "char-arith": ("gap", _has(r"\bas\s+char\b|\bchar\s*\("), "char arithmetic"),
    "such-that-exec": ("gap", lambda s: any(_such_that_sites(s)), "assign-such-that :| in executable code (nondeterministic choice)"),
    # burdens: t can say it another way
    # Row 28 (2026-09-09, SPEC.md "Strings as sequences of code points
    # (v1)"): `string-char`'s old regex, now a burden -- literals,
    # length, index, concat, slice, equality, char comparisons and `as
    # int` all lift (LIFTER-DECISIONS.md row 28); reclassified gap ->
    # burden, key renamed to match `t/nl_census.py`'s own `string-as-seq`
    # (`string-char`'s literal-forcing in `tag()` below renamed to match).
    "string-as-seq": ("burden", _has(r"\bstring\b|\bchar\b|\bseq<char>"), "a string or char used only the way t's seq of code points already covers: literals, |s|, indexing, +, a slice, ==/!=, char comparisons (<,<=,>,>=), as int -- SPEC.md 'Strings as sequences of code points', LIFTER-DECISIONS.md row 28"),
    "array-as-seq": ("burden", lambda s: _array_shapes(s)[0], "array<int>/array<nat> (one dimension): read-only, mutated in place under modifies, or allocated and filled -- lifts to seq (decision 1, decision 22)"),
    "zero-returns-array": ("burden", lambda s: _zero_return_shapes(s)[0], "a method with no return whose effect is its one array, lifted as a seq return by row 22 (LIFTER-DECISIONS.md row 22's modifies-param shape)"),
    "multi-method-independent": ("burden", lambda s: _multi_method_shapes(s)[0], "more than one graded method, none calling another by name -- decision 9 lifts one task per method, so no packaging decision is needed"),
    "multi-return-pair": ("burden", lambda s: _multi_return_shapes(s)[0], "exactly two return values, both int/nat/bool/seq<int|nat|char>/string -- lifts to one pair-typed return (LIFTER-DECISIONS.md row 29)"),
    # Rows 25-27 (2026-09-09, SPEC.md "Sequences: literals, concatenation,
    # slices (v1)"): a sequence literal, a slice and its two sugars, and a
    # seq-typed return all lift now (LIFTER-DECISIONS.md rows 25-27); a
    # functional update `s[i := v]` lifts too, as t's `update` (decision
    # 22 landed it 2026-09-09 morning, one row for the STATEMENT shape
    # `a[i] := e`, `_seq_update` here the EXPRESSION shape `s[i := v]`,
    # both now the same t operator). Reclassified gap -> burden, keys
    # unchanged so the tables stay comparable across the reclassification.
    "seq-return": ("burden", _seq_return, "sequence-valued return of a method or a function -- lifts as a seq return (LIFTER-DECISIONS.md rows 22/25-27)"),
    "seq-literal": ("burden", _seq_literal, "sequence literal [..] in an expression -- lifts to t's seq literal (LIFTER-DECISIONS.md row 25)"),
    "seq-slice": ("burden", _has(r"\[[^\]]*\.\.[^\]]*\]"), "slicing s[a..b], s[a..], s[..b] -- lifts to t's slice, sugars expanded (LIFTER-DECISIONS.md row 27)"),
    "seq-update": ("burden", _seq_update, "functional update s[i := v] -- lifts to t's update (LIFTER-DECISIONS.md decision 22/row 22, landed 2026-09-09 morning)"),
    # No detector fired on `+` between two seqs before rows 25-27 (t had
    # no seq concatenation to measure against); this one is lexical and
    # approximate on purpose -- `+ [`, `] +`, or `..] +` -- so it UNDER
    # -COUNTS: `r := a + b;` between two bare seq-typed names (no bracket
    # adjacent to the `+` at all) never matches, only a `+` next to a
    # display or a slice does. A real count needs the lifter's own type
    # knowledge (`lift_classify.expr_kind`), not a lexical scan; this
    # detector names the burden's LOWER bound, not its true size.
    "seq-concat": ("burden", _has(r"\+\s*\[|\]\s*\+|\.\.\s*\]\s*\+"), "+ on two seqs (concatenation) -- lifts to t's own + (LIFTER-DECISIONS.md row 26); lexical and approximate, UNDER-counts (see comment above)"),
    "nat": ("burden", _has(r"\bnat\b"), "nat, as int with a >= 0 clause"),
    "for-loop": ("burden", _has(r"\bfor\s+" + IDENT + r"\s*:="), "for loop (a while with a bound)"),
    "iff": ("burden", _has(r"<==>"), "<==> (== on bools)"),
    "seq-membership": ("burden", _has(r"\b!?in\b"), "in / !in (a bounded exists over a seq; set and map membership are their own gaps)"),
    "as-cast": ("burden", _has(r"\bas\s+(?:int|nat)\b"), "as int / as nat casts"),
    "parallel-assign": ("burden", _has(IDENT + r"\s*,\s*" + IDENT + r"\s*:=(?!=)"), "x, y := a, b (sequenced through a temporary)"),
    "untyped-var": ("burden", _has(r"\bvar\s+" + IDENT + r"\s*:="), "var without a type (t declares every type)"),
    "no-if-no-loop": ("burden", lambda s: not re.search(r"\bif\b|\bwhile\b", s), "straight-line body: the twin ladder has only its extensional operators to try"),
    "frame-clause": ("burden", _has(r"\bmodifies\b|\breads\b"), "modifies / reads (array frames when no class is present)"),
    "trailing-return": ("burden", lambda s: _returns(s)[1], "a return as the last statement (assign the result instead)"),
    "early-return": ("burden", lambda s: _returns(s)[0], "a return that is not in tail position of a method body (lifts to t's early-exit `return` statement)"),
    "break-as-return": ("burden", _break_as_return, "an unlabeled break whose innermost loop is the tail of the method body, with at most a straight-line continuation after it (lifts to t's early-exit `return` of the method's own result, LIFTER-DECISIONS.md row 23)"),
    "main-harness": ("burden", _has(r"\bmethod\s+Main\b"), "a Main test harness (stripped before tagging)"),
    "while-no-decreases": ("burden", lambda s: any(
        "decreases" not in s[m.end():m.end() + 400].split("{", 1)[0]
        for m in re.finditer(r"\bwhile\b", s)), "a loop without its decreases (t requires one)"),
    "if-no-else": ("burden", lambda s: bool(re.search(r"\bif\b[^{]*\{", s)) and not re.search(r"\belse\b", s), "if without else"),
    "function-or-predicate": ("burden", _has(r"\bfunction\b|\bpredicate\b"), "pure functions, as spec_funs when first-order over int and seq"),
    "spec-only-quantifier": ("burden", _has(r"\bforall\b|\bexists\b"), "quantifiers (bounded ones are in t)"),
    # hints: proof scaffolding
    "assert": ("hint", _has(r"\bassert\b"), "assert statements"),
    "lemma": ("hint", _has(r"\blemma\b"), "lemmas"),
    "ghost": ("hint", _has(r"\bghost\b"), "ghost code"),
    "calc": ("hint", _has(r"\bcalc\b"), "calc proofs"),
    "forall-statement": ("hint", _has(r"^\s*forall\b[^:]*(?:ensures|\{)"), "forall statements"),
    "assume": ("hint", _has(r"\bassume\b"), "assume (unsound as a hint; refused by every t adapter)"),
    "reveal-opaque": ("hint", _has(r"\breveal\b|\bopaque\b"), "reveal / opaque"),
    "assign-such-that": ("hint", lambda s: any(not e for e in _such_that_sites(s)), "assign-such-that in a lemma, a function or on a ghost variable (the executable one is the such-that-exec gap)"),
    "attribute": ("hint", _has(r"\{:"), "attributes"),
    "ghost-var": ("hint", _has(r"\bghost\s+var\b"), "ghost variables"),
    "assert-by": ("hint", _has(r"\bassert\b[^;]*\bby\b"), "assert ... by { }"),
    "old": ("hint", _has(r"\bold(?:@" + IDENT + r")?\s*\("), "old() / old@L() (two-state; heap or array frames)"),
    # shape
    "has-method": ("shape", _has(r"\bmethod\b"), "at least one method"),
    "method-with-ensures": ("shape", _method_with_ensures, "a method carrying an ensures of its own (a function's or a lemma's does not count)"),
}

GAPS = [k for k, (kind, _, _) in DETECTORS.items() if kind == "gap"]


def tag(src: str) -> dict:
    masked, seen = mask(src)
    has_main = re.search(r"\bmethod\s+Main\b", masked) is not None
    if has_main:
        # mask() preserves offsets, so the Main span found on the masked
        # text names the same bytes of the source; literals inside Main
        # (print strings) must not tag the program either. The span is
        # blanked in the ORIGINAL source: rebuilding it from the masked text
        # would blank every literal in the file before the recount.
        span = main_span(masked)
        if span is not None:
            i, j = span
            _, seen = mask(src[:i] + blank(src[i:j]) + src[j:])
        masked = strip_main(masked)
    # SYNTAX.md: lemmas, assert, assume and calc are hints and never put a
    # program outside the fragment, so gaps and burdens are read from source
    # with the scaffolding blanked. The hint detectors themselves, and the
    # shape detectors, still read the whole text: a lemma has to be visible
    # to be counted as one.
    hintless = _mask_hints(masked)
    tags = {k: bool(fn(hintless if kind in ("gap", "burden") else masked))
            for k, (kind, fn, _) in DETECTORS.items()}
    tags["main-harness"] = has_main
    if seen["string_lit"] or seen["char_lit"]:
        # Row 28: any string/char literal is the burden `string-as-seq`
        # (t already has a t seq of code points to give it), not a gap on
        # its own -- `string-lib`'s own two signals (`_string_lib`) are
        # unaffected by mere literal presence.
        tags["string-as-seq"] = True
    tags["gaps"] = sorted(k for k in GAPS if tags[k])
    tags["in_fragment"] = (not tags["gaps"]) and tags["has-method"] and tags["method-with-ensures"]
    return tags


# -------------------------------------------------------------- families
def family(name: str) -> str:
    """The sub-corpus a DafnyBench file came from, read off its name."""
    head = name.split("_")[0]
    head = re.sub(r"\d+$", "", head) or head
    low = head.lower()
    if low.startswith("dafny-synthesis"):
        return "MBPP-DFY (dafny-synthesis)"
    if low.startswith("clover"):
        return "Clover"
    return "GitHub (" + head + ")"


def greedy(programs: list[dict]) -> list[tuple[str, int, int]]:
    """Open gates one at a time, each time the one that unlocks the most
    still-blocked programs; returns (gate, newly unlocked, cumulative)."""
    open_gates: set[str] = set()
    covered = sum(1 for p in programs if p["in_fragment"])
    steps = []
    remaining = [p for p in programs if not p["in_fragment"]
                 and p["has-method"] and p["method-with-ensures"]]
    while remaining:
        best, best_n = None, 0
        for g in GAPS:
            if g in open_gates:
                continue
            n = sum(1 for p in remaining if set(p["gaps"]) <= open_gates | {g})
            if n > best_n:
                best, best_n = g, n
        if best is None or best_n == 0:
            # no single gate unlocks anything: open the most frequent gap
            cnt = Counter(g for p in remaining for g in p["gaps"] if g not in open_gates)
            if not cnt:
                break
            best, best_n = cnt.most_common(1)[0][0], 0
        open_gates.add(best)
        unlocked = [p for p in remaining if set(p["gaps"]) <= open_gates]
        remaining = [p for p in remaining if p not in unlocked]
        covered += len(unlocked)
        steps.append((best, len(unlocked), covered))
    return steps


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus")
    ap.add_argument("--name", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    corpus = Path(a.corpus)
    files = sorted(corpus.glob("*.dfy"))
    if not files:
        print(f"no .dfy files under {corpus}", file=sys.stderr)
        return 2
    name = a.name or corpus.resolve().parent.parent.parent.name or corpus.name
    programs = []
    for f in files:
        t = tag(f.read_text(encoding="utf-8", errors="replace"))
        t["file"] = f.name
        t["family"] = family(f.name)
        programs.append(t)
    n = len(programs)
    graded = [p for p in programs if p["has-method"] and p["method-with-ensures"]]
    in_frag = [p for p in programs if p["in_fragment"]]
    gap_count = Counter(g for p in programs for g in p["gaps"])
    burden_count = Counter(k for p in programs for k, (kind, _, _) in DETECTORS.items() if kind == "burden" and p[k])
    hint_count = Counter(k for p in programs for k, (kind, _, _) in DETECTORS.items() if kind == "hint" and p[k])
    steps = greedy(programs)
    fam = defaultdict(lambda: [0, 0, 0])
    for p in programs:
        fam[p["family"]][0] += 1
        fam[p["family"]][1] += p["in_fragment"]
        fam[p["family"]][2] += p["has-method"] and p["method-with-ensures"]
    # Sole blocker counts only GRADABLE programs (a method with an ensures of
    # its own), the same population as in_frag and the greedy curve: a
    # lemma-only file or a method with no ensures is not unlocked by opening
    # its one gate.
    one_gap = Counter(p["gaps"][0] for p in graded if len(p["gaps"]) == 1)

    lines = []
    w = lines.append
    w(f"# t coverage census: {name} ({n} programs)")
    w("")
    w("What this corpus needs that t does not have, program by program, and")
    w("which gate opens the most programs. Lexical census, no kernel run; the")
    w("in-fragment count says a program's constructs fit SYNTAX.md, not that")
    w("seven kernels verify its t rendering. Method and detectors at the end.")
    w("")
    w("## Headline")
    w("")
    w(f"- programs: {n}; with a method carrying its own ensures (gradable): {len(graded)}")
    w(f"- in t's fragment today: **{len(in_frag)}** of {len(graded)} gradable "
      f"({100 * len(in_frag) / max(1, len(graded)):.1f}%)")
    w(f"- gradable programs blocked by exactly one gap: {sum(one_gap.values())}")
    w("")
    w("## Gaps, by programs that need them")
    w("")
    w("| gap | programs | sole blocker for (gradable) | meaning |")
    w("|---|---|---|---|")
    for g, c in gap_count.most_common():
        w(f"| {g} | {c} | {one_gap.get(g, 0)} | {DETECTORS[g][2]} |")
    w("")
    w("## Greedy gate order (open the gate that unlocks the most programs)")
    w("")
    w("| step | gate | newly unlocked | cumulative in fragment | of gradable |")
    w("|---|---|---|---|---|")
    for i, (g, k, cum) in enumerate(steps, 1):
        w(f"| {i} | {g} | {k} | {cum} | {100 * cum / max(1, len(graded)):.1f}% |")
    w("")
    mb = [p for p in programs if p["family"].startswith("MBPP")]
    if mb:
        mb_graded = [p for p in mb if p["has-method"] and p["method-with-ensures"]]
        w("")
        w(f"### The same order on the MBPP-DFY family alone ({len(mb_graded)} gradable, the LLM-shaped subset)")
        w("")
        w("| step | gate | newly unlocked | cumulative | of gradable |")
        w("|---|---|---|---|---|")
        for i, (g, k, cum) in enumerate(greedy(mb), 1):
            w(f"| {i} | {g} | {k} | {cum} | {100 * cum / max(1, len(mb_graded)):.1f}% |")
        w("")
    w("A step with 0 newly unlocked is a gate that unlocks nothing alone but")
    w("is the most frequent remaining gap; the programs it belongs to need")
    w("more than one gate.")
    w("")
    w("## By family")
    w("")
    w("| family | programs | gradable | in fragment |")
    w("|---|---|---|---|")
    for k, (tot, inf, gr) in sorted(fam.items(), key=lambda x: -x[1][0]):
        w(f"| {k} | {tot} | {gr} | {inf} |")
    w("")
    w("## Burdens (expressible at a translation cost)")
    w("")
    w("| burden | programs | meaning |")
    w("|---|---|---|")
    for g, c in burden_count.most_common():
        w(f"| {g} | {c} | {DETECTORS[g][2]} |")
    w("")
    w("## Hints (proof scaffolding a kernel may need; t has none)")
    w("")
    w("| hint | programs | meaning |")
    w("|---|---|---|")
    for g, c in hint_count.most_common():
        w(f"| {g} | {c} | {DETECTORS[g][2]} |")
    w("")
    w("## In fragment today")
    w("")
    for p in in_frag:
        w(f"- {p['file']}")
    w("")
    w("## Method")
    w("")
    w("Source is masked (comments, string and char literals blanked, their")
    w("presence recorded outside `{:attribute}` arguments and outside the")
    w("`method Main` harness, which is blanked in the ORIGINAL source so that")
    w("a literal elsewhere in the file is still recorded) and each detector is")
    w("a regular expression or a small scanner over the masked text;")
    w("`coverage_census.py` lists every one.")
    w("")
    w("Lexical detection is approximate in both directions: `+` on sequences")
    w("is not distinguished from `+` on integers (concatenation is not tagged,")
    w("so seq needs are under-counted) and `nat` is a burden not a gap. Where")
    w("one token means two things, the detector reads its context:")
    w("")
    w("- proof scaffolding is blanked before any gap or burden is read: whole")
    w("  lemma declarations, and `assert`, `assume` and `calc` statements.")
    w("  SYNTAX.md makes these hints, which never put a program outside the")
    w("  fragment, so a construct appearing only inside one is not counted;")
    w("  the hint rows below are counted on the unblanked text;")
    w("- a quantifier is unbounded when a bound variable carries a non-int")
    w("  declared type, or carries no int range on the variable itself (a bare")
    w("  `v`, not `v*v`) in the guard; membership `v in e` counts as a range,")
    w("  `v !in e` does not, and an equality `v == e` counts only when this")
    w("  file types `e` as an integer, by declaring the function it calls or")
    w("  the collection it indexes to return int or nat;")
    w("- `a[i] := e` is an element assignment only when the left-hand side")
    w("  starts a statement, so the `:=` inside a functional update")
    w("  `m[k := v]` is not one, and the index is bracket-balanced;")
    w("- `s[i := v]` is a sequence update only when its receiver is a slice,")
    w("  or is not named as a map, imap or multiset in a file that holds a")
    w("  sequence somewhere;")
    w("- a `[` opens a sequence display only when what precedes it is not an")
    w("  identifier, `]` or `)`, or is one of a fixed list of keywords")
    w("  (`then [0]`, `else []`, `return [];`);")
    w("- a brace group holding only identifiers or integers is a set display")
    w("  only in expression position: `predicate P() { false }` is a body;")
    w("- `case` alone does not prove a datatype, since a match always carries")
    w("  its `match` keyword; `if { case .. }` is the guarded-alternative")
    w("  statement and is tagged as nondeterminism instead;")
    w("- a return is early only when it is not in tail position of a `method`")
    w("  body; a return in a lemma, a function or a predicate is not an exit;")
    w("- `:|` is nondeterministic choice (a gap) in a non-ghost method or")
    w("  constructor and proof scaffolding (a hint) in a lemma, a function, a")
    w("  ghost declaration or the ghost-only `:| assume P` form;")
    w("- a program is gradable when a METHOD carries an ensures of its own:")
    w("  an ensures on a function, a lemma, a constructor or an iterator")
    w("  states nothing a kernel would grade about the method;")
    w("- a comma inside `(int, int)` or `map<K, V>` is part of one type, not a")
    w("  second return value, and such a group is a tuple only when no call,")
    w("  index, arrow type, datatype update or binder head claims it first;")
    w("- a real literal is a digit run, a dot and a digit run, never glued to")
    w("  an identifier or another dot, so `x.1.1` is a tuple projection;")
    w("- an arrow type is `->`, `-->` or `~>` with or without spaces, and a")
    w("  declaration is generic even when an attribute stands between the")
    w("  keyword and the name.")
    w("")
    w("A declaration with no body (an uninterpreted function, a method")
    w("signature), a method with no return value, a least or greatest")
    w("predicate, and spec functions in a call cycle are gaps of their own.")
    w("Every file's tag set is in the JSON beside this report when `--json` is")
    w("given, so any row can be checked against its source.")
    w("")
    out = Path(a.out) if a.out else None
    text = "\n".join(lines)
    if out:
        out.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {out}")
    else:
        print(text)
    if a.json:
        Path(a.json).write_text(json.dumps(programs, indent=1), encoding="utf-8", newline="\n")
        print(f"wrote {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
