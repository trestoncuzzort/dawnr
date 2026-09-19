import unittest

import torch
from torch.nn import functional as F

from completion_batch import encode_example, encode_segments, collate


class Bytes:
    def encode(self, text):
        return list(text.encode())

    def decode(self, ids):
        return bytes(ids).decode()


class CompletionBatchTests(unittest.TestCase):
    def test_treatments_have_identical_inputs_and_answer_targets(self):
        parts = [("state=3\n", "execution"), ("answer=4\n", "answer")]
        baseline = encode_segments(Bytes(), "x=2\n", parts, block_size=64,
                                   supervise_execution=False)
        treated = encode_segments(Bytes(), "x=2\n", parts, block_size=64,
                                  supervise_execution=True)
        self.assertEqual(baseline["inputs"], treated["inputs"])
        for b, t in zip(baseline["targets"], treated["targets"]):
            if b != -1:
                self.assertEqual(b, t)
        self.assertEqual(Bytes().decode([t for t in baseline["targets"] if t != -1]),
                         "answer=4\n")
        self.assertEqual(Bytes().decode([t for t in treated["targets"] if t != -1]),
                         "state=3\nanswer=4\n")

    def test_shift_mask_and_unicode_roundtrip(self):
        example = encode_example(Bytes(), "input: α\nanswer:", " β\n", block_size=64)
        inputs, targets, segments = collate([example])
        self.assertEqual(Bytes().decode(targets[targets != -1].tolist()), " β\n")
        first = example["prompt_tokens"] - 1
        self.assertEqual(inputs[0, first].item(), ord(":"))
        self.assertEqual(targets[0, first].item(), ord(" "))
        self.assertTrue((segments == 0).all())

    def test_padding_and_prompt_have_zero_loss_gradient(self):
        examples = [encode_example(Bytes(), p, c, block_size=64)
                    for p, c in [("long prompt:", "yes"), ("q:", "n")]]
        _, targets, segments = collate(examples)
        logits = torch.randn(*targets.shape, 256, requires_grad=True)
        F.cross_entropy(logits.flatten(0, 1), targets.flatten(), ignore_index=-1).backward()
        self.assertEqual(logits.grad[targets == -1].abs().sum().item(), 0)
        self.assertGreater(logits.grad[targets != -1].abs().sum().item(), 0)
        self.assertTrue((targets[segments == -1] == -1).all())

    def test_refuses_truncation(self):
        with self.assertRaises(ValueError):
            encode_example(Bytes(), "prompt", "answer", block_size=4)


if __name__ == "__main__":
    unittest.main()
