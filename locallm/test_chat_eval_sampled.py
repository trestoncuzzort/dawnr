"""chat_eval --samples (2026-09-30): the base rate by sampling. r12's core registration says that
at spec_agrees 0 the base rate is measured by sampling, 64 draws per problem through the checker,
before any reward is built. pass_at_k is human-eval's unbiased estimator
(https://github.com/openai/human-eval, arXiv:2107.03374); sampled_summary turns per-problem counts
into the problems with any such draw, the per-draw rate, pass@k and the difficulty band of
t/RL-DESIGN-2026-09-26.md. The greedy path is untouched. No torch, no kernel."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "t"))

import chat_eval  # noqa: E402


def problem(tid, n, **counts):
    return {"task_id": tid, "n": n, **{k: counts.get(k, 0) for k in chat_eval.SAMPLED}}


class PassAtK(unittest.TestCase):
    def test_known_values(self):
        self.assertEqual(chat_eval.pass_at_k(64, 0, 16), 0.0)
        self.assertEqual(chat_eval.pass_at_k(64, 64, 1), 1.0)
        self.assertAlmostEqual(chat_eval.pass_at_k(4, 1, 1), 0.25)
        self.assertAlmostEqual(chat_eval.pass_at_k(4, 1, 2), 0.5)      # 1 - C(3,2)/C(4,2)
        self.assertEqual(chat_eval.pass_at_k(4, 1, 4), 1.0)            # every draw taken: the one correct is in
        self.assertAlmostEqual(chat_eval.pass_at_k(64, 1, 16), 0.25)   # one correct of 64: 16/64

    def test_refuses_impossible_counts(self):
        for n, c, k in ((4, 5, 1), (4, -1, 1), (4, 1, 5), (4, 1, 0)):
            with self.assertRaises(ValueError):
                chat_eval.pass_at_k(n, c, k)


class SampledSummary(unittest.TestCase):
    def test_counts_rates_band_and_pass_at_k(self):
        rows = [problem(1, 64, well_formed=64, examples_all_pass=8, tests=4, spec_agrees=1),
                problem(2, 64, well_formed=32, examples_all_pass=32, tests=0, spec_agrees=0, examples_pass_spec_disagrees=32),
                problem(3, 64), problem(4, 64, well_formed=1)]
        s = chat_eval.sampled_summary(rows)
        self.assertEqual((s["problems"], s["draws"]), (4, 256))
        self.assertEqual(s["spec_agrees"]["problems_with_any"], 1)
        self.assertEqual(s["spec_agrees"]["draws"], 1)
        self.assertAlmostEqual(s["spec_agrees"]["per_draw"], round(1 / 256, 5))
        self.assertAlmostEqual(s["spec_agrees"]["pass_at"]["16"], round(0.25 / 4, 5))
        self.assertAlmostEqual(s["spec_agrees"]["pass_at"]["64"], 0.25)
        self.assertEqual(s["examples_all_pass"]["problems_with_any"], 2)
        self.assertEqual(s["examples_all_pass"]["in_band"], 1)          # 8/64 is in (0, 1/4]; 32/64 is not
        self.assertEqual(s["examples_pass_spec_disagrees"]["draws"], 32)
        self.assertEqual(s["well_formed"]["problems_with_any"], 3)

    def test_a_k_above_the_fewest_draws_is_left_out(self):
        s = chat_eval.sampled_summary([problem(1, 8, tests=1), problem(2, 16, tests=2)])
        self.assertEqual(sorted(s["tests"]["pass_at"]), ["1", "8"])

    def test_nothing_sampled_is_refused(self):
        with self.assertRaises(ValueError):
            chat_eval.sampled_summary([])


class GreedyPathUnchanged(unittest.TestCase):
    def test_ask_still_decodes_one_greedy_row(self):
        src = (HERE / "chat_eval.py").read_text(encoding="utf-8")
        self.assertIn("engine.generate_batch(prompt, 1, max_tokens=max_tokens, temperature=0.0, seed=0)", src)
        self.assertIn('ap.add_argument("--samples", type=int, default=1', src)

    def test_sampling_refuses_the_other_modes(self):
        for extra in (["--conversations", "x.jsonl"], ["--rescore", "x.rows.jsonl"], ["--dev", "0"],
                      ["--temperature", "0"]):
            with self.assertRaises(SystemExit):
                chat_eval.main(["--model", "m", "--out", "o.json", "--samples", "4", *extra])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
