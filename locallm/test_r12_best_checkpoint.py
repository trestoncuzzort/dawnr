"""r12 fix: the sweep's best-validation state was lost.

THE DEFECT (internal/PRETRAIN-R12-2026-09-25.md, "Results"): train_distributed.py
overwrites ckpt.pt every --save-every steps, so the wd0.8/lr1e-3 arm's best state
(step 7,400, validation 1.166) was gone by the time the run finished overfit at
step 11,200 (validation 1.289). This tests the fix: train.EarlyStopper (already
used by train.py; receipt 6f98c04dd7df, Lightning's EarlyStopping + ModelCheckpoint
algorithm, github.com/Lightning-AI/pytorch-lightning) is reused rather than a
second stopping/keeping implementation, best.pt is written rank 0 only whenever
validation improves, and the resume contract carries the stopper's state
(including best_val/best_step, so a resumed run does not reset "best" to
infinity and overwrite a genuinely-better pre-interruption best.pt with a worse
post-interruption checkpoint).

Runs on the CPU with two ranks, torch.distributed.run --standalone. The real-run
tests take under a minute each.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

import torch  # noqa: E402

import data  # noqa: E402
import train  # noqa: E402
import train_distributed as training  # noqa: E402
import run_pretraining_study as study  # noqa: E402
from model import GPT, GPTConfig  # noqa: E402


# ---------------------------------------------------------------------------
# flags, identity, resume refusal
# ---------------------------------------------------------------------------
class FlagTests(unittest.TestCase):
    def test_defaults_match_the_measured_constants_and_early_stop_is_off(self):
        args = training.parse_args(["--data", "x"])
        self.assertFalse(args.early_stop, "a recorded --steps command must not be cut short by default")
        self.assertEqual(args.min_delta, train.EARLY_STOP_MIN_DELTA)
        self.assertEqual(args.patience, train.EARLY_STOP_PATIENCE)

    def test_bad_settings_are_refused(self):
        for extra in (["--patience", "0"], ["--patience", "-1"], ["--min-delta", "-0.1"]):
            with self.assertRaises(SystemExit):
                training.parse_args(["--data", "x", *extra])

    def test_early_stop_is_a_boolean_optional_flag(self):
        self.assertTrue(training.parse_args(["--data", "x", "--early-stop"]).early_stop)
        self.assertFalse(training.parse_args(["--data", "x", "--no-early-stop"]).early_stop)


class IdentityResumeTests(unittest.TestCase):
    def test_identity_carries_the_stopping_settings_and_a_change_is_refused(self):
        train_text, val_text = "training words\n\ntraining words", "held out\n\nsecond held out"
        tok = data.build_tokenizer(train_text, kind="bpe", vocab_size=256, training_text=train_text)
        corpus = data.Corpus(train_text, tok, "cpu", validation_text=val_text)
        cfg = GPTConfig(vocab_size=tok.vocab_size)
        argv = ["--data", "train.txt", "--validation-data", "val.txt", "--device", "cpu", "--no-bf16"]
        base = training.parse_args(argv)
        identity = training.training_identity(base, cfg, corpus, train_text, data.tokenizer_fingerprint(tok), 2)
        self.assertEqual(identity["training"]["early_stop"], False)
        self.assertEqual(identity["training"]["min_delta"], train.EARLY_STOP_MIN_DELTA)
        self.assertEqual(identity["training"]["patience"], train.EARLY_STOP_PATIENCE)
        saved = {"distributed_schema": training.SCHEMA, "identity": identity, "step": 2, "rank_rng": [{}, {}]}
        for changed_args in (argv + ["--early-stop"], argv + ["--min-delta", "0.02"], argv + ["--patience", "9"]):
            changed = training.training_identity(training.parse_args(changed_args), cfg, corpus, train_text,
                                                  data.tokenizer_fingerprint(tok), 2)
            with self.assertRaisesRegex(ValueError, "training"):
                training.validate_resume(saved, changed)


# ---------------------------------------------------------------------------
# best_record / save_best_checkpoint, no distributed process needed
# ---------------------------------------------------------------------------
def tiny_gpt():
    torch.manual_seed(0)
    cfg = GPTConfig(vocab_size=32, block_size=8, n_layer=1, n_head=2, n_embd=16, architecture="gpt", bias=True)
    return GPT(cfg), cfg


class BestRecordTests(unittest.TestCase):
    def test_best_record_is_none_before_any_finite_check(self):
        stopper = train.EarlyStopper()
        record = training.best_record(stopper)
        self.assertEqual(record, {"step": None, "val_nats_per_token": None, "train_nats_per_token": None})

    def test_best_record_reports_the_lowest_check_only(self):
        stopper = train.EarlyStopper(patience=50)
        stopper.update(10, 2.0, train=1.0)
        stopper.update(20, 1.5, train=0.8)
        stopper.update(30, 1.8, train=0.6)   # worse: not the best
        record = training.best_record(stopper)
        self.assertEqual(record, {"step": 20, "val_nats_per_token": 1.5, "train_nats_per_token": 0.8})


class SaveBestCheckpointTests(unittest.TestCase):
    def test_writes_atomically_and_the_weights_score_as_recorded(self):
        model, cfg = tiny_gpt()
        stopper = train.EarlyStopper(patience=50)
        stopper.update(0, 3.0, model=model, train=2.9)
        with torch.no_grad():
            for p in model.parameters():
                p.add_(0.01)                  # move the live model away from what was kept
        stopper.update(10, 1.2, model=model, train=1.0)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "best.pt"
            training.save_best_checkpoint(path, stopper, cfg, "fingerprint-x")
            self.assertFalse(path.with_name("best.pt.tmp").exists())
            loaded = torch.load(path, map_location="cpu", weights_only=True)
        self.assertEqual(loaded["step"], 10)
        self.assertEqual(loaded["val_nats_per_token"], 1.2)
        self.assertEqual(loaded["train_nats_per_token"], 1.0)
        self.assertEqual(loaded["tokenizer_fingerprint"], "fingerprint-x")
        self.assertEqual(loaded["config"], asdict(cfg))
        restored = GPT(GPTConfig(**loaded["config"]))
        restored.load_state_dict(loaded["model"])
        for name, p in model.named_parameters():
            self.assertTrue(torch.equal(p, restored.state_dict()[name]), name)


class ConfigSyncTests(unittest.TestCase):
    def test_the_sweep_config_never_cuts_a_recorded_arm_short(self):
        # run_pretraining_study.CONFIG hardcodes these (it avoids importing train,
        # which needs torch, at module scope) so they cannot silently drift from
        # the constants a real run's argparse defaults would otherwise pick up.
        self.assertEqual(study.CONFIG["early_stop"], False)
        self.assertEqual(study.CONFIG["min_delta"], train.EARLY_STOP_MIN_DELTA)
        self.assertEqual(study.CONFIG["patience"], train.EARLY_STOP_PATIENCE)


# ---------------------------------------------------------------------------
# real two-rank CPU runs
# ---------------------------------------------------------------------------
def letters_corpus(seed: int, n: int, low: int, high: int, alphabet: str) -> str:
    import random
    rng = random.Random(seed)
    docs = ["".join(rng.choice(alphabet) for _ in range(rng.randint(low, high))) for _ in range(n)]
    return "\n\n".join(docs)


ALPHABET = "abcdefghijklmnop "


class RealRunTests(unittest.TestCase):
    """Both real-run tests share one letters corpus: random character frequencies
    are learned in well under a hundred steps and there is nothing else in the
    text to learn, so validation loss falls fast and then wobbles at the noise
    floor (test_early_stop.py's _letters_corpus finding, reused here at
    train_distributed scale)."""

    def _write_corpus(self, root: Path):
        (root / "corpus.txt").write_text(letters_corpus(0, 40, 200, 400, ALPHABET), encoding="utf-8")
        (root / "validation.txt").write_text(letters_corpus(1, 12, 200, 400, ALPHABET), encoding="utf-8")

    def _base_command(self, root: Path, out: Path, **overrides):
        cfg = dict(steps=300, eval_every=20, save_every=20, patience=3, min_delta=0.01,
                   n_layer=2, n_head=2, n_embd=32, block_size=32, batch_size=8, lr=2e-2)
        cfg.update(overrides)
        return [sys.executable, "-m", "torch.distributed.run", "--standalone", "--nproc-per-node=2",
                str(HERE / "train_distributed.py"), "--data", str(root / "corpus.txt"),
                "--validation-data", str(root / "validation.txt"), "--tokenizer", "char",
                "--out", str(out), "--device", "cpu", "--no-bf16", "--architecture", "gpt",
                "--seed", "11", "--split-seed", "23", "--dropout", "0.0", "--cpu-threads", "1",
                "--eval-iters", "2", "--log-every", "0",
                "--steps", str(cfg["steps"]), "--eval-every", str(cfg["eval_every"]),
                "--save-every", str(cfg["save_every"]), "--patience", str(cfg["patience"]),
                "--min-delta", str(cfg["min_delta"]), "--n-layer", str(cfg["n_layer"]),
                "--n-head", str(cfg["n_head"]), "--n-embd", str(cfg["n_embd"]),
                "--block-size", str(cfg["block_size"]), "--batch-size", str(cfg["batch_size"]),
                "--grad-accum", "1", "--lr", str(cfg["lr"])]

    def _run(self, command, root):
        env = dict(os.environ, OMP_NUM_THREADS="1", TOKENIZERS_PARALLELISM="false", CUDA_VISIBLE_DEVICES="")
        proc = subprocess.run(command, cwd=HERE, env=env, capture_output=True, text=True, timeout=180)
        if proc.returncode:
            self.fail((proc.stdout + proc.stderr)[-8000:])
        return proc

    @staticmethod
    def _metrics(out: Path):
        return [json.loads(line) for line in (out / "metrics.jsonl").read_text().splitlines()]

    def test_best_checkpoint_matches_the_true_minimum_and_resume_agrees(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_corpus(root)
            full, resumed = root / "full", root / "resumed"
            base = self._base_command(root, full)
            self._run(base, root)
            rows = self._metrics(full)
            best_step = min(rows, key=lambda r: r["val_nats_per_token"])["step"]
            best_val = min(r["val_nats_per_token"] for r in rows)

            run = json.loads((full / "run.json").read_text())
            self.assertEqual(run["best"]["step"], best_step)
            self.assertAlmostEqual(run["best"]["val_nats_per_token"], best_val, places=6)
            self.assertTrue((full / "best.pt").is_file())
            self.assertFalse((full / "best.pt.tmp").exists())
            best_ckpt = torch.load(full / "best.pt", map_location="cpu", weights_only=True)
            self.assertEqual(best_ckpt["step"], best_step)
            self.assertAlmostEqual(best_ckpt["val_nats_per_token"], best_val, places=6)

            # Score the saved weights directly and confirm they really are the
            # checkpoint that scored best, not just the record saying so.
            tokenizer = data.load_tokenizer(full / "tokenizer.json")
            corpus = data.Corpus((root / "corpus.txt").read_text(encoding="utf-8"), tokenizer, "cpu",
                                 validation_text=(root / "validation.txt").read_text(encoding="utf-8"))
            model = GPT(GPTConfig(**best_ckpt["config"]))
            model.load_state_dict(best_ckpt["model"])
            model.eval()
            generator = torch.Generator(device="cpu").manual_seed(training.EVAL_SEED)
            with torch.no_grad():
                losses = torch.stack([model(*corpus.get_batch("val", 8, 32, generator=generator))[1]
                                      for _ in range(20)])
            self.assertLess(abs(losses.mean().item() - best_val), 0.35,
                            "best.pt's weights do not score near the recorded best validation loss")

            # Interrupt well after the best step and resume: exact-step resume
            # means the full and resumed runs must agree on everything, the
            # best checkpoint included, not just the last one.
            stop_after = best_step + 20 if best_step + 20 <= 300 else 300
            self._run(self._base_command(root, resumed) + ["--stop-after", str(stop_after)], root)
            self._run(self._base_command(root, resumed) + ["--resume"], root)
            resumed_run = json.loads((resumed / "run.json").read_text())
            self.assertEqual(resumed_run["best"], run["best"])
            resumed_best = torch.load(resumed / "best.pt", map_location="cpu", weights_only=True)
            for name, tensor in best_ckpt["model"].items():
                self.assertTrue(torch.equal(tensor, resumed_best["model"][name]), name)
            full_ckpt = torch.load(full / "ckpt.pt", map_location="cpu", weights_only=True)
            resumed_ckpt = torch.load(resumed / "ckpt.pt", map_location="cpu", weights_only=True)
            self.assertEqual(full_ckpt["early_stopping"], resumed_ckpt["early_stopping"])

    def test_resume_does_not_overwrite_a_better_pre_interruption_best(self):
        # A corpus this small and a model this tiny memorise the letter
        # frequencies fast and then validation only gets worse: the true best is
        # an early check, so everything evaluated after --stop-after is worse,
        # and the resumed run's best.pt must stay the pre-interruption one.
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_corpus(root)
            out = root / "run"
            self._run(self._base_command(root, out) + ["--stop-after", "20"], root)
            first_best = json.loads((out / "run.json").read_text())["best"]
            self.assertEqual(first_best["step"], 20)   # the only check so far
            first_best_bytes = (out / "best.pt").read_bytes()
            self._run(self._base_command(root, out, steps=300) + ["--resume"], root)
            final_run = json.loads((out / "run.json").read_text())
            # The recorded best must never regress relative to what was already found.
            self.assertLessEqual(final_run["best"]["val_nats_per_token"], first_best["val_nats_per_token"] + 1e-9)
            if final_run["best"]["step"] == first_best["step"]:
                self.assertEqual((out / "best.pt").read_bytes(), first_best_bytes,
                                "best.pt changed even though no later check beat the pre-interruption best")

    def test_early_stop_halts_before_the_horizon(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write_corpus(root)
            out = root / "run"
            self._run(self._base_command(root, out, steps=2000, eval_every=10, save_every=10,
                                         patience=3, min_delta=0.01) + ["--early-stop"], root)
            run = json.loads((out / "run.json").read_text())
            self.assertLess(run["completed_steps"], 2000, "early stopping never triggered on a plateauing corpus")
            self.assertEqual(run["stop_reason"], "patience")
            self.assertEqual(run["status"], "stopped")
            rows = self._metrics(out)
            best_step = min(rows, key=lambda r: r["val_nats_per_token"])["step"]
            self.assertEqual(run["best"]["step"], best_step)
            self.assertLess(best_step, run["completed_steps"], "patience should exhaust after the best check")
            ckpt = torch.load(out / "ckpt.pt", map_location="cpu", weights_only=True)
            self.assertEqual(ckpt["early_stopping"]["stopping_reason"], "patience")


if __name__ == "__main__":
    unittest.main()
