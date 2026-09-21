#!/usr/bin/env python3
"""Is that pid still running, and how do we ask it to stop -- once per platform, because the POSIX
idioms are not merely unavailable on Windows, they do the wrong thing.

`t/lab.py` watches steps it did not always start: it reads a pid out of `runs/logs/<step>.pid` and
has to decide, several times a second, whether that step is still going, and on `Stop` it has to
end the step and everything the step spawned. It did both inline with two POSIX calls:

* `os.killpg` is `Availability: Unix` (docs.python.org/3/library/os.html#os.killpg), so `Stop`
  raised `AttributeError` on Windows before it stopped anything.
* `os.kill(pid, 0)` is not a probe there. The same page says that on Windows any `sig` other than
  `CTRL_C_EVENT` or `CTRL_BREAK_EVENT` "will cause the process to be unconditionally killed by the
  TerminateProcess API, and the exit code will be set to sig"
  (docs.python.org/3/library/os.html#os.kill). Signal 0 is not carved out, so the harmless
  liveness check terminates the step it was asking about -- and sets its exit code to 0, which is
  the value a run that finished cleanly would have. The window would report success for a job it
  had just destroyed.

So the probe is written twice, and the Windows one uses a mechanism that carries no right to
terminate: a read-only handle, waited on for zero milliseconds. `t/test_proc.py` re-reads this
file's own source and asserts no `os.kill` call lives outside the `_posix` helpers, because this is
a bug that comes back -- the next editor reaches for the idiom they know.

Where a platform cannot tell, both functions answer "alive". A pid we may not signal is a pid that
exists (stackoverflow.com/q/568271, the EPERM answer); calling it dead would make the window
announce that a running job had finished, and that is the expensive direction of the mistake.
"""
from __future__ import annotations

import os
import signal
import subprocess
import time

__all__ = ["alive", "stop_tree"]

WINDOWS = os.name == "nt"

# Ask, wait, insist, wait. Measured here 2026-09-20: a sleeping python child of ours was gone
# 0.000 s after SIGTERM to its group (worst of 20 runs) and a two-deep tree in 0.011 s (worst of
# 10), so these ceilings are not for the common case -- they are for a step that is mid-write on an
# answer file and should be allowed to finish the line. They are also a freeze: `Stop` is a Tk
# button callback and runs on the GUI thread, so 2 s + 1 s is the longest the window can hang, and
# a hang that short was judged cheaper than leaving half a step alive.
_POLITE_GRACE = 2.0
_FORCE_GRACE = 1.0
_POLL = 0.02

# Windows constants. Values from learn.microsoft.com/en-us/windows/win32/procthread/process-security-and-access-rights
# and learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject.
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000  # read-only right; PROCESS_TERMINATE is 0x0001 and is
_SYNCHRONIZE = 0x00100000                    # never asked for, so no handle here can kill
_WAIT_OBJECT_0 = 0x00000000                  # signalled -- a process object signals when it exits
_ERROR_ACCESS_DENIED = 5
_ERROR_INVALID_PARAMETER = 87


def alive(pid: int) -> bool:
    """True if a process with this pid exists and we are allowed to signal it.

    Sends nothing that could terminate it, on any platform.

    An exited child of ours that nobody has waited for counts as alive, because a zombie is still
    in the process table and still answers the probe (checked on this machine: an exited child
    answers `os.kill(pid, 0)` until `wait()`, then raises `ProcessLookupError`). `stop_tree` reaps
    before it answers; a caller that holds the `Popen` should ask `Popen.poll` instead, which is
    what `t/lab.py` does for the steps it started itself.
    """
    if pid <= 0:
        # To kill(2) pid 0 means every process in our own process group and a negative pid means a
        # process group; to Windows pid 0 is the System Idle Process. None of those is a step, and
        # all of them would aim the next call at something we did not mean
        # (stackoverflow.com/q/568271 raises ValueError for 0 for the same reason).
        return False
    return _alive_windows(pid) if WINDOWS else _alive_posix(pid)


def stop_tree(pid: int) -> bool:
    """Ask the process and everything it started to stop, politely first, then not.

    True if the pid is gone afterwards. Raises nothing on any platform, including for a pid that
    is already gone, never existed, or was never ours.
    """
    if pid <= 0:
        return True
    try:
        return _stop_windows(pid) if WINDOWS else _stop_posix(pid)
    except Exception:
        # Wider than OSError on purpose. The contract is that this never raises, because a Stop
        # button is not the place to surface an EPERM from a pid that turned out to belong to
        # someone else, a WinError out of taskkill, or an AttributeError from the ctypes handshake
        # on some platform that answers os.name == "nt" without a kernel32. Whether it worked is a
        # question the probe can still answer, so the answer is not lost with the exception.
        return not alive(pid)


# ---------------------------------------------------------------- POSIX

def _alive_posix(pid: int) -> bool:
    """Signal 0 here really is the no-op existence probe Windows only pretends to have.

    The three-way reading is from stackoverflow.com/q/568271: ESRCH means no such pid, and EPERM
    "clearly means there's a process to deny access to".
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        # kill(2) documents only EINVAL, EPERM and ESRCH, and EINVAL cannot happen for sig 0, so
        # this is unreachable rather than a case with a defensible answer.
        return False
    return True


def _stop_posix(pid: int) -> bool:
    _reap(pid)
    if not _alive_posix(pid):
        return True
    for sig, grace in ((signal.SIGTERM, _POLITE_GRACE), (signal.SIGKILL, _FORCE_GRACE)):
        _signal_group_posix(pid, sig)
        if _gone_within(pid, grace):
            return True
    return not _alive_posix(pid)


def _signal_group_posix(pid: int, sig: int) -> None:
    """Signal the step's whole process group -- but only when the step actually leads one.

    `t/lab.py` starts steps with `start_new_session=True`, which makes the step a session leader,
    so its process group id is its own pid. That is what makes `killpg` right rather than clever: a
    step is `bash -lc` wrapped around a python that spawns more, and SIGTERM to the bash alone
    orphans the work that holds the GPUs.

    A pid read out of a pid file need not lead anything, though, and `killpg(pid)` on a non-leader
    signals whichever group happens to carry that number -- which can be this window's own. So the
    kernel is asked first, and a pid that does not lead its group is signalled alone.
    """
    try:
        leads = os.getpgid(pid) == pid
    except OSError:
        leads = False
    try:
        if leads:
            os.killpg(pid, sig)
        else:
            os.kill(pid, sig)
    except ProcessLookupError:
        pass                     # exited between the probe and the signal; that is the goal
    except PermissionError:
        pass                     # not ours after all -- leave it alone rather than keep trying
    except OSError:
        pass
    _reap(pid)


def _reap(pid: int) -> None:
    """Collect an exited child of ours so it stops looking alive. POSIX only.

    This is the trap in the whole file. A child that has exited but has not been waited for is a
    zombie: still in the process table, and `os.kill(pid, 0)` against it still succeeds. Without
    this call `stop_tree` would kill a step and then report it running for ever.

    If the caller also holds a `Popen` for this pid we win the race for its status, so its `poll()`
    reports returncode 0 rather than -SIGTERM. `subprocess` already handles a child it cannot find
    (`ChildProcessError` inside `_internal_poll`) instead of raising, and `t/lab.py` only asks
    `poll()` whether the step is over, not how it ended.
    """
    try:
        os.waitpid(pid, os.WNOHANG)
    except OSError:
        # ChildProcessError for anything that is not our child -- the normal case for a step
        # started by an earlier window, and not an error here.
        pass


# ---------------------------------------------------------------- Windows

def _alive_windows(pid: int) -> bool:
    """Open a handle that carries no right to terminate, then ask whether it has signalled yet.

    Neither call can kill. `PROCESS_QUERY_LIMITED_INFORMATION` and `SYNCHRONIZE` are a read right
    and a wait right; `TerminateProcess` needs `PROCESS_TERMINATE`, which is not requested
    (learn.microsoft.com/en-us/windows/win32/procthread/process-security-and-access-rights).
    `WaitForSingleObject` with a zero timeout "does not enter a wait state ... it always returns
    immediately", and a process handle is signalled once the process terminates
    (learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject), so
    anything other than WAIT_OBJECT_0 -- WAIT_TIMEOUT for a running process, WAIT_FAILED if the
    wait itself broke -- is read as alive.

    psutil reads `GetExitCodeProcess` instead, and its own source admits STILL_ACTIVE "is not fully
    reliable" because a process may legitimately exit with 259, so it settles the ambiguity by
    enumerating every pid on the machine (github.com/giampaolo/psutil, psutil/arch/windows/proc_utils.c).
    This runs several times a second from a GUI poll, so the wait, which has no such ambiguity, is
    used instead -- but the error codes below are read exactly the way psutil reads them.
    """
    import ctypes                   # imported inside the branch: ctypes.WinDLL exists only on
    from ctypes import wintypes     # Windows (on this Linux python 3.14 it is simply absent)

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    k32.OpenProcess.restype = wintypes.HANDLE   # declared, because ctypes defaults to c_int and a
    k32.CloseHandle.argtypes = (wintypes.HANDLE,)   # 64-bit handle would come back truncated
    k32.CloseHandle.restype = wintypes.BOOL
    k32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    k32.WaitForSingleObject.restype = wintypes.DWORD

    handle = k32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION | _SYNCHRONIZE, False, pid)
    if not handle:
        err = ctypes.get_last_error()
        if err == _ERROR_ACCESS_DENIED:
            return True     # the process is there, it is just not ours to open
        # "Yeah, this is the actual error code in case of 'no such process'" is psutil's comment on
        # ERROR_INVALID_PARAMETER, and it is the only code here that means dead. A failed
        # OpenProcess that leaves ERROR_SUCCESS behind also happens
        # (github.com/giampaolo/psutil/issues/1877); psutil settles that by enumerating pids, and
        # it is answered alive here, as is any other code we do not recognise.
        return err != _ERROR_INVALID_PARAMETER
    try:
        return k32.WaitForSingleObject(handle, 0) != _WAIT_OBJECT_0
    finally:
        k32.CloseHandle(handle)


def _stop_windows(pid: int) -> bool:
    """`taskkill /t`, then `taskkill /t /f`.

    `/t` "Ends the specified process and any child processes started by it" and `/f` forces
    (learn.microsoft.com/en-us/windows-server/administration/windows-commands/taskkill), which is
    the nearest thing Windows offers to signalling the POSIX process group. Without `/t` a step's
    own children survive it, which is the orphaned-GPU-job failure the group signal exists to
    prevent. The Win32 alternative is a job object, and that has to be chosen when the process is
    created; these steps were not started inside one.

    Without `/f`, taskkill asks by posting a close to the process's window, and a step here is a
    console program with no window, so the polite pass commonly refuses with "could only be
    terminated forcibly" -- hence a second pass rather than trust in the first. taskkill's exit
    code is not read: 128 for "process not found" and 1 for a refusal both end with the same
    question, which the probe answers better than the exit code does.

    `os.kill(pid, signal.CTRL_BREAK_EVENT)` is the other documented route on Windows and is
    deliberately not used. It needs the child to have been started with CREATE_NEW_PROCESS_GROUP,
    which "is necessary for using os.kill() on the subprocess"
    (docs.python.org/3/library/subprocess.html); `t/lab.py` passes `start_new_session=True`, which
    the same page marks `Availability: POSIX`. So on Windows the step sits in this window's own
    console process group, and a control event would close the watching window along with it.
    """
    for extra, grace in ((["/t"], _POLITE_GRACE), (["/t", "/f"], _FORCE_GRACE)):
        _taskkill(["/pid", str(pid), *extra])
        if _gone_within(pid, grace):
            return True
    return not _alive_windows(pid)


def _taskkill(args: list[str]) -> None:
    try:
        subprocess.run(["taskkill", *args], capture_output=True, timeout=10,
                       # or a console window flashes over the lab window on every Stop
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        # taskkill absent from PATH, or wedged past the timeout. The forced pass and then the probe
        # decide what actually happened; there is nothing useful to raise at a button.
        pass


# ---------------------------------------------------------------- shared

def _gone_within(pid: int, seconds: float) -> bool:
    """Poll rather than wait: the pid may not be our child, so there is nothing to wait() on."""
    deadline = time.monotonic() + seconds
    while True:
        if not WINDOWS:
            _reap(pid)
        if not alive(pid):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(_POLL)
