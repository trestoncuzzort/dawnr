#!/usr/bin/env python3
"""test_lift_lemmas.py: LIFTER-DECISIONS row 38 (SPEC.md "Lemmas (v1)") --
a Dafny lemma the lifted method calls lifts to a t lemma, its call to a t
lemma call, and a lemma that cannot lift is dropped with its calls exactly
as decision 8 always did, never a refusal of the method. No prover: the
snippets are parsed by test_lift_rules' shim, as every rewrite-row test is.

Run: python3 t/test_lift_lemmas.py   (or pytest)
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import check_wf                                                # noqa: E402
import interp                                                  # noqa: E402
import lift_classify as C                                      # noqa: E402
import lift_parse                                              # noqa: E402
import lift_rewrite as R                                       # noqa: E402
from test_lift_rules import _rule_names, _find_all             # noqa: E402


def _lift_one(src: str, method_name: str):
    """lift_parse (the real parser: the shim in test_lift_rules keeps no
    lemma parts), then classify and rewrite `method_name`."""
    mod = lift_parse.parse(src)
    methods = {m.name: m for m in lift_parse.gradable_methods(mod)}
    v = C.classify(mod, methods[method_name])
    assert isinstance(v, C.Liftable), f"expected liftable, got refusal: {v}"
    rr = R.rewrite(mod, v, "unit.dfy", "sha")
    assert rr.refusal is None, rr.refusal
    assert check_wf.check_wf(rr.task) == [], check_wf.check_wf(rr.task)
    return rr.task, rr.record

INDUCTIVE = """
function sum(s: seq<int>): int
{
  if |s| == 0 then 0 else s[0] + sum(s[1..])
}

lemma SumAppend(s: seq<int>, x: int)
  ensures sum(s + [x]) == sum(s) + x
{
  if |s| == 0 {
    assert s + [x] == [x];
  } else {
    var t := s[1..];
    assert (s + [x])[1..] == t + [x];
    SumAppend(t, x);
  }
}

method Total(s: seq<int>) returns (r: int)
  ensures r == sum(s)
{
  r := 0;
  var i := 0;
  while i < |s|
    invariant 0 <= i <= |s|
    invariant r == sum(s[..i])
    decreases |s| - i
  {
    assert s[..i+1] == s[..i] + [s[i]];
    SumAppend(s[..i], s[i]);
    r := r + s[i];
    i := i + 1;
  }
  assert s[..|s|] == s;
}
"""


def test_inductive_lemma_lifts_with_its_proof_skeleton() -> None:
    task, rec = _lift_one(INDUCTIVE, "Total")
    assert check_wf.check_wf(task) == []
    rules = _rule_names(rec)
    assert "lemma-lifted" in rules and "lemma-call-lifted" in rules, rules
    (lem,) = task["lemmas"]
    assert lem["name"] == "sumAppend"
    # Dafny's default decreases on the first (seq) parameter, as its length
    assert lem["decreases"] == {"op": "len", "args": [{"var": lem["params"][0]["name"]}]}
    body = lem["body"]
    assert "if" in body[0]
    then, els = body[0]["if"]["then"], body[0]["if"]["else"]
    assert any("assert" in s for s in then)
    # the proof's local `t` is substituted into the assert and the self-call
    self_calls = [s for s in els if "lemma" in s]
    assert self_calls and "{'var': 't'}" not in str(self_calls), self_calls
    assert any("assert" in s for s in els)
    calls = _find_all(task["body"], "lemma")
    assert calls and calls[0]["name"] == "sumAppend"


def test_the_lifted_body_computes_what_it_did() -> None:
    task, _ = _lift_one(INDUCTIVE, "Total")
    env = {task["params"][0]["name"]: (4, -1, 7), task["returns"][0]["name"]: None}
    interp.exec_body(task["body"], env, interp.funs_of(task, task["body"]), interp.St())
    assert env[task["returns"][0]["name"]] == 10


UNLIFTABLE = """
lemma Refl<T>(x: T)
  ensures x == x
{
}

method Uses(x: int) returns (r: int)
  ensures r == x
{
  Refl(x);
  r := x;
}
"""


def test_a_lemma_that_cannot_lift_is_dropped_not_refused() -> None:
    task, rec = _lift_one(UNLIFTABLE, "Uses")
    rules = _rule_names(rec)
    assert "lemma-not-lifted" in rules and "lemma-call-dropped" in rules, rules
    assert "lemmas" not in task
    assert not _find_all(task["body"], "lemma")


EXPLICIT = """
function f(n: nat): nat
{
  if n == 0 then 1 else 2 * f(n - 1)
}

lemma FPos(n: nat)
  ensures f(n) >= 1
  decreases n
{
  if n > 0 { FPos(n - 1); }
}

method M(n: nat) returns (r: int)
  ensures r >= 1
{
  FPos(n);
  r := f(n);
}
"""


def test_explicit_decreases_and_nat_guard() -> None:
    task, rec = _lift_one(EXPLICIT, "M")
    (lem,) = task["lemmas"]
    p = lem["params"][0]["name"]
    assert lem["decreases"] == {"var": p}
    assert {"op": ">=", "args": [{"var": p}, {"int": 0}]} in lem["requires"]
    assert lem["body"][0]["if"]["then"][0]["lemma"]["name"] == lem["name"]


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok   {name}")
            except Exception as e:                       # noqa: BLE001
                fails += 1
                print(f"FAIL {name}: {type(e).__name__}: {e}"[:600])
    print(f"{fails} failed")
    raise SystemExit(1 if fails else 0)
