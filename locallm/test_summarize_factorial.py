"""Lab tests for the factorial report, whose job is not to overstate a verdict."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ARMS = ("baseline", "latent", "execution", "combined")


def write_study(directory, correct_by_seed):
    """correct_by_seed: {seed: {arm: correct_tasks}}; a missing arm stays pending."""
    study = Path(directory)
    blocks = []
    for seed, cells in correct_by_seed.items():
        arms = []
        for arm in ARMS:
            entry = {"id": f"{arm}-seed{seed}", "arm": arm, "seed": seed,
                     "status": "complete" if arm in cells else "pending", "attempts": []}
            arms.append(entry)
            if arm not in cells:
                continue
            out = study / entry["id"]
            out.mkdir(parents=True)
            (out / "score.json").write_text(json.dumps({
                "by_split": {"eval_pattern": {"tasks": 100, "correct": cells[arm]}},
                "verdicts": {"correct": cells[arm], "wrong_output": 100 - cells[arm]},
                "tests_by_stratum": {"in_range": {"passed": 0, "total": 100}}}))
            (out / "run.json").write_text(json.dumps({
                "accounting": {"train_seconds": 1.0, "answer_tokens": 2,
                               "execution_tokens_supervised": 3},
                "peak_allocated_bytes": 4}))
        blocks.append({"seed": seed, "order": list(ARMS), "arms": arms})
    (study / "study.json").write_text(json.dumps({"blocks": blocks}))
    return study


def report(study):
    result = subprocess.run([sys.executable, str(HERE / "summarize_factorial.py"),
                             "--study", str(study), "--splits", "eval_pattern"],
                            capture_output=True, text=True, check=True)
    return result.stdout


class VerdictTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def study(self, cells):
        return write_study(Path(self.directory.name) / "study", cells)

    def test_an_unfinished_study_decides_nothing(self):
        text = report(self.study({1337: {"baseline": 10, "latent": 12}, 7: {}, 42: {}}))
        self.assertIn("undecided", text)
        self.assertNotIn("**held**", text)
        self.assertNotIn("**falsified**", text)

    def test_one_finished_seed_can_falsify_an_every_seed_claim(self):
        text = report(self.study({1337: {"baseline": 20, "latent": 20,
                                         "execution": 20, "combined": 21}, 7: {}, 42: {}}))
        self.assertIn("falsified** at seed(s) 1337", text)

    def test_all_seeds_passing_is_held(self):
        cells = {"baseline": 10, "latent": 12, "execution": 13, "combined": 30}
        text = report(self.study({seed: dict(cells) for seed in (1337, 7, 42)}))
        self.assertNotIn("undecided", text)
        self.assertEqual(text.count("**held**"), 3)

    def test_the_interaction_is_reported_apart_from_the_additive_gain(self):
        # Combined gains 20 points, but exactly the sum of the two single arms.
        cells = {"baseline": 10, "latent": 20, "execution": 20, "combined": 30}
        text = report(self.study({seed: dict(cells) for seed in (1337, 7, 42)}))
        self.assertIn("| 1337 | +10.0 | +10.0 | +20.0 | +0.0 |", text)
        self.assertIn("the interaction is positive in every seed: **falsified**", text)
        self.assertIn(f"combined beats baseline by at least 5 points in every seed: **held**",
                      text)


if __name__ == "__main__":
    unittest.main()
