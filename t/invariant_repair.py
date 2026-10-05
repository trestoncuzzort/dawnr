#!/usr/bin/env python3
"""t/invariant_repair.py -- a proof that fails on its loop invariants, repaired by rule and re-checked, with no
model asked (2026-10-05).

    python3 t/invariant_repair.py --file ANSWER.t [--save REPAIRED.t]
    python3 t/invariant_repair.py --tasks DIR --out REPORT.json [--jobs 8]     # every task JSON in DIR, Dafny alone

Two ways a right program goes unproved for a reason that has nothing to do with the program:

  order     `t` checks a loop's invariants in order (t/SPEC.md, "Invariants are checked in order"): an invariant
            that reads `xs[j]` for `j < i` is only defined once an earlier invariant has bounded `i`. A writer that
            never learned this lists the bound last, and six provers read the task unproved on the invariant's
            own definedness. Found in a trial of a 35B model writing `t` from the reference alone: its `largest`
            was unproved by Dafny and Verus as written and verified by both with the bound moved first.
  surplus   a model adds an invariant that is not needed for the postcondition and is not inductive, and the
            whole proof fails on it. DafnyPro (Banerjee, Bouissou and Zetzsche, arXiv:2601.05385, 3.2) prunes
            such clauses greedily; the idea is Houdini's (Flanagan and Leino, FME 2001): let the checker refute
            candidate annotations and keep what survives.

`repair` does both, driven by what Dafny reports (t/dafny_feedback.py's reading of it, kept with line numbers):
when an invariant is reported undefined, each loop's invariants over plain numbers are moved before those that
index or quantify; then, to a fixed point, every invariant reported as not proved on entry or not maintained is
dropped. It stops when Dafny verifies, when Dafny's complaint is about something that is not an invariant, or
after ROUNDS rounds.

Why this is safe. Invariants are annotations: the program's behaviour, its tests and its specification are
untouched (`same_program` checks it, as DafnyPro's diff-checker does), and an invariant that is removed or moved
cannot make a wrong program verify, because what remains must still hold on entry, be maintained, and imply the
postcondition. What comes back is a new candidate program, the one with the surviving invariants in their new
order; it is that text which then goes through the whole gate (all the provers, the sabotaged twin) and is shown
and certified, never the original with a borrowed verdict. Research receipt e85d39d1a968.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

ROUNDS = 4
_LOCATED = re.compile(r"^.*?\((?P<line>\d+),(?P<col>\d+)\): (?P<kind>Error|Related location): ?(?P<msg>.*)$")
_TALLY = re.compile(r"finished with (\d+) verified, (\d+) errors?")


def loops(task_or_body) -> list[dict]:
    """Every `while` of a body, outer before inner, in the order they are written."""
    out = []

    def walk(stmts):
        for s in stmts or []:
            if "while" in s:
                out.append(s["while"])
                walk(s["while"].get("body"))
            elif "if" in s:
                walk(s["if"].get("then"))
                walk(s["if"].get("else"))
    walk(task_or_body["body"] if isinstance(task_or_body, dict) else task_or_body)
    return out


def _nodes(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _nodes(v)
    elif isinstance(node, list):
        for v in node:
            yield from _nodes(v)


def plain(invariant) -> bool:
    """An invariant over numbers alone: no quantifier, no indexing, no slice. These bound the variables the others
    index with, and are always defined."""
    return not any("forall" in n or "exists" in n or n.get("op") in ("at", "slice") or "call" in n for n in _nodes(invariant))


def reordered(task: dict) -> dict | None:
    """The task with each loop's plain invariants first, the others after, each group in its written order; None
    when that is the order they are already in."""
    new, changed = copy.deepcopy(task), False
    for w in loops(new):
        invs = w.get("invariants") or []
        ordered = [i for i in invs if plain(i)] + [i for i in invs if not plain(i)]
        if ordered != invs:
            w["invariants"], changed = ordered, True
    return new if changed else None


def same_program(a: dict, b: dict) -> bool:
    """Whether two tasks differ in nothing but their loops' invariants."""
    def bare(task):
        t = copy.deepcopy(task)
        for w in loops(t):
            w["invariants"] = []
        return json.dumps(t, sort_keys=True)
    return bare(a) == bare(b)


def diagnose(task: dict, wall: int = 150) -> dict:
    """One Dafny run on the lowered task: {"verified", "undefined": [(loop, k)], "failing": [(loop, k)], "other":
    n}, the invariants named by position (loop index, index within the loop). `why` is set when nothing could be
    run. An error whose line is not an invariant's counts under "other"."""
    import lower_dafny
    from verifiers import dafny as adapter
    if not adapter.DAFNY:
        return {"verified": False, "undefined": [], "failing": [], "other": 0, "why": "no dafny"}
    try:
        source = lower_dafny.lower(task, task["body"])
    except Exception as e:                                      # noqa: BLE001 -- a task that does not lower has no proof to repair
        return {"verified": False, "undefined": [], "failing": [], "other": 0, "why": f"does not lower: {type(e).__name__}"}
    lines = source.split("\n")
    written = [(k, j) for k, w in enumerate(loops(task)) for j in range(len(w.get("invariants") or []))]
    lowered = [n for n, text in enumerate(lines, 1) if text.strip().startswith("invariant ")]
    where = dict(zip(lowered, written)) if len(lowered) == len(written) else {}
    with tempfile.TemporaryDirectory(prefix="invariant-repair-") as tmp:
        path = Path(tmp) / "task.dfy"
        path.write_text(source, encoding="utf-8")
        try:
            p = subprocess.run([adapter.DAFNY, "verify", "--resource-limit", str(adapter.DEFAULT_RLIMIT), str(path)],
                               capture_output=True, text=True, errors="replace", timeout=wall)
        except subprocess.TimeoutExpired:
            return {"verified": False, "undefined": [], "failing": [], "other": 1, "why": "dafny did not finish"}
    out = p.stdout + p.stderr
    m = _TALLY.search(out)
    if p.returncode == 0 and m is not None and int(m.group(1)) >= 1 and int(m.group(2)) == 0:
        return {"verified": True, "undefined": [], "failing": [], "other": 0}
    errors, current = [], None
    for raw in out.split("\n"):
        hit = _LOCATED.match(raw.strip())
        if hit is None:
            continue
        if hit.group("kind") == "Error":
            current = {"msg": hit.group("msg"), "line": int(hit.group("line")), "related": None}
            errors.append(current)
        elif current is not None and current["related"] is None:
            current["related"] = int(hit.group("line"))
    undefined, failing, other = [], [], 0
    for e in errors:
        at = where.get(e["related"]) or where.get(e["line"])
        if at is None:
            other += 1
        elif "could not be proved on entry" in e["msg"] or "could not be proved to be maintained" in e["msg"]:
            failing.append(at)
        else:                                                   # index out of range, a precondition: the invariant's own definedness
            undefined.append(at)
    return {"verified": False, "undefined": sorted(set(undefined)), "failing": sorted(set(failing)), "other": other + (0 if errors else 1)}


def without(task: dict, drop: list[tuple[int, int]]) -> dict:
    new = copy.deepcopy(task)
    for k, w in enumerate(loops(new)):
        w["invariants"] = [inv for j, inv in enumerate(w.get("invariants") or []) if (k, j) not in drop]
    return new


def repair(task: dict, diagnose=diagnose, rounds: int = ROUNDS) -> dict:
    """{"verified": Dafny's verdict on the last candidate, "task": the repaired task when it differs from the one
    given and Dafny verifies it (else None), "steps": what was done, "as written": whether it verified untouched}."""
    d = diagnose(task)
    if d["verified"]:
        return {"verified": True, "task": None, "steps": [], "as written": True}
    steps, current = [], task
    if d["undefined"]:
        moved = reordered(current)
        if moved is not None:
            current, d = moved, diagnose(moved)
            steps.append("the invariants over plain numbers moved before those that index or quantify")
    for _ in range(rounds):
        if d["verified"] or not d["failing"]:
            break
        current = without(current, d["failing"])
        steps.append(f"{len(d['failing'])} invariant{'s' if len(d['failing']) != 1 else ''} dropped that Dafny could not prove on entry or maintained")
        d = diagnose(current)
    ok = bool(d["verified"]) and bool(steps) and same_program(task, current)
    return {"verified": bool(d["verified"]), "task": current if ok else None, "steps": steps, "as written": False}


def _one(path: str) -> dict:
    task = json.loads(Path(path).read_text(encoding="utf-8"))
    if not loops(task):
        return {"name": task.get("name"), "loops": 0}
    r = repair(task)
    return {"name": task.get("name"), "loops": len(loops(task)), "as written": r["as written"], "verified": r["verified"],
            "steps": r["steps"], "task": r["task"]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--file", type=Path, help="one t program")
    ap.add_argument("--save", type=Path, help="write the repaired program here")
    ap.add_argument("--tasks", type=Path, help="a directory of task JSON files")
    ap.add_argument("--only", type=Path, help="with --tasks: a file of task names, one a line; the others are left alone")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--jobs", type=int, default=8)
    a = ap.parse_args(argv)
    import surface
    if a.file:
        r = repair(surface.parse(a.file.read_text(encoding="utf-8")))
        if r["as written"]:
            print("Dafny verifies it as written; nothing to repair.")
        elif r["task"] is not None:
            print("REPAIRED: " + "; ".join(r["steps"]) + ". Dafny verifies the result.\n\n" + surface.print_task(r["task"]).rstrip())
            if a.save:
                a.save.write_text(surface.print_task(r["task"]), encoding="utf-8")
        else:
            print("NOT REPAIRED" + (": " + "; ".join(r["steps"]) + ", and Dafny still does not verify it." if r["steps"]
                                    else ": what Dafny reports is not about a loop invariant."))
        return 0 if r["verified"] else 1
    if not a.tasks or not a.out:
        raise SystemExit("invariant_repair: give --file, or --tasks and --out")
    from multiprocessing import Pool
    names = set(a.only.read_text(encoding="utf-8").split()) if a.only else None
    files = sorted(str(f) for f in a.tasks.glob("*.json") if names is None or f.stem in names)
    with Pool(a.jobs) as pool:
        rows = pool.map(_one, files, chunksize=1)
    looped = [r for r in rows if r.get("loops")]
    summary = {"tasks": len(rows), "with a loop": len(looped), "verified as written": sum(1 for r in looped if r["as written"]),
               "repaired": sum(1 for r in looped if r.get("task") is not None),
               "by reordering alone": sum(1 for r in looped if r.get("task") is not None and len(r["steps"]) == 1 and "moved" in r["steps"][0])}
    a.out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
