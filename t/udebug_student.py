#!/usr/bin/env python3
"""t/udebug_student.py -- a local model's answers to judge questions, in the teacher's sample layout.

    python3 t/udebug_student.py --questions t/out/udebug/heldout-questions.jsonl --tag base-q35-4b \\
        --backend hf --model t/out/gcp-base --max-new 1024 --batch 8
    python3 t/udebug_student.py --questions ... --tag student-x --backend server --endpoint http://127.0.0.1:8080/v1/chat/completions

Each question (t/udebug_rows.py --heldout-out: the problem, its tests directory and the teacher's own
prompt messages) is answered once, greedily, under the model's chat template with thinking off, the
rendering t/student_sft.py trained on. The reply is written exactly as t/udebug_teacher.py writes a
sample (<out>/<judge>-<id>/s1/p<id>.py and record.json), so t/udebug_gate.py grades a student the same
way it grades a teacher: every stored case under the memory cap, `proof: none` on every row.

Backends: `hf` loads the model with t/student_generate.py's loader and decodes in batches on the local
card; `server` posts to an OpenAI-compatible chat endpoint (llama.cpp's llama-server, --jinja) and reads
choices[0].message.content. A question whose record.json exists is skipped, so a stopped run resumes.
"""
from __future__ import annotations
import argparse
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import udebug_teacher  # noqa: E402


def read_questions(path: Path, limit: int) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows[:limit] if limit else rows


def sample_dir(out: Path, q: dict) -> Path:
    judge, ident = q["problem"].split("/", 1)
    return out / f"{judge}-{ident}" / "s1"


def write_sample(d: Path, q: dict, reply: str, in_tok: int, out_tok: int, wall: float, done_reason: str,
                 model: str, provider: str, endpoint: str, tag: str, max_new: int) -> bool:
    judge, ident = q["problem"].split("/", 1)
    prog, _ = udebug_teacher.extract(reply, "python")
    d.mkdir(parents=True, exist_ok=True)
    if prog is not None:
        (d / f"p{ident}.py").write_text(prog.rstrip() + "\n", encoding="utf-8")
    record = {"judge": judge, "id": ident, "title": q.get("title"), "tests_dir": q["tests_dir"],
              "model": model, "provider": provider, "endpoint": endpoint, "tag": tag,
              "prompt_version": "student", "target": "python", "sample_index": 1, "num_samples": 1,
              "options": {"temperature": 0.0, "max_tokens": max_new, "note": "greedy, thinking off"},
              "messages": q["prompt"], "reply": reply, "prompt_tokens": in_tok, "reply_tokens": out_tok,
              "wall_s": round(wall, 3), "done_reason": done_reason, "fences": {"python": prog is not None}}
    (d / "record.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    return prog is not None


def run_hf(todo: list[tuple[dict, Path]], a, summary: dict) -> None:
    import student_generate
    model, tokenizer = student_generate.load(a.model)
    for start in range(0, len(todo), a.batch):
        chunk = todo[start:start + a.batch]
        t0 = time.monotonic()
        replies = student_generate.decode(model, tokenizer, [q["prompt"] for q, _ in chunk], a.max_new, 0.0)
        wall = (time.monotonic() - t0) / max(1, len(chunk))
        for (q, d), (text, stopped, tokens) in zip(chunk, replies):
            fenced = write_sample(d, q, text, 0, tokens, wall, "stop" if stopped else "length",
                                  a.model, "transformers", "", a.tag, a.max_new)
            summary["answered"] += 1
            summary["fenced"] += int(fenced)
            summary["reply_tokens"] += tokens
            summary["hit_cap"] += int(not stopped)
        print(f"{min(start + a.batch, len(todo))}/{len(todo)} answered, {summary['fenced']} with a python fence, "
              f"{summary['hit_cap']} at the token cap", flush=True)


def run_server(todo: list[tuple[dict, Path]], a, summary: dict) -> None:
    def one(item):
        q, d = item
        body = json.dumps({"model": a.tag, "messages": q["prompt"], "temperature": 0.0, "max_tokens": a.max_new,
                           "chat_template_kwargs": {"enable_thinking": False}}).encode()
        req = urllib.request.Request(a.endpoint, data=body, headers={"Content-Type": "application/json"})
        t0 = time.monotonic()
        with urllib.request.urlopen(req, timeout=a.timeout) as r:
            j = json.load(r)
        wall = time.monotonic() - t0
        choice = j["choices"][0]
        usage = j.get("usage", {})
        return q, d, choice["message"].get("content") or "", usage.get("prompt_tokens", 0), \
            usage.get("completion_tokens", 0), wall, choice.get("finish_reason", "")

    with ThreadPoolExecutor(max_workers=a.concurrency) as pool:
        for q, d, text, in_tok, out_tok, wall, reason in pool.map(one, todo):
            fenced = write_sample(d, q, text, in_tok, out_tok, wall, reason, a.model or a.tag, "llama-server",
                                  a.endpoint, a.tag, a.max_new)
            summary["answered"] += 1
            summary["fenced"] += int(fenced)
            summary["reply_tokens"] += out_tok
            summary["hit_cap"] += int(reason == "length")
            if summary["answered"] % 10 == 0:
                print(f"{summary['answered']}/{len(todo)} answered, {summary['fenced']} fenced, "
                      f"{summary['hit_cap']} at the cap", flush=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--questions", required=True, type=Path)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out", default="", help="default t/out/udebug/student-<tag>")
    ap.add_argument("--backend", choices=("hf", "server"), default="hf")
    ap.add_argument("--model", default="", help="hf: a merged model directory; server: the name written to the record")
    ap.add_argument("--endpoint", default="http://127.0.0.1:8080/v1/chat/completions")
    ap.add_argument("--max-new", type=int, default=1024)
    ap.add_argument("--batch", type=int, default=8, help="hf: conversations decoded together")
    ap.add_argument("--concurrency", type=int, default=4, help="server: requests in flight")
    ap.add_argument("--timeout", type=float, default=1800.0, help="server: seconds per request")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)
    if a.backend == "hf" and not a.model:
        ap.error("--backend hf needs --model")
    out = Path(a.out) if a.out else HERE / "out" / "udebug" / f"student-{a.tag}"
    out.mkdir(parents=True, exist_ok=True)
    questions = read_questions(a.questions, a.limit)
    todo = [(q, sample_dir(out, q)) for q in questions]
    todo = [(q, d) for q, d in todo if not (d / "record.json").is_file()]
    print(f"{len(questions)} questions, {len(todo)} to answer (resumed ones skipped)", flush=True)
    summary = {"tag": a.tag, "backend": a.backend, "model": a.model, "questions": len(questions),
               "answered": 0, "fenced": 0, "hit_cap": 0, "reply_tokens": 0, "max_new": a.max_new,
               "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    t0 = time.monotonic()
    if todo:
        (run_hf if a.backend == "hf" else run_server)(todo, a, summary)
    summary["wall_s"] = round(time.monotonic() - t0, 1)
    summary["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
