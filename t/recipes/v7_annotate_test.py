#!/usr/bin/env python3
"""The annotation sub-skill test of t/PREDICT-2026-10-19-decomposed-rows.md (prediction P2).

Each held-out row (out/v7/annotate-heldout.jsonl) is asked once, greedily, in its own words through the
pinned llama.cpp server (t/recipes/v6_server_route.py's Decoder, so answers are cached by model identity).
An answer passes when it parses, keeps every non-blank line of the question in order (only annotations
added), and the Dafny kernel verifies it with its twin refuted (t/tlib.py's verify). The same instrument
runs for v5 and for the candidate; the registration compares the two counts.

Sources: the annotation-repair task of https://arxiv.org/html/2610.19298 (the program kept, the
annotations rewritten); t/recipes/v6_server_route.py; t/tlib.py.

    python3 t/recipes/v7_annotate_test.py --heldout out/v7/annotate-heldout.jsonl --endpoint URL \\
        --model NAME --identity ID --cache DIR --out DIR [--kernels dafny] [--max-new 1024]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import surface                                                  # noqa: E402
import tlib                                                     # noqa: E402

BLOCK = re.compile(r"```t\n(.*?)```", re.S)


def load_decoder():
    spec = importlib.util.spec_from_file_location("v6_server_route", HERE / "recipes" / "v6_server_route.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Decoder


def lines_of(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def keeps(question: str, answer: str) -> bool:
    """Every non-blank line of the question appears in the answer, in order."""
    wanted, got, i = lines_of(question), lines_of(answer), 0
    for line in got:
        if i < len(wanted) and line == wanted[i]:
            i += 1
    return i == len(wanted)


def outcome(value) -> str:
    return str(getattr(value, "value", value)).lower()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--heldout", type=Path, required=True)
    ap.add_argument("--endpoint", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--identity", required=True)
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--kernels", default="dafny")
    ap.add_argument("--max-new", type=int, default=1024)
    ap.add_argument("--concurrency", type=int, default=4)
    a = ap.parse_args(argv)
    rows = [json.loads(l) for l in a.heldout.read_text(encoding="utf-8").splitlines() if l.strip()]
    kernels = a.kernels.split(",")
    decoder = load_decoder()(a.endpoint, a.model, a.identity, a.cache, concurrency=a.concurrency)
    replies = decoder.decode(None, None, [r["prompt"] for r in rows], a.max_new, 0.0, 0.95, None)
    a.out.mkdir(parents=True, exist_ok=True)
    results, counts = [], {"asked": len(rows), "block": 0, "parses": 0, "keeps": 0, "verified": 0, "passes": 0}
    for row, (content, stopped, tokens) in zip(rows, replies):
        question = BLOCK.search(row["prompt"][-1]["content"]).group(1)
        entry = {"name": row.get("name"), "parent_sha256": row.get("parent_sha256"), "tokens": tokens,
                 "stopped": stopped, "block": False, "parses": False, "keeps": False, "kernels": {}, "pass": False}
        m = BLOCK.search(content or "")
        if m:
            entry["block"] = True
            counts["block"] += 1
            answer = m.group(1)
            try:
                task = surface.parse(answer)
                entry["parses"] = True
                counts["parses"] += 1
            except Exception as e:                              # noqa: BLE001
                task = None
                entry["why"] = str(e)[:200]
            if task is not None:
                entry["keeps"] = keeps(question, answer)
                counts["keeps"] += entry["keeps"]
                try:
                    verdict = tlib.verify(task, kernels=kernels)
                    entry["kernels"] = {k: {"real": outcome(v.get("real")), "twin": outcome(v.get("twin")),
                                            "provisional": bool(v.get("provisional"))} for k, v in verdict.items()}
                except Exception as e:                          # noqa: BLE001
                    entry["why"] = f"verify: {str(e)[:200]}"
                good = entry["kernels"] and all(v["real"] == "verified" and v["twin"] == "refuted"
                                                 for v in entry["kernels"].values())
                counts["verified"] += bool(good)
                entry["pass"] = bool(good and entry["keeps"])
                counts["passes"] += entry["pass"]
        results.append(entry)
    (a.out / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in results), encoding="utf-8")
    summary = {"identity": a.identity, "heldout": str(a.heldout), "kernels": kernels, **counts}
    (a.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
