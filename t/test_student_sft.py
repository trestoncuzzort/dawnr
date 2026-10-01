"""t/student_sft.py (2026-10-01): the row encoding. The loss is on the response only (QLoRA,
arXiv:2305.14314 B.3), the response ends with the tokenizer's end token, and a row that does not
fit is dropped, never truncated. A stand-in tokenizer; no model, no GPU."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import student_sft  # noqa: E402


class Tok:
    """One token per character; the template wraps the messages and opens the assistant turn."""
    eos_token = "#"

    def __init__(self):
        self.calls = []

    def apply_chat_template(self, messages, tokenize, add_generation_prompt, **kwargs):
        self.calls.append(kwargs)
        return "".join(f"<{m['role'][0]}>{m['content']}" for m in messages) + "<a>"

    def __call__(self, text, add_special_tokens):
        assert add_special_tokens is False
        return {"input_ids": [ord(c) for c in text]}


ROW = {"prompt": [{"role": "system", "content": "S"}, {"role": "user", "content": "U"}], "chosen": "ans"}


class Encoding(unittest.TestCase):
    def test_the_prompt_is_masked_and_the_response_ends_with_the_end_token(self):
        tok = Tok()
        e = student_sft.encode_row(tok, ROW, 100)
        prompt = "<s>S<u>U<a>"
        self.assertEqual("".join(chr(i) for i in e["input_ids"]), prompt + "ans#")
        self.assertEqual(e["labels"][: len(prompt)], [-100] * len(prompt))
        self.assertEqual("".join(chr(i) for i in e["labels"][len(prompt):]), "ans#")
        self.assertEqual(tok.calls, [{"enable_thinking": False}])        # thinking off, asked of the template

    def test_a_row_that_does_not_fit_is_dropped_not_truncated(self):
        self.assertIsNone(student_sft.encode_row(Tok(), ROW, 14))        # prompt 11 + answer 4 = 15
        self.assertIsNotNone(student_sft.encode_row(Tok(), ROW, 15))

    @unittest.skipUnless(importlib.util.find_spec("torch"), "padding builds tensors; no torch on this machine")
    def test_padding_masks_the_pad_positions(self):
        a = {"input_ids": [1, 2, 3], "labels": [-100, 2, 3]}
        b = {"input_ids": [4], "labels": [4]}
        batch = student_sft.pad_batch([a, b], pad_id=0)
        self.assertEqual(batch["input_ids"].tolist(), [[1, 2, 3], [4, 0, 0]])
        self.assertEqual(batch["labels"].tolist(), [[-100, 2, 3], [4, -100, -100]])
        self.assertEqual(batch["attention_mask"].tolist(), [[1, 1, 1], [1, 0, 0]])


@unittest.skipUnless(importlib.util.find_spec("torch"), "the loss is a tensor computation; no torch on this machine")
class ResponseLoss(unittest.TestCase):
    def test_the_head_on_response_positions_only_equals_the_full_shifted_cross_entropy(self):
        import torch

        torch.manual_seed(0)
        vocab, width = 11, 5
        embed = torch.nn.Embedding(vocab, width)
        head = torch.nn.Linear(width, vocab, bias=False)
        seen = {}

        class Backbone:
            def __call__(self, input_ids, attention_mask):
                return type("Out", (), {"last_hidden_state": embed(input_ids)})()

        class Base:
            model = Backbone()

            @staticmethod
            def lm_head(h):
                seen["rows"] = h.shape[0]                 # how many positions reached the output layer
                return head(h)

        batch = student_sft.pad_batch(
            [{"input_ids": [1, 2, 3, 4, 5, 6], "labels": [-100, -100, -100, 4, 5, 6]},
             {"input_ids": [7, 8, 9], "labels": [-100, 8, 9]}], pad_id=0)
        loss = student_sft.response_loss(Base, batch)
        logits = head(embed(batch["input_ids"]))
        full = torch.nn.functional.cross_entropy(logits[:, :-1].reshape(-1, vocab), batch["labels"][:, 1:].reshape(-1),
                                                 ignore_index=-100)
        self.assertAlmostEqual(float(loss), float(full), places=5)
        self.assertEqual(seen["rows"], 5)                 # five response tokens, not 2 x 6 positions


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
