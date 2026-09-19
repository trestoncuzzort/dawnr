"""Exercise GPU control commands with fake SSH and an isolated process table.

No real SSH connection, signal, GPU command, or model launch is performed.
Run this test on the lab workstation, like the other project checks.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("lab_gpu.sh")
FAKE_TOOL = r'''#!/usr/bin/env python3
import json, os, re, subprocess, sys
from pathlib import Path
name = Path(sys.argv[0]).name
args = sys.argv[1:]
root = Path(os.environ["GPU_TEST_ROOT"])
state_file = root / "processes.json"
state = json.loads(state_file.read_text())
with (root / "calls.jsonl").open("a") as out:
    out.write(json.dumps([name, args]) + "\n")
if name == "ssh":
    command = args[-1]
    if os.environ.get("GPU_TEST_CAPTURE_ONLY"):
        sys.exit(0)
    state.append({"pid": 98, "uid": 1001, "cmd": "bash -c " + command})
    state_file.write_text(json.dumps(state))
    sys.exit(subprocess.run(["bash", "-c", command]).returncode)
if name == "id":
    assert args == ["-u"], args
    print(1001)
elif name in ("pkill", "pgrep"):
    # Missing or wrong user filters must fail the test, never fall back to a real tool.
    assert "-u" in args, args
    uid = int(args[args.index("-u") + 1])
    assert uid == 1001, uid
    pattern = re.compile(args[-1].replace("[[:space:]]", r"\s"))
    matches = [p for p in state if p["uid"] == uid and pattern.search(p["cmd"])]
    if name == "pkill":
        killed = [p for p in matches if not p.get("survive") and
                  ("-9" in args or not p.get("needs_kill"))]
        state_file.write_text(json.dumps([p for p in state if p not in killed]))
    elif "-fc" in args:
        print(len(matches))
    else:
        for p in matches:
            print(p["pid"], p["cmd"])
    sys.exit(0 if matches else 1)
elif name == "nvidia-smi":
    if "--query-compute-apps=pid,used_memory" in args:
        print("15, 1200 MiB\n16, 500 MiB")
    else:
        print("0, 1700 MiB, 48000 MiB, 0 %")
elif name == "ps":
    pid = int(args[args.index("-p") + 1])
    for p in state:
        if p["pid"] == pid:
            print(" ", p["uid"])
elif name not in ("sleep", "ls", "tail", "rsync", "systemctl"):
    raise AssertionError("Unexpected fake tool: " + name)
'''


class LabGpuTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        bindir = self.root / "bin"
        bindir.mkdir()
        for name in ("ssh", "id", "pkill", "pgrep", "nvidia-smi", "ps", "sleep", "ls", "tail",
                     "rsync", "systemctl"):
            tool = bindir / name
            tool.write_text(FAKE_TOOL)
            tool.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.root), T_LAB="test-target",
                        GPU_TEST_ROOT=str(self.root), PATH=f"{bindir}:{os.environ['PATH']}")
        self.processes = [
            {"pid": 10, "uid": 1001, "cmd": "python3 t/loop_generate.py --tag example"},
            {"pid": 11, "uid": 1001, "cmd": "python3 t/loop_train.py", "needs_kill": True},
            {"pid": 12, "uid": 1001, "cmd": "python3 t/spec_experiment.py generate --tag example"},
            {"pid": 13, "uid": 1001, "cmd": "/venv/bin/vllm serve example"},
            {"pid": 14, "uid": 1001, "cmd": "VLLM::Worker_TP0"},
            {"pid": 15, "uid": 10010, "cmd": "python3 t/loop_train.py"},
            {"pid": 16, "uid": 1001, "cmd": "python3 unrelated.py"},
            {"pid": 17, "uid": 1001, "cmd": "python3 t/loop_generate.pyx"},
            {"pid": 18, "uid": 10010, "cmd": "VLLM::Worker_TP0"},
            {"pid": 19, "uid": 1001, "cmd": "python3 locallm/train_distributed.py --out locallm/out/core"},
            {"pid": 20, "uid": 1001, "cmd": "python3 locallm/train.py --out locallm/out/single"},
        ]

    def run_command(self, command, capture_only=False):
        (self.root / "processes.json").write_text(json.dumps(self.processes))
        env = dict(self.env)
        if capture_only:
            env["GPU_TEST_CAPTURE_ONLY"] = "1"
        return subprocess.run(["bash", str(SCRIPT), command], cwd=self.root,
                              env=env, capture_output=True, text=True, timeout=10)

    def calls(self):
        return [json.loads(line) for line in (self.root / "calls.jsonl").read_text().splitlines()]

    def test_stop_covers_current_jobs_and_preserves_other_users_and_shell(self):
        result = self.run_command("stop")
        self.assertEqual(result.returncode, 0, result.stderr)
        remaining = json.loads((self.root / "processes.json").read_text())
        self.assertEqual({p["pid"] for p in remaining}, {15, 16, 17, 18, 98})
        signals = [args for name, args in self.calls() if name == "pkill"]
        self.assertEqual(len(signals), 2)
        self.assertNotIn("-9", signals[0])
        self.assertIn("-9", signals[1])
        self.assertIn("ours still running: 0", result.stdout)
        self.assertIn("16, 500 MiB", result.stdout)
        self.assertNotIn("15, 1200 MiB", result.stdout)

    def test_stop_reports_failure_if_a_target_survives(self):
        self.processes[0]["survive"] = True
        result = self.run_command("stop")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ours still running: 1", result.stdout)
        self.assertNotIn("stopped this remote account", result.stdout)

    def test_status_lists_current_jobs_only_for_the_remote_uid(self):
        result = self.run_command("status")
        self.assertEqual(result.returncode, 0, result.stderr)
        for pid in range(10, 15):
            self.assertRegex(result.stdout, rf"(?m)^{pid} ")
        for pid in (15, 16, 17, 18, 98):
            self.assertNotRegex(result.stdout, rf"(?m)^{pid} ")

    def test_start_does_not_modify_the_remote_git_checkout(self):
        result = self.run_command("start", capture_only=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = [args[-1] for name, args in self.calls() if name == "ssh"]
        self.assertGreater(len(commands), 1)
        for command in commands:
            self.assertNotRegex(command, r"\bgit\b")
        self.assertIn("test -d ~/tup", commands[0])

    def test_takeover_scopes_signals_and_separates_remote_stop_from_launch(self):
        output = self.root / "t" / "out" / "loop"
        output.mkdir(parents=True)
        (output / "apps-ids.txt").write_text("1\n")
        result = self.run_command("takeover", capture_only=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        local_signals = [args for name, args in calls if name == "pkill"]
        self.assertEqual(len(local_signals), 1)
        self.assertIn("-u", local_signals[0])
        commands = [args[-1] for name, args in calls if name == "ssh"]
        self.assertEqual(len(commands), 2)
        self.assertIn("pkill -u $(id -u)", commands[0])
        self.assertNotIn("setsid", commands[0])
        self.assertNotIn("pkill", commands[1])


if __name__ == "__main__":
    unittest.main()
