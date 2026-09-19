import json
import unittest

import execution_trace
import surface


SOURCE = """t 1 gate recursion task trace_demo(x: int) returns (r: int)
requires x >= 0
ensures r == x + 1
{ r := x + 1; }
"""


class TraceExportTests(unittest.TestCase):
    def test_records_are_serializable_and_not_proofs(self):
        task = surface.parse(SOURCE)
        for x in range(20):
            row = execution_trace.collect(task, {"x": x})
            self.assertEqual(row["status"], "ensures_true_at_input")
            self.assertEqual(row["final_state"]["r"], {"type": "int", "value": x + 1})
            self.assertFalse(row["training_eligible"])
            self.assertFalse(row["independently_validated"])
            self.assertEqual(json.loads(json.dumps(row)), row)
        changed = surface.parse(SOURCE.replace("r == x + 1", "r == x + 2"))
        other = execution_trace.collect(changed, {"x": 0})
        self.assertEqual(other["status"], "ensures_false_at_input")
        self.assertNotEqual(row["contract_sha256"], other["contract_sha256"])

    def test_budget_and_precondition_remain_distinct(self):
        task = surface.parse(SOURCE)
        self.assertEqual(execution_trace.collect(task, {"x": -1})["status"],
                         "outside_precondition")
        row = execution_trace.collect(task, {"x": 0}, max_events=1)
        self.assertEqual(row["status"], "unknown_budget")
        self.assertEqual(len(row["events"]), 1)
        self.assertEqual(row["phase"], "body")

    def test_type_identity(self):
        self.assertNotEqual(execution_trace.typed(True), execution_trace.typed(1))
        with self.assertRaises(TypeError):
            execution_trace.typed((1, 2))

    def test_missing_postcondition_is_not_a_successful_check(self):
        task = surface.parse(SOURCE)
        task["ensures"] = []
        self.assertEqual(execution_trace.collect(task, {"x": 0})["status"],
                         "executed_no_postcondition")


if __name__ == "__main__":
    unittest.main()
