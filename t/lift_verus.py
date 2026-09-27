#!/usr/bin/env python3
"""t/lift_verus.py -- the Verus front end of the lifter: read one verified Verus file
(vericoding-benchmark's `vericoded/V*_vericoded.rs`) and render its gradable function,
with every spec fn it reaches, as Dafny text that `t/lifter.py` lifts unchanged.

Why Dafny text. The lifter's intermediate form is the Dafny AST of `t/lift_ast.py`, read
from `dafny resolve --rprint` (t/LIFTER-DESIGN.md section 1). Rendering Verus into the
Dafny surface and letting the lifter resolve it reuses every later stage as it is --
resolve (Dafny types every rendered `var` and rejects an ill-typed rendering), parse,
classify, rewrite, the equivalence lemmas and the differential run of `t/lift_check.py`
-- and forks none of them. The rendering is not trusted: `t/lift_check_verus.py` proves
the lifted spec equivalent to the SOURCE spec in Verus itself, on the source's own
types, and the lifted program is graded in seven kernels. The body needs no fidelity
argument: whatever program the lift holds must verify against a spec proved equivalent
to the source's, or it is not a document.

What the rendering decides, each with the source it rests on (research receipt
030fff794977, the Verus guide, verus-lang.github.io/verus/guide/integers.html):

  * machine integers (i8..i128, isize, u8..u128, usize) become mathematical: signed as
    `int`, unsigned scalars as `nat` (their lower bound kept, their upper bound dropped).
    Ghost arithmetic in Verus already widens to `int`, and exec arithmetic in a verified
    file never overflows, so a verified program computes the same values on its domain.
    The lifted spec is therefore the source spec on a WIDER domain; the equivalence
    harness checks it on the source's own domain and the kernels prove the program on
    the wider one. Recorded as the rewrite `machine-int-widened`.
  * a sequence of unsigned elements (Vec<usize>, &[u8], ...) keeps its lower bound as an
    explicit `forall` requires (parameter) or ensures (result): rewrite
    `unsigned-elements-bound`.
  * ghost `/` and `%` are Euclidean in Verus, as in t (SPEC.md "Division and modulo"),
    and map one to one. Exec `/` and `%` truncate (Rust); they map only when both
    operands are unsigned, where the two conventions agree, and refuse otherwise
    (`exec-signed-div`).
  * views (`v@`), `as int`/`as nat` casts and `#[trigger]` annotations carry no meaning
    once integers are mathematical and are dropped.
  * proof code (`proof { }`, `assert`, lemma calls, `proof fn`) is dropped: a lemma is a
    hint (LIFTER-DESIGN.md section 3 drops Dafny lemmas the same way).

What it refuses, each by name (the refusal list feeds the t features track):
floats (`float`), structs/enums/Option/tuples (`datatype`), `&mut` parameters
(`mut-ref-param`), `loop`/`break`/`continue` (`loop-exit`), closures and higher-order
sequence operations (`higher-order`), `match` (`match`), `choose` (`choose`), sets and
maps (`set`, `map`), multisets (`multiset`), trust holes (`assume`, `admit`,
`external_body`: `trust-hole`), uninterpreted spec fns (`bodyless-spec-fn`), signed exec
division (`exec-signed-div`), and any token the reader does not know
(`verus-unparsed`). A refusal is never a guess.

INVENTED: no tool translates Verus to Dafny (searched arXiv, GitHub, StackExchange,
receipt 030fff794977); the reader is a recursive-descent parser over the subset the
vericoding files use, written for this lift.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


class VerusRefusal(Exception):
    """A construct the rendering will not lower, with the refusal reason and what was seen."""

    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


# ------------------------------------------------------------------ lexer --

_PUNCT = sorted("""<==> ==> <== === !== =~= !~= =~~= &&& ||| == != <= >= && || -> => :: ..= .. += -= *= /= %=
<< >> ( ) [ ] { } < > , ; : . @ # ! + - * / % = | & ^ ? '""".split(), key=len, reverse=True)
_NUM = re.compile(r"(0x[0-9a-fA-F_]+|0b[01_]+|[0-9][0-9_]*)(i8|i16|i32|i64|i128|isize|u8|u16|u32|u64|u128|usize|int|nat)?")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_CHAR = re.compile(r"'(\\.|\\u\{[0-9a-fA-F]+\}|[^'\\])'")
_STRING = re.compile(r'"(\\.|[^"\\])*"')
_FLOAT = re.compile(r"[0-9][0-9_]*\.[0-9][0-9_]*(e[+-]?[0-9]+)?(f32|f64)?|[0-9][0-9_]*(f32|f64)")


@dataclass
class Tok:
    kind: str      # "id" | "num" | "char" | "str" | "float" | "p" (punctuation) | "eof"
    text: str
    line: int
    value: object = None


def tokenize(src: str) -> list[Tok]:
    toks: list[Tok] = []
    i, line, n = 0, 1, len(src)
    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
            continue
        if c.isspace():
            i += 1
            continue
        if src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if src.startswith("/*", i):
            depth, j = 1, i + 2
            while j < n and depth:
                if src.startswith("/*", j):
                    depth, j = depth + 1, j + 2
                elif src.startswith("*/", j):
                    depth, j = depth - 1, j + 2
                else:
                    j += 1
            line += src.count("\n", i, j)
            i = j
            continue
        m = _FLOAT.match(src, i)
        if m and (m.group(0).count(".") == 1 or m.group(3)) and not src.startswith("..", m.start() + len(m.group(0).split(".")[0])):
            toks.append(Tok("float", m.group(0), line))
            i = m.end()
            continue
        m = _NUM.match(src, i)
        if m:
            digits = m.group(1).replace("_", "")
            val = int(digits, 0) if digits[:2] in ("0x", "0b") else int(digits)
            toks.append(Tok("num", m.group(0), line, (val, m.group(2))))
            i = m.end()
            continue
        m = _IDENT.match(src, i)
        if m:
            toks.append(Tok("id", m.group(0), line))
            i = m.end()
            continue
        if c == "'":
            m = _CHAR.match(src, i)
            if m:
                toks.append(Tok("char", m.group(0), line))
                i = m.end()
                continue
            # a lifetime ('a, 'static)
            m = _IDENT.match(src, i + 1)
            if m:
                toks.append(Tok("lifetime", "'" + m.group(0), line))
                i = m.end()
                continue
        if c == '"':
            m = _STRING.match(src, i)
            if m:
                toks.append(Tok("str", m.group(0), line))
                line += m.group(0).count("\n")
                i = m.end()
                continue
        for p in _PUNCT:
            if src.startswith(p, i):
                toks.append(Tok("p", p, line))
                i += len(p)
                break
        else:
            raise VerusRefusal("verus-unparsed", f"character {c!r} at line {line}")
    toks.append(Tok("eof", "", line))
    return toks


# -------------------------------------------------------------------- AST --
# Expressions and statements are plain tuples: (tag, ...). Types are strings in the
# rendering's vocabulary ("int", "nat", "bool", "char", "seq<int>", ...), or a tuple
# ("refuse", reason, text) for a type the rendering refuses when it is reached.

@dataclass
class VType:
    """A Verus type as read, plus its Dafny rendering. `kind` is "int" (signed machine or
    int), "nat" (unsigned machine or nat), "bool", "char", "seq" (with `elem`), "unit",
    or "refuse" (with `reason`)."""
    kind: str
    text: str
    elem: Optional["VType"] = None
    reason: str = ""
    parts: tuple = ()        # a pair's two component types (kind "pair")

    def dafny(self) -> str:
        if self.kind == "refuse":
            raise VerusRefusal(self.reason, self.text)
        if self.kind == "seq":
            inner = self.elem.dafny()
            return "seq<int>" if inner == "nat" else f"seq<{inner}>"
        return {"int": "int", "nat": "nat", "bool": "bool", "char": "char"}[self.kind]

    @property
    def unsigned_elems(self) -> bool:
        return self.kind == "seq" and self.elem is not None and self.elem.kind == "nat"


SIGNED = {"i8", "i16", "i32", "i64", "i128", "isize", "int"}
UNSIGNED = {"u8", "u16", "u32", "u64", "u128", "usize", "nat"}
SEQ_HEADS = {"Vec", "Seq"}


@dataclass
class Param:
    name: str
    type: VType
    mut: bool = False
    type_src: str = ""      # the type as written (token text), for the equivalence harness


@dataclass
class SpecFn:
    name: str
    params: list[Param]
    ret: VType
    body: object            # expression tuple, None when bodyless
    decreases: list = field(default_factory=list)
    line: int = 0
    text: str = ""          # the whole item as written (token text), for the equivalence harness


@dataclass
class ExecFn:
    name: str
    params: list[Param]
    ret_name: Optional[str]
    ret: VType
    requires: list
    ensures: list
    decreases: list
    body: list              # statements
    attrs: list[str]
    line: int = 0
    requires_src: list = field(default_factory=list)   # each clause as written (token text)
    ensures_src: list = field(default_factory=list)
    ret_src: str = ""


@dataclass
class VerusFile:
    spec_fns: dict[str, SpecFn]
    exec_fns: dict[str, ExecFn]
    proof_fns: set[str]
    datatypes: set[str]
    consts: dict[str, object]
    holes: list[str]
    const_text: dict = field(default_factory=dict)     # const items as written
    failed: dict = field(default_factory=dict)         # fn name -> (reason, detail) of an unreadable item
    lemmas: dict = field(default_factory=dict)         # proof fns with an ensures and no result


# ----------------------------------------------------------------- parser --

class Parser:
    def __init__(self, toks: list[Tok]):
        self.toks = toks
        self.i = 0
        self.last_texts: list[str] = []
        self.item_start: Optional[int] = None

    def text(self, a: int, b: int) -> str:
        """Tokens a..b-1 as source text (whitespace normalised, comments gone; an inner
        attribute's `#![` kept glued, which rustc's parser requires)."""
        return re.sub(r"# ! \[", "#![", " ".join(t.text for t in self.toks[a:b]))

    # token helpers
    def peek(self, k: int = 0) -> Tok:
        return self.toks[min(self.i + k, len(self.toks) - 1)]

    def at(self, text: str, k: int = 0) -> bool:
        t = self.peek(k)
        return t.text == text and t.kind in ("p", "id")

    def take(self) -> Tok:
        t = self.toks[self.i]
        self.i += 1
        return t

    def expect(self, text: str) -> Tok:
        t = self.take()
        if t.text != text:
            raise VerusRefusal("verus-unparsed", f"expected {text!r}, found {t.text!r} at line {t.line}")
        return t

    def accept(self, text: str) -> bool:
        if self.at(text):
            self.i += 1
            return True
        return False

    def skip_balanced(self) -> None:
        """Skip one balanced (...) / [...] / {...} group starting at the current token
        (or at the next `{`, when recovering from a clause the reader could not read)."""
        while self.peek().text not in ("(", "[", "{"):
            if self.take().kind == "eof":
                raise VerusRefusal("verus-unparsed", "unbalanced group")
        opener = self.take().text
        closer = {"(": ")", "[": "]", "{": "}"}[opener]
        depth = 1
        while depth:
            t = self.take()
            if t.kind == "eof":
                raise VerusRefusal("verus-unparsed", "unbalanced group")
            if t.kind == "p" and t.text == opener:
                depth += 1
            elif t.kind == "p" and t.text == closer:
                depth -= 1

    def skip_generics(self) -> str:
        """Skip `<...>`, returning its text (generics refuse when they reach the target)."""
        start = self.i
        depth = 0
        while True:
            t = self.take()
            if t.text == "<":
                depth += 1
            elif t.text == ">":
                depth -= 1
                if depth == 0:
                    break
            elif t.text == ">>":
                depth -= 2
                if depth <= 0:
                    break
            elif t.kind == "eof":
                raise VerusRefusal("verus-unparsed", "unbalanced generics")
        return " ".join(x.text for x in self.toks[start:self.i])

    # ---------------------------------------------------------------- types --

    def parse_type(self) -> VType:
        t = self.peek()
        if self.accept("&"):
            if self.peek().kind == "lifetime":
                self.take()
            mut = self.accept("mut")
            inner = self.parse_type()
            if mut:
                return VType("refuse", "&mut " + inner.text, reason="mut-ref-param")
            return inner
        if self.at("("):
            self.take()
            if self.accept(")"):
                return VType("unit", "()")
            parts = [self.parse_type()]
            while self.accept(","):
                if self.at(")"):
                    break
                parts.append(self.parse_type())
            self.expect(")")
            if len(parts) == 1:
                return parts[0]
            text = "(" + ", ".join(p.text for p in parts) + ")"
            if len(parts) == 2 and all(p.kind in ("int", "nat", "bool") for p in parts):
                # SPEC.md "Pairs": one value of two base components; the lifter lifts a
                # two-result Dafny method as exactly that (lift_rewrite, multi-return-pair)
                return VType("pair", text, parts=tuple(parts))
            return VType("refuse", text, reason="tuple")
        if self.at("["):
            self.take()
            elem = self.parse_type()
            if self.accept(";"):
                self.parse_expr()
                self.expect("]")
                return VType("refuse", f"[{elem.text}; N]", reason="fixed-array")
            self.expect("]")
            return VType("seq", f"[{elem.text}]", elem=elem)
        if t.kind != "id":
            raise VerusRefusal("verus-unparsed", f"type at {t.text!r} line {t.line}")
        name = self.take().text
        while self.at("::"):
            self.take()
            name = self.take().text
        args: list[VType] = []
        if self.at("<"):
            self.take()
            if not self.at(">"):
                args.append(self.parse_type())
                while self.accept(","):
                    args.append(self.parse_type())
            if self.at(">>"):
                # split `>>` closing two generic lists
                self.toks[self.i] = Tok("p", ">", t.line)
                self.toks.insert(self.i, Tok("p", ">", t.line))
            self.expect(">")
        if name in SIGNED:
            return VType("int", name)
        if name in UNSIGNED:
            return VType("nat", name)
        if name == "bool":
            return VType("bool", name)
        if name == "char":
            return VType("char", name)
        if name in ("f32", "f64"):
            return VType("refuse", name, reason="float")
        if name in SEQ_HEADS and len(args) == 1:
            elem = args[0]
            text = f"{name}<{elem.text}>"
            if elem.kind == "refuse":
                return VType("refuse", text, reason=elem.reason)
            if elem.kind == "pair":
                return VType("refuse", text, reason="tuple")
            if elem.kind == "seq":
                if elem.elem.kind == "seq":
                    return VType("refuse", text, reason="nested-seq-depth")
                return VType("seq", text, elem=elem)
            if elem.kind == "unit":
                return VType("refuse", text, reason="verus-unparsed")
            return VType("seq", text, elem=elem)
        if name in ("String", "str"):
            return VType("seq", name, elem=VType("char", "char"))
        if name == "Box" and len(args) == 1:
            return args[0]
        if name in ("Option", "Result"):
            return VType("refuse", name, reason="datatype")
        if name in ("Set",):
            return VType("refuse", name, reason="set")
        if name in ("Map",):
            return VType("refuse", name, reason="map")
        if name in ("Multiset",):
            return VType("refuse", name, reason="multiset")
        if name in ("HashMap", "HashSet", "BTreeMap"):
            return VType("refuse", name, reason="map")
        return VType("refuse", name, reason="datatype")

    # ---------------------------------------------------------- expressions --
    # Binding powers, lowest first (Verus operator precedence: <==> below ==>/<==
    # below || below && below comparisons below bitwise below shifts below + - below
    # * / % below `as` below unary below postfix).

    BIN = {
        "<==>": (1, "right"), "==>": (2, "right"), "<==": (2, "left"),
        "||": (3, "left"), "&&": (4, "left"),
        "==": (5, "chain"), "!=": (5, "chain"), "<": (5, "chain"), "<=": (5, "chain"),
        ">": (5, "chain"), ">=": (5, "chain"), "===": (5, "chain"), "!==": (5, "chain"),
        "=~=": (5, "chain"), "!~=": (5, "chain"), "=~~=": (5, "chain"),
        "|": (6, "left"), "^": (7, "left"), "&": (8, "left"),
        "<<": (9, "left"), ">>": (9, "left"),
        "+": (10, "left"), "-": (10, "left"),
        "*": (11, "left"), "/": (11, "left"), "%": (11, "left"),
    }

    def parse_expr(self, min_bp: int = 0, no_struct: bool = False) -> object:
        # prefix bullets `&&& a &&& b` / `||| a ||| b`
        if self.at("&&&") or self.at("|||"):
            op = self.peek().text
            parts = []
            while self.accept(op):
                parts.append(self.parse_expr(4 if op == "&&&" else 3, no_struct))
            return ("and" if op == "&&&" else "or", parts)
        if self.at("forall") or self.at("exists"):
            if self.peek(1).text in ("|", "||"):
                return self.parse_quant()
        if self.at("|") or self.at("||"):
            return self.parse_closure()
        lhs = self.parse_unary(no_struct)
        while True:
            t = self.peek()
            if t.kind == "p" and t.text == "&&&":
                # infix `&&&` (lower-precedence and)
                if min_bp > 1:
                    break
                self.take()
                rhs = self.parse_expr(2, no_struct)
                lhs = ("and", [lhs, rhs])
                continue
            if t.kind != "p" or t.text not in self.BIN:
                break
            bp, assoc = self.BIN[t.text]
            if bp < min_bp:
                break
            op = self.take().text
            if assoc == "chain":
                operands, ops = [lhs], []
                while True:
                    operands.append(self.parse_expr(bp + 1, no_struct))
                    ops.append(op)
                    nt = self.peek()
                    if nt.kind == "p" and nt.text in self.BIN and self.BIN[nt.text][1] == "chain":
                        op = self.take().text
                        continue
                    break
                lhs = ("chain", ops, operands)
                continue
            rhs = self.parse_expr(bp if assoc == "right" else bp + 1, no_struct)
            lhs = ("bin", op, lhs, rhs)
        return lhs

    def parse_quant(self) -> object:
        kind = self.take().text
        binders: list[Param] = []
        if self.accept("||"):
            raise VerusRefusal("verus-unparsed", "quantifier with no binder")
        self.expect("|")
        while not self.at("|"):
            name = self.take().text
            ty = VType("int", "int")
            if self.accept(":"):
                ty = self.parse_type()
            binders.append(Param(name, ty))
            if not self.accept(","):
                break
        self.expect("|")
        body = self.parse_expr(0)
        return ("quant", kind, binders, body)

    def parse_closure(self) -> object:
        """`|x: T, y| body`: kept as a node so `.map(|i, x| x as int)` can be read as the
        identity it is once integers are mathematical; any other use refuses."""
        params: list[Param] = []
        if not self.accept("||"):
            self.expect("|")
            while not self.at("|"):
                name = self.take().text
                ty = VType("int", "int")
                if self.accept(":"):
                    ty = self.parse_type()
                params.append(Param(name, ty))
                if not self.accept(","):
                    break
            self.expect("|")
        body = self.parse_expr(0)
        return ("closure", params, body)

    def parse_unary(self, no_struct: bool = False) -> object:
        t = self.peek()
        if t.kind == "p" and t.text == "!":
            self.take()
            return ("not", self.parse_unary(no_struct))
        if t.kind == "p" and t.text == "-":
            self.take()
            return ("neg", self.parse_unary(no_struct))
        if t.kind == "p" and t.text == "&":
            self.take()
            self.accept("mut")
            return self.parse_unary(no_struct)
        if t.kind == "p" and t.text == "*":
            self.take()
            return self.parse_unary(no_struct)
        if t.kind == "p" and t.text == "#":
            self.skip_attr()
            return self.parse_unary(no_struct)
        e = self.parse_postfix(self.parse_primary(no_struct))
        while self.at("as"):
            self.take()
            ty = self.parse_type()
            e = ("cast", e, ty)
            e = self.parse_postfix(e)
        return e

    def skip_attr(self) -> str:
        self.expect("#")
        self.accept("!")
        start = self.i
        self.skip_balanced()
        return " ".join(x.text for x in self.toks[start:self.i])

    def parse_args(self) -> list:
        self.expect("(")
        args = []
        while not self.at(")"):
            args.append(self.parse_expr(0))
            if not self.accept(","):
                break
        self.expect(")")
        return args

    def parse_postfix(self, e: object) -> object:
        while True:
            if self.at("@"):
                self.take()
                e = ("view", e)
            elif self.at("["):
                self.take()
                idx = self.parse_expr(0)
                self.expect("]")
                e = ("index", e, idx)
            elif self.at("."):
                self.take()
                t = self.take()
                if t.kind == "num":
                    e = ("field", e, t.text)
                    continue
                name = t.text
                if self.at("::"):   # turbofish .method::<T>()
                    self.take()
                    self.skip_generics()
                if self.at("("):
                    e = ("method", e, name, self.parse_args())
                else:
                    e = ("field", e, name)
            elif self.at("?"):
                raise VerusRefusal("datatype", "`?` operator")
            else:
                return e

    def parse_primary(self, no_struct: bool = False) -> object:
        t = self.peek()
        if t.kind == "num":
            self.take()
            return ("int", t.value[0])
        if t.kind == "float":
            raise VerusRefusal("float", t.text)
        if t.kind == "char":
            self.take()
            return ("char", t.text)
        if t.kind == "str":
            self.take()
            return ("str", t.text)
        if t.kind == "p" and t.text == "(":
            self.take()
            if self.accept(")"):
                return ("unit",)
            e = self.parse_expr(0)
            if self.at(","):
                items = [e]
                while self.accept(","):
                    if self.at(")"):
                        break
                    items.append(self.parse_expr(0))
                self.expect(")")
                return ("tuple", items)
            self.expect(")")
            return ("paren", e)
        if t.kind == "p" and t.text == "[":
            raise VerusRefusal("fixed-array", f"array literal at line {t.line}")
        if t.kind == "p" and t.text == "{":
            return ("block", self.parse_block())
        if t.kind != "id":
            raise VerusRefusal("verus-unparsed", f"expression at {t.text!r} line {t.line}")
        word = t.text
        if word in ("true", "false"):
            self.take()
            return ("bool", word == "true")
        if word == "if":
            return self.parse_if_expr()
        if word == "match" or (word == "matches" and self.peek(1).text == "!"):
            raise VerusRefusal("match", f"line {t.line}")
        if word in ("choose",):
            raise VerusRefusal("choose", f"line {t.line}")
        if word in ("loop",):
            raise VerusRefusal("loop-exit", f"`loop` at line {t.line}")
        if word == "old":
            raise VerusRefusal("mut-ref-param", f"`old` at line {t.line}")
        if word in ("Some", "None", "Ok", "Err"):
            raise VerusRefusal("datatype", word)
        if word == "move":
            raise VerusRefusal("higher-order", "closure")
        # macros: seq![...], vec![...], vec![x; n], assert!, etc.
        if self.peek(1).text == "!" and self.peek(2).text in ("[", "("):
            self.take()
            self.take()
            return self.parse_macro(word, t.line)
        self.take()
        path = [word]
        while self.at("::"):
            self.take()
            if self.at("<"):
                self.skip_generics()
                continue
            path.append(self.take().text)
        if self.at("(") :
            return ("call", "::".join(path), self.parse_args())
        if len(path) == 1:
            if not no_struct and self.at("{") and word[:1].isupper():
                raise VerusRefusal("datatype", f"struct literal {word}")
            return ("var", word)
        return ("path", "::".join(path))

    def parse_macro(self, name: str, line: int) -> object:
        opener = self.peek().text
        closer = "]" if opener == "[" else ")"
        self.take()
        items = []
        repeat = None
        while not self.at(closer):
            items.append(self.parse_expr(0))
            if self.accept(";"):
                repeat = self.parse_expr(0)
                break
            if not self.accept(","):
                break
        self.expect(closer)
        if name in ("seq", "vec"):
            if repeat is not None:
                return ("fill", repeat, items[0])
            return ("seqlit", items)
        if name in ("assert", "assume"):
            return ("unit",)
        raise VerusRefusal("verus-unparsed", f"macro {name}! at line {line}")

    def parse_if_expr(self) -> object:
        self.expect("if")
        cond = self.parse_expr(0, no_struct=True)
        then = self.parse_block()
        if self.accept("else"):
            if self.at("if"):
                other = [("expr", self.parse_if_expr())]
            else:
                other = self.parse_block()
        else:
            other = None
        return ("if", cond, then, other)

    # ----------------------------------------------------------- statements --

    def parse_block(self) -> list:
        self.expect("{")
        stmts = []
        while not self.at("}"):
            if self.accept(";"):
                continue
            stmts.append(self.parse_stmt())
        self.expect("}")
        return stmts

    def parse_stmt(self) -> object:
        t = self.peek()
        if t.kind == "p" and t.text == "#":
            attr = self.skip_attr()
            return ("attr", attr)
        if t.kind == "id":
            w = t.text
            if w == "let":
                self.take()
                ghost = False
                if self.at("ghost") or self.at("tracked"):
                    self.take()
                    ghost = True
                mut = self.accept("mut")
                if self.at("("):
                    raise VerusRefusal("tuple", f"tuple pattern at line {t.line}")
                name = self.take().text
                ty = None
                if self.accept(":"):
                    ty = self.parse_type()
                init = None
                if self.accept("="):
                    init = self.parse_expr(0)
                self.accept(";")
                return ("let", name, ty, init, mut, ghost)
            if w == "while":
                self.take()
                cond = self.parse_expr(0, no_struct=True)
                spec = self.parse_loop_spec()
                body = self.parse_block()
                return ("while", cond, spec, body, t.line)
            if w == "for":
                self.take()
                var = self.take().text
                self.expect("in")
                lo = self.parse_expr(9, no_struct=True)   # stop before `..`
                if not self.at(".."):
                    raise VerusRefusal("higher-order", f"`for` over an iterator at line {t.line}")
                self.take()
                hi = self.parse_expr(9, no_struct=True)
                spec = self.parse_loop_spec()
                body = self.parse_block()
                return ("for", var, lo, hi, spec, body, t.line)
            if w == "loop":
                raise VerusRefusal("loop-exit", f"`loop` at line {t.line}")
            if w in ("break", "continue"):
                raise VerusRefusal("loop-exit", f"`{w}` at line {t.line}")
            if w == "return":
                self.take()
                e = None if self.at(";") or self.at("}") else self.parse_expr(0)
                self.accept(";")
                return ("return", e)
            if w == "proof" and self.peek(1).text == "{":
                self.take()
                self.skip_balanced()
                return ("proof",)
            if w in ("assert", "assume", "admit") and self.peek(1).text == "(":
                self.take()
                self.skip_balanced()
                if w != "assert":
                    raise VerusRefusal("trust-hole", w)
                if self.at("by"):
                    self.take()
                    if self.at("("):
                        self.skip_balanced()
                    if self.at("{"):
                        self.skip_balanced()
                self.accept(";")
                return ("proof",)
            if w == "if":
                e = self.parse_if_expr()
                self.accept(";")
                return ("expr", e)
        e = self.parse_expr(0)
        for op in ("=", "+=", "-=", "*=", "/=", "%="):
            if self.at(op):
                self.take()
                rhs = self.parse_expr(0)
                self.accept(";")
                if op != "=":
                    rhs = ("bin", op[0], e, rhs)
                return ("assign", e, rhs)
        if self.accept(";"):
            return ("exprstmt", e)
        return ("expr", e)

    def parse_loop_spec(self) -> dict:
        spec = {"invariant": [], "decreases": [], "ensures": []}
        while True:
            w = self.peek().text
            if w in ("invariant", "invariant_except_break", "invariant_ensures"):
                self.take()
                spec["invariant"] += self.parse_clause_list()
                if w != "invariant":
                    spec["except_break"] = True
            elif w == "decreases":
                self.take()
                spec["decreases"] += self.parse_clause_list()
            elif w == "ensures":
                self.take()
                spec["ensures"] += self.parse_clause_list()
            else:
                return spec

    def parse_clause_list(self) -> list:
        """A comma-separated clause list ending at `{`, `;` or the next clause keyword."""
        out, texts = [], []
        stops = {"requires", "ensures", "decreases", "invariant", "invariant_except_break",
                 "recommends", "returns", "via", "opens_invariants", "no_unwind", "when"}
        while not self.at("{") and not self.at(";") and self.peek().text not in stops:
            a = self.i
            out.append(self.parse_expr(0, no_struct=True))
            texts.append(self.text(a, self.i))
            if not self.accept(","):
                break
        self.last_texts = texts
        return out

    # ---------------------------------------------------------------- items --

    def parse_params(self) -> list[Param]:
        self.expect("(")
        params = []
        while not self.at(")"):
            if self.at("#"):
                self.skip_attr()
            self.accept("tracked")
            self.accept("ghost")
            mut = self.accept("mut")
            name = self.take().text
            self.expect(":")
            a = self.i
            ty = self.parse_type()
            params.append(Param(name, ty, mut, self.text(a, self.i)))
            if not self.accept(","):
                break
        self.expect(")")
        return params

    def parse_file(self) -> VerusFile:
        vf = VerusFile({}, {}, set(), set(), {}, [])
        # find `verus! {`
        while not (self.at("verus") and self.peek(1).text == "!"):
            if self.peek().kind == "eof":
                raise VerusRefusal("verus-unparsed", "no verus! block")
            self.take()
        self.take()
        self.take()
        self.expect("{")
        attrs: list[str] = []
        while not self.at("}"):
            if self.peek().kind == "eof":
                raise VerusRefusal("verus-unparsed", "unterminated verus! block")
            before = self.i
            try:
                attrs = self.parse_item(vf, attrs)
            except VerusRefusal as r:
                # an item the reader cannot read is recorded against its name and
                # skipped; only a target that IS that item refuses (with this reason)
                m = re.search(r"\bfn\s+([A-Za-z_]\w*)", self.text(self.item_start or self.i, self.i + 1))
                if m:
                    vf.failed.setdefault(m.group(1), (r.reason, r.detail))
                self.recover()
                if self.i == before:
                    self.take()          # always make progress
                attrs = []
                self.item_start = None
        return vf

    def recover(self) -> None:
        """Skip to the end of the item being read: its body's closing brace or its `;`."""
        depth = 0
        while True:
            t = self.peek()
            if t.kind == "eof":
                return
            if t.kind == "p" and t.text == "{":
                self.skip_balanced()
                if depth == 0:
                    return
                continue
            if t.kind == "p" and t.text in ("(", "["):
                self.skip_balanced()
                continue
            if t.kind == "p" and t.text == "}" and depth == 0:
                return            # the verus! block's own close: leave it for the caller
            self.take()
            if t.kind == "p" and t.text == ";" and depth == 0:
                return

    def parse_item(self, vf: VerusFile, attrs: list[str]) -> list[str]:
        """One item (or one attribute or modifier of the next), returning the pending
        attributes."""
        if True:
            t = self.peek()
            if t.kind == "eof":
                raise VerusRefusal("verus-unparsed", "unterminated verus! block")
            if self.item_start is None:
                self.item_start = self.i
            if t.kind == "eof":
                raise VerusRefusal("verus-unparsed", "unterminated verus! block")
            if t.text == "#":
                attrs.append(self.skip_attr())
                return attrs
            if t.text in ("pub", "open", "closed", "uninterp", "broadcast", "axiom"):
                if t.text in ("uninterp", "axiom"):
                    attrs.append(t.text)
                self.take()
                if self.at("("):
                    self.skip_balanced()
                return attrs
            if t.text == "use":
                while not self.accept(";"):
                    self.take()
                self.item_start = None
                return []
            if t.text in ("spec", "proof", "exec") and self.peek(1).text == "fn":
                mode = self.take().text
                self.parse_fn(vf, mode, attrs)
                self.item_start = None
                return []
            if t.text == "fn":
                self.parse_fn(vf, "exec", attrs)
                self.item_start = None
                return []
            if t.text in ("struct", "enum", "trait", "type", "impl", "mod", "union"):
                self.take()
                name = self.peek().text
                vf.datatypes.add(name)
                while not self.at("{") and not self.at(";"):
                    self.take()
                if self.at("{"):
                    self.skip_balanced()
                else:
                    self.take()
                self.item_start = None
                return []
            if t.text in ("const", "static"):
                self.take()
                self.accept("mut")
                name = self.take().text
                self.expect(":")
                self.parse_type()
                self.expect("=")
                vf.consts[name] = self.parse_expr(0)
                self.accept(";")
                vf.const_text[name] = self.text(self.item_start or 0, self.i)
                self.item_start = None
                return []
            if t.text == "global":
                while not self.accept(";"):
                    self.take()
                return attrs
            raise VerusRefusal("verus-unparsed", f"item at {t.text!r} line {t.line}")

    def parse_fn(self, vf: VerusFile, mode: str, attrs: list[str]) -> None:
        line = self.expect("fn").line
        name = self.take().text
        if self.at("<"):
            gen = self.skip_generics()
            attrs = attrs + ["generics " + gen]
        params = self.parse_params()
        ret_name, ret, ret_src = None, VType("unit", "()"), "()"
        if self.accept("->"):
            if self.at("(") and self.peek(1).kind == "id" and self.peek(2).text == ":":
                self.take()
                ret_name = self.take().text
                self.expect(":")
                a = self.i
                ret = self.parse_type()
                ret_src = self.text(a, self.i)
                self.expect(")")
            else:
                a = self.i
                ret = self.parse_type()
                ret_src = self.text(a, self.i)
        requires, ensures, decreases = [], [], []
        requires_src, ensures_src = [], []
        while True:
            w = self.peek().text
            if w in ("requires", "recommends"):
                self.take()
                clauses = self.parse_clause_list()
                if w == "requires":
                    requires += clauses
                    requires_src += self.last_texts
            elif w == "ensures":
                self.take()
                ensures += self.parse_clause_list()
                ensures_src += self.last_texts
            elif w == "decreases":
                self.take()
                decreases += self.parse_clause_list()
            elif w in ("via", "when", "opens_invariants", "no_unwind", "returns"):
                self.take()
                self.parse_clause_list()
            elif w == "by" and self.peek(1).text == "(":
                self.take()
                self.skip_balanced()
            else:
                break
        holes = [a for a in attrs if re.search(r"external|assume_specification|admit|uninterp|axiom", a)]
        if self.accept(";"):
            if mode == "spec":
                vf.spec_fns[name] = SpecFn(name, params, ret, None, decreases, line,
                                           self.text(self.item_start or 0, self.i))
            elif mode == "exec":
                vf.holes.append(f"bodyless fn {name}")
            return
        if mode == "proof":
            vf.proof_fns.add(name)
            if ret_name is not None:
                # a proof fn that returns a value (DafnyBench's lemmas-with-results) is a
                # gradable function too; its body is ghost code
                start = self.i
                try:
                    body = self.parse_block()
                except VerusRefusal as r:
                    self.i = start
                    self.skip_balanced()
                    body = [("refused", r.reason, r.detail)]
                vf.exec_fns[name] = ExecFn(name, params, ret_name, ret, requires, ensures, decreases, body,
                                           attrs + ["proof"], line, requires_src, ensures_src, ret_src)
                if holes:
                    vf.holes.append(f"{name}: {holes}")
                return
            if ensures:
                # a lemma: kept so a corpus of lemmas (vstd) can lift each as a task whose
                # result is a token and whose ensures is the lemma's (lift_lemma below)
                ok = "ok"
                while ok in {p.name for p in params}:
                    ok += "_"
                vf.lemmas[name] = ExecFn(name, params, ok, VType("bool", "bool"), requires, ensures, decreases,
                                         [("expr", ("bool", True))], attrs + ["proof", "lemma"], line,
                                         requires_src, ensures_src, "bool")
            self.skip_balanced()
            if holes:
                vf.holes.append(f"{name}: {holes}")
            return
        if mode == "spec":
            start = self.i
            try:
                blk = self.parse_block()
                body = _block_to_expr(blk)
            except VerusRefusal as r:
                # keep the refusal to raise only if the target reaches this spec fn
                self.i = start
                self.skip_balanced()
                body = ("refused", r.reason, r.detail)
            vf.spec_fns[name] = SpecFn(name, params, ret, body, decreases, line,
                                       self.text(self.item_start or 0, self.i))
            if holes:
                vf.holes.append(f"{name}: {holes}")
            return
        start = self.i
        try:
            body = self.parse_block()
        except VerusRefusal as r:
            self.i = start
            self.skip_balanced()
            body = [("refused", r.reason, r.detail)]
        vf.exec_fns[name] = ExecFn(name, params, ret_name, ret, requires, ensures, decreases, body,
                                   attrs, line, requires_src, ensures_src, ret_src)


def _block_to_expr(stmts: list) -> object:
    """A spec fn body block `{ let x = e; ...; tail }` as one expression."""
    if not stmts:
        raise VerusRefusal("verus-unparsed", "empty spec fn body")
    *lets, tail = stmts
    if tail[0] != "expr":
        raise VerusRefusal("verus-unparsed", "spec fn body without a tail expression")
    e = tail[1]
    for s in reversed(lets):
        if s[0] == "let" and s[3] is not None:
            e = ("letin", s[1], s[3], e)
        elif s[0] in ("proof", "attr"):
            continue
        else:
            raise VerusRefusal("verus-unparsed", f"statement {s[0]} in a spec fn body")
    return e


# --------------------------------------------------------------- rendering --

# Dafny reserved words a Verus identifier may use (dafny.org/dafny/DafnyRef/DafnyRef, "Reserved
# words"); a name that is one, or that begins with `_` (not a Dafny identifier start), is
# renamed on the way out, and the lifter's own rename map records the t name it becomes.
DAFNY_RESERVED = {
    "abstract", "array", "as", "assert", "assume", "bool", "break", "by", "calc", "case", "char",
    "class", "codatatype", "const", "constructor", "continue", "datatype", "decreases", "else",
    "ensures", "exists", "expect", "export", "extends", "false", "forall", "fresh", "function",
    "ghost", "if", "imap", "import", "in", "include", "int", "invariant", "is", "iset", "iterator",
    "label", "lemma", "map", "match", "method", "modifies", "modify", "module", "multiset", "nameonly",
    "nat", "new", "newtype", "null", "object", "old", "opaque", "opened", "predicate", "print",
    "provides", "reads", "real", "refines", "requires", "return", "returns", "reveal", "reveals",
    "seq", "set", "static", "string", "then", "this", "trait", "true", "twostate", "type", "unchanged",
    "var", "while", "witness", "yield", "yields", "least", "greatest", "older", "hide",
}


def dn(name: str) -> str:
    """The Dafny spelling of a Verus identifier."""
    if name.startswith("_"):
        name = "u" + name
    if name in DAFNY_RESERVED:
        name = name + "_v"
    return name


def _strip(e):
    while isinstance(e, tuple) and e and e[0] in ("paren", "view"):
        e = e[1]
    return e


class Renderer:
    """Print the Verus tuple AST as Dafny. `ghost` is True in spec positions (spec fn
    bodies, requires/ensures, invariants, decreases), where `/` and `%` are Euclidean;
    False in exec code, where they truncate."""

    def __init__(self, vf: VerusFile, types: dict[str, VType]):
        self.vf = vf
        self.types = dict(types)      # name -> VType for params/locals in scope
        self.rewrites: list[str] = []
        self.declared: set[str] = set(types)   # every name bound so far (dafny forbids redeclaring)
        self.renames: dict[str, str] = {}       # a shadowing `let` gets a fresh dafny name
        self.called_specs: set[str] = set()
        self.called_execs: set[str] = set()
        self.body_ghost = False       # a proof fn's body is ghost code: `/` and `%` are Euclidean

    # --- expression typing, only as much as division and indexing need ---
    def kind_of(self, e) -> Optional[str]:
        e = _strip(e)
        tag = e[0]
        if tag == "var":
            t = self.types.get(e[1])
            return t.kind if t else None
        if tag in ("char",):
            return "char"
        if tag == "cast":
            return e[2].kind
        if tag == "int":
            return None
        if tag == "index":
            base = _strip(e[1])
            if base[0] == "var" and base[1] in self.types and self.types[base[1]].kind == "seq":
                return self.types[base[1]].elem.kind
            return None
        if tag == "method" and e[2] == "len":
            return "nat"
        if tag == "bin" and e[1] in "+*/%":
            a, b = self.kind_of(e[2]), self.kind_of(e[3])
            if a == "nat" and b in ("nat", None) or b == "nat" and a is None:
                return "nat"
        return None

    def expr(self, e, ghost: bool, prec: int = 0) -> str:
        tag = e[0]
        if tag == "int":
            return str(e[1])
        if tag == "bool":
            return "true" if e[1] else "false"
        if tag == "char":
            return e[1]
        if tag == "str":
            return e[1]
        if tag == "var":
            if e[1] in self.vf.consts and e[1] not in self.types:
                return self.expr(self.vf.consts[e[1]], ghost, prec)
            return dn(self.renames.get(e[1], e[1]))
        if tag == "path":
            return self.path_const(e[1])
        if tag == "paren":
            return "(" + self.expr(e[1], ghost) + ")"
        if tag == "view":
            return self.expr(e[1], ghost, prec)
        if tag == "cast":
            target = e[2]
            if target.kind in ("int", "nat"):
                src = self.kind_of(e[1])
                if src == "char":
                    return "(" + self.expr(e[1], ghost) + " as int)"
                if target.kind == "nat" and target.text not in ("nat",) and src == "int":
                    raise VerusRefusal("as-cast", f"signed to {target.text}")
                self.rewrites.append("machine-int-widened")
                return self.expr(e[1], ghost, prec)
            if target.kind == "char":
                return "(" + self.expr(e[1], ghost) + " as char)"
            raise VerusRefusal("as-cast", target.text)
        if tag == "not":
            return "!" + self.expr(e[1], ghost, 99)
        if tag == "neg":
            return "-" + self.expr(e[1], ghost, 99)
        if tag in ("and", "or"):
            op = " && " if tag == "and" else " || "
            return "(" + op.join("(" + self.expr(x, ghost) + ")" for x in e[1]) + ")"
        if tag == "chain":
            ops, operands = e[1], e[2]
            # `===`, `=~=` (extensional) and `=~~=` (deep extensional) are equality on
            # values, which is all a sequence is once views are dropped
            ops = ["==" if o in ("===", "=~=", "=~~=") else "!=" if o in ("!==", "!~=") else o
                   for o in ops]
            parts = [self.expr(operands[0], ghost, 6)]
            for o, x in zip(ops, operands[1:]):
                parts += [o, self.expr(x, ghost, 6)]
            return "(" + " ".join(parts) + ")"
        if tag == "bin":
            op, a, b = e[1], e[2], e[3]
            if op in ("|", "^", "&", "<<", ">>"):
                raise VerusRefusal("bitvector", op)
            if op in ("/", "%") and not ghost:
                ka, kb = self.kind_of(a), self.kind_of(b)
                if not (ka == "nat" and self._nonneg_literal_or_nat(b)):
                    # Rust truncates toward zero; t is Euclidean. With a positive literal
                    # divisor the truncating value is written out exactly:
                    # a / k == (a >= 0 ? a / k : -((-a) / k)), a % k likewise.
                    kb_ = _strip(b)
                    if kb_[0] == "int" and kb_[1] > 0:
                        x, k = self.expr(a, ghost), str(kb_[1])
                        self.rewrites.append("exec-truncating-div-written-out")
                        return f"(if {x} >= 0 then {x} {op} {k} else -((-{x}) {op} {k}))"
                    raise VerusRefusal("exec-signed-div", f"{op} on {ka}/{kb}")
            if op == "<==":
                return "(" + self.expr(b, ghost) + " ==> " + self.expr(a, ghost) + ")"
            return "(" + self.expr(a, ghost, 6) + f" {op} " + self.expr(b, ghost, 6) + ")"
        if tag == "quant":
            kind, binders, body = e[1], e[2], e[3]
            saved = dict(self.types)
            bs = []
            for p in binders:
                if p.type.kind not in ("int", "nat"):
                    raise VerusRefusal("unbounded-quantifier", f"quantifier over {p.type.text}")
                self.types[p.name] = VType("int", "int")
                bs.append(f"{dn(p.name)}: int")
                if p.type.kind == "nat":
                    body = ("bin", "==>" if kind == "forall" else "&&",
                            ("chain", ["<="], [("int", 0), ("var", p.name)]), body)
            text = f"({kind} {', '.join(bs)} :: {self.expr(body, True)})"
            self.types = saved
            return text
        if tag == "index":
            return self.expr(e[1], ghost, 99) + "[" + self.expr(e[2], ghost) + "]"
        if tag == "method":
            return self.method(e, ghost)
        if tag == "field":
            base = _strip(e[1])
            if base[0] == "var" and self.types.get(base[1]) is not None and \
                    self.types[base[1]].kind == "pair" and e[2] in ("0", "1"):
                return dn(self.renames.get(base[1], base[1])) + "_" + e[2]
            raise VerusRefusal("datatype", f"field .{e[2]}")
        if tag == "tuple":
            raise VerusRefusal("tuple", "tuple value outside a result position")
        if tag == "call":
            return self.call(e, ghost)
        if tag == "if":
            cond, then, other = e[1], e[2], e[3]
            if other is None:
                raise VerusRefusal("verus-unparsed", "if without else in an expression")
            return ("(if " + self.expr(cond, ghost) + " then " + self.expr(_block_to_expr(then), ghost)
                    + " else " + self.expr(_block_to_expr(other), ghost) + ")")
        if tag == "block":
            return "(" + self.expr(_block_to_expr(e[1]), ghost) + ")"
        if tag == "letin":
            return f"(var {e[1]} := {self.expr(e[2], ghost)}; {self.expr(e[3], ghost)})"
        if tag == "seqlit":
            return "[" + ", ".join(self.expr(x, ghost) for x in e[1]) + "]"
        if tag == "fill":
            return f"seq({self.expr(e[1], ghost)}, _ => {self.expr(e[2], ghost)})"
        if tag == "refused":
            raise VerusRefusal(e[1], e[2])
        if tag == "closure":
            raise VerusRefusal("higher-order", "closure")
        if tag == "unit":
            raise VerusRefusal("verus-unparsed", "unit value")
        raise VerusRefusal("verus-unparsed", f"expression {tag}")

    def _nonneg_literal_or_nat(self, b) -> bool:
        b = _strip(b)
        if b[0] == "int":
            return b[1] > 0
        return self.kind_of(b) == "nat"

    def path_const(self, path: str) -> str:
        consts = {"i8::MAX": 127, "i8::MIN": -128, "u8::MAX": 255, "i16::MAX": 32767, "i16::MIN": -32768,
                  "u16::MAX": 65535, "i32::MAX": 2147483647, "i32::MIN": -2147483648,
                  "u32::MAX": 4294967295, "i64::MAX": 9223372036854775807,
                  "i64::MIN": -9223372036854775808, "u64::MAX": 18446744073709551615}
        if path in consts:
            return str(consts[path])
        raise VerusRefusal("verus-unparsed", f"path {path}")

    def method(self, e, ghost: bool) -> str:
        recv, name, args = e[1], e[2], e[3]
        r = lambda: self.expr(recv, ghost, 99)
        a = lambda k: self.expr(args[k], ghost)
        if name == "len" and not args:
            return "|" + self.expr(recv, ghost) + "|"
        if name in ("clone", "to_vec", "view", "deep_view", "as_slice", "into", "to_owned") and not args:
            return self.expr(recv, ghost, 99)
        if name in ("index", "spec_index") and len(args) == 1:
            return f"{r()}[{a(0)}]"
        if name == "subrange" and len(args) == 2:
            return f"{r()}[{a(0)}..{a(1)}]"
        if name == "take" and len(args) == 1:
            return f"{r()}[..{a(0)}]"
        if name == "skip" and len(args) == 1:
            return f"{r()}[{a(0)}..]"
        if name == "first" and not args:
            return f"{r()}[0]"
        if name == "last" and not args:
            return f"{r()}[|{self.expr(recv, ghost)}| - 1]"
        if name == "drop_last" and not args:
            return f"{r()}[..|{self.expr(recv, ghost)}| - 1]"
        if name == "drop_first" and not args:
            return f"{r()}[1..]"
        if name in ("push",) and len(args) == 1 and ghost:
            return f"({r()} + [{a(0)}])"
        if name == "add" and len(args) == 1:
            return f"({r()} + {a(0)})"
        if name == "contains" and len(args) == 1:
            return f"({a(0)} in {r()})"
        if name == "update" and len(args) == 2:
            return f"{r()}[{a(0)} := {a(1)}]"
        if name in ("map", "map_values") and len(args) == 1:
            # `.map(|i, x| x as int)` / `.map_values(|x| x as int)`: the identity once
            # integers are mathematical (and `|_i, v| v@` once views are dropped); any
            # other closure is higher-order
            c = args[0]
            if c[0] == "closure" and c[1]:
                last = c[1][-1].name
                body = _strip(c[2])
                while body[0] == "cast" and body[2].kind in ("int", "nat"):
                    body = _strip(body[1])
                if body == ("var", last) and (name == "map_values" or len(c[1]) == 2):
                    self.rewrites.append("machine-int-widened")
                    return self.expr(recv, ghost, prec=99)
            raise VerusRefusal("higher-order", f".{name}(closure)")
        if name == "get" and len(args) == 1:
            return f"{r()}[{a(0)}]"
        if name in ("abs",) and not args:
            x = self.expr(recv, ghost)
            return f"(if {x} < 0 then -{x} else {x})"
        if name in ("to_multiset", "to_set", "filter", "fold_left", "fold_right", "iter", "sort",
                    "rev", "reverse", "insert", "remove", "dom", "is_empty", "unwrap", "is_some",
                    "is_none", "is_digit", "is_alphabetic", "is_uppercase", "is_lowercase",
                    "to_ascii_lowercase", "to_ascii_uppercase", "chars", "as_bytes", "split"):
            reason = {"to_multiset": "multiset", "to_set": "set", "unwrap": "datatype",
                      "is_some": "datatype", "is_none": "datatype", "dom": "map"}.get(name, "higher-order"
                      if name in ("filter", "fold_left", "fold_right", "iter") else "std-method")
            raise VerusRefusal(reason, f".{name}()")
        raise VerusRefusal("std-method", f".{name}()")

    def call(self, e, ghost: bool) -> str:
        name, args = e[1], e[2]
        if name in ("Vec::new", "Seq::empty", "Vec::with_capacity", "Seq::<int>::empty"):
            return "[]"
        if name in ("Seq::new",):
            raise VerusRefusal("higher-order", "Seq::new(n, closure)")
        if name in ("min", "max", "std::cmp::min", "std::cmp::max", "cmp::min", "cmp::max"):
            x, y = (self.expr(args[0], ghost), self.expr(args[1], ghost))
            op = "<=" if name.endswith("min") else ">="
            return f"(if {x} {op} {y} then {x} else {y})"
        if name in ("abs",) and len(args) == 1:
            x = self.expr(args[0], ghost)
            return f"(if {x} < 0 then -{x} else {x})"
        if name in self.vf.spec_fns:
            self.called_specs.add(name)
            return f"{dn(name)}(" + ", ".join(self.expr(x, ghost) for x in args) + ")"
        if name in self.vf.exec_fns:
            self.called_execs.add(name)
            return f"{dn(name)}(" + ", ".join(self.expr(x, ghost) for x in args) + ")"
        if name in self.vf.proof_fns:
            raise VerusRefusal("verus-unparsed", f"proof fn {name} in an expression")
        if name in self.vf.datatypes or name.split("::")[0] in self.vf.datatypes:
            raise VerusRefusal("datatype", name)
        raise VerusRefusal("std-call", name)

    # --- statements ---
    def stmts(self, body: list, ind: str, ret_name: str, lines: list[str], tail_assign: bool) -> None:
        for k, s in enumerate(body):
            last = k == len(body) - 1
            self.stmt(s, ind, ret_name, lines, tail_assign and last)

    def stmt(self, s, ind: str, ret_name: str, lines: list[str], is_tail: bool) -> None:
        tag = s[0]
        if tag in ("proof", "attr"):
            return
        if tag == "refused":
            raise VerusRefusal(s[1], s[2])
        if tag == "let":
            _, name, ty, init, mut, ghost = s
            if ghost:
                self.rewrites.append("ghost-let-as-local")
            vt = ty
            if vt is None and init is not None:
                vt = self.infer(init)
            rhs_text = self.rhs(init) if init is not None else None   # before the new binding
            dname = name
            if name in self.declared:
                k = 1
                while f"{name}_{k}" in self.declared:
                    k += 1
                dname = f"{name}_{k}"
                self.rewrites.append("shadowing-let-renamed")
            self.declared.add(dname)
            self.renames[name] = dname
            if vt is not None:
                self.types[name] = vt
            decl = f"var {dn(dname)}"
            if ty is not None:
                decl += f": {ty.dafny()}"
            if init is None:
                lines.append(f"{ind}{decl};")        # assigned later on every path; dafny checks
                return
            lines.append(f"{ind}{decl} := {rhs_text};")
            return
        if tag == "assign":
            lhs, rhs = _strip(s[1]), s[2]
            if lhs[0] == "var":
                lines.append(f"{ind}{dn(self.renames.get(lhs[1], lhs[1]))} := {self.rhs(rhs)};")
                return
            if lhs[0] == "index" and _strip(lhs[1])[0] == "var":
                v = dn(self.renames.get(_strip(lhs[1])[1], _strip(lhs[1])[1]))
                lines.append(f"{ind}{v} := {v}[{self.expr(lhs[2], self.body_ghost)} := {self.rhs(rhs)}];")
                return
            raise VerusRefusal("verus-unparsed", "assignment target")
        if tag in ("exprstmt", "expr"):
            e = _strip(s[1])
            if e[0] == "method" and e[2] == "push" and _strip(e[1])[0] == "var":
                v = dn(self.renames.get(_strip(e[1])[1], _strip(e[1])[1]))
                lines.append(f"{ind}{v} := {v} + [{self.expr(e[3][0], self.body_ghost)}];")
                return
            if e[0] == "method" and e[2] == "set" and _strip(e[1])[0] == "var" and len(e[3]) == 2:
                v = dn(self.renames.get(_strip(e[1])[1], _strip(e[1])[1]))
                lines.append(f"{ind}{v} := {v}[{self.expr(e[3][0], self.body_ghost)} := {self.expr(e[3][1], self.body_ghost)}];")
                return
            if e[0] == "method" and e[2] == "pop" and not e[3] and _strip(e[1])[0] == "var" and tag == "exprstmt":
                v = dn(self.renames.get(_strip(e[1])[1], _strip(e[1])[1]))
                lines.append(f"{ind}{v} := {v}[..|{v}| - 1];")
                return
            if e[0] == "call" and e[1] in self.vf.proof_fns:
                return                                     # a lemma call: a hint, dropped
            if e[0] == "unit":
                return
            if e[0] == "if":
                self.if_stmt(e, ind, ret_name, lines, is_tail and tag == "expr")
                return
            if e[0] == "block":
                self.stmts(e[1], ind, ret_name, lines, is_tail and tag == "expr")
                return
            if tag == "expr" and is_tail:
                lines += self.result_assign(e, ind, ret_name)
                return
            raise VerusRefusal("verus-unparsed", f"statement expression {e[0]}")
        if tag == "return":
            if s[1] is None:
                lines.append(f"{ind}return;")
            else:
                lines += self.result_assign(s[1], ind, ret_name)
                lines.append(f"{ind}return;")
            return
        if tag == "while":
            _, cond, spec, body, _line = s
            self.loop_header(f"while {self.expr(cond, self.body_ghost)}", spec, ind, lines)
            lines.append(f"{ind}{{")
            self.stmts(body, ind + "  ", ret_name, lines, False)
            lines.append(f"{ind}}}")
            return
        if tag == "for":
            _, var, lo, hi, spec, body, _line = s
            lo_t, hi_t = self.expr(lo, self.body_ghost), self.expr(hi, self.body_ghost)
            self.types[var] = VType("int", "int")
            dvar = var
            if var in self.declared:
                k = 1
                while f"{var}_{k}" in self.declared:
                    k += 1
                dvar = f"{var}_{k}"
            self.declared.add(dvar)
            self.renames[var] = dvar
            var = dn(dvar)
            lines.append(f"{ind}var {var} := {lo_t};")
            spec = dict(spec)
            # Verus's `for i in lo..hi` states `lo <= i <= hi` at the loop head itself
            spec["invariant"] = [("chain", ["<=", "<="], [lo, ("var", var), hi])] + list(spec["invariant"])
            self.rewrites.append("for-range-as-while")
            self.loop_header(f"while {var} < {hi_t}", spec, ind, lines, default_dec=f"{hi_t} - {var}")
            lines.append(f"{ind}{{")
            self.stmts(body, ind + "  ", ret_name, lines, False)
            lines.append(f"{ind}  {var} := {var} + 1;")
            lines.append(f"{ind}}}")
            return
        raise VerusRefusal("verus-unparsed", f"statement {tag}")

    def result_assign(self, e, ind: str, ret_name: str) -> list[str]:
        """`ret := e`, or for a pair result `(a, b)` the two components' assignments."""
        rt = self.types.get(ret_name)
        if rt is not None and rt.kind == "pair":
            e = _strip(e)
            if e[0] != "tuple" or len(e[1]) != 2:
                raise VerusRefusal("tuple", "a pair result not written as (a, b)")
            return [f"{ind}{dn(ret_name)}_0 := {self.rhs(e[1][0])};",
                    f"{ind}{dn(ret_name)}_1 := {self.rhs(e[1][1])};"]
        return [f"{ind}{dn(ret_name)} := {self.rhs(e)};"]

    def loop_header(self, head: str, spec: dict, ind: str, lines: list[str], default_dec: str = "") -> None:
        if spec.get("ensures"):
            raise VerusRefusal("loop-exit", "loop ensures")
        if spec.get("except_break"):
            raise VerusRefusal("loop-exit", "invariant_except_break")
        lines.append(f"{ind}{head}")
        for inv in spec["invariant"]:
            lines.append(f"{ind}  invariant {self.expr(inv, True)}")
        if spec["decreases"]:
            lines.append(f"{ind}  decreases " + ", ".join(self.expr(d, True) for d in spec["decreases"]))
        elif default_dec:
            lines.append(f"{ind}  decreases {default_dec}")

    def if_stmt(self, e, ind: str, ret_name: str, lines: list[str], is_tail: bool) -> None:
        _, cond, then, other = e
        lines.append(f"{ind}if {self.expr(cond, self.body_ghost)} {{")
        self.stmts(then, ind + "  ", ret_name, lines, is_tail)
        if other is not None:
            lines.append(f"{ind}}} else {{")
            self.stmts(other, ind + "  ", ret_name, lines, is_tail)
        lines.append(f"{ind}}}")

    def rhs(self, e) -> str:
        return self.expr(e, self.body_ghost)

    def infer(self, e) -> Optional[VType]:
        e = _strip(e)
        tag = e[0]
        if tag == "int":
            return None
        if tag == "bool":
            return VType("bool", "bool")
        if tag in ("seqlit", "fill"):
            return VType("seq", "Vec", elem=VType("int", "int"))
        if tag == "call" and e[1] in ("Vec::new", "Vec::with_capacity"):
            return VType("seq", "Vec", elem=VType("int", "int"))
        if tag == "var":
            return self.types.get(e[1])
        if tag == "index":
            base = _strip(e[1])
            if base[0] == "var" and base[1] in self.types and self.types[base[1]].kind == "seq":
                return self.types[base[1]].elem
        if tag == "method" and e[2] == "len":
            return VType("nat", "usize")
        if tag == "cast":
            return e[2]
        if tag == "method" and e[2] in ("clone",):
            return self.infer(e[1])
        k = self.kind_of(e)
        return VType(k, k) if k in ("int", "nat") else None


# ----------------------------------------------------------------- driver --

@dataclass
class Rendering:
    """The outcome of reading one Verus file. `dafny` is the rendered program (None on a
    refusal); `target` the gradable function's name; `refusal` a (reason, detail) pair;
    `rewrites` the rendering rules applied; `file` the parsed file (for the equivalence
    harness)."""
    dafny: Optional[str]
    target: Optional[str]
    refusal: Optional[tuple[str, str]] = None
    rewrites: list[str] = field(default_factory=list)
    file: Optional[VerusFile] = None


def sections(text: str) -> dict[str, str]:
    """The vericoding section markers (`// <vc-preamble>` ... `// </vc-preamble>`)."""
    out = {}
    for m in re.finditer(r"//\s*<(vc-[a-z]+)>\s*\n(.*?)//\s*</\1>", text, re.S):
        out[m.group(1)] = m.group(2)
    return out


def target_name(text: str) -> Optional[str]:
    """The exec fn the <vc-spec> section declares (a spec or proof fn there is context)."""
    spec = sections(text).get("vc-spec", "")
    spec = re.sub(r"/\*.*?\*/", "", spec, flags=re.S)
    spec = re.sub(r"//[^\n]*", "", spec)
    for m in re.finditer(r"(\b(?:spec|proof)\s+)?\bfn\s+([A-Za-z_][A-Za-z0-9_]*)", spec):
        if not m.group(1):
            return m.group(2)
    # otherwise a proof fn that returns a value, `proof fn f(..) -> (r: T)`
    m = re.search(r"\bproof\s+fn\s+([A-Za-z_][A-Za-z0-9_]*)[^{;]*?->\s*\(\s*[A-Za-z_]", spec)
    return m.group(1) if m else None


def _reach(vf: VerusFile, names: set[str]) -> list[str]:
    """Spec fns reachable from `names` (the target's call closure), in dependency order."""
    order: list[str] = []
    seen: set[str] = set()

    def calls(e, out: set):
        if isinstance(e, tuple):
            if e and e[0] == "call" and e[1] in vf.spec_fns:
                out.add(e[1])
            for x in e:
                calls(x, out)
        elif isinstance(e, list):
            for x in e:
                calls(x, out)
        elif isinstance(e, Param):
            pass

    def visit(n: str):
        if n in seen:
            return
        seen.add(n)
        deps: set = set()
        calls(vf.spec_fns[n].body, deps)
        calls(vf.spec_fns[n].decreases, deps)
        for d in sorted(deps):
            visit(d)
        order.append(n)

    for n in sorted(names):
        visit(n)
    return order


HOLE_PATTERNS = [(re.compile(r"\bassume\s*\("), "assume"), (re.compile(r"\badmit\s*\("), "admit"),
                 (re.compile(r"external_body|verifier::external\b|verifier\(external\)"), "external_body"),
                 (re.compile(r"assume_specification"), "assume_specification"),
                 (re.compile(r"\bunimplemented!|\btodo!"), "unimplemented")]


def trust_holes(text: str) -> list[str]:
    """Trust holes anywhere in the file outside comments (assume, admit, external_body)."""
    code = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    code = re.sub(r"//[^\n]*", "", code)
    return [name for pat, name in HOLE_PATTERNS if pat.search(code)]


def targets(text: str, lemmas: bool = False) -> list[str]:
    """Every gradable function in a Verus file that is not a vericoding task (a corpus
    such as verus-lang/verus's examples): each exec fn and value-returning proof fn with
    an ensures, and, with `lemmas`, each proof fn with an ensures and no result."""
    try:
        vf = Parser(tokenize(text)).parse_file()
    except VerusRefusal:
        return []
    out = [n for n, f in vf.exec_fns.items() if f.ensures]
    if lemmas:
        out += [n for n in vf.lemmas if n not in out]
    return out


def render(text: str, target: Optional[str] = None, lemma: bool = False) -> Rendering:
    """Render one Verus file's gradable function (the vericoding task's, or `target`) as
    Dafny, or refuse it by name. `lemma` renders a proof fn with no result as a task whose
    result is `ok: bool` (assigned true) and whose requires and ensures are the lemma's:
    the program is trivial, the proof obligation is the lemma, restated in t."""
    corpus = target is not None      # a named target in a corpus file: holes are judged per function
    if target is None:
        target = target_name(text)
    if target is None:
        return Rendering(None, None, ("no-method", "no <vc-spec> fn"))
    holes = trust_holes(text) if not corpus else []
    if holes:
        return Rendering(None, target, ("trust-hole", ", ".join(holes)))
    try:
        vf = Parser(tokenize(text)).parse_file()
    except VerusRefusal as r:
        return Rendering(None, target, (r.reason, r.detail))
    if lemma and target in vf.lemmas and target not in vf.exec_fns:
        vf.exec_fns[target] = vf.lemmas[target]
    try:
        return _render_file(vf, target)
    except VerusRefusal as r:
        return Rendering(None, target, (r.reason, r.detail), file=vf)
    except RecursionError:
        return Rendering(None, target, ("verus-unparsed", "nesting too deep"), file=vf)


def _render_file(vf: VerusFile, target: str) -> Rendering:
    fn = vf.exec_fns.get(target)
    if fn is None and target in vf.failed:
        raise VerusRefusal(*vf.failed[target])
    if fn is None:
        raise VerusRefusal("no-method", f"{target} is not an exec fn")
    if any(a.startswith("generics") for a in fn.attrs):
        raise VerusRefusal("generics", target)
    if any(re.search(r"external|admit|assume_specification|uninterp|axiom", a) for a in fn.attrs):
        raise VerusRefusal("trust-hole", f"{target}: {[a for a in fn.attrs if not a.startswith('generics')]}")
    if not fn.ensures:
        raise VerusRefusal("zero-ensures", target)
    if fn.ret.kind == "unit":
        if any(p.type.kind == "refuse" and p.type.reason == "mut-ref-param" for p in fn.params):
            raise VerusRefusal("mut-ref-param", target)
        raise VerusRefusal("zero-returns", target)
    for p in fn.params:
        if p.type.kind == "refuse":
            raise VerusRefusal(p.type.reason, f"parameter {p.name}: {p.type.text}")
        if p.type.kind == "pair":
            raise VerusRefusal("tuple", f"parameter {p.name}: {p.type.text}")
    if fn.ret.kind == "refuse":
        raise VerusRefusal(fn.ret.reason, f"return {fn.ret.text}")
    ret_name = fn.ret_name or "result"
    types = {p.name: p.type for p in fn.params}
    types[ret_name] = fn.ret
    rd = Renderer(vf, types)
    rd.body_ghost = "proof" in fn.attrs
    # spec positions first: the requires/ensures reach the spec fns the file must carry
    reqs = [rd.expr(e, True) for e in fn.requires]
    enss = [rd.expr(e, True) for e in fn.ensures]
    for p in fn.params:
        if p.type.unsigned_elems:
            reqs.append(f"forall i: int :: 0 <= i < |{dn(p.name)}| ==> {dn(p.name)}[i] >= 0")
            rd.rewrites.append("unsigned-elements-bound")
    if fn.ret.unsigned_elems:
        enss.append(f"forall i: int :: 0 <= i < |{dn(ret_name)}| ==> {dn(ret_name)}[i] >= 0")
        rd.rewrites.append("unsigned-elements-bound")
    if "lemma" in fn.attrs:
        # a lemma as a task: the token result is the truth value of the conclusion, so
        # the program `true` verifies exactly when the lemma holds, and a twin returning
        # false is refuted wherever the conclusion is satisfiable (t's grading needs one)
        enss = [f"({dn(ret_name)} <==> (" + " && ".join(f"({e})" for e in enss) + "))"]
        rd.rewrites.append("lemma-as-truth-value")
    body_lines: list[str] = []
    rd.stmts(fn.body, "  ", ret_name, body_lines, True)
    if rd.called_execs:
        raise VerusRefusal("calls-other-method", ", ".join(sorted(rd.called_execs)))
    # spec fns in the closure, rendered in dependency order
    fn_lines: list[str] = []
    done: set[str] = set()
    pending = set(rd.called_specs)
    while pending - done:
        order = _reach(vf, pending)
        for name in order:
            if name in done:
                continue
            done.add(name)
            sf = vf.spec_fns[name]
            if sf.body is None:
                raise VerusRefusal("bodyless-spec-fn", name)
            if sf.ret.kind == "refuse":
                raise VerusRefusal(sf.ret.reason, f"spec fn {name} returns {sf.ret.text}")
            if sf.ret.kind == "pair":
                raise VerusRefusal("tuple", f"spec fn {name} returns {sf.ret.text}")
            for p in sf.params:
                if p.type.kind == "pair":
                    raise VerusRefusal("tuple", f"spec fn {name} parameter {p.name}")
                if p.type.kind == "refuse":
                    raise VerusRefusal(p.type.reason, f"spec fn {name} parameter {p.name}: {p.type.text}")
            srd = Renderer(vf, {p.name: p.type for p in sf.params})
            body = srd.expr(sf.body, True)
            pending |= srd.called_specs
            rd.rewrites += srd.rewrites
            kind = "predicate" if sf.ret.kind == "bool" else "function"
            ret = "" if kind == "predicate" else f": {sf.ret.dafny()}"
            ps = ", ".join(f"{dn(p.name)}: {p.type.dafny()}" for p in sf.params)
            dec = ""
            if sf.decreases:
                dec = "\n  decreases " + ", ".join(srd.expr(d, True) for d in sf.decreases)
            fn_lines.append(f"{kind} {dn(name)}({ps}){ret}{dec}\n{{\n  {body}\n}}\n")
    params = ", ".join(f"{dn(p.name)}: {p.type.dafny()}" for p in fn.params)
    out = [f"// rendered from Verus by t/lift_verus.py: fn {target}", ""]
    out += fn_lines
    if fn.ret.kind == "pair":
        rets = ", ".join(f"{dn(ret_name)}_{k}: {fn.ret.parts[k].dafny()}" for k in (0, 1))
        rd.rewrites.append("pair-result-as-two-returns")
    else:
        rets = f"{dn(ret_name)}: {fn.ret.dafny()}"
    out.append(f"method {dn(target)}({params}) returns ({rets})")
    for r in reqs:
        out.append(f"  requires {r}")
    for e in enss:
        out.append(f"  ensures {e}")
    if fn.decreases:
        out.append("  decreases " + ", ".join(rd.expr(d, True) for d in fn.decreases))
    out.append("{")
    out += body_lines
    out.append("}")
    return Rendering("\n".join(out) + "\n", target, None, sorted(set(rd.rewrites)), vf)


if __name__ == "__main__":
    import sys
    for path in sys.argv[1:]:
        r = render(open(path, encoding="utf-8").read())
        print(f"== {path}: {r.refusal or 'rendered'} {r.rewrites}")
        if r.dafny:
            print(r.dafny)
