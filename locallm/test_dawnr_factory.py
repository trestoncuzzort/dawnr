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
