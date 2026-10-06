#!/usr/bin/env python3
"""check_wf.py: the t well-formedness checker, as a module of its own.

Moved out of fuzz_lower.py on 2026-09-11 (ROADMAP 14.3, "The checker as a
module"): `_valid_type`, `_ty`, `check_wf`, and every helper, constant and
table only they used, moved here verbatim (not copied), including
`NAME_RE`, the operator-classification sets (`V0_OPS`, `V1_OPS`,
`STRLIB_OPS`, `TERNARY`, `VARIADIC`, `UNARY`, `NARY`, `BOOLR`, `INTR`,
`BASE_TYPES`), `_self_calls`, `_check_returns` and `_check_stmts`.
fuzz_lower.py now imports this module and keeps `fuzz_lower.check_wf` (and
`fuzz_lower.NAME_RE`, since grade.py reads that name directly) working as
aliases, so grade.py, surface.py, loop_generate.py and spec_experiment.py
are unchanged. This module imports nothing from fuzz_lower (checked by
test_check_wf.py's `test_no_cycle`), so surface.py and the command can
import it directly without pulling in the fuzzer.

Every error `check_wf` and its helpers append now carries the SPEC.md rule
it enforces, appended in the fixed form `msg [SPEC: <rule>]`; the existing
message text is kept unchanged as the prefix, so any test matching on a
message's prefix still passes. The full catalogue is the RULES table
directly below, one entry per rule key used by `_e()` calls in this file.

Measured 2026-09-11, before and after this move, from t/ with kernels not
involved (numbers in fuzz_lower.py's and this file's own dated notes are
the ones actually printed by these commands, not restated here to avoid a
second, possibly stale, copy):

  python3 -c 'import fuzz_lower as f; c=f.build_corpus(400,1); \
    print(len(c), sum(1 for t in c if f.check_wf(t)))'
  python3 truth_fuzz.py --tasks-only --out <scratch> --seed 1
  python3 surface.py --check --n 20 --seeds 1,2

See fuzz_lower.py's own docstring note (same date) for the paired
before/after numbers this move was required to reproduce.

ROADMAP 14.2 ("Errors with a position"), well-formedness half, ported
2026-09-11 onto this module (the RULES table, `_e`, and every check_wf
helper above stay as wave A left them): `check_wf` gains two optional
parameters, `positions` (an `id(AST node) -> (line, col)` map, the shape
`surface.parse(text, positions=...)` fills) and `file`. With `positions`
omitted (every existing call site: fuzz_lower.py, grade.py,
test_check_wf.py), `check_wf` returns exactly what it always did, a
list[str]. With `positions` given, it returns a list[WfError] instead --
one error object per problem found, each carrying `.message`, `.rule`,
`.file`, `.line`, `.col`, and a `str()` of `"file:line:col: message
[SPEC: rule]"`. The position recorded is always that of the innermost
AST node `_e` was called while examining: `_ty` attributes an error to
the expression node `e` it is currently typing (not the outer
expression that called into it), `_check_stmts` to the statement `s`,
and `check_wf`'s own top-level checks to `task`, a `param`/`return`
dict, or a `spec_fun` dict as appropriate -- the one place that
decision is made is `_e` itself, which every error in this file funnels
through. `surface.check_file(path)` is the new entry point that wires
this up end to end: parse with positions, then check_wf with them.
"""

from __future__ import annotations

import re

# ===========================================================================
# 0. The SPEC.md rule catalogue.
#
# One entry per rule key used by _e() below. Each value is a short, fixed
# quote or paraphrase of the SPEC.md section or stated rule the errors
# tagged with that key enforce. Keep this table alphabetical by key so a
# new rule is easy to place and easy to find.
# ===========================================================================

RULES: dict[str, str] = {
    "arith-int": "+ - * neg take all ints or all reals, / both, % ints only; real(x) converts (Division and modulo; Exact rationals)",
    "assign-target": "assign targets a return or a local in scope (Gate 2)",
    "assign-type": "assign's expression type must match the target's declared type",
    "at-types": "at wants (a seq of any element type, int) and gives the element (Gate 1; Compositional types)",
    "bool-cond": "a condition or loop guard must be bool",
    "bool-lit-v1": "the bool literal is a v1 construct (Gate 1)",
    "bool-op": "and/or/not/implies are bool-only",
    "call-argtype": "a call's argument types must match the callee's params (Gate 3)",
    "call-arity": "a call's arity must match the callee's params (Gate 3)",
    "call-unknown": "call names a declared spec_fun or the task's own name (Gate 3)",
    "cmp-int": "< <= > >= compare two ints or two reals (Gate 1; Exact rationals)",
    "comp-seq": "a comprehension ranges over a seq or an int range [lo, hi) (Comprehensions)",
    "comp-cond": "a comprehension's condition is bool (Comprehensions)",
    "rat-literal": "a real literal is n/d in lowest terms with a finite decimal expansion (Exact rationals)",
    "real-conv": "real(x) wants an int; floor(x) and ceil(x) want a real (Exact rationals)",
    "decreases-selfcall": "a task decreases requires a self-recursive body, and vice versa (Gate 3)",
    "ensures-bool": "each ensures clause must be bool",
    "ensures-nonempty": "ensures must be non-empty (v0 and v1)",
    "eq-types": "== and != apply to two values of one type, structural at every depth (Gate 1; Compositional types)",
    "fill-types": "fill wants (int, v) and gives the seq of v's type (Sequences as values; Compositional types)",
    "ite-branches": "ite branches must have the same type",
    "lemma-body": "a lemma body holds only `if`, `assert` and lemma-call "
                  "statements, and a lemma has no return (Lemmas; Dafny "
                  "reference 6.3.3)",
    "lemma-call": "a lemma call is a statement naming a declared lemma, "
                  "with matching arity and argument types; a lemma is never "
                  "called as an expression and its arguments call no method "
                  "(Lemmas)",
    "lemma-decreases": "a lemma decreases requires a self-calling lemma "
                       "body, and vice versa (Lemmas)",
    "lemma-name": "lemma names are distinct from each other, the task, the "
                  "spec_funs and the methods, and match [A-Za-z][A-Za-z0-9_]* "
                  "(Lemmas)",
    "lemma-order": "a lemma body calls only EARLIER lemmas, or itself with "
                   "a decreases; its contract calls no lemma or method (Lemmas)",
    "local-shadow": "a local must not shadow a name already in scope (Gate 1 scope rule)",
    "local-v0": "locals are a v1 construct (Gate 2)",
    "datatype-name": "a datatype name matches [A-Za-z][A-Za-z0-9_]* (Datatypes)",
    "datatype-dup": "a datatype name is declared at most once per task (Datatypes)",
    "datatype-empty": "a datatype declares at least one constructor (Datatypes)",
    "datatype-unknown": "a datatype type or ctor names a datatype this task "
                        "declares (Datatypes)",
    "ctor-name": "a constructor name matches [A-Za-z][A-Za-z0-9_]* (Datatypes)",
    "ctor-dup": "a constructor name is declared at most once per datatype (Datatypes)",
    "ctor-fields-not-v1": "this v1 landing states enumerations only: a "
                          "constructor carries no fields (Datatypes)",
    "ctor-unknown": "a ctor names one of its datatype's own declared "
                    "constructors (Datatypes)",
    "ctor-arity": "a ctor's argument count matches its constructor's declared "
                  "field count (Datatypes)",
    "ctor-argtype": "a ctor's arguments match their constructor's declared "
                    "field types (Datatypes)",
    "match-scrutinee": "match scrutinizes a value of one of this task's own "
                       "declared datatypes (Datatypes)",
    "match-coverage": "match covers every constructor of the scrutinee's "
                      "datatype exactly once (Datatypes; Dafny reference 5.14)",
    "match-arity": "a match arm binds exactly its constructor's declared "
                   "fields (Datatypes)",
    "match-branches": "every match arm has the same type (Datatypes)",
    "method-call-position": "a method call is the whole right-hand side of an "
                            "assign or a var init, with call-free arguments; "
                            "never in a spec, a guard, an invariant, a "
                            "decreases, a return or another expression (Methods; "
                            "Dafny reference 8.5.2)",
    "method-decreases": "a method decreases requires a self-recursive method "
                        "body, and vice versa (Methods)",
    "method-name": "method names are distinct from each other, the task, and "
                   "the spec_funs, and match [A-Za-z][A-Za-z0-9_]* (Methods)",
    "method-order": "a method body calls only EARLIER methods, or itself with "
                    "a decreases; the task body calls any method (Methods)",
    "name": "the task name matches [A-Za-z][A-Za-z0-9_]*",
    "no-self-in-ensures": "ensures never references the task's own name (Gate 3)",
    "one-return": "exactly one return value (SPEC.md v0 and v1)",
    "op-arity": "each operator has the fixed arity its Expr form declares",
    "op-unknown": "an operator must be in the declared version's operator set",
    "proj-nonpair": "fst/snd want a pair or tuple operand, proj wants a tuple (Pairs; Compositional types)",
    "proj-index": "a projection index is an int literal within the tuple; .0 and .1 are fst and snd (Compositional types)",
    "tuple-arity": "a tuple display has three or more components; two are a pair (Compositional types)",
    "quant-bounds": "a quantifier's lo and hi must be int (Gate 1)",
    "quant-body": "a quantifier's body must be bool (Gate 1)",
    "quant-shadow": "a bound variable must not collide with a name already "
                    "in scope (Gate 1 scope rule)",
    "requires-bool": "each requires clause must be bool",
    "return-name": "return must name the task's return variable (Early exit)",
    "return-unreachable": "no statement follows a return in its block (Early exit)",
    "exit-outside-loop": "break and continue belong to a loop body (Early exits)",
    "exit-unreachable": "no statement follows a break or continue in its block (Early exits)",
    "loop-exit": "a while true loop holds a break of its own or a return, or it never ends (Early exits)",
    "return-v0": "return is a v1 construct (Early exit)",
    "seq-lit-mixed": "a seq literal's elements are all of one type (Nested sequences; Compositional types)",
    # 2026-10-05: both names were used by _ty since sets landed (2026-09-27) and never defined, so the first set
    # type error raised KeyError inside the checker and the answer's reason read "check_wf raised KeyError:
    # 'set-types'" (3 of the published model's 100 greedy dev answers, each `x in s` with s a seq)
    "set-lit-types": "a set display's elements are all of one type (Finite sets; Compositional types)",
    "map-lit-types": "a map display's keys are of one type and its values of one type (Maps)",
    "lambda-position": "a lambda is only the function argument of fold, sort_by, max_by or min_by (Higher-order calls)",
    "hof-types": "fold wants ((A, T) => A, A, seq<T>); sort_by, max_by and min_by want (seq<T>, T => int or real) "
                 "(Higher-order calls)",
    "map-types": "m[k] and k in m take a map and a key of its key type, m[k := v] a value of its value type, "
                 "keys and remove a map (Maps)",
    "lib-types": "min/max take two ints or two reals, abs an int or a real, sum a seq of ints or of reals, gcd/pow/isqrt "
                 "ints, rev a seq, sort a seq of ints or of reals, `in` an element of the seq's own type (The library; Sorting)",
    "set-types": "in wants (T, set<T>) or (T, seq<T>), card wants a set, union/inter/setminus want two sets of one type; "
                 "membership in a seq is written with a quantifier (Finite sets; Compositional types)",
    "slice-types": "slice wants (a seq of any element type, int, int) (Sequences: "
                   "literals, concatenation, slices; Compositional types)",
    "len-nonseq": "len is defined on a seq (Gate 1)",
    "loop-decreases": "a loop requires a decreases measure (Gate 2)",
    "loop-invariant-bool": "each loop invariant must be bool (Gate 2)",
    "spec-fun-body-type": "a spec_fun's body type must match its declared result (Gate 3)",
    "spec-fun-result": "a spec_fun's result is any t type (Gate 3; Compositional types)",
    "spec-fun-decreases-int": "a spec_fun's decreases must be int (Gate 3)",
    "strlib-arity": "each string-library member has a fixed arity (The string library)",
    "strlib-types": "each string-library member's argument types must "
                    "match its signature (The string library)",
    "unbound": "a name must be bound before use (v0 and Gate 1 scope rule)",
    "unknown-stmt": "a Stmt is one of assign/var/if/while/return/break/continue, or a "
                    "lemma call (v0 Stmt; Gate 2; Lemmas)",
    "update-types": "update wants (seq<T>, int, T) for the seq's own element type T "
                    "(Sequences as values; Compositional types)",
    "v0-frozen": "t:0 is frozen; spec_funs/methods/decreases/gate are v1 fields",
    "v0-int-only": "v0 has int only",
    "v1-expr-v0": "ite/forall/exists/call are v1 expression forms (v1: the three gates)",
    "valid-type": "a declared type is int, bool, seq, seq<T>, set, set<T>, a pair or tuple of types, or a "
                  "declared datatype; seq<int> and set<int> are spelled seq and set (Compositional types)",
    "while-v0": "while is a v1 construct (Gate 2)",
}




class WfError:
    """One well-formedness error, position-carrying. `.message` is the same
    text `check_wf` always produced (no position); `.rule` is a RULES key.
    `.file`/`.line`/`.col` are the offending AST node's position when
    `check_wf` was given a `positions` map that has an entry for that node,
    None otherwise (a node `surface.parse` did not mark, or no `positions`
    map at all). `str(err)` reads `"file:line:col: message [SPEC: rule]"`
    with a known position, `"message [SPEC: rule]"` without one -- the
    no-position form is byte-identical to what `check_wf` without
    `positions` still returns as a plain string, so a caller printing
    either kind of error, or SurfaceError from surface.py, reads the same
    way."""

    __slots__ = ("message", "rule", "file", "line", "col")

    def __init__(self, message: str, rule: str, file=None, line=None, col=None):
        self.message = message
        self.rule = rule
        self.file = file
        self.line = line
        self.col = col

    def __str__(self) -> str:
        tag = f" [SPEC: {RULES[self.rule]}]"
        if self.line is None:
            return self.message + tag
        where = f"{self.file or '<string>'}:{self.line}:{self.col if self.col is not None else '?'}"
        return f"{where}: {self.message}{tag}"

    __repr__ = __str__

    def __eq__(self, other):
        if isinstance(other, WfError):
            return (self.message, self.rule, self.file, self.line, self.col) == (
                other.message, other.rule, other.file, other.line, other.col)
        return NotImplemented

    def __hash__(self):
        return hash((self.message, self.rule, self.file, self.line, self.col))


class _Errs(list):
    """The list `check_wf` builds its errors into, carrying the `positions`
    map and `file` name it was called with so `_e()` can look up a node's
    position without every one of check_wf's helper functions growing two
    extra parameters just to pass them down to `_e`. When `positions` is
    None, `_e` appends plain strings (today's behaviour, unchanged); when
    it is a dict, `_e` appends WfError objects."""

    __slots__ = ("positions", "file")

    def __init__(self, positions=None, file="<string>"):
        super().__init__()
        self.positions = positions
        self.file = file


def _e(errs: "_Errs", node, msg: str, rule: str) -> None:
    """Record one well-formedness error: `msg`/`rule`, at `node`'s position
    when `errs.positions` is not None and holds an entry for it. `node` is
    whatever AST dict check_wf or one of its helpers was looking at when it
    found the problem: the task itself, a param/return/spec_fun dict, a
    statement dict, or an expression dict -- always a dict `surface.parse`'s
    `positions=` map could have recorded a (line, col) for.

    With `errs.positions is None` (the default, `check_wf(task)` with no
    `positions` argument), this appends the exact same string the old
    module-level `_e(errs, msg, rule)` always appended -- `node` is looked
    at only inside the `errs.positions is not None` branch, so it is dead
    weight in that mode and callers need not have marked their tasks."""
    if errs.positions is None:
        errs.append(f"{msg} [SPEC: {RULES[rule]}]")
        return
    pos = errs.positions.get(id(node))
    line, col = pos if pos is not None else (None, None)
    errs.append(WfError(msg, rule, errs.file, line, col))


NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
V0_OPS = {"+", "-", "*", "neg", "==", "!=", "<", "<=", ">", ">=",
          "and", "or", "not", "implies"}
# div and mod are v1 (SPEC.md "Division and modulo", 2026-09-08): Euclidean,
# undefined at y == 0, so v1's definedness rules apply to them as to at.
# pair, fst, snd are v1 (SPEC.md "Pairs", 2026-09-10): a pair is a value, and
# `fst`/`snd` are its only projections.
# The string library is v1 (SPEC.md "The string library", 2026-09-11): 17
# polymorphic seq members, split at two arities (one op).
STRLIB2_OPS = {"index", "rfind", "zfill", "center", "ljust", "rjust", "capitalize", "swapcase", "title",
               "isspace", "isalnum", "splitlines", "partition"}   # SPEC.md "The string library (v2)" (2026-10-06)
STRLIB_OPS = STRLIB2_OPS | {"split", "join", "tostr", "count", "find", "strip", "lstrip",
             "rstrip", "replace", "lower", "upper", "isdigit", "isalpha",
             "isupper", "islower", "startswith", "endswith"}
SET_OPS = {"set", "in", "card", "union", "inter", "diff"}   # SPEC.md "Finite sets" (2026-09-27)
MAP_OPS = {"mapdisp", "keys", "remove"}   # SPEC.md "Maps (v1)" (2026-10-06); at/update/in/len take a map by type
LIB_OPS = frozenset({"min", "max", "abs", "sum", "gcd", "pow", "isqrt", "rev",   # SPEC.md "The library (v1)" (2026-10-06)
                     "sort",                                                        # SPEC.md "Sorting (v1)" (2026-10-06)
                     "any", "all", "toset",                                         # SPEC.md "Reductions (v1)" (2026-10-06)
                     "isint", "toint",                                              # SPEC.md "The string library (v2)" (2026-10-06)
                     "fold", "sort_by", "max_by", "min_by"})                        # SPEC.md "Higher-order calls (v1)"
HOF_OPS = frozenset({"fold", "sort_by", "max_by", "min_by"})
V1_OPS = (V0_OPS | {"len", "at", "div", "mod", "update", "fill", "seq", "slice"}
         | {"pair", "fst", "snd", "tuple", "proj"} | {"toreal", "floor", "ceil"} | STRLIB_OPS | SET_OPS | LIB_OPS
         | MAP_OPS)
TERNARY = {"update", "slice", "replace"}
VARIADIC = {"seq", "set", "tuple", "mapdisp"}   # the displays: seq, set and map at any arity, zero included; tuple at three or more
UNARY = {"neg", "not", "len", "fst", "snd", "tostr",
         "lower", "upper", "isdigit", "isalpha", "isupper",
         "islower", "card", "toreal", "floor", "ceil", "abs", "sum", "isqrt", "rev", "sort", "keys",
         "any", "all", "toset",
         "capitalize", "swapcase", "title", "isspace", "isalnum", "splitlines", "isint", "toint"}
NARY = {"and", "or"}
BOOLR = {"==", "!=", "<", "<=", ">", ">=", "and", "or", "not", "implies"}
INTR = {"+", "-", "*", "neg", "len"}
BASE_TYPES = ("int", "bool", "seq", "real")     # the scalars and the string; "real": SPEC.md "Exact rationals (v1)" (2026-10-06)
# SPEC.md "Seq-valued spec_funs (v1)" (2026-09-27) listed three result types; since SPEC.md "Compositional types
# (v1)" (2026-10-06) a spec_fun takes and returns any type, so `_valid_type` decides and the list is gone.


def _gcd(a: int, b: int) -> int:
    while b:
        a, b = b, a % b
    return a


def _finite_decimal(d: int) -> bool:
    """Whether 1/d has a finite decimal expansion: d is 2^a 5^b."""
    for q in (2, 5):
        while d % q == 0:
            d //= q
    return d == 1


def _valid_type(t, dtypes=frozenset()) -> bool:
    """A well-formed t TYPE (SPEC.md "Compositional types (v1)", 2026-10-06): "int", "bool", "seq" (the canonical
    spelling of a seq of ints), `{"seq": T}` for any other element type T (so `{"seq": "seq"}` is still seq<seq>,
    as it was since 2026-09-10), `{"pair": [T1, T2]}` with any two types (a pair of pairs, a pair holding a set),
    `{"tuple": [T1, ..., Tn]}` with n >= 3, "set" (the canonical spelling of a set of ints), `{"set": T}` for any
    other element type, or `{"datatype": D}` naming one of THIS task's own declarations (`dtypes`: name -> decl,
    as `check_wf` built it). The non-canonical spellings `{"seq": "int"}`, `{"set": "int"}` and a two-component
    "tuple" are refused, so that every type has exactly one normal form (`parse(print(t)) == t`); so is anything
    else (an unknown string, a malformed dict), here rather than as a KeyError three checks later."""
    if t in BASE_TYPES or t == "set":
        return True
    if not (isinstance(t, dict) and len(t) == 1):
        return False
    (kind, inner), = t.items()
    if kind in ("seq", "set"):
        return inner != "int" and _valid_type(inner, dtypes)
    if kind == "map":
        # SPEC.md "Maps (v1)" (2026-10-06): map<K, V>, both written
        return isinstance(inner, list) and len(inner) == 2 and all(_valid_type(c, dtypes) for c in inner)
    if kind == "pair":
        return isinstance(inner, list) and len(inner) == 2 and all(_valid_type(c, dtypes) for c in inner)
    if kind == "tuple":
        return isinstance(inner, list) and len(inner) >= 3 and all(_valid_type(c, dtypes) for c in inner)
    return kind == "datatype" and isinstance(inner, str) and inner in dtypes


def _is_seq(t) -> bool:
    """A seq type of any element type ("seq" is the seq of ints)."""
    return t == "seq" or (isinstance(t, dict) and set(t) == {"seq"})


def _elem(t):
    """The element type of a seq type."""
    return "int" if t == "seq" else t["seq"]


def _seq_of(t):
    """The seq type over element type t, in its canonical spelling."""
    return "seq" if t == "int" else {"seq": t}


def _is_set(t) -> bool:
    return t == "set" or (isinstance(t, dict) and set(t) == {"set"})


def _set_elem(t):
    return "int" if t == "set" else t["set"]


def _set_of(t):
    return "set" if t == "int" else {"set": t}


def _is_map(t) -> bool:
    """A map type (SPEC.md "Maps (v1)", 2026-10-06)."""
    return isinstance(t, dict) and set(t) == {"map"}


def _components(t):
    """The component types of a pair or tuple type, or None for any other type."""
    if isinstance(t, dict) and (set(t) == {"pair"} or set(t) == {"tuple"}):
        return list(t.values())[0]
    return None


def _empty_display(a, t, want) -> bool:
    """Whether `a`, typed `t` with no hint, is the empty seq or set display standing for the seq or set type
    `want` (SPEC.md "Compositional types": `[]` and `{}` take the expected type; where no declared type reaches
    them, their default is the seq or set of ints, which is not a type error against another seq or set)."""
    if not isinstance(a, dict) or a.get("args"):
        return False
    return ((t == "seq" and a.get("op") == "seq" and _is_seq(want))
            or (t == "set" and a.get("op") == "set" and _is_set(want))
            or (_is_map(t) and a.get("op") == "mapdisp" and _is_map(want)))


def _ty_hof(e, op, args, env, funs, dtypes, ver, errs, bound):
    """SPEC.md "Higher-order calls (v1)" (2026-10-06): fold(f, init, s), sort_by(s, key), max_by(s, key),
    min_by(s, key), the lambda typed from its position (its parameters are bound names, as a quantifier's)."""
    if op == "fold":
        if len(args) != 3:
            _e(errs, e, "fold takes (f, init, s)", "op-arity")
            return None
        lam, init, seq = args
        nvars = 2
    else:
        if len(args) != 2:
            _e(errs, e, f"{op} takes (s, key)", "op-arity")
            return None
        seq, lam = args
        init = None
        nvars = 1
    ts = _ty(seq, env, funs, dtypes, ver, errs, bound)
    if not _is_seq(ts):
        _e(errs, e, f"{op} wants a seq, found {ts!r}", "hof-types")
        return None
    elem = _elem(ts)
    if not (isinstance(lam, dict) and set(lam) == {"lam"} and len(lam["lam"].get("vars", [])) == nvars):
        _e(errs, e, f"{op} wants a lambda of {nvars} parameter(s)", "hof-types")
        return None
    names = lam["lam"]["vars"]
    for v in names:
        if v in env or v in bound:
            _e(errs, e, f"lambda parameter {v} shadows a name in scope", "quant-shadow")
    if len(set(names)) != len(names):
        _e(errs, e, "a lambda's parameters need distinct names", "quant-shadow")
    sub = dict(env)
    if op == "fold":
        acc_t = _ty(init, env, funs, dtypes, ver, errs, bound)
        if acc_t is None:
            return None
        sub[names[0]], sub[names[1]] = acc_t, elem
        bt = _ty(lam["lam"]["body"], sub, funs, dtypes, ver, errs, bound | set(names), acc_t)
        if bt != acc_t and not _empty_display(lam["lam"]["body"], bt, acc_t):
            _e(errs, e, f"fold's lambda returns {bt!r}, its accumulator is {acc_t!r}", "hof-types")
        return acc_t
    sub[names[0]] = elem
    bt = _ty(lam["lam"]["body"], sub, funs, dtypes, ver, errs, bound | set(names))
    if bt not in ("int", "real"):
        _e(errs, e, f"{op}'s key is an int or a real, found {bt!r}", "hof-types")
    return ts if op == "sort_by" else elem


def _ty(e, env, funs, dtypes, ver, errs, bound, expect=None):
    """Type of e in env, or None; appends to errs. env maps name -> type.

    `expect`, added for SPEC.md "Nested sequences" (2026-09-10): the
    empty seq literal `[]` has no element to type from, so with zero
    elements it is ambiguous between a plain `seq` and a `{"seq": "seq"}`
    with no rows -- "SPEC.md: `[]` the empty nested seq where the
    declared type says so". Every OTHER position an empty literal can
    appear in already resolves correctly with no hint at all: a row
    argument to `update`/`fill`/an outer literal wants a plain `seq`
    regardless, which is exactly `[]`'s unhinted default below. Only a
    var init, an assign, a return, an ite branch and a call argument
    carry a declared type to check against, so only those five thread
    `expect` down; everywhere else it stays None and behaviour is
    unchanged from before this construct."""
    if "int" in e:
        return "int"
    if "rat" in e:
        # SPEC.md "Exact rationals (v1)" (2026-10-06): n / d in lowest terms, d >= 1, d of the form 2^a 5^b (a
        # finite decimal, the only literal the notation writes), else refused as non-canonical.
        r = e["rat"]
        ok = (isinstance(r, list) and len(r) == 2 and all(isinstance(x, int) and not isinstance(x, bool) for x in r)
              and r[1] >= 1 and _gcd(abs(r[0]), r[1]) == 1 and _finite_decimal(r[1]))
        if not ok:
            _e(errs, e, f"a real literal is n/d in lowest terms with a finite decimal expansion, not {r!r}", "rat-literal")
        return "real"
    if "bool" in e:
        if ver == 0:
            _e(errs, e, "bool literal in a v0 task", "bool-lit-v1")
        return "bool"
    if "var" in e:
        t = env.get(e["var"])
        if t is None:
            _e(errs, e, f"unbound var {e['var']}", "unbound")
        return t
    if ("ite" in e or "forall" in e or "exists" in e or "call" in e
            or "ctor" in e or "match" in e):
        if ver == 0:
            _e(errs, e, "v1 expression form in a v0 task", "v1-expr-v0")
    if "ctor" in e:
        # SPEC.md "Datatypes (v1)" (2026-09-27): {"ctor": {"dtype": D,
        # "name": C, "args": [...]}}, a value of datatype D built with
        # constructor C. Copied from Dafny's own datatype values (reference
        # manual 5.14): a constructor is qualified by its datatype's name,
        # exactly as t's surface notation writes `D.C`.
        c = e["ctor"]
        d = dtypes.get(c.get("dtype"))
        if d is None:
            _e(errs, e, f"ctor of unknown datatype {c.get('dtype')!r}",
               "datatype-unknown")
            return None
        cdecl = next((ct for ct in d.get("ctors", [])
                      if isinstance(ct, dict) and ct.get("name") == c.get("name")),
                     None)
        if cdecl is None:
            _e(errs, e, f"{c.get('dtype')} has no constructor {c.get('name')!r}",
               "ctor-unknown")
            return {"datatype": c.get("dtype")}
        fields = cdecl.get("fields") or []
        cargs = c.get("args", [])
        if len(cargs) != len(fields):
            _e(errs, e, f"{c['dtype']}.{c['name']} takes {len(fields)} "
                        f"argument(s), given {len(cargs)}", "ctor-arity")
        for fdecl, a in zip(fields, cargs):
            if _ty(a, env, funs, dtypes, ver, errs, bound, fdecl.get("type")) != fdecl.get("type"):
                _e(errs, e, f"{c['dtype']}.{c['name']}: field type mismatch",
                   "ctor-argtype")
        return {"datatype": c["dtype"]}
    if "match" in e:
        # SPEC.md "Datatypes (v1)": {"match": {"scrutinee": Expr, "arms":
        # [{"ctor": C, "binders": [...], "body": Expr}, ...]}}, total --
        # every arm's body must type, and every constructor of the
        # scrutinee's datatype must be covered EXACTLY once (Dafny
        # reference manual 5.14: a `match` is exhaustive over
        # constructors); the scrutinee's own type names which datatype,
        # so no separate "dtype" field is needed here the way `ctor`
        # needs one to disambiguate construction.
        m = e["match"]
        st = _ty(m["scrutinee"], env, funs, dtypes, ver, errs, bound)
        if not (isinstance(st, dict) and set(st) == {"datatype"}
                and st["datatype"] in dtypes):
            _e(errs, e, f"match scrutinee is not a datatype value: {st!r}",
               "match-scrutinee")
            return None
        d = dtypes[st["datatype"]]
        declared = [ct["name"] for ct in d.get("ctors", []) if isinstance(ct, dict)
                    and isinstance(ct.get("name"), str)]
        arms = m.get("arms", [])
        seen = [a.get("ctor") for a in arms]
        if sorted(seen) != sorted(declared) or len(seen) != len(set(seen)):
            _e(errs, e, f"match over {st['datatype']} must cover each "
                        f"constructor exactly once, found {seen!r}",
               "match-coverage")
        result = None
        mismatch = False
        for a in arms:
            cdecl = next((ct for ct in d.get("ctors", [])
                          if isinstance(ct, dict) and ct.get("name") == a.get("ctor")),
                         None)
            fields = (cdecl.get("fields") or []) if cdecl is not None else []
            binders = a.get("binders", [])
            if len(binders) != len(fields):
                _e(errs, e, f"match arm {a.get('ctor')}: {len(fields)} "
                            f"binder(s) expected, found {len(binders)}",
                   "match-arity")
            sub = dict(env)
            subbound = set(bound)
            for bname, fdecl in zip(binders, fields):
                if bname in env or bname in subbound:
                    _e(errs, e, f"match binder {bname} shadows a name in scope",
                       "quant-shadow")
                sub[bname] = fdecl.get("type")
                subbound.add(bname)
            at = _ty(a.get("body"), sub, funs, dtypes, ver, errs, subbound)
            if result is None:
                result = at
            elif at != result:
                mismatch = True
        if mismatch:
            _e(errs, e, "match arms have different types", "match-branches")
        return result
    if "ite" in e:
        c = e["ite"]
        if _ty(c["cond"], env, funs, dtypes, ver, errs, bound) != "bool":
            _e(errs, e, "ite condition is not bool", "bool-cond")
        a = _ty(c["then"], env, funs, dtypes, ver, errs, bound, expect)
        b = _ty(c["else"], env, funs, dtypes, ver, errs, bound, expect)
        if a != b:
            _e(errs, e, f"ite branches differ: {a} vs {b}", "ite-branches")
        return a
    if "comp" in e:
        # SPEC.md "Comprehensions (v1)" (2026-10-06): a bound variable over a seq's elements or an int range
        c = e["comp"]
        v = c["var"]
        if v in env or v in bound:
            _e(errs, e, f"bound var {v} shadows a name in scope", "quant-shadow")
        if "seq" in c:
            ts = _ty(c["seq"], env, funs, dtypes, ver, errs, bound)
            if not _is_seq(ts):
                _e(errs, e, f"a comprehension ranges over a seq or an int range, found {ts!r}", "comp-seq")
                elem_t = "int"
            else:
                elem_t = _elem(ts)
        else:
            for side in ("lo", "hi"):
                if _ty(c[side], env, funs, dtypes, ver, errs, bound) != "int":
                    _e(errs, e, f"comprehension {side} is not int", "quant-bounds")
            elem_t = "int"
        sub = dict(env)
        sub[v] = elem_t
        if _ty(c["cond"], sub, funs, dtypes, ver, errs, bound | {v}) != "bool":
            _e(errs, e, "a comprehension's condition is not bool", "comp-cond")
        body_t = _ty(c["body"], sub, funs, dtypes, ver, errs, bound | {v})
        return _seq_of(body_t) if body_t is not None else "seq"
    if "forall" in e or "exists" in e:
        q = e["forall"] if "forall" in e else e["exists"]
        v = q["var"]
        if v in env or v in bound:
            _e(errs, e, f"bound var {v} shadows a name in scope", "quant-shadow")
        for side in ("lo", "hi"):
            if _ty(q[side], env, funs, dtypes, ver, errs, bound) != "int":
                _e(errs, e, f"quantifier {side} is not int", "quant-bounds")
        sub = dict(env)
        sub[v] = "int"
        if _ty(q["body"], sub, funs, dtypes, ver, errs, bound | {v}) != "bool":
            _e(errs, e, "quantifier body is not bool", "quant-body")
        return "bool"
    if "call" in e:
        c = e["call"]
        f = funs.get(c["fun"])
        if f is None:
            _e(errs, e, f"call of unknown fun {c['fun']}", "call-unknown")
            return None
        if len(f["params"]) != len(c["args"]):
            _e(errs, e, f"arity mismatch calling {c['fun']}", "call-arity")
        for p, a in zip(f["params"], c["args"]):
            if _ty(a, env, funs, dtypes, ver, errs, bound, p["type"]) != p["type"]:
                _e(errs, e, f"argument type mismatch calling {c['fun']}", "call-argtype")
        return f["result"]
    if "lam" in e:
        _e(errs, e, "a lambda outside the function argument of fold, sort_by, max_by or min_by", "lambda-position")
        return None
    op = e["op"]
    ok = V0_OPS if ver == 0 else V1_OPS
    if op not in ok:
        _e(errs, e, f"operator {op!r} not in v{ver}", "op-unknown")
        return None
    args = e.get("args", [])
    if op in HOF_OPS:
        return _ty_hof(e, op, args, env, funs, dtypes, ver, errs, bound)
    if op in UNARY and len(args) != 1:
        _e(errs, e, f"{op} takes one argument", "op-arity")
    if op in TERNARY and len(args) != 3:
        _e(errs, e, f"{op} takes three arguments", "op-arity")
    if op == "split":
        # SPEC.md "The string library": split(s) and split(s, c), two
        # arities of one op, neither the plain-binary nor any other group.
        if len(args) not in (1, 2):
            _e(errs, e, "split takes one or two arguments", "strlib-arity")
    elif op in ("min", "max"):
        # SPEC.md "Reductions (v1)" (2026-10-06): two ints or reals, or one seq of them
        if len(args) not in (1, 2):
            _e(errs, e, f"{op} takes one or two arguments", "op-arity")
    elif op in ("strip", "lstrip", "rstrip"):
        # SPEC.md "The string library (v2)" (2026-10-06): whitespace, or a character set
        if len(args) not in (1, 2):
            _e(errs, e, f"{op} takes one or two arguments", "strlib-arity")
    elif op in ("center", "ljust", "rjust"):
        if len(args) not in (2, 3):
            _e(errs, e, f"{op} takes two or three arguments", "strlib-arity")
    elif (op not in UNARY and op not in NARY and op not in TERNARY
            and op not in VARIADIC and len(args) != 2):
        _e(errs, e, f"{op} takes two arguments", "op-arity")
    if op in NARY and len(args) < 2:
        _e(errs, e, f"{op} needs at least two arguments", "op-arity")
    # SPEC.md "Compositional types (v1)" (2026-10-06): a display's elements are typed against the element type
    # of the expected type, so `[[]]` under a declared `seq<seq<bool>>` reads its inner `[]` as a `seq<bool>`.
    expects = [None] * len(args)
    if op == "seq" and _is_seq(expect):
        expects = [_elem(expect)] * len(args)
    elif op == "set" and _is_set(expect):
        expects = [_set_elem(expect)] * len(args)
    elif op == "mapdisp" and _is_map(expect):
        expects = list(expect["map"]) * (len(args) // 2)
    elif op in ("pair", "tuple") and _components(expect) is not None and len(_components(expect)) == len(args):
        expects = list(_components(expect))
    ts = [_ty(a, env, funs, dtypes, ver, errs, bound, x) for a, x in zip(args, expects)]
    NESTED = {"seq": "seq"}
    if op == "seq":
        # SPEC.md "Sequences: literals, concatenation, slices": [e1, ..., en], [] included; SPEC.md
        # "Compositional types (v1)" (2026-10-06): the elements are of any ONE type T and the display is the
        # seq of T (ints: "seq"; rows: seq<seq>; bools, pairs, sets: {"seq": T}). [] has no element to type
        # from, so it takes `expect` when the caller has a seq type for it and is the seq of ints otherwise.
        if not ts:
            return expect if _is_seq(expect) else "seq"
        if any(t is None for t in ts):
            return None
        if all(t == ts[0] for t in ts):
            return _seq_of(ts[0])
        _e(errs, e, "seq literal elements must all be of one type", "seq-lit-mixed")
        return _seq_of(ts[0])
    if op == "slice":
        if not _is_seq(ts[0]) or ts[1] != "int" or ts[2] != "int":
            _e(errs, e, "slice wants (a seq of any element type, int, int)", "slice-types")
            return "seq"
        return ts[0]
    if op == "+" and len(ts) == 2 and ts[0] == ts[1] and _is_seq(ts[0]):
        # s + t on two seqs (or two nested seqs, SPEC.md "Nested sequences")
        # is concatenation, the same polymorphism as ==.
        return ts[0]
    if op == "len":
        if not (_is_seq(ts[0]) or _is_map(ts[0])):
            _e(errs, e, "len of a non-seq, non-map", "len-nonseq")
        return "int"
    if op == "at" and _is_map(ts[0]):
        # SPEC.md "Maps (v1)" (2026-10-06): m[k], the key of the map's key type, defined iff k in m
        kt, vt = ts[0]["map"]
        if ts[1] != kt and not _empty_display(args[1], ts[1], kt):
            _e(errs, e, f"m[k] wants a key of the map's key type {kt!r}, found {ts[1]!r}", "map-types")
        return vt
    if op == "update" and _is_map(ts[0]):
        kt, vt = ts[0]["map"]
        if ts[1] != kt and not _empty_display(args[1], ts[1], kt):
            _e(errs, e, f"m[k := v] wants a key of the map's key type {kt!r}, found {ts[1]!r}", "map-types")
        if ts[2] != vt and not _empty_display(args[2], ts[2], vt):
            _e(errs, e, f"m[k := v] wants a value of the map's value type {vt!r}, found {ts[2]!r}", "map-types")
        return ts[0]
    if op == "at":
        # SPEC.md "Compositional types (v1)": at(s, i) on a seq<T> gives a T (an int on a plain seq, a row on a
        # seq<seq>, a pair on a seq of pairs).
        if ts[1] != "int" or not _is_seq(ts[0]):
            _e(errs, e, "at wants (a seq of any element type, int)", "at-types")
            return None
        return _elem(ts[0])
    if op == "update":
        # SPEC.md "Sequences as values": s[i := v], (seq<T>, int, T) -> seq<T> for any element type T (SPEC.md
        # "Compositional types (v1)"); the index's definedness is `at`'s.
        if ts[1] != "int":
            _e(errs, e, "update index must be int", "update-types")
        if not _is_seq(ts[0]):
            _e(errs, e, "update wants (a seq of any element type, int, an element of that type)", "update-types")
            return "seq"
        want = _elem(ts[0])
        if ts[2] != want and not _empty_display(args[2], ts[2], want):
            _e(errs, e, f"update wants an element of the seq's own type {want!r}, found {ts[2]!r}", "update-types")
        return ts[0]
    if op == "fill":
        # seq(n, v): n copies of v, a seq of v's type (SPEC.md "Compositional types (v1)").
        if ts[0] != "int":
            _e(errs, e, "fill count must be int", "fill-types")
        return _seq_of(ts[1]) if ts[1] is not None else "seq"
    if op == "set":
        # SPEC.md "Finite sets" (2026-09-27): {e1, ..., en}, {} included; SPEC.md "Compositional types (v1)"
        # (2026-10-06): the elements are of any ONE type T and the display is the set of T ("set" for ints).
        if not ts:
            return expect if _is_set(expect) else "set"
        if any(t is None for t in ts):
            return None
        if all(t == ts[0] for t in ts):
            return _set_of(ts[0])
        _e(errs, e, "set display elements must all be of one type", "set-lit-types")
        return _set_of(ts[0])
    if op == "in" and _is_map(ts[1]):
        # SPEC.md "Maps (v1)" (2026-10-06): domain membership
        kt = ts[1]["map"][0]
        if ts[0] != kt and not _empty_display(args[0], ts[0], kt):
            _e(errs, e, f"k in m wants a key of the map's key type {kt!r}, found {ts[0]!r}", "map-types")
        return "bool"
    if op == "mapdisp":
        # SPEC.md "Maps (v1)": map[k1 := v1, ...]; the keys of one type, the values of one type; map[] takes the
        # expected map type and is map<int, int> where none reaches it
        if len(args) % 2 == 1:
            _e(errs, e, "a map display is written in key/value pairs", "map-lit-types")
            return None
        if not ts:
            return expect if _is_map(expect) else {"map": ["int", "int"]}
        if any(t is None for t in ts):
            return None
        kts, vts = ts[0::2], ts[1::2]
        kt = next((t for t in kts if not (t == "seq" or t == "set")), kts[0])
        vt = next((t for t in vts if not (t == "seq" or t == "set")), vts[0])
        if not all(t == kt or _empty_display(a, t, kt) for a, t in zip(args[0::2], kts)):
            _e(errs, e, "a map display's keys must all be of one type", "map-lit-types")
        if not all(t == vt or _empty_display(a, t, vt) for a, t in zip(args[1::2], vts)):
            _e(errs, e, "a map display's values must all be of one type", "map-lit-types")
        return {"map": [kt, vt]}
    if op == "keys":
        if not _is_map(ts[0]):
            _e(errs, e, "keys of a non-map", "map-types")
            return "set"
        return _set_of(ts[0]["map"][0])
    if op == "remove":
        if not _is_map(ts[0]):
            _e(errs, e, "remove wants a map and a key", "map-types")
            return None
        kt = ts[0]["map"][0]
        if ts[1] != kt and not _empty_display(args[1], ts[1], kt):
            _e(errs, e, f"remove wants a key of the map's key type {kt!r}, found {ts[1]!r}", "map-types")
        return ts[0]
    if op == "in" and _is_seq(ts[1]):
        # SPEC.md "The library (v1)" (2026-10-06): membership in a seq, by the right operand's type
        if ts[0] != _elem(ts[1]) and not _empty_display(args[0], ts[0], _elem(ts[1])):
            _e(errs, e, "in wants (T, seq<T>): an element of the seq's own type", "lib-types")
        return "bool"
    if op == "in":
        if not _is_set(ts[1]) or (ts[0] != _set_elem(ts[1]) and not _empty_display(args[0], ts[0], _set_elem(ts[1]))):
            _e(errs, e, "in wants (T, set<T>) or (T, seq<T>): an element of the collection's own type", "set-types")
        return "bool"
    if op in ("min", "max") and len(ts) == 1:
        # SPEC.md "Reductions (v1)" (2026-10-06): the largest/smallest element of a seq of ints or of reals
        if _is_seq(ts[0]) and _elem(ts[0]) in ("int", "real"):
            return _elem(ts[0])
        _e(errs, e, f"{op} of one argument wants a seq of ints or of reals, found {ts[0]!r}", "lib-types")
        return "int"
    if op in ("isint", "toint"):
        # SPEC.md "The string library (v2)" (2026-10-06): library names over a seq of code points
        if ts[0] != "seq":
            _e(errs, e, f"{op} wants a seq, found {ts[0]!r}", "lib-types")
        return "bool" if op == "isint" else "int"
    if op in ("any", "all"):
        if ts[0] != {"seq": "bool"}:
            _e(errs, e, f"{op} wants a seq<bool>, found {ts[0]!r}", "lib-types")
        return "bool"
    if op == "toset":
        if not _is_seq(ts[0]):
            _e(errs, e, f"toset wants a seq, found {ts[0]!r}", "lib-types")
            return "set"
        return _set_of(_elem(ts[0]))
    if op in ("min", "max"):
        # SPEC.md "The library (v1)" (2026-10-06): two ints or two reals, never mixed
        if not (ts[0] == ts[1] and ts[0] in ("int", "real")):
            _e(errs, e, f"{op} wants two ints or two reals, found {ts!r}", "lib-types")
            return ts[0] if ts[0] in ("int", "real") else "int"
        return ts[0]
    if op == "abs":
        if ts[0] not in ("int", "real"):
            _e(errs, e, f"abs wants an int or a real, found {ts[0]!r}", "lib-types")
            return "int"
        return ts[0]
    if op == "sum":
        if _is_seq(ts[0]) and _elem(ts[0]) in ("int", "real"):
            return _elem(ts[0])
        _e(errs, e, f"sum wants a seq of ints or of reals, found {ts[0]!r}", "lib-types")
        return "int"
    if op in ("gcd", "pow"):
        if list(ts) != ["int", "int"]:
            _e(errs, e, f"{op} wants two ints, found {ts!r}", "lib-types")
        return "int"
    if op == "isqrt":
        if ts[0] != "int":
            _e(errs, e, f"isqrt wants an int, found {ts[0]!r}", "lib-types")
        return "int"
    if op == "rev":
        if not _is_seq(ts[0]):
            _e(errs, e, f"rev wants a seq, found {ts[0]!r}", "lib-types")
            return "seq"
        return ts[0]
    if op == "sort":
        # SPEC.md "Sorting (v1)" (2026-10-06): a seq of ints or of reals, the type's own order
        if not (_is_seq(ts[0]) and _elem(ts[0]) in ("int", "real")):
            _e(errs, e, f"sort wants a seq of ints or of reals, found {ts[0]!r}", "lib-types")
            return "seq"
        return ts[0]
    if op == "card":
        if not _is_set(ts[0]):
            _e(errs, e, "card of a non-set", "set-types")
        return "int"
    if op in ("union", "inter", "diff"):
        same = ts[0] == ts[1] or _empty_display(args[0], ts[0], ts[1]) or _empty_display(args[1], ts[1], ts[0])
        if not (_is_set(ts[0]) and _is_set(ts[1]) and same):
            _e(errs, e, f"{op} wants two sets of one element type", "set-types")
            return "set"
        return ts[1] if _empty_display(args[0], ts[0], ts[1]) else ts[0]
    if op == "pair":
        # SPEC.md "Pairs" (2026-09-10): (e1, e2), typed from its operands; since SPEC.md "Compositional types
        # (v1)" (2026-10-06) the two components are of any types (a pair of pairs, a pair holding a set).
        if ts[0] is None or ts[1] is None:
            return None
        return {"pair": ts}
    if op == "tuple":
        # SPEC.md "Compositional types (v1)": (e1, ..., en), n >= 3; two components are a `pair`, never a tuple.
        if len(ts) < 3:
            _e(errs, e, "a tuple has three or more components (two are a pair)", "tuple-arity")
            return None
        if any(t is None for t in ts):
            return None
        return {"tuple": ts}
    if op in ("fst", "snd"):
        # p.0 / p.1: SPEC.md "Pairs"; on a tuple of three or more they are its first two components (SPEC.md
        # "Compositional types": `.0` and `.1` print and parse as fst and snd on any product).
        comps = _components(ts[0])
        if comps is None:
            _e(errs, e, f"{op} wants a pair or tuple operand, found {ts[0]!r}", "proj-nonpair")
            return None
        return comps[0 if op == "fst" else 1]
    if op == "proj":
        # e.k for k >= 2 (SPEC.md "Compositional types (v1)"): the second argument is the literal index.
        k = args[1].get("int") if isinstance(args[1], dict) else None
        if not isinstance(k, int) or isinstance(k, bool):
            _e(errs, e, "a projection index is an int literal", "proj-index")
            return None
        if k < 2:
            _e(errs, e, "a projection .0 or .1 is fst or snd, never proj", "proj-index")
            return None
        comps = _components(ts[0])
        if comps is None or not (isinstance(ts[0], dict) and set(ts[0]) == {"tuple"}):
            _e(errs, e, f"proj wants a tuple operand, found {ts[0]!r}", "proj-nonpair")
            return None
        if k >= len(comps):
            _e(errs, e, f"projection .{k} of a tuple of {len(comps)}", "proj-index")
            return None
        return comps[k]
    if op in STRLIB_OPS:
        # SPEC.md "The string library" (2026-09-11): every member's
        # signature, seq/int/seq<seq> per the table there. `split` is the
        # only member with two arities, seq -> seq<seq> at one argument or
        # (seq, int) -> seq<seq> at two. Arity first, so a call with too
        # few or too many arguments is a refusal and never an IndexError
        # (the core's adversarial check found the crash, 2026-09-11).
        want = {"split": (1, 2), "join": (2,), "tostr": (1,), "count": (2,),
                "find": (2,), "strip": (1, 2), "lstrip": (1, 2), "rstrip": (1, 2),
                "replace": (3,), "lower": (1,), "upper": (1,), "isdigit": (1,),
                "isalpha": (1,), "isupper": (1,), "islower": (1,),
                "startswith": (2,), "endswith": (2,),
                # SPEC.md "The string library (v2)" (2026-10-06)
                "index": (2,), "rfind": (2,), "zfill": (2,), "center": (2, 3), "ljust": (2, 3), "rjust": (2, 3),
                "capitalize": (1,), "swapcase": (1,), "title": (1,), "isspace": (1,), "isalnum": (1,),
                "splitlines": (1,), "partition": (2,)}[op]
        if len(ts) not in want:
            _e(errs, e, f"{op} wants {' or '.join(str(w) for w in want)} "
                    f"argument(s), found {len(ts)}", "strlib-arity")
            return {"split": NESTED, "join": "seq", "tostr": "seq", "count": "int",
                    "find": "int", "replace": "seq"}.get(op, "seq" if op in
                    ("strip", "lstrip", "rstrip", "lower", "upper") else "bool")
        if op == "split":
            if len(ts) == 1:
                if ts[0] != "seq":
                    _e(errs, e, "split wants a seq", "strlib-types")
            elif ts[0] != "seq" or ts[1] not in ("int", "seq"):
                # SPEC.md "The string library (v2)": a code point or a sequence separator
                _e(errs, e, "split wants (seq, int) or (seq, seq)", "strlib-types")
            return NESTED
        if op in ("strip", "lstrip", "rstrip") and len(ts) == 2:
            if ts[0] != "seq" or ts[1] != "seq":
                _e(errs, e, f"{op} with a character set wants (seq, seq)", "strlib-types")
            return "seq"
        if op in ("index", "rfind"):
            if ts[0] != "seq" or ts[1] != "seq":
                _e(errs, e, f"{op} wants (seq, seq)", "strlib-types")
            return "int"
        if op == "zfill":
            if ts[0] != "seq" or ts[1] != "int":
                _e(errs, e, "zfill wants (seq, int)", "strlib-types")
            return "seq"
        if op in ("center", "ljust", "rjust"):
            if ts[0] != "seq" or ts[1] != "int" or (len(ts) == 3 and ts[2] != "int"):
                _e(errs, e, f"{op} wants (seq, int) or (seq, int, int)", "strlib-types")
            return "seq"
        if op in ("capitalize", "swapcase", "title"):
            if ts[0] != "seq":
                _e(errs, e, f"{op} wants a seq", "strlib-types")
            return "seq"
        if op in ("isspace", "isalnum"):
            if ts[0] != "seq":
                _e(errs, e, f"{op} wants a seq", "strlib-types")
            return "bool"
        if op == "splitlines":
            if ts[0] != "seq":
                _e(errs, e, "splitlines wants a seq", "strlib-types")
            return NESTED
        if op == "partition":
            if ts[0] != "seq" or ts[1] != "seq":
                _e(errs, e, "partition wants (seq, seq)", "strlib-types")
            return {"tuple": ["seq", "seq", "seq"]}
        if op == "join":
            if ts[0] != NESTED or ts[1] != "seq":
                _e(errs, e, "join wants (seq<seq>, seq)", "strlib-types")
            return "seq"
        if op == "tostr":
            if ts[0] != "int":
                _e(errs, e, "tostr wants an int", "strlib-types")
            return "seq"
        if op in ("count", "find"):
            if ts[0] != "seq" or ts[1] != "seq":
                _e(errs, e, f"{op} wants (seq, seq)", "strlib-types")
            return "int"
        if op in ("strip", "lstrip", "rstrip", "lower", "upper"):
            if ts[0] != "seq":
                _e(errs, e, f"{op} wants a seq", "strlib-types")
            return "seq"
        if op == "replace":
            if ts[0] != "seq" or ts[1] != "seq" or ts[2] != "seq":
                _e(errs, e, "replace wants (seq, seq, seq)", "strlib-types")
            return "seq"
        if op in ("isdigit", "isalpha", "isupper", "islower"):
            if ts[0] != "seq":
                _e(errs, e, f"{op} wants a seq", "strlib-types")
            return "bool"
        if ts[0] != "seq" or ts[1] != "seq":       # startswith, endswith
            _e(errs, e, f"{op} wants (seq, seq)", "strlib-types")
        return "bool"
    if op in ("+", "-", "*", "neg", "div", "mod"):
        # SPEC.md "Exact rationals (v1)" (2026-10-06): all-int or all-real, never mixed; `/` on reals is exact
        # division (the op stays "div"; the type decides), `%` is int-only.
        if ts and all(t == "real" for t in ts) and op != "mod":
            return "real"
        if any(t != "int" for t in ts):
            _e(errs, e, f"{op} wants all ints or all reals (not {ts!r}); write real(x) to convert", "arith-int")
            return "real" if "real" in ts and op != "mod" else "int"
        return "int"
    if op in ("toreal", "floor", "ceil"):
        want = "int" if op == "toreal" else "real"
        if ts[0] != want:
            _e(errs, e, f"{op} wants a {want}, found {ts[0]!r}", "real-conv")
        return "real" if op == "toreal" else "int"
    if op in ("<", "<=", ">", ">="):
        if not (all(t == "int" for t in ts) or all(t == "real" for t in ts)):
            _e(errs, e, f"{op} compares two ints or two reals (SPEC.md gate 1; Exact rationals)", "cmp-int")
        return "bool"
    if op in ("==", "!="):
        # Two seqs compare extensionally since SPEC.md "Sequences as
        # values"; two pairs compare componentwise since SPEC.md "Pairs"
        # (2026-09-10), "the polymorphic == again" -- dict equality on the
        # two type dicts already refuses a `==` across two DIFFERENT pair
        # types (a pair of (int, int) against a pair of (bool, int)), same
        # as it refuses int against seq.
        if ts[0] != ts[1] and not (_empty_display(args[0], ts[0], ts[1]) or _empty_display(args[1], ts[1], ts[0])):
            # SPEC.md "Nested sequences" (2026-09-10) and "Compositional types (v1)" (2026-10-06): a bare `[]` or
            # `{}` with no hint is the seq or set of ints by default; against another seq or set type on the other
            # side it is the empty value of THAT type, not a type error (`==` has no declared type to hint with).
            _e(errs, e, f"{op} wants two values of one type, found {ts[0]!r} and {ts[1]!r}", "eq-types")
        return "bool"
    if any(t != "bool" for t in ts):
        _e(errs, e, f"{op} over non-bool", "bool-op")
    return "bool"


def _self_calls(e, name) -> bool:
    if isinstance(e, dict):
        if "call" in e and e["call"]["fun"] == name:
            return True
        return any(_self_calls(v, name) for v in e.values())
    if isinstance(e, list):
        return any(_self_calls(v, name) for v in e)
    return False


def expression_type(expr: dict, variables: dict, functions: dict | None = None,
                    expected=None, positions: dict | None = None,
                    file: str = "<string>", datatypes: dict | None = None) -> tuple:
    """Type an expression using the same rules as task checking.

    Surface inline helpers use this before expansion, so unused definitions and
    arguments cannot escape the ordinary scope and type rules. `datatypes`
    (name -> decl) is new for SPEC.md "Datatypes (v1)" (2026-09-27) and
    defaults to empty: no existing caller passes a datatype-typed
    expression through an inline helper today, so `{}` reproduces exactly
    what this function did before datatypes existed, and a helper that DOES
    reach a `ctor`/`match` node is refused here (an "unbound"-style datatype
    name) rather than silently typed against some other task's declarations.
    """
    errors = _Errs(positions, file)
    result = _ty(expr, variables, functions or {}, datatypes or {}, 1, errors, set(), expected)
    return result, errors


def check_wf(task: dict, positions: dict | None = None,
            file: str = "<string>", *, expression_funs: dict | None = None) -> list:
    """Well-formedness errors in `task` (SYNTAX.md's grammar plus SPEC.md's
    scope, typing and gate rules). With no `positions` argument (the default)
    the return is a list[str], each `"message [SPEC: rule]"`, byte-identical
    to check_wf's behaviour before this function grew position-awareness --
    every existing caller (fuzz_lower.py, grade.py, test_check_wf.py) is
    unaffected. With a `positions` map (`id(AST node) -> (line, col)`, the
    shape `surface.parse(text, positions=...)` fills for this same `task`
    object) the return is a list[WfError] instead, each carrying `file`,
    `line` and `col` for the AST node `check_wf` or one of its helpers was
    looking at when it found the problem (the innermost node it can
    attribute the error to), plus the same `.rule` key and `str()` message
    as the no-position form, now prefixed `file:line:col: `. An empty list
    means `task` is well-formed, in either form. `expression_funs` is the
    surface elaborator's temporary signature environment for inline calls;
    it does not add definitions to the task or authorize new backend nodes.
    The elaborator checks again without it after expansion."""
    errs = _Errs(positions, file)
    ver = task["t"]
    if not NAME_RE.match(task["name"]):
        _e(errs, task, "bad task name", "name")
    if len(task["returns"]) != 1:
        _e(errs, task, "exactly one return value (SPEC.md v0 and v1)", "one-return")
    if not task["ensures"]:
        _e(errs, task, "ensures must be non-empty", "ensures-nonempty")
    # SPEC.md "Datatypes (v1)" (2026-09-27): `task["datatypes"]`, a list of
    # {"name": D, "ctors": [{"name": C}, ...]} -- v1 is enumerations only, a
    # constructor carries no fields, so a `ctor` dict with anything under
    # "fields" is refused here by name rather than silently accepted and
    # dropped at interp time. `dtypes` (name -> decl) is threaded through
    # every `_ty` call the same way `funs` already is, so a type or a
    # `ctor`/`match` node can be checked against ITS OWN task's declarations
    # only -- there is no such thing as a datatype declared by one task and
    # used by another.
    if ver == 0 and "datatypes" in task:
        _e(errs, task, "v1 field in a v0 task", "v0-frozen")
    dtypes: dict = {}
    for d in task.get("datatypes", []):
        dname = d.get("name")
        if not isinstance(dname, str) or not NAME_RE.match(dname):
            _e(errs, task, f"bad datatype name {dname!r}", "datatype-name")
            continue
        if dname in dtypes:
            _e(errs, task, f"datatype {dname} declared twice", "datatype-dup")
            continue
        ctors = d.get("ctors")
        if not isinstance(ctors, list) or not ctors:
            _e(errs, d, f"datatype {dname} has no constructors", "datatype-empty")
            dtypes[dname] = d
            continue
        cnames = set()
        for c in ctors:
            cname = c.get("name") if isinstance(c, dict) else None
            if not isinstance(cname, str) or not NAME_RE.match(cname):
                _e(errs, d, f"datatype {dname}: bad constructor name {cname!r}",
                   "ctor-name")
                continue
            if cname in cnames:
                _e(errs, d, f"datatype {dname}: constructor {cname} declared twice",
                   "ctor-dup")
            cnames.add(cname)
            if c.get("fields"):
                # SPEC.md "Datatypes (v1)": "enumerations: a datatype whose
                # constructors carry no fields ... records ... [and] non-
                # recursive sums ... stay out of v1" for this landing --
                # only the enum shape is implemented end to end (interp,
                # the seven lowerings, the ladder move), so a constructor
                # that DOES carry fields is refused here by name instead of
                # being accepted and then mishandled downstream.
                _e(errs, d, f"datatype {dname}: constructor {cname} carries "
                            f"fields, not in this v1 landing (enumerations "
                            f"only)", "ctor-fields-not-v1")
        dtypes[dname] = d
    funs = dict(expression_funs or {})
    funs.update({f["name"]: f for f in task.get("spec_funs", [])})
    if ver == 0 and (funs or "decreases" in task or "gate" in task
                     or "methods" in task or "lemmas" in task):
        _e(errs, task, "v1 field in a v0 task", "v0-frozen")
    penv = {p["name"]: p["type"] for p in task["params"]}
    # v0 is int only (SPEC.md v0; `bool` and `seq` are v1 types), for the return as for the parameters: a `t 0`
    # task returning bool passed this check and the Verus and Rocq v0 lowerings emitted it as int (2026-10-03)
    if ver == 0 and any(t != "int" for t in list(penv.values()) + [r["type"] for r in task["returns"]]):
        _e(errs, task, "v0 has int only", "v0-int-only")
    for p in task["params"]:
        if not _valid_type(p["type"], dtypes):
            _e(errs, p, f"param {p['name']} has an invalid type: {p['type']!r}", "valid-type")
    for r in task["returns"]:
        if not _valid_type(r["type"], dtypes):
            _e(errs, r, f"return {r['name']} has an invalid type: {r['type']!r}", "valid-type")
    for i, f in enumerate(task.get("spec_funs", [])):
        fenv = {p["name"]: p["type"] for p in f["params"]}
        earlier = dict(expression_funs or {})
        earlier.update({g["name"]: g for g in task["spec_funs"][:i]})
        earlier[f["name"]] = f              # self-recursion is allowed
        for p in f["params"]:
            if not _valid_type(p["type"], dtypes):
                _e(errs, p, f"spec_fun {f['name']}: {p['name']} has an invalid type: {p['type']!r}", "valid-type")
        if not _valid_type(f["result"], dtypes):
            # SPEC.md "Compositional types (v1)" (2026-10-06): any t type; an invalid one is refused here by name,
            # where before an unlisted result only failed the body-type check below under a misleading message.
            _e(errs, f, f"spec_fun {f['name']} result is not a t type: {f['result']!r}", "spec-fun-result")
        if _ty(f["decreases"], fenv, earlier, dtypes, ver, errs, set()) != "int":
            _e(errs, f, f"spec_fun {f['name']} decreases is not int", "spec-fun-decreases-int")
        if _ty(f["body"], fenv, earlier, dtypes, ver, errs, set(), f["result"]) != f["result"]:
            _e(errs, f, f"spec_fun {f['name']} body type != result", "spec-fun-body-type")
    for e in task.get("requires", []):
        if _ty(e, penv, funs, dtypes, ver, errs, set()) != "bool":
            _e(errs, e, "requires clause is not bool", "requires-bool")
    ret = task["returns"][0]
    eenv = dict(penv)
    eenv[ret["name"]] = ret["type"]
    for e in task["ensures"]:
        if _ty(e, eenv, funs, dtypes, ver, errs, set()) != "bool":
            _e(errs, e, "ensures clause is not bool", "ensures-bool")
    if _self_calls(task["ensures"], task["name"]):
        _e(errs, task, "ensures references the task name (SPEC.md gate 3)", "no-self-in-ensures")
    selfrec = _self_calls(task["body"], task["name"])
    if selfrec and "decreases" not in task:
        _e(errs, task, "self-recursive body without a task decreases", "decreases-selfcall")
    if not selfrec and "decreases" in task:
        _e(errs, task, "task decreases without a self-call", "decreases-selfcall")
    methods = task.get("methods", [])       # a v0 task with methods: v0-frozen above
    mnames = [m.get("name") for m in methods]
    # SPEC.md "Lemmas (v1)": checked before the methods, since a method
    # body may call any lemma and a lemma calls no method.
    lemmas = task.get("lemmas", [])
    lnames = [l.get("name") for l in lemmas]
    lsigs: dict = {}
    for i, l in enumerate(lemmas):
        _check_lemma(l, i, task, funs, lsigs, lnames, mnames, dtypes, ver, errs)
        if isinstance(l.get("name"), str) and isinstance(l.get("params"), list):
            lsigs[l["name"]] = l
    all_lemmas = {n for n in lnames if isinstance(n, str)}
    msigs = {}
    for i, m in enumerate(methods):
        _check_method(m, i, task, funs, msigs, mnames, dtypes, ver, errs, lemmas=lsigs)
        if isinstance(m.get("name"), str) and len(m.get("returns", [])) == 1:
            msigs[m["name"]] = {"params": m["params"],
                                "result": m["returns"][0]["type"],
                                "body": None, "decreases": None, "_method": True}
    all_methods = {n for n in mnames if isinstance(n, str)}
    for e in list(task.get("requires", [])) + list(task["ensures"]):
        _no_method_calls(e, all_methods, errs)
    for l in lemmas:
        for e in list(l.get("requires", [])) + list(l.get("ensures", [])) + (
                [l["decreases"]] if "decreases" in l else []):
            _no_method_calls(e, all_methods, errs)
    if "decreases" in task:
        _no_method_calls(task["decreases"], all_methods, errs)
    for f in task.get("spec_funs", []):
        _no_method_calls(f["body"], all_methods, errs)
        _no_method_calls(f["decreases"], all_methods, errs)
    bfuns = dict(funs)
    bfuns.update(msigs)
    if selfrec:
        bfuns[task["name"]] = {"params": task["params"],
                               "result": ret["type"], "body": None,
                               "decreases": None}
    _check_call_positions(task["body"], all_methods, errs)
    _check_stmts(task["body"], dict(eenv), bfuns, dtypes, ver, errs, {ret["name"]},
                 lemmas=lsigs)
    _check_returns(task["body"], ret["name"], errs)
    return errs


def _check_method(m, i, task, funs, earlier_sigs, mnames, dtypes, ver, errs,
                  lemmas=None):
    """One entry of `methods` (SPEC.md "Methods (v1)"): a named body with
    its own contract, checked like a task, whose body may call the
    spec_funs, every EARLIER method, and itself when it carries a
    decreases. Copied from Dafny's methods (reference manual 6.3, 8.5.2):
    a call is one statement's whole right-hand side."""
    name = m.get("name")
    if not isinstance(name, str) or not NAME_RE.match(name):
        _e(errs, m, f"bad method name {name!r}", "method-name")
        return
    if name == task["name"] or name in funs or mnames.count(name) > 1:
        _e(errs, m, f"method name {name} collides with the task, a spec_fun "
                    f"or another method", "method-name")
    for k in ("params", "returns", "requires", "ensures", "body"):
        if k not in m:
            _e(errs, m, f"method {name} is missing {k!r}", "method-name")
            return
    if len(m["returns"]) != 1:
        _e(errs, m, f"method {name}: exactly one return value", "one-return")
        return
    if not m["ensures"]:
        _e(errs, m, f"method {name}: ensures must be non-empty", "ensures-nonempty")
    penv = {p["name"]: p["type"] for p in m["params"]}
    for p in m["params"] + m["returns"]:
        if not _valid_type(p["type"], dtypes):
            _e(errs, p, f"method {name}: {p['name']} has an invalid type: "
                        f"{p['type']!r}", "valid-type")
    for e in m["requires"]:
        if _ty(e, penv, funs, dtypes, ver, errs, set()) != "bool":
            _e(errs, e, f"method {name}: requires clause is not bool", "requires-bool")
    r = m["returns"][0]
    eenv = dict(penv)
    eenv[r["name"]] = r["type"]
    if len(eenv) != len(m["params"]) + 1:
        _e(errs, m, f"method {name}: a parameter and the return share a name",
           "local-shadow")
    for e in m["ensures"]:
        if _ty(e, eenv, funs, dtypes, ver, errs, set()) != "bool":
            _e(errs, e, f"method {name}: ensures clause is not bool", "ensures-bool")
    here = {n for n in mnames if isinstance(n, str)} | {task["name"]}
    for e in list(m["requires"]) + list(m["ensures"]):
        _no_method_calls(e, here, errs)
    selfrec = _self_calls(m["body"], name)
    if selfrec and "decreases" not in m:
        _e(errs, m, f"method {name}: self-recursive body without a decreases",
           "method-decreases")
    if not selfrec and "decreases" in m:
        _e(errs, m, f"method {name}: decreases without a self-call", "method-decreases")
    if "decreases" in m:
        _no_method_calls(m["decreases"], here, errs)
        if _ty(m["decreases"], penv, funs, dtypes, ver, errs, set()) != "int":
            _e(errs, m, f"method {name}: decreases is not int", "method-decreases")
    later = {n for n in mnames[i + 1:] if isinstance(n, str)} | {task["name"]}
    if _calls_any(m["body"], later):
        _e(errs, m, f"method {name} calls a later method or the task", "method-order")
    bfuns = dict(funs)
    bfuns.update(earlier_sigs)
    if selfrec:
        bfuns[name] = {"params": m["params"], "result": r["type"],
                       "body": None, "decreases": None, "_method": True}
    _check_call_positions(m["body"], here, errs)
    _check_stmts(m["body"], dict(eenv), bfuns, dtypes, ver, errs, {r["name"]},
                 lemmas=lemmas)
    _check_returns(m["body"], r["name"], errs)


def _check_lemma_call(s, env, funs, dtypes, ver, errs, lemmas) -> None:
    """`{"lemma": {"name": L, "args": [...]}}`: Dafny's lemma call
    statement (reference manual 6.3.3), a no-op at run time whose effect is
    the lemma's ensures at the arguments, owed its requires there."""
    c = s["lemma"]
    if not isinstance(c, dict) or not isinstance(c.get("args"), list):
        _e(errs, s, "a lemma call is {name, args}", "lemma-call")
        return
    l = lemmas.get(c.get("name"))
    if l is None:
        _e(errs, s, f"call of unknown lemma {c.get('name')!r}", "lemma-call")
        return
    if len(l["params"]) != len(c["args"]):
        _e(errs, s, f"arity mismatch calling lemma {c['name']}", "lemma-call")
    for p, a in zip(l["params"], c["args"]):
        if _ty(a, env, funs, dtypes, ver, errs, set(), p["type"]) != p["type"]:
            _e(errs, s, f"argument type mismatch calling lemma {c['name']}",
               "lemma-call")


def _lemma_calls(body) -> list:
    """Every lemma-call statement's name under `body` (if branches too)."""
    out = []
    for s in body:
        if isinstance(s, dict) and "lemma" in s and isinstance(s["lemma"], dict):
            out.append(s["lemma"].get("name"))
        elif isinstance(s, dict) and "if" in s:
            out += _lemma_calls(s["if"]["then"]) + _lemma_calls(s["if"]["else"])
        elif isinstance(s, dict) and "while" in s:
            out += _lemma_calls(s["while"]["body"])
    return out


def _check_lemma_body(body, name, errs) -> None:
    for s in body:
        if (not isinstance(s, dict) or not ("if" in s or "lemma" in s or "assert" in s)
                or len(s) != 1):
            _e(errs, s, f"lemma {name}: a lemma body holds only if, assert and "
                        f"lemma calls", "lemma-body")
        elif "if" in s:
            _check_lemma_body(s["if"]["then"], name, errs)
            _check_lemma_body(s["if"]["else"], name, errs)


def _check_lemma(l, i, task, funs, earlier, lnames, mnames, dtypes, ver, errs):
    """One entry of `lemmas` (SPEC.md "Lemmas (v1)"), copied from Dafny's
    lemma (reference manual 6.3.3): a ghost method with no return, whose
    requires/ensures are the statement and whose body is its proof. The
    body holds only `if` and calls of EARLIER lemmas or of itself (with a
    decreases): Dafny's own shape for a case split and an induction."""
    name = l.get("name")
    if not isinstance(name, str) or not NAME_RE.match(name):
        _e(errs, l, f"bad lemma name {name!r}", "lemma-name")
        return
    if (name == task["name"] or name in funs or lnames.count(name) > 1
            or name in mnames or name == "assert"):
        _e(errs, l, f"lemma name {name} collides with the task, a spec_fun, "
                    f"a method or another lemma", "lemma-name")
    for k in ("params", "requires", "ensures", "body"):
        if k not in l:
            _e(errs, l, f"lemma {name} is missing {k!r}", "lemma-name")
            return
    if "returns" in l:
        _e(errs, l, f"lemma {name} has no return", "lemma-body")
    if not l["ensures"]:
        _e(errs, l, f"lemma {name}: ensures must be non-empty", "ensures-nonempty")
    penv = {p["name"]: p["type"] for p in l["params"]}
    if len(penv) != len(l["params"]):
        _e(errs, l, f"lemma {name}: two parameters share a name", "local-shadow")
    for p in l["params"]:
        if not _valid_type(p["type"], dtypes):
            _e(errs, p, f"lemma {name}: {p['name']} has an invalid type: "
                        f"{p['type']!r}", "valid-type")
    for e in l["requires"]:
        if _ty(e, penv, funs, dtypes, ver, errs, set()) != "bool":
            _e(errs, e, f"lemma {name}: requires clause is not bool", "requires-bool")
    for e in l["ensures"]:
        if _ty(e, penv, funs, dtypes, ver, errs, set()) != "bool":
            _e(errs, e, f"lemma {name}: ensures clause is not bool", "ensures-bool")
    _check_lemma_body(l["body"], name, errs)
    called = _lemma_calls(l["body"])
    selfrec = name in called
    if selfrec and "decreases" not in l:
        _e(errs, l, f"lemma {name}: self-calling body without a decreases",
           "lemma-decreases")
    if not selfrec and "decreases" in l:
        _e(errs, l, f"lemma {name}: decreases without a self-call", "lemma-decreases")
    if "decreases" in l and _ty(l["decreases"], penv, funs, dtypes, ver, errs, set()) != "int":
        _e(errs, l, f"lemma {name}: decreases is not int", "lemma-decreases")
    allowed = set(earlier) | {name}
    if any(c not in allowed for c in called if isinstance(c, str)
           and c in lnames):
        _e(errs, l, f"lemma {name} calls a later lemma", "lemma-order")
    sigs = dict(earlier)
    sigs[name] = l
    _check_stmts(l["body"], dict(penv), funs, dtypes, ver, errs, set(), lemmas=sigs,
                 in_lemma=True)


def _calls_any(e, names) -> bool:
    if isinstance(e, dict):
        if "call" in e and isinstance(e["call"], dict) and e["call"].get("fun") in names:
            return True
        return any(_calls_any(v, names) for v in e.values())
    if isinstance(e, list):
        return any(_calls_any(v, names) for v in e)
    return False


def _no_method_calls(e, names, errs) -> None:
    if names and _calls_any(e, names):
        _e(errs, e, "a method call outside the right-hand side of an assign "
                    "or var init", "method-call-position")


def _check_call_positions(body, names, errs) -> None:
    """Dafny reference manual 8.5.2: a method call is the whole right-hand
    side of `:=`, and its result is never an argument or an operand."""
    if not names:
        return
    for s in body:
        rhs = None
        if "assign" in s:
            rhs = s["assign"][1]
        elif "var" in s and isinstance(s["var"], dict):
            rhs = s["var"].get("init")
        if rhs is not None:
            if "call" in rhs and rhs["call"]["fun"] in names:
                _no_method_calls(rhs["call"]["args"], names, errs)
            else:
                _no_method_calls(rhs, names, errs)
        elif "return" in s:
            _no_method_calls(s["return"][1], names, errs)
        elif "lemma" in s and isinstance(s["lemma"], dict):
            _no_method_calls(s["lemma"].get("args", []), names, errs)
        elif "if" in s:
            _no_method_calls(s["if"]["cond"], names, errs)
            _check_call_positions(s["if"]["then"], names, errs)
            _check_call_positions(s["if"]["else"], names, errs)
        elif "while" in s:
            w = s["while"]
            _no_method_calls(w.get("cond"), names, errs)
            _no_method_calls(w.get("invariants", []), names, errs)
            _no_method_calls(w.get("decreases"), names, errs)
            _check_call_positions(w.get("body", []), names, errs)


def _check_returns(body, rname, errs):
    """Every `return` names the task's return variable, never a local that
    happens to be assignable in scope (SPEC.md Early exit)."""
    for s in body:
        if "return" in s and s["return"][0] != rname:
            _e(errs, s, f"return names {s['return'][0]}, not the task's return {rname}",
               "return-name")
        elif "if" in s:
            _check_returns(s["if"]["then"], rname, errs)
            _check_returns(s["if"]["else"], rname, errs)
        elif "while" in s:
            _check_returns(s["while"]["body"], rname, errs)


def _has_own_exit(body: list) -> bool:
    """SPEC.md "Early exits (v1)": a `break` at this loop's level (under ifs, not inside a nested loop, whose break
    is its own) or a `return` anywhere in the body."""
    for s in body:
        if "break" in s or "return" in s:
            return True
        if "if" in s and (_has_own_exit(s["if"]["then"]) or _has_own_exit(s["if"]["else"])):
            return True
        if "while" in s and _returns_somewhere(s["while"]["body"]):
            return True
    return False


def _returns_somewhere(body: list) -> bool:
    for s in body:
        if "return" in s:
            return True
        if "if" in s and (_returns_somewhere(s["if"]["then"]) or _returns_somewhere(s["if"]["else"])):
            return True
        if "while" in s and _returns_somewhere(s["while"]["body"]):
            return True
    return False


def _check_stmts(body, env, funs, dtypes, ver, errs, assignable, lemmas=None,
                 in_lemma=False, loop_depth=0):
    lemmas = {} if lemmas is None else lemmas
    for s in body:
        if "assign" in s:
            n, e = s["assign"]
            if n not in assignable:
                _e(errs, s, f"assign to {n}, not a return or local", "assign-target")
            t = _ty(e, env, funs, dtypes, ver, errs, set(), env.get(n))
            if t != env.get(n):
                _e(errs, s, f"assign {n}: {t} into {env.get(n)}", "assign-type")
        elif "var" in s:
            if ver == 0:
                _e(errs, s, "local in a v0 task", "local-v0")
            d = s["var"]
            if d["name"] in env:
                _e(errs, s, f"local {d['name']} shadows a name in scope", "local-shadow")
            if not _valid_type(d["type"], dtypes):
                _e(errs, s, f"local {d['name']} has an invalid type: "
                       f"{d['type']!r}", "valid-type")
            if _ty(d["init"], env, funs, dtypes, ver, errs, set(), d["type"]) != d["type"]:
                _e(errs, s, f"local {d['name']} init type mismatch", "assign-type")
            env[d["name"]] = d["type"]
            assignable.add(d["name"])
        elif "if" in s:
            c = s["if"]
            if _ty(c["cond"], env, funs, dtypes, ver, errs, set()) != "bool":
                _e(errs, s, "if condition is not bool", "bool-cond")
            _check_stmts(c["then"], dict(env), funs, dtypes, ver, errs, set(assignable),
                         lemmas, in_lemma, loop_depth)
            _check_stmts(c["else"], dict(env), funs, dtypes, ver, errs, set(assignable),
                         lemmas, in_lemma, loop_depth)
        elif "while" in s:
            if ver == 0:
                _e(errs, s, "while in a v0 task", "while-v0")
            w = s["while"]
            if _ty(w["cond"], env, funs, dtypes, ver, errs, set()) != "bool":
                _e(errs, s, "loop condition is not bool", "bool-cond")
            if "decreases" not in w:
                _e(errs, s, "loop without decreases (SPEC.md gate 2)", "loop-decreases")
            elif _ty(w["decreases"], env, funs, dtypes, ver, errs, set()) != "int":
                _e(errs, s, "loop decreases is not int", "loop-decreases")
            for inv in w.get("invariants", []):
                if _ty(inv, env, funs, dtypes, ver, errs, set()) != "bool":
                    _e(errs, s, "loop invariant is not bool", "loop-invariant-bool")
            if w["cond"] == {"bool": True} and not _has_own_exit(w["body"]):
                # SPEC.md "Early exits (v1)" (2026-10-06)
                _e(errs, s, "while true without a break of its own or a return never ends (SPEC.md Early exits)",
                   "loop-exit")
            _check_stmts(w["body"], dict(env), funs, dtypes, ver, errs, set(assignable),
                         lemmas, in_lemma, loop_depth + 1)
        elif "return" in s:
            if ver == 0:
                _e(errs, s, "return in a v0 task", "return-v0")
            n, e = s["return"]
            if n not in assignable:
                _e(errs, s, f"return names {n}, not the task's return", "return-name")
            t = _ty(e, env, funs, dtypes, ver, errs, set(), env.get(n))
            if t != env.get(n):
                _e(errs, s, f"return {n}: {t} into {env.get(n)}", "assign-type")
            if s is not body[-1]:
                _e(errs, s, "statement after return is unreachable (SPEC.md Early exit)",
                   "return-unreachable")
        elif "break" in s or "continue" in s:
            # SPEC.md "Early exits (v1)" (2026-10-06): inside a loop, last in its block
            kind = "break" if "break" in s else "continue"
            if ver == 0:
                _e(errs, s, f"{kind} in a v0 task", "v0-frozen")
            if loop_depth == 0:
                _e(errs, s, f"{kind} outside a loop", "exit-outside-loop")
            if s is not body[-1]:
                _e(errs, s, f"statement after {kind} is unreachable (SPEC.md Early exits)", "exit-unreachable")
        elif "lemma" in s:
            if ver == 0:
                _e(errs, s, "lemma call in a v0 task", "v0-frozen")
            _check_lemma_call(s, env, funs, dtypes, ver, errs, lemmas)
        elif "assert" in s and in_lemma:
            # SPEC.md "Lemmas (v1)": a proof step inside a lemma body only
            if _ty(s["assert"], env, funs, dtypes, ver, errs, set()) != "bool":
                _e(errs, s, "assert is not bool", "bool-cond")
        else:
            _e(errs, s, f"t has no statement {sorted(s)!r}", "unknown-stmt")
