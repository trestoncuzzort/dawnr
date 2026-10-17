#!/usr/bin/env python3
"""t/spec_refine.py applied to a real under-constrained spec (PREDICT-2026-10-16-spec-refine.md).

humaneval_dafny_031_is_prime admits is_prime(1)=True; the missing clause is `result ==> k >= 2`.
Strengthening with it must kill the survivor while keeping the real body valid; a strengthening that
forces `result` true always must be rejected (fail-closed)."""
import glob
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import tasks_io  # noqa: E402
import spec_refine  # noqa: E402

# `result ==> k >= 2`
GOOD = {"op": "implies", "args": [{"var": "result"},
                                  {"op": ">=", "args": [{"var": "k"}, {"int": 2}]}]}
# `result` alone: forces the postcondition true always; the real body returns False at k=1.
BAD = {"var": "result"}


def _is_prime() -> dict:
    fs = glob.glob(str(HERE / "humanevaldafny" / "*031*is_prime*")) or \
        glob.glob(str(HERE / "humanevaldafny" / "*is_prime*"))
    assert fs, "is_prime task not found"
    return tasks_io.load_task(fs[0])


def test_strengthening_kills_survivor_and_keeps_real():
    r = spec_refine.check(_is_prime(), GOOD)
    assert r["real_ok"] is True, r
    assert r["survivors_before"] >= 1, r
    assert r["survivors_after"] == 0, r
    assert r["accepted"] is True, r
    assert r["strength_after"] == 1.0, r


def test_spec_breaking_strengthening_is_rejected():
    r = spec_refine.check(_is_prime(), BAD)
    assert r["real_ok"] is False, r
    assert r["accepted"] is False, r
