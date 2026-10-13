#!/usr/bin/env python3
"""t/udebug_teacher.py -- a teacher answers judge problems in t, one t task plus an io module each (2026-10-12).

    ~/.venv-aws/bin/python t/udebug_teacher.py --bank t/out/udebug/bank.jsonl --exemplars problems/uva \\
        --tag deepseek-udebug-1 --judges UVa --shape int --limit 20 --samples 4 --temperature 0.7

The setting is `t/judge.py`'s: a problem is solved by a t task whose ensures states the problem
and whose body solves it, plus an io module (unverified glue: `cases(text)` reads the judge's
input into argument tuples, `render(text, calls)` prints the output), and the judge's stored
cases decide. `t/PREDICT-2026-10-08-math.md` wrote 25 of these by hand; this asks a teacher for
them at the bank's scale (`t/udebug_bank.py`), the E-step of ReST-EM (arXiv:2312.06585): K samples
per problem, kept later only by the oracle (`t/udebug_gate.py`: a proof with the twin refuted AND
every stored output reproduced). The prompt is prompt v5's reference text and few-shots (the ones
every prompted baseline is measured with, `t/spec_experiment.py`) followed by the io contract and
hand-written exemplars read from --exemplars at run time (never embedded here: the statements they
answer are the publisher's).

Transport, backoff, concurrency cap, ledger and spend cap are `t/bedrock_generate.py`'s, reused.
Bedrock's converse API has no seed: samples are not reproducible run to run, and every record says
so. Records land under --out/<judge>-<id>/s<k>/: record.json (messages, reply, usage), and when
the reply carried both fences, p<id>.t and p<id>_io.py for the gate. A problem directory with its
records already written is skipped, so a stopped run resumes.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import bedrock_generate as bg   # noqa: E402  (to_bedrock_messages, call_with_backoff, NonRetryable, prices)
import spec_experiment as se    # noqa: E402  (GRAMMAR_V5, fewshot_text)

DEFAULT_MODEL = "deepseek.v3.2"
DEFAULT_EXEMPLARS = ("p495", "p10302", "p343")

# Vertex AI's managed open models (MaaS) answer on an OpenAI-compatible route (docs.cloud.google.com,
# vertex-ai/generative-ai/docs/maas/deepseek and .../maas/qwen, read 2026-10-12): deepseek-v3.2-maas in
# `global`, deepseek-v3.1-maas in us-central1, qwen3-235b-a22b-instruct-2507-maas in global/us-south1.
# Every one is deprecated there, retiring 2026-10-21, so the record names model and date.
VERTEX_MODEL = "deepseek-ai/deepseek-v3.2-maas"
VERTEX_RETRYABLE = (408, 429, 500, 502, 503, 504)
RATE_LIMIT_MAX_ATTEMPTS = 40      # 429 is waited out: ~40 tries at up to RATE_LIMIT_MAX_DELAY s each
RATE_LIMIT_MAX_DELAY = 120.0


def force_ipv4() -> None:
    """Resolve to IPv4 only. Measured 2026-10-12 on the control laptop: `curl -6 https://aiplatform.googleapis.com/`
    times out while `-4` answers in 0.08 s; curl falls back on its own, urllib's create_connection walks every
    IPv6 address with the full timeout first (docs.python.org/3/library/socket.html#socket.create_connection)."""
    import socket
    original = socket.getaddrinfo

    def ipv4_first(*args, **kwargs):
        results = original(*args, **kwargs)
        return [r for r in results if r[0] == socket.AF_INET] or results

    socket.getaddrinfo = ipv4_first


def vertex_url(project: str, location: str) -> str:
    host = "aiplatform.googleapis.com" if location == "global" else f"{location}-aiplatform.googleapis.com"
    return f"https://{host}/v1/projects/{project}/locations/{location}/endpoints/openapi/chat/completions"


class VertexToken:
    """A bearer token from the application-default credentials file (`gcloud auth login --update-adc`),
    refreshed through oauth2.googleapis.com directly: the gcloud binary takes minutes per call here.
    GOOGLE_OAUTH_ACCESS_TOKEN, when set, is used as is."""

    def __init__(self, adc_path: str):
        self.adc_path = Path(adc_path).expanduser()
        self.token, self.expires = None, 0.0
        self.lock = threading.Lock()

    def get(self) -> str:
        import os
        import urllib.parse
        import urllib.request
        fixed = os.environ.get("GOOGLE_OAUTH_ACCESS_TOKEN")
        if fixed:
            return fixed
        with self.lock:
            if self.token and time.time() < self.expires - 120:
                return self.token
            adc = json.loads(self.adc_path.read_text(encoding="utf-8"))
            body = urllib.parse.urlencode({"client_id": adc["client_id"], "client_secret": adc["client_secret"],
                                           "refresh_token": adc["refresh_token"],
                                           "grant_type": "refresh_token"}).encode()
            with urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=body),
                                        timeout=30) as r:
                j = json.load(r)
            self.token, self.expires = j["access_token"], time.time() + float(j.get("expires_in", 3600))
            return self.token


BEDROCK_CLI_TRANSIENT = ("ThrottlingException", "ServiceUnavailableException", "ModelNotReadyException",
                         "InternalServerException", "timed out", "timeout", "Timeout", "Connection",
                         "EndpointConnectionError", "ReadTimeoutError", "Rate exceeded", "(429)",
                         "TooManyRequests", "CreateOAuth2Token", "being verified")
_AWS_ENV: dict = {"env": None, "at": 0.0}
_AWS_ENV_LOCK = threading.Lock()


def aws_static_env() -> dict | None:
    """Static session credentials for the CLI subprocesses. A signed-in CLI (`aws login`) refreshes an OAuth2 token
    on every invocation, and a hundred concurrent invocations get 429 `CreateOAuth2Token ... Rate exceeded`; one
    `aws configure export-credentials --format env` every 30 minutes hands the lane fixed keys instead."""
    import os
    import subprocess
    with _AWS_ENV_LOCK:
        if _AWS_ENV["env"] is not None and time.time() - _AWS_ENV["at"] < 1800:
            return _AWS_ENV["env"]
        try:
            p = subprocess.run([aws_cli(), "configure", "export-credentials", "--format", "env"],
                               capture_output=True, text=True, timeout=120)
        except Exception:  # noqa: BLE001 -- the ambient environment is the fallback
            return _AWS_ENV["env"]
        if p.returncode != 0:
            return _AWS_ENV["env"]
        env = dict(os.environ)
        for line in p.stdout.splitlines():
            line = line.strip()
            if line.startswith("export ") and "=" in line:
                k, v = line[len("export "):].split("=", 1)
                env[k] = v.strip().strip('"')
        _AWS_ENV["env"], _AWS_ENV["at"] = env, time.time()
        return env
BEDROCK_CLI_READ_TIMEOUT_S = 900     # the CLI's default read timeout is 60 s; a long reply takes minutes
BEDROCK_CLI_MAX_CONCURRENCY = 16
AWS_CLI_FALLBACKS = ("/home/t/.local/bin/aws", "/usr/local/bin/aws", "/usr/bin/aws")


def aws_cli() -> str:
    """The AWS CLI binary: PATH first, then the places it is installed here (a user service's PATH lacks ~/.local/bin)."""
    import os
    import shutil
    found = shutil.which("aws")
    if found:
        return found
    for cand in AWS_CLI_FALLBACKS:
        if os.path.isfile(cand):
            return cand
    raise bg.NonRetryable("the aws CLI is not installed or not on PATH")


def bedrock_cli_call(region: str, model: str, messages: list[dict], max_tokens: int, temperature: float,
                     max_attempts: int = 8) -> tuple[str, int, int, str | None]:
    """One `aws bedrock-runtime converse` (docs.aws.amazon.com/cli/latest/reference/bedrock-runtime/converse.html:
    --cli-input-json carries modelId, system, messages and inferenceConfig; the reply is output.message.content[].text
    with usage.inputTokens/outputTokens and stopReason). The laptop has no boto3; the CLI is signed in. Throttling
    and service errors are retried on vertex_call's schedule; a validation error or anything else is NonRetryable."""
    import os
    import random
    import subprocess
    import tempfile
    system = [{"text": m["content"]} for m in messages if m["role"] == "system"]
    conv = [{"role": m["role"], "content": [{"text": m["content"]}]} for m in messages if m["role"] != "system"]
    req = {"modelId": model, "messages": conv, "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature}}
    if system:
        req["system"] = system
    delay = 1.0
    attempt = 0
    while True:
        attempt += 1
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(req, f)
            path = f.name
        try:
            p = subprocess.run([aws_cli(), "bedrock-runtime", "converse", "--region", region, "--cli-input-json",
                                f"file://{path}", "--output", "json", "--cli-read-timeout",
                                str(BEDROCK_CLI_READ_TIMEOUT_S), "--cli-connect-timeout", "60"],
                               capture_output=True, text=True, timeout=BEDROCK_CLI_READ_TIMEOUT_S + 60,
                               env=aws_static_env())
            err = p.stderr.strip()
        except subprocess.TimeoutExpired:
            p, err = None, "timed out"
        finally:
            os.unlink(path)
        if p is not None and p.returncode == 0:
            d = json.loads(p.stdout)
            reply = "".join(c.get("text", "") for c in d.get("output", {}).get("message", {}).get("content", []))
            u = d.get("usage", {})
            return reply, u.get("inputTokens", 0) or 0, u.get("outputTokens", 0) or 0, d.get("stopReason")
        if not any(k in err for k in BEDROCK_CLI_TRANSIENT):
            raise bg.NonRetryable(f"bedrock cli: {err[:400]}")
        if attempt >= (RATE_LIMIT_MAX_ATTEMPTS if "Throttling" in err else max_attempts):
            raise bg.NonRetryable(f"bedrock cli after {attempt} attempts: {err[:300]}")
        sleep_s = min(delay, RATE_LIMIT_MAX_DELAY) * (1 + random.uniform(-0.2, 0.2))
        print(f"  transient error, retry {attempt} in {sleep_s:.1f}s", file=sys.stderr, flush=True)
        time.sleep(sleep_s)
        delay *= 2


OPENAI_URL = "https://api.openai.com/v1/chat/completions"


def openai_key(path: str) -> str:
    """The API key from --openai-key-file (or OPENAI_API_KEY); read, never printed."""
    import os
    env = os.environ.get("OPENAI_API_KEY")
    if env:
        return env.strip()
    p = Path(path).expanduser()
    if not p.is_file():
        raise SystemExit(f"udebug_teacher: no OpenAI key at {p} and OPENAI_API_KEY is unset")
    return p.read_text(encoding="utf-8").strip()


OPENAI_MAX_CONCURRENCY = 48


def openai_call(key: str, model: str, messages: list[dict], max_tokens: int, temperature: float,
                reasoning_effort: str = "", max_attempts: int = 8,
                service_tier: str = "") -> tuple[str, int, int, str | None]:
    """POST /chat/completions (github.com/openai/openai-openapi: Bearer auth; model, messages; the reply in
    choices[0].message.content with finish_reason and usage.prompt_tokens/completion_tokens). Newer models take
    max_completion_tokens and refuse a non-default temperature: a 400 naming either field is answered by resending
    without it. 429 and 5xx wait on vertex_call's schedule; any other error stops the lane."""
    import random
    import urllib.error
    import urllib.request
    body = {"model": model, "messages": messages, "max_completion_tokens": max_tokens, "stream": False}
    if abs(temperature - 1.0) > 1e-9:
        body["temperature"] = temperature
    if reasoning_effort:
        body["reasoning_effort"] = reasoning_effort
    if service_tier:
        body["service_tier"] = service_tier          # "priority": faster processing at a higher price
    delay = 1.0
    attempt = 0
    while True:
        attempt += 1
        req = urllib.request.Request(OPENAI_URL, data=json.dumps(body).encode(),
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=900) as r:
                j = json.load(r)
            choice = (j.get("choices") or [{}])[0]
            text = (choice.get("message") or {}).get("content") or ""
            usage = j.get("usage") or {}
            return text, usage.get("prompt_tokens", 0) or 0, usage.get("completion_tokens", 0) or 0, choice.get("finish_reason")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:600]
            if e.code == 400 and "max_completion_tokens" in detail and "max_completion_tokens" in body:
                body["max_tokens"] = body.pop("max_completion_tokens")
                continue
            if e.code == 400 and "temperature" in detail and "temperature" in body:
                body.pop("temperature")
                continue
            if e.code == 400 and "reasoning_effort" in detail and "reasoning_effort" in body:
                body.pop("reasoning_effort")
                continue
            if e.code == 400 and "service_tier" in detail and "service_tier" in body:
                body.pop("service_tier")
                continue
            if e.code == 429:
                if attempt >= RATE_LIMIT_MAX_ATTEMPTS:
                    raise bg.NonRetryable(f"HTTP 429 after {attempt} attempts: {detail}") from e
            elif e.code not in VERTEX_RETRYABLE or attempt >= max_attempts:
                raise bg.NonRetryable(f"HTTP {e.code}: {detail}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt >= max_attempts:
                raise bg.NonRetryable(f"connection error, exhausted {max_attempts} attempts: {e}") from e
        sleep_s = min(delay, RATE_LIMIT_MAX_DELAY) * (1 + random.uniform(-0.2, 0.2))
        print(f"  transient error, retry {attempt} in {sleep_s:.1f}s", file=sys.stderr, flush=True)
        time.sleep(sleep_s)
        delay *= 2


def vertex_call(url: str, token: VertexToken, model: str, messages: list[dict], max_tokens: int,
                temperature: float, max_attempts: int = 8) -> tuple[str, int, int, str | None]:
    """One chat completion; bedrock_generate.call_with_backoff's schedule (1, 2, 4, 8, 16 s, +/-20%) extended by
    two steps (32, 64 s) because the global endpoint's 429s outlasted the five-step schedule on 2026-10-12 when
    three runs overlapped; retried only on the transient statuses; any other 4xx is a NonRetryable with the body."""
    import random
    import urllib.error
    import urllib.request
    body = json.dumps({"model": model, "messages": messages, "max_tokens": max_tokens,
                       "temperature": temperature, "stream": False}).encode()
    delay = 1.0
    attempt = 0
    while True:
        attempt += 1
        try:
            req = urllib.request.Request(url, data=body, headers={"Authorization": f"Bearer {token.get()}",
                                                                  "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=600) as r:
                j = json.load(r)
            choice = (j.get("choices") or [{}])[0]
            text = (choice.get("message") or {}).get("content") or ""
            usage = j.get("usage") or {}
            return text, usage.get("prompt_tokens", 0) or 0, usage.get("completion_tokens", 0) or 0, choice.get("finish_reason")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:600]
            # 429 "Resource exhausted": "if the number of your requests exceeds the capacity allocated to
            # process requests" (docs.cloud.google.com/vertex-ai/generative-ai/docs/error-code-429, read
            # 2026-10-12: "implement a retry strategy by using truncated exponential backoff", smooth traffic,
            # ramp up gradually), so it is waited out, never fatal: three lanes aborted on it at 17:09Z after
            # the eight-step schedule, 60 calls in, because they were spiking the same capacity together.
            if e.code == 429:
                if attempt >= RATE_LIMIT_MAX_ATTEMPTS:
                    raise bg.NonRetryable(f"HTTP 429 after {attempt} attempts: {detail}") from e
            elif e.code not in VERTEX_RETRYABLE or attempt >= max_attempts:
                raise bg.NonRetryable(f"HTTP {e.code}: {detail}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt >= max_attempts:
                raise bg.NonRetryable(f"connection error, exhausted {max_attempts} attempts: {e}") from e
        sleep_s = min(delay, RATE_LIMIT_MAX_DELAY) * (1 + random.uniform(-0.2, 0.2))
        print(f"  transient error, retry {attempt} in {sleep_s:.1f}s", file=sys.stderr, flush=True)
        time.sleep(sleep_s)
        delay *= 2

IO_CONTRACT = """
Solving a judge problem in t has two parts, and you write both.

(1) The t task, named p<ID>: its `requires`/`ensures` state the problem as the statement defines it
    (or a standard model of it, such as the recurrence the statement implies), and its body solves
    it so the provers can verify it. The task sees one case at a time: its parameters are the
    numbers (or sequences of ints) of one case, its result is one int, bool or seq.

(2) The io module, plain Python, which is NOT verified and does the reading and printing:
      cases(text) -> list of argument tuples, one per call of the task, in input order;
      render(text, calls) -> the complete output text, given the input text and
                             [(args, result), ...] with result a Python int, bool or list.
    Follow the statement's output format exactly (wording, spacing, blank lines, trailing newline).

Reply with exactly two fenced blocks and nothing else: first ```t with the task, then ```python
with the io module.
""".strip()

DAFNY_CONTRACT = """
Solving a judge problem in Dafny has two parts, and you write both.

(1) A Dafny program with ONE method named p<ID>: its `requires`/`ensures` state the problem as the
    statement defines it (or a standard model of it, such as the recurrence the statement implies) and
    its body solves it so Dafny verifies it, with the `function`s (each with `decreases`) and `lemma`s it
    needs declared before the method. Stay in this subset, which is what the lifter to the verified
    language accepts: types int, bool and seq<int> only (no nat, arrays, classes, strings, tuples, sets,
    maps or generics); exactly one return value; functions are single expressions over those types; no
    ghost state, no `modifies`; proof steps belong in lemmas; quantifiers only over int ranges written
    `0 <= i < n`. The method sees one case at a time: its parameters are the numbers (or sequences of
    ints) of one case.
    Dafny, not C: there is no `? :` (write `if c then a else b`); inside a function `if` is that expression
    form, never a statement; `abs`, `max`, `min`, `pow` do not exist unless you define them as functions;
    every `while` carries `invariant`s and a `decreases`; `//` comments are fine, string literals are not.

(2) The io module, plain Python, which is NOT verified and does the reading and printing:
      cases(text) -> list of argument tuples, one per call of the method, in input order;
      render(text, calls) -> the complete output text, given the input text and
                             [(args, result), ...] with result a Python int, bool or list.
    Follow the statement's output format exactly (wording, spacing, blank lines, trailing newline).

Reply with exactly two fenced blocks and nothing else: first ```dafny with the program, then ```python
with the io module.
""".strip()

PYTHON_CONTRACT = """
Solve the judge problem with ONE complete Python 3 program that reads the whole input from standard input
and writes the whole output to standard output, in exactly the format the statement specifies (wording,
spacing, blank lines, trailing newline). Standard library only; no input prompts; read with
sys.stdin.read() or sys.stdin.buffer; handle every case in the input, in order. Integers may be large.
Reply with exactly one fenced block: ```python with the program, and nothing else.
""".strip()

TARGETS = ("t", "dafny", "python")

PARSER_RULES_V2 = """
Rules the t parser and its well-formedness gate enforce (each refused a reply in the first run):
- `t` is a reserved word: never name a variable, parameter or function `t`.
- No `let ... in`, no comments, no string or character literals anywhere; only int, bool and seq.
- A spec fun is ONE expression: `spec fun f(a: int): int`, then `  decreases a`, then `= EXPR`.
  No `{ }` body, no `var`, no `;`, no `requires` or `ensures` on a spec fun; recursion through
  `if C then A else B` inside the expression. `if C { } else { }` is the statement form, body only.
- Every function a task, spec fun or lemma calls must be declared above it as a spec fun with a
  `decreases` line and its `= EXPR` body on the very next line. Nothing is imported and there is no
  library: write pow10, digit sums, popcounts and the like as spec funs of your own.
- A spec fun's body has its declared result type; `+ - *` take all ints (no mixing with seq or bool).
- Keep it small: one task, the spec funs it needs, at most one lemma, and loop invariants that prove
  the ensures at exit.
""".strip()

PROMPT_VERSIONS = ("v1", "v2")

HINT_MAX = 60_000          # characters of an accepted Python program quoted whole as a hint
FENCE = re.compile(r"```(\w*)[ \t]*\n(.*?)^```[ \t]*$", re.S | re.M)   # the closing fence is a line of its own


def dafny_of(t_path: Path) -> str:
    """The engine's own Dafny lowering of a hand-written t task (`cli.py lower --kernel dafny`), with the
    method's name in the lower case the lifter is asked for; the exemplar a Dafny-writing teacher sees."""
    import subprocess
    text = subprocess.run([sys.executable, str(HERE / "cli.py"), "lower", "--kernel", "dafny", str(t_path)],
                          capture_output=True, text=True, check=True).stdout.strip()
    return re.sub(r"\bmethod P(\d+)\b", r"method p\1", text)


def exemplar_text(directory: Path, names: tuple[str, ...], target: str = "t") -> str:
    parts = []
    if target == "python":
        return ""                                   # the model knows stdin-to-stdout Python; nothing to show
    for n in names:
        src = dafny_of(directory / f"{n}.t") if target == "dafny" else \
            (directory / f"{n}.t").read_text(encoding="utf-8").strip()
        io_src = (directory / f"{n}_io.py").read_text(encoding="utf-8").strip()
        parts.append(f"Example {n}:\n```{target}\n{src}\n```\n```python\n{io_src}\n```")
    return "\n\n".join(parts)


def system_text(exemplars: str, version: str = "v1", target: str = "t") -> str:
    if target == "python":
        return PYTHON_CONTRACT
    if target == "dafny":
        return DAFNY_CONTRACT + "\n\nExamples of judge problems solved this way:\n\n" + exemplars
    rules = ("\n\n" + PARSER_RULES_V2) if version == "v2" else ""
    return (se.GRAMMAR_V5 + "\nExamples of complete t tasks:\n\n" + se.fewshot_text("v5")
            + rules + "\n\n" + IO_CONTRACT + "\n\nExamples of judge problems solved this way:\n\n" + exemplars)


FAIL_RANK = {"fail": 0, "error": 1, "timeout": 2}


def prior_attempts(rec: dict, dirs: list[Path]) -> list[dict]:
    """Every graded sample of this problem under the given lane directories, with its program text."""
    key = f"{rec['judge']}-{rec['id']}"
    out = []
    for d in dirs:
        for r in sorted((d / key).glob("s*/result.json")):
            try:
                o = json.loads(r.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            prog = r.parent / f"p{rec['id']}.py"
            o["program"] = prog.read_text(encoding="utf-8") if prog.is_file() else None
            o["sample_dir"] = str(r.parent)
            out.append(o)
    return out


def best_failed(attempts: list[dict]) -> dict | None:
    """The most informative refused attempt: a wrong answer over a crash over a timeout, then the most cases passed."""
    cands = [o for o in attempts if o.get("program") and (o.get("judge") or {}).get("status") in FAIL_RANK]
    if not cands:
        return None
    return min(cands, key=lambda o: (FAIL_RANK[o["judge"]["status"]], -(o["judge"].get("passed") or 0)))


def repair_text(rec: dict, prior: dict, corpus: Path) -> str:
    """The judge's refusal handed back to the model with the previous program (Chen et al., Teaching Large Language
    Models to Self-Debug, arXiv:2304.05128: execution feedback on a failed attempt raises accuracy more than fresh
    samples do). The failing case's input head and the expected output around the first difference are quoted
    from the stored files, so the model sees the format it missed rather than a description of it."""
    j = prior["judge"]
    case = j.get("case")
    tests = corpus / rec["tests_dir"]
    lines = ["A previous program (below) was run on the judge's stored cases and refused."]
    if j["status"] == "fail":
        lines.append(f"Case {case}: the output differs at {j.get('first_difference')} (compared with trailing spaces "
                     f"and trailing blank lines ignored); {j.get('passed') or 0} of {j.get('total')} stored cases "
                     f"matched before this one.")
    elif j["status"] == "error":
        lines.append(f"Case {case}: the program crashed: {j.get('first_difference')}")
        fd = j.get("first_difference") or ""
        if "RecursionError" in fd:
            lines.append("A RecursionError means the recursion is deeper than Python allows: use an explicit stack "
                         "or an iterative formulation, or raise the limit with sys.setrecursionlimit and run the "
                         "solver inside a threading.Thread with threading.stack_size(1 << 27).")
        elif "memory cap" in fd or "Killed" in fd:
            lines.append("The program was killed at a 3 GB memory cap: the stored inputs are large, so avoid "
                         "materializing per-case structures of the input's full size more than once.")
        elif "SyntaxError" in fd:
            lines.append("A SyntaxError usually means the previous reply was cut off before the program ended: "
                         "write the whole program compactly and close the fence.")
    else:
        lines.append(f"Case {case}: the program did not finish within {j.get('per_case_s') or 'the allowed'} seconds. "
                     "The stored inputs can be large: read all of stdin at once, keep the algorithm near-linear or "
                     "n log n, and build the output in one join.")
    if case:
        inp = tests / case
        if inp.is_file():
            text = inp.read_text(encoding="utf-8", errors="replace")
            head = text.splitlines()
            lines.append(f"The first lines of that case's input ({len(head)} lines, {inp.stat().st_size} bytes):")
            lines.append("\n".join(head[:30])[:1500])
            m = re.match(r"line (\d+):", j.get("first_difference") or "") if j["status"] == "fail" else None
            outp = tests / case.replace(".in.txt", ".out.txt")
            if m and outp.is_file():
                want = outp.read_text(encoding="utf-8", errors="replace").splitlines()
                k = int(m.group(1))
                lo, hi = max(0, k - 4), min(len(want), k + 3)
                lines.append(f"The expected output, lines {lo + 1} to {hi} of {len(want)}:")
                lines.append("\n".join(want[lo:hi])[:1200])
    lines.append("The previous program:")
    lines.append("```python\n" + prior["program"].rstrip() + "\n```")
    lines.append("Find the cause before writing: re-read the statement's input and output format (blank lines between "
                 "cases, trailing spaces, the end-of-input rule, exact wording and rounding), the edge cases (empty "
                 "input, one element, the largest values, negative numbers, duplicates) and the running time. Keep "
                 "that reasoning under 300 words, then write the corrected complete program: one ```python fence, "
                 "reading stdin and writing stdout. The fence must be complete; nothing after it.")
    return "\n\n".join(lines)


def speed_text(rec: dict, entry: dict, program: str) -> str:
    """A confirmed program that is too slow for a judge, handed back for a faster one. The export's evidence gives
    the slowest stored case; CPython at an online judge gets one to a few seconds."""
    return "\n\n".join([
        f"A previous program (below) is correct: it reproduces every one of the judge's {entry.get('cases')} stored "
        f"cases. But its slowest case takes {entry.get('max_case_s')} s, and an online judge allows CPython about one "
        f"to three seconds, so it would be refused for time.",
        "The previous program:",
        "```python\n" + program.rstrip() + "\n```",
        "Write a faster program with the same output. Look first for a better algorithm (precomputation across "
        "cases, a sieve or table built once, a closed form, memoization, binary search, prefix sums, a better data "
        "structure); then at Python costs: read all input at once with sys.stdin.buffer.read().split(), build the "
        "output in a list and write it once, avoid per-element function calls and deep recursion, use integers over "
        "floats and local variables inside functions. Keep the reasoning under 300 words, then one complete "
        "```python fence reading stdin and writing stdout; nothing after it."])


def user_text(rec: dict, target: str = "t", repair: str | None = None, hint: str | None = None) -> str:
    title = rec.get("title") or ""
    what = (f"the Dafny method `p{rec['id']}` and its io module" if target == "dafny"
            else "the Python program" if target == "python" else f"the t task `p{rec['id']}` and its io module")
    return (f"Judge problem {rec['judge']} {rec['id']}: {title}\n\n{rec['statement'].strip()}\n\n"
            f"A stored case of the judge -- input:\n{rec['sample_in']}\nexpected output:\n{rec['sample_out']}\n\n"
            f"Write {what}."
            + (f"\n\nA Python program that reproduces every stored case of this problem (it shows the function the judge "
               f"wants; the t task must compute the same function, and its contract must say what that function is, "
               f"not restate the code):\n```python\n{hint.rstrip()}\n```" if hint else "")
            + (f"\n\n{repair}" if repair else ""))


def extract(reply: str, target: str = "t") -> tuple[str | None, str | None]:
    """(program, io module); for the python target the program is the first python fence and the io module
    is the program itself, so the two-fence tests downstream read the same way."""
    src = io_src = None
    for lang, body in FENCE.findall(reply):
        if target == "python" and lang in ("python", "py"):
            return body, body
        if lang == target and src is None:
            src = body
        elif lang in ("python", "py") and io_src is None:
            io_src = body
    return src, io_src


def select(bank: Path, judges: set[str], shape: str, split: str, ids: set[str], limit: int,
           max_in_bytes: int) -> list[dict]:
    out = []
    with bank.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            key = f"{r['judge']}/{r['id']}"
            if ids:
                if key not in ids:
                    continue
            else:
                if judges and r["judge"] not in judges:
                    continue
                if shape != "any" and r["io_shape"] != shape:
                    continue
                if split != "any" and r["split"] != split:
                    continue
                if r["hand_solved"]:
                    continue                      # the measured set is never prompted
                if max_in_bytes and r["in_bytes"] > max_in_bytes:
                    continue
            if not r.get("statement") or r["n_scored"] == 0:
                continue
            out.append(r)
    return out[:limit] if limit else out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bank", required=True)
    ap.add_argument("--exemplars", required=True, help="directory of hand-written p<id>.t and p<id>_io.py")
    ap.add_argument("--exemplar-names", default=",".join(DEFAULT_EXEMPLARS))
    ap.add_argument("--tag", required=True)
    ap.add_argument("--prompt-version", choices=PROMPT_VERSIONS, default="v1",
                    help="v2 adds the parser rules measured on the v1 pilot's refusals")
    ap.add_argument("--target", choices=TARGETS, default="t",
                    help="dafny: the teacher writes a Dafny method the gate lifts to t (t/lifter.py)")
    ap.add_argument("--out", default="", help="default t/out/udebug/teacher-<tag>")
    ap.add_argument("--provider", choices=("bedrock", "vertex", "bedrock-cli", "openai"), default="bedrock")
    ap.add_argument("--openai-key-file", default="~/.config/openai/api_key")
    ap.add_argument("--reasoning-effort", default="", help="openai: low, medium or high (omitted by default)")
    ap.add_argument("--service-tier", default="", help="openai: priority for faster processing (costs more)")
    ap.add_argument("--model", default="", help=f"default {DEFAULT_MODEL} on Bedrock, {VERTEX_MODEL} on Vertex")
    ap.add_argument("--region", default=bg.DEFAULT_REGION, help="Bedrock region")
    ap.add_argument("--project", default="", help="Vertex: the Google Cloud project id")
    ap.add_argument("--location", default="global", help="Vertex: global, us-central1, ...")
    ap.add_argument("--adc", default="~/.config/gcloud/application_default_credentials.json",
                    help="Vertex: application-default credentials file for the bearer token")
    ap.add_argument("--judges", default="UVa")
    ap.add_argument("--shape", choices=("int", "text", "any"), default="int")
    ap.add_argument("--split", choices=("train", "heldout", "any"), default="train")
    ap.add_argument("--ids", default="", help="comma-separated judge/id keys; overrides the filters")
    ap.add_argument("--repair-from", default="", help="comma-separated lane directories: prompt only the problems "
                    "refused there (and accepted nowhere among them), with the refusal and the program quoted")
    ap.add_argument("--corpus", default="t/out/udebug-bulk-20261011", help="where the stored cases are (repair)")
    ap.add_argument("--slow-index", default="", help="the export's INDEX.jsonl: prompt the solved problems whose "
                    "slowest stored case exceeds --slow-above seconds for a faster program (quoting the solution)")
    ap.add_argument("--slow-above", type=float, default=2.0)
    ap.add_argument("--python-hint-from", default="", help="a solutions bundle (<judge>/<id>.py): the accepted Python "
                    "program is quoted in the prompt as the function to specify and prove (t and dafny targets)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-in-bytes", type=int, default=0, help="skip problems whose stored inputs exceed this")
    ap.add_argument("--samples", type=int, default=1)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--concurrency", type=int, default=bg.HARD_MAX_CONCURRENCY)
    ap.add_argument("--price-in-per-mtok", type=float, default=bg.PRICE_IN_PER_MTOK,
                    help="ledger estimate; the default is bedrock_generate's Sonnet list price, an overestimate "
                         "for DeepSeek, so the cap trips early rather than late")
    ap.add_argument("--price-out-per-mtok", type=float, default=bg.PRICE_OUT_PER_MTOK)
    ap.add_argument("--spend-cap-usd", type=float, default=5.0)
    ap.add_argument("--dry-run", action="store_true", help="write the prompts, call nothing")
    a = ap.parse_args(argv)

    out = Path(a.out) if a.out else HERE / "out" / "udebug" / f"teacher-{a.tag}"
    out.mkdir(parents=True, exist_ok=True)
    exemplars = exemplar_text(Path(a.exemplars), tuple(n for n in a.exemplar_names.split(",") if n), a.target)
    system = system_text(exemplars, a.prompt_version, a.target)
    suffix = {"dafny": ".dfy", "python": ".py", "t": ".t"}[a.target]
    ids = {k.strip() for k in a.ids.split(",") if k.strip()}
    judges = {j.strip() for j in a.judges.split(",") if j.strip()}
    problems = select(Path(a.bank), judges, a.shape, a.split, ids, a.limit, a.max_in_bytes)
    print(f"{len(problems)} problems selected; system prompt {len(system)} chars", flush=True)
    if a.python_hint_from:
        hints = 0
        for rec in problems:
            hp = Path(a.python_hint_from) / rec["judge"] / f"{rec['id']}.py"
            if hp.is_file():
                text = hp.read_text(encoding="utf-8")
                if len(text) > HINT_MAX:
                    print(f"  {hp}: {len(text)} characters, over the {HINT_MAX} hint cap; no hint for this problem "
                          "(a truncated program is not the accepted one)", file=sys.stderr, flush=True)
                    continue
                rec["_hint"] = text
                hints += 1
        print(f"{hints} of {len(problems)} problems carry an accepted Python program as a hint", flush=True)
    repair_dirs = [Path(p) for p in a.repair_from.split(",") if p]
    slow = {}
    if a.slow_index:
        with open(a.slow_index, encoding="utf-8") as f:
            for line in f:
                e = json.loads(line)
                if e.get("status") == "solved" and (e.get("max_case_s") or 0) > a.slow_above:
                    slow[(e["judge"], e["id"])] = e
    if repair_dirs or slow or a.slow_index:     # a slow index that qualifies nothing selects nothing
        kept = []
        for rec in problems:
            e = slow.get((rec["judge"], rec["id"]))
            if e is not None:
                prog = Path(e["sample_dir"]) / f"p{rec['id']}.py"
                if prog.is_file():
                    rec["_repair"] = speed_text(rec, e, prog.read_text(encoding="utf-8"))
                    rec["_repair_from"] = e["sample_dir"]
                    kept.append(rec)
                continue
            if not repair_dirs:
                continue
            attempts = prior_attempts(rec, repair_dirs)
            if any(o.get("accepted") for o in attempts):
                continue                                  # solved in one of those lanes already
            prior = best_failed(attempts)
            if prior is None:
                continue                                  # nothing to repair: never tried, or no program to quote
            rec["_repair"] = repair_text(rec, prior, Path(a.corpus))
            rec["_repair_from"] = prior["sample_dir"]
            kept.append(rec)
        problems = kept
        print(f"{len(problems)} problems carry a refused attempt to repair or a slow solution to speed up", flush=True)

    jobs = []
    for rec in problems:
        for k in range(1, a.samples + 1):
            d = out / f"{rec['judge']}-{rec['id']}" / f"s{k}"
            if (d / "record.json").is_file():
                try:
                    done = json.loads((d / "record.json").read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    done = None
                if isinstance(done, dict) and "reply" in done:
                    continue
                print(f"  {d}: record.json is truncated or malformed (an interrupted write); the sample is redone",
                      file=sys.stderr, flush=True)
            jobs.append((rec, k, d))
    print(f"{len(jobs)} calls to make ({a.samples} per problem, resumed ones skipped)", flush=True)
    if a.dry_run:
        for rec, k, d in jobs[:1]:
            d.mkdir(parents=True, exist_ok=True)
            (d / "prompt.json").write_text(json.dumps(
                [{"role": "system", "content": system},
                 {"role": "user", "content": user_text(rec, a.target, rec.get("_repair"), rec.get("_hint"))}],
                indent=1))
            print(f"dry run: prompt written to {d / 'prompt.json'}")
        return 0

    if a.provider == "bedrock":
        import boto3
        client = boto3.client("bedrock-runtime", region_name=a.region)
        model, endpoint = a.model or DEFAULT_MODEL, f"bedrock:{a.region}"

        def call(messages: list[dict]) -> tuple[str, int, int, str | None]:
            system_blocks, conv = bg.to_bedrock_messages(messages)
            resp = bg.call_with_backoff(client, model, system_blocks, conv, a.max_tokens, a.temperature)
            msg = resp.get("output", {}).get("message", {})
            reply = "".join(b.get("text", "") for b in msg.get("content", []) if "text" in b)
            usage = resp.get("usage", {})
            return reply, usage.get("inputTokens", 0) or 0, usage.get("outputTokens", 0) or 0, resp.get("stopReason")
    elif a.provider == "openai":
        if not a.model:
            raise SystemExit("udebug_teacher: --model is required with --provider openai")
        model, endpoint = a.model, OPENAI_URL
        key = openai_key(a.openai_key_file)

        def call(messages: list[dict]) -> tuple[str, int, int, str | None]:
            return openai_call(key, model, messages, a.max_tokens, a.temperature, a.reasoning_effort,
                               service_tier=a.service_tier)
    elif a.provider == "bedrock-cli":
        model, endpoint = a.model or DEFAULT_MODEL, f"bedrock-cli:{a.region}"

        def call(messages: list[dict]) -> tuple[str, int, int, str | None]:
            return bedrock_cli_call(a.region, model, messages, a.max_tokens, a.temperature)
    else:
        if not a.project:
            raise SystemExit("udebug_teacher: --project is required with --provider vertex")
        model, endpoint = a.model or VERTEX_MODEL, vertex_url(a.project, a.location)
        token = VertexToken(a.adc)
        force_ipv4()

        def call(messages: list[dict]) -> tuple[str, int, int, str | None]:
            return vertex_call(endpoint, token, model, messages, a.max_tokens, a.temperature)
    lock = threading.Lock()
    ledger = {"in": 0, "out": 0, "calls": 0, "usd": 0.0, "stop": False, "with_fences": 0}
    ledger_path = out / "ledger.jsonl"

    def spend(in_tok: int, out_tok: int) -> float:
        return in_tok / 1e6 * a.price_in_per_mtok + out_tok / 1e6 * a.price_out_per_mtok

    def one(rec: dict, k: int, d: Path):
        if ledger["stop"]:
            return "stopped"
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": user_text(rec, a.target, rec.get("_repair"), rec.get("_hint"))}]
        t0 = time.monotonic()
        try:
            reply, in_tok, out_tok, stop_reason = call(messages)
        except bg.NonRetryable as e:
            with lock:
                ledger["stop"] = True
            print(f"ABORT {rec['judge']}/{rec['id']} s{k}: {e}", file=sys.stderr, flush=True)
            return "aborted"
        wall = time.monotonic() - t0
        t_src, io_src = extract(reply, a.target)
        d.mkdir(parents=True, exist_ok=True)
        if t_src is not None and io_src is not None:
            (d / f"p{rec['id']}{suffix}").write_text(t_src.rstrip() + "\n", encoding="utf-8")
            if a.target != "python":
                (d / f"p{rec['id']}_io.py").write_text(io_src.rstrip() + "\n", encoding="utf-8")
        record = {"judge": rec["judge"], "id": rec["id"], "title": rec.get("title"), "tests_dir": rec["tests_dir"],
                  "model": model, "provider": a.provider, "endpoint": endpoint, "tag": a.tag,
                  "prompt_version": a.prompt_version, "target": a.target, "repair_from": rec.get("_repair_from"),
                  "sample_index": k, "num_samples": a.samples,
                  "options": {"temperature": a.temperature, "max_tokens": a.max_tokens,
                              "note": "no seed on either provider; this reply is not reproducible"},
                  "messages": messages, "reply": reply, "prompt_tokens": in_tok, "reply_tokens": out_tok,
                  "wall_s": round(wall, 3), "done_reason": stop_reason,
                  "fences": {a.target: t_src is not None, "python": io_src is not None}}
        (d / "record.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        with lock:
            ledger["in"] += in_tok
            ledger["out"] += out_tok
            ledger["calls"] += 1
            ledger["with_fences"] += t_src is not None and io_src is not None
            ledger["usd"] = spend(ledger["in"], ledger["out"])
            with ledger_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"key": f"{rec['judge']}/{rec['id']}", "k": k, "in": in_tok, "out": out_tok,
                                    "usd_running": round(ledger["usd"], 4), "wall_s": round(wall, 2)}) + "\n")
            if ledger["usd"] >= a.spend_cap_usd:
                ledger["stop"] = True
                print(f"SPEND CAP: estimate ${ledger['usd']:.3f} >= ${a.spend_cap_usd}; no further calls",
                      file=sys.stderr, flush=True)
            print(f"{ledger['calls']}/{len(jobs)} {rec['judge']}/{rec['id']} s{k}: {in_tok}+{out_tok} tok, "
                  f"{wall:.1f}s, fences t={t_src is not None} py={io_src is not None}, ${ledger['usd']:.3f}",
                  flush=True)
        return "ok"

    cap = (OPENAI_MAX_CONCURRENCY if a.provider == "openai"
           else BEDROCK_CLI_MAX_CONCURRENCY if a.provider == "bedrock-cli" else bg.HARD_MAX_CONCURRENCY)
    workers = max(1, min(a.concurrency, cap))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(lambda j: one(*j), jobs))
    summary = {"tag": a.tag, "model": model, "provider": a.provider, "endpoint": endpoint,
               "problems": len(problems), "calls_made": ledger["calls"],
               "replies_with_both_fences": ledger["with_fences"], "input_tokens": ledger["in"],
               "output_tokens": ledger["out"], "usd_estimate": round(ledger["usd"], 4),
               "stopped_early": ledger["stop"]}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=1))
    return 0 if not ledger["stop"] else 1


if __name__ == "__main__":
    sys.exit(main())
