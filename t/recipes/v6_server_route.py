"""Run the existing Python-first route against a pinned llama.cpp server.

This keeps spec_first's prompts and acceptance gates, replacing its HF decoder only.
Both v5 and v6 use this route at Q8_0. Each request is saved so a restart reuses the
same answer instead of sampling again. Seeds depend on stage and prompt, not batch
membership. No held-out reference is provided to the model.

Sources: ../spec_first.py; ../student_generate.py;
https://github.com/ggml-org/llama.cpp/tree/f1cee9941b0e843ea260bf8dd9a090fbd9711b6a/tools/server
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import urllib.error
import urllib.request


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


class Decoder:
    def __init__(self, endpoint, model, identity, cache, concurrency=8, post=None):
        self.endpoint, self.model, self.identity = endpoint, model, identity
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.concurrency, self.post = concurrency, post or self._post
        self.locks = {}

    def _post(self, body):
        request = urllib.request.Request(self.endpoint, data=canonical(body),
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=1800) as response:
                return json.load(response)
        except urllib.error.HTTPError as e:
            if e.code != 400:
                raise
            # llama.cpp answers 400 when a prompt does not fit the slot's context (tools/server, "exceeds the
            # available context size"); on a training panel some problems are that long. The reply is then
            # empty, which the route reads as no answer, instead of the whole run dying (2026-10-21).
            detail = e.read().decode("utf-8", "replace")[:300]
            sys.stderr.write(f"server refused a request (400): {detail}\n")
            return {"choices": [{"message": {"content": ""}, "finish_reason": "length"}],
                    "usage": {"completion_tokens": 0}, "error": detail}

    def one(self, messages, max_new, temperature, top_p, stage):
        seed = int(hashlib.sha256(canonical([stage, messages])).hexdigest()[:8], 16) & 0x7fffffff
        body = {"model": self.model, "messages": messages, "max_tokens": max_new,
                "temperature": temperature, "top_p": top_p, "top_k": 0, "min_p": 0,
                "repeat_penalty": 1.0, "seed": seed, "stream": False,
                "chat_template_kwargs": {"enable_thinking": False}}
        key = hashlib.sha256(canonical([self.identity, body])).hexdigest()
        path = self.cache / f"{key}.json"
        with self.locks.setdefault(key, threading.Lock()):
            if path.exists():
                record = json.loads(path.read_text())
                if record["identity"] != self.identity or record["request"] != body:
                    raise ValueError("cached request identity changed")
                response = record["response"]
            else:
                response = self.post(body)
            choices = response.get("choices", [])
            if len(choices) != 1:
                raise ValueError("model server must return exactly one choice")
            choice = choices[0]
            content = choice.get("message", {}).get("content")
            if not isinstance(content, str) or choice.get("finish_reason") not in ("stop", "length"):
                raise ValueError("model server returned an incomplete or invalid answer")
            tokens = response.get("usage", {}).get("completion_tokens")
            if not isinstance(tokens, int) or tokens < 0 or tokens > max_new:
                raise ValueError("model server returned an invalid completion-token count")
            if not path.exists():
                record = {"identity": self.identity, "request": body, "response": response}
                with tempfile.NamedTemporaryFile(dir=self.cache, mode="w", delete=False) as f:
                    json.dump(record, f, ensure_ascii=False)
                    temporary = Path(f.name)
                temporary.replace(path)
            return content, choice["finish_reason"] == "stop", tokens

    def decode(self, _model, _tokenizer, conversations, max_new, temperature, top_p, seed=None):
        with ThreadPoolExecutor(max_workers=self.concurrency) as workers:
            return list(workers.map(
                lambda messages: self.one(messages, max_new, temperature, top_p, seed), conversations))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--identity", required=True, help="model checksum and server revision")
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("route_args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    route_args = args.route_args[1:] if args.route_args[:1] == ["--"] else args.route_args
    if not route_args or args.concurrency < 1:
        parser.error("give spec_first arguments after -- and a positive concurrency")
    selection = argparse.ArgumentParser(add_help=False)
    selection.add_argument("--tag", required=True)
    selection.add_argument("--ids-file", required=True, type=Path)
    selected, _ = selection.parse_known_args(route_args)
    ids = selected.ids_file.read_text().split()
    if not ids or len(ids) != len(set(ids)):
        parser.error("the problem panel must be nonempty and contain no duplicate ids")
    engine = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(engine))
    import spec_first
    import student_generate

    sources = sorted(set(engine.glob("*.py")) | set((engine / "verifiers").rglob("*.py")))
    sources += sorted((engine.parent / "nl/data").glob("*.gz"))
    protocol = {"schema": 1, "decoder": "llama.cpp-Q8_0", "model": args.model,
                "identity": args.identity, "route_args": route_args,
                "panel_sha256": hashlib.sha256(selected.ids_file.read_bytes()).hexdigest(),
                "sources": {str(p.relative_to(engine.parent)): hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in sources},
                "driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "seed_rule": "sha256(canonical_json([stage, messages]))[:8] & 0x7fffffff"}
    protocol_path = args.cache / "protocol.json"
    decoder = Decoder(args.endpoint, args.model, args.identity, args.cache, args.concurrency)
    lock = (args.cache / "run.lock").open("a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit("another evaluation process holds this cache") from None
    if protocol_path.exists() and json.loads(protocol_path.read_text()) != protocol:
        raise SystemExit("evaluation protocol changed; use a fresh output and cache")
    protocol_path.write_text(json.dumps(protocol, indent=2) + "\n")
    original = student_generate.load, student_generate.decode, student_generate.problem_seed
    student_generate.load = lambda *_args, **_kwargs: (None, None)
    student_generate.decode = decoder.decode
    # Retain the stage salt here; Decoder combines it with each individual prompt.
    student_generate.problem_seed = lambda stage, _first_id: stage
    try:
        result = spec_first.main(["--model", args.model, *route_args])
    finally:
        student_generate.load, student_generate.decode, student_generate.problem_seed = original
    if result == 0:
        directory = spec_first.se.outdir(selected.tag)
        summary = json.loads((directory / "spec_first.json").read_text())
        if summary["problems"] != len(ids) or set(summary["per_problem"]) != set(ids):
            raise RuntimeError("the route did not account for every requested problem")
        taken = {tid for tid, state in summary["per_problem"].items() if state.get("taken") is not None}
        raw_ids = {p.stem for p in (directory / "raw").glob("*.json")}
        if summary["answered"] != len(taken) or raw_ids != taken:
            raise RuntimeError("the saved answer set is incomplete or contains foreign problems")
        (args.cache / "completed.json").write_text(json.dumps(protocol, indent=2) + "\n")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
