"""Two real CPU ranks must resume the same optimizer schedule and random streams."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import torch

import train_distributed as training
from data import CharTokenizer, Corpus, build_tokenizer, tokenizer_fingerprint
from model import GPTConfig

HERE = Path(__file__).resolve().parent


def assert_nested_equal(test, left, right):
    if isinstance(left, torch.Tensor):
        test.assertTrue(torch.equal(left, right), "checkpoint tensors differ")
    elif isinstance(left, dict):
        test.assertEqual(left.keys(), right.keys())
        for key in left:
            assert_nested_equal(test, left[key], right[key])
    elif isinstance(left, (tuple, list)):
        test.assertEqual(len(left), len(right))
        for a, b in zip(left, right):
            assert_nested_equal(test, a, b)
    else:
        test.assertEqual(left, right)


class DistributedTrainingTests(unittest.TestCase):
    def test_frozen_tokenizer_mismatch_and_uncommitted_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frozen, saved = root / "frozen.json", root / "saved.json"
            CharTokenizer.from_text("abc").save(frozen)
            CharTokenizer.from_text("abcd").save(saved)
            args = training.parse_args(["--data", "train.txt", "--tokenizer", "char", "--tokenizer-file", str(frozen)])
            with self.assertRaisesRegex(ValueError, "differs"):
                training.check_tokenizer_request(args, saved)
            metrics = root / "metrics.jsonl"
            metrics.write_text('{"step":0,"wrong":true}\n{"step":2,"value":1}\n{"step":3}\npartial')
            training.prepare_metrics(metrics, 2, {"val_nats_per_token": 3.0}, resume=True)
            self.assertEqual([json.loads(line) for line in metrics.read_text().splitlines()],
                             [{"step": 0, "val_nats_per_token": 3.0}, {"step": 2, "value": 1}])

    def test_explicit_validation_identity_preserves_both_partitions(self):
        args = training.parse_args(["--data", "train.txt", "--validation-data", "val.txt", "--tokenizer", "bpe",
                                    "--device", "cpu", "--no-bf16", "--split-seed", "999"])
        train_text, val_text = "training words\n\ntraining words", "held out snowman \u2603\n\nsecond held out"
        tok = build_tokenizer(train_text, kind="bpe", vocab_size=256, training_text=train_text)
        corpus = Corpus(train_text, tok, "cpu", validation_text=val_text)
        cfg = GPTConfig(vocab_size=tok.vocab_size)
        identity = training.training_identity(args, cfg, corpus, train_text, tokenizer_fingerprint(tok), 2)
        self.assertEqual(corpus.train_text, train_text)
        self.assertEqual(corpus.val_text, val_text)
        self.assertEqual(identity["data"]["split_mode"], "explicit")
        self.assertIsNone(identity["data"]["split_seed"])
        self.assertEqual(identity["data"]["val_sha256"], training.digest(val_text))
        self.assertEqual(tok.training["text_sha256"], training.digest(train_text))
        saved = {"distributed_schema": training.SCHEMA, "identity": identity, "step": 2, "rank_rng": [{}, {}]}
        args.eval_iters += 1
        changed = training.training_identity(args, cfg, corpus, train_text, tokenizer_fingerprint(tok), 2)
        with self.assertRaisesRegex(ValueError, "evaluation"):
            training.validate_resume(saved, changed)
        self.assertEqual(identity["runtime"]["torch"], str(torch.__version__))
        self.assertEqual(identity["training"]["cpu_threads"], args.cpu_threads)
        training.require_validation_coverage(tok, val_text)
        with self.assertRaisesRegex(ValueError, "would discard"):
            training.require_validation_coverage(CharTokenizer.from_text(train_text), val_text)

    def test_changed_schedule_and_missing_rng_are_refused(self):
        identity = {"training": {"steps": 4}, "world_size": 2, "data": {"sha256": "original"}}
        saved = {"distributed_schema": training.SCHEMA, "identity": identity,
                 "step": 2, "rank_rng": [{}, {}]}
        training.validate_resume(saved, identity)
        changed = {**identity, "training": {"steps": 6}}
        with self.assertRaisesRegex(ValueError, "training"):
            training.validate_resume(saved, changed)
        with self.assertRaisesRegex(ValueError, "RNG"):
            training.validate_resume({**saved, "rank_rng": [{}]}, identity)
        with self.assertRaisesRegex(ValueError, "data"):
            training.validate_resume(saved, {**identity, "data": {"sha256": "changed"}})

    def test_two_rank_cpu_resume_matches_uninterrupted_training(self):
        self.check_resume(device="cpu", world=2)

    @unittest.skipUnless(os.environ.get("T_DDP_GPU_TEST") == "1", "set T_DDP_GPU_TEST=1 for four-GPU resume regression")
    def test_four_rank_gpu_resume_matches_uninterrupted_training(self):
        self.assertGreaterEqual(torch.cuda.device_count(), 4)
        self.check_resume(device="cuda", world=4)

    def check_resume(self, device, world):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus = root / "corpus.txt"
            corpus.write_text("\n\n".join(
                f"Document {i}: this is distinct local training text with value {i*i}. "
                + "Every batch has a causal next token target. " * 4 for i in range(100)))
            validation = root / "validation.txt"
            validation.write_bytes(("Held out family with unseen snowman \u2603 and validation words.\r\n" * 100).encode("utf-8"))
            frozen = root / "frozen-tokenizer.json"
            build_tokenizer(corpus.read_text(), kind="bpe", vocab_size=256,
                            training_text=corpus.read_text()).save(frozen)
            full, resumed = root / "full", root / "resumed"
            gpu = device == "cuda"
            block_size, batch_size = (512, 1) if gpu else (16, 2)
            base = [sys.executable, "-m", "torch.distributed.run", "--standalone", f"--nproc-per-node={world}",
                    str(HERE / "train_distributed.py"), "--data", str(corpus), "--device", device,
                    "--bf16" if gpu else "--no-bf16",
                    "--tokenizer", "bpe", "--tokenizer-file", str(frozen), "--validation-data", str(validation),
                    "--vocab-size", "256", "--steps", "4", "--n-layer", "8" if gpu else "2",
                    "--n-head", "8" if gpu else "2", "--n-embd", "512" if gpu else "16",
                    "--block-size", str(block_size), "--batch-size", str(batch_size),
                    "--grad-accum", "2", "--save-every", "2", "--eval-every", "2", "--eval-iters", "1",
                    "--cpu-threads", "1", "--seed", "11", "--split-seed", "23", "--dropout", "0.2"]
            env = dict(os.environ, OMP_NUM_THREADS="1", TOKENIZERS_PARALLELISM="false")
            if not gpu:
                env["CUDA_VISIBLE_DEVICES"] = ""
            for destination, extra in ((full, []), (resumed, ["--stop-after", "2"]), (resumed, ["--resume"])):
                p = subprocess.run(base + ["--out", str(destination)] + extra,
                                   cwd=HERE, env=env, capture_output=True, text=True, timeout=120)
                if p.returncode:
                    self.fail((p.stdout + p.stderr)[-12000:].replace(str(Path.home()), "~"))
                record = json.loads((destination / "run.json").read_text())
                self.assertEqual(record["data_device"], "cpu")
                self.assertEqual(record["loss_units"], "nats/token")
                self.assertEqual(record["effective_batch_size"], world * batch_size * 2)
                self.assertEqual(record["tokens_per_step"], world * batch_size * 2 * block_size)
                self.assertEqual(len(record["peak_allocated_bytes_by_rank"]), world)
                if gpu:
                    self.assertTrue(all(peak > 0 for peak in record["peak_allocated_bytes_by_rank"]))
                self.assertEqual((destination / "tokenizer.json").read_bytes(), frozen.read_bytes())
                rows = [json.loads(line) for line in (destination / "metrics.jsonl").read_text().splitlines()]
                self.assertEqual([row["step"] for row in rows], [0, 2] if extra == ["--stop-after", "2"] else [0, 2, 4])
                self.assertEqual(rows[0], {"step": 0, **record["initial_losses"]})
                self.assertEqual(record["identity"]["data"]["split_mode"], "explicit")
                self.assertEqual(record["identity"]["data"]["val_sha256"],
                                 training.digest(validation.read_bytes().decode("utf-8")))
            a = torch.load(full / "ckpt.pt", map_location="cpu", weights_only=True)
            b = torch.load(resumed / "ckpt.pt", map_location="cpu", weights_only=True)
            self.assertEqual(a["step"], 4)
            self.assertEqual(b["step"], 4)
            self.assertEqual(a["identity"], b["identity"])
            assert_nested_equal(self, a["model"], b["model"])
            assert_nested_equal(self, a["optimizer"], b["optimizer"])
            assert_nested_equal(self, a["rank_rng"], b["rank_rng"])
            self.assertEqual(a["losses"], b["losses"])
            self.assertEqual(a["initial_losses"], b["initial_losses"])
            self.assertNotEqual(a["initial_losses"]["val_nats_per_token"], a["losses"]["val_nats_per_token"])
            # Each rank consumes its own batches and dropout, instead of duplicating rank zero's stream.
            self.assertFalse(torch.equal(a["rank_rng"][0]["batch"], a["rank_rng"][1]["batch"]))
            self.assertFalse(torch.equal(a["rank_rng"][0]["torch"], a["rank_rng"][1]["torch"]))
            if gpu:
                self.assertFalse(torch.equal(a["rank_rng"][0]["cuda"], a["rank_rng"][1]["cuda"]))
            self.assertTrue((resumed / "tokenizer.json").is_file())
            self.assertFalse((resumed / "ckpt.pt.tmp").exists())


if __name__ == "__main__":
    unittest.main()
