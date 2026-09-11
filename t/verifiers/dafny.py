"""t.verifiers.dafny: the first kernel, exit codes measured not assumed.

Checked 2026-09-11 (ensures-level undefined-witness probes, lower_dafny.py's
`_certificate`): this module reads REFUTED off the presence of a proved
`t_refutation_certificate` lemma alone (see CERT_NAME/_CERT below), never off
where in the task the witness's obligation lived (body vs. ensures), so the
ensures-site certificate lower_dafny.py now emits mints REFUTED through this
SAME door as every other refutation certificate, with no change needed here.

Mapping (dafny 4.11.0; the exit codes were measured in dafny_verify.py and
re-relied-on here, the REFUTED door measured 2026-09-02 on the training box
with the small probe files this docstring describes), in the order verify()
applies it:
    wall backstop fired            -> TIMEOUT
    any banned source token        -> VACUOUS (whatever the exit code)
    2                              -> MALFORMED (parse/resolution, and also
                                      any warning: dafny's default is
                                      --allow-warnings false, so a warning
                                      alone ends the run at exit 2)
    t_refutation_certificate named -> never VERIFIED. MALFORMED when the
                                      main run itself verified: nothing
                                      failed for a certificate to explain
                                      (the coherence gate, 2026-09-07).
                                      Otherwise REFUTED if and only
                                      if the isolated certificate run below
                                      is accepted; otherwise TIMEOUT when
                                      the main run said "out of resource"
                                      at exit 4, UNPROVED at exit 0 or 4,
                                      TOOL_ERROR for any other exit
    0 (name absent)                -> VERIFIED only when the verifier's own
                                      tally shows >= 1 obligation discharged,
                                      0 errors and no contradictory-
                                      assumptions warning; tally absent is
                                      TOOL_ERROR, "0 verified" is MALFORMED,
                                      the warning is VACUOUS
    4 (name absent)                -> TIMEOUT on "out of resource", else
                                      UNPROVED. Never REFUTED.
    anything else                  -> TOOL_ERROR

The deterministic budget is Z3's resource limit (--resource-limit), because
wall-clock is nondeterministic and rlimit is not: dafny_verify.py's finding,
inherited whole. --warn-contradictory-assumptions is passed on every run,
and what it does was measured 2026-09-02 on 4.11.0: it fires for an
unsatisfiable requires that Z3's unsat core isolates from the goal
(`requires false` next to a different ensures), and since this adapter
passes no --allow-warnings that warning ends the run at exit 2; it never
fires for `ensures true`, which verifies at exit 0 with no warning at all
(measured on a method and on the certificate lemma alike), and it stays
silent whenever the goal is itself in the core (`requires P ensures P`).
Vacuity of that kind is closed by the certificate shape rules below, not by
the warning.

EXIT 4 IS NOT A REFUTATION (2026-09-02). Until this date the adapter mapped
exit 4 to REFUTED. Reproduced that morning: the truth_fuzz task gt_q_ex_lit
(true by construction: ensures r == 0 and exists i in [0,3) :: i == 2, body
r := 0) exits 4 on 4.11.0 because Z3 does not instantiate the existential
unprompted, and the old rule sold that incompleteness as a refutation. Exit
4 is could-not-prove: the kernel prints no countermodel and offers no flag
that separates a false postcondition from a true one it failed to prove.
So a bare exit 4 now reads UNPROVED (the solver stopped, budget intact, no
countermodel, not knowledge either way), and the same true task measured
under this file reads UNPROVED at exit 4.

THE REFUTATION CERTIFICATE is the only door to REFUTED, per the protocol the
other columns adopted the same day: lower_dafny.py, when handed a measured
twin witness, appends one parameterless lemma named exactly
t_refutation_certificate whose ensures restates the witness as a ground
theorem (the spec's obligation fails at the measured input on the file's
own twin; see the certificate section there for what each witness kind
certifies and for the three Dafny-specific steps, unrolling, pruning and
the assert ladder). This adapter mints REFUTED if and only if the kernel
accepts that lemma in a second, isolated run:

    dafny verify --filter-symbol=t_refutation_certificate. --log-format text
        --resource-limit <budget> --warn-contradictory-assumptions <file>

The evidence is the kernel's, not a regex over the source. The main run
adds `--rprint <tempfile>` and `--log-format text`: --rprint writes the
program as the resolver saw it (comments gone, one declaration per block
at column 0, every clause on its own two-space line, measured on 4.11.0),
and --log-format text prints one "Results for <symbol> (<kind>)" block per
verified symbol with an "Overall outcome:" of Correct, Errors or
OutOfResource, the symbol qualified by its module and class ("M.C.cm").
Accepted when ALL of:

  shape, read from the kernel's --rprint of the main run:
    every column-0 declaration is an unmodified `function`, `method` or
    `lemma` (the honest lowering's whole vocabulary; a module, class,
    trait, datatype, type, const, iterator, import or any modifier such as
    ghost, static, twostate, least, greatest refuses), names are unique,
    and exactly one declaration is `lemma t_refutation_certificate()`
    (parameterless; no other name contains the string), whose header is
    exactly one `ensures` clause: no requires, no second ensures, no
    decreases, nothing else;
  attribution, read from the kernel's --log-format text of the main run:
    every "Results for" block whose outcome is not Correct names a plain
    `method` of that declaration list (the honest twin's failures are all
    in its one method, and "in a lemma, calls are allowed only to lemmas"
    is a resolution error, measured, so no lemma or function can depend on
    a method); the block "t_refutation_certificate (correctness)" is
    present; a tally that reports errors no block accounts for refuses;
    the main run printed no Warning line (a bodyless lemma, the axiom
    without the word, is a warning, and at exit 4 the twin's own error
    would otherwise hide it);
  the isolated run:
    exits 0, prints the finish line with verified >= 1 and errors == 0,
    every one of its "Results for" blocks names exactly
    t_refutation_certificate (the filter's start is unanchored, below) with
    outcome Correct, one of them the (correctness) block, and no
    contradictory-assumptions warning;
  and the file carries no banned token.

Why the shape and attribution rules exist (each door measured open on the
previous version of this adapter, 2026-09-02, and refused by this one):
a declaration regex over the raw source counted `// lemma
t_refutation_certificate()` in a comment, so a correct program plus that
comment plus a decoy `lemma xt_refutation_certificate() ensures true {}`
minted REFUTED with no certificate in the file, and a `method
t_refutation_certificate()` resting on a failing plain method did the same;
a line-start header scan attributed a helper lemma's failure to the
preceding method when the helper shared the method's closing line (`}
lemma h() ...`) or when form feeds in comments skewed Python's line count
away from Dafny's, so `lemma h() ensures fact(20) == 1 {}` let a false
certificate through; and nothing read the certificate's header, so
`requires g(0) == 1 ensures g(0) == 1` (unsatisfiable, no warning),
`requires false ensures false`, a bodyless `function g(): int` with
`requires g() == 5 ensures g() == 5`, and an uninitialized `const c: int`
with `requires c == 5` all minted REFUTED. The rprint carries none of the
source's comments (its own prelude comments are masked before the walk),
no line numbers to skew and no lexical tricks to hide a clause, and the
log names the failing symbol itself.

--filter-symbol, measured on 4.11.0 with two- and three-declaration files:
the flag verifies only symbols whose qualified name CONTAINS the string, exit
codes unchanged (0 verified, 2 parse/resolution or warning, 4 verification
failed), one finish line per run. The bare name also matched a decoy
t_refutation_certificate_extra ("1 verified, 1 error" when the decoy
failed); a trailing dot anchors the END of the name ("1 verified, 0 errors"
on the same file), which is why the run passes the name with a dot. The
start is not anchored: xt_refutation_certificate matched too, and a
nested M.t_refutation_certificate matched "t_refutation_certificate." while
"_module.t_refutation_certificate." and ".t_refutation_certificate."
matched nothing at top level, and the companion symbol a least lemma
gets ("t_refutation_certificate#", the prefix predicate) matched the dotted
form as well; this is why the isolated run's blocks must all name the
exact symbol. A name that appears in no declaration gives
"0 verified, 0 errors" at exit 0, which fails the verified >= 1 bar. The
count for the one honest lemma reads "1 verified" or "2 verified"
(--log-format text shows dafny splitting off a "(well-formedness)" task
when the ensures carries an index-in-range obligation, seq_max and
linear_search here), so the bar is >= 1 with errors == 0, not == 1.

What the isolated run assumes, and the closure for it: under the filter
the kernel proves the lemma from every callee contract and every function
definition in the file WITHOUT re-verifying them, so a helper lemma with
`ensures false` whose own proof fails, or a function with no valid
decreases (f(n) = f(n) + 1), would let a false certificate through the
isolated run. Measured, dafny's proof-dependency check caught both
("ensures clause proved using contradictory assumptions", exit 2), but that
check rests on Z3's unsat core, which this adapter does not assume minimal.
The closure is the attribution rule above: every failing symbol of the main
run must be a plain method, which nothing the certificate can call or
unfold depends on, so every fact the certificate rests on was verified in
the main run or is a bodyless function without an ensures (uninterpreted,
consistent; a bodyless anything WITH an ensures is a warning, measured:
"This ensures clause is part of a bodyless method", also for a static
lemma in a trait or class).

Two closures make the name safe: a file carrying the certificate name (raw
NFKC-normalized text, comments included) can NEVER mint VERIFIED, so
planting it in a real program only demotes that program (measured: the
honest lemma copied into a verified real program reads MALFORMED, never
VERIFIED; it read REFUTED until the coherence gate of 2026-09-07, which
refuses a certificate on a file the main run verified); and a certificate
the kernel rejects or cannot read mints
UNPROVED, never REFUTED (measured on the abs twin: `ensures 1 == 2` reads
UNPROVED; every requires form named above reads UNPROVED, `requires false`
with the honest ensures at exit 2 of the isolated run and the rest by the
shape rule; the declaration text in a comment, with or without the decoy
xt_refutation_certificate lemma, reads UNPROVED; a method-typed,
parameterised, twostate or least certificate reads UNPROVED; a failing
helper lemma on the method's closing line or behind form-feed comments
reads UNPROVED; a non-terminating function next to the certificate reads
UNPROVED). What the adapter cannot check is that the asserted formula IS
the negated spec at the witness (a content-free `ensures true` certificate
is a theorem the kernel accepts and this adapter cannot tell it from the
honest one), and, for value witnesses, that the twin method computes the r
the formula names (a method is not callable from a lemma): that binding
lives in the trusted lowering, the same trust already extended to every
lowered obligation.

Positive evidence (Wave-1 audit, 2026-08-31): exit 0 alone is NOT proof.
Measured on dafny 4.11.0, an empty file and a comments-only file both exit 0
printing "0 verified, 0 errors", and the old exit-0-is-VERIFIED rule scored
them VERIFIED. VERIFIED therefore requires the verifier's finish line
("Dafny program verifier finished with N verified, M errors") with N >= 1 and
M == 0. That tally is dafny's own stdout and `dafny verify` never executes
user code, so the source cannot print or suppress it; exit 0 with the line
absent is TOOL_ERROR, exit 0 with N == 0 is MALFORMED (zero obligations
discharged is not a proof). This check is the guarantee: even a ban token the
regex misses cannot conjure a discharged obligation out of "0 verified".

Ban regex (second line, same audit): opaque + lemma {:axiom} / assume
{:axiom} admits a false fact that --warn-contradictory-assumptions cannot see
(probes h7/h8/h9/h11 all exited 0 with "N verified" for a false theorem), and
{:verify false} / {:extern} / @Axiom / {:only} are stopped today only
incidentally, by warnings-as-errors at exit 2. Also measured: `include` pulls
a false axiom in from a file this scan never reads (the e6 probe exits 0
with "2 verified, 0 errors" and no ban token in the included-from file), so
`include` is banned outright. The regex bans the ENTIRE {:...} and @Attr
pragma surfaces (honest lowerings emit no attribute of any kind), plus the
keywords assume/axiom/opaque/reveal/extern/include, case-insensitively
(@Axiom is capitalized; `{ : axiom }` is a measured parse error but the
tolerant form costs nothing). The scan text is NFKC-normalized safe_text:
NFKC folds fullwidth homoglyph spellings back to ASCII, and a keyword dafny
itself acts on is necessarily ASCII, so the raw bytes cannot hide one. The
ban scan runs on the SOURCE, never on the rprint: the resolver's own print
carries {:trigger} and, inside its commented prelude, {:axiom}. A bodyless
lemma (an axiom without the word) is a warning and therefore exit 2,
measured 2026-09-02 ("This ensures clause is part of a bodyless method").

Cost of the door, measured 2026-09-02 sequentially through this adapter on
the abs, seq_max, linear_search and count_matches twins, three runs each:
the isolated run averages 1056 ms (978 to 1101) against 1113 ms (1027 to
1173) for the main run with its rprint and text log, so a twin verify call
costs about twice what it did and a flake-checked twin cell about 3 s
more. The suite of 11 tasks ran in about 2 minutes on the same box.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
import time
import unicodedata
from pathlib import Path

from . import Outcome, Result, safe_text, sha256_file, run_tree
from .discover import find, missing

DAFNY = find("T_DAFNY", ["dafny"], [".local/dafny/dafny"])
_DAFNY_WHY = missing("dafny", "T_DAFNY", ["dafny"], [".local/dafny/dafny"])

DEFAULT_RLIMIT = 500_000   # Z3 resource units; deterministic where seconds are not
WALL_S = 120               # hang backstop only, never the verdict

# Source tokens that can admit an unproved fact or skip/outsource an
# obligation (measured per docstring). Honest lower_dafny.py output contains
# no attributes, no @-forms, no strings, no comments, and none of these words.
BANNED_RE = re.compile(
    r"\{\s*:\s*\w+"                 # every {:attr} pragma ({:axiom}, {:verify false}, {:extern}, {:only}, ...)
    r"|@\s*[A-Za-z_]\w*"            # every 4.10+ @Attribute form (@Axiom, @Verify(false), ...)
    r"|\binclude\b"                 # imports source this scan never sees (e6: exit 0, "2 verified")
    r"|\bassume\w*"                 # assume statement, assume {:axiom}, {:assume_concurrent}
    r"|\b(?:axiom|opaque|reveal|extern)\b",
    re.IGNORECASE)

# Dafny 4.11.0's own tally line, printed exactly once per run (measured):
#   "Dafny program verifier finished with 1 verified, 0 errors"
FINISH_RE = re.compile(r"finished with (\d+) verified, (\d+) error")

# The one lemma name that can mint REFUTED (module docstring, certificate
# section). The raw-text scan only ever DEMOTES: it bars VERIFIED for any
# file carrying the name, comments included, fail-closed. Minting needs the
# kernel's own declaration listing AND its acceptance in the isolated run.
CERT_NAME = "t_refutation_certificate"
_CERT = re.compile(r"\bt_refutation_certificate\b")

# --log-format text (measured on 4.11.0): one block per verified symbol,
#   "Results for <symbol> (<kind>)" then "  Overall outcome: <Outcome>".
_RESULT_HEAD = re.compile(r"^Results for (\S+) \(([^)]*)\)\s*$")
_RESULT_OUTCOME = re.compile(r"^\s+Overall outcome:\s*(\S+)")

# --rprint (measured on 4.11.0): every declaration starts at column 0 with
# its modifiers, keyword and name; its clauses follow one per line indented
# by exactly two spaces; its body opens with a `{` line at column 0.
_HONEST_KINDS = ("function", "method", "lemma")
_RP_HEAD = re.compile(
    r"^((?:(?:ghost|static|twostate|least|greatest|opaque|abstract)\s+)*)"
    r"(function|method|lemma|predicate|constructor|class|trait|datatype|"
    r"codatatype|newtype|type|const|module|iterator|import|export)\b\s*"
    r"([A-Za-z_][\w'?#]*)?(.*)$")
_RP_CLAUSE = re.compile(r"^  ([a-z]+)\b")
_CERT_HEAD = re.compile(r"^lemma t_refutation_certificate\(\)\s*$")


def version() -> str:
    if not DAFNY:
        raise SystemExit(_DAFNY_WHY)
    p = subprocess.run([DAFNY, "--version"], capture_output=True, text=True)
    return f"dafny {p.stdout.strip()}"


def _mask_inert(s: str) -> str:
    """Blank //-comments, nested /* */ comments, "..." strings and char
    literals of a kernel-printed program, replacing each inert character
    with a space and keeping every newline. The rprint's own comments
    (the commented _System prelude, the call graphs, the /*** ... ***/
    expansion of a least lemma, the /*-- non-null type */ note after a
    class) carry declaration-looking lines at column 0, which is why they
    must go before the declaration walk. Mis-lexing fails closed in the
    walk below: an exposed comment yields a declaration the vocabulary
    rule or the name rule refuses, a hidden declaration loses the method a
    failing symbol must be attributed to."""
    out: list[str] = []
    i, n = 0, len(s)

    def blank(seg: str) -> None:
        out.append("".join(c if c == "\n" else " " for c in seg))

    while i < n:
        c = s[i]
        if s.startswith("//", i):
            j = s.find("\n", i)
            j = n if j < 0 else j
            blank(s[i:j])
            i = j
        elif s.startswith("/*", i):
            depth, j = 1, i + 2
            while j < n and depth:
                if s.startswith("/*", j):
                    depth += 1
                    j += 2
                elif s.startswith("*/", j):
                    depth -= 1
                    j += 2
                else:
                    j += 1
            blank(s[i:j])
            i = j
        elif c == '"':
            j = i + 1
            while j < n and s[j] not in '"\n':
                j += 2 if s[j] == "\\" else 1
            j = min(j + 1, n)
            blank(s[i:j])
            i = j
        elif c == "'" and (i == 0 or not (s[i - 1].isalnum()
                                          or s[i - 1] in "_'?")):
            # a char literal: 'x' or an escape such as '\n', '\'', '\U{1F600}'
            j = i + 1
            if j < n and s[j] == "\\":
                k = s.find("'", j + 2)
            else:
                k = s.find("'", j)
            if 0 < k and k - i <= 14 and "\n" not in s[i:k]:
                blank(s[i:k + 1])
                i = k + 1
            else:
                out.append(c)
                i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _rprint_decls(text: str) -> tuple[list[dict], list[str]]:
    """Walk the kernel's --rprint (masked): one dict per column-0
    declaration (mods, kind, name, head, clauses, body) and the column-0
    lines the walk could not read, which refuse the certificate."""
    decls: list[dict] = []
    stray: list[str] = []
    cur: dict | None = None
    for line in _mask_inert(text).split("\n"):
        if not line.strip():
            continue
        if line[0] in " \t":
            if cur is not None and not cur["body"]:
                m = _RP_CLAUSE.match(line)
                if m:
                    cur["clauses"].append(m.group(1))
            continue
        if line.strip() == "{":
            if cur is not None:
                cur["body"] = True
            continue
        if line.strip() == "}":
            continue
        m = _RP_HEAD.match(line)
        if not m:
            stray.append(line.strip()[:80])
            continue
        cur = {"mods": m.group(1).split(), "kind": m.group(2),
               "name": m.group(3), "head": line.rstrip(),
               "clauses": [], "body": "{" in m.group(4)}
        decls.append(cur)
    return decls, stray


def _symbol_outcomes(out: str) -> list[tuple[str, str, str]]:
    """(symbol, kind, outcome) per "Results for" block of a --log-format
    text run; a block without an outcome line reads as outcome ''."""
    blocks: list[tuple[str, str, str]] = []
    for line in out.splitlines():
        m = _RESULT_HEAD.match(line)
        if m:
            blocks.append((m.group(1), m.group(2), ""))
            continue
        m = _RESULT_OUTCOME.match(line)
        if m and blocks and not blocks[-1][2]:
            sym, kind, _ = blocks[-1]
            blocks[-1] = (sym, kind, m.group(1))
    return blocks


def _certificate_shape(rprint: str | None) -> tuple[list[str], str]:
    """The plain-method names of the kernel's resolved program, and '' when
    the program has the honest shape around exactly one certificate lemma
    (module docstring, "shape"); otherwise the first reason."""
    if rprint is None:
        return [], "the main run left no --rprint to read"
    decls, stray = _rprint_decls(rprint)
    if stray:
        return [], "unreadable line in the kernel's rprint: " + stray[0]
    if not decls:
        return [], "the kernel's rprint declares nothing"
    methods: list[str] = []
    names: set[str] = set()
    cert: list[dict] = []
    for d in decls:
        if d["mods"] or d["kind"] not in _HONEST_KINDS or not d["name"]:
            return [], ("declaration outside the honest vocabulary: "
                        + d["head"][:80])
        if d["name"] in names:
            return [], f"name declared twice: {d['name']}"
        names.add(d["name"])
        if CERT_NAME in d["name"]:
            if d["name"] != CERT_NAME:
                return [], f"a name contains the certificate name: {d['name']}"
            cert.append(d)
        if d["kind"] == "method":
            methods.append(d["name"])
    if len(cert) != 1:
        return methods, f"no `lemma {CERT_NAME}()` in the kernel's rprint"
    c = cert[0]
    if c["kind"] != "lemma" or not _CERT_HEAD.match(c["head"]):
        return methods, "the certificate is not `lemma " + CERT_NAME + "()`: " + c["head"][:80]
    if c["clauses"] != ["ensures"]:
        return methods, ("the certificate header must be exactly one "
                         f"ensures clause, found {c['clauses']}")
    return methods, ""


def _failing_non_methods(out: str, methods: list[str],
                         n_errors: int) -> list[str]:
    """The main run's failing symbols this adapter cannot attribute to a
    plain method of the kernel's own declaration list (module docstring,
    "attribution"), plus the structural refusals: no result block at all,
    no (correctness) block for the certificate, a Warning line, or a tally
    that reports errors no block accounts for."""
    blocks = _symbol_outcomes(out)
    bad = [f"{sym} ({kind}): {oc or 'no outcome'}"
           for sym, kind, oc in blocks
           if oc != "Correct" and not (oc in ("Errors", "OutOfResource")
                                       and sym in methods)]
    if not blocks:
        bad.append("the main run printed no Results block")
    if (CERT_NAME, "correctness") not in {(s, k) for s, k, _ in blocks}:
        bad.append(f"no Results block for {CERT_NAME} (correctness)")
    if n_errors > 0 and all(oc == "Correct" for _, _, oc in blocks):
        bad.append(f"tally reports {n_errors} error(s) no Results block "
                   "accounts for")
    warn = next((l for l in out.splitlines() if "Warning:" in l), None)
    if warn is not None:
        bad.append("main run warned: " + warn.strip()[:100])
    return bad


def _check_certificate(path: Path, budget: int, banned: list,
                       main_out: str, main_errors: int,
                       rprint: str | None) -> tuple[bool, dict]:
    """One isolated kernel run of the certificate lemma alone
    (--filter-symbol with the end-anchoring dot). Accepted means the kernel
    discharged it under every condition the module docstring lists; anything
    else, the wall backstop and a missing tally included, is not-accepted,
    which the caller maps to UNPROVED (or TIMEOUT) and never to REFUTED."""
    methods, shape_why = _certificate_shape(rprint)
    detail: dict = {"present": True, "declared": not shape_why,
                    "plain_methods": methods[:8]}
    if shape_why:
        detail["shape_why"] = shape_why
    outside = _failing_non_methods(main_out, methods, main_errors)
    detail["main_errors_outside_methods"] = outside[:5]
    t0 = time.monotonic()
    try:
        p = run_tree(
            [DAFNY, "verify", f"--filter-symbol={CERT_NAME}.",
             "--log-format", "text",
             "--resource-limit", str(budget),
             "--warn-contradictory-assumptions", str(path)],
            capture_output=True, text=True, timeout=WALL_S)
    except subprocess.TimeoutExpired:
        detail.update(accepted=False,
                      cert_ms=int((time.monotonic() - t0) * 1000),
                      why="certificate run hit the wall backstop")
        return False, detail
    out = p.stdout + p.stderr
    vac = [l for l in out.splitlines()
           if "contradictory assumption" in l.lower()]
    fin = FINISH_RE.search(out)
    n_verified = int(fin.group(1)) if fin else -1
    n_errors = int(fin.group(2)) if fin else -1
    blocks = _symbol_outcomes(out)
    detail.update(cert_ms=int((time.monotonic() - t0) * 1000),
                  cert_exit=p.returncode, verified_count=n_verified,
                  error_count=n_errors, vacuity_warnings=vac[:5],
                  cert_symbols=[f"{s} ({k}): {oc}" for s, k, oc in blocks][:5])
    why = ""
    if shape_why:
        why = shape_why
    elif outside:
        why = "main run has a failure outside a plain method: " + outside[0]
    elif p.returncode != 0:
        why = f"certificate run exited {p.returncode}: " + \
            out.split("\nResults for ", 1)[0][-300:]
    elif fin is None:
        why = "certificate run printed no 'N verified, M errors' line"
    elif n_verified < 1 or n_errors != 0:
        why = f"certificate run tallied {n_verified} verified, {n_errors} errors"
    elif not blocks or (CERT_NAME, "correctness") not in {
            (s, k) for s, k, _ in blocks}:
        why = f"certificate run has no Results block for {CERT_NAME} (correctness)"
    elif any(s != CERT_NAME or oc != "Correct" for s, _, oc in blocks):
        why = "certificate run verified something else: " + \
            detail["cert_symbols"][0]
    elif vac:
        why = "certificate proved using contradictory assumptions"
    elif banned:
        why = "banned token in source"
    accepted = not why
    detail["accepted"] = accepted
    if why:
        detail["why"] = why
    return accepted, detail


def verify(path: Path, budget: int = DEFAULT_RLIMIT) -> Result:
    if not DAFNY:
        raise SystemExit(_DAFNY_WHY)
    src_hash = sha256_file(path)
    # safe_text, not read_text: Wave-1's non-UTF8 probes crashed the scan.
    # NFKC folds homoglyph spellings; sha256 above still binds raw bytes.
    src = unicodedata.normalize("NFKC", safe_text(path))
    banned = sorted({m.group(0) for m in BANNED_RE.finditer(src)})
    cert_present = _CERT.search(src) is not None
    # The resolver's own print of the program, the declaration evidence
    # for the certificate door (module docstring); a temp file because
    # --rprint writes nowhere else.
    fd, rp_name = tempfile.mkstemp(prefix="t_rprint_", suffix=".dfy")
    os.close(fd)
    rprint: str | None = None
    t0 = time.monotonic()
    try:
        p = run_tree(
            [DAFNY, "verify", "--resource-limit", str(budget),
             "--warn-contradictory-assumptions",
             "--rprint", rp_name, "--log-format", "text", str(path)],
            capture_output=True, text=True, timeout=WALL_S)
        try:
            rprint = Path(rp_name).read_text(encoding="utf-8",
                                             errors="replace")
        except OSError:
            rprint = None
    except subprocess.TimeoutExpired:
        return Result("dafny", version(), src_hash, Outcome.TIMEOUT,
                      wall_ms=int((time.monotonic() - t0) * 1000),
                      budget=f"rlimit={budget}", error="wall backstop fired")
    finally:
        try:
            os.unlink(rp_name)
        except OSError:
            pass
    wall = int((time.monotonic() - t0) * 1000)
    out = p.stdout + p.stderr
    diag = out.split("\nResults for ", 1)[0]   # the diagnostics, not the log
    vac = [l for l in out.splitlines() if "contradictory assumption" in l.lower()]
    fin = FINISH_RE.search(out)
    n_verified = int(fin.group(1)) if fin else -1
    n_errors = int(fin.group(2)) if fin else -1
    oor = "out of resource" in diag.lower()
    err = ""
    cert: dict = {"present": cert_present}
    if banned:
        # A banned construct can admit or skip an obligation, so nothing
        # dafny says about this file is evidence, whatever the exit code.
        outcome = Outcome.VACUOUS
    elif p.returncode == 2:
        # Exit 2 is parse/resolution failure AND any warning, because this
        # adapter deliberately runs without --allow-warnings so that the
        # contradictory-assumptions warning can carry the vacuity signal.
        # Those are not the same event. When the run still printed its own
        # tally with an obligation discharged and no error, dafny COMPILED
        # AND VERIFIED the file and then failed it for a warning, so calling
        # it MALFORMED reports a prover's caution as a broken lowering, the
        # same class of misreport as selling incompleteness as refutation.
        # Measured 2026-09-04: the metamorphic sweep rewrote s[j] to
        # s[(j + 0)] in an invariant, dafny lost the quantifier trigger it
        # had been inferring, warned, and exited 2 on "2 verified, 0 errors".
        # Vacuity still wins when it fires; otherwise this is UNPROVED, not
        # VERIFIED, because a proof the prover calls brittle is not one this
        # project counts.
        if fin is not None and n_verified >= 1 and n_errors == 0:
            outcome = Outcome.VACUOUS if vac else Outcome.UNPROVED
            if not vac:
                err = "verified but warned, not counted: " + diag[-200:]
        else:
            outcome = Outcome.MALFORMED
    elif (cert_present and p.returncode == 0 and not oor and fin is not None
          and n_errors == 0 and n_verified >= 1):
        # THE COHERENCE GATE (2026-09-07, fstar's rule adopted). The main
        # run discharged every obligation in the file, the twin's own
        # included. A certificate claims the twin's theorem is false at the
        # witness; a file that also verifies is incoherent, and the claim
        # is evidence of nothing. Until this gate the branch below minted
        # REFUTED here from the lemma alone. Measured on the 159 lifted
        # tasks (ROADMAP 12.5): four cells read REFUTED on a twin dafny
        # proves, slow_max (an exit witness on a loop the method assigns
        # after) and downWhileGreater plus two mult tasks (a dropped bound
        # invariant dafny's own inference recovers, which _Admissible's
        # havoc rule does not model).
        #
        # Exit 0 and no "out of resource" are part of the test, not
        # decoration: dafny's tally does not count a starved method as an
        # error, so "1 verified, 0 errors, 1 out of resource" (measured on
        # three lifted square twins the same day: the lemma verified, the
        # method did not) read as a verified file to a gate on the counts
        # alone and demoted three honest refutations to MALFORMED.
        outcome = Outcome.MALFORMED
        err = ("certificate present on a file that verified: the kernel "
               "proved the twin, so the witness refutes nothing")
        cert["coherence"] = "file verified"
    elif cert_present:
        # Certificate discipline (module docstring): never VERIFIED; the
        # kernel's acceptance of the one declared lemma, in its own isolated
        # run, is the only thing that mints REFUTED.
        accepted, cert = _check_certificate(path, budget, banned, out,
                                            max(n_errors, 0), rprint)
        if accepted:
            outcome = Outcome.REFUTED
        elif p.returncode == 4 and oor:
            outcome = Outcome.TIMEOUT
        elif p.returncode in (0, 4):
            outcome = Outcome.UNPROVED
        else:
            outcome = Outcome.TOOL_ERROR
            err = diag[-400:]
    elif p.returncode == 0:
        if fin is None:
            # exit 0 without the verifier's own tally is not evidence.
            outcome = Outcome.TOOL_ERROR
            err = "exit 0 but no 'N verified, M errors' line: " + diag[-300:]
        elif n_verified < 1 or n_errors != 0:
            # "0 verified, 0 errors" at exit 0: measured for empty and
            # comments-only files. Nothing was proved.
            outcome = Outcome.MALFORMED
        elif vac:
            outcome = Outcome.VACUOUS
        else:
            outcome = Outcome.VERIFIED
    elif p.returncode == 4:
        # Could-not-prove. Z3 resource exhaustion also surfaces here with
        # "out of resource" in the text, a budget verdict; everything else
        # is the solver stopping without a countermodel, and no countermodel
        # is ever printed (module docstring), so never REFUTED.
        outcome = Outcome.TIMEOUT if oor else Outcome.UNPROVED
    else:
        outcome = Outcome.TOOL_ERROR
        err = diag[-400:]
    return Result("dafny", version(), src_hash, outcome,
                  ok=outcome == Outcome.VERIFIED, exit_code=p.returncode,
                  wall_ms=wall, budget=f"rlimit={budget}",
                  error=err,
                  extras={"vacuity_warnings": vac[:5],
                          "banned_tokens": banned[:8],
                          "verified_count": n_verified,
                          "error_count": n_errors,
                          "certificate": cert})
