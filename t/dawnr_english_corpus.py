#!/usr/bin/env python3
"""t/dawnr_english_corpus.py -- assemble the decontaminated general-English shards
into tokenized training shards, excluding every flagged document by id with a
check that proves none of them survived (2026-09-27).

internal/PRETRAIN-DAWNR-GENERAL.md, "Required before the English corpus is
assembled": "The 53 flagged documents must then be excluded by document id at
assembly time, with a check that proves it." This is that step, generalised to
however many documents the widened filter (t/dawnr_ngram_decontam.py,
t/PREDICT-2026-09-27-dawnr-english-widened.md) flags.

The proof, concretely: this script re-reads each shard file itself (the same
two globs, the same per-format id derivation dawnr_ngram_decontam.py's own
scan_fineweb_shard/scan_tinystories_file use -- reimplemented rather than
imported, since what is needed here is the id for every document, not only
the flagged ones the scan functions short-circuit past). For every shard file
it fully processes, it tracks which of that file's flagged ids it actually
encountered and skipped, and refuses (raises, does not warn) if that set does
not exactly equal the flagged set dawnr_ngram_decontam.py recorded for the
same file, or if the count of documents it excluded does not equal the
"contaminated" count in the decontamination report.json for that same file.
This is deliberately a re-derivation, not a reuse of the scan functions
themselves: an id-derivation bug shared by both scripts would not be caught by
reusing one script's logic in the other, but a *mismatch* between two
independent derivations of "which document is this" is exactly what the
equality check surfaces. Measuring instead of asserting contamination is
excluded is the same standard t/loop_filter.py already applies to training
documents, citing Sainz et al. 2023 (arXiv:2310.18018, "evaluation data must
stay unseen ... applied at every point where bytes can become training data").

Tokenized output follows nanoGPT's data/openwebtext/prepare.py design
(github.com/karpathy/nanoGPT): token ids as a flat uint16 array (safe because
the core tokenizer's vocabulary, 8,192, is under 2**16 -- the same reasoning
nanoGPT's own comment gives for GPT-2's 50,257), one array.array('H', ...)
shard per fixed token budget rather than nanoGPT's one np.memmap per split,
because this corpus is a bounded pilot slice carved out of a much larger
downloaded pool (internal/PRETRAIN-DAWNR-GENERAL.md section 2's token budget)
and benefits from resumable, independently-sized shard files. array.array
(not numpy) matches this repository's own precedent for the same job
(locallm/data.py:cached_encode's "array.array('i', ids)"); the bytes it
writes are what nanoGPT's own read recipe expects
(`np.memmap(path, dtype=np.uint16, mode='r')`) since array.array and numpy
agree on native byte order on the one architecture this project runs on.
A document's tokens are never split across two shard files: the current
shard is flushed (short of its nominal budget if need be) before a document
that would overflow it starts a new one, so DocumentBatches-style consumers
that expect a whole document per read are never handed a truncated one.

Usage (the lab's ~/.venv-train has torch, pyarrow and tokenizers together, the
combination this script needs; CPU only, no GPU touched):

    ~/.venv-train/bin/python3 t/dawnr_english_corpus.py \\
        --shards ~/data/dawnr-english \\
        --decontam ~/scratch/dawnr-english/decontam-widened-2026-09-27 \\
        --tokenizer ~/scratch/dawnr-english/core-tokenizer.json \\
        --out ~/scratch/dawnr-english/corpus-pilot-2026-09-27 \\
        --max-tokens 400000000 --shard-tokens 50000000 \\
        --emit-text-corpus ~/scratch/dawnr-english/corpus-pilot-2026-09-27/pilot-english.txt
"""
from __future__ import annotations

import argparse
import array
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCALLM = Path(os.environ.get("DAWNR_LOCALLM_DIR", str(HERE.parent / "locallm")))
sys.path.insert(0, str(LOCALLM))

DTYPE_CODE = "H"          # array.array unsigned short: 2 bytes, matches np.uint16 on this architecture
DTYPE_MAX = 2 ** 16


# ------------------------------------------------------------- shard reading --

def list_shard_files(shards_dir: Path) -> list[Path]:
    """The same two globs dawnr_ngram_decontam.py's main() uses, same sort order."""
    files = sorted((shards_dir / "fineweb-edu-sample-10BT").glob("*.parquet"))
    files += sorted((shards_dir / "tinystories").glob("*.txt"))
    return files


def iter_fineweb_docs(path: Path):
    """Yields (doc_id, text) exactly as dawnr_ngram_decontam.scan_fineweb_shard
    enumerates them: same columns, same batch order, so "the Nth document" and
    its "id" agree between the two scripts without either importing the other's
    scan loop."""
    import pyarrow.parquet as pq
    pf = pq.ParquetFile(path)
    for batch in pf.iter_batches(columns=["text", "id"], batch_size=4096):
        yield from zip(batch.column("id").to_pylist(), batch.column("text").to_pylist())


def iter_tinystories_docs(path: Path):
    """Yields (doc_id, text); doc_id is the 1-based index among non-blank
    stories, identical to scan_tinystories_file's own `scanned` counter."""
    text = path.read_text(encoding="utf-8", errors="replace")
    scanned = 0
    for story in text.split("<|endoftext|>"):
        if not story.strip():
            continue
        scanned += 1
        yield scanned, story.strip()


def iter_shard_docs(path: Path):
    if path.suffix == ".txt":
        yield from iter_tinystories_docs(path)
    else:
        yield from iter_fineweb_docs(path)


# --------------------------------------------------------------- assembly --

def load_decontam(decontam_dir: Path) -> tuple[dict, dict[str, set]]:
    report = json.loads((decontam_dir / "report.json").read_text(encoding="utf-8"))
    flagged_raw = json.loads((decontam_dir / "flagged_ids.json").read_text(encoding="utf-8"))
    flagged = {file: set(ids) for file, ids in flagged_raw.items()}
    if sum(len(v) for v in flagged.values()) != report.get("total_contaminated"):
        raise ValueError(
            f"{decontam_dir}: flagged_ids.json totals "
            f"{sum(len(v) for v in flagged.values())} but report.json's total_contaminated is "
            f"{report.get('total_contaminated')} -- these must come from the same run")
    return report, flagged


class ShardWriter:
    """Buffers token ids and flushes fixed-token-budget uint16 shard files. A
    document is never split across two files: add() flushes first if the
    incoming document would overflow the current buffer, unless the buffer is
    still empty (a single document longer than shard_tokens gets its own,
    over-budget shard rather than being truncated)."""

    def __init__(self, out_dir: Path, shard_tokens: int, prefix: str = "english"):
        self.out_dir, self.shard_tokens, self.prefix = out_dir, shard_tokens, prefix
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.buffer: list[int] = []
        self.shards: list[dict] = []
        self.total_tokens = 0

    def add(self, ids: list[int]) -> None:
        if self.buffer and len(self.buffer) + len(ids) > self.shard_tokens:
            self.flush()
        self.buffer.extend(ids)

    def flush(self) -> None:
        if not self.buffer:
            return
        name = f"{self.prefix}-{len(self.shards):05d}.bin"
        path = self.out_dir / name
        data = array.array(DTYPE_CODE, self.buffer)
        path.write_bytes(data.tobytes())
        self.shards.append({"file": name, "tokens": len(self.buffer)})
        self.total_tokens += len(self.buffer)
        self.buffer = []

    def close(self) -> list[dict]:
        self.flush()
        return self.shards


def assemble(shards_dir: Path, decontam_dir: Path, tokenizer_path: Path, out_dir: Path,
            max_tokens: int, shard_tokens: int, text_corpus_path: Path | None) -> dict:
    from data import DOC_END, load_tokenizer, tokenizer_fingerprint  # locallm/data.py

    report, flagged = load_decontam(decontam_dir)
    expected_contaminated_by_file = {r["file"]: r["contaminated"] for r in report["per_file"]}

    tok = load_tokenizer(str(tokenizer_path))
    if tok.vocab_size > DTYPE_MAX:
        raise ValueError(f"tokenizer vocab_size {tok.vocab_size} does not fit in uint16 (max {DTYPE_MAX})")
    end_ids = tok.encode(DOC_END)
    if not end_ids or tok.decode(end_ids) != DOC_END:
        raise ValueError(f"tokenizer cannot round-trip the document-end marker {DOC_END!r}")

    writer = ShardWriter(out_dir, shard_tokens)
    text_fh = open(text_corpus_path, "w", encoding="utf-8") if text_corpus_path else None

    all_files = list_shard_files(shards_dir)
    if not all_files:
        raise SystemExit(f"no shard files found under {shards_dir}")
    files_fully_processed = []
    scanned = kept = excluded = 0
    kept_chars = 0
    stopped_early = False
    t0 = time.time()
    try:
        for path in all_files:
            basename = path.name
            flagged_here = flagged.get(basename, set())
            seen_flagged_here: set = set()
            excluded_here = kept_here = 0
            for doc_id, text in iter_shard_docs(path):
                scanned += 1
                if doc_id in flagged_here:
                    excluded_here += 1
                    seen_flagged_here.add(doc_id)
                    continue
                body = text.strip("\r\n")
                if not body.strip():
                    continue
                ids = tok.encode(body + DOC_END)
                if not ids:
                    continue
                writer.add(ids)
                if text_fh is not None:
                    text_fh.write(body)
                    text_fh.write(DOC_END)
                kept_here += 1
                kept_chars += len(body)
            # THE PROOF: every flagged id for this file was actually found and
            # skipped while re-reading it, and the count of exclusions this
            # pass made agrees with the decontamination report's own count for
            # the same file. Either mismatch means the two scripts disagree
            # about which document is which, or a shard file changed on disk
            # between the decontamination run and this one -- both are refused
            # by name, never silently kept or silently trusted.
            if seen_flagged_here != flagged_here:
                raise AssertionError(
                    f"{basename}: {len(flagged_here - seen_flagged_here)} flagged id(s) were never "
                    f"encountered while reassembling this file (e.g. {sorted(flagged_here - seen_flagged_here)[:3]}); "
                    "the decontamination pass and this assembly pass disagree about this file's documents")
            if basename in expected_contaminated_by_file and excluded_here != expected_contaminated_by_file[basename]:
                raise AssertionError(
                    f"{basename}: excluded {excluded_here} documents here but the decontamination report "
                    f"says {expected_contaminated_by_file[basename]} were contaminated in this file")
            excluded += excluded_here
            kept += kept_here
            files_fully_processed.append(basename)
            if writer.total_tokens + len(writer.buffer) >= max_tokens:
                stopped_early = len(files_fully_processed) < len(all_files)
                break
    finally:
        shards = writer.close()
        if text_fh is not None:
            text_fh.close()
    elapsed = time.time() - t0

    total_tokens = sum(s["tokens"] for s in shards)
    manifest = {
        "schema": 1,
        "source_decontam_report": str(decontam_dir / "report.json"),
        "tokenizer_path": str(tokenizer_path),
        "tokenizer_fingerprint": tokenizer_fingerprint(tok),
        "tokenizer_vocab_size": tok.vocab_size,
        "dtype": "uint16",
        "doc_end": DOC_END,
        "files_processed": files_fully_processed,
        "stopped_early_on_token_budget": stopped_early,
        "documents_scanned": scanned,
        "documents_excluded_flagged": excluded,
        "documents_kept": kept,
        "proof": {
            "every_flagged_id_reencountered_per_file": True,
            "excluded_count_matches_decontam_report_per_file": True,
            "files_checked": len(files_fully_processed),
        },
        "kept_characters": kept_chars,
        "total_tokens": total_tokens,
        "chars_per_token": round(kept_chars / total_tokens, 4) if total_tokens else None,
        "shard_files": shards,
        "shard_tokens_nominal": shard_tokens,
        "elapsed_seconds": round(elapsed, 1),
        "text_corpus_path": str(text_corpus_path) if text_corpus_path else None,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shards", required=True)
    ap.add_argument("--decontam", required=True, help="dir holding report.json and flagged_ids.json")
    ap.add_argument("--tokenizer", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-tokens", type=int, default=400_000_000)
    ap.add_argument("--shard-tokens", type=int, default=50_000_000)
    ap.add_argument("--emit-text-corpus", default="", help="also write the kept, decontaminated "
                    "documents as plain joined text at this path (train.py --data can read it directly)")
    a = ap.parse_args()
    manifest = assemble(
        Path(a.shards).expanduser(), Path(a.decontam).expanduser(), Path(a.tokenizer).expanduser(),
        Path(a.out).expanduser(), a.max_tokens, a.shard_tokens,
        Path(a.emit_text_corpus).expanduser() if a.emit_text_corpus else None)
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
