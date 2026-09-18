#!/usr/bin/env python3
"""t/grammar_check.py -- is t.gbnf the same language t/surface.py accepts? (2026-09-18, WS-21)

    python3 t/grammar_check.py [--grammar t/t.gbnf] [--refused 500] [--verbose]

A generator decoding against [`t/t.gbnf`](t.gbnf) can only write what that grammar allows, so the grammar has
to be the notation and not a cousin of it. Two directions, both of which must hold, and
t/PREREG-2026-09-18-constrained.md forbids either arm running until they do:

  1. Everything the parser accepts, the grammar accepts. Measured over every committed task in t/tasks and
     every answer that became a task in t/out/spec-experiment/*/tasks, printed by surface.print_task, which is
     the canonical form; and over the raw reply text of those same answers, which is what a model actually
     writes -- spacing, line breaks and all.
  2. Everything the parser refuses, the grammar refuses. Measured over a sample of the replies recorded with
     stage "parse" in each set's extract.json. A grammar looser than the parser would move an answer from
     refused to refused-later, which is not the thing being bought.

Needs xgrammar (the backend vLLM decodes with), so it runs where vLLM is installed: on the lab workstation,
`~/.venv-vllm/bin/python t/grammar_check.py`. Everything else here is standard library.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness                                                  # noqa: E402
import surface                                                  # noqa: E402

SE = HERE / "out" / "spec-experiment"


def accepts(grammar, text: str) -> bool:
    from xgrammar.testing import _is_grammar_accept_string
    try:
        return bool(_is_grammar_accept_string(grammar, text))
    except Exception:                                           # noqa: BLE001
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--grammar", type=Path, default=HERE / "t.gbnf")
    ap.add_argument("--refused", type=int, default=500, help="how many refused replies to test (0 for all)")
    ap.add_argument("--verbose", action="store_true", help="print every disagreement, not the first few")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    try:
        from xgrammar import Grammar
    except ImportError:
        print("xgrammar is not installed here; run this where vLLM is (~/.venv-vllm/bin/python)")
        return 2
    # a GBNF comment is '#' to end of line, which xgrammar does not strip for us
    text = "\n".join(line for line in a.grammar.read_text(encoding="utf-8").splitlines()
                     if not line.lstrip().startswith("#"))
    try:
        g = Grammar.from_ebnf(text)
    except Exception as e:                                      # noqa: BLE001
        print(f"the grammar itself does not load: {e}")
        return 1

    print("1. every program the parser accepts, the grammar accepts")
    bad_canon, bad_raw, n_canon, n_raw = [], [], 0, 0
    tasks = sorted(HERE.glob("tasks/*.t")) + sorted(SE.glob("*/tasks/*.json"))
    for p in tasks:
        try:
            printed = surface.print_task(harness.load(p) if p.suffix == ".json" else surface.parse_file(str(p)))
        except Exception:                                       # noqa: BLE001
            continue
        n_canon += 1
        if not accepts(g, printed):
            bad_canon.append(p)
    print(f"   canonical form: {n_canon - len(bad_canon)} of {n_canon} accepted")

    # the same answers as the model wrote them, before the printer touched them
    import spec_experiment as se
    for d in sorted(SE.glob("*")):
        try:
            ex = json.loads((d / "extract.json").read_text())
        except (OSError, ValueError):
            continue
        for tid, v in ex.items():
            if v.get("stage") != "task":
                continue
            raw = d / "raw" / f"{tid}.json"
            if not raw.exists():
                continue
            try:
                block = se.find_block(json.loads(raw.read_text())["reply"]) or ""
            except (OSError, ValueError, KeyError):
                continue
            n_raw += 1
            if not accepts(g, block):
                bad_raw.append(f"{d.name}/{tid}")
    print(f"   as the model wrote it: {n_raw - len(bad_raw)} of {n_raw} accepted")
    for p in (bad_canon if a.verbose else bad_canon[:5]):
        print(f"     REFUSED BY THE GRAMMAR: {p}")
    for p in (bad_raw if a.verbose else bad_raw[:5]):
        print(f"     REFUSED BY THE GRAMMAR (raw): {p}")

    print("2. every reply the parser refuses, the grammar refuses")
    pool = []
    for d in sorted(SE.glob("*")):
        try:
            ex = json.loads((d / "extract.json").read_text())
        except (OSError, ValueError):
            continue
        for tid, v in ex.items():
            if v.get("stage") == "parse" and (d / "raw" / f"{tid}.json").exists():
                pool.append((d, tid))
    random.Random(a.seed).shuffle(pool)
    if a.refused:
        pool = pool[:a.refused]
    loose = []
    for d, tid in pool:
        try:
            block = se.find_block(json.loads((d / "raw" / f"{tid}.json").read_text())["reply"]) or ""
        except (OSError, ValueError, KeyError):
            continue
        if accepts(g, block):
            loose.append(f"{d.name}/{tid}")
    print(f"   {len(pool) - len(loose)} of {len(pool)} refused replies are refused by the grammar too")
    for p in (loose if a.verbose else loose[:5]):
        print(f"     ACCEPTED BY THE GRAMMAR BUT NOT THE PARSER: {p}")

    ok = not bad_canon and not bad_raw and not loose
    print("\n" + ("the grammar and the parser agree on every program tested" if ok else
                  "they disagree; the preregistration forbids generating until they do not"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
