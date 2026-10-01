"""t/rl_student.py: the band rule and the prompt set's boundaries (no model, no prover)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import rl_reward                                                 # noqa: E402
import rl_student                                                # noqa: E402
import spec_experiment as se                                     # noqa: E402


class Band(unittest.TestCase):
    def test_narrow_band(self):
        passes = {i: (1 if i < 50 else 0) for i in range(100)}
        ids, rule = rl_student.band_of(passes, 4)
        self.assertEqual((len(ids), rule), (50, "1 or 2 of 4"))

    def test_widens_then_stops(self):
        passes = {i: 3 for i in range(45)} | {i: 1 for i in range(45, 50)}
        ids, rule = rl_student.band_of(passes, 4)
        self.assertEqual((len(ids), rule), (50, "1 to 3 of 4"))
        ids, rule = rl_student.band_of({i: 4 for i in range(100)}, 4)
        self.assertEqual(ids, [])
        self.assertIn("fewer than 40", rule)


class PromptSet(unittest.TestCase):
    def test_no_held_out_or_dev_and_rows_apart(self):
        P = se.pool("v5")
        ids = rl_reward.rl_prompt_ids(pool=P)
        some = ids[:3]
        with tempfile.TemporaryDirectory() as d:
            rows = Path(d) / "rows.jsonl"
            rows.write_text("\n".join(json.dumps({"task_id": i}) for i in some) + "\n")
            fns = {P[ids[3]]["fn"]}
            c = rl_student.candidate_ids(P, rows, fns)
        self.assertEqual(set(c["rows"]) & set(c["other"]), set())
        self.assertTrue(set(some) - {i for i in some if P[i]["fn"] in fns} <= set(c["rows"]))
        self.assertFalse(any(P[i]["fn"] in fns for i in c["rows"] + c["other"]))
        dev = {int(l) for l in (Path.home() / "scratch/dev-ids-100.txt").read_text().split()}
        self.assertEqual(dev & set(c["rows"] + c["other"]), set())


if __name__ == "__main__":
    unittest.main()
