"""t/gen_fleet.sh writes its sentinel only for a complete answer set decoded with the flags it was given.

The fleet is run in a temporary tree with a stub generator standing in for
loop_locallm.py. The stub writes records in cmd_generate's shape and, under
environment switches, reproduces the three faults that fooled chains before:
a worker that exits 0 with an id unanswered (a killed shard already gets no
sentinel, so that case proves nothing), flags silently dropped (75a43fa), and a
stale record from another run sitting in raw/. No torch, no GPU.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent

STUB = r'''
import argparse, json, os, sys
from pathlib import Path
p = argparse.ArgumentParser()
sub = p.add_subparsers(dest="cmd", required=True)
g = sub.add_parser("generate")
g.add_argument("--model", required=True); g.add_argument("--tag", required=True)
g.add_argument("--split", required=True); g.add_argument("--ids-file", required=True)
g.add_argument("--temperature", type=float, required=True); g.add_argument("--top-k", type=int, default=20)
g.add_argument("--tokens", type=int, default=1200); g.add_argument("--seed", type=int, default=1)
g.add_argument("--examples", action="store_true")
a = p.parse_args()
ids = [int(x) for x in Path(a.ids_file).read_text().split()]
d = Path("t/out/spec-experiment") / a.tag / "raw"
d.mkdir(parents=True, exist_ok=True)
temperature = 0.5 if os.environ.get("STUB_DROP_FLAGS") else a.temperature
for tid in ids:
    if str(tid) == os.environ.get("STUB_SKIP_ID", ""):
        continue
    if (d / f"{tid}.json").exists():
        continue
    record = {"task_id": tid, "fn": "f", "model": f"locallm:{a.model}", "digest": "1 params",
              "pool_version": "v5", "prompt_version": "locallm-head",
              "options": {"temperature": temperature, "top_k": a.top_k, "max_new_tokens": a.tokens,
                          "tokenizer": "BPETokenizer", "seed": a.seed},
              "messages": [], "reply": "```t\n```", "done_reason": "length"}
    (d / f"{tid}.json").write_text(json.dumps(record, indent=1))
print(f"generate: {len(ids)} problems answered")
'''


class FleetSentinelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        t = self.root / "t"
        t.mkdir()
        shutil.copy(HERE / "gen_fleet.sh", t / "gen_fleet.sh")
        # the checks import the real spec_experiment and score_heldout; the generator is the stub.
        # Copies, not symlinks: spec_experiment locates t/out from its own resolved path, and a
        # symlink would point the check at the repository's answer sets instead of this tree's.
        for src in HERE.glob("*.py"):
            if src.name != "loop_locallm.py" and not src.name.startswith("test_"):
                shutil.copy(src, t / src.name)
        (t / "loop_locallm.py").write_text(STUB)
        for src in HERE.iterdir():              # verifiers/, tasks/ and the other data the modules import
            if src.is_dir() and src.name not in ("out", "__pycache__") and not src.name.startswith("."):
                (t / src.name).symlink_to(src)
        (t / "out" / "loop").mkdir(parents=True)
        (t / "out" / "loop" / "split.json").write_text(json.dumps({"eval_ids": [1, 2, 3, 4, 5, 6], "pool": "v5"}))
        (t / "out" / "model").mkdir()

    def fleet(self, *extra, env=None):
        environment = dict(os.environ, T_PY=sys.executable, T_SPLIT="t/out/loop/split.json",
                           PYTHONDONTWRITEBYTECODE="1")
        environment.update(env or {})
        r = subprocess.run(["bash", "t/gen_fleet.sh", "t/out/model", "demo", "2", "0 1", *extra],
                           cwd=self.root, env=environment, capture_output=True, text=True, timeout=120)
        return r.returncode, r.stdout + r.stderr

    def sentinel(self):
        return (self.root / "t" / "out" / "gen-demo.done").exists()

    def raw_ids(self):
        d = self.root / "t" / "out" / "spec-experiment" / "demo" / "raw"
        return sorted(int(p.stem) for p in d.glob("*.json")) if d.exists() else []

    def test_a_complete_set_with_the_flags_honoured_gets_the_sentinel(self):
        rc, out = self.fleet("--temperature", "0", "--tokens", "1200")
        self.assertEqual(rc, 0, out)
        self.assertTrue(self.sentinel(), out)
        self.assertEqual(self.raw_ids(), [1, 2, 3, 4, 5, 6])
        self.assertIn("6 of 6", out)

    def test_a_worker_that_exits_zero_with_an_id_unanswered_gets_no_sentinel(self):
        rc, out = self.fleet("--temperature", "0", env={"STUB_SKIP_ID": "3"})
        self.assertNotEqual(rc, 0)
        self.assertFalse(self.sentinel())
        self.assertIn("3", out.split("missing", 1)[1] if "missing" in out else "")

    def test_flags_the_worker_dropped_are_caught_from_the_records(self):
        rc, out = self.fleet("--temperature", "0", env={"STUB_DROP_FLAGS": "1"})
        self.assertNotEqual(rc, 0)
        self.assertFalse(self.sentinel())
        self.assertIn("temperature", out)

    def test_a_stale_record_from_another_run_is_refused(self):
        d = self.root / "t" / "out" / "spec-experiment" / "demo" / "raw"
        d.mkdir(parents=True)
        (d / "99.json").write_text(json.dumps({"task_id": 99, "model": "locallm:t/out/model",
                                               "options": {"temperature": 0.0}}))
        rc, out = self.fleet("--temperature", "0")
        self.assertNotEqual(rc, 0)
        self.assertFalse(self.sentinel())
        self.assertIn("99", out)

    def test_a_record_decoded_under_another_setting_is_refused(self):
        d = self.root / "t" / "out" / "spec-experiment" / "demo" / "raw"
        d.mkdir(parents=True)
        (d / "2.json").write_text(json.dumps({"task_id": 2, "model": "locallm:t/out/model",
                                              "options": {"temperature": 0.0, "top_k": 20, "max_new_tokens": 1200,
                                                          "tokenizer": "BPETokenizer", "seed": 7}}))
        rc, out = self.fleet("--temperature", "0")
        self.assertNotEqual(rc, 0)
        self.assertFalse(self.sentinel())
        self.assertIn("seed", out)

    def test_an_abbreviated_or_missing_temperature_flag_is_refused_before_launch(self):
        rc, out = self.fleet("--temp", "0")
        self.assertNotEqual(rc, 0)
        self.assertEqual(self.raw_ids(), [])
        self.assertIn("--temp", out)
        rc, out = self.fleet("--tokens", "1200")
        self.assertNotEqual(rc, 0)
        self.assertEqual(self.raw_ids(), [])
        self.assertIn("--temperature", out)


if __name__ == "__main__":
    unittest.main()
