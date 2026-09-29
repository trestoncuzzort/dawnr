"""chat_train drops a conversation longer than the model's context by name and
records it (2026-09-29, the r12 corpus through the pipeline: one 2,109-token
conversation against a 2,048-token context aborted the whole mid stage). A cut
conversation is never trained (ConversationBatches' rule stands); the whole
conversation is left out, named in run.json identities["dropped_over_block"],
and the run refuses only when nothing trainable remains. CPU, seconds."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import torch  # noqa: E402

import chat  # noqa: E402
import chat_data  # noqa: E402
import chat_train  # noqa: E402
import data  # noqa: E402
from model import GPT, GPTConfig  # noqa: E402
from test_dawnr_chat import HEADED, char_tok  # noqa: E402


def _init(d: Path, tok, block: int) -> Path:
    torch.manual_seed(0)
    model = GPT(GPTConfig(vocab_size=tok.vocab_size, block_size=block, n_layer=1, n_head=2, n_embd=16))
    init = d / "init"
    init.mkdir()
    torch.save({"model": model.state_dict(), "config": model.config.__dict__,
                "tokenizer_fingerprint": data.tokenizer_fingerprint(tok)}, init / "ckpt.pt")
    tok.save(init / "tokenizer.json")
    return init


def _long(split: str) -> dict:
    body = "t 1\ntask f(n: int) returns (r: int)\n" + "  ensures r == n\n" * 60 + "{\n  r := n;\n}"
    return {"messages": [{"role": "user", "content": "Problem: return n.\nSignature: f(n) -> int\n"},
                         {"role": "assistant", "content": body}],
            "split": split, "source": "long_one"}


class DropOverBlock(unittest.TestCase):
    def test_over_context_conversations_are_dropped_by_name_and_recorded(self):
        tok = char_tok()
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            init = _init(d, tok, 512)
            rows = [dict(chat_data.conversation(HEADED, tool=True), split="train"), _long("train"), _long("val")]
            convs = d / "c.jsonl"
            convs.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
            out = d / "out"
            args = ["--init", str(init), "--conversations", str(convs), "--out", str(out), "--steps", "2",
                    "--batch-size", "1", "--eval-every", "1", "--device", "cpu", "--lr", "1e-2", "--warmup", "1"]
            self.assertEqual(chat_train.main(args), 0)
            ident = json.loads((out / "run.json").read_text())["identities"]
            dropped = ident["dropped_over_block"]
            self.assertEqual([(x["split"], x["source"]) for x in dropped], [("train", "long_one"), ("val", "long_one")])
            self.assertTrue(all(x["tokens"] > 513 for x in dropped), dropped)
            self.assertEqual(ident["train"]["conversations"], 1)          # the headed one alone was trained
            self.assertIsNone(ident["val"])                               # the only val row was over the block

    def test_nothing_trainable_refuses(self):
        tok = char_tok()
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            init = _init(d, tok, 512)
            convs = d / "c.jsonl"
            convs.write_text(json.dumps(_long("train")) + "\n")
            with self.assertRaises(SystemExit):
                chat_train.main(["--init", str(init), "--conversations", str(convs), "--out", str(d / "out"),
                                 "--steps", "1", "--batch-size", "1", "--device", "cpu"])

    def test_a_fitting_set_records_no_drop(self):
        tok = char_tok()
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            init = _init(d, tok, 512)
            convs = d / "c.jsonl"
            convs.write_text(json.dumps(dict(chat_data.conversation(HEADED, tool=True), split="train")) + "\n")
            out = d / "out"
            self.assertEqual(chat_train.main(["--init", str(init), "--conversations", str(convs), "--out", str(out),
                                              "--steps", "1", "--batch-size", "1", "--device", "cpu"]), 0)
            self.assertEqual(json.loads((out / "run.json").read_text())["identities"]["dropped_over_block"], [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
