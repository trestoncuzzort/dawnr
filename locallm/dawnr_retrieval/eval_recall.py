#!/usr/bin/env python3
"""eval_recall.py: recall@k for dawnr_retrieval, on questions built from training-split proved-
corpus documents only.

    python3 locallm/dawnr_retrieval/eval_recall.py --corpus <corpus.txt> [--split <split.json>] [--k 5]
    python3 locallm/dawnr_retrieval/eval_recall.py --corpus <corpus.txt> --dense --model <checkpoint dir>

A question is a train-split document's own `Problem:` line, and the passage it must find is that
same document -- a headless document has no independent natural-language statement to query with,
so it is skipped rather than queried with its own program text (that would test copy-detection, not
retrieval). "Train-split" means data.split_documents(by="hash")'s train side, at the same seed and
val_frac the trainers use by default: `_is_val` below reimplements data.hash_holdout's exact
formula (same salt, same threshold) rather than importing locallm.data, which requires torch at
module scope for unrelated reasons -- see sources.py's docstring for the same reasoning applied to
corpus loading. Restricting questions to the train side keeps this evaluation on the same side of
the boundary the pretraining loss is measured on, rather than casually reusing the slice that holds
out for a different purpose.

This is a sanity/quality check of the ranking itself (does the index return a document, given a
paraphrase of its own stated problem), not a test of generalising to unseen text: every document
queried was, by construction, indexed. DAWNR-RETRIEVAL.md records the prediction made before this
was ever run, and the measured result beside it either way (AGENTS.md rule 3).
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

if __name__ == "__main__" and __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from dawnr_retrieval.eval_recall import main as _main
    raise SystemExit(_main())

from .index import KnowledgeIndex
from .sources import load_corpus

_SPLIT_SALT = b"locallm-split"     # data.hash_holdout's own salt; must match to reproduce its split


def _is_val(doc: str, seed: int, val_frac: float) -> bool:
    """Mirrors data.hash_holdout exactly (see this module's docstring for why it is reimplemented
    rather than imported): sha256(salt || seed || stripped document text), keep the low 8 bytes as
    an integer, compare against val_frac of the full range. Deterministic in the document's own
    text alone, so it agrees with data.split_documents(by="hash") for the same seed and val_frac
    regardless of what else is in the corpus."""
    payload = _SPLIT_SALT + b"\x00" + str(int(seed)).encode("ascii") + b"\x00" + doc.strip().encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    return int.from_bytes(digest[:8], "big") < val_frac * 2 ** 64


def build_eval_questions(passages, *, seed: int = 1337, val_frac: float = 0.1) -> list[tuple]:
    """[(query, expected passage id), ...] from train-split corpus documents that have a Problem:
    head (their own title, set by sources.load_corpus)."""
    return [(p.title, p.id) for p in passages
           if p.kind == "corpus" and p.title and not _is_val(p.text, seed, val_frac)]


def recall_at_k(index: KnowledgeIndex, questions, k: int = 5) -> dict:
    hits = sum(1 for query, expected in questions if expected in {p.id for p, _ in index.search(query, k)})
    n = len(questions)
    return {"n": n, "hits": hits, "k": k, "recall_at_k": (hits / n) if n else 0.0}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--corpus", type=Path, required=True)
    ap.add_argument("--split", type=Path, default=None, help="the evaluation split whose eval_ids must not appear")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--split-seed", type=int, default=1337)
    ap.add_argument("--val-frac", type=float, default=0.1)
    ap.add_argument("--dense", action="store_true", help="also measure BM25+dense (RRF) recall@k")
    ap.add_argument("--model", type=Path, default=None, help="a trained checkpoint dir; required with --dense")
    a = ap.parse_args(argv)
    if a.dense and not a.model:
        ap.error("--dense needs --model <checkpoint dir>")

    passages, problems = load_corpus(a.corpus, split_path=a.split)
    index = KnowledgeIndex()
    index.add_all(passages)
    index.build()
    questions = build_eval_questions(passages, seed=a.split_seed, val_frac=a.val_frac)
    if not questions:
        print("no train-split documents with a Problem: head; nothing to measure", file=sys.stderr)
        return 1

    bm25 = recall_at_k(index, questions, a.k)
    print(f"corpus: {a.corpus} ({index.count()} passages indexed, {len(problems)} document(s) excluded "
         f"by the held-out gate)")
    print(f"questions: {bm25['n']} (train-split documents with a Problem: head, seed {a.split_seed}, "
         f"val_frac {a.val_frac})")
    print(f"BM25 recall@{a.k}: {bm25['hits']}/{bm25['n']} = {bm25['recall_at_k']:.3f}")

    if a.dense:
        from .dense import DenseIndex
        index.dense = DenseIndex.build(index.passages(), model_dir=str(a.model))
        dense = recall_at_k(index, questions, a.k)
        print(f"BM25+dense (RRF) recall@{a.k}: {dense['hits']}/{dense['n']} = {dense['recall_at_k']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
