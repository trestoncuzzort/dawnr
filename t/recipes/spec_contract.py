"""Static contract gate shared by teacher transport and incremental data curation.

Sources: t/spec_first.py:accept (the existing checked header promotion),
t/check_wf.py, and t/surface.py. No reference or proof evaluation runs here.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_wf
import surface


def checked_contract(value: dict) -> tuple[dict, bool]:
    """Return a statically valid, printable contract and whether its version was promoted.

    Only the same 0-to-1 header promotion already used by spec_first.accept is allowed.
    Empty declaration lists have the same meaning as their omission by the printer.
    No expression, clause, parameter, result, helper body or frame is rewritten.
    """
    task = deepcopy(value)
    if type(task) is not dict or type(task.get("t")) is not int or task["t"] not in (0, 1):
        raise ValueError("invalid contract version")
    if task.get("body") != [] or type(task.get("ensures")) is not list or not task["ensures"]:
        raise ValueError("a contract needs an empty body and at least one ensures clause")
    for key in ("spec_funs", "datatypes", "methods", "lemmas"):
        if task.get(key) == []:
            del task[key]
    try:
        errors = check_wf.check_wf(task)
        promoted = False
        if errors and task["t"] == 0:
            candidate = dict(task, t=1)
            if not check_wf.check_wf(candidate):
                task, errors, promoted = candidate, [], True
        if errors:
            raise ValueError("ill-formed contract: " + str(errors[0]))
        printed = surface.print_task(task)
        if surface.parse(printed) != task:
            raise ValueError("printing changes the contract tree")
    except (KeyError, TypeError, IndexError, AttributeError, RecursionError, surface.SurfaceError) as error:
        raise ValueError("malformed contract: " + type(error).__name__ + ": " + str(error)) from error
    return task, promoted
