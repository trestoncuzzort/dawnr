#!/usr/bin/env python3
"""t/py_sandbox.py -- run a model-written Python function on a problem's assertions, in a sandbox
(2026-10-01).

    python3 t/py_sandbox.py solution.py "assert f(2) == 4" "assert f(3) == 9"

The specification-first pipeline (t/PREDICT-2026-10-01-spec-first.md) has the student write a
Python solution before it writes a specification, and keeps that solution only if it passes the
problem's visible tests. That means executing code a model wrote.

HumanEval's harness (github.com/openai/human-eval, human_eval/execution.py) is the published
shape: every completion in its own process, a temporary directory, a time limit, a memory limit,
one verdict per test. Its `reliability_guard` nulls destructive functions inside the interpreter
and says of itself that it "is NOT a security sandbox". This machine has a real one, so the guard
is replaced, not copied: bubblewrap runs the interpreter in fresh namespaces where /home and /tmp
are empty tmpfs, the system directories are read-only, and there is no network. Inside it the
runner sets an address-space limit, forbids new processes, and gives each assertion its own alarm.

There is no unsandboxed fallback: where bubblewrap is missing, `available()` is False and
`run_tests` refuses. Model-written code is never exec'd in this process.

`Session` keeps one such interpreter alive and calls the model's function on many inputs (the
gate's agreement stage, t/spec_gate.py: Clover's doc2code edge, arXiv:2310.17807, compares two
artifacts by their outputs on a set of inputs). Same namespaces, same limits, one alarm a call.
"""
from __future__ import annotations

import json
import os
import select
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RESULT = "@@py_sandbox result@@ "
RUNNER = r'''
import json, os, resource, signal, sys
MEM = %(memory)d * 1024 * 1024
JOB = os.path.dirname(os.path.abspath(__file__))       # /job under bwrap; the job folder itself under Seatbelt
for _lim, _val in ((resource.RLIMIT_AS, MEM), (resource.RLIMIT_NPROC, 0), (resource.RLIMIT_FSIZE, 1 << 20)):
    try:
        resource.setrlimit(_lim, (_val, _val))
    except (ValueError, OSError):
        if sys.platform != "darwin":                    # macOS does not enforce every limit; Linux must
            raise
RESULT = %(result)r


def _alarm(*_):
    raise TimeoutError()


def done(payload):
    sys.stdout.write("\n" + RESULT + json.dumps(payload) + "\n")
    sys.stdout.flush()
    raise SystemExit(0)


signal.signal(signal.SIGALRM, _alarm)
g = {"__name__": "solution"}
signal.alarm(%(per_test)d)
try:
    exec(compile(open(os.path.join(JOB, "solution.py")).read(), "solution", "exec"), g)
except BaseException as e:
    signal.alarm(0)
    done({"load": (type(e).__name__ + ": " + str(e))[:200]})
signal.alarm(0)
out = []
for a in json.load(open(os.path.join(JOB, "asserts.json"))):
    signal.alarm(%(per_test)d)
    try:
        exec(a, dict(g))
        out.append("pass")
    except AssertionError:
        out.append("fail")
    except TimeoutError:
        out.append("timeout")
    except BaseException as e:
        out.append("error: " + type(e).__name__)
    finally:
        signal.alarm(0)
done({"verdicts": out})
'''


SESSION_RUNNER = r'''
import json, os, resource, signal, sys
MEM = %(memory)d * 1024 * 1024
JOB = os.path.dirname(os.path.abspath(__file__))       # /job under bwrap; the job folder itself under Seatbelt
for _lim, _val in ((resource.RLIMIT_AS, MEM), (resource.RLIMIT_NPROC, 0), (resource.RLIMIT_FSIZE, 1 << 20)):
    try:
        resource.setrlimit(_lim, (_val, _val))
    except (ValueError, OSError):
        if sys.platform != "darwin":                    # macOS does not enforce every limit; Linux must
            raise
RESULT = %(result)r


def _alarm(*_):
    raise TimeoutError()


def say(payload):
    sys.stdout.write("\n" + RESULT + json.dumps(payload) + "\n")
    sys.stdout.flush()


def plain(v, depth=0):
    """The value as JSON carries it faithfully, or TypeError: a set, a dict, bytes, an object."""
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, float):
        if v != v or v in (float("inf"), float("-inf")):
            raise TypeError("float")
        return v
    if isinstance(v, (list, tuple)) and depth < 8:
        return [plain(x, depth + 1) for x in v]
    raise TypeError(type(v).__name__)


signal.signal(signal.SIGALRM, _alarm)
g = {"__name__": "solution"}
signal.alarm(%(per_call)d)
try:
    exec(compile(open(os.path.join(JOB, "solution.py")).read(), "solution", "exec"), g)
    f = g[%(fn)r]
    if not callable(f):
        raise TypeError("not callable")
except BaseException as e:
    signal.alarm(0)
    say({"load": (type(e).__name__ + ": " + str(e))[:200]})
    raise SystemExit(0)
signal.alarm(0)
say({"ready": True})
for line in sys.stdin:
    try:
        args = json.loads(line)
    except ValueError:
        say({"error": "bad request"})
        continue
    signal.alarm(%(per_call)d)
    try:
        out = f(*args)
        signal.alarm(0)
        try:
            say({"value": plain(out)})
        except (TypeError, ValueError) as e:
            say({"unrepresentable": str(e)[:60]})
    except TimeoutError:
        say({"timeout": True})
    except BaseException as e:
        signal.alarm(0)
        say({"error": type(e).__name__})
    finally:
        signal.alarm(0)
'''


class CallTimeout(Exception):
    """The function did not return within the session's time for one call."""


class CallError(Exception):
    """The function raised; str() is the exception's class name."""


class Unrepresentable(Exception):
    """The function returned a value JSON cannot carry faithfully (a set, a dict, an object)."""


class LoadError(Exception):
    """The code did not load, or does not define the function."""


SEATBELT = "/usr/bin/sandbox-exec"       # only /usr/bin's copy is trusted (codex-rs/sandboxing/src/seatbelt.rs)
SEATBELT_POLICIES = Path(__file__).resolve().parent / "third_party" / "codex_seatbelt"
SEATBELT_OURS = """
; t/py_sandbox.py: the job folder and the Python installation may be read; only the job's own temporary
; folder may be written. Nothing else is granted beyond Codex's base and read-only platform policies above.
(allow file-read* file-test-existence (subpath (param "JOB")) (subpath (param "PY_PREFIX")))
(allow file-map-executable (subpath (param "PY_PREFIX")))
(allow file-read* file-write* file-test-existence (subpath (param "TMP")))
"""


_PROBED: dict = {}


def available() -> bool:
    """A sandbox that runs here. On Linux, bwrap present is not enough: Ubuntu 23.10 and later restrict the user
    namespaces it needs unless an AppArmor profile grants them (t/apparmor-bwrap.sh), and then every run fails
    ("setting up uid map: Permission denied", seen on GitHub's Ubuntu 24.04 runner, 2026-10-02), so it is probed
    once with the flags the jobs use. Codex warns at startup on the same failure (codex-rs/linux-sandbox/README.md)."""
    if sys.platform == "darwin":
        return Path(SEATBELT).exists()
    if shutil.which("bwrap") is None:
        return False
    if "linux" not in _PROBED:
        with tempfile.TemporaryDirectory(prefix="py-sandbox-probe-") as tmp:
            cmd = _command(Path(tmp))[:-3] + ["/usr/bin/true"]          # the job's namespaces and mounts, no Python
            try:
                _PROBED["linux"] = subprocess.run(cmd, capture_output=True, timeout=20).returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                _PROBED["linux"] = False
    return _PROBED["linux"]


def why_unavailable() -> str:
    if sys.platform == "darwin":
        return f"{SEATBELT} is missing"
    if shutil.which("bwrap") is None:
        return "bubblewrap is not installed (Debian/Ubuntu: sudo apt install bubblewrap)"
    return ("bubblewrap cannot create its namespaces here; on Ubuntu 23.10 and later run once: "
            f"sudo bash {Path(__file__).resolve().parent / 'apparmor-bwrap.sh'}")


def seatbelt_profile() -> str:
    """Codex CLI's macOS policies (github.com/openai/codex, Apache-2.0, vendored unchanged) and ours after them."""
    parts = [(SEATBELT_POLICIES / f).read_text() for f in ("seatbelt_base_policy.sbpl", "seatbelt_read_only_platform_defaults.sbpl")]
    return "\n".join(parts) + SEATBELT_OURS


def _seatbelt_command(job: Path, python: str | None = None, prefix: str | None = None) -> list[str]:
    # Seatbelt matches the real path: macOS's temporary folders live under /var, a link to /private/var, so a grant
    # on /var/folders/... denies the files in it. Codex canonicalises every path it grants for the same reason
    # (codex-rs/sandboxing/src/seatbelt.rs); found on CI's macOS runner, 2026-10-02.
    job = Path(job).resolve()
    prefix = str(Path(prefix or sys.base_prefix).resolve())
    tmp = job / "tmp"
    tmp.mkdir(exist_ok=True)
    return [SEATBELT, "-p", seatbelt_profile(), f"-DJOB={job}", f"-DPY_PREFIX={prefix}",
            f"-DTMP={tmp}", python or sys.executable, "-I", str(job / "runner.py")]


def _command(job: Path) -> list[str]:
    if sys.platform == "darwin":
        return _seatbelt_command(job)
    cmd = ["bwrap", "--unshare-all", "--die-with-parent", "--new-session",
           "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--tmpfs", "/home", "--chdir", "/tmp"]
    for d in ("/usr", "/lib", "/lib64", "/bin", "/etc/alternatives"):
        if Path(d).exists():
            cmd += ["--ro-bind", d, d]
    return cmd + ["--ro-bind", str(job), "/job", "/usr/bin/python3", "-I", "/job/runner.py"]


def run_tests(code: str, asserts: list[str], per_test: int = 3, memory_mb: int = 1024) -> dict:
    """{"status": "ran", "verdicts": [...], "all_pass": bool} | {"status": "load-error", "why"} |
    {"status": "timeout"} | {"status": "sandbox-error", "why"}. Raises RuntimeError without a sandbox."""
    if not available():
        raise RuntimeError(f"py_sandbox: no sandbox ({why_unavailable()}); model-written code is not run without it")
    with tempfile.TemporaryDirectory(prefix="py-sandbox-") as tmp:
        job = Path(tmp)
        (job / "solution.py").write_text(code, encoding="utf-8")
        (job / "asserts.json").write_text(json.dumps(list(asserts)), encoding="utf-8")
        (job / "runner.py").write_text(RUNNER % {"memory": memory_mb, "per_test": per_test, "result": RESULT},
                                       encoding="utf-8")
        try:
            p = subprocess.run(_command(job), capture_output=True, text=True, errors="replace",
                               timeout=per_test * (len(asserts) + 1) + 5)
        except subprocess.TimeoutExpired:
            return {"status": "timeout"}
    for line in reversed(p.stdout.splitlines()):
        if line.startswith(RESULT):
            payload = json.loads(line[len(RESULT):])
            if "load" in payload:
                return {"status": "load-error", "why": payload["load"]}
            v = payload["verdicts"]
            return {"status": "ran", "verdicts": v, "all_pass": bool(v) and all(x == "pass" for x in v)}
    return {"status": "sandbox-error", "why": (p.stderr or p.stdout)[-300:]}


class Session:
    """A model-written function held in one sandboxed interpreter and called many times.

        with py_sandbox.Session(code, "f") as s:
            s.call([2])            # -> the value | CallError | CallTimeout | Unrepresentable

    A call that overruns kills the interpreter; the next call starts a fresh one. Values cross as
    JSON: a tuple comes back as a list, None as None."""

    def __init__(self, code: str, fn: str, per_call: int = 3, memory_mb: int = 1024):
        if not available():
            raise RuntimeError(f"py_sandbox: no sandbox ({why_unavailable()}); model-written code is not run without it")
        self.code, self.fn, self.per_call, self.memory_mb = code, fn, per_call, memory_mb
        self._tmp = tempfile.TemporaryDirectory(prefix="py-sandbox-")
        job = Path(self._tmp.name)
        (job / "solution.py").write_text(code, encoding="utf-8")
        (job / "runner.py").write_text(SESSION_RUNNER % {"memory": memory_mb, "per_call": per_call,
                                                         "result": RESULT, "fn": fn}, encoding="utf-8")
        self._job, self._p, self._buf, self.restarts = job, None, b"", 0
        self._start()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _start(self) -> None:
        self._buf = b""
        self._p = subprocess.Popen(_command(self._job), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL)
        first = self._read(self.per_call + 5)
        if first is None or "load" in first:
            why = "the sandbox did not start" if first is None else first["load"]
            self._kill()
            raise LoadError(why)

    def _kill(self) -> None:
        if self._p is not None:
            try:
                self._p.kill()
                self._p.wait(timeout=5)
            except Exception:                                   # noqa: BLE001
                pass
            for f in (self._p.stdin, self._p.stdout):
                try:
                    f.close()
                except Exception:                               # noqa: BLE001
                    pass
            self._p = None

    def _read(self, seconds: float) -> dict | None:
        """The next protocol line, or None when the time is up or the interpreter is gone. Anything
        the model's code prints is not a protocol line and is skipped."""
        end, fd = time.monotonic() + seconds, self._p.stdout.fileno()
        while True:
            while b"\n" in self._buf:
                line, self._buf = self._buf.split(b"\n", 1)
                text = line.decode("utf-8", "replace")
                if text.startswith(RESULT):
                    try:
                        return json.loads(text[len(RESULT):])
                    except ValueError:
                        return None
            left = end - time.monotonic()
            if left <= 0:
                return None
            ready, _, _ = select.select([fd], [], [], left)
            if not ready:
                return None
            chunk = os.read(fd, 1 << 16)
            if not chunk:
                return None
            self._buf += chunk
            if len(self._buf) > (8 << 20):                      # a function that prints without end
                return None

    def call(self, args: list):
        if self._p is None or self._p.poll() is not None:
            self.restarts += 1
            self._start()
        try:
            self._p.stdin.write((json.dumps(list(args)) + "\n").encode("utf-8"))
            self._p.stdin.flush()
        except (BrokenPipeError, OSError, TypeError, ValueError) as e:
            if isinstance(e, (TypeError, ValueError)):
                raise CallError("arguments JSON cannot carry") from None
            self._kill()
            raise CallTimeout() from None
        reply = self._read(self.per_call + 1.5)
        if reply is None or reply.get("timeout"):
            self._kill()                                        # it may still be running; never reuse it
            raise CallTimeout()
        if "value" in reply:
            return reply["value"]
        if "unrepresentable" in reply:
            raise Unrepresentable(reply["unrepresentable"])
        raise CallError(str(reply.get("error", "error")))

    def close(self) -> None:
        self._kill()
        self._tmp.cleanup()


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2:
        print(__doc__)
        return 2
    print(json.dumps(run_tests(Path(argv[0]).read_text(encoding="utf-8"), argv[1:]), indent=1))
    return 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
