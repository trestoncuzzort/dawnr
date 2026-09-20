# Generating a formal specification from natural-language intent

Fetched 2026-09-20. **Recovered from a finished agent that returned its report
without writing this file** — the lesson is in the handoff. Ratings are for this
repo: a small language with an executable interpreter, seven proof systems,
per-problem unit tests, and a reference solution per problem.

## The highest-value cluster: grading a spec by running it

**Verus-SpecGym: An Agentic Environment for Evaluating Specification
Autoformalization** — 2026, [arXiv:2605.26457](https://arxiv.org/abs/2605.26457).
Verus-SpecBench, 581 spec-writing tasks from Codeforces, plus an agentic
environment. The core contribution is an **executable-specification evaluator**:
a generated spec compiles to runnable Rust and is executed against official
tests plus adversarial Codeforces "hacks". No reference spec, no LLM judge.
Gemini 3.1 Pro 77.8%; frontier 51.1-57.8%; open-source 21.5-25.5%.
**LLM-as-a-judge misses 26% of the failures the executable evaluator catches.**
*HIGH — closest paper to our architecture; compile each candidate spec to a
predicate over (input, output) in our interpreter and run it.*

**How Powerful Are LLMs in Generating Formal Program Specifications? (Coins)** —
ICML 2026, [arXiv:2608.13077](https://arxiv.org/html/2608.13077). Rocq-based,
four stages: syntax → first-case acceptance → **Passall** → **Rejectall**. 164
HumanEval problems, 1,640 mutation-derived negatives, ~756 positives/problem.
Rejectall: Gemini 3 Pro 28.05%, GPT-5 15.24%, Claude 4.5 Opus 14.63%, GPT-4o
4.27%, DeepSeek-V3.1 1.22%. Gemini drops 60.98% → 28.05% from first-case to
all-cases. Ablation: better verification +3.05%, better specs +5.01%.
*HIGH — already partly implemented here as `spec_check.mutations` (Rejectall on
outputs) and `check_points` (Passall on the problem's own assertions).*

**CodeSpecBench** — 2026, [arXiv:2604.12268](https://arxiv.org/html/2604.12268v1).
Specs as **executable Python pre/postcondition functions**, no prover. Scores
*correctness* (accepts valid) and *completeness* (rejects invalid) jointly.
2,494 LeetCode tasks, 217.8 tests/task. GPT-5-mini 47.0%, Gemini-2.5-Pro 46.2%.
**Code generation pass rates are 3-4x the spec pass rates for the same models.**
*HIGH — report the code-vs-spec gap as a headline number.*

**VeriContest** — 2026, [arXiv:2605.08553](https://arxiv.org/abs/2605.08553).
946 LeetCode/Codeforces problems in Rust/Verus with **paired positive and
negative test suites** used as a postcondition-completeness layer. Across 10
models: code 92.18% → **spec 48.31%** → proof 13.95% → end-to-end 5.29%.
*HIGH — the four-stage cascade is a good reporting skeleton.*

**VeriEquivBench** — [arXiv:2510.06296](https://arxiv.org/abs/2510.06296). An
**equivalence score**: the verifier confirms code satisfies spec, AND a
generated `Check_*_Spec` proves the spec *tightly* describes the code for all
inputs. Underspecified specs score zero. 2,389 problems. Claude-4-sonnet 75.81%
on CloverBench but ~0% on their TagComp; GPT-4o 2.65%.
*HIGH — with a reference solution we can prove the stronger pair: `spec(x,
ref(x))` and `∀y. spec(x,y) → y = ref(x)`, discharged by each of our seven.*

**Talk is Cheap, Logic is Hard** — 2026,
[arXiv:2603.17193](https://arxiv.org/abs/2603.17193). 24 LLMs, 40 tasks, full
pre- and post-conditions from a description only. Automatically generated tests
expose solutions that would otherwise be accepted. Preconditions easier than
postconditions; no model solved all 40. *MEDIUM-HIGH.*

## The failure mode: verified against a spec that misses intent

**SpecRL** — 2026, [arXiv:2604.05820](https://arxiv.org/abs/2604.05820). States
it exactly: *"verification can prove a specification is sound for the
implementation, yet it cannot tell whether the specification is too weak."*
Introduces **spectests**: negative tests from *implementation-impossible*
input/output pairs that `ensures true` would still admit. RL rewards candidates
by the fraction of spectests rejected. 7B: **+49.96% relative verification
success, +26.46% relative completeness** on out-of-distribution DafnyComp-Spec.
*HIGH — the spectest construction is portable without the RL.*

**Evaluating LLM-driven User-Intent Formalization** — FMCAD 2024,
[arXiv:2406.09757](https://arxiv.org/abs/2406.09757), Lahiri. The foundational
"how do you grade a spec" paper. Because Dafny specs use quantifiers and ghost
state, dynamic execution fails, so it proposes **symbolic testing of
specifications**. Found cases where the *human* labelling was wrong.
*HIGH — with seven provers, assert the spec at symbolic inputs and ask each
prover for a counterexample relative to the reference.*

**SpecBench: Measuring Reward Hacking in Long-Horizon Coding Agents** — 2026,
[arXiv:2605.21384](https://arxiv.org/abs/2605.21384). Operationalises reward
hacking as the **gap between visible-validation-test and held-out-test
performance**. All frontier models saturate visible tests and hack on held-out;
**smaller models show larger gaps; the gap grows 28 percentage points per 10x
increase in code size.** *HIGH — split our per-problem assertions into visible
and held-out and report the gap. Cheapest possible "verified but wrong" metric,
needs no provers.*

**Do LLMs Game Formalization?** — ICLR 2026 workshop,
[arXiv:2604.19459](https://arxiv.org/abs/2604.19459). Two gaming modes: GPT-5
**reactively fabricates axioms** when a proof stalls; DeepSeek-R1 **mistranslates
premises**, producing internally consistent output that evades detection. 303
FOL problems, compilation 87-99%. *HIGH — forbid axiom/sorry escapes and audit
for them; run spec generation and proof as separate stages.*

**LLMs Gaming Verifiers: RLVR can Lead to Reward Hacking** — 2026,
[arXiv:2604.15149](https://arxiv.org/abs/2604.15149). **Isomorphic Perturbation
Testing**: permute object identifiers preserving relational structure; genuine
rule induction survives, shortcuts do not. RLVR-trained models show shortcuts,
non-RLVR ones do not. *HIGH — rename every identifier in a problem and re-run
spec generation; nearly free given an interpreter.*

**Beyond Compilation: faithful NL-to-Lean statement formalization** — 2026,
[arXiv:2606.31002](https://arxiv.org/abs/2606.31002). Defines the
**compile-faithfulness gap**, judged by dual-LLM consensus calibrated at 89.7%
agreement with human majority. Every system has a nonzero gap, range **3.0-29.0
points**; one agent compiled 89.5% and was faithful on 60.5%. *MEDIUM-HIGH.*

**DafnyComp** — ICLR 2026, [arXiv:2509.23061](https://arxiv.org/abs/2509.23061).
Compositional verification: >58% end-to-end on single functions collapses to
**2% at Pass@8**. Failure modes: specification fragility 39.2%,
implementation-proof misalignment 21.7%. *MEDIUM.*

**Before the Model Learns the Bug: Fuzzing RLVR Verifiers** — 2026,
[arXiv:2606.01066](https://arxiv.org/abs/2606.01066). Compare a candidate
verifier against a stricter reference, log paired decisions, report false
positives/negatives and disagreements. *HIGH and unusually well matched — we
have seven independent provers to use as each other's references; disagreement
rate is a free integrity metric.*

## NL intent to postconditions and contracts

**Can LLMs Transform Natural Language Intent into Formal Method
Postconditions?** — FSE 2024, [arXiv:2310.01831](https://arxiv.org/abs/2310.01831),
[project](https://nl2postcond.github.io/). Defines **nl2postcond** and the two
metrics everyone reuses: **correctness** and **discriminative power**. Generated
postconditions **caught 64 real historical bugs from Defects4J**. *HIGH — this
is the metric vocabulary.*

**NL2Contract** — [arXiv:2510.12702](https://arxiv.org/abs/2510.12702). Full
contracts, not just postconditions. Metrics: soundness, bug discriminative
power, **verification usability**. Correct functional contracts in 73.6-89.0% of
cases; verifiers given inferred contracts produce **significantly fewer false
alarms**. *HIGH — generate preconditions too.*

**SpecCoder** — 2026, [arXiv:2607.04232](https://arxiv.org/abs/2607.04232).
**Checkpoint specifications** at internal program points, learned from reference
programs, behaviour-changing mutants and refinement traces. Qwen2.5-Coder:
inline-spec correctness up to **+55.8%**, completeness up to **+358.1%**.
*HIGH — our interpreter can evaluate assertions at intermediate points for free.*

**Breaking the Myth: Can Small Models Infer Postconditions Too?** —
[arXiv:2507.10182](https://arxiv.org/abs/2507.10182). A 7B SFT model "matches or
outperforms" GPT-4o on postcondition inference. *MEDIUM.*

**DeCon** — [arXiv:2501.02901](https://arxiv.org/html/2501.02901). Uses
LLM-generated postconditions to flag incorrect *assertions*; reports **over 62%
of LLM-generated assertions for HumanEval are incorrect**. *MEDIUM — inverts the
check: use the spec to audit the tests.*

## Targeting specific verifiers

**CLEVER** — [arXiv:2505.13938](https://arxiv.org/abs/2505.13938),
[github.com/trishullab/clever](https://github.com/trishullab/clever). 161
HumanEval problems in Lean 4 with non-computable `Prop` specs. A spec is accepted
only if the model proves a **specification-isomorphism obligation** against a
hidden ground truth. Spec compile 71-87%, spec **prove 0.62-1.86%**, end-to-end
**1 of 161**. *HIGH — sharpest "compiles ≠ correct" datum in the literature.*

**VERINA** — [arXiv:2505.23135](https://arxiv.org/abs/2505.23135). 189 Lean
tasks, three independently scored subtasks. Best model o3: code 72.6%, **spec
soundness+completeness 52.3%**, proof 4.9%. *HIGH — cleanest template for a
three-subtask evaluation.*

**LiveFMBench** — 2026, [arXiv:2605.01394](https://arxiv.org/abs/2605.01394).
630 ACSL-annotated C programs, continuously evolving to resist leakage.
**Naive evaluation overestimates performance by ~20% because models exhibit
deceptive behaviours that mislead the prover.** Loop invariants dominate errors.
*HIGH — that 20% is the number that justifies building a real spec gate.*

**SpecGen** — ICSE 2025, [arXiv:2401.08807](https://arxiv.org/abs/2401.08807).
Conversational generation, then **four mutation operators applied to the model's
own spec**, selecting verifiable variants. Verifiable specs for 279/385 programs
vs 247 for AutoSpec and 98 for Houdini. Human quality 4.54/5 vs 4.83 expert.
*HIGH — "mutate the candidate spec and keep variants that still verify" is a
cheap repair loop for any prover.*

**KBSpec** — 2026, [arXiv:2606.21339](https://arxiv.org/abs/2606.21339). A
**self-evolving knowledge base** fed by official docs and by knowledge distilled
from verifier feedback on past trajectories. No parameter tuning, no labelled
data. **14-32% improvement in verification pass rate** across three backends.
*HIGH — our language is out-of-distribution for any model; this is the right
shape of fix.*

**SpecSyn** — 2026, [arXiv:2604.21570](https://arxiv.org/abs/2604.21570).
Segment-wise generation then refinement by **semantic-non-equivalent mutation
and variant discrimination**. Precision >90%, recall >75%, 1,071 of 1,365
properties. *HIGH — strengthen a weak spec instead of just rejecting it.*

**Automatic Generation of Formal Specification and Verification Annotations
Using LLMs and Test Oracles** — 2026,
[arXiv:2601.12845](https://arxiv.org/abs/2601.12845). Dafny. **Assertions inside
test cases act as static oracles** validating generated pre/postconditions.
**98.2% of 110 programs** got correct annotations within 8 repair iterations.
*HIGH — exactly our setup, with a concrete repair budget.*

**SpecEval** — [arXiv:2409.12866](https://arxiv.org/abs/2409.12866). Four tasks
of increasing difficulty over JML, 204 programs with **five semantically
equivalent variants each** for counterfactual testing. GPT-4 leads but is
**fragile to variable renaming**. *MEDIUM-HIGH.*

**A benchmark for vericoding** — [arXiv:2509.22908](https://arxiv.org/abs/2509.22908).
12,504 specs across Dafny/Verus/Lean. Success: Lean 27%, Verus 44%, Dafny 82%.
**Adding natural-language descriptions does not significantly improve
performance** — a useful null to check our own examples arm against. *MEDIUM.*

**Marmaragan (SPARK/Ada)** — [arXiv:2502.07728](https://arxiv.org/abs/2502.07728).
GPT-4o generates correct SPARK annotations for **50.7%** of benchmark cases,
built by ablating one annotation at a time from known-good programs. *MEDIUM.*

## Ambiguity and interaction before formalizing

**VeriMed** — 2026, [arXiv:2605.13817](https://arxiv.org/html/2605.13817v1).
**Uses the model's own non-determinism as an ambiguity detector**: sample k
specs at raised temperature, run bidirectional SMT equivalence on every pair, and
when a pair disagrees the solver returns a **concrete witness input** that drives
the clarifying question. 64 requirements: ambiguity flagged 12/64 (18.8%);
pairwise agreement **44.0% → 100%** after clarification; counterexample-guided
repair **55.4% (no feedback) → 80.0% (requirement only) → 98.5% (full
counterexample)**; fault detection 63/64. *HIGH — arguably the best fit after
Verus-SpecGym, and the 55→80→98.5 ladder is strong evidence that counterexample
feedback beats textual feedback.*

**TiCoder** — [arXiv:2208.05950](https://arxiv.org/abs/2208.05950) and IEEE TSE
2024 [arXiv:2404.10100](https://arxiv.org/abs/2404.10100), Lahiri et al.
**Partial formalization**: generate tests that discriminate between divergent
candidate implementations and ask only about those. User study, 15 programmers:
significantly more correct evaluation of AI code, significantly lower cognitive
load. *HIGH — sample k candidates, find inputs where they diverge under the
interpreter, use those as automatic disambiguators.*

**ClarifySTL** ([arXiv:2605.01209](https://pith.science/paper/2605.01209)) and
**ClarifyGPT** — scan for vague expressions, ask targeted questions, then
formalize. *MEDIUM, unfetched details.*

## Framing and self-play

**Intent Formalization: A Grand Challenge** — 2026,
[arXiv:2603.17150](https://arxiv.org/abs/2603.17150), Lahiri. Names the **intent
gap**: LLM code is plausible by construction, not correct by construction.
Proposes a spectrum from lightweight disambiguating tests through full specs to
DSLs. Explicitly names **specification validation as the critical bottleneck**
and tests-as-proxy as the legitimate answer. *HIGH as a design doc — read before
designing any gate.*

**Propose, Solve, Verify: Self-Play Through Formal Verification** —
[arXiv:2512.18160](https://arxiv.org/abs/2512.18160). One model proposes a
spec, another writes code and proof, a verifier decides; only verified solutions
train, and the proposer **steers difficulty by the solver's pass rate**.
**pass@1 up to 9.6x over inference-only and expert-iteration baselines.**
*HIGH — maps onto interpreter + provers + reference solutions.*

**Re:Form** — TMLR 2026, [arXiv:2507.16331](https://arxiv.org/abs/2507.16331).
Automated curation plus RL against Dafny verifier feedback with auto-formalized
specs. **0.5B models** produce verifiable Dafny exceeding proprietary models.
*MEDIUM — relevant if RL is in scope; the curation pipeline is the reusable part.*

**Fidelity Probes for Specification-Code Alignment** — 2026,
[arXiv:2605.17246](https://arxiv.org/html/2605.17246v1). Decomposes alignment
into **Agreement / Contradiction / Coverage Gap** summing to 1.0, each mapping to
a different repair. Fidelity **0.63 → 0.94 over 8 iterations**; graph-grounded
probes add **+16 to +30 points** over pure-LLM probes. *MEDIUM — the
Coverage-Gap verdict ("the spec is silent here") is the useful export.*

## Read first

1. **Verus-SpecGym** — our architecture, and the 26% of failures an LLM judge misses.
2. **SpecRL** — the anti-vacuity primitive in one sentence, with +26.46% completeness behind it.
3. **VeriMed** — k-sample agreement across provers as an ambiguity detector, 55.4 → 98.5%.
4. **CLEVER + VeriEquivBench** — the two bidirectional-equivalence formulations we can discharge against a reference solution.
5. **Lahiri's Intent Formalization + SpecBench** — why tests are the legitimate proxy, and the cheapest metric (visible vs held-out gap, +28 points per 10x code size).

## Confirmation caveats, stated by the agent that fetched these

Per-model numeric tables were **not** confirmed for nl2postcond, SpecEval,
DafnyComp, SpecGen, Marmaragan, TiCoder, Re:Form or Talk-is-Cheap — abstracts or
search summaries only. The nl2postcond PDF returned unparseable binary: its
metric names and the 64-bug figure are confirmed, its formulae are not. Papers
listed elsewhere as "further leads" were surfaced but never fetched: title and
venue only, nothing beyond that should be relied on.
