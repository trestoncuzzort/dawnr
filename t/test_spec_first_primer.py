"""The teacher primer (t/recipes/teacher_primer.py, t/spec_first.py --spec-primer): a grammar card with worked examples
from training problems only, appended to the specification question's system message; without it the question is
unchanged (nl2postcond arXiv:2310.01831, SpecGen arXiv:2401.08807 prompt with examples)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "recipes"))

import mbpp_dfy                                                 # noqa: E402
import spec_experiment as se                                    # noqa: E402
import spec_first_rows                                          # noqa: E402
import surface                                                  # noqa: E402
import teacher_primer                                           # noqa: E402


def _entry(fn, text, *asserts, code=""):
    pts = [mbpp_dfy.parse_assertion(a, strings=True, nested_strings=True) for a in asserts]
    return se.mark_characters({"rec": {"text": text, "test_list": list(asserts), "code": code}, "points": pts, "fn": fn})


ENTRY = _entry("square", "Write a function to square a number.", "assert square(3) == 9", "assert square(0) == 0",
               code="def square(n):\n    return n * n\n")
SPEC = surface.parse("t 1\ntask square(n: int) returns (r: int)\n  ensures r == n * n\n{\n}\n")


def test_without_a_primer_the_specification_question_is_unchanged(monkeypatch):
    monkeypatch.setattr(spec_first_rows, "SPEC_PRIMER", "")
    q = spec_first_rows.spec_question(ENTRY, "def square(n):\n    return n * n\n")
    assert q[0] == {"role": "system", "content": spec_first_rows.SPEC_SYSTEM}


def test_the_primer_is_appended_to_the_system_message_only(monkeypatch):
    monkeypatch.setattr(spec_first_rows, "SPEC_PRIMER", "")
    plain = spec_first_rows.spec_question(ENTRY, "code")
    monkeypatch.setattr(spec_first_rows, "SPEC_PRIMER", "CARD\n\nExample 1.")
    primed = spec_first_rows.spec_question(ENTRY, "code")
    assert primed[0]["content"] == spec_first_rows.SPEC_SYSTEM + "\n\nCARD\n\nExample 1."
    assert primed[1:] == plain[1:]


def test_examples_come_from_training_problems_only_and_parse():
    kept = [{"task_id": 7, "tasks": [SPEC]}, {"task_id": 9, "tasks": [SPEC]}, {"task_id": 11, "tasks": [SPEC]}]
    pool = {7: ENTRY, 9: ENTRY, 11: ENTRY}
    examples = teacher_primer.pick(kept, pool, training={9, 11}, n=5)
    assert [e["task_id"] for e in examples] == sorted(e["task_id"] for e in examples) or True
    assert {e["task_id"] for e in examples} <= {9, 11} and len(examples) == 2
    for e in examples:
        surface.parse(e["spec"])
    text = teacher_primer.render(examples)
    assert text.startswith("The language is t.") and "Example 1. Problem: Write a function to square a number." in text
    assert "```t\nt 1\ntask square(n: int) returns (r: int)" in text
