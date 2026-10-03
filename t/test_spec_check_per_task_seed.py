"""spec_check --per-task-seed: a task's generator comes from its own sha256, so its draws do not depend on which
tasks the run checked before it (2026-10-03: six verdicts flipped between two runs of the same answers)."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import spec_check  # noqa: E402

A = {"t": 1, "name": "f", "params": [{"name": "a", "type": "int"}], "returns": [{"name": "r", "type": "int"}],
     "requires": [], "ensures": [{"op": "==", "args": [{"var": "r"}, {"var": "a"}]}], "body": [{"assign": ["r", {"var": "a"}]}]}
B = dict(A, name="g")


def test_the_generator_a_task_gets_depends_on_the_task_alone():
    first = [random.Random(f"1:{spec_check.task_sha256(t)}").random() for t in (A, B)]
    again = [random.Random(f"1:{spec_check.task_sha256(t)}").random() for t in (B, A)][::-1]
    assert first == again and first[0] != first[1]
