#!/usr/bin/env python3
"""locallm/bedrock_proxy.py -- a text-only, nonstreaming Bedrock proxy with an estimated per-run request budget.

    ~/.venv-bedrock/bin/python locallm/bedrock_proxy.py --port 8790 --cap 60 --ledger LEDGER.jsonl --key-file KEY

The pipeline's own client (t/spec_experiment.py `chat`, --api openai) and t/rl_teacher_expert_iter.py
sample-spec send POST /v1/chat/completions here, with the proxy's key as their bearer token (T_API_KEY). The
proxy forwards each request to Bedrock's OpenAI-compatible endpoint, bedrock-mantle
(docs.aws.amazon.com/bedrock/latest/userguide/bedrock-mantle.html), on the flex service tier, with a short-term
Bedrock API key it mints from the operator's AWS login: the shorter of 12 hours and the life of the credentials
that sign it (docs.aws.amazon.com/bedrock/latest/userguide/api-keys-generate.html), so it is re-minted before the
credentials the AWS CLI refreshes run out. The AWS key never leaves this process.

Before dispatch, the journal reserves the serialized request's UTF-8 byte count plus framing headroom and the
forwarded output limit, priced at the highest registered rates. Bytes are an estimate, not a proven token bound.
Valid usage settles at the registered rate for the reported tier; uncertain outcomes consume the reservation.
Reservations survive restart, one writer owns the journal, and observed overruns stop further admission.
There are no automatic retries. This local estimate is neither an account-wide limit nor a billing guarantee;
current prices must be verified before a run and AWS billing remains the authority. The journal records no
prompts, completions or credentials. Only plain text messages and one completion per request are accepted.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# USD per million tokens (input, output), us-east-1, from the AWS Price List API
# (aws pricing get-products --service-code AmazonBedrock, read 2026-10-03): the flex tier, and standard in case
# Bedrock reports that it served a request on standard instead
PRICES = {
    "openai.gpt-oss-120b": {"flex": (0.075, 0.30), "default": (0.15, 0.60)},
    "qwen.qwen3-235b-a22b-2507": {"flex": (0.11, 0.44), "default": (0.22, 0.88)},
    "qwen.qwen3-coder-next": {"flex": (0.25, 0.60), "default": (0.50, 1.20)},
    "deepseek.v3.2": {"flex": (0.31, 0.925), "default": (0.62, 1.85)},
    "zai.glm-5": {"flex": (0.50, 1.60), "default": (1.00, 3.20)},
}
PRICING_REGION = "us-east-1"
DEFAULT_OUTPUT_TOKENS = 4096
MAX_OUTPUT_TOKENS = 131072
MAX_REQUEST_BYTES = 1024 * 1024
_FIELDS = {"model", "messages", "max_tokens", "max_completion_tokens", "service_tier", "stream", "n",
           "temperature", "top_p", "seed", "stop", "frequency_penalty", "presence_penalty"}


def _rates(model: str, tier: str) -> tuple[Decimal, Decimal]:
    if not isinstance(model, str) or model not in PRICES or not isinstance(tier, str) or tier not in PRICES[model]:
        raise ValueError("model and service tier must have registered prices")
    pair = PRICES[model][tier]
    if not isinstance(pair, (tuple, list)) or len(pair) != 2:
        raise ValueError("invalid registered price")
    rates = tuple(Ledger._money(value) for value in pair)
    if any(rate <= 0 for rate in rates):
        raise ValueError("registered prices must be positive")
    return rates


def usd(model: str, tier: str, prompt_tokens: int, completion_tokens: int) -> float:
    if any(type(value) is not int or value < 0 for value in (prompt_tokens, completion_tokens)):
        raise ValueError("usage counts must be nonnegative integers")
    p_in, p_out = _rates(model, tier)
    return float((prompt_tokens * p_in + completion_tokens * p_out) / Decimal(1000000))


def prepare_request(body: dict) -> tuple[dict, float]:
    """Validate the supported billing scope and return exactly what will be sent, with its estimate."""
    if not isinstance(body, dict) or set(body) - _FIELDS:
        raise ValueError("expected a JSON object with supported text-completion fields only")
    body = dict(body)
    model, tier = body.get("model"), body.setdefault("service_tier", "flex")
    _rates(model, tier)
    if body.get("stream", False) is not False or type(body.get("n", 1)) is not int or body.get("n", 1) != 1:
        raise ValueError("only one nonstreaming completion is supported")
    body.update(stream=False, n=1)
    messages = body.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages must be a nonempty list of text messages")
    for message in messages:
        if (not isinstance(message, dict) or set(message) != {"role", "content"}
                or message["role"] not in ("system", "developer", "user", "assistant")
                or not isinstance(message["content"], str)):
            raise ValueError("messages require a supported role and plain text content")
    if "max_tokens" in body and "max_completion_tokens" in body:
        raise ValueError("supply only one output token limit")
    limit_key = "max_completion_tokens" if "max_completion_tokens" in body else "max_tokens"
    limit = body.setdefault(limit_key, DEFAULT_OUTPUT_TOKENS)
    if type(limit) is not int or not 1 <= limit <= MAX_OUTPUT_TOKENS:
        raise ValueError(f"output token limit must be an integer from 1 to {MAX_OUTPUT_TOKENS}")
    for field, low, high in (("temperature", 0, 2), ("top_p", 0, 1),
                             ("frequency_penalty", -2, 2), ("presence_penalty", -2, 2)):
        if field in body:
            value = body[field]
            if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"invalid {field}")
    if "seed" in body and (type(body["seed"]) is not int or not -(2 ** 63) <= body["seed"] < 2 ** 63):
        raise ValueError("seed must be a signed 64-bit integer")
    if "stop" in body and not (isinstance(body["stop"], str) or
            isinstance(body["stop"], list) and 1 <= len(body["stop"]) <= 4
            and all(isinstance(value, str) for value in body["stop"])):
        raise ValueError("stop must be text or one to four text strings")
    encoded = json.dumps(body, allow_nan=False).encode("utf-8")
    if len(encoded) > MAX_REQUEST_BYTES:
        raise ValueError("normalized request exceeds the byte limit")
    # Deliberately conservative for ordinary text; not a provider tokenizer or a mathematical upper bound.
    estimated_input = len(encoded) + 1024 + 32 * len(messages)
    rates = [_rates(model, name) for name in PRICES[model]]
    estimate = (estimated_input * max(rate[0] for rate in rates)
                + limit * max(rate[1] for rate in rates)) / Decimal(1000000)
    return body, float(estimate)


def usage_cost(model: str, payload: bytes) -> dict:
    """No supplied charge means the ledger retains the full reservation."""
    try:
        response = json.loads(payload)
        usage, tier = response["usage"], response["service_tier"]
        prompt, completion = usage["prompt_tokens"], usage["completion_tokens"]
        amount = usd(model, tier, prompt, completion)
        return {"tier": tier, "prompt_tokens": prompt, "completion_tokens": completion, "usd": amount}
    except (ValueError, KeyError, TypeError, OverflowError):
        return {"usage_status": "missing_or_invalid"}


class Bedrock:
    def __init__(self, region: str, aws: str):
        if region != PRICING_REGION:
            raise ValueError("this price registry covers only " + PRICING_REGION)
        self.region, self.aws = region, aws
        self.url = f"https://bedrock-mantle.{region}.api.aws/v1/chat/completions"
        self._lock, self._token, self._until = threading.Lock(), None, 0.0

    def token(self) -> str:
        with self._lock:
            if self._token and time.time() < self._until - 180:
                return self._token
            # imported here so --help works without the AWS libraries
            from botocore.credentials import Credentials
            from aws_bedrock_token_generator.token_generator import _generate_token
            p = subprocess.run([self.aws, "configure", "export-credentials", "--format", "process"],
                               capture_output=True, text=True, timeout=120)
            if p.returncode != 0:
                raise RuntimeError("the AWS login has expired; run `aws login` (" + p.stderr.strip()[-160:] + ")")
            c = json.loads(p.stdout)
            expires = (dt.datetime.fromisoformat(c["Expiration"]).timestamp() if c.get("Expiration")
                       else time.time() + 3600)
            life = int(min(12 * 3600, max(60, expires - time.time())))
            self._token = _generate_token(Credentials(c["AccessKeyId"], c["SecretAccessKey"], c.get("SessionToken")),
                                          self.region, life)
            self._until = time.time() + life
            return self._token

    def chat(self, body: dict, timeout: float) -> tuple[int, bytes]:
        data = json.dumps(body, allow_nan=False).encode("utf-8")
        req = urllib.request.Request(self.url, data=data, headers={
            "Content-Type": "application/json", "Authorization": "Bearer " + self.token()})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as error:
            with error:
                return error.code, error.read()
        except (urllib.error.URLError, TimeoutError, OSError):
            # A lost response can follow a billable completion. Retrying would create another unreserved attempt.
            return 504, b'{"error": {"message": "bedrock_proxy: no reply from Bedrock; outcome uncertain"}}'


class Ledger:
    def __init__(self, path: Path, cap: float):
        self.path, self.cap, self.lock = Path(path).expanduser().resolve(), float(cap), threading.Lock()
        self._cap = self._money(cap)
        if self._cap <= 0:
            raise ValueError('cap must be positive and finite')
        self._spent, self._pending, self.requests = Decimal(0), {}, 0
        self._seen = set()
        self._blocked = False
        self._owner = None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # A second proxy cannot reserve independently against the same file.
        import fcntl
        self._owner = self.path.with_suffix(self.path.suffix + '.lock').open('a')
        try:
            fcntl.flock(self._owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if self.path.exists():
                for line in self.path.read_text(encoding='utf-8').splitlines():
                    row = json.loads(line)
                    if not isinstance(row, dict):
                        raise ValueError('ledger records must be objects')
                    event = row.get('event')
                    if event == 'reserve':
                        ticket = row['reservation_id']
                        if not isinstance(ticket, str) or not ticket or ticket in self._seen:
                            raise ValueError('invalid or duplicate reservation')
                        amount = self._money(row['reserved_usd'])
                        if amount <= 0:
                            raise ValueError('reservation must be positive')
                        self._pending[ticket] = amount
                        self._seen.add(ticket)
                    elif event == 'settle':
                        ticket = row['reservation_id']
                        if ticket not in self._pending:
                            raise ValueError('settlement has no pending reservation')
                        amount = self._money(row['usd'])
                        self._blocked |= amount > self._pending.pop(ticket)
                        self._spent += amount
                        self.requests += 1
                    elif event is None and 'usd' in row:
                        # Historical priced records retain their recorded cost.
                        self._spent += self._money(row['usd'])
                        self.requests += 1
                    else:
                        raise ValueError('unpriced or unknown ledger record')
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _money(value) -> Decimal:
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
            raise ValueError('cost must be a finite nonnegative number')
        result = Decimal(str(value))
        if not result.is_finite() or result < 0:
            raise ValueError('cost must be a finite nonnegative number')
        return result

    @property
    def spent(self) -> float:
        return float(self._spent)

    @property
    def reserved(self) -> float:
        return float(sum(self._pending.values(), Decimal(0)))

    def _append(self, row: dict) -> None:
        if self._owner is None:
            raise RuntimeError('ledger is closed')
        payload = (json.dumps(row, allow_nan=False) + '\n').encode('utf-8')
        try:
            created = not self.path.exists()
            with self.path.open('ab', buffering=0) as handle:
                if handle.write(payload) != len(payload):
                    raise OSError('incomplete ledger write')
                os.fsync(handle.fileno())
            if created:
                descriptor = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        except BaseException:
            self._blocked = True
            raise

    def reserve(self, amount: float) -> str | None:
        value = self._money(amount)
        if value <= 0:
            raise ValueError('reservation must be positive')
        with self.lock:
            if self._blocked or self._spent + sum(self._pending.values(), Decimal(0)) + value > self._cap:
                return None
            ticket = uuid.uuid4().hex
            self._append({'event': 'reserve', 'reservation_id': ticket, 'reserved_usd': float(value)})
            self._pending[ticket] = value
            self._seen.add(ticket)
            return ticket

    def settle(self, ticket: str, row: dict) -> None:
        with self.lock:
            if ticket not in self._pending:
                raise ValueError('unknown or already settled reservation')
            reserved = self._pending[ticket]
            try:
                amount = self._money(row['usd'])
                accounting = 'reported_usage'
            except (KeyError, ValueError):
                amount, accounting = reserved, 'uncertain_reserved_cost'
            event = dict(row, event='settle', reservation_id=ticket, usd=float(amount), accounting=accounting)
            self._append(event)
            self._blocked |= amount > reserved
            self._pending.pop(ticket)
            self._spent += amount
            self.requests += 1

    def close(self) -> None:
        if self._owner is not None:
            self._owner.close()
            self._owner = None


def make_handler(bedrock: Bedrock, ledger: Ledger, key: str, timeout: float):
    if not isinstance(key, str) or not key or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("a nonempty key and positive finite timeout are required")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, code: int, payload: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass                                        # accounting was already settled before sending

        def error(self, code: int, message: str) -> None:
            self.reply(code, json.dumps({"error": {"message": "bedrock_proxy: " + message}}).encode())

        def do_GET(self):
            if self.path.rstrip("/") == "/health":
                with ledger.lock:
                    state = {"spent_usd": round(ledger.spent, 4), "reserved_usd": round(ledger.reserved, 4),
                             "cap_usd": ledger.cap, "requests": ledger.requests,
                             "admission_blocked": ledger._blocked, "accounting": "estimated_request_budget"}
                return self.reply(200, json.dumps(state).encode())
            self.error(404, "only POST /v1/chat/completions and GET /health")

        def do_POST(self):
            if self.path.rstrip("/") != "/v1/chat/completions":
                return self.error(404, "only POST /v1/chat/completions and GET /health")
            if not secrets.compare_digest(self.headers.get("Authorization", "").encode(), ("Bearer " + key).encode()):
                return self.error(401, "wrong key")
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) != 1 or self.headers.get("Transfer-Encoding") is not None:
                return self.error(400, "one Content-Length and no Transfer-Encoding are required")
            try:
                length = int(lengths[0])
                if not 1 <= length <= MAX_REQUEST_BYTES:
                    return self.error(413, "request body is empty or exceeds the byte limit")
                self.connection.settimeout(min(timeout, 30))
                raw = self.rfile.read(length)
                if len(raw) != length:
                    return self.error(400, "incomplete request body")
                body = json.loads(raw)
                body, estimate = prepare_request(body)
            except (ValueError, TypeError, UnicodeError, OverflowError):
                return self.error(400, "invalid JSON, limits, prices, or unsupported text-completion request")
            except (TimeoutError, OSError):
                return self.error(408, "request body could not be read")
            try:
                ticket = ledger.reserve(estimate)
            except (OSError, RuntimeError, ValueError):
                return self.error(503, "the accounting journal is unavailable; request was not dispatched")
            if ticket is None:
                return self.error(402, f"the estimated request budget of ${ledger.cap:.2f} cannot admit this request")
            t0, status, payload = time.monotonic(), 500, b""
            row = {"t": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "model": body["model"]}
            try:
                status, payload = bedrock.chat(body, timeout)
                if status == 200:
                    row.update(usage_cost(body["model"], payload))
            except Exception as error:                            # noqa: BLE001 -- preserve uncertain charges
                status, payload = 502, b'{"error": {"message": "bedrock_proxy: upstream outcome uncertain"}}'
                row["error_kind"] = type(error).__name__
            row.update(status=status, seconds=round(time.monotonic() - t0, 1))
            try:
                ledger.settle(ticket, row)
            except (OSError, RuntimeError, ValueError):
                # The durable reservation remains, and Ledger blocks further admission after a write failure.
                return self.error(503, "the accounting outcome could not be recorded; reservation retained")
            self.reply(status, payload)

    return Handler


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--cap", type=float, required=True, help="estimated USD request budget; AWS billing may differ")
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--key-file", type=Path, required=True, help="created with a random key if absent")
    ap.add_argument("--region", choices=[PRICING_REGION], default=PRICING_REGION)
    ap.add_argument("--aws", default=shutil.which("aws") or "aws", help="the AWS CLI that holds the login")
    ap.add_argument("--timeout", type=float, default=900.0)
    a = ap.parse_args(argv)
    if not 0 <= a.port <= 65535 or not math.isfinite(a.timeout) or a.timeout <= 0:
        ap.error("port must be 0..65535 and timeout positive and finite")
    if not math.isfinite(a.cap) or a.cap <= 0:
        ap.error("cap must be positive and finite")
    if not a.key_file.exists():
        a.key_file.parent.mkdir(parents=True, exist_ok=True)
        a.key_file.write_text(secrets.token_hex(24))
        a.key_file.chmod(0o600)
    key = a.key_file.read_text().strip()
    if not key:
        ap.error("the key file is empty")
    a.ledger.parent.mkdir(parents=True, exist_ok=True)
    bedrock, ledger = Bedrock(a.region, a.aws), Ledger(a.ledger, a.cap)
    try:
        bedrock.token()                                             # fail now, not on the first request
        with ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(bedrock, ledger, key, a.timeout)) as server:
            print(f"bedrock_proxy: http://127.0.0.1:{server.server_port}/v1, estimated budget ${a.cap:.2f}, "
                  f"accounted ${ledger.spent:.4f} over {ledger.requests} requests; AWS billing is authoritative",
                  flush=True)
            server.serve_forever()
    finally:
        ledger.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
