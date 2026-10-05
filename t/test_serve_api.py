"""t/serve_api.py: the gate behind a local HTTP API. Who may call it (a token, loopback's own Host, no other
site's page: Jupyter Server's and OWASP's rules), what a job is (the terminal's own command), and how a job is
submitted, read, cancelled and erased."""
import http.client
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import certificate                                              # noqa: E402
import run_par                                                  # noqa: E402
import serve_api                                                # noqa: E402
import spec_check                                               # noqa: E402

PY = sys.executable
QUICK = ("import sys, json, pathlib; d = pathlib.Path(sys.argv[1]); print('SHOWN: a stand-in');"
         "(d / 'result.json').write_text(json.dumps({'ok': True})); (d / 'certificate.json').write_text('{\"c\": 1}')")


def stand_in(kind, body, job, student, base):
    """Commands that take the place of the real ones: quick, slow, refusing, or broken, by what the request says."""
    if body.get("slow"):
        return [PY, "-c", "import time; time.sleep(60)"]
    if body.get("refuse"):
        return [PY, "-c", "print('REFUSED: a stand-in'); raise SystemExit(1)"]
    if body.get("broken"):
        return [PY, "-c", "raise SystemExit(7)"]
    return [PY, "-c", QUICK, str(job)]


@pytest.fixture
def api(tmp_path):
    server, token = serve_api.serve(tmp_path, "127.0.0.1:1", "127.0.0.1:1", 0, seconds=30.0, token="t0ken")
    server.jobs.build = stand_in
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]

    def call(method, path, body=None, headers=None, token="t0ken", host=None):
        h = {"Host": host or f"127.0.0.1:{port}"}
        if token:
            h["Authorization"] = f"Bearer {token}"
        data = None
        if body is not None:
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        h.update(headers or {})
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
        c.request(method, path, body=data, headers=h)
        r = c.getresponse()
        raw = r.read()
        c.close()
        try:
            return r.status, json.loads(raw)
        except ValueError:
            return r.status, raw

    def wait(jid, states=serve_api.ENDED, seconds=20):
        end = time.time() + seconds
        while time.time() < end:
            _status, job = call("GET", f"/v1/jobs/{jid}")
            if job["state"] in states:
                return job
            time.sleep(0.05)
        raise AssertionError(f"job {jid} is still {job['state']}")
    call.wait, call.server, call.port = wait, server, port
    yield call
    server.shutdown()


def test_every_v1_request_needs_the_token_and_the_page_does_not(api):
    assert api("GET", "/v1/jobs/" + "0" * 16, token=None)[0] == 401
    assert api("GET", "/v1/jobs/" + "0" * 16, token="wrong")[0] == 401
    assert api("POST", "/v1/jobs", {"kind": "calc"}, token=None)[0] == 401
    assert api("DELETE", "/v1/jobs/" + "0" * 16, token=None)[0] == 401
    status, page = api("GET", "/", token=None)
    assert status == 200 and b"<title>dawnr</title>" in page and b"t0ken" not in page


def test_a_page_from_another_site_or_a_rebound_name_is_refused_whatever_it_sends(api):
    assert api("GET", "/v1/jobs/" + "0" * 16, host="evil.example:80")[0] == 403           # a name rebound to 127.0.0.1
    assert api("GET", "/", token=None, host="evil.example")[0] == 403
    assert api("POST", "/v1/jobs", {"kind": "calc"}, headers={"Origin": "http://evil.example"})[0] == 403
    assert api("POST", "/v1/jobs", {"kind": "calc"}, headers={"Sec-Fetch-Site": "cross-site"})[0] == 403
    own = f"http://127.0.0.1:{api.port}"
    assert api("POST", "/v1/jobs", {"kind": "calc"}, headers={"Origin": own, "Sec-Fetch-Site": "same-origin"})[0] == 202
    assert api("GET", "/v1/jobs/" + "0" * 16, host=f"localhost:{api.port}")[0] == 404          # localhost is this machine too


def test_a_request_that_is_not_a_json_job_is_refused_with_why(api):
    assert api("POST", "/v1/jobs", b"kind=calc", headers={"Content-Type": "application/x-www-form-urlencoded"})[0] == 415
    assert api("POST", "/v1/jobs", b"{not json")[0] == 400
    assert api("POST", "/v1/jobs", b"[1, 2]")[0] == 400
    status, reply = api("POST", "/v1/jobs", {"kind": "launch"})
    assert status == 400 and "`kind` must be one of ask, prove, verify, extract, cite, calc, check" in reply["error"]
    assert api("GET", "/v1/nothing")[0] == 404 and api("POST", "/v1/other", {"kind": "calc"})[0] == 404


def test_a_job_is_accepted_runs_and_is_read_back_with_its_text_result_and_certificate(api):
    status, job = api("POST", "/v1/jobs", {"kind": "ask"})
    assert status == 202 and job["state"] in ("queued", "running") and len(job["id"]) == 16
    job = api.wait(job["id"])
    assert job["state"] == "done" and job["outcome"] == "shown" and job["exit"] == 0
    assert job["text"].startswith("SHOWN: a stand-in") and job["result"] == {"ok": True} and job["certificate"] is True
    assert api("GET", f"/v1/jobs/{job['id']}/certificate") == (200, {"c": 1})
    refused = api.wait(api("POST", "/v1/jobs", {"kind": "ask", "refuse": True})[1]["id"])
    assert refused["state"] == "done" and refused["outcome"] == "refused" and refused["certificate"] is False
    assert api("GET", f"/v1/jobs/{refused['id']}/certificate")[0] == 404


def test_a_command_that_breaks_or_overruns_ends_as_failed_not_as_an_answer(api):
    broken = api.wait(api("POST", "/v1/jobs", {"kind": "ask", "broken": True})[1]["id"])
    assert broken["state"] == "failed" and broken["exit"] == 7 and "outcome" not in broken
    api.server.jobs.seconds = 0.3
    slow = api.wait(api("POST", "/v1/jobs", {"kind": "ask", "slow": True})[1]["id"])
    assert slow["state"] == "failed" and "did not finish" in slow["why"]


def test_the_same_idempotency_key_gives_back_the_job_it_first_made(api):
    first = api("POST", "/v1/jobs", {"kind": "calc"}, headers={"Idempotency-Key": "k1"})
    again = api("POST", "/v1/jobs", {"kind": "calc"}, headers={"Idempotency-Key": "k1"})
    other = api("POST", "/v1/jobs", {"kind": "calc"}, headers={"Idempotency-Key": "k2"})
    assert first[0] == 202 and again[0] == 200 and again[1]["id"] == first[1]["id"] and other[1]["id"] != first[1]["id"]


def test_a_running_job_is_cancelled_by_killing_it_and_what_it_left_is_erased(api):
    slow = api("POST", "/v1/jobs", {"kind": "ask", "slow": True})[1]
    api.wait(slow["id"], states=("running",))
    began = time.time()
    status, job = api("DELETE", f"/v1/jobs/{slow['id']}")
    assert status == 200 and job["state"] == "cancelled" and time.time() - began < 5
    assert not (api.server.jobs.dir / slow["id"]).exists()
    after = api.wait(api("POST", "/v1/jobs", {"kind": "ask"})[1]["id"])                    # the worker is free again
    assert after["state"] == "done"
    assert api("DELETE", f"/v1/jobs/{after['id']}")[1]["state"] == "done" and not (api.server.jobs.dir / after["id"]).exists()
    assert api("DELETE", "/v1/jobs/" + "0" * 16)[0] == 404


def test_a_cancel_that_arrives_while_the_command_is_starting_still_ends_it(api, monkeypatch):
    """Between `running` and the process existing there is nothing to kill; the worker must end the command itself.
    (Seen once on a slow CI machine as the next job staying queued behind a cancelled one.)"""
    real, started, gate = subprocess.Popen, [], threading.Event()

    def slow_start(*args, **kwargs):
        gate.wait(5)                                            # the cancel lands here
        started.append(real(*args, **kwargs))
        return started[-1]
    monkeypatch.setattr(serve_api.subprocess, "Popen", slow_start)
    slow = api("POST", "/v1/jobs", {"kind": "ask", "slow": True})[1]
    api.wait(slow["id"], states=("running",))
    assert api("DELETE", f"/v1/jobs/{slow['id']}")[1]["state"] == "cancelled" and not started
    gate.set()
    after = api.wait(api("POST", "/v1/jobs", {"kind": "ask"})[1]["id"], seconds=10)        # the worker is free again
    assert after["state"] == "done" and len(started) == 2 and started[0].poll() is not None
    assert not (api.server.jobs.dir / slow["id"]).exists() and api("GET", f"/v1/jobs/{slow['id']}")[1]["state"] == "cancelled"


def test_the_queue_is_bounded_and_says_so(api, monkeypatch):
    monkeypatch.setattr(serve_api, "MAX_QUEUE", 2)
    running = api("POST", "/v1/jobs", {"kind": "ask", "slow": True})[1]
    api.wait(running["id"], states=("running",))
    queued = [api("POST", "/v1/jobs", {"kind": "ask", "slow": True}) for _ in range(2)]
    assert [status for status, _ in queued] == [202, 202] and queued[1][1]["ahead"] == 2
    status, reply = api("POST", "/v1/jobs", {"kind": "ask"})
    assert status == 429 and "2 jobs are already waiting" in reply["error"]
    for _status, job in queued + [(0, running)]:
        api("DELETE", f"/v1/jobs/{job['id']}")


def test_each_kind_becomes_the_terminals_own_command_with_its_inputs_inside_the_jobs_directory(tmp_path):
    def build(kind, body):
        d = tmp_path / f"{kind}-{len(list(tmp_path.iterdir()))}"
        d.mkdir()
        return serve_api.command(kind, body, d, "s:1", "b:2"), d
    argv, d = build("ask", {"question": "Double a number.", "tests": ["assert double(3) == 6"]})
    assert argv[1:8] == ["t/answer.py", "--student", "s:1", "--python", "b:2", "--consistency", "5"]
    assert argv[8:] == ["--text", "Double a number.", "--test", "assert double(3) == 6", "--json", str(d / "result.json"),
                        "--certificate", str(d / "certificate.json")]
    argv, d = build("prove", {"specification": "t 1\ntask f(n: int) returns (r: int)\n  ensures r == n\n{\n}\n"})
    assert argv[1:3] == ["t/prove.py", "prove"] and (d / "spec.t").read_text().startswith("t 1\ntask f")
    argv, d = build("verify", {"python": "def f(n: int):\n    return n\n", "function": "f"})
    assert argv[1] == "t/verify_py.py" and argv[argv.index("--fn") + 1] == "f" and (d / "function.py").exists()
    argv, d = build("extract", {"fields": ["total(number): the amount due"],
                                "files": [{"name": "../../etc/passwd", "text": "a"}, {"name": "passwd", "text": "b"}]})
    files = argv[argv.index("--json") + 2:]
    assert argv[1] == "locallm/extract_docs.py" and [Path(f).parent for f in files] == [d / "files"] * 2
    assert sorted(Path(f).name for f in files) == ["_passwd", "passwd"]                   # a path is only its last part, and names do not collide
    argv, d = build("cite", {"question": "When?", "files": [{"name": "n.txt", "text": "x"}]})
    assert argv[1:5] == ["locallm/cite_docs.py", "--host", "b:2", "When?"]
    argv, d = build("calc", {"question": "2 + 2?"})
    assert argv[1] == "locallm/calc.py" and argv[-1] == "2 + 2?"
    argv, d = build("check", {"certificate": {"_type": "x"}, "provers": ["dafny"]})
    assert argv[1:3] == ["t/certificate.py", "check"] and argv[-2:] == ["--kernels", "dafny"] and json.loads((d / "given.cert.json").read_text()) == {"_type": "x"}


def test_a_chat_program_picks_the_kind_of_job_as_its_model_and_gets_the_gates_text_back(api):
    status, models = api("GET", "/v1/models")
    assert status == 200 and [m["id"] for m in models["data"]] == [f"dawnr-{k}" for k in serve_api.KINDS] + ["dawnr-tools"]
    status, reply = api("POST", "/v1/chat/completions", {"model": "dawnr-ask", "messages": [
        {"role": "user", "content": "Double a number.\nassert double(3) == 6"}]})
    assert status == 200 and reply["object"] == "chat.completion" and reply["choices"][0]["finish_reason"] == "stop"
    assert reply["choices"][0]["message"]["content"].startswith("SHOWN: a stand-in") and "/certificate)" in reply["choices"][0]["message"]["content"]
    assert api("POST", "/v1/chat/completions", {"model": "gpt-4", "messages": []})[0] == 404
    assert api("POST", "/v1/chat/completions", {"model": "dawnr-ask", "messages": []}, token=None)[0] == 401


def test_a_chat_reply_can_be_streamed_and_starts_before_the_job_ends(api):
    import http.client
    c = http.client.HTTPConnection("127.0.0.1", api.port, timeout=20)
    c.request("POST", "/v1/chat/completions", body=json.dumps({"model": "dawnr-calc", "stream": True, "messages": [{"role": "user", "content": "2 + 2?"}]}),
              headers={"Host": f"127.0.0.1:{api.port}", "Authorization": "Bearer t0ken", "Content-Type": "application/json"})
    r = c.getresponse()
    raw = r.read().decode()
    c.close()
    assert r.status == 200 and r.getheader("Content-Type").startswith("text/event-stream")
    events = [json.loads(l[6:]) for l in raw.splitlines() if l.startswith("data: {")]
    assert events[0]["choices"][0]["delta"] == {"role": "assistant", "content": ""}
    assert events[1]["choices"][0]["delta"]["content"].startswith("SHOWN: a stand-in") and events[-1]["choices"][0]["finish_reason"] == "stop"
    assert raw.rstrip().endswith("data: [DONE]")


WEATHER = {"type": "function", "function": {"name": "get_weather", "description": "The weather.", "parameters": {
    "type": "object", "required": ["loc"], "properties": {"loc": {"type": "string", "description": "The city"}, "days": {"type": "integer"}}}}}


def offered(api, monkeypatch, reply, request="Get the weather for me.", **more):
    """One request that offers a tool, with the base model's turn stood in for; (status, reply, what the model was sent)."""
    from locallm import tool_check
    sent = []

    def ask_model(host, tools, messages, post=None, max_tokens=400):
        sent.append({"host": host, "tools": tools, "messages": messages, "max_tokens": max_tokens})
        if isinstance(reply, Exception):
            raise reply
        return reply
    monkeypatch.setattr(tool_check, "ask_model", ask_model)
    status, got = api("POST", "/v1/chat/completions", {"model": "dawnr-tools", "tools": [WEATHER], "messages": [{"role": "user", "content": request}], **more})
    return status, got, sent


def call_of(**arguments):
    return {"content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "get_weather", "arguments": json.dumps(arguments)}}]}


def test_a_tool_call_is_handed_back_only_when_its_values_were_said(api, monkeypatch):
    # the person gave no city and the model made one up: the reply is a question that names the parameter
    status, got, sent = offered(api, monkeypatch, call_of(loc="Paris, France"))
    choice = got["choices"][0]
    assert status == 200 and choice["finish_reason"] == "stop" and "tool_calls" not in choice["message"]
    assert choice["message"]["content"].startswith("To call get_weather I need `loc` (The city). What should it be?")
    assert got["dawnr"]["check"] == "asked" and got["dawnr"]["proposed"] == [{"name": "get_weather", "arguments": {"loc": "Paris, France"}}]
    assert got["dawnr"]["ask"][0]["parameter"] == "loc" and got["dawnr"]["ask"][0]["tool"] == "get_weather"
    assert sent[0]["host"] == "127.0.0.1:1" and sent[0]["tools"] == [WEATHER]                    # the base model's server, the tools as offered
    # the city was said: the call comes back in OpenAI's shape, without the optional value nobody gave
    status, got, _ = offered(api, monkeypatch, call_of(loc="Lisbon", days=7), "Weather in Lisbon?")
    choice = got["choices"][0]
    assert choice["finish_reason"] == "tool_calls" and choice["message"]["content"] is None
    assert choice["message"]["tool_calls"] == [{"id": "c1", "type": "function", "function": {"name": "get_weather", "arguments": '{"loc": "Lisbon"}'}}]
    assert got["dawnr"] == {"check": "released", "left_out": [{"parameter": "days", "value": 7, "why": "that number was not said", "tool": "get_weather"}]}
    # a tool that was not offered is refused, and plain words pass through
    undeclared = {"content": "", "tool_calls": [{"function": {"name": "send_email", "arguments": "{}"}}]}
    assert offered(api, monkeypatch, undeclared)[1]["dawnr"]["check"] == "refused"
    status, got, _ = offered(api, monkeypatch, {"content": "Which city?"})
    assert got["choices"][0]["message"] == {"role": "assistant", "content": "Which city?"} and got["dawnr"] == {"check": "no call was written"}


def test_a_tools_request_that_cannot_be_served_says_why(api, monkeypatch):
    assert offered(api, monkeypatch, ConnectionRefusedError("refused"))[0] == 502
    assert api("POST", "/v1/chat/completions", {"model": "dawnr-tools", "messages": [{"role": "user", "content": "hi"}]})[0] == 400
    assert api("POST", "/v1/chat/completions", {"model": "dawnr-tools", "tools": [WEATHER], "messages": []})[0] == 400
    status, got = api("POST", "/v1/chat/completions", {"model": "dawnr-ask", "tools": [WEATHER], "messages": [{"role": "user", "content": "hi"}]})
    assert status == 400 and "tools are offered to the model dawnr-tools" in got["error"]["message"]
    assert api("POST", "/v1/chat/completions", {"model": "dawnr-tools", "tools": [WEATHER], "messages": [{"role": "user", "content": "x"}]}, token=None)[0] == 401
    # a program that names some other model and offers tools gets the checked turn too
    from locallm import tool_check
    monkeypatch.setattr(tool_check, "ask_model", lambda host, tools, messages, post=None, max_tokens=400: {"content": "Which city?"})
    status, got = api("POST", "/v1/chat/completions", {"model": "gpt-4o", "tools": [WEATHER], "messages": [{"role": "user", "content": "weather"}]})
    assert status == 200 and got["model"] == "dawnr-tools"


def test_a_checked_call_can_be_streamed(api, monkeypatch):
    import http.client
    from locallm import tool_check
    monkeypatch.setattr(tool_check, "ask_model", lambda host, tools, messages, post=None, max_tokens=400: call_of(loc="Lisbon"))
    c = http.client.HTTPConnection("127.0.0.1", api.port, timeout=20)
    c.request("POST", "/v1/chat/completions", body=json.dumps({"model": "dawnr-tools", "stream": True, "tools": [WEATHER],
                                                               "messages": [{"role": "user", "content": "Weather in Lisbon?"}]}),
              headers={"Host": f"127.0.0.1:{api.port}", "Authorization": "Bearer t0ken", "Content-Type": "application/json"})
    r = c.getresponse()
    raw = r.read().decode()
    c.close()
    events = [json.loads(l[6:]) for l in raw.splitlines() if l.startswith("data: {")]
    assert r.status == 200 and events[1]["choices"][0]["delta"]["tool_calls"][0]["function"] == {"name": "get_weather", "arguments": '{"loc": "Lisbon"}'}
    assert events[1]["choices"][0]["delta"]["tool_calls"][0]["index"] == 0 and events[-1]["choices"][0]["finish_reason"] == "tool_calls"
    assert events[-1]["dawnr"]["check"] == "released" and raw.rstrip().endswith("data: [DONE]")


def test_each_kind_reads_the_last_message_by_its_own_convention():
    def job(kind, *contents):
        return serve_api.from_chat(kind, [{"role": "user", "content": c} for c in contents])
    assert job("ask", "Double a number.\nassert double(3) == 6\nassert double(0) == 0") == {
        "kind": "ask", "question": "Double a number.", "tests": ["assert double(3) == 6", "assert double(0) == 0"]}
    v = job("verify", "Check this:\n```python\ndef f(n: int):\n    return n\n```\nassert f(1) == 1")
    assert v["python"] == "def f(n: int):\n    return n\n" and v["tests"] == ["assert f(1) == 1"]
    assert job("verify", "def f(n: int):\n    return n")["python"].startswith("def f")
    assert job("prove", "```t\nt 1\ntask f(n: int) returns (r: int)\n  ensures r == n\n{\n}\n```")["specification"].startswith("t 1\ntask f")
    assert job("calc", "What is 2 + 2?") == {"kind": "calc", "question": "What is 2 + 2?"}
    assert job("cite", "When is it due?\n---\nPayable by March 3.") == {"kind": "cite", "question": "When is it due?", "files": [{"name": "message.txt", "text": "Payable by March 3."}]}
    earlier = job("cite", "Payable by March 3.", "When is it due?")
    assert earlier["question"] == "When is it due?" and earlier["files"] == [{"name": "message-1.txt", "text": "Payable by March 3."}]
    e = job("extract", "total(number): the amount due\ndue(date): when\n---\nThe total due is $5 by March 3, 2026.")
    assert e["fields"] == ["total(number): the amount due", "due(date): when"] and e["files"][0]["text"].startswith("The total due")
    assert job("check", '{"_type": "x"}') == {"kind": "check", "certificate": {"_type": "x"}}
    parts = serve_api.from_chat("calc", [{"role": "user", "content": [{"type": "text", "text": "2 + 2?"}, {"type": "image_url", "image_url": {}}]}])
    assert parts["question"] == "2 + 2?"
    with pytest.raises(serve_api.Bad, match="not a certificate"):
        job("check", "hello")
    with pytest.raises(serve_api.Bad, match="no message to read"):
        serve_api.from_chat("ask", [{"role": "assistant", "content": "hi"}])


def test_a_message_the_kind_cannot_read_comes_back_as_a_reply_that_says_how(api):
    api.server.jobs.build = serve_api.command                   # the real reading of the request
    status, reply = api("POST", "/v1/chat/completions", {"model": "dawnr-ask", "messages": [{"role": "user", "content": "Double a number."}]})
    text = reply["choices"][0]["message"]["content"]
    assert status == 200 and text.startswith("dawnr could not read that: `tests` must hold at least one") and "one `assert f(arguments) == value` to a line" in text


def test_with_another_writer_the_jobs_that_write_t_ask_it_with_the_reference_and_the_rest_are_unchanged(tmp_path):
    def build(kind, body):
        d = tmp_path / f"{kind}-w"
        d.mkdir()
        return serve_api.command(kind, body, d, "https://writer.example/v1", "b:2", "big-model")
    wrote = ["--student", "https://writer.example/v1", "--student-name", "big-model", "--reference", "--max-new", "3072"]
    for kind, body in (("ask", {"question": "Double.", "tests": ["assert double(3) == 6"]}),
                       ("prove", {"specification": "t 1\ntask f(n: int) returns (r: int)\n  ensures r == n\n{\n}\n"}),
                       ("verify", {"python": "def f(n: int):\n    return n\n"})):
        argv = build(kind, body)
        i = argv.index("--student")
        assert argv[i:i + 7] == wrote, argv
    assert "--reference" not in build("calc", {"question": "2 + 2?"})
    jobs = serve_api.Jobs(tmp_path / "home", "https://writer.example/v1", "127.0.0.1:1", writer="big-model")
    assert jobs.writer == "big-model"


@pytest.mark.parametrize("kind, body, why", [
    ("ask", {"question": "Double."}, "`tests` must hold at least one"),
    ("ask", {"question": "", "tests": ["assert f(1) == 1"]}, "`question` must be a non-empty string"),
    ("ask", {"question": "x", "tests": ["import os"]}, "each test must be an `assert"),
    ("ask", {"question": "x" * 5000, "tests": ["assert f(1) == 1"]}, "`question` is longer than 4000 characters"),
    ("verify", {"python": "def f(n): return n", "function": "f; rm"}, "`function` must be a Python name"),
    ("extract", {"fields": [], "files": [{"name": "a", "text": "b"}]}, "`fields` must be a list of 1 to 30"),
    ("extract", {"fields": ["a: b"], "files": []}, "`files` must be a list of 1 to 20"),
    ("cite", {"question": "q", "files": [{"name": "a"}]}, "each file is"),
    ("check", {"certificate": "not an object"}, "`certificate` must be the certificate's JSON object"),
    ("check", {"certificate": {}, "provers": ["dafny; rm"]}, "`provers` must be a list of prover names"),
])
def test_a_job_that_lacks_what_its_command_needs_is_refused_before_anything_runs(tmp_path, kind, body, why):
    with pytest.raises(serve_api.Bad, match=why.replace("(", r"\(").replace(")", r"\)")):
        serve_api.command(kind, body, tmp_path, "s:1", "b:2")


dafny = pytest.mark.skipif("dafny" not in {b for b, _, _ in run_par.probe_backends()[1]}, reason="Dafny is not installed here")


@dafny
def test_a_certificate_is_replayed_through_the_api_by_the_real_command(api):
    import prove
    program = "t 1\ntask double(n: int) returns (r: int)\n  ensures r == 2 * n\n{\n  r := 2 * n;\n}\n"
    r = prove.prove(prove.read_spec(program), None, prover=lambda tasks, jobs: {
        task["name"]: {k: "verified / refuted" for k in spec_check.KERNELS} for task in tasks})
    api.server.jobs.build = serve_api.command
    job = api.wait(api("POST", "/v1/jobs", {"kind": "check", "certificate": certificate.from_proof(r), "provers": ["dafny"]})[1]["id"], seconds=120)
    assert job["state"] == "done" and job["outcome"] == "reproduced", job
    assert job["text"].startswith("REPRODUCED: proved here by 1 prover (dafny)") and job["result"]["verdict"] == "reproduced"


def test_the_page_is_opened_through_a_file_only_its_owner_can_read_so_the_token_is_on_no_command_line(tmp_path, monkeypatch):
    import platform
    monkeypatch.setattr(platform, "release", lambda: "6.8.0-generic")
    handed = []
    path = serve_api.open_page(tmp_path, 8713, "s3cret&\"", lambda address: handed.append(address) or True)
    assert path == tmp_path / "run" / "open.html" and handed == [path.as_uri()] and "s3cret" not in handed[0]
    assert (path.stat().st_mode & 0o777) == 0o600
    text = path.read_text()
    assert 'content="0; url=http://127.0.0.1:8713/#token=s3cret&amp;&quot;"' in text                   # the token, escaped, only inside the file
    # no browser here, or one that fails to start: nothing is left behind and the caller prints the address
    assert serve_api.open_page(tmp_path, 8713, "t", lambda address: False) is None and not path.exists()

    def broken(address):
        raise OSError("no display")
    assert serve_api.open_page(tmp_path, 8713, "t", broken) is None and not path.exists()
    # under WSL the Windows browser cannot read a Linux file: nothing is tried
    monkeypatch.setattr(platform, "release", lambda: "5.15.167.4-microsoft-standard-WSL2")
    assert serve_api.open_page(tmp_path, 8713, "t", lambda address: handed.append("tried") or True) is None and "tried" not in handed

