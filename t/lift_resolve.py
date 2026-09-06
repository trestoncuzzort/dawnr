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

import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from lift_ast import Refusal
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
    section 5's construct vocabulary (`array`, `div-mod`, `assume`, ...)
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
