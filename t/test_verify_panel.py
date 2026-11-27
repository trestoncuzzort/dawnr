"""t/verify_panel.py: a `dawnr verify` panel run leaves one record per function in the run folder it is given: the
stages each specification and body stopped at and why, the proved twin when there is one, and the inputs the function
was held to. Totals alone cannot say which function stopped where; these records can."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import answer                                                   # noqa: E402
import py_sandbox                                               # noqa: E402
import spec_check                                               # noqa: E402
import verify_panel                                             # noqa: E402

needs_sandbox = pytest.mark.skipif(not py_sandbox.available(), reason="no sandbox for a person's Python here")

ALL = {k: "verified / refuted" for k in spec_check.KERNELS}
BODY = "```t\nt 1\ntask double(n: int) returns (r: int)\n  ensures r == 2 * n\n{\n  r := 2 * n;\n}\n```"
TRIPLE = BODY.replace("double", "triple").replace("2 * n", "3 * n")
PROBLEMS = [
    {"id": 7, "fn": "double", "code": "def double(n):\r\n  return 2 * n", "text": "Write a function to double a number.",
     "tests": ["assert double(3) == 6", "assert double(0) == 0", "assert double(-2) == -4"]},
    {"id": 8, "fn": "triple", "code": "def triple(n):\n    return 3 * n\n", "text": "Write a function to triple a number.",
     "tests": ["assert triple(1) == 3", "assert triple(2) == 6"]},
    {"id": 9, "fn": "halve", "code": "def halve(n):\n    return n // 2\n", "text": "Write a function to halve a number.",
     "tests": ["assert halve(4) == 3"]},
]


def student(*replies):
    queue = list(replies)
    asked = []

    def decode(conversations, temperature, salt, first, max_new):
        asked.append(conversations[0])
        return [(queue.pop(0) if queue else "no answer", True, 0)]
    decode.asked = asked
    return decode


def proving(tasks, jobs):
    return {task["name"]: ALL for task in tasks}


@needs_sandbox
def test_a_panel_run_leaves_one_record_per_function_in_the_folder_it_is_given(tmp_path):
    run = tmp_path / "verify-run"
    model = student(BODY)
    summary = verify_panel.run(PROBLEMS, run, model, prover=proving, settings={"whole": 1, "specs": 1, "answers": 1},
                               about={"model": "a test double"})
    assert sorted(p.name for p in run.iterdir()) == ["7.json", "8.json", "9.json", "run.json"]
    proved = json.loads((run / "7.json").read_text())
    assert proved["id"] == 7 and proved["fn"] == "double" and proved["verified"] and proved["route"] == "answers"
    assert "task double(n: int) returns (r: int)" in proved["twin"]["program"] and proved["twin"]["provers"] == sorted(ALL)
    assert proved["stages"] == [] and proved["asked"] == {"answers": 1}
    # the inputs: the problem's own tests as the examples, and the draws the function was held to
    inputs = proved["inputs"]
    assert inputs["examples"] == PROBLEMS[0]["tests"] and inputs["taken from the function"] is False
    assert inputs["kinds"] == [{"args": ["int"], "expected": "int"}] * 3
    assert inputs["specification check"] == {"seed": 1, "draws": 100, "larger draws": 60}
    assert proved["twin"]["behind the specification"]["agrees with the Python on"] >= 10
    # the function the record is about, as verify read it: the reference, with the problem's words as its docstring
    assert proved["function"]["code"] == PROBLEMS[0]["code"] and proved["function"]["doc"] == PROBLEMS[0]["text"]
    refused = json.loads((run / "8.json").read_text())
    assert not refused["verified"] and refused["route"] is None and refused["twin"] is None
    assert refused["why"].startswith("no specification the model wrote holds at your function's answers")
    assert [(s["route"], s["source"], s["stage"]) for s in refused["stages"]] == [
        ("answers", "answer 1", "reply"), ("specification", "specification 1", "reply")]
    # a function that fails its own problem's test is refused before the model is asked, and says so
    broken = json.loads((run / "9.json").read_text())
    assert not broken["verified"] and broken["stages"] == [
        {"route": None, "source": "the function", "stage": "entry",
         "reason": "your function fails your own example `assert halve(4) == 3`; nothing was asked of the model"}]
    assert len(model.asked) == 3                                  # 7: one answer; 8: one answer, one specification
    manifest = json.loads((run / "run.json").read_text())
    assert manifest["about"] == {"model": "a test double"} and manifest["ids"] == [7, 8, 9]
    assert manifest["settings"] == {"whole": 1, "specs": 1, "answers": 1}
    assert manifest["done"] == summary == {"functions": 3, "verified": 1, "refused": 2, "errors": 0,
                                           "stopped at": {"entry": 1, "reply": 1}}


@needs_sandbox
def test_a_run_taken_up_again_keeps_the_records_it_has_and_an_error_is_a_record_too(tmp_path):
    run = tmp_path / "verify-run"
    verify_panel.run(PROBLEMS[:1], run, student(BODY), prover=proving, settings={"whole": 1, "specs": 1, "answers": 1},
                     commit="0123abc")
    before = (run / "7.json").read_bytes()
    first = json.loads((run / "run.json").read_text())
    assert first["commit"] == "0123abc" and first["taken up again"] == []

    def timing_out(tasks, jobs):
        raise answer.ProverTimeout("the provers did not finish")
    again = student(TRIPLE)
    summary = verify_panel.run(PROBLEMS[:2], run, again, prover=timing_out, settings={"whole": 1, "specs": 1, "answers": 1})
    assert (run / "7.json").read_bytes() == before and len(again.asked) == 1     # 7 is not asked again
    failed = json.loads((run / "8.json").read_text())
    assert not failed["verified"] and failed["error"] == "ProverTimeout: the provers did not finish"
    assert failed["stages"][-1] == {"route": None, "source": "the run", "stage": "error",
                                    "reason": "ProverTimeout: the provers did not finish"}
    assert summary["errors"] == 1 and summary["functions"] == 2 and summary["verified"] == 1
    # the manifest keeps the first start time and lists each time the run was taken up again
    manifest = json.loads((run / "run.json").read_text())
    assert manifest["started"] == first["started"] and len(manifest["taken up again"]) == 1



def _timing_out(tasks, jobs):
    raise answer.ProverTimeout("the provers did not finish")


@needs_sandbox
def test_an_error_after_some_stages_keeps_those_stages_and_ends_with_the_error_as_a_stage_of_its_own(tmp_path):
    # A function whose check raised keeps the refusals verify had made before it raised; the error alone would lose
    # them. Here answer 1 is refused for want of a task block, answer 2 is held and answers as the function does, and
    # then the provers do not finish.
    run = tmp_path / "verify-run"
    model = student("no task block here", TRIPLE)
    verify_panel.run(PROBLEMS[1:2], run, model, prover=_timing_out, settings={"whole": 2, "specs": 1, "answers": 1})
    got = json.loads((run / "8.json").read_text())
    assert not got["verified"] and got["error"] == "ProverTimeout: the provers did not finish"
    assert [(s["route"], s["source"], s["stage"]) for s in got["stages"]] == [
        ("answers", "answer 1", "reply"), (None, "the run", "error")]
    assert got["stages"][-1]["reason"] == "ProverTimeout: the provers did not finish"
    assert len(got["refused"]) == 1 and got["refused"][0].startswith("answer 1: ")          # the refusal line is kept too
    assert got["stopped at"] == "error" and got["why"] == got["error"]


@needs_sandbox
def test_an_error_in_the_second_route_keeps_what_the_first_route_refused_before_it(tmp_path):
    run = tmp_path / "verify-run"
    model = student("no task block here", TRIPLE, TRIPLE)                 # answer 1 is refused; a specification follows
    verify_panel.run(PROBLEMS[1:2], run, model, prover=_timing_out, settings={"whole": 1, "specs": 1, "answers": 1})
    got = json.loads((run / "8.json").read_text())
    assert got["error"] == "ProverTimeout: the provers did not finish"
    assert [(s["route"], s["source"], s["stage"]) for s in got["stages"]] == [
        ("answers", "answer 1", "reply"), (None, "the run", "error")]
    assert [r.split(":")[0] for r in got["refused"]] == ["answer 1"]


@needs_sandbox
def test_an_error_before_any_stage_is_still_the_error_alone(tmp_path):
    run = tmp_path / "verify-run"
    verify_panel.run(PROBLEMS[1:2], run, student(TRIPLE), prover=_timing_out, settings={"whole": 1, "specs": 1, "answers": 1})
    got = json.loads((run / "8.json").read_text())
    assert [(s["route"], s["stage"]) for s in got["stages"]] == [(None, "error")] and got["refused"] == []


def test_the_panel_is_the_wider_111_with_each_reference_as_the_function_and_its_words_as_the_docstring(monkeypatch):
    pool = {5: {"fn": "f", "rec": {"text": "Words.", "code": "def f(x):\n    return x\n", "test_list": ["assert f(1) == 1"]}},
            6: {"fn": "g", "rec": {"text": "More.", "code": "def g(x):\n    return x\n", "test_list": ["assert g(2) == 2"]}}}
    monkeypatch.setattr(verify_panel.se, "wider_pool", lambda: pool)
    monkeypatch.setattr(verify_panel.heldout_audit, "wider_clean", lambda: {6})
    assert verify_panel.problems() == [{"id": 6, "fn": "g", "code": "def g(x):\n    return x\n", "text": "More.",
                                        "tests": ["assert g(2) == 2"]}]
    f = verify_panel.function_of(verify_panel.problems()[0])
    assert f["fn"] == "g" and f["doc"] == "More." and f["code"] == "def g(x):\n    return x\n"
