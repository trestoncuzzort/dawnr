#!/usr/bin/env python3
"""t/audit_reference_types.py -- does a problem's reference behave the same on the value the
specification check hands it as on the value the problem's own assertions use?

    python3 t/audit_reference_types.py [--draws 200] [--out audit.json]

t represents a string as a sequence of integers, and t/spec_check.check_task calls the problem's
Python solution with that list. Two things can go wrong for a problem whose assertions pass a
str. The solution raises on the list (TypeError, AttributeError): known since 2026-09-18, the
check then reports "no valid draws" and counts nothing. Or the solution runs and silently
computes another function, because every comparison against a character literal is false:
MBPP 771's bracket balancer, fed integers, answers "the length is even". A specification that
says "even length" then agrees with it on every draw (found 2026-09-30 in the base-rate run,
t/PREDICT-2026-09-30-dawnr-base-rate.md).

For every dev and held-out problem whose first assertion passes a str literal, this draws the
check's own inputs (spec_check.draw, shaped like the problem's example), calls the reference
both ways (the old list-of-integers call and the assertion-typed call spec_check makes since the
repair of 2026-09-30), and classes the problem: raises on every draw, silently differs on some
draw, or the same on every draw. It reads references and assertions only; no model answer is
involved. It stays as the record of the class the repair closed.

EvalPlus (arXiv:2305.01210; https://github.com/evalplus/evalplus, evalplus/gen/type_mut.py)
grows test inputs by type-aware mutation in which a str stays a str and every new input is
validated by executing the ground truth; the repair this audit points at is the same rule for
the check's reference calls.
"""
from __future__ import annotations

import argparse
import ast
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import spec_check                                                # noqa: E402


class _Timeout(Exception):
    pass


def str_positions(entry: dict) -> list[int]:
    """The argument positions that are str literals in the problem's first parseable assertion."""
    for src in entry["rec"].get("test_list", []):
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == entry["fn"]:
                return [i for i, a in enumerate(node.args)
                        if isinstance(a, ast.Constant) and isinstance(a.value, str)]
    return []


def normalise(v):
    """One representation for the two calls' outputs: a str is its code points, and a one-element
    list of an integer is that integer, because a character comes back as an int from the integer
    call and as a one-character str from the string call (MBPP 565 splits a word into characters:
    the same answer either way). A reference whose two answers are [5] and 5 is therefore read as
    agreeing; the audit under-reports that case rather than inventing differences."""
    if isinstance(v, str):
        v = [ord(c) for c in v]
    if isinstance(v, (list, tuple)):
        items = [normalise(x) for x in v]
        if len(items) == 1 and isinstance(items[0], int) and not isinstance(items[0], bool):
            return items[0]
        return items
    return v


def as_the_assertion_types(args: list, positions: list[int]) -> list:
    """The drawn arguments with each str position made a str again: a list of code points joined,
    a single code point (a character argument) as a one-character str."""
    out = []
    for i, a in enumerate(args):
        if i in positions and isinstance(a, list):
            out.append("".join(chr(c) for c in a))
        elif i in positions and isinstance(a, int) and not isinstance(a, bool):
            out.append(chr(a))
        else:
            out.append(list(a) if isinstance(a, list) else a)
    return out


def _call(fn, args, seconds: int = 2):
    try:
        with spec_check.deadline(seconds, exc=_Timeout):          # portable since 2026-09-30 (SIGALRM is Unix-only)
            return "ok", normalise(fn(*args))
    except _Timeout:
        return "timeout", None
    except Exception as e:                                        # noqa: BLE001
        return "raise", type(e).__name__


def classify(entry: dict, draws: int = 200, seed: int = 0) -> dict | None:
    """None when no assertion passes a str or there is no reference; else the counts over
    `draws` of the check's own inputs and the class they put the problem in."""
    positions = str_positions(entry)
    fn = spec_check.reference(entry["rec"], entry["fn"]) if positions else None
    if fn is None:
        return None
    kinds = [k for k, _v in entry["points"][0]["args"]]
    examples = [v for _k, v in entry["points"][0]["args"]]
    rnd = random.Random(seed)
    raised = differs = same = string_refused = 0
    witness = None
    for _ in range(draws):
        args = [spec_check.draw(k, rnd, ex) for k, ex in zip(kinds, examples)]
        if any(a is None for a in args):
            break
        as_ints = _call(fn, [list(a) if isinstance(a, list) else a for a in args])
        try:
            typed = as_the_assertion_types(args, positions)
        except (ValueError, TypeError):
            continue
        as_str = _call(fn, typed)
        if as_ints[0] != "ok":
            raised += 1
        elif as_str[0] != "ok":
            string_refused += 1
        elif as_ints[1] != as_str[1]:
            differs += 1
            witness = witness or {"args": args, "on_integers": as_ints[1], "on_the_string": as_str[1]}
        else:
            same += 1
    ran = differs + same
    kind = "differs" if differs else "raises" if raised and not ran else "same" if ran else "unclassified"
    return {"class": kind, "raised": raised, "differs": differs, "same": same,
            "string_refused": string_refused, "witness": witness}


def main(argv=None) -> int:
    import loop_filter
    import spec_experiment as se
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--split", type=Path, default=HERE / "out" / "loop" / "split-v5.json")
    ap.add_argument("--decontamination", type=Path, default=HERE / "decontamination-2026-09-21.json")
    ap.add_argument("--draws", type=int, default=200)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    pool = se.pool("v5")
    eval_ids = sorted(int(i) for i in json.loads(a.split.read_text(encoding="utf-8"))["eval_ids"])
    overlap = {int(i) for i in json.loads(a.decontamination.read_text(encoding="utf-8"))["overlap_ids"]}
    report: dict = {"draws": a.draws, "sets": {}}
    for name, ids in (("dev", sorted(loop_filter.r12_dev_ids())), ("held-out", eval_ids)):
        rows = {}
        for tid in ids:
            entry = pool.get(tid)
            if entry and entry.get("points"):
                r = classify(entry, a.draws, seed=tid)
                if r is not None:
                    rows[tid] = {"fn": entry["fn"], **r}
        by = {k: sorted(t for t, r in rows.items() if r["class"] == k) for k in ("raises", "differs", "same", "unclassified")}
        summary = {"problems": len(ids), "take_a_string": len(rows), **{k: len(v) for k, v in by.items()},
                   "differs_ids": by["differs"]}
        if name == "held-out":
            summary["differs_on_the_clean_200"] = [t for t in by["differs"] if t not in overlap]
        report["sets"][name] = {"summary": summary, "problems": {str(t): r for t, r in rows.items()}}
        print(name, json.dumps(summary))
    if a.out:
        a.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
