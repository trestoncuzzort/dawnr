"""dawnr_factory.py: tasks made by the thousand are only as good as their judges. Every family's tasks must start
not done, be done under their own solution with nothing else touched, and be nobody's twin among the measuring
tasks; and a described machine answers the same way every time."""
import random
import shutil
import tempfile
from pathlib import Path

import pytest

from locallm import dawnr_cli as cli

import dawnr_factory as factory
import dawnr_families


def test_no_group_of_families_failed_to_import_and_each_family_says_what_it_teaches():
    assert dawnr_families.BROKEN == {} and len(factory.FAMILIES) >= 5
    assert all((fn.__doc__ or "").strip() for fn in factory.FAMILIES.values())


def test_a_task_is_the_same_for_the_same_seed_and_a_twin_of_a_measuring_task_is_named():
    a, b = factory.make("shift_numbered", 7), factory.make("shift_numbered", 7)
    assert (a["request"], a["files"], a["solution"]) == (b["request"], b["files"], b["solution"]) and a["id"] == "shift_numbered:7"
    assert factory.make("shift_numbered", 8)["files"] != a["files"]
    assert factory.twin({"request": "Swap the contents of left.md and right.md."}).startswith("the same request as measuring task")
    assert factory.twin({"request": "Turn on dark mode."}) and factory.twin(a) is None
    assert factory.twin({"request": "Exchange what left.md and right.md hold, and tell me when it is done."}) is None


def test_a_described_machine_answers_from_its_seed_and_is_nobodys():
    m, again = factory.Machine(random.Random(3)), factory.Machine(random.Random(3))
    assert m.run("uname -r")["stdout"].strip() == m.kernel == again.kernel and m.run("nproc")["stdout"].strip() == str(m.cpus)
    assert m.run("zzqx-no-such-program")["exit"] == 127 and str(m.top_process[0]) in m.run("ps aux --sort=-%mem | head -2")["stdout"]
    assert m.sentence.startswith("This computer: ") and m.sentence.endswith(".")
    assert not any(name in m.sentence + m.host + m.run("whoami")["stdout"] for name in factory.identifiers())


@pytest.mark.parametrize("name", sorted(factory.FAMILIES))
def test_every_family_makes_tasks_its_own_solution_passes_and_nothing_else_does(name, tmp_path):
    needs_sandbox = "run" in factory.make(name, 0)["expect"]
    if needs_sandbox and shutil.which("bwrap") is None:
        pytest.skip("its check runs the result, and there is no sandbox here")
    usable = 0
    for seed in range(6):
        task, base, opened = factory.make(name, seed), Path(tempfile.mkdtemp(dir=tmp_path)), []
        if factory.twin(task):
            continue                                            # refused by the gate, as it would be when teaching

        def shell_for(work, base=base, opened=opened):
            harness, agent = cli.build_agent(cli.default_config(work, state=base / "state"))
            opened.append(harness)
            return agent.shell
        try:
            why = factory.selfcheck(task, base, shell_for if "run" in task["expect"] else None)
        finally:
            for harness in opened:
                harness.close()
        if why == ["its check runs the result, and there is no sandbox here"]:
            pytest.skip(why[0])
        assert why == [], (task["id"], why)
        usable += 1
    assert usable >= 3, f"{name}: too many of its tasks are twins of measuring tasks"


def test_a_bad_rounds_or_steps_setting_stops_the_check_before_any_task_is_checked(monkeypatch, capsys):
    # --check builds the assistant's shell with dawnr_cli.default_config, which reads DAWNR_MAX_ROUNDS and
    # DAWNR_MAX_STEPS, for a family whose check runs the result; it is refused for every family, so that the same
    # setting does not stop one family's check and let another's through
    monkeypatch.delenv("DAWNR_MAX_STEPS", raising=False)
    monkeypatch.setenv("DAWNR_MAX_ROUNDS", "0")
    message = "dawnr_factory: DAWNR_MAX_ROUNDS='0' is not a whole number above 0; set it to one, or unset it for the default of 18\n"
    assert "run" in factory.make("add_json_command", 0)["expect"] and "run" not in factory.make("edit_add_header", 0)["expect"]
    for name in ("add_json_command", "edit_add_header"):
        assert factory.main(["--check", "1", "--family", name]) == 2
        assert capsys.readouterr() == ("", message)
    # the list and a task shown build nothing and read no setting
    assert factory.main(["--show", "edit_add_header", "0"]) == 0 and "REQUEST:" in capsys.readouterr().out


def test_the_check_says_the_budget_its_shells_were_built_with(monkeypatch, capsys):
    monkeypatch.delenv("DAWNR_MAX_ROUNDS", raising=False)
    monkeypatch.delenv("DAWNR_MAX_STEPS", raising=False)
    assert factory.main(["--check", "1", "--family", "edit_add_header"]) == 0
    assert capsys.readouterr().out.splitlines()[0] == 'loop budget {"max_steps": 40, "max_rounds": 18, "max_failures": 2}'
    monkeypatch.setenv("DAWNR_MAX_ROUNDS", "3")
    monkeypatch.setenv("DAWNR_MAX_STEPS", "2")
    assert factory.main(["--check", "1", "--family", "edit_add_header"]) == 0
    assert capsys.readouterr().out.splitlines()[0] == 'loop budget {"max_steps": 2, "max_rounds": 3, "max_failures": 2}'
    # the list and a task shown build no shell, and say no budget
    assert factory.main(["--list"]) == 0 and "loop budget" not in capsys.readouterr().out
