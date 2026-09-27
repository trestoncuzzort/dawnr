"""checkpoint_bench.py: CPU decode latency and peak memory for one real checkpoint.

    python3 locallm/checkpoint_bench.py --model <dir> --out bench.json [--tokens 64] [--repeats 3]

bench_decode.py (2026-09-19) already measures a synthetic GPTConfig's cached-vs-uncached decode
speed to check the KV cache does no extra work; this measures the one number a report card
needs about an actual checkpoint on the machine reading it -- tokens/second and peak resident
memory generating its own text, greedy, forced onto the CPU, with the same load-average
bracketing bench_decode.py uses (torch.set_num_threads, os.getloadavg -- reused from there
rather than re-measured a second way) so a number taken on a loaded shared machine is not
silently treated as clean. This reuses bench_decode.py's processor_name()/load_average()
instead of redefining them.

Peak memory is resident set size, not CUDA memory: resource.getrusage(RUSAGE_SELF).ru_maxrss
(docs.python.org/3/library/resource.html, "ru_maxrss: ... in kilobytes [on Linux]... the value
will be in bytes on some other Unix-like systems"; getrusage(2) confirms bytes on Darwin/BSD),
the portable measurement the standard library itself documents. There is no CUDA figure here
because this bench never asks for a GPU device -- the report's "CPU latency and memory"
section is deliberately the number a person's own machine gives it, offline, not a cluster's.
"""
from __future__ import annotations

import argparse
import json
import platform
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def peak_rss_bytes() -> int:
    """ru_maxrss is kilobytes on Linux, bytes on Darwin/BSD (getrusage(2)); Windows has no
    resource module, and the caller sees that ImportError rather than a wrong number."""
    ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return ru * 1024 if platform.system() == "Linux" else ru


def run(model_dir: Path, prompt: str, tokens: int, repeats: int, threads: int | None) -> dict:
    import torch
    from bench_decode import load_average, processor_name
    from checkpoint import load_checkpoint

    if threads is not None:
        torch.set_num_threads(threads)
    model, tok, _cfg = load_checkpoint(model_dir, device="cpu")
    ids = torch.tensor([tok.encode(prompt)], dtype=torch.long)
    runs = []
    with torch.no_grad():
        model.generate(ids, 1, temperature=0, use_cache=True)  # warm up: exclude first-call setup cost
        for repeat in range(repeats):
            load = load_average()
            start = time.perf_counter()
            model.generate(ids, tokens, temperature=0, use_cache=True)
            elapsed = time.perf_counter() - start
            runs.append({"repeat": repeat, "seconds": elapsed, "tokens_per_second": tokens / elapsed,
                        "ms_per_token": 1000 * elapsed / tokens, "load_1min": load[0] if load else None})
    mid = len(runs) // 2
    return {"model": str(model_dir), "parameters": model.total_params(), "prompt_tokens": ids.size(1),
            "new_tokens": tokens, "threads": torch.get_num_threads(), "processor": processor_name(),
            "torch": torch.__version__, "python": platform.python_version(), "runs": runs,
            "median_tokens_per_second": sorted(r["tokens_per_second"] for r in runs)[mid],
            "median_ms_per_token": sorted(r["ms_per_token"] for r in runs)[mid],
            "peak_rss_bytes": peak_rss_bytes(), "load_average_end": load_average()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--prompt", default="function to ")
    ap.add_argument("--tokens", type=int, default=64)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--threads", type=int, default=None, help="torch.set_num_threads; default: torch's own choice")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.tokens < 1 or a.repeats < 1:
        ap.error("--tokens and --repeats must be positive")
    result = run(a.model, a.prompt, a.tokens, a.repeats, a.threads)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "runs"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
