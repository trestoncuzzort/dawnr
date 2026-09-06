#!/usr/bin/env python3
"""mbpp_dfy.py -- the MBPP-DFY tier, and the input points people wrote for it.

DafnyBench's 785 ground-truth programs include 164 named
`dafny-synthesis_task_id_NNN.dfy`: Dafny versions of MBPP problems, the 164
that ROADMAP WS-13.1 and WS-16.2 call the MBPP-DFY programs. `nl/` holds the
MBPP originals, keyed by the same `task_id`, each carrying a `test_list` of
Python assertions.

Why that matters is nl/FIDELITY.md's argument in one line: the lifter's own
fidelity domain is built from the program's own literals (`interp.ladders` is
`[0,1,-1] + _around(literals) + INTS`, which gives `factorial`, `abs` and
`gcd` the identical 86 values), so it cannot find a divergence away from those
literals. The MBPP assertions were written by people who never saw the lifter.
They are few, but they are independent, and independence is the property the
ladder cannot have. MBPP task 605 tests `prime_num(-1010)`, and -1010 lies in
the ladder's untried interval between 40 and 10^6.

    python3 mbpp_dfy.py                # the tier, and how many points survive
    python3 mbpp_dfy.py --json OUT     # the join plus parsed points
    python3 mbpp_dfy.py --show 605     # one problem, its asserts and points

A point is usable only if every argument is in t's fragment: `int`, `bool`, or
`seq<int>` (`lower_dafny.TYPES`). An assertion over strings, dicts, tuples or
floats is REFUSED with a named reason and counted, never silently dropped, so
the surviving count is a measurement rather than a filter nobody audited. That
is the same discipline LIFTER-DECISIONS.md applies to constructs.

Standard library only. Reads gzipped JSONL and parses Python with `ast`;
nothing is executed, and no dafny is invoked.
"""
from __future__ import annotations

import argparse
import ast
import gzip
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import corpora  # noqa: E402

# nl/ sits beside t/ in the repo. The corpus is committed, unlike t-corpora.
NL_DATA = Path(__file__).resolve().parent.parent / "nl" / "data"
MBPP_SPLITS = ("mbpp.jsonl.gz", "mbpp_test.jsonl.gz",
               "mbpp_validation.jsonl.gz", "mbpp_prompt.jsonl.gz")

DFY_NAME_RE = re.compile(r"^dafny-synthesis_task_id_(\d+)\.dfy$")


def mbpp_records() -> dict[int, dict]:
    """Every MBPP record from all four splits, keyed by `task_id`."""
    out: dict[int, dict] = {}
    for split in MBPP_SPLITS:
        path = NL_DATA / split
        if not path.exists():
            continue
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line)
                    out[rec["task_id"]] = rec
    return out


def dfy_task_ids(corpus_dir: Path) -> dict[int, Path]:
    """The MBPP-DFY programs in a DafnyBench checkout, keyed by `task_id`."""
    out: dict[int, Path] = {}
    if not corpus_dir.exists():
        return out
    for p in sorted(corpus_dir.iterdir()):
        m = DFY_NAME_RE.match(p.name)
        if m:
            out[int(m.group(1))] = p
    return out


# ---------------------------------------------------------------------------
# Turning one Python assertion into a t-typed point.
# ---------------------------------------------------------------------------

def _literal(node: ast.AST):
    """A Python AST node as an int, bool, or list-of-int; else raise.

    Deliberately narrow. `ast.literal_eval` would happily return a string, a
    dict or a float, and the caller's job is to REFUSE those by name rather
    than carry them into a Dafny harness that has no word for them.
    """
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return ("bool", node.value)
        if isinstance(node.value, int):
            return ("int", node.value)
        raise _Unsupported(type(node.value).__name__)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        kind, v = _literal(node.operand)
        if kind != "int":
            raise _Unsupported("negated-" + kind)
        return ("int", -v)
    if isinstance(node, (ast.List, ast.Tuple)):
        if isinstance(node, ast.Tuple):
            raise _Unsupported("tuple")
        items = []
        for el in node.elts:
            kind, v = _literal(el)
            if kind != "int":
                raise _Unsupported("seq-of-" + kind)
            items.append(v)
        return ("seq", items)
    if isinstance(node, ast.Call):
        fn = getattr(node.func, "id", None) or getattr(node.func, "attr", "call")
        raise _Unsupported("call:" + str(fn))
    if isinstance(node, ast.Dict):
        raise _Unsupported("dict")
    if isinstance(node, ast.Set):
        raise _Unsupported("set")
    raise _Unsupported(type(node).__name__)


class _Unsupported(Exception):
    """An argument outside t's int/bool/seq<int> fragment, named."""


def parse_assertion(src: str) -> dict:
    """One MBPP `assert` line as {ok, fn, args, expected} or {ok: False, why}.

    Only the shape `assert f(a, b, ...) == expected` is accepted, plus the
    bare `assert f(...)` and `assert not f(...)` forms, which MBPP uses for
    boolean answers. Anything else (a comparison chain, `math.isclose`, an
    `in` test) is refused by name.
    """
    try:
        tree = ast.parse(src.strip(), mode="exec")
    except SyntaxError as e:
        return {"ok": False, "why": "syntax:%s" % e.msg}
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Assert):
        return {"ok": False, "why": "not-a-single-assert"}

    test = tree.body[0].test
    negate = False
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        negate, test = True, test.operand

    if isinstance(test, ast.Compare):
        if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
            return {"ok": False, "why": "comparison:%s"
                    % type(test.ops[0]).__name__.lower()}
        call, rhs = test.left, test.comparators[0]
    elif isinstance(test, ast.Call):
        call, rhs = test, None
    else:
        return {"ok": False, "why": "shape:%s" % type(test).__name__.lower()}

    if not isinstance(call, ast.Call):
        return {"ok": False, "why": "lhs-not-a-call"}
    fn = getattr(call.func, "id", None) or getattr(call.func, "attr", None)
    if fn is None:
        return {"ok": False, "why": "unnamed-callee"}
    if call.keywords:
        return {"ok": False, "why": "keyword-argument"}

    args = []
    for a in call.args:
        try:
            args.append(_literal(a))
        except _Unsupported as u:
            return {"ok": False, "why": "arg:%s" % u}

    if rhs is None:
        expected = ("bool", not negate)
    else:
        try:
            expected = _literal(rhs)
        except _Unsupported as u:
            return {"ok": False, "why": "expected:%s" % u}
        if negate:
            return {"ok": False, "why": "negated-equality"}

    return {"ok": True, "fn": fn, "args": args, "expected": expected}


def tier(corpus_dir: Path | None = None) -> list[dict]:
    """One row per MBPP-DFY program: the Dafny file, the MBPP record, and the
    assertions parsed into points with every refusal named."""
    corpus_dir = corpus_dir or corpora.CORPUS_DIR
    dfy = dfy_task_ids(corpus_dir)
    mbpp = mbpp_records()
    rows = []
    for task_id in sorted(dfy):
        rec = mbpp.get(task_id)
        row = {
            "task_id": task_id,
            "dfy": dfy[task_id].name,
            "matched": rec is not None,
            "text": rec["text"] if rec else None,
            "points": [],
            "refused": [],
        }
        for a in (rec or {}).get("test_list", []):
            parsed = parse_assertion(a)
            if parsed["ok"]:
                row["points"].append({"assert": a, "fn": parsed["fn"],
                                      "args": parsed["args"],
                                      "expected": parsed["expected"]})
            else:
                row["refused"].append({"assert": a, "why": parsed["why"]})
        rows.append(row)
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--corpus-dir", type=Path, default=corpora.CORPUS_DIR)
    ap.add_argument("--json", type=Path, default=None,
                    help="write the full join, points included, here")
    ap.add_argument("--show", type=int, default=None,
                    help="print one task_id's assertions and points")
    args = ap.parse_args(argv)

    if not args.corpus_dir.exists():
        print("no DafnyBench at %s. %s"
              % (args.corpus_dir, corpora.why_missing(args.corpus_dir)))
        return 1

    rows = tier(args.corpus_dir)
    if not rows:
        print("no dafny-synthesis_task_id_*.dfy under %s" % args.corpus_dir)
        return 1

    if args.show is not None:
        hit = [r for r in rows if r["task_id"] == args.show]
        if not hit:
            print("task_id %d is not in the MBPP-DFY tier" % args.show)
            return 1
        r = hit[0]
        print("%s  (MBPP task_id %d)" % (r["dfy"], r["task_id"]))
        print("  %s" % (r["text"] or "(unmatched)"))
        for p in r["points"]:
            print("  point   %s(%s) == %s"
                  % (p["fn"], ", ".join(repr(v) for _, v in p["args"]),
                     repr(p["expected"][1])))
        for x in r["refused"]:
            print("  refused %-18s %s" % (x["why"], x["assert"][:60]))
        return 0

    matched = [r for r in rows if r["matched"]]
    pts = sum(len(r["points"]) for r in rows)
    ref = sum(len(r["refused"]) for r in rows)
    usable = [r for r in rows if r["points"]]

    print("MBPP-DFY programs in %s: %d" % (args.corpus_dir.name, len(rows)))
    print("matched to an MBPP record:      %d (%.1f%%)"
          % (len(matched), 100 * len(matched) / len(rows)))
    print("assertions they carry:          %d" % (pts + ref))
    print("  parsed to t-typed points:     %d (%.1f%%)"
          % (pts, 100 * pts / max(1, pts + ref)))
    print("  refused, by reason:           %d" % ref)
    print("programs with >=1 usable point: %d (%.1f%%)"
          % (len(usable), 100 * len(usable) / len(rows)))

    why: dict[str, int] = {}
    for r in rows:
        for x in r["refused"]:
            key = x["why"].split(":")[0] if x["why"].startswith("arg:") else x["why"]
            why[x["why"]] = why.get(x["why"], 0) + 1
    if why:
        print()
        print("refusal reasons:")
        for k, n in sorted(why.items(), key=lambda kv: -kv[1]):
            print("  %-28s %d" % (k, n))

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(rows, indent=2), encoding="utf-8",
                             newline="\n")
        print()
        print("wrote %s" % args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
