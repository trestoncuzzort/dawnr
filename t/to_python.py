#!/usr/bin/env python3
"""t/to_python.py -- a proved `t` answer handed back as a Python function, checked against `t` itself (2026-10-05).

    import to_python
    src, fn = to_python.translate(task, examples)        # readable Python, the question's own types at the boundary
    report = to_python.check(task, src, fn, examples)    # {"agrees": bool, "inputs": N, ...}

What the provers prove is the `t` program. This writes the same program in Python and checks the translation, rather
than proving the translator: every answer's Python is run beside `t`'s reference interpreter (t/interp.py, whose
semantics every prover's lowering follows) on the question's own tests and on up to N inputs from the interpreter's
own bounded domain that satisfy the program's `requires`, and the Python is shown only when every one agrees
(differential testing: two implementations, the same inputs, any disagreement a bug; research receipt 3a0219b3d74f).
Dafny's own Python backend is the other route (a verified compiler's output, verbose and needing Dafny's runtime);
this one is meant to be read.

Faithful by construction where it matters: inside the function, values are the interpreter's own (ints, bools,
tuples for sequences, frozensets for sets, (a, b) for pairs); integer division and modulo are Euclidean, as `t`
defines them, not Python's floor division; the string library's operations are the interpreter's own functions,
copied in by source. Only the boundary converts: a sequence the question's tests pass as a Python `str` arrives as
its code points and leaves as a `str`, a `list` arrives as a tuple and leaves as a list.

The proof covers the inputs the program's `requires` admits, of the types it declares, and nothing else, so the
Python refuses the rest instead of answering it: a `ValueError` outside the `requires`, a `TypeError` for an
argument that is not of the declared type ("a runtime wrapper enforces the proved input domain",
internal/ENTERPRISE-PLAN-2026-09-19.md; Meyer's design by contract, where a violated precondition is the caller's
fault and is reported at the call). The check runs the guard beside the interpreter too: on drawn inputs the
`requires` excludes, the Python must refuse.

Not translated (the answer keeps its `t` form only): datatypes (constructors and `match`), which no answer has
needed yet.
"""
from __future__ import annotations

import inspect
import json
import keyword
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import interp                                                   # noqa: E402
import surface                                                  # noqa: E402

INDENT = "    "
_RENAME_SUFFIX = "_"
# the string library: interp's own implementations, copied by source, so the semantics are the same functions
_STR_HELPERS = {
    "split": ["_str_split_ws", "_str_split_sep"], "join": ["_str_join"], "tostr": ["_str_tostr"],
    "count": ["_str_count"], "find": ["_str_find"], "strip": ["_str_strip"], "lstrip": ["_str_strip"],
    "rstrip": ["_str_strip"], "replace": ["_str_replace"], "lower": ["_str_lower", "_is_upper_letter"],
    "upper": ["_str_upper", "_is_lower_letter"], "isdigit": ["_str_isdigit"],
    "isalpha": ["_str_isalpha", "_is_upper_letter", "_is_lower_letter"],
    "isupper": ["_str_isupper", "_is_upper_letter", "_is_lower_letter"],
    "islower": ["_str_islower", "_is_upper_letter", "_is_lower_letter"],
    "startswith": ["_str_startswith"], "endswith": ["_str_endswith"],
}
_BINOP = {"+": "+", "-": "-", "*": "*", "==": "==", "!=": "!=", "<": "<", "<=": "<=", ">": ">", ">=": ">="}


class Unsupported(Exception):
    """A construct this translation does not write; the answer is shown in `t` only."""


def _ident(name: str) -> str:
    # only a hard keyword cannot name a variable or function; a soft keyword (match, case, type) can, and a renamed
    # `match` would no longer be the function the question's tests call
    if keyword.iskeyword(name) or name.startswith("_t_"):
        return name + _RENAME_SUFFIX
    return name


class _Writer:
    def __init__(self, task: dict):
        self.task = task
        self.helpers: list[str] = []          # interp function names to copy in
        self.need_divmod = False
        self.fun_names = {f["name"] for f in task.get("spec_funs", [])} | {m["name"] for m in task.get("methods", [])}
        self.self_name = task["name"]

    def _need(self, names: list[str]) -> None:
        for n in names:
            if n not in self.helpers:
                self.helpers.append(n)

    # ---------------------------------------------------------------- expressions --
    def expr(self, e: dict) -> str:
        if "int" in e:
            return repr(e["int"])
        if "bool" in e:
            return "True" if e["bool"] else "False"
        if "var" in e:
            return _ident(e["var"])
        if "ite" in e:
            c = e["ite"]
            return f"({self.expr(c['then'])} if {self.expr(c['cond'])} else {self.expr(c['else'])})"
        if "ctor" in e or "match" in e:
            raise Unsupported("datatypes")
        if "comp" in e:
            # SPEC.md "Comprehensions (v1)" (2026-10-06): Python's own, as a tuple
            c = e["comp"]
            v = _ident(c["var"])
            src = (f"range({self.expr(c['lo'])}, {self.expr(c['hi'])})" if "lo" in c else self.expr(c["seq"]))
            cond = "" if c["cond"] == {"bool": True} else f" if {self.expr(c['cond'])}"
            return f"tuple({self.expr(c['body'])} for {v} in {src}{cond})"
        if "forall" in e or "exists" in e:
            kind = "forall" if "forall" in e else "exists"
            q = e[kind]
            fn = "all" if kind == "forall" else "any"
            v = _ident(q["var"])
            return f"{fn}({self.expr(q['body'])} for {v} in range({self.expr(q['lo'])}, {self.expr(q['hi'])}))"
        if "call" in e:
            c = e["call"]
            name = c["fun"]
            args = ", ".join(self.expr(a) for a in c["args"])
            if name == self.self_name:
                return f"_t_core({args})"
            if name not in self.fun_names:
                raise Unsupported(f"a call to {name}, which the task does not define")
            return f"_t_fn_{name}({args})"
        op = e.get("op")
        a = e.get("args", [])
        x = [self.expr(v) for v in a]
        if op == "and":
            return "(" + " and ".join(x) + ")"
        if op == "or":
            return "(" + " or ".join(x) + ")"
        if op == "implies":
            return f"((not {x[0]}) or {x[1]})"
        if op == "not":
            return f"(not {x[0]})"
        if op == "neg":
            return f"(-{x[0]})"
        if op == "len":
            return f"len({x[0]})"
        if op == "at":
            return f"{x[0]}[{x[1]}]"
        if op == "update":
            return f"_t_update({x[0]}, {x[1]}, {x[2]})"
        if op == "fill":
            return f"(({x[1]},) * {x[0]})"
        if op == "seq":
            return "(" + "".join(v + ", " for v in x) + ")" if x else "()"
        if op == "slice":
            return f"{x[0]}[{x[1]}:{x[2]}]"
        if op == "pair":
            return f"({x[0]}, {x[1]})"
        if op == "fst":
            return f"{x[0]}[0]"
        if op == "snd":
            return f"{x[0]}[1]"
        if op == "set":
            return "frozenset((" + "".join(v + ", " for v in x) + "))"
        if op == "mapdisp":
            # SPEC.md "Maps (v1)" (2026-10-06): Python's own dict (the rightmost of two equal keys wins there too)
            return "{" + ", ".join(f"{x[i]}: {x[i + 1]}" for i in range(0, len(x), 2)) + "}"
        if op == "keys":
            return f"frozenset({x[0]}.keys())"
        if op == "remove":
            return f"_t_mapdel({x[0]}, {x[1]})"
        if op == "in":
            return f"({x[0]} in {x[1]})"
        # SPEC.md "The library (v1)" (2026-10-06): Python's own where it has one, a helper where it does not
        if op in ("min", "max", "abs", "sum", "any", "all"):
            return f"{op}({', '.join(x)})"   # Python's own, at either arity of min/max (SPEC.md "Reductions (v1)")
        if op == "toset":
            return f"frozenset({x[0]})"
        if op == "gcd":
            return f"_t_gcd({x[0]}, {x[1]})"
        if op == "pow":
            return f"({x[0]} ** {x[1]})"
        if op == "isqrt":
            return f"_t_isqrt({x[0]})"
        if op == "rev":
            return f"{x[0]}[::-1]"
        if op == "sort":
            return f"tuple(sorted({x[0]}))"   # SPEC.md "Sorting (v1)" (2026-10-06)
        if op == "card":
            return f"len({x[0]})"
        if op == "union":
            return f"({x[0]} | {x[1]})"
        if op == "inter":
            return f"({x[0]} & {x[1]})"
        if op == "diff":
            return f"({x[0]} - {x[1]})"
        if op in ("div", "mod"):
            self.need_divmod = True
            return f"_t_{op}({x[0]}, {x[1]})"
        if op in _STR_HELPERS:
            self._need(_STR_HELPERS[op])
            if op == "split":
                return f"_str_split_ws({x[0]})" if len(x) == 1 else f"_str_split_sep({x[0]}, {x[1]})"
            if op == "strip":
                return f"_str_strip({x[0]}, True, True)"
            if op == "lstrip":
                return f"_str_strip({x[0]}, True, False)"
            if op == "rstrip":
                return f"_str_strip({x[0]}, False, True)"
            return f"_str_{op}({', '.join(x)})"
        if op in _BINOP:
            return f"({x[0]} {_BINOP[op]} {x[1]})"
        raise Unsupported(f"operator {op!r}")

    # ----------------------------------------------------------------- statements --
    def stmts(self, body: list, depth: int) -> list[str]:
        pad = INDENT * depth
        out: list[str] = []
        for s in body:
            if "assign" in s:
                name, e = s["assign"]
                out.append(f"{pad}{_ident(name)} = {self.expr(e)}")
            elif "var" in s:
                d = s["var"]
                out.append(f"{pad}{_ident(d['name'])} = {self.expr(d['init'])}")
            elif "return" in s:
                _name, e = s["return"]
                out.append(f"{pad}return {self.expr(e)}")
            elif "break" in s or "continue" in s:
                out.append(f"{pad}{'break' if 'break' in s else 'continue'}")   # SPEC.md "Early exits (v1)"
            elif "if" in s:
                c = s["if"]
                out.append(f"{pad}if {self.expr(c['cond'])}:")
                out += self.stmts(c["then"], depth + 1) or [f"{pad}{INDENT}pass"]
                if c.get("else"):
                    out.append(f"{pad}else:")
                    out += self.stmts(c["else"], depth + 1)
            elif "while" in s:
                w = s["while"]
                for inv in w.get("invariants", []):
                    out.append(f"{pad}# invariant: {surface.pexpr(inv)}")
                if w.get("decreases") is not None:
                    out.append(f"{pad}# decreases: {surface.pexpr(w['decreases'])}")
                out.append(f"{pad}while {self.expr(w['cond'])}:")
                out += self.stmts(w["body"], depth + 1) or [f"{pad}{INDENT}pass"]
            elif "lemma" in s:
                continue                                        # ghost: erased at run time (SPEC.md "Lemmas (v1)")
            else:
                raise Unsupported(f"statement {list(s)[0]!r}")
        return out

    def function(self, py_name: str, params: list, body: list, ret: str, depth: int = 0) -> list[str]:
        pad = INDENT * depth
        ps = ", ".join(_ident(p["name"]) for p in params)
        lines = [f"{pad}def {py_name}({ps}):"]
        lines += self.stmts(body, depth + 1)
        lines.append(f"{pad}{INDENT}return {_ident(ret)}")
        return lines


# ------------------------------------------------------------------ the boundary --

def _literal_kind(node) -> str:
    """How a test writes one value: "str", "char" (a one-character string), "strs" (a list of strings), "list",
    else "value"."""
    import ast
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return "char" if len(node.value) == 1 else "str"
    if isinstance(node, (ast.List, ast.Tuple)):
        if any(isinstance(x, ast.Constant) and isinstance(x.value, str) for x in node.elts):
            return "strs"
        return "list"
    return "value"


def _containers(node) -> tuple[str, ...]:
    """How a test writes a sequence at each depth, "list" or "tuple", down its first elements: `[(1, 2), (3, 4)]`
    is ("list", "tuple"). () for anything that is not a list or a tuple."""
    import ast
    out = []
    while isinstance(node, (ast.List, ast.Tuple)):
        out.append("tuple" if isinstance(node, ast.Tuple) else "list")
        node = node.elts[0] if node.elts else None
    return tuple(out)


def _merge(a: str, b: str) -> str:
    rank = {"value": 0, "list": 1, "char": 2, "str": 3, "strs": 4}
    return a if rank[a] >= rank[b] else b


def _boundary_kinds(task: dict, tests: list[str]) -> tuple[list[str], str]:
    """For each parameter and for the result, its form at the boundary, from its declared `t` type and from how the
    question's own tests write it (the parsed points no longer tell a string from a list of code points):
    "str" (a seq written as a Python string), "strs" (a seq<seq> written as a list of strings), "char" (an int
    written as a one-character string), "list" (any other seq or seq<seq>), "set", or "value" (as is)."""
    import ast
    seen_in = ["value"] * len(task["params"])
    seen_out = "value"
    out_containers: tuple[str, ...] = ()
    for line in tests or []:
        try:
            node = ast.parse(line.strip()).body[0]
        except (SyntaxError, IndexError):
            continue
        if not (isinstance(node, ast.Assert) and isinstance(node.test, ast.Compare) and node.test.comparators
                and isinstance(node.test.left, ast.Call)):
            continue
        for i, arg in enumerate(node.test.left.args[:len(seen_in)]):
            seen_in[i] = _merge(seen_in[i], _literal_kind(arg))
        seen_out = _merge(seen_out, _literal_kind(node.test.comparators[0]))
        if len(_containers(node.test.comparators[0])) > len(out_containers):
            out_containers = _containers(node.test.comparators[0])   # the deepest writing seen (an empty one says less)

    def form(ttype, seen: str) -> str:
        if ttype == "seq":
            return "str" if seen in ("str", "char") else "list"
        if isinstance(ttype, dict) and "seq" in ttype:          # seq<seq>, stored as {"seq": "seq"}
            return "strs" if seen == "strs" else "list"
        if ttype == "set" or (isinstance(ttype, dict) and "set" in ttype):
            return "set"
        if ttype == "int" and seen == "char":
            return "char"
        return "value"
    ins = [form(p["type"], k) for p, k in zip(task["params"], seen_in)]
    out = form(task["returns"][0]["type"], seen_out)
    # 2026-10-05, the wider reader: a result the tests write with a tuple somewhere (`(0, 4, 5, 1)`, `[(1, 2), (3, 4)]`)
    # leaves in that writing, or Python's == finds the list unequal to the tuple and the question's own test fails
    if "tuple" in out_containers:
        if out == "list":
            out = "shape:" + ",".join(out_containers)
        elif out == "strs" and out_containers[0] == "tuple":
            out = "strs-tuple"
    return ins, out


_IN = {"str": "tuple(ord(c) for c in {v})", "strs": "tuple(tuple(ord(c) for c in x) for x in {v})",
       "char": "ord({v})", "list": "_t_tuple({v})", "set": "frozenset({v})"}
_OUT = {"str": "''.join(chr(c) for c in {v})", "strs": "[''.join(chr(c) for c in x) for x in {v}]",
        "char": "chr({v})", "list": "_t_list({v})", "set": "set({v})", "value": "{v}"}


def _depth(ttype) -> int | None:
    """How deep a parameter's sequences nest: 1 for seq, 2 for seq<seq>; None for a type that is not one of these."""
    if ttype == "seq":
        return 1
    if isinstance(ttype, dict) and ttype.get("seq") == "seq":
        return 2
    return None


def _type_guard(ttype, kind: str, v: str) -> tuple[str, str] | None:
    """(a Python test that the argument is of the declared type as the boundary writes it, its name in words), or
    None for a type the guard does not know and so does not judge."""
    if kind == "str":
        return f"isinstance({v}, str)", "a string"
    if kind == "char":
        return f"isinstance({v}, str) and len({v}) == 1", "a one-character string"
    if kind == "strs":
        return f"isinstance({v}, (list, tuple)) and all(isinstance(x, str) for x in {v})", "a list of strings"
    if kind == "set":
        return f"isinstance({v}, (set, frozenset)) and all(_t_ints(x, 0) for x in {v})", "a set of integers"
    if kind == "list" and _depth(ttype):
        return f"_t_ints({v}, {_depth(ttype)})", "a list of integers" if _depth(ttype) == 1 else "a list of lists of integers"
    if kind == "value" and ttype == "int":
        return f"_t_ints({v}, 0)", "an integer"
    if kind == "value" and ttype == "bool":
        return f"isinstance({v}, bool)", "a boolean"
    return None


def translate(task: dict, tests: list[str] | None = None, fn_name: str | None = None) -> tuple[str, str]:
    """(Python source, the function's name). Raises Unsupported for what it does not write."""
    w = _Writer(task)
    name = _ident(fn_name or task["name"])
    ret = task["returns"][0]["name"]
    core = w.function("_t_core", task["params"], task["body"], ret)
    funs: list[str] = []
    for f in task.get("spec_funs", []):
        ps = ", ".join(_ident(p["name"]) for p in f["params"])
        funs += [f"def _t_fn_{f['name']}({ps}):", f"{INDENT}return {w.expr(f['body'])}", ""]
    for m in task.get("methods", []):
        funs += w.function(f"_t_fn_{m['name']}", m["params"], m["body"], m["returns"][0]["name"]) + [""]
    ins, out = _boundary_kinds(task, tests or [])
    params = [_ident(p["name"]) for p in task["params"]]
    conv_in = []
    for p, decl, kind in zip(params, task["params"], ins):      # the declared types first: nothing was proved for another
        typed = _type_guard(decl["type"], kind, p)
        if typed:
            conv_in += [f"{INDENT}if not ({typed[0]}):",
                        f"{INDENT}{INDENT}raise TypeError({f'{name}: `{p}` must be {typed[1]}; nothing was proved for anything else'!r})"]
    for p, kind in zip(params, ins):
        if kind in _IN:
            conv_in.append(f"{INDENT}{p} = " + _IN[kind].format(v=p))
    requires = [w.expr(c) for c in task.get("requires", [])]
    if requires:                                                # then the `requires`, on the values the program will see
        said = "; ".join(surface.pexpr(c) for c in task["requires"])
        conv_in += [f"{INDENT}if not _t_requires({', '.join(params)}):",
                    f"{INDENT}{INDENT}raise ValueError({f'{name}: this input is outside what was proved (requires {said})'!r})"]
        funs += [f"def _t_requires({', '.join(params)}):", f"{INDENT}try:",
                 f"{INDENT}{INDENT}return " + " and ".join(f"bool({r})" for r in requires),
                 f"{INDENT}except (IndexError, ZeroDivisionError):   # a `requires` with no value here admits nothing",
                 f"{INDENT}{INDENT}return False", ""]
    if out.startswith("shape:"):
        result = f"_t_shape(_t_result, {tuple(out[6:].split(','))!r})"
    elif out == "strs-tuple":
        result = "tuple(''.join(chr(c) for c in x) for x in _t_result)"
    else:
        result = _OUT[out].format(v="_t_result")
    spec = [surface.pexpr(c) for c in task.get("requires", [])], [surface.pexpr(c) for c in task.get("ensures", [])]
    doc = [f'{INDENT}"""The program dawnr proved in `t`, written in Python (checked against `t`, not itself proved).',
           ""]
    doc += [f"{INDENT}requires {r}" for r in spec[0]] + [f"{INDENT}ensures  {e}" for e in spec[1]]
    if spec[0]:
        doc += ["", f"{INDENT}Outside its `requires` it raises ValueError: nothing was proved there."]
    doc += [f'{INDENT}"""']
    lines = [f"def {name}({', '.join(params)}):"] + doc + conv_in
    lines += [f"{INDENT}_t_result = _t_core({', '.join(params)})", f"{INDENT}return {result}", ""]
    lines += core + [""] + funs
    support: list[str] = []
    if any("_t_update(" in l for l in lines):
        support += ["def _t_update(s, i, v):", f"{INDENT}if isinstance(s, dict):", f"{INDENT}{INDENT}return {{**s, i: v}}",
                    f"{INDENT}return s[:i] + (v,) + s[i + 1:]", ""]
    if any("_t_mapdel(" in l for l in lines):
        support += ["def _t_mapdel(m, k):", f"{INDENT}return {{kk: vv for kk, vv in m.items() if kk != k}}", ""]
    if any("_t_gcd(" in l for l in lines):
        support += ["def _t_gcd(a, b):", f"{INDENT}import math", f"{INDENT}return math.gcd(a, b)", ""]
    if any("_t_isqrt(" in l for l in lines):
        support += ["def _t_isqrt(n):", f"{INDENT}import math", f"{INDENT}return math.isqrt(n)", ""]
    if any("_t_tuple(" in l for l in lines):
        support += ["def _t_tuple(v):", f"{INDENT}return tuple(_t_tuple(x) for x in v) if isinstance(v, (list, tuple)) else v", ""]
    if any("_t_ints(" in l for l in lines):
        support += ["def _t_ints(v, depth):", f"{INDENT}if depth == 0:",
                    f"{INDENT}{INDENT}return isinstance(v, int) and not isinstance(v, bool)",
                    f"{INDENT}return isinstance(v, (list, tuple)) and all(_t_ints(x, depth - 1) for x in v)", ""]
    if any("_t_list(" in l for l in lines):
        support += ["def _t_list(v):", f"{INDENT}return [_t_list(x) for x in v] if isinstance(v, tuple) else v", ""]
    if any("_t_shape(" in l for l in lines):
        support += ["def _t_shape(v, kinds):", f"{INDENT}if not isinstance(v, tuple):", f"{INDENT}{INDENT}return v",
                    f"{INDENT}inner = [_t_shape(x, kinds[1:] or kinds[-1:]) for x in v]",
                    f"{INDENT}return tuple(inner) if kinds[0] == \"tuple\" else inner", ""]
    if w.need_divmod:
        support += ["def _t_mod(x, y):", f"{INDENT}return x % abs(y)          # Euclidean, as t defines it (SPEC.md)", "",
                    "def _t_div(x, y):", f"{INDENT}return (x - x % abs(y)) // y", ""]
    helper_src = [inspect.getsource(getattr(interp, h)).rstrip() for h in w.helpers]
    joined = "\n".join(helper_src)
    head = []
    if "_WS" in joined:
        head.append(f"_WS = {interp._WS!r}")
    if "MAX_SEQ" in joined:
        head.append(f"MAX_SEQ = {interp.MAX_SEQ!r}")
    if "Budget" in joined:
        head += ["", "class Budget(Exception):", f"{INDENT}\"\"\"t's length cap: a sequence past MAX_SEQ decides nothing.\"\"\""]
    for src_h in helper_src:
        support += src_h.splitlines() + [""]
    if head:
        support = head + [""] + support
    return "\n".join(lines + support).rstrip() + "\n", name


# --------------------------------------------------------------------- the check --

def _shape(v, kinds: tuple[str, ...]):
    """A t sequence as the tests write it: a list or a tuple at each depth (the function the translation carries)."""
    if isinstance(v, interp.Pair):
        return (_shape(v.a, ()), _shape(v.b, ()))
    if not isinstance(v, tuple):
        return v
    inner = [_shape(x, kinds[1:] or kinds[-1:]) for x in v]
    return tuple(inner) if kinds and kinds[0] == "tuple" else inner


def _t_value_to_py(v, kind: str):
    """An interpreter value as the question's own Python writes it (the boundary's form)."""
    if kind == "str":
        return "".join(chr(c) for c in v)
    if kind == "strs":
        return ["".join(chr(c) for c in x) for x in v]
    if kind == "char":
        return chr(v)
    if kind == "set":
        return set(v)
    if kind == "strs-tuple":
        return tuple("".join(chr(c) for c in x) for x in v)
    if kind.startswith("shape:"):
        return _shape(v, tuple(kind[6:].split(",")))
    if isinstance(v, interp.Pair):
        return (_t_value_to_py(v.a, "value"), _t_value_to_py(v.b, "value"))
    if isinstance(v, tuple):
        return [_t_value_to_py(x, "value") for x in v]
    return v


def _interp_result(task: dict, env: dict):
    funs = interp.funs_of(task, task["body"])
    st = interp.St()
    if not all(interp.ev(c, dict(env), funs, st) for c in task.get("requires", [])):
        return None, "requires"
    env2 = dict(env)
    ret = task["returns"][0]["name"]
    env2[ret] = None
    interp.exec_body(task["body"], env2, funs, st)
    return env2[ret], None


_REFUSES = """
def _t_refuses(f, *args):
    try:
        f(*args)
    except ValueError:
        return True
    return False
"""


def check(task: dict, src: str, fn: str, tests: list[str] | None = None, n: int = 200,
          per_test: int = 3, outside: int = 50) -> dict:
    """Run the translation beside the interpreter, in the sandbox (t/py_sandbox.py), on the question's own tests,
    on up to `n` inputs from the interpreter's own domain that the program's `requires` admits, and on up to
    `outside` that it excludes, which the Python must refuse with a ValueError.
    {"agrees": bool, "inputs": N, "refused": M, "why"?, "first"?: the first assertion that did not pass}."""
    import py_sandbox
    ins, out = _boundary_kinds(task, tests or [])
    names = [(p["name"], p["type"]) for p in task["params"]]
    asserts, refusals = [], []
    for env in interp.domain(task, names, interp.MAX_POINTS):
        if len(asserts) >= n:
            break
        try:
            got, refusal = _interp_result(task, env)
        except (interp.Undef, interp.Budget, RecursionError, ZeroDivisionError):
            continue
        if refusal and len(refusals) < outside:
            try:
                refusals.append(f"assert _t_refuses({fn}, *{[_t_value_to_py(env[p], k) for (p, _t), k in zip(names, ins)]!r})")
            except (ValueError, TypeError, OverflowError):
                pass
        if refusal or got is None:
            continue
        try:
            args = [_t_value_to_py(env[p], k) for (p, _t), k in zip(names, ins)]
            want = _t_value_to_py(got, out)
        except (ValueError, TypeError, OverflowError):
            continue                                            # not a value a Python caller could pass (a bad code point)
        asserts.append(f"assert {fn}(*{args!r}) == {want!r}")
    asserts += [t.strip() for t in tests or [] if t.strip()]
    if not asserts:
        return {"agrees": False, "inputs": 0, "why": "no input to check on"}
    r = py_sandbox.run_tests(src + _REFUSES, asserts + refusals, per_test=per_test)
    ok = r.get("status") == "ran" and bool(r.get("all_pass"))
    if ok:
        return {"agrees": True, "inputs": len(asserts), "refused": len(refusals)}
    first = next((a for a, v in zip(asserts + refusals, r.get("verdicts") or []) if v != "pass"), None)
    return {"agrees": False, "inputs": len(asserts), "refused": len(refusals), "why": json.dumps(r)[:300],
            **({"first": first} if first else {})}
