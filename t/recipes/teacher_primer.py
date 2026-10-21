#!/usr/bin/env python3
"""A primer for a general teacher that has never seen t: the specification syntax in one card plus worked examples
drawn from the student's own reference-checked specifications on TRAINING problems (never a gated panel), so an
open-weight model can be asked the route's specification question with --spec-primer (t/spec_first.py).

    python3 t/recipes/teacher_primer.py --kept KEPT_SPECS.jsonl --out PRIMER.md [--examples 6] [--pool v5]

nl2postcond (arXiv:2310.01831) and SpecGen (arXiv:2401.08807) prompt with worked examples; the Qwen3.5-9B audition of
2026-10-21 wrote Python for 83 of 95 problems and no parsable t specification without one. The card states only what
t/SPEC.md states (Gate 1 quantifiers and sequences, strings as code points, the string library, spec funs).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import graded_pool                                              # noqa: E402
import spec_experiment as se                                    # noqa: E402
import surface                                                  # noqa: E402

CARD = """\
The language is t. A specification is a task with an empty body, in this exact shape:

```t
t 1
gate loops
task NAME(p: int, s: seq) returns (r: int)
  requires len(s) > 0
  ensures r == s[0] + p
{
}
```

Rules of the notation:
- Types: `int` (mathematical integers), `bool`, `seq` (a sequence of ints; a string is a seq of its code points, so
  `'a'` is 97 and `"abc"` is a seq literal), `seq<seq>` (a sequence of sequences, for a list of strings or lists).
- `requires` states what the inputs satisfy; `ensures` states what the result `r` satisfies; several clauses are allowed.
- Quantifiers are bounded and half-open: `forall i in [0, len(s)) . P(i)` and `exists i in [lo, hi) . P(i)`; the bound
  variable must be a fresh name; `hi <= lo` is the empty range.
- Sequences: `len(s)`, `s[i]` (defined only when `0 <= i < len(s)`; guard it with `requires` or inside the quantifier
  range), `s[i..j]` (the slice from i to j), `+` (concatenation), `==` between two seqs is elementwise.
- Operators: `and`, `or`, `not`, `==>` (implies), `==`, `!=`, `<`, `<=`, `>`, `>=`, `+`, `-`, `*`, `/`, `%` (integer division
  and modulo are defined only when the divisor is not 0). A conditional expression is `if c then a else b`.
- String library on seqs, as in Python: `count(s, t)`, `find(s, t)` (least index, -1 when absent), `split(s)`,
  `split(s, c)`, `join(rows, sep)`, `strip(s)`, `replace(s, t, u)`, `upper(s)`, `lower(s)`, `isdigit(s)`, `isalpha(s)`,
  `tostr(n)`; and `sum(s)`, `abs(x)`, `min(a, b)`, `max(a, b)`.
- A helper is a `spec fun`, declared before the task and usable in clauses, for example
  `spec fun is_prime(n: int): bool = n >= 2 and forall d in [2, n) . n % d != 0`. A recursive spec fun needs a
  `decreases` measure. Put `gate recursion` on the second line when a spec fun is recursive, `gate loops` otherwise.
- The task's name, parameters (in the tests' order) and return type are given in the question; keep them exactly.
- Say what the result IS, as tightly as the tests allow: a weak clause like `r >= 0` passes nothing useful, and a
  clause false on one of the given tests fails the whole specification.

Worked examples (each specification was checked against the problem's own solution on random inputs):
"""


def pick(kept: list[dict], pool: dict, training: set[int], n: int, seed: int = 1) -> list[dict]:
    """n kept specifications of training problems, short first within a shuffled draw, with distinct problems and at
    least one each of: a quantifier, a requires, a spec fun, a string-library member, a bool result (when available)."""
    rnd = random.Random(seed)
    rows = [r for r in kept if int(r["task_id"]) in training and r.get("tasks")]
    rnd.shuffle(rows)
    wants = {"forall": lambda t: "forall" in t, "requires": lambda t: "requires" in t, "spec fun": lambda t: "spec fun" in t,
             "string": lambda t: any(f"{m}(" in t for m in ("count", "find", "split", "join", "strip", "replace")),
             "bool": lambda t: "returns (r: bool)" in t or "returns (b: bool)" in t}
    chosen, seen = [], set()
    def take(cond):
        for r in rows:
            tid = int(r["task_id"])
            if tid in seen:
                continue
            text = surface.print_task(r["tasks"][0])
            if cond(text) and len(text) < 700:
                seen.add(tid); chosen.append((tid, text)); return True
        return False
    for key, cond in wants.items():
        if len(chosen) < n:
            take(cond)
    while len(chosen) < n and take(lambda t: True):
        pass
    out = []
    for tid, text in chosen[:n]:
        entry = pool[tid]
        out.append({"task_id": tid, "problem": entry["rec"]["text"].strip(), "tests": entry["rec"]["test_list"],
                    "python": (entry["rec"].get("code") or "").strip("\n"), "spec": text})
    return out


def render(examples: list[dict]) -> str:
    parts = [CARD]
    for i, e in enumerate(examples, 1):
        parts.append(f"\nExample {i}. Problem: {e['problem']}\nTests:\n" + "\n".join(e["tests"]) +
                     "\n\nA Python solution:\n```python\n" + e["python"] + "\n```\n\nSpecification:\n```t\n" + e["spec"].strip() + "\n```\n")
    return "".join(parts)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kept", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--examples", type=int, default=6)
    ap.add_argument("--pool", default="v5")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args(argv)
    pool = se.pool(a.pool)
    training = graded_pool.training_ids(HERE / "out" / "loop" / "split-v5.json", pool)
    kept = [json.loads(l) for l in a.kept.read_text(encoding="utf-8").splitlines() if l.strip()]
    examples = pick(kept, pool, training, a.examples, a.seed)
    for e in examples:                                           # every example parses and is a training problem
        surface.parse(e["spec"])
        assert e["task_id"] in training
    a.out.write_text(render(examples), encoding="utf-8")
    print(json.dumps({"examples": [e["task_id"] for e in examples], "chars": a.out.stat().st_size}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
