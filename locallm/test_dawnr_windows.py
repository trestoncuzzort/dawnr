"""A Windows desktop reached from Ubuntu under WSL (2026-10-05): what the system layer lets look, refuses, and says
about such a machine; the lines the recipes give it; and the front door's routing of a Windows program's line."""
import os
import shutil

import pytest

from locallm import dawnr_cli as cli
from locallm.dawnr_agent import system
from locallm.dawnr_agent.recipes import recipes

LOOKS = {
    'powershell.exe -NoProfile -Command "Get-CimInstance Win32_Battery | Select-Object -ExpandProperty EstimatedChargeRemaining"': True,
    "powershell.exe -NoProfile -Command 'Get-Process | Sort-Object CPU -Descending | Select-Object -First 5 Name, CPU'": True,
    'powershell.exe -NoProfile -Command "Get-Service | Where-Object Status -eq Running | Measure-Object"': True,
    'powershell.exe -NoProfile -Command "(Get-CimInstance Win32_Battery).EstimatedChargeRemaining"': False,     # a call
    'powershell.exe -NoProfile -Command "Get-Content C:\\Users\\t\\notes.txt"': False,                           # a file
    'powershell.exe -NoProfile -Command "Get-Process | Stop-Process"': False,
    'powershell.exe -NoProfile -Command "Clear-RecycleBin -Force"': False,
    "powershell.exe -EncodedCommand ZwBl": False,
    'powershell.exe -NoProfile -Command "Get-Date; Remove-Item x"': False,
    "tasklist.exe": True, 'tasklist.exe /FI "IMAGENAME eq notepad.exe" /NH': True, "tasklist.exe /S server /U me": False,
    "tasklist.exe | grep -i notepad": True,
    "systeminfo.exe": True, "ipconfig.exe /all": True, "ipconfig.exe /flushdns": False, "whoami.exe": True, "hostname.exe": True,
    "tzutil.exe /g": True, 'tzutil.exe /s "UTC"': False,
    'reg.exe query "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize" /v AppsUseLightTheme': True,
    "reg.exe query HKCU\\Software\\SomeApp /v token": False, "reg.exe add HKCU\\x /v y /d 1": False,
    "netsh.exe wlan show interfaces": True, 'netsh.exe wlan show profile name="Home" key=clear': False, "netsh.exe wlan disconnect": False,
    "cmd.exe /c ver": True, "cmd.exe /c del x": False, "wslpath -w /home/t/report.pdf": True,
}


def test_windows_lines_that_only_look_are_told_from_the_rest():
    wrong = [(line, want) for line, want in LOOKS.items() if (system.look(line) is not None) != want]
    assert wrong == []


def test_windows_lines_are_refused_for_the_same_reasons_as_linux_ones():
    assert "administrator rights" in system.refusal("runas.exe /user:Administrator cmd")
    assert "administrator rights" in system.refusal('powershell.exe -Command "Start-Process cmd -Verb RunAs"')
    assert "secrets are kept (`key=clear`)" in system.refusal("netsh.exe wlan show profile name=Home key=clear")
    assert "secrets are kept (`.ssh`)" in system.refusal("type C:\\Users\\t\\.ssh\\id_rsa")
    assert "disks, partitions" in system.refusal("diskpart.exe")
    assert "sweeping a drive" in system.refusal("del /s /q C:\\Windows") and "sweeping a drive" in system.refusal('powershell.exe -Command "Remove-Item -Recurse -Force C:\\Users"')
    assert "network is off" in system.refusal("curl.exe https://x.y", offline=True)
    assert "network is off" in system.refusal('powershell.exe -Command "Invoke-WebRequest https://x.y"', offline=True)
    # what a Windows desktop is asked to do goes through `pc`, asked for, and is not refused
    assert system.refusal('explorer.exe "$(wslpath -w ./report.pdf)"') is None
    assert system.refusal("powershell.exe -NoProfile -Command 'Clear-RecycleBin -Force'") is None
    assert system.refusal("rundll32.exe user32.dll,LockWorkStation") is None
    assert system.refusal("tasklist.exe") == "that only looks, and needs nobody's yes: call `sysinfo` with it"


def test_the_sentence_about_the_computer_says_when_windows_is_the_desktop(monkeypatch):
    monkeypatch.setattr(system.os, "uname", lambda: os.uname_result(("Linux", "pc", "6.18.40.1-microsoft-standard-WSL2", "#1", "x86_64")))
    monkeypatch.setattr(system.shutil, "which", lambda name: "/mnt/c/WINDOWS/explorer.exe" if name == "explorer.exe" else None)
    monkeypatch.delenv("XDG_CURRENT_DESKTOP", raising=False)
    said = system.facts()
    assert "desktop Windows under WSL." in said and "called by name with .exe" in said and "wslpath -w PATH" in said
    assert "explorer.exe" in recipes(said, has=lambda p: p.endswith(".exe") or p == "wslpath") and "xdg-open" not in recipes(said, has=lambda p: True)
    # without interop (a person can turn it off) there is no desktop here
    monkeypatch.setattr(system.shutil, "which", lambda name: None)
    assert "no desktop session" in system.facts()


def test_a_windows_programs_line_is_routed_out_of_the_sandbox(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    cfg = cli.default_config(work, state=tmp_path / "state")
    harness, agent = cli.build_agent(cfg, plan_approver=cli.plan_approver(lambda prompt: "n", lambda *_: None))
    with harness:
        planner = cli.Planner(harness, agent, "nowhere:1", "base", look_first=False)
        offered = {t["function"]["name"] for t in planner.tools}
        if not {"sh", "pc", "sysinfo"} <= offered:
            pytest.skip("not every tool is offered here")
        assert planner.route("sh", "tasklist.exe | grep -i notepad") == "sysinfo"
        assert planner.route("sh", 'explorer.exe "$(wslpath -w ./report.pdf)"') == "pc"
        assert planner.route("sh", "powershell.exe -NoProfile -Command 'Clear-RecycleBin -Force'") == "pc"
        assert planner.route("sh", "python3 report.py") == "sh"
