#!/usr/bin/env python3
"""t/refute_at.py: refute a task's own body at an input you name, in every kernel.

A finding states a PX4 function with the contract it needs and without the guard PX4's callers do not establish
(t/flight/findings/). verify refutes such a body at whatever input the bounded search reaches first, and only when a
twin exists. This tool takes the input instead: the one a real message carries, such as a SERIAL_CONTROL count of 71
against its 70-byte field. The interpreter runs the body there. It produces a `value` witness (the ensures is false)
or an `undefined` one (an index out of range, or a method called outside its requires), in the shape
harness.real_witness gives. Each kernel's own certificate builder then lowers the body with that witness. As
everywhere in t, REFUTED is minted only by the kernel accepting the certificate.

  python3 t/refute_at.py TASK.t --at '{"count": 71, "data": [0, ...]}' [--kernels dafny,framac] [--json]
  python3 t/refute_at.py --all DIR --table TABLE.md     # every task in DIR/real_inputs.json, at its real input

An argument written as a list is a seq (or array). A value written {"fill": N, "len": L} is a seq of L copies of N,
so a 70-byte field need not be spelled out.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness  # noqa: E402
import interp  # noqa: E402
import run_par  # noqa: E402
import tasks_io  # noqa: E402


def _value(v):
    if isinstance(v, dict) and set(v) == {"fill", "len"}:
        return tuple([v["fill"]] * v["len"])
    if isinstance(v, list):
        return tuple(_value(x) for x in v)
    return v


def witness_at(task: dict, env0: dict) -> dict | None:
    """The refuting witness at env0, or None when the body meets its contract there. Raises ValueError when env0
    does not satisfy `requires`: a refutation outside the contract's domain says nothing."""
    harness._set_ctx(task)
    funs = interp.funs_of(task, task["body"])
    if not all(interp.ev(c, env0, funs, interp.St()) for c in task.get("requires", [])):
        raise ValueError("the input does not satisfy `requires`")
    ret = task["returns"][0]["name"]
    env = dict(env0)
    env[ret] = None
    arrays = [p["name"] for p in task["params"] if p["type"] == "array"]
    if arrays:
        env[interp.OLD_KEY] = {a: env0[a] for a in arrays}       # SPEC.md "Heap (v1)": old(...) reads the entry values
    try:
        interp.exec_body(task["body"], env, funs, interp.St(check_measures=True))
    except interp.Undef as u:
        w = interp._shown(env0)
        w.update(_kind="undefined", _real="no value", _twin=str(u), _ens=True)
        return w
    for c in task["ensures"]:
        if not interp.ev(c, env, funs, interp.St()):
            w = interp._shown(env0)
            w.update(_kind="value", _real=interp._j(env[ret]), _twin=interp._j(env[ret]), _ens=True)
            return w
    return None


def refute(task: dict, w: dict, kernels: list[str]) -> dict:
    """kernel -> outcome of the body lowered with witness w (REFUTED when the kernel accepts the certificate)."""
    out = {}
    with tempfile.TemporaryDirectory(prefix="t-refute-") as d:
        for bname, lmod, suffix in run_par.BACKENDS:
            if bname not in kernels:
                continue
            try:
                src = importlib.import_module(lmod).lower(task, task["body"], witness=w)
            except NotImplementedError as e:
                out[bname] = f"abstain: {e}"
                continue
            path = Path(d) / f"{task['name']}.{suffix}"
            path.write_text(src, encoding="utf-8", newline="\n")
            res = importlib.import_module(f"verifiers.{bname}").verify(path)
            out[bname] = str(res.outcome)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="refute_at.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("task", metavar="TASK.t", nargs="?")
    ap.add_argument("--at", help="the input, a JSON object of parameter values")
    ap.add_argument("--all", metavar="DIR", help="every task named in DIR/real_inputs.json, at its input")
    ap.add_argument("--table", metavar="PATH", help="with --all: write the verdicts as a markdown table")
    ap.add_argument("--kernels", default=",".join(b for b, _l, _s in run_par.BACKENDS))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    kernels = args.kernels.split(",")
    if args.all:
        manifest = json.loads((Path(args.all) / "real_inputs.json").read_text())
        rows = []
        for name, entry in manifest.items():
            task = tasks_io.load_task(str(Path(args.all) / f"{name}.t"))
            env0 = {k: _value(v) for k, v in entry["input"].items()}
            w = witness_at(task, env0)
            outcomes = refute(task, w, kernels) if w else {k: "not refuted" for k in kernels}
            n = sum(1 for o in outcomes.values() if o.lower().startswith("refuted"))
            print(f"{name}: {n}/{len(kernels)} refuted at {entry['input']}", flush=True)
            rows.append((name, entry, w, outcomes, n))
        if args.table:
            lines = ["# PX4 findings refuted at real inputs", "",
                     "Each finding's own body, at the input a real PX4 message or buffer carries "
                     "(t/flight/findings/real_inputs.json), lowered with its refutation certificate in every "
                     "kernel (t/refute_at.py). REFUTED means the kernel accepted the certificate.", "",
                     "| finding | input | kind | " + " | ".join(kernels) + " | refuted |",
                     "|---|---|---|" + "---|" * len(kernels) + "---|"]
            for name, entry, w, outcomes, n in rows:
                lines.append(f"| {name} | {entry['why']} | {w['_kind'] if w else '-'} | "
                             + " | ".join(outcomes.get(k, '') for k in kernels) + f" | {n}/{len(kernels)} |")
            Path(args.table).write_text("\n".join(lines) + "\n")
        return 0
    if not args.task or not args.at:
        ap.error("TASK.t and --at are required without --all")
    task = tasks_io.load_task(args.task)
    env0 = {k: _value(v) for k, v in json.loads(args.at).items()}
    w = witness_at(task, env0)
    if w is None:
        print(f"{task['name']}: the body meets its contract at this input; nothing to refute")
        return 1
    outcomes = refute(task, w, kernels)
    if args.json:
        print(json.dumps({"task": task["name"], "witness": harness.witness(w), "kind": w["_kind"],
                          "outcomes": outcomes}))
    else:
        print(f"{task['name']}: {w['_kind']} witness, {harness.witness(w)}")
        for k, o in outcomes.items():
            print(f"  {k}: {o}")
    return 0 if all(o.lower().startswith("refuted") or o.startswith("abstain") for o in outcomes.values()) else 2


if __name__ == "__main__":
    sys.exit(main())
