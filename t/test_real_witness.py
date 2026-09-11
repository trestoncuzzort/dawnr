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

import fuzz_lower                    # noqa: E402
import harness                       # noqa: E402
import interp                        # noqa: E402
import tlib                          # noqa: E402
from fuzz_lower import AT, I, IFS, OP, V, ASG  # noqa: E402
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


@test
def test_ensures_undefined_probes_name_the_site_and_expr():
    """ROADMAP 13.4, the harness column, 2026-09-12: fz_p_at_oob, fz_p_at_neg,
    fz_p_at_zero and fz_p_attotal all have a real body that is defined at
    every input (an if/else assigning r, no `at` in the body at all) but an
    `ensures` containing an unguarded `at` past the sequence -- the shape
    the ensures-level undefined witness exists for. Each must come back
    `_kind` "undefined", `_site` "ensures", carrying `_expr` (the offending
    `at` node) and no `_twin` -- distinct from the body-level undefined
    witness (`_twin` present, no `_site`/`_expr`), which is what
    fz_p_at_body (an unguarded `at` IN the body) must still produce, so the
    two shapes are checked side by side here."""
    probes = {t["name"]: t for t in fuzz_lower.probes()
             if t["name"] in ("fz_p_at_oob", "fz_p_at_neg", "fz_p_at_zero",
                              "fz_p_attotal", "fz_p_at_body")}
    assert len(probes) == 5, sorted(probes)
    for name in ("fz_p_at_oob", "fz_p_at_neg", "fz_p_at_zero", "fz_p_attotal"):
        w = harness.real_witness(probes[name])
        assert w is not None, name
        assert w.get("_kind") == "undefined", (name, w)
        assert w.get("_site") == "ensures", (name, w)
        assert isinstance(w.get("_expr"), dict) and "op" in w["_expr"], (name, w)
        assert "_twin" not in w, (name, w)
        assert w.get("_real") == "no value", (name, w)
    w = harness.real_witness(probes["fz_p_at_body"])
    assert w is not None, "fz_p_at_body"
    assert w.get("_kind") == "undefined", w
    assert "_twin" in w, ("fz_p_at_body should stay body-kind", w)
    assert "_site" not in w and "_expr" not in w, (
        "fz_p_at_body is a BODY-level undefined witness, not ensures-level", w)


@test
def test_hand_built_ensures_undefined_task():
    """A task shaped nothing like the `at`-based probes above: `div` by a
    denominator that is always zero (x - x), written directly into
    `ensures` and never guarded by `requires`. The body is total (r := x,
    defined at every x), so this is squarely the ensures-only case."""
    task = {"t": 1, "name": "test_ensures_div0",
           "params": [{"name": "x", "type": "int"}],
           "returns": [{"name": "r", "type": "int"}], "requires": [],
           "ensures": [OP("==",
                          OP("div", V("x"), OP("-", V("x"), V("x"))),
                          I(0))],
           "body": [ASG("r", V("x"))]}
    w = harness.real_witness(task)
    assert w is not None
    assert w.get("_kind") == "undefined", w
    assert w.get("_site") == "ensures", w
    assert w.get("_expr", {}).get("op") == "div", w
    assert "_twin" not in w, w


@test
def test_hand_built_guarded_at_in_ensures_does_not_trigger():
    """The negative case the ensures-level witness must NOT fire on: `at`
    appears in `ensures`, but `requires len(s) > 0` makes it defined at
    every input the scan ever reaches, and the body computes the same
    value, so the task is correct end to end and real_witness must be
    None."""
    task = {"t": 1, "name": "test_ensures_guarded_at",
           "params": [{"name": "s", "type": "seq"}],
           "returns": [{"name": "r", "type": "int"}],
           "requires": [OP(">", OP("len", V("s")), I(0))],
           "ensures": [OP("==", V("r"), AT("s", I(0)))],
           "body": [ASG("r", AT("s", I(0)))]}
    w = harness.real_witness(task)
    assert w is None, w


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
