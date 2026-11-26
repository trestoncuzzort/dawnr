#!/usr/bin/env python3
"""t/verify_reader_census.py -- how many of MBPP's problems `dawnr verify` can pose, by the reader it reads them with.

    python3 t/verify_reader_census.py [--json OUT]

A problem is posable when every one of its tests is read into `t` values, as `dawnr verify` reads a person's tests
(t/answer.py entry_of; with --test given, verify_py.entry_for). Before is the wider reader of 2026-10-05
(t/PREDICT-2026-10-05-wider-reader.md: 796 of 974); after is the typed reader of 2026-11-26 (t/typed_values.py).
Each problem the wider reader refuses is grouped by its first refusal, as the investigation of 2026-11-26 grouped
it: a float, a tuple mixing kinds, a dict, deeper nesting (three list levels, or rows that hold strings, which are
three levels in `t`), a list mixing kinds, None, a set, a list of bools, an object, other.

For each problem now posable it also says whether t/to_python.py's comparison of a proved program with the
function would carry the types the question suggests (verify_py._carried), since `verify` shows a twin only after
that comparison: a posed question whose types it does not carry is refused there, by name. This counts posing, not
proving: no model and no prover is run.

It also checks that the typed reader reads every problem the wider reader read exactly as the wider reader does.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import answer                                                   # noqa: E402
import mbpp_dfy                                                 # noqa: E402
import typed_values                                             # noqa: E402
import verify_py                                                # noqa: E402

WIDE = dict(strings=True, nested_strings=True, tuples=True, nested_ints=True)
GROUPS = ("float", "tuple mixing kinds", "dict", "deeper nesting", "list mixing kinds", "None", "set", "list of bools",
          "object", "other")


def _shape(v) -> str:
    return ("bool" if isinstance(v, bool) else "int" if isinstance(v, int) else "str" if isinstance(v, str)
            else "float" if isinstance(v, float) else "coll" if isinstance(v, (list, tuple)) else type(v).__name__)


def _depth(v) -> int:
    return 1 + max((_depth(x) for x in v), default=0) if isinstance(v, (list, tuple)) else 0


def _mixes(v, kind) -> bool:
    if isinstance(v, kind) and len({_shape(x) for x in v}) > 1:
        return True
    return isinstance(v, (list, tuple)) and any(_mixes(x, kind) for x in v)


def group(why: str, tests: list[str]) -> str:
    """The investigation's grouping of a first refusal (its inv-data/unread.py, with mixed.py's split of
    `seq-of-seq`; what mixed.py left unclassified are rows of strings, three levels in t, so deeper nesting)."""
    if "float" in why or "complex" in why or why == "arg:BinOp":
        return "float"
    if "seq-of-seq" in why:
        values = []
        for line in tests:
            try:
                test = ast.parse(line.strip()).body[0].test
                call = test.left if isinstance(test, ast.Compare) else test
                if isinstance(call, ast.Call):
                    values += [ast.literal_eval(a) for a in call.args]
                if isinstance(test, ast.Compare):
                    values.append(ast.literal_eval(test.comparators[0]))
            except Exception:                                   # noqa: BLE001 -- a value it cannot evaluate says nothing
                pass
        if any(_mixes(v, list) for v in values):
            return "list mixing kinds"
        if any(_mixes(v, tuple) for v in values):
            return "tuple mixing kinds"
        return "deeper nesting"
    if "dict" in why:
        return "dict"
    if "NoneType" in why:
        return "None"
    if why.endswith(":set"):
        return "set"
    if "seq-of-bool" in why:
        return "list of bools"
    if why in ("arg:Name", "arg:call:Pair"):
        return "object"
    return "other"


def carried(entry: dict) -> bool:
    """Whether the comparison with the function carries every typed position at the type the question suggests."""
    first = entry["points"][0]
    for i, (kind, _v) in enumerate(list(first["args"]) + [first["expected"]]):
        if not typed_values.is_typed(kind):
            continue
        ty = typed_values.type_of_kind(kind)
        cells = [(p["args"][i] if i < len(first["args"]) else p["expected"]) for p in entry["points"]]
        if not all(verify_py._carried(ty, v) for _k, v in cells):
            return False
    return True


def census(records: dict) -> dict:
    read = unchanged = 0
    rows, per = [], defaultdict(Counter)
    for tid, rec in sorted(records.items()):
        points = [mbpp_dfy.parse_assertion(a, **WIDE) for a in rec["test_list"]]
        bad = [p["why"] for p in points if not p["ok"]]
        if points and not bad:
            read += 1
            try:
                typed = answer.entry_of(rec["text"], rec["test_list"], typed=True)["points"]
                unchanged += [{k: v for k, v in p.items() if k != "raw"} for p in typed] == \
                    answer.entry_of(rec["text"], rec["test_list"])["points"]
            except ValueError:
                pass
            continue
        g = group(bad[0] if bad else "no tests", rec["test_list"])
        try:
            entry = answer.entry_of(rec["text"], rec["test_list"], typed=True)
            first = entry["points"][0]
            kinds = [k for k, _v in first["args"]] + [first["expected"][0]]
            types = sorted({typed_values.words(typed_values.type_of_kind(k)) for k in kinds if typed_values.is_typed(k)})
            posed, why, carries = True, None, carried(entry)
        except ValueError as error:
            posed, why, types, carries = False, str(error)[:240], [], False
        per[g]["refused by the wider reader"] += 1
        per[g]["posable"] += posed
        per[g]["posable, and the comparison carries the suggested types"] += carries
        rows.append({"id": tid, "first refusal": bad[0] if bad else "no tests", "group": g, "posable": posed,
                     "why not": why, "types": types, "comparison carries": carries})
    return {"problems": len(records), "read by the wider reader": read,
            "of those, read the same by the typed reader": unchanged,
            "refused by the wider reader": len(rows), "posable now": sum(r["posable"] for r in rows),
            "per first refusal": {g: dict(per[g]) for g in GROUPS if g in per}, "problems refused": rows}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", type=Path, help="write every refused problem's row here")
    a = ap.parse_args(argv)
    out = census(mbpp_dfy.mbpp_records())
    if a.json:
        a.json.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "problems refused"}, indent=1))
    return 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
