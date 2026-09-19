import copy
import unittest

import torch

from model import GPT, GPTConfig
from research_model import ResearchModel


class ResearchModelTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(23)
        self.config = GPTConfig(vocab_size=23, block_size=8, n_layer=2,
                                n_head=2, n_embd=16, dropout=0, architecture="modern")
        self.core = GPT(self.config)
        self.inputs = torch.randint(23, (2, 8))
        self.targets = torch.randint(23, (2, 8))
        self.targets[:, :3] = -1
        self.segments = torch.zeros_like(self.inputs)

    def test_baseline_matches_loss_and_gradients(self):
        control = copy.deepcopy(self.core)
        wrapper = ResearchModel(self.core)
        expected, loss = control(self.inputs, self.targets)
        actual, losses = wrapper(self.inputs, self.targets, self.segments)
        torch.testing.assert_close(actual, expected, rtol=0, atol=0)
        torch.testing.assert_close(losses["total"], loss, rtol=0, atol=0)
        loss.backward()
        losses["total"].backward()
        for a, b in zip(control.parameters(), self.core.parameters()):
            torch.testing.assert_close(a.grad, b.grad, rtol=0, atol=0)

    def test_step_and_checkpoint_roundtrip(self):
        wrapper = ResearchModel(self.core, latent=True, horizon=2)
        optimizer = torch.optim.AdamW(wrapper.parameters(), lr=1e-3)
        _, losses = wrapper(self.inputs, self.targets, self.segments)
        losses["total"].backward()
        self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all()
                            for p in wrapper.parameters()))
        optimizer.step()
        restored = GPT(self.config)
        restored.load_state_dict(wrapper.inference_state_dict(), strict=True)
        torch.testing.assert_close(restored(self.inputs)[0], self.core(self.inputs)[0], rtol=0, atol=0)
        self.assertEqual(len(self.core.transformer.ln_f._forward_hooks), 0)
        self.assertEqual(len(self.core.transformer.wte._forward_hooks), 0)

    def test_rejects_supervised_padding(self):
        self.segments[0, -1] = -1
        with self.assertRaises(ValueError):
            ResearchModel(self.core)(self.inputs, self.targets, self.segments)

    def test_execution_loss_preserves_completion_weight(self):
        wrapper = ResearchModel(self.core)
        execution = torch.full_like(self.targets, -1)
        execution[:, 1:3] = 2
        _, baseline = wrapper(self.inputs, self.targets, self.segments)
        _, treatment = wrapper(self.inputs, self.targets, self.segments, execution)
        torch.testing.assert_close(baseline["completion"], treatment["completion"], rtol=0, atol=0)
        torch.testing.assert_close(treatment["total"], baseline["total"] + treatment["execution"])
        execution[0, 5] = 3
        with self.assertRaises(ValueError):
            wrapper(self.inputs, self.targets, self.segments, execution)


if __name__ == "__main__":
    unittest.main()
