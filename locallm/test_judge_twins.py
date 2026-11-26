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


def test_a_bad_rounds_or_steps_setting_is_said_before_any_twin_is_judged(monkeypatch, capsys):
    # a family whose check runs the result is judged with the assistant's shell, built by dawnr_cli.default_config,
    # which reads DAWNR_MAX_ROUNDS and DAWNR_MAX_STEPS
    monkeypatch.delenv("DAWNR_MAX_ROUNDS", raising=False)
    monkeypatch.setenv("DAWNR_MAX_STEPS", "2.5")
    assert "run" in factory.make("add_json_command", 0)["expect"]
    assert jt.main(["--seeds", "1", "--family", "add_json_command"]) == 2
    assert capsys.readouterr() == ("", "judge_twins: DAWNR_MAX_STEPS='2.5' is not a whole number above 0; set it to one, "
                                       "or unset it for the default of 40\n")


def test_the_rows_and_the_first_line_record_the_budget_the_shells_were_built_with(tmp_path, monkeypatch, capsys):
    import json
    monkeypatch.delenv("DAWNR_MAX_ROUNDS", raising=False)
    monkeypatch.delenv("DAWNR_MAX_STEPS", raising=False)
    out = tmp_path / "rows.jsonl"
    assert jt.main(["--seeds", "1", "--family", "edit_add_header", "--out", str(out)]) == 0
    assert capsys.readouterr().out.startswith('loop budget {"max_steps": 40, "max_rounds": 18, "max_failures": 2}\n')
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert rows and {json.dumps(r["budget"]) for r in rows} == {'{"max_steps": 40, "max_rounds": 18, "max_failures": 2}'}
    monkeypatch.setenv("DAWNR_MAX_ROUNDS", "3")
    monkeypatch.setenv("DAWNR_MAX_STEPS", "2")
    assert jt.main(["--seeds", "1", "--family", "edit_add_header", "--out", str(out)]) == 0
    assert capsys.readouterr().out.startswith('loop budget {"max_steps": 2, "max_rounds": 3, "max_failures": 2}\n')
    assert {json.dumps(json.loads(line)["budget"]) for line in out.read_text().splitlines()} == {'{"max_steps": 2, "max_rounds": 3, "max_failures": 2}'}
