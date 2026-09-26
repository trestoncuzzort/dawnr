#!/usr/bin/env python3
"""t/compare_arms.py -- decide between two locallm recipes from per-seed held-out counts.

    python3 t/score_heldout.py --split t/out/loop/split-v5.json --outcomes t/out/r12-outcomes.json \\
        base-s1337 base-s1 ... new-s1337 new-s1 ...
    python3 t/compare_arms.py --outcomes t/out/r12-outcomes.json \\
        --arm base=base-s1337,base-s1,... --arm new=new-s1337,new-s1,... \\
        --prereg t/PREREG-r12.md [--paired] [--metric clean|tests-pass|written-clean] \\
        [--problems decontam|all] [--nboot 10000] [--seed 0] [--json OUT.json]

The unit is the training run, so every number here is over seeds, never over
one checkpoint (r12 plan, section E; internal/research/r12-2026-09-21/eval-stats.md).
The first --arm is the baseline A, the second the treatment B; one or two arms,
never more, because a registered look is one decision.

What is printed, and where each piece comes from:

* per arm: "mean [min-max] (n seeds)", with a warning under 10 seeds;
* per tag: a Wilson 95% interval in problems, because the CLT interval fails
  at 2 of 232 (Bowyer et al., arXiv:2503.01747; Wald goes negative there);
* the difference in means and the exact one-sided permutation p over seeds,
  with its mid-p: the subset-sum shift of Streitberg and Roehmel as in
  exactRankTests' permdist.c (raw.githubusercontent.com/cran/exactRankTests/master/src/permdist.c),
  enumerated when small; a sign-flip test under --paired (same corpus, same
  seed list);
* Bouthillier's probability that one run of B beats one run of A
  (arXiv:2103.03098, appendix C), with a percentile bootstrap interval;
* McNemar's mid-p when both arms are a single checkpoint, with Fagerland's
  tie case (BMC Med Res Methodol 13:91, pmc.ncbi.nlm.nih.gov/articles/PMC3716987);
* Dodge's expected best of n seeds, so a best seed is only ever reported
  beside what n draws are expected to give (arXiv:1909.03004);
* the per-problem seed solve-rate table (Miller, arXiv:2411.00640, the paired view).

The verdict is eval-stats.md protocol step 4, now also written into section E
of t/RUN-NEXT-locallm-r12.md: ADOPT if the permutation p <= 0.05 and the upper
bound of the P(B>A) interval is above 0.75; NOT MEANINGFUL if that upper bound
is at most 0.75; otherwise INCONCLUSIVE. It departs from Bouthillier twice, on
purpose: significance comes from the exact permutation p rather than from the
interval's lower bound above 0.5, and ties count 1/2 (the Mann-Whitney
convention the paper calls equivalent) rather than strict wins only, because
counts of 0-6 tie constantly. Without --prereg the verdict is printed as
unregistered and exploratory.

Prereg file format: one line ``seeds: N``; every arm must have exactly N tags
or the run is refused. Optional ``metric: <name>`` and ``problems: <name>``
lines are enforced when present. Anything else in the file is ignored.

Refused, never skipped: an unknown tag, a partial tag, more than two arms,
--paired over unequal arms, written-clean over a tag scored without --corpus,
a prereg whose seed count the arms do not match. Standard library only.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import random
import re
import sys
from fractions import Fraction
from math import comb
from pathlib import Path

ALPHA = Fraction(1, 20)
GAMMA = 0.75
ENUMERATE_UP_TO = 100_000
METRICS = ("clean", "tests-pass", "written-clean")
PROBLEM_SETS = ("decontam", "all")


# -- exact permutation tests -----------------------------------------------------------------------

def _ints(values, label: str) -> list[int]:
    out = []
    for v in values:
        if isinstance(v, bool) or not isinstance(v, int):
            raise ValueError(f"{label}: per-seed counts must be integers, got {v!r}")
        out.append(v)
    return out


def _size_sum_counts(values: list[int], size: int) -> list[int]:
    """counts[s] = number of ``size``-subsets of ``values`` with sum s (non-negative ints).

    The two-sample shift algorithm of Streitberg and Roehmel (1986), as in
    exactRankTests' cpermdist2: H[i][j] += H[i - 1][j - v] for every value v,
    iterating i and j downwards so each value is used once. Exact big-int counts.
    """
    total = sum(values)
    dp = [[0] * (total + 1) for _ in range(size + 1)]
    dp[0][0] = 1
    for v in values:
        for j in range(size, 0, -1):
            row, prev = dp[j], dp[j - 1]
            for s in range(total, v - 1, -1):
                if prev[s - v]:
                    row[s] += prev[s - v]
    return dp[size]


def permutation_test(a, b, method: str = "auto") -> tuple[Fraction, Fraction]:
    """One-sided exact permutation p that B's mean exceeds A's, and its mid-p.

    The statistic is the sum of B's counts (the arm sizes are fixed, so this is
    the difference in means): p = P(a random |B|-subset of the pooled counts sums
    to at least the observed sum). Enumerated with itertools.combinations while
    C(N, |B|) <= 100000, otherwise by the subset-sum DP above.
    """
    a, b = _ints(a, "A"), _ints(b, "B")
    if not a or not b:
        raise ValueError("both arms need at least one seed")
    shift = min(a + b)
    pooled = [v - shift for v in a + b]
    n_b = len(b)
    observed = sum(v - shift for v in b)
    total = comb(len(pooled), n_b)
    if method == "enumerate" or (method == "auto" and total <= ENUMERATE_UP_TO):
        ge = eq = 0
        for subset in itertools.combinations(pooled, n_b):
            s = sum(subset)
            ge += s >= observed
            eq += s == observed
    else:
        counts = _size_sum_counts(pooled, n_b)
        ge = sum(counts[observed:])
        eq = counts[observed] if observed < len(counts) else 0
    return Fraction(ge, total), Fraction(2 * ge - eq, 2 * total)


def paired_permutation_test(a, b, method: str = "auto") -> tuple[Fraction, Fraction]:
    """One-sided exact sign-flip p over d_i = b_i - a_i (same seed list, paired by position).

    T* = sum|d| - 2X where X is the sum of |d_i| over the seeds whose sign is
    flipped negative, so P(T* >= T) counts the subsets of |d| with 2X <= sum|d| - T:
    the symmetry-problem shift of exactRankTests' cpermdist1, H[s] += H[s - v].
    """
    a, b = _ints(a, "A"), _ints(b, "B")
    if len(a) != len(b) or not a:
        raise ValueError("--paired needs two arms of the same length, paired by position")
    d = [y - x for x, y in zip(a, b)]
    magnitudes = [abs(v) for v in d]
    bound = sum(magnitudes) - sum(d)           # 2X <= bound
    total = 1 << len(d)
    if method == "enumerate" or (method == "auto" and total <= ENUMERATE_UP_TO):
        ge = eq = 0
        for signs in itertools.product((1, -1), repeat=len(d)):
            x = sum(v for v, sign in zip(magnitudes, signs) if sign < 0)
            ge += 2 * x <= bound
            eq += 2 * x == bound
    else:
        counts = [0] * (sum(magnitudes) + 1)
        counts[0] = 1
        for v in magnitudes:
            for s in range(len(counts) - 1, v - 1, -1):
                if counts[s - v]:
                    counts[s] += counts[s - v]
        ge = sum(c for s, c in enumerate(counts) if 2 * s <= bound)
        eq = counts[bound // 2] if bound % 2 == 0 and bound // 2 < len(counts) else 0
    return Fraction(ge, total), Fraction(2 * ge - eq, 2 * total)


# -- the other statistics ---------------------------------------------------------------------------

def prob_outperform(a, b, paired: bool = False) -> Fraction:
    """P(one run of B beats one run of A), ties counted 1/2.

    Bouthillier et al. (arXiv:2103.03098, appendix C) estimate this over random
    pairings and count strict wins; unpaired arms here use every one of the
    |A|x|B| pairs (the Mann-Whitney index, which the paper states is equivalent)
    so the estimate carries no pairing noise, and ties count 1/2 because integer
    counts of 0-6 tie constantly and strict wins alone would push the
    probability toward 0 under the null.
    """
    if paired:
        pairs = list(zip(a, b))
    else:
        pairs = [(x, y) for x in a for y in b]
    wins = sum(2 if y > x else 1 if y == x else 0 for x, y in pairs)
    return Fraction(wins, 2 * len(pairs))


def bootstrap_ci(a, b, paired: bool, nboot: int = 10_000, seed: int = 0) -> tuple[float, float]:
    """Percentile bootstrap interval for prob_outperform: resample pairs, or each arm on its own."""
    rnd = random.Random(seed)
    values = []
    for _ in range(nboot):
        if paired:
            idx = [rnd.randrange(len(a)) for _ in a]
            values.append(prob_outperform([a[i] for i in idx], [b[i] for i in idx], paired=True))
        else:
            values.append(prob_outperform([rnd.choice(a) for _ in a], [rnd.choice(b) for _ in b]))
    values.sort()
    lo = values[math.floor(0.025 * (nboot - 1))]
    hi = values[math.ceil(0.975 * (nboot - 1))]
    return float(lo), float(hi)


def mcnemar_exact_two_sided(n12: int, n21: int) -> Fraction:
    """Exact conditional McNemar: twice the smaller binomial tail over the discordant pairs."""
    n = n12 + n21
    if n == 0:
        return Fraction(1)
    tail = sum(comb(n, x) for x in range(min(n12, n21) + 1))
    return min(Fraction(1), Fraction(2 * tail, 1 << n))


def mcnemar_mid_p(n12: int, n21: int) -> Fraction:
    """Fagerland, Lydersen and Laake 2013: mid-p = exact two-sided p minus f(n12|n); when
    n12 = n21 the mid-p is 1 - f(n12|n)/2. No discordant pair at all: 1."""
    n = n12 + n21
    if n == 0:
        return Fraction(1)
    point = Fraction(comb(n, n12), 1 << n)
    if n12 == n21:
        return 1 - point / 2
    return mcnemar_exact_two_sided(n12, n21) - point


def expected_best_of(values, n: int) -> Fraction:
    """Dodge et al. 2019, expected validation performance of the best of n draws:
    sum over distinct v of v * (F(v)^n - F(v-)^n) with F the empirical CDF."""
    values = sorted(values)
    total = len(values)
    if not total or n < 1:
        raise ValueError("expected_best_of needs values and n >= 1")
    expectation, below = Fraction(0), Fraction(0)
    for v in sorted(set(values)):
        at_or_below = Fraction(sum(1 for x in values if x <= v), total)
        expectation += v * (at_or_below ** n - below ** n)
        below = at_or_below
    return expectation


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Wilson score interval, returned in problems rather than as a fraction.

    Bowyer et al. (arXiv:2503.01747) show CLT intervals collapse or go negative
    below a few hundred datapoints; for 2 of 232 the Wald interval is negative
    at its lower end, while this gives [0.55, 7.16] problems.
    """
    if n <= 0 or not 0 <= k <= n:
        raise ValueError("wilson needs 0 <= k <= n and n > 0")
    p = k / n
    z2 = z * z
    denominator = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denominator
    return (max(0.0, centre - half) * n, min(1.0, centre + half) * n)


def verdict(p: Fraction, ci_upper: float) -> str:
    """eval-stats.md protocol step 4, the rule section E of the r12 plan registers."""
    if ci_upper <= GAMMA:
        return "NOT MEANINGFUL"
    if p <= ALPHA:
        return "ADOPT"
    return "INCONCLUSIVE"


def simulate_arm(n_seeds: int, rnd: random.Random) -> list[int]:
    """Per-seed clean counts from the spread eval-stats.md fitted: six easy problems at
    0.3 and 194 at 0.001, with a per-seed effect N(0, 0.75) on the logit. Used by the
    size test, which asks that halves of one such arm are told apart at most 5% of the time."""
    easy, hard = [0.3] * 6, [0.001] * 194
    counts = []
    for _ in range(n_seeds):
        effect = rnd.gauss(0, 0.75)
        total = 0
        for p in easy + hard:
            logit = math.log(p / (1 - p)) + effect
            total += rnd.random() < 1 / (1 + math.exp(-logit))
        counts.append(total)
    return counts


# -- reading the export -----------------------------------------------------------------------------

def read_prereg(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise SystemExit(f"cannot read the prereg file {path}: {e}")
    seeds = {int(m.group(1)) for m in re.finditer(r"(?m)^\s*seeds:\s*(\d+)\s*$", text)}
    if len(seeds) != 1:
        raise SystemExit(f"{path}: want exactly one 'seeds: N' line, found {sorted(seeds) or 'none'}")
    out = {"seeds": seeds.pop()}
    for key, allowed in (("metric", METRICS), ("problems", PROBLEM_SETS)):
        found = {m.group(1) for m in re.finditer(rf"(?m)^\s*{key}:\s*(\S+)\s*$", text)}
        if len(found) > 1:
            raise SystemExit(f"{path}: conflicting '{key}:' lines {sorted(found)}")
        if found:
            value = found.pop()
            if value not in allowed:
                raise SystemExit(f"{path}: {key} must be one of {allowed}, not {value!r}")
            out[key] = value
    return out


def panel_for(export: dict, problems: str) -> tuple[str, dict]:
    panels = export.get("panels")
    if not isinstance(panels, dict):
        raise SystemExit("the outcomes file has no panels; write it with score_heldout.py --outcomes")
    prefix = "clean-" if problems == "decontam" else "all-"
    names = [name for name in panels if name.startswith(prefix)]
    if len(names) != 1:
        raise SystemExit(f"want one {prefix}N panel in the outcomes file, found {names}")
    return names[0], panels[names[0]]


def tag_outcomes(panel: dict, tag: str, metric: str) -> dict[int, bool]:
    """One Boolean per problem of the panel for the metric, refusing what cannot be measured."""
    tags = panel.get("tags", {})
    if tag not in tags:
        raise SystemExit(f"tag {tag!r} is not in the outcomes file; score it first (known: {sorted(tags)[:8]})")
    entry = tags[tag]
    if entry.get("partial"):
        raise SystemExit(f"tag {tag!r} is a partial answer set; a partial count is not a seed's number")
    ids = [int(i) for i in panel["task_ids"]]

    def field(name: str) -> dict[int, bool]:
        values = entry.get(name)
        if not isinstance(values, dict):
            raise SystemExit(f"tag {tag!r} has no {name} map; written-clean needs a set scored with --corpus"
                             if name == "recited" else f"tag {tag!r} has no {name} map")
        try:
            out = {tid: values[str(tid)] for tid in ids}
        except KeyError as e:
            raise SystemExit(f"tag {tag!r}: {name} map lacks problem {e}")
        if any(type(v) is not bool for v in out.values()):
            raise SystemExit(f"tag {tag!r}: {name} map is not Boolean")
        return out

    if metric == "clean":
        return field("clean")
    if metric == "tests-pass":
        return field("tests_pass")
    clean, recited = field("clean"), field("recited")
    return {tid: clean[tid] and not recited[tid] for tid in ids}


def fmt(x) -> str:
    x = float(x)
    return str(int(x)) if x == int(x) else f"{x:.4g}"


def report(export: dict, arms: list[tuple[str, list[str]]], metric: str, problems: str, paired: bool,
           prereg: dict | None, nboot: int, seed: int) -> tuple[list[str], dict]:
    lines, result = [], {"metric": metric, "problems": problems, "paired": paired}
    if len(arms) > 2:
        raise SystemExit("at most two arms: a registered look is one decision")
    panel_name, panel = panel_for(export, problems)
    lines.append(f"panel {panel_name}, metric {metric}" + (", paired by position" if paired else ""))
    result["panel"] = panel_name
    per_arm = {}
    for name, tags in arms:
        outcomes = {tag: tag_outcomes(panel, tag, metric) for tag in tags}
        counts = [sum(o.values()) for o in outcomes.values()]
        per_arm[name] = (tags, outcomes, counts)
        mean = Fraction(sum(counts), len(counts))
        seeds = f"{len(counts)} seed" + ("s" if len(counts) != 1 else "")
        lines.append(f"{name}: {fmt(mean)} [{min(counts)}-{max(counts)}] ({seeds})"
                     + ("   WARNING: under 10 seeds, section E asks for 10 or more" if len(counts) < 10 else ""))
        for tag, count in zip(tags, counts):
            lo, hi = wilson(count, len(panel["task_ids"]))
            lines.append(f"    {tag}: {count} of {len(panel['task_ids'])}, Wilson 95% [{lo:.2f}, {hi:.2f}]")
        best = ", ".join(f"n={n}: {float(expected_best_of(counts, n)):.2f}"
                         for n in sorted({1, 2, 5, 10, len(counts)} & set(range(1, len(counts) + 1))))
        lines.append(f"    expected best of n seeds (Dodge): {best}")
        result[name] = {"tags": tags, "counts": counts, "mean": float(mean)}
    if prereg is not None:
        for name, (tags, _o, _c) in per_arm.items():
            if len(tags) != prereg["seeds"]:
                raise SystemExit(f"prereg registers seeds: {prereg['seeds']}, arm {name} has {len(tags)} tags")
        for key, value in (("metric", metric), ("problems", problems)):
            if key in prereg and prereg[key] != value:
                raise SystemExit(f"prereg registers {key}: {prereg[key]}, this run asks for {value}")
    if len(arms) < 2:
        lines.append("one arm: nothing to compare")
        return lines, result
    (name_a, (tags_a, out_a, a)), (name_b, (tags_b, out_b, b)) = per_arm.items()
    if paired and len(a) != len(b):
        raise SystemExit("--paired needs two arms of the same size, paired by position")
    diff = Fraction(sum(b), len(b)) - Fraction(sum(a), len(a))
    if paired:
        p, mid_p = paired_permutation_test(a, b)
        test = "exact sign-flip permutation over paired seeds"
    else:
        p, mid_p = permutation_test(a, b)
        test = "exact permutation over seeds"
    lines.append(f"difference in means {name_b} - {name_a}: {fmt(diff)}; {test}: one-sided p = {float(p):.4f} "
                 f"({p.numerator}/{p.denominator}), mid-p = {float(mid_p):.4f}")
    pba = prob_outperform(a, b, paired)
    lo, hi = bootstrap_ci(a, b, paired, nboot, seed)
    lines.append(f"P({name_b} > {name_a}), ties 1/2: {float(pba):.3f}, bootstrap 95% [{lo:.3f}, {hi:.3f}] "
                 f"({nboot} resamples), threshold {GAMMA}")
    result.update({"difference": float(diff), "p": float(p), "p_exact": f"{p.numerator}/{p.denominator}",
                   "mid_p": float(mid_p), "prob_outperform": float(pba), "ci": [lo, hi]})
    single = len(a) == 1 and len(b) == 1
    if single:
        oa, ob = next(iter(out_a.values())), next(iter(out_b.values()))
        n12 = sum(ob[t] and not oa[t] for t in ob)
        n21 = sum(oa[t] and not ob[t] for t in oa)
        lines.append(f"two single checkpoints: McNemar n12={n12} ({name_b} only), n21={n21} ({name_a} only), "
                     f"exact two-sided p = {float(mcnemar_exact_two_sided(n12, n21)):.4f}, "
                     f"mid-p = {float(mcnemar_mid_p(n12, n21)):.4f}")
        result["mcnemar"] = {"n12": n12, "n21": n21, "mid_p": float(mcnemar_mid_p(n12, n21))}
    # the paired view: which problems any seed of either arm solved
    ids = [int(i) for i in panel["task_ids"]]
    rows = []
    for tid in ids:
        ka = sum(o[tid] for o in out_a.values())
        kb = sum(o[tid] for o in out_b.values())
        if ka or kb:
            rows.append((tid, ka, kb))
    lines.append(f"problems solved by any seed ({len(rows)}): " + "; ".join(
        f"{tid} {name_a} {ka}/{len(a)} {name_b} {kb}/{len(b)}" for tid, ka, kb in rows[:60])
        + (" ..." if len(rows) > 60 else ""))
    result["problems_solved"] = rows
    if single:
        decision = "INCONCLUSIVE"
        lines.append(f"verdict: {decision} (section E: never one run; McNemar compares these two checkpoints only)")
    else:
        decision = verdict(p, hi)
        lines.append(f"verdict: {decision}" + ("" if prereg is not None else " (unregistered, exploratory)"))
    result["verdict"] = decision
    result["registered"] = prereg is not None
    return lines, result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--outcomes", type=Path, required=True, help="written by score_heldout.py --outcomes")
    ap.add_argument("--arm", action="append", required=True, metavar="NAME=tag1,tag2,...",
                    help="the seeds of one recipe; first is the baseline, second the treatment")
    ap.add_argument("--paired", action="store_true", help="same corpus and seed list: sign-flip test")
    ap.add_argument("--prereg", type=Path, help="registration with a 'seeds: N' line")
    ap.add_argument("--metric", choices=METRICS, default="clean")
    ap.add_argument("--problems", choices=PROBLEM_SETS, default="decontam")
    ap.add_argument("--nboot", type=int, default=10_000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json", type=Path, help="also write the numbers here")
    a = ap.parse_args(argv)
    arms = []
    for spec in a.arm:
        name, sep, tags = spec.partition("=")
        if not sep or not name or not tags:
            raise SystemExit(f"--arm {spec!r}: want NAME=tag1,tag2,...")
        tag_list = [t for t in tags.split(",") if t]
        if len(set(tag_list)) != len(tag_list):
            raise SystemExit(f"--arm {name}: a tag is listed twice")
        arms.append((name, tag_list))
    if len({name for name, _ in arms}) != len(arms):
        raise SystemExit("two arms with one name")
    try:
        export = json.loads(a.outcomes.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise SystemExit(f"cannot read {a.outcomes}: {e}")
    if export.get("schema_version") not in (1, 2):
        raise SystemExit(f"{a.outcomes}: unsupported schema {export.get('schema_version')!r}")
    if a.metric != "clean" and export.get("schema_version") == 1:
        raise SystemExit(f"{a.outcomes}: schema 1 carries only clean; rescore with the current score_heldout.py")
    prereg = read_prereg(a.prereg) if a.prereg else None
    lines, result = report(export, arms, a.metric, a.problems, a.paired, prereg, a.nboot, a.seed)
    print("\n".join(lines))
    if a.json:
        a.json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
