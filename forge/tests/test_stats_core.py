"""tests/test_stats_core.py — the published numbers, pinned to the code.

Three layers, each with a reason:

  1. Known t-distribution values — the same self-checks analyze_run1.py has
     always run, so the extraction cannot have changed the machinery.
  2. THE PUBLISHED TABLE 1 AND TOST VALUES, recomputed from the retained rows
     in data/ruler_noise.jsonl. Until stats_core.py existed, the paper's three
     equivalence p-values (.0024 / .0433 / .295) and its 90% interval
     [-0.84, +1.94] pp were hand-derived — reproducible by no code in this
     repository. Now they are asserted to the digit. If the data or the code
     drifts, this file says so before the paper does.
  3. A DELIBERATELY BROKEN TOST kept in this file (test_detectors.py idiom):
     p = min(p_lower, p_upper) instead of max. That is a real bug seen in the
     wild — equivalence declared from one side only — and at the ±1.00 pp
     margin it DECLARES equivalence (p = .034) where the correct test does not
     (p = .295). A test both versions pass is not testing anything; this pair
     cannot both pass.
  4. DEGENERATE INPUTS, with the broken twins kept beside them for the same
     reason. Each twin is the code that used to ship, verbatim, and each one
     returns something a caller would print: t = 0 and p = 1 for a paired
     difference that is a constant 1.0, and a bare ZeroDivisionError from
     inside a df expression for two constant Welch arms. A test the old code
     also passes proves nothing, so the twins are asserted to still misbehave.

Run: python tests/test_stats_core.py   (self-executing; there is no pytest on
the machines this runs on — the runner at the bottom is the same one every
other file in tests/ carries)
"""
from __future__ import annotations

import json
import math
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import analyze_run1                                               # noqa: E402
from analyze_run1 import BASE, NULL, TRAINED, load, rate          # noqa: E402
from stats_core import (DegenerateInput, certify, mean, paired,   # noqa: E402
                        sd, t_crit, t_sf, tost, welch)


def _arms():
    by = load()
    return ([rate(r) for r in by[TRAINED]], [rate(r) for r in by[NULL]])


# --- 1. machinery ---------------------------------------------------------
def test_t_distribution_known_values():
    assert abs(t_crit(10) - 2.228) < 0.002
    assert abs(t_crit(78) - 1.991) < 0.003
    assert abs(2 * t_sf(2.0, 30) - 0.0546) < 0.001
    # 90% two-sided critical value, used by the TOST interval
    assert abs(t_crit(74, alpha=0.10) - 1.6657) < 0.002


# --- 2. the published numbers, from the retained bytes --------------------
def test_table1_primary_comparison_reproduces():
    tr, nu = _arms()
    assert len(tr) == 40 and len(nu) == 40, "prereg N drifted"
    w = welch(tr, nu)
    assert abs(w["t"] - 0.656) < 0.0005, w["t"]
    assert abs(w["df"] - 74.0) < 0.05, w["df"]
    assert abs(w["p"] - 0.5140) < 0.00005, w["p"]
    assert abs(w["diff"] * 100 - 0.55) < 0.005, w["diff"]
    assert abs(w["ci"][0] * 100 - -1.12) < 0.005
    assert abs(w["ci"][1] * 100 - 2.21) < 0.005


def test_published_tost_values_reproduce():
    tr, nu = _arms()
    # preregistered margin +-2.98 pp -> p = .0024
    assert abs(tost(tr, nu, 0.0298)["p"] - 0.0024) < 0.00005
    # +-2.00 pp -> p = .0433 (the abstract's "rejected +-2 pp or larger")
    assert abs(tost(tr, nu, 0.0200)["p"] - 0.0433) < 0.00005
    # +-1.00 pp -> p = .295 ("simply not resolved at this n")
    assert abs(tost(tr, nu, 0.0100)["p"] - 0.295) < 0.0005
    # the 90% TOST interval, [-0.84, +1.94] pp
    lo, hi = tost(tr, nu, 0.0200)["ci90"]
    assert abs(lo * 100 - -0.84) < 0.005
    assert abs(hi * 100 - 1.94) < 0.005


def test_tost_decisions_match_the_paper():
    tr, nu = _arms()
    assert tost(tr, nu, 0.0298)["equivalent"] is True
    assert tost(tr, nu, 0.0200)["equivalent"] is True
    assert tost(tr, nu, 0.0100)["equivalent"] is False


# --- 3. the broken twin ---------------------------------------------------
def _tost_broken_min(a, b, margin):
    """The bug: min() of the one-sided p-values. Kept so the tests can prove
    they distinguish it from the correct max()."""
    r = tost(a, b, margin)
    return {"p": min(r["p_lower"], r["p_upper"]),
            "equivalent": min(r["p_lower"], r["p_upper"]) < 0.05}


def test_broken_min_tost_fails_where_correct_does_not():
    tr, nu = _arms()
    correct = tost(tr, nu, 0.0100)
    broken = _tost_broken_min(tr, nu, 0.0100)
    # The broken version declares equivalence at +-1 pp; the correct one must not.
    assert broken["equivalent"] is True, "twin lost its bug; the test is dead"
    assert correct["equivalent"] is False
    assert broken["p"] < 0.05 < correct["p"]


# --- Monte Carlo, small run so the suite stays fast -----------------------
def test_certificate_holds_alpha():
    c = certify(sims=2000, verbose=False)
    assert 0.03 < c["welch_fpr_equal_var"] < 0.07
    assert 0.03 < c["welch_fpr_unequal_var"] < 0.07
    assert c["tost_fpr_at_margin"] < 0.07


# --- 4. degenerate inputs, and the twins that used to answer them ---------
def _raises(fn, *a, **k):
    """Returns the exception a call raised, or None. Deliberately catches
    everything: the point of these tests is WHICH exception comes out."""
    try:
        fn(*a, **k)
    except BaseException as e:                                    # noqa: BLE001
        return e
    return None


def _paired_silent_zero(a, b):
    """The bug, verbatim: `t = mean(d)/se if se else 0.0`. A zero standard
    error becomes a t of 0 and a p of 1 -- 'no evidence of a difference' --
    even when every single pair differs by the same non-zero amount."""
    d = [x - y for x, y in zip(a, b)]
    n = len(d)
    se = sd(d) / math.sqrt(n)
    t = mean(d) / se if se else 0.0
    return {"diff": mean(d), "se": se, "df": n - 1, "t": t,
            "p": 2.0 * t_sf(abs(t), n - 1)}


def _welch_unguarded_df(a, b):
    """The bug, verbatim: the Welch-Satterthwaite df with nothing in front of
    it. Two constant arms make it 0/0 and it dies inside the expression."""
    na, nb = len(a), len(b)
    va, vb = sd(a) ** 2, sd(b) ** 2
    return (va / na + vb / nb) ** 2 / (
        (va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1))


def test_paired_refuses_a_constant_non_zero_difference():
    e = _raises(paired, [1.0, 1.0], [0.0, 0.0])
    assert isinstance(e, DegenerateInput), f"paired() answered instead: {e!r}"
    assert "unbounded" in str(e), str(e)
    # The twin must still produce the misleading answer, or this test is dead.
    twin = _paired_silent_zero([1.0, 1.0], [0.0, 0.0])
    assert twin["diff"] == 1.0 and twin["t"] == 0.0 and twin["p"] == 1.0, twin


def test_paired_refuses_identical_samples():
    e = _raises(paired, [1.0, 1.0, 1.0], [1.0, 1.0, 1.0])
    assert isinstance(e, DegenerateInput), f"paired() answered instead: {e!r}"
    assert "identical" in str(e), str(e)


def test_paired_refuses_mismatched_lengths():
    """zip() truncates in silence, so the old code compared the first n pairs
    of a mismatched call and reported an n the caller never asked for."""
    e = _raises(paired, [1.0, 2.0, 3.0], [1.0, 2.0])
    assert isinstance(e, DegenerateInput), f"paired() answered instead: {e!r}"


def test_welch_refuses_two_constant_arms_by_name():
    e = _raises(welch, [1.0, 1.0], [0.0, 0.0])
    assert isinstance(e, DegenerateInput), f"welch() raised {e!r}"
    assert not isinstance(e, ZeroDivisionError)
    # The twin still dies the old way, from inside the arithmetic.
    twin = _raises(_welch_unguarded_df, [1.0, 1.0], [0.0, 0.0])
    assert isinstance(twin, ZeroDivisionError), f"twin lost its bug: {twin!r}"


def test_welch_still_answers_when_only_one_arm_is_constant():
    """ONE constant arm is not degenerate: the df collapses to the other arm's
    n-1, which is the right answer. The guard must not swallow this case."""
    w = welch([1.0, 1.0, 1.0], [0.0, 1.0, 2.0])
    assert math.isfinite(w["t"]) and math.isfinite(w["p"])
    assert abs(w["df"] - 2.0) < 1e-9, w["df"]


def test_non_finite_observations_are_refused_everywhere():
    nan, inf = float("nan"), float("inf")
    for fn, args in ((welch, ([0.1, 0.2, nan], [0.1, 0.2, 0.3])),
                     (welch, ([0.1, 0.2, 0.3], [0.1, 0.2, inf])),
                     (paired, ([0.1, 0.2, nan], [0.1, 0.2, 0.3])),
                     (tost, ([0.1, 0.2, nan], [0.1, 0.2, 0.3], 0.02))):
        e = _raises(fn, *args)
        assert isinstance(e, DegenerateInput), f"{fn.__name__} returned {e!r}"


def test_a_nan_p_value_would_read_as_not_significant():
    """WHY the check above matters, asserted rather than described: NaN fails
    both halves of the significance question, so a caller that asks only one
    of them gets a definite-looking answer from a run that has no result."""
    nan = float("nan")
    assert not (nan < 0.05)
    assert not (nan >= 0.05)


def test_the_loader_refuses_a_nan_rate():
    """json.loads accepts the bare token NaN. The banked file must not, and
    the refusal has to happen at the loader -- after that the value is a float
    like any other."""
    row = {"model": TRAINED, "replicate": 1, "n_tasks": 1, "n_samples": 5,
           "aggregate": {"pass@1": float("nan")},
           "per_task": [{"tid": "A", "greedy": None, "sampled": [1, 0, 1]}]}
    tmp = Path(tempfile.mkdtemp(prefix="test_stats_core_")) / "noise.jsonl"
    tmp.write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert "NaN" in tmp.read_text(encoding="utf-8"), "fixture lost its NaN"
    saved = analyze_run1.NOISE
    try:
        analyze_run1.NOISE = tmp
        e = _raises(load)
        assert isinstance(e, DegenerateInput), f"the loader accepted it: {e!r}"
    finally:
        analyze_run1.NOISE = saved
    # and the real file still loads, so the guard did not close the door.
    assert len(load()[BASE]) == 50


if __name__ == "__main__":
    fails = []
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            try:
                fn(); print(f"PASS {name}")
            except AssertionError as e:
                fails.append(name); print(f"FAIL {name}: {e}")
    print(f"\n{len(fails)} failed")
    raise SystemExit(1 if fails else 0)
