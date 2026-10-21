"""The oracle gate (t/PREDICT-2026-10-21-oracle-route.md): the student's own tested Python judges every
specification candidate in place of the three tests (t/spec_gate.judge; Clover arXiv:2310.17807)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mbpp_dfy                                                 # noqa: E402
import py_sandbox                                               # noqa: E402
import spec_experiment as se                                    # noqa: E402
import spec_first                                               # noqa: E402
import surface                                                  # noqa: E402


def _entry(*asserts):
    pts = [mbpp_dfy.parse_assertion(a, strings=True, nested_strings=True) for a in asserts]
    return se.mark_characters({"rec": {"text": "Write a function to square a number.", "test_list": list(asserts),
                                       "code": "def square(n):\n    return n * n\n"},
                               "points": pts, "fn": "square"})


ENTRY = _entry("assert square(3) == 9", "assert square(4) == 16", "assert square(0) == 0")
PY = "def square(n):\n    return n * n\n"


def _spec(ensures):
    return surface.parse(f"t 1\ntask square(n: int) returns (r: int)\n  ensures {ensures}\n{{\n}}\n")


RIGHT, WRONG, VAGUE = _spec("r == n * n"), _spec("r == n + n"), _spec("r >= 0")


def test_the_oracle_keeps_the_specification_its_python_agrees_with_and_records_every_verdict():
    if not py_sandbox.available():
        pytest.skip("no sandbox")
    written = {"1": [("written/0", VAGUE), ("written/1", WRONG), ("written/2", RIGHT)]}
    per = {"1": [], "2": []}
    stats = {"1": {"kept": 0}, "2": {"kept": 0}}
    record = []
    changed = spec_first.oracle_gate(written, {"1": PY}, {"1": ENTRY, "2": ENTRY}, ["1", "2"], per, 3, stats, record, draws=40)
    assert changed == 1 and [k["source"] for k in per["1"]] == ["written/2"] and per["2"] == []
    assert stats["1"]["oracle judged"] == 3 and stats["1"]["oracle kept"] == 1 and stats["1"]["kept"] == 1
    assert [r["verdict"] for r in record] == ["oracle-dropped", "oracle-dropped", "oracle-kept"]
    assert record[2]["oracle"]["passes"] and record[2]["scores"]["correctness"] == 1.0
    assert "n * n" in per["1"][0]["task"]["ensures"][0].__repr__() or per["1"][0]["source"] == "written/2"


def test_a_problem_without_python_is_left_to_the_three_test_gate():
    if not py_sandbox.available():
        pytest.skip("no sandbox")
    kept, _ = spec_first.kept_specifications([("written/0", RIGHT)], ENTRY, 3)
    per = {"1": kept}
    stats = {"1": {"kept": 1}}
    changed = spec_first.oracle_gate({"1": [("written/0", RIGHT)]}, {}, {"1": ENTRY}, ["1"], per, 3, stats, [])
    assert changed == 0 and [k["source"] for k in per["1"]] == ["written/0"] and "oracle kept" not in stats["1"]


def test_the_main_route_refuses_the_oracle_gate_without_the_students_python(tmp_path):
    ids = tmp_path / "ids.txt"; ids.write_text("1\n")
    with pytest.raises(SystemExit):
        spec_first.main(["--model", "none", "--from-samples", "x", "--tag", "o", "--ids-file", str(ids), "--oracle-gate"])
