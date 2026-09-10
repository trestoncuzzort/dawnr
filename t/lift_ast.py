"""Dafny-side AST for the lifter (LIFTER-DESIGN.md section 3), plus the two
cross-module records every stage passes along: `Refusal` (a method or file
that will not lift, and why) and `LiftRecord` (the provenance sidecar of
section 8 and 18.2 for a method that did lift).

This module is data only. It is the contract the other lift_*.py modules
build and consume; it decides nothing and computes nothing. Every AST node
carries the rprint line it came from (`line`, inherited from `Node`), because
every refusal in section 5 must quote a line and every rewrite in section 4
must log one.

The grammar mirrors LIFTER-DESIGN.md section 3's EBNF one production at a
time. Where the grammar allows a bare "*" (a nondeterministic `if`/`while`
guard, an `ExprList` of "*", a havoc `Rhs`), the sentinel `Star` node stands
in for it so every such position has exactly one representation. Constructs
in section 3's `Skipped` production (datatype, class, trait, ...) are parsed
into `SkippedDecl` and never elaborated further: the parser recognises more
than t accepts so the classifier can name a precise refusal, never because
skipped declarations are partially supported.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union


# ---------------------------------------------------------------------------
# Base node.
# ---------------------------------------------------------------------------

@dataclass
class Node:
    """Every AST node's shared field: the 1-based line in the rprint text
    this node was read from. A parse error, a refusal, and a rewrite log
    entry all point back through this field to the exact source line."""
    line: int


@dataclass
class Star(Node):
    """The bare "*" token, wherever section 3's grammar allows it in place
    of an Expr: a nondeterministic `if`/`while` guard, an `ExprList` of
    "*" (reads/modifies/decreases "everything, unspecified"), or a havoc
    `Rhs`. One node type for all three positions; the position itself
    (which field it sits in) says which reading applies."""


@dataclass
class Attr(Node):
    """A `{:Id ExprList}` attribute. Always recorded, never acted on: t has
    no attribute system, so every attribute a node carries is dropped by
    the rewriter and counted, never interpreted (e.g. `{:trigger ...}` on a
    quantifier changes no lift decision)."""
    name: str
    args: tuple["Expr", ...] = ()


# ---------------------------------------------------------------------------
# Types.
# ---------------------------------------------------------------------------

@dataclass
class Type(Node):
    """One node for every alternative of section 3's `Type` production.
    `kind` is the leading keyword or "id" for a user identifier; `args`
    holds type arguments (`seq<T>` -> kind="seq", args=(T,); a function
    type `Type -> Type` -> kind="func", args=(dom, cod); a tuple type
    `(T, T, ...)` -> kind="tuple", args=(...)). `nullable` is `array?<T>`.
    `bits` is the N of `bv N`. `name` is the identifier text when
    kind == "id" (a user type name, e.g. a datatype cursed to be
    `type-decl`-refused) and the generic arguments, if any, are in `args`."""
    kind: str
    args: tuple["Type", ...] = ()
    nullable: bool = False
    bits: Optional[int] = None
    name: Optional[str] = None


@dataclass
class Param(Node):
    """A `Params` entry, a `Binders` entry, or a `VarDecl`: anywhere the
    grammar pairs an identifier with an optional type. `type` is `None`
    exactly where the source left it out (an untyped `var`, a `VarDecl`
    with no `: Type`); the census's `untyped-var` gap names this case."""
    name: str
    type: Optional[Type] = None
    ghost: bool = False


# ---------------------------------------------------------------------------
# Expressions.
# ---------------------------------------------------------------------------

@dataclass
class Expr(Node):
    """Base of every `Expr` alternative. Never instantiated directly."""


@dataclass
class IntLit(Expr):
    value: int


@dataclass
class RealLit(Expr):
    """A `real` literal, kept as source text (t has no real type; this node
    exists only so the `real` refusal can quote what it saw)."""
    text: str


@dataclass
class BoolLit(Expr):
    value: bool


@dataclass
class CharLit(Expr):
    text: str


@dataclass
class StringLit(Expr):
    text: str


@dataclass
class Ident(Expr):
    name: str


@dataclass
class Old(Expr):
    arg: Expr


@dataclass
class Fresh(Expr):
    arg: Expr


@dataclass
class Unary(Expr):
    """`!` or unary `-`. Repeated unary minus ("--x") is two nested `Unary`
    nodes per section 3's note, never folded."""
    op: str            # "!" | "-"
    arg: Expr


@dataclass
class Binary(Expr):
    """One binary operator at the `Add`/`Mul` precedence levels: `+ - * / %`.
    `/` and `%` parse (the parser accepts more than t does) so `div-mod` can
    quote the line; t itself has neither."""
    op: str
    left: Expr
    right: Expr


@dataclass
class NaryBool(Expr):
    """The `OrAnd` production: `Not ("&&" Not)*` or `Not ("||" Not)*`,
    flattened to one n-ary node per run of the same operator (mixing `&&`
    and `||` without parens is not in the grammar; rprint always
    parenthesises a mix, so a mix always shows up as nested `NaryBool`
    nodes joined by a `Chain`-free `Unary`/parenthesised `Expr`, never as
    one node with mixed children)."""
    op: str            # "&&" | "||"
    args: tuple[Expr, ...]


@dataclass
class Implies(Expr):
    """`==>`, right-associative: `a ==> b ==> c` is `Implies(a, Implies(b,
    c))`. `<==` desugars to the same node with operands swapped at parse
    time (section 3's `OrAnd ("<==" OrAnd)*` reads left-associative; each
    step becomes `Implies(right, left)`)."""
    left: Expr
    right: Expr


@dataclass
class Iff(Expr):
    """`<==>`, the lowest-precedence operator (section 3's `Equiv`)."""
    left: Expr
    right: Expr


@dataclass
class Chain(Expr):
    """A relational chain: `Rel ::= Add (RelOp Add)*`. Two operands with one
    operator print as a plain `Binary`-shaped chain of length 1 by
    convention (classify.py may fold that case); two or more operators
    (`0 <= i < n`, `a == b == c`) need this node because t's `Expr` grammar
    (SYNTAX.md) has no chain node at all: a chain of length >= 2 is always
    `chain-desugared` (LIFTER-DECISIONS.md, section 18.2) or a refusal,
    never emitted as-is."""
    ops: tuple[str, ...]         # len(operands) - 1 entries
    operands: tuple[Expr, ...]


@dataclass
class IfExpr(Expr):
    cond: Expr
    then: Expr
    else_: Expr


@dataclass
class Quantifier(Expr):
    """`forall`/`exists`. `attrs` are recorded and dropped (see `Attr`).
    `range` is the optional `"|" Expr` guard; `None` means unguarded, which
    section 3's grammar allows but is unbounded and refused
    (`unbounded-quantifier`) unless a rewrite bounds it from the range
    guard's shape (LIFTER-DESIGN.md section 4)."""
    kind: str                    # "forall" | "exists"
    binders: tuple[Param, ...]
    attrs: tuple[Attr, ...]
    range: Optional[Expr]
    body: Expr


@dataclass
class SetDisplay(Expr):
    elems: tuple[Expr, ...]


@dataclass
class MapDisplay(Expr):
    """`{ k := v, ... }`-style map display; `pairs` is (key, value) per
    entry. Always a `map` refusal downstream; kept for a precise line."""
    pairs: tuple[tuple[Expr, Expr], ...]


@dataclass
class SeqDisplay(Expr):
    """`[e, e, ...]`. A non-empty display is `seq-literal` (refused in v1,
    decision 3); `[]` alone is the `s == []` / `s != []` shape decision 2's
    `in-desugared` sibling rule does not cover and decision 3 refuses too."""
    elems: tuple[Expr, ...]


@dataclass
class Comprehension(Expr):
    """`set Binders ... :: Expr`, `map Binders ... :: Expr := Expr`, or
    `seq(n, i => Expr)`-style constructions folded to one shape: always a
    refusal (`set`/`map`/`seq-comprehension`), kept only for its line and
    kind. `value` is the map comprehension's value expression, `None` for
    `set`/`seq`."""
    kind: str                    # "set" | "map" | "seq"
    binders: tuple[Param, ...]
    range: Optional[Expr]
    body: Expr
    value: Optional[Expr] = None


@dataclass
class TupleExpr(Expr):
    """`"(" Expr ("," Expr)+ ")"` (arity >= 2; arity 1 is just parens around
    one Expr and is not wrapped in this node). Always `tuple`-refused as a
    value; also the printed shape of a tuple `decreases` clause, handled
    separately by `DecreasesClause.exprs` rather than this node."""
    elems: tuple[Expr, ...]


@dataclass
class Call(Expr):
    """`Primary "(" [ExprList] ")"`: a function or spec_fun application, or
    (if `fn` is not a bound Id) a call through a value of function type
    (`higher-order`, refused). `fn` is generally an `Ident`."""
    fn: Expr
    args: tuple[Expr, ...]


@dataclass
class Index(Expr):
    """`Primary "[" Expr "]"`: sequence or array indexing (`s[i]`, `a[i]`)."""
    base: Expr
    index: Expr


@dataclass
class Slice(Expr):
    """`Primary "[" [Expr] ".." [Expr] "]"`. `lo`/`hi` are `None` where the
    source omitted them (`s[..k]`, `s[k..]`, `s[..]`). Always `seq-slice`
    (refused): t has no slicing operator."""
    base: Expr
    lo: Optional[Expr]
    hi: Optional[Expr]


@dataclass
class SeqUpdate(Expr):
    """`Primary "[" Expr ":=" Expr "]"`: functional sequence update.
    Lifts to t's `update` operator when the base types `seq` (row 30,
    2026-09-10, SPEC.md "Nested sequences (v1)"); else refused
    `seq-update` (an unresolvable base)."""
    base: Expr
    index: Expr
    value: Expr


@dataclass
class Member(Expr):
    """`Primary "." Id`: field/property access, most commonly `a.Length`
    (rewritten to `len(a)` under decision 1's read-only-array row, refused
    as `array` otherwise) or a datatype destructor (refused, `datatype`)."""
    base: Expr
    name: str


@dataclass
class Cast(Expr):
    """`Primary "as" Type`. Always `as-cast` in the census vocabulary."""
    base: Expr
    type: Type


@dataclass
class TypeTest(Expr):
    """`Primary "is" Type`."""
    base: Expr
    type: Type


@dataclass
class Cardinality(Expr):
    """`"|" Expr "|"`: `len` for a seq/array (`|s|` desugars to `len(s)`),
    or a set/map cardinality (refused, `set`/`map`)."""
    arg: Expr


# ---------------------------------------------------------------------------
# Rhs-only and guard-only alternatives that are not plain Exprs.
# ---------------------------------------------------------------------------

@dataclass
class NewRhs(Node):
    """A `"new" ...` allocation on the right of `:=`. t has no heap, so
    this is always a refusal (`array` for `new T[n]`, `heap`/`datatype`
    otherwise); the source text is kept verbatim rather than parsed
    further, since nothing past the refusal reads it."""
    text: str


Rhs = Union[Expr, Star, NewRhs]
ExprListOrStar = Union[tuple[Expr, ...], Star]


# ---------------------------------------------------------------------------
# Specification clauses (FSpec, MSpec, LoopSpec share these shapes).
# ---------------------------------------------------------------------------

@dataclass
class Spec(Node):
    """Base of one `FSpec`/`MSpec`/`LoopSpec` entry."""


@dataclass
class RequiresClause(Spec):
    expr: Expr


@dataclass
class EnsuresClause(Spec):
    expr: Expr


@dataclass
class InvariantClause(Spec):
    """Loop-only (`LoopSpec`'s `"invariant" Expr`)."""
    expr: Expr


@dataclass
class ReadsClause(Spec):
    """Function-only (`FSpec`'s `"reads" ExprList`)."""
    exprs: ExprListOrStar


@dataclass
class ModifiesClause(Spec):
    """Method or loop `"modifies" ExprList`."""
    exprs: ExprListOrStar


@dataclass
class DecreasesClause(Spec):
    """`"decreases" ExprList`, on a function, method, or loop. `exprs` has
    more than one entry exactly for a tuple (lexicographic) measure
    (decision 11); `Star` is Dafny's `decreases *` (`decreases-star`,
    refused unconditionally)."""
    exprs: ExprListOrStar


FSpec = Union[RequiresClause, EnsuresClause, ReadsClause, DecreasesClause]
MSpec = Union[RequiresClause, EnsuresClause, ModifiesClause, DecreasesClause]
LoopSpec = Union[InvariantClause, DecreasesClause, ModifiesClause]


# ---------------------------------------------------------------------------
# Statements.
# ---------------------------------------------------------------------------

@dataclass
class Stmt(Node):
    """Base of every `Stmt` alternative."""


@dataclass
class Lhs(Node):
    """One target of a (possibly parallel) assignment: a bare name, an
    indexed target `Expr "[" Expr "]"` (array write, always
    `array-mutation`), or a field target `Expr "." Id` (always a
    refusal: t has no heap)."""
    kind: str                    # "name" | "index" | "field"
    name: Optional[str] = None   # kind == "name"
    base: Optional[Expr] = None  # kind in ("index", "field")
    index: Optional[Expr] = None # kind == "index"
    field: Optional[str] = None  # kind == "field"


@dataclass
class Assign(Stmt):
    """`Lhs ("," Lhs)* ":=" Rhs ("," Rhs)* ";"`. Parallel assignment
    (`len(targets) > 1`) is always `parallel-assign-temps`-rewritten to
    sequential assignment through fresh temporaries (LIFTER-DESIGN.md
    section 4); a single target with a single Rhs is the common case."""
    targets: tuple[Lhs, ...]
    values: tuple[Rhs, ...]


@dataclass
class VarDeclStmt(Stmt):
    """`"var" ["ghost"] VarDecl ("," VarDecl)* [":=" Rhs ("," Rhs)*] ";"`.
    `ghost` is the source's `ghost` modifier (a ghost local read by
    executable code is `ghost-var`, refused). `init` is `None` for an
    uninitialised declaration (`uninitialized-local` if read before an
    assignment reaches every path, decision 13's `default-init` otherwise)."""
    ghost: bool
    names: tuple[Param, ...]
    init: Optional[tuple[Rhs, ...]]


@dataclass
class AssignSuchThat(Stmt):
    """`"var" VarDecl ("," VarDecl)* ":|" Expr ";"`. Always `such-that-exec`
    (refused): t has no nondeterministic-choice statement."""
    names: tuple[Param, ...]
    cond: Expr


@dataclass
class IfStmt(Stmt):
    """`"if" (Expr | "*") Block ["else" (Block | IfStmt)]`. `else_` is a
    tuple of statements for a `Block` else, a nested `IfStmt` for an
    `else if` chain (kept as a single node, not flattened, so the source's
    nesting depth is exactly what a rewrite log line refers to), or `None`
    for no else (`if-no-else`, which decision-file policy may still allow
    to lift with a synthesised `then`-only-guarded else in the classifier,
    never here)."""
    cond: Union[Expr, Star]
    then: tuple[Stmt, ...]
    else_: Union[tuple[Stmt, ...], "IfStmt", None]


@dataclass
class IfCaseStmt(Stmt):
    """`"if" "{" ("case" Expr "=>" Stmt*)+ "}"`. Always refused
    (`no-if-no-loop`'s sibling; the census has no exact name for this
    shape, so the classifier names it directly, e.g. `if-case`)."""
    cases: tuple[tuple[Expr, tuple[Stmt, ...]], ...]


@dataclass
class WhileStmt(Stmt):
    """`"while" (Expr | "*") LoopSpec* Block`. `specs` holds
    `InvariantClause`/`DecreasesClause`/`ModifiesClause` entries in source
    order; a loop with no `DecreasesClause` in `specs` and none inferable
    is `uninferable-decreases` (section 5)."""
    cond: Union[Expr, Star]
    specs: tuple[LoopSpec, ...]
    body: tuple[Stmt, ...]


@dataclass
class WhileCaseStmt(Stmt):
    """`"while" "{" ("case" Expr "=>" Stmt*)+ "}"`. Always refused."""
    specs: tuple[LoopSpec, ...]
    cases: tuple[tuple[Expr, tuple[Stmt, ...]], ...]


@dataclass
class ForStmt(Stmt):
    """`"for" Id [":" Type] ":=" Expr ("to" | "downto") Expr LoopSpec*
    Block`. Desugared per decision 15 / LIFTER-DESIGN.md section 4 to a
    `WhileStmt` with the implicit range invariant and the `hi - k`
    measure; this node is what the parser hands the classifier before that
    rewrite runs, so `for-loop`/`for-desugared` can quote the original
    line even after the rewrite is applied."""
    var: str
    var_type: Optional[Type]
    lo: Expr
    direction: str                # "to" | "downto"
    hi: Expr
    specs: tuple[LoopSpec, ...]
    body: tuple[Stmt, ...]


@dataclass
class ReturnStmt(Stmt):
    """`"return" [Expr ("," Expr)*] ";"`. `values` is empty for a bare
    `return;` (a "tail return", decision-vocabulary `tail-return`), which
    only means something once section 4's return-elaboration rule has run;
    a `return` with values is `trailing-return`."""
    values: tuple[Expr, ...]


@dataclass
class BreakStmt(Stmt):
    label: Optional[str] = None


@dataclass
class ContinueStmt(Stmt):
    label: Optional[str] = None


@dataclass
class AssertStmt(Stmt):
    """`"assert" Expr ";"`. Dropped and counted (`assert-dropped`,
    decision 8): a hint, never part of the lifted spec."""
    cond: Expr
    attrs: tuple[Attr, ...] = ()


@dataclass
class AssertByStmt(Stmt):
    """`"assert" Expr "by" Block`. Dropped and counted the same as
    `AssertStmt`; `proof` is never elaborated."""
    cond: Expr
    proof: tuple[Stmt, ...] = ()


@dataclass
class AssumeStmt(Stmt):
    """`"assume" Expr ";"` in executable code. Always `assume` (refused,
    decision 7): the source's `assume` was a census hint, but a lifted
    `assume` would make the lifted theorem weaker than the one dafny
    checked, which this project refuses to do silently."""
    cond: Expr


@dataclass
class CalcStmt(Stmt):
    """`"calc" ...`, brace-matched by the parser and kept as raw text.
    Dropped and counted (`calc`, decision 8's hint list); never
    elaborated, since t has no calculation statement."""
    text: str


@dataclass
class ForallStmt(Stmt):
    """`"forall" Binders [Attr*] ["|" Expr] Block`, the forall-statement
    form (distinct from the `Quantifier` expression). Always refused
    (`forall-statement`, census name): t has no forall-statement, only the
    `forall`/`exists` expression form."""
    binders: tuple[Param, ...]
    attrs: tuple[Attr, ...]
    range: Optional[Expr]
    body: tuple[Stmt, ...]


@dataclass
class PrintStmt(Stmt):
    """`"print" ExprList ";"`. Always `io` (refused): t bodies are pure."""
    args: ExprListOrStar


@dataclass
class ExpectStmt(Stmt):
    """`"expect" Expr ";"`. Always `nondet`/`io`-adjacent refusal (a runtime
    check with no proof-relevant meaning in t)."""
    cond: Expr


@dataclass
class RevealStmt(Stmt):
    """`"reveal" ... ";"`. Dropped and counted (`reveal-opaque`, decision
    8's hint list): only meaningful with `opaque`, which t bodies never use."""
    text: str


@dataclass
class LabelStmt(Stmt):
    """`"label" Id ":" Stmt`. `stmt` is the labelled statement; a `break`
    or `continue` targeting this label carries the same `label` string."""
    label: str
    stmt: Stmt


@dataclass
class CallStmt(Stmt):
    """`Id "(" [ExprList] ")" ";"`: a call of a method other than the
    enclosing one is `calls-other-method`; a call of a lemma is
    `lemma-call` (dropped, decision 8); a self-call is section 4's
    self-recursion rewrite (`Call` expression territory once hoisted,
    SPEC.md gate 3) unless it sits under a lazily evaluated operator or a
    quantifier body (`self-call-lazy`, refused)."""
    name: str
    args: tuple[Expr, ...]


@dataclass
class BlockStmt(Stmt):
    """A bare nested `Block` used as a `Stmt` (the grammar's trailing
    `| Block` alternative). Rare; kept distinct from the containing list
    so a rewrite that needs to know "this was its own scope" can tell."""
    body: tuple[Stmt, ...]


# ---------------------------------------------------------------------------
# Declarations.
# ---------------------------------------------------------------------------

@dataclass
class Decl(Node):
    """Base of every `Decl` alternative (`Function`, `Method`, `Lemma`,
    `Skipped`)."""
    name: Optional[str] = None


@dataclass
class FunctionDecl(Decl):
    """`["ghost"] ("function" | "predicate") Id [TypeParams] "(" Params ")"
    [":" Type] FSpec* ("{" Expr "}" | )`. `body is None` means bodyless
    (`bodyless-function`, refused: the classifier never guesses a body).
    `is_predicate` distinguishes `predicate` (implicit `: bool`) from
    `function`; both are represented identically otherwise."""
    ghost: bool = True
    is_predicate: bool = False
    type_params: tuple[str, ...] = ()
    params: tuple[Param, ...] = ()
    ret_type: Optional[Type] = None
    specs: tuple[FSpec, ...] = ()
    body: Optional[Expr] = None
    attrs: tuple[Attr, ...] = ()


@dataclass
class MethodDecl(Decl):
    """`"method" Id [TypeParams] "(" Params ")" ["returns" "(" Params ")"]
    MSpec* (Block | )`. `body is None` means bodyless
    (`bodyless-method`, refused). This is the node `lift_parse.py`'s
    `gradable_methods` selects from and every later stage operates on."""
    type_params: tuple[str, ...] = ()
    params: tuple[Param, ...] = ()
    returns: tuple[Param, ...] = ()
    specs: tuple[MSpec, ...] = ()
    body: Optional[tuple[Stmt, ...]] = None
    attrs: tuple[Attr, ...] = ()


@dataclass
class LemmaDecl(Decl):
    """`("lemma" | "least lemma" | "greatest lemma" | "twostate lemma")
    ...`, brace-matched and its body dropped: a lemma is a hint
    (LIFTER-DESIGN.md section 3), never elaborated, never lifted. `text`
    is the declaration's raw rprint text, kept only so a `lemma-call`
    refusal or a `lemma-call-dropped` log entry can quote it."""
    keyword: str = "lemma"
    text: str = ""


@dataclass
class SkippedDecl(Decl):
    """One of `datatype`, `codatatype`, `class`, `trait`, `type`,
    `newtype`, `const`, `iterator`, `module`, `import`, `export`, `least
    predicate`, `greatest predicate`, `twostate function`, `twostate
    predicate`. `gap_name` is the census gap name this keyword maps to
    (section 5's vocabulary); the declaration is never lifted, and no
    method inside it (a `class`'s methods, say) is visited."""
    keyword: str = ""
    gap_name: str = ""


# ---------------------------------------------------------------------------
# Module (the parsed rprint file) and its call graph.
# ---------------------------------------------------------------------------

@dataclass
class CallGraphSCC:
    """One `"* SCC at height" Int ":" ("*" Id)+` line of the rprint
    preamble's `/* CALL GRAPH for module _module: ... */` comment."""
    height: int
    names: tuple[str, ...]


@dataclass
class Module:
    """The parsed rprint file: every top-level declaration in source
    order, plus the call graph the preamble records (used to compute "the
    call-graph closure" `lift_rewrite.py` needs to know which spec_funs
    and helper functions a gradable method transitively calls)."""
    decls: tuple[Decl, ...]
    call_graph: tuple[CallGraphSCC, ...] = ()
    source_path: Optional[str] = None


# ---------------------------------------------------------------------------
# Refusal.
# ---------------------------------------------------------------------------

@dataclass
class Refusal:
    """Why a file or method did not lift. `reason` is a string from
    section 5's vocabulary (or `LIFTER-DECISIONS.md`'s additions:
    `array-mutation`, `lift-check-failed`, `lift-diff-failed`,
    `check-wf-failed`, ...) -- never invented ad hoc where the census
    already names the construct. `token` is the offending token's source
    text (the identifier, keyword, or operator that triggered the
    refusal); `line` is its rprint line. `stage` says which module raised
    it, one of "resolve", "parse", "classify", "rewrite", "check" -- the
    stage that MAY decide a given reason is fixed by LIFTER-DESIGN.md
    section 2's table and is never split across two stages for the same
    reason."""
    reason: str
    token: str
    line: int
    stage: str


# ---------------------------------------------------------------------------
# LiftRecord: the provenance sidecar (section 8 and 18.2).
# ---------------------------------------------------------------------------

@dataclass
class Rename:
    """One entry of the rename map: a source identifier that could not
    survive into t verbatim (a t keyword, a name colliding after
    sanitisation, a non-ASCII letter under `name-unsanitisable`'s ASCII
    rule) and the name it became."""
    t_name: str
    reason: str


@dataclass
class Rewrite:
    """One entry of the rewrite log: `rule` is a name from
    LIFTER-DESIGN.md section 4 / section 18.2's vocabulary
    (`split-conjuncts`, `in-desugared`, `nat-return-ensures`,
    `array-readonly-as-seq`, ...); `line` is the rprint line of the source
    construct the rule fired on."""
    rule: str
    line: int


@dataclass
class ClauseAdded:
    """One entry of the added-clause log: a clause with no source
    counterpart that the lift introduced (`nat-return-ensures`'s
    `ensures r >= 0`, `nat-invariant-added`'s appended `v >= 0`,
    `nat-param-guard`, ...). `text` is the clause as t surface syntax
    (SYNTAX.md `written:` notation), for a human row to read."""
    rule: str
    text: str


@dataclass
class ClauseDropped:
    """One entry of the dropped-clause log (decision 8): `rule` is
    `assert-dropped`, `lemma-call-dropped`, `function-ensures-dropped`,
    `unused-function-dropped`, or `main-dropped`; `count` is how many
    instances of that rule fired for this method (`assert-dropped` is
    usually > 1; the others are typically 0 or 1 per method but are
    counted, not just flagged, so a file with three unused helper
    functions reports 3)."""
    rule: str
    count: int


@dataclass
class LiftRecord:
    """The `<task>.lift.json` sidecar (LIFTER-DESIGN.md section 8): every
    field the disagreement table (section 8) and the rewrite-vocabulary
    cross-reference (section 18.2) read. One `LiftRecord` per lifted
    method; a file with several gradable methods (decision 9) has one per
    method, never one per file.

    `decreases_origin` is keyed by a stable per-loop/per-spec_fun label
    (e.g. "loop@<line>" or the spec_fun's name) and valued one of
    "stated" (the source wrote a decreases), "rprint-inferred" (rprint
    printed one dafny inferred), "projected" or "guess:sum" (decision 11's
    tuple-measure reduction). `twin_rung` is one of SYNTAX.md's eight
    operator names (or a "<op>#<k>" / "<op>+nonrefuting" tag per
    `harness.twin_for`'s `_tag`) or `None` when the twin was refused
    (`twin_witness is None` and the refusal reason lives in the row this
    record is attached to, not in the record itself: a refused twin is
    not a `lift-check-failed`/`lift-diff-failed` LIFT refusal, section 5's
    closing paragraph). `checker_verdicts` is keyed by lemma name (`L_req`,
    `L_ens`, `L_fun_<name>`, `L_inv_<k>`, the loop-k decreases lemma) and
    valued a `verifiers.Outcome` name. `differential_verdict` is one of
    "agrees on N points", "bad=M" with the first differing input, or
    `None` when the differential arm did not run (`arm-unavailable`,
    section 18.5). `dafny_exit_codes` is keyed by invocation name
    ("resolve-rprint", "resolve-print", "verify-source", "verify-checker",
    "run-differential") and valued the process exit code (section 18.1's
    three-invocation discipline plus the checker/differential runs of
    sections 9-10). `warnings` collects every warning line dafny printed
    on any of those invocations, verbatim; section 18.1 says they are
    recorded and ignored, never promoted to a refusal. `lowered_task_verdict`
    is the checker file's own lowered-`<Method>` verdict (decision 8's
    dropped hints show up here as UNPROVED, decision 17's own column: never
    folded into `checker_verdicts` or a `lift-check-failed` refusal)."""
    source_path: str
    method: str
    rprint_sha256: str
    rename_map: dict[str, Rename] = field(default_factory=dict)
    rewrites: list[Rewrite] = field(default_factory=list)
    clauses_added: list[ClauseAdded] = field(default_factory=list)
    clauses_dropped: list[ClauseDropped] = field(default_factory=list)
    decreases_origin: dict[str, str] = field(default_factory=dict)
    twin_rung: Optional[str] = None
    twin_witness: Optional[dict] = None
    checker_verdicts: dict[str, str] = field(default_factory=dict)
    differential_verdict: Optional[str] = None
    dafny_exit_codes: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    lowered_task_verdict: Optional[str] = None
