#!/usr/bin/env python3
"""t/python_beside.py -- a Python solution beside each question, kept only if it passes the question's
own tests in the sandbox (2026-10-01).

    python3 t/python_beside.py --model DIR --ids-file IDS --out python.jsonl              # a local student
    python3 t/python_beside.py --api openai --host 127.0.0.1:8101,127.0.0.1:8102 --name M \\
        --ids-file IDS --out python.jsonl                                                  # llama.cpp, transformers serve
    python3 t/python_beside.py --api ollama --host 127.0.0.1:11434 --name phi4-mini --ids-file IDS --out python.jsonl

The gate's specification stage (t/spec_gate.py) needs a second artifact that shares no text with
the `t` answer: Clover (arXiv:2310.17807) accepts generated code only when independently produced
artifacts agree, and compares code with code by outputs on inputs. This writes that artifact: the
question and its tests in the words the Python-first rows use (t/spec_first_rows.python_question),
one greedy attempt and then sampled ones at 0.7, the first reply whose fenced block passes every
test of the question in the sandbox (t/py_sandbox.py; HumanEval's harness is the shape,
github.com/openai/human-eval). Nothing is kept that fails a test, and model-written code is run
nowhere but the sandbox.

Rows: {"task_id", "code" (or null), "attempt", "attempts", "writer"}. A run resumes: ids already in
--out are skipped.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import py_sandbox                                               # noqa: E402
import spec_experiment as se                                    # noqa: E402
import spec_first                                               # noqa: E402
import spec_first_rows                                          # noqa: E402

TEMPERATURE, TOP_P = 0.7, 0.95


def _post(url: str, body: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def api_decode(api: str, hosts: list[str], name: str, extra: dict | None = None, timeout: float = 900.0, post=_post):
    """A `decode` with the shape spec_first.written_python expects, over one or several HTTP servers
    (a conversation goes to host i mod n; the servers answer in parallel). A request that fails is
    an empty reply: the attempt is spent and nothing is kept from it."""
    def one(job):
        i, messages, temperature, seed, max_new = job
        host = hosts[i % len(hosts)]
        try:
            if api == "ollama":
                body = {"model": name, "messages": messages, "stream": False, "think": False,
                        "options": {"temperature": temperature, "top_p": TOP_P, "seed": seed, "num_predict": max_new}}
                body["options"].update(extra or {})
                return post(f"http://{host}/api/chat", body, timeout)["message"]["content"] or ""
            body = {"model": name, "messages": messages, "temperature": temperature, "top_p": TOP_P, "seed": seed,
                    "max_tokens": max_new, **(extra or {})}
            return post(f"http://{host}/v1/chat/completions", body, timeout)["choices"][0]["message"]["content"] or ""
        except Exception:                                       # noqa: BLE001
            return ""

    def decode(conversations, temperature, salt, _first, max_new):
        jobs = [(i, c, temperature, salt, max_new) for i, c in enumerate(conversations)]
        with ThreadPoolExecutor(max_workers=max(1, len(hosts))) as pool:
            return [(text, True, 0) for text in pool.map(one, jobs)]
    return decode


def write(decode, ids: list[str], P: dict, out: Path, attempts: int, batch: int, max_new: int, writer: str) -> dict:
    """Append one row per problem to `out`, a chunk at a time, and return {"asked", "kept"}."""
    done = set()
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done.add(str(json.loads(line)["task_id"]))
    todo = [t for t in ids if t not in done]
    kept = 0
    with out.open("a", encoding="utf-8") as f:
        for start in range(0, len(todo), batch):
            chunk = todo[start:start + batch]
            python, counts = spec_first.written_python(decode, chunk, P, attempts, batch, max_new)
            for t in chunk:
                f.write(json.dumps({"task_id": int(t), "code": python.get(t), "attempt": counts[t]["python"],
                                    "attempts": counts[t]["python attempts"], "writer": writer}) + "\n")
            f.flush()
            kept += len(python)
            print(f"python_beside: {min(start + batch, len(todo))} of {len(todo)} asked, {kept} kept", flush=True)
    return {"asked": len(todo), "kept": kept}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", help="a local merged student directory (loads torch)")
    ap.add_argument("--api", choices=("openai", "ollama"))
    ap.add_argument("--host", help="host:port[,host:port...] for --api")
    ap.add_argument("--name", help="the model's name for --api")
    ap.add_argument("--extra", default="", help="JSON merged into each request (openai) or its options (ollama)")
    ap.add_argument("--ids-file", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--pool", choices=se.POOL_VERSIONS, default="v5")
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--max-new", type=int, default=768)
    a = ap.parse_args(argv)
    if bool(a.model) == bool(a.api):
        ap.error("give --model, or --api with --host and --name")
    if not py_sandbox.available():
        raise SystemExit("python_beside: bubblewrap is not installed; model-written code is not run without it")
    P = {str(k): v for k, v in se.pool(a.pool).items()}
    ids = [t for t in a.ids_file.read_text(encoding="utf-8").split() if t in P]
    if a.api:
        if not (a.host and a.name):
            ap.error("--api needs --host and --name")
        decode = api_decode(a.api, a.host.split(","), a.name, json.loads(a.extra) if a.extra else None)
        writer = f"{a.api}:{a.name}"
    else:
        import student_generate                                 # noqa: E402  (loads torch)
        model, tokenizer = student_generate.load(a.model)

        def decode(conversations, temperature, salt, first, max_new):
            return student_generate.decode(model, tokenizer, conversations, max_new, temperature, TOP_P,
                                           student_generate.problem_seed(salt, first))
        writer = str(a.model)
    r = write(decode, ids, P, a.out, a.attempts, a.batch, a.max_new, writer)
    total = sum(1 for line in a.out.read_text(encoding="utf-8").splitlines() if line.strip() and json.loads(line).get("code"))
    print(f"python_beside: {total} of {len(ids)} problems have a Python solution that passes their tests "
          f"({r['asked']} asked in this run)")
    return 0


if __name__ == "__main__":                                      # pragma: no cover
    raise SystemExit(main())
