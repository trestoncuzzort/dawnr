#!/usr/bin/env python3
"""t/student_rows.py -- "specification given, write the body" rows for the student (2026-10-01).

    python3 t/student_rows.py --corpus t/out/loop/corpus-r12-headed.txt --split t/out/loop/split-v5.json \\
        --out rows.jsonl

The setting every published success uses: the vericoding benchmark (arXiv:2509.22908) gives the
model a formal specification and asks for verified code, and SAFE (arXiv:2410.15756) trains its
student on (program and specification) to proof. Each document of a registered corpus is a `t`
task every kernel proved; this prints it once with an empty body as the question and once in full
as the answer. The header, the parameters, the requires and ensures and the spec funs are given
(they are the specification); the body, its invariants and its decreases are what is asked for.

Rows are t/loop_train.py's and t/student_sft.py's shape (`prompt` messages, `chosen` fenced
answer) with `kind: "spec-given"`. A document named for a held-out, dev or policy-excluded problem
stops the build by name; a registered corpus has none, and this checks instead of assuming.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import loop_dataset                                             # noqa: E402
import loop_filter                                              # noqa: E402
import spec_experiment                                          # noqa: E402
import surface                                                  # noqa: E402

ASK = ("Complete this t task. Keep its header, parameters, requires, ensures and spec funs exactly "
       "as given and write the body, with loop invariants and decreases where there is a loop, so "
       "that the provers can verify it.\n\n")


def documents(corpus_text: str) -> list[dict]:
    """The corpus's tasks, parsed; a document is its optional head lines and one t program."""
    out = []
    for doc in re.split(r"\n\n\n+", corpus_text):
        if not doc.strip():
            continue
        lines = doc.split("\n")
        start = next((k for k, l in enumerate(lines) if re.match(r"^(t [01]$|datatype )", l)), None)
        if start is None:
            raise SystemExit(f"student_rows: a document has no t program: {doc[:80]!r}")
        out.append(surface.parse("\n".join(lines[start:]) + "\n"))
    return out


def blocked_ids(split_path: Path) -> set[int]:
    split = json.loads(split_path.read_text(encoding="utf-8"))
    policy = loop_filter.decontamination()
    return ({int(i) for i in split["eval_ids"]} | set(loop_filter.r12_dev_ids(HERE / "r12-dev-ids.json"))
            | set(policy.exclude_train_ids) | set(policy.overlap_eval_ids))


def row_for(task: dict) -> dict:
    question = surface.print_task(dict(task, body=[])).strip()
    answer = surface.print_task(task).strip()
    return {"kind": "spec-given", "name": task["name"], "source": "corpus",
            "prompt": [{"role": "system", "content": spec_experiment.STUDENT_SYSTEM},
                       {"role": "user", "content": ASK + loop_dataset.fence(question)}],
            "chosen": loop_dataset.fence(answer)}


def build(corpus_path: Path, split_path: Path) -> list[dict]:
    blocked = blocked_ids(split_path)
    rows, seen = [], set()
    for task in documents(corpus_path.read_text(encoding="utf-8")):
        tid = loop_filter.problem_id(task["name"])
        if tid is not None and tid in blocked:
            raise SystemExit(f"student_rows: {task['name']} is a held-out, dev or excluded problem")
        row = row_for(task)
        if row["chosen"] in seen:
            continue
        seen.add(row["chosen"])
        rows.append(row)
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", type=Path, required=True)
    ap.add_argument("--split", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    rows = build(a.corpus, a.split)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
    print(json.dumps({"rows": len(rows), "corpus": str(a.corpus)}))
    return 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
