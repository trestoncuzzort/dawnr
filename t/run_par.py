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

THE VERDICT CACHE (2026-09-19, ROADMAP 15.1 extended from the library to
this driver). t/cache.py and t/tlib.py already spent no kernel run on an
unchanged task in an editor; this driver spent a full run on every cell of
every re-grade. It now reads the same cache, one entry per SIDE (the real
source and the twin source are separate keys, exactly as tlib.py keys
them), with the same discipline, unrelaxed:

  * a side is written only after a COMPLETED n-of-3 flake agreement, so
    nothing provisional is ever cached and a cache hit is never
    provisional. A cell with one flaked side still caches the side that
    agreed, and caches nothing for the side that did not;
  * the key is the lowered source's bytes, the kernel, the kernel's own
    version string, and the budget -- and, because this driver runs while
    t/verifiers/* is being edited, an ADAPTER FINGERPRINT as well: the
    sha256 of verifiers/<kernel>.py, verifiers/__init__.py and
    verifiers/discover.py, plus the flake n. The adapter decides VERIFIED
    against VACUOUS from the same kernel output and holds the default
    budget constant the driver never passes, so an edited adapter must
    mean a fresh key, not a stale hit (t/cache.py's `extra`);
  * TIMEOUT and TOOL_ERROR are never written. A timeout is a statement
    about this machine under this load at this moment (the wall backstops
    fire under --jobs pressure: the 96-prover regime above flaked nine
    cells on them), and TOOL_ERROR is "never evidence of anything" by the
    Outcome vocabulary's own words. Neither is a property of the source
    the key can stand for, so both are re-run every time.

--no-cache turns it off, and IS the default for a run that writes the
committed t/AGREEMENT.md: that matrix is always produced by real kernel
runs. Asking for --cache on the committed table is refused, not warned
about, so the rule holds without anyone remembering it. Everywhere else
(a sweep with its own --table, a re-grade into /tmp) the cache is on by
default; --no-cache is how you ask for the second opinion.

A cached table and a fresh one are the same bytes: nothing about the cache
reaches AGREEMENT.md. The run's SUMMARY LINE is where the cache shows, and
it always names the hits and the kernel runs, so a reader can tell a
cached table from a fresh one without reading this file.

THE COMMITTED-TABLE GUARD (2026-09-25, r12 blocker A3). A run that writes
t/AGREEMENT.md must grade exactly the committed t/tasks/*.t, unchanged, in
all seven kernels. A strict subset of tasks or of kernels is refused unless
--allow-subset-table says the overwrite is meant; a changed or foreign task
file is refused outright (a table of other tasks belongs under --table).
Commit a3c6f955 is the reason: `--tasks t/nested --jobs 7` with no --table
replaced the 35-row matrix with one row, and the corpus builder that reads
the table lost every committed task without a word. Refused before any
kernel is probed or run; see committed_task_refusal.

THE SPARK JOB CAP (2026-09-25, r12 blocker A8). With more than one cell in
flight, every pool worker gets T_SPARK_JOBS=1 unless the parent set the
variable, so gnatprove runs one prover per call and a sweep is 6 x jobs
provers rather than 48 x jobs. About 20 jobs is the limit on 120 threads
(6 x 20 = 120); grade_lab.sh passes the variable itself and is unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import cache                        # noqa: E402  (the verdict cache, ROADMAP 15.1)
import harness                      # noqa: E402
import tasks_io                     # noqa: E402
import verifiers                    # noqa: E402  (verifiers.LAUNCHES, the launch counter)
from verifiers import Outcome, cell_pair, flake_check, sha256_file, mp_context   # noqa: E402
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

# ----------------------------------------------------------- verdict cache --
# The committed matrix. A run writing THIS file never reads the cache; see
# the module docstring, and the refusal in main().
COMMITTED_TABLE = HERE / "AGREEMENT.md"
# The committed corpus the matrix stands for: every t/tasks/*.t, all seven
# kernels. A run that writes COMMITTED_TABLE must cover exactly these
# (committed_task_refusal, committed_kernel_refusal below).
COMMITTED_TASKS = HERE / "tasks"
ALL_KERNELS = tuple(b for b, _lmod, _suffix in BACKENDS)


def _is_committed(table: Path) -> bool:
    """Resolved-path comparison, so `AGREEMENT.md`, `./AGREEMENT.md`,
    `t/AGREEMENT.md` and a symlink to it are one answer (cache_decision
    has always compared this way)."""
    try:
        return Path(table).resolve() == Path(COMMITTED_TABLE).resolve()
    except OSError:
        return Path(table) == Path(COMMITTED_TABLE)


def _digests(paths) -> dict[str, str]:
    """file name -> sha256 of the bytes, for a list of task files."""
    out = {}
    for p in paths:
        p = Path(p)
        out[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


# ---------------------------------------------- the committed-table guard --
# 2026-09-20, commit a3c6f955: `python3 t/run_par.py --tasks t/nested --jobs 7`
# (the reproduction command in t/nested/README.md) had no --table, so this
# driver wrote its default, the committed t/AGREEMENT.md, and the 35-row
# matrix became a one-row table. The corpus builder reads that table
# (loop_locallm.clean_rows needs all seven cells `verified / refuted`), so
# the next corpus silently lost every committed task (r12 blocker A3).
#
# Jest solves the same class of accident -- a filtered run must not prune
# the committed results file -- by marking the snapshots of the tests it
# did not execute as checked, so `removeUncheckedKeys` deletes nothing a
# partial run did not see (jest-circus, legacy-code-todo-rewrite/
# jestAdapter.ts, _addSnapshotData; fetched 2026-09-25 from
# raw.githubusercontent.com/jestjs/jest/main/packages/jest-circus/src/
# legacy-code-todo-rewrite/jestAdapter.ts). Its file is keyed per test, so
# a partial run merges into it. AGREEMENT.md is not: one timestamp, one
# Backends block, one verdict-basis line and one sole-blocker section
# describe the whole run, and rows from two runs under one header would
# claim a single measurement that never happened. So the committed table
# is refused rather than merged: a strict subset needs
# --allow-subset-table, and changed bytes or a foreign task have no
# override at all (write elsewhere with --table). The refusal happens
# before any kernel is probed or run.
def committed_task_refusal(table: Path, tasks, allow_subset: bool) -> str | None:
    """None when `tasks` may be written to `table`, else the refusal text.
    Only the committed table is guarded; any other path is always fine."""
    if not _is_committed(table):
        return None
    committed = _digests(sorted(Path(COMMITTED_TASKS).glob("*.t")))
    run = _digests(tasks)
    foreign = sorted(n for n in run if n not in committed)
    changed = sorted(n for n in run if n in committed and run[n] != committed[n])
    if foreign or changed:
        what = []
        if changed:
            what.append(f"{len(changed)} task file(s) differ from t/tasks: {', '.join(changed[:5])}"
                        + (" ..." if len(changed) > 5 else ""))
        if foreign:
            what.append(f"{len(foreign)} task file(s) are not committed: {', '.join(foreign[:5])}"
                        + (" ..." if len(foreign) > 5 else ""))
        return ("REFUSED: t/AGREEMENT.md is the matrix of the committed tasks, and this run's "
                + "; ".join(what) + ". A table of other tasks belongs elsewhere: pass "
                "--table <file>. Nothing was written.")
    missing = sorted(n for n in committed if n not in run)
    if missing and not allow_subset:
        return (f"REFUSED: this run grades {len(run)} of {len(committed)} committed tasks, a "
                f"strict subset; writing t/AGREEMENT.md would delete the other {len(missing)} "
                f"row(s) (a3c6f955 did exactly this with `--tasks t/nested` and no --table). "
                f"Pass --table <file> for a table of this subset, or --allow-subset-table to "
                f"overwrite the committed table on purpose. Nothing was written.")
    return None


def committed_kernel_refusal(table: Path, cols, allow_subset: bool) -> str | None:
    """None when the columns `cols` ([(kernel, version_or_ABSENT), ...],
    after any --kernels filter) may be written to `table`, else the refusal.
    The committed table needs all seven present: a --kernels subset or an
    ABSENT kernel would leave columns out, and clean_rows reads a missing
    column as "no agreement" for every task."""
    if not _is_committed(table) or allow_subset:
        return None
    named = {b for b, _v in cols}
    absent = sorted(b for b, v in cols if str(v).startswith("ABSENT"))
    left_out = sorted(b for b in ALL_KERNELS if b not in named)
    if not absent and not left_out:
        return None
    what = []
    if left_out:
        what.append(f"kernel column(s) left out by --kernels: {', '.join(left_out)}")
    if absent:
        what.append(f"kernel(s) absent on this machine: {', '.join(absent)}")
    return ("REFUSED: t/AGREEMENT.md needs all seven kernel columns, and this run has "
            + "; ".join(what) + ". Pass --table <file> for a partial table, or "
            "--allow-subset-table to overwrite the committed table on purpose. "
            "Nothing was written.")


# ------------------------------------------------------ the SPARK job cap --
# spark.py runs gnatprove with -j (JOBS_CAP 8), measured verdict-neutral and
# a pure scheduling knob there. A cell is already six concurrent kernel
# calls (verifiers.cell_pair), so a sweep of N cells is N x 6 x 8 prover
# processes: on 2026-09-20 a 24-job sweep reached a load of 351 on 120
# threads, and the wall backstops then fire on cells that would prove alone
# (r12 blocker A8). joblib caps the inner thread count of every pool worker
# through the worker's environment, "unless the variable is already present
# in the parent process environment" (joblib/_parallel_backends.py,
# _prepare_worker_env; fetched 2026-09-25 from raw.githubusercontent.com/
# joblib/joblib/main/joblib/_parallel_backends.py). Same shape here: the
# workers get T_SPARK_JOBS=1 (spark.py's own comment names 1 as the setting
# for a parallel sweep, and cpu // (6 x jobs) is 1 for any sweep of ten or
# more jobs on 120 threads); a parent that set the variable is obeyed; the
# parent's own environment is never touched.
def spark_jobs_env(cells_in_flight: int, environ=None) -> dict[str, str]:
    """The environment the pool workers get on top of the parent's: {} when
    one cell runs at a time or T_SPARK_JOBS is already set (blank counts as
    unset, which is how spark.py reads it), else T_SPARK_JOBS=1."""
    environ = os.environ if environ is None else environ
    if cells_in_flight > 1 and not str(environ.get("T_SPARK_JOBS", "")).strip():
        return {"T_SPARK_JOBS": "1"}
    return {}


def _worker_env(env: dict) -> None:
    """ProcessPoolExecutor initializer: runs once in each worker, so the
    variables land in the workers and nowhere else. Module-level, so it
    pickles under spawn. conformance.py's pool passes the same pair."""
    os.environ.update(env)

# What a cache entry is allowed to stand for. VERIFIED, REFUTED, VACUOUS,
# MALFORMED and UNPROVED are functions of the source, the kernel, the
# budget and the adapter -- all four in the key. TIMEOUT and TOOL_ERROR are
# not: a timeout says this machine, under this load, ran out of wall or
# steps (the wall backstops fire under --jobs pressure), and TOOL_ERROR is
# never evidence of anything. Remembering either would be remembering the
# machine, not the program, so neither is ever written and both are re-run
# on every pass.
CACHEABLE = frozenset({Outcome.VERIFIED, Outcome.REFUTED, Outcome.VACUOUS,
                       Outcome.MALFORMED, Outcome.UNPROVED})

_ADAPTER_FP: dict[str, str] = {}


def adapter_fingerprint(bname: str) -> str:
    """sha256 of the code that turns this kernel's output into an Outcome:
    verifiers/<bname>.py, plus verifiers/__init__.py (the Outcome
    vocabulary, flake_check, run_tree and the wall-backstop machinery) and
    verifiers/discover.py (which binary gets run at all). Read once per
    process, from disk, in the parent.

    Why it is in the key and the kernel's --version string is not enough:
    the adapter holds each backend's DEFAULT_RLIMIT/DEFAULT_STEPS -- the
    budget this driver never passes and therefore never varies -- and it
    holds the ban regexes and certificate checks that separate VERIFIED
    from VACUOUS. Edit t/verifiers/dafny.py and the same dafny, on the same
    bytes, can honestly return a different Outcome. An unfingerprinted key
    would hand back the old one."""
    if bname not in _ADAPTER_FP:
        h = hashlib.sha256()
        for name in (f"{bname}.py", "__init__.py", "discover.py"):
            p = HERE / "verifiers" / name
            try:
                h.update(p.read_bytes())
            except OSError as e:                    # noqa: BLE001
                # Unreadable adapter: fold the reason in, so the key is
                # distinct from any key built from a file that was read.
                h.update(f"UNREADABLE {name} {e}".encode("utf-8"))
            h.update(b"\0")
        _ADAPTER_FP[bname] = h.hexdigest()
    return _ADAPTER_FP[bname]


def _cached_outcome(bname: str, key: str, cache_dir) -> str | None:
    """The cached outcome for one side, or None for a miss. An entry whose
    outcome is not in CACHEABLE is read as a MISS, not as a verdict: this
    driver never writes one, so such a file came from somewhere else, and
    "somewhere else" is not evidence."""
    hit = cache.read(bname, key, cache_dir)
    if not isinstance(hit, dict):
        return None
    outcome = hit.get("outcome")
    return outcome if outcome in CACHEABLE else None


def _record_sides(bname: str, task_name: str, sides: dict, keys, versions: dict,
                  cache_dir, flake_n: int, counts: dict) -> int:
    """Count what this cell ran, write back the sides that may be written,
    and return how many of its two sides came from the cache.

    The write rule, in one place: a side is written only if it RAN (a cache
    hit is not re-written), only if its n-of-3 flake_check AGREED, and only
    if its outcome is one the key can stand for. A flaked side leaves no
    entry, so the next run asks the kernel again instead of trusting a
    verdict the kernel itself did not repeat."""
    n_hit = 0
    for i, side in enumerate(("real", "twin")):
        outcome, agreed, was_cached = sides[side]
        if was_cached:
            n_hit += 1
            counts["cached_sides"] += 1
            continue
        counts["ran_sides"] += 1
        counts["runs"] += flake_n
        if cache_dir is None or keys is None or not agreed:
            continue
        if outcome not in CACHEABLE:
            counts["unwritable"] += 1
            continue
        try:
            cache.write(bname, keys[i],
                        {"outcome": outcome, "backend_version": versions[bname]},
                        cache_dir)
        except OSError as e:                        # noqa: BLE001
            # A cache that cannot be written is a slower next run, never a
            # failed this one: the verdict in hand is unaffected.
            print(f"  (cache write failed for {task_name} x {bname} {side}: {e})",
                  flush=True)
            continue
        counts["written"] += 1
    return n_hit


def cache_key(source: str, bname: str, version: str, flake_n: int) -> str:
    """This driver's key for one lowered source. The budget component is
    None, which is what run_par passes every backend's verify() -- i.e.
    each adapter's own default, whose value is inside the fingerprint."""
    return cache.key_for(source, bname, version, None,
                         extra=f"adapter={adapter_fingerprint(bname)};"
                               f"flake={flake_n}")


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


def _run_cell(bname: str, task_name: str, suffix: str, op: str, flake_n: int = 3,
              cached: tuple | None = None):
    # Re-imported per call: correct under spawn (fresh interpreter, no
    # inherited module object); a sys.modules hit under fork, used below.
    # flake_n defaults to cell_pair's own default (3, everyone); grade.py's
    # --flake is the only caller that ever passes another value, so a bare
    # `python3 run_par.py` dispatch is unchanged.
    #
    # `cached` is (real_outcome_or_None, twin_outcome_or_None), the sides
    # the PARENT already found in the verdict cache -- a pair of strings or
    # Nones, so it pickles under spawn like every other argument here. None
    # (the default, and what every caller outside this file passes) is the
    # uncached cell, byte-identical to what this function has always done:
    # one cell_pair, 2n kernel calls. A cell whose BOTH sides are cached is
    # never submitted at all, so it costs no worker and no dispatch.
    backend = importlib.import_module(f"verifiers.{bname}")
    real = harness.OUT / f"{task_name}.{suffix}"
    twin = harness.OUT / f"{task_name}_twin.{suffix}"
    c_real, c_twin = cached if cached is not None else (None, None)
    _watch_event(ev="start", task=task_name, kernel=bname, op=op,
                 cached=[c_real is not None, c_twin is not None])
    launches0 = verifiers.LAUNCHES
    try:
        if c_real is None and c_twin is None:
            (r_real, a1), (r_twin, a2) = cell_pair(backend.verify, real, twin, flake_n)
            o_real, o_twin = r_real.outcome, r_twin.outcome
        elif c_real is None:
            # Only the real side is unknown; a cached twin is a completed
            # agreement by construction, so its agreed flag is True.
            r_real, a1 = flake_check(backend.verify, real, flake_n)
            o_real, o_twin, a2 = r_real.outcome, c_twin, True
        else:
            r_twin, a2 = flake_check(backend.verify, twin, flake_n)
            o_real, a1, o_twin = c_real, True, r_twin.outcome
    except BaseException as e:
        _watch_event(ev="end", task=task_name, kernel=bname, real="error",
                     twin=type(e).__name__, agree=False)
        raise
    _watch_event(ev="end", task=task_name, kernel=bname, real=str(o_real),
                 twin=str(o_twin), agree=bool(a1 and a2))
    # The two per-side agreement flags travel separately from the cell's
    # own (a1 and a2): the caller caches a side that agreed even when its
    # sibling flaked, and caches neither of a cell it cannot write.
    return (task_name, bname, op, (o_real, o_twin, a1 and a2),
            {"real": (o_real, bool(a1), c_real is not None),
             "twin": (o_twin, bool(a2), c_twin is not None)},
            verifiers.LAUNCHES - launches0)


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


def lower_and_dispatch(tasks: list[Path], present, jobs_arg, flake_n: int = 3,
                       versions: dict | None = None, cache_dir=None,
                       stats: dict | None = None):
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
    identical to before; grade.py's --flake is the only caller that does.

    THE CACHE (2026-09-19) is off unless `cache_dir` is given, so every
    caller that does not ask for it -- grade.py, cli.py, test_twin_rule.py,
    and this file's own --no-cache path -- runs exactly the kernels it ran
    before. With a cache_dir, a side (real source, or twin source) whose
    key is present costs no kernel run, a cell whose BOTH sides are present
    is never even submitted to the pool, and a side that runs is written
    back only on a completed n-of-3 agreement with a cacheable outcome
    (module docstring: never TIMEOUT, never TOOL_ERROR). `versions` maps
    kernel -> the version string probe_backends() already read in this
    process; a kernel missing from it is never cached, because a key
    without the kernel's own version is a key that cannot be invalidated
    by a toolchain upgrade. `stats`, when a dict is passed, is filled with
    the counts main() prints in its summary line -- an out-parameter rather
    than a fourth return value, so every existing three-tuple call site is
    untouched."""
    rows = {harness.load(t)["name"]: {} for t in tasks}
    all_ok = True
    versions = versions or {}
    counts = {"cells": 0, "cached_cells": 0, "cached_sides": 0, "ran_sides": 0,
              "runs": 0, "measured_runs": 0, "written": 0, "unwritable": 0}
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
            wits[name] = w
            # The cache lookup sits HERE, after the lowering and before the
            # dispatch, because the lowered bytes just written are the key:
            # the cache answers for a source, never for a task name. The
            # lowering itself still runs on every pass -- it is Python over
            # an interpreted witness search, not a kernel -- so a fully
            # cached run still writes out/*.dfy and the table's verdict-basis
            # hashes still name files this run produced.
            keys = hit_real = hit_twin = None
            if cache_dir is not None and bname in versions:
                keys = (cache_key(real_src, bname, versions[bname], flake_n),
                        cache_key(twin_src, bname, versions[bname], flake_n))
                hit_real, hit_twin = (_cached_outcome(bname, k, cache_dir)
                                      for k in keys)
            if hit_real is not None and hit_twin is not None:
                # No kernel, no worker, no dispatch: both sides of this cell
                # were agreed by a previous run on these exact bytes.
                cell = (hit_real, hit_twin, True)
                rows[name][bname] = cell
                good = cell == (Outcome.VERIFIED, Outcome.REFUTED, True)
                all_ok &= good
                counts["cells"] += 1
                counts["cached_cells"] += 1
                counts["cached_sides"] += 2
                print(f"  {name} x {bname} [{op}]: real={cell[0]} twin={cell[1]}"
                      + ("" if good else "  <-- FINDING")
                      + f"   (cached; twin witness: {harness.witness(w)})", flush=True)
                continue
            pending.append((bname, name, suffix, op, (hit_real, hit_twin), keys))
    n_cells = len(tasks) * len(BACKENDS)          # matrix size, independent of what lowered
    jobs = jobs_arg or max(1, min(n_cells, os.cpu_count() or 1))
    # Platform-selected: fork where it exists, spawn on Windows. The spawn
    # contract (module-level worker, picklable args, __main__ guard) lives
    # in verifiers.mp_context's docstring; the spawn branch is exercised on
    # Linux via T_MP_START=spawn against the full matrix.
    ctx = mp_context()
    keymap = {(b, n): k for b, n, _s, _o, _c, k in pending}
    # A8: the cells actually in flight decide the cap, so a two-cell run at
    # --jobs 64 and a sixty-cell run at --jobs 2 are both read correctly.
    worker_env = spark_jobs_env(min(jobs, len(pending)))
    if worker_env:
        print(f"  {min(jobs, len(pending))} cells in flight x 6 kernel calls each: workers get "
              f"T_SPARK_JOBS=1 (gnatprove one prover per call; set T_SPARK_JOBS to override)",
              flush=True)
    with ProcessPoolExecutor(max_workers=jobs, mp_context=ctx,
                             initializer=_worker_env, initargs=(worker_env,)) as ex:
        futs = {ex.submit(_run_cell, b, n, s, o, flake_n, c): (b, n, o)
                for b, n, s, o, c, _k in pending}
        for fut in as_completed(futs):
            name, bname, op, cell, sides, launched = fut.result()
            rows[name][bname] = cell
            good = cell == (Outcome.VERIFIED, Outcome.REFUTED, True)
            all_ok &= good
            counts["cells"] += 1
            counts["measured_runs"] += launched
            n_hit = _record_sides(bname, name, sides, keymap.get((bname, name)),
                                  versions, cache_dir, flake_n, counts)
            print(f"  {name} x {bname} [{op}]: real={cell[0]} twin={cell[1]}"
                  + ("" if good else "  <-- FINDING")
                  + ("" if not n_hit else f"   ({n_hit} side cached)")
                  + f"   (twin witness: {harness.witness(wits.get(name))})", flush=True)
    if stats is not None:
        stats.update(counts)
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


def cache_decision(table: Path, flag, cache_dir: Path):
    """(cache_dir_or_None, refusal_or_None) for one run's --cache/--no-cache
    and --table. One function so the rule is stated once and can be tested
    without running a kernel (t/test_run_par_cache.py):

      * --cache on the committed t/AGREEMENT.md is REFUSED. That table is
        the claim the project makes about seven kernels; it is produced by
        running them.
      * no flag, committed table -> off. The default IS --no-cache there.
      * no flag, any other table -> on. A sweep, a re-grade into /tmp, a
        recheck after a lowering fix: these re-run constantly and are
        exactly what the cache exists for.
      * --no-cache -> off, anywhere.

    The comparison is on resolved paths, so `AGREEMENT.md`, `./AGREEMENT.md`,
    `t/AGREEMENT.md` and a symlink to it are one answer."""
    try:
        committed = table.resolve() == COMMITTED_TABLE.resolve()
    except OSError:
        committed = table == COMMITTED_TABLE
    if committed and flag is True:
        return None, ("REFUSED: --cache writes the committed t/AGREEMENT.md "
                      "from remembered verdicts. That table is the claim, and "
                      "the claim is produced by real kernel runs. Drop "
                      "--cache, or write somewhere else with --table.")
    use = (not committed) if flag is None else bool(flag)
    return (cache_dir if use else None), None


def cache_summary(stats: dict, cache_dir) -> str:
    """The cache clause of the run's summary line. Printed on EVERY run,
    including a --no-cache one, which says so in those words: a reader who
    sees a table and a summary must be able to tell whether kernels
    produced it without reading this file or the cache directory. Nothing
    here reaches AGREEMENT.md -- a cached table and a fresh one are the
    same bytes, which is the property the run must not hide."""
    cells = stats.get("cells", 0)
    runs = stats.get("runs", 0)
    if cache_dir is None:
        return (f"no cache (--no-cache): {cells} cells, {runs} kernel runs, "
                f"every verdict measured here")
    parts = [f"cache on ({cache_dir})",
             f"{stats.get('cached_cells', 0)} of {cells} cells whole from cache",
             f"{stats.get('cached_sides', 0)} of {2 * cells} sides",
             f"{runs} kernel runs",
             f"{stats.get('written', 0)} entries written"]
    if stats.get("unwritable"):
        parts.append(f"{stats['unwritable']} side(s) too noisy to cache "
                     f"(timeout or tool error)")
    measured = stats.get("measured_runs", 0)
    if measured != runs:
        # The workers' own flake_check counter disagreeing with the count
        # derived here is a finding about this file, not a rounding note.
        parts.append(f"WORKERS COUNTED {measured} <-- does not match, a finding")
    return "; ".join(parts)


def main(argv=None) -> int:
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
    # touches t/tasks, t/out or t/AGREEMENT.md. --tasks and --table resolve
    # to COMMITTED_TASKS / COMMITTED_TABLE at call time, not at import, so
    # t/test_run_par_guards.py can point both at a sandbox.
    ap.add_argument("--tasks", type=Path, default=None,
                    help="directory of task .t (or, unconverted, .json) "
                         "files (default t/tasks)")
    ap.add_argument("--out", type=Path, default=HERE / "out",
                    help="directory for lowered sources and kernel logs (default t/out)")
    ap.add_argument("--table", type=Path, default=None,
                    help="where the agreement table is written (default t/AGREEMENT.md)")
    ap.add_argument("--kernels", default="",
                    help="comma-separated subset of the seven kernels to grade "
                         "(default all); the table shows only these columns")
    ap.add_argument("--allow-subset-table", action="store_true",
                    help="overwrite the committed t/AGREEMENT.md on purpose from a "
                         "strict subset of t/tasks or of the seven kernels (it is "
                         "refused otherwise, since a3c6f955); changed or foreign "
                         "task files are never allowed there")
    # The verdict cache (module docstring). Default: ON for any other table,
    # OFF for the committed t/AGREEMENT.md, and asking for it there is
    # refused below rather than quietly honoured.
    ap.add_argument("--cache", dest="cache", action="store_true", default=None,
                    help="reuse cached verdicts for unchanged lowered sources "
                         "(default on, except when writing t/AGREEMENT.md)")
    ap.add_argument("--no-cache", dest="cache", action="store_false",
                    help="run every kernel on every cell; the default for a "
                         "run that writes the committed t/AGREEMENT.md")
    ap.add_argument("--cache-dir", type=Path, default=cache.DEFAULT_CACHE_DIR,
                    help="where cached verdicts live (default t/out/cache, "
                         "shared with t/tlib.py's editor cache; content-keyed, "
                         "so it is correct across --out directories)")
    args = ap.parse_args(argv)
    if args.tasks is None:
        args.tasks = Path(COMMITTED_TASKS)
    if args.table is None:
        args.table = Path(COMMITTED_TABLE)
    jobs_arg = args.jobs
    cache_dir, refusal = cache_decision(args.table, args.cache, args.cache_dir)
    if refusal:
        print(refusal)
        return 2
    tasks = tasks_io.load_dir(args.tasks)
    # A3: the committed table is refused for a partial, changed or foreign
    # task set BEFORE anything is created, probed or run.
    refusal = committed_task_refusal(args.table, tasks, args.allow_subset_table)
    if refusal:
        print(refusal)
        return 2
    harness.OUT = args.out
    harness.OUT.mkdir(parents=True, exist_ok=True)
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
    # A3, the column half: a --kernels subset or an ABSENT kernel would write
    # the committed table with a column missing. Refused before any kernel runs.
    refusal = committed_kernel_refusal(args.table, cols, args.allow_subset_table)
    if refusal:
        print(refusal)
        return 2
    stats: dict = {}
    rows, wits, all_ok = lower_and_dispatch(
        tasks, present, jobs_arg,
        versions={b: v for b, v in cols if not v.startswith("ABSENT")},
        cache_dir=cache_dir, stats=stats)
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
          f"{'FULL AGREEMENT' if all_ok else 'DISAGREEMENT, a finding, see ' + str(args.table)}"
          f"; {cache_summary(stats, cache_dir)}")
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
