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


def test_python_is_taken_from_a_fenced_block_only():
    assert spec_first.python_of("```python\ndef f():\n    return 1\n```") == "def f():\n    return 1\n"
    assert spec_first.python_of("def f(): return 1") is None and spec_first.python_of("```python\n\n```") is None


class _Student:
    """Replies by what the question asks for; counts the questions."""

    def __init__(self, python, spec, proof):
        self.replies, self.asked = {"python": python, "spec": spec, "proof": proof}, []

    def decode(self, conversations, temperature, salt, first, max_new):
        out = []
        for c in conversations:
            kind = ("python" if c[0]["content"] == spec_first.spec_first_rows.PY_SYSTEM else
                    "spec" if c[0]["content"] == spec_first.spec_first_rows.SPEC_SYSTEM else "proof")
            self.asked.append((kind, temperature))
            replies = self.replies[kind]
            out.append((replies[min(len([a for a in self.asked if a[0] == kind]) - 1, len(replies) - 1)], True, 10))
        return out


PY_ENTRY = dict(ENTRY, rec=dict(ENTRY["rec"], text="Square a number.", code="def square(n):\n    return n * n\n"))


def test_the_python_route_keeps_only_python_that_passes_the_tests_in_the_sandbox():
    import pytest
    import py_sandbox
    if not py_sandbox.available():
        pytest.skip("bubblewrap is not installed")
    student = _Student(["```python\ndef square(n):\n    return n + n\n```", "```python\ndef square(n):\n    return n * n\n```"],
                       [], [])
    python, counts = spec_first.written_python(student.decode, ["1"], {"1": PY_ENTRY}, 3, 16, 64)
    assert python == {"1": "def square(n):\n    return n * n\n"}
    assert counts["1"] == {"python attempts": 2, "python": 1}        # the greedy one failed a test; the first sample passed
    assert [a for a in student.asked] == [("python", 0.0), ("python", 0.7)]


def test_written_specifications_are_parsed_candidates_with_the_python_in_the_question():
    student = _Student([], ["```t\nt 1\ntask square(n: int) returns (r: int)\n  ensures r == n * n\n{\n}\n```", "not a task"], [])
    out = spec_first.written_specifications(student.decode, {"1": "def square(n):\n    return n * n\n"},
                                            {"1": PY_ENTRY}, 1, 16, 64)
    assert [label for label, _task in out["1"]] == ["written/0"]
    kept, _ = spec_first.kept_specifications(out["1"], PY_ENTRY, 3)
    assert len(kept) == 1 and kept[0]["scores"]["correctness"] == 1.0


def test_given_specifications_are_read_stripped_and_scored(tmp_path, monkeypatch):
    import json
    ids = tmp_path / "ids.txt"; ids.write_text("1\n")
    given = tmp_path / "given.jsonl"
    given.write_text(json.dumps({"task_id": 1, "tasks": [RIGHT, WRONG], "sources": ["lab/a", "lab/b"]}) + "\n")
    monkeypatch.setattr(se, "pool", lambda version: {1: ENTRY})
    monkeypatch.setattr(se, "OUT_ROOT", tmp_path)
    monkeypatch.setattr(se, "outdir", lambda tag: (tmp_path / tag).mkdir(exist_ok=True) or tmp_path / tag)
    assert spec_first.main(["--model", "none", "--given-specs", str(given), "--tag", "g", "--ids-file", str(ids),
                            "--stage1-only"]) == 0
    out = json.loads((tmp_path / "g" / "spec_first.json").read_text())
    assert out["with a kept specification"] == 1 and out["per_problem"]["1"]["kept"] == 1
    assert out["per_problem"]["1"]["dropped"] == 1
