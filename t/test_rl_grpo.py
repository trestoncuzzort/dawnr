"""t/rl_grpo.py's loss on toy inputs (arXiv:2402.03300 eq. 3 and 4). Needs torch;
skipped where it is not installed (run with ~/.venv-locallm/bin/python)."""

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import torch
    import rl_grpo
except ImportError:                                               # pragma: no cover
    torch = None


@unittest.skipIf(torch is None, "torch not installed")
class Advantages(unittest.TestCase):
    def test_normalised_within_each_group(self):
        r = torch.tensor([[0.0, 1.0, 0.0, 1.0], [0.1, 0.1, 0.5, 1.0]])
        a = rl_grpo.group_advantages(r)
        self.assertTrue(torch.allclose(a.mean(dim=1), torch.zeros(2), atol=1e-6))
        self.assertTrue(torch.allclose(a.std(dim=1), torch.ones(2), atol=1e-4))
        self.assertGreater(a[1, 3], a[1, 2])
        self.assertGreater(a[1, 2], a[1, 0])

    def test_mean_scale_keeps_a_format_step_small(self):
        # a group whose only spread is 0 vs 0.05: GRPO's std makes it +-1-sized, Dr. GRPO keeps it 0.05-sized
        r = torch.tensor([[0.0, 0.05, 0.0, 0.05], [0.0, 1.0, 0.0, 1.0]])
        std = rl_grpo.group_advantages(r)
        mean = rl_grpo.group_advantages(r, scale="mean")
        self.assertAlmostEqual(float(std[0].abs().max()), float(std[1].abs().max()), places=4)
        self.assertAlmostEqual(float(mean[0, 1]), 0.025, places=6)
        self.assertAlmostEqual(float(mean[1, 1]), 0.5, places=6)

    def test_equal_rewards_give_zero_not_nan(self):
        a = rl_grpo.group_advantages(torch.tensor([[0.1, 0.1, 0.1], [1.0, 1.0, 1.0]]))
        self.assertTrue(torch.equal(a, torch.zeros(2, 3)))


@unittest.skipIf(torch is None, "torch not installed")
class Loss(unittest.TestCase):
    def setUp(self):
        self.mask = torch.tensor([[1, 1, 1, 0], [1, 1, 0, 0]])

    def test_on_policy_at_reference_is_minus_mean_advantage(self):
        lp = torch.log(torch.full((2, 4), 0.5))
        adv = torch.tensor([1.0, -3.0])
        loss, s = rl_grpo.grpo_loss(lp, lp, lp, adv, self.mask, clip=0.2, beta=0.04)
        self.assertAlmostEqual(float(loss), -(1.0 - 3.0) / 2, places=6)
        self.assertAlmostEqual(s["kl"], 0.0, places=7)
        self.assertEqual(s["clip_frac"], 0.0)

    def test_k3_kl_matches_its_formula_and_is_positive(self):
        lp = torch.log(torch.tensor([[0.5, 0.5, 0.5, 0.5], [0.2, 0.2, 0.2, 0.2]]))
        ref = torch.log(torch.tensor([[0.25, 0.25, 0.25, 0.25], [0.4, 0.4, 0.4, 0.4]]))
        adv = torch.zeros(2)
        loss, s = rl_grpo.grpo_loss(lp, lp, ref, adv, self.mask, clip=0.2, beta=1.0)
        k3 = lambda p, q: q / p - math.log(q / p) - 1              # noqa: E731
        want = (k3(0.5, 0.25) + k3(0.2, 0.4)) / 2
        self.assertAlmostEqual(s["kl"], want, places=5)
        self.assertAlmostEqual(float(loss), want, places=5)       # zero advantage: loss is beta * KL
        self.assertGreater(want, 0)

    def test_clipping_stops_the_gradient_past_the_trust_region(self):
        old = torch.log(torch.full((1, 4), 0.5))
        mask = torch.tensor([[1, 1, 1, 1]])
        for adv, ratio, moves in ((1.0, 1.5, False), (1.0, 1.1, True), (-1.0, 0.5, False), (-1.0, 1.5, True)):
            lp = (old + math.log(ratio)).clone().requires_grad_(True)
            loss, _ = rl_grpo.grpo_loss(lp, old, lp.detach(), torch.tensor([adv]), mask, clip=0.2, beta=0.0)
            loss.backward()
            self.assertEqual(bool(lp.grad.abs().sum() > 0), moves, (adv, ratio))

    def test_gradient_raises_a_good_answer_and_lowers_a_bad_one(self):
        lp = torch.log(torch.full((2, 4), 0.5)).requires_grad_(True)
        loss, _ = rl_grpo.grpo_loss(lp, lp.detach(), lp.detach(), torch.tensor([1.0, -1.0]),
                                    torch.ones(2, 4, dtype=torch.long), clip=0.2, beta=0.04)
        loss.backward()
        self.assertTrue((lp.grad[0] < 0).all())     # descending the loss raises answer 0's log-probs
        self.assertTrue((lp.grad[1] > 0).all())

    def test_padding_is_ignored(self):
        lp = torch.log(torch.full((2, 4), 0.5))
        other = lp.clone()
        other[:, 3] = -50.0                           # garbage where the mask is 0 in both rows
        a, _ = rl_grpo.grpo_loss(lp, lp, lp, torch.tensor([1.0, 2.0]), self.mask, clip=0.2, beta=0.04)
        b, _ = rl_grpo.grpo_loss(other, lp, lp, torch.tensor([1.0, 2.0]), self.mask, clip=0.2, beta=0.04)
        self.assertAlmostEqual(float(a), float(b), places=6)

    def test_token_logprobs_masks_only_the_answer(self):
        torch.manual_seed(0)
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "locallm"))
        from model import GPT, GPTConfig
        m = GPT(GPTConfig(vocab_size=11, block_size=16, n_layer=1, n_head=2, n_embd=8))
        x = torch.tensor([[1, 2, 3, 4, 5, 0], [1, 2, 3, 4, 5, 6]])
        logp, mask = rl_grpo.token_logprobs(m, x, [2, 3], [5, 6])
        self.assertEqual(mask.tolist(), [[False, True, True, True, False],
                                         [False, False, True, True, True]])
        full = torch.log_softmax(m(x)[0], dim=-1)
        self.assertAlmostEqual(float(logp[0, 1]), float(full[0, 1, 3]), places=5)   # scores token x[0, 2]


if __name__ == "__main__":
    unittest.main()
