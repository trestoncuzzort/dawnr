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
    Ident, Iff, IfCaseStmt, IfExpr, IfStmt, Implies, Index, IntLit, InvariantClause, LetExpr,
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
    line in the rprint text that was passed to `parse`. `reason` names the
    census-vocabulary construct the parser recognised at that point when
    it could (section 5, section 18.2): a shape the grammar does not admit
    into the AST but that the parser can still name precisely (a `match`
    statement, a lambda literal, a datatype update, an object method call,
    ...), so the refusal is never just a bare confusing token. It defaults
    to `"parse-failure"` for a token the parser genuinely cannot place at
    all. Every catcher of this exception (`lifter.py`, `lift_census.py`)
    turns it into a `lift_ast.Refusal(reason=e.reason, token=token,
    line=line, stage="parse")` -- this module raises the exception rather
    than building the `Refusal` itself so it has no dependency on how a
    caller chooses to report a file-level vs. method-level parse
    failure."""

    def __init__(self, token: str, line: int, message: str = "",
                 reason: str = "parse-failure"):
        super().__init__(message or f"unexpected token {token!r} at line {line}")
        self.token = token
        self.line = line
        self.reason = reason


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
    # Bitvector-only shift operators (section 18.2's grammar extensions):
    # not round-tripped into t (bitvector is always a refusal), lexed and
    # parsed as ordinary Binary nodes purely so the method around them
    # still parses and the `bv` type is what the classifier names.
    # Deliberately NOT "!!" here: lexing it as one token would also
    # swallow a legitimate double negation ("!!p", two unary "!"), so
    # set/multiset disjointness is recognised as two adjacent "!" tokens
    # at the relational-operator level instead (`_parse_rel`).
    "<<", ">>",
]
_SINGLE_OPS = set("()[]{},.:;|!+-*/%<>=?@#&^")


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
            # "#" is not part of any identifier a Dafny author can write,
            # but rprint synthesises names like "_t#0" (a chained
            # quantifier's compiler-introduced bound variable) and
            # "i#inv" (a forall-statement's own bound variable printed
            # back out); accepting "#<alnum>" as an identifier tail is a
            # lexer-level grammar extension (section 18.2's "a shape the
            # printer emits that the grammar did not anticipate"), not a
            # refusal -- the classifier treats these Ids like any other.
            while j < n and (text[j].isalnum() or text[j] in "_'"
                              or (text[j] == "#" and j + 1 < n
                                  and text[j + 1].isalnum())):
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
                # `\U{H+}` (row 28, 2026-09-09, SPEC.md "Strings as
                # sequences of code points (v1)"): the only valid
                # spelling of a full-range unicode escape on this dafny
                # (measured: `'\U{1F600}'` verifies and runs; `'\{41}'`
                # -- no `U` -- and `'\u{41}'` -- lowercase `u` -- are
                # both parse errors), so this checks for `U` THEN `{`, not a
                # bare `{` (which never follows a backslash in valid
                # Dafny and used to be checked here instead, dead code
                # that left `j` short of the closing `}`/`'` for any
                # `\U{...}` literal, desynchronising the rest of the
                # lexer instead of handing `lift_classify.py` a
                # well-formed token to name a refusal on).
                if j - 1 < n and text[j - 1] == "U" and j < n and text[j] == "{":
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
        elif c == "`":
            # A frame-field designator (`modifies this`value`, `reads
            # this`elements`, or bare `` `field` ``): section 3's grammar
            # has no such node (ReadsClause/ModifiesClause hold Exprs, and
            # a field name alone by itself is not one), and it only ever
            # names a class field on the heap, so it is named `heap`
            # right here rather than falling through to a bare-backtick
            # parse-failure.
            raise LiftParseError("`", _line_of(line_starts, start_i),
                                  "frame field designator", reason="heap")
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

    def _expect_gt(self) -> None:
        """Close one level of `"<" Type ("," Type)* ">"` nesting. A
        nested generic ("seq<Code<V>>") has its two closing angle
        brackets lexed as one ">>" token (added for the bitvector shift
        operator, section 18.2) -- this splits it back into the ">" that
        closes the inner level and a one-character ">" left in the token
        stream for whatever closes the outer level next, instead of
        consuming a shift operator's worth of closing punctuation."""
        if self.at(">>"):
            self.tokens[self.pos] = self.cur._replace(text=">", start=self.cur.start + 1)
            return
        self.expect(">")

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
        self._expect_gt()
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
            # A named result ("function abs(x: int32): (r: int32)"): the
            # author's name for the return value, used only inside this
            # function's own `ensures` clauses. Section 3's Type
            # production has no room for the "Id ':'" prefix (a genuine
            # Type can never start that way, so the two forms never
            # collide); lift_ast.FunctionDecl has no field to hold the
            # name, so it is parsed and dropped -- an `ensures` clause
            # that names it is left referring to a plain, unbound `Ident`,
            # which is exactly as far as this module (parse only) is
            # responsible for going.
            if (self.at("(") and self.tokens[self.pos + 1].kind == "id"
                    and self.tokens[self.pos + 2].text == ":"):
                self.advance()  # "("
                self.expect_ident()  # result name, discarded
                self.expect(":")
                ret_type = self.parse_type()
                self.expect(")")
            else:
                ret_type = self.parse_type()
        specs = self._parse_fspec_list()
        body = None
        if self.at("{"):
            self.advance()
            body = self.parse_expr()
            self._check_hint_chain_semicolon()
            self.expect("}")
        if self.at("by"):
            # `function ... { Expr } by method { Stmt* }`: an alternative
            # imperative implementation of the same function, checked
            # against the `ensures` above by dafny itself. Decision 14
            # names this `function-method`; brace-matched and dropped the
            # same way a lemma body is (section 3's own Skipped/Lemma
            # convention), since section 3's FunctionDecl has no field to
            # hold a second body.
            self.advance()
            self.expect("method")
            self._skip_brace_matched_block()
            raise LiftParseError("by", line, "function ... by method",
                                  reason="function-method")
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

    def _check_hint_chain_semicolon(self) -> None:
        """A fully-parsed Expr followed immediately by ";" (measured in a
        function body's "then" arm: "IntLemma(x); 3") is Dafny's
        statement-in-an-expression form (Reference Manual 9.31.6,
        dafny.org/latest/DafnyRef/DafnyRef#sec-statement-in-an-expression)
        -- a hint statement (a lemma call, an `assert ... by`) sequenced
        before the real result. Called only where no ";" can close anything
        else: a function body, an if-expression's "then" arm, a
        parenthesised expression. NOT after an if-expression's "else" arm:
        there the ";" is as likely the enclosing statement's own terminator
        (`r := if a > 0 then a else 0;`), and reading it as a hint chain
        refused 61 of the 2026-09-26 corpus files, none of which had one; a
        real chain after an "else" arm still reaches the function-body check
        once the if-expression returns. A let expression consumes its own
        ";" (`_parse_let`), so it never reaches here. `lift_ast` has no node
        for a statement inside an expression: refused by the construct's
        own name, `stmt-in-expression` (until 2026-09-26 it borrowed
        `let-expression`, which is now lifted)."""
        if self.at(";"):
            raise LiftParseError(";", self.cur.line, "statement in an expression",
                                  reason="stmt-in-expression")

    def _skip_brace_matched_block(self) -> None:
        """Consume a `"{" ... "}"` block whose interior this module has
        no reason to parse (a lemma body, a `function ... by method`
        body), tracking nested braces so a `{` inside the block does not
        end the scan early."""
        self.expect("{")
        depth = 1
        while depth > 0:
            if self.at("{"):
                depth += 1
            elif self.at("}"):
                depth -= 1
            elif self.at_eof():
                raise LiftParseError("<eof>", self.cur.line, "unterminated block")
            self.advance()

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

    def _skip_clause_label(self) -> None:
        """A `requires`/`ensures`/`invariant`/`assert` clause may open
        with an author-chosen label ("requires A: c <= x", "requires inv:
        0 <= i <= |q| && ...", "assert 0: f(a, f(b, c)) == ... by {...}"):
        section 3's FSpec/MSpec/LoopSpec/AssertStmt have no room for it,
        and no `Spec`/`Stmt` node has a field to keep it in, so it is
        recognised and dropped here. Unambiguous: no Expr production ever
        starts with a bare `Id` or `Int` immediately followed by a
        literal `":"` (the quantifier/comprehension separator is the
        two-character `"::"`, a different token)."""
        if (self.cur.kind in ("id", "int")
                and self.tokens[self.pos + 1].text == ":"):
            self.advance()
            self.advance()

    def _parse_fspec_list(self) -> list:
        specs = []
        while True:
            line = self.cur.line
            if self.at("requires"):
                self.advance()
                self._skip_clause_label()
                specs.append(RequiresClause(line, self.parse_expr()))
            elif self.at("ensures"):
                self.advance()
                self._skip_clause_label()
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
                self._skip_clause_label()
                specs.append(RequiresClause(line, self.parse_expr()))
            elif self.at("ensures"):
                self.advance()
                self._skip_clause_label()
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
                self._skip_clause_label()
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
            args = ()
            # The element type is optional (bare "set", "seq"): Dafny
            # infers it. Measured (section 18.2): "predicate
            # IsSubset(A: set, B: set)", "lemma Lemma_1(Seq_1: seq, ...)".
            if self.at("<"):
                self.advance()
                args = (self.parse_type(),)
                self._expect_gt()
            return Type(line, kind=tok.text, args=args)
        if tok.text in ("map", "imap"):
            self.advance()
            args = ()
            if self.at("<"):
                self.advance()
                k = self.parse_type()
                self.expect(",")
                v = self.parse_type()
                self._expect_gt()
                args = (k, v)
            return Type(line, kind=tok.text, args=args)
        if tok.text in ("array", "array?"):
            nullable = tok.text.endswith("?")
            self.advance()
            args: tuple[Type, ...] = ()
            if self.at("<"):
                self.advance()
                args = (self.parse_type(),)
                self._expect_gt()
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
            # A module-qualified type name ("Code.Variables", "T.C"):
            # section 3's Type production has no "." form, but rprint
            # always fully qualifies a type from another module. Folded
            # into one dotted name string; `lift_classify.py` sees the
            # same "T.C" it would see unqualified.
            while self.at(".") and self.tokens[self.pos + 1].kind == "id":
                self.advance()
                name = f"{name}.{self.expect_ident()}"
            args = ()
            if self.at("<"):
                self.advance()
                items = [self.parse_type()]
                while self.at(","):
                    self.advance()
                    items.append(self.parse_type())
                self._expect_gt()
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

        if self.at("match"):
            # `match Expr (Case)+` or `match Expr { (Case)* }`: section 3
            # has no Match node at all (`lift_ast.py` carries none), so
            # this always names the census's own `datatype` gap rather
            # than falling through and reporting some confusing token
            # deep inside the match subject or its first case pattern
            # (measured: the subject's own first token -- "l", "xs", "t",
            # "n", a case-value identifier -- was the token every one of
            # the 154 parse-refusal "match" files reported before this).
            raise LiftParseError("match", line, "match statement", reason="datatype")
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
            self._skip_clause_label()
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

        if tok.kind == "id" and self.tokens[self.pos + 1].text == "<":
            # A call with explicit type arguments as its own statement
            # ("PrintArray<int>(null);"): CallStmt has only a bare `Id
            # "(" ... ")"` shape (no field for type arguments), so on
            # confirming this really is one (a Dafny statement can never
            # otherwise open "Id <"), the type arguments are parsed and
            # dropped rather than kept. Backtracks to the ordinary lhs
            # path below on anything that is not this exact shape (a
            # relational "a < b" used as, e.g., an argument is never a
            # full statement by itself, so no real statement is lost).
            save = self.pos
            name = self.advance().text
            self.advance()  # "<"
            ok = True
            try:
                self.parse_type()
                while self.at(","):
                    self.advance()
                    self.parse_type()
                ok = self.at(">")
            except LiftParseError:
                ok = False
            if ok:
                self.advance()  # ">"
                ok = self.at("(")
            if ok:
                self.advance()  # "("
                args = self._parse_expr_list_until(")")
                self.expect(")")
                self.expect(";")
                return CallStmt(line, name, tuple(args))
            self.pos = save

        lhss = [self._parse_lhs()]
        while self.at(","):
            self.advance()
            lhss.append(self._parse_lhs())
        if self.at(":|") and all(l.kind == "name" for l in lhss):
            # `Lhs (","Lhs)* ":|" Expr ";"` -- the such-that form without
            # a leading "var" (re-binding an already-declared local:
            # "p :| p in m;"). Section 3's grammar only has the "var"
            # form; `lift_ast.AssignSuchThat` needs only names, which a
            # bare re-assignment already has, so no AST change is needed.
            # Always `such-that-exec` downstream regardless of this
            # spelling.
            self.advance()
            cond = self.parse_expr()
            self.expect(";")
            names = tuple(Param(l.line, l.name, None, False) for l in lhss)
            return AssignSuchThat(line, names, cond)
        if self.at("("):
            # A call statement on a dotted or indexed receiver
            # ("cm.Restock();", "carPark.closeCarPark();", "aa[j,
            # k].Foo();"): section 3's CallStmt is only `Id "(" ... ")"
            # ";"`, and lift_ast.CallStmt keeps no receiver, so this is
            # always a heap-object method call the AST cannot represent
            # rather than a bare-token parse-failure.
            raise LiftParseError("(", self.cur.line,
                                  "call on a dotted or indexed receiver",
                                  reason="heap")
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
        if self.at("("):
            # A tuple-destructuring declaration ("var (c: int, r: int) :=
            # argmax(radii, 0);"): `VarDeclStmt.names` is a flat `Param`
            # tuple with no way to say "these came from one destructured
            # value", so this is named `tuple` (the construct actually
            # in play) instead of failing later on the first ":" inside
            # the parens.
            raise LiftParseError("(", line, "tuple-destructuring var",
                                  reason="tuple")
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
        if self.at("{") or self.at("case"):
            # rprint sometimes omits the wrapping "{" "}" around an
            # if-case block entirely (measured, Clover_canyon_search.dfy:
            # "if\ncase a[m] <= b[n] =>\n  m := m + 1;\ncase ... =>\n  n
            # := n + 1;" with no braces at all, the case list simply
            # ending where the enclosing block's own "}" does).
            # `_parse_case_block` already stops on either "case" running
            # out or a "}", so the same call serves both spellings.
            braced = self.at("{")
            if braced:
                self.advance()
            cases = self._parse_case_block()
            if braced:
                self.expect("}")
            return IfCaseStmt(line, tuple(cases))
        if self.cur.kind == "id" and self.tokens[self.pos + 1].text == ":":
            # A binding-guard if ("if i: int, j: int {:trigger ...} :| 0
            # <= i < j < a.Length && a[i] > a[j] { ... }"): the guard is
            # an existential witness binding, not a boolean Expr at all
            # (no Expr production starts "Id ':'", same non-ambiguity as
            # a clause label). No AST node models a binding guard, so
            # this is named `such-that-exec` directly; the block after
            # ":|" is still walked (never left unconsumed) even though
            # its statements are discarded with the refusal.
            self._parse_binders()
            self._parse_attrs()
            self.expect(":|")
            self.parse_expr()
            self.parse_block()
            raise LiftParseError(":|", line, "if binding guard",
                                  reason="such-that-exec")
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
        if self.at("{") or self.at("case"):
            braced = self.at("{")
            if braced:
                self.advance()
            cases = self._parse_case_block()
            if braced:
                self.expect("}")
            return WhileCaseStmt(line, (), tuple(cases))
        cond: Union[Expr, Star]
        if self.at("*"):
            cond = Star(self.cur.line)
            self.advance()
        else:
            cond = self.parse_expr()
        specs = self._parse_loopspec_list()
        if self.at("{"):
            body = self.parse_block()
        else:
            # A non-block single-statement body ("while r >= d invariant
            # ... decreases r - d\n  r := r - 1;" -- measured,
            # Programmverifikation-...-Hoangkim.dfy: the source itself
            # never opens a "{" for this loop at all, so dafny's own
            # grammar accepts a bare Stmt here same as an "if"/"for"
            # guard would; wrapped as the one-element block
            # `lift_ast.WhileStmt.body` already expects).
            body = (self.parse_stmt(),)
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
                if self.at(","):
                    # array2/array3 assignment ("m3[i, j] := 0;"): same
                    # multi-index fold into one TupleExpr as the
                    # expression-position Index above, for the same
                    # reason (always refused `array` once the base's
                    # `array<T>` type is seen, however it was indexed).
                    idxs = [idx]
                    while self.at(","):
                        self.advance()
                        idxs.append(self.parse_expr())
                    self.expect("]")
                    idx = TupleExpr(line, tuple(idxs))
                    if self.at("[") or self.at("."):
                        base = Index(line, base, idx)
                        continue
                    return Lhs(line, kind="index", base=base, index=idx)
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

    def _at_disjoint_op(self) -> bool:
        """Set/multiset disjointness ("A !! B") is two adjacent "!"
        tokens in a binary-operator position. It is deliberately not
        lexed as one "!!" token: that would also swallow a legitimate
        double negation ("!!p", section 18.2), which only ever appears
        at the START of a Unary, never here after a full Add-level
        operand has already been parsed -- the two spellings never
        collide because they are only ever checked in these two
        different parser positions."""
        return self.cur.text == "!" and self.tokens[self.pos + 1].text == "!"

    def _parse_rel(self) -> Expr:
        left = self._parse_add()
        ops = []
        operands = [left]
        while self.cur.text in RELOPS or self._at_disjoint_op():
            line = self.cur.line
            if self._at_disjoint_op():
                self.advance()
                self.advance()
                ops.append("!!")
            else:
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
        # "<<"/">>" (shift) and "&"/"^" (bitwise and/xor) are bitvector
        # operators with no dedicated precedence tier in section 3's
        # grammar; t has no bitvector, so exact precedence among them
        # never affects a lift outcome (the method around them is always
        # refused `bitvector` once its `bv` type is seen). Folded into
        # this tier so the operators are at least tokenised into a
        # well-formed AST instead of stalling the parse.
        while self.cur.text in ("*", "/", "%", "<<", ">>", "&", "^"):
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
                    elif self.at(","):
                        # array2/array3 indexing ("a[i, j]"): Index has
                        # one `index` field, so the comma-separated
                        # indices are folded into one TupleExpr the same
                        # way a parenthesised tuple would be, purely so
                        # this parses; downstream already refuses any
                        # `array<T>`-typed value regardless of how it was
                        # indexed (section 18.6: "array2 ... stay refused
                        # `array`").
                        idxs = [first]
                        while self.at(","):
                            self.advance()
                            idxs.append(self.parse_expr())
                        self.expect("]")
                        atom = Index(line, atom, TupleExpr(line, tuple(idxs)))
                    else:
                        self.expect("]")
                        atom = Index(line, atom, first)
            elif self.at("."):
                self.advance()
                if self.at("("):
                    # A datatype update expression ("v.(f := e)",
                    # "k.(0 := 100, c3 := 200)"): section 3's Primary
                    # postfix set has no such form, and lift_ast has no
                    # dedicated update node, so it is named `datatype`
                    # right here instead of falling through to
                    # `expect_ident` raising a bare-token failure on the
                    # "(" itself.
                    raise LiftParseError("(", self.cur.line,
                                          "datatype update expression",
                                          reason="datatype")
                if self.cur.kind == "int":
                    # Tuple field projection ("iv.0", "pair.1"): Primary's
                    # "." postfix only names an Id (a field/destructor);
                    # `Member.name` is already a bare string, so an
                    # integer index reuses it unchanged.
                    name = self.advance().text
                else:
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

    def _parse_let(self, line: int) -> LetExpr:
        """Dafny's let expression (Reference Manual 9.31.7, grammar
        17.2.7.39, dafny.org/latest/DafnyRef/DafnyRef#sec-let-expression):
        `["ghost"] "var" CasePattern {"," CasePattern} (":=" | ":-" |
        {Attribute} ":|") Expression {"," Expression} ";" Expression`.

        A CasePattern here is a binder, `Id [":" Type]` (rprint prints the
        type it inferred: "var m: real := mean(numbers); ..."). A tuple
        pattern ("var (a: int, b: int) := pos[i]; ...", 14 of the 432
        let-refused files of 2026-09-26) or a datatype pattern ("var
        SCons(u, v) := z; ...") binds through a destructor this AST has no
        node for, so it is refused by name, `let-pattern`, here. Everything
        else becomes a `LetExpr`; whether it lifts (":=" substitutes, ":|"
        and ":-" are refused by name) is `lift_classify`'s decision, made
        per method on its own closure, never for the whole file.

        The body is a full `parse_expr()`: like a quantifier's, it extends
        as far right as the text allows ("0 <= i ==> var x := s[i]; x > 0
        && x < 9" binds x over the whole conjunction)."""
        ghost = False
        if self.at("ghost"):
            self.advance()
            ghost = True
        self.expect("var")
        binders: list[Param] = []
        while True:
            if self.at("(") or (self.cur.kind == "id"
                                and self.tokens[self.pos + 1].text == "("):
                raise LiftParseError(self.cur.text, self.cur.line,
                                      "tuple or datatype pattern in a let expression",
                                      reason="let-pattern")
            bline = self.cur.line
            name = self.expect_ident()
            btype = None
            # ":" then "-" is the let-or-fail operator ":-" (lexed as two
            # tokens), never a type: no Type starts with "-".
            if self.at(":") and self.tokens[self.pos + 1].text != "-":
                self.advance()
                btype = self.parse_type()
            binders.append(Param(bline, name, btype, False))
            if not self.at(","):
                break
            self.advance()
        self._parse_attrs()  # `{:attr} :|`: recorded nowhere, like every attribute
        if self.at(":="):
            op = ":="
            self.advance()
        elif self.at(":|"):
            op = ":|"
            self.advance()
        elif self.at(":") and self.tokens[self.pos + 1].text == "-":
            op = ":-"
            self.advance()
            self.advance()
        else:
            raise LiftParseError(self.cur.text or "<eof>", self.cur.line,
                                  f"expected ':=', ':|' or ':-' in a let expression, "
                                  f"found {self.cur.text!r}")
        rhs = [self.parse_expr()]
        while self.at(","):
            self.advance()
            rhs.append(self.parse_expr())
        self.expect(";")
        body = self.parse_expr()
        return LetExpr(line, ghost, tuple(binders), op, tuple(rhs), body)

    def _parse_atom(self) -> Expr:
        tok = self.cur
        line = tok.line
        if tok.text == "match":
            # `match Expr { case ... }` used as an expression (a function
            # or predicate body, or nested in one): same construct as the
            # statement form, same reason.
            raise LiftParseError("match", line, "match expression", reason="datatype")
        if tok.text == "null":
            # The heap null literal: section 3's Atom has no such literal
            # (t has no heap, so no reference type ever needs one), and
            # lift_ast has no NullLit node. Read as a plain Ident so a
            # method that merely passes `null` to an already-refused
            # heap-object call (its only measured use, section 18.2)
            # still parses; nothing downstream binds an identifier named
            # "null" to anything, so it can never be mistaken for a real
            # local.
            self.advance()
            return Ident(line, "null")
        if tok.text == "var" or (tok.text == "ghost"
                                  and self.tokens[self.pos + 1].text == "var"):
            return self._parse_let(line)
        if tok.text == ":" and self.tokens[self.pos + 1].text == "-":
            # The bare let-or-fail form ":- E; body" (grammar 17.2.7.39's
            # second alternative): no binder, a failure-compatible datatype
            # on the right. Named for what it is.
            raise LiftParseError(":-", line, "let-or-fail expression",
                                  reason="let-or-fail")
        if tok.text in ("assert", "assume", "expect", "reveal", "calc"):
            # A statement before an expression ("assert x != 0; 10 / x",
            # Reference Manual 9.31.6): these are keywords, never names, so
            # the construct is known here, at its first token.
            raise LiftParseError(tok.text, line, "statement in an expression",
                                  reason="stmt-in-expression")
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
            if self.at("@"):
                # A labeled old ("old@L(a[..])"): section 3's Atom only
                # has plain "old" "(" Expr ")", and `lift_ast.Old` has no
                # field for the label, so silently dropping it would
                # change WHICH program point the value comes from -- a
                # real semantic difference, not a droppable hint. Named
                # `old` (the construct's own census key) rather than
                # risked as a silent misreading.
                raise LiftParseError("@", self.cur.line, "labeled old",
                                      reason="old")
            self.expect("(")
            e = self.parse_expr()
            self.expect(")")
            return Old(line, e)
        if tok.text == "new":
            # "new" as a plain expression ("return new A[rows, cols]
            # ((x: nat, y: int) => ...);"): section 3 only allows "new"
            # in Rhs position (an assignment/var-decl initialiser), not
            # as a general Expr/Atom, and a fresh heap allocation is
            # exactly the `heap` construct regardless of where it turns
            # up.
            raise LiftParseError("new", line, "new as an expression",
                                  reason="heap")
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
            self._check_hint_chain_semicolon()
            self.expect("else")
            # No hint-chain check after the "else" arm: a ";" there may be
            # the enclosing statement's own terminator (see
            # `_check_hint_chain_semicolon`).
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
            if self.at("("):
                # `seq(n, (i: int) requires 0 <= i <= n => body)`: the
                # generator is a full lambda literal (typed parameter,
                # optional "requires"), not the bare-Id shorthand below --
                # the same `higher-order` construct as any other lambda.
                raise LiftParseError("(", self.cur.line,
                                      "seq generator lambda",
                                      reason="higher-order")
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
            # A lambda literal ("(n: int, m: int) => n >= m", "(i: int)
            # requires 0 <= i <= n => Power10(i)") looks exactly like a
            # parenthesised expression or tuple display up to its closing
            # ")" -- the two are told apart only by what follows. Section
            # 3's Atom has no lambda production at all (lift_ast has no
            # Lambda node), so on confirming the shape, this is named
            # `higher-order` before the tuple-display path below ever
            # tries to parse the parameter list as expressions and fails
            # confusingly on the first ":".
            save = self.pos
            self.advance()
            ok = True
            try:
                if not self.at(")"):
                    self._parse_params()
                ok = self.at(")")
            except LiftParseError:
                ok = False
            if ok:
                self.advance()  # ")"
                ok = self.at("=>") or self.at("requires")
            if ok:
                tail_tok, tail_line = self.cur.text, self.cur.line
                self.pos = save
                raise LiftParseError(tail_tok, tail_line, "lambda literal",
                                      reason="higher-order")
            self.pos = save
            self.advance()  # "("
            if self.at(")"):
                self.advance()
                return TupleExpr(line, ())
            elems = [self.parse_expr()]
            self._check_hint_chain_semicolon()
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
    try:
        decls = parser.parse_module_decls()
    except LiftParseError as e:
        # Section 18.2: a refusal names the construct in the census's
        # vocabulary where one exists, never a bare token. A file that
        # declares a bitvector type and then stalls the parse is a
        # `bitvector` refusal whatever token it stalled on.
        #
        # `|` is the case that made this necessary. The other bitvector
        # operators (`<<`, `>>`, `&`, `^`) are folded into `_parse_mul` so
        # they at least tokenise, but `|` cannot join them: it is also the
        # cardinality bracket `|s|`, and giving it a binary tier would
        # break every sequence length in the corpus. Naming the refusal is
        # the fix the design asks for; widening the grammar is not.
        # Measured 2026-09-06: dafny-synthesis_task_id_799.dfy, token `|`
        # at rprint line 122, source `(n << d) | (n >> (32 - d))` over
        # `bv32`, the one file in the 785 still reading `parse-failure`.
        if e.reason == "parse-failure" and _declares_bitvector(text):
            raise LiftParseError(e.token, e.line, str(e),
                                 reason="bitvector") from None
        raise
    return Module(decls=tuple(decls), call_graph=call_graph, source_path=None)


def _declares_bitvector(text: str) -> bool:
    """True when the rprint says the file uses a bitvector type.

    Two witnesses, either sufficient: dafny's own preamble line, and a
    `bv<N>` type written in a declaration. The preamble line alone is not
    enough because `print_dafny`'s output (the section 10(b) fixpoint feeds
    it back through here) does not reproduce the preamble."""
    if "bitvector types in use" in text:
        return True
    return re.search(r"\bbv\d+\b", text) is not None


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
    if isinstance(e, LetExpr):
        # Parenthesised like every compound: a let's body runs as far right
        # as it can, so an unbracketed one would swallow what follows it.
        g = "ghost " if e.ghost else ""
        binders = ", ".join(_print_param(b) for b in e.binders)
        rhs = ", ".join(_print_expr(r) for r in e.rhs)
        return f"({g}var {binders} {e.op} {rhs}; {_print_expr(e.body)})"
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
