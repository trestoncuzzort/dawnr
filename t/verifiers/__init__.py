"""t.verifiers: one Outcome, many kernels.

Every backend module in this package exposes the same two functions:

    version() -> str                      # exact pinned toolchain identity
    verify(path, budget=None) -> Result   # one file, one verdict

The Outcome taxonomy is dafny_verify.py's, unchanged, because it was measured
there and the reasons transfer: a MALFORMED rejected-half teaches syntax, not
proof; a VACUOUS pass is the spec weakened out from under the theorem; a
TIMEOUT is not knowledge; and TOOL_ERROR is never evidence of anything.

flake_check() is the noise-floor discipline: no single verdict is trusted for
a witness until the same file returns the same outcome n times. Backends with
an SMT solver underneath (Dafny, Verus, SPARK, Frama-C) need this; the
kernel-checked backends (Lean, Rocq, Agda) are architecturally deterministic
and may pass n=1, but saying so is the dossier's claim and re-measuring it
here is cheap, so the default is n=3 for everyone.
"""
from __future__ import annotations

import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path


def safe_text(p: Path) -> str:
    """Decode a source file for regex scanning WITHOUT crashing on non-UTF8.

    Wave-1 audit (2026-08-31) crashed six of seven adapters with an
    unhandled UnicodeDecodeError: each read the source with
    `path.read_text(encoding="utf-8")` before invoking its kernel, so a
    probe of random bytes killed the adapter instead of scoring MALFORMED.
    errors="replace" keeps every real byte position intact for the ban
    regexes (a replacement char never spuriously matches a keyword) while
    guaranteeing a str. The verdict hash still binds to raw bytes via
    sha256_file; this function is for scanning, never for hashing."""
    return p.read_bytes().decode("utf-8", errors="replace")


class Outcome:
    VERIFIED = "verified"      # a real proof, and only this is ok=True
    VACUOUS = "vacuous"        # accepted, but for the wrong reason, never a win
    REFUTED = "refuted"        # the honest "this is wrong"
    MALFORMED = "malformed"    # does not parse/resolve; NOT a proof failure
    TIMEOUT = "timeout"        # budget exhausted; we do NOT know it is wrong
    # The solver stopped WITHOUT exhausting the budget and WITHOUT a
    # countermodel. Added by measurement (2026-09-01, gnatprove FSF 16.1.0):
    # gnatprove's per-unit .spark audit carries exactly three unproved_status
    # values, "limit", "gave_up" and "unknown", and abs_twin.ads/max_twin.ads
    # report "gave_up" after Z3 spent 1 step of 20000. Folding that into
    # TIMEOUT would assert a budget exhaustion the kernel's own record denies;
    # folding it into REFUTED is the bug this outcome exists to make
    # unrepresentable. ok=False, exactly like TIMEOUT: not knowledge.
    UNPROVED = "unproved"
    TOOL_ERROR = "tool_error"  # anything else; never counted as evidence


@dataclass
class Result:
    backend: str
    backend_version: str
    source_sha256: str
    outcome: str
    ok: bool = False           # True ONLY for Outcome.VERIFIED
    exit_code: int = -1
    wall_ms: int = 0
    budget: str = ""           # the deterministic bound used, backend dialect
    error: str = ""
    extras: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        return asdict(self)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# Process groups run_tree has started and not yet collected. start_new_session
# detaches a prover from its driver's process group, so a driver killed from
# outside (a stopped agent, a closed tmux session, SIGTERM) left its prover
# running with nobody to kill it: 2026-09-16, six orphaned rocqworker
# processes (/tmp/t-rocq-* scratch dirs, parent systemd) had run 24 to 44
# hours and held about 290 GB of memory between them. The driver now kills
# every live group at interpreter exit and on SIGTERM or SIGHUP, then takes
# the signal's default action. SIGKILL of the driver still cannot be caught.
_LIVE_GROUPS: set[int] = set()


def _kill_live_groups() -> None:
    import signal
    for pg in list(_LIVE_GROUPS):
        try:
            os.killpg(pg, signal.SIGKILL)
        except OSError:
            pass


def _kill_live_groups_and_die(signum, frame) -> None:
    import signal
    _kill_live_groups()
    signal.signal(signum, signal.SIG_DFL)
    os.kill(os.getpid(), signum)


def _install_group_reaper() -> None:
    import atexit
    import signal
    atexit.register(_kill_live_groups)
    # SIGHUP does not exist on Windows, and this runs at import: without the
    # guard the whole module raises AttributeError there and every test that
    # touches the harness fails at collection rather than at use (issue #44).
    for sig in (s for s in (getattr(signal, "SIGTERM", None),
                            getattr(signal, "SIGHUP", None)) if s is not None):
        try:
            if signal.getsignal(sig) is signal.SIG_DFL:
                signal.signal(sig, _kill_live_groups_and_die)
        except ValueError:      # not the main thread: atexit still holds
            pass


_install_group_reaper()


def run_tree(cmd, *, timeout, cwd=None, env=None, capture_output=True,
             text=False, **kw):
    """subprocess.run for a prover that forks. The child starts its own
    session, and a timeout kills the whole process group before raising
    TimeoutExpired, so a straggling z3, gnatwhy3 or alt-ergo cannot outlive
    the scratch directory or the budget. Added 2026-09-09 after truth_fuzz
    died in spark's TemporaryDirectory cleanup ("Directory not empty:
    'gnatprove'"): subprocess.run's timeout kills gnatprove alone, and its
    orphaned prover kept writing into the directory being removed. Same
    return type as subprocess.run, so call sites read as before."""
    import signal
    import subprocess
    proc = subprocess.Popen(
        cmd, cwd=cwd, env=env, start_new_session=True,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE if capture_output else None,
        text=text, **kw)
    _LIVE_GROUPS.add(proc.pid)
    try:
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_group(proc.pid)
            proc.communicate()
            raise
    finally:
        # EVERY exit path kills the group: a normal return, TimeoutExpired,
        # any other exception, KeyboardInterrupt. Until 2026-09-25 only the
        # timeout branch did, so a leader that exited and left a grandchild
        # (why3server's z3 under gnatprove) orphaned it: 12 and then 26 z3
        # processes ran for a day on the lab (r12 blocker A5). CPython's
        # subprocess.run kills its child on every path -- `except:  #
        # Including KeyboardInterrupt` in Lib/subprocess.py (fetched
        # 2026-09-25, raw.githubusercontent.com/python/cpython/3.12/Lib/
        # subprocess.py); the whole group is the unit here because a prover
        # forks (Beyer, Loewe, Wendler, "Reliable benchmarking", STTT 2019,
        # doi.org/10.1007/s10009-017-0469-y, section 2: a tool "may
        # arbitrarily spawn child processes"). Process groups can be escaped
        # with setsid/setpgid (their section 3.3); cgroups would close that
        # and the shared lab delegates none to us, so t/stall_check.py's
        # orphan check is the detector for that case.
        #
        # On the normal path the leader is already reaped, so killpg
        # addresses its pgid with the leader gone. A pid cannot be reused
        # while its process group still has members (POSIX), and an empty
        # group's id is reused only after the pid counter wraps (4,194,304
        # on the lab), so the kill cannot land on a stranger.
        _kill_group(proc.pid)
        if proc.returncode is None:          # exception path: leader not reaped yet
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            for pipe in (proc.stdout, proc.stderr):   # communicate() never got to close them
                if pipe is not None and not pipe.closed:
                    pipe.close()
        _LIVE_GROUPS.discard(proc.pid)       # after the kill, so atexit covers the window
    return subprocess.CompletedProcess(cmd, proc.returncode, out, err)


def _kill_group(pgid: int) -> None:
    """SIGKILL a process group; a group that no longer exists is not an
    error, and one we may not signal (a stranger's, after pid reuse) is
    left alone rather than raised over."""
    import signal
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def _serial() -> bool:
    """T_CELL_SERIAL=1 restores the one-call-at-a-time form of flake_check
    and cell_pair, for measuring what concurrency itself changes."""
    return os.environ.get("T_CELL_SERIAL", "") not in ("", "0")


LAUNCHES = 0    # t/tlib.py's cache measurement: one dispatch through here is
                # one subprocess launch by the backend's verify(); a cache
                # hit in tlib.verify never calls flake_check at all, so this
                # counter going flat across a second verify() call IS the
                # "ran no kernel" measurement (t/tlib.py, t/test_tlib.py).


def reset_launch_count() -> None:
    global LAUNCHES
    LAUNCHES = 0


def flake_check(verify_fn, path: Path, n: int = 3):
    """Run verify n times; return (Result, agreed). Disagreement returns the
    LAST result (by submission order) with agreed=False, so the caller must
    refuse the witness, not pick a favorite run.

    The n runs are concurrent since 2026-09-09 (threads; each verify is a
    subprocess in its own scratch directory, or writes nothing beside the
    source: measured for all seven adapters, framac with -wp-cache none).
    A verdict that depends on whether its siblings run beside it is exactly
    the load-sensitivity this function exists to refuse, so concurrency
    changes no verdict a serial run would have trusted; it changes the
    cell's wall time from n budgets to one. T_CELL_SERIAL=1 is the old
    form, kept for that measurement."""
    global LAUNCHES
    LAUNCHES += n
    if _serial() or n <= 1:
        results = [verify_fn(path) for _ in range(n)]
    else:
        with ThreadPoolExecutor(max_workers=n) as ex:
            results = list(ex.map(lambda _i: verify_fn(path), range(n)))
    outcomes = {r.outcome for r in results}
    return results[-1], len(outcomes) == 1


def cell_pair(verify_fn, real: Path, twin: Path, n: int = 3):
    """flake_check the real and the twin of one cell at the same time:
    ((Result, agreed), (Result, agreed)). With flake_check's own
    concurrency this is 2n kernel calls in flight per cell, so a driver's
    job count is cells in flight and its kernel-call concurrency is 2n
    times that (run_par.py documents the sizing)."""
    if _serial():
        return flake_check(verify_fn, real, n), flake_check(verify_fn, twin, n)
    with ThreadPoolExecutor(max_workers=2) as ex:
        fr = ex.submit(flake_check, verify_fn, real, n)
        ft = ex.submit(flake_check, verify_fn, twin, n)
        return fr.result(), ft.result()


def mp_context():
    """Process-pool context for the parallel drivers, on every platform.

    fork where the platform offers it (every measured run on the training
    box used fork); spawn otherwise, because Windows has no fork. Spawn
    re-imports modules in each child instead of inheriting memory, which
    imposes a contract on every caller, audited 2026-09-02 across all five
    drivers: the worker handed to the pool is a module-level function, its
    arguments pickle (strings, ints and small tuples throughout), and each
    entry point sits behind an `if __name__ == "__main__"` guard, without
    which spawn re-executes the driver inside every child. T_MP_START
    forces a method so the other platform's path can be exercised where it
    does not naturally run; the full matrix under T_MP_START=spawn on
    Linux is the witness that the spawn branch works on a real workload.
    """
    import multiprocessing
    import os
    method = os.environ.get("T_MP_START") or (
        "fork" if "fork" in multiprocessing.get_all_start_methods() else "spawn")
    return multiprocessing.get_context(method)


def acquire_run_lock(out_dir):
    """One writer for out/ at a time, on every platform.

    Two live suite runs write the same out/ filenames, so the second must
    refuse. run_par.py's /proc scan enforces that on Linux but /proc does
    not exist on Windows, so the portable mechanism is a lock file taken
    with O_EXCL. Returns a zero-argument release callable on success, or a
    refusal string naming the holder on conflict.

    Staleness: the file records the holder's pid. On POSIX a dead pid is
    detected with os.kill(pid, 0) and the lock is taken over. On Windows
    os.kill(pid, 0) TERMINATES the process (TerminateProcess semantics per
    the os.kill docs), so it is never used there; OpenProcess with
    query-limited rights answers liveness instead. That branch is
    UNVERIFIED on a real Windows box and therefore fails CLOSED: any error
    treats the holder as alive and the refusal message names the lock file
    so a human can delete a stale one by hand.
    """
    import os
    import sys
    lock = Path(out_dir) / ".run.lock"
    lock.parent.mkdir(exist_ok=True)

    def alive(pid):
        if sys.platform != "win32":
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return False
            except PermissionError:
                return True
            return True
        try:
            import ctypes
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if h:
                ctypes.windll.kernel32.CloseHandle(h)
                return True
            return ctypes.windll.kernel32.GetLastError() == 5
        except Exception:
            return True

    for _ in range(2):
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, ("%d\n" % os.getpid()).encode())
            os.close(fd)
            def release():
                try:
                    os.unlink(str(lock))
                except OSError:
                    pass
            return release
        except FileExistsError:
            try:
                head = lock.read_text().split()
            except OSError:
                head = []
            pid = int(head[0]) if head and head[0].isdigit() else None
            if pid is not None and not alive(pid):
                try:
                    os.unlink(str(lock))
                except OSError:
                    pass
                continue
            return ("another t run holds %s (pid %s). Two concurrent runs "
                    "write the same out/ filenames; let it finish, or delete "
                    "the lock file if that run is dead." % (lock, pid))
    return "could not acquire %s after clearing a stale holder" % lock
