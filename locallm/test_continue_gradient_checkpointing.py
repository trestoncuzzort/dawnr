"""continue_from_checkpoint --gradient-checkpointing (2026-09-30): r12's core stage 1 was trained on
an 80 GB card with activation checkpointing off; the continuation inherits the init's config and
ran out of memory at batch 16 x 2048 on a 16 GB card. The flag overrides the inherited setting.
torch.utils.checkpoint recomputes each block's forward in the backward pass
(docs.pytorch.org/docs/stable/checkpoint.html; Chen et al., arXiv:1604.06174), so the gradients
are those of the uncheckpointed pass: tested here by equality. CPU only, a few seconds."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import torch  # noqa: E402

import continue_from_checkpoint as cfc  # noqa: E402
from model import GPT, GPTConfig  # noqa: E402


def saved_core(directory, checkpointing):
    cfg = GPTConfig(vocab_size=32, block_size=16, n_layer=3, n_head=2, n_embd=16, dropout=0.0,
                    gradient_checkpointing=checkpointing)
    torch.manual_seed(0)
    model = GPT(cfg)
    path = Path(directory) / "best.pt"
    torch.save({"model": model.state_dict(), "config": cfg.__dict__, "step": 1}, path)
    return path


def gradients(model):
    torch.manual_seed(1)
    idx = torch.randint(0, 32, (4, 16))
    model.train()
    model.zero_grad()
    _, loss = model(idx, idx)
    loss.backward()
    return loss.detach(), {n: p.grad.clone() for n, p in model.named_parameters() if p.grad is not None}


class GradientCheckpointingTests(unittest.TestCase):
    def test_none_keeps_the_init_setting_and_a_value_overrides_it(self):
        with tempfile.TemporaryDirectory() as d:
            off = saved_core(d, False)
            self.assertFalse(cfc.load_core(off, "cpu", 0.0, torch, GPT, GPTConfig)[1].gradient_checkpointing)
            self.assertTrue(cfc.load_core(off, "cpu", 0.0, torch, GPT, GPTConfig,
                                          gradient_checkpointing=True)[1].gradient_checkpointing)
        with tempfile.TemporaryDirectory() as d:
            on = saved_core(d, True)
            self.assertTrue(cfc.load_core(on, "cpu", 0.0, torch, GPT, GPTConfig)[1].gradient_checkpointing)
            self.assertFalse(cfc.load_core(on, "cpu", 0.0, torch, GPT, GPTConfig,
                                           gradient_checkpointing=False)[1].gradient_checkpointing)

    def test_the_override_leaves_the_loss_and_every_gradient_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            path = saved_core(d, False)
            plain = cfc.load_core(path, "cpu", 0.0, torch, GPT, GPTConfig)[0]
            recomputed = cfc.load_core(path, "cpu", 0.0, torch, GPT, GPTConfig, gradient_checkpointing=True)[0]
        loss_a, grads_a = gradients(plain)
        loss_b, grads_b = gradients(recomputed)
        self.assertTrue(torch.equal(loss_a, loss_b))
        self.assertEqual(set(grads_a), set(grads_b))
        for name in grads_a:
            self.assertTrue(torch.equal(grads_a[name], grads_b[name]), name)

    def test_the_flag_defaults_to_inheriting(self):
        src = (HERE / "continue_from_checkpoint.py").read_text(encoding="utf-8")
        self.assertIn('"--gradient-checkpointing", action=argparse.BooleanOptionalAction, default=None', src)
        self.assertIn("gradient_checkpointing=args.gradient_checkpointing", src)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
