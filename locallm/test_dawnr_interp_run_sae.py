"""dawnr_interp.run_sae: the command line that wires activations -> sae -> browser ->
spec_probe together. What must hold: given a real (if tiny) checkpoint directory and
a corpus file, main() returns success and writes all four promised output files,
with run.json actually describing the run that produced them. The component pieces
have their own focused tests; this is the one place that exercises the CLI's
argument parsing and file I/O together. Needs torch; CPU only, a couple of seconds.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import torch  # noqa: E402

import data  # noqa: E402
from model import GPT, GPTConfig  # noqa: E402

from dawnr_interp.run_sae import main  # noqa: E402

CORPUS = "\n\n".join(f"""task f{i}(x: int) returns (y: int)
  requires x >= 0
  ensures y >= x
{{
  y := x + {i};
}}""" for i in range(15))


def write_tiny_checkpoint(directory: Path) -> Path:
    tok = data.CharTokenizer.from_text(CORPUS)
    cfg = GPTConfig(vocab_size=tok.vocab_size, block_size=32, n_layer=2, n_head=2, n_embd=8, dropout=0.0)
    torch.manual_seed(0)
    model = GPT(cfg)
    out = directory / "ckpt"
    out.mkdir()
    torch.save({"model": model.state_dict(), "config": cfg.__dict__}, out / "ckpt.pt")
    tok.save(out / "tokenizer.json")
    return out


class RunSAEMainTest(unittest.TestCase):
    def test_writes_every_promised_output_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            checkpoint_dir = write_tiny_checkpoint(tmp_path)
            corpus_path = tmp_path / "corpus.txt"
            corpus_path.write_text(CORPUS, encoding="utf-8")
            out_dir = tmp_path / "out"

            rc = main([
                "--checkpoint", str(checkpoint_dir),
                "--corpus", str(corpus_path),
                "--out", str(out_dir),
                "--steps", "20", "--expansion", "2", "--device", "cpu",
            ])

            self.assertEqual(rc, 0)
            for name in ("spec-probe.md", "feature-browser.md", "sae.pt", "run.json"):
                self.assertTrue((out_dir / name).is_file(), name)

            run_info = json.loads((out_dir / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(run_info["steps"], 20)
            self.assertEqual(run_info["d_in"], 8)
            self.assertEqual(run_info["d_hidden"], 16)
            self.assertGreater(run_info["n_positions"], 0)

            saved = torch.load(out_dir / "sae.pt", map_location="cpu", weights_only=True)
            self.assertIn("state_dict", saved)
            self.assertEqual(saved["config"]["d_in"], 8)

            probe_text = (out_dir / "spec-probe.md").read_text(encoding="utf-8")
            self.assertIn("Specification vs. boilerplate probe", probe_text)

    def test_an_empty_corpus_is_refused_not_crashed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            checkpoint_dir = write_tiny_checkpoint(tmp_path)
            corpus_path = tmp_path / "empty.txt"
            corpus_path.write_text("", encoding="utf-8")
            rc = main(["--checkpoint", str(checkpoint_dir), "--corpus", str(corpus_path),
                      "--out", str(tmp_path / "out")])
            self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
