import unittest

import torch

from latent_objective import FutureStateObjective
from model import GPT, GPTConfig


class FutureStateTests(unittest.TestCase):
    def test_auxiliary_training_reaches_owned_core_without_changing_logits(self):
        torch.manual_seed(8)
        model = GPT(GPTConfig(vocab_size=19, block_size=8, n_layer=1,
                              n_head=2, n_embd=16, dropout=0, architecture="modern"))
        objective = FutureStateObjective(16, (1, 2))
        tokens = torch.randint(19, (2, 8))
        baseline = model(tokens)[0].detach()
        states = []
        handle = model.transformer.ln_f.register_forward_hook(
            lambda module, args, output: states.append(output))
        try:
            logits, language_loss = model(tokens, tokens)
        finally:
            handle.remove()
        torch.testing.assert_close(logits, baseline, rtol=0, atol=0)
        losses, _ = objective(states[0], torch.zeros_like(tokens))
        # Check the auxiliary path alone actually trains the backbone.
        sum(losses.values()).backward(retain_graph=True)
        self.assertGreater(model.transformer.wte.weight.grad.abs().sum().item(), 0)
        language_loss.backward()
        self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all()
                            for p in model.parameters()))

    def test_future_target_is_detached(self):
        torch.manual_seed(4)
        head = FutureStateObjective(4, (2,))
        hidden = torch.randn(1, 3, 4, requires_grad=True)
        losses, counts = head(hidden, torch.zeros(1, 3, dtype=torch.long))
        losses[2].backward()
        self.assertEqual(counts[2], 1)
        self.assertGreater(hidden.grad[:, 0].abs().sum().item(), 0)
        self.assertEqual(hidden.grad[:, 1:].abs().sum().item(), 0)
        self.assertTrue(all(p.grad is not None for p in head.parameters()))

    def test_no_cross_example_or_padding_targets(self):
        head = FutureStateObjective(4, (1, 2))
        hidden = torch.randn(1, 7, 4, requires_grad=True)
        # Reused ID after another example must not create a crossing pair.
        segments = torch.tensor([[0, 0, 1, 0, 0, -1, -1]])
        losses, counts = head(hidden, segments)
        self.assertEqual(counts, {1: 2, 2: 0})
        self.assertEqual(losses[2].item(), 0)
        sum(losses.values()).backward()
        self.assertTrue(torch.isfinite(hidden.grad).all())

    def test_short_sequence_has_finite_zero_gradients(self):
        head = FutureStateObjective(4, (4,))
        hidden = torch.randn(1, 2, 4, requires_grad=True)
        losses, counts = head(hidden, torch.zeros(1, 2, dtype=torch.long))
        losses[4].backward()
        self.assertEqual(counts[4], 0)
        self.assertTrue(all(p.grad is not None and p.grad.abs().sum() == 0
                            for p in head.parameters()))


if __name__ == "__main__":
    unittest.main()
