"""t/spec_gate.py: the gate's specification stage with no reference solution. The model's own
tested Python stands where the reference stands in spec_check (Clover's doc2code edge,
arXiv:2310.17807: two artifacts compared by their outputs on inputs); SAFE's 60% floor for a
usable specification (arXiv:2410.15756, 3.2)."""
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import py_sandbox                                               # noqa: E402
import spec_check                                               # noqa: E402
import spec_gate                                                # noqa: E402
import surface                                                  # noqa: E402

pytestmark = pytest.mark.skipif(not py_sandbox.available(), reason="bubblewrap is not installed")


def _codes(text):
    return [ord(c) for c in text]


def _entry(fn, assertions, args, expected, code=""):
    return {"rec": {"code": code, "test_list": assertions, "text": ""}, "fn": fn,
            "points": [{"ok": True, "fn": fn, "args": args, "expected": expected}]}


DOUBLE = _entry("double", ["assert double(3) == 6"], [["int", 3]], ["int", 6])
RIGHT_PY = "def double(n):\n    return 2 * n\n"


def _task(ensures, body="r := 2 * n;", requires=""):
    return surface.parse(f"t 1\ntask double(n: int) returns (r: int)\n{requires}  ensures {ensures}\n{{\n  {body}\n}}\n")


def test_a_specification_that_pins_the_answer_and_agrees_with_the_python_passes():
    v = spec_gate.judge(_task("r == 2 * n"), DOUBLE, RIGHT_PY)
    assert v["passes"] and v["why"] == "passes"
    assert v["agreement"]["draws"] >= spec_gate.MIN_DRAWS and v["agreement"]["completeness"] == 1.0


def test_a_true_and_weak_specification_is_refused_as_weak():
    v = spec_gate.judge(_task("n >= 0 ==> r >= n"), DOUBLE, RIGHT_PY)
    assert not v["passes"] and v["why"] == "weak specification"
    assert v["agreement"]["status"] == "agrees" and v["agreement"]["completeness"] < spec_gate.MIN_COMPLETENESS


def test_a_specification_of_another_function_that_fits_the_one_test_is_refused():
    # 6 == 3 + 3 == 2 * 3: `r == n + 3` fits the question's only test and is not doubling
    v = spec_gate.judge(_task("r == n + 3", "r := n + 3;"), DOUBLE, RIGHT_PY)
    assert not v["passes"] and v["why"] == "the specification is false at the Python's answer"
    assert v["tests"]["correctness"] == 1.0                     # the question's own test cannot tell


def test_without_a_tested_python_beside_it_an_answer_is_refused():
    v = spec_gate.judge(_task("r == 2 * n"), DOUBLE, None)
    assert not v["passes"] and v["why"] == "no test-passing Python beside it"


def test_a_requires_that_admits_little_more_than_the_example_is_refused():
    # n == 3 is drawn often enough to "agree" on more than ten draws; it is one input
    v = spec_gate.judge(_task("r == 6", "r := 6;", "  requires n == 3\n"), DOUBLE, RIGHT_PY)
    assert not v["passes"] and v["why"] == "the requires excludes most drawn inputs"
    assert v["agreement"]["outside_requires"] > v["agreement"]["draws"]


def test_a_real_precondition_that_excludes_some_drawn_inputs_still_passes():
    v = spec_gate.judge(_task("r == 2 * n", requires="  requires n >= 1\n"), DOUBLE, RIGHT_PY)
    assert v["passes"], v
    assert 0 < v["agreement"]["outside_requires"] < v["agreement"]["draws"]


def test_python_that_does_not_load_is_a_refusal_not_a_crash():
    v = spec_gate.judge(_task("r == 2 * n"), DOUBLE, "def other(n):\n    return n\n")
    assert not v["passes"] and v["why"].startswith("the Python does not load")


def test_a_string_question_goes_to_the_python_as_a_string():
    entry = _entry("shout", ['assert shout("ab") == "AB"'], [["seq", _codes("ab")]], ["seq", _codes("AB")])
    task = surface.parse("t 1\ntask shout(s: seq) returns (r: seq)\n  ensures r == s.upper()\n{\n  r := s.upper();\n}\n")
    v = spec_gate.judge(task, entry, "def shout(s):\n    assert isinstance(s, str)\n    return s.upper()\n")
    assert v["passes"], v


def test_the_oracle_maps_the_sandbox_outcomes_onto_the_reference_checks_own():
    code = ("def double(n):\n    if n == 1:\n        raise ValueError('refused')\n    if n == 2:\n        return {4}\n"
            "    if n == 4:\n        while True:\n            pass\n    return 2 * n\n")
    with py_sandbox.Session(code, "double", per_call=1) as s:
        call = spec_gate.python_oracle(s)
        assert call(3) == 6
        with pytest.raises(Exception):
            call(1)
        with pytest.raises(TypeError):
            spec_check.to_t(call(2))                            # "the result has no t value": the draw is skipped
        with pytest.raises(spec_check.Timeout):
            call(4)


def test_check_task_with_an_oracle_never_loads_the_reference():
    entry = dict(DOUBLE, rec={"code": "raise SystemExit('the reference must not be run')", "test_list": DOUBLE["rec"]["test_list"]})
    r = spec_check.check_task(_task("r == 2 * n"), entry, 20, random.Random(1), oracle=lambda n: 2 * n)
    assert r["status"] == "agrees" and r["draws"] == 20



def test_judge_all_refuses_when_another_test_passing_solution_reads_the_question_differently(monkeypatch):
    """ClarifyGPT's consistency check (arXiv:2310.10996): 'odd parity' read as 'is odd' and as 'an odd number
    of one bits' pass the same three tests (13, 21, 18); the second solution finds the first reading false."""
    calls = []

    def fake_judge(task, entry, code, seed=1, n=100):
        calls.append(code)
        if code == "parity":
            return {"passes": False, "why": "the specification is false at the Python's answer",
                    "agreement": {"status": "disagrees", "args": [3], "reference_said": False}}
        return {"passes": True, "why": "passes", "agreement": {"status": "agrees"}}
    monkeypatch.setattr(spec_gate, "judge", fake_judge)
    out = spec_gate.judge_all({}, {}, "is_odd", ["is_odd", "also_is_odd", "parity"])
    assert out["passes"] is False and out["why"] == "the Python solutions read the question differently"
    assert out["ambiguous"] == {"args": [3], "another_solution_said": False, "solution": 2}
    assert calls == ["is_odd", "also_is_odd", "parity"]                 # the duplicate of the first is not re-judged


def test_judge_all_ignores_an_extra_solution_s_weak_check_and_passes_when_all_agree(monkeypatch):
    def fake_judge(task, entry, code, seed=1, n=100):
        if code == "narrow":
            return {"passes": False, "why": "too few draws inside the requires", "agreement": {"status": "agrees"}}
        return {"passes": True, "why": "passes", "agreement": {"status": "agrees"}}
    monkeypatch.setattr(spec_gate, "judge", fake_judge)
    out = spec_gate.judge_all({}, {}, "a", ["b", "narrow"])
    assert out["passes"] is True and out["solutions_agreeing"] == 3
    monkeypatch.setattr(spec_gate, "judge", lambda *a, **k: {"passes": False, "why": "weak specification"})
    assert spec_gate.judge_all({}, {}, "a", ["b"])["why"] == "weak specification"   # the primary check decides first
