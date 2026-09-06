#!/usr/bin/env python3
"""corpus_audit.py -- put numbers on the three Known Limitations.

nl/README.md names three things nobody had measured: no cross-source
deduplication, no decontamination, and nothing executed. This measures the
first two and says exactly what it cannot measure about the third. A
limitation with a number beside it is a fact; without one it is a worry.

    python3 scripts/corpus_audit.py                 # all sections
    python3 scripts/corpus_audit.py --dedup         # cross-source overlap
    python3 scripts/corpus_audit.py --contam        # benchmark leakage
    python3 scripts/corpus_audit.py --json OUT      # machine-readable

Method, stated so the numbers can be argued with:

DEDUP compares problem STATEMENTS, not solutions. Each statement is
normalised (casefold, collapse whitespace, drop punctuation) and hashed. Two
problems collide when their normalised statements are byte-identical. That is
a floor, not a ceiling: it finds verbatim reuse and misses paraphrase, so the
overlap reported here is the least overlap there is.

CONTAM asks the leakage question the README raises: does a problem in an
EVALUATION split (humaneval, mbpp_test) also appear in a split someone might
train on (apps_*, codecontests_*, mbpp, mbpp_validation, mbpp_prompt)? Same
normalisation, same floor. This measures overlap WITHIN this corpus only. It
says nothing about the pretraining corpora these benchmarks are famously
inside, which is a larger problem no local computation can settle.

Standard library only. Streams the gzip, never decompresses to disk, and
holds only hashes plus short keys, so the 918 MB costs memory in the tens of
megabytes.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

# Which field carries the problem statement, per source.
STATEMENT_FIELD = {
    "apps_raw_train.jsonl.gz": "question",
    "apps_raw_test.jsonl.gz": "question",
    "codecontests_train.jsonl.gz": "description",
    "codecontests_test.jsonl.gz": "description",
    "codecontests_valid.jsonl.gz": "description",
    "mbpp.jsonl.gz": "text",
    "mbpp_test.jsonl.gz": "text",
    "mbpp_validation.jsonl.gz": "text",
    "mbpp_prompt.jsonl.gz": "text",
    "humaneval.jsonl.gz": "prompt",
}

SOURCE_OF = {
    "apps_raw_train.jsonl.gz": "APPS",
    "apps_raw_test.jsonl.gz": "APPS",
    "codecontests_train.jsonl.gz": "CodeContests",
    "codecontests_test.jsonl.gz": "CodeContests",
    "codecontests_valid.jsonl.gz": "CodeContests",
    "mbpp.jsonl.gz": "MBPP",
    "mbpp_test.jsonl.gz": "MBPP",
    "mbpp_validation.jsonl.gz": "MBPP",
    "mbpp_prompt.jsonl.gz": "MBPP",
    "humaneval.jsonl.gz": "HumanEval",
}

# Splits a coverage or training claim would EVALUATE on.
EVAL_SPLITS = {"humaneval.jsonl.gz", "mbpp_test.jsonl.gz"}

_PUNCT = re.compile(r"[^\w\s]+")
_WS = re.compile(r"\s+")


def normalise(text: str) -> str:
    """Casefold, drop punctuation, collapse whitespace. Deliberately crude:
    the point is a floor on verbatim reuse, not a similarity metric."""
    return _WS.sub(" ", _PUNCT.sub(" ", (text or "").casefold())).strip()


def statement_hashes(split: str):
    """Yield (hash, key) per record, streaming."""
    path = DATA / split
    if not path.exists():
        return
    field = STATEMENT_FIELD[split]
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if not line.strip():
                continue
            rec = json.loads(line)
            norm = normalise(rec.get(field, ""))
            if len(norm) < 24:
                # Too short to be evidence of anything. MBPP's one-liners are
                # ~50 chars, so this only drops degenerate records.
                continue
            h = hashlib.sha1(norm.encode("utf-8")).hexdigest()
            key = rec.get("task_id", rec.get("name", rec.get("id", i)))
            yield h, "%s:%s" % (split, key)


def build_index(splits):
    """hash -> [keys], plus per-split record counts."""
    index = defaultdict(list)
    counts = {}
    for split in splits:
        n = 0
        for h, key in statement_hashes(split):
            index[h].append(key)
            n += 1
        counts[split] = n
        print("  indexed %-34s %6d statements" % (split, n), file=sys.stderr)
    return index, counts


def dedup_report(index, counts):
    """Collisions, and how many cross a source boundary."""
    dup_groups = {h: ks for h, ks in index.items() if len(ks) > 1}
    cross = {}
    within = {}
    pairs = defaultdict(int)
    for h, ks in dup_groups.items():
        srcs = {SOURCE_OF[k.split(":")[0]] for k in ks}
        if len(srcs) > 1:
            cross[h] = ks
            for a in sorted(srcs):
                for b in sorted(srcs):
                    if a < b:
                        pairs["%s / %s" % (a, b)] += 1
        else:
            within[h] = ks
    total = sum(counts.values())
    dup_records = sum(len(ks) for ks in dup_groups.values())
    return {
        "statements_indexed": total,
        "distinct_statements": len(index),
        "duplicate_groups": len(dup_groups),
        "records_in_a_duplicate_group": dup_records,
        "groups_crossing_a_source": len(cross),
        "groups_within_one_source": len(within),
        "cross_source_pairs": dict(sorted(pairs.items(), key=lambda kv: -kv[1])),
        "examples": [ks for ks in list(cross.values())[:5]],
    }


def contam_report(index):
    """Eval-split statements that also appear in a trainable split."""
    out = {}
    for split in sorted(EVAL_SPLITS):
        leaked, total = [], 0
        for h, key in statement_hashes(split):
            total += 1
            others = [k for k in index.get(h, []) if not k.startswith(split)]
            if others:
                leaked.append({"eval": key, "also_in": others[:4]})
        out[split] = {
            "records": total,
            "also_present_elsewhere": len(leaked),
            "share": (len(leaked) / total) if total else 0.0,
            "examples": leaked[:5],
        }
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dedup", action="store_true")
    ap.add_argument("--contam", action="store_true")
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args(argv)
    do_all = not (args.dedup or args.contam)

    splits = [s for s in STATEMENT_FIELD if (DATA / s).exists()]
    if not splits:
        print("no data under %s" % DATA)
        return 1

    print("indexing problem statements", file=sys.stderr)
    index, counts = build_index(splits)
    report = {}

    if do_all or args.dedup:
        d = dedup_report(index, counts)
        report["dedup"] = d
        print()
        print("== Cross-source deduplication ==")
        print("statements indexed:              %d" % d["statements_indexed"])
        print("distinct after normalisation:    %d" % d["distinct_statements"])
        print("duplicate groups:                %d" % d["duplicate_groups"])
        print("records inside one:              %d (%.2f%%)"
              % (d["records_in_a_duplicate_group"],
                 100 * d["records_in_a_duplicate_group"]
                 / max(1, d["statements_indexed"])))
        print("groups crossing a source:        %d" % d["groups_crossing_a_source"])
        print("groups within one source:        %d" % d["groups_within_one_source"])
        if d["cross_source_pairs"]:
            print("which sources overlap:")
            for k, n in d["cross_source_pairs"].items():
                print("  %-30s %d" % (k, n))

    if do_all or args.contam:
        c = contam_report(index)
        report["contamination"] = c
        print()
        print("== Decontamination, within this corpus only ==")
        for split, r in c.items():
            print("%-24s %4d records, %3d also appear in a trainable split (%.1f%%)"
                  % (split, r["records"], r["also_present_elsewhere"],
                     100 * r["share"]))
        print()
        print("This bounds leakage INSIDE nl/ only. These benchmarks sit in")
        print("many pretraining corpora, which no local computation settles.")

    if args.json:
        args.json.write_text(json.dumps(report, indent=2), encoding="utf-8",
                             newline="\n")
        print()
        print("wrote %s" % args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
