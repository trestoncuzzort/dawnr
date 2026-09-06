#!/usr/bin/env python3
"""preference_pairs.py -- chosen/rejected pairs grounded in a judge, not a model.

CodeContests records carry `solutions` and `incorrect_solutions` for the SAME
problem: human submissions that a real online judge accepted, and human
submissions it rejected. That is a preference signal whose label came from
running the code against tests, which is the defence most verifiable-reward
setups lack. ROADMAP WS-12.6 is the consumer.

    python3 scripts/preference_pairs.py                    # counts only
    python3 scripts/preference_pairs.py --out pairs.jsonl  # write them
    python3 scripts/preference_pairs.py --per-problem 4 --lang PYTHON3

Each output line is one pair:

    {"problem": "<name>", "source": "CODEFORCES", "split": "train",
     "difficulty": "EASY", "language": "PYTHON3",
     "prompt": "<problem statement>",
     "chosen": "<accepted submission>", "rejected": "<rejected submission>"}

What this does NOT establish, stated because the labels are the whole value:
nothing here was executed. `solutions` is trusted to be correct and
`incorrect_solutions` to be wrong entirely on upstream's word, exactly as
nl/README.md's third Known Limitation says. A rejected submission may have
failed on a time limit rather than a wrong answer, and the two are not
distinguished upstream, so a pair can encode "slower" rather than "wrong".
Pairing is within one language by default for that reason: a cross-language
pair adds a second difference nobody asked for.

Standard library only, streams the gzip, writes JSONL.
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
SPLITS = ("codecontests_train.jsonl.gz", "codecontests_valid.jsonl.gz",
          "codecontests_test.jsonl.gz")
# Same preference order the corpus used when it capped solutions at 25.
LANG_ORDER = ("PYTHON3", "PYTHON", "CPP", "JAVA")


def by_language(entries):
    """{language: [solution text, ...]} from a list of {language, solution}."""
    out: dict[str, list[str]] = {}
    for e in entries or []:
        out.setdefault(e.get("language", "UNKNOWN_LANGUAGE"), []).append(
            e.get("solution", ""))
    return out


def pairs_for(rec: dict, per_problem: int, want_lang: str | None):
    """Pair accepted against rejected within one language, best language
    first. Returns (pairs, language_used or None)."""
    good = by_language(rec.get("solutions"))
    bad = by_language(rec.get("incorrect_solutions"))
    langs = [want_lang] if want_lang else [
        l for l in LANG_ORDER if l in good and l in bad]
    for lang in langs:
        g, b = good.get(lang) or [], bad.get(lang) or []
        if not g or not b:
            continue
        out = []
        for i in range(min(per_problem, len(g), len(b))):
            out.append({
                "problem": rec.get("name", ""),
                "source": rec.get("source", ""),
                "difficulty": rec.get("difficulty_label", ""),
                "language": lang,
                "prompt": rec.get("description", ""),
                "chosen": g[i],
                "rejected": b[i],
            })
        if out:
            return out, lang
    return [], None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=None,
                    help="write pairs as JSONL here")
    ap.add_argument("--per-problem", type=int, default=4,
                    help="max pairs per problem (default 4)")
    ap.add_argument("--lang", default=None, choices=LANG_ORDER,
                    help="restrict to one language")
    ap.add_argument("--limit", type=int, default=None,
                    help="stop after N problems, for a smoke run")
    args = ap.parse_args(argv)

    have = [s for s in SPLITS if (DATA / s).exists()]
    if not have:
        print("no codecontests splits under %s" % DATA)
        return 1

    langs = Counter()
    sources = Counter()
    n_problems = n_usable = n_pairs = 0
    skipped = Counter()
    sink = args.out.open("w", encoding="utf-8", newline="\n") if args.out else None

    try:
        for split in have:
            with gzip.open(DATA / split, "rt", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    if args.limit and n_problems >= args.limit:
                        break
                    rec = json.loads(line)
                    n_problems += 1
                    if not rec.get("solutions"):
                        skipped["no accepted solution"] += 1
                        continue
                    if not rec.get("incorrect_solutions"):
                        skipped["no rejected solution"] += 1
                        continue
                    ps, lang = pairs_for(rec, args.per_problem, args.lang)
                    if not ps:
                        skipped["no language with both"] += 1
                        continue
                    n_usable += 1
                    n_pairs += len(ps)
                    langs[lang] += len(ps)
                    sources[rec.get("source", "")] += len(ps)
                    if sink:
                        for p in ps:
                            sink.write(json.dumps(p) + "\n")
    finally:
        if sink:
            sink.close()

    print("problems read:            %d" % n_problems)
    print("problems yielding a pair: %d (%.1f%%)"
          % (n_usable, 100 * n_usable / max(1, n_problems)))
    print("pairs built:              %d (at most %d per problem)"
          % (n_pairs, args.per_problem))
    print()
    print("by language:")
    for k, v in langs.most_common():
        print("  %-16s %7d" % (k, v))
    print()
    print("by judge:")
    for k, v in sources.most_common():
        print("  %-16s %7d" % (k, v))
    if skipped:
        print()
        print("problems yielding nothing:")
        for k, v in skipped.most_common():
            print("  %-24s %6d" % (k, v))
    if args.out:
        print()
        print("wrote %s" % args.out)
    print()
    print("Labels are upstream's, unverified: nothing here was executed, and a")
    print("rejected submission may have failed on time rather than on answer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
