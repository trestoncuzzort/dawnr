"""Regression tests for held-out pool ids expressed through task-name aliases."""
import json
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
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


class TempDirTestCase(unittest.TestCase):
    def tempdir(self) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        return Path(directory.name)


class ProblemIdTests(TempDirTestCase):
    # The 21 same-task exclusions read by hand on 2026-09-21.
    SAME_TASK_IDS = frozenset({
        29, 76, 102, 242, 404, 427, 451, 496, 498, 504, 595, 728, 759, 767,
        790, 930, 952, 200124, 202465, 203929, 204462,
    })
    # The 77 behavioural exclusions t/behavioural_decontam.py measured on 2026-09-25 (schema 2,
    # after the review: an own input a reference did not answer leaves the count): pool v5 and
    # pool v6 against the same 232 held-out ids, 77 computed duplicates and
    # 0 undecided pair(s) read by hand as the same function; 16 of the 21 above
    # rediscovered, 61 new (13 MBPP, 3 HumanEval, 37 APPS, 8 stdin-shaped, the last only in pool v6).
    BEHAVIOURAL_IDS = frozenset({
        29, 41, 62, 71, 102, 152, 199, 242, 372, 388, 404, 427, 451, 496, 504, 567, 595, 600, 635, 756,
        759, 767, 790, 930, 940, 955, 100013, 100023, 100057, 200178, 200201, 200343, 202415, 202457,
        202465, 202493, 202504, 202525, 202542, 202551, 202658, 202849, 202860, 202893, 202914, 203008,
        203031, 203336, 203383, 203579, 203632, 203736, 203778, 203920, 203929, 203985, 204032, 204152,
        204154, 204157, 204207, 204444, 204455, 204462, 204498, 204695, 204712, 204714, 204735, 300281,
        300683, 300709, 301606, 304681, 5973913, 8141530, 9333067,
    })

    def test_decontamination_policy_has_the_registered_scope(self):
        policy = loop_filter.decontamination()
        self.assertEqual(len(policy.drop_document_names), 37)
        # 82 excluded train ids: the 21 read by hand and the 77 measured, 16 in both
        self.assertEqual(len(self.SAME_TASK_IDS), 21)
        self.assertEqual(len(self.BEHAVIOURAL_IDS), 77)
        self.assertEqual(len(self.SAME_TASK_IDS & self.BEHAVIOURAL_IDS), 16)
        self.assertEqual(policy.exclude_train_ids, self.SAME_TASK_IDS | self.BEHAVIOURAL_IDS)
        self.assertEqual(len(policy.exclude_train_ids), 82)
        # provenance: every excluded id names the file(s) that excluded it
        self.assertEqual(set(policy.excluded_by), set(policy.exclude_train_ids))
        by_file = {}
        for files in policy.excluded_by.values():
            for name in files:
                by_file[name] = by_file.get(name, 0) + 1
        self.assertEqual(by_file, {"decontamination-2026-09-21.json": 21,
                                   "decontamination-behavioural-2026-09-25.json": 77})
        self.assertEqual(policy.excluded_by[76], ("decontamination-2026-09-21.json",))
        self.assertEqual(policy.excluded_by[41], ("decontamination-behavioural-2026-09-25.json",))
        self.assertEqual(policy.excluded_by[242], ("decontamination-2026-09-21.json",
                                                   "decontamination-behavioural-2026-09-25.json"))
        # 49 held-out ids have a behavioural twin in training; the clean 200 stay the 32's complement
        self.assertEqual(len(policy.behavioural_overlap_eval_ids), 49)
        self.assertTrue({47, 141, 269, 428, 813, 931}.issubset(policy.behavioural_overlap_eval_ids))
        self.assertEqual(len(policy.overlap_eval_ids), 32)
        self.assertEqual(policy.overlap_eval_ids, frozenset({
            10, 138, 161, 208, 269, 347, 358, 366, 402, 411, 443, 492, 502, 518,
            527, 565, 566, 604, 626, 682, 687, 699, 719, 729, 775, 800, 813, 842,
            887, 928, 931, 970,
        }))
        self.assertTrue({
            "clover_array_product__arrayProduct", "contains", "digit_sum", "gcd", "remainder",
            "dafny_synthesis_task_id_269__asciiValue", "dafny_synthesis_task_id_626__areaOfLargestTriangleInSemicircle",
        }.issubset(policy.drop_document_names))

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

    def test_shared_validator_combines_aliases_metadata_and_a2_policy(self):
        renamed = "t 1\ntask renamed_for_export(a: int) returns (r: int)\n{\n  r := a;\n}\n"
        held = loop_filter.validate_training_data(renamed, {269}, task_ids=[269])
        self.assertFalse(held.ok)
        self.assertEqual(held.held_out, {269: frozenset({"task_id=269"})})
        same_task = loop_filter.validate_training_data(DECONTAMINATED, {269})
        self.assertFalse(same_task.ok)
        self.assertEqual(same_task.same_task_names, frozenset({"clover_array_product__arrayProduct"}))



class BuilderTests(TempDirTestCase):
    def test_builder_excludes_lifted_held_out_names(self):
        directory = self.tempdir()
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

    def test_builder_rejects_a_renamed_sft_row_by_its_task_id(self):
        directory = self.tempdir()
        sft = directory / "sft.jsonl"
        split = directory / "split.json"
        corpus = directory / "corpus.txt"
        sft.write_text(json.dumps({
            "task_id": 269,
            "task": "renamed_for_export",
            "chosen": "```t\n" + SAFE + "```",
        }) + "\n", encoding="utf-8")
        split.write_text(json.dumps({"eval_ids": [269]}), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable, str(HERE / "loop_locallm.py"), "corpus", "--pool", "v5",
                "--sft", str(sft), "--split", str(split), "--out", str(corpus),
            ],
            capture_output=True, text=True, cwd=HERE,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("mbpp_5__f", corpus.read_text(encoding="utf-8"))
        self.assertIn("1 document(s) excluded", result.stdout)


    def test_gate_rejects_an_unnamed_held_out_row(self):
        gate = loop_locallm.Gate({269})
        self.assertFalse(gate.admit("", [], {269}))
        self.assertEqual(gate.held, ["<unnamed> (269)"])

    def test_builder_excludes_a_registered_same_task_source(self):
        directory = self.tempdir()
        base = directory / "base.txt"
        corpus = directory / "corpus.txt"
        base.write_text("\n\n".join((DECONTAMINATED, SAFE)), encoding="utf-8")
        split = directory / "split.json"
        split.write_text(json.dumps({"eval_ids": [269]}), encoding="utf-8")

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
        self.assertNotIn("clover_array_product__arrayProduct", corpus.read_text(encoding="utf-8"))
        self.assertIn("mbpp_5__f", corpus.read_text(encoding="utf-8"))
        self.assertIn("decontamination filter: 1 document(s) excluded", result.stdout)

    def test_gate_excludes_a_registered_train_id(self):
        gate = loop_locallm.Gate(set())
        self.assertFalse(gate.admit("", [], {242}))
        self.assertEqual(gate.decontaminated, ["<unnamed> (task_id=242)"])


class PreflightTests(TempDirTestCase):
    def test_preflight_rejects_aliases_and_explicit_task_ids(self):
        directory = self.tempdir()
        corpus = directory / "corpus.txt"
        pool = directory / "pool.jsonl"
        corpus.write_text(LEAKED_269, encoding="utf-8")
        pool.write_text(json.dumps({"task": "renamed", "task_id": 626}) + "\n", encoding="utf-8")

        self.assertFalse(preflight.check_corpora({269, 626}, [corpus]))
        self.assertFalse(preflight.check_pool_files({269, 626}, [pool]))

    def test_preflight_rejects_registered_same_task_sources(self):
        directory = self.tempdir()
        corpus = directory / "corpus.txt"
        pool = directory / "pool.jsonl"
        corpus.write_text(DECONTAMINATED, encoding="utf-8")
        pool.write_text(json.dumps({"task": "unrelated", "task_id": 242}) + "\n", encoding="utf-8")

        self.assertFalse(preflight.check_corpora(set(), [corpus]))
        self.assertFalse(preflight.check_pool_files(set(), [pool]))


    def test_selected_current_inputs_ignore_legacy_artifacts_until_audit(self):
        directory = self.tempdir()
        split = directory / "split.json"
        current = directory / "current.txt"
        out = directory / "out"
        legacy = out / "loop" / "corpus-legacy.txt"
        split.write_text(json.dumps({"eval_ids": [269]}), encoding="utf-8")
        current.write_text(SAFE, encoding="utf-8")
        legacy.parent.mkdir(parents=True)
        legacy.write_text(LEAKED_269, encoding="utf-8")

        with mock.patch.object(preflight, "OUT", out):
            self.assertFalse(preflight.check_split(split))
            self.assertTrue(preflight.check_split(split, corpora=[current]))
            self.assertFalse(preflight.check_split(split, audit_history=True))


class ContinueFromCheckpointTests(TempDirTestCase):
    def test_continuation_rejects_lifted_alias_before_loading_torch(self):
        directory = self.tempdir()
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

    def test_direct_manual_continuation_cannot_bypass_same_task_policy(self):
        directory = self.tempdir()
        data = directory / "manual-corpus.txt"
        split = directory / "split.json"
        data.write_text(DECONTAMINATED, encoding="utf-8")
        split.write_text(json.dumps({"eval_ids": [269]}), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable, str(HERE.parent / "locallm" / "continue_from_checkpoint.py"),
                "--init", str(directory / "missing-init"), "--data", str(data),
                "--split", str(split), "--out", str(directory / "out"),
            ],
            capture_output=True, text=True, cwd=HERE,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("same-task source", result.stderr)



if __name__ == "__main__":
    unittest.main()
