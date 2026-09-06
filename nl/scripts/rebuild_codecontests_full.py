#!/usr/bin/env python3
"""Rebuild the FULL code_contests extraction (~20.9 GB of JSONL) from HuggingFace.

The repo ships a capped variant — every problem and every test, but at most N
solutions per problem — because the full solution set does not fit in GitHub LFS.
This script reproduces the uncapped original.

    pip install huggingface_hub pyarrow        # in a venv
    python rebuild_codecontests_full.py --out ./cc_full

Downloads ~7.6 GB of parquet, writes ~20.9 GB of JSONL. Field semantics and
ClassLabel decoding are identical to the shipped files, so the capped files are a
strict subset: same rows, same keys, fewer entries in the two solution lists.
"""
import argparse, glob, json, os, sys

SOURCE = ['UNKNOWN_SOURCE','CODECHEF','CODEFORCES','HACKEREARTH','CODEJAM','ATCODER','AIZU']
DIFF = ['UNKNOWN_DIFFICULTY','EASY','MEDIUM','HARD','HARDER','HARDEST','EXTERNAL',
        'A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P','Q','R','S','T','U','V']
LANG = ['UNKNOWN_LANGUAGE','PYTHON','CPP','PYTHON3','JAVA']


def label(names, v):
    return names[v] if isinstance(v, int) and 0 <= v < len(names) else v


def decode_sols(col):
    if not col:
        return []
    return [{"language": label(LANG, l), "solution": s}
            for l, s in zip(col.get("language") or [], col.get("solution") or [])]


def decode_tests(col):
    if not col:
        return []
    return [{"input": i, "output": o}
            for i, o in zip(col.get("input") or [], col.get("output") or [])]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="./cc_full")
    ap.add_argument("--cache", default=None, help="where to put the parquet (default: <out>/raw)")
    ap.add_argument("--keep-parquet", action="store_true")
    args = ap.parse_args()

    try:
        from huggingface_hub import snapshot_download
        import pyarrow.parquet as pq
    except ImportError:
        sys.exit("need: pip install huggingface_hub pyarrow")

    out = os.path.abspath(args.out)
    raw = args.cache or os.path.join(out, "raw")
    os.makedirs(out, exist_ok=True)

    print("downloading parquet (~7.6 GB)...")
    snapshot_download(repo_id="deepmind/code_contests", repo_type="dataset",
                      allow_patterns=["data/*.parquet"], local_dir=raw, max_workers=8)

    for split in ("train", "valid", "test"):
        files = sorted(glob.glob(os.path.join(raw, "data", f"{split}-*.parquet")))
        if not files:
            print(f"!! no parquet for {split}", file=sys.stderr)
            continue
        dest = os.path.join(out, f"codecontests_{split}_full.jsonl")
        n = 0
        with open(dest, "w") as fh:
            for path in files:
                for batch in pq.ParquetFile(path).iter_batches(batch_size=32):
                    for r in batch.to_pylist():
                        tl = r.get("time_limit") or {}
                        fh.write(json.dumps({
                            "name": r.get("name"),
                            "description": r.get("description"),
                            "source": label(SOURCE, r.get("source")),
                            "difficulty": r.get("difficulty"),
                            "difficulty_label": label(DIFF, r.get("difficulty")),
                            "cf_rating": r.get("cf_rating"),
                            "cf_points": r.get("cf_points"),
                            "cf_tags": r.get("cf_tags"),
                            "cf_contest_id": r.get("cf_contest_id"),
                            "cf_index": r.get("cf_index"),
                            "time_limit_seconds": tl.get("seconds"),
                            "time_limit_nanos": tl.get("nanos"),
                            "memory_limit_bytes": r.get("memory_limit_bytes"),
                            "input_file": r.get("input_file"),
                            "output_file": r.get("output_file"),
                            "is_description_translated": r.get("is_description_translated"),
                            "untranslated_description": r.get("untranslated_description"),
                            "public_tests": decode_tests(r.get("public_tests")),
                            "private_tests": decode_tests(r.get("private_tests")),
                            "generated_tests": decode_tests(r.get("generated_tests")),
                            "solutions": decode_sols(r.get("solutions")),
                            "incorrect_solutions": decode_sols(r.get("incorrect_solutions")),
                        }, ensure_ascii=False) + "\n")
                        n += 1
        print(f"{split}: {n} rows -> {dest} ({os.path.getsize(dest)/1e9:.2f} GB)")

    if not args.keep_parquet:
        print(f"(parquet kept at {raw}; delete it to reclaim ~7.6 GB)")


if __name__ == "__main__":
    main()
