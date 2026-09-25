"""Regression tests for held-out pool ids expressed through task-name aliases."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import loop_filter
import loop_locallm
import preflight
import spec_experiment as se


HERE = Path(__file__).resolve().parent
LEAKED_269 = (
    "Signature: dafny_synthesis_task_id_269__asciiValue(int) -> int\n"
    "t 1\n"
    "task dafny_synthesis_task_id_269__asciiValue(c: int) returns (ascii: int)\n"
    "  ensures ascii == c\n"
    "{\n"
    "  ascii := c;\n"
    "}\n"
)
LEAKED_626 = (
    "Signature: dafny_synthesis_task_id_626__areaOfLargestTriangleInSemicircle(int) -> int\n"
    "t 1\n"
    "task dafny_synthesis_task_id_626__areaOfLargestTriangleInSemicircle(radius: int) returns (area: int)\n"
    "  ensures area == radius * radius\n"
    "{\n"
    "  area := radius * radius;\n"
    "}\n"
)
SAFE = (
    "Signature: mbpp_5__f(int) -> int\n"
    "t 1\n"
    "task mbpp_5__f(a: int) returns (r: int)\n"
    "  ensures r == a\n"
    "{\n"
    "  r := a;\n"
    "}\n"
)
DECONTAMINATED = (
    "t 1\n"
    "task clover_array_product__arrayProduct(a: int) returns (r: int)\n"
    "  ensures r == a\n"
    "{\n"
    "  r := a;\n"
    "}\n"
)


class ProblemIdTests(unittest.TestCase):
    def test_decontamination_policy_has_the_registered_scope(self):
        policy = loop_filter.decontamination()
        self.assertEqual(len(policy.drop_document_names), 37)
        self.assertEqual(len(policy.exclude_train_ids), 21)
        self.assertEqual(len(policy.overlap_eval_ids), 32)
        self.assertIn("clover_array_product__arrayProduct", policy.drop_document_names)
        self.assertIn(242, policy.exclude_train_ids)

    def test_all_pool_families_map_to_a_single_id(self):
        cases = {
            "mbpp_269__ascii_value": 269,
            "dafny_synthesis_task_id_269__asciiValue": 269,
            "dafny-synthesis_task_id_626.areaOfLargestTriangleInSemicircle": 626,
            "he_41__car_race_collision": se.HUMANEVAL_BASE + 41,
            "apps_124__search": se.APPS_BASE + 124,
            "apps_100113__apps_stdin_113": 300113,
        }
        for name, task_id in cases.items():
            self.assertEqual(loop_filter.problem_id(name), task_id)

    def test_scan_finds_lifted_aliases_and_rejects_non_task_names(self):
        found = loop_filter.problem_ids_in(LEAKED_269 + LEAKED_626 + SAFE)
        self.assertEqual(set(found), {5, 269, 626})
        self.assertIn("dafny_synthesis_task_id_269__asciiValue", found[269])
        self.assertIsNone(loop_filter.problem_id("mbpp_12_x"))
        self.assertEqual(loop_filter.problem_ids_in("apps_raw_train the_41__x"), {})


class BuilderTests(unittest.TestCase):
    def test_builder_excludes_lifted_held_out_names(self):
        directory = Path(tempfile.mkdtemp())
        base = directory / "base.txt"
        split = directory / "split.json"
        corpus = directory / "corpus.txt"
        base.write_text("\n\n".join((LEAKED_269, LEAKED_626, SAFE)), encoding="utf-8")
        split.write_text(json.dumps({"eval_ids": [269, 626]}), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                str(HERE / "loop_locallm.py"),
                "corpus",
                "--pool",
                "v5",
                "--base",
                str(base),
                "--split",
                str(split),
                "--out",
                str(corpus),
            ],
            capture_output=True,
            text=True,
            cwd=HERE,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = corpus.read_text(encoding="utf-8")
        self.assertNotIn("task_id_269__", text)
        self.assertNotIn("task_id_626__", text)
        self.assertIn("mbpp_5__f", text)
        self.assertIn("2 document(s) excluded", result.stdout)

    def test_gate_rejects_an_unnamed_held_out_row(self):
        gate = loop_locallm.Gate({269})
        self.assertFalse(gate.admit("", [], {269}))
        self.assertEqual(gate.held, ["<unnamed> (269)"])

    def test_builder_excludes_a_registered_same_task_source(self):
        directory = Path(tempfile.mkdtemp())
        base = directory / "base.txt"
        corpus = directory / "corpus.txt"
        base.write_text("\n\n".join((DECONTAMINATED, SAFE)), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                str(HERE / "loop_locallm.py"),
                "corpus",
                "--pool",
                "v5",
                "--base",
                str(base),
                "--out",
                str(corpus),
            ],
            capture_output=True,
            text=True,
            cwd=HERE,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("clover_array_product__arrayProduct", corpus.read_text(encoding="utf-8"))
        self.assertIn("mbpp_5__f", corpus.read_text(encoding="utf-8"))
        self.assertIn("decontamination filter: 1 document(s) excluded", result.stdout)

    def test_gate_excludes_a_registered_train_id(self):
        gate = loop_locallm.Gate(set())
        self.assertFalse(gate.admit("", [], {242}))
        self.assertEqual(gate.decontaminated, ["<unnamed> (task_id=242)"])


class PreflightTests(unittest.TestCase):
    def test_preflight_rejects_aliases_and_explicit_task_ids(self):
        directory = Path(tempfile.mkdtemp())
        corpus = directory / "corpus.txt"
        pool = directory / "pool.jsonl"
        corpus.write_text(LEAKED_269, encoding="utf-8")
        pool.write_text(json.dumps({"task": "renamed", "task_id": 626}) + "\n", encoding="utf-8")

        self.assertFalse(preflight.check_corpora({269, 626}, [corpus]))
        self.assertFalse(preflight.check_pool_files({269, 626}, [pool]))

    def test_preflight_rejects_registered_same_task_sources(self):
        directory = Path(tempfile.mkdtemp())
        corpus = directory / "corpus.txt"
        pool = directory / "pool.jsonl"
        corpus.write_text(DECONTAMINATED, encoding="utf-8")
        pool.write_text(json.dumps({"task": "unrelated", "task_id": 242}) + "\n", encoding="utf-8")

        self.assertFalse(preflight.check_corpora(set(), [corpus]))
        self.assertFalse(preflight.check_pool_files(set(), [pool]))


class ContinueFromCheckpointTests(unittest.TestCase):
    def test_continuation_rejects_lifted_alias_before_loading_torch(self):
        directory = Path(tempfile.mkdtemp())
        data = directory / "corpus.txt"
        split = directory / "split.json"
        data.write_text(LEAKED_269, encoding="utf-8")
        split.write_text(json.dumps({"eval_ids": [269]}), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                str(HERE.parent / "locallm" / "continue_from_checkpoint.py"),
                "--init",
                str(directory / "missing-init"),
                "--data",
                str(data),
                "--split",
                str(split),
                "--out",
                str(directory / "out"),
            ],
            capture_output=True,
            text=True,
            cwd=HERE,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("contains held-out ids", result.stderr)


if __name__ == "__main__":
    unittest.main()
