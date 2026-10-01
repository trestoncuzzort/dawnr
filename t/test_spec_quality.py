"""SAFE's test-based specification scores (arXiv:2410.15756, 3.2), on the problem's own tests."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mbpp_dfy                                                 # noqa: E402
import spec_experiment as se                                    # noqa: E402
import spec_quality                                             # noqa: E402
import surface                                                  # noqa: E402


def _entry(*asserts):
    pts = [mbpp_dfy.parse_assertion(a, strings=True, nested_strings=True) for a in asserts]
    return se.mark_characters({"rec": {"test_list": list(asserts)}, "points": pts, "fn": "f"})


ENTRY = _entry("assert f(3) == 9", "assert f(4) == 16", "assert f(0) == 0")


def _task(ensures, requires=""):
    return surface.parse(f"t 1\ntask f(n: int) returns (r: int)\n{requires}  ensures {ensures}\n{{\n}}\n")


def test_the_right_specification_holds_on_every_test_and_rejects_every_mutant():
    s = spec_quality.scores(_task("r == n * n"), ENTRY)
    assert s["correctness"] == 1.0 and s["completeness"] == 1.0 and s["tests"] == 3 and s["mutants"] > 0
    assert spec_quality.keeps(s)


def test_a_wrong_specification_fails_correctness():
    s = spec_quality.scores(_task("r == n + n"), ENTRY)            # true only at 0
    assert s["correctness"] < 0.8 and not spec_quality.keeps(s)


def test_a_vacuous_specification_fails_completeness():
    s = spec_quality.scores(_task("r >= 0"), ENTRY)
    assert s["correctness"] == 1.0 and s["completeness"] < 0.6 and not spec_quality.keeps(s)


def test_a_test_outside_the_requires_is_not_counted():
    s = spec_quality.scores(_task("r == n * n", "  requires n > 0\n"), ENTRY)
    assert s["tests"] == 2 and s["correctness"] == 1.0


def test_a_signature_the_tests_do_not_fit_is_unscorable_and_not_kept():
    task = surface.parse("t 1\ntask f(n: int, m: int) returns (r: int)\n  ensures r == n\n{\n}\n")
    s = spec_quality.scores(task, ENTRY)
    assert "unscorable" in s and not spec_quality.keeps(s)


def test_a_specification_no_test_reaches_is_unscorable():
    s = spec_quality.scores(_task("r == n * n", "  requires n > 100\n"), ENTRY)
    assert s == {"unscorable": "no test inside the requires"}
