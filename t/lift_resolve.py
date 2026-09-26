"""The Dafny front end: turn a .dfy path into the resolver's print, honestly.

LIFTER-DESIGN.md section 1 (why rprint, not a hand-rolled Dafny parser),
section 3 (what the print is a print OF), section 10(b) (rprint is a
measured fixpoint: rprint(f) reprints identically, which is what makes it
safe to parse), and section 18.1 (the three-invocation exit-code
discipline). Follows `verifiers/dafny.py`'s invocation style (DAFNY
resolution via `verifiers.discover.find`, `subprocess.run` with
`capture_output=True, text=True` and a wall-clock `timeout`) but is a
separate, simpler front end: `verifiers/dafny.py.verify` is the grading
kernel adapter (WS-7), this module is the lift pipeline's own front door
and never scores a task.

Architecture role (LIFTER-DESIGN.md section 2's table, copied verbatim):
    input: a .dfy path
    output: rprint text, exit code, stderr
    MAY decide: `resolve-failure`, `parse-failure` (unknown token)
    MAY NOT decide: nothing about constructs

Section 18.1's three invocations, each under a wall timeout, each recording
its exit code and stdout:
    1. `dafny resolve FILE --allow-warnings --rprint:OUT`   (the AST source)
    2. `dafny resolve FILE --allow-warnings --print:OUT2`   (kept beside the
       record so a row can quote what the author wrote, never parsed)
    3. `dafny verify FILE --allow-warnings`                 (the source
       verdict, decision 12: lift and tag `source-unverified` rather than
       refuse on a non-zero exit here)

Measured (section 18.1): without `--allow-warnings`, 257 of 785 corpus files
exit 2 on warnings alone; with it, exit 2 is a real error. The exit code is
read BEFORE the rprint file is opened (it is written even on a type error),
and a non-zero resolve exit is `resolve-failure` carrying dafny's first
`Error:` line; the rprint is never parsed in that case. Subprocess flags are
written `--flag:value` (Windows-safe per RUN-ON-WINDOWS.md), matching the
banked corpus rprints' own invocation
(`dafny resolve F --allow-warnings --rprint:OUT`).

MEASURED QUIRK (2026-09-05, this box, dafny 4.11.0): every diagnostic this
module cares about -- a resolution `Error:` line, a parse `Error:` line, a
`Warning:` line, even the CLI's own "file not found" -- is written to
STDOUT, never stderr (checked directly: `dafny resolve bad.dfy
--allow-warnings --rprint:x` on a file with a real resolution error, and
again on a file with a deprecated-syntax warning under the same flag, both
land their message on stdout with stderr empty). `ResolveResult
.resolve_stderr` is still named `_stderr` per the interfaces contract, but
it is populated defensively: real stderr text when the process actually
wrote to stderr (kept first, in case some other failure mode -- a crash,
an assertion -- ever does), the stdout capture otherwise. This way the
field always carries the diagnostic regardless of which stream dafny used,
which is what every caller of this module actually needs from it.
"""

from __future__ import annotations

import dataclasses
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from lift_ast import (
    DecreasesClause, EnsuresClause, ForStmt, IfStmt, InvariantClause, LabelStmt,
    BlockStmt, MethodDecl, ModifiesClause, Param, Refusal, RequiresClause, WhileStmt,
)
# Reused deliberately, not reimplemented: `_lex`/`_compute_line_starts`
# tokenise ANY Dafny text the same way regardless of whose text it is, and
# `_Parser`/`_parse_mspec_list`/`_parse_loopspec_list`/`parse_expr`/
# `parse_type` are the exact grammar a rprint-derived clause already goes
# through -- see `check_against_source`'s docstring below for why this
# module, not `lift_parse.py`, is where the ORIGINAL source text also
# needs to be parsed once.
from lift_parse import LiftParseError, _Parser, _compute_line_starts, _lex
from verifiers import dafny as _dafny_kernel

DEFAULT_TIMEOUT_S = 120.0

# Dafny's own tally line names which kind of error it hit (measured,
# module docstring): "N parse errors detected" for a token outside
# Dafny's OWN grammar entirely, "N resolution/type errors detected" for
# everything else (a name that does not resolve, a type mismatch, an
# ill-formed reveal, ...). `lift_resolve.ResolveResult.refusal`'s
# docstring says an implementer who finds dafny itself reporting an
# unparseable-token error at this stage should mint `parse-failure`
# here rather than `resolve-failure` -- this is the measured signal that
# tells the two apart without guessing from the error text's wording.
_PARSE_ERROR_TALLY_RE = re.compile(r"\b\d+\s+parse errors?\s+detected\b", re.IGNORECASE)

# Dafny's own diagnostic line shape (measured):
#   "<file>(<line>,<col>): Error: <message>"
#   "<file>(<line>,<col>): Warning: <message>"
_DIAG_LOCATION_RE = re.compile(r"\((\d+),\d+\):\s*(Error|Warning):")


def _first_error_line(text: str) -> Optional[str]:
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if "Error:" in stripped:
            return stripped
    return None


def _extract_warnings(text: str) -> list[str]:
    return [raw_line.strip() for raw_line in text.splitlines() if "Warning:" in raw_line]


def _error_line_number(diag_line: Optional[str]) -> int:
    """Pull the 1-based source line out of a dafny diagnostic's own
    `(line,col):` locator, e.g. "foo.dfy(65,60): Error: ...". `0` when the
    diagnostic carries no locator at all (a CLI-level message such as
    "file not found", or an empty diagnostic on a bare non-zero exit)."""
    if not diag_line:
        return 0
    m = _DIAG_LOCATION_RE.search(diag_line)
    return int(m.group(1)) if m else 0


@dataclass
class ResolveResult:
    """Everything section 18.1's three invocations produced for one file.

    `resolve_exit` and `resolve_stderr` are the `--rprint` invocation's
    exit code and captured stderr (the one that gates whether `rprint_text`
    is meaningful at all). `rprint_text` is `None` exactly when
    `resolve_exit != 0`: the rprint file is still written by dafny on a
    type error (section 18.1), but this module never reads it in that
    case, because a `resolve-failure` refusal must never be second-guessed
    by a downstream parse of a program dafny itself rejected.

    `print_text` is the `--print:OUT2` invocation's output, kept verbatim
    for provenance (a disagreement-table row can quote what the author
    literally wrote) and never fed to `lift_parse.parse`.

    `verify_exit` is decision 12's source verdict (`dafny verify FILE
    --allow-warnings`): 0 or 4 on Dafny 4.11.0 per `t/README.md`'s measured
    exit codes, carried on every row rather than gating the lift. `None`
    when the resolve step already failed and the verify invocation was
    skipped (no point verifying a file that does not even resolve), or
    when a later invocation (the `--print` or `verify` step) hit the wall
    timeout after a clean `--rprint` resolve (see `resolve`'s docstring:
    a timeout on ANY of the three invocations is `resolve-failure`, and
    `verify_exit`/`print_text` for a step that never finished stay `None`
    even though `rprint_text` from an earlier, already-completed step is
    kept -- `rprint_text`'s nullity is tied strictly to `resolve_exit`,
    per this field's own docstring, not to the overall outcome).

    `refusal` is `None` on a clean resolve; otherwise a `Refusal` with
    `stage="resolve"` and `reason` one of `resolve-failure` (dafny exited
    non-zero with a real `Error:` line) or `parse-failure` (an unknown
    token surfaced at this stage rather than in `lift_parse.py` -- see the
    architecture table's literal wording above, copied as written even
    though `parse-failure`'s trigger in section 5 is "a token outside
    section 3's grammar", which `lift_parse.py` ordinarily detects; this
    module's `may decide` column names both, so an implementer who finds
    dafny itself reporting an unparseable-token error at the resolve stage
    (as opposed to a resolution/type error) should mint `parse-failure`
    here rather than pass a bogus rprint on to `lift_parse.parse`)."""
    source_path: Path
    resolve_exit: int
    resolve_stderr: str
    rprint_text: Optional[str]
    print_text: Optional[str]
    verify_exit: Optional[int]
    refusal: Optional[Refusal]
    warnings: list[str] = field(default_factory=list)


def _dafny_binary() -> str:
    dafny = _dafny_kernel.DAFNY
    if not dafny:
        raise SystemExit(_dafny_kernel._DAFNY_WHY)
    return dafny


def _run(dafny: str, args: list[str], timeout_s: float) -> tuple[int, str, str, bool]:
    """One dafny invocation as an argument list (no shell -- corpus file
    names contain spaces and one contains non-ASCII, RUN-ON-WINDOWS.md).
    Returns (exit_code, stdout, stderr, timed_out); on a timeout,
    exit_code is -1 (dafny gives no real exit code for a killed process)
    and whatever partial stdout/stderr the OS handed back is kept rather
    than discarded."""
    try:
        proc = subprocess.run(
            [dafny, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
        )
        return proc.returncode, proc.stdout, proc.stderr, False
    except subprocess.TimeoutExpired as e:
        out = e.stdout or ""
        err = e.stderr or ""
        if isinstance(out, bytes):
            out = out.decode("utf-8", errors="replace")
        if isinstance(err, bytes):
            err = err.decode("utf-8", errors="replace")
        return -1, out, err, True


def _diag_text(stdout: str, stderr: str) -> str:
    """See the module docstring's MEASURED QUIRK note: dafny 4.11.0 writes
    its diagnostics to stdout, not stderr, on this box. Real stderr text
    wins when present (a crash, an unhandled exception print dafny might
    one day route there); stdout is the measured fallback."""
    return stderr if stderr.strip() else stdout


def resolve(dfy_path: Path, timeout_s: float = DEFAULT_TIMEOUT_S) -> ResolveResult:
    """Run section 18.1's three dafny invocations against `dfy_path` and
    report their exit codes and text, honestly.

    Inputs: a .dfy path, a wall-clock timeout in seconds applied to each of
    the three subprocess invocations independently (never a combined
    budget: a slow verify must not truncate a fast resolve's rprint).

    Output: a `ResolveResult`. `resolve_exit` and `rprint_text`/`print_text`
    always come from the `--rprint`/`--print` invocations respectively (two
    separate dafny processes, per section 18.1, item 1: "The rprint file is
    still written on a type error, so the exit code is read BEFORE the
    rprint is opened"). `verify_exit` comes from the third invocation and is
    `None` when the first failed.

    MAY decide (section 2's table, verbatim): `resolve-failure`,
    `parse-failure` (unknown token).

    MAY NOT decide: nothing about constructs -- no refusal reason from
    section 5's construct vocabulary (`array`, `heap`, `assume`, ...)
    is ever raised here; those all require a parsed AST and belong to
    `lift_classify.py`. A timeout on any of the three invocations is
    reported as `resolve-failure` with the timeout named in `token`, never
    silently treated as success or failure of a different kind."""
    dfy_path = Path(dfy_path)
    dafny = _dafny_binary()
    warnings: list[str] = []

    with tempfile.TemporaryDirectory(prefix="lift_resolve_") as tmp:
        tmp_dir = Path(tmp)
        rprint_out = tmp_dir / "rprint_out.dfy"
        print_out = tmp_dir / "print_out.dfy"

        # 1. dafny resolve FILE --allow-warnings --rprint:OUT
        exit1, out1, err1, timed_out1 = _run(
            dafny,
            ["resolve", str(dfy_path), "--allow-warnings", f"--rprint:{rprint_out}"],
            timeout_s,
        )
        diag1 = _diag_text(out1, err1)
        warnings.extend(_extract_warnings(diag1))

        if timed_out1:
            return ResolveResult(
                source_path=dfy_path,
                resolve_exit=exit1,
                resolve_stderr=diag1,
                rprint_text=None,
                print_text=None,
                verify_exit=None,
                refusal=Refusal(
                    reason="resolve-failure",
                    token=f"timeout after {timeout_s}s (resolve --rprint)",
                    line=0,
                    stage="resolve",
                ),
                warnings=warnings,
            )

        if exit1 != 0:
            err_line = _first_error_line(diag1)
            token = err_line or (diag1.strip().splitlines()[0] if diag1.strip()
                                  else f"dafny exited {exit1}")
            reason = "parse-failure" if _PARSE_ERROR_TALLY_RE.search(diag1) else "resolve-failure"
            return ResolveResult(
                source_path=dfy_path,
                resolve_exit=exit1,
                resolve_stderr=diag1,
                rprint_text=None,   # never opened on nonzero exit (section 18.1)
                print_text=None,
                verify_exit=None,
                refusal=Refusal(
                    reason=reason,
                    token=token,
                    line=_error_line_number(err_line),
                    stage="resolve",
                ),
                warnings=warnings,
            )

        # exit1 == 0: the rprint may now be opened.
        if not rprint_out.exists():
            return ResolveResult(
                source_path=dfy_path,
                resolve_exit=exit1,
                resolve_stderr=diag1,
                rprint_text=None,
                print_text=None,
                verify_exit=None,
                refusal=Refusal(
                    reason="resolve-failure",
                    token="dafny exited 0 but wrote no --rprint output",
                    line=0,
                    stage="resolve",
                ),
                warnings=warnings,
            )
        rprint_text = rprint_out.read_text(encoding="utf-8")

        # 2. dafny resolve FILE --allow-warnings --print:OUT2 (provenance
        # only; never parsed -- see the module and field docstrings).
        exit2, out2, err2, timed_out2 = _run(
            dafny,
            ["resolve", str(dfy_path), "--allow-warnings", f"--print:{print_out}"],
            timeout_s,
        )
        diag2 = _diag_text(out2, err2)
        warnings.extend(_extract_warnings(diag2))

        if timed_out2:
            return ResolveResult(
                source_path=dfy_path,
                resolve_exit=exit1,
                resolve_stderr=diag1,
                rprint_text=rprint_text,
                print_text=None,
                verify_exit=None,
                refusal=Refusal(
                    reason="resolve-failure",
                    token=f"timeout after {timeout_s}s (resolve --print)",
                    line=0,
                    stage="resolve",
                ),
                warnings=warnings,
            )

        print_text: Optional[str] = print_out.read_text(encoding="utf-8") if (
            exit2 == 0 and print_out.exists()
        ) else None

        # 3. dafny verify FILE --allow-warnings (decision 12: source
        # verdict, carried on every row, never gates the lift here).
        exit3, out3, err3, timed_out3 = _run(
            dafny,
            ["verify", str(dfy_path), "--allow-warnings"],
            timeout_s,
        )
        diag3 = _diag_text(out3, err3)
        warnings.extend(_extract_warnings(diag3))

        if timed_out3:
            return ResolveResult(
                source_path=dfy_path,
                resolve_exit=exit1,
                resolve_stderr=diag1,
                rprint_text=rprint_text,
                print_text=print_text,
                verify_exit=None,
                refusal=Refusal(
                    reason="resolve-failure",
                    token=f"timeout after {timeout_s}s (verify)",
                    line=0,
                    stage="resolve",
                ),
                warnings=warnings,
            )

        return ResolveResult(
            source_path=dfy_path,
            resolve_exit=exit1,
            resolve_stderr=diag1,
            rprint_text=rprint_text,
            print_text=print_text,
            verify_exit=exit3,
            refusal=None,
            warnings=warnings,
        )


# ===========================================================================
# Source-clause cross-check (2026-09-12, ROADMAP 16.2, LIFTER-DECISIONS.md
# row 32: "the lifter: do not trust a lossy print of the source").
#
# MEASURED DEFECT: `dafny-synthesis_task_id_598` IsArmstrong's own ensures
# reads `(n / 100) * (n / 100) * (n / 100) + ...`; `dafny resolve
# --rprint:-` prints it as `n / 100 * n / 100 * n / 100 + ...` (dafny's own
# pretty-printer drops the parentheses around a divided operand of `*`,
# even though `/` and `*` share one precedence level and left-associate,
# so the reprinted text parses to a DIFFERENT tree, `((n div 100) * n) div
# 100`, than the source's own `(n div 100) * (n div 100) * (n div 100)`).
# `lift_parse.parse` only ever sees rprint's text (`lift_resolve.resolve`'s
# own docstring, section 18.1), so the wrong tree was the only tree
# anyone ever built, and `lift_check.py`'s equivalence lemma compared that
# SAME wrong tree against itself through the SAME print -- a printer
# defect that can never be caught by construction, no matter how good the
# checker's own automation is.
#
# THE FIX: re-derive the graded method's own requires/ensures (and, on a
# best-effort basis below, every loop's invariant/decreases) from the
# ORIGINAL .dfy file's own bytes, using the EXACT SAME grammar
# (`lift_parse._Parser._parse_mspec_list`/`_parse_loopspec_list`) applied
# to a different token stream, and correct the rprint-derived method's
# specs in place wherever the two trees disagree -- so everything
# downstream (classify, rewrite, check) sees the source's own tree from
# this point on, and `lift_check`'s L_ens/L_req/L_inv lemmas compare the
# source's own text against the lifted task, never rprint's print of the
# source against itself. A method whose source text cannot be tokenised,
# whose name cannot be found in it, or whose requires/ensures/invariant
# clause COUNT cannot be matched 1:1 against rprint's own count is refused
# `source-unparseable` rather than silently trusted on rprint's word
# alone (this section's own docstrings below name where each of the three
# can fire). `decreases`/`modifies` mismatches are logged, never refused
# -- dafny itself INFERS a `decreases` the source never wrote (measured:
# IsArmstrong's own source has none, rprint's has `decreases n`), so a
# count mismatch there is expected, not a disagreement.
# ===========================================================================

_METHOD_LIKE_BASE_WORDS = ("method", "function", "predicate", "lemma")

_SPEC_KIND_NAME = {
    RequiresClause: "requires",
    EnsuresClause: "ensures",
    InvariantClause: "invariant",
    ModifiesClause: "modifies",
    DecreasesClause: "decreases",
}

# Kinds whose clause COUNT must match 1:1 between rprint and the source: a
# mismatch here means the correspondence itself cannot be trusted, so the
# method is refused rather than guessed at. `modifies`/`decreases` are
# deliberately absent (see the module-level docstring above: dafny can
# both infer and, for `modifies`, implicitly widen these, so a count
# mismatch is expected there and never gates a refusal).
_STRICT_COUNT_SPEC_KINDS = (RequiresClause, EnsuresClause, InvariantClause)


def _struct_eq(a: object, b: object) -> bool:
    """Structural equality of two `lift_ast` nodes (or plain values),
    ignoring every node's own `line` field (the two trees being compared
    here come from two DIFFERENT texts -- rprint's and the source's own
    -- so their line numbers are never expected to agree even when their
    shape does) and every node's own `attrs` field (`Quantifier.attrs`'s
    own docstring: "recorded and dropped" -- an SMT trigger hint dafny's
    RESOLVER inserts on `--rprint`, e.g. `{:trigger a[k]}`, that the
    author's own source text never carries and no later stage ever reads
    for meaning; measured on `dafny-synthesis_task_id_644`'s Reverse,
    whose `ensures`/`invariant` quantifiers are otherwise IDENTICAL
    between rprint and source -- comparing `attrs` would report a false
    disagreement on a real agreement), and a `Param.type` of `None` on
    either side (`Param`'s own docstring: "`None` exactly where the
    source left it out" -- a quantifier binder the author wrote
    untyped, `forall k :: ...`, resolves to an explicit `k: int` on
    rprint's own print; also measured on task_644's Reverse, the SAME
    method: comparing `type` there too would report a second false
    disagreement on the very same real agreement). Recurses through
    dataclasses, tuples and lists; anything else compares with plain
    `==` (an `int`/`str`/`Star`/`None` leaf, or a fully-specified `Type`
    node -- e.g. a `Cast`'s or `TypeTest`'s own mandatory `type` field,
    never `Optional` the way `Param.type` is, so a genuine source/rprint
    disagreement there, never yet measured, is NOT given the same
    inference-shaped pass)."""
    if type(a) is not type(b):
        return False
    if dataclasses.is_dataclass(a):
        for f in dataclasses.fields(a):
            if f.name == "line" or f.name == "attrs":
                continue
            if isinstance(a, Param) and f.name == "type" and (a.type is None or b.type is None):
                continue
            if not _struct_eq(getattr(a, f.name), getattr(b, f.name)):
                return False
        return True
    if isinstance(a, (tuple, list)):
        if len(a) != len(b):
            return False
        return all(_struct_eq(x, y) for x, y in zip(a, b))
    return a == b


def _matching_brace(tokens: list, start: int) -> int:
    """`tokens[start].text == "{"`. Returns the index of the matching
    `"}"`, by plain depth counting -- every `{`/`}` in well-formed Dafny
    text (a block, a set/map display, an attribute, a lambda's arrow body
    has none) is genuinely balanced, so no smarter scan is needed."""
    depth = 0
    for i in range(start, len(tokens)):
        t = tokens[i].text
        if t == "{":
            depth += 1
        elif t == "}":
            depth -= 1
            if depth == 0:
                return i
    return len(tokens) - 1


def _source_find_method_header(tokens: list, name: str) -> Optional[int]:
    """The index just past `name`'s own token, for the FIRST declaration
    (`method`/`function`/`predicate`/`lemma`) in `tokens` whose own name
    token is `name` -- i.e. right where the type-parameter list (if any)
    or the formal-parameter `"("` begins. `None` when no such declaration
    is found (a method-level `{:attr}` attribute between the base keyword
    and the name, which this scan does not skip over, is a KNOWN
    narrowing: none of the 164 dafny-synthesis files measured for this
    row use one, named here rather than silently guessed past)."""
    for i, tok in enumerate(tokens):
        if (tok.kind == "id" and tok.text in _METHOD_LIKE_BASE_WORDS
                and i + 1 < len(tokens) and tokens[i + 1].kind == "id"
                and tokens[i + 1].text == name):
            return i + 2
    return None


def _source_skip_angle_generic(parser: "_Parser") -> None:
    """Skip a `"<" ... ">"` type-parameter list at `parser.pos`, if one is
    there; a no-op otherwise. Depth-counted (not content-parsed) since
    this function's only job is to land `parser.pos` right after it;
    `">>"` (the bitvector shift lexeme, section 18.2) closes two levels
    at once, exactly as `_Parser._expect_gt` already treats it."""
    if not parser.at("<"):
        return
    parser.advance()
    depth = 1
    while depth > 0 and not parser.at_eof():
        t = parser.cur.text
        if t == "<":
            depth += 1
            parser.advance()
        elif t == ">>":
            depth -= 2
            parser.advance()
        elif t == ">":
            depth -= 1
            parser.advance()
        else:
            parser.advance()


def _source_skip_parens(parser: "_Parser") -> None:
    """Skip one balanced `"(" ... ")"` at `parser.pos` (a formal- or
    `returns`-parameter list) without parsing its contents -- the
    parameter TYPES are not this row's concern (only clause EXPRESSIONS
    are), and the rprint-derived method's own `params`/`returns` are
    already trusted (LIFTER-DESIGN.md never named the printer defect this
    row fixes as touching a type)."""
    parser.expect("(")
    depth = 1
    while depth > 0:
        if parser.at_eof():
            raise LiftParseError("<eof>", parser.cur.line,
                                  "unterminated parameter list in source text")
        t = parser.cur.text
        if t == "(":
            depth += 1
        elif t == ")":
            depth -= 1
        parser.advance()


def _collect_loop_nodes(body: Optional[tuple]) -> list:
    """Pre-order `WhileStmt`/`ForStmt` nodes from a method body, in the
    SAME left-to-right, depth-first order `lift_check._walk_source_loops`
    already walks (recursing into `IfStmt`/`BlockStmt`/`LabelStmt` only,
    never a `ForallStmt`/`AssertByStmt`'s own ghost-only body -- that
    module's own comment, "ghost-only, hints... never walked for loops
    that would need a real-body lemma", applies here for the same
    reason: this function's own caller aligns this list, index for
    index, against a LEXICAL scan of `while`/`for` tokens in the raw
    source text, and the two must enumerate the same loops in the same
    order or not be trusted to align at all -- see
    `check_against_source`'s own count-mismatch fallback)."""
    out: list = []

    def walk(stmts) -> None:
        for s in stmts:
            if isinstance(s, WhileStmt):
                out.append(s)
                walk(s.body)
            elif isinstance(s, ForStmt):
                out.append(s)
                walk(s.body)
            elif isinstance(s, IfStmt):
                walk(s.then)
                if isinstance(s.else_, tuple):
                    walk(s.else_)
                elif isinstance(s.else_, IfStmt):
                    walk((s.else_,))
            elif isinstance(s, BlockStmt):
                walk(s.body)
            elif isinstance(s, LabelStmt):
                walk((s.stmt,))
            # Any other statement kind (including one this row's own
            # simplified walk does not name) is left un-recursed-into,
            # which can only ever UNDER-count loops, never over-count or
            # misorder them -- an under-count is caught by the caller's
            # own length check and degrades to "skip, log a warning",
            # never a silent misalignment.

    walk(body or ())
    return out


def _expr_repr(node: object) -> str:
    """A complete, unambiguous quote of a `lift_ast` node for a sidecar
    warning line -- the dataclass's own `repr`, not a re-print through
    either printer this row exists to stop trusting uncritically."""
    return repr(node)


def _align_and_correct(rprint_specs: tuple, raw_specs: list, label: str,
                        warnings: list) -> tuple[tuple, Optional[Refusal]]:
    """Compare `rprint_specs` (already parsed from rprint's text) against
    `raw_specs` (freshly parsed from the source's own text), kind by
    kind (a source's clauses are matched to rprint's own same-kind
    clauses positionally, in the order both texts spell them out --
    rprint has never been measured to reorder clauses WITHIN one kind,
    only to occasionally add an inferred `decreases`, see the
    module-level docstring). Returns a new specs tuple (same length and
    order as `rprint_specs`, individual entries replaced by the source's
    own tree wherever the two disagree) and `None`, or `(rprint_specs,
    Refusal(reason="source-unparseable", ...))` when a strict-count kind
    (`_STRICT_COUNT_SPEC_KINDS`) cannot be matched 1:1."""
    rp_by_kind: dict = {}
    for i, s in enumerate(rprint_specs):
        rp_by_kind.setdefault(type(s), []).append(i)
    raw_by_kind: dict = {}
    for s in raw_specs:
        raw_by_kind.setdefault(type(s), []).append(s)

    new_specs = list(rprint_specs)
    for kind, idxs in rp_by_kind.items():
        raws = raw_by_kind.get(kind, [])
        name = _SPEC_KIND_NAME.get(kind, kind.__name__)
        strict = kind in _STRICT_COUNT_SPEC_KINDS
        if strict and len(idxs) != len(raws):
            first_line = rprint_specs[idxs[0]].line if idxs else 0
            return tuple(new_specs), Refusal(
                reason="source-unparseable",
                token=(f"{label}: {len(idxs)} rprint {name} clause(s) but "
                       f"{len(raws)} parsed from the source text"),
                line=first_line,
                stage="resolve",
            )
        n = len(idxs) if strict else min(len(idxs), len(raws))
        for k in range(n):
            rp_i = idxs[k]
            rp_node = rprint_specs[rp_i]
            raw_node = raws[k]
            if not _struct_eq(rp_node, raw_node):
                warnings.append(
                    f"rprint-source-disagreement: {label} {name}#{k}: "
                    f"rprint's own print parses to a DIFFERENT tree than "
                    f"the source's own text; corrected to the source's "
                    f"tree (rprint={_expr_repr(rp_node)}, "
                    f"source={_expr_repr(raw_node)})")
                new_specs[rp_i] = raw_node
    return tuple(new_specs), None


def _drop_clause_semicolons(tokens: list) -> list:
    """Every `;` token of the source text except those that close a let
    expression. A let's `;` is the first one after its `var` at the same
    bracket depth (its right-hand sides are expressions, and an expression
    holds no bare `;` of its own), so each `var` opens a pending let at the
    current depth and the next `;` at that depth closes it and is kept; a
    bracket that closes below a pending let's depth ends it. A statement
    `var` in the method body keeps its `;` too, harmlessly: no statement is
    parsed from this text, only clauses and loop headers."""
    out = []
    pending: list[int] = []
    depth = 0
    for tok in tokens:
        text = tok.text
        if text in ("(", "[", "{"):
            depth += 1
        elif text in (")", "]", "}"):
            depth -= 1
            while pending and pending[-1] > depth:
                pending.pop()
        elif text == "var":
            pending.append(depth)
        elif text == ";":
            if pending and pending[-1] == depth:
                pending.pop()
                out.append(tok)
            continue
        out.append(tok)
    return out


def check_against_source(dfy_path: Path, method: MethodDecl) -> tuple[list[str], Optional[Refusal]]:
    """Correct `method` (a `lift_parse.parse(rprint_text)`-derived
    `MethodDecl`, mutated IN PLACE, its body's `WhileStmt`/`ForStmt` loop
    nodes included) against `dfy_path`'s own bytes -- see this section's
    module-level docstring for the measured defect this exists to catch.
    Call this AFTER `lift_parse.gradable_methods` and BEFORE
    `lift_classify.classify`/`lift_rewrite.rewrite`/`lift_check.check`,
    so every later stage sees the corrected tree, never rprint's.

    Returns `(warnings, refusal)`: `warnings` are `rprint-source-
    disagreement:` lines (`LiftRecord.warnings`'s own free-text log,
    section 8 -- this row does not add a new sidecar field, per the
    task's own file-ownership limits: `lift_ast.py` is not this row's
    file to change) for every clause actually corrected, and a loop-level
    `... loop invariant/decreases clauses were NOT cross-checked ...`
    line wherever the best-effort loop alignment below could not be
    trusted. `refusal` is `None` on success (`method` already corrected);
    otherwise a `Refusal(reason="source-unparseable", ...)` and `method`
    is left PARTIALLY corrected (whatever kind matched before the
    mismatching one) -- the caller discards it either way once a refusal
    is returned, so this is safe, never observed."""
    try:
        text = Path(dfy_path).read_text(encoding="utf-8")
    except OSError as e:
        return [], Refusal(reason="source-unparseable", token=str(e), line=0, stage="resolve")
    try:
        line_starts = _compute_line_starts(text)
        tokens = _lex(text, 0, line_starts)
    except LiftParseError as e:
        return [], Refusal(reason="source-unparseable", token=e.token, line=e.line, stage="resolve")

    # Dafny's own grammar allows (and rprint never prints) an optional
    # bare `;` after a `requires`/`ensures`/`modifies`/`invariant`/
    # `decreases` clause (measured: dafny-synthesis_task_id_644's own
    # `modifies a;`) -- `_parse_mspec_list`/`_parse_loopspec_list` (built
    # to read rprint's text, which never has one) stop their clause loop
    # the instant the next token is not a clause keyword, so an
    # un-skipped `;` silently truncated the clause list to whatever came
    # before it (measured: task_644's own `ensures` on the very next
    # line was never reached). Outside a let expression a bare `;` never
    # appears in the span this module tokenises (generics, formal/return
    # parameter lists, clause expressions, loop headers), so those are
    # dropped before any of this section's own parsing runs; the `;` that
    # closes a let (`ensures var m := mean(s); r == m`, grammar 17.2.7.39,
    # dafny.org/latest/DafnyRef/DafnyRef#sec-let-expression) is part of
    # the clause and is kept (2026-09-26, `_drop_clause_semicolons`).
    tokens = _drop_clause_semicolons(tokens)

    idx = _source_find_method_header(tokens, method.name)
    if idx is None:
        return [], Refusal(
            reason="source-unparseable",
            token=f"method {method.name!r} not found in the source text",
            line=method.line, stage="resolve")

    parser = _Parser(tokens, text)
    parser.pos = idx
    try:
        _source_skip_angle_generic(parser)
        _source_skip_parens(parser)
        if parser.at("returns"):
            parser.advance()
            _source_skip_parens(parser)
        raw_mspecs = parser._parse_mspec_list()
    except LiftParseError as e:
        return [], Refusal(reason="source-unparseable", token=e.token, line=e.line, stage="resolve")

    warnings: list[str] = []
    new_specs, refusal = _align_and_correct(method.specs, raw_mspecs, method.name, warnings)
    if refusal is not None:
        return warnings, refusal
    method.specs = new_specs

    # Loop-level invariant/decreases: best-effort, per this section's own
    # module docstring. Only attempted when a plain LEXICAL count of
    # "while"/"for" tokens in the method's own raw-text body agrees with
    # `_collect_loop_nodes`'s structural count over the rprint-parsed
    # body; on a mismatch this skips loop correction entirely (a logged
    # warning, never a refusal -- a loop invariant a printer defect could
    # also corrupt is a real, if so-far unmeasured, risk this method
    # narrows rather than closes, named honestly instead of guessed at).
    try:
        loop_nodes = _collect_loop_nodes(method.body)
        body_start = parser.pos
        body_end = _matching_brace(tokens, body_start) if parser.at("{") else body_start
        raw_loop_positions = [i for i in range(body_start, body_end)
                               if tokens[i].kind == "id" and tokens[i].text in ("while", "for")]
        if len(raw_loop_positions) != len(loop_nodes):
            if loop_nodes:
                warnings.append(
                    f"rprint-source-disagreement: {method.name}: "
                    f"{len(loop_nodes)} loop(s) in the parsed body vs "
                    f"{len(raw_loop_positions)} 'while'/'for' token(s) found "
                    f"lexically in the source text; loop invariant/decreases "
                    f"clauses were NOT cross-checked against the source for "
                    f"this method (skipped, not corrected)")
        else:
            for node, tok_i in zip(loop_nodes, raw_loop_positions):
                parser.pos = tok_i + 1
                if isinstance(node, WhileStmt):
                    if parser.at("*"):
                        parser.advance()
                    else:
                        parser.parse_expr()
                else:  # ForStmt: `"for" Id [":" Type] ":=" Expr ("to" | "downto") Expr`
                    parser.expect_ident()
                    if parser.at(":"):
                        parser.advance()
                        parser.parse_type()
                    parser.expect(":=")
                    parser.parse_expr()
                    if parser.at("to") or parser.at("downto"):
                        parser.advance()
                    else:
                        raise LiftParseError(
                            parser.cur.text or "<eof>", parser.cur.line,
                            "expected 'to'/'downto' in a for-loop header (source text)")
                    parser.parse_expr()
                raw_loopspecs = parser._parse_loopspec_list()
                new_loop_specs, loop_refusal = _align_and_correct(
                    node.specs, raw_loopspecs, f"{method.name}@line{node.line}", warnings)
                if loop_refusal is not None:
                    # A loop invariant is as load-bearing as the method's
                    # own ensures (section 9's L_inv lemmas): this
                    # refuses too, exactly like the method-level case
                    # above, rather than silently leaving it uncorrected.
                    return warnings, loop_refusal
                node.specs = new_loop_specs
    except LiftParseError as e:
        warnings.append(
            f"rprint-source-disagreement: {method.name}: loop clauses could "
            f"not be located in the source text ({e.token!r} at line "
            f"{e.line}); loop invariant/decreases clauses were NOT "
            f"cross-checked against the source for this method")

    return warnings, None
