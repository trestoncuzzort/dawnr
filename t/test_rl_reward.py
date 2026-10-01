"""t/rl_reward.py: the tiers, the prompt set's boundary, the cache, and the
batch path with a fake prover (no kernel runs here)."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import loop_filter                                               # noqa: E402
import rl_reward                                                 # noqa: E402
import spec_experiment as se                                     # noqa: E402

ADD_ONE = """```t
t 0
task mbpp_1__inc(x: int) returns (r: int)
  ensures r == x + 1
{
  r := x + 1;
}
```"""
ENTRY = {"fn": "inc", "rec": {"code": "def inc(x):\n    return x + 1\n", "text": "add one"},
         "points": [{"args": [("int", 1)], "expected": ("int", 2)},
                    {"args": [("int", 5)], "expected": ("int", 6)}]}


class Tiers(unittest.TestCase):
    def sig(self, reply, entry=ENTRY):
        return rl_reward.local_signals(1, reply, entry)

    def test_none_for_no_block_and_parse_error(self):
        self.assertEqual(rl_reward.tier(self.sig("no program here")), "none")
        self.assertEqual(rl_reward.tier(self.sig("```t\nt 0\ntask f(x: int) returns (r: int)\n{ * }\n```")), "none")

    def test_parses_but_not_well_formed(self):
        bad = ADD_ONE.replace("r := x + 1;", "r := [x];")      # assigns a seq to an int
        s = self.sig(bad)
        self.assertEqual(s["stage"], "wf")
        self.assertEqual(rl_reward.tier(s), "parses")

    def test_typed_when_tests_fail(self):
        s = self.sig(ADD_ONE.replace("r := x + 1;", "r := x + 2;").replace("r == x + 1", "r == x + 2"))
        self.assertEqual(s["tests"], "fail")
        self.assertEqual(rl_reward.tier(s), "typed")

    def test_tests_then_proved_only_with_clean_dafny(self):
        s = self.sig(ADD_ONE)
        self.assertEqual(s["tests"], "pass")
        self.assertTrue(rl_reward.needs_proof(s))
        self.assertEqual(rl_reward.tier(s), "tests")
        self.assertEqual(rl_reward.tier(s, "refuted / refuted"), "tests")
        self.assertEqual(rl_reward.tier(s, "verified / decorative"), "tests")
        self.assertEqual(rl_reward.tier(s, "verified / refuted"), "proved")
        self.assertEqual(rl_reward.reward(s, "verified / refuted"), 1.0)

    def test_a_spec_the_reference_contradicts_never_reaches_proved(self):
        # right program, wrong specification: the tests pass, the proof would fail
        # anyway, but even a (hypothetical) clean Dafny cell must not pay for it
        s = self.sig(ADD_ONE.replace("ensures r == x + 1", "ensures r == x + 2"))
        self.assertEqual(s["tests"], "pass")
        self.assertFalse(rl_reward.spec_ok(s))
        self.assertFalse(rl_reward.needs_proof(s))
        self.assertEqual(rl_reward.tier(s, "verified / refuted"), "tests")

    def test_a_wrong_program_the_given_tests_miss_is_caught_by_drawn_inputs(self):
        # the inspection gate's case: `n % 2 == 0`-style answers that three assertions do not separate
        entry = {"fn": "is_two", "rec": {"code": "def is_two(x):\n    return x % 2 == 0\n", "text": "even"},
                 "points": [{"args": [("int", 2)], "expected": ("bool", True)},
                            {"args": [("int", 3)], "expected": ("bool", False)}]}
        wrong = "```t\nt 0\ntask mbpp_1__is_two(x: int) returns (r: bool)\n  ensures r == (x == 2)\n{\n  r := x == 2;\n}\n```"
        right = wrong.replace("(x == 2)", "(x % 2 == 0)").replace("x == 2;", "x % 2 == 0;").replace("t 0", "t 1")
        s = self.sig(wrong, entry)
        self.assertEqual(s["tests"], "pass")
        self.assertEqual(s["drawn"]["status"], "fail")
        self.assertEqual(rl_reward.tier(s, "verified / refuted"), "typed")
        s = self.sig(right, entry)
        self.assertEqual(s["drawn"]["status"], "pass")
        self.assertGreater(s["drawn"]["passed"], 10)

    def test_a_reference_that_does_not_reproduce_its_tests_is_not_used(self):
        entry = dict(ENTRY, rec={"code": "def inc(x):\n    return x + 7\n", "text": "add one"})
        s = self.sig(ADD_ONE, entry)
        self.assertEqual(s["drawn"]["status"], "reference does not reproduce its tests")
        self.assertTrue(rl_reward.tests_ok(s))

    def test_a_proof_of_a_weak_spec_scores_below_a_full_one(self):
        s = self.sig(ADD_ONE)
        self.assertFalse(s["spec"].get("weak"))
        weak = dict(s, spec=dict(s["spec"], weak=True))
        self.assertEqual(rl_reward.tier(weak, "verified / refuted"), "proved-weak")
        self.assertLess(rl_reward.reward(weak, "verified / refuted"), rl_reward.reward(s, "verified / refuted"))
        self.assertGreater(rl_reward.reward(weak, "verified / refuted"), rl_reward.TIERS["tests"])

    def test_an_incomplete_spec_measured_is_weak(self):
        # `ensures r > x` agrees with the reference but accepts x + 2, x + 3, ...: the gate's completeness rule
        # (spec_check.complete, both mutant families at least 60%) calls it weak, so its proof is proved-weak
        loose = ADD_ONE.replace("ensures r == x + 1", "ensures r > x")
        s = self.sig(loose)
        self.assertEqual(s["spec"]["status"], "agrees")
        self.assertTrue(s["spec"]["weak"])
        self.assertEqual(rl_reward.tier(s, "verified / refuted"), "proved-weak")
        self.assertFalse(self.sig(ADD_ONE)["spec"]["weak"])

    def test_rewards_are_ordered(self):
        values = [rl_reward.TIERS[t] for t in ("none", "parses", "typed", "tests", "proved-weak", "proved")]
        self.assertEqual(values, sorted(values))
        self.assertEqual(len(set(values)), len(values))


class PromptSet(unittest.TestCase):
    def test_no_held_out_dev_or_excluded_id(self):
        split = json.loads(rl_reward.SPLIT.read_text(encoding="utf-8"))
        pool = se.pool(split["pool"])
        ids = set(rl_reward.rl_prompt_ids(rl_reward.SPLIT, pool))
        policy = loop_filter.decontamination()
        self.assertTrue(ids)
        self.assertFalse(ids & {int(i) for i in split["eval_ids"]})
        self.assertFalse(ids & set(loop_filter.r12_dev_ids()))
        self.assertFalse(ids & set(policy.exclude_train_ids))
        self.assertTrue(ids <= {int(i) for i in split["train_ids"]})


class CacheAndBatch(unittest.TestCase):
    def test_same_answer_graded_once_and_proved_once(self):
        calls = []

        def fake_prove(tasks, **_kw):
            calls.append(sorted(tasks))
            return {name: "verified / refuted" for name in tasks}

        with tempfile.TemporaryDirectory() as tmp:
            cache = rl_reward.RewardCache(Path(tmp) / "r.jsonl")
            pool = {1: ENTRY}
            items = [(1, ADD_ONE), (1, ADD_ONE), (1, "nothing")]
            out = rl_reward.score_many(items, pool, cache, prove_fn=fake_prove)
            self.assertEqual([o["tier"] for o in out], ["proved", "proved", "none"])
            self.assertEqual(len(calls), 1)
            self.assertEqual(len(calls[0]), 1)
            again = rl_reward.score_many(items, pool, rl_reward.RewardCache(Path(tmp) / "r.jsonl"),
                                         prove_fn=fake_prove)
            self.assertEqual([o["reward"] for o in again], [1.0, 1.0, 0.0])
            self.assertEqual(len(calls), 1)                   # all from the cache on disk

    def test_key_ignores_text_outside_the_block(self):
        self.assertEqual(rl_reward.answer_key(1, ADD_ONE), rl_reward.answer_key(1, ADD_ONE + "\n\ntrailing"))
        self.assertNotEqual(rl_reward.answer_key(1, ADD_ONE), rl_reward.answer_key(2, ADD_ONE))


if __name__ == "__main__":
    unittest.main()
