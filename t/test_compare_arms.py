"""t/compare_arms.py: every statistic has an oracle, the DP equals brute force, and a null arm is not adopted."""
import io
import itertools
import json
import math
import random
import tempfile
import unittest
from contextlib import redirect_stdout
from fractions import Fraction
from pathlib import Path

import compare_arms as ca


def brute_unpaired(a, b):
    pooled = list(a) + list(b)
    n_b, observed = len(b), sum(b)
    ge = eq = total = 0
    for subset in itertools.combinations(range(len(pooled)), n_b):
        s = sum(pooled[i] for i in subset)
        total += 1
        ge += s >= observed
        eq += s == observed
    return Fraction(ge, total), Fraction(2 * ge - eq, 2 * total)


def brute_paired(a, b):
    d = [y - x for x, y in zip(a, b)]
    observed = sum(d)
    ge = eq = total = 0
    for signs in itertools.product((1, -1), repeat=len(d)):
        s = sum(v * sign for v, sign in zip(d, signs))
        total += 1
        ge += s >= observed
        eq += s == observed
    return Fraction(ge, total), Fraction(2 * ge - eq, 2 * total)


class PermutationTests(unittest.TestCase):
    def test_the_dp_equals_brute_force_at_five_seeds_per_arm(self):
        rnd = random.Random(7)
        for _ in range(300):
            a = [rnd.randint(0, 6) for _ in range(5)]
            b = [rnd.randint(0, 6) for _ in range(5)]
            self.assertEqual(ca.permutation_test(a, b, method="dp"), brute_unpaired(a, b), (a, b))
            self.assertEqual(ca.permutation_test(a, b), brute_unpaired(a, b), (a, b))
        for _ in range(50):
            a = [rnd.randint(0, 6) for _ in range(3)]
            b = [rnd.randint(0, 6) for _ in range(7)]
            self.assertEqual(ca.permutation_test(a, b, method="dp"), brute_unpaired(a, b), (a, b))

    def test_the_sign_flip_dp_equals_enumeration(self):
        rnd = random.Random(11)
        for n in range(5, 13):
            a = [rnd.randint(0, 6) for _ in range(n)]
            b = [rnd.randint(0, 6) for _ in range(n)]
            self.assertEqual(ca.paired_permutation_test(a, b, method="dp"), brute_paired(a, b), (a, b))
            self.assertEqual(ca.paired_permutation_test(a, b), brute_paired(a, b), (a, b))

    def test_exact_values(self):
        self.assertEqual(ca.permutation_test([0] * 5, [5] * 5), (Fraction(1, 252), Fraction(1, 504)))
        self.assertEqual(ca.paired_permutation_test([0] * 5, [1] * 5), (Fraction(1, 32), Fraction(1, 64)))
        self.assertEqual(ca.permutation_test([2, 2, 2], [2, 2, 2])[0], Fraction(1))

    def test_a_permutation_test_of_two_halves_of_one_arm_rejects_at_most_five_percent(self):
        # the exact size: over ALL 252 splits of one 10-seed arm, the share with p <= .05 is <= .05
        rnd = random.Random(3)
        arm = ca.simulate_arm(10, rnd)
        rejected = 0
        for subset in itertools.combinations(range(10), 5):
            a = [arm[i] for i in subset]
            b = [arm[i] for i in range(10) if i not in subset]
            rejected += ca.permutation_test(a, b)[0] <= Fraction(1, 20)
        self.assertLessEqual(rejected / 252, 0.05)
        # and the simulated rate over random half splits of 50 twenty-seed arms
        trials = rejected = 0
        for arm_seed in range(50):
            arm = ca.simulate_arm(20, random.Random(100 + arm_seed))
            for _ in range(20):
                order = list(range(20))
                rnd.shuffle(order)
                a = [arm[i] for i in order[:10]]
                b = [arm[i] for i in order[10:]]
                trials += 1
                rejected += ca.permutation_test(a, b)[0] <= Fraction(1, 20)
        self.assertLessEqual(rejected / trials, 0.05)


class OracleTests(unittest.TestCase):
    def test_mcnemar_mid_p_reproduces_fagerland(self):
        self.assertEqual(ca.mcnemar_exact_two_sided(1, 7), Fraction(18, 256))
        self.assertEqual(ca.mcnemar_mid_p(1, 7), Fraction(10, 256))          # 0.0390625
        self.assertAlmostEqual(float(ca.mcnemar_exact_two_sided(6, 16)), 0.0525, places=4)
        self.assertAlmostEqual(float(ca.mcnemar_mid_p(6, 16)), 0.0347, places=4)
        self.assertEqual(ca.mcnemar_mid_p(0, 5), Fraction(1, 32))
        self.assertEqual(ca.mcnemar_mid_p(3, 3), Fraction(54, 64))           # 0.84375, the tie case
        self.assertEqual(ca.mcnemar_mid_p(0, 0), Fraction(1))

    def test_expected_best_of_n(self):
        self.assertEqual(ca.expected_best_of([1, 2, 3], 2), Fraction(22, 9))
        self.assertEqual(ca.expected_best_of([1, 2, 3], 1), Fraction(2))
        values = [0, 1, 1, 4]
        draws = itertools.product(values, repeat=3)
        brute = Fraction(sum(max(d) for d in draws), len(values) ** 3)
        self.assertEqual(ca.expected_best_of(values, 3), brute)

    def test_probability_of_outperforming_counts_ties_as_half(self):
        self.assertEqual(ca.prob_outperform([1, 2], [2, 3]), Fraction(7, 8))
        self.assertEqual(ca.prob_outperform([1, 2], [2, 2], paired=True), Fraction(3, 4))
        lo, hi = ca.bootstrap_ci([1, 2], [2, 3], paired=False, nboot=200, seed=0)
        self.assertTrue(0 <= lo <= hi <= 1)

    def test_wilson_intervals_in_problems(self):
        # eval-stats.md prints 2 -> [0.6, 7.2] and the review 232 x [0.24%, 3.09%] = [0.55, 7.17];
        # the formula itself gives [0.549, 7.165], so the oracle is held to a hundredth
        for k, want in ((0, (0.0, 3.78)), (2, (0.55, 7.16)), (5, (2.14, 11.47))):
            lo, hi = ca.wilson(k, 232)
            self.assertAlmostEqual(lo, want[0], delta=0.01)
            self.assertAlmostEqual(hi, want[1], delta=0.01)

    def test_verdict_rule_and_its_boundaries(self):
        self.assertEqual(ca.verdict(Fraction(1, 20), 0.76), "ADOPT")
        self.assertEqual(ca.verdict(Fraction(1, 20), 0.75), "NOT MEANINGFUL")
        self.assertEqual(ca.verdict(Fraction(6, 100), 0.9), "INCONCLUSIVE")
        self.assertEqual(ca.verdict(Fraction(6, 100), 0.5), "NOT MEANINGFUL")


def export(tags, n_problems=20, schema=2):
    ids = list(range(1, n_problems + 1))
    panel = {"task_ids": ids, "tags": {}}
    for tag, (clean, recited) in tags.items():
        entry = {"clean": {str(i): i in clean for i in ids}, "clean_count": len(clean),
                 "spec_agrees": {str(i): False for i in ids}, "spec_agrees_count": 0,
                 "tests_pass": {str(i): i in clean for i in ids}, "tests_pass_count": len(clean),
                 "answered_count": n_problems, "partial": False}
        if recited is not None:
            entry["recited"] = {str(i): i in recited for i in ids}
            entry["recited_count"] = len(recited)
        panel["tags"][tag] = entry
    return {"schema_version": schema, "split": "split.json", "overlap_ids": [], "allow_partial": False,
            "panels": {f"all-{n_problems}": panel, f"clean-{n_problems}": panel}}


class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write(self, data, name="outcomes.json"):
        path = self.root / name
        path.write_text(json.dumps(data))
        return path

    def run_main(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = ca.main(list(args))
        return rc, out.getvalue()

    def test_separated_arms_are_adopted_and_identical_arms_never(self):
        tags = {}
        for s in range(10):
            tags[f"a{s}"] = ({1, 2} if s % 2 else {1}, None)
            tags[f"b{s}"] = ({1, 2, 3, 4, 5, 6} if s % 2 else {1, 2, 3, 4, 5}, None)
        path = self.write(export(tags))
        prereg = self.root / "prereg.md"
        prereg.write_text("# r12\nseeds: 10\nmetric: clean\n")
        arms = ("--arm", "base=" + ",".join(f"a{s}" for s in range(10)),
                "--arm", "new=" + ",".join(f"b{s}" for s in range(10)))
        rc, out = self.run_main("--outcomes", str(path), *arms, "--prereg", str(prereg), "--nboot", "300")
        self.assertEqual(rc, 0)
        self.assertIn("verdict: ADOPT", out)
        self.assertIn("base: 1.5 [1-2] (10 seeds)", out)
        self.assertIn("new: 5.5 [5-6] (10 seeds)", out)
        rc, out = self.run_main("--outcomes", str(path), "--arm", "x=" + ",".join(f"a{s}" for s in range(5)),
                                "--arm", "y=" + ",".join(f"a{s}" for s in range(5, 10)), "--nboot", "300")
        self.assertNotIn("verdict: ADOPT", out)
        self.assertIn("unregistered", out)

    def test_refusals(self):
        tags = {f"a{s}": ({1}, None) for s in range(3)}
        tags.update({f"b{s}": ({1, 2}, None) for s in range(3)})
        tags["part"] = ({1}, None)
        data = export(tags)
        data["panels"]["clean-20"]["tags"]["part"]["partial"] = True
        data["panels"]["all-20"]["tags"]["part"]["partial"] = True
        path = self.write(data)
        prereg = self.root / "prereg.md"
        prereg.write_text("seeds: 5\n")
        base = "--arm", "base=a0,a1,a2"
        with self.assertRaisesRegex(SystemExit, "seeds"):
            ca.main(["--outcomes", str(path), *base, "--arm", "new=b0,b1,b2", "--prereg", str(prereg)])
        with self.assertRaisesRegex(SystemExit, "partial"):
            ca.main(["--outcomes", str(path), *base, "--arm", "new=part,b1,b2"])
        with self.assertRaisesRegex(SystemExit, "nope"):
            ca.main(["--outcomes", str(path), *base, "--arm", "new=nope,b1,b2"])
        with self.assertRaisesRegex(SystemExit, "two arms"):
            ca.main(["--outcomes", str(path), *base, "--arm", "new=b0,b1,b2", "--arm", "third=b0"])
        with self.assertRaisesRegex(SystemExit, "paired"):
            ca.main(["--outcomes", str(path), *base, "--arm", "new=b0,b1", "--paired"])
        with self.assertRaisesRegex(SystemExit, "recited"):
            ca.main(["--outcomes", str(path), *base, "--arm", "new=b0,b1,b2", "--metric", "written-clean"])
        prereg.write_text("seeds: 3\nmetric: tests-pass\n")
        with self.assertRaisesRegex(SystemExit, "metric"):
            ca.main(["--outcomes", str(path), *base, "--arm", "new=b0,b1,b2", "--prereg", str(prereg),
                     "--metric", "clean"])
        prereg.write_text("seeds: 3\nseeds: 4\n")
        with self.assertRaisesRegex(SystemExit, "seeds"):
            ca.main(["--outcomes", str(path), *base, "--arm", "new=b0,b1,b2", "--prereg", str(prereg)])

    def test_two_single_checkpoints_get_mcnemar_and_no_recipe_verdict(self):
        path = self.write(export({"one": ({1, 2, 3, 4, 5, 6, 7, 8}, None), "two": ({1}, None)}))
        rc, out = self.run_main("--outcomes", str(path), "--arm", "A=two", "--arm", "B=one", "--nboot", "50")
        self.assertEqual(rc, 0)
        self.assertIn("McNemar", out)
        self.assertIn("n12=7", out)
        self.assertIn("verdict: INCONCLUSIVE", out)

    def test_written_clean_uses_the_recited_map(self):
        path = self.write(export({"a": ({1, 2, 3}, {1, 2}), "b": ({1, 2, 3}, set())}))
        rc, out = self.run_main("--outcomes", str(path), "--arm", "A=a", "--arm", "B=b",
                                "--metric", "written-clean", "--nboot", "50")
        self.assertIn("A: 1 [1-1] (1 seed)", out)
        self.assertIn("B: 3 [3-3] (1 seed)", out)


if __name__ == "__main__":
    unittest.main()
