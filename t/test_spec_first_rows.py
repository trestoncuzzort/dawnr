"""Rows for the specification written first (arXiv:2410.15756 3.2, 3.3): three kinds from one pool row."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import loop_dataset                                             # noqa: E402
import mbpp_dfy                                                 # noqa: E402
import spec_experiment as se                                    # noqa: E402
import spec_first_rows as sfr                                   # noqa: E402
import student_rows                                             # noqa: E402
import surface                                                  # noqa: E402

CODE = "def square(n):\n    return n * n\n"
ASSERTS = ["assert square(3) == 9", "assert square(0) == 0"]
ENTRY = se.mark_characters({"rec": {"text": "Square a number.", "test_list": ASSERTS, "code": CODE},
                            "points": [mbpp_dfy.parse_assertion(a, strings=True) for a in ASSERTS], "fn": "square"})
TASK = "t 1\ntask square(n: int) returns (r: int)\n  ensures r == n * n\n{\n  r := n * n;\n}\n"
ROW = {"task_id": 7, "tag": "x", "name": "mbpp_7__square", "chosen": loop_dataset.fence(TASK.strip()),
       "kernels_verified": 7, "undecided": []}


def test_one_pool_row_gives_the_three_kinds():
    rows, report = sfr.build([ROW], {7: ENTRY})
    assert [r["source"] for r in rows] == ["python", "spec", "proof-py"]
    assert report == {"pool_rows": 1, "problems": 1, "python": 1, "spec": 1, "proof-py": 1}
    py, spec, proof = rows
    assert py["chosen"] == "```python\ndef square(n):\n    return n * n\n```"
    assert "Write a Python function named `square`" in py["prompt"][1]["content"]
    assert py["prompt"][0]["content"] == sfr.PY_SYSTEM


def test_the_spec_row_shows_the_python_and_answers_with_an_empty_body():
    spec = sfr.build([ROW], {7: ENTRY})[0][1]
    user = spec["prompt"][1]["content"]
    assert "A Python solution:\n```python\ndef square(n):" in user and "the body stays empty" in user
    assert spec["prompt"][0]["content"] == sfr.SPEC_SYSTEM
    answer = surface.parse(se.find_block(spec["chosen"]))
    assert answer["body"] == [] and len(answer["ensures"]) == 1


def test_the_proof_row_is_the_specification_given_question_plus_the_python():
    proof = sfr.build([ROW], {7: ENTRY})[0][2]
    user = proof["prompt"][1]["content"]
    assert user.startswith(student_rows.ASK) and "A Python solution to the same problem:" in user
    assert "r := n * n" not in user.split("A Python solution")[0]      # the body is not in the question
    assert proof["chosen"] == ROW["chosen"]


def test_a_second_answer_to_the_same_problem_adds_only_what_is_new():
    other = dict(ROW, chosen=loop_dataset.fence(TASK.replace("r := n * n;", "r := n; r := r * n;").strip()))
    rows, report = sfr.build([ROW, other], {7: ENTRY})
    assert report == {"pool_rows": 2, "problems": 1, "python": 1, "spec": 1, "proof-py": 2}


def test_a_problem_without_a_python_solution_gives_no_row():
    rows, report = sfr.build([ROW], {7: dict(ENTRY, rec=dict(ENTRY["rec"], code=""))})
    assert rows == [] and report["no python solution"] == 1
