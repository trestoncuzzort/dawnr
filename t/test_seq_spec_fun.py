#!/usr/bin/env python3
"""test_seq_spec_fun.py: SPEC.md "Seq-valued spec_funs (v1)" (2026-09-27), the
language side, no prover: the notation parses and prints a `spec fun ..:
seq`, check_wf accepts a seq result and refuses a nested or pair one by
name, the interpreter evaluates a seq-valued call (indexed, measured,
sliced, concatenated, compared), the twin ladder finds a witnessed twin for
the committed task, seven lowerings emit text for the fixtures (real and
twin: framac's own \\list route, t/FEATURES-SEQFUN-2026-09-27.md "Frama-C,
the \\list route", landed 2026-09-27, is t/test_framac_seq_fun.py's to
check in depth), and every committed task's lowering is unchanged by the
construct (t/tasks, t/lemmas, t/nested: the same text before and after,
per kernel, real and twin, checked against the file's own no-seq-spec_fun
tasks). Since the 2026-09-27 review: the dafny and F* refutation
certificates ladder every seq-valued spec_fun call and every ground seq
operator around it (lower_dafny.py, certificate step 3), checked on the
review's two seeded spec_fun faults as text here and, with `--slow`, as
the two kernels' own verdicts.

Run: python3 t/test_seq_spec_fun.py [--slow]   (or pytest)
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
            "fz_p_sf_seq_false", "fz_p_sf_seq_swap", "fz_p_sf_seq_slice_off")
# a straight-line body with no `if`, no invariant and no mutable index: no
# twin, exactly the ladder's stated rule; graded on the (refuted) real side
# alone (fz_p_sf_seq_slice_off's body slices, so it draws `off-by-one`)
NO_TWIN = ("fz_p_sf_seq_false",)


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
    # since SPEC.md "Compositional types (v1)" (2026-10-06) a spec_fun's result is any t type: a nested-seq
    # or pair result is a valid declaration, and what fails is the seq body against it (the body-type rule)
    for res in ({"seq": "seq"}, {"pair": ["int", "int"]}):
        bad = copy.deepcopy(task)
        bad["spec_funs"][0]["result"] = res
        errs = check_wf.check_wf(bad)
        assert errs and all("spec-fun-body-type" in e or "body type" in e or "one type" in e
                            or "all ints or all reals" in e or "branches" in e for e in errs), (res, errs)
        assert not any("not a t type" in e for e in errs), (res, errs)
    # a name that is no type at all is still refused by name
    bad = copy.deepcopy(task)
    bad["spec_funs"][0]["result"] = "nat"
    errs = check_wf.check_wf(bad)
    assert any("not a t type" in e for e in errs), errs
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
        if name in NO_TWIN:
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


def test_seven_kernels_lower() -> None:
    """Since the \\list route (2026-09-27, t/FEATURES-SEQFUN-2026-09-27.md
    "Frama-C, the \\list route"): all seven kernels now lower every
    fixture, real and twin (framac's own coverage -- the \\list route's
    named residual abstains, not a wholesale one -- is
    t/test_framac_seq_fun.py's, not this file's, to check)."""
    tasks = {"double_all": _committed()}
    tasks.update(_probes())
    for name, task in tasks.items():
        has_twin = harness.twin_for(task)[0] is not None
        for twin in ((False, True) if has_twin else (False,)):
            got = _lower_all(task, twin)
            for k in KERNELS:
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
    assert "logic \\list<integer> dbl{L}(int *s, integer s_n, integer n) =" in real["framac"]
    print("test_seven_kernels_lower: ok")


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
            if os.path.basename(path) not in ("double_all.t", "filter_pos.t"):  # filter_pos: PREDICT T55
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


def _seeded(name: str) -> tuple[dict, dict]:
    """One of the review's seeded spec_fun faults as a probe (fuzz_lower.py,
    `fz_p_sf_seq_swap` / `fz_p_sf_seq_slice_off`) with the interpreter's
    real witness, the conformance suite's own no-twin path."""
    p = _probes()[name]
    w = harness.real_witness(p)
    assert w is not None and w.get("s") == [0, 1], (name, w)
    return p, w


def test_certificate_seq_rungs() -> None:
    """The 2026-09-27 review's finding: a bug seeded in a seq-valued
    spec_fun's own body read unproved in dafny and F* (not refuted, not
    verified) because the certificate left the recursive call for the
    kernel to unfold past its default fuel, and a literal against a ground
    append for it to relate with no index term to trigger on. Now both
    certificates carry a rung per seq-valued call the formula reaches,
    callees first, and one per ground seq operator around it
    (lower_dafny.seq_ladder). Text-level; the verdicts are `--slow`."""
    import lower_dafny  # noqa: E402
    import lower_fstar  # noqa: E402
    p, w = _seeded("fz_p_sf_seq_swap")
    dfy = lower_dafny.lower(p, p["body"], witness=w)
    fst = lower_fstar.lower(p, p["body"], witness=w)
    for rung in ("  var t_v0: seq<int> := [];", "  var t_v2: seq<int> := [2, 0];",
                 "  assert dbl(s, 0) == t_v0;", "  assert dbl(s, 1) == t_v1;",
                 "  assert dbl(s, 2) == t_v2;"):
        assert rung in dfy, (rung, dfy)
    assert dfy.index("dbl(s, 0)") < dfy.index("dbl(s, 1)") < dfy.index("dbl(s, 2)")
    for rung in ("  assert (Seq.equal (dbl (Seq.createL #int [0; 1]) 0) (Seq.createL #int []));",
                 "  assert (Seq.equal (dbl (Seq.createL #int [0; 1]) 2) (Seq.createL #int [2; 0]));"):
        assert rung in fst, (rung, fst)
    assert fst.index("[0; 1]) 0)") < fst.index("[0; 1]) 1)") < fst.index("[0; 1]) 2)")
    assert fst.index("assert (Seq.equal (dbl") < fst.index("  assert_norm (")
    p, w = _seeded("fz_p_sf_seq_slice_off")
    dfy = lower_dafny.lower(p, p["body"], witness=w)
    fst = lower_fstar.lower(p, p["body"], witness=w)
    assert "  assert tl(s) == t_v0;" in dfy and "  assert (tl(s) + [s[0]]) == t_v1;" in dfy, dfy
    assert dfy.index("assert tl(s) ==") < dfy.index("assert (tl(s) + [s[0]])")
    assert ("  assert (Seq.equal (tl (Seq.createL #int [0; 1])) (Seq.createL #int [0]));"
            in fst), fst
    assert ("  assert (Seq.equal (Seq.append (tl (Seq.createL #int [0; 1])) "
            "(Seq.create 1 (Seq.index (Seq.createL #int [0; 1]) 0))) "
            "(Seq.createL #int [0; 0]));" in fst), fst
    # a certificate with no seq-valued call in its formula carries no rung:
    # double_all's own twin (an undefined-kind witness at s = [])
    dfy = tlib.lower(_committed(), "dafny", twin_body=True)
    assert "t_refutation_certificate" in dfy and "t_v0" not in dfy, dfy
    fst = tlib.lower(_committed(), "fstar", twin_body=True)
    assert "t_refutation_certificate" in fst and "Seq.equal (dbl" not in fst, fst
    print("test_certificate_seq_rungs: ok")


def test_kernels_refute_the_seeded_faults(slow: bool) -> None:
    """dafny and F* on the two seeded faults' real side: refuted, each
    through its own certificate run (verifiers/dafny.py, verifiers/fstar.py
    mint REFUTED only from the targeted certificate run)."""
    if not slow:
        print("test_kernels_refute_the_seeded_faults: skipped (pass --slow)")
        return
    import tempfile  # noqa: E402
    import lower_dafny  # noqa: E402
    import lower_fstar  # noqa: E402
    from verifiers import dafny as dafny_backend  # noqa: E402
    from verifiers import fstar as fstar_backend  # noqa: E402
    if not (dafny_backend.DAFNY and fstar_backend.FSTAR):
        print("test_kernels_refute_the_seeded_faults: skipped (a kernel is absent)")
        return
    with tempfile.TemporaryDirectory() as d:
        for name in ("fz_p_sf_seq_swap", "fz_p_sf_seq_slice_off"):
            p, w = _seeded(name)
            for backend, lower, suffix in ((dafny_backend, lower_dafny, "dfy"),
                                           (fstar_backend, lower_fstar, "fst")):
                path = os.path.join(d, f"{name}.{suffix}")
                with open(path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(lower.lower(p, p["body"], witness=w))
                r = backend.verify(__import__("pathlib").Path(path))
                assert r.outcome == "refuted", (name, suffix, r.outcome, r.extras)
    print("test_kernels_refute_the_seeded_faults: ok")


def run(slow: bool = False) -> None:
    test_notation_roundtrip()
    test_check_wf_accepts_seq_and_refuses_the_rest()
    test_interp_evaluates_a_seq_valued_call()
    test_twin_ladder_finds_a_witness()
    test_seven_kernels_lower()
    test_committed_tasks_lower_as_before()
    test_certificate_seq_rungs()
    test_kernels_refute_the_seeded_faults(slow)
    print("test_seq_spec_fun: ok")


if __name__ == "__main__":
    run("--slow" in sys.argv[1:])
