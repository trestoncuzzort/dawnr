"""Training must preserve notation, requested context and intermediate artifacts."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import loop_train as train


class CharacterTokenizer:
    eos_token = "!"
    pad_token = None
    bos_token = "^"
    unk_token = None
    additional_special_tokens = []
    chat_template = "original model template"

    def __init__(self, broken=False):
        self.broken = broken

    def __call__(self, text, **kwargs):
        return {"input_ids": list(map(ord, text))}

    def decode(self, ids, **kwargs):
        text = "".join(map(chr, ids))
        return text.replace(" ", "") if self.broken else text

    def apply_chat_template(self, messages, **kwargs):
        return messages[0]["content"] + ":"

    def save_pretrained(self, path):
        Path(path, "tokenizer.json").write_text("saved")


class TrainingReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def data(self, name, rows):
        path = self.root / name
        path.write_text("\n".join(json.dumps(r) for r in rows))
        return path

    @staticmethod
    def row(prompt, chosen="answer", rejected="wrong"):
        return {"prompt": [{"role": "user", "content": prompt}], "chosen": chosen, "rejected": rejected}

    def test_fallback_preserves_template_and_special_tokens(self):
        bad = CharacterTokenizer(broken=True)
        good = CharacterTokenizer()
        good.chat_template = None
        good.eos_token = good.bos_token = None
        repaired = train.repair_tokenizer(bad, lambda: good)
        self.assertTrue(train.tokenizer_is_faithful(repaired))
        self.assertEqual(repaired.chat_template, bad.chat_template)
        self.assertEqual(repaired.eos_token, bad.eos_token)
        self.assertEqual(repaired.pad_token, bad.eos_token)

    def test_unfaithful_fallback_refuses_training(self):
        with self.assertRaisesRegex(ValueError, "refusing to train"):
            train.repair_tokenizer(CharacterTokenizer(True), lambda: CharacterTokenizer(True))

    def test_good_tokenizer_does_not_need_fallback(self):
        tok = CharacterTokenizer()
        def never():
            self.fail("Faithful tokenizers must not be replaced")
        self.assertIs(train.repair_tokenizer(tok, never), tok)

    def test_pinned_gpu_cannot_bypass_memory_or_existence(self):
        with patch.object(train, "free_vram_by_gpu", return_value={0: 3000, 1: 16000}):
            self.assertEqual(train.pick_gpu(None)[0], 1)
            with self.assertRaisesRegex(ValueError, "not present"):
                train.pick_gpu(9)
            gpu, free = train.pick_gpu(0)
            with self.assertRaisesRegex(ValueError, "below"):
                train.require_gpu_space(gpu, free, 4096)
        with patch.object(train, "pick_gpu", return_value=(0, {0: 3000})), patch(
                "sys.argv", ["loop_train.py", "--gpu", "0", "--min-free-mib", "4096"]):
            # main must return before any heavy import or dataset/model load.
            with patch.object(train, "load_tokenizer", side_effect=AssertionError("must not load")):
                self.assertEqual(train.main(), 3)

    def test_sft_sequence_limit_survives_trl_field_rename(self):
        class NewConfig:
            def __init__(self, max_length=1024): pass
        class OldConfig:
            def __init__(self, max_seq_length=1024): pass
        self.assertEqual(train.sft_length_kwargs(NewConfig, 4096), {"max_length": 4096})
        self.assertEqual(train.sft_length_kwargs(OldConfig, 4096), {"max_seq_length": 4096})
        with self.assertRaises(ValueError):
            train.sft_length_kwargs(object, 4096)

    def test_prompt_only_rows_are_excluded_and_reported(self):
        path = self.data("rows.jsonl", [self.row("short"), self.row("x" * 32)])
        for builder in (train.build_pair_dataset, train.build_sft_dataset):
            counts = {}
            dataset = builder(CharacterTokenizer(), path, 20, counts)
            self.assertEqual(len(dataset), 1)
            self.assertEqual(counts, {"input": 2, "kept": 1, "no_answer_tokens": 1, "partial_answers": 0})
            with self.assertRaisesRegex(ValueError, "retain answer tokens"):
                builder(CharacterTokenizer(), path, 3)

    def test_sft_does_not_duplicate_eos_and_empty_answers_fail(self):
        path = self.data("sft.jsonl", [self.row("prompt", "answer!")])
        ds = train.build_sft_dataset(CharacterTokenizer(), path, 20)
        self.assertEqual(ds[0]["text"], "prompt:answer!")
        empty = self.data("empty.jsonl", [self.row("prompt", "")])
        with self.assertRaisesRegex(ValueError, "no assistant answer"):
            train.build_sft_dataset(CharacterTokenizer(), empty, 20)
        with self.assertRaisesRegex(ValueError, "empty chosen"):
            train.build_pair_dataset(CharacterTokenizer(), empty, 20)

    def test_partial_completion_counts_are_visible(self):
        path = self.data("partial.jsonl", [self.row("prompt", "x" * 30)])
        for builder in (train.build_pair_dataset, train.build_sft_dataset):
            counts = {}
            self.assertEqual(len(builder(CharacterTokenizer(), path, 20, counts)), 1)
            self.assertEqual(counts["partial_answers"], 1)

    def test_intermediate_adapter_tokenizer_state_and_metrics_are_saved(self):
        root = self.root
        class Trainer:
            def save_model(self, destination):
                Path(destination, "adapter_model.safetensors").write_text("adapter")
            def save_state(self):
                (root / "trainer_state.json").write_text('{"global_step":3}')
            def save_metrics(self, stage, metrics):
                (root / (stage + "_results.json")).write_text(json.dumps(metrics))
        train.persist_stage(Trainer(), CharacterTokenizer(), root, "sft", {"loss": .5})
        self.assertTrue((root / "adapter_model.safetensors").exists())
        self.assertTrue((root / "tokenizer.json").exists())
        self.assertEqual(json.loads((root / "trainer_state.json").read_text())["global_step"], 3)
        self.assertEqual(json.loads((root / "sft_results.json").read_text())["loss"], .5)
        record = {"seed": 7, "pairs": train.file_record(root / "sft_results.json")}
        train.write_run_record(root, record, "sft_complete")
        saved = json.loads((root / "run.json").read_text())
        self.assertEqual(saved["stage"], "sft_complete")
        self.assertEqual(saved["seed"], 7)
        self.assertEqual(len(saved["pairs"]["sha256"]), 64)
        self.assertFalse((root / "run.json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
