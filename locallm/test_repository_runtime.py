"""Retired host actions stay unavailable across default and custom agent entry points."""
from pathlib import Path
from unittest import mock
import shutil

import pytest

from locallm import dawnr_cli as cli
from dawnr_agent.config import AgentConfigError
from dawnr_agent.system import SystemTools


def config(tmp_path):
    work = tmp_path / "project"
    work.mkdir()
    result = cli.default_config(work, state=tmp_path / "state")
    result["agent"].pop("shell", None)
    result["agent"]["commands"] = [{"argv": ["echo", "{arg}"], "network": False, "permission": "allow"}]
    result["permissions"]["run_command"] = "allow"
    return result


@pytest.mark.parametrize("command", ["xdg-open example.pdf", "systemctl --user restart example", "gsettings set example enabled true"])
@pytest.mark.parametrize("detach", [False, True])
def test_legacy_host_tool_is_a_refusal_even_with_act_enabled(command, detach):
    runner, starter = mock.Mock(), mock.Mock()
    tools = SystemTools(act=True, runner=runner, starter=starter)
    assert [tool.name for tool in tools.tools()] == ["sysinfo"]
    assert tools.decide({"command": command})[0] == "deny"
    assert tools.pc({"command": command, "detach": detach}, None).is_error
    runner.assert_not_called()
    starter.assert_not_called()


@pytest.mark.parametrize("retired", [{"system": True}, {"sandbox": "none"}])
def test_old_host_configuration_fails_explicitly_before_creating_state(tmp_path, retired):
    cfg = config(tmp_path)
    cfg["agent"].update(retired)
    with pytest.raises(AgentConfigError, match="retired|unsandboxed"):
        cli.build_agent(cfg)
    assert not (tmp_path / "state").exists()


@pytest.mark.parametrize("problem", ["bwrap is not installed", "namespace creation denied"])
def test_unavailable_sandbox_does_not_fall_back_to_host_command(tmp_path, problem):
    cfg = config(tmp_path)
    which = shutil.which
    def available(program, **kwargs):
        return None if program == "bwrap" and problem == "bwrap is not installed" else which(program, **kwargs)
    with mock.patch("dawnr_agent.config.shutil.which", side_effect=available), \
         mock.patch("dawnr_agent.config.Bwrap.probe", return_value=problem):
        harness, agent = cli.build_agent(cfg)
    with harness:
        runner = mock.Mock()
        agent.commands.runner = runner
        answer = harness.call("run_command", {"argv": ["echo", "hello"]})
        assert answer.is_error and "no command runs" in answer.text
        runner.assert_not_called()
        assert "pc" not in harness.visible_names()


def test_direct_command_handler_cannot_run_without_sandbox(tmp_path):
    cfg = config(tmp_path)
    with mock.patch("dawnr_agent.config.Bwrap.probe", return_value=None):
        harness, agent = cli.build_agent(cfg)
    with harness:
        agent.commands.sandbox = None
        runner = mock.Mock()
        agent.commands.runner = runner
        result = agent.commands.run_command({"argv": ["echo", "hello"]}, None)
        assert result.is_error and "sandbox is required" in result.text
        runner.assert_not_called()


@pytest.mark.parametrize("program", ["df", "bash"])
def test_repository_program_cannot_shadow_a_host_diagnostic(tmp_path, monkeypatch, program):
    cfg = config(tmp_path)
    root = Path(cfg["agent"]["roots"][0]["path"])
    marker = tmp_path / "unexpected-host-write"
    shadow = root / program
    shadow.write_text(f"#!/bin/sh\nprintf compromised > '{marker}'\n")
    shadow.chmod(0o755)
    monkeypatch.setenv("PATH", str(root) + ":/usr/bin:/bin")
    harness, agent = cli.build_agent(cfg)
    with harness:
        result = harness.call("sysinfo", {"command": "df -h"})
        assert not marker.exists(), "a repository file ran on the host through a read-only diagnostic"
        assert not result.is_error


@pytest.mark.parametrize("command", ["cat /proc/version", "head -n 5 /proc/meminfo", "cat /etc/os-release"])
def test_file_shaped_host_diagnostics_stay_on_sysinfo(command):
    from types import SimpleNamespace
    from dawnr_agent.system import look
    planner = SimpleNamespace(tools=[{"function": {"name": name}} for name in ("sysinfo", "sh")])
    assert look(command) is not None
    assert cli.Planner.route(planner, "sysinfo", command) == "sysinfo"
    assert cli.Planner.route(planner, "sysinfo", "cat here/build.log") == "sh"
    assert cli.Planner.route(planner, "pc", command) == "pc"
