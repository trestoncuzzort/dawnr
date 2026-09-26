"""The denoising experiment of FINDINGS-denoising-2026-09-26.md: does FIM shrink memorisation?

Arms: --fim-rate 0 and --fim-rate 0.5 (and optionally --fim-span t), 3 seeds
each, trained from random weights through continue_from_checkpoint.py
--doc-batches (the r12 path: one whole document per row, hash split, the
held-out gates), early stopping off. For each seed one random init is written
and shared by every arm, so arms differ only in the transform. The init's
character tokenizer carries the FIM sentinels in every arm, so vocabulary and
initialization are identical; an arm at rate 0 never sees a sentinel.

    python exp_fim_denoising.py run --corpus corpus.txt --split split-v5.json --work DIR
    python exp_fim_denoising.py summarize --work DIR
    python exp_fim_denoising.py infill --work DIR --arm fim0.5-char --seed 1

Every loss is continue_from_checkpoint's document_loss: the token-weighted
mean over every document exactly once, on untransformed left-to-right text.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# The studio's Medium width and depth (studio.SIZES["Medium"]), with a context
# long enough that no document of the r12 corpus is cut (longest 1,262 chars).
SHAPE = dict(n_layer=4, n_head=4, n_embd=256, block_size=1280)
TRAIN = dict(steps=3000, batch_size=16, lr=3e-3, warmup=100, dropout=0.0, eval_every=50)
ARMS = {"fim0-char": (0.0, "char"), "fim0.5-char": (0.5, "char"), "fim0.5-t": (0.5, "t")}


def make_init(corpus: Path, out: Path, seed: int) -> None:
    import torch
    import data
    import fim
    from model import GPT, GPTConfig
    if (out / "ckpt.pt").exists():
        return
    out.mkdir(parents=True, exist_ok=True)
    tok = data.CharTokenizer.from_text(corpus.read_text(encoding="utf-8")).with_sentinels(fim.SENTINELS)
    tok.save(out / "tokenizer.json")
    torch.manual_seed(seed)
    cfg = GPTConfig(vocab_size=tok.vocab_size, **SHAPE)
    model = GPT(cfg)
    torch.save({"model": model.state_dict(), "config": asdict(cfg),
                "tokenizer_fingerprint": data.tokenizer_fingerprint(tok)}, out / "ckpt.pt")


def run(args) -> None:
    work = Path(args.work)
    for seed in args.seeds:
        init = work / f"init-s{seed}"
        make_init(Path(args.corpus), init, seed)
        for arm in args.arms:
            rate, span = ARMS[arm]
            out = work / f"{arm}-s{seed}"
            done = out / "run.json"
            if done.exists() and json.loads(done.read_text()).get("status") == "complete":
                continue
            cmd = [sys.executable, str(HERE / "continue_from_checkpoint.py"), "--init", str(init),
                   "--data", str(args.corpus), "--split", str(args.split), "--out", str(out),
                   "--doc-batches", "--steps", str(args.steps), "--batch-size", str(TRAIN["batch_size"]),
                   "--block-size", str(SHAPE["block_size"]), "--lr", str(TRAIN["lr"]),
                   "--warmup", str(TRAIN["warmup"]), "--dropout", str(TRAIN["dropout"]),
                   "--eval-every", str(TRAIN["eval_every"]), "--log-every", str(TRAIN["eval_every"]),
                   "--save-every", str(args.steps), "--seed", str(seed),
                   "--fim-rate", str(rate), "--fim-span", span]
            print(f"== {arm} seed {seed}", flush=True)
            with (work / f"{arm}-s{seed}.log").open("w") as log:
                subprocess.run(cmd, check=True, stdout=log, stderr=subprocess.STDOUT)


def curve(out: Path) -> list[dict]:
    return [json.loads(line) for line in (out / "metrics.jsonl").read_text().splitlines()]


def summarize(args) -> dict:
    work = Path(args.work)
    table = {}
    for arm in ARMS:
        rows = []
        for out in sorted(work.glob(f"{arm}-s*")):
            if not out.is_dir() or not (out / "run.json").exists():
                continue
            run = json.loads((out / "run.json").read_text())
            if run.get("status") != "complete":
                continue
            c = curve(out)
            best = min(c, key=lambda r: r["val"])
            final = run["final_losses"]
            rows.append({"seed": run["identities"]["seed"], "final_val": final["val"],
                         "best_val": best["val"], "best_step": best["step"],
                         "final_train": final["train"], "gap": final["val"] - final["train"],
                         "train_at_best": best["train"]})
        if rows:
            agg = {k: {"mean": statistics.mean(r[k] for r in rows),
                       "range": max(r[k] for r in rows) - min(r[k] for r in rows)}
                   for k in ("final_val", "best_val", "best_step", "final_train", "gap")}
            table[arm] = {"seeds": rows, "summary": agg}
    print(json.dumps(table, indent=2))
    return table


# Held-out infill probes: the middle is one whole line chosen by these rules,
# and a random character span, on validation documents only.
def infill(args) -> None:
    import torch
    import checkpoint
    import data
    import fim
    work = Path(args.work)
    out = work / f"{args.arm}-s{args.seed}"
    model, tok, _ = checkpoint.load_checkpoint(out, device="cuda" if torch.cuda.is_available() else "cpu")
    run = json.loads((out / "run.json").read_text())
    text = Path(run["identities"]["corpus"]).read_text(encoding="utf-8")
    split = run["identities"]["split"]
    _, val_docs = data.split_documents(text, split["val_frac"], split["seed"], by=split["by"])
    rng = random.Random(args.probe_seed)
    exact = closed = total = 0
    for doc in rng.sample(val_docs, min(args.n, len(val_docs))):
        body = doc.strip("\r\n")
        units = fim.t_units(body)
        probes = []
        if units:
            a, b = units[rng.randrange(len(units))]
            probes.append(("unit", body[:a], body[a:b], body[b:]))
        probes.append(("chars",) + fim.char_split(body, rng))
        for kind, prefix, middle, suffix in probes:
            got, ok = fim.infill(model, tok, prefix, suffix, max_new_tokens=max(40, 2 * len(middle)))
            total += 1
            exact += got == middle
            closed += ok
            if args.show:
                tail = prefix.splitlines()[-1] if prefix.splitlines() else ""
                print(f"--- {kind}  exact={got == middle}  closed={ok}\n"
                      f"  prefix ends: {tail[-60:]!r}\n  truth : {middle[:160]!r}\n  model : {got[:160]!r}")
    print(json.dumps({"arm": args.arm, "seed": args.seed, "probes": total,
                      "exact": exact, "closed_with_eot": closed}))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--corpus", required=True)
    r.add_argument("--split", required=True)
    r.add_argument("--work", required=True)
    r.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    r.add_argument("--arms", nargs="+", default=["fim0-char", "fim0.5-char"], choices=list(ARMS))
    r.add_argument("--steps", type=int, default=TRAIN["steps"])
    s = sub.add_parser("summarize")
    s.add_argument("--work", required=True)
    i = sub.add_parser("infill")
    i.add_argument("--work", required=True)
    i.add_argument("--arm", default="fim0.5-char")
    i.add_argument("--seed", type=int, default=1)
    i.add_argument("--n", type=int, default=30)
    i.add_argument("--probe-seed", type=int, default=0)
    i.add_argument("--show", action="store_true")
    args = ap.parse_args()
    {"run": run, "summarize": summarize, "infill": infill}[args.cmd](args)


if __name__ == "__main__":
    main()
