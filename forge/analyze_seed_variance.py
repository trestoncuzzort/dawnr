#!/usr/bin/env python3
"""analyze_seed_variance.py — where training-seed variance actually lives, measured.

OPEN-ITEMS has carried this since council #17: `se_diff = sqrt(2)*run_sd` has no
slot for TRAINING-SEED variance — the null arm is one checkpoint, so it has zero
seed variance by construction, and one checkpoint cannot support a claim about
DPO at any k (Dodge et al. 2020, Bouthillier et al. 2021). The fix was always
"measure it"; the data to measure it with has been sitting in
data/ruler_noise.jsonl since the hc-seed campaign: same recipe, different
training seed, scored on the frozen ruler under the pinned verifier.

WHAT THIS COMPUTES
------------------
1. Per-seed mean and sd of run-level greedy-free pass@1, for every hc-seed arm
   with the FULL 40 replicates (partial arms are listed and excluded — mixing a
   5-replicate arm into a variance decomposition weights it as if it were 40).
2. The decomposition: within-seed variance (replicate noise on one checkpoint)
   vs between-seed variance of arm means, and the method-of-moments seed
   component  sigma^2_seed = max(0, var(seed means) - within/40).
3. The 55 pairwise Welch tests between full arms, and the empirical rejection
   rate at alpha .05. Under the hypothesis the paper's Table 2b supports —
   the data determine the function, seeds only choose coordinates — every pair
   is a true null, and this rate is an IN-SYSTEM empirical false-positive rate
   for the replicate-only test in the presence of whatever seed variance
   actually exists.

HONEST LIMITS, stated first:
  - The hc-seed campaign was unpreregistered exploration. These numbers SIZE
    Run 2's design; they are not themselves a confirmatory result.
  - The 55 pairs share 11 arms, so they are not independent tests; the
    rejection count is descriptive, not a calibrated binomial draw.
  - sigma_seed here is seed variance of THIS recipe on THIS instrument. It does
    not transfer to other systems — that non-transfer is exactly why the
    locallm-surrogate proposal was killed (ROADMAP.md, graveyard).

Output is printed and banked to council/seed_variance_decomposition.txt. The
directory is CREATED here rather than assumed: council/ is gitignored, so on a
fresh clone it does not exist, and the script used to print the entire report
and then die on write() with a FileNotFoundError and exit 1. Everything looked
right on screen and nothing was banked, which is the worst of the two failures
it could have had.

The three divisions below are guarded for the same reason. Each one is a ratio
whose denominator is a measured variance or a count of pairs, and each becomes
0/0 on inputs this script can actually be handed: one full arm (no
between-seed term exists), or arms with no replicate variance at all.
"""
from __future__ import annotations

import json
from pathlib import Path

from analyze_run1 import load, rate
from stats_core import DegenerateInput, mean, sd, welch

HERE = Path(__file__).resolve().parent
OUT = HERE / "council" / "seed_variance_decomposition.txt"
FULL_N = 40


def main() -> int:
    by = load()
    arms = {m: [rate(r) for r in rows] for m, rows in by.items()
            if m and m.startswith("hc-seed")}
    full = {m: v for m, v in sorted(arms.items()) if len(v) == FULL_N}
    partial = {m: len(v) for m, v in sorted(arms.items()) if len(v) != FULL_N}

    lines: list[str] = []
    say = lines.append
    say("SEED-VARIANCE DECOMPOSITION — hc-seed campaign, frozen ruler, pinned verifier")
    say("=" * 78)
    say(f"arms with the full {FULL_N} replicates: {len(full)} "
        f"({', '.join(full)})")
    say(f"excluded partial arms: "
        + (", ".join(f"{m} (n={n})" for m, n in partial.items()) or "none"))
    say("")
    say(f"{'seed':12} {'mean':>8} {'sd':>8}")
    for m, v in full.items():
        say(f"{m:12} {mean(v):8.4f} {sd(v):8.4f}")

    say("")
    if len(full) < 2:
        say("decomposition: NOT COMPUTED. A between-seed term needs at least "
            "two full")
        say(f"arms and {len(full)} was found. There is no variance of seed "
            f"means over one")
        say("seed, and a decomposition reported from one arm would be a "
            "number with no")
        say("second observation behind it.")
    else:
        means = [mean(v) for v in full.values()]
        within_var = mean([sd(v) ** 2 for v in full.values()])
        between_var = sd(means) ** 2
        expected_under_null = within_var / FULL_N
        seed_var = max(0.0, between_var - expected_under_null)
        say("decomposition (method of moments):")
        say(f"  within-seed sd (replicate noise, one checkpoint)   {within_var ** 0.5:.4f}")
        say(f"  observed sd of the {len(full)} seed means           "
            f"        {between_var ** 0.5:.4f}")
        say(f"  expected sd of means if seeds did not matter        "
            f"       {expected_under_null ** 0.5:.4f}   (within/sqrt({FULL_N}))")
        say(f"  seed component  sigma_seed                          "
            f"       {seed_var ** 0.5:.4f}")
        # 0/0 when the arms have no replicate variance AND no spread between
        # them: the share of a total variance of zero is not 0, it is undefined.
        share_den = seed_var + expected_under_null
        say(f"  variance share  sigma^2_seed / (sigma^2_seed + within/{FULL_N})"
            + (f"   {seed_var / share_den:.3f}" if share_den else
               "   undefined (total variance is exactly 0)"))

    names = list(full)
    rejections, ps, undefined = 0, [], []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            try:
                w = welch(full[names[i]], full[names[j]])
            except DegenerateInput as e:
                # Two arms with no replicate variance have no Welch t. Counting
                # such a pair as "not rejected" would push the empirical rate
                # down with a test that was never run.
                undefined.append((names[i], names[j], str(e)))
                continue
            ps.append((w["p"], names[i], names[j], w["diff"]))
            rejections += w["p"] < 0.05
    ps.sort()
    say("")
    say(f"pairwise Welch between full arms: {len(ps) + len(undefined)} pairs, "
        f"alpha .05")
    if ps:
        say(f"  rejections: {rejections}/{len(ps)}  "
            f"(empirical rate {rejections / len(ps):.3f}; nominal .05 if seeds do not matter)")
        say(f"  smallest p: " + ", ".join(
            f"{a} vs {b} p={p:.4f} ({d * 100:+.2f} pp)" for p, a, b, d in ps[:3]))
    else:
        say("  no pair yielded a defined test, so there is no rejection rate.")
    if undefined:
        say(f"  {len(undefined)} pair(s) UNDEFINED and excluded from the rate: "
            + ", ".join(f"{a} vs {b}" for a, b, _ in undefined[:3])
            + (" ..." if len(undefined) > 3 else ""))
    say("")
    say("WHAT THIS CANNOT SHOW: the campaign was unpreregistered exploration, the")
    say("55 pairs share 11 arms, and sigma_seed does not transfer off this system.")
    say("It sizes Run 2; it settles nothing by itself.")

    text = "\n".join(lines) + "\n"
    print(text, end="")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    try:
        shown = OUT.relative_to(HERE)
    except ValueError:      # OUT pointed outside the tree; show it in full
        shown = OUT
    print(f"[banked to {shown}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
