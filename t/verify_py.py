#!/usr/bin/env python3
"""t/verify_py.py -- a Python function you already have, given a proved twin (2026-10-05).

    python3 t/verify_py.py --student HOST:PORT --file F.py [--fn NAME] [--test "assert f(1) == 2" ...]
        [--specs 3] [--answers 3] [--save-t OUT.t] [--save-python OUT.py] [--certificate OUT.json]

`dawnr verify F.py` is this.

Why. Most people who want a function checked already wrote it. The function is then the best oracle there is for
what it does: it can be run. VERT (Yang et al., arXiv:2404.18852) checks a model-written translation against an
oracle built from the source program by property-based testing and regenerates one that fails; CrossHair
(github.com/pschanely/CrossHair) searches a typed, contracted Python function for counterexamples with an SMT
solver. Here the model writes, as SAFE's two stages do (arXiv:2410.15756 3.2 and 3.3, the `spec` and `proof-py`
rows the student was trained on, t/spec_first_rows.py), first a specification from the function and its examples,
then a `t` body for it; and three things that did not write them decide. Research receipt 6f200fb63ee1.

  the function itself   run in the sandbox (t/py_sandbox.py): a specification is kept only if it holds at the
                        function's own answers on drawn inputs and rejects most wrong ones (t/spec_gate.py), and a
                        body only if it answers every drawn input inside its `requires` as the function does
  the provers           the body must be proved against that specification, its sabotaged twin refuted
  the person            the specification is printed to be read: it says what the function does, which is not
                        always what was meant

What is established and what is not. The proof is of the `t` program. That it is the same function as the Python
is tested on drawn inputs, not proved (VERT's property-testing level; there is no model checker for Python here).
The examples, when none is given with --test, are taken from the function itself on small inputs of its annotated
types, so they record what it does; a bug in it is recorded too, and shows in the specification.

Read: one plain top-level function with positional parameters. Without --test, each parameter needs one of the
annotations int, bool, str, list[int], list[str], list[list[int]].
"""
from __future__ import annotations

import argparse
import ast
import copy
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import answer as gate                                           # noqa: E402
import interp                                                   # noqa: E402
import py_sandbox                                               # noqa: E402
import python_beside                                            # noqa: E402
import score_levels                                             # noqa: E402
import spec_experiment as se                                    # noqa: E402
import spec_first                                               # noqa: E402
import spec_first_rows                                          # noqa: E402
import spec_gate                                                # noqa: E402
import surface                                                  # noqa: E402
import to_python                                                # noqa: E402

TEMPERATURE = 0.7
EXAMPLES = 6                   # examples taken from the function when the person gives none
# small values of each annotated type, a plain one first: the first example fixes the kinds the model is told
_DRAWS = {
    "int": [2, 0, 1, 5, -1, 10, 3, -4, 7, 12],
    "bool": [True, False],
    "str": ["ab", "", "a", "hello", "Hello World", "a1b2", "racecar"],
    "list[int]": [[1, 2, 3], [], [1], [3, 1, 2], [2, 2], [-1, 5, 0, 4], [10, -3, 7, 7, 0]],
    "list[str]": [["b", "a"], [], ["a"], ["hello", "world", "hi"]],
    "list[list[int]]": [[[1, 2], [3, 4]], [], [[1]], [[3], [], [1, 2]]],
}
_REPR = "\n\ndef _t_repr_call(args):\n    return repr({fn}(*args))\n"


class Refused(Exception):
    """The file cannot be taken as it is; the message says what to change."""


def _kind(annotation) -> str | None:
    """An annotation as one of _DRAWS' keys, or None."""
    if annotation is None:
        return None
    text = ast.unparse(annotation).replace(" ", "").replace("typing.", "").replace("List[", "list[")
    return text if text in _DRAWS else None


def read_function(source: str, fn: str | None = None) -> dict:
    """{"fn", "kinds": [kind | None per parameter], "doc", "shown": the function and the file's functions it calls,
    "code": the file}. Refused with what to change when the file holds no function this reads."""
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        raise Refused(f"the file is not Python: {error.msg} (line {error.lineno})") from None
    defs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    if fn is None:
        public = [n for n in defs if not n.startswith("_")]
        if len(public) != 1:
            raise Refused("the file has no top-level function" if not defs else
                          f"the file has more than one function; say which with --fn ({', '.join(sorted(defs))})")
        fn = public[0]
    if fn not in defs:
        raise Refused(f"the file has no top-level function `{fn}`")
    node = defs[fn]
    a = node.args
    if a.vararg or a.kwarg or a.kwonlyargs:
        raise Refused(f"`{fn}` takes *args, **kwargs or keyword-only parameters; only positional parameters are read")
    if any(isinstance(n, (ast.Yield, ast.YieldFrom, ast.Await)) for n in ast.walk(node)):
        raise Refused(f"`{fn}` is a generator or awaits; only a function that returns a value is read")
    if not a.args:
        raise Refused(f"`{fn}` takes no parameter; there is nothing to specify")
    used, order = {fn}, [fn]
    for name in order:                                          # the file's own functions it calls, in call order
        for n in ast.walk(defs[name]):
            if isinstance(n, ast.Name) and n.id in defs and n.id not in used:
                used.add(n.id)
                order.append(n.id)
    shown = "\n\n".join(ast.get_source_segment(source, defs[name]) or "" for name in order)
    return {"fn": fn, "kinds": [_kind(p.annotation) for p in a.args], "params": [p.arg for p in a.args],
            "doc": ast.get_docstring(node) or "", "shown": shown, "code": source}


def drawn_tests(function: dict, want: int = EXAMPLES, seed: int = 0) -> list[str]:
    """`assert f(arguments) == value` lines taken from the function itself in the sandbox, on small inputs of its
    annotated types; an input it raises on is passed over. Refused when a parameter has no annotation this reads."""
    missing = [p for p, k in zip(function["params"], function["kinds"]) if k is None]
    if missing:
        raise Refused(f"no --test was given and `{missing[0]}` has no annotation this reads; annotate each parameter "
                      f"({', '.join(_DRAWS)}) or give an example with --test \"assert {function['fn']}(...) == ...\"")
    pools = [_DRAWS[k] for k in function["kinds"]]
    rng = random.Random(seed)
    tried = [tuple(pool[i % len(pool)] for pool in pools) for i in range(max(len(pool) for pool in pools))]
    tried += [tuple(rng.choice(pool) for pool in pools) for _ in range(4 * want)]
    out, seen = [], set()
    with py_sandbox.Session(function["code"] + _REPR.format(fn=function["fn"]), "_t_repr_call") as session:
        for args in tried:
            if repr(args) in seen:
                continue
            seen.add(repr(args))
            try:
                value = session.call([list(args)])
            except (py_sandbox.CallError, py_sandbox.CallTimeout, py_sandbox.Unrepresentable):
                continue
            if isinstance(value, str):
                out.append(f"assert {function['fn']}({', '.join(repr(a) for a in args)}) == {value}")
            if len(out) >= want:
                break
    return out


def entry_for(function: dict, tests: list[str]) -> tuple[dict, bool]:
    """(the entry the gate reads, whether the examples were taken from the function). Refused when the function
    fails an example the person gave, or its examples are not values `t` holds."""
    drawn = not tests
    if drawn:
        tests = drawn_tests(function)
        if len(tests) < 2:
            raise Refused(f"`{function['fn']}` answered fewer than two of the small inputs tried; give examples with --test")
    else:
        r = py_sandbox.run_tests(function["code"], [t.strip() for t in tests])
        if r.get("status") != "ran":
            raise Refused(f"the file could not be run in the sandbox ({r.get('why') or r.get('status')})")
        failed = [t for t, v in zip(tests, r["verdicts"]) if v != "pass"]
        if failed:
            raise Refused(f"your function fails your own example `{failed[0].strip()}`; nothing was asked of the model")
    text = function["doc"].strip() or f"Write `{function['fn']}`, the function the Python solution below computes."
    try:
        entry = gate.entry_of(text, tests)
    except ValueError as error:
        raise Refused(("the examples taken from the function are not values t holds: " if drawn else "") + str(error)) from None
    if entry["fn"] != function["fn"]:
        raise Refused(f"the examples call `{entry['fn']}`, and the function is `{function['fn']}`")
    return entry, drawn


def _ensures(spec: dict) -> str:
    """A specification's `ensures` clauses on one line, for a refusal a person can read."""
    return "`" + "; ".join(surface.pexpr(e) for e in spec.get("ensures", [])) + "`"


def _false_at(spec: dict, entry: dict) -> str | None:
    """The first example at which the specification does not hold of the recorded answer, or None."""
    try:
        funs = interp.funs_of(spec, [])
        ret = spec["returns"][0]["name"]
        for source, point in zip(entry["rec"]["test_list"], entry["points"]):
            env, refusal = se.bind_point(spec, point)
            if refusal is not None:
                return None
            kind, value = se.expected_value(spec, point)
            env[ret] = se._as_interp_value(kind, value)
            st = interp.St()
            try:
                if not all(interp.ev(c, env, funs, st) for c in spec.get("requires", [])):
                    continue
                if not all(interp.ev(e, env, funs, st) is True for e in spec.get("ensures", [])):
                    return source.strip()[7:]
            except (interp.Undef, interp.Budget, RecursionError, ZeroDivisionError):
                return source.strip()[7:]
    except Exception:                                           # noqa: BLE001 -- the example is advice for the refusal line
        return None
    return None


def verify(entry: dict, function: dict, student, specs: int = 3, answers: int = 3, max_new: int = 1024,
           prover=gate.prove, jobs: int = 2) -> dict:
    """The whole of `verify` for one function. `student` is a `decode` (python_beside.api_decode's shape).
    {"shown": {...} | None, "refused": [...], "why"?}."""
    fn, code, shown_code = entry["fn"], function["code"], function["shown"]
    tests = entry["rec"]["test_list"]
    out = {"fn": fn, "tests": tests, "refused": [], "shown": None, "specifications asked": specs, "bodies asked": 0}
    written = []
    for attempt in range(specs):
        reply = student([spec_first_rows.spec_question(entry, shown_code)], 0.0 if attempt == 0 else TEMPERATURE,
                        100 + attempt, "q", max_new)[0][0]
        block = se.find_block(reply or "")
        if block is None:
            out["refused"].append(f"specification {attempt + 1}: no t task in the reply")
            continue
        try:
            written.append((f"specification {attempt + 1}", surface.parse(block)))
        except Exception as error:                              # noqa: BLE001 -- the parser's message is the reason
            out["refused"].append(f"specification {attempt + 1}: it does not parse ({str(error).split(': ', 1)[-1][:90]})")
    record: list = []
    kept, _counts = spec_first.kept_specifications(written, entry, specs, record)
    tasks, false_at = dict(written), []
    for r in record:
        if r["verdict"] in ("dropped", "unscorable"):
            said, example = _ensures(tasks[r["source"]]), _false_at(tasks[r["source"]], entry)
            if "unscorable" in r["scores"]:
                out["refused"].append(f"{r['source']}: {said} cannot be judged on your examples ({r['scores']['unscorable']})")
            elif example:
                false_at.append(example)
                out["refused"].append(f"{r['source']}: {said} is false at your function's own answer `{example}`")
            else:
                c = r["scores"].get("completeness")
                out["refused"].append(f"{r['source']}: {said} says too little"
                                      + (f": it accepts {100 * (1 - c):.0f}% of the wrong results tried on your examples" if c is not None else ""))
    supported = []
    for k in kept:                                              # the function itself decides what a specification is worth
        v = spec_gate.judge(k["task"], entry, code)
        if v["passes"]:
            supported.append({"label": k["source"], "spec": k["task"], "stage": v})
            continue
        a = v.get("agreement") or {}
        if a.get("status") == "disagrees" and a.get("args") is not None:
            call = f"{fn}({', '.join(json.dumps(x) for x in a['args'])}) == {json.dumps(a.get('reference_said'))}"
            false_at.append(call)
            out["refused"].append(f"{k['source']}: {_ensures(k['task'])} is false at your function's own answer `{call}`")
        else:
            out["refused"].append(f"{k['source']}: {_ensures(k['task'])}: {v['why']}")
    if not supported:
        why = "no specification the model wrote holds at your function's answers and pins them down"
        if false_at and function.get("doc") and len(false_at) == len([x for x in out["refused"] if "is false at your function's own answer" in x]) == len(written):
            # written from the docstring and the code, and false of what the code does: one of the two is not what was meant
            why += (f". Every one it wrote from your docstring is false at an answer your function gives (`{false_at[0]}`): "
                    "either the model misread the docstring, or the function does not do what it says")
        return dict(out, why=why)
    seen: set[str] = set()
    for s in supported:
        for attempt in range(answers):
            reply = student([spec_first_rows.proof_question(s["spec"], shown_code)], 0.0 if attempt == 0 else TEMPERATURE,
                            attempt, "q", max_new)[0][0]
            out["bodies asked"] += 1
            label = f"{s['label']}, body {attempt + 1}"
            text, why = spec_first.accept(reply or "", s["spec"], entry)
            if text is None:
                out["refused"].append(f"{label}: {why}")
                continue
            if text in seen:
                continue
            seen.add(text)
            task = surface.parse(text)
            same = to_python.check(task, code, fn, tests, outside=0)
            if not same.get("agrees"):
                where = f" (`{same['first'][7:]}` is the proved program's answer, not yours)" if same.get("first") else ""
                out["refused"].append(f"{label}: it does not answer as your function does{where}")
                continue
            named = se.rename_task(copy.deepcopy(task), f"answer_{out['bodies asked']}__{fn}")
            row = prover([named], jobs).get(named["name"])
            _level, proved = score_levels.answer_level("pass", row, None)
            if not proved:
                refuting = [k for k, cell in (row or {}).items() if str(cell).split(" / ")[0] == "refuted"]
                out["refused"].append(f"{label}: " + (f"refuted by {', '.join(refuting)}" if refuting else "no prover proved it"))
                continue
            a = s["stage"].get("agreement", {})
            out["shown"] = {
                "program": text, "proved by": proved,
                "provers": sorted(k for k, cell in row.items() if cell == score_levels.VERIFIED),
                "undecided": sorted(k for k, cell in row.items() if cell != score_levels.VERIFIED), "cells": dict(row),
                "specification": [l.strip() for l in text.splitlines() if l.strip().startswith(("requires ", "ensures "))],
                "behind the specification": {"tests passed": len(entry["points"]), "agrees with the Python on": a.get("draws"),
                                             "drawn inputs outside its requires": a.get("outside_requires", 0),
                                             "mutated outputs rejected": a.get("completeness")},
                "same as yours on": same["inputs"], "python": gate.python_of(task, entry)}
            return out
    return dict(out, why="no body the model wrote answered as your function does and was proved")


def render(r: dict, drawn: bool = False) -> str:
    lines = []
    if drawn:
        lines += ["No example was given, so these were taken from your function itself:"] + ["  " + t for t in r["tests"]] + [""]
    s = r["shown"]
    if s is None:
        lines.append("NOT VERIFIED: " + r["why"] + ".")
    else:
        b = s["behind the specification"]
        rejected = (f"{100 * b['mutated outputs rejected']:.0f}%" if isinstance(b["mutated outputs rejected"], (int, float))
                    else "every judged one")
        outside = b.get("drawn inputs outside its requires") or 0
        lines += [f"VERIFIED: a proved twin of `{r['fn']}`: proved by {s['proved by']} of 7 provers ({', '.join(s['provers'])}); "
                  "none refutes it." + (f" Undecided: {', '.join(s['undecided'])}." if s["undecided"] else ""),
                  f"Inside its `requires` it answers as your function does on {s['same as yours on']} drawn inputs (yours ran in "
                  f"the sandbox), the {b['tests passed']} example(s) among them.",
                  f"Its specification holds at your function's answers on {b['agrees with the Python on']} drawn inputs and "
                  f"rejects {rejected} of the wrong outputs tried."
                  + (f" Its `requires` leaves out {outside} of the inputs drawn that your function answers." if outside else ""),
                  "", s["program"].rstrip(), "",
                  "Read the specification: it is what was proved, and it says what your function does, which may not be",
                  "what you meant. The proof is of the t program above; that it is the same function as your Python is",
                  "tested on the inputs counted here, not proved."]
    if r["refused"]:
        lines += ["", "Not used:"] + ["  " + x for x in r["refused"]]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--student", required=True, help="host:port of the server holding the model")
    ap.add_argument("--student-name", default="student")
    ap.add_argument("--file", type=Path, required=True, help="a Python file with the function")
    ap.add_argument("--fn", help="the function's name, when the file has more than one")
    ap.add_argument("--test", action="append", default=[], help="your own example, an `assert f(arguments) == value` line; repeat")
    ap.add_argument("--specs", type=int, default=3, help="specifications asked for")
    ap.add_argument("--answers", type=int, default=3, help="bodies asked for a specification")
    ap.add_argument("--jobs", type=int, default=2, help="provers at once")
    ap.add_argument("--reference", action="store_true",
                    help="the writer has never seen t: put the language's reference before each question")
    ap.add_argument("--max-new", type=int, default=1024, help="tokens an answer may take")
    ap.add_argument("--save-t", type=Path, metavar="FILE", help="write the proved t program here")
    ap.add_argument("--save-python", type=Path, metavar="FILE", help="write the proved twin as Python here (it refuses what was not proved)")
    ap.add_argument("--certificate", type=Path, metavar="FILE", help="write the certificate here, for `dawnr check`")
    ap.add_argument("--json", type=Path)
    a = ap.parse_args(argv)
    try:
        function = read_function(a.file.read_text(encoding="utf-8"), a.fn)
        entry, drawn = entry_for(function, a.test)
    except OSError as error:
        raise SystemExit(f"verify: cannot read {a.file}: {error.strerror}")
    except Refused as refused:
        raise SystemExit(f"verify: {refused}")
    student = python_beside.api_decode("openai", [a.student], a.student_name)
    r = verify(entry, function, python_beside.referenced(student) if a.reference else student, a.specs, a.answers, max_new=a.max_new, jobs=a.jobs)
    print(render(r, drawn))
    if a.json:
        a.json.write_text(json.dumps(r, indent=1, default=str) + "\n", encoding="utf-8")
    shown = r["shown"] or {}
    if a.save_t and shown:
        a.save_t.write_text(shown["program"].rstrip() + "\n", encoding="utf-8")
        print(f"\nt program written to {a.save_t}")
    if a.save_python:
        source = (shown.get("python") or {}).get("source")
        if source:
            a.save_python.write_text(source if source.endswith("\n") else source + "\n", encoding="utf-8")
            print(f"\nThe proved twin written as Python to {a.save_python}")
        else:
            print(f"\nNothing written to {a.save_python}: there is no checked Python of a proved twin.", file=sys.stderr)
    if a.certificate:
        import certificate
        made = certificate.from_verify(r, function)
        if made:
            certificate.write(a.certificate, made)
            print(f"\nCertificate written to {a.certificate}; `dawnr check` replays it on any machine, without the model.")
        else:
            print(f"\nNothing written to {a.certificate}: nothing was verified.", file=sys.stderr)
    return 0 if r["shown"] else 1


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
