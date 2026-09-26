#!/usr/bin/env python3
"""t/test_run_par_guards.py -- run_par refuses to write the committed table
from a partial, changed or foreign run (r12 blocker A3), and hands each pool
worker T_SPARK_JOBS=1 when cells run in parallel (A8). 2026-09-25.

A3. Commit a3c6f955 replaced the 35-task t/AGREEMENT.md with a one-row table:
`python3 t/run_par.py --tasks t/nested --jobs 7` (the reproduction command in
t/nested/README.md) had no --table, so run_par wrote its default, the
committed path. The corpus builder reads that table (loop_locallm.clean_rows
needs all seven cells `verified / refuted`), so the accident silently removed
every committed task from the next corpus. Jest keeps a filtered run from
pruning its snapshot file by marking the unexecuted tests' snapshots as
checked (packages/jest-circus/src/legacy-code-todo-rewrite/jestAdapter.ts,
_addSnapshotData); AGREEMENT.md carries run-wide fields (one timestamp, one
Backends block, one verdict basis), so it cannot be merged per row, and the
guard refuses instead:

  * a strict subset of t/tasks/*.t is refused unless --allow-subset-table;
  * a task whose bytes differ from the committed file, or a task that is not
    a committed file at all, is refused with no override (only --table
    elsewhere);
  * a missing kernel column (--kernels subset, or an ABSENT kernel) is
    refused unless --allow-subset-table;
  * every other table path is untouched by these rules.

A8. spark.py runs gnatprove with -j (JOBS_CAP 8), so a sweep at N cells is
N x 6 x 8 provers; on 2026-09-20 a 24-job sweep reached a load of 351 on
120 threads. joblib caps the inner thread count in each pool worker's
environment unless the parent set it (joblib/_parallel_backends.py,
_prepare_worker_env); run_par does the same with T_SPARK_JOBS=1 whenever
more than one cell is in flight. The parent's environment is untouched.

Standard library only; no kernel is run (the dispatch is faked). unittest.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness                                                # noqa: E402
import run_par                                                # noqa: E402
import verifiers                                              # noqa: E402

SENTINEL = "# sentinel table: must survive a refused run\n"
TASKS = sorted((HERE / "tasks").glob("*.t"))


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def fake_lower(task, body, witness=None):
    return "lowered\n"


class GuardSandbox:
    """A copy of the committed layout under a temp dir, with the probe and
    the dispatch faked, so main() runs to its table write without a kernel."""

    def __init__(self, absent: str | None = None):
        self.dir = Path(tempfile.mkdtemp(prefix="t-run-par-guards-"))
        self.tasks = self.dir / "tasks"
        self.tasks.mkdir()
        for p in TASKS:
            shutil.copy(p, self.tasks / p.name)
        self.table = self.dir / "AGREEMENT.md"
        self.table.write_text(SENTINEL, encoding="utf-8")
        self.out = self.dir / "out"
        self.absent = absent
        self.dispatched = []
        self._saved = (run_par.COMMITTED_TASKS, run_par.COMMITTED_TABLE,
                       run_par.probe_backends, run_par.lower_and_dispatch,
                       harness.OUT)

    def __enter__(self):
        run_par.COMMITTED_TASKS = self.tasks
        run_par.COMMITTED_TABLE = self.table
        run_par.probe_backends = self._probe
        run_par.lower_and_dispatch = self._dispatch
        return self

    def __exit__(self, *exc):
        (run_par.COMMITTED_TASKS, run_par.COMMITTED_TABLE, run_par.probe_backends,
         run_par.lower_and_dispatch, harness.OUT) = self._saved
        shutil.rmtree(self.dir, ignore_errors=True)
        return False

    def _probe(self):
        cols, present = [], []
        for bname, _lmod, suffix in run_par.BACKENDS:
            if bname == self.absent:
                cols.append((bname, "ABSENT: faked away"))
                continue
            cols.append((bname, "fake 1.0"))
            present.append((bname, fake_lower, suffix))
        return cols, present

    def _dispatch(self, tasks, present, jobs_arg, flake_n=3, versions=None,
                  cache_dir=None, stats=None):
        self.dispatched.append([Path(t).name for t in tasks])
        rows = {harness.load(t)["name"]: {b: ("verified", "refuted", True)
                                          for b, _l, _s in present}
                for t in tasks}
        if stats is not None:
            stats.update(cells=len(rows) * len(present), runs=0)
        return rows, {}, True

    def subset(self, n: int = 1) -> Path:
        d = self.dir / "subset"
        d.mkdir(exist_ok=True)
        for p in TASKS[:n]:
            shutil.copy(p, d / p.name)
        return d

    def run(self, *argv: str) -> tuple[int, str]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = run_par.main([*argv, "--out", str(self.out)])
        return rc, buf.getvalue()


class CommittedTableGuardTests(unittest.TestCase):
    def test_a_strict_subset_leaves_the_committed_table_byte_identical(self):
        with GuardSandbox() as sb:
            rc, out = sb.run("--tasks", str(sb.subset(1)), "--jobs", "7")
            self.assertEqual(rc, 2, out)
            self.assertIn("strict subset", out)
            self.assertIn("a3c6f955", out)
            self.assertEqual(sb.table.read_text(encoding="utf-8"), SENTINEL)
            self.assertEqual(sb.dispatched, [], "refused before any dispatch")

    def test_the_full_committed_set_writes_the_table(self):
        with GuardSandbox() as sb:
            rc, out = sb.run("--tasks", str(sb.tasks))
            self.assertEqual(rc, 0, out)
            self.assertTrue(sb.table.read_text(encoding="utf-8")
                            .startswith("# t cross-kernel agreement"))
            self.assertEqual(len(sb.dispatched), 1)

    def test_a_subset_with_its_own_table_is_written_there_only(self):
        with GuardSandbox() as sb:
            other = sb.dir / "other.md"
            rc, out = sb.run("--tasks", str(sb.subset(2)), "--table", str(other))
            self.assertEqual(rc, 0, out)
            self.assertTrue(other.exists())
            self.assertEqual(sb.table.read_text(encoding="utf-8"), SENTINEL)

    def test_allow_subset_table_writes_the_committed_table_from_a_subset(self):
        with GuardSandbox() as sb:
            rc, out = sb.run("--tasks", str(sb.subset(3)), "--allow-subset-table")
            self.assertEqual(rc, 0, out)
            self.assertNotEqual(sb.table.read_text(encoding="utf-8"), SENTINEL)

    def test_changed_bytes_are_refused_even_with_the_flag(self):
        with GuardSandbox() as sb:
            d = sb.dir / "changed"
            d.mkdir()
            for p in TASKS:
                shutil.copy(p, d / p.name)
            victim = d / TASKS[0].name
            victim.write_text(victim.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            rc, out = sb.run("--tasks", str(d), "--allow-subset-table")
            self.assertEqual(rc, 2, out)
            self.assertIn(TASKS[0].name, out)
            self.assertIn("differ", out)
            self.assertEqual(sb.table.read_text(encoding="utf-8"), SENTINEL)

    def test_a_foreign_task_is_refused_even_with_the_flag(self):
        with GuardSandbox() as sb:
            d = sb.dir / "foreign"
            d.mkdir()
            for p in TASKS:
                shutil.copy(p, d / p.name)
            shutil.copy(TASKS[0], d / "zz_not_committed.t")
            rc, out = sb.run("--tasks", str(d), "--allow-subset-table")
            self.assertEqual(rc, 2, out)
            self.assertIn("zz_not_committed.t", out)
            self.assertEqual(sb.table.read_text(encoding="utf-8"), SENTINEL)

    def test_a_kernel_subset_is_refused_before_any_dispatch(self):
        with GuardSandbox() as sb:
            rc, out = sb.run("--tasks", str(sb.tasks), "--kernels", "lean")
            self.assertEqual(rc, 2, out)
            self.assertIn("kernel", out)
            self.assertEqual(sb.dispatched, [])
            self.assertEqual(sb.table.read_text(encoding="utf-8"), SENTINEL)

    def test_an_absent_kernel_is_refused_for_the_committed_table(self):
        with GuardSandbox(absent="fstar") as sb:
            rc, out = sb.run("--tasks", str(sb.tasks))
            self.assertEqual(rc, 2, out)
            self.assertIn("fstar", out)
            self.assertEqual(sb.dispatched, [])
            self.assertEqual(sb.table.read_text(encoding="utf-8"), SENTINEL)
            # The same partial install writes its own table freely.
            rc, out = sb.run("--tasks", str(sb.tasks), "--table", str(sb.dir / "mine.md"))
            self.assertEqual(rc, 0, out)

    def test_the_refusal_functions_answer_without_running_main(self):
        with GuardSandbox() as sb:
            self.assertIsNone(run_par.committed_task_refusal(sb.table, TASKS[:0] + list(sb.tasks.glob("*.t")), False))
            self.assertIn("strict subset", run_par.committed_task_refusal(sb.table, [sb.tasks / TASKS[0].name], False))
            self.assertIsNone(run_par.committed_task_refusal(sb.table, [sb.tasks / TASKS[0].name], True))
            self.assertIsNone(run_par.committed_task_refusal(sb.dir / "other.md", [sb.tasks / TASKS[0].name], False))
            cols = [(b, "v") for b in run_par.ALL_KERNELS]
            self.assertIsNone(run_par.committed_kernel_refusal(sb.table, cols, False))
            self.assertIn("lean", run_par.committed_kernel_refusal(sb.table, cols[:4], False))
            self.assertIsNone(run_par.committed_kernel_refusal(sb.table, cols[:4], True))
            self.assertIsNone(run_par.committed_kernel_refusal(sb.dir / "other.md", cols[:1], False))

    def test_the_accident_replayed_as_a_subprocess_is_refused(self):
        """The exact command behind a3c6f955, against the real t/tasks and
        the real t/AGREEMENT.md, which must come out byte-identical."""
        before = sha(HERE / "AGREEMENT.md")
        with tempfile.TemporaryDirectory() as out:
            p = subprocess.run([sys.executable, str(HERE / "run_par.py"), "--tasks",
                                str(HERE / "nested"), "--jobs", "7", "--out", out],
                               capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("strict subset", p.stdout)
        self.assertEqual(sha(HERE / "AGREEMENT.md"), before)


class SparkJobsEnvTests(unittest.TestCase):
    def test_the_pure_rule(self):
        self.assertEqual(run_par.spark_jobs_env(24, {}), {"T_SPARK_JOBS": "1"})
        self.assertEqual(run_par.spark_jobs_env(2, {}), {"T_SPARK_JOBS": "1"})
        self.assertEqual(run_par.spark_jobs_env(24, {"T_SPARK_JOBS": "4"}), {})
        self.assertEqual(run_par.spark_jobs_env(24, {"T_SPARK_JOBS": " "}), {"T_SPARK_JOBS": "1"})
        self.assertEqual(run_par.spark_jobs_env(1, {}), {})
        self.assertEqual(run_par.spark_jobs_env(0, {}), {})

    def _fake_backend(self):
        mod = types.ModuleType("verifiers.t3fake")

        def version():
            return "t3fake 1"

        def verify(path, budget=None):
            return verifiers.Result(backend="t3fake", backend_version="t3fake 1",
                                    source_sha256="", ok=False,
                                    outcome=f"env={os.environ.get('T_SPARK_JOBS')}")
        mod.version, mod.verify = version, verify
        sys.modules["verifiers.t3fake"] = mod
        return mod

    def _dispatch(self, jobs_arg):
        tasks = [HERE / "tasks" / "abs.t", HERE / "tasks" / "max.t"]
        present = [("t3fake", fake_lower, "txt")]
        saved = harness.OUT
        with tempfile.TemporaryDirectory() as d:
            harness.OUT = Path(d)
            try:
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rows, _w, _ok = run_par.lower_and_dispatch(tasks, present, jobs_arg)
            finally:
                harness.OUT = saved
        return {name: cells["t3fake"] for name, cells in rows.items()}

    @unittest.skipUnless(sys.platform.startswith("linux"), "fork-inherited fake backend")
    def test_workers_get_one_prover_per_call_and_the_parent_does_not(self):
        self._fake_backend()
        saved = os.environ.pop("T_SPARK_JOBS", None)
        try:
            cells = self._dispatch(jobs_arg=2)
            self.assertEqual(cells, {"abs": ("env=1", "env=1", True),
                                     "max": ("env=1", "env=1", True)})
            self.assertNotIn("T_SPARK_JOBS", os.environ)
            cells = self._dispatch(jobs_arg=1)
            self.assertEqual(cells["abs"], ("env=None", "env=None", True))
            os.environ["T_SPARK_JOBS"] = "4"
            cells = self._dispatch(jobs_arg=2)
            self.assertEqual(cells["abs"], ("env=4", "env=4", True))
        finally:
            os.environ.pop("T_SPARK_JOBS", None)
            if saved is not None:
                os.environ["T_SPARK_JOBS"] = saved
            sys.modules.pop("verifiers.t3fake", None)


if __name__ == "__main__":
    unittest.main()
