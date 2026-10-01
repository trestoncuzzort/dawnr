"""spec_experiment extract --promote-header (2026-10-01): a task that states `t 0` and is well
formed only as `t 1` is read as `t 1`, because v1 is a strict superset of v0 and the format line
is bookkeeping the body determines. Off by default; recorded on the answer; a task that is wrong
for another reason stays refused. EvalPlus normalises model output before grading
(github.com/evalplus/evalplus, evalplus/sanitize.py). No kernel."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import spec_experiment as se  # noqa: E402

V1_BODY_UNDER_V0 = ("```t\nt 0\ntask f(s: seq) returns (r: int)\n  ensures r == len(s)\n"
                    "{\n  r := len(s);\n}\n```")
WRONG_ANYWAY = ("```t\nt 0\ntask f(s: seq) returns (r: int)\n  ensures r == len(s)\n"
                "{\n  r := s;\n}\n```")


def one_answer(tmp: Path, tag: str, tid: int, fn: str, reply: str) -> None:
    raw = tmp / tag / "raw"
    raw.mkdir(parents=True)
    (tmp / tag / "tasks").mkdir()
    (raw / f"{tid}.json").write_text(json.dumps(
        {"task_id": tid, "fn": fn, "reply": reply, "done_reason": "stop", "model": "m",
         "pool_version": "v5", "prompt_version": "s1", "options": {}, "messages": []}), encoding="utf-8")


class PromoteHeader(unittest.TestCase):
    def run_extract(self, reply: str, promote: bool) -> dict:
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            pool = se.pool("v5")
            tid = sorted(pool)[0]
            one_answer(tmp, "x", tid, pool[tid]["fn"], reply)
            argv = ["extract", "--model", "x", "--pool", "v5"] + (["--promote-header"] if promote else [])
            with patch.object(se, "outdir", lambda tag: tmp / tag):
                se.main(argv)
            return json.loads((tmp / "x" / "extract.json").read_text())[str(tid)]

    def test_off_by_default_the_format_line_is_a_refusal(self):
        entry = self.run_extract(V1_BODY_UNDER_V0, promote=False)
        self.assertEqual(entry["stage"], "wf")
        self.assertNotIn("header_promoted", entry)

    def test_promoted_it_is_a_task_and_says_so(self):
        entry = self.run_extract(V1_BODY_UNDER_V0, promote=True)
        self.assertEqual(entry["stage"], "task")
        self.assertIs(entry["header_promoted"], True)
        self.assertEqual(entry["t"], 1)

    def test_a_task_wrong_for_another_reason_is_still_refused(self):
        entry = self.run_extract(WRONG_ANYWAY, promote=True)
        self.assertEqual(entry["stage"], "wf")
        self.assertNotIn("header_promoted", entry)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
