"""Similar proved problems before the question (arXiv:2402.00247 3.4.3). No model."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import spec_experiment as se                                    # noqa: E402
import student_fewshot as sf                                    # noqa: E402


def _entry(text, fn):
    return {"rec": {"text": text, "test_list": [f"assert {fn}(1) == 1"]}, "fn": fn,
            "points": [{"ok": True, "fn": fn, "args": [["int", 1]], "expected": ["int", 1]}]}


POOL = {1: _entry("Write a function to sum the even numbers of a list.", "sum_even"),
        2: _entry("Write a function to reverse a string.", "reverse"),
        3: _entry("Write a function to sum the odd numbers of a list.", "sum_odd"),
        4: _entry("Check whether a year is a leap year.", "leap"),
        5: _entry("Find the largest of three integers.", "max3"),
        6: _entry("Count the vowels in a word.", "vowels"),
        7: _entry("Decide whether a triangle is valid.", "triangle"),
        9: _entry("Write a function to sum the numbers of a list.", "sum_all")}
ROWS = [{"task_id": 1, "chosen": "A1-weak", "kernels_verified": 1}, {"task_id": 1, "chosen": "A1", "kernels_verified": 7},
        {"task_id": 2, "chosen": "A2", "kernels_verified": 3}, {"task_id": 3, "chosen": "A3", "kernels_verified": 5},
        {"task_id": 4, "chosen": "A4", "kernels_verified": 2}, {"task_id": 5, "chosen": "A5", "kernels_verified": 2},
        {"task_id": 6, "chosen": "A6", "kernels_verified": 2}, {"task_id": 7, "chosen": "A7", "kernels_verified": 2}]


def test_one_answer_a_problem_the_one_the_most_kernels_prove():
    best = sf.best_answers(ROWS)
    assert sorted(best) == [1, 2, 3, 4, 5, 6, 7] and best[1]["chosen"] == "A1"


def test_the_closest_solved_problems_are_shown_closest_last_then_the_question():
    answers = sf.best_answers(ROWS)
    index = sf.build_index(answers, POOL)
    examples = sf.retrieve(index, answers, POOL, POOL[9], 2)
    assert {a for _e, a in examples} == {"A1", "A3"}             # the two summing problems, not the string one
    c = sf.conversation(POOL[9], examples)
    assert [m["role"] for m in c] == ["system", "user", "assistant", "user", "assistant", "user"]
    assert c[0] == se.build_prompt(POOL[9], "s1")[0] and c[-1] == se.build_prompt(POOL[9], "s1")[1]
    assert c[2]["content"] in ("A1", "A3") and c[4]["content"] in ("A1", "A3")
    assert "sum the numbers of a list" in c[-1]["content"] and "sum the numbers of a list" not in c[1]["content"]


def test_a_problem_that_is_in_the_example_pool_is_not_asked(tmp_path, monkeypatch):
    import json
    import pytest
    rows = tmp_path / "rows.jsonl"; rows.write_text("".join(json.dumps(r) + "\n" for r in ROWS))
    ids = tmp_path / "ids.txt"; ids.write_text("2\n")
    monkeypatch.setattr(se, "pool", lambda version: POOL)
    with pytest.raises(SystemExit):
        sf.main(["--model", "none", "--pool-rows", str(rows), "--tag", "x", "--ids-file", str(ids), "--dry-run"])
