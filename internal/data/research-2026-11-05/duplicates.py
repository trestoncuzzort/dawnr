#!/usr/bin/env python3
"""How much of a training set is distinct? Exact and with names erased, per kind of row.

    python3 internal/data/research-2026-11-05/duplicates.py t/out/v5-full-20261011/train-rows.jsonl

Exploratory: written to look, with no prediction before it. Erasing names follows the identical-references-with-names-erased check in
t/DECONTAMINATION-2026-09-21.md, and the idea of filtering duplicates before training is `bigcode-project/selfcodealign` and `MinishLab/semhash` on the
list beside this file. It counts repeats. It does not say a repeat is harmful: a repair row and a graded row may share a target on purpose.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import sys

KEYWORDS = {"t", "task", "returns", "requires", "ensures", "invariant", "decreases", "var", "if", "else", "while", "for", "in", "return", "forall", "exists", "and", "or", "not", "true", "false",
            "int", "bool", "seq", "string", "pair", "len", "function", "predicate", "old", "result", "assert", "assume", "ghost", "lemma", "fst", "snd", "then", "let", "implies", "iff"}
TOKEN = re.compile(r"[A-Za-z_][A-Za-z_0-9]*|\S")


def body(text: str) -> str:
    """The target without its fence and without the spacing."""
    match = re.search(r"```[a-z]*\n(.*?)```", text, re.S)
    return " ".join((match.group(1) if match else text).split())


def erased(text: str) -> str:
    """Every name replaced by the order it first appears in, so two copies that differ only in names read the same."""
    seen: dict[str, str] = {}
    out = []
    for token in TOKEN.findall(body(text)):
        if re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", token) and token not in KEYWORDS:
            out.append(seen.setdefault(token, f"v{len(seen)}"))
        else:
            out.append(token)
    return " ".join(out)


def main() -> None:
    rows = [json.loads(line) for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if line.strip()]
    kinds = defaultdict(list)
    for row in rows:
        kinds[row.get("source", "?")].append(row)
    print(f"{len(rows)} rows")
    print(f"{'kind':12} {'rows':>6} {'distinct target':>16} {'distinct, names erased':>23} {'distinct prompt':>16} {'distinct problem':>17}")
    for kind, group in sorted([*kinds.items(), ("all", rows)], key=lambda item: -len(item[1])):
        print(f"{kind:12} {len(group):6} {len({body(row['chosen']) for row in group}):16} {len({erased(row['chosen']) for row in group}):23} "
              f"{len({str(row['prompt']) for row in group}):16} {len({row.get('task_id') for row in group}):17}")
    # The targets a model would see most often, whole, and in how many distinct problems.
    counts = Counter(erased(row["chosen"]) for row in rows)
    print("\nmost repeated targets, names erased:")
    for text, count in counts.most_common(8):
        problems = len({row.get("task_id") for row in rows if erased(row["chosen"]) == text})
        print(f"{count:5} rows, {problems:4} problems: {text[:120]}")
    shared = sum(count for count in counts.values() if count > 1)
    print(f"\nrows whose target, names erased, also appears in another row: {shared} of {len(rows)} ({100 * shared / len(rows):.1f}%)")
    print(f"rows removed if each such target were kept once: {len(rows) - len(counts)} ({100 * (len(rows) - len(counts)) / len(rows):.1f}%)")


if __name__ == "__main__":
    main()
