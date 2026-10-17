#!/usr/bin/env python3
"""t/spec_propose.py: propose strengthenings for under-constrained specifications with a model,
each verified by spec_refine.check (ExVerus arXiv:2603.25810, SpecSyn arXiv:2604.21570).

The model sees the spec + body (surface.print_task) and the surviving mutants with their separating
witnesses, and proposes t boolean expressions. Each is parsed with surface.parse_expr into an
`ensures` conjunct and run through spec_refine.check; a proposal is KEPT only if the gate accepts it
(the real body still verifies and strictly fewer behaviour-changing mutants survive). The model
proposes; the interpreter gate decides -- nothing the model emits is trusted without the gate.

Model backend: `~/.local/bin/fable` (Fable on the Console API credits) by default. Source:
SpecSyn arXiv:2604.21570, ExVerus arXiv:2603.25810; internal/research/spec-validation.md;
research receipt af2adafc3215. Motivated by internal/E1-FINDINGS-2026-10-14.md.

Usage:
    python3 t/spec_propose.py <FILE|DIR> [--model-cmd CMD] [--max-exprs N] [--seconds S]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # t/ on path
import audit  # noqa: E402
import surface  # noqa: E402
import tasks_io  # noqa: E402
import spec_refine  # noqa: E402

FABLE = str(Path.home() / ".local" / "bin" / "fable")

PROMPT = """You are strengthening an under-constrained formal specification in the small language `t`.
A program is lowered into proof kernels; a `survivor` is a WRONG program that the current `ensures`
still accepts, shown with a witness input where the real program and the wrong one differ.

Here is the task (its `ensures` is too weak):

{printed}

Surviving wrong programs the current spec wrongly accepts (operator changed -> witness -> real output vs wrong output):
{survivors}

Propose boolean expressions in `t` (same syntax as the existing `ensures` lines, referring to the
parameters and `result`) that, ADDED as extra `ensures` conjuncts, would make the spec REJECT those
wrong programs while staying TRUE for the real program. Prefer the smallest, most general clause.

Output ONLY a JSON array of strings, each a single t boolean expression (no `ensures` keyword, no
prose). Example for an is-prime task that wrongly accepted result=true at k=1:
["result ==> k >= 2"]
"""


def _readable_survivors(path: str, seconds: int, limit: int = 8) -> list[str]:
    r = audit.audit_file(path, seconds=seconds)
    out = []
    for s in r.get("survivors", [])[:limit]:
        out.append(f"- {s.get('op')}: {s.get('change')}  ::  {s.get('witness')}")
    return out


def _extract_json_array(text: str):
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if not m:
        return []
    try:
        v = json.loads(m.group(0))
        return [str(x) for x in v] if isinstance(v, list) else []
    except ValueError:
        return []


def _call_model(prompt: str, model_cmd: str) -> str:
    try:
        p = subprocess.run(model_cmd.split() + ["--max", "1600"], input=prompt,
                           capture_output=True, text=True, timeout=600)
        return p.stdout
    except Exception as e:  # noqa: BLE001
        return f"(model call failed: {type(e).__name__}: {e})"


def propose(path: str, model_cmd: str = FABLE, max_exprs: int = 4, seconds: int = 20) -> dict:
    task = tasks_io.load_task(path)
    survs = _readable_survivors(path, seconds)
    name = task.get("name", Path(path).stem)
    if not survs:
        return {"name": name, "status": "no-survivors"}
    prompt = PROMPT.format(printed=surface.print_task(task), survivors="\n".join(survs))
    reply = _call_model(prompt, model_cmd)
    exprs = _extract_json_array(reply)[:max_exprs]
    parsed = []
    for e in exprs:
        try:
            parsed.append((e, surface.parse_expr(e)))
        except Exception:  # noqa: BLE001 - a malformed proposal is simply discarded
            continue
    # try each single clause, then the conjunction of all parsed clauses
    attempts = [([a], e) for e, a in parsed]
    if len(parsed) > 1:
        attempts.append(([a for _, a in parsed], " && ".join(e for e, _ in parsed)))
    for asts, label in attempts:
        try:
            c = spec_refine.check(task, asts)
        except Exception:  # noqa: BLE001
            continue
        if c.get("accepted"):
            return {"name": name, "status": "strengthened", "clause": label,
                    "strength_before": c["strength_before"], "strength_after": c["strength_after"],
                    "survivors_before": c["survivors_before"], "survivors_after": c["survivors_after"]}
    return {"name": name, "status": "no-proposal-passed",
            "proposed": [e for e, _ in parsed], "n_raw": len(exprs)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="spec_propose.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("target", metavar="FILE|DIR")
    ap.add_argument("--model-cmd", default=FABLE, help="command that reads a prompt on stdin")
    ap.add_argument("--max-exprs", type=int, default=4)
    ap.add_argument("--seconds", type=int, default=20)
    a = ap.parse_args(argv)
    target = Path(a.target)
    files = ([str(p) for p in sorted(target.iterdir()) if p.suffix in (".t", ".json")]
             if target.is_dir() else [str(target)])
    strengthened = 0
    for f in files:
        # only spend a model call where there is actually a gap
        quick = audit.audit_file(f, seconds=a.seconds)
        if quick.get("status") != "ok" or not quick.get("survivors"):
            continue
        r = propose(f, a.model_cmd, a.max_exprs, a.seconds)
        if r.get("status") == "strengthened":
            strengthened += 1
            print(f"[OK]   {r['name']}: +ensures {r['clause']}  "
                  f"(strength {r['strength_before']:.2f} -> {r['strength_after']:.2f}, "
                  f"survivors {r['survivors_before']} -> {r['survivors_after']})")
        else:
            print(f"[--]   {r['name']}: {r.get('status')}"
                  + (f"; proposed {r.get('proposed')}" if r.get("proposed") else ""))
    print(f"\nstrengthened {strengthened} under-constrained spec(s), all gate-verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
