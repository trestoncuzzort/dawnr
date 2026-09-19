"""Lab tests for the factorial trainer: identical arms, honest masks, resume."""
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import torch

from data import CharTokenizer, tokenizer_fingerprint
from model import GPT, GPTConfig
import train_factorial as factorial

HERE = Path(__file__).resolve().parent
ROWS = [{"kind": "synthesis", "task_name": f"s{i}", "split": "train",
         "prompt": f"synthesize\ntask s{i}(x: int)\n{{\n", "completion": "  r := x;\n}\n"}
        for i in range(8)] + [
        {"kind": "execution", "task_name": f"e{i}", "split": "train",
         "prompt": f"execute x = {i}\ntask s0(x: int)\ntrace\n",
         "parts": [[f"enter 0 | r=? x={i}\nexit 0 | r={i}\n", "execution"],
                   [f"output r = {i}\n", "answer"]]} for i in range(8)]


def make_dataset(directory):
    out = Path(directory) / "dataset"
    out.mkdir()
    with (out / "train.jsonl").open("w") as stream:
        for row in ROWS:
            stream.write(json.dumps(row, sort_keys=True) + "\n")
    (out / "manifest.json").write_text(json.dumps(
        {"files": {"train.jsonl": "test"}, "seed": 1337}) + "\n")
    return out


def make_init(directory, tokenizer):
    out = Path(directory) / "init"
    out.mkdir()
    config = GPTConfig(vocab_size=tokenizer.vocab_size, block_size=128, n_layer=2,
                       n_head=2, n_embd=32, dropout=0.0)
    model = GPT(config)
    torch.save({"model": model.state_dict(), "config": asdict(config),
                "tokenizer_fingerprint": tokenizer_fingerprint(tokenizer)}, out / "ckpt.pt")
    tokenizer.save(out / "tokenizer.json")
    return out


def run(dataset, init, out, arm, *extra):
    command = [sys.executable, str(HERE / "train_factorial.py"), "--dataset", str(dataset),
               "--init", str(init), "--out", str(out), "--arm", arm, "--seed", "7",
               "--updates", "4", "--batch-size", "4", "--block-size", "128",
               "--device", "cpu", "--log-every", "1", "--save-every", "2", *extra]
    result = subprocess.run(command, capture_output=True, text=True, cwd=HERE)
    if result.returncode:
        raise AssertionError(result.stderr[-2000:])
    return json.loads((Path(out) / "run.json").read_text())


class FactorialTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        text = "".join(row["prompt"] + row.get("completion", "") +
                       "".join(part for part, _ in row.get("parts", [])) for row in ROWS)
        self.tokenizer = CharTokenizer.from_text(text)
        self.dataset = make_dataset(self.directory.name)
        self.init = make_init(self.directory.name, self.tokenizer)

    def arm(self, name, *extra):
        out = Path(self.directory.name) / name
        return run(self.dataset, self.init, out, name, *extra), out

    def test_every_arm_sees_the_same_examples_in_the_same_order(self):
        orders, answers = set(), set()
        for name in sorted(factorial.ARMS):
            report, _ = self.arm(name)
            orders.add(report["identities"]["example_order_sha256"])
            answers.add(report["accounting"]["answer_tokens"])
        self.assertEqual(len(orders), 1)
        self.assertEqual(len(answers), 1)

    def test_only_the_execution_arms_supervise_intermediate_tokens(self):
        for name in sorted(factorial.ARMS):
            report, _ = self.arm(name)
            present = report["accounting"]["execution_tokens_present"]
            supervised = report["accounting"]["execution_tokens_supervised"]
            self.assertGreater(present, 0)
            self.assertEqual(supervised, present if factorial.ARMS[name][1] else 0)

    def test_the_latent_arms_add_auxiliary_parameters_and_losses(self):
        baseline, _ = self.arm("baseline")
        latent, _ = self.arm("latent")
        self.assertEqual(baseline["identities"]["parameters"]["auxiliary"], 0)
        self.assertGreater(latent["identities"]["parameters"]["auxiliary"], 0)
        self.assertEqual(baseline["identities"]["parameters"]["backbone"],
                         latent["identities"]["parameters"]["backbone"])
        self.assertIn("regression", latent["final_losses"])
        self.assertNotIn("regression", baseline["final_losses"])

    def test_resume_reproduces_an_uninterrupted_run(self):
        whole, whole_out = self.arm("combined")
        part = Path(self.directory.name) / "resumed"
        run(self.dataset, self.init, part, "combined", "--dry-run", "2")
        resumed = run(self.dataset, self.init, part, "combined", "--resume")
        self.assertEqual(resumed["accounting"]["updates"], whole["accounting"]["updates"])
        self.assertEqual(resumed["accounting"]["answer_tokens"],
                         whole["accounting"]["answer_tokens"])
        one = torch.load(whole_out / "state.pt", map_location="cpu", weights_only=False)
        two = torch.load(part / "state.pt", map_location="cpu", weights_only=False)
        for key, tensor in one["wrapper"].items():
            self.assertTrue(torch.equal(tensor, two["wrapper"][key]), key)

    def test_resume_refuses_a_different_arm(self):
        out = Path(self.directory.name) / "mixed"
        run(self.dataset, self.init, out, "baseline", "--dry-run", "2")
        with self.assertRaises(AssertionError):
            run(self.dataset, self.init, out, "combined", "--resume")

    def test_the_export_is_core_only_and_loads_for_inference(self):
        _, out = self.arm("combined")
        exported = torch.load(out / "ckpt.pt", map_location="cpu", weights_only=True)
        self.assertNotIn("optimizer", exported)
        self.assertFalse([key for key in exported["model"] if key.startswith("auxiliary")])
        from checkpoint import load_checkpoint
        model, tokenizer, config = load_checkpoint(out, device="cpu")
        self.assertEqual(tokenizer.vocab_size, config.vocab_size)
        with torch.no_grad():
            logits, _ = model(torch.zeros((1, 4), dtype=torch.long))
        self.assertEqual(logits.shape[-1], config.vocab_size)


if __name__ == "__main__":
    unittest.main()
