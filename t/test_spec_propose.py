#!/usr/bin/env python3
"""t/spec_propose.py gate logic, deterministically (no live model): a sound proposed clause is
accepted, an unsound one is rejected. The model call is stubbed so the test exercises the
parse_expr -> spec_refine.check path, not the network."""
import glob
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import spec_propose  # noqa: E402


def _is_prime() -> str:
    fs = glob.glob(str(HERE / "humanevaldafny" / "*031*is_prime*")) or \
        glob.glob(str(HERE / "humanevaldafny" / "*is_prime*"))
    assert fs, "is_prime task not found"
    return fs[0]


def _with_fake_model(reply: str, path: str) -> dict:
    orig = spec_propose._call_model
    spec_propose._call_model = lambda prompt, cmd: reply
    try:
        return spec_propose.propose(path, model_cmd="unused", seconds=15)
    finally:
        spec_propose._call_model = orig


def test_sound_proposed_clause_accepted():
    r = _with_fake_model('["result ==> k >= 2"]', _is_prime())
    assert r["status"] == "strengthened", r
    assert r["strength_after"] == 1.0, r
    assert r["clause"] == "result ==> k >= 2", r


def test_unsound_proposed_clause_rejected():
    # `result` alone forces the postcondition true always; the real body returns False at k=1,
    # so the gate must reject it rather than accept a spec-breaking strengthening.
    r = _with_fake_model('["result"]', _is_prime())
    assert r["status"] == "no-proposal-passed", r
