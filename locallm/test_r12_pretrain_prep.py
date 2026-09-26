"""r12 W5: the core re-pretraining for the small-data regime, prepared without a GPU.

Three things, each tested on a two-layer, width-32 model so a run takes seconds
on a CPU (needs torch: run on the lab, CPU only):

* `train.make_optimizer(model, lr, weight_decay)` decays only tensors with two
  or more dimensions, as nanoGPT's configure_optimizers does
  (raw.githubusercontent.com/karpathy/nanoGPT/master/model.py); the split of the
  parameter set is checked to be exact, and a step with zero gradients shows
  the decay reaching the matrices and nothing else.
* `train_distributed.py --weight-decay`, recorded in the run identity so a
  resume with another value is refused, and `run_pretraining_study.CONFIG`
  carries the value its recorded commands ran with. The sweep's arms and the
  commands written in internal/PRETRAIN-R12-2026-09-25.md must agree.
* `continue_from_checkpoint.py --replay-data --replay-frac` mixes source rows
  into every batch at an exact row fraction (Ibrahim et al., arXiv:2403.08763),
  on both the windows path and `--doc-batches`, and the source corpus's loss is
  recorded before and after the fine-tune.
"""
import hashlib
import json
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import torch  # noqa: E402

import data  # noqa: E402
import train  # noqa: E402
import train_distributed as training  # noqa: E402
import run_pretraining_study as study  # noqa: E402
import continue_from_checkpoint as continuing  # noqa: E402
from model import GPT, GPTConfig  # noqa: E402

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "continue_from_checkpoint.py"
NOTE = HERE.parent / "internal" / "PRETRAIN-R12-2026-09-25.md"


def tiny(architecture="modern"):
    torch.manual_seed(0)
    cfg = GPTConfig(vocab_size=64, block_size=16, n_layer=2, n_head=2, n_embd=16,
                    architecture=architecture, bias=architecture == "gpt")
    return GPT(cfg)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DecayGroupTests(unittest.TestCase):
    def test_the_parameter_split_is_exact_for_both_architectures(self):
        for architecture in ("gpt", "modern"):
            with self.subTest(architecture=architecture):
                model = tiny(architecture)
                optimizer = train.make_optimizer(model, 1e-3, weight_decay=0.8)
                groups = optimizer.param_groups
                self.assertEqual(len(groups), 2)
                decayed = {id(p) for p in groups[0]["params"]}
                undecayed = {id(p) for p in groups[1]["params"]}
                self.assertEqual(decayed, {id(p) for p in model.parameters() if p.dim() >= 2})
                self.assertEqual(undecayed, {id(p) for p in model.parameters() if p.dim() < 2})
                self.assertFalse(decayed & undecayed)
                self.assertEqual(groups[0]["weight_decay"], 0.8)
                self.assertEqual(groups[1]["weight_decay"], 0.0)
                self.assertEqual(sum(p.numel() for g in groups for p in g["params"]), model.total_params())
                for name, p in model.named_parameters():
                    self.assertEqual(id(p) in decayed, p.dim() >= 2, name)
                self.assertTrue(undecayed, "every core has norm gains, which must not be decayed")
                if architecture == "gpt":
                    self.assertTrue(any(name.endswith(".bias") and id(p) in undecayed
                                        for name, p in model.named_parameters()))
                split = train.decay_split(model)
                self.assertEqual(split["decayed_tensors"], len(groups[0]["params"]))
                self.assertEqual(split["undecayed_tensors"], len(groups[1]["params"]))
                self.assertEqual(split["decayed_parameters"] + split["undecayed_parameters"], model.total_params())

    def test_default_reproduces_the_recorded_commands(self):
        optimizer = train.make_optimizer(tiny(), 1e-3)
        self.assertEqual(optimizer.param_groups[0]["weight_decay"], 0.1)
        self.assertEqual(optimizer.param_groups[1]["weight_decay"], 0.0)
        for group in optimizer.param_groups:
            self.assertEqual(tuple(group["betas"]), (0.9, 0.95))
        with self.assertRaises(ValueError):
            train.make_optimizer(tiny(), 1e-3, weight_decay=-0.1)

    def test_decay_reaches_the_matrices_and_nothing_else(self):
        # With a zero gradient AdamW's update term is zero, so one step is exactly
        # p <- p * (1 - lr * wd) on a decayed tensor and the identity elsewhere.
        model = tiny("gpt")
        before = {name: p.detach().clone() for name, p in model.named_parameters()}
        optimizer = train.make_optimizer(model, 0.5, weight_decay=0.8)
        for p in model.parameters():
            p.grad = torch.zeros_like(p)
        optimizer.step()
        for name, p in model.named_parameters():
            if p.dim() >= 2:
                self.assertTrue(torch.allclose(p, before[name] * (1 - 0.5 * 0.8), atol=1e-7), name)
            else:
                self.assertTrue(torch.equal(p, before[name]), name)


class DistributedFlagTests(unittest.TestCase):
    def test_flag_default_range_and_identity(self):
        self.assertEqual(training.parse_args(["--data", "x"]).weight_decay, 0.1)
        self.assertEqual(training.parse_args(["--data", "x", "--weight-decay", "0.8"]).weight_decay, 0.8)
        with self.assertRaises(SystemExit):
            training.parse_args(["--data", "x", "--weight-decay", "-0.1"])
        train_text, val_text = "training words\n\ntraining words", "held out\n\nsecond held out"
        tok = data.build_tokenizer(train_text, kind="bpe", vocab_size=256, training_text=train_text)
        corpus = data.Corpus(train_text, tok, "cpu", validation_text=val_text)
        cfg = GPTConfig(vocab_size=tok.vocab_size)
        argv = ["--data", "train.txt", "--validation-data", "val.txt", "--device", "cpu", "--no-bf16"]
        identity = training.training_identity(training.parse_args(argv + ["--weight-decay", "0.8"]), cfg, corpus,
                                              train_text, data.tokenizer_fingerprint(tok), 2)
        self.assertEqual(identity["optimizer"]["weight_decay"], 0.8)
        self.assertEqual(tuple(identity["optimizer"]["betas"]), (0.9, 0.95))
        self.assertIn("2 or more dimensions", identity["optimizer"]["decay"])
        control = training.training_identity(training.parse_args(argv), cfg, corpus,
                                             train_text, data.tokenizer_fingerprint(tok), 2)
        saved = {"distributed_schema": training.SCHEMA, "identity": control, "step": 2, "rank_rng": [{}, {}]}
        with self.assertRaisesRegex(ValueError, "optimizer"):
            training.validate_resume(saved, identity)


class SweepConfigTests(unittest.TestCase):
    ARMS = {(1e-3, 0.8), (3e-3, 0.8), (3e-3, 0.1)}

    def test_config_carries_the_decay_and_the_sweep_arms(self):
        self.assertEqual(study.CONFIG["weight_decay"], 0.1)
        args = Namespace(corpus=Path("corpus"), tokenizer_dir=Path("tokenizer"), out=Path("out"))
        command = study.command_for(args, study.arms()[0], False)
        self.assertEqual(command[command.index("--weight-decay") + 1], "0.1")
        parsed = training.parse_args(command[command.index("--data"):])
        self.assertEqual(parsed.weight_decay, 0.1)
        self.assertEqual(study.R12_SWEEP_STEPS, 11200)
        self.assertEqual({(arm["lr"], arm["weight_decay"]) for arm in study.R12_SWEEP}, self.ARMS)
        self.assertEqual(len({arm["id"] for arm in study.R12_SWEEP}), 3)
        for arm in study.R12_SWEEP:
            self.assertEqual(arm["steps"], study.R12_SWEEP_STEPS)
            self.assertEqual(arm["warmup_steps"], study.R12_SWEEP_STEPS // 20)
            self.assertEqual(arm["architecture"], "gpt")

    def test_the_note_commands_are_the_sweep(self):
        if not NOTE.exists():
            self.fail(f"{NOTE} is missing from this checkout; the sweep's commands live there")
        text = NOTE.read_text(encoding="utf-8")
        commands = []
        for block in re.findall(r"```(?:\w+)?\n(.*?)```", text, flags=re.S):
            joined = block.replace("\\\n", " ")
            for line in joined.splitlines():
                if "train_distributed.py" in line:
                    tokens = shlex.split(line)
                    commands.append(tokens[next(i for i, t in enumerate(tokens) if t.endswith("train_distributed.py")) + 1:])
        self.assertEqual(len(commands), len(study.R12_SWEEP), "one command per sweep arm")
        seen = set()
        for argv in commands:
            args = training.parse_args(argv)
            seen.add((args.lr, args.weight_decay))
            self.assertEqual(args.steps, study.R12_SWEEP_STEPS)
            self.assertEqual(args.warmup_steps, study.R12_SWEEP_STEPS // 20)
            self.assertEqual(args.architecture, "gpt")
            self.assertIsNotNone(args.validation_data)
            self.assertIsNotNone(args.tokenizer_file)
            for key in ("batch_size", "grad_accum", "block_size", "n_layer", "n_head", "n_embd", "dropout",
                        "eval_every", "eval_iters", "save_every", "log_every", "cpu_threads",
                        "gradient_checkpointing", "deterministic", "bf16", "tokenizer", "vocab_size", "preset"):
                self.assertEqual(getattr(args, key), study.CONFIG[key], key)
        self.assertEqual(seen, self.ARMS)


class ReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.text = "\n\n".join(f"Problem: fold the number {i}\nSignature: f{i}(int) -> int\n"
                               + ("r := r + %d;\n" % i) * (1 + (i * 37) % 7) + "}" for i in range(48)) + "\n"
        cls.data = root / "corpus.txt"
        cls.data.write_text(cls.text, encoding="utf-8")
        cls.split = root / "split.json"
        cls.split.write_text(json.dumps({"eval_ids": [999999]}), encoding="utf-8")
        source = root / "source"
        source.mkdir()
        cls.replay = source / "train.txt"
        cls.replay.write_text("\n\n".join(cls.method(i) for i in range(120)) + "\n", encoding="utf-8")
        cls.validation = source / "validation.txt"
        cls.validation.write_text("\n\n".join(cls.method(i) for i in range(120, 150)) + "\n", encoding="utf-8")
        tok = data.CharTokenizer.from_text(cls.text + cls.replay.read_text() + cls.validation.read_text())
        cls.init = root / "init"
        cls.init.mkdir()
        tok.save(cls.init / "tokenizer.json")
        cfg = GPTConfig(vocab_size=tok.vocab_size, block_size=64, n_layer=2, n_head=2, n_embd=32)
        torch.manual_seed(0)
        torch.save({"model": GPT(cfg).state_dict(), "config": asdict(cfg),
                    "tokenizer_fingerprint": data.tokenizer_fingerprint(tok)}, cls.init / "ckpt.pt")
        cls.runs = 0

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @staticmethod
    def method(i):
        return (f"method m{i}(x: int) returns (r: int)\n  ensures r == x * {i}\n{{\n"
                f"  r := x * {i};\n}}")

    def command(self, out, *extra, steps=10, batch=8):
        return [sys.executable, str(SCRIPT), "--init", str(self.init), "--data", str(self.data),
                "--split", str(self.split), "--out", str(out), "--steps", str(steps),
                "--batch-size", str(batch), "--block-size", "64", "--eval-every", "5", "--eval-iters", "2",
                "--log-every", "5", "--save-every", "5", "--device", "cpu", "--seed", "1", *extra]

    def run_script(self, *extra, steps=10, expect=0, batch=8):
        type(self).runs += 1
        out = Path(self.tmp.name) / f"run{self.runs}"
        proc = subprocess.run(self.command(out, *extra, steps=steps, batch=batch),
                              capture_output=True, text=True, timeout=600)
        if proc.returncode != expect:
            self.fail(f"exit {proc.returncode}, expected {expect}\nSTDOUT:\n{proc.stdout[-2000:]}"
                      f"\nSTDERR:\n{proc.stderr[-3000:]}")
        return out, proc

    @staticmethod
    def run_json(out):
        return json.loads((out / "run.json").read_text(encoding="utf-8"))

    def assert_source_losses(self, record, replayed=True):
        splits = ("train", "val") if replayed else ("val",)
        for when in ("before", "after"):
            self.assertEqual(set(record["source_losses"][when]), set(splits))
            for split in splits:
                value = record["source_losses"][when][split]
                self.assertIsInstance(value, float)
                self.assertLess(value, 1e6)
        self.assertEqual(record["identities"]["source_validation"]["sha256"], sha(self.validation))
        self.assertEqual(record["identities"]["source_validation"]["eval_seed"], train.EVAL_SEED)
        self.assertEqual(record["identities"]["source_validation"]["windows"], 2 * 8)

    def test_rows_per_batch_are_exact(self):
        self.assertEqual(continuing.replay_rows(8, 0.25), 2)
        self.assertEqual(continuing.replay_rows(4, 0.25), 1)
        self.assertEqual(continuing.replay_rows(8, 0.5), 4)
        for batch, frac in ((2, 0.25), (8, 1.0), (8, 0.0), (8, 1.5), (8, -0.25)):
            with self.assertRaises(ValueError):
                continuing.replay_rows(batch, frac)

    def test_a_mixed_batch_is_the_target_rows_then_the_replay_rows(self):
        target = (torch.arange(12).view(6, 2), torch.arange(12).view(6, 2) + 100)
        replay = (torch.arange(4).view(2, 2) + 1000, torch.arange(4).view(2, 2) + 2000)
        x, y = continuing.mix_batch(target, replay)
        self.assertEqual(x.shape, (8, 2))
        self.assertTrue(torch.equal(x[:6], target[0]) and torch.equal(y[:6], target[1]))
        self.assertTrue(torch.equal(x[6:], replay[0]) and torch.equal(y[6:], replay[1]))
        with self.assertRaises(ValueError):
            continuing.mix_batch(target, (torch.zeros(2, 3, dtype=torch.long), torch.zeros(2, 3, dtype=torch.long)))

    def test_windows_path_records_the_mix_and_the_source_losses(self):
        out, proc = self.run_script("--replay-data", str(self.replay), "--replay-frac", "0.25")
        record = self.run_json(out)
        self.assertEqual(record["status"], "complete")
        replay = record["identities"]["replay"]
        self.assertEqual(replay["frac"], 0.25)
        self.assertEqual(replay["rows_per_batch"], 2)
        self.assertEqual(replay["target_rows_per_batch"], 6)
        self.assertEqual(replay["row_share"], 0.25)
        self.assertEqual(replay["token_share_estimate"], 0.25)   # every row is a full window
        self.assertEqual(replay["sha256"], sha(self.replay))
        self.assertEqual(replay["kind"], "windows")
        self.assertGreater(replay["train_tokens"], 64)
        self.assertEqual(record["identities"]["batches"]["kind"], "windows")
        self.assert_source_losses(record)
        self.assertIn('"replay"', proc.stdout)

    def test_doc_batches_path_records_the_mix_and_the_token_share(self):
        out, _ = self.run_script("--replay-data", str(self.replay), "--replay-frac", "0.25", "--doc-batches")
        record = self.run_json(out)
        batches = record["identities"]["batches"]
        self.assertEqual(batches["kind"], "documents")
        replay = record["identities"]["replay"]
        self.assertEqual(replay["rows_per_batch"], 2)
        self.assertEqual(replay["target_rows_per_batch"], 6)
        # Target rows are padded, so two full replay windows hold at least a quarter
        # of the loss and usually more; the record says how much.
        expected = 2 * 64 / (2 * 64 + 6 * batches["target_tokens"] / batches["documents"])
        self.assertAlmostEqual(replay["token_share_estimate"], expected, places=6)
        self.assertGreaterEqual(replay["token_share_estimate"], 0.25)
        self.assertLess(replay["token_share_estimate"], 1.0)
        rows = [json.loads(line) for line in (out / "metrics.jsonl").read_text().splitlines()]
        self.assertTrue(all("epoch" in row for row in rows))
        self.assert_source_losses(record)

    def test_source_validation_alone_measures_forgetting_without_replay(self):
        out, _ = self.run_script("--source-validation", str(self.validation))
        record = self.run_json(out)
        self.assertIsNone(record["identities"]["replay"])
        self.assert_source_losses(record, replayed=False)
        plain, _ = self.run_script()
        self.assertIsNone(self.run_json(plain)["identities"]["replay"])
        self.assertIsNone(self.run_json(plain)["identities"]["source_validation"])
        self.assertNotIn("source_losses", self.run_json(plain))

    def test_refusals_are_loud(self):
        _, proc = self.run_script("--replay-data", str(self.replay), expect=2)
        self.assertIn("--replay-frac", proc.stderr)
        _, proc = self.run_script("--replay-frac", "0.25", expect=2)
        self.assertIn("--replay-data", proc.stderr)
        _, proc = self.run_script("--replay-data", str(self.replay), "--replay-frac", "0.25", batch=2, expect=1)
        self.assertIn("--replay-frac", proc.stderr)
        self.assertIn("0 rows", proc.stderr)
        lonely = Path(self.tmp.name) / "lonely.txt"
        lonely.write_text(self.replay.read_text(), encoding="utf-8")
        _, proc = self.run_script("--replay-data", str(lonely), "--replay-frac", "0.25", expect=1)
        self.assertIn("validation.txt", proc.stderr)

    def test_replay_naming_a_held_out_id_is_refused(self):
        leaky = Path(self.tmp.name) / "leaky.txt"
        leaky.write_text(self.replay.read_text() + "\n\ntask mbpp_999999__solve\n{ r := 0; }\n", encoding="utf-8")
        _, proc = self.run_script("--replay-data", str(leaky), "--replay-frac", "0.25",
                                  "--source-validation", str(self.validation), expect=1)
        self.assertIn("replay", proc.stderr)
        self.assertIn("999999", proc.stderr)

    def test_resume_refuses_a_changed_replay(self):
        out, _ = self.run_script("--replay-data", str(self.replay), "--replay-frac", "0.25", steps=5)
        proc = subprocess.run(self.command(out, "--replay-data", str(self.replay), "--replay-frac", "0.5",
                                           "--resume", steps=10), capture_output=True, text=True, timeout=600)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("replay", proc.stderr)
        proc = subprocess.run(self.command(out, "--replay-data", str(self.replay), "--replay-frac", "0.25",
                                           "--resume", steps=10), capture_output=True, text=True, timeout=600)
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        self.assertEqual(self.run_json(out)["steps_run"], 5)


if __name__ == "__main__":
    unittest.main()
