"""Plain-python tests for harness.real_witness (ROADMAP 15.5): the interpreter's
bounded search for an input on which a REAL body -- not a twin -- violates its
own `ensures`, or is undefined where `requires` admits the input. Three
things are measured here:

  1. real_witness(task) is None for EVERY committed task under t/tasks/*.t:
     the 34 tasks are all correct, so the scan must find nothing on any of
     them. This is the guard against the risk named in the task: nothing
     committed should move.
  2. real_witness(task) is NOT None on the three hand-written wrong examples
     under t/editors/examples/ (wrong_abs, wrong_sum_upto, wrong_last), and
     the witness it returns genuinely violates `ensures` under interp.py
     (re-checked here independently of harness.real_witness's own internal
     use of interp._breaks_ensures, by re-running the body and `ensures`
     directly).
  3. wrong_abs.t, run through tlib.verify(kernels=["dafny"]), reads
     real=REFUTED: the bar ROADMAP 15.5 names ("a real task REFUTED with
     the kernel's message") measured end to end, not merely at the
     interpreter.

Requires dafny on PATH for check 3 only; checks 1 and 2 run regardless.
No network. Run as: cd <repo>/t && python3 test_real_witness.py
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import harness                       # noqa: E402
import interp                        # noqa: E402
import tlib                          # noqa: E402
from verifiers import Outcome        # noqa: E402
from verifiers import dafny as dafny_backend  # noqa: E402

UNIT_TESTS = []


def test(fn):
    UNIT_TESTS.append(fn)
    return fn


def _dafny_available() -> bool:
    try:
        dafny_backend.version()
        return True
    except (Exception, SystemExit):                          # noqa: BLE001
        return False


def _confirms_violation(task: dict, w: dict) -> bool:
    """Independent re-check, using interp.py directly rather than trusting
    harness.real_witness's own bookkeeping: does the witness input, run
    through the REAL body, actually produce a value that violates `ensures`
    (or does the body itself raise Undef, for an "undefined"-kind witness)?"""
    funs = interp.funs_of(task, task["body"])
    ret = task["returns"][0]["name"]
    env0 = {n: (tuple(v) if isinstance(v, list) else v)
           for n, v in w.items() if not n.startswith("_")}
    st = interp.St()
    env = dict(env0)
    env[ret] = None
    try:
        interp.exec_body(task["body"], env, funs, st)
    except interp.Undef:
        return w.get("_kind") == "undefined"
    got = env[ret]
    if got is None:
        return False
    post = dict(env0)
    post[ret] = got
    try:
        for c in task["ensures"]:
            if not interp.ev(c, post, funs, st):
                return True
        return False
    except interp.Undef:
        return True


@test
def test_no_committed_task_has_a_real_witness():
    paths = sorted((HERE / "tasks").glob("*.t"))
    assert len(paths) >= 30, f"expected the committed corpus, found {len(paths)}"
    bad = []
    for p in paths:
        task = harness.load(p)
        w = harness.real_witness(task)
        if w is not None:
            bad.append((p.name, w))
    assert not bad, f"real_witness found a defect in committed tasks: {bad}"


@test
def test_wrong_examples_have_a_confirmed_real_witness():
    names = ("wrong_abs", "wrong_sum_upto", "wrong_last")
    for name in names:
        p = HERE / "editors" / "examples" / f"{name}.t"
        assert p.exists(), f"missing example {p}"
        task = harness.load(p)
        w = harness.real_witness(task)
        assert w is not None, f"{name}: real_witness found nothing"
        assert _confirms_violation(task, w), (name, w)


@test
def test_wrong_abs_reads_refuted_through_tlib():
    if not _dafny_available():
        print("  (dafny not on PATH, skipping test_wrong_abs_reads_refuted_through_tlib)")
        return
    task = harness.load(HERE / "editors" / "examples" / "wrong_abs.t")
    verdict = tlib.verify(task, kernels=["dafny"])
    entry = verdict["dafny"]
    assert entry.get("real") == Outcome.REFUTED, (
        f"wrong_abs real should be REFUTED with the certificate's message, "
        f"got {entry}")
    assert entry.get("real_witness", "none") != "none", entry


def run() -> None:
    failures = 0
    for fn in UNIT_TESTS:
        try:
            fn()
            print(f"{fn.__name__}: pass")
        except AssertionError as e:
            failures += 1
            print(f"{fn.__name__}: FAILED: {e}")
        except Exception as e:                                  # noqa: BLE001
            failures += 1
            traceback.print_exc()
            print(f"{fn.__name__}: FAILED (exception): {e}")
    if failures:
        raise AssertionError(f"{failures} of {len(UNIT_TESTS)} test(s) failed")
    print(f"test_real_witness: all {len(UNIT_TESTS)} checks passed")


if __name__ == "__main__":
    run()
