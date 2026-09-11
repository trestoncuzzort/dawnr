"""Plain-python tests for t/conformance.py (ROADMAP 13.4), no kernel and no
network: everything here is manifest-shape checking, never a lowering or a
kernel call (that is conformance.py's own `python3 conformance.py` run,
reported by hand, not asserted in a unit test).

Checked:

  - the probe manifest names EVERY probe fuzz_lower.probes() builds, by
    comparing the two name sets directly (never a count, which would pass
    even if the sets differed) -- 13.4's own text: "the manifest covers
    every probe fuzz_lower builds (compare names)";
  - every probe's `expected` value is one of conformance.OUTCOME_VOCAB --
    13.4's own text: "a probe's expected cell is one of the outcome
    vocabulary";
  - the metamorphic manifest's applicable/not-applicable split covers all
    20 of metamorphic.TRANSFORMS exactly once, with no name lost between
    the two lists and none double-counted;
  - the combined manifest has no duplicate task names (build_manifest's own
    assertion, exercised here rather than only trusted);
  - format_table/grade run over a small synthetic rows/cols fixture (no
    kernel involved) and produce the PASS/FAIL/N-A vocabulary the module
    docstring promises, including the N/A-for-absent-kernel and
    FAIL-for-missing-cell cases.

Run as: cd <repo>/t && python3 test_conformance.py
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

import conformance as cf
import fuzz_lower as fz
import metamorphic as mm

HERE = Path(__file__).resolve().parent

UNIT_TESTS = []


def test(fn):
    UNIT_TESTS.append(fn)
    return fn


# ------------------------------------------------------ probe manifest --

@test
def test_probe_manifest_covers_every_fuzz_lower_probe():
    built = {p["name"] for p in fz.probes()}
    covered = {it["name"] for it in cf.probe_manifest()}
    assert built == covered, (built - covered, covered - built)
    assert len(built) == len(fz.probes()), "fuzz_lower.probes() has a dup name"


@test
def test_probe_manifest_nonempty():
    items = cf.probe_manifest()
    assert len(items) >= 30, len(items)          # 53 measured 2026-09-11
    assert all(it["kind"] == "probe" for it in items)


@test
def test_every_probe_expected_in_outcome_vocab():
    for it in cf.probe_manifest():
        assert it["expected"] in cf.OUTCOME_VOCAB, (it["name"], it["expected"])


@test
def test_probe_manifest_reads_not_invents_expectation():
    # The manifest's `expected` must be byte-identical to the probe's own
    # `_expect`, never independently re-decided.
    raw = {p["name"]: p["_expect"] for p in fz.probes()}
    for it in cf.probe_manifest():
        assert it["expected"] == raw[it["name"]], it["name"]


# ------------------------------------------------------------ metamorphic --

@test
def test_metamorphic_applicable_and_not_applicable_partition_all_transforms():
    items, not_applicable, _bugs = cf.metamorphic_manifest()
    all_labels = {label for label, _fn in mm.TRANSFORMS}
    na = set(not_applicable)
    assert na <= all_labels, na - all_labels
    applied_count = len(items)
    assert applied_count + len(na) == len(all_labels), (
        applied_count, len(na), len(all_labels))
    assert len(all_labels) == 20, len(all_labels)      # metamorphic.py's own count


@test
def test_metamorphic_items_expect_base_task_verdict():
    items, _na, _bugs = cf.metamorphic_manifest()
    assert items, "no metamorphic transform applied to the base task"
    for it in items:
        assert it["expected"] == cf.BASE_EXPECT
        assert it["kind"] == "metamorphic"
        assert it["task"]["name"] != "abs"     # renamed, no collision


@test
def test_metamorphic_manifest_deterministic():
    items1, na1, bugs1 = cf.metamorphic_manifest()
    items2, na2, bugs2 = cf.metamorphic_manifest()
    assert [i["name"] for i in items1] == [i["name"] for i in items2]
    assert na1 == na2
    assert bugs1 == bugs2


# ------------------------------------------------------- combined manifest --

@test
def test_build_manifest_no_duplicate_names():
    items, _na, _bugs = cf.build_manifest()
    names = [it["name"] for it in items]
    assert len(names) == len(set(names)), "duplicate names in build_manifest()"


@test
def test_build_manifest_is_probes_plus_metamorphic():
    items, _na, _bugs = cf.build_manifest()
    probes = cf.probe_manifest()
    meta, _na2, _bugs2 = cf.metamorphic_manifest()
    assert len(items) == len(probes) + len(meta)
    kinds = {it["kind"] for it in items}
    assert kinds <= {"probe", "metamorphic", "metamorphic-bug"}


# --------------------------------------------------------------- grading --

@test
def test_grade_pass_fail_na_vocabulary():
    items = [{"name": "t1", "kind": "probe", "expected": "verified",
             "adversarial": False}]
    cols = [("dafny", "1.0"), ("verus", "ABSENT: no binary")]
    rows = {"t1": {"dafny": ("verified", "refuted", True)}}
    verdicts = cf.grade(items, rows, cols)
    assert verdicts["t1"]["dafny"] == "PASS"
    assert verdicts["t1"]["verus"] == "N/A"


@test
def test_grade_fail_on_mismatch_and_missing_cell():
    items = [{"name": "t1", "kind": "probe", "expected": "refuted",
             "adversarial": True}]
    cols = [("dafny", "1.0"), ("verus", "1.0")]
    rows = {"t1": {"dafny": ("verified", "refuted", True)}}   # wrong outcome
    verdicts = cf.grade(items, rows, cols)
    assert verdicts["t1"]["dafny"] == "FAIL"
    assert verdicts["t1"]["verus"] == "FAIL"       # no cell at all


@test
def test_grade_rejected_membership_not_equality():
    """2026-09-11 (ROADMAP 13.4): an "expected": "rejected" item PASSes on
    ANY of conformance.REJECTED_OK (refuted, unproved, malformed,
    lower-error), never only on the literal string "rejected" (which is
    not itself a real-column outcome any backend emits), and FAILs on
    verified, timeout or vacuous -- the three outcomes REJECTED_OK's own
    comment says a sound kernel must never speak here."""
    items = [{"name": "t1", "kind": "probe", "expected": "rejected",
             "adversarial": True}]
    cols = [("dafny", "1.0"), ("verus", "1.0"), ("spark", "1.0"),
           ("framac", "1.0")]
    rows = {"t1": {"dafny": ("refuted", "refuted", True),
                   "verus": ("unproved", "unproved", True),
                   "spark": ("timeout", "timeout", True),
                   "framac": ("vacuous", "vacuous", True)}}
    verdicts = cf.grade(items, rows, cols)
    assert verdicts["t1"]["dafny"] == "PASS"
    assert verdicts["t1"]["verus"] == "PASS"
    assert verdicts["t1"]["spark"] == "FAIL"
    assert verdicts["t1"]["framac"] == "FAIL"
    assert cf.REJECTED_OK == {"refuted", "unproved", "malformed",
                              "lower-error"}


@test
def test_grade_decorative_reads_the_pair_via_harness():
    """2026-09-11 (ROADMAP 13.4): an "expected": "decorative" item is
    graded through harness.decorative_kind on the (real, twin) PAIR, not
    real-outcome equality -- fz_p_vac_post's own task, whose measured
    ladder witness (collapse-if, `_ens` False) is exactly the "nothing
    entailed a refutation" shape decorative_kind's docstring names."""
    task = next(p for p in fz.probes() if p["name"] == "fz_p_vac_post")
    items = [{"name": "fz_p_vac_post", "kind": "probe",
             "expected": "decorative", "task": task, "adversarial": True}]
    cols = [("dafny", "1.0")]
    rows_both_verified = {"fz_p_vac_post": {"dafny": ("verified", "verified",
                                                      True)}}
    verdicts = cf.grade(items, rows_both_verified, cols)
    assert verdicts["fz_p_vac_post"]["dafny"] == "PASS"
    rows_refuted = {"fz_p_vac_post": {"dafny": ("refuted", "refuted", True)}}
    verdicts2 = cf.grade(items, rows_refuted, cols)
    assert verdicts2["fz_p_vac_post"]["dafny"] == "FAIL"


@test
def test_grade_metamorphic_bug_is_hard_fail():
    items = [{"name": "mm_tripwire_x", "kind": "metamorphic-bug",
             "expected": "TRIPWIRE", "adversarial": False}]
    cols = [("dafny", "1.0"), ("verus", "ABSENT: no binary")]
    rows = {}
    verdicts = cf.grade(items, rows, cols)
    assert verdicts["mm_tripwire_x"]["dafny"] == "FAIL"
    assert verdicts["mm_tripwire_x"]["verus"] == "N/A"


@test
def test_format_table_contains_expected_column_and_pass_fail():
    items = [{"name": "t1", "kind": "probe", "expected": "verified",
             "task": {}, "why": "", "adversarial": False}]
    cols = [("dafny", "1.0")]
    rows = {"t1": {"dafny": ("verified", "refuted", True)}}
    verdicts = {"t1": {"dafny": "PASS"}}
    table = cf.format_table(cols, items, rows, verdicts, [], [], HERE)
    assert "| task | expected | dafny |" in table
    assert "[PASS]" in table
    assert "t1" in table and "verified" in table


def run() -> None:
    failures = 0
    for fn in UNIT_TESTS:
        try:
            fn()
            print(f"{fn.__name__}: pass")
        except AssertionError as e:
            failures += 1
            print(f"{fn.__name__}: FAILED: {e}")
        except Exception as e:                                  # noqa: BLE001
            failures += 1
            traceback.print_exc()
            print(f"{fn.__name__}: FAILED (exception): {e}")
    if failures:
        raise AssertionError(f"{failures} of {len(UNIT_TESTS)} test(s) failed")
    print(f"test_conformance: all {len(UNIT_TESTS)} checks passed")


if __name__ == "__main__":
    try:
        run()
    except AssertionError as e:
        print(f"FAILED: {e}")
        sys.exit(1)
    sys.exit(0)
