#!/usr/bin/env python3
"""ollama_shim.py: speak ollama's /api/chat on one port and forward to a vLLM
OpenAI-compatible server on another, so t/spec_experiment.py (which posts
ollama's chat body and reads response["message"]["content"]) samples from a
vLLM-served model unchanged. 2026-09-15, the four-card window. Standard
library only.

    python3 ollama_shim.py --listen 127.0.0.1:11434 --upstream 127.0.0.1:8000

ollama options mapped: temperature, seed, num_predict (max_tokens), top_p.
2026-09-15: --chat-template-kwargs '{"enable_thinking": false}' is passed to
every upstream request as chat_template_kwargs; Qwen3.8's template opens a
thinking block by default and the visible reply was the reasoning, cut at
the token cap (15 of the first 17 at 3072). The kwargs are echoed back as
`shim_chat_template_kwargs` on every reply.
Everything else in `options` is dropped, and the response says so in
`shim_dropped` so a record can never silently claim an option it did not get.
"""
import argparse, json, sys, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UP = "127.0.0.1:8000"
KW = {}
MAP = {"temperature": "temperature", "seed": "seed", "num_predict": "max_tokens", "top_p": "top_p"}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"ollama shim over vllm\n")

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        if self.path != "/api/chat":
            self.send_response(404); self.end_headers(); return
        opts = body.get("options") or {}
        req = {"model": body["model"], "messages": body["messages"], "stream": False}
        dropped = []
        for k, v in opts.items():
            if k in MAP:
                req[MAP[k]] = v
            else:
                dropped.append(k)
        if KW:
            req["chat_template_kwargs"] = KW
        data = json.dumps(req).encode()
        r = urllib.request.Request(f"http://{UP}/v1/chat/completions", data=data,
                                   headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(r, timeout=float(body.get("shim_timeout", 1800))) as resp:
                out = json.loads(resp.read())
        except Exception as e:  # surface upstream failure as an ollama-style error
            self.send_response(502); self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(json.dumps({"error": f"shim upstream: {type(e).__name__}: {e}"[:500]}).encode()); return
        ch = out["choices"][0]
        reply = {"model": body["model"], "message": {"role": "assistant", "content": ch["message"]["content"]},
                 "done": True, "done_reason": ch.get("finish_reason"),
                 "prompt_eval_count": (out.get("usage") or {}).get("prompt_tokens"),
                 "eval_count": (out.get("usage") or {}).get("completion_tokens"),
                 "shim_dropped": dropped, "shim_chat_template_kwargs": KW}
        data = json.dumps(reply).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--listen", default="127.0.0.1:11434"); ap.add_argument("--upstream", default=UP); ap.add_argument("--chat-template-kwargs", default="")
    a = ap.parse_args(); UP = a.upstream
    KW = json.loads(a.chat_template_kwargs) if a.chat_template_kwargs else {}
    host, port = a.listen.rsplit(":", 1)
    print(f"ollama shim on {a.listen} -> vllm {UP}", flush=True)
    ThreadingHTTPServer((host, int(port)), H).serve_forever()
