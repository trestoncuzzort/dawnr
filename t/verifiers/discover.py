"""discover.py — find a kernel's binary without hardcoding one machine's paths.

Every adapter used to name a macOS/arm64 install location as its default:
`~/.local/verus/verus-arm64-macos/verus`, `gnatprove-aarch64-darwin-16.1.0-1`,
and so on. That works exactly on the machine those were installed on. Clone the
repository onto the Ubuntu box and t finds no kernel at all — not because the
kernels are absent, but because the adapter is looking somewhere that only
exists on a Mac.

Resolution order, most explicit first:
  1. the adapter's environment variable (T_VERUS_BIN, T_GNATPROVE, ...) —
     always wins, so a pinned install can be named exactly;
  2. PATH — the normal way a tool is found, and the way opam, elan, rustup and
     package managers all expect;
  3. glob patterns under $HOME for the tarball-style installs that never put
     anything on PATH.

`missing()` returns why nothing was found, so an absent kernel produces a
sentence rather than a stack trace — t/run_all.py prints it as ABSENT and
carries on with the kernels that are present. A kernel that cannot be found is
recorded, never silently skipped.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path


def find(env_var: str, names: list[str], globs: list[str] | None = None) -> str | None:
    """Resolve a kernel binary, or None. See module docstring for the order."""
    explicit = os.environ.get(env_var)
    if explicit:
        return explicit if Path(explicit).exists() else None
    for n in names:
        found = shutil.which(n)
        if found:
            return found
    for pattern in globs or []:
        # Windows binaries carry .exe, so a glob written for the POSIX name
        # ("dafny") would never match there; trying pattern + ".exe" costs
        # nothing on Linux, where no such file exists.
        variants = [pattern] if pattern.endswith(".exe") else [pattern, pattern + ".exe"]
        for pat in variants:
            for hit in sorted(Path.home().glob(pat)):
                if hit.is_file() and os.access(hit, os.X_OK):
                    return str(hit)
    return None


def missing(kernel: str, env_var: str, names: list[str], globs: list[str] | None = None) -> str:
    return (f"{kernel} not found. Looked at ${env_var}, then on PATH for "
            f"{', '.join(names)}"
            + (f", then under ~/ for {', '.join(globs)}" if globs else "")
            + f". Set {env_var} to the binary, or install it "
              f"(see tup/t/README.md).")
