"""t/spec_gate.py: the gate's specification stage with no reference solution. The model's own
tested Python stands where the reference stands in spec_check (Clover's doc2code edge,
arXiv:2310.17807: two artifacts compared by their outputs on inputs); SAFE's 60% floor for a
usable specification (arXiv:2410.15756, 3.2)."""
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import answer                                                   # noqa: E402
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


# ---- 2026-10-05: inputs larger than the examples (spec_check.draw_beyond, spec_gate.beyond_reason) ----
# Found the first time a larger model wrote the specification: every case spelled out up to the size the ordinary
# draws reach, and nothing said after it. QuickCheck grows its sizes (maxSize 100); EvalPlus, arXiv:2305.01210.

COUNT_ENTRY = answer.entry_of("How many of the numbers are even.",
                              ["assert count_even([1, 2, 3]) == 1", "assert count_even([]) == 0", "assert count_even([-1, 5, 0, 4]) == 2"])
COUNT_PYTHON = "def count_even(xs):\n    return sum(1 for x in xs if x % 2 == 0)\n"


def _even(i):
    return f"(if s[{i}] % 2 == 0 then 1 else 0)"


def _spelled_out(upto, tail):
    cases = "".join(f"if len(s) == {n} then {' + '.join(_even(i) for i in range(n)) or '0'} else " for n in range(upto + 1))
    return surface.parse(f"t 1\ntask count_even(s: seq) returns (r: int)\n  ensures r == ({cases}{tail})\n{{\n  r := 0;\n}}\n")


RECURSIVE = surface.parse("""t 1
task count_even(s: seq) returns (r: int)
  ensures r == evens(s, len(s))
spec fun evens(s: seq, n: int): int
  decreases n
= if n <= 0 then 0 else evens(s, n - 1) + (if n <= len(s) and s[n - 1] % 2 == 0 then 1 else 0)
{
  r := 0;
}
""")


def test_the_larger_draws_reach_past_anything_the_ordinary_ones_make_and_keep_the_examples_style():
    rnd = random.Random(3)
    ordinary = max(len(spec_check.draw("seq", rnd, [1, 2, 3, 4])) for _ in range(400))
    larger = [len(spec_check.draw_beyond("seq", rnd, [1, 2, 3, 4], share=1.0)) for _ in range(400)]
    assert ordinary == 6 and min(larger) == 7 and max(larger) >= 28
    ints = [spec_check.draw_beyond("int", rnd, 10, share=1.0) for _ in range(400)]
    assert min(ints) > 20 and max(ints) > 100 and all(x < 0 for x in (spec_check.draw_beyond("int", rnd, -5, share=1.0) for _ in range(50)))
    assert all(v == sorted(v) for v in (spec_check.draw_beyond("seq", rnd, [1, 3, 9], share=1.0) for _ in range(100)))
    one, several = spec_check.beyond_drawer(1), spec_check.beyond_drawer(2)
    assert all(len(one("seq", rnd, [1, 2])) > 4 for _ in range(100))
    assert any(len(several("seq", rnd, [1, 2])) <= 4 for _ in range(100))          # some stay ordinary, for joint preconditions


def test_a_specification_spelled_out_only_up_to_the_examples_size_passed_before_and_is_refused_now():
    enumerated = _spelled_out(6, "r")
    before = spec_gate.judge(enumerated, COUNT_ENTRY, COUNT_PYTHON, beyond=0)
    assert before["passes"] and before["agreement"]["completeness"] == 1.0          # what the gate saw until 2026-10-05
    now = spec_gate.judge(enumerated, COUNT_ENTRY, COUNT_PYTHON)
    assert not now["passes"] and now["why"] == "the specification says too little about inputs larger than the examples"
    assert now["larger"]["completeness"] < 0.6 and len(now["larger"]["weak_witness"]["args"][0]) > 6


def test_one_false_past_the_examples_or_whose_requires_stops_there_is_refused_too_and_an_honest_one_passes():
    false_after = spec_gate.judge(_spelled_out(6, "0"), COUNT_ENTRY, COUNT_PYTHON)
    assert not false_after["passes"] and false_after["why"] == "the specification is false at the Python's answer on an input larger than the examples"
    narrow = surface.parse(surface.print_task(_spelled_out(6, "r")).replace("  ensures r ==", "  requires len(s) <= 6\n  ensures r =="))
    stopped = spec_gate.judge(narrow, COUNT_ENTRY, COUNT_PYTHON)
    assert not stopped["passes"] and stopped["why"] == "the requires closes off inputs larger than the examples"
    honest = spec_gate.judge(RECURSIVE, COUNT_ENTRY, COUNT_PYTHON)
    assert honest["passes"] and honest["larger"]["completeness"] == 1.0 and honest["larger"]["draws"] == spec_gate.BEYOND_DRAWS


def test_a_requires_as_narrow_on_the_ordinary_draws_as_on_the_larger_ones_is_not_a_matter_of_size():
    # the two right specifications a floor on the larger draws alone refused (2026-10-05): a `requires` of hexadecimal
    # digits where the reference answers any string, and a length argument that must not exceed another
    ordinary = {"status": "agrees", "draws": 60, "outside_requires": 140, "completeness": 1.0}
    larger = {"status": "agrees", "draws": 9, "outside_requires": 191, "completeness": 1.0, "requires_caps_size": False}
    assert spec_gate.beyond_reason(larger, ordinary) is None                       # every character a hexadecimal digit
    hexadecimal = surface.parse("t 1\ntask f(s: seq) returns (r: int)\n  requires forall i in [0, len(s)) . s[i] >= 48 and s[i] <= 70\n  ensures r == 0\n{\n  r := 0;\n}\n")
    lengths = surface.parse("t 1\ntask f(a: seq, n: int, m: int) returns (r: int)\n  requires n >= 0 and m >= 0 and m <= n\n  ensures r == 0\n{\n  r := 0;\n}\n")
    assert not spec_check.caps_size(hexadecimal) and not spec_check.caps_size(lengths)   # an element's bound and a relation are not a cap
    for capped in ("requires len(s) <= 6", "requires 6 >= len(s)", "requires n < 5", "requires n >= 0 and n == 3"):
        task = surface.parse(f"t 1\ntask f(s: seq, n: int) returns (r: int)\n  {capped}\n  ensures r == 0\n{{\n  r := 0;\n}}\n")
        assert spec_check.caps_size(task), capped
    closed = {"status": "agrees", "draws": 2, "outside_requires": 58, "completeness": 1.0, "requires_caps_size": True}
    assert spec_gate.beyond_reason(closed, {"status": "agrees", "draws": 100, "completeness": 1.0}) == "the requires closes off inputs larger than the examples"
    assert spec_gate.beyond_reason(dict(closed, requires_caps_size=False), {"status": "agrees", "draws": 100, "completeness": 1.0}) is None


def test_too_few_larger_inputs_judged_leaves_it_unmeasured_not_refused():
    assert spec_gate.beyond_reason({"status": "agrees", "draws": 3, "mutants_rejected": 0, "mutants_accepted": 9, "completeness": 0.0}) is None
    assert spec_gate.beyond_reason({"status": "no valid draws"}) is None
    assert spec_gate.beyond_reason({"status": "agrees", "draws": 30, "mutants_rejected": 90, "mutants_accepted": 10, "completeness": 0.9}) is None
