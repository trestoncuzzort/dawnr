"""test_quant_int8.py — weight-only int8 quantization of the torch sampling path.

    python3 -m unittest test_quant_int8 -v

Needs torch (see model.py's own tests for why: this file is not
plain_generate.py, and makes no claim to run with nothing installed).
"""
from __future__ import annotations

import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import torch  # noqa: E402
import torch.nn as nn  # noqa: E402
import torch.nn.functional as F  # noqa: E402

from model import GPT, GPTConfig  # noqa: E402
import quant_int8 as qi  # noqa: E402


def tiny_gpt(seed=0, vocab_size=13, block_size=12, n_layer=2, n_head=2, n_embd=16):
    torch.manual_seed(seed)
    cfg = GPTConfig(vocab_size=vocab_size, block_size=block_size, n_layer=n_layer,
                    n_head=n_head, n_embd=n_embd, dropout=0.0)
    model = GPT(cfg)
    model.eval()
    return model, cfg


class QuantizeTensor(unittest.TestCase):
    """quantize_tensor_per_channel_symmetric: plain_generate.py's _quantize_row
    (arXiv:1806.08342 sections 2.2 and 2.6), the torch way."""

    def test_an_all_zero_row_gets_scale_one(self):
        q, scale = qi.quantize_tensor_per_channel_symmetric(torch.zeros(3, 5))
        self.assertTrue(torch.equal(scale, torch.ones(3)))
        self.assertTrue(torch.equal(q, torch.zeros(3, 5, dtype=torch.int8)))

    def test_values_stay_in_the_restricted_range(self):
        torch.manual_seed(1)
        q, scale = qi.quantize_tensor_per_channel_symmetric(torch.randn(11, 23) * 5)
        self.assertEqual(q.dtype, torch.int8)
        self.assertTrue(bool((q >= -127).all() and (q <= 127).all()))
        self.assertTrue(bool((scale > 0).all()))

    def test_the_row_peak_lands_on_the_edge_of_the_range(self):
        w = torch.tensor([[0.3, -1.2, 0.9], [2.0, -2.0, 1.0]])
        q, scale = qi.quantize_tensor_per_channel_symmetric(w)
        self.assertEqual(q[0].abs().max().item(), 127)
        self.assertAlmostEqual(scale[0].item(), 1.2 / 127.0, places=6)
        self.assertEqual(q[1].abs().max().item(), 127)

    def test_rejects_a_non_2d_tensor(self):
        with self.assertRaises(ValueError):
            qi.quantize_tensor_per_channel_symmetric(torch.randn(4))

    def test_dequantize_is_the_inverse_operation(self):
        torch.manual_seed(2)
        w = torch.randn(9, 14)
        q, scale = qi.quantize_tensor_per_channel_symmetric(w)
        back = qi.dequantize_per_channel_symmetric(q, scale)
        self.assertTrue(torch.equal(back, q.to(scale.dtype) * scale.unsqueeze(1)))
        half_step = (scale / 2).unsqueeze(1)   # within half a quantization step, row by row
        self.assertTrue(bool((back - w).abs().le(half_step + 1e-6).all()))


class QuantizedLinearModule(unittest.TestCase):
    def test_matches_a_manual_dequantized_linear(self):
        torch.manual_seed(3)
        linear = nn.Linear(10, 6)
        ql = qi.QuantizedLinear.from_linear(linear)
        x = torch.randn(4, 10)
        got = ql(x)
        want = F.linear(x, ql.weight_int8.float() * ql.scale.unsqueeze(1), linear.bias)
        self.assertTrue(torch.allclose(got, want, atol=1e-6))

    def test_close_to_but_not_exactly_the_float_linear(self):
        torch.manual_seed(4)
        linear = nn.Linear(32, 32)
        ql = qi.QuantizedLinear.from_linear(linear)
        x = torch.randn(5, 32)
        float_out, quant_out = linear(x), ql(x)
        self.assertFalse(torch.equal(float_out, quant_out))
        self.assertTrue(torch.allclose(float_out, quant_out, atol=0.2, rtol=0.05))

    def test_rejects_a_non_int8_weight_or_a_mismatched_scale(self):
        with self.assertRaises(ValueError):
            qi.QuantizedLinear(torch.zeros(3, 4, dtype=torch.float32), torch.ones(3), None)
        with self.assertRaises(ValueError):
            qi.QuantizedLinear(torch.zeros(3, 4, dtype=torch.int8), torch.ones(2), None)

    def test_no_bias_is_carried_through_as_none(self):
        linear = nn.Linear(5, 3, bias=False)
        ql = qi.QuantizedLinear.from_linear(linear)
        self.assertIsNone(ql.bias)
        self.assertEqual(ql(torch.randn(2, 5)).shape, (2, 3))

    def test_from_linear_does_not_mutate_the_source_module(self):
        linear = nn.Linear(6, 4)
        original = linear.weight.detach().clone()
        qi.QuantizedLinear.from_linear(linear)
        self.assertTrue(torch.equal(linear.weight.detach(), original))


class QuantizeModel(unittest.TestCase):
    def test_every_linear_is_replaced_and_embeddings_are_not(self):
        model, _ = tiny_gpt()
        # 4 nn.Linear per block (c_attn, attn.c_proj, mlp.c_fc, mlp.c_proj), 2
        # blocks, plus lm_head.
        report = qi.quantize_model_int8(model)
        self.assertEqual(report.modules_quantized, 4 * 2 + 1)
        for module in model.modules():
            self.assertNotIsInstance(module, nn.Linear)
        self.assertIsInstance(model.transformer.wte, nn.Embedding)
        self.assertEqual(model.transformer.wte.weight.dtype, torch.float32)
        self.assertIsInstance(model.transformer.wpe, nn.Embedding)
        self.assertIsInstance(model.lm_head, qi.QuantizedLinear)

    def test_is_a_no_op_the_second_time(self):
        model, _ = tiny_gpt()
        first = qi.quantize_model_int8(model)
        second = qi.quantize_model_int8(model)
        self.assertGreater(first.modules_quantized, 0)
        self.assertEqual(second.modules_quantized, 0)

    def test_weight_memory_drops_to_about_a_quarter(self):
        model, _ = tiny_gpt()
        before = qi.linear_weight_bytes(model)
        report = qi.quantize_model_int8(model)
        after = qi.linear_weight_bytes(model)
        self.assertEqual(before, report.float_bytes)
        self.assertEqual(after, report.int8_bytes)
        self.assertAlmostEqual(after, report.float_bytes * report.ratio)
        ratio = after / before
        self.assertLess(ratio, 0.40)
        self.assertGreater(ratio, 0.20)

    def test_quantizing_twice_from_the_same_weights_is_deterministic(self):
        model_a, cfg = tiny_gpt(seed=6)
        model_b = GPT(cfg)
        model_b.load_state_dict(model_a.state_dict())
        model_b.eval()
        qi.quantize_model_int8(model_a)
        qi.quantize_model_int8(model_b)
        x = torch.randint(0, cfg.vocab_size, (2, 7))
        with torch.no_grad():
            logits_a, _ = model_a(x)
            logits_b, _ = model_b(x)
        self.assertTrue(torch.equal(logits_a, logits_b))

    def test_greedy_generation_runs_and_stays_in_range(self):
        model, cfg = tiny_gpt(seed=7, n_embd=32)
        reference = GPT(cfg)
        reference.load_state_dict(model.state_dict())
        reference.eval()
        qi.quantize_model_int8(model)
        idx = torch.randint(0, cfg.vocab_size, (1, 3))
        with torch.no_grad():
            float_out = reference.generate(idx.clone(), 15, temperature=0)
            quant_out = model.generate(idx.clone(), 15, temperature=0)
        self.assertEqual(float_out.shape, quant_out.shape)
        self.assertTrue(bool((quant_out >= 0).all() and (quant_out < cfg.vocab_size).all()))
        # Not asserted to be high: a small random-weight model has no signal to
        # preserve, so quantization noise can and does flip greedy choices.
        # bench_int8.py / bench-int8-results-2026-09-27.json has the measured
        # agreement on the included, trained model, which is what this repo's
        # claim rests on; this only checks the machinery runs end to end.
        agreement = (float_out == quant_out).float().mean().item()
        self.assertGreaterEqual(agreement, 0.0)
        self.assertLessEqual(agreement, 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
