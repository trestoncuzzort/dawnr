#!/usr/bin/env python3
"""t/examples.py -- examples for a person to approve, in place of tests they would have to write (2026-10-05).

    python3 t/examples.py --python HOST:PORT --text "The largest number in a list." [--questions 4] [--json OUT.json]

`dawnr ask "QUESTION"` with no --test runs this first, in the terminal.

Why. `dawnr ask` needs `assert f(arguments) == value` lines, and a person who does not program cannot write them.
TiCoder (Fakhoury, Naik, Sakkas, Chakraborty and Lahiri, arXiv:2404.10100) has the model write candidate programs
and tests, shows the person the test that splits the candidates most evenly, takes "right", "wrong, it should be
this" or "that input makes no sense" for an answer, and prunes; with an idealised person one such question took a
model from 49% to 77% of MBPP problems right at the first answer, and people judged the code better with less
effort. Here the same loop makes the tests the gate then holds everything to. Research receipt 3a589b025171.

  drafts      the base model writes several Python solutions from the words alone, every parameter annotated
  inputs      the model suggests a few calls someone would try, and only their inputs are kept; small inputs
              are drawn for the annotations as well (t/verify_py.py's pools). Every draft is run on all of them
              in the sandbox, so what a draft answers is a fact about it, not a guess, and no result is ever
              taken from what the model wrote beside a call
  questions   first the inputs every draft answers: the one the drafts split on most evenly (TiCoder's score, the
              second largest group of drafts over the largest, the drafts that raise left out), then plain ones
              until there are enough examples; last the inputs some draft fails on, where the question is whether
              the input is allowed at all. The person presses Enter on the answer shown, types the right one, or
              says the input should not be allowed; drafts that answered otherwise are dropped
  examples    what the person approved or typed becomes the tests; nothing they did not see does

What this does not do: check the examples. They are the person's statement of what they mean, as tests typed by
hand are, and the program shown afterwards still has to pass them, agree with an independent solution and be
proved (t/answer.py). How many questions end with a shown answer this way, against the same questions asked with
the benchmark's own tests, is measured with the reference standing in for the person, as TiCoder measured it
(t/PREDICT-2026-10-05-examples.md).
"""
from __future__ import annotations

import argparse
import ast
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import py_sandbox  # noqa: E402
import python_beside  # noqa: E402
import spec_first  # noqa: E402
import spec_first_rows  # noqa: E402
import verify_py  # noqa: E402

DRAFTS = 5                     # Python solutions asked for: one greedy, the rest sampled as the gate samples them
SUGGESTED = 6                  # calls the model is asked to suggest; only their inputs are taken, never a result
QUESTIONS = 4                  # at most this many examples are put to the person
EXAMPLES = 3                   # once the drafts no longer disagree, stop when this many are approved
INPUTS = 40                    # small inputs every draft is run on
NOT_ALLOWED = "x"


class Refused(Exception):
    """No examples can be proposed; the message says what the person can do instead."""


def header_of(header: str) -> tuple[str, int]:
    """(the name, how many parameters) of a header written `name(a, b)` or `def name(a, b):`."""
    line = header.strip()
    node = ast.parse((line if line.startswith("def ") else "def " + line).rstrip(":") + ": pass").body[0]
    return node.name, len(node.args.args)


def question(text: str, header: str | None = None) -> list[dict]:
    """The request for one draft. `header`, when the caller knows the function's name and parameters (TiCoder gives
    the model the function header with the words; a benchmark's reference has one), is asked for as it stands."""
    what = (f"Write the Python function `{header.strip()}` that does this: keep that name and those parameters, in that order."
            if header else "Write one Python function that does this.")
    return [{"role": "system", "content": spec_first_rows.PY_SYSTEM},
            {"role": "user", "content": f"{text.strip()}\n\n{what} What it works on comes in as its parameters and the result is "
                                        "returned: it does not print, and it does not ask for input. Give every parameter a type "
                                        "annotation built from int, bool, str, list[...] and tuple[...]."}]


def suggestion(text: str, call: str) -> list[dict]:
    """The request for calls worth trying. TiCoder has the model write whole tests and asks the person about
    them; here only the inputs are the model's, because a value drawn from a fixed pool is rarely the interesting
    one (no small random matrix is a magic square) and a result the model wrote is a guess."""
    return [{"role": "user", "content": f"A function `{call}` has already been written for this request:\n\n{text.strip()}\n\n"
                                        f"Do not write the function. Write {SUGGESTED} calls of it that someone checking it would try: "
                                        "ordinary ones first, then an edge case or two. One call on each line: only the call, with no "
                                        "result and no comment."}]


def _plain(value, depth: int = 0) -> bool:
    """A value a person can read at a glance and the sandbox can be handed: numbers, text, lists and tuples of them."""
    if isinstance(value, int):                                  # bool is one
        return abs(value) <= 10 ** 6
    if isinstance(value, str):
        return len(value) <= 40
    return isinstance(value, (list, tuple)) and depth < 3 and len(value) <= 12 and all(_plain(v, depth + 1) for v in value)


def suggested(reply: str, fn: str, kinds: list[str]) -> list[tuple]:
    """The inputs of the calls of `fn` found in a reply, written as the kinds write them, each once. A call with
    other than plain small values, or another number of them, is passed over; whatever follows a call is not read."""
    out, text = [], reply or ""
    at = text.find(fn + "(")
    while at >= 0 and len(out) < SUGGESTED + 2:
        depth, quote, end = 0, None, None
        for i in range(at + len(fn), len(text)):                # the matching parenthesis, text in quotes skipped
            c = text[i]
            if quote:
                quote = None if c == quote and text[i - 1] != "\\" else quote
            elif c in "'\"":
                quote = c
            elif c in "([{":
                depth += 1
            elif c in ")]}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end is not None and (at == 0 or not (text[at - 1].isalnum() or text[at - 1] in "_.")):
            try:
                node = ast.parse(text[at:end], mode="eval").body
                args = tuple(ast.literal_eval(a) for a in node.args) if not node.keywords else None
            except (ValueError, SyntaxError, MemoryError, RecursionError):
                args = None
            if args is not None and len(args) == len(kinds) and all(_plain(a) for a in args):
                args = tuple(verify_py.fit(a, k) for a, k in zip(args, kinds))
                if not any(repr(args) == repr(seen) for seen in out):
                    out.append(args)
        at = text.find(fn + "(", (end or at + 1))
    return out[:SUGGESTED]


def shape(kind: str) -> str:
    """A kind with each tuple of one kind of element read as a list of it: drafts that differ only in asking for a
    tuple or for a list are run side by side, each handed what it asked for."""
    head, inner, variadic = verify_py._parts(kind)
    inner = [shape(k) for k in inner]
    if head == "list" or (head == "tuple" and (variadic or len(set(inner)) == 1)):
        return f"list[{inner[0]}]"
    return f"tuple[{', '.join(inner)}]" if head == "tuple" else kind


def drafts(decode, text: str, n: int = DRAFTS, max_new: int = 768, header: str | None = None) -> tuple[list[dict], list[str]]:
    """(the drafts that can be run side by side, why each other reply was left out). A draft is
    verify_py.read_function's reading of one reply; they are kept when they take the same shape of input, the
    shape most drafts chose."""
    read, left_out = [], []
    asked = header_of(header) if header else None
    for i in range(n):
        reply = decode([question(text, header)], 0.0 if i == 0 else spec_first.SAMPLE_TEMPERATURE, 0 if i == 0 else 1000 + i, "q", max_new)[0][0]
        code = spec_first.python_of(reply or "")
        if code is None:
            left_out.append(f"draft {i + 1}: no Python in the reply")
            continue
        try:
            f = verify_py.read_function(code, asked[0] if asked else None, entry=True)
        except verify_py.Refused as refused:
            left_out.append(f"draft {i + 1}: {refused}")
            continue
        if asked and len(f["kinds"]) != asked[1]:
            left_out.append(f"draft {i + 1}: it does not take the parameters asked for")
        elif verify_py.unread(f):
            left_out.append(f"draft {i + 1}: {verify_py.unread(f)}")
        elif not any(f["code"] == g["code"] for g in read):
            read.append(dict(f, n=i + 1))
    if not read:
        return [], left_out
    first = lambda group: min(f["n"] for f in group)            # noqa: E731
    by_shape = collections.defaultdict(list)
    for f in read:
        by_shape[tuple(shape(k) for k in f["kinds"])].append(f)
    kept = max(by_shape.values(), key=lambda group: (len(group), -first(group)))
    left_out += [f"draft {f['n']}: it takes other kinds of input than most drafts" for f in read if not any(f is g for g in kept)]
    return kept, left_out


def shown_kinds(fs: list[dict]) -> list[str]:
    """The kinds the examples are drawn for and written with: those most of the drafts asked for, the earliest
    draft's when two are as common."""
    by = collections.defaultdict(list)
    for f in fs:
        by[tuple(f["kinds"])].append(f["n"])
    return list(max(by, key=lambda kinds: (len(by[kinds]), -min(by[kinds]))))


def canon(value):
    """A value for comparing answers: a tuple and a list of the same elements are one answer."""
    if isinstance(value, (list, tuple)):
        return [canon(v) for v in value]
    if isinstance(value, dict):
        return {repr(k): canon(v) for k, v in value.items()}
    return value


def read_value(text: str):
    """(True, the value) for a Python literal a person typed (`9`, `[1, 3]`, `True`, `'abc'`), else (False, None)."""
    try:
        return True, ast.literal_eval(text.strip())
    except (ValueError, SyntaxError, MemoryError, RecursionError):
        return False, None


def run(fs: list[dict], inputs: list[tuple]) -> list[dict]:
    """Every draft on every input, in the sandbox: [{"args", "said": [the result's repr, or None where the draft
    raised, ran out of time or returned something that cannot be written down]}]."""
    rows = [{"args": args, "said": []} for args in inputs]
    for f in fs:
        try:
            session = py_sandbox.Session(f["code"] + verify_py._wrapper(f["fn"], f["kinds"]), "_t_repr_call")
        except py_sandbox.LoadError:                            # a draft that does not load answers nothing
            for row in rows:
                row["said"].append(None)
            continue
        with session:
            for row in rows:
                try:
                    value = session.call([list(row["args"])])
                except (py_sandbox.CallError, py_sandbox.CallTimeout, py_sandbox.Unrepresentable):
                    value = None
                row["said"].append(value if isinstance(value, str) and read_value(value)[0] else None)
    return rows


class Dialogue:
    """The questions, with no input or output of its own: `next()` gives the example to put, `answer()` takes the
    person's reply, `tests` are the examples approved so far."""

    def __init__(self, fn: str, rows: list[dict], questions: int = QUESTIONS, examples: int = EXAMPLES):
        self.fn, self.rows, self.left, self.examples = fn, rows, questions, examples
        # a draft that answers nothing at all (it did not load, or it fails on every input) is not standing
        self.alive = {i for i in range(len(rows[0]["said"]) if rows else 0) if any(row["said"][i] is not None for row in rows)}
        self.asked: set[int] = set()
        self.tests: list[str] = []
        self.results: list[str] = []

    def call(self, args: tuple) -> str:
        return f"{self.fn}({', '.join(repr(a) for a in args)})"

    def _groups(self, row: dict) -> list[tuple[str, int]]:
        """The distinct answers of the drafts still standing, most common first (one spelling for each answer)."""
        seen: dict[str, list] = {}
        for i in sorted(self.alive):
            said = row["said"][i]
            if said is not None:
                seen.setdefault(json.dumps(canon(read_value(said)[1]), sort_keys=True, default=repr), [said, 0])[1] += 1
        return sorted(((said, count) for said, count in seen.values()), key=lambda g: -g[1])

    def _raising(self, row: dict) -> int:
        return sum(1 for i in self.alive if row["said"][i] is None)

    def split(self, row: dict) -> float:
        """TiCoder's discriminating score over the drafts still standing: 0 when those that answer all say one
        thing, 1 when the two commonest answers have as many drafts each. Drafts that raise on the input are left
        out, as TiCoder leaves them."""
        sizes = [count for _said, count in self._groups(row)]
        return sizes[1] / sizes[0] if len(sizes) > 1 else 0.0

    def doubt(self, row: dict) -> float:
        """The same score with the drafts that raise counted as one more answer: how evenly the drafts are divided
        once whether the input is allowed at all is part of the question."""
        sizes = sorted([count for _said, count in self._groups(row)] + [self._raising(row)], reverse=True)
        return sizes[1] / sizes[0] if len(sizes) > 1 and sizes[0] else 0.0

    def next(self) -> dict | None:
        if self.left <= 0:
            return None
        open_ = [(k, row) for k, row in enumerate(self.rows) if k not in self.asked and self._groups(row)]
        if not open_:
            # no draft is left to answer (the person's values were none of theirs, or none ever ran): the plainest
            # inputs are still put, with nothing proposed, until there are enough examples to hold an answer to
            rest = [k for k in range(len(self.rows)) if k not in self.asked]
            if not rest or len(self.tests) >= self.examples:
                return None
            return {"row": rest[0], "call": self.call(self.rows[rest[0]]["args"]), "choices": [], "an error": False}
        # Inputs every standing draft answers come first. Measured on the first 31 questions of the wider panel
        # (t/PREDICT-2026-10-05-examples.md): with the raising drafts counted as a group, the inputs asked first
        # were the ones half the drafts fail on, the person said "not allowed" to each, and the questions ran out
        # with no example approved.
        clean = [(k, row) for k, row in open_ if not self._raising(row)]
        best = max((self.split(row) for _k, row in clean), default=0.0)
        if best > 0:                                            # they answer differently: the most even split
            k, row = next((k, row) for k, row in clean if self.split(row) == best)
        elif clean and len(self.tests) < self.examples:         # plain examples, an answer not seen yet if there is one
            k, row = ([(k, row) for k, row in clean if self._groups(row)[0][0] not in self.results] or clean)[0]
        else:                                                   # last, the inputs some draft fails on
            unsure = [(k, row) for k, row in open_ if self._raising(row)]
            if not unsure:
                return None
            best = max(self.doubt(row) for _k, row in unsure)
            k, row = next((k, row) for k, row in unsure if self.doubt(row) == best)
        return {"row": k, "call": self.call(row["args"]), "choices": [said for said, _count in self._groups(row)],
                "an error": self._raising(row) > 0}

    def answer(self, row: int, value: str | None) -> None:
        """`value` is the right result as a Python literal, or None when the input should not be allowed."""
        self.asked.add(row)
        self.left -= 1
        if value is None:
            return
        ok, right = read_value(value)
        if not ok:
            raise ValueError(f"{value!r} is not a value this reads")
        self.tests.append(f"assert {self.call(self.rows[row]['args'])} == {repr(right)}")
        self.results.append(value)
        self.alive = {i for i in self.alive if self.rows[row]["said"][i] is not None
                      and canon(read_value(self.rows[row]["said"][i])[1]) == canon(right)}


def propose(decode, text: str, questions: int = QUESTIONS, n: int = DRAFTS, max_new: int = 768,
            header: str | None = None) -> tuple[Dialogue, dict]:
    """(the dialogue for a question, {"drafts", "left out", "fn", "kinds"}). Refused when no draft can be run."""
    if not py_sandbox.available():
        raise Refused(f"the drafts only run in a sandbox, and {py_sandbox.why_unavailable()}; give examples with --test")
    fs, left_out = drafts(decode, text, n, max_new, header)
    if not fs:
        raise Refused("the model wrote no Python draft that could be run to make examples from (" + "; ".join(left_out)[:300]
                      + "); give examples with --test \"assert f(...) == ...\"")
    names = collections.Counter(f["fn"] for f in fs)
    fn = max(names, key=lambda name: (names[name], -min(f["n"] for f in fs if f["fn"] == name)))
    kinds = shown_kinds(fs)
    named = next(f for f in fs if f["fn"] == fn)
    call = header.strip() if header else f"{fn}({', '.join(f'{p}: {k}' for p, k in zip(named['params'], kinds))})"
    tried = suggested(decode([suggestion(text, call)], 0.0, 0, "q", 256)[0][0], fn, kinds)
    inputs = tried + [args for args in verify_py.drawn_inputs(kinds, INPUTS) if not any(repr(args) == repr(t) for t in tried)]
    rows = run(fs, inputs)
    return Dialogue(fn, rows, questions), {"drafts": [f["n"] for f in fs], "left out": left_out, "fn": fn, "kinds": kinds,
                                           "suggested": len(tried)}


HOW = ("Before anything is proved, a few examples to make sure of what you mean (the model's drafts were run on them).\n"
       "Press Enter if the result shown is right. Type the right result if it is not. Type x if that input should not be allowed.\n")
LETTERS = "abcdefgh"


def interactive(d: Dialogue, ask=input, say=print) -> list[str]:
    """Put the questions in a terminal; the examples the person approved, as test lines. Where the drafts disagree
    their answers are lettered, and a letter picks one."""
    say(HOW)
    while (q := d.next()) is not None:
        lettered = dict(zip(LETTERS, q["choices"]))
        one = len(q["choices"]) == 1                            # one answer to accept, whether or not a draft fails
        if not q["choices"]:
            prompt = f"{q['call']}  should give what? (the right result, or x)  > "
        elif one:
            prompt = (f"{q['call']}  gives  {q['choices'][0]}"
                      + ("   (a draft fails on this input: x if it should not be allowed)" if q["an error"] else "") + "   > ")
        else:
            said = "   ".join(f"{k}) {v}" for k, v in lettered.items()) + ("   (and a draft fails on it)" if q["an error"] else "")
            prompt = f"{q['call']}  the drafts disagree:  {said}\n  Type {' or '.join(lettered)}, or the right result, or x:  > "
        while True:
            try:
                reply = ask(prompt).strip()
            except EOFError:                                    # the terminal went away: what was approved so far stands
                return d.tests
            if reply.lower() == NOT_ALLOWED:
                d.answer(q["row"], None)
                break
            if not reply and one:
                d.answer(q["row"], q["choices"][0])
                break
            if reply.lower() in lettered and not one:
                d.answer(q["row"], lettered[reply.lower()])
                break
            if reply and read_value(reply)[0]:
                d.answer(q["row"], reply)
                break
            say("  That is not a value I can read. Type it as you would write it: 9, [1, 3], True, 'abc'; or x." if reply
                else "  Nothing is proposed here: type the right result, or x." if not q["choices"]
                else "  The drafts disagree here, so there is nothing to accept: type a letter, the right result, or x.")
    return d.tests


def simulate(d: Dialogue, oracle) -> list[str]:
    """The dialogue with `oracle(args)` standing in for the person (TiCoder's idealised user): it returns the right
    result's repr, or None for an input it does not accept."""
    while (q := d.next()) is not None:
        d.answer(q["row"], oracle(d.rows[q["row"]]["args"]))
    return d.tests


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--python", required=True, help="host:port of the server holding the base model")
    ap.add_argument("--python-name", default="base")
    ap.add_argument("--text", required=True, help="the question, in words")
    ap.add_argument("--questions", type=int, default=QUESTIONS, help="at most this many examples are put to you")
    ap.add_argument("--json", type=Path, help="write the approved examples here")
    a = ap.parse_args(argv)
    try:
        d, made = propose(python_beside.api_decode("openai", [a.python], a.python_name), a.text, a.questions)
    except Refused as refused:
        print(f"examples: {refused}", file=sys.stderr)
        return 2
    tests = interactive(d)
    print("\nYour examples, as tests:" if tests else "\nNo example was approved.")
    for t in tests:
        print(f'  --test "{t}"')
    if a.json:
        a.json.write_text(json.dumps({"fn": made["fn"], "tests": tests, "drafts": made}, indent=1) + "\n", encoding="utf-8")
    return 0 if tests else 1


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
