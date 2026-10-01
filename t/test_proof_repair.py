"""The proof-repair loop (arXiv:2410.15756 3.3): Dafny's message back to the student, Dafny as the
in-loop judge. A fake student and a fake Dafny; the gates are the real ones."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import loop_dataset                                             # noqa: E402
import mbpp_dfy                                                 # noqa: E402
import proof_repair as pr                                       # noqa: E402
import spec_experiment as se                                    # noqa: E402
import student_rows                                             # noqa: E402
import surface                                                  # noqa: E402

ASSERTS = ["assert total(3) == 6", "assert total(0) == 0"]
ENTRY = se.mark_characters({"rec": {"test_list": ASSERTS}, "fn": "total",
                            "points": [mbpp_dfy.parse_assertion(a, strings=True) for a in ASSERTS]})
WEAK = """t 1
gate loops
task total(n: int) returns (r: int)
  requires n >= 0
  ensures 2 * r == n * (n + 1)
{
  r := 0;
  var i: int := 0;
  while i < n
    invariant 0 <= i
    decreases n - i
  {
    i := i + 1;
    r := r + i;
  }
}
"""
STRONG = WEAK.replace("    invariant 0 <= i\n", "    invariant 0 <= i and i <= n\n    invariant 2 * r == i * (i + 1)\n")
WRONG = STRONG.replace("r := r + i;", "r := r + 1;")
QUESTION = [{"role": "system", "content": se.STUDENT_SYSTEM}, {"role": "user", "content": "Problem: sum 1..n"}]


def _reply(text):
    return loop_dataset.fence(text.strip())


def _judge(tasks):
    """Dafny, played: a task is verified exactly when it carries the strong invariant."""
    out = []
    for t in tasks:
        ok = "2 * r == i * (i + 1)" in surface.print_task(t)
        out.append({"verified": ok, "said": [] if ok else ["- a postcondition could not be proved on this return path: `ensures ((2 * r) == (n * (n + 1)))`"]})
    return out


class _Student:
    def __init__(self, replies):
        self.replies, self.seen = list(replies), []

    def decode(self, conversations, temperature, salt, first, max_new):
        out = []
        for c in conversations:
            self.seen.append((c, temperature))
            out.append((self.replies.pop(0) if self.replies else "nothing", True, 5))
        return out


def _candidates(text=WEAK, question=QUESTION):
    return {"1": {"question": question, "task": surface.parse(text)}}


def test_what_dafny_verifies_is_carried_over_untouched_and_nothing_is_asked():
    student = _Student([])
    state, counts = pr.run(_candidates(STRONG), {"1": ENTRY}, student.decode, _judge, 2, 2, 8, 64)
    assert state["1"]["verified"] and state["1"]["round"] == 0 and student.seen == []
    assert counts["verified untouched"] == 1 and counts["rounds"][0]["sent back"] == 0


def test_the_failed_proof_goes_back_with_dafnys_lines_and_a_verified_repair_is_taken():
    student = _Student([_reply(STRONG)])
    state, counts = pr.run(_candidates(), {"1": ENTRY}, student.decode, _judge, 1, 0, 8, 64)
    conv, temperature = student.seen[0]
    assert temperature == 0.0 and [m["role"] for m in conv] == ["system", "user", "assistant", "user"]
    assert conv[-1]["content"].startswith("It passes the tests, but the proof does not go through. Dafny reports:")
    assert "`ensures ((2 * r) == (n * (n + 1)))`" in conv[-1]["content"] and conv[-1]["content"].endswith("Write the corrected task.")
    assert "invariant 0 <= i" in conv[-2]["content"]
    assert state["1"]["verified"] and state["1"]["round"] == 1
    assert counts["rounds"][0] == {"round": 1, "sent back": 1, "repaired (Dafny verifies)": 1,
                                  "replaced by a repair that passes the cheap gates": 0, "refusals": {}}


def test_a_repair_that_fails_a_test_never_reaches_dafny_and_the_attempt_stands():
    student = _Student([_reply(WRONG), "no code", _reply(WRONG)])
    state, counts = pr.run(_candidates(), {"1": ENTRY}, student.decode, _judge, 1, 2, 8, 64)
    assert not state["1"]["verified"] and state["1"]["round"] == 0
    assert counts["rounds"][0]["refusals"] == {"fails a test": 2, "no task block": 1}


def test_a_given_specification_must_survive_the_repair():
    spec = surface.parse(WEAK); spec["body"] = []
    question = [{"role": "system", "content": se.STUDENT_SYSTEM},
                {"role": "user", "content": student_rows.ASK + loop_dataset.fence(surface.print_task(spec).strip())}]
    changed = STRONG.replace("ensures 2 * r == n * (n + 1)", "ensures r >= 0")
    student = _Student([_reply(changed), _reply(STRONG)])
    state, counts = pr.run(_candidates(question=question), {"1": ENTRY}, student.decode, _judge, 1, 1, 8, 64)
    assert counts["rounds"][0]["refusals"] == {"specification changed": 1}
    assert state["1"]["verified"] and state["1"]["round"] == 1


def test_a_second_round_works_from_the_repair_that_passed_the_cheap_gates():
    middle = WEAK.replace("    invariant 0 <= i\n", "    invariant 0 <= i and i <= n\n")
    student = _Student([_reply(middle), _reply(STRONG)])
    state, counts = pr.run(_candidates(), {"1": ENTRY}, student.decode, _judge, 2, 0, 8, 64)
    assert [r["repaired (Dafny verifies)"] for r in counts["rounds"]] == [0, 1]
    assert counts["rounds"][0]["replaced by a repair that passes the cheap gates"] == 1
    assert "i <= n" in student.seen[1][0][-2]["content"]             # round 2 shows the round-1 repair
    assert state["1"]["verified"] and state["1"]["round"] == 2
