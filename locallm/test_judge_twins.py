"""judge_twins: every twin differs from the solution in the one way its name says, and the judge sees the plain ones."""
import tempfile
from pathlib import Path

import dawnr_families  # noqa: F401  (registers the families)
import dawnr_factory as factory
import judge_twins as jt


def test_twins_are_named_and_differ():
    task = factory.make("edit_add_header", 0)
    twins = dict(jt.twins_of(task))
    assert set(twins) <= set(jt.TWINS)
    for name, twin in twins.items():
        assert twin != task["solution"], name
    assert "junk" in twins and "drop" in twins               # two files are written: one can be dropped, one can carry junk
    rel = sorted(twins["junk"]["files"])[0]
    assert twins["junk"]["files"][rel].endswith("zzz left over\n")


def test_bump_changes_one_digit_outside_comments():
    assert jt._bump("# v1\nx = 2\n", True) == "# v1\nx = 3\n"
    assert jt._bump("# v9\n", True) is None and jt._bump("# v9\n", False) == "# v0\n"


def test_judge_rejects_a_dropped_file_and_passes_the_solution():
    task = factory.make("edit_add_header", 0)
    twins = dict(jt.twins_of(task))
    with tempfile.TemporaryDirectory() as tmp:
        assert jt.judge_solution(task, task["solution"], Path(tmp) / "a")["done"]
        assert not jt.judge_solution(task, twins["drop"], Path(tmp) / "b")["done"]
