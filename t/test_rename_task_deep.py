"""spec_experiment.rename_task walks the task with an explicit stack: an answer nested deeper than Python's recursion
limit (one of Phi-4-mini's under t's grammar, 2026-10-03) stopped a whole set's extraction."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import spec_experiment as se  # noqa: E402


def test_rename_reaches_a_self_call_nested_far_past_the_recursion_limit():
    deep = {"call": {"fun": "old", "args": []}}
    for _ in range(sys.getrecursionlimit() * 3):
        deep = {"op": "not", "args": [deep]}
    task = {"name": "old", "body": [{"assign": ["r", deep]}], "requires": [],
            "ensures": [{"call": {"fun": "old", "args": []}}], "spec_funs": []}
    out = se.rename_task(task, "new")
    node = out["body"][0]["assign"][1]
    while "op" in node:
        node = node["args"][0]
    assert (out["name"], node["call"]["fun"], out["ensures"][0]["call"]["fun"]) == ("new", "new", "new")


def test_rename_leaves_calls_to_other_functions_alone():
    task = {"name": "f", "body": [{"assign": ["r", {"call": {"fun": "g", "args": [{"call": {"fun": "f", "args": []}}]}}]}],
            "requires": [], "ensures": []}
    out = se.rename_task(task, "h")
    call = out["body"][0]["assign"][1]["call"]
    assert call["fun"] == "g" and call["args"][0]["call"]["fun"] == "h"
