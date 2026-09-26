"""The stop rule and the batched sampler of r12 (t/RUN-NEXT-locallm-r12.md, C and D).

Three claims, each with the test that would falsify it:
  1. generate(stop=None) is bitwise the loop it replaced, for both cores, greedy and
     sampled, cached and uncached, through window rollover: a frozen copy of the old
     loop lives in this file and the two are compared token for token.
  2. With a stop, every row is bitwise the unstopped row cut at the step the loop
     ended, and the loop ends as soon as every row has stopped.
  3. sample_many at k=1 is bitwise generate(use_cache=True); its per-token
     log-probabilities equal a teacher-forced forward; a text stop through
     checkpoint.sample and sample_batch is exact, and the byte-level BPE limit is
     the one the docstring names (a U+FFFD tail), nothing more.
Needs torch: run on the lab, CPU.
"""
import math
import os
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import torch  # noqa: E402
from torch.nn import functional as F  # noqa: E402

import checkpoint  # noqa: E402
from data import BPETokenizer, CharTokenizer  # noqa: E402
from model import GPT, GPTConfig  # noqa: E402

DEVICE = os.environ.get("LOCALLM_TEST_DEVICE", "cpu")


def model_for(architecture="gpt", block_size=16, vocab=43, seed=173):
    torch.manual_seed(seed)
    return GPT(GPTConfig(vocab_size=vocab, block_size=block_size, n_layer=2,
                         n_head=2, n_embd=32, architecture=architecture)).to(DEVICE).eval()


@torch.no_grad()
def legacy_generate(model, idx, max_new_tokens, temperature=1.0, top_k=None, *, use_cache=False):
    """model.generate as committed at 78de5547, kept verbatim so the refactor is
    measured against the code it replaced rather than against itself."""
    model.eval()
    cache = None
    for _ in range(max_new_tokens):
        if use_cache:
            if cache is None or cache[0][0].size(-2) == model.config.block_size:
                logits, cache = model.forward_cached(idx[:, -model.config.block_size:], only_last=True)
            else:
                logits, cache = model.forward_cached(idx[:, -1:], cache, only_last=True)
        else:
            logits, _ = model(idx[:, -model.config.block_size:], only_last=True)
        logits = logits[:, -1, :]
        if temperature == 0:
            idx_next = logits.argmax(dim=-1, keepdim=True)
        else:
            logits = logits / temperature
            if top_k is not None:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits = logits.masked_fill(logits < v[:, [-1]], -float("Inf"))
            idx_next = torch.multinomial(F.softmax(logits, dim=-1), num_samples=1)
        idx = torch.cat((idx, idx_next), dim=1)
    return idx


class GenerateUnchangedTests(unittest.TestCase):
    def test_no_stop_is_bitwise_the_old_loop(self):
        for architecture in ("gpt", "modern"):
            model = model_for(architecture, block_size=8)
            for prefix in (3, 8, 11):
                ids = torch.randint(43, (2, prefix), device=DEVICE)
                for use_cache in (False, True):
                    for temperature, top_k in ((0, None), (0.8, 5), (1.0, None)):
                        with self.subTest(architecture=architecture, prefix=prefix, cache=use_cache,
                                          temperature=temperature):
                            torch.manual_seed(7)
                            old = legacy_generate(model, ids, 14, temperature, top_k, use_cache=use_cache)
                            torch.manual_seed(7)
                            new = model.generate(ids, 14, temperature, top_k, use_cache=use_cache)
                            torch.testing.assert_close(new, old, rtol=0, atol=0)

    def test_a_stop_that_never_fires_changes_nothing(self):
        model = model_for()
        ids = torch.randint(43, (3, 5), device=DEVICE)
        torch.manual_seed(3)
        plain = model.generate(ids, 10, 0.9, 6, use_cache=True)
        torch.manual_seed(3)
        stopped = model.generate(ids, 10, 0.9, 6, use_cache=True, stop=lambda row, new: False)
        torch.testing.assert_close(stopped, plain, rtol=0, atol=0)

    def test_a_zero_budget_returns_the_prompts(self):
        model = model_for()
        ids = torch.randint(43, (2, 4), device=DEVICE)
        torch.testing.assert_close(model.generate(ids, 0, stop=lambda row, new: True), ids, rtol=0, atol=0)

    def test_training_mode_is_restored_after_a_stop(self):
        model = model_for().train()
        ids = torch.randint(43, (1, 4), device=DEVICE)
        model.generate(ids, 3, 0, stop=lambda row, new: True)
        self.assertTrue(model.training)


class StopTests(unittest.TestCase):
    def test_each_row_is_the_unstopped_row_cut_where_the_loop_ended(self):
        """Rows stay in the batch, so a stopped row keeps consuming random numbers exactly
        as it would have: at any temperature the batch is a prefix of the unstopped batch."""
        for use_cache in (False, True):
            for temperature in (0, 0.7):
                model = model_for(block_size=12)
                ids = torch.randint(43, (3, 4), device=DEVICE)
                torch.manual_seed(11)
                full = model.generate(ids, 10, temperature, 4, use_cache=use_cache)
                stop_after = {0: 2, 1: 5, 2: 3}                   # tokens, per row
                asked = []

                def stop(row, new):
                    asked.append((row, len(new)))
                    return len(new) >= stop_after[row]
                torch.manual_seed(11)
                cut = model.generate(ids, 10, temperature, 4, use_cache=use_cache, stop=stop)
                with self.subTest(cache=use_cache, temperature=temperature):
                    self.assertEqual(cut.size(1), 4 + max(stop_after.values()))
                    torch.testing.assert_close(cut, full[:, :cut.size(1)], rtol=0, atol=0)
                    # a stopped row is not asked again
                    self.assertEqual([n for r, n in asked if r == 0], [1, 2])
                    self.assertEqual([n for r, n in asked if r == 1], [1, 2, 3, 4, 5])

    def test_the_loop_ends_when_every_row_has_stopped(self):
        model = model_for()
        calls = []
        real = model.forward_cached

        def counted(*args, **kwargs):
            calls.append(1)
            return real(*args, **kwargs)
        model.forward_cached = counted
        ids = torch.randint(43, (2, 3), device=DEVICE)
        out = model.generate(ids, 50, 0, use_cache=True, stop=lambda row, new: len(new) >= 4)
        self.assertEqual(out.size(1), 7)
        self.assertEqual(len(calls), 4)

    def test_a_stop_works_through_window_rollover(self):
        model = model_for(block_size=6)
        ids = torch.randint(43, (1, 4), device=DEVICE)
        full = model.generate(ids, 12, 0, use_cache=True)
        cut = model.generate(ids, 12, 0, use_cache=True, stop=lambda row, new: len(new) >= 9)
        self.assertEqual(cut.size(1), 13)
        torch.testing.assert_close(cut, full[:, :13], rtol=0, atol=0)


class SampleManyTests(unittest.TestCase):
    def test_k1_is_bitwise_cached_generate(self):
        for architecture in ("gpt", "modern"):
            for temperature, top_k in ((0, None), (0.8, 5)):
                model = model_for(architecture, block_size=8)
                ids = torch.randint(43, (1, 5), device=DEVICE)
                g1 = torch.Generator(device=DEVICE).manual_seed(5)
                g2 = torch.Generator(device=DEVICE).manual_seed(5)
                ref = model.generate(ids, 12, temperature, top_k, use_cache=True, generator=g1)
                rows = model.sample_many(ids[0], 1, 12, temperature=temperature, top_k=top_k, generator=g2)
                with self.subTest(architecture=architecture, temperature=temperature):
                    self.assertEqual(rows[0].tokens, ref[0, 5:].tolist())
                    self.assertFalse(rows[0].stopped)

    def test_greedy_rows_are_identical_and_stops_give_greedy_prefixes(self):
        model = model_for()
        ids = torch.randint(43, (1, 4), device=DEVICE)
        ref = model.generate(ids, 8, 0, use_cache=True)[0, 4:].tolist()
        rows = model.sample_many(ids[0], 3, 8, temperature=0, top_k=None,
                                 stop=lambda row, new: len(new) >= row + 2)
        for row, sampled in enumerate(rows):
            self.assertEqual(sampled.tokens, ref[:row + 2])
            self.assertTrue(sampled.stopped)
            self.assertEqual(len(sampled.logprobs), row + 2)

    def test_logprobs_match_a_teacher_forced_forward(self):
        model = model_for(block_size=32)
        ids = torch.randint(43, (1, 5), device=DEVICE)
        g = torch.Generator(device=DEVICE).manual_seed(9)
        rows = model.sample_many(ids[0], 4, 10, temperature=0.9, top_k=4, generator=g)
        for sampled in rows:
            seq = torch.tensor([ids[0].tolist() + sampled.tokens], device=DEVICE)
            logits, _ = model(seq)
            logp = F.log_softmax(logits[0, 4:-1].float(), dim=-1)
            expected = logp.gather(1, seq[0, 5:, None])[:, 0].tolist()
            self.assertEqual(len(expected), len(sampled.logprobs))
            for a, b in zip(expected, sampled.logprobs):
                self.assertAlmostEqual(a, b, delta=1e-4)
            # every sampled token was inside the top-4 of the teacher-forced distribution
            top = logits[0, 4:-1].topk(4, dim=-1).indices
            for pos, token in enumerate(sampled.tokens):
                self.assertIn(token, top[pos].tolist())

    def test_rollover_and_departures(self):
        model = model_for(block_size=6)
        ids = torch.randint(43, (1, 4), device=DEVICE)
        ref = model.generate(ids, 14, 0, use_cache=True)[0, 4:].tolist()
        rows = model.sample_many(ids[0], 3, 14, temperature=0, top_k=None,
                                 stop=lambda row, new: len(new) >= (3, 9, 14)[row])
        self.assertEqual([len(r.tokens) for r in rows], [3, 9, 14])
        for r, n in zip(rows, (3, 9, 14)):
            self.assertEqual(r.tokens, ref[:n])

    def test_validation_and_training_mode(self):
        model = model_for().train()
        ids = torch.randint(43, (1, 4), device=DEVICE)
        with self.assertRaises(ValueError):
            model.sample_many(ids, 2, 3, temperature=0.5, top_k=None)        # 2-D prompt
        with self.assertRaises(ValueError):
            model.sample_many(ids[0], 0, 3, temperature=0.5, top_k=None)
        with self.assertRaises(ValueError):
            model.sample_many(ids[0], 2, 3, temperature=-1, top_k=None)
        rows = model.sample_many(ids[0], 2, 3, temperature=0.5, top_k=None)
        self.assertEqual(len(rows), 2)
        self.assertTrue(model.training)


class TextStopTests(unittest.TestCase):
    """The stop as sample() and sample_batch() apply it, over real tokenizers."""

    def setUp(self):
        self.chars = CharTokenizer(sorted(set("abcdefghijklmnopqrstuvwxyz \n():=_{};0123456789")))
        self.model = model_for(vocab=self.chars.vocab_size, block_size=24)

    def test_char_tokenizer_text_stop_is_exact(self):
        prompt = "task f(x"
        full = checkpoint.sample(self.model, self.chars, prompt, tokens=30, temperature=0, top_k=None,
                                 use_cache=True)
        n = 12
        stopped = checkpoint.sample(self.model, self.chars, prompt, tokens=30, temperature=0, top_k=None,
                                    use_cache=True, stop=lambda text: n if len(text) >= n + 1 else None)
        self.assertEqual(len(stopped), n + 1)
        self.assertEqual(stopped, full[:n + 1])

    def test_sample_batch_reports_reply_statistics(self):
        prompt = "task f(x"
        g = torch.Generator(device=DEVICE).manual_seed(2)
        rows = checkpoint.sample_batch(self.model, self.chars, prompt, 3, tokens=20, temperature=0.9, top_k=5,
                                       stop=lambda text: 12 if len(text) >= 14 else None, generator=g)
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertTrue(row["stopped"])
            self.assertEqual(row["reply_tokens"], 12 - len(prompt))     # one token per character
            self.assertEqual(row["new_tokens"], 14 - len(prompt))
            self.assertAlmostEqual(row["mean_logprob"], row["logprob_sum"] / row["reply_tokens"])
            self.assertLessEqual(row["mean_logprob"], 0)
            self.assertTrue(row["text"].startswith(prompt))

    def test_reply_token_count_finds_the_prefix_inside_the_cut(self):
        ids = self.chars.encode("ab")
        new = self.chars.encode("cdefgh")
        for cut in range(2, 9):
            self.assertEqual(checkpoint.reply_token_count(self.chars, ids, new, cut), cut - 2)

    def test_byte_level_bpe_stop_is_token_exact(self):
        try:
            import tokenizers  # noqa: F401
        except ImportError:
            self.skipTest("tokenizers not installed")
        text = ("task f(x: int) returns (r: int)\n  ensures r == x\n{\n  r := x;\n}\n\n"
                "Problem: add one\nSignature: g(int) -> int\nt 1\ntask g(x: int) returns (r: int)\n"
                "{\n  r := x + 1;\n}\nü ö ä 你好\n") * 3
        tok = BPETokenizer.from_text(text, vocab_size=300)
        model = model_for(vocab=tok.vocab_size, block_size=48)
        prompt = "task f("
        ids = tok.encode(prompt)
        idx = torch.tensor([ids], device=DEVICE)
        full = model.generate(idx, 40, 0, use_cache=True)[0].tolist()
        for n in range(1, 40, 3):
            with self.subTest(n=n):
                stop = lambda row, new, n=n: len(new) >= n
                cut = model.generate(idx, 40, 0, use_cache=True, stop=stop)[0].tolist()
                self.assertEqual(cut, full[:len(ids) + n])
                stopped_text, full_text = tok.decode(cut), tok.decode(full)
                if stopped_text.endswith("�"):
                    self.assertTrue(full_text.startswith(stopped_text.rstrip("�")))
                else:
                    self.assertTrue(full_text.startswith(stopped_text))


class RealCheckpointTests(unittest.TestCase):
    """On the r9 checkpoint (set T_R12_CHECKPOINT to its directory), cached greedy
    decoding with the reply-boundary stop extracts the same reply as the unstopped
    run, for a few prompts. The boundary is the one t/loop_locallm.py cuts at."""

    def test_stopped_reply_equals_unstopped_reply(self):
        where = os.environ.get("T_R12_CHECKPOINT")
        if not where:
            self.skipTest("T_R12_CHECKPOINT not set")
        import re
        boundary = re.compile(r"\n\s*\n(?=Problem: |Signature: |t \d)")
        model, tok, _ = checkpoint.load_checkpoint(where, device=DEVICE)
        heads = ["Problem: Write a function to find the shared elements from the given two lists.\n"
                 "Signature: similar_elements(seq<int>, seq<int>) -> seq<int>\n",
                 "Problem: Write a function to find the n-th power of individual elements in a list.\n"
                 "Signature: nth_nums(seq<int>, int) -> seq<int>\n"]
        budget = int(os.environ.get("T_R12_TOKENS", "600"))

        def reply(head, text):
            body = text[len(head):] if text.startswith(head) else text
            return boundary.split(body, maxsplit=1)[0]

        def cut(head):
            def stop(text):
                body_start = len(head) if text.startswith(head) else 0
                m = boundary.search(text, body_start)
                return m.start() if m else None
            return stop
        for head in heads:
            full = checkpoint.sample(model, tok, head, tokens=budget, temperature=0, top_k=None, use_cache=True)
            stopped = checkpoint.sample(model, tok, head, tokens=budget, temperature=0, top_k=None,
                                        use_cache=True, stop=cut(head))
            with self.subTest(head=head[:40]):
                self.assertEqual(reply(head, stopped), reply(head, full))
                self.assertLessEqual(len(tok.encode(stopped)), len(tok.encode(full)))
                rows = checkpoint.sample_batch(model, tok, head, 3, tokens=budget, temperature=0, top_k=None,
                                               stop=cut(head))
                self.assertEqual(len({r["text"] for r in rows}), 1)
                self.assertEqual(reply(head, rows[0]["text"]), reply(head, full))
                self.assertTrue(math.isfinite(rows[0]["mean_logprob"]))


if __name__ == "__main__":
    unittest.main()
