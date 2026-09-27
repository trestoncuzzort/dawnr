#!/usr/bin/env python3
"""run_sae.py -- cache one layer's residual-stream activations, train a sparse
autoencoder dictionary over them, and write two markdown reports: a feature browser
(top activating contexts per feature) and a probe of AMBITION.md's first
interpretability question -- do any features fire on specifications and loop
invariants, as opposed to memorised boilerplate? (See README.md for the recipe and
its citation, sae.py/activations.py/browser.py/spec_probe.py for the pieces.)

Runs on CPU by default, which is enough for the corpora this reads (a few hundred KB
to a few MB of source text, not a pretraining run). A GPU run must go through this
project's lock and stay small, since a base-model pretraining job can already be
using most of the card:

    flock ~/scratch/gpu.lock systemd-run --user --scope -p MemoryMax=6G \\
        python3 locallm/dawnr_interp/run_sae.py --device cuda ...

Example, on one of this repository's own small checkpoints and its own tasks:

    python3 locallm/dawnr_interp/run_sae.py \\
        --checkpoint t/runs/2026-09-16/filter-loop/clean/r2/model \\
        --corpus t/out/some-corpus.txt --out ~/scratch/dawnr-interp/r2
"""
from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and __package__ in (None, ""):
    # run directly as `python3 .../dawnr_interp/run_sae.py`: reimport this file as
    # the package's own copy so the relative imports below resolve, exactly as
    # dawnr_harness/__main__.py does for the same reason.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from dawnr_interp.run_sae import main as _main
    raise SystemExit(_main())

import argparse  # noqa: E402
import json  # noqa: E402

import torch  # noqa: E402

from checkpoint import load_checkpoint  # noqa: E402

from . import browser  # noqa: E402
from .activations import cache_residual_stream, training_split_documents  # noqa: E402
from .sae import SAEConfig, SparseAutoencoder, train_sae  # noqa: E402
from .spec_probe import boilerplate_lines, feature_label_contrast, label_cached_activations, render_report  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--checkpoint", required=True, type=Path,
                    help="directory holding ckpt.pt + tokenizer.json (checkpoint.load_checkpoint)")
    ap.add_argument("--corpus", required=True, type=Path,
                    help="a text corpus file (documents separated by a blank line or make_corpus.py's "
                         "'# file:' markers, exactly what data.documents splits on)")
    ap.add_argument("--out", type=Path, default=Path.home() / "scratch" / "dawnr-interp",
                    help="output directory for the reports and the trained dictionary "
                         "(default: ~/scratch/dawnr-interp)")
    ap.add_argument("--layer", type=int, default=None,
                    help="which residual-stream layer to read, 0-indexed after that block "
                         "(default: the middle layer)")
    ap.add_argument("--expansion", type=int, default=8,
                    help="dictionary size = expansion * the model's width (the paper's R)")
    ap.add_argument("--l1", type=float, default=1e-3, dest="l1_coefficient",
                    help="sparsity coefficient (the paper's alpha) -- retune per model; "
                         "their value does not transfer across model scales")
    ap.add_argument("--steps", type=int, default=300)
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--seed", type=int, default=0, help="the SAE training batch sampler's seed")
    ap.add_argument("--val-frac", type=float, default=0.1,
                    help="fraction of the corpus withheld from activation caching (data.group_split's own "
                         "default), so this dictionary sees the same holdout a real training run would")
    ap.add_argument("--split-seed", type=int, default=1337, help="matches data.group_split's own default")
    ap.add_argument("--split-by", choices=("order", "hash"), default="order")
    ap.add_argument("--max-documents", type=int, default=None,
                    help="cap on how many training-split documents to read, for a bounded smoke run")
    ap.add_argument("--context-chars", type=int, default=60)
    ap.add_argument("--top-k-contexts", type=int, default=8)
    ap.add_argument("--browser-limit", type=int, default=200,
                    help="feature-browser.md documents at most this many features by default, the "
                         "liveliest by max activation; --full-browser ignores this cap")
    ap.add_argument("--full-browser", action="store_true",
                    help="write every dictionary feature to the browser, dead ones too, ignoring --browser-limit")
    ap.add_argument("--device", default="cpu",
                    help="'cpu' or 'cuda' -- a cuda run must go through this project's GPU lock, "
                         "see this file's module docstring")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    model, tok, cfg = load_checkpoint(args.checkpoint, device=args.device)
    layer = args.layer if args.layer is not None else cfg.n_layer // 2
    if not 0 <= layer < cfg.n_layer:
        print(f"--layer must be in [0, {cfg.n_layer}) for this checkpoint; got {layer}", file=sys.stderr)
        return 1

    corpus_text = args.corpus.read_text(encoding="utf-8")
    documents = training_split_documents(corpus_text, val_frac=args.val_frac, seed=args.split_seed,
                                         by=args.split_by)
    if not documents:
        print("no training-split documents in this corpus at this val_frac/seed; nothing to cache",
              file=sys.stderr)
        return 1

    which = "all" if args.max_documents is None else f"the first {args.max_documents}"
    print(f"caching layer {layer} of {cfg.n_layer} over {which} of {len(documents)} training-split documents...")
    cached = cache_residual_stream(model, tok, documents, layer, context_chars=args.context_chars,
                                   device=args.device, max_documents=args.max_documents)
    if len(cached) == 0:
        print("no token positions were cached (empty corpus after tokenization)", file=sys.stderr)
        return 1
    print(f"{len(cached)} positions cached, width {cached.activations.shape[1]}")

    sae_config = SAEConfig(d_in=cached.activations.shape[1], expansion=args.expansion,
                           l1_coefficient=args.l1_coefficient)
    sae = SparseAutoencoder(sae_config)
    print(f"training a {sae_config.d_hidden}-feature dictionary for {args.steps} steps...")
    history = train_sae(sae, cached.activations, steps=args.steps, batch_size=args.batch_size, lr=args.lr,
                        seed=args.seed, log_every=max(1, args.steps // 10), device=args.device)

    with torch.no_grad():
        code = sae.encode(cached.activations.to(args.device)).cpu()

    used_documents = documents[:args.max_documents] if args.max_documents is not None else documents
    boilerplate = boilerplate_lines(used_documents)
    labels = label_cached_activations(cached, used_documents, tok, boilerplate_lines=boilerplate)
    contrasts = feature_label_contrast(code, labels)
    probe_report = render_report(contrasts, cached, code, top_k_features=10, contexts_per_feature=5)

    stats = [(f, browser.feature_stats(code, f)) for f in range(sae_config.d_hidden)]
    if args.full_browser:
        browser_features = None
    else:
        alive = sorted((fs for fs in stats if fs[1]["fires"] > 0), key=lambda fs: fs[1]["max"], reverse=True)
        browser_features = [f for f, _ in alive[:args.browser_limit]]
    browser_md = browser.feature_browser_markdown(cached, code, features=browser_features,
                                                  top_k=args.top_k_contexts)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "spec-probe.md").write_text(probe_report, encoding="utf-8")
    (args.out / "feature-browser.md").write_text(browser_md, encoding="utf-8")
    torch.save({"config": sae_config.__dict__, "state_dict": sae.state_dict(), "layer": layer,
               "final_metrics": history[-1] if history else None}, args.out / "sae.pt")
    run_info = {
        "checkpoint": str(args.checkpoint), "corpus": str(args.corpus), "layer": layer, "n_layer": cfg.n_layer,
        "n_documents": len(used_documents), "n_positions": len(cached), "d_in": sae_config.d_in,
        "d_hidden": sae_config.d_hidden, "l1_coefficient": sae_config.l1_coefficient, "steps": args.steps,
        "final_metrics": history[-1] if history else None, "n_boilerplate_lines": len(boilerplate),
        "n_dead_features": sum(1 for _, s in stats if s["fires"] == 0),
    }
    (args.out / "run.json").write_text(json.dumps(run_info, indent=2), encoding="utf-8")
    print(f"wrote {args.out}/spec-probe.md, feature-browser.md, sae.pt and run.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
