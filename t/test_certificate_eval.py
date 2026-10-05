"""t/certificate_eval.py: each forgery changes one thing and keeps the digests honest, and the replay's verdicts
are tallied (the prover is a stand-in; the real one is exercised by test_certificate.py)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import certificate  # noqa: E402
import certificate_eval as ce  # noqa: E402
import py_sandbox  # noqa: E402
import surface  # noqa: E402

PROGRAM = """t 1
gate loops
task largest(s: seq) returns (r: int)
  requires len(s) > 0
  ensures forall i in [0, len(s)) . r >= s[i]
  ensures exists i in [0, len(s)) . r == s[i]
{
  r := s[0];
  var i: int := 1;
  while i < len(s)
    invariant 1 <= i and i <= len(s)
    invariant forall j in [0, i) . r >= s[j]
    invariant exists j in [0, i) . r == s[j]
    decreases len(s) - i
  {
    if s[i] > r {
      r := s[i];
    } else {
    }
    i := i + 1;
  }
}
"""
PYTHON = "def largest(s):\n    s = tuple(s)\n    _t_result = _t_core(s)\n    return _t_result\n\ndef _t_core(s):\n    return max(s)\n"


def made() -> dict:
    predicate = {"version": 1, "kind": "prove", "function": "largest", "question": None, "tests": ["assert largest([3, 9, 2]) == 9"],
                 "program": PROGRAM, "specification": certificate.spec_lines(PROGRAM), "proved": {"by": ["dafny"], "cells": {}},
                 "python": {"source": PYTHON, "function": "largest", "inputs": 10}, "measured": None}
    return ce.redigest({"_type": certificate.STATEMENT, "predicateType": certificate.PREDICATE, "predicate": predicate, "subject": []})


def test_each_forgery_changes_one_thing_and_takes_every_digest_again():
    cert = made()
    for how in ce.FORGERIES:
        forged, note = ce.forge(cert, how)
        assert forged is not None and note
        subject = {s["name"]: s["digest"]["sha256"] for s in forged["subject"]}
        assert subject == {name: certificate.digest(text) for name, text in certificate._artifacts(forged["predicate"])}
        changed = [k for k in ("program", "specification", "python") if forged["predicate"][k] != cert["predicate"][k]]
        assert changed == {"twin": ["program"], "spec": ["program", "specification"], "python": ["python"]}[how]
    assert cert == made()                                       # the certificate handed in is left as it was
    twin = surface.parse(ce.forge(cert, "twin")[0]["predicate"]["program"])
    assert twin["ensures"] == surface.parse(PROGRAM)["ensures"] and twin["body"] != surface.parse(PROGRAM)["body"]
    nothing = ce.forge(cert, "spec")[0]["predicate"]
    assert nothing["specification"] == ["requires len(s) > 0", "ensures r == r"] and surface.parse(nothing["program"])["body"] == surface.parse(PROGRAM)["body"]
    assert "_t_result = _t_one_off(_t_result)" in ce.forge(cert, "python")[0]["predicate"]["python"]["source"]


def test_a_certificate_without_python_is_not_forged_that_way():
    cert = made()
    cert["predicate"]["python"] = None
    assert ce.forge(ce.redigest(cert), "python") == (None, "the certificate carries no Python")


@pytest.mark.skipif(not py_sandbox.available(), reason="the recorded Python only runs in a sandbox")
def test_the_replay_rejects_every_forgery_and_keeps_the_one_as_written(monkeypatch):
    proved = {"dafny": "verified / refuted"}
    monkeypatch.setattr(ce, "prove", lambda tasks, jobs=2, kernels="": {t["name"]: dict(proved) for t in tasks})
    r = ce.evaluate(made(), "dafny")
    assert r["as written"]["verdict"] == certificate.REPRODUCED and r["as written"]["proved here"] == ["dafny"]
    # the twin fails a recorded test or breaks the specification at an input the replay finds, before any prover
    # is asked; the Python one off no longer answers as the program
    assert r["forged"]["twin"]["verdict"] == certificate.FAILED and r["forged"]["twin"]["stopped at"].split(":")[0] in ("tests", "counterexample")
    assert r["forged"]["python"]["verdict"] == certificate.FAILED and r["forged"]["python"]["stopped at"].startswith("python")
    s = ce.summarize([r])
    assert s["certificates"] == 1 and s["as written"] == {certificate.REPRODUCED: 1} and s["forged"]["twin"] == {certificate.FAILED: 1}


def test_the_command_writes_the_rows_and_the_tally(tmp_path, monkeypatch, capsys):
    f = tmp_path / "a.cert.json"
    f.write_text(json.dumps(made()))
    monkeypatch.setattr(ce, "evaluate", lambda cert, kernels, jobs: {"function": "largest", "kind": "prove", "as written": {"verdict": "REPRODUCED"},
                                                                    "forged": {h: {"made": True, "verdict": "FAILED"} for h in ce.FORGERIES}})
    assert ce.main([str(f), "--out", str(tmp_path / "r.json")]) == 0
    report = json.loads((tmp_path / "r.json").read_text())
    assert report["summary"]["forged"] == {h: {"FAILED": 1} for h in ce.FORGERIES} and report["rows"][0]["file"] == "a.cert.json"
    assert "a.cert.json: as written REPRODUCED; twin FAILED; spec FAILED; python FAILED" in capsys.readouterr().out
