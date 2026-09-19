"""Specification checking must identify the problem and the exact checked program."""
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

import spec_check as sc
import surface


def task(name="he_42__f", requires=""):
    return surface.parse(f"t 0\ntask {name}(a: int) returns (r: int)\n"
                         f"{requires}\n  ensures r == a + 1\n{{ r := a + 1; }}\n")


def entry(code="def f(a): return a + 1"):
    return {"fn": "f", "rec": {"code": code},
            "points": [{"args": [["int", 1]], "expected": ["int", 2]}]}


class SpecificationChecks(unittest.TestCase):
    def test_corpus_names_do_not_collide(self):
        self.assertEqual(sc.problem_id("mbpp_42__f", {}), 42)
        self.assertEqual(sc.problem_id("he_42__f", {}), 100042)
        self.assertEqual(sc.problem_id("apps_42__f", {}), 200042)

    def test_extract_mapping_is_authoritative_and_consistent(self):
        self.assertEqual(sc.problem_id("custom_name", {"100042": {"name": "custom_name"}}), 100042)
        with self.assertRaises(ValueError):
            sc.problem_id("he_42__f", {"42": {"name": "he_42__f"}})
        with self.assertRaises(ValueError):
            sc.problem_id("custom_name", {"1": {"name": "custom_name"},
                                          "2": {"name": "custom_name"}})

    def test_zero_accepted_inputs_are_not_agreement(self):
        result = sc.check_task(task(requires="  requires a < 0"), entry(), 20, random.Random(1))
        self.assertEqual(result, {"status": "no valid draws", "draws": 0})

    def test_reference_disagreement_is_observed(self):
        result = sc.check_task(task(), entry("def f(a): return a"), 20, random.Random(1))
        self.assertEqual(result["status"], "disagrees")

    def test_fingerprint_changes_with_specification(self):
        original = task()
        changed = surface.parse(surface.print_task(original).replace("a + 1", "a + 2"))
        self.assertNotEqual(sc.task_sha256(original), sc.task_sha256(changed))

    def test_main_records_actual_problem_and_preserves_prior_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            here = Path(tmp) / "t"
            tag = "he-source"
            d = here / "out/spec-experiment" / tag
            (d / "tasks").mkdir(parents=True)
            current = task()
            name = current["name"]
            (d / "tasks" / f"{name}.json").write_text(json.dumps(current))
            (d / "extract.json").write_text(json.dumps({"100042": {"name": name, "stage": "task"}}))
            (d / "tests.json").write_text(json.dumps({"100042": {"name": name, "overall": "pass"}}))
            result_path = here / "out/spec-disagree.json"
            prior = {"checked": 1, "tags": ["old"], "disagree": ["old/task"],
                     "programs": {"old/task": "unchanged"},
                     "results": {"old/task": {"status": "disagrees"}}}
            result_path.write_text(json.dumps(prior))
            cols = sc.KERNELS
            table = (cols, {name: {k: "verified / refuted" for k in cols}})
            with patch.object(sc, "HERE", here), patch.object(sc.se, "pool", return_value={
                    42: entry("def f(a): return 0"), 100042: entry()}), \
                    patch.object(sc.se, "parse_kernel_table", return_value=table), \
                    patch("sys.argv", ["spec_check.py", "--pool", "v5", "--n", "10",
                                       "--out", str(here / "report.md"), tag]):
                self.assertEqual(sc.main(), 0)
            saved = json.loads(result_path.read_text())
            result = saved["results"][f"{tag}/{name}"]
            self.assertEqual(result["task_id"], 100042)
            self.assertEqual(result["status"], "agrees")
            self.assertEqual(result["draws"], 10)
            self.assertEqual(result["task_sha256"], sc.task_sha256(current))
            self.assertEqual(saved["results"]["old/task"], prior["results"]["old/task"])
            self.assertEqual(saved["disagree"], prior["disagree"])
            self.assertEqual(saved["runs"][0]["tags"], [tag])


if __name__ == "__main__":
    unittest.main()
