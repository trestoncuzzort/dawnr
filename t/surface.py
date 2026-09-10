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

  The 9 `written:` lines in SYNTAX.md parse, unedited, to the JSON they sit
  beside (two added 2026-09-09, one for the char and string literals below
  and one for sequence literals, concatenation and slices). That
  is the check that this grammar is the documented notation and not a new
  one that resembles it.

  6 of 6 shapes the notation must refuse are refused (REFUSALS, below):
  div, `and` at arity 1, a keyword used as a name, a chained comparison, `/`
  in the lexer, and a comment.

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
    """A text that is not in the language, or an AST with no notation."""


# ===========================================================================
# 2. Lexer.
# ===========================================================================

KEYWORDS = {
    "t", "gate", "task", "returns", "requires", "ensures", "decreases",
    "spec", "fun", "return", "var", "while", "invariant", "if", "then", "else",
    "forall", "exists", "in", "len", "true", "false", "and", "or", "not",
    "int", "bool", "seq",
}

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


class Tok:
    __slots__ = ("kind", "text", "pos", "line")

    def __init__(self, kind, text, pos, line):
        self.kind, self.text, self.pos, self.line = kind, text, pos, line

    def __repr__(self):
        return "%s(%r)" % (self.kind, self.text)


def _lex_quoted(src: str, i: int, line: int, quote: str):
    """Scan a char or string literal body, `i` just past the opening quote.
    Returns (code points, index just past the closing quote). A literal
    never spans a line, so `line` does not change: a bare newline or the
    end of input before the closing quote is the same "unterminated"
    error. Escapes: \\n \\t \\r \\0 \\' \\" \\\\, plus \\u{H...H} (1 to 6
    hex digits) for any other code point."""
    n = len(src)
    pts = []
    while True:
        if i >= n or src[i] == "\n":
            raise SurfaceError("line %d: unterminated literal" % line)
        c = src[i]
        if c == quote:
            return pts, i + 1
        if c == "\\":
            if i + 1 >= n or src[i + 1] == "\n":
                raise SurfaceError("line %d: unterminated literal" % line)
            e = src[i + 1]
            if e == "u":
                j = i + 2
                if j >= n or src[j] != "{":
                    raise SurfaceError(
                        "line %d: bad escape \\u, expected \\u{HEX}" % line)
                j += 1
                k = j
                while k < n and k - j < 6 and src[k] in _HEXDIGIT:
                    k += 1
                if k == j:
                    raise SurfaceError(
                        "line %d: \\u{} needs at least one hex digit" % line)
                if k >= n or src[k] != "}":
                    raise SurfaceError(
                        "line %d: \\u{...} escape missing closing }" % line)
                cp = int(src[j:k], 16)
                if cp > MAX_CODE_POINT:
                    raise SurfaceError(
                        "line %d: \\u{%s} exceeds the maximum code point %d"
                        % (line, src[j:k], MAX_CODE_POINT))
                pts.append(cp)
                i = k + 1
                continue
            if e in _ESCAPES:
                pts.append(_ESCAPES[e])
                i += 2
                continue
            raise SurfaceError("line %d: bad escape \\%s" % (line, e))
        pts.append(ord(c))
        i += 1


def lex(src: str) -> list:
    """kinds: id, kw, nat, char, str, sym, eof. No comments: see the
    docstring. `char` and `str` tokens carry the decoded value directly
    (an int, a list of ints) rather than the source text: SurfaceError on
    an unterminated literal, a bad escape, or a char literal that does not
    hold exactly one code point."""
    toks, i, line, n = [], 0, 1, len(src)
    while i < n:
        c = src[i]
        if c in " \t\r":
            i += 1
            continue
        if c == "\n":
            line += 1
            i += 1
            continue
        if c == "'":
            start = i
            pts, i = _lex_quoted(src, i + 1, line, "'")
            if len(pts) != 1:
                raise SurfaceError(
                    "line %d: a char literal holds exactly one code point, "
                    "found %d" % (line, len(pts)))
            toks.append(Tok("char", pts[0], start, line))
            continue
        if c == '"':
            start = i
            pts, i = _lex_quoted(src, i + 1, line, '"')
            toks.append(Tok("str", pts, start, line))
            continue
        m = _ID.match(src, i)
        if m:
            w = m.group(0)
            toks.append(Tok("kw" if w in KEYWORDS else "id", w, i, line))
            i = m.end()
            continue
        m = _NAT.match(src, i)
        if m:
            toks.append(Tok("nat", m.group(0), i, line))
            i = m.end()
            continue
        for s in SYMBOLS:
            if src.startswith(s, i):
                toks.append(Tok("sym", s, i, line))
                i += len(s)
                break
        else:
            raise SurfaceError("line %d: unexpected character %r" % (line, c))
    toks.append(Tok("eof", "", n, line))
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


class Parser:
    def __init__(self, src: str):
        self.ret_name = None      # set by program(); a bare stmt has no task
        self.toks = lex(src)
        self.i = 0

    # -- token plumbing ----------------------------------------------------

    @property
    def tok(self) -> Tok:
        return self.toks[self.i]

    def at(self, kind: str, text=None) -> bool:
        t = self.tok
        return t.kind == kind and (text is None or t.text == text)

    def eat(self, kind: str, text=None) -> Tok:
        t = self.tok
        if not self.at(kind, text):
            want = text if text is not None else kind
            raise SurfaceError("line %d: expected %r, found %r"
                               % (t.line, want, t.text or "end of input"))
        self.i += 1
        return t

    def opt(self, kind: str, text=None) -> bool:
        if self.at(kind, text):
            self.i += 1
            return True
        return False

    def name(self) -> str:
        return self.eat("id").text

    def vtype(self, allowed=VAL_TYPES) -> str:
        t = self.eat("kw")
        if t.text not in allowed:
            raise SurfaceError("line %d: %r is not one of %s"
                               % (t.line, t.text, " ".join(allowed)))
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
        if self.at("sym", "("):
            self.eat("sym", "(")
            t1 = self.vtype()
            self.eat("sym", ",")
            t2 = self.vtype()
            self.eat("sym", ")")
            return {"pair": [t1, t2]}
        t = self.vtype()
        if t == "seq" and self.opt("sym", "<"):
            self.eat("kw", "seq")
            self.eat("sym", ">")
            return {"seq": "seq"}
        return t

    # -- program -----------------------------------------------------------

    def program(self) -> dict:
        self.eat("kw", "t")
        ver = int(self.eat("nat").text)
        if ver not in (0, 1):
            raise SurfaceError("format version must be 0 or 1, found %d" % ver)
        task = {"t": ver}
        if self.opt("kw", "gate"):
            task["gate"] = self.name()
        self.eat("kw", "task")
        task["name"] = self.name()
        task["params"] = self.params()
        self.eat("kw", "returns")
        self.eat("sym", "(")
        rname = self.name()
        self.ret_name = rname
        self.eat("sym", ":")
        rtype = self.ptype()
        self.eat("sym", ")")
        task["returns"] = [{"name": rname, "type": rtype}]

        requires, ensures, dec = [], [], None
        while self.tok.kind == "kw" and self.tok.text in (
                "requires", "ensures", "decreases"):
            what = self.eat("kw").text
            e = self.expr()
            if what == "requires":
                requires.append(e)
            elif what == "ensures":
                ensures.append(e)
            else:
                if dec is not None:
                    raise SurfaceError("line %d: a task has at most one "
                                       "decreases" % self.tok.line)
                dec = e
        task["requires"] = requires
        task["ensures"] = ensures

        funs = []
        while self.at("kw", "spec"):
            funs.append(self.spec_fun())
        if funs:
            task["spec_funs"] = funs
        if dec is not None:
            task["decreases"] = dec
        task["body"] = self.block()
        self.eat("eof")
        return task

    def params(self) -> list:
        self.eat("sym", "(")
        out = []
        if not self.at("sym", ")"):
            while True:
                pn = self.name()
                self.eat("sym", ":")
                out.append({"name": pn, "type": self.ptype()})
                if not self.opt("sym", ","):
                    break
        self.eat("sym", ")")
        return out

    def spec_fun(self) -> dict:
        self.eat("kw", "spec")
        self.eat("kw", "fun")
        fn = {"name": self.name(), "params": self.params()}
        self.eat("sym", ":")
        fn["result"] = self.vtype(("int", "bool"))
        self.eat("kw", "decreases")
        fn["decreases"] = self.expr()
        self.eat("sym", "=")
        fn["body"] = self.expr()
        return fn

    # -- statements --------------------------------------------------------

    def block(self) -> list:
        self.eat("sym", "{")
        out = []
        while not self.at("sym", "}"):
            if self.at("eof"):
                raise SurfaceError("line %d: unterminated block"
                                   % self.tok.line)
            out.append(self.stmt())
        self.eat("sym", "}")
        return out

    def stmt(self) -> dict:
        t = self.tok
        if self.opt("kw", "return"):
            # SPEC.md "Early exit" (2026-09-08): the AST names the task's
            # return variable, as assign does, so the interpreter needs no
            # context to run it; the notation fills the name from the header.
            if self.ret_name is None:
                raise SurfaceError("line %d: return outside a task" % t.line)
            e = self.expr()
            self.opt("sym", ";")
            return {"return": [self.ret_name, e]}
        if t.kind == "id":
            target = self.name()
            self.eat("sym", ":=")
            e = self.expr()
            self.opt("sym", ";")
            return {"assign": [target, e]}
        if self.opt("kw", "var"):
            vn = self.name()
            self.eat("sym", ":")
            ty = self.ptype()
            self.eat("sym", ":=")
            init = self.expr()
            self.opt("sym", ";")
            return {"var": {"name": vn, "type": ty, "init": init}}
        if self.opt("kw", "if"):
            cond = self.expr()
            then = self.block()
            self.eat("kw", "else")
            els = self.block()
            return {"if": {"cond": cond, "then": then, "else": els}}
        if self.opt("kw", "while"):
            cond = self.expr()
            invs = []
            while self.opt("kw", "invariant"):
                invs.append(self.expr())
            self.eat("kw", "decreases")
            dec = self.expr()
            body = self.block()
            return {"while": {"cond": cond, "invariants": invs,
                              "decreases": dec, "body": body}}
        raise SurfaceError("line %d: %r does not start a statement"
                           % (t.line, t.text or "end of input"))

    # -- expressions -------------------------------------------------------

    def expr(self) -> dict:
        """The lowest level: quantifiers and ite, whose bodies run to the
        right as far as they can, then implies."""
        if self.at("kw", "forall") or self.at("kw", "exists"):
            kind = self.eat("kw").text
            v = self.name()
            self.eat("kw", "in")
            self.eat("sym", "[")
            lo = self.expr()
            self.eat("sym", ",")
            hi = self.expr()
            self.eat("sym", ")")            # half-open range, SPEC.md gate 1
            self.eat("sym", ".")
            return {kind: {"var": v, "lo": lo, "hi": hi, "body": self.expr()}}
        if self.opt("kw", "if"):
            cond = self.expr()
            self.eat("kw", "then")
            then = self.expr()
            self.eat("kw", "else")
            return {"ite": {"cond": cond, "then": then, "else": self.expr()}}
        return self.p_implies()

    def p_implies(self) -> dict:
        left = self.p_or()
        if self.opt("sym", "==>"):
            right = self.expr() if (self.at("kw", "forall")
                                    or self.at("kw", "exists")
                                    or self.at("kw", "if")) else self.p_implies()
            return {"op": "implies", "args": [left, right]}
        return left

    def p_or(self) -> dict:
        args = [self.p_and()]
        while self.opt("kw", "or"):
            args.append(self.p_and())
        return args[0] if len(args) == 1 else {"op": "or", "args": args}

    def p_and(self) -> dict:
        args = [self.p_not()]
        while self.opt("kw", "and"):
            args.append(self.p_not())
        return args[0] if len(args) == 1 else {"op": "and", "args": args}

    def p_not(self) -> dict:
        if self.opt("kw", "not"):
            return {"op": "not", "args": [self.p_not()]}
        return self.p_cmp()

    def p_cmp(self) -> dict:
        left = self.p_add()
        if self.tok.kind == "sym" and self.tok.text in CMP_OPS:
            op = self.eat("sym").text
            right = self.p_add()
            if self.tok.kind == "sym" and self.tok.text in CMP_OPS:
                raise SurfaceError("line %d: comparisons do not chain; "
                                   "parenthesise" % self.tok.line)
            return {"op": op, "args": [left, right]}
        return left

    def p_add(self) -> dict:
        left = self.p_mul()
        while self.tok.kind == "sym" and self.tok.text in ("+", "-"):
            op = self.eat("sym").text
            left = {"op": op, "args": [left, self.p_mul()]}
        return left

    def p_mul(self) -> dict:
        left = self.p_unary()
        while self.at("sym", "*") or self.at("sym", "/") or self.at("sym", "%"):
            sym = self.toks[self.i].text
            self.eat("sym", sym)
            left = {"op": _MUL_OPS[sym], "args": [left, self.p_unary()]}
        return left

    def p_unary(self) -> dict:
        if self.opt("sym", "-"):
            # `-5` is the literal; `-(5)` is neg of the literal. See the
            # docstring: both nodes are live in the corpus.
            if self.tok.kind == "nat":
                return {"int": -int(self.eat("nat").text)}
            return {"op": "neg", "args": [self.p_unary()]}
        return self.p_postfix()

    def p_postfix(self) -> dict:
        e = self.p_atom()
        while True:
            if self.opt("sym", "["):
                if self.opt("sym", ".."):
                    # s[..b] is s[0..b] (SPEC.md "Sequences: literals,
                    # concatenation, slices"): sugar the parser expands, the
                    # AST carries the three-argument slice only.
                    hi = self.expr()
                    self.eat("sym", "]")
                    e = {"op": "slice", "args": [e, {"int": 0}, hi]}
                    continue
                idx = self.expr()
                if self.opt("sym", ":="):
                    val = self.expr()
                    self.eat("sym", "]")
                    e = {"op": "update", "args": [e, idx, val]}
                    continue
                if self.opt("sym", ".."):
                    if self.opt("sym", "]"):
                        # s[a..] is s[a..len(s)].
                        e = {"op": "slice",
                             "args": [e, idx, {"op": "len", "args": [e]}]}
                        continue
                    hi = self.expr()
                    self.eat("sym", "]")
                    e = {"op": "slice", "args": [e, idx, hi]}
                    continue
                self.eat("sym", "]")
                e = {"op": "at", "args": [e, idx]}
                continue
            if self.opt("sym", "."):
                # p.0 / p.1: the pair projections (SPEC.md "Pairs",
                # 2026-09-10). The lexer already tokenises "." and a
                # following NAT separately (there is no float literal in t
                # to collide with), so `.` here is unambiguously a
                # projection and not a decimal point; only these two digits
                # are the grammar, exactly as `and` at arity 1 has none.
                tok = self.eat("nat")
                if tok.text not in ("0", "1"):
                    raise SurfaceError("line %d: a pair projection is .0 "
                                       "or .1, found .%s"
                                       % (tok.line, tok.text))
                e = {"op": "fst" if tok.text == "0" else "snd", "args": [e]}
                continue
            break
        return e

    def p_atom(self) -> dict:
        t = self.tok
        if t.kind == "nat":
            return {"int": int(self.eat("nat").text)}
        if t.kind == "char":
            # 'a': sugar for its code point (SPEC.md "Strings as sequences
            # of code points (v1)"). The printer never emits this form.
            return {"int": self.eat("char").text}
        if t.kind == "str":
            # "abc": sugar for the seq literal of its code points; "" is
            # []. Same spec section; same non-canonical relationship to
            # the printer.
            return {"op": "seq",
                    "args": [{"int": cp} for cp in self.eat("str").text]}
        if self.at("kw", "true"):
            self.eat("kw")
            return {"bool": True}
        if self.at("kw", "false"):
            self.eat("kw")
            return {"bool": False}
        if self.at("kw", "len"):
            self.eat("kw")
            self.eat("sym", "(")
            e = self.expr()
            self.eat("sym", ")")
            return {"op": "len", "args": [e]}
        if self.at("kw", "seq"):
            # seq(n, v), the `fill` constructor (SPEC.md "Sequences as values").
            self.eat("kw")
            self.eat("sym", "(")
            n = self.expr()
            self.eat("sym", ",")
            v = self.expr()
            self.eat("sym", ")")
            return {"op": "fill", "args": [n, v]}
        if self.opt("sym", "("):
            e = self.expr()
            if self.opt("sym", ","):
                # (e1, e2): the pair literal (SPEC.md "Pairs", 2026-09-10).
                # `(e)` alone, no comma, stays grouping, as it always was.
                e2 = self.expr()
                self.eat("sym", ")")
                return {"op": "pair", "args": [e, e2]}
            self.eat("sym", ")")
            return e
        if self.opt("sym", "["):
            # [e1, ..., en], the sequence literal; [] the empty sequence
            # (SPEC.md "Sequences: literals, concatenation, slices").
            args = []
            if not self.at("sym", "]"):
                while True:
                    args.append(self.expr())
                    if not self.opt("sym", ","):
                        break
            self.eat("sym", "]")
            return {"op": "seq", "args": args}
        if t.kind == "id":
            ident = self.name()
            if self.opt("sym", "("):
                args = []
                if not self.at("sym", ")"):
                    while True:
                        args.append(self.expr())
                        if not self.opt("sym", ","):
                            break
                self.eat("sym", ")")
                return {"call": {"fun": ident, "args": args}}
            return {"var": ident}
        raise SurfaceError("line %d: %r does not start an expression"
                           % (t.line, t.text or "end of input"))


def parse(src: str) -> dict:
    return Parser(src).program()


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
          "pair": 2, "fst": 1, "snd": 1}


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

# The nine `written:` lines of SYNTAX.md, each beside the JSON it annotates.
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
    """The 11 committed tasks, then fuzz_lower's generator. Returns
    (well_formed, rejected_count, total_seen)."""
    here = os.path.dirname(os.path.abspath(__file__))
    good, seen, rejected = [], 0, 0
    for path in sorted(glob.glob(os.path.join(here, "tasks", "*.json"))):
        with open(path, encoding="utf-8") as fh:
            good.append((os.path.basename(path), json.load(fh)))
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
        "pair", "fst", "snd",
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
