#!/usr/bin/env python3
"""t/debug_rows.py -- self-debugging rows for the student (2026-10-01).

    python3 t/debug_rows.py --from-samples TAG [TAG ...] --split t/out/loop/split-v5.json \\
        --pool-rows sft-graded-k1.jsonl --out debug-rows.jsonl [--per-problem 6]

SAFE's second kind of training data (arXiv:2410.15756, section 3.3 and table 4: 10,486 debugging
pairs beside 9,706 verified programs): an incorrect attempt and the verifier's message, paired with
a correct answer for the same problem, so the fine-tuned model learns to act on what the checker
says. SAFE reports that one debugging sample after one proof sample beats two proof samples.

Here an attempt is any earlier answer to a TRAINING problem that the gate refused, and the message
is what the gate itself said, in the words message_for() fixes for training and for the repair
loop alike:

  - the parser or the well-formedness check refused it: their own message;
  - it fails one of the problem's tests: the first failing point;
  - it passes the tests and no kernel proves it, or a kernel refutes it: t/repair.py's verdict lines.

The answer is a row of t/graded_pool.py for the same problem (the gate admitted it; the
highest-trust copy). At most --per-problem rows a problem, taken round-robin over the kinds so one
kind does not crowd out the rest. Only training problems: the pool rows already exclude held-out,
dev and policy-excluded ids, and an attempt is read only for a problem the pool answers.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import loop_dataset                                             # noqa: E402
import repair                                                   # noqa: E402
import spec_experiment as se                                    # noqa: E402
import surface                                                  # noqa: E402

ASK_AGAIN = "\n\nWrite the corrected task."
MAX_ATTEMPT_CHARS = 3000


def message_for(stage: str, why: str | None, tests_entry: dict | None, row: dict | None,
                cols: list[str] | None) -> tuple[str, str] | None:
    """(kind, what the gate said) for a refused attempt, or None when the gate did not refuse it
    or there is nothing useful to say. The repair loop calls this too, so the student is asked
    at inference in the words it was trained on."""
    if stage in ("parse", "wf"):
        return (stage, "The t checker rejected it: " + (why or "not a well-formed task").strip())
    if stage != "task":
        return None
    overall = (tests_entry or {}).get("overall")
    if overall != "pass":
        for point in (tests_entry or {}).get("points", []):
            if point.get("verdict") == "pass":
                continue
            if "got" in point:
                return ("tests", f"It fails one of the problem's tests: it returns {point['got']!r} where "
                                 f"{point.get('expected')!r} is expected.")
            return ("tests", "It does not fit the problem's tests: " + str(point.get("why", point.get("verdict"))))
        return None
    if not row or not cols:
        return None
    if all(row.get(k) == "verified / refuted" for k in cols):
        return None                                             # proved everywhere: not a failure
    return ("proof", "It passes the tests, but the provers report:\n" + repair.feedback(row, cols))


def attempt_text(sample: dict) -> str | None:
    text = sample.get("text") if sample.get("wellformed") else sample.get("malformed_text")
    if not text or len(text) > MAX_ATTEMPT_CHARS:
        return None
    return text


def build(tags: list[str], split_path: Path, pool_rows: list[dict], per_problem: int) -> tuple[list[dict], dict]:
    split = json.loads(split_path.read_text(encoding="utf-8"))
    pool = se.pool(split.get("pool", "v1"))
    best = {}
    for r in pool_rows:                                         # the highest-trust admitted answer per problem
        if r["task_id"] not in best or r["kernels_verified"] > best[r["task_id"]]["kernels_verified"]:
            best[r["task_id"]] = r
    tag_dirs = [loop_dataset.load_tag_dir(t) for t in tags]
    rows, tally = [], Counter()
    for tid in sorted(best):
        target = best[tid]["chosen"]
        by_kind = defaultdict(list)
        seen = {target}
        for k, tagdata in enumerate(tag_dirs):
            try:
                sample = loop_dataset.grade_sample(tagdata, k, tid)
            except surface.SurfaceError:
                tally["task-no-longer-prints"] += 1
                continue
            if sample is None:
                continue
            text = attempt_text(sample)
            if text is None or text in seen:
                continue
            e = tagdata["extract"].get(str(tid), {})
            said = message_for(sample["stage"], e.get("why"), tagdata["tests"].get(str(tid)),
                               sample.get("kernel_row"), sample.get("kernel_columns"))
            if said is None:
                continue
            seen.add(text)
            by_kind[said[0]].append((sample["tag"], text, said[1]))
        taken = 0
        while taken < per_problem and any(by_kind.values()):    # round-robin over the kinds
            for kind in ("parse", "wf", "tests", "proof"):
                if by_kind[kind] and taken < per_problem:
                    tag, text, said = by_kind[kind].pop(0)
                    user = se.build_prompt(pool[tid], "s1")
                    rows.append({"kind": "debug", "failure": kind, "task_id": tid, "tag": tag, "source": "debug",
                                 "prompt": user + [{"role": "assistant", "content": text},
                                                   {"role": "user", "content": said + ASK_AGAIN}],
                                 "chosen": target})
                    tally[kind] += 1
                    taken += 1
    report = {"problems": len(best), "rows": len(rows), "by_kind": dict(tally), "per_problem": per_problem}
    return rows, report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from-samples", nargs="+", required=True, metavar="TAG")
    ap.add_argument("--split", type=Path, required=True)
    ap.add_argument("--pool-rows", type=Path, required=True, help="t/graded_pool.py's rows (the answers)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--per-problem", type=int, default=6)
    a = ap.parse_args(argv)
    pool_rows = [json.loads(l) for l in a.pool_rows.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows, report = build(a.from_samples, a.split, pool_rows, a.per_problem)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
    print(json.dumps(report))
    return 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
