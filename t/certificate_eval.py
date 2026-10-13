"""certificate_eval.py: replay certificates on this machine, and forge each one three ways to see that none of the
forgeries passes (V2 and V3 of t/PREDICT-2026-10-05-verify-python.md).

    python3 t/certificate_eval.py CERT.json [CERT.json ...] --out report.json [--kernels dafny] [--jobs 2]

A certificate (t/certificate.py) is an in-toto Statement whose digests any editor can take again, so a digest
proves nothing about the content: what makes an altered certificate fail is the replay. Each forgery here changes
one thing and takes every digest again, so only the content is wrong:

  twin      the program's body replaced by the gate's own sabotaged twin of it (harness.twin_for: a near miss by
            construction, with an input at which it breaks the specification)
  spec      every `ensures` replaced by one that says nothing (`r == r`), the body and the recorded measurements kept
  python    the recorded Python made to answer one off: an integer one more, a truth value flipped, a list without
            its last element (or with one more when it is empty), a string with one more character

Testing a checker by planting faults in what it checks is mutation analysis (DeMillo, Lipton and Sayward, "Hints
on Test Data Selection", IEEE Computer, 1978; https://en.wikipedia.org/wiki/Mutation_testing); the twin is this
project's own (t/SPEC.md, "The twins"). No model is asked anything. Research receipt 06f32a851111.
"""
from __future__ import annotations

import argparse
import ast
import copy
import functools
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import certificate  # noqa: E402
import harness  # noqa: E402
import spec_check  # noqa: E402
import surface  # noqa: E402
from answer import prove  # noqa: E402

FORGERIES = ("twin", "spec", "python")
BUMP = '''
def _t_one_off(v):
    if isinstance(v, bool):
        return not v
    if isinstance(v, int):
        return v + 1
    if isinstance(v, str):
        return v + "x"
    if isinstance(v, (list, tuple)):
        return type(v)(v[:-1]) if v else type(v)((0,))
    return v
'''


def redigest(cert: dict) -> dict:
    """The same certificate with every digest taken again from what it now carries."""
    cert["subject"] = [{"name": name, "digest": {"sha256": certificate.digest(text)}}
                       for name, text in certificate._artifacts(cert["predicate"])]
    return cert


def _parsed(predicate: dict) -> tuple[dict | None, str]:
    """(the program parsed, "") or (None, why it does not parse). A certificate under evaluation may carry anything,
    and a program the parser rejects is a forgery that cannot be made, reported beside the replay, not an abort."""
    try:
        return surface.parse(predicate["program"]), ""
    except Exception as e:  # noqa: BLE001 - whatever the parser raises on a rejected program is the note
        return None, f"the program does not parse: {str(e)[:200]}"


def _core_call(source: str) -> tuple[ast.Assign | None, str]:
    """The first `_t_result = _t_core(...)` statement of the recorded Python, found by parsing it, so that a string
    literal or a comment merely containing the text is never the place changed."""
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return None, f"the recorded Python does not parse: {e.msg} (line {e.lineno})"
    found = [n for n in ast.walk(tree)
             if isinstance(n, ast.Assign) and len(n.targets) == 1
             and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "_t_result"
             and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name) and n.value.func.id == "_t_core"]
    if not found:
        return None, "the recorded Python has no `_t_result = _t_core(...)` statement"
    return min(found, key=lambda n: (n.lineno, n.col_offset)), ""


def forge(cert: dict, how: str) -> tuple[dict | None, str]:
    """(the forged certificate, what was changed), or (None, why this one cannot be forged that way)."""
    out = copy.deepcopy(cert)
    predicate = out["predicate"]
    if how in ("twin", "spec"):
        task, why = _parsed(predicate)
        if task is None:
            return None, why
    if how == "twin":
        body, operator, _witness = harness.twin_for(task)
        if body is None:
            return None, f"the gate found no twin ({operator})"
        predicate["program"] = surface.print_task(dict(task, body=body))
        return redigest(out), f"the body is the gate's twin ({operator})"
    if how == "spec":
        r = task["returns"][0]["name"]
        nothing = surface.parse_expr(f"{r} == {r}")
        predicate["program"] = surface.print_task(dict(task, ensures=[nothing]))
        predicate["specification"] = certificate.spec_lines(predicate["program"])
        return redigest(out), f"every ensures replaced by `{r} == {r}`"
    if how == "python":
        python = predicate.get("python") or {}
        source = python.get("source") or ""
        if not source.strip():
            return None, "the certificate carries no Python"
        node, why = _core_call(source)
        if node is None:
            return None, why
        lines = source.splitlines(keepends=True)
        indent = lines[node.lineno - 1][:node.col_offset]
        if indent.strip():
            return None, "the recorded Python's core call shares its line with another statement"
        helper = "_t_one_off"                       # a name the recorded Python does not already use, so nothing of
        while helper in source:                     # its own is redefined by the forgery
            helper += "_"
        head, tail = lines[:node.end_lineno], lines[node.end_lineno:]
        if not head[-1].endswith("\n"):
            head[-1] += "\n"
        body = "".join(head) + f"{indent}_t_result = {helper}(_t_result)\n" + "".join(tail)
        python["source"] = body + ("" if body.endswith("\n") else "\n") + BUMP.replace("_t_one_off", helper)
        return redigest(out), "the recorded Python answers one off"
    raise ValueError(how)


def evaluate(cert: dict, kernels: str = "dafny", jobs: int = 2) -> dict:
    """The verdict on the certificate as written and on each forgery of it."""
    prover = functools.partial(prove, kernels=kernels) if kernels else None

    def verdict(c: dict) -> dict:
        began = time.time()
        r = certificate.check(c, prover=prover, jobs=jobs)
        stopped = next((f"{s['what']}: {s['detail']}" for s in r["steps"] if s["result"] == certificate.BAD), "")
        return {"verdict": r["verdict"], "stopped at": stopped[:300], "proved here": r["proved here"], "seconds": round(time.time() - began, 1)}
    out = {"function": cert["predicate"].get("function"), "kind": cert["predicate"].get("kind"), "as written": verdict(cert), "forged": {}}
    for how in FORGERIES:
        forged, note = forge(cert, how)
        out["forged"][how] = {"made": False, "note": note} if forged is None else dict(verdict(forged), made=True, note=note)
    return out


def summarize(rows: list[dict]) -> dict:
    out = {"certificates": len(rows), "as written": {}, "forged": {how: {} for how in FORGERIES}}
    for r in rows:
        v = r["as written"]["verdict"]
        out["as written"][v] = out["as written"].get(v, 0) + 1
        for how in FORGERIES:
            f = r["forged"][how]
            key = f["verdict"] if f["made"] else "could not be forged"
            out["forged"][how][key] = out["forged"][how].get(key, 0) + 1
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--kernels", default="dafny", help="replay with these provers only (default: dafny, a fresh install's)")
    ap.add_argument("--jobs", type=int, default=2)
    a = ap.parse_args(argv)
    os.environ.setdefault("T_MIN_KERNELS", "1")
    unknown = [k for k in a.kernels.split(",") if k and k not in spec_check.KERNELS]
    if unknown:
        raise SystemExit(f"certificate_eval: no prover is called {unknown[0]}")
    if any(f.resolve() == a.out.resolve() for f in a.files):
        raise SystemExit(f"certificate_eval: --out {a.out} is also an input; nothing was written")
    certs = [(f, json.loads(f.read_text(encoding="utf-8"))) for f in a.files]   # every input read before any write
    rows = []
    for f, cert in certs:
        row = dict(evaluate(cert, a.kernels, a.jobs), file=f.name)
        rows.append(row)
        print(f"{f.name}: as written {row['as written']['verdict']}; " + "; ".join(
            f"{how} {row['forged'][how].get('verdict', 'not forged')}" for how in FORGERIES), flush=True)
        a.out.write_text(json.dumps({"summary": summarize(rows), "rows": rows}, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summarize(rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
