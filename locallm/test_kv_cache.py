"""Cached decoding agrees with causal full forward, including window rollover."""
import gc
import os
import unittest
import weakref

import torch

from model import GPT, GPTConfig, RotaryEmbedding


DEVICE = os.environ.get("LOCALLM_TEST_DEVICE", "cpu")


def model_for(architecture, block_size=16):
    torch.manual_seed(173)
    return GPT(GPTConfig(vocab_size=43, block_size=block_size, n_layer=2,
                         n_head=2, n_embd=32, architecture=architecture)).to(DEVICE).eval()


class CacheTests(unittest.TestCase):
    def test_chunk_logits_match_full_forward_for_both_attention_paths(self):
        for architecture in ("gpt", "modern"):
            for batch in (1, 3):
                for fused in (False, True):
                    with self.subTest(architecture=architecture, batch=batch, fused=fused):
                        model = model_for(architecture)
                        for block in model.transformer.h:
                            block.attn.flash = fused
                        ids = torch.randint(43, (batch, 12), device=DEVICE)
                        expected = model(ids)[0]
                        for chunks in ((3, 1, 4, 4), (1,) * 12):
                            cache, offset, logits = None, 0, []
                            for size in chunks:
                                actual, cache = model.forward_cached(ids[:, offset:offset + size], cache)
                                offset += size
                                logits.append(actual)
                                self.assertEqual(cache[0][0].shape, (batch, 2, offset, 16))
                            torch.testing.assert_close(torch.cat(logits, dim=1), expected,
                                                       rtol=1e-5, atol=1e-6)

    def test_rotary_chunk_uses_prefix_position_offset(self):
        rotary = RotaryEmbedding(8, 16, 10000).to(DEVICE)
        values = torch.randn(2, 3, 12, 8, device=DEVICE)
        expected = rotary(values)[:, :, 5:9]
        actual = rotary(values[:, :, 5:9], position_offset=5)
        torch.testing.assert_close(actual, expected, rtol=0, atol=0)

    def test_greedy_generation_matches_through_window_rollover(self):
        for architecture in ("gpt", "modern"):
            model = model_for(architecture, block_size=8)
            for prefix in (3, 8, 11):
                with self.subTest(architecture=architecture, prefix=prefix):
                    ids = torch.randint(43, (2, prefix), device=DEVICE)
                    uncached = model.generate(ids, 14, temperature=0, use_cache=False)
                    cached = model.generate(ids, 14, temperature=0, use_cache=True)
                    torch.testing.assert_close(cached, uncached, rtol=0, atol=0)

    def test_cache_is_external_and_does_not_retain_training_graph(self):
        for architecture in ("gpt", "modern"):
            model = model_for(architecture)
            keys_before = tuple(model.state_dict())
            ids = torch.randint(43, (2, 6), device=DEVICE)
            logits, cache = model.forward_cached(ids)
            self.assertFalse(logits.requires_grad)
            references = [weakref.ref(t) for pair in cache for t in pair]
            self.assertTrue(all(t.grad_fn is None and not t.requires_grad for pair in cache for t in pair))
            del cache, logits
            gc.collect()
            self.assertTrue(all(ref() is None for ref in references))
            self.assertEqual(tuple(model.state_dict()), keys_before)
            model.train()
            _, loss = model(ids, ids)
            loss.backward()
            self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all()
                                for p in model.parameters()))

    def test_training_mode_and_gradients_survive_sampling(self):
        model = model_for("modern").train()
        ids = torch.randint(43, (2, 6), device=DEVICE)
        model(ids, ids)[1].backward()
        original = [p.grad.clone() for p in model.parameters()]
        model.generate(ids, 3, temperature=0, use_cache=True)
        self.assertTrue(model.training)
        for before, parameter in zip(original, model.parameters()):
            torch.testing.assert_close(before, parameter.grad, rtol=0, atol=0)
        with self.assertRaisesRegex(ValueError, "eval mode"):
            model.forward_cached(ids)

    def test_cache_shape_and_window_errors_are_explicit(self):
        model = model_for("modern", block_size=8)
        ids = torch.randint(43, (2, 8), device=DEVICE)
        _, cache = model.forward_cached(ids[:, :5])
        with self.assertRaisesRegex(ValueError, "context window"):
            model.forward_cached(ids[:, :4], cache)
        with self.assertRaisesRegex(ValueError, "one key/value pair per layer"):
            model.forward_cached(ids[:, :1], cache[:1])
        with self.assertRaisesRegex(ValueError, "cache batch"):
            model.forward_cached(ids[:1, :1], cache)

    def test_last_only_cached_projection_matches_full_projection(self):
        for architecture in ("gpt", "modern"):
            model = model_for(architecture)
            ids = torch.randint(43, (2, 9), device=DEVICE)
            _, cache = model.forward_cached(ids[:, :5])
            full, _ = model.forward_cached(ids[:, 5:], cache)
            last, _ = model.forward_cached(ids[:, 5:], cache, only_last=True)
            torch.testing.assert_close(last, full[:, -1:], rtol=1e-5, atol=1e-6)


if __name__ == "__main__":
    unittest.main()
