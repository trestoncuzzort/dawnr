"""Core architecture, causal masking, and recomputation checks without training a model."""
import copy
import os
import unittest

import torch

from model import GPT, GPTConfig, RMSNorm, RotaryEmbedding


DEVICE = os.environ.get("LOCALLM_TEST_DEVICE", "cpu")


def config(architecture="modern", **updates):
    values = dict(vocab_size=31, block_size=16, n_layer=2, n_head=2,
                  n_embd=32, dropout=0.0, architecture=architecture)
    values.update(updates)
    return GPTConfig(**values)


class ModelCoreTest(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(11)

    def test_old_config_and_weights_load_without_new_fields(self):
        old_config = dict(vocab_size=31, block_size=16, n_layer=2, n_head=2,
                          n_embd=32, dropout=0.0, bias=True)
        old = GPT(GPTConfig(**old_config)).to(DEVICE).eval()
        restored = GPT(GPTConfig(**old_config)).to(DEVICE).eval()
        restored.load_state_dict(old.state_dict(), strict=True)
        ids = torch.randint(31, (2, 8), device=DEVICE)
        torch.testing.assert_close(old(ids)[0], restored(ids)[0], rtol=0, atol=0)
        self.assertIn("transformer.wpe.weight", old.state_dict())
        self.assertEqual(old.total_params() - old.num_params(), 16 * 32)

    def test_modern_checkpoint_round_trip_and_gradients(self):
        model = GPT(config()).to(DEVICE)
        ids = torch.randint(31, (2, 8), device=DEVICE)
        _, loss = model(ids, ids)
        loss.backward()
        for name, value in model.named_parameters():
            self.assertIsNotNone(value.grad, name)
            self.assertTrue(torch.isfinite(value.grad).all(), name)
            self.assertGreater(value.grad.abs().sum().item(), 0, name)
        restored = GPT(GPTConfig(**model.config.__dict__)).to(DEVICE)
        restored.load_state_dict(model.state_dict(), strict=True)
        torch.testing.assert_close(model(ids)[0], restored(ids)[0], rtol=0, atol=0)
        self.assertNotIn("transformer.wpe.weight", model.state_dict())
        self.assertEqual(model.total_params(), model.num_params())

    def test_causal_prefix_and_attention_fallback(self):
        for architecture in ("gpt", "modern"):
            model = GPT(config(architecture)).to(DEVICE).eval()
            ids = torch.randint(31, (2, 12), device=DEVICE)
            original = model(ids)[0]
            changed = ids.clone()
            changed[:, 7:] = (changed[:, 7:] + 1) % 31
            torch.testing.assert_close(original[:, :7], model(changed)[0][:, :7])
            for block in model.transformer.h:
                block.attn.flash = False
            torch.testing.assert_close(original, model(ids)[0], atol=1e-6, rtol=1e-5)

    def test_checkpointing_preserves_dropout_loss_and_gradients(self):
        plain = GPT(config(dropout=0.2)).to(DEVICE).train()
        recompute = copy.deepcopy(plain)
        recompute.config.gradient_checkpointing = True
        ids = torch.randint(31, (2, 12), device=DEVICE)
        torch.manual_seed(91)
        expected, loss_a = plain(ids, ids)
        loss_a.backward()
        torch.manual_seed(91)
        actual, loss_b = recompute(ids, ids)
        loss_b.backward()
        torch.testing.assert_close(expected, actual, rtol=0, atol=0)
        torch.testing.assert_close(loss_a, loss_b, rtol=0, atol=0)
        for (_, a), (_, b) in zip(plain.named_parameters(), recompute.named_parameters()):
            torch.testing.assert_close(a.grad, b.grad, atol=1e-6, rtol=1e-5)

    def test_last_token_projection_matches_full_forward(self):
        for architecture in ("gpt", "modern"):
            model = GPT(config(architecture)).to(DEVICE).eval()
            ids = torch.randint(31, (2, 12), device=DEVICE)
            full, _ = model(ids)
            last, _ = model(ids, only_last=True)
            self.assertEqual(last.shape, (2, 1, 31))
            torch.testing.assert_close(full[:, -1:], last, atol=1e-6, rtol=1e-5)
            with self.assertRaises(ValueError):
                model(ids, ids, only_last=True)

    def test_rotary_preserves_norm_and_identity_at_position_zero(self):
        rotary = RotaryEmbedding(8, 16, 10000).to(DEVICE)
        value = torch.randn(2, 3, 16, 8, device=DEVICE)
        rotated = rotary(value)
        torch.testing.assert_close(rotated[:, :, 0], value[:, :, 0], rtol=0, atol=0)
        torch.testing.assert_close(rotated.square().sum(-1), value.square().sum(-1))

    def test_rmsnorm_matches_definition_at_low_precision(self):
        norm = RMSNorm(32, 1e-5).to(DEVICE)
        value = (torch.randn(2, 8, 32, device=DEVICE) * 1000).to(torch.bfloat16)
        reference = value.float() / (value.float().square().mean(-1, keepdim=True) + 1e-5).sqrt()
        actual = norm(value)
        self.assertTrue(torch.isfinite(actual).all())
        torch.testing.assert_close(actual.float(), reference, atol=0.02, rtol=0.01)

    def test_invalid_modern_head_dimension_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "even head"):
            config(n_embd=30, n_head=2)


if __name__ == "__main__":
    unittest.main()
