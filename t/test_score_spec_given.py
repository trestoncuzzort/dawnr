"""t/score_spec_given.py (2026-10-01): each answer's gate is recorded, a redefined specification
never reaches the kernels, and a row the grader could not build a twin for is a missing
measurement, counted apart from unproved. No kernel, no model."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import score_spec_given as ssg  # noqa: E402
import spec_check  # noqa: E402
import student_rows  # noqa: E402
import surface  # noqa: E402

SRC = ("t 1\ngate recursion\ntask abs(x: int) returns (y: int)\n  ensures y >= 0\n  ensures y == abs_v(x)\n"
       "spec fun abs_v(x_v: int): int\n  decreases x_v\n= if x_v > 0 then x_v else -x_v\n"
       "{\n  if x < 0 {\n    y := -x;\n  } else {\n    y := x;\n  }\n}\n")
ROW = student_rows.row_for(surface.parse(SRC))
ALL = {k: "verified / refuted" for k in spec_check.KERNELS}


class Judge(unittest.TestCase):
    def test_the_reference_answer_is_ready(self):
        stage, why, task = ssg.judge(ssg.question_task(ROW), ROW["chosen"])
        self.assertEqual((stage, why), ("ready", None))
        self.assertEqual(task["name"], "abs")

    def test_a_reply_without_a_task_and_one_that_does_not_parse_are_named(self):
        q = ssg.question_task(ROW)
        self.assertEqual(ssg.judge(q, "I cannot.")[0], "no-block")
        self.assertEqual(ssg.judge(q, "```t\nt 1\ntask abs(x: int) returns (y: int)\n{ y := [a for a in x]; }\n```")[0], "parse")

    def test_a_redefined_spec_fun_stops_before_the_kernels(self):
        cheat = ROW["chosen"].replace("= if x_v > 0 then x_v else -x_v", "= 0")
        stage, why, task = ssg.judge(ssg.question_task(ROW), cheat)
        self.assertEqual(stage, "spec-changed")
        self.assertIn("abs_v was redefined", why)
        self.assertIsNone(task)

    def test_a_renamed_answer_is_refused_strictly_and_judged_on_its_contract_when_the_name_is_normalised(self):
        renamed = ROW["chosen"].replace("task abs(", "task mbpp_7__abs(")
        q = ssg.question_task(ROW)
        self.assertEqual(ssg.judge(q, renamed)[:2], ("spec-changed", "the task was renamed"))
        stage, why, task = ssg.judge(q, renamed, normalise_name=True)
        self.assertEqual((stage, why, task["name"]), ("ready", None, "abs"))

    def test_normalising_the_name_does_not_let_a_redefined_spec_fun_through(self):
        cheat = ROW["chosen"].replace("task abs(", "task other(").replace("= if x_v > 0 then x_v else -x_v", "= 0")
        stage, why, _task = ssg.judge(ssg.question_task(ROW), cheat, normalise_name=True)
        self.assertEqual(stage, "spec-changed")
        self.assertIn("abs_v was redefined", why)

    def test_prepare_writes_only_ready_answers_and_records_every_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = ssg.prepare([ROW], {"abs": ROW["chosen"]}, Path(tmp))
            self.assertEqual(report["stages"], {"ready": 1})
            self.assertTrue((Path(tmp) / "abs.json").exists())
            report = ssg.prepare([ROW], {}, Path(tmp))
            self.assertEqual(report["stages"], {"unanswered": 1})
            self.assertFalse((Path(tmp) / "abs.json").exists())      # a stale file from the last run is removed


class Level(unittest.TestCase):
    def test_seven_proofs_is_seven_and_an_undecided_kernel_lowers_it(self):
        self.assertEqual(ssg.level_of(ALL), ("graded", 7))
        self.assertEqual(ssg.level_of(dict(ALL, spark="timeout / refuted", lean="unproved / refuted")), ("graded", 5))

    def test_a_refuting_kernel_is_its_own_outcome(self):
        self.assertEqual(ssg.level_of(dict(ALL, rocq="refuted / refuted")), ("refuted", 0))

    def test_no_twin_is_a_missing_measurement_not_unproved(self):
        self.assertEqual(ssg.level_of({k: "no-twin / no-twin" for k in spec_check.KERNELS}), ("no-twin", 0))

    def test_a_missing_or_partial_row_is_not_a_proof(self):
        self.assertEqual(ssg.level_of(None), ("no-table", 0))
        partial = dict(ALL)
        del partial["fstar"]
        self.assertEqual(ssg.level_of(partial), ("no-table", 0))


class AskAServer(unittest.TestCase):
    """The same question to a model a server holds (the 4-bit GGUF student under llama.cpp,
    github.com/ggml-org/llama.cpp): greedy, the same budget, and a run resumes."""

    def test_the_conversation_goes_over_greedy_and_the_answer_is_recorded_once(self):
        import json
        sent = []

        def post(url, body, timeout=0):
            sent.append((url, body))
            return {"choices": [{"message": {"content": ROW["chosen"]}, "finish_reason": "stop"}],
                    "usage": {"completion_tokens": 17}}

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "answers.jsonl"
            self.assertEqual(ssg.ask("student-q4", [ROW], out, "s1", 256, host="127.0.0.1:1", post=post), 0)
            self.assertEqual(ssg.ask("student-q4", [ROW], out, "s1", 256, host="127.0.0.1:1", post=post), 0)
            rows = [json.loads(line) for line in out.read_text().splitlines()]
        self.assertEqual(len(sent), 1)                              # the second run asked nothing
        url, body = sent[0]
        self.assertEqual(url, "http://127.0.0.1:1/v1/chat/completions")
        self.assertEqual((body["temperature"], body["max_tokens"]), (0, 256))
        self.assertEqual(body["messages"], ssg.conversation(ROW, "s1"))
        self.assertEqual((rows[0]["name"], rows[0]["reply"], rows[0]["stopped"], rows[0]["tokens"], rows[0]["model"]),
                         (ROW["name"], ROW["chosen"], True, 17, "student-q4"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
