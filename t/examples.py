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
  inputs      small inputs are drawn for those annotations (t/verify_py.py's pools) and every draft is run on
              them in the sandbox, so what a draft answers is a fact about it, not a guess
  questions   the input on which the drafts split most evenly comes first (TiCoder's score, the second largest
              group of drafts over the largest, with the drafts that raise counted as a group); the person presses
              Enter on the answer shown, types the right one, or says the input should not be allowed; drafts that
              answered otherwise are dropped
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
QUESTIONS = 4                  # at most this many examples are put to the person
EXAMPLES = 3                   # once the drafts no longer disagree, stop when this many are approved
INPUTS = 40                    # small inputs every draft is run on
NOT_ALLOWED = "x"


class Refused(Exception):
    """No examples can be proposed; the message says what the person can do instead."""


def question(text: str) -> list[dict]:
    kinds = ", ".join(verify_py._DRAWS)
    return [{"role": "system", "content": spec_first_rows.PY_SYSTEM},
            {"role": "user", "content": f"{text.strip()}\n\nWrite one Python function that does this. Give every parameter a type "
                                        f"annotation, one of: {kinds}. It reads no input and prints nothing."}]


def drafts(decode, text: str, n: int = DRAFTS, max_new: int = 768) -> tuple[list[dict], list[str]]:
    """(the drafts that can be run side by side, why each other reply was left out). A draft is
    verify_py.read_function's reading of one reply; they are kept when they take the same kinds of input, the
    kinds most drafts chose."""
    read, left_out = [], []
    for i in range(n):
        reply = decode([question(text)], 0.0 if i == 0 else spec_first.SAMPLE_TEMPERATURE, 0 if i == 0 else 1000 + i, "q", max_new)[0][0]
        code = spec_first.python_of(reply or "")
        if code is None:
            left_out.append(f"draft {i + 1}: no Python in the reply")
            continue
        try:
            f = verify_py.read_function(code)
        except verify_py.Refused as refused:
            left_out.append(f"draft {i + 1}: {refused}")
            continue
        if any(k is None for k in f["kinds"]):
            left_out.append(f"draft {i + 1}: a parameter has no annotation this reads")
        elif not any(f["code"] == g["code"] for g in read):
            read.append(dict(f, n=i + 1))
    if not read:
        return [], left_out
    shapes = collections.Counter(tuple(f["kinds"]) for f in read)
    shape = max(shapes, key=lambda s: (shapes[s], -min(f["n"] for f in read if tuple(f["kinds"]) == s)))
    left_out += [f"draft {f['n']}: it takes other kinds of input than most drafts" for f in read if tuple(f["kinds"]) != shape]
    return [f for f in read if tuple(f["kinds"]) == shape], left_out


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
        with py_sandbox.Session(f["code"] + verify_py._REPR.format(fn=f["fn"]), "_t_repr_call") as session:
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
        self.alive = set(range(len(rows[0]["said"]))) if rows else set()
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

    def split(self, row: dict) -> float:
        """TiCoder's discriminating score over the drafts still standing: 0 when they all do one thing, 1 when the
        two commonest things have as many drafts each. The drafts that raise on the input count as one group here
        (TiCoder leaves them out): whether an input is allowed at all is a question worth an early turn."""
        sizes = sorted([count for _said, count in self._groups(row)] + [sum(1 for i in self.alive if row["said"][i] is None)], reverse=True)
        return sizes[1] / sizes[0] if len(sizes) > 1 and sizes[0] else 0.0

    def next(self) -> dict | None:
        if self.left <= 0:
            return None
        open_ = [(k, row) for k, row in enumerate(self.rows) if k not in self.asked and self._groups(row)]
        if not open_:
            return None
        best = max(self.split(row) for _k, row in open_)
        if best == 0 and len(self.tests) >= self.examples:
            return None
        # among the most splitting inputs the plainest (drawn first); when none splits, one whose answer is new
        pick = [(k, row) for k, row in open_ if self.split(row) == best]
        fresh = [(k, row) for k, row in pick if self._groups(row)[0][0] not in self.results]
        k, row = (fresh or pick)[0] if best == 0 else pick[0]
        return {"row": k, "call": self.call(row["args"]), "choices": [said for said, _count in self._groups(row)],
                "an error": any(row["said"][i] is None for i in self.alive)}

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


def propose(decode, text: str, questions: int = QUESTIONS, n: int = DRAFTS, max_new: int = 768) -> tuple[Dialogue, dict]:
    """(the dialogue for a question, {"drafts", "left out"}). Refused when no draft can be run."""
    if not py_sandbox.available():
        raise Refused(f"the drafts only run in a sandbox, and {py_sandbox.why_unavailable()}; give examples with --test")
    fs, left_out = drafts(decode, text, n, max_new)
    if not fs:
        raise Refused("the model wrote no Python draft that could be run to make examples from (" + "; ".join(left_out)[:300]
                      + "); give examples with --test \"assert f(...) == ...\"")
    names = collections.Counter(f["fn"] for f in fs)
    fn = max(names, key=lambda name: (names[name], -min(f["n"] for f in fs if f["fn"] == name)))
    rows = run(fs, verify_py.drawn_inputs(fs[0]["kinds"], INPUTS))
    return Dialogue(fn, rows, questions), {"drafts": [f["n"] for f in fs], "left out": left_out, "fn": fn, "kinds": fs[0]["kinds"]}


HOW = ("Before anything is proved, a few examples to make sure of what you mean (the model's drafts were run on them).\n"
       "Press Enter if the result shown is right. Type the right result if it is not. Type x if that input should not be allowed.\n")
LETTERS = "abcdefgh"


def interactive(d: Dialogue, ask=input, say=print) -> list[str]:
    """Put the questions in a terminal; the examples the person approved, as test lines. Where the drafts disagree
    their answers are lettered, and a letter picks one."""
    say(HOW)
    while (q := d.next()) is not None:
        lettered = dict(zip(LETTERS, q["choices"]))
        if len(q["choices"]) == 1 and not q["an error"]:
            prompt = f"{q['call']}  gives  {q['choices'][0]}   > "
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
            if not reply and len(q["choices"]) == 1 and not q["an error"]:
                d.answer(q["row"], q["choices"][0])
                break
            if reply.lower() in lettered and not (len(q["choices"]) == 1 and not q["an error"]):
                d.answer(q["row"], lettered[reply.lower()])
                break
            if reply and read_value(reply)[0]:
                d.answer(q["row"], reply)
                break
            say("  That is not a value I can read. Type it as you would write it: 9, [1, 3], True, 'abc'; or x."
                if reply else "  The drafts disagree here, so there is nothing to accept: type a letter, the right result, or x.")
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
