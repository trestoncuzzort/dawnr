"""CPU-only fixture tests for study wake conditions and process identity."""
import json
import os
from pathlib import Path
import tempfile
import unittest

import probe_pretraining_study as probe


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.proc = self.root / "proc"
        self.proc.mkdir()
        (self.proc / "uptime").write_text("1100 0\n")
        self.output = self.root / "study"
        self.output.mkdir()
        self.pid = 123
        self.process(self.pid, "run_pretraining_study.py", self.output)
        self.now = 10000

    def tearDown(self):
        self.temporary.cleanup()

    def process(self, pid, script, output, *, start=100000, shell=False):
        root = self.proc / str(pid)
        root.mkdir(exist_ok=True)
        fields = ["S"] + ["0"] * 18 + [str(start)] + ["0"] * 4
        (root / "stat").write_text(f"{pid} (python worker) " + " ".join(fields))
        argv = ["bash" if shell else "python3"]
        if script == "train_distributed.py":
            argv += ["-m", "torch.distributed.run", "--nproc-per-node=4"]
        argv += [str(probe.HERE / script), "--out", str(output)]
        (root / "cmdline").write_bytes(b"\0".join(value.encode() for value in argv) + b"\0")
        if not (root / "cwd").exists():
            (root / "cwd").symlink_to(self.root)

    def ledger(self, status="running", *, age=5, step=100):
        arm_output = self.output / "modern-seed1337"
        arm_output.mkdir(exist_ok=True)
        logs = self.output / "logs"
        logs.mkdir(exist_ok=True)
        log = logs / "arm.log"
        log.write_text("training\n")
        run = arm_output / "run.json"
        run.write_text(json.dumps({"completed_steps": step}))
        (arm_output / "metrics.jsonl").write_text(json.dumps({"step": step}) + "\npartial")
        ledger = {"status": status, "configuration": {"steps": 1000}, "active_arm": "modern-seed1337",
                  "arms": [{"id": "modern-seed1337", "out": "modern-seed1337", "status": "running",
                            "attempts": [{"launcher_pid": 456, "log": "logs/arm.log"}]}]}
        (self.output / "study.json").write_text(json.dumps(ledger))
        self.process(456, "train_distributed.py", arm_output)
        for path in (self.output / "study.json", run, arm_output / "metrics.jsonl", log):
            os.utime(path, (self.now - age, self.now - age))

    def inspect(self, **kwargs):
        return probe.inspect_study(self.output, self.pid, proc=self.proc, now=self.now, **kwargs)

    def test_running_progress_and_partial_last_metric(self):
        self.ledger()
        result = self.inspect()
        self.assertEqual(result["status"], "running")
        self.assertFalse(result["event"])
        self.assertEqual(result["progress"]["step"], 100)
        self.assertTrue(result["runner"]["argv_match"])
        self.assertTrue(result["launcher"]["argv_match"])
        self.assertEqual(result["activity"]["log"], "logs/arm.log")
        self.assertNotIn(str(self.root), json.dumps(result))

    def test_complete_ledger_takes_precedence_over_exited_runner(self):
        self.ledger(status="complete", step=1000)
        (self.proc / str(self.pid) / "cmdline").unlink()
        result = self.inspect()
        self.assertEqual(result["status"], "complete")
        self.assertTrue(result["event"])

    def test_wrong_shell_and_reused_pid_fail_identity(self):
        self.ledger()
        self.process(self.pid, "run_pretraining_study.py", self.output, shell=True)
        self.assertEqual(self.inspect()["reason"], "runner_missing_or_replaced")
        self.process(self.pid, "run_pretraining_study.py", self.output, start=100001)
        self.assertTrue(self.inspect(runner_start_ticks=100000)["event"])

    def test_log_activity_cannot_mask_stalled_training_progress(self):
        self.ledger(age=700)
        os.utime(self.output / "logs/arm.log", (self.now, self.now))
        first = self.inspect()
        self.assertEqual(first["status"], "stalled")
        self.assertEqual(first["reason"], "no_training_progress")
        self.now += 30
        self.assertEqual(first["event_fingerprint"], self.inspect()["event_fingerprint"])

    def test_dead_launcher_has_short_publication_grace(self):
        self.ledger(age=5)
        (self.proc / "456" / "cmdline").unlink()
        self.assertFalse(self.inspect()["event"])
        self.now += 20
        self.assertEqual(self.inspect()["reason"], "launcher_missing_or_replaced")

    def test_missing_ledger_distinguishes_startup_and_timeout(self):
        self.assertEqual(self.inspect()["status"], "starting")
        (self.proc / "uptime").write_text("1300 0\n")
        self.assertEqual(self.inspect()["reason"], "ledger_startup_timeout")


if __name__ == "__main__":
    unittest.main()
