# Where dawnr should head — landscape synthesis (2026-10-14)

Source: 14-dimension Haiku research sweep (ultracode, capped 25 agents; 14/14 completed,
0 errors, 198 works cited, 190 confirmed by fetch). Raw findings:
`RESEARCH-2026-10-14-landscape.json`.

## The one finding, stated plainly

dawnr's **core loop is not novel.** Checker-gated verified-data training, autoformalization,
RLVR-style filtering, "small model from curated data beats its size class", and "one spec,
many provers" all have extensive, fetched prior art:

| dawnr piece | prior art the sweep found |
|---|---|
| NL → formal spec | autoformalization; nl2postcond (FSE 2024) already scores specs by whether they catch real bugs |
| keep only verifier-accepted outputs as training data | STaR / ReST-EM / RFT / RLVR (DeepSeek-R1, Tulu-3) |
| small model from curated data | phi / Phi-4 / SmolLM2 |
| one spec → many provers | Why3, Boogie, SPARK, Aeneas, hax; AlgoVeri does 3 kernels (Dafny/Verus/Lean) |
| generate-check-repair | Self-Debugging, AlphaVerus, AutoSpec, Clover |
| checker-gated generation to cut hallucination | LLM-Modulo, Clover, AWS Automated Reasoning |
| a spec must *reject* a wrong program | nl2postcond, IronSpec, MutDafny, containment verification |

## What is actually unclaimed — dawnr's defensible ground

Across all 14 dimensions, the same four things come back as **not found in the literature**:

1. **Seven-kernel ALL-MUST-AGREE conjunction + one-edit twin refutation with a concrete
   witness**, as a measured spec-adequacy gate. The most anyone combines is 3 kernels
   (AlgoVeri); nobody requires cross-kernel agreement or a shared counterexample.
2. **A published false-accept / mutant-survival rate for the gate**, and a
   coverage-vs-accuracy (selective-prediction) curve with three-state verdicts
   (verified / refuted / unverifiable-with-reason). Nobody headlines an audited false-accept rate.
3. **A matched-budget verified-vs-raw per-parameter ablation.** Dimensions 3, 4, 7 and 9 each
   independently name this as the missing experiment. No multi-verifier training ablation exists.
4. **Honest refusal scored as its own outcome.** Every benchmark counts only success; refusal
   maps to selective prediction, which is unmeasured in this space.

## Recommendation: measure the gate you have; do not build new capability

Stop adding provers, proof-rate pushes, language features, or a from-scratch model. Turn the
twin-refutation seven-kernel gate into a measured, published result. Three experiments, in
increasing effort (do them in this order):

- **E1 — gate adequacy numbers (smallest; mostly instrumenting what exists).** One-edit
  refutation over the 426 pairs in `t/twins/` plus Vericoding/AlgoVeri specs. Report per-kernel
  disagreement, mutant-survival, false-accept rate, and three-state coverage. Deliverable:
  *an audited false-accept rate for a multi-prover spec gate* — nobody has one.
- **E2 — independence audit (medium; cheap, high-credibility).** Re-run the twin set under a
  second solver (cvc5 where kernels default to Z3) to measure how much of "seven *independent*
  kernels" is real vs shared SMT core. This either strengthens or honestly corrects the central
  premise.
- **E3 — matched-budget verified-vs-raw ablation (largest; the headline).** Pretrained
  Apache-2.0 base 0.5–1.5B (the ladder plan's choice), 3 seeds, equal token budget, matched
  solution diversity: raw-code SFT vs all-seven-verified vs graded k-of-7. Score pass@1/pass@k
  on the public Vericoding Dafny benchmark **and** twin survival. This answers dawnr's own
  central question, which the literature has not answered.

## Honest risks (directions, not blockers)

- **Yield is bounded by the weakest kernel.** All-must-agree passes only when every kernel
  passes; Vericoding shows a 55-point spread (Dafny 82% vs Lean 27%). Decide up front whether to
  report k-of-7 graded admission alongside 7-of-7, or accept low yield because the point is
  adequacy, not volume.
- **Independence is the premise's soft spot** — hence E2 before any "seven independent" claim.
- **The NL→verified-spec benchmark niche is crowded** (vericoding, VERINA, VerifyThisBench). Do
  not claim "first multi-verifier spec benchmark"; claim the *measured cross-kernel gate*.

## Positioning / career (the north star)

The market pays for this now (Harmonic, Axiom, AWS Automated Reasoning, Lean FRO, DARPA expMath),
but nearly everyone rests on **one** prover (Lean). Seven-kernel + twin + measured adequacy is the
differentiator **if measured**. Concrete leads from the sweep:

- Release the twin-refutation gate as a **standalone open checker** + a spec-adequacy benchmark.
- **ARIA Safeguarded AI Track 1** — agent flagged a deadline of 31 Oct 2026; **verify this date
  independently before relying on it.**
- **AMLAS assurance-case** for a code-level, PX4-relevant `t` module (e.g. a sensor-validity or
  failsafe-transition predicate — deliberately not a physical-safety claim). Ties dawnr to the
  PX4 work already in flight.
- **AlgoVeri's identical-contract format** (77 contracts, if released) as the public yardstick.

## De-prioritize

More proof-rate experiments, bigger models, new `t` language features, the from-scratch 93M model
(the 2026-10-01 bet audit already found that unsupported; the pretrained permissive base is right).
