#!/usr/bin/env python3
"""test_lower_lean_methods.py: SPEC.md "Methods (v1)" in the Lean lowering.

Each method is lowered as a task of its own (its `{m}_t` def and
`{m}_t_spec` theorem, through the same shape dispatch a task gets), then
made irreducible and handed to grind by `grind_pattern`; a call site owes
the callee's requires as a definedness obligation and knows only the
callee's spec theorem (Dafny's modular call rule). Shapes lower_lean.py
cannot express raise NotImplementedError with a named reason. Kernel
verdicts are measured separately (t/FEATURES-TRACK.md); this file runs no
prover.

Run: python3 t/test_lower_lean_methods.py   (or pytest)
"""

from __future__ import annotations

import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import harness                                                 # noqa: E402
import surface                                                 # noqa: E402
from lower_lean import lower                                   # noqa: E402
from verifiers.lean import BANNED                              # noqa: E402

FIXTURES = sorted(glob.glob(os.path.join(HERE, "methods", "*.t")))
PROBE = os.path.join(HERE, "methods_probe", "opaque_callee.t")


def _load(path: str) -> dict:
    return surface.parse_file(path)


def _fixture(name: str) -> dict:
    return _load(os.path.join(HERE, "methods", name + ".t"))


def _clean(src: str) -> None:
    assert not BANNED.search(src), BANNED.findall(src)


def test_every_fixture_lowers_real_and_twin() -> None:
    assert len(FIXTURES) >= 4, FIXTURES
    for f in FIXTURES + [PROBE]:
        t = _load(f)
        src = lower(t, t["body"])
        _clean(src)
        for m in t["methods"]:
            name = m["name"] + "_t"
            # the method comes before the task, with its own contract,
            # made opaque and given to grind as its contract only
            assert src.index(f"def {name} ") < src.index(
                f"def {t['name']}_t "), (f, name)
            assert f"theorem {name}_spec " in src, (f, name)
            assert f"#print axioms {name}_spec" in src, (f, name)
            pnames = " ".join(p["name"] for p in m["params"])
            assert f"grind_pattern {name}_spec => {name} {pnames}\n" \
                in src, (f, name)
            assert f"attribute [irreducible] {name}\n" in src, (f, name)
        body, _op, w = harness.twin_for(t)
        _clean(lower(t, body, w))


def test_call_sites_use_the_callee_function_only() -> None:
    t = _fixture("max3")
    src = lower(t, t["body"])
    assert "def max3_t (a : Int) (b : Int) (c : Int) : Int :=\n" \
           "  (max2_t (max2_t a b) c)" in src, src
    # the task's own proof never names the callee for unfolding
    spec = src[src.index("theorem max3_t_spec"):]
    spec = spec[:spec.index("\n\n")]
    assert "max2_t" not in spec.replace("max3_t", ""), spec


def test_caller_owes_the_callee_requires() -> None:
    t = _fixture("clamp_sum")
    src = lower(t, t["body"])
    # add_clamped's own body owes clamp's `h >= 0` at both calls
    assert ("theorem add_clamped_t_wfbody (x : Int) (y : Int) (h : Int) :\n"
            "    (h ≥ (0 : Int)) → ((h ≥ (0 : Int)) ∧ (h ≥ (0 : Int)))"
            in src), src
    # the task owes add_clamped's `h >= 0` at `hi`
    assert ("theorem clamp_sum_t_wfbody (a : Int) (b : Int) (hi : Int) :\n"
            "    (hi ≥ (0 : Int)) → (hi ≥ (0 : Int))" in src), src


def test_call_inside_a_loop_and_a_loop_inside_a_method() -> None:
    t = _fixture("count_pos")
    src = lower(t, t["body"])
    assert "(step_t " in src and "def count_pos_t_loop" in src, src
    t = _fixture("rev_twice")
    src = lower(t, t["body"])
    assert "def rev_t_loop" in src and "theorem rev_t_spec" in src, src
    assert "  (rev_t (rev_t s))\n" in src, src


def test_twin_certificate_may_evaluate_the_callee() -> None:
    # a refutation is about what the twin computes, so the certificate's
    # simp set unfolds the methods; verification never does.
    t = _fixture("max3")
    body, _op, w = harness.twin_for(t)
    src = lower(t, body, w)
    cert = src[src.index("theorem t_refutation_certificate"):]
    assert "simp [max3_t, max2_t]" in cert, cert


def test_opaque_callee_is_lowered_modularly() -> None:
    t = _load(PROBE)
    src = lower(t, t["body"])
    assert "attribute [irreducible] inc_t" in src
    spec = src[src.index("theorem opaque_callee_t_spec"):]
    spec = spec[:spec.index("\n\n")]
    assert "inc_t" not in spec, spec


RECURSIVE_WITH_REQUIRES = """t 1
task recm_pre(n: int) returns (r: int)
  requires n >= 0
  ensures r >= 0
method sumto(k: int) returns (s: int)
  requires k >= 0
  ensures s >= 0
  decreases k
{
  if k == 0 {
    s := 0;
  } else {
    var u: int := sumto(k - 1);
    s := u + k;
  }
}
{
  r := sumto(n);
}
"""

RECURSIVE_NO_REQUIRES = """t 1
task recm_nopre(n: int) returns (r: int)
  ensures r >= 0
method cnt(k: int) returns (s: int)
  ensures s >= 0
  decreases k
{
  if k <= 0 {
    s := 0;
  } else {
    var u: int := cnt(k - 1);
    s := u + 1;
  }
}
{
  r := cnt(n);
}
"""


def _raises(task: dict, fragment: str) -> None:
    try:
        lower(task, task["body"])
    except NotImplementedError as e:
        assert fragment in str(e), str(e)
    else:
        raise AssertionError(f"expected an abstain naming {fragment!r}")


def test_abstains_on_a_call_to_a_recursive_method_with_requires() -> None:
    _raises(surface.parse(RECURSIVE_WITH_REQUIRES),
            "takes its requires as a proof argument")


def test_recursive_method_without_requires_lowers() -> None:
    t = surface.parse(RECURSIVE_NO_REQUIRES)
    src = lower(t, t["body"])
    _clean(src)
    # well-founded recursion is irreducible already; Lean rejects
    # re-setting it, so no attribute line is emitted for it
    assert "attribute [irreducible] cnt_t" not in src, src
    assert "grind_pattern cnt_t_spec => cnt_t k" in src, src


def test_abstains_on_a_method_with_no_parameters() -> None:
    t = _fixture("max3")
    m = dict(t["methods"][0])
    m.update(name="zero", params=[],
             ensures=[{"op": ">=", "args": [{"var": "m"}, {"int": 0}]}],
             body=[{"assign": ["m", {"int": 0}]}])
    t = dict(t, methods=[m], body=[
        {"assign": ["r", {"call": {"fun": "zero", "args": []}}]}])
    _raises(t, "no parameters")


def test_tasks_without_methods_emit_no_method_machinery() -> None:
    for f in sorted(glob.glob(os.path.join(HERE, "tasks", "*.t"))):
        t = _load(f)
        try:
            src = lower(t, t["body"])
        except NotImplementedError:
            continue
        assert "grind_pattern" not in src, f
        assert not re.search(r"attribute \[irreducible\]", src), f


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
            n += 1
            print("ok", k)
    print(f"{n} passed")
