"""t.verifiers.fstar, the seventh kernel: F*.

Verdict mapping (F* 2026.08.30 / bundled Z3 4.13.3, measured 2026-08-31 on
the training box in the install audit, re-relied-on here; tactic-admit rows
re-measured 2026-08-31 in the Wave-1 hole-closing pass):
  exit 0 + success line + >=1 solver-logged unsat -> VERIFIED (ban scan clean)
  banned token in SOURCE (admit/assume/magic/expect_failure families,
      option pragmas, warn_error; substring, raw + NFKC)  -> VACUOUS
  diagnostic number 296 at ANY level             -> VACUOUS  (a tactic
      admitted a goal; tadmit/admit_all/tadmit_t land here)
  Error number 335                               -> VACUOUS  (admit()/assume
      term/unsafe_coerce/admit_smt_queries/lax, all measured as 335)
  exit 0 + success line + ZERO solver-logged unsat -> MALFORMED (zero
      discharged obligations is not a proof)
  Error number 19, solver reason canceled/
      resource-limits on any attempt line        -> TIMEOUT  (rlimit verdict)
  Error number 19 otherwise                      -> UNPROVED (a give-up
      signal, not a countermodel; see THE CERTIFICATE below)
  a discharged t_refutation_certificate          -> REFUTED  (the only door)
  a t_refutation_certificate on a file that
      otherwise verifies                         -> MALFORMED
  Error number 168 (syntax) / 72 (resolution)    -> MALFORMED
  Error number 129 (missing input file)          -> TOOL_ERROR
  any other Error number                         -> MALFORMED (the typechecker
      rejected the shape before/around proof; never a refutation)
  nonzero exit with no parseable Error JSON      -> TOOL_ERROR
  wall backstop                                  -> TIMEOUT

THE CERTIFICATE is how a twin earns REFUTED back, adopted here 2026-09-06,
the last column to take ROADMAP 10.7's protocol. Until then Error 19 minted
REFUTED on its own, and 19 is "the SMT solver could not prove the query": F*
prints it whether the goal is false or merely hard, so incompleteness was
being sold as refutation. 12.5's sweep measured the cost at 23 real programs
REFUTED that dafny verifies, every one a nat-typed loop, and the column's 100
twin refutations rested on the same door. The reason it survived the
2026-09-02 purge is that the fuzz corpus never failed an F* proof.

Now `lower_fstar.py` appends, on TWIN calls only and only when the measured
witness is ground, one lemma named exactly t_refutation_certificate whose
statement is the witness instance built by `lower_verus.certificate_formula`,
the same formula every other column certifies, discharged by `assert_norm`
(ground normalisation, no SMT fallback). This adapter mints REFUTED only when
a targeted `--admit_except '<Module>.t_refutation_certificate'` run discharges
that one lemma, and a file declaring the name can never mint VERIFIED.

Measured 2026-09-06 on F* 2026.08.30, Darwin arm64: all 11 committed twins
refute through the certificate, and every decoy behaves: a real with no
certificate VERIFIES, a real carrying a true certificate reads MALFORMED, the
name in a comment changes nothing, and a twin carrying a FALSE certificate
reads UNPROVED rather than REFUTED.

Exit codes are 0/1 only (measured: every failure class exits 1), so
classification comes from the NDJSON diagnostics `--message_format json`
puts on stderr, one object per line, {"msg":[...],"level","range",
"number","ctx"}, never from the exit code beyond "0 = clean". On failing
runs even the progress lines land on stderr, so parsing skips non-JSON
lines. A timeout and a refutation share number 19 and are split by message
text, exactly as measured.

Measured traps this adapter owns:
  * `assume val` verifies at exit 0 UNDER --report_assumes error (measured
    on both a magic-value assume val and an axiom-shaped one), hence the
    lexical ban on the assume/admit/magic families in the SOURCE,
    verus-style, on top of the flag. A hit is VACUOUS regardless of the
    solver's opinion.
  * TACTIC ADMITS (Wave-1 hole, closed 2026-08-31). `assert P by (tadmit())`
    Likewise admit_all(), tadmit_t, and FStar.Tactics.tadmit closed the
    goal at the tactic engine: exit 0, success line, --report_assumes
    silent, and the old \\b-bounded ban blind to `tadmit` (word chars on
    both sides). Three measured layers close it:
      1. the ban is SUBSTRING matching, so tadmit/admit_all/tadmit_t/_admit/
         admit_ and every other identifier embedding a family name is hit;
      2. the engine's own per-goal report, "Tactics admitted goal.",
         number 296, ctx "While running primitive tadmit_t", is scanned at
         EVERY level and is VACUOUS on sight, so an admit primitive reached
         by a name no lexical scan can see (reflection, concatenated
         strings) still cannot verify;
      3. --warn_error @296 on the command line promotes 296 to a hard error
         (measured: exit 1). A file pragma `--warn_error -296` was measured
         to silence 296 entirely AND to override the CLI promotion, which
         is why every option pragma (#set/#push/#pop/#reset-options,
         #restart-solver) and the token warn_error are themselves banned:
         the honest lowering emits no pragma of any kind, and a working
         demotion must spell the pragma in plain ASCII for F* to parse it,
         so the substring scan cannot be evaded by the encoding tricks that
         work on identifiers.
  * POSITIVE OBLIGATION EVIDENCE comes from a channel the source cannot
    write into (Wave-2 hole, closed 2026-08-31). VERIFIED requires at least
    one goal the SOLVER answered unsat: an empty module, a comments-only
    file, or any run that discharged zero obligations is MALFORMED even at
    exit 0 with the success line: file-accepted is not proof-discharged.
    The evidence is --log_queries, which makes F* write the SMT2 it actually
    sent to Z3 into queries-<Module>.smt2 in the run's own scratch cwd and
    append one `; STATUS: <z3 answer>` comment per goal AFTER Z3 answers;
    the count of `^; STATUS: unsat` lines across those files is the gate.

    Why the file and not stdout. The previous gate counted the literal
    string "Query-stats" in stdout+stderr, and STDOUT IS A CHANNEL THE
    SOURCE WRITES INTO: `_ by (print "Query-stats")` and `dump "Query-stats"`
    both scored a false VERIFIED (Q5/Q6). The rejected alternatives were
    measured, not reasoned about:
      - a stricter stdout shape, or "F* summary/exit state": `print` takes an
        arbitrary string with escapes, so Q10 reproduced a full genuine row,
        `(F.fst(9,60-9,65))\\tQuery-stats (Q10.f, 1)\\tgoal 1 succeeded in
        0.00 seconds with fuel 2 and ifuel 1 and rlimit 50 (used rlimit
        0.001)`, and Q11 reproduced "Verified module:" plus the success
        line, both at exit 0. No stdout regex can be made unforgeable, and
        exit codes are 0/1 only, so there is no summary state left to read.
      - structured --message_format json records: measured, F* emits NO json
        record for a discharged query: Query-stats and the success line are
        raw stdout text, and json carries diagnostics only. There is no
        record to harden.
      - the .checked artifact (--cache_checked_modules): measured, Q5b/Q10/
        Q11 each produced a .fst.checked having discharged ZERO queries. It
        attests typechecking, not obligation discharge.
    The query log is unforgeable because the source cannot create a file:
    the tactic engine's only process/IO primitive refuses without a flag
    this adapter never passes, measured "launch_process: will not run
    anything unless --unsafe_tactic_exec is provided", number 228, exit 1
    (Q12). Nor can text be smuggled in: a block comment spelling
    `; STATUS: unsat` twice produced NO query file at all (the log exists
    only once F* issues a query), and with a real query present neither the
    comment text nor a string literal reached the file; only identifiers
    do, and an F* identifier cannot contain a newline or `;`, so it cannot
    forge a line-anchored status. --keep_query_captions false drops the
    source-derived captions anyway and costs 2% instead of 11% (below).
    (A status line is not per-goal attribution: an admitted VC still
    produces a trivially-unsat query, measured, so it gates the zero case
    while layers 1–3 gate the admit case.)
    This is a channel SWAP, not a stricter rule, and that was measured: on
    all eleven t tasks the solver-side unsat count equals the old stdout row
    count exactly: abs 4, factorial 7, max 7, fib 11, gcd 16, sum_upto 33,
    count_matches 35, all_nonneg 45, contains 45, seq_max 81,
    linear_search 125, every real still VERIFIED and every twin REFUTED
    under flake_check. Only exit 0 is read this way; failing twins do log
    partial unsat statuses (measured: linear_search_twin 81 unsat plus 4
    unknown at exit 1), so "every status unsat" would be a wrong and
    needless extra rule that buys nothing at exit 0.
  * `[@@expect_failure]` (the skeptic's catch, 2026-08-31) makes F* accept
    a file whose only theorem is FALSE: checked-to-fail, silently dropped,
    exit 0. Banned by substring, expect_lax_failure explicitly included
    (\\bexpect_failure\\b never matched it).
  * Unicode: the scan runs over the raw decode AND its NFKC normalization,
    so fullwidth/compatibility spellings of a banned name are hit. Cross-
    script homoglyphs (Cyrillic а in `аdmit`) survive NFKC, but F*'s ASCII
    lexer rejects them, measured number 168 on both homoglyph probes, so
    they end MALFORMED, never VERIFIED. Comment/string mentions of banned
    words DO fire the ban (measured on the overfire probes): scanning raw
    text is the conservative direction: a hidden live token can never
    slip through a comment-stripper this adapter does not have.
  * Non-UTF8 bytes (Wave-1 crash, closed 2026-08-31): the scan decodes via
    safe_text (errors=replace) and the scratch copy is written as RAW
    BYTES, so F* judges the same bytes the hash binds to; the measured
    result on the non-UTF8 probe is a lexer error -> MALFORMED, no
    exception.
  * --report_assumes error composed with --cache_off fails EVERY file
    (number 335 on Prims.fst unsafe_coerce), never composed here. Instead
    every verify runs in a fresh scratch directory, so no .checked cache
    can leak between runs (F*'s cache trap, ROADMAP 7.2). The scratch file
    is named after the source's own `module` line because F* binds module
    name to file name; the witness hash binds to the SOURCE bytes.
  * A user-code `unsafe_coerce` body was measured as Error 335 under
    --report_assumes error -> VACUOUS via the 335 row, no ban entry needed.
  * A missing input file is number 129 at exit 1: TOOL_ERROR, never
    MALFORMED.

Budget is --z3rlimit (deterministic solver resource units, the same
doctrine as Dafny's and Verus's rlimit rows); --z3seed and --z3version are
pinned. Two identical failing runs at the pinned seed were measured
byte-identical on stderr, so flake_check re-measures a determinism claim
rather than hoping for one.

Cost of the solver-side evidence: none of a second kernel run: --log_queries
is a flag on the run that already happens, and the adapter's added work is a
glob plus reading at most a few hundred KB (linear_search, the largest t
task, logs 304 KB with captions off). Measured A/B of the whole fstar column
against the pre-fix adapter, medians of three, real+twin under flake_check:
+1.4% over four cells (abs +18 ms, max +3 ms, count_matches -12 ms,
linear_search +88 ms). With captions left on it was +11%, which is why
--keep_query_captions false is passed.
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
import time
import unicodedata
from pathlib import Path

from . import Outcome, Result, safe_text, sha256_file
from .discover import find, missing

_GLOBS = [".local/fstar/fstar/bin/fstar.exe", ".local/fstar/**/bin/fstar.exe"]
FSTAR = find("T_FSTAR", ["fstar.exe", "fstar"], _GLOBS)
_FSTAR_WHY = missing("fstar", "T_FSTAR", ["fstar.exe", "fstar"], _GLOBS)

DEFAULT_RLIMIT = 50        # z3rlimit units; every t task + twin fits (measured)
Z3_VERSION = "4.13.3"      # the bundled default among the three shipped; pinned
Z3_SEED = 42
WALL_S = 120               # hang backstop only, never the verdict

# Substring families, deliberately unbounded (no \b): tadmit, admit_all,
# tadmit_t, _admit, admit_, expect_lax_failure and every embedding are hits.
# The pragma rows exist because a file pragma can demote diagnostic 296 out
# of existence (measured) and the honest lowering emits no pragmas at all.
BANNED = re.compile(
    r"admit|assume|magic|expect_(?:lax_)?failure"
    r"|#\s*(?:set|push|pop|reset)-options|#\s*restart-solver|warn_error")
_MODULE = re.compile(r"^\s*module\s+([A-Za-z0-9_.']+)", re.MULTILINE)
_OK_LINE = "All verification conditions discharged successfully"
# Forgeable (Q5/Q6/Q10 print it): reported for cross-checking, never gating.
_QUERY = re.compile(r"\bQuery-stats\b")
# The gate. One such line per goal, written by F* into queries-<Module>.smt2
# after Z3 answers; line-anchored because an F* identifier, the only source
# text measured to reach the log, cannot contain a newline.
_SOLVER_UNSAT = re.compile(r"^; STATUS: unsat[ \t]*$", re.MULTILINE)
# The one lemma name that can mint REFUTED, and the only door to it
# (ROADMAP 10.7's certificate protocol, adopted here 2026-09-06). Until then
# Error 19 alone minted REFUTED, and 19 is "the SMT solver could not prove the
# query", a give-up signal. 12.5 measured the cost: 23 reals REFUTED that
# dafny verifies. A file carrying this name can never mint VERIFIED.
CERT_NAME = "t_refutation_certificate"
_CERT_DECL = re.compile(r"^\s*let\s+t_refutation_certificate\s*\(\)\s*:\s*Lemma\b",
                        re.M)

TACTIC_ADMIT_NUM = 296     # "Tactics admitted goal.", measured on tadmit
# Under --query_stats every error-19 msg carries per-attempt reason lines
# ("unknown because canceled (rlimit=1; ...)" at rlimit exhaustion,
# "unknown because (incomplete quantifiers) (rlimit=50; ...)" at a real
# refutation, both measured 2026-08-31) PLUS a fixed advisory Note whose
# prose contains the literal words "timed out", 'canceled' and 'resource
# limits reached'. So the timeout/refutation split reads ONLY the reason
# lines: a whole-message "timed out" scan misclassified the false-baseline
# probe as TIMEOUT the moment --query_stats went on.
_UNKNOWN = re.compile(r"unknown because (.*?) ?\(rlimit=")


def _rlimit_timeout(msg: str) -> bool:
    reasons = _UNKNOWN.findall(msg)
    if reasons:
        return any("canceled" in r or "resource" in r or "timeout" in r
                   for r in reasons)
    # no solver reason lines (a 19 not shaped by --query_stats): the old
    # measured discriminator, with the advisory Note cut away first
    return "timed out" in msg.split("Note:")[0]


def version() -> str:
    if not FSTAR:
        raise SystemExit(_FSTAR_WHY)
    p = subprocess.run([FSTAR, "--version"], capture_output=True, text=True)
    return " / ".join(l.strip() for l in p.stdout.strip().splitlines())


def _check_certificate(fname: str, cwd: str, module: str,
                       budget: int) -> tuple[bool, str]:
    """One targeted kernel run of the certificate lemma alone.

    `--admit_except '<Module>.t_refutation_certificate'` admits every other
    query in the file, so the kernel's verdict is a verdict ON the
    certificate and a twin whose own proof fails (which is the whole point of
    a twin) cannot drag it down. Measured 2026-09-06 on F* 2026.08.30: a true
    ground certificate discharges, a false one is rejected Error 19 "Failed
    to prove: Prims.l_False", and on the real abs twin, whose own proof fails
    19, the targeted run discharges the certificate alone.

    Returns (accepted, why). Anything short of a clean discharge is False, so
    a rejected or unrunnable certificate costs a flip and never fakes one."""
    try:
        p = subprocess.run(
            # NOT --report_assumes error here: F* makes any use of
            # --admit_except itself an assume (Error 335, "Every use of this
            # option triggers an error: admit_except"), so the two flags
            # cannot both be on. Dropping it is safe because the MAIN run
            # already screened this exact file: a banned token or a 335 or a
            # 296 mints VACUOUS before the gate below is ever reached, so a
            # file that gets here carries no admit, no assume and no
            # tactic-admitted goal.
            [FSTAR, "--message_format", "json",
             "--z3version", Z3_VERSION, "--z3seed", str(Z3_SEED),
             "--z3rlimit", str(budget),
             "--warn_error", f"@{TACTIC_ADMIT_NUM}",
             "--admit_except", f"{module}.{CERT_NAME}", fname],
            capture_output=True, text=True, timeout=WALL_S, cwd=cwd)
    except subprocess.TimeoutExpired:
        return False, "certificate run hit the wall backstop"
    out = p.stdout + p.stderr
    if p.returncode != 0:
        return False, "the kernel did not accept the certificate lemma"
    if "All verification conditions discharged successfully" not in out:
        return False, "certificate run printed no discharge line"
    return True, ""


def verify(path: Path, budget: int = DEFAULT_RLIMIT) -> Result:
    if not FSTAR:
        raise SystemExit(_FSTAR_WHY)
    src_hash = sha256_file(path)
    raw = path.read_bytes()
    src_text = safe_text(path)
    banned = sorted(set(BANNED.findall(src_text))
                    | set(BANNED.findall(unicodedata.normalize("NFKC",
                                                               src_text))))
    m = _MODULE.search(src_text)
    fname = (m.group(1) + ".fst") if m else "T_unit.fst"
    bud = f"z3rlimit={budget} z3seed={Z3_SEED} z3={Z3_VERSION}"
    t0 = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="t-fstar-") as td:
        # raw bytes, not the decoded scan text: F* must judge exactly the
        # bytes src_hash binds to (non-UTF8 then fails ITS lexer -> MALFORMED)
        (Path(td) / fname).write_bytes(raw)
        try:
            p = subprocess.run(
                [FSTAR, "--message_format", "json",
                 "--z3version", Z3_VERSION, "--z3seed", str(Z3_SEED),
                 "--z3rlimit", str(budget), "--report_assumes", "error",
                 "--warn_error", f"@{TACTIC_ADMIT_NUM}", "--query_stats",
                 "--log_queries", "--keep_query_captions", "false",
                 fname],
                capture_output=True, text=True, timeout=WALL_S, cwd=td)
        except subprocess.TimeoutExpired:
            return Result("fstar", version(), src_hash, Outcome.TIMEOUT,
                          wall_ms=int((time.monotonic() - t0) * 1000),
                          budget=bud, error="wall backstop fired")
        # Read the solver-side log INSIDE the scratch context, because the directory
        # the source could not write into is about to be destroyed. F* names
        # the log after the module, so glob rather than trust the name.
        logs = sorted(Path(td).glob("queries-*.smt2"))
        discharged = sum(len(_SOLVER_UNSAT.findall(safe_text(f))) for f in logs)
        # The certificate's targeted run has to happen while the scratch
        # directory still exists, so it runs here and the gate below reads
        # the answer. Only when the file actually declares the lemma, so a
        # file without one costs no second kernel run.
        _cert_result = ((False, "no certificate")
                        if not _CERT_DECL.search(src_text)
                        else _check_certificate(fname, td,
                                                fname[:-len(".fst")], budget))
    wall = int((time.monotonic() - t0) * 1000)

    errs: list[tuple[int, str]] = []
    admitted = False           # diagnostic 296 at ANY level, error or not
    for line in p.stderr.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue                       # progress lines share stderr on failure
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("number") == TACTIC_ADMIT_NUM:
            admitted = True
        if d.get("level") == "Error":
            errs.append((d.get("number", -1), " ".join(d.get("msg") or [])))
    nums = {n for n, _ in errs}
    queries = len(_QUERY.findall(p.stdout)) + len(_QUERY.findall(p.stderr))

    if banned:
        outcome = Outcome.VACUOUS
    elif admitted:
        # the engine itself said a tactic closed a goal without proof; this
        # holds even if a missed spelling got the admit primitive executed
        outcome = Outcome.VACUOUS
    elif p.returncode == 0:
        if _OK_LINE not in p.stdout:
            # exit 0 was measured clean-only; the stdout line is a witness
            outcome = Outcome.TOOL_ERROR
        elif discharged == 0:
            # accepted, but the solver answered unsat for nothing, not a
            # proof. Counted from the query log, never from stdout: Q5/Q6/Q10
            # print their own "Query-stats" rows and scored VERIFIED under the
            # stdout counter.
            outcome = Outcome.MALFORMED
        else:
            outcome = Outcome.VERIFIED
    elif 335 in nums:
        outcome = Outcome.VACUOUS
    elif any(n == 19 and _rlimit_timeout(msg) for n, msg in errs):
        # a run the budget muddied is never counted as a refutation
        outcome = Outcome.TIMEOUT
    elif 19 in nums:
        # THE DOOR, closed 2026-09-06 (ROADMAP 10.7's protocol). Error 19 is
        # "the SMT solver could not prove the query": a give-up signal, not a
        # countermodel, and F* prints the same 19 whether the goal is false
        # or merely hard. Minting REFUTED from it sold incompleteness as
        # refutation, which 12.5 measured at 23 reals REFUTED that dafny
        # verifies, every one a nat-typed loop. It now mints UNPROVED, and
        # REFUTED is earned below through the certificate alone.
        outcome = Outcome.UNPROVED
    elif nums & {168, 72}:
        outcome = Outcome.MALFORMED
    elif 129 in nums:
        outcome = Outcome.TOOL_ERROR
    elif errs:
        outcome = Outcome.MALFORMED
    else:
        outcome = Outcome.TOOL_ERROR
    # The certificate gate (ROADMAP 10.7). Two directions, both one-way:
    # a file carrying the name can never mint VERIFIED, and a twin earns
    # REFUTED only when a targeted run discharges that one lemma.
    cert_detail = {}
    if _CERT_DECL.search(src_text):
        if outcome == Outcome.VERIFIED:
            # a certificate is a claim that the file's own theorem is FALSE
            # at the witness; a file that also verifies is incoherent.
            outcome = Outcome.MALFORMED
            cert_detail = {"certificate": "present on a file that verified"}
        elif outcome in (Outcome.UNPROVED, Outcome.TIMEOUT):
            accepted, why = _cert_result
            if accepted:
                outcome = Outcome.REFUTED
                cert_detail = {"certificate": "accepted"}
            else:
                cert_detail = {"certificate": "rejected: " + why}

    return Result("fstar", version(), src_hash, outcome,
                  ok=outcome == Outcome.VERIFIED, exit_code=p.returncode,
                  wall_ms=wall, budget=bud,
                  error=("" if outcome != Outcome.TOOL_ERROR
                         else (p.stderr + p.stdout)[-400:]),
                  extras={"errors": [(n, msg[:200]) for n, msg in errs[:5]],
                          "banned_tokens": banned[:5],
                          "tactic_admitted": admitted,
                          "solver_unsat": discharged,
                          "query_logs": len(logs),
                          # forgeable; kept so a forgery is legible in the
                          # witness as stdout_query_rows > solver_unsat
                          "stdout_query_rows": queries,
                          **cert_detail})
