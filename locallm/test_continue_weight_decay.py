"""continue_from_checkpoint --weight-decay (2026-09-29): the continued stage passes the pretraining
recipe's decay through to train.make_optimizer instead of the fine-tune default. The English
pilot's arm B stage 2 ran at the default 0.1 (the r12 sweep's diverging control,
internal/PRETRAIN-R12-2026-09-25.md) and diverged the same way; the registration named the
sweep's 0.8. A resume keeps the decay it started with; runs recorded without the key read as 0.1.
CPU only."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import torch  # noqa: E402

import train as core_train  # noqa: E402
from continue_from_checkpoint import decay_matches  # noqa: E402


class WeightDecayTests(unittest.TestCase):
    def test_make_optimizer_puts_the_decay_on_the_matrices_only(self):
        model = torch.nn.Sequential(torch.nn.Linear(4, 4), torch.nn.LayerNorm(4))
        opt = core_train.make_optimizer(model, 1e-3, 0.8)
        decays = sorted({g["weight_decay"] for g in opt.param_groups})
        self.assertEqual([0.0, 0.8], decays)
        matrices = [p for g in opt.param_groups if g["weight_decay"] == 0.8 for p in g["params"]]
        self.assertTrue(all(p.dim() >= 2 for p in matrices))

    def test_a_resume_keeps_its_decay_and_an_old_record_reads_as_the_default(self):
        self.assertTrue(decay_matches({"weight_decay": 0.8}, {"weight_decay": 0.8}))
        self.assertFalse(decay_matches({"weight_decay": 0.1}, {"weight_decay": 0.8}))
        self.assertTrue(decay_matches({}, {"weight_decay": 0.1}))     # recorded before the key existed
        self.assertFalse(decay_matches({}, {"weight_decay": 0.8}))

    def test_the_flag_defaults_to_the_recorded_fine_tune_value(self):
        src = (HERE / "continue_from_checkpoint.py").read_text(encoding="utf-8")
        self.assertIn('"--weight-decay", type=float, default=0.1', src)
        self.assertIn("make_optimizer(model, args.lr, args.weight_decay)", src)


if __name__ == "__main__":
    unittest.main()
