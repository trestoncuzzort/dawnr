#!/usr/bin/env python3
"""test_lower_rocq_methods.py: the Rocq lowering of SPEC.md "Methods (v1)".

Shape only; this file runs no prover (kernel verdicts are measured with the
real kernel, see lower_rocq.py's METHODS section). What it pins:

- every method is its own unit (`m_t`, `m_t_spec`) emitted before the task,
  followed by `m_t_closed`, its contract for the composed method;
- a caller takes each callee as a universally quantified function binder
  `t_m_m` plus the hypothesis `t_mspec_m t_m_m`, so its proof can only use
  the callee's contract (Dafny's modular call rule), never its body;
- the callee's requires at the call's arguments is an obligation lemma;
- a refutation certificate evaluates the twin program with the methods'
  concrete Definitions;
- shapes the lowering cannot express raise NotImplementedError by name;
- a task without methods lowers exactly as before (no method machinery).

Run: python3 t/test_lower_rocq_methods.py   (or pytest)
"""

from __future__ import annotations

import copy
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import harness                                                 # noqa: E402
import lower_rocq                                              # noqa: E402
import surface                                                 # noqa: E402

FIXTURES = sorted(glob.glob(os.path.join(HERE, "methods", "*.t")))


def _load(name: str, sub: str = "methods") -> dict:
    return surface.parse_file(os.path.join(HERE, sub, name + ".t"))


def _abstains(task: dict, reason: str) -> None:
    try:
        lower_rocq.lower(task, task["body"])
    except NotImplementedError as e:
        assert reason in str(e), (reason, str(e))
        return
    raise AssertionError(f"expected NotImplementedError({reason!r})")


def test_every_fixture_lowers_with_its_methods_first() -> None:
    assert len(FIXTURES) >= 4, FIXTURES
    for f in FIXTURES + [os.path.join(HERE, "methods_probe", "opaque_callee.t")]:
        t = surface.parse_file(f)
        src = lower_rocq.lower(t, t["body"])
        name = t["name"]
        task_def = src.index(f"Definition {name}_t ")
        for m in t["methods"]:
            mn = m["name"]
            assert f"Definition t_mspec_{mn} " in src, (f, mn)
            assert f"Theorem {mn}_t_spec" in src, (f, mn)
            assert f"Lemma {mn}_t_closed : t_mspec_{mn} " in src, (f, mn)
            assert src.index(f"Lemma {mn}_t_closed") < task_def, (f, mn)
        assert f"Theorem {name}_t_spec" in src
        assert f"Theorem {name}_t_closed" in src
        assert src.rstrip().endswith(f"Print Assumptions {name}_t_spec.")
        for bad in ("Admitted", "admit", "Axiom", "Variable", "Hypothesis",
                    "Opaque"):
            assert not re.search(rf"\b{bad}\b", src), (f, bad)


def test_caller_sees_the_callee_only_as_a_bound_function() -> None:
    t = _load("max3")
    src = lower_rocq.lower(t, t["body"])
    assert ("Definition max3_t (t_m_max2 : Z -> Z -> Z) (a : Z) (b : Z) "
            "(c : Z) : Z := (t_m_max2 (t_m_max2 a b) c).") in src
    spec = src[src.index("Theorem max3_t_spec"):]
    spec = spec[:spec.index("Qed.")]
    assert "forall (t_m_max2 : Z -> Z -> Z)" in spec
    assert "(t_mspec_max2 t_m_max2) ->" in spec
    # the caller's own proof never names the callee's Definition
    assert "max2_t" not in spec.replace("t_m_max2", "")
    closed = src[src.index("Theorem max3_t_closed"):]
    assert "(max3_t (max2_t) a b c)" in closed
    assert "exact max2_t_closed" in closed


def test_contract_is_the_callee_ensures_of_an_arbitrary_function() -> None:
    t = _load("clamp_sum")
    src = lower_rocq.lower(t, t["body"])
    d = src[src.index("Definition t_mspec_clamp"):]
    d = d[:d.index(".\n")]
    assert d.startswith("Definition t_mspec_clamp (t_mf : Z -> Z -> Z) : Prop")
    assert "(h >= 0) ->" in d
    assert "(t_mf x h)" in d
    # add_clamped calls clamp, so it is a caller unit too
    assert "Definition add_clamped_t (t_m_clamp : Z -> Z -> Z)" in src
    assert ("Lemma add_clamped_t_closed : t_mspec_add_clamped "
            "(add_clamped_t (clamp_t)).") in src


def test_callee_requires_is_an_obligation_at_the_call() -> None:
    t = _load("clamp_sum")
    src = lower_rocq.lower(t, t["body"])
    # clamp_sum calls add_clamped(a, b, hi): requires hi >= 0
    assert re.search(r"Lemma clamp_sum_def_\d+ : forall \(t_m_add_clamped "
                     r"[^\n]*\n  \(t_mspec_add_clamped t_m_add_clamped\) ->\n"
                     r"  \(hi >= 0\) ->\n  \(\(hi >= 0\)\)\.", src), src
    # count_pos's call sits in a loop: requires r >= 0 under the invariants
    t = _load("count_pos")
    src = lower_rocq.lower(t, t["body"])
    assert re.search(r"\(i < s_len\) ->\n  \(\(r >= 0\)\)\.", src)


def test_calls_in_loops_and_seq_returns_lower() -> None:
    t = _load("count_pos")
    src = lower_rocq.lower(t, t["body"])
    assert "count_pos_loop fu t_m_step s s_len (t_m_step r (s i)) (i + 1)" in src
    t = _load("rev_twice")
    src = lower_rocq.lower(t, t["body"])
    assert ("(t_m_rev : (Z -> Z) -> Z -> Z -> Z) "
            "(t_m_rev_len : (Z -> Z) -> Z -> Z)") in src
    assert "(t_m_rev (t_m_rev s s_len) (t_m_rev_len s s_len))" in src
    # a seq return also promises its length is nonnegative
    assert "((t_mf_len u u_len) >= 0)" in src


def test_every_tactic_entry_instantiates_contracts_first() -> None:
    t = _load("max3")
    src = lower_rocq.lower(t, t["body"])
    for tac in ("t_dis", "t_side", "t_dis_ext", "t_side_ext"):
        assert f"Ltac {tac} := t_minst; first [" in src, tac
    assert "Ltac t_minst := t_mi_max2; t_ma_max2." in src


def test_twin_certificates_use_the_concrete_methods() -> None:
    for name in ("max3", "clamp_sum", "rev_twice"):
        t = _load(name)
        body, _op, w = harness.twin_for(t)
        src = lower_rocq.lower(t, body, w)
        assert "Theorem t_refutation_certificate" in src, name
        assert "t_m_" not in src, name
        for m in t["methods"]:
            assert f"{m['name']}_t" in src, (name, m["name"])
    t = _load("clamp_sum")
    body, _op, w = harness.twin_for(t)
    src = lower_rocq.lower(t, body, w)
    assert "Definition clamp_sum_t (a : Z) (b : Z) (hi : Z) : Z := " \
           "(add_clamped_t a b b)." in src
    # count_pos's twin is an undefined-index witness: a bound, by lia
    t = _load("count_pos")
    body, _op, w = harness.twin_for(t)
    src = lower_rocq.lower(t, body, w)
    assert "~ (0 <= 0 /\\ 0 < 0)" in src


def test_abstains_by_name() -> None:
    t = _load("max3")
    t2 = copy.deepcopy(t)
    t2["methods"][0]["params"][0]["type"] = {"pair": ["int", "int"]}
    _abstains(t2, "method-pair-or-nested-type")
    t3 = copy.deepcopy(t)
    t3["methods"][0]["returns"][0]["type"] = {"seq": "seq"}
    _abstains(t3, "method-pair-or-nested-type")
    t4 = {"t": 1, "name": "z0", "params": [{"name": "a", "type": "int"}],
          "returns": [{"name": "r", "type": "int"}], "requires": [],
          "ensures": [{"op": ">=", "args": [{"var": "r"}, {"int": 0}]}],
          "methods": [{"name": "zero", "params": [],
                       "returns": [{"name": "o", "type": "int"}],
                       "requires": [],
                       "ensures": [{"op": "==", "args": [{"var": "o"},
                                                         {"int": 0}]}],
                       "body": [{"assign": ["o", {"int": 0}]}]}],
          "body": [{"assign": ["r", {"call": {"fun": "zero", "args": []}}]}]}
    _abstains(t4, "method-no-params")
    # a self-recursive task that also calls a method
    t5 = copy.deepcopy(t)
    t5["decreases"] = {"var": "a"}
    t5["body"] = [{"if": {"cond": {"op": "<=", "args": [{"var": "a"}, {"int": 0}]},
                          "then": [{"assign": ["r", {"call": {"fun": "max2", "args": [
                              {"var": "b"}, {"var": "c"}]}}]}],
                          "else": [{"assign": ["r", {"call": {"fun": "max3", "args": [
                              {"op": "-", "args": [{"var": "a"}, {"int": 1}]},
                              {"var": "b"}, {"var": "c"}]}}]}]}}]
    _abstains(t5, "method-rec-calls")
    # a callee requires whose bound variable is a name the argument uses
    t6 = copy.deepcopy(t)
    t6["methods"][0]["requires"] = [{"forall": {
        "var": "a", "lo": {"int": 0}, "hi": {"var": "x"},
        "body": {"op": ">=", "args": [{"var": "a"}, {"int": 0}]}}}]
    _abstains(t6, "method-requires-capture")


def test_tasks_without_methods_carry_no_method_machinery() -> None:
    for f in sorted(glob.glob(os.path.join(HERE, "tasks", "*.t")))[:12]:
        t = surface.parse_file(f)
        try:
            src = lower_rocq.lower(t, t["body"])
        except NotImplementedError:
            continue
        assert "t_minst" not in src and "t_mspec_" not in src, f


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"{fn.__name__}: pass")
    print(f"test_lower_rocq_methods: {len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
