"""The monitor must distinguish real work, incomplete data and actual proof results."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import lab_status as status


class LabStatusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / "repo"
        (self.root / "t").mkdir(parents=True)
        self.proc = self.base / "proc"
        self.proc.mkdir()
        (self.proc / "stat").write_text("btime 1000\n")
        self.events = self.base / "events.jsonl"

    def process(self, pid, argv, started=10, log=""):
        p = self.proc / str(pid)
        p.mkdir()
        (p / "cmdline").write_bytes(b"\0".join(x.encode() for x in argv) + b"\0")
        fields = ["S"] + ["0"] * 21
        fields[19] = str(int(started * os.sysconf("SC_CLK_TCK")))
        (p / "stat").write_text(f"{pid} (python3) " + " ".join(fields))
        (p / "cwd").symlink_to(self.root)
        (p / "fd").mkdir()
        if log:
            output = self.root / f"run-{pid}.log"
            output.write_text(log)
            (p / "fd" / "1").symlink_to(output)
        return p

    def answer_set(self, tag, outcomes, cells=None, kernels=status.KERNELS):
        d = self.root / "t/out/spec-experiment" / tag
        (d / "raw").mkdir(parents=True)
        extract, tests = {}, {}
        for i, (name, outcome) in enumerate(outcomes.items()):
            (d / "raw" / f"{i}.json").write_text("{}")
            extract[str(i)] = {"stage": "task", "name": name}
            if outcome is not None:
                tests[str(i)] = {"name": name, "overall": outcome}
        (d / "extract.json").write_text(json.dumps(extract))
        (d / "tests.json").write_text(json.dumps(tests))
        lines = ["| task | " + " | ".join(kernels) + " |",
                 "|---|" + "---|" * len(kernels)]
        for name in outcomes:
            row = [cells.get(name, {}).get(k, "verified / refuted") if cells else "verified / refuted"
                   for k in kernels]
            lines.append("| " + name + " | " + " | ".join(row) + " |")
        (d / "kernels.md").write_text("\n".join(lines))
        return d

    def test_exact_seven_kernel_clean_excludes_flakes(self):
        d = self.answer_set("demo", {"mbpp_1__ok": "pass", "mbpp_2__flake": "pass"},
                            {"mbpp_2__flake": {"lean": "verified / refuted (FLAKED)"}})
        result = status.count_set(d)
        self.assertEqual(result["clean"], 1)
        self.assertEqual(result["problems"], ["mbpp_1"])
        d = self.answer_set("partial", {"mbpp_3__partial": "pass"}, kernels=("lean",))
        self.assertEqual(status.count_set(d)["clean"], 0)

    def test_zero_pass_failures_count_but_unchecked_does_not(self):
        d = self.answer_set("failures", {"mbpp_1__bad": "fail", "mbpp_2__unknown": None})
        result = status.count_set(d)
        self.assertEqual(result["passed"], 0)
        self.assertEqual(result["wrong"], 1)
        self.assertEqual(result["graded"], 2)

    def test_only_real_owned_python_scripts_are_jobs(self):
        self.process(101, ["python3", "-u", "t/loop_generate.py", "--tag", "current"], log="still working\n")
        self.process(102, ["bash", "-c", "python3 t/loop_generate.py --tag fake"])
        self.process(103, ["python3", "-c", "run('t/loop_generate.py')"])
        self.process(104, ["python3", "-u", "t/spec_experiment.py", "extract", "--model", "finished"])
        self.process(105, ["python3", "-u", "t/spec_experiment.py", "generate", "--tag", "api"])
        self.process(106, ["python3", "elsewhere/loop_generate.py", "--tag", "other"])
        runs = status.process_runs(self.root, self.proc)
        self.assertEqual({r["tag"] for r in runs}, {"current", "api"})
        self.assertEqual(runs[0]["started"], 1010)
        self.assertEqual(runs[0]["log"], "still working")
        self.assertEqual(status.process_runs(self.root, self.proc, os.getuid() + 1), [])

    def test_identity_does_not_confuse_two_tags_on_one_model(self):
        steps = [["a", "A", "", "python3 t/loop_generate.py --tag alpha --model shared", "", ""],
                 ["b", "B", "", "python3 t/loop_generate.py --tag beta --model shared", "", ""]]
        run = {"_script": "loop_generate.py",
               "_argv": ["python3", "t/loop_generate.py", "--tag", "beta", "--model", "shared"]}
        self.assertEqual(status.match_step(run, steps)[0], "b")

    def test_core_distributed_ranks_form_one_visible_training_run(self):
        (self.root / "locallm").mkdir()
        output = self.root / "locallm/out/core"
        output.mkdir(parents=True)
        (output / "run.json").write_text(json.dumps({"completed_steps": 25,
            "identity": {"training": {"steps": 100}}}))
        for pid in range(101, 105):
            self.process(pid, ["python3", "-u", "locallm/train_distributed.py", "--out", "locallm/out/core"])
        self.process(105, ["python3", "unrelated/train_distributed.py", "--out", "locallm/out/core"])
        runs = status.process_runs(self.root, self.proc)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["workers"], 4)
        self.assertEqual(runs[0]["progress"], ["25 of 100 training steps", 0.25])

    def test_explicit_ids_union_limit_and_missing_total(self):
        (self.root / "ids.txt").write_text("1\n2\n3\n")
        argv = ["--ids-file=ids.txt", "--ids", "3,4", "--limit", "3"]
        self.assertEqual(status.expected_answers(argv, self.root), 3)
        self.assertIsNone(status.expected_answers(["--limit", "50"], self.root))
        self.assertIsNone(status.expected_answers(["--ids-file", "missing"], self.root))

    def test_event_cursor_partial_lines_rotation_and_active_processes(self):
        self.process(101, ["python3", "t/run_par.py"])
        start = {"ev": "start", "pid": 101, "task": "live", "kernel": "lean", "t": 1011}
        dead = {"ev": "start", "pid": 999, "task": "dead", "kernel": "lean", "t": 1011}
        end = {"ev": "end", "pid": 102, "task": "done", "kernel": "lean", "t": 1012}
        self.events.write_text("\n".join(json.dumps(x) for x in (start, dead, end)) + "\n{" )
        first = status.event_snapshot(self.events, self.proc)
        self.assertEqual(first["active"], [start])
        self.assertEqual(first["items"], [end])
        second = status.event_snapshot(self.events, self.proc, first["cursor"])
        self.assertEqual(second["items"], [])
        self.assertEqual(second["active"], [start])
        self.events.unlink()
        self.events.write_text(json.dumps(end) + "\n")
        rotated = status.event_snapshot(self.events, self.proc, first["cursor"])
        self.assertEqual(rotated["items"], [end])
        self.assertEqual(rotated["active"], [])

    def test_reused_process_number_cannot_resurrect_old_check(self):
        self.process(101, ["python3", "t/run_par.py"], started=100)
        self.events.write_text(json.dumps({"ev": "start", "pid": 101, "task": "old",
                                          "kernel": "lean", "t": 1010}) + "\n")
        self.assertEqual(status.event_snapshot(self.events, self.proc)["active"], [])

    def test_snapshot_includes_dynamic_work_raw_counts_and_current_score(self):
        (self.root / "ids.txt").write_text("1\n2\n3\n")
        self.process(101, ["python3", "t/loop_generate.py", "--tag", "new-round", "--ids-file", "ids.txt"])
        self.answer_set("new-round", {"mbpp_1__ok": "pass"})
        out = self.root / "t/out"
        (out / "score-r6.md").write_text("latest score")
        (out / "score-r4.md").write_text("old score")
        got = status.snapshot(self.root, self.proc, include_gpu=False, events_path=self.events)
        self.assertEqual(got["runs"][0]["key"], "run:101")
        self.assertEqual(got["runs"][0]["total"], 3)
        self.assertEqual(got["results"]["sets"][0][1]["answers"], 1)
        self.assertEqual(got["results"]["sets"][0][1]["total"], 3)
        self.assertGreater(got["results"]["sets"][0][1]["updated"], 0)
        self.assertIn("latest score", got["results"]["text"])
        self.assertNotIn("old score", got["results"]["text"])
        self.assertNotIn("_argv", got["runs"][0])
        json.dumps(got)

    def test_followup_is_visible_without_being_a_gpu_job(self):
        self.process(101, ["python3", "-u", "private/finish_existing.py"])
        logs = self.root / "t/runs/2026-09-19/logs"
        logs.mkdir(parents=True)
        (logs / "finish-existing-status.json").write_text(json.dumps({
            "pid": 101, "heartbeat": datetime.now(timezone.utc).isoformat(), "jobs": 8,
            "source_hashes": {"private": "unrelated"},
            "tags": {"demo": {"raw": 4, "expected": 232, "state": "waiting"}}}))
        got = status.snapshot(self.root, self.proc, include_gpu=False, events_path=self.events)
        self.assertTrue(got["followup"]["alive"])
        self.assertEqual(got["followup"]["tags"]["demo"]["raw"], 4)
        self.assertEqual(got["runs"], [])
        self.assertEqual(got["warnings"], [])
        self.assertNotIn("source_hashes", got["followup"])


if __name__ == "__main__":
    unittest.main()
