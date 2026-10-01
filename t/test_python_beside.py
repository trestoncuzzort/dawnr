"""t/python_beside.py: the Python written beside a question is kept only if it passes the question's
tests in the sandbox (Clover's second artifact, arXiv:2310.17807; HumanEval's harness shape,
github.com/openai/human-eval)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import py_sandbox                                               # noqa: E402
import python_beside                                            # noqa: E402

pytestmark = pytest.mark.skipif(not py_sandbox.available(), reason="bubblewrap is not installed")

P = {"1": {"fn": "double", "rec": {"text": "Double a number.", "test_list": ["assert double(3) == 6", "assert double(0) == 0"]}},
     "2": {"fn": "neg", "rec": {"text": "Negate a number.", "test_list": ["assert neg(3) == -3"]}}}
RIGHT = "```python\ndef double(n):\n    return 2 * n\n```"
WRONG = "```python\ndef double(n):\n    return n + 3\n```"            # fits the first test only


def test_only_python_that_passes_every_test_is_kept_and_a_run_resumes(tmp_path):
    asked = []

    def decode(conversations, temperature, salt, first, max_new):
        asked.append((len(conversations), temperature))
        return [(WRONG if temperature == 0.0 else RIGHT, True, 0) if "double" in c[-1]["content"] else ("no code", True, 0)
                for c in conversations]

    out = tmp_path / "python.jsonl"
    r = python_beside.write(decode, ["1", "2"], P, out, attempts=3, batch=8, max_new=64, writer="stub")
    rows = {row["task_id"]: row for row in map(json.loads, out.read_text().splitlines())}
    assert r == {"asked": 2, "kept": 1}
    assert rows[1]["code"].strip().endswith("return 2 * n") and rows[1]["attempt"] == 1 and rows[1]["attempts"] == 2
    assert rows[2]["code"] is None and rows[2]["attempts"] == 3
    assert asked[0] == (2, 0.0)                                 # one greedy attempt first, then sampled
    again = python_beside.write(decode, ["1", "2"], P, out, attempts=3, batch=8, max_new=64, writer="stub")
    assert again == {"asked": 0, "kept": 0} and len(out.read_text().splitlines()) == 2


def test_the_http_decode_spreads_requests_over_the_hosts_and_a_failed_one_is_an_empty_reply():
    seen = []

    def post(url, body, timeout):
        seen.append(url)
        if "8102" in url:
            raise OSError("down")
        return {"choices": [{"message": {"content": "hello"}}]}

    decode = python_beside.api_decode("openai", ["h:8101", "h:8102"], "m", {"x": 1}, post=post)
    out = decode([[{"role": "user", "content": "a"}], [{"role": "user", "content": "b"}]], 0.0, 0, "1", 16)
    assert [t for t, _s, _n in out] == ["hello", ""]
    assert sorted(seen) == ["http://h:8101/v1/chat/completions", "http://h:8102/v1/chat/completions"]


def test_the_ollama_shape_puts_sampling_in_options_and_turns_thinking_off():
    bodies = []

    def post(url, body, timeout):
        bodies.append((url, body))
        return {"message": {"content": "ok"}}

    decode = python_beside.api_decode("ollama", ["h:1"], "phi4-mini", {"num_gpu": 0}, post=post)
    assert decode([[{"role": "user", "content": "a"}]], 0.7, 2, "1", 32)[0][0] == "ok"
    url, body = bodies[0]
    assert url == "http://h:1/api/chat" and body["think"] is False
    assert body["options"] == {"temperature": 0.7, "top_p": 0.95, "seed": 2, "num_predict": 32, "num_gpu": 0}


def test_a_server_that_refuses_the_thinking_field_is_asked_again_without_it():
    bodies = []

    def post(url, body, timeout):
        bodies.append(dict(body))
        if "think" in body:
            raise OSError("400: this model does not support thinking")
        return {"message": {"content": "ok"}}

    decode = python_beside.api_decode("ollama", ["h:1"], "phi4-mini", post=post)
    assert decode([[{"role": "user", "content": "a"}]], 0.0, 0, "1", 32)[0][0] == "ok"
    assert "think" in bodies[0] and "think" not in bodies[1]

