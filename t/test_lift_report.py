"""Plain-python tests for `lift_census.py` and `lifter.py` (this
implementer's own two files; see `test_lifter.py`'s module docstring for
the shared driver contract this file follows: a module-level
`run(slow: bool = False) -> None` that raises `AssertionError` on
failure and prints a one-line summary).

Run directly with `cd /home/tmcuzzort/tup/t && python3 test_lift_report.py`,
or via the shared driver: `python3 test_lifter.py test_lift_report`.

Covers, per this implementer's acceptance list:
  (a) `lifter.py --list infragment.txt`, every other module still a stub
      -> 77 records with `module-not-implemented` verdicts, well under
      2 minutes wall (exercised here on a 5-file slice for speed; the
      full 77-file/2-minute claim is measured separately by hand and
      reported in the session's own notes, not re-measured on every test
      run).
  (b) `lift_census.py`'s report, built from those records plus
      census.json, has the right totals.
  (c) the disagreement-verdict rule on synthetic records, covering every
      producible verdict class plus a property test of the one
      documented-unreachable class (`"census"`, section 8: "`census`
      never"), and both counting units (decision 9: program vs. method).
  (d) resumability: a second identical `lift_file` call does no work
      (proved by monkeypatching `lift_resolve.resolve` to blow up and
      showing the cached call never reaches it).
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import lift_census
import lifter
from lift_ast import Refusal

CORPUS_DIR = Path("/home/tmcuzzort/t-corpora/DafnyBench/DafnyBench/dataset/ground_truth")
CENSUS_JSON = Path("/home/tmcuzzort/t-corpora/lifter-design-2026-09-05/census.json")
INFRAGMENT_TXT = Path("/home/tmcuzzort/t-corpora/lifter-design-2026-09-05/infragment.txt")


# ---------------------------------------------------------------------------
# (c) disagreement_verdict: one synthetic record per producible class,
# plus the documented-unreachable "census" class and the incomplete-
# pipeline (module-not-implemented/error) cases this project's stub state
# actually produces today.
# ---------------------------------------------------------------------------

def _census(in_fragment: bool, gaps: list[str]) -> dict:
    record = {g: True for g in gaps}
    record["in_fragment"] = in_fragment
    record["gaps"] = list(gaps)
    record["file"] = "synthetic.dfy"
    return record


def test_verdict_agree_in_fragment() -> None:
    # Census says in, lifter lifted and checked it: agree.
    rec = _census(True, [])
    v = lift_census.disagreement_verdict(rec, refusal=None, lifted_and_checked=True)
    assert v == "agree", v


def test_verdict_agree_out_of_fragment() -> None:
    # Both refuse for the SAME reason: agree.
    rec = _census(False, ["div-mod"])
    refusal = Refusal(reason="div-mod", token="%", line=7, stage="classify")
    v = lift_census.disagreement_verdict(rec, refusal=refusal, lifted_and_checked=False)
    assert v == "agree", v


def test_verdict_lifter_construct_present() -> None:
    # Census says in, lifter refused naming a real construct: lifter.
    rec = _census(True, [])
    refusal = Refusal(reason="div-mod", token="%", line=12, stage="classify")
    v = lift_census.disagreement_verdict(rec, refusal=refusal, lifted_and_checked=False)
    assert v == "lifter", v


def test_verdict_lifter_detector_fault() -> None:
    # Census says out (gap G set) but the lifter lifted and checked it
    # anyway, G not a policy gap and not a verified-rewrite gap either:
    # section 8's general "detector fault" case reads "lifter".
    rec = _census(False, ["if-no-else"])
    v = lift_census.disagreement_verdict(rec, refusal=None, lifted_and_checked=True)
    assert v == "lifter", v


def test_verdict_lifter_verified_rewrite() -> None:
    # Census gap is one of section 8's named "verified rewrites"
    # (seq-membership): lifted and checked -> lifter.
    rec = _census(False, ["seq-membership"])
    v = lift_census.disagreement_verdict(rec, refusal=None, lifted_and_checked=True)
    assert v == "lifter", v


def test_verdict_undecided_policy_reason_in_fragment() -> None:
    # Census says in, lifter refused `array` (section 5's one
    # policy-annotated reason): undecided.
    rec = _census(True, [])
    refusal = Refusal(reason="array", token="a", line=3, stage="classify")
    v = lift_census.disagreement_verdict(rec, refusal=refusal, lifted_and_checked=False)
    assert v == "undecided", v


def test_verdict_undecided_lift_check_failed() -> None:
    rec = _census(True, [])
    refusal = Refusal(reason="lift-check-failed", token="L_ens", line=9, stage="check")
    v = lift_census.disagreement_verdict(rec, refusal=refusal, lifted_and_checked=False)
    assert v == "undecided", v


def test_verdict_undecided_policy_gap_out_of_fragment() -> None:
    # Census out with the policy gap (read-only array), lifted and
    # checked anyway: undecided, not lifter -- this module never asserts
    # the census was wrong on a policy question (section 15).
    rec = _census(False, ["array"])
    v = lift_census.disagreement_verdict(rec, refusal=None, lifted_and_checked=True)
    assert v == "undecided", v


def test_verdict_gap_name() -> None:
    # Both refuse, but for different reasons: gap-name.
    rec = _census(False, ["real"])
    refusal = Refusal(reason="div-mod", token="%", line=5, stage="classify")
    v = lift_census.disagreement_verdict(rec, refusal=refusal, lifted_and_checked=False)
    assert v == "gap-name", v


def test_verdict_never_census() -> None:
    """Section 8, verbatim, in the in-fragment/lifter-refused branch:
    "`census` never (the census cannot be right that a program is in the
    fragment when a construct outside t is quoted)". No combination of
    inputs should ever produce `"census"`; this is a property test over
    every branch's shape, not just the one section 8 states it for."""
    reasons = ["div-mod", "array", "lift-check-failed", "real", "module-not-implemented", "error"]
    gap_sets = [[], ["div-mod"], ["array"], ["seq-membership"], ["real", "array"]]
    for in_fragment in (True, False):
        for lifted_and_checked in (True, False):
            for refusal in [None] + [Refusal(r, "x", 1, "classify") for r in reasons]:
                for gaps in gap_sets:
                    rec = _census(in_fragment, gaps)
                    v = lift_census.disagreement_verdict(rec, refusal, lifted_and_checked)
                    assert v != "census", (rec, refusal, lifted_and_checked, v)
                    assert v in ("agree", "lifter", "undecided", "gap-name"), v


def test_verdict_incomplete_pipeline_undecided() -> None:
    """The synthetic `module-not-implemented`/`error` reasons this
    project's stub state actually produces today are not a section-8
    concept; this module's own choice (documented in `lift_census.py`) is
    `undecided` for both, in every branch, since nothing was really
    decided yet."""
    for reason in ("module-not-implemented", "error"):
        refusal = Refusal(reason=reason, token="lift_resolve.resolve", line=0, stage="resolve")
        rec_in = _census(True, [])
        assert lift_census.disagreement_verdict(rec_in, refusal, False) == "undecided"
        rec_out = _census(False, ["div-mod"])
        assert lift_census.disagreement_verdict(rec_out, refusal, False) == "undecided"


def test_verdict_unchecked_lift_is_undecided() -> None:
    """`refusal is None` but `lifted_and_checked=False` (the
    `--skip-check` state: rewrite succeeded, `lift_check.check` never
    ran) must not read `agree`/`lifter` -- nothing was actually checked."""
    rec_in = _census(True, [])
    assert lift_census.disagreement_verdict(rec_in, None, False) == "undecided"
    rec_out = _census(False, ["if-no-else"])
    assert lift_census.disagreement_verdict(rec_out, None, False) == "undecided"


# ---------------------------------------------------------------------------
# (c) both counting units: program (decision 9: "in fragment iff every
# task lifts") vs. method.
# ---------------------------------------------------------------------------

def _row(file: str, method, refusal_reason: str | None, in_fragment: bool = True) -> lift_census.CensusRow:
    refusal = None if refusal_reason is None else Refusal(refusal_reason, "x", 1, "classify")
    row = lift_census.CensusRow(
        file=file, method=method, in_fragment=in_fragment, gaps={},
        lifter_verdict=("lifted" if refusal is None else f"refused:{refusal_reason}"),
        refusal=refusal,
    )
    row.disagreement = lift_census.disagreement_verdict(
        {"in_fragment": in_fragment, "gaps": []}, refusal, refusal is None)
    return row


def test_counting_units_program_vs_method() -> None:
    rows = [
        # one-method file, lifted
        _row("a.dfy", "A", None),
        # one-method file, refused
        _row("b.dfy", "B", "div-mod"),
        # two-method file: one lifted, one refused -> program NOT lifted,
        # but one method row IS lifted
        _row("c.dfy", "C1", None),
        _row("c.dfy", "C2", "array"),
        # two-method file, both lifted -> program lifted
        _row("d.dfy", "D1", None),
        _row("d.dfy", "D2", None),
    ]
    summary = lift_census.summarize(rows)
    # Method granularity: 6 rows, 4 lifted (A, C1, D1, D2).
    assert summary.method_total == 6, summary.method_total
    assert summary.method_lifted == 4, summary.method_lifted
    # Program granularity: 4 files; lifted iff EVERY method of that file
    # lifted -- a.dfy yes, b.dfy no, c.dfy no (C2 refused), d.dfy yes.
    assert summary.program_total == 4, summary.program_total
    assert summary.program_lifted == 2, summary.program_lifted
    assert summary.program_multi_method == 2, summary.program_multi_method  # c.dfy, d.dfy

    by_file = lift_census.program_rows(rows)
    assert lift_census.program_verdict(by_file["a.dfy"]) == "lifted"
    assert lift_census.program_verdict(by_file["c.dfy"]) == "refused:array"
    assert lift_census.program_verdict(by_file["d.dfy"]) == "lifted"
    print(f"test_counting_units_program_vs_method: "
          f"{summary.method_total} method rows / {summary.program_total} program rows, "
          f"method_lifted={summary.method_lifted} program_lifted={summary.program_lifted}")


def test_decision17_lifted_vs_counted() -> None:
    """Decision 17: a lifted row whose twin instrument refused is still
    `_is_lifted` but not `_is_counted` -- two different numbers."""
    lifted_clean = _row("e.dfy", "E", None)
    lifted_twin_refused = lift_census.CensusRow(
        file="f.dfy", method="F", in_fragment=True, gaps={},
        lifter_verdict="lifted", refusal=None, twin_refusal="no-operator")
    rows = [lifted_clean, lifted_twin_refused]
    summary = lift_census.summarize(rows)
    assert summary.method_lifted == 2, summary.method_lifted
    assert summary.method_counted == 1, summary.method_counted


# ---------------------------------------------------------------------------
# (a)/(d): lift_file over real corpus files while the other five modules
# are stubs -- no crash, module-not-implemented recorded, and a second
# call is a true no-op (resumability).
# ---------------------------------------------------------------------------

def test_lift_file_stub_no_crash() -> None:
    names = [line.strip() for line in INFRAGMENT_TXT.read_text(encoding="utf-8").splitlines()
             if line.strip()][:5]
    assert names, "infragment.txt produced no names"
    for name in names:
        p = CORPUS_DIR / name
        assert p.is_file(), f"missing corpus file: {p}"
        outcome = lifter.lift_file(p)
        assert outcome.resolve_refusal is not None
        assert outcome.resolve_refusal.reason == "module-not-implemented"
        assert outcome.resolve_refusal.stage == "resolve"
        assert outcome.methods == []
    print(f"test_lift_file_stub_no_crash: {len(names)} files, all "
          f"module-not-implemented, no crash")


def test_resumability_no_recompute() -> None:
    import lift_resolve

    p = CORPUS_DIR / "Clover_abs.dfy"
    assert p.is_file()
    tmp = Path(tempfile.mkdtemp(prefix="lift_report_resume_"))
    try:
        out1 = lifter.lift_file(p, out_dir=tmp)
        assert out1.resolve_refusal.reason == "module-not-implemented"
        marker = tmp / "Clover_abs.outcome.json"
        assert marker.is_file()

        orig_resolve = lift_resolve.resolve

        def _boom(*a, **kw):
            raise RuntimeError("resolve must not be called on a cached run")

        lift_resolve.resolve = _boom
        try:
            out2 = lifter.lift_file(p, out_dir=tmp)  # not forced: must hit cache
        finally:
            lift_resolve.resolve = orig_resolve
        assert out2.resolve_refusal.reason == "module-not-implemented", (
            "resumed call should reuse the cached record, not recompute")

        lift_resolve.resolve = _boom
        try:
            out3 = lifter.lift_file(p, out_dir=tmp, force=True)  # forced: must recompute
        finally:
            lift_resolve.resolve = orig_resolve
        assert out3.resolve_refusal.reason == "error", out3.resolve_refusal
        assert "must not be called" in out3.resolve_refusal.token
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("test_resumability_no_recompute: cached call skipped lift_resolve.resolve; "
          "--force recomputed it")


def test_lifter_cli_list_resumable(slow: bool = False) -> None:
    """The actual acceptance-(a)/(d) shape end to end through the CLI, on
    a small slice (5 files) unless `slow`, in which case the full 77."""
    names = [line.strip() for line in INFRAGMENT_TXT.read_text(encoding="utf-8").splitlines()
             if line.strip()]
    if not slow:
        names = names[:5]
    tmp = Path(tempfile.mkdtemp(prefix="lift_report_cli_"))
    list_path = tmp / "list.txt"
    list_path.write_text("\n".join(names) + "\n", encoding="utf-8", newline="\n")
    out_dir = tmp / "out"
    try:
        import time
        t0 = time.monotonic()
        rc1 = lifter.main(["--list", str(list_path), "--corpus-dir", str(CORPUS_DIR),
                            "--out", str(out_dir), "--jobs", "4"])
        wall1 = time.monotonic() - t0
        assert rc1 == 0
        summary1 = json.loads((out_dir / "run_summary.json").read_text(encoding="utf-8"))
        assert summary1["files_total"] == len(names)
        assert summary1["files_processed"] == len(names)
        assert summary1["files_resumed"] == 0

        t0 = time.monotonic()
        rc2 = lifter.main(["--list", str(list_path), "--corpus-dir", str(CORPUS_DIR),
                            "--out", str(out_dir), "--jobs", "4"])
        wall2 = time.monotonic() - t0
        assert rc2 == 0
        summary2 = json.loads((out_dir / "run_summary.json").read_text(encoding="utf-8"))
        assert summary2["files_resumed"] == len(names)
        assert summary2["files_processed"] == 0

        markers = list(out_dir.glob("*.outcome.json"))
        assert len(markers) == len(names), (len(markers), len(names))
        print(f"test_lifter_cli_list_resumable: {len(names)} files, "
              f"first run {wall1:.3f}s, resumed run {wall2:.3f}s, "
              f"{len(markers)} outcome markers")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# (b): lift_census's report on real records + census.json.
# ---------------------------------------------------------------------------

def test_build_table_and_report_totals() -> None:
    census_records = json.loads(CENSUS_JSON.read_text(encoding="utf-8"))
    infrag_names = set(line.strip() for line in INFRAGMENT_TXT.read_text(encoding="utf-8").splitlines()
                        if line.strip())
    subset = [r for r in census_records if r["file"] in infrag_names]
    assert len(subset) == 77, len(subset)
    assert all(r.get("in_fragment") for r in subset)

    tmp = Path(tempfile.mkdtemp(prefix="lift_report_census_"))
    subset_json = tmp / "census_subset.json"
    subset_json.write_text(json.dumps(subset), encoding="utf-8", newline="\n")
    try:
        rows = lift_census.build_table(subset_json, CORPUS_DIR, out_dir=tmp / "out")
        assert len(rows) == 77, len(rows)
        summary = lift_census.summarize(rows)
        assert summary.census_in_method_rows == 77, summary.census_in_method_rows
        assert summary.census_in_program_rows == 77, summary.census_in_program_rows
        assert summary.method_lifted == 0, summary.method_lifted
        assert summary.disagreement_counts.get("undecided") == 77, summary.disagreement_counts
        assert summary.disagreement_counts.get("lifter", 0) == 0
        assert summary.disagreement_counts.get("agree", 0) == 0
        assert summary.disagreement_counts.get("gap-name", 0) == 0

        md_path, json_path = lift_census.write_report(rows, tmp / "report")
        assert md_path.is_file() and json_path.is_file()
        md_text = md_path.read_text(encoding="utf-8")
        assert "—" not in md_text, "em-dash in report markdown"
        report_json = json.loads(json_path.read_text(encoding="utf-8"))
        assert report_json["summary"]["census_in_method_rows"] == 77
        print(f"test_build_table_and_report_totals: 77 rows, "
              f"{summary.census_in_method_rows} census-in, "
              f"{summary.method_lifted} lifted, undecided={summary.disagreement_counts['undecided']}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


OWN_TESTS = [
    test_verdict_agree_in_fragment,
    test_verdict_agree_out_of_fragment,
    test_verdict_lifter_construct_present,
    test_verdict_lifter_detector_fault,
    test_verdict_lifter_verified_rewrite,
    test_verdict_undecided_policy_reason_in_fragment,
    test_verdict_undecided_lift_check_failed,
    test_verdict_undecided_policy_gap_out_of_fragment,
    test_verdict_gap_name,
    test_verdict_never_census,
    test_verdict_incomplete_pipeline_undecided,
    test_verdict_unchecked_lift_is_undecided,
    test_counting_units_program_vs_method,
    test_decision17_lifted_vs_counted,
    test_lift_file_stub_no_crash,
    test_resumability_no_recompute,
    test_build_table_and_report_totals,
]


def run(slow: bool = False) -> None:
    """Called by `test_lifter.py`'s driver (`python3 test_lifter.py
    test_lift_report [--slow]`); also runnable standalone."""
    failures = 0
    for fn in OWN_TESTS:
        try:
            fn()
        except AssertionError as e:
            failures += 1
            print(f"{fn.__name__}: FAILED: {e}")
        else:
            if fn.__doc__ is None:
                pass

    try:
        test_lifter_cli_list_resumable(slow=slow)
    except AssertionError as e:
        failures += 1
        print(f"test_lifter_cli_list_resumable: FAILED: {e}")

    if failures:
        raise AssertionError(f"{failures} failure(s) in test_lift_report")
    print(f"test_lift_report: {len(OWN_TESTS) + 1} checks passed"
          f"{' (slow: full 77)' if slow else ''}")


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser()
    parser.add_argument("--slow", action="store_true")
    args = parser.parse_args()
    try:
        run(slow=args.slow)
    except AssertionError as e:
        print(e)
        sys.exit(1)
    sys.exit(0)
