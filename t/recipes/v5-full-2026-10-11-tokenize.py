#!/usr/bin/env python3
"""CPU-only token accounting using the trainer's exact encoder and pinned tokenizer.

Source: https://github.com/trestoncuzzort/dawnr/blob/1994e06a/t/student_sft.py
The previous L4 run supplies a measured calibration, not a guaranteed runtime.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, "t")
import student_sft
from huggingface_hub import snapshot_download
from transformers import AutoTokenizer

ROOT = Path("t/out/v5-full-20261011")
REVISION = "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"


def kind(row):
    value = row.get("kind") or row.get("source") or "unknown"
    return {"graded": "english", "samples": "english", "debug": "repair"}.get(value, value)


def profile(path, tokenizer):
    data = path.read_bytes()
    rows = student_sft.load_rows(path)
    used, dropped = [], []
    for index, row in enumerate(rows):
        encoded = student_sft.encode_row(tokenizer, row, 2**31 - 1)
        entry = {"index": index, "kind": kind(row), "task_id": row.get("task_id"),
                 "name": row.get("name"), "tokens": len(encoded["input_ids"]),
                 "response_tokens": sum(token != -100 for token in encoded["labels"])}
        (used if entry["tokens"] <= 2845 else dropped).append(entry)
    lengths = sorted(row["tokens"] for row in used)
    return {"sha256": hashlib.sha256(data).hexdigest(), "rows": len(rows), "used": len(used),
            "used_kinds": dict(Counter(row["kind"] for row in used)), "dropped": dropped,
            "tokens": sum(lengths), "squared_lengths": sum(n*n for n in lengths),
            "response_tokens": sum(row["response_tokens"] for row in used),
            "median_tokens": lengths[len(lengths)//2], "max_tokens": lengths[-1], "used_rows": used}


def main():
    assert (ROOT / "ROWS-AUDITED").is_file(), "finish audits before forecasting a GPU run"
    snapshot_download("Qwen/Qwen3.5-4B", revision=REVISION, local_dir=ROOT / "tokenizer",
                      allow_patterns=["tokenizer*", "chat_template*", "special_tokens_map.json", "vocab.json", "merges.txt", "config.json"])
    tokenizer = AutoTokenizer.from_pretrained(str(ROOT / "tokenizer"), local_files_only=True)
    current = profile(ROOT / "train-rows.jsonl", tokenizer)
    previous = profile(Path("t/out/gcp-student-2026-10-11-s1/train-rows.jsonl"), tokenizer)
    assert previous["used"] == 405 and previous["rows"] == 406
    ratios = {key: current[key] / previous[key]
              for key in ("used", "tokens", "response_tokens", "squared_lengths")}
    record = {"base_revision": REVISION, "max_len": 2845, "epochs": 5,
              "current": current, "previous": previous, "ratios": ratios,
              "previous_l4_training_seconds": 2462.9,
              "proportional_seconds": {k: 2462.9*v for k, v in ratios.items()},
              "qualification": "Scaling proxies from one completed L4 run; no runtime guarantee.",
              "tokenizer_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in (ROOT / "tokenizer").iterdir() if p.is_file()}}
    (ROOT / "tokenization.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"used": current["used"], "used_kinds": current["used_kinds"],
                      "dropped": len(current["dropped"]), "ratios": ratios,
                      "proportional_seconds": record["proportional_seconds"]}, indent=2))


if __name__ == "__main__":
    main()
