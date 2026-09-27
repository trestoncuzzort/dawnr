#!/usr/bin/env python3
"""bench_int8.py — measured speed, memory and greedy-output agreement for
plain_generate.py's --quantize/--quantize-kv and quant_int8.py's
quantize_model_int8, on the included checkpoint.

    python3 bench_int8.py                # writes bench-int8-results-<date>.json

The predictions this checks were written and committed first, in
PREDICT-int8-quant-2026-09-27.md.

CPU only, by design: this is a 10.9M-parameter model and the point of int8 here
is small hardware, not the RTX 4080 (AMBITION.md: "to fit small hardware:
quantisation, distillation, mixture of experts | partly: runs with no PyTorch,
on a CPU"). The torch half needs torch (see checkpoint.py); the plain_generate
half runs identically whichever interpreter runs this script, which is itself
part of what plain_generate.py claims.
"""
from __future__ import annotations

import datetime
import json
import pathlib
import statistics
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

INCLUDED = HERE.parent / "t/runs/2026-09-17/home-4080/models/model-r4"
PROMPT = "task "
TOKENS = 200
REPEATS = 3
TIME_V = "/usr/bin/time"


def _checkpoint_present() -> bool:
    ckpt = INCLUDED / "ckpt.pt"
    return ckpt.is_file() and ckpt.stat().st_size > 1000


def _median_seconds(fn, repeats=REPEATS):
    times, result = [], None
    for _ in range(repeats):
        start = time.perf_counter()
        result = fn()
        times.append(time.perf_counter() - start)
    return statistics.median(times), result


def _peak_rss_kb(cmd: list[str]) -> int | None:
    """Maximum resident set size (KB) of one subprocess run, via GNU time -v.
    None if /usr/bin/time is not present here, rather than failing the run."""
    if not pathlib.Path(TIME_V).exists():
        return None
    proc = subprocess.run([TIME_V, "-v", *cmd], capture_output=True, text=True)
    for line in proc.stderr.splitlines():
        if "Maximum resident set size" in line:
            return int(line.rsplit(":", 1)[1].strip())
    return None


def _agreement(a: str, b: str) -> dict:
    """Position-by-position agreement between two greedy decodes of equal
    length from the same prompt: how much int8 actually changed, not assumed."""
    n = min(len(a), len(b))
    matches = sum(1 for x, y in zip(a[:n], b[:n]) if x == y)
    first_divergence = next((i for i in range(n) if a[i] != b[i]), n)
    return {"length_compared": n, "matches": matches,
           "agreement": matches / n if n else 1.0,
           "first_divergence": first_divergence}


def bench_plain() -> dict:
    import plain_generate as pg
    if not _checkpoint_present():
        return {"skipped": "included checkpoint not present (git lfs pull needed)"}
    configs = [("float32", False, False), ("quantize", True, False),
              ("quantize_kv", False, True), ("quantize+quantize_kv", True, True)]
    rows, baseline_text = {}, None
    for name, q, qkv in configs:
        model, tok, _ = pg.load_checkpoint(INCLUDED, quantize=q, quantize_kv=qkv)
        elapsed, text = _median_seconds(
            lambda m=model, t=tok: pg.sample(m, t, PROMPT, TOKENS, temperature=0))
        cli = [sys.executable, str(HERE / "plain_generate.py"), "--out", str(INCLUDED),
              "--prompt", PROMPT, "--tokens", str(TOKENS), "--temperature", "0"]
        if q:
            cli.append("--quantize")
        if qkv:
            cli.append("--quantize-kv")
        rows[name] = {
            "seconds_total_median_of_3": elapsed,
            "ms_per_token": elapsed / TOKENS * 1000,
            "weight_bytes": model.weight_bytes(),
            "peak_rss_kb_one_process": _peak_rss_kb(cli),
        }
        if baseline_text is None:
            baseline_text = text
        else:
            rows[name]["agreement_vs_float32"] = _agreement(baseline_text, text)
    float_bytes = rows["float32"]["weight_bytes"]
    for name in rows:
        rows[name]["weight_bytes_ratio"] = rows[name]["weight_bytes"] / float_bytes
    return rows


def bench_torch() -> dict:
    try:
        import torch  # noqa: F401
    except ImportError:
        return {"skipped": "torch not installed in this interpreter"}
    if not _checkpoint_present():
        return {"skipped": "included checkpoint not present (git lfs pull needed)"}
    import checkpoint
    import quant_int8 as qi

    model, tok, _ = checkpoint.load_checkpoint(INCLUDED, device="cpu")
    elapsed, text_float = _median_seconds(
        lambda: checkpoint.sample(model, tok, PROMPT, TOKENS, temperature=0, device="cpu"))
    float_bytes = qi.linear_weight_bytes(model)
    rows = {"float32": {"seconds_total_median_of_3": elapsed,
                        "ms_per_token": elapsed / TOKENS * 1000,
                        "linear_weight_bytes": float_bytes, "weight_bytes_ratio": 1.0}}

    model_q, tok_q, _ = checkpoint.load_checkpoint(INCLUDED, device="cpu")
    report = qi.quantize_model_int8(model_q)
    elapsed_q, text_quant = _median_seconds(
        lambda: checkpoint.sample(model_q, tok_q, PROMPT, TOKENS, temperature=0, device="cpu"))
    rows["quantized"] = {
        "seconds_total_median_of_3": elapsed_q,
        "ms_per_token": elapsed_q / TOKENS * 1000,
        "linear_weight_bytes": report.int8_bytes,
        "weight_bytes_ratio": report.ratio,
        "modules_quantized": report.modules_quantized,
        "agreement_vs_float32": _agreement(text_float, text_quant),
    }
    return rows


def main() -> None:
    results = {
        "date": datetime.date.today().isoformat(),
        "prompt": PROMPT, "tokens": TOKENS, "repeats": REPEATS,
        "checkpoint": str(INCLUDED.relative_to(HERE.parent)),
        "python": sys.version, "plain_generate": bench_plain(), "torch": bench_torch(),
    }
    out = HERE / "bench-int8-results-2026-09-27.json"
    out.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))
    print(f"\nwritten to {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
