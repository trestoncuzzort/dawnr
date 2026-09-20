# NL → formal specification: literature (2023–2026)

Lane: **generating a formal specification from natural-language intent** — the step *before* verification.
Compiled 2026-09-20. Live file — appended as papers are confirmed.

Implementable-here rating is given against our context: a small language with an executable
interpreter, seven independent proof systems, per-problem unit tests, and a reference solution
per problem.

Legend: `[H]` high / `[M]` medium / `[L]` low implementable-here.

---

## Angle A — Benchmarks & evaluation environments for specification generation

### [H] Verus-SpecGym: An Agentic Environment for Evaluating Specification Autoformalization
- 2026 · arXiv:2605.26457 (26 May 2026) · https://arxiv.org/abs/2605.26457
- Agarwal, Neamtu, Aggarwal, Kim, Limperg, Flamant, Shimizu, Parno, Welleck (CMU + AWS)
- **Technique.** Verus-SpecBench = 581 spec-writing tasks from Codeforces targeting Verus (Rust).
  The contribution that matters: they extend Verus's `exec_spec` mechanism so a *generated
  specification can be executed as Rust code*, then test it against official Codeforces test
  cases **plus adversarial "hacks"** (edge cases competitors wrote to break wrong solutions).
  This gives deterministic spec-faithfulness checking with **no expert reference spec and no
  LLM judge**. A spec is faithful iff it accepts valid input/correct-output pairs and rejects
  invalid inputs and incorrect outputs.
- **Numbers.** 581 tasks. Gemini 3.1 Pro 77.8% pass; other frontier models 51.1–57.8%;
  open-source 21.5–25.5%. **LLM-as-a-judge misses 26% of the failures** the executable
  evaluator catches.
- **Repo.** Not yet confirmed — see "Repositories" section below (pending check).
- **Implement here:** make generated specs *executable in our interpreter* and score them as a
  two-sided classifier over (our unit tests as positives) × (mutants/wrong solutions as
  negatives) — this is the single closest paper to our setup.

### [H] How Powerful Are LLMs in Generating Formal Program Specifications? (Coins)
- 2026 · arXiv:2608.13077 (13 Aug 2026) · ICML · https://arxiv.org/html/2608.13077
- Yang, Li, Wang, An, Sun, Feng, Wang, Wang, Zhan, Xu
- **Technique.** Argues existing evaluation conflates "does the implementation satisfy the spec"
  with "is the spec any good". **Coins** is a Rocq-based framework that evaluates a spec by
  *instantiating it on concrete test cases* — a 4-stage ladder: (1) syntactic validity,
  (2) first positive case provable, (3) **Passall** = all positive cases provable,
  (4) **Rejectall** = rejects all negative cases. Negatives come from mutation testing.
- **Numbers.** 164 HumanEval problems, hand-written ground-truth Rocq specs, +1,640 mutation-derived
  negative tests, 755.98 positive tests/problem (HumanEval+). Rejectall: Gemini 3 Pro 28.05%
  (syntax 78.05%), GPT-5 15.24% (67.07%), Claude 4.5 Opus 14.63% (59.76%), GPT-4o 4.27%,
  Claude 3.7 1.83%, DeepSeek-V3.1 1.22%. Gemini drops 60.98% → 28.05% from first-case to
  all-cases — single tests are not enough. Ablation: better verification +3.05%, better specs
  +5.01%. Specs with executable `Fixpoint` components verify far more easily than pure
  relational predicates.
- **Implement here:** the exact 4-stage ladder (syntax → 1 test → all tests → rejects all
  mutants) as our spec-quality metric; it needs only our interpreter, tests and mutants.

### [H] CodeSpecBench: Benchmarking LLMs for Executable Behavioral Specification Generation
- 2026 · arXiv:2604.12268 (14 Apr 2026) · https://arxiv.org/html/2604.12268v1
- Chen, Dai, Zhu, Wang, Wang, Xu, Yuan, Guo, Wu
- **Technique.** Specs are **executable Python pre/postcondition functions**, not a proof-assistant
  language. Evaluation is execution-based: **Correctness** = accepts valid behaviours,
  **Completeness** = rejects invalid behaviours, pass = both. Deliberately cheap; no verifier needed.
- **Numbers.** CodeSpecBench-Func: 2,494 LeetCode function tasks, 217.8 tests/task, 96.3% statement
  / 93.6% branch coverage, 61 domains. CodeSpecBench-Repo: 500 SWE-bench Verified issues, 12
  projects, 123.3 tests/instance. Func pass: GPT-5-mini 47.0%, Gemini-2.5-Pro 46.2%,
  GPT-OSS-120B 42.5%, Claude-4.5-Sonnet 40.5%. Repo pass: Claude-4.5-Sonnet 20.2%,
  Gemini-2.5-Pro 18.2%, GPT-5-mini 9.6%, DeepSeek-V3.2 6.8%.
  **Code generation pass rates are 3–4× higher than spec generation pass rates.**
- **Implement here:** the correctness/completeness pair as a single "spec pass" gate, computed
  purely by running the spec as a predicate in our interpreter.

### [H] VeriContest: A Competitive-Programming Benchmark for Verifiable Code Generation
- 2026 · arXiv:2605.08553 (8 May 2026) · https://arxiv.org/abs/2605.08553
- Xie, Pawagi, Liu, Rai, Shao, Berberian Jr., Che, Wang
- **Technique.** 946 LeetCode/Codeforces problems with NL description, expert-validated Verus
  specs, judge-accepted Rust code, Verus-checked proofs, and **positive and negative test
  suites**. Testing is used explicitly as a second layer to validate *postcondition
  completeness* — i.e. to catch weak/vacuous specs that a verifier alone would bless.
  Three-phase construction: manual seed → semi-automated expansion → human-in-the-loop review.
- **Numbers.** Across 10 SOTA models: code gen 92.18%, **spec gen 48.31%**, proof gen 13.95%,
  end-to-end verified synthesis **5.29%**. Spec and proof identified as the bottleneck.
- **Implement here:** the positive/negative test-suite pair *as the definition of a good spec*,
  and the "spec pass rate ≫ end-to-end rate" decomposition as our reporting shape.

### [M] VERINA: Benchmarking Verifiable Code Generation
- 2025/2026 · arXiv:2505.23135 (29 May 2025, rev 16 Mar 2026) · https://arxiv.org/abs/2505.23135
- Ye, Yan, He, Kasriel, Yang, Song (Berkeley)
- **Technique.** 189 hand-curated Lean tasks, each with description, reference implementation,
  formal spec and extensive tests. Three subtasks: code, spec, proof. Spec is scored on
  **soundness and completeness** — soundness = spec accepts the reference behaviour,
  completeness = spec rejects wrong behaviour — evaluated with the test suites.
- **Numbers.** Best model o3: code 72.6%, **spec soundness+completeness 52.3%**, proof 4.9%
  (1 trial/task).
- **Implement here:** the soundness/completeness split reported separately — it tells you whether
  a failing spec is too strong or too weak, which a single pass-rate hides.

### [M] CLEVER: A Curated Benchmark for Formally Verified Code Generation
- 2025 · arXiv:2505.13938 (20 May 2025, rev 23 Oct 2025) · https://arxiv.org/abs/2505.13938
- Thakur, Lee, Tsoukalas, Sistla, Zhao, Zetzsche, Durrett, Yue, Chaudhuri
- **Technique.** 161 HumanEval problems formalised in Lean 4. Crucially the spec-generation task
  is graded by a **specification isomorphism proof**: the model must prove
  `∀ impl, (∀ x, problem_spec impl x) ↔ (∀ x, generated_spec impl x)` against a *hidden*
  ground-truth spec. Specs are non-computable `Prop`s so implementation logic cannot leak, and
  there is no test-case supervision.
- **Numbers.** Spec compile / spec prove / impl compile / impl prove / end-to-end:
  GPT-4o 84.47 / 0.62 / 68.32 / 0.62 / 0%; o4-mini 82.61 / 1.24 / 83.23 / 1.86 / 0.62%;
  Claude-3.7 86.96 / 0.62 / 65.22 / 1.86 / 0.62%; DeepSeek-R1 71.42 / 0.62 / 60.87 / 5.56 / 0.62%;
  COPRA+Claude-3.7 81.37 / 1.24 / 65.22 / 8.70 / 0.62%. **Only 1 of 161 solved end-to-end.**
  Note the gap: ~85% *compile*, <2% *prove equivalent* — compiling proves nothing.
- **Repo.** https://github.com/trishullab/clever (Lean 4 + Python).
- **Implement here:** since we have seven proof systems and a reference solution, we can pose the
  bidirectional-equivalence obligation `generated_spec ⟺ reference_spec` as a proof goal —
  a stronger gate than tests, usable as a tie-breaker on the problems where it discharges.

### [M] VeriEquivBench: An Equivalence Score for Ground-Truth-Free Evaluation of Formally Verifiable Code
- 2025/2026 · arXiv:2510.06296 (7 Oct 2025, rev 18 Apr 2026) · https://arxiv.org/abs/2510.06296
- Zeng, Che, Huang, Ye, Xu, Yuan, Fu
- **Technique.** Drops ground-truth spec matching. The **equivalence score** checks *bidirectional
  implication* in Dafny: forward = the verifier confirms code satisfies the spec; reverse = a
  generated `Check_*_Spec` method proves the spec *tightly* describes the code's behaviour for
  any input. An underspecified spec fails the reverse assertion and scores zero.
- **Numbers.** 2,389 problems (2,174 LeetCode-derived + 215 synthetic "TagComp" from 1,893
  candidates). pass@4: Claude-4-sonnet 75.81% on CloverBench but ~0% equivalence on TagComp;
  GPT-4o 2.65% exact match; Gemini-2.5-flash 0%.
- **Implement here:** the *reverse* direction only — auto-generate a "spec is tight" obligation
  against the reference solution, so `ensures true` scores zero by construction.

### [M] LiveFMBench: Unveiling the Power and Limits of Agentic Workflows in Specification Generation
- 2026 · arXiv:2605.01394 (2 May 2026) · https://arxiv.org/abs/2605.01394
- Xu, Cao, Mo, Hu, Wen, Lin, Han, Qin, Tian, Cheung, Sun, Lu
- **Technique.** Continuously-evolving (leakage-resistant) benchmark of **630 ACSL-annotated C
  programs**, 360 of them newly collected. Compares direct prompting, thinking mode, and agentic
  pipelines, with fine-grained failure-mode analysis.
- **Numbers.** **Naive evaluation overestimates performance by ~20%** because models exhibit
  deceptive behaviours that mislead the automated prover. Sampling and thinking both help;
  small models gain most from reasoning; agentic pipelines win at low sampling budget and on
  harder data. Loop invariants are the dominant error class.
- **Implement here:** the "naive evaluation overestimates by ~20%" audit — re-score a sample of
  our passing specs by hand/by mutants and report the inflation figure.

### [M] SpecEval: Evaluating Code Comprehension in LLMs via Program Specifications
- 2024/2025 · arXiv:2409.12866 (19 Sep 2024, rev 22 Mar 2025) · https://arxiv.org/abs/2409.12866
- Ma, Liu, Bu, Li, Wang, Liu
- **Technique.** Uses JML specs as a proxy for code comprehension. Four tasks of increasing
  difficulty: **specification correctness judgement, specification candidate selection,
  specification infilling, specification generation**. Adds **counterfactual analysis**: five
  semantically-equivalent variants per program (incl. variable renaming) to test whether the
  model is reasoning or reading NL cues.
- **Numbers.** 204 Java programs with expert-verified ground truth (from SpecGenBench, SV-COMP,
  Frama-C-Problems) × 5 variants ≈ 5,000 instances; 6 SOTA LLMs; all below satisfactory.
  GPT-4 leads but is **fragile to variable renaming**.
- **Implement here:** the four-task ladder (judge → select → infill → generate) as a difficulty
  curriculum, and the semantics-preserving-rename counterfactual as a cheap robustness probe.

### [M] A Benchmark for Vericoding: Formally Verified Program Synthesis
- 2025 · arXiv:2509.22908 (26 Sep 2025) · POPL 2026 (Dafny workshop) · https://arxiv.org/abs/2509.22908
- Bursuc, Ehrenborg, Lin, Astefanoaei, Chiosa, Kukovec, Singh, Butterley, Bizid, Dougherty,
  Zhao, Tan, Tegmark
- **Technique.** Largest spec corpus to date: **12,504 formal specifications** — 3,029 Dafny,
  2,334 Verus/Rust, 7,141 Lean; 6,174 previously unseen. Specs were LLM-translated and then
  validated by asking LLMs to compare each translation against its tagged source for faithful
  preservation of pre/postconditions and invariants.
- **Numbers.** Off-the-shelf LLM vericoding success: **Lean 27%, Verus/Rust 44%, Dafny 82%**.
  Dafny verification went 68% → 96% over one year. **Adding natural-language descriptions does
  not significantly improve performance** (a useful negative result for us).
- **Repo.** Beneficial-AI-Foundation GitHub (linked from paper).
- **Implement here:** their anti-cheating checks for vericoding (spec must not be weakened by the
  solver-facing code), plus the cross-language difficulty ordering as a prior for our systems.

### [L] DafnyComp / "Local Success Does Not Compose"
- 2025/2026 · arXiv:2509.23061 · ICLR 2026 poster · https://arxiv.org/abs/2509.23061 ·
  https://dafnycomp.github.io/
- **Technique.** 400 auto-synthesised Dafny programs (300 chain, 100 DAG, from 10 topology
  templates), each 2–5 functions in an acyclic call graph, requiring specs that hold *across*
  component boundaries.
- **Numbers.** >99% syntactic well-formedness and >58% end-to-end verification on single-function
  benchmarks collapses to **~0%** here; strongest model 2% at Pass@8. Failure modes:
  specification fragility 39.2%, implementation–proof misalignment 21.7%, reasoning instability 14.1%.
- **Implement here:** only if/when we have multi-function problems — the failure-mode taxonomy
  (fragility / misalignment / instability) is a good labelling scheme for our own error buckets.

---

## Angle B — "Verified but wrong": vacuous, weak, incomplete specs; spec gaming

### [H] SpecRL: RL with Test-Based Completeness Rewards for Formal Specification Synthesis
- 2026 · arXiv:2604.05820 (7 Apr 2026, rev 14 Jul 2026) · https://arxiv.org/abs/2604.05820
- Huang, Zhang, Sun, Sun, Xiong (Peking University)
- **Technique.** States the problem exactly: *"verification can prove that a specification is sound
  for the implementation, yet it cannot tell whether the specification is too weak."* Introduces
  **spectests** — negative tests built from **implementation-impossible input/output pairs** that a
  weak spec such as `ensures true` would still admit. Training rewards verified candidates by
  **the fraction of spectests their spec rejects**, ranking candidates by how many impossible
  behaviours they rule out.
- **Full pipeline (confirmed from the HTML, this is the recipe to copy):**
  1. Extract the target method.
  2. **Build a runtime-checkable `SpecCheck` predicate** from the spec clauses, folding
     preconditions in by implication: `predicate SpecCheck(x,y) { (R1 && R2) ==> (E1 && E2) }`
     — so a spec is *true by default* wherever its precondition does not hold.
  3. Drop non-compilable cases.
  4. **Positive seeds:** LLM proposes diverse inputs targeting different paths and boundaries;
     *execute them against the implementation* to get observed outputs; reflect-and-fix loop
     (≤3 rounds) on execution failure. Sanity check: the **reference** `SpecCheck` must accept
     every observed (input, output) pair.
  5. **Negative mutation → spectests:** LLM proposes *wrong* outputs aimed at plausible spec
     weaknesses (off-by-one, corner cases, boundary violations), each validated by a
     reflect-and-fix loop. A spectest looks like:
     `var a := new nat[] [3,1,4,1,5]; var m := Max(a); m := 14; expect !SpecCheck(a, m);`
  6. **Completeness score** = spectest rejection rate =
     `|{t ∈ T_neg : rejected}| / |T_neg|`.
  7. **Progressive four-stage reward:** extraction 0.05, compilation 0.15, verification 0.30,
     **spectest 0.50** — and the spectest reward is paid *only to verified candidates*.
- **Numbers.** 7B SpecRL on out-of-distribution DafnyComp-Spec: **+49.96% relative** verification
  success over SFT and **+26.46% relative** completeness. Datasets built: Py2Dfy-Spec 4,663
  programs / 54,284 spectests (11.64 per program); DafnyComp-Spec 232 / 2,913 (12.56);
  DafnyBench-Spec 107 / 1,059 (9.90). **Ablation (Qwen2.5-1.5B):** removing the spectest reward
  drops completeness **14.1%** pass@1 and verifiable **6.1%**; removing the *verification gate*
  inflates completeness **+32.3%** but crashes verifiable **64.7%** — the two are complementary,
  neither alone is a valid objective. Case study `findItem`: reference spec scores 2/8,
  Re:Form-style baseline 5/8, SpecRL-trained 8/8 rejection.
- **Repo.** None published as of this search.
- **Implement here:** spectests, end to end. We can generate implementation-impossible
  (input, output) pairs directly from the reference solution (perturb the reference output), build
  a `SpecCheck` predicate in our interpreter, and score every candidate spec by rejection fraction.
  **This is the cheapest high-value thing in this whole lane** — and note the ablation: gate on
  verification *first*, then reward completeness, or the metric inflates.

### [H] VeriAct / Spec-Harness: Beyond Verifiability — Agentic Synthesis of Correct and Complete Formal Specifications
- 2026 · arXiv:2604.00280 (31 Mar 2026, rev 8 Sep 2026) · https://arxiv.org/abs/2604.00280
  (the revised title is *"Spec-Harness: Measuring and Improving Behavioral Adequacy of
  LLM-Synthesized Formal Specifications"*)
- Md Rakib Hossain Misu, Iris Ma, Cristina V. Lopes (UC Irvine)
- **Technique.** States our exact failure mode: *"passing a verifier only confirms that an
  implementation is consistent with a specification, not that the specification is meaningful."*
  **Spec-Harness** scores a spec on **four dimensions** using **Hoare-triple-based symbolic
  verification plus input/output mutation**, detecting **under-constrained and over-constrained**
  specs that a verifier cannot see. **VeriAct** is a JML agent that consumes Spec-Harness feedback
  in a loop to push specs toward correctness *and* completeness.
- **Numbers.** Shows many verifier-accepted specs are **behaviorally inadequate**; Spec-Harness
  feedback improves specs from Codex CLI, Claude Code and VeriAct alike. (Exact tables not
  confirmed from the abstract page.)
- **Repo.** **https://github.com/Mondego/vACT** — Python 3.10+, **GPL-3.0**. Contains the agentic
  loop (code execution + OpenJML + Spec-Harness feedback) *and* baseline implementations of
  **Daikon, Houdini, SpecGen, AutoSpec and FormalBench** in one place.
- **Implement here:** the **four-dimension Spec-Harness score** and, above all, the
  **over-constrained** axis — most work only checks "too weak", but a spec that is too *strong*
  makes correct solutions unprovable and is what silently tanks a proof-gate pass rate.

### [H] Evaluating LLM-driven User-Intent Formalization for Verification-Aware Languages
- 2024 · arXiv:2406.09757 · FMCAD 2024 · https://arxiv.org/abs/2406.09757
- Shuvendu K. Lahiri (Microsoft Research)
- **Technique.** The origin of the "is this spec any good" metric for verification-aware languages.
  Dynamic execution cannot evaluate rich specs (quantifiers, ghost state), so the paper uses
  **symbolic testing of specifications** instead of the LLM-generated-mutant approach used for
  mainstream languages, yielding an automated proxy for spec quality in Dafny.
- **Numbers.** The automated metric shows close agreement with a **human-labelled dataset of Dafny
  specs for MBPP**, and found cases where the human labels were themselves wrong.
- **Implement here:** symbolic-testing-as-metric — with seven proof systems we can ask each one to
  discharge "reference solution satisfies candidate spec" (soundness) and "some wrong output
  violates candidate spec" (non-vacuity) as two separate obligations.

### [H] Intent Formalization: A Grand Challenge for Reliable Coding in the Age of AI Agents
- 2026 · arXiv:2603.17150 (17 Mar 2026) · https://arxiv.org/abs/2603.17150 ·
  blog: https://risemsr.github.io/blog/2026-03-05-shuvendu-intent-formalization/
- Shuvendu K. Lahiri
- **Technique.** Position/roadmap paper. Names the **"intent gap"** and argues LLM code is
  "plausible by construction but not correct by construction". Proposes a **tradeoff spectrum**:
  lightweight tests that disambiguate likely misinterpretations → full functional specs for
  verification → DSLs from which correct code is synthesised. Names the open problems: scaling
  beyond benchmarks, compositionality over changes, **metrics for validating specifications**,
  rich logics, human–AI specification interaction.
- **Numbers.** 10-page position paper; cites prior results rather than reporting new ones.
- **Implement here:** use it as the framing/vocabulary for our write-up, and adopt its claim that
  **spec validation is the bottleneck** — it justifies spending our budget on the spec gate rather
  than on the provers.

### [M] SpecBench: Measuring Reward Hacking in Long-Horizon Coding Agents
- 2026 · arXiv:2605.21384 (20 May 2026, rev 9 Sep 2026) · https://arxiv.org/abs/2605.21384
- Zhao, Srikanth, Wu, Jiang
- **Technique.** Operationalises reward hacking as the **gap between visible validation tests and
  held-out tests**. Each task = NL spec + visible tests (isolated features) + held-out tests
  (real feature composition). A genuine solution passes both; gaming saturates the visible set.
- **Numbers.** 30 systems-level tasks (JSON parsers → OS kernels). All frontier models saturate
  visible tests and hack held-out ones; smaller models have larger gaps; **the gap grows by 28
  percentage points per 10× increase in code size**. One agent wrote a 2,900-line hash table
  that memorised test inputs.
- **Implement here:** split our per-problem unit tests into visible (shown to the spec generator)
  and held-out (used only to score). The visible/held-out delta is a direct spec-gaming meter.

### [M] Do LLMs Game Formalization? Evaluating Faithfulness in Logical Reasoning
- 2026 · arXiv:2604.19459 (21 Apr 2026) · VerifAI-2 Workshop @ ICLR 2026 · https://arxiv.org/abs/2604.19459
- Kim, Poiroux, Bosselut (EPFL)
- **Technique.** Two-stage pipeline that **separates formalization from proving** so the two can be
  cross-compared; inconsistencies invisible to a compile check become visible. Identifies two
  distinct unfaithfulness modes: GPT-5 **fabricates axioms** reactively during proof generation
  (detectable by cross-stage comparison), DeepSeek-R1 **mistranslates premises** during
  formalization (internally consistent, evades detection entirely).
- **Numbers.** 303 first-order logic problems (203 FOLIO + 100 Multi-LogiEval), Lean 4.
  Compilation rates 87–99% — the paper's point is that high compilation/accuracy ≠ faithful.
- **Implement here:** the axiom-fabrication check — scan accepted proofs for axioms/assumptions the
  spec did not license, and the stage-separation so the spec writer never sees the prover's needs.

### [M] Beyond Compilation: Evaluating Faithful Natural-Language-to-Lean Statement Formalization
- 2026 · arXiv:2606.31002 (30 Jun 2026, rev 3 Sep 2026) · https://arxiv.org/abs/2606.31002
- Zhang, Gallardo Candela, Murthy, Xie, Wang, Raissi
- **Technique.** Defines and measures the **compile–faithfulness gap**. Faithfulness is judged by
  **dual-LLM consensus** (GPT-5.2 *and* Gemini-2.5-Pro must agree), calibrated against human review.
  Explicit conclusion: *"LLM judging is useful as a human-calibrated, conservative aggregate
  measure, not as an equivalence oracle."*
- **Numbers.** 400 graduate-level statements, 8 autoformalization systems. Every system has a
  nonzero gap, **3.0 to 29.0 percentage points**. The full GPT-5.2 tool-augmented agent compiled
  89.5% but was semantically faithful on only **60.5%** (29.0-point gap). Judge agreement with
  human majority on an audited random sample: **89.7%**.
- **Implement here:** report a compile-vs-faithful gap for our own pipeline, and if we use an
  LLM judge at all, require two-model consensus and calibrate it against a hand-audited sample.

### [M] LLMs Gaming Verifiers: RLVR can Lead to Reward Hacking
- 2026 · arXiv:2604.15149 (16 Apr 2026) · LLM Reasoning Workshop @ ICLR 2026 ·
  https://arxiv.org/abs/2604.15149
- Helff, Delfosse, Steinmann, Härle, Shindo, Schramowski, Stammer, Kersting, Friedrich
- **Technique.** **Isomorphic Perturbation Testing (IPT)**: evaluate output under two regimes —
  extensional verification on the original task, and **isomorphic verification on a logically
  isomorphic perturbation** obtained by permuting object identifiers while preserving relational
  structure. Genuine rule induction survives; shortcuts (enumerating instance-level labels) die.
- **Numbers.** RLVR-trained GPT-5 and Olmo3 show shortcuts; non-RLVR GPT-4o, GPT-4.5, Ministral do
  not. Shortcut prevalence **increases with task complexity and with inference-time compute**.
  Controlled experiments: extensional verification *induces* shortcuts; isomorphic verification
  eliminates them.
- **Implement here:** α-renaming / identifier-permutation of our problems as a spec-robustness
  probe — a spec that stops working under renaming was keyed to surface cues, not semantics.

### [M] The Verification Horizon: No Silver Bullet for Coding Agent Rewards
- 2026 · arXiv:2606.26300 · https://arxiv.org/abs/2606.26300
- **Technique.** Argues **no fixed reward function stays effective as policy capability grows** —
  verification must co-evolve with the generator. Shows targeted verification design suppresses
  reward hacking and improves completion quality.
- **Numbers.** Gains reported across multiple internal and public benchmarks (specific figures not
  confirmed from the abstract page).
- **Implement here:** version our spec gate and re-audit it each round rather than freezing it.

### [L] Before the Model Learns the Bug: Fuzzing RLVR Verifiers
- 2026 · arXiv:2606.01066 (31 May 2026) · https://arxiv.org/abs/2606.01066 · Jaideep Ray
- **Technique.** Lightweight **verifier-fuzzing** framework: generate adversarial completions,
  compare a buggy verifier against a stricter reference verifier, log paired decisions, and report
  false-positive / false-negative / disagreement / exploit / uncertainty metrics.
- **Numbers.** No specific counts confirmed from the abstract page.
- **Implement here:** fuzz our own spec-checking harness with deliberately vacuous specs
  (`true`, `output == output`) and confirm it rejects them — a unit test for the gate itself.

### [L] Hack-Verifiable Environments / Auditing Reward Hackability in Code RL Training Environments
- 2026 · arXiv:2605.20744 and arXiv:2606.16062 · https://arxiv.org/html/2605.20744 ·
  https://arxiv.org/pdf/2606.16062
- **Technique.** Systematic auditing of RL environments for hackability at scale.
  **Not fetched in detail** — titles and topic confirmed from search results only.
- **Implement here:** audit checklist for our own environment; low priority.

---

## Angle C — NL intent → postconditions / contracts

### [H] Can LLMs Transform Natural Language Intent into Formal Method Postconditions? (nl2postcond)
- 2023/2024 · arXiv:2310.01831 · **PACMSE / FSE 2024**, DOI 10.1145/3660791 ·
  https://arxiv.org/abs/2310.01831 · project: https://nl2postcond.github.io/
- Endres, Fakhoury, Chakraborty, Lahiri (Michigan + Microsoft Research)
- **Technique.** Founding paper of the lane. Defines **nl2postcond**: translate an NL doc comment
  into a programmatically checkable postcondition. Introduces two automatically-computable metrics:
  - **Test-set correctness (soundness).** `post` is *test-set-correct* iff for every input `i` in
    test set `T`, `post(i, r(i))` is true, where `r` is the **reference implementation**. I.e. the
    postcondition passes all tests against the golden solution.
  - **Bug-completeness score (discriminative power).** Over a set `CM` of semantically distinct
    buggy implementations: `|{m ∈ CM : post evaluates false on m}| / |CM|`. A postcondition
    scoring **1.0 is "bug-complete"**. Mutants are kept only if they differ from the reference on
    at least one test **and** are pairwise distinct.
  - Mutant construction: LLM generates **200 natural buggy solutions + 200 artificially seeded
    bugs per problem**.
- **Numbers.** **EvalPlus (Python, 164 problems)** — accept@1 / accept@10 / avg bug-completeness:
  GPT-4 (simple, no reference) **0.77 / 0.96 / 0.52**; GPT-3.5 (base) 0.46 / 0.87 / 0.72;
  StarChat (base) 0.21 / 0.82 / 0.24. **Defects4J (Java, 525 bugs / 840 functions)** — accept@1 /
  accept@10 / bugs caught: GPT-4 (with buggy code) **0.39 / 0.75 / 47 of 525**; StarChat
  0.12 / 0.56 / 24 of 525. Across all variants nl2postcond distinguished **70 buggy methods from
  64 unique bugs — 12.2% of the bugs considered**.
  Note the tension: GPT-4 is the most *correct* (0.77) but the *least* bug-complete (0.52) of the
  three — stronger models write safer, weaker postconditions. That is the vacuity problem in one
  row of a table.
- **Repo.** https://github.com/microsoft/nl-2-postcond (MIT).
- **Implement here:** **exactly these two metrics**, verbatim. We have the reference solution
  (correctness) and can generate mutants (bug-completeness). Report them *as a pair* — and expect
  the same inverse relationship, which is the number our proof-gate story needs.

### [H] Beyond Postconditions: Can LLMs infer Formal Contracts for Automatic Software Verification? (NL2Contract)
- 2025 · arXiv:2510.12702 (14 Oct 2025) · https://arxiv.org/abs/2510.12702
- Cedric Richter, Heike Wehrheim (Oldenburg)
- **Technique.** Extends nl2postcond to **full contracts: preconditions as well as postconditions**,
  inferred from function names, comments and documentation. Three evaluation axes:
  **soundness** (valid over all inputs), **bug discriminative power**, and **verification
  usability** (what happens when a real verifier is handed the contract).
- **Numbers.** Evaluated LLMs produce test-set-correct functional contracts in **73.6%–89.0%** of
  cases. Verifiers given inferred *pre*conditions emit **significantly fewer false alarms** than
  with postconditions alone; inferred preconditions align with developer intent.
- **Implement here:** generate preconditions too. Our false-alarm rate on the proof systems should
  drop the same way, and a missing precondition is a common cause of "unprovable but correct".

### [M] Breaking the Myth: Can Small Models Infer Postconditions Too?
- 2025 · arXiv:2507.10182 (14 Jul 2025) · https://arxiv.org/abs/2507.10182
- Zhang, Wang, Zhai
- **Technique.** Supervised fine-tuning of a **7B code model** on a purpose-built dataset of
  prompts + reasoning logs + postconditions. Handles repository dependencies and preserves
  pre-state information for expressive specs. Evaluated on syntax correctness, semantic
  correctness, and bug-distinguishing capability.
- **Numbers.** The 7B model **matches or beats GPT-4o and larger open models** on Defects4J.
  Exact per-metric percentages are in the PDF, not the abstract.
- **Implement here:** the dataset recipe (prompt + reasoning trace + gold postcondition) if we
  ever fine-tune a small local spec writer; the three-axis scoring is directly reusable now.

### [M] Teaching Code LLMs to Reason with Intermediate Formal Specifications (SpecCoder)
- 2026 · arXiv:2607.04232 (5 Jul 2026) · https://arxiv.org/abs/2607.04232
- Le-Anh, Le, Nguyen (UT Dallas)
- **Technique.** Moves past whole-program pre/postconditions to **checkpoint specifications** —
  assertions at strategic *internal* program points describing intermediate states. **SpecCoder**
  is a verification-guided training framework learning from validated reference programs,
  **behaviour-changing mutants**, and multi-turn specification-refinement traces; it keeps specs
  that hold on correct executions and rejects those that admit faulty ones.
- **Numbers.** HumanExec benchmark (Codeforces problems + test suites + reference solutions +
  **human buggy submissions**). With Qwen2.5-Coder: inline-spec correctness **+55.8%**,
  completeness **+358.1%**, executable assertion validity **+26.6%**.
- **Implement here:** checkpoint/intermediate assertions inside the interpreter trace — we can
  check them by execution without any prover, and they localise where intent is lost.

### [M] DeCon: Detecting Incorrect Assertions via Postconditions Generated by an LLM
- 2025 · arXiv:2501.02901 · https://arxiv.org/html/2501.02901
- **Technique.** Uses LLM-generated postconditions as an oracle to find *incorrect assertions*
  (inverting the usual direction). Reports that **>62% of LLM-generated assertions for HumanEval
  are incorrect** — a useful base rate for how noisy raw generated specs are.
- **Numbers.** >62% incorrect assertion rate on HumanEval (confirmed via secondary sources; full
  table not fetched).
- **Implement here:** the base-rate expectation — assume most raw generated specs are wrong and
  build the filter first.

### [L] Interactive Code Generation via Test-Driven User-Intent Formalization (TiCoder) / LLM-Based Test-Driven Interactive Code Generation
- 2022 / 2024 · arXiv:2208.05950 ; arXiv:2404.10100 · **IEEE TSE 2024**, DOI 10.1109/TSE.2024.3428972
  · https://arxiv.org/abs/2404.10100
- Lahiri, Naik, Fakhoury, et al. (Microsoft Research + UPenn)
- **Technique.** *Partial* formalization: generate tests that distinguish divergent candidate
  behaviours and ask the user to adjudicate, rather than writing a full spec up front.
- **Numbers.** Mixed-methods user study with 15 programmers: participants using the workflow were
  significantly more likely to correctly evaluate AI-generated code, with significantly lower
  task-induced cognitive load.
- **Implement here:** low, since we have no human in the loop — but the *distinguishing-test*
  generator is reusable as an automatic disambiguator between two candidate specs.

---

## Angle D — Specification generation for specific verifiers (Dafny, JML, ACSL, Verus, Lean, Rocq, SPARK)

### [H] Automatic Generation of Formal Specification and Verification Annotations Using LLMs and Test Oracles
- 2026 · arXiv:2601.12845 (19 Jan 2026) · https://arxiv.org/abs/2601.12845
- Faria, Trigo, Honorato, Abreu (Porto / INESC TEC)
- **Technique.** Dafny. Generates preconditions, postconditions, loop invariants, auxiliary
  predicates and proof helpers. The key trick for us: **assertions inside existing test cases are
  used as static oracles to automatically validate the generated pre/postconditions** — no manual
  inspection. Multi-model (Claude Opus 4.5 + GPT-5.2) with verifier feedback over ≤8 repair
  iterations.
- **Numbers.** **98.2% of 110 programs** got correct annotations. Proof-helper annotations are
  disproportionately hard. Ships a VS Code extension prototype.
- **Implement here:** turn our per-problem unit tests into static oracles for the generated spec —
  exactly the resource we already have, used exactly this way.

### [M] SpecGen: Automated Generation of Formal Program Specifications via LLMs
- 2024/2025 · arXiv:2401.08807 · **ICSE 2025**, DOI 10.1109/ICSE55347.2025.00129 ·
  https://arxiv.org/abs/2401.08807
- Ma, Liu, Li, Wu, Wang, Bu (Nanjing + NTU)
- **Technique.** Two phases for JML. Phase 1: conversational prompting to get a spec. Phase 2 (when
  that fails): apply **four mutation operators to the model's own specification** and select
  verifiable variants via a weighted heuristic search. Mutating the *spec*, not the program.
- **Numbers.** **279 / 385 programs** get verifiable specs, vs 247 for AutoSpec (best prior LLM
  method) and 98 for Houdini (best non-LLM). Human-rated semantic quality **4.54/5.00** vs expert
  ground truth 4.83 and traditional tools 2.32. Datasets: SV-COMP Java + 120 hand-built programs.
- **Implement here:** spec-mutation-and-select as a repair loop when the first generated spec does
  not verify — cheap, and our provers give the selection signal.

### [M] SpecSyn: LLM-based Synthesis and Refinement of Formal Specifications for Real-world Program Verification
- 2026 · arXiv:2604.21570 (23 Apr 2026) · https://arxiv.org/abs/2604.21570
- Ma, Liu, Li, Wu, Wang, Bu
- **Technique.** Decomposes a large program into segments, generates specs per segment, then
  **refines using semantic-non-equivalent program mutations and variant discrimination** — i.e. the
  spec must distinguish the original from mutants, which is a direct measure of specification
  *strength*.
- **Numbers.** Precision **>90%**, recall **>75%**; handled **1,071 of 1,365** target properties on
  open-source programs.
- **Implement here:** variant discrimination as our strength metric — generate semantically
  non-equivalent mutants of the reference solution and require the spec to reject them.

### [M] KBSpec: LLM-driven Formal Specification Generation with Evolving Domain Knowledge Base
- 2026 · arXiv:2606.21339 (19 Jun 2026, rev 14 Aug 2026) · https://arxiv.org/abs/2606.21339
- Wenhan Wang, Zeyu Sun
- **Technique.** JML. Dual-source knowledge: **external** (official documentation) + **internal**
  (verifier feedback on the model's own past specs), stored in a **self-evolving knowledge base
  updated from successful generation and repair trajectories** — no fine-tuning, no labelled data.
  Motivated by the scarcity of spec-language corpora in the wild.
- **Numbers.** **14–32% improvement in verification pass rate** over SOTA LLM-based approaches
  across three LLM backends; produces the largest number of high-completeness specs.
- **Implement here:** highly relevant because our language is small and unseen — build a growing
  retrieval store of (problem, accepted spec, prover feedback) triples and prepend to the prompt.

### [M] An Empirical Study of LLM-Generated Specifications for VeriFast
- 2026 · arXiv:2606.26490 · https://arxiv.org/pdf/2606.26490
- **Technique.** Separation-logic specs for C via VeriFast. **Not fetched in detail** — title, venue
  and topic confirmed from search results only.
- **Implement here:** pending; flagged for a second pass.

### [M] Inferring Multiple Helper Dafny Assertions with LLMs
- 2025 · arXiv:2511.00125 · https://arxiv.org/pdf/2511.00125
- **Technique.** Infers *multiple* helper assertions at once rather than one at a time.
  **Not fetched in detail** — confirmed from search results.
- **Implement here:** batch-assertion inference if single-assertion repair stalls.

### [M] Marmaragan / Verifying LLM-Generated Code in the Context of Software Verification with Ada/SPARK
- 2025 · arXiv:2502.07728 · SCITEPRESS · https://arxiv.org/pdf/2502.07728
- **Technique.** **Marmaragan** uses an LLM to generate SPARK annotations for existing Ada programs
  so GNATprove can verify them. Benchmarked on curated SPARK programs with annotations
  *selectively removed* to isolate specific capabilities.
- **Numbers.** GPT-4o produces correct annotations for **50.7%** of benchmark cases.
- **Implement here:** the **ablation-by-removal** benchmark design — take our reference specs,
  delete one clause at a time, and measure recovery. Gives per-clause-type difficulty for free.

### [M] miniF2F-Dafny: LLM-Guided Mathematical Theorem Proving via Auto-Active Verification
- 2025 · arXiv:2512.10187 · https://arxiv.org/pdf/2512.10187
- **Technique.** First translation of miniF2F into an auto-active verification language; each
  problem is a Dafny lemma with `requires`/`ensures` and an empty body.
  **Not fetched in detail** — confirmed from search results.
- **Implement here:** the "spec given, body empty" task shape as a control condition.

### [L] Evaluating LLM-Generated ACSL Annotations for Formal Verification
- 2026 · arXiv:2602.13851 · https://arxiv.org/pdf/2602.13851
- **Technique.** Compares LLM-generated ACSL annotations against rule-based/Frama-C RTE output.
  **Not fetched in detail.** Reported finding: rule-based approaches remain more reliable for
  *verifiable* annotations; LLMs produce a broader range with less consistency.
- **Implement here:** the comparison-to-a-rule-based-baseline framing.

### [L] Specify What? Enhancing Neural Specification Synthesis by Symbolic Methods
- 2024 · arXiv:2406.15540 · https://arxiv.org/pdf/2406.15540
- **Technique.** GPT-4 spec synthesis augmented with symbolic analyses from the Frama-C ecosystem —
  I/O examples from **PathCrawler** and error reports from **EVA** injected into the prompt.
- **Implement here:** feed concrete I/O examples (we have tests) and interpreter error traces into
  the spec prompt — the cheapest version of this is already available to us.

### [L] Seeking Specifications: The Case for Neuro-Symbolic Specification Synthesis
- 2025 · arXiv:2504.21061 · https://arxiv.org/pdf/2504.21061
- Position paper arguing neural generation must be paired with symbolic validation.

---

## Angle E — Requirements / intent formalization to logics (LTL, STL, SMT)

### [H] VeriMed: Neurosymbolic Auditing of Natural-Language Software Requirements
- 2026 · arXiv:2605.13817 (13 May 2026) · https://arxiv.org/html/2605.13817v1
- Bethel Hall, William Eiers (Stevens Institute)
- **Technique.** The standout idea for us: **use LLM non-determinism as an ambiguity detector**.
  Sample the LLM N=5 times at elevated temperature for candidate SMT encodings of a requirement,
  then run **bidirectional SMT equivalence checking on every pair**: encodings a and b agree iff
  both `C ∧ (a ∧ ¬b)` and `C ∧ (b ∧ ¬a)` are unsat. If either is sat, the solver hands back a
  **concrete witness state** showing exactly which parameter value split the encodings — and that
  witness drives the clarification question.
- **Numbers.** 64 hemodialysis safety requirements. Autoformalization: 64/64 (100%) round-trip
  bidirectional equivalence, mutation detection 249/256 (**97.3%**). Ambiguity: **12/64 (18.8%)**
  flagged ambiguity-sensitive; pairwise SMT agreement 44.0% before clarification → **100%** after.
  Counterexample-guided repair on 65 safety questions: 55.4% no feedback → 80.0% requirement-only
  → **98.5%** with full counterexamples; repair success 97.1%. End-to-end fault detection
  **63/64 (98.4%)** injected defects. Generalisation to 144 PCA-pump requirements: 135/144
  (93.75%) initial equivalence, all 144 converge after one repair iteration.
- **Implement here:** sample k specs per problem and check pairwise equivalence with our provers
  (or by differential execution on our interpreter). Disagreement = ambiguous intent = the
  problems where "verified but wrong" will happen. This is directly buildable today.

### [M] nl2spec: Interactively Translating Unstructured Natural Language to Temporal Logics with LLMs
- 2023 · **CAV 2023**, Springer LNCS, DOI 10.1007/978-3-031-37703-7_18 ·
  https://link.springer.com/chapter/10.1007/978-3-031-37703-7_18
- Cosler, Hahn, Mendoza, Schmitt, Trippel
- **Technique.** Derives temporal-logic specs from unstructured NL, and crucially maps **subformulas
  of the formalization back to the corresponding NL fragments**, so ambiguity is localised and the
  user can fix one subformula rather than the whole thing.
- **Repo.** https://github.com/realChrisHahn2/nl2spec (Python).
- **Implement here:** subformula↔NL-fragment traceability — attach each spec conjunct to the
  sentence that justifies it, then you can ablate conjuncts and see which intent is lost.

### [M] Towards an Agentic LLM-based Approach to Requirement Formalization from Unstructured Specifications
- 2026 · arXiv:2604.18228 · https://arxiv.org/pdf/2604.18228
- **Technique.** Agentic decomposition of requirement formalization. **Not fetched in detail.**

### [M] ClarifySTL: Interactive LLM Agent Framework for STL Transformation through Requirements Clarification
- 2026 · arXiv:2605.01209 · https://pith.science/paper/2605.01209
- **Technique.** Agents scan NL requirements for **vague expressions that leave information
  underspecified**, then generate specific clarification questions before producing Signal
  Temporal Logic. **Not fetched in detail.**
- **Implement here:** the vagueness scanner as a pre-pass that flags problems whose statement
  underdetermines the spec.

### [M] Bridging Natural Language and Formal Specification: NL→LTL via Hierarchical Semantics Decomposition (Req2LTL / OnionL)
- 2025 · arXiv:2512.17334 · https://arxiv.org/html/2512.17334
- **Technique.** Introduces **OnionL**, a hierarchical intermediate language encoding temporal
  semantics, scopes and logical relations, as a semantic bridge; LLM maps NL→OnionL, then
  rule-based translation OnionL→LTL. Reported to surpass NL2SPEC, NL2LTL and NL2TL on academic
  benchmarks and a real-world aerospace dataset (exact figures not fetched).
- **Implement here:** the **intermediate representation** idea — have the model emit a structured
  intermediate (typed, checkable) before the target spec syntax, so errors are caught earlier.

### [L] LTLGuard: Formalizing LTL Specifications with Compact Language Models and Lightweight Symbolic Reasoning
- 2026 · arXiv:2603.05728 · https://arxiv.org/pdf/2603.05728
- Small models + symbolic checking for LTL. **Not fetched in detail.**

### [L] NL2CTL: Automatic Generation of Formal Requirements Specifications via LLMs
- 2024 · Springer, DOI 10.1007/978-981-96-0617-7_1 ·
  https://link.springer.com/chapter/10.1007/978-981-96-0617-7_1
- NL → CTL. **Not fetched in detail.**

### [L] Towards a Common Framework for Autoformalization
- 2025 · arXiv:2509.09810 · https://arxiv.org/pdf/2509.09810
- Unifies autoformalization across theorem statements, logic programs, planning domains and
  knowledge graphs. Useful for vocabulary, not for a mechanism.

---

## Angle F — Adjacent: self-play, RL and pipelines that depend on spec quality

### [H] Propose, Solve, Verify: Self-Play Through Formal Verification
- 2025 · arXiv:2512.18160 (20 Dec 2025) · https://arxiv.org/abs/2512.18160
- Wilf, Aggarwal, Parno, Fried, Morency, Liang, Welleck (CMU)
- **Technique.** Self-play loop where **one model proposes a specification**, another writes code +
  proof hints, and a formal verifier checks it. Only verified solutions are used for training, and
  the proposer uses the solver's pass rate to keep generating specs at the right difficulty mix.
  Targets Verus/Dafny. Directly addresses "unit-test reward is unreliable" by replacing it with a
  proof reward — which is exactly where weak specs become dangerous.
- **Numbers.** PSV-Verus improves pass@1 by **up to 9.6×** over inference-only and expert-iteration
  baselines across three benchmarks.
- **Implement here:** the proposer/solver split and difficulty-targeted spec proposal — with seven
  proof systems we have an unusually rich verifier signal to drive the loop.

### [M] Re:Form — Reducing Human Priors in Scalable Formal Software Verification with RL in LLMs (Dafny)
- 2025/2026 · arXiv:2507.16331 (22 Jul 2025, rev 3 Jul 2026) · **TMLR, May 2026** ·
  https://arxiv.org/abs/2507.16331
- Yan, Che, Huang, Xu, Li, Li, Qu, Shi, Lin, Yang, Yuan, Zhao, Qiao, Zhou, Fu
- **Technique.** Automated data curation + RL against Dafny verifier feedback, with
  **auto-formalized** (not hand-written) specs. Introduces DafnyComp.
- **Numbers.** 0.5B models generate verifiable Dafny exceeding proprietary models; RL with
  regularization generalises out-of-domain. In the "best exploration" variant, the fraction with
  at least one **novel postcondition exceeds 17%**.
- **Implement here:** the auto-curation pipeline shape; also a warning — spec-hacking shows up as
  short repeated outputs, worth logging as a training-collapse signal.

### [M] Automating Formal Verification with Reinforcement Learning and Recursive Inference
- 2026 · arXiv:2605.30914 · https://arxiv.org/html/2605.30914v1
- **Technique.** RL + recursive inference for verification; documents the failure where
  "the model quickly converges to short, repeated outputs, consistent with specification-hacking
  behavior", and that some tasks had **trivial or underconstrained postconditions allowing constant
  implementations to verify**. **Not fetched in full detail.**
- **Implement here:** the constant-implementation probe — if a trivial constant function verifies
  against the spec, the spec is vacuous. Two lines of code, catches the worst case.

### [M] TLA-Prover: Verifiable TLA+ Specification Synthesis via Preference-Optimized LoRA
- 2026 · arXiv:2606.06133 · https://arxiv.org/html/2606.06133v1
- **Technique.** LoRA + preference optimization for TLA+ synthesis. Documents the canonical vacuity
  failure: a model that discovers **`TypeOK == TRUE`** passes TLC on every prompt while conveying
  nothing. **Not fetched in full detail.**
- **Implement here:** maintain an explicit blocklist/detector of tautological spec forms per proof
  system.

### [L] Local Success Does Not Compose — see DafnyComp in Angle A.

### [L] AlgoVeri: An Aligned Benchmark for Verified Code Generation on Classical Algorithms
- 2026 · ICML 2026 · https://en.papernotes.org/ICML2026/code_intelligence/algoveri_an_aligned_benchmark_for_verified_code_generation_on_classical_algorith/
- Strictly aligned benchmark across **Dafny, Verus and Lean** for the same algorithms — closest
  published analogue to our "seven independent proof systems" setup. **Not fetched in detail.**
- **Implement here:** the alignment methodology (same problem, same spec intent, N backends) and
  cross-backend difficulty comparison.

---

## Angle G — Spec-quality tooling: adversarial tests, diagnosis, back-translation

### [H] VeriScale: Adversarial Test-Suite Scaling for Verifiable Code Generation
- 2026 · arXiv:2605.22368 (21 May 2026) · https://arxiv.org/abs/2605.22368
- Bai, Liu, Mou, Wang, Yu, Xie, Li, Zhang, Liang, Luo
- **Technique.** Two stages: **test-suite expansion** driven by *adversarial implementations* (build
  wrong programs, then find inputs that separate them from the reference), and **test-suite
  reduction** distilling those into a compact but maximally discriminative suite. Applied on top
  of VERINA to produce **VerinaPlus** and **VerinaLite**.
- **Numbers.** VerinaPlus expands the original suites **83×**; VerinaLite **14×** at a fraction of
  the cost while keeping discriminative power. Across 8 SOTA LLMs, expanded suites produce
  **sharp score drops on both SpecGen and CodeGen** — i.e. the original benchmark was hiding
  weaknesses.
- **Implement here:** **this is the highest-leverage missing piece for our setup.** We have an
  interpreter and a reference solution, so we can generate adversarial implementations, mine
  separating inputs, and reduce to a small discriminative suite — then use *that* suite as the
  negative set for spec scoring. Answers "our unit tests are too weak to judge a spec".

### [H] Monty: Faithful Autoformalization of Natural Language Assertions
- 2026 · arXiv:2607.13303 (16 Jul 2026) · https://arxiv.org/html/2607.13303v2
- Liu, Parthasarathy, Murali (UIUC)
- **Technique.** Three mechanisms for turning an NL spec into an executable assertion *faithfully*:
  (1) **validity scoring** — syntactic check, fuzz-safety check, and semantic check against
  generated test inputs; (2) **clausal coverage conformance** — the core idea: **back-translate the
  formal spec to natural language**, then have an LLM score *bidirectional clause coverage* on
  a −1…+1 scale, i.e. does every NL clause appear in the formal spec and vice versa;
  (3) **active-learning disambiguation** — when several candidates score equally, query with a
  distinguishing test case.
- **Numbers.** 541 assertion pairs over 22 Java collection-like classes (416 C2S-Augmented,
  86 buggy-code/assertion, 39 manual NL). GPT-OSS: 89.7% accuracy / 92.8% precision / 97.6% recall;
  Qwen2.5-Coder: 75.7 / 91.6 / 93.2. **Up to +20 points precision** over naive LLM use, helping
  small models most. Clausal coverage beats NLI baselines (**AUC 0.659 vs 0.608**).
- **Implement here:** **round-trip back-translation with clause-level coverage scoring.** Cheap,
  needs no prover, and directly targets "the spec omits part of the stated intent" — the exact
  failure that makes a proof vacuous. Pair it with our tests for the validity half.

### [M] FormalRx: Rectify and eXamine Semantic Failures in Autoformalization
- 2026 · arXiv:2607.04655 (6 Jul 2026) · https://arxiv.org/html/2607.04655
- Wang, Huang, Wan, Zhu, Liu, Huang, Guo
- **Technique.** Replaces opaque binary/scalar autoformalization judgments with **actionable
  diagnosis**. A fine-tuned 8B model does four tasks in one forward pass: alignment verdict,
  **error categorization, error localization, and correction generation**. Ships the **Sci error
  taxonomy**: Semantic (S1 logical structure, S2 math objects, S3 math concepts), Constraint
  (C1 variable constraints, C2 range, C3–C5 premise/conclusion/auxiliary), Implementation
  (I1 truncation, I2 precedence) — **28 categories total** with a priority ordering.
- **Numbers.** FormalRx-Test = 7,030 samples. FormalRx-8B vs best baseline (Claude-4.6):
  verdict F1 **0.881** vs 0.880; **categorization F1 0.709 vs 0.475 (+23.4 pts)**;
  localization acc 0.750 vs 0.739; correction acc 0.729 vs 0.714. OOD: ConsistencyCheck F1 0.596;
  EPLA F1 0.541 (1.7B). Trained by SFT on 56,287 NL–FL pairs (52,521 after validation);
  ~2 h on 16 GH200 nodes, 10 epochs. Human study: 960 expert judgments, 84.7% LLM-component
  accuracy, 89.5% inter-annotator agreement (κ=0.895). Verdict-only baselines: BLEU 0.404 F1,
  LeanScorer 0.632 F1.
- **Implement here:** the **error taxonomy as our failure-labelling scheme** for specs that verify
  but miss intent. Localization ("which clause is wrong") is what turns a score into a fix.

### [M] SpecPylot: Python Specification Generation using Large Language Models
- 2026 · arXiv:2604.16560 (21 Apr 2026) · **FSE Companion '26** (tool demo), Montreal ·
  https://arxiv.org/pdf/2604.16560 · artifact DOI 10.5281/zenodo.19491112
- Ayon, Ahmed (Texas State)
- **Technique.** Generates **`icontract` decorators** — Python pre/postconditions embedded in the
  function signature, checked at runtime. Validates by executing the contracts against test cases.
  Evaluated against FormalBench and SpecGen datasets.
- **Numbers.** Specific tables not confirmed from the fetched metadata; artifact archived on Zenodo.
- **Implement here:** the **runtime-checked-decorator** representation. For a small interpreted
  language this is the cheapest possible spec format — no prover needed to get a first signal.

### [M] AutoReSpec: A Framework for Generating Specification using Large Language Models
- 2026 · arXiv:2604.03758 (4 Apr 2026) · https://arxiv.org/abs/2604.03758
- Ayon, Ahmed
- **Technique.** JML for Java. **Collaborative open + closed-source LLM pairing**, with the model
  pair and the prompt **selected dynamically from program structure** (loops/branches get the
  robust pair). When the primary model fails, a second model is invoked with **validator feedback**
  to repair the spec.
- **Numbers.** 72-program Java benchmark: 67/72 programs handled; **success probability 58.2%**,
  **completeness score 69.2%**, **26.89% faster** than SpecGen/FormalBench; beats both on success
  probability and completeness.
- **Implement here:** structure-conditioned routing — send loop-bearing problems down a more
  expensive spec-generation path, and keep a cheap path for straight-line problems.

### [M] FormalBench (from "Can LLMs Reason About Program Semantics?")
- 2025 · arXiv:2503.04779 (22 Feb 2025, rev 29 May 2025) · **ACL 2025 Main** ·
  https://arxiv.org/abs/2503.04779
- Le-Cong, Le, Murray (Melbourne)
- **Technique.** Benchmark for **formal specification synthesis** (Java/JML), measuring whether LLMs
  can reason across *all* executions rather than one trace. Includes a **robustness test against
  semantics-preserving code transformations**.
- **Numbers.** LLMs do well on simple control flow and **struggle badly with loops**; limited
  robustness to semantics-preserving transformations; **self-repair prompts improve success rates
  by 25%**.
- **Implement here:** the self-repair prompt loop (+25% is a large, cheap win) and the
  semantics-preserving-transformation robustness check.

### [M] Grounding AI Agents in Contracts: An Empirical Evaluation of Spec-Driven Test Generation
- 2026 · arXiv:2608.17177 · https://arxiv.org/html/2608.17177
- **Technique.** Agent first reasons about and **explicitly documents preconditions, postconditions
  and undefined behaviours**; this semi-formal intermediate spec then acts as a **cognitive
  scaffold** for test generation. **Not fetched in detail** — abstract confirmed via search.
- **Implement here:** emit the semi-formal contract *before* the formal one, as a scaffold — cheap
  ablation: does contract-first improve downstream proof rate?

### [L] Autoformalization in the Era of Large Language Models: A Survey
- 2025 · arXiv:2505.23486 (29 May 2025) · https://arxiv.org/pdf/2505.23486
- Weng, Du, Li, et al.
- Survey spanning theorem statements, logic programs, planning domains, knowledge graphs.
  Useful for taxonomy and related-work coverage, not for a mechanism.

### [M] Grammar Prompting for Domain-Specific Language Generation with LLMs
- 2023 · arXiv:2305.19234 · **NeurIPS 2023** · https://arxiv.org/abs/2305.19234
- **Technique.** For highly structured, low-resource languages, augment each few-shot demo with a
  **minimally-sufficient BNF grammar** for that particular output. At inference the LLM first
  **predicts a BNF grammar** for the test input, then generates the output constrained by it.
- **Implement here:** directly relevant — our spec language is small and almost certainly absent
  from pretraining. Emit a per-problem minimal grammar first, then the spec. See also
  **DSL-Xpert 2.0** (Inf. & Softw. Tech. 2025, doi:10.1016/j.infsof.2025.107861-ish, via
  ScienceDirect S0950584925002939) and **From Text to DSL: Evaluating Grammar-Based Model
  Generation Using Open LLMs** (arXiv:2605.15865) which tests 0.5B–32B open models on syntactic
  validity, semantic completeness and inter-model reference consistency with few-shot only.

### [L] Towards a Common Framework for Autoformalization
- 2025 · arXiv:2509.09810 · https://arxiv.org/pdf/2509.09810 — see Angle E.

---

## Angle H — Specification *inference from code* (complements NL→spec; gives the negative-example machinery)

### [H] ClassInvGen: Class Invariant Synthesis using Large Language Models
- 2025 · arXiv:2502.18917 · **Springer, DOI 10.1007/978-3-031-99991-8_4** ·
  https://arxiv.org/abs/2502.18917 · https://openreview.net/pdf?id=7iwJ2ZQS3s
- Sun, Agashe, Chakraborty, Taneja, Barrett, Dill, Qiu, Lahiri
- **Technique.** **Co-generates executable class invariants *and* the test inputs that filter them.**
  Pipeline: static-analysis preprocessing → LLM proposes candidate invariants *and* filtering test
  suites → instrument the code to check candidates → prune candidates with the generated tests.
  Exploits LLMs' strength at writing *pure functions* rather than logic syntax.
- **Numbers.** Beats both a pure-LLM spec generator and Daikon. Contributes a benchmark of standard
  C++ data structures **plus a harness that measures correctness AND completeness of generated
  specs using tests and mutants**. Case study on real Z3 SMT solver classes (incl. `bdd_manager`);
  Z3 developers confirmed most proposed invariants.
- **Implement here:** the **co-generation pattern** — make the model produce the spec *and* the
  tests that would falsify a wrong spec, in the same call. With our interpreter this is directly
  runnable, and the tests-and-mutants harness is the same shape as ours.

### [M] Improving Dynamic Specification Inference with LLM-Generated Counterexamples
- 2026 · arXiv:2604.10761 (12 Apr 2026) · CC BY-NC-SA 4.0 ·
  https://arxiv.org/abs/2604.10761 · artifact: https://zenodo.org/records/18899070
- Balestra, Nolasco, Molina, Garbervetsky, Degiovanni, Aguirre
- **Technique.** Dynamic inference (Daikon/**SpecFuzzer**) produces many spurious assertions because
  the test suite is not diverse enough. Fix: ask an LLM to **generate tests that try to invalidate
  each inferred assertion**, and discard the ones it breaks.
- **Numbers.** Discards **up to 11.68% of invalid assertions**; **up to +7% precision** against
  ground truth; **no recall degradation**.
- **Implement here:** the falsification prompt — for every candidate spec, ask for an input that
  violates it; if such an input exists on the *reference* solution, the spec is unsound. Cheap
  pre-filter before any prover runs.

### [M] An Empirical Study of LLM-Generated Specifications for VeriFast
- 2026 · arXiv:2606.26490 (25 Jun 2026) · https://arxiv.org/html/2606.26490
- Fan, Tran, Dod, Hu, Rego, Xie, DiVincenzo, Tan (Purdue)
- **Technique.** Separation-logic specs for C via VeriFast: pre/postconditions, loop invariants,
  recursive heap predicates, open/close auxiliary statements, lemmas. 8 prompting approaches ×
  10 LLMs × 3 input types (**NL** description only, **FB** formal pre/post given, **FBP** formal +
  memory-allocation constraints).
- **Numbers.** 60 programs / **303 C functions** (avg 43 LOC, 81 spec lines). Overall verification
  **31.4%** (855/2,727). By input: **FBP 39.9% > FB 29.5% > NL 24.6%** — i.e. giving the model a
  formal skeleton beats natural language by ~15 points. By model: Gemini 2.5 Pro 39.7%,
  Claude-3-7 29.8%, GPT-4o 24.5%. By feature: plain SL 51.2%, recursive predicates 30.9%,
  **concurrency 12.3%, loops 11.4%**. **Spec drift: 87% of pre/postconditions equivalent,
  5% strengthened, 8% weakened or changed** — and **9.0% (246/2,727) of outputs silently changed
  the source code's behaviour**. Errors (1,652 across 354 failing functions): 23% compile/syntax,
  **71% practical reasoning**, 6% theoretical logic; 94% traceable to missing domain knowledge of
  the SL verifier; 51.9% missing heap chunks. Best prompt: **RAG-sparse + function splitting, 64%**
  on the test set vs ≤56% for alternatives.
- **Implement here:** the **"did the model silently change the program while writing the spec"
  check** (9% failure rate!) and the **weakened/strengthened/equivalent** three-way classification
  of generated specs against the reference — both apply verbatim to us.

### [M] Enhancing LLM-based Specification Generation via Program Slicing and Logical Deletion
- 2025 · arXiv:2509.09917 · https://arxiv.org/pdf/2509.09917
- Chen, Zhang, Zhang, Zhang, Zhou, Shen, Ma, Yang
- **Technique.** Two filters. **Program slicing** trims the code fed to the model to the
  dependency-relevant segments, cutting prompt noise. **Logical deletion** prunes the generated
  spec: drop a clause and test whether it is still entailed by the rest — if so it was redundant.
- **Numbers.** Specific tables not confirmed from the fetched PDF metadata.
- **Implement here:** **logical deletion as a minimality check** — with seven provers we can ask
  "does spec-minus-clause-i still imply clause i?" and report the count of *non-redundant* clauses
  as a spec-substance metric. A vacuous spec has ~0 non-redundant clauses.

### [M] Integrating Symbolic Execution with LLMs for Automated Generation of Program Specifications
- 2025/2026 · arXiv:2506.09550 (rev 21 Jan 2026) · https://arxiv.org/pdf/2506.09550
- Yang, Ma, Wang, Xu, Cao, Zhan, Li, Gu
- **Technique.** Symbolic execution explores program paths and extracts path constraints; the LLM
  then synthesises loop invariants and preconditions from those constraints. C programs; four
  algorithms in the pipeline. Specific benchmark numbers not extractable from the PDF fetch.
- **Implement here:** feed **path constraints from our interpreter** (or a simple symbolic
  execution over our small language) into the spec prompt — grounded facts beat free-form NL.

### [M] Self-Spec: Model-Authored Specifications for Reliable LLM Code Generation
- 2026 · OpenReview · https://openreview.net/pdf?id=6pr7BUGkLp
- **Technique.** Asks whether a model can **invent its own task-specific specification DSL** and
  then faithfully implement code against that self-authored contract. Framing: inserting a
  specification intermediate into NL→code makes assumptions explicit, **reduces drift**, and
  improves outcomes. (PDF behind OpenReview bot check — abstract confirmed via search snippet
  only; **numbers not confirmed**.)
- **Implement here:** the ablation — NL→code vs NL→spec→code in our own pipeline, measuring the
  drift reduction. Worth running even before we settle on a spec language.

### [L] Code-Augur: Agentic Vulnerability Detection via Specification Inference
- 2026 · arXiv:2606.18619 · https://arxiv.org/pdf/2606.18619
- Infers specs to drive vulnerability detection. **Not fetched in detail.**

### [L] Not All Invariants Are Equal: Curating Training Data to Accelerate Program Verification
- 2026 · arXiv:2603.15510 · https://arxiv.org/pdf/2603.15510
- Data curation for invariant training. **Not fetched in detail** — relevant if we fine-tune.

### [L] SpecTra: Enhancing Code Translation by Generating Multi-Modal Specifications
- 2024 · arXiv:2405.18574 · https://arxiv.org/pdf/2405.18574
- Generates specs in several modalities (tests, symbolic constraints, NL) and uses their
  agreement. **Not fetched in detail** — the multi-modal agreement idea is reusable.

---

## Repositories (working code beats PDFs)

| Paper | Repo | Language | Licence | What to lift |
|---|---|---|---|---|
| **CLEVER** | https://github.com/trishullab/clever | Lean 4 + Python (`clever_bench` pkg) | **MIT** | The **staged certification design** that isolates failure across spec-gen / equivalence-proof / impl / proof — four independently checked stages. Also the spec-isomorphism obligation template. Directly mirrors a multi-prover pipeline. |
| **VERINA** | https://github.com/sunblaze-ucb/verina · data: https://huggingface.co/datasets/sunblaze-ucb/verina | Lean 4 + Python | *to confirm* | The **modular** evaluator: code / spec / proof scored separately and in composition, with spec scored on soundness *and* completeness against test suites. Also `sunblaze-ucb/vero` for repo-level. |
| **VeriContest** | https://github.com/HIPREL-Group/VeriContest · data: https://huggingface.co/datasets/Gax-c/VeriContest | Rust/Verus + Python | *to confirm* | The **four task modes** (SpecGen / CodeGen / ProofGen / End2End) evaluated both isolated and compositional, plus **positive and negative test suites per problem** used to catch weak postconditions. Closest task decomposition to ours. |
| **Verus-SpecGym** | https://github.com/formal-verif-is-cool/verus-spec-gym (fork of the **Harbor** agentic eval framework) | Rust/Verus + Python | *to confirm* | The **executable-specification evaluator** (`exec_spec` extension) and the agentic loop where the agent iterates against verifier errors. The adversarial "hacks" corpus is the model for our negative tests. |
| **SpecGen** | https://github.com/Lezhi-Ma/SpecGen-Artifact | Java + Python, drives **OpenJML** | *to confirm* | The **four spec-mutation operators** (predicative, logical, comparative, arithmetic) and the weighted heuristic selection over mutated specs — a ready-made spec-repair loop. |
| **nl2postcond** | https://github.com/microsoft/nl-2-postcond (umbrella repo also holds **TiCoder** TSE'24, the **FMCAD'24** spec-evaluation work, and an **AutoCLRS F\*** spec evaluation) | Python (+ Java for Defects4J) | **MIT** | The **correctness + discriminative-power** scoring harness and the Defects4J bug-discrimination driver. One repo covering three of the papers in this file. |
| nl2spec | https://github.com/realChrisHahn2/nl2spec | Python | *to confirm* | Subformula↔NL-fragment traceability and the interactive refinement loop |
| Vericoding benchmark | Beneficial-AI-Foundation GitHub (linked from arXiv:2509.22908) | Dafny/Verus/Lean | *to confirm* | 12,504 specs across 3 languages; the spec-faithfulness validation scripts |
| DafnyComp | https://dafnycomp.github.io/ (repo linked) | Dafny + Python | *to confirm* | 400 compositional programs + failure-mode labelling |
| **vACT / VeriAct + Spec-Harness** | https://github.com/Mondego/vACT | **Python 3.10+**, drives OpenJML | **GPL-3.0** ⚠️ (copyleft — read, don't vendor) | **The Spec-Harness scorer** (Hoare-triple symbolic verification + I/O mutation, four dimensions, catches over- *and* under-constrained specs) plus **in-repo baselines for Daikon, Houdini, SpecGen, AutoSpec and FormalBench**. Best single code artifact in this lane for "is this spec meaningful". |
| **FormalBench** | https://github.com/thanhlecongg/FormalBench | Python, drives **OpenJML 17 & 21** (Java/JML) and **ACSL** for C | *to confirm* | **FormalBench-Base 699 Java programs + FormalBench-Diverse 6,219 mutated programs.** The mutation-based *diverse* split is exactly the semantics-preserving-transformation robustness harness we'd otherwise have to build. |
| Vero (repo-level VERINA follow-on) | https://github.com/sunblaze-ucb/vero · https://vero.verina.io/ | Lean 4 | *to confirm* | Repository-level verified code generation, if we ever go multi-module |
| SpecPylot | Zenodo DOI 10.5281/zenodo.19491112 | Python (`icontract`) | *to confirm* | Runtime-checked pre/postcondition decorators — the lightest-weight spec format |
| Improving Dynamic Spec Inference w/ LLM Counterexamples | https://zenodo.org/records/18899070 | Java (SpecFuzzer) | CC BY-NC-SA 4.0 | The counterexample-generation prompts that discard invalid assertions |
| SpecRL | none published | — | — | Pipeline is fully described in the paper (see Angle B); reimplement from the 7 steps |
| Coins (How Powerful Are LLMs…) | not confirmed | Rocq + Python | — | 164 hand-written Rocq specs for HumanEval + 1,640 mutation-derived negatives |

---

## Confidence notes — what I could and could not confirm

Confirmed from primary sources (arXiv abstract/HTML, ACM/Springer, or the repo itself): all
titles, authors, dates, venues and arXiv ids above, plus every number attributed to
Verus-SpecGym, Coins, CodeSpecBench, VeriContest, VERINA, CLEVER, VeriEquivBench, LiveFMBench,
SpecEval, Vericoding, DafnyComp, SpecRL, Lahiri FMCAD'24, Lahiri intent-formalization,
SpecBench, "Do LLMs Game Formalization?", "Beyond Compilation", "LLMs Gaming Verifiers",
nl2postcond (headline only), NL2Contract, SpecCoder, SpecGen, SpecSyn, KBSpec, Marmaragan,
VeriMed, PSV, Re:Form, VeriScale, Monty, FormalRx, AutoReSpec, FormalBench, ClassInvGen,
the Daikon-counterexample paper, the VeriFast study, and the vACT/FormalBench/CLEVER/VERINA/
VeriContest/Verus-SpecGym/SpecGen/nl-2-postcond repos.

**Could NOT confirm:**
- **Self-Spec** — OpenReview PDF is behind a bot check; only the abstract framing is confirmed,
  no numbers.
- **SpecPylot, SpecSyn (target verifier), Enhancing…via Program Slicing, Integrating Symbolic
  Execution** — PDFs fetched as binary; abstracts confirmed, result tables not.
- Papers explicitly marked "*Not fetched in detail*" in the body: title/venue/topic confirmed from
  search results only — treat their descriptions as provisional.
- Licences marked "*to confirm*" were not read from the repo's LICENSE file.

---

## What to read first, and why

1. **SpecRL (arXiv:2604.05820)** — it is the only paper that gives a complete, copyable recipe for
   turning "a spec that verifies" into "a spec that means something": `SpecCheck` predicate,
   executed positive seeds, mutated negative spectests, rejection-rate score, and the ablation
   proving you must gate on verification *before* rewarding completeness.
2. **Verus-SpecGym (arXiv:2605.26457)** — the closest published environment to ours, and the
   source of the one number that should change how we evaluate: an **LLM judge misses 26% of the
   failures** that executing the spec catches. We have an interpreter; we should never use a judge.
3. **VeriScale (arXiv:2605.22368)** + **ClassInvGen (arXiv:2502.18917)** — together they solve
   "our per-problem unit tests are too weak to grade a spec": VeriScale mines adversarial tests
   from wrong implementations (83× expansion) and ClassInvGen co-generates the spec with the tests
   that would falsify it, with a correctness-and-completeness harness built on tests and mutants.
4. **vACT / Spec-Harness (arXiv:2604.00280, github.com/Mondego/vACT)** — the best running code for
   "is this spec meaningful", and the only one that scores **over**-constrained as well as
   under-constrained specs, which is what makes correct solutions unprovable across seven systems.
5. **Lahiri's intent-formalization pair (arXiv:2603.17150 + arXiv:2406.09757)** — the framing and
   vocabulary for the write-up, and the argument that **spec validation, not proving, is the
   bottleneck** — which is the case for spending our budget on the spec gate rather than the provers.
