"""t.verifiers.rocq — the fifth kernel: the Rocq Prover (né Coq).

Kernel-checked like Lean, solverless like Lean — determinism is
architectural. The pin is opam's rocq 9.2.0 (coqc + coqchk from the same
switch; the opam route's rocq-stdlib.9.2.0 does not exist, which the install
attempt measured the hard way).

VERIFIED requires positive evidence, not exit-0 (contract; Wave-1 audit
2026-08-31 measured four launderings past the old stdout-substring check):

  1. coqc accepts the source (exit 0);
  2. the source declares at least one named obligation
     (Theorem/Lemma/Corollary/Fact/Remark/Proposition/Property) — a file
     with zero theorems is MALFORMED, never VERIFIED;
  3. an ADAPTER-GENERATED audit file Requires the compiled unit and runs
     `Print Assumptions t_unit.<thm>.` for EVERY declared obligation: the
     audit run must exit 0, print exactly one "Closed under the global
     context" per obligation, and print no "Axioms:" section. The audit
     stdout contains only this adapter's commands' output — a sentinel the
     SOURCE prints (string_inject.v: Eval compute of the sentinel string;
     param_decoy.v / conjecture_decoy.v / funext_decoy.v: a decoy
     `Print Assumptions triv` on an honest True lemma) never reaches it.
     Print Assumptions also reports guard/universe bypasses ("is assumed
     to be guarded", measured on coqc 9.2), so those cannot close;
  4. coqchk -o -norec re-checks the compiled .vo with the independent
     checker kernel and its CONTEXT SUMMARY must list no t_unit.* entry
     under Axioms / type-in-type / unsafe (co)fixpoints / assumed
     positivity (measured: `Parameter bogus : False` appears there as
     `t_unit.bogus` even when no audited theorem mentions it).

Verdict classification (coqc/coqchk 9.2.0, re-measured on this machine
2026-08-31):
  banned token in comment-stripped SOURCE (Admitted / admit /
      Admit / give_up / Axiom(s) / Parameter(s) / Conjecture(s) /
      Hypothesis(-es) / Variable(s) / Context / Declare ML Module /
      bypass_check / Unset {Universe,Guard,Positivity} Checking)
                                                              -> VACUOUS
  audit run finds open assumptions or unsafe-flag reliance,
      or coqchk refuses / lists a t_unit.* assumption          -> VACUOUS
  "Tactic failure" / "Cannot find witness" / "Unable to
      unify" / "unsolved"                                      -> UNPROVED
      (the engine or a decision tactic stopped without a
      countermodel; lia's honest can't-prove is "Cannot find
      witness". Rocq is a proof assistant: an unclosed goal is
      not a disproof, so these never mint REFUTED. ROADMAP 10.7,
      fixed 2026-09-02; a rejected refutation certificate lands
      here too)
  "Syntax error" / "was not found" / "Illegal"                 -> MALFORMED
  source not valid UTF-8 (coqc 9.2 tolerates stray bytes in
      comments — junk_nonutf8.v measured — but this adapter's
      token scan would run on a lossy decode)                  -> MALFORMED
  zero declared theorems / audit cannot resolve a declared
      obligation name                                          -> MALFORMED
  wall backstop (whole pipeline shares one deadline)           -> TIMEOUT
  all four positive checks pass, and the declared goals
      include t_refutation_certificate (the lowering's
      kernel-checked proof that the spec fails at the measured
      twin witness; the ONLY door to REFUTED)                  -> REFUTED
  all four positive checks pass, certificate name present
      but not a declared goal (planting the name only demotes) -> VACUOUS
  all four positive checks above pass                          -> VERIFIED
UNPROVED markers are tested before MALFORMED; both exit nonzero.

The ban regex is the SECOND line of defense: it scans the source with
comments and string literals stripped (each replaced by one space, so a
token split by a comment cannot re-fuse: `Axi(**)om` lexes as two idents in
Coq and stays two words here — overfire_axiom_comment.v and
overfire_admit_comment.v measured the old in-comment ban as a false
VACUOUS), case-sensitively (Coq vernacular is case-sensitive; lowercase
`context` is an Ltac keyword in honest generated files), on both the raw
text and its NFKC normalization (fullwidth homoglyphs fold to ASCII; a
non-foldable homoglyph like Cyrillic А in `Аxiom` fails coqc's parser —
homoglyph_axiom.v measured MALFORMED). A ban token that slips through
still cannot yield a false VERIFIED: the audit + coqchk checks above do
not depend on it.

No deterministic resource flag exists at the CLI; the wall backstop is
honest about being a backstop, and flake_check re-measures the
architectural determinism claim.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import time
import unicodedata
from pathlib import Path

from . import Outcome, Result, safe_text, sha256_file
from .discover import find, missing

COQC = find("T_COQC", ['coqc', 'rocq'], [".opam/*/bin/coqc"])
_COQC_WHY = missing("rocq", "T_COQC", ['coqc', 'rocq'], [".opam/*/bin/coqc"])


def _find_coqchk() -> str | None:
    # same-switch sibling first: the checker must be the pin's own kernel
    if COQC:
        for n in ("coqchk", "rocqchk"):
            sib = Path(COQC).parent / n
            if sib.is_file():
                return str(sib)
    return find("T_COQCHK", ['coqchk', 'rocqchk'], [".opam/*/bin/coqchk"])


COQCHK = _find_coqchk()
WALL_S = 180
CLOSED = "Closed under the global context"

# Case-sensitive: Coq vernacular keywords are; lowercase `context` is Ltac.
BANNED = re.compile(
    r"\bAdmitted\b|\badmit\b|\bAdmit\b|\bgive_up\b"
    r"|\bAxioms?\b|\bParameters?\b|\bConjectures?\b"
    r"|\bHypothes[ie]s\b|\bVariables?\b|\bContext\b"
    r"|\bDeclare\s+ML\s+Module\b"
    r"|\bbypass_check\b"
    r"|\bUnset\s+(?:Universe|Guard|Positivity)\s+Checking\b")

THM = re.compile(
    r"\b(?:Theorem|Lemma|Corollary|Fact|Remark|Proposition|Property)"
    r"\s+([A-Za-z_][A-Za-z0-9_']*)")

# The ONE door to REFUTED: a goal with exactly this name, accepted by the
# kernel under the full audit discipline (bans, per-theorem closedness
# audit, coqchk re-check). The lowering emits it only for a measured twin
# witness; it states the negation of the spec instantiated at that witness
# and is proved by ground evaluation, so its acceptance is positive
# kernel evidence of falsity. A file that even MENTIONS the name outside
# a declared goal can never mint VERIFIED (planting it only demotes).
CERT_NAME = "t_refutation_certificate"
CERT_RE = re.compile(r"\bt_refutation_certificate\b")

# Incompleteness marks: the engine or a decision tactic STOPPED without a
# countermodel (Rocq is a proof assistant; an unclosed goal is not a
# disproof, and lia's honest can't-prove is "Cannot find witness").
# These mint UNPROVED, never REFUTED (ROADMAP 10.7, fixed 2026-09-02;
# the old REFUTED_MARKS minted REFUTED from exactly these strings).
UNPROVED_MARKS = ("Tactic failure", "Cannot find witness", "Unable to unify",
                  "unsolved")

MALFORMED_MARKS = ("Syntax error", "was not found", "Illegal", "Unknown")

_SPECIAL = re.compile(r'\(\*|\*\)|"')


def _strip(src: str) -> str:
    """Remove Coq comments (nested; strings are lexed inside them) and
    string literals, each replaced by one space so token boundaries survive
    exactly as Coq's lexer sees them."""
    out = []
    i, n = 0, len(src)
    depth = 0            # comment nesting
    while i < n:
        m = _SPECIAL.search(src, i)
        if not m:
            if depth == 0:
                out.append(src[i:])
            break
        tok = m.group()
        if depth == 0:
            out.append(src[i:m.start()])
            if tok == "(*":
                depth = 1
                out.append(" ")
                i = m.end()
            elif tok == '"':
                out.append(" ")
                i = m.end()
                while i < n:                      # skip string, "" escapes
                    j = src.find('"', i)
                    if j < 0:
                        i = n
                        break
                    if src.startswith('""', j):
                        i = j + 2
                        continue
                    i = j + 1
                    break
            else:                                 # stray *) outside comment
                i = m.end()
        else:
            if tok == "(*":
                depth += 1
                i = m.end()
            elif tok == "*)":
                depth -= 1
                i = m.end()
            else:                                 # string inside comment
                i = m.end()
                while i < n:
                    j = src.find('"', i)
                    if j < 0:
                        i = n
                        break
                    if src.startswith('""', j):
                        i = j + 2
                        continue
                    i = j + 1
                    break
    return "".join(out)


def _left(deadline: float) -> float:
    return max(1.0, deadline - time.monotonic())


def version() -> str:
    if not COQC:
        raise SystemExit(_COQC_WHY)
    p = subprocess.run([COQC, "--version"], capture_output=True, text=True)
    return p.stdout.strip().splitlines()[0]


def verify(path: Path, budget: int = 0) -> Result:
    if not COQC or not shutil.which(COQC):
        raise SystemExit("t.verifiers.rocq: no coqc on PATH")
    src_hash = sha256_file(path)
    src_bytes = path.read_bytes()
    src_text = safe_text(path)                    # never crashes on non-UTF8
    code = _strip(src_text)
    banned = sorted(set(BANNED.findall(code))
                    | set(BANNED.findall(unicodedata.normalize("NFKC", code))))
    thms = list(dict.fromkeys(THM.findall(code)))
    cert_declared = CERT_NAME in thms
    cert_carried = bool(
        CERT_RE.search(code)
        or CERT_RE.search(unicodedata.normalize("NFKC", code)))
    t0 = time.monotonic()
    deadline = t0 + WALL_S

    def done(outcome, exit_code=-1, error="", extras=None):
        return Result("rocq", version(), src_hash, outcome,
                      ok=outcome == Outcome.VERIFIED, exit_code=exit_code,
                      wall_ms=int((time.monotonic() - t0) * 1000),
                      budget="wall backstop only", error=error,
                      extras={"banned_tokens": banned[:5],
                              "theorems": thms[:10], **(extras or {})})

    try:
        src_bytes.decode("utf-8")
    except UnicodeDecodeError as e:
        # coqc 9.2 tolerates stray non-UTF8 bytes inside comments (measured:
        # junk_nonutf8.v compiles), but this adapter's token scan then runs
        # on a lossy decode; refuse rather than attest what was not read
        # faithfully. Harness-generated sources are always written UTF-8.
        return done(Outcome.MALFORMED,
                    error=f"source is not valid UTF-8 ({e}); "
                          "token scan would be lossy")

    if banned:
        return done(Outcome.VACUOUS, error="banned token(s) in source")

    # coqc derives a module name from the basename and rejects dots, so the
    # harness's *.twin.v files would be MALFORMED for filename reasons — the
    # same trap GNAT's naming convention set, in Rocq costume. The adapter
    # owns the on-disk name; the witness hash binds to the SOURCE bytes,
    # which are copied verbatim (no decode/re-encode round trip).
    import tempfile
    with tempfile.TemporaryDirectory(prefix="t-rocq-") as td:
        unit = Path(td) / "t_unit.v"
        unit.write_bytes(src_bytes)
        try:
            p = subprocess.run([COQC, "t_unit.v"], capture_output=True,
                               text=True, timeout=_left(deadline), cwd=td)
        except subprocess.TimeoutExpired:
            return done(Outcome.TIMEOUT, error="backstop fired")
        out = p.stdout + p.stderr
        if p.returncode != 0:
            if any(m in out for m in UNPROVED_MARKS):
                # stopped without a countermodel, without budget exhaustion:
                # not knowledge, and in particular not falsity. A rejected
                # t_refutation_certificate lands here too: UNPROVED.
                return done(Outcome.UNPROVED, exit_code=p.returncode,
                            error="proof search gave up: " + out[-200:])
            if any(m in out for m in MALFORMED_MARKS):
                return done(Outcome.MALFORMED, exit_code=p.returncode)
            return done(Outcome.MALFORMED, exit_code=p.returncode)
        if not thms:
            return done(Outcome.MALFORMED, exit_code=p.returncode,
                        error="no named theorem declared — no proof "
                              "obligation to verify")

        # positive check 1: adapter-controlled per-theorem closedness audit.
        # Only this file's Print Assumptions commands can write to this
        # run's stdout; nothing the SOURCE printed at compile time reaches
        # it (Require loads the .vo, it does not replay vernacular).
        audit = Path(td) / "t_audit.v"
        audit.write_text(
            "Require t_unit.\n"
            + "".join(f"Print Assumptions t_unit.{t}.\n" for t in thms),
            encoding="utf-8")
        try:
            a = subprocess.run([COQC, "t_audit.v"], capture_output=True,
                               text=True, timeout=_left(deadline), cwd=td)
        except subprocess.TimeoutExpired:
            return done(Outcome.TIMEOUT, error="backstop fired (audit)")
        a_out = a.stdout + a.stderr
        closed_n = a_out.count(CLOSED)
        if a.returncode != 0:
            return done(Outcome.MALFORMED, exit_code=a.returncode,
                        error="closedness audit could not resolve a "
                              "declared obligation: " + a_out[-300:],
                        extras={"audit_closed": closed_n})
        if closed_n != len(thms) or "Axioms:" in a_out:
            return done(Outcome.VACUOUS, exit_code=a.returncode,
                        error="assumptions not closed for every declared "
                              "obligation: " + a_out[-300:],
                        extras={"audit_closed": closed_n})

        # positive check 2: independent kernel re-check of the compiled
        # artifact; a source-printed line cannot appear here either.
        if not COQCHK:
            return done(Outcome.TOOL_ERROR,
                        error="no coqchk/rocqchk beside the pinned coqc — "
                              "independent kernel re-check unavailable")
        try:
            c = subprocess.run([COQCHK, "-silent", "-o", "-norec", "t_unit"],
                               capture_output=True, text=True,
                               timeout=_left(deadline), cwd=td)
        except subprocess.TimeoutExpired:
            return done(Outcome.TIMEOUT, error="backstop fired (coqchk)")
        c_out = c.stdout + c.stderr
        # CONTEXT SUMMARY entries are indented qualified names; any local
        # one (axiom, type-in-type, unsafe fixpoint, assumed positivity)
        # is an assumption smuggled past the theorem-name scan.
        local_assumed = re.findall(r"(?m)^\s+(t_unit\.\S+.*)$", c_out)
        if c.returncode != 0 or local_assumed:
            return done(Outcome.VACUOUS, exit_code=c.returncode,
                        error="coqchk kernel re-check refused the unit: "
                              + (" ; ".join(local_assumed)[:200]
                                 or c_out[-300:]),
                        extras={"audit_closed": closed_n,
                                "coqchk_assumed": local_assumed[:5]})
        if cert_declared:
            # All four positive checks passed and the declared goals include
            # the refutation certificate: the kernel accepted a proof that
            # the spec fails at the measured witness, audited exactly like
            # any proof (closedness per theorem, coqchk re-check). This is
            # the one door to REFUTED: positive evidence of falsity.
            return done(Outcome.REFUTED, exit_code=0,
                        extras={"audit_closed": closed_n, "coqchk": "clean",
                                "certificate": "kernel-accepted"})
        if cert_carried:
            # The certificate name appears outside a declared goal. Such a
            # file may never mint VERIFIED: carrying the refutation name is
            # a claim of falsity machinery, and exit 0 without the declared,
            # audited goal is acceptance for the wrong reason.
            return done(Outcome.VACUOUS, exit_code=0,
                        error="carries t_refutation_certificate without "
                              "declaring it as a goal",
                        extras={"audit_closed": closed_n, "coqchk": "clean"})
        return done(Outcome.VERIFIED, exit_code=0,
                    extras={"audit_closed": closed_n, "coqchk": "clean"})
