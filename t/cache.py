"""t/cache.py: the verdict cache t/tlib.py reads and writes.

ROADMAP 15.1: an editor re-verifying an unchanged task must cost no kernel
run. The key is sha256 of the LOWERED source bytes, the kernel name, the
kernel's own version string, the budget, adapter fingerprint and repetition
count, so a task whose body is unchanged but whose lowering, kernel, or budget
changed gets a fresh key
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
import tempfile

from verifiers import Outcome

HERE = Path(__file__).resolve().parent
DEFAULT_CACHE_DIR = HERE / "out" / "cache"
CACHEABLE = frozenset({Outcome.VERIFIED, Outcome.REFUTED, Outcome.VACUOUS,
                       Outcome.MALFORMED, Outcome.UNPROVED})
_ADAPTER_FP: dict[str, str] = {}


def adapter_fingerprint(kernel: str) -> str:
    """Hash the adapter, execution machinery and discovery policy once per process."""
    if kernel not in _ADAPTER_FP:
        h = hashlib.sha256()
        for name in (f"{kernel}.py", "__init__.py", "discover.py"):
            p = HERE / "verifiers" / name
            try:
                h.update(p.read_bytes())
            except OSError as exc:
                h.update(f"UNREADABLE {name} {exc}".encode("utf-8"))
            h.update(b"\0")
        _ADAPTER_FP[kernel] = h.hexdigest()
    return _ADAPTER_FP[kernel]


def verdict_key(source: str, kernel: str, version: str, budget, flake: int) -> str:
    """A result depends on the adapter's interpretation and the requested repeats."""
    return key_for(source, kernel, version, budget,
                   extra=f"adapter={adapter_fingerprint(kernel)};flake={flake}")


def key_for(source: str, kernel: str, kernel_version: str, budget,
            extra: str = "") -> str:
    """sha256 over the lowered source, the kernel, its version, and the
    budget -- exactly the four things ROADMAP 15.1 names as what an
    unchanged verdict depends on.

    `extra` is anything ELSE a caller knows the verdict depends on, folded
    into the same key: both verdict drivers pass the sha256 of the adapter
    modules that turn a kernel's output into an Outcome, plus the flake n,
    because that driver runs while t/verifiers/* is edited and an edited
    adapter can read the same kernel output as a different Outcome. Empty
    by default for callers outside the verdict drivers. Legacy library keys
    without this extra identity are no longer reused by tlib."""
    h = hashlib.sha256()
    for part in (source, kernel, kernel_version, str(budget)):
        h.update(part.encode("utf-8"))
        h.update(b"\0")
    if extra:
        h.update(extra.encode("utf-8"))
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
        data = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if (not isinstance(data, dict) or not isinstance(data.get("outcome"), str)
            or data["outcome"] not in CACHEABLE
            or not isinstance(data.get("backend_version"), str)
            or not data["backend_version"]):
        return None
    return data


def write(kernel: str, key: str, data: dict, cache_dir: Path = DEFAULT_CACHE_DIR) -> None:
    """Write-once-visible: build the full JSON off to the side, then
    os.replace it into place, so a concurrent reader (another editor
    session, or a table run sharing the same out/cache by coincidence of
    task+kernel+version+budget) never observes a half-written file."""
    p = path_for(kernel, key, cache_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         prefix=f".{p.name}.", suffix=".tmp",
                                         dir=p.parent, delete=False) as stream:
            tmp = Path(stream.name)
            json.dump(data, stream, sort_keys=True, indent=2)
        os.replace(tmp, p)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
