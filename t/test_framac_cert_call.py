"""test_framac_cert_call.py: Frama-C's certificate for an undefined-kind
twin witness whose violation sits inside a spec_fun call's argument
(2026-09-28): `defs_t` states the arguments' obligations left to right, so
the certificate is emitted with the ground index guard. Pure lowering,
no prover; the real-prover check is t/test_framac_seq_fun.py's kind."""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import lower_framac as F                                       # noqa: E402
from test_dafny_cert_call import TASK, TWIN_BODY, WITNESS      # noqa: E402


def test_defs_t_states_a_calls_argument_obligations() -> None:
    ob = F.defs_t({"call": {"fun": "f", "args": [{"op": "at", "args": [{"var": "s"}, {"var": "i"}]}]}})
    assert ob is not None and "<" in str(ob), ob


def test_the_certificate_is_emitted_for_a_violation_inside_a_call() -> None:
    src = F.lower(TASK, TWIN_BODY, witness=WITNESS)
    assert F.CERT_FN in src, src[-600:]
    assert "t_refutation_certificate" in src


def test_a_bare_call_of_literals_has_no_obligation() -> None:
    assert F.defs_t({"call": {"fun": "f", "args": [{"int": 3}]}}) is None


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
