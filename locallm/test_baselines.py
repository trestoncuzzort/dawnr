"""Tests for baselines.py. `python test_baselines.py`, no framework.

THE CLAIM UNDER TEST is not "the arithmetic runs". It is that these numbers can
tell a model that learned something from one that did not — which is the whole
reason the file exists. So the tests below are ordered by how much they would
hurt if they were wrong:

  1. the baselines rank in the only order they can (uniform worst, longer
     context better) — if this breaks, every comparison built on it is noise;
  2. on text with STRUCTURE the n-gram beats letter frequency by a wide margin,
     and on text with NONE they converge — this is the red witness: a broken
     n-gram that ignored its context would pass test 1 and fail here;
  3. `closed_fraction` goes NEGATIVE when the "model" is worse than the lookup
     table, because a comparison that cannot deliver bad news is decoration;
  4. an INELIGIBLE holdout publishes no claim at all — not the verdict, not the
     arm-to-arm comparisons, not a field invented after this test was written.
     That last one is the point of section 6: the claim set is derived from the
     payload, so the test can be wrong about the fields and still be right
     about the rule.

Section 6 imports the two experiment modules, and through them torch, because
the thing under test is the declaration each experiment ships. A test that
re-declared the payload shape here would pass while the experiments published
whatever they liked.
"""
import math
import random
import sys

import baselines
import exp_steps_tail
import exp_steps_vs_quality

FAILS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    if detail:
        print(f"         {detail}")
    if not ok:
        FAILS.append(name)


def structured_text(n: int = 60_000) -> str:
    """Repetitive, strongly-ordered text: a trigram should do very well here."""
    words = ["the cat sat on the mat. ", "the dog ran to the park. ",
             "a boy saw the cat. ", "the girl ran home. "]
    rng = random.Random(1337)
    return "".join(rng.choice(words) for _ in range(n // 20))


def unstructured_text(n: int = 60_000) -> str:
    """Same characters, no order at all: context cannot help, so the n-gram
    should collapse toward the frequency model."""
    rng = random.Random(1337)
    src = structured_text(n)
    chars = list(src)
    rng.shuffle(chars)
    return "".join(chars)


def split(text: str) -> tuple[str, str, int]:
    cut = int(len(text) * 0.9)
    return text[:cut], text[cut:], len(set(text))


print("Scoring dumb models against each other, so 'your model learned something'")
print("is a comparison rather than an assertion.\n")

# ---------------------------------------------------------------- 1. ordering
tr, va, V = split(structured_text())
uni = baselines.uniform_nats(V)
freq = baselines.frequency_nats(tr, va, V)
bi = baselines.ngram_nats(tr, va, V, order=2)
tri = baselines.ngram_nats(tr, va, V, order=3)

check("uniform is the worst possible reference", uni > freq,
      f"uniform {uni:.4f} > frequency {freq:.4f} nats")
check("knowing the previous character beats knowing none", freq > bi,
      f"frequency {freq:.4f} > bigram {bi:.4f} nats")
check("knowing two characters beats knowing one", bi > tri,
      f"bigram {bi:.4f} > trigram {tri:.4f} nats")
check("uniform equals log(vocab) exactly", abs(uni - math.log(V)) < 1e-12,
      f"log({V}) = {math.log(V):.6f}")

# --------------------------------------------------- 2. RED WITNESS: context
# A trigram that ignored its context would still rank below frequency on
# test 1 (more smoothing mass), so test 1 alone does not prove it reads the
# context. This does: the SAME characters, shuffled, must destroy its edge.
s_tr, s_va, s_V = split(structured_text())
u_tr, u_va, u_V = split(unstructured_text())
edge_structured = baselines.frequency_nats(s_tr, s_va, s_V) - \
    baselines.ngram_nats(s_tr, s_va, s_V)
edge_shuffled = baselines.frequency_nats(u_tr, u_va, u_V) - \
    baselines.ngram_nats(u_tr, u_va, u_V)
check("the n-gram's advantage comes from CONTEXT, not from smoothing",
      edge_structured > 0.5 and edge_structured > edge_shuffled * 3,
      f"advantage over frequency: structured {edge_structured:.4f} nats, "
      f"same characters shuffled {edge_shuffled:.4f} nats")

# ------------------------------------------- 3. it must be able to say 'worse'
good = baselines.compare(s_tr, s_va, s_V, model_val_nats=tri * 0.5)
bad = baselines.compare(s_tr, s_va, s_V, model_val_nats=tri * 2.0)
check("a model better than the lookup table closes a positive fraction",
      good["closed_fraction"] > 0,
      f"closed_fraction = {good['closed_fraction']:+.3f}")
check("a model WORSE than the lookup table reports negative, not zero",
      bad["closed_fraction"] < 0,
      f"closed_fraction = {bad['closed_fraction']:+.3f}")
check("the bad-news path says so in words",
      any("WORSE" in ln for ln in baselines.summary_lines(bad)),
      [ln.strip() for ln in baselines.summary_lines(bad) if "WORSE" in ln][:1])

# ----------------------------------------------------------- 4. unit sanity
row = good["model"]
check("bits/char is nats/char divided by ln 2",
      abs(row["bits_per_char"] - row["nats_per_char"] / math.log(2)) < 1e-12)
check("'choices' is exp of the loss, matching the studio's plot",
      abs(row["choices"] - math.exp(row["nats_per_char"])) < 1e-9)

# ------------------------------------------------------------- 5. edge cases
check("an empty holdout does not divide by zero",
      isinstance(baselines.ngram_nats("abcabc", "", 3), float))
check("a corpus shorter than the context falls back to uniform",
      abs(baselines.ngram_nats("ab", "ab", 3) - baselines.uniform_nats(3)) < 1e-12)

# ------------------------------- 6. an ineligible holdout makes NO claim at all
# The failure this section exists for has been found three times: a run prints
# why it cannot be trusted and then publishes the ordinary affirmative result.
# The first fix nulled closed_fraction; the verdict, the comparisons and the run
# log row went on saying "longer training measurably helps" beside it.
WHY = ("this corpus cannot support the requested split: no whole-document "
       "split of it gets near the request")

# The seams this section tests, checked BEFORE they are used. Without this the
# file dies on an AttributeError against any version that does not have them,
# and a traceback is a worse failure report than a line that names what is
# missing. It stops rather than skipping: a section that quietly did not run
# would be the false green this whole file exists to prevent.
MISSING = ([f"baselines.{n}" for n in ("withhold_claims", "claims_in")
            if not hasattr(baselines, n)]
           + [f"{m.__name__}.{n}"
              for m in (exp_steps_vs_quality, exp_steps_tail)
              for n in ("summarise", "compare_arms", "verdict_of", "payload_of",
                        "PAYLOAD_DATA", "RECORD_DATA")
              if not hasattr(m, n)])
check("the gate and the payload builders are where this section tests them",
      not MISSING, f"missing: {MISSING}" if MISSING else "")
if MISSING:
    print(f"\n{len(FAILS)} failed: {', '.join(FAILS)}")
    sys.exit(1)

# A baseline table WITH a model row, so `baseline.closed_fraction` exists. No
# experiment declares that path -- compare() adds it only when it is given a
# model loss -- and it must be withheld anyway. That is the fail-closed
# direction, tested on a real field rather than an imagined one.
base = baselines.compare(s_tr, s_va, s_V, model_val_nats=tri * 0.5)
ng = base[f"ngram_{baselines.NGRAM_ORDER}"]["choices"]
ARMS = {"100": [2.10, 2.12], "200": [1.90, 1.91], "400": [1.70, 1.71]}


def steps_payload(reason):
    summary = {k: exp_steps_vs_quality.summarise(v, ng, reason)
               for k, v in ARMS.items()}
    comps = exp_steps_vs_quality.compare_arms(summary, list(ARMS))
    return exp_steps_vs_quality.payload_of(
        base, summary, comps, exp_steps_vs_quality.verdict_of(comps),
        "cpu", 1.0, reason)


ok_run, gated = steps_payload(None), steps_payload(WHY)

check("an eligible run publishes its verdict, unchanged",
      ok_run["verdict"] == "longer training measurably helps"
      and len(ok_run["comparisons"]) == 2 and ok_run["claims_withheld"] == []
      and ok_run["holdout_eligible"] is True,
      f"verdict {ok_run['verdict']!r}, {len(ok_run['comparisons'])} comparisons")

check("an ineligible run publishes NO verdict and NO comparison",
      gated["verdict"] is None and gated["comparisons"] is None,
      f"verdict {gated['verdict']!r}, comparisons {gated['comparisons']!r}")

check("...and the reason is what stands where they were",
      gated["ineligible_reason"] == WHY and gated["holdout_eligible"] is False
      and {"verdict", "comparisons"} <= set(gated["claims_withheld"]),
      f"withheld: {', '.join(gated['claims_withheld'])}")

check("...while every reading survives, because it is what happened",
      all(gated["arms"][k]["seeds"] == v and
          gated["arms"][k]["mean"] == ok_run["arms"][k]["mean"] and
          gated["arms"][k]["spread"] == ok_run["arms"][k]["spread"]
          for k, v in ARMS.items())
      and gated["baseline"]["ngram_3"]["choices"] == ng,
      f"arms {sorted(gated['arms'])} keep seeds, mean, spread and choices")

# RED WITNESS for the mechanism rather than the list: two claim-bearing fields
# no declaration mentions. `baseline.closed_fraction` is real and shipped;
# `how_sure_we_are` is the field someone adds next year without reading this.
check("a claim NOBODY DECLARED is withheld anyway",
      gated["baseline"]["closed_fraction"] is None
      and "baseline.closed_fraction" in gated["claims_withheld"],
      f"baseline.closed_fraction was {base['closed_fraction']:+.3f} before the "
      f"gate and is declared nowhere")

invented = baselines.withhold_claims(
    {"device": "cpu", "wall_s": 1.0, "how_sure_we_are": 0.99},
    WHY, exp_steps_vs_quality.PAYLOAD_DATA)
check("...including one invented after this test was written",
      invented["how_sure_we_are"] is None
      and "how_sure_we_are" in invented["claims_withheld"]
      and invented["device"] == "cpu",
      f"withheld {invented['claims_withheld']}, kept device and wall_s")

check("the withheld set is DERIVED from the payload, not listed beside it",
      baselines.claims_in(ok_run, exp_steps_vs_quality.PAYLOAD_DATA)
      == ["arms.100.closed_fraction", "arms.200.closed_fraction",
          "arms.400.closed_fraction", "baseline.closed_fraction",
          "comparisons", "verdict"],
      "; ".join(baselines.claims_in(ok_run, exp_steps_vs_quality.PAYLOAD_DATA)))

# The run log row is the same surface in miniature, and it is the one a reviewer
# reads months later without the result file in front of him.
row = baselines.withhold_claims({"verdict": "longer training measurably helps",
                                 "wall_s": 12.5},
                                WHY, exp_steps_vs_quality.RECORD_DATA)
check("the run log row withholds the verdict too, and says why",
      row["verdict"] is None and row["wall_s"] == 12.5
      and row["ineligible_reason"] == WHY,
      f"metrics: {row}")

# And the tail experiment, whose payload has a different shape and the same rule.
TAIL_ARMS = {"1000": [{"train": 1.50, "val": 1.90}, {"train": 1.51, "val": 1.91}],
             "2000": [{"train": 1.20, "val": 1.95}, {"train": 1.21, "val": 1.96}]}


def tail_payload(reason, partial=False):
    summary = {k: exp_steps_tail.summarise(v, int(k), 100_000, ng, reason)
               for k, v in TAIL_ARMS.items()}
    comps = exp_steps_tail.compare_arms(summary, list(TAIL_ARMS))
    return exp_steps_tail.payload_of(
        base, summary, "cpu", 1.0, reason, partial=partial,
        comparisons=comps, verdict=exp_steps_tail.verdict_of(comps))


tail_ok, tail_gated = tail_payload(None), tail_payload(WHY)
check("the tail experiment answers the same way on the same rule",
      tail_ok["verdict"].startswith("TAIL FOUND")
      and tail_gated["verdict"] is None and tail_gated["comparisons"] is None
      and tail_gated["arms"]["2000"]["mean_gap"] == tail_ok["arms"]["2000"]["mean_gap"],
      f"eligible: {tail_ok['verdict'][:40]}...; ineligible: "
      f"{tail_gated['verdict']!r}, gap reading kept")

check("a partial tail file has no verdict KEY, which is not the same as null",
      "verdict" not in tail_payload(None, partial=True)
      and "comparisons" not in tail_payload(WHY, partial=True),
      "not computed yet and withheld are different facts")

print()
if FAILS:
    print(f"{len(FAILS)} failed: {', '.join(FAILS)}")
else:
    print("=" * 64)
    print("all tests pass — and the n-gram's edge survives only on ordered text")
    print("=" * 64)
sys.exit(1 if FAILS else 0)
