#!/usr/bin/env python3
"""t/spec_check.py -- does an accepted answer's specification agree with the problem's own solution? (2026-09-18)

    python3 t/spec_check.py [--pool v4] [--n 200] [--only clean] [tag ...]

The seven proof systems check a program against its specification. Nothing checks the specification against the
problem. The ablation of 2026-09-17 measured what that costs: on held-out answers, where the model writes its
own specification, every proof gate admits wrong answers about 97 percent of the time, and only the tests catch
it. The tests are three assertions.

This runs the missing check. For each task it draws random arguments of the shapes the problem's own assertions
use, calls the problem's reference solution on them, and evaluates the task's `ensures` with that result bound
to the return variable, using t's own interpreter. An `ensures` that reads false on an input the reference
solution answers is a specification that disagrees with the problem, and every answer it admits is a false
accept that seven provers and a refuted twin both missed.

Disagreements are reported with the input that shows them. The reference solutions come from the corpus records
(nl/), and they are executed in this process, so run it on a corpus you trust.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import datetime
import hashlib
import json
import re
import random
import signal
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness                                                  # noqa: E402
import interp                                                   # noqa: E402
import loop_filter                                             # noqa: E402
import spec_experiment as se                                    # noqa: E402
import surface                                                 # noqa: E402

KERNELS = ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"]


def task_sha256(task: dict) -> str:
    """Bind a check to the exact canonical program, including its specification."""
    return hashlib.sha256(surface.print_task(task).strip().encode("utf-8")).hexdigest()


def problem_id(name: str, extracted: dict) -> int | None:
    """Recover the pool ID, keeping HumanEval and APPS separate from MBPP."""
    ids = {int(tid) for tid, entry in extracted.items()
           if str(tid).isdigit() and entry.get("name") == name}
    if len(ids) > 1:
        raise ValueError(f"ambiguous problem IDs for {name}: {sorted(ids)}")
    # every name family a corpus or answer set uses, including the Dafny-dataset
    # lifts (dafny_synthesis_task_id_N__) that the old (mbpp|he|apps) pattern
    # missed; the same function the corpus builder and preflight use (A1)
    named = loop_filter.problem_id(name)
    if ids:
        tid = next(iter(ids))
        if named is not None and tid != named:
            raise ValueError(f"extract ID {tid} disagrees with task name {name}")
        return tid
    return named


class Timeout(Exception):
    pass


def _alarm(_sig, _frm):
    raise Timeout()


@contextlib.contextmanager
def _deadline_alarm(seconds: float, exc=Timeout):
    """Unix: the real-time interval timer (signal.setitimer, "Availability: Unix"), the same clock
    signal.alarm rang before 2026-09-30 and score_synthesis rang on its own; float seconds allowed."""
    def _raise(_sig, _frm):
        raise exc()
    signal.signal(signal.SIGALRM, _raise)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


@contextlib.contextmanager
def _deadline_thread(seconds: float, exc=Timeout):
    """Elsewhere: a watchdog thread raises `exc` in this thread with PyThreadState_SetAsyncExc
    (docs.python.org/3/c-api/threads.html), the mechanism stopit's ThreadingTimeout uses
    (github.com/glenfant/stopit) and pytest-timeout's thread method reaches for where SIGALRM is
    missing (pytest_timeout.py: HAVE_SIGALRM decides the method). It interrupts Python bytecode
    only: a reference stuck inside one C call ends when that call returns. A firing that has not
    landed when the block ends is cleared by passing NULL; one that lands in the same instant is
    reported as a timeout."""
    import ctypes
    target = ctypes.c_ulong(threading.get_ident())
    timer = threading.Timer(seconds, ctypes.pythonapi.PyThreadState_SetAsyncExc,
                            (target, ctypes.py_object(exc)))
    timer.daemon = True
    timer.start()
    try:
        yield
    finally:
        timer.cancel()
        ctypes.pythonapi.PyThreadState_SetAsyncExc(target, None)


def deadline(seconds: float, exc=Timeout):
    """Raise `exc` (default Timeout) in the calling thread if the block runs longer than `seconds`
    (2026-09-30: the evaluation path runs on Windows too). Unix keeps the real-time signal, so
    nothing measured there changes. `exc` lets a caller keep its own class: score_synthesis's
    Timeout is a BaseException on purpose, so an interpreter's `except Exception` cannot absorb it."""
    return (_deadline_alarm(seconds, exc) if hasattr(signal, "SIGALRM")
            else _deadline_thread(seconds, exc))


MAX_REFERENCE_TIMEOUTS = 5      # draws the reference did not finish before a check stops drawing
CROSS_PER_DRAW = 3              # earlier draws whose answers are put to the ensures as wrong ones
MIN_COMPLETENESS = 0.6          # SAFE's floor for a usable specification (arXiv:2410.15756, 3.2)


def keep_witnesses(old: dict, new: dict) -> dict:
    """Verdicts after a re-check, where a disagreement found earlier is not forgotten.

    A `disagrees` verdict carries an input at which the specification is false of the
    problem's own answer: a counterexample, and it does not expire because a later check drew
    other inputs. EvalPlus grows a problem's tests and never drops one (gen/mut_gen.py appends
    to the seed pool). So where `new` reads `agrees` and `old` held a disagreement for the SAME
    task contents (task_sha256), the old verdict stands, marked as kept. Everything else is
    `new`'s."""
    out = dict(new)
    for key, n in new.items():
        o = old.get(key) or {}
        if (n.get("status") == "agrees" and o.get("status") == "disagrees"
                and o.get("task_sha256") and o.get("task_sha256") == n.get("task_sha256")):
            out[key] = dict(o, kept_from_an_earlier_check=True)
    return out


def complete(result: dict, floor: float = MIN_COMPLETENESS) -> bool | None:
    """Does an agreeing specification also pin the answer down? False when either mutant family
    measured (outputs near the right one; other inputs' answers) is rejected less than `floor` of
    the time, True when every family measured clears it, None when no mutant was judged."""
    shares = [result[k] for k in ("completeness", "cross_completeness") if isinstance(result.get(k), (int, float))]
    if not shares:
        return None
    return all(x >= floor for x in shares)


def draw(kind: str, rnd: random.Random, like=None, strings: bool = False):
    """A random value of the kind a problem's own assertions use, shaped like the problem's own example.

    `strings` (2026-10-01, t/PREDICT-2026-10-01-spec-check-coverage.md): the position is one where
    the assertion passes a LIST OF STRINGS. Its rows are then drawn in the example's shape, as every
    other kind is: about as many rows, about as long, code points near the example's. Without it a
    nested value is drawn as it always was (integers from -4 to 4), so no other draw moves.

    2026-09-18: drawing freely finds disagreements that are the REFERENCE's fault, not the specification's.
    mbpp_733's reference is a binary search, so it answers -1 on an unsorted array although the element is
    there; the problem never says its inputs are sorted. An example argument from the problem's own assertions
    carries those unstated preconditions, so a draw copies its shape: a sorted example stays sorted, an example
    of characters stays characters, a positive example stays positive."""
    if kind == "int":
        if isinstance(like, int) and not isinstance(like, bool):
            lo, hi = (0, max(2, abs(like) * 2)) if like >= 0 else (-max(2, abs(like) * 2), 0)
            return rnd.randint(lo, hi)
        return rnd.choice([rnd.randint(-8, 8), rnd.randint(0, 40)])
    if kind == "bool":
        return rnd.random() < 0.5
    if kind == "seq":
        ex = list(like) if isinstance(like, (list, tuple)) else []
        n = rnd.randint(0, max(3, len(ex) + 2))
        if ex and all(isinstance(x, int) for x in ex):
            lo, hi = min(ex), max(ex)
            lo, hi = (lo - 2, hi + 2) if lo != hi else (lo - 2, lo + 2)
            vals = [rnd.randint(lo, hi) for _ in range(n)]
            if ex == sorted(ex):
                vals.sort()
            return vals
        return [rnd.randint(-6, 6) for _ in range(n)]
    if kind == "seq-of-seq":
        rows = [list(r) for r in like if isinstance(r, (list, tuple))] if isinstance(like, (list, tuple)) else []
        points = [x for r in rows for x in r if isinstance(x, int) and not isinstance(x, bool)]
        if strings and points:
            lo, hi = max(0, min(points) - 2), max(points) + 2
            longest = max(len(r) for r in rows)
            return [[rnd.randint(lo, hi) for _ in range(rnd.randint(0, longest + 2))]
                    for _ in range(rnd.randint(0, len(rows) + 2))]
        return [[rnd.randint(-4, 4) for _ in range(rnd.randint(0, 3))] for _ in range(rnd.randint(0, 3))]
    return None


FAR = 0.15                     # of the larger draws, the share drawn far past the examples


def draw_beyond(kind: str, rnd: random.Random, like=None, strings: bool = False, share: float = 0.7):
    """A value in the example's style and LARGER than any `draw` makes of it (2026-10-05).

    `draw` stops at the longest example plus two elements, and at twice the example for an integer. A larger writer
    found what that leaves open: a specification that spells out the cases up to that size and says nothing after
    them (`if len(s) == 0 then ... else if len(s) == 6 then ... else r`) held on every draw and rejected every wrong
    output, because no draw was longer than six. QuickCheck grows its test size to 100 as a run proceeds
    (Test/QuickCheck/Test.hs, `maxSize`), and EvalPlus (arXiv:2305.01210) found tests the size of a benchmark's own
    missing a fifth to a quarter of wrong programs. Research receipt 5deec846ed0c.

    A `share` of the draws are larger: most from just past `draw`'s bound to about three times it, and FAR of them
    far past it (sequences of 28 to 40, integers to twenty times the bound), because a case-by-case specification
    costs its writer text that grows with the size it covers, and an answer has a budget. The style is the
    example's (a sorted example stays sorted, code points stay near the example's). The rest are ordinary draws, so a
    problem whose arguments constrain each other still gets inputs it defines; with one argument every draw is
    larger (`beyond_drawer`)."""
    if kind == "bool" or rnd.random() >= share:
        return draw(kind, rnd, like, strings)
    far = rnd.random() < FAR
    if kind == "int":
        if isinstance(like, int) and not isinstance(like, bool):
            top = max(2, abs(like) * 2)
            x = rnd.randint(4 * top, 20 * top) if far else rnd.randint(top + 1, max(top * 3, top + 12))
            return x if like >= 0 else -x
        return rnd.choice([rnd.randint(41, 160), -rnd.randint(9, 40)]) if not far else rnd.randint(161, 800)
    if kind == "seq":
        ex = list(like) if isinstance(like, (list, tuple)) else []
        top = max(3, len(ex) + 2)
        n = rnd.randint(28, 40) if far else rnd.randint(top + 1, max(top * 3, 12))
        if ex and all(isinstance(x, int) for x in ex):
            lo, hi = min(ex), max(ex)
            lo, hi = (lo - 2, hi + 2) if lo != hi else (lo - 2, lo + 2)
            vals = [rnd.randint(lo, hi) for _ in range(n)]
            if ex == sorted(ex):
                vals.sort()
            return vals
        return [rnd.randint(-6, 6) for _ in range(n)]
    if kind == "seq-of-seq":
        rows = [list(r) for r in like if isinstance(r, (list, tuple))] if isinstance(like, (list, tuple)) else []
        points = [x for r in rows for x in r if isinstance(x, int) and not isinstance(x, bool)]
        count = rnd.randint(16, 24) if far else rnd.randint(max(4, len(rows) + 3), max(8, 3 * (len(rows) + 2)))
        if strings and points:
            lo, hi = max(0, min(points) - 2), max(points) + 2
            longest = max(len(r) for r in rows)
            return [[rnd.randint(lo, hi) for _ in range(rnd.randint(0, longest + 2))] for _ in range(count)]
        return [[rnd.randint(-4, 4) for _ in range(rnd.randint(0, 3))] for _ in range(count)]
    return None


LARGER_DRAWS = 200             # larger inputs a scored verdict is held to (the product's gate asks 60, for its latency)
MIN_LARGER = 5                 # of them inside the `requires` before the measurement counts
# INVENTED: no published number. A `requires` may rightly exclude inputs (a problem's unstated precondition), and
# larger inputs fall outside a right one more often than ordinary inputs do: measured 2026-10-05, a floor on the share
# of larger inputs admitted refused two right specifications (every character a hexadecimal digit, where the
# reference answers any string and a longer random string is less often all digits; one length argument not above
# another). So the share is held against the share of ordinary draws admitted, and only for a `requires` that itself
# puts a number above a length or a parameter (`len(s) <= 6`, `n < 5`): under half is a `requires` that stops at
# the size of the examples.
LARGER_DOMAIN_RATIO = 0.5


def caps_size(task: dict) -> bool:
    """Does a `requires` bound a parameter, or the length of one, from above by a number?"""
    names = {p["name"] for p in task.get("params", [])}

    def sized(e) -> bool:
        return isinstance(e, dict) and (e.get("var") in names or (e.get("op") == "len" and len(e.get("args", [])) == 1
                                                                 and isinstance(e["args"][0], dict) and e["args"][0].get("var") in names))

    def walk(e) -> bool:
        if isinstance(e, list):
            return any(walk(x) for x in e)
        if not isinstance(e, dict):
            return False
        a = e.get("args")
        if e.get("op") in ("<", "<=", "==") and isinstance(a, list) and len(a) == 2 and sized(a[0]) and "int" in (a[1] or {}):
            return True
        if e.get("op") in (">", ">=", "==") and isinstance(a, list) and len(a) == 2 and sized(a[1]) and "int" in (a[0] or {}):
            return True
        return any(walk(v) for v in e.values())
    return walk(task.get("requires", []))


def _admitted(result: dict) -> float | None:
    inside, outside = result.get("draws", 0) or 0, result.get("outside_requires", 0) or 0
    return inside / (inside + outside) if inside + outside else None


def larger_reason(larger: dict | None, floor: float = 0.6, ordinary: dict | None = None) -> str | None:
    """Why a specification that stands on inputs the size of the examples does not stand on larger ones
    (`larger_inputs`'s result); None when it does, when it was not measured, or when too few larger inputs could be
    judged to say. `ordinary` is the same check's result on the ordinary draws, for the `requires` (above)."""
    if not larger:
        return None
    if larger.get("status") == "disagrees":
        return "the specification is false at the solution's answer on an input larger than the examples"
    if larger.get("status") != "agrees":
        return None
    inside, outside = larger.get("draws", 0) or 0, larger.get("outside_requires", 0) or 0
    if larger.get("requires_caps_size") and inside + outside >= MIN_LARGER:
        before = _admitted(ordinary) if ordinary else None
        if _admitted(larger) < LARGER_DOMAIN_RATIO * (before if before is not None else 1.0):
            return "the requires closes off inputs larger than the examples"
    if inside >= MIN_LARGER and complete(larger, floor) is False:
        return "the specification says too little about inputs larger than the examples"
    return None


_LARGER_KEEP = ("status", "draws", "outside_requires", "completeness", "cross_completeness", "mutants_rejected",
                "mutants_accepted", "cross_rejected", "cross_accepted", "skipped", "args", "reference_said", "ensures",
                "weak_witness", "cross_witness")


def larger_inputs(task: dict, entry: dict, seed, n: int = LARGER_DRAWS, oracle=None) -> dict:
    """The check on `n` inputs larger than the examples, from a generator of its own (seeded by `seed`), so asking
    for it moves no other draw. What a verdict stores under "larger"."""
    r = check_task(task, entry, n, random.Random(f"larger:{seed}"), oracle=oracle, drawer=beyond_drawer(len(task["params"])))
    return {**{k: r[k] for k in _LARGER_KEEP if k in r}, "requires_caps_size": caps_size(task)}


def beyond_drawer(arguments: int):
    """`draw_beyond` for a problem of that many arguments: every draw larger when there is one argument, seven in ten
    of each argument's draws when there are several."""
    share = 1.0 if arguments == 1 else 0.7
    return lambda kind, rnd, like=None, strings=False: draw_beyond(kind, rnd, like, strings, share)


def to_t(value, kind: str | None = None):
    """A Python value from the reference solution as an interpreter value, read the way the pool
    reads the problem's own assertions (t/mbpp_dfy.py `_literal`, SPEC.md "Strings as sequences of
    code points"). A string is a seq of code points; where the declared `kind` is int, a
    one-character string is that character, as the notation's 'a' is sugar for 97; a list whose
    every element is a one-character string is a flat seq of code points (`split('python') ==
    ['p', 'y', ...]`), as the assertion parser reads that literal, unless the kind is seq-of-seq."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        # The problem's own assertions compare with Python equality, under which 3.0 == 3
        # (EvalPlus compares outputs the same way: evalplus/eval/__init__.py, `out == exp`).
        # MBPP 78's solution returns (n + 1) / 2. A float that is not a whole number has no t value.
        if value != value or value in (float("inf"), float("-inf")) or value != int(value):
            raise TypeError("unsupported reference result: a float that is not a whole number")
        return int(value)
    if isinstance(value, str):
        if kind == "int" and len(value) == 1:
            return ord(value)
        return tuple(ord(c) for c in value)
    if isinstance(value, (list, tuple)):
        # `kind` is the pool's name for a nested value (`seq-of-seq`) when a point is read and the
        # TASK's declared type (surface.py's {"seq": "seq"} for `seq<seq>`) when a reference result
        # is read. Until 2026-10-01 only the first spelling counted as nested here, so a reference
        # that returned ['i'] for a task returning `seq<seq>` was read as the flat string (105,)
        # and the `ensures` then took len() of an integer ("interpreter refused").
        nested = kind == "seq-of-seq" or kind == {"seq": "seq"}
        if not nested and value and all(isinstance(x, str) and len(x) == 1 for x in value):
            return tuple(ord(x) for x in value)
        inner = "seq" if nested else None
        return tuple(to_t(x, inner) for x in value)
    raise TypeError(f"unsupported reference result: {type(value).__name__}")


def string_positions(entry: dict) -> list[int]:
    """The argument positions that are str literals in the problem's first parseable assertion:
    the positions where the reference expects a str, which t represents as a seq of code points
    (a one-character str as an int)."""
    for src in entry.get("rec", {}).get("test_list", []) or []:
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == entry.get("fn"):
                return [i for i, a in enumerate(node.args)
                        if isinstance(a, ast.Constant) and isinstance(a.value, str)]
    return []


def bound_inputs(params: list, args: list, positions: list[int]) -> dict:
    """The drawn arguments as interpreter values under the task's parameters. A character drawn
    for a string position is a one-character string where the task declares a string: the
    problem's first assertion passed a one-character literal, the kinds therefore say `int`, and
    a task that (rightly) declares `seq` used to be handed an integer and the check ended with
    "interpreter refused" (spec_experiment.mark_characters has the test-harness half, 2026-10-01)."""
    env = {}
    for i, (p, a) in enumerate(zip(params, args)):
        if i in positions and p.get("type") == "seq" and isinstance(a, int) and not isinstance(a, bool):
            env[p["name"]] = (a,)
        else:
            env[p["name"]] = to_t(a)
    return env


def nested_string_positions(entry: dict) -> list[int]:
    """The argument positions that are a list of str literals in the problem's first parseable
    assertion: where the reference expects a list of str. t holds such a value as a seq<seq> of
    code points, or as a flat seq when every string is one character."""
    for src in entry.get("rec", {}).get("test_list", []) or []:
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == entry.get("fn"):
                return [i for i, a in enumerate(node.args)
                        if isinstance(a, (ast.List, ast.Tuple)) and a.elts
                        and all(isinstance(x, ast.Constant) and isinstance(x.value, str) for x in a.elts)]
    return []


def python_arguments(args: list, positions: list[int], nested: list[int] | tuple = ()) -> list:
    """The drawn arguments as the reference's own assertions pass them (2026-09-30, receipt
    ad806d032e1a): a str where the assertion passed a str literal, joined from the code points,
    a one-character str for a character argument, a list elsewhere. Before this the reference was
    handed a list of integers for every string, and a solution that compares against character
    literals then ran and computed another function without raising (MBPP 771's bracket balancer
    answered "the length is even"). EvalPlus keeps a str a str when it grows test inputs
    (arXiv:2305.01210); this is the same rule for the reference call."""
    out = []
    for i, a in enumerate(args):
        if i in nested and isinstance(a, (list, tuple)):
            # 2026-10-01: a list of strings stays a list of strings (EvalPlus's typed mutation keeps
            # types element by element, evalplus/gen/type_mut.py). Until now the rows went over as
            # lists of integers and MBPP 91's `any(sub in s for s in words)` asked whether a string
            # is an element of a list of numbers. chr() raises on a value that is no code point,
            # and the caller treats that draw as one the problem does not define.
            out.append(["".join(chr(c) for c in row) if isinstance(row, (list, tuple)) else chr(row) for row in a])
        elif i in positions and isinstance(a, (list, tuple)):
            out.append("".join(chr(c) for c in a))
        elif i in positions and isinstance(a, int) and not isinstance(a, bool):
            out.append(chr(a))
        else:
            out.append(list(a) if isinstance(a, (list, tuple)) else a)
    return out


def mutations(value):
    """Wrong outputs derived from a right one, deterministically.

    The completeness half of the check, after arXiv 2603.17150: a specification
    that is true of the right answer and also true of a wrong one does not say
    what the problem asked. arXiv 2608.13077 makes the same measurement its
    primary metric and finds it separates models where acceptance metrics do
    not (28.05% against 4.27%).

    Deterministic on purpose. This file threads one seeded generator through
    every task in order, so consuming a draw here would change every downstream
    verdict and every report already cited. Mutations come from the value.
    """
    out = []
    if isinstance(value, bool):
        out.append(not value)
    elif isinstance(value, int):
        # A neighbourhood, not four guesses. CLEVER (arXiv:2505.13938) and
        # VeriEquivBench (arXiv:2510.06296) both state the strong form of this
        # as a proof obligation -- no output other than the right one may
        # satisfy the specification -- and score a spec zero when it is merely
        # sound. We cannot prove that against a Python reference, so we search:
        # the wider the search that finds nothing, the stronger the negative.
        out += [value + d for d in range(-4, 5) if d]
        out += [0, 1, -1, -value, value * 2, value // 2 if value else 7]
    elif isinstance(value, tuple):
        rows = all(isinstance(x, tuple) for x in value) and bool(value)
        if value:
            out.append(value[:-1])                                  # dropped the last element
            head = value[0]
            if isinstance(head, bool):
                out.append((not head,) + value[1:])
            elif isinstance(head, int):
                out.append((head + 1,) + value[1:])
            if len(value) > 1:
                out.append(tuple(reversed(value)))
                out.append(value[1:])                       # dropped the first
                out.append((value[1], value[0]) + value[2:])  # swapped the first two
            if isinstance(head, int) and not isinstance(head, bool):
                out.append((head - 1,) + value[1:])
                out.append((0,) + value[1:])
        out.append(value + ((),) if rows else value + (0,))          # one element too many
    seen, unique = set(), []
    for candidate in out:
        if candidate == value:
            continue                       # not a wrong answer; says nothing either way
        key = repr(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def with_reference_plus(pool: dict, path) -> tuple[dict, int]:
    """The pool with MBPP+'s solutions (EvalPlus, arXiv:2305.01210; huggingface.co/datasets/evalplus/mbppplus) in
    place of MBPP's own, for every MBPP problem MBPP+ holds whose solution defines the same function. EvalPlus
    corrected MBPP solutions that disagree with their own task (2026-10-02: 605's primality test checked only the
    divisor 2). Returns (pool, number swapped); the input pool is not changed."""
    import copy
    plus = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            plus[int(r["task_id"])] = r["code"]
    out, swapped = dict(pool), 0
    for tid, entry in pool.items():
        code = plus.get(int(tid)) if int(tid) < 100000 else None
        # EvalPlus also changed some tasks' contract (454 returns a bool where MBPP's own tests expect the strings
        # 'Found a match!' and 'Not matched!'), so MBPP+'s solution replaces MBPP's only where it passes the
        # problem's own test assertions (found on the first re-score, 2026-10-02)
        if code and re.search(rf"\bdef\s+{re.escape(entry['fn'])}\s*\(", code) and passes_own_tests(code, entry):
            e = copy.deepcopy(entry)
            e["rec"]["code"] = code
            out[tid] = e
            swapped += 1
    return out, swapped


def passes_own_tests(code: str, entry: dict) -> bool:
    """Does this solution pass the problem's own `assert` lines (MBPP's test_list)?"""
    tests = entry.get("rec", {}).get("test_list") or []
    if not tests:
        return False
    g: dict = {"__builtins__": __builtins__}
    try:
        exec("import math, collections, itertools, functools, re, heapq, bisect, string\n"
             "from typing import List, Dict, Tuple, Set, Optional, Any\n", g)
        with deadline(5):
            exec(compile(code, "<reference-plus>", "exec"), g)        # noqa: S102  (EvalPlus's reference solution)
            for t in tests:
                exec(compile(t, "<test>", "exec"), g)                 # noqa: S102  (the problem's own assertion)
        return True
    except BaseException:                                           # noqa: BLE001  (an assertion, an error, a timeout)
        return False


def reference(rec: dict, fn: str):
    """The problem's own solution as a callable, or None when it will not run."""
    code = rec.get("code") or ""
    if not code.strip():
        return None
    # the corpus's own solutions assume the imports their site had: APPS solutions are LeetCode-shaped and
    # annotate with List and Dict, MBPP's use math and collections (2026-09-18)
    g: dict = {"__builtins__": __builtins__}
    try:
        exec("import math, collections, itertools, functools, re, heapq, bisect, string\n"
             "from typing import List, Dict, Tuple, Set, Optional, Any\n", g)
    except Exception:                                           # noqa: BLE001
        pass
    try:
        exec(compile(code, f"<{fn}>", "exec"), g)                # noqa: S102  (corpus reference solution)
    except Exception:                                           # noqa: BLE001
        return None
    f = g.get(fn)
    return f if callable(f) else None


def lazy_functions():
    """The laziest programs anyone could write, as callables over the arguments.

    AlphaVerus (arXiv:2412.06176, github.com/cmu-l3/alphaverus) calls this the
    **exploit model**: write the laziest program that satisfies the
    specification, and if it verifies, the specification is broken. They report
    that without this filter `assume(false)` snowballed across every program and
    progress plateaued.

    Enumerating the lazy programs is stronger than perturbing one output,
    because it asks whether an entire wrong *function* satisfies the spec rather
    than whether one wrong *answer* does. It needs no model and no prover: the
    interpreter evaluates the ensures with the lazy program's result in place of
    the real one.
    """
    def first(args):
        return args[0] if args else None

    return [
        ("constant zero", lambda args: 0),
        ("constant one", lambda args: 1),
        ("constant false", lambda args: False),
        ("constant true", lambda args: True),
        ("empty sequence", lambda args: ()),
        ("returns its first argument", first),
        ("first argument plus one",
         lambda args: first(args) + 1 if isinstance(first(args), int)
         and not isinstance(first(args), bool) else None),
        ("length of the first argument",
         lambda args: len(first(args)) if isinstance(first(args), tuple) else None),
        ("the larger of the first two",
         lambda args: max(args[0], args[1]) if len(args) > 1
         and all(isinstance(a, int) and not isinstance(a, bool) for a in args[:2]) else None),
        ("the first argument, reversed",
         lambda args: tuple(reversed(first(args))) if isinstance(first(args), tuple) else None),
    ]


def exploit(task: dict, entry: dict) -> dict:
    """Does a lazy program satisfy this specification and still fail the problem?

    A specification that a constant or an identity function satisfies has not
    described the problem, however many provers discharge it. Returns the first
    lazy program that gets away with it, or nothing.
    """
    funs = interp.funs_of(task, task["body"])
    name = task["returns"][0]["name"]
    points = [p for p in entry.get("points", [])
              if len(p.get("args", [])) == len(task["params"])]
    if not points:
        return {"exploited_by": None, "lazy_programs_tried": 0}
    tried = 0
    for label, lazy in lazy_functions():
        tried += 1
        satisfied = disagreed = 0
        for point in points:
            try:
                args = [to_t(v) for _k, v in point["args"]]
                guess = lazy(args)
                if guess is None:
                    satisfied = -1
                    break                      # this lazy program does not type here
                env = {p["name"]: a for p, a in zip(task["params"], args)}
                env[name] = to_t(guess) if not isinstance(guess, tuple) else guess
                expected = to_t(point["expected"][1])
            except (TypeError, KeyError, IndexError, ValueError):
                satisfied = -1
                break
            st = interp.St()
            try:
                if not all(interp.ev(c, env, funs, st) for c in task.get("requires", [])):
                    continue
                if not all(interp.ev(e, env, funs, st) is True for e in task.get("ensures", [])):
                    satisfied = -1
                    break                      # the spec catches it, which is the point
            except (interp.Undef, interp.Budget, RecursionError, ZeroDivisionError):
                satisfied = -1
                break
            except Exception:                  # noqa: BLE001
                satisfied = -1
                break
            satisfied += 1
            disagreed += int(env[name] != expected)
        if satisfied > 0 and disagreed > 0:
            # It satisfied the specification everywhere the precondition allowed
            # and still answered the problem wrongly at least once.
            return {"exploited_by": label, "lazy_programs_tried": tried,
                    "wrong_at_points": disagreed}
    return {"exploited_by": None, "lazy_programs_tried": tried}


def check_points(task: dict, entry: dict) -> dict:
    """Does the specification hold at the problem's OWN examples?

    Clover (arXiv 2310.17807, https://github.com/ChuyueSun/Clover) reduces
    correctness to consistency between three artifacts: the code, the docstring
    and the formal annotation, checking every pair. It reports 87% acceptance on
    correct instances with no false positives.

    This project already has two of those edges. The seven verifiers check code
    against annotation, and `check_task` above checks annotation against the
    problem by running its reference solution. The edge measured here is the one
    nobody was checking: the annotation against the problem's own assertions,
    which are ground-truth input/output pairs shipped with every problem.

    It needs no reference solution, no random draws and no language model, so it
    reaches the answers `check_task` must give up on: on 2026-09-20 that was 78
    of 149 in one arm, where the reference would not run or the drawn shapes did
    not fit. A specification false at an example the problem itself states is
    wrong, and no amount of proving can fix it.
    """
    funs = interp.funs_of(task, task["body"])
    name = task["returns"][0]["name"]
    held = failed = excluded = 0
    first = None
    for point in entry.get("points", []):
        if len(point.get("args", [])) != len(task["params"]):
            # zip() would silently truncate here and check a task against a
            # point it does not fit, which is a verdict about nothing.
            continue                       # arity differs; check_task reports that separately
        try:
            env = {p["name"]: to_t(v) for p, (_k, v) in zip(task["params"], point["args"])}
            env[name] = to_t(point["expected"][1])
        except (TypeError, KeyError, IndexError, ValueError):
            continue                       # a point this task cannot even be asked about
        if len(env) != len(task["params"]) + 1:
            continue                       # duplicate parameter names collapsed the env
        st = interp.St()
        try:
            if not all(interp.ev(c, env, funs, st) for c in task.get("requires", [])):
                # NOT nothing: the problem supplied this input, and the
                # specification's own precondition refuses it. That is the
                # over-constrained failure mode, which vACT/Spec-Harness
                # (github.com/Mondego/vACT) is the one published artifact to
                # score, and which is invisible to every check that only asks
                # whether a spec is too weak. A spec that narrows the problem
                # makes correct programs unprovable rather than wrong.
                excluded += 1
                continue
            ok = all(interp.ev(e, env, funs, st) is True for e in task.get("ensures", []))
        except (interp.Undef, interp.Budget, RecursionError, ZeroDivisionError):
            continue
        except Exception:                  # noqa: BLE001
            continue
        if ok:
            held += 1
        else:
            failed += 1
            if first is None:
                first = {"args": [v for _k, v in point["args"]], "expected": point["expected"][1]}
    out = {"points_held": held, "points_failed": failed, "points_excluded": excluded}
    if excluded and not held and not failed:
        out["over_constrained"] = True     # it refused every example it was given
    if first is not None:
        out["contradicts_example"] = first
    return out


def check_task(task: dict, entry: dict, n: int, rnd: random.Random, oracle=None, drawer=None) -> dict:
    """One task against its problem's solution: how many draws agreed, and the first that did not.

    `oracle`, when given, is called in place of the problem's reference solution, with the same
    arguments (t/spec_gate.py passes a sandboxed Python function the model itself wrote: Clover's
    doc2code edge, arXiv:2310.17807, which compares two artifacts by their outputs on inputs).
    Nothing else changes: the draws, the mutants and the statuses are the reference check's.

    `drawer`, when given, makes the inputs in place of `draw` (`draw_beyond`: the same check on inputs
    larger than the examples). Without it every draw is the one it has always been."""
    draw_one = drawer or draw
    fn = oracle if oracle is not None else reference(entry["rec"], entry["fn"])
    if fn is None:
        return {"status": "no reference"}
    kinds = [k for k, _v in entry["points"][0]["args"]]
    if len(kinds) != len(task["params"]):
        return {"status": "arity differs from the problem"}
    # 2026-10-01 (t/PREDICT-2026-10-01-spec-check-inputs.md): every draw is shaped like ONE example,
    # and until now that was always the problem's first assertion. MBPP 67 (bell_number) tests
    # n = 2, 10 and 56; every draw fell in [0, 4], and a lookup-table answer that is wrong for every
    # n from 11 to 55 read "agrees on 100 draws". EvalPlus seeds its input generation with ALL of
    # a problem's inputs and mutates a random one each time (gen/__init__.py `seed_pool`,
    # gen/mut_gen.py `random.choice(self.seed_pool)`); so does this, over the points whose kinds
    # match the first point's.
    seeds = [[v for _k, v in p["args"]] for p in entry["points"]
             if [k for k, _v in p.get("args", [])] == kinds]
    positions = string_positions(entry)
    nested = nested_string_positions(entry)
    funs = interp.funs_of(task, task["body"])
    agreed = 0
    # 2026-10-01 (t/PREDICT-2026-10-01-spec-check-coverage.md): one draw the reference could not
    # finish, or whose result t cannot represent, used to end the whole check, and the answer was
    # then never counted. EvalPlus drops such an input and goes on (gen/util/__init__.py,
    # trusted_check_exec); so does this, counting what it dropped. A check stops early after
    # MAX_REFERENCE_TIMEOUTS draws the reference did not finish, so one task costs seconds.
    skipped = {"reference did not finish": 0, "reference result has no t value": 0}
    rejected = accepted = 0            # the completeness half: wrong outputs the ensures catches
    weak_witness = None
    # 2026-10-01: the mutants above are wrong outputs NEAR the right one, so a specification that
    # never ties the result to the input ("r is one of these eleven numbers") rejects most of them.
    # nl2postcond (arXiv:2310.01831) measures completeness against the outputs of whole buggy
    # programs; the simplest buggy program answers a different question. So the solution's answers
    # to the last CROSS_PER_DRAW earlier draws, where they differ from this one's, are put to the
    # ensures as wrong answers for this input, and counted apart (`cross_completeness`).
    answered = []
    cross_rejected = cross_accepted = 0
    cross_witness = None
    # 2026-10-01: inputs the solution answers and the task's `requires` excludes. They say nothing
    # about the `ensures`, and they were not counted, so a task whose `requires` admits little more
    # than the problem's own examples read "agrees" on the few draws that landed inside. Counted
    # now and reported (`outside_requires`); t/spec_gate.py decides on it, this check does not.
    outside = 0
    # The fourth quadrant. vACT's four-way split (arXiv:2604.00280) wants inputs
    # the problem REJECTS, and this corpus ships none, which is why
    # spec_scorecard.py has printed "pre-completeness NOT MEASURED" since it was
    # written. It does not need shipped negatives: the problem's own reference
    # solution is the oracle for the problem's DOMAIN exactly as it is already
    # the oracle for its outputs. An input the reference refuses to compute is
    # an input the problem does not define, and a requires that still admits it
    # is claiming ground the problem never gave it.
    #
    # This is the admissibility half of the admissibility / soundness /
    # uniqueness triad that property-based spec validation uses (VERINA
    # arXiv:2505.23135, CLEVER arXiv:2505.13938), where the same three cheap
    # random checks found underspecification in about 10% of specifications.
    # The signal was already being computed in the loop below and thrown away.
    #
    # AUDITED BEFORE IT WAS BELIEVED, and the first version was wrong. On the
    # 27B set, 97 answers produced domain probes and **54 of them came from a
    # reference that never succeeded on any draw at all**: t represents a string
    # as a sequence of ints, the corpus's Python solution wants a `str`, and
    # every call raises TypeError. Those refusals say nothing about the
    # specification, only that the harness cannot hand this problem a value it
    # accepts. Counting them scored a confident 0.000 on exactly the answers the
    # instrument cannot evaluate at all, which is the false precision this
    # project refuses everywhere else. The probes are therefore only reported
    # when the reference is known to RUN on this problem.
    domain_probes = domain_admitted = 0
    reference_ran = 0                  # draws where the reference returned a value
    domain_witness = None
    for _ in range(n):
        if skipped["reference did not finish"] >= MAX_REFERENCE_TIMEOUTS:
            break
        examples = seeds[0] if len(seeds) == 1 else rnd.choice(seeds)
        args = [draw_one(k, rnd, ex, strings=i in nested) for i, (k, ex) in enumerate(zip(kinds, examples))]
        if any(a is None for a in args):
            return {"status": f"cannot draw {kinds}"}
        try:
            with deadline(5):
                out = fn(*python_arguments(args, positions, nested))
        except Timeout:
            skipped["reference did not finish"] += 1
            continue
        except Exception:                                       # noqa: BLE001
            # The reference refuses this input, so the problem does not define
            # it. Does the specification exclude it too? A requires that admits
            # it is incomplete on the input side. Timeouts are handled above and
            # deliberately do not reach here: not finishing is a different
            # failure from not being defined.
            try:
                env_in = bound_inputs(task["params"], args, positions)
            except TypeError:
                continue                     # no t value for the input: cannot ask
            st_in = interp.St()
            try:
                admits = all(interp.ev(c, env_in, funs, st_in) is True
                             for c in task.get("requires", []))
            except (interp.Undef, interp.Budget, RecursionError, ZeroDivisionError):
                continue                     # undefined on this input is a rejection by refusal
            except Exception:                # noqa: BLE001
                continue
            domain_probes += 1
            if admits:
                domain_admitted += 1
                if domain_witness is None:
                    domain_witness = {"args": args, "reference_raised": True}
            continue
        reference_ran += 1
        try:
            env = bound_inputs(task["params"], args, positions)
            env[task["returns"][0]["name"]] = to_t(out, task["returns"][0].get("type"))
        except TypeError:
            skipped["reference result has no t value"] += 1
            continue
        st = interp.St()
        try:
            if not all(interp.ev(c, env, funs, st) for c in task.get("requires", [])):
                outside += 1                                    # outside the precondition, says nothing
                continue
            bad = [i for i, e in enumerate(task.get("ensures", []))
                   if interp.ev(e, env, funs, st) is not True]
        except (interp.Undef, interp.Budget, RecursionError, ZeroDivisionError):
            continue
        except Exception:                                       # noqa: BLE001
            return {"status": "interpreter refused"}
        if bad:
            return {"status": "disagrees", "ensures": bad[0], "args": args,
                    "reference_said": out, "agreed_before": agreed}
        agreed += 1
        # The ensures is true of the right answer. Is it also true of a wrong
        # one? Nothing else in this project asks, and a specification that
        # cannot tell them apart is what the proven-but-wrong column is made of.
        for wrong in mutations(env[task["returns"][0]["name"]]):
            probe = dict(env)
            probe[task["returns"][0]["name"]] = wrong
            st2 = interp.St()
            try:
                holds = all(interp.ev(e, probe, funs, st2) is True
                            for e in task.get("ensures", []))
            except (interp.Undef, interp.Budget, RecursionError, ZeroDivisionError):
                continue                 # undefined on a wrong answer is a rejection by refusal
            except Exception:            # noqa: BLE001
                continue
            if holds:
                accepted += 1
                if weak_witness is None:
                    weak_witness = {"args": args, "reference_said": out, "also_accepts": wrong}
            else:
                rejected += 1
        right = env[task["returns"][0]["name"]]
        for other_args, other_out, other in answered[-CROSS_PER_DRAW:]:
            if other == right:
                continue                   # the same answer is not a wrong one here
            probe = dict(env)
            probe[task["returns"][0]["name"]] = other
            st3 = interp.St()
            try:
                holds = all(interp.ev(e, probe, funs, st3) is True for e in task.get("ensures", []))
            except (interp.Undef, interp.Budget, RecursionError, ZeroDivisionError):
                continue
            except Exception:            # noqa: BLE001
                continue
            if holds:
                cross_accepted += 1
                if cross_witness is None:
                    cross_witness = {"args": args, "reference_said": out, "also_accepts": other_out,
                                     "which_is_the_answer_for": other_args}
            else:
                cross_rejected += 1
        answered.append((args, out, right))
    status = ("agrees" if agreed else
              "reference result has no t value" if skipped["reference result has no t value"] else
              "reference did not finish" if skipped["reference did not finish"] else "no valid draws")
    result = {"status": status, "draws": agreed}
    if outside:
        result["outside_requires"] = outside
    if any(skipped.values()):
        result["skipped"] = {k: v for k, v in skipped.items() if v}
    if rejected or accepted:
        # Reported, never silently turned into a failure: a problem with more
        # than one right answer can accept a mutated output legitimately, so
        # this is evidence with a witness attached, for a human or a later gate.
        result.update(mutants_rejected=rejected, mutants_accepted=accepted,
                      completeness=round(rejected / (rejected + accepted), 3),
                      weak=accepted > 0)
        if weak_witness is not None:
            result["weak_witness"] = weak_witness
    if cross_rejected or cross_accepted:
        result.update(cross_rejected=cross_rejected, cross_accepted=cross_accepted,
                      cross_completeness=round(cross_rejected / (cross_rejected + cross_accepted), 3))
        if cross_witness is not None:
            result["cross_witness"] = cross_witness
    if domain_probes and not reference_ran:
        # The reference refused every draw, so this problem has no measurable
        # domain boundary here and the refusals are the harness's, not the
        # specification's. Said out loud rather than dropped.
        result["pre_completeness_unmeasurable"] = "reference never ran"
    if domain_probes and reference_ran:
        # Evidence with a witness, never an automatic failure, for the same
        # reason the output half is: a problem can legitimately be total, and a
        # reference that raises can be a bug in the reference rather than a
        # boundary of the problem. A human or a later gate decides.
        result.update(domain_probes=domain_probes, domain_admitted=domain_admitted,
                      reference_ran=reference_ran,
                      pre_completeness=round(1 - domain_admitted / domain_probes, 3),
                      pre_incomplete=domain_admitted > 0)
        if domain_witness is not None:
            result["domain_witness"] = domain_witness
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("tags", nargs="*")
    ap.add_argument("--pool", default="v4")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--only", choices=["clean", "all"], default="clean")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--per-task-seed", action="store_true",
                    help="each task's own generator, seeded from the task's sha256 (verdicts independent of the run)")
    ap.add_argument("--reference-plus", type=Path, default=None,
                    help="MBPP+ rows (JSONL): use EvalPlus's corrected solution where it has the problem")
    ap.add_argument("--out", type=Path, default=HERE / "SPEC-CHECK-2026-09-18.md")
    a = ap.parse_args()
    if a.n < 1:
        ap.error("--n must be positive")
    pool = se.pool(a.pool)
    if a.reference_plus:
        pool, swapped = with_reference_plus(pool, a.reference_plus)
        print(f"spec_check: MBPP+ references in place of the original for {swapped} problems", flush=True)
    # ONE generator, threaded through every task in order, so task N's arguments
    # depend on tasks 1..N-1. That is what makes `--seed 1` reproduce a report
    # exactly, and it is also why this loop cannot be parallelized for speed:
    # any concurrency changes the draw order and therefore the verdicts, and
    # this file's output is cited evidence (t/SPEC-CHECK-*.md, the README's
    # 650-answer figure, and t/out/spec-disagree.json, which the training gate
    # reads). Considered and rejected on 2026-09-20.
    #
    # The safe route, if the runtime ever matters: seed per task from the task's
    # own sha256 instead of sharing this generator, which makes tasks
    # independent and parallelizable. That is a change to the instrument, not an
    # optimization of it -- every existing report would have to be regenerated
    # and the change registered before anyone compares old numbers with new.
    rnd = random.Random(a.seed)
    # --per-task-seed (2026-10-03, the remedy named above): each task draws from its own generator, seeded from the
    # run's seed and the task's sha256, so its verdict no longer depends on which tasks were checked before it
    # (between two runs of the same answers six verdicts flipped). A different instrument: its reports are not
    # compared with the shared-generator ones.
    root = HERE / "out" / "spec-experiment"
    tags = a.tags or sorted(p.name for p in root.glob("*") if (p / "kernels.md").exists())
    rows, tally = [], {"agrees": 0, "disagrees": 0, "other": 0}
    for tag in tags:
        d = root / tag
        cols, cells = se.parse_kernel_table(d / "kernels.md")
        try:
            extracted = json.loads((d / "extract.json").read_text())
        except (OSError, ValueError):
            extracted = {}
        try:
            tests = {v.get("name"): v.get("overall") for v in json.loads((d / "tests.json").read_text()).values()}
        except (OSError, ValueError):
            tests = {}
        for name, row in cells.items():
            clean = (tests.get(name) == "pass"
                     and all(row.get(k, "").startswith("verified / refuted") for k in KERNELS))
            if a.only == "clean" and not clean:
                continue
            path = d / "tasks" / f"{name}.json"
            if not path.exists():
                continue
            task = harness.load(path)
            try:
                tid = problem_id(name, extracted)
                entry = pool.get(tid)
                trnd = random.Random(f"{a.seed}:{task_sha256(task)}") if a.per_task_seed else rnd
                r = (check_task(task, entry, a.n, trnd) if entry is not None
                     else {"status": "problem not in pool"})
                if r.get("status") == "agrees":
                    # 2026-10-05: the same check on inputs larger than the examples, from the task's own generator
                    # (no draw above moves); t/score_levels.py --larger reads it (larger_reason). A failure to
                    # measure is recorded and never ends the run or changes the verdict above.
                    try:
                        r["larger"] = larger_inputs(task, entry, f"{a.seed}:{task_sha256(task)}")
                    except Exception as e:                      # noqa: BLE001
                        r["larger"] = {"status": f"not measured ({type(e).__name__})"}
                if entry is not None:
                    # Clover's third consistency edge (arXiv 2310.17807): the
                    # annotation against the problem's own assertions. Needs no
                    # reference solution, so it reaches the tasks check_task
                    # gives up on, and it never flagged a clean answer in the
                    # three arms measured on 2026-09-20.
                    r.update(check_points(task, entry))
            except ValueError as e:
                tid = None
                r = {"status": "problem mapping refused", "reason": str(e)}
            try:
                sha = task_sha256(task)
            except Exception as e:                              # noqa: BLE001
                # An answer written before a word became a keyword of the surface syntax (`card`,
                # 2026-10-01, in a train-side set) no longer prints, so it has no identity to bind
                # a verdict to. It is not a valid program today: recorded, never admitted, and the
                # other answers are still checked (the run used to end here with a traceback).
                r, sha = {"status": "task no longer prints", "reason": f"{type(e).__name__}: {e}"}, None
            r.update(task_id=tid, task_sha256=sha, pool=a.pool,
                     seed=a.seed, attempts=a.n)
            key = "agrees" if r["status"] == "agrees" else ("disagrees" if r["status"] == "disagrees" else "other")
            tally[key] += 1
            rows.append((tag, name, r))
            if key == "disagrees":
                print(f"DISAGREES {tag}/{name}: ensures[{r['ensures']}] is false at args={r['args']}, "
                      f"the problem's solution answers {r['reference_said']!r}")
    print(f"\n{sum(tally.values())} tasks checked against their problem's own solution, {a.n} draws each: "
          f"{tally['agrees']} agree, {tally['disagrees']} disagree, {tally['other']} could not be checked")
    # A tag that produced no rows was NOT checked, whatever the command asked for,
    # and it must not enter the cumulative "tags" list below. This is the same
    # failure CORRECTIONS.md records for score_heldout.py, in a second place: on
    # 2026-09-20 two runs named 42 tags, five of them arms graded on the v3
    # held-out split, and asked for --pool v5. Every answer in those five was
    # skipped for being outside the pool, both runs reported the same counts as
    # the 37-tag run before them, and all five were still recorded as checked --
    # so the README's "3 against 2 after the specification check" had no evidence
    # in the tree for a day. Silence about a tag now says nothing about it.
    empty = [t for t in tags if t not in {tag for tag, _n, _r in rows}]
    if empty:
        # INVENTED, and the search that says so is recorded rather than implied.
        # No paper was found covering this case in program verification. The
        # nearest prior art is in supply-chain provenance, where SLSA draws the
        # same line between a manifest, which lists what claims to be present, and
        # a signed attestation, which asserts what a pipeline actually consumed --
        # and notes that confirming each input met its requirements "is the piece
        # that doesn't exist yet, and this is the step most pipelines skip"
        # (slsa.dev/spec/v1.0/verifying-artifacts). The cumulative "tags" list here
        # is the manifest and the "results" rows are the attestation, and they had
        # drifted apart by 30 tags. The in-repo precedent is CORRECTIONS.md's first
        # entry, the same mistake in score_heldout.py.
        #
        # Say only what is established. Reaching the checker needs a kernels.md,
        # a tasks/<name>.json, and -- under --only clean -- a row whose tests pass
        # AND whose seven kernels all read verified / refuted. A task id outside
        # the pool is NOT one of the reasons: that case still writes a row, with
        # status "problem not in pool". Naming a cause this loop cannot tell apart
        # would be a false verdict, which is the one thing this file must not emit.
        print(f"\nNOT CHECKED, no answer of theirs reached the checker under --only {a.only}: "
              f"{', '.join(empty)}")
        print("  Left out of the checked list, because a tag nothing was checked for must not "
              "read as a tag that passed. Look for a missing kernels.md or tasks/ directory, "
              "no row that is both test-passing and clean in all seven, or a pool the arm was "
              "not graded against.")
    lines = ["# Specifications against the problems' own solutions, 2026-09-18", "",
             f"`python3 t/spec_check.py --pool {a.pool} --n {a.n} --only {a.only}`, seed {a.seed}. Each task's",
             "`ensures` is evaluated with the problem's reference solution supplying the result, on random",
             "arguments of the shapes the problem's own assertions use. A disagreement is a specification the",
             "seven proof systems proved and the twin rule accepted that does not say what the problem asked.", "",
             f"- checked: {sum(tally.values())}", f"- agree on every draw: {tally['agrees']}",
             f"- disagree: {tally['disagrees']}", f"- could not be checked: {tally['other']}", ""]
    for tag, name, r in rows:
        if r["status"] == "disagrees":
            lines.append(f"- `{tag}/{name}`: ensures[{r['ensures']}] false at `{r['args']}`, "
                         f"the problem's solution answers `{r['reference_said']!r}`")
    a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # machine-readable, so loop_dataset.py can keep these out of a pool and preflight.py can count them
    # the program itself, not only its name: two tags can answer the same problem, and only the answer whose
    # specification disagrees must be kept out of a pool (2026-09-18)
    disagree, texts = [], {}
    for tag, name, r in rows:
        if r["status"] != "disagrees":
            continue
        disagree.append(f"{tag}/{name}")
        try:
            texts[f"{tag}/{name}"] = surface.print_task(
                harness.load(root / tag / "tasks" / f"{name}.json")).strip()
        except (OSError, ValueError):
            pass
    # Merge rather than overwrite, and record WHICH tags were checked. Without that list a reader cannot tell
    # "this answer set was checked and nothing disagreed" from "nobody ever checked this answer set", and
    # score_heldout.py was silently reading the second as the first: every tag absent from the disagreement
    # list scored full marks in its "clean, spec checked" column, checked or not (2026-09-19).
    out_path = HERE / "out" / "spec-disagree.json"
    try:
        prev = json.loads(out_path.read_text())
    except (OSError, ValueError):
        prev = {}
    checked_tags = sorted(set(prev.get("tags", [])) | ({tag for tag, _n, _r in rows} & set(tags)))
    results = {f"{tag}/{name}": result for tag, name, result in rows}
    keep = [x for x in prev.get("disagree", []) if x not in results]
    keep_texts = {k: v for k, v in (prev.get("programs") or {}).items()
                  if k not in results}
    updated = {**prev, "checked": int(prev.get("checked", 0)) + sum(tally.values()),
               "tags": checked_tags, "disagree": sorted(keep + disagree),
               "programs": {**keep_texts, **texts},
               "results": {**prev.get("results", {}), **results},
               "runs": [*prev.get("runs", []),
                        {"tags": tags, "pool": a.pool, "seed": a.seed, "attempts": a.n,
                         "only": a.only, "counts": tally, "checked_nothing": empty,
                         "when": datetime.datetime.now(datetime.timezone.utc).isoformat()}]}
    temp = out_path.with_suffix(".tmp")
    temp.write_text(json.dumps(updated, indent=1) + "\n", encoding="utf-8")
    temp.replace(out_path)
    # relative_to raises when --out is outside the repository or given as a
    # relative path from elsewhere, which failed a run on 2026-09-19 AFTER the
    # report had been written: the work was done and the command still exited
    # nonzero. Report the path we can, never crash on the way out.
    try:
        shown = a.out.resolve().relative_to(HERE.parent)
    except ValueError:
        shown = a.out.resolve()
    print(f"written to {shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
