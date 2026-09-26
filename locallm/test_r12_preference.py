"""r12 W7: preference pairs against the recited attractors, DPOP in the continuation trainer.

data.PairBatches lays a pair out as the corpus document would be laid out;
continue_from_checkpoint.py --pairs is gated like --data, records every
setting, is bit-identical to a run without pairs under --pref-loss none, and
under --pref-loss dpop keeps the chosen side's log-probability at its
reference or above while the rejected side's falls (Smaug, arXiv:2402.13228).
Each trainer test runs the script as a subprocess on a two-layer, width-32
model with a character tokenizer. Needs torch: run on the lab, CPU only.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import torch  # noqa: E402

import continue_from_checkpoint as cfc  # noqa: E402
import data  # noqa: E402
import train as core_train  # noqa: E402
from model import GPT, GPTConfig  # noqa: E402

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "continue_from_checkpoint.py"


def corpus(n=48):
    # the same 48 "fold" documents test_r12_continue uses: the default split seed holds out 6
    return "\n\n".join(f"Problem: fold the number {i}\nSignature: f{i}(int) -> int\n"
                       + ("r := r + %d;\n" % i) * (1 + (i * 37) % 7) + "}" for i in range(n)) + "\n"


def pairs(n=8):
    """Chosen and rejected differ by one character and share everything after it: Smaug's low-edit-distance case.

    The programs use letters the corpus never writes (q, x, y, *, /), so the
    language-model loss on the corpus pushes both sides DOWN; the DPOP hinge
    has to hold the chosen side up against it.
    """
    out = []
    for i in range(n):
        out.append({"task_id": 1000 + i,
                    "prompt": f"Problem: scale the number {i}\nSignature: g{i}(int) -> int\n",
                    "chosen": "q := x * y;\n  q := q * %d;\n}" % (i + 2),
                    "rejected": "q := x / y;\n  q := q * %d;\n}" % (i + 2),
                    "provenance": {"synthetic": True}})
    return out


def pair_text(rows):
    return "".join(r["prompt"] + r["chosen"] + r["rejected"] for r in rows)


def fitted_model(cfg, text, tok, steps=300, lr=3e-3, seed=0):
    """A tiny model already fit to the corpus, the situation DPOP is measured in.

    Smaug and Iterative RPO both start from a model that has been supervised
    on the task (Smaug Section 3: "we typically run DPO after SFT"). From a
    random init the corpus loss lifts every shared character of both sides by
    more than the preference term separates them (measured here on 2026-09-25:
    chosen +9.1, rejected +5.1 nats after 30 steps), so the property "the
    rejected side falls below its reference" is not the one being tested.
    """
    torch.manual_seed(seed)
    model = GPT(cfg)
    corpus_rows = data.Corpus(text, tok, "cpu", val_frac=0.1, grouped=True, seed=1337, split_by="hash")
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
    model.train()
    for _ in range(steps):
        x, y = corpus_rows.get_batch("train", 8, cfg.block_size)
        _, loss = model(x, y)
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
    model.eval()
    return model


def preference_only(model_state, cfg, rows, tok, lam, steps=30, lr=1e-3, beta=0.3):
    """Train on the preference loss alone and return (chosen - reference, rejected - reference) per pair."""
    model = GPT(cfg)
    model.load_state_dict(model_state)
    batches = data.PairBatches(rows, tok, cfg.block_size, seed=0)
    reference = cfc.pair_logps(model, batches, 8, torch, data.IGNORE_INDEX)
    # the trainer's optimizer and its gradient clip: with a bare AdamW and no
    # clip, the hinge's one large gradient sets Adam's momentum for the next
    # twenty steps and lifts BOTH sides by 33 nats (measured 2026-09-25)
    optimizer = core_train.make_optimizer(model, lr)
    model.train()
    for step in range(steps):
        ix, xc, yc, xr, yr = batches.get_batch(step, 8)
        logits, _ = model(torch.cat([xc, xr]))
        logps = cfc.sequence_logps(logits, torch.cat([yc, yr]), torch, data.IGNORE_INDEX)
        loss, _ = cfc.dpop_loss(logps[:len(xc)], logps[len(xc):], reference[0][ix], reference[1][ix],
                                beta, lam, torch)
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
    chosen, rejected = cfc.pair_logps(model, batches, 8, torch, data.IGNORE_INDEX)
    return (chosen - reference[0]).tolist(), (rejected - reference[1]).tolist()


class PairBatchesTests(unittest.TestCase):
    def setUp(self):
        self.rows = pairs(3)
        self.tok = data.CharTokenizer.from_text(corpus() + pair_text(self.rows))

    def test_a_pair_row_is_the_corpus_row_with_the_head_masked(self):
        rows = data.PairBatches(self.rows, self.tok, block_size=96, seed=0)
        docs = data.DocumentBatches([r["prompt"] + r["chosen"] for r in self.rows], self.tok, 96, seed=0)
        prompt_len = len(self.tok.encode(self.rows[0]["prompt"]))
        self.assertTrue(torch.equal(rows.x_chosen, docs.x))
        self.assertTrue(torch.equal(rows.y_chosen[:, prompt_len - 1:], docs.y[:, prompt_len - 1:]))
        self.assertTrue((rows.y_chosen[:, :prompt_len - 1] == data.IGNORE_INDEX).all())
        self.assertEqual(int((rows.y_chosen[0] != data.IGNORE_INDEX).sum()),
                         len(self.tok.encode(self.rows[0]["chosen"] + data.DOC_END)))
        self.assertEqual(rows.record()["pairs"], 3)
        self.assertEqual(rows.chosen_tokens, rows.rejected_tokens)

    def test_a_pair_over_the_block_is_refused_by_name(self):
        with self.assertRaises(ValueError) as caught:
            data.PairBatches(self.rows, self.tok, block_size=16, seed=0)
        self.assertIn("task_id 1000", str(caught.exception))

    def test_an_empty_side_or_prompt_is_refused(self):
        for bad in ({**self.rows[0], "prompt": ""}, {**self.rows[0], "rejected": " "}):
            with self.assertRaises(ValueError):
                data.PairBatches([bad], self.tok, block_size=96, seed=0)

    def test_the_order_comes_from_its_own_generator(self):
        state = torch.get_rng_state()
        rows = data.PairBatches(self.rows, self.tok, block_size=96, seed=5)
        ix, *_ = rows.get_batch(0, 2)
        self.assertEqual(len(ix), 2)
        self.assertTrue(torch.equal(state, torch.get_rng_state()))
        again = data.PairBatches(self.rows, self.tok, block_size=96, seed=5)
        self.assertEqual(rows.order(0), again.order(0))


class LossTests(unittest.TestCase):
    def test_sequence_logps_sum_only_the_unmasked_targets(self):
        logits = torch.zeros(1, 4, 5)
        targets = torch.tensor([[data.IGNORE_INDEX, 1, 2, data.IGNORE_INDEX]])
        got = cfc.sequence_logps(logits, targets, torch, data.IGNORE_INDEX)
        self.assertAlmostEqual(float(got[0]), 2 * torch.log(torch.tensor(1 / 5)).item(), places=5)

    def test_dpop_is_dpo_while_the_chosen_side_holds_and_penalises_a_fall(self):
        pc, pr, rc, rr = torch.tensor([-10.0]), torch.tensor([-12.0]), torch.tensor([-10.0]), torch.tensor([-11.0])
        held, detail = cfc.dpop_loss(pc, pr, rc, rr, beta=0.3, lam=50.0, torch_module=torch)
        plain = -torch.nn.functional.logsigmoid(0.3 * ((pc - rc) - (pr - rr))).mean()
        self.assertAlmostEqual(float(held), float(plain), places=6)
        self.assertEqual(detail["hinge"], 0.0)
        self.assertEqual(detail["reward_accuracy"], 1.0)
        fallen, detail = cfc.dpop_loss(torch.tensor([-10.5]), pr, rc, rr, beta=0.3, lam=50.0, torch_module=torch)
        self.assertGreater(float(fallen), float(held))
        self.assertAlmostEqual(detail["hinge"], 0.5, places=6)

    def test_the_hinge_is_what_holds_the_chosen_side(self):
        """Preference loss alone, same fitted init, lambda 0 (plain DPO) against lambda 50 (DPOP).

        Asserted for DPOP: no chosen side ends below its reference and every
        rejected side ends below its own. Plain DPO's numbers are printed, not
        asserted: Smaug's failure (the tokens after the edit lose probability)
        is measured on trained LLMs, and a width-32 model need not show it.
        """
        rows = pairs()
        tok = data.CharTokenizer.from_text(corpus() + pair_text(rows))
        cfg = GPTConfig(vocab_size=tok.vocab_size, block_size=96, n_layer=2, n_head=2, n_embd=32)
        state = fitted_model(cfg, corpus(), tok).state_dict()
        torch.manual_seed(1)
        dpop_chosen, dpop_rejected = preference_only(state, cfg, rows, tok, lam=50.0)
        torch.manual_seed(1)
        dpo_chosen, dpo_rejected = preference_only(state, cfg, rows, tok, lam=0.0)
        print(f"\n[r12 W7] preference loss alone, 30 steps, chosen minus reference: DPOP min {min(dpop_chosen):.3f} "
              f"(rejected max {max(dpop_rejected):.3f}); plain DPO min {min(dpo_chosen):.3f} "
              f"(rejected max {max(dpo_rejected):.3f})", flush=True)
        self.assertGreaterEqual(min(dpop_chosen), -1e-3)
        self.assertLess(max(dpop_rejected), 0.0)


class TrainerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.text = corpus()
        cls.rows = pairs()
        cls.data = root / "corpus.txt"
        cls.data.write_text(cls.text, encoding="utf-8")
        cls.pairs = root / "pairs.jsonl"
        cls.pairs.write_text("".join(json.dumps(r) + "\n" for r in cls.rows), encoding="utf-8")
        cls.split = root / "split.json"
        cls.split.write_text(json.dumps({"eval_ids": [999999]}), encoding="utf-8")
        tok = data.CharTokenizer.from_text(cls.text + pair_text(cls.rows))
        cls.init = root / "init"
        cls.init.mkdir()
        tok.save(cls.init / "tokenizer.json")
        cfg = GPTConfig(vocab_size=tok.vocab_size, block_size=96, n_layer=2, n_head=2, n_embd=32)
        model = fitted_model(cfg, cls.text, tok)          # DPOP is measured after supervised fitting
        torch.save({"model": model.state_dict(), "config": asdict(cfg),
                    "tokenizer_fingerprint": data.tokenizer_fingerprint(tok)}, cls.init / "ckpt.pt")
        cls.runs = 0

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def command(self, out, *extra, steps=10, seed=1):
        return [sys.executable, str(SCRIPT), "--init", str(self.init), "--data", str(self.data),
                "--split", str(self.split), "--out", str(out), "--steps", str(steps),
                "--batch-size", "4", "--block-size", "96", "--eval-every", "5", "--eval-iters", "2",
                "--log-every", "5", "--save-every", "5", "--device", "cpu", "--seed", str(seed),
                "--deterministic", *extra]

    def run_script(self, *extra, steps=10, expect=0, seed=1):
        type(self).runs += 1
        out = Path(self.tmp.name) / f"run{self.runs}"
        proc = subprocess.run(self.command(out, *extra, steps=steps, seed=seed),
                              capture_output=True, text=True, timeout=900)
        if proc.returncode != expect:
            self.fail(f"exit {proc.returncode}, expected {expect}\nSTDOUT:\n{proc.stdout[-2000:]}"
                      f"\nSTDERR:\n{proc.stderr[-3000:]}")
        return out, proc

    @staticmethod
    def run_json(out):
        return json.loads((out / "run.json").read_text(encoding="utf-8"))

    @staticmethod
    def weights(out):
        return torch.load(out / "ckpt.pt", map_location="cpu", weights_only=True)["model"]

    @staticmethod
    def records(out):
        return [{k: v for k, v in json.loads(line).items() if k != "seconds"}
                for line in (out / "metrics.jsonl").read_text().splitlines()]

    def test_pairs_with_no_preference_loss_leave_the_run_bit_identical(self):
        plain, _ = self.run_script(seed=3)
        loaded, proc = self.run_script("--pairs", str(self.pairs), "--pref-loss", "none", seed=3)
        wa, wb = self.weights(plain), self.weights(loaded)
        self.assertEqual([k for k in wa if not torch.equal(wa[k], wb[k])], [])
        self.assertEqual(self.records(plain), self.records(loaded))
        record = self.run_json(loaded)["identities"]["pairs"]
        self.assertIsNone(self.run_json(plain)["identities"]["pairs"])
        self.assertEqual(record["loss"], "none")
        self.assertEqual(record["pairs"], len(self.rows))
        self.assertFalse(record["reference"]["scored"])
        self.assertEqual(record["reference"]["init_ckpt_sha256"], self.run_json(loaded)["identities"]["init_ckpt_sha256"])
        self.assertIn('"pairs"', proc.stdout)

    def test_dpop_keeps_the_chosen_side_at_its_reference_while_the_rejected_side_falls(self):
        """The property Smaug reports (their Figure 4), in the trainer, with the corpus loss on."""
        out, _ = self.run_script("--pairs", str(self.pairs), "--pref-loss", "dpop", "--pref-beta", "0.3",
                                 "--pref-lambda", "50", "--pair-batch-size", "4", "--lr", "1e-3",
                                 "--eval-every", "10", "--log-every", "10", steps=30)
        report = self.run_json(out)
        ident = report["identities"]["pairs"]
        self.assertEqual((ident["loss"], ident["beta"], ident["lambda"], ident["batch_size"]), ("dpop", 0.3, 50.0, 4))
        self.assertTrue(ident["reference"]["scored"])
        final = report["pairs_final"]
        chosen, ref_c = final["chosen_logp"], final["chosen_ref_logp"]
        rejected, ref_r = final["rejected_logp"], final["rejected_ref_logp"]
        self.assertEqual(len(chosen), len(self.rows))
        print(f"\n[r12 W7] after 30 steps: chosen {sum(chosen) / len(chosen):.2f} (reference "
              f"{sum(ref_c) / len(ref_c):.2f}), rejected {sum(rejected) / len(rejected):.2f} (reference "
              f"{sum(ref_r) / len(ref_r):.2f}); per-pair chosen minus reference "
              f"{[round(c - r, 3) for c, r in zip(chosen, ref_c)]}", flush=True)
        for c, r in zip(chosen, ref_c):
            self.assertGreaterEqual(c, r - 1e-3, "a chosen side fell below its reference under DPOP")
        for c, r in zip(rejected, ref_r):
            self.assertLess(c, r, "a rejected side did not fall below its reference")
        evals = [rec for rec in self.records(out) if "pairs_chosen_logp" in rec]
        self.assertEqual([rec["step"] for rec in evals], [10, 20, 30])
        self.assertEqual(evals[-1]["pairs_reward_accuracy"], 1.0)
        self.assertGreater(evals[-1]["pairs_margin"], 0.0)
        self.assertEqual(evals[-1]["pairs_chosen_below_reference"], 0.0)
        self.assertIn("pref_step_loss", evals[-1])
        self.assertIn("lm_step_loss", evals[-1])

    def test_dpop_without_pairs_is_refused(self):
        _, proc = self.run_script("--pref-loss", "dpop", expect=1)
        self.assertIn("--pairs", proc.stderr)

    def test_a_pair_naming_a_held_out_id_is_refused_by_name(self):
        bad = Path(self.tmp.name) / "bad-pairs.jsonl"
        rows = pairs(2)
        rows[1]["task_id"] = 999999
        bad.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        _, proc = self.run_script("--pairs", str(bad), "--pref-loss", "dpop", expect=1)
        self.assertIn("999999", proc.stderr)
        self.assertIn(":2:", proc.stderr)

    def test_a_pair_whose_program_names_a_held_out_alias_is_refused(self):
        bad = Path(self.tmp.name) / "alias-pairs.jsonl"
        rows = pairs(1)
        rows[0]["rejected"] = "q := x / y;\n}  // mbpp_999999__leak"
        bad.write_text(json.dumps(rows[0]) + "\n", encoding="utf-8")
        _, proc = self.run_script("--pairs", str(bad), "--pref-loss", "none", expect=1)
        self.assertIn("999999", proc.stderr)

    def test_a_dpop_run_resumes_against_the_same_reference(self):
        out, _ = self.run_script("--pairs", str(self.pairs), "--pref-loss", "dpop", "--lr", "1e-3", steps=5)
        first = self.run_json(out)["pairs_final"]["chosen_ref_logp"]
        proc = subprocess.run(self.command(out, "--pairs", str(self.pairs), "--pref-loss", "dpop", "--lr", "1e-3",
                                           "--resume", steps=10), capture_output=True, text=True, timeout=900)
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        report = self.run_json(out)
        self.assertEqual(report["steps_run"], 5)
        self.assertEqual(report["pairs_final"]["chosen_ref_logp"], first)
        changed = subprocess.run(self.command(out, "--pairs", str(self.pairs), "--pref-loss", "dpop", "--lr", "1e-3",
                                              "--pref-lambda", "5", "--resume", steps=15),
                                 capture_output=True, text=True, timeout=900)
        self.assertNotEqual(changed.returncode, 0)
        self.assertIn("pairs.lambda", changed.stderr)


if __name__ == "__main__":
    unittest.main()
