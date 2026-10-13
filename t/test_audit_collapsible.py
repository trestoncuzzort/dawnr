"""Lab tests for the collapsibility audit."""
import unittest

import audit_collapsible as audit


class CollapsibleTests(unittest.TestCase):
    def test_a_repeated_cap_collapses_to_one(self):
        stages = [("cap", 12), ("cap", 12)]
        self.assertIsNotNone(audit.collapsible(stages, list(range(-5, 20))))

    def test_a_genuine_composition_does_not_collapse(self):
        stages = [("affine", 3, 4), ("affine", 3, 1)]
        self.assertIsNone(audit.collapsible(stages, list(range(-5, 20))))

    def test_an_identity_stage_is_dropped(self):
        stages = [("affine", 1, 0), ("shift", 3)]
        self.assertEqual(audit.collapsible(stages, list(range(-5, 20))), [1])

    def test_collapse_is_judged_on_the_task_s_own_inputs(self):
        # cap 20 never fires below 20, so on small inputs the pair collapses.
        stages = [("cap", 20), ("shift", 3)]
        self.assertIsNotNone(audit.collapsible(stages, list(range(-5, 10))))
        self.assertIsNone(audit.collapsible(stages, list(range(-5, 40))))


if __name__ == "__main__":
    unittest.main()


# Three defects the GPT-6 Astra review of 2026-10-13 named, each reproduced here before the fix.

def test_unknown_stages_do_not_count_as_composed(tmp_path):
    import json
    import audit_collapsible as audit
    entry = {"task_name": "unknown", "split": "held_out", "pattern": "shift_then_shift", "tests": {"test": [{"x": 0}]}}
    (tmp_path / "eval_synthesis.jsonl").write_text(json.dumps(entry) + "\n")
    score = tmp_path / "score.json"
    score.write_text(json.dumps({"rows": [{"task_name": "unknown", "verdict": "correct"}]}))
    report = audit.audit(tmp_path, [score])
    assert report["tasks_unknown_stages"] == 1
    assert report["scored"]["correct_composed"] == 0
    assert report["scored"]["correct_unaudited"] == 1


def test_cancelling_stages_collapse_to_empty():
    import audit_collapsible as audit
    # affine +5 then affine -5 is the identity; shift is not plain addition here (it reflects negatives), so the
    # reviewer's shift example does not cancel and must stay non-collapsible
    assert audit.collapsible([("affine", 1, 5), ("affine", 1, -5)], [-5, 0, 8]) == []
    assert audit.collapsible([("shift", 3), ("shift", -3)], [-5, 0, 8]) is None


def test_collapsible_accepts_input_iterator():
    import audit_collapsible as audit
    assert audit.collapsible([("cap", 12), ("cap", 12)], iter(range(-5, 20))) == [0]
