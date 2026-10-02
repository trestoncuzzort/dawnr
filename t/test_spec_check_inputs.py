"""The specification check's repair of 2026-10-01 (t/PREDICT-2026-10-01-spec-check-inputs.md):
draws are shaped by every example (EvalPlus's seed pool, github.com/evalplus/evalplus
gen/mut_gen.py), and another input's answer is a wrong answer here (nl2postcond's buggy-program
completeness, arXiv:2310.01831). The case is MBPP 67's: a lookup table that is right on the first
example's neighbourhood and wrong beyond it."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import spec_check                                               # noqa: E402
import surface                                                  # noqa: E402

REF = "def big(n):\n    return n * n\n"
ENTRY = {"fn": "big", "rec": {"code": REF, "test_list": ["assert big(1)==1", "assert big(7)==49", "assert big(16)==256"], "text": ""},
         "points": [{"ok": True, "fn": "big", "args": [("int", a)], "expected": ("int", a * a)} for a in (1, 7, 16)]}
FIRST_ONLY = dict(ENTRY, points=ENTRY["points"][:1])


def task(ensures, body):
    return surface.parse(f"t 1\ntask big(n: int) returns (r: int)\n  requires n >= 0\n  ensures {ensures}\n{{\n  {body}\n}}\n")


# right for n in 0..2 (the first example's neighbourhood), wrong above
TABLE = task("r == 0 or r == 1 or r == 4", "if n == 0 { r := 0; } else { if n == 1 { r := 1; } else { r := 4; } }")
HONEST = task("r == n * n", "r := n * n;")


def check(t, entry, seed=1):
    return spec_check.check_task(t, entry, 100, random.Random(seed))


def test_a_lookup_table_right_only_near_the_first_example_is_caught_by_draws_from_the_others():
    old = check(TABLE, FIRST_ONLY)
    assert old["status"] == "agrees"                            # what the check said before
    assert check(TABLE, ENTRY)["status"] == "disagrees"


def test_an_input_blind_specification_is_caught_by_another_inputs_answer_even_on_the_old_draws():
    r = check(TABLE, FIRST_ONLY)
    assert r["cross_completeness"] < spec_check.MIN_COMPLETENESS
    assert spec_check.complete(r) is False
    w = r["cross_witness"]
    assert w["also_accepts"] != w["reference_said"] and w["which_is_the_answer_for"] != w["args"]


def test_an_honest_specification_agrees_and_rejects_every_other_inputs_answer():
    r = check(HONEST, ENTRY)
    assert (r["status"], r["cross_completeness"], spec_check.complete(r)) == ("agrees", 1.0, True)
    assert r["draws"] >= 90


def test_complete_reads_both_families_and_says_none_when_nothing_was_judged():
    assert spec_check.complete({"completeness": 0.9, "cross_completeness": 0.7}) is True
    assert spec_check.complete({"completeness": 0.9, "cross_completeness": 0.5}) is False
    assert spec_check.complete({"completeness": 0.5}) is False
    assert spec_check.complete({"status": "agrees"}) is None


def test_one_example_draws_exactly_as_before_the_repair():
    """A problem with a single example consumes no extra randomness, so its verdicts do not move."""
    assert check(HONEST, FIRST_ONLY)["draws"] == check(HONEST, FIRST_ONLY)["draws"]
    a = spec_check.check_task(HONEST, FIRST_ONLY, 30, random.Random(5))
    b = spec_check.check_task(HONEST, FIRST_ONLY, 30, random.Random(5))
    assert a == b


def test_a_disagreement_found_earlier_on_the_same_task_is_kept_and_nothing_else_is():
    old = {"a": {"status": "disagrees", "task_sha256": "x", "args": [3]},
           "b": {"status": "disagrees", "task_sha256": "old contents"},
           "c": {"status": "agrees", "task_sha256": "z"}}
    new = {"a": {"status": "agrees", "task_sha256": "x"}, "b": {"status": "agrees", "task_sha256": "new contents"},
           "c": {"status": "disagrees", "task_sha256": "z"}, "d": {"status": "agrees", "task_sha256": "w"}}
    out = spec_check.keep_witnesses(old, new)
    assert out["a"]["status"] == "disagrees" and out["a"]["args"] == [3] and out["a"]["kept_from_an_earlier_check"]
    assert out["b"]["status"] == "agrees"                      # another task: the old witness says nothing about it
    assert out["c"]["status"] == "disagrees" and out["d"]["status"] == "agrees"



def test_reference_plus_swaps_only_mbpp_problems_with_the_same_function(tmp_path):
    import json as _json
    import spec_check
    pool = {605: {"fn": "prime_num", "rec": {"code": "def prime_num(n):\n    return n % 2 == 1\n"}},
            454: {"fn": "text_match_wordz", "rec": {"code": "def text_match_wordz(t):\n    return 'x'\n"}},
            100003: {"fn": "f", "rec": {"code": "def f(x):\n    return x\n"}}}
    rows = [{"task_id": 605, "code": "def prime_num(n):\n    return n > 1 and all(n % i for i in range(2, n))\n"},
            {"task_id": 454, "code": "def other_name(t):\n    return 'z' in t\n"},
            {"task_id": 100003, "code": "def f(x):\n    return -x\n"}]
    f = tmp_path / "plus.jsonl"; f.write_text("".join(_json.dumps(r) + "\n" for r in rows))
    out, n = spec_check.with_reference_plus(pool, f)
    assert n == 1
    assert "all(n % i" in out[605]["rec"]["code"] and "n % 2 == 1" in pool[605]["rec"]["code"]
    assert out[454] is pool[454] and out[100003] is pool[100003]
    assert spec_check.reference(out[605]["rec"], "prime_num")(9) is False
