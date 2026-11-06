#!/usr/bin/env python3
"""Render the research lists of 2026-11-05 as tables, one section per part of dawnr.

    python3 render.py DIRECTORY

Reads papers.jsonl and repos.jsonl from DIRECTORY, and prints Markdown for internal/RESEARCH-2026-11-05-papers-and-repos.md.
Nothing is reworded here: what a table says is what the list says, and the list is what validate.py checked.
"""
import json
import sys
from collections import Counter
from pathlib import Path

ORDER = ("native-bmc", "spec-quality", "proof-backends", "repair-loop", "constrained-generation", "teacher-data",
         "small-model-training", "evaluation-method", "assistant-runtime", "flight-domain", "documents-reasoning")
TITLES = {"native-bmc": "Native checks of real C", "spec-quality": "Specification quality", "proof-backends": "The seven proof back ends",
          "repair-loop": "Repair and search budgets", "constrained-generation": "Constrained generation", "teacher-data": "Teacher and training data",
          "small-model-training": "Training a small model", "evaluation-method": "Evaluation method", "assistant-runtime": "The assistant's runtime",
          "flight-domain": "Flight software and floating point", "documents-reasoning": "Documents and checked reasoning"}


def cell(text) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def order_key(row: dict):
    return ({"A": 0, "B": 1, "C": 2}[row["tier"]], str(row.get("id", row.get("repo", ""))).lower())


def main() -> None:
    root = Path(sys.argv[1])
    papers, repos = load(root / "papers.jsonl"), load(root / "repos.jsonl")
    print("| part of dawnr | papers (tier A) | repositories (tier A) |\n|---|---:|---:|")
    for name in ORDER:
        p, r = [row for row in papers if row["subsystem"] == name], [row for row in repos if row["subsystem"] == name]
        print(f"| [{TITLES[name]}](#{TITLES[name].lower().replace(' ', '-').replace(chr(39), '')}) | {len(p)} ({sum(row['tier'] == 'A' for row in p)}) | {len(r)} ({sum(row['tier'] == 'A' for row in r)}) |")
    print(f"| all | {len(papers)} ({sum(row['tier'] == 'A' for row in papers)}) | {len(repos)} ({sum(row['tier'] == 'A' for row in repos)}) |")
    print("\nLicences of the repositories: " + ", ".join(f"{name} {count}" for name, count in Counter(row["spdx"] for row in repos).most_common()) + ".\n")
    for name in ORDER:
        print(f"\n## {TITLES[name]}\n")
        rows = sorted((row for row in repos if row["subsystem"] == name), key=order_key)
        if rows:
            print("### Repositories\n\n| | repository | licence | what to take | into |\n|---|---|---|---|---|")
            for row in rows:
                print(f"| {row['tier']} | [{row['repo']}]({row['url']}/tree/{row['commit'][:12]}) | {row['spdx']} | {cell(row['take'])} | `{cell(row['dawnr_target'])}` |")
        rows = sorted((row for row in papers if row["subsystem"] == name), key=order_key)
        if rows:
            print("\n### Papers\n\n| | paper | what it reports | what to take | into |\n|---|---|---|---|---|")
            for row in rows:
                print(f"| {row['tier']} | [{cell(row['title'])}]({row['url']}) ({row['first_author']}, {row['year']}, {cell(row['venue'])}) | {cell(row['claim'])} | {cell(row['take'])} | `{cell(row['dawnr_target'])}` |")


if __name__ == "__main__":
    main()
