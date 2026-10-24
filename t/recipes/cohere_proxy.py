#!/usr/bin/env python3
"""A chat-completions endpoint in front of Cohere's v2 Chat API, so the frozen route (t/recipes/v6_server_route.py)
can use a Cohere model as a teacher with no change to the route. Modelled on t/recipes/bedrock_proxy.py.

Used under the Cohere Labs Catalyst Grant, with Cohere's written permission (2026-10-24) to turn outputs that pass our
checks into training rows for dawnr (internal/COHERE-GRANT-UPDATES.md). Every call is priced from Cohere's billed
units and appended to the grant ledger (~/.config/cohere/ledger.jsonl, shared with ~/.local/bin/cohere); past the
ceiling the proxy answers every request with an empty "length" reply and calls nothing.

Mapping: messages pass through (string content); max_tokens -> max_tokens plus the thinking budget when thinking is
on; temperature -> temperature; top_p -> p (clamped to 0.01..0.99); seed -> seed. finish_reason COMPLETE or
STOP_SEQUENCE -> stop, MAX_TOKENS -> length; thinking blocks are dropped from the content. A call that fails after
every retry becomes an empty "length" reply: one bad call costs one candidate, never the chunk.

    python3 t/recipes/cohere_proxy.py --port 8863 --model command-a-reasoning-08-2025 --think 2048 --log out/r61/cohere-proxy.jsonl
Sources: docs.cohere.com/reference/chat (v2 request and response fields, thinking.token_budget, billed_units);
t/recipes/bedrock_proxy.py (the reply fields the route checks, the failure policy).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

API = "https://api.cohere.com/v2/chat"
LEDGER = os.path.expanduser("~/.config/cohere/ledger.jsonl")
# USD per million billed tokens (in, out). Cohere publishes no list price for some of these; the conservative figures
# make the ledger overstate spend, so the ceiling trips early rather than late. Read the real balance in the dashboard.
PRICE = {"command-a-03-2025": (2.5, 10), "command-a-reasoning-08-2025": (5, 20), "command-a-plus-05-2026": (5, 20),
         "command-r-plus-08-2024": (2.5, 10), "command-r-08-2024": (0.15, 0.6), "command-r7b-12-2024": (0.0375, 0.15),
         "c4ai-aya-expanse-32b": (0.5, 1.5),
         # API evaluation is listed as free within rate limits on 2026-10-24; paid Model Vault is separate.
         # https://docs.cohere.com/docs/north-mini-code-1.0
         "north-mini-code-1-0": (0, 0)}


def to_cohere(body: dict, model: str, think: int) -> dict:
    msgs = []
    for m in body.get("messages", []):
        text = m.get("content") if isinstance(m.get("content"), str) else "".join(
            c.get("text", "") for c in (m.get("content") or []) if isinstance(c, dict))
        if m.get("role") in ("system", "user", "assistant"):
            msgs.append({"role": m["role"], "content": text})
    max_new = int(body.get("max_tokens") or 1024)
    req = {"model": model, "messages": msgs, "stream": False}
    if think > 0:
        req["thinking"] = {"type": "enabled", "token_budget": think}
        req["max_tokens"] = max_new + think
    elif think < 0:
        req["thinking"] = {"type": "disabled"}
        req["max_tokens"] = max_new
    else:
        req["max_tokens"] = max_new
    if body.get("temperature") is not None:
        req["temperature"] = float(body["temperature"])
    if body.get("top_p") is not None:
        req["p"] = min(0.99, max(0.01, float(body["top_p"])))
    if body.get("seed") is not None:
        req["seed"] = int(body["seed"])
    return req


def from_cohere(result: dict, max_new: int, model: str) -> dict:
    blocks = (result.get("message") or {}).get("content") or []
    content = "".join(b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text")
    fr = result.get("finish_reason")
    finish = "stop" if fr in ("COMPLETE", "STOP_SEQUENCE", "TOOL_CALL") else "length"
    tokens = (result.get("usage") or {}).get("tokens") or {}
    out_tokens = int(tokens.get("output_tokens", 0) or 0)
    return {"model": model, "choices": [{"index": 0, "message": {"role": "assistant", "content": content},
                                         "finish_reason": finish}],
            "usage": {"prompt_tokens": int(tokens.get("input_tokens", 0) or 0),
                      "completion_tokens": min(out_tokens, max_new),
                      "total_tokens": int(tokens.get("input_tokens", 0) or 0) + out_tokens},
            "stop_reason_raw": fr}


def call(key: str, req: dict, attempts: int = 7, timeout: int = 600) -> dict:
    data = json.dumps(req).encode()
    delay = 3.0
    for attempt in range(1, attempts + 1):
        r = urllib.request.Request(API, data=data, method="POST", headers={
            "Authorization": "Bearer " + key, "Content-Type": "application/json", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(r, timeout=timeout) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:300]
            if e.code not in (429, 500, 502, 503, 504) or attempt == attempts:
                raise RuntimeError(f"HTTP {e.code}: {msg}")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt == attempts:
                raise RuntimeError(f"network: {e}")
        time.sleep(delay)
        delay = min(delay * 2, 120)
    raise RuntimeError("unreachable")


class Handler(BaseHTTPRequestHandler):
    server_version = "dawnr-cohere-proxy/1"

    def log_message(self, *_):
        pass

    def do_GET(self):
        if self.path.startswith("/health"):
            self._send(200, {"status": "ok", "model": self.server.model, "spent_usd": round(self.server.spent, 4)})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self.path.endswith("/chat/completions"):
            return self._send(404, {"error": "not found"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        except Exception as e:                                  # noqa: BLE001
            return self._send(400, {"error": f"bad json: {e}"})
        max_new = int(body.get("max_tokens") or 1024)
        empty = {"model": self.server.model, "choices": [{"index": 0, "message": {"role": "assistant", "content": ""},
                                                          "finish_reason": "length"}],
                 "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}
        if self.server.spent >= self.server.ceiling:
            self.server.log({"ok": False, "error": "ceiling", "spent_usd": round(self.server.spent, 4)})
            return self._send(200, {**empty, "error": "ceiling"})
        t0 = time.time()
        with self.server.gate:
            try:
                result = call(self.server.key, to_cohere(body, self.server.model, self.server.think))
            except Exception as e:                              # noqa: BLE001
                self.server.log({"ok": False, "error": str(e)[:300], "seconds": round(time.time() - t0, 1)})
                return self._send(200, {**empty, "error": str(e)[:300]})
        reply = from_cohere(result, max_new, self.server.model)
        billed = (result.get("usage") or {}).get("billed_units") or {}
        bi, bo = float(billed.get("input_tokens", 0) or 0), float(billed.get("output_tokens", 0) or 0)
        pi, po = PRICE.get(self.server.model, (5, 20))
        usd = bi * pi / 1e6 + bo * po / 1e6
        self.server.charge(usd, {"in": bi, "out": bo, "tag": self.server.tag})
        self.server.log({"ok": True, "seconds": round(time.time() - t0, 1), "stop": reply["stop_reason_raw"],
                         "billed_in": bi, "billed_out": bo, "usd": round(usd, 6), **reply["usage"]})
        self._send(200, reply)

    def _send(self, code: int, payload: dict):
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, addr, model, think, concurrency, log_path, ceiling, tag):
        super().__init__(addr, Handler)
        self.model, self.think, self.ceiling, self.tag = model, think, ceiling, tag
        self.key = open(os.path.expanduser("~/.config/cohere/api_key")).read().strip()
        self.gate = threading.Semaphore(concurrency)
        self.lock = threading.Lock()
        self.log_path = log_path
        self.spent = 0.0
        self.calls = 0
        if os.path.exists(LEDGER):
            self.spent = sum(json.loads(l).get("usd", 0) for l in open(LEDGER) if l.strip())

    def charge(self, usd: float, meta: dict):
        with self.lock:
            with open(LEDGER, "a") as f:
                f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "kind": "chat-proxy",
                                    "model": self.model, "usd": round(usd, 6), **meta}) + "\n")
            self.calls += 1
            if self.calls % 25 == 0:        # other writers share the ledger: re-read it so the ceiling is the grant's
                self.spent = sum(json.loads(l).get("usd", 0) for l in open(LEDGER) if l.strip())
            else:
                self.spent += usd

    def log(self, record: dict):
        record["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self.lock, open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--port", type=int, default=8863)
    ap.add_argument("--model", default="command-a-reasoning-08-2025")
    ap.add_argument("--think", type=int, default=0, help="thinking budget in tokens; 0 = the model's default, -1 = off")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--ceiling", type=float, default=float(os.environ.get("COHERE_CEILING_USD", "950")))
    ap.add_argument("--tag", default="teacher")
    ap.add_argument("--log", default="cohere-proxy.jsonl")
    a = ap.parse_args(argv)
    server = Server(("127.0.0.1", a.port), a.model, a.think, a.concurrency, a.log, a.ceiling, a.tag)
    print(f"cohere proxy on 127.0.0.1:{a.port} -> {a.model} (think {a.think}), {a.concurrency} in flight, "
          f"ledger ${server.spent:.2f} of ${a.ceiling}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
