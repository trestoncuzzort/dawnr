#!/usr/bin/env python3
r"""t/lift_acsl.py -- a C/ACSL front end for the lifter (2026-09-26).

Reads one C function with its ACSL contract, loop annotations and the named
logic definitions it uses (the shape of ACSL by Example,
github.com/fraunhoferfokus/acsl-by-example, MIT), and writes the Dafny method
the lifter already reads. `t/lifter.py` then parses it into its own
intermediate form (lift_ast, via `dafny resolve`, which also type-checks the
translation) and rewrites it into a t task exactly as it does a Dafny
source. Nothing in the shared lifter modules changes for this: the front end
is this file, and the checks that tie the lift back to the C source are
`t/lift_acsl_check.py`.

    python3 t/lift_acsl.py FILE.c [--root StandardAlgorithms]     # print the Dafny, or the refusal

The semantics this relies on are the ACSL manual's
(github.com/acsl-language/acsl, speclang_modern.tex, fetched 2026-09-26 under
research receipt 4ba9253bafdb), section by section:

* "Integer arithmetic and machine integers": every arithmetic operation in a
  logic expression is over mathematical integers and a C integral value is
  promoted to one, so an ACSL clause already means what the same clause means
  in t. Division and modulo truncate toward zero (C99), which is NOT t's
  Euclidean div/mod: a `/` or `%` is lifted only when both operands have an
  unsigned C type, where the two agree (and the lifted document keeps the
  operands' non-negativity as `nat` obligations the kernels prove), and is
  refused `signed-division` otherwise.
* The C CODE is machine arithmetic. ACSL by Example proves every example with
  `-wp-rte -warn-unsigned-overflow -warn-unsigned-downcast`
  (StandardAlgorithms/Config/verify-local.mk), so on the precondition's domain
  no signed or unsigned operation overflows or wraps, and there the machine
  body and the mathematical body compute the same values. The lifted program
  is that mathematical reading. Two consequences, both explicit:
    - `unsigned`/`size_type` becomes `nat` (lower bound kept as a proof
      obligation: the lifter inserts `invariant v >= 0` for a nat local and
      `requires`/`ensures` for a nat parameter or result), so a lift that
      needed wrap-around cannot verify;
    - the upper bounds of C types (INT_MAX, UINT_MAX) are not added: the lifted
      theorem is the source's generalized to unbounded integers, and it is
      re-proved from scratch by seven kernels, so it is true; the source's
      theorem is its restriction to machine ranges. Recorded per task as the
      clause `machine-int-generalized`. Where the source itself states range
      facts (AccumulateBounds), they are part of its requires and are lifted.
* "Quantification on C integral types": `\forall int x` ranges over the
  type's interval; only `integer` binders are lifted (`typed-quantifier`).
* "Pre- and Post-state": a formal parameter in `ensures` denotes its
  pre-state value. A parameter the body assigns (accumulate's `init`) is
  therefore split: the parameter becomes `<p>0` (the pre-state value, what the
  contract and `\at(p, Pre)` mean) and a local `p` copies it, so the body text
  is unchanged.
* "Simple function contracts" and "Contracts with named behaviors": the
  contract is `P && (A_i ==> R_i)` before and `\old(A_i) ==> E_i` after; a
  behavior's `assigns` must be `\nothing` like the function's. `complete
  behaviors` / `disjoint behaviors` are obligations about the specification,
  not about the function ("Completeness of behaviors"), and are dropped with
  a record.
* "Loop invariants and loop assigns": a `for (init; c; step) s` invariant
  holds after `init` and is preserved by `c; s; step`, which is exactly the
  `init; while c { s; step }` this file emits; a `continue` would skip `step`
  and is refused. "Loop variants": `loop variant m` is t's `decreases m`.
  `loop assigns` of scalars restates the frame t already has and is dropped.
* "Memory" / `\valid_read(a + (0..n-1))`: a read-only pointer with that
  precondition becomes a `seq` parameter and `n` becomes `len(a)` everywhere.
  A second array valid over the same `n` gets `requires len(b) == len(a)`
  (the function cannot read past `n`, so no behaviour is lost). A pointer the
  function may write (`\valid`, non-`const`, or any `assigns` other than
  `\nothing`) is refused `array-write`: t has no heap. Aliasing between two
  read-only arrays is unobservable (nothing is written), so it is not an
  obligation here.
* "Semantics": ACSL logic is two-valued and total (an out-of-range `a[i]` is
  some value), t's is not (`at` outside [0, len) is undefined). A named
  predicate or logic function without recursion is therefore expanded at its
  use (capture-avoiding substitution), where t's definedness rules apply to
  the expanded clause under the clause's own context. A RECURSIVE logic
  function becomes a spec_fun whose array reads are guarded
  (`if 0 <= k < len(a) then a[k] else 0`), because t checks a spec_fun body
  for every argument; `t/lift_acsl_check.py` proves the guard changes nothing
  where the lift calls it (the function's domain, closed under its own
  recursion and containing every call site).

Everything else in the subset is refused by name (`Refusal.reason`); those
counts are what `t/LIFT-ACSL-BY-EXAMPLE.md` reports. Standard library only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ----------------------------------------------------------------- refusals --


class AcslRefusal(Exception):
    """A construct this front end does not lift, by name. `reason` is the census key."""

    def __init__(self, reason: str, detail: str = "", where: str = ""):
        super().__init__(f"{reason}: {detail} {where}".strip())
        self.reason = reason
        self.detail = detail
        self.where = where


# -------------------------------------------------------------------- lexer --

@dataclass
class Tok:
    kind: str          # id | num | op | annot | dir | eof
    text: str
    file: str = ""
    line: int = 0
    block: bool = True  # annot: /*@ ... */ (True) or //@ ... (False)

    def at(self) -> str:
        return f"{Path(self.file).name}:{self.line}" if self.file else f"line {self.line}"


OPS = sorted("""<==> <--> ==> --> ... .. -> ++ -- += -= *= /= %= &= |= ^= <<= >>= << >> <= >= == != && || ^^
+ - * / % < > = ! ~ & | ^ ? : ; , . ( ) [ ] { } # \\""".split(), key=len, reverse=True)
ID_RE = re.compile(r"\\?[A-Za-z_][A-Za-z0-9_]*")
NUM_RE = re.compile(r"(0[xX][0-9a-fA-F]+|[0-9]+)([uUlL]*)")


def scan(text: str, file: str = "", line0: int = 1, annot_mode: bool = False) -> list[Tok]:
    """C tokens, with preprocessor directives as `dir` tokens and ACSL annotations
    (`/*@ ... */`, `//@ ...`) as `annot` tokens holding their inner text. In
    annot_mode (lexing an annotation's own text) comments are C++ style only and
    `@` is white space (ACSL manual, "Lexical rules")."""
    toks: list[Tok] = []
    i, n, line = 0, len(text), line0
    at_line_start = True
    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
            i += 1
            at_line_start = True
            continue
        if c in " \t\r\f\v" or (annot_mode and c == "@"):
            i += 1
            continue
        if c == "#" and at_line_start and not annot_mode:
            j = i
            buf = []
            while j < n and text[j] != "\n":
                if text[j] == "\\" and j + 1 < n and text[j + 1] == "\n":
                    j += 2
                    line += 1
                    continue
                buf.append(text[j])
                j += 1
            toks.append(Tok("dir", "".join(buf), file, line))
            i = j
            continue
        at_line_start = False
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            if j < 0:
                raise AcslRefusal("source-unparseable", "unterminated comment", f"{file}:{line}")
            body = text[i + 2:j]
            if body.startswith("@") and not annot_mode:
                toks.append(Tok("annot", body[1:], file, line, True))
            line += body.count("\n")
            i = j + 2
            continue
        if text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            body = text[i + 2:j]
            if body.startswith("@") and not annot_mode:
                toks.append(Tok("annot", body[1:], file, line, False))
            i = j
            continue
        if c == '"' or c == "'":
            # kept as a token: refused where a lifted function uses one, not in the
            # rest of the unit (an SV-COMP harness's reach_error has one)
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == "\\" else 1
            toks.append(Tok("str", text[i:j + 1], file, line))
            i = j + 1
            continue
        m = ID_RE.match(text, i)
        if m:
            toks.append(Tok("id", m.group(0), file, line))
            i = m.end()
            continue
        m = NUM_RE.match(text, i)
        if m:
            toks.append(Tok("num", m.group(0), file, line))
            i = m.end()
            continue
        for op in OPS:
            if text.startswith(op, i):
                toks.append(Tok("op", op, file, line))
                i += len(op)
                break
        else:
            raise AcslRefusal("source-unparseable", f"character {c!r}", f"{file}:{line}")
    return toks


def num_value(text: str) -> int:
    m = NUM_RE.fullmatch(text)
    digits = m.group(1)
    return int(digits, 16) if digits[:2].lower() == "0x" else int(digits, 10)


# ------------------------------------------------------------- preprocessor --

# <limits.h>, as the corpus's typedefs.h uses it (int is 32-bit on every
# platform the corpus is proved for: Frama-C's default machdep x86_64).
BUILTIN_MACROS = {
    "INT_MAX": "2147483647", "INT_MIN": "(-2147483647-1)", "UINT_MAX": "4294967295u",
    "SHRT_MAX": "32767", "SHRT_MIN": "(-32767-1)", "USHRT_MAX": "65535",
    "CHAR_BIT": "8",
}


@dataclass
class Unit:
    """A preprocessed translation unit: C tokens (annotations inline) and the
    object-like macros defined, for expanding inside annotations the way
    Frama-C's -pp-annot does."""
    toks: list[Tok]
    macros: dict[str, list[Tok]]
    files: list[str]


STD_HEADERS = {"limits.h", "stddef.h", "stdint.h", "stdbool.h", "stdlib.h", "string.h"}


class Preprocessor:
    """Enough of cpp for this corpus: `#include "x"` (once per file, every header
    here has a guard), `#ifndef/#ifdef/#if 0|1|defined(X)/#else/#endif`,
    object-like `#define`. A function-like macro is refused when used."""

    def __init__(self, search: list[Path]):
        self.search = [Path(p) for p in search]
        self.macros: dict[str, list[Tok]] = {k: scan(v) for k, v in BUILTIN_MACROS.items()}
        self.fn_macros: set[str] = set()
        self.included: set[Path] = set()
        self.files: list[str] = []

    def find(self, name: str, near: Path) -> Path:
        for d in [near.parent] + self.search:
            p = d / name
            if p.is_file():
                return p.resolve()
        raise AcslRefusal("include-missing", name, str(near))

    def run(self, path: Path) -> Unit:
        out = self._file(Path(path).resolve())
        return Unit(self.expand(out), self.macros, self.files)

    def expand(self, toks: list[Tok], depth: int = 0) -> list[Tok]:
        if depth > 20:
            raise AcslRefusal("macro", "recursive macro")
        res: list[Tok] = []
        for t in toks:
            if t.kind == "id" and t.text in self.macros:
                body = [Tok(b.kind, b.text, t.file, t.line) for b in self.macros[t.text]]
                res.extend(self.expand(body, depth + 1))
            elif t.kind == "id" and t.text in self.fn_macros:
                raise AcslRefusal("macro-function", t.text, t.at())
            else:
                res.append(t)
        return res

    def _cond(self, expr: str, where: str) -> bool:
        e = expr.strip()
        m = re.fullmatch(r"!?\s*defined\s*\(?\s*(\w+)\s*\)?", e)
        if m:
            v = m.group(1) in self.macros or m.group(1) in self.fn_macros
            return (not v) if e.startswith("!") else v
        if e in ("0", "1"):
            return e == "1"
        raise AcslRefusal("preprocessor", f"#if {e}", where)

    def _file(self, path: Path) -> list[Tok]:
        if path in self.included:
            return []
        self.included.add(path)
        self.files.append(str(path))
        toks = scan(path.read_text(encoding="utf-8", errors="replace"), str(path))
        out: list[Tok] = []
        stack: list[list[bool]] = []   # [taking, some branch taken]

        def live() -> bool:
            return all(s[0] for s in stack)

        for t in toks:
            if t.kind != "dir":
                if live():
                    out.append(t)
                continue
            d = t.text.lstrip("#").strip()
            word, _, rest = d.partition(" ")
            rest = rest.strip()
            if word in ("ifndef", "ifdef"):
                on = (rest in self.macros or rest in self.fn_macros)
                on = (not on) if word == "ifndef" else on
                stack.append([on, on])
            elif word == "if":
                on = self._cond(rest, t.at()) if live() else False
                stack.append([on, on])
            elif word == "elif":
                if not stack:
                    raise AcslRefusal("preprocessor", "#elif without #if", t.at())
                on = (not stack[-1][1]) and self._cond(rest, t.at())
                stack[-1] = [on, stack[-1][1] or on]
            elif word == "else":
                if not stack:
                    raise AcslRefusal("preprocessor", "#else without #if", t.at())
                stack[-1] = [not stack[-1][1], True]
            elif word == "endif":
                if not stack:
                    raise AcslRefusal("preprocessor", "#endif without #if", t.at())
                stack.pop()
            elif not live():
                continue
            elif word == "include":
                if rest.startswith('"'):
                    name = rest.strip('"')
                    if name in STD_HEADERS and not any((d / name).is_file() for d in [path.parent] + self.search):
                        continue      # a system header spelled with quotes (iota.h's "limits.h")
                    out.extend(self._file(self.find(name, path)))
                # <system> headers: limits.h's macros are built in; nothing else is used
            elif word == "define":
                m = re.match(r"(\w+)(\()?", rest)
                if not m:
                    raise AcslRefusal("preprocessor", d, t.at())
                name = m.group(1)
                if m.group(2):
                    self.fn_macros.add(name)
                else:
                    self.macros[name] = scan(rest[len(name):], str(path), t.line)
            elif word in ("undef",):
                self.macros.pop(rest, None)
            elif word in ("pragma", "error", "warning", ""):
                if word == "error":
                    raise AcslRefusal("preprocessor", d, t.at())
            else:
                raise AcslRefusal("preprocessor", d, t.at())
        if stack:
            raise AcslRefusal("preprocessor", "unterminated #if", str(path))
        return out


# ---------------------------------------------------------------------- AST --
# One tuple-free node type keeps the printers short: kind plus fields in `a`.

@dataclass
class E:
    k: str
    a: tuple = ()
    line: int = 0

    def __repr__(self):
        return f"E({self.k}, {self.a})"


def walk(e, fn):
    """Pre-order visit of every E under e (tuples/lists descended)."""
    if isinstance(e, E):
        fn(e)
        for x in e.a:
            walk(x, fn)
    elif isinstance(e, (tuple, list)):
        for x in e:
            walk(x, fn)


# Node kinds:
#   int(v)  bool(v)  var(name)  result()  un(op, x)  bin(op, l, r)  chain(ops, operands)
#   ite(c, t, e)  index(base, i)  call(name, labels, args)  quant(kind, binders, body)
#   at(x, label)  old(x)  cast(ctype, x)  valid(kind, base, lo, hi)  sep(args)
#   let(name, value, body)  member(base, name, arrow)  cbuiltin(name, args)
#   assign(op, lhs, rhs)  incr(op, lhs, prefix)   (C expressions with side effects)

LOGIC_BUILTINS = {"\\abs", "\\max", "\\min"}
REL_OPS = ("<", "<=", ">", ">=", "==", "!=")

# C base types seen in this corpus, by the words that spell them.
C_TYPES = {
    ("int",): ("int", True), ("signed", "int"): ("int", True), ("signed",): ("int", True),
    ("unsigned", "int"): ("int", False), ("unsigned",): ("int", False),
    ("short",): ("short", True), ("short", "int"): ("short", True),
    ("unsigned", "short"): ("short", False), ("unsigned", "short", "int"): ("short", False),
    ("long",): ("long", True), ("long", "int"): ("long", True),
    ("unsigned", "long"): ("long", False), ("char",): ("char", True), ("unsigned", "char"): ("char", False),
    ("void",): ("void", None),
    ("long", "long"): ("long", True), ("long", "long", "int"): ("long", True),
    ("unsigned", "long", "long"): ("long", False), ("unsigned", "long", "long", "int"): ("long", False),
    ("signed", "char"): ("char", True),
}


@dataclass(frozen=True)
class CType:
    """kind: int | bool | void | ptr | struct | integer | boolean (the last two logic).
    `signed` for int; `elem` for ptr; `const` for the pointee; `name` for a typedef
    or struct name as written."""
    kind: str
    signed: Optional[bool] = None
    width: str = ""
    elem: Optional["CType"] = None
    const: bool = False
    name: str = ""

    def is_int(self) -> bool:
        return self.kind in ("int", "integer")

    def is_unsigned(self) -> bool:
        return self.kind == "int" and self.signed is False

    def show(self) -> str:
        if self.kind == "ptr":
            return ("const " if self.const else "") + self.elem.show() + "*"
        return self.name or (self.width if self.kind == "int" else self.kind)


INTEGER = CType("integer")
BOOLEAN = CType("boolean")


# ------------------------------------------------------------------- parser --

@dataclass
class LogicDef:
    name: str
    labels: tuple[str, ...]
    params: list[tuple[CType, str]]
    result: CType               # BOOLEAN for a predicate
    body: Optional[E]           # None: declared without a definition (axiomatic/abstract)
    where: str = ""
    axiomatic: str = ""         # the enclosing axiomatic block's name, if any


@dataclass
class Behavior:
    name: str
    assumes: list[E] = field(default_factory=list)
    requires: list[E] = field(default_factory=list)
    ensures: list[E] = field(default_factory=list)
    assigns: list[list[E]] = field(default_factory=list)


@dataclass
class Contract:
    requires: list[E] = field(default_factory=list)
    ensures: list[E] = field(default_factory=list)
    assigns: list[list[E]] = field(default_factory=list)
    behaviors: list[Behavior] = field(default_factory=list)
    other: list[tuple[str, object]] = field(default_factory=list)   # (clause keyword, payload)
    where: str = ""


@dataclass
class LoopAnnot:
    invariants: list[E] = field(default_factory=list)
    variant: Optional[E] = None
    assigns: list[list[E]] = field(default_factory=list)
    other: list[str] = field(default_factory=list)


@dataclass
class Func:
    name: str
    ret: CType
    params: list[tuple[CType, str]]
    body: Optional[list]         # statements, None for a prototype
    contract: Optional[Contract]
    where: str = ""
    error: Optional[AcslRefusal] = None    # the body did not parse; refused only if it is lifted


# Statements (tuples keep them light):
#   ("decl", ctype, name, init|None, line) ("expr", E, line) ("if", c, then, else, line)
#   ("while", c, body, LoopAnnot|None, line) ("for", init_stmts, c|None, step E|None, body, LoopAnnot|None, line)
#   ("do", body, c, annot, line) ("return", E|None, line) ("block", stmts) ("break", line) ("continue", line)
#   ("assert", E, line) ("annot", text, line)   -- any other statement-level annotation
#   ("skip",)


class Parser:
    def __init__(self, toks: list[Tok], typedefs: dict[str, CType], macros=None, logic_mode=False):
        self.toks = toks + [Tok("eof", "", toks[-1].file if toks else "", toks[-1].line if toks else 0)]
        self.i = 0
        self.typedefs = typedefs
        self.macros = macros or {}
        self.logic_mode = logic_mode

    # -- token helpers
    def peek(self, k: int = 0) -> Tok:
        return self.toks[min(self.i + k, len(self.toks) - 1)]

    def next(self) -> Tok:
        t = self.toks[self.i]
        self.i = min(self.i + 1, len(self.toks) - 1)
        return t

    def is_(self, text: str, k: int = 0) -> bool:
        t = self.peek(k)
        return t.kind in ("op", "id") and t.text == text

    def accept(self, text: str) -> bool:
        if self.is_(text):
            self.next()
            return True
        return False

    def expect(self, text: str) -> Tok:
        t = self.next()
        if t.text != text or t.kind not in ("op", "id"):
            raise AcslRefusal("source-unparseable", f"expected {text!r}, found {t.text!r}", t.at())
        return t

    def ident(self) -> Tok:
        t = self.next()
        if t.kind != "id":
            raise AcslRefusal("source-unparseable", f"expected a name, found {t.text!r}", t.at())
        return t

    # -- types
    def at_type(self, k: int = 0) -> bool:
        t = self.peek(k)
        if t.kind != "id":
            return False
        return (t.text in ("const", "unsigned", "signed", "int", "short", "long", "char", "void", "struct",
                           "integer", "boolean", "real", "float", "double", "volatile", "static", "inline",
                           "extern")
                or t.text in self.typedefs)

    def ctype(self, stars: bool = True) -> CType:
        const = False
        words: list[str] = []
        named: Optional[CType] = None
        while True:
            t = self.peek()
            if t.kind != "id":
                break
            if t.text in ("const", "volatile", "static", "inline", "extern"):
                const = const or t.text == "const"
                self.next()
            elif t.text in ("unsigned", "signed", "int", "short", "long", "char", "void"):
                words.append(self.next().text)
            elif t.text == "struct":
                self.next()
                named = CType("struct", name=self.ident().text)
            elif t.text in ("integer", "boolean") and not words and named is None:
                self.next()
                named = INTEGER if t.text == "integer" else BOOLEAN
            elif t.text in ("real", "float", "double") and not words and named is None:
                raise AcslRefusal("real", t.text, t.at())
            elif t.text in self.typedefs and not words and named is None:
                self.next()
                named = self.typedefs[t.text]
            else:
                break
        if named is None:
            key = tuple(words)
            if key not in C_TYPES:
                raise AcslRefusal("c-type", " ".join(words) or self.peek().text, self.peek().at())
            kind, signed = C_TYPES[key]
            named = CType("void") if kind == "void" else CType("int", signed, kind, name=" ".join(words))
        ty = named
        while stars and self.accept("*"):
            ty = CType("ptr", elem=ty, const=const)
            const = False
            while self.peek().kind == "id" and self.peek().text in ("const", "volatile"):
                self.next()
        return ty

    # -- expressions (ACSL precedence table, speclang_modern.tex "Operators precedence")
    def expr(self) -> E:
        return self.binding()

    def binding(self) -> E:
        t = self.peek()
        if t.kind == "id" and t.text in ("\\forall", "\\exists"):
            self.next()
            binders = []
            ty = self.ctype(stars=False)
            while True:
                bty = ty
                while self.accept("*"):
                    bty = CType("ptr", elem=bty)
                binders.append((bty, self.ident().text))
                if not self.accept(","):
                    break
                if self.at_type():
                    ty = self.ctype(stars=False)
            self.expect(";")
            body = self.binding()
            return E("quant", (t.text[1:], tuple(binders), body), t.line)
        if t.kind == "id" and t.text == "\\let":
            self.next()
            nm = self.ident().text
            self.expect("=")
            v = self.ternary()
            self.expect(";")
            body = self.binding()
            return E("let", (nm, v, body), t.line)
        return self.ternary()

    def ternary(self) -> E:
        c = self.equiv()
        if self.is_("?"):
            t = self.next()
            a = self.binding()
            self.expect(":")
            b = self.binding()
            return E("ite", (c, a, b), t.line)
        return c

    def _left(self, sub, ops) -> E:
        x = sub()
        while self.peek().kind == "op" and self.peek().text in ops:
            t = self.next()
            y = sub()
            x = E("bin", (t.text, x, y), t.line)
        return x

    def equiv(self) -> E:
        return self._left(self.implies, ("<==>",))

    def implies(self) -> E:
        x = self.lor()
        if self.is_("==>"):
            t = self.next()
            y = self.implies()
            return E("bin", ("==>", x, y), t.line)
        return x

    def lor(self) -> E:
        return self._left(self.lxor, ("||",))

    def lxor(self) -> E:
        return self._left(self.land, ("^^",))

    def land(self) -> E:
        return self._left(self.bequiv, ("&&",))

    def bequiv(self) -> E:
        return self._left(self.bimplies, ("<-->",))

    def bimplies(self) -> E:
        x = self.bor()
        if self.is_("-->"):
            t = self.next()
            return E("bin", ("-->", x, self.bimplies()), t.line)
        return x

    def bor(self) -> E:
        return self._left(self.bxor, ("|",))

    def bxor(self) -> E:
        return self._left(self.band, ("^",))

    def band(self) -> E:
        return self._left(self.rel, ("&",))

    def rel(self) -> E:
        x = self.shift()
        ops, xs = [], [x]
        while self.peek().kind == "op" and self.peek().text in REL_OPS:
            ops.append(self.next().text)
            xs.append(self.shift())
        if not ops:
            return x
        if len(ops) == 1:
            return E("bin", (ops[0], xs[0], xs[1]), x.line)
        if not self.logic_mode:
            raise AcslRefusal("c-relational-chain", " ".join(ops), self.peek().at())
        return E("chain", (tuple(ops), tuple(xs)), x.line)

    def shift(self) -> E:
        return self._left(self.add, ("<<", ">>"))

    def add(self) -> E:
        return self._left(self.mul, ("+", "-"))

    def mul(self) -> E:
        return self._left(self.unary, ("*", "/", "%"))

    def unary(self) -> E:
        t = self.peek()
        if t.kind == "op" and t.text in ("!", "-", "+", "~", "*", "&"):
            self.next()
            return E("un", (t.text, self.unary()), t.line)
        if t.kind == "op" and t.text in ("++", "--"):
            self.next()
            return E("incr", (t.text, self.unary(), True), t.line)
        if t.kind == "op" and t.text == "(" and self.at_type(1):
            self.next()
            ty = self.ctype()
            self.expect(")")
            return E("cast", (ty, self.unary()), t.line)
        if t.kind == "id" and t.text == "sizeof":
            raise AcslRefusal("sizeof", "sizeof", t.at())
        return self.postfix()

    def postfix(self) -> E:
        x = self.primary()
        while True:
            t = self.peek()
            if self.is_("["):
                self.next()
                i = self.expr()
                if self.is_(".."):
                    self.next()
                    hi = self.expr()
                    self.expect("]")
                    x = E("index", (x, E("range", (i, hi), t.line)), t.line)
                    continue
                self.expect("]")
                x = E("index", (x, i), t.line)
            elif self.is_(".") or self.is_("->"):
                self.next()
                x = E("member", (x, self.ident().text, t.text == "->"), t.line)
            elif self.is_("++") or self.is_("--"):
                self.next()
                x = E("incr", (t.text, x, False), t.line)
            else:
                return x

    def args(self) -> tuple:
        self.expect("(")
        out = []
        if not self.is_(")"):
            while True:
                out.append(self.expr())
                if not self.accept(","):
                    break
        self.expect(")")
        return tuple(out)

    def primary(self) -> E:
        t = self.next()
        if t.kind == "str":
            raise AcslRefusal("string-literal", t.text[:20], t.at())
        if t.kind == "num":
            return E("int", (num_value(t.text),), t.line)
        if t.kind == "op" and t.text == "(":
            if self.logic_mode and self.is_(".."):
                raise AcslRefusal("source-unparseable", "(..)", t.at())
            x = self.expr()
            if self.logic_mode and self.is_(".."):
                self.next()
                hi = self.expr()
                self.expect(")")
                return E("range", (x, hi), t.line)
            self.expect(")")
            return x
        if t.kind == "id":
            s = t.text
            if s in ("\\true", "\\false"):
                return E("bool", (s == "\\true",), t.line)
            if s == "\\result":
                return E("result", (), t.line)
            if s in ("\\old",):
                a = self.args()
                return E("old", (a[0],), t.line)
            if s == "\\at":
                self.expect("(")
                x = self.expr()
                self.expect(",")
                lab = self.ident().text
                self.expect(")")
                return E("at", (x, lab), t.line)
            if s in ("\\valid", "\\valid_read"):
                self.expect("(")
                x = self.expr()
                self.expect(")")
                return E("valid", (s[1:], x), t.line)
            if s == "\\separated":
                return E("sep", self.args(), t.line)
            if s == "\\nothing":
                return E("var", (s,), t.line)
            if s.startswith("\\") and s not in LOGIC_BUILTINS:
                raise AcslRefusal("acsl-builtin", s, t.at())
            labels: tuple = ()
            if self.is_("{") and self.logic_mode:
                self.next()
                labs = []
                while not self.is_("}"):
                    labs.append(self.ident().text)
                    self.accept(",")
                self.expect("}")
                labels = tuple(labs)
            if self.is_("("):
                return E("call", (s, labels, self.args()), t.line)
            if labels:
                raise AcslRefusal("logic-label", f"{s}{{{','.join(labels)}}}", t.at())
            if s in ("true", "false") and s not in self.macros:
                return E("bool", (s == "true",), t.line)
            return E("var", (s,), t.line)
        raise AcslRefusal("source-unparseable", f"unexpected {t.text!r}", t.at())

    # -- ACSL clauses
    def skip_names(self) -> None:
        """A clause's names (`requires valid: ...`, ACSL "naming"), dropped."""
        while self.peek().kind == "id" and not self.peek().text.startswith("\\") and self.is_(":", 1):
            self.next()
            self.next()

    def clause_expr(self) -> E:
        self.skip_names()
        x = self.expr()
        self.expect(";")
        return x

    def locations(self) -> list[E]:
        out = []
        while True:
            out.append(self.expr())
            if not self.accept(","):
                break
        self.expect(";")
        return out


def parse_annot_text(tok: Tok, unit_macros: dict, typedefs: dict) -> Parser:
    toks = scan(tok.text, tok.file, tok.line, annot_mode=True)
    pp = Preprocessor([])
    pp.macros = unit_macros
    toks = pp.expand(toks)
    return Parser(toks, typedefs, unit_macros, logic_mode=True)


CONTRACT_WORDS = {"requires", "ensures", "assigns", "behavior", "assumes", "terminates", "exits",
                  "decreases", "complete", "disjoint", "allocates", "frees", "check", "admit"}
GLOBAL_WORDS = {"logic", "predicate", "lemma", "axiomatic", "inductive", "axiom", "type", "ghost", "global",
                "check", "admit"}


def parse_contract(p: Parser, where: str) -> Contract:
    c = Contract(where=where)
    cur: Optional[Behavior] = None
    while p.peek().kind != "eof":
        t = p.next()
        w = t.text
        if w in ("check", "admit"):
            raise AcslRefusal("check-admit-clause", w, t.at())
        if w == "requires":
            (cur.requires if cur else c.requires).append(p.clause_expr())
        elif w == "ensures":
            (cur.ensures if cur else c.ensures).append(p.clause_expr())
        elif w == "assumes":
            if cur is None:
                raise AcslRefusal("source-unparseable", "assumes outside a behavior", t.at())
            cur.assumes.append(p.clause_expr())
        elif w == "assigns":
            (cur.assigns if cur else c.assigns).append(p.locations())
        elif w == "behavior":
            cur = Behavior(p.ident().text)
            p.expect(":")
            c.behaviors.append(cur)
        elif w in ("complete", "disjoint"):
            p.expect("behaviors")
            names = []
            while not p.is_(";"):
                names.append(p.next().text)
            p.expect(";")
            c.other.append((w + " behaviors", names))
        elif w in ("terminates", "exits", "decreases", "allocates", "frees"):
            c.other.append((w, p.clause_expr()))
        else:
            raise AcslRefusal("contract-clause", w, t.at())
    return c


def parse_loop_annot(p: Parser, la: LoopAnnot) -> None:
    while p.peek().kind != "eof":
        t = p.next()
        if t.text == "loop":
            w = p.next().text
            if w == "invariant":
                la.invariants.append(p.clause_expr())
            elif w == "variant":
                x = p.expr()
                if p.accept("for"):
                    raise AcslRefusal("loop-variant-relation", "variant for a relation", t.at())
                p.expect(";")
                la.variant = x
            elif w == "assigns":
                la.assigns.append(p.locations())
            else:
                raise AcslRefusal("loop-annotation", f"loop {w}", t.at())
        elif t.text == "for":
            raise AcslRefusal("loop-behavior", "for <behavior>: loop annotation", t.at())
        else:
            raise AcslRefusal("loop-annotation", t.text, t.at())


def parse_logic_globals(p: Parser, out: dict, axiomatic: str = "") -> None:
    """`logic`/`predicate` definitions into out[(name, arity)]; lemmas and axioms
    skipped (they are hints: WP uses them, t's kernels prove what they need
    themselves)."""
    while p.peek().kind != "eof":
        t = p.peek()
        w = t.text
        if w == "}" and axiomatic:
            return
        if w in ("lemma", "axiom"):
            p.next()
            depth = 0
            while not (p.is_(";") and depth == 0):
                if p.peek().kind == "eof":
                    raise AcslRefusal("source-unparseable", "unterminated lemma", t.at())
                if p.is_("(") or p.is_("{"):
                    depth += 1
                if p.is_(")") or p.is_("}"):
                    depth -= 1
                p.next()
            p.next()
        elif w == "axiomatic":
            p.next()
            name = p.ident().text
            p.expect("{")
            parse_logic_globals(p, out, name)
            p.expect("}")
        elif w in ("logic", "predicate"):
            p.next()
            res = BOOLEAN if w == "predicate" else p.ctype()
            name = p.ident().text
            labels: tuple = ()
            if p.accept("{"):
                labs = []
                while not p.is_("}"):
                    labs.append(p.ident().text)
                    p.accept(",")
                p.expect("}")
                labels = tuple(labs)
            params: list = []
            if p.accept("("):
                while not p.is_(")"):
                    ty = p.ctype()
                    params.append((ty, p.ident().text))
                    if not p.accept(","):
                        break
                p.expect(")")
            body = None
            if p.accept("="):
                body = p.expr()
            elif p.is_("reads"):
                while not p.is_(";"):
                    p.next()
            elif p.is_("{"):
                raise AcslRefusal("inductive", name, t.at())
            p.expect(";")
            out[(name, param_sig(params))] = LogicDef(name, labels, params, res, body, t.at(), axiomatic)
        elif w == "inductive":
            p.next()
            name = p.ident().text
            depth = 0
            while True:
                if p.is_("{"):
                    depth += 1
                if p.is_("}"):
                    depth -= 1
                    if depth == 0:
                        p.next()
                        break
                p.next()
            out[(name, "inductive")] = LogicDef(name, (), [], BOOLEAN, None, t.at(), "inductive")
        elif w == "type":
            p.next()
            while not p.is_(";"):
                p.next()
            p.next()
        else:
            raise AcslRefusal("logic-global", w, t.at())


def param_sig(params) -> str:
    """An overload's key: one letter per parameter, `p` pointer, `v` value (ACSL
    overloads Equal(a, m, n, b) against Equal(a, m, n, p) by parameter type)."""
    return "".join("p" if ty.kind == "ptr" else "v" for ty, _ in params)


class Program:
    """Every function, prototype contract and logic definition of one unit."""

    def __init__(self, unit: Unit):
        self.unit = unit
        self.typedefs: dict[str, CType] = {}
        self.funcs: dict[str, Func] = {}
        self.contracts: dict[str, Contract] = {}
        self.logic: dict[tuple[str, int], LogicDef] = {}
        self.structs: set[str] = set()
        self.global_errors: list[AcslRefusal] = []
        self.decl_errors: list[AcslRefusal] = []
        self._parse()

    def _annot_parser(self, tok: Tok) -> Parser:
        return parse_annot_text(tok, self.unit.macros, self.typedefs)

    def _parse(self) -> None:
        p = Parser(self.unit.toks, self.typedefs)
        pending: Optional[Contract] = None
        while p.peek().kind != "eof":
            t = p.peek()
            if t.kind == "annot":
                p.next()
                ap = self._annot_parser(t)
                first = ap.peek().text
                if first in GLOBAL_WORDS and first not in CONTRACT_WORDS:
                    try:
                        parse_logic_globals(ap, self.logic)
                    except AcslRefusal as r:
                        # a global this function may never use: refused only if it is used
                        # (an unknown logic name is then its own refusal)
                        self.global_errors.append(r)
                elif first in CONTRACT_WORDS:
                    pending = parse_contract(ap, t.at())
                elif ap.peek().kind == "eof":
                    continue
                else:
                    raise AcslRefusal("global-annotation", first, t.at())
                continue
            if t.text == "typedef":
                p.next()
                if p.is_("struct"):
                    p.next()
                    sname = p.ident().text if p.peek().kind == "id" else ""
                    if p.is_("{"):
                        depth = 0
                        while True:
                            if p.is_("{"):
                                depth += 1
                            if p.is_("}"):
                                depth -= 1
                                if depth == 0:
                                    p.next()
                                    break
                            p.next()
                    alias = p.ident().text
                    p.expect(";")
                    self.typedefs[alias] = CType("struct", name=alias or sname)
                    self.structs.add(alias)
                    continue
                ty = p.ctype()
                alias = p.ident().text
                p.expect(";")
                if alias == "bool" and ty.kind == "int":
                    ty = CType("bool", name="bool")
                self.typedefs[alias] = CType(ty.kind, ty.signed, ty.width, ty.elem, ty.const, alias) \
                    if ty.kind != "bool" else ty
                continue
            if t.text == "struct":
                p.next()
                name = p.ident().text
                if p.is_("{"):
                    depth = 0
                    while True:
                        if p.is_("{"):
                            depth += 1
                        if p.is_("}"):
                            depth -= 1
                            if depth == 0:
                                p.next()
                                break
                        p.next()
                p.expect(";")
                self.structs.add(name)
                continue
            if p.at_type() or t.text == "_Bool":
                start = p.i
                try:
                    pending = self._function(p, pending)
                except AcslRefusal as r:
                    self._skip_decl(p, start)
                    self.decl_errors.append(r)
                    pending = None
                continue
            if t.text == ";":
                p.next()
                continue
            start = p.i
            self._skip_decl(p, start)
            self.decl_errors.append(AcslRefusal("source-unparseable", f"top level {t.text!r}", t.at()))

    def _skip_decl(self, p: Parser, start: int) -> None:
        """Past one top-level declaration: to its `;`, or past its balanced `{...}`."""
        p.i = start
        depth = 0
        while p.peek().kind != "eof":
            t = p.next()
            if t.text == "{" and t.kind == "op":
                depth += 1
            elif t.text == "}" and t.kind == "op":
                depth -= 1
                if depth == 0:
                    if p.is_(";"):
                        p.next()
                    return
            elif t.text == ";" and t.kind == "op" and depth == 0:
                return

    def _function(self, p: Parser, pending):
        """One function declaration or definition; returns the contract still pending."""
        if p.accept("_Bool"):
            ret = CType("bool", name="_Bool")
        else:
            ret = p.ctype()
        name_tok = p.ident()
        if not p.is_("("):
            # a global variable
            while not p.is_(";"):
                p.next()
            p.next()
            self.funcs.setdefault("<globals>", Func("<globals>", ret, [], None, None, name_tok.at()))
            return None
        p.expect("(")
        params = []
        if p.is_("void") and p.is_(")", 1):
            p.next()
        while not p.is_(")"):
            ty = p.ctype()
            pname = p.ident().text if p.peek().kind == "id" else f"_{len(params)}"
            if p.is_("["):
                raise AcslRefusal("array-parameter", pname, p.peek().at())
            params.append((ty, pname))
            if not p.accept(","):
                break
        p.expect(")")
        if pending is not None:
            self.contracts[name_tok.text] = pending
            pending = None
        while p.peek().kind == "id" and p.peek().text == "__attribute__":
            p.next()
            depth = 0
            while True:
                tk = p.next()
                if tk.text == "(":
                    depth += 1
                elif tk.text == ")":
                    depth -= 1
                    if depth == 0:
                        break
        if p.accept(";"):
            self.funcs.setdefault(name_tok.text, Func(name_tok.text, ret, params, None, None, name_tok.at()))
            return None
        start = p.i
        try:
            body = self._block(p)
            err = None
        except AcslRefusal as r:
            self._skip_decl(p, start)
            body, err = [], r
        self.funcs[name_tok.text] = Func(name_tok.text, ret, params, body,
                                         self.contracts.get(name_tok.text), name_tok.at(), err)
        return None

    # -- statements
    def _block(self, p: Parser) -> list:
        p.expect("{")
        out = []
        while not p.is_("}"):
            if p.peek().kind == "eof":
                raise AcslRefusal("source-unparseable", "unterminated block", p.peek().at())
            out.extend(self._stmt(p))
        p.expect("}")
        return out

    def _stmt(self, p: Parser, annot: Optional[LoopAnnot] = None) -> list:
        t = p.peek()
        if t.kind == "annot":
            p.next()
            ap = self._annot_parser(t)
            first = ap.peek().text
            if first in ("loop", "for"):
                la = annot or LoopAnnot()
                parse_loop_annot(ap, la)
                nxt = p.peek()
                if nxt.kind == "annot":
                    return self._stmt(p, la)
                if nxt.text not in ("for", "while", "do"):
                    raise AcslRefusal("loop-annotation", "loop annotation not before a loop", t.at())
                return self._stmt(p, la)
            if first in ("assert", "check", "admit"):
                ap.next()
                ap.skip_names()
                x = ap.expr()
                ap.expect(";")
                return [("assert", x, t.line, first)]
            if first == "ghost":
                raise AcslRefusal("ghost-code", "ghost", t.at())
            if first in CONTRACT_WORDS:
                raise AcslRefusal("statement-contract", first, t.at())
            if first == "invariant":
                raise AcslRefusal("general-invariant", first, t.at())
            raise AcslRefusal("statement-annotation", first, t.at())
        if annot is not None and t.text not in ("for", "while", "do"):
            raise AcslRefusal("loop-annotation", "loop annotation not before a loop", t.at())
        if p.is_("{"):
            return [("block", self._block(p))]
        if p.is_(";"):
            p.next()
            return [("skip",)]
        w = t.text
        if w == "if":
            p.next()
            p.expect("(")
            c = p.expr()
            p.expect(")")
            th = self._stmt(p)
            el: list = []
            if p.accept("else"):
                el = self._stmt(p)
            return [("if", c, th, el, t.line)]
        if w == "while":
            p.next()
            p.expect("(")
            c = p.expr()
            p.expect(")")
            return [("while", c, self._stmt(p), annot, t.line)]
        if w == "do":
            p.next()
            body = self._stmt(p)
            p.expect("while")
            p.expect("(")
            c = p.expr()
            p.expect(")")
            p.expect(";")
            return [("do", body, c, annot, t.line)]
        if w == "for":
            p.next()
            p.expect("(")
            init: list = []
            if p.at_type():
                init = self._decl(p)
            elif not p.accept(";"):
                init = [("expr", p.expr(), t.line)]
                p.expect(";")
            c = None if p.is_(";") else p.expr()
            p.expect(";")
            step = None if p.is_(")") else p.expr()
            p.expect(")")
            return [("for", init, c, step, self._stmt(p), annot, t.line)]
        if w == "return":
            p.next()
            x = None if p.is_(";") else p.expr()
            p.expect(";")
            return [("return", x, t.line)]
        if w in ("break", "continue"):
            p.next()
            p.expect(";")
            return [(w, t.line)]
        if w in ("goto", "switch", "case", "default"):
            raise AcslRefusal(w, w, t.at())
        if p.at_type():
            return self._decl(p)
        x = p.expr()
        if p.is_(","):
            raise AcslRefusal("comma-expression", ",", t.at())
        p.expect(";")
        return [("expr", x, t.line)]

    def _decl(self, p: Parser) -> list:
        line = p.peek().line
        ty = p.ctype()
        out = []
        while True:
            stars = 0
            while p.accept("*"):
                stars += 1
            name = p.ident().text
            dty = ty
            for _ in range(stars):
                dty = CType("ptr", elem=dty)
            if p.is_("["):
                raise AcslRefusal("local-array", name, p.peek().at())
            init = None
            if p.accept("="):
                init = p.expr()
            out.append(("decl", dty, name, init, line))
            if not p.accept(","):
                break
        p.expect(";")
        return out


def load(path: Path, root: Path) -> Program:
    """Preprocess and parse one .c file of the corpus (headers searched in its
    own directory, the root, and the root's Logic/)."""
    search = [root, root / "Logic"] + [d for d in sorted(root.iterdir()) if d.is_dir()]
    return Program(Preprocessor(search).run(Path(path)))


# ------------------------------------------------------------- translation --

DAFNY_KEYWORDS = {
    "abstract", "array", "as", "assert", "assume", "bool", "break", "by", "calc", "case", "char", "class",
    "codatatype", "const", "constructor", "continue", "datatype", "decreases", "else", "ensures", "exists",
    "expect", "export", "extends", "false", "forall", "fresh", "function", "ghost", "if", "imap", "import",
    "in", "include", "int", "invariant", "is", "iset", "iterator", "label", "lemma", "map", "match", "method",
    "modifies", "modify", "module", "multiset", "nat", "new", "newtype", "null", "object", "old", "opened",
    "predicate", "print", "provides", "reads", "real", "refines", "requires", "return", "returns", "reveal",
    "reveals", "seq", "set", "static", "string", "then", "this", "trait", "true", "twostate", "type",
    "unchanged", "var", "while", "witness", "yield", "yields", "result", "len", "at", "fill", "update",
}


@dataclass
class RecFun:
    """A recursive logic function lifted as a guarded spec_fun, with what the
    check needs to prove the guard changes nothing where it matters."""
    acsl_name: str
    arity: int
    dafny_name: str
    params: list[tuple[str, str]]          # (name, "seq"|"int"|"bool")
    rec_param: str
    measure: E
    base: E
    domain: list[str]                      # conjuncts over params, in ACSL (len(x) written x_n)
    guarded_reads: int
    result: str                            # "int" | "bool"
    acsl_params: list = field(default_factory=list)   # (name, ACSL type as declared)


@dataclass
class Lifted:
    """The Dafny text plus everything the check needs to name the source again."""
    function: str
    dafny: str
    method: str
    params: list[dict]                     # {c_name, c_type, role: seq|len|scalar, dafny_name, of}
    ret: dict                              # {c_type, dafny_type}
    locals: list[dict]                     # {c_name, c_type, dafny_name} in declaration order
    mutated: dict[str, str]                # param -> its pre-state name
    rec_funs: list[RecFun]
    clauses_added: list[tuple[str, str]]
    clauses_dropped: list[tuple[str, int]]
    rewrites: list[str]
    src_pre: list[str]                     # ACSL, source names, \valid_read removed
    src_post: list[str]                    # ACSL, \result written `result`
    src_loops: list[dict]                  # {"inv": [ACSL], "variant": ACSL|None} in program order
    headers: list[str]                     # the source files the unit read
    spec_division: bool = False            # a `/` or `%` whose operands are not unsigned by type

    def sidecar(self) -> dict:
        d = {k: v for k, v in self.__dict__.items() if k not in ("rec_funs", "locals")}
        d["locals"] = [{k: v for k, v in x.items() if k != "_ty"} for x in self.locals]
        d["rec_funs"] = [{**r.__dict__, "measure": acsl(r.measure, {}), "base": acsl(r.base, {})}
                         for r in self.rec_funs]
        return d


def fresh(base: str, used: set) -> str:
    n = base
    k = 1
    while n in used:
        k += 1
        n = f"{base}{k}"
    used.add(n)
    return n


def subst(e: E, m: dict) -> E:
    """Capture-avoiding substitution of variables by expressions (bound names
    are renamed apart from every free variable of the substituted terms)."""
    if not isinstance(e, E):
        return e
    if e.k == "var":
        return m.get(e.a[0], e)
    if e.k == "quant":
        kind, binders, body = e.a
        free = set()
        for v in m.values():
            free |= free_vars(v)
        new_binders = []
        mm = {k: v for k, v in m.items() if k not in {b[1] for b in binders}}
        for ty, nm in binders:
            if nm in free:
                nn = fresh(nm, free | set(m) | {b[1] for b in binders} | free_vars(body))
                mm[nm] = E("var", (nn,), e.line)
                new_binders.append((ty, nn))
            else:
                new_binders.append((ty, nm))
        return E("quant", (kind, tuple(new_binders), subst(body, mm)), e.line)
    if e.k == "let":
        nm, v, body = e.a
        return subst(subst(body, {nm: v}), m)
    return E(e.k, tuple(subst(x, m) if isinstance(x, E) else
                        (tuple(subst(y, m) for y in x) if isinstance(x, tuple) and x and isinstance(x[0], E)
                         else x) for x in e.a), e.line)


def strip_at(e, labels: tuple):
    """\\at(x, L) -> x for L among a definition's own state labels (read-only arrays: one state)."""
    if not isinstance(e, E):
        return e
    if e.k == "at" and e.a[1] in labels:
        return strip_at(e.a[0], labels)
    return E(e.k, tuple(strip_at(x, labels) if isinstance(x, E) else
                        (tuple(strip_at(y, labels) for y in x) if isinstance(x, tuple) and x and isinstance(x[0], E)
                         else x) for x in e.a), e.line)


def free_vars(e) -> set:
    out: set = set()

    def go(x, bound):
        if isinstance(x, E):
            if x.k == "var" and x.a[0] not in bound:
                out.add(x.a[0])
            elif x.k == "quant":
                go(x.a[2], bound | {b[1] for b in x.a[1]})
                return
            elif x.k == "let":
                go(x.a[1], bound)
                go(x.a[2], bound | {x.a[0]})
                return
            for y in x.a:
                go(y, bound)
        elif isinstance(x, (tuple, list)):
            for y in x:
                go(y, bound)
    go(e, frozenset())
    return out


# -- ACSL printer (the check file quotes source clauses through this, so what
#    the check proves is about the tree this front end read, not raw text)

PREC = {"<==>": 1, "==>": 2, "||": 3, "^^": 4, "&&": 5, "==": 7, "!=": 7, "<": 8, "<=": 8, ">": 8, ">=": 8,
        "+": 10, "-": 10, "*": 11, "/": 11, "%": 11}


def acsl(e: E, ren: dict) -> str:
    """ACSL text of a clause, variables renamed by `ren` (fully parenthesized)."""
    k = e.k
    if k == "int":
        return str(e.a[0]) if e.a[0] >= 0 else f"({e.a[0]})"
    if k == "bool":
        return "\\true" if e.a[0] else "\\false"
    if k == "var":
        return ren.get(e.a[0], e.a[0])
    if k == "result":
        return ren.get("\\result", "\\result")
    if k == "un":
        return f"({e.a[0]}{acsl(e.a[1], ren)})"
    if k == "bin":
        return f"({acsl(e.a[1], ren)} {e.a[0]} {acsl(e.a[2], ren)})"
    if k == "chain":
        ops, xs = e.a
        s = acsl(xs[0], ren)
        for op, x in zip(ops, xs[1:]):
            s += f" {op} {acsl(x, ren)}"
        return f"({s})"
    if k == "ite":
        return f"({acsl(e.a[0], ren)} ? {acsl(e.a[1], ren)} : {acsl(e.a[2], ren)})"
    if k == "index":
        return f"{acsl(e.a[0], ren)}[{acsl(e.a[1], ren)}]"
    if k == "call":
        name, labels, args = e.a
        lab = "{" + ",".join(labels) + "}" if labels else ""
        return f"{name}{lab}(" + ", ".join(acsl(x, ren) for x in args) + ")"
    if k == "quant":
        kind, binders, body = e.a
        inner = {kk: v for kk, v in ren.items() if kk not in {b[1] for b in binders}}
        bs = ", ".join(f"{acsl_type(ty)} {nm}" for ty, nm in binders)
        return f"(\\{kind} {bs}; {acsl(body, inner)})"
    if k == "at":
        return f"\\at({acsl(e.a[0], ren)}, {e.a[1]})"
    if k == "old":
        return f"\\old({acsl(e.a[0], ren)})"
    if k == "cast":
        return f"(({acsl_type(e.a[0])}){acsl(e.a[1], ren)})"
    if k == "let":
        return f"(\\let {e.a[0]} = {acsl(e.a[1], ren)}; {acsl(e.a[2], ren)})"
    raise AcslRefusal("acsl-print", k)


STATE_LABELS = ("Here", "Pre", "Old", "Post")


def single_state(e, pre: dict):
    """A clause of a function that assigns \\nothing, over one memory state: \\old(x) and
    \\at(x, Pre|Old|Here|Post) become x (a parameter read at Pre becomes its pre-state
    name from `pre`), and every state label of a logic call becomes `L`, the one label
    of the check's lemmas. Sound because nothing is written: every state has the same
    arrays (ACSL manual, "Built-in construct \\at")."""
    if not isinstance(e, E):
        return e
    if e.k == "old" or (e.k == "at" and e.a[1] in ("Pre", "Old")):
        return single_state(subst(e.a[0], {p: E("var", (q,)) for p, q in pre.items() if p != q}), pre)
    if e.k == "at" and e.a[1] in ("Here", "Post"):
        return single_state(e.a[0], pre)
    if e.k == "call" and e.a[1]:
        if any(lb not in STATE_LABELS for lb in e.a[1]):
            raise AcslRefusal("logic-label", e.a[0])
        return E("call", (e.a[0], tuple("L" for _ in e.a[1]), tuple(single_state(x, pre) for x in e.a[2])),
                 e.line)
    return E(e.k, tuple(single_state(x, pre) if isinstance(x, E) else
                        (tuple(single_state(y, pre) for y in x) if isinstance(x, tuple) and x
                         and isinstance(x[0], E) else x) for x in e.a), e.line)


def acsl_type(t: CType) -> str:
    if t.kind == "ptr":
        return acsl_type(t.elem) + "*"
    if t.kind in ("integer", "boolean"):
        return t.kind
    if t.kind == "bool":
        return "int"
    if t.kind == "int":
        return ("" if t.signed else "unsigned ") + (t.width or "int")
    return t.name or t.kind


class Translator:
    """One C function of a Program to one Dafny method (plus spec functions)."""

    def __init__(self, prog: Program, fname: str):
        self.prog = prog
        self.fname = fname
        self.rewrites: list[str] = []
        self.added: list[tuple[str, str]] = []
        self.dropped: dict[str, int] = {}
        self.rec: dict[tuple[str, int], RecFun] = {}
        self.rec_order: list[tuple[str, int]] = []
        self.rec_dafny: list[str] = []
        self.spec_division = False
        self._ptrs: set = set()

    def drop(self, rule: str) -> None:
        self.dropped[rule] = self.dropped.get(rule, 0) + 1

    # ---------------------------------------------------------- the function
    def run(self) -> Lifted:
        f = self.prog.funcs.get(self.fname)
        if f is None or f.body is None:
            raise AcslRefusal("no-function", f"no definition of {self.fname}")
        if f.error is not None:
            raise f.error
        c = self.prog.contracts.get(self.fname) or f.contract
        if c is None:
            raise AcslRefusal("no-contract", self.fname, f.where)
        if not c.ensures and not any(b.ensures for b in c.behaviors):
            raise AcslRefusal("no-ensures", self.fname, f.where)
        self.f = f
        self.c = c
        self.where = f.where
        # -- parameters
        valid = self._valid_ranges(c)
        self.env: dict[str, CType] = {}
        self.seq_len: dict[str, str] = {}        # array param -> its length param
        self.len_of: dict[str, str] = {}         # length param -> the first array it measures
        params = []
        for ty, nm in f.params:
            self.env[nm] = ty
            if ty.kind == "ptr":
                if ty.elem.kind == "ptr":
                    raise AcslRefusal("pointer-to-pointer", nm, f.where)
                if ty.elem.kind == "struct":
                    raise AcslRefusal("struct", f"{nm}: {ty.show()}", f.where)
                if ty.elem.kind != "int" or not ty.elem.signed or ty.elem.width not in ("int",):
                    raise AcslRefusal("array-element-type", f"{nm}: {ty.show()}", f.where)
                if nm not in valid:
                    raise AcslRefusal("pointer-without-range", nm, f.where)
                kind, ln = valid[nm]
                if kind == "valid" or not ty.const:
                    raise AcslRefusal("array-write", f"{nm} is {'writable' if kind == 'valid' else 'not const'}",
                                      f.where)
                self.seq_len[nm] = ln
                self._ptrs.add(nm)
                self.len_of.setdefault(ln, nm)
            elif ty.kind == "struct":
                raise AcslRefusal("struct", f"{nm}: {ty.show()}", f.where)
            elif ty.kind not in ("int", "bool"):
                raise AcslRefusal("c-type", f"{nm}: {ty.show()}", f.where)
        for ln in self.len_of:
            if ln not in dict((nm, 1) for _, nm in f.params) or not self.env[ln].is_int():
                raise AcslRefusal("valid-range-shape", f"length {ln} is not an integer parameter", f.where)
        if f.ret.kind == "void":
            raise AcslRefusal("void-result", self.fname, f.where)
        if f.ret.kind == "struct":
            raise AcslRefusal("struct", f"returns {f.ret.show()}", f.where)
        if f.ret.kind not in ("int", "bool"):
            raise AcslRefusal("c-type", f"returns {f.ret.show()}", f.where)
        calls = []
        walk_stmts(code_only(f.body), lambda e: calls.append(e.a[0]) if e.k == "call" else None)
        if calls:
            raise AcslRefusal("calls-self" if self.fname in calls else "calls-other-method", calls[0], f.where)
        self._check_assigns(c)
        # -- which parameters does the body assign? (C passes by value)
        assigned = set()
        self._assigned(f.body, assigned)
        for ln in self.len_of:
            if ln in assigned:
                raise AcslRefusal("length-assigned", ln, f.where)
        self.mutated = {nm: fresh(nm + "0", {p for _, p in f.params} | self._all_names(f.body))
                        for _, nm in f.params if nm in assigned}
        if self.mutated:
            self.rewrites.append("mutated-param-copied")
        for nm in self.mutated:
            if self.env[nm].kind == "ptr":
                raise AcslRefusal("pointer-arith", f"{nm} reassigned", f.where)
        # -- names
        self.used = {nm for _, nm in f.params} | set(self.mutated.values())
        for _, nm in f.params:
            if nm in DAFNY_KEYWORDS:
                raise AcslRefusal("reserved-name", nm, f.where)
        self.ret_name = "result"
        self.used.add("result")
        # -- contract
        pre_ren = {p: self.mutated.get(p, p) for _, p in f.params}
        req, ens, src_pre, src_post = [], [], [], []
        for r in c.requires:
            kept = self._strip_valid(r)
            for x in kept:
                req.append(self.spec(x, pre_ren, "pre"))
                src_pre.append(acsl(single_state(x, pre_ren), pre_ren))
        for b in c.behaviors:
            if b.requires:
                raise AcslRefusal("behavior-requires", b.name, c.where)
            if b.assigns and not all(self._nothing(a) for a in b.assigns):
                raise AcslRefusal("array-write", f"behavior {b.name} assigns memory", c.where)
            if not b.assumes:
                raise AcslRefusal("behavior-without-assumes", b.name, c.where)
        for x in c.ensures:
            ens.append(self.spec(x, pre_ren, "post"))
            src_post.append(acsl(single_state(x, pre_ren), {**pre_ren, "\\result": "result"}))
        for b in c.behaviors:
            a = b.assumes[0]
            for more in b.assumes[1:]:
                a = E("bin", ("&&", a, more), more.line)
            for x in b.ensures:
                imp = E("bin", ("==>", a, x), x.line)
                ens.append(self.spec(imp, pre_ren, "post"))
                src_post.append(acsl(single_state(imp, pre_ren), {**pre_ren, "\\result": "result"}))
                self.rewrites.append("behavior-to-implication")
        for kw, payload in c.other:
            if kw in ("complete behaviors", "disjoint behaviors"):
                self.drop(kw.replace(" ", "-"))
            elif kw == "terminates":
                if not (isinstance(payload, E) and payload.k == "bool" and payload.a[0]):
                    raise AcslRefusal("terminates-condition", "terminates", c.where)
            elif kw == "exits":
                if not (isinstance(payload, E) and payload.k == "bool" and not payload.a[0]):
                    raise AcslRefusal("exits-clause", "exits", c.where)
            elif kw == "decreases":
                raise AcslRefusal("recursive-c-function", "decreases", c.where)
            else:
                raise AcslRefusal(kw + "-clause", kw, c.where)
        # -- body
        self.locals: list[dict] = []
        self.scope: set[str] = set(self.used)
        self.loops: list[dict] = []
        lines = []
        for p, p0 in self.mutated.items():
            lines.append(f"  var {p}: {self.dty(self.env[p])} := {p0};")
            self.locals.append({"c_name": p, "c_type": self.env[p].show(), "dafny_name": p, "copy_of": p0,
                                "_ty": self.env[p]})
            self.scope.add(p)
        lines += self.block(f.body, 1)
        # -- assemble
        dparams = []
        plist = []
        for ty, nm in f.params:
            role = "seq" if nm in self.seq_len else ("len" if nm in self.len_of else "scalar")
            dn = self.mutated.get(nm, nm)
            plist.append({"c_name": nm, "c_type": ty.show(), "role": role, "dafny_name": dn,
                          "of": self.seq_len.get(nm) or self.len_of.get(nm)})
            if role == "len":
                continue
            dparams.append(f"{dn}: {'seq<int>' if role == 'seq' else self.dty(ty)}")
        first_of_len: dict[str, str] = {}
        for ty, nm in f.params:
            if nm in self.seq_len:
                ln = self.seq_len[nm]
                if ln in first_of_len:
                    req.insert(0, f"|{nm}| == |{first_of_len[ln]}|")
                    self.added.append(("same-length-arrays", f"len({nm}) == len({first_of_len[ln]})"))
                else:
                    first_of_len[ln] = nm
        if any(self._unsigned(ty) for ty, _ in f.params) or self._unsigned(f.ret):
            self.added.append(("unsigned-as-nat", "unsigned parameters and result are nat"))
        self.added.append(("machine-int-generalized",
                           "C integer upper bounds (INT_MAX, UINT_MAX) are not carried; see lift_acsl.py"))
        rtype = self.dty(f.ret)
        out = []
        out += self.rec_dafny
        out.append(f"method {self.fname}({', '.join(dparams)}) returns ({self.ret_name}: {rtype})")
        for r in req:
            out.append(f"  requires {r}")
        for e_ in ens:
            out.append(f"  ensures {e_}")
        out.append("{")
        out += lines
        out.append("}")
        return Lifted(
            function=self.fname, dafny="\n".join(out) + "\n", method=self.fname, params=plist,
            ret={"c_type": f.ret.show(), "dafny_type": rtype}, locals=self.locals, mutated=dict(self.mutated),
            rec_funs=[self.rec[k] for k in self.rec_order], clauses_added=self.added,
            clauses_dropped=sorted(self.dropped.items()), rewrites=sorted(set(self.rewrites)),
            src_pre=src_pre, src_post=src_post, src_loops=self.loops, headers=list(self.prog.unit.files),
            spec_division=self.spec_division)

    # ------------------------------------------------------------- helpers
    def _unsigned(self, ty: CType) -> bool:
        return ty.kind == "int" and ty.signed is False

    def dty(self, ty: CType) -> str:
        if ty.kind == "bool" or ty.kind == "boolean":
            return "bool"
        if ty.kind == "integer":
            return "int"
        if ty.kind == "int":
            if ty.width in ("char", "short", "long") and ty.signed:
                return "int"
            return "int" if ty.signed else "nat"
        raise AcslRefusal("c-type", ty.show(), self.where)

    def _all_names(self, body) -> set:
        out = set()

        def go(s):
            if isinstance(s, tuple):
                if s and s[0] == "decl":
                    out.add(s[2])
                for x in s:
                    go(x)
            elif isinstance(s, list):
                for x in s:
                    go(x)
        go(body)
        return out

    def _assigned(self, body, out: set) -> None:
        def fn(e):
            if e.k in ("assign", "incr"):
                tgt = e.a[1]
                if tgt.k == "var":
                    out.add(tgt.a[0])
                elif tgt.k == "index":
                    base = tgt.a[0]
                    raise AcslRefusal("array-write", acsl_or(base), self.where)
                else:
                    raise AcslRefusal("pointer-write", tgt.k, self.where)
        walk_stmts(body, fn)

    def _nothing(self, locs: list[E]) -> bool:
        return len(locs) == 1 and locs[0].k == "var" and locs[0].a[0] == "\\nothing"

    def _check_assigns(self, c: Contract) -> None:
        if not c.assigns:
            raise AcslRefusal("assigns-missing", self.fname, c.where)
        for locs in c.assigns:
            if not self._nothing(locs):
                raise AcslRefusal("array-write", "assigns " + ", ".join(acsl_or(x) for x in locs), c.where)

    def _valid_ranges(self, c: Contract) -> dict:
        """pointer -> ("valid"|"valid_read", length param) from `\\valid[_read](a + (0..n-1))`."""
        out: dict = {}

        def conj(x):
            if x.k == "bin" and x.a[0] == "&&":
                return conj(x.a[1]) + conj(x.a[2])
            return [x]
        for r in c.requires + [q for b in c.behaviors for q in b.requires]:
            for x in conj(r):
                if x.k != "valid":
                    continue
                kind, arg = x.a
                shape = self._range_shape(arg)
                if shape is None:
                    raise AcslRefusal("valid-range-shape", acsl_or(arg), c.where)
                base, ln = shape
                prev = out.get(base)
                if prev and prev[1] != ln:
                    raise AcslRefusal("valid-range-shape", f"{base} has two ranges", c.where)
                if prev is None or kind == "valid":
                    out[base] = (kind, ln)
        return out

    def _range_shape(self, arg: E):
        # a + (0..n-1)
        if arg.k == "bin" and arg.a[0] == "+" and arg.a[1].k == "var" and arg.a[2].k == "range":
            lo, hi = arg.a[2].a
            if lo.k == "int" and lo.a[0] == 0 and hi.k == "bin" and hi.a[0] == "-" \
                    and hi.a[1].k == "var" and hi.a[2].k == "int" and hi.a[2].a[0] == 1:
                return arg.a[1].a[0], hi.a[1].a[0]
        return None

    def _strip_valid(self, r: E) -> list[E]:
        """A requires without its \\valid_read/\\separated conjuncts (the seq
        representation carries them); refuses one nested anywhere else."""
        def conj(x):
            if x.k == "bin" and x.a[0] == "&&":
                return conj(x.a[1]) + conj(x.a[2])
            return [x]
        kept = []
        for x in conj(r):
            if x.k == "valid":
                self.drop("valid-read-as-seq")
                continue
            if x.k == "sep":
                self.drop("separated-read-only")
                continue
            kept.append(x)
        return kept

    # ------------------------------------------------------ spec expressions
    def spec(self, e: E, ren: dict, pos: str) -> str:
        """Dafny text of an ACSL clause. `ren` maps C names to the names this
        position means (pre-state names for the contract)."""
        e = self.expand(e)
        return self.dx(e, ren, pos, set())

    def expand(self, e: E, depth: int = 0, labels_ok: tuple = ()) -> E:
        """Inline every non-recursive logic definition (capture-avoiding), and
        register every recursive one as a guarded spec function."""
        if depth > 40:
            raise AcslRefusal("logic-expansion-depth", "deep or mutual definitions", self.where)

        def go(x):
            if not isinstance(x, E):
                return x
            if x.k == "call" and x.a[0] not in LOGIC_BUILTINS:
                name, labels, args = x.a
                args = tuple(go(a) for a in args)
                sig = "".join("p" if (a.k == "var" and a.a[0] in self._ptrs) else "v" for a in args)
                d = self._logic(name, sig, x)
                # a read-only array has one state, so any single label naming the
                # current, pre or enclosing definition's state reads the same values
                if any(lb not in ("Here", "Pre", "Old", "Post") + labels_ok for lb in labels):
                    raise AcslRefusal("logic-label", f"{name}{{{','.join(labels)}}}", self.where)
                if len(d.labels) > 1:
                    # a function that assigns \nothing leaves every array as it was, so
                    # a two-state definition reads one state (ACSL manual, "Built-in
                    # construct \at": \at(e, L) is e evaluated in state L)
                    self.rewrites.append("single-state-labels-merged")
                if self._recursive(d):
                    self._register_rec(d)
                    return E("rcall", (name, sig, args), x.line)
                m = {}
                for (ty, pn), a in zip(d.params, args):
                    m[pn] = a
                return self.expand(strip_at(subst(d.body, m), d.labels), depth + 1, d.labels)
            return E(x.k, tuple(go(y) if isinstance(y, E) else
                                (tuple(go(z) for z in y) if isinstance(y, tuple) and y and isinstance(y[0], E)
                                 else y) for y in x.a), x.line)
        return go(e)

    def _logic(self, name: str, sig: str, at: E) -> LogicDef:
        d = self.prog.logic.get((name, sig))
        arity = len(sig)
        if d is None:
            if (name, "inductive") in self.prog.logic:
                raise AcslRefusal("inductive", name, self.where)
            if name in self.prog.funcs:
                raise AcslRefusal("calls-other-method", name, self.where)
            raise AcslRefusal("unknown-logic", f"{name}/{arity}", self.where)
        if d.body is None:
            raise AcslRefusal("axiomatic" if d.axiomatic else "abstract-logic", name, d.where)
        return d

    def _recursive(self, d: LogicDef) -> bool:
        found = []

        def fn(e):
            if e.k == "call" and e.a[0] == d.name and len(e.a[2]) == len(d.params):
                found.append(e)
        walk(d.body, fn)
        ptrs = {pn for ty, pn in d.params if ty.kind == "ptr"}
        sig = param_sig(d.params)
        return any("".join("p" if (a.k == "var" and a.a[0] in ptrs) else "v" for a in c.a[2]) == sig
                   for c in found)

    def _register_rec(self, d: LogicDef) -> None:
        key = (d.name, param_sig(d.params))
        if key in self.rec:
            return
        same_name = [k for k in self.prog.logic if k[0] == d.name]
        same_arity = [k for k in same_name if len(k[1]) == len(d.params)]
        dname = d.name if len(same_name) == 1 else \
            (f"{d.name}{len(d.params)}" if len(same_arity) == 1 else f"{d.name}_{key[1]}")
        if dname in DAFNY_KEYWORDS or dname == self.fname:
            dname = dname + "_fn"
        self.rec[key] = None      # recursion guard while its body expands
        params = []
        kinds = {}
        for ty, pn in d.params:
            if ty.kind == "ptr":
                if ty.elem.kind != "int" or not ty.elem.signed:
                    raise AcslRefusal("array-element-type", f"{d.name}.{pn}", d.where)
                kinds[pn] = "seq"
            elif ty.kind in ("int", "integer"):
                kinds[pn] = "int"
            elif ty.kind in ("bool", "boolean"):
                kinds[pn] = "bool"
            else:
                raise AcslRefusal("c-type", f"{d.name}.{pn}: {ty.show()}", d.where)
            params.append((pn, kinds[pn]))
        body = d.body
        # the recursion shape: `B ? base : ...` at the top, every self-call equal
        # to the parameters except one, which is `p - 1`
        if body.k != "ite":
            raise AcslRefusal("logic-recursion-shape", f"{d.name}: body is not `guard ? base : step`", d.where)
        base_guard = body.a[0]
        calls = []

        def fn(e):
            if e.k == "call" and e.a[0] == d.name and len(e.a[2]) == len(d.params):
                calls.append(e)
        walk(body.a[2], fn)
        walk(body.a[0], fn)
        walk(body.a[1], fn)
        rec_param = None
        for call in calls:
            for (ty, pn), a in zip(d.params, call.a[2]):
                if a.k == "var" and a.a[0] == pn:
                    continue
                if a.k == "bin" and a.a[0] == "-" and a.a[1].k == "var" and a.a[1].a[0] == pn \
                        and a.a[2].k == "int" and a.a[2].a[0] == 1 and kinds[pn] == "int":
                    if rec_param not in (None, pn):
                        raise AcslRefusal("logic-recursion-shape", f"{d.name}: two recursion parameters", d.where)
                    rec_param = pn
                    continue
                raise AcslRefusal("logic-recursion-shape", f"{d.name}: argument {acsl_or(a)}", d.where)
        if rec_param is None:
            raise AcslRefusal("logic-recursion-shape", f"{d.name}: no decreasing parameter", d.where)
        # measure from the base guard: `p <= e` -> p - e, `p < e` -> p - e + 1, `e >= p` likewise
        g = base_guard
        measure = None
        if g.k == "bin" and g.a[0] in ("<=", "<", ">=", ">"):
            op, l, r = g.a
            if op in (">=", ">"):
                op, l, r = {">=": "<=", ">": "<"}[op], r, l
            if l.k == "var" and l.a[0] == rec_param and rec_param not in free_vars(r):
                measure = E("bin", ("-", l, r), g.line)
                if op == "<":
                    measure = E("bin", ("+", measure, E("int", (1,))), g.line)
        if measure is None:
            raise AcslRefusal("logic-recursion-shape", f"{d.name}: base guard {acsl_or(g)}", d.where)
        # domain: every int parameter the base guard or an index mentions, within [0, len(x)]
        # of every array read at an index that mentions the recursion parameter
        idx_params, arrays = set(), []

        def fi(e):
            if e.k == "index" and e.a[0].k == "var" and kinds.get(e.a[0].a[0]) == "seq":
                fv = free_vars(e.a[1]) & {pn for pn, k in params if k == "int"}
                idx_params.update(fv)
                if rec_param in fv and e.a[0].a[0] not in arrays:
                    arrays.append(e.a[0].a[0])
        walk(body, fi)
        q = ({rec_param} | (free_vars(base_guard) & {pn for pn, k in params if k == "int"}) | idx_params)
        dom = []
        for arr in arrays:
            for pn in [pn for pn, k in params if pn in q]:
                dom.append(f"0 <= {pn} <= {arr}_n")
        # body text with guarded reads
        self._guarded = 0
        ren = {pn: pn for pn, _ in params}
        self.rec[key] = RecFun(d.name, len(d.params), dname, params, rec_param, measure, base_guard, dom, 0,
                               "bool" if d.result.kind in ("boolean", "bool") else "int",
                               [(pn, acsl_type(ty)) for ty, pn in d.params])
        saved = self._ptrs
        self._ptrs = {pn for pn, k in params if k == "seq"}
        body_x = self.expand(strip_at(body, d.labels), 0, d.labels)
        self._ptrs = saved
        text = self.dx(body_x, ren, "fun", {pn for pn, k in params if k == "seq"}, guard=True, fun=d)
        self.rec[key].guarded_reads = self._guarded
        ps = ", ".join(f"{pn}: {'seq<int>' if k == 'seq' else ('bool' if k == 'bool' else 'int')}"
                       for pn, k in params)
        res = "bool" if d.result.kind in ("boolean", "bool") else "int"
        self.rec_dafny += [f"function {dname}({ps}): {res}",
                           f"  decreases {self.dx(measure, ren, 'fun', set())}",
                           "{", f"  {text}", "}", ""]
        self.rec_order.append(key)
        if self._guarded:
            self.rewrites.append("logic-read-guarded")

    def dx(self, e: E, ren: dict, pos: str, seqs: set, guard: bool = False, fun: LogicDef = None) -> str:
        """Dafny text of an (expanded) ACSL expression."""
        D = lambda x: self.dx(x, ren, pos, seqs, guard, fun)   # noqa: E731
        k = e.k
        if k == "int":
            return str(e.a[0]) if e.a[0] >= 0 else f"({e.a[0]})"
        if k == "bool":
            return "true" if e.a[0] else "false"
        if k == "var":
            nm = e.a[0]
            if pos != "fun" and nm in self.len_of:
                return f"|{ren.get(self.len_of[nm], self.len_of[nm])}|"
            if nm == "\\nothing":
                raise AcslRefusal("source-unparseable", "\\nothing in an expression", self.where)
            if pos == "fun" and nm not in ren:
                raise AcslRefusal("logic-free-variable", nm, fun.where if fun else self.where)
            return ren.get(nm, nm)
        if k == "result":
            if pos != "post":
                raise AcslRefusal("source-unparseable", "\\result outside ensures", self.where)
            return self.ret_name
        if k == "old":
            if pos != "post":
                raise AcslRefusal("old-outside-post", "\\old", self.where)
            return D(e.a[0])
        if k == "at":
            x, lab = e.a
            if lab == "Here":
                return D(x)
            if lab in ("Pre", "Old"):
                pre = {p: self.mutated.get(p, p) for p in self.env}
                return self.dx(x, {**ren, **pre}, pos, seqs, guard, fun)
            raise AcslRefusal("at-label", lab, self.where)
        if k == "un":
            op, x = e.a
            if op == "!":
                return f"!({D(x)})"
            if op == "-":
                return f"(-{D(x)})"
            if op == "+":
                return D(x)
            if op == "*":
                raise AcslRefusal("pointer-deref", acsl_or(x), self.where)
            raise AcslRefusal("bitwise", op, self.where)
        if k == "bin":
            op, l, r = e.a
            if op in ("&&", "||", "==>", "<==>"):
                return f"({D(l)} {op} {D(r)})"
            if op in REL_OPS:
                return f"({D(l)} {op} {D(r)})"
            if op in ("+", "-", "*"):
                if l.k == "var" and l.a[0] in (seqs | set(self.seq_len)) or \
                        r.k == "var" and r.a[0] in (seqs | set(self.seq_len)):
                    raise AcslRefusal("pointer-arith", acsl_or(e), self.where)
                return f"({D(l)} {op} {D(r)})"
            if op in ("/", "%"):
                if not (self._nonneg(l, fun) and self._nonneg(r, fun)):
                    if not (r.k == "int" and r.a[0] > 0):
                        raise AcslRefusal("signed-division", acsl_or(e), self.where)
                    # ACSL truncates, t is Euclidean: equal iff the dividend is >= 0 there.
                    # Not decided here: the check must PROVE the clause equivalent, or the
                    # task is refused (lift_acsl_check, `spec-division-unproved`).
                    self.spec_division = True
                return f"({D(l)} {op} {D(r)})"
            if op == "^^":
                raise AcslRefusal("xor", op, self.where)
            raise AcslRefusal("bitwise", op, self.where)
        if k == "chain":
            ops, xs = e.a
            if len({o in ("<", "<=") for o in ops}) > 1 or any(o in ("!=", ">", ">=") for o in ops):
                parts = [f"({D(a)} {o} {D(b)})" for a, o, b in zip(xs, ops, xs[1:])]
                return "(" + " && ".join(parts) + ")"
            s = D(xs[0])
            for o, x in zip(ops, xs[1:]):
                s += f" {o} {D(x)}"
            return f"({s})"
        if k == "ite":
            return f"(if {D(e.a[0])} then {D(e.a[1])} else {D(e.a[2])})"
        if k == "index":
            base, i = e.a
            if i.k == "range":
                raise AcslRefusal("array-range", acsl_or(e), self.where)
            if base.k != "var" or not (base.a[0] in self.seq_len or base.a[0] in seqs):
                raise AcslRefusal("pointer-arith", acsl_or(e), self.where)
            b = D(base)
            ix = D(i)
            if guard:
                self._guarded += 1
                return f"(if 0 <= {ix} < |{b}| then {b}[{ix}] else 0)"
            return f"{b}[{ix}]"
        if k == "call":
            name, labels, args = e.a
            if name in LOGIC_BUILTINS:
                xs = [D(a) for a in args]
                if name == "\\abs" and len(xs) == 1:
                    return f"(if {xs[0]} < 0 then -{xs[0]} else {xs[0]})"
                if name in ("\\max", "\\min") and len(xs) == 2:
                    op = ">=" if name == "\\max" else "<="
                    return f"(if {xs[0]} {op} {xs[1]} then {xs[0]} else {xs[1]})"
                raise AcslRefusal("acsl-builtin", name, self.where)
            raise AcslRefusal("unknown-logic", f"{name}/{len(args)}", self.where)
        if k == "rcall":
            name, sig, args = e.a
            rf = self.rec.get((name, sig))
            if rf is None:
                raise AcslRefusal("unknown-logic", f"{name}/{sig}", self.where)
            outs = []
            for (pn, kind), a in zip(rf.params, args):
                if kind == "seq":
                    if a.k != "var" or not (a.a[0] in self.seq_len or a.a[0] in seqs):
                        raise AcslRefusal("pointer-arith", f"{name} called on {acsl_or(a)}", self.where)
                outs.append(D(a))
            return f"{rf.dafny_name}({', '.join(outs)})"
        if k == "quant":
            kind, binders, body = e.a
            bs = []
            inner = dict(ren)
            for ty, nm in binders:
                if ty.kind == "ptr":
                    raise AcslRefusal("pointer-quantifier", nm, self.where)
                if ty.kind not in ("integer",):
                    raise AcslRefusal("typed-quantifier", f"{ty.show()} {nm}", self.where)
                inner[nm] = nm
                bs.append(f"{nm}: int")
            b = self.dx(body, inner, pos, seqs, guard, fun)
            return f"({kind} {', '.join(bs)} :: {b})"
        if k == "cast":
            ty, x = e.a
            if x.k == "int" and ty.kind in ("int", "integer"):
                return D(x)
            raise AcslRefusal("cast", f"({ty.show()})", self.where)
        if k == "let":
            return D(subst(e.a[2], {e.a[0]: e.a[1]}))
        if k == "valid":
            raise AcslRefusal("valid-nested", acsl_or(e), self.where)
        if k == "sep":
            raise AcslRefusal("separated-nested", "\\separated", self.where)
        if k == "member":
            raise AcslRefusal("struct", acsl_or(e), self.where)
        if k in ("assign", "incr"):
            raise AcslRefusal("side-effect-expression", k, self.where)
        raise AcslRefusal("acsl-construct", k, self.where)

    def _nonneg(self, x: E, fun) -> bool:
        """Is x non-negative by its C type: an unsigned variable, a non-negative
        literal, or +,*,/,% of such (subtraction is excluded: its unsigned
        wrap is what the nat typing makes a proof obligation, so a `-` operand
        is accepted only when it is itself unsigned-typed arithmetic in the body)."""
        if x.k == "int":
            return x.a[0] >= 0
        if x.k == "var":
            ty = self.env.get(x.a[0]) or self.local_types.get(x.a[0])
            return ty is not None and ty.kind == "int" and ty.signed is False
        if x.k == "bin" and x.a[0] in ("+", "*", "/", "%"):
            return self._nonneg(x.a[1], fun) and self._nonneg(x.a[2], fun)
        if x.k == "bin" and x.a[0] == "-" and getattr(self, "_in_body", False):
            return self._nonneg(x.a[1], fun) and self._nonneg(x.a[2], fun)
        return False

    # ------------------------------------------------------------ statements
    def block(self, stmts: list, depth: int) -> list[str]:
        out = []
        for st in stmts:
            out += self.stmt(st, depth)
        return out

    @property
    def local_types(self) -> dict:
        return {d["c_name"]: d["_ty"] for d in self.locals if "_ty" in d}

    def ctyp(self, e: E) -> CType:
        """The C type of a body expression (int promotions ignored: only the
        signedness and bool-ness matter here)."""
        k = e.k
        if k == "int":
            return CType("int", True, "int")
        if k == "bool":
            return CType("bool")
        if k == "var":
            nm = e.a[0]
            ty = self.env.get(nm) or self.local_types.get(nm)
            if ty is None:
                raise AcslRefusal("unknown-name", nm, self.where)
            return ty
        if k == "index":
            return self.ctyp(e.a[0]).elem or CType("int", True, "int")
        if k == "un":
            return CType("bool") if e.a[0] == "!" else self.ctyp(e.a[1])
        if k == "bin":
            op = e.a[0]
            if op in REL_OPS or op in ("&&", "||"):
                return CType("bool")
            lt, rt = self.ctyp(e.a[1]), self.ctyp(e.a[2])
            if lt.kind == "bool" or rt.kind == "bool":
                return CType("int", True, "int")
            if lt.is_unsigned() or rt.is_unsigned():
                return CType("int", False, "int")
            return CType("int", True, "int")
        if k == "ite":
            return self.ctyp(e.a[1])
        if k == "cast":
            return e.a[0]
        return CType("int", True, "int")

    def cx(self, e: E, want_bool: bool = False) -> str:
        """Dafny text of a C body expression (no side effects allowed here)."""
        k = e.k
        if k in ("assign", "incr"):
            raise AcslRefusal("side-effect-expression", acsl_or(e), self.where)
        if k == "call":
            raise AcslRefusal("calls-other-method", e.a[0], self.where)
        ty = self.ctyp(e)
        text = self._cx(e)
        if want_bool and ty.kind != "bool":
            return f"({text} != 0)"
        return text

    def _cx(self, e: E) -> str:
        k = e.k
        C = self.cx
        if k == "int":
            return str(e.a[0])
        if k == "bool":
            return "true" if e.a[0] else "false"
        if k == "var":
            nm = e.a[0]
            if nm in self.len_of:
                return f"|{self.len_of[nm]}|"
            if nm in self.seq_len:
                raise AcslRefusal("pointer-arith", f"{nm} used as a value", self.where)
            return nm
        if k == "index":
            base, i = e.a
            if base.k != "var" or base.a[0] not in self.seq_len:
                raise AcslRefusal("pointer-arith", acsl_or(e), self.where)
            return f"{base.a[0]}[{C(i)}]"
        if k == "un":
            op, x = e.a
            if op == "!":
                return f"!{C(x, True)}"
            if op == "-":
                if self.ctyp(x).is_unsigned():
                    raise AcslRefusal("unsigned-negation", acsl_or(e), self.where)
                return f"(-{C(x)})"
            if op == "+":
                return C(x)
            if op in ("*", "&"):
                raise AcslRefusal("pointer-deref" if op == "*" else "address-of", acsl_or(e), self.where)
            raise AcslRefusal("bitwise", op, self.where)
        if k == "bin":
            op, l, r = e.a
            if op in ("&&", "||"):
                return f"({C(l, True)} {op} {C(r, True)})"
            lt, rt = self.ctyp(l), self.ctyp(r)
            if op in REL_OPS:
                if (lt.kind == "bool") != (rt.kind == "bool"):
                    raise AcslRefusal("bool-int-mix", acsl_or(e), self.where)
                if (lt.is_unsigned() != rt.is_unsigned()) and op not in ("==", "!=") \
                        and lt.kind == "int" and rt.kind == "int":
                    # C converts the signed operand to unsigned: a negative one compares huge
                    if not (self._lit_nonneg(l) or self._lit_nonneg(r)):
                        raise AcslRefusal("mixed-sign-comparison", acsl_or(e), self.where)
                return f"({C(l)} {op} {C(r)})"
            if op in ("+", "-", "*"):
                if lt.kind == "bool" or rt.kind == "bool":
                    raise AcslRefusal("bool-arith", acsl_or(e), self.where)
                if (lt.is_unsigned() != rt.is_unsigned()) and not (self._lit_nonneg(l) or self._lit_nonneg(r)):
                    raise AcslRefusal("mixed-sign-arith", acsl_or(e), self.where)
                return f"({C(l)} {op} {C(r)})"
            if op in ("/", "%"):
                if not (lt.is_unsigned() or self._lit_nonneg(l)) or not (rt.is_unsigned() or self._lit_nonneg(r)) \
                        or not (lt.is_unsigned() or rt.is_unsigned()):
                    raise AcslRefusal("signed-division", acsl_or(e), self.where)
                return f"({C(l)} {op} {C(r)})"
            raise AcslRefusal("bitwise", op, self.where)
        if k == "ite":
            return f"(if {C(e.a[0], True)} then {C(e.a[1])} else {C(e.a[2])})"
        if k == "cast":
            ty, x = e.a
            if x.k == "int" and ty.kind in ("int", "bool"):
                return str(x.a[0]) if ty.kind == "int" else ("true" if x.a[0] else "false")
            raise AcslRefusal("cast", f"({ty.show()})", self.where)
        if k == "member":
            raise AcslRefusal("struct", acsl_or(e), self.where)
        raise AcslRefusal("c-construct", k, self.where)

    def _lit_nonneg(self, x: E) -> bool:
        return x.k == "int" and x.a[0] >= 0

    def decl(self, ty: CType, name: str, init, depth: int) -> list[str]:
        ind = "  " * depth
        if ty.kind == "ptr":
            raise AcslRefusal("pointer-local", name, self.where)
        if ty.kind == "struct":
            raise AcslRefusal("struct", name, self.where)
        if name in self.scope:
            raise AcslRefusal("redeclared-local", name, self.where)
        if name in DAFNY_KEYWORDS:
            raise AcslRefusal("reserved-name", name, self.where)
        self.scope.add(name)
        if init is None:
            raise AcslRefusal("uninitialized-local", name, self.where)
        rhs = self.cx(init, ty.kind == "bool")
        self.locals.append({"c_name": name, "c_type": ty.show(), "dafny_name": name, "_ty": ty})
        return [f"{ind}var {name}: {self.dty(ty)} := {rhs};"]

    def assign_line(self, e: E, depth: int) -> list[str]:
        ind = "  " * depth
        if e.k == "incr":
            op, tgt, _prefix = e.a
            self._target(tgt)
            return [f"{ind}{tgt.a[0]} := {tgt.a[0]} {'+' if op == '++' else '-'} 1;"]
        if e.k == "assign":
            op, tgt, rhs = e.a
            self._target(tgt)
            ty = self.ctyp(tgt)
            if op == "=":
                return [f"{ind}{tgt.a[0]} := {self.cx(rhs, ty.kind == 'bool')};"]
            bop = op[:-1]
            if bop not in ("+", "-", "*", "/", "%"):
                raise AcslRefusal("bitwise", op, self.where)
            return [f"{ind}{tgt.a[0]} := {self.cx(E('bin', (bop, tgt, rhs), e.line))};"]
        if e.k == "call":
            raise AcslRefusal("calls-other-method", e.a[0], self.where)
        raise AcslRefusal("expression-statement", e.k, self.where)

    def _target(self, t: E) -> None:
        if t.k != "var":
            raise AcslRefusal("array-write", acsl_or(t), self.where)
        if t.a[0] in self.seq_len or t.a[0] in self.len_of:
            raise AcslRefusal("pointer-arith", t.a[0], self.where)
        if t.a[0] in self.env and t.a[0] not in self.mutated:
            raise AcslRefusal("param-assigned", t.a[0], self.where)

    def loop_spec(self, la: Optional[LoopAnnot], depth: int, line: int) -> list[str]:
        ind = "  " * depth
        out = []
        body_ren = {p: p for p in self.env}
        rec = {"inv": [], "variant": None, "line": line}
        if la is None:
            raise AcslRefusal("loop-without-invariant", f"loop at line {line}", self.where)
        if not la.invariants:
            raise AcslRefusal("loop-without-invariant", f"loop at line {line}", self.where)
        pre = {p: self.mutated.get(p, p) for p in self.env}
        for inv in la.invariants:
            out.append(f"{ind}  invariant {self.spec(inv, body_ren, 'loop')}")
            rec["inv"].append(acsl(single_state(self._at_pre(inv, pre), {}), {}))
        if la.variant is not None:
            out.append(f"{ind}  decreases {self.spec(la.variant, body_ren, 'loop')}")
            rec["variant"] = acsl(single_state(self._at_pre(la.variant, pre), {}), {})
        else:
            self.rewrites.append("variant-inferred-by-dafny")
        for locs in la.assigns:
            for x in locs:
                if x.k != "var":
                    raise AcslRefusal("array-write", "loop assigns " + acsl_or(x), self.where)
        if la.assigns:
            self.drop("loop-assigns-scalars")
        self.loops.append(rec)
        return out

    def _at_pre(self, e: E, pre: dict) -> E:
        """\\at(x, Pre) -> x's pre-state name, for the check's source text."""
        if not isinstance(e, E):
            return e
        if e.k == "at" and e.a[1] in ("Pre", "Old"):
            return subst(e.a[0], {p: E("var", (q,)) for p, q in pre.items() if p != q})
        return E(e.k, tuple(self._at_pre(x, pre) if isinstance(x, E) else
                            (tuple(self._at_pre(y, pre) for y in x) if isinstance(x, tuple) and x
                             and isinstance(x[0], E) else x) for x in e.a), e.line)

    def stmt(self, s: tuple, depth: int) -> list[str]:
        ind = "  " * depth
        kind = s[0]
        self._in_body = True
        if kind == "skip":
            return []
        if kind == "block":
            return self.block(s[1], depth)
        if kind == "decl":
            _, ty, name, init, line = s
            return self.decl(ty, name, init, depth)
        if kind == "expr":
            return self.assign_line(s[1], depth)
        if kind == "assert":
            self.drop("assert")
            return []
        if kind == "if":
            _, c, th, el, line = s
            out = [f"{ind}if {self.cx(c, True)} {{"]
            out += self.block(th, depth + 1)
            if el:
                out.append(f"{ind}}} else {{")
                out += self.block(el, depth + 1)
            out.append(f"{ind}}}")
            return out
        if kind == "while":
            _, c, body, la, line = s
            self._no_continue(body)
            out = [f"{ind}while {self.cx(c, True)}"]
            out += self.loop_spec(la, depth, line)
            out.append(f"{ind}{{")
            out += self.block(body, depth + 1)
            out.append(f"{ind}}}")
            return out
        if kind == "for":
            _, init, c, step, body, la, line = s
            self._no_continue(body)
            out = []
            for st in init:
                out += self.stmt(st, depth)
            if c is None:
                raise AcslRefusal("infinite-loop", "for (;;)", self.where)
            out.append(f"{ind}while {self.cx(c, True)}")
            out += self.loop_spec(la, depth, line)
            out.append(f"{ind}{{")
            out += self.block(body, depth + 1)
            if step is not None:
                out += self.assign_line(step, depth + 1)
            out.append(f"{ind}}}")
            self.rewrites.append("for-as-while")
            return out
        if kind == "do":
            raise AcslRefusal("do-while", "do ... while", self.where)
        if kind == "return":
            _, x, line = s
            if x is None:
                raise AcslRefusal("void-result", "return;", self.where)
            return [f"{ind}return {self.cx(x, self.f.ret.kind == 'bool')};"]
        if kind == "break":
            raise AcslRefusal("break", "break", self.where)
        if kind == "continue":
            raise AcslRefusal("continue", "continue", self.where)
        raise AcslRefusal("c-construct", kind, self.where)

    def _no_continue(self, body) -> None:
        def go(s):
            if isinstance(s, tuple) and s:
                if s[0] == "continue":
                    raise AcslRefusal("continue", "continue", self.where)
                if s[0] in ("while", "for", "do"):
                    return
                for x in s:
                    go(x)
            elif isinstance(s, list):
                for x in s:
                    go(x)
        go(body)


def code_only(body):
    """The statements without their assertions (ACSL, not C: a logic call there is no call)."""
    if isinstance(body, list):
        return [code_only(s) for s in body if not (isinstance(s, tuple) and s and s[0] == "assert")]
    if isinstance(body, tuple):
        return tuple(code_only(x) for x in body)
    return body


def walk_stmts(body, fn) -> None:
    """Every expression E in a statement list, through every statement kind."""
    def go(s):
        if isinstance(s, E):
            walk(s, fn)
        elif isinstance(s, (tuple, list)):
            for x in s:
                go(x)
    go(body)


def acsl_or(e) -> str:
    try:
        return acsl(e, {})
    except Exception:  # noqa: BLE001 - only for messages
        return getattr(e, "k", str(e))


# The C statement parser leaves assignments as `bin` "=" etc.; C assignment
# operators are not in the ACSL precedence table, so they are parsed here.

ASSIGN_OPS = ("=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>=")


def _parser_expr_with_assign(self) -> E:
    x = Parser.binding(self)
    if not self.logic_mode and self.peek().kind == "op" and self.peek().text in ASSIGN_OPS:
        t = self.next()
        rhs = _parser_expr_with_assign(self)
        return E("assign", (t.text, x, rhs), t.line)
    return x


Parser.expr = _parser_expr_with_assign


# --------------------------------------------------------------------- API --

def translate(c_file: Path, root: Path, function: Optional[str] = None) -> Lifted:
    """The Dafny rendering of one corpus function, or AcslRefusal."""
    c_file = Path(c_file)
    prog = load(c_file, Path(root))
    fname = function or c_file.stem
    if fname not in prog.funcs:
        defined = [f for f, g in prog.funcs.items() if g.body is not None and f != "<globals>"]
        if len(defined) == 1:
            fname = defined[0]
        else:
            raise AcslRefusal("no-function", f"{c_file.stem} not defined in {c_file.name}")
    if "<globals>" in prog.funcs:
        raise AcslRefusal("global-variable", "a global variable", c_file.name)
    return Translator(prog, fname).run()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("file", type=Path)
    ap.add_argument("--root", type=Path, default=None, help="the corpus's StandardAlgorithms directory")
    ap.add_argument("--function", default=None)
    ap.add_argument("--json", action="store_true", help="print the sidecar too")
    a = ap.parse_args(argv)
    root = a.root or a.file.resolve().parent.parent
    try:
        lifted = translate(a.file, root, a.function)
    except AcslRefusal as r:
        print(f"refused: {r.reason}: {r.detail} {r.where}")
        return 1
    print(lifted.dafny)
    if a.json:
        print(json.dumps(lifted.sidecar(), indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
