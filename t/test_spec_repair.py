"""t/spec_repair.py: an answer goes back with the stage's concrete witness (VeriMed, arXiv:2605.13817:
98.5% with the witness against 58.5% for a generic retry; SAFE's debugging loop, arXiv:2410.15756)
and only what the stage then passes is kept. No reference solution anywhere."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import answer                                                   # noqa: E402
import debug_rows                                               # noqa: E402
import py_sandbox                                               # noqa: E402
import spec_repair                                              # noqa: E402
import surface                                                  # noqa: E402

pytestmark = pytest.mark.skipif(not py_sandbox.available(), reason="bubblewrap is not installed")

ENTRY = answer.entry_of("Double a number.", ["assert double(3) == 6", "assert double(0) == 0"])
P, PY = {"1": ENTRY}, {"1": "def double(n):\n    return 2 * n\n"}
QUESTION = [{"role": "system", "content": "S"}, {"role": "user", "content": "Q"}]


def task(ensures, body="r := 2 * n;"):
    return surface.parse(f"t 1\ntask double(n: int) returns (r: int)\n  ensures {ensures}\n{{\n  {body}\n}}\n")


def fenced(t):
    return "```t\n" + surface.print_task(t) + "```"


RIGHT, WEAK, OTHER = task("r == 2 * n"), task("n >= 0 ==> r >= n"), task("r == n * n - n", "r := n * n - n;")


def decoder(*replies):
    seen, queue = [], list(replies)

    def decode(conversations, temperature, salt, first, max_new):
        seen.extend(conversations)
        return [(queue.pop(0) if queue else "nothing", True, 0) for _ in conversations]
    return decode, seen


def test_an_answer_that_already_passes_the_stage_is_carried_and_nothing_is_asked():
    decode, seen = decoder()
    state, counts = spec_repair.run({"1": {"question": QUESTION, "tasks": [WEAK, RIGHT]}}, P, PY, decode, 2, 0, 8, 64)
    assert state["1"]["passes"] and state["1"]["round"] == 0 and state["1"]["task"] is RIGHT
    assert counts["pass the stage untouched"] == 1 and not seen


def test_a_weak_answer_goes_back_with_the_witness_and_the_repair_the_stage_passes_is_kept():
    decode, seen = decoder(fenced(RIGHT))
    state, counts = spec_repair.run({"1": {"question": QUESTION, "tasks": [WEAK]}}, P, PY, decode, 2, 0, 8, 64)
    assert state["1"]["passes"] and state["1"]["round"] == 1
    said = seen[0][-1]["content"]
    assert said.startswith(debug_rows.SPEC_WEAK) and "double(" in said and said.endswith(debug_rows.ASK_AGAIN)
    assert seen[0][-2] == {"role": "assistant", "content": "```t\n" + surface.print_task(WEAK).strip() + "\n```"}
    assert counts["rounds"][0]["repaired (the stage passes it)"] == 1 and counts["pass the stage at the end"] == 1


def test_a_repair_that_is_still_wrong_becomes_the_next_attempt_with_its_own_witness():
    decode, seen = decoder(fenced(OTHER), fenced(RIGHT))
    state, counts = spec_repair.run({"1": {"question": QUESTION, "tasks": [WEAK]}}, P, PY, decode, 2, 0, 8, 64)
    assert state["1"]["passes"] and state["1"]["round"] == 2
    assert seen[1][-1]["content"].startswith(debug_rows.SPEC_WRONG)        # round two was told about OTHER
    assert [r["replaced by a repair with a new witness"] for r in counts["rounds"]] == [1, 0]


def test_a_reply_that_fails_a_test_is_refused_before_the_stage_and_the_attempt_stands():
    bad = task("r == 2 * n", "r := n;")
    decode, _ = decoder(fenced(bad), "prose")
    state, counts = spec_repair.run({"1": {"question": QUESTION, "tasks": [WEAK]}}, P, PY, decode, 1, 1, 8, 64)
    assert not state["1"]["passes"] and state["1"]["task"] is WEAK
    assert counts["rounds"][0]["refusals"] == {"fails a test": 1, "no task block": 1}


def test_without_a_python_there_is_no_witness_and_nothing_is_sent():
    decode, seen = decoder(fenced(RIGHT))
    state, counts = spec_repair.run({"1": {"question": QUESTION, "tasks": [WEAK]}}, P, {}, decode, 2, 0, 8, 64)
    assert not state["1"]["passes"] and not seen and counts["no witness to act on"] == 1
