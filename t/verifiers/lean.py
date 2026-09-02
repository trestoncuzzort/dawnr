r"""t.verifiers.lean — the fourth kernel, and the first proof assistant.

Shape difference, stated first: Lean has no SMT sidecar — "verified" means
THE KERNEL ACCEPTED A PROOF TERM. t's Lean lowering must therefore emit a
proof, and v0's fragment (linear integer arithmetic) makes that mechanical:
`omega` is a decision procedure for LIA living in core Lean, and its output
is still kernel-checked — the tactic is automation, never the authority.

VERIFIED requires POSITIVE EVIDENCE, not absence of complaints. Wave-1
audit (2026-08-31, lean 4.33.1) produced nine false VERIFIEDs against the
exit-0-plus-clean-audit rule: `@sorryAx _ false` applied directly (no
`sorry` word for the ban regex, no audit line to trip the allowlist), a
macro expanding to sorryAx, `/- x -/ axiom` dodging the `^\s*axiom` anchor,
`#guard_msgs (drop info)` swallowing the `#print axioms` output, a decoy
audit on `True` beside an unaudited false theorem, the empty file, a
comments-only file, T_LEAN_BIN=/bin/true (empty output = "clean audit"),
and a generated-shaped file with the proof replaced by sorryAx. All shared
one root: the audit was source-controlled, so withholding or suppressing it
looked identical to passing it.

The audit is now ADAPTER-CONTROLLED. verify() extracts every `theorem
<name>` from the comment-stripped source, appends to a temp copy a sentinel
theorem carrying a per-run random nonce plus its own `#print axioms` for
the sentinel and for each extracted name, and accepts only audit lines
printed AFTER the sentinel's own line (the nonce cannot be forged by the
source; lean prints messages in file order, and the appended commands are
last — measured 2026-08-31: a trailing `#guard_msgs (drop info) in` or
`#exit` in the source suppresses/absorbs appended commands, which then
FAILS this check rather than passing it). VERIFIED requires ALL of:
  - at least one `theorem` declaration in the source (zero -> MALFORMED);
  - no banned token (below) in the comment/string-stripped, NFKC-normalized
    source (-> VACUOUS, without consulting the kernel: the measured trap —
    in-file set_option overrides the CLI budget — is why the scan is first);
  - exit 0;
  - the nonce sentinel audit line present in the output (absent, or empty
    output, -> TOOL_ERROR: kernel evidence was not produced);
  - every extracted theorem has a post-sentinel audit line, and every audit
    line anywhere lists only {propext, Classical.choice, Quot.sound}.

REFUTED HAS EXACTLY ONE DOOR: the refutation certificate. Lean is a proof
assistant; a tactic that gives up ("omega could not prove", "unsolved
goals", "`grind` failed") reports its own incompleteness, never falsity.
The pre-2026-09-02 adapter minted REFUTED from those marks, and ground
truth fuzzing (ROADMAP 10.7) measured it refuting goals true by
construction; those marks now mint UNPROVED (stopped without countermodel,
without budget exhaustion). Positive evidence of falsity is a theorem
named exactly t_refutation_certificate: lower_lean.py emits it only when
lowering a twin with a measured witness, stating the spec instantiated at
that concrete witness, negated, and proved by kernel-checked ground
evaluation. REFUTED is minted if and only if that name is declared in the
source AND its post-sentinel audit line is present with only allowlisted
axioms (a failed proof is recorded via sorryAx and fails that test). A
certificate the kernel rejects mints UNPROVED, never REFUTED, and a file
declaring the certificate name can NEVER mint VERIFIED, so planting the
name in a real program only demotes it. Bans, sentinel and axiom audit
apply to certificate files unchanged.

Verdict classification (lean 4.33.1, measured on this machine 2026-08-31,
certificate rows and UNPROVED 2026-09-02):
  banned token in stripped source                            -> VACUOUS
  zero theorem declarations (empty/comments-only/junk)       -> MALFORMED
  "maxHeartbeats" / "deterministic timeout" in output        -> TIMEOUT
  t_refutation_certificate declared, audit clean             -> REFUTED
  t_refutation_certificate declared, rejected or unaudited   -> UNPROVED
  exit 0, sentinel + all audits present, allowlisted         -> VERIFIED
  exit 0, any audit lists a non-allowlisted axiom            -> VACUOUS
  exit 0, sentinel or a theorem's audit missing              -> TOOL_ERROR
  "omega could not prove" / "unsolved goals" / tactic-failed -> UNPROVED
  any other nonzero (parse/elaboration errors)               -> MALFORMED
UNPROVED is tested before MALFORMED because proof failures also exit 1.

Ban list (second line of defense; the positive audit above is what makes a
missed token unable to yield a false VERIFIED): sorry/sorryAx/admit,
native_decide + its axioms' names, the `axiom` keyword anywhere (not
line-anchored), macro/syntax/elab/notation machinery (an in-file macro can
expand to sorryAx), guard_msgs, set_option (covers maxHeartbeats and
debug.skipKernelTC), #eval/#exit/run_cmd/initialize/import (compiler-API
and elaboration-abort routes), variable (hypothesis smuggling into a
same-named theorem), implemented_by/extern (compiler-trust attributes).
None of these tokens appears in lower_lean.py output; the scan runs on
comment-stripped text so an honest comment mentioning "sorry" does not
trip it (wave-1 of1..of3 probes), and on NFKC-normalized text so fullwidth
homoglyphs of ASCII tokens do not evade it.

Budget: -DmaxHeartbeats, Lean's deterministic counter. Determinism is
architectural; flake_check re-measures it anyway because re-measuring is
cheap.
"""
from __future__ import annotations

import os
import re
import secrets
import subprocess
import tempfile
import time
import unicodedata
from pathlib import Path

from . import Outcome, Result, safe_text, sha256_file
from .discover import find, missing

LEAN = find("T_LEAN_BIN", ['lean'], [".elan/bin/lean"])
_LEAN_WHY = missing("lean", "T_LEAN_BIN", ['lean'], [".elan/bin/lean"])
DEFAULT_HEARTBEATS = 400_000
WALL_S = 180

BANNED = re.compile(
    r"\b(?:sorry|sorryAx|admit|native_decide|ofReduceBool|ofReduceNat|"
    r"trustCompiler|axiom|macro|macro_rules|syntax|elab|elab_rules|"
    r"notation|guard_msgs|set_option|run_cmd|run_elab|initialize|"
    r"builtin_initialize|import|variable|implemented_by|extern)\b"
    r"|#eval\b|#exit\b")
AXIOM_ALLOW = {"propext", "Classical.choice", "Quot.sound"}
# Incompleteness marks: a tactic that stopped, said nothing false. These
# minted REFUTED until 2026-09-02; "failed" matches nearly any error text,
# so the old name REFUTED_MARKS was the bug (ROADMAP 10.7), not just a
# misnomer. They mint UNPROVED now; REFUTED needs the certificate below.
UNPROVED_MARKS = ("omega could not prove", "unsolved goals", "failed")
# The single door to REFUTED: kernel-accepted proof that the spec fails at
# the measured witness. The name is the contract with lower_lean.py.
CERT_NAME = "t_refutation_certificate"

THEOREM_RE = re.compile(r"\btheorem\s+([A-Za-z_][A-Za-z0-9_']*)")
# '<name>' depends on axioms: [a, b] | '<name>' does not depend on any axioms
# (both forms measured verbatim, lean 4.33.1, 2026-08-31)
AUDIT_LINE = re.compile(
    r"'([^']+)' (?:depends on axioms: \[([^\]]*)\]"
    r"|does not depend on any axioms)")

_CODE_TOK = re.compile(r'--|/-|"')
_BLOCK_TOK = re.compile(r"/-|-/")
_STR_TOK = re.compile(r'\\.|"', re.DOTALL)


def _strip_comments_strings(text: str) -> str:
    """Blank line comments (--), nested block comments (/- -/), and string
    literal contents, each replaced by a single space so adjacent tokens
    cannot merge. Comments are stripped so a comment SAYING "sorry" is not
    a banned token (wave-1 of1..of3), while `/- x -/ axiom` leaves `axiom`
    in code position where the un-anchored ban regex sees it (wave-1 h3)."""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        m = _CODE_TOK.search(text, i)
        if not m:
            out.append(text[i:])
            break
        out.append(text[i:m.start()])
        tok = m.group()
        if tok == "--":
            j = text.find("\n", m.end())
            if j == -1:
                i = n
            else:
                out.append("\n")
                i = j + 1
        elif tok == "/-":
            depth, k = 1, m.end()
            while depth:
                m2 = _BLOCK_TOK.search(text, k)
                if not m2:
                    k = n
                    break
                depth += 1 if m2.group() == "/-" else -1
                k = m2.end()
            out.append(" ")
            i = k
        else:  # a string literal; \" escapes stay inside it
            k = m.end()
            while True:
                m3 = _STR_TOK.search(text, k)
                if not m3:
                    k = n
                    break
                k = m3.end()
                if m3.group() == '"':
                    break
            out.append(" ")
            i = k
    return "".join(out)


def version() -> str:
    if not LEAN:
        raise SystemExit(_LEAN_WHY)
    p = subprocess.run([str(LEAN), "--version"], capture_output=True, text=True)
    return p.stdout.strip().split(",")[0]


def verify(path: Path, budget: int = DEFAULT_HEARTBEATS) -> Result:
    src_hash = sha256_file(path)
    raw = safe_text(path)
    stripped = _strip_comments_strings(raw)
    # NFKC for the ban scan only: fullwidth/compatibility homoglyphs of the
    # ASCII tokens normalize onto them. Names are extracted from the
    # un-normalized text so `#print axioms <name>` resolves what was declared.
    banned = [m.group(0) for m in
              BANNED.finditer(unicodedata.normalize("NFKC", stripped))]
    theorems: list[str] = []
    for m in THEOREM_RE.finditer(stripped):
        if m.group(1) not in theorems:
            theorems.append(m.group(1))

    if banned:
        # scan verdict precedes the kernel: in-file set_option overrides the
        # CLI budget (the measured trap), so a banned file is never run.
        return Result("lean", version(), src_hash, Outcome.VACUOUS,
                      budget=f"heartbeats={budget}",
                      extras={"banned_tokens": banned[:5],
                              "theorems": theorems})
    if not theorems:
        # zero proof obligations: nothing a kernel could have discharged.
        return Result("lean", version(), src_hash, Outcome.MALFORMED,
                      budget=f"heartbeats={budget}",
                      error="no theorem declaration in source",
                      extras={"theorems": []})

    # adapter-controlled audit: sentinel nonce + one #print axioms per
    # theorem, appended to a temp copy; only output after the sentinel's own
    # audit line is trusted (the source cannot know the nonce).
    sentinel = f"t_audit_ok_{secrets.token_hex(8)}"
    audit = (f"\ntheorem {sentinel} : True := True.intro\n"
             f"#print axioms {sentinel}\n"
             + "".join(f"#print axioms {t}\n" for t in theorems))
    fd, tmp = tempfile.mkstemp(suffix=".lean", prefix="t_lean_audit_")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(path.read_bytes() + b"\n" + audit.encode("utf-8"))
        t0 = time.monotonic()
        try:
            p = subprocess.run([str(LEAN), f"-DmaxHeartbeats={budget}", tmp],
                               capture_output=True, text=True,
                               errors="replace", timeout=WALL_S)
        except subprocess.TimeoutExpired:
            return Result("lean", version(), src_hash, Outcome.TIMEOUT,
                          wall_ms=int((time.monotonic() - t0) * 1000),
                          budget=f"heartbeats={budget}",
                          error="wall backstop fired")
        wall = int((time.monotonic() - t0) * 1000)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass

    out = p.stdout + p.stderr
    audits = AUDIT_LINE.findall(out)
    ax_used = {a.strip() for _, axs in audits for a in axs.split(",")
               if a.strip()}
    bad_axioms = ax_used - AXIOM_ALLOW

    # trusted region: everything after the sentinel's own audit line.
    idx = out.find(f"{sentinel}' does not depend on any axioms")
    tail_names = ({nm for nm, _ in AUDIT_LINE.findall(out[idx:])}
                  if idx >= 0 else set())
    unaudited = [t for t in theorems
                 if not any(nm == t or nm.endswith("." + t)
                            for nm in tail_names)]

    error = ""
    if "maxHeartbeats" in out or "deterministic timeout" in out:
        outcome = Outcome.TIMEOUT
    elif CERT_NAME in theorems:
        # The only door to REFUTED. A file declaring the certificate name
        # can never mint VERIFIED, so this branch precedes the exit-0 path
        # on purpose: planting the name in a real program only demotes it.
        if idx < 0:
            outcome = Outcome.TOOL_ERROR
            error = ("adapter audit sentinel missing from tool output "
                     "(empty or suppressed); kernel evidence absent; "
                     f"output tail: {out[-200:]!r}")
        else:
            cert_lines = [
                axs for nm, axs in AUDIT_LINE.findall(out[idx:])
                if nm == CERT_NAME or nm.endswith("." + CERT_NAME)]
            cert_ok = bool(cert_lines) and all(
                {a.strip() for a in (axs or "").split(",")
                 if a.strip()} <= AXIOM_ALLOW
                for axs in cert_lines)
            if cert_ok:
                outcome = Outcome.REFUTED
            else:
                outcome = Outcome.UNPROVED
                error = ("refutation certificate declared but not "
                         "kernel-accepted (rejected proof, missing audit "
                         "line, or a non-allowlisted axiom); a rejected "
                         "certificate is never REFUTED")
    elif p.returncode == 0:
        if idx < 0:
            outcome = Outcome.TOOL_ERROR
            error = ("adapter audit sentinel missing from tool output "
                     "(empty or suppressed) — kernel evidence absent; "
                     f"output tail: {out[-200:]!r}")
        elif bad_axioms:
            outcome = Outcome.VACUOUS
        elif unaudited:
            outcome = Outcome.TOOL_ERROR
            error = ("no post-sentinel audit line for: "
                     + ", ".join(unaudited[:5]))
        else:
            outcome = Outcome.VERIFIED
    elif any(m in out for m in UNPROVED_MARKS):
        outcome = Outcome.UNPROVED
        error = ("proof search stopped without a countermodel and without "
                 "budget exhaustion; incompleteness, not falsity")
    else:
        outcome = Outcome.MALFORMED
    return Result("lean", version(), src_hash, outcome,
                  ok=outcome == Outcome.VERIFIED, exit_code=p.returncode,
                  wall_ms=wall, budget=f"heartbeats={budget}", error=error,
                  extras={"axioms": sorted(ax_used), "theorems": theorems,
                          "banned_tokens": []})
