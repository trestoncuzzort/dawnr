import unittest

import torch
from torch.nn import functional as F

from next_latent import NextLatent


class NextLatentTests(unittest.TestCase):
    def test_losses_match_explicit_calculation_and_detach_targets(self):
        objective = NextLatent(2)
        for parameter in objective.parameters():
            parameter.data.zero_()
        hidden = torch.tensor([[[1., 0.], [0., 2.]]], requires_grad=True)
        embeddings = torch.randn_like(hidden, requires_grad=True)
        head = torch.eye(2, requires_grad=True)
        result = objective(hidden, embeddings, torch.zeros(1, 2, dtype=torch.long), head)
        expected_regression = (0.5 + 1.5) / 2
        target = torch.softmax(torch.tensor([0., 2.]), dim=0)
        expected_kl = (target * (target.log() - torch.log_softmax(torch.tensor([1., 0.]), dim=0))).sum()
        self.assertAlmostEqual(result["regression"].item(), expected_regression)
        torch.testing.assert_close(result["kl"], expected_kl)
        (result["regression"] + result["kl"]).backward()
        self.assertIsNone(head.grad)
        self.assertEqual(hidden.grad[:, 1].abs().sum().item(), 0)
        self.assertGreater(hidden.grad[:, 0].abs().sum().item(), 0)

    def test_rollout_and_boundaries(self):
        torch.manual_seed(2)
        objective = NextLatent(4, horizon=3)
        hidden = torch.randn(1, 5, 4, requires_grad=True)
        embeddings = torch.randn_like(hidden, requires_grad=True)
        result = objective(hidden, embeddings, torch.tensor([[0, 0, 0, 1, -1]]),
                           torch.randn(7, 4))
        self.assertEqual(result["pairs"], [2, 1, 0])
        (result["regression"] + result["kl"]).backward()
        self.assertGreater(embeddings.grad[:, 1:3].abs().sum().item(), 0)
        self.assertEqual(embeddings.grad[:, 3:].abs().sum().item(), 0)
        self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all()
                            for p in objective.parameters()))

    def test_single_token_has_finite_zero_loss(self):
        objective = NextLatent(4, horizon=2)
        h = torch.randn(1, 1, 4, requires_grad=True)
        result = objective(h, h, torch.zeros(1, 1, dtype=torch.long), torch.randn(7, 4))
        loss = result["regression"] + result["kl"]
        loss.backward()
        self.assertEqual(loss.item(), 0)


if __name__ == "__main__":
    unittest.main()
