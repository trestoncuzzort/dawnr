#!/usr/bin/env python3
"""t/udebug_rows.py -- merge the gate's rows across teacher lanes into one training set (2026-10-12).

    python3 t/udebug_rows.py --bank t/out/udebug/bank.jsonl --out t/out/udebug/rows-judge-python.jsonl \\
        --pairs-out t/out/udebug/pairs-judge-python.jsonl --heldout-out t/out/udebug/heldout-questions.jsonl \\
        t/out/udebug/teacher-deepseek-udebug-py-scale t/out/udebug/teacher-qwen235-udebug-py-scale

Each lane directory holds the rows its gate wrote (`rows.jsonl`, `pairs.jsonl`); a problem answered by two
teachers has rows in both. This joins them under ReST-EM's cap (arXiv:2312.06585 kept at most 10 solutions
per problem; --cap, default 4) with the same program text kept once per problem, refuses any row whose
problem the bank does not mark `split: train` (the hash held-out and the hand-solved `measured` set never
train), and writes the held-out problems as a question set (statement, sample, the same system text) with no
answer, for the student to be measured on later by the same gate. Kinds are kept as they are (`judge-python`
beside the proof kinds), and every row records its lane.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import udebug_teacher as ut   # noqa: E402  (PYTHON_CONTRACT, user_text)


def load_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("lanes", nargs="+", help="teacher output directories with rows.jsonl and pairs.jsonl")
    ap.add_argument("--bank", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pairs-out", default="")
    ap.add_argument("--heldout-out", default="")
    ap.add_argument("--cap", type=int, default=4, help="rows kept per problem across lanes")
    ap.add_argument("--pair-cap", type=int, default=4)
    ap.add_argument("--kinds", default="", help="comma-separated kinds to keep (default: all)")
    a = ap.parse_args(argv)
    kinds = {k for k in a.kinds.split(",") if k}

    bank = {}
    with open(a.bank, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            bank[f"{r['judge']}/{r['id']}"] = r

    kept: dict[str, list[dict]] = collections.defaultdict(list)
    seen: dict[str, set[str]] = collections.defaultdict(set)
    pairs: dict[str, list[dict]] = collections.defaultdict(list)
    refused = collections.Counter()
    per_lane = collections.Counter()
    for lane in a.lanes:
        lane_path = Path(lane)
        # OpenAI's usage terms forbid training competing models on its outputs: a lane whose records name
        # that provider is refused here by name, whatever its rows say (the submission bundle may still use them).
        probe = next(iter(lane_path.glob("*/s*/record.json")), None)
        if probe is not None and json.loads(probe.read_text(encoding="utf-8")).get("provider") == "openai":
            refused["openai-lane"] += 1
            print(f"refused lane {lane}: provider openai (its outputs may not train a model)", file=sys.stderr)
            continue
        for row in load_jsonl(lane_path / "rows.jsonl"):
            if kinds and row.get("kind") not in kinds:
                continue
            key = row["problem"]
            b = bank.get(key)
            if b is None or b.get("split") != "train" or b.get("hand_solved"):
                refused["not-train"] += 1
                continue
            text = row["chosen"].strip()
            if text in seen[key]:
                refused["duplicate"] += 1
                continue
            if len(kept[key]) >= a.cap:
                refused["over-cap"] += 1
                continue
            seen[key].add(text)
            kept[key].append(dict(row, lane=lane_path.name))
            per_lane[lane_path.name] += 1
        for pair in load_jsonl(lane_path / "pairs.jsonl"):
            if kinds and pair.get("kind") not in kinds:
                continue
            key = pair["problem"]
            b = bank.get(key)
            if b is None or b.get("split") != "train" or b.get("hand_solved"):
                refused["pair-not-train"] += 1
                continue
            if len(pairs[key]) >= a.pair_cap:
                refused["pair-over-cap"] += 1
                continue
            pairs[key].append(dict(pair, lane=lane_path.name))

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    n_rows = 0
    with out.open("w", encoding="utf-8") as f:
        for key in sorted(kept):
            for row in kept[key]:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                n_rows += 1
    n_pairs = 0
    if a.pairs_out:
        with open(a.pairs_out, "w", encoding="utf-8") as f:
            for key in sorted(pairs):
                for pair in pairs[key]:
                    f.write(json.dumps(pair, ensure_ascii=False) + "\n")
                    n_pairs += 1
    n_held = 0
    if a.heldout_out:
        with open(a.heldout_out, "w", encoding="utf-8") as f:
            for key, b in sorted(bank.items()):
                if b.get("split") != "heldout" or not b.get("statement") or b.get("n_scored", 0) == 0:
                    continue
                if b["judge"] != "UVa":
                    continue
                f.write(json.dumps({"problem": key, "name": f"p{b['id']}", "kind": "judge-python-question",
                                    "tests_dir": b["tests_dir"],
                                    "prompt": [{"role": "system", "content": ut.PYTHON_CONTRACT},
                                               {"role": "user", "content": ut.user_text(b, "python")}]},
                                   ensure_ascii=False) + "\n")
                n_held += 1
    by_kind = collections.Counter(r["kind"] for rows in kept.values() for r in rows)
    summary = {"rows": n_rows, "problems": len(kept), "by_kind": dict(by_kind), "by_lane": dict(per_lane),
               "pairs": n_pairs, "pair_problems": len(pairs), "heldout_questions": n_held,
               "refused": dict(refused), "cap": a.cap}
    out.with_name(out.stem + "-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
