"""continue_from_checkpoint.py after r12 blockers A7, determinism and section C.

Each test runs the script as a subprocess on a two-layer, width-32 model with a
character tokenizer, so a run takes seconds on a CPU. Needs torch: run on the
lab, CPU only.
"""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import torch  # noqa: E402

import data  # noqa: E402
from model import GPT, GPTConfig  # noqa: E402

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "continue_from_checkpoint.py"


def corpus(n=48):
    # "fold": with these 48 documents the default split seed holds out 6 of them,
    # 12.2% of the characters, above the 8% floor the trainer refuses under.
    return "\n\n".join(f"Problem: fold the number {i}\nSignature: f{i}(int) -> int\n"
                       + ("r := r + %d;\n" % i) * (1 + (i * 37) % 7) + "}" for i in range(n)) + "\n"


def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class ContinueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.text = corpus()
        cls.data = root / "corpus.txt"
        cls.data.write_text(cls.text, encoding="utf-8")
        cls.split = root / "split.json"
        cls.split.write_text(json.dumps({"eval_ids": [999999]}), encoding="utf-8")
        tok = data.CharTokenizer.from_text(cls.text)
        cls.init = root / "init"
        cls.init.mkdir()
        tok.save(cls.init / "tokenizer.json")
        cfg = GPTConfig(vocab_size=tok.vocab_size, block_size=64, n_layer=2, n_head=2, n_embd=32)
        torch.manual_seed(0)
        model = GPT(cfg)
        torch.save({"model": model.state_dict(), "config": asdict(cfg),
                    "tokenizer_fingerprint": data.tokenizer_fingerprint(tok)}, cls.init / "ckpt.pt")
        cls.runs = 0

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_script(self, *extra, steps=10, expect=0, seed=1):
        type(self).runs += 1
        out = Path(self.tmp.name) / f"run{self.runs}"
        cmd = [sys.executable, str(SCRIPT), "--init", str(self.init), "--data", str(self.data),
               "--split", str(self.split), "--out", str(out), "--steps", str(steps),
               "--batch-size", "4", "--block-size", "64", "--eval-every", "5", "--eval-iters", "2",
               "--log-every", "5", "--save-every", "5", "--device", "cpu", "--seed", str(seed),
               *extra]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if proc.returncode != expect:
            self.fail(f"exit {proc.returncode}, expected {expect}\nSTDOUT:\n{proc.stdout[-2000:]}"
                      f"\nSTDERR:\n{proc.stderr[-3000:]}")
        return out, proc

    @staticmethod
    def run_json(out):
        return json.loads((out / "run.json").read_text(encoding="utf-8"))

    @staticmethod
    def weights(out, name="ckpt.pt"):
        return torch.load(out / name, map_location="cpu", weights_only=True)["model"]

    def test_defaults_hash_split_with_its_own_seed_and_determinism_recorded(self):
        out, _ = self.run_script()
        r = self.run_json(out)
        ident = r["identities"]
        self.assertEqual(r["schema"], 2)
        self.assertEqual(r["status"], "complete")
        self.assertEqual(ident["split"]["by"], "hash")
        self.assertEqual(ident["split"]["seed"], 1337)
        self.assertEqual(ident["split_seed"], 1337)
        self.assertEqual(ident["seed"], 1)
        self.assertGreater(ident["split"]["val_documents"], 0)
        self.assertEqual(ident["batches"]["kind"], "windows")
        rep = ident["reproducibility"]
        self.assertFalse(rep["requested"])
        self.assertIn("use_deterministic_algorithms", rep)
        self.assertIn("cublas_workspace_config", rep)
        self.assertIn("torch", rep)
        self.weights(out)                                   # loads with weights_only=True

    def test_split_seed_fixes_the_holdout_across_training_seeds(self):
        a, _ = self.run_script(seed=1)
        b, _ = self.run_script(seed=2)
        ia, ib = self.run_json(a)["identities"], self.run_json(b)["identities"]
        self.assertEqual(ia["split"]["val_sha256"], ib["split"]["val_sha256"])
        self.assertEqual(ia["split"]["val_documents"], ib["split"]["val_documents"])
        self.assertFalse(torch.equal(self.weights(a)["lm_head.weight"], self.weights(b)["lm_head.weight"]))

    def test_order_mode_reproduces_the_old_split(self):
        out, _ = self.run_script("--split-by", "order", "--split-seed", "5")
        ident = self.run_json(out)["identities"]
        self.assertEqual(ident["split"]["by"], "order")
        self.assertEqual(ident["split"]["val_sha256"], sha(data.group_split(self.text, 0.1, 5, by="order")[1]))

    def test_deterministic_runs_are_bit_identical_on_cpu(self):
        a, _ = self.run_script("--deterministic", seed=3)
        b, _ = self.run_script("--deterministic", seed=3)
        wa, wb = self.weights(a), self.weights(b)
        self.assertEqual(set(wa), set(wb))
        differing = [k for k in wa if not torch.equal(wa[k], wb[k])]
        self.assertEqual(differing, [])
        def records(out):     # every number but the wall clock
            return [{k: v for k, v in json.loads(line).items() if k != "seconds"}
                    for line in (out / "metrics.jsonl").read_text().splitlines()]
        self.assertEqual(records(a), records(b))
        rep = self.run_json(a)["identities"]["reproducibility"]
        self.assertTrue(rep["requested"] and rep["use_deterministic_algorithms"])
        self.assertEqual(rep["cublas_workspace_config"], ":4096:8")
        # Informational: whether the flag matters on this CPU. Printed, not asserted.
        c, _ = self.run_script(seed=3)
        d, _ = self.run_script(seed=3)
        wc, wd = self.weights(c), self.weights(d)
        plain = [k for k in wc if not torch.equal(wc[k], wd[k])]
        print(f"\n[r12] without --deterministic on CPU: {len(plain)} of {len(wc)} tensors differ", flush=True)

    def test_doc_batches(self):
        out, proc = self.run_script("--doc-batches", "--block-size", "24", "--eval-iters", "20")
        ident = self.run_json(out)["identities"]
        self.assertEqual(ident["batches"]["kind"], "documents")
        self.assertGreater(ident["batches"]["cut_documents"], 0)
        self.assertIn("cut_tokens", ident["batches"])
        self.assertEqual(ident["batches"]["order_seed"], 1)
        records = [json.loads(line) for line in (out / "metrics.jsonl").read_text().splitlines()]
        self.assertTrue(all(record["eval"] == "documents" for record in records))
        self.assertTrue(all(record["val"] == record["val"] and record["val"] < 1e6 for record in records))
        self.assertIn("doc_batches", proc.stdout)

    def test_keep_every_writes_weights_only_copies(self):
        out, _ = self.run_script("--keep-every", "5")
        for step in (5, 10):
            kept = torch.load(out / f"ckpt-step-{step}.pt", map_location="cpu", weights_only=True)
            self.assertNotIn("optimizer", kept)
            self.assertEqual(kept["step"], step)
            self.assertIn("config", kept)
        final = self.weights(out)
        last = self.weights(out, "ckpt-step-10.pt")
        self.assertEqual([k for k in final if not torch.equal(final[k], last[k])], [])
        self.assertEqual([k["step"] for k in self.run_json(out)["kept"]], [5, 10])
        self.assertTrue((out / "tokenizer.json").exists())

    def test_resume_refuses_a_changed_split_seed(self):
        out, _ = self.run_script("--keep-every", "5", steps=5)
        # --allow-short-holdout so that a short holdout at seed 99 cannot be the
        # refusal that fires first; the split-seed check is the one under test.
        cmd_extra = ["--resume", "--split-seed", "99", "--allow-short-holdout"]
        proc = subprocess.run([sys.executable, str(SCRIPT), "--init", str(self.init), "--data", str(self.data),
                               "--split", str(self.split), "--out", str(out), "--steps", "10",
                               "--batch-size", "4", "--block-size", "64", "--eval-every", "5",
                               "--eval-iters", "2", "--log-every", "5", "--save-every", "5",
                               "--device", "cpu", "--seed", "1", *cmd_extra],
                              capture_output=True, text=True, timeout=600)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("split_seed", proc.stderr)

    def test_resume_continues_the_same_run(self):
        out, _ = self.run_script("--keep-every", "5", steps=5)
        proc = subprocess.run([sys.executable, str(SCRIPT), "--init", str(self.init), "--data", str(self.data),
                               "--split", str(self.split), "--out", str(out), "--steps", "10",
                               "--batch-size", "4", "--block-size", "64", "--eval-every", "5",
                               "--eval-iters", "2", "--log-every", "5", "--save-every", "5",
                               "--device", "cpu", "--seed", "1", "--keep-every", "5", "--resume"],
                              capture_output=True, text=True, timeout=600)
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        r = self.run_json(out)
        self.assertEqual(r["steps_run"], 5)
        self.assertEqual([k["step"] for k in r["kept"]], [5, 10])

    def test_a_short_holdout_is_refused_by_name(self):
        # A split seed that holds out nothing on a three-document corpus.
        small = Path(self.tmp.name) / "small.txt"
        docs = data.documents(self.text)[:3]
        small.write_text("\n\n".join(docs) + "\n", encoding="utf-8")
        seed = next(s for s in range(1, 200) if not any(data.hash_holdout(d, s, 0.1) for d in docs))
        proc = subprocess.run([sys.executable, str(SCRIPT), "--init", str(self.init), "--data", str(small),
                               "--split", str(self.split), "--out", str(Path(self.tmp.name) / "short"),
                               "--steps", "2", "--batch-size", "2", "--block-size", "16", "--device", "cpu",
                               "--split-seed", str(seed)], capture_output=True, text=True, timeout=600)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("--split-seed", proc.stderr)


if __name__ == "__main__":
    unittest.main()
