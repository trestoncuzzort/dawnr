#!/usr/bin/env python3
"""Decompose the corrected v6 training snapshot into sub-task rows (queue row 1 of
internal/RESEARCH-2026-10-19-number-one-fv.md), registered in t/PREDICT-2026-10-19-decomposed-rows.md.

Sources: ATLAS splits each verified program into six sub-task rows and keeps failed attempts
(arXiv:2512.10173, https://arxiv.org/html/2512.10173, table 1); verifier-grounded RL finds the
largest 4B gain on annotation repair (arXiv:2610.19298, https://arxiv.org/html/2610.19298, its
results table). The snapshot already carries specification rows (t/spec_first_rows.py, 502),
specification-given rows (1,114) and repair rows (552); what it lacks is the annotation sub-task.

    python3 t/recipes/v7_decomposed_rows.py --rows SNAPSHOT.jsonl --sha256 HEX --out out/v7

Writes out/v7/v7-rows.jsonl (the snapshot's rows, then the new ones), out/v7/annotate-heldout.jsonl
(one in ten eligible programs by name, never trained on, the sub-skill's own test) and
out/v7/decomposition.json (counts and digests).

An annotation row: the admitted program with every `invariant`, `decreases` and `assert` line removed
is the question; the admitted program, verbatim, is the answer. Only programs that lose at least one
line inside a loop, a lemma or a body count; a program whose only annotation is a spec fun's
`decreases` is left out. Specification rows for admitted programs that still lack one are built with
t/spec_first_rows.build, in the route's own words, and kept only when the pair is new.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import spec_experiment as se                                    # noqa: E402
import spec_first_rows                                          # noqa: E402

BLOCK = re.compile(r"```t\n(.*?)```", re.S)
ANNOTATION = re.compile(r"^[ \t]*(?:invariant|decreases)\b[^\n]*\n", re.M)
ASSERT = re.compile(r"^[ \t]*assert\b[^\n]*;[ \t]*\n", re.M)
SPEC_FUN_DECREASES = re.compile(r"^spec fun[^\n]*\n(?:[ \t]+(?:requires|ensures|decreases)\b[^\n]*\n)*", re.M)
QUESTION = ("Complete the proof annotations of this t task. Keep its header, parameters, requires, ensures, "
            "spec funs, lemmas and every statement exactly as given, and add the loop invariants, decreases "
            "clauses and assertions the provers need, so that they can verify it.\n\n")
NL_SOURCES = ("graded", "samples", "spec", "proof-py")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def program_of(chosen: str) -> str | None:
    m = BLOCK.search(chosen)
    return m.group(1) if m else None


def stripped(program: str) -> str | None:
    """The program without its annotations, or None when nothing outside a spec fun's header is removed."""
    heads = [m.group(0) for m in SPEC_FUN_DECREASES.finditer(program)]
    inside_heads = sum(len(ANNOTATION.findall(h)) for h in heads)
    removed = len(ANNOTATION.findall(program)) + len(ASSERT.findall(program))
    if removed - inside_heads <= 0:
        return None
    return ASSERT.sub("", ANNOTATION.sub("", program))


def annotation_rows(rows: list[dict]) -> tuple[list[dict], list[dict], dict]:
    seen, eligible = set(), []
    for r in rows:
        if r.get("kind") == "judge-python" or not isinstance(r.get("chosen"), str):
            continue
        program = program_of(r["chosen"])
        if not program:
            continue
        key = hashlib.sha256(program.encode()).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        question = stripped(program)
        if question is None:
            continue
        system = r["prompt"][0] if r["prompt"] and r["prompt"][0]["role"] == "system" else None
        if system is None:
            continue
        eligible.append({"kind": "annotate", "source": "decomposed", "name": r.get("name"),
                         "task_id": r.get("task_id"), "tag": r.get("tag"),
                         "kernels_verified": r.get("kernels_verified"), "undecided": r.get("undecided"),
                         "parent_sha256": key,
                         "prompt": [system, {"role": "user", "content": QUESTION + "```t\n" + question + "```"}],
                         "chosen": "```t\n" + program + "```"})
    names = sorted({e["name"] or "" for e in eligible})
    held_names = set(names[9::10])
    held = [e for e in eligible if (e["name"] or "") in held_names]
    train = [e for e in eligible if (e["name"] or "") not in held_names]
    report = {"eligible programs": len(eligible), "names": len(names), "held-out names": len(held_names),
              "held-out rows": len(held), "training rows": len(train),
              "by parent kind": dict(Counter(str(r.get("kind")) for r in train))}
    return train, held, report


def missing_spec_rows(rows: list[dict], pool: dict) -> tuple[list[dict], dict]:
    existing = {(json.dumps(r["prompt"], sort_keys=True), r["chosen"]) for r in rows}
    nl = [r for r in rows if r.get("kind") is None and r.get("source") in NL_SOURCES
          and r.get("task_id") is not None and int(r["task_id"]) in pool
          and isinstance(r.get("chosen"), str) and se.find_block(r["chosen"])]
    built, report = spec_first_rows.build(nl, pool)
    new = [r for r in built if r["source"] == "spec"
           and (json.dumps(r["prompt"], sort_keys=True), r["chosen"]) not in existing]
    for r in new:
        r["kind"] = None
        r["source"] = "spec"
        r["decomposed"] = True
    return new, {"candidates": report.get("spec", 0), "new": len(new)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", type=Path, required=True)
    ap.add_argument("--sha256", required=True, help="the snapshot's digest, checked before anything is read")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--pool", choices=se.POOL_VERSIONS, default="v5")
    a = ap.parse_args(argv)
    if digest(a.rows) != a.sha256:
        raise SystemExit("the snapshot's digest differs from --sha256")
    rows = [json.loads(l) for l in a.rows.read_text(encoding="utf-8").splitlines() if l.strip()]
    train, held, ann_report = annotation_rows(rows)
    specs, spec_report = missing_spec_rows(rows, se.pool(a.pool))
    a.out.mkdir(parents=True, exist_ok=True)
    out_rows = a.out / "v7-rows.jsonl"
    out_rows.write_text("".join(json.dumps(r) + "\n" for r in rows + train + specs), encoding="utf-8")
    (a.out / "annotate-heldout.jsonl").write_text("".join(json.dumps(r) + "\n" for r in held), encoding="utf-8")
    report = {"input": {"path": str(a.rows), "sha256": a.sha256, "rows": len(rows)},
              "annotation": ann_report, "specification": spec_report,
              "output": {"path": str(out_rows), "rows": len(rows) + len(train) + len(specs),
                         "sha256": digest(out_rows)},
              "held_out": {"path": str(a.out / "annotate-heldout.jsonl"), "rows": len(held),
                           "sha256": digest(a.out / "annotate-heldout.jsonl")}}
    (a.out / "decomposition.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
