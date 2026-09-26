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


def fold_documents(n=48):
    # the same 48 "fold" documents test_r12_continue uses: the default split seed holds out 6
    return [f"Problem: fold the number {i}\nSignature: f{i}(int) -> int\n"
            + ("r := r + %d;\n" % i) * (1 + (i * 37) % 7) + "}" for i in range(n)]


def corpus(rows=(), n=48):
    """The fold documents plus each pair's chosen document, laid out as t/loop_locallm.py corpus writes them.

    A corpus document is head + program + newline, with a blank line between
    documents, so a pair's prompt + chosen is a substring of the corpus text:
    the identity load_pairs enforces, and the one the r12 data has (the three
    real pairs of 2026-09-25 against corpus-r8.txt, checked on the lab).
    """
    docs = fold_documents(n) + [r["prompt"] + r["chosen"] for r in rows]
    return "\n\n".join(d + "\n" for d in docs) + "\n"


def pairs(n=8):
    """Chosen and rejected differ by one character and share everything after it: Smaug's low-edit-distance case.

    The programs use letters the fold documents never write (q, x, y, *, /).
    The chosen side is a corpus document, as in r12, so the language-model
    loss lifts it and every token the rejected side shares with it; the
    rejected side has to fall through the edit and the tokens after it, which
    is where Smaug reports plain DPO lowering the chosen side as well.
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
        policy_chosen, policy_rejected = cfc.pair_forward(model, xc, yc, xr, yr, torch, data.IGNORE_INDEX)
        loss, _ = cfc.dpop_loss(policy_chosen, policy_rejected, reference[0][ix], reference[1][ix], beta, lam, torch)
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
        rejected side ends below its own. Asserted for plain DPO: the chosen
        side FALLS, Smaug's failure. It did not show while the chosen programs
        were foreign to the corpus (the first fixture); with the chosen side a
        fitted corpus document and the rejected side one edit away, plain DPO
        took every chosen side down with the rejected one (min -84.5 nats
        against DPOP's +3.5, measured 2026-09-25 on the lab).
        """
        rows = pairs()
        tok = data.CharTokenizer.from_text(corpus(rows) + pair_text(rows))
        cfg = GPTConfig(vocab_size=tok.vocab_size, block_size=96, n_layer=2, n_head=2, n_embd=32)
        state = fitted_model(cfg, corpus(rows), tok).state_dict()
        torch.manual_seed(1)
        dpop_chosen, dpop_rejected = preference_only(state, cfg, rows, tok, lam=50.0)
        torch.manual_seed(1)
        dpo_chosen, dpo_rejected = preference_only(state, cfg, rows, tok, lam=0.0)
        print(f"\n[r12 W7] preference loss alone, 30 steps, chosen minus reference: DPOP min {min(dpop_chosen):.3f} "
              f"(rejected max {max(dpop_rejected):.3f}); plain DPO min {min(dpo_chosen):.3f}, max "
              f"{max(dpo_chosen):.3f} (rejected max {max(dpo_rejected):.3f})", flush=True)
        self.assertGreaterEqual(min(dpop_chosen), -1e-3)
        self.assertLess(max(dpop_rejected), 0.0)
        self.assertLess(max(dpo_chosen), 0.0, "plain DPO did not lower the chosen side: the fixture no longer "
                                              "shows Smaug's failure, so it cannot show the hinge preventing it")


class TrainerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.rows = pairs()
        cls.text = corpus(cls.rows)          # every chosen side is a corpus document, as load_pairs requires
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

    def pair_logps_of(self, out):
        """Every pair's log p(chosen), log p(rejected) under a finished run's weights, scored as the trainer scores them."""
        cfg = GPTConfig(**self.run_json(out)["identities"]["config"])
        model = GPT(cfg)
        model.load_state_dict(self.weights(out))
        batches = data.PairBatches(self.rows, data.load_tokenizer(self.init / "tokenizer.json"), cfg.block_size, seed=0)
        chosen, rejected = cfc.pair_logps(model, batches, 8, torch, data.IGNORE_INDEX)
        return chosen.tolist(), rejected.tolist()

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

    def dpop_property(self, dropout, strict):
        """The property Smaug reports (their Figure 4), in the trainer, with the corpus loss on.

        Asserted per pair from run.json's pairs_final and from the last
        evaluation in metrics.jsonl: every rejected side below its reference,
        the mean chosen log-probability at or above the reference mean, and no
        chosen side below its reference by more than the hinge's slack. Strict
        (dropout 0): none below at all. Otherwise the slack is margin / lambda:
        the hinge sits inside the log-sigmoid under beta (Smaug Eq. 3), so at
        a margin of 28 nats and lambda 50 the term does not bite until the
        deficit nears 0.5 nats. Returns the run directory and the evaluations.
        """
        out, _ = self.run_script("--pairs", str(self.pairs), "--pref-loss", "dpop", "--pref-beta", "0.3",
                                 "--pref-lambda", "50", "--pair-batch-size", "4", "--lr", "1e-3",
                                 "--eval-every", "10", "--log-every", "10", "--dropout", str(dropout), steps=30)
        report = self.run_json(out)
        ident = report["identities"]["pairs"]
        self.assertEqual((ident["loss"], ident["beta"], ident["lambda"], ident["batch_size"]), ("dpop", 0.3, 50.0, 4))
        self.assertTrue(ident["reference"]["scored"])
        self.assertEqual(ident["dropout"], 0.0)                  # the pair pass, whatever the recipe's dropout
        self.assertEqual(report["identities"]["dropout"], dropout)
        self.assertTrue(ident["chosen_in_corpus"])
        final = report["pairs_final"]
        chosen, ref_c = final["chosen_logp"], final["chosen_ref_logp"]
        rejected, ref_r = final["rejected_logp"], final["rejected_ref_logp"]
        self.assertEqual(len(chosen), len(self.rows))
        print(f"\n[r12 W7] dropout {dropout}, after 30 steps: chosen {sum(chosen) / len(chosen):.2f} (reference "
              f"{sum(ref_c) / len(ref_c):.2f}), rejected {sum(rejected) / len(rejected):.2f} (reference "
              f"{sum(ref_r) / len(ref_r):.2f}); per-pair chosen minus reference "
              f"{[round(c - r, 3) for c, r in zip(chosen, ref_c)]}; rejected minus reference "
              f"{[round(c - r, 3) for c, r in zip(rejected, ref_r)]}", flush=True)
        for c, r in zip(rejected, ref_r):
            self.assertLess(c, r, "a rejected side did not fall below its reference")
        for c, rc, r, rr in zip(chosen, ref_c, rejected, ref_r):
            margin = (c - rc) - (r - rr)
            slack = 1e-3 if strict else max(margin, 0.0) / 50.0
            self.assertGreaterEqual(c, rc - slack, f"a chosen side fell below its reference under DPOP by more "
                                                   f"than the hinge's slack {slack:.3f} (margin {margin:.2f})")
        self.assertGreaterEqual(sum(chosen) / len(chosen), sum(ref_c) / len(ref_c) - (1e-3 if strict else 0.0))
        evals = [rec for rec in self.records(out) if "pairs_chosen_logp" in rec]
        self.assertEqual([rec["step"] for rec in evals], [10, 20, 30])
        last = evals[-1]
        self.assertEqual(last["pairs_reward_accuracy"], 1.0)
        self.assertGreater(last["pairs_margin"], 0.0)
        self.assertLess(last["pairs_rejected_logp"], last["pairs_rejected_ref_logp"])
        self.assertGreaterEqual(last["pairs_chosen_logp"], last["pairs_chosen_ref_logp"])
        if strict:
            self.assertEqual(last["pairs_chosen_below_reference"], 0.0)
            self.assertEqual(last["pairs_chosen_deficit"], 0.0)
        # the mean deficit is under the mean slack, margin / lambda (pairs_margin carries beta)
        self.assertLessEqual(last["pairs_chosen_deficit"], last["pairs_margin"] / (0.3 * 50.0))
        self.assertIn("pref_step_loss", last)
        self.assertIn("lm_step_loss", last)
        return out, evals

    def test_dpop_keeps_the_chosen_side_at_its_reference_while_the_rejected_side_falls(self):
        self.dpop_property(dropout=0.0, strict=True)

    def test_dpop_holds_under_the_recipe_dropout(self):
        """--dropout 0.1, the r12 recipe's setting, which the pilot arm copies.

        Before the pair pass ran without dropout (review of 2026-09-25) this
        run lifted every rejected side 6.0 to 8.7 nats ABOVE its reference
        while pairs_chosen_below_reference read 0.0 and reward accuracy 1.0:
        both pilot criteria said success. The hinge was firing on the dropout
        deficit between the policy's train-mode pass and the reference's
        eval-mode score.

        Under dropout the language-model term alone pulls every chosen side
        6.7 to 8.9 nats BELOW its reference in these 30 steps (the control
        run here, --pref-loss none), so the reference-based property is also
        checked against that control: with the term on, every chosen side ends
        above the control's and every rejected side below it. That is what
        "the preference term does not lower the preferred sequence" means
        when the other term is noisy.
        """
        control, _ = self.run_script("--pairs", str(self.pairs), "--pref-loss", "none", "--lr", "1e-3",
                                     "--eval-every", "10", "--log-every", "10", "--dropout", "0.1", steps=30)
        out, evals = self.dpop_property(dropout=0.1, strict=False)
        chosen, rejected = self.pair_logps_of(out)
        control_chosen, control_rejected = self.pair_logps_of(control)
        ref_c = self.run_json(out)["pairs_final"]["chosen_ref_logp"]
        print(f"[r12 W7] dropout 0.1, control (no preference term) chosen minus reference "
              f"{[round(c - r, 3) for c, r in zip(control_chosen, ref_c)]}; DPOP minus control, chosen "
              f"{[round(a - b, 2) for a, b in zip(chosen, control_chosen)]}, rejected "
              f"{[round(a - b, 2) for a, b in zip(rejected, control_rejected)]}; pref_hinge at the logged steps "
              f"{[round(rec['pref_hinge'], 4) for rec in evals]}", flush=True)
        for a, b in zip(chosen, control_chosen):
            self.assertGreater(a, b, "the preference term lowered a chosen side relative to training without it")
        for a, b in zip(rejected, control_rejected):
            self.assertLess(a, b, "the preference term did not lower a rejected side relative to training without it")

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

    def test_a_pair_that_is_not_a_corpus_document_is_refused_by_line(self):
        """A head the corpus does not carry (built with --examples against a corpus built without), or a chosen
        program that is not the corpus's, is refused and named, under --pref-loss none as under dpop."""
        headed = Path(self.tmp.name) / "headed-pairs.jsonl"
        rows = pairs(2)
        rows[1]["prompt"] += "Example: g1(3) == 6\n"
        headed.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        _, proc = self.run_script("--pairs", str(headed), "--pref-loss", "none", expect=1)
        self.assertIn(":2:", proc.stderr)
        self.assertIn("head is not in", proc.stderr)
        self.assertIn("task_id 1001", proc.stderr)
        other = Path(self.tmp.name) / "other-positive-pairs.jsonl"
        rows = pairs(1)
        rows[0]["chosen"] = rows[0]["chosen"].replace("q * 2", "q * 3")
        other.write_text(json.dumps(rows[0]) + "\n", encoding="utf-8")
        _, proc = self.run_script("--pairs", str(other), "--pref-loss", "dpop", expect=1)
        self.assertIn(":1:", proc.stderr)
        self.assertIn("chosen program is not in", proc.stderr)

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
