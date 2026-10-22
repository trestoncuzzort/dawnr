# Plateau repositories, set A: open code for verified code and proof generation

- Date (UTC): 2026-10-22 10:10 UTC
- Question: which open repositories ship the pieces behind verified code generation and proof generation for small models, so that dawnr's plateau on specification writing can borrow from them. This is a read-only survey. Nothing was cloned, built or executed; repository metadata and README openings were read through the GitHub API.
- Method (query counts): GitHub repository search with `gh search repos`, 244 logged calls of up to 30 results each: 60 name-oriented queries (mostly `in:name`), 30 topic queries (`topic:`), 50 long text queries plus 6 retries, 13 gap queries, and 85 short keyword queries. 233 calls returned a list; many were empty, because repository search requires every term to match the name, description or topics. 11 calls hit GitHub's search rate limit (HTTP 403), and 6 of them were retried successfully. Exact-name lookups with `gh api repos/OWNER/NAME`: 281 names, 224 resolved, 57 did not exist under that name. README openings were read for 35 repositories whose one-line descriptions were ambiguous. Web: 8 WebSearch queries and 7 WebFetch page reads, one of which the network refused. Distinct repositories seen across search and lookups: 1,914; 250 were kept.
- Tag key: R1 training pipeline with verifier reward (RL, expert iteration, reward models and training frameworks used with verifiers); R2 verified-program or verified-proof datasets and libraries; R3 benchmark harness; R4 specification or invariant synthesis, including contract tools; R5 proof search and tooling (provers, kernels, verifiers, editor and REPL tools); R6 autoformalization and synthetic data; R7 small-model releases or model families for code or proof generation. Numbers quoted for R7 rows come from each repository's own reports and were not re-measured.
- Totals: 250 repositories. Tags, counted over all rows (a row with two tags counts once under each): R1 49, R2 44, R3 43, R4 24, R5 94, R6 24, R7 29. Permissive-licence repositories: 174 of 250 (MIT 78, Apache-2.0 90, BSD-2-Clause 1, BSD-3-Clause 4, CC0-1.0 1). Also CC-BY-4.0 1 (a document set, not software). Copyleft or weak copyleft (GPL, LGPL, MPL, AGPL): 12. Other, meaning a custom or non-SPDX licence as GitHub reports it: 34. Unknown, meaning GitHub reports no licence: 29.
- Licence and stars: read from the GitHub API on 2026-10-22 10:10 UTC. The licence column shows the SPDX identifier when GitHub gives one. It reads "other" for custom or non-SPDX terms and "unknown" when GitHub reports no licence. Star counts are as read on that date.
- Excluded after reading: Huosj/AutoSpec (its README is a notice about a copy of a commercial command-line tool's source, not an AutoSpec implementation); kecodon/autoverus (its description refers to a mining tool and was not read further); Sahibzada-allahyar/Formal-Verification-RSI (promotional README, and its claims were not checked); Vilin97/Autoformalization and uw-math-ai/autoformalization-with-llms (the README describes a research workspace and a setup guide respectively); dtunai/miniF2F-code, TienMinh-08i/nl2postcond and duongngocyen/magnushammer-unofficial (no description; the first two also have no README text).
- Named systems without a repository we could find: Clover (paper and secondary pages only; the project blog could not be fetched); Laurel (artifact on Zenodo, no repository); nl2postcond (paper only; the two repositories carrying the name are a placeholder and a repository named for a project website); SAFE for Verus (paper only); Rango (no official repository; community items listed); Baldur (no repository); Verus-Agent under that name (a benchmark repository is listed instead); Lean Workbook from InternLM (not found; a fork is listed); NuminaMath-LEAN (not found as a GitHub repository); InternLM-StepProver, DeepSeek-Prover-V1, Herald and Dafny-synthesis (not found by name or search); Magnushammer (only an unofficial port with no description, not listed).
- Verification: each canonical link was checked on 2026-10-22 10:10 UTC with `gh api` (name, stars and licence) and an HTTP request to the link. 250 of 250 returned HTTP 200.

- Checked after the scout (2026-10-22 10:15 UTC): 250 numbered rows, no em or en dashes; a fixed sample of 25 links returned HTTP 200, 25 of 25; the licence and star cells of five rows (dafny-annotator, DafnyBench, verina, clever, STP) match the GitHub API.

## Table 1: repositories

| # | repository | link | licence | stars | tags | what it ships and why it may help |
|---|---|---|---|---|---|---|
| 1 | deepseek-ai/DeepSeek-Prover-V1.5 | https://github.com/deepseek-ai/DeepSeek-Prover-V1.5 | MIT | 588 | R1, R5, R7 | Lean 4 prover released as a 7B model with an inference and proof search path. The paper uses reinforcement learning from proof assistant feedback and tree search, and reports miniF2F and ProofNet results. |
| 2 | deepseek-ai/DeepSeek-Prover-V2 | https://github.com/deepseek-ai/DeepSeek-Prover-V2 | other | 1314 | R1, R6, R7 | Lean 4 prover in 7B and 671B sizes. Cold-start data comes from decomposing theorems into subgoals with a general model, followed by reinforcement learning on Lean-verified rollouts. |
| 3 | deepseek-ai/DeepSeek-Math | https://github.com/deepseek-ai/DeepSeek-Math | MIT | 3461 | R1, R7 | Math model whose paper introduces GRPO, the group-relative policy optimisation that later verifier-reward recipes build on. |
| 4 | deepseek-ai/DeepSeek-Math-V2 | https://github.com/deepseek-ai/DeepSeek-Math-V2 | Apache-2.0 | 1616 | R1, R7 | Second DeepSeekMath release, reached from the same family. The repository has no description, so the training claims here are not checked. |
| 5 | Goedel-LM/Goedel-Prover | https://github.com/Goedel-LM/Goedel-Prover | MIT | 240 | R6, R7 | Open 7B to 8B Lean 4 prover trained on formal statements produced by autoformalizing natural language problems, with Lean checking the data. Reports miniF2F results. |
| 6 | Goedel-LM/Goedel-Prover-V2 | https://github.com/Goedel-LM/Goedel-Prover-V2 | unknown | 194 | R1, R6, R7 | Lean 4 prover with scaffolded synthetic data and self-correction from compiler feedback, released in 8B and 32B sizes. |
| 7 | goedelcodeprover/Goedel-Code-Prover | https://github.com/goedelcodeprover/Goedel-Code-Prover | MIT | 138 | R5, R7 | Two-stage Lean 4 system that breaks a theorem with a sorry placeholder into lemmas and then completes the proofs. Links an 8B model on Hugging Face. |
| 8 | project-numina/kimina-prover-rl | https://github.com/project-numina/kimina-prover-rl | Apache-2.0 | 12 | R1 | Reinforcement learning pipeline for the Kimina-Prover Lean prover. The README shown on GitHub is the verl README, so the pipeline is presumably built on verl. |
| 9 | project-numina/kimina-lean-server | https://github.com/project-numina/kimina-lean-server | MIT | 213 | R5 | Lean server with a client SDK for checking many proof attempts in parallel, the kind of checker service a verifier-reward loop needs. |
| 10 | MoonshotAI/Kimina-Prover-Preview | https://github.com/MoonshotAI/Kimina-Prover-Preview | unknown | 378 | R7 | Technical report repository for the Kimina-Prover Preview, a Lean prover trained with reinforcement learning. The README links the report and Hugging Face assets. |
| 11 | kfdong/STP | https://github.com/kfdong/STP | MIT | 123 | R1, R6, R7 | Official code for a self-play theorem prover in which a model proposes conjectures and proves them in Lean in an iterative loop. Built on levanter. |
| 12 | InternLM/InternLM-Math | https://github.com/InternLM/InternLM-Math | Apache-2.0 | 553 | R5, R7 | Bilingual math LLMs that act as solver, prover, verifier and augmentor, with Lean 4 formal reasoning. Links released checkpoints. |
| 13 | lean-dojo/ReProver | https://github.com/lean-dojo/ReProver | MIT | 339 | R5, R7 | Retrieval-augmented Lean 4 provers: a premise retriever and a small generator, released with the LeanDojo benchmark tooling. A useful small baseline with retrieval. |
| 14 | lean-dojo/LeanDojo | https://github.com/lean-dojo/LeanDojo | MIT | 848 | R2, R5 | Toolkit that extracts proof states, tactics and premises from Lean repositories and exposes an interactive Lean environment to Python. Its extracted data is a common training source for Lean provers. |
| 15 | lean-dojo/LeanCopilot | https://github.com/lean-dojo/LeanCopilot | MIT | 1335 | R5 | Lean 4 plugin that runs language models for tactic suggestions and premise search inside the editor, with local model inference. |
| 16 | lean-dojo/LeanAgent | https://github.com/lean-dojo/LeanAgent | unknown | 88 | R1, R5 | Lifelong learning framework for Lean proving that keeps training as mathlib grows, described in the linked arXiv paper. |
| 17 | lean-dojo/LeanDojo-v2 | https://github.com/lean-dojo/LeanDojo-v2 | Apache-2.0 | 147 | R1, R5 | End-to-end framework for training, evaluating and deploying Lean provers, from the LeanDojo group. |
| 18 | wellecks/llmstep | https://github.com/wellecks/llmstep | MIT | 155 | R5 | Lean 4 tactic that asks a language model for proof step suggestions. A simple integration pattern for a small model. |
| 19 | cmu-l3/alphaverus | https://github.com/cmu-l3/alphaverus | unknown | 34 | R1, R5 | Bootstraps Verus code generation with a self-improving translation loop that keeps verifier-accepted translations as training data, plus treefinement for repairs. |
| 20 | ByteDance-Seed/BFS-Prover-V2 | https://github.com/ByteDance-Seed/BFS-Prover-V2 | Apache-2.0 | 53 | R5, R7 | Lean 4 prover from ByteDance Seed in the best-first search line. |
| 21 | ByteDance-Seed/Seed-Prover | https://github.com/ByteDance-Seed/Seed-Prover | Apache-2.0 | 441 | R1, R5, R7 | Lean 4 prover from ByteDance Seed that uses Lean feedback during proof search, under. |
| 22 | Leanabell-LM/Leanabell-Prover | https://github.com/Leanabell-LM/Leanabell-Prover | unknown | 12 | R1, R7 | Reinforcement learning for a Lean prover that stimulates reflective revision of failed proofs, with an arXiv paper and Hugging Face links. |
| 23 | Leanabell-LM/Leanabell-Prover-V2 | https://github.com/Leanabell-LM/Leanabell-Prover-V2 | unknown | 12 | R1, R7 | Second version of the Leanabell prover, described as verifier-integrated reasoning for formal theorem proving trained with reinforcement learning. |
| 24 | frenzymath/Archon | https://github.com/frenzymath/Archon | Apache-2.0 | 228 | R5 | AI-assisted Lean project automation that builds a DAG of lemmas from a blueprint and orchestrates proof attempts across them. |
| 25 | stanford-centaur/PyPantograph | https://github.com/stanford-centaur/PyPantograph | Apache-2.0 | 150 | R5 | Machine-to-machine interface to Lean 4 from Python, used to build proof-search environments. |
| 26 | microsoft/rStar | https://github.com/microsoft/rStar | MIT | 1432 | R1 | Repository for the rStar2-Agent report on agentic reasoning trained with reinforcement learning, per its README title. |
| 27 | ezelikman/STaR | https://github.com/ezelikman/STaR | Apache-2.0 | 233 | R1 | Code for STaR, which bootstraps reasoning by keeping rationales that reach the right answer and retraining on them. The check here is an answer match, not a proof checker. |
| 28 | hkust-nlp/simpleRL-reason | https://github.com/hkust-nlp/simpleRL-reason | MIT | 3880 | R1 | Small-scale RL recipe for reasoning models with rule-based rewards, easy to adapt to a verifier reward. |
| 29 | Jiayi-Pan/TinyZero | https://github.com/Jiayi-Pan/TinyZero | Apache-2.0 | 13253 | R1 | Minimal reproduction of R1-Zero-style RL on a small model with a rule-based reward, a low-cost template for verifier-reward training. |
| 30 | PRIME-RL/PRIME | https://github.com/PRIME-RL/PRIME | Apache-2.0 | 1873 | R1 | Reinforcement learning with implicit process rewards for reasoning, with a training stack that includes code execution checks. |
| 31 | Unakar/Logic-RL | https://github.com/Unakar/Logic-RL | Apache-2.0 | 2452 | R1 | Reproduction of R1-Zero-style RL on logic puzzles with a rule-based reward, a small reference for reward design. |
| 32 | salesforce/CodeRL | https://github.com/salesforce/CodeRL | BSD-3-Clause | 579 | R1 | Code generation with reinforcement learning from unit-test feedback and a critic model, the execution-as-reward idea for code. |
| 33 | reddy-lab-code-research/PPOCoder | https://github.com/reddy-lab-code-research/PPOCoder | MIT | 116 | R1 | PPO for code generation with compiler and unit-test feedback as the reward, the code for the TMLR paper. |
| 34 | BytedTsinghua-SIA/DAPO | https://github.com/BytedTsinghua-SIA/DAPO | unknown | 1954 | R1 | Open RL system for long reasoning chains with decoupled clipping and dynamic sampling, built on verl. The README reports AIME 2024 scores for its checkpoint. |
| 35 | nearai/putnambench-deepseek | https://github.com/nearai/putnambench-deepseek | unknown | 15 | R3, R5 | Agent that solved all 672 PutnamBench problems in Lean 4, with machine checking and corrected variants of two defective statements, per its README. |
| 36 | Sphere-AI-Lab/FormalMATH-Bench | https://github.com/Sphere-AI-Lab/FormalMATH-Bench | Apache-2.0 | 76 | R3, R6 | Formal mathematics benchmark of Lean 4 statements built with an autoformalization and filtering pipeline. Links its paper. |
| 37 | albertqjiang/draft_sketch_prove | https://github.com/albertqjiang/draft_sketch_prove | other | 74 | R5, R6 | Draft, Sketch and Prove: an informal proof is drafted, turned into a formal sketch with holes, and the holes are filled by an automated prover in Isabelle. |
| 38 | albertqjiang/Portal-to-ISAbelle | https://github.com/albertqjiang/Portal-to-ISAbelle | BSD-3-Clause | 57 | R1, R5 | Isabelle environment that lets models interact with Isabelle for proof search and training data, with a project page. |
| 39 | coq-tactician/coq-tactician | https://github.com/coq-tactician/coq-tactician | MIT | 87 | R5 | Tactic learner and prover for Coq that learns from existing proofs and runs interactively. |
| 40 | coq-tactician/coq-tactician-api | https://github.com/coq-tactician/coq-tactician-api | MIT | 3 | R5 | API that lets external agents drive Coq through Tactician. |
| 41 | UCSD-PL/proverbot9001 | https://github.com/UCSD-PL/proverbot9001 | GPL-3.0 | 45 | R5 | Machine-learning proof search for Coq, with data extraction from Coq projects. |
| 42 | JetBrains-Research/coqpilot | https://github.com/JetBrains-Research/coqpilot | LGPL-2.1 | 130 | R5 | VS Code extension that generates Coq proofs with language models and checks them with Coq, a working integration pattern. |
| 43 | verus-lang/verus | https://github.com/verus-lang/verus | MIT | 3381 | R5 | Verifier for Rust programs (Verus), the kernel that checks every Verus proof in this list. |
| 44 | dafny-lang/dafny | https://github.com/dafny-lang/dafny | other | 3589 | R5 | Dafny verification-aware language and verifier, the kernel behind the Dafny benchmarks and annotation tools. |
| 45 | dafny-lang/ide-vscode | https://github.com/dafny-lang/ide-vscode | MIT | 28 | R5 | Visual Studio Code integration for Dafny, used for editor feedback when writing verified code. |
| 46 | boogie-org/boogie | https://github.com/boogie-org/boogie | MIT | 603 | R5 | Intermediate verification language and verifier that Dafny and other tools compile into. |
| 47 | dafny-lang/libraries | https://github.com/dafny-lang/libraries | other | 49 | R2 | Libraries for Dafny programs, a source of reusable verified code. |
| 48 | rocq-prover/rocq | https://github.com/rocq-prover/rocq | LGPL-2.1 | 5611 | R5 | The Rocq Prover, the proof assistant formerly named Coq, the kernel for the Rocq items here. |
| 49 | rocq-community/rocq-lsp | https://github.com/rocq-community/rocq-lsp | LGPL-2.1 | 210 | R5 | Language server and VS Code extension for Rocq, used by editor-integrated tools and agents. |
| 50 | rocq-archive/coq-serapi | https://github.com/rocq-archive/coq-serapi | other | 136 | R5 | Serialization layer that exposes Coq internals to external tools, used by machine-learning provers. |
| 51 | ProofGeneral/PG | https://github.com/ProofGeneral/PG | GPL-3.0 | 562 | R5 | Proof General, an Emacs interface for proof assistants including Rocq and Isabelle. Licensed under. |
| 52 | FStarLang/FStar | https://github.com/FStarLang/FStar | Apache-2.0 | 3123 | R5 | The F* proof-oriented programming language and verifier, the kernel for F* proofs. |
| 53 | FStarLang/pulse | https://github.com/FStarLang/pulse | unknown | 36 | R5 | Pulse, a separation-logic DSL embedded in F* for verified imperative programs. |
| 54 | AdaCore/spark2014 | https://github.com/AdaCore/spark2014 | GPL-3.0 | 330 | R5 | SPARK 2014 toolset for verifying Ada programs. Licensed under. |
| 55 | AdaCore/why3 | https://github.com/AdaCore/why3 | other | 40 | R5 | Why3 verification platform, the backend that SPARK uses for its proofs. |
| 56 | Frama-C/Frama-C-snapshot | https://github.com/Frama-C/Frama-C-snapshot | unknown | 190 | R5 | Release snapshots of the Frama-C platform for C analysis, including the WP plugin that checks ACSL contracts. |
| 57 | creusot-rs/creusot | https://github.com/creusot-rs/creusot | LGPL-2.1 | 1934 | R5 | Deductive verifier for Rust programs built on Why3. |
| 58 | model-checking/kani | https://github.com/model-checking/kani | Apache-2.0 | 3574 | R5 | Model checker for Rust with proof harnesses for bounded checks. |
| 59 | AeneasVerif/aeneas | https://github.com/AeneasVerif/aeneas | Apache-2.0 | 1084 | R5 | Translates Rust programs into models for proof assistants such as Lean, a route from Rust code to checkable proofs. |
| 60 | AeneasVerif/charon | https://github.com/AeneasVerif/charon | Apache-2.0 | 450 | R5 | Rust analysis that extracts a compiler-independent representation for verification tools such as Aeneas. |
| 61 | cryspen/hax | https://github.com/cryspen/hax | Apache-2.0 | 488 | R5 | Rust verification toolchain that translates Rust into F* and other proof backends. |
| 62 | prusti/prusti | https://github.com/prusti/prusti | other | 1820 | R5 | Static verifier for Rust built on the Viper infrastructure. |
| 63 | viperproject/silicon | https://github.com/viperproject/silicon | MPL-2.0 | 149 | R5 | Symbolic-execution verifier for the Viper intermediate language. |
| 64 | viperproject/silver | https://github.com/viperproject/silver | MPL-2.0 | 100 | R5 | Definition of the Viper intermediate verification language. |
| 65 | Z3Prover/z3 | https://github.com/Z3Prover/z3 | other | 12807 | R5 | The Z3 SMT solver, the backend most verifiers in this list call. |
| 66 | cvc5/cvc5 | https://github.com/cvc5/cvc5 | other | 1376 | R5 | The cvc5 SMT solver used as a discharge backend by verification tools. |
| 67 | OCamlPro/alt-ergo | https://github.com/OCamlPro/alt-ergo | other | 149 | R5 | Alt-Ergo SMT solver for program verification. |
| 68 | verifast/verifast | https://github.com/verifast/verifast | other | 522 | R5 | Modular verifier for C, Java and Rust programs, a research prototype. |
| 69 | KeYProject/key | https://github.com/KeYProject/key | other | 89 | R5 | KeY deductive verifier for Java programs with JML contracts. |
| 70 | OpenJML/OpenJML | https://github.com/OpenJML/OpenJML | unknown | 187 | R5 | JML-based verification tool for Java programs, the verifier used by the SpecGen artifact. |
| 71 | marcoeilers/nagini | https://github.com/marcoeilers/nagini | MPL-2.0 | 303 | R4, R5 | Static verifier for Python 3 programs built on Viper. Licensed under. |
| 72 | pschanely/CrossHair | https://github.com/pschanely/CrossHair | other | 1339 | R4 | Analysis tool for Python that checks contracts and type annotations with symbolic execution. |
| 73 | Parquery/icontract | https://github.com/Parquery/icontract | MIT | 419 | R4 | Design-by-contract library for Python with informative violation messages. |
| 74 | life4/deal | https://github.com/life4/deal | MIT | 918 | R4 | Design-by-contract decorators for Python, adding preconditions and postconditions to ordinary functions. |
| 75 | HOL-Theorem-Prover/HOL | https://github.com/HOL-Theorem-Prover/HOL | other | 763 | R5 | HOL4 theorem prover, the proof assistant behind CakeML. |
| 76 | ufmg-smite/lean-smt | https://github.com/ufmg-smite/lean-smt | Apache-2.0 | 314 | R5 | Lean tactics that send goals to SMT solvers and check the returned certificates. |
| 77 | leanprover/lean4 | https://github.com/leanprover/lean4 | Apache-2.0 | 9626 | R5 | Lean 4 programming language and theorem prover, the kernel that checks every Lean proof in this list. |
| 78 | leanprover-community/mathlib4 | https://github.com/leanprover-community/mathlib4 | Apache-2.0 | 4337 | R2, R5 | Lean 4 mathematics library, the largest checked corpus of formal mathematics used to train and test Lean provers. |
| 79 | leanprover-community/repl | https://github.com/leanprover-community/repl | Apache-2.0 | 235 | R5 | REPL for Lean 4 that returns errors and sorries, used by proof-search harnesses. |
| 80 | leanprover/lean4checker | https://github.com/leanprover/lean4checker | Apache-2.0 | 36 | R5 | Replays the Lean environment for a module to confirm that a proof uses only the trusted kernel path. The repository is archived. |
| 81 | leanprover-community/aesop | https://github.com/leanprover-community/aesop | Apache-2.0 | 410 | R5 | White-box proof automation for Lean 4 with extensible rules, a standard automation tactic. |
| 82 | leanprover-community/duper | https://github.com/leanprover-community/duper | Apache-2.0 | 118 | R5 | Superposition prover for Lean 4 goals, usable as a proof automation backend. |
| 83 | leanprover-community/lean-auto | https://github.com/leanprover-community/lean-auto | Apache-2.0 | 193 | R5 | Experiments on automation for Lean, including translation of goals to external solvers. |
| 84 | leanprover-community/batteries | https://github.com/leanprover-community/batteries | Apache-2.0 | 422 | R5 | Extended standard library for Lean 4, a dependency of most Lean projects. |
| 85 | nomeata/loogle | https://github.com/nomeata/loogle | Apache-2.0 | 158 | R5 | Search tool for Mathlib declarations by type pattern, useful for premise lookup. |
| 86 | oOo0oOo/lean-lsp-mcp | https://github.com/oOo0oOo/lean-lsp-mcp | MIT | 534 | R5 | Model Context Protocol server that exposes the Lean language server to LLM agents for goal states and checks. |
| 87 | cmu-l3/llmlean | https://github.com/cmu-l3/llmlean | MIT | 215 | R5 | Connects Lean 4 to local or cloud language models for tactic and proof suggestions. |
| 88 | verus-lang/verus-analyzer | https://github.com/verus-lang/verus-analyzer | Apache-2.0 | 46 | R5 | Verus front end for IDEs, derived from rust-analyzer, for editor feedback when writing Verus code. |
| 89 | philzook58/knuckledragger | https://github.com/philzook58/knuckledragger | MIT | 178 | R5 | Low-barrier proof assistant in Python. |
| 90 | agda/agda | https://github.com/agda/agda | other | 2947 | R5 | Agda dependently typed programming language and proof assistant. |
| 91 | formal-land/rocq-of-rust | https://github.com/formal-land/rocq-of-rust | unknown | 1176 | R5 | Translates Rust programs to Rocq for verification. |
| 92 | Julian/lean.nvim | https://github.com/Julian/lean.nvim | MIT | 610 | R5 | Neovim support for the Lean theorem prover. |
| 93 | newca12/awesome-rust-formalized-reasoning | https://github.com/newca12/awesome-rust-formalized-reasoning | MIT | 400 | R5 | Curated list of Rust verification and formalized reasoning resources, useful for finding tools. |
| 94 | uhub/awesome-coq | https://github.com/uhub/awesome-coq | unknown | 236 | R5 | Curated list of Coq and Rocq frameworks, libraries and tools. |
| 95 | ohenley/awesome-ada | https://github.com/ohenley/awesome-ada | CC0-1.0 | 874 | R5 | Curated list of Ada and SPARK resources. |
| 96 | leanprover-community/lean4-samples | https://github.com/leanprover-community/lean4-samples | Apache-2.0 | 80 | R5 | Sample Lean 4 projects for starting a proof environment. The repository is archived. |
| 97 | leanprover-community/lean4-metaprogramming-book | https://github.com/leanprover-community/lean4-metaprogramming-book | Apache-2.0 | 316 | R5 | Book on Lean 4 metaprogramming, for building custom tactics and tools. |
| 98 | sun-wendy/DafnyBench | https://github.com/sun-wendy/DafnyBench | Apache-2.0 | 69 | R2, R3 | Benchmark of Dafny programs with verification hints removed, used to test LLM proof generation. Ships the dataset and evaluation scripts. |
| 99 | microsoft/verus-proof-synthesis | https://github.com/microsoft/verus-proof-synthesis | MIT | 126 | R2, R3, R5 | AutoVerus and VeruSAGE proof synthesis code and Verus benchmarks, with an agent baseline and Rust programs that need proofs. |
| 100 | dafny-lang/miniF2F | https://github.com/dafny-lang/miniF2F | MIT | 11 | R3 | Dafny version of miniF2F: a model fills empty lemma bodies so the proof verifies, with an automated evaluation harness. |
| 101 | bbayazit16/verifythis-verus | https://github.com/bbayazit16/verifythis-verus | MIT | 3 | R2, R3 | Rust implementations of VerifyThis challenges in Verus, a source of verified programs. |
| 102 | gernst/verifythis2020 | https://github.com/gernst/verifythis2020 | MIT | 3 | R2, R3 | Material and solutions for the VerifyThis 2020 long-term challenge. |
| 103 | verifythis/verifythis.github.io | https://github.com/verifythis/verifythis.github.io | unknown | 5 | R3 | Website for the VerifyThis verification challenge, 2020 edition. |
| 104 | trishullab/clever | https://github.com/trishullab/clever | MIT | 49 | R3, R4 | CLEVER benchmark: curated Lean specifications and verified programs for code generation, checked by the Lean type checker against held-out reference specifications. |
| 105 | sunblaze-ucb/verina | https://github.com/sunblaze-ucb/verina | Apache-2.0 | 83 | R3, R4 | Verifiable code generation arena with Lean specifications, code and proofs for each benchmark task. |
| 106 | haoyuzhao123/algoveri | https://github.com/haoyuzhao123/algoveri | Apache-2.0 | 9 | R3 | Code for AlgoVeri, a benchmark for verified code generation on classical algorithms. |
| 107 | quinn-dougherty/fvapps | https://github.com/quinn-dougherty/fvapps | other | 7 | R2, R3 | Formally verified subset of the APPS programming problems, with formal specifications. |
| 108 | zhangir-azerbayev/ProofNet | https://github.com/zhangir-azerbayev/ProofNet | MIT | 128 | R3 | Benchmark of undergraduate formal mathematics statements with informal and formal versions. |
| 109 | rahul3613/ProofNet-lean4 | https://github.com/rahul3613/ProofNet-lean4 | MIT | 31 | R3 | ProofNet ported into Lean 4 for prover evaluation. |
| 110 | marcusm117/ProofNet-Verified | https://github.com/marcusm117/ProofNet-Verified | Apache-2.0 | 3 | R3 | Audited and corrected ProofNet statements, a cleaner version of the benchmark. |
| 111 | trishullab/PutnamBench | https://github.com/trishullab/PutnamBench | unknown | 270 | R3 | Competition math benchmark formalized in Lean 4, Isabelle and Coq. |
| 112 | google-deepmind/miniF2F | https://github.com/google-deepmind/miniF2F | Apache-2.0 | 15 | R3 | Lean 4 port of miniF2F with corrections, a standard olympiad benchmark for formal provers. |
| 113 | facebookresearch/miniF2F | https://github.com/facebookresearch/miniF2F | MIT | 108 | R3 | Updated miniF2F with fixed statements and informal statements, a benchmark for formal olympiad mathematics. |
| 114 | openai/miniF2F | https://github.com/openai/miniF2F | unknown | 439 | R3 | Original miniF2F formal-to-formal olympiad benchmark, stated in several formal systems. The repository is archived. |
| 115 | yangky11/miniF2F-lean4 | https://github.com/yangky11/miniF2F-lean4 | MIT | 75 | R3 | miniF2F ported to Lean 4 for prover evaluation. |
| 116 | rahul3613/miniF2F-lean4 | https://github.com/rahul3613/miniF2F-lean4 | MIT | 7 | R3 | Another miniF2F port to Lean 4. |
| 117 | roozbeh-mohit/miniF2F_v2 | https://github.com/roozbeh-mohit/miniF2F_v2 | Apache-2.0 | 14 | R3 | A second miniF2F variant under Apache-2.0. The repository has no description. |
| 118 | LLM4Rocq/miniF2F-rocq | https://github.com/LLM4Rocq/miniF2F-rocq | MIT | 25 | R3 | miniF2F in Rocq, a benchmark for Rocq proof generation. |
| 119 | coq-tactician/benchmark-system | https://github.com/coq-tactician/benchmark-system | unknown | 4 | R3 | Benchmark system used with Tactician for Coq proof learning. The repository has no description. |
| 120 | princeton-vl/CoqGym | https://github.com/princeton-vl/CoqGym | LGPL-2.1 | 422 | R2, R3 | Learning environment for Coq proof search built on many Coq projects, with a proof dataset and tactic prediction tasks. |
| 121 | google-deepmind/formal-conjectures | https://github.com/google-deepmind/formal-conjectures | Apache-2.0 | 1332 | R2, R3 | Collection of formal Lean statements of open and solved conjectures, a source of checked targets. |
| 122 | ImperialCollegeLondon/FLT | https://github.com/ImperialCollegeLondon/FLT | Apache-2.0 | 1051 | R2 | Lean formalisation of Fermat's Last Theorem, a large checked corpus of Lean 4 proofs. |
| 123 | leanprover/cslib | https://github.com/leanprover/cslib | Apache-2.0 | 774 | R2 | Lean Computer Science Library: checked formal results on algorithms and program semantics. |
| 124 | leanprover-community/physlib | https://github.com/leanprover-community/physlib | Apache-2.0 | 805 | R2 | Lean formalisation of physics results, a checked corpus outside pure mathematics. |
| 125 | leanprover-community/mathlib3 | https://github.com/leanprover-community/mathlib3 | Apache-2.0 | 1665 | R2 | Lean 3 mathematics library, now obsolete, the origin of many older Lean corpora. The repository is archived. |
| 126 | isabelle-prover/mirror-afp-2025 | https://github.com/isabelle-prover/mirror-afp-2025 | unknown | 1 | R2 | Git mirror of the Isabelle Archive of Formal Proofs, a large checked library in Isabelle. The repository has no description. The repository is archived. |
| 127 | CakeML/cakeml | https://github.com/CakeML/cakeml | BSD-3-Clause | 1216 | R2 | CakeML compiler with machine-checked correctness proofs in HOL4. |
| 128 | AbsInt/CompCert | https://github.com/AbsInt/CompCert | other | 2251 | R2 | CompCert C compiler with machine-checked correctness proofs in Rocq. |
| 129 | seL4/l4v | https://github.com/seL4/l4v | other | 650 | R2 | Isabelle proofs and specifications for the seL4 kernel. |
| 130 | seL4/seL4 | https://github.com/seL4/seL4 | other | 5822 | R2 | seL4 microkernel source, the kernel whose correctness is proved in Isabelle. |
| 131 | uwplse/verdi | https://github.com/uwplse/verdi | BSD-2-Clause | 627 | R2 | Framework for verifying distributed systems implementations in Coq. |
| 132 | MetaRocq/metarocq | https://github.com/MetaRocq/metarocq | MIT | 561 | R2 | Verified metatheory of Rocq written in Rocq, a checked corpus of meta-level proofs. |
| 133 | UniMath/UniMath | https://github.com/UniMath/UniMath | other | 1020 | R2 | Univalent mathematics library in Rocq, a large checked corpus. |
| 134 | mit-plv/fiat-crypto | https://github.com/mit-plv/fiat-crypto | other | 847 | R2 | Verified generation of cryptographic primitive code in Rocq. |
| 135 | mit-plv/bedrock2 | https://github.com/mit-plv/bedrock2 | MIT | 338 | R2 | Verified low-level program language and compiler in Rocq. |
| 136 | PrincetonUniversity/VST | https://github.com/PrincetonUniversity/VST | other | 511 | R2 | Verified Software Toolchain for C programs in Rocq. |
| 137 | sarsko/CreuSAT | https://github.com/sarsko/CreuSAT | MIT | 704 | R2 | SAT solver written in Rust and verified with Creusot. |
| 138 | hacl-star/hacl-star | https://github.com/hacl-star/hacl-star | Apache-2.0 | 1842 | R2 | HACL*, a formally verified cryptographic library written in F*. |
| 139 | project-everest/everparse | https://github.com/project-everest/everparse | Apache-2.0 | 345 | R2 | Generator of verified parsers from F* specifications. |
| 140 | project-everest/vale | https://github.com/project-everest/vale | Apache-2.0 | 321 | R2 | Verified assembly language and its verifier in F*, used for cryptographic code. |
| 141 | secure-foundations/vest | https://github.com/secure-foundations/vest | MIT | 102 | R2 | Verified Rust parsing and serialization written with Verus. |
| 142 | awslabs/s2n-bignum | https://github.com/awslabs/s2n-bignum | other | 240 | R2 | Verified bignum routines written in assembly and checked in HOL Light. |
| 143 | cedar-policy/cedar-spec | https://github.com/cedar-policy/cedar-spec | Apache-2.0 | 217 | R2, R4 | Definitional implementation of the Cedar policy language with Dafny and Lean proofs. |
| 144 | fraunhoferfokus/acsl-by-example | https://github.com/fraunhoferfokus/acsl-by-example | MIT | 128 | R2 | Public examples of ACSL specifications for Frama-C. |
| 145 | LiveCodeBench/LiveCodeBench | https://github.com/LiveCodeBench/LiveCodeBench | MIT | 963 | R3 | Contamination-aware code benchmark with problems released over time, scored by unit tests. |
| 146 | bigcode-project/bigcode-evaluation-harness | https://github.com/bigcode-project/bigcode-evaluation-harness | Apache-2.0 | 1063 | R3 | Harness for evaluating autoregressive code models on code benchmarks with execution. |
| 147 | bigcode-project/bigcodebench | https://github.com/bigcode-project/bigcodebench | Apache-2.0 | 516 | R3 | Code benchmark with practical library-using tasks and unit-test scoring. The repository is archived. |
| 148 | evalplus/evalplus | https://github.com/evalplus/evalplus | Apache-2.0 | 1833 | R3 | HumanEval+ and MBPP+ test suites with extra tests and the evaluation tooling. |
| 149 | openai/human-eval | https://github.com/openai/human-eval | MIT | 3414 | R3 | Code for the HumanEval benchmark and the unbiased pass@k estimator from the Codex paper. |
| 150 | nuprl/MultiPL-E | https://github.com/nuprl/MultiPL-E | other | 317 | R3 | Multi-language translation of HumanEval and MBPP for benchmarking code models. |
| 151 | facebookresearch/cruxeval | https://github.com/facebookresearch/cruxeval | MIT | 174 | R3 | Code reasoning and execution benchmark that asks models to predict inputs and outputs. The repository is archived. |
| 152 | EleutherAI/lm-evaluation-harness | https://github.com/EleutherAI/lm-evaluation-harness | MIT | 14297 | R3 | General few-shot evaluation harness for language models, useful for fixed panels. |
| 153 | huggingface/lighteval | https://github.com/huggingface/lighteval | MIT | 2566 | R3 | Evaluation toolkit for LLMs across several backends. |
| 154 | openai/simple-evals | https://github.com/openai/simple-evals | MIT | 4672 | R3 | Reference evaluation scripts for language models with fixed prompts. |
| 155 | HypothesisWorks/hypothesis | https://github.com/HypothesisWorks/hypothesis | other | 9101 | R3 | Property-based testing library for Python, usable to check specifications against random inputs. |
| 156 | microsoft/loop-invariant-gen-experiments | https://github.com/microsoft/loop-invariant-gen-experiments | MIT | 35 | R4 | Loopy experiments: LLM-proposed loop invariants for C code, checked by Frama-C, with setup for Docker or a local Frama-C install. The repository is archived. |
| 157 | microsoft/NeuralInvariantRanker | https://github.com/microsoft/NeuralInvariantRanker | MIT | 13 | R4 | Ranks LLM-generated loop invariants so that a verifier sees the most promising candidates first. |
| 158 | Lezhi-Ma/SpecGen-Artifact | https://github.com/Lezhi-Ma/SpecGen-Artifact | MIT | 22 | R4 | SpecGen: LLM generation of JML specifications for Java programs, checked with OpenJML. The artifact is the prototype tool from the paper. |
| 159 | deskchen/autospec | https://github.com/deskchen/autospec | unknown | 10 | R4 | Generates and checks ACSL specifications for C programs with an LLM and Frama-C, after static decomposition of the program. |
| 160 | ai-ar-research/Lemur-program-verification | https://github.com/ai-ar-research/Lemur-program-verification | unknown | 20 | R4 | Lemur: LLM-based annotation and invariant generation for automated C program verification, with the Python code of the paper. |
| 161 | metareflection/dafny-annotator | https://github.com/metareflection/dafny-annotator | MIT | 21 | R1, R4 | LLM annotation system that adds logical annotations to Dafny programs until they verify. The README describes two components. |
| 162 | lean-dojo/TorchLean | https://github.com/lean-dojo/TorchLean | MIT | 182 | R4 | Lean 4 framework for specifying and verifying neural network code, a route to formal specs for model components. |
| 163 | quint-co/quint | https://github.com/quint-co/quint | Apache-2.0 | 1864 | R4 | Executable specification language with tooling for model checking, a reference for writing checkable specs. |
| 164 | NASA-SW-VnV/fret | https://github.com/NASA-SW-VnV/fret | other | 490 | R4 | NASA FRET: a tool for eliciting, specifying and formalising requirements, a route from natural language requirements to checkable formulas. |
| 165 | p-org/P | https://github.com/p-org/P | MIT | 3722 | R4 | P language for specifying and testing distributed systems, with model checking. |
| 166 | aallan/vera | https://github.com/aallan/vera | MIT | 418 | R4 | Programming language designed for language models to write, listed here for its spec-first design. |
| 167 | fizzbee-io/fizzbee | https://github.com/fizzbee-io/fizzbee | Apache-2.0 | 363 | R4 | Formal methods language for developers with a model checker, a low-barrier way to write checked specifications. |
| 168 | JasonGross/autoformalization-transpilation | https://github.com/JasonGross/autoformalization-transpilation | MIT | 21 | R6 | LLM transpilation from Coq to Lean, a route to building formal corpora from existing libraries. |
| 169 | scottnarmstrong/LeanAutoformalizationSkills | https://github.com/scottnarmstrong/LeanAutoformalizationSkills | CC-BY-4.0 | 51 | R6 | Portable Lean 4 autoformalization skill files for coding agents. Licensed under CC-BY-4.0, which is an attribution licence for documents. |
| 170 | Purewhite2019/rethinking_autoformalization | https://github.com/Purewhite2019/rethinking_autoformalization | Apache-2.0 | 30 | R6 | Code for an ICLR 2025 spotlight on improving LLM autoformalization of mathematics into Lean. |
| 171 | not-gary/autoformalization | https://github.com/not-gary/autoformalization | Apache-2.0 | 7 | R6 | Experiments on autoformalization of mathematics and code correctness from 2022. |
| 172 | lanzhang128/definition_autoformalization | https://github.com/lanzhang128/definition_autoformalization | unknown | 8 | R3, R6 | Assesses LLM autoformalization of real-world mathematical definitions in Isabelle/HOL and Lean 4, with scripts for each system. |
| 173 | tukamilano/automated-theory-construction-lean | https://github.com/tukamilano/automated-theory-construction-lean | MIT | 8 | R6 | Prototype framework for automated theory construction in Lean 4, a route to generating formal content. |
| 174 | dataopsnick/autoformalization | https://github.com/dataopsnick/autoformalization | unknown | 5 | R6 | Generates Lean 3 code from arXiv identifiers, a small autoformalization script. |
| 175 | NVIDIA-NeMo/Skills | https://github.com/NVIDIA-NeMo/Skills | Apache-2.0 | 1055 | R1, R6 | Project for improving the math and code skills of LLMs with synthetic data generation and training pipelines. |
| 176 | argilla-io/distilabel | https://github.com/argilla-io/distilabel | Apache-2.0 | 3431 | R6 | Framework for synthetic data and AI feedback generation, useful for building verifier-checked training sets. |
| 177 | ise-uiuc/magicoder | https://github.com/ise-uiuc/magicoder | MIT | 2094 | R6, R7 | Code model family trained on OSS-Instruct synthetic data built from open-source snippets, with training and evaluation code. |
| 178 | yizhongw/self-instruct | https://github.com/yizhongw/self-instruct | Apache-2.0 | 4617 | R6 | Original self-instruct pipeline that generates instruction data from a seed set with a language model. |
| 179 | nlpxucan/WizardLM | https://github.com/nlpxucan/WizardLM | unknown | 9472 | R6, R7 | Evol-Instruct synthetic data methods behind WizardLM, WizardCoder and WizardMath. |
| 180 | OpenCoder-llm/OpenCoder-llm | https://github.com/OpenCoder-llm/OpenCoder-llm | MIT | 2124 | R6, R7 | Open code LLM cookbook with data pipelines and training details, the source of a small open code model family. |
| 181 | ByteDance-Seed/Seed-Coder | https://github.com/ByteDance-Seed/Seed-Coder | MIT | 761 | R6, R7 | Family of open code LLMs with data curation pipelines, released under. |
| 182 | bigcode-project/starcoder2 | https://github.com/bigcode-project/starcoder2 | Apache-2.0 | 2094 | R7 | StarCoder2 code models with training data and evaluation details. |
| 183 | bigcode-project/starcoder | https://github.com/bigcode-project/starcoder | Apache-2.0 | 7500 | R7 | StarCoder code models and fine-tuning recipes. |
| 184 | deepseek-ai/DeepSeek-Coder | https://github.com/deepseek-ai/DeepSeek-Coder | MIT | 24305 | R7 | DeepSeek Coder code model family. |
| 185 | deepseek-ai/DeepSeek-Coder-V2 | https://github.com/deepseek-ai/DeepSeek-Coder-V2 | MIT | 7016 | R7 | Mixture-of-experts code model family from DeepSeek. |
| 186 | QwenLM/Qwen3-Coder | https://github.com/QwenLM/Qwen3-Coder | unknown | 16833 | R7 | Qwen3-Coder code model family. |
| 187 | QwenLM/Qwen3 | https://github.com/QwenLM/Qwen3 | unknown | 27680 | R7 | Qwen3 model series, the family that includes small base models a student can start from. |
| 188 | QwenLM/Qwen2.5-Math | https://github.com/QwenLM/Qwen2.5-Math | unknown | 1083 | R7 | Math-specific model series from the Qwen team. |
| 189 | meta-llama/codellama | https://github.com/meta-llama/codellama | other | 16224 | R7 | Inference code for Code Llama models under the Llama licence. The repository is archived. |
| 190 | huggingface/trl | https://github.com/huggingface/trl | Apache-2.0 | 19570 | R1 | Reinforcement learning and SFT library with a GRPO trainer that accepts custom reward functions, including verifiers. |
| 191 | verl-project/verl | https://github.com/verl-project/verl | Apache-2.0 | 23979 | R1 | RL post-training framework (HybridFlow) with recipes for math and code verifiers. |
| 192 | OpenRLHF/OpenRLHF | https://github.com/OpenRLHF/OpenRLHF | Apache-2.0 | 10107 | R1 | Scalable RL and RLHF framework built on Ray. |
| 193 | huggingface/open-r1 | https://github.com/huggingface/open-r1 | Apache-2.0 | 26479 | R1 | Open reproduction of DeepSeek-R1 training, including code execution rewards. |
| 194 | rllm-org/rllm | https://github.com/rllm-org/rllm | Apache-2.0 | 5894 | R1 | Reinforcement learning framework for training LLM agents. |
| 195 | hiyouga/EasyR1 | https://github.com/hiyouga/EasyR1 | Apache-2.0 | 5205 | R1 | Efficient RL training framework built on verl. |
| 196 | hiyouga/LlamaFactory | https://github.com/hiyouga/LlamaFactory | Apache-2.0 | 75654 | R1 | Unified fine-tuning for over 100 models with SFT, LoRA and QLoRA. |
| 197 | unslothai/unsloth | https://github.com/unslothai/unsloth | Apache-2.0 | 78402 | R1 | Fast LoRA and QLoRA fine-tuning with reinforcement learning support on single GPUs. |
| 198 | axolotl-ai-cloud/axolotl | https://github.com/axolotl-ai-cloud/axolotl | Apache-2.0 | 12611 | R1 | Fine-tuning framework configured by YAML for SFT, LoRA and preference training. |
| 199 | huggingface/peft | https://github.com/huggingface/peft | Apache-2.0 | 21828 | R1 | LoRA and other parameter-efficient adapters for transformers. |
| 200 | bitsandbytes-foundation/bitsandbytes | https://github.com/bitsandbytes-foundation/bitsandbytes | MIT | 8529 | R1 | k-bit quantisation kernels used by QLoRA training. |
| 201 | meta-pytorch/torchtune | https://github.com/meta-pytorch/torchtune | BSD-3-Clause | 5819 | R1 | PyTorch-native post-training library with fine-tuning recipes. |
| 202 | modelscope/ms-swift | https://github.com/modelscope/ms-swift | Apache-2.0 | 15911 | R1 | SFT, DPO and GRPO training framework for over 600 LLMs. |
| 203 | NVIDIA-NeMo/RL | https://github.com/NVIDIA-NeMo/RL | Apache-2.0 | 2077 | R1 | Scalable RL toolkit for post-training models. |
| 204 | alibaba/ROLL | https://github.com/alibaba/ROLL | Apache-2.0 | 3433 | R1 | Reinforcement learning scaling library for LLMs. |
| 205 | allenai/open-instruct | https://github.com/allenai/open-instruct | Apache-2.0 | 3904 | R1 | AllenAI post-training codebase with verifiable-reward RL. |
| 206 | NovaSky-AI/SkyRL | https://github.com/NovaSky-AI/SkyRL | Apache-2.0 | 2443 | R1 | Modular full-stack RL library for LLMs. |
| 207 | InternLM/xtuner | https://github.com/InternLM/xtuner | Apache-2.0 | 5214 | R1 | Training engine for large models with SFT and RL support. |
| 208 | ggml-org/llama.cpp | https://github.com/ggml-org/llama.cpp | MIT | 131995 | R1 | Inference engine and GGUF format used to serve the small models in a local pipeline. |
| 209 | vllm-project/vllm | https://github.com/vllm-project/vllm | Apache-2.0 | 95089 | R1 | High-throughput inference engine used to sample many candidate proofs per problem. |
| 210 | FStarLang/steel | https://github.com/FStarLang/steel | Apache-2.0 | 40 | R2 | Steel separation logic library for F*, a checked library of verified imperative code. |
| 211 | project-everest/mitls-fstar | https://github.com/project-everest/mitls-fstar | other | 183 | R2 | Verified implementation of TLS 1.3 in F*, a large verified program. |
| 212 | huggingface/smollm | https://github.com/huggingface/smollm | Apache-2.0 | 3931 | R7 | SmolLM and SmolVLM small model family with training data and evaluation details. |
| 213 | huggingface/cosmopedia | https://github.com/huggingface/cosmopedia | Apache-2.0 | 578 | R6 | Synthetic textbook and story data generation pipeline, a reference for large synthetic corpora. |
| 214 | leanprover/vscode-lean4 | https://github.com/leanprover/vscode-lean4 | Apache-2.0 | 314 | R5 | VS Code extension for Lean 4, the editor front end most Lean users run. |
| 215 | Kripner/nanoproof | https://github.com/Kripner/nanoproof | MIT | 98 | R1, R5, R7 | Minimal open implementation of an AlphaProof-style prover built on nanochat, with math pretraining, Lean midtraining and miniF2F plots in the README. |
| 216 | facebookresearch/atlas-lean | https://github.com/facebookresearch/atlas-lean | other | 316 | R2, R6 | Large Lean 4 library of textbook mathematics formalized with LLMs, a synthetic autoformalization corpus. The licence differs by version, so GitHub reports other. |
| 217 | Weber-GeoML/Choir | https://github.com/Weber-GeoML/Choir | Apache-2.0 | 117 | R6 | Open protocol for distributed multi-agent autoformalization, a way to pool formalization work across agents. |
| 218 | PL-ML/code2inv | https://github.com/PL-ML/code2inv | unknown | 106 | R4 | Learns loop invariants for verification conditions with a neural model, an early learned-invariant system. |
| 219 | verse-lab/velvet | https://github.com/verse-lab/velvet | Apache-2.0 | 131 | R4, R5 | Auto-active program verifier in Lean, where specifications and loop invariants sit in the source program. |
| 220 | midspiral/LemmaScript | https://github.com/midspiral/LemmaScript | MIT | 120 | R4 | Verification toolchain for TypeScript with specification annotations, a prototype for writing checkable specs. |
| 221 | loganrjmurphy/LeanEuclid | https://github.com/loganrjmurphy/LeanEuclid | MIT | 145 | R3, R6 | Benchmark for autoformalization in Lean of Euclid-style geometry statements. |
| 222 | jesse-michael-han/lean-gptf | https://github.com/jesse-michael-han/lean-gptf | Apache-2.0 | 135 | R5 | Interactive neural theorem proving in Lean, the GPT-f style prover code. |
| 223 | augustepoiroux/LeanInteract | https://github.com/augustepoiroux/LeanInteract | MIT | 134 | R5 | Python interface to Lean 4 for driving the Lean REPL from scripts. |
| 224 | lukaszcz/coqhammer | https://github.com/lukaszcz/coqhammer | other | 249 | R5 | Automated reasoning hammer for Rocq that calls external provers and reconstructs their answers as Coq proofs. |
| 225 | HigherOrderCO/Kind | https://github.com/HigherOrderCO/Kind | MIT | 3761 | R5 | Modern proof language with a dependently typed core. |
| 226 | jscoq/jscoq | https://github.com/jscoq/jscoq | other | 548 | R5 | Coq ported to JavaScript so that proofs run in the browser. |
| 227 | rocq-prover/vsrocq | https://github.com/rocq-prover/vsrocq | MIT | 461 | R5 | Visual Studio Code extension for Rocq, the editor integration for Rocq projects. |
| 228 | epfl-lara/stainless | https://github.com/epfl-lara/stainless | Apache-2.0 | 408 | R5 | Verification framework for higher-order Scala programs, a verified-code toolchain outside Lean and Dafny. |
| 229 | verse-lab/veil | https://github.com/verse-lab/veil | Apache-2.0 | 343 | R5 | Verifier for automated and interactive proofs about transition systems, built on Lean. |
| 230 | aya-prover/aya-dev | https://github.com/aya-prover/aya-dev | MIT | 366 | R5 | Proof assistant and dependently typed language. |
| 231 | juxt/allium | https://github.com/juxt/allium | MIT | 517 | R4 | Specification language whose tooling gives feedback on specs, designed to be read and checked. |
| 232 | will62794/spectacle | https://github.com/will62794/spectacle | MIT | 224 | R4 | Interactive playground for exploring and sharing TLA+ specifications. |
| 233 | Verified-zkEVM/ArkLib | https://github.com/Verified-zkEVM/ArkLib | Apache-2.0 | 347 | R2 | Lean library of formally verified arguments of knowledge for zero-knowledge proofs. |
| 234 | FormalizedFormalLogic/Foundation | https://github.com/FormalizedFormalLogic/Foundation | Apache-2.0 | 296 | R2 | Lean formalisation of mathematical logic, a checked library. |
| 235 | rocq-community/fourcolor | https://github.com/rocq-community/fourcolor | other | 252 | R2 | Formal proof of the Four Color Theorem in Rocq, a large checked development. |
| 236 | bloomberg/crane | https://github.com/bloomberg/crane | LGPL-2.1 | 171 | R2, R5 | Extraction system from Rocq to functional-style code, a route from verified proofs to executable programs. |
| 237 | YuanheZ/lean-stat-learning-theory | https://github.com/YuanheZ/lean-stat-learning-theory | Apache-2.0 | 141 | R2 | Sorry-free Lean library for statistical learning theory, a checked corpus from 2026. |
| 238 | QuickChick/QuickChick | https://github.com/QuickChick/QuickChick | other | 294 | R3 | Randomized property-based testing plugin for Rocq, a way to test specifications before proving them. |
| 239 | wellecks/ntptutorial | https://github.com/wellecks/ntptutorial | MIT | 179 | R5 | Tutorial on neural theorem proving by the author of llmstep. |
| 240 | namin/llm-verified-with-monte-carlo-tree-search | https://github.com/namin/llm-verified-with-monte-carlo-tree-search | MIT | 295 | R1, R5 | Prototype that synthesizes verified code with an LLM, using Monte Carlo tree search and calling the verifier at each step. Targets Dafny, Coq, Lean, Scala and Rust. |
| 241 | Deducteam/lambdapi | https://github.com/Deducteam/lambdapi | other | 406 | R5 | Proof assistant based on the lambda-Pi calculus modulo rewriting, used as a checker for interoperable proofs. |
| 242 | formal-land/rocq-of-ocaml | https://github.com/formal-land/rocq-of-ocaml | MIT | 277 | R5 | Translates OCaml code to Rocq for verification. |
| 243 | rkthomps/CoqStoq | https://github.com/rkthomps/CoqStoq | unknown | 12 | R2, R3 | Benchmark for evaluating Coq proof search tools, the dataset used by Rango-style proof search. |
| 244 | pink10000/coq-rango | https://github.com/pink10000/coq-rango | unknown | 0 | R5 | Coq tactic that implements the Rango proof synthesis tool. |
| 245 | dybolo/verus-agent-benchmark | https://github.com/dybolo/verus-agent-benchmark | MIT | 0 | R3, R5 | Docker-based benchmark for coding agents that repair incomplete Verus proofs in concurrent Rust programs, checked with Verus and Lynette. |
| 246 | therewillbecode/lean-workbook | https://github.com/therewillbecode/lean-workbook | MIT | 0 | R2 | Collection of maths exercises and solutions for Lean 4, a small corpus. This is not the InternLM Lean Workbook release. |
| 247 | dwrensha/compfiles | https://github.com/dwrensha/compfiles | Apache-2.0 | 256 | R2, R3 | Catalog of math problems formalized in Lean, with statements and solutions for competition problems. |
| 248 | openai/prm800k | https://github.com/openai/prm800k | MIT | 2154 | R1 | 800,000 step-level correctness labels on model solutions to MATH problems, the process supervision data behind verifier-style reward models. The repository is archived. |
| 249 | RLHFlow/RLHF-Reward-Modeling | https://github.com/RLHFlow/RLHF-Reward-Modeling | Apache-2.0 | 1545 | R1 | Recipes for training reward models for RLHF, a route to learned verifiers for reasoning. |
| 250 | google-deepmind/alphageometry | https://github.com/google-deepmind/alphageometry | Apache-2.0 | 4901 | R5 | Neuro-symbolic geometry prover that pairs a language model with a symbolic deduction engine. |
