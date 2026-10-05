#!/usr/bin/env python3
"""t/spec_quality.py -- is a specification the problem's, judged from the problem's own tests alone
(2026-10-01).

    python3 t/spec_quality.py TAG [TAG ...] [--pool v5]      # every task-stage answer of the sets

SAFE's two scores for a synthesized specification (arXiv:2410.15756, section 3.2, read from the
HTML): Correctness is the share of the problem's test cases (i, o) for which S(i, o) holds, and
Completeness the share of MUTATED cases (i, o') it rejects; SAFE keeps a specification at 80% and
60% and up to three a function. The idea is Lahiri's (arXiv:2406.09757), and nl2postcond
(arXiv:2310.01831) calls the first test-set correctness. Neither score needs a reference
solution, which is what makes them usable when a person asks a question: t/spec_check.py needs
the problem's solution and is an evaluation instrument only.

Here S(i, o) is the task's `requires` and `ensures` evaluated by the interpreter on a test's
arguments and expected result (a test outside the `requires` says nothing and is not counted),
and the mutants are t/spec_check.mutations of the expected result, the ones the reference check
has always used.

Measured on 1,600 stored answers that have a reference verdict (2026-10-01): of 1,084 the two
thresholds keep, 875 agree with the reference (81%); of 443 dropped for correctness, 425
disagree (96%).
"""
from __future__ import annotations

import argparse
import contextlib
import json
import signal
import sys
import threading
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness                                                  # noqa: E402
import interp                                                   # noqa: E402
import spec_check                                               # noqa: E402
import spec_experiment as se                                    # noqa: E402

MIN_CORRECTNESS, MIN_COMPLETENESS = 0.8, 0.6                    # SAFE's thresholds
# Wall clocks (2026-10-04). The interpreter bounds steps (MAX_STEPS) and sizes (MAX_BITS, MAX_SEQ), not time, and
# teacher3 seed 1's specification stage ran 77 minutes on one problem before the kernel killed it. A Python signal
# handler runs at the next bytecode of the main thread (docs.python.org/3/library/signal.html), so with every
# sequence operation capped the timer can interrupt between steps. Off the main thread, no limit. EVAL_SECONDS bounds
# one evaluation (a normal one takes milliseconds); SPEC_SECONDS bounds one specification's whole scoring, past which it
# is unscorable: with only the first, one slow specification was evaluated on every test and every mutant at up to
# 60 s each and ran 25 minutes without an answer (seed 1's second run).
EVAL_SECONDS = 10
SPEC_SECONDS = 120


class Overtime(Exception):
    """An evaluation that ran past EVAL_SECONDS: decides nothing, like interp.Budget."""


@contextlib.contextmanager
def time_limit(seconds: float):
    if threading.current_thread() is not threading.main_thread() or not hasattr(signal, "setitimer"):
        yield
        return

    def _raise(signum, frame):
        raise Overtime(f"over {seconds} s")
    old = signal.signal(signal.SIGALRM, _raise)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


_SKIP = (interp.Undef, interp.Budget, RecursionError, ZeroDivisionError, Overtime)


def scores(task: dict, entry: dict) -> dict:
    """{"correctness", "completeness", "tests", "mutants"} or {"unscorable": why}."""
    try:
        funs = interp.funs_of(task, task.get("body", []))
    except Exception as e:                                      # noqa: BLE001
        return {"unscorable": f"{type(e).__name__}: {e}"[:120]}
    ret = task["returns"][0]["name"]
    held = tests = rejected = mutants = 0
    t_end = time.monotonic() + SPEC_SECONDS

    def clock() -> float:
        return min(EVAL_SECONDS, t_end - time.monotonic())
    for point in entry["points"]:
        env, refusal = se.bind_point(task, point)
        if refusal is not None:
            return {"unscorable": refusal["why"]}
        kind, value = se.expected_value(task, point)
        env[ret] = se._as_interp_value(kind, value)
        if clock() <= 0:
            return {"unscorable": f"scoring over {SPEC_SECONDS} s"}
        st = interp.St()
        try:
            with time_limit(clock()):
                if not all(interp.ev(c, env, funs, st) for c in task.get("requires", [])):
                    continue                                    # outside the precondition: says nothing
                ok = all(interp.ev(e, env, funs, st) is True for e in task.get("ensures", []))
        except _SKIP:
            ok = False                                          # undefined on the right answer is not holding
        except Exception as e:                                  # noqa: BLE001
            return {"unscorable": f"{type(e).__name__}: {e}"[:120]}
        tests += 1
        held += ok
        for wrong in spec_check.mutations(env[ret]):
            probe = dict(env)
            probe[ret] = wrong
            if clock() <= 0:
                return {"unscorable": f"scoring over {SPEC_SECONDS} s"}
            st2 = interp.St()
            try:
                with time_limit(clock()):
                    accepts = all(interp.ev(e, probe, funs, st2) is True for e in task.get("ensures", []))
            except Exception:                                   # noqa: BLE001  (undefined on a wrong answer rejects it)
                accepts = False
            mutants += 1
            rejected += not accepts
    if tests == 0:
        return {"unscorable": "no test inside the requires"}
    return {"correctness": held / tests, "completeness": (rejected / mutants) if mutants else None,
            "tests": tests, "mutants": mutants}


def keeps(s: dict, min_correctness: float = MIN_CORRECTNESS, min_completeness: float = MIN_COMPLETENESS) -> bool:
    """SAFE's rule. A specification with no mutant to reject is not kept: nothing showed it says anything."""
    return ("unscorable" not in s and s["correctness"] >= min_correctness
            and s["completeness"] is not None and s["completeness"] >= min_completeness)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tags", nargs="+")
    ap.add_argument("--pool", choices=se.POOL_VERSIONS, default="v5")
    ap.add_argument("--json", type=Path)
    a = ap.parse_args(argv)
    pool = {str(k): v for k, v in se.pool(a.pool).items()}
    out, tally = {}, Counter()
    for tag in a.tags:
        d = se.outdir(tag)
        try:
            ext = json.loads((d / "extract.json").read_text(encoding="utf-8"))
        except OSError:
            continue
        for tid, e in ext.items():
            if e.get("stage") != "task" or tid not in pool:
                continue
            s = scores(harness.load(d / "tasks" / f"{e['name']}.json"), pool[tid])
            s["kept"] = keeps(s)
            out[f"{tag}/{e['name']}"] = s
            tally["kept" if s["kept"] else "unscorable" if "unscorable" in s else "dropped"] += 1
    print(f"{sum(tally.values())} specifications scored on their problem's own tests: " +
          ", ".join(f"{v} {k}" for k, v in tally.most_common()))
    if a.json:
        a.json.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
