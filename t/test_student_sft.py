"""t/student_sft.py (2026-10-01): the row encoding. The loss is on the response only (QLoRA,
arXiv:2305.14314 B.3), the response ends with the tokenizer's end token, and a row that does not
fit is dropped, never truncated. A stand-in tokenizer; no model, no GPU."""
from __future__ import annotations

import importlib.util
import hashlib
import json
import subprocess
import sys
import tempfile
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


class InputSnapshot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source.jsonl"
        self.out = self.root / "adapter"
        self.data = ("\n" + json.dumps(ROW) + "\n\n").encode()
        self.source.write_bytes(self.data)

    def freeze(self, **kwargs):
        return student_sft.snapshot_rows(self.source, self.out, **kwargs)

    def test_snapshot_survives_source_deletion_and_can_be_used_to_resume(self):
        rows, receipt = self.freeze(limit=1, max_len=100)
        self.source.unlink()
        frozen = self.out / receipt["file"]
        self.assertEqual(frozen.read_bytes(), self.data)
        self.assertEqual(receipt["sha256"], hashlib.sha256(self.data).hexdigest())
        self.assertEqual(rows, [ROW])
        self.assertEqual(student_sft.snapshot_rows(frozen, self.out, limit=1, max_len=100), (rows, receipt))

    def test_source_replacement_cannot_change_the_record_of_loaded_rows(self):
        rows, receipt = self.freeze()
        self.source.write_text(json.dumps({**ROW, "chosen": "changed"}) + "\n")
        self.assertEqual(rows[0]["chosen"], "ans")
        self.assertEqual(receipt["sha256"], hashlib.sha256(self.data).hexdigest())
        with self.assertRaisesRegex(SystemExit, "frozen training data"):
            self.freeze()
        self.assertEqual((self.out / receipt["file"]).read_bytes(), self.data)

    def test_changed_selection_and_corrupted_snapshot_are_refused(self):
        self.freeze()
        for selection in ({"limit": 1}, {"max_len": 100}):
            with self.subTest(selection=selection), self.assertRaisesRegex(SystemExit, "selection settings"):
                self.freeze(**selection)
        (self.out / "training-rows.jsonl").write_bytes(b"changed")
        with self.assertRaisesRegex(SystemExit, "frozen training data"):
            self.freeze()

    def test_a_legacy_checkpoint_without_data_identity_is_refused(self):
        (self.out / "trainer/checkpoint-10").mkdir(parents=True)
        with self.assertRaisesRegex(SystemExit, "no input snapshot"):
            self.freeze()
        self.assertFalse((self.out / "training-data.json").exists())

    def test_partial_snapshot_and_empty_rows_are_refused(self):
        self.out.mkdir()
        (self.out / "training-rows.jsonl").write_bytes(self.data)
        with self.assertRaisesRegex(SystemExit, "incomplete"):
            self.freeze()
        self.source.write_bytes(b"\n")
        with self.assertRaisesRegex(SystemExit, "empty training data"):
            self.freeze()

    def test_cli_checks_expected_hash_before_importing_model_dependencies(self):
        # -S removes site packages: reaching torch would fail with an ImportError.
        result = subprocess.run([sys.executable, "-S", str(HERE / "student_sft.py"),
                                 "--model", "unused", "--sft", str(self.source),
                                 "--out", str(self.out), "--sft-sha256", "0" * 64],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("differs from --sft-sha256", result.stderr)
        self.assertNotIn("ModuleNotFoundError", result.stderr)
        self.assertFalse(self.out.exists())


class Encoding(unittest.TestCase):
    def test_the_prompt_is_masked_and_the_response_ends_with_the_end_token(self):
        tok = Tok()
        e = student_sft.encode_row(tok, ROW, 100)
        prompt = "<s>S<u>U<a>"
        self.assertEqual("".join(chr(i) for i in e["input_ids"]), prompt + "ans#")
        self.assertEqual(e["labels"][: len(prompt)], [-100] * len(prompt))
        self.assertEqual("".join(chr(i) for i in e["labels"][len(prompt):]), "ans#")
        self.assertEqual(tok.calls, [{"enable_thinking": False}])        # thinking off, asked of the template

    def test_a_conversation_cut_into_pieces_is_trained_on_its_trained_pieces_only(self):
        row = {"pieces": [["<s>tools<u>do it<a>", False], ["call one#", True], ["<t>result<a>", False], ["Done.#", True]]}
        e = student_sft.encode_row(Tok(), row, 100)
        self.assertEqual("".join(chr(i) for i in e["input_ids"]), "<s>tools<u>do it<a>call one#<t>result<a>Done.#")
        self.assertEqual("".join(chr(i) for i in e["labels"] if i != -100), "call one#Done.#")
        self.assertEqual([i for i, label in enumerate(e["labels"]) if label != -100][0], len("<s>tools<u>do it<a>"))
        self.assertIsNone(student_sft.encode_row(Tok(), row, 20))

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


    def test_given_the_windows_token_count_the_micro_batches_add_up_to_the_mean_over_its_tokens(self):
        # transformers' contract under gradient accumulation (loss/loss_utils.py fixed_cross_entropy):
        # sum over this batch's target tokens, divided by the target tokens of the whole window. A
        # loss that returns its own batch mean is NOT divided by the Trainer afterwards, and reads
        # (and backpropagates) as many times too large as there are accumulated batches.
        import torch

        torch.manual_seed(0)
        vocab, width = 11, 5
        embed = torch.nn.Embedding(vocab, width)
        head = torch.nn.Linear(width, vocab, bias=False)

        class Backbone:
            def __call__(self, input_ids, attention_mask):
                return type("Out", (), {"last_hidden_state": embed(input_ids)})()

        class Base:
            model = Backbone()
            lm_head = staticmethod(head)

        rows = [{"input_ids": [1, 2, 3, 4, 5, 6], "labels": [-100, -100, -100, 4, 5, 6]},     # 3 target tokens
                {"input_ids": [7, 8, 9], "labels": [-100, 8, 9]}]                             # 2 target tokens
        window_tokens = 5
        parts = [student_sft.response_loss(Base, student_sft.pad_batch([r], pad_id=0), torch.tensor(window_tokens))
                 for r in rows]
        both = student_sft.pad_batch(rows, pad_id=0)
        mean_over_tokens = student_sft.response_loss(Base, both)                  # no count: the plain mean
        self.assertAlmostEqual(float(sum(parts)), float(mean_over_tokens), places=5)
        # and the old behaviour, a batch mean per micro-batch, would have summed to about twice that
        old = sum(student_sft.response_loss(Base, student_sft.pad_batch([r], pad_id=0)) for r in rows)
        self.assertGreater(float(old), 1.5 * float(mean_over_tokens))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
