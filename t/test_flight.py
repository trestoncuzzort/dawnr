#!/usr/bin/env python3
"""test_flight.py: t/flight/, PX4's functions restated in t. Every task is well-formed, its contract admits no
survivor (t/audit.py), the README names it, and the PX4 harness either calls PX4 for it or says why not. Every task
under findings/ is refuted by the interpreter and names the PX4 call it is checked against. No network, compiler or
kernel."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "flight"))

import audit  # noqa: E402
import check_wf  # noqa: E402
import harness  # noqa: E402
import px4_diff  # noqa: E402
import tasks_io  # noqa: E402

TASKS = sorted((HERE / "flight").glob("*.t"))


def test_every_task_is_well_formed_and_audited():
    assert len(TASKS) >= 18
    for p in TASKS:
        task = tasks_io.load_task(str(p))
        assert check_wf.check_wf(task) == [], p
        res = audit.classify(task)
        assert res["status"] == "ok" and not res["survivors"], (p.name, res.get("survivors"))


def test_every_task_is_tied_to_px4():
    readme = (HERE / "flight" / "README.md").read_text()
    for p in TASKS:
        name = tasks_io.load_task(str(p))["name"]
        assert f"| {name} |" in readme, name
        assert (name in px4_diff.CALLS) != (name in px4_diff.NOT_DIFFED), name


FINDINGS = sorted((HERE / "flight" / "findings").glob("*.t"))


def test_every_finding_is_refuted_and_tied_to_px4():
    readme = (HERE / "flight" / "README.md").read_text()
    assert FINDINGS
    for p in FINDINGS:
        task = tasks_io.load_task(str(p))
        assert check_wf.check_wf(task) == [], p
        harness._set_ctx(task)
        assert harness.real_witness(task) is not None, p.name     # a broken contract or an undefined step
        assert ((task["name"] in px4_diff.FINDING_OF and px4_diff.FINDING_OF[task["name"]] in px4_diff.CALLS)
                != (task["name"] in px4_diff.FINDING_NOT_RUN)), p.name
        assert f"| {task['name']} |" in readme, task["name"]


FIXES = sorted((HERE / "flight" / "fixes").glob("*.t"))


def test_every_fix_is_audited_and_tied_to_px4():
    readme = (HERE / "flight" / "README.md").read_text()
    assert FIXES
    for p in FIXES:
        task = tasks_io.load_task(str(p))
        assert check_wf.check_wf(task) == [], p
        res = audit.classify(task)
        assert res["status"] == "ok" and not res["survivors"], (p.name, res.get("survivors"))
        assert ((task["name"] in px4_diff.FIX_OF and px4_diff.FIX_OF[task["name"]] in px4_diff.CALLS)
                != (task["name"] in px4_diff.FIX_NOT_DIFFED)), p.name
        assert f"| {task['name']} |" in readme, task["name"]
