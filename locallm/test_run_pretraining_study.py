"""Audit, interruption and resume behavior without launching any GPU training."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import torch

import run_pretraining_study as study


def write_json(path, value):
    path.write_text(json.dumps(value))


def arguments(root):
    return argparse.Namespace(corpus=root / "corpus", tokenizer_dir=root / "tokenizer", out=root / "study",
                              resume=False, check_only=False)


def audit_fixture(args):
    args.corpus.mkdir()
    args.tokenizer_dir.mkdir()
    for name in ("train.txt", "validation.txt", "provenance.jsonl", "sources-lock.json"):
        (args.corpus / name).write_bytes((name + "\r\nraw UTF-8 text \u2603").encode())
    artifacts = {name: study.sha256(path) for path in args.corpus.iterdir() for name in [path.name]}
    write_json(args.corpus / "quality.json", {"artifacts": artifacts})
    (args.tokenizer_dir / "tokenizer.json").write_text("frozen tokenizer fixture")
    token_hash = study.sha256(args.tokenizer_dir / "tokenizer.json")
    audit = {"corpus_artifacts": artifacts, "tokenizer_file_sha256": token_hash,
             "tokenizer_fingerprint": "semantic-fingerprint", "context": 2048, "vocab_size": 8192,
             "training_windows": 10, "cross_split_family_overlap": 0, "cross_split_exact_overlap": 0,
             "cross_split_normalized_overlap": 0,
             "splits": {split: {"roundtrip": True, "sha256": artifacts[filename], "tokens": 4096}
                        for split, filename in (("train", "train.txt"), ("validation", "validation.txt"))}}
    write_json(args.tokenizer_dir / "audit.json", audit)
    inspection = {"status": "passed", "audit_sha256": study.sha256(args.tokenizer_dir / "audit.json"),
                  "tokenizer_file_sha256": token_hash, "inspected_windows": list(range(10))}
    write_json(args.tokenizer_dir / "inspection.json", inspection)
    return inspection


class StudyTests(unittest.TestCase):
    def test_acceptance_is_bound_to_exact_audit_tokenizer_and_raw_partitions(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(study, "tokenizer_identity", return_value="semantic-fingerprint"):
            args = arguments(Path(directory))
            inspection = audit_fixture(args)
            accepted = study.validate_inputs(args.corpus, args.tokenizer_dir)
            self.assertEqual(accepted["corpus_artifacts"]["train.txt"], study.sha256(args.corpus / "train.txt"))
            for mutation, pattern in (({"status": "rejected"}, "rejected"),
                                      ({"audit_sha256": "stale"}, "exact audit"),
                                      ({"inspected_windows": [0] * 10}, "ten distinct")):
                write_json(args.tokenizer_dir / "inspection.json", {**inspection, **mutation})
                with self.assertRaisesRegex(ValueError, pattern):
                    study.validate_inputs(args.corpus, args.tokenizer_dir)
            write_json(args.tokenizer_dir / "inspection.json", inspection)
            train = args.corpus / "train.txt"
            train.write_bytes(train.read_bytes().replace(b"\r\n", b"\n"))
            with self.assertRaisesRegex(ValueError, "train.txt"):
                study.validate_inputs(args.corpus, args.tokenizer_dir)

    def test_gpu_selection_uses_measured_space_and_preserves_saved_rank_order(self):
        rows = [{"index": index, "free_mib": 14000 + index * 100, "name": "test GPU"} for index in range(5)]
        selected = study.select_gpus(rows)
        self.assertEqual([row["index"] for row in selected], [4, 3, 2, 1])
        rows.reverse()
        self.assertEqual([row["index"] for row in study.select_gpus(rows, [1, 4, 2, 3])], [1, 4, 2, 3])
        rows[0]["free_mib"] = 1000
        with self.assertRaisesRegex(ValueError, "no longer"):
            study.select_gpus(rows, [1, 4, 2, 3])

    def test_lock_refuses_a_second_study(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(study, "LOCK_FILE", Path(directory) / "lock"):
            with study.study_lock():
                with self.assertRaisesRegex(ValueError, "already holds"):
                    with study.study_lock():
                        self.fail("duplicate acquired lock")
            with study.study_lock():
                pass

    def test_failed_arm_stops_sequence_and_explicit_resume_skips_completed_arms(self):
        with tempfile.TemporaryDirectory() as directory:
            args = arguments(Path(directory))
            inputs, sources = {"audited": "unchanged"}, {"model.py": "unchanged"}
            rows = [{"index": index, "free_mib": 15000, "name": "test GPU"} for index in range(4)]
            launched = []

            def runner(command, log, selected, stop, on_started):
                launched.append(command)
                on_started(123)
                log.write_text("mock process\n")
                output = Path(command[command.index("--out") + 1])
                output.mkdir(exist_ok=True)
                if len(launched) == 2:
                    (output / "ckpt.pt").write_text("saved checkpoint")
                    return 42
                return 0

            with patch.object(study, "validate_inputs", return_value=inputs), patch.object(study, "source_hashes", return_value=sources), patch.object(study, "query_gpus", return_value=rows), patch.object(study, "run_arm", side_effect=runner), patch.object(study, "completed_run", return_value={"completed_steps": 1000}):
                with self.assertRaisesRegex(RuntimeError, "process failed"):
                    study.run_study(args, study.StopRequest())
                ledger = study.read_json(args.out / "study.json")
                self.assertEqual([arm["status"] for arm in ledger["arms"]], ["complete", "failed"] + ["pending"] * 4)
                self.assertEqual(len(launched), 2)
                with self.assertRaisesRegex(ValueError, "requires --resume"):
                    study.run_study(args, study.StopRequest())
                self.assertEqual(len(launched), 2)
                args.resume = True
                ledger = study.run_study(args, study.StopRequest())
                self.assertEqual(ledger["status"], "complete")
                self.assertEqual(len(launched), 7)
                self.assertIn("--resume", launched[2])
                self.assertEqual([arm["seed"] for arm in ledger["arms"]], [1337, 1337, 7, 7, 42, 42])
                self.assertEqual([arm["architecture"] for arm in ledger["arms"]], ["modern", "gpt"] * 3)
                self.assertEqual(len(ledger["arms"][1]["attempts"]), 2)
                self.assertTrue(all(not Path(attempt["log"]).is_absolute() for arm in ledger["arms"] for attempt in arm["attempts"]))
                study.run_study(args, study.StopRequest())
                self.assertEqual(len(launched), 7)

    def test_source_change_prevents_next_arm(self):
        with tempfile.TemporaryDirectory() as directory:
            args = arguments(Path(directory))
            hashes = iter([{"model.py": "first"}, {"model.py": "first"}, {"model.py": "changed"}])
            rows = [{"index": index, "free_mib": 15000, "name": "test GPU"} for index in range(4)]
            with patch.object(study, "validate_inputs", return_value={}), patch.object(study, "source_hashes", side_effect=lambda: next(hashes)), patch.object(study, "query_gpus", return_value=rows), patch.object(study, "run_arm", return_value=0) as runner, patch.object(study, "completed_run", return_value={}):
                with self.assertRaisesRegex(ValueError, "changed between arms"):
                    study.run_study(args, study.StopRequest())
                self.assertEqual(runner.call_count, 1)
                self.assertEqual(study.read_json(args.out / "study.json")["status"], "failed")

    def test_interruption_terminates_launcher_and_child_group(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pidfile = root / "child.pid"
            code = "import subprocess,sys,time; from pathlib import Path; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(60)"
            stop = study.StopRequest()

            def interrupt():
                deadline = time.monotonic() + 5
                while not pidfile.exists() and time.monotonic() < deadline:
                    time.sleep(0.01)
                stop.handler(signal.SIGTERM, None)

            thread = threading.Thread(target=interrupt)
            thread.start()
            returncode = study.run_arm([sys.executable, "-c", code, str(pidfile)], root / "run.log", [0, 1, 2, 3], stop, lambda pid: None)
            thread.join(timeout=6)
            self.assertLess(returncode, 0)
            self.assertTrue(pidfile.exists())
            status = Path("/proc") / pidfile.read_text() / "stat"
            self.assertTrue(not status.exists() or status.read_text().split(") ", 1)[1][0] == "Z")

    def test_completed_checkpoint_and_history_are_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            args = arguments(Path(directory))
            arm = study.arms()[0]
            output = args.out / arm["out"]
            output.mkdir(parents=True)
            (output / "tokenizer.json").write_text("frozen")
            source = {name: name + "-hash" for name in study.SOURCE_FILES}
            inputs = {"corpus_artifacts": {"train.txt": "train", "validation.txt": "validation"},
                      "tokenizer_file_sha256": study.sha256(output / "tokenizer.json"), "tokenizer_fingerprint": "token"}
            ledger = {"inputs": inputs, "source_sha256": source}
            identity = {"world_size": 4,
                        "training": {key: study.CONFIG[key] for key in ("steps", "batch_size", "grad_accum", "lr", "warmup_steps", "bf16", "deterministic", "cpu_threads")},
                        "model": {key: study.CONFIG[key] for key in ("vocab_size", "block_size", "n_layer", "n_head", "n_embd", "dropout", "gradient_checkpointing")},
                        "data": {"split_mode": "explicit", "train_sha256": "train", "val_sha256": "validation"},
                        "tokenizer_fingerprint": "token", "evaluation": {"iters": 10, "seed": 12345, "loss_units": "nats/token"},
                        "source": {name: value for name, value in source.items() if name != "run_pretraining_study.py"}}
            identity["training"].update(seed=1337, device="cuda")
            identity["model"].update(architecture="modern", bias=False)
            initial, final = {"train_nats_per_token": 9.0, "val_nats_per_token": 9.1}, {"train_nats_per_token": 3.0, "val_nats_per_token": 3.2}
            record = {"status": "complete", "completed_steps": 1000, "loss_units": "nats/token", "initial_losses": initial,
                      "losses": final, "identity": identity, "parameters": 91245312, "tokens_per_step": 65536,
                      "wall_seconds": 1, "peak_allocated_bytes_by_rank": [100] * 4, "peak_reserved_bytes_by_rank": [200] * 4}
            write_json(output / "run.json", record)
            metrics = [{"step": step, **(initial if step == 0 else final)} for step in range(0, 1001, 100)]
            (output / "metrics.jsonl").write_text("".join(json.dumps(row) + "\n" for row in metrics))
            checkpoint = {"distributed_schema": 2, "step": 1000, "identity": identity, "initial_losses": initial,
                          "losses": final, "rank_rng": [{}] * 4, "model": {"weight": torch.tensor(1.0)},
                          "optimizer": {"state": {0: {"step": torch.tensor(1000)}}, "param_groups": [{"lr": 0.0003}]}}
            torch.save(checkpoint, output / "ckpt.pt")
            accepted = study.completed_run(args, arm, ledger)
            checkpoint["step"] = 900
            torch.save(checkpoint, output / "ckpt.pt")
            with self.assertRaisesRegex(ValueError, "checkpoint and endpoint"):
                study.completed_run(args, arm, ledger)
            checkpoint["step"] = 1000
            torch.save(checkpoint, output / "ckpt.pt")
            arm.update(accepted)
            record["wall_seconds"] = 2
            write_json(output / "run.json", record)
            with self.assertRaisesRegex(ValueError, "artifacts changed"):
                study.completed_run(args, arm, ledger)


if __name__ == "__main__":
    unittest.main()
