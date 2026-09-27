#!/usr/bin/env python3
"""t/lift_lean.py -- the Lean 4 front end of the lifter: read one verified Lean file
(vericoding-benchmark's `vericoded/L*_vericoded.lean`) and render its program, with the
definitions its contract reaches, as Dafny text that `t/lifter.py` lifts unchanged.

The same design as `t/lift_verus.py` (read its docstring first): the rendering is the
lifter's input, never trusted on its own; `t/lift_check_lean.py` proves the lifted
contract equivalent to the SOURCE contract in Lean itself.

The two contract shapes vericoding's Lean files use:

  * precondition/postcondition definitions (APPS, verified-cogen, verina, HumanEval by
    way of Clever): `def f_precond (xs) : Prop := P`, `def f (xs) (h_precond : ...) : T
    := body`, `def f_postcond (xs) (result : T) (h_precond : ...) : Prop := Q`. The
    requires is P, the ensures Q.
  * one specification theorem (DafnyBench, bignum): `theorem f_spec (xs) : H1 → ... →
    C`, where the hypotheses that do not mention `f` are the requires and C, with every
    `f xs` read as the result, the ensures.

What the rendering decides, each with its source (Lean language reference, "Integers",
lean-lang.org/doc/reference/latest/Basic-Types/Integers, research receipt 030fff794977):

  * `Int` is t's int; `/` and `%` on `Int` are `Int.ediv`/`Int.emod`, Euclidean, which
    is t's `div`/`mod` exactly -- except that Lean defines division by zero as 0 where t
    leaves it undefined, so a divisor the lifter cannot prove nonzero is refused by its
    own well-formedness check, never lowered.
  * `Nat` is `nat` (its lower bound kept); Nat subtraction truncates at 0 and is written
    out as `if a >= b then a - b else 0` (rewrite `nat-sub-truncated`).
  * `List Int` and `Array Int` are t's seq; `Nat` elements keep their lower bound as a
    `forall` requires or ensures (rewrite `nat-elements-bound`).
  * `a[i]!` reads as `a[i]`: out of range Lean returns the default, t is undefined, so
    again the lifter's definedness check decides and refuses.
  * proof arguments (`h_precond : ...`) carry no value and are dropped with their
    parameter.

What it refuses, each by name: strings and chars (`string`, `char`), floats (`float`),
tuples and structures (`tuple`, `datatype`), `Vector`/`Fin` (`dependent-type`),
lambdas and folds (`higher-order`), `match` and equation-compiler definitions (`match`),
`termination_by` recursion (`recursion`), Hoare-triple specs (`hoare-triple`), `^`
(`pow`), trust holes and meaning overrides (`sorry`, `axiom`, `instance`, `notation`:
`trust-hole`), and any token the reader does not know (`lean-unparsed`).

INVENTED: no tool translates Lean 4 definitions to Dafny (searched arXiv, GitHub,
StackExchange, receipt 030fff794977); the reader is a Pratt parser over the subset these
files use, written for this lift.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


class LeanRefusal(Exception):
    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


# ------------------------------------------------------------------ lexer --

_OPS = sorted("""
:= @[ → ↔ ∧ ∨ ¬ ≠ ≤ ≥ < > = == != && || + - * / % ^ ++ :: ∈ ∉ ∀ ∃ λ ↑ ( ) [ ] { } ⟨ ⟩ , : | #[ =>
← ! ? @ · . -> <-> /\\ \\/ >= <= $ |> <| ∣ ∘ × ⦃ ⦄ ⌜ ⌝ ⇓ ; ∑ ∏ ⁻¹ ≡ ⊆ ∩ ∪ \\ ~
""".split(), key=len, reverse=True)
_ID = re.compile(r"[A-Za-z_α-ωΑ-Ωᴀ-ᵿ«][A-Za-z0-9_'!?α-ωΑ-Ω₀-₉»]*"
                 r"(?:\.[A-Za-z_][A-Za-z0-9_'!?]*)*")
_NUM = re.compile(r"0x[0-9a-fA-F_]+|0b[01_]+|[0-9][0-9_]*(?:\.[0-9]+)?(?:e[+-]?[0-9]+)?")


@dataclass
class Tok:
    kind: str      # "id" | "num" | "float" | "str" | "char" | "op" | "eof"
    text: str
    line: int
    col: int
    pos: int = 0   # character offset in the source


def tokenize(src: str) -> list[Tok]:
    toks: list[Tok] = []
    i, n, line, lstart = 0, len(src), 1, 0
    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
            lstart = i
            continue
        if c.isspace():
            i += 1
            continue
        if src.startswith("--", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if src.startswith("/-", i):
            depth, j = 1, i + 2
            while j < n and depth:
                if src.startswith("/-", j):
                    depth, j = depth + 1, j + 2
                elif src.startswith("-/", j):
                    depth, j = depth - 1, j + 2
                else:
                    j += 1
            for k in range(i, j):
                if src[k] == "\n":
                    line += 1
                    lstart = k + 1
            i = j
            continue
        col = i - lstart
        if c == '"':
            j = i + 1
            while j < n and src[j] != '"':
                j += 2 if src[j] == "\\" else 1
            toks.append(Tok("str", src[i:j + 1], line, col, i))
            i = j + 1
            continue
        if c == "'" and i + 2 < n and (src[i + 2] == "'" or src[i + 1] == "\\"):
            j = src.find("'", i + 2 if src[i + 1] == "\\" else i + 1)
            toks.append(Tok("char", src[i:j + 1], line, col, i))
            i = j + 1
            continue
        m = _NUM.match(src, i)
        if m and c.isdigit():
            text = m.group(0)
            toks.append(Tok("float" if ("." in text or "e" in text.lower() and not text.startswith("0x")) else "num",
                            text, line, col, i))
            i = m.end()
            continue
        m = _ID.match(src, i)
        if m:
            toks.append(Tok("id", m.group(0), line, col, i))
            i = m.end()
            continue
        for p in _OPS:
            if src.startswith(p, i):
                toks.append(Tok("op", p, line, col, i))
                i += len(p)
                break
        else:
            raise LeanRefusal("lean-unparsed", f"character {c!r} at line {line}")
    toks.append(Tok("eof", "", line + 1, 0, n))
    return toks


# ------------------------------------------------------------------ types --

@dataclass
class LType:
    """int | nat | bool | prop | seq (elem) | refuse (reason) | proof (a Prop-typed binder)."""
    kind: str
    text: str
    elem: Optional["LType"] = None
    reason: str = ""

    def dafny(self) -> str:
        if self.kind == "refuse":
            raise LeanRefusal(self.reason, self.text)
        if self.kind == "seq":
            # a `List Char`/`Array Char` is Dafny's `seq<char>`, a string
            # spelled another way (LIFTER-DECISIONS row 28)
            return "seq<char>" if self.elem is not None and self.elem.kind == "char" else "seq<int>"
        return {"int": "int", "nat": "nat", "bool": "bool", "prop": "bool",
                "string": "string", "char": "char"}[self.kind]


@dataclass
class Binder:
    name: str
    type: LType
    implicit: bool = False
    src: str = ""


@dataclass
class Def:
    name: str
    binders: list[Binder]
    ret: LType
    body: object
    kind: str = "def"            # "def" | "theorem"
    text: str = ""               # the item as written (token text)
    ret_src: str = ""
    recursive_hint: bool = False  # termination_by / decreasing_by present
    stmt_text: str = ""          # a theorem's statement as written


# ----------------------------------------------------------------- parser --

ITEM_WORDS = {"def", "theorem", "lemma", "abbrev", "instance", "axiom", "structure", "inductive",
              "class", "open", "namespace", "section", "end", "set_option", "variable", "import",
              "macro", "notation", "infix", "infixl", "infixr", "prefix", "postfix", "noncomputable",
              "private", "protected", "partial", "mutual", "example", "opaque", "attribute", "local",
              "universe", "syntax", "macro_rules", "elab", "deriving", "unsafe", "@["}
BODY_STOP = {"termination_by", "decreasing_by", "where", "deriving"}


class Parser:
    def __init__(self, toks: list[Tok], src: str = ""):
        self.toks = toks
        self.src = src
        self.i = 0
        self.stop_col: Optional[int] = None     # a token on a later line at or left of this ends a term
        self.stop_line: int = 0

    def peek(self, k: int = 0) -> Tok:
        return self.toks[min(self.i + k, len(self.toks) - 1)]

    def at(self, text: str) -> bool:
        return self.peek().text == text and self.peek().kind in ("op", "id")

    def take(self) -> Tok:
        t = self.toks[self.i]
        self.i += 1
        return t

    def accept(self, text: str) -> bool:
        if self.at(text):
            self.i += 1
            return True
        return False

    def expect(self, text: str) -> Tok:
        t = self.take()
        if t.text != text:
            raise LeanRefusal("lean-unparsed", f"expected {text!r}, found {t.text!r} at line {t.line}")
        return t

    def text(self, a: int, b: int) -> str:
        """Tokens a..b-1 as the source wrote them (layout kept: Lean's `let` needs its lines)."""
        if b <= a:
            return ""
        if self.src:
            last = self.toks[b - 1]
            return self.src[self.toks[a].pos:last.pos + len(last.text)]
        return " ".join(t.text for t in self.toks[a:b])

    def ended(self) -> bool:
        """The current token cannot continue the term being read: end of input, a new
        top-level item, a body-ending keyword, or a layout break (a later line at or left
        of the column the enclosing `let`/definition opened)."""
        t = self.peek()
        if t.kind == "eof":
            return True
        if t.col == 0 and t.text in ITEM_WORDS | {"@["}:
            return True
        if t.text in BODY_STOP:
            return True
        if self.stop_col is not None and t.line > self.stop_line and t.col <= self.stop_col:
            return True
        return False

    # --- types ---
    def parse_type(self) -> LType:
        a = self.i
        parts: list[str] = []
        depth = 0
        while not self.ended():
            t = self.peek()
            if depth == 0 and t.text in (")", "}", "]", ":=", ",", "|") and t.kind == "op":
                break
            if t.text in ("(", "[", "{", "⟨"):
                depth += 1
            elif t.text in (")", "]", "}", "⟩"):
                depth -= 1
            parts.append(self.take().text)
        return classify_type(" ".join(parts), self.text(a, self.i))

    def parse_binders(self) -> list[Binder]:
        out: list[Binder] = []
        while self.peek().text in ("(", "{", "[", "⦃") and self.peek().kind == "op":
            opener = self.take().text
            closer = {"(": ")", "{": "}", "[": "]", "⦃": "⦄"}[opener]
            if opener == "[":
                depth = 1
                while depth:
                    t = self.take()
                    if t.text == "[":
                        depth += 1
                    elif t.text == "]":
                        depth -= 1
                    elif t.kind == "eof":
                        raise LeanRefusal("lean-unparsed", "binder")
                out.append(Binder("_inst", LType("refuse", "instance binder", reason="type-class"), True))
                continue
            names = []
            while self.peek().kind == "id" and not self.at(":"):
                names.append(self.take().text)
            if not self.accept(":"):
                raise LeanRefusal("lean-unparsed", f"binder without a type at line {self.peek().line}")
            a = self.i
            ty = self.parse_type()
            src = self.text(a, self.i)
            self.expect(closer)
            for nm in names:
                out.append(Binder(nm, ty, opener != "(", src))
        return out

    # --- expressions: a Pratt parser over Lean 4's precedence levels ---
    INFIX = {
        "↔": (20, "none"), "<->": (20, "none"), "→": (25, "right"), "->": (25, "right"),
        "∨": (30, "right"), "\\/": (30, "right"), "||": (30, "left"),
        "∧": (35, "right"), "/\\": (35, "right"), "&&": (35, "left"),
        "=": (50, "none"), "==": (50, "none"), "≠": (50, "none"), "!=": (50, "none"),
        "<": (50, "none"), ">": (50, "none"), "≤": (50, "none"), "≥": (50, "none"),
        "<=": (50, "none"), ">=": (50, "none"), "∈": (50, "none"), "∉": (50, "none"),
        "∣": (50, "none"),
        "++": (65, "left"), "::": (67, "right"),
        "+": (65, "left"), "-": (65, "left"), "*": (70, "left"), "/": (70, "left"), "%": (70, "left"),
        "^": (75, "right"),
    }

    def parse_expr(self, min_bp: int = 0):
        t = self.peek()
        if t.text in ("∀", "∃"):
            return self.parse_quant()
        if t.text in ("fun", "λ"):
            raise LeanRefusal("higher-order", f"lambda at line {t.line}")
        if t.text == "if":
            return self.parse_if()
        if t.text == "let":
            return self.parse_let()
        if t.text in ("match",):
            raise LeanRefusal("match", f"line {t.line}")
        if t.text in ("show",):
            raise LeanRefusal("lean-unparsed", "show")
        if t.text == "¬":
            self.take()
            lhs = ("not", self.parse_expr(40))
        elif t.text == "-" and t.kind == "op":
            self.take()
            lhs = ("neg", self.parse_expr(75))
        elif t.text == "!" and t.kind == "op":
            self.take()
            lhs = ("not", self.parse_expr(75))
        else:
            lhs = self.parse_app()
        while not self.ended():
            op = self.peek()
            if op.kind != "op" or op.text not in self.INFIX:
                break
            bp, assoc = self.INFIX[op.text]
            if bp < min_bp or (bp == min_bp and assoc != "right"):
                break
            self.take()
            nxt = self.peek()
            if nxt.text in ("∀", "∃", "if", "let", "fun", "λ", "¬"):
                rhs = self.parse_expr(0 if nxt.text != "¬" else 40)
            else:
                rhs = self.parse_expr(bp if assoc == "right" else bp + 1)
            lhs = ("bin", op.text, lhs, rhs)
        return lhs

    def parse_quant(self):
        kind = "forall" if self.take().text == "∀" else "exists"
        binders: list[Binder] = []
        bound = None
        while not self.at(","):
            if self.at("("):
                binders += self.parse_binders()
                continue
            t = self.take()
            if t.kind == "id":
                binders.append(Binder(t.text, LType("int", "_")))
                continue
            if t.text == ":":
                ty = self.parse_type()
                for b in binders:
                    if b.type.text == "_":
                        b.type = ty
                continue
            if t.text in ("<", "≤", ">", "≥", "∈", "∉"):
                # binder predicate: `∀ i < n, P` is `∀ i, i < n → P`
                rhs = self.parse_expr(51)
                bound = (t.text, rhs)
                continue
            raise LeanRefusal("lean-unparsed", f"quantifier binder {t.text!r} at line {t.line}")
        self.expect(",")
        body = self.parse_expr(0)
        for b in binders:
            if b.type.text == "_":
                b.type = LType("unknown", "_")
        return ("quant", kind, binders, bound, body)

    def parse_if(self):
        line = self.expect("if").line
        if self.peek().kind == "id" and self.peek(1).text == ":":
            self.take()
            self.take()
        cond = self.parse_expr(0)
        self.expect("then")
        a = self.parse_expr(0)
        if not self.accept("else"):
            raise LeanRefusal("lean-unparsed", f"if without else at line {line}")
        b = self.parse_expr(0)
        return ("if", cond, a, b)

    def parse_let(self):
        t = self.expect("let")
        if self.at("(") or self.at("⟨"):
            raise LeanRefusal("tuple", f"let pattern at line {t.line}")
        name = self.take().text
        if self.accept(":"):
            self.parse_type()
        self.expect(":=")
        saved = (self.stop_col, self.stop_line)
        self.stop_col, self.stop_line = t.col, t.line
        val = self.parse_expr(0)
        self.stop_col, self.stop_line = saved
        self.accept(";")
        body = self.parse_expr(0)
        return ("let", name, val, body)

    ATOM_STOP = {")", "]", "}", "⟩", ",", ":=", "then", "else", "|", ":", "=>", "with", "by", "at", "from"}

    def is_atom_start(self) -> bool:
        t = self.peek()
        if self.ended():
            return False
        if t.kind in ("id", "num", "float", "str", "char"):
            return t.text not in self.ATOM_STOP and t.text not in ("then", "else", "fun", "λ", "if",
                                                                     "let", "match", "with", "do", "at")
        return t.kind == "op" and t.text in ("(", "#[", "[", "↑", "⟨")

    def parse_app(self):
        head = self.parse_atom()
        args = []
        while self.is_atom_start():
            if self.peek().text == "[" and args == [] and head[0] != "name":
                break
            args.append(self.parse_atom())
        if args:
            return ("app", head, args)
        return head

    def parse_atom(self):
        t = self.peek()
        if t.kind == "num":
            self.take()
            e = ("int", int(t.text.replace("_", ""), 0))
        elif t.kind == "float":
            raise LeanRefusal("float", t.text)
        elif t.kind == "str":
            self.take()
            e = ("str", t.text)
        elif t.kind == "char":
            self.take()
            e = ("char", t.text)
        elif t.text == "↑":
            self.take()
            e = ("coe", self.parse_atom())
        elif t.text == "(":
            self.take()
            if self.accept(")"):
                raise LeanRefusal("datatype", "unit")
            inner = self.parse_expr(0)
            if self.accept(":"):
                ty = self.parse_type()
                inner = ("ascribe", inner, ty)
            elif self.at(","):
                raise LeanRefusal("tuple", f"tuple at line {t.line}")
            self.expect(")")
            e = ("paren", inner)
        elif t.text in ("#[", "["):
            self.take()
            items = []
            while not self.at("]"):
                items.append(self.parse_expr(0))
                if not self.accept(","):
                    break
            self.expect("]")
            e = ("list", items)
        elif t.text == "⟨":
            raise LeanRefusal("datatype", f"anonymous constructor at line {t.line}")
        elif t.kind == "id":
            self.take()
            if t.text in ("true", "True"):
                e = ("bool", True)
            elif t.text in ("false", "False"):
                e = ("bool", False)
            else:
                e = ("name", t.text)
        else:
            raise LeanRefusal("lean-unparsed", f"term at {t.text!r} line {t.line}")
        # postfix: a[i]!, a[i]?, a[i], .field (only when glued: no space before)
        while True:
            p = self.peek()
            prev = self.toks[self.i - 1]
            glued = p.line == prev.line and p.col == prev.col + len(prev.text)
            if p.text == "[" and glued:
                self.take()
                idx = self.parse_expr(0)
                self.expect("]")
                bang = False
                if self.peek().text == "!" and self.peek().col == self.toks[self.i - 1].col + 1:
                    self.take()
                    bang = True
                elif self.peek().text == "?" and self.peek().col == self.toks[self.i - 1].col + 1:
                    raise LeanRefusal("datatype", "a[i]? (Option)")
                e = ("index", e, idx, bang)
                continue
            if p.kind == "op" and p.text == "." and glued and self.peek(1).kind == "id":
                self.take()
                e = ("field", e, self.take().text)
                continue
            if p.kind == "id" and p.text.startswith(".") and glued:
                self.take()
                e = ("field", e, p.text[1:])
                continue
            return e

    # --- items ---
    def parse_def_like(self) -> Optional[Def]:
        start = self.i
        attrs = []
        while self.at("@["):
            a = self.i
            while not self.at("]"):
                self.take()
            self.take()
            attrs.append(self.text(a, self.i))
        mods = []
        while self.peek().text in ("noncomputable", "private", "protected", "partial", "unsafe"):
            mods.append(self.take().text)
        kw = self.take()
        if kw.text not in ("def", "theorem", "lemma", "abbrev"):
            raise LeanRefusal("lean-unparsed", f"item {kw.text}")
        name = self.take().text
        binders = self.parse_binders()
        ret = LType("unknown", "")
        ret_src = ""
        if self.accept(":"):
            if kw.text in ("theorem", "lemma"):
                self.stop_col, self.stop_line = None, 0
                a = self.i
                body = self.parse_expr(0)
                stmt = self.text(a, self.i)
                self.expect(":=")
                self.skip_to_item()
                return Def(name, binders, LType("prop", "Prop"), body, "theorem", self.text(start, self.i),
                           stmt_text=stmt)
            a = self.i
            ret = self.parse_type()
            ret_src = self.text(a, self.i)
        if self.at("|"):
            raise LeanRefusal("match", f"equation-compiler definition {name}")
        self.expect(":=")
        self.stop_col, self.stop_line = None, 0
        body_start = self.i
        try:
            body = self.parse_expr(0)
        except LeanRefusal as r:
            body = ("refused", r.reason, r.detail)
            self.i = body_start
        rec = False
        self.skip_to_item()
        text = self.text(start, self.i)
        if re.search(r"\b(termination_by|decreasing_by)\b", text):
            rec = True
        return Def(name, binders, ret, body, "def", text, ret_src, rec)

    def skip_to_item(self) -> None:
        """Advance to the next top-level item (a column-0 item keyword)."""
        while True:
            t = self.peek()
            if t.kind == "eof":
                return
            if t.col == 0 and (t.text in ITEM_WORDS or t.text == "@[") and self.i > 0 \
                    and self.toks[self.i - 1].line < t.line:
                return
            self.take()


TYPE_WORDS = {"Int": "int", "ℤ": "int", "Nat": "nat", "ℕ": "nat", "Bool": "bool", "Prop": "prop"}


def classify_type(text: str, src: str) -> LType:
    t = text.strip()
    while t.startswith("(") and t.endswith(")"):
        t = t[1:-1].strip()
    if t in TYPE_WORDS:
        return LType(TYPE_WORDS[t], src)
    m = re.fullmatch(r"(List|Array) (\S+)", t)
    if m:
        inner = classify_type(m.group(2), m.group(2))
        if inner.kind in ("int", "nat", "char"):
            return LType("seq", src, inner)
        if inner.kind == "bool":
            return LType("refuse", src, reason="seq-of-bool")
        if inner.kind in ("seq", "string"):
            return LType("refuse", src, reason="nested-seq")
        return LType("refuse", src, reason=inner.reason or "datatype")
    if re.search(r"\bFloat\b|ℝ|\bReal\b", t):
        return LType("refuse", src, reason="float")
    # Feature 6 of t/FEATURES-TRACK.md's cloud track (2026-09-27): a
    # `String` is Dafny's `string` (a `seq<char>`, Dafny Reference Manual
    # 5.5.3.4, dafny.org/latest/DafnyRef/DafnyRef#sec-strings) and a
    # `Char` its `char`, both of which the Dafny lifter lifts as code
    # points (LIFTER-DECISIONS row 28); every String/Char operation this
    # reader renders is spelled by its Lean core definition (`field`,
    # `call` below) over that model. What it cannot spell refuses by name:
    # `string-pos` (a byte position, `String.Pos`), `string-lib` (a
    # library member with no Dafny expression: splitOn, trim, toNat?, ...).
    if t == "String":
        return LType("string", src)
    if t == "Char":
        return LType("char", src)
    if re.search(r"\bString\b", t):
        return LType("refuse", src, reason="string")
    if re.search(r"\bChar\b", t):
        return LType("refuse", src, reason="char")
    if re.search(r"\bVector\b|\bFin\b", t):
        return LType("refuse", src, reason="dependent-type")
    if "×" in t:
        return LType("refuse", src, reason="tuple")
    if re.search(r"\bOption\b|\bExcept\b", t):
        return LType("refuse", src, reason="datatype")
    if re.search(r"\bUInt\d+|\bInt\d+|\bUSize\b", t):
        return LType("refuse", src, reason="fixed-width-int")
    if re.search(r"\bFinset\b|\bSet\b|\bMultiset\b", t):
        return LType("refuse", src, reason="set")
    if re.search(r"\bId\b|\bIO\b", t):
        return LType("refuse", src, reason="hoare-triple")
    if "→" in t or "->" in t:
        return LType("refuse", src, reason="higher-order")
    # an application of a definition, or a relation: a proposition (a proof binder)
    if re.match(r"[A-Za-z_][\w.]*(\s|$)", t) and t.split()[0] not in ("List", "Array", "Type"):
        return LType("proof", src)
    if re.search(r"[<>=≤≥≠∧∨¬]", t):
        return LType("proof", src)
    return LType("refuse", src, reason="datatype")


# --------------------------------------------------------------- the file --

@dataclass
class LeanFile:
    defs: dict[str, Def]
    theorems: dict[str, Def]
    holes: list[str]
    sections: dict[str, str]


def sections(text: str) -> dict[str, str]:
    out = {}
    for m in re.finditer(r"--\s*<(vc-[a-z]+)>\s*\n(.*?)--\s*</\1>", text, re.S):
        out[m.group(1)] = m.group(2)
    return out


HOLES = [(re.compile(r"\bsorry\b"), "sorry"), (re.compile(r"\badmit\b"), "admit"),
         (re.compile(r"^\s*axiom\b", re.M), "axiom"), (re.compile(r"\binstance\b"), "instance"),
         (re.compile(r"^\s*(?:local\s+)?(?:notation|infix[lr]?|prefix|postfix|macro|macro_rules|syntax)\b", re.M),
          "notation"),
         (re.compile(r"implemented_by|extern\b|unsafe\b"), "implemented_by"),
         (re.compile(r"native_decide"), "native_decide")]


def trust_holes(text: str) -> list[str]:
    code = re.sub(r"/-.*?-/", "", text, flags=re.S)
    code = re.sub(r"--[^\n]*", "", code)
    return [name for pat, name in HOLES if pat.search(code)]


def parse_file(text: str) -> LeanFile:
    toks = tokenize(text)
    p = Parser(toks, text)
    defs: dict[str, Def] = {}
    thms: dict[str, Def] = {}
    while p.peek().kind != "eof":
        t = p.peek()
        if t.col == 0 and (t.text in ("def", "theorem", "lemma", "abbrev", "@[", "noncomputable", "private",
                                      "protected", "partial")):
            try:
                d = p.parse_def_like()
            except LeanRefusal as r:
                p.skip_to_item()
                continue
            if d is None:
                continue
            (thms if d.kind == "theorem" else defs)[d.name] = d
            continue
        p.take()
        p.skip_to_item()
    return LeanFile(defs, thms, [], sections(text))


# ---------------------------------------------------------------- render --

def dn(name: str) -> str:
    """A Dafny identifier for a Lean name (dots and primes out, reserved words suffixed)."""
    from lift_verus import DAFNY_RESERVED
    n = name.replace(".", "_").replace("'", "_p").replace("!", "_b").replace("?", "_q")
    if n.startswith("_"):
        n = "u" + n
    if n in DAFNY_RESERVED:
        n += "_v"
    return n


class Renderer:
    def __init__(self, lf: LeanFile, env: dict[str, LType]):
        self.lf = lf
        self.env = dict(env)
        self.rewrites: list[str] = []
        self.called: set[str] = set()
        self.subst: dict[str, str] = {}      # a name read as another (the program's result)

    def proof_positions(self, d: Def) -> list[int]:
        return [k for k, b in enumerate(d.binders) if b.type.kind == "proof" and not b.implicit]

    def type_of(self, e) -> Optional[str]:
        tag = e[0]
        if tag == "name":
            t = self.env.get(e[1])
            if t is not None:
                return t.kind
            d = self.lf.defs.get(e[1])
            if d is not None and not [b for b in d.binders if not b.implicit and b.type.kind != "proof"]:
                return d.ret.kind
            return None
        if tag in ("paren",):
            return self.type_of(e[1])
        if tag == "str":
            return "string"
        if tag == "char":
            return "char"
        if tag == "ascribe":
            return e[2].kind
        if tag == "coe":
            return "int"
        if tag == "int":
            return None
        if tag == "index":
            base = self.type_of(e[1])
            bt = self._seq_elem(e[1])
            return bt
        if tag == "field":
            if e[2] in ("size", "length"):
                return "nat"
            if e[2] in ("toNat", "natAbs", "val"):
                return "nat"
            rt = self.type_of(e[1])
            if rt == "string":
                if e[2] in ("take", "drop", "dropRight", "takeRight", "push", "append", "trim"):
                    return "string"
                if e[2] in ("front", "back"):
                    return "char"
                if e[2] in ("data", "toList"):
                    return "seq"
                if e[2] in ("isEmpty", "startsWith", "endsWith", "contains", "isPrefixOf"):
                    return "prop"
            if rt == "char":
                if e[2] in ("isDigit", "isAlpha", "isUpper", "isLower", "isAlphanum", "isWhitespace"):
                    return "prop"
                if e[2] in ("toUpper", "toLower"):
                    return "char"
            return None
        if tag == "app":
            head = e[1]
            if head[0] == "name":
                d = self.lf.defs.get(head[1])
                if d is not None:
                    return d.ret.kind
                if head[1] in ("Int.toNat", "Int.natAbs", "List.length", "Array.size",
                               "String.length", "Char.toNat"):
                    return "nat"
                if head[1] in ("String.mk", "String.singleton", "String.append", "String.push"):
                    return "string"
                if head[1] == "Char.ofNat":
                    return "char"
                if head[1] in ("min", "max"):
                    kinds = {self.type_of(a) for a in e[2]}
                    return "nat" if kinds <= {"nat", None} and "nat" in kinds else ("int" if "int" in kinds else None)
            return None
        if tag == "bin":
            op = e[1]
            if op in ("+", "*", "/", "%", "-"):
                a, b = self.type_of(e[2]), self.type_of(e[3])
                if "int" in (a, b):
                    return "int"
                if a == "nat" or b == "nat":
                    return "nat"
                return None
            return "prop"
        if tag == "if":
            a, b = self.type_of(e[2]), self.type_of(e[3])
            return a or b
        if tag == "let":
            return None
        return None

    def _seq_elem(self, e) -> Optional[str]:
        e0 = e
        while e0[0] in ("paren",):
            e0 = e0[1]
        if e0[0] == "field" and e0[2] in ("toList", "toArray", "data"):
            return self._seq_elem(e0[1])
        if e0[0] == "name":
            t = self.env.get(e0[1])
            if t is not None and t.kind == "seq":
                return t.elem.kind
            if t is not None and t.kind == "string":
                return "char"  # feature 6: a string's elements are chars
        if e0[0] == "str":
            return "char"
        return None

    def ex(self, e) -> str:
        tag = e[0]
        if tag == "int":
            return str(e[1])
        if tag == "bool":
            return "true" if e[1] else "false"
        if tag == "str":
            return _dafny_string_literal(e[1])
        if tag == "char":
            return _dafny_char_literal(e[1])
        if tag == "paren":
            return "(" + self.ex(e[1]) + ")"
        if tag == "ascribe":
            if e[2].kind in ("int", "nat", "bool", "prop", "seq"):
                return self.ex(e[1])
            raise LeanRefusal(e[2].reason or "datatype", e[2].text)
        if tag == "coe":
            return self.ex(e[1])
        if tag == "name":
            return self.name(e[1], [])
        if tag == "not":
            return "!(" + self.ex(e[1]) + ")"
        if tag == "neg":
            return "(-" + self.ex(e[1]) + ")"
        if tag == "bin":
            return self.binop(e)
        if tag == "if":
            return f"(if {self.ex(e[1])} then {self.ex(e[2])} else {self.ex(e[3])})"
        if tag == "let":
            name, val, body = e[1], e[2], e[3]
            vt = self.type_of(val)
            saved = dict(self.env)
            if vt in ("int", "nat", "bool", "prop"):
                self.env[name] = LType(vt, vt)
            else:
                self.env.pop(name, None)
            text = f"(var {dn(name)} := {self.ex(val)}; {self.ex(body)})"
            self.env = saved
            return text
        if tag == "quant":
            return self.quant(e)
        if tag == "list":
            return "[" + ", ".join(self.ex(x) for x in e[1]) + "]"
        if tag == "index":
            return f"{self.ex(e[1])}[{self.index_expr(e[2])}]"
        if tag == "field":
            return self.field(e[1], e[2], [])
        if tag == "app":
            return self.app(e)
        if tag == "refused":
            raise LeanRefusal(e[1], e[2])
        raise LeanRefusal("lean-unparsed", f"term {tag}")

    def index_expr(self, i) -> str:
        return self.ex(i)

    def binop(self, e) -> str:
        op, a, b = e[1], e[2], e[3]
        A, B = self.ex(a), self.ex(b)
        if op in ("↔", "<->"):
            return f"({A} <==> {B})"
        if op in ("→", "->"):
            return f"({A} ==> {B})"
        if op in ("∨", "\\/", "||"):
            return f"({A} || {B})"
        if op in ("∧", "/\\", "&&"):
            return f"({A} && {B})"
        if op in ("=", "=="):
            return f"({A} == {B})"
        if op in ("≠", "!="):
            return f"({A} != {B})"
        if op in ("<", ">", "<=", ">="):
            return f"({A} {op} {B})"
        if op == "≤":
            return f"({A} <= {B})"
        if op == "≥":
            return f"({A} >= {B})"
        if op == "∈":
            return f"({A} in {B})"
        if op == "∉":
            return f"!({A} in {B})"
        if op == "∣":
            return f"(({A}) != 0 && ({B}) % ({A}) == 0 || ({A}) == 0 && ({B}) == 0)"
        if op == "++":
            return f"({A} + {B})"
        if op == "::":
            return f"([{A}] + {B})"
        if op in ("+", "*"):
            return f"({A} {op} {B})"
        if op == "-":
            ta, tb = self.type_of(a), self.type_of(b)
            if ta == "nat" and tb in ("nat", None) or tb == "nat" and ta is None:
                self.rewrites.append("nat-sub-truncated")
                return f"(if {A} >= {B} then {A} - {B} else 0)"
            if ta is None and tb is None and self._both_literals(a, b):
                return f"({A} - {B})"
            if ta is None and tb is None:
                raise LeanRefusal("nat-sub-unknown", "subtraction on operands of unknown type")
            return f"({A} - {B})"
        if op in ("/", "%"):
            return f"({A} {op} {B})"
        if op == "^":
            raise LeanRefusal("pow", "^")
        raise LeanRefusal("lean-unparsed", f"operator {op}")

    @staticmethod
    def _both_literals(a, b) -> bool:
        return a[0] == "int" and b[0] == "int"

    def quant(self, e) -> str:
        _, kind, binders, bound, body = e
        saved = dict(self.env)
        names, guards = [], []
        for b in binders:
            k = b.type.kind
            if k == "unknown":
                # Lean elaborates an untyped binder from its uses; the two these files
                # make are an array index (Nat) and arithmetic against Int. Read it the
                # same way; a wrong reading changes the contract, which the Lean
                # equivalence harness then refuses.
                k = "nat" if bound is not None or _indexes_with(body, b.name) else "int"
            if k not in ("int", "nat"):
                if k == "unknown":
                    raise LeanRefusal("quantifier-type", f"untyped binder {b.name}")
                raise LeanRefusal(b.type.reason or "unbounded-quantifier", f"quantifier over {b.type.text}")
            self.env[b.name] = LType(k, k)
            names.append(f"{dn(b.name)}: int")
            if k == "nat":
                guards.append(f"0 <= {dn(b.name)}")
        if bound is not None:
            op, rhs = bound
            if len(binders) != 1 or op not in ("<", "≤"):
                raise LeanRefusal("quantifier-type", f"binder predicate {op}")
            guards.append(f"{dn(binders[0].name)} {'<' if op == '<' else '<='} {self.ex(rhs)}")
        inner = self.ex(body)
        self.env = saved
        g = " && ".join(guards)
        if kind == "forall":
            return f"(forall {', '.join(names)} :: {('(' + g + ') ==> ') if g else ''}{inner})"
        return f"(exists {', '.join(names)} :: {('(' + g + ') && ') if g else ''}{inner})"

    def field(self, recv, name: str, args: list) -> str:
        R = self.ex(recv)
        rt = self.type_of(recv)
        if rt == "string" and name in ("get", "get!", "get?", "get'", "extract", "posOf", "revPosOf",
                                       "atEnd", "next", "prev", "set", "modify", "endPos",
                                       "toSubstring", "iter", "mkIterator", "utf8ByteSize"):
            # a byte position (`String.Pos`) indexes UTF-8 bytes, not chars
            raise LeanRefusal("string-pos", f".{name}")
        if rt == "string" and name in ("splitOn", "split", "intercalate", "trim", "trimLeft",
                                       "trimRight", "toNat?", "toNat!", "toInt?", "toInt!",
                                       "toUpper", "toLower", "capitalize", "decapitalize",
                                       "replace", "containsSubstr", "findSubstr", "find",
                                       "words", "lines", "splitOn", "isNat", "isInt",
                                       "toList!", "join", "map", "foldl", "foldr", "any", "all",
                                       "revFind", "dropWhile", "takeWhile", "dropRightWhile",
                                       "takeRightWhile", "isPrefixOf", "hash", "toName"):
            raise LeanRefusal("string-lib", f".{name}")
        if rt == "string" and name in ("dropRight", "takeRight") and len(args) == 1:
            # `String.dropRight s n`: all but the last n chars (Lean core,
            # `s.toSubstring.dropRight n`); `takeRight`: the last n
            n = self.ex(args[0])
            m = f"(if {n} <= |{R}| then {n} else |{R}|)"
            return f"{R}[..(|{R}| - {m})]" if name == "dropRight" else f"{R}[(|{R}| - {m})..]"
        if rt == "string" and name == "isEmpty" and not args:
            return f"(|{R}| == 0)"
        if rt == "string" and name == "front" and not args:
            return f"{R}[0]"
        if rt == "string" and name == "back" and not args:
            return f"{R}[|{R}| - 1]"
        if rt == "string" and name in ("startsWith", "endsWith") and len(args) == 1:
            # Lean core: `s.startsWith pre := s.substrEq 0 pre 0 pre.length`,
            # `s.endsWith post := s.takeRight post.length == post`
            P = self.ex(args[0])
            if name == "startsWith":
                return f"(|{P}| <= |{R}| && {R}[..|{P}|] == {P})"
            return f"(|{P}| <= |{R}| && {R}[|{R}| - |{P}|..] == {P})"
        if rt == "string" and name == "append" and len(args) == 1:
            return f"({R} + {self.ex(args[0])})"
        if rt == "string" and name == "asString" and not args:
            return R
        if rt == "char":
            if name in ("toNat", "val") and not args:
                return f"({R} as int)"
            if name == "isDigit" and not args:
                return f"('0' <= {R} && {R} <= '9')"
            if name == "isUpper" and not args:
                return f"('A' <= {R} && {R} <= 'Z')"
            if name == "isLower" and not args:
                return f"('a' <= {R} && {R} <= 'z')"
            if name == "isAlpha" and not args:
                return f"(('A' <= {R} && {R} <= 'Z') || ('a' <= {R} && {R} <= 'z'))"
            if name == "isAlphanum" and not args:
                return (f"(('A' <= {R} && {R} <= 'Z') || ('a' <= {R} && {R} <= 'z') "
                        f"|| ('0' <= {R} && {R} <= '9'))")
            if name == "isWhitespace" and not args:
                return f"({R} == ' ' || {R} == '\\t' || {R} == '\\r' || {R} == '\\n')"
            if name in ("toUpper", "toLower", "toString", "ofNat"):
                # `Char.toLower c = if 'A' <= c <= 'Z' then Char.ofNat (c.toNat + 32) else c`:
                # a code-point cast the Dafny lifter can only accept on a literal
                raise LeanRefusal("char-case", f".{name}")
        if name in ("size", "length") and not args:
            return f"|{R}|"
        if name in ("toList", "toArray", "data") and not args:
            return R
        if name == "asString" and not args:
            return R  # `List Char` to `String`: the same seq<char>
        if name == "toNat" and not args:
            return f"(if {R} >= 0 then {R} else 0)"
        if name == "natAbs" and not args:
            return f"(if {R} >= 0 then {R} else -{R})"
        if name in ("get!", "get") and len(args) == 1:
            return f"{R}[{self.ex(args[0])}]"
        if name == "push" and len(args) == 1:
            return f"({R} + [{self.ex(args[0])}])"
        if name == "contains" and len(args) == 1:
            return f"({self.ex(args[0])} in {R})"
        if name in ("take", "drop") and len(args) == 1:
            n = self.ex(args[0])
            m = f"(if {n} <= |{R}| then {n} else |{R}|)"
            return f"{R}[..{m}]" if name == "take" else f"{R}[{m}..]"
        if name in ("set!", "set") and len(args) == 2:
            i = self.ex(args[0])
            return f"(if 0 <= {i} < |{R}| then {R}[{i} := {self.ex(args[1])}] else {R})"
        if name == "succ" and not args:
            return f"({R} + 1)"
        if name in ("map", "filter", "foldl", "foldr", "all", "any", "sum", "count", "find?", "zip",
                    "zipWith", "range", "reverse", "sort", "max", "min", "toFinset", "eraseDups",
                    "countP", "head!", "getLast!", "maximum?", "minimum?"):
            raise LeanRefusal("higher-order" if name not in ("head!", "getLast!", "maximum?", "minimum?", "find?")
                              else "datatype", f".{name}")
        raise LeanRefusal("lean-method", f".{name}")

    def name(self, n: str, args: list) -> str:
        if n in self.subst and not args:
            return self.subst[n]
        if n in self.env and not args:
            return dn(n)
        if "." in n and n.split(".")[0] in self.env:
            parts = n.split(".")
            e = ("name", parts[0])
            for f in parts[1:-1]:
                e = ("field", e, f)
            return self.field(e, parts[-1], args)
        return self.call(n, args)

    def app(self, e) -> str:
        head, args = e[1], e[2]
        if head[0] == "name":
            return self.name(head[1], args)
        if head[0] == "field":
            return self.field(head[1], head[2], args)
        if head[0] == "paren":
            return self.app(("app", head[1], args))
        raise LeanRefusal("higher-order", "application of a non-name")

    def call(self, n: str, args: list) -> str:
        A = lambda k: self.ex(args[k])
        if n == "decide" and len(args) == 1:
            return self.ex(args[0])
        if n in ("min", "max", "Nat.min", "Nat.max", "Int.min", "Int.max") and len(args) == 2:
            op = "<=" if n.endswith("min") else ">="
            return f"(if {A(0)} {op} {A(1)} then {A(0)} else {A(1)})"
        if n in ("Int.toNat",) and len(args) == 1:
            return f"(if {A(0)} >= 0 then {A(0)} else 0)"
        if n in ("Int.natAbs", "abs", "Int.abs") and len(args) == 1:
            return f"(if {A(0)} >= 0 then {A(0)} else -{A(0)})"
        if n in ("Int.ofNat", "Nat.cast", "Int.toInt") and len(args) == 1:
            return A(0)
        if n in ("Int.emod",) and len(args) == 2:
            return f"({A(0)} % {A(1)})"
        if n in ("Int.ediv",) and len(args) == 2:
            return f"({A(0)} / {A(1)})"
        if n in ("Int.fdiv", "Int.tdiv", "Int.fmod", "Int.tmod", "Int.div", "Int.mod", "Int.bdiv", "Int.bmod"):
            raise LeanRefusal("div-convention", n)
        if n in ("List.length", "Array.size", "String.length") and len(args) == 1:
            return f"|{A(0)}|"
        if n in ("String.mk", "List.asString", "String.toList", "String.data") and len(args) == 1:
            return A(0)  # a string IS its list of chars
        if n == "String.singleton" and len(args) == 1:
            return f"[{A(0)}]"
        if n in ("String.append", "String.push") and len(args) == 2:
            return f"({A(0)} + {'[' + A(1) + ']' if n == 'String.push' else A(1)})"
        if n == "String.isEmpty" and len(args) == 1:
            return f"(|{A(0)}| == 0)"
        if n in ("Char.toNat", "Char.val") and len(args) == 1:
            return f"({A(0)} as int)"
        if n == "Char.ofNat" and len(args) == 1:
            # the Dafny lifter accepts `n as char` only when n is visibly a
            # code point (a literal in range), refusing `char-cast-unbounded`
            # otherwise; Lean's `Char.ofNat` returns '\0' outside the range
            return f"({A(0)} as char)"
        if n in ("Char.isDigit", "Char.isAlpha", "Char.isUpper", "Char.isLower", "Char.isAlphanum",
                 "Char.isWhitespace") and len(args) == 1:
            return self.field(args[0], n.split(".")[1], [])
        if n.startswith("String.") and n not in ("String.length",):
            raise LeanRefusal("string-lib", n)
        if n.startswith("Char."):
            raise LeanRefusal("char-case", n)
        if n in ("List.replicate", "Array.replicate", "Array.mkArray", "mkArray") and len(args) == 2:
            return f"seq({A(0)}, _ => {A(1)})"
        if n in ("Nat.succ",) and len(args) == 1:
            return f"({A(0)} + 1)"
        if n in ("not",) and len(args) == 1:
            return f"!({A(0)})"
        if n in ("List.range", "List.map", "List.filter", "List.foldl", "List.foldr", "List.sum", "Array.map",
                 "Array.foldl", "List.all", "List.any", "Array.all", "Array.any", "List.count", "Array.range",
                 "List.zip", "List.zipWith", "Finset.sum", "Finset.range", "List.iota"):
            raise LeanRefusal("higher-order", n)
        if n in ("Nat.gcd", "Int.gcd", "Nat.lcm", "Int.lcm", "Nat.factorial", "Nat.Prime", "Nat.sqrt",
                 "Int.sqrt", "Nat.log", "Nat.fib", "Nat.choose", "Nat.digits", "Int.sign"):
            raise LeanRefusal("mathlib-function", n)
        d = self.lf.defs.get(n)
        if d is None:
            raise LeanRefusal("unknown-function", n)
        keep = [k for k, b in enumerate(d.binders) if not b.implicit and b.type.kind != "proof"]
        explicit = [k for k, b in enumerate(d.binders) if not b.implicit]
        if len(args) != len(explicit):
            if len(args) == len(keep):
                used = args
            else:
                raise LeanRefusal("partial-application", f"{n} with {len(args)} of {len(explicit)} arguments")
        else:
            used = [a for k, a in zip(explicit, args) if d.binders[k].type.kind != "proof"]
        self.called.add(n)
        if not keep:
            return f"{dn(n)}()"
        return f"{dn(n)}(" + ", ".join(self.ex(a) for a in used) + ")"


def _lean_escapes_to_dafny(body: str) -> str:
    """The escapes a Lean literal may carry, in Dafny's spelling: `\\n \\t
    \\r \\0 \\' \\" \\\\` are the same in both; Lean's `\\xHH` and
    `\\u{H+}` become Dafny's `\\U{H+}` (the one code-point escape
    dafny 4.11 parses, LIFTER-DECISIONS row 28)."""
    out = []
    i = 0
    while i < len(body):
        c = body[i]
        if c != "\\":
            out.append(c)
            i += 1
            continue
        nxt = body[i + 1] if i + 1 < len(body) else ""
        if nxt in ("n", "t", "r", "0", "'", '"', "\\"):
            out.append("\\" + nxt)
            i += 2
        elif nxt == "x" and i + 3 < len(body) + 1:
            out.append("\\U{" + body[i + 2:i + 4].upper() + "}")
            i += 4
        elif nxt == "u" and i + 2 < len(body) and body[i + 2] == "{":
            j = body.index("}", i)
            out.append("\\U{" + body[i + 3:j].upper() + "}")
            i = j + 1
        else:
            raise LeanRefusal("string", f"escape \\{nxt}")
    return "".join(out)


def _dafny_string_literal(text: str) -> str:
    return '"' + _lean_escapes_to_dafny(text[1:-1]) + '"'


def _dafny_char_literal(text: str) -> str:
    return "'" + _lean_escapes_to_dafny(text[1:-1]) + "'"


# ---------------------------------------------------------------- driver --

@dataclass
class Rendering:
    dafny: Optional[str]
    target: Optional[str]
    refusal: Optional[tuple[str, str]] = None
    rewrites: list[str] = field(default_factory=list)
    file: Optional[LeanFile] = None
    shape: str = ""                 # "pre-post" | "spec-theorem"
    requires_src: list = field(default_factory=list)   # source Props (token text), for the harness
    ensures_src: str = ""
    result_name: str = "result"


def _indexes_with(e, name: str) -> bool:
    if isinstance(e, tuple) and e:
        if e[0] == "index" and _mentions(e[2], name):
            return True
        if e[0] == "bin" and e[1] in ("<", "≤", "<=") and _mentions(e[2], name) and isinstance(e[3], tuple) \
                and e[3][0] == "field" and e[3][2] in ("size", "length"):
            return True
        return any(_indexes_with(x, name) for x in e[1:])
    if isinstance(e, list):
        return any(_indexes_with(x, name) for x in e)
    return False


def _conjuncts(e) -> list:
    if e[0] == "bin" and e[1] in ("∧", "/\\"):
        return _conjuncts(e[2]) + _conjuncts(e[3])
    if e[0] == "paren":
        inner = e[1]
        if inner[0] == "bin" and inner[1] in ("∧", "/\\"):
            return _conjuncts(inner)
    return [e]


def _mentions(e, name: str) -> bool:
    if isinstance(e, tuple):
        if e[:2] == ("name", name):
            return True
        return any(_mentions(x, name) for x in e[1:])
    if isinstance(e, list):
        return any(_mentions(x, name) for x in e)
    return False


def _replace_calls(e, fname: str, params: list[str], result: str):
    """`fname p1 .. pn` (the program applied to its own parameters) read as `result`; any
    other application of the program refuses."""
    if isinstance(e, list):
        return [_replace_calls(x, fname, params, result) for x in e]
    if not isinstance(e, tuple) or not e:
        return e
    if e[0] == "app" and e[1] == ("name", fname):
        names = [a[1] if a[0] == "name" else None for a in e[2]]
        if names[:len(params)] == params:
            return ("name", result)
        raise LeanRefusal("spec-applies-program", f"{fname} applied to other arguments")
    if e == ("name", fname):
        if params:
            raise LeanRefusal("spec-applies-program", f"{fname} unapplied")
        return ("name", result)
    if e[0] == "quant":
        return (e[0], e[1], e[2], e[3], _replace_calls(e[4], fname, params, result))
    return tuple([e[0]] + [_replace_calls(x, fname, params, result) for x in e[1:]])


def target_def(lf: LeanFile) -> Optional[Def]:
    sec = lf.sections.get("vc-definitions", "")
    names = re.findall(r"^(?:noncomputable\s+|partial\s+)?def\s+([^\s(:{]+)", sec, re.M)
    if not names:
        return None
    for n in names:
        if f"{n}_postcond" in lf.defs or any(t.startswith(n + "_spec") for t in lf.theorems):
            return lf.defs.get(n)
    return lf.defs.get(names[-1])


def render(text: str) -> Rendering:
    holes = trust_holes(text)
    if holes:
        return Rendering(None, None, ("trust-hole", ", ".join(holes)))
    if "⦃" in text:
        return Rendering(None, None, ("hoare-triple", "monadic Hoare-triple specification"))
    try:
        lf = parse_file(text)
    except LeanRefusal as r:
        return Rendering(None, None, (r.reason, r.detail))
    fn = target_def(lf)
    if fn is None:
        return Rendering(None, None, ("no-method", "no definition in <vc-definitions>"), file=lf)
    try:
        return _render(lf, fn)
    except LeanRefusal as r:
        return Rendering(None, fn.name, (r.reason, r.detail), file=lf)
    except RecursionError:
        return Rendering(None, fn.name, ("lean-unparsed", "nesting too deep"), file=lf)


def _render(lf: LeanFile, fn: Def) -> Rendering:
    if fn.recursive_hint:
        raise LeanRefusal("recursion", f"{fn.name} uses termination_by")
    if isinstance(fn.body, tuple) and fn.body[0] == "refused":
        raise LeanRefusal(fn.body[1], fn.body[2])
    if any(b.implicit for b in fn.binders):
        raise LeanRefusal("implicit-argument", fn.name)
    params = [b for b in fn.binders if b.type.kind != "proof"]
    for b in params:
        if b.type.kind == "refuse":
            raise LeanRefusal(b.type.reason, f"parameter {b.name}: {b.type.text}")
        if b.type.kind == "prop":
            raise LeanRefusal("prop-parameter", b.name)
    if fn.ret.kind == "refuse":
        raise LeanRefusal(fn.ret.reason, f"result {fn.ret.text}")
    if fn.ret.kind in ("prop", "unknown", "proof"):
        raise LeanRefusal("datatype", f"result {fn.ret.text or 'unstated'}")
    if _mentions(fn.body, fn.name):
        raise LeanRefusal("recursion", f"{fn.name} calls itself")
    pnames = [b.name for b in params]
    env = {b.name: b.type for b in params}
    requires, ensures, result = [], None, "result"
    req_src, ens_src, shape = [], "", ""
    post = lf.defs.get(f"{fn.name}_postcond")
    pre = lf.defs.get(f"{fn.name}_precond")
    thm = next((t for n, t in lf.theorems.items() if n in (f"{fn.name}_spec", f"{fn.name}_spec_satisfied")
                or n.startswith(f"{fn.name}_spec")), None)
    if post is not None:
        shape = "pre-post"
        pb = [b for b in post.binders if b.type.kind != "proof"]
        if [b.name for b in pb[:len(pnames)]] != pnames or len(pb) != len(pnames) + 1:
            raise LeanRefusal("postcond-shape", f"{post.name} binders")
        result = pb[-1].name
        if pb[-1].type.kind != fn.ret.kind or (fn.ret.kind == "seq" and pb[-1].type.elem.kind != fn.ret.elem.kind):
            raise LeanRefusal("postcond-shape", "result type differs from the program's")
        if isinstance(post.body, tuple) and post.body[0] == "refused":
            raise LeanRefusal(post.body[1], post.body[2])
        ensures = [post.body]
        if pre is not None:
            if [b.name for b in pre.binders if b.type.kind != "proof"] != pnames:
                raise LeanRefusal("precond-shape", pre.name)
            if isinstance(pre.body, tuple) and pre.body[0] == "refused":
                raise LeanRefusal(pre.body[1], pre.body[2])
            requires = [pre.body]
    elif thm is not None:
        shape = "spec-theorem"
        tb = [b for b in thm.binders if b.type.kind != "proof"]
        if [b.name for b in tb] != pnames:
            raise LeanRefusal("theorem-binders", f"{thm.name} binds {[b.name for b in tb]}, the program {pnames}")
        stmt = thm.body
        while stmt[0] == "paren":
            stmt = stmt[1]
        hyps = []
        while stmt[0] == "bin" and stmt[1] in ("→", "->") and not _mentions(stmt[2], fn.name):
            hyps.append(stmt[2])
            stmt = stmt[3]
        # `let result := f xs` then the conclusion
        if stmt[0] == "let" and stmt[2][0] in ("app", "name") and _mentions(stmt[2], fn.name):
            result = stmt[1]
            conc = _replace_calls(stmt[3], fn.name, pnames, result)
            if _mentions(stmt[2], fn.name) and _replace_calls(stmt[2], fn.name, pnames, result) != ("name", result):
                raise LeanRefusal("spec-applies-program", "let binds another application")
        else:
            if "result" in pnames:
                result = "result_"
            conc = _replace_calls(stmt, fn.name, pnames, result)
        if not _mentions(conc, result):
            raise LeanRefusal("zero-ensures", "the conclusion does not mention the program")
        requires, ensures = hyps, [conc]
    else:
        raise LeanRefusal("no-spec", f"{fn.name} has neither a _postcond nor a _spec theorem")
    rd = Renderer(lf, env)
    reqs = [rd.ex(r) for r in requires]
    env_post = dict(env)
    env_post[result] = fn.ret
    rd.env = env_post
    enss = [rd.ex(e) for e in ensures]
    rd.env = dict(env)
    body = rd.ex(fn.body)
    for b in params:
        if b.type.kind == "seq" and b.type.elem.kind == "nat":
            reqs.append(f"forall i: int :: 0 <= i < |{dn(b.name)}| ==> {dn(b.name)}[i] >= 0")
            rd.rewrites.append("nat-elements-bound")
    if fn.ret.kind == "seq" and fn.ret.elem.kind == "nat":
        enss.append(f"forall i: int :: 0 <= i < |{dn(result)}| ==> {dn(result)}[i] >= 0")
        rd.rewrites.append("nat-elements-bound")
    # the definitions the contract and the program reach, in dependency order
    fn_lines: list[str] = []
    done: set[str] = set()
    order: list[str] = []

    def visit(n: str, stack: tuple = ()):
        if n in done or n in stack:
            return
        d = lf.defs[n]
        sub = Renderer(lf, {b.name: b.type for b in d.binders if b.type.kind != "proof"})
        if d.recursive_hint:
            raise LeanRefusal("recursion", f"{n} uses termination_by")
        if isinstance(d.body, tuple) and d.body[0] == "refused":
            raise LeanRefusal(d.body[1], d.body[2])
        if any(b.implicit for b in d.binders):
            raise LeanRefusal("implicit-argument", n)
        for b in d.binders:
            if b.type.kind == "refuse":
                raise LeanRefusal(b.type.reason, f"{n} parameter {b.name}: {b.type.text}")
        if d.ret.kind in ("refuse",):
            raise LeanRefusal(d.ret.reason, f"{n} returns {d.ret.text}")
        if d.ret.kind in ("unknown", "proof"):
            raise LeanRefusal("datatype", f"{n} returns {d.ret.text or 'an unstated type'}")
        text = sub.ex(d.body)
        rd.rewrites.extend(sub.rewrites)
        for c in sorted(sub.called):
            if c != n:
                visit(c, stack + (n,))
        done.add(n)
        ps = ", ".join(f"{dn(b.name)}: {b.type.dafny()}" for b in d.binders if b.type.kind != "proof")
        kind = "predicate" if d.ret.kind in ("prop", "bool") else "function"
        ret = "" if kind == "predicate" else f": {d.ret.dafny()}"
        fn_lines.append(f"{kind} {dn(n)}({ps}){ret}\n{{\n  {text}\n}}\n")

    for c in sorted(rd.called):
        visit(c)
    ret_t = fn.ret.dafny()
    ps = ", ".join(f"{dn(b.name)}: {b.type.dafny()}" for b in params)
    out = [f"// rendered from Lean 4 by t/lift_lean.py: def {fn.name} ({shape})", ""] + fn_lines
    out.append(f"method {dn(fn.name)}({ps}) returns ({dn(result)}: {ret_t})")
    out += [f"  requires {r}" for r in reqs]
    out += [f"  ensures {e}" for e in enss]
    out += ["{", f"  {dn(result)} := {body};", "}"]
    return Rendering("\n".join(out) + "\n", fn.name, None, sorted(set(rd.rewrites)), lf, shape,
                     requires_src=requires, ensures_src=ensures, result_name=result)


if __name__ == "__main__":
    import sys
    for path in sys.argv[1:]:
        r = render(open(path, encoding="utf-8").read())
        print(f"== {path}: {r.refusal or 'rendered'} {r.rewrites}")
        if r.dafny:
            print(r.dafny)
