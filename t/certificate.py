#!/usr/bin/env python3
"""t/certificate.py -- the record of a shown answer, and the check that replays it without the model (2026-10-05).

    python3 t/certificate.py check FILE [--spec SPEC.t] [--jobs 2] [--json OUT]

`dawnr ask ... --certificate FILE` and `dawnr prove ... --certificate FILE` write one; `dawnr check FILE` is this.

Why. A proved answer is worth what a second party can establish again without the party that produced it.
Proof-carrying code (Necula and Lee, "Safe kernel extensions without run-time checking", 1996) ships the proof
with the code, the consumer validates it against its own policy, and a tampered code or proof is "either invalid
or harmless". Five of the seven provers here are SMT-backed and leave no small proof object to ship, so the
certificate carries what makes the proof findable again (the program with its specification and invariants, the
tests, the Python handed back, the independently written Python the specification was held against) and the
consumer runs the provers it has. Research receipt 36ee1c1294d6.

The file is an in-toto Statement (github.com/in-toto/attestation, spec/v1/statement.md): `subject` names each
artifact with its SHA-256, `predicateType` is PREDICATE, and `predicate` is the record. It is plain JSON, so the
usual envelopes (DSSE, Sigstore, `ssh-keygen -Y sign`) sign it as it is. A signature says who made it; nothing
below depends on one, because nothing below takes the certificate's word.

What `check` does again, none of it with a model:

  digests        each subject's SHA-256 is that of the text the predicate carries
  program        it parses and is well formed (the gate's own checks)
  specification  the `requires` and `ensures` lines listed for the reader are the program's own; with --spec FILE,
                 the program keeps that file's specification unchanged (t/spec_given.kept)
  tests          the program passes every recorded test in the interpreter
  counterexample the interpreter's bounded search for an input where the program breaks its own specification
                 (t/harness.real_witness); one found fails the certificate with that input, and no prover is run
  proof          the provers on this machine are run on the program and on its sabotaged twin (t/run_par.py). One
                 that refutes the program fails the certificate; a prover the certificate names and this machine
                 lacks is reported as not checked here, never counted
  python         the Python in the certificate answers as the proved program does, in the sandbox, on the tests
                 and on inputs drawn from the program's own domain (t/to_python.check)
  measured       what was said about the specification is measured again: from a question, that it holds at the
                 recorded independent Python's answers on drawn inputs and rejects wrong outputs (t/spec_gate.py);
                 from a specification, the share of wrong results it rejects (t/prove.pins_down)

The verdict is `reproduced` (nothing failed and at least one prover here proved it and refuted its twin), `failed`
(something recorded did not hold), or `undecided here` (nothing failed and no prover here finished a proof).
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import answer as gate                                           # noqa: E402
import fuzz_lower                                               # noqa: E402
import harness                                                  # noqa: E402
import interp                                                   # noqa: E402
import py_sandbox                                               # noqa: E402
import score_levels                                             # noqa: E402
import spec_check                                               # noqa: E402
import spec_experiment as se                                    # noqa: E402
import spec_gate                                                # noqa: E402
import spec_given                                               # noqa: E402
import surface                                                  # noqa: E402
import to_python                                                # noqa: E402

STATEMENT = "https://in-toto.io/Statement/v1"
PREDICATE = "urn:dawnr:certificate:v1"
VERSION = 1
ABSENT = "—"              # run_par.format_table's cell for a prover that is not installed
REPRODUCED, FAILED, UNDECIDED = "reproduced", "failed", "undecided here"
OK, BAD, SKIPPED = "ok", "FAILED", "not checked here"


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def spec_lines(program: str) -> list[str]:
    """The lines a reader is shown as the specification: the program's own `requires` and `ensures`."""
    return [l.strip() for l in program.splitlines() if l.strip().startswith(("requires ", "ensures "))]


def _artifacts(predicate: dict) -> list[tuple[str, str]]:
    """(subject name, text) for every artifact the predicate carries."""
    out = [("program.t", predicate.get("program") or "")]
    if (predicate.get("python") or {}).get("source"):
        out.append(("function.py", predicate["python"]["source"]))
    if predicate.get("reference python"):
        out.append(("reference.py", predicate["reference python"]))
    return out


def _versions() -> dict[str, str]:
    """prover -> the version it reports on this machine; a missing one is left out."""
    import run_par
    cols, _present = run_par.probe_backends()
    return {name: version for name, version in cols if not str(version).startswith("ABSENT")}


def _commit() -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(HERE), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=10)
    except Exception:                                           # noqa: BLE001 -- provenance only
        return None
    return r.stdout.strip() or None


def make(*, kind: str, function: str, shown: dict, question: str | None = None, tests=(), reference_python: str | None = None,
         measured: dict | None = None, versions: dict | None = None, now: str | None = None) -> dict:
    """The certificate for a shown answer. `shown` is the gate's own record of it (answer.answer's or
    prove.prove's `shown`); `versions` and `now` are read from this machine when not given."""
    python = shown.get("python") or {}
    predicate = {
        "version": VERSION,
        "kind": kind,
        "function": function,
        "question": question,
        "tests": [t.strip() for t in tests],
        "program": shown["program"],
        "specification": spec_lines(shown["program"]),
        "proved": {"by": list(shown.get("provers") or []), "cells": dict(shown.get("cells") or {})},
        "python": ({"source": python["source"], "function": python.get("function") or function, "inputs": python.get("inputs")}
                   if python.get("source") else None),
        "reference python": reference_python,
        "measured": measured,
        "made": {"at": now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "provers": _versions() if versions is None else versions, "dawnr": _commit()},
    }
    return {"_type": STATEMENT,
            "subject": [{"name": name, "digest": {"sha256": digest(text)}} for name, text in _artifacts(predicate)],
            "predicateType": PREDICATE, "predicate": predicate}


def from_answer(r: dict, **kw) -> dict | None:
    """The certificate of `dawnr ask`'s shown answer (answer.answer's result); None when nothing was shown."""
    s = r.get("shown")
    if not s:
        return None
    return make(kind="ask", function=r["fn"], question=r.get("question"), tests=r.get("tests") or (), shown=s,
                reference_python=r.get("python beside it"), measured=s.get("behind the specification"), **kw)


def from_proof(r: dict, tests=(), **kw) -> dict | None:
    """The certificate of `dawnr prove`'s proved body (prove.prove's result); None when nothing was shown."""
    s = r.get("shown")
    if not s:
        return None
    return make(kind="prove", function=r["name"], tests=tests or (), shown=s, measured=s.get("specification"), **kw)


def write(path: Path, certificate: dict) -> None:
    path.write_text(json.dumps(certificate, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def _well_formed(program: str) -> tuple[dict | None, str]:
    """(the task, "") when the text is one well-formed t task, else (None, why): proof_repair.cheap's reading."""
    try:
        task = surface.parse(program.strip() + "\n")
    except Exception as error:                                  # noqa: BLE001 -- the parser's message is the finding
        return None, f"it does not parse: {error}"[:200]
    try:
        errs = fuzz_lower.check_wf(task)
    except Exception as error:                                  # noqa: BLE001
        errs = [str(error)]
    if errs:
        return None, f"it is not well formed: {errs[0]}"[:200]
    return task, ""


def _same(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return abs(a - b) < 1e-9
    return a == b


def _measured_again(predicate: dict, task: dict, entry: dict | None) -> tuple[str, str]:
    """(result, detail) for what the certificate says about the specification."""
    said = predicate.get("measured") or {}
    if predicate.get("kind") == "ask":
        code = predicate.get("reference python")
        if not code or entry is None:
            return BAD, "a question's certificate needs its tests and the independent Python the specification was held against"
        if not py_sandbox.available():
            return SKIPPED, f"the recorded Python only runs in a sandbox, and {py_sandbox.why_unavailable()}"
        v = spec_gate.judge(task, entry, code)
        a = v.get("agreement") or {}
        if not v.get("passes"):
            return BAD, f"the specification is not supported by the recorded Python: {v.get('why')}"
        detail = (f"the specification holds at the recorded Python's answer on {a.get('draws')} drawn inputs and rejects "
                  + (f"{100 * a['completeness']:.0f}%" if isinstance(a.get("completeness"), (int, float)) else "every judged one")
                  + " of the wrong outputs tried")
        for key, mine in (("agrees with the Python on", a.get("draws")), ("mutated outputs rejected", a.get("completeness"))):
            if key in said and not _same(said[key], mine):
                return BAD, f"{detail}; the certificate says {said[key]!r} for \"{key}\""
        return OK, detail
    import prove
    again = prove.pins_down(task)
    c = again.get("completeness")
    detail = ("no wrong result could be judged" if c is None else
              f"the specification rejects {100 * c:.0f}% of {again['mutants']} wrong results on {again['inputs']} inputs")
    if "completeness" in said and not _same(said.get("completeness"), c):
        return BAD, f"{detail}; the certificate says {said.get('completeness')!r}"
    return OK, detail


def check(certificate: dict, prover=None, jobs: int = 2, spec: dict | None = None) -> dict:
    """Replay a certificate. {"verdict", "steps": [{"what", "result", "detail"}], "proved here": [...], ...}.
    `prover` has answer.prove's shape; `spec` is a specification the program must keep (read_spec's task)."""
    steps: list[dict] = []
    out = {"verdict": FAILED, "steps": steps, "proved here": [], "function": None, "specification": []}

    def step(what: str, result: str, detail: str = "") -> bool:
        steps.append({"what": what, "result": result, "detail": detail})
        return result != BAD

    predicate = certificate.get("predicate") if isinstance(certificate, dict) else None
    if (not isinstance(predicate, dict) or certificate.get("_type") != STATEMENT or certificate.get("predicateType") != PREDICATE
            or predicate.get("version") != VERSION or not isinstance(predicate.get("program"), str)):
        step("certificate", BAD, f"not a dawnr certificate of version {VERSION}")
        return out
    out["function"], out["specification"] = predicate.get("function"), spec_lines(predicate["program"])
    recorded = {s.get("name"): (s.get("digest") or {}).get("sha256") for s in certificate.get("subject") or [] if isinstance(s, dict)}
    wrong = [name for name, text in _artifacts(predicate) if recorded.get(name) != digest(text)]
    if not step("digests", BAD if wrong else OK, f"{', '.join(wrong)} is not the text its digest was taken of" if wrong else ""):
        return out
    task, why = _well_formed(predicate["program"])
    if not step("program", OK if task else BAD, why):
        return out
    listed = list(predicate.get("specification") or [])
    step("specification", OK if listed == out["specification"] else BAD,
         "" if listed == out["specification"] else "the specification listed for the reader is not the program's own")
    if spec is not None:
        changed = spec_given.kept(spec, task)
        step("specification kept", BAD if changed is not None else OK,
             f"the program does not keep the given specification: {changed}" if changed is not None else "")
    tests, entry = list(predicate.get("tests") or []), None
    if tests:
        try:
            entry = gate.entry_of(predicate.get("question") or "", tests)
        except ValueError as error:
            step("tests", BAD, f"the recorded tests cannot be read: {error}"[:200])
        else:
            verdicts = [se.run_point(task, p)["verdict"] for p in entry["points"]]
            failed = [t for t, v in zip(tests, verdicts) if v != "pass"]
            step("tests", BAD if failed else OK, f"the program fails `{failed[0]}`" if failed else f"{len(tests)} pass")
    try:
        witness = harness.real_witness(task)
    except Exception:                                           # noqa: BLE001 -- the search is a quick refutation, not a gate
        witness = None
    if witness:
        at = ", ".join(f"{k} = {json.dumps(interp._j(v))}" for k, v in witness.items() if not k.startswith("_"))
        step("counterexample", BAD, f"the program breaks its own specification at {at}")
    else:
        step("counterexample", OK, "none found")
    if any(s["result"] == BAD for s in steps):                  # already decided: a prover run would add minutes and nothing
        return out
    name = f"answer_1__{predicate.get('function') or task['name']}"
    cells = (prover or gate.prove)([se.rename_task(copy.deepcopy(task), name)], jobs)
    row = cells.get(name) or {}
    out["cells"] = row
    refuting = sorted(k for k, cell in row.items() if str(cell).split(" / ")[0] == "refuted")
    here = sorted(k for k, cell in row.items() if cell == score_levels.VERIFIED)
    claimed = list((predicate.get("proved") or {}).get("by") or [])
    missing = sorted(k for k in spec_check.KERNELS if row.get(k, ABSENT) == ABSENT)
    unfinished = {k: row[k] for k in sorted(row) if k not in here and k not in missing and k not in refuting}
    if refuting:
        step("proof", BAD, f"refuted by {', '.join(refuting)}")
    else:
        said = f"proved by {', '.join(here)}, the sabotaged twin refuted" if here else "no prover here proved it"
        if [k for k in claimed if k in missing]:
            said += f"; named by the certificate and not installed here: {', '.join(k for k in claimed if k in missing)}"
        if unfinished:
            said += "; not finished here: " + ", ".join(f"{k} ({cell})" for k, cell in unfinished.items())
        step("proof", OK if here else SKIPPED, said)
    out["proved here"] = here
    python = predicate.get("python") or {}
    if python.get("source"):
        if not py_sandbox.available():
            step("python", SKIPPED, f"it only runs in a sandbox, and {py_sandbox.why_unavailable()}")
        else:
            try:
                r = to_python.check(task, python["source"], python.get("function") or predicate.get("function"), tests)
            except Exception as error:                          # noqa: BLE001 -- a certificate's Python may be anything
                r = {"agrees": False, "why": f"{type(error).__name__}: {error}"}
            step("python", OK if r.get("agrees") else BAD,
                 f"the same answer as the proved program on {r.get('inputs')} inputs" if r.get("agrees")
                 else f"the Python does not answer as the proved program does ({str(r.get('why'))[:160]})")
    if predicate.get("measured") is not None or predicate.get("kind") == "ask":
        try:
            result, detail = _measured_again(predicate, task, entry)
        except Exception as error:                              # noqa: BLE001
            result, detail = BAD, f"the measurement raised {type(error).__name__}: {error}"[:200]
        step("measured", result, detail)
    if any(s["result"] == BAD for s in steps):
        out["verdict"] = FAILED
    else:
        out["verdict"] = REPRODUCED if here else UNDECIDED
    return out


_WHAT = {"certificate": "the file is a certificate", "digests": "each part is the text its digest was taken of",
         "program": "the program parses and is well formed", "specification": "the specification listed is the program's own",
         "specification kept": "the program keeps the given specification", "tests": "the recorded tests pass",
         "counterexample": "the search for an input that breaks the specification", "proof": "the provers on this machine", "python": "the Python handed back", "measured": "what was said of the specification"}


def render(report: dict) -> str:
    steps = report["steps"]
    bad = [s for s in steps if s["result"] == BAD]
    if report["verdict"] == REPRODUCED:
        n = len(report["proved here"])
        head = (f"REPRODUCED: proved here by {n} prover{'s' if n != 1 else ''} ({', '.join(report['proved here'])}), "
                f"the sabotaged twin refuted, and nothing recorded failed.")
    elif report["verdict"] == UNDECIDED:
        head = "UNDECIDED HERE: nothing recorded failed, and no prover on this machine finished a proof of it."
    else:
        head = f"FAILED: {_WHAT.get(bad[0]['what'], bad[0]['what'])}: {bad[0]['detail']}." if bad else "FAILED."
    lines = [head, ""]
    for s in steps:
        lines.append(f"  {s['result']:<16} {_WHAT.get(s['what'], s['what'])}" + (f": {s['detail']}" if s["detail"] else ""))
    if report.get("function") and report.get("specification") and report["verdict"] != FAILED:
        lines += ["", f"What it establishes: `{report['function']}` meets"] + ["  " + l for l in report["specification"]]
        lines += ["It does not establish that this specification is what was meant; that is the reader's to judge."]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="replay a certificate on this machine")
    c.add_argument("file", type=Path)
    c.add_argument("--spec", type=Path, help="a specification the program must keep unchanged (a t task, as `dawnr prove` reads)")
    c.add_argument("--jobs", type=int, default=2, help="provers at once")
    c.add_argument("--json", type=Path)
    a = ap.parse_args(argv)
    os.environ.setdefault("T_MIN_KERNELS", "1")                 # one installed prover is enough to replay with
    try:
        certificate = json.loads(a.file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"FAILED: {a.file} is not a readable certificate ({error}).")
        return 1
    spec = None
    if a.spec:
        import prove
        try:
            spec = prove.read_spec(a.spec.read_text(encoding="utf-8"))
        except (OSError, prove.Refused) as error:
            raise SystemExit(f"check: {error}")
    report = check(certificate, jobs=a.jobs, spec=spec)
    print(render(report))
    if a.json:
        a.json.write_text(json.dumps(report, indent=1, default=str) + "\n", encoding="utf-8")
    return {REPRODUCED: 0, FAILED: 1}.get(report["verdict"], 2)


if __name__ == "__main__":
    sys.exit(main())
