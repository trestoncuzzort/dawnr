"""dawnr_interp.activations: the residual-stream hook and the held-out boundary it
must respect. What must hold: the hook captures exactly the tensor a manual replay
of model.py's own forward pass produces at the chosen layer (not some other layer,
not the pre-block input); a document longer than the model's context window is
walked in full, one position exactly once; and caching only ever reads
data.group_split's training half, never its validation half, which is what keeps a
dictionary trained through this module off the same held-out text training itself
withholds. Needs torch; CPU only, seconds.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import torch  # noqa: E402

import data  # noqa: E402
from model import GPT, GPTConfig  # noqa: E402

from dawnr_interp.activations import cache_residual_stream, training_split_documents  # noqa: E402


def tiny_model(**overrides):
    tok = data.CharTokenizer.from_text("abcdefghijklmnopqrstuvwxyz \n.,:;(){}")
    values = dict(vocab_size=tok.vocab_size, block_size=8, n_layer=3, n_head=2, n_embd=8, dropout=0.0)
    values.update(overrides)
    torch.manual_seed(7)
    model = GPT(GPTConfig(**values)).eval()
    return model, tok


class ResidualHookTest(unittest.TestCase):
    def test_matches_a_manual_replay_of_the_chosen_block(self):
        model, tok = tiny_model()
        doc = "hello"                       # 5 chars, under block_size 8: one chunk
        layer = 1
        cached = cache_residual_stream(model, tok, [doc], layer)

        ids = tok.encode(doc)
        with torch.no_grad():
            idx = torch.tensor([ids], dtype=torch.long)
            x = model.transformer.wte(idx)
            if "wpe" in model.transformer:
                x = x + model.transformer.wpe(torch.arange(len(ids)))
            x = model.transformer.drop(x)
            for i, block in enumerate(model.transformer.h):
                x = block(x)
                if i == layer:
                    break
            expected = x[0]

        self.assertEqual(len(cached), len(ids))
        torch.testing.assert_close(cached.activations, expected, atol=1e-5, rtol=1e-4)

    def test_captures_a_different_tensor_at_a_different_layer(self):
        model, tok = tiny_model()
        doc = "hello world"
        early = cache_residual_stream(model, tok, [doc], 0)
        late = cache_residual_stream(model, tok, [doc], 2)
        self.assertFalse(torch.allclose(early.activations, late.activations))

    def test_rejects_a_layer_outside_the_model(self):
        model, tok = tiny_model()
        with self.assertRaises(ValueError):
            cache_residual_stream(model, tok, ["hi"], -1)
        with self.assertRaises(ValueError):
            cache_residual_stream(model, tok, ["hi"], model.config.n_layer)

    def test_a_document_longer_than_block_size_is_walked_in_full(self):
        model, tok = tiny_model(block_size=4)
        doc = "the quick brown fox"        # far longer than block_size 4
        cached = cache_residual_stream(model, tok, [doc], 0)
        ids = tok.encode(doc)
        self.assertEqual(len(cached), len(ids))
        self.assertEqual(cached.position, list(range(len(ids))))
        self.assertEqual(cached.token_id, ids)
        self.assertTrue(all(d == 0 for d in cached.doc_index))

    def test_multiple_documents_are_indexed_separately(self):
        model, tok = tiny_model()
        cached = cache_residual_stream(model, tok, ["ab", "cde"], 0)
        self.assertEqual(cached.doc_index, [0, 0, 1, 1, 1])
        self.assertEqual(cached.position, [0, 1, 0, 1, 2])

    def test_empty_documents_are_skipped_without_error(self):
        model, tok = tiny_model()
        cached = cache_residual_stream(model, tok, ["", "ok", ""], 0)
        # doc_index keeps each row's ORIGINAL position in the list passed in, so a
        # caller can always index back into `documents` -- an empty entry is
        # skipped, not silently renumbered into a gap-free 0, 1, 2, ...
        self.assertEqual(cached.doc_index, [1, 1])

    def test_max_documents_caps_how_much_is_read(self):
        model, tok = tiny_model()
        cached = cache_residual_stream(model, tok, ["ab", "cd", "ef"], 0, max_documents=2)
        self.assertEqual(set(cached.doc_index), {0, 1})

    def test_context_wraps_the_activating_character(self):
        model, tok = tiny_model()
        cached = cache_residual_stream(model, tok, ["hello"], 0, context_chars=4)
        # position 2 is 'l' in "hello"
        i = cached.position.index(2)
        self.assertIn("<<l>>", cached.contexts[i])


class TrainingSplitDocumentsTest(unittest.TestCase):
    CORPUS = "\n\n".join(f"task DOC{i}(x: int) returns (y: int)\n  ensures y == x\n{{\n  y := x;\n}}"
                         for i in range(20))

    def test_matches_group_split_exactly(self):
        got = training_split_documents(self.CORPUS, val_frac=0.3, seed=5)
        train_text, _val_text = data.group_split(self.CORPUS, val_frac=0.3, seed=5)
        self.assertEqual(got, data.documents(train_text))

    def test_no_validation_document_survives_into_training(self):
        train_text, val_text = data.group_split(self.CORPUS, val_frac=0.3, seed=5)
        val_docs = set(data.documents(val_text))
        self.assertTrue(val_docs, "this split must actually hold something out for the test to mean anything")
        got = training_split_documents(self.CORPUS, val_frac=0.3, seed=5)
        self.assertFalse(val_docs & set(got))

    def test_by_hash_is_honoured(self):
        got_order = training_split_documents(self.CORPUS, val_frac=0.3, seed=5, by="order")
        got_hash = training_split_documents(self.CORPUS, val_frac=0.3, seed=5, by="hash")
        # different split rules need not agree on membership; this corpus is
        # constructed so they do not, which is what makes the by= plumbing tested.
        self.assertNotEqual(set(got_order), set(got_hash))


if __name__ == "__main__":
    unittest.main()
