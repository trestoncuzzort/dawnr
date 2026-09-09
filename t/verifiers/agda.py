"""t.verifiers.agda: the seventh kernel's adapter; the LOWERING IS PARKED.

Stated first, because it is the point: Agda's stdlib has no omega/lia-class
decision procedure, so a MECHANICAL proof-synthesis template for t's LIA
fragment does not fall out of the language the way it did for Lean and Rocq.
Emitting hand-plumbed lemma chains per spec shape is a design problem, not a
lowering, and pretending otherwise would mint exactly the unwitnessed
artifacts t exists to refuse. So: the adapter below is real and measured;
`lower_agda.py` does not exist yet; ROADMAP.md carries the parked gate.

Verdict classification (Agda 2.8.0 arm64 binary, measured on this machine
2026-08-31: exit 0 accepted, exit 42 for EVERY failure, discriminated by
the stable bracketed error names):
  banned token in SOURCE (postulate / TERMINATING pragma /
      a missing --safe would be a lowering bug)             -> VACUOUS
  [SafeFlag...]                                             -> VACUOUS
  [ParseError] / [ModuleNameDoesntMatchFileName] /
      [ScopeError...] / unresolved names                    -> MALFORMED
  type-check errors ([UnequalTerms], ...)                   -> REFUTED
  wall backstop                                             -> TIMEOUT
--safe is ALWAYS passed; the module/filename convention is handled the way
GNAT's and Rocq's were, so the adapter owns the on-disk name (module T_Unit,
file T_Unit.agda in a scratch dir); the witness hash binds to source bytes.
Budget: RTS heap cap plus the wall backstop; no per-proof deterministic
counter exists at the CLI.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

from . import Outcome, Result, sha256_file, run_tree
from .discover import find, missing

AGDA = find("T_AGDA", ['agda'], [".local/agda/**/agda", ".cabal/bin/agda"])
_AGDA_WHY = missing("agda", "T_AGDA", ['agda'], [".local/agda/**/agda", ".cabal/bin/agda"])
WALL_S = 180
BANNED = re.compile(r"\bpostulate\b|\{-#\s*TERMINATING", re.IGNORECASE)
MALFORMED_MARKS = ("[ParseError]", "[ModuleNameDoesntMatchFileName]",
                   "[ScopeError", "[NotInScope")
VACUOUS_MARKS = ("[SafeFlag",)


def version() -> str:
    if not AGDA:
        raise SystemExit(_AGDA_WHY)
    p = subprocess.run([str(AGDA), "--version"], capture_output=True, text=True)
    return p.stdout.strip().splitlines()[0]


def verify(path: Path, budget: int = 0) -> Result:
    src_hash = sha256_file(path)
    src = path.read_text(encoding="utf-8")
    banned = BANNED.findall(src)
    t0 = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="t-agda-", ignore_cleanup_errors=True) as td:
        unit = Path(td) / "T_Unit.agda"
        unit.write_text(re.sub(r"^module\s+\S+", "module T_Unit", src,
                               count=1, flags=re.MULTILINE)
                        if src.lstrip().startswith("module")
                        else src, encoding="utf-8")
        try:
            p = run_tree([str(AGDA), "--safe", "T_Unit.agda"],
                               capture_output=True, text=True,
                               timeout=WALL_S, cwd=td)
        except subprocess.TimeoutExpired:
            return Result("agda", version(), src_hash, Outcome.TIMEOUT,
                          wall_ms=int((time.monotonic() - t0) * 1000),
                          budget="wall backstop only", error="backstop fired")
    wall = int((time.monotonic() - t0) * 1000)
    out = p.stdout + p.stderr

    if banned:
        outcome = Outcome.VACUOUS
    elif any(m in out for m in VACUOUS_MARKS):
        outcome = Outcome.VACUOUS
    elif p.returncode == 0:
        outcome = Outcome.VERIFIED
    elif any(m in out for m in MALFORMED_MARKS):
        outcome = Outcome.MALFORMED
    else:
        outcome = Outcome.REFUTED   # type-check failure: [UnequalTerms] etc.
    return Result("agda", version(), src_hash, outcome,
                  ok=outcome == Outcome.VERIFIED, exit_code=p.returncode,
                  wall_ms=wall, budget="wall backstop only",
                  error="" if outcome != Outcome.TOOL_ERROR else out[-400:],
                  extras={"banned_tokens": banned[:5]})
