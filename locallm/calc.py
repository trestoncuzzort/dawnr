"""calc.py: a question with numbers, answered by the number the model reasons its way to, shown only when a working
written separately and computed exactly gives the same number (2026-10-05).

    python3 locallm/calc.py --host 127.0.0.1:8712 "A shop sells pens at $1.20 each. What do 15 pens cost with 10% off?"
        [--ways 3] [--needed 1] [--json OUT.json]

`dawnr calc` is this.

A language model that answers a sum in prose can set it up right and still get the arithmetic wrong; PAL (Gao et
al., arXiv:2211.10435) has the model write the steps as a program and leaves the solving to an interpreter. The
first build of this command was that alone: the working held by a grammar (llama-server's `grammar` field) to
comment lines and assignments of arithmetic, computed exactly, and shown when the workings agreed. Measured on
GSM8K (arXiv:2110.14168; K1 to K5 of locallm/PREDICT-2026-10-05-calc.md, 300 problems, the base model) it lost to
the model simply reasoning in prose: the first working was right on 239 where the prose answer was right on 279,
because held to assignments the model sets a problem up without having reasoned about it; the gate over three
workings showed 203 answers, 94.6% of them right, where prose showed 300 at 93.0%.

So the two are made to check each other, which is the rule "two independent formalisations must agree" of
Trustworthy Tax Reasoning (arXiv:2508.21051) and the reason CRANE (arXiv:2502.09061) lets a model reason freely
before it is constrained. The model answers once in prose, step by step, as it does best. It is then asked, without
being shown that reasoning, for the working under the grammar, several times. Three things that are not the model
stand between it and the person. Research receipt f8e8dafb74c0.

  the evaluator   reads a working's assignments with Python's own parser, admits only numbers, names already
                  assigned, the arithmetic operators and min, max, abs, round, floor and ceil, and computes in
                  exact rationals: no floating point, so 0.1 + 0.2 is 0.3
  agreement       the number the prose ends on is shown only when at least one working (`--needed`), computed
                  exactly, gives that same number; the working that agrees is printed with it
  the question    a working that uses a number the question does not state is still used, and the number is
                  pointed out beside it (as a filter this rule cost answers and bought nothing: K5)

Measured on 300 problems it had not seen (K6 to K9 of the same file): 260 answered and 254 right (97.7%), where
prose alone was right on 282 of the 300; of the 18 answers prose got wrong it still shows 6. Requiring two
agreeing workings (`--needed 2`) shows 223 with 4 wrong. What this cannot check is that both the reasoning and
the working read the question rightly: a misreading they share is shown, and the working is printed to be read.
"""
from __future__ import annotations

import argparse
import ast
import json
import math
import re
import sys
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from locallm import rag_rgb  # noqa: E402

SYSTEM = ("You work out questions that have numbers in them. Write the working as short Python: comment lines that say "
          "what each step is, and assignments that use only numbers from the question, names you have assigned, and "
          "+ - * / // % ** with min, max, abs, round, floor, ceil. Do the arithmetic in the assignments, not in your "
          "head. The last line assigns the result to `answer`.")
TEMPERATURE = 0.7
# The working ends at its first assignment to `answer`: any other name may be assigned before it (`target` is every
# name but that one), so a model that would go on to print or restate the result has nowhere to go.
GRAMMAR = r'''root ::= step{0,20} "answer = " expr "\n"
step ::= comment | assign
comment ::= "# " [^\n]{1,110} "\n"
assign ::= target " = " expr "\n"
expr ::= term (" " [+-] " " term)*
term ::= unary (" " ("*" | "/" | "//" | "%" | "**") " " unary)*
unary ::= "-"? atom
atom ::= number | call | name | "(" expr ")"
call ::= ("min" | "max" | "abs" | "round" | "floor" | "ceil") "(" expr (", " expr)* ")"
number ::= [0-9]{1,12} ("." [0-9]{1,8})?
name ::= [a-z] rest
rest ::= [a-z0-9_]{0,40}
target ::= [b-z] rest | "a" ( [a-mo-z0-9_] rest | "n" ( [a-rt-z0-9_] rest | "s" ( [a-vx-z0-9_] rest | "w" ( [a-df-z0-9_] rest | "e" ( [a-qs-z0-9_] rest | "r" [a-z0-9_] rest )? )? )? )? )?
'''
_OPS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b, ast.FloorDiv: lambda a, b: Fraction(math.floor(a / b)),
        ast.Mod: lambda a, b: a - b * math.floor(a / b)}
_CALLS = {"min": min, "max": max, "abs": abs, "floor": lambda x: Fraction(math.floor(x)),
          "ceil": lambda x: Fraction(math.ceil(x)), "round": lambda x, n=Fraction(0): _round(x, n)}
# numbers a working may use without the question stating them: the percent in a whole, and the common units
CONSTANTS = {Fraction(x) for x in (0, 1, 2, 7, 10, 12, 24, 30, 52, 60, 100, 365, 1000)}
_WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
          "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
          "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
          "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100, "thousand": 1000, "million": 1000000,
          "once": 1, "twice": 2, "double": 2, "doubles": 2, "doubled": 2, "thrice": 3, "triple": 3, "tripled": 3,
          "half": 2, "halves": 2, "halved": 2, "third": 3, "thirds": 3, "quarter": 4, "quarters": 4, "fifth": 5,
          "pair": 2, "pairs": 2, "couple": 2, "dozen": 12, "dozens": 12, "score": 20, "both": 2}
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


class Unusable(Exception):
    """A working that cannot be used; the message says why."""


def _round(x: Fraction, places: Fraction = Fraction(0)) -> Fraction:
    """Half away from zero, at `places` decimal places: what a person rounding money expects, not banker's rounding."""
    scale = Fraction(10) ** int(places)
    scaled = x * scale
    whole = math.floor(abs(scaled) + Fraction(1, 2))
    return Fraction(whole if scaled >= 0 else -whole) / scale


def _number(node: ast.Constant, source: str) -> Fraction:
    text = ast.get_source_segment(source, node) or repr(node.value)
    if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
        raise Unusable(f"`{text}` is not a number")
    return Fraction(text)                                       # from the digits as written: 0.1 is one tenth


def evaluate(program: str) -> tuple[Fraction, list[Fraction]]:
    """(the value of `answer`, every number written in the working). Unusable when the text is anything but
    assignments of arithmetic over numbers and names already assigned."""
    try:
        tree = ast.parse(program)
    except SyntaxError as error:
        raise Unusable(f"it is not arithmetic this reads (line {error.lineno})") from None
    names: dict[str, Fraction] = {}
    written: list[Fraction] = []

    def value(node) -> Fraction:
        if isinstance(node, ast.Constant):
            x = _number(node, program)
            written.append(x)
            return x
        if isinstance(node, ast.Name):
            if node.id not in names:
                raise Unusable(f"`{node.id}` is used before it is given a value")
            return names[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            return -value(node.operand) if isinstance(node.op, ast.USub) else value(node.operand)
        if isinstance(node, ast.BinOp):
            a, b = value(node.left), value(node.right)
            if isinstance(node.op, ast.Pow):
                if b.denominator != 1 or abs(b) > 64:
                    raise Unusable("a power that is not a small whole number")
                if a == 0 and b < 0:
                    raise Unusable("a division by zero")
                return a ** int(b)
            if type(node.op) not in _OPS:
                raise Unusable("an operator this does not compute")
            if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)) and b == 0:
                raise Unusable("a division by zero")
            return _OPS[type(node.op)](a, b)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _CALLS and not node.keywords:
            args = [value(x) for x in node.args]
            if not args or (node.func.id in ("abs", "floor", "ceil") and len(args) != 1) or (node.func.id == "round" and len(args) > 2):
                raise Unusable(f"`{node.func.id}` with the wrong number of values")
            return Fraction(_CALLS[node.func.id](*args))
        raise Unusable("something other than arithmetic")
    for line in tree.body:
        if not (isinstance(line, ast.Assign) and len(line.targets) == 1 and isinstance(line.targets[0], ast.Name)):
            raise Unusable("a line that is not `name = arithmetic`")
        names[line.targets[0].id] = value(line.value)
    if "answer" not in names:
        raise Unusable("it never assigns `answer`")
    return names["answer"], written


def stated(question: str) -> set[Fraction]:
    """The numbers a working may take from the question: each as written, as a percentage of itself and as a hundred
    of itself (20% is written 0.2 or 20), and the number words."""
    out = set(CONSTANTS)
    for m in _NUMBER.finditer(question):
        x = Fraction(m.group(0).replace(",", ""))
        out |= {x, x / 100, x * 100}
    for word in re.findall(r"[a-z]+", question.lower()):
        if word in _WORDS:
            x = Fraction(_WORDS[word])
            out |= {x, 1 / x} if x else {x}
    return out


def ungrounded(written: list[Fraction], question: str) -> list[Fraction]:
    """The numbers of a working that the question does not state, in the order written."""
    allowed = stated(question)
    allowed |= {1 - x for x in allowed if 0 < x < 1} | {1 + x for x in allowed if 0 < x < 1}   # "20% off", "20% more"
    return [x for x in dict.fromkeys(written) if x not in allowed]


def show(x: Fraction) -> str:
    """A rational as a person writes it: a whole number, a short decimal, or the fraction with its decimal beside it."""
    if x.denominator == 1:
        return str(x.numerator)
    d = x.denominator
    while d % 2 == 0:
        d //= 2
    while d % 5 == 0:
        d //= 5
    if d == 1:                                                  # a terminating decimal: exact as written
        digits = 0
        while (x * 10 ** digits).denominator != 1:
            digits += 1
        return f"{float(x):.{digits}f}" if digits <= 12 else f"{x.numerator}/{x.denominator}"
    return f"{x.numerator}/{x.denominator} (about {float(x):.4f})"


# The prose answer's prompt, word for word what was measured as the `prose` arm of K1 to K5.
REASON_SYSTEM = ("Work the problem out step by step. Then give the final number on a line of its own, after ####, "
                 "with no units.")
_STATED = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def ask_reasoned(host: str, question: str, post=rag_rgb._post) -> str:
    """The model answering as it does: step by step in words, ending `#### <number>`."""
    body = {"messages": [{"role": "system", "content": REASON_SYSTEM}, {"role": "user", "content": question}],
            "temperature": 0, "max_tokens": 600}
    return post(f"http://{host}/v1/chat/completions", body)["choices"][0]["message"]["content"] or ""


def reasoned_number(reply: str) -> Fraction | None:
    """The number after the last ####, or the last number of a reply that has none."""
    tail = reply.rsplit("####", 1)[1] if "####" in reply else reply
    found = _STATED.findall(tail)
    if not found:
        return None
    text = (found[0] if "####" in reply else found[-1]).replace(",", "")
    try:
        return Fraction(text)
    except (ValueError, ZeroDivisionError):
        return None


def ask(host: str, question: str, temperature: float, seed: int, post=rag_rgb._post) -> str:
    body = {"messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}],
            "temperature": temperature, "seed": seed, "max_tokens": 400, "grammar": GRAMMAR}
    return post(f"http://{host}/v1/chat/completions", body)["choices"][0]["message"]["content"] or ""


def judge(question: str, programs: list[str], grounded: bool = True) -> dict:
    """The gate over the workings already written: {"answer": Fraction | None, "why", "ways": [{"program", "value" |
    "why"}], "agree": n}. With `grounded`, a working that brings in a number the question does not state is not used."""
    ways = []
    for program in programs:
        try:
            value, written = evaluate(program)
        except Unusable as unusable:
            ways.append({"program": program, "why": str(unusable)})
            continue
        extra = ungrounded(written, question) if grounded else []
        if extra:
            ways.append({"program": program, "why": "it uses " + ", ".join(show(x) for x in extra) + ", which the question does not state"})
        else:
            ways.append({"program": program, "value": value})
    values = [w["value"] for w in ways if "value" in w]
    out = {"answer": None, "ways": ways, "agree": len(values)}
    if len(values) < 2:
        return dict(out, why="fewer than two ways of working it out could be computed from the question's own numbers")
    if len(set(values)) != 1:
        return dict(out, why="the ways of working it out disagree (" + ", ".join(show(v) for v in values) + ")")
    return dict(out, answer=values[0])


def settle(question: str, reasoned: str, programs: list[str], needed: int = 1) -> dict:
    """The gate `dawnr calc` runs: the number the prose reasoning ends on is the answer only when at least `needed`
    of the workings, computed exactly, give that number. {"answer": Fraction | None, "why", "stated", "reasoned",
    "ways": [{"program", "value" | "why", "note"?}], "agree": n}."""
    stated, ways = reasoned_number(reasoned), []
    for program in programs:
        try:
            value, written = evaluate(program)
        except Unusable as unusable:
            ways.append({"program": program, "why": str(unusable)})
            continue
        extra = ungrounded(written, question)
        ways.append({"program": program, "value": value,
                     **({"note": "it uses " + ", ".join(show(x) for x in extra) + ", which the question does not state"} if extra else {})})
    values = [w["value"] for w in ways if "value" in w]
    out = {"answer": None, "stated": stated, "reasoned": reasoned, "ways": ways, "agree": sum(1 for v in values if v == stated)}
    if stated is None:
        return dict(out, why="the reasoning does not end on a number")
    if not values:
        return dict(out, why="no working could be computed to check the reasoning's " + show(stated))
    if out["agree"] < needed:
        return dict(out, why=f"the reasoning ends on {show(stated)} and " + (
            "no working computed gives that (" if not out["agree"] else f"only {out['agree']} of the workings computed gives that (")
            + ", ".join(show(v) for v in values) + ")")
    return dict(out, answer=stated)


def calc(host: str, question: str, ways: int = 3, needed: int = 1, post=rag_rgb._post) -> dict:
    reasoned = ask_reasoned(host, question, post)
    programs = [ask(host, question, 0.0 if k == 0 else TEMPERATURE, k, post) for k in range(ways)]
    return dict(settle(question, reasoned, programs, needed), question=question)


def render(r: dict) -> str:
    if "stated" in r:
        return _render_settled(r)
    if r["answer"] is None:
        lines = ["REFUSED: " + r["why"] + "."]
        for k, w in enumerate(r["ways"], 1):
            lines += ["", f"Way {k}" + (f" gives {show(w['value'])}:" if "value" in w else f" was not used: {w['why']}.")]
            lines += ["  " + l for l in w["program"].rstrip().splitlines()]
        return "\n".join(lines)
    used = next(w for w in r["ways"] if "value" in w)
    lines = [f"ANSWER: {show(r['answer'])}", ""] + ["  " + l for l in used["program"].rstrip().splitlines()]
    lines += ["", f"Computed exactly from this working. {len(r['ways'])} ways of working it out were written, {r['agree']} could be "
                  f"computed from your question's own numbers, and they all give {show(r['answer'])}.",
              "Read the working: it is the reading of your question that was computed."]
    return "\n".join(lines)


def _render_settled(r: dict) -> str:
    def working(w: dict) -> list[str]:
        return ["  " + l for l in w["program"].rstrip().splitlines()]
    if r["answer"] is None:
        lines = ["REFUSED: " + r["why"] + "."]
        for k, w in enumerate(r["ways"], 1):
            lines += ["", f"Working {k}" + (f" gives {show(w['value'])}:" if "value" in w else f" could not be computed: {w['why']}.")] + working(w)
        return "\n".join(lines + ["", "The reasoning:", ""] + ["  " + l for l in r["reasoned"].strip().splitlines()])
    used = next(w for w in r["ways"] if w.get("value") == r["answer"])
    lines = [f"ANSWER: {show(r['answer'])}", ""] + working(used)
    lines += ["", f"The model reasoned its way to {show(r['answer'])} in words; this working, written separately and computed exactly, "
                  f"gives the same ({r['agree']} of {len(r['ways'])} workings do)."]
    if "note" in used:
        lines.append("Note: " + used["note"] + ".")
    lines.append("Read the working: it is the reading of your question that was computed.")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--host", required=True, help="host:port of a llama-server holding the base model")
    ap.add_argument("--ways", type=int, default=3, help="how many times the working is asked for")
    ap.add_argument("--needed", type=int, default=1, help="how many workings must compute the number the reasoning ends on")
    ap.add_argument("--json", type=Path)
    ap.add_argument("question")
    a = ap.parse_args(argv)
    try:
        r = calc(a.host, a.question, a.ways, a.needed)
    except OSError as error:
        print(f"calc: the model server at {a.host} did not answer ({error}).", file=sys.stderr)
        return 2
    print(render(r))
    if a.json:
        a.json.write_text(json.dumps(r, indent=1, default=lambda x: show(x) if isinstance(x, Fraction) else str(x)) + "\n",
                          encoding="utf-8")
    return 0 if r["answer"] is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
