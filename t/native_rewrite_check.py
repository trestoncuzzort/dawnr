#!/usr/bin/env python3
"""Do array and string inputs give the same answers as the arrays cases built by hand?

    python3 t/native_rewrite_check.py --fixtures t/native_fixtures --cbmc /path/to/cbmc --out /tmp/rewrites

Each published case named below is rewritten in a copy: the same pinned sources and the same
assertions, with the hand-written input plumbing replaced by an array or string input. The
published fixture is not changed. Both are run through the control suite one after the other, so
their times can be compared, and the report gives the verdicts and the lines of harness.

Replacements match exactly once or the script stops, so a changed fixture cannot be rewritten
by accident. Local precedent: t/PREDICT-2026-11-05-native-gate-model-gaps.md, predictions P6 and P7.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_case as cases

LIBUV_OLD = """    __CPROVER_assume(len >= 1 && len <= 5);
    /* one array per length, so that a read past the end of the input leaves its object */
    char s1[1], s2[2], s3[3], s4[4], s5[5];
    char *s = len == 1 ? s1 : len == 2 ? s2 : len == 3 ? s3 : len == 4 ? s4 : s5;
    s[0] = (char)b0;
    if (len > 1) s[1] = (char)b1;
    if (len > 2) s[2] = (char)b2;
    if (len > 3) s[3] = (char)b3;
    if (len > 4) s[4] = (char)b4;
    const char *p = s;
"""
LIBUV_NEW = """    unsigned len = s_len;
    unsigned char b0 = (unsigned char)s_e0, b1 = (unsigned char)s_e1, b2 = (unsigned char)s_e2, b3 = (unsigned char)s_e3;
    const char *p = s;
"""
FLAC_OLD = """    /* The string is the bytes b0 to b10 up to the first NUL byte, so its length is 0 to 11 and
       each character is any other byte. Position 11 holds the terminator. */
    char text[12];
    text[0] = (char)b0; text[1] = (char)b1; text[2] = (char)b2; text[3] = (char)b3;
    text[4] = (char)b4; text[5] = (char)b5; text[6] = (char)b6; text[7] = (char)b7;
    text[8] = (char)b8; text[9] = (char)b9; text[10] = (char)b10; text[11] = '\\0';
"""
LIBEVENT_OLD_DRAW = "".join(f"    __CPROVER_assume(count <= {index} || ch{index} != 0);\n" for index in range(11))
LIBEVENT_OLD = ("""    /* The string is count characters (0 to 11) of any value except the terminator, then the
       terminator. The characters after it are not part of the string and can have any value. */
    __CPROVER_assume(count <= 11);
""" + LIBEVENT_OLD_DRAW + """    char text[12];
    int pos = 0, negative = 0, digits = 0, shown, up;
    long long magnitude = 0, number;
    text[11] = '\\0';
    text[0] = (char)ch0; text[1] = (char)ch1; text[2] = (char)ch2; text[3] = (char)ch3;
    text[4] = (char)ch4; text[5] = (char)ch5; text[6] = (char)ch6; text[7] = (char)ch7;
    text[8] = (char)ch8; text[9] = (char)ch9; text[10] = (char)ch10;
    text[count] = '\\0';
""")
LIBEVENT_NEW = """    int count = (int)text_len;
    int pos = 0, negative = 0, digits = 0, shown, up;
    long long magnitude = 0, number;
"""
TEXT = [{"name": "text", "type": "char", "string": {"max": 11}}]
REWRITES = {
    "libuv-utf8-decode1": {"inputs": [{"name": "s", "type": "char", "array": {"min": 1, "max": 5}}], "assumptions": 0, "harness": [(LIBUV_OLD, LIBUV_NEW)]},
    "flac-metaflac-parse-uint32": {"inputs": TEXT, "assumptions": 0, "harness": [(FLAC_OLD, "")]},
    "libevent-servname-port-range": {"inputs": TEXT, "assumptions": 0, "harness": [(LIBEVENT_OLD, LIBEVENT_NEW)]},
}


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"{label}: the text to replace occurs {text.count(old)} times, not once")
    return text.replace(old, new)


def rewrite(root: Path, target: Path, change: dict) -> Path:
    shutil.copytree(root, target)
    case = json.loads((root / "case.json").read_text())
    harness = case["harness"]
    for old, new in change["harness"]:
        harness = replace_once(harness, old, new, case["id"])
    case.update(id=case["id"] + "-rewritten", inputs=change["inputs"], assumptions=change["assumptions"], harness=harness)
    (target / "case.json").write_text(json.dumps(case, indent=2) + "\n")
    return target


def row_view(summary: dict) -> list[dict]:
    return [{key: row.get(key) for key in ("variant", "unwind", "verdict", "properties", "confirmed_witnesses", "seconds", "ok")} for row in summary["rows"]]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fixtures", type=Path, default=Path(__file__).resolve().parent / "native_fixtures")
    parser.add_argument("--out", type=Path, required=True, help="new artifact directory; existing directories are refused")
    parser.add_argument("--cbmc", default="cbmc")
    parser.add_argument("--compiler", default="gcc")
    parser.add_argument("--timeout", type=float, default=1800)
    parser.add_argument("--memory-limit-mb", type=int, default=cases.DEFAULT_MEMORY_MB)
    parser.add_argument("--solver", choices=cases.SOLVERS, default=cases.DEFAULT_SOLVER)
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=False)
    report, same = [], True
    for name, change in REWRITES.items():
        root = args.fixtures / name
        new = rewrite(root, args.out / (name + "-case"), change)
        by_hand = cases.suite(root, args.out / (name + "-by-hand"), args.cbmc, args.timeout, args.compiler, args.memory_limit_mb, args.solver)
        rewritten = cases.suite(new, args.out / (name + "-rewritten"), args.cbmc, args.timeout, args.compiler, args.memory_limit_mb, args.solver)
        verdicts = [row["verdict"] for row in by_hand["rows"]], [row["verdict"] for row in rewritten["rows"]]
        fixed = [next(row["seconds"] for row in summary["rows"] if row["variant"] == "fixed") for summary in (by_hand, rewritten)]
        original = json.loads((args.out / (name + "-rewritten") / "original" / "receipt.json").read_text())
        witnesses = original.get("native_replay", {}).get("witnesses", [])
        entry = {"case": name, "same_verdicts": verdicts[0] == verdicts[1], "by_hand": row_view(by_hand), "rewritten": row_view(rewritten),
                 "harness_lines": [len(json.loads((directory / "case.json").read_text())["harness"].splitlines()) for directory in (root, new)],
                 "assumptions": [json.loads((directory / "case.json").read_text())["assumptions"] for directory in (root, new)],
                 "fixed_seconds": fixed, "fixed_time_ratio": round(fixed[1] / fixed[0], 2) if fixed[0] else None,
                 "witness_statuses": [witness["status"] for witness in witnesses], "failing_properties": sorted({witness["property"] for witness in witnesses}),
                 "witness_arrays": [witness.get("arrays") for witness in witnesses][:3]}
        same = same and entry["same_verdicts"] and rewritten["ok"]
        report.append(entry)
        print(json.dumps({key: entry[key] for key in ("case", "same_verdicts", "harness_lines", "assumptions", "fixed_seconds", "fixed_time_ratio", "witness_statuses")}), flush=True)
    (args.out / "rewrite-check.json").write_text(json.dumps({"format": cases.FORMAT + "-rewrite-check", "report": report}, indent=2, sort_keys=True) + "\n")
    return 0 if same else 1


if __name__ == "__main__":
    raise SystemExit(main())
