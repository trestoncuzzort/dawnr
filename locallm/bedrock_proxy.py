#!/usr/bin/env python3
"""locallm/bedrock_proxy.py -- an OpenAI-shaped endpoint on this machine that forwards to Amazon Bedrock under a
hard spending cap (2026-10-03).

    ~/.venv-bedrock/bin/python locallm/bedrock_proxy.py --port 8790 --cap 60 --ledger LEDGER.jsonl --key-file KEY

The pipeline's own client (t/spec_experiment.py `chat`, --api openai) and t/rl_teacher_expert_iter.py
sample-spec send POST /v1/chat/completions here, with the proxy's key as their bearer token (T_API_KEY). The
proxy forwards each request to Bedrock's OpenAI-compatible endpoint, bedrock-mantle
(docs.aws.amazon.com/bedrock/latest/userguide/bedrock-mantle.html), on the flex service tier, with a short-term
Bedrock API key it mints from the operator's AWS login: the shorter of 12 hours and the life of the credentials
that sign it (docs.aws.amazon.com/bedrock/latest/userguide/api-keys-generate.html), so it is re-minted before the
credentials the AWS CLI refreshes run out. The AWS key never leaves this process.

The cap is why it exists. The account is on AWS's Free plan: usage draws on its credit and at $0 the account is
suspended (AWS Free Tier FAQ). Every reply is priced from the token counts Bedrock returns and the AWS Price List's
rate for the tier Bedrock says it applied, and written to the ledger. Before a request is forwarded, its worst
case (its prompt at three characters a token, plus all of max_tokens) is reserved; a request that could carry spent
plus reserved past the cap is refused with HTTP 402 and never reaches AWS. A model without a price here is refused.
The ledger is the running figure; the credit balance AWS itself reports (`aws freetier get-account-plan-state`)
is the result.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
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
RETRY_SECONDS = (5, 15, 45, 90)         # throttling (429) and server errors; flex capacity is lent, not reserved


def usd(model: str, tier: str, prompt_tokens: int, completion_tokens: int) -> float:
    p_in, p_out = PRICES[model].get(tier) or PRICES[model]["default"]
    return (prompt_tokens * p_in + completion_tokens * p_out) / 1e6


class Bedrock:
    def __init__(self, region: str, aws: str):
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
        data = json.dumps(body).encode("utf-8")
        for attempt in range(len(RETRY_SECONDS) + 1):
            try:
                req = urllib.request.Request(self.url, data=data, headers={
                    "Content-Type": "application/json", "Authorization": "Bearer " + self.token()})
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.status, resp.read()
            except urllib.error.HTTPError as e:
                payload = e.read()
                if (e.code == 429 or e.code >= 500) and attempt < len(RETRY_SECONDS):
                    time.sleep(RETRY_SECONDS[attempt])
                    continue
                return e.code, payload
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                if attempt < len(RETRY_SECONDS):
                    time.sleep(RETRY_SECONDS[attempt])
                    continue
                return 504, json.dumps({"error": {"message": f"bedrock_proxy: no reply from Bedrock: {e}"}}).encode()
        return 504, b'{"error": {"message": "bedrock_proxy: retries exhausted"}}'


class Ledger:
    def __init__(self, path: Path, cap: float):
        self.path, self.cap, self.lock = path, cap, threading.Lock()
        self.spent, self.reserved, self.requests = 0.0, 0.0, 0
        if path.exists():
            for line in path.read_text().splitlines():
                try:
                    self.spent += float(json.loads(line).get("usd", 0.0))
                    self.requests += 1
                except ValueError:
                    continue

    def reserve(self, amount: float) -> bool:
        with self.lock:
            if self.spent + self.reserved + amount > self.cap:
                return False
            self.reserved += amount
            return True

    def settle(self, reserved: float, row: dict) -> None:
        with self.lock:
            self.reserved -= reserved
            self.spent += row.get("usd", 0.0)
            self.requests += 1
            with self.path.open("a") as f:
                f.write(json.dumps(row) + "\n")


def make_handler(bedrock: Bedrock, ledger: Ledger, key: str, timeout: float):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, code: int, payload: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def error(self, code: int, message: str) -> None:
            self.reply(code, json.dumps({"error": {"message": "bedrock_proxy: " + message}}).encode())

        def do_GET(self):
            if self.path.rstrip("/") == "/health":
                with ledger.lock:
                    state = {"spent_usd": round(ledger.spent, 4), "reserved_usd": round(ledger.reserved, 4),
                             "cap_usd": ledger.cap, "requests": ledger.requests}
                return self.reply(200, json.dumps(state).encode())
            self.error(404, "only POST /v1/chat/completions and GET /health")

        def do_POST(self):
            if self.path.rstrip("/") != "/v1/chat/completions":
                return self.error(404, "only POST /v1/chat/completions and GET /health")
            if not secrets.compare_digest(self.headers.get("Authorization", ""), "Bearer " + key):
                return self.error(401, "wrong key")
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0) or 0))
            try:
                body = json.loads(raw)
            except ValueError:
                return self.error(400, "the body is not JSON")
            model = body.get("model", "")
            if model not in PRICES:
                return self.error(400, f"no price for {model!r}; it is not one of the registered teachers")
            body.setdefault("service_tier", "flex")
            body.pop("structured_outputs", None)                    # a vLLM field Bedrock does not take
            worst = usd(model, body["service_tier"], len(raw) // 3 + 64, int(body.get("max_tokens") or 4096))
            if not ledger.reserve(worst):
                return self.error(402, f"the cap of ${ledger.cap:.2f} would be passed (spent ${ledger.spent:.4f})")
            t0, status, payload, row = time.time(), 500, b"", {}
            try:
                status, payload = bedrock.chat(body, timeout)
                row = {"t": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "model": model,
                       "status": status, "seconds": round(time.time() - t0, 1)}
                if status == 200:
                    d = json.loads(payload)
                    u, tier = d.get("usage") or {}, d.get("service_tier") or "default"
                    pt, ct = int(u.get("prompt_tokens") or 0), int(u.get("completion_tokens") or 0)
                    row.update(tier=tier, prompt_tokens=pt, completion_tokens=ct, usd=round(usd(model, tier, pt, ct), 6))
            except Exception as e:                                  # noqa: BLE001 -- the reserve must be released
                status, payload = 502, json.dumps({"error": {"message": f"bedrock_proxy: {type(e).__name__}: {e}"}}).encode()
                row.update(status=status, error=str(e)[:200])
            finally:
                ledger.settle(worst, row or {"status": status})
            self.reply(status, payload)

    return Handler


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--cap", type=float, required=True, help="US dollars; nothing is forwarded past it")
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--key-file", type=Path, required=True, help="created with a random key if absent")
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--aws", default=shutil.which("aws") or "aws", help="the AWS CLI that holds the login")
    ap.add_argument("--timeout", type=float, default=900.0)
    a = ap.parse_args(argv)
    if not a.key_file.exists():
        a.key_file.parent.mkdir(parents=True, exist_ok=True)
        a.key_file.write_text(secrets.token_hex(24))
        a.key_file.chmod(0o600)
    key = a.key_file.read_text().strip()
    a.ledger.parent.mkdir(parents=True, exist_ok=True)
    bedrock, ledger = Bedrock(a.region, a.aws), Ledger(a.ledger, a.cap)
    bedrock.token()                                                 # fail now, not on the first request
    server = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(bedrock, ledger, key, a.timeout))
    print(f"bedrock_proxy: http://127.0.0.1:{a.port}/v1, cap ${a.cap:.2f}, spent ${ledger.spent:.4f} "
          f"over {ledger.requests} requests", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
