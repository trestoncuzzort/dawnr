"""judge.py: run a proved t solution on a judge's test data and compare the output with the judge's.

    python3 t/judge.py problems/uva/p495.t --tests DIR [--io problems/uva/p495_io.py] [--show]

DIR holds the judge's cases as NNNN.in.txt / NNNN.out.txt pairs (uDebug's layout). The arithmetic is the task's
Dafny lowering, the same program Dafny verified (six other kernels verify their own lowerings of the same t
source), compiled by Dafny's Python backend so integers are unbounded. Reading the input and writing the output
belong to the problem's io module, which is unverified glue: the judge's expected outputs are its test, and they
also test the spec, since a spec can be proved and still state the wrong problem (FVAPPS, arXiv:2502.05714, found
unit tests and specifications disagreeing in the same way).

The io module (default: the .t file's stem + "_io.py") defines
    cases(text) -> list of argument tuples, one per call of the proved task;
    render(text, calls) -> the full output text, given the input text and [(args, result), ...].
A call's result arrives as a Python int, bool or list.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import surface  # noqa: E402
import tlib     # noqa: E402
from build import DAFNY  # noqa: E402

_IMPORT_LOCK = threading.RLock()


def _load_translation(directory: Path):
    """Load a translation with its own self-imports and runtime, then restore imports.

    Dafny gives every translation the same module names. Importing module_ normally
    can silently execute the previous task's code. Keep each loaded module object
    alive through its globals, but never leave its names or path in the caller's
    import state. See docs.python.org/3/library/importlib.html.
    """
    roots = {p.stem for p in directory.glob("*.py") if p.name != "__main__.py"}
    roots.update(p.name for p in directory.iterdir() if (p / "__init__.py").is_file())

    def belongs(name):
        return name.split(".", 1)[0] in roots

    with _IMPORT_LOCK:
        saved = {n: m for n, m in sys.modules.items() if belongs(n)}
        old_path = list(sys.path)
        try:
            for n in saved:
                del sys.modules[n]
            sys.path.insert(0, str(directory))
            importlib.invalidate_caches()
            runtime = importlib.import_module("_dafny")
            module = importlib.import_module("module_")
            return module, runtime
        finally:
            for n in list(sys.modules):
                if belongs(n):
                    del sys.modules[n]
            sys.modules.update(saved)
            sys.path[:] = old_path


def compile_task(task: dict, work: Path):
    """Translate the task's Dafny lowering to Python once and return the proved method as a Python callable.

    The inputs never enter Dafny source: an earlier version wrote them into a generated Main, and Dafny's front end
    took more than ten minutes on 5,000 calls (UVa 495, uDebug file 0006) and on long sequence literals (UVa
    10302). `dafny translate py --include-runtime` emits the same code `dafny run` executes, as a module."""
    src = tlib.lower(task, "dafny")
    names = re.findall(r"^method\s+(\w+)\(", src, re.M)      # helper methods come first; the task's is named after it
    name = next((x for x in names if x.lower() == task["name"].lower()), None)
    if name is None:
        raise SystemExit(f"judge: no method for task {task['name']!r} in the Dafny lowering")
    (work / "prog.dfy").write_text(src, encoding="utf-8")
    p = subprocess.run([DAFNY, "translate", "py", "--no-verify", "--include-runtime", "prog.dfy"],
                       capture_output=True, text=True, timeout=600, cwd=str(work))
    if p.returncode != 0:
        raise SystemExit("judge: dafny translate failed: " + ((p.stdout + p.stderr).strip().splitlines() or ["?"])[-1][:300])
    module, _dafny = _load_translation(work / "prog-py")
    # Dafny's Python backend escapes each underscore in a source identifier.
    # Task methods start with a capital, so Python keyword escaping is irrelevant.
    fn = getattr(module.default__, name.replace("_", "__"))

    def to_dafny(v):
        return _dafny.SeqWithoutIsStrInference([to_dafny(x) for x in v]) if isinstance(v, (list, tuple)) else v

    def from_dafny(v):
        return [from_dafny(x) for x in v] if isinstance(v, _dafny.Seq) else v

    return lambda args: from_dafny(fn(*[to_dafny(a) for a in args]))


def run_cases(call, calls: list[tuple]) -> list:
    """Each tuple in calls is one call of the proved method; returns the results in order."""
    return [call(args) for args in calls]


def _norm(s: str) -> list[str]:
    lines = [ln.rstrip() for ln in s.replace("\r\n", "\n").split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("task")
    ap.add_argument("--tests", required=True)
    ap.add_argument("--io")
    ap.add_argument("--show", action="store_true", help="print the first differing line of a failing file")
    a = ap.parse_args()
    task = surface.parse_file(a.task)
    io_path = Path(a.io) if a.io else Path(a.task).with_name(Path(a.task).stem + "_io.py")
    spec = importlib.util.spec_from_file_location("problem_io", io_path)
    io = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(io)
    ins = sorted(Path(a.tests).glob("*.in.txt"))
    if not ins:
        raise SystemExit(f"judge: no *.in.txt under {a.tests}")
    passed = skipped = 0
    with tempfile.TemporaryDirectory(prefix="t-judge-") as tmp:
        call = compile_task(task, Path(tmp))
        for f in ins:
            text = f.read_text(encoding="utf-8", errors="replace")
            want = f.with_name(f.name.replace(".in.txt", ".out.txt")).read_text(encoding="utf-8", errors="replace")
            calls = [tuple(c) for c in io.cases(text)]
            results = run_cases(call, calls)
            got = io.render(text, list(zip(calls, results)))
            g, w = _norm(got), _norm(want)
            if w == ["Sorry! Output limit exceeded!"]:      # uDebug's placeholder: the judge never stored this output
                skipped += 1
                print(f"{f.name}: SKIP (uDebug kept no expected output: 'Output limit exceeded'; {len(calls)} calls ran)")
                continue
            ok = g == w
            passed += ok
            print(f"{f.name}: {'PASS' if ok else 'FAIL'} ({len(calls)} calls, {len(w)} lines)")
            if not ok and a.show:
                i = next((i for i in range(max(len(g), len(w))) if i >= len(g) or i >= len(w) or g[i] != w[i]), 0)
                print(f"  line {i + 1}: got  {g[i] if i < len(g) else '<none>'!r}")
                print(f"  line {i + 1}: want {w[i] if i < len(w) else '<none>'!r}")
    print(f"{passed}/{len(ins) - skipped} test files match the judge's output" + (f" ({skipped} without a stored output)" if skipped else ""))
    return 0 if passed == len(ins) - skipped else 1


if __name__ == "__main__":
    sys.exit(main())
