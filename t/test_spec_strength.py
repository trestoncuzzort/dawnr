#!/usr/bin/env python3
"""Cross-check t/spec_strength.py against t/audit.py (PREDICT-2026-10-16-spec-strength.md,
prediction 2): the scorer must report exactly audit's killed / survivor counts, and
strength == killed / (killed + survivors)."""
import glob
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import audit  # noqa: E402
import spec_strength  # noqa: E402

_SECONDS = 10


def _sample(n: int = 6) -> list[str]:
    files = sorted(glob.glob(str(HERE / "tasks" / "*.t")))
    if not files:
        files = sorted(glob.glob(str(HERE / "tasks" / "*.json")))
    return files[:n]


def test_scorer_consistent_with_audit():
    files = _sample()
    assert files, "no sample tasks found under t/tasks"
    checked = 0
    for f in files:
        raw = audit.audit_file(f, seconds=_SECONDS)
        s = spec_strength.score_one(f, None, _SECONDS)
        assert s["name"]
        if raw.get("status") != "ok":
            assert s["status"] == raw.get("status")
            continue
        assert s["killed"] == raw["killed"]
        assert s["changing"] == raw["killed"] + len(raw["survivors"])
        if s["changing"]:
            assert abs(s["strength"] - raw["killed"] / s["changing"]) < 1e-9
        else:
            assert s["strength"] is None
        checked += 1
    assert checked >= 1, "no auditable (ok) tasks in the sample to cross-check"


def test_strength_bounds_and_worklist_order():
    rows = [spec_strength.score_one(f, None, _SECONDS) for f in _sample(8)]
    for s in rows:
        if s["strength"] is not None:
            assert 0.0 <= s["strength"] <= 1.0
    weak = spec_strength.rank_weakest(rows)
    keys = [(r["strength"] if r["strength"] is not None else 1.0) for r in weak]
    assert keys == sorted(keys)  # weakest-first: non-decreasing strength (None last)
    for r in weak:
        assert r["survivors"], "rank_weakest must only include tasks with survivors"
