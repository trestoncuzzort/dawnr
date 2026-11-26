"""dawnr_teach.py: each task runs the assistant as a person runs it, settings included."""
import dawnr_teach as teach


def test_a_bad_rounds_or_steps_setting_is_said_before_any_task_and_no_seed_is_recorded(tmp_path, monkeypatch, capsys):
    # Each task runs the assistant's loop with dawnr_cli.default_config, which reads DAWNR_MAX_ROUNDS and
    # DAWNR_MAX_STEPS. The next run skips every seed in the log, so if each task refused a bad setting on its own,
    # every seed would be logged as an error and nothing would be left to run once the setting is fixed.
    monkeypatch.delenv("DAWNR_MAX_ROUNDS", raising=False)
    monkeypatch.setenv("DAWNR_MAX_STEPS", "-3")
    out = tmp_path / "rows.jsonl"
    argv = ["--host", "nowhere:1", "--out", str(out), "--family", "edit_add_header", "--per-family", "1", "--workers", "1"]
    assert teach.main(argv) == 2
    assert capsys.readouterr() == ("", "dawnr_teach: DAWNR_MAX_STEPS='-3' is not a whole number above 0; set it to one, "
                                       "or unset it for the default of 40\n")
    assert not out.exists() and not out.with_suffix(".log.jsonl").exists()


def test_each_line_of_the_log_records_the_budget_the_run_gave_its_tasks(tmp_path, monkeypatch):
    # Each log line records the budget, so a run with DAWNR_MAX_ROUNDS or DAWNR_MAX_STEPS set can be told from one
    # without. There is no server, so each task is judged not done, which still writes a log line.
    import json
    log = tmp_path / "rows.log.jsonl"
    argv = ["--host", "nowhere:1", "--out", str(tmp_path / "rows.jsonl"), "--family", "edit_add_header", "--per-family", "1", "--workers", "1"]
    monkeypatch.delenv("DAWNR_MAX_ROUNDS", raising=False)
    monkeypatch.delenv("DAWNR_MAX_STEPS", raising=False)
    assert teach.main(argv) == 0
    assert [json.loads(line)["budget"] for line in log.read_text().splitlines()] == [{"max_steps": 40, "max_rounds": 18, "max_failures": 2}]
    monkeypatch.setenv("DAWNR_MAX_ROUNDS", "3")
    monkeypatch.setenv("DAWNR_MAX_STEPS", "2")
    assert teach.main(argv[:-4] + ["--first-seed", "2000", "--per-family", "1", "--workers", "1"]) == 0
    assert [json.loads(line)["budget"] for line in log.read_text().splitlines()][1:] == [{"max_steps": 2, "max_rounds": 3, "max_failures": 2}]
