"""t/cache.py: the verdict cache t/tlib.py reads and writes.

ROADMAP 15.1: an editor re-verifying an unchanged task must cost no kernel
run. The key is sha256 of the LOWERED source bytes, the kernel name, the
kernel's own version string, and the budget used, so a task whose body is
unchanged but whose lowering, kernel, or budget changed gets a fresh key
rather than a stale hit. One JSON file per key, written only after a
completed n-of-3 flake_check agreement (t/tlib.py's job, not this
module's): a cache entry is never partial or provisional by construction,
because nothing provisional is ever written here.

Layout: out/cache/<kernel>/<key>.json, one file per (kernel, key) so two
kernels lowering the same task never collide and a budget change never
overwrites the entry a different budget produced.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_CACHE_DIR = HERE / "out" / "cache"


def key_for(source: str, kernel: str, kernel_version: str, budget) -> str:
    """sha256 over the lowered source, the kernel, its version, and the
    budget -- exactly the four things ROADMAP 15.1 names as what an
    unchanged verdict depends on."""
    h = hashlib.sha256()
    for part in (source, kernel, kernel_version, str(budget)):
        h.update(part.encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()


def path_for(kernel: str, key: str, cache_dir: Path = DEFAULT_CACHE_DIR) -> Path:
    return Path(cache_dir) / kernel / f"{key}.json"


def read(kernel: str, key: str, cache_dir: Path = DEFAULT_CACHE_DIR) -> dict | None:
    """The cached {"outcome": ..., "backend_version": ...} for this key, or
    None on a miss (absent file, or a file this process cannot parse --
    corrupt/partial is treated as a miss, never as evidence)."""
    p = path_for(kernel, key, cache_dir)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError):
        return None


def write(kernel: str, key: str, data: dict, cache_dir: Path = DEFAULT_CACHE_DIR) -> None:
    """Write-once-visible: build the full JSON off to the side, then
    os.replace it into place, so a concurrent reader (another editor
    session, or a table run sharing the same out/cache by coincidence of
    task+kernel+version+budget) never observes a half-written file."""
    p = path_for(kernel, key, cache_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, sort_keys=True, indent=2),
                   encoding="utf-8", newline="\n")
    os.replace(tmp, p)
