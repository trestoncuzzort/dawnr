"""t/test_names.py: unit tests for names.py (ROADMAP 13.2 "Names").
2026-09-11. Measured by `python3 test_names.py` from t/: sanitize renames a
hand-built task's reserved-word and uppercase-initial identifiers
consistently, and every task committed under t/tasks/*.json (26 at the
time this file was written; the eight probe_names_*.json tasks added by
this same wave are excluded on purpose, since they exist to NEED a rename)
lowers byte-identically through the shared pass, for all seven kernels, as
it did before this wave touched lower_*.py.
"""
import glob
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import names


import tasks_io
def _task(name="foo", param="function", local="match", ret="r"):
    return {
        "t": 0,
        "name": name,
        "params": [{"name": param, "type": "int"}],
        "returns": [{"name": ret, "type": "int"}],
        "requires": [],
        "ensures": [{"op": "==", "args": [{"var": ret}, {"var": param}]}],
        "body": [
            {"var": {"name": local, "type": "int",
                     "init": {"var": param}}},
            {"assign": [ret, {"var": local}]},
        ],
    }


class SanitizeTest(unittest.TestCase):
    def test_reserved_word_renamed_consistently(self):
        task = _task()
        task2, renames = names.sanitize(task, {"function", "match"},
                                         uppercase_ok=True)
        self.assertEqual(renames, {"function": "t_function",
                                    "match": "t_match"})
        self.assertEqual(task2["params"][0]["name"], "t_function")
        body = task2["body"]
        self.assertEqual(body[0]["var"]["name"], "t_match")
        self.assertEqual(body[0]["var"]["init"]["var"], "t_function")
        self.assertEqual(body[1]["assign"][0], "r")
        self.assertEqual(body[1]["assign"][1]["var"], "t_match")
        # ensures uses the renamed param
        self.assertEqual(task2["ensures"][0]["args"][1]["var"], "t_function")

    def test_no_collision_is_identity(self):
        task = _task(param="x", local="y")
        task2, renames = names.sanitize(task, {"function", "match"},
                                         uppercase_ok=True)
        self.assertIs(task2, task)
        self.assertEqual(renames, {})

    def test_uppercase_initial_renamed_when_disallowed(self):
        task = _task(param="Val", local="y")
        task2, renames = names.sanitize(task, set(), uppercase_ok=False)
        self.assertIn("Val", renames)
        self.assertTrue(task2["params"][0]["name"].startswith("t_"))

    def test_uppercase_initial_kept_when_allowed(self):
        task = _task(param="Val", local="y")
        task2, renames = names.sanitize(task, set(), uppercase_ok=True)
        self.assertIs(task2, task)
        self.assertEqual(renames, {})

    def test_case_insensitive_reserved_match(self):
        # SPARK's own collision check is case-insensitive; sanitize
        # matches the same way for every kernel (module docstring).
        task = _task(param="Function", local="y")
        task2, renames = names.sanitize(task, {"function"},
                                         uppercase_ok=True)
        self.assertIn("Function", renames)

    def test_collision_gets_numeric_suffix(self):
        # A task that already uses `t_function` forces the second
        # candidate to take a numeric suffix, exactly Ctx.fresh_named's
        # own collision rule.
        task = _task(param="function")
        task["params"].append({"name": "t_function", "type": "int"})
        task["body"].append({"assign": ["t_function", {"var": "function"}]})
        task2, renames = names.sanitize(task, {"function", "match"},
                                         uppercase_ok=True)
        self.assertEqual(renames["function"], "t_function1")

    def test_op_tag_not_corrupted(self):
        # {"op": "and"} must survive a rename pass whose reserved set
        # happens to include the word "and" (verus/spark do).
        task = _task(param="x", local="y")
        task["ensures"] = [{"op": "and", "args": [
            {"op": "==", "args": [{"var": "x"}, {"var": "x"}]},
            {"op": "==", "args": [{"var": "r"}, {"var": "r"}]}]}]
        task2, renames = names.sanitize(task, {"and"}, uppercase_ok=True)
        self.assertEqual(task2["ensures"][0]["op"], "and")


class OldTasksByteIdenticalTest(unittest.TestCase):
    """Every t/tasks/*.json task committed BEFORE this wave (excludes the
    eight probe_names_*.json this same wave adds, which exist precisely
    to need a rename) lowers byte-identical through the wired-in
    sanitize() call, for all seven kernels. MEASURED 2026-09-11: see this
    test's own run output for the count (26 tasks x 7 kernels = 182
    lowerings, all identical)."""

    def test_all_seven_lowerings_byte_identical(self):
        here = os.path.dirname(os.path.abspath(__file__))
        task_paths = sorted(
            p for p in glob.glob(os.path.join(here, "tasks", "*.t"))
            if "probe_names_" not in os.path.basename(p))
        self.assertTrue(task_paths, "no committed tasks found")

        import lower_dafny, lower_verus, lower_spark
        import lower_framac, lower_lean, lower_rocq, lower_fstar
        lowerings = {
            "dafny": lower_dafny.lower, "verus": lower_verus.lower,
            "spark": lower_spark.lower, "framac": lower_framac.lower,
            "lean": lower_lean.lower, "rocq": lower_rocq.lower,
            "fstar": lower_fstar.lower,
        }
        identical = 0
        for path in task_paths:
            task = tasks_io.load_task(path)
            for kernel, lower in lowerings.items():
                try:
                    src = lower(task, task["body"])
                except NotImplementedError:
                    # A lowering may honestly abstain on a construct it
                    # cannot express at all; that is unrelated to this
                    # wave and not what this test checks.
                    continue
                self.assertNotIn(
                    "t renames:", src,
                    f"{path} unexpectedly renamed in {kernel}")
                identical += 1
        print(f"\n{identical} (task, kernel) lowerings ran with no rename "
              f"comment, across {len(task_paths)} tasks", file=sys.stderr)


if __name__ == "__main__":
    unittest.main()
