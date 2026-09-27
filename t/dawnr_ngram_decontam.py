#!/usr/bin/env python3
"""t/dawnr_ngram_decontam.py -- 13-gram decontamination of the general-English
shards against the held-out and dev problem pools (2026-09-26).

The precedent is GPT-3's own contamination measurement (Brown et al. 2020,
arXiv:2005.14165): a training document is treated as contaminated if it
shares a 13-gram with an evaluation set, and the paper's own repository
documents the choice directly (github.com/openai/gpt-3/overlap_frequency.md
gives sample 13-grams and their counts in their filtered Common Crawl data).
This filter is a word-level variant of the same idea (13 consecutive
lowercased `[A-Za-z0-9]+` tokens, not 13 consecutive BPE tokens) -- simpler
and tokenizer-independent, at the documented cost that GPT-3's own top-13-gram
list warns about: some 13-grams are generic boilerplate (line-number runs,
alphabet fragments) rather than document-specific, which is exactly why every
match is written out with its matched problem id and shared phrase rather
than only a count, so a boilerplate false positive is visible rather than
silently hidden inside a number.

The protected set is every held-out eval problem (t/out/loop/split-v5.json,
`eval_ids`) plus every dev problem (t/r12-dev-ids.json, `dev_ids`). Both are
plain MBPP task ids by this project's own design: `t/spec_experiment.py`'s
`pool()` keeps "the held-out set of this project ... split-v3's MBPP
problems", and the dev-id rule (t/r12-dev-ids.json, "rule") draws only from
"train_ids below the HumanEval base (MBPP)". So the 332-problem protected set
below is built from MBPP alone (nl/data/mbpp*.jsonl.gz, the same four splits
t/mbpp_dfy.mbpp_records() reads); HumanEval, APPS and CodeContests sit in the
wider training pool but never in the held-out or dev boundary, so they are
not part of what this filter protects. AMBITION.md's own framing that "web
text contains MBPP, HumanEval, APPS and CodeContests problems and solutions"
is about what a downloaded general-English corpus could contain, not about
what must be filtered against -- the filter protects exactly the boundary
t/loop_filter.py's `TrainingDataGate` already treats as absolute, applied to
prose instead of to a named training document.

Usage (lab CPUs, no GPU; --jobs capped at 8 per the machine budget):

    ~/.venv-train/bin/python3 t/dawnr_ngram_decontam.py \\
        --nl-data nl/data --split t/out/loop/split-v5.json --dev-ids t/r12-dev-ids.json \\
        --shards ~/data/dawnr-english --out ~/scratch/dawnr-english/decontam \\
        --jobs 8
"""
from __future__ import annotations

import argparse
import gzip
import json
import multiprocessing as mp
import os
import re
import sys
import time
from pathlib import Path

WORD = re.compile(r"[A-Za-z0-9]+")
N = 13
MBPP_SPLITS = ("mbpp.jsonl.gz", "mbpp_test.jsonl.gz", "mbpp_validation.jsonl.gz", "mbpp_prompt.jsonl.gz")


def mbpp_records(nl_data: Path) -> dict[int, dict]:
    """Every MBPP record across all four splits, keyed by task_id.

    Same four files and the same "later file does not need to override
    earlier one" merge as t/mbpp_dfy.mbpp_records(); reimplemented here
    (rather than imported) so this script has no dependency on the proof
    engine's import chain (surface, interp, fuzz_lower, tasks_io) that
    module pulls in, none of which this filter needs.
    """
    out: dict[int, dict] = {}
    for split in MBPP_SPLITS:
        path = nl_data / split
        if not path.exists():
            continue
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line)
                    out[rec["task_id"]] = rec
    return out


def protected_ids(split_path: Path, dev_ids_path: Path) -> dict[int, str]:
    """id -> "why protected", for every held-out eval id and every dev id."""
    split = json.loads(split_path.read_text(encoding="utf-8"))
    dev = json.loads(dev_ids_path.read_text(encoding="utf-8"))
    reasons: dict[int, str] = {}
    for i in split["eval_ids"]:
        reasons[int(i)] = "eval"
    for i in dev["dev_ids"]:
        reasons.setdefault(int(i), "dev")
    return reasons


def problem_text(rec: dict) -> str:
    return "\n".join([rec.get("text", ""), *rec.get("test_list", []), rec.get("code", "")])


def build_index(records: dict[int, dict], ids: dict[int, str], n: int = N):
    """first-word -> set of n-gram tuples that start with it, and n-gram -> the ids it came from.

    Checking membership this way costs one dict lookup (the first word) for
    almost every position in a scanned document; only a position whose first
    word is one of the (typically few thousand) distinct protected-ngram
    starting words pays for building and comparing the full tuple. This is
    what makes scanning ~10B tokens of downloaded text on 8 CPU cores
    tractable instead of doing a 13-tuple hash at every single position.
    """
    index: dict[str, set[tuple]] = {}
    owners: dict[tuple, set[int]] = {}
    missing = []
    for pid, reason in ids.items():
        rec = records.get(pid)
        if rec is None:
            missing.append(pid)
            continue
        words = WORD.findall(problem_text(rec).lower())
        for i in range(len(words) - n + 1):
            gram = tuple(words[i:i + n])
            index.setdefault(gram[0], set()).add(gram)
            owners.setdefault(gram, set()).add(pid)
    return index, owners, missing


def find_match(words: list[str], index: dict[str, set[tuple]], n: int = N):
    for i in range(len(words) - n + 1):
        first = words[i]
        candidates = index.get(first)
        if not candidates:
            continue
        gram = tuple(words[i:i + n])
        if gram in candidates:
            return i, gram
    return None, None


# --------------------------------------------------------------- scanning --

def scan_fineweb_shard(path: str, index: dict[str, set[tuple]], owners: dict[tuple, set[int]]) -> dict:
    import pyarrow.parquet as pq
    pf = pq.ParquetFile(path)
    scanned = matched = 0
    examples = []
    for batch in pf.iter_batches(columns=["text", "id", "url"], batch_size=4096):
        texts = batch.column("text").to_pylist()
        ids = batch.column("id").to_pylist()
        urls = batch.column("url").to_pylist()
        for text, doc_id, url in zip(texts, ids, urls):
            scanned += 1
            words = WORD.findall(text.lower())
            pos, gram = find_match(words, index)
            if gram is not None:
                matched += 1
                if len(examples) < 25:
                    examples.append({
                        "shard": os.path.basename(path), "doc_id": doc_id, "url": url,
                        "matched_problem_ids": sorted(owners[gram]), "shared_phrase": " ".join(gram),
                        "snippet": text[max(0, text.lower().find(gram[0])):][:280],
                    })
    return {"file": os.path.basename(path), "documents": scanned, "contaminated": matched, "examples": examples}


def scan_tinystories_file(path: str, index: dict[str, set[tuple]], owners: dict[tuple, set[int]]) -> dict:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    stories = text.split("<|endoftext|>")
    scanned = matched = 0
    examples = []
    for story in stories:
        if not story.strip():
            continue
        scanned += 1
        words = WORD.findall(story.lower())
        pos, gram = find_match(words, index)
        if gram is not None:
            matched += 1
            if len(examples) < 25:
                examples.append({
                    "shard": os.path.basename(path), "doc_id": scanned,
                    "matched_problem_ids": sorted(owners[gram]), "shared_phrase": " ".join(gram),
                    "snippet": story.strip()[:280],
                })
    return {"file": os.path.basename(path), "documents": scanned, "contaminated": matched, "examples": examples}


_INDEX = None
_OWNERS = None


def _init_worker(index, owners):
    global _INDEX, _OWNERS
    _INDEX, _OWNERS = index, owners


def _scan_one(path: str) -> dict:
    fn = scan_tinystories_file if path.endswith(".txt") else scan_fineweb_shard
    t0 = time.time()
    result = fn(path, _INDEX, _OWNERS)
    result["seconds"] = round(time.time() - t0, 1)
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nl-data", required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--dev-ids", required=True)
    ap.add_argument("--shards", required=True, help="directory holding fineweb-edu-sample-10BT/ and tinystories/")
    ap.add_argument("--out", required=True)
    ap.add_argument("--jobs", type=int, default=8)
    a = ap.parse_args()
    jobs = max(1, min(a.jobs, 8, os.cpu_count() or 1))

    shards_dir = Path(a.shards).expanduser()
    files = sorted(str(p) for p in (shards_dir / "fineweb-edu-sample-10BT").glob("*.parquet"))
    files += sorted(str(p) for p in (shards_dir / "tinystories").glob("*.txt"))
    if not files:
        raise SystemExit(f"no shard files found under {shards_dir}")

    ids = protected_ids(Path(a.split), Path(a.dev_ids))
    records = mbpp_records(Path(a.nl_data))
    index, owners, missing = build_index(records, ids)
    print(f"protected ids: {len(ids)} (eval {sum(v == 'eval' for v in ids.values())}, "
          f"dev {sum(v == 'dev' for v in ids.values())}); missing from nl/data: {len(missing)}; "
          f"distinct 13-grams: {len(owners)}", file=sys.stderr)

    t0 = time.time()
    with mp.Pool(jobs, initializer=_init_worker, initargs=(index, owners)) as pool:
        per_file = pool.map(_scan_one, files)
    elapsed = time.time() - t0

    total_documents = sum(r["documents"] for r in per_file)
    total_contaminated = sum(r["contaminated"] for r in per_file)
    all_examples = [e for r in per_file for e in r["examples"]]
    report = {
        "protected_ids": len(ids), "protected_ids_missing_from_nl_data": missing,
        "distinct_13grams": len(owners), "shard_files": len(files), "jobs": jobs,
        "elapsed_seconds": round(elapsed, 1),
        "total_documents": total_documents, "total_contaminated": total_contaminated,
        "contaminated_fraction": round(total_contaminated / total_documents, 8) if total_documents else None,
        "per_file": [{k: v for k, v in r.items() if k != "examples"} for r in per_file],
    }
    out_dir = Path(a.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    with open(out_dir / "examples.jsonl", "w", encoding="utf-8") as f:
        for e in all_examples:
            f.write(json.dumps(e) + "\n")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
