#!/usr/bin/env python3
"""t/student_fewshot.py -- the most similar proved problems, shown before the question (2026-10-01).

    ~/.venv-t/bin/python t/student_fewshot.py --model DIR --pool-rows sft-graded-k1-s2.jsonl \\
        --tag OUT --ids-file ids.txt [--k 5]

Misu et al. (arXiv:2402.00247, section 3.4.3): GPT-4 writes verified Dafny with a specification
for 19% of 178 MBPP problems from a bare prompt and for 58% when the prompt carries the five most
similar solved problems, retrieved by embedding similarity. Registered here as the fourth arm of
t/PREDICT-2026-10-01-several-answers.md.

The solved problems are the graded training pool's (t/graded_pool.py: training problems only,
each answer passes its tests, is proved by at least one kernel with none refuting, and carries a
specification that agrees with the reference); one answer a problem, the one the most kernels
prove. Similarity is BM25 over the problem text (locallm/dawnr_retrieval/bm25.py, the index this
project already has; the paper used an embedding model). Each example is a question-and-answer
turn in the student's own trained words (prompt s1), least similar first so the closest sits next
to the question, then the question. One greedy answer a problem, written in
t/spec_experiment.py's layout.

A problem is never shown itself: the pool holds training problems, and an id that is both in the
pool and asked is refused by name.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "locallm"))

import spec_experiment as se                                    # noqa: E402
from dawnr_retrieval.bm25 import BM25Index                      # noqa: E402


def best_answers(pool_rows: list[dict]) -> dict[int, dict]:
    """One answer a problem: the one proved by the most kernels, the first of them."""
    best: dict[int, dict] = {}
    for r in pool_rows:
        tid = int(r["task_id"])
        if tid not in best or (r.get("kernels_verified") or 0) > (best[tid].get("kernels_verified") or 0):
            best[tid] = r
    return best


def build_index(answers: dict[int, dict], pool: dict) -> BM25Index:
    index = BM25Index()
    for tid in sorted(answers):
        index.add(tid, pool[tid]["rec"]["text"])
    return index.build()


def conversation(entry: dict, examples: list[tuple[dict, str]], version: str = "s1") -> list[dict]:
    """system, then each (example problem's entry, its answer) as a turn, then the question."""
    question = se.build_prompt(entry, version)
    out = [question[0]]
    for ex_entry, answer in examples:
        out += [se.build_prompt(ex_entry, version)[1], {"role": "assistant", "content": answer}]
    return out + [question[1]]


def retrieve(index: BM25Index, answers: dict[int, dict], pool: dict, entry: dict, k: int) -> list[tuple[dict, str]]:
    hits = index.search(entry["rec"]["text"], k=k)
    return [(pool[tid], answers[tid]["chosen"]) for tid, _score in reversed(hits)]   # closest last


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--pool-rows", type=Path, required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--ids-file", type=Path, required=True)
    ap.add_argument("--pool", choices=se.POOL_VERSIONS, default="v5")
    ap.add_argument("--prompt", choices=("s1", "s2"), default="s1")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--max-new", type=int, default=1024)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--dry-run", action="store_true", help="build the conversations, print one, ask nothing")
    a = ap.parse_args(argv)

    pool = se.pool(a.pool)
    ids = [x for x in a.ids_file.read_text(encoding="utf-8").split() if x.strip()]
    answers = best_answers([json.loads(l) for l in a.pool_rows.read_text(encoding="utf-8").splitlines() if l.strip()])
    shown_and_asked = sorted(int(t) for t in ids if int(t) in answers)
    if shown_and_asked:
        raise SystemExit(f"student_fewshot: asked problems are in the example pool: {shown_and_asked[:5]}")
    index = build_index(answers, pool)
    conversations = {t: conversation(pool[int(t)], retrieve(index, answers, pool, pool[int(t)], a.k), a.prompt)
                     for t in ids}
    if a.dry_run:
        c = conversations[ids[0]]
        print(json.dumps({"problems": len(ids), "examples a problem": (len(c) - 2) // 2, "pool problems": len(answers),
                          "characters in the first prompt": sum(len(m["content"]) for m in c)}))
        print(c[-3]["content"][-300:], "\n---\n", c[-2]["content"][:300], "\n---\n", c[-1]["content"][:300])
        return 0

    import student_generate                                     # noqa: E402  (loads torch)
    d = se.outdir(a.tag)
    lock = se.tag_lock(d)
    if lock is None:
        raise SystemExit(f"student_fewshot: another generator holds {a.tag}")
    model, tokenizer = student_generate.load(a.model)
    options = {"temperature": 0.0, "seed": 1, "num_predict": a.max_new, "decoder": "transformers-batched",
               "retrieved": {"k": a.k, "index": "bm25 over the problem text", "pool_rows": str(a.pool_rows),
                             "pool_problems": len(answers)}}
    todo = [t for t in ids if not (d / "raw" / f"{t}.json").exists()]
    started = time.monotonic()
    for start in range(0, len(todo), a.batch):
        chunk = todo[start:start + a.batch]
        replies = student_generate.decode(model, tokenizer, [conversations[t] for t in chunk], a.max_new)
        for t, (text, stopped, ntok) in zip(chunk, replies):
            se.write_record(d / "raw" / f"{t}.json", {
                "task_id": t, "fn": pool[int(t)]["fn"], "model": str(a.model), "digest": "", "pool_version": a.pool,
                "prompt_version": f"{a.prompt}+retrieved", "options": options, "messages": conversations[t],
                "reply": text, "reply_tokens": ntok, "done_reason": "stop" if stopped else "length"})
        print(f"student_fewshot: {a.tag}: {min(start + a.batch, len(todo))}/{len(todo)} "
              f"({time.monotonic() - started:.0f} s)", flush=True)
    lock.close()
    return 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
