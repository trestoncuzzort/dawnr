#!/usr/bin/env python3
"""review_sweep.py: a frontier-model review of every engine module, one call per file, findings as JSON for triage.

    python3 t/review_sweep.py --model gpt-6-astra --out t/out/review-20261013 --paths 't/*.py' 'locallm/*.py' \\
        --exclude 'test_*' --concurrency 6 --reasoning-effort high --cap-usd 300

Each module is sent with its test file (same stem) and a reviewer contract: report only defects that a concrete
input or state turns into wrong output, a crash, a false verdict or a silent acceptance; cite the line; give the
minimal failing test. Style is out of scope. The reply is JSON; it is stored as a finding list per file for a human
triage that reproduces each claim before anything is changed (every fix still needs its own test and source).
Calls go through udebug_teacher.openai_call (github.com/openai/openai-openapi) and are priced per million tokens
for a running estimate against --cap-usd; nothing here edits code.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import fnmatch
import glob
import json
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import udebug_teacher as ut  # noqa: E402

CONTRACT = """You are reviewing one Python module of a formal-verification engine (the `t` language: a specification
language lowered into Dafny, Verus, SPARK, Frama-C, Lean 4, Rocq and F*; verdicts come from those kernels; a
proof counts only when the kernel also refutes a one-edit twin). The code must never report a verdict the kernel
did not give, never weaken a specification, and must refuse by name what it cannot lower.

Report DEFECTS only: a concrete input, task or state that makes the module produce wrong output, crash, return a
false verdict, accept something it should refuse, or lower a construct to something with a different meaning.
For each one give: the line number, the function, the severity (critical = a false proof or a false refutation
can result; high = wrong output or crash on a realistic input; medium = wrong on an edge the tests do not cover),
your confidence (0 to 1), the claim in one sentence, the input or state that triggers it, what the code does and
what it should do, and a minimal failing test as Python (unittest or a plain function) that would turn red today.

Do not report style, naming, performance, missing docstrings, or hypotheticals you cannot ground in the code
shown. If the module has no defects you can ground, return an empty list. Answer with JSON only:
{"findings": [{"line": int, "function": str, "severity": "critical|high|medium", "confidence": float,
"claim": str, "trigger": str, "actual": str, "expected": str, "test": str}]}"""


def pair_test(path: Path) -> Path | None:
    cand = path.with_name("test_" + path.name)
    return cand if cand.is_file() else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--paths", nargs="+", required=True, help="globs of modules to review")
    ap.add_argument("--exclude", nargs="*", default=["test_*", "conftest.py"], help="basename patterns to skip")
    ap.add_argument("--concurrency", type=int, default=6)
    ap.add_argument("--reasoning-effort", default="high")
    ap.add_argument("--max-tokens", type=int, default=32768)
    ap.add_argument("--max-source-chars", type=int, default=700_000, help="larger files are split by top-level chunks")
    ap.add_argument("--price-in-per-mtok", type=float, default=10.0)
    ap.add_argument("--price-out-per-mtok", type=float, default=50.0)
    ap.add_argument("--cap-usd", type=float, default=300.0)
    ap.add_argument("--openai-key-file", default="~/.config/openai/api_key")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)

    files = []
    for g in a.paths:
        for f in sorted(glob.glob(g)):
            p = Path(f)
            if any(fnmatch.fnmatch(p.name, pat) for pat in a.exclude):
                continue
            files.append(p)
    if a.limit:
        files = files[:a.limit]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    key = ut.openai_key(a.openai_key_file)
    ledger = {"in": 0, "out": 0, "usd": 0.0, "calls": 0, "stop": False}
    lock = threading.Lock()
    todo = [p for p in files if not (out / (p.as_posix().replace("/", "__") + ".json")).is_file()]
    print(f"{len(files)} modules, {len(todo)} to review", flush=True)

    def chunks(src: str) -> list[str]:
        if len(src) <= a.max_source_chars:
            return [src]
        parts, cur = [], []
        for line in src.splitlines(keepends=True):
            if line.startswith(("def ", "class ")) and sum(map(len, cur)) > a.max_source_chars // 2:
                parts.append("".join(cur)); cur = []
            cur.append(line)
        if cur:
            parts.append("".join(cur))
        return parts

    def one(p: Path) -> None:
        if ledger["stop"]:
            return
        src = p.read_text(encoding="utf-8", errors="replace")
        test = pair_test(p)
        test_src = test.read_text(encoding="utf-8", errors="replace")[:120_000] if test else ""
        findings, usage, t0 = [], [], time.monotonic()
        for i, chunk in enumerate(chunks(src)):
            user = (f"Module `{p}`" + (f" (part {i + 1}, lines continue from the previous part)" if i else "")
                    + ":\n\n```python\n" + chunk + "\n```\n\n"
                    + (f"Its tests, `{test}` (for what is already covered):\n\n```python\n{test_src}\n```\n\n" if test_src and i == 0 else "")
                    + "Review it under the contract. JSON only.")
            messages = [{"role": "system", "content": CONTRACT}, {"role": "user", "content": user}]
            try:
                reply, tin, tout, stop = ut.openai_call(key, a.model, messages, a.max_tokens, 1.0, a.reasoning_effort)
            except Exception as e:  # noqa: BLE001 -- the sweep records the failure and goes on
                findings.append({"error": f"{type(e).__name__}: {str(e)[:300]}", "chunk": i})
                continue
            usage.append({"in": tin, "out": tout, "finish": stop})
            text = reply.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            try:
                got = json.loads(text)
                for f in got.get("findings", []):
                    f["chunk"] = i
                    findings.append(f)
            except ValueError:
                findings.append({"error": "reply was not JSON", "chunk": i, "reply_head": reply[:400]})
            with lock:
                ledger["in"] += tin; ledger["out"] += tout; ledger["calls"] += 1
                ledger["usd"] = ledger["in"] / 1e6 * a.price_in_per_mtok + ledger["out"] / 1e6 * a.price_out_per_mtok
                if ledger["usd"] >= a.cap_usd:
                    ledger["stop"] = True
        rec = {"module": str(p), "test": str(test) if test else None, "model": a.model, "reasoning_effort": a.reasoning_effort,
               "lines": src.count("\n") + 1, "usage": usage, "wall_s": round(time.monotonic() - t0, 1), "findings": findings}
        (out / (p.as_posix().replace("/", "__") + ".json")).write_text(json.dumps(rec, indent=1), encoding="utf-8")
        real = [f for f in findings if "error" not in f]
        print(f"{p}: {len(real)} findings ({sum(1 for f in real if f.get('severity') == 'critical')} critical) "
              f"in {rec['wall_s']}s; ${ledger['usd']:.2f} so far", flush=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, a.concurrency)) as ex:
        list(ex.map(one, todo))
    summary = {"model": a.model, "modules": len(files), "reviewed": ledger["calls"], "usd_estimate": round(ledger["usd"], 2),
               "stopped_at_cap": ledger["stop"]}
    (out / "SUMMARY.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
