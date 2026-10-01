#!/usr/bin/env python3
"""t/spec_first_rows.py -- training rows for the specification written first (2026-10-01).

    python3 t/spec_first_rows.py --pool-rows sft-graded-k1-s2.jsonl --out spec-first-rows.jsonl

SAFE trains its two stages on two kinds of example (arXiv:2410.15756, 3.2 and 3.3): for
specification synthesis the model is given "the function's implementation and docstring" and
writes preconditions and postconditions; for proof synthesis it is given the function and its
specification and writes the proof. A fine-tuned student here has been shown only the whole job
at once (English to a finished task) and the second half (a specification to its body).

Every row of the graded pool (t/graded_pool.py: a training problem's answer that passes its
tests, is proved by at least one kernel with none refuting, and whose specification agrees with
the reference) carries what three more kinds of row need, because the problem comes with its own
Python solution:

  python     the problem and its tests            -> the Python solution
  spec       the problem, its tests, the Python   -> the task with an empty body
  proof-py   the specification and the Python     -> the finished task

The Python is the high-resource half: a model that has never seen `t` already writes it, and a
solution can be checked by running the problem's tests (t/py_sandbox.py). At inference the
student's own tested Python stands where the reference stands here.

Only training problems appear: the pool rows are built from them alone, and this file reads
nothing else. One python row a problem, one spec row a distinct specification, one proof-py row
a pool row.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import loop_dataset                                             # noqa: E402
import spec_experiment as se                                    # noqa: E402
import student_rows                                             # noqa: E402
import surface                                                  # noqa: E402

PY_SYSTEM = "You write Python. Reply with one fenced python block and nothing else."
SPEC_SYSTEM = ("You write specifications in t, a small verified language. Reply with one fenced t task whose "
               "body is empty and nothing else: the header line, the task with the requested name and "
               "parameters, and requires and ensures clauses that specify the result, with spec funs where "
               "they are needed.")


def python_block(code: str) -> str:
    return "```python\n" + code.strip("\n") + "\n```"


def _statement(entry: dict) -> str:
    r = entry["rec"]
    return f"Problem: {r['text'].strip()}\n\nTests:\n" + "\n".join(r["test_list"])


def python_question(entry: dict) -> list[dict]:
    return [{"role": "system", "content": PY_SYSTEM},
            {"role": "user", "content": _statement(entry) + f"\n\nWrite a Python function named `{entry['fn']}` "
                                                             "that passes the tests."}]


def spec_question(entry: dict, code: str) -> list[dict]:
    arity, kinds, ret = se.signature_words(entry, surface=True)
    return [{"role": "system", "content": SPEC_SYSTEM},
            {"role": "user", "content": _statement(entry) + "\n\nA Python solution:\n" + python_block(code) +
             f"\n\nWrite the specification of the t task named `{entry['fn']}` with {arity} parameter(s) of "
             f"type(s) {kinds}, in the order the tests pass them, returning {ret}: the ensures must specify "
             "the result, and the body stays empty."}]


def proof_question(spec: dict, code: str) -> list[dict]:
    return [{"role": "system", "content": se.STUDENT_SYSTEM},
            {"role": "user", "content": student_rows.ASK + loop_dataset.fence(surface.print_task(spec).strip()) +
             "\n\nA Python solution to the same problem:\n" + python_block(code)}]


def specification_of(task: dict) -> dict:
    spec = dict(task, body=[])
    if "lemmas" in spec:
        spec["lemmas"] = []
    return spec


def build(pool_rows: list[dict], pool: dict) -> tuple[list[dict], dict]:
    rows, seen_python, seen_spec, counts = [], set(), set(), Counter()
    for r in pool_rows:
        tid = int(r["task_id"])
        entry = pool[tid]
        code = (entry["rec"].get("code") or "").strip("\n")
        if not code.strip():
            counts["no python solution"] += 1
            continue
        task = surface.parse(se.find_block(r["chosen"]))
        spec = specification_of(task)
        spec_text = loop_dataset.fence(surface.print_task(spec).strip())
        base = {"task_id": tid, "tag": r.get("tag"), "name": r.get("name"),
                "kernels_verified": r.get("kernels_verified"), "undecided": r.get("undecided")}
        if tid not in seen_python:
            seen_python.add(tid)
            rows.append({**base, "source": "python", "prompt": python_question(entry), "chosen": python_block(code)})
            counts["python"] += 1
        if (tid, spec_text) not in seen_spec:
            seen_spec.add((tid, spec_text))
            rows.append({**base, "source": "spec", "prompt": spec_question(entry, code), "chosen": spec_text})
            counts["spec"] += 1
        rows.append({**base, "source": "proof-py", "prompt": proof_question(spec, code), "chosen": r["chosen"]})
        counts["proof-py"] += 1
    return rows, {"pool_rows": len(pool_rows), "problems": len(seen_python), **counts}


def build_from_specs(kept: list[dict], pool: dict, skip: set[int]) -> tuple[list[dict], dict]:
    """python and spec rows for problems that have a kept specification and no proved answer:
    t/spec_first.py --reference-python writes them (kept by the problem's own tests AND by the
    reference check), and a right specification teaches specification writing whether or not a
    proof for it exists yet (SAFE keeps up to three a function, arXiv:2410.15756 3.2). Problems
    in `skip` (the pool's, which already give rows) are left out."""
    rows, counts = [], Counter()
    for k in kept:
        tid = int(k["task_id"])
        if tid in skip:
            counts["already in the pool"] += 1
            continue
        entry = pool[tid]
        code = (entry["rec"].get("code") or "").strip("\n")
        if not code.strip():
            continue
        base = {"task_id": tid, "tag": "kept-specs", "name": None, "kernels_verified": 0, "undecided": []}
        rows.append({**base, "source": "python", "prompt": python_question(entry), "chosen": python_block(code)})
        counts["python"] += 1
        seen = set()
        for task in k["tasks"][:3]:
            spec = se.rename_task(specification_of(json.loads(json.dumps(task))), entry["fn"])
            text = loop_dataset.fence(surface.print_task(spec).strip())
            if text in seen:
                continue
            seen.add(text)
            rows.append({**base, "source": "spec", "prompt": spec_question(entry, code), "chosen": text})
            counts["spec"] += 1
    return rows, {"problems": counts["python"], **counts}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pool-rows", type=Path, required=True)
    ap.add_argument("--kept-specs", type=Path, help="t/spec_first.py's kept-specs.jsonl for unproved training problems")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--pool", choices=se.POOL_VERSIONS, default="v5")
    a = ap.parse_args(argv)
    pool_rows = [json.loads(l) for l in a.pool_rows.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows, report = build(pool_rows, se.pool(a.pool))
    if a.kept_specs:
        kept = [json.loads(l) for l in a.kept_specs.read_text(encoding="utf-8").splitlines() if l.strip()]
        more, rep2 = build_from_specs(kept, se.pool(a.pool), {int(r["task_id"]) for r in pool_rows})
        rows += more
        report["from kept specifications"] = rep2
    a.out.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    print(json.dumps(report))
    return 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
