"""Audit the preregistered endpoint and comparison gates with tiny CPU checkpoints."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import torch

import summarize_pretraining as summary


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


class PretrainingSummaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.directories = {}

    def tearDown(self):
        self.temporary.cleanup()

    def arm(self, architecture, seed=1337, final=None, status="complete", completed=1000):
        directory = self.root / f"{architecture}-{seed}"
        directory.mkdir()
        self.directories[(architecture, seed)] = directory
        final = final if final is not None else (1.92 if architecture == "modern" else 2.0)
        token = '{"fixture":"frozen vocabulary bytes"}\n'
        (directory / "tokenizer.json").write_text(token)
        identity = {
            "model": {"n_layer": 12, "n_head": 12, "n_embd": 768, "block_size": 2048,
                      "vocab_size": 8192, "dropout": 0.0, "bias": architecture == "gpt",
                      "architecture": architecture, "gradient_checkpointing": True,
                      "rope_theta": 10000.0, "norm_eps": 1e-5, "ffn_hidden_size": None},
            "training": {"steps": 1000, "batch_size": 8, "grad_accum": 1, "lr": 0.0003,
                         "warmup_steps": 50, "bf16": True, "device": "cuda", "deterministic": True,
                         "cpu_threads": 4, "seed": seed},
            "evaluation": {"iters": 10, "seed": 12345, "loss_units": "nats/token"},
            "data": {"corpus_sha256": digest("train"), "train_sha256": digest("train"),
                     "val_sha256": digest("val"), "split_mode": "explicit", "split_seed": None, "val_frac": None},
            "source": {name: digest(name) for name in summary.SOURCE_FILES},
            "world_size": 4, "tokenizer_fingerprint": digest("tokenizer"),
            "tokenizer": {"kind": "bpe", "requested_vocab_size": 8192},
            "runtime": {"python": "3.11", "torch": "2.9", "cuda": "12.8", "cudnn": 9000,
                        "device_name": "fixture GPU"},
            "reproducibility": {"ddp_buckets": "registration_order", "cublas_workspace_config": ":4096:8"},
        }
        rows = [{"step": step, "val_nats_per_token": 5.0 + (final - 5.0) * step / 1000,
                 "train_nats_per_token": 5.2 + (final - 5.0) * step / 1000}
                for step in range(0, completed + 1, 100)]
        baseline = {key: rows[0][key] for key in summary.LOSSES}
        losses = {key: rows[-1][key] for key in summary.LOSSES}
        record = {"schema": 2, "identity": identity, "status": status, "completed_steps": completed,
                  "initial_losses": baseline, "losses": losses, "loss_units": "nats/token",
                  "evaluation_interval": 100, "tokenizer_file_sha256": digest(token),
                  "train_tokens": 1000000, "val_tokens": 50000, "parameters": 91245312,
                  "effective_batch_size": 32, "tokens_per_step": 65536,
                  "source_sha256": identity["source"]["train_distributed.py"],
                  "wall_seconds": 500.0, "optimizer_seconds": 400.0, "resumed_from_step": 0,
                  "peak_allocated_bytes_by_rank": [2**30] * 4,
                  "peak_reserved_bytes_by_rank": [2**31] * 4,
                  "private_extra": "/private/account/workspace/on-host"}
        self.write(directory, record, rows)
        return directory

    def write(self, directory, record, rows=None, update_checkpoint=True):
        (directory / "run.json").write_text(json.dumps(record))
        if rows is not None:
            (directory / "metrics.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        if update_checkpoint:
            checkpoint = {"distributed_schema": 2, "step": record["completed_steps"],
                          "identity": record["identity"], "config": record["identity"]["model"],
                          "tokenizer_fingerprint": record["identity"]["tokenizer_fingerprint"],
                          "initial_losses": record["initial_losses"], "losses": record["losses"],
                          "model": {"sentinel": torch.tensor([1.0])}}
            torch.save(checkpoint, directory / "ckpt.pt")

    def edit(self, directory, change, checkpoint=True):
        record = json.loads((directory / "run.json").read_text())
        change(record)
        self.write(directory, record, update_checkpoint=checkpoint)

    def test_one_pair_reports_prediction_but_replications_stay_pending(self):
        self.arm("modern")
        self.arm("gpt")
        report = summary.summarize(self.directories)
        self.assertEqual("replications_pending", report["overall_status"])
        self.assertEqual(1, report["completed_pairs"])
        self.assertAlmostEqual(0.04, report["paired_results"][0]["modern_relative_improvement"])
        self.assertTrue(report["paired_results"][0]["architecture_prediction_met"])
        self.assertIsNone(report["all_architecture_predictions_met"])
        self.assertEqual(6, len(report["arms"]))
        self.assertTrue(report["arms"][0]["checkpoint_endpoint_verified"])
        self.assertEqual(65536000, report["arms"][0]["trained_tokens"])
        rendered = json.dumps(report) + summary.markdown(report)
        self.assertNotIn("private/account", rendered)
        self.assertNotIn(str(self.root), rendered)
        self.assertNotIn("on-host", rendered)

    def test_every_seed_is_retained_including_falsified_predictions(self):
        for seed in summary.SEEDS:
            self.arm("modern", seed, final=2.1 if seed == 42 else 1.92)
            self.arm("gpt", seed)
        report = summary.summarize(self.directories)
        self.assertEqual("complete", report["overall_status"])
        self.assertTrue(report["replications_complete"])
        self.assertTrue(report["all_learning_predictions_met"])
        self.assertFalse(report["all_architecture_predictions_met"])
        self.assertEqual([1337, 7, 42], [pair["seed"] for pair in report["paired_results"]])
        self.assertLess(report["paired_results"][-1]["modern_relative_improvement"], 0)
        self.assertEqual(3, report["completed_pairs"])

    def test_matching_thresholds_and_failed_learning_are_not_hidden(self):
        self.arm("modern", final=4.01)
        self.arm("gpt", final=4.2)
        report = summary.summarize(self.directories)
        self.assertFalse(report["arms"][0]["learning_prediction_met"])
        self.assertTrue(report["paired_results"][0]["architecture_prediction_met"])
        self.assertEqual("replications_pending", report["overall_status"])

    def test_exact_prediction_boundaries_are_inclusive(self):
        self.arm("modern", final=4.0)
        self.arm("gpt", final=5.0)
        self.arm("modern", seed=7, final=1.94)
        self.arm("gpt", seed=7, final=2.0)
        report = summary.summarize(self.directories)
        self.assertTrue(report["arms"][0]["learning_prediction_met"])
        self.assertAlmostEqual(0.2, report["arms"][0]["validation_loss_drop_fraction"])
        self.assertTrue(report["paired_results"][1]["architecture_prediction_met"])
        self.assertAlmostEqual(0.03, report["paired_results"][1]["modern_relative_improvement"])

    def test_data_tokenizer_eval_source_and_schedule_mismatches_refuse_comparison(self):
        self.arm("modern")
        control = self.arm("gpt")
        original = json.loads((control / "run.json").read_text())
        changes = [
            lambda r: r["identity"]["data"].update(val_sha256=digest("different-val")),
            lambda r: r["identity"].update(tokenizer_fingerprint=digest("different-vocab")),
            lambda r: r["identity"]["evaluation"].update(iters=11),
            lambda r: r["identity"]["source"].update({"train.py": digest("different-optimizer")}),
            lambda r: r["identity"]["training"].update(steps=999),
            lambda r: r["identity"]["training"].update(batch_size=4, grad_accum=2),
            lambda r: r["identity"]["runtime"].update(torch="different-version"),
        ]
        for change in changes:
            record = copy.deepcopy(original)
            change(record)
            self.write(control, record)
            report = summary.summarize(self.directories)
            self.assertEqual("invalid_comparison", report["overall_status"])
            self.assertEqual(0, report["completed_pairs"])
            self.assertNotIn("modern_relative_improvement", report["paired_results"][0])

    def test_partial_failed_and_nonfinite_runs_remain_visible(self):
        self.arm("modern", status="stopped", completed=400)
        self.arm("gpt", status="failed", completed=200)
        report = summary.summarize(self.directories)
        self.assertEqual(["stopped", "failed"], [arm["status"] for arm in report["arms"][:2]])
        self.assertEqual("failed_or_invalid_arm", report["paired_results"][0]["status"])
        self.assertFalse(report["replications_complete"])
        directory = self.directories[("modern", 1337)]
        rows = [json.loads(line) for line in (directory / "metrics.jsonl").read_text().splitlines()]
        rows[-1]["val_nats_per_token"] = float("nan")
        (directory / "metrics.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        report = summary.summarize(self.directories)
        self.assertEqual("invalid", report["arms"][0]["status"])
        self.assertIn("nonfinite", report["arms"][0]["reason"])
        json.dumps(report, allow_nan=False)

    def test_endpoint_checkpoint_and_evaluation_rows_must_agree(self):
        directory = self.arm("modern")
        original = json.loads((directory / "run.json").read_text())
        self.edit(directory, lambda r: r.update(completed_steps=900))
        self.assertIn("endpoint", summary.summarize(self.directories)["arms"][0]["reason"])
        self.write(directory, original)
        self.edit(directory, lambda r: r["identity"]["evaluation"].update(iters=11), checkpoint=False)
        self.assertIn("checkpoint", summary.summarize(self.directories)["arms"][0]["reason"])
        self.write(directory, original)
        rows = [json.loads(line) for line in (directory / "metrics.jsonl").read_text().splitlines()]
        (directory / "metrics.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows if row["step"] != 500))
        self.assertIn("missing", summary.summarize(self.directories)["arms"][0]["reason"])

    def test_tokenizer_bytes_and_resumed_timing_scope(self):
        directory = self.arm("modern")
        self.edit(directory, lambda r: r.update(resumed_from_step=900))
        report = summary.summarize(self.directories)
        self.assertEqual("last_process_segment", report["arms"][0]["measurement_scope"])
        self.assertEqual(100, report["arms"][0]["measured_steps"])
        self.assertIn("last 100 optimizer steps", summary.markdown(report))
        (directory / "tokenizer.json").write_text("changed")
        self.assertIn("tokenizer", summary.summarize(self.directories)["arms"][0]["reason"])

    def test_cli_outputs_are_sanitized_and_invalid_input_returns_two(self):
        directory = self.arm("modern")
        output, markdown = self.root / "summary.json", self.root / "summary.md"
        args = ["--run", f"modern:1337={directory}", "--json", str(output), "--markdown", str(markdown)]
        self.assertEqual(0, summary.main(args))
        self.assertTrue(markdown.read_text().startswith("# Source-pretraining comparison"))
        self.assertNotIn(str(directory), output.read_text())
        (directory / "ckpt.pt").write_bytes(b"not a checkpoint")
        self.assertEqual(2, summary.main(args))
        self.assertIn("checkpoint metadata missing", output.read_text())


if __name__ == "__main__":
    unittest.main()
