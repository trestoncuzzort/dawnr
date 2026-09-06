#!/usr/bin/env python3
"""lift_gate.py -- refuse a corpus number until the lifter earns one.

The rule this enforces, Treston's, 2026-09-06: if the lifter is not
preserving meaning on the simplest functional tasks, any success metric over
the 24,748-problem corpus in nl/ is meaningless. nl/FIDELITY.md is the
argument; this is the executable form of it. It exits nonzero while the tier
is unproven, so a coverage number cannot be printed by accident.

Two arms, reported separately and never added together:

  LADDER  the existing section-10(a) run over `interp.Reference(task).points`,
          a domain built from the program's own literals and then capped by
          DIFF_MAX_POINTS. Measured on this tier: 12 to 512 points.
  HUMAN   the same harness over the MBPP assertions for the same problem
          (mbpp_dfy.py), written by people who never saw the lifter. Few
          points, but independent, which is the property the ladder lacks.

Both arms answer "does the lifted body compute what the source computes",
and only the second can find a divergence away from the program's own
constants. A row that passes the ladder and fails the human arm is the case
this whole file exists to catch.

    python3 lift_gate.py                 # run the gate, exit 1 if unproven
    python3 lift_gate.py --json OUT      # per-program detail
    python3 lift_gate.py --limit 5       # first N programs, for a smoke run

Needs dafny and a DafnyBench checkout ($T_CORPORA, see corpora.py). Each
program costs one resolve plus one `dafny run`, so the full tier is minutes,
not seconds.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import corpora           # noqa: E402
import interp            # noqa: E402
import lift_check        # noqa: E402
import lift_classify     # noqa: E402
import lift_parse        # noqa: E402
import lift_resolve      # noqa: E402
import lift_rewrite      # noqa: E402
import mbpp_dfy          # noqa: E402
from lift_ast import Refusal  # noqa: E402

TIMEOUT_S = 200.0


def gate_tier() -> list[dict]:
    """The programs the gate can speak about today: MBPP-DFY, called in
    fragment by the census, and carrying at least one human-written point
    that lands inside t's int/bool/seq<int> fragment."""
    if not corpora.available(corpora.INFRAGMENT_TXT):
        return []
    infragment = set(corpora.INFRAGMENT_TXT.read_text(
        encoding="utf-8").split())
    return [r for r in mbpp_dfy.tier()
            if r["dfy"] in infragment and r["points"]]


def _front_end(dfy_path: Path):
    """resolve -> parse -> gradable -> classify -> rewrite, the chain
    `lifter.lift_file` runs, returning (task, source, closure) for the first
    gradable method or (None, None, reason)."""
    rr = lift_resolve.resolve(dfy_path, TIMEOUT_S)
    if rr.refusal is not None:
        return None, None, "resolve:%s" % rr.refusal.reason
    module = lift_parse.parse(rr.rprint_text)
    methods = lift_parse.gradable_methods(module)
    if not methods:
        return None, None, "no-gradable-method"
    method = methods[0]
    plan = lift_classify.classify(module, method)
    if isinstance(plan, Refusal):
        return None, None, "classify:%s" % plan.reason
    rprint_sha256 = hashlib.sha256(
        rr.rprint_text.encode("utf-8")).hexdigest()
    rw = lift_rewrite.rewrite(module, plan, str(dfy_path), rprint_sha256)
    if isinstance(rw, Refusal):
        return None, None, "rewrite:%s" % rw.reason
    task = rw.task if hasattr(rw, "task") else rw
    return task, (method, plan.closure), None


def human_points(task: dict, row: dict):
    """The row's MBPP points as the harness's (env, value) pairs.

    Mapped POSITIONALLY onto the task's own parameter names: MBPP names the
    Python function's arguments and the Dafny source names its own, and the
    only thing the two agree on is order. A point whose arity or type does
    not match the task's signature is dropped and named, because feeding a
    seq where the method wants an int would produce a Dafny compile error
    that looks like a fidelity failure and is not one.
    """
    params = [(p["name"], p["type"]) for p in task["params"]]
    out, skipped = [], []
    for p in row["points"]:
        args = p["args"]
        if len(args) != len(params):
            skipped.append((p["assert"], "arity %d vs %d"
                            % (len(args), len(params))))
            continue
        env, ok = {}, True
        for (name, ty), (kind, val) in zip(params, args):
            if kind != ty:
                skipped.append((p["assert"], "%s wants %s, got %s"
                                % (name, ty, kind)))
                ok = False
                break
            env[name] = tuple(val) if ty == "seq" else val
        if ok:
            out.append((env, None))
    return out, skipped


def run_arm(task, source, closure, points, tag):
    """Build and run one differential harness over `points`."""
    if not points:
        return {"arm": tag, "verdict": "no-points", "points": 0, "bad": None}
    text = lift_check._build_differential_with_points(
        task, source, closure, points)
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / ("%s.%s.dfy" % (task["name"], tag))
        path.write_text(text, encoding="utf-8", newline="\n")
        exit_code, _printed, n, bad, _out = lift_check._run_differential(
            path, TIMEOUT_S)
    if bad < 0:
        return {"arm": tag, "verdict": "arm-unavailable", "points": n,
                "bad": None, "exit": exit_code}
    return {"arm": tag, "verdict": ("agrees on %d points" % n) if bad == 0
            else ("bad=%d of %d points" % (bad, n)),
            "points": n, "bad": bad, "exit": exit_code}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args(argv)

    tier = gate_tier()
    if not tier:
        print("gate: cannot run. " + corpora.why_missing(
            corpora.CORPUS_DIR, corpora.INFRAGMENT_TXT))
        return 1
    if args.limit:
        tier = tier[:args.limit]

    print("MBPP-DFY gate tier: %d programs (in fragment, with human points)"
          % len(tier))
    print()
    print("%-42s %-22s %-22s" % ("program", "ladder arm", "human arm"))
    print("-" * 88)

    results = []
    for row in tier:
        dfy = corpora.CORPUS_DIR / row["dfy"]
        task, sc, why = _front_end(dfy)
        if task is None:
            print("%-42s %s" % (row["dfy"][:41], "front end: " + str(why)))
            results.append({"dfy": row["dfy"], "error": why})
            continue
        source, closure = sc

        ladder = run_arm(task, source, closure,
                         interp.Reference(task).points[:lift_check.DIFF_MAX_POINTS],
                         "ladder")
        pts, skipped = human_points(task, row)
        human = run_arm(task, source, closure, pts, "human")

        print("%-42s %-22s %-22s" % (row["dfy"][:41].replace(
            "dafny-synthesis_task_id_", "task_"),
            ladder["verdict"][:21], human["verdict"][:21]))
        results.append({"dfy": row["dfy"], "task": task["name"],
                        "ladder": ladder, "human": human,
                        "points_skipped": skipped})

    print("-" * 88)
    ok = [r for r in results if r.get("ladder", {}).get("bad") == 0
          and r.get("human", {}).get("bad") == 0]
    bad = [r for r in results
           if (r.get("ladder", {}).get("bad") or 0) > 0
           or (r.get("human", {}).get("bad") or 0) > 0]
    unavail = [r for r in results if r not in ok and r not in bad]

    hpts = sum(r.get("human", {}).get("points", 0) for r in results)
    lpts = sum(r.get("ladder", {}).get("points", 0) for r in results)
    print("both arms bad=0:      %d of %d" % (len(ok), len(results)))
    print("a disagreement:       %d" % len(bad))
    print("an arm unavailable:   %d" % len(unavail))
    print("points run:           %d ladder, %d human" % (lpts, hpts))

    if args.json:
        args.json.write_text(json.dumps(results, indent=2, default=str),
                             encoding="utf-8", newline="\n")
        print("wrote %s" % args.json)

    print()
    if bad:
        print("GATE FAILED: %d program(s) disagree with their source. No "
              "coverage number over nl/ means anything until this is 0."
              % len(bad))
        return 1
    if unavail:
        print("GATE NOT PASSED: %d program(s) could not be measured. An arm "
              "that did not run is not an arm that agreed." % len(unavail))
        return 1
    print("GATE PASSED on %d programs: both arms bad=0." % len(ok))
    return 0


if __name__ == "__main__":
    sys.exit(main())
