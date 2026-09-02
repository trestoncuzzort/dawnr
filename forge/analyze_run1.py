#!/usr/bin/env python3
"""analyze_run1.py — the preregistered comparison, and nothing more than it.

Runs exactly the analysis fixed in data/prereg_track_a_run1.json BEFORE the
first replicate was scored: run-level greedy-free pass@1, Welch on each arm's
OWN standard deviation (never pooled), two-sided, alpha 0.05, fixed N = 40 per
arm.

Welch and not Student's t because pooling assumes the two arms have the same
variance, and the whole question is whether training changed the model -- a
change in spread is a change. Pooling would hide it in the denominator.

A paired per-task comparison is reported SECOND, as a secondary view. Both arms
see the identical frozen task set, so pairing removes between-task difficulty,
which is the largest source of variance here. It is secondary because the
preregistration named the run-level test as primary, and promoting whichever
test gives the better answer after seeing both is the exact move preregistration
exists to prevent.

No scipy on this machine, so the t distribution is implemented in stats_core.py
(extracted from this file 2026-08-31, behavior-preserving, output byte-identical;
one implementation, imported by everything that reports a p-value). Checked
against known values in main().

THREE THINGS THIS FILE USED TO GET WRONG, and what it does instead
------------------------------------------------------------------
1. POOLING ACROSS VERIFIERS. Rows were grouped by MODEL alone. The base arm
   'llama3:8b-instruct-q4_K_M' holds 10 rows banked before the verifier was
   pinned (verifier absent entirely, replicate counter 1..10) and 40 banked
   after it (CPython 3.11.9, replicate counter restarted at 1..40). Averaging
   them produced one "base mean" over two different instruments, and the gap it
   hid is 7.6 pp -- larger than every effect this file reports. Every arm is now
   partitioned by provenance.verifier_key(), the same key ruler_noise.py pools
   on; the base arm reports the pinned 40 as the reference and prints the
   pre-pin 10 separately under an explicit NOT-POOLABLE line. Because the
   replicate counter restarts per key, a run-order or drift statistic is only
   meaningful WITHIN one key, and there is deliberately none across keys here.
2. A METRIC LABEL THAT WAS TRUE OF ONLY TWO OF THE THREE ARMS. The header said
   "greedy-free run-level pass@1" over the whole report. It is true of the two
   compared arms, whose rows carry greedy=null and five sampled draws. The base
   arm's rows carry a greedy draw plus four sampled ones, and its banked
   aggregate INCLUDES the greedy draw. Both constructions are now computed for
   every arm and printed side by side, and the label on the banked aggregate is
   derived by comparing it against both -- checked, not asserted. Comparing is
   not enough BY ITSELF, though: the two constructions can come out equal, and
   the label then used to read that tie as proof that no greedy draw existed.
   Presence is a fact about the ROW SHAPE and is now read from the row shape --
   see has_greedy_draw() and stored_construction().
3. AN UNMEASURED TASK SCORED AS ZERO. The per-task view enumerated tasks from
   the trained arm only, so a task present in just the null arm was invisible;
   and a task whose `sampled` list was empty was averaged in as 0.0, which is
   the score of a task that was measured and failed everywhere. Tasks now come
   from the UNION of both arms, an entry with no sampled draws contributes
   nothing, a task with no measurement in either arm is excluded, and the
   excluded count is printed rather than absorbed.

AND A FOURTH, WHICH IS THE OTHER THREE ONE LEVEL UP
---------------------------------------------------
4. THE TWO COMPARED ARMS WERE NEVER CHECKED AGAINST EACH OTHER. Fix 1 made
   each arm one verifier key and said nothing about the two arms sharing
   it, so a trained arm scored on 3.11.9/win32 and a null arm scored on
   3.12.10/linux both cleared single_key() and the primary Welch ran across
   two instruments. Fix 2 derived each arm's construction label and said
   nothing about the two arms sharing that either, so a greedy-free trained
   arm against a greedy-anchored null arm printed "UNRECOGNISED (matches
   neither construction)" on the metric line and then reported a
   difference, a CI and a p-value underneath it. Three instances of one
   shape, so the fence is one level up rather than a third patch:
   require_commensurable() runs immediately before the comparison, derives
   what two arms must share from the ROW STRUCTURE rather than from those
   findings, and RAISES. A difference between two numbers that were not
   built the same way is not an effect, and a warning printed above one
   does not turn it into a comparison.
"""
from __future__ import annotations

import json
from pathlib import Path

from provenance import UNPINNED, is_pinned, verifier_key
from stats_core import (DegenerateInput, mean, paired, sd, t_crit, t_sf,
                        welch)

HERE = Path(__file__).resolve().parent
NOISE = HERE / "data" / "ruler_noise.jsonl"
TRAINED, NULL = "llama3-forged", "llama3-forged-null"
BASE = "llama3:8b-instruct-q4_K_M"
MDE_PP = 2.98          # preregistered minimum detectable effect
# Banked aggregates are rounded to 4 decimal places, so recomputing one can
# differ by up to 5e-5 (measured worst case across every retained row: 4.84e-5).
# The two constructions themselves differ by 5.0e-2 on the base arm, so this
# window tells them apart by a factor of 500 and cannot mislabel either.
_TOL = 1e-4


def _refuse_non_finite(token: str):
    """json.loads accepts the bare tokens NaN, Infinity and -Infinity by
    default, and a NaN rate survives every downstream comparison silently:
    `p < 0.05` and `p >= 0.05` are BOTH false against it, so a run that was
    never measured reads as one that was measured and found unremarkable.
    A banked replicate has no such value; if one appears, the file is wrong."""
    raise DegenerateInput(
        f"{NOISE}: a row carries the non-finite JSON token {token!r}. A "
        f"run-level rate is a measurement or it is absent; it is never NaN.")


def load() -> dict[str, list[dict]]:
    """Rows grouped by model. Grouping by model is NOT a pooling decision --
    partition() below supplies the key that is, and every statistic in main()
    is computed inside one of its groups."""
    out: dict[str, list[dict]] = {}
    with open(NOISE, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                r = json.loads(line, parse_constant=_refuse_non_finite)
                out.setdefault(r.get("model"), []).append(r)
    return out


def rate(row: dict) -> float:
    """The aggregate AS BANKED. What construction that is depends on the row --
    see stored_construction(); it is greedy-free for the two compared arms and
    greedy-anchored for the base arm."""
    agg = row["aggregate"]
    return agg["pass@1"] if isinstance(agg, dict) else float(agg)


def entries(r: dict) -> list[dict]:
    """per_task is a LIST of {tid, greedy, sampled} in the banked rows, but the
    earliest ones stored a mapping. Both shapes, one accessor."""
    pt = r["per_task"]
    return pt if isinstance(pt, list) else [dict(v, tid=k) for k, v in pt.items()]


def partition(rows: list[dict]) -> dict[tuple, list[dict]]:
    """Split one arm into the groups whose rows may legitimately be averaged."""
    out: dict[tuple, list[dict]] = {}
    for r in rows:
        out.setdefault(verifier_key(r), []).append(r)
    return out


def greedy_free_rate(row: dict) -> float | None:
    """Run-level pass@1 over the SAMPLED draws only. None when nothing in the
    row was sampled -- an unmeasured row has no rate, it does not have 0.0."""
    vals = [sum(e["sampled"]) / len(e["sampled"])
            for e in entries(row) if e.get("sampled")]
    return mean(vals) if vals else None


def greedy_anchored_rate(row: dict) -> float | None:
    """Run-level pass@1 counting the temp-0 greedy draw as one more draw, which
    is what eval.py banked before the greedy anchor was dropped."""
    vals = []
    for e in entries(row):
        s = list(e.get("sampled") or [])
        if e.get("greedy") is not None:
            s = [float(bool(e["greedy"]))] + s
        if s:
            vals.append(sum(s) / len(s))
    return mean(vals) if vals else None


def has_greedy_draw(rows: list[dict]) -> bool:
    """Does any row in this arm bank a temp-0 greedy draw?

    A question about the ROW SHAPE, and the row shape is the only thing that can
    answer it. Asked because the two constructions can come out numerically
    equal -- an arm that passed every draw scores 1.0 both ways -- and a tie
    between two numbers is not evidence that one of the inputs was absent.
    """
    return any(e.get("greedy") is not None for r in rows for e in entries(r))


def stored_construction(rows: list[dict]) -> str:
    """Which of the two the banked aggregate actually equals, decided by
    recomputing both and comparing -- so the label cannot drift off the data.

    WHERE COMPARING IS NOT ENOUGH. When the two constructions agree, the stored
    number cannot say which one produced it, and this used to print "greedy-free
    (no greedy draw was banked)" on that tie -- reading a numeric coincidence as
    proof of an absence. The executed witness: one row with greedy=True,
    sampled=[1, 1] and aggregate 1.0 is 1.0 under BOTH constructions and plainly
    HAS a banked greedy draw, and it got that label. Presence is a fact about
    the row shape, so on a tie the row shape decides: the stored value is
    reported as greedy-ANCHORED whenever any greedy draw is banked, because the
    anchored reading is then true of the number, and the claim of absence is
    made only when no row carries one.

    A stored value matching greedy-free and NOT greedy-anchored keeps the plain
    "greedy-free" label even where a greedy draw exists. There the number itself
    discriminates -- it says the draw was left out of the aggregate -- and that
    label asserts nothing about whether one was banked.
    """
    if not rows:
        return "no rows"
    free = all(v is not None and abs(rate(r) - v) <= _TOL
               for r, v in ((r, greedy_free_rate(r)) for r in rows))
    anch = all(v is not None and abs(rate(r) - v) <= _TOL
               for r, v in ((r, greedy_anchored_rate(r)) for r in rows))
    if free and not anch:
        return "greedy-free"
    if anch and not free:
        return "greedy-ANCHORED"
    if free and anch:
        if has_greedy_draw(rows):
            return ("greedy-ANCHORED (a greedy draw is banked; the two "
                    "constructions are indistinguishable on these rows)")
        return "greedy-free (no greedy draw was banked)"
    return "UNRECOGNISED (matches neither construction)"


def per_task_mean(rows: list[dict], tid: str) -> float | None:
    """Mean sampled rate for one task across an arm's rows.

    An entry with no sampled draws is NOT measured, so it contributes nothing.
    Scoring it 0.0 states that the model was asked and failed every time, which
    is a different claim from the one the data supports. None means the arm
    never measured this task at all.
    """
    vals = []
    for r in rows:
        for e in entries(r):
            if e.get("tid") != tid:
                continue
            s = e.get("sampled") or []
            if s:
                vals.append(sum(s) / len(s))
    return mean(vals) if vals else None


def _msd(v: list[float]) -> str:
    """mean and sd, with sd left blank at n=1 rather than dividing by zero."""
    return (f"mean {mean(v):.4f}   sd {sd(v):.4f}" if len(v) > 1
            else f"mean {mean(v):.4f}   sd n/a (n=1)")


def arm_block(label: str, rows: list[dict]) -> list[str]:
    """One arm's rates under both constructions, plus what was banked."""
    free = [v for v in (greedy_free_rate(r) for r in rows) if v is not None]
    anch = [v for v in (greedy_anchored_rate(r) for r in rows) if v is not None]
    st = [rate(r) for r in rows]
    out = [f"    {label}  n={len(rows)}"]
    out.append(f"      stored aggregate  {_msd(st)}"
               f"   [{stored_construction(rows)}]")
    if free:
        out.append(f"      greedy-free       {_msd(free)}")
    if anch:
        out.append(f"      greedy-anchored   {_msd(anch)}")
    return out


def single_key(name: str, rows: list[dict]) -> list[dict]:
    """The rows of an arm that must be one instrument. Refuses to average two.

    The preregistered comparison is between two checkpoints scored on ONE
    instrument. If an arm ever spans two verifier keys, the honest answer is
    not to pick one silently -- it is to stop and say so.
    """
    groups = partition(rows)
    if len(groups) > 1:
        print(f"\n  !! NOT-POOLABLE: arm {name} spans {len(groups)} verifier "
              f"keys and cannot be averaged into one number:")
        for k, v in sorted(groups.items(), key=lambda kv: str(kv[0])):
            print(f"       {k[0]}/{k[1]}  n={len(v)}  "
                  f"stored mean {mean([rate(r) for r in v]):.4f}")
        raise SystemExit(
            f"refusing to report a preregistered comparison over pooled "
            f"verifiers ({name})")
    return rows


# --- commensurability: the precondition the comparison rests on ----------
class Incommensurable(ValueError):
    """Two arms that are not measurements of the same thing.

    RAISED, NOT PRINTED, because both softer answers were already tried in
    this file and each one shipped a number. A warning above the result: the
    metric line printed UNRECOGNISED and the Welch block ran anyway. A check
    inside one arm that says nothing about the other: single_key(), which
    cleared a 3.11.9 arm and a 3.12.10 arm standing side by side. A
    difference between two numbers built by different instruments, or by
    different constructions, is not an effect, and there is no honest way to
    print one with a caveat attached.
    """


# THE DIMENSIONS, DERIVED FROM THE ROW STRUCTURE RATHER THAN LISTED.
# Hand-picking "the fields that matter" is the invented-scope mistake this
# project keeps paying for, so the set is read off the code and the data in
# three steps.
#
# STEP 1 -- what this file reads BY NAME, taken from its own accessors above
# rather than judged by eye:
#   model      load() groups on it. It IS the contrast: the two arms must
#              differ on it, and that is the only thing they may differ on.
#   aggregate  rate(). The measurement being compared.
#   per_task   entries(). The per-task measurements the label is built from.
# Their VALUES have to differ between arms -- that is the measurement -- so
# they are excluded from value comparison and checked on SHAPE in step 3.
#
# STEP 2 -- every OTHER key on the row describes the conditions under which
# the measurement was taken, and a run configuration is precisely what an
# arm holds CONSTANT across its replicates. So the data decides: a key is a
# dimension for an arm when the arm takes one value on it. A key that varies
# is per-replicate bookkeeping (ts, replicate) or a per-run count, and there
# is no single value on it to compare. Nothing is named here -- the rows'
# own key set supplies the candidates, and each arm's own data sorts them.
#
# STEP 3 -- the dimensions no single key carries, read off the accessors
# again: the verifier key (verifier_key(), the identity partition() already
# pools on), the aggregate's shape (rate() branches on dict-vs-number, and a
# bare number does not say which statistic it is), how many sampled draws
# stand behind each per-task rate, whether a greedy draw is banked at all
# (has_greedy_draw, a fact about the row shape), which construction the
# banked aggregate matches (stored_construction), and the set of task ids
# actually measured -- a run-level mean over a different task set is a
# different number.
_READ_BY_NAME = ("model", "aggregate", "per_task")
# `verifier` is dropped from step 2 and re-entered in step 3 as the DERIVED
# key. Raw equality would be STRICTER across two arms than partition() is
# within one -- the recorded dict also carries `executable` and
# `launcher_version` -- and one definition of "the same instrument", applied
# in both directions, is the whole point of the fix that produced
# verifier_key().
_DERIVED_INSTEAD = ("verifier",)
# Deliberately carries no COUNT. Two arms that both vary on a per-run
# measurement agree that it is not configuration; recording 39 values against
# 38 would turn that agreement into a refusal.
_VARIES = "<varies across this arm's rows>"


def context_dimensions(rows: list[dict],
                       keys: set[str]) -> dict[str, str] | None:
    """Step 2 for one arm: what it holds constant, over the given key set.

    None when the arm has fewer than two rows. With a single row every key is
    trivially constant -- ts and replicate included -- so the
    constant-versus-varying split stops meaning anything, and refusing
    because two arms carry different timestamps would be a refusal for a
    false reason. welch() rejects a one-row arm on its own terms
    (stats_core._sample, minimum 2), so no p-value escapes there either way.
    """
    if len(rows) < 2:
        return None
    out: dict[str, str] = {}
    for k in sorted(keys):
        vals = {json.dumps(r.get(k), sort_keys=True) for r in rows}
        out[k] = vals.pop() if len(vals) == 1 else _VARIES
    return out


def shape_dimensions(rows: list[dict]) -> dict[str, str]:
    """Step 3 for one arm: the dimensions no single row key carries."""
    es = [e for r in rows for e in entries(r)]
    agg = sorted({"a bare number (unlabelled)"
                  if not isinstance(r["aggregate"], dict)
                  else "{" + ", ".join(sorted(r["aggregate"])) + "}"
                  for r in rows})
    tids = sorted({e["tid"] for e in es})
    return {
        "verifier key (provenance.verifier_key)":
            ", ".join(sorted(f"{k[0]}/{k[1]}"
                             for k in {verifier_key(r) for r in rows})),
        "aggregate shape (what rate() reads)": ", ".join(agg),
        "sampled draws behind each per-task rate":
            ", ".join(str(n) for n in
                      sorted({len(e.get("sampled") or []) for e in es})),
        "greedy draw banked (row shape)": str(has_greedy_draw(rows)),
        "stored aggregate construction": stored_construction(rows),
        "measured task ids": f"{len(tids)}: {', '.join(tids)}",
    }


def require_commensurable(a_name: str, a_rows: list[dict],
                          b_name: str, b_rows: list[dict]) -> None:
    """Refuse the comparison unless the two arms were measured the same way.

    Runs immediately before the primary Welch. The dimensions are derived in
    the three steps documented above; this function only applies them and
    reports which one differs, with both values.

    WHAT THIS DOES NOT COVER, stated because a check that overstates its
    reach is worse than no check:
      - A key that VARIES within either arm is not a dimension for it: the
        arm has no single value on it, so there is nothing to compare.
        Within-arm heterogeneity is a different defect, and only the verifier
        key is policed for it (single_key()). Re-run half of one arm at
        another temperature and `temp` stops being configuration for that
        arm -- though the two arms then disagree about whether it is
        configuration at all, and THAT is reported.
      - Arms of fewer than two rows: step 2 is skipped entirely, because the
        classification is undefined there. welch() refuses those inputs, so
        no p-value is printed regardless.
      - It compares DECLARED metadata. A row recording temp 0.8 that was
        actually sampled at 0.2 is invisible here. What this certifies is
        that the two arms describe themselves identically, not that either
        description is true.
      - It cannot see a difference nothing records. No row carries the
        decoding seed, the prompt template, the adapter rank or the
        quantisation, so two arms differing in any of those read as
        commensurable.
      - per_task's CONTAINER (list versus mapping) is deliberately not a
        dimension: entries() normalises both to the same entries, so it
        cannot move a number.
      - It says nothing about whether these are the RIGHT two arms to compare
        -- the preregistration decides that -- and nothing about the base
        arm, which never enters the comparison.
      - stored_construction is compared as a LABEL, decided at _TOL = 1e-4.
        Two arms agreeing on it agree to that tolerance and no finer.
    """
    for name, rows in ((a_name, a_rows), (b_name, b_rows)):
        label = stored_construction(rows)
        if not label.startswith(("greedy-free", "greedy-ANCHORED")):
            raise Incommensurable(
                f"arm {name}: its banked aggregate is {label}. Which "
                f"construction produced the stored number is unknown, so "
                f"it cannot be matched against the other arm's -- and that "
                f"is the state the metric line used to print before "
                f"reporting a difference underneath it.")

    dims: dict[str, tuple[str, str]] = {}
    a_shape, b_shape = shape_dimensions(a_rows), shape_dimensions(b_rows)
    for k in a_shape:
        dims[k] = (a_shape[k], b_shape[k])

    keys = ({k for r in a_rows + b_rows for k in r}
            - set(_READ_BY_NAME) - set(_DERIVED_INSTEAD))
    a_ctx = context_dimensions(a_rows, keys)
    b_ctx = context_dimensions(b_rows, keys)
    if a_ctx is not None and b_ctx is not None:
        for k in sorted(keys):
            dims[f"row field {k!r}"] = (a_ctx[k], b_ctx[k])

    differ = {k: v for k, v in dims.items() if v[0] != v[1]}
    if not differ:
        return
    detail = "".join(f"\n  {k}\n      {a_name}: {av}\n      {b_name}: {bv}"
                     for k, (av, bv) in differ.items())
    raise Incommensurable(
        f"{a_name} and {b_name} are not commensurable: they differ on "
        f"{len(differ)} of the {len(dims)} dimensions the primary "
        f"comparison's validity rests on. Welch would report the difference "
        f"between two numbers that were not built the same way, which is not "
        f"an effect." + detail)


def main() -> int:
    # Self-check the t implementation before trusting a p-value from it.
    assert abs(t_crit(10) - 2.228) < 0.002, t_crit(10)
    assert abs(t_crit(78) - 1.991) < 0.003, t_crit(78)
    assert abs(2 * t_sf(2.0, 30) - 0.0546) < 0.001, 2 * t_sf(2.0, 30)

    by = load()
    tr_rows = single_key(TRAINED, by.get(TRAINED, []))
    nu_rows = single_key(NULL, by.get(NULL, []))
    # Each arm is one instrument by now; nothing yet says the two arms are
    # the SAME instrument, or that their banked aggregates were built the
    # same way. Raises rather than warns -- see require_commensurable().
    require_commensurable(TRAINED, tr_rows, NULL, nu_rows)
    tr = [rate(r) for r in tr_rows]
    nu = [rate(r) for r in nu_rows]

    print("=" * 66)
    print("  RUN 1 RE-SCORE - the preregistered comparison")
    print("=" * 66)
    print(f"  metric   : run-level pass@1 -- compared arms: "
          f"{stored_construction(tr_rows + nu_rows)}")
    print(f"  arms     : trained={len(tr)}  null={len(nu)}   (prereg: 40 each)")
    if len(tr) != 40 or len(nu) != 40:
        print("  !! N does not match the preregistration; reporting anyway.")

    print(f"\n  trained  mean {mean(tr):.4f}   sd {sd(tr):.4f}")
    print(f"  null     mean {mean(nu):.4f}   sd {sd(nu):.4f}")

    ba_groups = partition(by.get(BASE, []))
    if ba_groups:
        pinned = {k: v for k, v in ba_groups.items() if is_pinned(k)}
        other = {k: v for k, v in ba_groups.items() if not is_pinned(k)}
        print("\n  base     (reference only; never enters the comparison)")
        if len(pinned) == 1:
            (k, v), = pinned.items()
            for ln in arm_block(f"reference, verifier {k[0]}/{k[1]}", v):
                print(ln)
        else:
            for k, v in sorted(pinned.items(), key=lambda kv: str(kv[0])):
                for ln in arm_block(f"verifier {k[0]}/{k[1]}", v):
                    print(ln)
            if len(pinned) > 1:
                print("    !! more than one pinned verifier; no single "
                      "reference named.")
        for k, v in sorted(other.items(), key=lambda kv: str(kv[0])):
            print(f"    NOT-POOLABLE with the reference above -- these rows "
                  f"were banked before the verifier was pinned ({UNPINNED}),")
            print(f"    their replicate counter restarts at 1, and no "
                  f"run-order statistic spans the two groups:")
            for ln in arm_block(f"pre-pin, verifier {k[0]}/{k[1]}", v):
                print(ln)

    w = welch(tr, nu)
    pp = w["diff"] * 100
    print("\n  PRIMARY - Welch, two-sided, unpooled")
    print(f"    difference   {pp:+.2f} pp   (trained minus null)")
    print(f"    95% CI       [{w['ci'][0]*100:+.2f}, {w['ci'][1]*100:+.2f}] pp")
    print(f"    t = {w['t']:.3f}   df = {w['df']:.1f}   p = {w['p']:.4f}")
    print(f"    prereg MDE   {MDE_PP:.2f} pp -> "
          f"{'CLEARS' if abs(pp) >= MDE_PP else 'does NOT clear'}")
    print(f"    at alpha .05 -> "
          f"{'SIGNIFICANT' if w['p'] < 0.05 else 'not significant'}")

    # Secondary: pair by task. Both arms see the same frozen task set, so the
    # task list is their UNION -- taking it from one arm makes a task the other
    # arm alone measured disappear instead of being reported as unpaired.
    tasks = sorted({e["tid"] for r in tr_rows + nu_rows for e in entries(r)})
    ta = [per_task_mean(tr_rows, t) for t in tasks]
    tb = [per_task_mean(nu_rows, t) for t in tasks]
    keep = [(x, y) for x, y in zip(ta, tb) if x is not None and y is not None]
    dropped = [t for t, x, y in zip(tasks, ta, tb) if x is None or y is None]
    if len(keep) > 2:
        p = paired([x for x, _ in keep], [y for _, y in keep])
        print(f"\n  SECONDARY - paired by task (n={len(keep)} tasks)")
        print(f"    difference   {p['diff']*100:+.2f} pp")
        print(f"    95% CI       [{p['ci'][0]*100:+.2f}, "
              f"{p['ci'][1]*100:+.2f}] pp")
        print(f"    t = {p['t']:.3f}   df = {p['df']}   p = {p['p']:.4f}")
        print(f"    excluded {len(dropped)} of {len(tasks)} tasks as unmeasured "
              f"in at least one arm"
              + (f": {', '.join(dropped)}" if dropped else ""))

    print("\n  WHAT THIS CANNOT SHOW: one checkpoint per arm. Zero training-seed")
    print("  variance by construction, so this cannot support a claim about DPO")
    print("  at any k. A look, not a verdict.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
