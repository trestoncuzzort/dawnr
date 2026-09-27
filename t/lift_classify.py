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

import lift_let
from lift_ast import (
    Assign, AssignSuchThat, AssertStmt, AssertByStmt, AssumeStmt, Binary,
    BlockStmt, BoolLit, BreakStmt, Call, CallStmt, CalcStmt, Cardinality,
    Cast, Chain, CharLit, ContinueStmt, Decl, DecreasesClause, EnsuresClause, Expr,
    ExpectStmt, ForStmt, ForallStmt, FunctionDecl, Fresh, Iff, IfCaseStmt,
    IfExpr, IfStmt, Implies, Index, Ident, IntLit, InvariantClause,
    LabelStmt, LemmaDecl, LetExpr, Lhs, MapDisplay, Member, MethodDecl,
    ModifiesClause, Module, NaryBool, NewRhs, Node, Old, Param, PrintStmt,
    Quantifier, ReadsClause, Refusal, RequiresClause, RevealStmt,
    ReturnStmt, Rewrite, SeqDisplay, SeqUpdate, SetDisplay, SkippedDecl,
    Slice, Spec, Star, Stmt, StringLit, TupleExpr, Type, TypeTest, Unary,
    VarDeclStmt, WhileCaseStmt, WhileStmt, Comprehension, RealLit,
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


def _is_seq_fun_result(t: Optional[Type]) -> bool:
    """Row 49 (2026-09-27, SPEC.md "Seq-valued spec_funs (v1)"): the
    Dafny function result types that lift to a spec_fun's `"seq"` result:
    `string`, `seq<char>` (row 28's code points), `seq<int>`, `seq<nat>`.
    One level only: a nested seq result is not in v1."""
    return (t is not None
            and (t.kind == "string" or _is_seq_of_int(t) or _is_seq_of_char(t)))


def _type_text(t: Type) -> str:
    """A type's Dafny-like spelling for a refusal token (`seq<string>`)."""
    if t.args:
        return f"{t.kind}<{', '.join(_type_text(a) for a in t.args)}>"
    return t.kind


def _is_seq_of_char(t: Optional[Type]) -> bool:
    # Row 28 (2026-09-09, SPEC.md "Strings as sequences of code points
    # (v1)"): `seq<char>` written that way is `string` by another name
    # ("string of anything nested is not", the task's own words) -- one
    # level of char elements only, the same one-level rule
    # `_is_seq_of_int`/`_is_seq_of_nat` already carry.
    return (t is not None and t.kind == "seq" and len(t.args) == 1
            and _is_char(t.args[0]))


def _is_nested_seq_of_int(t: Optional[Type]) -> bool:
    # Row 30 (2026-09-10, SPEC.md "Nested sequences (v1)"): `seq<seq<int>>`,
    # one level of nesting, int rows -- t's `{"seq": "seq"}`.
    return (t is not None and t.kind == "seq" and len(t.args) == 1
            and t.args[0].kind == "seq" and len(t.args[0].args) == 1
            and t.args[0].args[0].kind == "int")


def _is_nested_seq_of_nat(t: Optional[Type]) -> bool:
    # Row 30: `seq<seq<nat>>`, the same one level of nesting, nat rows.
    return (t is not None and t.kind == "seq" and len(t.args) == 1
            and t.args[0].kind == "seq" and len(t.args[0].args) == 1
            and t.args[0].args[0].kind == "nat")


def _is_nested_seq_of_char(t: Optional[Type]) -> bool:
    # Row 43 (2026-09-27, t/FEATURES-TRACK.md, nested string sequences):
    # `seq<string>` or `seq<seq<char>>`, one level of nesting whose rows
    # are strings -- t's `{"seq": "seq"}` with code-point rows, row 28's
    # string-as-seq applied per row exactly as row 30 applies int rows.
    return (t is not None and t.kind == "seq" and len(t.args) == 1
            and (t.args[0].kind == "string" or _is_seq_of_char(t.args[0])))


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
        # Row 30 (2026-09-10, SPEC.md "Nested sequences (v1)"): one level
        # of seq-of-seq nesting, int/nat rows, is t's own `{"seq": "seq"}`.
        # A `seq<seq<nat>>` row gets the same non-negativity gap a bare
        # `seq<nat>` param/local already has above (no per-row guard this
        # lifter can add), refused `nat-seq-elements` the same way; a
        # RETURN's own weaker-theorem exemption for that gap lives in
        # `classify`'s return-handling branch, not here, mirroring how a
        # flat `seq<nat>` return is already exempted there. Refused by
        # name otherwise: `seq-of-bool` (`seq<bool>`, one level), `nested-
        # seq-string` (`seq<string>`, `seq<seq<char>>`), `nested-seq-deep`
        # (three levels or more), `array` (`seq<array<..>>`, row 22's own
        # territory, not a seq-nesting question), `nested-seq-other`
        # (anything else: `seq<seq<bool>>`, `seq<seq<real>>`, ...).
        row = t.args[0] if len(t.args) == 1 else None
        if row is not None and row.kind == "seq" and len(row.args) == 1:
            leaf = row.args[0]
            if leaf.kind == "nat":
                return "nat-seq-elements"
            if leaf.kind == "int":
                return None
            if leaf.kind == "char":
                return None  # row 43: `seq<seq<char>>`, a row of code points
            if leaf.kind in ("seq", "string"):
                return "nested-seq-deep"  # a string is itself a seq: three levels
            # Row 46 (2026-09-27): the row's own element names the refusal,
            # `seq<seq<real>>` as `seq<real>` does one level down.
            return _seq_element_issue(leaf) or "nested-seq-other"
        if row is not None and row.kind == "bool":
            return "seq-of-bool"
        if row is not None and row.kind == "string":
            return None  # row 43: `seq<string>`, the same nested seq
        # Row 46 (2026-09-27, t/FEATURES-TRACK.md, nested-seq-other): the
        # 2026-09-27 census of the 143 methods this branch used to fold
        # into `nested-seq-other` is dominated by element types t has no
        # value for at all -- `seq<real>` (the numpy-shaped vericoding
        # files), `seq<bv32>`, `seq<(int, int)>`, `seq<T>` under a type
        # parameter, `seq<Datatype>` -- none of them a seq-NESTING question.
        # Each now refuses under the element's own name (`seq-of-real`,
        # `seq-of-bitvector`, `seq-of-pair`, `seq-of-datatype`, `seq-of-
        # set`, `seq-of-map`), so the census can rank them with `real`,
        # `bitvector`, `datatype` and `set` where they belong; only a
        # shape none of those names fits stays `nested-seq-other`.
        named = _seq_element_issue(row)
        if named is not None:
            return named
        if row is not None and row.kind == "array":
            # `seq<array<int>>`: row 22's array-as-seq-value machinery is
            # built around exactly one top-level array per method (a
            # `modifies`-param mutation or an alloc-fill return); an array
            # nested inside another seq value is a second, aliasing-prone
            # array position that same machinery never reaches, so this
            # is the array's own refusal, not a seq-nesting one.
            return "array"
        if row is not None and row.kind == "seq":
            return "nested-seq-deep"  # a bare `seq<seq>`, no element given
        return "nested-seq-other"
    if t.kind == "array":
        return "array"
    if t.kind in ("array2", "array3"):
        # Row 30 (2026-09-10): a matrix with its own indexing, a
        # different Dafny type from `seq<seq<int>>`, named `array2`
        # regardless of rank (used to fold into the plain `array`
        # refusal here; row 30's own census split wants it distinct).
        return "array2"
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
        return _tuple_issue(t)  # row 44: a two-component tuple is t's pair
    if t.kind == "bv":
        return "bitvector"
    if t.kind == "object":
        return "heap"
    if t.kind == "func":
        return "higher-order"
    if t.kind == "id":
        # Row 30 (2026-09-10): `array2<int>`/`array3<int>` parse as an
        # ordinary generic "id" type (this grammar has no dedicated
        # array2/array3 keyword), so without this check they would read
        # as the unrelated `generics` gap; a multi-dimensional array is
        # its own matrix-shaped construct with its own indexing, not a
        # nested seq, so it is named `array2` here regardless of rank.
        if t.name in ("array2", "array3"):
            return "array2"
        return "generics" if t.args else "datatype"
    return "type-decl"


def _seq_element_issue(el: Optional[Type]) -> Optional[str]:
    """Row 46 (2026-09-27): the refusal name for a seq whose ELEMENT type
    `el` t has no value for -- the element's own kind, `seq-of-<kind>` --
    or `None` when this function has no sharper name than the caller's
    (`nested-seq-other`)."""
    if el is None:
        return None
    if el.kind == "bool":
        return "seq-of-bool"    # `seq<seq<bool>>`: the row's own name, one level down
    if el.kind == "real":
        return "seq-of-real"
    if el.kind == "bv":
        return "seq-of-bitvector"
    if el.kind == "tuple":
        return "seq-of-pair"    # t has no seq of pairs (SPEC.md "Pairs": "Not in v1")
    if el.kind in ("set", "iset"):
        return "seq-of-set"
    if el.kind in ("map", "imap"):
        return "seq-of-map"
    if el.kind == "id":
        # a datatype, a type synonym or a method's own type parameter; all
        # read as `id` here, none is a t value
        return "seq-of-datatype"
    if el.kind == "object":
        return "seq-of-object"
    return None


def _tuple_issue(t: Type) -> Optional[str]:
    """Row 44 (2026-09-27, t/FEATURES-TRACK.md, tuples): a Dafny tuple type
    `(T1, T2)` is t's pair (SPEC.md "Pairs (v1)") when it has exactly two
    components, each a type row 29 already carries as a pair component
    (`_pair_component_issue`: int, nat, bool, seq, string); `tuple-arity`
    for any other arity (t has no triple), `tuple-component` otherwise
    (a real, a char, an array, a nested tuple, ...)."""
    if len(t.args) != 2:
        return "tuple-arity"
    if any(_pair_component_issue(a) is not None for a in t.args):
        return "tuple-component"
    return None


def _id_type_gap(module, ty: Optional[Type]) -> Optional[str]:
    """Row 48: an `id` type that is not one of the file's datatypes is
    named by the declaration that introduces it (`class`, `trait`, `type`,
    `newtype`: the SkippedDecl's own gap name), or `opaque-type` when the
    file declares nothing by that name (an import or a Dafny built-in)."""
    if ty is None or ty.kind != "id" or ty.args:
        return None
    for d in module.decls:
        if isinstance(d, SkippedDecl):
            words = d.text.split()
            if len(words) >= 2 and words[1] == ty.name:
                return d.gap_name
    return "opaque-type"


_DATATYPE_KIND_ORDER = ("recursive", "generic", "real", "sum", "record", "enum")


def _datatype_kind(module) -> Optional[str]:
    """Row 48 (2026-09-27): the shape a member access on this file's
    datatypes needs, read from every skipped `datatype`/`codatatype`
    declaration's token text. Per declaration: `recursive` when a
    constructor's fields mention the type's own name, `generic` when the
    type takes parameters, `real` when a field is real-valued, `enum` when
    every constructor is nullary, `record` for one constructor with fields,
    `sum` otherwise. A file with several datatypes is named by the hardest
    kind present (the order above), since the member is not resolved to its
    type here; None when the file declares no datatype (the member belongs
    to a class, map or module import instead)."""
    kinds: set[str] = set()
    for d in module.decls:
        if not (isinstance(d, SkippedDecl) and d.keyword.split()[-1] in ("datatype", "codatatype")):
            continue
        words = d.text.split()
        if "=" not in words:
            continue
        eq = words.index("=")
        head, body = words[1:eq], words[eq + 1:]
        name = head[0] if head else ""
        generic = "<" in head
        ctors = " ".join(body).split(" | ")
        fields = [c[c.index("("):] for c in ctors if "(" in c]
        if any(re.search(r"\b" + re.escape(name) + r"\b", f) for f in fields if name):
            kinds.add("recursive")
        elif generic:
            kinds.add("generic")
        elif any(re.search(r"\breal\b", f) for f in fields):
            kinds.add("real")
        elif not fields:
            kinds.add("enum")
        elif len(ctors) == 1:
            kinds.add("record")
        else:
            kinds.add("sum")
    for k in _DATATYPE_KIND_ORDER:
        if k in kinds:
            return k
    return None


def _tuple_names(method: MethodDecl, closure: tuple) -> frozenset:
    """Row 44: every name declared with an accepted tuple type (a param, the
    return, a closure function's param, a typed local), whose `.0`/`.1`
    projections lift as `fst`/`snd`."""
    names = set()

    def note(name: Optional[str], t: Optional[Type]) -> None:
        if name and t is not None and t.kind == "tuple" and _tuple_issue(t) is None:
            names.add(name)

    for p in method.params:
        note(p.name, p.type)
    for r in method.returns:
        note(r.name, r.type)
    for d in closure:
        if isinstance(d, FunctionDecl):
            for p in d.params:
                note(p.name, p.type)
    for root in [method] + list(closure):
        for n in walk(root):
            if isinstance(n, VarDeclStmt):
                for nm in n.names:
                    note(nm.name, nm.type)
    return frozenset(names)


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
    if t.kind == "seq" and len(t.args) == 1 and t.args[0].kind in ("seq", "string"):
        # Row 30 (2026-09-10): a nested seq is still "seq" in this row's
        # own int/bool/seq vocabulary -- `+`/slice (rows 26-27) work the
        # same way at any nesting depth, this row only needs to know
        # "is it seq-typed", never how deep. Row 43 (2026-09-27): a
        # `seq<string>` is the same nested seq.
        return "seq"
    if t.kind == "string":
        return "seq"  # row 28: string is seq<int> by another name
    if t.kind == "array" and not t.nullable and _is_array_of_int(t):
        return "seq"
    if t.kind == "tuple" and _tuple_issue(t) is None:
        return "pair"  # row 44: a tuple-typed name; its components are `#0`/`#1`
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
        if isinstance(e.base, Ident):
            # Row 43 (2026-09-27): a nested name's row, `xs[i]`, is itself
            # seq-kinded (`_build_kind_env`'s `#row` entry); every other
            # index is an element, an int, as before.
            rk = lookup(e.base.name + "#row")
            if rk is not None:
                return rk
        return "int"
    if isinstance(e, Cardinality):
        return "int"
    if isinstance(e, Cast) and e.type.kind in ("int", "nat", "char"):
        # Row 46 (2026-09-27): `e as char` / `e as int` is an int-kinded
        # expression (a char is its code point, row 28); whether the cast
        # itself is safe is the cast pass's own question (`int-as-char-
        # lifted` or `char-cast-unbounded`), asked at the same node. Before
        # this the kind was unknown, so a display `[(n % 10 + 48) as char]`
        # refused `nested-seq-other`, a name that said nothing about it.
        return "int"
    if isinstance(e, TupleExpr):
        return "pair" if len(e.elems) == 2 else None  # row 44: a pair literal
    if isinstance(e, Member):
        if e.name in ("0", "1") and isinstance(e.base, Ident):
            # Row 44: a tuple projection has its component's kind
            # (`_build_kind_env`'s `<name>#0`/`#1` entries), else unknown.
            return lookup(e.base.name + "#" + e.name)
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


def _build_kind_env(method: MethodDecl, closure: tuple[Decl, ...],
                    method_kinds: Optional[dict] = None,
                    multi_kinds: Optional[dict] = None) -> dict[str, str]:
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
    env: dict[str, str] = dict(method_kinds or {})
    env.update(_closure_fn_kinds(method, closure))
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
                if (n.init and len(n.init) == 1 and len(n.names) >= 2 and multi_kinds
                        and isinstance(n.init[0], Call) and isinstance(n.init[0].fn, Ident)
                        and n.init[0].fn.name in multi_kinds):
                    # Row 41 (2026-09-27): `var a, b := M(x);` of a two-return
                    # method types each name from M's own out-parameters.
                    for nm, k in zip(n.names, multi_kinds[n.init[0].fn.name]):
                        k = _declared_kind(nm.type) or k
                        if k is not None:
                            env[nm.name] = k
                elif n.init:
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
    # Row 43 (2026-09-27, nested string sequences): a nested name's ROWS
    # are seq-kinded too, recorded under a `<name>#row` key no Dafny
    # identifier can spell, so `expr_kind` types `xs[i]` (a row) `seq`
    # rather than `int` and `xs[i][..k]`, `xs[i] + s` resolve (row 30 left
    # the row an int, its own named residual). Declared types first
    # (`seq<seq<int>>`, `seq<seq<nat>>`, `seq<string>`, `seq<seq<char>>`),
    # then an untyped local whose initialiser is a nested display.

    def _row(name: str, t: Optional[Type]) -> None:
        if (t is not None and t.kind == "seq" and len(t.args) == 1
                and t.args[0].kind in ("seq", "string")):
            env[name + "#row"] = "seq"
        if t is not None and t.kind == "tuple" and _tuple_issue(t) is None:
            # Row 44 (2026-09-27, tuples): the two components of a tuple-
            # typed name, `p.0`/`p.1`, under the same unspellable key idea.
            for idx, ct in enumerate(t.args):
                k = _declared_kind(ct)
                if k is not None:
                    env[f"{name}#{idx}"] = k

    for p in method.params:
        _row(p.name, p.type)
    for r in method.returns:
        _row(r.name, r.type)
    for d in closure:
        if isinstance(d, FunctionDecl):
            for p in d.params:
                _row(p.name, p.type)
    for root in [method] + list(closure):
        for n in walk(root):
            if isinstance(n, VarDeclStmt):
                for idx, nm in enumerate(n.names):
                    if nm.type is not None:
                        _row(nm.name, nm.type)
                    elif (n.init and len(n.init) == len(n.names)
                          and isinstance(n.init[idx], SeqDisplay)
                          and any(isinstance(el, (SeqDisplay, StringLit))
                                  for el in n.init[idx].elems)):
                        env[nm.name + "#row"] = "seq"
    return env


def _seq_literal_issue(n: SeqDisplay, env: dict) -> Optional[str]:
    """Row 25: `None` when every element of the Dafny sequence display
    `n` is int-typed (so it lifts to t's literal, `[]` -- no elements at
    all -- included). Row 30 (2026-09-10, SPEC.md "Nested sequences
    (v1)"): `None` too when `n` is itself a NESTED display, `[[1, 2],
    [3]]`, every element a seq expression -- a literal inner `SeqDisplay`
    whose OWN elements are all int-typed (one level down only; a further
    nested inner display, or a string-literal row, refuses by name
    below), or any other seq-typed element (an `Ident`, a slice, a call
    -- this best-effort scan cannot see whether that row is itself flat
    or would recurse a level too deep, the same "accept what it cannot
    disprove" reading `_type_issue`'s own DECLARED-type check settles
    precisely wherever the literal sits in a typed position). Anything
    else refuses by name: `nested-seq-string` (a string-literal row, or a
    display of chars nested another level), `nested-seq-deep` (a display
    nested two levels down), `nested-seq-other` (a bool or unresolvable
    element)."""
    for el in n.elems:
        if isinstance(el, StringLit):
            continue  # row 43: a string-literal row is a row of code points
        if isinstance(el, SeqDisplay):
            for inner in el.elems:
                if isinstance(inner, StringLit):
                    return "nested-seq-deep"  # a row of strings: three levels
                if isinstance(inner, SeqDisplay):
                    return "nested-seq-deep"
                if expr_kind(inner, env.get) != "int":
                    return "nested-seq-deep"
            continue
        k = expr_kind(el, env.get)
        if k in ("int", "seq"):
            continue
        if k == "bool":
            return "seq-of-bool"     # row 46: `[i % 3 == 0]`, a bool element
        if isinstance(el, RealLit):
            return "seq-of-real"     # row 46: `[1.0]`
        if isinstance(el, TupleExpr):
            return "seq-of-pair"     # row 46: `[(a, b)]`
        return "nested-seq-other"
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
    nested: set[str] = set()

    def note(name: Optional[str], t: Optional[Type]) -> None:
        if name is None or t is None:
            return
        if t.kind == "char":
            chars.add(name)
        elif t.kind == "string" or _is_seq_of_char(t):
            seqs.add(name)
        elif _is_nested_seq_of_char(t):
            # Row 43: `xs[i]` is a string and `xs[i][j]` a char, so the
            # nested name is kept apart for `_is_char_expr`.
            nested.add(name)

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
    return chars, seqs, nested


def _is_char_expr(e: Expr, char_names: set, char_seq_names: set = frozenset(),
                  nested_names: set = frozenset()) -> bool:
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
        return _is_char_expr(e.arg, char_names, char_seq_names, nested_names)
    if isinstance(e, Cast):
        return e.type.kind == "char"
    if isinstance(e, IfExpr):
        return (_is_char_expr(e.then, char_names, char_seq_names, nested_names)
                and _is_char_expr(e.else_, char_names, char_seq_names, nested_names))
    if isinstance(e, Index) and isinstance(e.base, Ident):
        return e.base.name in char_seq_names
    if (isinstance(e, Index) and isinstance(e.base, Index)
            and isinstance(e.base.base, Ident)):
        # Row 43: `xs[i][j]` on a `seq<string>` name is a char.
        return e.base.base.name in nested_names
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


def _closure_incl_methods(module: Module, method: MethodDecl) -> tuple[Decl, ...]:
    """Row 51's own reachability walk: identical to `_closure` except a
    `MethodDecl` callee is also followed and included, not dropped. `_closure`
    itself must stay function/lemma-only -- its other three callers (the
    mutual-recursion check, the read-only-array condition, `find_array_
    mutation`) all assume a closure of side-effect-free, provable-body
    declarations, and a method has neither property, so widening the shared
    helper would change what those three see. The source-axiom/source-assume
    check has no such assumption: Dafny gives a called METHOD's `ensures`
    exactly the same caller-trusted status as a called function's or lemma's
    (Reference Manual 6.3.1, 6.3.3), so an axiom-attributed method reached as
    a callee is exactly as much a row-51 hazard as an axiom-attributed
    function or lemma is, and must be walked into and included the same way."""
    by_name = {d.name: d for d in module.decls if d.name}
    order: list[Decl] = []
    seen: set[str] = set()

    def visit(name: str) -> None:
        if name in seen:
            return
        d = by_name.get(name)
        if d is None or not isinstance(d, (FunctionDecl, LemmaDecl, MethodDecl)):
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


# ---------------------------------------------------------------------------
# `source-axiom` / `source-assume` (row 51, 2026-09-27, t/LIFT-2026-09-26.md's
# DT0258 finding): a source-level reading, over the WHOLE module, of the
# three markers Dafny Reference Manual section 11.2.4 (`{:axiom}`), 11.2.22
# (`{:verify false}`) and 8.18 (the `assume` statement) document as unchecked
# trust -- `{:axiom}` "means that the post-condition may be assumed to be
# true without proof" and the body may be omitted; `{:verify false}` "skip[s]
# verification... altogether, not even trying to verify the well-formedness
# of postconditions and preconditions"; an `assume` statement "lets the user
# specify a logical proposition that Dafny may assume to be true without
# proof. If in fact the proposition is not true this may lead to invalid
# conclusions." None of the three is checked against the declaration's own
# body, so a placeholder function decorated with axiom lemmas about it (the
# vericoding DT0258 `BitwiseOr` case: a body that always returns 0, and
# `lemma {:axiom} BitwiseOrIdentity(x) ensures BitwiseOr(x, 0) == x`, false
# for that body whenever x != 0) verifies in dafny while being false of the
# very function the lift would inline. This is a SOURCE-level reading, not a
# semantic one: `LemmaDecl` keeps no parsed `attrs` field (its raw `text`
# does, since `_parse_lemma` reads and discards the attribute tokens but
# `text` is a straight slice of the source between the same two token
# positions) and `walk()` never descends into a `LemmaDecl.parts` (not a
# dataclass field, by the same docstring's design: a lemma's own body is
# never a reason to refuse the method that calls it -- decision 8 still
# drops the CALL as a hint; this rule looks at what the lemma itself CLAIMS
# and whether that claim is trustworthy, not at whether the call survives).
# ---------------------------------------------------------------------------

_AXIOM_ATTR_RE = re.compile(r"\{\s*:\s*axiom\b")
_VERIFY_FALSE_ATTR_RE = re.compile(r"\{\s*:\s*verify\s+false\b")
_ASSUME_WORD_RE = re.compile(r"(?<![A-Za-z0-9_])assume(?![A-Za-z0-9_])")


def _has_axiom_attr(attrs: tuple) -> bool:
    return any(a.name == "axiom" for a in attrs)


def _has_verify_false_attr(attrs: tuple) -> bool:
    for a in attrs:
        if a.name != "verify" or not a.args:
            continue
        arg = a.args[0]
        if isinstance(arg, BoolLit) and arg.value is False:
            return True
        if isinstance(arg, Ident) and arg.name == "false":
            return True
    return False


def _lemma_signature_text(d: "LemmaDecl") -> str:
    """The lemma's own `lemma [modifiers] {:attr} Name(...)` prefix, up to
    the first `(` of its parameter list -- restricting the attribute search
    to where `{:axiom}`/`{:verify false}` can actually sit (section 11's
    grammar puts an entity's own attributes right after its keyword), so an
    unrelated `{:axiom}`/`{:verify false}`-shaped fragment inside the body
    (a nested `assert ... by`, a quoted string) is never mistaken for the
    lemma's own attribute."""
    idx = d.text.find("(")
    return d.text if idx < 0 else d.text[:idx]


def _lemma_is_axiomatised(d: "LemmaDecl") -> bool:
    head = _lemma_signature_text(d)
    return bool(_AXIOM_ATTR_RE.search(head) or _VERIFY_FALSE_ATTR_RE.search(head))


def _lemma_has_assume(d: "LemmaDecl") -> bool:
    """An `assume` statement (attributed or not) anywhere in the lemma's own
    proof -- the source-level reading, over `d.text` (the lemma's full raw
    slice, signature through closing brace), rather than an AST walk: a
    lemma's parsed `parts.body` is `None` whenever its proof used a shape
    this parser's statement grammar does not know (a `calc`, a nested
    `forall`), and the hazard `assume` names (`Reference Manual` 8.18: "the
    user takes responsibility for being absolutely sure that the
    proposition is indeed true") is exactly as real whether or not the rest
    of the proof happened to parse."""
    return bool(_ASSUME_WORD_RE.search(d.text))


def _axiomatised_names(module: Module) -> dict[str, int]:
    """Every top-level `FunctionDecl`/`MethodDecl`/`LemmaDecl` in the module
    carrying `{:axiom}` or `{:verify false}` -- name -> its own line."""
    out: dict[str, int] = {}
    for d in module.decls:
        if not d.name:
            continue
        if isinstance(d, (FunctionDecl, MethodDecl)):
            if _has_axiom_attr(d.attrs) or _has_verify_false_attr(d.attrs):
                out[d.name] = d.line
        elif isinstance(d, LemmaDecl):
            if _lemma_is_axiomatised(d):
                out[d.name] = d.line
    return out


def _references_ident(node, name: str) -> bool:
    return any(isinstance(n, Ident) and n.name == name for n in walk(node))


def _axiom_only_functions(module: Module, axiomatised: dict[str, int]) -> dict[str, int]:
    """A `FunctionDecl` F, not itself axiomatised, whose only lemmas of
    record in the file are axiom lemmas about it (DT0258: `BitwiseOr` carries
    no attribute of its own, but `BitwiseOrCommutative`/`BitwiseOrIdentity`/
    `BitwiseOrIdempotent` -- every lemma in the file whose ensures names it
    -- are all `{:axiom}`). A function with NO lemma of record, or with at
    least one lemma that is not itself axiomatised, is not flagged here: it
    either stands on its own body (ordinary `classify` handles it) or has a
    real proof backing at least one of its stated properties."""
    lemmas = [d for d in module.decls if isinstance(d, LemmaDecl)]
    out: dict[str, int] = {}
    for f in module.decls:
        if not (isinstance(f, FunctionDecl) and f.name) or f.name in axiomatised:
            continue
        related = []
        for lm in lemmas:
            specs = tuple(getattr(getattr(lm, "parts", None), "specs", ()) or ())
            if any(isinstance(s, (RequiresClause, EnsuresClause))
                   and _references_ident(s.expr, f.name) for s in specs):
                related.append(lm)
        if related and all(lm.name in axiomatised for lm in related):
            out[f.name] = related[0].line
    return out


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


_REL_FLIP = {">": "<", ">=": "<="}


def _normalize_chain(c: Expr) -> Expr:
    """A relational chain written right to left (`|s| > i >= 0`, `n > k`) as
    its `<`/`<=` mirror (`0 <= i < |s|`, `k < n`): every rule below reads
    only `<`/`<=` chains, and the corpora write both spellings (2026-09-27:
    `i >= 0 && i < |res|` is the HumanEval-Dafny house style, 8 of the 40
    quantifiers refused `unbounded-quantifier` in the first 720 methods of
    the vericoding + HumanEval-Dafny lift). A chain already in `<`/`<=`
    form, a mixed one, or one with `==`/`!=`/`in` is returned unchanged."""
    if not isinstance(c, Chain):
        return c
    if all(op in ("<", "<=") for op in c.ops):
        return c
    if all(op in (">", ">=") for op in c.ops):
        return Chain(c.line, tuple(_REL_FLIP[op] for op in reversed(c.ops)),
                     tuple(reversed(c.operands)))
    return c


def _top_conjuncts(e: Expr) -> list:
    return list(e.args) if isinstance(e, NaryBool) and e.op == "&&" else [e]


def _conj(parts: list, line: int) -> Optional[Expr]:
    if not parts:
        return None
    return parts[0] if len(parts) == 1 else NaryBool(line, "&&", tuple(parts))


def _bound_range(binder: str, guard: Expr) -> Optional[tuple[Expr, Expr, Optional[Expr]]]:
    """`lo <= k < hi` (one chain, or two comparisons, either spelling) for
    exactly the named binder, optionally AND'ed with more conjuncts:
    (lo, hi, extra) with `extra` the conjunction of whatever else was in
    the guard (None if nothing else), or None if no conjunct bounds `binder`
    this way. Kept for callers that bound one binder in a guard; the
    quantifier rules below use `_bind_binders` directly."""
    conjuncts = _top_conjuncts(guard)
    got = _bind_binders([binder], conjuncts, None, set())
    if got is None:
        return None
    bound, used, chain_extras, _rules = got
    lo, hi, mem = bound[binder]
    if mem is not None:
        return None
    rest = [c for i, c in enumerate(conjuncts) if i not in used] + chain_extras
    return (lo, hi, _conj(rest, guard.line))


def _bound_membership(binder: str, guard: Expr) -> Optional[Expr]:
    """`k in s` (section 4.4's third quantifier row): returns `s` when
    `guard` is exactly `k in s` for the named binder, else None."""
    if isinstance(guard, Chain) and len(guard.ops) == 1 and guard.ops[0] == "in":
        a, b = guard.operands
        if _is_ident(a, binder):
            return b
    return None


def _chain_bounds(unbound: set, c: Chain, nat_names: set):
    """Every binder in one `<`/`<=` chain, bounded at once (t/FEATURES-TRACK.md
    feature 5, generalising row 31's `0 <= i < j < hi` pair): `0 <= x < y <
    z < w < |s|`, the sortedness invariant `0 <= k1 < i <= k2 < n`, or a
    single binder inside a longer chain, `0 <= k < i <= n`. A binder's lower
    bound is its left neighbour (plus one after `<`; a leftmost `nat` binder
    reads 0); its upper bound is the nearest operand to its right that is
    not a binder, plus one when every relation between them is `<=`. Reading
    the quantifier as nested single-binder ranges in chain order is exact:
    an outer value the chain would have excluded (no room for the binders to
    its right) gets an empty inner range, true for a forall and false for an
    exists, the same widening row 31 relied on. The chain's relations between
    two non-binder operands (`i <= n` in `0 <= k < i <= n`) are returned as
    `extras` and stay in the body. Returns (bounds, extras) or None when a
    binder occurs twice or lacks a bound."""
    ops, xs = c.ops, c.operands

    def is_binder(x) -> bool:
        return isinstance(x, Ident) and x.name in unbound

    pos: dict = {}
    for i, x in enumerate(xs):
        if is_binder(x):
            if x.name in pos:
                return None
            pos[x.name] = i
    if not pos:
        return None
    bounds: dict = {}
    for name, i in pos.items():
        if i == 0:
            if name not in nat_names:
                return None
            lo = IntLit(c.line, 0)
        else:
            lo = xs[i - 1] if ops[i - 1] == "<=" else _plus1(xs[i - 1])
        j = i + 1
        while j < len(xs) and is_binder(xs[j]):
            j += 1
        if j >= len(xs):
            return None
        strict = any(op == "<" for op in ops[i:j])
        hi = xs[j] if strict else _plus1(xs[j])
        bounds[name] = (lo, hi)
    extras = [Chain(c.line, (ops[k],), (xs[k], xs[k + 1]))
              for k in range(len(ops)) if not (is_binder(xs[k]) or is_binder(xs[k + 1]))]
    return bounds, extras


def _subst_many(e, mapping: dict):
    """Simultaneous substitution of several identifiers (a predicate's
    parameters by a call's arguments), so `P(b, a)` for `P(a, b)` never
    substitutes through itself."""
    if isinstance(e, Ident):
        return mapping.get(e.name, e)
    if dataclasses.is_dataclass(e):
        changes = {}
        for f in dataclasses.fields(e):
            val = getattr(e, f.name)
            if isinstance(val, tuple):
                newval = tuple(_subst_many(v, mapping) for v in val)
            elif dataclasses.is_dataclass(val):
                newval = _subst_many(val, mapping)
            else:
                newval = val
            if newval is not val:
                changes[f.name] = newval
        return dataclasses.replace(e, **changes) if changes else e
    return e


def _bind_binders(names: list, conjuncts: list, predicates: Optional[dict], nat_names: set):
    """Bound every binder in `names` from the conjunct list of a quantifier's
    guard, antecedent or body. Four rules, in this order, each over the
    binders the earlier ones left unbound:

    1. membership, `k in s` (decision 2): `s`, the binder reading `s[j]`;
    2. a `<`/`<=` chain of two or more relations holding the binder
       (`_chain_bounds`, either spelling via `_normalize_chain`);
    3. two single comparisons, a lower one (`lo <= k`, `lo < k`, or `k >= lo`,
       `k > lo`) and an upper one (`k < hi`, `k <= hi`, `hi > k`, `hi >= k`);
       a `nat` binder with only an upper bound reads `0` for its lower one
       (feature 5's one-sided range: the binder's own type is the bound
       Dafny used);
    4. a call of a closure predicate `P(.., k, ..)` with the binder as a bare
       argument whose body is a conjunction that bounds that parameter by
       rules 1 to 3 (feature 5's range through a predicate): the range, with
       P's parameters replaced by the call's arguments, bounds `k`, and the
       call itself stays in the body, so the quantifier is unchanged where
       `P(k)` holds and vacuous elsewhere, exactly as the source. The check
       stage proves the equivalence on every program (L_req/L_ens/L_inv).

    Returns (bound: name -> (lo, hi, mem), used conjunct indices, the
    chains' binder-free relations to keep, rule names) or None when some
    binder stays unbound (`unbounded-quantifier`, the caller's refusal)."""
    unbound = set(names)
    bound: dict = {}
    used: set = set()
    rules: set = set()
    extras: list = []
    norm = [_normalize_chain(c) for c in conjuncts]
    # 1. membership
    for i, c in enumerate(norm):
        if isinstance(c, Chain) and len(c.ops) == 1 and c.ops[0] == "in":
            a, b = c.operands
            if isinstance(a, Ident) and a.name in unbound and not _mentions_ident(b, a.name):
                bound[a.name] = (None, None, b)
                unbound.discard(a.name)
                used.add(i)
                rules.add("in-desugared")
    # 2. chains
    for i, c in enumerate(norm):
        if i in used or not isinstance(c, Chain) or len(c.ops) < 2:
            continue
        if not all(op in ("<", "<=") for op in c.ops):
            continue
        got = _chain_bounds(unbound, c, nat_names)
        if got is None:
            continue
        bs, ex = got
        for name, (lo, hi) in bs.items():
            bound[name] = (lo, hi, None)
            unbound.discard(name)
        used.add(i)
        extras.extend(ex)
        if len(bs) > 1 or len(c.ops) > 2:
            rules.add("quantifier-bounded-chain")
    # 3. single comparisons
    for name in list(names):
        if name not in unbound:
            continue
        lo_i = hi_i = None
        lo = hi = None
        for i, c in enumerate(norm):
            if i in used or not (isinstance(c, Chain) and len(c.ops) == 1
                                 and c.ops[0] in ("<", "<=")):
                continue
            a, b = c.operands
            if _is_ident(b, name) and lo_i is None and not _mentions_ident(a, name):
                lo_i, lo = i, (_plus1(a) if c.ops[0] == "<" else a)
            elif _is_ident(a, name) and hi_i is None and not _mentions_ident(b, name):
                hi_i, hi = i, (_plus1(b) if c.ops[0] == "<=" else b)
        if hi_i is not None and lo_i is None and name in nat_names:
            lo = IntLit(norm[hi_i].line, 0)
            rules.add("quantifier-bounded-nat")
        if hi_i is not None and lo is not None:
            bound[name] = (lo, hi, None)
            unbound.discard(name)
            used.add(hi_i)
            if lo_i is not None:
                used.add(lo_i)
    # 4. a predicate whose body bounds its parameter
    if unbound and predicates:
        for name in list(names):
            if name not in unbound:
                continue
            for c in norm:
                if not (isinstance(c, Call) and isinstance(c.fn, Ident) and c.fn.name in predicates):
                    continue
                pd = predicates[c.fn.name]
                if pd.body is None or len(pd.params) != len(c.args):
                    continue
                for j, a in enumerate(c.args):
                    if not _is_ident(a, name):
                        continue
                    pn = pd.params[j]
                    pnat = {pn.name} if pn.type is not None and pn.type.kind == "nat" else set()
                    inner = _bind_binders([pn.name], _top_conjuncts(pd.body), None, pnat)
                    if inner is None:
                        continue
                    lo, hi, mem = inner[0][pn.name]
                    mapping = {q.name: arg for q, arg in zip(pd.params, c.args)}
                    sub = lambda e: None if e is None else _subst_many(e, mapping)
                    bound[name] = (sub(lo), sub(hi), sub(mem))
                    unbound.discard(name)
                    rules.add("quantifier-bounded-predicate")
                    if mem is not None:
                        rules.add("in-desugared")
                    break
                if name not in unbound:
                    break
    if unbound:
        return None
    return bound, used, extras, rules


def _order_binders(binders: tuple, bound: dict) -> Optional[list]:
    """Nest the binders so that each one's bounds mention only binders
    nested outside it (`0 <= j < i < n` nests `i` inside `j`): the declared
    order where it works, else the first order that does; None on a cycle."""
    names = [b.name for b in binders]
    deps = {}
    for n in names:
        lo, hi, mem = bound[n]
        deps[n] = {m for m in names if m != n and any(
            e is not None and _mentions_ident(e, m) for e in (lo, hi, mem))}
    out: list = []
    done: set = set()
    while len(out) < len(names):
        progressed = False
        for n in names:
            if n in done or not deps[n] <= done:
                continue
            lo, hi, mem = bound[n]
            out.append((n, lo, hi, mem))
            done.add(n)
            progressed = True
        if not progressed:
            return None
    return out


def _eliminate_defined_binders(q: Quantifier) -> Optional[Quantifier]:
    """Row 33 (2026-09-14), widened 2026-09-27 (feature 5): a binder pinned
    by an equality is substituted away wherever Dafny puts the equation --
    the range guard (`| _t#0 == i + 1`, the resolver's companion binder), an
    unguarded `exists` body's own conjunction (`exists c :: c == F(s) && r ==
    G(c)`, vericoding DA0491) or an unguarded `forall`'s antecedent (`forall
    c :: c == F(s) ==> P(c)`). `exists x :: x == E && P(x)` and `forall x ::
    x == E ==> P(x)` are both `P(E)`, so a quantifier all of whose binders
    are pinned collapses to its body, which the caller lifts as a plain
    expression. Returns the quantifier with the pinned binders gone (possibly
    none left), or None when nothing applies... never None: the input itself
    when no equation is found."""
    while q.binders:
        where = "range"
        found = _binder_defining_equality(q.binders, q.range)
        if found is None and q.range is None:
            if q.kind == "exists" and isinstance(q.body, NaryBool) and q.body.op == "&&":
                found = _binder_defining_equality(q.binders, q.body)
                where = "body"
            elif q.kind == "forall" and isinstance(q.body, Implies):
                found = _binder_defining_equality(q.binders, q.body.left)
                where = "antecedent"
        if found is None:
            break
        name, repl, remaining = found
        new_binders = tuple(b for b in q.binders if b.name != name)
        if where == "range":
            new_body = _subst_ast(q.body, name, repl)
            new_range = _subst_ast(remaining, name, repl) if remaining is not None else None
            q = dataclasses.replace(q, binders=new_binders, range=new_range, body=new_body)
        elif where == "body":
            rest = (_subst_ast(remaining, name, repl) if remaining is not None
                    else BoolLit(q.line, True))
            q = dataclasses.replace(q, binders=new_binders, body=rest)
        else:
            right = _subst_ast(q.body.right, name, repl)
            new_body = (right if remaining is None
                        else Implies(q.line, _subst_ast(remaining, name, repl), right))
            q = dataclasses.replace(q, binders=new_binders, body=new_body)
    return q


def closure_predicates(closure: tuple) -> dict:
    """Feature 5: the closure's bodied predicates (and bool-valued
    functions) by name, the `predicates` argument of `bound_quantifier`."""
    return {d.name: d for d in closure
            if isinstance(d, FunctionDecl) and d.name and d.body is not None
            and (d.is_predicate or (d.ret_type is not None and d.ret_type.kind == "bool"))}


def bound_quantifier(q: Quantifier, predicates: Optional[dict] = None):
    """Section 4.4's quantifier-bounding rules, unified into one contract:
    on success, returns {"binders": [(name, lo, hi, membership_seq), ...],
    "body": Expr, "rules": set} where `body` is the FULLY RESOLVED predicate
    to lift at the innermost level (every `&&`/`==>` combination already
    folded in), each binder's `lo`/`hi` are `None` exactly when
    `membership_seq` is not (the `k in s` row: `lo`/`hi` become `0`/`len(s)`
    and `body` must still be substituted `k -> s[j]` by the caller using the
    returned fresh binder position), the binders are listed outermost first
    (`_order_binders`: each one's bounds mention only earlier ones), and an
    EMPTY binder list means every binder was pinned by an equality and the
    quantifier IS its body (`_eliminate_defined_binders`). `rules` names the
    rules that fired, for the sidecar. Returns None when some binder has no
    finite range this reads (the caller refuses `unbounded-quantifier`).

    `predicates` (t/FEATURES-TRACK.md feature 5, 2026-09-27) maps the
    closure's predicate names to their `FunctionDecl`s, for the range
    through a predicate rule of `_bind_binders`; None disables that rule.

    The shapes read, each the source's own conjunction of constraints plus a
    residual body: a guard (`| C :: B`); an unguarded forall with an
    antecedent (`C ==> B`); an unguarded exists whose body is one
    conjunction (`C && B'`, the constraints and the residual mixed, every
    unused conjunct kept as body); and the resolver's distributed forms
    (`_extract_unguarded_range`, row 31). Whatever the constraints do not
    bound stays in the body: `extra ==> B` for a forall, `extra && B` for an
    exists, so the lifted quantifier says exactly what the source said."""
    q = _eliminate_defined_binders(q)
    if not q.binders:
        return {"binders": [], "body": q.body, "rules": {"quantifier-eliminated"}}
    nat_names = {b.name for b in q.binders if b.type is not None and b.type.kind == "nat"}
    names = [b.name for b in q.binders]
    shapes = []
    if q.range is not None:
        shapes.append((_top_conjuncts(q.range), q.body))
    else:
        if q.kind == "forall" and isinstance(q.body, Implies):
            shapes.append((_top_conjuncts(q.body.left), q.body.right))
        if q.kind == "exists" and isinstance(q.body, NaryBool) and q.body.op == "&&":
            shapes.append((list(q.body.args), None))
        extracted = _extract_unguarded_range(q.kind, q.body)
        if extracted is not None:
            rng, new_body = extracted
            shapes.append((_top_conjuncts(rng), new_body))
    for conjuncts, residual in shapes:
        got = _bind_binders(names, conjuncts, predicates, nat_names)
        if got is None:
            continue
        bound, used, chain_extras, rules = got
        rest = [c for i, c in enumerate(conjuncts) if i not in used] + chain_extras
        extra = _conj(rest, q.line)
        if q.kind == "forall":
            body = residual if extra is None else Implies(q.line, extra, residual)
        elif residual is None:
            body = extra if extra is not None else BoolLit(q.line, True)
        else:
            body = residual if extra is None else NaryBool(q.line, "&&", (extra, residual))
        ordered = _order_binders(q.binders, bound)
        if ordered is None:
            return None
        rules = set(rules) | {"quantifier-bounded"}
        return {"binders": ordered, "body": body, "rules": rules}
    return None


def _expr_eq_ignore_line(a, b) -> bool:
    """Structural equality between two `Expr` subtrees, ignoring every
    `line` field. dataclass `__eq__` compares `line` too, which is right
    almost everywhere in this file (two nodes from the same reprinted
    clause land on the same line) but wrong for row 31's repeated-range
    detection when the two copies of the range happen to sit on different
    SOURCE lines -- dafny's own `rprint` always puts a whole clause on one
    line, but a hand-written or differently-wrapped guard need not."""
    if a is b:
        return True
    if type(a) is not type(b):
        return False
    if dataclasses.is_dataclass(a):
        for f in dataclasses.fields(a):
            if f.name == "line":
                continue
            if not _expr_eq_ignore_line(getattr(a, f.name), getattr(b, f.name)):
                return False
        return True
    if isinstance(a, tuple):
        return len(a) == len(b) and all(
            _expr_eq_ignore_line(x, y) for x, y in zip(a, b))
    return a == b


def _extract_unguarded_range(kind: str, body: Expr):
    """Row 31: dafny's own printer (`rprint`, what `lift_resolve` feeds the
    lifter) does not always leave an unguarded quantifier's range as the
    single `range ==> P` / `range && P` shape the two branches above
    already read. For a body that is itself a conjunction (forall) or
    disjunction (exists), dafny DISTRIBUTES the range across every
    top-level clause -- `range ==> (A && B)` prints as `(range ==> A) &&
    (range ==> B)`, and `range && (A || B)` prints as `(range && A) ||
    (range && B)` -- so the simple `isinstance(body, Implies)` /
    `NaryBool("&&")` tests above never fire even though the range is
    right there, repeated verbatim in every clause. Detects the repeat (by
    structural equality -- dataclass `__eq__`, sound here because every
    copy came from re-printing the SAME source guard onto the SAME line)
    and reassembles the single-guard shape `_bound_range` already knows
    how to parse. Returns (range_expr, body_without_range) or None."""
    if kind == "forall":
        if isinstance(body, Implies):
            return (body.left, body.right)
        if isinstance(body, NaryBool) and body.op == "&&" and len(body.args) >= 2 \
                and all(isinstance(c, Implies) for c in body.args):
            rng = body.args[0].left
            if all(_expr_eq_ignore_line(c.left, rng) for c in body.args[1:]):
                parts = tuple(c.right for c in body.args)
                new_body = parts[0] if len(parts) == 1 \
                    else NaryBool(body.line, "&&", parts)
                return (rng, new_body)
        return None
    else:  # "exists"
        if isinstance(body, NaryBool) and body.op == "||" and len(body.args) >= 2 \
                and all(isinstance(d, NaryBool) and d.op == "&&" and len(d.args) >= 2
                        for d in body.args):
            rng = body.args[0].args[0]
            if all(_expr_eq_ignore_line(d.args[0], rng) for d in body.args[1:]):
                def _rest(d):
                    r = d.args[1:]
                    return r[0] if len(r) == 1 else NaryBool(d.line, "&&", tuple(r))
                new_body = NaryBool(body.line, "||", tuple(_rest(d) for d in body.args))
                return (rng, new_body)
        return None


def _ordered_pair_bound(b1: str, b2: str, c: Chain):
    """Row 31, the `0 <= i < j < hi` shape (section 4.4 never had it: two
    binders ordered against the SAME array/seq end, one chain of three
    relations over four operands, not the two separate two-operand chains
    the N-binder loop below otherwise expects). Sound to read as `i` over
    `[lo, hi)` and, nested inside, `j` over `[i+1, hi)` (or `[i, hi)` for a
    non-strict middle relation): every `i` the tighter original guard
    would have excluded (those with no valid `j` left) simply gets an
    empty inner range, contributing nothing to a forall (vacuously true)
    or an exists (no witness) -- the same widening `in-desugared` already
    relies on for its `[0, len(s))` outer range. Returns
    ((lo1,hi1),(lo2,hi2)) for (b1,b2) in that order, or None."""
    if not (isinstance(c, Chain) and len(c.ops) == 3 and len(c.operands) == 4):
        return None
    op1, op2, op3 = c.ops
    v0, v1, v2, v3 = c.operands
    if not (_is_ident(v1, b1) and _is_ident(v2, b2)):
        return None
    if not (op1 in ("<", "<=") and op2 in ("<", "<=") and op3 in ("<", "<=")):
        return None
    lo1 = _plus1(v0) if op1 == "<" else v0
    hi_shared = _plus1(v3) if op3 == "<=" else v3
    lo2 = _plus1(Ident(c.line, b1)) if op2 == "<" else Ident(c.line, b1)
    return ((lo1, hi_shared), (lo2, hi_shared))


def _mentions_ident(e: Expr, name: str) -> bool:
    """True iff `Ident(name)` occurs anywhere in `e`'s subtree (row 33's
    self-reference guard: an equation `_t#0 == _t#0 + 1` does not define
    `_t#0`, it is unsatisfiable/circular, so it must never be read as a
    substitution)."""
    if isinstance(e, Ident):
        return e.name == name
    if dataclasses.is_dataclass(e):
        return any(_mentions_any(getattr(e, f.name), name) for f in dataclasses.fields(e))
    return False


def _mentions_any(val, name: str) -> bool:
    if isinstance(val, tuple):
        return any(_mentions_any(v, name) for v in val)
    if dataclasses.is_dataclass(val):
        return _mentions_ident(val, name)
    return False


def _subst_ast(e: Expr, name: str, repl: Expr) -> Expr:
    """Plain AST-level substitution of `Ident(name)` by `repl` throughout
    `e` (row 33). Distinct from `lift_rewrite._subst`: that one runs at
    rewrite time against an already fresh-renamed scope and knows about
    the `_AtHole` membership sentinel; this one runs here, at classify
    time, directly on the still-unrewritten `lift_ast.Expr` tree, purely
    to eliminate an equality-filter binder before the existing bounding
    rules ever see it."""
    if isinstance(e, Ident):
        return repl if e.name == name else e
    if dataclasses.is_dataclass(e):
        changes = {}
        for f in dataclasses.fields(e):
            val = getattr(e, f.name)
            newval = _subst_ast_any(val, name, repl)
            if newval is not val:
                changes[f.name] = newval
        return dataclasses.replace(e, **changes) if changes else e
    return e


def _subst_ast_any(val, name: str, repl: Expr):
    if isinstance(val, tuple):
        return tuple(_subst_ast_any(v, name, repl) for v in val)
    if dataclasses.is_dataclass(val):
        return _subst_ast(val, name, repl)
    return val


def _binder_defining_equality(binders: tuple, guard: Optional[Expr]):
    """Row 33 (2026-09-14): find a top-level conjunct of `guard` that is a
    plain equality `Chain(("==",), (A, B))` where exactly one side is a
    bare `Ident` naming one of `binders` and the other side does not
    mention that same binder (so the equation fixes it uniquely in terms
    of the rest of the quantifier's own binders and outer scope, never in
    terms of itself). This is dafny's own resolver-introduced companion
    binder for a chained index (`exists i, _t#0 | _t#0 == i + 1 :: ...`,
    the synthetic name printed for `a[i + 1]` inside an `exists`/`forall`
    whose bound variable dafny would otherwise have to re-derive), but the
    match is purely structural: any binder pinned by a same-shaped
    equality qualifies, source-written or resolver-synthesised alike.
    Returns (binder_name, replacement_expr, remaining_guard) for the
    FIRST such conjunct found, or None. `remaining_guard` is `guard` with
    that one conjunct removed (None if nothing else was in it)."""
    if guard is None:
        return None
    conjuncts = list(guard.args) if isinstance(guard, NaryBool) and guard.op == "&&" else [guard]
    names = {b.name for b in binders}
    for i, c in enumerate(conjuncts):
        if not (isinstance(c, Chain) and len(c.ops) == 1 and c.ops[0] == "=="):
            continue
        a, b = c.operands
        for lhs, rhs in ((a, b), (b, a)):
            if isinstance(lhs, Ident) and lhs.name in names and not _mentions_ident(rhs, lhs.name):
                rest = [x for j, x in enumerate(conjuncts) if j != i]
                remaining = None
                if rest:
                    remaining = rest[0] if len(rest) == 1 else NaryBool(c.line, "&&", tuple(rest))
                return (lhs.name, rhs, remaining)
    return None


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

def _closure_root_shadows(root: Node, method: MethodDecl, name: str) -> bool:
    """True iff `root` is a closure `FunctionDecl`/`LemmaDecl` (never
    `method` itself) whose OWN parameter list rebinds `name`, so every
    bare `Ident` spelled `name` inside `root`'s body and specs denotes
    ITS OWN parameter, never the method's same-named one -- Dafny scopes
    a function's parameters to its own declaration, and nothing in
    `root` can read past that shadow to reach an outer binding of the
    same name (`root` is never nested inside `method`; it is a sibling
    top-level declaration `_closure` pulled in because `method` calls
    it, so there is no enclosing-scope relationship for `root`'s OWN
    `name` to see through in the first place).

    Row (decision 1 / array read-only, this wave): measured on
    `dafny-synthesis_task_id_755` (`SecondSmallest`, array param `s`).
    The closure includes `min(s: seq<int>)`, whose OWN parameter is also
    named `s` (an unrelated seq, shadowing the method's array); `min`'s
    body calls `MinPair(s)`. `array_readonly_issue`'s scan used to walk
    every closure root with one flat, scope-blind identifier match, so
    `MinPair(s)` read as the ARRAY `s` escaping to a call and refused a
    genuinely read-only parameter (`array`, false positive). Guarding
    each root by its own parameter list before scanning it fixes exactly
    this and nothing else: the guard only SILENCES matches inside a root
    that provably cannot see the outer `name` at all, so no method that
    previously satisfied the read-only condition can newly fail it, and
    no write to the TRUE `param_name` anywhere reachable is silenced (a
    shadowing root's own body cannot write to the outer array under a
    name it does not bind)."""
    if root is method:
        return False
    params = getattr(root, "params", None)
    return bool(params) and any(p.name == name for p in params)


def array_readonly_issue(param_name: str, method: MethodDecl,
                          closure: tuple[Decl, ...], module: Optional[Module] = None,
                          _stack: tuple = ()) -> Optional[str]:
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
    have refused it before decision 22 existed).

    Passing `param_name` to a CLOSURE `FunctionDecl` (a spec_fun
    candidate, e.g. `InArray(a, x)`) is exempted from the "passed to a
    call" escape check, unlike passing it to another METHOD (still
    unreachable here in practice -- a call of a different method already
    refuses `calls-other-method` before this function ever runs) or
    through an unresolved callee. A Dafny FUNCTION can never write
    through any reference it is handed -- functions have no assignment
    statements and no heap mutation at all, ghost or not -- so hand it
    the array under decision 1's OWN read-only condition and nothing new
    can happen to it; the function's own parameter picks up the identical
    seq value `lift_rewrite.py` already threads through every other
    scope. Measured on `dafny-synthesis_task_id_2/161/249/579`
    (`SharedElements`/`RemoveElements`/`Intersection`/
    `DissimilarElements`, all four calling `InArray(a, x)`/`InArray(b,
    x)`): before this exemption, the bare `a`/`b` argument tripped this
    same escape check the reads-clause row above also had to widen, so
    fixing only the reads clause would have left these four refused
    `array` instead.

    t/FEATURES-TRACK.md feature 4 (2026-09-27, "arrays read by functions"),
    with `module` given: two more calls are not escapes. A LEMMA call
    (`SumRPrefix(v, i);`, vericoding DD0128; `UpdateMinCount(v, ...)`,
    DD0130): a Dafny lemma is a ghost method with no `modifies` clause
    (Reference Manual 6.3.3, "Lemmas": a lemma "cannot modify the heap"),
    so an array it is handed is only read, and the lifter drops or lifts
    the lemma on its own terms anyway (decision 8, row 38). A call of
    another METHOD of the module whose own parameter at that position is
    itself a read-only array by this same condition, recursively
    (`search(v, elem)` calling `binarySearch(v, elem)`, DD0135): the callee
    sees the same value the caller does and writes nothing through it (a
    callee that writes it, or reaches a cycle, is still an escape; a
    self-call passes the array to the very method being checked, whose
    own reads are what this scan covers). Measured 2026-09-27 by
    re-lifting the 86 staged files whose 88 methods the 2026-09-26 lift
    refused `array` (rewrite stage, check skipped): 21 of the 88 pass this
    condition now, 14 of them lift (query, queryFast x2, sumElemsB,
    mCountMin, mPeekSum, binarySearchRec, barrier, SharedElements,
    FilterOddNumbers, BinarySearchRecursive, Mcontained, BinarySearch,
    BinarySearchLoop) and 7 are refused later by name; the 67 still
    refused `array` are arrays of char/real/bool/bv32/T/arrays, array
    results, and the in-place sorts (`aliased`), none of them this
    condition's."""
    closure_fn_names = {d.name for d in closure if isinstance(d, FunctionDecl) and d.name}
    # the closure carries the lemmas the method calls (row 38), so a caller
    # without the module (the check stage re-deriving decision 22's shape)
    # still sees a lemma call as a lemma call
    lemma_names: set = {d.name for d in closure if isinstance(d, LemmaDecl) and d.name}
    methods_by_name: dict = {}
    if module is not None:
        lemma_names |= {d.name for d in module.decls if isinstance(d, LemmaDecl) and d.name}
        methods_by_name = {d.name: d for d in module.decls
                           if isinstance(d, MethodDecl) and d.name}

    def _callee_reads_only(callee: MethodDecl, positions: list) -> bool:
        if callee.name in _stack or callee.name == method.name:
            return callee.name == method.name
        for i in positions:
            if i >= len(callee.params):
                return False
            cp = callee.params[i]
            if cp.type is None or cp.type.kind != "array" or cp.type.nullable:
                return False
            if array_readonly_issue(cp.name, callee, _closure(module, callee), module,
                                    _stack + (method.name,)) is not None:
                return False
        return True

    scope: list[Node] = [method] + list(closure)
    for root in scope:
        shadowed = _closure_root_shadows(root, method, param_name)
        for n in walk(root):
            if isinstance(n, Assign):
                for lhs in n.targets:
                    if (not shadowed and lhs.kind == "index"
                            and isinstance(lhs.base, Ident) and lhs.base.name == param_name):
                        return "array-mutation"
            if isinstance(n, Call) and isinstance(n.fn, Ident) and n.fn.name in closure_fn_names:
                continue  # a pure spec_fun call: exempted above
            if isinstance(n, (Call, CallStmt)):
                if shadowed:
                    continue
                args = n.args
                positions = [i for i, a in enumerate(args)
                             if isinstance(a, Ident) and a.name == param_name]
                if not positions:
                    continue
                callee_name = (n.name if isinstance(n, CallStmt)
                               else (n.fn.name if isinstance(n.fn, Ident) else None))
                if callee_name in lemma_names:
                    continue  # feature 4: a lemma reads, never writes
                if callee_name in methods_by_name and _callee_reads_only(
                        methods_by_name[callee_name], positions):
                    continue  # feature 4: a read-only callee
                return "array"
    return None


def _array_passed_to_call(name: str, method: MethodDecl, closure: tuple[Decl, ...],
                          module: Optional[Module] = None) -> bool:
    """True iff `name` appears as a bare argument to some call anywhere
    in the method's closure -- the aliasing half of `array_readonly
    _issue`, factored out so decision 22's mutated array can reuse it
    without also tripping that function's own array-mutation check
    (which the mutated array is EXPECTED to trip). Shadow-guarded the
    same way and for the same reason as `array_readonly_issue`. With
    `module` given (feature 4, 2026-09-27), a LEMMA call is not an alias:
    a lemma reads the array and cannot write it (the sorts' own
    permutation lemmas, `SortedLemma(a, ...)`, are what tripped this)."""
    lemma_names: set = {d.name for d in closure if isinstance(d, LemmaDecl) and d.name}
    if module is not None:
        lemma_names |= {d.name for d in module.decls if isinstance(d, LemmaDecl) and d.name}
    # 2026-09-27 (t/FEATURES-TRACK.md, in-place writes, the Dafny half's
    # first shape): a closure FUNCTION (a predicate in an invariant,
    # `IsSorted(a, 0, i)`, insertionSort's `sorted(a, 0, i)`) is not an
    # alias either: a Dafny function has no assignment and no heap
    # mutation, it reads the array's value at the point of evaluation, and
    # that value is exactly the seq decision 22 threads there (the same
    # exemption `array_readonly_issue` grants a read-only parameter).
    # Measured: 2 of the 11 `aliased` sorts have no `multiset` spec and
    # lift once this is exempt; the other 9 refuse `multiset` next.
    closure_fn_names = {d.name for d in closure if isinstance(d, FunctionDecl) and d.name}
    for root in [method] + list(closure):
        if _closure_root_shadows(root, method, name):
            continue
        for n in walk(root):
            if isinstance(n, Call) and isinstance(n.fn, Ident) and n.fn.name in closure_fn_names:
                continue
            if isinstance(n, (Call, CallStmt)):
                callee_name = (n.name if isinstance(n, CallStmt)
                               else (n.fn.name if isinstance(n.fn, Ident) else None))
                if callee_name in lemma_names:
                    continue
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


def find_array_mutation(method: MethodDecl, closure: tuple[Decl, ...],
                        module: Optional[Module] = None
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

    if _array_passed_to_call(name, method, closure, module):
        # Aliasing: the mutated array is also read through another name
        # (passed as an argument somewhere in the closure), which this
        # shim cannot verify the callee's effect on.
        return None, (param.line, "array", "aliased")

    elem_kind = "nat" if param.type.args[0].kind == "nat" else "int"
    return ArrayMutation(kind="modifies-param", name=name, elem_kind=elem_kind), None


def _dropped_function_decreases_set_ids(closure: tuple[Decl, ...]) -> frozenset[int]:
    """`id()`s of every `SetDisplay` dafny's rprint puts in an INFERRED
    decreases clause (`decreases {a}, a, x`) on a closure `FunctionDecl`
    that never self-calls. Dafny always materialises a leading `{obj,
    ...}` heap-ordering component for any function with a nonempty
    `reads` clause -- whether or not the function actually recurses --
    but t's own decreases synthesis for a spec_fun with NO self-call
    needs no decreases at all (`_lift_function`, SPEC.md gate 3) and
    never reads the source's decreases in that case, so this set literal
    is dead text this row never elaborates.

    Row (decision 1's function-parameter widening, this wave): measured
    on `dafny-synthesis_task_id_2/161/249/579` (`InArray`, `reads a`, no
    self-call, printed `decreases {a}, a, x`). The generic per-node scan
    used to flag every `SetDisplay` unconditionally (`"set"`); once the
    reads-clause and call-escape rows above accept `InArray` itself,
    this inferred set was the next false refusal on the exact same four
    rows. A SELF-recursive function's `decreases` is untouched here (its
    `SetDisplay`, if any, is left for the generic scan and for
    `_decreases_issues`'s own lexicographic-projection check, since t
    DOES read that function's decreases then); so is any `SetDisplay`
    anywhere else in a requires/ensures/body -- this only exempts a node
    that is (a) inside a `DecreasesClause`'s own expression list and (b)
    on a function this row already proved is never re-elaborated."""
    ids: set[int] = set()
    for d in closure:
        if not isinstance(d, FunctionDecl) or d.body is None:
            continue
        self_calls = [c for c in walk(d.body) if isinstance(c, Call)
                      and isinstance(c.fn, Ident) and c.fn.name == d.name]
        if self_calls:
            continue
        for s in d.specs:
            if isinstance(s, DecreasesClause) and not isinstance(s.exprs, Star):
                for e in s.exprs:
                    if isinstance(e, SetDisplay):
                        ids.add(id(e))
    return frozenset(ids)


def _array_mutation_accepted_ids(method: MethodDecl, mutation: Optional[ArrayMutation],
                                  ret_param: Optional[Param]) -> frozenset[int]:
    """`id()`s of the `Old`/`Fresh`/`Slice`/`VarDeclStmt` nodes decision 22
    maps rather than refuses (the `id()`-set pattern `_self_call
    _positions` already uses for the same reason: a flat per-node scan
    has no context of its own, so the exemption is looked up by node
    identity instead).

    `old(a[k])` and `old(a[..])` on the ONE `modifies`-param array (`a`
    reads as the parameter both inside and outside `old` in t; the scope
    substitution that makes the OUTSIDE reading mean the return is
    `lift_rewrite.py`'s job, not this one's); `a[..]` with no `old`
    wrapper on that same name (post-state, reading as the return);
    `fresh(b)` where `b` is the return of a `alloc-fill` method whose
    return type is `array<int|nat>` (SPEC.md: "`fresh(b)` on a returned
    array is dropped''); and the `VarDeclStmt` that binds an `alloc-fill`
    mutation's own local to `new int[..]`/`new nat[..]` (`var cubedArray
    := new int[a.Length];`).

    That last one is its own row (this wave, array read-only): measured
    on `dafny-synthesis_task_id_447` (`CubeElements`). `find_array
    _mutation` already validates the local's `new`-shape and marks it
    `alloc-fill`, but the GENERIC per-node scan (`_scan_node_for_issues`)
    separately flags every array-typed `VarDeclStmt` as `local array`
    unconditionally, with no notion of decision 22 at all -- so a
    genuinely read-only array PARAMETER (`a`, never assigned, never
    passed to a call) was refused `array` anyway, on account of an
    UNRELATED local decision 22 already accepted. Exempting exactly the
    one `VarDeclStmt` `find_array_mutation` itself classified widens
    acceptance only for a local already proven to be decision 22's own
    accepted shape; every other array-typed local (one `find_array
    _mutation` did NOT map -- two-dimensional, non-int/nat element, or
    simply never mutated at all) still hits the generic rule unchanged."""
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
    elif mutation.kind == "alloc-fill":
        name = mutation.name
        for n in walk(method):
            if isinstance(n, VarDeclStmt) and n.names and n.init:
                for i, nm in enumerate(n.names):
                    if (nm.name == name and i < len(n.init)
                            and isinstance(n.init[i], NewRhs)):
                        ids.add(id(n))
        if (ret_param is not None and ret_param.type is not None
                and ret_param.type.kind == "array" and not ret_param.type.nullable
                and _is_array_of_int(ret_param.type)):
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
    # Methods as callees (2026-09-26, SPEC.md "Methods (v1)", LIFTER-DECISIONS.md
    # row 37): every OTHER method this one calls, once each in first-call order,
    # as (dafny name, that method's own `Liftable`). Each callee was classified
    # by this same function (its refusal is this method's refusal), so its own
    # `callees` carry the rest of the call graph; `lift_rewrite.rewrite` lifts
    # them callees-first into the task's `methods`.
    callees: tuple = ()
    # Row 45 (2026-09-27, t/FEATURES-TRACK.md, return default): the dafny
    # name of the single out-parameter section 4.7's SYNTACTIC check could
    # not see assigned on every path (`_assigns_ret_all_paths`), `None`
    # when it could. `lift_rewrite.rewrite` opens such a body with the
    # return's type default and logs `return-default-init`; `lift_check`
    # then verifies the SOURCE method under dafny's own definite-assignment
    # rule (a semantic check, not a syntactic one -- measured on dafny
    # 4.11.0: a `while true { .. r := i; return; .. }` body and an if-case
    # both pass it while this syntactic check refuses them) and refuses
    # `return-default-unverified` when dafny does not accept it, so the
    # default is only ever kept where dafny proved it is never observed.
    ret_default: Optional[str] = None
    # Row 51 (2026-09-27, t/LIFT-2026-09-26.md's DT0258 finding): the lines
    # of every `{:axiom}`/`{:verify false}` declaration (or axiom-only
    # function, `_axiom_only_functions`) that the source file carries OUTSIDE
    # this method's own closure -- a note, never a refusal (LIFTER-DESIGN.md
    # section 8's own distinction: "a file whose axioms lie outside the
    # method's closure lifts as before"). `lift_rewrite.rewrite` copies each
    # line into the sidecar as an `axiom-in-file` rewrite entry so the
    # census can count it without re-reading the source.
    axiom_in_file: tuple[int, ...] = ()


def _first(issues: list[tuple[int, str, str]]) -> tuple[int, str, str]:
    return min(issues, key=lambda t: t[0])


def classify(module: Module, method: MethodDecl, _stack: tuple = (),
             _memo: Optional[dict] = None) -> "Refusal | Liftable":
    """`_stack` (the callers whose classification is in progress, outermost
    first) and `_memo` (dafny method name -> its verdict, shared by one
    top-level call) are the methods-as-callees recursion's own state; a
    caller outside this module passes neither."""
    if _memo is None:
        _memo = {}
    issues: list[tuple[int, str, str]] = []
    rewrites: list[Rewrite] = []

    closure = _closure(module, method)

    # -- let expressions (2026-09-26, `lift_let`): every rule below reads the
    # method and closure with their lets substituted away, the tree
    # `lift_rewrite.rewrite` will lift, so a type, a quantifier bound or a
    # call is seen where the substitution puts it. The plan still carries the
    # SOURCE's own method and closure: `lift_check` compares each source
    # clause, lets and all, against its lift, which makes Dafny prove every
    # substitution, as it proves every other rewrite. A let that cannot be
    # substituted is an issue here like any other construct, first by line. The
    # closure is the source's (a call only in a let's unused right-hand side
    # still has its function lifted, and printed for the checker). --
    source_method, source_closure = method, closure
    method_names = {d.name for d in module.decls if isinstance(d, MethodDecl) and d.name}
    datatype_kind = _datatype_kind(module)  # row 48: names datatype-typed binders/params/returns/members
    lets = lift_let.expand_scope(method, closure, method_names)
    issues += lets.issues
    # A binder is a local whose type the substitution erases: one t cannot carry
    # (real, set, map, a tuple, a datatype, ...) is refused by that type's name, as
    # a parameter's is, wherever the body reads it. Not the three a substitution
    # makes harmless: `seq<nat>`/`nat` bounds are facts dafny proved of the value,
    # not assumptions, and an array-typed binder is an alias the read-only-array
    # rule then sees through. An unused binder's value is never read at all.
    for root in [source_method] + list(source_closure):
        for n in walk(root):
            if isinstance(n, LetExpr) and n.op == ":=":
                for b in n.binders:
                    bad = _type_issue(b.type) if b.type is not None else None
                    if bad == "datatype":  # row 48
                        bad = (f"datatype-{datatype_kind}" if datatype_kind is not None
                               else _id_type_gap(module, b.type) or bad)
                    if bad not in (None, "nat-seq-elements", "array") and lift_let.binder_uses(n, b.name):
                        issues.append((n.line, bad, b.name))
    for line in lets.lines:
        rewrites.append(Rewrite(rule="let-substituted", line=line))
    method, closure = lets.method, lets.closure

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

    # -- source-axiom / source-assume (row 51) ----------------------------
    # `{:axiom}`, `{:verify false}` and `assume` are read over the WHOLE
    # module (a declaration outside this method's closure is a note, not a
    # refusal -- `axiom_in_file` below), then checked against exactly what
    # LIFTER-DECISIONS row 51 names: the method's own closure (its spec,
    # body and invariants are all inside `_called_names(method)`'s reach)
    # and, for `assume`, the method's own body directly. This closure is
    # `_closure_incl_methods`, not the shared `closure`/`source_closure`:
    # `closure` stops at any callee that is not a FunctionDecl/LemmaDecl, so
    # an axiom-attributed METHOD reached as a callee (row 51 review finding
    # 2: `method {:axiom} DoubleIt(...)` called by a plain method) would
    # otherwise be neither checked against `axiomatised` here nor excluded
    # from `axiom_in_file` correctly -- it would be dropped from the check
    # entirely and then wrongly reported as an axiom lying outside the
    # closure, though it is a direct callee.
    axiom_closure = _closure_incl_methods(module, source_method)
    axiomatised = _axiomatised_names(module)
    axiom_only = _axiom_only_functions(module, axiomatised)
    closure_names = {d.name for d in axiom_closure if d.name}
    for d in axiom_closure:
        if not d.name:
            continue
        if d.name in axiomatised:
            issues.append((axiomatised[d.name], "source-axiom", d.name))
        elif isinstance(d, FunctionDecl) and d.name in axiom_only:
            issues.append((axiom_only[d.name], "source-axiom", d.name))
        if isinstance(d, LemmaDecl) and _lemma_has_assume(d):
            issues.append((d.line, "source-assume", "assume"))
    # A direct `assume` in the method's OWN body is caught below by the
    # generic per-node pass (`_scan_node_for_issues`'s `AssumeStmt` branch,
    # same reason `source-assume`) once `scope_roots` exists; not duplicated
    # here.
    axiom_in_file = tuple(sorted(
        {line for name, line in axiomatised.items() if name not in closure_names}
        | {line for name, line in axiom_only.items() if name not in closure_names}))

    # -- array mutation / allocation (decision 22), ahead of the
    # returns check: a `modifies-param` shape needs `method.returns`
    # empty to qualify (its synthesized return is the array; a method
    # that already returns something would need a SECOND return, which
    # t cannot express), so the zero-returns row below must see the
    # verdict first. --------------------------------------------------
    array_mutation, mutation_issue = find_array_mutation(method, closure, module)
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
            # Row 47 (2026-09-27, t/FEATURES-TRACK.md, zero-returns): a
            # method with no out-parameter is a t task only through
            # decision 22's modifies-param shape (SPEC.md "Sequences as
            # values": "a method whose effect is its array is a task whose
            # return is a seq"). The 2026-09-27 census read 39 such
            # methods refused `zero-returns`, and the name said nothing
            # about 35 of them: `find_array_mutation` had already named
            # the shape it could not map (`multi-array-mutation`, two
            # arrays written in one body, the DJ family's `a[i] := 0` plus
            # `sum[0] := total`) on a LATER line, which this method-line
            # issue then hid, or the method's `modifies` clause is real
            # but every write happens inside a callee (BubbleSort's
            # `Swap(a, j, j+1)`), which the shape detector never sees.
            # Now: a named mutation issue stands alone; a `modifies` with
            # no index assignment refuses `array-mutation` under the token
            # `modifies-via-call` (the method calls other methods) or
            # `modifies-no-index-assign`; and a method with no return and
            # no `modifies` is, in t's vocabulary, a lemma about its
            # parameters (SPEC.md "Lemmas (v1)": "Dafny's lemma ... with no
            # return"), which t states only inside a task that calls it,
            # so it refuses `lemma-shaped`.
            if mutation_issue is not None:
                pass
            elif any(isinstance(sp, ModifiesClause) for sp in method.specs):
                via_call = any(isinstance(n, CallStmt) for n in walk(method))
                issues.append((method.line, "array-mutation",
                               "modifies-via-call" if via_call else "modifies-no-index-assign"))
            else:
                issues.append((method.line, "lemma-shaped", method.name or "?"))
    elif len(method.returns) == 2:
        ret_a, ret_b = method.returns
        bad_a = _pair_component_issue(ret_a.type)
        bad_b = _pair_component_issue(ret_b.type)
        if bad_a is not None or bad_b is not None:
            bad_name = ret_a.name if bad_a is not None else ret_b.name
            issues.append((method.line, "multi-return-nested", bad_name))
        else:
            pair_returns = (ret_a, ret_b)
    elif len(method.returns) > 1:
        issues.append((method.line, "multi-return-arity", method.name or "?"))

    # A destructuring assign or declaration (`a, b := M(x);`, `var a, b :=
    # M(x);`: one value for two targets, Dafny's multi-return call sugar,
    # Reference Manual 8.5.2) lifts when the value is a call of another
    # two-return method (t/FEATURES-TRACK.md feature 6, 2026-09-27; decided
    # by `_method_calls` below, row 41). Any other shape -- a self-recursive
    # multi-return call, three or more targets, a target that is not a name
    # -- is not one `lift_rewrite._lift_stmt` maps (its multi-target Assign
    # zips targets against values pairwise and would silently drop an
    # assignment), so it is refused rather than mis-lifted. Before feature 6
    # this refused every two-return method with any destructuring assign.
    if method.body is not None:
        # other methods by out-parameter count; a destructuring call of one
        # with as many targets as out-parameters is `_method_calls`'s to
        # decide (two lift, three or more refuse `method-call-multi-return`)
        other_arity = {d.name: len(d.returns) for d in module.decls
                       if isinstance(d, MethodDecl) and d.name and d.name != method.name}

        def _call_of_other(v, n_targets: int) -> bool:
            return (isinstance(v, Call) and isinstance(v.fn, Ident)
                    and other_arity.get(v.fn.name) == n_targets)

        for n in walk(method.body):
            if isinstance(n, Assign) and len(n.targets) != len(n.values):
                ok = (len(n.values) == 1 and all(t.kind == "name" for t in n.targets)
                      and _call_of_other(n.values[0], len(n.targets)))
                if not ok:
                    issues.append((n.line, "multi-return-nested", "destructuring-assign"))
            elif isinstance(n, VarDeclStmt) and n.init and len(n.names) != len(n.init):
                ok = len(n.init) == 1 and _call_of_other(n.init[0], len(n.names))
                if not ok:
                    issues.append((n.line, "multi-return-nested", "destructuring-assign"))

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
            if reason == "datatype":  # row 48
                reason = (f"datatype-{datatype_kind}" if datatype_kind is not None
                          else _id_type_gap(module, p.type) or reason)
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
            # the same as `seq<int>` too. Row 30 (2026-09-10): a nested
            # `seq<seq<int>>`/`seq<seq<nat>>` return is accepted the same
            # way, nat rows included -- the return-side weaker theorem
            # (no per-row `>= 0` guarantee) is the same one a flat
            # `seq<nat>` return already has, just applied per row. Any
            # other seq shape (bool, string, three deep) stays refused.
            if not (_is_seq_of_int(rt) or _is_seq_of_nat(rt) or _is_seq_of_char(rt)
                    or _is_nested_seq_of_int(rt) or _is_nested_seq_of_nat(rt)
                    or _is_nested_seq_of_char(rt)):
                issues.append((ret_param.line, "seq-return", ret_param.name))
        elif (rt is not None and rt.kind == "array" and not rt.nullable
                and _is_array_of_int(rt) and array_mutation is not None
                and array_mutation.kind == "alloc-fill"):
            pass  # decision 22: an allocated array return is a seq return
        else:
            reason = _type_issue(rt)
            if reason == "datatype":  # row 48
                reason = (f"datatype-{datatype_kind}" if datatype_kind is not None
                          else _id_type_gap(module, rt) or reason)
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
        bad = array_readonly_issue(p.name, method, closure, module)
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
    tuple_names = _tuple_names(method, closure)  # row 44
    accepted_ids = (_array_mutation_accepted_ids(method, array_mutation, ret_param)
                     | frozenset(id(m) for _, _, m in null_checks)
                     | _dropped_function_decreases_set_ids(closure))
    for root in scope_roots:
        for n in walk(root):
            _scan_node_for_issues(n, issues, method.name, closure_names, method_names, accepted_ids,
                                  tuple_names, datatype_kind)

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
    kind_env = _build_kind_env(method, closure, _method_return_kinds(module),
                               _method_return_kind_lists(module))
    char_names, char_seq_names, nested_str_names = _build_char_names(method, closure)
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
                    _is_char_expr(n.left, char_names, char_seq_names, nested_str_names)
                    or _is_char_expr(n.right, char_names, char_seq_names, nested_str_names)):
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
            elif isinstance(n, SeqUpdate):
                # Row 30 (2026-09-10, SPEC.md "Nested sequences (v1)"):
                # the functional update EXPRESSION `s[i := r]` lifts to
                # t's own `update` operator (already real, decision 22's
                # array-mutation STATEMENT rewrite target) whenever its
                # base types `seq`, flat or nested alike; anything else
                # (an unresolvable base) stays refused `seq-update`.
                if expr_kind(n.base, kind_env.get) == "seq":
                    rewrites.append(Rewrite(rule="seq-update-lifted", line=n.line))
                else:
                    issues.append((n.line, "seq-update", ":="))
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
                elif n.type.kind == "int" and _is_char_expr(n.base, char_names, char_seq_names,
                                                             nested_str_names):
                    rewrites.append(Rewrite(rule="char-as-int-lifted", line=n.line))
                else:
                    issues.append((n.line, "as-cast", "as"))

    # -- definite assignment of the return, every path (section 4.7) -----
    # Row 45 (2026-09-27): no longer a refusal on its own. Dafny checks
    # definite assignment of an out-parameter SEMANTICALLY (a Boogie
    # obligation, "out-parameter 'r' ... might be uninitialized at this
    # return point"; Reference Manual 5.3.1.2, auto-initialization and
    # definite assignment), so a method this syntactic walk cannot see
    # assigning `r` on every path (an assignment inside `while true`,
    # under a `break`, in an if-case) may still be accepted by dafny, and
    # one dafny rejects is caught by `lift_check`'s own `verify-source`
    # step (refused `return-default-unverified`). The one return type
    # with no t default is `char` (dafny's own default is 'D'; t has no
    # char value to name it by), refused `return-default-char`.
    ret_default: Optional[str] = None
    if ret_param is not None and method.body is not None:
        if not _assigns_ret_all_paths(method.body, ret_param.name):
            if ret_param.type is not None and ret_param.type.kind == "char":
                issues.append((method.line, "return-default-char", ret_param.name))
            else:
                ret_default = ret_param.name
    # Row 29: the SAME check, once per out-parameter -- `_assigns_ret_
    # all_paths` already treats a `return e1, e2;` (any non-empty
    # ReturnStmt.values) as assigning whichever single `ret_name` it is
    # asked about, so calling it twice (once per component name) is
    # correct with no change to the helper itself.
    # Row 45: a pair component already opens the body with decision 13's
    # `default-init` (see `lift_rewrite.rewrite`), so an unassigned one
    # needs only the same `verify-source` gate; `ret_default` names the
    # first such component so the rewrite logs `return-default-init`.
    if pair_returns is not None and method.body is not None:
        ret_a, ret_b = pair_returns
        for comp in (ret_a, ret_b):
            if not _assigns_ret_all_paths(method.body, comp.name) and ret_default is None:
                ret_default = comp.name

    # -- self-recursion shape (section 4.5's `r := M(args)` row) ---------
    issues += _self_call_positions(method)

    # -- calls of OTHER methods (SPEC.md "Methods (v1)", row 37) ----------
    callee_plans, call_issues = _method_calls(module, method, _stack, _memo)
    issues += call_issues

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
    # Feature 5 (2026-09-27): the closure's predicates, for the range
    # through a predicate rule; the same dict `lift_rewrite` reads off
    # `Scope.predicates`, so the two stages bound every quantifier alike.
    predicates = closure_predicates(closure)
    for root in scope_roots:
        for n in walk(root):
            if isinstance(n, Quantifier):
                got = bound_quantifier(n, predicates)
                if got is None:
                    issues.append((n.line, "unbounded-quantifier", n.kind))
                else:
                    has_mem = any(mem is not None for _, _, _, mem in got["binders"])
                    rewrites.append(Rewrite(rule="in-desugared" if has_mem
                                             else "quantifier-bounded", line=n.line))
                    for rule in sorted(got.get("rules", ())):
                        if rule not in ("in-desugared", "quantifier-bounded"):
                            rewrites.append(Rewrite(rule=rule, line=n.line))

    # -- mutual recursion ---------------------------------------------------
    mr = _mutual_recursion_issue(closure)
    if mr is not None:
        issues.append(mr)

    # -- function-contract (a `reads` clause on any closure function) ----
    # A `reads` clause naming exactly the function's OWN array-typed
    # parameter(s) (`predicate InArray(a: array<int>, x: int) reads a`)
    # is framing, not a functional contract: a Dafny FUNCTION can never
    # write through any reference (functions are heap-read-only by
    # construction, ghost or not), so the array named is read-only in
    # this function's body by CONSTRUCTION, the exact condition decision
    # 1 already grants a method's own array parameter -- t has no heap
    # to frame in the first place once that array lifts to a `seq`
    # value, so the clause is simply dropped, the same way an empty
    # `reads ()` already was before this row. Measured on
    # `dafny-synthesis_task_id_2/161/249/579` (`InArray`, the MBPP-DFY
    # 164's own four `function-contract` census rows, every one this
    # exact predicate): `InArray` has NO `requires`/`ensures` at all,
    # only `reads a` -- the one thing this row's own name in
    # LIFTER-DECISIONS.md ("a function with its own requires or
    # ensures") does not actually describe, which is why every one of
    # these four stayed refused under the generic reads-nonempty rule
    # this loop used to apply unconditionally. A reads clause naming
    # anything ELSE (a field, a different array, `*`, a non-array
    # expression) still refuses `function-contract` exactly as before:
    # this widening touches only the shape decision 1 already trusts.
    for d in closure:
        if isinstance(d, FunctionDecl):
            # 2026-09-27 (t/FEATURES-TRACK.md, strings): a t spec_fun's result
            # is int, bool or seq (SPEC.md gate 3, `"result": "int"|"bool"|
            # "seq"`, the seq result since "Seq-valued spec_funs (v1)",
            # 2026-09-27, LIFTER-DECISIONS row 49). A closure function
            # returning `string`, `seq<char>`, `seq<int>` or `seq<nat>` lifts
            # to a seq-valued spec_fun (row 28's code points for the string
            # spellings, exactly as a string parameter does); a `char` result
            # is an int (row 28). A `function F(..): bool` is a predicate
            # spelled as a function (Dafny Reference Manual 6.4.2: a
            # predicate is a function returning bool) and lifts as one, a
            # bool result, exactly as `_lift_function` already types it;
            # the first spelling of this check (row 43's same-day note)
            # listed int/nat/char only and refused 66 of the 305
            # `function-result` methods of the 2026-09-27 baseline re-lift
            # by this omission alone (t/FEATURES-SEQFUN-2026-09-27.md).
            # Anything else -- a nested seq, a tuple, a set, a datatype, a
            # real -- still refuses here by name, `function-result`; before
            # 2026-09-27 every non-int result did (135 methods of the
            # 2026-09-26 lift).
            if (not d.is_predicate and d.ret_type is not None
                    and not (d.ret_type.kind in ("int", "nat", "char", "bool")
                             or _is_seq_fun_result(d.ret_type))):
                issues.append((d.line, "function-result",
                               f"{d.name or '?'}:{_type_text(d.ret_type)}"))
            own_array_names = {p.name for p in d.params
                                if p.type is not None and p.type.kind == "array"
                                and not p.type.nullable and _is_array_of_int(p.type)}
            for s in d.specs:
                if isinstance(s, ReadsClause):
                    if isinstance(s.exprs, Star):
                        issues.append((s.line, "function-contract", d.name or "?"))
                        continue
                    exprs = s.exprs if isinstance(s.exprs, tuple) else ()
                    if not exprs:
                        continue
                    if all(isinstance(e, Ident) and e.name in own_array_names for e in exprs):
                        rewrites.append(Rewrite(rule="function-reads-array-dropped", line=s.line))
                        continue
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

    for cname, _cplan in callee_plans:
        rewrites.append(Rewrite(rule="method-lifted", line=_cplan.method.line))
    return Liftable(method=source_method, closure=source_closure, rewrites=rewrites,
                    pair_returns=pair_returns, callees=tuple(callee_plans),
                    ret_default=ret_default, axiom_in_file=axiom_in_file)


def _scan_node_for_issues(n: Node, issues: list, method_name: str,
                           closure_names: set[str],
                           method_names: set[str] = frozenset(),
                           accepted_ids: frozenset[int] = frozenset(),
                           tuple_names: frozenset = frozenset(),
                           datatype_kind: Optional[str] = None) -> None:
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
    that same dedicated pass. Row 30 (2026-09-10): `SeqUpdate` moved out
    the same way, its refusal now conditional on whether its base types
    `seq` (`expr_kind`, the dedicated pass below), not unconditional."""
    if isinstance(n, (Old, Fresh)):
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
        # Row 51 (2026-09-27): renamed from the bare `assume` this branch
        # used before -- `source-assume` is now the one reason for BOTH an
        # assume directly in the method's own body (this branch: `walk()`
        # only ever reaches an `AssumeStmt` here through `method.body`
        # itself, since a `FunctionDecl` body is an expression and a
        # `LemmaDecl`'s own body is never a `scope_roots` member -- `parts`
        # is not a dataclass field, by design) and one inside a callee
        # lemma's proof (`_lemma_has_assume`, checked separately in
        # `classify` over `closure` before this generic pass runs, since
        # that scan needs the lemma's raw `text`, not this walk).
        issues.append((n.line, "source-assume", "assume"))
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
        if id(n) not in accepted_ids:
            issues.append((n.line, "array", "local array"))
    elif isinstance(n, MapDisplay):
        issues.append((n.line, "map", "{...}"))
    elif isinstance(n, SetDisplay):
        if id(n) not in accepted_ids:
            issues.append((n.line, "set", "{...}"))
    elif isinstance(n, Comprehension) and n.kind == "set":
        issues.append((n.line, "set", "set-comprehension"))
    elif isinstance(n, Comprehension) and n.kind == "map":
        issues.append((n.line, "map", "map-comprehension"))
    elif isinstance(n, Comprehension) and n.kind == "seq":
        issues.append((n.line, "seq-comprehension", "seq-comprehension"))
    elif isinstance(n, TupleExpr):
        # Row 44 (2026-09-27): a two-element tuple literal is t's pair
        # literal (SPEC.md "Pairs (v1)"); any other arity has no t value.
        if len(n.elems) != 2:
            issues.append((n.line, "tuple-arity", f"({len(n.elems)})"))
    elif isinstance(n, TypeTest):
        issues.append((n.line, "as-cast", "is"))
    elif isinstance(n, Member) and n.name != "Length":
        # Row 44: `.0`/`.1` on a name declared with an accepted tuple type
        # is a pair projection. Row 48 (2026-09-27) names everything else
        # by what it is (measured on the 78 methods the old blanket
        # `datatype` covered: 42 of them touched no datatype at all):
        # `.0`/`.1` on an indexed element is a seq of pairs (row 46's
        # name), on any other expression a tuple projection t's pair does
        # not reach yet; `Length0`/`Length1` are array2's; `Floor` is
        # real's; a `Ctor?` discriminator or a field on a file that
        # declares datatypes is named by the datatype's shape; a member on
        # a file with no datatype is a class, map or module member.
        if n.name in ("0", "1"):
            if not (isinstance(n.base, Ident) and n.base.name in tuple_names):
                if isinstance(n.base, Index):
                    issues.append((n.line, "seq-of-pair", n.name))
                else:
                    issues.append((n.line, "tuple-projection", n.name))
        elif n.name in ("Length0", "Length1"):
            issues.append((n.line, "array2", n.name))
        elif n.name == "Floor":
            issues.append((n.line, "real", n.name))
        elif datatype_kind is None:
            issues.append((n.line, "member-access", n.name))
        elif n.name.endswith("?"):
            issues.append((n.line, f"datatype-{datatype_kind}", "discriminator " + n.name))
        else:
            issues.append((n.line, f"datatype-{datatype_kind}", "field " + n.name))
    elif isinstance(n, VarDeclStmt) and n.ghost:
        issues.append((n.line, "ghost-local", "ghost var"))
    elif isinstance(n, CallStmt):
        if n.name == method_name:
            issues.append((n.line, "self-call-lazy", n.name))
        elif n.name not in closure_names:
            issues.append((n.line, "calls-other-method", n.name))
        # else: a lemma call in the closure -- dropped, not refused
        # (decision 8; see _plan_rewrites' lemma-call-dropped entry).
    # A `Call` naming a DIFFERENT method (`x := M(args)`, `var x := M(args)`,
    # or any other position) is no longer refused here: `_method_calls`
    # (row 37, SPEC.md "Methods (v1)") decides it with the context it needs.


def _method_return_kinds(module: Module) -> dict[str, str]:
    """dafny method name -> the kind of its one return, for every method of
    `module` with exactly one out-parameter of a kind `expr_kind` knows, so
    `var x := M(args);` types `x` from `M`'s declared return (row 37)."""
    kinds: dict[str, str] = {}
    for d in module.decls:
        if isinstance(d, MethodDecl) and d.name and len(d.returns) == 1:
            k = _declared_kind(d.returns[0].type)
            if k is not None:
                kinds[d.name] = k
    return kinds


def _method_return_kind_lists(module: Module) -> dict[str, list]:
    """dafny method name -> the kinds of its out-parameters, in order, for
    every method with two or more (row 41: `var a, b := M(x);` types `a` and
    `b` from them); a kind `expr_kind` does not know is None in its slot."""
    return {d.name: [_declared_kind(r.type) for r in d.returns]
            for d in module.decls
            if isinstance(d, MethodDecl) and d.name and len(d.returns) >= 2}


def _method_calls(module: Module, method: MethodDecl, stack: tuple, memo: dict
                  ) -> tuple[list, list[tuple[int, str, str]]]:
    """Row 37 (2026-09-26, SPEC.md "Methods (v1)"): every call of ANOTHER
    method in `method`'s body, decided. Covered, and returned as
    `(name, Liftable)` once per callee in first-call order: the callee is a
    non-ghost method of this module with exactly one out-parameter and no
    type parameters, the call is the whole right-hand side of a one-target
    `x := M(args);` or a one-name `var x := M(args);` (Dafny reference
    manual 8.5.2: a method call is a whole right-hand side, its results
    assigned to as many left-hand sides as it has out-parameters, and "the
    result of a method call is not allowed to be used as an argument of
    another method call"), no argument calls a method, the callee itself
    classifies `Liftable` (recursively, this function's own caller), it
    neither mutates nor allocates an array (a heap effect on the caller, or
    an array result, t's call has no word for), and no method on the call
    chain is reached again (a callee's DIRECT self-recursion is its own
    classify's self-call row, with its own decreases rule). Everything else
    is an issue by name: `method-call-ghost`, `method-call-no-return`,
    `method-call-multi-return`, `method-call-generic`, `method-call-position`,
    `method-call-array`, `method-mutual-recursion`, or
    `callee-refused:<the callee's own reason>` (token `<callee>:<token>`).
    A call STATEMENT `M(args);` of a method that is not a lemma is still
    `calls-other-method` (`_scan_node_for_issues`): a method with no
    out-parameter has no value for t to bind."""
    issues: list[tuple[int, str, str]] = []
    plans: list = []
    if method.body is None:
        return plans, issues
    by_name = {d.name: d for d in module.decls if isinstance(d, MethodDecl) and d.name}

    def is_other_call(n) -> bool:
        return (isinstance(n, Call) and isinstance(n.fn, Ident)
                and n.fn.name in by_name and n.fn.name != method.name)

    whole_rhs: set[int] = set()
    # Row 41 (t/FEATURES-TRACK.md feature 6, 2026-09-27): `a, b := M(args);`
    # and `var a, b := M(args);`, Dafny's call of a two-out-parameter method
    # (Reference Manual 8.5.2: "assigned to as many left-hand sides as it
    # has out-parameters"), keyed by the number of targets the call must
    # match; `lift_rewrite` binds the callee's pair return to a fresh local
    # and projects it (`p.0`, `p.1`) into the two names.
    arity_at: dict[int, int] = {}
    for s in walk(method.body):
        rhs = None
        if (isinstance(s, Assign) and len(s.values) == 1
                and all(t.kind == "name" for t in s.targets) and 1 <= len(s.targets) <= 2):
            rhs = s.values[0]
            n_targets = len(s.targets)
        elif (isinstance(s, VarDeclStmt) and not s.ghost and s.init
                and len(s.init) == 1 and 1 <= len(s.names) <= 2):
            rhs = s.init[0]
            n_targets = len(s.names)
        if rhs is not None and is_other_call(rhs):
            whole_rhs.add(id(rhs))
            arity_at[id(rhs)] = n_targets

    seen: set[str] = set()
    for n in walk(method.body):
        if not is_other_call(n):
            continue
        name = n.fn.name
        callee = by_name[name]
        if callee.ghost:
            issues.append((n.line, "method-call-ghost", name))
            continue
        if len(callee.returns) == 0:
            issues.append((n.line, "method-call-no-return", name))
            continue
        if len(callee.returns) > 2:
            issues.append((n.line, "method-call-multi-return", name))
            continue
        if callee.type_params:
            issues.append((n.line, "method-call-generic", name))
            continue
        if id(n) not in whole_rhs or any(is_other_call(x) for a in n.args for x in walk(a)):
            issues.append((n.line, "method-call-position", name))
            continue
        if arity_at.get(id(n)) != len(callee.returns):
            # `x := Two(a);` (one name for two out-parameters) is a Dafny
            # type error; the source verified, so this is a shape the
            # parser read but Dafny never accepts. Refused by the call's
            # own name for completeness.
            issues.append((n.line, "method-call-multi-return", name))
            continue
        if name in stack:
            issues.append((n.line, "method-mutual-recursion", name))
            continue
        if name in seen:
            continue
        seen.add(name)
        verdict = memo.get(name)
        if verdict is None:
            verdict = classify(module, callee, stack + (method.name,), memo)
            memo[name] = verdict
        if isinstance(verdict, Refusal):
            if verdict.reason == "method-mutual-recursion":
                issues.append((n.line, verdict.reason, verdict.token))
            elif verdict.reason.startswith("callee-refused:"):
                # a callee's callee: one prefix, the chain in the token
                issues.append((n.line, verdict.reason, f"{name}:{verdict.token}"))
            else:
                issues.append((n.line, f"callee-refused:{verdict.reason}",
                               f"{name}:{verdict.token}"))
            continue
        mutation, _ = find_array_mutation(callee, _closure(module, callee), module)
        if mutation is not None:
            issues.append((n.line, "method-call-array", name))
            continue
        plans.append((name, verdict))
    return plans, issues


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
