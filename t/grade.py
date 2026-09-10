#!/usr/bin/env python3
"""grade.py: ROADMAP WS-19 move 1, the grader as one artifact.

t already runs its own tasks (run_par.py, run_all.py) and its own model
replies (spec_experiment.py), through the same cell/gate/flake machinery,
but as two drivers wired for our own runs, in our own layout, reported in
our own two files. This is the single entry point: a reader who has never
seen the repo runs a model against it and reads one table, whether the
input is a directory of t task files or a model's replies.

    python3 grade.py --tasks DIR [--out DIR] [--jobs N] [--kernels a,b,c] [--flake N]
    python3 grade.py --replies PATH [--out DIR] [--jobs N] [--kernels a,b,c] [--flake N]

--tasks grades t task files directly: every *.json in DIR is graded exactly
as run_par.py grades t/tasks, through the SAME functions (run_par.probe_backends,
run_par.lower_and_dispatch, run_par.format_table): no cell, gate or flake
rule is reimplemented here, only called.

--replies grades a model's replies. PATH is either:
  - a directory in the spec experiment's raw record layout
    (spec_experiment.py's out/spec-experiment/<tag>/raw/<task_id>.json,
    one file per problem, {"task_id", "fn", "reply", "pool_version", ...}),
    or
  - a plain JSONL file, one object per line, {"id": ..., "reply": "...",
    "tests": [...optional MBPP-style assert strings...]}.
Each reply's first fenced t block (spec_experiment.find_block: a ```t
fence, or failing that a bare `t 0`/`t 1` header) is parsed with
surface.parse, renamed to a name unique to its record id (spec_experiment.
rename_task's approach: also fixing every self-call), checked with
fuzz_lower.check_wf, and, if well-formed, written to --out/tasks/ and
graded exactly like --tasks. A record whose block does not parse or is not
well-formed is refused and named (mirroring spec_experiment.cmd_extract's
stages: no-block, parse:<message>, wf:<messages>), never dropped silently.
Optional tests, MBPP-style assert strings, are run through the interpreter
(mbpp_dfy.parse_assertion + spec_experiment.run_point, the identical
functions spec_experiment.py's own `tests` stage calls) for the JSONL
form's own `tests` field, or, for the raw-record-directory form, from the
record's own pool (spec_experiment.pool(pool_version), keyed by task_id),
which is what spec_experiment.py's `tests` stage already does for that
same record. Nothing about test execution is reimplemented; the same
functions are called.

Output under --out (default t/out/grade):
  verdicts.json   per task: each column's real and twin outcome, the flake
                  agreement flag, whether that column counts (real VERIFIED,
                  twin REFUTED, agreed), and whether that kernel's
                  certificate was accepted (exactly "twin == REFUTED", per
                  every verifiers/<kernel>.py docstring: REFUTED is minted
                  if and only if the certificate is accepted, so the two
                  are the same fact under two names); the twin's operator
                  (SPEC.md "The twins" ladder tag) and its witness, and the
                  witness kind (a proof witness, "exit" or "preservation",
                  for INVARIANT-DROP, else a value witness); the row's gate
                  (AGREEMENT.md's own definition of Agreement: verified /
                  refuted, agreed, in EVERY present column) and how many
                  present columns count; the run's backend versions and
                  which kernels answered; for --replies, the extract stage
                  per record and the tests verdict per record; and a
                  top-level summary (task count, kernel count, the
                  columns-counting histogram, how many tasks count in every
                  present kernel, wall time, and the same all_ok the exit
                  code reports).
  table.md        AGREEMENT.md's exact format (run_par.format_table,
                  called directly, not re-derived).
  summary.txt     one paragraph.

Reuses run_par.py's probe/lower/dispatch/table functions and
spec_experiment.py's find_block/rename_task/pool/run_point; the only
grade.py-owned logic is extraction bookkeeping (naming a record, tallying
stages) and the small MBPP-assertion-verdict aggregation duplicated from
spec_experiment.cmd_tests (five lines: pass/fail/signature/requires-
excluded/undefined), because spec_experiment.py is not a file this task
owns and that aggregation is not itself a cell, gate or flake rule.

Exit code matches run_par.py's convention: 0 on full agreement (every
graded task counts in every present kernel), 1 on any disagreement or
refusal recorded in the table, 2 on an operational refusal (fewer than
T_MIN_KERNELS kernels answered; both --tasks and --replies given or
neither).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import fuzz_lower                    # noqa: E402  (NAME_RE, check_wf)
import harness                       # noqa: E402
import mbpp_dfy                      # noqa: E402  (parse_assertion, for JSONL tests)
import run_par                       # noqa: E402  (probe_backends, lower_and_dispatch, format_table)
import spec_experiment as se         # noqa: E402  (find_block, rename_task, pool, run_point)
import surface                       # noqa: E402
from verifiers import Outcome, acquire_run_lock   # noqa: E402


# --------------------------------------------------------------- extract --

def _safe_name(prefix: str, tid, hint: str | None) -> str:
    """A name fuzz_lower.NAME_RE accepts, unique to (prefix, tid): the same
    shape spec_experiment.cmd_extract uses (`mbpp_<id>__<fn>`, falling back
    to `mbpp_<id>` when the hint would make an illegal identifier), widened
    to any prefix/id so a JSONL id that is not a bare integer still names a
    legal, readable task."""
    tid_s = re.sub(r"[^A-Za-z0-9_]", "_", str(tid))
    if hint:
        cand = f"{prefix}_{tid_s}__{re.sub(r'[^A-Za-z0-9_]', '_', hint)}"
        if fuzz_lower.NAME_RE.match(cand):
            return cand
    cand = f"{prefix}_{tid_s}"
    if fuzz_lower.NAME_RE.match(cand):
        return cand
    return f"{prefix}_id" if prefix and prefix[0].isalpha() else f"g_{prefix}_id"


def extract_one(reply: str, tid, fn_hint: str | None, prefix: str) -> dict:
    """One reply -> {"stage": "no-block"|"parse"|"wf"|"task", ...}, the same
    four stages spec_experiment.cmd_extract counts, using its own
    find_block and rename_task so a fenced block is found and a task is
    renamed exactly as the spec experiment's own extraction does."""
    block = se.find_block(reply)
    if block is None:
        return {"stage": "no-block"}
    try:
        task = surface.parse(block)
    except surface.SurfaceError as e:
        return {"stage": "parse", "why": str(e)[:200]}
    except Exception as e:                                   # noqa: BLE001
        return {"stage": "parse", "why": f"{type(e).__name__}: {e}"[:200]}
    name = _safe_name(prefix, tid, fn_hint or task.get("name"))
    task = se.rename_task(task, name)
    try:
        errs = fuzz_lower.check_wf(task)
    except Exception as e:                                   # noqa: BLE001
        errs = [f"check_wf raised {type(e).__name__}: {e}"[:200]]
    if errs:
        return {"stage": "wf", "why": "; ".join(errs)[:300], "name": name}
    return {"stage": "task", "task": task, "name": name}


def _load_records(path: Path):
    """Yield (kind, tid, record): kind "raw" for the spec experiment's
    out/spec-experiment/<tag>/raw/ layout (path is that directory, one
    <task_id>.json per file), kind "jsonl" for a plain JSONL file, one
    object per line, {"id", "reply", "tests": optional}."""
    if path.is_dir():
        for p in sorted(path.glob("*.json"),
                        key=lambda p: (len(p.stem), p.stem)):
            rec = json.loads(p.read_text(encoding="utf-8"))
            yield "raw", rec.get("task_id", p.stem), rec
    else:
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            yield "jsonl", rec.get("id", i), rec


def _overall(verdicts: list[str]) -> str:
    """The same aggregation spec_experiment.cmd_tests applies to one
    problem's points: pass iff every point passes; else signature beats
    fail beats requires-excluded beats undefined, in that order (five
    lines, duplicated from cmd_tests because spec_experiment.py is not
    among the files this task owns; not a cell, gate or flake rule)."""
    if all(v == "pass" for v in verdicts):
        return "pass"
    if any(v in ("arity", "type") for v in verdicts):
        return "signature"
    if any(v == "fail" for v in verdicts):
        return "fail"
    if any(v == "requires-excluded" for v in verdicts):
        return "requires-excluded"
    return "undefined"


def cmd_replies(args) -> dict:
    """Extract + check_wf + (optional) tests for every record under
    args.replies, writing each well-formed task to args.out/tasks/. Returns
    {"extract": ..., "tests": ...} for verdicts.json; the tasks directory
    it wrote is graded next, by the same path --tasks uses."""
    tasks_dir = args.out / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    extract_results: dict[str, dict] = {}
    tests_results: dict[str, dict] = {}
    pools: dict[str, dict] = {}

    for kind, tid, rec in _load_records(args.replies):
        reply = rec.get("reply", "")
        fn_hint = rec.get("fn")
        prefix = "mbpp" if kind == "raw" else "g"
        res = extract_one(reply, tid, fn_hint, prefix)
        entry = {"stage": res["stage"]}
        if "why" in res:
            entry["why"] = res["why"]
        if "name" in res:
            entry["name"] = res["name"]
        extract_results[str(tid)] = entry
        if res["stage"] != "task":
            continue
        task, name = res["task"], res["name"]
        (tasks_dir / f"{name}.json").write_text(
            json.dumps(task, indent=1), encoding="utf-8")

        points = None
        if kind == "raw":
            pv = rec.get("pool_version", "v1")
            if pv not in pools:
                pools[pv] = se.pool(pv)
            pentry = pools[pv].get(tid)
            if pentry is not None:
                points = pentry["points"]
        elif rec.get("tests"):
            parsed = [mbpp_dfy.parse_assertion(a) for a in rec["tests"]]
            points = [p for p in parsed if p.get("ok")]
            if len(points) != len(parsed):
                entry["tests_refused"] = len(parsed) - len(points)

        if points:
            pts = [se.run_point(task, p) for p in points]
            overall = _overall([p["verdict"] for p in pts])
            tests_results[str(tid)] = {"name": name, "overall": overall, "points": pts}

    (args.out / "extract.json").write_text(
        json.dumps(extract_results, indent=1), encoding="utf-8")
    (args.out / "tests.json").write_text(
        json.dumps(tests_results, indent=1), encoding="utf-8")
    return {"extract": extract_results, "tests": tests_results}


# ------------------------------------------------------------- kernel run --

def run_kernels(tasks: list[Path], out_dir: Path, jobs, kernels_arg, flake_n):
    """Probe the seven kernels and dispatch every cell, exactly as
    run_par.py's own main() does (probe_backends -> lower_and_dispatch),
    restricted to --kernels when given. Returns (cols, present_names, rows,
    wall_s, all_ok); cols always lists every kernel probe_backends() probes,
    so an excluded-by---kernels kernel is dropped from cols too rather than
    shown present with empty cells."""
    t0 = time.monotonic()
    cols_all, present_all = run_par.probe_backends()
    if kernels_arg:
        wanted = {k.strip() for k in kernels_arg.split(",") if k.strip()}
        cols = [c for c in cols_all if c[0] in wanted]
        present = [p for p in present_all if p[0] in wanted]
    else:
        cols, present = cols_all, present_all
    rows, wits, all_ok = run_par.lower_and_dispatch(
        tasks, present, jobs, flake_n=flake_n)
    wall_s = time.monotonic() - t0
    present_names = [b for b, v in cols if not v.startswith("ABSENT")]
    return cols, present_names, rows, wits, wall_s, all_ok


def build_verdicts(cols, rows, wits, tasks: list[Path], flake_n, wall_s) -> dict:
    """The per-task detail block for verdicts.json: each column's real/twin
    outcome, its flake agreement, whether it counts, and whether that
    kernel's certificate was accepted (== twin REFUTED, per every
    verifiers/<kernel>.py docstring: REFUTED is minted if and only if the
    certificate is accepted); the task's twin operator, witness and witness
    kind; the row's gate (AGREEMENT.md's Agreement: verified/refuted,
    agreed, in every present column) and its columns-counting count."""
    detail: dict[str, dict] = {}
    hist: dict[int, int] = {}
    n_gate = 0
    for tpath in tasks:
        task = harness.load(tpath)
        name = task["name"]
        twin_body, op, w = harness.twin_cached(task)
        columns = {}
        n_counting = 0
        for bname, _ver in cols:
            cell = rows.get(name, {}).get(bname)
            if cell is None:
                continue
            real, twin, agreed = cell
            counts = bool(real == Outcome.VERIFIED and twin == Outcome.REFUTED and agreed)
            if counts:
                n_counting += 1
            columns[bname] = {
                "real": real, "twin": twin, "agreed": bool(agreed),
                "counts": counts,
                "certificate_accepted": bool(twin == Outcome.REFUTED),
            }
        gate = bool(columns) and n_counting == len(columns)
        if gate:
            n_gate += 1
        hist[n_counting] = hist.get(n_counting, 0) + 1
        if twin_body is None:
            witness_line, witness_kind = None, None
        else:
            witness_line = harness.witness(w)
            witness_kind = (w or {}).get("_kind", "value")
        detail[name] = {
            "op": op, "witness": witness_line, "witness_kind": witness_kind,
            "columns": columns, "columns_counting": n_counting, "gate": gate,
        }
    present_names = [b for b, v in cols if not v.startswith("ABSENT")]
    return {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "backends": {b: v for b, v in cols},
        "kernels_present": present_names,
        "flake_n": flake_n,
        "tasks": detail,
        "summary": {
            "n_tasks": len(tasks),
            "n_kernels": len(cols),
            "n_kernels_present": len(present_names),
            "histogram_columns_counting": {str(k): v for k, v in sorted(hist.items())},
            "n_counting_in_all_present": n_gate,
            "wall_s": round(wall_s, 1),
        },
    }


def write_outputs(out_dir: Path, cols, rows, wits, tasks, flake_n, wall_s,
                  all_ok: bool, extra: dict | None = None) -> None:
    text = run_par.format_table(cols, rows, tasks, harness.OUT)
    (out_dir / "table.md").write_text(text, encoding="utf-8", newline="\n")

    verdicts = build_verdicts(cols, rows, wits, tasks, flake_n, wall_s)
    verdicts["summary"]["all_ok"] = all_ok
    if extra:
        verdicts.update(extra)
    (out_dir / "verdicts.json").write_text(
        json.dumps(verdicts, indent=1), encoding="utf-8")

    s = verdicts["summary"]
    present_names = verdicts["kernels_present"]
    para = (
        f"{s['n_tasks']} tasks graded, {s['n_kernels_present']} of {s['n_kernels']} "
        f"kernels present ({', '.join(present_names) if present_names else 'none'}); "
        f"{s['n_counting_in_all_present']} of {s['n_tasks']} count in every present "
        f"kernel (real verified, twin refuted by an accepted certificate, no flake "
        f"disagreement across {flake_n} runs); the columns-counting histogram is "
        f"{json.dumps(s['histogram_columns_counting'], sort_keys=True)}; the kernel "
        f"run's wall time was {wall_s:.1f}s. "
        + ("FULL AGREEMENT." if all_ok else "DISAGREEMENT: see table.md and verdicts.json.")
    )
    (out_dir / "summary.txt").write_text(para + "\n", encoding="utf-8")


# ------------------------------------------------------------------ main --

def cmd_tasks(args) -> int:
    args.out.mkdir(parents=True, exist_ok=True)
    harness.OUT = args.out
    harness.OUT.mkdir(parents=True, exist_ok=True)
    tasks = sorted(args.tasks.glob("*.json"))
    if not tasks:
        print(f"\nREFUSED: no tasks in {args.tasks}, nothing was verified. "
              f"Nothing written under {args.out}.")
        return 2
    cols, present_names, rows, wits, wall_s, all_ok = run_kernels(
        tasks, args.out, args.jobs, args.kernels, args.flake)
    if len(present_names) < args.min_kernels:
        print(f"\nREFUSED: {len(present_names)} kernel(s) available, "
              f"{args.min_kernels} required. Agreement across fewer than "
              f"two kernels is not agreement; it is one opinion, or none. "
              f"Nothing written under {args.out}.")
        for b, v in cols:
            if v.startswith("ABSENT"):
                print(f"  {b}: {v}")
        return 2
    write_outputs(args.out, cols, rows, wits, tasks, args.flake, wall_s, all_ok)
    print(f"\n{len(present_names)} kernels, {len(tasks)} tasks: "
          f"{'FULL AGREEMENT' if all_ok else 'DISAGREEMENT, see ' + str(args.out / 'table.md')}")
    return 0 if all_ok else 1


def cmd_replies_main(args) -> int:
    args.out.mkdir(parents=True, exist_ok=True)
    harness.OUT = args.out
    harness.OUT.mkdir(parents=True, exist_ok=True)
    extra = cmd_replies(args)
    tasks = sorted((args.out / "tasks").glob("*.json"))
    n_records = sum(1 for _ in _load_records(args.replies))
    stage_counts: dict[str, int] = {}
    for e in extra["extract"].values():
        stage_counts[e["stage"]] = stage_counts.get(e["stage"], 0) + 1
    print(f"extract: {n_records} replies; " +
          ", ".join(f"{k} {v}" for k, v in sorted(stage_counts.items())))
    cols, present_names, rows, wits, wall_s, all_ok = run_kernels(
        tasks, args.out, args.jobs, args.kernels, args.flake)
    if len(present_names) < args.min_kernels:
        print(f"\nREFUSED: {len(present_names)} kernel(s) available, "
              f"{args.min_kernels} required. Extraction results are written "
              f"under {args.out} (extract.json, tests.json); no kernel table.")
        for b, v in cols:
            if v.startswith("ABSENT"):
                print(f"  {b}: {v}")
        return 2
    write_outputs(args.out, cols, rows, wits, tasks, args.flake, wall_s, all_ok, extra=extra)
    print(f"\n{len(present_names)} kernels, {len(tasks)} well-formed tasks of "
          f"{n_records} replies: "
          f"{'FULL AGREEMENT' if all_ok else 'DISAGREEMENT, see ' + str(args.out / 'table.md')}")
    return 0 if all_ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="t's grader: one entry point for a tasks directory or a model's replies.")
    ap.add_argument("--tasks", type=Path,
                    help="directory of t task JSON files to grade")
    ap.add_argument("--replies", type=Path,
                    help="a model's replies: the spec experiment's raw record "
                         "directory, or a JSONL file of {id, reply, tests?}")
    ap.add_argument("--out", type=Path, default=HERE / "out" / "grade",
                    help="output directory (default t/out/grade)")
    ap.add_argument("--jobs", type=int, default=None,
                    help="cells in flight (run_par.py's --jobs)")
    ap.add_argument("--kernels", type=str, default=None,
                    help="comma-separated kernel names to grade (default: all seven)")
    ap.add_argument("--flake", type=int, default=3,
                    help="flake_check repeat count per verdict (default 3, "
                         "verifiers.cell_pair's own default)")
    ap.add_argument("--min-kernels", dest="min_kernels", type=int,
                    default=None,
                    help="refuse below this many present kernels (default: "
                         "T_MIN_KERNELS env var, or 2, run_par.py's own rule)")
    args = ap.parse_args(argv)
    if bool(args.tasks) == bool(args.replies):
        print("REFUSED: pass exactly one of --tasks or --replies.")
        return 2
    if args.min_kernels is None:
        import os
        args.min_kernels = int(os.environ.get("T_MIN_KERNELS", "2"))

    args.out.mkdir(parents=True, exist_ok=True)
    lock = acquire_run_lock(args.out)
    if not callable(lock):
        print(f"REFUSED: {lock}")
        return 2
    try:
        if args.tasks:
            return cmd_tasks(args)
        return cmd_replies_main(args)
    finally:
        lock()


if __name__ == "__main__":
    raise SystemExit(main())
