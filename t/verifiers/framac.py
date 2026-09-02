"""t.verifiers.framac — the sixth kernel: Frama-C/WP over ACSL contracts.

Pins: Frama-C 33.0 (Arsenic) + alt-ergo 2.4.3-free (NEVER opam's alt-ergo
2.6.x, which is non-commercial — the WS-7 licensing catch), via opam.

THE REFUTED DOCTRINE, remeasured 2026-09-02, because the old one violated
the law verifiers/__init__.py states (ROADMAP 10.7: a goal whose own status
was Timeout scored REFUTED). The load-bearing measurement, side by side at
the pinned budget: a trivially false ground postcondition (ensures \\result
== 1 on a function returning 0) and a true but unprovable lemma (Lagrange
four squares) BOTH come back [Stepout]; -wp-counter-examples changes
neither, because alt-ergo 2.4.3 has no counterexample driver under WP, so
WP's Invalid status is unreachable on this toolchain and no run here has
ever produced it. Falsity and hardness are indistinguishable by prover
status, so NO prover status mints REFUTED. The partition of an unproved
file is per goal, from the kernel's own report: any unproved goal whose
status is Timeout or Stepout (a pinned budget fired, wall or steps) makes
the file TIMEOUT; anything else unproved makes it UNPROVED. Outcome.TIMEOUT
therefore covers both the WALL backstop and a budget-ended goal.

REFUTED is minted by exactly one thing, the REFUTATION CERTIFICATE
(shared protocol across all seven columns): lower_framac.py may append to a
twin file one function, t_certificate, replaying the twin computation at the
measured witness input as branch-free ground code whose branch decisions
are themselves emitted goals, ending in one assert named
t_refutation_certificate that negates the instantiated ensures. This
adapter mints REFUTED if and only if that goal is declared in the kernel's
per-goal report AND the kernel accepted it AND every other goal in the
certificate's audit set (the certificate function's goals, smoke included,
plus every function-less global goal such as the termination lemmas) is
accepted, under the full existing audit discipline. Two hard rules, both
enforced below: a file carrying the certificate name can NEVER mint
VERIFIED, so planting the name in a real program only demotes it; and a
certificate the kernel rejects mints UNPROVED, never REFUTED. Measured
2026-09-02: all five value-witness twins (abs, factorial, fib, gcd, max)
carry a certificate discharged by Qed or alt-ergo in milliseconds,
recursive logic functions unfolding at ground arguments included
(fact(2) in 6ms), while each twin's own ensures goal stays Stepout.

THE SEMANTIC DECISION, half of which was wrong until 2026-09-01: without
-wp-rte, WP reasons about C integer ARITHMETIC mathematically, so -wp-rte
stays deliberately absent and the machine-int arm is a later gate, same as
Verus's exec/i64 arm. But the TYPING is a separate knob, and its default was
not t's semantics at all: -wp-model now pins Typed+nat, without which every
C `int` came with is_sint32 and the kernel proved bounded theorems for
unbounded t tasks. See MODEL below for the measurement.

-wp-cache none because a proof cache poisons flake_check — a cached verdict
re-measures nothing.

THE AUDIT ARCHITECTURE (Wave-2/3, all points measured 2026-08-31):

* VERIFIED requires the positive line `[wp] Proved goals: N / N` with N >= 1,
  anchored at start-of-line and taken from the LAST occurrence, plus exit 0.
  Source echoes in kernel diagnostics are indented with a line number
  (measured on parse_error.c), so a source line cannot forge the anchor.
* The ban scan runs on the kernel's OWN normalized view (`frama-c -print`):
  macros are expanded (macro_axiom.c), backslash-newline splices are undone
  (splice_axiom.c), and plain C comments are dropped (overfire_admit.c) —
  three evasions the raw regex provably mis-scores. Raw-text scanning is only
  the fallback when the file does not parse, where VERIFIED is unreachable.
* `axiomatic`/`axiom` are banned because WP assumes axioms globally and emits
  NO goal for them: axiom_false.c and axiom_nofalse.c both closed
  `Proved goals: 4 / 4` over a false axiom. `lemma` and `check` are NOT
  banned: their obligations are emitted (lemma_false.c measured 4/5).
* Every WP budget knob is pinned, none left at its default: -wp-steps,
  -wp-timeout, -wp-smoke-timeout and -wp-par (whose default is the machine's
  core count), all four echoed into Result.budget, plus
  -wp-smoke-dead-local-init to complete the smoke family (the one smoke class
  WP leaves off by default). All 11
  honest tasks stay N / N and all 11 twins stay N < M with the full set on
  (measured across out/*.c). See the constants for the sizing measurement,
  including the correction it forced: on the twins the failing goal ends
  with a budget status (`[Timeout]` at the 2s sizing walls, `[Stepout]` at
  the current 10s/20000 pins), so those cells read TIMEOUT, and the wall is
  pinned small and stated rather than raised until steps bind, a point 30s
  of budget failed to reach.
* TOOL_ERROR is live: absent/dead kernel binary, empty kernel output,
  `[wp] User Error` / `Plug-in wp aborted` (measured with an unknown prover:
  exit 0, no Proved line — exit codes alone cannot be trusted), and a
  `Failed:` prover status outside a smoke test. A prover failure is never
  REFUTED — it is not evidence.

THE TWO SEMANTIC VACUITY INSTRUMENTS, and the measured division of labour:

1. -wp-smoke-tests, WP's own instrument: it asks the prover to derive \\false
   from each contract's hypotheses and from each program point's path
   condition, and reports `(Doomed)` / `Failed smoke-test`. That catches
   vacuity sitting in a *hypothesis position* — `requires 0 == 1` and
   `requires bad(x) >= 0` over an inconsistent definition both measured
   Doomed (requires_false.c, e2_reqbad.c).

2. THE CONSISTENCY PROBE, this adapter's kernel-native answer to what smoke
   provably cannot see. Measured 2026-08-31: smoke tests catch NEITHER of the
   two non-well-founded-definition probes, because the contradiction is
   laundered into an ensures *antecedent*, which is not a smoke position, and
   because alt-ergo only instantiates a definition axiom when a term over
   that symbol is in scope — no smoke goal mentions the symbol, so
   `Smoke Tests: 1 / 1` passes over a theory that is flatly inconsistent.
   Both holes are live soundness failures, not cosmetic ones: with
   `logic integer bad(integer n) = bad(n) + 1;` in scope,
   `ensures bad(x) >= 0 ==> \\result == 998` on a function returning 999 was
   VERIFIED 4 / 4 (e1_wrong.c), and the predicate form
   `predicate bad(integer n) = ! bad(n);` did the same (e3_pred_wrong.c).

   So the adapter puts the term in scope and asks the kernel. For every
   RECURSIVE logic/predicate definition in the kernel's own normalized AST it
   synthesizes two probe functions carrying COMPLEMENTARY preconditions over
   that symbol — `F(a) >= 0` / `F(a) < 0` for a logic function, `P(a)` /
   `!P(a)` for a predicate — and re-runs WP restricted to them with -wp-fct.
   No consistent theory can make both members of a complementary pair
   underivable-from, so BOTH smoke goals coming back `(Doomed)` is a kernel
   proof that the file's logic environment is inconsistent -> VACUOUS. The
   verdict is the prover's, not a regex's, and the AND over the pair is what
   makes it one-sided: a merely lopsided definition (fact is never negative,
   so `fact(a) < 0` is genuinely unsatisfiable) dooms at most one side.
   Measured: both probes Doomed on both holes; `Smoke Tests: 2 / 2` (neither
   doomed) on the honest recursive lowerings count_matches and factorial.

3. THE STRUCTURAL BACKSTOP, second line only. A non-well-founded recursive
   definition is an inconsistency vector whether or not alt-ergo finds the
   contradiction at this budget, and WP checks logic-function termination
   never (lower_framac.py's docstring records the same measurement from the
   other side). Frama-C 33 has no `decreases` clause for a logic definition
   at all — `decreases` inside a `logic ... = ...;` annotation is a parse
   error, measured — so the only expressible well-foundedness obligation is
   the emitted-goal form the lowering already produces: one
   `lemma <F>_terminates_<k>` per recursive call, stating that the measure is
   bounded and decreases. A recursive F with no such obligation is refused.
   This is a naming convention and is therefore NOT what the soundness claim
   rests on — instrument 2 runs first and decides on kernel evidence; this
   only fails closed on definitions whose inconsistency alt-ergo did not
   find.
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

from . import Outcome, Result, safe_text, sha256_file
from .discover import find, missing

FRAMAC = find("T_FRAMAC", ['frama-c'], [".opam/*/bin/frama-c"])
_FRAMAC_WHY = missing("framac", "T_FRAMAC", ['frama-c'], [".opam/*/bin/frama-c"])
DEFAULT_STEPS = 20_000
WALL_S = 240
PRINT_WALL_S = 60
PROBE_WALL_S = 120
# WP leaves both at 2s and prints neither, so a version bump could move them
# under a witness silently. Pinned for that reason, and sized by measurement,
# not raised on principle: NO verdict in the 24-cell corpus, the 31 Wave-1
# probes or the 8 hole probes differs between 2s and 30s on either knob. The
# slowest honest goal in out/*.c finishes in 28ms and the slowest smoke goal
# that ever doomed took 13ms, so these are ~350x margins against load on a
# shared box, which is what they are for.
#
# Sizing them is a cost decision because both are pure WALL bounds with no
# step-budget twin: WP exposes -wp-smoke-timeout only, and on a recursive
# definition NO smoke goal is refutable, so each one burns its full wall
# (factorial.c: 5.4s at 2s, 8.0s at 5s, 33s at 30s). Correcting the record
# above: for the twins -wp-steps is NOT what ends the failing goal — every
# twin in out/*.c fails `[Timeout]`, never `[Stepout]`, at 2s and at 30s
# alike, so alt-ergo never reaches 20 000 steps on those VCs and the wall is
# the operative budget bound there. Raising it buys no verdict, only
# ~13s of suite time per extra second, so it stays small and stated.
GOAL_TIMEOUT_S = 10
SMOKE_TIMEOUT_S = 5

# THE ARITHMETIC MODEL, pinned 2026-09-01 because the default one was
# UNSOUND for t. WP's default machine-integer model types every C `int` with
# is_sint32, so the hypothesis `x <= 2^31-1` is handed to the prover for
# free — and SPEC.md says t integers are mathematical and unbounded.
# MEASURED on the differential fuzzer's probes: under the default model
# framac VERIFIED fz_p_intwidth (ensures r <= 2^31-1 with both branches
# live) while dafny, verus, spark, lean, rocq and fstar REFUTED it, and the
# same for fz_p_seqlen (a seq length in an `int` formal) and for a
# seq-element probe no fuzzer task had reached until this repair added it
# (fz_p_elemwidth, `ensures len(s) > 0 ==> s[0] <= 2^31-1`: 10/10 goals
# proved, twin refuted, so the flip rule would have COUNTED it).
# `+nat` is WP's own natural-arithmetic selector: C integers are modelled by
# mathematical integers with no range hypothesis at all, which is exactly
# SPEC.md's int. Under it all three probes are REFUTED with the other six
# kernels, and all 22 committed cells (11 real VERIFIED, 11 twin REFUTED)
# are unchanged, goal counts included.
#
# This is the ONE place the choice can be made — ACSL's unbounded `integer`
# is a LOGIC type, and Frama-C 33 rejects it for a ghost variable and for a
# ghost function's parameters and result (both measured: "syntax error ...
# before or at token"), so no C program lower_framac.py could emit carries
# an unbounded program variable. The lowering emits the C; the model that
# says what a C int MEANS is a flag, and it is pinned here with the rest.
# It only ever REMOVES a hypothesis, so it can turn a proof into a
# non-proof, never the reverse.
MODEL = "Typed+nat"
# WP names every goal after the model; the consistency probe reads goal
# names, so the two must move together.
GOAL_PREFIX = MODEL.lower().replace("+", "_") + "_"

# -wp-par defaults to the machine's core count (measured: `default: 120` on
# this box), which is the roadmap's "prover auto-detect" left unpinned. It is
# verdict-relevant, not cosmetic: the bound that ends a failing goal here is a
# wall, so how much CPU each prover gets decides how far it got — the same
# witness taken at -wp-par 120 and re-taken on a laptop is not the same
# experiment. Pinned at 4, which any machine can honour; on factorial.c the
# measured wall is 22.7s at 1, 10.2s at 4, 8.0s at 8.
PAR = 4

# admit/assumes discharge goals by fiat at the use site; axiomatic/axiom are
# assumed globally with no emitted goal (see module docstring, measured);
# `requires \false` kept although smoke tests subsume it — the regex is the
# second line and costs nothing.
BANNED = re.compile(
    r"\badmit\b|\bassumes\b|\baxiomatic\b|\baxiom\b|requires\s+\\false",
    re.IGNORECASE)

# Cyrillic/Greek confusables folded to ASCII before the raw fallback scan
# (homoglyph_axiom.c: frama-c rejects the homoglyph identifier -> MALFORMED
# regardless; the fold only upgrades the fallback label, never gates VERIFIED).
_FOLD = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y",
    "і": "i", "ѕ": "s", "ԁ": "d", "ɑ": "a", "α": "a", "ο": "o", "τ": "t",
    "ι": "i", "А": "A", "Е": "E", "О": "O", "С": "C", "Р": "P", "Х": "X"})

_PROVED = re.compile(r"^\[wp\] Proved goals:\s*(\d+)\s*/\s*(\d+)\s*$", re.M)
_STATUS = re.compile(r"^\s+(Qed|Alt-Ergo|Timeout|Stepout|Unknown|Failed)"
                     r":?\s+\d+", re.M)
_DOOMED = re.compile(r"Failed smoke-test|\(Doomed\)")
_SMOKE = re.compile(r"^\s+Smoke Tests:\s+(\d+)\s*/\s*(\d+)", re.M)
_FAILED = re.compile(r"^\s+Failed:\s+\d+", re.M)
_TOOLFAIL = re.compile(r"Plug-in wp aborted|\[wp\] User Error")
_PRINT_MARK = "/* Generated by Frama-C */"

# --- refutation-certificate machinery (see the doctrine, module docstring) --
CERT_NAME = "t_refutation_certificate"
# WP names a named assert's goal <model>_<fn>_assert_<name> (measured:
# typed_nat_t_certificate_assert_t_refutation_certificate). Suffix-anchored
# so an identifier merely CONTAINING the name (a task called
# refutation_certificate lowers to refutation_certificate_t, whose unnamed
# assert goal ends _t_assert) can demote a file but never forge acceptance.
_CERT_GOAL = re.compile("_assert_" + CERT_NAME + "$")
# The kernel's verdict vocabulary (frama-c-wp 33.0 report code): none,
# computing, valid, invalid, unknown, timeout, stepout, failed. Budget
# statuses make the file TIMEOUT; everything else unproved is UNPROVED,
# "invalid" included, because that status was unreachable under the pinned
# alt-ergo in every measurement (even ensures \result == 1 over return 0
# comes back stepout) and an unmeasured pathway must not mint.
_BUDGET_VERDICTS = {"timeout", "stepout"}
# Text fallback when the kernel wrote no JSON report: WP prints one line per
# unproved goal, e.g. "[wp] [Stepout] typed_nat_abs_t_ensures (Alt-Ergo)".
_GOAL_LINE = re.compile(r"^\[wp\] \[(Timeout|Stepout|Unknown|Failed)\]"
                        r"\s+(\S+)", re.M)


def _load_report(p: Path):
    """The kernel's per-goal JSON report (-wp-report-json), or None. None
    never mints anything: no report, no certificate, and the unproved
    partition falls back to the per-goal text lines."""
    try:
        entries = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if isinstance(entries, list) and all(isinstance(e, dict)
                                         for e in entries):
        return entries
    return None


def _unproved_goals(report, out: str) -> list:
    """(goal, status) for every unproved non-smoke goal, from the JSON
    report when present, else from the per-goal text lines."""
    if report is not None:
        return [(e.get("goal", "?"), str(e.get("verdict", "?")).lower())
                for e in report if not e.get("smoke") and not e.get("passed")]
    return [(g, s.lower()) for s, g in _GOAL_LINE.findall(out)]


def _cert_status(report) -> tuple[bool, bool, str]:
    """(declared, accepted, note) for the refutation certificate, judged on
    the kernel's own per-goal report and nothing else. Accepted requires:
    exactly one certificate-named assert goal, proved; and every goal in the
    certificate's audit set proved, that set being every goal of the
    certificate's enclosing function (its branch-decision asserts, its
    assigns, its smoke tests) plus every function-less global goal (the
    termination lemmas the logic definitions stand on)."""
    if report is None:
        return False, False, "kernel wrote no per-goal report"
    certs = [e for e in report
             if not e.get("smoke") and _CERT_GOAL.search(e.get("goal", ""))]
    if not certs:
        return False, False, "no certificate goal declared"
    if len(certs) != 1:
        return True, False, f"{len(certs)} certificate goals declared"
    fn = certs[0].get("function")
    if not fn:
        return True, False, "certificate goal outside any function"

    def ok(e):
        return bool(e.get("passed")) and (
            e.get("smoke") or str(e.get("verdict", "")).lower() == "valid")

    audit = [e for e in report
             if e.get("function") == fn or not e.get("function")]
    bad = [e.get("goal", "?") for e in audit if not ok(e)]
    if bad:
        return True, False, ("unproved in the certificate audit set: "
                             + ", ".join(bad[:4]))
    return True, True, fn

# --- consistency-probe machinery (see docstring section 2) -----------------
_PROBE_TAG = "t_vacuity_probe"
_ACSL_BLOCK = re.compile(r"/\*@(.*?)\*/", re.S)
# Matches a DEFINITION (`... ) =`), never a bare declaration: only definitions
# are assumed as axioms, and only those can make the theory inconsistent.
_LOGIC_DEF = re.compile(
    r"\b(?P<kind>logic|predicate)\s+"
    r"(?:(?P<ret>[^;{}()=]*?)\s+)??"       # `predicate p(...)` has no return type
    r"(?P<name>[A-Za-z_]\w*)\s*"
    r"(?P<labels>\{[^{}]*\})?\s*"
    r"\((?P<params>[^()]*)\)\s*=")
_PARAM = re.compile(r"^(?P<ty>.+?)\s*(?P<stars>\**)\s*(?P<nm>[A-Za-z_]\w*)$")
# -print renders ACSL `integer` as ℤ; `int` appears for C-typed parameters.
_INT_TYPES = {"ℤ", "integer", "int"}


def _wf_obligation(flat: str, name: str) -> bool:
    """A kernel-emitted well-foundedness goal for recursive symbol `name`.
    Frama-C 33 rejects `decreases` inside a logic definition (measured), so
    the lemma form lower_framac.py emits is the only one that exists."""
    return re.search(r"\blemma\s+" + re.escape(name) + r"_(?:terminates|decreases)",
                     flat) is not None


def _recursive_defs(norm: str) -> tuple[list, str]:
    """Recursive ACSL logic/predicate definitions in the kernel's normalized
    AST, with the flattened annotation text they were read from."""
    body = norm.split(_PRINT_MARK, 1)[1] if _PRINT_MARK in norm else norm
    flat_all, defs = [], []
    for blk in _ACSL_BLOCK.findall(body):
        flat = " ".join(blk.split())
        flat_all.append(flat)
        for m in _LOGIC_DEF.finditer(flat):
            depth, rhs = 0, []
            for ch in flat[m.end():]:
                if ch in "([":
                    depth += 1
                elif ch in ")]":
                    depth -= 1
                elif ch == ";" and depth <= 0:
                    break
                rhs.append(ch)
            name = m.group("name")
            if not re.search(r"\b" + re.escape(name) + r"\b", "".join(rhs)):
                continue                    # non-recursive: a definitional
            params, typed = [], True        # extension, always consistent
            for raw in (m.group("params") or "").split(","):
                raw = raw.strip()
                if raw in ("", "void"):
                    continue
                pm = _PARAM.match(raw)
                if not pm or pm.group("ty").strip() not in _INT_TYPES:
                    typed = False           # cannot build a well-typed probe
                    break
                params.append("int " + pm.group("stars"))
            defs.append({"kind": m.group("kind"), "name": name,
                         "labels": m.group("labels"), "params": params,
                         "typed": typed})
    return defs, " ".join(flat_all)


def _probe_source(raw: str, defs: list) -> tuple[str, list]:
    """Original source + two complementary-precondition probe functions per
    recursive symbol. Both preconditions doomed == theory inconsistent."""
    lines, pairs = [raw, ""], []
    for i, d in enumerate(defs):
        if not d["typed"]:
            continue
        args = [f"t_p{j}" for j in range(len(d["params"]))]
        sig = ", ".join(t + a for t, a in zip(d["params"], args)) or "void"
        lab = ("{" + ",".join("Pre" for _ in d["labels"].strip("{}").split(","))
               + "}") if d["labels"] else ""
        call = f"{d['name']}{lab}({', '.join(args)})"
        pos, neg = ((call, f"!({call})") if d["kind"] == "predicate"
                    else (f"({call}) >= 0", f"({call}) < 0"))
        fp, fn = f"{_PROBE_TAG}_pos_{i}", f"{_PROBE_TAG}_neg_{i}"
        for f, req in ((fp, pos), (fn, neg)):
            lines += [f"/*@ requires {req};", "    assigns \\nothing; */",
                      f"void {f}({sig}) {{ return; }}"]
        pairs.append((d["name"], fp, fn))
    return "\n".join(lines), pairs


def _doomed_fn(out: str, fn: str) -> bool:
    return re.search(r"\(Doomed\)\s+" + re.escape(GOAL_PREFIX)
                     + re.escape(fn) + r"_wp_smoke", out) is not None


def _consistency_probe(raw: str, defs: list, budget: int) -> tuple[list, str]:
    """Ask the kernel whether the file's logic environment is inconsistent.
    Returns (symbols proved inconsistent, why-the-probe-was-inconclusive)."""
    if _PROBE_TAG in raw:
        return [], f"source already defines {_PROBE_TAG}*"
    src, pairs = _probe_source(raw, defs)
    if not pairs:
        return [], "no probe expressible for the parameter types"
    with tempfile.TemporaryDirectory(prefix="t-framac-probe-") as td:
        f = Path(td) / "probe.c"
        f.write_text(src, encoding="utf-8")
        # -wp-fct restricts goal generation to the probes, so the original
        # file's own goals are neither re-proved nor charged to this run.
        fcts = ",".join(fn for _, pos_fn, neg_fn in pairs
                        for fn in (pos_fn, neg_fn))
        try:
            _, out = _run(
                [FRAMAC, "-wp", "-wp-model", MODEL, "-wp-fct", fcts,
                 "-wp-prover", "alt-ergo",
                 "-wp-steps", str(budget), "-wp-cache", "none", "-wp-par",
                 str(PAR), "-wp-timeout", str(GOAL_TIMEOUT_S),
                 "-wp-smoke-tests", "-wp-smoke-dead-local-init",
                 "-wp-smoke-timeout", str(SMOKE_TIMEOUT_S), str(f)],
                PROBE_WALL_S)
        except (subprocess.TimeoutExpired, OSError) as e:
            return [], f"probe run did not complete: {type(e).__name__}"
    if not _PROVED.search(out) or _TOOLFAIL.search(out):
        return [], "probe file produced no WP goals"
    return [sym for sym, p, n in pairs
            if _doomed_fn(out, p) and _doomed_fn(out, n)], ""


def _budget(steps: int) -> str:
    """Every knob that can move a verdict, in the witness. A pin nobody can
    read from the record is not a pin (fstar.py sets the same precedent)."""
    return (f"wp-model={MODEL} wp-steps={steps} "
            f"wp-timeout={GOAL_TIMEOUT_S}s "
            f"wp-smoke-timeout={SMOKE_TIMEOUT_S}s wp-par={PAR}")


def version() -> str:
    if not FRAMAC:
        raise SystemExit(_FRAMAC_WHY)
    p = subprocess.run([FRAMAC, "-version"], capture_output=True, text=True)
    return f"frama-c {p.stdout.strip()} / alt-ergo 2.4.3-free"


def _ver() -> str:
    try:
        return version()
    except (SystemExit, OSError):
        return "frama-c (unavailable)"


def _run(cmd: list, wall: int):
    """(returncode, decoded output). Decoded errors='replace' because kernel
    diagnostics echo raw source bytes — text=True would re-crash on the very
    non-UTF8 probes safe_text exists for."""
    p = subprocess.run(cmd, capture_output=True, timeout=wall)
    return p.returncode, (p.stdout.decode("utf-8", errors="replace")
                          + p.stderr.decode("utf-8", errors="replace"))


def verify(path: Path, budget: int = DEFAULT_STEPS) -> Result:
    src_hash = sha256_file(path)
    t0 = time.monotonic()
    if not FRAMAC:
        return Result("framac", "frama-c (absent)", src_hash,
                      Outcome.TOOL_ERROR, budget=_budget(budget),
                      error=_FRAMAC_WHY)

    # The t lowering emits UTF-8 only, so a non-decodable source is not a t
    # artifact: MALFORMED, before any kernel run. Measured 2026-08-31 without
    # this gate: frama-c 33 accepts raw bytes inside a plain comment and
    # proves the goals (nonutf8.c scored VERIFIED), and 10MB of random bytes
    # (random10mb.c) burned the full wall backstop.
    try:
        raw_src = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as e:
        return Result("framac", _ver(), src_hash, Outcome.MALFORMED,
                      wall_ms=int((time.monotonic() - t0) * 1000),
                      budget=_budget(budget),
                      error=f"source is not valid UTF-8: {e}")

    # Ban audit on the kernel's normalized view; the scan starts after the
    # print marker so the echoed source PATH (e.g. axiom_false.c in the
    # Parsing line) cannot trip the regex.
    print_ok, norm = False, ""
    try:
        rc_p, norm = _run([FRAMAC, "-no-autoload-plugins", "-print",
                           str(path)], PRINT_WALL_S)
        print_ok = rc_p == 0 and _PRINT_MARK in norm
    except (subprocess.TimeoutExpired, OSError):
        pass
    if print_ok:
        banned = BANNED.findall(norm.split(_PRINT_MARK, 1)[1])
        ban_audit = "kernel-normalized (-print)"
    else:
        raw = safe_text(path)
        banned = BANNED.findall(raw) or BANNED.findall(raw.translate(_FOLD))
        ban_audit = "raw fallback (unparseable source)"
    if banned:
        return Result("framac", _ver(), src_hash, Outcome.VACUOUS,
                      wall_ms=int((time.monotonic() - t0) * 1000),
                      budget=_budget(budget),
                      extras={"banned_tokens": banned[:5],
                              "ban_audit": ban_audit})

    # Recursive logic/predicate definitions only: WP assumes a definition as
    # an axiom and emits no goal for it, and it never checks that the
    # recursion terminates. Non-recursive definitions are definitional
    # extensions and cannot introduce an inconsistency, so they are not
    # probed and cost nothing.
    rec, flat = _recursive_defs(norm) if print_ok else ([], "")
    probe_note = "no recursive logic definition"
    if rec:
        inconsistent, probe_note = _consistency_probe(raw_src, rec, budget)
        if inconsistent:
            return Result("framac", _ver(), src_hash, Outcome.VACUOUS,
                          wall_ms=int((time.monotonic() - t0) * 1000),
                          budget=_budget(budget),
                          error="logic environment is inconsistent: WP doomed "
                                "both halves of a complementary hypothesis "
                                "pair over " + ", ".join(inconsistent),
                          extras={"inconsistent_symbols": inconsistent,
                                  "vacuity_instrument": "consistency probe "
                                                        "(-wp-fct smoke)",
                                  "banned_tokens": [], "ban_audit": ban_audit})
        unmeasured = [d["name"] for d in rec if not _wf_obligation(flat, d["name"])]
        if unmeasured:
            return Result("framac", _ver(), src_hash, Outcome.VACUOUS,
                          wall_ms=int((time.monotonic() - t0) * 1000),
                          budget=_budget(budget),
                          error="recursive logic definition with no emitted "
                                "well-foundedness obligation: "
                                + ", ".join(unmeasured),
                          extras={"unmeasured_recursion": unmeasured,
                                  "vacuity_instrument": "structural backstop",
                                  "probe_note": probe_note,
                                  "banned_tokens": [], "ban_audit": ban_audit})

    try:
        # -wp-report-json is the audit channel, not a budget knob: it makes
        # the kernel write its OWN per-goal verdicts, which is what the
        # unproved partition and the certificate acceptance are judged on
        # (a summary line cannot say WHICH goal timed out, and a proved
        # certificate goal is invisible in the default text output).
        with tempfile.TemporaryDirectory(prefix="t-framac-report-") as td:
            rj = Path(td) / "report.json"
            rc, out = _run(
                [FRAMAC, "-wp", "-wp-model", MODEL, "-wp-prover", "alt-ergo",
                 "-wp-steps",
                 str(budget), "-wp-cache", "none", "-wp-par", str(PAR),
                 "-wp-timeout", str(GOAL_TIMEOUT_S), "-wp-smoke-tests",
                 "-wp-smoke-dead-local-init", "-wp-smoke-timeout",
                 str(SMOKE_TIMEOUT_S), "-wp-report-json", str(rj), str(path)],
                WALL_S)
            report = _load_report(rj)
    except subprocess.TimeoutExpired:
        return Result("framac", _ver(), src_hash, Outcome.TIMEOUT,
                      wall_ms=int((time.monotonic() - t0) * 1000),
                      budget=_budget(budget), error="wall backstop fired")
    except OSError as e:
        return Result("framac", _ver(), src_hash, Outcome.TOOL_ERROR,
                      wall_ms=int((time.monotonic() - t0) * 1000),
                      budget=_budget(budget),
                      error=f"kernel binary failed to run: {e}")
    wall = int((time.monotonic() - t0) * 1000)
    proved = list(_PROVED.finditer(out))
    m = proved[-1] if proved else None
    statuses = _STATUS.findall(out)
    smoke = _SMOKE.search(out)
    unproved = _unproved_goals(report, out)
    declared, accepted, cert_note = _cert_status(report)
    # The demotion gate: a file carrying the certificate name anywhere in
    # the kernel's normalized view (raw fallback if unparseable) can never
    # mint VERIFIED, whether or not a certificate goal was declared.
    scan = norm.split(_PRINT_MARK, 1)[1] if print_ok else safe_text(path)
    cert_marked = CERT_NAME in scan or declared
    err = ""

    if not out.strip():
        outcome = Outcome.TOOL_ERROR
        err = "kernel produced empty output"
    elif _DOOMED.search(out) or (smoke and smoke.group(1) != smoke.group(2)):
        outcome = Outcome.VACUOUS       # contract hypotheses derive \false
    elif _TOOLFAIL.search(out):
        outcome = Outcome.TOOL_ERROR    # plugin/prover infrastructure failure
        err = out[-400:]
    elif m is None:
        outcome = Outcome.MALFORMED     # WP never reached goal generation
    elif int(m.group(2)) == 0:
        outcome = Outcome.MALFORMED     # zero proof obligations is no theorem
    elif _FAILED.search(out):
        outcome = Outcome.TOOL_ERROR    # prover failure outside a smoke test
        err = out[-400:]
    elif int(m.group(1)) == int(m.group(2)):
        if not (rc == 0 and print_ok):
            outcome = Outcome.TOOL_ERROR  # all-proved without a clean exit
            err = out[-400:]              # or without the controlled ban audit
        elif cert_marked:
            # Certificate file, everything proved: the kernel accepted the
            # ground proof that ensures fails at the witness. A file that
            # merely CARRIES the name without an accepted certificate goal
            # is only demoted: never VERIFIED, and never REFUTED either.
            if accepted:
                outcome = Outcome.REFUTED
                err = "kernel-accepted refutation certificate in " + cert_note
            else:
                outcome = Outcome.UNPROVED
                err = ("carries the certificate name without an accepted "
                       "certificate: " + cert_note)
        else:
            outcome = Outcome.VERIFIED
    elif accepted and rc == 0 and print_ok:
        # Unproved goals remain (the twin's own contract, typically ended by
        # a budget), but the certificate's audit set is fully accepted: the
        # kernel proved that ensures fails at the measured witness input,
        # which is the positive evidence REFUTED requires.
        outcome = Outcome.REFUTED
        err = "kernel-accepted refutation certificate in " + cert_note
    elif cert_marked:
        outcome = Outcome.UNPROVED      # a rejected certificate never mints
        err = "certificate not accepted: " + cert_note
    elif any(s in _BUDGET_VERDICTS for _, s in unproved):
        outcome = Outcome.TIMEOUT       # a pinned budget fired: wall or steps
        err = ("budget exhausted on "
               + ", ".join(g for g, s in unproved[:4]
                           if s in _BUDGET_VERDICTS))
    else:
        outcome = Outcome.UNPROVED      # stopped without budget exhaustion
        err = ("unproved without budget exhaustion: "
               + ", ".join(f"{g} ({s})" for g, s in unproved[:4]))
    return Result("framac", _ver(), src_hash, outcome,
                  ok=outcome == Outcome.VERIFIED, exit_code=rc,
                  wall_ms=wall, budget=_budget(budget), error=err,
                  extras={"proved": m.group(0).replace("[wp] ", "").strip()
                          if m else None,
                          "goal_statuses": statuses[:8],
                          "unproved_goals": unproved[:8],
                          "certificate": {"declared": declared,
                                          "accepted": accepted,
                                          "note": cert_note}
                          if cert_marked else None,
                          "smoke": smoke.group(0).strip() if smoke else None,
                          "recursive_defs": [d["name"] for d in rec],
                          "probe_note": probe_note,
                          "banned_tokens": [],
                          "ban_audit": ban_audit})
