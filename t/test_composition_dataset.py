"""Lab tests for the composition curriculum: oracle agreement, holdouts, seams."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import build_composition_dataset as build
import composition_reference as ref
from execution_trace import collect, digest


def every_pattern(limit=None):
    patterns = [(kind,) for kind in ref.KINDS]
    patterns += [(a, b) for a in ref.KINDS for b in ref.KINDS]
    patterns += [("affine", "tri", "cap"), ("tri", "shift", "tri"), ("cap", "cap", "affine")]
    return patterns[:limit] if limit else patterns


class OracleTests(unittest.TestCase):
    def test_oracle_matches_the_interpreter_on_every_pattern(self):
        checked = 0
        for pattern in every_pattern():
            stages = tuple(build.GRID[kind][0] for kind in pattern)
            source, task = build.build_task("probe", stages)
            for x in range(-5, 8):
                if ref.loop_trips(stages, x) > 60:
                    continue
                row = collect(task, {"x": x})
                self.assertEqual(row["status"], "ensures_true_at_input", (pattern, x))
                self.assertEqual(row["events"], ref.expected_events(stages, x), (pattern, x))
                self.assertEqual(row["final_state"]["r"],
                                 {"type": "int", "value": ref.final_value(stages, x)})
                checked += 1
        self.assertGreater(checked, 200)

    def test_statement_layout_matches_the_printed_body(self):
        for pattern in every_pattern():
            stages = tuple(build.GRID[kind][-1] for kind in pattern)
            _, task = build.build_task("probe", stages)
            self.assertEqual(len(task["body"]),
                             1 + sum(ref.statement_count(kind) for kind in pattern))

    def test_corruption_of_a_trace_is_rejected(self):
        stages = (("affine", 3, 1), ("tri", 4))
        _, task = build.build_task("probe", stages)
        events = collect(task, {"x": 4})["events"]
        self.assertGreaterEqual(build.corruption_checks(stages, 4, events), 5)
        self.assertNotEqual(events[:-1], ref.expected_events(stages, 4))
        moved = [dict(row) for row in events]
        moved[2]["path"] = [99]
        self.assertNotEqual(moved, ref.expected_events(stages, 4))
        altered = [dict(row) for row in events]
        altered[3]["state"] = {**altered[3]["state"], "r": {"type": "int", "value": -12345}}
        self.assertNotEqual(altered, ref.expected_events(stages, 4))

    def test_wrong_stage_order_is_a_different_program(self):
        forward, backward = (("affine", 2, 1), ("cap", 5)), (("cap", 5), ("affine", 2, 1))
        self.assertNotEqual([ref.final_value(forward, x) for x in range(-4, 9)],
                            [ref.final_value(backward, x) for x in range(-4, 9)])


class SerializationTests(unittest.TestCase):
    def test_prompt_and_completion_rebuild_the_canonical_source(self):
        for pattern in every_pattern():
            stages = tuple(build.GRID[kind][0] for kind in pattern)
            source, _ = build.build_task("probe", stages)
            example = build.synthesis_example(source)
            self.assertEqual(example["prompt"].partition("\n")[2] + example["completion"], source)
            self.assertNotIn("ensures", example["completion"])

    def test_delta_lines_reconstruct_every_state(self):
        stages = (("tri", 4), ("shift", 3))
        _, task = build.build_task("probe", stages)
        events = collect(task, {"x": 5})["events"]
        rebuilt, previous = {}, {}
        for event in events:
            line = build.event_line(event, previous)
            payload = line.partition(" | ")[2]
            for item in payload.split():
                name, _, value = item.partition("=")
                rebuilt[name] = ({"type": "unassigned"} if value == "?"
                                 else {"type": "int", "value": int(value)})
            self.assertEqual(rebuilt, event["state"], line)
            previous = event["state"]

    def test_execution_answer_part_holds_only_the_final_output(self):
        stages = (("affine", 2, 1),)
        source, task = build.build_task("probe", stages)
        events = collect(task, {"x": 3})["events"]
        example = build.execution_example(source, 3, events, ref.final_value(stages, 3))
        self.assertEqual([role for _, role in example["parts"]], ["execution", "answer"])
        self.assertEqual(example["parts"][1][0], "output r = 7\n")


class SplitTests(unittest.TestCase):
    def test_evaluation_patterns_are_never_trained(self):
        splits = build.split_patterns(1337, 5, 12)
        trained = set(splits["train"])
        for split in ("eval_pattern", "eval_depth"):
            self.assertTrue(trained.isdisjoint(splits[split]))
            self.assertTrue(splits[split])
        self.assertTrue(all(len(pattern) == 3 for pattern in splits["eval_depth"]))
        self.assertTrue(all(len(pattern) <= 2 for pattern in splits["train"]))

    def test_contract_hash_changes_with_the_contract(self):
        source, task = build.build_task("probe", (("affine", 2, 1),))
        other = build.build_task("probe", (("affine", 2, 2),))[1]
        keys = ("name", "params", "returns", "requires", "ensures", "spec_funs")
        self.assertNotEqual(digest({k: task.get(k) for k in keys}),
                            digest({k: other.get(k) for k in keys}))


class BuildTests(unittest.TestCase):
    def build(self, directory):
        out = Path(directory) / "dataset"
        subprocess.run([sys.executable, str(Path(build.__file__)), "--out", str(out),
                        "--variants", "1", "--inputs", "3", "--eval-inputs", "2"],
                       check=True, capture_output=True, cwd=Path(build.__file__).parent)
        return out

    def test_two_builds_agree_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            one, two = self.build(first), self.build(second)
            for name in ("train.jsonl", "eval_synthesis.jsonl", "eval_execution.jsonl",
                         "traces.jsonl"):
                self.assertEqual((one / name).read_bytes(), (two / name).read_bytes(), name)
            self.assertEqual(json.loads((one / "manifest.json").read_text())["files"],
                             json.loads((two / "manifest.json").read_text())["files"])

    def test_evaluation_manifest_withholds_the_reference_body(self):
        with tempfile.TemporaryDirectory() as directory:
            out = self.build(directory)
            rows = [json.loads(line) for line in
                    (out / "eval_synthesis.jsonl").read_text().splitlines()]
            trained = {json.loads(line)["task_name"] for line in
                       (out / "train.jsonl").read_text().splitlines()}
            for row in rows:
                self.assertNotIn("completion", row)
                self.assertNotIn(row["task_name"], trained)
                self.assertTrue(row["tests"]["extrapolation"])
                self.assertTrue(all(abs(test["x"]) >= 18
                                    for test in row["tests"]["extrapolation"]))


if __name__ == "__main__":
    unittest.main()
