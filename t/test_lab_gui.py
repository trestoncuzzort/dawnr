"""Remote monitor UI checks. Run with a Tk display on the lab workstation."""
import os
import tkinter as tk
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import lab


class ConfigurationTests(unittest.TestCase):
    def test_unresolved_or_flaky_twin_is_not_reported_as_proven(self):
        self.assertEqual(lab.verdict("verified", "refuted")[1], "Proven")
        self.assertEqual(lab.verdict("verified", "verified")[1], "Promise too weak")
        self.assertEqual(lab.verdict("verified", "refuted", False)[1], "Inconsistent")
        for twin in ("timeout", "unproved", "abstain", "malformed", ""):
            self.assertEqual(lab.verdict("verified", twin)[1], "Twin unresolved")

    def test_private_config_is_data_not_shell(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "lab-workstation.conf").write_text("export T_LAB='user@example.invalid' # private\n")
            with patch.object(lab, "HERE", path), patch.dict(os.environ, {"T_LAB": ""}):
                self.assertEqual(lab.lab_target(), "user@example.invalid")
            with patch.dict(os.environ, {"T_LAB": "-oProxyCommand=anything"}):
                self.assertEqual(lab.lab_target(), "")


class RemoteGuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(str(exc))
        self.root.withdraw()
        self.errors = []
        self.root.report_callback_exception = lambda *error: self.errors.append(error)
        with patch.object(lab, "lab_target", return_value="user@example.invalid"), \
             patch.object(lab.Lab, "watch_lab"), \
             patch.object(lab.subprocess, "run", side_effect=AssertionError("local completion command")):
            self.app = lab.Lab(self.root, "Collect data")

    def tearDown(self):
        if hasattr(self, "root"):
            for callback in self.root.tk.call("after", "info"):
                self.root.after_cancel(callback)
            self.root.destroy()

    @staticmethod
    def snapshot():
        return {"version": 1, "runs": [
            {"key": "run:123", "pid": 123, "title": "Generate: model-a", "tag": "model-a",
             "kind": "generate", "started": 1, "progress": ["12 of 232 answers", 12 / 232], "log": "answer 12"}],
            "results": {"sets": [["model-a", {"answers": 12, "tasks": 4, "passed": 3, "graded": 2,
                         "clean": 1, "wrong": 0, "problems": ["mbpp_1"]}]],
                        "totals": {"tasks": 4, "passed": 3, "graded": 2, "clean": 1, "wrong": 0},
                        "n_problems": 1, "text": "current pool"},
            "events": {"active": [{"task": "current", "kernel": "lean", "t": 1, "pid": 456}],
                       "items": [{"ev": "end", "task": "finished", "kernel": "spark", "t": 2,
                                  "real": "verified", "twin": "refuted"}]},
            "gpus": [{"index": 0, "used_mb": 4, "total_mb": 48, "utilization": 20}], "warnings": []}

    def test_remote_snapshot_populates_all_tabs_without_local_compute(self):
        with patch.object(lab.subprocess, "run", side_effect=AssertionError("local subprocess")), \
             patch.object(lab, "memory_mb", side_effect=AssertionError("remote PID read locally")):
            self.app.show_lab_snapshot(self.snapshot())
            self.app.tick()
            self.root.update()
        self.assertNotIn("Test a model", self.app.pages)
        self.assertEqual(self.app.remote_runs.item("123", "values")[2], "12 of 232 answers")
        self.assertEqual(self.app.log_text.get("1.0", "end").strip(), "answer 12")
        self.assertEqual(len(self.app.res_table.get_children()), 2)
        self.assertEqual(self.app.counts["proven"], 1)
        self.assertEqual(len(self.app.now.get_children()), 1)
        self.assertFalse(self.errors)

    def test_disconnect_keeps_data_and_reconnect_clears_error(self):
        self.app.show_lab_snapshot(self.snapshot())
        self.app.q.put(("lab_error", "Lab unavailable; last snapshot retained"))
        self.app.drain()
        self.assertIn("unavailable", self.app.lab_error)
        self.assertTrue(self.app.remote_runs.exists("123"))
        empty = self.snapshot()
        empty["runs"] = []
        empty["events"] = {"items": [], "active": []}
        self.app.q.put(("lab_snapshot", empty))
        self.app.drain()
        self.assertEqual(self.app.lab_error, "")
        self.assertEqual(self.app.remote_runs.get_children(), ())
        self.assertEqual(self.app.running, {})
        self.assertFalse(self.errors)


if __name__ == "__main__":
    unittest.main()
