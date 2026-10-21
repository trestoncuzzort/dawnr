"""The repair turn at the specification stage (t/PREDICT-2026-10-21-repair-turn.md): a dropped specification
goes back to the student with the interpreter's witnesses, the problem's own test that it rejects or the wrong
result it accepts (ExVerus arXiv:2603.25810 and AxDafny arXiv:2606.32007 send a counterexample back). No model:
a scripted student stands in."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mbpp_dfy                                                 # noqa: E402
import spec_experiment as se                                    # noqa: E402
import spec_first                                               # noqa: E402
import spec_quality                                             # noqa: E402
import surface                                                  # noqa: E402


def _entry(*asserts):
    pts = [mbpp_dfy.parse_assertion(a, strings=True, nested_strings=True) for a in asserts]
    return se.mark_characters({"rec": {"text": "Write a function to square a number.", "test_list": list(asserts)},
                               "points": pts, "fn": "square"})


ENTRY = _entry("assert square(3) == 9", "assert square(4) == 16", "assert square(0) == 0")
PY = "def square(n):\n    return n * n\n"


def _spec(ensures, params="n: int", requires=""):
    req = f"  requires {requires}\n" if requires else ""
    return surface.parse(f"t 1\ntask square({params}) returns (r: int)\n{req}  ensures {ensures}\n{{\n}}\n")


def _fence(ensures):
    return f"```t\nt 1\ntask square(n: int) returns (r: int)\n  ensures {ensures}\n{{\n}}\n```"


class _Student:
    """Replies in order to every repair question; records what it was asked."""

    def __init__(self, replies):
        self.replies, self.asked = list(replies), []

    def decode(self, conversations, temperature, salt, _first, _max_new):
        out = []
        for c in conversations:
            self.asked.append((c, temperature, salt))
            out.append((self.replies.pop(0) if self.replies else "", True, 1))
        return out


def test_a_wrong_specification_is_witnessed_by_the_test_it_rejects_and_the_false_clause():
    ws = spec_quality.witnesses(_spec("r == n + n"), ENTRY)
    assert ws[0] == "the test `square(3) == 9` is rejected: `ensures r == n + n` is false on it"
    assert ws[1] == "the wrong result `6` for the test `square(3) == 9` is accepted: every ensures holds on it"
    assert spec_quality.witnesses(_spec("r == n * n or r == 0"), ENTRY) == [
        "the wrong result `0` for the test `square(3) == 9` is accepted: every ensures holds on it"]


def test_a_vague_specification_is_witnessed_by_a_wrong_result_it_accepts():
    ws = spec_quality.witnesses(_spec("r >= 0"), ENTRY)
    assert len(ws) == 1 and ws[0].startswith("the wrong result `") and "for the test `square(3) == 9` is accepted" in ws[0]


def test_a_specification_wrong_and_vague_gives_both_witnesses_in_that_order():
    ws = spec_quality.witnesses(_spec("r == n + n or r > 100"), ENTRY)
    assert ws[0].startswith("the test `square(3) == 9` is rejected") and ws[1].startswith("the wrong result")


def test_a_signature_that_does_not_fit_the_tests_is_witnessed_as_such():
    ws = spec_quality.witnesses(_spec("len(r) >= 0", params="s: seq").__class__(
        {**_spec("r >= 0"), "params": [{"name": "s", "type": "seq"}]}), ENTRY)
    assert len(ws) == 1 and ws[0].startswith("the test `square(3) == 9` does not fit the task's signature")


def test_a_precondition_that_excludes_every_test_is_witnessed():
    ws = spec_quality.witnesses(_spec("r == n * n", requires="n > 100"), ENTRY)
    assert ws == ["no test satisfies the requires: the precondition excludes every test"]


def test_a_string_result_is_shown_as_the_test_wrote_it():
    entry = se.mark_characters({"rec": {"test_list": ["assert parity(3) == 'ODD'", "assert parity(2) == 'EVEN'"]},
                                "points": [mbpp_dfy.parse_assertion("assert parity(3) == 'ODD'", strings=True),
                                           mbpp_dfy.parse_assertion("assert parity(2) == 'EVEN'", strings=True)],
                                "fn": "parity"})
    task = surface.parse("t 1\ntask parity(n: int) returns (r: seq)\n  ensures len(r) >= 3\n{\n}\n")
    ws = spec_quality.witnesses(task, entry)
    assert ws and ws[0].startswith("the wrong result `'") and "for the test `parity(3) == 'ODD'`" in ws[0]


def test_the_repair_question_continues_the_specification_question_with_the_witnesses():
    q = spec_first.repair_question(ENTRY, PY, "```t\nnonsense\n```", ["the test `square(3) == 9` is rejected: x"])
    assert [m["role"] for m in q] == ["system", "user", "assistant", "user"]
    assert q[:2] == spec_first.spec_first_rows.spec_question(ENTRY, PY)
    assert q[2]["content"] == "```t\nnonsense\n```"
    assert "- the test `square(3) == 9` is rejected: x" in q[3]["content"]
    assert "named `square`" in q[3]["content"] and "the body stays empty" in q[3]["content"]


def test_the_best_candidate_is_the_most_correct_then_most_complete_scored_one():
    wrong, vague = _spec("r == n + n"), _spec("r >= 0")
    written = [("written/0", wrong), ("written/1", vague)]
    replies = [("written/0", "W"), ("written/1", "V")]
    scored = []
    spec_first.kept_specifications(written, ENTRY, 3, record=scored)
    label, reply, ws = spec_first.best_candidate(written, scored, replies, ENTRY)
    assert (label, reply) == ("written/1", "V")                  # correctness 1.0 beats 0.0
    assert ws[0].startswith("the wrong result")


def test_an_unparsable_last_reply_is_repaired_from_its_parse_failure():
    label, reply, ws = spec_first.best_candidate([], [], [("written/0", "no fence at all")], ENTRY)
    assert (label, reply) == ("written/0", "no fence at all") and ws == ["the reply has no fenced t task"]
    label, reply, ws = spec_first.best_candidate([], [], [("written/0", "```t\nt 1\ntask (\n```")], ENTRY)
    assert ws[0].startswith("the task does not parse:")
    assert spec_first.best_candidate([], [], [], ENTRY) is None


def _state(written_specs):
    """A problem "1" after the plain samples: written candidates, their replies, the scored records, nothing kept."""
    written = {"1": [(f"written/{i}", t) for i, t in enumerate(written_specs)]}
    replies = {"1": [(f"written/{i}", f"reply {i}") for i in range(len(written_specs))]}
    scored = []
    per = {"1": spec_first.kept_specifications(written["1"], ENTRY, 3, record=scored)[0]}
    scored_by = {"1": scored}
    record = [{"task_id": 1, **r} for r in scored]
    stats = {"1": {"scored": len(scored), "kept": len(per["1"]), "duplicate": 0,
                   "dropped": sum(r["verdict"] == "dropped" for r in scored), "unscorable": 0,
                   "repair asks": 0, "repaired": 0, "repair witnesses": []}}
    return written, replies, per, scored_by, record, stats


def test_a_kept_repair_enters_per_and_the_records_and_stops_further_repairs():
    written, replies, per, scored_by, record, stats = _state([_spec("r == n + n")])
    student = _Student([_fence("r == n * n")])
    n = spec_first.repaired_specifications(student.decode, ["1"], {"1": PY}, {"1": ENTRY}, written, replies, per,
                                           scored_by, 2, 3, 16, 64, record, stats)
    assert n == 1 and [k["source"] for k in per["1"]] == ["repair/0"]
    assert len(student.asked) == 1 and student.asked[0][1] == 0.0 and student.asked[0][2] == 200
    assert student.asked[0][0][2]["content"] == "reply 0"           # the candidate shown is the student's own reply
    assert stats["1"]["repair asks"] == 1 and stats["1"]["repaired"] == 1 and stats["1"]["kept"] == 1
    assert stats["1"]["repair witnesses"][0] == "the test `square(3) == 9` is rejected: `ensures r == n + n` is false on it"
    assert len(stats["1"]["repair witnesses"]) == 2             # it also accepts a wrong result; both are shown
    assert record[-1]["source"] == "repair/0" and record[-1]["verdict"] == "kept"
    assert replies["1"][-1] == ("repair/0", _fence("r == n * n"))


def test_a_failed_repair_is_tried_once_more_sampled_then_the_problem_stays_unkept():
    written, replies, per, scored_by, record, stats = _state([_spec("r == n + n")])
    student = _Student([_fence("r == n - n"), "no task here"])
    n = spec_first.repaired_specifications(student.decode, ["1"], {"1": PY}, {"1": ENTRY}, written, replies, per,
                                           scored_by, 2, 3, 16, 64, record, stats)
    assert n == 0 and per["1"] == [] and stats["1"]["repair asks"] == 2 and stats["1"]["repaired"] == 0
    assert [a[1] for a in student.asked] == [0.0, spec_first.TEMPERATURE] and [a[2] for a in student.asked] == [200, 201]
    assert record[-1]["source"] == "repair/0" and record[-1]["verdict"] == "dropped"
    assert stats["1"]["dropped"] == 2 and stats["1"]["scored"] == 2


def test_a_problem_with_a_kept_specification_or_no_python_is_never_asked():
    written, replies, per, scored_by, record, stats = _state([_spec("r == n * n")])
    student = _Student([_fence("r == n * n")])
    assert per["1"]
    n = spec_first.repaired_specifications(student.decode, ["1", "2"], {"1": PY}, {"1": ENTRY, "2": ENTRY}, written,
                                           replies, per, scored_by, 2, 3, 16, 64, record, stats)
    assert n == 0 and student.asked == []


def test_the_main_route_refuses_repair_without_the_students_python(tmp_path):
    import pytest
    ids = tmp_path / "ids.txt"; ids.write_text("1\n")
    with pytest.raises(SystemExit):
        spec_first.main(["--model", "none", "--from-samples", "x", "--tag", "r", "--ids-file", str(ids), "--repair", "2"])
