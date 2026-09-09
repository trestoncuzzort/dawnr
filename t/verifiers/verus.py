"""t.verifiers.verus, the second kernel.

Verdict mapping (Verus 0.2026.08.30.b432e82, per the WS-7 dossier and
measured here): exit codes are 0/1 only, so the taxonomy comes from
--output-json plus the message stream. VERIFIED demands POSITIVE evidence,
all five at once: verification-results present, errors == 0 with success,
verified >= 1, at least one non-spec fn carrying a real `ensures` clause,
and, as the last gate, a kernel-native vacuity probe that comes back clean.
The Wave-1 audit (2026-08-31) measured success=true with verified=0 for an
empty verus!{} block, a spec-only file, and a #[verifier::external] theorem
All three scored VERIFIED under the old errors==0 test. verified counts
only functions whose obligations the solver actually discharged, so
verified >= 1 is the obligation evidence; the ensures scan closes the
remaining trivial pass (exec fn with no ensures: verified=1, zero theorems).

VACUITY IS ASKED OF THE KERNEL, NOT OF A REGEX. Two native instruments,
in order of what they cost:

1. --no-cheating. Verus's own flag for "reject assume, admit,
   verifier::external_body and assume_specification". It is the kernel
   deciding, by construct identity rather than by spelling, so it holds
   against renames and homoglyphs the token scan cannot see: measured
   2026-08-31, h_assume.rs and h_extbody.rs are refused with
   "assume/admit not allowed with --no-cheating" at encountered-vir-error,
   and honest lowerings are byte-for-byte unaffected (count_matches,
   seq_max: verified 4 and 6, errors 0, with and without the flag).

2. The precondition smoke probe (_probe_vacuity), this adapter's answer to
   Dafny's --warn-contradictory-assumptions: Verus has no such flag, so the
   question is put to the solver directly. For every non-spec fn carrying a
   `requires`, the probe appends to the source a second verus!{} block
   holding a proof fn with THAT function's parameters and THAT function's
   requires clauses verbatim, no ensures, and a body of exactly
   `assert(false);`. If the solver proves it, the precondition is
   unsatisfiable and every obligation the original function "discharged"
   under it proved nothing, so VACUOUS. Appending rather than rewriting is
   what makes it robust: the probe fn sees the file's own spec fns, types
   and imports, so it compiles whenever the original does.

   The probe is PER FUNCTION, which is the point. `verified` is a FILE-WIDE
   SUM, so one honest proof fn paired with one unsatisfiable-requires fn
   scores verified=2, errors=0 (measured, n_truepplusvac.rs) while the file
   contains a function that ensures false. Each probe fn contributes exactly
   one obligation at a line this adapter generated and therefore knows, so
   the diagnostic spans name which function is vacuous regardless of what
   the rest of the file did.

   Self-check, because a probe that silently fails to compile would report
   every precondition as unsatisfiable: the appended block ends with a
   canary proof fn with NO requires and the same `assert(false);`. It must
   come back refuted. If it does not, because the probe file did not build, the
   run timed out or the JSON did not parse, the instrument had no reading,
   so the file cannot be certified: TOOL_ERROR, never VERIFIED. Same for a
   function the probe cannot express (generics, a where clause, or a `self`
   receiver, none of which t emits): refuse the file rather than skip the
   function.

   Cost, measured 2026-08-31 on this box: the probe is the LAST gate, so it
   runs only on files that would otherwise be VERIFIED, and not at all on a
   file where no function has a requires (abs, max: zero extra runs). Where
   it runs it costs one extra Verus invocation, 318-407 ms against a
   330-540 ms first run.

The lexical scans stay as a cheap second line, never as the thing the
soundness claim rests on. The ban is prefix-matched (`assume\\w*` etc.)
because Wave-1's \\b-delimited exact words missed assume_specification and
#[verifier::external] ('_' is a word char, and `external` was not listed).
`requires false` is the same hazard from the other side (measured VERIFIED,
Wave-1 h_reqfalse). Both are strictly redundant now: --no-cheating and the
smoke probe catch a superset, including the cases the regexes provably miss:
`requires 1 == 0` and `requires x < x` carry no `false` token at all, and
`requires ({ let b = false; b })` hides the token behind a `{` the
tempered-dot stops at (measured VERIFIED, all three, before the probe).
The requires-false scan was NARROWED on 2026-09-04 to a clause that IS the
constant false, per-clause and paren-stripped, because asking whether the
token appears anywhere in the block is a strictly larger question than the
one it can answer: the metamorphic sweep rewrote a precondition P to the
equivalent `P || false` and this adapter called 79 files vacuous that were
satisfiable exactly when P was. Everything subtler than a literal clause is
_probe_vacuity's job, which asks the solver for a model instead of guessing
from spelling.
The scans are deliberately asymmetric about inert text:
  - ban + requires-false run on the RAW decoded source (a hit in a comment
    or string over-flags to VACUOUS, which fails closed; stripping first would
    let a stripper bug hide a live assume behind a `"//"` string);
  - the positive ensures evidence runs on comment/string-MASKED source (a
    masking bug can only hide a real ensures, which scores MALFORMED,
    fails closed; raw text would let `// ensures` fake the evidence).
Ban matching also folds NFKC + common Cyrillic homoglyphs + zero-width
chars: a look-alike `аssume` is not the Verus builtin (rustc rejects the
identifier, so verified>=1 already refuses the file); folding upgrades that
refusal to VACUOUS.

TIMEOUT: the Wave-1 sniff (`"rlimit" and "exceeded" anywhere in output)
was source-spoofable: a comment `// rlimit exceeded` is quoted verbatim in
the diagnostic gutter, flipping a REFUTED into TIMEOUT (measured,
c_rlimitword). The check is now anchored to the tool's own header line
(`error:`/`note:` at column 0, since gutter-quoted source always carries a
`N | ` prefix), uses the exact phrase embedded in the rust_verify binary
(": Resource limit (rlimit) exceeded"), and additionally requires
errors > 0 in verification-results (a compile_error! spoof fails rustc with
errors == 0 and stays MALFORMED).

Budget: --rlimit (solver resource multiplier), deterministic where
wall-clock is not, the same doctrine as Dafny's. The bundled Z3 is used as
shipped; the release bundle pins it, and version() records the identity.

REFUTED (ROADMAP 10.7, measured 2026-09-02 on 0.2026.08.30.b432e82): Verus
surfaces NO signal that separates a countermodel from incompleteness, so a
bare verification failure NEVER mints REFUTED here. The measurement, in
order of depth: (1) --output-json for a genuinely false postcondition
(ensures r >= 0, body x) and for TRUE nonlinear distributivity
(ensures r == x*y + x*z, body x*(y+z)) is field-for-field identical:
errors=1, success=false, no other field moves. (2) The message stream is
identical: "postcondition not satisfied", same shape, no model. (3) The
SMT transcript (--log smt-transcript) shows why nothing better is
possible: Verus sets smt.mbqi false and auto_config false, so Z3 answers
"unknown" for BOTH queries, never "sat", and never builds a model; the
later "unsat" answers are the --multiple-errors localization re-queries.
(4) --expand-errors marks track conjunction structure, not falsity: the
single-clause false goal gets no mark while the true nonlinear conjunct
gets ✘ (both measured). (5) No flag mentions counterexamples or models
(--help, full scan). Errors > 0 without an rlimit header is therefore
Outcome.UNPROVED: the solver stopped, no budget exhaustion, no
countermodel, not knowledge either way.

THE REFUTATION CERTIFICATE is how a twin cell earns REFUTED back, per the
shared protocol: lower_verus.py, when handed a measured witness, appends
one proof fn named exactly t_refutation_certificate holding a single
assert(..) by (compute_only) that instantiates the spec at the concrete
witness and evaluates the negated obligation ground (see the section
comment there for what each witness kind certifies). This adapter mints
REFUTED if and only if the kernel both DECLARED that goal (its own
func-details listing from the first run, never a regex alone) and
ACCEPTED it in a second, targeted run (--verify-root --verify-function,
errors == 0 and verified >= 1; measured: the targeted run carries no
"success" field), and the main run FAILED: a file whose every goal
discharged, the certificate's included, reads MALFORMED (the coherence
gate, 2026-09-07, fstar's rule), because a claim that the twin's theorem
is false at the witness cannot sit beside the kernel's proof of that
theorem. Two closures make the name safe: a file carrying the
certificate name can NEVER mint VERIFIED, so planting it in a real
program only demotes that program; and a certificate the kernel rejects
or cannot read mints UNPROVED, never REFUTED. All demotion gates
(--no-cheating refusal, ban scan, requires-false) run BEFORE the
certificate is consulted, so the audit discipline is unchanged. What the
adapter cannot check is that the asserted formula IS the negated spec at
the witness: that binding lives in the lowering, which is the same trust
already extended to every lowered obligation.
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
import time
import unicodedata
from pathlib import Path

from . import Outcome, Result, safe_text, sha256_file, run_tree
from .discover import find, missing

VERUS = find("T_VERUS_BIN", ['verus'], [".local/verus/**/verus"])
_VERUS_WHY = missing("verus", "T_VERUS_BIN", ['verus'], [".local/verus/**/verus"])
DEFAULT_RLIMIT = 10
WALL_S = 120

# Prefix-matched ban families: assume, assume_specification, admit, external,
# external_body, external_fn_specification, external_type_specification, and
# any future *_specification aspect spelled with these stems. Left \b is
# sound: the live constructs sit after '::', '(', '[', or whitespace, all
# non-word chars.
BANNED = re.compile(r"\b(?:assume|admit|external)\w*")

# requires-false: scan from `requires` up to the next clause keyword or
# block/statement delimiter for a bare `false` token. Stops at '{', so a
# `false` hidden behind an ite inside a requires clause escapes this regex,
# as does `requires 0 == 1`, and no regex decides satisfiability. Both are
# measured evasions (n_reqfalse_brace, n_reqvac); _probe_vacuity is what
# actually closes them.
_REQ_BLOCK = re.compile(
    r"\brequires\b((?:(?!\bensures\b|\bdecreases\b|\brecommends\b|[{;])[\s\S])*)")


def _req_false_clause(text: str) -> bool:
    """True when some requires CLAUSE is literally the constant false.

    The older rule asked whether the token `false` appeared anywhere between
    `requires` and the next clause keyword, which is a different question and
    a strictly larger one. Measured 2026-09-04: the metamorphic sweep rewrote
    a precondition P to the equivalent `P || false` and this adapter called 79
    files vacuous that were not, every one of them verus. That is the failure
    ROADMAP 10.2 names, an adapter re-parsing a rich language with a regex,
    and it joins the char literal, the raw identifier `r#try` and the
    parameter named `recommends` in that list.

    So the token scan is narrowed to what it can actually decide, a clause
    that IS false, and everything else is left to _probe_vacuity, which asks
    the solver whether a precondition has a model. A genuine `requires false`
    is caught here AND there; `P || false` is caught by neither, correctly,
    because it is satisfiable exactly when P is.
    """
    for m in _REQ_BLOCK.finditer(text):
        depth = 0
        clause: list[str] = []
        for ch in m.group(1) + ",":
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            if ch == "," and depth <= 0:
                c = "".join(clause).strip()
                while c.startswith("(") and c.endswith(")"):
                    c = c[1:-1].strip()
                if c == "false":
                    return True
                clause = []
            else:
                clause.append(ch)
    return False

_ENSURES = re.compile(r"\bensures\b")

# Anchored to column 0 and to the exact phrase in the rust_verify binary;
# requires errors > 0 at the call site (see module docstring).
_RLIMIT_DIAG = re.compile(
    r"^(?:error|note)(?:\[[^\]]*\])?: .*Resource limit \(rlimit\) exceeded",
    re.M)

# Verus's own refusal of the cheating constructs, emitted at column 0 with
# encountered-vir-error and no verified/errors tally at all.
_NOCHEAT_DIAG = re.compile(r"^error: .*not allowed with --no-cheating", re.M)

# The one goal name that can mint REFUTED (module docstring, certificate
# section). The raw-text scan only ever DEMOTES: it bars VERIFIED for any
# file carrying the name, comments and strings included, fail-closed.
# Minting additionally requires the kernel's own func-details declaration.
CERT_NAME = "t_refutation_certificate"
_CERT = re.compile(r"\bt_refutation_certificate\b")

# Cyrillic/Greek/Armenian codepoints that render as a-z (the confusables
# actually seen evading keyword scans; NFKC does not fold these).
_HOMOGLYPHS = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x",
    "і": "i", "ѕ": "s", "ј": "j", "ԛ": "q", "ԝ": "w", "ɑ": "a", "ν": "v",
    "υ": "u", "ο": "o", "ⅰ": "i", "ⅼ": "l", "ⅾ": "d", "ⅿ": "m"})
_ZERO_WIDTH = dict.fromkeys(
    (0x200b, 0x200c, 0x200d, 0x2060, 0xfeff, 0x00ad))


def _fold(s: str) -> str:
    return unicodedata.normalize("NFKC", s.translate(_ZERO_WIDTH)) \
        .translate(_HOMOGLYPHS)


def _ban_hits(text: str) -> list[str]:
    hits = BANNED.findall(text)
    for h in BANNED.findall(_fold(text)):
        if h not in hits:
            hits.append(h)
    return hits


def _mask_inert(s: str) -> str:
    """Blank out //-comments, nested /* */ comments, "..." strings and
    r/r#..# raw strings, replacing each inert character with a space and
    keeping every newline, so offsets and line numbers are identical to the
    input. Mis-lexing fails closed in both consumers: the `ensures` evidence
    scan can only lose a real ensures (MALFORMED, never VERIFIED), and the
    signature parser can only lose a function (a lost requires-carrying fn
    would skip its probe, so the parser is cross-checked by the canary and
    by the ban/requires-false scans on raw text). Char literals are not
    lexed: one codepoint cannot spell a keyword, and a '"' char literal at
    worst opens a phantom string, which again only over-masks. t's lowering
    emits exactly one comment (`// verus!`) and no string/char literals."""
    out: list[str] = []
    i, n = 0, len(s)

    def blank(seg: str) -> None:
        out.append("".join(c if c == "\n" else " " for c in seg))

    while i < n:
        c = s[i]
        nxt = s[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            j = s.find("\n", i)
            j = n if j < 0 else j
            blank(s[i:j])
            i = j
        elif c == "/" and nxt == "*":
            depth, j = 1, i + 2
            while j < n and depth:
                if s.startswith("/*", j):
                    depth, j = depth + 1, j + 2
                elif s.startswith("*/", j):
                    depth, j = depth - 1, j + 2
                else:
                    j += 1
            blank(s[i:j])
            i = j
        elif c == '"':
            j = i + 1
            while j < n and s[j] != '"':
                j += 2 if s[j] == "\\" else 1
            j = min(j + 1, n)
            blank(s[i:j])
            i = j
        elif (c == "r" and nxt in ('"', "#")
              and (i == 0 or not (s[i - 1].isalnum() or s[i - 1] == "_"))):
            j = i + 1
            hashes = 0
            while j < n and s[j] == "#":
                hashes, j = hashes + 1, j + 1
            if j < n and s[j] == '"':
                close = '"' + "#" * hashes
                k = s.find(close, j + 1)
                k = n if k < 0 else k + len(close)
                blank(s[i:k])
                i = k
            else:
                out.append(c)
                i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


# ------------------------------------------ the native vacuity instrument
# A Verus fn signature is `[spec|proof|exec] fn NAME [<GEN>] (PARAMS)
# [-> RET] [where W] CLAUSE* { BODY }`. The parser below needs exactly two
# things per function: the parameter list and the requires clauses, so it
# reads signatures only and stops at the body brace.

_CLAUSE_KWS = ("requires", "recommends", "ensures", "default_ensures",
               "returns", "decreases", "opens_invariants", "no_unwind",
               "where", "via", "when")
_CLAUSE_RE = re.compile(r"(?:" + "|".join(_CLAUSE_KWS) + r")\b")
_FN_HEAD = re.compile(r"\bfn\s+([A-Za-z_]\w*)")
_MODE_RE = re.compile(r"\b(spec|proof|exec)\s*(?:\([^)]*\)\s*)?$")
_SELF = re.compile(r"\bself\b")

# `error: <msg>` / `warning: ...` followed (possibly after other lines) by a
# `  --> file:LINE:COL` span. Parsed pairwise rather than by one regex so a
# diagnostic without a span cannot swallow the next one's location.
_DIAG_HEAD = re.compile(r"^(error|warning|note)(?:\[[^\]]*\])?: (.*)$")
_DIAG_SPAN = re.compile(r"^\s*--> [^\n]*?:(\d+):\d+")


def _match_bracket(m: str, i: int, op: str, cl: str) -> int:
    """i indexes the opening bracket; return the index just past its match,
    or -1 if unbalanced."""
    depth = 0
    while i < len(m):
        if m[i] == op:
            depth += 1
        elif m[i] == cl:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


def _fns(text: str) -> list[dict]:
    """Every `fn` ITEM in text, as {name, mode, generics, params, clauses,
    line}. Reads the comment/string mask for structure and slices the
    original for content, so the two always agree on offsets."""
    m = _mask_inert(text)
    out: list[dict] = []
    for hit in _FN_HEAD.finditer(m):
        pre = _MODE_RE.search(m[:hit.start()].rstrip())
        mode = pre.group(1) if pre else "exec"
        i = hit.end()
        while i < len(m) and m[i].isspace():
            i += 1
        gen = ""
        if i < len(m) and m[i] == "<":
            depth, j = 0, i
            while j < len(m):
                if m[j] == "<":
                    depth += 1
                elif m[j] == "-" and j + 1 < len(m) and m[j + 1] == ">":
                    j += 1                      # a return arrow, not a close
                elif m[j] == ">":
                    depth -= 1
                    if depth == 0:
                        j += 1
                        break
                j += 1
            gen = text[i:j]
            i = j
            while i < len(m) and m[i].isspace():
                i += 1
        if i >= len(m) or m[i] != "(":
            continue                            # `fn(..)` pointer type, not an item
        j = _match_bracket(m, i, "(", ")")
        if j < 0:
            continue
        params = text[i + 1:j - 1]
        # Walk the rest of the signature to the body brace, collecting
        # clauses. A `{` while a clause expression is expected is a block
        # expression inside that clause (`requires ({ let b = false; b })`
        # and its unparenthesized form), not the body.
        k, expect_expr, body = j, False, -1
        clauses: dict[str, str] = {}
        cur, cur_start = None, -1
        while k < len(m):
            c = m[k]
            if c in "([":
                k = _match_bracket(m, k, c, ")" if c == "(" else "]")
                if k < 0:
                    break
                expect_expr = False
                continue
            if c == "{":
                if not expect_expr:
                    body = k
                    break
                k = _match_bracket(m, k, "{", "}")
                if k < 0:
                    break
                expect_expr = False
                continue
            if c == ";":
                break                           # declaration without a body
            if c == ",":
                expect_expr = cur is not None
                k += 1
                continue
            cw = _CLAUSE_RE.match(m, k)
            if cw and not (m[k - 1].isalnum() or m[k - 1] == "_"):
                if cur:
                    clauses[cur] = text[cur_start:k]
                cur, cur_start = cw.group(0), cw.end()
                expect_expr = True
                k = cw.end()
                continue
            expect_expr = False
            k += 1
        if body < 0:
            continue
        if cur:
            clauses[cur] = text[cur_start:body]
        out.append({"name": hit.group(1), "mode": mode, "generics": gen,
                    "params": params, "clauses": clauses,
                    "line": text.count("\n", 0, hit.start()) + 1})
    return out


def _diags(err: str) -> list[tuple[int, str, str]]:
    """(line, severity, message) for every diagnostic carrying a span."""
    out, head = [], None
    for line in err.splitlines():
        h = _DIAG_HEAD.match(line)
        if h:
            head = (h.group(1), h.group(2))
            continue
        s = _DIAG_SPAN.match(line)
        if s and head:
            out.append((int(s.group(1)), head[0], head[1]))
            head = None
    return out


def _build_probe(text: str, targets: list[dict]) -> tuple[str, dict[int, str]]:
    """The probe source and {assert_line: function_name}. The probe is the
    original file plus one appended verus!{} block, so every name the
    requires clauses mention is still in scope."""
    pfx = "t_vac"
    while pfx in text:
        pfx += "_"
    head = text if text.endswith("\n") else text + "\n"
    blocks = ["\nverus!{\n"]
    for n, f in enumerate(targets):
        req = f["clauses"]["requires"].rstrip().rstrip(",")
        blocks.append(f"proof fn {pfx}_{n}({f['params']})\n"
                      f"    requires\n{req},\n{{\n    assert(false);\n}}\n")
    blocks.append(f"proof fn {pfx}_canary()\n{{\n    assert(false);\n}}\n")
    blocks.append("}\n")
    lines, off = {}, head.count("\n")
    for j, blk in enumerate(blocks):
        for rel, line in enumerate(blk.splitlines()):
            if line.strip() == "assert(false);":
                lines[off + rel + 1] = (f"{pfx}_canary" if j == len(blocks) - 2
                                        else targets[j - 1]["name"])
        off += blk.count("\n")
    return head + "".join(blocks), lines


def _probe_vacuity(text: str, budget: int) -> tuple[str, dict]:
    """Ask the solver whether any function's precondition is unsatisfiable.

    Returns (status, detail) with status one of:
      "clean"    : every precondition has a model, or none exist to probe
      "vacuous"  : assert(false) was PROVED under some precondition
      "unusable" : the instrument gave no reading; the caller must refuse
    """
    fns = _fns(text)
    targets = [f for f in fns
               if f["mode"] != "spec" and "requires" in f["clauses"]]
    if not targets:
        return "clean", {"probed": 0, "probe_ms": 0}
    # A probe fn is a copy of the parameter list, so a receiver or a
    # type-parameter bound it cannot carry means no reading for that
    # function. Refuse the file rather than certify it unprobed. (t's
    # lowerings emit neither; measured on all 11 tasks and their twins.)
    inexpressible = [f["name"] for f in targets
                     if f["generics"] or "where" in f["clauses"]
                     or _SELF.search(f["params"])
                     or _SELF.search(f["clauses"]["requires"])]
    if inexpressible:
        return "unusable", {"probed": 0, "probe_ms": 0,
                            "why": "no probe expressible for "
                                   + ", ".join(inexpressible[:5])}
    src, lines = _build_probe(text, targets)
    t0 = time.monotonic()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        # Fixed basename: Verus derives the crate name from it, and a dot or
        # dash in the name is a rustc error (measured, the .twin.rs finding).
        f = Path(d) / "t_vacuity_probe.rs"
        f.write_text(src, encoding="utf-8")
        try:
            p = run_tree(
                [str(VERUS), "--output-json", "--no-cheating",
                 "--rlimit", str(budget), str(f)],
                capture_output=True, text=True, timeout=WALL_S)
        except subprocess.TimeoutExpired:
            return "unusable", {"probed": len(targets),
                                "probe_ms": int((time.monotonic() - t0) * 1000),
                                "why": "probe run hit the wall backstop"}
    ms = int((time.monotonic() - t0) * 1000)
    try:
        vr = json.loads(p.stdout).get("verification-results")
    except (json.JSONDecodeError, AttributeError):
        vr = None
    detail = {"probed": len(targets), "probe_ms": ms}
    if not isinstance(vr, dict):
        detail["why"] = "probe run produced no verification-results"
        return "unusable", detail
    errs: dict[int, list[str]] = {}
    for ln, sev, msg in _diags(p.stderr):
        if sev == "error" and ln in lines:
            errs.setdefault(ln, []).append(msg)
    canary = [ln for ln, nm in lines.items() if nm.endswith("_canary")]
    if not canary or not any("assertion failed" in m
                             for m in errs.get(canary[0], [])):
        # The canary asserts false under NO precondition, so the solver must
        # reject it. Silence means the probe file never reached the solver
        # (a build error, an unparsed diagnostic stream) and every "proved"
        # below would be an artifact. No reading.
        detail["why"] = "probe canary was not refuted: " + p.stderr[-300:]
        return "unusable", detail
    proved, undecided = [], []
    for ln, nm in sorted(lines.items()):
        if nm.endswith("_canary"):
            continue
        msgs = errs.get(ln, [])
        if not msgs:
            proved.append(nm)                   # assert(false) DISCHARGED
        elif not any("assertion failed" in m for m in msgs):
            undecided.append(f"{nm}: {msgs[0]}")
    if undecided:
        # An rlimit or any other error at the probe's own assert is not the
        # solver saying "this precondition has a model"; it is the solver
        # saying nothing.
        detail["why"] = "probe undecided for " + "; ".join(undecided[:3])
        return "unusable", detail
    if proved:
        detail["vacuous_fns"] = proved[:5]
        return "vacuous", detail
    return "clean", detail


def _cert_error_lines(text: str, err: str) -> bool:
    """True when some error diagnostic's span falls inside the
    t_refutation_certificate fn, so the kernel's refusal is a refusal OF
    the certificate. Needed because a compute_only rejection aborts the
    whole run with encountered-vir-error and NO verified/errors counts
    (measured 2026-09-02: "expression simplifies to ... false"), which
    would otherwise be indistinguishable from a front-end failure."""
    fns = _fns(text)
    idx = [i for i, f in enumerate(fns) if f["name"] == CERT_NAME]
    if not idx:
        return False
    lo = fns[idx[0]]["line"]
    hi = (fns[idx[0] + 1]["line"] if idx[0] + 1 < len(fns)
          else 10 ** 9)
    return any(sev == "error" and lo <= ln < hi
               for ln, sev, _m in _diags(err))


def _check_certificate(path: Path, budget: int) -> tuple[bool, dict]:
    """One targeted kernel run of the certificate goal alone
    (--verify-root --verify-function). Accepted means the kernel
    discharged it: errors == 0 and verified >= 1 in the filtered
    verification-results (measured on 0.2026.08.30: the targeted run
    carries no "success" field, only the counts and the two encountered
    flags). Anything else, a wall timeout and an unparseable stream
    included, is not-accepted, which the caller maps to UNPROVED and
    never to REFUTED."""
    t0 = time.monotonic()
    try:
        p = run_tree(
            [str(VERUS), "--output-json", "--no-cheating",
             "--rlimit", str(budget), "--verify-root",
             "--verify-function", CERT_NAME, str(path)],
            capture_output=True, text=True, timeout=WALL_S)
    except subprocess.TimeoutExpired:
        return False, {"cert_ms": int((time.monotonic() - t0) * 1000),
                       "why": "certificate run hit the wall backstop"}
    ms = int((time.monotonic() - t0) * 1000)
    vr, fd = None, {}
    try:
        doc = json.loads(p.stdout)
        vr = doc.get("verification-results")
        fd = doc.get("func-details")
        if not isinstance(fd, dict):
            fd = {}
    except (json.JSONDecodeError, AttributeError):
        pass
    if not isinstance(vr, dict):
        return False, {"cert_ms": ms,
                       "why": "certificate run produced no "
                              "verification-results"}
    verified = vr.get("verified", 0)
    if not isinstance(verified, int) or isinstance(verified, bool):
        verified = 0
    declared = any(k == CERT_NAME or k.endswith("::" + CERT_NAME)
                   for k in fd)
    accepted = (declared and vr.get("errors", 1) == 0 and verified >= 1
                and vr.get("encountered-error") is False
                and vr.get("encountered-vir-error") is False)
    detail = {"cert_ms": ms, "cert_results": vr,
              "declared_in_cert_run": declared}
    if not accepted:
        detail["why"] = "the kernel did not accept the certificate goal"
    return accepted, detail


def version() -> str:
    if not VERUS:
        raise SystemExit(_VERUS_WHY)
    p = subprocess.run([str(VERUS), "--version"], capture_output=True, text=True)
    line = next((l for l in p.stdout.splitlines() if "Version" in l), "?")
    return f"verus {line.split(':', 1)[-1].strip()}"


def verify(path: Path, budget: int = DEFAULT_RLIMIT) -> Result:
    src_hash = sha256_file(path)
    # safe_text, not read_text: a non-UTF8 probe killed this adapter with an
    # unhandled UnicodeDecodeError in Wave-1 (j_nonutf8, j_random).
    text = safe_text(path)
    banned = _ban_hits(text)
    req_false = _req_false_clause(text)
    masked = _mask_inert(text)
    # Theorem evidence, per function rather than per file: some non-spec fn
    # must carry a real `ensures` CLAUSE, not merely the word somewhere in
    # the file. Conjoined with the older file-wide scan so a parser miss can
    # only withhold evidence (MALFORMED), never manufacture it.
    has_theorem = (_ENSURES.search(masked) is not None
                   and any(f["mode"] != "spec" and "ensures" in f["clauses"]
                           for f in _fns(text)))
    t0 = time.monotonic()
    try:
        p = run_tree(
            [str(VERUS), "--output-json", "--no-cheating",
             "--rlimit", str(budget), str(path)],
            capture_output=True, text=True, timeout=WALL_S)
    except subprocess.TimeoutExpired:
        return Result("verus", version(), src_hash, Outcome.TIMEOUT,
                      wall_ms=int((time.monotonic() - t0) * 1000),
                      budget=f"rlimit={budget}", error="wall backstop fired")
    wall = int((time.monotonic() - t0) * 1000)
    vr, fd = None, {}
    try:
        doc = json.loads(p.stdout)
        vr = doc.get("verification-results")
        fd = doc.get("func-details")
        if not isinstance(fd, dict):
            fd = {}
    except (json.JSONDecodeError, AttributeError):
        pass
    # Certificate presence, two readings that only ever demote: the
    # kernel's own goal listing (this is the one that can help mint
    # REFUTED) and the raw/folded text scan (bars VERIFIED even from a
    # comment, fail-closed).
    cert_declared = any(k == CERT_NAME or k.endswith("::" + CERT_NAME)
                        for k in fd)
    cert_present = bool(cert_declared or _CERT.search(text)
                        or _CERT.search(_fold(text)))

    errors = vr.get("errors", 0) if isinstance(vr, dict) else 0
    verified = vr.get("verified", 0) if isinstance(vr, dict) else 0
    if not isinstance(verified, int) or isinstance(verified, bool):
        verified = 0

    err, probe, cert = "", {}, {}
    if _NOCHEAT_DIAG.search(p.stderr):
        # The kernel itself refused an assume/admit/external_body/
        # assume_specification, by construct rather than by spelling.
        outcome = Outcome.VACUOUS
        probe = {"no_cheating_refusal": True}
    elif banned:
        outcome = Outcome.VACUOUS
    elif req_false:
        outcome = Outcome.VACUOUS
    elif vr is None:
        outcome = Outcome.MALFORMED
    elif (vr.get("errors", 1) == 0 and vr.get("success")
          and verified >= 1 and has_theorem and not cert_present):
        # Everything the solver counts says "proved". The remaining question
        # is whether it proved anything: ask the kernel (module docstring,
        # instrument 2).
        status, probe = _probe_vacuity(text, budget)
        if status == "vacuous":
            outcome = Outcome.VACUOUS
        elif status == "unusable":
            outcome = Outcome.TOOL_ERROR
            err = "vacuity probe gave no reading: " + probe.get("why", "?")
        else:
            outcome = Outcome.VERIFIED
    elif (cert_present and vr.get("errors", 1) == 0 and vr.get("success")
          and verified >= 1):
        # THE COHERENCE GATE (2026-09-07, fstar's rule adopted): every goal
        # in the file discharged, the twin's own included, so a certificate
        # claiming the twin's theorem false at the witness is incoherent
        # with the kernel's own verdict and evidence of nothing. Until this
        # gate the branch below minted REFUTED here from the goal alone.
        # Measured on the 159 lifted tasks (ROADMAP 12.5): slow_max read
        # REFUTED on a twin verus proves, an exit witness on a loop the
        # method assigns after.
        outcome = Outcome.MALFORMED
        err = ("certificate present on a file that verified: the kernel "
               "proved the twin, so the witness refutes nothing")
        cert = {"present": True, "declared_to_kernel": cert_declared,
                "coherence": "file verified"}
    elif cert_present:
        # Certificate discipline (module docstring): never VERIFIED; the
        # kernel's acceptance of the one declared goal is the only thing
        # that mints REFUTED, checked in its own targeted run so the main
        # goals' failures cannot mask it and vice versa. The targeted run
        # is its own declaration record too: a name that exists only in a
        # comment makes the run abort with "could not find function"
        # (measured), so it can never be accepted.
        accepted, cert = _check_certificate(path, budget)
        cert["declared_to_kernel"] = cert_declared
        if accepted:
            outcome = Outcome.REFUTED
        elif _RLIMIT_DIAG.search(p.stderr) and errors > 0:
            outcome = Outcome.TIMEOUT
        elif errors > 0 or _cert_error_lines(text, p.stderr):
            # The solver rejected goals without exhausting the budget, or
            # the kernel's abort points into the certificate fn itself: a
            # rejected certificate mints UNPROVED, never REFUTED.
            outcome = Outcome.UNPROVED
        else:
            # The front end rejected the file before any goal was seen
            # (rustc error, empty run): same reading as the tail below.
            outcome = Outcome.MALFORMED
    elif _RLIMIT_DIAG.search(p.stderr) and errors > 0:
        outcome = Outcome.TIMEOUT
    elif errors > 0:
        # No countermodel exists behind this signal (ROADMAP 10.7, module
        # docstring): with smt.mbqi off the solver answers "unknown" for a
        # false goal and for a true-but-nonlinear one alike, so errors > 0
        # is the solver stopping, not the solver refuting. UNPROVED, and a
        # twin earns REFUTED back only through the certificate above.
        outcome = Outcome.UNPROVED
    else:
        # vr exists but nothing was refuted and the positive-evidence gate
        # did not open: rustc rejected the file before verification, OR the
        # run discharged zero obligations (verified == 0: empty verus block,
        # spec-only file, external-annotated theorem, all measured
        # success=true in Wave-1), OR no ensures survives outside
        # comments/strings (zero stated theorems). MALFORMED, never
        # UNPROVED and never VERIFIED. The first repair here matched "error[" in
        # stderr, and the 2026-08-31 Dell install audit measured it vacuous:
        # the dotted-name diagnostic is a bare "error: invalid character '.'
        # in crate name" with no [E####] bracket, so <name>.twin.rs still
        # flipped verdicts on its filename alone. Classifying from the
        # solver's own counts closes every message-shape variant at once.
        outcome = Outcome.MALFORMED
    if not err and outcome == Outcome.TOOL_ERROR:
        err = p.stderr[-400:]
    return Result("verus", version(), src_hash, outcome,
                  ok=outcome == Outcome.VERIFIED, exit_code=p.returncode,
                  wall_ms=wall, budget=f"rlimit={budget}",
                  error=err,
                  extras={"verification_results": vr,
                          "banned_tokens": banned[:5],
                          "requires_false": req_false,
                          "has_ensures": has_theorem,
                          "verified_count": verified,
                          "vacuity_probe": probe,
                          "certificate": cert})
