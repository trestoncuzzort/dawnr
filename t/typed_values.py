#!/usr/bin/env python3
"""t/typed_values.py -- test values beyond ints, bools, strings and lists of them, read at the type a task declares
(2026-11-26).

The test reader (t/mbpp_dfy.py `_literal`) reads an int, a bool, a string, and lists and tuples of them, and refuses
the rest by name. `t` itself has carried more since 2026-10-06: products of any arity and of any component types,
sequences and sets of any element type (SPEC.md "Compositional types (v1)"), maps ("Maps (v1)") and datatypes with
fields ("Datatypes (v2)"), and Dafny carries all of them. Of MBPP's 974 problems the reader refused 178; after the
63 with a float, the first refusals were a tuple or list mixing kinds of element, a dict, deeper nesting, None, a
set and a list of bools. This module is the reading those problems need, and nothing is read here that `t` has no
type for.

How a value is read. A test's value is kept as the Python literal it is (`ast.literal_eval`'s own reading, with a
float, a complex number and bytes refused by name), and it is read at the type the TASK declares when a task meets
it: a str is a `seq` of its code points (one character may also be an `int`, as SPEC.md's 'a' is 97), a tuple is a
`(T1, T2)` pair or a tuple of three or more, a dict is a `map<K, V>`, a set is a `set<T>`, None is the constructor
without fields of a datatype that has one such constructor and one with one field (an option), and a list that
mixes kinds is a `seq` of a datatype with one one-field constructor a kind. That is how MultiPL-E types a test's
data for a typed target, "from the type of the function signature" (arXiv:2208.08227, III-C.2), and how
spec_experiment.kind_fits already reads a nested list. A value the declared type cannot hold faithfully is refused
(`Unreadable`), never squeezed into it: a key that would collide with another once read, a bool where an int is
declared (SPEC.md gate 1), a str where a list is declared.

What the question says. A position's values across the problem's tests are given one type here (`type_of`), in
the canonical spellings of SPEC.md "Compositional types (v1)": tuples of one kind are sequences, as the wider reader
of 2026-10-05 reads them, and a tuple of several kinds is a product. Two forms only the question uses name a
datatype the task must declare: `{"option": T}` (None or a T) and `{"sum": [...]}` (a list mixing ints, bools,
strings and lists of ints). The point carries the type as its kind, `t:` and the type as JSON, so that no earlier
kind ("int", "seq", "seq-of-seq", ...) is ever confused with one of these.

Crossing into the sandbox. A person's function runs in t/py_sandbox.py, whose calls cross as JSON: no tuple, no
set, no dict with a key that is not a string. So for these values the code loaded there gets one more function,
which takes the arguments as the text of a Python literal and gives back the text of its result's literal
(`wrapper`), read on this side by `ast.literal_eval` again. verify_py's `_t_repr_call` already sends results back
as `repr` text; this sends the arguments the same way. Nothing of the sandbox itself changes.

Drawn inputs (`draw`) keep each example's shape, as spec_check.draw does for the kinds it knows: a str stays a str
of about the same length and alphabet, a tuple keeps its length and the kinds of its components, a dict draws keys
like the example's keys and values like its values, None stays None.
"""
from __future__ import annotations

import ast
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import interp                                                   # noqa: E402

PREFIX = "t:"
LITERAL_CALL = "_t_literal_call"


class Unreadable(Exception):
    """A value with no reading here, or none at the declared type; str() names what it is."""


class _NoValue:
    """What a sandboxed call that answered no literal is read as: no type reads it."""

    def __repr__(self) -> str:
        return "<no literal>"


NO_VALUE = _NoValue()


# ------------------------------------------------------------------ the literal --

def literal(node: ast.AST):
    """A test's value as the Python literal it is. Unreadable, named as mbpp_dfy names its refusals, for anything
    else: a float (t's integers only in this reader; SPEC.md "Floats (v1)" waits on a prover decision), a call, a
    name."""
    if isinstance(node, ast.Constant):
        v = node.value
        if v is None or isinstance(v, (bool, int, str)):
            return v
        raise Unreadable(type(v).__name__)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        v = literal(node.operand)
        if isinstance(v, bool) or not isinstance(v, int):
            raise Unreadable("negated-" + type(v).__name__)
        return -v if isinstance(node.op, ast.USub) else v
    if isinstance(node, ast.Tuple):
        return tuple(literal(x) for x in node.elts)
    if isinstance(node, ast.List):
        return [literal(x) for x in node.elts]
    if isinstance(node, ast.Set):
        out = [literal(x) for x in node.elts]
        try:
            return set(out)
        except TypeError:
            raise Unreadable("set of an unhashable value") from None
    if isinstance(node, ast.Dict):
        if any(k is None for k in node.keys):
            raise Unreadable("dict unpacking")
        keys = [literal(k) for k in node.keys]
        try:
            return dict(zip(keys, (literal(v) for v in node.values)))
        except TypeError:
            raise Unreadable("dict with an unhashable key") from None
    if isinstance(node, ast.Call):
        fn = getattr(node.func, "id", None) or getattr(node.func, "attr", "call")
        if fn == "set" and isinstance(node.func, ast.Name) and not node.args and not node.keywords:
            return set()                                        # the empty set, which has no display of its own
        raise Unreadable("call:" + str(fn))
    raise Unreadable(type(node).__name__)


# ------------------------------------------------------------- the question's type --

_ANY = "?"          # an empty collection's element: any type, settled by the others or by `_settle`
_CHAR = "char"      # a one-character str: a string, or a character where ints are


def _shape(v):
    """One value's own type, before the values beside it are seen."""
    if v is None:
        return "none"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, str):
        return _CHAR if len(v) == 1 else "seq"
    if isinstance(v, list):
        return {"seq": _elements([_shape(x) for x in v])}
    if isinstance(v, tuple):
        return {"tup": [_shape(x) for x in v]}
    if isinstance(v, set):
        return {"set": _elements([_shape(x) for x in v])}
    if isinstance(v, dict):
        return {"map": [_elements([_shape(k) for k in v]), _elements([_shape(x) for x in v.values()])]}
    raise Unreadable(type(v).__name__)


class _Clash(Exception):
    pass


def _key(t) -> str:
    return json.dumps(t, sort_keys=True)


def _unify(a, b):
    """The one type both values have, or _Clash."""
    if _key(a) == _key(b):
        return a
    if a == _ANY:
        return b
    if b == _ANY:
        return a
    if isinstance(a, str) and isinstance(b, str) and {a, b} == {_CHAR, "seq"}:
        return "seq"                                            # strings, some one character long
    if a == "none" or b == "none":
        other = b if a == "none" else a
        return other if isinstance(other, dict) and "option" in other else {"option": other}
    if isinstance(a, dict) and "option" in a or isinstance(b, dict) and "option" in b:
        x = a["option"] if isinstance(a, dict) and "option" in a else a
        y = b["option"] if isinstance(b, dict) and "option" in b else b
        return {"option": _unify(x, y)}
    if isinstance(a, dict) and "sum" in a or isinstance(b, dict) and "sum" in b:
        return _as_sum(a, b)
    if not (isinstance(a, dict) and isinstance(b, dict)):
        raise _Clash
    (ka, va), = a.items()
    (kb, vb), = b.items()
    if ka == kb == "tup":
        if len(va) == len(vb):
            return {"tup": [_unify(x, y) for x, y in zip(va, vb)]}
        return {"seq": _elements(va + vb)}                      # tuples of several lengths are sequences
    if {ka, kb} == {"tup", "seq"}:
        comps, seq = (va, vb) if ka == "tup" else (vb, va)
        return {"seq": _elements(comps + [seq])}
    if ka == kb and ka in ("seq", "set"):
        return {ka: _unify_or_sum(va, vb)}
    if ka == kb == "map":
        return {"map": [_unify(va[0], vb[0]), _unify(va[1], vb[1])]}
    if {ka, kb} == {"map", "set"}:                              # `{}` is an empty dict, written where a set is meant
        m, s = (va, b) if ka == "map" else (vb, a)
        if m == [_ANY, _ANY]:
            return s
    raise _Clash


# a list that mixes kinds is a sequence of a datatype with one constructor a kind; the kinds a constructor's field
# can hold (SPEC.md "Datatypes (v2)": a field is an int, a bool or a seq)
_SUM_KIND = {"int": "Int", "bool": "Bool", "seq": "Str", _CHAR: "Str"}


def _sum_kinds(t) -> set[str]:
    if isinstance(t, dict) and "sum" in t:
        return set(t["sum"])
    if isinstance(t, str) and t in _SUM_KIND:
        return {_SUM_KIND[t]}
    if isinstance(t, dict) and set(t) == {"seq"} and t["seq"] in ("int", _ANY):
        return {"Seq"}
    if isinstance(t, dict) and set(t) == {"tup"} and all(c == "int" for c in t["tup"]):
        return {"Seq"}
    raise _Clash


def _as_sum(a, b):
    return {"sum": sorted(_sum_kinds(a) | _sum_kinds(b))}


def _unify_or_sum(a, b):
    try:
        return _unify(a, b)
    except _Clash:
        return _as_sum(a, b)


def _elements(shapes: list):
    """The type of a collection's elements: one type, or for a list that mixes kinds, a sum of them."""
    out = _ANY
    for s in shapes:
        out = _unify_or_sum(out, s)
    return out


def _settle(t):
    """A type in SPEC.md's canonical spellings, the question's own forms kept: an unconstrained element is an int
    (t's `[]` is a plain seq, `map[]` a map<int, int>), a character alone is a string, a tuple of one kind a seq."""
    if t == _ANY:
        return "int"
    if t == _CHAR:
        return "seq"
    if isinstance(t, str):
        if t == "none":
            raise Unreadable("None and nothing else: no type to make optional")
        return t
    (k, v), = t.items()
    if k == "seq":
        if v in (_CHAR,):
            return "seq"                                        # a list of one-character strings is a string's code points
        inner = _settle(v)
        return "seq" if inner == "int" else {"seq": inner}
    if k == "set":
        inner = _settle(v)
        return "set" if inner == "int" else {"set": inner}
    if k == "map":
        return {"map": [_settle(v[0]), _settle(v[1])]}
    if k == "tup":
        if len(v) < 2:
            return _settle({"seq": v[0] if v else _ANY})
        try:
            one = _ANY
            for c in v:
                one = _unify(one, c)
            return _settle({"seq": one})                         # one kind throughout: a sequence
        except _Clash:
            comps = [_settle(c) for c in v]
            return {"pair": comps} if len(comps) == 2 else {"tuple": comps}
    if k == "option":
        inner = _settle(v)
        if inner not in ("int", "bool", "seq"):
            raise Unreadable("an optional value of a compound type (a datatype's field is an int, a bool or a seq)")
        return {"option": inner}
    if k == "sum":
        return {"sum": list(v)}
    raise Unreadable(f"no type for {k}")


def type_of(values: list):
    """The one type the values at a position have across a problem's tests; Unreadable when none holds them all."""
    out = _ANY
    try:
        for v in values:
            out = _unify_or_sum(out, _shape(v))
    except _Clash:
        raise Unreadable("values of different kinds at one position") from None
    return _settle(out)


def kind_of(t) -> str:
    return PREFIX + json.dumps(t, sort_keys=True)


PENDING = PREFIX + "?"          # read only as a literal, and typed once the values beside it are seen (`settle`)


def settle(points: list[dict]) -> list[dict]:
    """Give every position the reader could read only as a literal one type across the tests (`type_of` over the
    problem's own values there), and that position's every value as its literal; a position the reader read whole
    in every test keeps its reading, so a problem it read before reads as it did. Unreadable, naming the position,
    when the values there have no type. The points are changed in place and returned."""
    if not points:
        return points
    columns = [("expected", None)] + [("args", i) for i in range(max(len(p["args"]) for p in points))]
    for side, i in columns:
        cells = [p["expected"] if i is None else (p["args"][i] if i < len(p["args"]) else None) for p in points]
        if not any(c is not None and c[0] == PENDING for c in cells):
            continue
        where = "the expected value" if i is None else f"argument {i + 1}"
        if any(c is None for c in cells):
            raise Unreadable(f"{where}: the tests pass different numbers of arguments")
        raws = [p["raw"]["expected"] if i is None else p["raw"]["args"][i] for p in points]
        try:
            kind = kind_of(type_of(raws))
        except Unreadable as why:
            raise Unreadable(f"{where}: {why}") from None
        for p, v in zip(points, raws):
            if i is None:
                p["expected"] = (kind, v)
            else:
                p["args"][i] = (kind, v)
    return points


def is_typed(kind) -> bool:
    return isinstance(kind, str) and kind.startswith(PREFIX)


def type_of_kind(kind: str):
    return json.loads(kind[len(PREFIX):])


def entry_is_typed(entry: dict) -> bool:
    return any(is_typed(k) for p in entry.get("points", []) for k, _v in list(p["args"]) + [p["expected"]])


# ------------------------------------------------------------------ the words --

_SUM_CTOR = {"Int": ("i", "int"), "Bool": ("b", "bool"), "Str": ("s", "seq"), "Seq": ("xs", "seq")}


def declarations(types: list) -> dict:
    """The datatypes the question's types need, named in order of appearance: {type key: (name, declaration)}."""
    out: dict = {}

    def walk(t):
        if isinstance(t, dict):
            (k, v), = t.items()
            if k == "option" and _key(t) not in out:
                name = "Option" if not any(n.startswith("Option") for n, _d in out.values()) else f"Option{len(out) + 1}"
                out[_key(t)] = (name, f"datatype {name} = Nothing | Some(v: {v})")
            elif k == "sum" and _key(t) not in out:
                name = "Item" if not any(n.startswith("Item") for n, _d in out.values()) else f"Item{len(out) + 1}"
                ctors = " | ".join(f"{c}({_SUM_CTOR[c][0]}: {_SUM_CTOR[c][1]})" for c in v)
                out[_key(t)] = (name, f"datatype {name} = {ctors}")
            elif k in ("pair", "tuple", "map"):
                for x in v:
                    walk(x)
            elif k in ("seq", "set"):
                walk(v)
    for t in types:
        walk(t)
    return out


def words(t, names: dict | None = None) -> str:
    """A type in t's own notation, a datatype the question needs by the name `declarations` gives it."""
    names = names if names is not None else declarations([t])
    if isinstance(t, str):
        return t
    (k, v), = t.items()
    if k in ("option", "sum"):
        return names[_key(t)][0]
    if k in ("pair", "tuple"):
        return "(" + ", ".join(words(x, names) for x in v) + ")"
    if k in ("seq", "set"):
        return f"{k}<{words(v, names)}>"
    if k == "map":
        return f"map<{words(v[0], names)}, {words(v[1], names)}>"
    if k == "datatype":
        return v
    return str(t)


# ---------------------------------------------------------- read at the declared type --

def _ctors(dts: dict, name: str) -> list[dict]:
    if name not in dts:
        raise Unreadable(f"the task declares no datatype {name}")
    return dts[name]["ctors"]


def _field_type(c: dict):
    return c["fields"][0]["type"]


def _fits_kind(v, field_type) -> bool:
    """Whether a value's own Python kind is the field's kind: a bool a bool, an int an int, a str or a list of ints
    a seq. The first test of a constructor for a value of a list that mixes kinds."""
    if field_type == "bool":
        return isinstance(v, bool)
    if field_type == "int":
        return isinstance(v, int) and not isinstance(v, bool)
    if field_type == "seq":
        return isinstance(v, (str, list, tuple))
    if isinstance(field_type, dict) and "datatype" in field_type:
        return False
    return False


def read_at(v, ty, dts: dict | None = None):
    """The test value `v` as the interpreter's value of the declared type `ty` (`dts`: the task's datatypes by name);
    Unreadable when the type cannot hold it as it is."""
    dts = dts or {}
    if v is NO_VALUE:
        raise Unreadable("the function answered no literal")
    if ty == "int":
        if isinstance(v, int) and not isinstance(v, bool):
            return v
        if isinstance(v, str) and len(v) == 1:
            return ord(v)                                       # SPEC.md: 'a' is 97
        raise Unreadable(f"{type(v).__name__} where an int is declared")
    if ty == "bool":
        if isinstance(v, bool):
            return v
        raise Unreadable(f"{type(v).__name__} where a bool is declared")
    if ty == "seq":
        if isinstance(v, str):
            return tuple(ord(c) for c in v)
        if isinstance(v, (list, tuple)):
            return tuple(read_at(x, "int", dts) for x in v)
        raise Unreadable(f"{type(v).__name__} where a seq is declared")
    if ty == "set":
        ty = {"set": "int"}
    if not isinstance(ty, dict) or len(ty) != 1:
        raise Unreadable(f"no reading at {ty!r}")
    (k, inner), = ty.items()
    if k == "seq":
        if isinstance(v, (list, tuple)):
            return tuple(read_at(x, inner, dts) for x in v)
        raise Unreadable(f"{type(v).__name__} where a seq<...> is declared")
    if k == "set":
        if isinstance(v, (set, frozenset)) or (isinstance(v, dict) and not v):
            out = frozenset(read_at(x, inner, dts) for x in v)
            if len(out) != len(v):
                raise Unreadable("two elements of the set are one value once read")
            return out
        raise Unreadable(f"{type(v).__name__} where a set is declared")
    if k == "pair":
        if isinstance(v, (list, tuple)) and len(v) == 2:
            return interp.Pair(read_at(v[0], inner[0], dts), read_at(v[1], inner[1], dts))
        raise Unreadable(f"{type(v).__name__} where a pair is declared")
    if k == "tuple":
        if isinstance(v, (list, tuple)) and len(v) == len(inner):
            return interp.Tup(tuple(read_at(x, t, dts) for x, t in zip(v, inner)))
        raise Unreadable(f"{type(v).__name__} where a tuple of {len(inner)} is declared")
    if k == "map":
        if isinstance(v, dict):
            pairs = [(read_at(a, inner[0], dts), read_at(b, inner[1], dts)) for a, b in v.items()]
            if len({repr(interp._tv(a)) for a, _b in pairs}) != len(pairs):
                raise Unreadable("two keys of the dict are one key once read")
            return interp.MapV.of(pairs)
        raise Unreadable(f"{type(v).__name__} where a map is declared")
    if k == "datatype":
        return _read_ctor(v, inner, dts)
    raise Unreadable(f"no reading at {ty!r}")


def _read_ctor(v, name: str, dts: dict):
    ctors = _ctors(dts, name)
    bare = [c for c in ctors if not c.get("fields")]
    one = [c for c in ctors if len(c.get("fields") or []) == 1]
    if v is None:
        if len(bare) == 1:
            return interp.Ctor(name, bare[0]["name"], ())
        raise Unreadable(f"None, and {name} has {len(bare)} constructors without fields")
    if len(ctors) == 1 and len(ctors[0].get("fields") or []) >= 2:      # a record, from a tuple of its fields
        fields = ctors[0]["fields"]
        if isinstance(v, (list, tuple)) and len(v) == len(fields):
            return interp.Ctor(name, ctors[0]["name"], tuple(read_at(x, f["type"], dts) for x, f in zip(v, fields)))
        raise Unreadable(f"{type(v).__name__} where the record {name} of {len(fields)} fields is declared")
    if len(bare) == 1 and len(one) == 1 and len(ctors) == 2:           # an option: None, or the value itself
        return interp.Ctor(name, one[0]["name"], (read_at(v, _field_type(one[0]), dts),))
    # one of several kinds: the constructor whose field is this value's kind; a str and a list are both a seq, so
    # where two constructors take a seq the names the question suggested (Str, Seq) decide, and nothing else does
    fit = [c for c in one if _fits_kind(v, _field_type(c))]
    if len(fit) > 1 and isinstance(v, (str, list, tuple)):
        hint = "Str" if isinstance(v, str) else "Seq"
        fit = [c for c in fit if c["name"] == hint] or fit
    if len(fit) != 1:
        raise Unreadable(f"{type(v).__name__}: {'no' if not fit else 'more than one'} constructor of {name} takes it")
    return interp.Ctor(name, fit[0]["name"], (read_at(v, _field_type(fit[0]), dts),))


def datatypes_of(task: dict) -> dict:
    return {d["name"]: d for d in task.get("datatypes", []) or []}


def fits(v, ty, dts: dict | None = None) -> bool:
    try:
        read_at(v, ty, dts)
        return True
    except Unreadable:
        return False


# ------------------------------------------------------------------ the crossing --

# Appended to the person's code in the sandbox: the arguments arrive as one literal's text, the result leaves as
# its literal's text, a dict, list, tuple or set of another class (a Counter, a defaultdict, a namedtuple) written
# as the plain one it compares equal to. A value with no literal (an object) leaves as text literal_eval refuses.
_WRAPPER = '''

def {name}(_t_text):
    import ast as _t_ast

    def _t_plain(v, depth=0):
        if depth > 40:
            raise TypeError("nested too deep")
        if isinstance(v, dict):
            return {{_t_plain(k, depth + 1): _t_plain(x, depth + 1) for k, x in v.items()}}
        if isinstance(v, (set, frozenset)):
            return {{_t_plain(x, depth + 1) for x in v}}
        if isinstance(v, tuple):
            return tuple(_t_plain(x, depth + 1) for x in v)
        if isinstance(v, list):
            return [_t_plain(x, depth + 1) for x in v]
        if v is None or isinstance(v, (bool, int, float, str)):
            return v
        raise TypeError(type(v).__name__)
    _t_out = {fn}(*_t_ast.literal_eval(_t_text))      # what the function raises is the function's
    try:
        return repr(_t_plain(_t_out))
    except TypeError:
        return "<no literal>"
'''


def wrapper(fn: str) -> str:
    return _WRAPPER.format(name=LITERAL_CALL, fn=fn)


def encode(args: list) -> list:
    """A call's arguments as the one JSON string the wrapper takes."""
    return [repr(tuple(args))]


def decode(text):
    """The wrapper's answer as the value it is; NO_VALUE for an answer that is no literal."""
    if not isinstance(text, str):
        return NO_VALUE
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError, MemoryError, RecursionError, TypeError):
        return NO_VALUE


# ------------------------------------------------------------------ drawn inputs --

def _draw_int(like, rnd: random.Random, larger: bool) -> int:
    if isinstance(like, int) and not isinstance(like, bool):
        top = max(2, abs(like) * 2)
        x = rnd.randint(top + 1, max(top * 3, top + 12)) if larger else rnd.randint(0, top)
        return x if like >= 0 else -x
    return rnd.randint(41, 160) if larger else rnd.choice([rnd.randint(-8, 8), rnd.randint(0, 40)])


def _draw_str(like: str, rnd: random.Random, larger: bool) -> str:
    points = [ord(c) for c in like if 32 <= ord(c) < 127]
    lo, hi = (max(32, min(points) - 2), min(126, max(points) + 2)) if points else (97, 122)
    n = rnd.randint(len(like) + 1, max(12, 3 * (len(like) + 2))) if larger else rnd.randint(0, len(like) + 2)
    return "".join(chr(rnd.randint(lo, hi)) for _ in range(n))


def _count(like_len: int, rnd: random.Random, larger: bool) -> int:
    return rnd.randint(like_len + 3, max(8, 3 * (like_len + 2))) if larger else rnd.randint(0, like_len + 2)


def draw(ty, like, rnd: random.Random, larger: bool = False):
    """A random value of the question's type `ty` in the shape of the example `like` (one of the problem's own
    values at that position); `larger` draws past the examples' sizes (spec_check.draw_beyond's purpose)."""
    if like is None:
        return None
    if isinstance(ty, dict) and "option" in ty:
        return draw(ty["option"], like, rnd, larger)
    if isinstance(ty, dict) and "sum" in ty:
        return _draw_like(like, rnd, larger)
    if ty == "bool" or isinstance(like, bool):
        return rnd.random() < 0.5
    if ty == "int":
        if isinstance(like, str):
            return _draw_str(like, rnd, False)[:1] or like      # a character stays a character
        return _draw_int(like, rnd, larger)
    if isinstance(like, str):
        return _draw_str(like, rnd, larger)
    if ty in ("seq", "set") or isinstance(ty, dict) and set(ty) & {"seq", "set"}:
        inner = "int" if ty in ("seq", "set") else ty.get("seq", ty.get("set"))
        # a set's elements in a fixed order: a set of strings iterates in an order each run of Python picks anew
        items = (sorted(like, key=repr) if isinstance(like, set) else list(like)) if isinstance(like, (list, tuple, set)) else []
        if not items:
            return type(like)() if isinstance(like, (list, tuple, set)) else like
        # only the outermost collection grows past the examples: a larger draw of a nested value stays a size
        # the interpreter's own caps can take
        made = [draw(inner, rnd.choice(items), rnd) for _ in range(_count(len(items), rnd, larger))]
        if isinstance(like, list) and items and all(isinstance(x, int) and not isinstance(x, bool) for x in items) \
                and items == sorted(items):
            made.sort()                                         # a sorted example stays sorted (spec_check.draw)
        if isinstance(like, set) or isinstance(like, dict):
            try:
                return set(made)
            except TypeError:
                return like
        return tuple(made) if isinstance(like, tuple) else made
    if isinstance(ty, dict) and ("pair" in ty or "tuple" in ty):
        comps = ty.get("pair") or ty.get("tuple")
        if isinstance(like, (list, tuple)) and len(like) == len(comps):
            made = [draw(t, x, rnd, larger) for t, x in zip(comps, like)]          # a tuple's size is its own
            return tuple(made) if isinstance(like, tuple) else made
        return like
    if isinstance(ty, dict) and "map" in ty:
        if not isinstance(like, dict) or not like:
            return {} if isinstance(like, dict) else like
        keys, values = list(like), list(like.values())
        out = {}
        for _ in range(_count(len(keys), rnd, larger)):
            k = draw(ty["map"][0], rnd.choice(keys), rnd)
            try:
                out[k] = draw(ty["map"][1], rnd.choice(values), rnd)
            except TypeError:
                pass
        return out
    return _draw_like(like, rnd, larger)


def _draw_like(like, rnd: random.Random, larger: bool):
    """A value of the example's own Python kind, for an element of a list that mixes kinds."""
    if isinstance(like, bool):
        return rnd.random() < 0.5
    if isinstance(like, int):
        return _draw_int(like, rnd, larger)
    if isinstance(like, str):
        return _draw_str(like, rnd, larger)
    if isinstance(like, (list, tuple)) and like and all(isinstance(x, int) and not isinstance(x, bool) for x in like):
        made = [_draw_int(rnd.choice(like), rnd, larger) for _ in range(_count(len(like), rnd, larger))]
        return tuple(made) if isinstance(like, tuple) else made
    return like


# ------------------------------------------------------------------ wrong answers --

def mutations(value, datatypes: dict | None = None, limit: int = 12) -> list:
    """Wrong outputs near a right one of a compound type (a pair, a tuple, a set, a map, a datatype value, a seq of
    them), deterministically, for the completeness half of the specification check (spec_check.mutations, which
    keeps the ints, bools and seqs it always had). Each is of the same type as the right one."""
    from spec_check import mutations as plain
    out = []

    def near(x):
        if compound(x):
            return mutations(x, datatypes, 4)
        if isinstance(x, int) and not isinstance(x, bool):
            return [m for m in (x + 1, x - 1, x + 2, 0) if m != x]      # the nearest first
        return plain(x)[:4]
    if isinstance(value, interp.Pair):
        out += [interp.Pair(m, value.b) for m in near(value.a)] + [interp.Pair(value.a, m) for m in near(value.b)]
        if _plain_kind(value.a) is not None and _plain_kind(value.a) == _plain_kind(value.b) and value.a != value.b:
            out.append(interp.Pair(value.b, value.a))           # the two components swapped, where they are one type
    elif isinstance(value, interp.Tup):
        for i, x in enumerate(value.items):
            out += [interp.Tup(value.items[:i] + (m,) + value.items[i + 1:]) for m in near(x)[:2]]
    elif isinstance(value, frozenset):
        items = interp._in_order(value)
        out += [value - {x} for x in items[:4]]
        for x in items[:2]:
            out += [value | {m} for m in near(x) if m not in value][:2]
    elif isinstance(value, interp.MapV):
        pairs = list(value.items)
        out += [interp.MapV(tuple(p for p in pairs if p is not q)) for q in pairs[:3]]
        for i, (k, x) in enumerate(pairs[:3]):
            out += [interp.MapV.of(pairs[:i] + [(k, m)] + pairs[i + 1:]) for m in near(x)[:2]]
        if pairs:
            k, x = pairs[0]
            out += [interp.MapV.of(pairs + [(m, x)]) for m in near(k) if not value.has(m)][:2]
    elif isinstance(value, interp.Ctor):
        for i, x in enumerate(value.args):
            out += [interp.Ctor(value.dtype, value.ctor, value.args[:i] + (m,) + value.args[i + 1:]) for m in near(x)[:3]]
        for c in ((datatypes or {}).get(value.dtype) or {}).get("ctors", []):
            if c["name"] != value.ctor and not c.get("fields"):
                out.append(interp.Ctor(value.dtype, c["name"], ()))
            elif c["name"] != value.ctor and len(c["fields"]) == 1 and len(value.args) == 1 and \
                    fits_value(value.args[0], c["fields"][0]["type"]):
                out.append(interp.Ctor(value.dtype, c["name"], value.args))
    elif isinstance(value, tuple) and value and any(compound(x) for x in value):
        out += [value[:-1], value[1:], tuple(reversed(value)), value + (value[-1],)]
        out += [(m,) + value[1:] for m in near(value[0])[:3]]
    seen, unique = set(), []
    for m in out:
        k = repr(interp._tv(m))
        if m != value and k != repr(interp._tv(value)) and k not in seen:
            seen.add(k)
            unique.append(m)
    return unique[:limit]


def _plain_kind(x) -> str | None:
    for kind in ("bool", "int", "seq"):
        if fits_value(x, kind):
            return kind
    return None


def compound(x) -> bool:
    return isinstance(x, (interp.Pair, interp.Tup, frozenset, interp.MapV, interp.Ctor)) or (
        isinstance(x, tuple) and any(compound(y) for y in x))


def fits_value(x, ty) -> bool:
    """Whether an interpreter value is of the plain type `ty` (int, bool, seq), for a constructor's field."""
    if ty == "int":
        return isinstance(x, int) and not isinstance(x, bool)
    if ty == "bool":
        return isinstance(x, bool)
    if ty == "seq":
        return isinstance(x, tuple) and all(isinstance(y, int) and not isinstance(y, bool) for y in x)
    return False
