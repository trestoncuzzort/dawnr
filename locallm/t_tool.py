"""t_tool.py: dawnr's first tool, the t interpreter, called by the model on its own draft.

nanochat's engine (https://github.com/karpathy/nanochat, nanochat/engine.py)
lets the model write <|python_start|> expr <|python_end|>, evaluates the
expression with a restricted eval under a 3-second alarm, and forces the
result back into the stream between <|output_start|> and <|output_end|>.
dawnr's tool is the fastest part of the proof engine instead: the draft t
program is parsed (t/surface.py), type checked (the same check_wf the RL
reward and the grader use), and run in t's interpreter (t/interp.py) on every
`Example:` line the user gave, and the tool answers with the verdicts. It is
the standard library only, runs in-process, and needs no alarm: the
interpreter has its own step budget (interp.Budget).

What the tool answers, one line each, stopping at the first failure:

    parses: yes | parses: no: <why>
    well formed: yes | well formed: no: <why>
    example 1: pass | example 1: fail: got 5, expected 6 | example 1: <verdict>: <why>

Values compare as JSON (true is not 1), the way the grader keeps int and bool
apart (interp._tv).

examples_from_program() computes Example lines from a PROVED program: inputs
from the interpreter's own ladders over the task's literals (interp.domain),
kept where the task's `requires` holds, and the program's output on them.
Seven kernels proved that program meets its specification, so each line is a
true statement about the specification, not a guess.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

T = Path(__file__).resolve().parents[1] / "t"
if str(T) not in sys.path:
    sys.path.insert(0, str(T))

EXAMPLE = re.compile(r"^Example:\s*([A-Za-z_][A-Za-z0-9_]*)\((.*)\)\s*==\s*(.+?)\s*$", re.M)
MAX_WHY = 160
RUNNABLE_TYPES = ("int", "bool", "seq")


def _short(text: str) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= MAX_WHY else text[:MAX_WHY - 3] + "..."


def parse_examples(text: str) -> list[dict]:
    """Every `Example: f(a, b) == v` line in text, as {"fn", "args", "expected", "line"}.
    A line whose values are not JSON is kept with "error", so the tool can say so."""
    out = []
    for m in EXAMPLE.finditer(text or ""):
        row = {"fn": m.group(1), "line": m.group(0).strip()}
        try:
            row["args"] = json.loads("[" + m.group(2) + "]")
            row["expected"] = json.loads(m.group(3))
        except ValueError as e:
            row["error"] = f"not JSON: {e}"
        out.append(row)
    return out


def _value(ty: str, v):
    """A JSON value as the interpreter holds a value of t type `ty` (a seq is a tuple, rows too)."""
    if ty == "seq":
        if isinstance(v, str):
            return tuple(ord(c) for c in v)
        if not isinstance(v, list):
            raise TypeError(f"expected a list for a seq, got {json.dumps(v)}")
        return tuple(_value("seq", x) if isinstance(x, (list, str)) else x for x in v)
    if ty == "bool":
        if not isinstance(v, bool):
            raise TypeError(f"expected a bool, got {json.dumps(v)}")
        return v
    if ty == "int":
        if isinstance(v, bool) or not isinstance(v, int):
            raise TypeError(f"expected an int, got {json.dumps(v)}")
        return v
    raise TypeError(f"the tool cannot pass a {ty} argument")


def run(task: dict, args: list) -> dict:
    """Run a parsed task on positional interpreter values: {"verdict": ok|requires-excluded|
    undefined|budget|crash, "got": <JSON value>}."""
    import interp
    params = task["params"]
    if len(args) != len(params):
        return {"verdict": "arity", "why": f"{len(args)} arguments for {len(params)} parameters"}
    env = {p["name"]: a for p, a in zip(params, args)}
    ret = task["returns"][0]["name"]
    funs = interp.funs_of(task, task["body"])
    st = interp.St()
    try:
        if not all(interp.ev(c, env, funs, st) for c in task.get("requires", [])):
            return {"verdict": "requires-excluded"}
        env2 = dict(env)
        env2[ret] = None
        interp.exec_body(task["body"], env2, funs, st)
    except interp.Undef as u:
        return {"verdict": "undefined", "why": _short(u)}
    except (interp.Budget, RecursionError) as b:
        return {"verdict": "budget", "why": _short(b)}
    except (TypeError, ValueError, KeyError, IndexError, AttributeError) as c:
        return {"verdict": "crash", "why": _short(f"{type(c).__name__}: {c}")}
    if env2[ret] is None:
        return {"verdict": "undefined", "why": "no path assigned the return"}
    return {"verdict": "ok", "got": interp._j(env2[ret])}


def check(program: str) -> tuple[dict | None, list[str]]:
    """Parse and type check a draft; return (task or None, the tool's lines so far)."""
    import surface
    import fuzz_lower
    try:
        task = surface.parse(program)
    except Exception as e:                                       # noqa: BLE001  (any parse failure is the answer)
        return None, [f"parses: no: {_short(f'{type(e).__name__}: {e}')}"]
    try:
        errs = fuzz_lower.check_wf(task)
    except Exception as e:                                       # noqa: BLE001
        errs = [f"check_wf raised {type(e).__name__}: {e}"]
    if errs:
        return None, ["parses: yes", f"well formed: no: {_short('; '.join(errs))}"]
    return task, ["parses: yes", "well formed: yes"]


def call(program: str, context: str = "") -> str:
    """The tool: check the draft, then run it on every Example line in `context`."""
    task, lines = check(program)
    if task is None:
        return "\n".join(lines)
    types = [p["type"] for p in task["params"]]
    for i, ex in enumerate(parse_examples(context), 1):
        if "error" in ex:
            lines.append(f"example {i}: unreadable: {_short(ex['error'])}")
            continue
        try:
            args = [_value(ty, v) for ty, v in zip(types, ex["args"])]
        except TypeError as e:
            lines.append(f"example {i}: cannot run: {_short(e)}")
            continue
        if len(ex["args"]) != len(types):
            lines.append(f"example {i}: arity: {len(ex['args'])} arguments for {len(types)} parameters")
            continue
        got = run(task, args)
        if got["verdict"] != "ok":
            lines.append(f"example {i}: {got['verdict']}" + (f": {got['why']}" if got.get("why") else ""))
        elif json.dumps(got["got"]) == json.dumps(ex["expected"]):
            lines.append(f"example {i}: pass")
        else:
            lines.append(f"example {i}: fail: got {json.dumps(got['got'])}, expected {json.dumps(ex['expected'])}")
    return "\n".join(lines)


def examples_from_program(program: str, n: int = 2, limit: int = 256) -> list[str]:
    """Up to n `Example:` lines computed by running a proved program.

    Inputs come from interp.domain (ladders over the task's literals, shell
    order); an input the `requires` excludes is skipped, as is one the
    interpreter cannot finish. Distinct outputs are required and inputs from
    the median size up come first, so the lines separate programs rather than
    all showing f(0).
    Only int, bool and seq parameters are shown (what parse_examples reads
    back); anything else gives no examples.
    """
    import interp
    import surface
    task = surface.parse(program)
    names = [(p["name"], p["type"]) for p in task["params"]]
    if not names or any(ty not in RUNNABLE_TYPES for _, ty in names):
        return []
    rows = []
    for env in interp.domain(task, names, limit):
        args = [env[name] for name, _ in names]
        got = run(task, args)
        if got["verdict"] == "ok":
            rows.append(([interp._j(a) for a in args], got["got"]))
    if not rows:
        return []

    def size(row):
        return len(json.dumps(row[0]))

    # from the median input size upward, then the smaller ones: the smallest
    # inputs (0, []) rarely separate programs and the largest are the ladders'
    # 2**31 boundary values
    ordered = sorted(rows, key=size)
    ordered = ordered[len(ordered) // 2:] + ordered[:len(ordered) // 2]
    chosen, seen = [], set()
    for row in ordered:
        key = json.dumps(row[1])
        if key not in seen:
            chosen.append(row)
            seen.add(key)
        if len(chosen) == n:
            break
    fn = task["name"]
    return [f"Example: {fn}({', '.join(json.dumps(a) for a in args)}) == {json.dumps(out)}"
            for args, out in chosen]
