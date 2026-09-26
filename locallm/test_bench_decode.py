"""bench_decode.py on a CPU: fixed threads, alternating order, load and parity recorded."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from bench_decode import summarize  # noqa: E402


class SummaryTests(unittest.TestCase):
    def test_pairs_each_repeat_and_takes_the_wider_spread_as_noise(self):
        rows = [{"repeat": 0, "cached": False, "seconds": 4.0, "greedy_equal": True},
                {"repeat": 0, "cached": True, "seconds": 1.0, "greedy_equal": True},
                {"repeat": 1, "cached": False, "seconds": 6.0, "greedy_equal": True},
                {"repeat": 1, "cached": True, "seconds": 1.0, "greedy_equal": True},
                {"repeat": 2, "cached": False, "seconds": 5.0, "greedy_equal": True},
                {"repeat": 2, "cached": True, "seconds": 1.1, "greedy_equal": True}]
        summary = summarize(rows, tokens=10)
        self.assertEqual(summary["paired_speedups"], [4.0, 6.0, 5.0 / 1.1])
        self.assertAlmostEqual(summary["speedup"], 5.0)
        self.assertAlmostEqual(summary["noise"], (6.0 - 4.0) / 5.0)
        self.assertAlmostEqual(summary["uncached_ms_per_step"], 500.0)
        self.assertAlmostEqual(summary["cached_ms_per_step"], 100.0)
        self.assertTrue(summary["greedy_equal"])


class CpuRunTests(unittest.TestCase):
    def test_cpu_run_records_threads_order_load_and_parity(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "bench.json"
            env = {**os.environ, "CUDA_VISIBLE_DEVICES": ""}
            done = subprocess.run(
                [sys.executable, str(HERE / "bench_decode.py"), "--device", "cpu", "--architecture", "gpt",
                 "--layers", "1", "--width", "16", "--heads", "2", "--vocab", "43", "--context", "8",
                 "--prefix", "3", "--tokens", "9", "--repeats", "2", "--threads", "1",
                 "--order", "alternate", "--out", str(out)],
                capture_output=True, text=True, timeout=300, cwd=str(HERE), env=env)
            self.assertEqual(done.returncode, 0, done.stderr[-2000:])
            report = json.loads(out.read_text())
        self.assertEqual(report["threads"], 1)
        self.assertEqual([row["cached"] for row in report["runs"]], [False, True, False, True])
        self.assertEqual(report["cached_equals_uncached"], {"gpt": True})
        self.assertTrue(all(row["greedy_equal"] for row in report["runs"]))
        # prefix 3 + 9 tokens crosses the 8-token window: the cached path prefills
        # once, grows its cache to 8 keys, then rebuilds the full window on each
        # of the last three steps
        cached_check = next(check for check in report["work_checks"] if check["cached"])
        self.assertEqual(cached_check["multi_token_steps"], 4)
        self.assertEqual(len(report["summary"]["gpt"]["paired_speedups"]), 2)
        if hasattr(os, "getloadavg"):
            self.assertEqual(len(report["load_average_start"]), 3)
            self.assertTrue(all(row["load_1min"] is not None for row in report["runs"]))


if __name__ == "__main__":
    unittest.main()
