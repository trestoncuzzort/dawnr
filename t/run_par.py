#!/usr/bin/env python3
"""run_par.py: cell-parallel driver for the t suite; run_all.py is the
reference instrument. Cells (task, backend) are independent, with distinct
out/ filenames, so this computes the identical (real, twin, agreed) tuple
per cell over a ProcessPoolExecutor instead of a for-loop, writing the
identical t/AGREEMENT.md format so the two tables diff cleanly modulo the
timestamp line.

Cross-check against run_all.py: DONE 2026-08-31, ubuntu-box: the two
tables are byte-identical modulo the timestamp line (65/66 cells
verified/refuted, the same count_matches x rocq timeout finding, exit 1
from both), serial 27 min vs parallel 9 min, the parallel time being the
slowest single cell (that rocq timeout, 3 x 180 s wall). Standing rule:
divergence between the two tables is a finding about the suite, not a
driver bug to paper over. Parallel is a second measurement, never a
faster stand-in trusted by default.

Inside a cell (2026-09-09): the six kernel calls (three flake runs for the
real, three for the twin) run concurrently through verifiers.cell_pair, so
a cell's wall is one budget, not six; measured before the change, the
180-task sweep at 96 jobs spent its last ten minutes on two cells. --jobs
is therefore cells in flight, and kernel-call concurrency is six times it:
on the Dell's 120 threads, --jobs 16 is the 96-prover regime that flaked 9
spark and framac cells on their wall backstops, --jobs 5 is the 30-prover
regime that ran clean. T_CELL_SERIAL=1 restores the sequential cell.
"""
from __future__ import annotations

import argparse
import importlib
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import harness                      # noqa: E402
import tasks_io                     # noqa: E402
from verifiers import Outcome, cell_pair, sha256_file, mp_context   # noqa: E402
import blockers                     # noqa: E402  (the sole-blocker section, ROADMAP WS-19 move 4)

BACKENDS = [
    ("dafny", "lower_dafny", "dfy"),
    ("verus", "lower_verus", "rs"),
    ("spark", "lower_spark", "ads"),
    ("framac", "lower_framac", "c"),
    ("lean", "lower_lean", "lean"),
    ("rocq", "lower_rocq", "v"),
    ("fstar", "lower_fstar", "fst"),
]


def _watch_event(**ev) -> None:
    """One JSON line per cell start and end, appended to the file named by
    T_WATCH (unset: nothing is written). t/watch_gui.py reads the file and
    opens one window per running cell. A single short write in append mode,
    so concurrent workers do not interleave lines. Added 2026-09-16."""
    path = os.environ.get("T_WATCH")
    if not path:
        return
    import json
    import time
    ev.update(pid=os.getpid(), t=time.time())
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev) + "\n")
    except OSError:
        pass


def _run_cell(bname: str, task_name: str, suffix: str, op: str, flake_n: int = 3):
    # Re-imported per call: correct under spawn (fresh interpreter, no
    # inherited module object); a sys.modules hit under fork, used below.
    # flake_n defaults to cell_pair's own default (3, everyone); grade.py's
    # --flake is the only caller that ever passes another value, so a bare
    # `python3 run_par.py` dispatch is unchanged.
    backend = importlib.import_module(f"verifiers.{bname}")
    real = harness.OUT / f"{task_name}.{suffix}"
    twin = harness.OUT / f"{task_name}_twin.{suffix}"
    _watch_event(ev="start", task=task_name, kernel=bname, op=op)
    try:
        (r_real, a1), (r_twin, a2) = cell_pair(backend.verify, real, twin, flake_n)
    except BaseException as e:
        _watch_event(ev="end", task=task_name, kernel=bname, real="error",
                     twin=type(e).__name__, agree=False)
        raise
    _watch_event(ev="end", task=task_name, kernel=bname, real=str(r_real.outcome),
                 twin=str(r_twin.outcome), agree=bool(a1 and a2))
    return task_name, bname, op, (r_real.outcome, r_twin.outcome, a1 and a2)


def probe_backends():
    """Probe every entry of BACKENDS for its kernel binary, exactly once, in
    the parent process, never inside a worker. Returns (cols, present):
    cols is [(bname, version_or_"ABSENT: ..."), ...] in BACKENDS order,
    covering every backend whether or not its kernel answered; present is
    the same backends restricted to the ones that did, as
    (bname, lower_fn, suffix), the shape lower_and_dispatch consumes.

    Split out of main() 2026-09-10 (ROADMAP WS-19 move 1) so grade.py can
    run the identical probe over the same seven kernels; the probing loop
    itself, and its one call to backend.version() per kernel, are unchanged
    from the form main() has run inline since this file was written."""
    cols, present = [], []
    for bname, lmod, suffix in BACKENDS:
        try:
            backend = importlib.import_module(f"verifiers.{bname}")
            ver = backend.version()     # binary probe: exactly once, only here, in the parent
        except (Exception, SystemExit) as e:               # noqa: BLE001
            cols.append((bname, f"ABSENT: {e}"))
            continue
        cols.append((bname, ver))
        present.append((bname, importlib.import_module(lmod).lower, suffix))
    return cols, present


def lower_and_dispatch(tasks: list[Path], present, jobs_arg, flake_n: int = 3):
    """Sequential lowering (real + twin, every (backend, task) pair from
    `present`) followed by the parallel cell dispatch: the pipeline main()
    has always run inline, between the backend probe and the table write.

    Returns (rows, wits, all_ok): rows maps task name -> {backend:
    (real_outcome, twin_outcome, agreed)}; wits maps task name -> its
    measured twin witness (a task with no twin has no entry); all_ok is
    False as soon as any (task, backend) pair has no twin, abstains, fails
    to lower, or disagrees with the flip rule (real VERIFIED, twin
    REFUTED, no flake disagreement).

    Split out of main() 2026-09-10 (ROADMAP WS-19 move 1) so grade.py can
    run the identical cell/gate/flake machinery over its own tasks and
    replies. `flake_n` defaults to 3 (cell_pair's own default, SPEC.md's
    "The twins" and verifiers/__init__.py's flake_check), so a bare
    `python3 run_par.py` invocation, which never passes it, is byte-
    identical to before; grade.py's --flake is the only caller that does."""
    rows = {harness.load(t)["name"]: {} for t in tasks}
    all_ok = True
    # Lowering + writes: sequential, entirely before any dispatch below, so
    # out/*.{suffix} has a single writer for the whole time it is produced.
    pending, wits = [], {}
    for bname, lower, suffix in present:
        for tpath in tasks:
            task = harness.load(tpath)
            name = task["name"]
            # The whole task, not just the body: the twin is chosen by a
            # measured witness (harness.twin_for), and the witness needs
            # params/requires/ensures to have anything to run on. Cached, so
            # the ladder search happens once per task, not once per backend.
            twin_body, op, w = harness.twin_cached(task)
            if twin_body is None:
                rows[name][bname] = ("no-twin", "no-twin", True)
                all_ok = False
                print(f"  {name} x {bname}: no twin, "
                      f"{harness.REFUSALS[op]}  <-- FINDING", flush=True)
                continue
            # real_witness (harness.py, ROADMAP 15.5): lowered with the
            # real's own measured witness when the bounded scan found one
            # (real VERIFIED, but its own body violates `ensures` on some
            # requires-admitted input, or is undefined there), so a sound
            # kernel's REFUTED on the real reads the same certificate a
            # twin's REFUTED does. None for every task the ladder's other
            # side already trusts (harness.real_witness), so an unchanged
            # committed task lowers byte-identically to before.
            rw = harness.real_witness(task)
            try:
                real_src = lower(task, task["body"], witness=rw)
                twin_src = lower(task, twin_body, witness=w)
            except NotImplementedError as e:
                rows[name][bname] = ("abstain", "abstain", True)
                all_ok = False
                print(f"  {name} x {bname}: ABSTAIN: {e}", flush=True)
                continue
            except Exception as e:                          # noqa: BLE001
                rows[name][bname] = ("lower-error", "lower-error", True)
                all_ok = False
                print(f"  {name} x {bname}: LOWER-ERROR {type(e).__name__}: {e}", flush=True)
                continue
            # newline="\n": the lowering's bytes are the verdict basis, hashed
            # into AGREEMENT.md. Path.write_text defaults to os.linesep, so a
            # Windows host produced CRLF sources whose hashes differed from
            # every other platform's for the same text (measured 2026-09-02:
            # abs.dfy 9147e4af… on Windows vs 9fe1e7e8… everywhere else,
            # equal after CRLF->LF). One newline choice, every host.
            # A LOWERING THAT EXPLODES IS NOT A VERDICT. Measured 2026-09-17 on the lab workstation: an answer
            # chaining 26 string `replace` calls lowered to Rocq as a 27.7 GB source, twice, which filled 52 GB
            # of a shared disk and wedged the run. A source past the cap is recorded and skipped, never run.
            cap = int(os.environ.get("T_MAX_SOURCE_MB", "64")) * 1024 * 1024
            if max(len(real_src), len(twin_src)) > cap:
                mb = max(len(real_src), len(twin_src)) / 1024 / 1024
                rows[name][bname] = ("lower-too-big", "lower-too-big", True)
                all_ok = False
                print(f"  {name} x {bname}: LOWER-TOO-BIG {mb:.0f} MB, over the "
                      f"{cap / 1024 / 1024:.0f} MB cap (T_MAX_SOURCE_MB); not run", flush=True)
                continue
            (harness.OUT / f"{name}.{suffix}").write_text(real_src, encoding="utf-8", newline="\n")
            (harness.OUT / f"{name}_twin.{suffix}").write_text(twin_src, encoding="utf-8", newline="\n")
            pending.append((bname, name, suffix, op))
            wits[name] = w
    n_cells = len(tasks) * len(BACKENDS)          # matrix size, independent of what lowered
    jobs = jobs_arg or max(1, min(n_cells, os.cpu_count() or 1))
    # Platform-selected: fork where it exists, spawn on Windows. The spawn
    # contract (module-level worker, picklable args, __main__ guard) lives
    # in verifiers.mp_context's docstring; the spawn branch is exercised on
    # Linux via T_MP_START=spawn against the full matrix.
    ctx = mp_context()
    with ProcessPoolExecutor(max_workers=jobs, mp_context=ctx) as ex:
        futs = {ex.submit(_run_cell, b, n, s, o, flake_n): (b, n, o) for b, n, s, o in pending}
        for fut in as_completed(futs):
            name, bname, op, cell = fut.result()
            rows[name][bname] = cell
            good = cell == (Outcome.VERIFIED, Outcome.REFUTED, True)
            all_ok &= good
            print(f"  {name} x {bname} [{op}]: real={cell[0]} twin={cell[1]}"
                  + ("" if good else "  <-- FINDING")
                  + f"   (twin witness: {harness.witness(wits.get(name))})", flush=True)
    return rows, wits, all_ok


def format_table(cols, rows, tasks, out_dir: Path, wits: dict | None = None) -> str:
    """The AGREEMENT.md text, exactly as main() has always built it: a UTC
    timestamp header, the cell-grammar line, the `| task | ... |` header and
    one row per task in `rows`'s iteration order, the kernels-present line,
    the Backends block, and the verdict-basis hash line naming the first
    task with both a .dfy and a .rs file under `out_dir`.

    Split out of main() 2026-09-10 (ROADMAP WS-19 move 1); byte-identical to
    the inline form it replaces (modulo the timestamp, which is
    `datetime.now` at call time either way), so grade.py's table.md is in
    AGREEMENT.md's exact format by construction, not by a second writer
    kept in sync by hand.

    `wits` (task name -> its measured twin witness, `lower_and_dispatch`'s
    own return value) is what tells a real-VERIFIED/twin-VERIFIED cell
    "decorative" from "unsound" (SPEC.md "The twins", 2026-09-11, ROADMAP
    13.3): omitted or missing an entry, such a cell still reads
    `verified / decorative` (harness.decorative_kind's own conservative
    default for a witness it cannot see), never `verified / verified`."""
    wits = wits or {}
    lines = [f"# t cross-kernel agreement, "
             f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%MZ')}",
             "",
             "Cell = real outcome / twin outcome. Agreement means "
             "`verified / refuted` in every present column. A real-VERIFIED, "
             "twin-VERIFIED cell reads `verified / decorative` (the spec "
             "cannot tell real and twin apart) or `verified / unsound` (the "
             "twin's own measured witness says a sound kernel must refute "
             "it, and this one did not); neither counts as agreement.",
             ""]
    header = "| task | " + " | ".join(b for b, _ in cols) + " |"
    lines += [header, "|" + "---|" * (len(cols) + 1)]
    col_names = [b for b, _ in cols]
    cell_rows: dict[str, dict[str, str]] = {}   # the same cell text, for blockers.render_section below
    for tname, cells in rows.items():
        row = [tname]
        for bname, _ in cols:
            c = cells.get(bname)
            if c is None:
                row.append("\u2014")
                continue
            kind = harness.decorative_kind(c[0], c[1], wits.get(tname))
            twin_text = kind if kind is not None else c[1]
            row.append(f"{c[0]} / {twin_text}" + ("" if c[2] else " (FLAKED)"))
        lines.append("| " + " | ".join(row) + " |")
        cell_rows[tname] = dict(zip(col_names, row[1:]))
    present_names = [b for b, v in cols if not v.startswith("ABSENT")]
    lines += ["", f"Kernels present: {len(present_names)} of {len(cols)} "
              f"({', '.join(present_names) if present_names else 'NONE'})"]
    lines += ["", "Backends:"] + [f"- {b}: {v}" for b, v in cols]
    # The example hashes name the first task that has both files, which is
    # abs on the committed corpus (so the default table is unchanged).
    ex = next((t for t in tasks if (out_dir / f"{harness.load(t)['name']}.dfy").exists()
               and (out_dir / f"{harness.load(t)['name']}.rs").exists()), None)
    if ex is not None:
        exn = harness.load(ex)["name"]
        lines += ["", f"Verdict basis: every source file hashed; e.g. "
                  f"`{exn}.dfy` {sha256_file(out_dir / f'{exn}.dfy')[:16]}…, "
                  f"`{exn}.rs` {sha256_file(out_dir / f'{exn}.rs')[:16]}…"]
    else:
        lines += ["", "Verdict basis: every source file hashed."]
    # ROADMAP WS-19 move 4: the sole-blocker count, over the cell text just
    # built above, no second parse of the table this function is writing.
    lines += ["", blockers.render_section(col_names, cell_rows).rstrip("\n")]
    return "\n".join(lines) + "\n"


def main() -> int:
    # Mutual exclusion is the lock file taken in __main__ (verifiers.
    # acquire_run_lock), on every platform. A /proc scan used to sit here
    # as an extra Linux-only check, matching any process whose argv held
    # "run_par.py"; it refused against its own launcher,
    # `timeout 600 python3 run_par.py` and nohup and sh -c, because the argv
    # carries the script name too (measured 2026-09-02 inside a tup guest,
    # exit 2, zero cells run). The lock already answers the question the
    # scan was asking, so the scan is gone.
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=None,
                    help="cells in flight; each cell makes six concurrent kernel calls")
    # The three paths below default to the committed layout, so a bare run
    # is byte-identical to before; a sweep over another corpus (ROADMAP 12.5,
    # the lifted DafnyBench tasks, 2026-09-06) passes all three so it never
    # touches t/tasks, t/out or t/AGREEMENT.md.
    ap.add_argument("--tasks", type=Path, default=HERE / "tasks",
                    help="directory of task .t (or, unconverted, .json) "
                         "files (default t/tasks)")
    ap.add_argument("--out", type=Path, default=HERE / "out",
                    help="directory for lowered sources and kernel logs (default t/out)")
    ap.add_argument("--table", type=Path, default=HERE / "AGREEMENT.md",
                    help="where the agreement table is written (default t/AGREEMENT.md)")
    ap.add_argument("--kernels", default="",
                    help="comma-separated subset of the seven kernels to grade "
                         "(default all); the table shows only these columns")
    args = ap.parse_args()
    jobs_arg = args.jobs
    harness.OUT = args.out
    harness.OUT.mkdir(parents=True, exist_ok=True)
    tasks = tasks_io.load_dir(args.tasks)
    # Rows are keyed by the task's own name, which is what every cell and
    # every output file uses; on the committed corpus the file stem is the
    # same string, on a lifted corpus it is not (Clover_abs.Abs.json holds
    # the task named clover_abs__abs, measured 2026-09-06). lower_and_dispatch
    # builds the rows skeleton itself, from the same `tasks` list.
    cols, present = probe_backends()
    if args.kernels:
        keep = {k.strip() for k in args.kernels.split(",") if k.strip()}
        cols = [(b, v) for b, v in cols if b in keep]
        present = [p for p in present if p[0] in keep]
    rows, wits, all_ok = lower_and_dispatch(tasks, present, jobs_arg)
    present_names = [b for b, v in cols if not v.startswith("ABSENT")]
    MIN_KERNELS = int(os.environ.get("T_MIN_KERNELS", "2"))
    # Refuse BEFORE writing; see run_all.py for the measurement behind it.
    if len(present_names) < MIN_KERNELS:
        print(f"\nREFUSED: {len(present_names)} kernel(s) available, "
              f"{MIN_KERNELS} required. Agreement across fewer than two "
              f"kernels is not agreement; it is one opinion, or none. "
              f"AGREEMENT.md not written.")
        for b, v in cols:
            if v.startswith("ABSENT"):
                print(f"  {b}: {v}")
        return 2
    if not tasks:
        print("\nREFUSED: no tasks in t/tasks/, nothing was verified. "
              "AGREEMENT.md not written.")
        return 2

    text = format_table(cols, rows, tasks, harness.OUT, wits)
    args.table.write_text(text, encoding="utf-8", newline="\n")
    print(f"\n{len(present_names)} kernels, {len(tasks)} tasks: "
          f"{'FULL AGREEMENT' if all_ok else 'DISAGREEMENT, a finding, see ' + str(args.table)}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    from verifiers import acquire_run_lock
    # Lock the out directory the run will write, which is t/out unless
    # --out says otherwise (a sweep into its own directory must not be
    # refused by, or refuse, a table run on the committed tasks).
    _pre = argparse.ArgumentParser(add_help=False)
    _pre.add_argument("--out", type=Path, default=HERE / "out")
    _lock = acquire_run_lock(_pre.parse_known_args()[0].out)
    if not callable(_lock):
        print(f"REFUSED: {_lock}")
        raise SystemExit(2)
    try:
        _code = main()
    finally:
        _lock()
    raise SystemExit(_code)
