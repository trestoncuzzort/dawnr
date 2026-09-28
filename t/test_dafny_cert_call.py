"""test_dafny_cert_call.py: the Dafny refutation certificate's replay of an
undefined-kind twin witness walks through a spec_fun call (2026-09-28): the
call's arguments are evaluated first, left to right, so an out-of-range
index inside an argument yields the ground guard, and the call's value
comes from the interpreter. A quantifier in the body still refuses."""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import lower_dafny as L                                        # noqa: E402

SEQ = {"seq": "int"}
TASK = {
    "t": 1, "gate": "loops", "name": "shift_all",
    "params": [{"name": "s", "type": "seq"}], "returns": [{"name": "r", "type": "seq"}],
    "requires": [], "ensures": [{"op": "==", "args": [{"op": "len", "args": [{"var": "r"}]}, {"op": "len", "args": [{"var": "s"}]}]}],
    "spec_funs": [{"name": "f", "params": [{"name": "x", "type": "int"}], "result": "int", "decreases": {"int": 0},
                   "body": {"op": "+", "args": [{"var": "x"}, {"int": 1}]}}],
    "body": [],
}
# the sabotaged body: `while i <= len(s)` runs one iteration too many and
# indexes s[len(s)] inside the call's argument
TWIN_BODY = [
    {"assign": ["r", {"op": "seq", "args": []}]},
    {"var": {"name": "i", "type": "int", "init": {"int": 0}}},
    {"while": {"cond": {"op": "<=", "args": [{"var": "i"}, {"op": "len", "args": [{"var": "s"}]}]},
               "invariants": [], "decreases": {"op": "-", "args": [{"op": "len", "args": [{"var": "s"}]}, {"var": "i"}]},
               "body": [
                   {"assign": ["r", {"op": "+", "args": [{"var": "r"}, {"op": "seq", "args": [
                       {"call": {"fun": "f", "args": [{"op": "at", "args": [{"var": "s"}, {"var": "i"}]}]}}]}]}]},
                   {"assign": ["i", {"op": "+", "args": [{"var": "i"}, {"int": 1}]}]}]}},
]
WITNESS = {"s": [], "_kind": "undefined", "_real": [], "_twin": "at index 0 outside [0,0)", "_ens": True}


def test_a_call_in_the_body_no_longer_refuses_the_certificate() -> None:
    cert = L._certificate(TASK, TWIN_BODY, WITNESS)
    assert cert is not None and "t_refutation_certificate" in cert, cert
    assert "0 < 0" in cert or "0 <= 0" in cert, cert   # the index guard, ground


def test_the_call_value_flows_into_later_state() -> None:
    # two iterations on s = [5]: the first call is defined (f(5) = 6), the
    # second indexes s[1] out of range; the guard names index 1
    w = {"s": [5], "_kind": "undefined", "_real": [6], "_twin": "at index 1 outside [0,1)", "_ens": True}
    cert = L._certificate(TASK, TWIN_BODY, w)
    assert cert is not None and "1 < 1" in cert, cert


def test_a_quantifier_in_the_body_still_refuses() -> None:
    body = [{"assign": ["r", {"op": "seq", "args": []}]},
            {"if": {"cond": {"forall": {"var": "k", "lo": {"int": 0}, "hi": {"op": "len", "args": [{"var": "s"}]},
                                        "body": {"op": ">=", "args": [{"op": "at", "args": [{"var": "s"}, {"var": "k"}]}, {"int": 0}]}}},
                    "then": [{"assign": ["r", {"op": "seq", "args": [{"op": "at", "args": [{"var": "s"}, {"int": 0}]}]}]}], "else": []}}]
    assert L._certificate(TASK, body, WITNESS) is None


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
