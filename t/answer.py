#!/usr/bin/env python3
"""t/answer.py -- one question through the whole gate, on one machine (2026-10-01).

    python3 t/answer.py --student HOST:PORT --python HOST:PORT \\
        --text "Write a function that doubles a number." --test "assert double(3) == 6" [--test ...]

What comes back is either an answer that is SHOWN -- a `t` program, its specification, how many of
the seven provers proved it with none refuting, and what stood behind the specification -- or a
REFUSAL that says which gate stopped each attempt. Nothing is shown on the model's word.

The stages, cheapest first (each is a tool this project already measures with):

  1. the student answers the question: one greedy answer, the rest sampled at 0.7 (SAFE's
     Accuracy@k, arXiv:2410.15756: the gate makes sampling safe);
  2. each answer must parse, be well formed and pass the question's own tests
     (t/proof_repair.cheap);
  3. a Python solution is written beside the question by the base model and kept only if it
     passes the same tests in the sandbox (t/python_beside.py, t/py_sandbox.py);
  4. the specification stage with no reference (t/spec_gate.py; Clover's consistency check,
     arXiv:2310.17807): on drawn inputs the specification must hold at the Python's output,
     admit at least half of them, and reject at least 60% of mutated outputs;
  5. the seven provers and the sabotaged twins (t/run_par.py) on what is left; an answer a
     prover refutes is dropped, and the answer proved by the most provers is the one shown;
  6. the shown answer is written again as a Python function under the question's own name and
     run beside the `t` program on the question's tests and on inputs from the interpreter's own
     domain (t/to_python.py: differential testing, the translation is checked and not proved);
     the Python is shown only when every input agrees, and `--save-python FILE` writes it.

The servers are OpenAI-compatible (llama.cpp with a 4-bit GGUF, or `transformers serve`); the
question's tests are `assert f(args) == value` lines in the notation the pool reads
(t/mbpp_dfy.parse_assertion).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import mbpp_dfy                                                 # noqa: E402
import proof_repair                                             # noqa: E402
import python_beside                                            # noqa: E402
import score_levels                                             # noqa: E402
import spec_experiment as se                                    # noqa: E402
import spec_first                                               # noqa: E402
import spec_gate                                                # noqa: E402
import surface                                                  # noqa: E402
import to_python                                                # noqa: E402

TEMPERATURE = 0.7


def entry_of(text: str, tests: list[str]) -> dict:
    """The question as the pool holds a problem: its words, its tests read into points, the
    function's name. ValueError when a test is not an `assert f(...) == value` line the pool's
    reader takes, or the tests name different functions."""
    points = [mbpp_dfy.parse_assertion(a, strings=True, nested_strings=True) for a in tests]
    bad = [f"{a!r}: {p.get('why')}" for a, p in zip(tests, points) if not p.get("ok")]
    if not points or bad:
        raise ValueError("the tests must be `assert f(arguments) == value` lines: " + "; ".join(bad or ["none given"]))
    names = {p["fn"] for p in points}
    if len(names) != 1:
        raise ValueError(f"the tests call more than one function: {sorted(names)}")
    return se.mark_characters({"rec": {"text": text, "test_list": list(tests), "code": ""}, "points": points, "fn": names.pop()})


def candidates(replies: list[str], entry: dict) -> tuple[list[dict], list[str]]:
    """(the distinct answers that parse, are well formed and pass the question's tests, the reason
    each other reply was refused)."""
    kept, seen, refused = [], set(), []
    for n, reply in enumerate(replies):
        if not (reply or "").strip():                           # python_beside.api_decode's reply to a failed request
            refused.append(f"answer {n + 1}: no reply from the model (it did not answer in time, or the request failed)")
            continue
        task, why = proof_repair.cheap(reply, entry, None)
        if task is None:
            refused.append(f"answer {n + 1}: {why}")
            continue
        text = surface.print_task(task)
        if text in seen:
            continue
        seen.add(text)
        kept.append({"n": n + 1, "task": task, "text": text})
    return kept, refused


def python_of(task: dict, entry: dict) -> dict:
    """The shown answer as a Python function under the question's own name: {"source", "inputs"} when the
    translation answers every input tried as the `t` program does, else {"source": None, "why"}. What was proved is
    the `t` program; a translation that was not checked against it is never shown, and a fault in the translator
    costs the Python, not the answer."""
    tests = list(entry["rec"]["test_list"])
    try:
        source, fn = to_python.translate(task, tests, entry["fn"])
    except to_python.Unsupported as unsupported:
        return {"source": None, "why": f"it uses {unsupported}, which the translation does not write yet"}
    except Exception as error:                                  # noqa: BLE001
        return {"source": None, "why": f"the translation failed ({type(error).__name__})"}
    try:
        report = to_python.check(task, source, fn, tests)
    except Exception as error:                                  # noqa: BLE001
        return {"source": None, "why": f"the translation could not be run beside the proved program ({type(error).__name__})"}
    if not report.get("agrees"):
        return {"source": None, "inputs": report.get("inputs", 0),
                "why": "its Python translation did not answer every input as the proved program does"}
    return {"source": source, "inputs": report["inputs"]}


def prove(tasks: list[dict], jobs: int = 2, timeout: float = 1800.0) -> dict[str, dict]:
    """name -> the seven kernels' cells for it (t/run_par.py: each program and its sabotaged twin)."""
    with tempfile.TemporaryDirectory(prefix="t-answer-") as tmp:
        d = Path(tmp)
        (d / "tasks").mkdir()
        for task in tasks:
            (d / "tasks" / f"{task['name']}.json").write_text(json.dumps(task), encoding="utf-8")
        env = dict(os.environ, T_SPARK_JOBS="1", CUDA_VISIBLE_DEVICES="")
        subprocess.run([sys.executable, str(HERE / "run_par.py"), "--tasks", str(d / "tasks"), "--out", str(d / "out"),
                        "--table", str(d / "table.md"), "--jobs", str(jobs), "--no-cache"],
                       capture_output=True, text=True, timeout=timeout, env=env)
        _cols, cells = se.parse_kernel_table(d / "table.md")
    return cells


def answer(entry: dict, student, python, prompt_version: str = "s2", answers: int = 5, max_new: int = 1024,
           prover=prove, jobs: int = 2, consistency: int = 0) -> dict:
    """The whole gate for one question. `student` and `python` are `decode`s
    (python_beside.api_decode's shape). Returns {"shown": {...} | None, "refused": [...], ...}."""
    question = se.build_prompt(entry, prompt_version)
    replies = [student([question], 0.0, 0, "q", max_new)[0][0]]
    for seed in range(1, answers):
        replies.append(student([question], TEMPERATURE, seed, "q", max_new)[0][0])
    kept, refused = candidates(replies, entry)
    out = {"question": entry["rec"]["text"], "fn": entry["fn"], "tests": entry["rec"]["test_list"], "answers asked": len(replies),
           "pass the tests": len(kept), "refused": refused, "shown": None}
    if not kept:
        return dict(out, why="no answer parsed, was well formed and passed the question's tests")
    code, counts = spec_first.written_python(python, ["q"], {"q": entry}, 3, 1, 768)
    out["python beside it"] = code.get("q")
    # `consistency` further solutions sampled at 0.8 hold the specification too (ClarifyGPT's code consistency
    # check, arXiv:2310.10996; t/PREDICT-2026-10-02-ambiguity.md): a question two solutions read differently is refused
    others = spec_first.sampled_python(python, ["q"], {"q": entry}, consistency, 1, 768)["q"] if consistency and code.get("q") else []
    judged = []
    for c in kept:
        v = spec_gate.judge_all(c["task"], entry, code.get("q"), others)
        if v.get("ambiguous") and "ambiguous" not in out:
            out["ambiguous"] = v["ambiguous"]
        c["stage"] = v
        (judged if v["passes"] else refused).append(c if v["passes"] else f"answer {c['n']}: {v['why']}")
    if not judged:
        return dict(out, why="the question can be read more than one way" if out.get("ambiguous")
                    else "no answer's specification could be supported without a reference")
    for i, c in enumerate(judged):                              # distinct names: one table row each
        c["task"] = se.rename_task(c["task"], f"answer_{c['n']}__{entry['fn']}")
    cells = prover([c["task"] for c in judged], jobs)
    best, best_task = None, None
    for c in judged:
        row = cells.get(c["task"]["name"])
        _level, proved = score_levels.answer_level("pass", row, None)
        if not proved:
            refuting = [k for k, cell in (row or {}).items() if str(cell).split(" / ")[0] == "refuted"]
            refused.append(f"answer {c['n']}: " + (f"refuted by {', '.join(refuting)}" if refuting else "no prover proved it"))
            continue
        if best is None or proved > best["proved by"]:
            a = c["stage"].get("agreement", {})
            best_task = c["task"]
            best = {"answer": c["n"], "program": c["text"], "proved by": proved,
                    "provers": sorted(k for k, cell in row.items() if cell == score_levels.VERIFIED),
                    "undecided": sorted(k for k, cell in row.items() if cell != score_levels.VERIFIED),
                    "specification": [l.strip() for l in c["text"].splitlines() if l.strip().startswith(("requires ", "ensures "))],
                    "behind the specification": {"tests passed": len(entry["points"]), "agrees with the Python on": a.get("draws"),
                                                 "drawn inputs outside its requires": a.get("outside_requires", 0),
                                                 "mutated outputs rejected": a.get("completeness")}}
    out["shown"] = best
    if best is None:
        out["why"] = "no prover proved an answer whose specification was supported"
    else:
        best["python"] = python_of(best_task, entry)
    return out


def render(r: dict) -> str:
    lines = []
    s = r["shown"]
    if s is None:
        lines.append("REFUSED: " + r["why"] + ".")
    else:
        b = s["behind the specification"]
        lines += [f"SHOWN: proved by {s['proved by']} of 7 provers ({', '.join(s['provers'])}); none refutes it."
                  + (f" Undecided: {', '.join(s['undecided'])}." if s["undecided"] else ""),
                  f"Its specification passes the question's {b['tests passed']} test(s), holds at an independently written "
                  f"Python solution's answer on {b['agrees with the Python on']} drawn inputs, and rejects "
                  + (f"{100 * b['mutated outputs rejected']:.0f}%" if isinstance(b["mutated outputs rejected"], (int, float)) else "every judged one")
                  + " of the wrong outputs tried.", "", s["program"].rstrip()]
        py = s.get("python") or {}
        if py.get("source"):
            lines += ["", f"The same function in Python. It is translated from the proved program and gave the same answer on "
                          f"{py['inputs']} inputs, the question's tests among them; the proof is of the t program above, "
                          f"and the Python is tested against it, not proved.", "", py["source"].rstrip()]
        elif py:
            lines += ["", f"No Python version is shown: {py['why']}."]
    if r["refused"]:
        lines += ["", f"Of {r['answers asked']} answers asked for, not shown:"] + ["  " + x for x in r["refused"]]
    if s is None and r.get("ambiguous"):
        a = r["ambiguous"]
        args = ", ".join(repr(x) for x in a.get("args") or [])
        lines += ["", f"Another solution that passes the same tests answers {r.get('fn', 'f')}({args}) with "
                      f"{a.get('another_solution_said')!r}, and the answer's specification disagrees there. "
                      f"Add a --test for that input to say which is meant."]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--student", required=True, help="host:port of the server holding the student")
    ap.add_argument("--python", required=True, help="host:port of the server holding the Python writer (the base model)")
    ap.add_argument("--student-name", default="student")
    ap.add_argument("--python-name", default="base")
    ap.add_argument("--text", required=True, help="the question, in words")
    ap.add_argument("--test", action="append", default=[], help="an `assert f(arguments) == value` line; repeat")
    ap.add_argument("--prompt", choices=se.PROMPT_VERSIONS, default="s2")
    ap.add_argument("--answers", type=int, default=5)
    ap.add_argument("--consistency", type=int, default=0,
                    help="further Python solutions sampled at 0.8 that must not find the specification false (0: off)")
    ap.add_argument("--jobs", type=int, default=2, help="provers at once")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--save-python", type=Path, metavar="FILE",
                    help="write the shown answer's Python function here (only when it was checked against the proof)")
    a = ap.parse_args(argv)
    try:
        entry = entry_of(a.text, a.test)
    except ValueError as e:
        raise SystemExit(f"answer: {e}")
    r = answer(entry, python_beside.api_decode("openai", [a.student], a.student_name),
               python_beside.api_decode("openai", [a.python], a.python_name), a.prompt, a.answers, jobs=a.jobs, consistency=a.consistency)
    print(render(r))
    if a.json:
        a.json.write_text(json.dumps(r, indent=1, default=str) + "\n", encoding="utf-8")
    if a.save_python:
        source = ((r["shown"] or {}).get("python") or {}).get("source")
        if source:
            a.save_python.write_text(source if source.endswith("\n") else source + "\n", encoding="utf-8")
            print(f"\nPython written to {a.save_python}")
        else:
            print(f"\nNothing written to {a.save_python}: there is no checked Python for this question.", file=sys.stderr)
    return 0 if r["shown"] else 1


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
