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
    "arith-int": "+ - * neg div mod are int-only",
    "assign-target": "assign targets a return or a local in scope (Gate 2)",
    "assign-type": "assign's expression type must match the target's declared type",
    "at-types": "at wants (seq or seq<seq>, int) (Gate 1; Nested sequences)",
    "bool-cond": "a condition or loop guard must be bool",
    "bool-lit-v1": "the bool literal is a v1 construct (Gate 1)",
    "bool-op": "and/or/not/implies are bool-only",
    "call-argtype": "a call's argument types must match the callee's params (Gate 3)",
    "call-arity": "a call's arity must match the callee's params (Gate 3)",
    "call-unknown": "call names a declared spec_fun or the task's own name (Gate 3)",
    "cmp-int": "< <= > >= are int-only (Gate 1)",
    "decreases-selfcall": "a task decreases requires a self-recursive body, and vice versa (Gate 3)",
    "ensures-bool": "each ensures clause must be bool",
    "ensures-nonempty": "ensures must be non-empty (v0 and v1)",
    "eq-types": "== and != apply to two ints, two bools, two seqs, two "
                "nested seqs, or two pairs of the same type",
    "fill-types": "fill wants (int, int) or (int, seq) for the row "
                  "(Sequences as values; Nested sequences)",
    "ite-branches": "ite branches must have the same type",
    "local-shadow": "a local must not shadow a name already in scope (Gate 1 scope rule)",
    "local-v0": "locals are a v1 construct (Gate 2)",
    "name": "the task name matches [A-Za-z][A-Za-z0-9_]*",
    "no-self-in-ensures": "ensures never references the task's own name (Gate 3)",
    "one-return": "exactly one return value (SPEC.md v0 and v1)",
    "op-arity": "each operator has the fixed arity its Expr form declares",
    "op-unknown": "an operator must be in the declared version's operator set",
    "pair-types": "pair components must each be int, bool or seq, no pair "
                  "of pairs, no pair of three (Pairs)",
    "proj-nonpair": "fst/snd require a pair operand (Pairs)",
    "quant-bounds": "a quantifier's lo and hi must be int (Gate 1)",
    "quant-body": "a quantifier's body must be bool (Gate 1)",
    "quant-shadow": "a bound variable must not collide with a name already "
                    "in scope (Gate 1 scope rule)",
    "requires-bool": "each requires clause must be bool",
    "return-name": "return must name the task's return variable (Early exit)",
    "return-unreachable": "no statement follows a return in its block (Early exit)",
    "return-v0": "return is a v1 construct (Early exit)",
    "seq-lit-mixed": "a seq literal's elements must be all int or all seq, "
                     "no mixing, no pair or nested-seq rows (Nested sequences)",
    "slice-types": "slice wants (seq or seq<seq>, int, int) (Sequences: "
                   "literals, concatenation, slices)",
    "len-nonseq": "len is defined on a seq (Gate 1)",
    "loop-decreases": "a loop requires a decreases measure (Gate 2)",
    "loop-invariant-bool": "each loop invariant must be bool (Gate 2)",
    "spec-fun-body-type": "a spec_fun's body type must match its declared result (Gate 3)",
    "spec-fun-decreases-int": "a spec_fun's decreases must be int (Gate 3)",
    "strlib-arity": "each string-library member has a fixed arity (The string library)",
    "strlib-types": "each string-library member's argument types must "
                    "match its signature (The string library)",
    "unbound": "a name must be bound before use (v0 and Gate 1 scope rule)",
    "unknown-stmt": "a Stmt is one of assign/var/if/while/return (v0 Stmt; Gate 2)",
    "update-types": "update wants (seq, int, int) or (seq<seq>, int, seq) "
                    "for the row (Sequences as values; Nested sequences)",
    "v0-frozen": "t:0 is frozen; spec_funs/decreases/gate are v1 fields",
    "v0-int-only": "v0 has int only",
    "v1-expr-v0": "ite/forall/exists/call are v1 expression forms (v1: the three gates)",
    "valid-type": "a declared type is int, bool, seq, a pair of two base "
                  "types, or a seq<seq> (Pairs; Nested sequences)",
    "while-v0": "while is a v1 construct (Gate 2)",
}


def _e(errs: list[str], msg: str, rule: str) -> None:
    """Append msg to errs with its SPEC.md rule named, fixed form
    "msg [SPEC: rule]". The rule key must be in RULES; msg is kept
    unchanged as the prefix so prefix-matching tests still pass."""
    errs.append(f"{msg} [SPEC: {RULES[rule]}]")


# ===========================================================================
# 1. Well-formedness: SYNTAX.md grammar plus SPEC.md's scope rules.
# ===========================================================================

NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
V0_OPS = {"+", "-", "*", "neg", "==", "!=", "<", "<=", ">", ">=",
          "and", "or", "not", "implies"}
# div and mod are v1 (SPEC.md "Division and modulo", 2026-09-08): Euclidean,
# undefined at y == 0, so v1's definedness rules apply to them as to at.
# pair, fst, snd are v1 (SPEC.md "Pairs", 2026-09-10): a pair is a value, and
# `fst`/`snd` are its only projections.
# The string library is v1 (SPEC.md "The string library", 2026-09-11): 17
# polymorphic seq members, split at two arities (one op).
STRLIB_OPS = {"split", "join", "tostr", "count", "find", "strip", "lstrip",
             "rstrip", "replace", "lower", "upper", "isdigit", "isalpha",
             "isupper", "islower", "startswith", "endswith"}
V1_OPS = (V0_OPS | {"len", "at", "div", "mod", "update", "fill", "seq", "slice"}
         | {"pair", "fst", "snd"} | STRLIB_OPS)
TERNARY = {"update", "slice", "replace"}
VARIADIC = {"seq"}      # the literal: any arity, zero included
UNARY = {"neg", "not", "len", "fst", "snd", "tostr", "strip", "lstrip",
         "rstrip", "lower", "upper", "isdigit", "isalpha", "isupper",
         "islower"}
NARY = {"and", "or"}
BOOLR = {"==", "!=", "<", "<=", ">", ">=", "and", "or", "not", "implies"}
INTR = {"+", "-", "*", "neg", "len"}
BASE_TYPES = ("int", "bool", "seq")     # every T1, T2 a pair may hold


def _valid_type(t) -> bool:
    """A well-formed t TYPE: "int", "bool", "seq", a pair
    `{"pair": [T1, T2]}` with T1, T2 each one of int/bool/seq (SPEC.md
    "Pairs", 2026-09-10): no pair of pairs, no seq of pairs, no pair of
    three; or `{"seq": "seq"}` (SPEC.md "Nested sequences", 2026-09-10),
    one level only -- the value under "seq" must be the literal string
    "seq" and nothing else, so `{"seq": {"seq": "seq"}}` (three levels) and
    `{"seq": {"pair": [...]}}` (a seq of pairs) are both refused here, by
    name, exactly as the SPEC says v1 does not have them. Anything else (an
    unknown string, a malformed dict, a pair whose own component is itself
    a dict) is refused here rather than left for a KeyError or a silent
    pass three checks later."""
    if t in BASE_TYPES:
        return True
    if isinstance(t, dict) and set(t) == {"pair"}:
        return (isinstance(t["pair"], list) and len(t["pair"]) == 2
                and all(c in BASE_TYPES for c in t["pair"]))
    return isinstance(t, dict) and t == {"seq": "seq"}


def _ty(e, env, funs, ver, errs, bound, expect=None):
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
    if "bool" in e:
        if ver == 0:
            _e(errs, "bool literal in a v0 task", "bool-lit-v1")
        return "bool"
    if "var" in e:
        t = env.get(e["var"])
        if t is None:
            _e(errs, f"unbound var {e['var']}", "unbound")
        return t
    if "ite" in e or "forall" in e or "exists" in e or "call" in e:
        if ver == 0:
            _e(errs, "v1 expression form in a v0 task", "v1-expr-v0")
    if "ite" in e:
        c = e["ite"]
        if _ty(c["cond"], env, funs, ver, errs, bound) != "bool":
            _e(errs, "ite condition is not bool", "bool-cond")
        a = _ty(c["then"], env, funs, ver, errs, bound, expect)
        b = _ty(c["else"], env, funs, ver, errs, bound, expect)
        if a != b:
            _e(errs, f"ite branches differ: {a} vs {b}", "ite-branches")
        return a
    if "forall" in e or "exists" in e:
        q = e["forall"] if "forall" in e else e["exists"]
        v = q["var"]
        if v in env or v in bound:
            _e(errs, f"bound var {v} shadows a name in scope", "quant-shadow")
        for side in ("lo", "hi"):
            if _ty(q[side], env, funs, ver, errs, bound) != "int":
                _e(errs, f"quantifier {side} is not int", "quant-bounds")
        sub = dict(env)
        sub[v] = "int"
        if _ty(q["body"], sub, funs, ver, errs, bound | {v}) != "bool":
            _e(errs, "quantifier body is not bool", "quant-body")
        return "bool"
    if "call" in e:
        c = e["call"]
        f = funs.get(c["fun"])
        if f is None:
            _e(errs, f"call of unknown fun {c['fun']}", "call-unknown")
            return None
        if len(f["params"]) != len(c["args"]):
            _e(errs, f"arity mismatch calling {c['fun']}", "call-arity")
        for p, a in zip(f["params"], c["args"]):
            if _ty(a, env, funs, ver, errs, bound, p["type"]) != p["type"]:
                _e(errs, f"argument type mismatch calling {c['fun']}", "call-argtype")
        return f["result"]
    op = e["op"]
    ok = V0_OPS if ver == 0 else V1_OPS
    if op not in ok:
        _e(errs, f"operator {op!r} not in v{ver}", "op-unknown")
        return None
    args = e.get("args", [])
    if op in UNARY and len(args) != 1:
        _e(errs, f"{op} takes one argument", "op-arity")
    if op in TERNARY and len(args) != 3:
        _e(errs, f"{op} takes three arguments", "op-arity")
    if op == "split":
        # SPEC.md "The string library": split(s) and split(s, c), two
        # arities of one op, neither the plain-binary nor any other group.
        if len(args) not in (1, 2):
            _e(errs, "split takes one or two arguments", "strlib-arity")
    elif (op not in UNARY and op not in NARY and op not in TERNARY
            and op not in VARIADIC and len(args) != 2):
        _e(errs, f"{op} takes two arguments", "op-arity")
    if op in NARY and len(args) < 2:
        _e(errs, f"{op} needs at least two arguments", "op-arity")
    ts = [_ty(a, env, funs, ver, errs, bound) for a in args]
    NESTED = {"seq": "seq"}
    if op == "seq":
        # SPEC.md "Sequences: literals, concatenation, slices": [e1, ..., en]
        # of ints, [] included. SPEC.md "Nested sequences" (2026-09-10)
        # makes this polymorphic: elements all int is a plain seq, elements
        # all seq (rows) is a seq<seq>; [] has no element to type from, so
        # it takes `expect` when the caller has one (a var/assign/return/
        # ite/call context) and falls back to plain seq otherwise, exactly
        # the pre-nested behaviour.
        if not ts:
            return expect if expect in ("seq", NESTED) else "seq"
        if all(t == "int" for t in ts):
            return "seq"
        if all(t == "seq" for t in ts):
            return NESTED
        _e(errs, "seq literal elements must be all int or all seq "
                "(no mixing, no pair or nested-seq rows)", "seq-lit-mixed")
        return "seq"
    if op == "slice":
        if ts[0] not in ("seq", NESTED) or ts[1] != "int" or ts[2] != "int":
            _e(errs, "slice wants (seq or seq<seq>, int, int)", "slice-types")
            return "seq"
        return ts[0]
    if op == "+" and len(ts) == 2 and ts[0] == ts[1] and ts[0] in ("seq", NESTED):
        # s + t on two seqs (or two nested seqs, SPEC.md "Nested sequences")
        # is concatenation, the same polymorphism as ==.
        return ts[0]
    if op == "len":
        if ts[0] not in ("seq", NESTED):
            _e(errs, "len of a non-seq", "len-nonseq")
        return "int"
    if op == "at":
        # SPEC.md "Nested sequences": at(m, i) on a seq<seq> gives a row
        # (a seq), where at(s, i) on a plain seq gives an int.
        if ts[1] != "int" or ts[0] not in ("seq", NESTED):
            _e(errs, "at wants (seq or seq<seq>, int)", "at-types")
            return None
        return "int" if ts[0] == "seq" else "seq"
    if op == "update":
        # SPEC.md "Sequences as values": s[i := v] is (seq, int, int) ->
        # seq; SPEC.md "Nested sequences" (2026-09-10): m[i := r] on a
        # seq<seq> takes a ROW (a seq) as the third argument, not an int.
        if ts[1] != "int":
            _e(errs, "update index must be int", "update-types")
        if ts[0] == "seq":
            if ts[2] != "int":
                _e(errs, "update wants (seq, int, int)", "update-types")
            return "seq"
        if ts[0] == NESTED:
            if ts[2] != "seq":
                _e(errs, "update wants (seq<seq>, int, seq) for the row", "update-types")
            return NESTED
        _e(errs, "update wants (seq or seq<seq>, int, element)", "update-types")
        return "seq"
    if op == "fill":
        # seq(n, v): v: int gives a seq, v: seq (a row) gives a seq<seq>
        # (SPEC.md "Nested sequences", 2026-09-10).
        if ts[0] != "int":
            _e(errs, "fill count must be int", "fill-types")
        if ts[1] == "int":
            return "seq"
        if ts[1] == "seq":
            return NESTED
        _e(errs, "fill wants (int, int) or (int, seq) for the row", "fill-types")
        return "seq"
    if op == "pair":
        # SPEC.md "Pairs" (2026-09-10): (e1, e2), typed from its operands;
        # T1, T2 must each be int, bool or seq. There is no way to spell a
        # "seq of pairs" as a type in t (seq is not parameterised), so the
        # only shape to refuse here is a pair of pairs, one level at a time:
        # a pair nested as either operand already failed this same check
        # when IT was typed, so ts[0]/ts[1] not in BASE_TYPES catches it.
        if ts[0] not in BASE_TYPES or ts[1] not in BASE_TYPES:
            _e(errs, "pair components must be int, bool or seq "
                    "(no pair of pairs, no pair of three)", "pair-types")
        return {"pair": ts}
    if op in ("fst", "snd"):
        # p.0 / p.1: SPEC.md "Pairs". Only a pair operand is defined; a
        # non-pair operand (including a pair-of-something gone wrong above,
        # which types as None or a bad dict) is refused with a clear reason
        # rather than an IndexError three lines from now.
        t0 = ts[0]
        if not (isinstance(t0, dict) and set(t0) == {"pair"}):
            _e(errs, f"{op} wants a pair operand, found {t0!r}", "proj-nonpair")
            return None
        return t0["pair"][0 if op == "fst" else 1]
    if op in STRLIB_OPS:
        # SPEC.md "The string library" (2026-09-11): every member's
        # signature, seq/int/seq<seq> per the table there. `split` is the
        # only member with two arities, seq -> seq<seq> at one argument or
        # (seq, int) -> seq<seq> at two. Arity first, so a call with too
        # few or too many arguments is a refusal and never an IndexError
        # (the core's adversarial check found the crash, 2026-09-11).
        want = {"split": (1, 2), "join": (2,), "tostr": (1,), "count": (2,),
                "find": (2,), "strip": (1,), "lstrip": (1,), "rstrip": (1,),
                "replace": (3,), "lower": (1,), "upper": (1,), "isdigit": (1,),
                "isalpha": (1,), "isupper": (1,), "islower": (1,),
                "startswith": (2,), "endswith": (2,)}[op]
        if len(ts) not in want:
            _e(errs, f"{op} wants {' or '.join(str(w) for w in want)} "
                    f"argument(s), found {len(ts)}", "strlib-arity")
            return {"split": NESTED, "join": "seq", "tostr": "seq", "count": "int",
                    "find": "int", "replace": "seq"}.get(op, "seq" if op in
                    ("strip", "lstrip", "rstrip", "lower", "upper") else "bool")
        if op == "split":
            if len(ts) == 1:
                if ts[0] != "seq":
                    _e(errs, "split wants a seq", "strlib-types")
            elif ts[0] != "seq" or ts[1] != "int":
                _e(errs, "split wants (seq, int)", "strlib-types")
            return NESTED
        if op == "join":
            if ts[0] != NESTED or ts[1] != "seq":
                _e(errs, "join wants (seq<seq>, seq)", "strlib-types")
            return "seq"
        if op == "tostr":
            if ts[0] != "int":
                _e(errs, "tostr wants an int", "strlib-types")
            return "seq"
        if op in ("count", "find"):
            if ts[0] != "seq" or ts[1] != "seq":
                _e(errs, f"{op} wants (seq, seq)", "strlib-types")
            return "int"
        if op in ("strip", "lstrip", "rstrip", "lower", "upper"):
            if ts[0] != "seq":
                _e(errs, f"{op} wants a seq", "strlib-types")
            return "seq"
        if op == "replace":
            if ts[0] != "seq" or ts[1] != "seq" or ts[2] != "seq":
                _e(errs, "replace wants (seq, seq, seq)", "strlib-types")
            return "seq"
        if op in ("isdigit", "isalpha", "isupper", "islower"):
            if ts[0] != "seq":
                _e(errs, f"{op} wants a seq", "strlib-types")
            return "bool"
        if ts[0] != "seq" or ts[1] != "seq":       # startswith, endswith
            _e(errs, f"{op} wants (seq, seq)", "strlib-types")
        return "bool"
    if op in ("+", "-", "*", "neg", "div", "mod"):
        if any(t != "int" for t in ts):
            _e(errs, f"{op} over non-int", "arith-int")
        return "int"
    if op in ("<", "<=", ">", ">="):
        if any(t != "int" for t in ts):
            _e(errs, f"{op} is int-only (SPEC.md gate 1)", "cmp-int")
        return "bool"
    if op in ("==", "!="):
        # Two seqs compare extensionally since SPEC.md "Sequences as
        # values"; two pairs compare componentwise since SPEC.md "Pairs"
        # (2026-09-10), "the polymorphic == again" -- dict equality on the
        # two type dicts already refuses a `==` across two DIFFERENT pair
        # types (a pair of (int, int) against a pair of (bool, int)), same
        # as it refuses int against seq.
        if ts[0] != ts[1]:
            # SPEC.md "Nested sequences" (2026-09-10): a bare `[]` with no
            # hint types "seq" by default (the `op == "seq"` arm above);
            # against a seq<seq>-typed other side that default is not a
            # real type error, so an operand that IS the empty-literal AST
            # node is let through as the empty nested seq it plainly is,
            # rather than requiring a caller-supplied `expect` at every
            # `==` site (`==` has no declared type of its own to hint with).
            def _empty_lit(a, t):
                return t == "seq" and a.get("op") == "seq" and not a.get("args")
            zero, one = ts[0] == NESTED and _empty_lit(args[1], ts[1]), \
                       ts[1] == NESTED and _empty_lit(args[0], ts[0])
            if not (zero or one):
                _e(errs, f"{op} wants two ints, two bools, two seqs, "
                       f"two nested seqs, or two pairs of the same type", "eq-types")
        return "bool"
    if any(t != "bool" for t in ts):
        _e(errs, f"{op} over non-bool", "bool-op")
    return "bool"


def _self_calls(e, name) -> bool:
    if isinstance(e, dict):
        if "call" in e and e["call"]["fun"] == name:
            return True
        return any(_self_calls(v, name) for v in e.values())
    if isinstance(e, list):
        return any(_self_calls(v, name) for v in e)
    return False


def check_wf(task: dict) -> list[str]:
    errs: list[str] = []
    ver = task["t"]
    if not NAME_RE.match(task["name"]):
        _e(errs, "bad task name", "name")
    if len(task["returns"]) != 1:
        _e(errs, "exactly one return value (SPEC.md v0 and v1)", "one-return")
    if not task["ensures"]:
        _e(errs, "ensures must be non-empty", "ensures-nonempty")
    funs = {f["name"]: f for f in task.get("spec_funs", [])}
    if ver == 0 and (funs or "decreases" in task or "gate" in task):
        _e(errs, "v1 field in a v0 task", "v0-frozen")
    penv = {p["name"]: p["type"] for p in task["params"]}
    if ver == 0 and any(t != "int" for t in penv.values()):
        _e(errs, "v0 has int only", "v0-int-only")
    for p in task["params"]:
        if not _valid_type(p["type"]):
            _e(errs, f"param {p['name']} has an invalid type: {p['type']!r}", "valid-type")
    for r in task["returns"]:
        if not _valid_type(r["type"]):
            _e(errs, f"return {r['name']} has an invalid type: {r['type']!r}", "valid-type")
    for i, f in enumerate(task.get("spec_funs", [])):
        fenv = {p["name"]: p["type"] for p in f["params"]}
        earlier = {g["name"]: g for g in task["spec_funs"][:i]}
        earlier[f["name"]] = f              # self-recursion is allowed
        if _ty(f["decreases"], fenv, earlier, ver, errs, set()) != "int":
            _e(errs, f"spec_fun {f['name']} decreases is not int", "spec-fun-decreases-int")
        if _ty(f["body"], fenv, earlier, ver, errs, set()) != f["result"]:
            _e(errs, f"spec_fun {f['name']} body type != result", "spec-fun-body-type")
    for e in task.get("requires", []):
        if _ty(e, penv, funs, ver, errs, set()) != "bool":
            _e(errs, "requires clause is not bool", "requires-bool")
    ret = task["returns"][0]
    eenv = dict(penv)
    eenv[ret["name"]] = ret["type"]
    for e in task["ensures"]:
        if _ty(e, eenv, funs, ver, errs, set()) != "bool":
            _e(errs, "ensures clause is not bool", "ensures-bool")
    if _self_calls(task["ensures"], task["name"]):
        _e(errs, "ensures references the task name (SPEC.md gate 3)", "no-self-in-ensures")
    selfrec = _self_calls(task["body"], task["name"])
    if selfrec and "decreases" not in task:
        _e(errs, "self-recursive body without a task decreases", "decreases-selfcall")
    if not selfrec and "decreases" in task:
        _e(errs, "task decreases without a self-call", "decreases-selfcall")
    bfuns = dict(funs)
    if selfrec:
        bfuns[task["name"]] = {"params": task["params"],
                               "result": ret["type"], "body": None,
                               "decreases": None}
    _check_stmts(task["body"], dict(eenv), bfuns, ver, errs, {ret["name"]})
    _check_returns(task["body"], ret["name"], errs)
    return errs


def _check_returns(body, rname, errs):
    """Every `return` names the task's return variable, never a local that
    happens to be assignable in scope (SPEC.md Early exit)."""
    for s in body:
        if "return" in s and s["return"][0] != rname:
            _e(errs, f"return names {s['return'][0]}, not the task's return {rname}",
               "return-name")
        elif "if" in s:
            _check_returns(s["if"]["then"], rname, errs)
            _check_returns(s["if"]["else"], rname, errs)
        elif "while" in s:
            _check_returns(s["while"]["body"], rname, errs)


def _check_stmts(body, env, funs, ver, errs, assignable):
    for s in body:
        if "assign" in s:
            n, e = s["assign"]
            if n not in assignable:
                _e(errs, f"assign to {n}, not a return or local", "assign-target")
            t = _ty(e, env, funs, ver, errs, set(), env.get(n))
            if t != env.get(n):
                _e(errs, f"assign {n}: {t} into {env.get(n)}", "assign-type")
        elif "var" in s:
            if ver == 0:
                _e(errs, "local in a v0 task", "local-v0")
            d = s["var"]
            if d["name"] in env:
                _e(errs, f"local {d['name']} shadows a name in scope", "local-shadow")
            if not _valid_type(d["type"]):
                _e(errs, f"local {d['name']} has an invalid type: "
                       f"{d['type']!r}", "valid-type")
            if _ty(d["init"], env, funs, ver, errs, set(), d["type"]) != d["type"]:
                _e(errs, f"local {d['name']} init type mismatch", "assign-type")
            env[d["name"]] = d["type"]
            assignable.add(d["name"])
        elif "if" in s:
            c = s["if"]
            if _ty(c["cond"], env, funs, ver, errs, set()) != "bool":
                _e(errs, "if condition is not bool", "bool-cond")
            _check_stmts(c["then"], dict(env), funs, ver, errs, set(assignable))
            _check_stmts(c["else"], dict(env), funs, ver, errs, set(assignable))
        elif "while" in s:
            if ver == 0:
                _e(errs, "while in a v0 task", "while-v0")
            w = s["while"]
            if _ty(w["cond"], env, funs, ver, errs, set()) != "bool":
                _e(errs, "loop condition is not bool", "bool-cond")
            if "decreases" not in w:
                _e(errs, "loop without decreases (SPEC.md gate 2)", "loop-decreases")
            elif _ty(w["decreases"], env, funs, ver, errs, set()) != "int":
                _e(errs, "loop decreases is not int", "loop-decreases")
            for inv in w.get("invariants", []):
                if _ty(inv, env, funs, ver, errs, set()) != "bool":
                    _e(errs, "loop invariant is not bool", "loop-invariant-bool")
            _check_stmts(w["body"], dict(env), funs, ver, errs, set(assignable))
        elif "return" in s:
            if ver == 0:
                _e(errs, "return in a v0 task", "return-v0")
            n, e = s["return"]
            if n not in assignable:
                _e(errs, f"return names {n}, not the task's return", "return-name")
            t = _ty(e, env, funs, ver, errs, set(), env.get(n))
            if t != env.get(n):
                _e(errs, f"return {n}: {t} into {env.get(n)}", "assign-type")
            if s is not body[-1]:
                _e(errs, "statement after return is unreachable (SPEC.md Early exit)",
                   "return-unreachable")
        else:
            _e(errs, f"t has no statement {sorted(s)!r}", "unknown-stmt")
