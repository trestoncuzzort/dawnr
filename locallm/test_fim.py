"""Fill-in-the-middle (fim.py; Bavarian et al., arXiv:2207.14255).

What must hold: the transform loses nothing (prefix + middle + suffix is the
document), the layouts are the paper's, no ordinary text can encode to a
sentinel in either tokenizer, fim_rate 0 is byte-identical to the batches
before FIM existed, validation is never transformed, old tokenizers and
checkpoints load as before, and a tiny CPU run trains with FIM on through both
entry points. The golden hashes were computed from data.py at the commit
before FIM was added. Needs torch; CPU only, seconds.
"""
import hashlib
import json
import os
import random
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import torch  # noqa: E402

import checkpoint  # noqa: E402
import data  # noqa: E402
import fim  # noqa: E402
import plain_generate  # noqa: E402
from model import GPT, GPTConfig  # noqa: E402

HERE = Path(__file__).resolve().parent

# The corpus the golden hashes below were computed on.
TEXT = "".join(f"Problem: task {i}\nSignature: f{i}(int) -> int\n" + ("  r := r + %d;\n" % i) * (1 + i % 4)
               + "  ensures r >= 0\n}" + ("\n\n" if i < 29 else "\n") for i in range(30))
GOLDEN_CHAR_FINGERPRINT = "92e10a8a396d7bbe53a9181d8f33d2c141c24c55f44920a1c8c0734e689efe30"
GOLDEN_DOC_BATCHES = "9cba348866757c7d780efe5190eda2dd111791b20a7803a281677f51f4afd23d"
GOLDEN_WINDOWS = "19e610b928c18f184adccfa9ff832e1f145205c6189106b97312cc18374e0140"

T_DOC = """task find(a: seq, key: int) returns (index: int)
  requires len(a) >= 0
  ensures -(1) <= index
  ensures index < len(a)
{
  index := 0;
  while index < len(a)
    invariant 0 <= index and index <= len(a)
    decreases len(a) - index
  {
    index := index + 1;
  }
}"""

CHAR = data.CharTokenizer.from_text(TEXT + T_DOC)
FIMCHAR = CHAR.with_sentinels(fim.SENTINELS)


def doc_batch_hash(tok, **kw):
    rows = data.DocumentBatches(data.documents(TEXT), tok, block_size=96, seed=7, **kw)
    h = hashlib.sha256()
    for step in range(12):
        x, y = rows.get_batch(step, 4)
        h.update(x.numpy().tobytes())
        h.update(y.numpy().tobytes())
    return h.hexdigest()


def bpe(text):
    try:
        return data.BPETokenizer.from_text(text, vocab_size=300)
    except RuntimeError:
        return None


class TransformTests(unittest.TestCase):
    def test_char_split_round_trips(self):
        rng = random.Random(0)
        for n in (0, 1, 2, 17, 300):
            doc = "".join(rng.choice("ab{};\n ") for _ in range(n))
            for _ in range(200):
                p, m, s = fim.char_split(doc, rng)
                self.assertEqual(p + m + s, doc)

    def test_char_split_is_a_third_each_in_expectation(self):
        rng, doc = random.Random(1), "x" * 999
        sums = [0, 0, 0]
        for _ in range(6000):
            for k, part in enumerate(fim.char_split(doc, rng)):
                sums[k] += len(part)
        for total in sums:
            self.assertAlmostEqual(total / 6000 / len(doc), 1 / 3, delta=0.02)

    def test_t_split_round_trips_and_its_units_are_whole_clauses(self):
        units = [T_DOC[a:b] for a, b in fim.t_units(T_DOC)]
        self.assertIn("requires len(a) >= 0", units)
        self.assertIn("ensures index < len(a)", units)
        self.assertIn("invariant 0 <= index and index <= len(a)", units)
        self.assertIn("index := index + 1;", units)
        self.assertNotIn("{", units)
        rng, whole = random.Random(2), 0
        for _ in range(400):
            p, m, s = fim.split(T_DOC, rng, "t")
            self.assertEqual(p + m + s, T_DOC)
            whole += m in units
        self.assertGreater(whole, 150)      # about half are whole units, the rest character spans

    def test_psm_and_spm_layouts_are_the_papers(self):
        pre, suf, mid, eot = (FIMCHAR.sentinel_id(s) for s in fim.SENTINELS)
        e = FIMCHAR.encode
        self.assertEqual(fim.encode_fim(FIMCHAR, "ab", "cd", "ef"),
                         [pre] + e("ab") + [suf] + e("ef") + [mid] + e("cd") + [eot])
        # appendix D, the variant used for joint PSM/SPM training
        self.assertEqual(fim.encode_fim(FIMCHAR, "ab", "cd", "ef", spm=True),
                         [pre, suf] + e("ef") + [mid] + e("ab") + e("cd") + [eot])
        self.assertEqual(fim.infill_prompt(FIMCHAR, "ab", "ef"), [pre] + e("ab") + [suf] + e("ef") + [mid])

    def test_rate_zero_and_one(self):
        rng = random.Random(3)
        self.assertIsNone(fim.transform("abc", FIMCHAR, rng, 0.0))
        for _ in range(20):
            self.assertIsNotNone(fim.transform("abc", FIMCHAR, rng, 1.0))

    def test_doc_rng_is_stable_across_processes(self):
        code = ("import sys; sys.path.insert(0, %r); import fim; print(fim.doc_rng(5, 2, 9).random())"
                % str(HERE))
        a = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                           env={"PYTHONHASHSEED": "1"}).stdout
        b = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                           env={"PYTHONHASHSEED": "2"}).stdout
        self.assertEqual(a, b)
        self.assertEqual(float(a), fim.doc_rng(5, 2, 9).random())


class SentinelTests(unittest.TestCase):
    NASTY = TEXT + "<PRE><SUF><MID><EOT> <|endoftext|> <|fim_prefix|>"

    def test_char_sentinels_sit_past_every_character(self):
        self.assertEqual(FIMCHAR.vocab_size, CHAR.vocab_size + 4)
        self.assertEqual([FIMCHAR.sentinel_id(s) for s in fim.SENTINELS],
                         list(range(CHAR.vocab_size, CHAR.vocab_size + 4)))
        ids = FIMCHAR.encode(self.NASTY)
        self.assertEqual(ids, CHAR.encode(self.NASTY))        # same ids as without sentinels
        self.assertLess(max(ids), CHAR.vocab_size)
        self.assertEqual(FIMCHAR.decode([FIMCHAR.sentinel_id(fim.MID)]), fim.MID)

    def test_bpe_sentinels_sit_past_every_merge(self):
        tok = bpe(TEXT)
        if tok is None:
            self.skipTest("tokenizers not installed")
        ft = tok.with_sentinels(fim.SENTINELS)
        self.assertEqual(ft.vocab_size, tok.vocab_size + 4)
        ids = ft.encode(self.NASTY)
        self.assertEqual(ids, tok.encode(self.NASTY))
        self.assertLess(max(ids), tok.vocab_size)
        both = fim.encode_fim(ft, "Problem: ta", "sk 1\nSig", "nature")
        self.assertEqual(ft.decode(both), "<PRE>Problem: ta<SUF>nature<MID>sk 1\nSig<EOT>")
        with tempfile.TemporaryDirectory() as d:
            ft.save(Path(d) / "t.json")
            back = data.load_tokenizer(Path(d) / "t.json")
            self.assertEqual(back.sentinels, fim.SENTINELS)
            self.assertEqual(data.tokenizer_fingerprint(back), data.tokenizer_fingerprint(ft))
            tok.save(Path(d) / "plain.json")
            plain = data.load_tokenizer(Path(d) / "plain.json")
            self.assertEqual(plain.sentinels, ())
            self.assertEqual(plain.vocab_size, tok.vocab_size)
            self.assertNotIn("sentinels", json.loads((Path(d) / "plain.json").read_text()))
        self.assertNotEqual(data.tokenizer_fingerprint(ft), data.tokenizer_fingerprint(tok))


class CompatibilityTests(unittest.TestCase):
    def test_fim_rate_zero_batches_are_byte_identical_to_before(self):
        tok = data.CharTokenizer.from_text(TEXT)
        self.assertEqual(doc_batch_hash(tok), GOLDEN_DOC_BATCHES)
        self.assertEqual(doc_batch_hash(tok, fim_rate=0.0), GOLDEN_DOC_BATCHES)
        # a sentinel-carrying tokenizer gives the same rows while FIM is off
        self.assertEqual(doc_batch_hash(tok.with_sentinels(fim.SENTINELS), fim_rate=0.0), GOLDEN_DOC_BATCHES)
        torch.manual_seed(3)
        c = data.Corpus(TEXT, tok, "cpu")
        h = hashlib.sha256()
        for _ in range(5):
            x, y = c.get_batch("train", 4, 32)
            h.update(x.numpy().tobytes())
            h.update(y.numpy().tobytes())
        self.assertEqual(h.hexdigest(), GOLDEN_WINDOWS)

    def test_old_character_tokenizer_file_loads_as_before(self):
        tok = data.CharTokenizer.from_text(TEXT)
        self.assertEqual(data.tokenizer_fingerprint(tok), GOLDEN_CHAR_FINGERPRINT)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "tokenizer.json"
            path.write_text(json.dumps(tok.chars, ensure_ascii=False), encoding="utf-8")   # the old format
            back = data.load_tokenizer(path)
            self.assertEqual(back.sentinels, ())
            self.assertEqual(back.vocab_size, len(tok.chars))
            self.assertEqual(data.tokenizer_fingerprint(back), GOLDEN_CHAR_FINGERPRINT)
            tok.save(path)                                      # and it still writes that format
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), tok.chars)

    def test_sentinel_tokenizer_round_trips_in_both_readers(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "tokenizer.json"
            FIMCHAR.save(path)
            back = data.load_tokenizer(path)
            self.assertEqual((back.chars, back.sentinels), (FIMCHAR.chars, fim.SENTINELS))
            self.assertEqual(data.tokenizer_fingerprint(back), data.tokenizer_fingerprint(FIMCHAR))
            self.assertNotEqual(data.tokenizer_fingerprint(back), data.tokenizer_fingerprint(CHAR))
            plain = plain_generate.CharTokens.load(path)            # the torch-free reader
            self.assertEqual(plain.vocab_size, FIMCHAR.vocab_size)
            ids = fim.encode_fim(FIMCHAR, "ab", "cd", "ef")
            self.assertEqual(plain.decode(ids), FIMCHAR.decode(ids))

    def test_old_checkpoint_loads(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            tok = data.CharTokenizer.from_text(TEXT)
            (out / "tokenizer.json").write_text(json.dumps(tok.chars, ensure_ascii=False), encoding="utf-8")
            cfg = GPTConfig(vocab_size=tok.vocab_size, block_size=32, n_layer=1, n_head=2, n_embd=16)
            torch.manual_seed(0)
            m = GPT(cfg)
            torch.save({"model": m.state_dict(), "config": asdict(cfg),
                        "tokenizer_fingerprint": GOLDEN_CHAR_FINGERPRINT}, out / "ckpt.pt")
            model, back, _ = checkpoint.load_checkpoint(out, device="cpu")
            self.assertEqual(back.vocab_size, tok.vocab_size)
            x = torch.tensor([tok.encode("Problem: task 1")])
            self.assertTrue(torch.equal(model(x)[0], m.eval()(x)[0]))


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.docs = data.documents(TEXT)

    def test_fim_rows_hold_the_whole_document_and_end_in_eot(self):
        rows = data.DocumentBatches(self.docs, FIMCHAR, block_size=128, seed=1, fim_rate=1.0)
        pre, suf, mid, eot = (FIMCHAR.sentinel_id(s) for s in fim.SENTINELS)
        seen = set()
        for step in range(rows.batches_per_epoch(5)):
            x, y = rows.get_batch(step, 5)
            for r in range(x.shape[0]):
                n = int((y[r] != data.IGNORE_INDEX).sum())
                ids = [int(x[r, 0])] + y[r, :n].tolist()
                self.assertEqual(ids[0], pre)
                self.assertEqual(ids[-1], eot)
                self.assertEqual(ids.count(mid), 1)
                if ids[1] == suf:                                  # SPM: suffix, then prefix+middle
                    k = ids.index(mid)
                    suffix, rest = FIMCHAR.decode(ids[2:k]), FIMCHAR.decode(ids[k + 1:-1])
                    body = rest + suffix
                else:
                    j, k = ids.index(suf), ids.index(mid)
                    body = (FIMCHAR.decode(ids[1:j]) + FIMCHAR.decode(ids[k + 1:-1])
                            + FIMCHAR.decode(ids[j + 1:k]))
                self.assertIn(body, [d.strip("\r\n") for d in self.docs])
                seen.add(body)
        self.assertEqual(len(seen), len(self.docs))          # one epoch covers every document once
        self.assertEqual(rows.fim_cut_rows, 0)

    def test_fim_batches_are_a_pure_function_of_seed_and_step_and_vary_by_epoch(self):
        a = data.DocumentBatches(self.docs, FIMCHAR, block_size=128, seed=4, fim_rate=0.5)
        b = data.DocumentBatches(self.docs, FIMCHAR, block_size=128, seed=4, fim_rate=0.5)
        for step in (9, 0, 3, 9):
            self.assertTrue(torch.equal(a.get_batch(step, 4)[0], b.get_batch(step, 4)[0]))
        per = a.batches_per_epoch(len(self.docs))
        e0 = a.get_batch(0, len(self.docs))[0]
        e1 = a.get_batch(per, len(self.docs))[0]
        self.assertFalse(torch.equal(e0.sort(0).values, e1.sort(0).values))

    def test_evaluation_rows_are_never_transformed(self):
        plain = data.DocumentBatches(self.docs, FIMCHAR, block_size=128, seed=4)
        fimmed = data.DocumentBatches(self.docs, FIMCHAR, block_size=128, seed=4, fim_rate=1.0)
        for (xa, ya), (xb, yb) in zip(plain.in_order(4), fimmed.in_order(4)):
            self.assertTrue(torch.equal(xa, xb) and torch.equal(ya, yb))

    def test_fim_refuses_a_tokenizer_without_sentinels(self):
        with self.assertRaises(ValueError):
            data.DocumentBatches(self.docs, CHAR, block_size=128, seed=0, fim_rate=0.5)
        with self.assertRaises(ValueError):
            data.FIMWindows(self.docs, CHAR, seed=0, fim_rate=0.5)

    def test_fim_windows_rebuild_each_epoch(self):
        w = data.FIMWindows(self.docs, FIMCHAR, seed=2, fim_rate=0.5)
        first = w.stream.clone()
        n = sum(1 for i in first.tolist() if i == FIMCHAR.sentinel_id(fim.EOT))
        self.assertGreater(n, 5)
        self.assertLess(n, len(self.docs) - 5)
        torch.manual_seed(0)
        while w.epoch == 0:
            x, y = w.get_batch(4, 32)
            self.assertEqual(x.shape, (4, 32))
            self.assertTrue(torch.equal(x[:, 1:], y[:, :-1]))
        self.assertFalse(torch.equal(first, w.stream))


class TrainingRunTests(unittest.TestCase):
    """Both entry points, end to end on a CPU with FIM on."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.data = root / "corpus.txt"
        text = "\n\n".join(f"Problem: fold the number {i}\nSignature: f{i}(int) -> int\n"
                           + ("r := r + %d;\n" % i) * (1 + (i * 37) % 7) + "}" for i in range(48)) + "\n"
        cls.data.write_text(text, encoding="utf-8")
        cls.split = root / "split.json"
        cls.split.write_text(json.dumps({"eval_ids": [999999]}), encoding="utf-8")
        tok = data.CharTokenizer.from_text(text)          # an old-style init: no sentinels
        cls.init = root / "init"
        cls.init.mkdir()
        tok.save(cls.init / "tokenizer.json")
        cfg = GPTConfig(vocab_size=tok.vocab_size, block_size=96, n_layer=2, n_head=2, n_embd=32)
        torch.manual_seed(0)
        cls.init_model = GPT(cfg)
        torch.save({"model": cls.init_model.state_dict(), "config": asdict(cfg),
                    "tokenizer_fingerprint": data.tokenizer_fingerprint(tok)}, cls.init / "ckpt.pt")
        cls.tok = tok

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_continue(self, name, *extra):
        out = Path(self.tmp.name) / name
        cmd = [sys.executable, str(HERE / "continue_from_checkpoint.py"), "--init", str(self.init),
               "--data", str(self.data), "--split", str(self.split), "--out", str(out), "--steps", "12",
               "--batch-size", "4", "--block-size", "96", "--eval-every", "6", "--eval-iters", "2",
               "--log-every", "6", "--save-every", "6", "--device", "cpu", "--lr", "1e-3", *extra]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        self.assertEqual(proc.returncode, 0, proc.stderr[-3000:])
        return out, json.loads((out / "run.json").read_text(encoding="utf-8"))

    def test_continue_with_fim_adds_sentinels_and_trains(self):
        for extra in (("--doc-batches",), ()):
            out, run = self.run_continue("c" + "".join(extra), "--fim-rate", "0.5", *extra)
            self.assertEqual(run["status"], "complete")
            self.assertEqual(run["identities"]["fim"]["rate"], 0.5)
            self.assertTrue(run["identities"]["fim"]["sentinels_added"])
            self.assertEqual(run["identities"]["config"]["vocab_size"], self.tok.vocab_size + 4)
            model, tok, _ = checkpoint.load_checkpoint(out, device="cpu")
            self.assertEqual(tok.sentinels, fim.SENTINELS)
            text, _ = fim.infill(model, tok, "Problem: fold", "\n}", max_new_tokens=8)
            self.assertIsInstance(text, str)

    def test_continue_without_fim_records_none(self):
        out, run = self.run_continue("plain", "--doc-batches")
        self.assertIsNone(run["identities"]["fim"])
        self.assertEqual((out / "tokenizer.json").read_bytes(), (self.init / "tokenizer.json").read_bytes())

    def test_added_sentinel_rows_leave_old_logits_unchanged(self):
        import continue_from_checkpoint as cfc
        cfg = GPTConfig(**asdict(self.init_model.config))
        m = GPT(cfg)
        m.load_state_dict(self.init_model.state_dict())
        m.eval()
        x = torch.tensor([self.tok.encode("Problem: fold the number 3")])
        before = m(x)[0]
        tok = cfc.add_fim_sentinels(m, cfg, self.tok, torch, fim.SENTINELS)
        after = m(x)[0]
        self.assertEqual(after.shape[-1], self.tok.vocab_size + 4)
        self.assertTrue(torch.allclose(after[..., :self.tok.vocab_size], before, atol=1e-6))
        self.assertEqual(tok.vocab_size, self.tok.vocab_size + 4)
        self.assertIs(m.transformer.wte.weight, m.lm_head.weight)

    def test_train_py_with_fim(self):
        out = Path(self.tmp.name) / "train"
        cmd = [sys.executable, str(HERE / "train.py"), "--data", str(self.data), "--out", str(out),
               "--steps", "8", "--batch-size", "4", "--block-size", "32", "--n-layer", "1", "--n-head", "2",
               "--n-embd", "16", "--eval-interval", "4", "--fim-rate", "0.5", "--no-early-stop"]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=self.tmp.name,
                              env={**os.environ, "CUDA_VISIBLE_DEVICES": "", "OMP_NUM_THREADS": "4",
                                   "LOCALLM_RUN_LOG": str(Path(self.tmp.name) / "r.jsonl")})
        self.assertEqual(proc.returncode, 0, proc.stderr[-3000:])
        self.assertIn("fill-in-the-middle: rate 0.5", proc.stdout)
        tok = data.load_tokenizer(out / "tokenizer.json")
        self.assertEqual(tok.sentinels, fim.SENTINELS)
        checkpoint.load_checkpoint(out, device="cpu")


if __name__ == "__main__":
    unittest.main()
