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


def vertex_call(url: str, token: VertexToken, model: str, messages: list[dict], max_tokens: int,
                temperature: float, max_attempts: int = 6) -> tuple[str, int, int, str | None]:
    """One chat completion; the same backoff schedule as bedrock_generate.call_with_backoff (1, 2, 4, 8, 16 s,
    +/-20%), retried only on the transient statuses; any other 4xx is a NonRetryable with the body."""
    import random
    import urllib.error
    import urllib.request
    body = json.dumps({"model": model, "messages": messages, "max_tokens": max_tokens,
                       "temperature": temperature, "stream": False}).encode()
    delay = 1.0
    for attempt in range(1, max_attempts + 1):
        req = urllib.request.Request(url, data=body, headers={"Authorization": f"Bearer {token.get()}",
                                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                j = json.load(r)
            choice = (j.get("choices") or [{}])[0]
            text = (choice.get("message") or {}).get("content") or ""
            usage = j.get("usage") or {}
            return text, usage.get("prompt_tokens", 0) or 0, usage.get("completion_tokens", 0) or 0, choice.get("finish_reason")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:600]
            if e.code not in VERTEX_RETRYABLE or attempt == max_attempts:
                raise bg.NonRetryable(f"HTTP {e.code}: {detail}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == max_attempts:
                raise bg.NonRetryable(f"connection error, exhausted {max_attempts} attempts: {e}") from e
        sleep_s = delay * (1 + random.uniform(-0.2, 0.2))
        print(f"  transient error, retry {attempt}/{max_attempts} in {sleep_s:.1f}s", file=sys.stderr, flush=True)
        time.sleep(sleep_s)
        delay *= 2
    raise bg.NonRetryable("unreachable: retry loop exited without returning or raising")

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

FENCE = re.compile(r"```(\w*)[ \t]*\n(.*?)```", re.S)


def exemplar_text(directory: Path, names: tuple[str, ...]) -> str:
    parts = []
    for n in names:
        t_src = (directory / f"{n}.t").read_text(encoding="utf-8").strip()
        io_src = (directory / f"{n}_io.py").read_text(encoding="utf-8").strip()
        parts.append(f"Example {n}:\n```t\n{t_src}\n```\n```python\n{io_src}\n```")
    return "\n\n".join(parts)


def system_text(exemplars: str) -> str:
    return (se.GRAMMAR_V5 + "\nExamples of complete t tasks:\n\n" + se.fewshot_text("v5")
            + "\n\n" + IO_CONTRACT + "\n\nExamples of judge problems solved this way:\n\n" + exemplars)


def user_text(rec: dict) -> str:
    title = rec.get("title") or ""
    return (f"Judge problem {rec['judge']} {rec['id']}: {title}\n\n{rec['statement'].strip()}\n\n"
            f"A stored case of the judge -- input:\n{rec['sample_in']}\nexpected output:\n{rec['sample_out']}\n\n"
            f"Write the t task `p{rec['id']}` and its io module.")


def extract(reply: str) -> tuple[str | None, str | None]:
    t_src = io_src = None
    for lang, body in FENCE.findall(reply):
        if lang == "t" and t_src is None:
            t_src = body
        elif lang in ("python", "py") and io_src is None:
            io_src = body
    return t_src, io_src


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
    ap.add_argument("--out", default="", help="default t/out/udebug/teacher-<tag>")
    ap.add_argument("--provider", choices=("bedrock", "vertex"), default="bedrock")
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
    exemplars = exemplar_text(Path(a.exemplars), tuple(n for n in a.exemplar_names.split(",") if n))
    system = system_text(exemplars)
    ids = {k.strip() for k in a.ids.split(",") if k.strip()}
    judges = {j.strip() for j in a.judges.split(",") if j.strip()}
    problems = select(Path(a.bank), judges, a.shape, a.split, ids, a.limit, a.max_in_bytes)
    print(f"{len(problems)} problems selected; system prompt {len(system)} chars", flush=True)

    jobs = []
    for rec in problems:
        for k in range(1, a.samples + 1):
            d = out / f"{rec['judge']}-{rec['id']}" / f"s{k}"
            if (d / "record.json").is_file():
                continue
            jobs.append((rec, k, d))
    print(f"{len(jobs)} calls to make ({a.samples} per problem, resumed ones skipped)", flush=True)
    if a.dry_run:
        for rec, k, d in jobs[:1]:
            d.mkdir(parents=True, exist_ok=True)
            (d / "prompt.json").write_text(json.dumps(
                [{"role": "system", "content": system}, {"role": "user", "content": user_text(rec)}], indent=1))
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
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user_text(rec)}]
        t0 = time.monotonic()
        try:
            reply, in_tok, out_tok, stop_reason = call(messages)
        except bg.NonRetryable as e:
            with lock:
                ledger["stop"] = True
            print(f"ABORT {rec['judge']}/{rec['id']} s{k}: {e}", file=sys.stderr, flush=True)
            return "aborted"
        wall = time.monotonic() - t0
        t_src, io_src = extract(reply)
        d.mkdir(parents=True, exist_ok=True)
        if t_src is not None and io_src is not None:
            (d / f"p{rec['id']}.t").write_text(t_src.rstrip() + "\n", encoding="utf-8")
            (d / f"p{rec['id']}_io.py").write_text(io_src.rstrip() + "\n", encoding="utf-8")
        record = {"judge": rec["judge"], "id": rec["id"], "title": rec.get("title"), "tests_dir": rec["tests_dir"],
                  "model": model, "provider": a.provider, "endpoint": endpoint, "tag": a.tag,
                  "sample_index": k, "num_samples": a.samples,
                  "options": {"temperature": a.temperature, "max_tokens": a.max_tokens,
                              "note": "no seed on either provider; this reply is not reproducible"},
                  "messages": messages, "reply": reply, "prompt_tokens": in_tok, "reply_tokens": out_tok,
                  "wall_s": round(wall, 3), "done_reason": stop_reason,
                  "fences": {"t": t_src is not None, "python": io_src is not None}}
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

    workers = max(1, min(a.concurrency, bg.HARD_MAX_CONCURRENCY))
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
