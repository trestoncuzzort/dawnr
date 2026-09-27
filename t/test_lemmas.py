#!/usr/bin/env python3
"""test_lemmas.py: SPEC.md "Lemmas (v1)" without a prover -- the notation,
well-formedness, the interpreter (a lemma call is a no-op), the twin ladder
(it never breaks a lemma call), and each lowering's shape on the fixtures in
t/lemmas/ and the seeded-fault probes in t/lemmas_probe/. Kernel verdicts
are measured by run_par and recorded in t/FEATURES-TRACK.md.

The design is Dafny's lemma (reference manual 6.3.3): a ghost method with no
return whose requires/ensures are the statement, whose body is its proof,
and whose call statement gives the caller its ensures.

Run: python3 t/test_lemmas.py   (or pytest)
"""

from __future__ import annotations

import copy
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import check_wf                                                # noqa: E402
import harness                                                 # noqa: E402
import interp                                                  # noqa: E402
import surface                                                 # noqa: E402

FIXTURES = sorted(glob.glob(os.path.join(HERE, "lemmas", "*.t")))
PROBES = sorted(glob.glob(os.path.join(HERE, "lemmas_probe", "*.t")))


def _load(path: str) -> dict:
    return surface.parse_file(path)


def _fx(name: str) -> dict:
    return _load(os.path.join(HERE, "lemmas", name + ".t"))


def _pr(name: str) -> dict:
    return _load(os.path.join(HERE, "lemmas_probe", name + ".t"))


def _keys(task: dict) -> set:
    out = set()
    errs = check_wf.check_wf(task, positions={})
    for e in errs:
        out.add(e.rule)
    return out


def test_fixtures_parse_check_and_round_trip() -> None:
    assert len(FIXTURES) >= 3 and len(PROBES) >= 3
    for f in FIXTURES + PROBES:
        t = _load(f)
        assert t.get("lemmas"), f
        assert check_wf.check_wf(t) == [], (f, check_wf.check_wf(t))
        text = surface.print_task(t)
        again = surface.parse(text)
        assert surface.canon(again) == surface.canon(t), f
        assert surface.print_task(again) == text, f


def test_wf_rules() -> None:
    base = _fx("pow2_pos")
    # a lemma called as an expression is an unknown function
    t = copy.deepcopy(base)
    t["body"][1]["var"]["init"] = {"call": {"fun": "pow2_ge1",
                                            "args": [{"var": "n"}]}}
    assert "call-unknown" in _keys(t)
    # an assignment in a lemma body
    t = copy.deepcopy(base)
    t["lemmas"][0]["body"] = [{"assign": ["k", {"int": 0}]}]
    assert "lemma-body" in _keys(t)
    # a self-call without a decreases, and a decreases without one
    t = copy.deepcopy(base)
    del t["lemmas"][0]["decreases"]
    assert "lemma-decreases" in _keys(t)
    t = copy.deepcopy(base)
    t["lemmas"][0]["body"] = []
    assert "lemma-decreases" in _keys(t)
    # a lemma in a v0 task
    t = copy.deepcopy(base)
    t["t"] = 0
    assert "v0-frozen" in _keys(t)
    # wrong argument type
    t = copy.deepcopy(base)
    t["body"][0]["lemma"]["args"] = [{"bool": True}]
    assert "lemma-call" in _keys(t)
    # a lemma contract calling a method
    t = copy.deepcopy(_load(os.path.join(HERE, "methods", "max3.t")))
    t["lemmas"] = [{"name": "bad", "params": [{"name": "a", "type": "int"}],
                    "requires": [], "ensures": [
                        {"op": "==", "args": [{"call": {"fun": "max2", "args": [
                            {"var": "a"}, {"var": "a"}]}}, {"var": "a"}]}],
                    "body": []}]
    assert "method-call-position" in _keys(t) or "call-unknown" in _keys(t)


def test_interpreter_skips_the_call() -> None:
    t = _fx("sum_loop")
    env = {"s": (1, 2, 3), "r": None}
    interp.exec_body(t["body"], env, interp.funs_of(t, t["body"]), interp.St())
    assert env["r"] == 6
    # the same body without the call computes the same value
    import lower_lean
    env2 = {"s": (1, 2, 3), "r": None}
    b2 = lower_lean.strip_lemma_calls(t["body"])
    interp.exec_body(b2, env2, interp.funs_of(t, b2), interp.St())
    assert env2["r"] == 6


def test_twin_never_touches_a_lemma_call() -> None:
    for f in FIXTURES:
        t = _load(f)
        body, op, w = harness.twin_cached(t)
        if body is None:
            continue

        def calls(b):
            out = []
            for s in b:
                if "lemma" in s:
                    out.append(s)
                elif "if" in s:
                    out += calls(s["if"]["then"]) + calls(s["if"]["else"])
                elif "while" in s:
                    out += calls(s["while"]["body"])
            return out
        assert calls(body) == calls(t["body"]), f


def _lower(mod: str, t: dict) -> str:
    return __import__(mod).lower(t, t["body"])


def test_dafny_emits_a_lemma_with_a_body_and_a_call() -> None:
    src = _lower("lower_dafny", _fx("sq_bound"))
    # never a body-less lemma (an axiom in Dafny)
    assert re.search(r"lemma mul_le_sq\(.*\)\n(  .*\n)*\{\n\}", src), src
    assert "mul_le_sq(x, y);" in src


def test_verus_emits_a_proof_fn() -> None:
    src = _lower("lower_verus", _fx("sum_loop"))
    assert "proof fn sum_append(" in src
    assert "decreases (hi - lo)," in src
    assert re.search(r"sum_append\(s, \(?0", src), src


def test_fstar_emits_a_lemma_with_a_pattern() -> None:
    src = _lower("lower_fstar", _fx("sum_loop"))
    assert "let rec sum_append" in src and ": Lemma (requires" in src
    assert "[SMTPat (sum_range a lo (hi + 1)); SMTPat (sum_range a lo hi)]" in src
    for p in PROBES:     # the false lemmas are stated, never dropped
        t = _load(p)
        assert f"{t['lemmas'][0]['name']} " in _lower("lower_fstar", t)


def test_spark_emits_a_boolean_lemma_function_and_owes_its_call() -> None:
    src = _lower("lower_spark", _fx("sum_loop"))
    assert "function Sum_append (A : Seq; Lo : Big_Integer; Hi : Big_Integer) return Boolean" in src
    assert "Post => (Sum_range (A, Lo, (Hi + Big_Integer'(1)))" in src
    assert "(if (Sum_append (S, Big_Integer'(0), I))" in src


def test_framac_emits_a_ghost_lemma_function() -> None:
    src = _lower("lower_framac", _fx("sum_loop"))
    assert "/*@ ghost\n  /@\n" in src
    assert "void sum_append_t(int *a, int a_n, int lo, int hi)" in src
    assert "decreases ((hi - lo));" in src
    assert "/*@ ghost sum_append_t(s, s_n, 0, i); */" in src


def test_lean_proves_each_lemma_and_hands_it_to_grind() -> None:
    src = _lower("lower_lean", _fx("sum_loop"))
    assert "theorem sum_append_l " in src
    assert "termination_by ((hi - lo)).toNat" in src
    assert "grind_pattern sum_append_l =>" in src
    assert "#print axioms sum_append_l" in src
    for p in PROBES:
        t = _load(p)
        assert f"theorem {t['lemmas'][0]['name']}_l " in _lower("lower_lean", t)


def test_rocq_proves_the_program_without_the_lemma() -> None:
    t = _fx("sum_loop")
    src = _lower("lower_rocq", t)
    assert "sum_append" not in src
    import lower_lean
    bare = {k: v for k, v in t.items() if k != "lemmas"}
    bare["body"] = lower_lean.strip_lemma_calls(t["body"])
    assert src == __import__("lower_rocq").lower(bare, bare["body"])


def test_an_assert_is_a_proof_step_where_it_can_be_stated() -> None:
    t = _pr("false_assert")
    assert t["lemmas"][0]["body"] == [{"assert": {"op": ">=", "args": [
        {"var": "k"}, {"int": 1}]}}]
    assert "assert (k >= 1);" in _lower("lower_dafny", t)
    assert "assert((k >= (1int)));" in _lower("lower_verus", t)
    assert "assert ((k >= 1))" in _lower("lower_fstar", t)
    assert "/@ assert (k >= 1); @/" in _lower("lower_framac", t)
    assert "have _la1 : (k ≥ (1 : Int)) := by" in _lower("lower_lean", t)
    # an assert outside a lemma body is not a t statement
    bad = copy.deepcopy(t)
    bad["body"].insert(0, {"assert": {"bool": True}})
    assert "unknown-stmt" in _keys(bad)


def test_no_kernel_axiomatizes_a_lemma() -> None:
    banned = {"lower_dafny": [r"\{:axiom\}", r"\bassume\b"],
              "lower_verus": [r"admit\(", r"assume\("],
              "lower_fstar": [r"\badmit\b", r"\bassume\b"],
              "lower_lean": [r"\bsorry\b", r"\baxiom\b"],
              "lower_framac": [r"\baxiom\b", r"admit"],
              "lower_spark": [r"pragma Assume", r"False_Positive"]}
    for f in FIXTURES + PROBES:
        t = _load(f)
        for mod, pats in banned.items():
            try:
                src = _lower(mod, t)
            except NotImplementedError:
                continue
            for p in pats:
                assert not re.search(p, src), (f, mod, p)


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok   {name}")
            except Exception as e:                       # noqa: BLE001
                fails += 1
                print(f"FAIL {name}: {type(e).__name__}: {e}"[:400])
    print(f"{fails} failed")
    raise SystemExit(1 if fails else 0)
