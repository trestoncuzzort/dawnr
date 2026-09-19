"""Lab tests for the mask audit, on a tokenizer built in the test itself."""
import unittest

import audit_example_masks as audit
from completion_batch import IGNORE_INDEX
from data import build_tokenizer

def corpus():
    """Every character the fixtures use, so the audit tests the masks, not coverage."""
    text = ""
    for row in rows():
        text += row["prompt"] + row.get("completion", "")
        text += "".join(part for part, _ in row.get("parts", []))
    return text


def rows():
    return [{"kind": "synthesis", "task_name": "a", "split": "train",
             "prompt": "synthesize\ntask a(x: int)\n{\n", "completion": "  r := x;\n}\n"},
            {"kind": "execution", "task_name": "b", "split": "train",
             "prompt": "execute x = 3\ntask a(x: int)\ntrace\n",
             "parts": [["enter 0 | r=? x=3\nexit 0 | r=3\n", "execution"],
                       ["output r = 3\n", "answer"]]}]


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tokenizer = build_tokenizer(corpus(), "char")

    def test_arms_share_inputs_and_answer_targets(self):
        report = audit.audit(self.tokenizer, rows(), block_size=512, inspect=5)
        self.assertTrue(report["identical_input_ids"])
        self.assertTrue(report["identical_answer_targets"])
        self.assertEqual(report["examples"], {"synthesis": 1, "execution": 1})
        self.assertEqual(report["overlength"], {})

    def test_only_the_execution_arm_supervises_the_trace(self):
        checked = audit.audit_example(self.tokenizer, rows()[1], block_size=512)
        self.assertEqual(checked["supervised_baseline"], "output r = 3\n")
        self.assertEqual(checked["added_by_execution_arm"],
                         "enter 0 | r=? x=3\nexit 0 | r=3\n")
        self.assertGreater(sum(t != IGNORE_INDEX for t in checked["treated"]["targets"]),
                           sum(t != IGNORE_INDEX for t in checked["baseline"]["targets"]))

    def test_the_synthesis_completion_is_supervised_in_every_arm(self):
        checked = audit.audit_example(self.tokenizer, rows()[0], block_size=512)
        self.assertEqual(checked["supervised_baseline"], "  r := x;\n}\n")
        self.assertEqual(checked["added_by_execution_arm"], "")

    def test_overlength_examples_are_dropped_for_every_arm(self):
        report = audit.audit(self.tokenizer, rows(), block_size=12, inspect=5)
        self.assertEqual(report["overlength"], {"synthesis": 1, "execution": 1})
        self.assertEqual(report["kept_examples"], 0)


if __name__ == "__main__":
    unittest.main()
