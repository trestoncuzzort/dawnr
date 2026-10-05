#!/usr/bin/env python3
"""t/prove.py -- from a specification, not from English (2026-10-05).

    python3 t/prove.py prove --student HOST:PORT --spec FILE [--answers 5] [--save-python OUT.py] [--save-t OUT.t]
    python3 t/prove.py spec --student HOST:PORT --python HOST:PORT --text "..." --test "assert f(1) == 2" [--save FILE]

`dawnr prove FILE` and `dawnr spec "QUESTION" --test ...` are these two.

Why this way in. From English the hard step is the specification: most of the model's wrong answers are a program
proved against a specification that is not the question's (t/PREDICT-2026-10-01-v6.md). Given the specification it
writes a body all seven provers accept far more often (27 of 33 held-out questions, 10 of the 14 whose function is
nowhere in its training rows; t/DECONTAMINATION-2026-10-05.md). And the specification is where a person's check
belongs: checking a program against a specification is mechanical, while "there is no algorithmic way of ensuring
the correctness of the user-intent formalization" (Lahiri, arXiv:2406.09757), so the specification is shown to be
read, with a measure of how much it says: its power to reject wrong results, which is how nl2postcond
(arXiv:2310.01831) judges a postcondition. Research receipt 7ef0f73bdaab.

  prove   FILE holds one `t` task: its header, parameters, `requires`, `ensures` and spec funs, and an empty body.
          The model is asked for the body as its training rows ask (t/student_rows.py ASK), one greedy answer and
          the rest sampled. An answer counts only if it carries the specification unchanged (t/spec_given.kept: it
          may add an `ensures`, never drop or alter one), is well formed, and is proved with no prover refuting it;
          the one proved by the most provers is shown, with the same function in Python (t/to_python.py). A file
          that already has a body is sent to the provers as written and no model is asked.
          `--test "assert f(1) == 2"` gives the person's own examples. An answer that fails one is not sent to the
          provers while another passes them all; and when a body is PROVED and still fails a test, that is said
          first and loudest, because it means the specification allows an answer the person's own example rules
          out: the proof is real and the specification is not yet what was meant (Lahiri's test-based check of a
          specification, arXiv:2406.09757, with the person's tests as the tests).
          The proof says the program meets the specification; it cannot say the specification is what was meant.
          So the specification is also measured, with the proved program as the oracle: on inputs of the program's
          own domain, the share of wrong results (t/spec_check.mutations of the right one) the `ensures` rejects,
          SAFE's completeness (arXiv:2410.15756, 3.2), and when it is low one concrete wrong result it accepts.

  spec    the first four stages of `dawnr ask` (t/answer.py), stopped before the provers, and what is shown is the
          specifications: every distinct specification whose program passed the question's tests and which holds
          at an independently written Python solution's answer on drawn inputs, each with how much it pins down.
          `--save FILE` writes one of them with an empty body, ready for `prove`.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import answer as gate                                           # noqa: E402
import dafny_feedback                                           # noqa: E402
import interp                                                   # noqa: E402
import python_beside                                            # noqa: E402
import score_levels                                             # noqa: E402
import score_spec_given                                         # noqa: E402
import spec_check                                               # noqa: E402
import spec_experiment as se                                    # noqa: E402
import spec_first                                               # noqa: E402
import spec_gate                                                # noqa: E402
import spec_panel                                               # noqa: E402
import student_rows                                             # noqa: E402
import surface                                                  # noqa: E402
import to_python                                                # noqa: E402

TEMPERATURE = 0.7
PIN_INPUTS = 60               # inputs of the program's own domain the specification is measured on
WEAK = 0.6                    # SAFE's line: a specification that rejects fewer wrong results than this is weak
_STAGE = {"no-block": "no t task in the reply", "parse": "it does not parse", "wf": "it is not well formed",
          "spec-changed": "it changed the specification"}


class Refused(Exception):
    """The file is not a specification this can work from; the message says why."""


def read_spec(text: str) -> dict:
    """The task in FILE, fenced or bare."""
    block = se.find_block(text) or text
    try:
        task = surface.parse(block.strip() + "\n")
    except Exception as error:                                  # noqa: BLE001 -- the parser's message is the help
        raise Refused(f"the file is not a t task: {error}") from None
    if not task.get("returns"):
        raise Refused("the task returns nothing; a specification needs a result to speak about")
    if not task.get("ensures"):
        raise Refused("the task has no `ensures`: there is nothing to prove")
    return task


def pins_down(task: dict, n: int = PIN_INPUTS) -> dict:
    """How much the specification says, with the proved program as the oracle: {"inputs", "mutants", "rejected",
    "completeness", "witness"}; completeness None when no input or no mutant could be judged. The witness is the
    first wrong result the `ensures` accepts: {"args": {...}, "right": value, "also_accepted": value}."""
    ret = task["returns"][0]["name"]
    funs = interp.funs_of(task, task.get("body", []))
    mutants = rejected = 0
    witness = None
    points = spec_panel.inputs(task, n)
    for values, right in points:
        env = {p["name"]: v for p, v in zip(task["params"], values)}
        for wrong in spec_check.mutations(right):
            if wrong == right and isinstance(wrong, bool) == isinstance(right, bool):
                continue
            probe = dict(env)
            probe[ret] = wrong
            try:
                accepts = all(interp.ev(e, probe, funs, interp.St()) is True for e in task.get("ensures", []))
            except Exception:                                   # noqa: BLE001 -- undefined on a wrong result rejects it
                accepts = False
            mutants += 1
            rejected += not accepts
            if accepts and witness is None:
                witness = {"args": {p["name"]: interp._j(v) for p, v in zip(task["params"], values)},
                           "right": interp._j(right), "also_accepted": interp._j(wrong)}
    return {"inputs": len(points), "mutants": mutants, "rejected": rejected,
            "completeness": (rejected / mutants) if mutants else None, "witness": witness}


def read_tests(tests: list[str], spec: dict) -> dict | None:
    """The person's own examples, read as a question's tests are (t/answer.py entry_of); None when there are none."""
    if not tests:
        return None
    try:
        entry = gate.entry_of("", list(tests))
    except ValueError as error:
        raise Refused(str(error)) from None
    if entry["fn"] != spec["name"]:
        raise Refused(f"the tests call `{entry['fn']}`, and the specification's task is `{spec['name']}`")
    return entry


def failing(task: dict, entry: dict | None) -> list[dict]:
    """The person's tests this program does not pass: [{"test", "verdict", "got"}]."""
    out = []
    for source, point in zip(entry["rec"]["test_list"], entry["points"]) if entry else ():
        try:
            verdict = se.run_point(task, point)
        except Exception as error:                              # noqa: BLE001 -- a crash on a test is that test failing
            verdict = {"verdict": f"raised {type(error).__name__}"}
        if verdict["verdict"] != "pass":
            out.append({"test": source.strip(), "verdict": verdict["verdict"], "got": verdict.get("got")})
    return out


def python_of(task: dict, name: str, tests: list[str] | None = None) -> dict:
    """The proved program as Python under the specification's own name, shown only when it answers every input
    tried as the program does (t/to_python.py); the person's tests, when given, are among the inputs and decide how
    a sequence is written at the boundary (a str, a list, a tuple)."""
    tests = list(tests or [])
    try:
        source, fn = to_python.translate(task, tests, name)
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
    return {"source": source, "function": fn, "inputs": report["inputs"], "refused": report.get("refused", 0)}


def prove(spec: dict, student=None, answers: int = 5, max_new: int = 1024, prover=gate.prove, jobs: int = 2,
          tests: dict | None = None) -> dict:
    """The whole of `prove` for one specification. `student` is a `decode` (python_beside.api_decode's shape); it is
    not asked when the specification already carries a body. `tests` is read_tests' entry, or None."""
    name = spec["name"]
    out = {"name": name, "answers asked": 0, "refused": [], "shown": None, "wrote the body": "the model",
           "tests": len(tests["points"]) if tests else 0}
    kept: list[dict] = []
    if spec.get("body"):
        out["wrote the body"] = "the file"
        kept.append({"n": 1, "task": spec, "text": surface.print_task(spec)})
    else:
        question = student_rows.row_for(spec)["prompt"]
        replies = [student([question], 0.0, 0, "q", max_new)[0][0]]
        for seed in range(1, answers):
            replies.append(student([question], TEMPERATURE, seed, "q", max_new)[0][0])
        out["answers asked"] = len(replies)
        seen = set()
        for n, reply in enumerate(replies):
            if not (reply or "").strip():
                out["refused"].append(f"answer {n + 1}: no reply from the model")
                continue
            stage, why, task = score_spec_given.judge(spec, reply, normalise_name=True)
            if task is None:
                out["refused"].append(f"answer {n + 1}: {_STAGE.get(stage, stage)}" + (f" ({why})" if why else ""))
                continue
            text = surface.print_task(task)
            if text not in seen:
                seen.add(text)
                kept.append({"n": n + 1, "task": task, "text": text})
        if not kept:
            return dict(out, why="no answer kept the specification and was well formed")
    for c in kept:
        c["fails"] = failing(c["task"], tests)
    passing = [c for c in kept if not c["fails"]]
    if tests and passing:                                       # the cheap check first: only what passes the person's tests is proved
        for c in kept:
            if c["fails"]:
                f = c["fails"][0]
                out["refused"].append(f"answer {c['n']}: fails your test `{f['test']}`"
                                      + (f" (it returns {_value(f['got'])})" if f.get("got") is not None else f" ({f['verdict']})"))
        kept = passing
    named = {c["n"]: se.rename_task(copy.deepcopy(c["task"]), f"answer_{c['n']}__{name}") for c in kept}
    cells = prover(list(named.values()), jobs)
    best = best_c = None
    for c in kept:
        row = cells.get(named[c["n"]]["name"])
        _level, proved = score_levels.answer_level("pass", row, None)
        if not proved:
            refuting = [k for k, cell in (row or {}).items() if str(cell).split(" / ")[0] == "refuted"]
            out["refused"].append(f"answer {c['n']}: " + (f"refuted by {', '.join(refuting)}" if refuting else "no prover proved it"))
            continue
        if best is None or proved > best["proved by"]:
            best_c = c
            best = {"answer": c["n"], "program": c["text"], "proved by": proved,
                    "provers": sorted(k for k, cell in row.items() if cell == score_levels.VERIFIED),
                    "undecided": sorted(k for k, cell in row.items() if cell != score_levels.VERIFIED), "cells": dict(row)}
    if best is None:
        # the specification is the person's to fix, and "not proved" names nothing they could act on; Dafny's own
        # diagnostics name the clause (t/dafny_feedback.py, after SAFE's verifier-error triplets, arXiv:2410.15756 3.3)
        try:
            out["dafny says"] = {"answer": kept[0]["n"], "lines": dafny_feedback.diagnostics(kept[0]["task"])}
        except Exception:                                       # noqa: BLE001 -- advice only: no Dafny here, or it did not run
            pass
        return dict(out, why="no prover proved a body for this specification" if out["wrote the body"] == "the model"
                    else "no prover proved the program as written")
    try:
        best["specification"] = pins_down(best_c["task"])
    except Exception as error:                                  # noqa: BLE001 -- the measurement is advice, not a gate
        best["specification"] = {"completeness": None, "why": f"{type(error).__name__}: {error}"[:120]}
    if best_c["fails"]:
        # proved, and it fails the person's own example: the specification admits an answer the example rules out
        out["contradiction"] = dict(best, fails=best_c["fails"])
        return dict(out, why="a body was proved against your specification and it fails your own test")
    best["python"] = python_of(best_c["task"], name, tests["rec"]["test_list"] if tests else None)
    out["shown"] = best
    return out


def _value(v) -> str:
    return json.dumps(v)


def render_proof(r: dict) -> str:
    lines = []
    s = r["shown"]
    c = r.get("contradiction")
    if c:
        f = c["fails"][0]
        lines += [f"NOT WHAT YOU ASKED FOR: a body was proved against your specification by {c['proved by']} of 7 provers "
                  f"({', '.join(c['provers'])}), and it fails your own test.",
                  f"`{f['test']}`: " + (f"the program returns {_value(f['got'])}." if f.get("got") is not None
                                        else f"the program gives no answer there ({f['verdict']})."),
                  "The proof is real, so your specification allows that answer. Tighten an `ensures` until it rules it out, "
                  "or correct the test.", "", c["program"].rstrip()]
    elif s is None:
        lines.append("NOT PROVED: " + r["why"] + ".")
    else:
        lines.append(f"PROVED: by {s['proved by']} of 7 provers ({', '.join(s['provers'])}); none refutes it."
                     + (f" Undecided: {', '.join(s['undecided'])}." if s["undecided"] else "")
                     + f" The body was written by {r['wrote the body']}; the specification is yours, unchanged."
                     + (f" It passes your {r['tests']} test{'s' if r['tests'] != 1 else ''}." if r.get("tests") else ""))
        q = s["specification"]
        if q.get("completeness") is None:
            lines.append("How much your specification pins down could not be measured here"
                         + (f" ({q['why']})." if q.get("why") else " (no input of its domain could be tried)."))
        else:
            share = f"{100 * q['completeness']:.0f}%"
            if q["completeness"] >= WEAK:
                lines.append(f"Your specification rejects {share} of the {q['mutants']} wrong results tried on {q['inputs']} inputs.")
            else:
                lines.append(f"Your specification says little: it rejects only {share} of the {q['mutants']} wrong results tried "
                             f"on {q['inputs']} inputs. The proof is real, and it is a proof of this weak statement.")
            w = q.get("witness")
            if w:
                args = ", ".join(f"{k} = {_value(v)}" for k, v in w["args"].items())
                lines.append(f"For {args} the program returns {_value(w['right'])}, and your specification would also accept "
                             f"{_value(w['also_accepted'])}. If that is not what you mean, add an `ensures` that rules it out.")
        lines += ["", s["program"].rstrip()]
        py = s.get("python") or {}
        if py.get("source"):
            lines += ["", f"The same function in Python. It is translated from the proved program and gave the same answer on "
                          f"{py['inputs']} inputs{gate._refusing(py)}; the proof is of the t program above, and the Python "
                          f"is tested against it, not proved.", "", py["source"].rstrip()]
        elif py:
            lines += ["", f"No Python version is shown: {py['why']}."]
    if r["refused"]:
        lines += ["", f"Of {r['answers asked']} answers asked for, not shown:" if r["answers asked"] else "Not shown:"]
        lines += ["  " + x for x in r["refused"]]
    said = (r.get("dafny says") or {}).get("lines")
    if s is None and not c and said:
        about = f"answer {r['dafny says']['answer']}" if r["answers asked"] else "the program"
        lines += ["", f"What Dafny reports about {about} (a clause of your specification named here is yours to change):"]
        lines += ["  " + x for x in said]
    return "\n".join(lines)


# ------------------------------------------------------------------- spec --

def propose(entry: dict, student, python, prompt_version: str = "s2", answers: int = 5, max_new: int = 1024) -> dict:
    """Candidate specifications for a question in words: {"specifications": [...], "refused": [...]}; each
    specification is {"text" (the task with an empty body), "written by" (answers), "tests", "draws",
    "completeness"}, best first."""
    question = se.build_prompt(entry, prompt_version)
    replies = [student([question], 0.0, 0, "q", max_new)[0][0]]
    for seed in range(1, answers):
        replies.append(student([question], TEMPERATURE, seed, "q", max_new)[0][0])
    kept, refused = gate.candidates(replies, entry)
    out = {"question": entry["rec"]["text"], "fn": entry["fn"], "answers asked": len(replies), "refused": refused,
           "specifications": []}
    if not kept:
        return dict(out, why="no answer parsed, was well formed and passed the question's tests")
    code, _counts = spec_first.written_python(python, ["q"], {"q": entry}, 3, 1, 768)
    groups: dict[str, dict] = {}
    for c in kept:
        v = spec_gate.judge_all(c["task"], entry, code.get("q"), [])
        if not v["passes"]:
            refused.append(f"answer {c['n']}: {v['why']}")
            continue
        key = student_rows._normalised(c["task"], False)
        a = v.get("agreement", {})
        g = groups.setdefault(key, {"text": surface.print_task(dict(c["task"], body=[])).strip(), "written by": [],
                                    "tests": len(entry["points"]), "draws": a.get("draws"),
                                    "completeness": a.get("completeness")})
        g["written by"].append(c["n"])
    ranked = sorted(groups.values(), key=lambda g: (-(g["completeness"] if isinstance(g["completeness"], (int, float)) else 1.0),
                                                    -len(g["written by"]), g["written by"][0]))
    out["specifications"] = ranked
    if not ranked:
        out["why"] = "no answer's specification could be supported without a reference"
    return out


def render_specs(r: dict) -> str:
    lines = []
    specs = r["specifications"]
    if not specs:
        lines.append("NO SPECIFICATION: " + r["why"] + ".")
    else:
        lines.append(f"{len(specs)} specification{'s' if len(specs) != 1 else ''} for {r['fn']}, each true of the question's "
                     f"tests and of an independently written Python solution's answers on drawn inputs. Read them: "
                     f"the one you pick is what will be proved.")
        for k, g in enumerate(specs, 1):
            share = (f"{100 * g['completeness']:.0f}%" if isinstance(g["completeness"], (int, float)) else "every judged one")
            lines += ["", f"[{k}] written by {len(g['written by'])} of {r['answers asked']} answers; holds on {g['tests']} "
                          f"test(s) and {g['draws']} drawn inputs; rejects {share} of the wrong results tried.", "", g["text"]]
    if r["refused"]:
        lines += ["", f"Of {r['answers asked']} answers asked for, not used:"] + ["  " + x for x in r["refused"]]
    return "\n".join(lines)


# ------------------------------------------------------------------- main --

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prove")
    p.add_argument("--student", required=True, help="host:port of the server holding the model")
    p.add_argument("--student-name", default="student")
    p.add_argument("--spec", type=Path, required=True, help="a file with one t task: the specification, body empty")
    p.add_argument("--answers", type=int, default=5)
    p.add_argument("--test", action="append", default=[], help="your own example, an `assert f(arguments) == value` line; repeat")
    p.add_argument("--jobs", type=int, default=2, help="provers at once")
    p.add_argument("--save-python", type=Path, metavar="FILE")
    p.add_argument("--save-t", type=Path, metavar="FILE", help="write the proved t program here")
    p.add_argument("--certificate", type=Path, metavar="FILE",
                   help="write the proof's certificate here, for `dawnr check` to replay without the model")
    p.add_argument("--json", type=Path)
    s = sub.add_parser("spec")
    s.add_argument("--student", required=True)
    s.add_argument("--python", required=True, help="host:port of the server holding the Python writer (the base model)")
    s.add_argument("--student-name", default="student")
    s.add_argument("--python-name", default="base")
    s.add_argument("--text", required=True, help="the question, in words")
    s.add_argument("--test", action="append", default=[], help="an `assert f(arguments) == value` line; repeat")
    s.add_argument("--prompt", choices=se.PROMPT_VERSIONS, default="s2")
    s.add_argument("--answers", type=int, default=5)
    s.add_argument("--save", type=Path, metavar="FILE", help="write a specification here, body empty, for `prove`")
    s.add_argument("--pick", type=int, default=1, help="which specification --save writes (1 is the first shown)")
    s.add_argument("--json", type=Path)
    a = ap.parse_args(argv)
    if a.cmd == "prove":
        try:
            spec = read_spec(a.spec.read_text(encoding="utf-8"))
            tests = read_tests(a.test, spec)
        except OSError as error:
            raise SystemExit(f"prove: cannot read {a.spec}: {error.strerror}")
        except Refused as refused:
            raise SystemExit(f"prove: {refused}")
        student = None if spec.get("body") else python_beside.api_decode("openai", [a.student], a.student_name)
        r = prove(spec, student, a.answers, jobs=a.jobs, tests=tests)
        print(render_proof(r))
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
                print(f"\nPython written to {a.save_python}")
            else:
                print(f"\nNothing written to {a.save_python}: there is no checked Python for this specification.", file=sys.stderr)
        if a.certificate:
            import certificate
            made = certificate.from_proof(r, a.test)
            if made:
                certificate.write(a.certificate, made)
                print(f"\nCertificate written to {a.certificate}; `dawnr check` replays it on any machine, without the model.")
            else:
                print(f"\nNothing written to {a.certificate}: nothing was proved.", file=sys.stderr)
        return 0 if r["shown"] else 1
    try:
        entry = gate.entry_of(a.text, a.test)
    except ValueError as error:
        raise SystemExit(f"spec: {error}")
    r = propose(entry, python_beside.api_decode("openai", [a.student], a.student_name),
                python_beside.api_decode("openai", [a.python], a.python_name), a.prompt, a.answers)
    print(render_specs(r))
    if a.json:
        a.json.write_text(json.dumps(r, indent=1, default=str) + "\n", encoding="utf-8")
    if a.save:
        specs = r["specifications"]
        if 1 <= a.pick <= len(specs):
            a.save.write_text(specs[a.pick - 1]["text"] + "\n", encoding="utf-8")
            print(f"\nSpecification {a.pick} written to {a.save}. Prove it with:  dawnr prove {a.save}")
        else:
            print(f"\nNothing written to {a.save}: there is no specification {a.pick}.", file=sys.stderr)
    return 0 if r["specifications"] else 1


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
