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

Compound values at the boundary (the values t/typed_values.py reads). The boundary writes a value as the Python
value the test wrote, at the type the program declares:
  - a map is a dict, a tuple of any arity a tuple, a set a set, and a string inside any of them a str;
  - a datatype value is the Python value typed_values read it from: an option's None or the value itself, a record
    the tuple of its fields, one constructor of several the value of its kind.
Inside the function a map is a dict, a tuple a tuple, and a datatype value a tuple of its constructor's name and its
fields. Each position's written form is kept in a small form (`_form`) that `_t_in` and `_t_out` read, in the
generated Python and beside the interpreter alike, so the comparison and the hand-back cross the boundary by the same
code. A value with no faithful writing is refused by name (`Uncarried`): a dict inside a set, a datatype whose
constructors have no fields, or a sequence that the tests write as a list in one test and a tuple in another, where
the result is compared.

Not translated (the answer keeps its `t` form only): a datatype the task does not declare.
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
import typed_values                                             # noqa: E402

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
    # SPEC.md "The string library (v2)" (2026-10-06)
    "index": ["_str_index", "_str_find"], "rfind": ["_str_rfind"], "zfill": ["_str_zfill"],
    "center": ["_str_just"], "ljust": ["_str_just"], "rjust": ["_str_just"],
    "capitalize": ["_str_capitalize", "_str_upper", "_str_lower", "_is_upper_letter", "_is_lower_letter"],
    "swapcase": ["_str_swapcase", "_is_upper_letter", "_is_lower_letter"],
    "title": ["_str_title", "_is_upper_letter", "_is_lower_letter"],
    "isspace": ["_str_isspace"], "isalnum": ["_str_isalnum", "_is_upper_letter", "_is_lower_letter"],
    "splitlines": ["_str_splitlines"], "partition": ["_str_partition3", "_str_find"],
    "isint": ["_str_isint"], "toint": ["_str_toint"],
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
        self.floats = "float" in json.dumps(task)     # SPEC.md "Floats (v1)": a task naming the type or float()
        self.self_name = task["name"]

    def _need(self, names: list[str]) -> None:
        for n in names:
            if n not in self.helpers:
                self.helpers.append(n)

    # ---------------------------------------------------------------- expressions --
    def datatype_expr(self, e: dict) -> str:
        """SPEC.md "Datatypes (v1)" and "(v2): fields": a datatype value is the tuple of its constructor's name and its
        fields (structural equality, as t's), `match` a chain of conditionals that evaluates only the chosen arm, a field
        the position of the name in the constructor that carries it."""
        declared = {d["name"]: d for d in self.task.get("datatypes", []) or []}
        if "ctor" in e:
            c = e["ctor"]
            if c.get("dtype") not in declared or "name" not in c:
                raise Unsupported(f"datatypes: {c.get('dtype')} is not one the task declares")
            return "(" + "".join(v + ", " for v in [repr(c["name"])] + [self.expr(a) for a in c.get("args", [])]) + ")"
        if "match" in e:
            m = e["match"]
            arms = []
            for arm in m["arms"]:
                binders = ", ".join(_ident(b) for b in arm.get("binders", []))
                arms.append((arm["ctor"], f"(lambda {binders}: {self.expr(arm['body'])})(*_t_s[1:{1 + len(arm.get('binders', []))}])"))
            chain = arms[-1][1]                                     # check_wf: one arm for every constructor
            for ctor, body in reversed(arms[:-1]):
                chain = f"({body} if _t_s[0] == {ctor!r} else {chain})"
            return f"(lambda _t_s: {chain})({self.expr(m['scrutinee'])})"
        f = e["field"]
        where: dict = {}
        for d in declared.values():
            for c in d["ctors"]:
                names = [x["name"] for x in c.get("fields") or []]
                if f["name"] in names and where.setdefault(c["name"], names.index(f["name"]) + 1) != names.index(f["name"]) + 1:
                    raise Unsupported(f"datatypes: field {f['name']} at different places in constructors of one name")
        if not where:
            raise Unsupported(f"datatypes: no constructor of the task has the field {f['name']}")
        return f"_t_field({self.expr(f['of'])}, {where!r})"

    def expr(self, e: dict) -> str:
        if "int" in e:
            return repr(e["int"])
        if e.get("op") == "float":
            # SPEC.md "Floats (v1)": a real literal rounded here, exactly as t rounds it (Python's float of a
            # Fraction is correctly rounded); an int converted at run time, an overflow raising
            a0 = e["args"][0]
            if "rat" in a0:
                import fractions
                v = float(fractions.Fraction(a0["rat"][0], a0["rat"][1]))
                return repr(v)
            return f"_t_tofloat({self.expr(a0)})"
        if e.get("op") == "sqrt":
            return f"_t_sqrt({self.expr(e['args'][0])})"
        if "bool" in e:
            return "True" if e["bool"] else "False"
        if "var" in e:
            return _ident(e["var"])
        if "ite" in e:
            c = e["ite"]
            return f"({self.expr(c['then'])} if {self.expr(c['cond'])} else {self.expr(c['else'])})"
        if "ctor" in e or "match" in e or "field" in e:
            return self.datatype_expr(e)
        if "lam" in e:
            # SPEC.md "Higher-order calls (v1)" (2026-10-06): Python's own lambda
            return "(lambda %s: %s)" % (", ".join(_ident(v) for v in e["lam"]["vars"]), self.expr(e["lam"]["body"]))
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
            if "in" in q:
                # SPEC.md "Quantifiers over a collection": Python iterates a set or a list directly
                return f"{fn}({self.expr(q['body'])} for {v} in {self.expr(q['in'])})"
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
        if op == "tuple":
            return "(" + "".join(v + ", " for v in x) + ")"       # SPEC.md "Compositional types (v1)": three or more
        if op == "proj":
            return f"{x[0]}[{x[1]}]"
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
        if op == "fold":
            return f"__import__('functools').reduce({x[0]}, {x[2]}, {x[1]})"   # SPEC.md "Higher-order calls (v1)"
        if op == "sort_by":
            return f"tuple(sorted({x[0]}, key={x[1]}))"
        if op in ("max_by", "min_by"):
            return f"{op[:3]}({x[0]}, key={x[1]})"
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
        if op == "div" and self.floats:
            return f"_t_fdiv({x[0]}, {x[1]})"      # SPEC.md "Floats (v1)": a float's quotient, or an int's Euclidean one
        if op in ("div", "mod"):
            self.need_divmod = True
            return f"_t_{op}({x[0]}, {x[1]})"
        if op in _STR_HELPERS:
            self._need(_STR_HELPERS[op])
            if op == "split":
                if len(x) == 1:
                    return f"_str_split_ws({x[0]})"
                self._need(["_str_split_str"])   # SPEC.md "The string library (v2)": by the separator's kind
                return f"(_str_split_sep({x[0]}, {x[1]}) if isinstance({x[1]}, int) else _str_split_str({x[0]}, {x[1]}))"
            if op in ("strip", "lstrip", "rstrip"):
                left, right = op != "rstrip", op != "lstrip"
                if len(x) == 2:
                    self._need(["_str_strip_chars"])
                    return f"_str_strip_chars({x[0]}, {x[1]}, {left}, {right})"
                return f"_str_strip({x[0]}, {left}, {right})"
            if op in ("center", "ljust", "rjust"):
                fill = x[2] if len(x) == 3 else "32"
                return f"_str_just({x[0]}, {x[1]}, {fill}, {op[0]!r})"
            if op == "partition":
                return f"_str_partition3({x[0]}, {x[1]})"
            return f"_str_{op}({', '.join(x)})"
        if op in _BINOP:
            if self.floats and op in ("+", "-", "*"):
                return f"_t_f({x[0]} {_BINOP[op]} {x[1]})"   # SPEC.md "Floats (v1)": no value unless finite
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
            elif "aset" in s:
                # SPEC.md "Heap (v1)": the caller's list, one element written; a negative index is t's undefined
                # write, not Python's write from the end
                name, i, e = s["aset"]
                out.append(f"{pad}_t_aset({_ident(name)}, {self.expr(i)}, {self.expr(e)})")
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
            elif "par" in s:
                # SPEC.md "Concurrency (v1)": each iteration a call on a thread pool; `par-race` gives each one its own
                # element and its own locals, so the threads share nothing they write
                w = s["par"]
                self.par_k = getattr(self, "par_k", 0) + 1
                fn = f"_t_iter{self.par_k}"
                for inv in w.get("invariants", []):
                    out.append(f"{pad}# invariant: {surface.pexpr(inv)}")
                out.append(f"{pad}def {fn}({_ident(w['var'])}):")
                out += self.stmts(w["body"], depth + 1) or [f"{pad}{INDENT}pass"]
                out.append(f"{pad}_t_par({fn}, {self.expr(w['lo'])}, {self.expr(w['hi'])})")
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
    nodes_in: list[list] = [[] for _ in task["params"]]       # every test's own writing, for the typed positions
    nodes_out: list = []
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
            nodes_in[i].append(arg)
        nodes_out.append(node.test.comparators[0])
        seen_out = _merge(seen_out, _literal_kind(node.test.comparators[0]))
        if len(_containers(node.test.comparators[0])) > len(out_containers):
            out_containers = _containers(node.test.comparators[0])   # the deepest writing seen (an empty one says less)

    def form(ttype, seen: str) -> str:
        if ttype == "array":
            return "array"          # SPEC.md "Heap (v1)": the caller's own list, written in place, never copied
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
    # A position the typed reader read (t/typed_values.py) that the boundary above does not carry is written by a form
    # of its declared type and of how the tests write it; Uncarried where it has no faithful writing.
    dts = typed_values.datatypes_of(task)
    for i, (p, ns) in enumerate(zip(task["params"], nodes_in)):
        f = _form_of(p["type"], ns, dts, False)
        if f is not None:
            ins[i] = "form:" + json.dumps(f)
    f = _form_of(task["returns"][0]["type"], nodes_out, dts, True)
    if f is not None:
        out = "form:" + json.dumps(f)
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
    if kind == "array":
        return f"isinstance({v}, list) and _t_ints({v}, 1)", "a list of integers (written in place)"
    if kind == "value" and ttype == "float":
        return f"isinstance({v}, float) and __import__('math').isfinite({v})", "a finite float"   # SPEC.md "Floats (v1)"
    if kind == "value" and ttype == "int":
        return f"_t_ints({v}, 0)", "an integer"
    if kind == "value" and ttype == "bool":
        return f"isinstance({v}, bool)", "a boolean"
    return None


# ------------------------------------------------- compound values at the boundary --
# A position's "form" says how its values are written in Python, as a JSON-able list (it is embedded in the generated
# source):
#   ["int"], ["bool"]
#   ["char"]                                    an int written as a one-character str
#   ["str"]                                     a seq written as a str
#   ["seq", container, elem]
#   ["set", elem, frozen, empty]
#   ["tup", container, [elems]]                 a pair or a tuple of three or more
#   ["map", key, value]
#   ["opt", bare, one, field]                   None, or the value
#   ["rec", ctor, container, [fields]]          a record, from the tuple of its fields
#   ["sum", bare, [[ctor, kind, field], ...]]   one constructor of several, chosen by the value's kind
# `container` is "list" or "tuple". A set's `empty` is "set" or "dict": MBPP writes an empty set as `{}` as often as
# `set()`, and `set() == {}` is False in Python, so the empty set is written as the tests write it. Inside the function
# a value is the interpreter's, except that a map is a dict, a pair or tuple a tuple, and a datatype value a tuple (its
# constructor's name, then its fields).


class Uncarried(Unsupported):
    """A value the boundary cannot write as the Python value the test wrote, named; nothing is compared or shown."""


def _t_in(v, f):
    """The Python value `v` of a position written as `f`, as the function inside holds it; TypeError when it is not one."""
    k = f[0]
    if k == "int":
        if isinstance(v, int) and not isinstance(v, bool):
            return v
    elif k == "bool":
        if isinstance(v, bool):
            return v
    elif k == "char":
        if isinstance(v, str) and len(v) == 1:
            return ord(v)
    elif k == "str":
        if isinstance(v, str):
            return tuple(ord(c) for c in v)
    elif k == "seq":
        if isinstance(v, (list, tuple)):
            return tuple(_t_in(x, f[2]) for x in v)
    elif k == "set":
        if isinstance(v, (set, frozenset)) or (f[3] == "dict" and isinstance(v, dict) and not v):
            return frozenset(_t_in(x, f[1]) for x in v)
    elif k == "tup":
        if isinstance(v, (list, tuple)) and len(v) == len(f[2]):
            return tuple(_t_in(x, g) for x, g in zip(v, f[2]))
    elif k == "map":
        if isinstance(v, dict):
            return {_t_in(a, f[1]): _t_in(b, f[2]) for a, b in v.items()}
    elif k == "opt":
        if v is None:
            return (f[1],)
        return (f[2], _t_in(v, f[3]))
    elif k == "rec":
        if isinstance(v, (list, tuple)) and len(v) == len(f[3]):
            return (f[1],) + tuple(_t_in(x, g) for x, g in zip(v, f[3]))
    elif k == "sum":
        if v is None and f[1] is not None:
            return (f[1],)
        hit = [(c, g) for c, kind, g in f[2]
               if (kind == "bool" and isinstance(v, bool))
               or (kind == "int" and isinstance(v, int) and not isinstance(v, bool))
               or (kind in ("str", "seq") and isinstance(v, str))
               or (kind in ("list", "seq") and isinstance(v, (list, tuple)))]
        if len(hit) == 1:
            return (hit[0][0], _t_in(v, hit[0][1]))
    raise TypeError("a value of the declared type")


def _t_out(v, f):
    """The function's value `v` of a position written as `f`, as the Python value the test writes; ValueError when it has none."""
    k = f[0]
    if k == "char":
        return chr(v)
    if k == "str":
        return "".join(chr(c) for c in v)
    if k == "seq":
        xs = [_t_out(x, f[2]) for x in v]
        return xs if f[1] == "list" else tuple(xs)
    if k == "tup":
        xs = [_t_out(x, g) for x, g in zip(v, f[2])]
        return xs if f[1] == "list" else tuple(xs)
    if k == "set":
        xs = {_t_out(x, f[1]) for x in v}
        return {} if f[3] == "dict" and not xs else frozenset(xs) if f[2] else xs
    if k == "map":
        return {_t_out(a, f[1]): _t_out(b, f[2]) for a, b in v.items()}
    if k == "opt":
        return None if v[0] == f[1] else _t_out(v[1], f[3])
    if k == "rec":
        xs = [_t_out(x, g) for x, g in zip(v[1:], f[3])]
        return xs if f[2] == "list" else tuple(xs)
    if k == "sum":
        if v[0] == f[1]:
            return None
        for c, _kind, g in f[2]:
            if v[0] == c:
                return _t_out(v[1], g)
        raise ValueError("a constructor with no Python value")
    return v


def _t_field(v, where):
    if v[0] not in where:
        raise ValueError("a field the constructor does not have, undefined in t")
    return v[where[v[0]]]


def _native(v):
    """An interpreter value as the generated function holds it (see above)."""
    if isinstance(v, interp.Pair):
        return (_native(v.a), _native(v.b))
    if isinstance(v, interp.Tup):
        return tuple(_native(x) for x in v.items)
    if isinstance(v, interp.MapV):
        return {_native(a): _native(b) for a, b in v.items}
    if isinstance(v, interp.Ctor):
        return (v.ctor,) + tuple(_native(a) for a in v.args)
    if isinstance(v, tuple):
        return tuple(_native(x) for x in v)
    if isinstance(v, frozenset):
        return frozenset(_native(x) for x in v)
    return v


def _words(ty) -> str:
    try:
        return surface._print_type(ty)
    except Exception:                                           # noqa: BLE001 -- words for a refusal
        return str(ty)


def _container(raws: list, strict: bool, what: str, default: str = "list") -> str:
    """"list" or "tuple", as the tests write the collections at one position; where they differ, the first one's for an
    argument (a function takes either) and a refusal for a result (an equal list and tuple are unequal in Python).
    With no test to say, `default`: a sequence is a list, a tuple or a record's fields a tuple."""
    kinds = {"tuple" if isinstance(r, tuple) else "list" for r in raws}
    if len(kinds) > 1 and strict:
        raise Uncarried(f"{what} written as a list in one test and as a tuple in another")
    return ("tuple" if isinstance(raws[0], tuple) else "list") if raws else default


def _form(ty, raws: list, dts: dict, strict: bool, hashable: bool = False):
    """How the values `raws` (the tests' own, at this position) of declared type `ty` are written in Python. Uncarried
    where a Python value cannot hold them as the tests wrote them. `strict`: a result, compared with `==`; `hashable`:
    inside a set or as a key, where a list or a dict cannot be."""
    if ty == "int":
        strs = [r for r in raws if isinstance(r, str)]
        if strs:
            if len(strs) != len(raws) or any(len(r) != 1 for r in strs):
                raise Uncarried("an int written as a string in one test and otherwise in another")
            return ["char"]
        return ["int"]
    if ty == "bool":
        return ["bool"]
    if ty == "seq":
        strs = [r for r in raws if isinstance(r, str)]
        if strs:
            if len(strs) != len(raws):
                raise Uncarried("a sequence written as a string in one test and as a list in another")
            return ["str"]
        ty = {"seq": "int"}
    if ty == "set":
        ty = {"set": "int"}
    if not isinstance(ty, dict) or len(ty) != 1:
        raise Uncarried(f"the type {_words(ty)}")
    (k, inner), = ty.items()
    if k in ("seq", "set"):
        if k == "seq" and not all(isinstance(r, (list, tuple)) for r in raws):
            raise Uncarried(f"a value that is not a list or tuple where {_words(ty)} is declared")
        if k == "set" and not all(isinstance(r, (set, frozenset)) or r == {} for r in raws):
            raise Uncarried(f"a value that is not a set where {_words(ty)} is declared")
        flat = [x for r in raws for x in r]
        if k == "set":
            as_dict = [r for r in raws if isinstance(r, dict)]
            as_set = [r for r in raws if not isinstance(r, dict) and not r]
            if as_dict and as_set and strict:
                raise Uncarried("an empty set written as {} in one test and as set() in another")
            return ["set", _form(inner, flat, dts, strict, True), hashable,
                    "dict" if as_dict and not as_set and not hashable else "set"]
        return ["seq", "tuple" if hashable else _container(raws, strict, "a sequence"),
                _form(inner, flat, dts, strict, hashable)]
    if k in ("pair", "tuple"):
        if not all(isinstance(r, (list, tuple)) and len(r) == len(inner) for r in raws):
            raise Uncarried(f"a value that is not a {len(inner)}-tuple where {_words(ty)} is declared")
        return ["tup", "tuple" if hashable else _container(raws, strict, "a tuple", "tuple"),
                [_form(t, [r[i] for r in raws], dts, strict, hashable) for i, t in enumerate(inner)]]
    if k == "map":
        if hashable:
            raise Uncarried("a dict inside a set or as a key (a dict has no hash in Python)")
        if not all(isinstance(r, dict) for r in raws):
            raise Uncarried(f"a value that is not a dict where {_words(ty)} is declared")
        return ["map", _form(inner[0], [a for r in raws for a in r], dts, strict, True),
                _form(inner[1], [b for r in raws for b in r.values()], dts, strict)]
    if k == "datatype":
        return _form_datatype(inner, raws, dts, strict, hashable)
    raise Uncarried(f"the type {_words(ty)}")


def _form_datatype(name: str, raws: list, dts: dict, strict: bool, hashable: bool):
    """A datatype value as typed_values.read_at reads it (`_read_ctor`): None the constructor without fields, a record
    from the tuple of its fields, an option's value as itself, else the constructor whose field has the value's kind.
    A result (`strict`) must have a Python value for every constructor, or what it does not write goes unseen."""
    if name not in dts:
        raise Uncarried(f"a datatype {name} the task does not declare")
    ctors = dts[name]["ctors"]
    bare = [c for c in ctors if not c.get("fields")]
    one = [c for c in ctors if len(c.get("fields") or []) == 1]
    full = [r for r in raws if r is not None]
    if len(ctors) == 1 and len(ctors[0].get("fields") or []) >= 2:
        c = ctors[0]
        fields = c["fields"]
        if not all(isinstance(r, (list, tuple)) and len(r) == len(fields) for r in full) or len(full) != len(raws):
            raise Uncarried(f"a value that is not a tuple of {len(fields)} where the record {name} is declared")
        return ["rec", c["name"], "tuple" if hashable else _container(full, strict, f"the record {name}", "tuple"),
                [_form(f["type"], [r[i] for r in full], dts, strict, hashable) for i, f in enumerate(fields)]]
    if len(bare) == 1 and len(one) == 1 and len(ctors) == 2:
        return ["opt", bare[0]["name"], one[0]["name"], _form(one[0]["fields"][0]["type"], full, dts, strict, hashable)]
    seqs = [c for c in one if c["fields"][0]["type"] == "seq"]
    taken: dict = {}
    for r in full:                                              # the constructor each test value is read as
        try:
            taken.setdefault(typed_values.read_at(r, {"datatype": name}, dts).ctor, []).append(r)
        except typed_values.Unreadable as why:
            raise Uncarried(f"a value of {name} that typed_values cannot read ({why})") from None
    entries, unwritten = [], [c["name"] for c in ctors if c not in one and c not in bare]
    unwritten += [c["name"] for c in bare] if len(bare) != 1 else []
    for c in one:
        ft, n = c["fields"][0]["type"], c["name"]
        kind = {"bool": "bool", "int": "int"}.get(ft) if isinstance(ft, str) else None
        if ft == "seq":
            kind = "seq" if len(seqs) == 1 else {"Str": "str", "Seq": "list"}.get(n)
        if kind is None:
            unwritten.append(n)
            continue
        mine = taken.get(n, [])
        if kind == "str":
            g = ["str"]
        elif kind == "list":
            g = ["seq", "tuple" if hashable else _container(mine, strict, f"a sequence in {n}"),
                 _form("int", [x for r in mine for x in r], dts, strict)]
        else:
            g = _form(ft, mine, dts, strict, hashable)
        entries.append([n, kind, g])
    if not entries and len(bare) != 1:
        raise Uncarried(f"the datatype {name}, whose constructors have no Python value")
    if strict and unwritten:
        raise Uncarried(f"the constructor {unwritten[0]} of {name}, which has no Python value")
    return ["sum", bare[0]["name"] if len(bare) == 1 else None, entries]


def _needs_form(ty) -> bool:
    """Whether the function inside holds a value of `ty` otherwise than a Python caller does: a map, a tuple of three or
    more, a datatype value (anywhere in the type)."""
    text = json.dumps(ty)
    return any(f'"{k}"' in text for k in ("map", "tuple", "datatype")) and "float" not in text and "real" not in text


def _form_of(ty, nodes: list, dts: dict, result: bool):
    """The form of a position the typed reader read (the plain reader refuses a test value there), or of a type the
    interpreter holds otherwise than a Python caller does (a map, a tuple of three or more, a datatype: `_needs_form`);
    None for the rest, which keeps the plain boundary. A typed position always gets a form, even where the plain
    boundary would write part of it (a list of tuples it would write as lists): it is written as the tests write it.
    Uncarried where that cannot be."""
    if not nodes and _needs_form(ty):
        return _form(ty, [], dts, result)                       # no test to say how it is written: the plain Python value
    if not nodes or "float" in json.dumps(ty) or "real" in json.dumps(ty):
        return None
    raws = []
    for n in nodes:
        try:
            raws.append(typed_values.literal(n))
        except typed_values.Unreadable:
            return None                                         # a float, a call, a name: not a value the typed reader reads
    import mbpp_dfy
    wide = dict(strings=True, nested_strings=True, tuples=True, nested_ints=True)
    for n in nodes:
        try:
            mbpp_dfy._literal(n, **wide)
        except Exception:                                       # noqa: BLE001 -- plain reader refuses: a typed position
            break
    else:
        if not _needs_form(ty):
            return None                                         # read by the plain reader, of a type it holds as it is
    return _form(ty, raws, dts, result)


def uncarried(ty, raws: list, dts: dict | None = None, result: bool = False) -> str | None:
    """None when the boundary writes the values `raws` of declared type `ty` as the tests wrote them (a form, `_form`),
    else why not, in words. verify asks it before a model is asked for a program, to say
    what the comparison with the person's function cannot carry."""
    try:
        _form(ty, raws, dts or {}, result)
    except Uncarried as why:
        return str(why)
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
    for p, decl, kind in zip(params, task["params"], ins):
        if kind.startswith("form:"):
            said = f"{name}: `{p}` must be {_words(decl['type'])}; nothing was proved for anything else"
            conv_in += [f"{INDENT}try:", f"{INDENT}{INDENT}{p} = _t_in({p}, {json.loads(kind[5:])!r})",
                        f"{INDENT}except TypeError:", f"{INDENT}{INDENT}raise TypeError({said!r}) from None"]
        elif kind in _IN:
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
    if out.startswith("form:"):
        result = f"_t_out(_t_result, {json.loads(out[5:])!r})"
    elif out.startswith("shape:"):
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
    if any(h in l for l in lines for h in ("_t_f(", "_t_fdiv(", "_t_sqrt(", "_t_tofloat(")):
        # SPEC.md "Floats (v1)": an operation with no finite result has no value in t, so it raises here
        support += ["def _t_f(v):", f"{INDENT}if isinstance(v, float) and not __import__('math').isfinite(v):",
                    f"{INDENT}{INDENT}raise ArithmeticError('no finite result, undefined in t')", f"{INDENT}return v", "",
                    "def _t_fdiv(x, y):", f"{INDENT}if isinstance(x, float):", f"{INDENT}{INDENT}if y == 0.0:",
                    f"{INDENT}{INDENT}{INDENT}raise ArithmeticError('division by zero, undefined in t')",
                    f"{INDENT}{INDENT}return _t_f(x / y)", f"{INDENT}if y == 0:",
                    f"{INDENT}{INDENT}raise ArithmeticError('division by zero, undefined in t')",
                    f"{INDENT}return (x - x % abs(y)) // y", "",
                    "def _t_sqrt(x):", f"{INDENT}if x < 0.0:", f"{INDENT}{INDENT}raise ArithmeticError('sqrt of a negative, undefined in t')",
                    f"{INDENT}return __import__('math').sqrt(x)", "",
                    "def _t_tofloat(n):", f"{INDENT}try:", f"{INDENT}{INDENT}return _t_f(float(n))",
                    f"{INDENT}except OverflowError:", f"{INDENT}{INDENT}raise ArithmeticError('float() overflows, undefined in t')", ""]
    if any("_t_par(" in l for l in lines):
        # SPEC.md "Concurrency (v1)": the iterations on a thread pool; where no thread can start (a sandbox), each one
        # not yet run runs in order, the same result by `par-race`, and none runs twice
        support += ["def _t_par(fn, lo, hi):", f"{INDENT}done = set()", "",
                    f"{INDENT}def run(i):", f"{INDENT}{INDENT}fn(i)", f"{INDENT}{INDENT}done.add(i)", "",
                    f"{INDENT}try:", f"{INDENT}{INDENT}import concurrent.futures",
                    f"{INDENT}{INDENT}with concurrent.futures.ThreadPoolExecutor() as pool:",
                    f"{INDENT}{INDENT}{INDENT}for f in [pool.submit(run, i) for i in range(lo, hi)]:",
                    f"{INDENT}{INDENT}{INDENT}{INDENT}f.result()",
                    f"{INDENT}except RuntimeError as e:",
                    f"{INDENT}{INDENT}if 'thread' not in str(e):", f"{INDENT}{INDENT}{INDENT}raise",
                    f"{INDENT}{INDENT}for i in range(lo, hi):", f"{INDENT}{INDENT}{INDENT}if i not in done:",
                    f"{INDENT}{INDENT}{INDENT}{INDENT}run(i)", ""]
    for helper in (_t_in, _t_out, _t_field):
        if any(f"{helper.__name__}(" in l for l in lines):
            support += inspect.getsource(helper).rstrip().splitlines() + [""]
    if any("_t_aset(" in l for l in lines):
        support += ["def _t_aset(a, i, v):", f"{INDENT}if not 0 <= i < len(a):",
                    f"{INDENT}{INDENT}raise IndexError('write outside the array, undefined in t')", f"{INDENT}a[i] = v", ""]
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
    if "_LINEBREAKS" in joined:
        head.append(f"_LINEBREAKS = {interp._LINEBREAKS!r}")
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
    if kind.startswith("form:"):
        return _t_out(_native(v), json.loads(kind[5:]))
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
        return [_t_value_to_py(x, "value") for x in v]     # an "array" too: the caller's list
    return v


def _interp_result(task: dict, env: dict, heap: dict | None = None):
    """The interpreter's return value (and, with `heap` a dict, the final contents of the modified arrays put in
    it: SPEC.md "Heap (v1)")."""
    funs = interp.funs_of(task, task["body"])
    st = interp.St()
    if not all(interp.ev(c, dict(env), funs, st) for c in task.get("requires", [])):
        return None, "requires"
    env2 = dict(env)
    ret = task["returns"][0]["name"]
    env2[ret] = None
    interp.exec_body(task["body"], env2, funs, st)
    if heap is not None:
        heap.update({a: env2[a] for a in interp.heap_mods(task)})
    return env2[ret], None


def _variants(v, ty, lad: dict, dts: dict, depth: int = 0):
    """`v`, a value of declared type `ty`, with one part of it replaced: a component, a value of a map, an element, a key
    added, a string made longer or shorter, the datatype's other values. What a function that is right on the
    tests and wrong in one place of the type is likely to differ on."""
    def ladder(t) -> list:
        try:
            return list(interp._ladder(lad, t)[:6])
        except Exception:                                       # noqa: BLE001 -- a type with no ladder has no replacement
            return []
    if depth > 3:
        return
    if ty == "seq" and isinstance(v, tuple):
        yield v[:-1]
        yield v + (v[-1] if v else 0,)
        yield v[::-1]
        yield tuple(x + 1 for x in v)
        for x in ladder("seq"):
            yield x
        return
    if not isinstance(ty, dict) or len(ty) != 1:
        return
    (k, inner), = ty.items()
    parts = types = rebuild = None
    if k == "pair" and isinstance(v, interp.Pair):
        parts, types, rebuild = [v.a, v.b], inner, lambda ps: interp.Pair(*ps)
    elif k == "tuple" and isinstance(v, interp.Tup):
        parts, types, rebuild = list(v.items), inner, lambda ps: interp.Tup(tuple(ps))
    elif k == "datatype" and isinstance(v, interp.Ctor):
        yield from lad.get(f"datatype:{inner}", ())
        c = next((c for d in dts.values() for c in d["ctors"] if d["name"] == inner and c["name"] == v.ctor), None)
        if c and c.get("fields") and len(c["fields"]) == len(v.args):
            parts, types, rebuild = list(v.args), [f["type"] for f in c["fields"]], lambda ps: interp.Ctor(v.dtype, v.ctor, tuple(ps))
    if parts is not None:
        for i, (x, t) in enumerate(zip(parts, types)):
            for alt in ladder(t) + list(_variants(x, t, lad, dts, depth + 1)):
                yield rebuild(parts[:i] + [alt] + parts[i + 1:])
        return
    if k == "map" and isinstance(v, interp.MapV):
        for j, (key, val) in enumerate(v.items):
            for alt in ladder(inner[1]) + list(_variants(val, inner[1], lad, dts, depth + 1)):
                yield interp.MapV.of(list(v.items[:j]) + [(key, alt)] + list(v.items[j + 1:]))
        for key in ladder(inner[0]):
            for val in ladder(inner[1])[:1]:
                yield v.put(key, val)
        return
    if k == "seq" and isinstance(v, tuple):
        for j, x in enumerate(v[:8]):
            for alt in ladder(inner) + list(_variants(x, inner, lad, dts, depth + 1)):
                yield v[:j] + (alt,) + v[j + 1:]
        for alt in ladder(inner)[:2]:
            yield v + (alt,)
        yield v[:-1]
        return
    if k == "set" and isinstance(v, frozenset):
        for alt in ladder(inner):
            yield v | {alt}
        for x in list(v)[:4]:
            yield v - {x}


def _example_inputs(task: dict, tests: list[str], ins: list[str], limit: int = 150) -> list[dict]:
    """The tests' own arguments, read at the declared types, and each with one typed parameter's value replaced by
    each of its `_variants`: inputs shaped like the examples, where a function that passes the examples is likely to
    be wrong. Only for a parameter written by a form; the rest keep the tests' values."""
    import ast
    params = task["params"]
    dts = typed_values.datatypes_of(task)
    lad = interp.ladders(task)
    out: list[dict] = []
    seen: set = set()

    def add(vals: list) -> None:
        key = repr([interp._tv(v) for v in vals])
        if key not in seen and len(out) < limit:
            seen.add(key)
            out.append({p["name"]: v for p, v in zip(params, vals)})
    for line in tests:
        try:
            node = ast.parse(line.strip()).body[0]
            args = node.test.left.args
            base = [typed_values.read_at(typed_values.literal(a), p["type"], dts) for a, p in zip(args, params)]
        except (SyntaxError, IndexError, AttributeError, typed_values.Unreadable):
            continue
        if len(base) != len(params):
            continue
        add(base)
        for i, kind in enumerate(ins):
            if kind.startswith("form:"):
                for alt in _variants(base[i], params[i]["type"], lad, dts):
                    add(base[:i] + [alt] + base[i + 1:])
    return out


def _t_same(a, b) -> bool:
    """`a == b` and the same type at every level: Python's `==` calls 1, True and 1.0 equal, a set and a frozenset, a dict
    and an OrderedDict or defaultdict, a str and a subclass of it, a tuple and a namedtuple, and a function that answers
    the one where the proved program answers the other has not answered as the program does. The type of each part of
    `b`, the reference, is the one the tests write it in (`_form` decides list or tuple, a set or the `{}` written for
    an empty one); only the order of a set's elements and a dict's keys is free."""
    if type(a) is not type(b):
        return False
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(_t_same(x, y) for x, y in zip(a, b))
    if isinstance(a, (set, frozenset)):
        return len(a) == len(b) and all(any(_t_same(x, y) for y in b) for x in a)
    if isinstance(a, dict):
        return len(a) == len(b) and all(any(_t_same(k, j) and _t_same(v, w) for j, w in b.items()) for k, v in a.items())
    return a == b


def _strict_example(line: str) -> str:
    """`assert f(x) == v` as `assert _t_same(f(x), v)`; any other line as it was written."""
    import ast
    try:
        node = ast.parse(line).body[0]
        t = node.test
        if (isinstance(node, ast.Assert) and isinstance(t, ast.Compare) and len(t.ops) == 1 and isinstance(t.ops[0], ast.Eq)
                and isinstance(t.left, ast.Call)):
            return f"assert _t_same({ast.unparse(t.left)}, {ast.unparse(t.comparators[0])})"
    except (SyntaxError, IndexError):
        pass
    return line


_REFUSES = "\n\n" + inspect.getsource(_t_same) + """
def _t_call_heap(f, args, idx):
    out = f(*args)
    return out, [args[i] for i in idx]

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
    try:
        ins, out = _boundary_kinds(task, tests or [])
    except Uncarried as why:                                    # nothing was written, so nothing is claimed
        return {"agrees": False, "abstained": True, "inputs": 0, "why": f"the comparison with your function cannot carry {why}"}
    names = [(p["name"], p["type"]) for p in task["params"]]
    asserts, strict, refusals = [], [], []         # `asserts` as they read (`==`); `strict` is what runs (`_t_same`)
    def one(env: dict) -> None:
        heap: dict = {}
        try:
            got, refusal = _interp_result(task, env, heap)
        except (interp.Undef, interp.Budget, RecursionError, ZeroDivisionError):
            return
        if refusal and len(refusals) < outside:
            try:
                refusals.append(f"assert _t_refuses({fn}, *{[_t_value_to_py(env[p], k) for (p, _t), k in zip(names, ins)]!r})")
            except (ValueError, TypeError, OverflowError):
                pass
        if refusal or got is None:
            return
        try:
            args = [_t_value_to_py(env[p], k) for (p, _t), k in zip(names, ins)]
            want = _t_value_to_py(got, out)
        except (ValueError, TypeError, OverflowError):
            return                                            # not a value a Python caller could pass (a bad code point)
        mods = interp.heap_mods(task)
        if mods:
            # SPEC.md "Heap (v1)": the call's result and each modified list's contents afterwards
            idx = [i for i, (p, _t) in enumerate(names) if p in mods]
            finals = [_t_value_to_py(heap[names[i][0]], "array") for i in idx]
            asserts.append(f"assert _t_call_heap({fn}, {args!r}, {idx!r}) == ({want!r}, {finals!r})")
            strict.append(f"assert _t_same(_t_call_heap({fn}, {args!r}, {idx!r}), ({want!r}, {finals!r}))")
            return
        asserts.append(f"assert {fn}(*{args!r}) == {want!r}")
        strict.append(f"assert _t_same({fn}(*{args!r}), {want!r})")

    for env in interp.domain(task, names, interp.MAX_POINTS):
        if len(asserts) >= n:
            break
        one(env)
    if any(k.startswith("form:") for k in ins):
        # A tuple's, a map's or a datatype's own domain is a few dozen values of 0, 1 and -1 (interp._ladder caps a
        # product at PAIR_SHELL), so a function that differs where a component is 2, or a string is two long, would not
        # be met. The tests' own inputs, and each with one part replaced, are compared as well.
        for env in _example_inputs(task, tests or [], ins):
            one(env)
    if not asserts and any(k.startswith("form:") for k in ins + [out]):
        # the tests alone say nothing about a function that is the person's own: with no input of the program's domain
        # written as the function's Python values there is nothing to compare, and "agrees" would be a claim from nothing
        return {"agrees": False, "abstained": True, "inputs": 0,
                "why": "no input of the program's domain could be written as the values your function takes"}
    # The person's own examples are run in their written forms: `assert f(x) == v` runs as `assert _t_same(f(x), v)`, so
    # a function that passes its own example only because 1 == True (or 1 == 1.0, or a list for a tuple's subclass)
    # does not count as agreeing.
    own = [t.strip() for t in tests or [] if t.strip()]
    asserts += own
    strict += [_strict_example(t) for t in own]
    if not asserts:
        return {"agrees": False, "inputs": 0, "why": "no input to check on"}
    r = py_sandbox.run_tests(src + _REFUSES, strict + refusals, per_test=per_test)
    ok = r.get("status") == "ran" and bool(r.get("all_pass"))
    if ok:
        return {"agrees": True, "inputs": len(asserts), "refused": len(refusals)}
    first = next((a for a, v in zip(asserts + refusals, r.get("verdicts") or []) if v != "pass"), None)
    return {"agrees": False, "inputs": len(asserts), "refused": len(refusals), "why": json.dumps(r)[:300],
            **({"first": first} if first else {})}
