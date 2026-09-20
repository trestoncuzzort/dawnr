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


def mutations(value):
    """Wrong outputs derived from a right one, deterministically.

    The completeness half of the check, after arXiv 2603.17150: a specification
    that is true of the right answer and also true of a wrong one does not say
    what the problem asked. arXiv 2608.13077 makes the same measurement its
    primary metric and finds it separates models where acceptance metrics do
    not (28.05% against 4.27%).

    Deterministic on purpose. This file threads one seeded generator through
    every task in order, so consuming a draw here would change every downstream
    verdict and every report already cited. Mutations come from the value.
    """
    out = []
    if isinstance(value, bool):
        out.append(not value)
    elif isinstance(value, int):
        out += [value + 1, value - 1, 0, -value]
    elif isinstance(value, tuple):
        rows = all(isinstance(x, tuple) for x in value) and bool(value)
        if value:
            out.append(value[:-1])                                  # dropped the last element
            head = value[0]
            if isinstance(head, bool):
                out.append((not head,) + value[1:])
            elif isinstance(head, int):
                out.append((head + 1,) + value[1:])
            if len(value) > 1:
                out.append(tuple(reversed(value)))
        out.append(value + ((),) if rows else value + (0,))          # one element too many
    seen, unique = set(), []
    for candidate in out:
        if candidate == value:
            continue                       # not a wrong answer; says nothing either way
        key = repr(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


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


def check_points(task: dict, entry: dict) -> dict:
    """Does the specification hold at the problem's OWN examples?

    Clover (arXiv 2310.17807, https://github.com/ChuyueSun/Clover) reduces
    correctness to consistency between three artifacts: the code, the docstring
    and the formal annotation, checking every pair. It reports 87% acceptance on
    correct instances with no false positives.

    This project already has two of those edges. The seven verifiers check code
    against annotation, and `check_task` above checks annotation against the
    problem by running its reference solution. The edge measured here is the one
    nobody was checking: the annotation against the problem's own assertions,
    which are ground-truth input/output pairs shipped with every problem.

    It needs no reference solution, no random draws and no language model, so it
    reaches the answers `check_task` must give up on: on 2026-09-20 that was 78
    of 149 in one arm, where the reference would not run or the drawn shapes did
    not fit. A specification false at an example the problem itself states is
    wrong, and no amount of proving can fix it.
    """
    funs = interp.funs_of(task, task["body"])
    name = task["returns"][0]["name"]
    held = failed = 0
    first = None
    for point in entry.get("points", []):
        if len(point.get("args", [])) != len(task["params"]):
            # zip() would silently truncate here and check a task against a
            # point it does not fit, which is a verdict about nothing.
            continue                       # arity differs; check_task reports that separately
        try:
            env = {p["name"]: to_t(v) for p, (_k, v) in zip(task["params"], point["args"])}
            env[name] = to_t(point["expected"][1])
        except (TypeError, KeyError, IndexError, ValueError):
            continue                       # a point this task cannot even be asked about
        if len(env) != len(task["params"]) + 1:
            continue                       # duplicate parameter names collapsed the env
        st = interp.St()
        try:
            if not all(interp.ev(c, env, funs, st) for c in task.get("requires", [])):
                continue                   # outside its own precondition, says nothing
            ok = all(interp.ev(e, env, funs, st) is True for e in task.get("ensures", []))
        except (interp.Undef, interp.Budget, RecursionError, ZeroDivisionError):
            continue
        except Exception:                  # noqa: BLE001
            continue
        if ok:
            held += 1
        else:
            failed += 1
            if first is None:
                first = {"args": [v for _k, v in point["args"]], "expected": point["expected"][1]}
    out = {"points_held": held, "points_failed": failed}
    if first is not None:
        out["contradicts_example"] = first
    return out


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
    rejected = accepted = 0            # the completeness half: wrong outputs the ensures catches
    weak_witness = None
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
        # The ensures is true of the right answer. Is it also true of a wrong
        # one? Nothing else in this project asks, and a specification that
        # cannot tell them apart is what the proven-but-wrong column is made of.
        for wrong in mutations(env[task["returns"][0]["name"]]):
            probe = dict(env)
            probe[task["returns"][0]["name"]] = wrong
            st2 = interp.St()
            try:
                holds = all(interp.ev(e, probe, funs, st2) is True
                            for e in task.get("ensures", []))
            except (interp.Undef, interp.Budget, RecursionError, ZeroDivisionError):
                continue                 # undefined on a wrong answer is a rejection by refusal
            except Exception:            # noqa: BLE001
                continue
            if holds:
                accepted += 1
                if weak_witness is None:
                    weak_witness = {"args": args, "reference_said": out, "also_accepts": wrong}
            else:
                rejected += 1
    result = {"status": "agrees" if agreed else "no valid draws", "draws": agreed}
    if rejected or accepted:
        # Reported, never silently turned into a failure: a problem with more
        # than one right answer can accept a mutated output legitimately, so
        # this is evidence with a witness attached, for a human or a later gate.
        result.update(mutants_rejected=rejected, mutants_accepted=accepted,
                      completeness=round(rejected / (rejected + accepted), 3),
                      weak=accepted > 0)
        if weak_witness is not None:
            result["weak_witness"] = weak_witness
    return result


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
    # ONE generator, threaded through every task in order, so task N's arguments
    # depend on tasks 1..N-1. That is what makes `--seed 1` reproduce a report
    # exactly, and it is also why this loop cannot be parallelized for speed:
    # any concurrency changes the draw order and therefore the verdicts, and
    # this file's output is cited evidence (t/SPEC-CHECK-*.md, the README's
    # 650-answer figure, and t/out/spec-disagree.json, which the training gate
    # reads). Considered and rejected on 2026-09-20.
    #
    # The safe route, if the runtime ever matters: seed per task from the task's
    # own sha256 instead of sharing this generator, which makes tasks
    # independent and parallelizable. That is a change to the instrument, not an
    # optimization of it -- every existing report would have to be regenerated
    # and the change registered before anyone compares old numbers with new.
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
                if entry is not None:
                    # Clover's third consistency edge (arXiv 2310.17807): the
                    # annotation against the problem's own assertions. Needs no
                    # reference solution, so it reaches the tasks check_task
                    # gives up on, and it never flagged a clean answer in the
                    # three arms measured on 2026-09-20.
                    r.update(check_points(task, entry))
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
