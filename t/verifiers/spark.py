"""t.verifiers.spark — the third kernel: GNATprove (SPARK 2014, Why3 + Z3).

Verdicts are classified from the kernel's own machine-written audit (the
per-unit .spark JSON), because gnatprove was MEASURED (2026-08-31, FSF
16.1.0-1, confirmed on x86_64-linux) to exit 0 for a full proof, for an
unproved postcondition, for a file that does not even parse, AND — Wave-1
audit, 2026-08-31 — for eight files where the proof obligation was justified,
skipped, or never generated at all:
    any "error:" line                 -> MALFORMED (checked FIRST; a broken
                                          file can produce both)
    wall backstop                     -> TIMEOUT
    no .spark audit                   -> TOOL_ERROR (never a pass)
    otherwise the audit decides       -> _classify_audit below, and VERIFIED
                                          additionally requires the havoc
                                          oracle to show the postcondition has
                                          teeth; zero checks generated is not
                                          a pass.
    clean audit but nonzero exit      -> TOOL_ERROR

REFUTED IS NOT "UNPROVED" — the Wave-4 repair, 2026-09-01. The adapter used to
map any "medium:" or "high:" line on stdout to REFUTED. A gnatprove `medium`
means "could not prove", which is INCOMPLETENESS; the differential fuzzer
(t/fuzz_lower.py, 218 tasks) MEASURED the misfire on seven true seq-scan
tasks — fz_v1scan_047/073/089/099/122/172/175 — where six kernels VERIFIED and
spark claimed a refutation whose own audit read
`VC_POSTCONDITION medium/limit`: the 20000-step budget ran out. ROADMAP 7.4
and verifiers/__init__.py already forbid folding a deterministic resource-out
into REFUTED, so the text rule was breaking the taxonomy's own invariant.

What the audit distinguishes, all MEASURED on this install:
  * gnatprove's unproved_status vocabulary is exactly three words —
    "limit" (the --steps budget ran out), "gave_up" (the prover answered
    Unknown, MEASURED as Z3 "Unknown\\n(sat)" after 1 step), "unknown".
    NONE of the three is a countermodel; unproved_status alone therefore
    cannot license a refutation.
  * severity is the countermodel channel, and only under --counterexamples=on
    (OFF by default, which is why the old adapter had no way to tell):
    probe p4_false_int_abs.ads (Post => F'Result >= 0 and (F'Result = X or
    F'Result = -X) over a body returning -X) reports severity "medium" with
    no cntexmp under the default flags, and severity "high" with a cntexmp
    field {X = 0-witness} once counterexamples are on. The escalation is the
    RAC confirmation, not the mere existence of a model: with
    --check-counterexamples=off the same file keeps a cntexmp and drops back
    to "medium" (probe p1_false_int.ads). So severity "high" == "gnatprove
    ran the counterexample and it really fails".
  * a flow check that fails carries how_proved "flow", severity "high",
    status "unknown" and no cntexmp (probe t_p5: `X := Z` with Z
    uninitialized). Flow analysis is complete, not a solver, so its "high" is
    also a definite defect — it is the one high without a countermodel that
    still rules REFUTED.

Hence: REFUTED needs severity "high" (plus a cntexmp for a prover check);
"limit" is TIMEOUT; everything else unproved is UNPROVED. See
_classify_unproved. The flags that make this measurable —
--counterexamples=on --check-counterexamples=on --ce-steps=<steps> — are
hardening flags in ROADMAP 7.3's sense and are recorded in Result.budget: a
run without them is a weaker instrument that cannot see a countermodel at all.
--ce-steps is pinned to the run's own --steps because the switch it replaces
is a wall-clock timeout, and a wall clock is not machine-independent; the
counterexample was MEASURED identical at ce-steps 100/1000/20000/100000.

WHAT THE REPAIR COST, and it is a finding about the corpus, not about this
rule: under the honest rule NONE of the 11 committed twins is REFUTED —
9 report medium/limit (TIMEOUT) and abs/max report medium/gave_up (UNPROVED),
and not one carries a counterexample. All 11 real lowerings still VERIFY, so
the spark column is now verified/timeout and verified/unproved, never
verified/refuted. The cause is the seq/int model, MEASURED as a matched pair
that differs only in the numeric type: the abs twin (Post => F'Result >= 0
and (F'Result = X or F'Result = -X) over a body returning -X) reports
severity "high" with a counterexample when X : Integer, and severity "medium"
with no counterexample when X : Big_Integer — at 20000 AND at 200000 steps,
and under --prover=all. Big_Integer is private, so gnatprove has no model to
build. A SPARK twin written over Big_Integer therefore CANNOT be refuted with
evidence by this kernel, whatever the budget. Loosening the rule back would
buy the flips by calling nine budget exhaustions a disproof; the flips have
to be bought from the lowering instead.

POSITIVE EVIDENCE (the contract): exit 0 under --quiet was MEASURED to be
what pragma SPARK_Mode (Off), pragma/aspect Import, and pragma Annotate
(GNATprove, Skip_Proof|Skip_Flow_And_Proof|False_Positive|Intentional, ...)
all produce — with zero checks proved. So VERIFIED additionally requires,
from gnatprove's own gnatprove/*.spark JSON in the scratch dir (written by
the tool, not printable or suppressible by the source, unlike stdout):
  * >= 1 proof entry with severity "info" (a check actually proved), of
    which >= 1 is rule VC_POSTCONDITION (every t lowering puts a Post on F);
  * no proof entry justified or unproved (annot_kind / severity != "info":
    MEASURED shape of Annotate False_Positive/Intentional under --quiet —
    the medium entry stays in the JSON while stdout goes silent);
  * empty pragma_assume / skip_proof / skip_flow_proof lists (MEASURED:
    Skip_Proof fills skip_proof while printing nothing);
  * every entity in the "spark" map analyzed "all" (MEASURED: an Import'd or
    SPARK_Mode-Off body leaves "spec" or an empty map — the theorem's body
    was never in the proof's scope).

SEMANTIC VACUITY — two kernel-native instruments, neither of them lexical.

(1) gnatprove's own proof warnings, --proof-warnings=on. MEASURED on the
    Wave-2 probes: a contradictory Pre — Pre => Big_Integer'(1) =
    Big_Integer'(2), which discharges a FALSE Post at exit 0 with severity
    "info" — puts a proof entry {rule: VC_INCONSISTENT_PRE, severity:
    "warning", message: "precondition is always False"} in the .spark JSON:
    the kernel itself saying the hypothesis is unsatisfiable, in its own
    machine-written record. The three always-False rules
    (VC_INCONSISTENT_PRE / _POST / _ASSUME) rule VACUOUS. The detection is
    semantic, not syntactic — MEASURED to fire on
    Pre => (X > 0 and then X < 0) as well — and MEASURED to fire on none of
    the 22 honest files (11 real + 11 twin).

    VC_UNREACHABLE_BRANCH and VC_DEAD_CODE are NOT verdicts here, MEASURED:
    VC_UNREACHABLE_BRANCH fires on 7 of the 11 honest real lowerings
    (count_matches, factorial, fib, gcd, linear_search, sum_upto, max's twin)
    because lower_spark.py wraps every Subprogram_Variant as
    (if D >= 0 then D else 0) and the `else 0` branch is provably dead under
    the invariant. Ruling on that rule would fail 7 honest cells. They are
    recorded in extras["proof_warnings"] as evidence and nothing more; the
    vacuous-implication class they would have caught is caught by (2).

(2) The havoc oracle, for the class no warning reports: a postcondition that
    is TRUE of every possible result (Post => True; Post => (if 1 = 2 then
    ...)) is proved honestly by the kernel and looks exactly like a real
    proof. _havoc_source replaces F's expression-function completion with a
    call to an Import'd, contract-free function, so F'Result becomes an
    arbitrary value of the return type, and asks the SAME kernel at the SAME
    --steps budget whether F's postcondition still proves. If it does, the
    contract says nothing about the computed result and the cell is VACUOUS.
    MEASURED: F's VC_POSTCONDITION goes "info" -> "medium" on all 22 honest
    files and stays "info" on all three Wave-2 holes — full separation. The
    oracle runs ONLY when every other gate has already said VERIFIED, so
    refuted twins never pay for it. F's postcondition is identified by
    gnatprove's own entity table (entities[id].name ending in ".F"), not by
    source position.

    The oracle is fail-closed: a source the completion scanner cannot
    rewrite, a havoc run that emits "error:", or a havoc run with no
    VC_POSTCONDITION for F is TOOL_ERROR, never VERIFIED — the adapter may
    not certify what its own instrument could not examine.

THE CERTIFICATE CHANNEL (10.8, 2026-09-02): the flips the honest rule gave
up are bought back from the lowering, exactly as the paragraph above
demanded. lower_spark.py restates the harness's measured witness as one
ground goal named t_refutation_certificate in the twin file; the audit rule
at CERT_ENTITY below mints REFUTED only when the kernel discharges every
check of that goal, a rejected certificate is UNPROVED (never REFUTED), and
a file whose active code carries the name can never mint VERIFIED. MEASURED
2026-09-02: the nine verified/timeout twins all read verified/refuted under
the unchanged 20000-step budget, every real cell stays VERIFIED, and the
soundness probes (planted name without goals, false certificate, accepted
certificate planted in a real program, name in a comment) land UNPROVED,
UNPROVED, REFUTED-the-demotion, and inert respectively.

Budget: --steps, gnatprove's explicitly machine-independent deterministic
bound; the havoc run reuses it, so "provable against an arbitrary result" is
judged at exactly the standard the real run was judged at. The havoc run's
unproved F postcondition was MEASURED to reach "medium" two ways —
unproved_status "gave_up" (Z3 answered "Unknown (sat)": abs, max, sum_upto)
and "limit" (the 20000 steps ran out: the other 8 tasks) — so a "limit"
result cannot be refused as inconclusive: demanding "gave_up" would turn 8
of the 11 honest cells into TIMEOUT. Both are recorded in extras["f_post"].
Prover pinned to the bundled Z3 with --prover=z3.

`pragma Assume`, SPARK_Mode Off, Import, and GNATprove justification
annotations prove or excuse anything — t never emits them; the adapter rules
VACUOUS on sight (BANNED below). That ban is the
cheap second line, not the guarantee: the guarantee is the audit requirements
plus the two instruments above. The ban scan runs on _active_code():
comments, string literals and character literals stripped (a commented
"pragma Assume" is inert — Wave-1 probe p12 measured the unstripped scan
overfiring VACUOUS on an honest proof) and unicode homoglyphs folded to
ASCII (probe p11; GNAT itself rejects non-ASCII program text with "error:
illegal character", so folding cannot excuse real code).

Assertion_Policy (Ignore) needs no ban: MEASURED (p06/p07) — gnatprove
proves the ignored assertions anyway and still reports "medium:".

gnatprove requires a project; each verify runs in a scratch dir with a
two-line .gpr beside a copy of the source. The hash in the Result is the
SOURCE file's, so witnesses bind to t's artifact, not the scaffolding.

SPARKlib (2026-09-01): lower_spark.py's seq is now
SPARK.Containers.Functional.Infinite_Sequences, the only sequence in reach
whose length is a Big_Natural rather than a bounded array index (the array
model handed the kernel `len(s) <= 2^31-1` for free and VERIFIED the
fz_p_seqlen probe six other kernels REFUTE). So a source that withs
SPARK.Containers gets the shipped library added to its project: the
sparklib.gpr copy below is the vendor's own sparklib.gpr.templ with an
Object_Dir under our control, and `Externally_Built => True` because the
library is proved by AdaCore, not here — MEASURED without it, gnatprove
analyzed all of SPARKlib (25s, and "medium:" lines from
spark-lemmas-floating_point_arithmetic.ads that would have refuted every
seq task). GPR_PROJECT_PATH points at the toolchain's own lib/gnat so
sparklib_internal/sparklib_common resolve. A source that does not with
SPARK.Containers gets the bare two-line project it always got.

That library arrives with entities of its own, and _classify_audit's
"every entity analyzed all" rule had to learn about them: a generic
instantiation's members legitimately sit at "spec" because their bodies are
in the library, not here. The rule is now scoped to entities DECLARED IN the
analyzed file, with instantiations recognized structurally — an entity whose
members' primary sloc is another file — never by name. A subprogram declared
in the t artifact with no completion (the uninterpreted-function trick, the
thing this rule exists to catch) has no such members and is still MALFORMED.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
import unicodedata
from pathlib import Path

from . import Outcome, Result, safe_text, sha256_file
from .discover import find, missing

GNATPROVE = find("T_GNATPROVE", ['gnatprove'], [".local/gnatprove/**/bin/gnatprove", ".alire/**/bin/gnatprove"])
_GNATPROVE_WHY = missing("spark", "T_GNATPROVE", ['gnatprove'], [".local/gnatprove/**/bin/gnatprove", ".alire/**/bin/gnatprove"])
DEFAULT_STEPS = 20_000
WALL_S = 180

# Pragma AND aspect forms of every accepted-without-proof mechanism (Wave-1:
# pragma SPARK_Mode (Off) / pragma Import (C, ...) evaded the aspect-only
# ban; Import => True reordered after Post, and bare `Import` in a comma
# aspect list, evaded `with Import`). \bImport(?:_\w+)?\b needs no context:
# the word in active code is the aspect, the pragma, or GNAT's
# Import_Function/Import_Procedure variants; pragma Interface is the Ada 83
# synonym. GNATprove-comma catches pragma Annotate AND Annotate => (...) for
# the justify/skip families without caring which syntax carried it.
BANNED = re.compile(
    r"pragma\s+Assume\b"
    r"|SPARK_Mode\s*(?:=>|\()\s*Off\b"
    r"|\bImport(?:_\w+)?\b"
    r"|pragma\s+Interface(?:_Name)?\b"
    r"|GNATprove\s*,\s*(?:False_Positive|Intentional|Skip_Proof"
    r"|Skip_Flow_And_Proof)\b",
    re.IGNORECASE)

# Confusable-to-ASCII fold for the ban scan (probe p11: Cyrillic А in
# "pragma Аssume"). NFKC first (fullwidth/compatibility forms), then the
# common Cyrillic/Greek lookalikes of the letters our ban tokens use.
_HOMOGLYPHS = str.maketrans(
    "АВЕКМНОРСТУХЅІЈабвеорсухіјѕԛԝ"
    "ΑΒΕΖΗΙΚΜΝΟΡΤΥΧοικρτυσνε",
    "ABEKMHOPCTYXSIJabveopcyxijsqw"
    "ABEZHIKMNOPTYXoikptusve")

# One leftmost-first pass: a string opened in a comment is not a string, a
# "--" inside a string or character literal is not a comment. [^"\n] keeps
# an unterminated literal from swallowing lines (fail-closed: leftovers can
# only over-match the ban, never under-match it).
_INERT = re.compile(r"'[^'\n]'|\"(?:[^\"\n]|\"\")*\"|--[^\n]*")

GPR = "project T_Work is\n   for Source_Dirs use (\".\");\nend T_Work;\n"
GPR_SPARKLIB = ("with \"sparklib\";\n"
                "project T_Work is\n   for Source_Dirs use (\".\");\n"
                "end T_Work;\n")
# The vendor's lib/gnat/sparklib.gpr.templ, completed as its comment
# instructs: an Object_Dir under our control. Externally_Built keeps
# gnatprove out of the library's own proofs (see the header).
SPARKLIB_GPR = """\
project SPARKlib extends "sparklib_internal" is
   for Externally_Built use "True";
   for Object_Dir use "sparklib_obj";
   for Source_Dirs use SPARKlib_Internal'Source_Dirs;
   for Excluded_Source_Files use SPARKlib_Internal'Excluded_Source_Files;
end SPARKlib;
"""
# A source that reaches for the library says so by withing it; everything
# else keeps the bare project and pays nothing for the library's presence.
_USES_SPARKLIB = re.compile(r"^\s*with\s+SPARK\.", re.MULTILINE | re.IGNORECASE)


def _env() -> dict:
    """gnatprove's environment: GPR_PROJECT_PATH extended with the
    toolchain's own lib/gnat, where sparklib_internal.gpr and
    sparklib_common.gpr ship. Derived from the binary that was discovered,
    never from a second guess at where SPARK is installed."""
    env = dict(os.environ)
    if GNATPROVE:
        gnat = str(Path(GNATPROVE).resolve().parent.parent / "lib" / "gnat")
        old = env.get("GPR_PROJECT_PATH", "")
        env["GPR_PROJECT_PATH"] = f"{gnat}{os.pathsep}{old}" if old else gnat
    return env

# gnatprove's own always-False rules (--list-categories, "Proof warnings
# categories"): the kernel reporting that a hypothesis it was handed cannot
# be satisfied. MEASURED absent from all 22 honest files, present on the
# contradictory-Pre probe.
CONTRADICTORY = frozenset((
    "VC_INCONSISTENT_PRE", "VC_INCONSISTENT_POST", "VC_INCONSISTENT_ASSUME"))
# Same warning family, recorded but NEVER ruled on: MEASURED to fire on 7 of
# 11 honest real lowerings (lower_spark.py's (if D >= 0 then D else 0)
# Subprogram_Variant wrapper makes the `else 0` branch provably dead).
UNREACHABLE = frozenset(("VC_UNREACHABLE_BRANCH", "VC_DEAD_CODE"))

# The havoc oracle's injected function. Contract-free and Import'd, so
# gnatprove has nothing to know about its result but its type. The name is
# suffixed with a digest of the source (probe e4 measured a file that squats
# the fixed name: gnatprove answers "conflicts with declaration at line N",
# which costs the oracle its subject). Predicting the suffix requires a source
# containing its own hash, so squatting it is not an available move.
HAVOC_FN = "T_Vacuity_Havoc"

# THE REFUTATION CERTIFICATE (10.8). lower_spark.py may put ONE extra goal in
# a twin file, a function named exactly this, whose body is the harness
# witness instantiated as a ground formula (the negated ensures at the
# measured input, or the negated exit-entailment at the measured loop state).
# The audit routes its checks separately from everything else's, and the
# classification is:
#   * every certificate check discharged (severity "info"), its
#     VC_POSTCONDITION included  -> REFUTED: the kernel itself accepted a
#     proof that the spec fails at the witness. Positive evidence, exactly
#     like a confirmed countermodel, and MEASURED (2026-09-02, all nine
#     certificate twins) to discharge in 2-8s at the standard 20000 steps
#     where countermodel SEARCH exhausts the budget: the certificate hands
#     the prover the witness instead of asking it to find one.
#   * any certificate check unproved -> never REFUTED from the certificate,
#     and never VERIFIED for the whole file: "limit" on the certificate is
#     TIMEOUT, anything else is UNPROVED. A certificate-entity check with
#     severity "high" is deliberately NOT the countermodel channel: a
#     failing certificate is a wrong accusation, not a wrong program.
#   * a file whose ACTIVE CODE names t_refutation_certificate can never
#     mint VERIFIED, goals or no goals: the name is reserved for refutation
#     evidence, so planting it in a real program only demotes that program
#     (to UNPROVED), never promotes anything.
# Everything else is unchanged: bans, contradictory-hypothesis warnings and
# justified/skip/assume checks still outrank the certificate (VACUOUS), and
# the confirmed-countermodel channel (severity "high" plus cntexmp, RAC
# executed) still refutes independently of any certificate.
CERT_ENTITY = "t_refutation_certificate"

# lower_spark.py emits F's completion as one signature line ending in `is`
# followed by a parenthesised expression; the W_k helpers put `is` on the
# next line, so both placements are accepted. The declaration is never
# matched: it is followed by `with`, not by `is`.
_F_COMPLETION = re.compile(
    r"^[ \t]*function[ \t]+F[ \t]*(\([^\n]*\))?[ \t]*return[ \t]+(\w+)"
    r"[ \t]*\r?\n?[ \t]*is\b",
    re.MULTILINE)


def _active_code(raw: str) -> str:
    folded = unicodedata.normalize("NFKC", raw).translate(_HOMOGLYPHS)
    return _INERT.sub(" ", folded)


def _end_of_expression(src: str, i: int) -> int:
    """Index just past the `;` closing the expression-function body that
    starts at src[i:]. Parenthesis depth is tracked with string and character
    literals skipped, so a `;` inside them cannot end the body early.
    Returns -1 when the body is unterminated."""
    depth, n = 0, len(src)
    while i < n:
        c = src[i]
        if c == '"':
            i += 1
            while i < n and src[i] != '"':
                i += 1
        elif c == "'" and i + 2 < n and src[i + 2] == "'":
            i += 2                      # character literal, never an attribute
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif c == ";" and depth <= 0:
            return i + 1
        i += 1
    return -1


def _havoc_source(src: str) -> tuple[str | None, str]:
    """F's completion replaced by a call to an Import'd contract-free
    function, so F'Result is an arbitrary value of the return type. Returns
    (text, "") or (None, why) — and (None, why) is fail-closed at the call
    site, never a pass."""
    fn = (HAVOC_FN + "_"
          + hashlib.sha256(src.encode("utf-8", "replace")).hexdigest()[:12])
    if fn.lower() in src.lower():
        return None, (f"source already declares {fn}; the havoc oracle cannot "
                      f"inject a fresh arbitrary result")
    ms = list(_F_COMPLETION.finditer(src))
    if not ms:
        return None, "no `function F ... is` expression-function completion"
    m = ms[-1]
    end = _end_of_expression(src, m.end())
    if end < 0:
        return None, "F's expression-function body is unterminated"
    plist, rtype = m.group(1) or "", m.group(2)
    body = (f"   function {fn} return {rtype}\n"
            f"   with Import, Global => null;\n\n"
            f"   function F {plist} return {rtype} is\n"
            f"     ({fn});\n")
    return src[:m.start()] + body + src[end:], ""


def _unproved(entry: dict, how: str) -> dict:
    """One undischarged check, reduced to the four fields the verdict turns
    on. `cntexmp` is presence-only: the values are the user's witness, not
    the adapter's evidence, and copying them into a Result would put source
    text into a record that must stay hash-bound."""
    return {"how": how, "rule": entry.get("rule", ""),
            "severity": entry.get("severity", ""),
            "status": (entry.get("unproved_status") or {}).get("status", ""),
            "cntexmp": "cntexmp" in entry,
            "at": f"{entry.get('file')}:{entry.get('line')}"}


def _classify_unproved(un: list[dict]) -> tuple[str, str]:
    """The Wave-4 split (header): severity "high" is gnatprove's own
    certainly-wrong, reached for a prover check ONLY when a counterexample
    was generated and RAC-confirmed, and for a flow check by the complete
    flow analysis. Everything else undischarged is ignorance, and ignorance
    is never a refutation."""
    ce = [u for u in un if u["severity"] == "high"
          and (u["cntexmp"] or u["how"] == "flow")]
    if ce:
        return Outcome.REFUTED, "; ".join(
            f"{u['rule']} at {u['at']}: gnatprove severity high"
            + (" with a confirmed counterexample" if u["cntexmp"]
               else " from flow analysis") for u in ce[:4])
    # A "limit" is the --steps bound running out: the taxonomy's TIMEOUT,
    # deterministic resource-out included (verifiers/__init__.py, ROADMAP 7.3).
    limit = [u for u in un if u["status"] == "limit"]
    if limit:
        return Outcome.TIMEOUT, (
            "budget exhausted, NOT refuted: "
            + "; ".join(f"{u['rule']} at {u['at']} severity {u['severity']}"
                        f"/limit" for u in limit[:4]))
    return Outcome.UNPROVED, (
        "could not prove, no countermodel and no budget exhaustion: "
        + "; ".join(f"{u['rule']} at {u['at']} severity {u['severity']}"
                    f"/{u['status'] or 'no-status'}" for u in un[:4]))


def _read_audit(work: Path) -> tuple[dict | None, str]:
    """Summarize gnatprove/*.spark. (None, why) when the audit is absent or
    unreadable — that is TOOL_ERROR, never a pass: the kernel's own record
    is the only acceptable positive evidence."""
    gdir = work / "gnatprove"
    files = sorted(gdir.glob("*.spark")) if gdir.is_dir() else []
    if not files:
        return None, "gnatprove wrote no .spark audit"
    a = {"proved": 0, "post_proved": 0, "justified": 0, "unproved": [],
         "skips": 0, "assumes": 0, "entities": {},
         "contradictory": [], "unreachable": [], "f_post": [],
         "cert": {"proved": 0, "post_proved": 0, "unproved": []}}
    for f in files:
        try:
            d = json.loads(f.read_bytes().decode("utf-8", errors="replace"))
        except (json.JSONDecodeError, OSError) as e:
            return None, f"unreadable audit {f.name}: {e}"
        a["assumes"] += len(d.get("pragma_assume", []))
        a["skips"] += (len(d.get("skip_proof", []))
                       + len(d.get("skip_flow_proof", [])))
        # gnatprove's entity table: id -> qualified name, its own attribution
        # of every check to a subprogram (measured key "entities").
        names = {str(k).strip(): (v or {}).get("name", "")
                 for k, v in (d.get("entities") or {}).items()}
        for entry in d.get("proof", []):
            rule = entry.get("rule", "")
            if rule in CONTRADICTORY or rule in UNREACHABLE:
                # Scoped to the t artifact's own file. The vacuity question is
                # about t's contract, and SPARKlib's conditional preconditions
                # (`Pre => (SPARKlib_Defensive => ...)`) are always-False in
                # the shipped non-defensive build: MEASURED 2026-09-01, five
                # VC_INCONSISTENT_PRE from spark-containers-*.ads alone, which
                # unscoped would rule VACUOUS on every seq task.
                where = f"{rule} at {entry.get('file')}:{entry.get('line')}"
                if entry.get("file") == f"{f.stem}.ads":
                    a["contradictory" if rule in CONTRADICTORY
                      else "unreachable"].append(where)
                continue      # a warning, not an obligation: never counted
            owner = names.get(str(entry.get("entity")).strip(), "")
            if rule == "VC_POSTCONDITION" \
                    and owner.rsplit(".", 1)[-1] == "F":
                # severity + why it went unproved; NEITHER "limit" nor
                # "gave_up" is a countermodel (header) — this string is the
                # havoc oracle's info/not-info signal, nothing more.
                a["f_post"].append(
                    f"{entry.get('severity')}/"
                    f"{(entry.get('unproved_status') or {}).get('status')}")
            # A justified check and an unproved check are different findings
            # and were merged into one "flagged" counter before Wave-4: the
            # merge is what let an unproved obligation reach the VACUOUS
            # branch, and what left the REFUTED decision to a stdout regex.
            # Certificate-entity checks are routed to their own bucket: they
            # must never count toward the file's proofs (a certificate file
            # never mints VERIFIED) and never reach _classify_unproved (a
            # failing certificate must not borrow the countermodel channel).
            # A justified certificate check still counts as justified, which
            # is VACUOUS: excusing the certificate is still excusing a check.
            if "annot_kind" in entry:
                a["justified"] += 1
            elif owner.rsplit(".", 1)[-1].lower() == CERT_ENTITY:
                if entry.get("severity") != "info":
                    a["cert"]["unproved"].append(_unproved(entry, "prover"))
                else:
                    a["cert"]["proved"] += 1
                    if rule == "VC_POSTCONDITION":
                        a["cert"]["post_proved"] += 1
            elif entry.get("severity") != "info":
                a["unproved"].append(_unproved(entry, "prover"))
            else:
                a["proved"] += 1
                if rule == "VC_POSTCONDITION":
                    a["post_proved"] += 1
        for entry in d.get("flow", []):
            # honest flow entries are "info" (plus library "warning"s in
            # warn_error, not here); a justified flow check carries
            # annot_kind exactly like a justified proof check. A failing
            # flow check on the certificate entity kills the certificate,
            # never the program: same routing as the proof entries.
            if "annot_kind" in entry:
                a["justified"] += 1
            elif entry.get("severity") not in ("info", "warning"):
                fowner = names.get(str(entry.get("entity")).strip(), "")
                if fowner.rsplit(".", 1)[-1].lower() == CERT_ENTITY:
                    a["cert"]["unproved"].append(_unproved(entry, "flow"))
                else:
                    a["unproved"].append(_unproved(entry, "flow"))
        # "Declared here" is the entity's PRIMARY sloc (a generic member
        # carries the library's location first and the instantiation's
        # second). An entity of ours at "spec" is a body outside the
        # proof's scope; a library entity at "spec" is the library.
        ents = d.get("entities") or {}
        here = f"{f.stem}.ads"
        own = {k.strip(): (v or {}).get("name", "") for k, v in ents.items()
               if ((v or {}).get("sloc") or [{}])[0].get("file") == here}
        # An instantiation is recognized structurally, never by name: it is
        # an entity of ours whose members are declared in another file. A
        # subprogram declared here with no completion — the uninterpreted-
        # function trick this rule exists to catch — has no such members.
        foreign = {n.rsplit(".", 1)[0]
                   for k, v in ents.items()
                   for n in [(v or {}).get("name", "")]
                   if n and ((v or {}).get("sloc") or [{}])[0].get("file")
                   not in (here, None)}
        for k, v in (d.get("spark") or {}).items():
            k = k.strip()
            if k in own and own[k] not in foreign:
                a["entities"][f"{f.stem}:{k}"] = v
    return a, ""


def _classify_audit(a: dict) -> tuple[str, str]:
    """Every run with a readable audit lands here; the audit decides. Returns
    (outcome, reason). VERIFIED here is provisional — verify() must still
    clear it through the havoc oracle."""
    if a["contradictory"]:
        return Outcome.VACUOUS, (
            "gnatprove --proof-warnings reports an unsatisfiable hypothesis: "
            + "; ".join(a["contradictory"][:4]))
    # Cheating outranks failing: a file that justified or skipped an
    # obligation never earned the right to be called merely unproved.
    if a["assumes"] or a["skips"] or a["justified"]:
        return Outcome.VACUOUS, (
            f"accepted without discharging: {a['assumes']} pragma_assume, "
            f"{a['skips']} skipped, {a['justified']} justified "
            f"check(s) in the .spark audit")
    # The confirmed-countermodel channel outranks the certificate: severity
    # "high" is the kernel's own executed evidence about the program's very
    # obligation, so a cell that has it (abs, max) keeps the evidence
    # signature it had before the certificate channel existed (10.8).
    ce = [u for u in a["unproved"] if u["severity"] == "high"
          and (u["cntexmp"] or u["how"] == "flow")]
    if ce:
        return _classify_unproved(a["unproved"])
    cert = a["cert"]
    if cert["proved"] or cert["unproved"]:
        if not cert["unproved"] and cert["post_proved"]:
            return Outcome.REFUTED, (
                "kernel accepted the t_refutation_certificate goal: the "
                "measured witness instantiation of the spec is proved to "
                f"fail ({cert['proved']} certificate check(s) discharged, "
                f"{cert['post_proved']} of them its postcondition)")
        # A rejected certificate never refutes and the file never verifies.
        # The program's own checks still classify normally below, so a
        # confirmed countermodel on F stays REFUTED and a starved F stays
        # TIMEOUT; only a file whose every non-certificate check proved
        # falls through to the certificate's own failure.
        detail = "; ".join(
            f"{u['rule']} at {u['at']} severity {u['severity']}"
            f"/{u['status'] or 'no-status'}" for u in cert["unproved"][:4])
        if a["unproved"]:
            return _classify_unproved(a["unproved"])
        if any(u["status"] == "limit" for u in cert["unproved"]):
            return Outcome.TIMEOUT, (
                "certificate not judged within budget: " + detail)
        return Outcome.UNPROVED, (
            "kernel did not accept t_refutation_certificate: " + detail)
    if a["unproved"]:
        return _classify_unproved(a["unproved"])
    if a["proved"] == 0:
        return Outcome.MALFORMED, (
            "zero checks proved (audit shows no proof obligations were "
            "generated — SPARK_Mode Off / Import / empty unit shape)")
    if not a["entities"] or any(v != "all" for v in a["entities"].values()):
        return Outcome.MALFORMED, (
            f"body not fully analyzed: entities {a['entities']} "
            f"(an entity below \"all\" has code outside the proof's scope)")
    if a["post_proved"] == 0:
        return Outcome.MALFORMED, (
            "no VC_POSTCONDITION proved — the artifact's theorem (the Post "
            "on F) was never discharged")
    return Outcome.VERIFIED, ""


def _ce_flags(budget: int) -> list[str]:
    """The counterexample channel, off by default in gnatprove. Without it
    severity never reaches "high" and a genuinely false postcondition is
    byte-identical to a starved true one (header, probes p4/p1) — the adapter
    would have no evidence with which to refuse the old text rule.
    --ce-steps is pinned to the run's own --steps: the switch it replaces is a
    wall-clock timeout, and ROADMAP 7.3 requires a machine-independent bound."""
    return ["--counterexamples=on", "--check-counterexamples=on",
            f"--ce-steps={budget}"]


def _run(src_text: str, unit: str, budget: int, warnings: bool,
         cntexmp: bool = False):
    """One gnatprove run over src_text in a fresh scratch dir. Returns
    (proc | None, audit | None, why); proc None means the wall backstop
    fired."""
    with tempfile.TemporaryDirectory(prefix="t-spark-") as td:
        work = Path(td)
        lib = _USES_SPARKLIB.search(src_text) is not None
        (work / "t_work.gpr").write_text(GPR_SPARKLIB if lib else GPR,
                                         encoding="utf-8")
        if lib:
            (work / "sparklib.gpr").write_text(SPARKLIB_GPR, encoding="utf-8")
            (work / "sparklib_obj").mkdir()
        # GNAT's naming convention demands file name == unit name; deriving it
        # here keeps harness filenames free (twins live in *.twin.ads outside).
        (work / unit).write_text(src_text, encoding="utf-8")
        cmd = [str(GNATPROVE), "-P", "t_work.gpr", "--steps", str(budget),
               "--prover=z3", "--quiet"]
        if warnings:
            cmd.append("--proof-warnings=on")
        if cntexmp:
            cmd += _ce_flags(budget)
        try:
            p = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=WALL_S, cwd=work, env=_env())
        except subprocess.TimeoutExpired:
            return None, None, "wall backstop fired"
        audit, why = _read_audit(work)   # before the scratch dir dies
    return p, audit, why


def _havoc_verdict(src_text: str, unit: str, budget: int) -> tuple[str, str]:
    """The weak-spec oracle. VERIFIED only when F's postcondition FAILS
    against an arbitrary result; VACUOUS when it still proves; TOOL_ERROR
    when the oracle could not be applied — never a pass on ignorance."""
    hv, why = _havoc_source(src_text)
    if hv is None:
        return Outcome.TOOL_ERROR, f"havoc oracle not applicable: {why}"
    # No counterexample flags here: the oracle's whole question is whether F's
    # VC_POSTCONDITION stays "info" against an arbitrary result, and severity
    # info/not-info answers it. Asking for a countermodel would buy a witness
    # nothing reads and pay a second CE prover run on every would-be pass.
    p, audit, awhy = _run(hv, unit, budget, warnings=False)
    if p is None:
        return Outcome.TIMEOUT, "havoc oracle: wall backstop fired"
    out = p.stdout + p.stderr
    if re.search(r"^.*\berror\b", out, re.MULTILINE):
        return Outcome.TOOL_ERROR, (
            "havoc oracle rejected by gnatprove: " + out[-300:])
    if audit is None:
        return Outcome.TOOL_ERROR, f"havoc oracle: {awhy}"
    if not audit["f_post"]:
        return Outcome.TOOL_ERROR, (
            "havoc oracle produced no VC_POSTCONDITION for F; the contract "
            "was not examined against an arbitrary result")
    if all(s.startswith("info") for s in audit["f_post"]):
        return Outcome.VACUOUS, (
            "content-free contract: F's postcondition still proves when the "
            f"body is replaced by an arbitrary (Import'd) {HAVOC_FN} result, "
            "so it constrains nothing the body computes")
    return Outcome.VERIFIED, ""


def version() -> str:
    if not GNATPROVE:
        raise SystemExit(_GNATPROVE_WHY)
    p = subprocess.run([str(GNATPROVE), "--version"],
                       capture_output=True, text=True)
    first = p.stdout.strip().splitlines()
    return "gnatprove " + " / ".join(first[:2])


def verify(path: Path, budget: int = DEFAULT_STEPS) -> Result:
    if not GNATPROVE:
        raise SystemExit(_GNATPROVE_WHY)
    src_hash = sha256_file(path)
    src_text = safe_text(path)
    active = _active_code(src_text)
    banned = [m.group(0) for m in BANNED.finditer(active)]
    cert_named = CERT_ENTITY in active.lower()
    t0 = time.monotonic()
    m = re.search(r"package\s+(\w+)", src_text)
    unit = (m.group(1).lower() if m else "t_unit") + ".ads"
    fingerprint = f"steps={budget} " + " ".join(_ce_flags(budget))
    p, audit, audit_why = _run(src_text, unit, budget, warnings=True,
                               cntexmp=True)
    if p is None:
        return Result("spark", version(), src_hash, Outcome.TIMEOUT,
                      wall_ms=int((time.monotonic() - t0) * 1000),
                      budget=fingerprint, error="wall backstop fired")
    out = p.stdout + p.stderr
    why = ""
    if banned:
        outcome = Outcome.VACUOUS
    elif re.search(r"^.*\berror\b", out, re.MULTILINE):
        outcome = Outcome.MALFORMED
    elif audit is None:
        outcome, why = Outcome.TOOL_ERROR, audit_why
    else:
        # No stdout branch survives here. gnatprove's "medium:"/"high:" lines
        # used to decide REFUTED from this point; the audit says which of the
        # two they were (header), and stdout cannot say. The returncode is
        # likewise not a classifier — ROADMAP 7.4 forbids one — but a clean
        # audit under a nonzero exit is an inconsistency the adapter must not
        # certify past.
        outcome, why = _classify_audit(audit)
        if outcome == Outcome.VERIFIED and p.returncode != 0:
            outcome, why = Outcome.TOOL_ERROR, (
                f"audit shows every check discharged but gnatprove exited "
                f"{p.returncode}: " + out[-300:])
    if outcome == Outcome.VERIFIED and cert_named:
        # The name is reserved for refutation evidence (header): a file that
        # carries it in active code never mints VERIFIED, goals or no goals,
        # so planting it in a real program only costs that program its pass.
        # Checked before the havoc oracle: a file that cannot verify does
        # not pay for the second kernel run.
        outcome, why = Outcome.UNPROVED, (
            "active code names t_refutation_certificate but no accepted "
            "certificate goal decides the file: a certificate-carrying "
            "file never mints VERIFIED")
    havoc_wall = 0
    if outcome == Outcome.VERIFIED:
        # Only a would-be pass pays for the second kernel run: a refuted twin
        # is already answered, and running the oracle on it would buy nothing.
        h0 = time.monotonic()
        outcome, why = _havoc_verdict(src_text, unit, budget)
        havoc_wall = int((time.monotonic() - h0) * 1000)
    wall = int((time.monotonic() - t0) * 1000)
    extras = {"banned_tokens": banned[:5], "havoc_ms": havoc_wall}
    if audit is not None:
        extras["audit"] = {k: audit[k] for k in
                           ("proved", "post_proved", "justified",
                            "skips", "assumes")}
        extras["audit"]["entities"] = audit["entities"]
        extras["proof_warnings"] = (audit["contradictory"]
                                    + audit["unreachable"])[:5]
        extras["f_post"] = audit["f_post"]
        if audit["cert"]["proved"] or audit["cert"]["unproved"]:
            extras["cert"] = {"proved": audit["cert"]["proved"],
                              "post_proved": audit["cert"]["post_proved"],
                              "unproved": audit["cert"]["unproved"][:5]}
        # The verdict's whole basis when the outcome is not VERIFIED: which
        # check, what severity, whether a countermodel backed it.
        extras["unproved"] = audit["unproved"][:5]
    return Result("spark", version(), src_hash, outcome,
                  ok=outcome == Outcome.VERIFIED, exit_code=p.returncode,
                  wall_ms=wall, budget=fingerprint,
                  error=why if why else
                  ("" if outcome != Outcome.TOOL_ERROR else out[-400:]),
                  extras=extras)
