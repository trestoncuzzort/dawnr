"""No wrong answer judged is not evidence that a specification pins the answer down (2026-11-26).

`spec_check.complete` says None when no mutant of either family was judged, and the gate, the scores and the RL
reward each read None as "not failing", so `ensures true` passed wherever no wrong answer was judged (the t-track
found MBPP 490 on a branch). The rule: the verify gate refuses it with a reason, and no score or reward counts it
as strong. The specification here is the vacuous one, `ensures true`, over a function whose answer is the same
for every input; the answer's value type is stood in for by patching `spec_check.mutations` to find no mutant,
which is what it says of a value it has no mutations for, and the other family has no other answer to offer."""
import random
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import debug_rows                                               # noqa: E402
import graded_pool                                              # noqa: E402
import rl_reward                                                # noqa: E402
import spec_check                                               # noqa: E402
import spec_first                                               # noqa: E402
import spec_gate                                                # noqa: E402
import surface                                                  # noqa: E402

VACUOUS = "t 1\ntask zero(n: int) returns (r: int)\n  ensures true\n{\n  r := 0;\n}\n"
ENTRY = {"fn": "zero", "rec": {"code": "def zero(n):\n    return 0\n", "test_list": ["assert zero(3)==0"], "text": ""},
         "points": [{"ok": True, "fn": "zero", "args": [("int", 3)], "expected": ("int", 0)}]}
REPLY = "```t\n" + VACUOUS + "```"


def unjudged():
    """The check's own result for `ensures true` where no wrong answer can be judged."""
    with mock.patch.object(spec_check, "mutations", lambda value: []):
        return spec_check.check_task(surface.parse(VACUOUS), ENTRY, 50, random.Random(1))


class Unjudged(unittest.TestCase):
    def test_the_check_agrees_and_judges_no_wrong_answer(self):
        r = unjudged()
        self.assertEqual(r["status"], "agrees")
        self.assertGreaterEqual(r["draws"], 10)
        self.assertNotIn("completeness", r)
        self.assertNotIn("cross_completeness", r)
        self.assertIsNone(spec_check.complete(r))          # unchanged: complete still reports what it measured

    def test_pins_down_is_true_only_when_a_wrong_answer_was_judged_and_rejected(self):
        self.assertFalse(spec_check.pins_down({"status": "agrees"}))
        self.assertFalse(spec_check.pins_down({"completeness": 0.5}))
        self.assertTrue(spec_check.pins_down({"completeness": 0.6}))
        self.assertTrue(spec_check.pins_down({"completeness": 0.9, "cross_completeness": 0.7}))
        self.assertTrue(spec_check.no_wrong_answer_judged({"status": "agrees"}))
        self.assertFalse(spec_check.no_wrong_answer_judged({"completeness": 0.0}))

    def test_the_verify_gate_refuses_it_and_says_why(self):
        r = unjudged()
        self.assertFalse(spec_gate.passes(r))
        self.assertEqual(spec_gate.reason(r), "no wrong answer could be judged against the specification")

    def test_the_gates_other_reasons_stay(self):
        self.assertEqual(spec_gate.reason({"status": "agrees", "draws": 100, "completeness": 0.2}), "weak specification")
        self.assertEqual(spec_gate.reason({"status": "agrees", "draws": 100, "completeness": 1.0}), "passes")
        self.assertEqual(spec_gate.reason({"status": "disagrees"}), "the specification is false at the Python's answer")

    def test_the_reference_keep_rule_refuses_it(self):
        self.assertFalse(spec_first.reference_keeps(unjudged()))
        self.assertTrue(spec_first.reference_keeps({"status": "agrees", "draws": 100, "completeness": 0.6}))

    def test_the_graded_pool_refuses_it_with_its_own_reason(self):
        import test_graded_pool as g
        s = g.sample()
        key = f"{s['tag']}/{s['name']}"
        ev = g.evidence(s)
        ev[key].pop("completeness", None)
        ev[key].pop("cross_completeness", None)
        self.assertEqual(graded_pool.rejection(s, ev, "v5", 1), "spec-no-wrong-answer-judged")

    def test_a_self_debugging_row_says_nothing_could_be_judged(self):
        said = debug_rows.spec_message({"fn": "zero", "rec": ENTRY["rec"], "points": ENTRY["points"]},
                                       surface.parse(VACUOUS), unjudged())
        self.assertTrue(said and said.startswith(debug_rows.SPEC_WEAK))
        self.assertIn("No wrong answer could be judged", said)

    def test_a_proof_of_it_earns_no_strong_reward(self):
        with mock.patch.object(spec_check, "mutations", lambda value: []):
            s = rl_reward.local_signals(1, REPLY, ENTRY)
        self.assertEqual(s["tests"], "pass")
        self.assertEqual(s["spec"]["status"], "agrees")
        self.assertTrue(s["spec"]["weak"])
        # the lazy-program check (`exploit`) is its own rule and flags `ensures true` too; it is set aside here so the
        # tier shows what the completeness rule alone does
        s = dict(s, exploit=None)
        self.assertEqual(rl_reward.tier(s, "verified / refuted"), "proved-weak")
        self.assertLess(rl_reward.reward(s, "verified / refuted"), rl_reward.TIERS["proved"])


if __name__ == "__main__":
    unittest.main()
