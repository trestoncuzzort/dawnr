#!/usr/bin/env python3
"""provenance.py — the identity two banked replicates must share before pooling.

EXTRACTED FROM ruler_noise.py, which now imports it from here. Nothing about the
rule changed; where it lives did. ruler_noise.py cannot be imported without a
pinned verifier (it pulls in dataset_gate, which SystemExits at import when
neither .venv-train nor SRLM_VERIFY_PY resolves), and analyze_run1.py is a
CPU-only re-scoring script that must keep running on a bare interpreter. Two
copies of a pooling key is the one outcome that must not happen — a copy is
correct in its own file and wrong the moment the two drift, which is the same
lesson venv_guard.py and task_bank.py were extracted for.

Stdlib only, and deliberately no imports from this package, so importing it
costs nothing and drags nothing in.
"""
from __future__ import annotations

__all__ = ["UNPINNED", "is_pinned", "verifier_key"]

# The version string recorded for rows banked before the verifier was pinned
# (section 71). It is a real, distinct key — not a missing value to be filled in
# — because "we do not know which interpreter scored this" is exactly the state
# that must never be pooled with a known one.
UNPINNED = "pre-pin/unrecorded"


def verifier_key(rec: dict) -> tuple:
    """The identity two replicates must share before they may be pooled.

    Section 71 pooled on the interpreter VERSION alone. That is not sufficient:
    two hosts running the same CPython under different operating systems record
    the same string and were silently poolable -- see
    docs/port-2026-08-24/RED-WITNESS-D-POOLING-KEY.txt, where 18 banked rows read
    3.12.10 from a Windows host and a Linux host would have matched them.

    Rows banked before this change carry no `platform`, so it is backfilled from
    the recorded executable path: a drive letter or a backslash is unambiguous.
    """
    v = rec.get("verifier") or {}
    ver = v.get("version", UNPINNED)
    plat = v.get("platform")
    if plat is None:
        exe = v.get("executable", "") or ""
        plat = "win32" if ("\\" in exe or exe[1:3] == ":\\") else "unknown"
    return (ver, plat)


def is_pinned(key: tuple) -> bool:
    """True when the key names an interpreter that was actually recorded."""
    return key[0] != UNPINNED
