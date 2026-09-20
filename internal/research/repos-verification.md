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
