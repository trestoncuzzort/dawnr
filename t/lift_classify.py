"""Classify one gradable method: refuse it (naming a section-5 reason and
the offending rprint line) or mark it liftable with the rewrite list
`lift_rewrite.py` must apply.

Reads LIFTER-DESIGN.md sections 4 (mapping rules -- what a rewrite IS),
5 (refusal rules -- the reason vocabulary and trigger table), 6 (decreases
inference -- when a loop/spec_fun's measure is uninferable), 7 (nat
handling -- when a nat parameter/return/local forces a refusal vs. an
added clause), 18.2 (the rewrite-vocabulary cross-reference), 18.6 (the
read-only-array-as-seq row), and LIFTER-DECISIONS.md whole (it overrides
the design wherever they differ, notably decision 1: read-only
`array<int>` lifts to `seq` rather than refusing). Also reads
`fuzz_lower.check_wf`'s shape (this module never calls it -- `lift_check
.py` does, post-rewrite -- but the rewrite list this module plans must be
achievable in a task that will pass it) and SYNTAX.md's reserved words
(`surface.py`'s KEYWORDS / a lowering's RESERVED set, for `name
-unsanitisable`/renaming decisions, decision-file row 8's neighbourhood).

Architecture role (LIFTER-DESIGN.md section 2's table, copied verbatim):
    input: Dafny AST
    output: per method: the refusal reason (section 5) or a "liftable"
            mark with the rewrite list
    MAY decide: the refusal reason from the census vocabulary plus
                section 5's additions
    MAY NOT decide: any rewrite

That last line is section 2's own word, and it is deliberately narrow:
this module decides WHETHER each section-4 rewrite rule fires (by
inspecting the AST and recording the rule id and line) but never performs
one -- it plans the list `lift_rewrite.py` executes to the letter,
producing no t syntax and touching no source clause itself.

SHARED HELPERS. `lift_rewrite.py` is this module's sibling (both are owned
by the same implementer, per the interfaces contract) and imports several
private helpers from here (the leading-underscore names) rather than
re-deriving the same AST analysis a second time: the call-graph closure,
the generic `walk` visitor, the type-acceptability check, the quantifier
bound extractor, the tail-return scan, and the read-only-array condition.
`classify` decides WHETHER a rule fires; `rewrite` (in the sibling module)
performs it, using the same detectors so the two never disagree about what
the AST contains.

KNOWN SHIM LIMITATIONS (documented here since this module is the one where
the gap first bites): `lift_parse.py` is still a stub (NotImplementedError)
as of this writing, so this module was developed and tested against a
hand-written parser shim living in `test_lift_rules.py` (never imported
here -- this module only ever touches `lift_ast` node types, exactly per
its contract). Two consequences worth naming: (1) section 4.8's renaming
check uses only the keyword list section 4.8 gives verbatim (t's own
KEYWORDS, "main", "t_refutation_certificate") plus the deterministic rename
rule; it does NOT check lower_fstar.py/lower_rocq.py/lower_spark.py's own
RESERVED sets, since reading those files was outside this task's assigned
reading list. (2) `decreases_origin`'s "stated" vs. "rprint-inferred" label
is a best-effort pattern match against section 6's own documented inferred
shapes (`hi - lo`, `hi - 0`, the `!=`-guard `ite`); it can only be exact
when `lift_resolve.py` eventually threads the ORIGINAL (pre-resolution)
print text through so the two can be diffed -- an input this module's
fixed signature does not currently receive. Neither limitation can corrupt
a lifted value: both are provenance/bookkeeping labels, not part of the
theorem the checker (`lift_check.py`) verifies.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field
from typing import Iterator, Optional

from lift_ast import (
    Assign, AssignSuchThat, AssertStmt, AssertByStmt, AssumeStmt, Binary,
    BlockStmt, BoolLit, BreakStmt, Call, CallStmt, CalcStmt, Cardinality,
    Cast, Chain, CharLit, ContinueStmt, Decl, DecreasesClause, EnsuresClause, Expr,
    ExpectStmt, ForStmt, ForallStmt, FunctionDecl, Fresh, Iff, IfCaseStmt,
    IfExpr, IfStmt, Implies, Index, Ident, IntLit, InvariantClause,
    LabelStmt, LemmaDecl, Lhs, MapDisplay, Member, MethodDecl,
    ModifiesClause, Module, NaryBool, NewRhs, Node, Old, Param, PrintStmt,
    Quantifier, ReadsClause, Refusal, RequiresClause, RevealStmt,
    ReturnStmt, Rewrite, SeqDisplay, SeqUpdate, SetDisplay, SkippedDecl,
    Slice, Spec, Star, Stmt, StringLit, TupleExpr, Type, TypeTest, Unary,
    VarDeclStmt, WhileCaseStmt, WhileStmt, Comprehension,
)


# ---------------------------------------------------------------------------
# Generic AST walker. Every lift_ast node is a dataclass, so one visitor
# serves every node type: yield the node itself, then recurse through its
# dataclass fields (tuples/lists/dicts unwrapped, scalars ignored). Section
# 5's refusal rows are overwhelmingly "does construct X appear anywhere in
# the method's (or its closure's) reach" -- this makes each such row a
# one-line `isinstance` filter over `walk(...)` instead of a bespoke visitor.
# ---------------------------------------------------------------------------

def walk(obj) -> Iterator[Node]:
    if obj is None:
        return
    if isinstance(obj, Node):
        yield obj
        for f in dataclasses.fields(obj):
            yield from walk(getattr(obj, f.name))
    elif isinstance(obj, (tuple, list)):
        for item in obj:
            yield from walk(item)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk(k)
            yield from walk(v)
    # else: str/int/bool/None -- a leaf, nothing to recurse into.


def _line(n: Node) -> int:
    return getattr(n, "line", 0)


# ---------------------------------------------------------------------------
# Section 4.8's keyword union, verbatim from the design text (the design
# names surface.py's KEYWORDS list inline; see module docstring for why the
# other three lowerings' RESERVED sets are not checked here).
# ---------------------------------------------------------------------------

T_KEYWORDS = {
    "t", "gate", "task", "returns", "requires", "ensures", "decreases",
    "spec", "fun", "var", "while", "invariant", "if", "then", "else",
    "forall", "exists", "in", "len", "true", "false", "and", "or", "not",
    "int", "bool", "seq",
}
RESERVED_EXTRA = {"main", "t_refutation_certificate"}


# ---------------------------------------------------------------------------
# Types.
# ---------------------------------------------------------------------------

def _is_nat(t: Optional[Type]) -> bool:
    return t is not None and t.kind == "nat"


def _is_int_like(t: Optional[Type]) -> bool:
    return t is not None and t.kind in ("int", "nat")


def _is_bool(t: Optional[Type]) -> bool:
    return t is not None and t.kind == "bool"


def _is_seq_of_int(t: Optional[Type]) -> bool:
    return (t is not None and t.kind == "seq" and len(t.args) == 1
            and _is_int_like(t.args[0]))


def _is_seq_of_nat(t: Optional[Type]) -> bool:
    return (t is not None and t.kind == "seq" and len(t.args) == 1
            and _is_nat(t.args[0]))


def _is_char(t: Optional[Type]) -> bool:
    return t is not None and t.kind == "char"


def _is_seq_of_char(t: Optional[Type]) -> bool:
    # Row 28 (2026-09-09, SPEC.md "Strings as sequences of code points
    # (v1)"): `seq<char>` written that way is `string` by another name
    # ("string of anything nested is not", the task's own words) -- one
    # level of char elements only, the same one-level rule
    # `_is_seq_of_int`/`_is_seq_of_nat` already carry.
    return (t is not None and t.kind == "seq" and len(t.args) == 1
            and _is_char(t.args[0]))


def _is_array_of_int(t: Optional[Type]) -> bool:
    return (t is not None and t.kind == "array" and not t.nullable
            and len(t.args) == 1 and _is_int_like(t.args[0]))


def _type_issue(t: Optional[Type]) -> Optional[str]:
    """Section 4.2's type table, as a refusal reason or None when the type
    is one this lifter can carry (int/nat/bool/seq<int|nat|char>/char/
    string -- row 28, 2026-09-09: a char is a t int and a string a t seq,
    so neither refuses on its type alone here any more; what still
    refuses about them needs the method's own scope, not a bare `Type`
    node, and lives in `classify`'s own dedicated pass, see that row's
    own comment there). Array is handled by the caller separately (it
    needs a whole-closure usage check, decision 1 / section 18.6, not a
    local type test)."""
    if t is None:
        return "untyped-var"
    if t.kind in ("int", "nat", "bool"):
        return None
    if t.kind == "seq":
        if _is_seq_of_nat(t):
            # decision 14: `seq<nat>`'s element bound is part of the
            # source's precondition exactly as a `nat` parameter's is
            # (section 7); the lifter carries no per-element guard for a
            # bare `seq`, so this is refused rather than silently widened.
            return "nat-seq-elements"
        if len(t.args) == 1 and (_is_int_like(t.args[0]) or _is_char(t.args[0])):
            # Row 28: `seq<char>` is `string` written another way (SPEC.md
            # "Strings as sequences of code points (v1)"), so it carries
            # here exactly as `seq<int>` already does.
            return None
        return "nested-seq"
    if t.kind == "array":
        return "array"
    if t.kind in ("array2", "array3"):
        return "array"
    if t.kind == "real":
        return "real"
    if t.kind in ("char", "string"):
        # Row 28 (2026-09-09, SPEC.md "Strings as sequences of code
        # points (v1)"): a Dafny `char` is a t int (its own code point),
        # a `string` a t `seq` of them -- the same type the lifter
        # already gives `seq<int>` -- so neither refuses on its type
        # alone any more (`string-char` used to be raised here
        # unconditionally). What still refuses is narrower and lives in
        # the dedicated pass below (`char-arith`, `char-cast-unbounded`,
        # `string-lib`, `char-literal-nonbmp`), which needs the method's
        # own scope to decide, not a bare `Type` node.
        return None
    if t.kind == "set" or t.kind == "iset":
        return "set"
    if t.kind in ("map", "imap"):
        return "map"
    if t.kind == "tuple":
        return "tuple"
    if t.kind == "bv":
        return "bitvector"
    if t.kind == "object":
        return "heap"
    if t.kind == "func":
        return "higher-order"
    if t.kind == "id":
        return "generics" if t.args else "datatype"
    return "type-decl"


def _pair_component_issue(t: Optional[Type]) -> Optional[str]:
    """Row 29 (2026-09-09, SPEC.md "Pairs (v1)"): is `t` one of the
    component types t's v1 pair construct carries -- "each of T1, T2
    one of int, bool, seq" (a `nat` is an `int` with decision 4's own
    non-negativity ensures added; a `string`/`seq<char>` is a `seq` per
    row 28)? `None` means yes; a bare `char` is deliberately NOT
    accepted here (row 28 only ever folds it into `int` for a SINGLE
    return's own `t_ret`, and doing the same for a pair component needs
    a guard stated on the PROJECTION, `r.0`/`r.1`, not the return
    itself -- narrowed out of this row's own scope, see
    LIFTER-DECISIONS.md row 29's residual list), nor is an
    `array<int>`/`array<nat>` component (row 22's alloc-fill/modifies-
    param machinery is built around exactly ONE return; combining it
    with a second, independent component is also narrowed out). Both
    are refused `multi-return-nested` by the caller, the same token a
    nested seq or a genuine Dafny tuple component gets."""
    if t is None:
        return "untyped-var"
    if t.kind in ("int", "nat", "bool", "string"):
        return None
    if t.kind == "seq":
        if _is_seq_of_int(t) or _is_seq_of_nat(t) or _is_seq_of_char(t):
            return None
        return "nested-seq"
    return "unsupported"


# ---------------------------------------------------------------------------
# Rows 25-27 (2026-09-09, SPEC.md "Sequences: literals, concatenation,
# slices (v1)"): a small, best-effort, non-flow-sensitive "int" | "bool" |
# "seq" kind inference, needed only to settle three questions -- a `+`'s
# two operands, a slice's receiver, a literal's own elements -- never a
# full type checker (Dafny already type-checked the source; where this
# cannot settle a kind, the caller refuses `seq-typing` rather than
# guess). `expr_kind` is the one shared computation (`scan_breaks`'s
# pattern): `classify` calls it with a plain dict's `.get` (`_build_kind
# _env`, static declared-type knowledge only); `lift_rewrite.rewrite`
# calls it with a small wrapper over its own live `Scope` (`_rw_lookup`
# there), consulted only to decide whether a `+` gets recorded `seq
# -concat-lifted` -- never to accept or refuse anything, that is this
# module's decision alone, already settled by the time rewrite runs.
# ---------------------------------------------------------------------------

def _declared_kind(t: Optional[Type]) -> Optional[str]:
    """The static half of `expr_kind`'s question: a parameter's, return's
    or local's OWN declared type, read as `int`/`bool`/`seq` wherever
    rows 25-27 can use it. `None` for anything this row does not resolve
    (an untyped local -- its initialiser is the only other source of a
    kind, `expr_kind` itself -- or a seq element type this row does not
    carry, already refused `nat-seq-elements`/`nested-seq` elsewhere by
    `_type_issue`, whether or not this function also happens to call it
    seq). `nat` reads as `int`: t tracks no separate nat-ness at this
    grain, decision 4/14's own territory, not this row's."""
    if t is None:
        return None
    if t.kind == "bool":
        return "bool"
    if t.kind in ("int", "nat"):
        return "int"
    if t.kind == "char":
        # Row 28: a char IS its code point, one t int; this row's
        # int/bool/seq vocabulary has no separate "char" kind (a
        # +/-'s char-ness is `_is_char_expr`'s own, narrower question,
        # below, needed only where the distinction actually matters).
        return "int"
    if t.kind == "seq" and len(t.args) == 1 and (_is_int_like(t.args[0]) or _is_char(t.args[0])):
        return "seq"
    if t.kind == "string":
        return "seq"  # row 28: string is seq<int> by another name
    if t.kind == "array" and not t.nullable and _is_array_of_int(t):
        return "seq"
    return None


def expr_kind(e: Expr, lookup) -> Optional[str]:
    """Best-effort `int`/`bool`/`seq` kind of `e`. `lookup(name)` resolves
    an `Ident` (or a `Call`'s callee) to its known kind, `None` when
    unknown -- see the section banner above for who passes what."""
    if isinstance(e, IntLit):
        return "int"
    if isinstance(e, BoolLit):
        return "bool"
    if isinstance(e, CharLit):
        return "int"  # row 28: a char literal is its code point
    if isinstance(e, StringLit):
        return "seq"  # row 28: a string literal is the seq literal of code points
    if isinstance(e, Ident):
        return lookup(e.name)
    if isinstance(e, Old):
        return expr_kind(e.arg, lookup)
    if isinstance(e, SeqDisplay):
        return "seq"
    if isinstance(e, Slice):
        return "seq"
    if isinstance(e, Unary):
        return "bool" if e.op == "!" else "int"
    if isinstance(e, Binary):
        if e.op == "+":
            lk = expr_kind(e.left, lookup)
            rk = expr_kind(e.right, lookup)
            if lk == "seq" and rk == "seq":
                return "seq"
            if lk == "int" and rk == "int":
                return "int"
            return None
        return "int"  # `- * / %`: t has none of these on seq
    if isinstance(e, (NaryBool, Implies, Iff, Chain, Quantifier)):
        return "bool"
    if isinstance(e, Index):
        return "int"
    if isinstance(e, Cardinality):
        return "int"
    if isinstance(e, Member):
        return "int"  # `.Length`; anything else is refused `datatype` elsewhere
    if isinstance(e, IfExpr):
        tk, ek = expr_kind(e.then, lookup), expr_kind(e.else_, lookup)
        return tk if tk == ek else None
    if isinstance(e, Call) and isinstance(e.fn, Ident):
        return lookup(e.fn.name)
    return None


def _closure_fn_kinds(method: MethodDecl, closure: tuple[Decl, ...]) -> dict[str, str]:
    """dafny name -> kind for every `Call` `expr_kind` might need to
    resolve: the method's own name (a self-recursive call, section 4.5),
    keyed to its own return's kind, and every closure function's own
    declared return (a `predicate`'s is implicitly `bool`). Anything
    this cannot resolve (a call of a DIFFERENT method, already refused
    `calls-other-method` elsewhere) is simply absent."""
    kinds: dict[str, str] = {}
    if method.name and len(method.returns) == 1:
        k = _declared_kind(method.returns[0].type)
        if k is not None:
            kinds[method.name] = k
    for d in closure:
        if isinstance(d, FunctionDecl) and d.name:
            k = "bool" if d.is_predicate else _declared_kind(d.ret_type)
            if k is not None:
                kinds[d.name] = k
    return kinds


def _build_kind_env(method: MethodDecl, closure: tuple[Decl, ...]) -> dict[str, str]:
    """Name -> `int`/`bool`/`seq` for rows 25-27's own questions: every
    parameter and the one return by declared type (the method's own and
    every closure function's -- a `+`/slice/literal can sit inside a
    spec_fun's body too, `classify`'s own `scope_roots` reaches both),
    every closure function/the method's own name by `_closure_fn_kinds`,
    every local the body declares -- by its own declared type where
    given, else `expr_kind` of its initialiser (so `var t := s + [x];`
    types `t` `seq` from its own right-hand side, recursively) -- and
    every quantifier binder / `for`-loop variable, by ITS declared type
    or else `int` (section 6's own quantifier-boundedness and decision
    15's `for`-loop rows both restrict this lifter to int/nat binders,
    so `int` is never a guess here, only a name this row would otherwise
    see as `None` and wrongly refuse `seq-typing` on -- measured:
    `forall i :: ... ==> r[|s| + i] == a[i]`'s `|s| + i` is plain int
    arithmetic over a quantifier binder, not a `+` this row should ever
    touch). A flat, block-scope-blind forward pass over `walk`'s own
    traversal order: Dafny already block-scopes and type-checked the
    source, and this row only ever needs a best-effort answer, refusing
    `seq-typing` when it truly has none, never a wrong kind silently
    accepted. `setdefault` throughout: an outer param/return/local name
    a quantifier binder or `for`-var happens to share is not clobbered
    by the (rare) shadowing case, the more common reading kept."""
    env: dict[str, str] = dict(_closure_fn_kinds(method, closure))
    for p in method.params:
        k = _declared_kind(p.type)
        if k is not None:
            env[p.name] = k
    for r in method.returns:
        # Row 29 (2026-09-09): a pair method's TWO out-parameters need
        # their own kind here exactly as a single return's own does --
        # `a`/`b` appear as plain body-local reads/writes and as the
        # `+`/slice operands rows 25-27 already resolve through this
        # env, unrelated to that row's own `r.0`/`r.1` ensures
        # projection, which is `lift_rewrite`'s concern, not this one's.
        k = _declared_kind(r.type)
        if k is not None:
            env[r.name] = k
    for d in closure:
        if isinstance(d, FunctionDecl):
            for p in d.params:
                k = _declared_kind(p.type)
                if k is not None:
                    env.setdefault(p.name, k)
    for root in [method] + list(closure):
        for n in walk(root):
            if isinstance(n, VarDeclStmt):
                if n.init:
                    for nm, rhs in zip(n.names, n.init):
                        k = _declared_kind(nm.type)
                        if k is None and isinstance(rhs, Expr):
                            k = expr_kind(rhs, env.get)
                        if k is not None:
                            env[nm.name] = k
                else:
                    for nm in n.names:
                        k = _declared_kind(nm.type)
                        if k is not None:
                            env[nm.name] = k
            elif isinstance(n, Quantifier):
                for b in n.binders:
                    env.setdefault(b.name, _declared_kind(b.type) or "int")
            elif isinstance(n, ForStmt):
                env.setdefault(n.var, _declared_kind(n.var_type) or "int")
    return env


def _seq_literal_issue(n: SeqDisplay, env: dict) -> Optional[str]:
    """Row 25: `None` when every element of the Dafny sequence display
    `n` is int-typed (so it lifts to t's literal, `[]` -- no elements at
    all -- included); else the section-5 reason the FIRST offending
    element names -- `nested-seq` for a nested display (or anything else
    this row cannot type as `int`, the same bucket `_type_issue` already
    uses for "seq of anything but int/nat"). Row 28 (2026-09-09): a char
    literal element (`['a', 'b']`) is no longer refused here at all --
    `expr_kind` now types a `CharLit` `int` (its own code point), so it
    falls straight through to the ordinary "every element int" reading,
    unlike a `StringLit` element (`["ab", "cd"]`, a display of DISPLAYS
    in effect, `expr_kind` typing it `seq`), which still lands on
    `nested-seq` below -- "string of anything nested is not [in the
    fragment]", the task's own words for row 28's own refusal list."""
    for el in n.elems:
        if isinstance(el, SeqDisplay):
            return "nested-seq"
        if expr_kind(el, env.get) != "int":
            return "nested-seq"
    return None


# ---------------------------------------------------------------------------
# Row 28 (2026-09-09, SPEC.md "Strings as sequences of code points (v1)"):
# a Dafny `char` is a t int, the code point; `string` a t `seq` of them.
# `expr_kind`/`_declared_kind` above already fold char into the SAME "int"
# kind a plain int has (a char IS its code point, no separate t kind), so
# this section answers the two narrower questions that folding loses: a
# Binary +/-'s operand is SPECIFICALLY char (Dafny gives `char + char` and
# `char - char` an overflow/underflow proof obligation t cannot state,
# measured on dafny 4.11.0 -- `char-arith`, refused), and a Cast's own
# safety (`char as int` is always the identity; `int as char` only when
# the operand is visibly already a code point -- a literal in range or a
# char cast back -- else `char-cast-unbounded`).
# ---------------------------------------------------------------------------

_CHAR_ESCAPES = {"n": 10, "t": 9, "r": 13, "0": 0, "'": 39, '"': 34, "\\": 92}

# Measured on dafny 4.11.0 (this task's own environment): the DEFAULT run
# (no `--unicode-char` flag at all, what `lifter.py`/`lift_check.py` both
# invoke) already accepts the FULL Unicode range for `as char` and for a
# char VALUE generally -- `1114111 as char`/`70000 as char` both verify
# with no obligation beyond "not negative, not above 1114111" -- so a
# cast's own safety bound and a char parameter's/return's own domain
# guard (below) both use 1114111, SPEC.md's own "an int in [0, 1114111]".
_CHAR_MAX = 1114111
# A LITERAL's own decodability is a narrower, more conservative question
# than a value's general validity: SPEC.md's row 28 mapping says "a Dafny
# char is a UTF-16 code unit unless the program is compiled with
# --unicode-char, so a literal outside the Basic Multilingual Plane is
# refused rather than guessed" -- measured to be stale as a claim about
# THIS dafny's default (see `_CHAR_MAX`'s own comment), but still the
# stated, deliberate policy for what this lifter decodes from LITERAL
# syntax, so literal decoding keeps the more conservative BMP bound
# (0xFFFF) rather than widening to match the value bound above.
_CHAR_LITERAL_MAX = 0xFFFF


def _decode_one_char(text: str, i: int):
    """One Dafny character starting at `text[i]` (never a delimiting
    quote): the standard escapes measured on dafny 4.11.0 (`'\\n'` -> 10,
    `'\\t'` -> 9, `'\\r'` -> 13, `'\\0'` -> 0, `'\\''` -> 39, `'\\"'` -> 34,
    `'\\\\'` -> 92), the full-range escape `\\U{H+}` (measured: the ONLY
    valid spelling for a non-ASCII code point on this dafny -- `\\u{H+}`
    (lowercase u) and `\\{H+}` (no letter at all) are both parse errors),
    or one literal, unescaped
    character read by Python's own code-point indexing (Python's `str` is
    already code-point-indexed, so one raw BMP or astral character -- no
    `\\U{...}` needed -- decodes correctly here with no special case).
    Returns `(codepoint, index just past it)`; `codepoint` is `None` when
    the escape is not one of these (never measured to occur in the
    corpus, refused rather than guessed, `char-literal-nonbmp`)."""
    c = text[i]
    if c != "\\":
        return ord(c), i + 1
    nxt = text[i + 1] if i + 1 < len(text) else ""
    if nxt in _CHAR_ESCAPES:
        return _CHAR_ESCAPES[nxt], i + 2
    if nxt == "U" and text[i + 2:i + 3] == "{":
        end = text.find("}", i + 3)
        if end == -1:
            return None, len(text)
        try:
            return int(text[i + 3:end], 16), end + 1
        except ValueError:
            return None, end + 1
    return None, min(i + 2, len(text))


def decode_char_literal(text: str):
    """Row 28: the code point a Dafny char literal `text` (QUOTES
    INCLUDED, exactly `CharLit.text`) denotes, or `None` when it cannot
    be decoded safely -- an unrecognised escape, or a code point beyond
    `_CHAR_LITERAL_MAX` (see that name's own comment)."""
    inner = text[1:-1]
    if not inner:
        return None
    cp, end = _decode_one_char(inner, 0)
    if cp is None or end != len(inner) or cp > _CHAR_LITERAL_MAX:
        return None
    return cp


def decode_string_literal(text: str):
    """Row 28: the list of code points a Dafny string literal `text`
    (quotes included, `StringLit.text`) denotes, `[]` for `\"\"`, or
    `None` when any character fails to decode (`decode_char_literal`'s
    own rule, applied character by character)."""
    inner = text[1:-1]
    out: list[int] = []
    i = 0
    while i < len(inner):
        cp, i = _decode_one_char(inner, i)
        if cp is None or cp > _CHAR_LITERAL_MAX:
            return None
        out.append(cp)
    return out


def _build_char_names(method: MethodDecl, closure: tuple[Decl, ...]):
    """Row 28's own narrower companion to `_build_kind_env`: two sets,
    (char-typed names, string/seq<char>-typed names), by DECLARED type
    only (params, the one return, every closure function's own params,
    and locals) -- an untyped `var c := 'a';` is section 4.2's own
    `untyped-var` territory already, not this row's, and no initialiser
    -inference is attempted (unlike `_build_kind_env`'s int/bool/seq
    reading) since char-ness only ever matters for a NAME this simple
    reading can already see is declared one."""
    chars: set[str] = set()
    seqs: set[str] = set()

    def note(name: Optional[str], t: Optional[Type]) -> None:
        if name is None or t is None:
            return
        if t.kind == "char":
            chars.add(name)
        elif t.kind == "string" or _is_seq_of_char(t):
            seqs.add(name)

    for p in method.params:
        note(p.name, p.type)
    if len(method.returns) == 1:
        note(method.returns[0].name, method.returns[0].type)
    for d in closure:
        if isinstance(d, FunctionDecl):
            for p in d.params:
                note(p.name, p.type)
    for root in [method] + list(closure):
        for n in walk(root):
            if isinstance(n, VarDeclStmt):
                for nm in n.names:
                    note(nm.name, nm.type)
    return chars, seqs


def _is_char_expr(e: Expr, char_names: set, char_seq_names: set = frozenset()) -> bool:
    """Row 28: best-effort "this expression's Dafny type is exactly
    char", the one question `expr_kind`'s int/bool/seq vocabulary cannot
    answer since it folds char into plain int by design. Used only for a
    Binary +/-'s operand (char-arith) and a Cast's own safety
    (char-as-int/int-as-char); `Index` on a NAMED string/seq<char>
    receiver (`s[i]`, e.g. two characters of a string compared or cast)
    is the one non-leaf shape measured worth carrying -- anything else
    (a spec_fun call's own return, an arbitrary Binary/Chain result) is
    `False`, the conservative answer, never a guess."""
    if isinstance(e, CharLit):
        return True
    if isinstance(e, Ident):
        return e.name in char_names
    if isinstance(e, Old):
        return _is_char_expr(e.arg, char_names, char_seq_names)
    if isinstance(e, Cast):
        return e.type.kind == "char"
    if isinstance(e, IfExpr):
        return (_is_char_expr(e.then, char_names, char_seq_names)
                and _is_char_expr(e.else_, char_names, char_seq_names))
    if isinstance(e, Index) and isinstance(e.base, Ident):
        return e.base.name in char_seq_names
    return False


def _char_cast_safe(base: Expr, char_names: set, char_seq_names: set) -> bool:
    """Row 28's own condition for accepting `n as char`: the task's own
    words, "ONLY when the lifter can see the operand is a code point
    already (a char cast back, or a literal in range)". A literal is
    checked against `_CHAR_MAX` (the value bound, not the more
    conservative literal-decoding bound: dafny itself accepts any
    literal up to 1114111 here with no extra obligation, measured, and
    this is a CAST's safety, not a literal's own decoding)."""
    if isinstance(base, IntLit) and 0 <= base.value <= _CHAR_MAX:
        return True
    if (isinstance(base, Cast) and base.type.kind == "int"
            and _is_char_expr(base.base, char_names, char_seq_names)):
        return True
    return False


# ---------------------------------------------------------------------------
# The call-graph closure (LIFTER-DESIGN.md section 4.1's "declarations
# outside the method's call-graph closure" row). We do not have rprint's
# own "CALL GRAPH for module _module" comment available (the shim parser
# strips comments; see the module docstring), so the closure -- and the
# mutual-recursion check that rides on it -- is computed here by a plain
# reachability walk over Call/Ident/CallStmt names instead. This is a
# strictly more mechanical (and checkable) source of the same fact.
# ---------------------------------------------------------------------------

def _called_names(node) -> set[str]:
    names: set[str] = set()
    for n in walk(node):
        if isinstance(n, Call) and isinstance(n.fn, Ident):
            names.add(n.fn.name)
        elif isinstance(n, CallStmt):
            names.add(n.name)
    return names


def _closure(module: Module, method: MethodDecl) -> tuple[Decl, ...]:
    by_name = {d.name: d for d in module.decls if d.name}
    order: list[Decl] = []
    seen: set[str] = set()

    def visit(name: str) -> None:
        if name in seen:
            return
        d = by_name.get(name)
        if d is None or not isinstance(d, (FunctionDecl, LemmaDecl)):
            return
        seen.add(name)
        for dep in _called_names(d):
            if dep != name:
                visit(dep)
        order.append(d)

    for dep in _called_names(method):
        if dep != method.name:
            visit(dep)
    return tuple(order)


def _mutual_recursion_issue(closure: tuple[Decl, ...]) -> Optional[tuple[int, str, str]]:
    funs = [d for d in closure if isinstance(d, FunctionDecl)]
    calls = {f.name: (_called_names(f) - {f.name}) for f in funs}
    names = set(calls)

    def reachable(start: str) -> set[str]:
        out: set[str] = set()
        stack = list(calls.get(start, ()) & names)
        while stack:
            n = stack.pop()
            if n in out:
                continue
            out.add(n)
            stack.extend(calls.get(n, ()) & names)
        return out

    for f in funs:
        reach = reachable(f.name)
        if f.name in reach:  # f reaches itself only via >=1 OTHER function
            return (f.line, "mutual-recursion", f.name)
    return None


# ---------------------------------------------------------------------------
# Quantifier bound extraction (section 4.4). Returns a dict describing how
# to build t's `forall`/`exists` node, or None if the range is not one of
# the bounded shapes -- in which case the caller refuses
# `unbounded-quantifier` (or `set`/`map` when the binder ranges over one).
# ---------------------------------------------------------------------------

def _is_ident(e: Expr, name: str) -> bool:
    """True iff `e` is exactly the bound variable `name` (never a compound
    expression that merely mentions it) -- integrator-added: `_bound_range`
    below called this and `_plus1` without either ever being defined
    anywhere in this file (measured: a `NameError` the instant a genuine
    literal `lo <= k < hi` chain guard reached this function, dormant only
    because zero of the 77 in-fragment files contain any quantifier at
    all, so `bound_quantifier` was never actually exercised by any
    implementer's own test run). Fixed 2026-09-05."""
    return isinstance(e, Ident) and e.name == name


def _plus1(e: Expr) -> Expr:
    """`e + 1`, to convert a strict `<` bound into t's own `lo <= v < hi`
    (inclusive lo, exclusive hi) convention, matching how `_lift_chain`'s
    `in-desugared` row already builds a `[0, len(s))` range."""
    return Binary(e.line, "+", e, IntLit(e.line, 1))


def _bound_range(binder: str, guard: Expr) -> Optional[tuple[Expr, Expr, Optional[Expr]]]:
    """`lo <= k < hi` and its three half-open siblings (section 4.4), for
    exactly the named binder, optionally AND'ed with more conjuncts.
    Returns (lo, hi, extra) where `extra` is the conjunction of whatever
    else was in the guard (None if nothing else was), or None if no
    conjunct bounds `binder` this way."""
    conjuncts = list(guard.args) if isinstance(guard, NaryBool) and guard.op == "&&" else [guard]
    for i, c in enumerate(conjuncts):
        if isinstance(c, Chain) and len(c.ops) == 2 and len(c.operands) == 3:
            lo_op, hi_op = c.ops
            lo, mid, hi = c.operands
            if _is_ident(mid, binder) and lo_op in ("<", "<=") and hi_op in ("<", "<="):
                lo2 = _plus1(lo) if lo_op == "<" else lo
                hi2 = _plus1(hi) if hi_op == "<=" else hi
                rest = [x for j, x in enumerate(conjuncts) if j != i]
                extra = None
                if rest:
                    extra = rest[0] if len(rest) == 1 else NaryBool(rest[0].line, "&&", tuple(rest))
                return (lo2, hi2, extra)
    # Integrator addition 2026-09-05: the SAME range, written as two
    # separate single-comparison conjuncts (`lo <= k && k < hi`) rather
    # than one written chain (`lo <= k < hi`) -- the shape
    # `lower_dafny.lower` always prints and dafny's own rprint never
    # recombines into a chain, measured via the 18.4 inverse test: every
    # one of 13/31 sampled tasks with a quantifier hit `unbounded
    # -quantifier` on the round trip before this was added, all for this
    # one reason.
    lo_i = hi_i = None
    lo = hi = None
    for i, c in enumerate(conjuncts):
        if not (isinstance(c, Chain) and len(c.ops) == 1 and len(c.operands) == 2):
            continue
        op = c.ops[0]
        a, b = c.operands
        if op in ("<", "<=") and _is_ident(b, binder) and lo_i is None:
            lo_i, lo = i, (_plus1(a) if op == "<" else a)
        elif op in ("<", "<=") and _is_ident(a, binder) and hi_i is None:
            hi_i, hi = i, (_plus1(b) if op == "<=" else b)
    if lo_i is not None and hi_i is not None and lo_i != hi_i:
        rest = [x for j, x in enumerate(conjuncts) if j not in (lo_i, hi_i)]
        extra = None
        if rest:
            extra = rest[0] if len(rest) == 1 else NaryBool(rest[0].line, "&&", tuple(rest))
        return (lo, hi, extra)
    return None


def _bound_membership(binder: str, guard: Expr) -> Optional[Expr]:
    """`k in s` (section 4.4's third quantifier row): returns `s` when
    `guard` is exactly `k in s` for the named binder, else None."""
    if isinstance(guard, Chain) and len(guard.ops) == 1 and guard.ops[0] == "in":
        a, b = guard.operands
        if _is_ident(a, binder):
            return b
    return None


def bound_quantifier(q: Quantifier):
    """Section 4.4's quantifier-bounding rules, unified into one contract:
    on success, returns {"binders": [(name, lo, hi, membership_seq), ...],
    "body": Expr} where `body` is the FULLY RESOLVED predicate to lift at
    the innermost level (every `&&`/`==>` combination already folded in),
    and each binder's `lo`/`hi` are `None` exactly when `membership_seq`
    is not (the `k in s` row, section 4.4's third quantifier row: `lo`/`hi`
    become `0`/`len(s)` and `body` must still be substituted `k -> s[j]`
    by the caller using the returned fresh binder position). Returns None
    when the range is not one of section 4.4's bounded shapes (the caller
    refuses `unbounded-quantifier`)."""
    if len(q.binders) == 0:
        return None

    if len(q.binders) == 1:
        b = q.binders[0]
        guard = q.range
        if guard is None:
            # Unguarded: the range lives inside body as `lo<=k<hi ==> P`
            # (forall) or `lo<=k<hi && P` (exists).
            if q.kind == "forall" and isinstance(q.body, Implies):
                got = _bound_range(b.name, q.body.left)
                if got is None or got[2] is not None:
                    return None  # extra conjuncts with no `==>` shape: bail
                lo, hi, _ = got
                return {"binders": [(b.name, lo, hi, None)], "body": q.body.right}
            if q.kind == "exists" and isinstance(q.body, NaryBool) and q.body.op == "&&":
                got = _bound_range(b.name, q.body)
                if got is None:
                    return None
                lo, hi, extra = got
                body = extra if extra is not None else BoolLit(q.line, True)
                return {"binders": [(b.name, lo, hi, None)], "body": body}
            return None
        mem = _bound_membership(b.name, guard)
        if mem is not None:
            return {"binders": [(b.name, None, None, mem)], "body": q.body}
        got = _bound_range(b.name, guard)
        if got is None:
            return None
        lo, hi, extra = got
        if extra is not None:
            body = Implies(q.line, extra, q.body) if q.kind == "forall" \
                else NaryBool(q.line, "&&", (extra, q.body))
        else:
            body = q.body
        return {"binders": [(b.name, lo, hi, None)], "body": body}

    # Multiple binders: each finds its own chain conjunct in a top-level
    # "&&" range guard (section 4.4's "two binders" row, generalised to N).
    guard = q.range
    if guard is None:
        return None
    conjuncts = list(guard.args) if isinstance(guard, NaryBool) and guard.op == "&&" else [guard]
    used = [False] * len(conjuncts)
    result_binders = []
    for b in q.binders:
        found = None
        for i, c in enumerate(conjuncts):
            if used[i]:
                continue
            if isinstance(c, Chain) and len(c.ops) == 2 and len(c.operands) == 3:
                lo_op, hi_op = c.ops
                lo, mid, hi = c.operands
                if _is_ident(mid, b.name) and lo_op in ("<", "<=") and hi_op in ("<", "<="):
                    lo2 = _plus1(lo) if lo_op == "<" else lo
                    hi2 = _plus1(hi) if hi_op == "<=" else hi
                    found = (lo2, hi2)
                    used[i] = True
                    break
        if found is None:
            return None
        result_binders.append((b.name, found[0], found[1], None))
    rest = [c for i, c in enumerate(conjuncts) if not used[i]]
    extra = None
    if rest:
        extra = rest[0] if len(rest) == 1 else NaryBool(rest[0].line, "&&", tuple(rest))
    if extra is not None:
        body = Implies(q.line, extra, q.body) if q.kind == "forall" \
            else NaryBool(q.line, "&&", (extra, q.body))
    else:
        body = q.body
    return {"binders": result_binders, "body": body}


# ---------------------------------------------------------------------------
# Tail/early-return scan (section 4.5's three `return` rows, plus SPEC.md
# "Early exit (v1)", 2026-09-08). Returns (issues, rewrites) where issues
# are refusal candidates still raised here (none, as of the early-exit
# rule below -- `break`/`continue` get their own dedicated scan,
# `scan_breaks` below, not `_scan_node_for_issues`'s generic pass) and
# rewrites are (line, kind) pairs,
# kind one of "tail" (a return in tail position, desugared away by
# `lift_rewrite._desugar_returns`) or "early" (any other return, mapped to
# t's `{"return": [ret, e]}` statement -- LIFTER-DECISIONS.md row 21).
# Both as plain tuples the caller turns into Rewrite objects.
# ---------------------------------------------------------------------------

def scan_returns(stmts: tuple[Stmt, ...], tail: bool
                  ) -> tuple[list[tuple[int, str, str]], list[tuple[int, str]]]:
    issues: list[tuple[int, str, str]] = []
    rewrites: list[tuple[int, str]] = []  # (line, "tail" | "early")
    n = len(stmts)
    for i, s in enumerate(stmts):
        this_tail = tail and (i == n - 1)
        if isinstance(s, ReturnStmt):
            rewrites.append((s.line, "tail" if this_tail else "early"))
        elif isinstance(s, IfStmt):
            i2, r2 = scan_returns(s.then, this_tail)
            issues += i2
            rewrites += r2
            if isinstance(s.else_, tuple):
                i3, r3 = scan_returns(s.else_, this_tail)
            elif isinstance(s.else_, IfStmt):
                i3, r3 = scan_returns((s.else_,), this_tail)
            else:
                i3, r3 = [], []
            issues += i3
            rewrites += r3
        elif isinstance(s, WhileStmt):
            i2, r2 = scan_returns(s.body, False)
            issues += i2
            rewrites += r2
        elif isinstance(s, ForStmt):
            i2, r2 = scan_returns(s.body, False)
            issues += i2
            rewrites += r2
        elif isinstance(s, BlockStmt):
            i2, r2 = scan_returns(s.body, False)
            issues += i2
            rewrites += r2
        elif isinstance(s, LabelStmt):
            i2, r2 = scan_returns((s.stmt,), False)
            issues += i2
            rewrites += r2
    return issues, rewrites


# ---------------------------------------------------------------------------
# Break scan (LIFTER-DECISIONS.md row 23, 2026-09-09). An unlabeled `break`
# lifts to t's early exit `return ret;` exactly when its innermost
# enclosing loop L is reachable from the method body through nothing but
# IfStmt then/else branches (BlockStmt and LabelStmt transparent, never
# through another loop's own body) and the straight-line CONTINUATION C
# that would run after L -- every statement physically after L in its own
# block, then every statement after the enclosing if in ITS block, and so
# on to the end of the method body -- contains no WhileStmt, ForStmt,
# BreakStmt, ContinueStmt or ReturnStmt, except a single trailing
# ReturnStmt (exactly the tail return `_desugar_returns` removes or turns
# into an assignment, so transparent here too). `_find_tail_loops` and
# `_continuation_issue` do this computation once; `scan_breaks` (called
# from both `classify`, on the raw AST, and `lift_rewrite._desugar_breaks`,
# on the AST `_desugar_returns` already ran over) is the one shared entry
# point, so the two modules can never disagree about which break
# qualifies. `ContinueStmt` and a labeled `BreakStmt` are refused outright
# (`continue`, `break-label`); an unlabeled break whose innermost loop
# sits inside another loop is `break-in-nested-loop`; one whose loop's
# continuation holds a loop or break/continue is `break-before-loop`;
# every other non-tail shape (e.g. the loop followed by a non-tail
# return, or sitting in a non-tail if branch) is `break-not-tail`.
# ---------------------------------------------------------------------------

def _find_tail_loops(stmts: tuple[Stmt, ...], outer: tuple[Stmt, ...]
                      ) -> dict[int, tuple[Stmt, ...]]:
    """Every WhileStmt/ForStmt reachable from `stmts` through nothing but
    IfStmt/BlockStmt/LabelStmt nesting, mapped by `id` to its full
    continuation: the statements physically after it in its own block,
    then physically after each enclosing if in ITS block, and so on,
    finally reaching `outer` -- the continuation of `stmts` itself, handed
    down by the caller (`()` at the method body's own top level, meaning
    nothing follows and the method simply ends)."""
    found: dict[int, tuple[Stmt, ...]] = {}
    n = len(stmts)
    for i, s in enumerate(stmts):
        rest = stmts[i + 1:]
        if isinstance(s, IfStmt):
            branch_outer = rest + outer
            found.update(_find_tail_loops(s.then, branch_outer))
            if isinstance(s.else_, tuple):
                found.update(_find_tail_loops(s.else_, branch_outer))
            elif isinstance(s.else_, IfStmt):
                found.update(_find_tail_loops((s.else_,), branch_outer))
        elif isinstance(s, BlockStmt):
            found.update(_find_tail_loops(s.body, rest + outer))
        elif isinstance(s, LabelStmt):
            found.update(_find_tail_loops((s.stmt,), rest + outer))
        elif isinstance(s, (WhileStmt, ForStmt)):
            found[id(s)] = rest + outer
    return found


def _continuation_issue(cont: tuple[Stmt, ...]) -> Optional[str]:
    """None if `cont` (a loop's continuation, from `_find_tail_loops`) is
    clean enough to duplicate at a break; else the refusal token. A
    trailing ReturnStmt is exempt -- by construction `cont` always reaches
    the method body's own end, so a ReturnStmt in that last slot is
    exactly the tail return `_desugar_returns` removes or turns into an
    assignment (row 21); any OTHER ReturnStmt, or a loop or break/continue
    anywhere in `cont`, is not."""
    if not cont:
        return None
    scan = cont[:-1] if isinstance(cont[-1], ReturnStmt) else cont
    for s in scan:
        for n in walk(s):
            if isinstance(n, (WhileStmt, ForStmt, BreakStmt, ContinueStmt)):
                return "break-before-loop"
            if isinstance(n, ReturnStmt):
                return "break-not-tail"
    return None


def _scan_breaks_continues(stmts: tuple[Stmt, ...], loop_stack: list
                            ) -> list[tuple[str, Stmt, list]]:
    """Every BreakStmt/ContinueStmt reachable from `stmts` by a full
    descent (through IfStmt/WhileStmt/ForStmt/BlockStmt/LabelStmt --
    break/continue never nest inside an expression), each tagged with the
    stack of loops enclosing it (innermost last); mirrors `scan_returns`'s
    own recursion shape."""
    found: list[tuple[str, Stmt, list]] = []
    for s in stmts:
        if isinstance(s, BreakStmt):
            found.append(("break", s, list(loop_stack)))
        elif isinstance(s, ContinueStmt):
            found.append(("continue", s, list(loop_stack)))
        elif isinstance(s, IfStmt):
            found += _scan_breaks_continues(s.then, loop_stack)
            if isinstance(s.else_, tuple):
                found += _scan_breaks_continues(s.else_, loop_stack)
            elif isinstance(s.else_, IfStmt):
                found += _scan_breaks_continues((s.else_,), loop_stack)
        elif isinstance(s, (WhileStmt, ForStmt)):
            found += _scan_breaks_continues(s.body, loop_stack + [s])
        elif isinstance(s, BlockStmt):
            found += _scan_breaks_continues(s.body, loop_stack)
        elif isinstance(s, LabelStmt):
            found += _scan_breaks_continues((s.stmt,), loop_stack)
    return found


def scan_breaks(body: tuple[Stmt, ...]
                 ) -> tuple[list[tuple[int, str, str]],
                            list[tuple[Stmt, Stmt, tuple[Stmt, ...]]]]:
    """Returns (issues, accepted): issues are (line, "early-exit", token)
    refusal candidates; accepted is (break_node, loop_node, continuation)
    for every unlabeled break row 23 lifts. `lift_rewrite._desugar_breaks`
    uses `id(break_node)` to find the exact node it must replace."""
    issues: list[tuple[int, str, str]] = []
    accepted: list[tuple[Stmt, Stmt, tuple[Stmt, ...]]] = []
    tail_loops = _find_tail_loops(body, ())
    for kind, node, loop_stack in _scan_breaks_continues(body, []):
        if kind == "continue":
            issues.append((node.line, "early-exit", "continue"))
            continue
        if node.label is not None:
            issues.append((node.line, "early-exit", "break-label"))
            continue
        if not loop_stack:
            issues.append((node.line, "early-exit", "break-not-tail"))
            continue
        if len(loop_stack) > 1:
            issues.append((node.line, "early-exit", "break-in-nested-loop"))
            continue
        loop = loop_stack[0]
        cont = tail_loops.get(id(loop))
        if cont is None:
            issues.append((node.line, "early-exit", "break-not-tail"))
            continue
        bad = _continuation_issue(cont)
        if bad is not None:
            issues.append((node.line, "early-exit", bad))
            continue
        accepted.append((node, loop, cont))
    return issues, accepted


# ---------------------------------------------------------------------------
# `x != null` on a non-nullable array (row 24, 2026-09-09).
# ---------------------------------------------------------------------------

def _null_compare(e: Expr, accepted_names: frozenset[str]) -> Optional[Ident]:
    """`e` is `x != null` or `null != x` where `x`'s Dafny name is in
    `accepted_names` (a non-nullable `array<int|nat>` parameter or
    return of the method being classified): returns the `null` Ident
    node, the one `_scan_node_for_issues` would otherwise flag `heap`.
    `None` for anything else, including `x == null` on the same `x`
    (row 24: a closed fact (false) but never appears in verified code,
    so it is refused `heap` as before, never dropped).

    A single relational operator (`!=` included) always parses as a
    length-1 `Chain` (`lift_ast.Chain`'s own docstring: "two operands
    with one operator print as a plain Binary-shaped chain of length 1
    BY CONVENTION" -- the AST node is still `Chain`, never `Binary`;
    `Binary` is section 3's `Add`/`Mul` production, `+ - * / %` only),
    so this matches `Chain(ops=("!=",), operands=(x, null))` (either
    operand order), not a `Binary` node."""
    if not (isinstance(e, Chain) and len(e.ops) == 1 and e.ops[0] == "!="):
        return None
    left, right = e.operands
    if isinstance(left, Ident) and left.name == "null" \
            and isinstance(right, Ident) and right.name in accepted_names:
        return left
    if isinstance(right, Ident) and right.name == "null" \
            and isinstance(left, Ident) and left.name in accepted_names:
        return right
    return None


def scan_null_checks(method: MethodDecl
                      ) -> list[tuple[Spec, Expr, Ident]]:
    """Row 24: `requires a != null` (or `a != null` as a top-level `&&`
    conjunct) is a tautology when `a` is a parameter or return whose
    DECLARED type is a non-nullable `array<int|nat>` (Dafny 4 proves it
    trivially -- only `array?<int>` is nullable). Returns one entry per
    such comparison this rule accepts: the `Spec` node it lives in
    (`RequiresClause`/`EnsuresClause`/loop `InvariantClause`), the
    comparison `Binary` itself, and the `null` Ident inside it, so both
    `classify` (exempt it from the `heap` refusal, record
    `null-check-dropped`) and `lift_rewrite._strip_null_checks` (the
    SAME shared computation, per `scan_breaks`'s pattern) never disagree
    about which comparisons are safe to drop.

    Only a WHOLE clause or a TOP-LEVEL `&&` conjunct of one is matched
    (mirrors `lift_rewrite._strip_fresh_conjuncts`'s "top-level `&&`
    conjunct" reading of decision 22): `a != null` inside an `||`, an
    `==>`, or a plain body expression never reaches this function (it is
    not a clause's top-level expr or top-level `&&` conjunct), so
    `_scan_node_for_issues` still refuses it `heap` as before -- only
    the tautological POSITIVE positions section 4's ensures/requires/
    invariant machinery ever proves are safe to drop."""
    accepted_names = frozenset(
        {p.name for p in method.params if _is_array_of_int(p.type)}
        | {r.name for r in method.returns if _is_array_of_int(r.type)})
    if not accepted_names:
        return []
    clauses: list[Spec] = [s for s in method.specs
                            if isinstance(s, (RequiresClause, EnsuresClause))]
    if method.body is not None:
        for n in walk(method.body):
            if isinstance(n, (WhileStmt, ForStmt)):
                clauses += [sp for sp in n.specs if isinstance(sp, InvariantClause)]
    out: list[tuple[Spec, Expr, Ident]] = []
    for spec in clauses:
        e = spec.expr
        m = _null_compare(e, accepted_names)
        if m is not None:
            out.append((spec, e, m))
            continue
        if isinstance(e, NaryBool) and e.op == "&&":
            for a in e.args:
                m = _null_compare(a, accepted_names)
                if m is not None:
                    out.append((spec, a, m))
    return out


# ---------------------------------------------------------------------------
# Read-only array condition (decision 1 / section 18.6).
# ---------------------------------------------------------------------------

def array_readonly_issue(param_name: str, method: MethodDecl,
                          closure: tuple[Decl, ...]) -> Optional[str]:
    """None if `param_name` (an `array<int|nat>` parameter) satisfies the
    read-only condition everywhere in the method's closure; else the
    section-5 reason it fails with (`array-mutation` for a write,
    `array` for anything else that disqualifies it -- being passed to
    another call, an aliasing concern this shim cannot verify past).

    A `new` allocation ANYWHERE in the method used to disqualify every
    array param outright (decision 1's original, conservative reading);
    decision 22 narrows that. Dafny forbids assigning to an in-parameter
    (`a := new int[5];` does not resolve when `a` is a parameter), so a
    `NewRhs` can never alias `param_name` -- it is always bound to a
    local or the return, a DIFFERENT name decision 22's own
    `find_array_mutation` classifies on its own terms. Dropping this
    check only WIDENS acceptance (a method that used to fail this
    condition because of an unrelated `new` may now pass it); no method
    that satisfied the OLD, stricter condition can newly fail it, so no
    currently-lifted task can change here (an already-successful lift's
    scope has no `NewRhs` in it at all -- if it did, this branch would
    have refused it before decision 22 existed)."""
    scope: list[Node] = [method] + list(closure)
    for root in scope:
        for n in walk(root):
            if isinstance(n, Assign):
                for lhs in n.targets:
                    if (lhs.kind == "index" and isinstance(lhs.base, Ident)
                            and lhs.base.name == param_name):
                        return "array-mutation"
            if isinstance(n, (Call, CallStmt)):
                args = n.args
                for a in args:
                    if isinstance(a, Ident) and a.name == param_name:
                        return "array"
    return None


def _array_passed_to_call(name: str, method: MethodDecl, closure: tuple[Decl, ...]) -> bool:
    """True iff `name` appears as a bare argument to some call anywhere
    in the method's closure -- the aliasing half of `array_readonly
    _issue`, factored out so decision 22's mutated array can reuse it
    without also tripping that function's own array-mutation check
    (which the mutated array is EXPECTED to trip)."""
    for root in [method] + list(closure):
        for n in walk(root):
            if isinstance(n, (Call, CallStmt)):
                for a in n.args:
                    if isinstance(a, Ident) and a.name == name:
                        return True
    return False


# ---------------------------------------------------------------------------
# Array mutation and allocation (decision 22 / SPEC.md "Sequences as values
# (v1)"). An array parameter or local of int (or nat) elements is a `seq`;
# `a[i] := e` becomes `a := a[i := e]`; `new int[n]` becomes `seq(n, 0)`.
# Two shapes map:
#
#   "modifies-param": a method `modifies a` (exactly `a`, nothing else,
#   on the method and every loop inside it) that writes `a[i] := e`
#   somewhere. `a` becomes a seq PARAMETER and the task gets a FRESH seq
#   return (`lift_rewrite.py` names it); the body is primed `<ret> := a;`
#   so every later `a[i] := e` rewrites as an update of the return.
#   Requires ZERO Dafny-declared returns: a method that already returns
#   something (BubbleSort's `n`, removeElement's `i`) would need a SECOND
#   return to also carry the array's final value, and t has exactly one.
#
#   "alloc-fill": a local or the return itself is bound to `new int[n]`
#   (or `new nat[n]`, single dimension) and optionally filled by later
#   `x[i] := e`; `new int[n]` becomes `fill(n, 0)` directly. The return's
#   OWN Dafny type must be `array<int>`/`array<nat>` (non-nullable) for
#   this to matter -- a plain local that is never returned is refused by
#   the ordinary "local array" rule exactly as before.
#
# At most one array is mutated/allocated per method; a mutated array read
# through another name (passed to a call), a modifies clause naming
# anything but the one array, and every shape this row does not name
# (two-dimensional arrays, non-int/nat elements, more than one mutated
# array) are refused, `array-mutation` unless the type itself is bad
# (`array`).
# ---------------------------------------------------------------------------

_ARRAY_NEW_SHAPE_RE = re.compile(r"^new\s+[A-Za-z_]\w*(?:<[^<>]*>)?\s*\[")
_NEW_ARRAY_RE = re.compile(r"^new\s+(int|nat)\s*\[\s*([^\[\]]+?)\s*\]$")


def _looks_like_array_new(rhs: "NewRhs") -> bool:
    """True iff `rhs.text` is array-allocation SHAPED at all (a type
    name immediately followed by `[`), as opposed to object construction
    `new C(...)` or `new C;` -- Dafny's array `new` always uses brackets,
    a class/trait `new` never does before its first `(`. This gates
    `find_array_mutation` so it stays silent on a non-array `new`
    exactly as it always was (nothing scanned `NewRhs` at all outside
    `array_readonly_issue`'s per-array-param check before decision 22),
    rather than newly refusing a method decision 22 has no business
    looking at."""
    return _ARRAY_NEW_SHAPE_RE.match(rhs.text.strip()) is not None


def _new_array_size_text(rhs: "NewRhs") -> Optional[tuple[str, str]]:
    """`(elem_kind, size_text)` when `rhs.text` is `new int[<expr>]` or
    `new nat[<expr>]` (one dimension, no nested `[`/`]`, so `array2`'s
    `new int[n, m]` and jagged `new int[n][m]` both fail the match); else
    `None` (a bad element type or more than one dimension -- call only
    after `_looks_like_array_new` has already confirmed this IS an array
    allocation, not an unrelated heap allocation `new C(...)`)."""
    m = _NEW_ARRAY_RE.match(rhs.text.strip())
    if m is None:
        return None
    return m.group(1), m.group(2)


@dataclass
class ArrayMutation:
    kind: str              # "modifies-param" | "alloc-fill"
    name: str               # dafny name of the mutated/allocated array
    elem_kind: str = "int"   # "int" | "nat", from the source's own typing


def _index_assign_targets(method: MethodDecl) -> list[tuple[int, str]]:
    """`(line, base_name)` for every `x[i] := e` (or `x[i], y[j] := ..`)
    target anywhere in the method (body and specs both, so a loop's own
    `modifies`/invariants are covered too); a target this shim cannot
    resolve to a bare name (`a[i][j] := e`, `obj.a[i] := e`) is reported
    with base_name `None` so the caller can refuse rather than ignore it."""
    out: list[tuple[int, str]] = []
    for n in walk(method):
        if isinstance(n, Assign):
            for lhs in n.targets:
                if lhs.kind != "index":
                    continue
                if isinstance(lhs.base, Ident):
                    out.append((n.line, lhs.base.name))
                else:
                    out.append((n.line, None))
    return out


def _alloc_bindings(method: MethodDecl) -> list[tuple[int, str, "NewRhs"]]:
    """`(line, bound_name, NewRhs)` for every `name := new ...` or
    `var name := new ...` in the method body (never in specs -- `new` is
    not an expression a `requires`/`ensures`/`invariant` can contain)."""
    out: list[tuple[int, str, "NewRhs"]] = []
    if method.body is None:
        return out
    for n in walk(method.body):
        if isinstance(n, Assign) and len(n.targets) == 1 and n.targets[0].kind == "name":
            v = n.values[0] if n.values else None
            if isinstance(v, NewRhs):
                out.append((n.line, n.targets[0].name, v))
        elif isinstance(n, VarDeclStmt) and n.init:
            for nm, v in zip(n.names, n.init):
                if isinstance(v, NewRhs):
                    out.append((n.line, nm.name, v))
    return out


def find_array_mutation(method: MethodDecl, closure: tuple[Decl, ...]
                         ) -> tuple[Optional[ArrayMutation], Optional[tuple[int, str, str]]]:
    """The method's ONE mutated/allocated array, per the shapes above.
    Returns `(mutation, None)` when found and well-shaped, `(None,
    None)` when the method has no array index-assignment and no `new
    int/nat[..]` allocation at all (nothing for this row to do -- the
    caller falls back to the pre-decision-22 rules unchanged), or
    `(None, issue)` with a section-5 `(line, reason, token)` issue when
    array mutation/allocation IS present but not in a shape this row
    maps."""
    index_targets = _index_assign_targets(method)
    allocs = _alloc_bindings(method)

    bad_index = [(l, n) for l, n in index_targets if n is None]
    if bad_index:
        line = min(l for l, _ in bad_index)
        return None, (line, "array-mutation", "nested-or-field-index")

    good_alloc: dict[str, tuple[int, str, str]] = {}   # name -> (line, elem_kind, size_text)
    bad_alloc_names: set[str] = set()
    for line, name, rhs in allocs:
        if not _looks_like_array_new(rhs):
            continue  # object construction etc.: invisible to this row, as always
        parsed = _new_array_size_text(rhs)
        if parsed is None:
            bad_alloc_names.add(name)
            continue
        elem_kind, size_text = parsed
        if name not in good_alloc:
            good_alloc[name] = (line, elem_kind, size_text)

    mutated_names = {n for _, n in index_targets} | set(good_alloc)
    if not mutated_names and not bad_alloc_names:
        return None, None

    if bad_alloc_names and (bad_alloc_names & mutated_names or not mutated_names):
        # An allocation this row cannot map (array2, non-int/nat element,
        # jagged) that is also index-assigned or allocation-only: refused
        # by name here rather than falling through to the generic "local
        # array" `array` reason, so the reason names the real construct.
        line = min(l for l, n, _ in allocs if n in bad_alloc_names)
        return None, (line, "array", "array2-or-bad-element")

    if len(mutated_names) > 1:
        line = min([l for l, n in index_targets if n in mutated_names]
                    + [good_alloc[n][0] for n in mutated_names if n in good_alloc])
        return None, (line, "array-mutation", "multi-array-mutation")

    name = next(iter(mutated_names))
    param = next((p for p in method.params if p.name == name), None)

    if name in good_alloc:
        _, elem_kind, _ = good_alloc[name]
        if param is not None:
            # A parameter can never be the target of `:=`-to-a-`new` in
            # Dafny (in-parameters are not assignable); if the shim ever
            # sees one anyway, treat it as unmapped rather than guess.
            line = good_alloc[name][0]
            return None, (line, "array-mutation", "param-reallocated")
        return ArrayMutation(kind="alloc-fill", name=name, elem_kind=elem_kind), None

    # Otherwise: an index-assigned name with no matching allocation --
    # only a `modifies` PARAMETER is mapped; an index-assigned LOCAL with
    # no `new` (impossible to construct in well-typed Dafny -- a local
    # array must be initialised from `new` or another array-typed value,
    # and only the `new` case is one this row maps) falls through
    # unmapped.
    if param is None:
        line = min(l for l, n in index_targets if n == name)
        return None, (line, "array-mutation", "local-index-assign-no-alloc")
    if param.type is None or param.type.kind != "array" or param.type.nullable \
            or not _is_array_of_int(param.type):
        line = param.line
        return None, (line, "array", "array2-or-bad-element")

    modifies = [s for s in walk(method) if isinstance(s, ModifiesClause)]
    if not modifies:
        line = min(l for l, n in index_targets if n == name)
        return None, (line, "array-mutation", "missing-modifies")
    for mc in modifies:
        if isinstance(mc.exprs, Star):
            return None, (mc.line, "array-mutation", "modifies-other")
        if len(mc.exprs) != 1 or not (isinstance(mc.exprs[0], Ident) and mc.exprs[0].name == name):
            return None, (mc.line, "array-mutation", "modifies-other")

    if _array_passed_to_call(name, method, closure):
        # Aliasing: the mutated array is also read through another name
        # (passed as an argument somewhere in the closure), which this
        # shim cannot verify the callee's effect on.
        return None, (param.line, "array", "aliased")

    elem_kind = "nat" if param.type.args[0].kind == "nat" else "int"
    return ArrayMutation(kind="modifies-param", name=name, elem_kind=elem_kind), None


def _array_mutation_accepted_ids(method: MethodDecl, mutation: Optional[ArrayMutation],
                                  ret_param: Optional[Param]) -> frozenset[int]:
    """`id()`s of the `Old`/`Fresh`/`Slice` nodes decision 22 maps rather
    than refuses (the `id()`-set pattern `_self_call_positions` already
    uses for the same reason: a flat per-node scan has no context of its
    own, so the exemption is looked up by node identity instead).

    `old(a[k])` and `old(a[..])` on the ONE `modifies`-param array (`a`
    reads as the parameter both inside and outside `old` in t; the scope
    substitution that makes the OUTSIDE reading mean the return is
    `lift_rewrite.py`'s job, not this one's); `a[..]` with no `old`
    wrapper on that same name (post-state, reading as the return); and
    `fresh(b)` where `b` is the return of a `alloc-fill` method whose
    return type is `array<int|nat>` (SPEC.md: "`fresh(b)` on a returned
    array is dropped'')."""
    if mutation is None:
        return frozenset()
    ids: set[int] = set()
    if mutation.kind == "modifies-param":
        name = mutation.name
        for n in walk(method):
            if isinstance(n, Old):
                inner = n.arg
                if isinstance(inner, Index) and isinstance(inner.base, Ident) and inner.base.name == name:
                    ids.add(id(n))
                elif (isinstance(inner, Slice) and isinstance(inner.base, Ident)
                        and inner.base.name == name and inner.lo is None and inner.hi is None):
                    ids.add(id(n))
                    ids.add(id(inner))
            elif (isinstance(n, Slice) and isinstance(n.base, Ident)
                    and n.base.name == name and n.lo is None and n.hi is None):
                ids.add(id(n))
    elif mutation.kind == "alloc-fill" and ret_param is not None \
            and ret_param.type is not None and ret_param.type.kind == "array" \
            and not ret_param.type.nullable and _is_array_of_int(ret_param.type):
        for n in walk(method):
            if isinstance(n, Fresh) and isinstance(n.arg, Ident) and n.arg.name == ret_param.name:
                ids.add(id(n))
    return frozenset(ids)


# ---------------------------------------------------------------------------
# Liftable and classify.
# ---------------------------------------------------------------------------

@dataclass
class Liftable:
    method: MethodDecl
    closure: tuple[Decl, ...]
    rewrites: list[Rewrite] = field(default_factory=list)
    # Row 29 (2026-09-09, SPEC.md "Pairs (v1)"): the method's own two
    # out-parameters, in source order, when `classify` accepted a
    # `multi-return` shape as a pair (both component types supported);
    # `None` for every other method, single-return included. Carried
    # here rather than re-derived in `lift_rewrite.rewrite` from
    # `method.returns` alone, since a bare arity-2 `returns` clause is
    # not enough on its own -- classify already confirmed both
    # component types AND every other row-29 condition below.
    pair_returns: Optional[tuple[Param, Param]] = None


def _first(issues: list[tuple[int, str, str]]) -> tuple[int, str, str]:
    return min(issues, key=lambda t: t[0])


def classify(module: Module, method: MethodDecl) -> "Refusal | Liftable":
    issues: list[tuple[int, str, str]] = []
    rewrites: list[Rewrite] = []

    closure = _closure(module, method)
    scope_roots: list[Node] = [method] + list(closure)

    # -- bodyless method/function (section 5): a `body is None` node is
    # never guessed at by the classifier or rewriter (lift_ast.py's
    # MethodDecl/FunctionDecl docstrings); left unchecked, this reaches
    # lift_rewrite and crashes (`_desugar_returns(None, ...)`,
    # `_lift_expr(None, ...)`) instead of refusing (ex10_hoangkim's
    # bodyless `method q(x:nat, y:nat) returns (z:nat) requires .. ensures
    # ..` with no `{ }`, unreachable from `strange` so never itself
    # classified were it not also a gradable method in its own right). --
    if method.body is None:
        issues.append((method.line, "bodyless-method", method.name or "?"))
    for d in closure:
        if isinstance(d, FunctionDecl) and d.body is None:
            issues.append((d.line, "bodyless-function", d.name or "?"))

    # -- array mutation / allocation (decision 22), ahead of the
    # returns check: a `modifies-param` shape needs `method.returns`
    # empty to qualify (its synthesized return is the array; a method
    # that already returns something would need a SECOND return, which
    # t cannot express), so the zero-returns row below must see the
    # verdict first. --------------------------------------------------
    array_mutation, mutation_issue = find_array_mutation(method, closure)
    if mutation_issue is not None:
        issues.append(mutation_issue)
    if (array_mutation is not None and array_mutation.kind == "modifies-param"
            and len(method.returns) >= 1):
        # A method that ALREADY returns something (BubbleSort's own
        # `n`, removeElement's own `i`) and modifies an array in place
        # would need a SECOND return to also carry the array's final
        # value; t has exactly one. Demote back to "no mutation found"
        # so every check below falls back to its pre-decision-22 shape
        # (the read-only-array condition correctly refuses the param
        # for the write it truly has, and the modifies-clause check
        # fires too), rather than silently dropping the array's effect.
        issues.append((method.line, "array-mutation", "modifies-with-existing-return"))
        array_mutation = None

    # -- returns: zero/multi first (section 5) --------------------------
    # Row 29 (2026-09-09, SPEC.md "Pairs (v1)"): a `multi-return` shape
    # with EXACTLY two returns lifts to one pair-typed return, provided
    # BOTH components are types this lifter already carries as a return
    # (`_pair_component_issue`); three or more stays refused
    # `multi-return-arity` (the SPEC's own name for it), and an arity-two
    # method with an unsupported component (array, bitvector, real, map,
    # multiset, a nested Dafny tuple, or a bare char -- see that
    # function's own docstring) is `multi-return-nested`.
    pair_returns: Optional[tuple[Param, Param]] = None
    if len(method.returns) == 0:
        if array_mutation is None or array_mutation.kind != "modifies-param":
            issues.append((method.line, "zero-returns", method.name or "?"))
    elif len(method.returns) == 2:
        ret_a, ret_b = method.returns
        bad_a = _pair_component_issue(ret_a.type)
        bad_b = _pair_component_issue(ret_b.type)
        if bad_a is not None or bad_b is not None:
            bad_name = ret_a.name if bad_a is not None else ret_b.name
            issues.append((method.line, "multi-return-nested", bad_name))
        elif method.body is not None and any(
                isinstance(n, Assign) and len(n.targets) != len(n.values)
                for n in walk(method.body)):
            # A destructuring assign (`a, b := M(x);`, ONE value for TWO
            # targets, Dafny's own multi-return call-assignment sugar)
            # is not a shape `lift_rewrite._lift_stmt`'s general
            # multi-target Assign handling maps (it `zip`s targets
            # against values pairwise and would silently drop `b`'s
            # assignment) -- refused rather than mis-lifted; the only
            # way past every OTHER refusal (a call to a different
            # method already refuses `multi-method`/`calls-other-
            # method` elsewhere) is a SELF-recursive multi-return call,
            # absent from the corpus population this row measured.
            issues.append((method.line, "multi-return-nested", "destructuring-assign"))
        else:
            pair_returns = (ret_a, ret_b)
    elif len(method.returns) > 1:
        issues.append((method.line, "multi-return-arity", method.name or "?"))

    ret_param = method.returns[0] if len(method.returns) == 1 else None

    # -- param / return types --------------------------------------------
    array_params: list[Param] = []
    for p in method.params:
        if p.type is not None and p.type.kind == "array":
            if p.type.nullable or not _is_array_of_int(p.type):
                issues.append((p.line, "array", p.name))
            else:
                array_params.append(p)
            continue
        reason = _type_issue(p.type)
        if reason is not None:
            issues.append((p.line, reason, p.name))

    if ret_param is not None:
        rt = ret_param.type
        if rt is not None and rt.kind == "seq":
            # Rows 25-27 (2026-09-09): a `seq<int>`/`seq<nat>` return is
            # an ordinary seq return -- t has had these since decision
            # 22 opened "Sequences as values (v1)" -- so it no longer
            # refuses `seq-return` on element type alone (SPEC.md notes
            # this widening explicitly); a `seq<nat>` return carries no
            # per-element `>= 0` guarantee (t has none to give it, the
            # same gap decision 14 names for a `seq<nat>` LOCAL/PARAM,
            # deliberately accepted here as the weaker theorem). Row 28
            # (2026-09-09): `seq<char>` (`string` written that way) reads
            # the same as `seq<int>` too. Any other seq shape (nested,
            # bool) stays refused.
            if not (_is_seq_of_int(rt) or _is_seq_of_nat(rt) or _is_seq_of_char(rt)):
                issues.append((ret_param.line, "seq-return", ret_param.name))
        elif (rt is not None and rt.kind == "array" and not rt.nullable
                and _is_array_of_int(rt) and array_mutation is not None
                and array_mutation.kind == "alloc-fill"):
            pass  # decision 22: an allocated array return is a seq return
        else:
            reason = _type_issue(rt)
            if reason is not None and not (rt is not None and rt.kind == "nat"):
                issues.append((ret_param.line, reason, ret_param.name))

    # -- read-only array condition (decision 1 / 18.6) -------------------
    # the one array decision 22 accepts as mutated (if any) is validated
    # by `find_array_mutation` itself and skips this loop entirely.
    mutated_param_name = (array_mutation.name if array_mutation is not None
                           and array_mutation.kind == "modifies-param" else None)
    for p in array_params:
        if p.name == mutated_param_name:
            continue
        bad = array_readonly_issue(p.name, method, closure)
        if bad is not None:
            issues.append((p.line, bad, p.name))

    # -- modifies anywhere (method or a loop) => array-mutation, UNLESS
    # decision 22 already validated it as the one accepted modifies
    # clause (every `modifies` in `find_array_mutation` named exactly
    # the mutated array, so nothing here would add a new issue -- but a
    # `modifies` with no write at all, decision 14's own reason, is a
    # shape `find_array_mutation` never sees, so this stays live then). -
    if mutated_param_name is None:
        for n in walk(method):
            if isinstance(n, ModifiesClause):
                issues.append((n.line, "array-mutation", "modifies"))

    # -- everything a single generic pass over every node can catch ------
    closure_names = {d.name for d in closure if d.name}
    method_names = {d.name for d in module.decls if isinstance(d, MethodDecl) and d.name}
    null_checks = scan_null_checks(method)
    accepted_ids = (_array_mutation_accepted_ids(method, array_mutation, ret_param)
                     | frozenset(id(m) for _, _, m in null_checks))
    for root in scope_roots:
        for n in walk(root):
            _scan_node_for_issues(n, issues, method.name, closure_names, method_names, accepted_ids)

    # -- sequences: literal, concat, slice (rows 25-27, 2026-09-09) ------
    # `SeqDisplay`/`Slice`/a `+` on seqs used to be unconditional
    # refusals (`_scan_node_for_issues`, before this row); now each
    # fires only when this row cannot actually map it, using
    # `_build_kind_env`'s best-effort typing. A slice needs one more
    # check `_scan_node_for_issues` cannot make on its own: decision
    # 22's own `array-mutation`'s ONE mutated array still refuses a
    # BOUNDED slice of itself (`a[lo..hi]`, `a[lo..]`, `a[..hi]` --
    # only its unbounded `a[..]`, already exempted via `accepted_ids`,
    # maps); every OTHER seq-typed receiver (a read-only array
    # parameter, a seq local/parameter/return, a slice-of-a-slice) now
    # lifts the same way a plain seq does, per SPEC.md's own note that
    # `a[..]` on an array parameter "is the parameter itself, unchanged".
    kind_env = _build_kind_env(method, closure)
    char_names, char_seq_names = _build_char_names(method, closure)
    mutated_array_name = array_mutation.name if array_mutation is not None else None
    for root in scope_roots:
        for n in walk(root):
            if isinstance(n, SeqDisplay):
                bad = _seq_literal_issue(n, kind_env)
                if bad is not None:
                    issues.append((n.line, bad, "[...]"))
                else:
                    rewrites.append(Rewrite(rule="seq-literal-lifted", line=n.line))
            elif isinstance(n, Slice):
                if id(n) in accepted_ids:
                    continue  # decision 22's own unbounded exemption, unchanged
                if (mutated_array_name is not None and isinstance(n.base, Ident)
                        and n.base.name == mutated_array_name):
                    issues.append((n.line, "seq-slice", "[..]"))
                elif expr_kind(n.base, kind_env.get) == "seq":
                    if n.lo is None and n.hi is None:
                        rewrites.append(Rewrite(rule="whole-slice-as-seq", line=n.line))
                    else:
                        rewrites.append(Rewrite(rule="seq-slice-lifted", line=n.line))
                else:
                    issues.append((n.line, "seq-slice", "[..]"))
            elif isinstance(n, Binary) and n.op in ("+", "-") and (
                    _is_char_expr(n.left, char_names, char_seq_names)
                    or _is_char_expr(n.right, char_names, char_seq_names)):
                # Row 28: `char + char`/`char - char` verify on dafny
                # 4.11.0 with an overflow/underflow proof obligation
                # (measured: t8/t9.dfy above), a fact t's plain,
                # unbounded int addition/subtraction has no way to
                # state; refused rather than silently widened into an
                # int op that drops the obligation. (Only `+`/`-` are
                # ever reachable here: `*`/`/`/`%` on char is a Dafny
                # TYPE ERROR, measured, so classify never sees one.)
                # Checked BEFORE the plain `+` seq/int reading below,
                # since a char operand types "int" under `expr_kind`
                # (row 28 folds char into int there on purpose) and
                # would otherwise silently pass as ordinary arithmetic.
                issues.append((n.line, "char-arith", n.op))
            elif isinstance(n, Binary) and n.op == "+":
                lk = expr_kind(n.left, kind_env.get)
                rk = expr_kind(n.right, kind_env.get)
                if lk == "seq" and rk == "seq":
                    rewrites.append(Rewrite(rule="seq-concat-lifted", line=n.line))
                elif lk == "int" and rk == "int":
                    pass  # ordinary arithmetic, unaffected by rows 25-27
                else:
                    issues.append((n.line, "seq-typing", "+"))
            elif isinstance(n, Chain) and len(n.ops) == 1 and n.ops[0] in ("<", "<=", ">", ">="):
                # Row 28: an ORDER comparison on a seq-typed operand --
                # measured on dafny 4.11.0 to be "proper prefix"/"prefix"
                # semantics, not the lexicographic order a first guess
                # (and the task's own framing) would assume ("ac" < "b"
                # and "b" < "ac" both false) -- is not an operator t has
                # on seqs at all (SPEC.md: "Lexicographic order on
                # strings is not an operator"), string or plain seq<int>
                # alike; `_lift_chain` would otherwise print it straight
                # through as an int comparison with no complaint, since a
                # single relational op is never type-checked there.
                if (expr_kind(n.operands[0], kind_env.get) == "seq"
                        or expr_kind(n.operands[1], kind_env.get) == "seq"):
                    issues.append((n.line, "string-lib", n.ops[0]))
            elif isinstance(n, (CharLit, StringLit)):
                bad = (decode_char_literal(n.text) if isinstance(n, CharLit)
                       else decode_string_literal(n.text))
                if bad is None:
                    issues.append((n.line, "char-literal-nonbmp", n.text))
            elif isinstance(n, Cast):
                # Row 28: `Cast` handling MOVED here from
                # `_scan_node_for_issues` in full (see that function's own
                # docstring) -- every cast, accepted or not, is decided in
                # this one place now. `char as int` is always the
                # identity (a char already IS its code point); `int as
                # char` only when `_char_cast_safe` can see the operand
                # is already one (a literal in range, or a cast back);
                # every other cast (`as nat`, `as real`, an unsafe `as
                # char`, ...) keeps the old, generic `as-cast` refusal.
                if n.type.kind == "char":
                    if _char_cast_safe(n.base, char_names, char_seq_names):
                        rewrites.append(Rewrite(rule="int-as-char-lifted", line=n.line))
                    else:
                        issues.append((n.line, "char-cast-unbounded", "as char"))
                elif n.type.kind == "int" and _is_char_expr(n.base, char_names, char_seq_names):
                    rewrites.append(Rewrite(rule="char-as-int-lifted", line=n.line))
                else:
                    issues.append((n.line, "as-cast", "as"))

    # -- definite assignment of the return, every path (section 4.7) -----
    if ret_param is not None and method.body is not None:
        if not _assigns_ret_all_paths(method.body, ret_param.name):
            issues.append((method.line, "return-not-assigned-on-all-paths",
                            ret_param.name))
    # Row 29: the SAME check, once per out-parameter -- `_assigns_ret_
    # all_paths` already treats a `return e1, e2;` (any non-empty
    # ReturnStmt.values) as assigning whichever single `ret_name` it is
    # asked about, so calling it twice (once per component name) is
    # correct with no change to the helper itself.
    if pair_returns is not None and method.body is not None:
        ret_a, ret_b = pair_returns
        if not _assigns_ret_all_paths(method.body, ret_a.name):
            issues.append((method.line, "return-not-assigned-on-all-paths", ret_a.name))
        if not _assigns_ret_all_paths(method.body, ret_b.name):
            issues.append((method.line, "return-not-assigned-on-all-paths", ret_b.name))

    # -- self-recursion shape (section 4.5's `r := M(args)` row) ---------
    issues += _self_call_positions(method)

    # -- returns (tail vs early-exit) ------------------------------------
    if method.body is not None:
        ri, rr = scan_returns(method.body, True)
        issues += ri
        tail_lines = [l for l, k in rr if k == "tail"]
        early_lines = [l for l, k in rr if k == "early"]
        if tail_lines:
            rewrites.append(Rewrite(rule="tail-return", line=tail_lines[0]))
        if early_lines:
            rewrites.append(Rewrite(rule="early-exit-return", line=early_lines[0]))

    # -- breaks (row 23, 2026-09-09) --------------------------------------
    if method.body is not None:
        bi, ba = scan_breaks(method.body)
        issues += bi
        if ba:
            rewrites.append(Rewrite(rule="break-as-return", line=ba[0][0].line))
            dup = next((node for node, _loop, cont in ba if cont), None)
            if dup is not None:
                rewrites.append(Rewrite(rule="break-continuation-duplicated", line=dup.line))

    # -- null checks on a non-nullable array (row 24, 2026-09-09) --------
    if null_checks:
        rewrites.append(Rewrite(rule="null-check-dropped", line=null_checks[0][1].line))

    # -- quantifier boundedness -------------------------------------------
    for root in scope_roots:
        for n in walk(root):
            if isinstance(n, Quantifier):
                got = bound_quantifier(n)
                if got is None:
                    issues.append((n.line, "unbounded-quantifier", n.kind))
                else:
                    has_mem = any(mem is not None for _, _, _, mem in got["binders"])
                    rewrites.append(Rewrite(rule="in-desugared" if has_mem
                                             else "quantifier-bounded", line=n.line))

    # -- mutual recursion ---------------------------------------------------
    mr = _mutual_recursion_issue(closure)
    if mr is not None:
        issues.append(mr)

    # -- function-contract (a `reads` clause on any closure function) ----
    for d in closure:
        if isinstance(d, FunctionDecl):
            for s in d.specs:
                if isinstance(s, ReadsClause):
                    nonempty = isinstance(s.exprs, Star) or (isinstance(s.exprs, tuple) and s.exprs)
                    if nonempty:
                        issues.append((s.line, "function-contract", d.name or "?"))

    # -- decreases inference (section 6 / decision 11) --------------------
    dec_issues = _decreases_issues(method, closure)
    issues += dec_issues

    if issues:
        line, reason, token = _first(issues)
        return Refusal(reason=reason, token=token, line=line, stage="classify")

    # -- plan the remaining rewrites (chains, iff, nat, split, etc.) ------
    rewrites += _plan_rewrites(module, method, closure, ret_param, array_params,
                                mutated_param_name, array_mutation)

    return Liftable(method=method, closure=closure, rewrites=rewrites, pair_returns=pair_returns)


def _scan_node_for_issues(n: Node, issues: list, method_name: str,
                           closure_names: set[str],
                           method_names: set[str] = frozenset(),
                           accepted_ids: frozenset[int] = frozenset()) -> None:
    """One generic pass catching every section-5 row that is a plain
    "does this construct appear anywhere" test. Rows needing context
    (self-recursion shape, tail returns, quantifier bounds, decreases,
    the read-only-array condition, decision 22's array mutation) have
    their own dedicated scans; `accepted_ids` (from
    `_array_mutation_accepted_ids`, unioned with `scan_null_checks`'s
    row-24 matches) is decision 22's (and row 24's) way of exempting the
    specific `Old`/`Fresh`/`Slice`/`null`-`Ident` nodes they map rather
    than refuse, by identity, since this scan otherwise has no context
    of its own.

    `Binary` nodes with op `/` or `%` are no longer refused here: SPEC.md
    "Division and modulo (v1)" (2026-09-08) gives t Euclidean `div`/`mod`,
    the same convention Dafny's own `/` and `%` use on `int` (measured on
    dafny 4.11.0), so `lift_rewrite.py` maps them one to one and no
    div-mod issue is raised. `SeqDisplay`, `Slice` and a `+` on seqs are
    likewise no longer refused unconditionally here: rows 25-27
    (2026-09-09) have their own dedicated, type-aware pass in `classify`
    (`_build_kind_env`/`expr_kind`), since deciding whether they fire
    needs more context (the method's own param/return/local types) than
    this generic per-node scan carries. `Cast` is no longer refused here
    either, same reason, same move: row 28 (2026-09-09) needs to know
    whether a cast's OWN operand is char-typed (`char as int`, always
    safe; `int as char`, safe only when the operand is visibly already a
    code point) before it can tell an accepted char cast from every
    other cast this lifter still refuses `as-cast` (`as nat`, `as real`,
    ...), so ALL `Cast` handling, accepted and refused alike, moved to
    that same dedicated pass."""
    if isinstance(n, SeqUpdate):
        issues.append((n.line, "seq-update", ":="))
    elif isinstance(n, (Old, Fresh)):
        if id(n) not in accepted_ids:
            issues.append((n.line, "old", "old"))
    elif isinstance(n, Ident) and n.name == "null":
        # `a != null`, `a == null`: the parser has no dedicated NullLit
        # node (section 3's shim keeps `null` a bare Ident), but it is a
        # heap fact t has no word for -- an array param compared to null
        # (minArray, FindMax) (LIFTER-DESIGN.md section 5's `heap` row).
        # Row 24 (2026-09-09): `accepted_ids` also carries the `null`
        # Ident of every `x != null` `scan_null_checks` accepted (`x` a
        # non-nullable `array<int|nat>` param/return, in a whole-clause
        # or top-level `&&`-conjunct position) -- a tautology Dafny
        # proves trivially, dropped rather than refused. Everything
        # else (a nullable `array?`, a class/object, `==`, or the same
        # comparison anywhere but a safe clause position) still refuses.
        if id(n) not in accepted_ids:
            issues.append((n.line, "heap", "null"))
    elif isinstance(n, AssumeStmt):
        issues.append((n.line, "assume", "assume"))
    elif isinstance(n, AssignSuchThat):
        issues.append((n.line, "such-that-exec", ":|"))
    elif isinstance(n, PrintStmt):
        issues.append((n.line, "io", "print"))
    elif isinstance(n, ExpectStmt):
        issues.append((n.line, "io", "expect"))
    elif isinstance(n, (IfCaseStmt, WhileCaseStmt)):
        issues.append((n.line, "nondet", "case"))
    elif isinstance(n, IfStmt) and isinstance(n.cond, Star):
        issues.append((n.line, "nondet", "*"))
    elif isinstance(n, WhileStmt) and isinstance(n.cond, Star):
        issues.append((n.line, "nondet", "*"))
    elif isinstance(n, Assign) and any(isinstance(v, Star) for v in n.values):
        issues.append((n.line, "nondet", "*"))
    elif isinstance(n, VarDeclStmt) and n.names and any(
            nm.type is not None and nm.type.kind == "array" for nm in n.names):
        issues.append((n.line, "array", "local array"))
    elif isinstance(n, MapDisplay):
        issues.append((n.line, "map", "{...}"))
    elif isinstance(n, SetDisplay):
        issues.append((n.line, "set", "{...}"))
    elif isinstance(n, Comprehension) and n.kind == "set":
        issues.append((n.line, "set", "set-comprehension"))
    elif isinstance(n, Comprehension) and n.kind == "map":
        issues.append((n.line, "map", "map-comprehension"))
    elif isinstance(n, Comprehension) and n.kind == "seq":
        issues.append((n.line, "seq-comprehension", "seq-comprehension"))
    elif isinstance(n, TupleExpr):
        issues.append((n.line, "tuple", "(...)"))
    elif isinstance(n, TypeTest):
        issues.append((n.line, "as-cast", "is"))
    elif isinstance(n, Member) and n.name != "Length":
        issues.append((n.line, "datatype", n.name))
    elif isinstance(n, VarDeclStmt) and n.ghost:
        issues.append((n.line, "ghost-local", "ghost var"))
    elif isinstance(n, CallStmt):
        if n.name == method_name:
            issues.append((n.line, "self-call-lazy", n.name))
        elif n.name not in closure_names:
            issues.append((n.line, "calls-other-method", n.name))
        # else: a lemma call in the closure -- dropped, not refused
        # (decision 8; see _plan_rewrites' lemma-call-dropped entry).
    elif (isinstance(n, Call) and isinstance(n.fn, Ident)
          and n.fn.name != method_name and n.fn.name in method_names):
        # `x := M(args)` / `var x := M(args)` / any other expression
        # position naming a DIFFERENT method (section 4.5's row; a
        # same-named self-call is section 4.5's own rewrite, handled by
        # `_self_call_positions`, and a call of a closure function is an
        # ordinary spec_fun application, not this row at all).
        issues.append((n.line, "calls-other-method", n.fn.name))


def _self_call_positions(method: MethodDecl) -> list[tuple[int, str, str]]:
    """Section 4.5's `r := M(args)` row: a self-call is only supported as
    the WHOLE right-hand side of a plain assignment, or inside a spec
    clause -- and even there, never under a lazily evaluated operator or a
    quantifier body (`self-call-lazy`). Everything else (a self-call
    nested in an if/while condition, or as a bare discarded call
    statement) is refused the same way."""
    name = method.name
    issues: list[tuple[int, str, str]] = []
    allowed_roots: list[Expr] = []
    if method.body is not None:
        for s in walk(method.body):
            if isinstance(s, Assign):
                allowed_roots.extend(v for v in s.values if isinstance(v, Expr))
            elif isinstance(s, VarDeclStmt) and s.init:
                allowed_roots.extend(v for v in s.init if isinstance(v, Expr))
    for spec in method.specs:
        e = getattr(spec, "expr", None)
        if e is not None:
            allowed_roots.append(e)

    allowed_ids = {id(n) for root in allowed_roots for n in walk(root)}

    def lazy_ids(root) -> set[int]:
        lz: set[int] = set()
        for n in walk(root):
            if isinstance(n, NaryBool):
                for a in n.args[1:]:
                    lz |= {id(x) for x in walk(a)}
            elif isinstance(n, Implies):
                lz |= {id(x) for x in walk(n.right)}
            elif isinstance(n, Quantifier):
                lz |= {id(x) for x in walk(n.body)}
        return lz

    lazy = set()
    for root in allowed_roots:
        lazy |= lazy_ids(root)

    def is_self_call(n) -> bool:
        return isinstance(n, Call) and isinstance(n.fn, Ident) and n.fn.name == name

    if method.body is not None:
        for n in walk(method.body):
            if is_self_call(n):
                if id(n) not in allowed_ids or id(n) in lazy:
                    issues.append((n.line, "self-call-lazy", name))
    for spec in method.specs:
        e = getattr(spec, "expr", None)
        if e is None:
            continue
        lz = lazy_ids(e)
        for n in walk(e):
            if is_self_call(n) and id(n) in lz:
                issues.append((n.line, "self-call-lazy", name))
    return issues


def _decreases_issues(method: MethodDecl, closure: tuple[Decl, ...]
                       ) -> list[tuple[int, str, str]]:
    from lift_ast import Binary
    issues: list[tuple[int, str, str]] = []

    def assigned_names(body) -> set[str]:
        names: set[str] = set()
        for n in walk(body):
            if isinstance(n, Assign):
                for t in n.targets:
                    if t.kind == "name":
                        names.add(t.name)
        return names

    for n in walk(method.body):
        if isinstance(n, WhileStmt):
            dcs = [s for s in n.specs if isinstance(s, DecreasesClause)]
            if not dcs:
                issues.append((n.line, "uninferable-decreases", "while"))
                continue
            dc = dcs[0]
            if isinstance(dc.exprs, Star):
                issues.append((dc.line, "decreases-star", "*"))
                continue
            exprs = dc.exprs
            if len(exprs) > 1:
                assigned = assigned_names(n.body)
                kept = [e for e in exprs if not (isinstance(e, Ident) and e.name not in assigned)]
                if len(kept) == 0:
                    issues.append((dc.line, "lexicographic-decreases", "decreases"))
                elif len(kept) >= 2 and not all(_is_int_expr_guess(e) for e in kept):
                    issues.append((dc.line, "lexicographic-decreases", "decreases"))
    for d in closure:
        if isinstance(d, FunctionDecl):
            dcs = [s for s in d.specs if isinstance(s, DecreasesClause)]
            if dcs:
                dc = dcs[0]
                if isinstance(dc.exprs, Star):
                    issues.append((dc.line, "decreases-star", "*"))
                elif len(dc.exprs) > 1:
                    calls = [c for c in walk(d.body) if isinstance(c, Call)
                             and isinstance(c.fn, Ident) and c.fn.name == d.name]
                    param_names = [p.name for p in d.params]
                    dropped = unchanged_at_every_call(param_names, calls, len(dc.exprs))
                    kept_idx = [i for i in range(len(dc.exprs)) if i not in dropped]
                    if len(kept_idx) == 0:
                        issues.append((dc.line, "lexicographic-decreases", d.name or "?"))
            # else: rprint always prints one; absence would be
            # uninferable-decreases, but for a spec_fun that never
            # self-calls no decreases is needed at all (no issue).

    # -- method-level decreases (section 4.5's `r := M(args)` self-call
    # row): a self-recursive method needs the same tuple-projection
    # pre-check as a closure FunctionDecl gets above, done here rather
    # than left to lift_rewrite so a tuple that neither projects nor
    # sums is refused instead of crashing on an empty component list
    # (mystery1/mystery2, decreases n, m with neither ever assigned). --
    if method.body is not None:
        self_calls = [c for c in walk(method.body) if isinstance(c, Call)
                      and isinstance(c.fn, Ident) and c.fn.name == method.name]
        if self_calls:
            dcs = [s for s in method.specs if isinstance(s, DecreasesClause)]
            if not dcs:
                issues.append((method.line, "uninferable-decreases", method.name or "?"))
            else:
                dc = dcs[0]
                if isinstance(dc.exprs, Star):
                    issues.append((dc.line, "decreases-star", "*"))
                elif len(dc.exprs) > 1:
                    param_names = [p.name for p in method.params]
                    dropped = unchanged_at_every_call(param_names, self_calls, len(dc.exprs))
                    kept_idx = [i for i in range(len(dc.exprs)) if i not in dropped]
                    if len(kept_idx) == 0:
                        issues.append((dc.line, "lexicographic-decreases", method.name or "?"))
    return issues


def _is_int_expr_guess(e: Expr) -> bool:
    return True  # section 6: "if several remain and all are int" -- our
    # shim has no static type checker, so any surviving component is
    # accepted as summable; a genuinely non-int component (a seq, say)
    # would already have been refused earlier by the type checks.


# ---------------------------------------------------------------------------
# Rewrite planning (the Liftable.rewrites summary; lift_rewrite.py performs
# the mechanics itself using the same detectors, per the module docstring).
# ---------------------------------------------------------------------------

def _plan_rewrites(module: Module, method: MethodDecl, closure: tuple[Decl, ...],
                    ret_param: Optional[Param], array_params: list[Param],
                    mutated_param_name: Optional[str] = None,
                    array_mutation: Optional[ArrayMutation] = None
                    ) -> list[Rewrite]:
    from lift_ast import Binary
    out: list[Rewrite] = []

    for p in method.params:
        if _is_nat(p.type):
            out.append(Rewrite(rule="nat-param-guard", line=p.line))
    if ret_param is not None and _is_nat(ret_param.type):
        out.append(Rewrite(rule="nat-return-ensures", line=ret_param.line))

    nat_names = {p.name for p in method.params if _is_nat(p.type)}
    if ret_param is not None and _is_nat(ret_param.type):
        nat_names.add(ret_param.name)
    for n in walk(method.body):
        if isinstance(n, VarDeclStmt):
            for nm in n.names:
                if _is_nat(nm.type):
                    nat_names.add(nm.name)
    for n in walk(method.body):
        if isinstance(n, WhileStmt):
            assigned = {t.name for s in walk(n.body) if isinstance(s, Assign)
                        for t in s.targets if t.kind == "name"}
            hit = nat_names & assigned
            if hit:
                out.append(Rewrite(rule="nat-invariant-added", line=n.line))

    for p in array_params:
        if p.name == mutated_param_name:
            continue
        out.append(Rewrite(rule="array-readonly-as-seq", line=p.line))

    if array_mutation is not None:
        out.append(Rewrite(rule="array-mutation-as-seq", line=method.line))

    for d in closure:
        if isinstance(d, FunctionDecl):
            has_req = any(isinstance(s, RequiresClause) for s in d.specs)
            has_nat_param = any(_is_nat(p.type) for p in d.params)
            if has_req or has_nat_param:
                out.append(Rewrite(rule="spec-fun-totalised", line=d.line))
            if any(_is_nat(p.type) for p in d.params) is False and d.ret_type is not None and d.ret_type.kind == "nat":
                pass
            if d.ret_type is not None and d.ret_type.kind == "nat":
                out.append(Rewrite(rule="nat-result-fact-dropped", line=d.line))

    for n in walk(method):
        if isinstance(n, Chain) and len(n.ops) >= 2:
            out.append(Rewrite(rule="chain-desugared", line=n.line))
        elif isinstance(n, Iff):
            out.append(Rewrite(rule="iff-to-eq", line=n.line))

    for spec in method.specs:
        if isinstance(spec, EnsuresClause) and isinstance(spec.expr, NaryBool) and spec.expr.op == "&&":
            out.append(Rewrite(rule="split-conjuncts", line=spec.line))
    for spec in method.specs:
        if isinstance(spec, RequiresClause) and isinstance(spec.expr, NaryBool) and spec.expr.op == "&&":
            out.append(Rewrite(rule="split-conjuncts", line=spec.line))

    for n in walk(method.body):
        if isinstance(n, Assign) and len(n.targets) > 1:
            out.append(Rewrite(rule="parallel-assign-temps", line=n.line))
        elif isinstance(n, VarDeclStmt) and n.init is None:
            out.append(Rewrite(rule="default-init", line=n.line))
        elif isinstance(n, ForStmt):
            out.append(Rewrite(rule="for-desugared", line=n.line))

    for n in walk(method):
        if isinstance(n, AssertStmt):
            out.append(Rewrite(rule="assert-dropped", line=n.line))
        elif isinstance(n, AssertByStmt):
            out.append(Rewrite(rule="assert-dropped", line=n.line))
        elif isinstance(n, CalcStmt):
            out.append(Rewrite(rule="assert-dropped", line=n.line))
        elif isinstance(n, RevealStmt):
            out.append(Rewrite(rule="assert-dropped", line=n.line))
        elif isinstance(n, ForallStmt):
            out.append(Rewrite(rule="assert-dropped", line=n.line))
        elif isinstance(n, CallStmt):
            out.append(Rewrite(rule="lemma-call-dropped", line=n.line))

    for d in closure:
        if isinstance(d, FunctionDecl) and any(isinstance(s, EnsuresClause) for s in d.specs):
            out.append(Rewrite(rule="function-ensures-dropped", line=d.line))

    for d in module.decls:
        if isinstance(d, MethodDecl) and d.name == "Main":
            out.append(Rewrite(rule="main-dropped", line=d.line))

    reachable_names = {d.name for d in closure if d.name}
    for d in module.decls:
        if (isinstance(d, (FunctionDecl, LemmaDecl)) and d is not method
                and (d.name not in reachable_names)):
            out.append(Rewrite(rule="unused-function-dropped", line=d.line))

    return out


def _gradable_methods_fallback(module: Module) -> list[MethodDecl]:
    """Decision 9's own one-line rule, used only if `lift_parse
    .gradable_methods` is not yet implemented (it is this module's stub
    sibling's job; see `classify_all`'s docstring)."""
    return [d for d in module.decls
            if isinstance(d, MethodDecl) and d.name != "Main"
            and any(isinstance(s, EnsuresClause) for s in d.specs)]


def classify_all(module: Module) -> dict[str, "Refusal | Liftable"]:
    """Classify every gradable method in `module` (via
    `lift_parse.gradable_methods`), keyed by method name.

    A file with several gradable methods (decision 9) gets one entry per
    method here, never a single file-level verdict; a file-level
    `split-per-method` label (section 5's row for `multi-method`) is
    reported by the caller from `len(result) > 1`, not by this function,
    which never returns anything but per-method verdicts."""
    try:
        import lift_parse
        methods = lift_parse.gradable_methods(module)
    except NotImplementedError:
        methods = _gradable_methods_fallback(module)
    return {m.name: classify(module, m) for m in methods}


# ---------------------------------------------------------------------------
# Definite assignment of the return, on every path (section 4.7). A
# best-effort structural mirror of Dafny's own check: true iff every
# straight-line path through `stmts` assigns `ret_name` somewhere (a loop
# never counts, since it may run zero times; an `if` counts only when BOTH
# branches do, recursively; a tail `return e`/`return r`/`return;` counts
# exactly when the source's own return-elaboration (section 4.5) would make
# it into an assignment of `ret_name` or relies on one already having run).
# ---------------------------------------------------------------------------

def _assigns_ret_all_paths(stmts: tuple[Stmt, ...], ret_name: str) -> bool:
    assigned = False
    for s in stmts:
        if assigned:
            continue
        if isinstance(s, Assign):
            if any(t.kind == "name" and t.name == ret_name for t in s.targets):
                assigned = True
        elif isinstance(s, IfStmt):
            then_ok = _assigns_ret_all_paths(s.then, ret_name)
            if isinstance(s.else_, tuple):
                else_ok = _assigns_ret_all_paths(s.else_, ret_name)
            elif isinstance(s.else_, IfStmt):
                else_ok = _assigns_ret_all_paths((s.else_,), ret_name)
            else:
                else_ok = False
            if then_ok and else_ok:
                assigned = True
        elif isinstance(s, BlockStmt):
            if _assigns_ret_all_paths(s.body, ret_name):
                assigned = True
        elif isinstance(s, LabelStmt):
            if _assigns_ret_all_paths((s.stmt,), ret_name):
                assigned = True
        elif isinstance(s, ReturnStmt) and s.values:
            assigned = True  # tail `return e` (section 4.5) becomes `r := e`
        # WhileStmt / ForStmt: never counted (may execute zero times).
    return assigned


def unchanged_at_every_call(param_names: list[str], calls: list, n: int) -> set[int]:
    """Decision 11's function-tuple projection test: component `i` is
    dropped only when it is passed through UNCHANGED (the same-named
    identifier, in the same position) AT EVERY self-call found, not merely
    at one of them (gcd's `gcd(x-y, y)` and `gcd(x, y-x)`: `y` is
    unchanged only in the first call and `x` only in the second, so
    NEITHER is dropped and both survive into `guess:sum`, matching
    section 6's own worked example)."""
    if not calls:
        return set()
    unchanged = set(range(n))
    for c in calls:
        this_call = set()
        for i, (pn, arg) in enumerate(zip(param_names, c.args)):
            if isinstance(arg, Ident) and arg.name == pn:
                this_call.add(i)
        unchanged &= this_call
    return unchanged
