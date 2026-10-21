"""The Python-stage repair (t/PREDICT-2026-10-21-python-repair.md): the last Python attempt repairs the failed reply
that passed the most tests, with the sandbox's finding (Self-Debugging arXiv:2304.05128, Reflexion arXiv:2303.11366)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mbpp_dfy                                                 # noqa: E402
import py_sandbox                                               # noqa: E402
import spec_experiment as se                                    # noqa: E402
import spec_first                                               # noqa: E402


def _entry(*asserts):
    pts = [mbpp_dfy.parse_assertion(a, strings=True, nested_strings=True) for a in asserts]
    return se.mark_characters({"rec": {"text": "Write a function to square a number.", "test_list": list(asserts)},
                               "points": pts, "fn": "square"})


ENTRY = _entry("assert square(3) == 9", "assert square(4) == 16", "assert square(0) == 0")
ASSERTS = ENTRY["rec"]["test_list"]


def _py(body):
    return f"```python\ndef square(n):\n    return {body}\n```"


class _Student:
    def __init__(self, script):
        self.script, self.asked = script, []

    def decode(self, conversations, temperature, salt, _first, _max_new):
        self.asked.append((salt, [[m["role"] for m in c] for c in conversations], conversations))
        return [(self.script[salt], True, 1) for _ in conversations]


def test_witnesses_name_the_failing_asserts_or_the_reason_nothing_ran():
    assert spec_first.python_witnesses(None, None, ASSERTS) == ["the reply has no fenced python block"]
    assert spec_first.python_witnesses("x", {"status": "load-error", "why": "SyntaxError"}, ASSERTS) == ["the code does not load: SyntaxError"]
    assert spec_first.python_witnesses("x", {"status": "timeout"}, ASSERTS) == ["the tests time out"]
    ws = spec_first.python_witnesses("x", {"status": "ran", "verdicts": ["fail", "pass", "error: boom"]}, ASSERTS)
    assert ws == ["`assert square(3) == 9`: fail", "`assert square(0) == 0`: error: boom"]


def test_the_last_attempt_repairs_the_reply_that_passed_the_most_tests():
    if not py_sandbox.available():
        pytest.skip("no sandbox")
    student = _Student({0: _py("n + n"), 1: "no code here", 2: _py("n * n")})
    python, counts = spec_first.written_python(student.decode, ["1"], {"1": ENTRY}, 3, 16, 64, repair=True)
    assert python == {"1": "def square(n):\n    return n * n\n"}
    assert counts["1"] == {"python attempts": 3, "python": 2, "python repair asks": 1, "python repaired": 1}
    salt, roles, conversations = student.asked[2]
    assert salt == 2 and roles == [["system", "user", "assistant", "user"]]
    assert conversations[0][2]["content"] == _py("n + n")           # the reply with one passing test, not the codeless one
    assert "- `assert square(3) == 9`:" in conversations[0][3]["content"]
    assert "Fix the function `square`" in conversations[0][3]["content"]


def test_without_repair_every_attempt_is_a_plain_question():
    if not py_sandbox.available():
        pytest.skip("no sandbox")
    student = _Student({0: _py("n + n"), 1: "no code here", 2: _py("n * n")})
    python, counts = spec_first.written_python(student.decode, ["1"], {"1": ENTRY}, 3, 16, 64)
    assert python == {"1": "def square(n):\n    return n * n\n"} and counts["1"] == {"python attempts": 3, "python": 2}
    assert all(roles == [["system", "user"]] for _s, roles, _c in student.asked)


def test_a_problem_whose_first_attempt_passes_is_never_repaired():
    if not py_sandbox.available():
        pytest.skip("no sandbox")
    student = _Student({0: _py("n * n"), 1: _py("n"), 2: _py("n")})
    python, counts = spec_first.written_python(student.decode, ["1"], {"1": ENTRY}, 3, 16, 64, repair=True)
    assert counts["1"] == {"python attempts": 1, "python": 0, "python repair asks": 0, "python repaired": 0}


def test_the_main_route_refuses_python_repair_with_one_attempt(tmp_path):
    ids = tmp_path / "ids.txt"; ids.write_text("1\n")
    with pytest.raises(SystemExit):
        spec_first.main(["--model", "none", "--python", "1", "--python-repair", "--tag", "y", "--ids-file", str(ids)])
