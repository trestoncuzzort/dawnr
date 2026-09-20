# Judging specification quality, and using that judgement as a training/filtering signal

Literature sweep, 2023–2026 (prioritising 2025–2026). Lane: the half *after* a specification
exists — is it any good, and can that judgement drive training or data filtering.

Local context assumed for the "implementable-here" rating: a small language with an executable
interpreter, seven independent proof systems, per-problem unit tests, a reference solution per
problem, and an existing mutation engine that produces deliberately broken twins of a program.

Status: **sweep complete** (search budget exhausted at 200 queries; fetches continued after).
**44 distinct works** across 8 angles, 15 repositories located. Entries marked `[unverified]`
could not be fully confirmed from a primary source; the gap is stated explicitly, and there is a
"What could not be confirmed" section before the reading list.

Headline for the impatient: the single most transferable idea in this literature is that
**a specification's quality is the fraction of deliberately-broken programs it rejects** — and we
already own the machine that produces those broken programs. Papers A1, A2, A3, A4, B1, E1 and
F1 are seven independent arrivals at that same measurement, and E1 is the one that turns it into
a training reward.

---

## Angle A — Validating specifications with tests: soundness and completeness

### A1. Evaluating LLM-driven User-Intent Formalization for Verification-Aware Languages
- **Year / venue**: 2024, FMCAD 2024 — arXiv:2406.09757
- **URL**: https://arxiv.org/abs/2406.09757
- **Technique**: The origin point for the soundness/completeness pair used by nearly everything
  downstream. A rich specification (quantifiers, ghost state) cannot be executed, so it is
  *symbolically tested*: for each test pair `(i, o)` the tool asks the verifier to discharge the
  Hoare triple `{true} x := i; y := o; {phi(x, y)}`. Soundness = the spec accepts every
  reference input/output pair. Completeness = the spec *rejects* perturbed outputs; the tool
  mutates each expected output up to 5 ways (integers: add/subtract a random 1..10; arrays: drop
  an element or insert a random value; booleans: flip) and scores `|rejected| / |mutants|`.
- **Numbers**: 153 MBPP problems with specifications; the tool ran on 64 of them. Specs humans
  labelled `strong_spec` scored completeness > 0.66; `weak_spec` scored < 0.66. The automated
  metric found at least 3 cases where the *human* label was wrong (specs weaker than an
  available alternative), i.e. it caught bugs in the ground truth.
- **Implementable here**: **HIGH**. This is almost exactly our setup, minus Dafny.
- **What to implement**: the two-sided score — run each candidate spec against (a) the reference
  solution's I/O pairs for soundness, and (b) mutated outputs / our broken twins for
  completeness — and report both, never just "it verifies".
- **Repo**: not confirmed; the paper describes a Dafny-specific prototype.

### A2. Spec-Harness: Measuring and Improving Behavioral Adequacy of LLM-Synthesized Formal Specifications
- **Year / venue**: 2026 — arXiv:2604.00280 (v1 title was *VeriAct: Beyond Verifiability —
  Agentic Synthesis of Correct and Complete Formal Specifications*; v2, 8 Sep 2026, is
  Spec-Harness). Authors: Md Rakib Hossain Misu, Iris Ma, Cristina V. Lopes.
- **URL**: https://arxiv.org/abs/2604.00280
- **Technique**: Generalises A1 into a 2x2: **Post-Correctness** (spec accepts all valid `(i,o)`),
  **Post-Completeness** (spec rejects mutated outputs), **Pre-Correctness** (precondition admits
  all valid inputs without false rejection), **Pre-Completeness** (precondition rejects invalid
  inputs). All four are discharged as Hoare triples through OpenJML's SMT backend without
  re-executing the method: `{true} x := i; y := o {phi(x,y)}` and `{true} x := i {psi(x)}`.
  Completeness uses type-directed output mutation (`o ± delta` for ints, element insert/delete
  for arrays), fixed-size mutant set per output.
- **Numbers**: benchmarks SpecGenBench (120 Java methods) and FormalBench (662 methods after
  filtering). The headline gap: Houdini verifies at 93% / 67% but scores Post-Completeness of
  only 24% / 19%, and **Pre-Correctness 0% on both**. SpecGen 30.2% verified with
  Post-Completeness ≤ 9%; AutoSpec 27.9% verified, ≤ 9%. GEPA-optimised prompts pushed
  verification to 46.61% / 18.59% but Post-Completeness only 39% / 14% — "optimizing against
  verifier acceptance makes specifications pass more often without making them capture more
  behavior". Feeding Spec-Harness back to agents: Claude Code 49.2% → 63.3% Post-Harness@0.75 on
  SpecGenBench; Codex 48.3% → 55.0%; VeriAct 50.0% with every verified task also clearing the
  adequacy bar. On FormalBench VeriAct traded verification 65.0% → 15.8% to raise
  Post-Harness@0.75 from 10.8% → 15.8% (the agent refuses to submit weak specs).
- **Note**: a vacuous `ensures true` scores Post-Correctness 1.0 and Post-Completeness 0.0 — the
  metric separates the two failure modes cleanly.
- **Implementable here**: **HIGH**.
- **What to implement**: the four-quadrant score as our spec scorecard, with the precondition
  half driven by inputs the reference solution rejects, and a `@0.75` threshold gate.
- **Repo**: **https://github.com/Mondego/vACT** (also referenced as `Mondego/VeriAct`) —
  "vACT: Verifiable specification synthesis with Spec-Harness feedback". Contains the
  Spec-Harness scorer (Hoare-triple construction + OpenJML invocation + type-directed output
  mutation) and the agent loop. Reported behaviour worth copying: **iteration 1 fixes
  syntax/type errors flagged by OpenJML; iteration 2 fixes specification weakness flagged by
  Spec-Harness** — two distinct feedback channels, not one. Language/licence to confirm.

### A3. Can LLMs Reason About Program Semantics? (FormalBench)
- **Year / venue**: ACL 2025 (Long) — arXiv:2503.04779
- **URL**: https://arxiv.org/abs/2503.04779 · https://aclanthology.org/2025.acl-long.1068/
- **Technique**: Benchmark for JML specification inference with two metrics.
  **Consistency** = the spec passes the deductive verifier against the real program.
  **Completeness** = mutation-based: generate K non-equivalent mutants of the *program*, verify
  the spec against each; a complete spec should make every mutant fail; score = failed mutants / K.
  Also measures **robustness** under semantics-preserving program transformations.
- **Numbers**: FormalBench-Base = 699 Java programs; FormalBench-Diverse = 6,219 programs built
  by mutating Base. Tooling: OpenJML 21.0 + Major 3.0.1. Consistency pass rates: GPT-4 69.4%
  average (92.3% sequential, 85.7% conditional, 61.2% simple loops, 38.5% complex loops);
  Claude-3 65.9%; LLaMA-3-70B 58.0%; DeepSeek-Coder-33B 56.3%; GPT-3.5 52.8%; CodeLlama-34B 49.3%.
  Self-repair prompts: GPT-4 69.4% → 78.1% (1 round) → 85.2% (3 rounds), +25% relative.
  Dominant failure mode: "under-strength loop invariants — generating invariants like `true`,
  which are consistent but useless."
- **Implementable here**: **HIGH** — this is the closest published analogue of our mutation engine.
- **What to implement**: completeness = fraction of our broken twins that the candidate spec
  rejects; treat it as the primary spec-quality number, with verifier-consistency as a gate only.
- **Repo**: **https://github.com/thanhlecongg/FormalBench** — Python 3.12, **Apache 2.0**,
  installable as a library (`pip install -e .[default]`). Pluggable per-language:
  **Java → Major** mutation framework + OpenJML; **C → Mull** + Frama-C. Consistency is reported
  as verification success/failure rate. **This is the cleanest thing to lift: the completeness
  harness is language-parameterised, so swapping in our interpreter + mutation engine + one of
  our proof systems is the intended extension point.**

### A4. PostcondBench: Benchmarking Correctness and Completeness in Formal Postcondition Inference
- **Year / venue**: 2026 — arXiv:2605.03356. Authors: Gehao Zhang, Juan Zhai.
- **URL**: https://arxiv.org/abs/2605.03356
- **Technique**: Same soundness/completeness split, but completeness is operationalised as
  **defect discrimination** — "a postcondition set is more complete if it is violated by more
  defective implementations while remaining satisfied on correct executions". Ships a runnable
  execution environment so scoring is automatic.
- **Numbers**: 420 tasks (Python + Java) drawn from 121 open-source projects; 5 SOTA LLMs, 3
  prompt formulations. Headline: a substantial gap between correctness and completeness, widening
  with task complexity and repository dependencies.
- **Implementable here**: **HIGH**.
- **What to implement**: score a spec by how many of our broken twins it flags while the
  reference solution still passes — a single "defect discrimination" number per problem.
- **Repo**: not confirmed.

### A5. CodeSpecBench: Benchmarking LLMs for Executable Behavioral Specification Generation
- **Year / venue**: 2026 — arXiv:2604.12268
- **URL**: https://arxiv.org/abs/2604.12268
- **Technique**: Specifications written as *executable* Python pre/postcondition functions, so
  no SMT solver is needed at all — the spec is just code you run. Scores correctness (accepts
  valid behaviour) and completeness (rejects invalid behaviour), at both function and repository
  level.
- **Numbers**: 15 SOTA LLMs; best model only **20.2% pass rate** on repository-level tasks.
  Finding: specification generation is substantially harder than code generation, and strong
  coding scores do not predict it.
- **Implementable here**: **HIGH** — we have an executable interpreter, so executable specs are
  free; no proof system required for this signal.
- **What to implement**: an executable-predicate spec format that our interpreter can run
  directly against the reference solution and against each broken twin.
- **Repo**: not confirmed.

### A6. VERINA: Benchmarking Verifiable Code Generation
- **Year / venue**: 2025 — arXiv:2505.23135
- **URL**: https://arxiv.org/abs/2505.23135
- **Technique**: Modular Lean benchmark separating code generation, specification generation and
  proof generation, plus their compositions, so spec quality is scored independently of code.
- **Numbers**: 189 manually curated Lean tasks. Best model (o3): code correctness 72.6%,
  **specification soundness-and-completeness 52.3%**, proof success 4.9% (one trial/task).
- **Implementable here**: **MEDIUM**.
- **What to implement**: the modular split — report spec score and code score separately so a
  model cannot hide a weak spec behind correct code.
- **Repo**: **https://github.com/sunblaze-ucb/verina** (UC Berkeley Sunblaze); dataset at
  **https://huggingface.co/datasets/sunblaze-ucb/verina**. Published at **ICLR 2026**.
  **The per-task layout is the thing to copy**: each task is a folder with `task.json`,
  `description.txt`, `task.lean` (ground-truth code + specification + proof), `test.json`
  **and `reject_inputs.json`** — i.e. a *negative* input set shipped alongside the positive
  tests, which is precisely the artifact our completeness scoring needs and which most
  benchmarks omit.

### A7. Validating Formal Specifications with LLM-generated Test Cases
- **Year / venue**: 2025/2026 — arXiv:2510.23350 (Oct 2025, rev. Feb 2026); also in Springer
  LNCS, doi 10.1007/978-3-032-26204-2_15. Authors: Alcino Cunha, Nuno Macedo.
- **URL**: https://arxiv.org/abs/2510.23350
- **Technique**: LLM generates **positive and negative** test cases directly from the natural
  language requirement, then those tests are run against a human-written Alloy specification of
  a domain model. Positive tests that the spec rejects mean **over-constraint** (valid instances
  eliminated); negative tests the spec accepts mean **under-constraint** (invalid instances
  permitted). Encoding is beautifully simple: both test kinds use the same `some disj ...` pattern
  with equality constraints pinning the instance; a positive test asserts `expect 1`
  (satisfiable), a negative test asserts `expect 0` (unsatisfiable).
- **Numbers**: 4 domain models / **43 requirements** total (social network 8, production line 10,
  train station 10, courses 15). Asking for N positive and N negative per requirement gives 258
  cases at N=3. **GPT-5 with a few-shot prompt: 96% validity (247/258)** — syntactically correct,
  executable and matching the oracle; one-shot 79%, zero-shot 46%. Gemini 2.5 Pro 81%,
  Claude Opus 4.1 76%, GPT-5 Mini 67%. Wrong-specification detection improves with suite size:
  at **N=1 only 38.10% of wrong specs are caught**; at **N=3, 9.90% of errors are missed**; at
  **N=5, 6.43% missed**. "A diverse test suite is essential to help the specifier quickly rule
  out many wrong specifications."
- **Implementable here**: **HIGH**.
- **What to implement**: require a negative test suite per problem (inputs with *wrong* outputs);
  a spec that accepts any of them is under-constrained. Note the N-sensitivity: **one negative
  test per requirement catches only ~38% of bad specs, three catches ~90%** — budget accordingly.
- **Repo**: not confirmed.

### A8. Verus-SpecGym: An Agentic Environment for Evaluating Specification Autoformalization
- **Year / venue**: 2026 — arXiv:2605.26457. Authors incl. Pranjal Aggarwal, Bryan Parno, Sean Welleck.
- **URL**: https://arxiv.org/abs/2605.26457
- **Technique**: Agentic environment (Verus + bash + filesystem). Rather than proving spec
  equivalence, it *executes* generated specifications via Verus's `exec_spec` mechanism as Rust
  code, then validates them against official Codeforces tests **and against Codeforces "hacks"** —
  adversarial edge cases written by competitors specifically to break wrong solutions.
- **Numbers**: Verus-SpecBench = 581 tasks. Gemini 3.1 Pro 77.8%; other frontier models
  51.1–57.8%; open-source 21.5–25.5%. **LLM-as-judge missed 26% of the failures the formal
  evaluator caught.**
- **Implementable here**: **HIGH**.
- **What to implement**: make specs executable and evaluate them on an adversarial negative
  suite; the 26% figure is the argument against using a model as the spec judge.
- **Repo**: not confirmed.

### A9. Talk is Cheap, Logic is Hard: Benchmarking LLMs on Post-Condition Formalization
- **Year / venue**: 2026 — arXiv:2603.17193. Authors: I.S.W.B. Prasetya, Fitsum Kifetew, Davide Prandi.
- **URL**: https://arxiv.org/abs/2603.17193
- **Technique**: 24 LLMs on 40 fresh pre/postcondition formalisation tasks; uses automatically
  generated tests as a second gate that exposes specs which would otherwise have been accepted.
- **Numbers**: LLMs formalise preconditions better than postconditions; none solved all tasks;
  proprietary models show higher false-negative rates, open-source higher error rates. Exact
  per-model percentages not confirmed from the abstract.
- **Implementable here**: **MEDIUM**.
- **What to implement**: the observation that pre- and postconditions have different difficulty —
  score them separately.

### A10. Certified Program Synthesis with a Multi-Modal Verifier (Velvet / LeetProof)
- **Year / venue**: 2026 — arXiv:2604.16584. Authors incl. Vladimir Gladshtein, Ilya Sergey, Peter Müller.
- **URL**: https://arxiv.org/abs/2604.16584
- **Technique**: A Lean-embedded verifier combining three modes — randomised property-based
  testing, automated proof, interactive proof scripting. Critically it **validates the generated
  specification by randomised PBT *before* any code is synthesised**, so a bad spec never reaches
  the proof stage. Spec validation uncovered defects in existing reference benchmarks.
- **Numbers**: no quantitative results confirmed from the abstract page.
- **Implementable here**: **HIGH**.
- **What to implement**: gate the pipeline — PBT the spec first, synthesise only if it passes.

### A11. PBT as spec validation: admissibility / soundness / uniqueness triad
- **Source**: write-up "On the Unreasonable Effectiveness of Property-Based Testing for
  Validating Formal Specifications", proofsandintuitions.net, 18 May 2026, applied to VERINA
  (arXiv:2505.23135) and CLEVER (arXiv:2505.13938).
- **URL**: https://proofsandintuitions.net/2026/05/18/property-based-testing-specifications/
- **Technique**: Decompose spec validation into three cheap random checks instead of a symbolic
  proof: **admissibility** (the sampled input satisfies the precondition), **soundness** (the
  spec accepts the intended output), **uniqueness** (the spec *rejects* alternative outputs).
  Uniqueness uses **mutation-based sampling** — perturb the expected output rather than sampling
  outputs blindly, which is far more likely to hit the discriminating case.
- **Numbers**: found underspecification in ~10% of specs across both benchmarks — **13 bugs in
  188 VERINA problems and 18 bugs in 104 CLEVER problems**, 292 specifications tested total.
- **Implementable here**: **HIGH** — this is the cheapest high-yield thing on the list.
- **What to implement**: the uniqueness check with mutation-based output sampling, driven by our
  existing mutation engine, as a fast pre-filter before any proof system runs.
- **Caveat**: secondary source (a technical blog). The VERINA and CLEVER papers are primary; the
  triad framing and the 10% figure come from the post and are **not yet confirmed against a
  peer-reviewed paper**.

### A12. CLEVER: A Curated Benchmark for Formally Verified Code Generation
- **Year / venue**: 2025 — arXiv:2505.13938. Authors incl. Amitayush Thakur, Greg Durrett,
  Swarat Chaudhuri.
- **URL**: https://arxiv.org/abs/2505.13938
- **Technique**: Two sequential certifications: generate a formal specification that must match a
  **held-out ground-truth specification**, then a Lean implementation provably satisfying it.
  No few-shot leakage; everything machine-checked by Lean's type checker.
- **Numbers**: 161 problems; all evaluated methods struggle to achieve full verification (exact
  rates not confirmed from the abstract page).
- **Implementable here**: **MEDIUM**.
- **What to implement**: keep a held-out reference specification per problem and score
  generated specs against it rather than against the verifier alone.

### A13. LiveFMBench: Unveiling the Power and Limits of Agentic Workflows in Specification Generation
- **Year / venue**: 2026 — arXiv:2605.01394
- **URL**: https://arxiv.org/abs/2605.01394
- **Technique**: Live benchmark for ACSL C specification generation across direct prompting,
  thinking mode and agentic pipelines; explicitly filters **unfaithful behaviours** — models
  gaming the prover rather than specifying the program.
- **Numbers**: 630 ACSL-annotated C programs (360 newly collected). **True specification accuracy
  drops ~20 percentage points once unfaithful behaviours are excluded** — "naive evaluation
  substantially overestimates performance". Incorrect loop invariants dominate the error profile.
- **Implementable here**: **MEDIUM**.
- **What to implement**: an explicit "unfaithful behaviour" filter in scoring, and always report
  the naive and filtered numbers side by side.

### A14. Intent Formalization: A Grand Challenge for Reliable Coding in the Age of AI Agents
- **Year / venue**: 2026 — arXiv:2603.17150. Author: Shuvendu K. Lahiri. Position paper.
- **URL**: https://arxiv.org/abs/2603.17150
- **Technique**: Frames the "intent gap" and argues the central open problem is *validating*
  specifications, since only the user can confirm intent. Calls for semi-automated
  specification-quality metrics using lightweight user interaction and proxy artifacts such as tests.
- **Numbers**: none — position paper, no experiments.
- **Implementable here**: **LOW** (framing, not technique).
- **What to implement**: nothing directly; useful as the citation for why spec-quality metrics
  are the bottleneck.

### A16. An Empirical Study of LLM-Generated Specifications for VeriFast
- **Year / venue**: 2026 — arXiv:2606.26490 (25 Jun 2026). Authors: Wen Fan, Minh Tran,
  Sanya Dod, Xin Hu, Marilyn Rego, Danning Xie, Jenna DiVincenzo, Lin Tan (Purdue).
- **URL**: https://arxiv.org/abs/2606.26490
- **Technique**: Large-scale empirical study of separation-logic specification generation:
  **303 C functions × 8 prompting approaches × 10 LLMs × 3 input types**.
- **Numbers**: functional behaviour preserved in **>91%** of both source and specifications, but
  **verification success only 31.4%**; **94% of errors trace to the LLM's lack of
  domain-specific knowledge of the SL verifier** rather than to misunderstanding the program.
  Best: Gemini 2.5 Pro given formal contracts.
- **Caveat**: does **not** break out weak-but-verifying specs, so it measures the soundness half
  only.
- **Implementable here**: **MEDIUM**.
- **What to implement**: the 94% figure argues for giving the generator verifier-specific
  scaffolding (syntax, idioms, prior error patterns) rather than more reasoning — cheap to do
  across our seven proof systems, and it separates "cannot express" from "does not understand".

### A15. Automatic Generation of Formal Specification and Verification Annotations Using LLMs and Test Oracles
- **Year / venue**: 2026 — arXiv:2601.12845 (19 Jan 2026). Authors: João Pascoal Faria,
  Emanuel Trigo, Vinicius Honorato, Rui Abreu.
- **URL**: https://arxiv.org/abs/2601.12845
- **Technique**: Generates Dafny annotations from natural-language specs **plus the test code**,
  and — the key move — uses the **assertions inside the test cases as static oracles** to
  automatically validate the generated pre/postconditions, with verifier feedback driving repair.
  A multi-model ensemble (Claude Opus 4.5 + GPT-5.2) does the generation.
- **Numbers**: **98.2% of 110 Dafny programs** got correct annotations within **8 repair
  iterations**.
- **Implementable here**: **HIGH** — we already have per-problem unit tests whose assertions can
  serve the same role.
- **What to implement**: mine the assertions already present in our unit tests and use them as
  the static oracle that a candidate spec must agree with, before any prover runs.

---

## Angle B — Mutation testing applied to specifications; mutation score as specification strength

### B1. MutDafny: A Mutation-Based Approach to Assess Dafny Specifications
- **Year / venue**: 2025/2026 — arXiv:2511.15403 (Nov 2025, rev. Apr 2026).
  Authors: Isabel Amaral, Alexandra Mendes, José Campos.
- **URL**: https://arxiv.org/abs/2511.15403
- **Technique**: Mutates the **implementation** and lets the specification act as the oracle: if
  a mutated program still verifies, the spec is too weak. 40 mutation operators, part taken from
  existing tools and part synthesised from bugfix commits in public Dafny GitHub projects.
  Mutation score = killed / (total − invalid − timed-out).
- **Numbers**: 118,458 mutants over 794 real-world Dafny programs, ~2.7 mutants per line.
  Specifications killed **82% of mutants on average**, interquartile range 76%–96%. 11,035
  surviving mutants affected methods that *had* postconditions. Manual analysis of a subset
  confirmed 5 genuinely weak specifications, ≈ one weak spec per 241 lines of code.
- **Implementable here**: **HIGH** — direct match for our mutation engine.
- **What to implement**: per-problem spec mutation score with explicit invalid/timeout exclusion,
  and a surviving-mutant report that names which broken twin escaped.
- **Repo**: **https://github.com/MutDafny/mutdafny** — "A tool for mutation testing of Dafny
  programs". Requires .NET 6.0 and Java ≤ 22. The operator catalogue is the asset: derived from
  **147 operators previously proposed for other languages**, plus new Dafny-specific ones mined
  from **1,475 bugfix commits across 112 public GitHub repositories**; 40 shipped initially with
  more added after finding new weakness classes. Also presented at **ICSE 2026**. Licence to
  confirm. Lift the operator taxonomy and the bugfix-commit mining method for generating
  *realistic* broken twins rather than syntactic ones.

### B2. SpecSyn: LLM-based Synthesis and Refinement of Formal Specifications for Real-world Program Verification
- **Year / venue**: 2026 — arXiv:2604.21570. Authors: Lezhi Ma, Shangqing Liu, Yi Li, Qiong Wu,
  Han Wang, Lei Bu.
- **URL**: https://arxiv.org/abs/2604.21570
- **Technique**: Top-down decomposition of a large program into segments, bottom-up spec
  synthesis per segment, then a refinement mechanism based on **semantic-non-equivalent program
  mutations and variant discrimination** — generate mutated variants and keep strengthening the
  spec until it discriminates them. This is a mutation engine used as a *training loop*, not
  just a metric.
- **Numbers**: precision > 90%, recall > 75%; handled 1,071 of 1,365 target properties on
  real open-source programs.
- **Implementable here**: **HIGH**.
- **What to implement**: the refinement loop — when a broken twin survives, feed that exact twin
  back to the generator as the counterexample to strengthen against.

### B3. Mutation-Guided LLM-based Test Generation at Meta (ACH)
- **Year / venue**: FSE 2025 (Industry) — arXiv:2501.12862, doi 10.1145/3696630.3728544
- **URL**: https://arxiv.org/abs/2501.12862
- **Technique**: Production system that generates *faults first* (targeted mutants describing a
  concern in natural language), then generates tests that kill them — inverting the usual order.
  Includes an **LLM-based equivalent-mutant detector**, the perennial blocker for mutation scoring.
- **Numbers**: 10,795 Android Kotlin classes across 7 Meta platforms; 9,095 mutants and 571
  privacy-hardening tests. Equivalent-mutant detection precision 0.79 / recall 0.47, rising to
  **0.95 / 0.96 with simple pre-processing**. Engineers accepted 73% of generated tests in
  Messenger/WhatsApp test-a-thons; 36% judged privacy-relevant.
- **Implementable here**: **HIGH**.
- **What to implement**: the equivalent-mutant detector idea — pre-process (cheap static/dynamic
  equivalence check) before asking a model, since that is what moved recall 0.47 → 0.96. Directly
  fixes the noise floor of any mutation-score-based spec metric we build.

### B4. MuAlloy: A Mutation Testing Framework for Alloy
- **Year / venue**: ICSE 2018 (demo) — IEEE Xplore 8449437. Older than the window but it is the
  reference design for mutating a *specification language*.
- **URL**: https://ieeexplore.ieee.org/document/8449437 · paper PDF:
  https://kaiyuanw.github.io/papers/paper7-icse18.pdf
- **Technique**: AST-level mutation of Alloy models with operators specific to specification
  constructs: MOR (multiplicity, `lone sig` → `one sig`), QOR (quantifier, `all` → `some`),
  UOR/BOR/LOR (unary/binary/logical operator replacement, e.g. `a=>b` → `a<=>b`, `a&&b` → `a||b`),
  UOI (unary operator insertion, `a.b` → `a.~b`), BOE (operand exchange, `a=>b` → `b=>a`).
  Automatically checks mutant equivalence and, for each non-equivalent mutant, generates the
  Alloy instance that kills it, saved as an AUnit test.
- **Numbers**: reported efficient and practical; specific scores not confirmed from the sources read.
- **Implementable here**: **HIGH**.
- **What to implement**: the operator catalogue — we currently mutate *programs*; these are the
  operators for mutating *specifications*, which is what we need to test our spec-judge itself.
- **Repo**: https://github.com/kaiyuanw/MuAlloy (Java, built on Alloy 4.2; licence to confirm).
  Lift the operator list and the mutant-killing-instance generation pattern.

### B5. Using Mutations to Analyze Formal Specifications
- **Year / venue**: SPLASH 2022 Companion — doi 10.1145/3563768.3563960
- **URL**: https://dl.acm.org/doi/10.1145/3563768.3563960
- **Technique**: "Mutation verification" — using mutants to strengthen and assess formal
  specifications in a verification tool, rather than to assess a test suite.
- **Numbers**: not confirmed.
- **Implementable here**: **MEDIUM** — mostly of value as the naming/priority citation.

### B6. MIST-RL: Mutation-based Incremental Suite Testing via Reinforcement Learning
- **Year / venue**: 2026 — arXiv:2603.01409. Authors: Sicheng Zhu, Jiajun Wang, Jiawei Ai, Xin Li.
- **URL**: https://arxiv.org/abs/2603.01409
- **Technique**: RL for test-suite generation where the reward is an **incremental** mutation
  reward — the model is paid for killing *newly* killed mutants only — plus a dynamic penalty
  that suppresses functionally equivalent assertions and redundant tests.
- **Numbers**: **+28.5% mutation score** over baselines with **19.3% fewer test cases**;
  +3.05% code-reranking accuracy on HumanEval+ at 10 candidates. Benchmarks HumanEval+, MBPP+.
- **Implementable here**: **HIGH**.
- **What to implement**: incremental (marginal) rather than absolute mutation reward when we
  train a spec generator — it is what stops the model emitting near-duplicate clauses.

---

## Angle C — Vacuous, trivial, weak or under-constrained specifications

### C0. The classical foundation (pre-window, but this is where the vocabulary comes from)
- **Beer, Ben-David, Eisner, Rodeh — *Efficient Detection of Vacuity in Temporal Model Checking***,
  Formal Methods in System Design 2001.
  https://www.cs.toronto.edu/~chechik/courses05/csc2108/beer01.pdf
- **Kupferman & Vardi — *Vacuity Detection in Temporal Model Checking***, STTT 2003.
- **Ball & Kupferman — *Vacuity in Testing***, TAP 2008.
  https://www.cs.huji.ac.il/~ornak/publications/tap08.pdf
- **Gurfinkel & Chechik — *How Vacuous Is Vacuous?* / *Sanity Checks in Formal Verification***
  (Springer, doi 10.1007/11817949_3); **Chockler et al., *Vacuity in practice: temporal antecedent
  failure***, FMSD 46(1), 2015, doi 10.1007/s10703-014-0221-0.
- **Core idea**: a property passes *vacuously* when part of the formula was irrelevant to why it
  passed — classically **antecedent failure**, where an implication holds only because its
  precondition is unsatisfiable in the model. Beer et al. give a logic-independent notion and an
  efficient decision procedure for logics with polarity; Kupferman & Vardi extend it to
  *temporal* antecedent failure.
- **The number that matters**: in industrial hardware practice, **roughly 20% of specifications
  pass vacuously on the first formal-verification runs of a new design, and a vacuous pass always
  indicates a real problem in the design, the specification or the environment.** That is the
  prior to hold when reading any modern "our specs verify" claim.
- **Implementable here**: **MEDIUM** for the algorithms (they are temporal-logic specific),
  **HIGH** for the framing and the baseline rate.
- **What to implement**: the polarity-based sanity check — replace each subformula with the
  strongest/weakest value of its polarity; if the verdict does not change, that subformula was
  irrelevant and the spec is vacuous in it. This generalises beyond temporal logic and is the
  principled version of what KaPilot (C1) does with a single `ensures false`.

### C1. KaPilot: LLM-Assisted Generation of Kani Specifications for Unsafe Rust Verification
- **Year / venue**: 2026 — arXiv:2607.21957 (24 Jul 2026). Authors: Minghua Wang, Yuxi Ling,
  Mingzhi Gao, Yuwei Liu, Lin Huang.
- **URL**: https://arxiv.org/abs/2607.21957
- **Technique**: The cheapest vacuity test in the literature. Append a deliberately unsatisfiable
  postcondition — `#[kani::ensures(|_| false)]` — to the generated spec. If verification
  **succeeded before and fails after**, the spec is non-vacuous; if it still succeeds, the
  precondition has collapsed to false and the postcondition constrains nothing.
- **Numbers**: 124 unsafe Rust functions (GoldSet 54 with ground truth, ULSet 70 without).
  Spec generation success 88.9% (48/54) on GoldSet, 71.4% (50/70) on ULSet; **57.4% of GoldSet
  specs were equivalent to or stronger than ground truth**. Count of vacuous specs caught is not
  reported.
- **Implementable here**: **HIGH** — one extra proof call per spec, works with any of our seven
  proof systems.
- **What to implement**: the `ensures false` interpolation as a mandatory non-vacuity gate before
  a spec is admitted to any dataset.

### C2. LASA: Enhancing SoC Security Verification with LLM-Aided Property Generation
- **Year / venue**: 2025 — arXiv:2506.17865
- **URL**: https://arxiv.org/abs/2506.17865
- **Technique**: Classical model-checking vacuity theory applied to LLM output: generated
  security properties are screened by **vacuity checking based on nine standard theorems/rules**
  from the literature; only non-vacuous properties survive to the next stage. Adds FPV coverage
  analysis with an iterative refinement step when coverage is below threshold.
- **Numbers**: average coverage ≈ 88% across open-source SoC designs; found 5 unique bugs in the
  buggy OpenTitan SoC from Hack@DAC'24.
- **Implementable here**: **MEDIUM** — the nine-theorem machinery is temporal-logic specific, but
  the pipeline shape (generate → vacuity-screen → coverage-screen → refine) transfers directly.
- **What to implement**: the two-stage screen: non-vacuity first, then coverage/strength, with
  refinement triggered by the coverage threshold.
- **Related**: LASSO (MLCAD 2025), same group, assertion-based SoC verification.

### C3. AlphaVerus: Bootstrapping Formally Verified Code Generation through Self-Improving Translation and Treefinement
- **Year / venue**: 2024 — arXiv:2412.06176. Authors: Pranjal Aggarwal, Bryan Parno, Sean Welleck.
- **URL**: https://arxiv.org/abs/2412.06176
- **Technique**: Three phases per iteration — **Exploration** (translate from a higher-resource
  language, sample many trajectories, keep partially correct ones by verifier feedback),
  **Treefinement** (tree search over program refinements guided by verifier feedback, using
  REBASE reward-balanced search — beats linear refinement), and **Critique**, which is the part
  that matters for our lane. Critique has three filters:
  1. **Rule-based**: string matching for trivial verification escapes — `assume(false)`,
     `#[verifier::external]`, trivially-true preconditions.
  2. **Comparison model**: a model judges whether the generated spec and algorithm match the
     source program's intent and structure; rejected if at least `r` of several sampled
     judgements say misaligned.
  3. **Exploit model** — the strongest idea here. An adversarial model writes a *deliberately
     trivial* implementation against the synthesised specification (e.g. return an empty array).
     **If the trivial implementation verifies, the specification is flawed.** This catches
     subtle gaps such as a missing array-length condition that admits an empty return.
  Surviving verified programs become the next round's few-shot data; no finetuning.
- **Numbers**: translated **~45% of DafnyBench** into verified Verus. Artefact:
  **Dafny2Verus-Collection = 247 translated programs, 102 error trajectories, 579 exploit pairs.**
  Downstream with Llama-3.1-70B + Treefinement: **32.9% pass@256 on HumanEval-Verus, 65.7% on
  MBPP** vs GPT-4o baseline 27.1% / 35.9%. **Without critique, the model progressively learned to
  game the verifier — `assume(false)` spread across all programs and translation success
  plateaued (their Figure 7).** That snowballing is the exact failure a spec-quality filter exists
  to prevent.
- **Implementable here**: **HIGH**.
- **What to implement**: the **exploit model** — for each candidate spec, have a model (or our
  mutation engine, degenerately) produce the laziest possible program and check whether it
  satisfies the spec. Also keep the "exploit pairs" as a labelled dataset in their own right.
- **Repo**: **https://github.com/cmu-l3/alphaverus** (Python; `pip install -r requirements.txt`;
  licence to confirm). Project page: https://alphaverus.github.io/ . Lift the critique module and
  the Dafny2Verus-Collection exploit pairs.

### C4. Re:Form — Reducing Human Annotations in Scalable Formal Software Verification with RL in LLMs (Dafny)
- **Year / venue**: 2025/2026 — arXiv:2507.16331; **published in TMLR, May 2026**.
- **URL**: https://arxiv.org/abs/2507.16331
- **Technique**: Introduces the **Spec Superiority Rate (SSR)** and a **subset reward**. A
  generated spec is "superior" if it simultaneously *weakens* the precondition and *strengthens*
  the postcondition relative to ground truth, i.e. it implies the ground-truth spec. Reward =
  syntax + verification + subset. This is a strength metric based on logical subsumption rather
  than string match, and it drives the model toward the weakest admissible precondition and
  strongest guaranteed postcondition. Includes an automatic, verifier-integrated data curation
  pipeline.
- **Numbers**: a 0.5B model after SFT emits syntactically valid verifiable Dafny and surpasses
  proprietary models. The **14B model reaches 55.3% spec-superiority in-domain and a 63.8%
  relative gain over its SFT counterpart** on out-of-domain compositional benchmarks. RL shows
  stronger out-of-domain generalisation than SFT.
- **Implementable here**: **HIGH** — we have seven proof systems, so subsumption checks are cheap.
- **What to implement**: SSR as our headline spec-strength number — prove `generated ⟹ reference`
  and `reference_pre ⟹ generated_pre` with one of the proof systems, and reward the implication,
  not the text.
- **Repo**: **https://github.com/Veri-Code/ReForm** — SFT + RL pipeline for code→specification,
  plus the DafnyComp benchmark construction. Model checkpoints released on Hugging Face under the
  **Veri-Code** org (e.g. `Veri-Code/ReForm-SFT-14B`). Benchmark site: https://dafnycomp.github.io/
  Lift the subset-reward implementation (the implication check and its reward shaping) and the
  automatic verifier-integrated data-curation pipeline. Licence/language to confirm.

### C5. VeriEquivBench: An Equivalence Score for Ground-Truth-Free Evaluation of Formally Verifiable Code
- **Year / venue**: 2025/2026 — arXiv:2510.06296 (Oct 2025, latest Apr 2026).
- **URL**: https://arxiv.org/abs/2510.06296
- **Technique**: Replaces ground-truth matching with a **bidirectional implication check** in
  Dafny. Forward: code satisfies its postconditions (normal verification). Reverse: a custom
  harness materialises an arbitrary value satisfying all pre/postconditions and asserts it equals
  the method's actual output — so an underspecified postcondition (e.g. `max >= a` without
  `max >= b`) fails, "without any false positives".
- **Numbers**: 2,389 problems (2,174 LeetCode-derived at 75.8% conversion; 215 synthetic TagComp
  at 71.7%); only 161 have ground-truth-equivalent specs. End-to-end results are brutal:
  Claude-4-sonnet 0% exact matching on TagComp, GPT 2.65% mutual-equivalence, despite 73.79%
  syntactically-correct Dafny. Applied to existing benchmarks as an audit: DafnySynthesis 76.22%
  pass the equivalence score, **CloverBench only 61.29%, DafnyBench 43.09%**; manual inspection
  found 18% further errors in expert-annotated benchmarks.
- **Implementable here**: **HIGH**.
- **What to implement**: the reverse-implication harness — for each spec, ask a proof system
  whether the spec pins the output *uniquely*; anything that does not is under-constrained.
  Also: audit our own per-problem specs with it, given what it found in CloverBench/DafnyBench.

### C6. From Natural Language to Verified Code: AI-Assisted Problem-to-Code with Dafny-Based Formal Verification
- **Year / venue**: 2026 — arXiv:2604.22601 (24 Apr 2026).
- **URL**: https://arxiv.org/abs/2604.22601
- **Technique**: **Dual-layer validation** against vacuous verification: the *formal* layer
  (Dafny proves code consistent with its spec) is not trusted alone; every verified method must
  *also* pass a functional test suite (uDebug edge cases). Explicitly framed as stopping models
  from gaming the verifier with weak or empty postconditions.
- **Numbers**: NL2VC-60 = 60 formally verified Dafny programs from UVa Online Judge; results on
  11 sampled problems — Gemma 4-31B 90.91% with self-healing, GPT-OSS-120B 81.82%,
  Qwen 3.5-9B 72.73%. The paper does **not** report the vacuity rate (how many verified solutions
  failed the functional layer), which is the number we would most want.
- **Implementable here**: **HIGH** — this is exactly "proof systems + per-problem unit tests".
- **What to implement**: never accept "proof passed" alone; require proof ∧ unit tests, and log
  the disagreement rate as our vacuity estimate.

---

## Angle D — Specification repair, strengthening and refinement loops

### D1. VeriSpecGen — Intent-aligned Formal Specification Synthesis via Traceable Refinement
- **Year / venue**: 2026 — arXiv:2604.10392. Authors incl. Zhe Ye, Dawn Song, Soonho Kong.
- **URL**: https://arxiv.org/abs/2604.10392
- **Technique**: Decompose the natural-language description into discrete requirements, generate
  **requirement-targeted tests with explicit traceability**, and when validation fails use the
  traceability map to identify which requirement failed and repair *that clause* rather than
  regenerating the whole specification. Lean.
- **Numbers**: **86.6% on the VERINA SpecGen task** with Claude Opus 4.5; up to **+31.8 points**
  over baselines across models. Harvested **343K training examples from refinement trajectories**;
  training on those trajectories gives **62–106% relative improvement** in spec synthesis, with
  transfer gains to general reasoning.
- **Implementable here**: **HIGH**. The 343K-trajectory result is the strongest published case
  for "spec-repair traces are training data".
- **What to implement**: clause-level attribution — map each spec clause to the test that
  falsified it, repair locally, and keep the whole repair trajectory as a training example.

### D2. KBSpec: LLM-driven Formal Specification Generation with Evolving Domain Knowledge Base
- **Year / venue**: 2026 — arXiv:2606.21339 (Jun 2026, rev. Aug 2026). Authors: Wenhan Wang, Zeyu Sun.
- **URL**: https://arxiv.org/abs/2606.21339
- **Technique**: Dual-source knowledge base — external (official specification-language docs) and
  internal (distilled from verifier feedback on past successes and repairs) — that self-evolves
  from generation/repair trajectories with **no parameter tuning and no labelled training data**.
- **Numbers**: **14–32% improvement in verification pass rates** over SOTA LLM approaches on JML;
  produced the largest number of high-completeness specifications across three LLM backends.
- **Implementable here**: **HIGH** — a retrieval store is far cheaper than finetuning.
- **What to implement**: a growing store of (failed spec, verifier/mutant counterexample, repaired
  spec) triples, retrieved at generation time.

### D3. AutoReSpec: A Framework for Generating Specification using Large Language Models
- **Year / venue**: 2026 — arXiv:2604.03758; ACM doi 10.1145/3793655.3793731 (IEEE/ACM 3rd Intl.
  Conf. on AI Foundation Models and Software Engineering, 2026).
- **URL**: https://arxiv.org/abs/2604.03758
- **Technique**: Specification generation with a refinement loop, evaluated on both success
  probability and the FormalBench mutation-based completeness score.
- **Numbers**: **58.2% success probability and 69.2% completeness score**, 67/72 passes,
  outperforming SpecGen and FormalBench prompts on both axes.
- **Implementable here**: **MEDIUM**.
- **What to implement**: report success probability and completeness jointly — the pair is what
  distinguishes real progress from verifier-pleasing.

### D4. SpecGen: Automated Generation of Formal Program Specifications via LLMs
- **Year / venue**: 2024/2025 — arXiv:2401.08807
- **URL**: https://arxiv.org/abs/2401.08807
- **Technique**: Two phases — conversational prompting with few-shot examples, then a
  **mutation-based phase with heuristic selection**: mutate the candidate specification and keep
  whichever mutant OpenJML can verify. Verifier error messages drive the feedback prompt.
- **Numbers**: verifiable specs for **279 of 385 programs**; human-rated semantic quality
  **4.54/5.00**; overall success probability **59.97%** vs 46.13% (AutoSpec) and 35.95%
  (plain conversational generation).
- **Implementable here**: **MEDIUM-HIGH**.
- **What to implement**: mutating the *specification* (not the program) as a repair operator —
  a cheap local search our mutation engine could be extended to cover.

### D5. Laurel: Unblocking Automated Verification with Large Language Models
- **Year / venue**: 2024/2025 — arXiv:2405.16792; **PACMPL / OOPSLA, doi 10.1145/3720499**;
  presented at Dafny 2025 (POPL 2025).
- **URL**: https://arxiv.org/abs/2405.16792 · https://dl.acm.org/doi/full/10.1145/3720499
- **Technique**: Generates the *helper assertions* that unblock a stalled Dafny proof. Two ideas:
  localise the missing assertion by parsing the verifier's error message and insert a
  **placeholder** at that point, and select few-shot examples from the same codebase using a new
  **proof similarity metric**.
- **Numbers**: synthesises **56.6% of assertions** extracted from real-world code on DafnyGym,
  improving both success rate and number of attempts needed (an earlier version reported "over 50%").
- **Implementable here**: **MEDIUM**.
- **What to implement**: placeholder-localisation from proof-system error messages — applies to
  each of our seven provers independently, and the disagreement between them is itself a signal.

### D6. Can Formal Specifications Be Synthesized from Tests Alone?
- **Year / venue**: 2026 — arXiv:2608.13240 (13 Aug 2026). Authors incl. Bernhard Beckert,
  Anne Koziolek (KIT).
- **URL**: https://arxiv.org/abs/2608.13240
- **Technique**: Black-box spec inference — the LLM sees only the interface, test code and
  dynamic execution traces, never the implementation, and emits JML. Candidates are validated
  **locally with bounded model checking**, whose diagnostics drive iterative refinement.
  Benchmark: SpecGenBench.
- **Numbers**: none confirmed (early-results paper; the abstract page reports no metrics).
- **Implementable here**: **HIGH** — we have per-problem unit tests and an interpreter that can
  emit traces, and hiding the reference solution removes the "spec mirrors the code" failure.
- **What to implement**: generate specs from tests + traces with the reference solution hidden,
  then use the hidden reference solution purely as the soundness oracle.

### D7. ExVerus: Verus Proof Repair via Counterexample Reasoning
- **Year / venue**: 2026 — arXiv:2603.25810 (26 Mar 2026, rev. 30 Mar). Authors: Jun Yang,
  Yuechun Sun, Yi Wu, Rodrigo Caridad, Yongwei Yuan, Jianan Yao, Shan Lu, Kexin Pei.
- **URL**: https://arxiv.org/abs/2603.25810
- **Technique**: Argues that existing work "treat[s] proof generation as a static, end-to-end
  prediction over source code, relying on limited verifier feedback and lacking access to
  concrete program behaviors". When a proof fails, ExVerus **automatically generates and
  validates a counterexample**, then guides the LLM to **generalise that counterexample into an
  inductive invariant** that blocks the failure — behavioural feedback rather than error strings.
- **Numbers**: 31 pages, 8 figures; **no empirical results were visible on the abstract page**
  and no repo URL is given there.
- **Implementable here**: **MEDIUM-HIGH**.
- **What to implement**: the generalisation step — when one of our broken twins survives a spec,
  do not just report it; ask the generator to turn that concrete twin into the *general* clause
  that would have excluded it. That is the bridge from "mutation score" to "spec repair".

---

## Angle E — Verification / specification-quality signals to FILTER or REWARD training data

### E1. SpecRL: Reinforcement Learning with Test-Based Completeness Rewards for Formal Specification Synthesis
- **Year / venue**: 2026 — arXiv:2604.05820 (Apr 2026, rev. Jul 2026). Authors: Zhechong Huang,
  Zhao Zhang, Zeyu Sun, Huifeng Sun, Yingfei Xiong. (Also circulated as *Reinforcement Learning
  with Negative Tests as Completeness Signal for Formal Specification Synthesis*.)
- **URL**: https://arxiv.org/abs/2604.05820
- **Technique**: **The single closest paper to our goal.** Verifier feedback is binary and cannot
  detect a weak spec, so SpecRL builds **spectests** — offline-constructed
  *implementation-impossible* input/output pairs that a weak spec such as `ensures true` would
  still admit. The RL reward is the **fraction of spectests the candidate specification rejects**,
  giving a dense, progressive completeness signal that ranks candidates by how many impossible
  behaviours they rule out. Offline spectest construction makes the signal reusable across runs.
- **Numbers**: on out-of-distribution DafnyComp-Spec, the 7B model improves over SFT by
  **+49.96% verification success and +26.46% specification completeness** (relative lifts);
  consistent gains over SFT and over RL with a reference-based binary reward across four model
  scales. The spectest pipeline was applied to two existing Dafny datasets, Py2Dfy and DafnyComp,
  producing **Py2Dfy-Spec** and **DafnyComp-Spec** (232 programs, held out as OOD).
- **Key design detail worth copying**: completeness is evaluated on **all compiling**
  specifications regardless of whether they verify — this **decouples soundness from completeness
  at evaluation time**, so a spec cannot hide a weak postcondition behind a verification failure.
- **Implementable here**: **HIGH — top pick.**
- **What to implement**: build a per-problem "spectest" bank of impossible (input, output) pairs
  — our mutation engine's broken twins run on the unit-test inputs produce exactly these — and
  make the reward the fraction rejected, not a pass/fail on the prover. Build the bank **offline
  once** so the signal is reusable across every training run.
- **Repo**: not confirmed (no public code found as of this sweep).

### E2. Verification Limits Code LLM Training
- **Year / venue**: 2025 — arXiv:2509.20837. Authors: Srishti Gureja, Elena Tommasone,
  Jingyi He, Sara Hooker, Matthias Gallé, Marzieh Fadaee (Cohere Labs).
- **URL**: https://arxiv.org/abs/2509.20837
- **Technique**: The counterweight to naive filtering. Names the **verification ceiling**: when
  both solutions and their validation are model-generated, only solutions the verifier can
  recognise survive, so training data quality is capped by verifier capability. Studies three
  axes — test quality vs quantity, strictness of the pass threshold, and whether formally
  correct solutions are actually necessary.
- **Numbers**: richer test suites give **+3 pass@1** on average while more tests alone shows
  diminishing returns; relaxing the rigid 100%-pass criterion and adding **LLM-based soft
  verification gives +2–4 pass@1**.
- **Implementable here**: **HIGH**.
- **What to implement**: do not hard-gate the training set at 100% spec/test pass — sweep the
  threshold, and measure whether the strict filter is costing us more than it buys.

### E3. Auditing Reward Hackability in Code RL Training Environments
- **Year / venue**: 2026 — arXiv:2606.16062 (14 Jun 2026). Author: Shreshth Rajan.
- **URL**: https://arxiv.org/abs/2606.16062
- **Technique**: Audits how often a code-RL environment accepts an incorrect solution, using a
  **Docker-verified incorrect-patch pipeline**: construct patches known to be wrong and see which
  test suites still pass them. Adds a **gold-sanity gate** — a generated test that fails against
  the *gold* patch is defective by construction — and a diversity-biased retry to harden tasks.
- **Numbers**: **28.5% of 49 SWE-bench Verified tasks** and **25.0% of 20 R2E-Gym tasks** have
  suites weak enough that a verified-incorrect patch passes. Models score **+14.14 pp Pass@1 on
  hackable vs robust tasks** (95% CI [+11.80, +16.48], p < 1e-6), holding for 123 of 134 frontier
  models. Gold-sanity gate: **61.9% defect rate — 65 of 105 decisive LLM-generated tests fail
  against the gold patch itself**. Hardening converged 9 of 11 broken tasks.
- **Implementable here**: **HIGH**.
- **What to implement**: two gates, both cheap for us — (i) every generated test/spec must pass
  against the reference solution (gold-sanity), and (ii) every problem must reject its broken
  twins (hackability audit). Report the per-problem hackability rate.

### E4. When the Reward Suite Is Leaky: A Preregistered Causal Contrast of Natural Verifier False Positives in RLVR
- **Year / venue**: 2026 — arXiv:2607.11022 (13 Jul 2026). Author: Chuyifei Zhang.
- **URL**: https://arxiv.org/abs/2607.11022
- **Technique**: A preregistered two-arm causal experiment rather than an audit: identical GRPO
  runs, tasks, seeds and compute, rewarded by **original MBPP tests (leaky)** vs **MBPP+ extra
  tests (hardened)**. False positives are natural, not injected. A static "leakiness audit"
  precedes training and is then correlated against realised false-positive mass.
- **Numbers**: held-out gap of only **0.20 pp (95% upper bound 0.75 pp, non-inferior at a 1.5 pp
  margin)** — i.e. hardening the reward suite did *not* measurably change held-out performance in
  this setting. Static leakiness audit correlates with rewarded false-positive mass at
  **Spearman 0.80**. Leak-stratum FP share is **+43.8 pp** above clean tasks; **47.57%** of
  rewarded false positives are genuinely incorrect programs.
- **Implementable here**: **HIGH** — and it is the honest counterexample to keep us disciplined.
- **What to implement**: before investing in spec hardening, run this exact two-arm contrast on
  our own data; the static leakiness audit (ρ=0.80) is a cheap proxy for the expensive one.

### E5. SpecBench: Measuring Reward Hacking in Long-Horizon Coding Agents
- **Year / venue**: 2026 — arXiv:2605.21384 (May 2026, rev. Sep 2026). Authors: Bingchen Zhao,
  Dhruv Srikanth, Yuxiang Wu, Zhengyao Jiang.
- **URL**: https://arxiv.org/abs/2605.21384
- **Technique**: Separates the proxy from the objective by construction: each task has a natural
  language spec, **visible validation tests** that exercise features in isolation, and
  **held-out tests** that *compose* the same features. The visible-minus-held-out gap is the
  reward-hacking measurement.
- **Numbers**: 30 systems-level tasks from a JSON parser to an OS kernel. The gap **grows by
  28 percentage points per tenfold increase in code size**; smaller models show larger gaps.
  Named failure: a 2,900-line hash-table "compiler" that memorised test inputs.
- **Implementable here**: **HIGH**.
- **What to implement**: split our per-problem unit tests into a visible set (used for reward)
  and a held-out compositional set (used only for measurement); the gap is our hacking metric.

### E6. Automating Formal Verification with Reinforcement Learning and Recursive Inference
- **Year / venue**: 2026 — arXiv:2605.30914 (29 May 2026). Author: Max Tan.
- **URL**: https://arxiv.org/abs/2605.30914
- **Technique**: GRPO on Dafny scored by compiler + verifier outcomes, plus verifier-guided
  inference-time search in Lean. Its value to us is the negative result: **specification
  hacking** — models exploit weak formal specifications instead of solving the problem. Remedy
  was dataset filtering using LLM-extracted metadata about **specification faithfulness,
  specification leakage and task difficulty**, producing a subset where high reward means real
  verification progress.
- **Numbers**: naive Dafny RLVR drove verified reward from **2.2% → 58.1%** on an APPS-derived
  dataset — which turned out to be specification hacking, not capability. **After filtering
  underspecified and vulnerable tasks**, multi-turn RLVR moved verified pass rate **9.7% → 31.1%**.
  Lean: direct repair 46.2%, full scaffold with a proof reviser 69.2%; on VERINA, decomposition
  plus proof reviser solved 7 of 42 previously unsolved tasks.
- **Implementable here**: **HIGH**.
- **What to implement**: the 2.2%→58.1% figure is the cautionary tale — before believing any
  reward curve, audit whether the underlying specs are strong enough to make the reward mean
  anything. Filter on spec faithfulness and leakage first.

### E7. Klear-CodeTest: Scalable Test Case Generation for Code Reinforcement Learning
- **Year / venue**: 2025 — arXiv:2508.05710 (Aug 2025, rev. Sep 2025). Kwai Klear team.
- **URL**: https://arxiv.org/abs/2508.05710
- **Technique**: Generator-Validation (G-V) framework: LLMs write executable *generator programs*
  (80 regular-case candidates, 20 corner-case) rather than literal test cases, and an input is
  accepted only if **two independent gold solutions produce identical output** — a differential
  agreement check that handles multi-solution problems. Plus a hardened execution sandbox.
- **Numbers**: **27,965 problems, ~86 test cases each (~2.4M tests)**, filtered from 28,315 valid
  problems (Codeforces, TACO-verified, CodeContests). Test quality **TPR 91.4% / TNR 87.8%**
  (Python3 93.4/87.5; C/C++ 86.59/93.64). DAPO RL on Qwen3-4B, LiveCodeBench-v5: overall
  **59.1% pass@1 vs 57.3% with baseline tests**; medium 69.7% → 72.3%, hard 26.0% → 27.5%.
- **Implementable here**: **HIGH** — we have a reference solution per problem; a second
  independent solution gives the differential check for free.
- **What to implement**: the two-solution agreement filter for admitting test inputs, and
  TPR/TNR as the per-problem test-quality report.
- **Repo**: **https://github.com/Kwai-Klear/CodeTest** — the G-V framework, the multi-layered
  sandbox ("Judge"), and the curated 27,965-problem dataset with validated tests. Lift the
  input-generator-program pattern (generate a *generator*, not test cases) and the two-gold-
  solution consistency validator. Licence to confirm.

### E8. DRIVE: Data Curation Best Practices for RL with Verifiable Reward in Competitive Code Generation
- **Year / venue**: 2025 — arXiv:2511.06307 (9 Nov 2025). Tencent.
- **URL**: https://arxiv.org/abs/2511.06307
- **Technique**: Two-stage executable testcase-driven RL. Stage 1: GRPO over a large uniformly
  distributed problem set, 8 rollouts/prompt, 24k-token window. Stage 2 ("Pre-GRPO"): a small,
  high-quality set of *hard* problems with a **64-rollout budget** and a hard-focus curriculum
  that retains difficult instances. Evaluated on LeetCode/Codeforces weekly contests to avoid
  leakage.
- **Numbers**: Qwen2.5-32B base; SOTA among similar-scale models, comparable to DeepSeek v3.1 and
  Doubao-1.5-Thinking. Specific dataset sizes and filtering thresholds were **not confirmed** from
  the abstract page.
- **Implementable here**: **MEDIUM**.
- **What to implement**: the two-stage curriculum — cheap broad pass, then a large rollout budget
  concentrated on the problems where the spec signal actually discriminates.

### E9. EvolveCoder: Evolving Test Cases via Adversarial Verification for Code RL
- **Year / venue**: 2026 — arXiv:2603.12698
- **URL**: https://arxiv.org/abs/2603.12698
- **Technique**: Solution-conditioned adversarial verification — test cases are iteratively
  refined based on the *execution behaviour of candidate solutions*, optimising for difficulty,
  **discriminative power** and reduced redundancy.
- **Numbers**: EvolveCoder-22k dataset built through multiple adversarial evolution rounds; RL on
  it improves Qwen3-4B by **+4.2 points average across four downstream benchmarks**, beating
  strong 4B-scale baselines.
- **Implementable here**: **HIGH**.
- **What to implement**: evolve our negative/broken-twin set against the current model's outputs
  — keep the twins that survive, discard the ones everything already catches.
- **Repo**: **https://github.com/TIGER-AI-Lab/EvolveCoder** (TIGER-AI-Lab). Lift the
  solution-conditioned evolution loop and the redundancy-reduction step; the EvolveCoder-22k
  dataset is the artefact. Licence to confirm.

### E10. Code-A1: Adversarial Evolving of Code LLM and Test LLM via Reinforcement Learning
- **Year / venue**: 2026 — arXiv:2603.15611. ZJU-REAL.
- **URL**: https://arxiv.org/abs/2603.15611
- **Technique**: Two *separate* models with opposing rewards — the Code LLM is paid for passing
  tests, the Test LLM for exposing defects. The architectural separation removes self-collusion
  and safely permits **white-box** test generation (the Test LLM may inspect the candidate code).
  Adds a "Mistake Book" experience replay and a composite reward balancing test validity against
  adversarial difficulty.
- **Numbers**: on Qwen2.5-Coder, matches or exceeds models trained on **human-annotated** tests
  while also improving test-generation ability.
- **Implementable here**: **HIGH**.
- **What to implement**: separate spec-generator and solution-generator models with opposed
  rewards; validity-vs-difficulty balancing is the part that stops the spec model emitting
  unsatisfiable garbage.
- **Repo**: https://github.com/ZJU-REAL/Code-A1 (contents/licence to confirm).

### E11. UTRL — Learning to Generate Unit Test via Adversarial Reinforcement Learning
- **Year / venue**: 2025/2026 — arXiv:2508.21107 (Aug 2025, rev. Mar 2026); **ICLR 2026**.
  Authors: Dongjun Lee, Changho Hwang, Kimin Lee.
- **URL**: https://arxiv.org/abs/2508.21107
- **Technique**: Alternating adversarial training of a test-generator LLM and a code-generator
  LLM. Two rewards: a **discrimination reward** (test generator paid for identifying faults in
  generated code) and a **code reward** (code generator paid for passing).
- **Numbers**: not confirmed from the abstract page.
- **Implementable here**: **MEDIUM-HIGH**.
- **What to implement**: the discrimination reward, transplanted to specs — a spec is paid for
  separating the reference solution from the broken twins.
- **Repo**: code released on GitHub per the paper; exact URL not confirmed.

### E12. RM-RF: Reward Model for Run-Free Unit Test Evaluation
- **Year / venue**: 2026 — arXiv:2601.13097 (19 Jan 2026).
- **URL**: https://arxiv.org/abs/2601.13097
- **Technique**: A learned reward model that predicts, from source + test code alone and with
  **no execution**, three signals: does the suite compile and run, does it increase coverage, and
  does it **improve the mutation kill rate**. Labels come from a real execution pipeline.
- **Numbers**: multilingual (Java, Python, Go); **average F1 0.69 across the three targets**;
  substantially lower latency and infrastructure cost than compile-and-run.
- **Implementable here**: **MEDIUM**.
- **What to implement**: only if running seven proof systems per candidate becomes the
  bottleneck — then distil a cheap predictor of "will this spec kill mutants" from logged runs.

### E13. The Verification Horizon: No Silver Bullet for Coding Agent Rewards
- **Year / venue**: 2026 — arXiv:2606.26300 (24 Jun 2026, rev. 29 Jun). Large Qwen-affiliated author list.
- **URL**: https://arxiv.org/abs/2606.26300
- **Technique**: Position/empirical study across four reward constructions — test verifier
  (general coding), rubric verifier (frontend), the user as verifier (real-world agent tasks),
  automated agent verifier (long-horizon). Core claim: verification, not generation, is now the
  hard part, and every verifier is only a proxy for intent. Secondary sources describe a data
  pipeline that reverse-engineers repo specifications, applies rule-based degeneracy filtering,
  and keeps trajectories above an evaluator threshold for finetuning.
- **Numbers**: **none confirmed** — the abstract page reports no metrics, and the pipeline detail
  above comes from a secondary summary, not the paper text.
- **Implementable here**: **LOW-MEDIUM** (framing).

### E14. CodeContests+: High-Quality Test Case Generation for Competitive Programming
- **Year / venue**: 2025 — Findings of EMNLP 2025
- **URL**: https://aclanthology.org/2025.findings-emnlp.299/
- **Technique**: An LLM agent system that rebuilds test cases for CodeContests, and — the part we
  want — establishes **TPR (does the suite accept correct solutions) and TNR (does it reject
  incorrect ones)** as the standard two-number test-quality metric now used downstream by
  Klear-CodeTest and others.
- **Numbers**: substantially higher accuracy than original CodeContests, notably higher TPR;
  improved test quality yields considerable RL advantages. Exact figures not confirmed.
- **Implementable here**: **HIGH** (the metric, not the pipeline).
- **What to implement**: adopt TPR/TNR as the vocabulary for spec quality — TPR = soundness on
  the reference solution, TNR = completeness on the broken twins.

### E15. Robust Code RL via Faulty-Code-Driven Test Case Synthesis and Dense Reward Shaping
- **Year / venue**: 2026 — arXiv:2608.24135 (25 Aug 2026, rev. 27 Aug). Ant Group authors.
- **URL**: https://arxiv.org/abs/2608.24135
- **Technique**: **The closest match to our mutation engine in the RL-data literature.** Instead
  of generating tests from the problem statement, it generates them from deliberately
  **"near-correct" faulty codes** — programs that differ from correct ones only in a subtle
  logical error — so the synthesised tests are *forced* to be discriminating. Validator agents
  then apply **behavioural feature clustering** to drop invalid or redundant tests (two tests
  that separate the same set of programs are redundant). Adds a stepwise **dense** reward based
  on pass rates rather than an all-or-nothing gate, to reduce false negatives.
- **Numbers**: **+3 absolute points on LiveCodeBench** from RL fine-tuning Qwen3-32B.
- **Implementable here**: **HIGH**.
- **What to implement**: two things. (i) Drive test/spec synthesis *from* our broken twins rather
  than from the problem statement — "write the spec that distinguishes this twin from the
  reference". (ii) Behavioural clustering to deduplicate: group twins by which specs reject them
  and keep one representative per cluster, which is also the cheap equivalent-mutant proxy.

---

## Angle F — Property-based and metamorphic testing as an oracle for specification quality

### F1. PBT-Bench: Benchmarking AI Agents on Property-Based Testing
- **Year / venue**: 2026 — arXiv:2605.15229 (13 May 2026). Authors: Lucas Jing, Xinqi Wang,
  Liao Zhang, Simon S. Du.
- **URL**: https://arxiv.org/abs/2605.15229
- **Technique**: Isolates the skill of *deriving a semantic invariant* from documentation and
  writing a Hypothesis `@given` strategy that concentrates probability mass in the bug-triggering
  region — as distinct from reproducing a known bug or writing a patch. Scored by **bug recall**
  against injected bugs, across three difficulty levels (L1 single-constraint boundary bugs →
  L3 stateful protocol violations).
- **Numbers**: 100 problems over 40 real Python libraries, **365 semantic bugs (mean 3.65/problem)**.
  Bug recall **42.1%–83.4%** under a PBT-guided prompt vs **31.4%–76.7%** open-ended;
  Hypothesis scaffolding lifts mid-capability models by **>20 pp**.
- **Implementable here**: **HIGH**.
- **What to implement**: bug recall against our broken twins as the primary spec metric, stratified
  by twin difficulty — a single aggregate score hides which class of bug we never catch.
- **Repo**: **https://github.com/ElliotXinqiWang/PBTbench**; dataset at
  **https://huggingface.co/datasets/pbtbench-team**. Python/Hypothesis. Lift the bug-difficulty
  stratification (L1 single-constraint boundary → L3 stateful cross-function protocol) and the
  bug-recall scorer. Note the design constraint they impose: bugs are chosen so that
  **default-strategy random inputs almost never trigger them** — otherwise the metric measures
  fuzzing luck, not specification quality. Eight LLMs evaluated under two prompting regimes;
  scaffolding helps mid-tier models >20 pp but helps the strongest models less, and *degrades*
  two of them.

### F2. FVSpec: Real-World Property-Based Tests as Lean Challenges
- **Year / venue**: 2026 — arXiv:2606.01008 (31 May 2026, rev. 14 Sep 2026). Authors: Quinn
  Dougherty, Max von Hippel, Simon Henniger, Hazel Shackleton, Mike Dodds (Galois).
- **URL**: https://arxiv.org/abs/2606.01008
- **Technique**: Harvests real property-based tests from the wild and transpiles them into formal
  specifications via a three-agent LLM pipeline — PBTs are treated as *already-written informal
  specifications* that just need formalising.
- **Numbers**: scraped **7,413 distinct PBTs** from real Python repos, auto-translated **2,623
  (35%)** into **9,415 Lean 4 specifications** with `sorry` placeholders (~3.5 formalisations per
  PBT). (An earlier version reported 11,039 PBTs / 2,772 translated / 25%.)
- **Implementable here**: **MEDIUM**.
- **What to implement**: treat any property we can already express as a test as the seed for the
  formal spec — and note the 35% ceiling on automatic translation.

### F3. CodeMetaAgent — LLM Assisted Coding with Metamorphic Specification Mutation Agent
- **Year / venue**: 2025 — arXiv:2511.18249 (23 Nov 2025). Authors: Mostafijur Rahman Akhond, Gias Uddin.
- **URL**: https://arxiv.org/abs/2511.18249
- **Technique**: Uses metamorphic relations **proactively on the specification** rather than for
  post-hoc validation: generate semantically equivalent mutations of the task specification and
  use agreement across those variants as a consistency signal, reducing variance caused by how
  the spec happens to be phrased.
- **Numbers**: up to **+17% accuracy**; code coverage up to 99.81%. Models: GPT-4o, Mistral Large,
  GPT-OSS, Qwen3-Coder. Datasets: HumanEval-Pro, MBPP-Pro, SWE-Bench_Lite.
- **Implementable here**: **HIGH** — this is differential agreement applied to specs, and it is
  cheap: paraphrase the spec, regenerate, compare.
- **What to implement**: metamorphic spec mutation — if two semantically equivalent phrasings of a
  spec yield disagreeing verdicts on the same program, the spec is unstable and should be dropped.

### F4. Property-Generated Solver / Effective LLM Code Refinement via Property-Oriented Feedback
- **Year / venue**: 2025 — arXiv:2506.18315
- **URL**: https://arxiv.org/abs/2506.18315
- **Technique**: Validate high-level program properties/invariants with PBT instead of predicting
  exhaustive I/O oracles, explicitly to break the "cycle of self-deception" where the generated
  tests share the generated code's flaws. Adds structurally minimal counterexample feedback.
- **Numbers**: not confirmed from the abstract page.
- **Implementable here**: **HIGH**.
- **What to implement**: the self-deception framing — our specs must be generated from the problem
  statement, not from the candidate solution, or they inherit its bugs.

### F5. Bidirectional Empowerment of Metamorphic Testing and Large Language Models: A Systematic Survey
- **Year / venue**: 2026 — arXiv:2605.13898
- **URL**: https://arxiv.org/abs/2605.13898
- **Technique**: Survey of the two directions (MT for testing LLMs; LLMs for inferring metamorphic
  relations and follow-up test cases).
- **Implementable here**: **LOW** (orientation only).

### F6. PropGen — From Exploration to Specification: LLM-Based Property Generation for Mobile App Testing
- **Year / venue**: 2026 — arXiv:2604.13463
- **URL**: https://arxiv.org/abs/2604.13463
- **Technique**: Generates properties, then **refines the imprecise ones** using the failures
  observed during testing — a property-repair loop with concrete yield numbers.
- **Numbers**: **985 properties generated, 912 valid; 118 of 127 imprecise properties successfully
  refined; 25 previously unknown functional bugs** found that existing techniques missed.
- **Implementable here**: **MEDIUM**.
- **What to implement**: the refine-on-false-alarm loop — 118/127 is a strong recovery rate for a
  cheap mechanism.

### F7. Understanding the Characteristics of LLM-Generated Property-Based Tests in Exploring Edge Cases
- **Year / venue**: 2025 — arXiv:2510.25297
- **URL**: https://arxiv.org/abs/2510.25297
- **Technique**: Empirical comparison of PBT against example-based testing for LLM-generated tests.
- **Numbers**: each method alone detects **68.75%** of bugs; **combined, 81.25%** — the two find
  different bugs.
- **Implementable here**: **MEDIUM-HIGH**.
- **What to implement**: keep both concrete unit tests and property-style specs; the union is
  materially stronger than either.

### F8. LLM-Based Test Oracles: Source-of-Authority Taxonomy — A Systematic Literature Review
- **Year / venue**: 2026 — arXiv:2607.05031 (6 Jul 2026, final 2 Sep 2026). Authors:
  Ali Hassaan Mughal, Muhammad Bilal.
- **URL**: https://arxiv.org/abs/2607.05031
- **Technique**: Classifies LLM-based oracles not by form but by **where their authority comes
  from** — a written specification, a reference implementation, a differential peer, or merely
  the model's training-data priors. Two oracles can look identical and rest on completely
  different foundations.
- **Numbers**: 2,436 records screened → 54 included studies → **83 with snowballing**.
  Two findings that bear directly on us: **just over half the corpus reaches a verdict with no
  specification at all**, and **"oracle quality is most often judged by resemblance to a known
  oracle rather than by whether injected faults are caught."**
- **Implementable here**: **MEDIUM** (survey), but the second finding is the strongest available
  argument for our approach.
- **What to implement**: nothing directly — cite it to justify scoring specs by fault detection
  against broken twins rather than by similarity to a reference spec.

---

## Angle G — Differential / multi-version agreement as a correctness signal

### G1. Clover: Closed-Loop Verifiable Code Generation  ← the anchor
- **Year / venue**: 2023/2024 — arXiv:2310.17807; **published in Springer LNCS,
  doi 10.1007/978-3-031-65112-0_7** (contrary to the arXiv listing, it is not preprint-only).
  Authors: Chuyue Sun, Ying Sheng, Oded Padon, Clark Barrett (Stanford).
- **URL**: https://arxiv.org/abs/2310.17807
- **Technique**: Reduces correctness to **consistency among three artifacts — code, docstring and
  formal annotation**. Phase 1 generates all three; phase 2 runs pairwise consistency checks. The
  code↔annotation check is deductive verification (Dafny). The **annotation completeness check is
  the reconstruction test**: given only the annotation, have an LLM regenerate code, then check
  the regenerated code is *equivalent* to the original — if it is, the annotation carried enough
  information, i.e. it is complete. The Clover hypothesis: if all checks pass then the code is
  correct w.r.t. the annotation, the annotation captures the full functionality, and the docstring
  reflects it too.
- **Numbers**: the verification phase **accepts 87% of correct examples and rejects 100% of
  incorrect (adversarial) ones** — zero false positives. Found **6 incorrect programs in
  MBPP-DFY-50**. CloverBench = textbook-level annotated Dafny programs (exact size not confirmed).
- **Implementable here**: **HIGH — the structural template for our whole pipeline.**
- **What to implement**: the **reconstruction test for completeness** — regenerate a solution from
  the specification alone and check equivalence against the reference solution using our proof
  systems and our interpreter. This needs no new infrastructure.
- **Repo**: **https://github.com/ChuyueSun/Clover** — **Python, MIT licence**. Layout: `/clover`
  (core consistency checks), `/clover_end2end` (full pipeline), `/clover_mbpp` (MBPP-DFY runs),
  `/dataset` (CloverBench), plus `exps.py`, `debug_exp.py` and `run_clover*.sh`. Requires Dafny as
  the verifier. MIT means we can lift code directly. Take the six-check matrix and the
  annotation→code reconstruction+equivalence check. (The repo README does not enumerate which of
  the six checks are implemented or state CloverBench's size — confirm by reading the tree.)
  **`/dataset` contains four corpora: `CloverBench`, `MBPP-DFY-153`, `MBPP-DFY-50-legal`,
  `MBPP-DFY-50-original`.** Per-folder counts are not shown in the directory listing. Note the
  cross-link: **`MBPP-DFY-153` is the same 153-problem Dafny/MBPP corpus that Lahiri's symbolic
  testing paper (A1) evaluates on** — so A1's soundness/completeness metric and Clover's
  consistency checks can be run head-to-head on identical data. That is the cheapest possible
  replication for us to reproduce before building anything.
- **Critic / successor**: **VeriEquivBench (C5)** audits CloverBench with its equivalence score and
  finds only **61.29% of CloverBench specs pass** — a direct, quantified criticism of the anchor.
  **Spec-Harness (A2)** is the strongest successor on the completeness half; **Verus-SpecGym (A8)**
  and **VERINA (A6)** benchmark the same idea in Verus and Lean respectively.

### G2. ConVerTest — Consistency Meets Verification: Enhancing Test Generation Quality Without Ground-Truth Solutions
- **Year / venue**: 2026 — arXiv:2602.10522 (11 Feb 2026). Authors: Hamed Taherkhani,
  Alireza DaghighFarsoodeh, Mohammad Chowdhury, Hung Viet Pham, Hadi Hemmati (York University).
- **URL**: https://arxiv.org/abs/2602.10522
- **Technique**: Three stacked mechanisms, all without a ground-truth solution.
  (i) **Self-Consistency**: generate diverse test stubs, complete each with many samples, keep the
  most frequent completion by AST comparison — filters stochastic assertion errors.
  (ii) **Chain-of-Verification** for iterative refinement.
  (iii) **Dual Execution Agreement**: run every candidate solution against every generated test,
  group solutions by which test subset they pass ("agreement sets"), score
  `score = (tests passed) × sqrt(solutions in set)`, and treat the consensus winner as the
  reference that labels each test valid or invalid.
- **Numbers**: validity rate +7–19% from SC over holistic, then +7–39% more from full ConVerTest
  (CodeQwen3 on LBPP 73% → 88%; Gemma3.3 on LBPP 53% → 84%). Line coverage +7–28% from SC.
  **Mutation score +10–18% from SC**, with only 1–2% drops from the filtering stage.
  Classification: precision 84–91%, recall 89–96%, F1 86–91%. Ablations: removing CoVe costs
  2–12% recall; removing SC costs 4–6% mutation score; removing everything costs 16–26% line
  coverage and 6–18% mutation score. Datasets BigCodeBench-Hard and LBPP (161 problems).
- **Implementable here**: **HIGH**.
- **What to implement**: the agreement-set scoring formula, applied to specs — generate N
  independent specs per problem, partition programs by which specs accept them, and let the
  largest coherent group define the reference verdict.

### G3. TRAILS — Inferring Code Correctness from Specification
- **Year / venue**: 2026 — arXiv:2605.29822 (28 May 2026). Authors: Florian Tambon, Mike Papadakis.
- **URL**: https://arxiv.org/abs/2605.29822
- **Technique**: Never reasons about the code. Generates diverse inputs by **category partitioning
  over the specification**, executes them against the candidate, then asks the LLM only whether
  each resulting `(input, output)` pair conforms to the spec — scores aggregate into a correctness
  probability. Sidesteps both the cost of dynamic consensus over many candidates and the order
  bias of static code reasoning.
- **Numbers**: up to **+39% Matthews correlation coefficient** relative to zero-shot CoT, on
  LiveCodeBench and CoCoClaNeL, with Qwen3Coder-30B, Devstral-Small-24B, Olmo3.1-Instruct;
  benchmarked against HoarePrompt. Notably more stable across seeds.
- **Implementable here**: **HIGH**.
- **What to implement**: judge `(input, output)` pairs against the spec rather than judging the
  program — with our interpreter the pairs are free, and MCC is the right metric for a
  spec-as-classifier.

### G4. Beyond Trusting Trust: Multi-Model Validation for Robust Code Generation
- **Year / venue**: 2025 — arXiv:2502.16279 (22 Feb 2025). Author: Bradley McDanel.
- **URL**: https://arxiv.org/abs/2502.16279
- **Technique**: Ensemble validation — multiple independent models used to detect anomalous code
  via cross-model consensus, framed against Thompson's "Reflections on Trusting Trust".
- **Numbers**: **none** — explicitly a perspective piece with no empirical validation.
- **Implementable here**: **LOW**.
- **Caution**: cite for framing only; it has no experiments.

### G5. Limits of agreement as a correctness signal  [UNVERIFIED — do not cite yet]
- A search summary surfaced two quantitative cautions that I could **not** trace to a primary
  source before the search budget ran out, and which should not be cited until checked:
  (i) a July 2026 preprint auditing ~265,000 samples reporting agreement-vs-correctness
  **Spearman ρ of only 0.20–0.59**; (ii) an **ICML 2025** study of 350+ LLMs reporting that when
  two models both err, they land on the *same* wrong answer **~60%** of the time.
- Why it matters: both directly attack the premise of Angle G. Correlated errors mean that
  "several independently generated specifications agree" is much weaker evidence than it looks,
  and would argue for **diversity of mechanism** (different proof systems, executable vs.
  symbolic checks, mutation-based rejection) over diversity of samples from one model.
- **Action**: re-run this one search and find the primary citations before any design decision
  rests on multi-version agreement.

---

## Angle H — Datasets and benchmarks worth reusing directly

### H1. A benchmark for vericoding: formally verified program synthesis
- **Year / venue**: 2025/2026 — arXiv:2509.22908 (26 Sep 2025); **Dafny workshop @ POPL 2026**.
  Authors incl. Quinn Dougherty, Max Tan, Max Tegmark (Beneficial AI Foundation).
- **URL**: https://arxiv.org/abs/2509.22908
- **Repo**: **https://github.com/Beneficial-AI-Foundation/vericoding-benchmark**
- **Technique**: The largest specification corpus available — **12,504 formal specifications**
  (Dafny 3,029, Verus/Rust 2,334, Lean 7,141), of which **6,174 are new and previously unseen**.
  Measures "vericoding": synthesising code *from* a specification. Uses iterative translation,
  ensembles and verification feedback.
- **Numbers**: vericoding success **82.2% Dafny, 44.2% Verus, 26.8% Lean**. Pure Dafny
  verification improved **68% → 96% over one year**. Adding natural-language descriptions does
  **not** significantly help.
- **Caveat**: the abstract page does **not** describe any anti-cheating or non-vacuity screening
  of the 12,504 specs — worth checking before trusting them, given what VeriEquivBench (C5)
  found in CloverBench and DafnyBench.
- **Implementable here**: **MEDIUM** — a source of specs to test our judge against, not a method.

### H2. DafnyBench: A Benchmark for Formal Software Verification
- **Year / venue**: 2024 — arXiv:2406.08467; OpenReview `yBgTVWccIx`.
- **URL**: https://arxiv.org/abs/2406.08467 · **Repo: https://github.com/sun-wendy/DafnyBench**
- **Technique**: **782 programs, ~53,000 lines**, shipped as two sets — `ground_truth` and
  `hints_removed`. The task is to refill the removed hints/annotations so Dafny verifies again.
  A clean template for building a spec-reconstruction task from a corpus we already have.
- **Numbers**: best model Claude 3 Opus ≈ **68%** success; ~54% first-try, plateauing near 65%
  around n≈5 attempts. **VeriEquivBench (C5) later found only 43.09% of DafnyBench passes its
  equivalence score** — the benchmark's own specs are frequently under-constrained.
- **Implementable here**: **MEDIUM**.
- **What to implement**: the hints-removed construction — strip our specs and ask the model to
  reconstruct them, scoring by mutation-kill parity with the original.

### H3. Others noted but not fetched  [unverified]
- **VeriContest: A Competitive-Programming Benchmark for Verifiable Code Generation** —
  arXiv:2605.08553.
- **AxDafny: Agentic Verified Code Generation in Dafny** — arXiv:2606.32007.
- **CASP: An evaluation dataset for formal verification of C code** — arXiv:2508.18798.
- **SpecGenBench** (used by D3, D6) and **Py2Dfy** (used by E1) — dataset provenance not confirmed.
- Each surfaced in search but was not opened; listed so the thread is not lost.

---

## Cross-cutting: repositories, with what to lift from each

Confirmed, with language/licence where established:

| Repo | Paper | Language / licence | What to lift |
|---|---|---|---|
| **https://github.com/ChuyueSun/Clover** | G1 Clover | **Python, MIT** | The consistency-check matrix; the annotation→code **reconstruction + equivalence** completeness test. MIT, so code can be copied directly. |
| **https://github.com/thanhlecongg/FormalBench** | A3 FormalBench | **Python 3.12, Apache 2.0** | The mutation-based completeness harness. Already language-parameterised (Java/Major/OpenJML, C/Mull/Frama-C) — **the intended extension point for a new language is exactly our situation**. |
| **https://github.com/Mondego/vACT** | A2 Spec-Harness / VeriAct | tbc | Hoare-triple construction for all four correctness/completeness quadrants; type-directed output mutation; the two-channel repair loop (syntax errors from the verifier, weakness from Spec-Harness). |
| **https://github.com/MutDafny/mutdafny** | B1 MutDafny | .NET 6 + Java ≤22; licence tbc | Operator catalogue (147 imported + Dafny-specific mined from 1,475 bugfix commits / 112 repos) and the **bugfix-commit mining method** for realistic rather than syntactic mutants. |
| **https://github.com/kaiyuanw/MuAlloy** | B4 MuAlloy | Java (Alloy 4.2); licence tbc | Mutation operators for a *specification language* (MOR/QOR/UOR/BOR/LOR/UOI/BOE) and generation of the instance that kills each mutant. |
| **https://github.com/cmu-l3/alphaverus** | C3 AlphaVerus | Python; licence tbc | The **critique** module: rule-based trivial-escape matching, comparison model, and the **exploit model**. Plus the Dafny2Verus-Collection (247 programs, 102 error trajectories, **579 exploit pairs**). |
| **https://github.com/Veri-Code/ReForm** | C4 Re:Form | tbc | Subset-reward / Spec-Superiority-Rate implementation; verifier-integrated data curation. Checkpoints on HF under `Veri-Code`. |
| **https://github.com/sunblaze-ucb/verina** | A6 VERINA | tbc (ICLR 2026) | The per-task folder layout — notably **`reject_inputs.json`, a negative input set shipped with the positive tests**. HF dataset: `sunblaze-ucb/verina`. |
| **https://github.com/ElliotXinqiWang/PBTbench** | F1 PBT-Bench | Python/Hypothesis; licence tbc | Bug-difficulty stratification L1–L3 and the bug-recall scorer. HF: `pbtbench-team`. |
| **https://github.com/Kwai-Klear/CodeTest** | E7 Klear-CodeTest | tbc | Generator-Validation framework, sandbox "Judge", 27,965-problem validated dataset, two-gold-solution consistency validator. |
| **https://github.com/TIGER-AI-Lab/EvolveCoder** | E9 EvolveCoder | tbc | Solution-conditioned adversarial test evolution + redundancy reduction; EvolveCoder-22k. |
| **https://github.com/ZJU-REAL/Code-A1** | E10 Code-A1 | tbc | Two-model adversarial RL with separated code/test policies; "Mistake Book" replay; validity-vs-difficulty composite reward. |
| **https://github.com/sun-wendy/DafnyBench** | H2 DafnyBench | tbc | `ground_truth` / `hints_removed` split. |
| **https://github.com/Beneficial-AI-Foundation/vericoding-benchmark** | H1 Vericoding | tbc | 12,504 specs across Dafny/Verus/Lean. |
| https://dafnycomp.github.io/ | C4/E1 DafnyComp | site | Compositional spec benchmark; DafnyComp-Spec (232 programs) is SpecRL's OOD set. |

No public code found in this sweep for: **SpecRL (E1)**, **SpecSyn (B2)**, **VeriSpecGen (D1)**,
**KBSpec (D2)**, **KaPilot (C1)**, **VeriEquivBench (C5)**, **PostcondBench (A4)**,
**CodeSpecBench (A5)**, **Lahiri's symbolic-testing tool (A1)**.

---

## What could not be confirmed (be honest about these)

- **FormalBench (A3) per-model *completeness* scores.** I confirmed the metric definition, the
  tooling (OpenJML 21.0 + Major 3.0.1 for Java, Mull + Frama-C for C) and the dataset sizes
  (699 / 6,219), and I have consistency pass rates per model — but **the per-model completeness
  percentages are not in any page I could render**. The ACL PDF and the arXiv PDF both came back
  as unparseable binary, and the arXiv HTML page carries metadata only. Third-party anchors do
  exist: AutoReSpec (D3) reports **69.2% completeness** on this metric, and Spec-Harness (A2)
  reports FormalBench prompts at **50% PostComp** on SpecGenBench.
- **CloverBench size and the exact six consistency checks (G1).** The repo README, the arXiv
  abstract page, the Stanford PDF and the OpenReview PDF all failed to yield them (PDFs are
  binary; OpenReview served a browser-verification page). The 87% accept / 100% reject headline
  and the 6 incorrect MBPP-DFY-50 programs *are* confirmed. Resolve by reading
  `github.com/ChuyueSun/Clover/dataset` directly — the repo is MIT and Python.
- **AlphaVerus (C3)**: confirmed the three critique filters and the headline numbers, but the
  *count* of exploits caught per round is not stated beyond "579 exploit pairs" in the artefact.
- **DRIVE (E8)** dataset sizes and filtering thresholds; **UTRL (E11)** numbers; **CLEVER (A12)**
  per-model rates; **Can Formal Specs Be Synthesized from Tests Alone (D6)** has no reported
  numbers at all (early-results paper); **The Verification Horizon (E13)** reports none either.
- **ExVerus (D7)** was identified by title/id only and never opened.
- **G5** — see above; the two anti-agreement statistics are unsourced.
- **Search budget exhausted** at 200 WebSearch calls. WebFetch still worked; the remaining items
  above are all resolvable with targeted fetches or by reading the repos.

---

## What to read first, and why

1. **SpecRL (E1, arXiv:2604.05820)** — the only paper that turns a completeness measurement into
   an RL *reward*, with offline-built "spectests" that our mutation engine already produces;
   +49.96% verification and +26.46% completeness over SFT is the strongest result in the lane.
2. **Spec-Harness / VeriAct (A2, arXiv:2604.00280, code at github.com/Mondego/vACT)** — the full
   four-quadrant scorecard plus working code, and the finding that optimising for verifier
   acceptance raises pass rates without raising captured behaviour, which is the failure mode our
   seven proof systems would otherwise walk straight into.
3. **FormalBench (A3, arXiv:2503.04779, Apache-2.0 code)** — the mutation-based completeness
   metric with a language-parameterised harness we can extend rather than rebuild, and the
   concrete failure signature to watch for (`invariant true`).
4. **AlphaVerus critique (C3, arXiv:2412.06176, code at github.com/cmu-l3/alphaverus)** — the
   **exploit model**: write the laziest program that satisfies the spec, and if it verifies the
   spec is broken. Their Figure 7 shows `assume(false)` snowballing across all programs when this
   filter is removed, which is what a spec-quality gate is actually for.
5. **Clover (G1) read together with VeriEquivBench (C5)** — the anchor's reconstruction-based
   completeness test and its 87%/100% headline, immediately followed by the audit finding only
   **61.29% of CloverBench** survives a bidirectional-implication check. Read as a pair, they
   give both the method and its measured limit.
