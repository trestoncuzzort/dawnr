"""dawnr_teach.py: what the teacher is given is the assistant as a person runs it, settings and all."""
import dawnr_teach as teach


def test_a_bad_rounds_or_steps_setting_is_said_before_any_task_and_no_seed_is_recorded(tmp_path, monkeypatch, capsys):
    # each task runs the assistant's loop with dawnr_cli.default_config, which reads DAWNR_MAX_ROUNDS and
    # DAWNR_MAX_STEPS. A seed in the log is one the next run skips, so a setting refused one task at a time would
    # record every seed as an error and leave nothing to run once the setting is put right
    monkeypatch.delenv("DAWNR_MAX_ROUNDS", raising=False)
    monkeypatch.setenv("DAWNR_MAX_STEPS", "-3")
    out = tmp_path / "rows.jsonl"
    argv = ["--host", "nowhere:1", "--out", str(out), "--family", "edit_add_header", "--per-family", "1", "--workers", "1"]
    assert teach.main(argv) == 2
    assert capsys.readouterr() == ("", "dawnr_teach: DAWNR_MAX_STEPS='-3' is not a whole number above 0; set it to one, "
                                       "or unset it for the default of 40\n")
    assert not out.exists() and not out.with_suffix(".log.jsonl").exists()
