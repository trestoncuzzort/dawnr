#!/usr/bin/env python3
"""t/surface.py - a surface syntax for t, and the parse-print round trip that
is the only reason it is allowed to exist.

SYNTAX.md carried `written:` lines beside every JSON example ("if x >= 0 { r
:= x } else { r := -x }") and said in the same breath that nothing parsed
them, because "a surface syntax would need its own verified parse-print
round-trip before its proofs meant anything". This file is that syntax and
that round trip. The deliverable is not the parser; it is the measurement
below.

WHAT IT IS. Pure notation over the existing AST. Nothing here adds, removes
or reinterprets a construct: the grammar is exactly SYNTAX.md's EBNF block,
and every production maps to one JSON node. There is no construct the
notation can say that the JSON cannot already say, and none the JSON can say
that the notation drops. `parse` is total on the printed language and partial
elsewhere; it type-checks nothing, because typing is check_wf's job in
fuzz_lower.py and the kernels' job after that. A surface syntax that quietly
accepted more than the AST would be a second, undocumented language.

THE ROUND TRIP, measured (2026-09-04, this file's --check):

  parse(print(t)) == t, canonical JSON, on 1628 of 1628 tasks. The corpus is
  the 11 committed tasks in t/tasks/ plus fuzz_lower.build_corpus over seeds
  1 through 7: 200 generated plus 19 hand-built probes per seed, 1574 in all,
  less the 16 that check_wf rejects, which carry constructs t does not have
  and are therefore not t tasks. 1432 of the 1628 are distinct by canonical
  form; the repeats are the 19 probes, which build_corpus emits once per seed.

  print(parse(text)) == text on the second pass for all 1628, so printing is
  idempotent and every task has one normal form in the notation.

  The 22 `written:` lines in SYNTAX.md parse, unedited, to the JSON they sit
  beside (two added 2026-09-09, one for the char and string literals below
  and one for sequence literals, concatenation and slices). That
  is the check that this grammar is the documented notation and not a new
  one that resembles it.

  8 of 8 shapes the notation must refuse are refused (REFUSALS, below):
  div, `and` at arity 1, a keyword used as a name, a chained comparison, `/`
  in the lexer, a comment, `tostr` (a keyword since 2026-09-11) used as a
  name, and a dot followed by an unknown string-library member.

  100000 of 100000 random ASTs round trip: --fuzz 20000 on each of the seeds
  1 through 5. That instrument samples the GRAMMAR, not t's semantics, and it
  is the one that found this file's only real defect (note 1 below). It is
  permanent, not scaffolding for this wave: a corpus can only exercise the
  shapes its generators emit, so the defect it found is one the 1628-task
  corpus structurally cannot contain, and the next such defect will be too.

  3 of 3 char/string literal probes (LITERALS, below; SPEC.md "Strings as
  sequences of code points (v1)") parse to the stated AST and reparse
  correctly from their own canonical print, which is never the literal
  text: `'a'` prints as `97`, `"ab" + "c"` as `[97, 98] + [99]`, `""` as
  `[]`. These are the one place in this file where the two passes above
  are deliberately over DIFFERENT text: the first pass is the invariant
  (a char or string literal parses to its code point(s)); the second, as
  always, is on the canonical text the first pass's AST prints to.

2026-09-11 (SPEC.md "The string library (v1)"): 17 members added (split,
join, tostr, count, find, strip, lstrip, rstrip, replace, lower, upper,
isdigit, isalpha, isupper, islower, startswith, endswith), a postfix
`.name(...)` on every member but `tostr` (a plain function like `len`) and
`join` (the notation's `sep.join(rows)` swaps the AST's own `(rows, sep)`
argument order, its receiver second, the one member where "receiver
first" does not hold). Measured: `python3 t/surface.py --check` with 6 new
`written:` lines (22 total) and the corpus grown by 3 committed tasks
(word_count, split_join, count_vowels) still round trips at 100%; see the
live counts the command itself prints, not the numbers frozen into this
docstring's 2026-09-04 paragraph above, which this wave did not re-measure.

TWO PLACES WHERE THE OBVIOUS NOTATION WOULD HAVE LOST INFORMATION, since
both are live in the corpus and both round trip only because they are
written differently:

  1. `{"int": -5}` and `{"op": "neg", "args": [{"int": 5}]}` are DIFFERENT
     AST nodes (6204 and 658 occurrences). Printing both as `-5` would make
     the round trip a coin flip. So a negative literal is `-5` and `neg` of a
     literal is `-(5)`: `neg` parenthesises its argument exactly when the
     argument's printed form STARTS WITH A DIGIT. The test is on the text
     and not on the node because `neg` of `at` on a literal base prints
     `18[false]`, and `-18[false]` reparses as `at` of the literal `-18`.
     That shape does not occur in the 1628-task corpus and was found by
     --fuzz; it is the one defect the corpus alone would have missed.
     Everywhere else `-e` is `neg`, as SYNTAX.md writes it.

  2. `and` and `or` are n-ary (arities 2, 3 and 4 occur). `a and b and c`
     is the 3-ary node, and the 2-ary node whose first argument is itself an
     `and` is `(a and b) and c`. Flattening on print would collapse two
     distinct trees onto one string. Parentheses are therefore load-bearing
     at these two operators and nowhere else.

WHAT IS DELIBERATELY NOT HERE, each because deciding it would be a semantic
decision this file is not entitled to make:

  - No comments. A comment is text with no AST node, so it cannot survive
    print(parse(text)) and would make the round trip conditional.
  - `/` and `%` are `div` and `mod` (SPEC.md "Division and modulo", since
    2026-09-08: Euclidean, undefined at a zero divisor). Before that day t had
    neither and the notation refused the slash; the refusal probe now checks
    that the WORD div is not an operator in the notation.
  - No chained comparison. `a == b == c` is rejected rather than read as a
    conjunction; the AST has no node for it and inventing one would be a new
    construct.
  - No `and`/`or` at arity 1. The AST admits it and the notation cannot
    write it (`a and` is not a sentence). It does not occur in any of the
    1402 tasks; if one is ever built by hand, print raises rather than
    emitting something that reads as a different tree.
  - No notation for the fuzzer's `_`-prefixed bookkeeping keys (`_family`,
    `_expect`, `_gt`, ...). They are not part of the task format in SPEC.md,
    so print drops them and the round trip is compared modulo them.

Grammar, in the same EBNF dialect SYNTAX.md uses:

    Program  ::= "t" NAT ("gate" Id)?
                 "task" Id "(" Params ")" "returns" "(" Id ":" Type ")"
                 Clause* SpecFun* Block
    Clause   ::= "requires" Expr | "ensures" Expr | "decreases" Expr
    Params   ::= (Id ":" Type ("," Id ":" Type)*)?
    Type     ::= BaseType | "(" BaseType "," BaseType ")"  (* pair: v1, since 2026-09-10; no pair of pairs *)
               | "seq" "<" "seq" ">"                       (* nested seq: v1, since 2026-09-10; one level only *)
    BaseType ::= "int" | "bool" | "seq"
    SpecFun  ::= "spec" "fun" Id "(" Params ")" ":" ("int"|"bool")
                 "decreases" Expr "=" Expr
    Block    ::= "{" Stmt* "}"
    Stmt     ::= Id ":=" Expr ";"?
               | "var" Id ":" Type ":=" Expr ";"?
               | "if" Expr Block "else" Block
               | "while" Expr ("invariant" Expr)* "decreases" Expr Block
    Expr     ::= "forall" Id "in" "[" Expr "," Expr ")" "." Expr
               | "exists" Id "in" "[" Expr "," Expr ")" "." Expr
               | "if" Expr "then" Expr "else" Expr
               | Implies
    Implies  ::= Or ("==>" Implies)?              (* right associative *)
    Or       ::= And ("or" And)*                  (* n-ary, flat *)
    And      ::= Not ("and" Not)*                 (* n-ary, flat *)
    Not      ::= "not" Not | Cmp
    Cmp      ::= Add (("=="|"!="|"<"|"<="|">"|">=") Add)?   (* non-associative *)
    Add      ::= Mul (("+"|"-") Mul)*             (* left associative *)
    Mul      ::= Unary (("*"|"/"|"%") Unary)*     (* left associative; / % are div mod *)
    Unary    ::= "-" NAT | "-" Unary | Postfix
    Postfix  ::= Atom (("[" Expr (":=" Expr)? "]") | ("." ("0"|"1")))*
                                       (* `[...]` at/update; `.0`/`.1` fst/snd, v1 since 2026-09-10 *)
    Atom     ::= NAT | "true" | "false" | "len" "(" Expr ")"
               | "seq" "(" Expr "," Expr ")"       (* `fill`: seq(n, v) *)
               | Id "(" (Expr ("," Expr)*)? ")"   (* call *)
               | Id | "(" Expr ("," Expr)? ")"    (* grouping, or the pair literal (v1, 2026-09-10) *)

2026-09-11 (ROADMAP 14.2 "Errors with a position", parse side; check_wf's
well-formedness side is out of scope here, being built as its own module
elsewhere): every SurfaceError raised while LEXING or PARSING text now
carries `file`, `line`, `col` and the SYNTAX.md `production` being parsed
(see the SurfaceError class docstring for the two SYNTAX.md-heading cases
where no EBNF production name applies), `Tok` carries a `col` alongside
its existing `line`, and `str(err)` reads "file:line:col: message
[production]". Two new entry points: `parse_file(path)` reads and parses
a .t file, reporting `path` as `file` in any error; `parse(text,
positions=None)` (and `parse_file(path, positions=None)`) fill an optional
dict with `id(node) -> (line, col)` for every AST dict the parse builds,
for the well-formedness side to reuse once it exists (see `Parser.mark`
and `parse`'s own docstring). PRINTER errors (`pexpr`, `print_task`,
`_ident`, `_print_type`, `pstmts`) are unchanged: they are raised against a
possibly-malformed AST with no source text behind it, so they carry a
message only and `str(err)` falls back to that message, exactly as before
this note. Measured: `python3 t/surface.py --check --n 40 --seeds 1,2`
still round trips at 100% (the round trip itself is unchanged, only error
REPORTING is new) and `python3 t/test_surface_errors.py` passes 9 of 9
against the committed corpus in `t/malformed/` (one `.t` file per
production/heading this file's parser can name, listed in
`t/malformed/EXPECTED.tsv`); see those two commands' own printed output
for the live counts, not numbers frozen into this paragraph. Open: the
well-formedness side (`check_wf`, currently in `fuzz_lower.py`, not
touched by this note) does not yet carry position information or use the
`positions` dict `parse` now offers; the malformed corpus above therefore
has no check_wf rows yet, per the ROADMAP item's own DONE WHEN, which
covers both once check_wf is its own module.

Usage:

    python3 t/surface.py --check                 # the round trip, all corpora
    python3 t/surface.py --print t/tasks/abs.json
    python3 t/surface.py --parse FILE.t          # surface text to JSON
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

import check_wf


# ===========================================================================
# 1. Canonical form. Two ASTs are the same task when these strings match.
#    `_`-prefixed keys are fuzz_lower bookkeeping, not the task format.
# ===========================================================================

def strip_meta(task: dict) -> dict:
    return {k: v for k, v in task.items() if not k.startswith("_")}


def canon(task: dict) -> str:
    return json.dumps(strip_meta(task), sort_keys=True,
                      separators=(",", ":"), ensure_ascii=False)


class SurfaceError(Exception):
    """A text that is not in the language, or an AST with no notation.

    2026-09-11 (ROADMAP 14.2 "Errors with a position"): every error raised
    while LEXING or PARSING text (the lexer functions and every Parser
    method) carries the offending token's `file`, `line` and `col`, and the
    `production` of SYNTAX.md being parsed (or, where SYNTAX.md's own EBNF
    block has no name for what is being checked, the SYNTAX.md heading the
    rule sits under: see the note at the top of t/malformed/EXPECTED.tsv
    for the exact list). `str(err)` then reads "file:line:col: message
    [production]". Errors raised by the PRINTER (pexpr, print_task,
    _ident, _print_type, pstmts) are not parse errors: they are given a
    possibly-malformed AST with no source text behind it, so `line`/`col`/
    `production` stay None and `str(err)` falls back to the message alone.
    Measured by `python3 t/test_surface_errors.py` against the corpus in
    t/malformed/.
    """

    def __init__(self, message, file=None, line=None, col=None,
                production=None):
        self.message = message
        self.file = file
        self.line = line
        self.col = col
        self.production = production
        super().__init__(message)

    def __str__(self):
        if self.line is None:
            return self.message
        where = "%s:%s:%s" % (self.file or "<string>", self.line,
                              self.col if self.col is not None else "?")
        tag = " [%s]" % self.production if self.production else ""
        return "%s: %s%s" % (where, self.message, tag)


# ===========================================================================
# 2. Lexer.
# ===========================================================================

KEYWORDS = {
    "t", "gate", "task", "returns", "requires", "ensures", "decreases",
    "spec", "fun", "return", "var", "while", "invariant", "if", "then", "else",
    "forall", "exists", "in", "len", "true", "false", "and", "or", "not",
    "int", "bool", "seq",
    "tostr",       # SPEC.md "The string library" (2026-09-11): tostr(n) is
                   # a function like len(n), reserved the same way.
}

# SPEC.md "The string library" (2026-09-11): the 16 members reached as a
# postfix `.name(...)` (every member but tostr, which is a plain function
# call). These are NOT lexer keywords: `s.split()` only ever means the
# member because the parser looks for one of these names specifically
# after a `.`, exactly as `.0`/`.1` are recognised there without reserving
# "0" and "1"; a task is still free to name a spec_fun or a local `split`.
STR_METHODS = {"split", "join", "count", "find", "strip", "lstrip", "rstrip",
              "replace", "lower", "upper", "isdigit", "isalpha", "isupper",
              "islower", "startswith", "endswith"}

# Longest match first: "==>" before "==" before "=", ":=" before ":".
SYMBOLS = ["==>", "==", "!=", "<=", ">=", ":=", "=", "<", ">", "+", "-", "*",
           "/", "%", "(", ")", "[", "]", "{", "}", ",", "..", ".", ":", ";"]

_ID = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
_NAT = re.compile(r"[0-9]+")

# Escapes shared by char and string literals (SPEC.md "Strings as sequences
# of code points (v1)"): the four the spec names, plus \r and \0 since a
# code point is any int in [0, 1114111] and those two are as ordinary as \n
# and \t, plus \" so a string can hold a quote. A char literal has no
# textual use for \" but accepting it there too costs nothing and avoids a
# rule that only one of the two literal forms recognises an escape.
_ESCAPES = {"n": 10, "t": 9, "r": 13, "0": 0, "'": 39, '"': 34, "\\": 92}
_HEXDIGIT = "0123456789abcdefABCDEF"
MAX_CODE_POINT = 1114111  # SPEC.md: a character is an int in [0, 1114111].


# SYNTAX.md names no production for a char/string literal (both are Atom
# sugar with no EBNF name of their own in surface.py's grammar either, and
# SYNTAX.md's own Expr production does not mention them by name), so lexer
# errors raised inside a literal use the SYNTAX.md heading they are
# documented under instead: "Strings as sequences of code points (v1)".
# A lexer error with no construct at all to blame (an unexpected
# character) is filed under "Id", SYNTAX.md's own production for a name,
# since that is the nearest thing a bare, unrecognised character could
# have been starting. See t/malformed/EXPECTED.tsv for the full list of
# these no-name cases.
LIT_PRODUCTION = "Strings as sequences of code points (v1)"


class Tok:
    __slots__ = ("kind", "text", "pos", "line", "col")

    def __init__(self, kind, text, pos, line, col):
        self.kind, self.text, self.pos, self.line, self.col = (
            kind, text, pos, line, col)

    def __repr__(self):
        return "%s(%r)" % (self.kind, self.text)


def _lex_quoted(src: str, i: int, line: int, line_start: int, file: str,
                quote: str):
    """Scan a char or string literal body, `i` just past the opening quote.
    Returns (code points, index just past the closing quote). A literal
    never spans a line, so `line` does not change and `col` at any point
    inside it is `pos - line_start + 1`: a bare newline or the end of
    input before the closing quote is the same "unterminated" error.
    Escapes: \\n \\t \\r \\0 \\' \\" \\\\, plus \\u{H...H} (1 to 6 hex
    digits) for any other code point."""
    n = len(src)

    def err(pos, msg):
        raise SurfaceError(msg, file=file, line=line,
                           col=pos - line_start + 1, production=LIT_PRODUCTION)

    pts = []
    while True:
        if i >= n or src[i] == "\n":
            err(i, "unterminated literal")
        c = src[i]
        if c == quote:
            return pts, i + 1
        if c == "\\":
            if i + 1 >= n or src[i + 1] == "\n":
                err(i, "unterminated literal")
            e = src[i + 1]
            if e == "u":
                j = i + 2
                if j >= n or src[j] != "{":
                    err(i, "bad escape \\u, expected \\u{HEX}")
                j += 1
                k = j
                while k < n and k - j < 6 and src[k] in _HEXDIGIT:
                    k += 1
                if k == j:
                    err(i, "\\u{} needs at least one hex digit")
                if k >= n or src[k] != "}":
                    err(i, "\\u{...} escape missing closing }")
                cp = int(src[j:k], 16)
                if cp > MAX_CODE_POINT:
                    err(i, "\\u{%s} exceeds the maximum code point %d"
                        % (src[j:k], MAX_CODE_POINT))
                pts.append(cp)
                i = k + 1
                continue
            if e in _ESCAPES:
                pts.append(_ESCAPES[e])
                i += 2
                continue
            err(i, "bad escape \\%s" % e)
        pts.append(ord(c))
        i += 1


def lex(src: str, file: str = "<string>") -> list:
    """kinds: id, kw, nat, char, str, sym, eof. No comments: see the
    docstring. `char` and `str` tokens carry the decoded value directly
    (an int, a list of ints) rather than the source text: SurfaceError on
    an unterminated literal, a bad escape, or a char literal that does not
    hold exactly one code point. `file` is only for error messages: it
    names the source in every SurfaceError this lexer raises, "<string>"
    when the text did not come from a file (see parse_file)."""
    toks, i, line, n = [], 0, 1, len(src)
    line_start = 0
    while i < n:
        c = src[i]
        if c in " \t\r":
            i += 1
            continue
        if c == "\n":
            line += 1
            i += 1
            line_start = i
            continue
        col = i - line_start + 1
        if c == "'":
            start = i
            pts, i = _lex_quoted(src, i + 1, line, line_start, file, "'")
            if len(pts) != 1:
                raise SurfaceError(
                    "a char literal holds exactly one code point, found %d"
                    % len(pts), file=file, line=line, col=col,
                    production=LIT_PRODUCTION)
            toks.append(Tok("char", pts[0], start, line, col))
            continue
        if c == '"':
            start = i
            pts, i = _lex_quoted(src, i + 1, line, line_start, file, '"')
            toks.append(Tok("str", pts, start, line, col))
            continue
        m = _ID.match(src, i)
        if m:
            w = m.group(0)
            toks.append(Tok("kw" if w in KEYWORDS else "id", w, i, line, col))
            i = m.end()
            continue
        m = _NAT.match(src, i)
        if m:
            toks.append(Tok("nat", m.group(0), i, line, col))
            i = m.end()
            continue
        for s in SYMBOLS:
            if src.startswith(s, i):
                toks.append(Tok("sym", s, i, line, col))
                i += len(s)
                break
        else:
            raise SurfaceError("unexpected character %r" % c, file=file,
                               line=line, col=col, production="Id")
    toks.append(Tok("eof", "", n, line, n - line_start + 1))
    return toks


# ===========================================================================
# 3. Parser. Recursive descent; the precedence ladder is the one in the
#    docstring's grammar, lowest binding first.
# ===========================================================================

CMP_OPS = {"==", "!=", "<", "<=", ">", ">="}
# The multiplicative symbols and the AST operators they denote. `/` and `%`
# are SPEC.md's div and mod (Euclidean, 2026-09-08); the notation is sugar
# and the AST op names are the words, as SPEC.md writes them.
_MUL_OPS = {"*": "*", "/": "div", "%": "mod"}
_OP_TEXT = {"div": "/", "mod": "%"}
VAL_TYPES = ("int", "bool", "seq")


# 2026-09-11 (ROADMAP 14.2): the production every raise site below names.
# Six are SYNTAX.md's own EBNF names (Task, Type, SpecFun, Stmt, Expr, Op,
# Id); SYNTAX.md gives no production name to a char/string literal or to
# the notation's "comparisons do not chain" rule, so those two use the
# SYNTAX.md heading they are documented under instead. The full list of
# no-name cases lives in the header comment of t/malformed/EXPECTED.tsv.
NO_CHAIN_HEADING = "What the notation refuses"


class Parser:
    def __init__(self, src: str, file: str = "<string>", positions=None):
        self.ret_name = None      # set by program(); a bare stmt has no task
        self.file = file
        self.positions = positions   # optional dict: id(node) -> (line, col)
        self.toks = lex(src, file)
        self.i = 0
        self.production = "Task"  # the SYNTAX.md production being parsed

    # -- token plumbing ----------------------------------------------------

    @property
    def tok(self) -> Tok:
        return self.toks[self.i]

    def at(self, kind: str, text=None) -> bool:
        t = self.tok
        return t.kind == kind and (text is None or t.text == text)

    def err(self, tok: Tok, message: str, production=None):
        raise SurfaceError(message, file=self.file, line=tok.line,
                           col=tok.col, production=production or self.production)

    def eat(self, kind: str, text=None, production=None) -> Tok:
        t = self.tok
        if not self.at(kind, text):
            want = text if text is not None else kind
            self.err(t, "expected %r, found %r"
                     % (want, t.text or "end of input"), production)
        self.i += 1
        return t

    def opt(self, kind: str, text=None) -> bool:
        if self.at(kind, text):
            self.i += 1
            return True
        return False

    def mark(self, tok: Tok, node):
        """Record where `node` (an AST dict this parser just built) starts,
        if the caller asked for positions (see module docstring 'POSITIONS
        FOR THE WELL-FORMEDNESS SIDE'). Always returns `node` so call sites
        read as `return self.mark(tok, {...})`."""
        if self.positions is not None:
            self.positions[id(node)] = (tok.line, tok.col)
        return node

    def name(self, production=None) -> str:
        return self.eat("id", production=production).text

    def vtype(self, allowed=VAL_TYPES) -> str:
        t = self.eat("kw", production="Type")
        if t.text not in allowed:
            self.err(t, "%r is not one of %s" % (t.text, " ".join(allowed)),
                     "Type")
        return t.text

    def ptype(self):
        """A t TYPE: int/bool/seq, a pair `(T1, T2)` (SPEC.md "Pairs",
        2026-09-10), or a nested seq `seq<seq>` (SPEC.md "Nested
        sequences", 2026-09-10). T1 and T2 are read with `vtype()`, not
        `ptype()` itself, because there is no pair of pairs to recurse
        into; this is the one place the grammar's `Type` and `BaseType`
        differ. `<` and `>` are already the comparison symbols the lexer
        tokenises everywhere else, but a type position never holds an
        expression, so reading `<` right after the keyword `seq` here is
        unambiguous with no new token: nothing else can follow a type's
        own `seq` keyword at this point in the grammar."""
        start = self.tok
        if self.at("sym", "("):
            self.eat("sym", "(", "Type")
            t1 = self.vtype()
            self.eat("sym", ",", "Type")
            t2 = self.vtype()
            self.eat("sym", ")", "Type")
            return self.mark(start, {"pair": [t1, t2]})
        t = self.vtype()
        if t == "seq" and self.opt("sym", "<"):
            self.eat("kw", "seq", "Type")
            self.eat("sym", ">", "Type")
            return self.mark(start, {"seq": "seq"})
        return t

    # -- program -----------------------------------------------------------

    def program(self) -> dict:
        start = self.tok
        self.production = "Task"
        self.eat("kw", "t")
        ver = int(self.eat("nat").text)
        if ver not in (0, 1):
            self.err(start, "format version must be 0 or 1, found %d" % ver)
        task = {"t": ver}
        if self.opt("kw", "gate"):
            task["gate"] = self.name()
        self.eat("kw", "task")
        task["name"] = self.name()
        task["params"] = self.params("Task")
        self.eat("kw", "returns")
        self.eat("sym", "(")
        rname = self.name()
        self.ret_name = rname
        self.eat("sym", ":")
        rtok = self.tok
        rtype = self.ptype()
        self.production = "Task"           # ptype() left it on "Type"
        self.eat("sym", ")")
        task["returns"] = [self.mark(rtok, {"name": rname, "type": rtype})]

        requires, ensures, dec = [], [], None
        while self.tok.kind == "kw" and self.tok.text in (
                "requires", "ensures", "decreases"):
            self.production = "Task"
            wtok = self.eat("kw")
            what = wtok.text
            e = self.expr()
            self.production = "Task"       # expr() left it on "Expr"
            if what == "requires":
                requires.append(e)
            elif what == "ensures":
                ensures.append(e)
            else:
                if dec is not None:
                    self.err(wtok, "a task has at most one decreases")
                dec = e
        task["requires"] = requires
        task["ensures"] = ensures

        funs = []
        while self.at("kw", "spec"):
            funs.append(self.spec_fun())
        self.production = "Task"           # spec_fun() left it on "SpecFun"
        if funs:
            task["spec_funs"] = funs
        if dec is not None:
            task["decreases"] = dec
        task["body"] = self.block()
        self.production = "Task"           # block()/stmt() left it on "Stmt"
        self.eat("eof")
        return self.mark(start, task)

    def params(self, production: str) -> list:
        """`production` is the caller's own (Task for a task's own params,
        SpecFun for a spec_fun's): Params has no name of its own in
        SYNTAX.md, it is written inline inside both, so every error here is
        filed under whichever of the two is parsing them."""
        self.production = production
        self.eat("sym", "(", production)
        out = []
        if not self.at("sym", ")"):
            while True:
                ptok = self.tok
                pn = self.name(production)
                self.eat("sym", ":", production)
                ty = self.ptype()
                self.production = production   # ptype() left it on "Type"
                out.append(self.mark(ptok, {"name": pn, "type": ty}))
                if not self.opt("sym", ","):
                    break
        self.eat("sym", ")", production)
        return out

    def spec_fun(self) -> dict:
        start = self.tok
        self.production = "SpecFun"
        self.eat("kw", "spec")
        self.eat("kw", "fun")
        fn = {"name": self.name("SpecFun"), "params": self.params("SpecFun")}
        self.eat("sym", ":")
        fn["result"] = self.vtype(("int", "bool"))
        self.production = "SpecFun"        # vtype() left it on "Type"
        self.eat("kw", "decreases")
        fn["decreases"] = self.expr()
        self.production = "SpecFun"        # expr() left it on "Expr"
        self.eat("sym", "=")
        fn["body"] = self.expr()
        self.production = "SpecFun"
        return self.mark(start, fn)

    # -- statements --------------------------------------------------------

    def block(self) -> list:
        self.production = "Stmt"
        self.eat("sym", "{")
        out = []
        while not self.at("sym", "}"):
            if self.at("eof"):
                self.err(self.tok, "unterminated block")
            out.append(self.stmt())
            self.production = "Stmt"       # stmt() may leave it on "Expr"
        self.eat("sym", "}")
        return out

    def stmt(self) -> dict:
        self.production = "Stmt"
        t = self.tok
        if self.opt("kw", "return"):
            # SPEC.md "Early exit" (2026-09-08): the AST names the task's
            # return variable, as assign does, so the interpreter needs no
            # context to run it; the notation fills the name from the header.
            if self.ret_name is None:
                self.err(t, "return outside a task")
            e = self.expr()
            self.opt("sym", ";")
            return self.mark(t, {"return": [self.ret_name, e]})
        if t.kind == "id":
            target = self.name()
            self.eat("sym", ":=", "Stmt")
            e = self.expr()
            self.opt("sym", ";")
            return self.mark(t, {"assign": [target, e]})
        if self.opt("kw", "var"):
            t = self.tok            # the declared name, not the keyword (2026-09-11)
            vn = self.name("Stmt")
            self.eat("sym", ":", "Stmt")
            ty = self.ptype()
            self.production = "Stmt"       # ptype() left it on "Type"
            self.eat("sym", ":=")
            init = self.expr()
            self.opt("sym", ";")
            return self.mark(t, {"var": {"name": vn, "type": ty,
                                         "init": init}})
        if self.opt("kw", "if"):
            cond = self.expr()
            self.production = "Stmt"
            then = self.block()
            self.production = "Stmt"       # block() left it on "Stmt" already
            self.eat("kw", "else")
            els = self.block()
            return self.mark(t, {"if": {"cond": cond, "then": then,
                                        "else": els}})
        if self.opt("kw", "while"):
            cond = self.expr()
            self.production = "Stmt"
            invs = []
            while self.opt("kw", "invariant"):
                invs.append(self.expr())
                self.production = "Stmt"
            self.eat("kw", "decreases")
            dec = self.expr()
            self.production = "Stmt"
            body = self.block()
            return self.mark(t, {"while": {"cond": cond, "invariants": invs,
                                           "decreases": dec, "body": body}})
        self.err(t, "%r does not start a statement" % (t.text or "end of input"))

    # -- expressions -------------------------------------------------------

    def expr(self) -> dict:
        """The lowest level: quantifiers and ite, whose bodies run to the
        right as far as they can, then implies."""
        self.production = "Expr"
        start = self.tok
        if self.at("kw", "forall") or self.at("kw", "exists"):
            kind = self.eat("kw").text
            v = self.name("Expr")
            self.eat("kw", "in")
            self.eat("sym", "[")
            lo = self.expr()
            self.production = "Expr"
            self.eat("sym", ",")
            hi = self.expr()
            self.production = "Expr"
            self.eat("sym", ")")            # half-open range, SPEC.md gate 1
            self.eat("sym", ".")
            body = self.expr()
            self.production = "Expr"
            return self.mark(start, {kind: {"var": v, "lo": lo, "hi": hi,
                                            "body": body}})
        if self.opt("kw", "if"):
            cond = self.expr()
            self.production = "Expr"
            self.eat("kw", "then")
            then = self.expr()
            self.production = "Expr"
            self.eat("kw", "else")
            els = self.expr()
            self.production = "Expr"
            return self.mark(start, {"ite": {"cond": cond, "then": then,
                                             "else": els}})
        return self.p_implies()

    def p_implies(self) -> dict:
        start = self.tok
        left = self.p_or()
        if self.opt("sym", "==>"):
            right = self.expr() if (self.at("kw", "forall")
                                    or self.at("kw", "exists")
                                    or self.at("kw", "if")) else self.p_implies()
            self.production = "Expr"
            return self.mark(start, {"op": "implies", "args": [left, right]})
        return left

    def p_or(self) -> dict:
        start = self.tok
        args = [self.p_and()]
        while self.opt("kw", "or"):
            args.append(self.p_and())
        return (args[0] if len(args) == 1
               else self.mark(start, {"op": "or", "args": args}))

    def p_and(self) -> dict:
        start = self.tok
        args = [self.p_not()]
        while self.opt("kw", "and"):
            args.append(self.p_not())
        return (args[0] if len(args) == 1
               else self.mark(start, {"op": "and", "args": args}))

    def p_not(self) -> dict:
        start = self.tok
        if self.opt("kw", "not"):
            return self.mark(start, {"op": "not", "args": [self.p_not()]})
        return self.p_cmp()

    def p_cmp(self) -> dict:
        start = self.tok
        left = self.p_add()
        if self.tok.kind == "sym" and self.tok.text in CMP_OPS:
            op = self.eat("sym").text
            right = self.p_add()
            if self.tok.kind == "sym" and self.tok.text in CMP_OPS:
                # SYNTAX.md names no production for this rule (Cmp is
                # surface.py's own non-associative precedence level, not a
                # SYNTAX.md name): filed under the SYNTAX.md heading that
                # documents it, "## What the notation refuses".
                self.err(self.tok, "comparisons do not chain; parenthesise",
                         NO_CHAIN_HEADING)
            return self.mark(start, {"op": op, "args": [left, right]})
        return left

    def p_add(self) -> dict:
        left = self.p_mul()
        while self.tok.kind == "sym" and self.tok.text in ("+", "-"):
            start = self.tok
            op = self.eat("sym").text
            left = self.mark(start, {"op": op, "args": [left, self.p_mul()]})
        return left

    def p_mul(self) -> dict:
        left = self.p_unary()
        while self.at("sym", "*") or self.at("sym", "/") or self.at("sym", "%"):
            start = self.tok
            sym = self.toks[self.i].text
            self.eat("sym", sym)
            left = self.mark(start, {"op": _MUL_OPS[sym],
                                     "args": [left, self.p_unary()]})
        return left

    def p_unary(self) -> dict:
        start = self.tok
        if self.opt("sym", "-"):
            # `-5` is the literal; `-(5)` is neg of the literal. See the
            # docstring: both nodes are live in the corpus.
            if self.tok.kind == "nat":
                return self.mark(start, {"int": -int(self.eat("nat").text)})
            return self.mark(start, {"op": "neg", "args": [self.p_unary()]})
        return self.p_postfix()

    def p_postfix(self) -> dict:
        e = self.p_atom()
        while True:
            start = self.tok
            if self.opt("sym", "["):
                if self.opt("sym", ".."):
                    # s[..b] is s[0..b] (SPEC.md "Sequences: literals,
                    # concatenation, slices"): sugar the parser expands, the
                    # AST carries the three-argument slice only.
                    hi = self.expr()
                    self.production = "Expr"
                    self.eat("sym", "]")
                    e = self.mark(start, {"op": "slice",
                                          "args": [e, {"int": 0}, hi]})
                    continue
                idx = self.expr()
                self.production = "Expr"
                if self.opt("sym", ":="):
                    val = self.expr()
                    self.production = "Expr"
                    self.eat("sym", "]")
                    e = self.mark(start, {"op": "update",
                                          "args": [e, idx, val]})
                    continue
                if self.opt("sym", ".."):
                    if self.opt("sym", "]"):
                        # s[a..] is s[a..len(s)].
                        e = self.mark(start, {"op": "slice", "args": [
                            e, idx, {"op": "len", "args": [e]}]})
                        continue
                    hi = self.expr()
                    self.production = "Expr"
                    self.eat("sym", "]")
                    e = self.mark(start, {"op": "slice", "args": [e, idx, hi]})
                    continue
                self.eat("sym", "]")
                e = self.mark(start, {"op": "at", "args": [e, idx]})
                continue
            if self.opt("sym", "."):
                if self.tok.kind == "nat":
                    # p.0 / p.1: the pair projections (SPEC.md "Pairs",
                    # 2026-09-10). The lexer already tokenises "." and a
                    # following NAT separately (there is no float literal
                    # in t to collide with), so `.` here is unambiguously a
                    # projection and not a decimal point; only these two
                    # digits are the grammar, exactly as `and` at arity 1
                    # has none. `.0`/`.1` are `Op` in SYNTAX.md ("fst" |
                    # "snd"), not `Expr`: a malformed projection names a
                    # specific operator, not "an expression is missing".
                    tok = self.eat("nat")
                    if tok.text not in ("0", "1"):
                        self.err(tok, "a pair projection is .0 or .1, "
                                 "found .%s" % tok.text, "Op")
                    e = self.mark(start, {"op": "fst" if tok.text == "0"
                                          else "snd", "args": [e]})
                    continue
                if self.tok.kind == "id" and self.tok.text in STR_METHODS:
                    # s.split(), s.count(t), sep.join(rows), ... (SPEC.md
                    # "The string library", 2026-09-11): postfix, so it
                    # composes with indexing and slicing the same way .0/.1
                    # do (s.split()[0], s.strip().lower()). Every error
                    # below names one string-library member, so all are
                    # "Op", SYNTAX.md's production for the operator list.
                    ntok = self.eat("id")
                    name = ntok.text
                    self.eat("sym", "(", "Op")
                    margs = []
                    if not self.at("sym", ")"):
                        while True:
                            margs.append(self.expr())
                            if not self.opt("sym", ","):
                                break
                    self.eat("sym", ")", "Op")
                    if name == "split":
                        if len(margs) not in (0, 1):
                            self.err(ntok, ".split takes zero or one "
                                     "argument, given %d" % len(margs), "Op")
                        e = self.mark(start, {"op": "split",
                                              "args": [e] + margs})
                    elif name == "join":
                        if len(margs) != 1:
                            self.err(ntok, ".join takes exactly one "
                                     "argument, given %d" % len(margs), "Op")
                        # sep.join(rows): SPEC.md's op signature is
                        # join(rows, sep), the receiver second.
                        e = self.mark(start, {"op": "join",
                                              "args": [margs[0], e]})
                    elif name == "replace":
                        if len(margs) != 2:
                            self.err(ntok, ".replace takes exactly two "
                                     "arguments, given %d" % len(margs), "Op")
                        e = self.mark(start, {"op": "replace",
                                              "args": [e] + margs})
                    elif name in ("count", "find", "startswith", "endswith"):
                        if len(margs) != 1:
                            self.err(ntok, ".%s takes exactly one argument, "
                                     "given %d" % (name, len(margs)), "Op")
                        e = self.mark(start, {"op": name,
                                              "args": [e, margs[0]]})
                    else:
                        # strip, lstrip, rstrip, lower, upper, isdigit,
                        # isalpha, isupper, islower: no arguments.
                        if margs:
                            self.err(ntok, ".%s takes no arguments, given %d"
                                     % (name, len(margs)), "Op")
                        e = self.mark(start, {"op": name, "args": [e]})
                    continue
                # Neither .0/.1 nor a known string-library member: "Op"
                # again, since the message names the set of valid operators
                # a dot may introduce.
                self.err(self.tok, "a dot must be followed by .0, .1, or a "
                         "string-library member", "Op")
            break
        return e

    def p_atom(self) -> dict:
        t = self.tok
        if t.kind == "nat":
            return self.mark(t, {"int": int(self.eat("nat").text)})
        if t.kind == "char":
            # 'a': sugar for its code point (SPEC.md "Strings as sequences
            # of code points (v1)"). The printer never emits this form.
            return self.mark(t, {"int": self.eat("char").text})
        if t.kind == "str":
            # "abc": sugar for the seq literal of its code points; "" is
            # []. Same spec section; same non-canonical relationship to
            # the printer.
            return self.mark(t, {"op": "seq",
                                 "args": [{"int": cp}
                                          for cp in self.eat("str").text]})
        if self.at("kw", "true"):
            self.eat("kw")
            return self.mark(t, {"bool": True})
        if self.at("kw", "false"):
            self.eat("kw")
            return self.mark(t, {"bool": False})
        if self.at("kw", "len"):
            self.eat("kw")
            self.eat("sym", "(")
            e = self.expr()
            self.production = "Expr"
            self.eat("sym", ")")
            return self.mark(t, {"op": "len", "args": [e]})
        if self.at("kw", "seq"):
            # seq(n, v), the `fill` constructor (SPEC.md "Sequences as values").
            self.eat("kw")
            self.eat("sym", "(")
            n = self.expr()
            self.production = "Expr"
            self.eat("sym", ",")
            v = self.expr()
            self.production = "Expr"
            self.eat("sym", ")")
            return self.mark(t, {"op": "fill", "args": [n, v]})
        if self.at("kw", "tostr"):
            # tostr(n): SPEC.md "The string library" (2026-09-11), a
            # function like len(n), not a postfix member.
            self.eat("kw")
            self.eat("sym", "(")
            n = self.expr()
            self.production = "Expr"
            self.eat("sym", ")")
            return self.mark(t, {"op": "tostr", "args": [n]})
        if self.opt("sym", "("):
            e = self.expr()
            self.production = "Expr"
            if self.opt("sym", ","):
                # (e1, e2): the pair literal (SPEC.md "Pairs", 2026-09-10).
                # `(e)` alone, no comma, stays grouping, as it always was.
                e2 = self.expr()
                self.production = "Expr"
                self.eat("sym", ")")
                return self.mark(t, {"op": "pair", "args": [e, e2]})
            self.eat("sym", ")")
            return e
        if self.opt("sym", "["):
            # [e1, ..., en], the sequence literal; [] the empty sequence
            # (SPEC.md "Sequences: literals, concatenation, slices").
            args = []
            if not self.at("sym", "]"):
                while True:
                    args.append(self.expr())
                    self.production = "Expr"
                    if not self.opt("sym", ","):
                        break
            self.eat("sym", "]")
            return self.mark(t, {"op": "seq", "args": args})
        if t.kind == "id":
            ident = self.name()
            if self.opt("sym", "("):
                args = []
                if not self.at("sym", ")"):
                    while True:
                        args.append(self.expr())
                        self.production = "Expr"
                        if not self.opt("sym", ","):
                            break
                self.eat("sym", ")")
                return self.mark(t, {"call": {"fun": ident, "args": args}})
            return self.mark(t, {"var": ident})
        self.err(t, "%r does not start an expression"
                 % (t.text or "end of input"))


def parse(src: str, positions=None) -> dict:
    """Text to canonical JSON. `positions`, if given a dict, is filled with
    id(node) -> (line, col) for every AST dict this parse builds (the task
    itself, every param/return/spec_fun entry, every type, every
    statement, every expression node): the well-formedness side keeps its
    own copy of the AST and can look a node up in this dict by `id()` to
    report where in the source it came from, exactly as SurfaceError does
    for a parse error. A node's position is where it STARTS: the keyword or
    the first token of the expression, not the whole span. Two distinct
    nodes never collide in this dict because Python's `id()` is unique
    among the live objects the parser itself built and nothing here is
    shared or interned; keep the returned task (or a structure built from
    walking it) alive for as long as `positions` is read, since `id()` can
    be reused once an object is garbage collected."""
    return Parser(src, positions=positions).program()


def parse_file(path: str, positions=None) -> dict:
    """A .t file to canonical JSON, `path` reported (as given, not resolved
    or normalised) in every SurfaceError this raises, so the caller sees
    which file was bad without having to catch and re-wrap. See `parse`
    for `positions`."""
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    return Parser(src, file=path, positions=positions).program()


def check_file(path: str) -> list:
    """A .t file to its well-formedness errors, parse and check_wf both
    covered: `parse_file(path, positions=...)`, then `check_wf.check_wf`
    with that same positions map and `path` as `file`. A file that fails
    to PARSE never reaches check_wf -- the SurfaceError the parse raised is
    the sole element of the returned list, the same object `parse_file`
    would have raised, so a caller can `str()` it exactly like any other
    error this returns. A file that parses but is not well-formed returns
    `check_wf`'s list of WfError (empty when well-formed). Added 2026-09-11
    (ROADMAP 14.2, well-formedness half): the one entry point that wires
    the parse side's positions to the checker side, so a caller need not
    know either module's internals to get `file:line:col: message
    [SPEC: rule]` for a malformed .t file."""
    positions: dict = {}
    try:
        task = parse_file(path, positions=positions)
    except SurfaceError as exc:
        return [exc]
    return check_wf.check_wf(task, positions=positions, file=path)


def parse_expr(src: str) -> dict:
    """One expression, for the SYNTAX.md `written:` lines that are not tasks."""
    p = Parser(src)
    e = p.expr()
    p.eat("eof")
    return e


def parse_stmt(src: str) -> dict:
    p = Parser(src)
    s = p.stmt()
    p.eat("eof")
    return s


# ===========================================================================
# 4. Printer. Precedence-driven: a child is parenthesised exactly when its
#    own level binds looser than the level its position allows. The two
#    information-losing cases the docstring names are handled here.
# ===========================================================================

P_QUANT = 0
P_IMPLIES = 1
P_OR = 2
P_AND = 3
P_NOT = 4
P_CMP = 5
P_ADD = 6
P_MUL = 7
P_UNARY = 8
P_POSTFIX = 9

_BINPREC = {"+": P_ADD, "-": P_ADD, "*": P_MUL, "div": P_MUL, "mod": P_MUL}
_ARITY = {"neg": 1, "not": 1, "len": 1, "at": 2, "update": 3, "fill": 2, "slice": 3, "implies": 2,
          "+": 2, "-": 2, "*": 2, "div": 2, "mod": 2,
          "==": 2, "!=": 2, "<": 2, "<=": 2, ">": 2, ">=": 2,
          "pair": 2, "fst": 1, "snd": 1,
          # SPEC.md "The string library" (2026-09-11); `split` is excluded
          # here (one or two arguments) and checked in its own print/parse
          # branches instead, exactly as `seq`/`and`/`or` are excluded for
          # their own variable arities.
          "join": 2, "tostr": 1, "count": 2, "find": 2, "strip": 1,
          "lstrip": 1, "rstrip": 1, "replace": 3, "lower": 1, "upper": 1,
          "isdigit": 1, "isalpha": 1, "isupper": 1, "islower": 1,
          "startswith": 2, "endswith": 2}


def _wrap(text: str, prec: int, floor: int) -> str:
    return "(%s)" % text if prec < floor else text


def pexpr(e, floor: int = P_QUANT) -> str:
    if not isinstance(e, dict):
        raise SurfaceError("not an expression node: %r" % (e,))
    keys = set(e)
    if keys == {"op", "args"}:
        kind = "op"
    elif len(keys) == 1:
        kind = next(iter(keys))
    else:
        raise SurfaceError("not an expression node: %r" % (e,))

    if kind == "int":
        n = e["int"]
        if not isinstance(n, int) or isinstance(n, bool):
            raise SurfaceError("int literal is not an integer: %r" % (n,))
        # A negative literal binds like a unary minus for the reader; it is
        # one token for the parser.
        return _wrap(str(n), P_UNARY if n < 0 else P_POSTFIX, floor)
    if kind == "bool":
        if e["bool"] not in (True, False):
            raise SurfaceError("bool literal is not a boolean: %r" % (e,))
        return "true" if e["bool"] else "false"
    if kind == "var":
        return _ident(e["var"])
    if kind == "call":
        c = e["call"]
        return "%s(%s)" % (_ident(c["fun"]),
                           ", ".join(pexpr(a) for a in c["args"]))
    if kind == "ite":
        it = e["ite"]
        return _wrap("if %s then %s else %s"
                     % (pexpr(it["cond"]), pexpr(it["then"]),
                        pexpr(it["else"])), P_QUANT, floor)
    if kind in ("forall", "exists"):
        q = e[kind]
        return _wrap("%s %s in [%s, %s) . %s"
                     % (kind, _ident(q["var"]), pexpr(q["lo"]),
                        pexpr(q["hi"]), pexpr(q["body"])), P_QUANT, floor)
    if kind != "op":
        raise SurfaceError("unknown expression node %r" % kind)

    op, args = e["op"], e["args"]
    if op in _ARITY and len(args) != _ARITY[op]:
        raise SurfaceError("%r takes %d argument(s), given %d"
                           % (op, _ARITY[op], len(args)))

    if op == "len":
        return "len(%s)" % pexpr(args[0])
    if op == "at":
        return _wrap("%s[%s]" % (pexpr(args[0], P_POSTFIX), pexpr(args[1])),
                     P_POSTFIX, floor)
    if op == "update":
        return _wrap("%s[%s := %s]" % (pexpr(args[0], P_POSTFIX), pexpr(args[1]),
                                       pexpr(args[2])), P_POSTFIX, floor)
    if op == "fill":
        return "seq(%s, %s)" % (pexpr(args[0]), pexpr(args[1]))
    if op == "seq":
        # The literal, any arity including zero (SPEC.md "Sequences:
        # literals, concatenation, slices"); `[]` is the empty sequence.
        return "[%s]" % ", ".join(pexpr(a) for a in args)
    if op == "slice":
        # Always the three-argument form: the parser's `s[a..]` and `s[..b]`
        # sugars print back as `s[a..len(s)]` and `s[0..b]`, which reparse
        # to the same AST.
        return _wrap("%s[%s..%s]" % (pexpr(args[0], P_POSTFIX), pexpr(args[1]),
                                     pexpr(args[2])), P_POSTFIX, floor)
    if op == "pair":
        # (e1, e2) (SPEC.md "Pairs", 2026-09-10): its own delimiters, like
        # `seq`'s `[...]` or `call`'s `f(...)`, so no `_wrap` floor applies.
        return "(%s, %s)" % (pexpr(args[0]), pexpr(args[1]))
    if op in ("fst", "snd"):
        # p.0 / p.1: the projections, postfix like `at`.
        return _wrap("%s.%s" % (pexpr(args[0], P_POSTFIX),
                                "0" if op == "fst" else "1"),
                     P_POSTFIX, floor)
    if op == "split":
        # SPEC.md "The string library" (2026-09-11): s.split() / s.split(c),
        # postfix so it composes with indexing (`s.split()[0]`).
        if len(args) not in (1, 2):
            raise SurfaceError("split takes one or two arguments, given %d"
                               % len(args))
        inner = "" if len(args) == 1 else pexpr(args[1])
        return _wrap("%s.split(%s)" % (pexpr(args[0], P_POSTFIX), inner),
                     P_POSTFIX, floor)
    if op == "join":
        # join(rows, sep): the notation reads sep.join(rows), the receiver
        # SECOND in the AST (SPEC.md states the op's own signature as
        # "join(rows, sep)"), swapped back here.
        return _wrap("%s.join(%s)" % (pexpr(args[1], P_POSTFIX),
                                      pexpr(args[0])), P_POSTFIX, floor)
    if op == "tostr":
        return "tostr(%s)" % pexpr(args[0])
    if op in ("count", "find", "startswith", "endswith"):
        return _wrap("%s.%s(%s)" % (pexpr(args[0], P_POSTFIX), op,
                                    pexpr(args[1])), P_POSTFIX, floor)
    if op in ("strip", "lstrip", "rstrip", "lower", "upper", "isdigit",
             "isalpha", "isupper", "islower"):
        return _wrap("%s.%s()" % (pexpr(args[0], P_POSTFIX), op),
                     P_POSTFIX, floor)
    if op == "replace":
        return _wrap("%s.replace(%s, %s)" % (pexpr(args[0], P_POSTFIX),
                                             pexpr(args[1]), pexpr(args[2])),
                     P_POSTFIX, floor)
    if op == "neg":
        # `-(5)`, never `-5`: the bare form is the literal node. The test is
        # on the printed text and not on the node, because `neg` of `at` on a
        # literal base prints `18[false]`, and `-18[false]` would be lexed
        # with the sign inside the literal and reparse as `at` of `-18`.
        body = pexpr(args[0], P_POSTFIX)
        if body[:1].isdigit():
            body = "(%s)" % body
        return _wrap("-" + body, P_UNARY, floor)
    if op == "not":
        return _wrap("not " + pexpr(args[0], P_NOT), P_NOT, floor)
    if op in ("and", "or"):
        if len(args) < 2:
            raise SurfaceError("%r at arity %d has no notation; see the "
                               "module docstring" % (op, len(args)))
        prec = P_AND if op == "and" else P_OR
        sep = " %s " % op
        return _wrap(sep.join(pexpr(a, prec + 1) for a in args), prec, floor)
    if op == "implies":
        return _wrap("%s ==> %s" % (pexpr(args[0], P_IMPLIES + 1),
                                    pexpr(args[1], P_IMPLIES)),
                     P_IMPLIES, floor)
    if op in CMP_OPS:
        return _wrap("%s %s %s" % (pexpr(args[0], P_CMP + 1), op,
                                   pexpr(args[1], P_CMP + 1)), P_CMP, floor)
    if op in _BINPREC:
        prec = _BINPREC[op]
        return _wrap("%s %s %s" % (pexpr(args[0], prec), _OP_TEXT.get(op, op),
                                   pexpr(args[1], prec + 1)), prec, floor)
    raise SurfaceError("operator %r is not in t; see SPEC.md" % op)


def _ident(name) -> str:
    if not isinstance(name, str) or not _ID.fullmatch(name):
        raise SurfaceError("not an identifier: %r" % (name,))
    if name in KEYWORDS:
        raise SurfaceError("%r is a keyword of the surface syntax and has no "
                           "notation as a name" % name)
    return name


def _print_type(t) -> str:
    """int/bool/seq print as themselves; a pair `{"pair": [T1, T2]}`
    (SPEC.md "Pairs", 2026-09-10) prints as `(T1, T2)`; a nested seq
    `{"seq": "seq"}` (SPEC.md "Nested sequences", 2026-09-10) prints as
    `seq<seq>`. Both are the notation `ptype()` parses back. Anything else
    is not a t type."""
    if isinstance(t, dict):
        p = t.get("pair")
        if (set(t) == {"pair"} and isinstance(p, list) and len(p) == 2
                and all(c in VAL_TYPES for c in p)):
            return "(%s, %s)" % (p[0], p[1])
        if t == {"seq": "seq"}:
            return "seq<seq>"
        raise SurfaceError("not a t type: %r" % (t,))
    if t not in VAL_TYPES:
        raise SurfaceError("not a t type: %r" % (t,))
    return t


def pstmts(body: list, ind: str) -> list:
    out = []
    for s in body:
        if not isinstance(s, dict) or len(s) != 1:
            raise SurfaceError("not a statement node: %r" % (s,))
        kind = next(iter(s))
        if kind == "return":
            out.append("%sreturn %s;" % (ind, pexpr(s["return"][1], 0)))
            continue
        if kind == "assign":
            tgt, val = s["assign"]
            out.append("%s%s := %s;" % (ind, _ident(tgt), pexpr(val)))
        elif kind == "var":
            v = s["var"]
            out.append("%svar %s: %s := %s;"
                       % (ind, _ident(v["name"]), _print_type(v["type"]),
                          pexpr(v["init"])))
        elif kind == "if":
            f = s["if"]
            out.append("%sif %s {" % (ind, pexpr(f["cond"], P_IMPLIES)))
            out += pstmts(f["then"], ind + "  ")
            out.append("%s} else {" % ind)
            out += pstmts(f["else"], ind + "  ")
            out.append("%s}" % ind)
        elif kind == "while":
            w = s["while"]
            out.append("%swhile %s" % (ind, pexpr(w["cond"], P_IMPLIES)))
            for inv in w["invariants"]:
                out.append("%s  invariant %s" % (ind, pexpr(inv)))
            out.append("%s  decreases %s" % (ind, pexpr(w["decreases"])))
            out.append("%s{" % ind)
            out += pstmts(w["body"], ind + "  ")
            out.append("%s}" % ind)
        else:
            raise SurfaceError("unknown statement node %r" % kind)
    return out


def print_task(task: dict) -> str:
    """The AST to surface text. Raises SurfaceError on anything the notation
    cannot say, rather than emitting text that reads as a different tree."""
    t = strip_meta(task)
    for k in ("t", "name", "params", "returns", "requires", "ensures", "body"):
        if k not in t:
            raise SurfaceError("task is missing required field %r" % k)
    unknown = set(t) - {"t", "name", "params", "returns", "requires",
                        "ensures", "gate", "spec_funs", "decreases", "body"}
    if unknown:
        raise SurfaceError("task carries fields t does not define: %s"
                           % " ".join(sorted(unknown)))
    if t["t"] not in (0, 1):
        raise SurfaceError("format version must be 0 or 1, found %r" % t["t"])
    if len(t["returns"]) != 1:
        raise SurfaceError("a task returns exactly one value, found %d"
                           % len(t["returns"]))

    lines = ["t %d" % t["t"]]
    if "gate" in t:
        lines.append("gate %s" % _ident(t["gate"]))
    ps = ", ".join("%s: %s" % (_ident(p["name"]), _print_type(p["type"]))
                   for p in t["params"])
    r = t["returns"][0]
    lines.append("task %s(%s) returns (%s: %s)"
                 % (_ident(t["name"]), ps, _ident(r["name"]),
                    _print_type(r["type"])))
    for e in t["requires"]:
        lines.append("  requires %s" % pexpr(e))
    for e in t["ensures"]:
        lines.append("  ensures %s" % pexpr(e))
    if "decreases" in t:
        lines.append("  decreases %s" % pexpr(t["decreases"]))
    for fn in t.get("spec_funs", []):
        fps = ", ".join("%s: %s" % (_ident(p["name"]), _print_type(p["type"]))
                        for p in fn["params"])
        lines.append("spec fun %s(%s): %s" % (_ident(fn["name"]), fps,
                                              fn["result"]))
        lines.append("  decreases %s" % pexpr(fn["decreases"]))
        lines.append("= %s" % pexpr(fn["body"]))
    lines.append("{")
    lines += pstmts(t["body"], "  ")
    lines.append("}")
    return "\n".join(lines) + "\n"


# ===========================================================================
# 5. The measurement. Every number this file claims is produced here.
# ===========================================================================

# The `written:` lines of SYNTAX.md, each beside the JSON it annotates
# (9 through 2026-09-04, +2 char/string and +5 pairs/nested-seq by
# 2026-09-10, +6 the string library on 2026-09-11); --check reports the
# live count as `len(WRITTEN)`, so this comment need not be kept in sync.
# This table is what makes the grammar the DOCUMENTED notation rather than a
# new one that resembles it; --check parses each and compares to that JSON.
WRITTEN = [
    ("expr", "x < 0 ==> r == -x",
     {"op": "implies", "args": [
         {"op": "<", "args": [{"var": "x"}, {"int": 0}]},
         {"op": "==", "args": [{"var": "r"},
                               {"op": "neg", "args": [{"var": "x"}]}]}]}),
    ("stmt", "if x >= 0 { r := x } else { r := -x }",
     {"if": {"cond": {"op": ">=", "args": [{"var": "x"}, {"int": 0}]},
             "then": [{"assign": ["r", {"var": "x"}]}],
             "else": [{"assign": ["r", {"op": "neg",
                                        "args": [{"var": "x"}]}]}]}}),
    ("expr", "len(s)", {"op": "len", "args": [{"var": "s"}]}),
    ("expr", "s[i]", {"op": "at", "args": [{"var": "s"}, {"var": "i"}]}),
    ("expr", "forall i in [0, len(s)) . r >= s[i]",
     {"forall": {"var": "i", "lo": {"int": 0},
                 "hi": {"op": "len", "args": [{"var": "s"}]},
                 "body": {"op": ">=", "args": [
                     {"var": "r"},
                     {"op": "at", "args": [{"var": "s"}, {"var": "i"}]}]}}}),
    ("stmt", "var i: int := 1;",
     {"var": {"name": "i", "type": "int", "init": {"int": 1}}}),
    ("expr", "gcds(a, b)",
     {"call": {"fun": "gcds", "args": [{"var": "a"}, {"var": "b"}]}}),
    # SPEC.md "Strings as sequences of code points (v1)", added 2026-09-09.
    ("expr", "'a'", {"int": 97}),
    ("expr", '"abc"',
     {"op": "seq", "args": [{"int": 97}, {"int": 98}, {"int": 99}]}),
    # SPEC.md "Pairs (v1)", added 2026-09-10.
    ("expr", "(a, b)",
     {"op": "pair", "args": [{"var": "a"}, {"var": "b"}]}),
    ("expr", "p.0", {"op": "fst", "args": [{"var": "p"}]}),
    ("expr", "p.1", {"op": "snd", "args": [{"var": "p"}]}),
    ("stmt", "var r: (int, int) := (x, y);",
     {"var": {"name": "r", "type": {"pair": ["int", "int"]},
              "init": {"op": "pair", "args": [{"var": "x"}, {"var": "y"}]}}}),
    # SPEC.md "Nested sequences (v1)", added 2026-09-10.
    ("expr", "s[i][j]",
     {"op": "at", "args": [{"op": "at", "args": [{"var": "s"}, {"var": "i"}]},
                           {"var": "j"}]}),
    ("stmt", "var m: seq<seq> := [[1, 2], [3]];",
     {"var": {"name": "m", "type": {"seq": "seq"},
              "init": {"op": "seq", "args": [
                  {"op": "seq", "args": [{"int": 1}, {"int": 2}]},
                  {"op": "seq", "args": [{"int": 3}]}]}}}),
    ("stmt", "var m: seq<seq> := [];",
     {"var": {"name": "m", "type": {"seq": "seq"},
              "init": {"op": "seq", "args": []}}}),
    # SPEC.md "The string library (v1)", added 2026-09-11.
    ("expr", "s.split()", {"op": "split", "args": [{"var": "s"}]}),
    ("expr", "s.split(c)",
     {"op": "split", "args": [{"var": "s"}, {"var": "c"}]}),
    ("expr", "sep.join(rows)",
     {"op": "join", "args": [{"var": "rows"}, {"var": "sep"}]}),
    ("expr", "tostr(n)", {"op": "tostr", "args": [{"var": "n"}]}),
    ("expr", "s.count(u)",
     {"op": "count", "args": [{"var": "s"}, {"var": "u"}]}),
    ("expr", "s.strip().lower()",
     {"op": "lower", "args": [{"op": "strip", "args": [{"var": "s"}]}]}),
]

# Three more char/string probes (SPEC.md "Strings as sequences of code
# points (v1)"), checked differently from WRITTEN above: a char or string
# literal is sugar the printer never emits, so unlike every WRITTEN line its
# own text is not the canonical print of the AST it parses to. --check
# verifies both passes on these: the text parses to the stated AST (the
# first pass, the invariant given non-canonical text), and printing that
# AST and reparsing IT recovers the same AST (the second pass, always on
# canonical text, exactly as the docstring's two-pass description reads
# when the source is not already in canonical form).
LITERALS = [
    ("'a'", {"int": 97}),
    ('"ab" + "c"',
     {"op": "+", "args": [
         {"op": "seq", "args": [{"int": 97}, {"int": 98}]},
         {"op": "seq", "args": [{"int": 99}]}]}),
    ('""', {"op": "seq", "args": []}),
]


def _corpus(seeds, n):
    """The committed tasks (ROADMAP 14.1: t/tasks/*.t, read through this
    file's own parse rather than tasks_io, which imports this module and so
    cannot be imported back from it), then fuzz_lower's generator. Returns
    (well_formed, rejected_count, total_seen)."""
    here = os.path.dirname(os.path.abspath(__file__))
    good, seen, rejected = [], 0, 0
    for path in sorted(glob.glob(os.path.join(here, "tasks", "*.t"))):
        with open(path, encoding="utf-8") as fh:
            good.append((os.path.basename(path), parse(fh.read())))
        seen += 1
    if seeds:
        sys.path.insert(0, here)
        import fuzz_lower                                   # noqa: PLC0415
        for seed in seeds:
            for task in fuzz_lower.build_corpus(n, seed):
                seen += 1
                # check_wf is re-run rather than read off `_wf_errors`:
                # build_corpus clears that field for the fz_p_nodiv probe so
                # the lowerings still see it, and a task carrying an operator
                # t does not have is not a t task.
                if fuzz_lower.check_wf(task):
                    rejected += 1
                    continue
                good.append(("seed%d/%s" % (seed, task["name"]), task))
    return good, rejected, seen


# Shapes the notation must REFUSE. A parser that accepted more than the AST
# would be a second, undocumented language; these are the cases where that
# would be easiest to do by accident.
REFUSALS = [
    ("print", {"t": 0, "name": "d", "params": [], "returns":
               [{"name": "r", "type": "int"}], "requires": [], "ensures":
               [{"bool": True}], "body": [{"assign": ["r", {
                   "op": "/", "args": [{"int": 4}, {"int": 2}]}]}]},
     "the AST operator is the word div; a slash is not an operator name"),
    ("print", {"t": 0, "name": "a1", "params": [], "returns":
               [{"name": "r", "type": "bool"}], "requires": [], "ensures":
               [{"op": "and", "args": [{"bool": True}]}], "body":
               [{"assign": ["r", {"bool": True}]}]},
     "and at arity 1 has no notation"),
    ("print", {"t": 0, "name": "kw", "params":
               [{"name": "len", "type": "int"}], "returns":
               [{"name": "r", "type": "int"}], "requires": [], "ensures":
               [{"bool": True}], "body": [{"assign": ["r", {"int": 0}]}]},
     "a keyword cannot be a name"),
    ("parse", "t 1 task f(x: int) returns (r: int) ensures 1 == 2 == 3 { r := 0 }",
     "comparisons do not chain"),
    ("parse", "t 1 task f(x: int) returns (r: int) ensures x div 2 == 0 { r := 0 }",
     "div is written /, the word is the AST's and not the notation's"),
    ("parse", "t 1 task f(x: int) returns (r: int) ensures true { r := 0 } // done",
     "there are no comments"),
    ("print", {"t": 1, "name": "sk", "params":
               [{"name": "tostr", "type": "seq"}], "returns":
               [{"name": "r", "type": "seq"}], "requires": [], "ensures":
               [{"bool": True}], "body": [{"assign": ["r", {"var": "tostr"}]}]},
     "tostr is a keyword (SPEC.md \"The string library\") and cannot be a name"),
    ("parse", "t 1 task f(s: seq) returns (r: seq) ensures true { r := s.upcase(); }",
     "a dot is followed by .0, .1, or a string-library member; upcase is none"),
]


# ---------------------------------------------------------------------------
# A structural fuzzer over the AST itself, not over t's semantics. The corpus
# above is generated by fuzz_lower's nine families, and a family never emits
# some shapes the notation still has to survive: `implies` on the LEFT of
# `implies`, `not` of a quantifier, `and` nested directly in `and`, `neg` of
# `neg`, `at` of an `at`, an `ite` as a loop guard. Those are exactly the
# places a printer loses a tree. This generator is unconstrained by typing
# and by SPEC.md's well-formedness, because the notation is not a type
# checker: it must round trip any tree the grammar can describe.
# ---------------------------------------------------------------------------

_FUZZ_NAMES = ["x", "y", "s", "r", "i", "j", "n", "acc", "f", "g"]


def _rand_expr(rng, depth: int) -> dict:
    import random                                            # noqa: PLC0415
    assert isinstance(rng, random.Random)
    if depth <= 0:
        return rng.choice([
            lambda: {"int": rng.randint(-99, 99)},
            lambda: {"bool": rng.choice([True, False])},
            lambda: {"var": rng.choice(_FUZZ_NAMES)},
        ])()
    d = depth - 1
    kind = rng.choice([
        "int", "bool", "var", "bin", "cmp", "neg", "not", "andor", "implies",
        "len", "at", "update", "fill", "seq", "slice", "ite", "quant", "call",
        "pair", "fst", "snd", "strlib",
    ])
    if kind == "int":
        return {"int": rng.randint(-10 ** 9, 10 ** 9)}
    if kind == "bool":
        return {"bool": rng.choice([True, False])}
    if kind == "var":
        return {"var": rng.choice(_FUZZ_NAMES)}
    if kind == "bin":
        return {"op": rng.choice(["+", "-", "*", "div", "mod"]),
                "args": [_rand_expr(rng, d), _rand_expr(rng, d)]}
    if kind == "cmp":
        return {"op": rng.choice(sorted(CMP_OPS)),
                "args": [_rand_expr(rng, d), _rand_expr(rng, d)]}
    if kind == "neg":
        return {"op": "neg", "args": [_rand_expr(rng, d)]}
    if kind == "not":
        return {"op": "not", "args": [_rand_expr(rng, d)]}
    if kind == "andor":
        return {"op": rng.choice(["and", "or"]),
                "args": [_rand_expr(rng, d) for _ in range(rng.randint(2, 4))]}
    if kind == "implies":
        return {"op": "implies",
                "args": [_rand_expr(rng, d), _rand_expr(rng, d)]}
    if kind == "len":
        return {"op": "len", "args": [_rand_expr(rng, d)]}
    if kind == "at":
        return {"op": "at", "args": [_rand_expr(rng, d), _rand_expr(rng, d)]}
    if kind == "update":
        return {"op": "update", "args": [_rand_expr(rng, d), _rand_expr(rng, d),
                                         _rand_expr(rng, d)]}
    if kind == "fill":
        return {"op": "fill", "args": [_rand_expr(rng, d), _rand_expr(rng, d)]}
    if kind == "seq":
        return {"op": "seq", "args": [_rand_expr(rng, d)
                                      for _ in range(rng.randint(0, 3))]}
    if kind == "slice":
        return {"op": "slice", "args": [_rand_expr(rng, d), _rand_expr(rng, d),
                                        _rand_expr(rng, d)]}
    if kind == "pair":
        return {"op": "pair", "args": [_rand_expr(rng, d), _rand_expr(rng, d)]}
    if kind in ("fst", "snd"):
        return {"op": kind, "args": [_rand_expr(rng, d)]}
    if kind == "strlib":
        # SPEC.md "The string library (v1)", added 2026-09-11: 17 members,
        # `split` at two arities of its own op.
        op = rng.choice(["split1", "split2", "join", "tostr", "count",
                        "find", "strip", "lstrip", "rstrip", "replace",
                        "lower", "upper", "isdigit", "isalpha", "isupper",
                        "islower", "startswith", "endswith"])
        if op == "split1":
            return {"op": "split", "args": [_rand_expr(rng, d)]}
        if op == "split2":
            return {"op": "split",
                    "args": [_rand_expr(rng, d), _rand_expr(rng, d)]}
        if op == "replace":
            return {"op": "replace", "args": [_rand_expr(rng, d)
                                              for _ in range(3)]}
        if op in ("tostr", "strip", "lstrip", "rstrip", "lower", "upper",
                 "isdigit", "isalpha", "isupper", "islower"):
            return {"op": op, "args": [_rand_expr(rng, d)]}
        return {"op": op,                    # join, count, find,
                "args": [_rand_expr(rng, d),  # startswith, endswith
                        _rand_expr(rng, d)]}
    if kind == "ite":
        return {"ite": {"cond": _rand_expr(rng, d), "then": _rand_expr(rng, d),
                        "else": _rand_expr(rng, d)}}
    if kind == "quant":
        return {rng.choice(["forall", "exists"]):
                {"var": rng.choice(_FUZZ_NAMES), "lo": _rand_expr(rng, d),
                 "hi": _rand_expr(rng, d), "body": _rand_expr(rng, d)}}
    return {"call": {"fun": rng.choice(_FUZZ_NAMES),
                     "args": [_rand_expr(rng, d)
                              for _ in range(rng.randint(0, 3))]}}


def _rand_type(rng):
    """int/bool/seq, a pair of two of them (SPEC.md "Pairs", 2026-09-10), or
    a nested seq `seq<seq>` (SPEC.md "Nested sequences", 2026-09-10), so the
    round trip exercises `(T1, T2)` and `seq<seq>` in the same places it
    already exercises the base types: params, returns, locals. 0.25/0.1
    rather than an even split across three shapes: a pair's own `(T1, T2)`
    already carries two base-type draws so it needs the larger share to
    come up often enough on its own two slots; `seq<seq>` has no slots to
    fill, so one flat draw is enough to reach it as often as any one base
    type on its own."""
    r = rng.random()
    if r < 0.25:
        return {"pair": [rng.choice(["int", "bool", "seq"]),
                         rng.choice(["int", "bool", "seq"])]}
    if r < 0.35:
        return {"seq": "seq"}
    return rng.choice(["int", "bool", "seq"])


def _rand_stmts(rng, depth: int, k: int) -> list:
    out = []
    for _ in range(k):
        choice = rng.random()
        if depth <= 0 or choice < 0.5:
            out.append({"assign": [rng.choice(_FUZZ_NAMES),
                                   _rand_expr(rng, rng.randint(0, 3))]})
        elif choice < 0.65:
            out.append({"var": {"name": rng.choice(_FUZZ_NAMES),
                                "type": _rand_type(rng),
                                "init": _rand_expr(rng, 2)}})
        elif choice < 0.85:
            out.append({"if": {"cond": _rand_expr(rng, 2),
                               "then": _rand_stmts(rng, depth - 1,
                                                   rng.randint(0, 2)),
                               "else": _rand_stmts(rng, depth - 1,
                                                   rng.randint(0, 2))}})
        else:
            out.append({"while": {
                "cond": _rand_expr(rng, 2),
                "invariants": [_rand_expr(rng, 2)
                               for _ in range(rng.randint(0, 3))],
                "decreases": _rand_expr(rng, 2),
                "body": _rand_stmts(rng, depth - 1, rng.randint(1, 2))}})
    return out


def _rand_task(rng) -> dict:
    task = {"t": rng.choice([0, 1]), "name": rng.choice(_FUZZ_NAMES),
            "params": [{"name": nm, "type": _rand_type(rng)}
                       for nm in rng.sample(_FUZZ_NAMES, rng.randint(0, 3))],
            "returns": [{"name": rng.choice(_FUZZ_NAMES),
                         "type": _rand_type(rng)}],
            "requires": [_rand_expr(rng, 3) for _ in range(rng.randint(0, 2))],
            "ensures": [_rand_expr(rng, 3) for _ in range(rng.randint(1, 2))]}
    if rng.random() < 0.4:
        task["gate"] = rng.choice(["quantifiers", "loops", "recursion"])
    if rng.random() < 0.3:
        task["spec_funs"] = [
            {"name": rng.choice(_FUZZ_NAMES),
             "params": [{"name": nm, "type": rng.choice(["int", "seq"])}
                        for nm in rng.sample(_FUZZ_NAMES, rng.randint(0, 2))],
             "result": rng.choice(["int", "bool"]),
             "decreases": _rand_expr(rng, 2),
             "body": _rand_expr(rng, 3)}
            for _ in range(rng.randint(1, 2))]
    if rng.random() < 0.3:
        task["decreases"] = _rand_expr(rng, 2)
    task["body"] = _rand_stmts(rng, 2, rng.randint(1, 3))
    return task


def fuzz(count: int, seed: int, verbose: bool) -> int:
    import random                                            # noqa: PLC0415
    rng = random.Random(seed)
    fails = []
    for k in range(count):
        task = _rand_task(rng)
        try:
            text = print_task(task)
            back = parse(text)
        except SurfaceError as exc:
            fails.append(("ast#%d" % k, str(exc)))
            continue
        if canon(back) != canon(task):
            fails.append(("ast#%d" % k, "parse(print(t)) differs from t"))
        elif print_task(back) != text:
            fails.append(("ast#%d" % k, "print is not idempotent"))
    print("structural fuzz: %d random ASTs, seed %d, %d round trip"
          % (count, seed, count - len(fails)))
    for label, why in fails[:20 if not verbose else len(fails)]:
        print("  %-10s %s" % (label, why))
    return 1 if fails else 0


def check(seeds, n, verbose: bool) -> int:
    fails = []

    print("written: lines from SYNTAX.md")
    w_ok = 0
    for kind, text, want in WRITTEN:
        got = (parse_expr if kind == "expr" else parse_stmt)(text)
        if json.dumps(got, sort_keys=True) == json.dumps(want, sort_keys=True):
            w_ok += 1
        else:
            fails.append(("written:%s" % text, "parsed to %r" % (got,)))
    print("  %d of %d parse to the JSON they annotate" % (w_ok, len(WRITTEN)))

    print("\nchar/string literal probes")
    l_ok = 0
    for text, want in LITERALS:
        try:
            got = parse_expr(text)
        except SurfaceError as exc:
            fails.append(("literal:%s" % text, "parse: %s" % exc))
            continue
        if json.dumps(got, sort_keys=True) != json.dumps(want, sort_keys=True):
            fails.append(("literal:%s" % text, "parsed to %r" % (got,)))
            continue
        try:
            canon_text = pexpr(want)
            back = parse_expr(canon_text)
        except SurfaceError as exc:
            fails.append(("literal:%s" % text, "reparse of print: %s" % exc))
            continue
        if json.dumps(back, sort_keys=True) != json.dumps(want, sort_keys=True):
            fails.append(("literal:%s" % text,
                          "print %r reparses to %r" % (canon_text, back)))
            continue
        l_ok += 1
    print("  %d of %d parse to the stated AST and reparse from their "
          "canonical print" % (l_ok, len(LITERALS)))

    print("\nshapes the notation must refuse")
    r_ok = 0
    for kind, subject, why in REFUSALS:
        try:
            print_task(subject) if kind == "print" else parse(subject)
        except SurfaceError:
            r_ok += 1
        else:
            fails.append(("refusal:%s" % why, "accepted, and should not have"))
    print("  %d of %d refused" % (r_ok, len(REFUSALS)))

    good, rejected, seen = _corpus(seeds, n)
    print("\ncorpus: %d tasks seen, %d rejected by check_wf, %d well-formed "
          "(%d distinct)"
          % (seen, rejected, len(good), len({canon(t) for _, t in good})))

    rt_ok = idem_ok = 0
    for label, task in good:
        try:
            text = print_task(task)
        except SurfaceError as exc:
            fails.append((label, "print: %s" % exc))
            continue
        try:
            back = parse(text)
        except SurfaceError as exc:
            fails.append((label, "parse: %s" % exc))
            continue
        if canon(back) == canon(task):
            rt_ok += 1
        else:
            fails.append((label, "parse(print(t)) differs from t"))
            continue
        if print_task(back) == text:
            idem_ok += 1
        else:
            fails.append((label, "print(parse(text)) differs from text"))

    print("  parse(print(t)) == t          : %d of %d" % (rt_ok, len(good)))
    print("  print(parse(text)) == text    : %d of %d" % (idem_ok, len(good)))

    if fails:
        print("\n%d FAILURE(S):" % len(fails))
        for label, why in fails[:20 if not verbose else len(fails)]:
            print("  %-28s %s" % (label, why))
        if not verbose and len(fails) > 20:
            print("  ... %d more (--verbose for all)" % (len(fails) - 20))
        return 1
    print("\nround trip verified on %d tasks, no failures." % len(good))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="run the round trip over tasks/ and fuzz_lower")
    ap.add_argument("--print", dest="pr", metavar="TASK.json",
                    help="print one task as surface text")
    ap.add_argument("--parse", dest="pa", metavar="FILE.t",
                    help="parse surface text to canonical JSON")
    ap.add_argument("--seeds", default="1,2,3,4,5,6,7")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--fuzz", type=int, metavar="N",
                    help="round trip N random ASTs from the grammar itself")
    ap.add_argument("--fuzz-seed", type=int, default=1)
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    if a.fuzz:
        return fuzz(a.fuzz, a.fuzz_seed, a.verbose)

    if a.pr:
        with open(a.pr, encoding="utf-8") as fh:
            sys.stdout.write(print_task(json.load(fh)))
        return 0
    if a.pa:
        with open(a.pa, encoding="utf-8") as fh:
            print(json.dumps(parse(fh.read()), indent=2))
        return 0
    if a.check:
        seeds = [int(s) for s in a.seeds.split(",") if s.strip()]
        return check(seeds, a.n, a.verbose)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
