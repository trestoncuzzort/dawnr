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


def tiny_model(block_size=12, n_layer=2, n_head=2, n_embd=16, seed=7):
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
    return pg.PlainGPT(config, state), pg.CharTokens(VOCAB)


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
