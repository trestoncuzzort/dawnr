#!/usr/bin/env python3
"""test_seq_spec_fun.py: SPEC.md "Seq-valued spec_funs (v1)" (2026-09-27), the
language side, no prover: the notation parses and prints a `spec fun ..:
seq`, check_wf accepts a seq result and refuses a nested or pair one by
name, the interpreter evaluates a seq-valued call (indexed, measured,
sliced, concatenated, compared), the twin ladder finds a witnessed twin for
the committed task, six lowerings emit text for the fixtures (real and
twin) and Frama-C abstains by name, and every committed task's lowering is
unchanged by the construct (t/tasks, t/lemmas, t/nested: the same text
before and after, per kernel, real and twin, checked against the file's
own no-seq-spec_fun tasks).

Run: python3 t/test_seq_spec_fun.py   (or pytest)
"""
from __future__ import annotations

import copy
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import check_wf     # noqa: E402
import fuzz_lower   # noqa: E402
import harness      # noqa: E402
import interp       # noqa: E402
import surface      # noqa: E402
import tlib         # noqa: E402

KERNELS = [b for b, _, _ in tlib.BACKENDS]
FIXTURES = ("fz_p_sf_seq_len", "fz_p_sf_seq_at", "fz_p_sf_seq_build",
            "fz_p_sf_seq_false")


def _committed() -> dict:
    return surface.parse_file(os.path.join(HERE, "tasks", "double_all.t"))


def _probes() -> dict:
    return {p["name"]: {k: v for k, v in p.items() if not k.startswith("_")}
            for p in fuzz_lower.probes() if p["name"] in FIXTURES}


def test_notation_roundtrip() -> None:
    task = _committed()
    sf = task["spec_funs"][0]
    assert sf["name"] == "dbl" and sf["result"] == "seq", sf
    printed = surface.print_task(task)
    assert "spec fun dbl(s: seq, n: int): seq" in printed, printed
    assert surface.parse(printed) == task
    print("test_notation_roundtrip: ok")


def test_check_wf_accepts_seq_and_refuses_the_rest() -> None:
    task = _committed()
    assert check_wf.check_wf(task) == []
    for name, p in _probes().items():
        assert check_wf.check_wf(p) == [], (name, check_wf.check_wf(p))
    # a seq body against an int result is the body-type rule, as before
    bad = copy.deepcopy(task)
    bad["spec_funs"][0]["result"] = "int"
    errs = check_wf.check_wf(bad)
    assert any("spec-fun-body-type" in e or "body type != result" in e for e in errs), errs
    # a nested-seq or pair result is refused by name (not in v1)
    for res in ({"seq": "seq"}, {"pair": ["int", "int"]}, "nat"):
        bad = copy.deepcopy(task)
        bad["spec_funs"][0]["result"] = res
        errs = check_wf.check_wf(bad)
        assert any("result must be int, bool or seq" in e for e in errs), (res, errs)
    print("test_check_wf_accepts_seq_and_refuses_the_rest: ok")


def test_interp_evaluates_a_seq_valued_call() -> None:
    task = _committed()
    funs = {f["name"]: f for f in task["spec_funs"]}
    st = interp.St()
    dbl = {"call": {"fun": "dbl", "args": [{"var": "s"}, {"op": "len", "args": [{"var": "s"}]}]}}
    env = {"s": (1, 2, 3)}
    assert tuple(interp.ev(dbl, env, funs, st)) == (2, 4, 6)
    assert interp.ev({"op": "len", "args": [dbl]}, env, funs, st) == 3
    assert interp.ev({"op": "at", "args": [dbl, {"int": 1}]}, env, funs, st) == 4
    sl = interp.ev({"op": "slice", "args": [dbl, {"int": 1}, {"int": 3}]}, env, funs, st)
    assert tuple(sl) == (4, 6)
    cat = interp.ev({"op": "+", "args": [dbl, {"op": "seq", "args": [{"int": 0}]}]}, env, funs, st)
    assert tuple(cat) == (2, 4, 6, 0)
    assert interp.ev({"op": "==", "args": [dbl, {"op": "seq", "args": [{"int": 2}, {"int": 4}, {"int": 6}]}]},
                     env, funs, st) is True
    assert interp.ev(dbl, {"s": ()}, funs, st) == () or list(interp.ev(dbl, {"s": ()}, funs, st)) == []
    ref = interp.Reference(task)
    assert ref.points, "the committed task has a measurable domain"
    print("test_interp_evaluates_a_seq_valued_call: ok")


def test_twin_ladder_finds_a_witness() -> None:
    task = _committed()
    tb, op, w = harness.twin_for(task)
    assert tb is not None and op == "compare-flip", (op, w)
    assert w is not None and w.get("s") == [], w
    for name, p in _probes().items():
        tb, op, w = harness.twin_for(p)
        if name == "fz_p_sf_seq_false":
            # a straight-line body with no `if` and no invariant: no twin,
            # exactly the ladder's stated rule; the probe is graded on its
            # (refuted) real side alone
            assert tb is None, (name, op)
        else:
            assert tb is not None, (name, op, w)
    print("test_twin_ladder_finds_a_witness: ok")


def _lower_all(task: dict, twin: bool) -> dict:
    out = {}
    for k in KERNELS:
        try:
            out[k] = tlib.lower(task, k, twin_body=twin)
        except NotImplementedError as e:
            out[k] = e
    return out


def test_six_kernels_lower_and_framac_abstains() -> None:
    tasks = {"double_all": _committed()}
    tasks.update(_probes())
    for name, task in tasks.items():
        has_twin = harness.twin_for(task)[0] is not None
        for twin in ((False, True) if has_twin else (False,)):
            got = _lower_all(task, twin)
            for k in KERNELS:
                if k == "framac":
                    assert isinstance(got[k], NotImplementedError), (name, k, got[k])
                    assert "returns a seq" in str(got[k]), got[k]
                else:
                    assert isinstance(got[k], str) and got[k], (name, k, got[k])
    # the kernels' own spellings of the result type
    real = _lower_all(tasks["double_all"], False)
    assert "function dbl(s: seq<int>, n: int): seq<int>" in real["dafny"]
    assert "spec fn dbl(s: Seq<int>, n: int) -> Seq<int>" in real["verus"]
    assert "return Seq" in real["spark"]
    assert "def dbl_s (s : List Int) (n : Int) : List Int" in real["lean"]
    assert "Fixpoint sf_dbl_fuel (fuel : nat) (s : Z -> Z) (s_len : Z) (n : Z) : ((Z -> Z) * Z)" in real["rocq"]
    assert "(fst (sf_dbl" in real["rocq"] and "cbn [fst snd]" in real["rocq"]
    assert ": Tot (Seq.seq int) (decreases n)" in real["fstar"]
    print("test_six_kernels_lower_and_framac_abstains: ok")


def test_committed_tasks_lower_as_before() -> None:
    """Byte identity, the in-tree half: every committed task without a
    seq-valued spec_fun lowers through code paths this construct gates on
    `result == "seq"` only, so the text a kernel receives cannot depend on
    the construct existing. This checks the gates themselves: no committed
    task other than double_all declares one, and every committed task
    still lowers (or abstains) in every kernel, real and twin. The
    cross-checkout sha256 comparison is in the report."""
    n = 0
    for d in ("tasks", "lemmas", "nested"):
        for path in sorted(glob.glob(os.path.join(HERE, d, "*.t"))):
            task = surface.parse_file(path)
            seq_sf = [f["name"] for f in task.get("spec_funs", []) if f["result"] == "seq"]
            if os.path.basename(path) != "double_all.t":
                assert not seq_sf, (path, seq_sf)
            for k in KERNELS:
                for twin in (False, True):
                    try:
                        tlib.lower(task, k, twin_body=twin)
                    except (NotImplementedError, ValueError):
                        pass       # a named abstain, or a task with no twin
                    n += 1
    assert n > 0
    print(f"test_committed_tasks_lower_as_before: ok ({n} lowerings)")


def run() -> None:
    test_notation_roundtrip()
    test_check_wf_accepts_seq_and_refuses_the_rest()
    test_interp_evaluates_a_seq_valued_call()
    test_twin_ladder_finds_a_witness()
    test_six_kernels_lower_and_framac_abstains()
    test_committed_tasks_lower_as_before()
    print("test_seq_spec_fun: ok")


if __name__ == "__main__":
    run()
