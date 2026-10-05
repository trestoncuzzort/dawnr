"""t/serve_api.py: the gate behind a local HTTP API. Who may call it (a token, loopback's own Host, no other
site's page: Jupyter Server's and OWASP's rules), what a job is (the terminal's own command), and how a job is
submitted, read, cancelled and erased."""
import http.client
import json
import sys
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
    import threading
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
