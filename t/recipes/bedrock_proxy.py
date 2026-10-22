#!/usr/bin/env python3
"""A chat-completions endpoint in front of Amazon Bedrock's Converse API, so the frozen route
(t/recipes/v6_server_route.py, which speaks llama.cpp's OpenAI-style endpoint) can use a Bedrock model as the
teacher without any change to the route. One thread per request; each request is one `aws bedrock-runtime converse`
call through the CLI (which carries the `aws login` session; boto3 is not installed here). The reply has exactly the
fields the route checks: one choice, message.content, finish_reason stop|length, usage.completion_tokens.

Mapping: system messages become Converse `system` blocks, the rest become `messages` with text blocks; max_tokens,
temperature and top_p become inferenceConfig; stopReason end_turn -> stop, max_tokens -> length; reasoning blocks
(DeepSeek) are dropped from the content. Every call is logged as one JSON line (tokens in and out) for the spend.

    python3 t/recipes/bedrock_proxy.py --port 8853 --model deepseek.v3.2 --region us-east-1 --log out/v9/bedrock-proxy.jsonl
Sources: docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html (the Converse request and
response shapes); t/recipes/v6_server_route.py (the fields the route sends and checks); t/bedrock_generate.py
(the earlier Bedrock sampler, boto3, backoff on throttling).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def to_converse(body: dict) -> tuple[list[dict], list[dict], dict]:
    """(system blocks, messages, inferenceConfig) for a chat-completions request body."""
    system, messages = [], []
    for m in body.get("messages", []):
        text = m.get("content") if isinstance(m.get("content"), str) else "".join(
            c.get("text", "") for c in (m.get("content") or []) if isinstance(c, dict))
        if m.get("role") == "system":
            system.append({"text": text})
        elif m.get("role") in ("user", "assistant"):
            if messages and messages[-1]["role"] == m["role"]:
                messages[-1]["content"].append({"text": text})          # Converse wants alternating roles
            else:
                messages.append({"role": m["role"], "content": [{"text": text}]})
    config = {"maxTokens": int(body.get("max_tokens") or 1024)}
    if body.get("temperature") is not None:
        config["temperature"] = float(body["temperature"])
    if body.get("top_p") is not None:
        config["topP"] = float(body["top_p"])
    return system, messages, config


def from_converse(result: dict, max_new: int, model: str) -> dict:
    """The chat-completions reply the route checks, from a Converse result."""
    blocks = result.get("output", {}).get("message", {}).get("content", [])
    content = "".join(b.get("text", "") for b in blocks if isinstance(b, dict) and "text" in b)
    stop = result.get("stopReason")
    finish = "stop" if stop in ("end_turn", "stop_sequence", "tool_use") else "length"
    usage = result.get("usage", {})
    out_tokens = int(usage.get("outputTokens", 0) or 0)
    return {"model": model, "choices": [{"index": 0, "message": {"role": "assistant", "content": content},
                                         "finish_reason": finish}],
            "usage": {"prompt_tokens": int(usage.get("inputTokens", 0) or 0),
                      "completion_tokens": min(out_tokens, max_new), "total_tokens": int(usage.get("totalTokens", 0) or 0)},
            "stop_reason_raw": stop}


def converse_cli(model: str, region: str, system: list[dict], messages: list[dict], config: dict,
                 attempts: int = 6, timeout: int = 600) -> dict:
    """One Converse call through the aws CLI, with backoff on throttling and transient errors."""
    env = dict(os.environ, AWS_PAGER="", AWS_MAX_ATTEMPTS="5", AWS_RETRY_MODE="adaptive")
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(messages, f)
        mpath = f.name
    try:
        cmd = ["aws", "bedrock-runtime", "converse", "--region", region, "--model-id", model,
               "--messages", f"file://{mpath}", "--inference-config", json.dumps(config), "--output", "json",
               "--cli-read-timeout", str(timeout)]
        if system:
            cmd += ["--system", json.dumps(system)]
        delay = 4.0
        for attempt in range(1, attempts + 1):
            p = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout + 60)
            if p.returncode == 0:
                return json.loads(p.stdout)
            err = p.stderr.strip()[-400:]
            transient = any(k in err for k in ("Throttling", "TooManyRequests", "ServiceUnavailable",
                                                "ModelNotReady", "timed out", "Timeout", "InternalServer",
                                                "Rate exceeded", "(429)", "CreateOAuth2Token"))
            if not transient or attempt == attempts:
                raise RuntimeError(err or f"aws exited {p.returncode}")
            time.sleep(delay)
            delay = min(delay * 2, 90)
    finally:
        os.unlink(mpath)


class Handler(BaseHTTPRequestHandler):
    server_version = "dawnr-bedrock-proxy/1"

    def log_message(self, *_):                                  # quiet
        pass

    def do_GET(self):
        if self.path.startswith("/health"):
            self._send(200, {"status": "ok", "model": self.server.model})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self.path.endswith("/chat/completions"):
            return self._send(404, {"error": "not found"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
        except Exception as e:                                  # noqa: BLE001
            return self._send(400, {"error": f"bad json: {e}"})
        system, messages, config = to_converse(body)
        t0 = time.time()
        with self.server.gate:
            try:
                result = converse_cli(self.server.model, self.server.region, system, messages, config)
            except Exception as e:                              # noqa: BLE001
                # a call that fails after every retry becomes an empty "length" reply, exactly what the route makes of
                # llama.cpp's 400 (v6_server_route.Decoder._post): one bad call costs one candidate, never the chunk
                # (2026-10-22 14:51Z: one "CreateOAuth2Token Rate exceeded" 502 killed a 50-problem chunk)
                self.server.log({"ok": False, "error": str(e)[:300], "seconds": round(time.time() - t0, 1)})
                return self._send(200, {"model": self.server.model, "error": str(e)[:300],
                                        "choices": [{"index": 0, "message": {"role": "assistant", "content": ""},
                                                     "finish_reason": "length"}],
                                        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}})
        reply = from_converse(result, int(body.get("max_tokens") or 1024), self.server.model)
        self.server.log({"ok": True, "seconds": round(time.time() - t0, 1), "stop": reply["stop_reason_raw"],
                         **reply["usage"]})
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

    def __init__(self, addr, model, region, concurrency, log_path):
        super().__init__(addr, Handler)
        self.model, self.region = model, region
        self.gate = threading.Semaphore(concurrency)
        self.log_lock = threading.Lock()
        self.log_path = log_path

    def log(self, record: dict):
        record["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self.log_lock, open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--port", type=int, default=8853)
    ap.add_argument("--model", default="deepseek.v3.2")
    ap.add_argument("--region", default="us-east-1")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--log", default="bedrock-proxy.jsonl")
    a = ap.parse_args(argv)
    server = Server(("127.0.0.1", a.port), a.model, a.region, a.concurrency, a.log)
    print(f"bedrock proxy on 127.0.0.1:{a.port} -> {a.model} ({a.region}), {a.concurrency} in flight", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
