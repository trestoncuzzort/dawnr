#!/usr/bin/env python3
"""t/dawnr_tokenizer_compression.py -- does the core's code-trained BPE read English? (2026-09-26)

Measures characters per token (`chars_per_token`, the same metric and the
same formula `locallm/dawnr_pipeline.py`'s `chars_per_token` uses for the
code side: chars / tokens over a list of documents) on a sample of the
downloaded general-English shards, using the r12 core's own frozen
tokenizer.json (8,192-entry byte-level BPE trained on ~150 MB of source code,
internal/PRETRAIN-R12-2026-09-25.md). The code-side number this is compared
against is already measured and cited, not re-derived here: the DAWNR
pipeline's own tokenizer stage reports 2.4994 chars/token on the proved
corpus's train side and 2.5224 on its validation side using this exact
tokenizer and this exact metric (`~/scratch/dawnr-pipeline/core-1/report.md`,
"Tokenizer" section, `locallm/dawnr_pipeline.py:stage_tokenizer`).

Requires only the `tokenizers` package (present in ~/.venv-locallm) and, for
the FineWeb-Edu parquet shards, `pyarrow` (present in ~/.venv-train on the
lab); TinyStories is plain text and needs neither. The prediction and
decision rule (keep / extend / retrain) this measurement is checked against
are fixed in advance in t/PREDICT-2026-09-26-dawnr-english.md.

Usage:

    ~/.venv-locallm/bin/python3 t/dawnr_tokenizer_compression.py \\
        --tokenizer ~/scratch/dawnr-pipeline/core-wd08/tokenizer.json \\
        --fineweb-shard ~/data/dawnr-english/fineweb-edu-sample-10BT/000_00000.parquet \\
        --tinystories ~/data/dawnr-english/tinystories/TinyStoriesV2-GPT4-valid.txt \\
        --char-budget 50000000
"""
import argparse
import json
import sys
from pathlib import Path

LOCALLM = Path(__file__).resolve().parent.parent / "locallm"
sys.path.insert(0, str(LOCALLM))


def chars_per_token(tok, docs: list[str]) -> float | None:
    """Mirrors locallm/dawnr_pipeline.py:chars_per_token exactly (chars / tokens)."""
    chars = sum(len(d) for d in docs)
    tokens = sum(len(tok.encode(d)) for d in docs)
    return round(chars / tokens, 4) if tokens else None, chars, tokens


def sample_fineweb(path: str, char_budget: int) -> list[str]:
    import pyarrow.parquet as pq
    pf = pq.ParquetFile(path)
    docs, total = [], 0
    for batch in pf.iter_batches(columns=["text"], batch_size=2048):
        for text in batch.column("text").to_pylist():
            docs.append(text)
            total += len(text)
            if total >= char_budget:
                return docs
    return docs


def sample_tinystories(path: str, char_budget: int) -> list[str]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    stories, total, out = text.split("<|endoftext|>"), 0, []
    for story in stories:
        story = story.strip()
        if not story:
            continue
        out.append(story)
        total += len(story)
        if total >= char_budget:
            break
    return out


def main() -> None:
    from data import load_tokenizer, tokenizer_fingerprint

    ap = argparse.ArgumentParser()
    ap.add_argument("--tokenizer", required=True)
    ap.add_argument("--fineweb-shard", action="append", default=[])
    ap.add_argument("--tinystories", default="")
    ap.add_argument("--char-budget", type=int, default=50_000_000)
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    tok = load_tokenizer(a.tokenizer)
    report = {"tokenizer": a.tokenizer, "vocab_size": tok.vocab_size,
              "fingerprint": tokenizer_fingerprint(tok),
              "code_side_reference": {
                  "source": "locallm/dawnr_pipeline.py:stage_tokenizer, "
                            "~/scratch/dawnr-pipeline/core-1/report.md",
                  "chars_per_token_train": 2.4994, "chars_per_token_val": 2.5224,
              }, "english_side": {}}

    for shard in a.fineweb_shard:
        docs = sample_fineweb(shard, a.char_budget)
        cpt, chars, tokens = chars_per_token(tok, docs)
        report["english_side"][f"fineweb-edu:{Path(shard).name}"] = {
            "documents": len(docs), "chars": chars, "tokens": tokens, "chars_per_token": cpt}

    if a.tinystories:
        docs = sample_tinystories(a.tinystories, a.char_budget)
        cpt, chars, tokens = chars_per_token(tok, docs)
        report["english_side"][f"tinystories:{Path(a.tinystories).name}"] = {
            "documents": len(docs), "chars": chars, "tokens": tokens, "chars_per_token": cpt}

    text = json.dumps(report, indent=1)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
