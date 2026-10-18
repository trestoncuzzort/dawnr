"""Controls for matched evaluation: frozen requests, seed stability, and honest failures."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

spec = importlib.util.spec_from_file_location("v6_server_route", Path(__file__).with_name("v6_server_route.py"))
route = importlib.util.module_from_spec(spec)
spec.loader.exec_module(route)


def response(text="answer", finish="stop", tokens=3):
    return {"choices": [{"message": {"content": text}, "finish_reason": finish}],
            "usage": {"completion_tokens": tokens}}


def test_resume_reuses_the_saved_answer_and_a_new_model_cannot_reuse_it(tmp_path):
    calls = []
    def post(body):
        calls.append(body)
        return response(str(len(calls)))
    a = route.Decoder("unused", "candidate", "weights-a", tmp_path, post=post)
    messages = [{"role": "user", "content": "task"}]
    assert a.one(messages, 10, .7, .95, 1) == ("1", True, 3)
    assert a.one(messages, 10, .7, .95, 1) == ("1", True, 3)
    b = route.Decoder("unused", "candidate", "weights-b", tmp_path, post=post)
    assert b.one(messages, 10, .7, .95, 1) == ("2", True, 3)
    assert len(calls) == 2


def test_seed_and_answer_do_not_depend_on_batch_order(tmp_path):
    calls = []
    def post(body):
        calls.append(body)
        return response(str(body["seed"]))
    d = route.Decoder("unused", "model", "identity", tmp_path, post=post)
    a, b = [[{"role": "user", "content": s}] for s in ("a", "b")]
    ab = d.decode(None, None, [a, b], 10, .7, .95, 4)
    ba = d.decode(None, None, [b, a], 10, .7, .95, 4)
    assert ab == ba[::-1] and len(calls) == 2
    assert all(c["top_k"] == 0 and c["min_p"] == 0 and c["repeat_penalty"] == 1 for c in calls)
    assert all(c["chat_template_kwargs"] == {"enable_thinking": False} for c in calls)
    assert d.one(a, 10, .7, .95, 5)[0] != ab[0][0]


@pytest.mark.parametrize("bad", [response(finish=None), response(tokens=11),
                                 response(text=None), {"choices": []}])
def test_invalid_server_result_is_not_cached_or_counted_as_a_refusal(tmp_path, bad):
    d = route.Decoder("unused", "model", "identity", tmp_path, post=lambda _body: bad)
    with pytest.raises(ValueError):
        d.one([], 10, 0, .95, 0)
    assert list(tmp_path.iterdir()) == []


def test_length_capped_reply_is_preserved_as_unfinished(tmp_path):
    d = route.Decoder("unused", "model", "identity", tmp_path,
                      post=lambda _body: response("partial", "length", 10))
    assert d.one([], 10, 0, .95, 0) == ("partial", False, 10)


@pytest.mark.parametrize("missing", ["panel-outcome", "saved-answer"])
def test_successful_exit_without_complete_evidence_cannot_mark_a_run_complete(tmp_path, monkeypatch, missing):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import spec_first
    monkeypatch.setattr(spec_first.se, "OUT_ROOT", tmp_path / "sets")
    panel = tmp_path / "ids.txt"
    panel.write_text("17\n")
    cache = tmp_path / "cache"
    def fake_route(_args):
        summary = {"problems": 1, "per_problem": {}, "answered": 0}
        if missing == "saved-answer":
            summary.update(per_problem={"17": {"taken": {"attempt": 0}}}, answered=1)
        directory = spec_first.se.outdir("partial")
        (directory / "spec_first.json").write_text(json.dumps(summary))
        return 0
    monkeypatch.setattr(spec_first, "main", fake_route)
    with pytest.raises(RuntimeError):
        route.main(["--endpoint", "unused", "--model", "v5", "--identity", "pinned",
                    "--cache", str(cache), "--", "--tag", "partial", "--ids-file", str(panel)])
    assert not (cache / "completed.json").exists()
