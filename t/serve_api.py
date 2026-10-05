#!/usr/bin/env python3
"""t/serve_api.py -- the gate behind a local HTTP API, and a page in the browser over it (2026-10-05).

    python3 t/serve_api.py --student 127.0.0.1:8711 --base 127.0.0.1:8712 [--port 8713] [--home DIR]

`dawnr serve api` starts the models and then this.

Every job is one of the commands the terminal runs (ask, prove, verify, extract, cite, calc, check), started as a
child process with the same arguments and read back from the files it writes, so the API and the terminal are one
code path and a cancel is a kill. The shape is internal/ENTERPRISE-PLAN-2026-09-19.md's: submit a job, read its
state, cancel it, fetch its certificate, replay a certificate; idempotency keys, a bounded queue, a time limit, and
states that end (done, failed, cancelled).

    POST   /v1/jobs                    {"kind": "ask", "question": "...", "tests": ["assert f(1) == 2"]}  -> 202 {"id", "state"}
    GET    /v1/jobs/ID                 {"state", "outcome", "text", "result", "certificate": true|false, ...}
    GET    /v1/jobs/ID/certificate     the certificate, for `dawnr check` or POST /v1/jobs {"kind": "check", ...}
    DELETE /v1/jobs/ID                 cancel it if it has not ended, and erase what it left on disk
    GET    /v1/health                  what is installed and how long the queue is
    GET    /                           the page (t/ui.html)

Who may call it. This server runs model-written and person-given code (in the sandbox) and reads back the person's
files, so access to it is access to those. Jupyter Server's answer to the same position is a token generated at
start, on by default, carried in the Authorization header and in the URL the person opens
(jupyter-server.readthedocs.io, "Security in the Jupyter Server"); OWASP's CSRF cheat sheet asks for a token on
every state-changing request and the origin verified with the standard headers. Here: it binds to loopback; a
token is made at start, written to a file only its owner can read, and required on every /v1 request as
`Authorization: Bearer`, which a page from another site cannot send without a preflight this server never answers;
the Host header must name loopback, so a page that rebinds its own name to 127.0.0.1 is refused; an Origin header,
when present, must be this server's own; a POST must be application/json. Research receipt 79e484ca2cb3.
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import re
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
KINDS = ("ask", "prove", "verify", "extract", "cite", "calc", "check")
ENDED = ("done", "failed", "cancelled")
MAX_BODY = 4 * 1024 * 1024
MAX_QUEUE = 16
KEEP = 200                     # finished jobs kept on disk; the oldest go first
_SAFE = re.compile(r"[^A-Za-z0-9._-]+")
_ID = re.compile(r"[a-f0-9]{16}")


class Bad(Exception):
    """A request that cannot be run; the message is the reply."""


def _text(body: dict, key: str, limit: int, required: bool = True) -> str:
    value = body.get(key)
    if value is None and not required:
        return ""
    if not isinstance(value, str) or not value.strip():
        raise Bad(f"`{key}` must be a non-empty string")
    if len(value) > limit:
        raise Bad(f"`{key}` is longer than {limit} characters")
    return value


def _tests(body: dict) -> list[str]:
    tests = body.get("tests") or []
    if not isinstance(tests, list) or len(tests) > 20 or not all(isinstance(t, str) and len(t) <= 600 for t in tests):
        raise Bad("`tests` must be a list of at most 20 `assert f(arguments) == value` lines")
    if any(not t.strip().startswith("assert ") for t in tests):
        raise Bad("each test must be an `assert f(arguments) == value` line")
    return [t.strip() for t in tests]


def _files(body: dict, job: Path) -> list[str]:
    files = body.get("files")
    if not isinstance(files, list) or not 1 <= len(files) <= 20:
        raise Bad("`files` must be a list of 1 to 20 {\"name\", \"text\"}")
    out, used = [], set()
    (job / "files").mkdir()
    for f in files:
        if not isinstance(f, dict) or not isinstance(f.get("text"), str) or not isinstance(f.get("name"), str):
            raise Bad("each file is {\"name\": \"...\", \"text\": \"...\"}")
        if len(f["text"]) > 1_000_000:
            raise Bad(f"{f['name']!r} is longer than a million characters")
        name = _SAFE.sub("_", Path(f["name"]).name).strip("._") or "file"
        while name in used:
            name = "_" + name
        used.add(name)
        (job / "files" / name).write_text(f["text"], encoding="utf-8")
        out.append(str(job / "files" / name))
    return out


def command(kind: str, body: dict, job: Path, student: str, base: str) -> list[str]:
    """The terminal's own command for the job, its inputs written under the job's directory. Bad when the request
    does not hold what that command needs."""
    py, result, cert = sys.executable, str(job / "result.json"), str(job / "certificate.json")
    tests = [x for t in (_tests(body) if kind in ("ask", "prove", "verify") else []) for x in ("--test", t)]
    if kind == "ask":
        if not tests:
            raise Bad("`tests` must hold at least one `assert f(arguments) == value` line")
        return [py, "t/answer.py", "--student", student, "--python", base, "--consistency", "5",
                "--text", _text(body, "question", 4000), *tests, "--json", result, "--certificate", cert]
    if kind == "prove":
        (job / "spec.t").write_text(_text(body, "specification", 20000), encoding="utf-8")
        return [py, "t/prove.py", "prove", "--student", student, "--spec", str(job / "spec.t"), *tests,
                "--json", result, "--certificate", cert]
    if kind == "verify":
        (job / "function.py").write_text(_text(body, "python", 20000), encoding="utf-8")
        fn = _text(body, "function", 80, required=False)
        if fn and not fn.isidentifier():
            raise Bad("`function` must be a Python name")
        return [py, "t/verify_py.py", "--student", student, "--file", str(job / "function.py"), *(["--fn", fn] if fn else []),
                *tests, "--json", result, "--certificate", cert]
    if kind == "extract":
        fields = body.get("fields")
        if not isinstance(fields, list) or not 1 <= len(fields) <= 30 or not all(isinstance(f, str) and 0 < len(f) <= 300 for f in fields):
            raise Bad("`fields` must be a list of 1 to 30 strings like \"total(number): the amount due\"")
        return [py, "locallm/extract_docs.py", "--host", base, *[x for f in fields for x in ("--field", f)],
                "--json", result, *_files(body, job)]
    if kind == "cite":
        return [py, "locallm/cite_docs.py", "--host", base, _text(body, "question", 4000), *_files(body, job)]
    if kind == "calc":
        return [py, "locallm/calc.py", "--host", base, "--json", result, _text(body, "question", 4000)]
    if kind == "check":
        certificate = body.get("certificate")
        if not isinstance(certificate, dict):
            raise Bad("`certificate` must be the certificate's JSON object")
        provers = body.get("provers") or []
        if not isinstance(provers, list) or not all(isinstance(k, str) and k.isalpha() for k in provers):
            raise Bad("`provers` must be a list of prover names")
        (job / "given.cert.json").write_text(json.dumps(certificate), encoding="utf-8")
        return [py, "t/certificate.py", "check", str(job / "given.cert.json"), "--json", result,
                *(["--kernels", ",".join(provers)] if provers else [])]
    raise Bad(f"`kind` must be one of {', '.join(KINDS)}")


# what a command's exit status means, in a word a caller can branch on
_OUTCOME = {"check": {0: "reproduced", 1: "failed", 2: "undecided here"}, "ask": {0: "shown", 1: "refused"},
            "prove": {0: "proved", 1: "not proved"}, "verify": {0: "verified", 1: "not verified"},
            "calc": {0: "answered", 1: "refused"}, "extract": {0: "read"}, "cite": {0: "read"}}


class Jobs:
    """The queue and its one worker: the models answer one request at a time, so jobs run one after another."""

    def __init__(self, home: Path, student: str, base: str, seconds: float = 1800.0, build=command):
        self.home, self.student, self.base, self.seconds, self.build = home, student, base, seconds, build
        self.dir = home / "jobs"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.jobs: dict[str, dict] = {}
        self.keys: dict[str, str] = {}
        self.lock = threading.Lock()
        self.waiting: queue.Queue = queue.Queue()
        self.process: dict[str, subprocess.Popen] = {}
        threading.Thread(target=self._work, daemon=True).start()

    def submit(self, body: dict, key: str | None) -> tuple[dict, bool]:
        """(the job, whether it is new). The same idempotency key gives back the job it first made."""
        kind = body.get("kind")
        if kind not in KINDS:
            raise Bad(f"`kind` must be one of {', '.join(KINDS)}")
        with self.lock:
            if key and key in self.keys and self.keys[key] in self.jobs:
                return self.public(self.jobs[self.keys[key]]), False
            if sum(1 for j in self.jobs.values() if j["state"] == "queued") >= MAX_QUEUE:
                raise OverflowError
            jid = secrets.token_hex(8)
            job_dir = self.dir / jid
            job_dir.mkdir()
            try:
                argv = self.build(kind, body, job_dir, self.student, self.base)
            except Bad:
                shutil.rmtree(job_dir, ignore_errors=True)
                raise
            job = {"id": jid, "kind": kind, "state": "queued", "submitted": time.time(), "argv": argv, "dir": job_dir}
            self.jobs[jid] = job
            if key:
                self.keys[key] = jid
        self.waiting.put(jid)
        return self.public(job), True

    def _work(self) -> None:
        while True:
            jid = self.waiting.get()
            with self.lock:
                job = self.jobs.get(jid)
                if job is None or job["state"] != "queued":
                    continue
                job.update(state="running", started=time.time())
            env = dict(os.environ, T_MIN_KERNELS=os.environ.get("T_MIN_KERNELS", "1"), PYTHONUNBUFFERED="1")
            try:
                with open(job["dir"] / "stdout.txt", "w", encoding="utf-8") as out:
                    p = subprocess.Popen(job["argv"], cwd=REPO, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                         env=env, start_new_session=True)
                    self.process[jid] = p
                    try:
                        code = p.wait(timeout=self.seconds)
                    except subprocess.TimeoutExpired:
                        self._kill(p)
                        code = None
            except OSError as error:
                code = None
                (job["dir"] / "stdout.txt").write_text(f"the command could not be started: {error}\n", encoding="utf-8")
            finally:
                self.process.pop(jid, None)
            with self.lock:
                if job["state"] == "cancelled":
                    continue
                if code is None:
                    job.update(state="failed", why=f"it did not finish in {self.seconds:.0f} s, or could not be started")
                elif code in _OUTCOME[job["kind"]]:
                    job.update(state="done", exit=code, outcome=_OUTCOME[job["kind"]][code])
                else:
                    job.update(state="failed", exit=code, why="the command stopped with an error; its output says why")
                job["finished"] = time.time()
            self._trim()

    @staticmethod
    def _kill(p: subprocess.Popen) -> None:
        try:
            os.killpg(p.pid, signal.SIGKILL)                    # the command and the provers it started
        except (ProcessLookupError, PermissionError):
            pass
        p.wait()

    def cancel(self, jid: str) -> dict | None:
        """End a job that has not ended, and erase what any job left on disk. None when there is no such job."""
        with self.lock:
            job = self.jobs.get(jid)
            if job is None:
                return None
            if job["state"] not in ENDED:
                job.update(state="cancelled", finished=time.time())
            p = self.process.get(jid)
        if p is not None:
            self._kill(p)
        shutil.rmtree(job["dir"], ignore_errors=True)
        return self.public(job)

    def _trim(self) -> None:
        with self.lock:
            ended = sorted((j for j in self.jobs.values() if j["state"] in ENDED), key=lambda j: j.get("finished", 0))
            for job in ended[:-KEEP] if len(ended) > KEEP else []:
                shutil.rmtree(job["dir"], ignore_errors=True)
                del self.jobs[job["id"]]

    def public(self, job: dict) -> dict:
        out = {k: job[k] for k in ("id", "kind", "state", "submitted", "started", "finished", "exit", "outcome", "why") if k in job}
        d = job["dir"]
        if job["state"] in ENDED and d.exists():
            try:
                out["text"] = (d / "stdout.txt").read_text(encoding="utf-8", errors="replace")[-200_000:]
            except OSError:
                out["text"] = ""
            if (d / "result.json").exists():
                try:
                    out["result"] = json.loads((d / "result.json").read_text(encoding="utf-8"))
                except ValueError:
                    pass
        out["certificate"] = (d / "certificate.json").exists()
        if job["state"] == "queued":
            out["ahead"] = sum(1 for j in self.jobs.values() if j["state"] in ("queued", "running") and j["submitted"] < job["submitted"])
        return out

    def get(self, jid: str) -> dict | None:
        with self.lock:
            job = self.jobs.get(jid)
            return self.public(job) if job else None

    def certificate(self, jid: str) -> bytes | None:
        with self.lock:
            job = self.jobs.get(jid)
        path = job["dir"] / "certificate.json" if job else None
        return path.read_bytes() if path and path.exists() else None


def _up(host: str) -> bool:
    try:
        with urllib.request.urlopen(f"http://{host}/health", timeout=2) as r:
            return b'"ok"' in r.read()
    except Exception:                                           # noqa: BLE001 -- down is down
        return False


def health(jobs: Jobs) -> dict:
    sys.path.insert(0, str(HERE))
    import run_par
    cols, _present = run_par.probe_backends()
    with jobs.lock:
        waiting = sum(1 for j in jobs.jobs.values() if j["state"] == "queued")
        running = sum(1 for j in jobs.jobs.values() if j["state"] == "running")
    return {"provers": {name: version for name, version in cols if not str(version).startswith("ABSENT")},
            "student": _up(jobs.student), "base": _up(jobs.base), "queued": waiting, "running": running, "kinds": list(KINDS)}


def make_handler(jobs: Jobs, token: str, port: int, page: bytes):
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}

    class Handler(BaseHTTPRequestHandler):
        server_version = "dawnr"

        def log_message(self, *_):                              # the page polls; a line a poll would bury everything else
            pass

        def _send(self, status: int, body, content: str = "application/json") -> None:
            data = body if isinstance(body, bytes) else (json.dumps(body) + "\n").encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content + ("; charset=utf-8" if not content.startswith("application/octet") else ""))
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'")
            self.end_headers()
            self.wfile.write(data)

        def _refused(self) -> str | None:
            """Why this request is not this machine's own person or program, or None."""
            if self.headers.get("Host") not in allowed_hosts:
                return "this server answers only as 127.0.0.1 or localhost"
            origin = self.headers.get("Origin")
            if origin is not None and origin not in {f"http://{h}" for h in allowed_hosts}:
                return "a page from another site may not call this server"
            if self.headers.get("Sec-Fetch-Site") not in (None, "same-origin", "none"):
                return "a page from another site may not call this server"
            return None

        def _authorised(self) -> bool:
            given = self.headers.get("Authorization", "")
            return given.startswith("Bearer ") and secrets.compare_digest(given[7:].strip(), token)

        def _gate(self) -> bool:
            why = self._refused()
            if why:
                self._send(403, {"error": why})
                return False
            if not self._authorised():
                self._send(401, {"error": "send the token dawnr printed at start as `Authorization: Bearer <token>`"})
                return False
            return True

        def do_GET(self):                                       # noqa: N802
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                why = self._refused()
                return self._send(403, {"error": why}) if why else self._send(200, page, "text/html")
            if not self._gate():
                return None
            if path == "/v1/health":
                return self._send(200, health(jobs))
            m = re.fullmatch(r"/v1/jobs/([a-f0-9]{16})(/certificate)?", path)
            if not m:
                return self._send(404, {"error": "no such path"})
            if m.group(2):
                data = jobs.certificate(m.group(1))
                return self._send(200, data) if data else self._send(404, {"error": "this job has no certificate"})
            job = jobs.get(m.group(1))
            return self._send(200, job) if job else self._send(404, {"error": "no such job"})

        def do_POST(self):                                      # noqa: N802
            if not self._gate():
                return None
            if self.path.split("?", 1)[0] != "/v1/jobs":
                return self._send(404, {"error": "no such path"})
            if (self.headers.get("Content-Type") or "").split(";")[0].strip().lower() != "application/json":
                return self._send(415, {"error": "send the job as application/json"})
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = -1
            if not 0 < length <= MAX_BODY:
                return self._send(413, {"error": f"the request must be between 1 and {MAX_BODY} bytes"})
            try:
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError
            except ValueError:
                return self._send(400, {"error": "the request is not a JSON object"})
            try:
                job, new = jobs.submit(body, self.headers.get("Idempotency-Key"))
            except Bad as bad:
                return self._send(400, {"error": str(bad)})
            except OverflowError:
                return self._send(429, {"error": f"{MAX_QUEUE} jobs are already waiting; try again when one has ended"})
            return self._send(202 if new else 200, job)

        def do_DELETE(self):                                    # noqa: N802
            if not self._gate():
                return None
            m = re.fullmatch(r"/v1/jobs/([a-f0-9]{16})", self.path.split("?", 1)[0])
            job = jobs.cancel(m.group(1)) if m else None
            return self._send(200, job) if job else self._send(404, {"error": "no such job"})

    return Handler


def serve(home: Path, student: str, base: str, port: int, seconds: float = 1800.0, token: str | None = None):
    """(the server, its token). The caller runs `server.serve_forever()`."""
    token = token or secrets.token_urlsafe(32)
    jobs = Jobs(home, student, base, seconds)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(jobs, token, port, (HERE / "ui.html").read_bytes()))
    if port == 0:                                               # the system picked one: the Host check must know it
        port = server.server_address[1]
        server.RequestHandlerClass = make_handler(jobs, token, port, (HERE / "ui.html").read_bytes())
    server.jobs = jobs
    return server, token


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--student", required=True, help="host:port of the server holding the model that writes t")
    ap.add_argument("--base", required=True, help="host:port of the server holding the base model")
    ap.add_argument("--port", type=int, default=8713)
    ap.add_argument("--home", type=Path, default=Path(os.environ.get("DAWNR_HOME") or Path.home() / ".local/share/dawnr"),
                    help="where jobs and the token are kept")
    ap.add_argument("--seconds", type=float, default=1800.0, help="the longest a job may run")
    a = ap.parse_args(argv)
    a.home.mkdir(parents=True, exist_ok=True)
    server, token = serve(a.home, a.student, a.base, a.port, a.seconds)
    token_file = a.home / "run" / "api.token"
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.touch(mode=0o600, exist_ok=True)
    os.chmod(token_file, 0o600)
    token_file.write_text(token + "\n", encoding="utf-8")
    port = server.server_address[1]
    print(f"dawnr is listening on this machine only.\n  the page:   http://127.0.0.1:{port}/#token={token}\n"
          f"  the API:    http://127.0.0.1:{port}/v1/jobs   (Authorization: Bearer <the token in {token_file}>)\n"
          "Stop it with Ctrl-C.", flush=True)
    def stop(*_):                                               # a service manager's TERM ends it as Ctrl-C does
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        for p in list(server.jobs.process.values()):
            Jobs._kill(p)
        try:
            token_file.unlink()
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
