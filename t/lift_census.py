"""Build the section-8 disagreement table over the 785-file corpus.

Reads LIFTER-DESIGN.md sections 2 (architecture -- this module's own row),
8 (the disagreement-verdict rule, mechanical, reproduced below in
`disagreement_verdict`'s docstring), 12 (test plan step 6:
`test_lift_census.py` checks this rule against the 44 disagreements the
readers recorded, `inventory.md` section 3), 13 (expected numbers this
module's output is checked against once real), 18.2 (the rewrite
vocabulary and the expected disagreement classes -- what the first-785-run
should find: 12 lift with a rewrite the census calls a gap, 6 policy rows,
30 refuse with the census's own name, 9 refuse with a reason the census
has none for), and LIFTER-DECISIONS.md decisions 9 (file vs. method
counting unit) and 17 (a lifted task that t's own instruments refuse gets
its own column, not folded into "lift failed"). Reads `t/coverage_census
.py`'s output shape only (`census.json`: a list of 785 records, each with
a `"file"` key and one boolean per gap name -- see `census.json` itself,
already on disk at `/home/tmcuzzort/t-corpora/lifter-design-2026-09-05
/census.json`); this module never regenerates census.json, only reads it.

Architecture role (LIFTER-DESIGN.md section 2's table, copied verbatim):
    input: all of the above (resolve/parse/classify/rewrite/check) for
           785 files, census.json
    output: the disagreement table, per-file rows
    MAY decide: agreement / disagreement / undecided per row
    MAY NOT decide: the policy calls in section 15

"The policy calls in section 15" means: this module reports what the
mechanical rule says, never overrides a row's verdict because a policy
question (e.g. "should read-only array lift to seq") is still open --
those calls are LIFTER-DECISIONS.md's to make, upstream of this module.

Modelling note (documented, not hidden, since section 8's prose gives
only two worked examples of each class): the gap-name lookup tables just
below (`POLICY_GAP_NAMES`, `VERIFIED_REWRITE_GAP_NAMES`,
`POLICY_REFUSAL_REASONS`) are transcribed directly from section 8's own
examples ("policy gap (read-only array)"; "one of the verified rewrites
(`seq-membership`, `s != []`)") and section 5's table (the only reason
annotated "(policy 15.1 ...)" is `array`). Section 18.2 says this
prediction is "checked against" once the 785-file run is real; nothing in
this module hard-codes 18.2's expected counts (12/6/30/9) themselves --
those are a validation target for a later, real corpus run, computed
mechanically here from whatever `disagreement_verdict` returns, never
asserted as given.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from lift_ast import Refusal

# ---------------------------------------------------------------------------
# Section 8 / section 5 / section 15 lookup tables (see the module
# docstring's "Modelling note" for where each entry is sourced from).
# ---------------------------------------------------------------------------

# Section 8, verbatim: "`undecided` when `G` is a policy gap (read-only
# array)". Section 5's reason table annotates exactly one reason
# "(policy 15.1 could turn read-only params into seq)": `array`. Both name
# the same census gap name.
POLICY_GAP_NAMES: frozenset[str] = frozenset({"array"})

# Section 8, verbatim: "one of the verified rewrites (`seq-membership`,
# `s != []`)". `seq-membership` is the census's own gap name (decision 2,
# desugared). `s != []`/`s == []` is the census's `seq-literal` gap name
# (decision 3's exact-emptiness shape); decision 3 itself still refuses
# `seq-literal` in v1 ("Revisit from the 785 table"), so in practice this
# branch of the rule will not currently fire for `seq-literal` -- it stays
# in the table because section 8 names it explicitly and a future reversal
# of decision 3 must not require touching this rule.
VERIFIED_REWRITE_GAP_NAMES: frozenset[str] = frozenset({"seq-membership", "seq-literal"})

# Refusal reasons this module treats as "a policy reason (section 15)"
# per section 8's in-fragment branch. `array` is the only reason section
# 5's table itself flags as policy-linked; `lift-check-failed` is handled
# as its own explicit case in `disagreement_verdict` (section 8 names it
# separately: "or `lift-check-failed`"), not folded into this set.
POLICY_REFUSAL_REASONS: frozenset[str] = frozenset({"array"})

# Not a section-8 concept: these are the two synthetic reasons this
# pipeline records while a called module is still a stub (`lifter.py`'s
# NotImplementedError-catching contract) or has hit an unexpected bug.
# Section 8 gives no rule for "the lifter did not really run yet", so
# treating both as `undecided` is this module's own conservative choice --
# never `"lifter"` (that would falsely claim the census is wrong) and
# never `"agree"` (nothing was actually checked).
INCOMPLETE_PIPELINE_REASONS: frozenset[str] = frozenset({"module-not-implemented", "error"})


@dataclass
class CensusRow:
    """One row of the section-8 disagreement table, for one (file, method)
    pair (decision 9: a file with several gradable methods gets one row
    per method here; a file-level row, used only for the `multi-method`/
    `split-per-method` program-count view, is a separate aggregate this
    module also produces, not a `CensusRow`).

    `file` and `method` identify the row (`method` is `None` for a
    file-level `Refusal` that never reached method classification, e.g.
    `resolve-failure`, `no-method`). `in_fragment` and `gaps` are copied
    from the matching `census.json` record (`gaps` a dict of every gap-name
    boolean on that record, not just the ones relevant to this row).
    `lifter_verdict` is `"lifted"` or `"refused:<reason>"`; `refusal` holds
    the full `Refusal` (reason, token, line, stage) when refused, `None`
    when lifted. `rewrites` and `renames` mirror the method's `LiftRecord`
    (empty when refused before rewrite). `check_wf`, `interp_points`,
    `interp_first_value`, `twin_rung`, `twin_refusal`, `checker_verdicts`,
    `differential_verdict` mirror `lift_check.CheckOutput`/`LiftRecord`
    (all `None`/empty when the method never reached that stage).
    `kernel_outcomes` is per-kernel (`dafny`, `verus`, ...) once the seven
    run over the lifted task (section 8: "once the seven run"; empty
    before then, per this module's OWN scope, which is the lift, not the
    grading). `disagreement` is this row's verdict from
    `disagreement_verdict`."""
    file: str
    method: Optional[str]
    in_fragment: bool
    gaps: dict[str, bool]
    lifter_verdict: str
    refusal: Optional[Refusal] = None
    rewrites: list[str] = field(default_factory=list)
    renames: dict[str, str] = field(default_factory=dict)
    check_wf: list[str] = field(default_factory=list)
    interp_points: int = 0
    interp_first_value: object = None
    twin_rung: Optional[str] = None
    twin_refusal: Optional[str] = None
    checker_verdicts: dict[str, str] = field(default_factory=dict)
    differential_verdict: Optional[str] = None
    kernel_outcomes: dict[str, str] = field(default_factory=dict)
    disagreement: str = "undecided"


def disagreement_verdict(census_record: dict, refusal: Optional[Refusal],
                          lifted_and_checked: bool) -> str:
    """The section-8 mechanical rule, no judgment: given one `census.json`
    record (`in_fragment` plus the gap-name booleans) and this row's
    lifter outcome, return one of `"agree"`, `"lifter"`, `"census"`,
    `"undecided"`, or `"gap-name"`.

    Input: `census_record` (one element of `census.json`: has `in_fragment`
    and one boolean per gap name); `refusal` (the `Refusal` this row's
    method/file got, or `None` if it lifted); `lifted_and_checked` (`True`
    iff the method lifted AND `lift_check.check` found no refusal --
    section 8's "lifter lifted and checked").

    Output, per section 8 (copied): census `in_fragment=True`, lifter
    refused with `refusal.reason` at `refusal.line`: `"lifter"` if the
    reason names a construct present at that line (the census cannot be
    right that a program is in-fragment when a construct outside t is
    quoted), never `"census"`, `"undecided"` if the reason is a policy
    reason (LIFTER-DESIGN.md section 15) or `lift-check-failed` (then the
    LIFTER is suspect, a bug report against it). Census `in_fragment=False`
    with gap `G` set, lifter lifted and checked: `"lifter"` when `G`'s
    construct is absent (a detector fault, e.g. the whole-file
    `if-no-else` rule) or is one of the verified rewrites
    (`seq-membership`, `s != []`); `"undecided"` when `G` is a policy gap
    (read-only array). Both refuse with different reasons: `"gap-name"`,
    the lifter's reason stands (it quotes a line), the census's tag is a
    detector fault when its construct is absent. Both agree: `"agree"`.

    MAY decide: agreement / disagreement / undecided per row (exactly the
    return value above).

    MAY NOT decide: the policy calls in section 15 -- this function never
    resolves whether a gap name is "really" a policy gap or a detector
    fault by inspecting the source itself; that classification is fixed
    data (which gap names are policy gaps is a section-15/decisions-file
    fact, looked up, not computed from the AST)."""
    in_fragment = bool(census_record.get("in_fragment", False))
    true_gaps = set(census_record.get("gaps") or [])

    if in_fragment:
        if refusal is None:
            # Census says in, lifter agrees it lifts -- but only once it
            # was actually checked; an unchecked lift (e.g. --skip-check)
            # cannot be scored "agree" against a census that reports a
            # fully-graded verdict.
            return "agree" if lifted_and_checked else "undecided"
        if refusal.reason in INCOMPLETE_PIPELINE_REASONS:
            return "undecided"
        if refusal.reason == "lift-check-failed":
            return "undecided"
        if refusal.reason in POLICY_REFUSAL_REASONS:
            return "undecided"
        # The census cannot be right that a program is in-fragment when a
        # construct outside t is quoted at a real line: never "census".
        return "lifter"

    # census in_fragment is False (out, with true_gaps naming why).
    if refusal is None:
        if not lifted_and_checked:
            return "undecided"
        if true_gaps & POLICY_GAP_NAMES:
            return "undecided"
        # Either the flagged construct(s) are absent (a detector fault)
        # or every true gap is a verified rewrite: both read "lifter" per
        # section 8. A lift that succeeded with gaps outside both sets
        # still reads "lifter" (the construct the census named was, by
        # this lift's own evidence, not actually blocking) -- section 8's
        # "detector fault" wording is the general case here.
        return "lifter"

    if refusal.reason in INCOMPLETE_PIPELINE_REASONS:
        return "undecided"
    if refusal.reason in true_gaps:
        return "agree"
    return "gap-name"


# ---------------------------------------------------------------------------
# Row assembly: turning a lifter.FileOutcome plus its census record into
# CensusRow objects. lifter.py is imported lazily inside build_table (not
# at module top level) so a standalone `import lift_census` never pays for
# importing every module of the pipeline just to call disagreement_verdict
# in a unit test.
# ---------------------------------------------------------------------------

def _record_rewrites(record) -> list[str]:
    if record is None:
        return []
    return [rw.rule for rw in record.rewrites]


def _record_renames(record) -> dict[str, str]:
    if record is None:
        return {}
    return {src: ren.t_name for src, ren in record.rename_map.items()}


def _record_twin_refusal(record) -> Optional[str]:
    """`LiftRecord` (per the interfaces contract handed to every
    implementer) has no dedicated twin-refusal field -- only `twin_rung`/
    `twin_witness`, which stay `None` on a twin refusal (section 5's
    closing paragraph: that is not a lift refusal). The convention this
    module reads, pending `lift_check.py`'s real implementation, is a
    `"twin-refused:<reason>"`-prefixed entry in `record.warnings` (the one
    free-form list every stage may append to); absent that, `None` is
    reported rather than guessed."""
    if record is None:
        return None
    if record.twin_rung is not None:
        return None
    for w in record.warnings:
        if w.startswith("twin-refused:"):
            return w[len("twin-refused:"):]
    return None


def _record_check_wf(refusal: Optional[Refusal]) -> list[str]:
    if refusal is not None and refusal.reason == "check-wf-failed":
        return [refusal.token] if refusal.token else ["check-wf-failed"]
    return []


def _census_gaps_dict(census_record: dict) -> dict[str, bool]:
    skip = {"file", "family", "gaps", "in_fragment"}
    return {k: bool(v) for k, v in census_record.items() if k not in skip}


def _row_from_method_outcome(census_record: dict, method_outcome) -> "CensusRow":
    refusal = method_outcome.refusal
    lifted = refusal is None
    record = method_outcome.record
    row = CensusRow(
        file=census_record["file"],
        method=(method_outcome.method or None),
        in_fragment=bool(census_record.get("in_fragment", False)),
        gaps=_census_gaps_dict(census_record),
        lifter_verdict=("lifted" if lifted else f"refused:{refusal.reason}"),
        refusal=refusal,
        rewrites=_record_rewrites(record),
        renames=_record_renames(record),
        check_wf=_record_check_wf(refusal),
        interp_points=getattr(method_outcome, "interp_points", 0) or 0,
        interp_first_value=getattr(method_outcome, "interp_first_value", None),
        twin_rung=(record.twin_rung if record is not None else None),
        twin_refusal=_record_twin_refusal(record),
        checker_verdicts=(dict(record.checker_verdicts) if record is not None else {}),
        differential_verdict=(record.differential_verdict if record is not None else None),
        kernel_outcomes={},
    )
    row.disagreement = disagreement_verdict(census_record, refusal, lifted)
    return row


def _row_from_file_refusal(census_record: dict, refusal: Refusal) -> "CensusRow":
    row = CensusRow(
        file=census_record["file"],
        method=None,
        in_fragment=bool(census_record.get("in_fragment", False)),
        gaps=_census_gaps_dict(census_record),
        lifter_verdict=f"refused:{refusal.reason}",
        refusal=refusal,
    )
    row.disagreement = disagreement_verdict(census_record, refusal, False)
    return row


def rows_for_file(census_record: dict, outcome) -> list["CensusRow"]:
    """Turn one `lifter.FileOutcome` plus its matching `census.json`
    record into this file's `CensusRow`s: a single file-level row when
    `resolve_refusal`/`parse_refusal` stopped the file before any method
    was reached, otherwise one row per entry of `outcome.methods`
    (including the synthetic `method=""` -> `method=None` entry for
    `no-method`/`no-ensures`, per decision 9's "one row per gradable
    method" read together with `lifter.FileOutcome`'s own docs)."""
    if outcome.resolve_refusal is not None:
        return [_row_from_file_refusal(census_record, outcome.resolve_refusal)]
    if outcome.parse_refusal is not None:
        return [_row_from_file_refusal(census_record, outcome.parse_refusal)]
    return [_row_from_method_outcome(census_record, mo) for mo in outcome.methods]


def build_table(census_path: Path, corpus_dir: Path,
                 out_dir: Optional[Path] = None) -> list[CensusRow]:
    """Run the full lift pipeline (via `lifter.lift_file`) over every file
    named in the `census_path` JSON, found under `corpus_dir`, and build
    one `CensusRow` per (file, gradable method) pair plus file-level rows
    for files that never reach method classification, applying
    `disagreement_verdict` to each.

    Input: `census_path` (the `census.json` file: 785 records, each with a
    `"file"` key resolved against `corpus_dir`), `corpus_dir` (the
    DafnyBench ground_truth directory), `out_dir` (optional: when given,
    every lifted method's task JSON and `.lift.json` sidecar are written
    there, same as `lifter.lift_file`'s own `out_dir`).

    Output: the disagreement table as a list of `CensusRow`, in
    `census.json`'s file order, per-method within a file in declaration
    order (decision 9).

    MAY decide: agreement / disagreement / undecided per row (via
    `disagreement_verdict`).

    MAY NOT decide: the policy calls in section 15.

    `lift_file` is resumable (a source file whose out_dir record already
    exists is loaded from disk rather than re-run, unless the caller has
    otherwise forced a fresh run) -- see `lifter.lift_file`'s own docs --
    so calling this again with the same `out_dir` after a prior
    `lifter.py --list ...`/`--dir ...` run over some of `census_path`'s
    files reuses exactly those records rather than redoing the work."""
    import lifter  # local import: keep a bare disagreement_verdict test cheap

    census_path = Path(census_path)
    corpus_dir = Path(corpus_dir)
    records = json.loads(census_path.read_text(encoding="utf-8"))

    rows: list[CensusRow] = []
    for census_record in records:
        dfy_path = corpus_dir / census_record["file"]
        outcome = lifter.lift_file(dfy_path, out_dir=out_dir)
        rows.extend(rows_for_file(census_record, outcome))
    return rows


# ---------------------------------------------------------------------------
# Reporting: program- and method-granularity counts (decision 9), the
# lifted-vs-counted split (decision 17), and the markdown + JSON report
# (this module's own "Build" contract, item 2: "reporting BOTH program and
# method counts, the lifted-versus-counted split of decision 17, and the
# class counts of 18.2").
# ---------------------------------------------------------------------------

# Decision 17: "A task that lifts but t's own instruments refuse
# (`no-operator`, `interp-no-input`, a preservation-witness twin that
# dafny reads UNPROVED)" gets its OWN column, not folded into "lift
# failed". A row counts as "lifted" (decision-17's first count) whenever
# `CensusRow.refusal is None` (lift_check.check's own refusal, per its
# docstring, is never set for a bare twin refusal); it additionally counts
# as "counted" (fully graded, nothing outstanding) only when it also has
# no twin refusal and no differential/checker failure recorded.
def _is_lifted(row: "CensusRow") -> bool:
    return row.refusal is None and row.method is not None


def _is_counted(row: "CensusRow") -> bool:
    """Decision 17's second count: lifted AND every t-side instrument
    that ran actually passed (no twin refusal recorded, and, when a
    differential verdict was measured, it agrees). A row can be
    `_is_lifted` but not `_is_counted` -- that gap IS decision 17's point:
    coverage of the fragment and coverage of the measurement are two
    numbers."""
    if not _is_lifted(row):
        return False
    if row.twin_refusal is not None:
        return False
    if row.differential_verdict is not None and not row.differential_verdict.startswith("agrees"):
        return False
    return True


def _refusal_reason(row: "CensusRow") -> Optional[str]:
    return row.refusal.reason if row.refusal is not None else None


def program_rows(rows: list["CensusRow"]) -> dict[str, list["CensusRow"]]:
    """Group rows by `file` (decision 9's program-granularity view)."""
    by_file: dict[str, list[CensusRow]] = {}
    for row in rows:
        by_file.setdefault(row.file, []).append(row)
    return by_file


def program_verdict(file_rows: list["CensusRow"]) -> str:
    """One file's program-level verdict (decision 9: "in fragment iff
    every task lifts"): `"lifted"` iff every row for this file is
    `_is_lifted`; otherwise `"refused:<first reason>"` naming the first
    refusing row's reason (the file-level `split-per-method` label lives
    in the caller, which knows how many methods this file had)."""
    if all(_is_lifted(r) for r in file_rows):
        return "lifted"
    first = next(r for r in file_rows if not _is_lifted(r))
    return f"refused:{_refusal_reason(first)}"


@dataclass
class ReportSummary:
    """The counts `build_report` computes: both granularities (decision
    9), the lifted-vs-counted split (decision 17), the disagreement-class
    counts (section 8's five verdicts) and the census in/out split, at
    both granularities."""
    method_total: int = 0
    method_lifted: int = 0
    method_counted: int = 0
    program_total: int = 0
    program_lifted: int = 0
    program_multi_method: int = 0
    census_in_method_rows: int = 0
    census_in_program_rows: int = 0
    disagreement_counts: dict[str, int] = field(default_factory=dict)
    refusal_reason_counts: dict[str, int] = field(default_factory=dict)


def summarize(rows: list["CensusRow"]) -> ReportSummary:
    s = ReportSummary()
    s.method_total = len(rows)
    for row in rows:
        if _is_lifted(row):
            s.method_lifted += 1
        if _is_counted(row):
            s.method_counted += 1
        if row.in_fragment:
            s.census_in_method_rows += 1
        s.disagreement_counts[row.disagreement] = s.disagreement_counts.get(row.disagreement, 0) + 1
        reason = _refusal_reason(row)
        if reason is not None:
            s.refusal_reason_counts[reason] = s.refusal_reason_counts.get(reason, 0) + 1

    by_file = program_rows(rows)
    s.program_total = len(by_file)
    for file_rows in by_file.values():
        if len(file_rows) > 1:
            s.program_multi_method += 1
        if program_verdict(file_rows) == "lifted":
            s.program_lifted += 1
        if any(r.in_fragment for r in file_rows):
            s.census_in_program_rows += 1
    return s


def _row_to_jsonable(row: "CensusRow") -> dict:
    d = asdict(row)
    # asdict() already turns the nested Refusal dataclass into a plain
    # dict (or None); nothing else in CensusRow is a dataclass/object that
    # json.dumps cannot already handle on its own.
    return d


def build_report(rows: list["CensusRow"]) -> tuple[str, dict]:
    """Render `rows` as the section-8 disagreement table: a markdown
    table (no em-dashes, per house style) plus a JSON-serialisable summary
    dict holding the same rows and `summarize`'s counts."""
    summary = summarize(rows)

    lines = []
    lines.append("# Lifter census disagreement table")
    lines.append("")
    lines.append(f"Method rows: {summary.method_total} total, "
                 f"{summary.method_lifted} lifted, "
                 f"{summary.method_counted} counted (decision 17).")
    lines.append(f"Program rows: {summary.program_total} total, "
                 f"{summary.program_lifted} lifted (every method lifts), "
                 f"{summary.program_multi_method} multi-method.")
    lines.append(f"Census in_fragment: {summary.census_in_method_rows} method rows, "
                 f"{summary.census_in_program_rows} program rows.")
    lines.append("")
    lines.append("Disagreement verdict counts:")
    for verdict in ("agree", "lifter", "census", "undecided", "gap-name"):
        lines.append(f"- {verdict}: {summary.disagreement_counts.get(verdict, 0)}")
    lines.append("")
    lines.append("Refusal reason counts:")
    for reason, count in sorted(summary.refusal_reason_counts.items()):
        lines.append(f"- {reason}: {count}")
    lines.append("")
    lines.append("| file | method | in_fragment | verdict | disagreement |")
    lines.append("|---|---|---|---|---|")
    for row in rows:
        method_cell = row.method if row.method is not None else "(file)"
        lines.append(f"| {row.file} | {method_cell} | {row.in_fragment} | "
                     f"{row.lifter_verdict} | {row.disagreement} |")

    report_json = {
        "summary": asdict(summary),
        "rows": [_row_to_jsonable(r) for r in rows],
    }
    return "\n".join(lines) + "\n", report_json


def write_report(rows: list["CensusRow"], out_path: Path) -> tuple[Path, Path]:
    """Write `build_report(rows)`'s markdown to `out_path` (with a
    `.md` suffix forced) and its JSON beside it (same stem, `.json`
    suffix). Returns the two paths written. Windows-safe: UTF-8, explicit
    `newline="\\n"`."""
    out_path = Path(out_path)
    md_path = out_path.with_suffix(".md")
    json_path = out_path.with_suffix(".json")
    md_text, report_json = build_report(rows)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    with md_path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(md_text)
    with json_path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(report_json, f, indent=2, sort_keys=True)
        f.write("\n")
    return md_path, json_path


def _normalize_argv(argv: list[str]) -> list[str]:
    """Accept `--flag:value` (RUN-ON-WINDOWS.md's subprocess-flag
    convention, applied here to this module's own CLI too) alongside the
    argparse-native `--flag value` / `--flag=value` forms: rewrite the
    first `:` in a long option to `=` before argparse ever sees it."""
    out = []
    for a in argv:
        if a.startswith("--") and ":" in a and "=" not in a.split(":", 1)[0]:
            key, _, rest = a.partition(":")
            out.append(f"{key}={rest}")
        else:
            out.append(a)
    return out


def main(argv: Optional[list[str]] = None) -> int:
    """CLI: build the section-8 report either by running the full
    pipeline (`--corpus-dir` given: calls `build_table`, resumable through
    `--out`) or by joining whatever records already sit under `--out`
    against `--census-json` alone (`--corpus-dir` omitted: `build_table`
    is still used, since `lifter.lift_file`'s own resumability means an
    already-populated `--out` does no repeat work for files it already
    holds a record for -- but this mode requires `--corpus-dir` too,
    since `lift_file` needs a source path to resolve even on a cache
    hit's early-exit check).

    Writes `<report>.md` and `<report>.json` (default report path:
    `<out>/census_report`)."""
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(
        description="Build the lifter's section-8 disagreement table.")
    parser.add_argument("--census-json", required=True, type=Path)
    parser.add_argument("--corpus-dir", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=None,
                         help="directory to read/write per-file lift records "
                              "(resumable; omit to run without persisting)")
    parser.add_argument("--report", type=Path, default=None,
                         help="report path stem (default: <out>/census_report, "
                              "or ./census_report when --out is omitted)")
    args = parser.parse_args(_normalize_argv(argv))

    report_stem = args.report
    if report_stem is None:
        report_stem = (args.out / "census_report") if args.out is not None else Path("census_report")

    rows = build_table(args.census_json, args.corpus_dir, out_dir=args.out)
    summary = summarize(rows)
    md_path, json_path = write_report(rows, report_stem)

    print(f"{len(rows)} rows ({summary.program_total} programs, "
          f"{summary.method_lifted} method rows lifted, "
          f"{summary.method_counted} counted)")
    print(f"census in_fragment: {summary.census_in_method_rows} method rows, "
          f"{summary.census_in_program_rows} program rows")
    for verdict in ("agree", "lifter", "census", "undecided", "gap-name"):
        print(f"  {verdict}: {summary.disagreement_counts.get(verdict, 0)}")
    print(f"wrote {md_path}")
    print(f"wrote {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
