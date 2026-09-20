#!/usr/bin/env python3
"""t/spec_check.py -- does an accepted answer's specification agree with the problem's own solution? (2026-09-18)

    python3 t/spec_check.py [--pool v4] [--n 200] [--only clean] [tag ...]

The seven proof systems check a program against its specification. Nothing checks the specification against the
problem. The ablation of 2026-09-17 measured what that costs: on held-out answers, where the model writes its
own specification, every proof gate admits wrong answers about 97 percent of the time, and only the tests catch
it. The tests are three assertions.

This runs the missing check. For each task it draws random arguments of the shapes the problem's own assertions
use, calls the problem's reference solution on them, and evaluates the task's `ensures` with that result bound
to the return variable, using t's own interpreter. An `ensures` that reads false on an input the reference
solution answers is a specification that disagrees with the problem, and every answer it admits is a false
accept that seven provers and a refuted twin both missed.

Disagreements are reported with the input that shows them. The reference solutions come from the corpus records
(nl/), and they are executed in this process, so run it on a corpus you trust.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import random
import re
import signal
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness                                                  # noqa: E402
import interp                                                   # noqa: E402
import spec_experiment as se                                    # noqa: E402
import surface                                                 # noqa: E402

KERNELS = ["dafny", "verus", "spark", "framac", "lean", "rocq", "fstar"]


def task_sha256(task: dict) -> str:
    """Bind a check to the exact canonical program, including its specification."""
    return hashlib.sha256(surface.print_task(task).strip().encode("utf-8")).hexdigest()


def problem_id(name: str, extracted: dict) -> int | None:
    """Recover the pool ID, keeping HumanEval and APPS separate from MBPP."""
    ids = {int(tid) for tid, entry in extracted.items()
           if str(tid).isdigit() and entry.get("name") == name}
    if len(ids) > 1:
        raise ValueError(f"ambiguous problem IDs for {name}: {sorted(ids)}")
    match = re.fullmatch(r"(mbpp|he|apps)_(\d+)__.+", name)
    named = None
    if match:
        named = int(match[2]) + {"mbpp": 0, "he": se.HUMANEVAL_BASE,
                                 "apps": se.APPS_BASE}[match[1]]
    if ids:
        tid = next(iter(ids))
        if named is not None and tid != named:
            raise ValueError(f"extract ID {tid} disagrees with task name {name}")
        return tid
    return named


class Timeout(Exception):
    pass


def _alarm(_sig, _frm):
    raise Timeout()


def draw(kind: str, rnd: random.Random, like=None):
    """A random value of the kind a problem's own assertions use, shaped like the problem's own example.

    2026-09-18: drawing freely finds disagreements that are the REFERENCE's fault, not the specification's.
    mbpp_733's reference is a binary search, so it answers -1 on an unsorted array although the element is
    there; the problem never says its inputs are sorted. An example argument from the problem's own assertions
    carries those unstated preconditions, so a draw copies its shape: a sorted example stays sorted, an example
    of characters stays characters, a positive example stays positive."""
    if kind == "int":
        if isinstance(like, int) and not isinstance(like, bool):
            lo, hi = (0, max(2, abs(like) * 2)) if like >= 0 else (-max(2, abs(like) * 2), 0)
            return rnd.randint(lo, hi)
        return rnd.choice([rnd.randint(-8, 8), rnd.randint(0, 40)])
    if kind == "bool":
        return rnd.random() < 0.5
    if kind == "seq":
        ex = list(like) if isinstance(like, (list, tuple)) else []
        n = rnd.randint(0, max(3, len(ex) + 2))
        if ex and all(isinstance(x, int) for x in ex):
            lo, hi = min(ex), max(ex)
            lo, hi = (lo - 2, hi + 2) if lo != hi else (lo - 2, lo + 2)
            vals = [rnd.randint(lo, hi) for _ in range(n)]
            if ex == sorted(ex):
                vals.sort()
            return vals
        return [rnd.randint(-6, 6) for _ in range(n)]
    if kind == "seq-of-seq":
        return [[rnd.randint(-4, 4) for _ in range(rnd.randint(0, 3))] for _ in range(rnd.randint(0, 3))]
    return None


def to_t(value):
    """A Python value from the reference solution as an interpreter value."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return tuple(ord(c) for c in value)
    if isinstance(value, (list, tuple)):
        return tuple(to_t(x) for x in value)
    raise TypeError(f"unsupported reference result: {type(value).__name__}")


def reference(rec: dict, fn: str):
    """The problem's own solution as a callable, or None when it will not run."""
    code = rec.get("code") or ""
    if not code.strip():
        return None
    # the corpus's own solutions assume the imports their site had: APPS solutions are LeetCode-shaped and
    # annotate with List and Dict, MBPP's use math and collections (2026-09-18)
    g: dict = {"__builtins__": __builtins__}
    try:
        exec("import math, collections, itertools, functools, re, heapq, bisect, string\n"
             "from typing import List, Dict, Tuple, Set, Optional, Any\n", g)
    except Exception:                                           # noqa: BLE001
        pass
    try:
        exec(compile(code, f"<{fn}>", "exec"), g)                # noqa: S102  (corpus reference solution)
    except Exception:                                           # noqa: BLE001
        return None
    f = g.get(fn)
    return f if callable(f) else None


def check_task(task: dict, entry: dict, n: int, rnd: random.Random) -> dict:
    """One task against its problem's solution: how many draws agreed, and the first that did not."""
    fn = reference(entry["rec"], entry["fn"])
    if fn is None:
        return {"status": "no reference"}
    kinds = [k for k, _v in entry["points"][0]["args"]]
    examples = [v for _k, v in entry["points"][0]["args"]]
    if len(kinds) != len(task["params"]):
        return {"status": "arity differs from the problem"}
    funs = interp.funs_of(task, task["body"])
    agreed = 0
    for _ in range(n):
        args = [draw(k, rnd, ex) for k, ex in zip(kinds, examples)]
        if any(a is None for a in args):
            return {"status": f"cannot draw {kinds}"}
        signal.signal(signal.SIGALRM, _alarm)
        signal.alarm(5)
        try:
            out = fn(*[x if not isinstance(x, list) else list(x) for x in args])
        except Timeout:
            return {"status": "reference did not finish"}
        except Exception:                                       # noqa: BLE001
            continue                                            # the reference refuses this input; not a finding
        finally:
            signal.alarm(0)
        try:
            env = {p["name"]: to_t(a) for p, a in zip(task["params"], args)}
            env[task["returns"][0]["name"]] = to_t(out)
        except TypeError:
            return {"status": "reference result has no t value"}
        st = interp.St()
        try:
            if not all(interp.ev(c, env, funs, st) for c in task.get("requires", [])):
                continue                                        # outside the precondition, says nothing
            bad = [i for i, e in enumerate(task.get("ensures", []))
                   if interp.ev(e, env, funs, st) is not True]
        except (interp.Undef, interp.Budget, RecursionError, ZeroDivisionError):
            continue
        except Exception:                                       # noqa: BLE001
            return {"status": "interpreter refused"}
        if bad:
            return {"status": "disagrees", "ensures": bad[0], "args": args,
                    "reference_said": out, "agreed_before": agreed}
        agreed += 1
    return {"status": "agrees" if agreed else "no valid draws", "draws": agreed}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("tags", nargs="*")
    ap.add_argument("--pool", default="v4")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--only", choices=["clean", "all"], default="clean")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", type=Path, default=HERE / "SPEC-CHECK-2026-09-18.md")
    a = ap.parse_args()
    if a.n < 1:
        ap.error("--n must be positive")
    pool = se.pool(a.pool)
    rnd = random.Random(a.seed)
    root = HERE / "out" / "spec-experiment"
    tags = a.tags or sorted(p.name for p in root.glob("*") if (p / "kernels.md").exists())
    rows, tally = [], {"agrees": 0, "disagrees": 0, "other": 0}
    for tag in tags:
        d = root / tag
        cols, cells = se.parse_kernel_table(d / "kernels.md")
        try:
            extracted = json.loads((d / "extract.json").read_text())
        except (OSError, ValueError):
            extracted = {}
        try:
            tests = {v.get("name"): v.get("overall") for v in json.loads((d / "tests.json").read_text()).values()}
        except (OSError, ValueError):
            tests = {}
        for name, row in cells.items():
            clean = (tests.get(name) == "pass"
                     and all(row.get(k, "").startswith("verified / refuted") for k in KERNELS))
            if a.only == "clean" and not clean:
                continue
            path = d / "tasks" / f"{name}.json"
            if not path.exists():
                continue
            task = harness.load(path)
            try:
                tid = problem_id(name, extracted)
                entry = pool.get(tid)
                r = (check_task(task, entry, a.n, rnd) if entry is not None
                     else {"status": "problem not in pool"})
            except ValueError as e:
                tid = None
                r = {"status": "problem mapping refused", "reason": str(e)}
            r.update(task_id=tid, task_sha256=task_sha256(task), pool=a.pool,
                     seed=a.seed, attempts=a.n)
            key = "agrees" if r["status"] == "agrees" else ("disagrees" if r["status"] == "disagrees" else "other")
            tally[key] += 1
            rows.append((tag, name, r))
            if key == "disagrees":
                print(f"DISAGREES {tag}/{name}: ensures[{r['ensures']}] is false at args={r['args']}, "
                      f"the problem's solution answers {r['reference_said']!r}")
    print(f"\n{sum(tally.values())} tasks checked against their problem's own solution, {a.n} draws each: "
          f"{tally['agrees']} agree, {tally['disagrees']} disagree, {tally['other']} could not be checked")
    lines = ["# Specifications against the problems' own solutions, 2026-09-18", "",
             f"`python3 t/spec_check.py --pool {a.pool} --n {a.n} --only {a.only}`, seed {a.seed}. Each task's",
             "`ensures` is evaluated with the problem's reference solution supplying the result, on random",
             "arguments of the shapes the problem's own assertions use. A disagreement is a specification the",
             "seven proof systems proved and the twin rule accepted that does not say what the problem asked.", "",
             f"- checked: {sum(tally.values())}", f"- agree on every draw: {tally['agrees']}",
             f"- disagree: {tally['disagrees']}", f"- could not be checked: {tally['other']}", ""]
    for tag, name, r in rows:
        if r["status"] == "disagrees":
            lines.append(f"- `{tag}/{name}`: ensures[{r['ensures']}] false at `{r['args']}`, "
                         f"the problem's solution answers `{r['reference_said']!r}`")
    a.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # machine-readable, so loop_dataset.py can keep these out of a pool and preflight.py can count them
    # the program itself, not only its name: two tags can answer the same problem, and only the answer whose
    # specification disagrees must be kept out of a pool (2026-09-18)
    disagree, texts = [], {}
    for tag, name, r in rows:
        if r["status"] != "disagrees":
            continue
        disagree.append(f"{tag}/{name}")
        try:
            texts[f"{tag}/{name}"] = surface.print_task(
                harness.load(root / tag / "tasks" / f"{name}.json")).strip()
        except (OSError, ValueError):
            pass
    # Merge rather than overwrite, and record WHICH tags were checked. Without that list a reader cannot tell
    # "this answer set was checked and nothing disagreed" from "nobody ever checked this answer set", and
    # score_heldout.py was silently reading the second as the first: every tag absent from the disagreement
    # list scored full marks in its "clean, spec checked" column, checked or not (2026-09-19).
    out_path = HERE / "out" / "spec-disagree.json"
    try:
        prev = json.loads(out_path.read_text())
    except (OSError, ValueError):
        prev = {}
    checked_tags = sorted(set(prev.get("tags", [])) | set(tags))
    results = {f"{tag}/{name}": result for tag, name, result in rows}
    keep = [x for x in prev.get("disagree", []) if x not in results]
    keep_texts = {k: v for k, v in (prev.get("programs") or {}).items()
                  if k not in results}
    updated = {**prev, "checked": int(prev.get("checked", 0)) + sum(tally.values()),
               "tags": checked_tags, "disagree": sorted(keep + disagree),
               "programs": {**keep_texts, **texts},
               "results": {**prev.get("results", {}), **results},
               "runs": [*prev.get("runs", []),
                        {"tags": tags, "pool": a.pool, "seed": a.seed, "attempts": a.n,
                         "only": a.only, "counts": tally,
                         "when": datetime.datetime.now(datetime.timezone.utc).isoformat()}]}
    temp = out_path.with_suffix(".tmp")
    temp.write_text(json.dumps(updated, indent=1) + "\n", encoding="utf-8")
    temp.replace(out_path)
    # relative_to raises when --out is outside the repository or given as a
    # relative path from elsewhere, which failed a run on 2026-09-19 AFTER the
    # report had been written: the work was done and the command still exited
    # nonzero. Report the path we can, never crash on the way out.
    try:
        shown = a.out.resolve().relative_to(HERE.parent)
    except ValueError:
        shown = a.out.resolve()
    print(f"written to {shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
