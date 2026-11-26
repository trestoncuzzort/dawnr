#!/usr/bin/env python3
"""t/verify_panel.py -- `dawnr verify` on a panel of functions, one record per function in a run folder (2026-11-26).

    python3 t/verify_panel.py --student HOST:PORT --run DIR [--student-name NAME] [--reference] [--max-new 1024]
        [--whole 5] [--specs 3] [--answers 3] [--jobs 2] [--kernels dafny] [--ids 106,206]

Why. The two panel runs of 2026-10-05 (V1 and V4 of t/PREDICT-2026-10-05-verify-python.md) left their totals and
nothing else: 9 of 111 proved, and of the 102 refused, 88 for want of a specification that held at the function's
own answers and 14 for want of a proved body. Which function stopped where, and why, could not be read afterwards,
so whether a refusal was the model's specification, the proof, or `t` itself was never counted. This is the panel
driver those runs did not commit, written so that a run leaves what it found.

The panel is the one those runs used: the wider 111 (`heldout_audit.wider_clean()`, pool v7's additions), each
problem's reference solution as the Python file, its words as the docstring and its tests as the examples. Every
function is asked exactly as `dawnr verify FILE.py --test ...` asks it (t/verify_py.py `entry_for` and `verify`).

The run folder holds `run.json` (what was asked, of which model, at which commit, and the totals when the run
ends) and one `ID.json` per function:

  verified, route, why     whether a proved twin was found, by which route, and if not, the reason verify gives
  twin                     the proved twin as verify shows it: the program, its specification, the provers' cells,
                           what it was held to, and its Python when the hand-back writes one
  stages                   one entry per refusal line, in order: the route, the attempt (`answer 2`,
                           `specification 1, body 3`), the stage it stopped at (verify_py.STAGES) and the reason,
                           with what it was tried on (the input where a specification was false, the cells of a
                           prover row, the inputs a body was compared on)
  specifications           for the specification route, every specification written and its verdict and scores,
                           and for each kept one what holding it against the function found
  candidates               for the whole-answer route, what holding each candidate against the function found
  inputs                   the examples, whether they were taken from the function, their kinds, and the seed and
                           counts of the drawn inputs the specification check uses
  stopped at               the furthest stage any attempt reached (verify_py.STAGES), for a refused function

A run taken up again keeps the records it has and asks only for the functions that have none. A function whose
check raised (the provers did not finish, the sandbox failed) is a record too, with the error, and the run goes on.
"""
from __future__ import annotations

import argparse
import inspect
import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import answer as gate                                           # noqa: E402
import heldout_audit                                            # noqa: E402
import spec_experiment as se                                    # noqa: E402
import spec_gate                                                # noqa: E402
import verify_py                                                # noqa: E402

MANIFEST = "run.json"


def problems(ids: set[int] | None = None) -> list[dict]:
    """The wider 111, as the runs of 2026-10-05 asked them: {"id", "fn", "code", "text", "tests"}, in id order."""
    pool = se.wider_pool()
    out = []
    for tid in sorted(heldout_audit.wider_clean()):
        if ids is not None and tid not in ids:
            continue
        p = pool[tid]
        out.append({"id": tid, "fn": p["fn"], "code": p["rec"]["code"], "text": p["rec"]["text"],
                    "tests": list(p["rec"]["test_list"])})
    return out


def function_of(problem: dict) -> dict:
    """The problem's reference read as verify reads a file, with the problem's words as its docstring."""
    f = verify_py.read_function(problem["code"], problem["fn"])
    return dict(f, doc=problem["text"])


def _check_settings() -> dict:
    """The seed and counts spec_gate.judge draws with when verify calls it (its own defaults)."""
    p = inspect.signature(spec_gate.judge).parameters
    return {"seed": p["seed"].default, "draws": p["n"].default, "larger draws": p["beyond"].default}


def _stopped_at(stages: list[dict]) -> str | None:
    known = [s["stage"] for s in stages if s["stage"] in verify_py.STAGES]
    return max(known, key=verify_py.STAGES.index) if known else None


def record(problem: dict, function: dict | None, entry: dict | None, drawn: bool, r: dict | None,
           error: str | None = None, entry_refused: str | None = None, seconds: float | None = None) -> dict:
    """One function's record (the module docstring says what each field holds)."""
    r = r or {}
    stages = list(r.get("stages", []))
    if entry_refused is not None:
        stages.append({"route": None, "source": "the function", "stage": "entry", "reason": entry_refused})
    if error is not None:
        stages.append({"route": None, "source": "the run", "stage": "error", "reason": error})
    shown = r.get("shown")
    asked = {k: r[f"{k} asked"] for k in ("answers", "specifications", "bodies") if f"{k} asked" in r}
    out = {"id": problem["id"], "fn": problem["fn"], "verified": bool(shown), "route": r.get("route") if shown else None,
           "why": None if shown else (r.get("why") or entry_refused or error), "twin": shown, "stages": stages,
           "refused": list(r.get("refused", [])), "specifications": r.get("specifications", []),
           "candidates": r.get("candidates", []), "asked": asked,
           "inputs": {"examples": list(entry["rec"]["test_list"]) if entry else list(problem["tests"]),
                      "taken from the function": drawn,
                      "kinds": ([{"args": [k for k, _v in p["args"]], "expected": p["expected"][0]} for p in entry["points"]]
                                if entry else None),
                      "specification check": _check_settings()},
           "stopped at": None if shown else _stopped_at(stages),
           "function": ({"code": function["code"], "doc": function["doc"]} if function
                        else {"code": problem["code"], "doc": problem["text"]})}
    if error is not None:
        out["error"] = error
    if seconds is not None:
        out["seconds"] = round(seconds, 1)
    return out


def _write(path: Path, value: dict) -> None:
    """Written whole, as spec_experiment writes a raw record (a run stopped mid-write leaves no half record to be
    taken for one); a value JSON has no word for is written as its text."""
    se.write_record(path, json.loads(json.dumps(value, default=str)))


def _commit() -> str | None:
    try:
        return subprocess.run(["git", "-C", str(HERE), "rev-parse", "HEAD"], capture_output=True, text=True,
                              timeout=10).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def one(problem: dict, student, prover, settings: dict) -> dict:
    """Ask verify about one problem and return its record; nothing it raises ends the run."""
    start = time.monotonic()
    function = entry = r = None
    drawn = False
    try:
        function = function_of(problem)
        try:
            entry, drawn = verify_py.entry_for(function, list(problem["tests"]))
        except verify_py.Refused as refused:
            return record(problem, function, None, False, None, entry_refused=str(refused), seconds=time.monotonic() - start)
        r = verify_py.verify(entry, function, student, prover=prover, **settings)
    except verify_py.Refused as refused:
        return record(problem, function, entry, drawn, None, entry_refused=str(refused), seconds=time.monotonic() - start)
    except Exception as error:                                  # noqa: BLE001 -- recorded, and the run goes on
        return record(problem, function, entry, drawn, r, error=f"{type(error).__name__}: {error}"[:300],
                      seconds=time.monotonic() - start)
    return record(problem, function, entry, drawn, r, seconds=time.monotonic() - start)


def summary(records: list[dict]) -> dict:
    refused = [x for x in records if not x["verified"] and not x.get("error")]
    return {"functions": len(records), "verified": sum(1 for x in records if x["verified"]), "refused": len(refused),
            "errors": sum(1 for x in records if x.get("error")),
            "stopped at": dict(sorted(Counter(x["stopped at"] for x in refused).items(),
                                      key=lambda kv: verify_py.STAGES.index(kv[0]) if kv[0] in verify_py.STAGES else 99))}


def run(problems_: list[dict], run_dir: Path, student, prover=gate.prove, settings: dict | None = None,
        about: dict | None = None, say=lambda line: None) -> dict:
    """Every problem's record in `run_dir` (made if absent), `run.json` beside them; the totals."""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    settings = dict(settings or {})
    manifest = {"about": dict(about or {}), "ids": [p["id"] for p in problems_], "settings": settings,
                "commit": _commit(), "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "done": None}
    _write(run_dir / MANIFEST, manifest)
    records = []
    for n, problem in enumerate(problems_, 1):
        path = run_dir / f"{problem['id']}.json"
        if path.exists():
            records.append(json.loads(path.read_text(encoding="utf-8")))
            continue
        rec = one(problem, student, prover, settings)
        _write(path, rec)
        records.append(rec)
        say(f"verify_panel: {n} of {len(problems_)}: {problem['id']} {problem['fn']}: "
            + ("VERIFIED" if rec["verified"] else f"stopped at {rec['stopped at']}") + f" ({rec.get('seconds')} s)")
    done = summary(records)
    _write(run_dir / MANIFEST, dict(manifest, done=done, ended=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))
    return done


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--student", required=True, help="host:port of the server holding the model")
    ap.add_argument("--student-name", default="student")
    ap.add_argument("--run", type=Path, required=True, help="the run folder: one record per function is written here")
    ap.add_argument("--reference", action="store_true",
                    help="the writer has never seen t: put the language's reference before each question")
    ap.add_argument("--max-new", type=int, default=1024)
    ap.add_argument("--whole", type=int, default=5)
    ap.add_argument("--specs", type=int, default=3)
    ap.add_argument("--answers", type=int, default=3)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--kernels", default="", help="comma-separated provers to ask (default: every one installed)")
    ap.add_argument("--ids", default="", help="comma-separated problem ids (default: the whole panel)")
    a = ap.parse_args(argv)
    os.environ.setdefault("T_MIN_KERNELS", "1")                 # as `dawnr verify` runs it (bin/dawnr)
    import python_beside
    student = python_beside.api_decode("openai", [a.student], a.student_name)
    if a.reference:
        student = python_beside.referenced(student)
    ids = {int(x) for x in a.ids.split(",") if x.strip()} or None
    settings = {"whole": a.whole, "specs": a.specs, "answers": a.answers, "max_new": a.max_new, "jobs": a.jobs}
    about = {"student": a.student, "student name": a.student_name, "reference": a.reference,
             "kernels": a.kernels or "installed", "T_MIN_KERNELS": os.environ["T_MIN_KERNELS"]}
    done = run(problems(ids), a.run, student, prover=lambda tasks, jobs: gate.prove(tasks, jobs, kernels=a.kernels),
               settings=settings, about=about, say=lambda line: print(line, flush=True))
    print(json.dumps(done, indent=1))
    return 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
