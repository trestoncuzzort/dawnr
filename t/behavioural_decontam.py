#!/usr/bin/env python3
"""t/behavioural_decontam.py -- behavioural decontamination of the train split (2026-09-25).

A TRAIN problem is a behavioural duplicate of a HELD-OUT problem when their
reference solutions agree on both problems' own test inputs plus 100 inputs
drawn with t/spec_check.py's draw() from the shown kinds (50 shaped like each
problem's own first example), for every held-out problem of the same signature
kinds. Such a train problem teaches the exact program the held-out problem
asks for, whatever its English says, so it leaves every future corpus; the
existing text and AST detectors (t/DECONTAMINATION-2026-09-21.md) cannot see it
when the two solutions are written differently.

Prior art, each fetched and read on 2026-09-25 (receipt a35af518059a):
- Riddell et al., https://ar5iv.labs.arxiv.org/html/2403.04811: contamination
  scored by substring Levenshtein plus Dolos AST k-gram similarity; models score
  far higher on the most-similar subset. Static, sized for a terabyte corpus.
  Our pool is ~3,000 problems with runnable references, so we execute instead.
- Soft Contamination, https://arxiv.org/html/2602.12413v1: semantic duplicates
  raise seen and unseen items by about 20%, close neighbours have no effect.
  The line between duplicate and neighbour is what this file draws: a pair that
  differs on one drawn input is a MINIMAL PAIR and is kept, listed separately.
- Yang et al., https://arxiv.org/html/2311.04850v2 (lm-sys/llm-decontaminator):
  n-gram decontamination misses rephrased samples; their detector is an
  embedding top-k plus an LLM judge. Rejected as the mechanism: the references
  are the oracle here, no judge is needed.
- HyClone, https://arxiv.org/html/2508.01357v1: type-4 clones confirmed by
  cross-execution on shared inputs ("identical outputs on the same inputs
  approximates functional equivalence"); recall rises, precision falls, and
  generated INPUTS are reliable where generated outputs are not. Adopted, with
  spec_check.draw() as the input generator. Their filtering step DISCARDS an
  input a program cannot answer ("retaining only those producing valid
  outputs") instead of scoring it, which schema 2 of this file does too: an
  own input a reference did not answer leaves the own-input count
  (review of 2026-09-25, receipt 02d3d871b0d1).
- pytest-timeout, https://raw.githubusercontent.com/pytest-dev/pytest-timeout/main/README.rst:
  a signal-raised timeout "may interfere with the code under test"; when the
  code swallows it, "often the only sure way to interrupt a hanging test is by
  terminating the entire process" with os._exit(), after the debugging output
  on stderr. Adopted for a reference with a bare except (receipt ffe9f5d99d7e).
- CPython issue 66587 (bpo-22393), https://github.com/python/cpython/issues/66587:
  multiprocessing.Pool waits forever for a worker that died mid-task; still
  open. The parent here takes results with a timeout and names the held-out
  ids it never got (receipt 990302ddaaff).

Schema 2 (the review of 2026-09-25): the first version required every own
input to agree, which made one 1 s timeout on an own input (find_lucas on
an AtCoder problem's N=86) a bar no evidence could clear, and a duplicate
verdict impossible for eight pairs that agreed everywhere they were both
answered. Now an own input a reference did not answer (in time, within its
recursion or memory limit, or because the other problem's argument shape
cannot hold it) leaves the count; a duplicate needs every ANSWERED own input
agreed, at least one of them the held-out problem's own, and the draws as
before. A pair the rule still cannot decide is UNDECIDED, listed with both
statements, and `write` refuses to produce the policy until each such pair
has been read by hand (--read-same / --read-different), so no pair is left
with neither a verdict nor a reading.

What the rule cannot see, said here rather than hidden: draws follow the
example's shape (a non-negative example draws non-negative, a sorted example
stays sorted), so two problems that differ only outside that shape are
duplicates under this rule. Outputs are compared as t reads them: a string is
its code points, a one-character string is that character, a bool is not an int.
A reference that will not run, or raises on every input it is given, is
reported by name and never treated as agreeing; an input where exactly one
reference raises is a difference, not agreement.

Run on the lab CPU (about one CPU-hour for pool v5, read-only pools):
    python3 t/behavioural_decontam.py --pool v5 --split t/out/loop/split-v5.json \\
        --progress <scratch>/v5.jsonl --jobs 4
    python3 t/behavioural_decontam.py --pool v6 --split t/out/loop/split-v6.json ...
    python3 t/behavioural_decontam.py write --from <scratch>/v5.jsonl <scratch>/v6.jsonl \\
        --out t/decontamination-behavioural-2026-09-25.json --report t/DECONTAMINATION-BEHAVIOURAL-2026-09-25.md \\
        --read-same 204714:502='remainder of two integers' --read-different TRAIN:EVAL='why' ...
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import io
import json
import os
import random
import re
import signal
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import spec_check                                               # noqa: E402
import spec_experiment as se                                    # noqa: E402

SCHEMA = 2                      # 2 (2026-09-25 review): own_unanswered and own_eval_agreed in every pair record
SEED = "behavioural-decontam-2026-09-25"
DRAWS_PER_PROBLEM = 50          # 100 per pair: 50 shaped like each problem's own first example
MIN_DRAWS_AGREED = 50           # a duplicate needs half the pair's draws answered alike: equal values, or
                                # both references refusing the input with the same exception ...
MIN_DRAWS_VALUED = 10           # ... and at least this many answered with equal VALUES, so two references
                                # that only refuse alike are never called the same function.
# The refusal clause exists because the first run missed a byte-identical
# reference: train 595 and held-out 699 raise the same error on 52 of their 100
# draws (their own domain), agree on the other 46, and the bar of 50 agreeing
# values called that insufficient. Refusing the same input the same way is
# behaviour too.
TIMEOUT_S = 1.0                 # CPU seconds per reference call (ITIMER_VIRTUAL, so a niced run on a busy
                                # machine gives the same verdicts); a wall-clock backstop of 10x guards sleeps
BUDGET_S = 60.0                 # CPU seconds per reference over the whole run, then "did not finish"
MAX_TIMEOUTS = 20               # timed-out calls per reference over the whole run, then "did not finish"
PAIR_TIMEOUTS = 2               # timed-out calls per reference within one pair, then the pair's rest is skipped
# The first version used spec_check's 5 s wall-clock alarm per call and killed a
# reference after three timeouts anywhere. On the lab that stalled: a train
# problem with a 10^9-sized example draws 10^9-sized inputs, an MBPP reference
# loops to n on them, three of those killed the HELD-OUT reference for every
# later pair, and a reference at 0.5 s per call (under the alarm) cost 25 s per
# pair times 548 pairs. A timeout is therefore an input the reference does not
# answer (undefined, never a difference), bounded per pair, per reference and
# by CPU time, and a reference that exhausts its budget is reported by name.
INACTIVITY_S = 900.0            # the parent stops and names the unfinished held-out ids when no held-out id
                                # finishes for this long: a worker that died mid-task is never waited on forever
                                # (CPython issue 66587, open: multiprocessing.Pool would wait forever)
HUNG_EXIT = 70                  # a worker's exit status when a reference swallowed its timeout (pytest-timeout's os._exit)
HUNG_WHY = ("reference swallowed the CPU timeout (a bare except) and ran past the wall-clock backstop; "
            "the worker exited and this reference is refused by name")
RECURSION_LIMIT = sys.getrecursionlimit()   # set before every reference call: a corpus solution that raises the
                                # limit at load time must not change what a later reference in the same
                                # worker can answer (find_lucas(-10) timed out in one worker and raised
                                # RecursionError in another before this was pinned)
# Names the corpus solutions use without importing them, because the site that
# ran them (LeetCode, Codewars) had them in scope; spec_check.reference already
# supplies the modules and the typing names. A NameError on one of these was
# the reason several v5 references "raised on every input", which says nothing
# about the function and left the pair unchecked.
REFERENCE_PRELUDE = ("from math import gcd, sqrt, ceil, floor, log, log2, factorial, comb, perm, isqrt, inf, prod\n"
                     "from functools import lru_cache, cache, reduce\n"
                     "from itertools import permutations, combinations, accumulate, product, chain, groupby\n"
                     "from collections import Counter, defaultdict, deque, OrderedDict\n"
                     "from heapq import heappush, heappop, heapify\n"
                     "from bisect import bisect_left, bisect_right, insort\n"
                     "import sys\n")
UNANSWERED = frozenset({"timeout", "skipped", "exhausted", "unrenderable"})   # says nothing about the function
SOURCES = (
    "https://ar5iv.labs.arxiv.org/html/2403.04811",
    "https://arxiv.org/html/2602.12413v1",
    "https://arxiv.org/html/2311.04850v2",
    "https://arxiv.org/html/2508.01357v1",
)
A2_POLICY = HERE / "decontamination-2026-09-21.json"
RULE_TEXT = ("a train problem is a behavioural duplicate of a held-out problem of the same signature kinds "
             "when both references run and return equal values (as t reads them) on every one of both problems' "
             "own assertion inputs that both answered, at least one of them the held-out problem's own, and on "
             "every drawn input that both answered, with at least MIN_DRAWS_AGREED of the pair's 100 draws "
             "(50 per problem, spec_check.draw shaped like the problem's first example) answered alike (equal "
             "values, or both references raising the same exception) and at least MIN_DRAWS_VALUED of them equal "
             "values; an input where exactly one reference raises is a difference; an input a reference did not "
             "answer (not in time, not within its recursion or memory limit, or a t value the other problem's "
             "argument shape cannot hold) says nothing: it leaves the count and is never a difference; a pair "
             "that never differed but falls short of this bar is undecided and must be read by hand before the "
             "policy is written; a reference that does not run is reported by name and never counted as agreeing")


class Unrenderable(Exception):
    """A t value this problem's own example shape cannot be written in."""


# ---------------------------------------------------------------- values --

def canon(value):
    """A reference result as t reads it, tagged so that True != 1 and 'a' == 97.

    Mirrors mbpp_dfy._literal: a string is its code points, a ONE-character
    string is that character (an int), a list of one-character strings is a
    flat seq of ints, a list with a longer string is a seq of seqs. A float or
    a None is not a t value; it is kept as itself so that 2.0 differs from 2
    and a pair that returns them is not called equal."""
    if isinstance(value, bool):
        return ("b", value)
    if isinstance(value, int):
        return ("i", value)
    if isinstance(value, float):
        # MBPP 76 returns 20.0 where its twin 347 returns 20, and the problem's
        # own assertion `== 20` accepts both: an integral float IS that int to
        # the problem and to t, which has no floats. 2.5 stays a value of its
        # own, unequal to anything t can write.
        if value == value and value not in (float("inf"), float("-inf")) and value.is_integer():
            return ("i", int(value))
        return ("f", value)
    if value is None:
        return ("n",)
    if isinstance(value, str):
        points = [ord(c) for c in value]
        if len(points) == 1:
            return ("i", points[0])
        return ("q", tuple(("i", c) for c in points))
    if isinstance(value, (list, tuple)):
        if value and all(isinstance(x, str) for x in value) and any(len(x) != 1 for x in value):
            return ("q", tuple(("q", tuple(("i", ord(c)) for c in x)) for x in value))
        return ("q", tuple(canon(x) for x in value))
    return ("o", repr(value))


def shape_of(literal):
    """The native shape of one assertion argument: str, list/tuple (with its element shape), or scalar."""
    if isinstance(literal, str):
        return ("str",)
    if isinstance(literal, (list, tuple)):
        inner = shape_of(literal[0]) if literal else None
        return ("list" if isinstance(literal, list) else "tuple", inner)
    return ("scalar",)


def _clamp(point) -> int:
    if isinstance(point, bool) or not isinstance(point, int):
        raise Unrenderable(f"not a code point: {point!r}")
    return min(max(point, 0), 0x10FFFF)


def render(value, shape):
    """A t value (int, bool, list of ints, list of lists) in the native shape a reference expects."""
    if shape is None or shape == ("scalar",):
        if isinstance(value, (list, tuple)):
            return [render(x, None) for x in value]
        return value
    if shape == ("str",):
        if isinstance(value, bool):
            raise Unrenderable("a bool is not a character")
        if isinstance(value, int):
            return chr(_clamp(value))
        if isinstance(value, (list, tuple)):
            return "".join(chr(_clamp(c)) for c in value)
        raise Unrenderable(f"no string for {type(value).__name__}")
    kind, inner = shape
    if not isinstance(value, (list, tuple)):
        raise Unrenderable(f"a {kind} shape for a scalar")
    items = [render(x, inner) for x in value]
    return items if kind == "list" else tuple(items)


_JSON_WORDS = (("true", "True"), ("false", "False"), ("null", "None"))


def literal_args(entry: dict) -> list | None:
    """The first assertion's call arguments as Python literals (a str stays a str), or None.

    The pool's points already turned every string into its code points, which
    is right for t and wrong for the Python reference, whose own site handed
    it a str; the assertion text still says which it was. APPS assertions are
    json.dumps'ed (true/false/null), so those words are read as Python's."""
    tests = entry["rec"].get("test_list") or []
    if not tests:
        return None
    source = str(tests[0]).strip()
    attempts = [source]
    fixed = source
    for word, python in _JSON_WORDS:
        fixed = re.sub(rf"\b{word}\b", python, fixed)
    attempts.append(fixed)
    best = None
    for attempt in attempts:
        try:
            tree = ast.parse(attempt)
        except SyntaxError:
            continue
        if not tree.body or not isinstance(tree.body[0], ast.Assert):
            return None
        test = tree.body[0].test
        if isinstance(test, ast.Compare):
            test = test.left
        elif isinstance(test, ast.UnaryOp):
            test = test.operand
        if not isinstance(test, ast.Call):
            return None
        out = []
        for node in test.args:
            try:
                out.append(ast.literal_eval(node))
            except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
                out.append(None)
        if all(literal is not None for literal in out):
            return out
        if best is None:
            best = out          # the JSON reading may still fill a position the Python one could not
    return best


def arg_shapes(entry: dict) -> list:
    """One shape per argument position, from the assertion text; None where it could not be read."""
    arity = len(entry["points"][0]["args"])
    literals = literal_args(entry)
    if literals is None or len(literals) != arity:
        return [None] * arity
    return [None if lit is None else shape_of(lit) for lit in literals]


def signature(entry: dict) -> tuple:
    point = entry["points"][0]
    return (tuple(k for k, _v in point["args"]), point["expected"][0])


def own_inputs(entry: dict) -> list[list]:
    return [[v for _k, v in point["args"]] for point in entry["points"]
            if len(point.get("args", [])) == len(entry["points"][0]["args"])]


def draws_for(tid: int, entry: dict, n: int = DRAWS_PER_PROBLEM, seed: str = SEED) -> list[list] | None:
    """n inputs drawn like spec_check.check_task draws them, seeded by the problem alone.

    Seeded per problem, not per pair, so a problem's draws are the same against
    every partner and each reference runs on them once (cached)."""
    kinds = [k for k, _v in entry["points"][0]["args"]]
    examples = [v for _k, v in entry["points"][0]["args"]]
    rnd = random.Random(f"{seed}:{tid}")
    out = []
    for _ in range(n):
        args = [spec_check.draw(k, rnd, ex) for k, ex in zip(kinds, examples)]
        if any(a is None for a in args):
            return None
        out.append(args)
    return out


def problem_name(tid: int, entry: dict) -> str:
    """The task name the corpus would give this problem (spec_experiment.extract_tag's rule)."""
    tid = int(tid)
    prefix = (f"apps_{tid - se.APPS_BASE}" if tid >= se.APPS_BASE else
              f"he_{tid - se.HUMANEVAL_BASE}" if tid >= se.HUMANEVAL_BASE else f"mbpp_{tid}")
    return f"{prefix}__{entry['fn']}"


# ------------------------------------------------------------- execution --

@contextlib.contextmanager
def _quiet():
    """No stdout, no stderr, an empty stdin: a reference that prints or reads must not touch the run."""
    saved = sys.stdin
    sink = io.StringIO()
    sys.stdin = io.StringIO("")
    try:
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            yield
    finally:
        sys.stdin = saved


class ReferenceTimeout(BaseException):
    """The CPU timer fired inside a reference.

    A BaseException, not an Exception, so a reference's own `except Exception`
    (common in corpus solutions) cannot swallow it, the way KeyboardInterrupt
    escapes such a clause. The first version raised spec_check.Timeout, an
    Exception, and a reference that caught it ran on past both timers."""


# What the timers know about the call in flight, for the one case nothing in
# this process can stop: a reference with a bare `except:` swallows the
# ReferenceTimeout too. pytest-timeout's README (fetched 2026-09-25,
# https://raw.githubusercontent.com/pytest-dev/pytest-timeout/main/README.rst)
# says of that case "often the only sure way to interrupt a hanging test is by
# terminating the entire process ... a hard termination (os._exit()) ... but
# the plugin will ensure you will have the debugging output on stderr". So the
# wall-clock backstop, finding the CPU timeout already raised and swallowed,
# names the held-out id and the reference on stderr and in the sidecar next to
# the progress file, then exits the worker; run_pool's inactivity limit reports
# the lost held-out id, and the next run refuses that reference by name.
_TIMER: dict = {"fired": False, "tid": None, "name": None, "eval_id": None, "hung_path": None}


def _cpu_timeout(_sig, _frame):
    _TIMER["fired"] = True
    raise ReferenceTimeout()


def _wall_backstop(_sig, _frame):
    if _TIMER["fired"]:
        _report_hung()
        os._exit(HUNG_EXIT)
    _TIMER["fired"] = True
    raise ReferenceTimeout()


def _report_hung() -> None:
    line = json.dumps({"kind": "hung", "eval_id": _TIMER.get("eval_id"), "tid": _TIMER.get("tid"),
                       "name": _TIMER.get("name"), "why": HUNG_WHY})
    try:
        sys.__stderr__.write(f"behavioural_decontam: worker exiting: {line}\n")
        sys.__stderr__.flush()
    except Exception:                                           # noqa: BLE001
        pass
    if _TIMER.get("hung_path"):
        try:
            with open(_TIMER["hung_path"], "a", encoding="utf-8") as sidecar:
                sidecar.write(line + "\n")
        except OSError:
            pass


def hung_path_for(progress: Path) -> Path:
    return Path(str(progress) + ".hung")


def read_hung(path: Path) -> dict[int, str]:
    """The references an earlier run's workers died in, by id, from the sidecar next to the progress file."""
    refuse: dict[int, str] = {}
    if Path(path).exists():
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                if record.get("tid") is not None:
                    refuse[int(record["tid"])] = record.get("why") or HUNG_WHY
    return refuse


def _disarm() -> None:
    """Both timers off and both handlers ignored, so a tick that already tripped is dropped, not raised later."""
    signal.setitimer(signal.ITIMER_VIRTUAL, 0)
    signal.setitimer(signal.ITIMER_REAL, 0)
    signal.signal(signal.SIGVTALRM, signal.SIG_IGN)
    signal.signal(signal.SIGALRM, signal.SIG_IGN)


def run_reference(fn, native: list, timeout_s: float = TIMEOUT_S) -> tuple:
    """("ok", canon) | ("raised", name) | ("timeout",) | ("exhausted", name).

    timeout_s is CPU time; a wall-clock backstop fires at 10x that and then
    every timeout_s, so a reference that sleeps, or one that swallowed the CPU
    timeout, is still stopped. A reference that swallowed the timeout and then
    returned is scored as a timeout: it did not answer within its budget.

    The first version cleared the timers in a `finally` and let a Timeout that
    fired inside that `finally` escape: on the lab a worker died of it after 96
    held-out ids and multiprocessing tore the run down. A signal can arrive at
    any bytecode, so the timeout is caught around the clearing too, the handlers
    are set to ignore before returning (a signal that tripped during clearing is
    then dropped by the interpreter instead of raised at a random later line),
    and the streams a reference may have been in the middle of redirecting are
    put back.

    A RecursionError or a MemoryError is the reference running out of its
    resources on this input, not an answer about the function; it is scored
    like a timeout (HyClone, https://arxiv.org/html/2508.01357v1, drops such
    inputs rather than scoring them). The recursion limit is pinned per call
    so that a corpus solution raising it at load time does not change what a
    later reference in the same worker can answer."""
    streams = (sys.stdin, sys.stdout, sys.stderr)
    limit = sys.getrecursionlimit()
    _TIMER["fired"] = False
    result = ("raised", "no result")
    try:
        try:
            sys.setrecursionlimit(RECURSION_LIMIT)
            signal.signal(signal.SIGVTALRM, _cpu_timeout)
            signal.signal(signal.SIGALRM, _wall_backstop)
            signal.setitimer(signal.ITIMER_VIRTUAL, timeout_s)
            signal.setitimer(signal.ITIMER_REAL, 10 * timeout_s, timeout_s)
            with _quiet():
                out = fn(*native)
            result = ("timeout",) if _TIMER["fired"] else ("ok", canon(out))
        finally:
            _disarm()
    except ReferenceTimeout:
        result = ("timeout",)
    except (RecursionError, MemoryError) as error:
        result = ("exhausted", type(error).__name__)
    except KeyboardInterrupt:
        raise
    except BaseException as error:                              # noqa: BLE001  (SystemExit included)
        result = ("raised", type(error).__name__)
    _disarm()
    sys.setrecursionlimit(limit)
    sys.stdin, sys.stdout, sys.stderr = streams
    return result


def _with_prelude(rec: dict) -> dict:
    """The record with REFERENCE_PRELUDE before its code (not when the code has a `from __future__` line, which must come first)."""
    code = rec.get("code") or ""
    if not code.strip() or "from __future__" in code:
        return rec
    return {**rec, "code": REFERENCE_PRELUDE + code}


class Runner:
    """Calls each problem's reference on t values, in its own native shape, with a cache per input."""

    def __init__(self, pool: dict, timeout_s: float = TIMEOUT_S, max_timeouts: int = MAX_TIMEOUTS,
                 budget_s: float = BUDGET_S, refuse: dict | None = None):
        self.pool = pool
        self.timeout_s = timeout_s
        self.max_timeouts = max_timeouts
        self.budget_s = budget_s
        self.refuse = {int(k): v for k, v in (refuse or {}).items()}   # from the .hung sidecar: never loaded
        self.refs: dict[int, object] = {}
        self.shapes: dict[int, list] = {}
        self.cache: dict[tuple, tuple] = {}
        self.timeouts: dict[int, int] = {}
        self.spent: dict[int, float] = {}      # CPU seconds per reference
        self.ran: dict[int, int] = {}          # calls that returned a value
        self.exhausted_calls: dict[int, int] = {}   # calls that ran out of recursion depth or memory
        self.calls: dict[int, int] = {}

    def reference(self, tid: int):
        if tid not in self.refs:
            entry = self.pool[tid]
            if tid in self.refuse:
                self.refs[tid] = None
            else:
                with _quiet():              # a reference that prints at load time stays out of the log
                    self.refs[tid] = spec_check.reference(_with_prelude(entry["rec"]), entry["fn"])
            self.shapes[tid] = arg_shapes(entry)
        return self.refs[tid]

    def exhausted(self, tid: int) -> str | None:
        if self.timeouts.get(tid, 0) >= self.max_timeouts:
            return f"reference did not finish: {self.max_timeouts} calls over {self.timeout_s}s CPU each"
        if self.spent.get(tid, 0.0) >= self.budget_s:
            return f"reference did not finish: over {self.budget_s:.0f}s CPU in all"
        return None

    def cached(self, tid: int, args: list) -> tuple | None:
        """An answer this reference already gave on this input, or None."""
        return self.cache.get((tid, canon(list(args))))

    def call(self, tid: int, args: list) -> tuple:
        key = (tid, canon(list(args)))
        hit = self.cache.get(key)
        if hit is not None:
            return hit
        fn = self.reference(tid)
        if fn is None:
            result = ("no reference",)
        elif self.exhausted(tid):
            return ("timeout",)             # not cached: the input itself was never tried
        else:
            try:
                native = [render(a, s) for a, s in zip(args, self.shapes[tid])]
            except Unrenderable as error:
                result = ("unrenderable", str(error))
            else:
                self.calls[tid] = self.calls.get(tid, 0) + 1
                _TIMER["tid"], _TIMER["name"] = int(tid), problem_name(tid, self.pool[tid])
                started = time.process_time()
                result = run_reference(fn, native, self.timeout_s)
                self.spent[tid] = self.spent.get(tid, 0.0) + time.process_time() - started
                if result[0] == "timeout":
                    self.timeouts[tid] = self.timeouts.get(tid, 0) + 1
                elif result[0] == "ok":
                    self.ran[tid] = self.ran.get(tid, 0) + 1
                elif result[0] == "exhausted":
                    self.exhausted_calls[tid] = self.exhausted_calls.get(tid, 0) + 1
        self.cache[key] = result
        return result

    def why_not_run(self, tid: int) -> str | None:
        """Why this reference produced no value at all, or None when it ran at least once."""
        if tid in self.refuse:
            return self.refuse[tid]
        if self.reference(tid) is None:
            return "reference does not load (no code, an import or syntax error, or the function is missing)"
        if self.ran.get(tid, 0):
            return None
        if self.timeouts.get(tid, 0):
            return f"reference did not finish within {self.timeout_s}s CPU on any input"
        if self.calls.get(tid, 0) and self.exhausted_calls.get(tid, 0) == self.calls[tid]:
            return "reference ran out of recursion depth or memory on every input it was given"
        if self.calls.get(tid, 0):
            return "reference raised on every input it was given"
        return "reference was never called"


# ------------------------------------------------------------------ pairs --

def pair_inputs(train_entry: dict, eval_entry: dict, train_draws: list, eval_draws: list) -> list[tuple[str, list, int]]:
    """Both problems' own inputs, then the held-out problem's draws, then the train problem's, as (tag, args, weight).

    An own input appears once. A draw that comes up more than once is called
    once (the reference is cached) but WEIGHS as many times as it was drawn:
    the rule counts 100 draws, and on a small domain (an example of 2 draws
    from 0..4) those 100 draws are a handful of distinct values, which is the
    domain exhausted, not evidence missing. The first version counted distinct
    draws and called divisorGame (n even) against is_Sum_Of_Powers_Of_Two (n
    even) insufficient on 16 distinct draws that all agreed."""
    out: list[tuple[str, list, int]] = []
    seen_own: set = set()
    for tag, inputs in (("own_train", own_inputs(train_entry)), ("own_eval", own_inputs(eval_entry))):
        for args in inputs:
            key = canon(list(args))
            if key in seen_own:
                continue
            seen_own.add(key)
            out.append((tag, args, 1))
    # The held-out problem's draws come first: they are its shape, the evidence
    # that matters, and they are cached across every pair of that held-out id.
    # The tag says whose shape a draw has, so that a reference which stops
    # answering one shape in this pair (PAIR_TIMEOUTS) is still asked the other.
    weights: dict = {}
    order: list = []
    for tag, drawn in (("draw_eval", eval_draws), ("draw_train", train_draws)):
        for args in drawn:
            key = canon(list(args))
            if key not in weights:
                weights[key] = 0
                order.append((key, args, tag))
            weights[key] += 1
    out.extend((tag, args, weights[key]) for key, args, tag in order)
    return out


WITNESS_ITEMS = 24              # a witness is for a reader; a 10^5-element draw or a 10^5-digit int is not
WITNESS_DIGITS = 60


def _brief(value):
    """A JSON-writable value cut to a size a person can read (and json can load back)."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value if -10 ** WITNESS_DIGITS < value < 10 ** WITNESS_DIGITS else f"<int of {len(str(abs(value)))} digits>"
    if isinstance(value, float):
        return value
    if isinstance(value, str):
        return value if len(value) <= 4 * WITNESS_ITEMS else value[:4 * WITNESS_ITEMS] + f"<... {len(value)} chars>"
    if isinstance(value, (list, tuple)):
        items = [_brief(x) for x in value[:WITNESS_ITEMS]]
        if len(value) > WITNESS_ITEMS:
            items.append(f"<... {len(value)} items>")
        return items
    return repr(value)[:4 * WITNESS_ITEMS]


def _show(value):
    """A canon value back into JSON-writable form for a witness."""
    tag = value[0]
    if tag in ("b", "i", "f"):
        return _brief(value[1])
    if tag == "n":
        return None
    if tag == "q":
        return _brief([_show(x) for x in value[1]])
    return _brief(value[1])


def compare_pair(runner: Runner, train_id: int, eval_id: int, inputs: list[tuple[str, list, int]]) -> dict:
    """One train problem against one held-out problem on a fixed list of inputs.

    An input a reference did not answer (a timeout, a skipped draw, a
    RecursionError or MemoryError, or a t value the reference's own argument
    shape cannot hold) is UNANSWERED: never agreement, never a difference, and
    when it is an own input it leaves the own-input count (own_unanswered).
    HyClone (https://arxiv.org/html/2508.01357v1) drops such inputs the same
    way. An answer a reference already gave is used even after the reference
    stopped answering this pair's draws, and that stop is per draw shape."""
    own_total = own_agreed = own_unanswered = own_eval_agreed = 0
    draws = draws_agreed = agreed = 0
    differences = one_sided = undefined = timeouts = exhausted = unrenderable = 0
    both_raised = draws_refused_alike = 0
    answered = {train_id: 0, eval_id: 0}
    timed_out: dict[tuple, int] = {}      # (reference, draw shape) -> timeouts on this pair's draws of that shape
    witness = None
    for tag, args, weight in inputs:
        is_own = tag.startswith("own")
        if is_own:
            own_total += 1
        else:
            draws += weight
        results = {}
        for tid in (train_id, eval_id):
            hit = runner.cached(tid, args)
            if hit is not None:
                results[tid] = hit          # an answer already given is never skipped
            elif not is_own and timed_out.get((tid, tag), 0) >= PAIR_TIMEOUTS:
                # this reference has stopped answering this pair's draws of this
                # shape; the own inputs (at most 8 per problem) and the other
                # shape's draws are still tried
                results[tid] = ("skipped",)
            else:
                results[tid] = runner.call(tid, args)
                if results[tid][0] == "timeout" and not is_own:
                    timed_out[(tid, tag)] = timed_out.get((tid, tag), 0) + 1
        r_train, r_eval = results[train_id], results[eval_id]
        ok_train, ok_eval = r_train[0] == "ok", r_eval[0] == "ok"
        answered[train_id] += ok_train
        answered[eval_id] += ok_eval
        kinds = {r_train[0], r_eval[0]}
        if kinds & UNANSWERED:
            # An input a reference did not answer says nothing about the
            # function: not agreement, and not a difference either.
            undefined += weight
            if kinds & {"timeout", "skipped"}:
                timeouts += weight
            if "exhausted" in kinds:
                exhausted += weight
            if "unrenderable" in kinds:
                unrenderable += weight
            if is_own:
                own_unanswered += 1
            continue
        if ok_train and ok_eval:
            if r_train[1] == r_eval[1]:
                agreed += weight
                if is_own:
                    own_agreed += 1
                    if tag == "own_eval":
                        own_eval_agreed += 1
                else:
                    draws_agreed += weight
                continue
            differences += weight
            kind = "disagree"
        elif ok_train or ok_eval:
            one_sided += weight
            kind = "one raised"
        else:
            undefined += weight
            if r_train[0] == "raised" and r_eval[0] == "raised" and r_train[1] == r_eval[1]:
                both_raised += weight       # the same refusal of the same input: behaviour, and alike
                if not is_own:
                    draws_refused_alike += weight
            continue
        # the first difference on an own input outranks one on a draw: it is the stronger witness
        if witness is None or (is_own and not witness["where"].startswith("own")):
            witness = {"where": tag, "kind": kind, "input": _brief([render(a, None) for a in args]),
                       "train_said": _show(r_train[1]) if ok_train else r_train[0],
                       "eval_said": _show(r_eval[1]) if ok_eval else r_eval[0]}
    out = {"train_id": int(train_id), "eval_id": int(eval_id),
           "agreed_inputs": agreed, "own_inputs": own_total, "own_agreed": own_agreed,
           "own_unanswered": own_unanswered, "own_eval_agreed": own_eval_agreed,
           "draws": draws, "draws_agreed": draws_agreed, "draws_refused_alike": draws_refused_alike,
           "both_raised": both_raised, "differences": differences, "one_sided": one_sided,
           "undefined": undefined, "timeouts": timeouts, "exhausted": exhausted, "unrenderable": unrenderable,
           "train_answered": answered[train_id], "eval_answered": answered[eval_id]}
    if runner.reference(train_id) is None or runner.reference(eval_id) is None:
        out["fixed"] = "no reference"
    if witness is not None:
        out["difference"] = witness
    out["verdict"] = verdict_of(out)
    return out


def verdict_of(pair: dict) -> str:
    """The verdict from a pair's counts. The run measures; this decides, so a
    changed threshold re-derives every verdict from the progress files without
    running a reference again.

    Schema 2: own inputs a reference did not answer leave the count. The first
    version required own_agreed == own_inputs, so one timed-out own input made
    a duplicate verdict impossible whatever the other 105 inputs said."""
    if pair.get("fixed"):
        return pair["fixed"]                # "no reference", "cannot draw"
    if "own_unanswered" not in pair or "own_eval_agreed" not in pair:
        raise SystemExit("REFUSED: a pair record without own_unanswered and own_eval_agreed was written by "
                         "schema 1 of behavioural_decontam.py; rerun the pool under schema 2")
    if not pair["train_answered"] or not pair["eval_answered"]:
        return "not run"
    if pair["differences"] or pair["one_sided"]:
        return "different" if pair["difference"]["where"].startswith("own") else "minimal pair"
    own_answered = pair["own_inputs"] - pair["own_unanswered"]
    if (own_answered > 0 and pair["own_agreed"] == own_answered and pair["own_eval_agreed"] >= 1
            and pair["draws_agreed"] >= MIN_DRAWS_VALUED
            and pair["draws_agreed"] + pair["draws_refused_alike"] >= MIN_DRAWS_AGREED):
        return "duplicate"
    return "undecided"


def why_undecided(pair: dict) -> str:
    """What an undecided pair fell short of, for the reader who must decide it."""
    own_answered = pair["own_inputs"] - pair["own_unanswered"]
    parts = []
    if own_answered <= 0:
        parts.append(f"no own input answered by both ({pair['own_unanswered']} unanswered)")
    elif pair["own_agreed"] < own_answered:
        parts.append(f"{own_answered - pair['own_agreed']} own input(s) answered by both without equal values "
                     "(both raised)")
    elif pair["own_eval_agreed"] < 1:
        parts.append("none of the held-out problem's own inputs answered by both")
    alike = pair["draws_agreed"] + pair["draws_refused_alike"]
    if pair["draws_agreed"] < MIN_DRAWS_VALUED:
        parts.append(f"{pair['draws_agreed']} of {pair['draws']} draws with equal values (need {MIN_DRAWS_VALUED})")
    elif alike < MIN_DRAWS_AGREED:
        parts.append(f"{alike} of {pair['draws']} draws answered alike (need {MIN_DRAWS_AGREED})")
    unanswered = []
    if pair.get("timeouts"):
        unanswered.append(f"{pair['timeouts']} not in time")
    if pair.get("exhausted"):
        unanswered.append(f"{pair['exhausted']} over the recursion or memory limit")
    if pair.get("unrenderable"):
        unanswered.append(f"{pair['unrenderable']} outside the other problem's argument shape")
    if unanswered:
        parts.append("unanswered: " + ", ".join(unanswered))
    return "; ".join(parts) or "fell short of the bar"


def compare_eval(runner: Runner, pool: dict, eval_id: int, train_ids: list[int], draws: dict,
                 known: dict | None = None, known_pool: str = "") -> list[dict]:
    """Every train problem of this held-out problem's signature, against it.

    A pair already measured for an earlier pool version (`known`, from that
    run's progress file) is copied, marked `copied_from`, not run again: pool
    v6 is v5's entries unchanged plus the stdin problems (spec_experiment.pool),
    the draws are seeded by problem id, so the pair's counts are the same."""
    eval_entry = pool[eval_id]
    eval_draws = draws.get(eval_id)
    results = []
    for train_id in train_ids:
        if known and (int(train_id), int(eval_id)) in known:
            results.append(dict(known[(int(train_id), int(eval_id))], copied_from=known_pool))
            continue
        train_draws = draws.get(train_id)
        if eval_draws is None or train_draws is None:
            results.append({"train_id": int(train_id), "eval_id": int(eval_id), "verdict": "cannot draw",
                            "fixed": "cannot draw", "agreed_inputs": 0, "own_inputs": 0, "own_agreed": 0,
                            "own_unanswered": 0, "own_eval_agreed": 0,
                            "draws": 0, "draws_agreed": 0, "draws_refused_alike": 0, "both_raised": 0,
                            "differences": 0, "one_sided": 0, "undefined": 0, "timeouts": 0,
                            "exhausted": 0, "unrenderable": 0,
                            "train_answered": 0, "eval_answered": 0})
            continue
        inputs = pair_inputs(pool[train_id], eval_entry, train_draws, eval_draws)
        results.append(compare_pair(runner, train_id, eval_id, inputs))
    return results


# --------------------------------------------------------------- the run --

def sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_split(pool: dict, version: str, split_path: Path) -> dict:
    """The split's ids, refused loudly when the split describes a pool this process did not load."""
    split = json.loads(Path(split_path).read_text(encoding="utf-8"))
    if split.get("pool") != version:
        raise SystemExit(f"REFUSED: {split_path} is split of pool {split.get('pool')!r}, not {version}")
    if int(split.get("pool_size", -1)) != len(pool):
        # The worktree failure mode: nl/data or t/out is missing and the pool
        # silently shrinks to an older version. A verdict about a smaller pool
        # would be printed as if it were about this one.
        raise SystemExit(f"REFUSED: pool {version} loaded {len(pool)} entries, the split says {split.get('pool_size')}; "
                         "the pool's data is not all on this machine")
    eval_ids = [int(i) for i in split["eval_ids"]]
    train_ids = [int(i) for i in split["train_ids"]]
    missing = [i for i in eval_ids + train_ids if i not in pool]
    if missing:
        raise SystemExit(f"REFUSED: {len(missing)} split id(s) not in pool {version}: {missing[:5]}")
    return {"eval_ids": eval_ids, "train_ids": train_ids, "split_sha256": sha256_of(split_path),
            "split": str(split_path)}


def group_by_signature(pool: dict, eval_ids: list[int], train_ids: list[int]) -> list[tuple[int, list[int]]]:
    """(eval id, the train ids of its signature kinds), largest groups first for the worker balance."""
    trains: dict[tuple, list[int]] = {}
    for tid in train_ids:
        trains.setdefault(signature(pool[tid]), []).append(tid)
    tasks = [(eid, sorted(trains.get(signature(pool[eid]), []))) for eid in eval_ids]
    return sorted(tasks, key=lambda t: (-len(t[1]), t[0]))


_WORKER: dict = {}


def _worker_init(pool: dict, draws: dict, timeout_s: float, memory_bytes: int, known: dict | None = None,
                 refuse: dict | None = None, hung_path: Path | None = None):
    _WORKER["runner"] = Runner(pool, timeout_s=timeout_s, refuse=refuse)
    _TIMER["hung_path"] = str(hung_path) if hung_path else None
    _WORKER["pool"] = pool
    _WORKER["draws"] = draws
    _WORKER["known"] = known or {"pairs": {}, "not_run": {}, "pool": ""}
    if memory_bytes:
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        except (ImportError, ValueError, OSError):
            pass


def _worker(task: tuple[int, list[int]]) -> dict:
    eval_id, train_ids = task
    _TIMER["eval_id"] = int(eval_id)
    runner: Runner = _WORKER["runner"]
    started = time.time()
    known = _WORKER["known"]
    try:
        results = compare_eval(runner, _WORKER["pool"], eval_id, train_ids, _WORKER["draws"],
                               known["pairs"], known["pool"])
    except KeyboardInterrupt:
        raise
    except BaseException as error:                              # noqa: BLE001
        # Reported to the parent by held-out id and left out of the progress
        # file, so the run goes on and a rerun retries exactly this id; one
        # bad reference must not take the other 231 down with it.
        import traceback
        return {"eval_id": int(eval_id), "error": f"{type(error).__name__}: {error}",
                "traceback": traceback.format_exc()[-2000:]}
    not_run = {}
    copied = {int(p["train_id"]) for p in results if p.get("copied_from")}
    for tid in [eval_id] + list(train_ids):
        if tid in copied or (tid == eval_id and copied and int(eval_id) in known["not_run"]):
            if int(tid) in known["not_run"]:
                not_run[int(tid)] = known["not_run"][int(tid)]     # the earlier run's finding, carried over
            continue
        why = runner.why_not_run(tid)
        if why is not None and why != "reference was never called":
            not_run[int(tid)] = why
    return {"eval_id": int(eval_id), "pairs": results, "not_run": not_run, "copied": len(copied),
            "seconds": round(time.time() - started, 2)}


MEASUREMENT_KEYS = ("seed", "draws_per_problem", "timeout_s", "budget_s", "max_timeouts", "pair_timeouts")


def load_known(path: Path, version: str, header: dict) -> dict:
    """An earlier pool version's finished progress file, as pairs this run may copy.

    Refused unless that pool precedes this one (pool v6 is v5 plus the stdin
    problems, entries and ids unchanged) and its measurement settings match."""
    known = read_progress(path)
    earlier = known["header"]
    if earlier.get("pool") not in se.POOL_VERSIONS or se.POOL_VERSIONS.index(earlier["pool"]) >= se.POOL_VERSIONS.index(version):
        raise SystemExit(f"REFUSED: --known {path} is pool {earlier.get('pool')!r}, not an earlier pool than {version}")
    for key in MEASUREMENT_KEYS:
        if earlier.get(key) != header[key]:
            raise SystemExit(f"REFUSED: --known {path} has {key}={earlier.get(key)!r}, this run {header[key]!r}")
    pairs = {(int(p["train_id"]), int(p["eval_id"])): {k: v for k, v in p.items() if k != "copied_from"}
             for p in known["pairs"]}
    return {"pairs": pairs, "not_run": known["not_run"], "pool": earlier["pool"], "file": Path(path).name,
            "split_sha256": earlier["split_sha256"]}


def run_pool(version: str, split_path: Path, progress: Path, jobs: int = 1, timeout_s: float = TIMEOUT_S,
             memory_bytes: int = 3 << 30, log=sys.stderr, pool: dict | None = None,
             known_path: Path | None = None, inactivity_s: float = INACTIVITY_S) -> dict:
    """Every held-out problem against every train problem of its signature; one JSONL line per held-out id.

    The progress file is the unit of resumption: a line already there for this
    pool version and split digest is not recomputed, so a run interrupted on a
    shared machine continues where it stopped. `known_path` names an earlier
    pool version's finished progress file whose pairs are copied, not rerun.

    A worker that dies mid-task (a reference that swallowed its timeout exits
    the worker, see _wall_backstop; a segfault) leaves multiprocessing.Pool
    waiting forever (CPython issue 66587, open), so results are taken with
    `inactivity_s` between them and the held-out ids not yet in the progress
    file are named when that runs out; the sidecar <progress>.hung names the
    reference, and the next run refuses it instead of running it again."""
    started = time.time()
    if pool is None:
        pool = se.pool(version)
    split = load_split(pool, version, split_path)
    header = {"kind": "header", "schema": SCHEMA, "pool": version, "pool_size": len(pool),
              "split": Path(split_path).name, "split_sha256": split["split_sha256"],
              "eval_ids": len(split["eval_ids"]), "train_ids": len(split["train_ids"]),
              "seed": SEED, "draws_per_problem": DRAWS_PER_PROBLEM, "min_draws_agreed": MIN_DRAWS_AGREED,
              "min_draws_valued": MIN_DRAWS_VALUED,
              "timeout_s": timeout_s, "budget_s": BUDGET_S, "max_timeouts": MAX_TIMEOUTS,
              "pair_timeouts": PAIR_TIMEOUTS, "rule": RULE_TEXT, "sources": list(SOURCES)}
    known = load_known(Path(known_path), version, header) if known_path else None
    if known:
        header["known_from"] = {"pool": known["pool"], "file": known["file"], "split_sha256": known["split_sha256"],
                                "pairs": len(known["pairs"])}
    done: set[int] = set()
    progress = Path(progress)
    if progress.exists():
        for line in progress.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("kind") == "header":
                # the measurement settings must match; the thresholds need not, because
                # verdict_of re-derives every verdict from the counts when the file is read
                for key in ("schema", "pool", "split_sha256") + MEASUREMENT_KEYS:
                    if record.get(key) != header[key]:
                        raise SystemExit(f"REFUSED: {progress} was written for {key}={record.get(key)!r}, "
                                         f"this run has {header[key]!r}; use another progress file")
            elif record.get("kind") == "eval":
                done.add(int(record["eval_id"]))
    else:
        progress.parent.mkdir(parents=True, exist_ok=True)
        progress.write_text(json.dumps(header) + "\n", encoding="utf-8")
    hung = hung_path_for(progress)
    refuse = read_hung(hung)
    if refuse:
        print(f"  refusing {len(refuse)} reference(s) an earlier run's worker died in ({hung}): {sorted(refuse)}",
              file=log, flush=True)
    draws = {tid: draws_for(tid, pool[tid]) for tid in set(split["eval_ids"]) | set(split["train_ids"])}
    tasks = [t for t in group_by_signature(pool, split["eval_ids"], split["train_ids"]) if t[0] not in done]
    pairs = sum(len(t[1]) for t in tasks)
    print(f"behavioural decontamination: pool {version} ({len(pool)}), {len(split['eval_ids'])} held-out, "
          f"{len(split['train_ids'])} train, {len(tasks)} held-out ids to do ({len(done)} done), "
          f"{pairs} pairs, {jobs} worker(s)", file=log, flush=True)
    finished = 0
    failed: list[dict] = []
    with progress.open("a", encoding="utf-8") as out:
        def record(result: dict):
            nonlocal finished
            if "error" in result:
                failed.append(result)
                print(f"  held-out {result['eval_id']} FAILED: {result['error']}\n{result.get('traceback', '')}",
                      file=log, flush=True)
                return
            result["kind"] = "eval"
            out.write(json.dumps(result, sort_keys=True) + "\n")
            out.flush()
            finished += 1
            if finished % 10 == 0 or finished == len(tasks):
                counts = {}
                for pair in result["pairs"]:
                    counts[pair["verdict"]] = counts.get(pair["verdict"], 0) + 1
                print(f"  {finished}/{len(tasks)} held-out {result['eval_id']}: {len(result['pairs'])} pairs "
                      f"{counts} in {result['seconds']}s; {time.time() - started:.0f}s so far", file=log, flush=True)
        if jobs > 1:
            import multiprocessing
            context = multiprocessing.get_context("fork")
            pending = {int(t[0]) for t in tasks}
            with context.Pool(jobs, initializer=_worker_init,
                              initargs=(pool, draws, timeout_s, memory_bytes, known, refuse, hung),
                              maxtasksperchild=16) as workers:
                results = workers.imap_unordered(_worker, tasks)
                while pending:
                    try:
                        result = results.next(timeout=inactivity_s)
                    except StopIteration:
                        break
                    except multiprocessing.TimeoutError:
                        workers.terminate()
                        raise SystemExit(f"FAILED: no held-out id finished in {inactivity_s:.0f}s; not in {progress}: "
                                         f"{sorted(pending)}. A worker died mid-task (a reference that swallowed its "
                                         f"timeout is named in {hung} and on stderr) or the machine is starved; rerun to "
                                         "continue, the named reference is then refused") from None
                    pending.discard(int(result["eval_id"]))
                    record(result)
            if pending:
                raise SystemExit(f"FAILED: the workers finished without results for held-out ids {sorted(pending)}; "
                                 f"see {hung} and stderr, then rerun")
        else:
            _worker_init(pool, draws, timeout_s, 0, known, refuse, hung)
            for task in tasks:
                record(_worker(task))
    if failed:
        raise SystemExit(f"FAILED: {len(failed)} held-out id(s) raised inside the comparison and are not in "
                         f"{progress}: {[f['eval_id'] for f in failed]}; fix the cause and rerun to finish them")
    return {"header": header, "seconds": round(time.time() - started, 1), "progress": str(progress)}


# ------------------------------------------------------------ the policy --

def read_progress(path: Path) -> dict:
    """A finished progress file as {header, pairs, not_run}; refused when a held-out id is missing."""
    header = None
    pairs: list[dict] = []
    not_run: dict[int, str] = {}
    seen: set[int] = set()
    # A witness written before _brief existed can hold an integer of 10^5
    # digits, which json refuses to read back under Python's default limit.
    if hasattr(sys, "set_int_max_str_digits"):
        sys.set_int_max_str_digits(0)
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("kind") == "header":
            header = record
            if header.get("schema") != SCHEMA:
                raise SystemExit(f"REFUSED: {path} was written by schema {header.get('schema')!r} of "
                                 f"behavioural_decontam.py, this is schema {SCHEMA} (own inputs a reference did "
                                 "not answer leave the count); rerun the pool")
        elif record.get("kind") == "eval":
            seen.add(int(record["eval_id"]))
            for pair in record["pairs"]:
                pair["verdict"] = verdict_of(pair)      # this file's thresholds, not the run's
                pairs.append(pair)
            for tid, why in record.get("not_run", {}).items():
                not_run[int(tid)] = why
    if header is None:
        raise SystemExit(f"REFUSED: {path} has no header")
    if len(seen) != int(header["eval_ids"]):
        raise SystemExit(f"REFUSED: {path} holds {len(seen)} of {header['eval_ids']} held-out ids; the run did not finish")
    return {"header": header, "pairs": pairs, "not_run": not_run}


def _names(pool: dict | None, tid: int) -> str:
    if pool and tid in pool:
        return problem_name(tid, pool[tid])
    return str(tid)


def _text(pool: dict | None, tid: int, n: int = 110) -> str:
    if pool and tid in pool:
        text = " ".join((pool[tid]["rec"].get("text") or "").split())
        return text[:n] + ("..." if len(text) > n else "")
    return ""


def id_class(tid: int) -> str:
    """mbpp, humaneval, apps (function-shaped) or stdin, from the id ranges spec_experiment assigns."""
    tid = int(tid)
    if tid < se.HUMANEVAL_BASE:
        return "mbpp"
    if tid < se.APPS_BASE:
        return "humaneval"
    if tid < se.APPS_BASE + se.HUMANEVAL_BASE:
        return "apps"
    return "stdin"


def by_class(ids) -> dict[str, int]:
    counts = {"mbpp": 0, "humaneval": 0, "apps": 0, "stdin": 0}
    for tid in ids:
        counts[id_class(tid)] += 1
    return counts


READINGS = ("same function", "different function")


def parse_readings(same: list[str], different: list[str]) -> dict[tuple[int, int], dict]:
    """--read-same / --read-different arguments, `TRAIN:EVAL=note`, as {(train, eval): {reading, note}}."""
    out: dict[tuple[int, int], dict] = {}
    for reading, items in ((READINGS[0], same), (READINGS[1], different)):
        for item in items:
            key, sep, note = item.partition("=")
            train, colon, held = key.partition(":")
            if not (colon and train.strip().isdigit() and held.strip().isdigit()):
                raise SystemExit(f"REFUSED: a reading is TRAIN:EVAL=note, not {item!r}")
            if not note.strip():
                raise SystemExit(f"REFUSED: the reading of {key} needs a note saying what was read: {item!r}")
            pair = (int(train), int(held))
            if pair in out:
                raise SystemExit(f"REFUSED: pair {pair} read twice")
            out[pair] = {"reading": reading, "note": note.strip()}
    return out


def build_policy(runs: list[dict], pools: dict[str, dict] | None = None, a2_policy: Path = A2_POLICY,
                 readings: dict[tuple[int, int], dict] | None = None, unread_ok: bool = False) -> dict:
    """The checked-in policy from one finished progress file per pool version.

    A pair the rule left undecided (never differed, fell short of the bar)
    must carry a reading by hand, `same function` or `different function`
    with a note, or this refuses: the review of 2026-09-25 found eight such
    pairs, Lucas numbers and binomial coefficients among them, admitted to
    every future corpus with neither a verdict nor a reading. A pair read as
    the same function is excluded like a duplicate and listed apart, with the
    counts it agreed on and both statements, so the reading can be checked."""
    readings = dict(readings or {})
    a2 = json.loads(Path(a2_policy).read_text(encoding="utf-8"))
    a2_ids = {int(i) for i in a2["exclude_future_train_ids"]}
    per_pool: dict[str, dict] = {}
    duplicates: list[dict] = []
    minimal: list[dict] = []
    undecided: list[dict] = []
    not_run: list[dict] = []
    by_train: dict[int, set[int]] = {}
    by_reading: dict[int, set[int]] = {}
    eval_with_twin: set[int] = set()
    for run in runs:
        header = run["header"]
        version = header["pool"]
        pool = (pools or {}).get(version)
        counts: dict[str, int] = {}
        for pair in run["pairs"]:
            counts[pair["verdict"]] = counts.get(pair["verdict"], 0) + 1
            row = {"pool": version, "train_id": pair["train_id"], "train": _names(pool, pair["train_id"]),
                   "eval_id": pair["eval_id"], "eval": _names(pool, pair["eval_id"]),
                   "agreed_inputs": pair["agreed_inputs"], "own_inputs": pair["own_inputs"],
                   "own_agreed": pair["own_agreed"], "own_unanswered": pair.get("own_unanswered", 0),
                   "draws": pair["draws"], "draws_agreed": pair["draws_agreed"]}
            if pair["verdict"] == "duplicate":
                duplicates.append(row)
                by_train.setdefault(pair["train_id"], set()).add(pair["eval_id"])
                eval_with_twin.add(pair["eval_id"])
            elif pair["verdict"] == "minimal pair":
                row["difference"] = pair.get("difference")
                minimal.append(row)
            elif pair["verdict"] == "undecided":
                row.update({"own_eval_agreed": pair["own_eval_agreed"], "draws_refused_alike": pair["draws_refused_alike"],
                            "undefined": pair["undefined"], "timeouts": pair["timeouts"],
                            "exhausted": pair.get("exhausted", 0), "unrenderable": pair.get("unrenderable", 0),
                            "why": why_undecided(pair),
                            "train_text": _text(pool, pair["train_id"], 300), "eval_text": _text(pool, pair["eval_id"], 300)})
                key = (int(pair["train_id"]), int(pair["eval_id"]))
                if key in readings:
                    row.update(readings[key])
                    if readings[key]["reading"] == READINGS[0]:
                        by_reading.setdefault(key[0], set()).add(key[1])
                        eval_with_twin.add(key[1])
                undecided.append(row)
        for tid, why in sorted(run["not_run"].items()):
            not_run.append({"pool": version, "id": int(tid), "name": _names(pool, int(tid)), "why": why})
        per_pool[version] = {"split": header["split"], "split_sha256": header["split_sha256"],
                             "pool_size": header["pool_size"], "eval_ids": header["eval_ids"],
                             "train_ids": header["train_ids"], "pairs": len(run["pairs"]), "verdicts": counts,
                             "references_not_run": len(run["not_run"])}
        copied = [pair["copied_from"] for pair in run["pairs"] if pair.get("copied_from")]
        if copied:
            # read off the pairs, not the header: a run resumed with --known keeps its first header
            per_pool[version]["pairs_copied_from"] = {"pool": sorted(set(copied)), "pairs": len(copied),
                                                      "file": header.get("known_from", {}).get("file")}
    undecided_keys = {(r["train_id"], r["eval_id"]) for r in undecided}
    unread = sorted(undecided_keys - set(readings))
    if unread and not unread_ok:
        names = {(r["train_id"], r["eval_id"]): f"{r['train']} vs {r['eval']}: {r['why']}" for r in undecided}
        raise SystemExit("REFUSED: the rule left these pairs undecided and they have no reading by hand "
                         "(--read-same TRAIN:EVAL=note or --read-different TRAIN:EVAL=note):\n  "
                         + "\n  ".join(f"{k[0]}:{k[1]} {names[k]}" for k in unread))
    stray = sorted(set(readings) - undecided_keys)
    if stray:
        raise SystemExit(f"REFUSED: readings for pairs the rule decided, or that were never compared: {stray}")
    exclude = sorted(set(by_train) | set(by_reading))
    distinct = {"duplicate_pairs": len({(r["train_id"], r["eval_id"]) for r in duplicates}),
                "minimal_pairs": len({(r["train_id"], r["eval_id"]) for r in minimal}),
                "undecided_pairs": len(undecided_keys),
                "undecided_read_as_same": len({k for k, v in readings.items() if v["reading"] == READINGS[0]}),
                "undecided_read_as_different": len({k for k, v in readings.items() if v["reading"] == READINGS[1]}),
                "undecided_unread": len(unread),
                "references_not_run": len({r["id"] for r in not_run})}
    read_by_hand = sorted((r for r in undecided if r.get("reading")),
                          key=lambda r: (r["pool"], r["train_id"], r["eval_id"]))
    return {
        "schema": SCHEMA,
        "about": ("Train problems whose reference solution computes the same function as a held-out problem's "
                  "(t/out/loop/split-v3.json eval ids, unchanged through split-v6) on both problems' own "
                  "assertion inputs and on drawn inputs, plus the pairs the rule left undecided and were read by "
                  "hand as the same function (read_by_hand). Human-readable report with examples: "
                  "t/DECONTAMINATION-BEHAVIOURAL-2026-09-25.md. Loaded by loop_filter.decontamination(), "
                  "which merges exclude_train_ids into the same-task exclusions of t/decontamination-2026-09-21.json."),
        "rule": {"text": RULE_TEXT, "seed": SEED, "draws_per_problem": DRAWS_PER_PROBLEM,
                 "draws_per_pair": 2 * DRAWS_PER_PROBLEM, "min_draws_agreed": MIN_DRAWS_AGREED,
                 "min_draws_valued": MIN_DRAWS_VALUED,
                 "timeout_s_cpu": TIMEOUT_S, "budget_s_cpu": BUDGET_S, "max_timeouts": MAX_TIMEOUTS,
                 "pair_timeouts": PAIR_TIMEOUTS, "recursion_limit": RECURSION_LIMIT,
                 "signature": "argument kinds and result kind of the first assertion",
                 "one_sided_raise": "a difference",
                 "unanswered": ("an input a reference did not answer (not in time, over its recursion or memory "
                                "limit, or a t value the other problem's argument shape cannot hold) is undefined: "
                                "never agreement, never a difference; an own input so left leaves the own-input count"),
                 "undecided": ("a pair that never differed and fell short of the bar; read by hand before this file "
                               "is written, and excluded when read as the same function"),
                 "outputs_compared": "as t reads them (canon)",
                 "code": "t/behavioural_decontam.py"},
        "sources": list(SOURCES),
        "pools": per_pool,
        "distinct": distinct,               # the lists below are per pool, and pool v6 holds v5's pairs again
        "exclude_train_ids": exclude,
        "exclude_train_ids_by_eval": {str(tid): sorted(by_train.get(tid, set()) | by_reading.get(tid, set()))
                                      for tid in exclude},
        "exclude_train_ids_by_reading": sorted(by_reading),
        "exclusions_by_class": {"all": by_class(exclude), "new": by_class(set(exclude) - a2_ids),
                                "rediscovered": by_class(a2_ids & set(exclude))},
        "behavioural_overlap_eval_ids": sorted(eval_with_twin),
        "rediscovered_from_2026_09_21": sorted(a2_ids & set(exclude)),
        "new_exclusions": sorted(set(exclude) - a2_ids),
        "not_rediscovered_from_2026_09_21": sorted(a2_ids - set(exclude)),
        "duplicates": sorted(duplicates, key=lambda r: (r["pool"], r["train_id"], r["eval_id"])),
        "read_by_hand": read_by_hand,
        "minimal_pairs": sorted(minimal, key=lambda r: (r["pool"], r["train_id"], r["eval_id"])),
        "undecided": sorted(undecided, key=lambda r: (r["pool"], r["train_id"], r["eval_id"])),
        "references_not_run": not_run,
    }


def _why_not_rediscovered(policy: dict, runs: list[dict], tid: int) -> str:
    """The best explanation the runs give for a 2026-09-21 exclusion this rule did not find."""
    verdicts = [p for run in runs for p in run["pairs"] if p["train_id"] == tid]
    if not verdicts:
        return "not in any pool's train split, or no held-out problem shares its signature kinds"
    for entry in policy["references_not_run"]:
        if entry["id"] == tid:
            return entry["why"]
    kinds = sorted({p["verdict"] for p in verdicts})
    best = max(verdicts, key=lambda p: (p["verdict"] == "minimal pair", p["agreed_inputs"]))
    return (f"verdicts {kinds}; closest held-out {best['eval_id']} ({best['verdict']}, "
            f"{best['agreed_inputs']} agreed)")


def write_report(policy: dict, runs: list[dict], pools: dict[str, dict] | None, path: Path,
                 notes: str = "") -> None:
    a2 = json.loads(Path(A2_POLICY).read_text(encoding="utf-8"))
    lines = ["# Behavioural decontamination of the train split, 2026-09-25", "",
             "The second decontamination list `t/loop_filter.decontamination()` merges, beside",
             "`t/DECONTAMINATION-2026-09-21.md` (the same-task list read by hand). This one is",
             "computed: a train problem whose reference solution computes the same function",
             "as a held-out problem's, on both problems' own assertion inputs and on 100",
             "drawn inputs, teaches the held-out answer whatever its English says, so it",
             "leaves every future corpus. Written by `t/behavioural_decontam.py` (schema 2,",
             "after the review of 2026-09-25).", "",
             "## The rule", "", f"- {policy['rule']['text']}.",
             f"- Draws: {DRAWS_PER_PROBLEM} per problem with `spec_check.draw()` shaped like the problem's",
             f"  first example, seeded `{SEED}:<id>`, so a pair sees {2 * DRAWS_PER_PROBLEM} draws; a duplicate",
             f"  needs at least {MIN_DRAWS_AGREED} of them answered alike (equal values, or both references",
             f"  raising the same exception on that input) and at least {MIN_DRAWS_VALUED} equal values.",
             "- Signature kinds: the argument kinds and the result kind of the first assertion.",
             "- Outputs are compared as t reads them: a string is its code points, a",
             "  one-character string is that character, `true` is not `1`.",
             "- An input a reference did not answer says nothing: not in time (1 s CPU),",
             "  over its recursion or memory limit, or a t value the other problem's",
             "  argument shape cannot hold. An own input so left leaves the own-input",
             "  count; a duplicate needs every answered own input agreed, at least one of",
             "  them the held-out problem's own. (Schema 1 required every own input to",
             "  agree, so one timed-out own input made a duplicate impossible; the review",
             "  of 2026-09-25 found eight such pairs.)",
             "- A pair that agrees on every answered own input and differs on a drawn one",
             "  is a MINIMAL PAIR, kept, and listed below; a pair that differs on an own",
             "  input is simply different and is not listed.",
             "- A pair that never differed but falls short of the bar is UNDECIDED. Each",
             "  is listed with both statements and was read by hand before this file was",
             "  written (`write` refuses otherwise); one read as the same function is",
             "  excluded and listed apart from the computed duplicates.",
             "- A reference that does not load, does not finish, or raises on every input is",
             "  reported by name and is never counted as agreeing. The rule says nothing",
             "  about such a train problem; the 2026-09-21 text and AST reading is the",
             "  only check it has had.", "",
             "Prior art (fetched 2026-09-25): " + "; ".join(SOURCES) + ".", "",
             "What the rule cannot see: draws follow the example's shape, so two problems",
             "that differ only outside it (negative inputs, an unsorted sequence) count as",
             "duplicates here. That is the right side to err on for a corpus: the train",
             "problem's program passes the held-out problem's tests. Conversely a draw",
             "outside both problems' stated domains (0 for two problems about positive",
             "integers) can part two references that agree everywhere the problems look,",
             "and the pair is then a minimal pair, kept.", "",
             "## Counts", "", "| pool | split | held-out | train | pairs | duplicate | minimal pair | different | undecided | not run or no reference | cannot draw | references not run |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for version, info in policy["pools"].items():
        v = info["verdicts"]
        lines.append(f"| {version} | `{info['split']}` `{info['split_sha256'][:12]}` | {info['eval_ids']} | {info['train_ids']} | "
                     f"{info['pairs']} | {v.get('duplicate', 0)} | {v.get('minimal pair', 0)} | {v.get('different', 0)} | "
                     f"{v.get('undecided', 0)} | {v.get('not run', 0) + v.get('no reference', 0)} | {v.get('cannot draw', 0)} | "
                     f"{info['references_not_run']} |")
    excl = policy["exclude_train_ids"]
    by_reading = policy["exclude_train_ids_by_reading"]
    classes = policy["exclusions_by_class"]
    lines += ["", f"**{len(excl)} train ids are excluded** from every future build "
              f"({len(excl) - len(by_reading)} computed duplicates, {len(by_reading)} read by hand as the same function): "
              + ", ".join(map(str, excl)) + ".", "",
              f"- Rediscovered from the 21 same-task exclusions of 2026-09-21: {len(policy['rediscovered_from_2026_09_21'])} "
              f"({', '.join(map(str, policy['rediscovered_from_2026_09_21'])) or 'none'}).",
              f"- New: {len(policy['new_exclusions'])} ({', '.join(map(str, policy['new_exclusions'])) or 'none'}).",
              f"- Read by hand: {len(by_reading)} ({', '.join(map(str, by_reading)) or 'none'}).",
              f"- Held-out problems with a behavioural twin in training: {len(policy['behavioural_overlap_eval_ids'])} "
              f"({', '.join(map(str, policy['behavioural_overlap_eval_ids'])) or 'none'}). The 32 overlap ids of",
              "  2026-09-21 stay frozen; `score_heldout.py` can report these separately.", "",
              "| exclusions | mbpp | humaneval | apps (function) | stdin-shaped |", "|---|---:|---:|---:|---:|"]
    for name in ("all", "new", "rediscovered"):
        c = classes[name]
        lines.append(f"| {name} ({sum(c.values())}) | {c['mbpp']} | {c['humaneval']} | {c['apps']} | {c['stdin']} |")
    lines += ["", "## Ten duplicates", ""]
    shown = 0
    for row in policy["duplicates"]:
        if shown >= 10:
            break
        pool = (pools or {}).get(row["pool"])
        lines.append(f"{shown + 1}. train `{row['train']}` ({row['train_id']}): {_text(pool, row['train_id'])}")
        lines.append(f"   held-out `{row['eval']}` ({row['eval_id']}): {_text(pool, row['eval_id'])}")
        lines.append(f"   agreed on {row['agreed_inputs']} inputs ({row['own_agreed']} of {row['own_inputs']} own, "
                     f"{row['own_unanswered']} own unanswered, {row['draws_agreed']} of {row['draws']} draws), pool {row['pool']}")
        shown += 1
    if not shown:
        lines.append("(none)")
    distinct = policy["distinct"]
    lines += ["", f"Distinct over the pools (pool v6 holds every v5 pair again): {distinct['duplicate_pairs']} duplicate pairs, "
              f"{distinct['minimal_pairs']} minimal pairs, {distinct['undecided_pairs']} undecided pairs "
              f"({distinct['undecided_read_as_same']} read as the same function, {distinct['undecided_read_as_different']} "
              f"as different, {distinct['undecided_unread']} unread), "
              f"{distinct['references_not_run']} references that did not run.",
              "", "## Undecided pairs, read by hand", "",
              f"{distinct['undecided_pairs']} distinct pairs never differed on an input both references answered "
              f"but fell short of the bar ({len(policy['undecided'])} rows in the JSON, per pool). The rule excludes "
              "none of them by itself; each was read from both statements and the reading is recorded here and in "
              "the JSON. A pair read as the same function is excluded.", ""]
    seen_undecided: set = set()
    for row in policy["undecided"]:
        key = (row["train_id"], row["eval_id"])
        if key in seen_undecided:
            continue
        seen_undecided.add(key)
        reading = row.get("reading", "UNREAD")
        lines.append(f"- train {row['train_id']} `{row['train']}` vs held-out {row['eval_id']} `{row['eval']}`: "
                     f"**{reading}**. Agreed on {row['agreed_inputs']} inputs ({row['own_agreed']} of {row['own_inputs']} own, "
                     f"{row['own_unanswered']} own unanswered, {row['draws_agreed']} of {row['draws']} draws); {row['why']}.")
        if row.get("note"):
            lines.append(f"  reading: {row['note']}")
        lines.append(f"  train: {row['train_text']}")
        lines.append(f"  held-out: {row['eval_text']}")
    if not seen_undecided:
        lines.append("(none)")
    lines += ["", "## Minimal pairs (kept)", "",
              f"{distinct['minimal_pairs']} distinct pairs agree on every answered own input and differ on a drawn one "
              f"({len(policy['minimal_pairs'])} rows in the JSON, per pool). The first ten:", ""]
    for row in policy["minimal_pairs"][:10]:
        d = row.get("difference") or {}
        lines.append(f"- train {row['train_id']} `{row['train']}` vs held-out {row['eval_id']} `{row['eval']}`: "
                     f"agreed {row['agreed_inputs']}, then on input `{json.dumps(d.get('input'))}` train said "
                     f"`{json.dumps(d.get('train_said'))}`, held-out said `{json.dumps(d.get('eval_said'))}` ({d.get('kind')})")
    lines += ["", "## The 2026-09-21 exclusions this rule did not rediscover", ""]
    for tid in policy["not_rediscovered_from_2026_09_21"]:
        lines.append(f"- {tid}: {_why_not_rediscovered(policy, runs, tid)}")
    if not policy["not_rediscovered_from_2026_09_21"]:
        lines.append("(none)")
    lines += ["", "## References that did not run", "",
              f"{distinct['references_not_run']} references produced no value on any input they were given, "
              "so every pair with them is 'not run', never a duplicate (each listed once, from the first pool that ran it). "
              "The rule says nothing about these train problems; the only check they have had is the text and AST "
              "reading of 2026-09-21.", ""]
    shown_ids: set = set()
    for entry in policy["references_not_run"]:
        if entry["id"] in shown_ids:
            continue
        shown_ids.add(entry["id"])
        if len(shown_ids) > 80:
            lines.append(f"- ... {distinct['references_not_run'] - 80} more in the JSON")
            break
        lines.append(f"- {entry['pool']} {entry['id']} `{entry['name']}`: {entry['why']}")
    lines += ["", "## Weak tests", "",
              f"The 18 held-out problems with weak tests (`t/decontamination-2026-09-21.json` weak_test_eval_ids) are "
              f"{', '.join(map(str, a2.get('weak_test_eval_ids', [])))}; a duplicate verdict there rests on the draws, "
              "which is why the draws are required.", ""]
    if notes.strip():
        lines += ["## Reading of the results", "",
                  "Written by hand from the pairs above (passed to `write --notes`; the sections before this one",
                  "are generated).", "", notes.strip(), ""]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def cmd_write(args) -> int:
    runs = [read_progress(Path(p)) for p in args.from_progress]
    versions = [run["header"]["pool"] for run in runs]
    if len(set(versions)) != len(versions):
        raise SystemExit(f"REFUSED: two progress files for one pool version: {versions}")
    pools = {}
    if not args.no_pools:
        for version in versions:
            pools[version] = se.pool(version)
            expected = runs[versions.index(version)]["header"]["pool_size"]
            if len(pools[version]) != expected:
                raise SystemExit(f"REFUSED: pool {version} here has {len(pools[version])} entries, the run had {expected}")
    policy = build_policy(runs, pools, readings=parse_readings(args.read_same, args.read_different),
                          unread_ok=args.unread_ok)
    Path(args.out).write_text(json.dumps(policy, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    notes = Path(args.notes).read_text(encoding="utf-8") if args.notes else ""
    write_report(policy, runs, pools, Path(args.report), notes)
    d = policy["distinct"]
    print(f"wrote {args.out}: {len(policy['exclude_train_ids'])} excluded "
          f"({len(policy['rediscovered_from_2026_09_21'])} rediscovered, {len(policy['new_exclusions'])} new), "
          f"{d['duplicate_pairs']} duplicate pairs, {d['minimal_pairs']} minimal pairs, "
          f"{d['undecided_pairs']} undecided ({d['undecided_read_as_same']} read as the same function), "
          f"{d['references_not_run']} references not run; {args.report}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    run = sub.add_parser("run", help="compare one pool's train split against its held-out ids")
    run.add_argument("--pool", choices=se.POOL_VERSIONS, required=True)
    run.add_argument("--split", required=True)
    run.add_argument("--progress", required=True, help="JSONL, one line per held-out id; resumes")
    run.add_argument("--jobs", type=int, default=1)
    run.add_argument("--timeout", type=float, default=TIMEOUT_S, help="CPU seconds per reference call")
    run.add_argument("--memory-gb", type=float, default=3.0, help="RLIMIT_AS per worker; 0 for none")
    run.add_argument("--known", default="", help="an earlier pool version's finished progress file: its pairs are copied, not rerun")
    run.add_argument("--inactivity", type=float, default=INACTIVITY_S,
                     help="seconds without a finished held-out id before the run stops and names the unfinished ids")
    write = sub.add_parser("write", help="the policy file and report from finished progress files")
    write.add_argument("--from", dest="from_progress", nargs="+", required=True)
    write.add_argument("--out", required=True)
    write.add_argument("--report", required=True)
    write.add_argument("--no-pools", action="store_true", help="names and texts left out (no pool data here)")
    write.add_argument("--notes", default="", help="a markdown file appended to the report as the hand-written reading")
    write.add_argument("--read-same", action="append", default=[], metavar="TRAIN:EVAL=NOTE",
                       help="an undecided pair read by hand as the same function (excluded)")
    write.add_argument("--read-different", action="append", default=[], metavar="TRAIN:EVAL=NOTE",
                       help="an undecided pair read by hand as a different function (kept)")
    write.add_argument("--unread-ok", action="store_true", help="write although undecided pairs have no reading (a draft, never the checked-in file)")
    args = ap.parse_args(argv)
    if args.cmd == "run":
        result = run_pool(args.pool, Path(args.split), Path(args.progress), jobs=args.jobs, timeout_s=args.timeout,
                          memory_bytes=int(args.memory_gb * (1 << 30)),
                          known_path=Path(args.known) if args.known else None, inactivity_s=args.inactivity)
        print(f"done in {result['seconds']}s: {result['progress']}")
        return 0
    if args.cmd == "write":
        return cmd_write(args)
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
