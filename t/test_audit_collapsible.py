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
