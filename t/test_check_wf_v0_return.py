"""check_wf: v0 is int only for the return too (SPEC.md v0; `bool` is a v1 type)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_wf import check_wf  # noqa: E402


def task(t, rtype):
    return {"t": t, "name": "f", "params": [{"name": "a", "type": "int"}], "returns": [{"name": "r", "type": rtype}],
            "requires": [], "ensures": [{"op": "==", "args": [{"var": "r"}, {"var": "r"}]}],
            "body": [{"assign": ["r", {"op": "==", "args": [{"var": "a"}, {"int": 0}]}]}] if rtype == "bool"
            else [{"assign": ["r", {"var": "a"}]}]}


def test_a_v0_task_returning_bool_is_not_well_formed_and_the_same_task_under_t1_is():
    assert any("v0 has int only" in e for e in check_wf(task(0, "bool")))
    assert not check_wf(task(1, "bool"))
    assert not check_wf(task(0, "int"))
