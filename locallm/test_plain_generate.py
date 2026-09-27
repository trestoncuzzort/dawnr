"""plain_generate's decoder, checked on a tiny model built in memory.

No checkpoint file and no torch: PlainGPT takes a config and a state dict of
tensor descriptions, so a two-layer, 16-wide model with random weights is built
here in a millisecond and every test runs on any Python 3.10 or newer.

    python3 -m unittest test_plain_generate -v

What is pinned, and why each matters:

  * The two arithmetics. Python 3.12+ decodes through math.sumprod with values
    stored as columns; 3.10 and 3.11 keep sum(map(mul, ...)). On 3.10/3.11 the
    column form must equal the old (time, dimension) double loop to the last
    bit, since the brief for that path is "today's behaviour"; on 3.12+ the two
    arithmetics must agree to rounding and on every greedy choice here.
  * The window. The exact-window mode must be what torch's uncached sampler
    does: every next token predicted from a fresh forward over the last
    block_size tokens. The refill mode must be exactly "reset, re-read the last
    `keep` tokens from position 0, continue", which is what the docs promise.
  * Streaming. generate() is list(iter_generate()), and "".join(stream()) is
    sample(), for the same seed, so the window and the command line cannot drift
    apart from the function the tests check.
"""
from __future__ import annotations

import array
import math
import pathlib
import random
import sys
import unittest
from operator import mul
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import plain_generate as pg  # noqa: E402

VOCAB = list("abcdefghij .\n")


def tensor(shape, rng, scale=0.3):
    numel = 1
    for dim in shape:
        numel *= dim
    flat = array.array("f", [rng.uniform(-scale, scale) for _ in range(numel)])
    return {"shape": tuple(shape), "flat": flat, "offset": 0, "numel": numel}


def tiny_model(block_size=12, n_layer=2, n_head=2, n_embd=16, seed=7,
              quantize=False, quantize_kv=False):
    rng = random.Random(seed)
    V, D = len(VOCAB), n_embd
    state = {"transformer.wte.weight": tensor((V, D), rng, 1.0),
             "transformer.wpe.weight": tensor((block_size, D), rng, 1.0),
             "transformer.ln_f.weight": tensor((D,), rng, 1.0),
             "transformer.ln_f.bias": tensor((D,), rng),
             "lm_head.weight": tensor((V, D), rng, 1.0)}
    for i in range(n_layer):
        p = f"transformer.h.{i}."
        for name, shape in (("ln_1.weight", (D,)), ("ln_1.bias", (D,)),
                            ("ln_2.weight", (D,)), ("ln_2.bias", (D,)),
                            ("attn.c_attn.weight", (3 * D, D)), ("attn.c_attn.bias", (3 * D,)),
                            ("attn.c_proj.weight", (D, D)), ("attn.c_proj.bias", (D,)),
                            ("mlp.c_fc.weight", (4 * D, D)), ("mlp.c_fc.bias", (4 * D,)),
                            ("mlp.c_proj.weight", (D, 4 * D)), ("mlp.c_proj.bias", (D,))):
            state[p + name] = tensor(shape, rng)
    config = {"n_layer": n_layer, "n_head": n_head, "n_embd": D,
              "block_size": block_size, "vocab_size": V}
    return (pg.PlainGPT(config, state, quantize=quantize, quantize_kv=quantize_kv),
           pg.CharTokens(VOCAB))


def old_attend(weights, values):
    """The loop plain_generate used before 2026-09-26, verbatim in effect."""
    norm = 1.0 / sum(weights)
    accumulated = [0.0] * len(values[0])
    for weight, value in zip(weights, values):
        weight *= norm
        for j in range(len(value)):
            accumulated[j] += weight * value[j]
    return accumulated


def plain_arithmetic():
    return mock.patch.multiple(pg, _dot=pg._dot_plain, _attend=pg._attend_plain)


def fresh_logits(model, tokens):
    """What torch's uncached sampler computes: a clean forward over `tokens`."""
    model.reset()
    logits = None
    for t in tokens:
        logits = model.step(t)
    return logits


class TheArithmetic(unittest.TestCase):
    def test_column_attention_is_the_old_loop(self):
        rng = random.Random(3)
        for T, hd in ((1, 4), (7, 8), (50, 16)):
            weights = [math.exp(rng.uniform(-5, 0)) for _ in range(T)]
            values = [[rng.uniform(-2, 2) for _ in range(hd)] for _ in range(T)]
            columns = [list(col) for col in zip(*values)]
            got, want = pg._attend_plain(weights, columns), old_attend(weights, values)
            if sys.version_info < (3, 12):
                # sum() adds floats left to right before 3.12, as the loop did.
                self.assertEqual(got, want, "the 3.10/3.11 path changed arithmetic")
            else:
                for a, b in zip(got, want):
                    self.assertAlmostEqual(a, b, places=12)

    @unittest.skipUnless(hasattr(math, "sumprod"), "math.sumprod is Python 3.12+")
    def test_sumprod_path_agrees_with_the_plain_path(self):
        model, _ = tiny_model()
        ids = [1, 4, 2, 9, 0, 3, 3, 7]
        fast = fresh_logits(model, ids)
        with plain_arithmetic():
            slow = fresh_logits(model, ids)
        for a, b in zip(fast, slow):
            self.assertAlmostEqual(a, b, places=9)
        model.reset()
        fast_ids = model.generate([1, 2], 9, temperature=0)
        model.reset()
        self.assertEqual(fast_ids, _plain_generate(model, [1, 2], 9))
        self.assertEqual(len(fast_ids), 9)

    def test_the_default_matches_the_interpreter(self):
        if hasattr(math, "sumprod"):
            self.assertIs(pg._dot, math.sumprod)
        else:
            self.assertIs(pg._dot, pg._dot_plain)
        self.assertEqual(pg._dot_plain([1.0, 2.0], [3.0, 4.0]), sum(map(mul, [1.0, 2.0], [3.0, 4.0])))


def argmax(logits):
    return max(range(len(logits)), key=logits.__getitem__)


def reference_greedy(model, prompt, n, keep):
    """Greedy decoding written from the documented rule, one fresh forward per token.

    keep=None is torch's uncached sampler: the next token always comes from the
    last block_size tokens. Otherwise the context is cut to its last `keep`
    tokens whenever a new token would not fit, and grows again from there.
    """
    B = model.block_size
    ctx, out = list(prompt[-B:]), []
    for _ in range(n):
        nxt = argmax(fresh_logits(model, ctx))
        out.append(nxt)
        if len(ctx) == B:
            ctx = ctx[len(ctx) - (B - 1 if keep is None else keep):]
        ctx.append(nxt)
    return out


class TheWindow(unittest.TestCase):
    """block_size 8, so 30 new tokens cross the window several times."""

    def setUp(self):
        self.model, _ = tiny_model(block_size=8)
        self.prompt = [1, 5, 2]

    def gen(self, n, **kw):
        self.model.reset()
        return self.model.generate(self.prompt, n, temperature=0, **kw)

    def test_exact_window_is_the_uncached_crop(self):
        got = self.gen(30, exact_window=True)
        # 3 prompt tokens and 29 fed back (the last is never fed): 32 - 8.
        self.assertEqual(self.model.rebuilt, 24)
        self.assertEqual(got, reference_greedy(self.model, self.prompt, 30, None))

    def test_the_refill_is_what_the_docstring_says(self):
        for keep in (None, 1, 3, 6):
            with self.subTest(keep=keep):
                got = self.gen(30, keep=keep)
                want = reference_greedy(self.model, self.prompt, 30,
                                        4 if keep is None else keep)
                self.assertEqual(got, want)

    def test_refills_are_rare_by_default(self):
        self.gen(30)
        # 3 prompt + 29 fed back: full at 8, then a refill of 4 every 4 tokens.
        self.assertEqual(self.model.rebuilt, 6)
        self.gen(30, exact_window=True)
        self.assertEqual(self.model.rebuilt, 24)   # every token past the line

    def test_both_modes_agree_inside_the_window(self):
        self.assertEqual(self.gen(4), self.gen(4, exact_window=True))

    def test_a_long_prompt_is_cut_without_changing_the_answer(self):
        long_prompt = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5, 8, 9, 7]
        model = self.model
        model.reset()
        for t in long_prompt:           # the old way: token by token, exact window
            logits = model.step(t, model.block_size - 1)
        self.assertEqual(model.rebuilt, len(long_prompt) - 8)
        self.assertEqual(logits, fresh_logits(model, long_prompt[-8:]))
        model.reset()
        self.assertEqual(model.generate(long_prompt, 1, temperature=0)[0], argmax(logits))
        self.assertEqual(model.rebuilt, 0, "the cut prompt needed no refill")

    def test_stop_at_window_still_stops(self):
        got = self.gen(30, past_context=False)
        self.assertEqual(len(got), 8 - 3)
        self.assertTrue(self.model.stopped_at_context)

    def test_a_keep_outside_the_window_is_refused(self):
        for bad in (-1, 8, 100):
            with self.assertRaises(ValueError):
                self.gen(3, keep=bad)
        with self.assertRaises(ValueError):
            self.gen(3, exact_window=True, keep=2)
        self.assertEqual(self.model.window_keep(True), 7)
        self.assertEqual(self.model.window_keep(False, 0), 0)


class Streaming(unittest.TestCase):
    def setUp(self):
        self.model, self.tok = tiny_model(block_size=8)

    def test_generate_is_the_iterator_listed(self):
        for kw in ({"temperature": 0}, {"temperature": 0.9, "seed": 4},
                   {"temperature": 1.2, "top_k": 3, "seed": 11, "exact_window": True}):
            with self.subTest(**kw):
                self.model.reset()
                whole = self.model.generate([2, 3], 25, **kw)
                self.model.reset()
                self.assertEqual(list(self.model.iter_generate([2, 3], 25, **kw)), whole)
                self.assertEqual(len(whole), 25)

    def test_the_pieces_join_to_the_sample(self):
        for prompt in ("abc", "", "zzz", "a b.\nc"):
            with self.subTest(prompt=prompt):
                pieces = list(pg.stream(self.model, self.tok, prompt, 20,
                                        temperature=0.8, seed=5))
                self.assertEqual("".join(pieces),
                                 pg.sample(self.model, self.tok, prompt, 20,
                                           temperature=0.8, seed=5))
                self.assertEqual(len(pieces), 21, "the prompt, then one piece per token")

    def test_the_prompt_arrives_before_the_model_reads_it(self):
        pieces = pg.stream(self.model, self.tok, "abc", 5)
        self.assertEqual(next(pieces), "abc")
        self.assertEqual(self.model.history, [], "nothing was read yet")

    def test_bad_arguments_fail_at_the_call(self):
        for kw in ({"temperature": -1}, {"top_k": 0}, {"keep": 99}):
            with self.subTest(**kw), self.assertRaises(ValueError):
                pg.stream(self.model, self.tok, "abc", 5, **kw)
            with self.subTest(**kw), self.assertRaises(ValueError):
                self.model.iter_generate([1], 5, **kw)

    def test_stopping_early_costs_nothing_more(self):
        pieces = pg.stream(self.model, self.tok, "ab", 50, temperature=0)
        got = [next(pieces) for _ in range(4)]
        fed = len(self.model.history)
        pieces.close()
        self.assertEqual(len(got), 4)
        self.assertEqual(fed, 2 + 2, "the prompt and the tokens before the last one shown")

    def test_the_unknown_character_note(self):
        self.assertEqual(pg.unknown_note(self.tok, "abc"), "")
        note = pg.unknown_note(self.tok, "aé—b", what="what you typed")
        self.assertIn("2 of the characters in what you typed", note)
        self.assertIn("'é'", note)
        self.assertTrue(note.endswith("."))
        self.assertIn("starts from the first character", pg.unknown_note(self.tok, "ZZ"))


INCLUDED = HERE.parent / "t/runs/2026-09-17/home-4080/models/model-r4"


class TheCommandLine(unittest.TestCase):
    def test_streamed_output_is_what_sample_returns(self):
        if not (INCLUDED / "ckpt.pt").is_file() or (INCLUDED / "ckpt.pt").stat().st_size < 1000:
            self.skipTest("the included model's weights are not in this checkout")
        import subprocess
        got = subprocess.run([sys.executable, str(HERE / "plain_generate.py"), "--out",
                              str(INCLUDED), "--prompt", "task ", "--tokens", "6",
                              "--temperature", "0"], capture_output=True, text=True,
                             check=True)
        model, tok, _ = pg.load_checkpoint(INCLUDED)
        self.assertEqual(got.stdout, pg.sample(model, tok, "task ", 6, temperature=0) + "\n")


def _plain_generate(model, ids, n):
    with plain_arithmetic():
        return model.generate(ids, n, temperature=0)


class Int8WeightQuantization(unittest.TestCase):
    """--quantize: per-row symmetric int8, off by default.

    Krishnamoorthi 2018 (arXiv:1806.08342) section 2.2's restricted-range
    symmetric quantizer (scale = peak/127, clamp to [-127, 127], zero-point 0)
    and section 2.6's per-channel granularity (one scale per output row).
    """

    def test_an_all_zero_row_gets_scale_one_not_a_division_by_zero(self):
        q, scale = pg._quantize_row([0.0, 0.0, 0.0])
        self.assertEqual(scale, 1.0)
        self.assertEqual(list(q), [0, 0, 0])

    def test_quantized_values_stay_in_the_restricted_signed_range(self):
        rng = random.Random(1)
        for _ in range(20):
            row = [rng.uniform(-9, 9) for _ in range(17)]
            q, scale = pg._quantize_row(row)
            self.assertTrue(all(-127 <= v <= 127 for v in q))
            self.assertGreater(scale, 0.0)

    def test_the_peak_element_lands_on_the_edge_of_the_range(self):
        # eq. 7-8: scale = peak / 127, so the largest-magnitude element
        # quantizes to exactly +-127 (whichever sign the peak carries).
        q, scale = pg._quantize_row([0.3, -1.2, 0.9])
        self.assertEqual(min(q), -127)
        self.assertAlmostEqual(scale, 1.2 / 127.0, places=12)

    def test_dequantizing_recovers_the_row_within_half_a_step(self):
        rng = random.Random(2)
        row = [rng.uniform(-5, 5) for _ in range(40)]
        q, scale = pg._quantize_row(row)
        for original, quantized in zip(row, q):
            self.assertLessEqual(abs(original - quantized * scale), scale / 2 + 1e-9)

    def test_quantize_rows_matches_quantize_row_one_at_a_time(self):
        rng = random.Random(3)
        rows = [[rng.uniform(-4, 4) for _ in range(9)] for _ in range(6)]
        q_rows, scales = pg._quantize_rows(rows)
        self.assertEqual(len(q_rows), len(rows))
        # scales is array('f'): float32 storage, so each readback is that
        # float32's nearest float64, not the float64 _quantize_row computed —
        # they agree to float32 precision, not bit for bit.
        for got_scale, row in zip(scales, rows):
            self.assertAlmostEqual(got_scale, pg._quantize_row(row)[1], places=6)
        for got, row in zip(q_rows, rows):
            self.assertEqual(list(got), list(pg._quantize_row(row)[0]))

    def test_matvec_int8_is_the_dequantized_dot_product(self):
        # The identity the whole design leans on: dot(int8_row, x) * scale IS
        # dot(dequantized_row, x), not an approximation of it.
        rng = random.Random(4)
        rows = [[rng.uniform(-3, 3) for _ in range(11)] for _ in range(5)]
        bias = [rng.uniform(-1, 1) for _ in range(5)]
        x = [rng.uniform(-2, 2) for _ in range(11)]
        q_rows, scales = pg._quantize_rows(rows)
        got = pg._matvec_int8(q_rows, scales, x, bias)
        for i, (q_row, scale, b) in enumerate(zip(q_rows, scales, bias)):
            dequantized = [v * scale for v in q_row]
            want = sum(a * c for a, c in zip(dequantized, x)) + b
            self.assertAlmostEqual(got[i], want, places=5)

    def test_embed_row_dequantizes_and_the_unquantized_case_is_the_same_object(self):
        rows = [array.array("f", [1.0, 2.0, 3.0])]
        self.assertIs(pg._embed_row(rows, None, 0), rows[0])
        q_rows, scales = pg._quantize_rows([[1.0, -2.0, 0.5]])
        got = pg._embed_row(q_rows, scales, 0)
        self.assertEqual(got, [v * scales[0] for v in q_rows[0]])

    def test_the_default_is_unquantized(self):
        model, _ = tiny_model()
        self.assertFalse(model.quantize)
        self.assertFalse(model.quantize_kv)
        self.assertIsNone(model.wte_scale)
        self.assertIsNone(model.wpe_scale)
        self.assertIsNone(model.head_scale)
        for layer in model.layers:
            for key in ("qkv_scale", "attn_out_scale", "fc_scale", "mlp_out_scale"):
                self.assertIsNone(layer[key])

    def test_a_quantized_model_runs_and_stays_finite(self):
        model, _ = tiny_model(quantize=True)
        model.reset()
        out = model.generate([1, 2, 3], 40, temperature=0)
        self.assertEqual(len(out), 40)
        self.assertTrue(all(0 <= t < model.vocab_size for t in out))

    def test_two_quantized_builds_of_the_same_weights_agree_exactly(self):
        model_a, _ = tiny_model(quantize=True, seed=9)
        model_b, _ = tiny_model(quantize=True, seed=9)
        self.assertEqual(model_a.generate([1, 2], 25, temperature=0),
                         model_b.generate([1, 2], 25, temperature=0))

    def test_quantized_weights_are_about_a_quarter_the_bytes(self):
        plain, _ = tiny_model(quantize=False, seed=5)
        quantized, _ = tiny_model(quantize=True, seed=5)
        ratio = quantized.weight_bytes() / plain.weight_bytes()
        self.assertLess(ratio, 0.40, "int8 rows plus a float32 scale per row "
                                     "should still land well under half of float32")
        self.assertGreater(ratio, 0.20, "a quarter is the floor; scale overhead adds a bit")

    def test_weight_bytes_of_an_unquantized_model_is_plain_float32_storage(self):
        model, _ = tiny_model()
        expected = sum(len(row) * row.itemsize
                       for rows, _ in model._weight_slots() for row in rows)
        self.assertEqual(model.weight_bytes(), expected)


class Int8KVCache(unittest.TestCase):
    """--quantize-kv: the same per-row scheme, one scale per cached vector
    (see plain_generate.py's _attend_int8_plain/_sumprod docstring comment)."""

    def test_attend_int8_plain_matches_a_naive_reference(self):
        rng = random.Random(11)
        T, hd = 6, 5
        weights = [math.exp(rng.uniform(-4, 0)) for _ in range(T)]
        vectors = [[rng.uniform(-2, 2) for _ in range(hd)] for _ in range(T)]
        q_vectors, value_scales = zip(*(pg._quantize_row(v) for v in vectors))
        columns = [array.array("b", [q[j] for q in q_vectors]) for j in range(hd)]
        got = pg._attend_int8_plain(weights, columns, list(value_scales))
        norm = 1.0 / sum(weights)
        want = [sum(w * norm * (qv[j] * s) for w, qv, s in zip(weights, q_vectors, value_scales))
               for j in range(hd)]
        for a, b in zip(got, want):
            self.assertAlmostEqual(a, b, places=9)

    @unittest.skipUnless(hasattr(math, "sumprod"), "math.sumprod is Python 3.12+")
    def test_attend_int8_sumprod_agrees_with_attend_int8_plain(self):
        rng = random.Random(12)
        T, hd = 7, 6
        weights = [math.exp(rng.uniform(-4, 0)) for _ in range(T)]
        vectors = [[rng.uniform(-2, 2) for _ in range(hd)] for _ in range(T)]
        q_vectors, value_scales = zip(*(pg._quantize_row(v) for v in vectors))
        columns = [array.array("b", [q[j] for q in q_vectors]) for j in range(hd)]
        slow = pg._attend_int8_plain(weights, columns, list(value_scales))
        fast = pg._attend_int8_sumprod(weights, columns, list(value_scales))
        for a, b in zip(slow, fast):
            self.assertAlmostEqual(a, b, places=9)

    def test_a_quantized_cache_runs_across_a_window_refill(self):
        model, _ = tiny_model(block_size=8, quantize_kv=True)
        model.reset()
        got = model.generate([1, 5, 2], 30, temperature=0)
        self.assertEqual(len(got), 30)
        self.assertGreater(model.rebuilt, 0, "30 tokens at block_size 8 must refill")
        self.assertTrue(all(0 <= t < model.vocab_size for t in got))

    def test_two_runs_of_a_quantized_cache_agree_exactly(self):
        model_a, _ = tiny_model(quantize_kv=True, seed=13)
        model_b, _ = tiny_model(quantize_kv=True, seed=13)
        self.assertEqual(model_a.generate([2, 3], 20, temperature=0.8, seed=1),
                         model_b.generate([2, 3], 20, temperature=0.8, seed=1))

    def test_both_quantize_flags_together(self):
        model, _ = tiny_model(quantize=True, quantize_kv=True)
        got = model.generate([1, 1, 2], 15, temperature=0)
        self.assertEqual(len(got), 15)


class IncludedModelInt8(unittest.TestCase):
    """The shipped round-4 checkpoint, quantized both ways.

    The full 200-token speed/memory/agreement measurement this track was asked
    for is bench_int8.py, run against PREDICT-int8-quant-2026-09-27.md's
    predictions (bench-int8-results-2026-09-27.json has the numbers); this
    class is the fast regression that both paths still load and generate
    correctly.
    """

    def setUp(self):
        if not (INCLUDED / "ckpt.pt").is_file() or (INCLUDED / "ckpt.pt").stat().st_size < 1000:
            self.skipTest("the included model's weights are not in this checkout")

    def test_quantize_flags_load_and_generate_on_the_real_checkpoint(self):
        model, tok, _ = pg.load_checkpoint(INCLUDED, quantize=True, quantize_kv=True)
        self.assertTrue(model.quantize and model.quantize_kv)
        text = pg.sample(model, tok, "task ", 20, temperature=0)
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), len("task "))

    def test_quantized_weights_measure_close_to_a_quarter(self):
        plain, _, _ = pg.load_checkpoint(INCLUDED)
        quantized, _, _ = pg.load_checkpoint(INCLUDED, quantize=True)
        ratio = quantized.weight_bytes() / plain.weight_bytes()
        self.assertLess(ratio, 0.30)
        self.assertGreater(ratio, 0.24)

    def test_cli_quantize_flags_run(self):
        import subprocess
        got = subprocess.run([sys.executable, str(HERE / "plain_generate.py"), "--out",
                              str(INCLUDED), "--prompt", "task ", "--tokens", "6",
                              "--temperature", "0", "--quantize", "--quantize-kv"],
                             capture_output=True, text=True, check=True)
        self.assertIn("weights held as", got.stderr)
        self.assertIn("int8 weights", got.stderr)
        self.assertIn("int8 KV cache", got.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
