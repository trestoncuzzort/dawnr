"""dawnr_agent/shell.py: any command run for real over an overlay, in the sandbox; its changes asked for and applied
through the journal. These run where bubblewrap can mount an overlay (Linux 5.11+, bubblewrap 0.8+) and skip elsewhere."""
import os
import shutil
from pathlib import Path

import pytest

from locallm import dawnr_cli as cli


def agent_in(tmp_path, approve=True, **files):
    work = tmp_path / "work"
    work.mkdir()
    for name, text in files.items():
        (work / name).parent.mkdir(parents=True, exist_ok=True)
        (work / name).write_text(text)
    asked = []

    def approver(name, arguments, why):
        asked.append(why)
        return approve
    cfg = {"offline": True, "permissions": {},
           "agent": {"roots": [{"name": "here", "path": str(work), "mode": "write"}], "state": str(tmp_path / "state"), "shell": True}}
    harness, agent = cli.build_agent(cfg, approver=approver)
    if agent.shell is None:
        harness.close()
        pytest.skip("no overlay sandbox here: " + "; ".join(p for p in harness.problems if p.startswith("shell")))
    return work, harness, agent, asked


pytestmark = pytest.mark.skipif(shutil.which("bwrap") is None, reason="bubblewrap is not installed")


@pytest.fixture(autouse=True, params=["overlay", "copy"])
def mode(request, monkeypatch):
    """Every test twice: over an overlay (bubblewrap 0.11 and newer) and over a copy of the folder (older ones)."""
    monkeypatch.setenv("DAWNR_SH_MODE", request.param)
    return request.param


def test_a_command_that_changes_nothing_is_a_read_and_runs_unasked(tmp_path):
    work, harness, agent, asked = agent_in(tmp_path, **{"a.txt": "one\n", "b.txt": "two\n"})
    with harness:
        r = harness.call("sh", {"command": "cat a.txt b.txt | wc -l; ls"})
    assert not r.is_error and r.text.startswith("exit 0\n2\n") and "a.txt" in r.text and asked == []
    assert r.trust == "untrusted" and agent.ops.journal.entries() == [] and os.listdir(tmp_path / "state" / "sh") == []


def test_what_a_command_changed_is_the_reason_it_is_asked_for_and_no_means_the_folder_is_as_it_was(tmp_path):
    work, harness, agent, asked = agent_in(tmp_path, approve=False, **{"a.txt": "one\n", "b.txt": "two\n"})
    with harness:
        r = harness.call("sh", {"command": "mv a.txt renamed.txt && echo x >> b.txt && mkdir new"})
    assert asked == ["it would change 4: new folder here/new; change here/b.txt; create here/renamed.txt; remove here/a.txt"]
    assert sorted(os.listdir(work)) == ["a.txt", "b.txt"] and (work / "b.txt").read_text() == "two\n"
    assert agent.ops.journal.entries() == [] and r.is_error


def test_approved_the_changes_are_applied_through_the_journal_and_go_back_together(tmp_path):
    work, harness, agent, asked = agent_in(tmp_path, **{"a.txt": "one\n", "b.txt": "two\n", "old/c.txt": "three\n"})
    with harness:
        r = harness.call("sh", {"command": "mv a.txt renamed.txt && echo x >> b.txt && mkdir -p sub/deep && printf '#!/bin/sh\\n' > sub/deep/run.sh"
                                           " && chmod +x sub/deep/run.sh && mv old gone && unlink gone/c.txt && rmdir gone"})
        assert not r.is_error and "Applied " in r.text and len(asked) == 1
        assert sorted(str(p.relative_to(work)) for p in work.rglob("*")) == ["b.txt", "renamed.txt", "sub", "sub/deep", "sub/deep/run.sh"]
        assert (work / "b.txt").read_text() == "two\nx\n" and (work / "renamed.txt").read_text() == "one\n"
        assert os.access(work / "sub/deep/run.sh", os.X_OK)
        rows = agent.ops.journal.entries()
        assert len({row["group"] for row in rows}) == 1 and {row["action"] for row in rows} == {"mkdir", "rmdir", "sh"}
        said = cli.undo(agent)                                  # the person's /undo: the whole command, last change first
        assert "not undone" not in said
        assert sorted(str(p.relative_to(work)) for p in work.rglob("*")) == ["a.txt", "b.txt", "old", "old/c.txt"]
        assert (work / "b.txt").read_text() == "two\n" and (work / "old/c.txt").read_text() == "three\n"
        assert cli.undo(agent) == "nothing to undo"


def test_the_command_cannot_reach_the_network_write_outside_the_folder_or_read_a_secret(tmp_path, monkeypatch):
    # the sandbox puts an empty /tmp over the real one, so the pretend home is made beside the real one
    import tempfile
    base = Path(tempfile.mkdtemp(prefix=".dawnr-shell-test-", dir=os.path.expanduser("~")))
    try:
        home, outside = base / "home", base / "outside.txt"
        (home / ".ssh").mkdir(parents=True)
        (home / ".ssh" / "id").write_text("PRIVATE KEY\n")
        (home / "notes.txt").write_text("not a secret\n")
        outside.write_text("mine\n")
        monkeypatch.setenv("HOME", str(home))
        work, harness, agent, asked = agent_in(tmp_path, **{"a.txt": "one\n"})
        with harness:
            r = harness.call("sh", {"command": f"echo hacked > {outside} ; cat {home}/.ssh/id ; cat {home}/notes.txt ; "
                                               "python3 -c \"import urllib.request; urllib.request.urlopen('http://93.184.216.34', timeout=3)\" ; echo end"})
        assert outside.read_text() == "mine\n" and "Read-only file system" in r.text      # the rest of the disk is read-only
        assert "PRIVATE KEY" not in r.text and "not a secret" in r.text                    # read, but for the secret folders
        assert "end" in r.text and "unreachable" in r.text and asked == []                  # and there is no network
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_what_a_tool_writes_into_its_own_cache_is_not_a_change_and_removing_a_cache_still_is(tmp_path):
    work, harness, agent, asked = agent_in(tmp_path, **{"mod.py": "def f():\n    return 1\n", "t.py": "from mod import f\nprint('OK', f())\n"})
    with harness:
        r = harness.call("sh", {"command": "python3 t.py"})        # python writes __pycache__/mod.*.pyc as it imports
        assert r.text.startswith("exit 0\nOK 1") and asked == [] and sorted(os.listdir(work)) == ["mod.py", "t.py"]
        (work / "__pycache__").mkdir()
        (work / "__pycache__" / "old.pyc").write_bytes(b"x")
        r = harness.call("sh", {"command": "rm -r __pycache__ && echo kept > notes.txt"})
    assert len(asked) == 1 and "remove here/__pycache__/old.pyc" in asked[0] and "create here/notes.txt" in asked[0], asked
    assert sorted(os.listdir(work)) == ["mod.py", "notes.txt", "t.py"]


def test_a_command_about_the_running_computer_is_sent_to_sysinfo_and_the_sandboxs_walls_are_named(tmp_path):
    work, harness, agent, asked = agent_in(tmp_path, **{"a.txt": "one\n"})
    with harness:
        assert harness.call("sh", {"command": "ps aux | grep firefox"}).text.startswith("exit ")      # nowhere else to look: it runs
        agent.shell.elsewhere = "To look at the computer call `sysinfo` with this line."
        r = harness.call("sh", {"command": "ps aux | grep firefox"})
        assert r.is_error and "`ps` reports on the running computer" in r.text and r.text.endswith("call `sysinfo` with this line.")
        assert not harness.call("sh", {"command": "python3 - << 'EOF'\ntop = 1; ps = 2\nprint(top + ps)\nEOF"}).is_error
        r = harness.call("sh", {"command": "touch /etc/dawnr-test-file"})
        assert "Read-only file system" in r.text and "Only the folder can be changed from here" in r.text and asked == []


def test_long_output_comes_back_as_its_start_and_its_end_with_what_was_left_out_counted(tmp_path):
    work, harness, agent, asked = agent_in(tmp_path, **{"a.txt": "one\n"})
    with harness:
        r = harness.call("sh", {"command": "seq 1 5000; echo THE-ERROR-AT-THE-END"})
    assert len(r.text) < 4300 and r.text.startswith("exit 0\n1\n2\n") and r.text.rstrip().endswith("THE-ERROR-AT-THE-END")
    assert " lines (" in r.text and "characters) not shown]" in r.text


def test_a_secret_in_the_folder_is_not_there_for_a_command_and_is_not_taken_for_removed(tmp_path, mode):
    work, harness, agent, asked = agent_in(tmp_path, **{"a.txt": "one\n", ".env": "TOKEN=abc123\n", "keys/id_rsa": "PRIVATE\n"})
    with harness:
        assert agent.shell.mode == mode
        r = harness.call("sh", {"command": "cat .env keys/id_rsa; ls -a; echo two > b.txt"})
    assert "abc123" not in r.text and "PRIVATE" not in r.text
    assert asked == ["it would change 1: create here/b.txt"]                               # and the secrets were not "removed"
    assert (work / ".env").read_text() == "TOKEN=abc123\n" and (work / "keys/id_rsa").read_text() == "PRIVATE\n" and (work / "b.txt").exists()


def test_inside_a_command_the_folder_also_answers_to_the_name_the_file_tools_give_it(tmp_path):
    work, harness, agent, asked = agent_in(tmp_path, **{"a.txt": "one\n"})
    with harness:
        r = harness.call("sh", {"command": "cat here/a.txt && mv here/a.txt here/b.txt"})
        assert not r.is_error and "one" in r.text and sorted(os.listdir(work)) == ["b.txt"]     # and that name is no change
        assert asked == ["it would change 2: create here/b.txt; remove here/a.txt"]


def test_a_socket_under_the_home_folder_cannot_be_reached_from_inside(tmp_path, monkeypatch):
    import socket
    import tempfile
    import threading
    base = Path(tempfile.mkdtemp(prefix=".dawnr-shell-test-", dir=os.path.expanduser("~")))
    try:
        home = base / "home"
        (home / "svc").mkdir(parents=True)
        path = str(home / "svc" / "agent.sock")
        server = socket.socket(socket.AF_UNIX)
        server.bind(path)
        server.listen(1)
        server.settimeout(4)
        heard = []

        def accept():
            try:
                conn, _ = server.accept()
                heard.append(conn.recv(100))
            except OSError:
                pass
        thread = threading.Thread(target=accept)
        thread.start()
        monkeypatch.setenv("HOME", str(home))
        work, harness, agent, asked = agent_in(tmp_path, **{"a.txt": "one\n"})
        with harness:
            assert agent.shell.sockets == [path]
            r = harness.call("sh", {"command": "python3 -c \"import socket; s = socket.socket(socket.AF_UNIX); "
                                               f"s.connect('{path}'); s.send(b'out'); print('CONNECTED')\""})
        thread.join()
        server.close()
        assert r.text.startswith("exit 1") and "ConnectionRefusedError" in r.text and heard == []
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_a_file_that_moved_since_the_command_ran_stops_the_apply_and_a_link_is_never_applied(tmp_path):
    work, harness, agent, asked = agent_in(tmp_path, **{"a.txt": "one\n"})
    with harness:
        run = agent.shell.run({"command": "echo two > a.txt; ln -s /etc/passwd link"})
        assert [c.line() for c in run.changes] == ["change here/a.txt", "not applied: here/link (a link is not applied)"]
        (work / "a.txt").write_text("the person edited it meanwhile\n")
        r = harness.call("sh", {"command": "echo two > a.txt; ln -s /etc/passwd link"})
    assert r.is_error and "changed since the command ran" in r.text
    assert (work / "a.txt").read_text() == "the person edited it meanwhile\n" and not (work / "link").exists()


def test_in_a_plan_the_dry_run_is_the_run_and_a_command_after_another_change_is_sent_back(tmp_path):
    work, harness, agent, asked = agent_in(tmp_path, **{"a.txt": "one\n"})
    with harness:
        p = agent.preview("sh", {"command": "sed -i s/one/uno/ a.txt"}, {})
        assert p.error is None and "it would change 1: change here/a.txt" in p.summary and p.writes == {("here", ("a.txt",)): b"uno\n"}
        assert (work / "a.txt").read_text() == "one\n"            # the dry run ran it, over the overlay
        later = agent.preview("sh", {"command": "cat a.txt"}, {("here", ("a.txt",)): b"x"})
        assert later.error and "a plan of its own" in later.error
        assert agent.preview("sh", {"command": ""}, {}).error and agent.shell.decide({"command": "true"})[0] == "allow"


def test_a_command_may_come_again_after_something_changed_but_not_the_changing_one_straight_after_itself(tmp_path):
    from dawnr_agent import AgentLoop, Budget, ScriptedPlanner
    work, harness, agent, asked = agent_in(tmp_path, **{"a.txt": "one\n"})
    more = {"steps": [{"tool": "sh", "arguments": {"command": "echo x >> a.txt"}}]}
    look = {"steps": [{"tool": "sh", "arguments": {"command": "cat a.txt"}}]}
    with harness:
        res = AgentLoop(agent, ScriptedPlanner([look, more, look, more, more, more, look]), budget=Budget(max_rounds=10)).run("x")
    assert (res.stop, len(res.rounds), res.steps_run) == ("no progress", 6, 4) and (work / "a.txt").read_text() == "one\nx\nx\n"


def test_yes_does_not_answer_for_a_plan_that_loses_a_files_contents(tmp_path):
    import json

    def turn(command):
        return {"choices": [{"message": {"role": "assistant", "content": "", "tool_calls": [
            {"id": "c", "type": "function", "function": {"name": "sh", "arguments": json.dumps({"command": command})}}]}}]}
    replies = [turn("mv a.txt c.txt"), {"choices": [{"message": {"content": "Renamed."}}]},
               turn("mv c.txt b.txt && mv b.txt c.txt"), {"choices": [{"message": {"content": "Swapped."}}]}]
    work = tmp_path / "work"
    work.mkdir()
    (work / "a.txt").write_text("alpha\n")
    (work / "b.txt").write_text("beta\n")
    said, asked = [], []

    def ask(prompt):
        asked.append(prompt)
        return "n"
    approve = cli.plan_approver(ask, said.append, yes=True)
    harness, agent = cli.build_agent(cli.default_config(work, state=tmp_path / "state"), plan_approver=approve)
    if agent.shell is None:
        harness.close()
        pytest.skip("no overlay sandbox here")
    approve.agent = agent
    with harness:
        meter = cli.Meter(lambda url, body, timeout=0: replies.pop(0))
        planner = cli.Planner(harness, agent, "x:1", "base", post=meter)
        cli.run_task(agent, planner, meter, "Rename a.txt to c.txt.", [], said.append)
        assert asked == [] and sorted(os.listdir(work)) == ["b.txt", "c.txt"]          # a rename loses nothing: --yes covers it
        cli.run_task(agent, planner, meter, "Swap b.txt and c.txt.", [], said.append)   # the model's wrong swap
        assert len(asked) == 1 and any("This removes here/b.txt and its contents are kept in no other file" in line for line in said)
        assert (work / "b.txt").read_text() == "beta\n" and (work / "c.txt").read_text() == "alpha\n"      # no: nothing ran


def test_the_assistant_offers_sh_by_default_and_not_the_tools_it_replaces(tmp_path):
    work = tmp_path / "w"
    work.mkdir()
    harness, agent = cli.build_agent(cli.default_config(work, state=tmp_path / "state"), plan_approver=lambda dry: False)
    with harness:
        names = harness.visible_names()
        assert {"fs_read", "fs_write", "fs_edit", "fs_list", "fs_search"} <= set(names) and "plan" not in names and "t" not in names
        assert ("sh" in names) == (agent.shell is not None)
