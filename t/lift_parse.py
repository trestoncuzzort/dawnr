"""Parse the resolver's print into the section-3 AST, and print it back.

LIFTER-DESIGN.md section 1 (rprint over a hand grammar of raw Dafny: rprint
is dafny's OWN unparse of what it resolved, so the parser here never has to
resolve overloads, imports, or type inference itself), section 3 (the EBNF
this module implements, reproduced as `lift_ast.py`'s node types), and
section 10(b) (the fixpoint property this module exists to make true:
`rprint(print(parse(rprint(f)))) == rprint(f)`).

The parser recognises MORE than t accepts (section 3's opening paragraph):
it must read the whole method to name a precise refusal, so it builds AST
nodes for every construct in section 3's grammar (`lift_ast.py`'s
`SkippedDecl`, `NewRhs`, `Slice`, `SeqUpdate`, ... included), and leaves
"is this liftable" entirely to `lift_classify.py`. A parse error means a
token OUTSIDE section 3's grammar entirely -- something even the permissive
grammar above does not admit -- and is always a `parse-failure`, never a
guess at what the author meant.

Architecture role (LIFTER-DESIGN.md section 2's table, copied verbatim):
    input: rprint text
    output: a Dafny AST of the fragment in section 3, or a parse error
            naming the token
    MAY decide: which declaration is the gradable method (a `method` with
                >= 1 ensures)
    MAY NOT decide: whether a construct is liftable

IMPLEMENTATION NOTE on the preamble (section 1): every rprint opens with
"// <filename>", then one big `/* ... */` comment holding the `module
_System { ... }` block and the "// bitvector types in use:" line (this
comment nests other `/* */` comments inside it -- `/*-- non-null type
...*/`, `/*special witness*/`, `/*_tuple#2*/` -- so finding its end needs a
depth-counting scan, not a naive first-`*/`-wins search), then a second
`/* CALL GRAPH for module _module: ... */` comment this module DOES read
(into `lift_ast.CallGraphSCC`), then the real declarations, which rprint
prints comment-free (measured: no in-fragment declaration carries an
embedded comment). `_skip_preamble` implements exactly this, generically
(any `//` line comment or nested `/* */` block comment is skipped the same
way, so a comment appearing after the preamble, if one ever did, would not
crash the scan).

IMPLEMENTATION NOTE on `Skipped` declarations (section 3): rprint prints
every top-level declaration starting at column 0, with everything that
belongs to it (spec clauses, nested members, continuation lines of a
multi-line subset type) indented -- the same invariant `verifiers/dafny
.py`'s own `_RP_HEAD`/`_RP_CLAUSE` regexes rely on. This module never
elaborates a `Skipped` declaration's internals (`lift_ast.SkippedDecl` has
no field to hold them), so it finds the declaration's extent the same way:
skip tokens until the next one that is both first-on-its-line and one of
the recognised top-level start words, or EOF.
"""

from __future__ import annotations

import bisect
import re
from typing import NamedTuple, Optional, Union

from lift_ast import (
    AssertByStmt, AssertStmt, Assign, AssignSuchThat, AssumeStmt, Attr, Binary, BlockStmt,
    BoolLit, BreakStmt, CalcStmt, Call, CallGraphSCC, CallStmt, Cardinality,
    Cast, Chain, CharLit, ContinueStmt, Comprehension, DecreasesClause,
    EnsuresClause, Expr, ExpectStmt, ForallStmt, ForStmt, Fresh, FunctionDecl,
    Ident, Iff, IfCaseStmt, IfExpr, IfStmt, Implies, Index, IntLit, InvariantClause,
    LabelStmt, LemmaDecl, Lhs, MapDisplay, Member, MethodDecl, Module,
    ModifiesClause, NaryBool, NewRhs, Node, Old, Param, PrintStmt,
    Quantifier, ReadsClause, RealLit, RequiresClause, Refusal, ReturnStmt,
    RevealStmt, SeqDisplay, SeqUpdate, SetDisplay, SkippedDecl, Slice, Star,
    Stmt, StringLit, Type, TupleExpr, TypeTest, Unary, VarDeclStmt,
    WhileCaseStmt, WhileStmt,
)


class LiftParseError(Exception):
    """Raised by `parse` on a token outside section 3's grammar entirely.

    `token` is the offending token's source text; `line` is its 1-based
    line in the rprint text that was passed to `parse`. Every catcher of
    this exception (`lifter.py`, `lift_census.py`) turns it into a
    `lift_ast.Refusal(reason="parse-failure", token=token, line=line,
    stage="parse")` -- this module raises the exception rather than
    building the `Refusal` itself so it has no dependency on how a caller
    chooses to report a file-level vs. method-level parse failure."""

    def __init__(self, token: str, line: int, message: str = ""):
        super().__init__(message or f"unexpected token {token!r} at line {line}")
        self.token = token
        self.line = line


# ===========================================================================
# Lexer.
# ===========================================================================

class Token(NamedTuple):
    kind: str    # "id" | "int" | "real" | "char" | "string" | "op" | "eof"
    text: str
    line: int
    col: int     # 0-based column of the token's first character
    start: int   # character offset of the token's first character
    end: int     # character offset just past the token's last character


# Longest-match-first: multi-character operators. "!in" is checked with an
# extra word-boundary guard below (so "!interesting" does not clip to
# "!in" + "teresting") since it is the one entry that is letters, not pure
# punctuation.
_MULTI_OPS = [
    "<==>", "==>", "<==", "-->", "::", ":=", ":|", "..", "<=", ">=",
    "==", "!=", "&&", "||", "~>", "->", "=>",
]
_SINGLE_OPS = set("()[]{},.:;|!+-*/%<>=?@#")


def _compute_line_starts(text: str) -> list[int]:
    starts = [0]
    for idx, ch in enumerate(text):
        if ch == "\n":
            starts.append(idx + 1)
    return starts


def _line_of(line_starts: list[int], pos: int) -> int:
    return bisect.bisect_right(line_starts, pos)


def _skip_block_comment(text: str, i: int) -> int:
    """`text[i:i+2] == "/*"`. Returns the index just past the matching
    `*/`, counting nested `/* */` pairs (section 1: the preamble's outer
    comment nests several inner ones). Returns `len(text)` if the comment
    is never closed (an rprint truncated by a timeout, say); the caller's
    own token/EOF handling then reports the failure rather than this
    function looping forever."""
    depth = 1
    j = i + 2
    n = len(text)
    while j < n and depth > 0:
        if text.startswith("/*", j):
            depth += 1
            j += 2
        elif text.startswith("*/", j):
            depth -= 1
            j += 2
        else:
            j += 1
    return j


_SCC_HEAD_RE = re.compile(r"^\s*\*\s*SCC at height\s+(\d+)\s*:\s*$")
_SCC_NAME_RE = re.compile(r"^\s*\*\s+(\S+)\s*$")


def _parse_call_graph(comment_body: str) -> tuple[CallGraphSCC, ...]:
    """`comment_body` is the text between the `/* CALL GRAPH for module
    _module:` marker (exclusive) and the closing `*/` (exclusive) of that
    second preamble comment. Best-effort: a line this does not recognise
    is simply not counted as height or name (never raises -- the call
    graph is a closure-rule convenience for `lift_rewrite.py`, not a
    refusal-bearing structure, so a malformed line here should not cost a
    file its whole parse)."""
    sccs: list[CallGraphSCC] = []
    cur_height: Optional[int] = None
    cur_names: list[str] = []
    for raw_line in comment_body.splitlines():
        m = _SCC_HEAD_RE.match(raw_line)
        if m:
            if cur_height is not None:
                sccs.append(CallGraphSCC(cur_height, tuple(cur_names)))
            cur_height = int(m.group(1))
            cur_names = []
            continue
        m2 = _SCC_NAME_RE.match(raw_line)
        if m2:
            cur_names.append(m2.group(1))
    if cur_height is not None:
        sccs.append(CallGraphSCC(cur_height, tuple(cur_names)))
    return tuple(sccs)


def _skip_preamble(text: str) -> tuple[tuple[CallGraphSCC, ...], int]:
    """Returns (call_graph, offset) where `offset` is the character index
    at which the real declarations begin (section 1's preamble: the
    "// filename" line, the big `module _System { ... }` comment, the
    `/* CALL GRAPH for module _module: ... */` comment -- read into
    `call_graph` -- in that order, each optional so this also tolerates
    being handed text with no preamble at all, e.g. `print_dafny`'s own
    output fed back through the section 10(b)/12 fixpoint test)."""
    i, n = 0, len(text)
    call_graph: tuple[CallGraphSCC, ...] = ()
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
            continue
        if text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if text.startswith("/*", i):
            j = _skip_block_comment(text, i)
            body = text[i + 2:max(i + 2, j - 2)]
            if body.lstrip().startswith("CALL GRAPH for module _module:"):
                call_graph = _parse_call_graph(body)
            i = j
            continue
        break
    return call_graph, i


def _lex(text: str, start: int, line_starts: list[int]) -> list[Token]:
    tokens: list[Token] = []
    i, n = start, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
            continue
        if text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if text.startswith("/*", i):
            i = _skip_block_comment(text, i)
            continue

        start_i = i
        if c.isalpha() or c == "_":
            j = i + 1
            while j < n and (text[j].isalnum() or text[j] in "_'"):
                j += 1
            if j < n and text[j] == "?":
                j += 1
            kind, tok_text = "id", text[i:j]
            i = j
        elif c.isdigit():
            j = i + 1
            while j < n and text[j].isdigit():
                j += 1
            if j < n and text[j] == "." and j + 1 < n and text[j + 1].isdigit():
                j += 1
                while j < n and text[j].isdigit():
                    j += 1
                kind = "real"
            else:
                kind = "int"
            tok_text = text[i:j]
            i = j
        elif c == "'":
            j = i + 1
            if j < n and text[j] == "\\":
                j += 2
                if j - 1 < n and text[j - 1] == "{":
                    while j < n and text[j] != "}":
                        j += 1
                    j += 1
            elif j < n:
                j += 1
            if j < n and text[j] == "'":
                j += 1
            kind, tok_text = "char", text[i:j]
            i = j
        elif c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            j = min(j + 1, n)
            kind, tok_text = "string", text[i:j]
            i = j
        elif c == "!" and text.startswith("!in", i) and not (
            i + 3 < n and (text[i + 3].isalnum() or text[i + 3] in "_'")
        ):
            kind, tok_text = "op", "!in"
            i += 3
        else:
            matched = next((op for op in _MULTI_OPS if text.startswith(op, i)), None)
            if matched:
                kind, tok_text = "op", matched
                i += len(matched)
            elif c in _SINGLE_OPS:
                kind, tok_text = "op", c
                i += 1
            else:
                raise LiftParseError(c, _line_of(line_starts, start_i),
                                      f"unrecognised character {c!r}")

        tok_line = _line_of(line_starts, start_i)
        tok_col = start_i - line_starts[tok_line - 1]
        tokens.append(Token(kind, tok_text, tok_line, tok_col, start_i, i))

    eof_line = _line_of(line_starts, n)
    tokens.append(Token("eof", "", eof_line, 0, n, n))
    return tokens


# ===========================================================================
# Grammar vocabulary.
# ===========================================================================

MODIFIER_WORDS = {"ghost", "static", "twostate", "least", "greatest", "opaque", "abstract"}
SKIPPED_BASE_WORDS = {
    "datatype", "codatatype", "class", "trait", "type", "newtype", "const",
    "iterator", "module", "import", "export",
}
BASE_DECL_WORDS = {"function", "predicate", "method", "lemma"} | SKIPPED_BASE_WORDS
TOP_LEVEL_START_WORDS = MODIFIER_WORDS | BASE_DECL_WORDS

RELOPS = {"==", "!=", "<", "<=", ">", ">=", "in", "!in"}

# section 3's Skipped production maps to the census's own gap vocabulary
# (LIFTER-DESIGN.md section 3's closing comment, section 5's vocabulary).
# "type-decl" is the census's generic bucket for a type-shaped declaration
# with no more specific name of its own (class, trait, a type synonym, a
# newtype, a top-level const); "datatype"/"iterator"/"module" and the two
# extreme-predicate forms each have their own census key. `import`/`export`
# fold under "module" (they are the module system, not a type). "twostate
# function"/"twostate predicate" have no dedicated census key measured so
# far -- they fall to "type-decl" as the nearest general bucket; flagged
# for the classify/census implementer to confirm or override.
KEYWORD_GAP_NAME = {
    "datatype": "datatype",
    "codatatype": "datatype",
    "class": "type-decl",
    "trait": "type-decl",
    "type": "type-decl",
    "newtype": "type-decl",
    "const": "type-decl",
    "iterator": "iterator",
    "module": "module",
    "import": "module",
    "export": "module",
    "least predicate": "extreme-predicate",
    "greatest predicate": "extreme-predicate",
    "twostate function": "type-decl",
    "twostate predicate": "type-decl",
}


def _combine_keyword(modifiers: list[str], base: str) -> str:
    prefix = [m for m in modifiers if m in ("least", "greatest", "twostate")]
    return f"{prefix[-1]} {base}" if prefix else base


# ===========================================================================
# Parser.
# ===========================================================================

class _Parser:
    def __init__(self, tokens: list[Token], source: str):
        self.tokens = tokens
        self.pos = 0
        self._source = source

    @property
    def cur(self) -> Token:
        return self.tokens[self.pos]

    def at(self, text: str) -> bool:
        return self.cur.text == text and self.cur.kind != "eof"

    def at_eof(self) -> bool:
        return self.cur.kind == "eof"

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        if tok.kind != "eof":
            self.pos += 1
        return tok

    def expect(self, text: str) -> Token:
        if not self.at(text):
            raise LiftParseError(self.cur.text or "<eof>", self.cur.line,
                                  f"expected {text!r}, found {self.cur.text!r}")
        return self.advance()

    def expect_ident(self) -> str:
        if self.cur.kind != "id":
            raise LiftParseError(self.cur.text or "<eof>", self.cur.line,
                                  f"expected identifier, found {self.cur.text!r}")
        return self.advance().text

    # -- declarations -------------------------------------------------

    def parse_module_decls(self) -> list:
        decls = []
        while not self.at_eof():
            decls.append(self.parse_decl())
        return decls

    def parse_decl(self):
        start_line = self.cur.line
        modifiers: list[str] = []
        while self.cur.text in MODIFIER_WORDS:
            modifiers.append(self.advance().text)
        base = self.cur.text
        if base in ("function", "predicate"):
            if any(m in ("twostate", "least", "greatest") for m in modifiers):
                return self._parse_skipped(modifiers, base, start_line)
            return self._parse_function(modifiers, base, start_line)
        if base == "method":
            return self._parse_method(modifiers, start_line)
        if base == "lemma":
            return self._parse_lemma(modifiers, start_line)
        if base in SKIPPED_BASE_WORDS:
            return self._parse_skipped(modifiers, base, start_line)
        raise LiftParseError(base or "<eof>", self.cur.line)

    def _parse_skipped(self, modifiers: list[str], base: str, start_line: int) -> SkippedDecl:
        combined = _combine_keyword(modifiers, base)
        gap_name = KEYWORD_GAP_NAME.get(combined, "type-decl")
        self.advance()  # the base keyword itself
        while not self.at_eof() and not (
            self.cur.col == 0 and self.cur.text in TOP_LEVEL_START_WORDS
        ):
            self.advance()
        return SkippedDecl(start_line, keyword=combined, gap_name=gap_name)

    def _parse_attrs(self) -> tuple[Attr, ...]:
        attrs = []
        while self.at("{") and self.tokens[self.pos + 1].text == ":":
            line = self.cur.line
            self.advance()  # "{"
            self.advance()  # ":"
            name = self.expect_ident()
            args = self._parse_expr_list_until("}")
            self.expect("}")
            attrs.append(Attr(line, name, tuple(args)))
        return tuple(attrs)

    def _parse_type_params(self) -> tuple[str, ...]:
        if not self.at("<"):
            return ()
        self.advance()
        names = []
        while not self.at(">"):
            if self.cur.text in ("+", "-", "*"):
                self.advance()
            names.append(self.expect_ident())
            if self.at("("):
                depth = 0
                while True:
                    if self.at("("):
                        depth += 1
                    elif self.at(")"):
                        depth -= 1
                    self.advance()
                    if depth == 0:
                        break
            if self.at(","):
                self.advance()
            else:
                break
        self.expect(">")
        return tuple(names)

    def _parse_params(self) -> list[Param]:
        params = []
        if self.at(")"):
            return params
        params.append(self._parse_param())
        while self.at(","):
            self.advance()
            params.append(self._parse_param())
        return params

    def _parse_param(self) -> Param:
        line = self.cur.line
        ghost = False
        if self.at("ghost"):
            self.advance()
            ghost = True
        name = self.expect_ident()
        self.expect(":")
        type_ = self.parse_type()
        return Param(line, name, type_, ghost)

    def _parse_binder(self) -> Param:
        line = self.cur.line
        name = self.expect_ident()
        type_ = None
        if self.at(":"):
            self.advance()
            type_ = self.parse_type()
        return Param(line, name, type_, False)

    def _parse_binders(self) -> list[Param]:
        binders = [self._parse_binder()]
        while self.at(","):
            self.advance()
            binders.append(self._parse_binder())
        return binders

    def _parse_function(self, modifiers: list[str], base: str, line: int) -> FunctionDecl:
        self.advance()  # function | predicate
        attrs = self._parse_attrs()
        name = self.expect_ident()
        type_params = self._parse_type_params()
        self.expect("(")
        params = self._parse_params()
        self.expect(")")
        is_predicate = base == "predicate"
        ret_type = None
        if self.at(":"):
            self.advance()
            ret_type = self.parse_type()
        specs = self._parse_fspec_list()
        body = None
        if self.at("{"):
            self.advance()
            body = self.parse_expr()
            self.expect("}")
        return FunctionDecl(line, name=name, ghost="ghost" in modifiers,
                             is_predicate=is_predicate, type_params=type_params,
                             params=tuple(params), ret_type=ret_type,
                             specs=tuple(specs), body=body, attrs=attrs)

    def _parse_method(self, modifiers: list[str], line: int) -> MethodDecl:
        self.advance()  # method
        attrs = self._parse_attrs()
        name = self.expect_ident()
        type_params = self._parse_type_params()
        self.expect("(")
        params = self._parse_params()
        self.expect(")")
        returns: list[Param] = []
        if self.at("returns"):
            self.advance()
            self.expect("(")
            returns = self._parse_params()
            self.expect(")")
        specs = self._parse_mspec_list()
        body = None
        if self.at("{"):
            body = self.parse_block()
        return MethodDecl(line, name=name, type_params=type_params,
                           params=tuple(params), returns=tuple(returns),
                           specs=tuple(specs), body=body, attrs=attrs)

    def _parse_lemma(self, modifiers: list[str], line: int) -> LemmaDecl:
        start = self.cur.start if not modifiers else self.tokens[self.pos - len(modifiers)].start
        self.advance()  # lemma
        self._parse_attrs()
        self.expect_ident()  # name (not separately retained; text below has it)
        self._parse_type_params()
        self.expect("(")
        self._parse_params()
        self.expect(")")
        if self.at("returns"):
            self.advance()
            self.expect("(")
            self._parse_params()
            self.expect(")")
        self._parse_mspec_list()
        end = self.tokens[self.pos - 1].end
        if self.at("{"):
            self.advance()
            depth = 1
            while depth > 0:
                if self.at("{"):
                    depth += 1
                elif self.at("}"):
                    depth -= 1
                elif self.at_eof():
                    raise LiftParseError("<eof>", self.cur.line, "unterminated lemma body")
                self.advance()
            end = self.tokens[self.pos - 1].end
        keyword = _combine_keyword(modifiers, "lemma")
        text = self._source[start:end]
        return LemmaDecl(line, keyword=keyword, text=text)

    def _parse_fspec_list(self) -> list:
        specs = []
        while True:
            line = self.cur.line
            if self.at("requires"):
                self.advance()
                specs.append(RequiresClause(line, self.parse_expr()))
            elif self.at("ensures"):
                self.advance()
                specs.append(EnsuresClause(line, self.parse_expr()))
            elif self.at("reads"):
                self.advance()
                specs.append(ReadsClause(line, self._parse_exprlist_or_star()))
            elif self.at("decreases"):
                self.advance()
                specs.append(DecreasesClause(line, self._parse_exprlist_or_star()))
            else:
                break
        return specs

    def _parse_mspec_list(self) -> list:
        specs = []
        while True:
            line = self.cur.line
            if self.at("requires"):
                self.advance()
                specs.append(RequiresClause(line, self.parse_expr()))
            elif self.at("ensures"):
                self.advance()
                specs.append(EnsuresClause(line, self.parse_expr()))
            elif self.at("modifies"):
                self.advance()
                specs.append(ModifiesClause(line, self._parse_exprlist_or_star()))
            elif self.at("decreases"):
                self.advance()
                specs.append(DecreasesClause(line, self._parse_exprlist_or_star()))
            else:
                break
        return specs

    def _parse_loopspec_list(self) -> list:
        specs = []
        while True:
            line = self.cur.line
            if self.at("invariant"):
                self.advance()
                specs.append(InvariantClause(line, self.parse_expr()))
            elif self.at("decreases"):
                self.advance()
                specs.append(DecreasesClause(line, self._parse_exprlist_or_star()))
            elif self.at("modifies"):
                self.advance()
                specs.append(ModifiesClause(line, self._parse_exprlist_or_star()))
            else:
                break
        return specs

    def _parse_exprlist_or_star(self):
        line = self.cur.line
        if self.at("*"):
            self.advance()
            return Star(line)
        return tuple(self._parse_expr_list())

    def _parse_expr_list(self) -> list[Expr]:
        exprs = [self.parse_expr()]
        while self.at(","):
            self.advance()
            exprs.append(self.parse_expr())
        return exprs

    def _parse_expr_list_until(self, closing: str) -> list[Expr]:
        if self.at(closing):
            return []
        return self._parse_expr_list()

    # -- types ----------------------------------------------------------

    def parse_type(self) -> Type:
        base = self._parse_type_primary()
        if self.cur.text in ("->", "~>", "-->"):
            self.advance()
            cod = self.parse_type()
            return Type(base.line, kind="func", args=(base, cod))
        return base

    def _parse_type_primary(self) -> Type:
        line = self.cur.line
        tok = self.cur
        if tok.kind == "id" and re.fullmatch(r"bv\d+", tok.text):
            self.advance()
            return Type(line, kind="bv", bits=int(tok.text[2:]))
        if tok.text in ("int", "nat", "bool", "string", "char", "real"):
            self.advance()
            return Type(line, kind=tok.text)
        if tok.text in ("seq", "set", "iset", "multiset"):
            self.advance()
            self.expect("<")
            inner = self.parse_type()
            self.expect(">")
            return Type(line, kind=tok.text, args=(inner,))
        if tok.text in ("map", "imap"):
            self.advance()
            self.expect("<")
            k = self.parse_type()
            self.expect(",")
            v = self.parse_type()
            self.expect(">")
            return Type(line, kind=tok.text, args=(k, v))
        if tok.text in ("array", "array?"):
            nullable = tok.text.endswith("?")
            self.advance()
            args: tuple[Type, ...] = ()
            if self.at("<"):
                self.advance()
                args = (self.parse_type(),)
                self.expect(">")
            return Type(line, kind="array", args=args, nullable=nullable)
        if self.at("("):
            self.advance()
            elems = []
            if not self.at(")"):
                elems.append(self.parse_type())
                while self.at(","):
                    self.advance()
                    elems.append(self.parse_type())
            self.expect(")")
            if len(elems) == 1:
                return elems[0]
            return Type(line, kind="tuple", args=tuple(elems))
        if tok.kind == "id":
            self.advance()
            name = tok.text
            args = ()
            if self.at("<"):
                self.advance()
                items = [self.parse_type()]
                while self.at(","):
                    self.advance()
                    items.append(self.parse_type())
                self.expect(">")
                args = tuple(items)
            return Type(line, kind="id", name=name, args=args)
        raise LiftParseError(tok.text or "<eof>", tok.line, "expected a type")

    # -- statements -------------------------------------------------------

    def parse_block(self) -> tuple[Stmt, ...]:
        self.expect("{")
        stmts = []
        while not self.at("}"):
            stmts.append(self.parse_stmt())
        self.expect("}")
        return tuple(stmts)

    def parse_stmt(self) -> Stmt:
        tok = self.cur
        line = tok.line

        if self.at("var"):
            return self._parse_var_stmt(line)
        if self.at("ghost") and self.tokens[self.pos + 1].text == "var":
            # Measured (2026-09-05): rprint always prints "ghost var ...",
            # never "var ghost ..." (519 occurrences of the former, 0 of
            # the latter across the 785-file corpus) -- the opposite
            # keyword order from section 3's literal EBNF (`"var"
            # ["ghost"] VarDecl...`). Accepted here to match measured
            # reality; `_parse_var_stmt` still also accepts "var ghost"
            # defensively, in case some other dafny version prints that.
            self.advance()  # "ghost"
            return self._parse_var_stmt(line, ghost_prefix=True)
        if self.at("if"):
            return self._parse_if_stmt(line)
        if self.at("while"):
            return self._parse_while_stmt(line)
        if self.at("for"):
            return self._parse_for_stmt(line)
        if self.at("return"):
            self.advance()
            values = []
            if not self.at(";"):
                values = self._parse_expr_list()
            self.expect(";")
            return ReturnStmt(line, tuple(values))
        if self.at("break"):
            self.advance()
            label = None
            if self.cur.kind == "id":
                label = self.advance().text
            elif self.cur.kind == "int":
                self.advance()
            self.expect(";")
            return BreakStmt(line, label)
        if self.at("continue"):
            self.advance()
            label = None
            if self.cur.kind == "id":
                label = self.advance().text
            elif self.cur.kind == "int":
                self.advance()
            self.expect(";")
            return ContinueStmt(line, label)
        if self.at("assert"):
            self.advance()
            attrs = self._parse_attrs()
            cond = self.parse_expr()
            if self.at("by"):
                self.advance()
                proof = self.parse_block()
                return AssertByStmt(line, cond, proof)
            self.expect(";")
            return AssertStmt(line, cond, attrs)
        if self.at("assume"):
            self.advance()
            self._parse_attrs()
            cond = self.parse_expr()
            self.expect(";")
            return AssumeStmt(line, cond)
        if self.at("calc"):
            return self._parse_calc_stmt(line)
        if self.at("forall"):
            self.advance()
            binders = tuple(self._parse_binders())
            attrs = self._parse_attrs()
            range_ = None
            if self.at("|"):
                self.advance()
                range_ = self.parse_expr()
            # A forall-STATEMENT may carry its own "ensures" clause(s)
            # before the body block (measured: "...FindPivotIndex.dfy":
            # "forall k: nat {...} | 0 <= k < i && ... ensures ... {").
            # `lift_ast.ForallStmt` has no field for these (the node is
            # always `forall-statement`-refused downstream regardless, per
            # its own docstring), so they are parsed and discarded here
            # rather than left to derail the rest of the file's decl loop.
            while self.at("ensures"):
                self.advance()
                self.parse_expr()
            body = self.parse_block()
            return ForallStmt(line, binders, attrs, range_, body)
        if self.at("print"):
            self.advance()
            args = self._parse_exprlist_or_star()
            self.expect(";")
            return PrintStmt(line, args)
        if self.at("expect"):
            self.advance()
            cond = self.parse_expr()
            if self.at(","):
                self.advance()
                self.parse_expr()  # optional failure message, discarded
            self.expect(";")
            return ExpectStmt(line, cond)
        if self.at("reveal"):
            self.advance()
            start = self.cur.start
            depth = 0
            while not (depth == 0 and self.at(";")):
                if self.cur.text in ("(", "[", "{"):
                    depth += 1
                elif self.cur.text in (")", "]", "}"):
                    depth -= 1
                elif self.at_eof():
                    raise LiftParseError("<eof>", self.cur.line, "unterminated reveal")
                self.advance()
            text = self._source[start:self.cur.start].strip()
            self.expect(";")
            return RevealStmt(line, text)
        if self.at("label"):
            self.advance()
            name = self.expect_ident()
            self.expect(":")
            inner = self.parse_stmt()
            return LabelStmt(line, name, inner)
        if self.at("{"):
            return BlockStmt(line, self.parse_block())

        # Assign or CallStmt, both starting with an identifier.
        if tok.kind == "id" and self.tokens[self.pos + 1].text == "(":
            name = self.advance().text
            self.advance()  # "("
            args = self._parse_expr_list_until(")")
            self.expect(")")
            self.expect(";")
            return CallStmt(line, name, tuple(args))

        lhss = [self._parse_lhs()]
        while self.at(","):
            self.advance()
            lhss.append(self._parse_lhs())
        self.expect(":=")
        values = [self._parse_rhs()]
        while self.at(","):
            self.advance()
            values.append(self._parse_rhs())
        self.expect(";")
        return Assign(line, tuple(lhss), tuple(values))

    def _parse_var_stmt(self, line: int, ghost_prefix: bool = False) -> Stmt:
        self.advance()  # var
        ghost = ghost_prefix
        if self.at("ghost"):
            self.advance()
            ghost = True
        names = [self._parse_vardecl_name()]
        while self.at(","):
            self.advance()
            names.append(self._parse_vardecl_name())
        if self.at(":|"):
            self.advance()
            cond = self.parse_expr()
            self.expect(";")
            return AssignSuchThat(line, tuple(names), cond)
        init = None
        if self.at(":="):
            self.advance()
            init = [self._parse_rhs()]
            while self.at(","):
                self.advance()
                init.append(self._parse_rhs())
            init = tuple(init)
        self.expect(";")
        return VarDeclStmt(line, ghost, tuple(names), init)

    def _parse_vardecl_name(self) -> Param:
        line = self.cur.line
        name = self.expect_ident()
        type_ = None
        if self.at(":"):
            self.advance()
            type_ = self.parse_type()
        return Param(line, name, type_, False)

    def _parse_case_block(self):
        cases = []
        while self.at("case"):
            self.advance()
            cond = self.parse_expr()
            self.expect("=>")
            stmts = []
            while not (self.at("case") or self.at("}")):
                stmts.append(self.parse_stmt())
            cases.append((cond, tuple(stmts)))
        return cases

    def _parse_if_stmt(self, line: int) -> Stmt:
        self.advance()  # if
        if self.at("{"):
            self.advance()
            cases = self._parse_case_block()
            self.expect("}")
            return IfCaseStmt(line, tuple(cases))
        cond: Union[Expr, Star]
        if self.at("*"):
            cond = Star(self.cur.line)
            self.advance()
        else:
            cond = self.parse_expr()
        then_block = self.parse_block()
        else_ = None
        if self.at("else"):
            self.advance()
            if self.at("if"):
                else_ = self._parse_if_stmt(self.cur.line)
            else:
                else_ = self.parse_block()
        return IfStmt(line, cond, then_block, else_)

    def _parse_while_stmt(self, line: int) -> Stmt:
        self.advance()  # while
        if self.at("{"):
            self.advance()
            cases = self._parse_case_block()
            self.expect("}")
            return WhileCaseStmt(line, (), tuple(cases))
        cond: Union[Expr, Star]
        if self.at("*"):
            cond = Star(self.cur.line)
            self.advance()
        else:
            cond = self.parse_expr()
        specs = self._parse_loopspec_list()
        body = self.parse_block()
        return WhileStmt(line, cond, tuple(specs), body)

    def _parse_for_stmt(self, line: int) -> Stmt:
        self.advance()  # for
        var = self.expect_ident()
        var_type = None
        if self.at(":"):
            self.advance()
            var_type = self.parse_type()
        self.expect(":=")
        lo = self.parse_expr()
        if self.at("to"):
            direction = "to"
        elif self.at("downto"):
            direction = "downto"
        else:
            raise LiftParseError(self.cur.text or "<eof>", self.cur.line,
                                  "expected 'to' or 'downto'")
        self.advance()
        hi = self.parse_expr()
        specs = self._parse_loopspec_list()
        body = self.parse_block()
        return ForStmt(line, var, var_type, lo, direction, hi, tuple(specs), body)

    def _parse_calc_stmt(self, line: int) -> Stmt:
        start = self.cur.start
        self.advance()  # calc
        # optional hint operator before the brace, e.g. "calc <= { ... }"
        if not self.at("{"):
            self.advance()
        self.expect("{")
        depth = 1
        while depth > 0:
            if self.at("{"):
                depth += 1
            elif self.at("}"):
                depth -= 1
            elif self.at_eof():
                raise LiftParseError("<eof>", self.cur.line, "unterminated calc")
            self.advance()
        text = self._source[start:self.tokens[self.pos - 1].end]
        return CalcStmt(line, text)

    def _parse_lhs(self) -> Lhs:
        line = self.cur.line
        base: Expr = self._atom_ident_expr()
        while True:
            if self.at("["):
                self.advance()
                idx = self.parse_expr()
                self.expect("]")
                if self.at("[") or self.at("."):
                    base = Index(line, base, idx)
                    continue
                return Lhs(line, kind="index", base=base, index=idx)
            if self.at("."):
                self.advance()
                name = self.expect_ident()
                if self.at("[") or self.at("."):
                    base = Member(line, base, name)
                    continue
                return Lhs(line, kind="field", base=base, field=name)
            break
        if isinstance(base, Ident):
            return Lhs(line, kind="name", name=base.name)
        return Lhs(line, kind="index", base=base, index=IntLit(line, 0))

    def _atom_ident_expr(self) -> Expr:
        line = self.cur.line
        name = self.expect_ident()
        return Ident(line, name)

    def _parse_rhs(self):
        line = self.cur.line
        if self.at("*"):
            self.advance()
            return Star(line)
        if self.at("new"):
            return self._parse_new_rhs(line)
        return self.parse_expr()

    def _parse_new_rhs(self, line: int) -> NewRhs:
        start = self.cur.start
        self.advance()  # new
        depth = 0
        end = self.cur.start
        while True:
            if self.at_eof():
                break
            if depth == 0 and (self.at(",") or self.at(";")):
                break
            if self.cur.text in ("(", "[", "{"):
                depth += 1
            elif self.cur.text in (")", "]", "}"):
                depth -= 1
            end = self.advance().end
        text = self._source[start:end].strip()
        return NewRhs(line, text)

    # -- expressions ------------------------------------------------------

    def parse_expr(self) -> Expr:
        return self._parse_equiv()

    def _parse_equiv(self) -> Expr:
        left = self._parse_implies()
        while self.at("<==>"):
            line = self.cur.line
            self.advance()
            right = self._parse_implies()
            left = Iff(line, left, right)
        return left

    def _parse_implies(self) -> Expr:
        left = self._parse_orand()
        if self.at("==>"):
            line = self.cur.line
            self.advance()
            right = self._parse_implies()
            return Implies(line, left, right)
        while self.at("<=="):
            line = self.cur.line
            self.advance()
            right = self._parse_orand()
            left = Implies(line, right, left)
        return left

    def _parse_orand(self) -> Expr:
        left = self._parse_not()
        if self.at("&&"):
            line = self.cur.line
            args = [left]
            while self.at("&&"):
                self.advance()
                args.append(self._parse_not())
            return NaryBool(line, "&&", tuple(args))
        if self.at("||"):
            line = self.cur.line
            args = [left]
            while self.at("||"):
                self.advance()
                args.append(self._parse_not())
            return NaryBool(line, "||", tuple(args))
        return left

    def _parse_not(self) -> Expr:
        if self.at("!"):
            line = self.cur.line
            self.advance()
            return Unary(line, "!", self._parse_not())
        return self._parse_rel()

    def _parse_rel(self) -> Expr:
        left = self._parse_add()
        ops = []
        operands = [left]
        while self.cur.text in RELOPS:
            line = self.cur.line
            ops.append(self.advance().text)
            operands.append(self._parse_add())
        if not ops:
            return left
        return Chain(line, tuple(ops), tuple(operands))

    def _parse_add(self) -> Expr:
        left = self._parse_mul()
        while self.cur.text in ("+", "-"):
            line = self.cur.line
            op = self.advance().text
            right = self._parse_mul()
            left = Binary(line, op, left, right)
        return left

    def _parse_mul(self) -> Expr:
        left = self._parse_unary()
        while self.cur.text in ("*", "/", "%"):
            line = self.cur.line
            op = self.advance().text
            right = self._parse_unary()
            left = Binary(line, op, left, right)
        return left

    def _parse_unary(self) -> Expr:
        if self.at("-"):
            line = self.cur.line
            self.advance()
            return Unary(line, "-", self._parse_unary())
        return self._parse_primary()

    def _parse_primary(self) -> Expr:
        atom = self._parse_atom()
        while True:
            line = self.cur.line
            if self.at("("):
                self.advance()
                args = self._parse_expr_list_until(")")
                self.expect(")")
                atom = Call(line, atom, tuple(args))
            elif self.at("["):
                self.advance()
                if self.at(".."):
                    self.advance()
                    hi = None if self.at("]") else self.parse_expr()
                    self.expect("]")
                    atom = Slice(line, atom, None, hi)
                else:
                    first = self.parse_expr()
                    if self.at(".."):
                        self.advance()
                        hi = None if self.at("]") else self.parse_expr()
                        self.expect("]")
                        atom = Slice(line, atom, first, hi)
                    elif self.at(":="):
                        self.advance()
                        value = self.parse_expr()
                        self.expect("]")
                        atom = SeqUpdate(line, atom, first, value)
                    else:
                        self.expect("]")
                        atom = Index(line, atom, first)
            elif self.at("."):
                self.advance()
                name = self.expect_ident()
                atom = Member(line, atom, name)
            elif self.at("as"):
                self.advance()
                t = self.parse_type()
                atom = Cast(line, atom, t)
            elif self.at("is"):
                self.advance()
                t = self.parse_type()
                atom = TypeTest(line, atom, t)
            else:
                break
        return atom

    def _parse_map_pair(self) -> tuple[Expr, Expr]:
        k = self.parse_expr()
        self.expect(":=")
        v = self.parse_expr()
        return (k, v)

    def _parse_atom(self) -> Expr:
        tok = self.cur
        line = tok.line
        if tok.kind == "int":
            self.advance()
            return IntLit(line, int(tok.text))
        if tok.kind == "real":
            self.advance()
            return RealLit(line, tok.text)
        if tok.kind == "char":
            self.advance()
            return CharLit(line, tok.text)
        if tok.kind == "string":
            self.advance()
            return StringLit(line, tok.text)
        if tok.text == "true":
            self.advance()
            return BoolLit(line, True)
        if tok.text == "false":
            self.advance()
            return BoolLit(line, False)
        if tok.text == "old":
            self.advance()
            self.expect("(")
            e = self.parse_expr()
            self.expect(")")
            return Old(line, e)
        if tok.text == "fresh":
            self.advance()
            self.expect("(")
            e = self.parse_expr()
            self.expect(")")
            return Fresh(line, e)
        if tok.text == "if":
            self.advance()
            cond = self.parse_expr()
            self.expect("then")
            then_ = self.parse_expr()
            self.expect("else")
            else_ = self.parse_expr()
            return IfExpr(line, cond, then_, else_)
        if tok.text in ("forall", "exists"):
            self.advance()
            binders = tuple(self._parse_binders())
            attrs = self._parse_attrs()
            range_ = None
            if self.at("|"):
                self.advance()
                range_ = self.parse_expr()
            self.expect("::")
            body = self.parse_expr()
            return Quantifier(line, tok.text, binders, attrs, range_, body)
        if tok.text == "set":
            self.advance()
            binders = tuple(self._parse_binders())
            self._parse_attrs()
            range_ = None
            if self.at("|"):
                self.advance()
                range_ = self.parse_expr()
            # Dafny's shorthand set-builder omits "::  body" when the body
            # is just the (single) bound variable itself: "set i: int |
            # P(i)" means "set i: int | P(i) :: i" (measured,
            # Clover_count_lessthan.dfy: "|set i: int {:trigger ...} | i
            # in numbers && i < threshold|", no "::" at all before the
            # closing cardinality bar).
            if self.at("::"):
                self.advance()
                body = self.parse_expr()
            else:
                body = Ident(line, binders[0].name)
            return Comprehension(line, "set", binders, range_, body, None)
        if tok.text == "map":
            self.advance()
            if self.at("["):
                self.advance()
                pairs = []
                if not self.at("]"):
                    pairs.append(self._parse_map_pair())
                    while self.at(","):
                        self.advance()
                        pairs.append(self._parse_map_pair())
                self.expect("]")
                return MapDisplay(line, tuple(pairs))
            binders = tuple(self._parse_binders())
            self._parse_attrs()
            range_ = None
            if self.at("|"):
                self.advance()
                range_ = self.parse_expr()
            self.expect("::")
            body = self.parse_expr()
            value = None
            if self.at(":="):
                self.advance()
                value = self.parse_expr()
            return Comprehension(line, "map", binders, range_, body, value)
        if tok.text == "seq" and self.tokens[self.pos + 1].text == "(":
            self.advance()
            self.expect("(")
            n_expr = self.parse_expr()
            self.expect(",")
            var_name = self.expect_ident()
            self.expect("=>")
            body = self.parse_expr()
            self.expect(")")
            return Comprehension(line, "seq", (Param(line, var_name),), n_expr, body, None)
        if tok.text == "multiset" and self.tokens[self.pos + 1].text == "{":
            # `multiset{e, e, ...}` display (measured:
            # "...SelectionSortMultiset.dfy": `requires m != multiset{}`).
            # lift_ast has no dedicated multiset-display node (t has no
            # multiset type at all, so it is always refused downstream
            # regardless); reusing SetDisplay here is a deliberate
            # approximation so the surrounding method still parses instead
            # of derailing the whole file's decl loop the way an
            # unconsumed "{" previously did.
            self.advance()  # multiset
            self.advance()  # "{"
            elems = []
            if not self.at("}"):
                elems.append(self.parse_expr())
                while self.at(","):
                    self.advance()
                    elems.append(self.parse_expr())
            self.expect("}")
            return SetDisplay(line, tuple(elems))
        if tok.text == "|":
            self.advance()
            inner = self.parse_expr()
            self.expect("|")
            return Cardinality(line, inner)
        if tok.text == "(":
            self.advance()
            if self.at(")"):
                self.advance()
                return TupleExpr(line, ())
            elems = [self.parse_expr()]
            while self.at(","):
                self.advance()
                elems.append(self.parse_expr())
            self.expect(")")
            return elems[0] if len(elems) == 1 else TupleExpr(line, tuple(elems))
        if tok.text == "[":
            self.advance()
            elems = []
            if not self.at("]"):
                elems.append(self.parse_expr())
                while self.at(","):
                    self.advance()
                    elems.append(self.parse_expr())
            self.expect("]")
            return SeqDisplay(line, tuple(elems))
        if tok.text == "{":
            self.advance()
            elems = []
            if not self.at("}"):
                elems.append(self.parse_expr())
                while self.at(","):
                    self.advance()
                    elems.append(self.parse_expr())
            self.expect("}")
            return SetDisplay(line, tuple(elems))
        if tok.kind == "id":
            self.advance()
            return Ident(line, tok.text)
        raise LiftParseError(tok.text or "<eof>", tok.line)


def parse(text: str) -> Module:
    """Parse `text` (the `--rprint` output of a `dafny resolve` run, or any
    other text shaped like it -- notably a previous `print_dafny` output,
    which is what the section 10(b)/section 12 test 1 fixpoint test feeds
    back in) into a `lift_ast.Module`.

    Input: rprint text (see `lift_resolve.ResolveResult.rprint_text`).

    Output: a `lift_ast.Module` covering every declaration in section 3's
    `Decl` production (`Function`, `Method`, `Lemma` kept only as
    `lift_ast.LemmaDecl` shells, `Skipped` kept as `lift_ast.SkippedDecl`).
    Raises `LiftParseError` naming the first token outside section 3's
    grammar, never a partial/best-effort `Module`.

    MAY decide: which declaration is the gradable method -- a `method`
    with at least one `ensures` clause and not named `Main` (decision 9).
    This module does not itself return that selection from `parse`; use
    `gradable_methods` below on its result, so `parse`'s contract stays
    "the whole file's AST" and the gradability question has one answer
    site.

    MAY NOT decide: whether a construct is liftable. A `SkippedDecl`, an
    `array` type, an `assume` statement, an unbounded quantifier -- all
    parse cleanly into their `lift_ast` node and are handed unchanged to
    `lift_classify.py`, which alone decides refusal vs. liftable."""
    call_graph, start = _skip_preamble(text)
    line_starts = _compute_line_starts(text)
    tokens = _lex(text, start, line_starts)
    parser = _Parser(tokens, text)
    decls = parser.parse_module_decls()
    return Module(decls=tuple(decls), call_graph=call_graph, source_path=None)


def gradable_methods(module: Module) -> list[MethodDecl]:
    """The `MethodDecl`s in `module` that are gradable: a `method` with at
    least one `ensures` clause, not named `Main` (decision 9's unit of
    counting -- "one task per gradable method"; `Main` is always dropped
    and counted under `main-dropped`, decision 8, never gradable even when
    it happens to carry an `ensures`). Order is the file's declaration
    order, which is also the order `lifter.py` assigns per-method rows in.

    This is the concrete form of `parse`'s "MAY decide: which declaration
    is the gradable method" -- it is deliberately a plain filter over
    `module.decls`, not a new AST field, so a caller can always recompute
    it from a `Module` alone."""
    result = []
    for d in module.decls:
        if not isinstance(d, MethodDecl):
            continue
        if d.name == "Main":
            continue
        if any(isinstance(s, EnsuresClause) for s in d.specs):
            result.append(d)
    return result


# ===========================================================================
# Printer (section 10(b)/12's fixpoint test only -- never a lift).
# ===========================================================================
#
# Because the fixpoint test re-resolves this printer's output with dafny
# and compares dafny's OWN re-canonicalisation to the original banked
# rprint (never this printer's raw text to the original directly), this
# printer does not need to reproduce rprint's exact whitespace or its
# precedence-minimal parenthesisation -- dafny is itself a canonicalising
# pretty-printer, so any syntactically valid, semantics-preserving
# rendering of the same AST reprints to the same canonical form. This
# printer therefore parenthesises liberally (always, for every compound
# expression) rather than minimally: over-parenthesising changes no AST
# dafny would parse back out of it, and removes an entire class of
# precedence bugs a minimal printer would risk.
#
# KNOWN GAP: `lift_ast.SkippedDecl` carries only `keyword`/`gap_name`, not
# the declaration's original text (the interfaces contract has no field
# for it), so this printer cannot reproduce a skipped datatype/class/
# trait/etc. byte-for-byte -- it emits a syntactically valid placeholder
# of the same keyword instead. None of the 77 in-fragment files contain a
# top-level Skipped declaration (measured, see notes_for_integrator), so
# this gap does not affect acceptance test (c); it would need a real text
# field on `SkippedDecl` to fix for the full 785.


def _print_star_or_list(x) -> str:
    if isinstance(x, Star):
        return "*"
    return ", ".join(_print_expr(e) for e in x)


def _print_type(t: Type) -> str:
    if t.kind in ("int", "nat", "bool", "string", "char", "real"):
        return t.kind
    if t.kind == "bv":
        return f"bv{t.bits}"
    if t.kind in ("seq", "set", "iset", "multiset"):
        return f"{t.kind}<{_print_type(t.args[0])}>"
    if t.kind in ("map", "imap"):
        return f"{t.kind}<{_print_type(t.args[0])}, {_print_type(t.args[1])}>"
    if t.kind == "array":
        q = "?" if t.nullable else ""
        inner = f"<{_print_type(t.args[0])}>" if t.args else ""
        return f"array{q}{inner}"
    if t.kind == "tuple":
        return "(" + ", ".join(_print_type(a) for a in t.args) + ")"
    if t.kind == "func":
        return f"({_print_type(t.args[0])}) -> ({_print_type(t.args[1])})"
    if t.kind == "id":
        args = f"<{', '.join(_print_type(a) for a in t.args)}>" if t.args else ""
        return f"{t.name}{args}"
    return t.kind


def _print_param(p: Param) -> str:
    g = "ghost " if p.ghost else ""
    ty = f": {_print_type(p.type)}" if p.type is not None else ""
    return f"{g}{p.name}{ty}"


def _print_expr(e: Expr) -> str:
    if isinstance(e, IntLit):
        return str(e.value)
    if isinstance(e, RealLit):
        return e.text
    if isinstance(e, BoolLit):
        return "true" if e.value else "false"
    if isinstance(e, CharLit):
        return e.text
    if isinstance(e, StringLit):
        return e.text
    if isinstance(e, Ident):
        return e.name
    if isinstance(e, Old):
        return f"old({_print_expr(e.arg)})"
    if isinstance(e, Fresh):
        return f"fresh({_print_expr(e.arg)})"
    if isinstance(e, Unary):
        return f"({e.op}{_print_expr(e.arg)})"
    if isinstance(e, Binary):
        return f"({_print_expr(e.left)} {e.op} {_print_expr(e.right)})"
    if isinstance(e, NaryBool):
        return "(" + f" {e.op} ".join(_print_expr(a) for a in e.args) + ")"
    if isinstance(e, Implies):
        return f"({_print_expr(e.left)} ==> {_print_expr(e.right)})"
    if isinstance(e, Iff):
        return f"({_print_expr(e.left)} <==> {_print_expr(e.right)})"
    if isinstance(e, Chain):
        parts = [_print_expr(e.operands[0])]
        for op, operand in zip(e.ops, e.operands[1:]):
            parts.append(op)
            parts.append(_print_expr(operand))
        return "(" + " ".join(parts) + ")"
    if isinstance(e, IfExpr):
        return f"(if {_print_expr(e.cond)} then {_print_expr(e.then)} else {_print_expr(e.else_)})"
    if isinstance(e, Quantifier):
        binders = ", ".join(_print_param(b) for b in e.binders)
        rng = f" | {_print_expr(e.range)}" if e.range is not None else ""
        return f"({e.kind} {binders}{rng} :: {_print_expr(e.body)})"
    if isinstance(e, SetDisplay):
        return "{" + ", ".join(_print_expr(x) for x in e.elems) + "}"
    if isinstance(e, MapDisplay):
        return "map[" + ", ".join(f"{_print_expr(k)} := {_print_expr(v)}" for k, v in e.pairs) + "]"
    if isinstance(e, SeqDisplay):
        return "[" + ", ".join(_print_expr(x) for x in e.elems) + "]"
    if isinstance(e, Comprehension):
        if e.kind == "seq":
            n_expr = _print_expr(e.range) if e.range is not None else "0"
            var_name = e.binders[0].name if e.binders else "i"
            return f"seq({n_expr}, {var_name} => {_print_expr(e.body)})"
        binders = ", ".join(_print_param(b) for b in e.binders)
        rng = f" | {_print_expr(e.range)}" if e.range is not None else ""
        val = f" := {_print_expr(e.value)}" if e.value is not None else ""
        return f"({e.kind} {binders}{rng} :: {_print_expr(e.body)}{val})"
    if isinstance(e, TupleExpr):
        return "(" + ", ".join(_print_expr(x) for x in e.elems) + ")"
    if isinstance(e, Call):
        return f"{_print_expr(e.fn)}({', '.join(_print_expr(a) for a in e.args)})"
    if isinstance(e, Index):
        return f"{_print_expr(e.base)}[{_print_expr(e.index)}]"
    if isinstance(e, Slice):
        lo = _print_expr(e.lo) if e.lo is not None else ""
        hi = _print_expr(e.hi) if e.hi is not None else ""
        return f"{_print_expr(e.base)}[{lo}..{hi}]"
    if isinstance(e, SeqUpdate):
        return f"{_print_expr(e.base)}[{_print_expr(e.index)} := {_print_expr(e.value)}]"
    if isinstance(e, Member):
        return f"{_print_expr(e.base)}.{e.name}"
    if isinstance(e, Cast):
        return f"({_print_expr(e.base)} as {_print_type(e.type)})"
    if isinstance(e, TypeTest):
        return f"({_print_expr(e.base)} is {_print_type(e.type)})"
    if isinstance(e, Cardinality):
        return f"|{_print_expr(e.arg)}|"
    raise TypeError(f"print_dafny: unhandled expr node {type(e).__name__}")


def _print_rhs(r) -> str:
    if isinstance(r, Star):
        return "*"
    if isinstance(r, NewRhs):
        return r.text
    return _print_expr(r)


def _print_lhs(l: Lhs) -> str:
    if l.kind == "name":
        return l.name
    if l.kind == "index":
        return f"{_print_expr(l.base)}[{_print_expr(l.index)}]"
    return f"{_print_expr(l.base)}.{l.field}"


def _print_fspec(s) -> str:
    if isinstance(s, RequiresClause):
        return f"requires {_print_expr(s.expr)}"
    if isinstance(s, EnsuresClause):
        return f"ensures {_print_expr(s.expr)}"
    if isinstance(s, ReadsClause):
        return f"reads {_print_star_or_list(s.exprs)}"
    if isinstance(s, ModifiesClause):
        return f"modifies {_print_star_or_list(s.exprs)}"
    if isinstance(s, DecreasesClause):
        return f"decreases {_print_star_or_list(s.exprs)}"
    raise TypeError(f"print_dafny: unhandled spec node {type(s).__name__}")


def _print_loopspec(s) -> str:
    if isinstance(s, InvariantClause):
        return f"invariant {_print_expr(s.expr)}"
    return _print_fspec(s)


def _print_stmts(stmts, indent: int) -> list[str]:
    lines = []
    for s in stmts:
        lines.extend(_print_stmt(s, indent))
    return lines


def _print_stmt(s: Stmt, indent: int) -> list[str]:
    pad = " " * indent
    if isinstance(s, VarDeclStmt):
        g = "ghost " if s.ghost else ""
        names = ", ".join(_print_param(p) for p in s.names)
        init = f" := {', '.join(_print_rhs(v) for v in s.init)}" if s.init is not None else ""
        return [f"{pad}var {g}{names}{init};"]
    if isinstance(s, AssignSuchThat):
        names = ", ".join(_print_param(p) for p in s.names)
        return [f"{pad}var {names} :| {_print_expr(s.cond)};"]
    if isinstance(s, Assign):
        lhss = ", ".join(_print_lhs(l) for l in s.targets)
        values = ", ".join(_print_rhs(v) for v in s.values)
        return [f"{pad}{lhss} := {values};"]
    if isinstance(s, IfStmt):
        cond = "*" if isinstance(s.cond, Star) else _print_expr(s.cond)
        lines = [f"{pad}if {cond} {{"]
        lines.extend(_print_stmts(s.then, indent + 2))
        if s.else_ is None:
            lines.append(f"{pad}}}")
        elif isinstance(s.else_, IfStmt):
            nested = _print_stmt(s.else_, indent)
            lines.append(f"{pad}}} else {nested[0].lstrip()}")
            lines.extend(nested[1:])
        else:
            lines.append(f"{pad}}} else {{")
            lines.extend(_print_stmts(s.else_, indent + 2))
            lines.append(f"{pad}}}")
        return lines
    if isinstance(s, IfCaseStmt):
        lines = [f"{pad}if {{"]
        for cond, body in s.cases:
            lines.append(f"{pad}  case {_print_expr(cond)} =>")
            lines.extend(_print_stmts(body, indent + 4))
        lines.append(f"{pad}}}")
        return lines
    if isinstance(s, WhileStmt):
        cond = "*" if isinstance(s.cond, Star) else _print_expr(s.cond)
        lines = [f"{pad}while {cond}"]
        for spec in s.specs:
            lines.append(f"{pad}  {_print_loopspec(spec)}")
        lines.append(f"{pad}{{")
        lines.extend(_print_stmts(s.body, indent + 2))
        lines.append(f"{pad}}}")
        return lines
    if isinstance(s, WhileCaseStmt):
        lines = [f"{pad}while {{"]
        for cond, body in s.cases:
            lines.append(f"{pad}  case {_print_expr(cond)} =>")
            lines.extend(_print_stmts(body, indent + 4))
        lines.append(f"{pad}}}")
        return lines
    if isinstance(s, ForStmt):
        vt = f": {_print_type(s.var_type)}" if s.var_type is not None else ""
        lines = [f"{pad}for {s.var}{vt} := {_print_expr(s.lo)} {s.direction} {_print_expr(s.hi)}"]
        for spec in s.specs:
            lines.append(f"{pad}  {_print_loopspec(spec)}")
        lines.append(f"{pad}{{")
        lines.extend(_print_stmts(s.body, indent + 2))
        lines.append(f"{pad}}}")
        return lines
    if isinstance(s, ReturnStmt):
        vals = " " + ", ".join(_print_expr(v) for v in s.values) if s.values else ""
        return [f"{pad}return{vals};"]
    if isinstance(s, BreakStmt):
        lbl = f" {s.label}" if s.label else ""
        return [f"{pad}break{lbl};"]
    if isinstance(s, ContinueStmt):
        lbl = f" {s.label}" if s.label else ""
        return [f"{pad}continue{lbl};"]
    if isinstance(s, AssertStmt):
        return [f"{pad}assert {_print_expr(s.cond)};"]
    if isinstance(s, AssertByStmt):
        lines = [f"{pad}assert {_print_expr(s.cond)} by {{"]
        lines.extend(_print_stmts(s.proof, indent + 2))
        lines.append(f"{pad}}}")
        return lines
    if isinstance(s, AssumeStmt):
        return [f"{pad}assume {_print_expr(s.cond)};"]
    if isinstance(s, CalcStmt):
        return [f"{pad}{s.text}"]
    if isinstance(s, ForallStmt):
        binders = ", ".join(_print_param(b) for b in s.binders)
        rng = f" | {_print_expr(s.range)}" if s.range is not None else ""
        lines = [f"{pad}forall {binders}{rng} {{"]
        lines.extend(_print_stmts(s.body, indent + 2))
        lines.append(f"{pad}}}")
        return lines
    if isinstance(s, PrintStmt):
        return [f"{pad}print {_print_star_or_list(s.args)};"]
    if isinstance(s, ExpectStmt):
        return [f"{pad}expect {_print_expr(s.cond)};"]
    if isinstance(s, RevealStmt):
        return [f"{pad}reveal {s.text};"]
    if isinstance(s, LabelStmt):
        inner = _print_stmt(s.stmt, indent)
        inner[0] = f"{pad}{s.label}: {inner[0].lstrip()}"
        return inner
    if isinstance(s, CallStmt):
        args = ", ".join(_print_expr(a) for a in s.args)
        return [f"{pad}{s.name}({args});"]
    if isinstance(s, BlockStmt):
        lines = [f"{pad}{{"]
        lines.extend(_print_stmts(s.body, indent + 2))
        lines.append(f"{pad}}}")
        return lines
    raise TypeError(f"print_dafny: unhandled stmt node {type(s).__name__}")


def _print_decl(d) -> str:
    if isinstance(d, FunctionDecl):
        header = ("ghost " if d.ghost else "") + ("predicate " if d.is_predicate else "function ")
        header += d.name
        if d.type_params:
            header += "<" + ", ".join(d.type_params) + ">"
        header += "(" + ", ".join(_print_param(p) for p in d.params) + ")"
        if d.ret_type is not None:
            header += f": {_print_type(d.ret_type)}"
        lines = [header]
        for s in d.specs:
            lines.append(f"  {_print_fspec(s)}")
        if d.body is not None:
            lines.append("{")
            lines.append(f"  {_print_expr(d.body)}")
            lines.append("}")
        return "\n".join(lines)
    if isinstance(d, MethodDecl):
        header = "method " + d.name
        if d.type_params:
            header += "<" + ", ".join(d.type_params) + ">"
        header += "(" + ", ".join(_print_param(p) for p in d.params) + ")"
        if d.returns:
            header += " returns (" + ", ".join(_print_param(p) for p in d.returns) + ")"
        lines = [header]
        for s in d.specs:
            lines.append(f"  {_print_fspec(s)}")
        if d.body is not None:
            lines.append("{")
            lines.extend(_print_stmts(d.body, 2))
            lines.append("}")
        return "\n".join(lines)
    if isinstance(d, LemmaDecl):
        return d.text
    if isinstance(d, SkippedDecl):
        # See "KNOWN GAP" above the printer section: no raw text is kept
        # for a skipped declaration, so this is a syntactically valid
        # placeholder, not a faithful reproduction.
        base = d.keyword.split()[-1]
        safe_name = f"Skipped_{abs(hash((d.keyword, d.line))) % 100000}"
        if base in ("datatype", "codatatype"):
            return f"{base} {safe_name} = {safe_name}_Ctor"
        if base in ("class", "trait"):
            return f"{base} {safe_name} {{ }}"
        if base in ("type", "newtype"):
            return f"{base} {safe_name} = int"
        if base == "const":
            return f"const {safe_name}: int := 0"
        if base == "iterator":
            return f"iterator {safe_name}() {{ }}"
        if base == "module":
            return f"module {safe_name} {{ }}"
        if base in ("import", "export"):
            return f"module {safe_name} {{ }}"
        return f"module {safe_name} {{ }}"
    raise TypeError(f"print_dafny: unhandled decl node {type(d).__name__}")


def print_dafny(module: Module) -> str:
    """The inverse of `parse`: print `module` back out as Dafny surface
    text. See the printer-section comment above for why this need not
    match rprint's exact formatting or its precedence-minimal
    parenthesisation to satisfy the section 12 test 1 fixpoint property
    `rprint(print(parse(rprint(f)))) == rprint(f)` -- dafny's own
    re-resolution and re-print canonicalises whatever valid Dafny this
    function emits, so only syntactic validity and AST fidelity matter
    here, not cosmetic formatting.

    `print_dafny` MUST round-trip every construct `parse` can produce,
    including every construct `lift_classify.py` will go on to refuse
    (`SkippedDecl`, `NewRhs`, an unbounded `Quantifier`, ...): the
    fixpoint test runs on the 77 in-fragment files AND the 49 refusal
    samples (section 12 test 1), so this function MAY NOT decide, any
    more than `parse` may, whether a construct is liftable -- it must be
    able to print anything it can be handed. (`SkippedDecl` is the one
    documented exception -- see "KNOWN GAP" above -- because the AST node
    itself does not carry enough information to do so faithfully.)"""
    return "\n\n".join(_print_decl(d) for d in module.decls) + "\n"
