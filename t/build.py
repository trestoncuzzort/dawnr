#!/usr/bin/env python3
"""t/build.py: ship what was proved (programme R4, internal/RESEARCH-2026-10-07-zoom-out.md section 8).

A kernel proves a lowering of the routine; a backend and a toolchain then turn that lowering into a program that
runs. Neither step is verified (receipt cdec03946087: Dafny's backends and the target toolchains are in its trusted
base). This module compiles the proven lowerings, runs each executable on the task's domain points, and compares
every result with t's interpreter:

- **c:** the Frama-C lowering is C with its ACSL in comments. A generated `main` calls the routine on each point,
  and gcc builds it with `-ffp-contract=off`, so every float operation rounds once, as t's semantics says.
  Sequences go in as an array and a length; a sequence result comes back in a buffer the size its own `requires`
  states.
- **dafny-py:** the Dafny lowering with a generated `Main`, compiled by Dafny's Python backend.

A disagreement is a finding about a lowering, a backend or a toolchain, never about the kernel's proof. Agreement is
evidence on the domain points run, not a proof.

  python3 t/build.py t/tasks --target c --jobs 4 --table BUILD-C.md
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness  # noqa: E402
import interp  # noqa: E402
import tasks_io  # noqa: E402
import tlib  # noqa: E402
from verifiers.discover import find  # noqa: E402

POINTS = 40
DAFNY = find("T_DAFNY", ["dafny"], [".local/dafny/dafny"])
SCALAR = ("int", "bool", "float")


class Unsupported(Exception):
    pass


def _points(ref) -> list:
    """Up to POINTS domain points, spread evenly over the interpreter's list, with their real values and heaps."""
    pts = list(enumerate(ref.points))
    if len(pts) > POINTS:
        step = len(pts) / POINTS
        pts = [pts[int(i * step)] for i in range(POINTS)]
    return pts


def _supported(task: dict, kinds: tuple) -> None:
    for p in task["params"]:
        if p["type"] not in kinds:
            raise Unsupported(f"parameter type {p['type']!r}")
    rt = task["returns"][0]["type"]
    if rt not in kinds or rt == "array":
        raise Unsupported(f"result type {rt!r}")


# ---------------------------------------------------------------------------- c

def _c_lit(v):
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, float):
        return v.hex()
    return str(int(v))


def _c_expect(task, val, heap) -> str:
    rt = task["returns"][0]["type"]
    out = (f"{len(val)}:" + "".join(f" {int(x)}" for x in val)) if rt == "seq" else (
        val.hex() if rt == "float" else str(int(val)))
    for p in task["params"]:
        if p["type"] == "array":
            out += " |" + "".join(f" {int(x)}" for x in heap[p["name"]])
    return out


def _capacity(src: str, name: str, env: dict) -> int | None:
    """The size a buffer's own `requires` gives it (`X_n == E` or `X_n >= E`), evaluated at the call's values."""
    for m in re.finditer(rf"requires\s+\(?{name}_n\s*(==|>=)\s*([^;]+);", src):
        try:
            return int(eval(m.group(2).replace("\\length", "len"), {"__builtins__": {}}, dict(env)))
        except Exception:                              # noqa: BLE001
            continue
    return None


def c_program(task: dict, ref, pts, wide: bool = False) -> tuple[str, list]:
    """The C lowering and a `main` that calls it at each point. The call is built from the C signature itself:
    t's data parameters and their lengths, the result's buffer, and a scratch buffer for each sequence local
    (SPEC.md T31: the caller provides it), each sized by its own `requires`. With `wide`, C's `int` is 64 bits."""
    _supported(task, ("int", "bool", "seq", "array", "float"))
    src = tlib.lower(task, "framac")
    fn = re.search(r"^(?:int|double|_Bool)\s+(\w+_t)\(([^)]*)\)\s*\{", src, re.M)
    if not fn:
        raise Unsupported("no C function in the lowering")
    name = fn.group(1)
    cparams = [x.strip().rsplit(None, 1)[-1].lstrip("*") for x in fn.group(2).split(",") if x.strip()]
    # the names pass renames a C keyword (`char` -> `t_char`) and says so in a comment: read C names back as t's
    back = {}
    m = re.search(r"t renames:\s*([^\n*]*)", src)
    if m:
        for pair in m.group(1).split(","):
            if "->" in pair:
                old_n, new_n = (x.strip() for x in pair.split("->"))
                back[new_n] = old_n
                back[new_n + "_n"] = old_n + "_n"
    rt, rname = task["returns"][0]["type"], task["returns"][0]["name"]
    ptypes = {p["name"]: p["type"] for p in task["params"]}
    lines, expect = [], []
    for k, (idx, (env0, real)) in enumerate(pts):
        env = ref._start(env0)
        scal = {n: (len(v) if isinstance(v, tuple) else v) for n, v in env.items() if n in ptypes}
        lens = dict(scal)
        for n, v in env.items():
            if n in ptypes and ptypes[n] in ("seq", "array"):
                lens[f"{n}_n"] = len(v)
        decl, args = [], []
        for cp0 in cparams:
            cp = back.get(cp0, cp0)
            base = cp[:-2] if cp.endswith("_n") else None
            if cp in ptypes and ptypes[cp] in ("seq", "array"):
                vals = list(env[cp])
                decl.append(f"t_int {cp}_{k}[{max(len(vals), 1)}] = {{{', '.join(_c_lit(x) for x in vals) or '0'}}};")
                args.append(f"{cp}_{k}")
            elif cp in ptypes:
                args.append(_c_lit(env[cp]))
            elif base in ptypes:
                args.append(str(len(env[base])))
            elif cp.endswith("_n"):
                args.append(str(lens[f"{base}_cap"]))
            else:
                cap = _capacity(src, cp, lens)
                if cap is None:
                    cap = len(real) if cp == rname and rt == "seq" else 4096
                if cp == rname and rt == "seq":
                    cap = max(cap, len(real))
                lens[f"{cp}_cap"] = cap
                decl.append(f"t_int {cp}_{k}[{max(cap, 1)}];")
                args.append(f"{cp}_{k}")
        call = f"{name}({', '.join(args)})"
        if rt == "seq":
            show = (f"long n_{k} = {call}; printf(\"%ld:\", n_{k}); "
                    f"for (long i = 0; i < n_{k}; i++) printf(\" %ld\", (long){rname}_{k}[i]);")
        elif rt == "float":
            show = f"printf(\"%a\", {call});"
        else:
            show = f"printf(\"%ld\", (long)({call}));"
        for p in task["params"]:
            if p["type"] == "array":
                show += (f" printf(\" |\"); for (long i = 0; i < {len(env[p['name']])}; i++) "
                         f"printf(\" %ld\", (long){p['name']}_{k}[i]);")
        lines.append("  { " + " ".join(decl) + " " + show + " printf(\"\\n\"); }")
        heap = dict((n, env[n]) for n in ptypes if ptypes[n] == "array")
        if ref.mods:
            heap.update(ref.heaps[idx])
        expect.append(_c_expect(task, real, heap))
    head = "#include <stdio.h>\n#include <stdlib.h>\n"
    if wide:
        head += "typedef long t_int;\n#define int long\n" + src + "\n#undef int\n"
    else:
        head += "typedef int t_int;\n" + src + "\n"
    return head + "int main(void) {\n" + "\n".join(lines) + "\n  return 0;\n}\n", expect


def _norm_float(line: str) -> str:
    """gcc prints `%a` its own way; compare floats by value."""
    try:
        return float.fromhex(line).hex()
    except ValueError:
        return line


def run_c(prog: str, work: Path) -> list:
    c, exe = work / "prog.c", work / "prog"
    c.write_text(prog, encoding="utf-8")
    p = subprocess.run(["gcc", "-std=c11", "-O1", "-ffp-contract=off", "-w", "-o", str(exe), str(c), "-lm"],
                       capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        raise RuntimeError("compile: " + (p.stderr.strip().splitlines() or ["?"])[0][:200])
    p = subprocess.run([str(exe)], capture_output=True, text=True, timeout=60)
    if p.returncode != 0:
        raise RuntimeError(f"run: exit {p.returncode}")
    return p.stdout.splitlines()


# ---------------------------------------------------------------------- dafny-py

def _d_lit(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (tuple, list)):
        return "[" + ", ".join(_d_lit(x) for x in v) + "]"
    return str(int(v))


def _d_show(v) -> str:
    if isinstance(v, interp.Pair):
        return f"({_d_show(v.a)}, {_d_show(v.b)})"
    return _d_lit(v)


def dafny_program(task: dict, ref, pts) -> tuple[str, list]:
    _supported(task, ("int", "bool", "seq", "array"))
    src = tlib.lower(task, "dafny")
    m = re.search(r"^method\s+(\w+)\(", src, re.M)
    if not m:
        raise Unsupported("no method in the lowering")
    name = m.group(1)
    lines, expect = [], []
    for k, (idx, (env0, real)) in enumerate(pts):
        env = ref._start(env0)
        args, arrs = [], []
        for p in task["params"]:
            v = env[p["name"]]
            if p["type"] == "array":
                lines.append(f"  var {p['name']}_{k} := new int[] {_d_lit(v)};")
                args.append(f"{p['name']}_{k}")
                arrs.append(f"{p['name']}_{k}[..]")
            else:
                args.append(_d_lit(v))
        lines.append(f"  var r_{k} := {name}({', '.join(args)});")
        lines.append(f"  print r_{k}" + "".join(f", \" | \", {a}" for a in arrs) + ", \"\\n\";")
        heap = {p["name"]: env[p["name"]] for p in task["params"] if p["type"] == "array"}
        if ref.mods:
            heap.update(ref.heaps[idx])
        expect.append(_d_show(real) + "".join(f" | {_d_lit(heap[p['name']])}" for p in task["params"]
                                              if p["type"] == "array"))
    return src + "\nmethod Main() {\n" + "\n".join(lines) + "\n}\n", expect


def run_dafny(prog: str, work: Path, target: str = "py") -> list:
    f = work / "prog.dfy"
    f.write_text(prog, encoding="utf-8")
    p = subprocess.run([DAFNY, "run", "--no-verify", "--target", target, str(f)], capture_output=True, text=True,
                       timeout=300, cwd=str(work))
    if p.returncode != 0:
        raise RuntimeError("dafny run: " + ((p.stdout + p.stderr).strip().splitlines() or ["?"])[-1][:200])
    return [ln for ln in p.stdout.splitlines() if ln and not ln.startswith("Dafny program verifier")]


TARGETS = {"c": (c_program, run_c), "c64": (lambda t, r, p: c_program(t, r, p, wide=True), run_c),
           "dafny-py": (dafny_program, run_dafny)}


def build_file(path: str, target: str) -> dict:
    res = {"file": path, "target": target}
    try:
        task = tasks_io.load_task(path)
    except Exception as e:                              # noqa: BLE001
        res.update(name=Path(path).stem, status=f"load-error: {type(e).__name__}")
        return res
    res["name"] = task.get("name", Path(path).stem)
    make, run = TARGETS[target]
    try:
        harness._set_ctx(task)
        ref = interp.Reference(task)
        pts = _points(ref)
        if not pts:
            res["status"] = "no-input"
            return res
        prog, expect = make(task, ref, pts)
        with tempfile.TemporaryDirectory(prefix="t-build-") as d:
            got = run(prog, Path(d))
    except Unsupported as e:
        res["status"] = f"not built: {e}"
        return res
    except NotImplementedError as e:
        res["status"] = "not built: the lowering refuses it"
        return res
    except Exception as e:                              # noqa: BLE001
        res["status"] = f"error: {type(e).__name__}: {e}"[:240]
        return res
    norm = _norm_float if task["returns"][0]["type"] == "float" else (lambda x: x)
    got = [norm(g.strip()) for g in got]
    bad = [(i, e, g) for i, (e, g) in enumerate(zip(expect, got)) if e != g]
    res["points"] = len(expect)
    res["status"] = "agrees" if len(got) == len(expect) and not bad else "DISAGREES"
    if target in ("c", "c64") and len(got) == len(expect) and bad:
        # C's int is 32 bits; the Frama-C proof's integers are mathematical (WP's Typed+nat, pinned because t's are).
        # A point whose inputs or expected outputs leave int32 is the width gap, not a lowering bug.
        wide = {i for i, (idx, (env0, real)) in enumerate(pts) if not _fits32(env0) or not _fits32(real)}
        res["beyond_int32"] = len(wide)
        if all(i in wide for i, _e, _g in bad):
            res["status"] = "agrees within int32"
            res["first"] = None
    if res["status"] != "agrees":
        i, e, g = (bad[0] if bad else (len(got), "(a line)", "(none)"))
        env0 = pts[i][1][0] if i < len(pts) else {}
        res["first"] = {"input": {k: interp._j(v) for k, v in env0.items()}, "expected": e, "got": g}
    return res


def _fits32(v) -> bool:
    if isinstance(v, bool) or isinstance(v, float):
        return True
    if isinstance(v, int):
        return -2 ** 31 <= v < 2 ** 31
    if isinstance(v, (tuple, list)):
        return all(_fits32(x) for x in v) and len(v) < 2 ** 31
    if isinstance(v, dict):
        return all(_fits32(x) for x in v.values())
    if isinstance(v, interp.Pair):
        return _fits32(v.a) and _fits32(v.b)
    return True


def table(results: list, target: str) -> str:
    built = [r for r in results if r.get("status") in ("agrees", "agrees within int32", "DISAGREES")]
    agree = [r for r in built if r["status"] == "agrees"]
    agree32 = [r for r in built if r["status"] == "agrees within int32"]
    lines = [f"# Built and run: {target}", "",
             "Each task's proven lowering, compiled with its own toolchain and run on up to "
             f"{POINTS} domain points; every result compared with t's interpreter (t/build.py).", "",
             f"- tasks: {len(results)}; built and run: {len(built)}; agree on every point: {len(agree)}; "
             f"agree on every point inside int32 and differ only beyond it: {len(agree32)}; disagree: "
             f"{len(built) - len(agree) - len(agree32)}; points run: {sum(r.get('points', 0) for r in built)}", "",
             "| task | status | points | first disagreement |", "|---|---|---|---|"]
    for r in sorted(results, key=lambda r: r["name"]):
        first = json.dumps(r["first"]).replace("|", "\\|") if r.get("first") else ""
        lines.append(f"| {r['name']} | {r['status'].replace('|', chr(92) + '|')} | {r.get('points', '')} | {first} |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="build.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("target_path", metavar="FILE|DIR")
    ap.add_argument("--target", choices=sorted(TARGETS), default="c")
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--table", metavar="PATH")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    t = Path(args.target_path)
    files = [str(p) for p in sorted(t.iterdir()) if p.suffix in (".t", ".json")] if t.is_dir() else [str(t)]
    if args.jobs > 1:
        with ProcessPoolExecutor(max_workers=args.jobs) as ex:
            results = list(ex.map(build_file, files, [args.target] * len(files)))
    else:
        results = [build_file(f, args.target) for f in files]
    for r in results:
        print(json.dumps(r, sort_keys=True) if args.json else
              f"{r['name']}: {r['status']}" + (f" ({r['points']} points)" if r.get("points") else "")
              + (f" first: {r['first']}" if r.get("first") else ""))
    if args.table:
        Path(args.table).write_text(table(results, args.target), encoding="utf-8", newline="\n")
    return 1 if any(r.get("status") == "DISAGREES" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
