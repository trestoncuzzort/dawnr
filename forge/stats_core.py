#!/usr/bin/env python3
"""stats_core.py — one implementation of the statistics this project reports.

Extracted from analyze_run1.py (which now imports from here) so the t machinery
exists once. The extraction is behavior-preserving and WITNESSED: analyze_run1.py's
output is byte-identical before and after, and tests/test_stats_core.py asserts the
published Table 1 and TOST numbers to the digit from the retained rows.

WHAT IS NEW HERE AND WHY IT EXISTS
----------------------------------
TOST. The paper reports three equivalence p-values (.0024 at the preregistered
±2.98 pp margin, .0433 at ±2.00 pp, .295 at ±1.00 pp) and a 90% interval of
[−0.84, +1.94] pp — and until this file, no code in the repository computed them.
They were hand-derived. A number that appears in the paper but cannot be recomputed
by the repo is exactly the class of claim verify_paper.py exists to catch, so the
computation now lives here, on the same t implementation the primary comparison
uses, and the published values are pinned in the test suite.

HONEST LIMITS, stated first:
  - Welch and TOST assume approximate normality of the run-level rates. The paper
    already bounds this with a permutation test and Mann-Whitney (§ Results); this
    module does not reimplement those.
  - certify() is a Monte Carlo check of TYPE-I ERROR under Gaussian nulls, at a
    fixed seed. It certifies the procedures as implemented, not the normality of
    any particular data.
  - tost() returns p = max(p_lower, p_upper), the standard TOST decision value
    (Lakens, 2017). A min() here is a real bug seen in the wild — declared
    equivalence from one side only — and the test suite keeps that broken variant
    to prove the tests can tell them apart.

DEGENERATE INPUTS ARE REFUSED BY NAME, NOT ANSWERED
---------------------------------------------------
Three inputs used to leave this module with a number that was worse than no
number, and all three now raise DegenerateInput:

  - paired([1,1], [0,0]). Every pair differs by exactly 1.0, so the t statistic
    is 1.0/0 — unbounded, not zero. The old `t = mean(d)/se if se else 0.0`
    returned t = 0, p = 1: "no evidence of any difference", from data whose
    every observation differs. A silent sentinel dressed as a result.
  - welch() on two constant arrays. Both variances are zero, so the
    Welch–Satterthwaite df is 0/0 and the module raised ZeroDivisionError from
    the middle of an arithmetic expression, which tells a caller nothing about
    which input was bad. One constant arm is NOT degenerate and still answers.
  - a non-finite observation. Python's json admits NaN, so a NaN rate loads
    without complaint, and every comparison against the resulting p-value is
    False — `p < 0.05` and `p >= 0.05` are both False, so a caller that tests
    significance silently reports "not significant". analyze_run1.py refuses
    NaN at the loader as well; this is the second fence, for every other caller.

Refusing is deliberate. Any p this module returns gets printed, and a printed
p-value is a claim about evidence. Where the t framework defines none, the
honest output is a named error the caller can report, not a plausible float.

No scipy on the machines this runs on, so the t distribution is implemented here:
regularised incomplete beta by continued fraction (Lentz), critical values by
bisection. Self-checked against known values in certify() and the test suite.
"""
from __future__ import annotations

import math
import random

__all__ = ["DegenerateInput", "mean", "sd", "t_sf", "t_crit", "welch", "paired",
           "tost", "certify"]


class DegenerateInput(ValueError):
    """A sample on which the requested statistic is not defined.

    Raised instead of returning a sentinel, and instead of letting a bare
    ZeroDivisionError escape from inside an expression. The message names the
    offending sample and the reason, so a caller can print the truth.
    """


# --- t distribution -------------------------------------------------------
def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta (Lentz's method)."""
    tiny, eps = 1e-30, 3e-16
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        c = 1.0 + aa / c
        if abs(d) < tiny:
            d = tiny
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        c = 1.0 + aa / c
        if abs(d) < tiny:
            d = tiny
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def _betai(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
             + a * math.log(x) + b * math.log(1.0 - x))
    front = math.exp(lbeta)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_sf(t: float, df: float) -> float:
    """P(T > t): the upper tail of Student's t."""
    x = df / (df + t * t)
    tail = 0.5 * _betai(df / 2.0, 0.5, x)
    return tail if t > 0 else 1.0 - tail


def t_crit(df: float, alpha: float = 0.05) -> float:
    """Two-sided critical value at level alpha, by bisection on the CDF."""
    lo, hi = 0.0, 100.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if t_sf(mid, df) > alpha / 2.0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


# --- statistics -----------------------------------------------------------
def _sample(v: list[float], label: str, minimum: int = 2) -> list[float]:
    """Every entry point's front door: the sample is big enough and finite.

    A non-finite observation is checked HERE rather than at each formula,
    because NaN propagates to the p-value and then stops being detectable —
    both `p < alpha` and `p >= alpha` are False against a NaN, so it reads as
    "not significant" to any caller that only asks one of the two questions.
    """
    if len(v) < minimum:
        raise DegenerateInput(
            f"{label} needs at least {minimum} observations; got {len(v)}")
    bad = [i for i, x in enumerate(v) if not math.isfinite(x)]
    if bad:
        raise DegenerateInput(
            f"{label} carries {len(bad)} non-finite observation(s) at index "
            f"{bad[:5]}{'...' if len(bad) > 5 else ''}: "
            f"{[v[i] for i in bad[:5]]}")
    return v


def mean(v: list[float]) -> float:
    return sum(_sample(v, "mean sample", minimum=1)) / len(v)


def sd(v: list[float]) -> float:
    _sample(v, "sd sample")
    m = mean(v)
    return math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1))


def welch(a: list[float], b: list[float]) -> dict:
    """Welch's t-test. Each arm keeps its own variance; nothing is pooled.

    Raises DegenerateInput when BOTH arms are constant: the standard error and
    the Welch-Satterthwaite df are then each 0/0. One constant arm is fine --
    the df collapses to the other arm's n-1, which is the correct answer, not a
    degenerate one.
    """
    _sample(a, "welch arm a")
    _sample(b, "welch arm b")
    na, nb = len(a), len(b)
    va, vb = sd(a) ** 2, sd(b) ** 2
    if va == 0.0 and vb == 0.0:
        raise DegenerateInput(
            f"both welch arms are constant (a == {a[0]!r}, b == {b[0]!r}): the "
            f"standard error is 0 and the Welch-Satterthwaite df is 0/0, so "
            f"neither t nor a p-value is defined. Observed difference "
            f"{mean(a) - mean(b)!r}.")
    se = math.sqrt(va / na + vb / nb)
    diff = mean(a) - mean(b)
    df = (va / na + vb / nb) ** 2 / (
        (va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1))
    t = diff / se
    tc = t_crit(df)
    return {"diff": diff, "se": se, "df": df, "t": t,
            "p": 2.0 * t_sf(abs(t), df),
            "ci": (diff - tc * se, diff + tc * se)}


def paired(a: list[float], b: list[float]) -> dict:
    """Paired t-test on a - b.

    Raises DegenerateInput when the differences have zero spread. That covers
    both the identical case (every difference 0, t = 0/0) and the constant
    non-zero case (every difference the same value d != 0, t = d/0, unbounded).
    The old code answered t = 0, p = 1 for both, which for the second one is
    the exact opposite of what the sample shows.
    """
    if len(a) != len(b):
        raise DegenerateInput(
            f"paired samples must be the same length; got {len(a)} and {len(b)}")
    _sample(a, "paired arm a")
    _sample(b, "paired arm b")
    d = [x - y for x, y in zip(a, b)]
    n = len(d)
    spread = sd(d)
    if spread == 0.0:
        raise DegenerateInput(
            f"every paired difference is exactly {d[0]!r} over n={n}, so the "
            f"sample spread is 0 and t = {mean(d)!r}/0 is undefined"
            + (" (the two samples are identical)" if d[0] == 0 else
               " -- unbounded, NOT zero") + ". No p-value is returned.")
    se = spread / math.sqrt(n)
    t = mean(d) / se
    tc = t_crit(n - 1)
    return {"diff": mean(d), "se": se, "df": n - 1, "t": t,
            "p": 2.0 * t_sf(abs(t), n - 1),
            "ci": (mean(d) - tc * se, mean(d) + tc * se)}


def tost(a: list[float], b: list[float], margin: float) -> dict:
    """Two one-sided tests for equivalence at ±margin (Lakens, 2017), on the
    same Welch machinery as the primary comparison: unpooled se, Welch df.

    p_lower tests H0: diff <= -margin (rejecting says diff > -margin);
    p_upper tests H0: diff >= +margin (rejecting says diff < +margin);
    p = max of the two — equivalence is declared only when BOTH one-sided
    nulls are rejected. The 90% interval is the TOST-standard interval whose
    containment inside [−margin, +margin] is the same decision at alpha .05.
    """
    if margin <= 0:
        raise ValueError("margin must be positive")
    w = welch(a, b)
    diff, se, df = w["diff"], w["se"], w["df"]
    t_lower = (diff + margin) / se     # against the -margin boundary
    t_upper = (diff - margin) / se     # against the +margin boundary
    p_lower = t_sf(t_lower, df)        # P(T > t_lower): small when diff >> -margin
    p_upper = t_sf(-t_upper, df)       # P(T < t_upper): small when diff << +margin
    tc90 = t_crit(df, alpha=0.10)
    return {"margin": margin, "diff": diff, "se": se, "df": df,
            "p_lower": p_lower, "p_upper": p_upper,
            "p": max(p_lower, p_upper),
            "equivalent": max(p_lower, p_upper) < 0.05,
            "ci90": (diff - tc90 * se, diff + tc90 * se)}


# --- Monte Carlo certificate ---------------------------------------------
def certify(sims: int = 20_000, n: int = 40, seed: int = 20260831,
            verbose: bool = True) -> dict:
    """Type-I-error certificate for welch() and tost(), under Gaussian nulls.

    Three certified properties, each with its analytic target:
      1. welch under an equal-variance null rejects at ~alpha (.05).
      2. welch under an UNEQUAL-variance null (sd ratio 2:1) still rejects at
         ~alpha — the property Welch buys and pooling loses.
      3. tost with the TRUE difference placed exactly AT the margin declares
         equivalence at ~alpha — the equivalence test's own type-I error.
    A fixed seed makes the certificate reproducible; change the seed and the
    rates move within binomial noise (~±0.4 pp at 20k sims), not further.
    """
    rng = random.Random(seed)

    def arm(mu, sigma):
        return [rng.gauss(mu, sigma) for _ in range(n)]

    welch_eq = welch_uneq = tost_at_margin = 0
    margin = 0.5   # in sd units of the base arm (sigma=1)
    for _ in range(sims):
        if welch(arm(0, 1), arm(0, 1))["p"] < 0.05:
            welch_eq += 1
        if welch(arm(0, 2), arm(0, 1))["p"] < 0.05:
            welch_uneq += 1
        if tost(arm(margin, 1), arm(0, 1), margin)["equivalent"]:
            tost_at_margin += 1

    out = {"sims": sims, "n_per_arm": n, "seed": seed,
           "welch_fpr_equal_var": welch_eq / sims,
           "welch_fpr_unequal_var": welch_uneq / sims,
           "tost_fpr_at_margin": tost_at_margin / sims,
           "target": 0.05}
    if verbose:
        print(f"  Monte Carlo certificate ({sims:,} sims, n={n}/arm, seed {seed})")
        print(f"    welch type-I, equal variances    {out['welch_fpr_equal_var']:.4f}  (target .05)")
        print(f"    welch type-I, sd ratio 2:1       {out['welch_fpr_unequal_var']:.4f}  (target .05)")
        print(f"    tost type-I, true diff at margin {out['tost_fpr_at_margin']:.4f}  (target <= .05)")
    return out


def _self_check() -> None:
    """Known values, same as analyze_run1.py has always asserted."""
    assert abs(t_crit(10) - 2.228) < 0.002, t_crit(10)
    assert abs(t_crit(78) - 1.991) < 0.003, t_crit(78)
    assert abs(2 * t_sf(2.0, 30) - 0.0546) < 0.001, 2 * t_sf(2.0, 30)


if __name__ == "__main__":
    _self_check()
    print("stats_core: t-distribution self-checks pass")
    certify()
