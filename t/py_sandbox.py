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
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RESULT = "@@py_sandbox result@@ "
RUNNER = r'''
import json, resource, signal, sys
MEM = %(memory)d * 1024 * 1024
resource.setrlimit(resource.RLIMIT_AS, (MEM, MEM))
resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
resource.setrlimit(resource.RLIMIT_FSIZE, (1 << 20, 1 << 20))
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
    exec(compile(open("/job/solution.py").read(), "solution", "exec"), g)
except BaseException as e:
    signal.alarm(0)
    done({"load": (type(e).__name__ + ": " + str(e))[:200]})
signal.alarm(0)
out = []
for a in json.load(open("/job/asserts.json")):
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


def available() -> bool:
    return shutil.which("bwrap") is not None


def _command(job: Path) -> list[str]:
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
        raise RuntimeError("py_sandbox: bubblewrap is not installed; model-written code is not run without it")
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


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2:
        print(__doc__)
        return 2
    print(json.dumps(run_tests(Path(argv[0]).read_text(encoding="utf-8"), argv[1:]), indent=1))
    return 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
