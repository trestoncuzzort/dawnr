"""The proof-stage repair (t/PREDICT-2026-10-21-proof-repair.md): the last proof attempt repairs the best refused
reply with the gate's own refusal as the witness (ExVerus arXiv:2603.25810, AxDafny arXiv:2606.32007). No model."""
import json
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mbpp_dfy                                                 # noqa: E402
import spec_experiment as se                                    # noqa: E402
import spec_first                                               # noqa: E402
import surface                                                  # noqa: E402


def _entry(*asserts):
    pts = [mbpp_dfy.parse_assertion(a, strings=True, nested_strings=True) for a in asserts]
    return se.mark_characters({"rec": {"text": "Write a function to square a number.", "test_list": list(asserts)},
                               "points": pts, "fn": "square"})


ENTRY = _entry("assert square(3) == 9", "assert square(4) == 16", "assert square(0) == 0")
SPEC = surface.parse("t 1\ntask square(n: int) returns (r: int)\n  ensures r == n * n\n{\n}\n")


def _task(body, ensures="r == n * n"):
    return f"```t\nt 1\ntask square(n: int) returns (r: int)\n  ensures {ensures}\n{{\n  {body}\n}}\n```"


def test_each_refusal_kind_gives_a_witness_the_student_can_act_on():
    cases = [
        ("no fence at all", "the reply has no fenced t task"),
        ("```t\nt 1\ntask (\n```", "the task does not parse:"),
        (_task("r := n * n;", ensures="r == n + n"), "the specification was changed:"),
        (_task("r := m * n;"), "not well formed: unbound var m"),
        (_task("r := n + n;"), "the test `square(3) == 9` fails: the task returns 6"),
    ]
    for reply, start in cases:
        answer, why = spec_first.accept(reply, SPEC, ENTRY)
        assert answer is None, reply
        ws = spec_first.proof_witnesses(reply, SPEC, ENTRY, why)
        assert ws and ws[0].startswith(start), (reply, why, ws)


def test_the_repair_question_continues_the_proof_question_with_the_witness():
    reply = _task("r := n + n;")
    _answer, why = spec_first.accept(reply, SPEC, ENTRY)
    q = spec_first.repair_proof_question(SPEC, "def square(n):\n    return n * n\n", reply, why, ENTRY)
    assert [m["role"] for m in q] == ["system", "user", "assistant", "user"]
    assert q[2]["content"] == reply and "- the test `square(3) == 9` fails" in q[3]["content"]
    assert "Keep its header, parameters, requires, ensures and spec funs exactly as given" in q[3]["content"]
    q2 = spec_first.repair_proof_question(SPEC, None, reply, why, ENTRY)
    assert q2[:2] == spec_first.question(SPEC)


def _outdir(root, tag):
    d = root / tag
    (d / "raw").mkdir(parents=True, exist_ok=True)
    return d


def _fake_student(script):
    """A student_generate stand-in: replies by attempt (the stage passed as the seed)."""
    mod = types.ModuleType("student_generate")
    asked = []

    def load(_model):
        return None, None

    def problem_seed(stage, _first):
        return stage

    def decode(_model, _tokenizer, conversations, _max_new, _temperature, _top_p, seed=None):
        asked.append((seed, [list(m["role"] for m in c) for c in conversations]))
        return [(script[seed], True, 1) for _ in conversations]
    mod.load, mod.problem_seed, mod.decode, mod.asked = load, problem_seed, decode, asked
    return mod


def test_the_last_attempt_repairs_the_best_refused_reply_and_the_record_says_so(tmp_path, monkeypatch):
    ids = tmp_path / "ids.txt"; ids.write_text("1\n")
    given = tmp_path / "given.jsonl"
    given.write_text(json.dumps({"task_id": 1, "tasks": [SPEC], "sources": ["lab/a"]}) + "\n")
    monkeypatch.setattr(se, "pool", lambda version: {1: ENTRY})
    monkeypatch.setattr(se, "OUT_ROOT", tmp_path)
    monkeypatch.setattr(se, "outdir", lambda tag: _outdir(tmp_path, tag))
    student = _fake_student({0: _task("r := m * n;"), 1: _task("r := n + n;"), 2: _task("r := n * n;")})
    monkeypatch.setitem(sys.modules, "student_generate", student)
    assert spec_first.main(["--model", "none", "--given-specs", str(given), "--tag", "pr", "--ids-file", str(ids),
                            "--samples", "2", "--proof-repair"]) == 0
    out = json.loads((tmp_path / "pr" / "spec_first.json").read_text())
    r = out["per_problem"]["1"]
    assert r["taken"] == {"attempt": 2, "specification": "lab/a", "repair": True}
    assert r["asked"] == 3 and r["proof repair asks"] == 1 and r["proof repaired"] == 1
    assert r["refusals"] == {"not well formed": 1, "fails a test": 1}
    assert student.asked[2][1] == [["system", "user", "assistant", "user"]]      # the third ask is the repair
    raw = json.loads((tmp_path / "pr" / "raw" / "1.json").read_text())
    assert raw["spec_first"]["attempt"] == 2 and raw["options"]["spec_first"]["proof_repair"] is True
    assert raw["messages"][2]["content"] == _task("r := n + n;")                  # the closest refusal, not the first


def test_without_the_flag_the_route_samples_as_before(tmp_path, monkeypatch):
    ids = tmp_path / "ids.txt"; ids.write_text("1\n")
    given = tmp_path / "given.jsonl"
    given.write_text(json.dumps({"task_id": 1, "tasks": [SPEC], "sources": ["lab/a"]}) + "\n")
    monkeypatch.setattr(se, "pool", lambda version: {1: ENTRY})
    monkeypatch.setattr(se, "OUT_ROOT", tmp_path)
    monkeypatch.setattr(se, "outdir", lambda tag: _outdir(tmp_path, tag))
    student = _fake_student({0: _task("r := m * n;"), 1: _task("r := n + n;"), 2: _task("r := n * n;")})
    monkeypatch.setitem(sys.modules, "student_generate", student)
    assert spec_first.main(["--model", "none", "--given-specs", str(given), "--tag", "pl", "--ids-file", str(ids),
                            "--samples", "2"]) == 0
    r = json.loads((tmp_path / "pl" / "spec_first.json").read_text())["per_problem"]["1"]
    assert r["taken"] == {"attempt": 2, "specification": "lab/a"} and "proof repair asks" not in r
    assert all(roles == [["system", "user"]] for _seed, roles in student.asked)
