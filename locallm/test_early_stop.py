"""Does training stop when it stops learning, and is the saved model the best one?

THE DEFECT. Neither trainer had a stopping rule and both saved the LAST weights:
FINDINGS-how-long-to-train.md measured that doubling 80,000 steps to 160,000
bought 0.0028 against a seed noise floor of 0.0052, and said the app "would
happily run all night". train.EarlyStopper is Lightning's EarlyStopping rule
(patience against min_delta, non-finite and divergence stops) plus Lightning's
ModelCheckpoint rule for which weights are kept (the strict lowest validation
loss). The first half of this file drives it with made-up loss sequences; the
second half trains a real, tiny model on the CPU through both entry points and
checks that the weights on disk score the best check, not the last.

Runs on the CPU with at most four threads, whatever the machine has.
"""
from __future__ import annotations

import math
import os
import pathlib
import random
import subprocess
import sys
import tempfile
import unittest

os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ.setdefault("OMP_NUM_THREADS", "4")

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import torch  # noqa: E402

torch.set_num_threads(4)

import runlog  # noqa: E402
from train import (EARLY_STOP_MIN_DELTA, EARLY_STOP_PATIENCE,  # noqa: E402
                   EarlyStopper, cpu_state_copy, estimate_loss, state_bytes)

D = 2.0 ** -8          # a min_delta that binary floating point holds exactly


def _drive(values, **kw):
    """Feed one check per value, at steps 0, 10, 20 ...; return (stopper, index
    of the check that stopped it or None)."""
    s = EarlyStopper(**kw)
    for i, v in enumerate(values):
        if s.update(i * 10, v):
            return s, i
    return s, None


# ---------------------------------------------------------------------------
# made-up sequences
# ---------------------------------------------------------------------------
def test_the_defaults_are_the_measured_ones():
    assert EARLY_STOP_MIN_DELTA == 0.005 and EARLY_STOP_PATIENCE == 5


def test_improves_then_plateaus_within_min_delta():
    """Falls fast, then wobbles inside noise: stops after exactly `patience`
    checks without a real drop, and keeps the lowest check, which is not the
    reference the patience was counted from."""
    vals = [3.0, 2.0, 1.5, 1.2, 1.199, 1.197, 1.201, 1.198, 1.203, 1.0]
    s, i = _drive(vals, min_delta=0.005, patience=5)
    assert i == 8, f"stopped at check {i}, expected the fifth flat one (8)"
    assert s.reason == "patience" and s.stopped_step == 80
    assert s.reference == 1.2 and s.reference_step == 30
    assert s.best_step == 50 and s.best_val == 1.197, (s.best_step, s.best_val)
    assert s.summary() == ("stopped at step 80: validation had not improved by more "
                           "than run-to-run noise (0.005) for 5 checks; saved the "
                           "weights from step 50")


def test_a_slow_steady_improvement_is_not_stopped():
    """Each check drops less than min_delta, but the drops add up against the
    reference, so a run that is still learning slowly keeps going."""
    vals = [2.0 - 0.002 * k for k in range(40)]
    s, i = _drive(vals, min_delta=0.005, patience=5)
    assert i is None, f"a steady 0.002-per-check improvement was stopped at {i}"
    assert s.best_step == 390


def test_an_improvement_of_exactly_min_delta_is_not_one():
    """Lightning's rule: `current + min_delta < best`, so a drop of exactly
    min_delta counts as no improvement. The values are exact in binary."""
    vals = [1.0] + [1.0 - D] * 5
    s, i = _drive(vals, min_delta=D, patience=5)
    assert i == 5 and s.reason == "patience"
    assert s.best_step == 10, "the first of the equal lows is the kept one"
    # One unit in the last place more than min_delta IS an improvement.
    vals = [1.0] + [math.nextafter(1.0 - D, 0.0)] + [1.0] * 4
    s, i = _drive(vals, min_delta=D, patience=5)
    assert i is None and s.reference_step == 10 and s.wait_count == 4


def test_nan_stops_at_once_and_keeps_the_last_finite_best():
    for bad in (float("nan"), float("inf")):
        s, i = _drive([3.0, 2.0, 2.5, bad, 1.0], patience=50)
        assert i == 3 and s.reason == "non_finite", (bad, i, s.reason)
        assert s.best_step == 10 and s.best_val == 2.0
        assert "stopped being a number" in s.summary()
        assert "saved the weights from step 10" in s.summary()


def test_nan_on_the_very_first_check_says_nothing_was_kept():
    s, i = _drive([float("nan")])
    assert i == 0 and s.best_step is None
    assert "no check had a usable score" in s.summary()


def test_divergence_stops_past_the_threshold_only_when_asked():
    s, i = _drive([3.0, 2.0, 6.0, 1.0], divergence_threshold=5.0, patience=50)
    assert i == 2 and s.reason == "divergence" and s.best_step == 10
    assert "past the divergence limit 5" in s.summary()
    s, i = _drive([3.0, 2.0, 6.0, 1.0], patience=50)
    assert i is None and s.best_step == 30, "no threshold, no divergence stop"
    s, i = _drive([3.0, 2.0, 5.0], divergence_threshold=5.0, patience=50)
    assert i is None, "equal to the threshold is not past it"


def test_a_training_loss_that_is_not_a_number_stops_the_run():
    s = EarlyStopper()
    s.update(0, 3.0)
    assert not s.training_loss_broke(5, 2.9)
    assert s.training_loss_broke(7, float("nan"))
    assert s.reason == "non_finite_train" and s.stopped_step == 7
    assert "training loss stopped being a number" in s.summary()


def test_early_stop_off_runs_the_length_but_still_keeps_the_best():
    vals = [3.0, 2.0, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6]
    s, i = _drive(vals, stop_early=False, patience=2)
    assert i is None and s.best_step == 10
    s.finish(70, "finished")
    assert s.summary() == ("ran the planned 70 steps; saved the weights from step "
                           "10, which scored best (the last check was worse)")


def test_an_unfair_split_keeps_the_last_weights_and_says_why():
    s, i = _drive([3.0, 2.0, 2.5], stop_early=False, keep_best=False)
    assert i is None and s.best_step == 20, "keep_best=False follows the latest check"
    s.finish(20, "finished")
    assert "no fair held-out part" in s.summary()
    assert s.record()["weights"] == "last"


def test_bad_settings_are_refused():
    for kw in ({"patience": 0}, {"patience": 2.5}, {"min_delta": -0.1},
               {"min_delta": float("nan")}):
        try:
            EarlyStopper(**kw)
        except ValueError:
            continue
        raise AssertionError(f"{kw} was accepted")


def test_state_round_trips_so_a_resume_can_continue_the_count():
    """Lightning's resume contract: a restored stopper continues exactly where
    the saved one was, and the state survives torch.load(weights_only=True)."""
    s, _ = _drive([3.0, 2.0, 2.001, 2.002], patience=5)
    state = s.state_dict()
    with tempfile.TemporaryDirectory() as d:
        torch.save({"training": s.record()}, pathlib.Path(d) / "x.pt")
        back = torch.load(pathlib.Path(d) / "x.pt", weights_only=True)
    assert back["training"]["early_stopping"] == state
    r = EarlyStopper()
    r.load_state_dict(back["training"]["early_stopping"])
    assert (r.wait_count, r.reference, r.patience) == (2, 2.0, 5)
    stops = [r.update(40 + 10 * k, 2.003) for k in range(3)]
    assert stops == [False, False, True], "the restored count did not continue"


def test_the_weight_copy_is_on_the_cpu_frozen_and_tied_once():
    from model import GPT, GPTConfig
    torch.manual_seed(0)
    m = GPT(GPTConfig(vocab_size=50, block_size=16, n_layer=1, n_head=2, n_embd=32))
    copy = cpu_state_copy(m)
    assert all(t.device.type == "cpu" for t in copy.values())
    assert copy["lm_head.weight"] is copy["transformer.wte.weight"], "tied weight copied twice"
    params = sum(p.numel() for p in m.parameters()) * 4
    assert state_bytes(copy) <= params + sum(b.numel() * 4 for b in m.buffers())
    before = copy["lm_head.weight"].clone()
    with torch.no_grad():
        for p in m.parameters():
            p.add_(1.0)
    assert torch.equal(copy["lm_head.weight"], before), "the copy moved with the model"


# ---------------------------------------------------------------------------
# a real run, on the CPU
# ---------------------------------------------------------------------------
def _letters_corpus(path: pathlib.Path) -> None:
    """Thirty documents of random letters. The model learns the letter
    frequencies within a hundred steps and then there is nothing left to learn
    about text it has not seen: validation goes flat and wobbles, which is the
    shape the stop exists for. Random, so the leakage scan finds no overlap and
    the 30 documents split cleanly."""
    rng = random.Random(0)
    docs = ["".join(rng.choice("abcdefghijklmnop ") for _ in range(rng.randint(200, 400)))
            for _ in range(30)]
    path.write_text("\n\n".join(docs), encoding="utf-8")


CFG = dict(n_layer=2, n_head=4, n_embd=128, block_size=64, dropout=0.0,
           steps=600, batch_size=16, lr=1e-2, eval_interval=20, seed=1337,
           device="cpu")


def _load_and_score(out: pathlib.Path, corpus, batch_size, block_size):
    from checkpoint import load_checkpoint
    model, tok, cfg = load_checkpoint(out, "cpu")
    return estimate_loss(model, corpus, batch_size, block_size), \
        torch.load(out / "ckpt.pt", map_location="cpu", weights_only=True)


def test_a_real_studio_run_stops_and_saves_the_best_weights():
    import queue
    import threading
    try:
        import studio
    except ModuleNotFoundError as exc:
        # tkinter is an optional stdlib package, absent on a stock python3
        # (see test_launchers.py) and on some CI Pythons. The command-line
        # path below covers the same stopping logic without it.
        if exc.name != "tkinter":
            raise
        raise unittest.SkipTest(str(exc))
    from data import CharTokenizer, Corpus
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        was = runlog.LOG
        runlog.LOG = d / "runs.jsonl"          # never the tracked log
        try:
            _letters_corpus(d / "corpus.txt")
            q = queue.Queue()
            w = studio.TrainWorker(dict(CFG, data=str(d / "corpus.txt"), out=str(d / "out")),
                                   q, threading.Event())
            w.run()
        finally:
            runlog.LOG = was
        msgs = []
        while not q.empty():
            msgs.append(q.get())
        errors = [p for k, p in msgs if k == "error"]
        assert not errors, errors[0]
        checks = [p for k, p in msgs if k == "metrics"]
        logs = "\n".join(p for k, p in msgs if k == "log")
        done = [p for k, p in msgs if k == "done"][0]
        rec = done["training"]
        assert rec["stop_reason"] == "patience", (rec["stop_reason"], logs[-400:])
        assert rec["stopped_step"] < CFG["steps"], "it ran the whole length"
        assert f"Stopped at step {rec['stopped_step']}: validation had not improved" in logs
        assert f"saved the weights from step {rec['saved_step']}" in logs

        text = (d / "corpus.txt").read_text(encoding="utf-8")
        corpus = Corpus(text, CharTokenizer.from_text(text), "cpu")
        got, ck = _load_and_score(d / "out", corpus, CFG["batch_size"], CFG["block_size"])
        vals = {m["step"]: m["val"] for m in checks}
        best_step = min(vals, key=vals.get)
        last_step = max(vals)
        assert rec["saved_step"] == best_step
        assert abs(got["val"] - vals[best_step]) < 1e-6, \
            f"saved weights score {got['val']}, the best check scored {vals[best_step]}"
        assert abs(got["val"] - vals[last_step]) > 1e-4, \
            "best and last checks are the same, so this run proves nothing"
        assert ck["training"]["why"] == rec["why"]
        assert ck["training"]["weights"] == "best validation"
        print(f"    studio run: best step {best_step} val {vals[best_step]:.4f}, "
              f"stopped at step {rec['stopped_step']}, last check step {last_step} "
              f"val {vals[last_step]:.4f}")


def test_a_real_command_line_run_stops_and_saves_the_best_weights():
    from data import CharTokenizer, Corpus
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        _letters_corpus(d / "corpus.txt")
        env = dict(os.environ, CUDA_VISIBLE_DEVICES="", OMP_NUM_THREADS="4",
                   LOCALLM_RUN_LOG=str(d / "runs.jsonl"))
        c = CFG
        p = subprocess.run(
            [sys.executable, str(HERE / "train.py"), "--data", str(d / "corpus.txt"),
             "--out", str(d / "out"), "--steps", str(c["steps"]),
             "--batch-size", str(c["batch_size"]), "--block-size", str(c["block_size"]),
             "--n-layer", str(c["n_layer"]), "--n-head", str(c["n_head"]),
             "--n-embd", str(c["n_embd"]), "--dropout", "0", "--lr", str(c["lr"]),
             "--eval-interval", str(c["eval_interval"])],
            capture_output=True, text=True, timeout=900, cwd=str(d), env=env)
        assert p.returncode == 0, p.stderr[-1500:]
        assert "early stopping: on" in p.stdout
        assert "validation had not improved by more than run-to-run noise" in p.stdout
        vals = {}
        for line in p.stdout.splitlines():
            if line.startswith("step ") and "| val " in line:
                vals[int(line.split()[1])] = float(line.split("| val ")[1].split()[0])
        text = (d / "corpus.txt").read_text(encoding="utf-8")
        corpus = Corpus(text, CharTokenizer.from_text(text), "cpu")
        got, ck = _load_and_score(d / "out", corpus, c["batch_size"], c["block_size"])
        rec = ck["training"]
        best = min(vals, key=vals.get)
        assert rec["saved_step"] == best and rec["stop_reason"] == "patience"
        assert abs(got["val"] - vals[best]) < 1e-4, (got["val"], vals[best])
        row = runlog.json.loads((d / "runs.jsonl").read_text().splitlines()[-1])
        assert row["training"]["saved_step"] == best
        assert abs(row["metrics"]["val_loss"] - got["val"]) < 1e-6


if __name__ == "__main__":
    fails = []
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            try:
                fn(); print(f"PASS {name}")
            except AssertionError as e:
                fails.append(name); print(f"FAIL {name}: {e}")
    print(f"\n{len(fails)} failed")
    raise SystemExit(1 if fails else 0)
