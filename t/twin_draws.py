#!/usr/bin/env python3
"""t/twin_draws.py -- is a lifted program a gated pool problem's twin? Asked on drawn inputs (2026-09-26).

The lift's twin gate (t/lift_corpora.py twin_of) refused a lifted program as the behavioural twin of a
gated pool problem (held-out, dev split, same-task exclusion) when the program passed every one of that
problem's test points. Those problems carry one to three points, so the gate refused coincidences as
well: on the lift of 2026-09-26, 179 programs were refused this way, and single gated problems (202415,
350, 202551, 565) each "twinned" 9 to 13 unrelated programs.

This file asks the question the points cannot answer. A candidate (the program passes every point of
problem P) is run against P's reference solution on DRAWS inputs drawn like P's first point, with
t/spec_check.py's draw() seeded per problem (behavioural_decontam.draws_for), the same inputs the
project's behavioural rule of 2026-09-25 uses. The program is P's twin unless the two answer at least
one drawn input differently; one such input clears it of P. That is differential testing against the
ground truth on generated inputs "structurally similar to the seeds", which EvalPlus (Liu et al.,
https://ar5iv.labs.arxiv.org/html/2305.01210) showed catches programs a benchmark's few tests pass
("a logically flawed solution can still pass all simple tests"); research receipt 8de65a1ec350.

What counts, stated rather than implied:
- An input either side does not answer is dropped, never a difference: the program's requires excludes
  it, the interpreter finds it undefined or runs out of budget, or the reference raises, times out,
  runs out of recursion or memory. EvalPlus filters inputs outside the ground truth's precondition for
  the same reason: "ill-formed inputs can incur undefined behaviors ... false-positives".
- The reference's answer is read as a value of the program's own type, the way the pool reads an
  assertion's expected literal (mbpp_dfy._literal: a one-character string is a t character, a string is
  its code points) plus the leniencies Python's own == grants (True == 1, 20.0 == 20). The answer is kept
  as the reference gave it (behavioural_decontam.Runner's `read` hook) and read only at comparison time,
  as EvalPlus keeps the ground truth's raw outputs (receipt 4c1b6361a8b4): 'a' is 97 where the program
  returns an int and the one-element string [97] where it returns a seq, which a canonical form fixed in
  advance cannot tell apart. An answer with no such reading (a non-integral float, None, a dict, a list
  where the program returns an int) drops the draw.
- A drawn string whose code point render() would clamp is dropped: the reference would be asked another
  question than the program.
- The gate stays conservative the other way: a reference that does not load, a kind no draw can
  produce, or no draw both sides answer keeps the program P's twin.

What the rule cannot see: draws follow the example's shape (a non-negative example draws non-negative),
so a program that differs from P only outside that shape stays P's twin, which errs on the side of the
gate; and a reference wrong on some input outside its own tests (EvalPlus found over 10% of HumanEval's
ground truths wrong) can clear a program that answers that input correctly. Every verdict keeps its
counts and the first differing input, so a clearance on one input among many is there to be read.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import behavioural_decontam as bd                                # noqa: E402
import spec_experiment as se                                     # noqa: E402

DRAWS = 100                                   # inputs per candidate problem, all shaped like its first point
SEED = "lift-twin-2026-09-26"                 # draws seeded by problem alone: every program meets the same inputs
SOURCES = ("https://ar5iv.labs.arxiv.org/html/2305.01210",
           "https://raw.githubusercontent.com/evalplus/evalplus/master/evalplus/eval/__init__.py")
RULE = ("a lifted program that passes every test point of a gated pool problem is that problem's twin unless, "
        f"on {DRAWS} inputs drawn like the problem's first point (spec_check.draw, seeded per problem), the program "
        "and the problem's reference answer at least one input differently, the reference's answer read as a value "
        "of the program's own type; an input either side does not answer, or whose answer has no such reading, is "
        "dropped; a reference that does not load, a kind no draw can produce, or no input both answer keeps the "
        "program the twin; a program is admitted only when it is the twin of no gated problem")
VERDICTS = ("differs", "agrees", "no draw answered by both", "no reference", "cannot draw")
MAX_CODE_POINT = 0x10FFFF


class Opaque:
    """A reference answer no t value can be read from (a dict, a set, a generator), named by its type."""

    __slots__ = ("kind",)

    def __init__(self, kind: str):
        self.kind = kind

    def __repr__(self) -> str:
        return f"<{self.kind}>"

    def __eq__(self, other) -> bool:
        return isinstance(other, Opaque) and other.kind == self.kind

    def __hash__(self) -> int:
        return hash(("Opaque", self.kind))


def answer_form(value):
    """A reference's answer copied into immutable Python: None, bool, int, float and str as they are, a
    list or tuple as a tuple of forms, anything else Opaque. Strings stay strings (canon would not keep
    them), and a list the reference goes on mutating cannot change the answer after it was given."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return tuple(answer_form(x) for x in value)
    return Opaque(type(value).__name__)


def _int(form):
    """A form as a t int: an int, a bool (True == 1 to Python), an integral float, a one-character string
    (a t character); else None."""
    if isinstance(form, bool):
        return int(form)
    if isinstance(form, int):
        return form
    if isinstance(form, float):
        if form == form and form not in (float("inf"), float("-inf")) and form.is_integer():
            return int(form)
        return None
    if isinstance(form, str) and len(form) == 1:
        return ord(form)
    return None


def _row(form):
    """A form as one row of a nested seq: a string's code points (a one-character string is a row of one,
    as mbpp_dfy's nested_strings reading has it), or a sequence whose every element reads as an int."""
    if isinstance(form, str):
        return tuple(ord(c) for c in form)
    if isinstance(form, tuple):
        items = [_int(x) for x in form]
        if all(x is not None for x in items):
            return tuple(items)
    return None


def _depth(like: tuple) -> int:
    """0 for the empty seq (its depth is unknown), 2 for a seq of seqs, 1 for a flat one."""
    if not like:
        return 0
    return 2 if isinstance(like[0], tuple) else 1


def read_answer(form, like):
    """The reference's answer (an answer_form) read as a value of the program's type, the type of `like`
    (the program's own answer: a bool, an int, or a seq as a tuple); None when it has no such reading."""
    if isinstance(like, bool):
        if isinstance(form, bool):
            return form
        if isinstance(form, (int, float)):
            number = _int(form)
            return bool(number) if number in (0, 1) else None
        return None
    if isinstance(like, int):
        return _int(form)
    if not isinstance(like, tuple):
        return None
    depth = _depth(like)
    if isinstance(form, str):
        return tuple(ord(c) for c in form) if depth < 2 else None
    if not isinstance(form, tuple):
        return None
    if depth < 2:
        flat = [_int(x) for x in form]
        if all(x is not None for x in flat):
            return tuple(flat)
        if depth == 1:
            return None
    rows = [_row(x) for x in form]
    return tuple(rows) if all(r is not None for r in rows) else None


def faithful(value, shape) -> bool:
    """Whether behavioural_decontam.render hands the reference this very t value. render clamps a code
    point outside 0..0x10FFFF into range, which would ask the reference another question than the
    program is asked; such a draw is dropped."""
    if shape == ("str",):
        points = value if isinstance(value, (list, tuple)) else [value]
        return all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= MAX_CODE_POINT for c in points)
    if shape is None or shape == ("scalar",) or not isinstance(value, (list, tuple)):
        return True
    return all(faithful(x, shape[1]) for x in value)


def _tupled(value):
    """run_point's JSON-shaped answer (interp._j: a seq as a list) back as t's own tuples."""
    if isinstance(value, list):
        return tuple(_tupled(x) for x in value)
    return value


def program_answer(task: dict, kinds: list, args: list, expected) -> tuple:
    """("ok", the program's answer) or (why it gave none,). The program runs through spec_experiment.run_point,
    the function its test points ran through: its requires excluding the input, a read outside a
    sequence, the interpreter's budget and a crash are its own verdicts; an arithmetic or memory error the
    interpreter does not name is a crash too. `expected` only has to be well-formed; the answer is used."""
    try:
        result = se.run_point(task, {"args": list(zip(kinds, args)), "expected": expected})
    except (ArithmeticError, MemoryError) as error:
        return (f"crash: {type(error).__name__}",)
    if result["verdict"] in ("pass", "fail"):
        return ("ok", _tupled(result["got"]))
    return (result["verdict"],)


def runner(pool: dict, hung_path: Path | None = None) -> bd.Runner:
    """A reference runner for the twin check: behavioural_decontam's (a CPU timeout per call, a budget per
    reference, answers cached per input), keeping each answer as given. A reference that swallowed its
    timeout makes the process exit (behavioural_decontam._wall_backstop, exit status 70) after naming it
    in hung_path; the next run refuses that reference by name, so its candidates stay twins."""
    refuse = bd.read_hung(hung_path) if hung_path else {}
    bd._TIMER["hung_path"] = str(hung_path) if hung_path else None
    return bd.Runner(pool, refuse=refuse, read=answer_form)


def draw_check(task: dict, tid: int, entry: dict, reference_runner: bd.Runner, n: int = DRAWS,
               seed: str = SEED) -> dict:
    """The program against pool problem tid's reference on n inputs drawn like that problem's first point.

    Returns the counts, the verdict (one of VERDICTS), `twin` (whether this problem still refuses the
    program), `why` when the check could not run, and `witness`, the first input both answered
    differently."""
    check = {"problem": int(tid), "draws": 0, "answered_by_both": 0, "agreed": 0, "differed": 0,
             "program_silent": 0, "reference_silent": 0, "no_t_reading": 0, "unfaithful": 0}
    if reference_runner.reference(tid) is None:
        return _decided(check, "no reference", reference_runner.why_not_run(tid))
    kinds = [k for k, _v in entry["points"][0]["args"]]
    draws = bd.draws_for(tid, entry, n=n, seed=seed)
    if draws is None:
        return _decided(check, "cannot draw", f"spec_check.draw has no draw for the kinds {kinds}")
    expected = entry["points"][0]["expected"]
    shapes = reference_runner.shapes[tid]
    for args in draws:
        check["draws"] += 1
        if not all(faithful(a, s) for a, s in zip(args, shapes)):
            check["unfaithful"] += 1
            continue
        mine = program_answer(task, kinds, args, expected)
        if mine[0] != "ok":
            check["program_silent"] += 1
            continue
        theirs = reference_runner.call(tid, args)
        if theirs[0] != "ok":
            check["reference_silent"] += 1
            continue
        reading = read_answer(theirs[1], mine[1])
        if reading is None:
            check["no_t_reading"] += 1
            continue
        check["answered_by_both"] += 1
        if reading == mine[1]:
            check["agreed"] += 1
            continue
        check["differed"] += 1
        if "witness" not in check:
            check["witness"] = {"input": bd._brief(list(args)), "program": bd._brief(mine[1]),
                                "reference": bd._brief(theirs[1])}
    if check["differed"]:
        return _decided(check, "differs")
    if check["answered_by_both"]:
        return _decided(check, "agrees")
    return _decided(check, "no draw answered by both", reference_runner.why_not_run(tid))


def _decided(check: dict, verdict: str, why: str | None = None) -> dict:
    check["verdict"] = verdict
    check["twin"] = verdict != "differs"
    if why:
        check["why"] = why
    return check
