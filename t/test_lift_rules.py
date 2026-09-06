"""Plain-python tests for lift_classify.py and lift_rewrite.py (owned by
the same implementer as this file; see LIFTER-DESIGN.md's header table).

lift_parse.py is still a stub (`raise NotImplementedError`) as of this
writing, so this file carries its own small parser shim (`_ShimParser`
below) rather than waiting on it, per this task's own instruction: "parse
the banked rprint of the source (lift_parse if the front is ready;
otherwise write the smallest parser shim you need inside your test file
and say so)". This IS that "say so": the shim is a hand-written
recursive-descent reader of dafny's own `--rprint` output, built directly
from `lift_ast.py`'s node docstrings (which reproduce section 3's EBNF
one production at a time) and cross-checked against the real banked
rprint files this test file runs on. It is deliberately scoped to what
those real files and this file's own synthetic snippets need, not to
section 3's full grammar -- an unrecognised top-level keyword is a
`_ShimParseError`, exactly like `lift_parse.LiftParseError`'s contract,
so a gap here surfaces as a loud test failure rather than a silent
misparse. Known gaps the shim does not attempt: nested set/map
comprehensions, higher-order function types, iterator declarations. None
of these appear in the 77 in-fragment files or the 21 seeds (both
exercised below); where they were guessed at all it is a best effort,
never load-bearing for this file's own PASS/FAIL verdicts.

Run as: cd <repo>/t && python3 test_lifter.py test_lift_rules
   or directly: cd <repo>/t && python3 test_lift_rules.py
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import traceback
from pathlib import Path

import corpora
import lift_ast as A
import lift_classify as C
import lift_rewrite as R
import fuzz_lower
import interp

CORPUS_RPRINT = corpora.CORPUS_RPRINT
INFRAGMENT = corpora.INFRAGMENT_TXT


# ===========================================================================
# Part 1: the parser shim (lexer + recursive descent), producing lift_ast
# nodes only. This section is infrastructure, not the deliverable; the
# deliverable is lift_classify.py / lift_rewrite.py, tested in Part 3.
# ===========================================================================

class _ShimParseError(Exception):
    def __init__(self, token: str, line: int):
        super().__init__(f"shim parser: unexpected token {token!r} at line {line}")
        self.token = token
        self.line = line


_PUNCT = sorted([
    "<==>", "..", "::", "==>", "<==", ":=", ":|", "==", "!=", "<=", ">=",
    "&&", "||", "!in", "->", "~>", "-->", "<", ">", "(", ")", "[", "]",
    "{", "}", ",", ":", ";", "|", ".", "+", "-", "*", "/", "%", "=", "?", "!",
], key=len, reverse=True)

_KEYWORDS = {
    "method", "function", "predicate", "ghost", "lemma", "least", "greatest",
    "twostate", "returns", "requires", "ensures", "invariant", "decreases",
    "modifies", "reads", "if", "then", "else", "while", "for", "to",
    "downto", "var", "return", "break", "continue", "assert", "assume",
    "calc", "forall", "exists", "in", "print", "expect", "reveal", "label",
    "new", "old", "fresh", "unchanged", "true", "false", "int", "bool",
    "real", "char", "string", "nat", "object", "array", "seq", "set",
    "iset", "multiset", "map", "imap", "as", "is", "class", "trait",
    "datatype", "codatatype", "type", "newtype", "const", "iterator",
    "module", "import", "export", "case", "by", "not", "and", "or",
}


class _Tok:
    __slots__ = ("kind", "text", "line")

    def __init__(self, kind, text, line):
        self.kind = kind
        self.text = text
        self.line = line

    def __repr__(self):
        return f"Tok({self.kind},{self.text!r}@{self.line})"


def _lex(text: str) -> list[_Tok]:
    toks: list[_Tok] = []
    i = 0
    n = len(text)
    line = 1
    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
            i += 1
            continue
        if c in " \t\r":
            i += 1
            continue
        if text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j == -1 else j
            continue
        if text.startswith("/*", i):
            depth = 1
            i += 2
            while i < n and depth > 0:
                if text.startswith("/*", i):
                    depth += 1
                    i += 2
                elif text.startswith("*/", i):
                    depth -= 1
                    i += 2
                else:
                    if text[i] == "\n":
                        line += 1
                    i += 1
            continue
        if c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                if text[j] == "\\":
                    j += 1
                j += 1
            toks.append(_Tok("string", text[i:j + 1], line))
            i = j + 1
            continue
        if c == "'":
            # could be a char literal 'x' or an apostrophe glued onto an
            # identifier tail (gcd') -- identifiers are handled below by
            # including trailing apostrophes there, so a bare "'" reaching
            # here starts a char literal.
            j = i + 1
            while j < n and text[j] != "'":
                if text[j] == "\\":
                    j += 1
                j += 1
            toks.append(_Tok("char", text[i:j + 1], line))
            i = j + 1
            continue
        if c.isdigit():
            j = i
            while j < n and text[j].isdigit():
                j += 1
            if j < n and text[j] == "." and j + 1 < n and text[j + 1].isdigit():
                j += 1
                while j < n and text[j].isdigit():
                    j += 1
                toks.append(_Tok("real", text[i:j], line))
            else:
                toks.append(_Tok("int", text[i:j], line))
            i = j
            continue
        if c.isalpha() or c == "_":
            j = i
            while j < n and (text[j].isalnum() or text[j] in "_"):
                j += 1
            while j < n and text[j] == "'":
                j += 1
            word = text[i:j]
            toks.append(_Tok("id", word, line))
            i = j
            continue
        matched = None
        for p in _PUNCT:
            if text.startswith(p, i):
                matched = p
                break
        if matched is None:
            raise _ShimParseError(c, line)
        toks.append(_Tok("punct", matched, line))
        i += len(matched)
    toks.append(_Tok("eof", "", line))
    return toks


class _P:
    def __init__(self, toks: list[_Tok]):
        self.toks = toks
        self.i = 0

    def peek(self, k=0) -> _Tok:
        j = self.i + k
        return self.toks[j] if j < len(self.toks) else self.toks[-1]

    def at(self, text) -> bool:
        return self.peek().text == text

    def at_kind(self, kind) -> bool:
        return self.peek().kind == kind

    def advance(self) -> _Tok:
        t = self.toks[self.i]
        if self.i < len(self.toks) - 1:
            self.i += 1
        return t

    def expect(self, text) -> _Tok:
        t = self.peek()
        if t.text != text:
            raise _ShimParseError(t.text or "<eof>", t.line)
        return self.advance()

    def ident(self) -> _Tok:
        t = self.peek()
        if t.kind != "id":
            raise _ShimParseError(t.text or "<eof>", t.line)
        return self.advance()

    # -- attrs --------------------------------------------------------
    def parse_attrs(self) -> tuple:
        attrs = []
        while self.at("{") and self.peek(1).text == ":":
            line = self.peek().line
            self.advance()
            self.advance()
            name = self.ident().text
            args = []
            if not self.at("}"):
                args.append(self.expr())
                while self.at(","):
                    self.advance()
                    args.append(self.expr())
            self.expect("}")
            attrs.append(A.Attr(line, name, tuple(args)))
        return tuple(attrs)

    # -- types ----------------------------------------------------------
    def parse_type(self) -> A.Type:
        t = self.peek()
        line = t.line
        if t.text == "(":
            self.advance()
            items = []
            if not self.at(")"):
                items.append(self.parse_type())
                while self.at(","):
                    self.advance()
                    items.append(self.parse_type())
            self.expect(")")
            if self.at("->") or self.at("~>") or self.at("-->"):
                self.advance()
                cod = self.parse_type()
                return A.Type(line, kind="func", args=tuple(items) + (cod,))
            if len(items) == 1:
                return items[0]
            return A.Type(line, kind="tuple", args=tuple(items))
        if t.kind == "id" and t.text.startswith("array"):
            self.advance()
            nullable = False
            if self.at("?"):
                self.advance()
                nullable = True
            args = ()
            if self.at("<"):
                self.advance()
                args = (self.parse_type(),)
                self.expect(">")
            kind = "array" if t.text == "array" else t.text
            return A.Type(line, kind=kind, args=args, nullable=nullable)
        if t.text in ("int", "bool", "real", "char", "string", "nat", "object"):
            self.advance()
            return A.Type(line, kind=t.text)
        if t.text in ("seq", "set", "iset", "multiset"):
            self.advance()
            args = ()
            if self.at("<"):
                self.advance()
                args = (self.parse_type(),)
                self.expect(">")
            return A.Type(line, kind=t.text, args=args)
        if t.text in ("map", "imap"):
            self.advance()
            args = ()
            if self.at("<"):
                self.advance()
                k = self.parse_type()
                self.expect(",")
                v = self.parse_type()
                self.expect(">")
                args = (k, v)
            return A.Type(line, kind=t.text, args=args)
        if t.kind == "id":
            self.advance()
            name = t.text
            nullable = False
            if self.at("?"):
                self.advance()
                nullable = True
            args = ()
            if self.at("<"):
                self.advance()
                items = [self.parse_type()]
                while self.at(","):
                    self.advance()
                    items.append(self.parse_type())
                self.expect(">")
                args = tuple(items)
            return A.Type(line, kind="id", args=args, nullable=nullable, name=name)
        raise _ShimParseError(t.text or "<eof>", t.line)

    # -- params -----------------------------------------------------------
    def parse_params(self) -> list[A.Param]:
        self.expect("(")
        out = []
        if not self.at(")"):
            out.append(self._one_param())
            while self.at(","):
                self.advance()
                out.append(self._one_param())
        self.expect(")")
        return out

    def _one_param(self) -> A.Param:
        line = self.peek().line
        ghost = False
        if self.at("ghost"):
            self.advance()
            ghost = True
        name = self.ident().text
        ty = None
        if self.at(":"):
            self.advance()
            ty = self.parse_type()
        return A.Param(line, name, ty, ghost)

    def parse_binders(self) -> tuple[A.Param, ...]:
        out = [self._one_param()]
        while self.at(","):
            self.advance()
            out.append(self._one_param())
        return tuple(out)

    # -- expr list / star -------------------------------------------------
    def parse_expr_list(self) -> list:
        out = [self.expr()]
        while self.at(","):
            self.advance()
            out.append(self.expr())
        return out

    def parse_expr_list_or_star(self):
        if self.at("*"):
            line = self.peek().line
            self.advance()
            return A.Star(line)
        return tuple(self.parse_expr_list())

    # -- expressions, precedence climbing ----------------------------------
    def expr(self) -> A.Expr:
        return self._iff()

    def _iff(self) -> A.Expr:
        left = self._implies()
        while self.at("<==>"):
            line = self.peek().line
            self.advance()
            right = self._implies()
            left = A.Iff(line, left, right)
        return left

    def _implies(self) -> A.Expr:
        left = self._orand()
        if self.at("==>"):
            line = self.peek().line
            self.advance()
            right = self._implies()
            return A.Implies(line, left, right)
        while self.at("<=="):
            line = self.peek().line
            self.advance()
            right = self._orand()
            left = A.Implies(line, right, left)
        return left

    def _orand(self) -> A.Expr:
        left = self._not()
        if self.at("&&"):
            line = self.peek().line
            args = [left]
            while self.at("&&"):
                self.advance()
                args.append(self._not())
            return A.NaryBool(line, "&&", tuple(args))
        if self.at("||"):
            line = self.peek().line
            args = [left]
            while self.at("||"):
                self.advance()
                args.append(self._not())
            return A.NaryBool(line, "||", tuple(args))
        return left

    def _not(self) -> A.Expr:
        if self.at("!"):
            line = self.peek().line
            self.advance()
            return A.Unary(line, "!", self._not())
        return self._rel()

    _REL_OPS = ("==", "!=", "<=", ">=", "<", ">", "in", "!in")

    def _rel(self) -> A.Expr:
        first = self._add()
        ops = []
        operands = [first]
        while self.peek().text in self._REL_OPS:
            op = self.advance().text
            ops.append(op)
            operands.append(self._add())
        if not ops:
            return first
        return A.Chain(first.line, tuple(ops), tuple(operands))

    def _add(self) -> A.Expr:
        left = self._mul()
        while self.peek().text in ("+", "-"):
            line = self.peek().line
            op = self.advance().text
            right = self._mul()
            left = A.Binary(line, op, left, right)
        return left

    def _mul(self) -> A.Expr:
        left = self._unary()
        while self.peek().text in ("*", "/", "%"):
            line = self.peek().line
            op = self.advance().text
            right = self._unary()
            left = A.Binary(line, op, left, right)
        return left

    def _unary(self) -> A.Expr:
        if self.at("-"):
            line = self.peek().line
            self.advance()
            return A.Unary(line, "-", self._unary())
        return self._postfix()

    def _postfix(self) -> A.Expr:
        e = self._primary()
        while True:
            if self.at("."):
                line = self.peek().line
                self.advance()
                name = self.ident().text
                e = A.Member(line, e, name)
            elif self.at("("):
                line = self.peek().line
                self.advance()
                args = [] if self.at(")") else self.parse_expr_list()
                self.expect(")")
                e = A.Call(line, e, tuple(args))
            elif self.at("["):
                line = self.peek().line
                self.advance()
                if self.at(".."):
                    self.advance()
                    hi = None if self.at("]") else self.expr()
                    self.expect("]")
                    e = A.Slice(line, e, None, hi)
                else:
                    first = self.expr()
                    if self.at(".."):
                        self.advance()
                        hi = None if self.at("]") else self.expr()
                        self.expect("]")
                        e = A.Slice(line, e, first, hi)
                    elif self.at(":="):
                        self.advance()
                        val = self.expr()
                        self.expect("]")
                        e = A.SeqUpdate(line, e, first, val)
                    else:
                        self.expect("]")
                        e = A.Index(line, e, first)
            elif self.at("as"):
                line = self.peek().line
                self.advance()
                ty = self.parse_type()
                e = A.Cast(line, e, ty)
            elif self.at("is"):
                line = self.peek().line
                self.advance()
                ty = self.parse_type()
                e = A.TypeTest(line, e, ty)
            else:
                break
        return e

    def _primary(self) -> A.Expr:
        t = self.peek()
        line = t.line
        if t.kind == "int":
            self.advance()
            return A.IntLit(line, int(t.text))
        if t.kind == "real":
            self.advance()
            return A.RealLit(line, t.text)
        if t.kind == "char":
            self.advance()
            return A.CharLit(line, t.text)
        if t.kind == "string":
            self.advance()
            return A.StringLit(line, t.text)
        if t.text == "true":
            self.advance()
            return A.BoolLit(line, True)
        if t.text == "false":
            self.advance()
            return A.BoolLit(line, False)
        if t.text == "old":
            self.advance()
            self.expect("(")
            a = self.expr()
            self.expect(")")
            return A.Old(line, a)
        if t.text == "fresh":
            self.advance()
            self.expect("(")
            a = self.expr()
            self.expect(")")
            return A.Fresh(line, a)
        if t.text == "unchanged":
            self.advance()
            self.expect("(")
            args = [] if self.at(")") else self.parse_expr_list()
            self.expect(")")
            inner = args[0] if len(args) == 1 else A.TupleExpr(line, tuple(args)) if args else A.BoolLit(line, True)
            return A.Fresh(line, inner)
        if t.text == "|":
            self.advance()
            a = self.expr()
            self.expect("|")
            return A.Cardinality(line, a)
        if t.text == "(":
            self.advance()
            if self.at(")"):
                self.advance()
                return A.TupleExpr(line, ())
            items = [self.expr()]
            while self.at(","):
                self.advance()
                items.append(self.expr())
            self.expect(")")
            if len(items) == 1:
                return items[0]
            return A.TupleExpr(line, tuple(items))
        if t.text == "[":
            self.advance()
            items = [] if self.at("]") else self.parse_expr_list()
            self.expect("]")
            return A.SeqDisplay(line, tuple(items))
        if t.text == "{":
            self.advance()
            if self.at("}"):
                self.advance()
                return A.SetDisplay(line, ())
            first = self.expr()
            if self.at(":="):
                self.advance()
                v = self.expr()
                pairs = [(first, v)]
                while self.at(","):
                    self.advance()
                    k2 = self.expr()
                    self.expect(":=")
                    v2 = self.expr()
                    pairs.append((k2, v2))
                self.expect("}")
                return A.MapDisplay(line, tuple(pairs))
            items = [first]
            while self.at(","):
                self.advance()
                items.append(self.expr())
            self.expect("}")
            return A.SetDisplay(line, tuple(items))
        if t.text in ("forall", "exists"):
            kind = t.text
            self.advance()
            binders = self.parse_binders()
            attrs = self.parse_attrs()
            rng = None
            if self.at("|"):
                self.advance()
                rng = self.expr()
            self.expect("::")
            body = self.expr()
            return A.Quantifier(line, kind, binders, attrs, rng, body)
        if t.text in ("set", "map") and self.peek(1).kind == "id":
            kind = t.text
            self.advance()
            binders = self.parse_binders()
            rng = None
            if self.at("|"):
                self.advance()
                rng = self.expr()
            self.expect("::")
            body = self.expr()
            value = None
            if kind == "map" and self.at(":="):
                self.advance()
                value = self.expr()
            return A.Comprehension(line, kind, binders, rng, body, value)
        if t.text == "if":
            self.advance()
            cond = self.expr()
            self.expect("then")
            then = self.expr()
            self.expect("else")
            els = self.expr()
            return A.IfExpr(line, cond, then, els)
        if t.kind == "id":
            self.advance()
            return A.Ident(line, t.text)
        raise _ShimParseError(t.text or "<eof>", t.line)

    # -- Lhs / statements ---------------------------------------------------
    def _lhs_from(self, name: str, line: int) -> A.Lhs:
        base = A.Ident(line, name)
        steps = []
        while self.at("[") or self.at("."):
            if self.at("["):
                self.advance()
                idx = self.expr()
                self.expect("]")
                steps.append(("index", idx))
            else:
                self.advance()
                fname = self.ident().text
                steps.append(("field", fname))
        if not steps:
            return A.Lhs(line, kind="name", name=name)
        cur = base
        for kind, val in steps[:-1]:
            cur = A.Index(line, cur, val) if kind == "index" else A.Member(line, cur, val)
        lk, lv = steps[-1]
        if lk == "index":
            return A.Lhs(line, kind="index", base=cur, index=lv)
        return A.Lhs(line, kind="field", base=cur, field=lv)

    def parse_rhs(self):
        if self.at("*"):
            line = self.peek().line
            self.advance()
            return A.Star(line)
        if self.at("new"):
            line = self.peek().line
            self.advance()
            depth = 0
            parts = []
            while True:
                t = self.peek()
                if depth == 0 and t.text in (",", ";"):
                    break
                if t.text in "([{":
                    depth += 1
                elif t.text in ")]}":
                    depth -= 1
                parts.append(t.text)
                self.advance()
            return A.NewRhs(line, " ".join(parts))
        return self.expr()

    def parse_rhs_list(self) -> list:
        out = [self.parse_rhs()]
        while self.at(","):
            self.advance()
            out.append(self.parse_rhs())
        return out

    def parse_loop_specs(self) -> list:
        specs = []
        while self.peek().text in ("invariant", "decreases", "modifies"):
            kw = self.advance().text
            line = self.toks[self.i - 1].line
            if kw == "invariant":
                specs.append(A.InvariantClause(line, self.expr()))
            elif kw == "decreases":
                specs.append(A.DecreasesClause(line, self.parse_expr_list_or_star()))
            else:
                specs.append(A.ModifiesClause(line, self.parse_expr_list_or_star()))
        return specs

    def parse_block(self) -> tuple:
        self.expect("{")
        out = []
        while not self.at("}"):
            out.append(self.parse_stmt())
        self.expect("}")
        return tuple(out)

    def _skip_balanced_to_end(self) -> str:
        depth = 0
        parts = []
        while True:
            t = self.peek()
            if t.kind == "eof":
                break
            if t.text in "([{":
                depth += 1
            elif t.text in ")]}":
                depth -= 1
            parts.append(t.text)
            self.advance()
            if depth == 0 and (t.text == ";" or t.text == "}"):
                break
        return " ".join(parts)

    def parse_stmt(self) -> A.Stmt:
        t = self.peek()
        line = t.line
        if t.text == "ghost" and self.peek(1).text == "var":
            self.advance()
            return self._var_decl(ghost=True)
        if t.text == "var":
            return self._var_decl(ghost=False)
        if t.text == "if":
            self.advance()
            if self.at("{"):
                cases = self._case_list()
                return A.IfCaseStmt(line, cases)
            cond = A.Star(line) if self.at("*") else self.expr()
            if isinstance(cond, A.Star):
                self.advance()
            then = self.parse_block()
            else_ = None
            if self.at("else"):
                self.advance()
                if self.at("if"):
                    else_ = self.parse_stmt()
                else:
                    else_ = self.parse_block()
            return A.IfStmt(line, cond, then, else_)
        if t.text == "while":
            self.advance()
            if self.at("{"):
                cases = self._case_list()
                return A.WhileCaseStmt(line, (), cases)
            cond = A.Star(line) if self.at("*") else self.expr()
            if isinstance(cond, A.Star):
                self.advance()
            specs = self.parse_loop_specs()
            if self.at("{") and self._peek_is_case():
                cases = self._case_list()
                return A.WhileCaseStmt(line, tuple(specs), cases)
            body = self.parse_block()
            return A.WhileStmt(line, cond, tuple(specs), body)
        if t.text == "for":
            self.advance()
            var = self.ident().text
            var_type = None
            if self.at(":"):
                self.advance()
                var_type = self.parse_type()
            self.expect(":=")
            lo = self.expr()
            direction = self.advance().text  # "to" | "downto"
            hi = self.expr()
            specs = self.parse_loop_specs()
            body = self.parse_block()
            return A.ForStmt(line, var, var_type, lo, direction, hi, tuple(specs), body)
        if t.text == "return":
            self.advance()
            if self.at(";"):
                self.advance()
                return A.ReturnStmt(line, ())
            vals = self.parse_expr_list()
            self.expect(";")
            return A.ReturnStmt(line, tuple(vals))
        if t.text == "break":
            self.advance()
            label = None
            if self.at_kind("id"):
                label = self.advance().text
            self.expect(";")
            return A.BreakStmt(line, label)
        if t.text == "continue":
            self.advance()
            label = None
            if self.at_kind("id"):
                label = self.advance().text
            self.expect(";")
            return A.ContinueStmt(line, label)
        if t.text == "assert":
            self.advance()
            attrs = self.parse_attrs()
            cond = self.expr()
            if self.at("by"):
                self.advance()
                proof = self.parse_block()
                return A.AssertByStmt(line, cond, proof)
            self.expect(";")
            return A.AssertStmt(line, cond, attrs)
        if t.text == "assume":
            self.advance()
            self.parse_attrs()
            cond = self.expr()
            self.expect(";")
            return A.AssumeStmt(line, cond)
        if t.text == "calc":
            self.advance()
            text = self._skip_balanced_to_end()
            return A.CalcStmt(line, text)
        if t.text == "forall":
            self.advance()
            binders = self.parse_binders()
            attrs = self.parse_attrs()
            rng = None
            if self.at("|"):
                self.advance()
                rng = self.expr()
            body = self.parse_block()
            return A.ForallStmt(line, binders, attrs, rng, body)
        if t.text == "print":
            self.advance()
            args = self.parse_expr_list_or_star()
            self.expect(";")
            return A.PrintStmt(line, args)
        if t.text == "expect":
            self.advance()
            cond = self.expr()
            while self.at(","):
                self.advance()
                self.expr()
            self.expect(";")
            return A.ExpectStmt(line, cond)
        if t.text == "reveal":
            self.advance()
            text = self._skip_balanced_to_end()
            return A.RevealStmt(line, text)
        if t.text == "label":
            self.advance()
            label = self.ident().text
            self.expect(":")
            inner = self.parse_stmt()
            return A.LabelStmt(line, label, inner)
        if t.text == "{":
            body = self.parse_block()
            return A.BlockStmt(line, body)
        # default: Lhs list (assign / call-stmt / such-that)
        name = self.ident().text
        if self.at("("):
            self.advance()
            args = [] if self.at(")") else self.parse_expr_list()
            self.expect(")")
            self.expect(";")
            return A.CallStmt(line, name, tuple(args))
        targets = [self._lhs_from(name, line)]
        while self.at(","):
            self.advance()
            n2 = self.ident().text
            targets.append(self._lhs_from(n2, line))
        if self.at(":|"):
            self.advance()
            cond = self.expr()
            self.expect(";")
            params = tuple(A.Param(line, t2.name, None, False) for t2 in targets)
            return A.AssignSuchThat(line, params, cond)
        self.expect(":=")
        values = self.parse_rhs_list()
        self.expect(";")
        return A.Assign(line, tuple(targets), tuple(values))

    def _peek_is_case(self) -> bool:
        return self.peek(1).text == "case"

    def _case_list(self):
        self.expect("{")
        cases = []
        while self.at("case"):
            self.advance()
            cond = self.expr()
            self.expect("=>")
            stmts = []
            while not (self.at("case") or self.at("}")):
                stmts.append(self.parse_stmt())
            cases.append((cond, tuple(stmts)))
        self.expect("}")
        return tuple(cases)

    def _var_decl(self, ghost: bool) -> A.Stmt:
        line = self.peek().line
        self.expect("var")
        names = [self._one_param()]
        while self.at(","):
            self.advance()
            names.append(self._one_param())
        if self.at(":|"):
            self.advance()
            cond = self.expr()
            self.expect(";")
            return A.AssignSuchThat(line, tuple(names), cond)
        if self.at(":="):
            self.advance()
            vals = self.parse_rhs_list()
            self.expect(";")
            return A.VarDeclStmt(line, ghost, tuple(names), tuple(vals))
        self.expect(";")
        return A.VarDeclStmt(line, ghost, tuple(names), None)

    # -- top level --------------------------------------------------------
    def _decl_attrs_and_name(self):
        self.parse_attrs()
        return self.ident().text

    def parse_function_decl(self) -> A.FunctionDecl:
        line = self.peek().line
        ghost = False
        if self.at("ghost"):
            self.advance()
            ghost = True
        kw = self.advance().text  # function | predicate
        is_pred = kw == "predicate"
        self.parse_attrs()
        name = self.ident().text
        type_params = ()
        if self.at("<"):
            type_params = self._skip_type_params()
        params = self.parse_params()
        ret_type = None
        if self.at(":"):
            self.advance()
            ret_type = self.parse_type()
        specs = []
        while self.peek().text in ("requires", "ensures", "reads", "decreases"):
            kw2 = self.advance().text
            l2 = self.toks[self.i - 1].line
            if kw2 == "requires":
                specs.append(A.RequiresClause(l2, self.expr()))
            elif kw2 == "ensures":
                specs.append(A.EnsuresClause(l2, self.expr()))
            elif kw2 == "reads":
                specs.append(A.ReadsClause(l2, self.parse_expr_list_or_star()))
            else:
                specs.append(A.DecreasesClause(l2, self.parse_expr_list_or_star()))
        body = None
        if self.at("{"):
            self.advance()
            body = self.expr()
            self.expect("}")
        d = A.FunctionDecl(line, ghost=ghost, is_predicate=is_pred, type_params=type_params,
                            params=tuple(params), ret_type=ret_type, specs=tuple(specs),
                            body=body, attrs=())
        d.name = name
        return d

    def _skip_type_params(self):
        self.expect("<")
        out = [self.ident().text]
        while self.at(","):
            self.advance()
            out.append(self.ident().text)
        self.expect(">")
        return tuple(out)

    def parse_method_decl(self) -> A.MethodDecl:
        line = self.peek().line
        self.expect("method")
        self.parse_attrs()
        name = self.ident().text
        type_params = ()
        if self.at("<"):
            type_params = self._skip_type_params()
        params = self.parse_params()
        returns = ()
        if self.at("returns"):
            self.advance()
            returns = tuple(self.parse_params())
        specs = []
        while self.peek().text in ("requires", "ensures", "modifies", "decreases"):
            kw2 = self.advance().text
            l2 = self.toks[self.i - 1].line
            if kw2 == "requires":
                specs.append(A.RequiresClause(l2, self.expr()))
            elif kw2 == "ensures":
                specs.append(A.EnsuresClause(l2, self.expr()))
            elif kw2 == "modifies":
                specs.append(A.ModifiesClause(l2, self.parse_expr_list_or_star()))
            else:
                specs.append(A.DecreasesClause(l2, self.parse_expr_list_or_star()))
        body = None
        if self.at("{"):
            body = self.parse_block()
        d = A.MethodDecl(line, type_params=type_params, params=tuple(params),
                          returns=returns, specs=tuple(specs), body=body, attrs=())
        d.name = name
        return d

    def parse_lemma_decl(self) -> A.LemmaDecl:
        line = self.peek().line
        kw_parts = []
        while self.peek().text in ("least", "greatest", "twostate", "lemma"):
            kw_parts.append(self.advance().text)
        self.parse_attrs()
        name = None
        if self.at_kind("id"):
            name = self.advance().text
        text = self._skip_balanced_to_end()
        d = A.LemmaDecl(line, keyword=" ".join(kw_parts), text=text)
        d.name = name
        return d

    _SKIP_GAP = {
        "datatype": "datatype", "codatatype": "datatype",
        "class": "heap", "trait": "heap",
        "type": "type-decl", "newtype": "type-decl",
        "const": "type-decl", "iterator": "iterator",
        "module": "module", "import": "module", "export": "module",
    }

    def parse_skipped_decl(self) -> A.SkippedDecl:
        line = self.peek().line
        kw = self.advance().text
        gap = self._SKIP_GAP.get(kw, "type-decl")
        name = None
        if self.at_kind("id"):
            name = self.advance().text
        self._skip_balanced_to_end()
        d = A.SkippedDecl(line, keyword=kw, gap_name=gap)
        d.name = name
        return d

    def parse_module(self, source_path: str | None) -> A.Module:
        decls = []
        while not self.at_kind("eof"):
            t = self.peek()
            if t.text == "ghost" and self.peek(1).text in ("function", "predicate"):
                decls.append(self.parse_function_decl())
            elif t.text in ("function", "predicate"):
                decls.append(self.parse_function_decl())
            elif t.text == "method":
                decls.append(self.parse_method_decl())
            elif t.text in ("lemma", "least", "greatest", "twostate"):
                decls.append(self.parse_lemma_decl())
            elif t.text in self._SKIP_GAP:
                decls.append(self.parse_skipped_decl())
            else:
                raise _ShimParseError(t.text or "<eof>", t.line)
        return A.Module(tuple(decls), (), source_path)


def shim_parse(text: str, source_path: str | None = None) -> A.Module:
    toks = _lex(text)
    p = _P(toks)
    return p.parse_module(source_path)


def shim_gradable_methods(module: A.Module) -> list[A.MethodDecl]:
    return [d for d in module.decls
            if isinstance(d, A.MethodDecl) and d.name != "Main"
            and any(isinstance(s, A.EnsuresClause) for s in d.specs)]


# ===========================================================================
# Part 2: acceptance (a) -- every seed in test_lifter.SEEDS.
# ===========================================================================

def _load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _points_by_position(task: dict) -> dict:
    ref = interp.Reference(task)
    names = [p["name"] for p in task["params"]]
    return {tuple(env[n] for n in names): v for env, v in ref.points}


def run_seed_acceptance() -> list[tuple[str, str]]:
    """Acceptance (a): parse each seed's banked rprint (shim parser, front
    not ready), classify + rewrite, assert `check_wf(task) == []`, then
    compare the lifted task to the hand lift by `interp.Reference` on the
    shared domain (params matched by POSITION, since a hand lifter was
    free to rename -- see test_lifter.SEEDS' own docstring). Returns one
    (seed_name, verdict) pair per seed; verdict is "agree", "differ:...",
    or a failure tag. Never raises: a per-seed exception is caught and
    reported as its own verdict, since one bad seed must not hide the
    other 20's results."""
    import test_lifter as TL

    out: list[tuple[str, str]] = []
    for seed_json, corpus_path, method in TL.SEEDS:
        try:
            rp = CORPUS_RPRINT / (corpus_path.name + ".rprint.dfy")
            text = rp.read_text(encoding="utf-8", errors="replace")
            mod = shim_parse(text, corpus_path.name)
            methods = {m.name: m for m in shim_gradable_methods(mod)}
            if method not in methods:
                out.append((seed_json.name, "shim-could-not-find-method"))
                continue
            v = C.classify(mod, methods[method])
            if not isinstance(v, C.Liftable):
                out.append((seed_json.name, f"refused:{v.reason}@{v.line}"))
                continue
            rr = R.rewrite(mod, v, corpus_path.name, "sha256-not-computed-by-shim")
            errs = fuzz_lower.check_wf(rr.task)
            assert errs == [], f"check_wf({seed_json.name}) = {errs}"
            hand = _load_json(seed_json)
            mine_pts = _points_by_position(rr.task)
            hand_pts = _points_by_position(hand)
            shared = set(mine_pts) & set(hand_pts)
            diffs = [k for k in shared if mine_pts[k] != hand_pts[k]]
            if not shared:
                out.append((seed_json.name,
                            f"no-shared-domain (mine={len(mine_pts)} hand={len(hand_pts)})"))
            elif diffs:
                k = diffs[0]
                out.append((seed_json.name,
                            f"differ on {len(diffs)}/{len(shared)}: {k} -> "
                            f"mine={mine_pts[k]} hand={hand_pts[k]}"))
            else:
                out.append((seed_json.name, f"agree ({len(shared)} shared points)"))
        except AssertionError as e:
            out.append((seed_json.name, f"FAIL:{e}"))
        except Exception as e:
            out.append((seed_json.name, f"EXC:{type(e).__name__}:{e}"))
    return out


def test_seed_acceptance() -> None:
    results = run_seed_acceptance()
    for name, verdict in results:
        print(f"  {name:30s} {verdict}")
    bad = [r for r in results if not (r[1].startswith("agree") or r[1].startswith("differ"))]
    assert not bad, f"seeds that neither agreed nor cleanly differed: {bad}"
    n_agree = sum(1 for _, v in results if v.startswith("agree"))
    n_differ = len(results) - n_agree
    tail = (" (0 differ)" if n_differ == 0 else
            f" ({n_differ} differ for a reported reason each -- see the per-seed lines "
            f"above; a hand lift under a different default is a difference to report, "
            f"not a bug to hide, per this module's own instructions)")
    print(f"test_seed_acceptance: {n_agree}/{len(results)} seeds agree with their hand lift{tail}")


# ===========================================================================
# Part 3: acceptance (b) -- all 77 of infragment.txt.
# ===========================================================================

def run_infragment() -> dict:
    """Acceptance (b): every file in infragment.txt (banked rprint),
    classified and rewritten. Returns a summary dict: lifted count,
    refusals-by-reason (each with file:method@line), check_wf failures
    (should be none -- a real bug if not), and rewrite-rule counts."""
    names = [l.rstrip("\n") for l in INFRAGMENT.read_text(encoding="utf-8").splitlines() if l.strip()]
    lifted = 0
    refused: dict[str, list[str]] = {}
    check_wf_failures: list[str] = []
    crashed: list[str] = []
    rewrite_counts: dict[str, int] = {}
    for name in names:
        rp = CORPUS_RPRINT / (name + ".rprint.dfy")
        try:
            text = rp.read_text(encoding="utf-8", errors="replace")
            mod = shim_parse(text, name)
            methods = shim_gradable_methods(mod)
            if not methods:
                refused.setdefault("no-gradable-method(shim)", []).append(name)
                continue
            for m in methods:
                v = C.classify(mod, m)
                if isinstance(v, C.Liftable):
                    rr = R.rewrite(mod, v, name, "sha256-not-computed-by-shim")
                    errs = fuzz_lower.check_wf(rr.task)
                    if errs:
                        check_wf_failures.append(f"{name}:{m.name} -> {errs}")
                    else:
                        lifted += 1
                        for r in rr.record.rewrites:
                            rewrite_counts[r.rule] = rewrite_counts.get(r.rule, 0) + 1
                else:
                    refused.setdefault(v.reason, []).append(f"{name}:{m.name}@{v.line}")
        except Exception as e:
            crashed.append(f"{name}: {type(e).__name__}: {e}")
    return {"total_files": len(names), "lifted": lifted, "refused": refused,
            "check_wf_failures": check_wf_failures, "crashed": crashed,
            "rewrite_counts": rewrite_counts}


def test_infragment() -> None:
    summary = run_infragment()
    print(f"  {summary['lifted']} lifted / {summary['total_files']} files")
    for reason, items in sorted(summary["refused"].items(), key=lambda kv: -len(kv[1])):
        print(f"  refused {reason}: {len(items)} -- {items[:5]}")
    print(f"  rewrite counts: {summary['rewrite_counts']}")
    if summary["crashed"]:
        print(f"  CRASHED: {summary['crashed']}")
    if summary["check_wf_failures"]:
        print(f"  check_wf FAILURES: {summary['check_wf_failures']}")
    assert not summary["crashed"], f"{len(summary['crashed'])} file(s) crashed the shim/lifter"
    assert not summary["check_wf_failures"], (
        f"{len(summary['check_wf_failures'])} lifted task(s) failed check_wf")
    print(f"test_infragment: {summary['lifted']}/{summary['total_files']} lifted, "
          f"check_wf == [] on every one, 0 crashes")


# ===========================================================================
# Part 4: acceptance (c) -- one unit test per rewrite row, on a small
# synthetic snippet parsed the same way (shim_parse) as everything else in
# this file. Each snippet is written directly (not extracted from the
# corpus), so its shape is deliberately minimal and exercises exactly the
# one rule under test.
# ===========================================================================

def _lift_one(src: str, method_name: str, source_path: str = "unit.dfy"):
    """Parse `src`, classify+rewrite `method_name`. Returns (task, record)
    on success; raises AssertionError with the Refusal if classify refused
    (every caller in this section expects to lift, except the two refusal
    checks, which call `_classify_one` directly instead)."""
    mod = shim_parse(src, source_path)
    methods = {m.name: m for m in shim_gradable_methods(mod)}
    assert method_name in methods, f"{method_name} not found/gradable in shim parse"
    v = C.classify(mod, methods[method_name])
    assert isinstance(v, C.Liftable), f"expected liftable, got refusal: {v}"
    rr = R.rewrite(mod, v, source_path, "sha")
    errs = fuzz_lower.check_wf(rr.task)
    assert errs == [], f"check_wf: {errs}\ntask={json.dumps(rr.task, indent=1)}"
    return rr.task, rr.record


def _classify_one(src: str, method_name: str, source_path: str = "unit.dfy"):
    mod = shim_parse(src, source_path)
    methods = {m.name: m for m in shim_gradable_methods(mod)}
    assert method_name in methods, f"{method_name} not found/gradable in shim parse"
    return C.classify(mod, methods[method_name])


def _rule_names(record) -> set:
    return {r.rule for r in record.rewrites}


def test_chain_desugared() -> None:
    src = """
method Chained(x: int, y: int, z: int) returns (r: bool)
  ensures r == (x <= y && y <= z)
{
  r := x <= y <= z;
}
"""
    task, rec = _lift_one(src, "Chained")
    assert "chain-desugared" in _rule_names(rec)
    body_rhs = task["body"][0]["assign"][1]
    assert body_rhs == {"op": "and", "args": [
        {"op": "<=", "args": [{"var": "x"}, {"var": "y"}]},
        {"op": "<=", "args": [{"var": "y"}, {"var": "z"}]}]}
    print("test_chain_desugared: 'x <= y <= z' -> and(x<=y, y<=z), rule logged")


def test_iff_to_eq() -> None:
    src = """
method Iffy(a: bool, b: bool) returns (r: bool)
  ensures r <==> (a && b)
{
  r := a <==> b;
}
"""
    task, rec = _lift_one(src, "Iffy")
    assert "iff-to-eq" in _rule_names(rec)
    ens = task["ensures"][0]
    assert ens["op"] == "==" and ens["args"][0] == {"var": "r"}
    print("test_iff_to_eq: '<==>' -> '==' on two bools, rule logged")


def test_nat_return_ensures() -> None:
    src = """
method NatRet(x: int) returns (r: nat)
  ensures r == x + 1
{
  r := x + 1;
}
"""
    task, rec = _lift_one(src, "NatRet")
    assert "nat-return-ensures" in _rule_names(rec)
    assert task["ensures"][0] == {"op": ">=", "args": [{"var": "r"}, {"int": 0}]}
    assert task["returns"][0]["type"] == "int"
    print("test_nat_return_ensures: 'returns (r: nat)' -> ensures r>=0 FIRST, r: int")


def test_nat_invariant_added_and_dedup() -> None:
    added_src = """
method NatLoop(n: nat) returns (r: nat)
  ensures r >= 0
  decreases n
{
  r := 0;
  var i: int := 0;
  while i < n
    invariant i <= n
    decreases n - i
  {
    r := r + 1;
    i := i + 1;
  }
}
"""
    task, rec = _lift_one(added_src, "NatLoop")
    assert "nat-invariant-added" in _rule_names(rec)
    invs = task["body"][2]["while"]["invariants"]
    ge0_r = {"op": ">=", "args": [{"var": "r"}, {"int": 0}]}
    assert invs[-1] == ge0_r, f"expected r>=0 appended LAST, got {invs}"
    assert invs[0] == {"op": "<=", "args": [{"var": "i"}, {"var": "n"}]}, \
        "author's own invariant must stay first"

    dedup_src = """
method NatLoopDedup(n: nat) returns (r: nat)
  ensures r >= 0
  decreases n
{
  r := 0;
  var i: int := 0;
  while i < n
    invariant r >= 0
    invariant i <= n
    decreases n - i
  {
    r := r + 1;
    i := i + 1;
  }
}
"""
    task2, rec2 = _lift_one(dedup_src, "NatLoopDedup")
    invs2 = task2["body"][2]["while"]["invariants"]
    count = sum(1 for x in invs2 if x == ge0_r)
    assert count == 1, f"nat-invariant-added must not duplicate an already-present clause, got {invs2}"
    print("test_nat_invariant_added_and_dedup: appended after author's invariants; "
          "not duplicated when already present")


def test_spec_fun_totalised() -> None:
    src = """
function Half(n: nat): int
  requires n >= 0
  decreases n
{
  if n == 0 then 0 else 1 + Half(n - 2)
}

method UseHalf(n: nat) returns (r: int)
  ensures r == Half(n)
{
  r := Half(n);
}
"""
    task, rec = _lift_one(src, "UseHalf")
    assert "spec-fun-totalised" in _rule_names(rec)
    fn = task["spec_funs"][0]
    assert "ite" in fn["body"], f"expected a totalising ite wrapper, got {fn['body']}"
    assert fn["body"]["ite"]["else"] == {"int": 0}
    print("test_spec_fun_totalised: nat-param + requires guard -> ite(D, body, 0)")


def test_tail_return() -> None:
    src = """
method TailRet(x: int) returns (r: int)
  ensures r == x + 1
{
  if x >= 0 {
    return x + 1;
  } else {
    r := x + 1;
  }
}
"""
    task, rec = _lift_one(src, "TailRet")
    assert "tail-return" in _rule_names(rec)
    then_branch = task["body"][0]["if"]["then"]
    assert then_branch == [{"assign": ["r", {"op": "+", "args": [{"var": "x"}, {"int": 1}]}]}]
    print("test_tail_return: tail 'return e;' -> 'r := e', definite assignment intact")


def test_parallel_assign_temps() -> None:
    src = """
method Swap(a: int, b: int) returns (r: int)
  ensures r == a + b
{
  var x: int := a;
  var y: int := b;
  x, y := y, x;
  r := x + y;
}
"""
    task, rec = _lift_one(src, "Swap")
    assert "parallel-assign-temps" in _rule_names(rec)
    # semantic check, not just syntactic: x/y really swap (not aliased).
    pts = list(interp.domain(task, [(p["name"], p["type"]) for p in task["params"]], limit=20))
    ref = interp.Reference(task)
    assert ref.points, "parallel-assign lift produced no reachable point"
    for env0, v in ref.points[:5]:
        assert v == env0["a"] + env0["b"]
    print("test_parallel_assign_temps: 'x,y := y,x' via fresh temps, semantics verified by interp")


def test_default_init() -> None:
    src = """
method DefaultInit(n: int) returns (r: int)
  ensures r == n
{
  var x: int;
  x := n;
  r := x;
}
"""
    task, rec = _lift_one(src, "DefaultInit")
    assert "default-init" in _rule_names(rec)
    first = task["body"][0]
    assert first["var"]["init"] == {"int": 0}
    ref = interp.Reference(task)
    for env0, v in ref.points[:5]:
        assert v == env0["n"]
    print("test_default_init: 'var x: int;' -> 'var x: int := 0;', semantics verified by interp")


def test_split_conjuncts_ensures_not_invariants() -> None:
    src = """
method SplitTest(x: int) returns (r: int)
  ensures r >= 0 && r <= x + 1
  decreases x
{
  r := 0;
  var i: int := 0;
  while i < x
    invariant r >= 0 && i <= x
    decreases x - i
  {
    i := i + 1;
    r := r + 1;
  }
}
"""
    task, rec = _lift_one(src, "SplitTest")
    assert "split-conjuncts" in _rule_names(rec)
    assert len(task["ensures"]) == 2, f"ensures must split into 2 clauses, got {task['ensures']}"
    invs = task["body"][2]["while"]["invariants"]
    assert invs[0] == {"op": "and", "args": [
        {"op": ">=", "args": [{"var": "r"}, {"int": 0}]},
        {"op": "<=", "args": [{"var": "i"}, {"var": "x"}]}]}, \
        f"invariant must NOT split (decision 10), got {invs}"
    print("test_split_conjuncts_ensures_not_invariants: ensures splits to 2 clauses, "
          "invariant stays one 'and' node")


def test_in_desugared_fresh_binder() -> None:
    src = """
method InTest(x: int, s: seq<int>) returns (r: bool)
  ensures r == (x in s)
{
  r := x in s;
}
"""
    task, rec = _lift_one(src, "InTest")
    rules = [r.rule for r in rec.rewrites]
    assert rules.count("in-desugared") >= 2, f"expected 2+ in-desugared (ensures + body), got {rules}"
    body_rhs = task["body"][0]["assign"][1]
    assert "exists" in body_rhs
    binder = body_rhs["exists"]["var"]
    ens_rhs = task["ensures"][0]["args"][1]
    binder2 = ens_rhs["exists"]["var"]
    assert binder != binder2, f"the two desugarings must use distinct fresh binders, got {binder!r} twice"
    print(f"test_in_desugared_fresh_binder: 'x in s' -> bounded exists over [0,len(s)), "
          f"fresh binders {binder!r}/{binder2!r}")


def test_array_readonly_as_seq_and_mutation_refusal() -> None:
    ok_src = """
method ArrRO(a: array<int>, n: int) returns (r: int)
  requires n == a.Length
  ensures r == n
{
  r := a.Length;
}
"""
    task, rec = _lift_one(ok_src, "ArrRO")
    assert "array-readonly-as-seq" in _rule_names(rec)
    assert task["params"][0]["type"] == "seq"
    assert task["body"][0]["assign"][1] == {"op": "len", "args": [{"var": "a"}]}

    bad_src = """
method ArrWrite(a: array<int>, i: int, v: int) returns (r: int)
  requires 0 <= i && i < a.Length
  ensures r == v
{
  a[i] := v;
  r := v;
}
"""
    v = _classify_one(bad_src, "ArrWrite")
    assert isinstance(v, C.Refusal) and v.reason == "array-mutation", f"expected array-mutation refusal, got {v}"
    print("test_array_readonly_as_seq_and_mutation_refusal: read-only array<int> -> seq + len/at; "
          "a write refuses array-mutation")


def test_decreases_tuple_projection_and_guess_sum() -> None:
    proj_src = """
function Proj(x: int, y: int): int
  decreases x, y
{
  if x == 0 then y else Proj(x - 1, y)
}

method UseProj(x: int, y: int) returns (r: int)
  requires x >= 0
  ensures r == Proj(x, y)
{
  r := Proj(x, y);
}
"""
    task, rec = _lift_one(proj_src, "UseProj")
    assert "decreases-tuple-reduced" in _rule_names(rec)
    assert rec.decreases_origin.get("Proj") == "projected"
    # `Proj`'s own params get their own t-names from the SAME global
    # renamer as the method's (`UseProj` also has a param "x"), so the
    # first surviving param's *emitted* name is looked up rather than
    # assumed to still be "x" -- see _Renamer's docstring on why this
    # lift is deliberately conservative about cross-scope name reuse.
    fn_x_t = task["spec_funs"][0]["params"][0]["name"]
    assert task["spec_funs"][0]["decreases"] == {"var": fn_x_t}, task["spec_funs"][0]["decreases"]

    sum_src = """
function SumDec(x: int, y: int): int
  decreases x, y
{
  if x == 0 then y else if y == 0 then x else SumDec(x - 1, y - 1)
}

method UseSumDec(x: int, y: int) returns (r: int)
  requires x >= 0 && y >= 0
  ensures r == SumDec(x, y)
{
  r := SumDec(x, y);
}
"""
    task2, rec2 = _lift_one(sum_src, "UseSumDec")
    assert "guess:sum" in _rule_names(rec2)
    assert rec2.decreases_origin.get("SumDec") == "guess:sum"
    dec = task2["spec_funs"][0]["decreases"]
    fn2_x_t = task2["spec_funs"][0]["params"][0]["name"]
    fn2_y_t = task2["spec_funs"][0]["params"][1]["name"]
    assert dec == {"op": "+", "args": [{"var": fn2_x_t}, {"var": fn2_y_t}]}, dec
    print("test_decreases_tuple_projection_and_guess_sum: y-unchanged-every-call -> projected to x; "
          "neither-unchanged -> guess:sum(x,y)")


def test_set_refused_before_rewrite() -> None:
    """The 785 run found `SetDisplay` and a set `Comprehension` reaching
    lift_rewrite uncaught (dafny-synthesis task_id_455 / task_id_142);
    classify must refuse `set` for both, and for a set-typed local, before
    a rewrite is ever attempted."""
    display_src = """
method UseDisplay(x: int) returns (r: bool)
  ensures r == true
{
  var s := {1, 2, 3};
  r := x in s;
}
"""
    v = _classify_one(display_src, "UseDisplay")
    assert isinstance(v, C.Refusal) and v.reason == "set", f"expected set refusal, got {v}"

    compr_src = """
method UseCompr(n: int) returns (r: bool)
  ensures r == true
{
  var s := set x: int | 0 <= x < n :: x;
  r := true;
}
"""
    v2 = _classify_one(compr_src, "UseCompr")
    assert isinstance(v2, C.Refusal) and v2.reason == "set", f"expected set refusal, got {v2}"
    print("test_set_refused_before_rewrite: a set display and a set comprehension both "
          "refuse `set` at classify, never reaching rewrite")


def test_calls_other_method_in_assignment() -> None:
    """Section 4.5's `x := M(args);` row: a call of a DIFFERENT method,
    as a plain assignment's or a var-init's right-hand side, must refuse
    `calls-other-method` -- previously only a bare `M(args);` call
    STATEMENT was caught, so this shape (nitwit's `nit_flip` calling the
    method `max_nit`, VSI-Benchmarks' `Mul` calling `Add`) reached
    lift_rewrite and either crashed or emitted an unknown-fun call."""
    src = """
method Helper(x: int) returns (h: int)
  ensures h == x
{
  h := x;
}

method Caller(x: int) returns (r: int)
  ensures r == x
{
  var t := Helper(x);
  r := t;
}
"""
    v = _classify_one(src, "Caller")
    assert isinstance(v, C.Refusal) and v.reason == "calls-other-method", f"expected calls-other-method, got {v}"
    print("test_calls_other_method_in_assignment: `var t := Helper(x);` refuses "
          "calls-other-method (not just a bare call statement)")


def test_null_refuses_heap() -> None:
    """A bare `null` literal (the shim, like lift_parse.py, has no
    dedicated NullLit node -- it is a plain Ident named "null") is a heap
    fact t has no word for: an array param compared to null (minArray,
    FindMax) must refuse `heap`, not reach rewrite as an ordinary
    identifier."""
    src = """
method UsesNull(a: array<int>) returns (r: int)
  requires a != null && a.Length > 0
  ensures r == 0
{
  r := 0;
}
"""
    v = _classify_one(src, "UsesNull")
    assert isinstance(v, C.Refusal) and v.reason == "heap", f"expected heap refusal, got {v}"
    print("test_null_refuses_heap: `a != null` refuses heap")


def test_bodyless_method_refused() -> None:
    """A method with no body (`method q(...) returns (...) requires ..
    ensures ..` and no `{ }`, ex10_hoangkim's `q`) must refuse
    `bodyless-method` instead of reaching lift_rewrite's
    `_desugar_returns(None, ...)` and crashing with a TypeError."""
    src = """
method NoBody(x: nat) returns (z: nat)
  requires x > 2
  ensures z > x
"""
    v = _classify_one(src, "NoBody")
    assert isinstance(v, C.Refusal) and v.reason == "bodyless-method", f"expected bodyless-method, got {v}"
    print("test_bodyless_method_refused: a method with no body refuses bodyless-method")


def test_method_level_decreases_neither_projects_nor_sums() -> None:
    """Decision 11's tuple-decreases test, done at the method-level self-
    call site (`mystery1`/`mystery2`-shaped): when NEITHER stated
    component ever changes across every self-call (both params passed
    straight through unchanged, so `unchanged_at_every_call` drops both),
    the tuple neither projects nor sums and classify must refuse
    `lexicographic-decreases` -- previously this reached
    lift_rewrite._method_level_decreases and crashed with an IndexError
    on an empty `lifted` list (both Software-building-and-verification
    -Projects `mystery1` and `mystery2`)."""
    src = """
method Loopy(n: nat, m: nat) returns (res: nat)
  decreases n, m
  ensures n + m == res
{
  if n == 0 {
    res := m;
  } else {
    var aux := Loopy(n, m);
    res := 1 + aux;
  }
}
"""
    v = _classify_one(src, "Loopy")
    assert isinstance(v, C.Refusal) and v.reason == "lexicographic-decreases", (
        f"expected lexicographic-decreases, got {v}")
    print("test_method_level_decreases_neither_projects_nor_sums: neither param ever "
          "changes at the self-call -> lexicographic-decreases (not a rewrite crash)")


def test_predicate_result_is_bool() -> None:
    """`predicate` declares no `: T` at all (implicit `: bool`); a spec_fun
    built from one must get a `bool` result and a `False` totalisation
    default, not fall through to `int`/`0` for lack of an explicit
    ret_type -- the bug behind nitwit's max_nit/nit_flip check_wf failure
    ("ite branches differ: bool vs int; spec_fun ... body type != result")."""
    src = """
predicate IsBig(b: nat) {
  b >= 2
}

method UsesPred(b: nat) returns (r: bool)
  ensures r == IsBig(b)
{
  r := IsBig(b);
}
"""
    task, rec = _lift_one(src, "UsesPred")
    spec_fun = task["spec_funs"][0]
    assert spec_fun["result"] == "bool", f"expected bool result, got {spec_fun}"
    print("test_predicate_result_is_bool: a `predicate`'s spec_fun gets result \"bool\" "
          "(and check_wf, run via _lift_one, passes)")


def test_multi_method_one_task_each() -> None:
    src = """
method First(x: int) returns (r: int)
  ensures r == x
{
  r := x;
}

method Second(x: int) returns (r: int)
  ensures r == x + 1
{
  r := x + 1;
}
"""
    mod = shim_parse(src, "twomethods.dfy")
    methods = shim_gradable_methods(mod)
    assert len(methods) == 2, f"expected 2 gradable methods, got {len(methods)}"
    tasks = []
    for m in methods:
        v = C.classify(mod, m)
        assert isinstance(v, C.Liftable)
        rr = R.rewrite(mod, v, "twomethods.dfy", "sha")
        assert fuzz_lower.check_wf(rr.task) == []
        tasks.append(rr.task)
    names = {t["name"] for t in tasks}
    assert len(names) == 2, f"the two methods must yield two distinctly-named tasks, got {names}"
    print(f"test_multi_method_one_task_each: 2 gradable methods -> 2 tasks, names={sorted(names)}")


def test_seq_nat_param_refused() -> None:
    """Decision 14: `seq<nat>`'s element bound is part of the source's
    precondition exactly as a `nat` parameter's is (section 7); the
    lifter carries no per-element guard for a bare `seq`, so a `seq<nat>`
    parameter must refuse `nat-seq-elements` rather than lift to an
    unconstrained `seq` (probe_seqnat.dfy: `SumSeq(s: seq<nat>) returns
    (r: int) ensures r >= 0` was lifting to a task whose domain admits
    `s = [-1]`, a wider domain than the source verified over)."""
    src = """
method SumSeq(s: seq<nat>) returns (r: int)
  ensures r >= 0
{
  r := 0;
}
"""
    v = _classify_one(src, "SumSeq")
    assert isinstance(v, C.Refusal) and v.reason == "nat-seq-elements", (
        f"expected nat-seq-elements refusal, got {v}")
    # A plain seq<int> param must still lift (only the nat-elements case
    # is refused; seq<int> has no such bound to lose).
    src_int = src.replace("seq<nat>", "seq<int>")
    task, _rec = _lift_one(src_int, "SumSeq")
    assert task["params"][0]["type"] == "seq"
    print("test_seq_nat_param_refused: seq<nat> param refuses nat-seq-elements; "
         "seq<int> still lifts")


def test_quantifier_membership_binder_substitution() -> None:
    """Section 4.4's `forall k | k in s :: P` row must substitute `at(s,
    j)` for the bound element `k`, not the bare sequence `s` itself (the
    finding: `_lift_quantifier`'s `_AtHole` returned the seq expression
    directly, so every occurrence of `k` in the body became `s`, turning
    `k > 0` into the ill-typed `s > 0`). `_lift_one` already asserts
    `check_wf(rr.task) == []`, which the old bug failed (`> is int-only`);
    this also checks the printed body actually indexes `s` by the fresh
    binder."""
    src = """
method AllPos(s: seq<int>) returns (r: int)
  requires forall k | k in s :: k > 0
  ensures r >= 0
{
  r := 0;
}
"""
    task, rec = _lift_one(src, "AllPos")
    req = task["requires"][0]
    assert "forall" in req, f"expected a forall in requires, got {req}"
    body = req["forall"]["body"]
    # body is `at(s, j) > 0`, never the bare seq `s > 0`.
    assert body["op"] == ">", body
    lhs = body["args"][0]
    assert lhs.get("op") == "at", f"expected the binder indexed into s (`at`), got {lhs}"
    at_args = lhs["args"]
    assert at_args[0] == {"var": "s"}, at_args
    assert at_args[1] == {"var": req["forall"]["var"]}, (
        f"the `at` index must be the quantifier's own (fresh) binder, got {at_args[1]!r} "
        f"vs binder {req['forall']['var']!r}")
    print(f"test_quantifier_membership_binder_substitution: "
         f"'k | k in s :: k > 0' -> at(s, {req['forall']['var']}) > 0")


UNIT_TESTS = [
    test_chain_desugared, test_iff_to_eq, test_nat_return_ensures,
    test_nat_invariant_added_and_dedup, test_spec_fun_totalised,
    test_tail_return, test_parallel_assign_temps, test_default_init,
    test_split_conjuncts_ensures_not_invariants, test_in_desugared_fresh_binder,
    test_array_readonly_as_seq_and_mutation_refusal,
    test_decreases_tuple_projection_and_guess_sum, test_multi_method_one_task_each,
    test_set_refused_before_rewrite, test_calls_other_method_in_assignment,
    test_null_refuses_heap, test_bodyless_method_refused,
    test_method_level_decreases_neither_projects_nor_sums,
    test_predicate_result_is_bool,
    test_seq_nat_param_refused, test_quantifier_membership_binder_substitution,
]


# ===========================================================================
# Driver: run(slow) is test_lifter.py's contract for each implementer file.
# ===========================================================================

def run(slow: bool = False) -> None:
    if not corpora.available(CORPUS_RPRINT, INFRAGMENT):
        print("test_lift_rules: skipped, "
              + corpora.why_missing(CORPUS_RPRINT, INFRAGMENT))
        return
    failures = 0

    print("-- unit tests (acceptance c) --")
    for fn in UNIT_TESTS:
        try:
            fn()
        except AssertionError as e:
            failures += 1
            print(f"{fn.__name__}: FAILED: {e}")
        except Exception as e:
            failures += 1
            traceback.print_exc()
            print(f"{fn.__name__}: FAILED (exception): {e}")

    print("-- seed acceptance (acceptance a) --")
    try:
        test_seed_acceptance()
    except AssertionError as e:
        failures += 1
        print(f"test_seed_acceptance: FAILED: {e}")

    print("-- infragment acceptance (acceptance b) --")
    try:
        test_infragment()
    except AssertionError as e:
        failures += 1
        print(f"test_infragment: FAILED: {e}")

    if failures:
        raise AssertionError(f"{failures} test group(s) failed")
    print("test_lift_rules: all checks passed")


if __name__ == "__main__":
    try:
        run(slow="--slow" in sys.argv)
    except AssertionError as e:
        print(f"FAILED: {e}")
        sys.exit(1)
    sys.exit(0)
