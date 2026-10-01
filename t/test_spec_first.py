"""The specification-first arm (arXiv:2410.15756 3.2, 3.3): keep specifications by the problem's
own tests, then take a specification-given answer only through the cheap gates. No model."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import loop_dataset                                             # noqa: E402
import mbpp_dfy                                                 # noqa: E402
import spec_experiment as se                                    # noqa: E402
import spec_first                                               # noqa: E402
import student_rows                                             # noqa: E402
import surface                                                  # noqa: E402


def _entry(*asserts):
    pts = [mbpp_dfy.parse_assertion(a, strings=True, nested_strings=True) for a in asserts]
    return se.mark_characters({"rec": {"test_list": list(asserts)}, "points": pts, "fn": "square"})


ENTRY = _entry("assert square(3) == 9", "assert square(4) == 16", "assert square(0) == 0")


def _task(ensures, body, name="mbpp_1__square"):
    return surface.parse(f"t 1\ntask {name}(n: int) returns (r: int)\n  ensures {ensures}\n{{\n  {body}\n}}\n")


RIGHT = _task("r == n * n", "r := n + 1;")                       # a right specification over a wrong body
WRONG = _task("r == n + n", "r := n + n;")
VAGUE = _task("r >= 0", "r := n * n;")
SAME = _task("r == n * n", "r := n * n;", name="mbpp_1__sq")     # the right one again under another name


def test_only_the_specification_the_tests_support_is_kept_and_once():
    kept, counts = spec_first.kept_specifications(
        [("a/x", WRONG), ("b/x", RIGHT), ("c/x", VAGUE), ("d/x", SAME)], ENTRY, 3)
    assert [k["source"] for k in kept] == ["b/x"]
    assert counts == {"scored": 4, "kept": 1, "duplicate": 1, "dropped": 2, "unscorable": 0}
    assert kept[0]["task"]["body"] == []                         # the wrong body is gone


def test_at_most_per_problem_are_kept_the_most_complete_first():
    weaker = _task("r >= n and (n > 0 ==> r > n or n == 1)", "r := n * n;")
    kept, _ = spec_first.kept_specifications([("w/x", weaker), ("r/x", RIGHT)], ENTRY, 1)
    assert len(kept) == 1 and kept[0]["source"] == "r/x"


def test_the_question_is_the_trained_specification_given_question():
    spec = spec_first.specification_of(RIGHT)
    q = spec_first.question(spec)
    assert q[0] == {"role": "system", "content": se.STUDENT_SYSTEM}
    assert q[1]["content"] == student_rows.ASK + loop_dataset.fence(surface.print_task(spec).strip())
    assert "r := n + 1" not in q[1]["content"]


def _reply(ensures, body, name="mbpp_1__square"):
    return loop_dataset.fence(surface.print_task(_task(ensures, body, name)).strip())


def test_an_answer_is_taken_only_through_every_gate():
    spec = spec_first.specification_of(RIGHT)
    assert spec_first.accept(_reply("r == n * n", "r := n * n;"), spec, ENTRY)[1] == "taken"
    assert spec_first.accept("no code here", spec, ENTRY)[1] == "no task block"
    assert spec_first.accept("```t\nt 1\ntask (\n```", spec, ENTRY)[1] == "does not parse"
    assert spec_first.accept(_reply("r == n * n", "r := n + 1;"), spec, ENTRY)[1] == "fails a test"
    assert spec_first.accept(_reply("r >= 0", "r := n * n;"), spec, ENTRY)[1].startswith("specification changed")
    assert spec_first.accept(_reply("r == n * n", "r := n * n;", name="other"), spec, ENTRY)[1].startswith(
        "specification changed")
