#!/usr/bin/env python3
"""t/spec_refine.py: strengthen an under-constrained specification against its surviving mutants and
verify the strengthening deterministically (kernel-free).

A survivor (t/spec_strength.py, t/audit.py) is a behaviour-changing mutant the task's `ensures` still
accepts. ExVerus (arXiv:2603.25810) and SpecSyn (arXiv:2604.21570) strengthen a weak spec by adding
the clause that excludes such a survivor, then re-checking that the real program still verifies. This
module is the VERIFY half of that loop:

    strengthen(task, extra) -> a copy of task with extra `ensures` conjunct(s) appended.
    check(task, extra)      -> {real_ok, survivors_before, survivors_after, killed_now,
                                strength_before, strength_after, accepted}

`extra` is one t AST `ensures` conjunct or a list of them, in the schema tasks_io.load_task returns,
e.g. `result ==> k >= 2` is
    {"op": "implies", "args": [{"var": "result"},
                               {"op": ">=", "args": [{"var": "k"}, {"int": 2}]}]}.
A strengthening is `accepted` only when the real body STILL satisfies the strengthened spec
(audit.classify reports status "real-violates-spec" otherwise -- so a strengthening that breaks the
real program is rejected, fail-closed) AND strictly fewer behaviour-changing mutants survive.

A proposer (a model over the t/spec_strength worklist, or a human) supplies `extra`; this harness is
the gate every proposal must pass before any kernel is asked to re-prove the strengthened task.
Source: SpecSyn arXiv:2604.21570, ExVerus arXiv:2603.25810; internal/research/spec-validation.md;
research receipt af2adafc3215. Motivated by internal/E1-FINDINGS-2026-10-14.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # t/ on path for audit/harness/interp
import audit  # noqa: E402


def strengthen(task: dict, extra) -> dict:
    """A copy of `task` with `extra` appended to its `ensures` list. `extra` is one AST conjunct
    (a dict) or a list of them."""
    nodes = extra if isinstance(extra, list) else [extra]
    return {**task, "ensures": list(task.get("ensures", [])) + list(nodes)}


def _strength(res: dict):
    changing = res.get("killed", 0) + len(res.get("survivors", []))
    return (res["killed"] / changing) if changing else None


def check(task: dict, extra) -> dict:
    """Append `extra` to the task's `ensures` and report, interpreter-only, whether the real body
    still satisfies the strengthened spec and how many behaviour-changing mutants it still admits."""
    before = audit.classify(task)
    mod = strengthen(task, extra)
    after = audit.classify(mod)
    real_ok = after.get("status") != "real-violates-spec"
    after_ok = after.get("status") == "ok"
    sb = len(before.get("survivors", []))
    sa = len(after.get("survivors", [])) if after_ok else None
    return {
        "name": task.get("name"),
        "real_ok": real_ok,
        "after_status": after.get("status"),
        "survivors_before": sb,
        "survivors_after": sa,
        "killed_now": (sb - sa) if sa is not None else None,
        "strength_before": _strength(before),
        "strength_after": _strength(after) if after_ok else None,
        "accepted": bool(real_ok and after_ok and sa is not None and sa < sb),
    }
