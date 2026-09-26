"""The raw-record writer, the per-tag generator lock, and the extractor's refusal of torn records.

Written against the 15 torn qwen235-v6new records of 2026-09-20 (t/DATA-r12.md):
two generators on one tag, each writing raw/<id>.json with a truncating open and
no rename. Sources: docs.python.org/3/library/os.html#os.replace (atomic rename),
docs.python.org/3/library/fcntl.html (flock), docs.python.org/3/library/json.html.
"""
import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spec_experiment as se  # noqa: E402

GOOD_REPLY = (
    "Here it is.\n```t\n"
    "t 1\n"
    "task f(a: int) returns (r: int)\n"
    "  ensures r == a\n"
    "{\n"
    "  r := a;\n"
    "}\n"
    "```\n"
)


def record(tid: int, reply: str = GOOD_REPLY) -> dict:
    return {"task_id": tid, "fn": "f", "model": "m", "digest": "d", "pool_version": "v1",
            "prompt_version": "v1", "options": {"temperature": 0, "seed": 1}, "messages": [],
            "reply": reply, "prompt_tokens": 1, "reply_tokens": 1, "eval_s": 0.0, "wall_s": 0.0,
            "done_reason": "stop"}


class WriteRecordTests(unittest.TestCase):
    def test_a_record_lands_whole_and_leaves_no_temp_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw"
            raw.mkdir()
            se.write_record(raw / "7.json", record(7, "x" * 5000))
            self.assertEqual(json.loads((raw / "7.json").read_text())["task_id"], 7)
            self.assertEqual([p.name for p in raw.iterdir()], ["7.json"])

    def test_the_writer_replaces_an_existing_file_rather_than_appending_to_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw"
            raw.mkdir()
            se.write_record(raw / "7.json", record(7, "long " * 400))
            se.write_record(raw / "7.json", record(7, "short"))
            text = (raw / "7.json").read_text()
            self.assertEqual(json.loads(text)["reply"], "short")   # no "Extra data" tail


class TagLockTests(unittest.TestCase):
    def test_a_second_generator_on_the_same_tag_is_refused_until_the_first_closes(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "raw").mkdir()
            first = se.tag_lock(d)
            self.assertIsNotNone(first)
            self.assertIsNone(se.tag_lock(d))
            first.close()
            again = se.tag_lock(d)
            self.assertIsNotNone(again)
            again.close()

    def test_cmd_generate_refuses_by_name_while_the_lock_is_held(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(se, "OUT_ROOT", Path(tmp)):
            d = se.outdir("locktest")
            held = se.tag_lock(d)
            try:
                args = argparse.Namespace(tag="locktest", model="m")   # must refuse before it reads a pool
                self.assertEqual(se.cmd_generate(args), 2)
            finally:
                held.close()
            self.assertEqual(sorted(p.name for p in (d / "raw").iterdir()), [se.LOCK_NAME])

    def test_the_lock_and_temp_files_are_not_raw_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw"
            raw.mkdir()
            (raw / se.LOCK_NAME).write_text("")
            (raw / ".9.json.123.tmp").write_text("{")
            se.write_record(raw / "9.json", record(9))
            self.assertEqual([p.name for p in raw.glob("*.json")], ["9.json"])


class ExtractTagTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)
        (self.d / "raw").mkdir()
        (self.d / "tasks").mkdir()

    def write_raw(self, rec: dict, tail: str = "") -> Path:
        p = self.d / "raw" / f"{rec['task_id']}.json"
        p.write_text(json.dumps(rec, indent=1) + tail, encoding="utf-8")
        return p

    def test_a_torn_record_refuses_the_whole_extraction_and_writes_nothing(self):
        self.write_raw(record(5))
        self.write_raw(record(6), tail='", "wall_s": 61.2, "done_reason": "stop"\n}')
        with patch("sys.stderr"):
            self.assertEqual(se.extract_tag(self.d), 2)
        self.assertFalse((self.d / "extract.json").exists())
        self.assertEqual(list((self.d / "tasks").iterdir()), [])

    def test_a_clean_set_extracts_and_a_stale_task_file_is_removed(self):
        (self.d / "tasks" / "mbpp_99__old.json").write_text("{}")
        self.write_raw(record(5))
        self.assertEqual(se.extract_tag(self.d), 0)
        results = json.loads((self.d / "extract.json").read_text())
        self.assertEqual(results["5"]["stage"], "task")
        self.assertEqual(results["5"]["name"], "mbpp_5__f")
        self.assertEqual(sorted(p.name for p in (self.d / "tasks").iterdir()), ["mbpp_5__f.json"])


if __name__ == "__main__":
    unittest.main()
