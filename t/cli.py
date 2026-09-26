#!/usr/bin/env python3
"""t/cli.py: one command, ROADMAP 14.4 ("One command").

Everything an editor or a script needs from t through a single entry
point, `python3 t/cli.py <subcommand> ...`, argparse, standard library
only (no dependency this file adds beyond what surface.py, check_wf.py,
tlib.py, harness.py, names.py and run_par.py already require):

    parse FILE.t [--json]              text/error -> canonical JSON AST
    check FILE.t [--json]               well-formedness diagnostics
    format FILE.t [--write]             the printer's canonical text
    lower FILE.t --kernel K|all [--out DIR]
    verify FILE.t|DIR [--kernels a,b] [--flake N] [--jobs N] [--table PATH] [--json]
    twin FILE.t [--json]                the ladder's chosen operator + witness
    explain WORD [--kernel K]           one sentence per kernel for an outcome word

Every flag also accepts `--flag=value` (argparse's own long-option form;
test_cli.py's test_flag_equals_form exercises this once, per the bar's
"state it and test it once").

Two output forms, chosen the same way on every subcommand: text for a
person by default, `--json` for an editor -- JSON Lines, one record per
diagnostic, each a JSON object with exactly the keys "file", "line",
"col", "rule", "severity", "kernel", "message". `severity` is one of
"error", "warning", "info", "verdict" ("verdict" for a kernel outcome
report -- verify/twin/explain -- which is not itself a defect, "error"
for a well-formedness or parse problem, and this file never emits
"warning"/"info" since neither surface.py nor check_wf.py distinguishes
them from "error" today; the field exists for a future rule that does).
`line`/`col` are `None` (JSON `null`) wherever the record is not about
one AST node (a verify/twin/explain record, or a WfError with no
position). `kernel` is `""` wherever the record is not about one kernel
(parse/check/format diagnostics).

Exit codes, the same meaning on every subcommand: 0 nothing wrong (every
diagnostic printed, if any, was informational; every verdict, if any, was
the flip verify() counts as agreement); 1 at least one diagnostic of
severity "error", or at least one verdict that is not the counted flip
(REFUSED, a kernel outcome that is not VERIFIED/REFUTED, a task that
REFUSES to yield a twin); 2 a usage problem (a bad flag, an unknown
kernel or verdict word) -- argparse itself already exits 2 for a bad
flag; this file returns 2 by hand for a bad subcommand argument argparse
cannot see (an unknown --kernel name, an unknown `explain` word).

`verify` on a DIRECTORY is the one subcommand that does not stand alone:
the bar requires its AGREEMENT.md to be byte-identical (modulo the
timestamp line) to run_par.py's own, so this file imports run_par's
`probe_backends`, `lower_and_dispatch` and `format_table` and calls them
in the same order main() does, rather than re-implementing any of the
cell/gate/flake machinery run_par.py, harness.py, grade.py and
verifiers/*.py already own (this file touches none of them). See
COMMAND.md's `verify` section for the one full-matrix run this item is
allowed, and its diff against t/AGREEMENT.md.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import harness                       # noqa: E402
import names                         # noqa: E402
import run_par                       # noqa: E402
import surface                       # noqa: E402
import tasks_io                      # noqa: E402
import tlib                          # noqa: E402
from check_wf import check_wf        # noqa: E402
from verifiers import Outcome        # noqa: E402

KERNELS = [b for b, _, _ in tlib.BACKENDS]
SUFFIX_FOR = {b: s for b, _, s in tlib.BACKENDS}

# The outcome words explain's vocabulary knows, straight from
# verifiers.Outcome (never a second taxonomy invented here).
_OUTCOME_WORDS = {
    Outcome.VERIFIED, Outcome.VACUOUS, Outcome.REFUTED, Outcome.MALFORMED,
    Outcome.TIMEOUT, Outcome.UNPROVED, Outcome.TOOL_ERROR,
}


# ===========================================================================
# Diagnostics: the one record shape every subcommand's --json prints.
# ===========================================================================

def diag(file=None, line=None, col=None, rule="", severity="error",
        kernel="", message="") -> dict:
    return {"file": file, "line": line, "col": col, "rule": rule,
            "severity": severity, "kernel": kernel, "message": message}


def print_json_lines(records) -> None:
    for r in records:
        print(json.dumps(r, sort_keys=True))


def surface_error_diag(exc: surface.SurfaceError, fallback_file: str) -> dict:
    return diag(file=exc.file or fallback_file, line=exc.line, col=exc.col,
               rule=exc.production or "", severity="error", kernel="",
               message=exc.message)


def wf_error_diag(err) -> dict:
    # A WfError built with positions=None is a plain str, not a WfError
    # (check_wf.py's own contract); callers here always pass positions=
    # {} so every element is a real WfError with .message/.rule/etc.
    return diag(file=err.file, line=err.line, col=err.col, rule=err.rule,
               severity="error", kernel="", message=err.message)


# ===========================================================================
# parse
# ===========================================================================

def cmd_parse(args) -> int:
    path = str(args.file)
    positions: dict = {}
    try:
        task = surface.parse_file(path, positions=positions)
    except surface.SurfaceError as exc:
        d = surface_error_diag(exc, path)
        if args.json:
            print_json_lines([d])
        else:
            print(str(exc))
        return 1
    print(json.dumps(task, indent=2, sort_keys=True))
    return 0


# ===========================================================================
# check
# ===========================================================================

def cmd_check(args) -> int:
    path = str(args.file)
    positions: dict = {}
    try:
        task = surface.parse_file(path, positions=positions)
    except surface.SurfaceError as exc:
        d = surface_error_diag(exc, path)
        if args.json:
            print_json_lines([d])
        else:
            print(str(exc))
        return 1
    errors = check_wf(task, positions=positions, file=path)
    if args.json:
        print_json_lines(wf_error_diag(e) for e in errors)
    elif errors:
        for e in errors:
            print(str(e))
    else:
        print(f"{path}: well-formed, no errors")
    return 1 if errors else 0


# ===========================================================================
# format
# ===========================================================================

def cmd_format(args) -> int:
    path = Path(args.file)
    try:
        task = surface.parse_file(str(path))
    except surface.SurfaceError as exc:
        if args.json:
            print_json_lines([surface_error_diag(exc, str(path))])
        else:
            print(str(exc))
        return 1
    try:
        text = surface.print_task(task)
    except surface.SurfaceError as exc:
        if args.json:
            print_json_lines([diag(file=str(path), rule="", severity="error",
                                    message=exc.message)])
        else:
            print(str(exc))
        return 1
    if args.write:
        path.write_text(text, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(text)
    return 0


# ===========================================================================
# lower
# ===========================================================================

def _lower_one(task: dict, kernel: str) -> str:
    return tlib.lower(task, kernel, twin_body=False)


def cmd_lower(args) -> int:
    path = str(args.file)
    positions: dict = {}
    try:
        task = surface.parse_file(path, positions=positions)
    except surface.SurfaceError as exc:
        if args.json:
            print_json_lines([surface_error_diag(exc, path)])
        else:
            print(str(exc))
        return 1

    kernels = KERNELS if args.kernel == "all" else [args.kernel]
    unknown = [k for k in kernels if k not in KERNELS]
    if unknown:
        print(f"cli.py lower: unknown kernel(s) {unknown}, known: {KERNELS}",
              file=sys.stderr)
        return 2

    out_dir = Path(args.out) if args.out else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    problems = []
    for kernel in kernels:
        try:
            src = _lower_one(task, kernel)
        except (NotImplementedError, ValueError) as e:
            problems.append(diag(file=path, rule="lower", severity="error",
                                 kernel=kernel, message=str(e)))
            continue
        if out_dir:
            dest = out_dir / f"{task['name']}.{SUFFIX_FOR[kernel]}"
            dest.write_text(src, encoding="utf-8", newline="\n")
            if not args.json:
                print(f"{kernel}: wrote {dest}")
        else:
            if not args.json:
                if len(kernels) > 1:
                    print(f"# kernel: {kernel}")
                sys.stdout.write(src)
                if not src.endswith("\n"):
                    sys.stdout.write("\n")

    if args.json:
        print_json_lines(problems)
    elif problems:
        for p in problems:
            print(f"{p['kernel']}: {p['message']}")
    return 1 if problems else 0


# ===========================================================================
# verify
# ===========================================================================

def _verify_file(args, path: Path) -> int:
    positions: dict = {}
    try:
        task = surface.parse_file(str(path), positions=positions)
    except surface.SurfaceError as exc:
        if args.json:
            print_json_lines([surface_error_diag(exc, str(path))])
        else:
            print(str(exc))
        return 1

    kernels = args.kernels.split(",") if args.kernels else None
    if kernels is not None:
        unknown = [k for k in kernels if k not in KERNELS]
        if unknown:
            print(f"cli.py verify: unknown kernel(s) {unknown}, known: {KERNELS}",
                  file=sys.stderr)
            return 2

    flake = args.flake if args.flake is not None else 3
    result = tlib.verify(task, kernels=kernels, flake=flake)

    records = []
    all_ok = True
    for kernel, entry in result.items():
        if entry.get("real") is None:
            all_ok = False
            sev = "verdict"
            msg = tlib.explain(entry)
        else:
            r, t = entry["real"], entry["twin"]
            flip = r == Outcome.VERIFIED and t == Outcome.REFUTED
            all_ok &= flip
            sev = "verdict"
            msg = tlib.explain(entry)
        records.append(diag(file=str(path), rule=entry.get("twin_op") or "",
                            severity=sev, kernel=kernel, message=msg))

    if args.json:
        print_json_lines(records)
    else:
        for r in records:
            print(f"{r['kernel']}: {r['message']}")
    return 0 if all_ok else 1


def _verify_dir(args, path: Path) -> int:
    if args.out:
        harness.OUT = Path(args.out)
    harness.OUT.mkdir(parents=True, exist_ok=True)
    table_path = Path(args.table) if args.table else HERE / "AGREEMENT.md"

    tasks = tasks_io.load_dir(path)
    # `t verify <dir>` writes t/AGREEMENT.md by default, the same accident as
    # a3c6f955 (a one-directory run replaced the committed matrix): the
    # committed table takes exactly the committed tasks and all seven kernels
    refusal = run_par.committed_task_refusal(table_path, tasks, False)
    if refusal:
        print(refusal, file=sys.stderr)
        return 2
    cols, present = run_par.probe_backends()
    if args.kernels:
        wanted = set(args.kernels.split(","))
        unknown = wanted - {b for b, _ in cols}
        if unknown:
            print(f"cli.py verify: unknown kernel(s) {sorted(unknown)}, "
                  f"known: {[b for b, _ in cols]}", file=sys.stderr)
            return 2
        cols = [c for c in cols if c[0] in wanted]
        present = [p for p in present if p[0] in wanted]
    refusal = run_par.committed_kernel_refusal(table_path, cols, False)
    if refusal:
        print(refusal, file=sys.stderr)
        return 2

    flake_n = args.flake if args.flake is not None else 3
    jobs_arg = args.jobs
    rows, wits, all_ok = run_par.lower_and_dispatch(tasks, present, jobs_arg, flake_n)

    present_names = [b for b, v in cols if not v.startswith("ABSENT")]
    import os
    min_kernels = int(os.environ.get("T_MIN_KERNELS", "2"))
    if len(present_names) < min_kernels:
        print(f"\nREFUSED: {len(present_names)} kernel(s) available, "
              f"{min_kernels} required. AGREEMENT.md not written.")
        return 2
    if not tasks:
        print("\nREFUSED: no tasks, nothing was verified. AGREEMENT.md not written.")
        return 2

    if args.json:
        records = []
        for tname, cells in rows.items():
            for bname, _ in cols:
                c = cells.get(bname)
                if c is None:
                    continue
                kind = harness.decorative_kind(c[0], c[1], wits.get(tname))
                twin_text = kind if kind is not None else c[1]
                good = c == (Outcome.VERIFIED, Outcome.REFUTED, True)
                records.append(diag(
                    file=str(path / f"{tname}.t"), rule="", severity="verdict",
                    kernel=bname,
                    message=f"real={c[0]} twin={twin_text}"
                            + ("" if c[2] else " (FLAKED)")
                            + ("" if good else " <-- FINDING")))
        print_json_lines(records)

    text = run_par.format_table(cols, rows, tasks, harness.OUT, wits)
    table_path.write_text(text, encoding="utf-8", newline="\n")
    if not args.json:
        print(f"\n{len(present_names)} kernels, {len(tasks)} tasks: "
              f"{'FULL AGREEMENT' if all_ok else 'DISAGREEMENT, see ' + str(table_path)}")
    return 0 if all_ok else 1


def cmd_verify(args) -> int:
    path = Path(args.target)
    if path.is_dir():
        return _verify_dir(args, path)
    return _verify_file(args, path)


# ===========================================================================
# twin
# ===========================================================================

def cmd_twin(args) -> int:
    path = str(args.file)
    try:
        task = surface.parse_file(path)
    except surface.SurfaceError as exc:
        if args.json:
            print_json_lines([surface_error_diag(exc, path)])
        else:
            print(str(exc))
        return 1

    twin_body, op, w = tlib.twin(task)
    if twin_body is None:
        msg = f"REFUSED: {harness.REFUSALS.get(op, op)}"
        d = diag(file=path, rule=op or "", severity="verdict", kernel="",
                message=msg)
        if args.json:
            print_json_lines([d])
        else:
            print(msg)
        return 1

    msg = f"{op}, witness: {harness.witness(w)}"
    d = diag(file=path, rule=op, severity="verdict", kernel="", message=msg)
    if args.json:
        print_json_lines([d])
    else:
        print(msg)
    return 0


# ===========================================================================
# explain
# ===========================================================================

def cmd_explain(args) -> int:
    word = args.verdict.lower()
    if word not in _OUTCOME_WORDS:
        print(f"cli.py explain: unknown verdict word {args.verdict!r}, "
              f"known: {sorted(_OUTCOME_WORDS)}", file=sys.stderr)
        return 2
    kernels = [args.kernel] if args.kernel else KERNELS
    unknown = [k for k in kernels if k not in KERNELS]
    if unknown:
        print(f"cli.py explain: unknown kernel(s) {unknown}, known: {KERNELS}",
              file=sys.stderr)
        return 2

    sentence = tlib._OUTCOME_SENTENCE.get(word, word)
    records = [diag(rule=word, severity="verdict", kernel=k,
                    message=f"{k}: {word} is {sentence}") for k in kernels]
    if args.json:
        print_json_lines(records)
    else:
        for r in records:
            print(r["message"])
    return 0


# ===========================================================================
# argparse wiring
# ===========================================================================

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="cli.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("parse", help="text to canonical JSON AST")
    p.add_argument("file", metavar="FILE.t")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_parse)

    p = sub.add_parser("check", help="well-formedness diagnostics")
    p.add_argument("file", metavar="FILE.t")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("format", help="the printer's canonical text")
    p.add_argument("file", metavar="FILE.t")
    p.add_argument("--write", action="store_true",
                  help="rewrite the file in place instead of stdout")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_format)

    p = sub.add_parser("lower", help="lowered source for one kernel or all")
    p.add_argument("file", metavar="FILE.t")
    p.add_argument("--kernel", required=True,
                  help=f"one of {KERNELS} or 'all'")
    p.add_argument("--out", metavar="DIR",
                  help="write lowered sources here instead of stdout")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_lower)

    p = sub.add_parser("verify", help="verify a file or a whole tasks/ directory")
    p.add_argument("target", metavar="FILE.t|DIR")
    p.add_argument("--kernels", metavar="a,b",
                  help="comma-separated kernel names (default: all present)")
    p.add_argument("--flake", type=int, default=None)
    p.add_argument("--jobs", type=int, default=None,
                  help="directory form only: cells in flight")
    p.add_argument("--table", metavar="PATH",
                  help="directory form only: where AGREEMENT.md is written")
    p.add_argument("--out", metavar="DIR",
                  help="directory form only: where lowered sources are written")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("twin", help="the ladder's chosen operator and witness")
    p.add_argument("file", metavar="FILE.t")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_twin)

    p = sub.add_parser("explain", help="what a verdict means, per kernel")
    p.add_argument("verdict", metavar="WORD",
                  help=f"one of {sorted(_OUTCOME_WORDS)}")
    p.add_argument("--kernel", help="restrict to one kernel (default: all)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_explain)

    return ap


def main(argv=None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    # A missing input is a usage error (exit 2), reported as one diagnostic
    # in whichever form was asked for, never a traceback (2026-09-11, found
    # by the independent check of 14.4).
    target = getattr(args, "file", None) or getattr(args, "target", None)
    if target is not None and not Path(target).exists():
        if getattr(args, "json", False):
            print(json.dumps({"file": str(target), "line": 0, "col": 0, "rule": "usage",
                              "severity": "error", "kernel": "",
                              "message": f"no such file or directory: {target}"}))
        else:
            print(f"cli.py {args.cmd if hasattr(args, 'cmd') else ''}: no such file or directory: {target}".replace("  ", " "), file=sys.stderr)
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
