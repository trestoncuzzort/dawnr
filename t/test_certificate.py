"""t/certificate.py: a shown answer's record, and the check that replays it without the model. Proof-carrying
code's property is the one tested (Necula and Lee, 1996): a certificate that was altered is "either invalid or
harmless", and a prover this machine lacks is never counted."""
import copy
import functools
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import answer                                                   # noqa: E402
import certificate                                              # noqa: E402
import prove                                                    # noqa: E402
import py_sandbox                                               # noqa: E402
import run_par                                                  # noqa: E402
import spec_check                                               # noqa: E402

sandbox = pytest.mark.skipif(not py_sandbox.available(), reason="no sandbox for model-written Python here")

ALL = {k: "verified / refuted" for k in spec_check.KERNELS}
ONLY_DAFNY = {k: ("verified / refuted" if k == "dafny" else certificate.ABSENT) for k in spec_check.KERNELS}
SPEC = """t 1
gate loops
task total(a: seq) returns (r: int)
  ensures r == sum_to(a, len(a))
spec fun sum_to(s: seq, n: int): int
  decreases n
= if n <= 0 then 0 else sum_to(s, n - 1) + s[n - 1]
{
  r := 0;
  var i: int := 0;
  while i < len(a)
    invariant 0 <= i and i <= len(a)
    invariant r == sum_to(a, i)
    decreases len(a) - i
  {
    r := r + a[i];
    i := i + 1;
  }
}
"""
TESTS = ["assert total([1, 2, 3]) == 6", "assert total([]) == 0"]
VERSIONS = {"dafny": "4.11.0"}


def prover(cells_for):
    return lambda tasks, jobs: {t["name"]: cells_for(t) for t in tasks}


def proved(tests=TESTS, cells=ALL):
    spec = prove.read_spec(SPEC)
    r = prove.prove(spec, None, prover=prover(lambda t: cells), tests=prove.read_tests(tests, spec))
    assert r["shown"], r
    return certificate.from_proof(r, tests, versions=VERSIONS, now="2026-10-05T09:00:00Z")


def resealed(cert, **changes):
    """The certificate with its predicate changed and every digest taken again: what a careful forger would write."""
    c = copy.deepcopy(cert)
    c["predicate"].update(changes)
    c["subject"] = [{"name": n, "digest": {"sha256": certificate.digest(t)}} for n, t in certificate._artifacts(c["predicate"])]
    return c


def results(report):
    return {s["what"]: s["result"] for s in report["steps"]}


def test_a_certificate_is_an_in_toto_statement_naming_what_was_proved_and_by_what():
    c = proved()
    assert c["_type"] == "https://in-toto.io/Statement/v1" and c["predicateType"] == certificate.PREDICATE
    p = c["predicate"]
    assert p["kind"] == "prove" and p["function"] == "total" and p["tests"] == TESTS
    assert p["specification"] == ["ensures r == sum_to(a, len(a))"]
    assert p["proved"]["by"] == sorted(spec_check.KERNELS) and p["proved"]["cells"] == ALL
    assert p["made"] == {"at": "2026-10-05T09:00:00Z", "provers": VERSIONS, "dawnr": p["made"]["dawnr"]}
    names = {s["name"]: s["digest"]["sha256"] for s in c["subject"]}
    assert names["program.t"] == certificate.digest(p["program"])
    assert json.loads(json.dumps(c)) == c                       # plain JSON: any envelope can sign it


def test_nothing_shown_means_no_certificate():
    assert certificate.from_proof({"shown": None, "name": "total"}) is None
    assert certificate.from_answer({"shown": None, "fn": "double"}) is None


def test_the_check_replays_every_step_and_says_reproduced():
    report = certificate.check(proved(), prover=prover(lambda t: ALL))
    assert report["verdict"] == certificate.REPRODUCED and report["proved here"] == sorted(spec_check.KERNELS)
    r = results(report)
    assert r["digests"] == r["program"] == r["specification"] == r["tests"] == r["proof"] == r["measured"] == "ok"
    assert r["counterexample"] == "ok"
    text = certificate.render(report)
    assert text.startswith("REPRODUCED: proved here by 7 provers")
    assert "What it establishes: `total` meets" in text and "ensures r == sum_to(a, len(a))" in text
    assert "does not establish that this specification is what was meant" in text


def test_a_prover_this_machine_lacks_is_named_and_never_counted():
    report = certificate.check(proved(), prover=prover(lambda t: ONLY_DAFNY))
    assert report["verdict"] == certificate.REPRODUCED and report["proved here"] == ["dafny"]
    proof = next(s for s in report["steps"] if s["what"] == "proof")
    assert "proved by dafny" in proof["detail"] and "not installed here: framac, fstar, lean, rocq, spark, verus" in proof["detail"]
    assert certificate.render(report).startswith("REPRODUCED: proved here by 1 prover (dafny)")


def test_no_prover_finishing_here_is_undecided_not_reproduced_and_not_failed():
    cells = {k: ("timeout / refuted" if k == "dafny" else certificate.ABSENT) for k in spec_check.KERNELS}
    report = certificate.check(proved(), prover=prover(lambda t: cells))
    assert report["verdict"] == certificate.UNDECIDED and results(report)["proof"] == "not checked here"
    assert "not finished here: dafny (timeout / refuted)" in next(s for s in report["steps"] if s["what"] == "proof")["detail"]
    assert certificate.render(report).startswith("UNDECIDED HERE")


def test_a_prover_that_refutes_the_program_fails_the_certificate():
    report = certificate.check(proved(), prover=prover(lambda t: dict(ALL, verus="refuted / refuted")))
    assert report["verdict"] == certificate.FAILED
    assert certificate.render(report).startswith("FAILED: the provers on this machine: refuted by verus")


def test_a_program_altered_after_the_digest_was_taken_fails_before_anything_runs():
    c = proved()
    c["predicate"]["program"] = c["predicate"]["program"].replace("r := r + a[i];", "r := r + a[i] + 1;")
    called = []
    report = certificate.check(c, prover=lambda tasks, jobs: called.append(tasks) or {})
    assert report["verdict"] == certificate.FAILED and results(report) == {"digests": "FAILED"} and not called
    assert "program.t is not the text its digest was taken of" in certificate.render(report)


def test_a_resealed_wrong_program_fails_its_recorded_test_and_no_prover_is_asked():
    c = proved()
    forged = resealed(c, program=c["predicate"]["program"].replace("r := r + a[i];", "r := r + a[i] + 1;"))
    called = []
    report = certificate.check(forged, prover=lambda tasks, jobs: called.append(tasks) or {})
    assert report["verdict"] == certificate.FAILED and results(report)["tests"] == "FAILED" and not called
    assert "the program fails `assert total([1, 2, 3]) == 6`" in certificate.render(report)


def test_a_resealed_wrong_program_with_no_tests_is_caught_breaking_its_own_specification():
    c = proved(tests=[])
    forged = resealed(c, program=c["predicate"]["program"].replace("r := r + a[i];", "r := r + a[i] + 1;"))
    called = []
    report = certificate.check(forged, prover=lambda tasks, jobs: called.append(tasks) or {})
    assert report["verdict"] == certificate.FAILED and not called
    bad = next(s for s in report["steps"] if s["what"] == "counterexample")
    assert bad["result"] == "FAILED" and "the program breaks its own specification at a = " in bad["detail"]


def test_a_specification_listed_for_the_reader_that_is_not_the_programs_fails():
    forged = resealed(proved(), specification=["ensures r >= 0"])
    report = certificate.check(forged, prover=prover(lambda t: ALL))
    assert report["verdict"] == certificate.FAILED and results(report)["specification"] == "FAILED"


def test_a_claim_about_the_specification_that_does_not_measure_again_fails():
    c = proved()
    assert c["predicate"]["measured"]["completeness"] == 1.0
    weak = SPEC.replace("  ensures r == sum_to(a, len(a))\n", "  ensures r == sum_to(a, len(a)) or r >= 0\n")
    spec = prove.read_spec(weak)
    r = prove.prove(spec, None, prover=prover(lambda t: ALL))
    honest = certificate.from_proof(r, versions=VERSIONS)
    said = honest["predicate"]["measured"]["completeness"]
    assert said < 1.0
    assert certificate.check(honest, prover=prover(lambda t: ALL))["verdict"] == certificate.REPRODUCED
    forged = resealed(honest, measured=dict(honest["predicate"]["measured"], completeness=1.0))
    report = certificate.check(forged, prover=prover(lambda t: ALL))
    assert report["verdict"] == certificate.FAILED and results(report)["measured"] == "FAILED"
    assert "the certificate says 1.0" in certificate.render(report)


def test_with_a_specification_file_the_program_must_keep_it_unchanged():
    c = proved()
    same = prove.read_spec(SPEC)
    assert results(certificate.check(c, prover=prover(lambda t: ALL), spec=same))["specification kept"] == "ok"
    other = prove.read_spec(SPEC.replace("ensures r == sum_to(a, len(a))", "ensures r == sum_to(a, len(a)) + 1"))
    report = certificate.check(c, prover=prover(lambda t: ALL), spec=other)
    assert report["verdict"] == certificate.FAILED and results(report)["specification kept"] == "FAILED"


def test_a_file_that_is_not_a_certificate_fails_plainly(tmp_path, capsys):
    assert certificate.check({"_type": "something else"})["verdict"] == certificate.FAILED
    assert certificate.check(resealed(proved(), version=99))["verdict"] == certificate.FAILED
    path = tmp_path / "c.json"
    path.write_text("not json", encoding="utf-8")
    assert certificate.main(["check", str(path)]) == 1
    assert capsys.readouterr().out.startswith("FAILED: ")


@sandbox
def test_the_python_handed_back_is_run_beside_the_proved_program_again():
    c = proved()
    p = c["predicate"]["python"]
    assert p["function"] == "total" and "def total" in p["source"]
    assert results(certificate.check(c, prover=prover(lambda t: ALL)))["python"] == "ok"
    forged = resealed(c, python=dict(p, source=p["source"].replace("def total", "def total_was") + "\ndef total(a):\n    return 0\n"))
    report = certificate.check(forged, prover=prover(lambda t: ALL))
    assert report["verdict"] == certificate.FAILED and results(report)["python"] == "FAILED"
    assert "the Python does not answer as the proved program does" in certificate.render(report)


ENTRY_TESTS = ["assert double(3) == 6", "assert double(0) == 0"]
RIGHT = "```t\nt 1\ntask double(n: int) returns (r: int)\n  ensures r == 2 * n\n{\n  r := 2 * n;\n}\n```"
PYTHON = "```python\ndef double(n):\n    return 2 * n\n```"


def asked():
    entry = answer.entry_of("Double a number.", ENTRY_TESTS)
    r = answer.answer(entry, lambda *a: [(RIGHT, True, 0)], lambda *a: [(PYTHON, True, 0)], answers=1, prover=prover(lambda t: ALL))
    assert r["shown"], r
    return certificate.from_answer(r, versions=VERSIONS)


@sandbox
def test_a_questions_certificate_carries_the_independent_python_and_the_check_holds_the_specification_against_it_again():
    c = asked()
    p = c["predicate"]
    assert p["kind"] == "ask" and p["question"] == "Double a number." and p["tests"] == ENTRY_TESTS
    assert "def double" in p["reference python"] and {s["name"] for s in c["subject"]} == {"program.t", "function.py", "reference.py"}
    report = certificate.check(c, prover=prover(lambda t: ALL))
    assert report["verdict"] == certificate.REPRODUCED, report
    measured = next(s for s in report["steps"] if s["what"] == "measured")
    assert measured["result"] == "ok" and "holds at the recorded Python's answer on" in measured["detail"]


@sandbox
def test_a_questions_certificate_whose_recorded_python_disagrees_with_the_specification_fails():
    c = asked()
    forged = resealed(c, **{"reference python": "def double(n):\n    return 2 * n + (1 if n > 5 else 0)\n"})
    report = certificate.check(forged, prover=prover(lambda t: ALL))
    assert report["verdict"] == certificate.FAILED and results(report)["measured"] == "FAILED"
    assert "not supported by the recorded Python" in certificate.render(report)


def test_prove_writes_the_certificate_and_check_reads_it_back(tmp_path, monkeypatch, capsys):
    spec, out = tmp_path / "total.t", tmp_path / "total.cert.json"
    spec.write_text(SPEC, encoding="utf-8")
    real = prove.prove
    monkeypatch.setattr(prove, "prove", lambda s, student, answers, max_new=1024, jobs=2, tests=None:
                        real(s, student, answers, prover=prover(lambda t: ALL), jobs=jobs, tests=tests))
    assert prove.main(["prove", "--student", "unused:1", "--spec", str(spec), "--certificate", str(out),
                       "--test", TESTS[0]]) == 0
    assert "Certificate written to" in capsys.readouterr().out
    c = json.loads(out.read_text(encoding="utf-8"))
    assert c["predicate"]["tests"] == [TESTS[0]] and c["predicate"]["kind"] == "prove"
    monkeypatch.setattr(certificate.gate, "prove", prover(lambda t: ONLY_DAFNY))
    assert certificate.main(["check", str(out), "--spec", str(spec), "--json", str(tmp_path / "report.json")]) == 0
    assert capsys.readouterr().out.startswith("REPRODUCED: proved here by 1 prover (dafny)")
    assert json.loads((tmp_path / "report.json").read_text())["verdict"] == "reproduced"


dafny = pytest.mark.skipif("dafny" not in {b for b, _, _ in run_par.probe_backends()[1]}, reason="Dafny is not installed here")
LARGEST = """t 1
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


@dafny
def test_with_the_real_provers_a_true_certificate_reproduces_and_one_whose_proof_is_gone_does_not(monkeypatch):
    monkeypatch.setenv("T_MIN_KERNELS", "1")
    only_dafny = functools.partial(answer.prove, kernels="dafny")   # one prover keeps this to seconds; the path is the real one
    r = prove.prove(prove.read_spec(LARGEST), None, prover=only_dafny)
    assert r["shown"] and r["shown"]["provers"] == ["dafny"], r
    c = certificate.from_proof(r)
    assert c["predicate"]["made"]["provers"].get("dafny")
    report = certificate.check(c, prover=only_dafny)
    assert report["verdict"] == certificate.REPRODUCED and report["proved here"] == ["dafny"]
    # the program is still right, so no test and no bounded search can object; without this invariant the proof is gone
    gone = resealed(c, program=c["predicate"]["program"].replace("    invariant forall j in [0, i) . r >= s[j]\n", ""))
    report = certificate.check(gone, prover=only_dafny)
    assert report["verdict"] == certificate.UNDECIDED and report["proved here"] == []
