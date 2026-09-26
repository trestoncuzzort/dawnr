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
  spec_check.draw() as the input generator.

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
        --out t/decontamination-behavioural-2026-09-25.json --report t/DECONTAMINATION-BEHAVIOURAL-2026-09-25.md
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import io
import json
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

SCHEMA = 1
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
SOURCES = (
    "https://ar5iv.labs.arxiv.org/html/2403.04811",
    "https://arxiv.org/html/2602.12413v1",
    "https://arxiv.org/html/2311.04850v2",
    "https://arxiv.org/html/2508.01357v1",
)
A2_POLICY = HERE / "decontamination-2026-09-21.json"
RULE_TEXT = ("a train problem is a behavioural duplicate of a held-out problem of the same signature kinds "
             "when both references run and return equal values (as t reads them) on every one of both problems' "
             "own assertion inputs and on every drawn input that both answered, with at least MIN_DRAWS_AGREED of "
             "the pair's 100 draws (50 per problem, spec_check.draw shaped like the problem's first example) "
             "answered alike (equal values, or both references raising the same exception) and at least "
             "MIN_DRAWS_VALUED of them equal values; an input where exactly one reference raises is a difference; "
             "an input a reference did not answer in time says nothing; a reference that does not run is "
             "reported by name and never counted as agreeing")


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


def _timeout(_sig, _frame):
    raise spec_check.Timeout()


def _disarm() -> None:
    """Both timers off and both handlers ignored, so a tick that already tripped is dropped, not raised later."""
    signal.setitimer(signal.ITIMER_VIRTUAL, 0)
    signal.setitimer(signal.ITIMER_REAL, 0)
    signal.signal(signal.SIGVTALRM, signal.SIG_IGN)
    signal.signal(signal.SIGALRM, signal.SIG_IGN)


def run_reference(fn, native: list, timeout_s: float = TIMEOUT_S) -> tuple:
    """("ok", canon) | ("raised", name) | ("timeout",); timeout_s is CPU time, with a 10x wall-clock backstop.

    The first version cleared the timers in a `finally` and let a Timeout that
    fired inside that `finally` escape: on the lab a worker died of it after 96
    held-out ids and multiprocessing tore the run down. A signal can arrive at
    any bytecode, so the timeout is caught around the clearing too, the handlers
    are set to ignore before returning (a signal that tripped during clearing is
    then dropped by the interpreter instead of raised at a random later line),
    and the streams a reference may have been in the middle of redirecting are
    put back."""
    streams = (sys.stdin, sys.stdout, sys.stderr)
    result = ("raised", "no result")
    try:
        try:
            signal.signal(signal.SIGVTALRM, _timeout)
            signal.signal(signal.SIGALRM, _timeout)
            signal.setitimer(signal.ITIMER_VIRTUAL, timeout_s)
            signal.setitimer(signal.ITIMER_REAL, 10 * timeout_s)
            with _quiet():
                out = fn(*native)
            result = ("ok", canon(out))
        finally:
            _disarm()
    except spec_check.Timeout:
        result = ("timeout",)
    except KeyboardInterrupt:
        raise
    except BaseException as error:                              # noqa: BLE001  (SystemExit included)
        result = ("raised", type(error).__name__)
    _disarm()
    sys.stdin, sys.stdout, sys.stderr = streams
    return result


class Runner:
    """Calls each problem's reference on t values, in its own native shape, with a cache per input."""

    def __init__(self, pool: dict, timeout_s: float = TIMEOUT_S, max_timeouts: int = MAX_TIMEOUTS,
                 budget_s: float = BUDGET_S):
        self.pool = pool
        self.timeout_s = timeout_s
        self.max_timeouts = max_timeouts
        self.budget_s = budget_s
        self.refs: dict[int, object] = {}
        self.shapes: dict[int, list] = {}
        self.cache: dict[tuple, tuple] = {}
        self.timeouts: dict[int, int] = {}
        self.spent: dict[int, float] = {}      # CPU seconds per reference
        self.ran: dict[int, int] = {}          # calls that returned a value
        self.calls: dict[int, int] = {}

    def reference(self, tid: int):
        if tid not in self.refs:
            entry = self.pool[tid]
            with _quiet():                  # a reference that prints at load time stays out of the log
                self.refs[tid] = spec_check.reference(entry["rec"], entry["fn"])
            self.shapes[tid] = arg_shapes(entry)
        return self.refs[tid]

    def exhausted(self, tid: int) -> str | None:
        if self.timeouts.get(tid, 0) >= self.max_timeouts:
            return f"reference did not finish: {self.max_timeouts} calls over {self.timeout_s}s CPU each"
        if self.spent.get(tid, 0.0) >= self.budget_s:
            return f"reference did not finish: over {self.budget_s:.0f}s CPU in all"
        return None

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
                started = time.process_time()
                result = run_reference(fn, native, self.timeout_s)
                self.spent[tid] = self.spent.get(tid, 0.0) + time.process_time() - started
                if result[0] == "timeout":
                    self.timeouts[tid] = self.timeouts.get(tid, 0) + 1
                elif result[0] == "ok":
                    self.ran[tid] = self.ran.get(tid, 0) + 1
        self.cache[key] = result
        return result

    def why_not_run(self, tid: int) -> str | None:
        """Why this reference produced no value at all, or None when it ran at least once."""
        if self.reference(tid) is None:
            return "reference does not load (no code, an import or syntax error, or the function is missing)"
        if self.ran.get(tid, 0):
            return None
        if self.timeouts.get(tid, 0):
            return f"reference did not finish within {self.timeout_s}s CPU on any input"
        if self.calls.get(tid, 0):
            return "reference raised on every input it was given"
        return "reference was never called"


# ------------------------------------------------------------------ pairs --

def pair_inputs(train_entry: dict, eval_entry: dict, train_draws: list, eval_draws: list) -> list[tuple[str, list, int]]:
    """Both problems' own inputs, then both problems' draws, as (tag, args, weight).

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
    weights: dict = {}
    order: list = []
    for args in list(train_draws) + list(eval_draws):
        key = canon(list(args))
        if key not in weights:
            weights[key] = 0
            order.append((key, args))
        weights[key] += 1
    out.extend(("draw", args, weights[key]) for key, args in order)
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


def compare_pair(runner: Runner, train_id: int, eval_id: int, inputs: list[tuple[str, list]]) -> dict:
    """One train problem against one held-out problem on a fixed list of inputs."""
    own_total = own_agreed = 0
    draws = draws_agreed = agreed = 0
    differences = one_sided = undefined = timeouts = 0
    both_raised = draws_refused_alike = 0
    answered = {train_id: 0, eval_id: 0}
    timed_out = {train_id: 0, eval_id: 0}
    witness = None
    for tag, args, weight in inputs:
        is_own = tag != "draw"
        if is_own:
            own_total += 1
        else:
            draws += weight
        results = {}
        for tid in (train_id, eval_id):
            if not is_own and timed_out[tid] >= PAIR_TIMEOUTS:
                # this reference has stopped answering this pair's draws; the
                # own inputs (at most 8 per problem) are always tried
                results[tid] = ("skipped",)
                continue
            results[tid] = runner.call(tid, args)
            if results[tid][0] == "timeout":
                timed_out[tid] += 1
        r_train, r_eval = results[train_id], results[eval_id]
        ok_train, ok_eval = r_train[0] == "ok", r_eval[0] == "ok"
        answered[train_id] += ok_train
        answered[eval_id] += ok_eval
        if r_train[0] in ("timeout", "skipped") or r_eval[0] in ("timeout", "skipped"):
            # An input a reference did not answer in time says nothing about
            # the function: not agreement, and not a difference either.
            timeouts += weight
            undefined += weight
            continue
        if ok_train and ok_eval:
            if r_train[1] == r_eval[1]:
                agreed += weight
                if is_own:
                    own_agreed += 1
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
        if witness is None or (is_own and witness["where"] == "draw"):
            witness = {"where": tag, "kind": kind, "input": _brief([render(a, None) for a in args]),
                       "train_said": _show(r_train[1]) if ok_train else r_train[0],
                       "eval_said": _show(r_eval[1]) if ok_eval else r_eval[0]}
    out = {"train_id": int(train_id), "eval_id": int(eval_id),
           "agreed_inputs": agreed, "own_inputs": own_total, "own_agreed": own_agreed,
           "draws": draws, "draws_agreed": draws_agreed, "draws_refused_alike": draws_refused_alike,
           "both_raised": both_raised, "differences": differences, "one_sided": one_sided,
           "undefined": undefined, "timeouts": timeouts,
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
    running a reference again."""
    if pair.get("fixed"):
        return pair["fixed"]                # "no reference", "cannot draw"
    if not pair["train_answered"] or not pair["eval_answered"]:
        return "not run"
    if pair["differences"] or pair["one_sided"]:
        return "different" if pair["difference"]["where"] != "draw" else "minimal pair"
    if (pair["own_agreed"] == pair["own_inputs"] > 0
            and pair["draws_agreed"] >= MIN_DRAWS_VALUED
            and pair["draws_agreed"] + pair["draws_refused_alike"] >= MIN_DRAWS_AGREED):
        return "duplicate"
    return "insufficient"


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
                            "draws": 0, "draws_agreed": 0, "draws_refused_alike": 0, "both_raised": 0,
                            "differences": 0, "one_sided": 0, "undefined": 0, "timeouts": 0,
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


def _worker_init(pool: dict, draws: dict, timeout_s: float, memory_bytes: int, known: dict | None = None):
    _WORKER["runner"] = Runner(pool, timeout_s=timeout_s)
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
             known_path: Path | None = None) -> dict:
    """Every held-out problem against every train problem of its signature; one JSONL line per held-out id.

    The progress file is the unit of resumption: a line already there for this
    pool version and split digest is not recomputed, so a run interrupted on a
    shared machine continues where it stopped. `known_path` names an earlier
    pool version's finished progress file whose pairs are copied, not rerun."""
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
                for key in ("pool", "split_sha256") + MEASUREMENT_KEYS:
                    if record.get(key) != header[key]:
                        raise SystemExit(f"REFUSED: {progress} was written for {key}={record.get(key)!r}, "
                                         f"this run has {header[key]!r}; use another progress file")
            elif record.get("kind") == "eval":
                done.add(int(record["eval_id"]))
    else:
        progress.parent.mkdir(parents=True, exist_ok=True)
        progress.write_text(json.dumps(header) + "\n", encoding="utf-8")
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
            with context.Pool(jobs, initializer=_worker_init, initargs=(pool, draws, timeout_s, memory_bytes, known),
                              maxtasksperchild=16) as workers:
                for result in workers.imap_unordered(_worker, tasks):
                    record(result)
        else:
            _worker_init(pool, draws, timeout_s, 0, known)
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


def build_policy(runs: list[dict], pools: dict[str, dict] | None = None, a2_policy: Path = A2_POLICY) -> dict:
    """The checked-in policy from one finished progress file per pool version."""
    a2 = json.loads(Path(a2_policy).read_text(encoding="utf-8"))
    a2_ids = {int(i) for i in a2["exclude_future_train_ids"]}
    per_pool: dict[str, dict] = {}
    duplicates: list[dict] = []
    minimal: list[dict] = []
    insufficient: list[dict] = []
    not_run: list[dict] = []
    by_train: dict[int, set[int]] = {}
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
                   "draws": pair["draws"], "draws_agreed": pair["draws_agreed"]}
            if pair["verdict"] == "duplicate":
                duplicates.append(row)
                by_train.setdefault(pair["train_id"], set()).add(pair["eval_id"])
                eval_with_twin.add(pair["eval_id"])
            elif pair["verdict"] == "minimal pair":
                row["difference"] = pair.get("difference")
                minimal.append(row)
            elif pair["verdict"] == "insufficient":
                row["undefined"] = pair["undefined"]
                insufficient.append(row)
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
    exclude = sorted(by_train)
    distinct = {"duplicate_pairs": len({(r["train_id"], r["eval_id"]) for r in duplicates}),
                "minimal_pairs": len({(r["train_id"], r["eval_id"]) for r in minimal}),
                "insufficient_pairs": len({(r["train_id"], r["eval_id"]) for r in insufficient}),
                "references_not_run": len({r["id"] for r in not_run})}
    return {
        "schema": SCHEMA,
        "about": ("Train problems whose reference solution computes the same function as a held-out problem's "
                  "(t/out/loop/split-v3.json eval ids, unchanged through split-v6) on both problems' own "
                  "assertion inputs and on drawn inputs. Human-readable report with examples: "
                  "t/DECONTAMINATION-BEHAVIOURAL-2026-09-25.md. Loaded by loop_filter.decontamination(), "
                  "which merges exclude_train_ids into the same-task exclusions of t/decontamination-2026-09-21.json."),
        "rule": {"text": RULE_TEXT, "seed": SEED, "draws_per_problem": DRAWS_PER_PROBLEM,
                 "draws_per_pair": 2 * DRAWS_PER_PROBLEM, "min_draws_agreed": MIN_DRAWS_AGREED,
                 "min_draws_valued": MIN_DRAWS_VALUED,
                 "timeout_s_cpu": TIMEOUT_S, "budget_s_cpu": BUDGET_S, "max_timeouts": MAX_TIMEOUTS,
                 "pair_timeouts": PAIR_TIMEOUTS,
                 "signature": "argument kinds and result kind of the first assertion",
                 "one_sided_raise": "a difference",
                 "timeout": "an input a reference did not answer in time is undefined: never agreement, never a difference",
                 "outputs_compared": "as t reads them (canon)",
                 "code": "t/behavioural_decontam.py"},
        "sources": list(SOURCES),
        "pools": per_pool,
        "distinct": distinct,               # the lists below are per pool, and pool v6 holds v5's pairs again
        "exclude_train_ids": exclude,
        "exclude_train_ids_by_eval": {str(tid): sorted(evals) for tid, evals in sorted(by_train.items())},
        "behavioural_overlap_eval_ids": sorted(eval_with_twin),
        "rediscovered_from_2026_09_21": sorted(a2_ids & set(exclude)),
        "new_exclusions": sorted(set(exclude) - a2_ids),
        "not_rediscovered_from_2026_09_21": sorted(a2_ids - set(exclude)),
        "duplicates": sorted(duplicates, key=lambda r: (r["pool"], r["train_id"], r["eval_id"])),
        "minimal_pairs": sorted(minimal, key=lambda r: (r["pool"], r["train_id"], r["eval_id"])),
        "insufficient_evidence": sorted(insufficient, key=lambda r: (r["pool"], r["train_id"], r["eval_id"])),
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
             "leaves every future corpus. Written by `t/behavioural_decontam.py`.", "",
             "## The rule", "", f"- {policy['rule']['text']}.",
             f"- Draws: {DRAWS_PER_PROBLEM} per problem with `spec_check.draw()` shaped like the problem's",
             f"  first example, seeded `{SEED}:<id>`, so a pair sees {2 * DRAWS_PER_PROBLEM} draws; a duplicate",
             f"  needs at least {MIN_DRAWS_AGREED} of them answered alike (equal values, or both references",
             f"  raising the same exception on that input) and at least {MIN_DRAWS_VALUED} equal values.",
             "- Signature kinds: the argument kinds and the result kind of the first assertion.",
             "- Outputs are compared as t reads them: a string is its code points, a",
             "  one-character string is that character, `true` is not `1`.",
             "- A pair that agrees on every own input and differs on a drawn one is a",
             "  MINIMAL PAIR, kept, and listed below; a pair that differs on an own input is",
             "  simply different and is not listed.",
             "- A reference that does not load, does not finish, or raises on every input is",
             "  reported by name and is never counted as agreeing.", "",
             "Prior art (fetched 2026-09-25): " + "; ".join(SOURCES) + ".", "",
             "What the rule cannot see: draws follow the example's shape, so two problems",
             "that differ only outside it (negative inputs, an unsorted sequence) count as",
             "duplicates here. That is the right side to err on for a corpus: the train",
             "problem's program passes the held-out problem's tests.", "",
             "## Counts", "", "| pool | split | held-out | train | pairs | duplicate | minimal pair | different | insufficient | not run or no reference | cannot draw | references not run |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for version, info in policy["pools"].items():
        v = info["verdicts"]
        lines.append(f"| {version} | `{info['split']}` `{info['split_sha256'][:12]}` | {info['eval_ids']} | {info['train_ids']} | "
                     f"{info['pairs']} | {v.get('duplicate', 0)} | {v.get('minimal pair', 0)} | {v.get('different', 0)} | "
                     f"{v.get('insufficient', 0)} | {v.get('not run', 0) + v.get('no reference', 0)} | {v.get('cannot draw', 0)} | "
                     f"{info['references_not_run']} |")
    excl = policy["exclude_train_ids"]
    lines += ["", f"**{len(excl)} train ids are excluded** from every future build: "
              + ", ".join(map(str, excl)) + ".", "",
              f"- Rediscovered from the 21 same-task exclusions of 2026-09-21: {len(policy['rediscovered_from_2026_09_21'])} "
              f"({', '.join(map(str, policy['rediscovered_from_2026_09_21'])) or 'none'}).",
              f"- New: {len(policy['new_exclusions'])} ({', '.join(map(str, policy['new_exclusions'])) or 'none'}).",
              f"- Held-out problems with a behavioural twin in training: {len(policy['behavioural_overlap_eval_ids'])} "
              f"({', '.join(map(str, policy['behavioural_overlap_eval_ids'])) or 'none'}). The 32 overlap ids of",
              "  2026-09-21 stay frozen; `score_heldout.py` can report these separately.", "",
              "## Ten duplicates", ""]
    shown = 0
    for row in policy["duplicates"]:
        if shown >= 10:
            break
        pool = (pools or {}).get(row["pool"])
        lines.append(f"{shown + 1}. train `{row['train']}` ({row['train_id']}): {_text(pool, row['train_id'])}")
        lines.append(f"   held-out `{row['eval']}` ({row['eval_id']}): {_text(pool, row['eval_id'])}")
        lines.append(f"   agreed on {row['agreed_inputs']} inputs ({row['own_inputs']} own, {row['draws_agreed']} of {row['draws']} draws), pool {row['pool']}")
        shown += 1
    if not shown:
        lines.append("(none)")
    distinct = policy["distinct"]
    lines += ["", f"Distinct over the pools (pool v6 holds every v5 pair again): {distinct['duplicate_pairs']} duplicate pairs, "
              f"{distinct['minimal_pairs']} minimal pairs, {distinct['insufficient_pairs']} pairs with insufficient evidence, "
              f"{distinct['references_not_run']} references that did not run.",
              "", "## Minimal pairs (kept)", "",
              f"{distinct['minimal_pairs']} distinct pairs agree on every own input and differ on a drawn one "
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
              "so every pair with them is 'not run', never a duplicate (each listed once, from the first pool that ran it):", ""]
    shown_ids: set = set()
    for entry in policy["references_not_run"]:
        if entry["id"] in shown_ids:
            continue
        shown_ids.add(entry["id"])
        if len(shown_ids) > 80:
            lines.append(f"- ... {distinct['references_not_run'] - 80} more in the JSON")
            break
        lines.append(f"- {entry['pool']} {entry['id']} `{entry['name']}`: {entry['why']}")
    lines += ["", "## Insufficient evidence", "",
              f"{distinct['insufficient_pairs']} distinct pairs never differed but fell short of the bar ({MIN_DRAWS_AGREED} draws "
              f"answered alike, {MIN_DRAWS_VALUED} with values, every own input agreed); they are "
              "listed in the JSON and not excluded.", "",
              "## Weak tests", "",
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
    policy = build_policy(runs, pools)
    Path(args.out).write_text(json.dumps(policy, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    notes = Path(args.notes).read_text(encoding="utf-8") if args.notes else ""
    write_report(policy, runs, pools, Path(args.report), notes)
    d = policy["distinct"]
    print(f"wrote {args.out}: {len(policy['exclude_train_ids'])} excluded "
          f"({len(policy['rediscovered_from_2026_09_21'])} rediscovered, {len(policy['new_exclusions'])} new), "
          f"{d['duplicate_pairs']} duplicate pairs, {d['minimal_pairs']} minimal pairs, "
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
    write = sub.add_parser("write", help="the policy file and report from finished progress files")
    write.add_argument("--from", dest="from_progress", nargs="+", required=True)
    write.add_argument("--out", required=True)
    write.add_argument("--report", required=True)
    write.add_argument("--no-pools", action="store_true", help="names and texts left out (no pool data here)")
    write.add_argument("--notes", default="", help="a markdown file appended to the report as the hand-written reading")
    args = ap.parse_args(argv)
    if args.cmd == "run":
        result = run_pool(args.pool, Path(args.split), Path(args.progress), jobs=args.jobs, timeout_s=args.timeout,
                          memory_bytes=int(args.memory_gb * (1 << 30)),
                          known_path=Path(args.known) if args.known else None)
        print(f"done in {result['seconds']}s: {result['progress']}")
        return 0
    if args.cmd == "write":
        return cmd_write(args)
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
