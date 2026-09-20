# Open-source repos & tools for LLM-assisted formal verification and spec generation

Research lane: **repositories and tools we can read and lift from** (not just papers).
Compiled 2026-09-20. Every entry below was confirmed by fetching the live GitHub page
unless explicitly marked otherwise.

Our context, for the "what we could lift" lines: a small specification language with an
executable interpreter, seven proof backends (Dafny, Verus, SPARK, Frama-C, Lean 4, Rocq,
F*), per-problem unit tests, a reference solution per problem, and an existing mutation
engine that makes deliberately broken twins.

---

## 1. DafnyBench

- **URL:** https://github.com/sun-wendy/DafnyBench
- **Language:** Dafny (dataset) + Python (eval harness)
- **Licence:** Apache-2.0
- **Activity:** 39 commits, 68 stars, 14 forks. Stable/finished rather than actively
  developed — it is a published benchmark artifact, not a living tool. Not dead, but
  don't expect upstream movement.
- **What it does:** 782 verified Dafny programs scraped from GitHub and deduplicated,
  each shipped in two forms: a `ground_truth` version with all annotations, and a
  `hints_removed` version with every `assert` / `invariant` stripped from method bodies.
  The task is to reconstruct the hints and have Dafny verify the result. Includes an
  `eval/` harness that shells out to Dafny, supports API models, and does
  configurable feedback-iteration loops (re-prompt with the verifier error).
- **Paper:** "DafnyBench: A Benchmark for Formal Software Verification", Loughridge et al.,
  arXiv:2406.08467.
- **Lift:** The **hints-removed / ground-truth pairing plus the error-feedback eval loop**
  is exactly the harness shape we need per backend — steal the loop structure (verify,
  capture Dafny's error text, re-prompt, bounded retries) and the per-program pass/fail
  summary dataframe format. Note it absorbed Clover and dafny-synthesis programs, so
  expect overlap if we use several Dafny benchmarks at once.
- **Evaluate against directly:** Yes — for the Dafny backend. Biggest Dafny corpus available.

## 2. Clover / CloverBench

- **URL:** https://github.com/ChuyueSun/Clover
- **Language:** Python (driver) over Dafny
- **Licence:** MIT
- **Activity:** 96 commits, 49 stars. Research artifact accompanying a CAV'24 paper;
  appears complete but quiet.
- **What it does:** Implements "closed-loop verifiable code generation": instead of
  trusting an LLM's code, it runs **six consistency checks among the three artifacts —
  code, docstring, and formal annotation** (each pair checked in both directions, some by
  the verifier, some by an LLM equivalence judge). The claim is that if all checks pass,
  the code matches the annotation, the annotation is complete w.r.t. the code, and the
  docstring matches both. Reported 87% accept on correct examples, 100% reject on
  adversarial ones. CloverBench is 60 hand-written textbook-level annotated Dafny
  programs with **five variants each: one ground truth and four deliberately
  incorrect/adversarial twins**.
- **Paper:** "Clover: Closed-Loop Verifiable Code Generation", Sun, Sheng, Padon, Barrett;
  arXiv:2310.17807, published at AI Verification (SAIV) 2024 / Springer LNCS 14846.
- **Lift:** This is the closest existing thing to what our mutation engine is for. Lift
  **the six-way consistency-check matrix directly** — it turns our (spec, code, tests,
  broken twin) tuples into a scoring rubric, and its four-adversarial-variants-per-problem
  design is a published precedent for our broken twins. Also lift their LLM-caching layer
  (`exps.py`) to keep eval cost sane.
- **Evaluate against directly:** Yes — CloverBench's 60×5 set is a drop-in
  accept/reject discrimination benchmark for our mutation engine.

## 3. microsoft/verus-proof-synthesis (AutoVerus + VeruSAGE)

- **URL:** https://github.com/microsoft/verus-proof-synthesis
- **Language:** Python (plus Rust/Verus benchmark sources and a Rust parser utility)
- **Licence:** MIT
- **Activity:** 192 commits, 116 stars, open issues and PRs — **the most alive repo in
  this list**, backed by Microsoft Research.
- **What it does:** Two LLM proof-synthesis systems for Verus (Rust). **AutoVerus** runs a
  three-phase pipeline — Inference (few-shot proof candidates), Refinement (targeted
  improvement of promising candidates), Repair (debug remaining verification errors) —
  and proves 137/150 Verus-Bench tasks. **VeruSAGE** is an agentic
  observation-reasoning-action loop aimed at repository-level systems verification.
  Ships `utils/lynette`, a Verus parser utility.
- **Papers:** "AutoVerus: Automated Proof Generation for Rust Code" (arXiv:2409.13082);
  "Leveraging Large Language Models for Automated Proof Synthesis in Rust"
  (arXiv:2311.03739); repo-level work in arXiv:2509.25197.
- **Lift:** Take the **three-phase inference→refinement→repair decomposition** as the
  reference architecture for our Verus backend, and take `lynette` so we don't hand-roll
  Verus AST manipulation. Their few-shot example bank for Verus proof idioms is directly
  reusable prompt material.
- **Evaluate against directly:** Yes — **Verus-Bench** (150 tasks: 11 from CloverBench,
  78 from MBPP, 38 from Diffy, 23 Verus tutorial examples) is the standard Verus target,
  and its CloverBench/MBPP provenance means problems may line up with our own set.
  **VeruSAGE-Bench** (849 repo-level tasks) is far beyond our scope but worth knowing.

## 4. dafny-annotator

- **URL:** https://github.com/metareflection/dafny-annotator
- **Language:** Python
- **Licence:** MIT
- **Activity:** 65 commits, 20 stars. Small academic tool; modest but real.
- **What it does:** Uses an LLM plus search to insert logical annotations (assertions,
  invariants, `decreases` clauses) into Dafny programs until they verify. Ships
  **DafnySynth**, a synthetic data generator built on an extensible *editor* architecture
  that mutates/grows Dafny programs to create training data. Uses DafnyBench as its
  eval set.
- **Paper:** referenced as arXiv:2402.08147 on the repo badge (note: badge number looks
  possibly stale relative to the project; treat the citation as needing a double-check).
- **Lift:** **DafnySynth's editor architecture** is the most relevant piece — it is an
  existing, working design for programmatically generating program variants, which is the
  same machinery class as our mutation engine. Worth reading before we extend ours.

## 5. dafny-synthesis (MBPP-DFY)

- **URL:** https://github.com/Mondego/dafny-synthesis
- **Language:** Python + Dafny
- **Licence:** **GPL-3.0** — note the copyleft; fine for reading and for using the dataset,
  but do not paste their driver code into a permissively-licensed repo of ours.
- **Activity:** 83 commits, 56 stars. FSE-2024 artifact with a reviewed release tag
  (`Artifacts@FSE24-Reviewed`). Finished artifact, not an evolving tool.
- **What it does:** First empirical study of LLMs synthesizing *verifiable* Dafny methods
  from 178 MBPP problems, comparing Contextless / Signature / retrieval-augmented CoT
  prompts. The durable output is the datasets: **MBPP-DFY-153** (153 MBPP problems with
  Dafny specs, verified implementations and tests — 50 hand-written by the authors, 103
  synthesized by GPT-4 and human-checked), plus **MBPP-DFY-50** and **MBPP-san-DFY-228**.
- **Paper:** "Towards AI-Assisted Synthesis of Verified Dafny Methods", Misu et al.,
  FSE 2024 / arXiv:2402.00247.
- **Lift:** MBPP-DFY-153 has the *exact shape of our problem records* — description,
  formal spec, reference solution, tests, one per problem. It is the closest existing
  corpus to our per-problem format and the obvious source for seeding or cross-checking
  our own problem set. Also lift their three-prompt ablation (contextless / signature /
  RAG-CoT) as a ready-made experimental design for measuring how much context a backend
  needs.
- **Evaluate against directly:** Yes, and it is the natural bridge — MBPP problem IDs let
  us line up against Verus-Bench's 78 MBPP tasks too.

## 6. dafny-sketcher

- **URL:** https://github.com/namin/dafny-sketcher
- **Language:** C# (it forks/extends the Dafny language implementation) + tooling
- **Licence:** MIT
- **Activity:** 479 commits, 18 stars. Low stars but a high commit count — an actively
  hacked-on personal/lab research tool (Nada Amin's group), not a stub.
- **What it does:** Piggybacks on the actual Dafny compiler to do interactive
  semi-automated verified program synthesis, combining LLMs with symbolic reasoning. It
  can, e.g., synthesize inductive-proof scaffolding by inspecting the datatype structure
  of a function's parameters. Ships **a CLI, an MCP server, and a VSCode/LSP extension**,
  plus a "verified functional programming" testbed.
- **Paper:** no dedicated paper cited in the README; references the authors' earlier
  VerMCTS work.
- **Lift:** The **MCP server** is the single most directly reusable artifact here — it is
  an existing, working way to expose a proof backend to an LLM agent as a tool, which is
  what we would otherwise hand-roll seven times. Also a good model for symbolic sketching
  (generate proof *structure* from types, let the LLM fill leaves) rather than
  free-generating whole proofs.

## 7. AlphaVerus

- **URL:** https://github.com/cmu-l3/alphaverus
- **Language:** Python (targeting Verus/Rust)
- **Licence:** *not confirmed from the search snippet — verify on the repo page before
  reuse.*
- **Activity:** CMU L3 lab (Sean Welleck's group) artifact for an ICML/ICLR-cycle paper.
- **What it does:** Bootstraps verified code generation **without human data or
  finetuning** by iteratively translating Dafny programs into Verus. Three steps per
  iteration: *Exploration* (sample many translation trajectories, keep partially correct
  ones by verifier feedback), *Treefinement* (tree search over the program space guided by
  verifier errors, keeping ancestors as error-correction exemplars), and *Critique*
  (filter out underspecified or vacuous translations). Bootstraps its own exemplars each
  round.
- **Paper:** "AlphaVerus: Bootstrapping Formally Verified Code Generation through
  Self-Improving Translation and Treefinement", arXiv:2412.06176.
- **Lift:** Two things. (a) **Treefinement** — a concrete tree-search-over-repairs
  algorithm driven by verifier error text, better than our likely naive retry loop.
  (b) The **Critique / vacuity filter** — their explicit machinery for catching
  *underspecified* translations that verify trivially is precisely the failure mode our
  mutation engine and unit tests exist to catch, and their filter is a second, independent
  detector we could run alongside. Also: it is a working **cross-backend translation**
  pipeline (Dafny → Verus), which is directly relevant to having seven backends over one
  spec language.

## 8. Laurel + DafnyGym

- **URL:** artifact on Zenodo, DOI 10.5281/zenodo.14676571 (OOPSLA 2025 artifact);
  DafnyGym dataset site at https://dafnygym.github.io/
  *(I could not confirm a canonical GitHub mirror of the Laurel implementation from
  search — the Zenodo artifact is the reliable pointer. Treat any GitHub URL as
  unverified until checked.)*
- **Language:** Python driver over Dafny
- **Licence:** not confirmed
- **Activity:** published OOPSLA 2025 artifact; DafnyGym has its own project page.
- **What it does:** Automatically generates the *helper assertions* that unblock a stuck
  Dafny proof. Two domain-specific prompting tricks: (1) parse the verifier's error
  message to pick the **location** for a missing assertion and insert a placeholder there,
  and (2) retrieve **qualitatively similar lemmas from the same codebase** via a proof
  similarity metric to use as few-shot examples. Reports generating >50% of required
  assertions in a few attempts. **DafnyGym** is its eval set: Dafny lemmas extracted from
  three real production codebases (the Dafny standard library, AWS's Cedar authorization
  library, and DafnyVMC Monte-Carlo library).
- **Paper:** "Laurel: Unblocking Automated Verification with Large Language Models",
  PACMPL/OOPSLA 2025, doi 10.1145/3720499, arXiv:2405.16792.
- **Lift:** The **error-message-to-assertion-placeholder** trick is cheap and high-value:
  it converts a raw verifier complaint into a *positioned* hole for the LLM to fill,
  which we can implement once per backend. The **proof-similarity retrieval** is a good
  use for our reference solutions — they become the few-shot bank.
- **Evaluate against directly:** DafnyGym is worth it as a *real-world* counterweight to
  our textbook-scale problems, though it is Dafny-only and harder than our set.

## 9. Vericoding — **the single most relevant repo found**

- **URL:** https://github.com/Beneficial-AI-Foundation/vericoding
  (search results also surfaced a `vericoding-benchmark` name; the live repo confirmed
  above is `vericoding` — use that one)
- **Language:** Python tooling over Dafny, Verus and Lean sources
- **Licence:** MIT
- **Activity:** **1,128 commits, actively developed**, 33 stars, paper under ICLR review
  and a Dafny-workshop @ POPL 2026 paper. Alive.
- **What it does:** Defines "vericoding" — generate formally verified code *from a formal
  spec* (as opposed to vibe coding from NL) — and ships the largest benchmark for it:
  **12,504 formal specifications, 3,029 Dafny / 2,334 Verus-Rust / 7,141 Lean**, of which
  6,174 are new unseen problems. Crucially, **each task is decomposed into
  `preamble` / `spec` / `code` components with quality metadata**, and specs are shipped
  compiling-with-`sorry`/`assume false` in the code slot. Also ships construction scripts
  (translation between languages, formatting, quality analysis), an experiments harness
  (55,397 recorded runs across models), and outcome tracking. Reported baselines: 82%
  Dafny, 44% Verus, 27% Lean.
- **Paper:** "A benchmark for vericoding: formally verified program synthesis",
  arXiv:2509.22908.
- **Lift:** Nearly everything. (a) The **preamble/spec/code task decomposition** is the
  data model we need for one spec language across many backends — adopt it rather than
  inventing one. (b) The **cross-language translation scripts in `src/`** are a working
  precedent for emitting one problem into three backends; we need seven, but the shape
  transfers. (c) The **"issues" folder convention** — specs that don't compile kept
  separately from tasks that do — is a cheap quality-gate discipline. (d) Their
  per-model outcome-tracking schema saves us designing a results format.
- **Evaluate against directly:** **Yes, first choice.** It is the only benchmark found
  that spans three of our seven backends with aligned problems, so it measures exactly the
  cross-backend consistency our design claims. Their published per-language success rates
  (82/44/27) are a ready baseline to beat or match.

## 10. AutoSpec+ (Xidian ICTT)

- **URL:** https://github.com/Xidian-ICTT-GZ/AutoSpec
- **Language:** Python, analysing C
- **Licence:** Apache-2.0
- **Activity:** **only 10 commits, 6 stars — thin.** Recently published code dump rather
  than a maintained tool. Read it, don't depend on it.
- **What it does:** Neuro-symbolic ACSL specification synthesis for C. LLM proposes
  contracts, loop invariants and ranking functions; **Frama-C/WP acts as a deterministic
  critic**. Five stages: static analysis → neural generation → formal verification →
  iterative repair → optional termination analysis. Builds an **extended call graph and
  synthesizes specs bottom-up** so each LLM call sees only a proof-relevant slice.
  Supports Gemini/GPT/DeepSeek backends. Claims 91.05% pass@5 on SyGuS, SV-COMP and
  industrial code.
- **Paper:** no citation on the repo page; the AutoSpec line of work is
  "Enchanting Program Specification Synthesis by Large Language Models using Static
  Analysis and Program Verification" (CAV 2024) — confirm the exact paper before citing.
- **Lift:** The **bottom-up call-graph decomposition** is the answer to context limits on
  anything bigger than a single function, and **ranking functions for termination** is a
  detail most LLM spec work skips but that Dafny/SPARK/Frama-C all demand from us.
  This is our best concrete reference for the Frama-C backend specifically.

## 11. SPARK / Ada — **weakest angle; no strong LLM-specific repo exists**

Searched several ways and found no maintained open-source LLM-assisted SPARK
specification tool. What does exist, and is worth having:

- **https://github.com/AdaCore/spark2014** — the SPARK 2014 / GNATprove toolchain itself
  (AdaCore, actively maintained). The docs include a `usage_scenarios` section describing
  **turning test cases into Contract Cases**: each test's input constraint becomes a
  guard, its output constraint the consequence. That is a direct, mechanical route from
  *our per-problem unit tests* to SPARK contracts, and it is the most useful single thing
  found on this angle.
- **https://github.com/tofgarion/spark-by-example** — SPARK 2014 port of "ACSL by
  Example": a corpus of specified-and-proved standard algorithms. Good few-shot material
  and a sanity corpus for the SPARK backend.
- **https://github.com/AdaCore/skills** — AdaCore's own agent-skills plugin, including a
  `gnatprove` skill. Vendor-maintained guidance on driving GNATprove from an agent.
- **https://github.com/agent-sh/ada-spark** — third-party agent skill for idiomatic
  Ada/SPARK (Ada 2022, Alire + GNAT FSF). Unverified depth; treat as prompt material.
- Relevant paper with no strong repo: "Verifying LLM-Generated Code in the Context of
  Software Verification with Ada/SPARK", arXiv:2502.07728.
- **Lift:** the test-case → Contract Cases transformation from the spark2014 user guide,
  and spark-by-example as the few-shot bank. **Plainly: we will be building the SPARK
  backend more from scratch than the others.**

## 12. LeanDojo

- **URL:** https://github.com/lean-dojo/LeanDojo (org: https://github.com/lean-dojo)
- **Language:** Python (plus Lean)
- **Licence:** MIT
- **Activity:** 623 commits, **836 stars** — by far the most-used repo in this list.
  Caveat: the README says **this original version is deprecated in favour of
  LeanDojo-v2** for new projects, so start from v2.
- **What it does:** Two things, both of which we need for a Lean 4 backend. (1) **Data
  extraction** from any Lean GitHub repo — proof states, tactics, premises, file
  dependencies, ASTs. (2) **Programmatic interaction with Lean**: open a theorem, run a
  tactic, get the resulting state back, i.e. a gym-style environment. Compatible with
  Lean 4 v4.3.0-rc2+. LeanDojo-v2 wraps repository tracing, dataset management,
  retrieval-augmented agents, HF fine-tuning and external inference APIs into one toolkit.
- **Benchmark:** **LeanDojo Benchmark 4** — 122,517 theorems/proofs, 259,580 tactics,
  167,779 premises from mathlib4 (on Zenodo with a DOI).
- **Paper:** "LeanDojo: Machine Learning for Theorem Proving in Lean", NeurIPS 2023
  Datasets & Benchmarks.
- **Lift:** The **interaction layer** — do not hand-roll a Lean 4 driver; LeanDojo already
  solves process management, state extraction and timeout handling. Its
  tactic-state-in / tactic-out interface is also the right abstraction to generalise
  across our seven backends (each backend exposes "current obligations" + "apply step").

## 13. Rango (rkthomps/coq-modeling) + CoqStoq

- **URL:** https://github.com/rkthomps/coq-modeling
- **Language:** Python (driving Coq via coq-lsp)
- **Licence:** MIT
- **Activity:** 561 commits, 31 stars. Real, substantial codebase; academic but not a stub.
- **What it does:** Neural proof synthesis for Coq/Rocq using **retrieval augmentation at
  every proof step** — at each step it retrieves relevant premises *and similar proofs
  from the current project* to condition a fine-tuned LLM, so the prover "adapts to its
  environment" rather than relying on frozen training data. Ships a full pipeline:
  data processing, training, evaluation. **CoqStoq** is its benchmark, mined via
  the Coq LSP.
- **Paper:** "Rango: Adaptive Retrieval-Augmented Proving for Automated Software
  Verification", arXiv:2412.14063 (ICSE 2025).
- **Lift:** The **in-project retrieval** idea maps straight onto our setup: our reference
  solutions and their proofs form a per-problem-family corpus, and retrieving the nearest
  solved twin is the cheapest accuracy win available. Also the cleanest example of
  driving a proof assistant through LSP rather than a bespoke wrapper — relevant for the
  Rocq backend. Related: the **LLM4Rocq** org (https://github.com/LLM4Rocq) and
  **CoqPyt**, a Python client for coq-lsp used for mining Coq data.

## 14. MutDafny — mutation testing *of Dafny specifications* (**high value for us**)

- **URL:** https://github.com/MutDafny/mutdafny
- **Language:** C# / .NET — implemented as a **Dafny compiler plugin**, not an external
  text-mangler.
- **Licence:** **not stated on the repo page** — must be resolved before we copy any code.
- **Activity:** 190 commits but only 2 stars. Brand-new (ICSE 2026), essentially unknown.
  Substantial code behind a tiny audience; low risk of it being a stub, high risk of it
  being unmaintained after the paper.
- **What it does:** **Exactly our mutation engine's problem, already solved once for
  Dafny.** It mutates Dafny code and asks whether the *formal specification* still
  verifies. A mutant that survives verification is evidence the spec is too weak — so
  mutation score becomes a **spec-completeness metric** rather than a test-suite metric.
  Implements **55 mutation operators**: arithmetic/relational/conditional/logical/shift
  operator replacement (AOR, ROR, COR, LOR, SOR), boolean-binary replacement (BBR), unary
  operator insertion/deletion, literal and expression value replacement (LVR, EVR),
  method-level mutations (return-value replacement, argument propagation, call
  replacement, variable replacement), collection mutations (initialisation, element
  update, swap, comprehension update), statement-level mutations (deletion, swap, loop
  and case-block modification), and polymorphic reference / accessor-modifier replacement.
- **Paper:** "MutDafny: A Mutation-Based Approach to Assess Dafny Specifications",
  Amaral, Mendes and Campos, ICSE 2026.
- **Lift:** **The 55-operator catalogue is the single most directly liftable artifact we
  found.** Our mutation engine already makes broken twins; this is a published, curated
  taxonomy of *which* breakages are worth making, with the collection and
  comprehension operators (the ones people forget) spelled out. Two further lifts:
  (a) the framing of **mutation score as a spec-completeness number** gives our broken
  twins a headline metric; (b) being a **compiler plugin** rather than a source rewriter
  is the right architecture — it mutates typed ASTs so every mutant is well-formed, which
  is what we would want for our spec language's interpreter.

## 15. Daikon / SpecFuzzer / EvoSpex — oracle & invariant inference

- **Daikon:** https://github.com/codespecs/daikon — **actively maintained** (v5.9.1
  released 2026-09-01), Java, the canonical dynamic likely-invariant detector. Runs a
  test suite and reports invariants that held at every program point.
- **SpecFuzzer:** https://github.com/facumolina/specfuzzer — infers class specifications
  (postconditions, invariants) for Java by **grammar-based fuzzing** of candidate
  assertions, filtered by Daikon against the test suite, then **clustered and ranked by a
  mutation-based mechanism**. Because the candidate space comes from a grammar, it is
  explicitly designed to be **retargeted to a different specification language by
  swapping the fuzzing grammar**. Papers: "Fuzzing Class Specifications" (ICSE 2022,
  arXiv:2201.10874) and an ASE 2023 tool demo.
- **EvoSpex:** evolutionary search for a succinct postcondition that accepts observed
  method behaviour and rejects mutated/deviant behaviour (Molina et al.). Repo under
  https://github.com/facumolina — confirm exact name before use.
- **Lift:** This is the *other* half of our pipeline and the part LLM papers keep
  ignoring. (a) **SpecFuzzer's grammar-based candidate generation is a natural fit for our
  small specification language** — we already have a grammar and an executable
  interpreter, which is precisely what SpecFuzzer needs and what makes retargeting cheap.
  (b) **EvoSpex's accept-observed / reject-mutated objective is the same signal our
  broken twins provide**, so we can score a candidate spec without any LLM in the loop.
  (c) Our **executable interpreter + per-problem unit tests** give us a Daikon-style
  dynamic filter for free: run candidate specs against the tests, discard any that the
  reference solution violates or that a broken twin satisfies.

## 16. Verina (Verifiable Code Generation Arena) — **closest match to our problem record**

- **URL:** https://github.com/sunblaze-ucb/verina · site https://verina.io/
- **Language:** Lean 4 (dataset) + Python (harness)
- **Licence:** Apache-2.0
- **Activity:** only 18 commits but 78 stars, 12 forks, CI workflows, a website and a
  HuggingFace release. Published at ICLR 2026 — current, and the low commit count reflects
  a clean release rather than neglect.
- **What it does:** 189 **manually curated** Lean coding tasks, deliberately modular so
  you can evaluate **code generation, specification generation and proof generation
  separately or in combination** — the only benchmark found that treats spec generation as
  a first-class task with soundness *and* completeness scored. Each datapoint is a
  directory containing `description.txt` (NL task), `task.lean` (ground-truth code +
  spec + proof), `task.json` (metadata, signatures), and **`test.json` plus
  `reject_inputs.json`**. Provenance: 49 problems hand-translated, 59 taken from
  **CloverBench** Dafny instances and translated to Lean, rest curated. Headline result:
  o3 gets 72.6% code correctness, 52.3% spec soundness+completeness, and **4.9% proof
  success** — proofs are the wall.
- **Paper:** "VERINA: Benchmarking Verifiable Code Generation", arXiv:2505.23135,
  ICLR 2026.
- **Lift:** (a) **`reject_inputs.json` is their version of our broken twins** — an
  explicit list of inputs a *correct* spec must reject, used to score spec
  *completeness* (a too-weak spec accepts them). That is a cheaper, test-shaped
  completeness signal than full mutation, and our interpreter can produce it. Steal the
  file format. (b) The **modular code/spec/proof task split** is the evaluation design we
  should copy verbatim — it isolates which of our seven backends is failing and at which
  stage. (c) Its CloverBench lineage means **Verina, CloverBench, Verus-Bench and
  Vericoding share problems**, so one problem set can be scored against four papers.
- **Evaluate against directly:** Yes — best single target for the Lean 4 backend, and the
  only one that scores specification generation the way we care about. Related follow-on:
  **Vero** (repository-level verified code generation, https://vero.verina.io/).

## 17. FVAPPS — unit tests turned into theorems

- **URL:** https://github.com/quinn-dougherty/fvapps ·
  dataset https://huggingface.co/datasets/quinn-dougherty/fvapps
- **Language:** Python pipeline + Lean 4 output
- **Licence:** present in repo but type not shown on the page — confirm before reuse.
- **Activity:** 173 commits, only 7 stars. Published (IEEE/LLM4Code 2025) but little
  community uptake; the *dataset* is the live artifact, the pipeline is a one-shot.
- **What it does:** Takes the APPS competitive-programming dataset and **generalises its
  Python unit tests into Lean 4 theorems stated with `sorry`**. 4,715 samples total,
  1,083 of which passed curation/quality control. Pipeline stages: preprocess APPS
  solutions → two agents generate property tests (Python) and skeleton Lean theorems →
  QA gates (`qa_autoformalize` for faithfulness, `qa_plausible` for non-vacuity) →
  postprocess for release. Sonnet proved 30% and Gemini 18% of 406 theorems from 100
  samples.
- **Paper:** "Proving the Coding Interview: A Benchmark for Formally Verified Code
  Generation", Dougherty & Mehta, arXiv:2502.05714.
- **Lift:** **The unit-test → theorem lifting step is precisely the bridge we need.** We
  already have per-problem unit tests and a reference solution; FVAPPS is the worked
  example of promoting those concrete cases into universally-quantified properties, plus
  the **two QA gates** (is the formalisation faithful? is it non-vacuous?) that stop the
  pipeline emitting theorems that are trivially true. Those two gates belong in our
  generator regardless of backend. Caveat the paper itself makes: the automated pipeline
  lacks human validation, hence the 4,715 → 1,083 curation drop — a warning about how much
  of auto-generated spec data survives scrutiny.

## 18. Dafny's own test generation: DTest and DSpec2Test

- **URL:** https://github.com/dafny-lang/dafny (the `generate-tests` command); DSpec2Test
  landed as PR https://github.com/dafny-lang/dafny/pull/6508
- **Language:** C#
- **Licence:** MIT (Dafny)
- **Activity:** Dafny itself is very actively maintained by AWS. DSpec2Test earned
  **ASE 2026 Available / Functional / Reusable artifact badges**.
- **What it does:** **DTest** drives the SMT solver to produce counterexamples, translates
  them into Dafny unit tests using Dafny's unit-testing and mocking attributes, and —
  critically — **converts method postconditions into runtime oracles**. Evaluated on the
  Dafny utilities library and the AWS Encryption SDK (79% / 62% statement coverage).
  **DSpec2Test** adds a "Spec" mode: instrument an *empty* method body with
  state-capturing annotations, add synthesized DNF/BVA constraints as `assume`s and an
  `assert false` to force the solver to emit a counterexample containing concrete
  input/output pairs — i.e. **generate tests from the specification alone, with no
  implementation**.
- **Papers:** "A Toolkit for Automated Testing of Dafny" (NFM 2023, Amazon Science);
  DSpec2Test at ASE 2026.
- **Lift:** Two direct lifts. (a) **Postcondition → runtime oracle** is the same move our
  executable interpreter makes; DTest shows how to do it inside a proof backend so the
  *same* spec drives both verification and testing. (b) **DSpec2Test's spec-only test
  generation** would let us cross-validate: generate tests from the spec, run them against
  our reference solution, and any disagreement means the spec is wrong — a check that
  needs no LLM and no mutation engine. Also a differential-testing lever across backends
  (same spec, seven backends, compare the generated test sets).

## 19. Etna — evaluation platform for property-based testing, with hand-crafted mutants

- **URL:** https://github.com/jwshii/etna
- **Language:** Python harness driving Coq (QuickChick) and Haskell PBT frameworks
- **Licence:** confirm on repo page
- **Activity:** ICFP 2023 artifact-evaluated; extensible by design. Modest but real.
- **What it does:** A benchmarking platform for comparing property-based testing
  strategies. Five workloads — Binary Search Tree, Red-Black Tree, Simply-Typed Lambda
  Calculus, System F, and IFC — and **over 100 hand-crafted mutations** across them. For
  each mutant, the question is how quickly (and whether) a given PBT strategy finds a
  counterexample. Handles the "technical drudgery of performance measurement" and is
  explicitly built to have new frameworks and workloads slotted in.
- **Paper:** "Etna: An Evaluation Platform for Property-Based Testing (Experience
  Report)", PACMPL/ICFP 2023, doi 10.1145/3607860.
- **Lift:** **Etna is the methodological template for evaluating our mutation engine.** It
  is a published precedent for exactly the experiment we can run: a library of
  deliberately broken twins, a set of strategies, and a measurement of
  time/tests-to-detection rather than a bare pass/fail. Lift (a) the harness design —
  workloads × strategies × mutants, with timing — and (b) the *discipline of hand-crafted
  rather than randomly generated mutants*, which is what makes their results
  interpretable and is the main critique our generated twins will face. Related current
  work worth tracking: "A Declarative Framework for Hand-Crafted Mutation Analysis and
  Management" (arXiv:2603.07065) and **PBT-Bench** (arXiv:2605.15229), benchmarking AI
  agents on property-based testing.

## 20. Lean 4 prover models (open weights + training code)

Not spec-generation tools, but these are the models we would actually call for the
Lean 4 and Rocq backends, and all three ship real code:

- **DeepSeek-Prover-V2** — https://github.com/deepseek-ai/DeepSeek-Prover-V2. Open-weights
  LLM for Lean 4 whole-proof generation; initialisation data from a **recursive
  theorem-proving pipeline** (decompose a goal into subgoals with DeepSeek-V3, solve the
  leaves, recompose). Well-known, high-traffic repo.
- **Goedel-Prover** — https://github.com/Goedel-LM/Goedel-Prover. 57.6% Pass@32 on
  miniF2F, best open-source at release. Follow-on **Goedel-Code-Prover**
  (arXiv:2603.19329) is specifically about **hierarchical proof search for code
  verification** — closer to our use case than the maths provers.
- **Kimina-Prover-RL** — https://github.com/project-numina/kimina-prover-rl. Open
  **training pipeline** (not just weights) for Lean 4 proving, using a structured
  reasoning-then-generation paradigm à la DeepSeek-R1.
- **Lift:** the **recursive goal decomposition** (DeepSeek-Prover-V2) and **hierarchical
  proof search** (Goedel-Code-Prover) are the two search strategies worth implementing
  behind our proof backends; Kimina's RL recipe is the reference if we ever fine-tune on
  our own problem set. Practically: these give us a *local, free* proving option for the
  Lean backend instead of paying per API call across seven backends.

## 21. Goedel-Code-Prover — hierarchical decomposition for *code* verification

- **URL:** https://github.com/goedelcodeprover/Goedel-Code-Prover ·
  weights https://huggingface.co/Goedel-LM/Goedel-Code-Prover-8B ·
  site https://goedelcodeprover.github.io/
- **Language:** Python, Lean 4
- **Licence:** confirm on repo page
- **Activity:** March 2026 release with model card, site and repo. Current.
- **What it does:** Splits code verification into **decompose** then **prove**: break a
  hard verification goal into structurally simpler subgoals before any tactic-level
  proving. The novel bit is a **decomposition score** combining constructive
  justification with structural effectiveness, used *both* as the RL training reward and
  as the inference-time ranking criterion over candidate decompositions. One unified 8B
  policy does both jobs (supervised init → hybrid RL). The repo exposes the pipeline as
  separable stages — **decompose-only, or prove-only from a previously decomposed JSON**.
- **Results (useful to us as a baseline table):** 62.0% over 427 tasks across three Lean
  code-verification benchmarks — **68.8% on Verina, 54.0% on Clever, 62.3% on AlgoVeri** —
  2.6× the strongest baseline and beating neural provers up to 84× larger.
- **Paper:** "Goedel-Code-Prover: Hierarchical Proof Search for Open State-of-the-Art Code
  Verification", Li et al., arXiv:2603.19329.
- **Lift:** (a) **The decompose/prove split with a JSON interchange between them** is the
  right seam for a seven-backend system: decomposition is backend-agnostic and can be done
  once per problem, then each backend only has to discharge leaves. Lift the interface,
  even if not the model. (b) The **decomposition score** is a reusable idea for ranking
  which spec-shaped subgoals to hand out. (c) An 8B model beating 84×-larger ones means
  our backends can plausibly run **locally on the lab GPUs** rather than via API.
- **Evaluate against directly:** their three-benchmark table (Verina / Clever / AlgoVeri)
  is a ready-made comparison set for the Lean 4 backend.

## 22. formally-verified-code-rl — RL environments for C + ACSL + Frama-C

- **URL:** https://github.com/stanleyngugi/formally-verified-code-rl
- **Language:** Python
- **Licence:** confirm on repo page
- **Activity:** described as "first release" — early, small, unproven. Flagging it as
  promising-but-thin rather than a dependable dependency.
- **What it does:** Packages code generation whose correctness is **checked by a formal
  verifier** as **RL environments**; first release targets C + ACSL + Frama-C.
- **Lift:** the **environment wrapper shape** — verifier-as-reward-function, with
  episode/reset/step semantics — is the cleanest way to expose our seven backends to any
  training or search loop, and to our own agent evaluation. Worth reading for the
  interface even if the code is immature.

## 23. CASP — C/ACSL specification-implementation pairs

- **URL:** dataset described in arXiv:2508.18798 (Springer LNCS, AISoLA 2025). *I could
  not confirm a canonical GitHub URL for CASP from search — treat distribution as
  paper/publisher-hosted until verified.*
- **What it is:** Self-contained C functions annotated with ACSL, harvested from **The
  Stack v1/v2** (permissively licensed BigCode corpora), each pair **verified with
  Frama-C** and then **manually inspected**; faulty files repaired automatically and by
  hand. The research-only corpus is 221 train / 47 validation / 48 test examples.
- **Lift:** the **harvest → auto-verify → manual-inspect → repair** construction recipe is
  the quality pipeline we would need if we ever grow our problem set from public code
  rather than authoring it. Its permissive-licence sourcing discipline is also worth
  copying. Related: **FormalSpecCpp** (arXiv:2502.15217), a C++ formal-specification
  dataset built with LLMs, and **AutoACSL** (arXiv:2606.20969), which pairs LLMs with
  code-property-graph static analysis to synthesize ACSL.
- **Evaluate against directly:** plausible small target for the Frama-C backend, though
  it is spec-*given* rather than spec-*generation* shaped.

## 24. AlgoVeri — **aligned multi-backend benchmark; read this one first**

- **URL:** https://github.com/haoyuzhao123/algoveri
- **Language:** Dafny, Verus/Rust and Lean sources + evaluation code
- **Licence:** confirm on repo page
- **Activity:** Feb 2026 paper (arXiv:2602.09464, v2 present). Current.
- **What it does:** 77 classical "textbook" algorithms — data structures, graph
  algorithms, maths — posed as vericoding tasks, and it is **the first suite whose
  specifications are strictly *aligned* across three reasoning systems: Dafny, Verus and
  Lean**, deliberately spanning SMT-based verifiers and an interactive theorem prover so
  cross-system comparison is meaningful. Ships all data plus evaluation code.
- **Results:** Gemini-3 Flash 40.3% Dafny, 24.7% Verus, 7.8% Lean — the collapse across
  backends *for the same problems* is the phenomenon our architecture exists to address.
- **Paper:** "AlgoVeri: An Aligned Benchmark for Verified Code Generation on Classical
  Algorithms", arXiv:2602.09464.
- **Lift:** **This is the closest published thing to our thesis and the most important
  prior art to read before building.** Specifically: (a) how they define "aligned"
  specifications across three systems — the semantic equivalence argument is exactly what
  our one spec language + seven backends has to make, and they made it first, for three;
  (b) their per-backend evaluation code; (c) their 77-algorithm problem list as a
  ready-made coverage target. Also read it as the competitive framing: our contribution
  has to be *seven* backends, the executable interpreter, and the mutation-based
  spec-quality signal, because "aligned multi-backend benchmark" alone is taken.
- **Evaluate against directly:** **Yes — highest priority.** It covers three of our seven
  backends with aligned problems and publishes per-backend numbers to beat.

## 25. CLEVER — curated, anti-vacuity, spec-generation-first

- **URL:** https://github.com/trishullab/clever (also on HuggingFace)
- **Language:** Lean 4 + Python
- **Licence:** confirm on repo page
- **Activity:** NeurIPS 2025 / ICML 2025 presence; UT Austin (Trishul lab). Current.
- **What it does:** 161 hand-curated problems for **end-to-end** verified code generation
  in Lean. Each problem is two tasks: (1) **generate a specification that matches a
  held-out ground-truth specification**, and (2) generate an implementation that provably
  satisfies it. Design principles are the interesting part — it deliberately **avoids
  test-case supervision, avoids LLM-generated annotations, and excludes specifications
  that leak implementation logic or admit vacuous solutions**. Everything is checked
  post-hoc by Lean's type checker. No method achieves full verification; it is meant to be
  a frontier benchmark.
- **Paper:** "CLEVER: A Curated Benchmark for Formally Verified Code Generation",
  arXiv:2505.13938.
- **Lift:** **Their spec-matching task definition and their exclusion criteria.** Matching
  a generated spec against a held-out ground-truth spec is a harder and cleaner signal
  than "does it verify", and it is a task our reference solutions already let us pose. The
  exclusion criteria are effectively a **checklist for auditing our own problem set**:
  no implementation leakage, no vacuity, no test-case supervision. Note the tension with
  our design — CLEVER treats test-case supervision as contamination, while our
  per-problem unit tests are a feature; we should be ready to report both with and
  without them.
- **Evaluate against directly:** Yes, as the hard-mode Lean target and as the only
  benchmark scoring spec generation against a held-out ground-truth spec.

## 26. CodeSpecBench — **executable specifications scored by accept/reject**

- **URL:** https://github.com/SparksofAGI/CodeSpecBench
- **Language:** Python
- **Licence:** **not specified in the repo** — blocker for code reuse; the ideas are free.
- **Activity:** **one commit, 7 stars — a code drop, not a project.** Treat as reference
  material only.
- **What it does:** Benchmarks LLMs on generating **executable behavioral
  specifications**, encoded as **executable Python preconditions and postconditions**
  (preconditions validate inputs and program state before execution; postconditions
  validate outputs and allowed state changes after). Two settings: `-Func`
  (self-contained functions, test inputs validated via online-judge submissions) and
  `-Repo` (real repository issues, specs dynamically injected around the target function
  and run against curated suites). Best of 15 models managed only **20.2% pass on
  repo-level**.
- **Paper:** "CodeSpecBench: Benchmarking LLMs for Executable Behavioral Specification
  Generation", arXiv:2604.12268.
- **Lift:** **Their evaluation protocol is our evaluation protocol, already written down.**
  Correctness = the spec *accepts all valid behaviours/tests*; completeness = it
  *rejects all invalid behaviours/tests*; pass rate = both. Our executable interpreter
  supplies the accept side from the reference solution and unit tests, and our **mutation
  engine's broken twins supply the reject side** — meaning we can report
  correctness/completeness/pass-rate in their exact terms and be directly comparable.
  Adopt this vocabulary in our metrics rather than inventing one.

## 27. FormalBench — JML specification inference, with a mutation-built variant set

- **URL:** https://github.com/thanhlecongg/FormalBench ·
  extension https://github.com/GyDeen/FormalBench-Extension
- **Language:** Python harness over Java + OpenJML
- **Licence:** confirm on repo page
- **Activity:** ACL 2025 paper; **the de facto standard spec-inference benchmark** —
  SpecGen, AutoReSpec, KBSpec and CodeSpecBench all compare against it, which is the best
  evidence of liveness in this list.
- **What it does:** Evaluates LLMs on inferring JML specifications from Java source, with
  OpenJML as the verifier. **FormalBench-Base** is 699 Java programs;
  **FormalBench-Diverse** is **6,219 programs built by applying mutations to the base
  set** — i.e. the benchmark itself is generated by a mutation engine, to test robustness
  of spec inference rather than memorisation. Metrics: pass rate (specs the verifier
  accepts) and fail rate (specs that trigger at least one verifier error), plus
  consistency/completeness analyses.
- **Paper:** "Can LLMs Reason About Program Semantics? A Comprehensive Evaluation of LLMs
  on Formal Specification Inference" (ACL 2025).
- **Lift:** **Base-set-plus-mutation-derived-diverse-set is a published precedent for
  using our mutation engine to 10× our problem set** (699 → 6,219) and for the argument
  that mutation-derived variants measure reasoning rather than recall. That is a strong
  justification for the engine we already have. Also lift their pass-rate/fail-rate
  split — distinguishing "verifier rejected it" from "verifier errored" matters across
  seven backends with seven error taxonomies.
- **Evaluate against directly:** not in our backend list (JML/Java), but it is the
  benchmark our *methodology* will be compared to, so we should be able to speak to it.

## 28. LLM4Rocq — the Rocq backend's toolbox, already built

- **URL (org):** https://github.com/LLM4Rocq
- **Licence/activity:** several separate repos; confirm each individually. The org is
  clearly current (Rocq, not Coq, naming) and unusually tooling-focused.
- **Repos that matter to us:**
  - **`pytanque`** (https://github.com/LLM4Rocq/pytanque) — Python API for lightweight
    communication with Rocq: proof state management, AST parsing, position-based queries,
    structured feedback. **This is the Rocq equivalent of LeanDojo's interaction layer.**
  - **`rocq-ml-toolbox`** (https://github.com/LLM4Rocq/rocq-ml-toolbox) — environment
    generation, project parsing, Docker helpers, safe proof-checking, plus
    **`rocq-ml-server`**, a FastAPI/uvicorn inference server with Redis-backed sessions
    and an arbiter supervising multiple pet-server workers.
  - **`rocq-mcp`** (https://github.com/LLM4Rocq/rocq-mcp, also
    https://github.com/AndreasLoow/rocq-mcp) — **MCP server exposing Rocq compilation,
    verification, querying and interactive tactic stepping as agent tools.**
  - **`miniF2F-rocq`** (https://github.com/LLM4Rocq/miniF2F-rocq) — Rocq port of miniF2F.
  - **`crrrocq-mini`** — agentic Rocq theorem proving: tool-calling inference pipeline,
    CoT-with-tool-calling dataset generation, and s1-style training on ~1000 curated
    examples.
- **Lift:** **Do not write a Rocq driver.** Take `pytanque` for programmatic control and
  `rocq-mcp` for agent exposure. `rocq-ml-server`'s **session-pooled worker architecture
  with an arbiter** is also the right answer to a real problem we will hit: proof backends
  are slow, stateful processes, and running seven of them across a problem set needs
  pooling, not fresh spawns. That architecture generalises to all seven backends.

## 29. Verus proof repair: ExVerus and KVerus (papers ahead of public code)

- **ExVerus** — "ExVerus: Verus Proof Repair via Counterexample Reasoning",
  arXiv:2603.25810, ICML 2026. Fully automated Verus proof generation guided by
  **semantically meaningful, source-level counterexamples**. When a proof fails it
  generates and validates a counterexample, then prompts the LLM to **generalise the
  counterexample into an inductive invariant** that blocks it. The trick:
  **bypass Verus's huge low-level SMT queries entirely** and have the LLM synthesize a
  small SMT query that simulates the failure at source level. Reports better accuracy,
  robustness *and token efficiency* than prompting-based generators.
- **KVerus** — "KVerus: Scalable and Resilient Formal Verification Proof Generation for
  Rust Code", arXiv:2605.03822. Retrieval-augmented, with a **dynamic knowledge base of
  code metadata, lemma semantics and toolchain specifics**, dependency-aware program
  analysis, semantic lemma indexing and error-driven self-refinement; repairs proofs when
  the surrounding code evolves. **80.2% on three single-file benchmarks vs AutoVerus's
  56.9%** — currently the strongest reported Verus numbers.
- **Repos:** **I could not confirm public GitHub repositories for either.** Both are
  recent (2026) papers; check https://verus-lang.github.io/verus/publications-and-projects/
  for released artifacts before assuming code exists.
- **Lift:** ExVerus's **counterexample → inductive invariant generalisation** is the
  highest-leverage idea in this whole document for our repair loop, and it is
  backend-agnostic: every one of our seven backends can produce a counterexample or a
  failing test, and our **executable interpreter can validate a candidate counterexample
  cheaply before spending an LLM call on it**. KVerus's "toolchain specifics in the
  knowledge base" is the pragmatic lesson — most failures are version/idiom mismatches,
  not logic.
