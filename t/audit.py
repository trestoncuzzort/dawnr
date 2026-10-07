#!/usr/bin/env python3
"""t/audit.py: how much room a specification leaves for wrong programs (NORTH-STAR.md target 3, D8).

A kernel proves a program against its specification. Nothing in that proof says the specification can tell the
program from a wrong one. This audit asks, for one task or a directory of them: of the one-edit mutants of the
body (the twin ladder's extensional rungs, every one of them, not only the first), how many change what the routine
computes, and how many of those does the `ensures` catch?

Each mutant the checker accepts lands in exactly one class, decided by the interpreter over the task's bounded
input domain:
- **same**: it computes what the real body computes at every domain point (an equivalent mutant, or one that
  differs only outside the domain). Not evidence about the spec either way.
- **killed**: at some domain point its result falsifies `ensures` (or is undefined), so a sound kernel must refute
  it.
- **diverges**: it runs out of steps at a point where the real body terminates; a kernel rejects it on
  termination, so it says nothing about the postcondition.
- **survivor**: it computes a different result at some domain point, and its result satisfies `ensures` at every
  domain point. The spec cannot tell it from the real program. The witness is the input where the two differ.

A survivor is a gap in the postcondition, or a latitude the author intended (a spec that allows either of two
correct answers); the audit cannot tell those apart, and says so. With `--kernel`, each task's real body and its
first survivors are verified in that kernel: a survivor the kernel proves is a wrong program with a proof, the
strongest form of the finding. A survivor the kernel does not prove may still be a gap (its loop invariants may
simply not hold for the mutant), so kernel-proved counts are a lower bound.

Prior art (receipt 0139ee2dd35d): MutDafny (arXiv 2511.15403) mutates Dafny implementations and calls a mutant
alive when Dafny verifies it; over 118,458 mutants 30,459 were alive, and a manual triage of 284 found 157
equivalent. Here equivalence is decided by execution before any kernel runs, and a survivor is a postcondition
finding independent of loop invariants. Bounded domain only: a difference outside it is not seen.

  python3 t/audit.py t/tasks --jobs 4 --table AUDIT.md
  python3 t/audit.py DIR --kernel dafny --jobs 3 --json > audit.jsonl
"""
from __future__ import annotations

import argparse
import importlib
import json
import re
import signal
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness  # noqa: E402
import interp  # noqa: E402
import surface  # noqa: E402
import tasks_io  # noqa: E402
import tlib  # noqa: E402

TASK_SECONDS = 60      # one task's whole ladder; a task that runs out is reported as "timeout", never dropped
CONFIRM = 3            # survivors per task sent to the kernel, in ladder order, until one is proved


class _Out(Exception):
    pass


def _alarm(_signum, _frame):
    raise _Out()


def classify(task: dict) -> dict:
    """The task's mutants by class. `survivors` keeps each survivor's operator tag, body and witness."""
    res = {"name": task.get("name", "?"), "status": "ok", "mutants": 0, "same": 0, "killed": 0,
           "diverges": 0, "survivors": [], "ill_formed": 0,
           "capped": False}
    harness._set_ctx(task)
    ref = interp.Reference(task)
    if not ref.points:
        res["status"] = "no-input"
        return res
    if harness.real_witness(task) is not None:
        res["status"] = "real-violates-spec"   # the real body itself breaks its contract: nothing to audit against
        return res
    base_ok = not harness._ill_formed(task, task["body"])
    n = 0
    for op, gen in harness.EXTENSIONAL:
        for k, mut in enumerate(gen(task["body"], harness._scope(task))):
            n += 1
            if n > harness.MAX_CANDIDATES:
                res["capped"] = True
                break
            if base_ok and harness._ill_formed(task, mut):
                res["ill_formed"] += 1
                continue
            try:
                kind = _scan(ref, task, mut)
            except TypeError:
                res["ill_formed"] += 1   # the same guard as the twin ladder: an ill-typed candidate is no mutant
                continue
            res["mutants"] += 1
            if kind == "survivor":
                res["survivors"].append({"op": harness._tag(op, k), "body": mut, "witness": ref.witness(mut)})
            else:
                res[kind] += 1
        if res["capped"]:
            break
    return res


def _scan(ref, task: dict, mut: list) -> str:
    """One pass over the domain: "killed" at the first point whose result falsifies `ensures` (or has no value),
    "diverges" at the first point where the mutant runs out of steps (the real body terminated there, so a kernel
    rejects the mutant on termination, not on the spec), else "survivor" if it differed anywhere, else "same"."""
    funs = interp.funs_of(task, mut)
    differs = False
    for k, (env0, real) in enumerate(ref.points):
        env = ref._start(env0)
        try:
            interp.exec_body(mut, env, funs, interp.St())
            got = env[ref.ret]
        except interp.Undef:
            return "killed"
        except (interp.Budget, RecursionError):
            return "diverges"
        if got is None:
            return "killed"
        gh = ref._heap(env)
        if interp._tv(got) != interp._tv(real) or ref._heap_differs(gh, k):
            if ref._breaks_ensures(env0, got, gh):
                return "killed"
            differs = True
    return "survivor" if differs else "same"


def _changed_line(task: dict, mut: list) -> str:
    """The first line of the printed program the mutant changes, as `old` -> `new`; empty when unprintable."""
    try:
        a = surface.print_task(task).splitlines()
        b = surface.print_task({**task, "body": mut}).splitlines()
    except Exception:                                   # noqa: BLE001 (a lifted task the printer does not carry)
        return ""
    for x, y in zip(a, b):
        if x != y:
            return f"`{x.strip()}` -> `{y.strip()}`"
    return ""


def _kernel_verdict(task: dict, body: list, kernel: str, path: Path) -> str:
    lmod, _suffix = tlib._LOWER_MOD[kernel]
    try:
        src = importlib.import_module(lmod).lower({**task, "body": body}, body)
    except NotImplementedError:
        return "abstain"
    except Exception:                                   # noqa: BLE001
        return "lower-error"
    path.write_text(src, encoding="utf-8", newline="\n")
    return importlib.import_module(f"verifiers.{kernel}").verify(path).outcome


def audit_file(path: str, kernel: str | None = None, seconds: int = TASK_SECONDS, out_dir: str | None = None) -> dict:
    """One task file's audit as a JSON-ready dict (bodies dropped, each survivor's changed line and witness kept)."""
    try:
        task = tasks_io.load_task(path)
    except Exception as e:                              # noqa: BLE001
        return {"file": path, "name": Path(path).stem, "status": f"load-error: {type(e).__name__}"}
    old = signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(seconds)
    try:
        res = classify(task)
    except _Out:
        res = {"name": task.get("name", "?"), "status": "timeout"}
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)
    res["file"] = path
    survivors = res.get("survivors", [])
    if kernel and res["status"] == "ok":
        work = Path(out_dir or tempfile.mkdtemp(prefix="t-audit-"))
        work.mkdir(parents=True, exist_ok=True)
        _lmod, suffix = tlib._LOWER_MOD[kernel]
        stem = re.sub(r"[^A-Za-z0-9_]", "_", Path(path).stem)
        res["kernel"] = kernel
        res["real_verdict"] = _kernel_verdict(task, task["body"], kernel, work / f"{stem}.{suffix}")
        if res["real_verdict"] == "verified":
            for i, s in enumerate(survivors[:CONFIRM]):
                s["verdict"] = _kernel_verdict(task, s["body"], kernel, work / f"{stem}_survivor{i}.{suffix}")
                if s["verdict"] == "verified":
                    break
    for s in survivors:
        s["change"] = _changed_line(task, s["body"])
        s["witness"] = harness.witness(s["witness"])
        del s["body"]
    res["proved_survivors"] = sum(1 for s in survivors if s.get("verdict") == "verified")
    return res


def _row(r: dict) -> str:
    if r["status"] != "ok":
        return f"| {r['name']} | {r['status']} | | | | | | |"
    sv = r["survivors"]
    ex = ""
    if sv:
        s = next((s for s in sv if s.get("verdict") == "verified"), sv[0])
        ex = f"{s['op']}: {s['change']} at {s['witness']}".replace("|", "\\|")
    proved = str(r["proved_survivors"]) if "kernel" in r and r.get("real_verdict") == "verified" else (
        f"(real {r['real_verdict']})" if "kernel" in r else "")
    return (f"| {r['name']} | {r['mutants']} | {r['killed']} | {r['same']} | {r['diverges']} | {len(sv)} | {proved} "
            f"| {ex} |")


def table(results: list[dict], kernel: str | None) -> str:
    ok = [r for r in results if r["status"] == "ok"]
    with_sv = [r for r in ok if r["survivors"]]
    changing = sum(r["killed"] + len(r["survivors"]) for r in ok)
    killed = sum(r["killed"] for r in ok)
    lines = ["# Specification audit", "",
             "Every one-edit mutant of each body, classed by the interpreter over the task's bounded domain "
             "(t/audit.py): **killed** (the spec rejects its result somewhere), **same** (computes the same "
             "everywhere), **diverges** (runs out of steps where the real body ends), **survivor** (computes something different, and the spec accepts it everywhere).", "",
             f"- tasks: {len(results)}; audited: {len(ok)}; not audited: "
             + (", ".join(f"{n} {s}" for s, n in sorted(_count(r['status'] for r in results if r['status'] != 'ok').items()))
                or "none"),
             f"- behaviour-changing mutants the specs kill: {killed} of {changing}"
             + (f" ({100 * killed / changing:.1f}%)" if changing else ""),
             f"- tasks whose spec admits a survivor: {len(with_sv)} of {len(ok)}"]
    if kernel:
        real_ok = [r for r in ok if r.get("real_verdict") == "verified"]
        proved = [r for r in real_ok if r["proved_survivors"]]
        lines.append(f"- {kernel}: real body verified in {len(real_ok)} of {len(ok)}; of those, a survivor "
                     f"proved too (a wrong program with a proof) in {len(proved)}")
    lines += ["", "| task | mutants | killed | same | diverges | survivors | proved by the kernel "
              "| a survivor: change at input |", "|---|---|---|---|---|---|---|---|"]
    lines += [_row(r) for r in sorted(results, key=lambda r: r["name"])]
    return "\n".join(lines) + "\n"


def _count(xs) -> dict:
    out: dict = {}
    for x in xs:
        out[x] = out.get(x, 0) + 1
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="audit.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("target", metavar="FILE|DIR")
    ap.add_argument("--kernel", help="verify each real body and its first survivors in this kernel")
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--seconds", type=int, default=TASK_SECONDS, help="interpreter budget per task")
    ap.add_argument("--table", metavar="PATH", help="write the Markdown table here")
    ap.add_argument("--out", metavar="DIR", help="where kernel sources are written")
    ap.add_argument("--json", action="store_true", help="one JSON line per task on stdout")
    args = ap.parse_args(argv)
    if args.kernel and args.kernel not in tlib._LOWER_MOD:
        print(f"audit.py: unknown kernel {args.kernel!r}, known: {sorted(tlib._LOWER_MOD)}", file=sys.stderr)
        return 2
    target = Path(args.target)
    files = ([str(p) for p in sorted(target.iterdir()) if p.suffix in (".t", ".json")] if target.is_dir()
             else [str(target)])
    run = [(f, args.kernel, args.seconds, args.out) for f in files]
    if args.jobs > 1:
        with ProcessPoolExecutor(max_workers=args.jobs) as ex:
            results = list(ex.map(audit_file, *zip(*run)))
    else:
        results = [audit_file(*r) for r in run]
    for r in results:
        if args.json:
            print(json.dumps(r, sort_keys=True))
        elif r["status"] != "ok":
            print(f"{r['name']}: {r['status']}")
        else:
            sv = r["survivors"]
            line = (f"{r['name']}: {r['mutants']} mutants, {r['killed']} killed, {r['same']} same, "
                    f"{r['diverges']} diverge, {len(sv)} survivor(s)")
            first = next((s for s in sv if s.get("verdict") == "verified"), sv[0] if sv else None)
            if first:
                line += f"; {first['op']} {first['change']} at {first['witness']}"
            if "kernel" in r:
                line += f"\n  {r['kernel']}: real {r['real_verdict']}"
                if first and first.get("verdict"):
                    line += f", this survivor {first['verdict']}" + (
                        " (a different program, proved against the same spec)" if first["verdict"] == "verified" else "")
            print(line)
    if args.table:
        Path(args.table).write_text(table(results, args.kernel), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
